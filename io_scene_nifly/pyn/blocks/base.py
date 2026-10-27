"""The root of the block hierarchy -- NiObject, NiObjectNET, NiProperty, NiAVObject --
and the helpers every block uses: DLL return checks, weight conversion, partitions."""

from __future__ import annotations

import os
from enum import Enum
import re
import logging
from ctypes import *
from typing import ValuesView, List
from collections.abc import MutableMapping
import xml.etree.ElementTree as xml
from pathlib import Path
from ..niflytools import *
from ..nifdefs import *
from ..niflydll import nifly, nifly_path
from ..nifconstants import BSXFlagsValues, HAVOC_SCALE_FACTOR, game_traits


log = logging.getLogger("pynifly")


def check_return(func, *args, **kwargs):
    _niffile.NifFile.clear_log()
    errval = 0
    try:
        errval = func(*args, **kwargs)
    except Exception as e:
        raise Exception(f"Error calling nifly {func.__name__}: {e}")
    if func.restype is None:
        if _niffile.NifFile.message_log():
            raise Exception(f"Error calling nifly {func.__name__}: " + (_niffile.NifFile.message_log()))
    elif errval != 0:
        raise Exception(f"Error calling nifly {func.__name__}: "
            + (_niffile.NifFile.message_log() if _niffile.NifFile.message_log() else "(no message)"))


def dll_string(func, *args, size=128):
    """Read a string from a DLL getter called as func(*args, buf, buflen) that returns the
    string's full length. If the first read was truncated, read again with a buffer big
    enough (Len-then-fill)."""
    buf = create_string_buffer(size)
    n = func(*args, buf, size)
    if n >= size:
        buf = create_string_buffer(n + 1)
        func(*args, buf, n + 1)
    return buf.value.decode('utf-8')


def check_msg(func, *args, **kwargs):
    nifly.clearMessageLog()
    try:
        retval = func(*args, **kwargs)
        if _niffile.NifFile.message_log():
            raise Exception(f"Error calling nifly {func.__name__}: " + (_niffile.NifFile.message_log()))
    except Exception as e:
        raise Exception(f"Error calling nifly {func.__name__}: {e}") from e
    return retval


def check_id(func, *args, **kwargs):
    nifly.clearMessageLog()
    try:
        retval = func(*args, **kwargs)
        if (retval or 0xFFFFFFFF) == NODEID_NONE:
            raise Exception(f"Error calling nifly {func.__name__}: " + (_niffile.NifFile.message_log()))
    except Exception as e:
        raise Exception(f"Error calling nifly {func.__name__}: {_niffile.NifFile.message_log()}") from e
    return retval


def get_weights_by_bone(weights_by_vert, used_groups):
    """Given a list of weights 1-1 with vertices, return weights organized by bone. 
        weights_by_vert = [dict[group-name: weight], ...] 1-1 with verts
        Result: {group_name: [(vert_index, weight), ...], ...}
        Result contains only groups with non-zero weights, only groups that are in the 
        used-groups list, and only the 4 heaviest weights, which are normalized to add up to 1.
    """
    result = {}
    #Get weights by group
    for vert_index, vert_weights in enumerate(weights_by_vert):
        weight_pairs = [(w, nm) for nm, w in vert_weights.items() if w > 0.00005 and nm in used_groups]
        weight_pairs.sort()
        weight_pairs.reverse()
        sum_weights = sum(vw for vw, nm in weight_pairs[0:4])
        for wgt, nm in weight_pairs[0:4]:
            if nm not in result:
                result[nm] = []
            result[nm].append((vert_index, wgt/sum_weights))
            
    return result


def get_weights_by_vertex(verts, weights_by_bone):
    """Given a list of weights by bone, return a list 1:1 with vertices"""
    wbv = [None] * len(verts)
    for i in range(0, len(verts)):
        wbv[i] = {}
        
    for this_bone, this_weightlist in weights_by_bone.items():
        for weight_pair in this_weightlist:
            this_vert, this_weight = weight_pair
            wbv[this_vert][this_bone] = this_weight
    return wbv


class Partition:
    def __init__(self, part_id=0, namedict=None, name=None):
        self.id = part_id
        self._name = name
        self.namedict = namedict

    @property
    def name(self):
        if self._name:
            return self._name
        else:
            return f"{self.__class__.__name__} #{self.id}"

    @name.setter
    def name(self, val):
        if val:
            self._name = val

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    def __le__(self, other):
        return self.name <= other.name

    def __gt__(self, other):
        return self.name > other.name

    def __ge__(self, other):
        return self.name >= other.name


class SkyPartition(Partition):
    skymatch = re.compile(r'SBP_([0-9]+)_\w+')

    def __init__(self, part_id=0, flags=0, namedict=None, name=None):
        super().__init__(part_id, namedict, name)
        self.flags = flags
        if not self._name:
            bp = namedict.part_by_id(part_id)
            if bp:
                self._name = bp.name
            else:
                self._name = f"SBP_{part_id}_UNKNOWN"

    @classmethod
    def name_match(cls, name):
        m = SkyPartition.skymatch.match(name)
        if m:
            return int(m.group(1))
        else:
            return -1


class FO4Segment(Partition):
    fo4segmatch = re.compile(r'FO4\w+ \#*([0-9]+)\Z')
    fo4segmatch1 = re.compile(r'FO4 Seg +([0-9]+)\Z')

    def __init__(self, part_id=0, index=0, subsegments=0, namedict=fo4Dict, name=None):
        super().__init__(part_id, namedict=namedict, name=name)
        self.index = index
        self.subseg_count = subsegments
        self.subsegments = []

    @property
    def name(self):
        """ FO4 segments don't have proper names. Build a fake name from the ID
            """
        if self._name:
            return self._name
        else:
            return "FO4 Seg " + '{:0>3d}'.format(self.index)

    @classmethod
    def name_match(cls, name):
        m = FO4Segment.fo4segmatch1.match(name)
        if m:
            return int(m.group(1))

        m = FO4Segment.fo4segmatch.match(name)
        if m:
            return int(m.group(1))
        else:
            return -1


class FO4Subsegment(FO4Segment):
    fo4subsegm1 = re.compile(r'(FO4 Seg [0-9]+) \| ([^\|]+)( \| (.+))?\Z')
    fo4subsegm = re.compile(r'\AFO4 *.*')
    fo4bpm = re.compile(r'\AFO4 *(\d+) - ')

    def __init__(self, part_id, user_slot, material=-1, parent=None, namedict=fo4Dict, name=None):
        """
        part_id = unique id used inside the nif
        user_slot = user index
        material = bone ID
        parent = parent segment
        namedict = dictionary to use
        name = name for the subsegment. If not provided, will be constructed.
        """
        super().__init__(part_id, user_slot, 0, namedict, name)
        self.user_slot = user_slot
        self.material = material
        # Slice-plane positions along the dismember bone (the "cut offsets" in
        # BSGeometryPerSegmentSharedData). Empty on most subsegments; only the
        # bearer of each material carries a non-empty list (0-8 floats).
        self.cut_offsets = []
        if name:
            self._name = name
        else:
            bp_name = namedict.part_by_id(user_slot)
            if not bp_name:
                if user_slot == 0:
                    bp_name = '{:0>3d}'.format(len(parent.subsegments))
                else:
                    bp_name = '{:0>3d}'.format(user_slot)

            mat_name = namedict.dismem_by_id(material)
            if not mat_name:
                mat_name = ""
                if material != 0xffffffff:
                    mat_name = '0x{:0>8x}'.format(material)
            if len(mat_name) > 0:
                mat_name = " | " + mat_name

            self._name = f"{parent.name} | {bp_name}{mat_name}"

        self.parent = parent
        parent.subsegments.append(self)

    @property
    def parent_name(self):
        self.parent.name

    @classmethod
    def name_match(cls, name):
        """ Determine whether given string is a valid FO4Subsegment name. Ignore any numeral after a hash. Returned parent name comes from built-in name structure.
            Returns: name of parent, ID (body part # or dismember hash), dismember hash of parent
        """
        mat = 0
        m = FO4Subsegment.fo4subsegm1.match(name)
        if m:
            id = 0
            mat = -1
            try:
                if len(m.groups()) >= 2:
                    if m[2] in fo4Dict.parts:
                        id = fo4Dict.parts[m[2]]
                    else:
                        id = int(m[2])
                if len(m.groups()) >= 4 and m[4]:
                    if m[4] in fo4Dict.dismem:
                        mat = fo4Dict.dismem[m[4]]
                    else:
                        mat = int(m[4], 0)
            except Exception:
                log.error(f"Cannot parse segment name: {name}")
            return(m[1], id, mat)

        m = FO4Subsegment.fo4bpm.match(name)
        if m:
            subseg_id = int(m.group(1))
            parent_name = ''
            return (parent_name, subseg_id, mat)
        
        m = FO4Subsegment.fo4subsegm.match(name)
        if m:
            subseg_id = 0
            return ('', subseg_id, mat)
        else:
            return ("", -1, mat)


# --- NiObject -- #
class NiObject:
    """ Represents any block in a nif file. """
    
    # These are the types of blocks we can create from an ID. {classname: class, ...}
    block_types = {}
    # This is an array indexed by buffer type, containing the associated classes.
    buffer_types = [None] * PynBufferTypes.COUNT

    # Buffer used to pass properties across the DLL layer. Overridden by subtypes.
    buffer_type = -1
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        self._handle = handle
        self._controller = None
        self.file:_niffile.NifFile = file
        self.id = id
        if handle is None and id != NODEID_NONE and file is not None:
            self._handle = check_msg(nifly.getNodeByID,file._handle, id)
        if self.id == NODEID_NONE and handle is not None and file is not None:
            self.id = check_msg(nifly.getBlockID, self.file._handle, self._handle)
        self._parent = parent
        if properties:
            self._properties = properties
        else:
            self._properties = None
        self._blockname = None
    
    @property
    def blockname(self):
        if self._blockname == None:
            if self.id == NODEID_NONE:
                self._blockname = self.__class__.__name__
            else:
                self._blockname = dll_string(nifly.getBlockname, self.file._handle, self.id)
        return self._blockname
    
    @property
    def properties(self):
        if not self._properties:
            self._properties = self.getbuf()
            if self.id != NODEID_NONE and self.file._handle:
                check_return(nifly.getBlock,
                    self.file._handle, 
                    self.id, 
                    byref(self._properties))
        return self._properties
    
    @properties.setter
    def properties(self, value):
        self._properties = value.copy()
        check_return(
            nifly.setBlock, self.file._handle, self.id, byref(self._properties))
        
    def write_properties(self):
        """ Write current properties to the nif file. """
        check_return(
            nifly.setBlock, self.file._handle, self.id, byref(self._properties))

    def register_subclasses():
        """Register all subclasses for easy finding."""
        subclasses = list(NiObject.__subclasses__())
        while subclasses:
            sc = subclasses.pop(0)
            NiObject.block_types[sc.__name__] = sc
            NiObject.buffer_types[sc.buffer_type] = sc
            subclasses = subclasses + sc.__subclasses__()

    @classmethod
    def _buftype_name(cls, buftype):
        """Given a buffer type id, return the associated class name."""
        return cls.buffer_types[buftype].__name__

    @classmethod
    def getbuf(cls, values=None):
        """To be overwritten by subclasses."""
        assert False, "getbuf should have been overwritten."


class NiObjectNET(NiObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None, name=""):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._name = name
        self._controller = None
        self._bgdata = None
        self._strdata = None
        self._clothdata = None

        if self._handle:
            self.properties
            buflen = self.file.max_string_len
            buf = create_string_buffer(buflen)
            nifly.getNodeName(self._handle, buf, buflen)
            self._name = buf.value.decode('utf-8')
            if id == NODEID_NONE:
                self.id = nifly.getBlockID(self.file._handle, self._handle)

        self.file.register_node(self)


    @property
    def name(self):
        if self._name == None:
            namebuf = (c_char * self.file.max_string_len)()
            nifly.getString(
                self.file._handle, self._properties.nameID, self.file.max_string_len, namebuf)
            self._name = namebuf.value.decode('utf-8')
        return self._name
    
    @name.setter
    def name(self, value):
        if self.file: self.file.unregister_name(self)
        self._name = value
        if self.file: 
            if self.id != NODEID_NONE:
                self.properties.nameID = nifly.addString(
                    self.file._handle, value.encode('utf-8'))
                check_return(
                    nifly.setBlock, self.file._handle, self.id, byref(self._properties))

            self.file.register_node(self)
        

    @property
    def controller(self):
        if self._controller: return self._controller
        if self.properties.controllerID == NODEID_NONE: return None
        self._controller = self.file.read_node(id=self.properties.controllerID, parent=self)
        return self._controller
    
    @controller.setter
    def controller(self, c):
        self._controller = c
        self.properties.controllerID = c.id
        nifly.setController(self.file._handle, self.id, c.id)


class NiProperty(NiObjectNET):
    pass


class NiAVObject(NiObjectNET):
    def add_collision(self, body, flags=None, collision_type=None, body_id=None):
        if collision_type == PynBufferTypes.bhkSPCollisionObjectBufType:
            buf = bhkSPCollisionObjectBuf()
        elif collision_type == PynBufferTypes.bhkPCollisionObjectBufType:
            buf = bhkPCollisionObjectBuf()
        elif collision_type == PynBufferTypes.bhkNiCollisionObjectBufType:
            buf = bhkNiCollisionObjectBuf()
        elif collision_type == PynBufferTypes.bhkNPCollisionObjectBufType:
            buf = bhkNPCollisionObjectBuf()
        else:
            buf = bhkCollisionObjectBuf()
        if flags is not None: buf.flags = flags
        buf.targetID = self.id
        if collision_type == PynBufferTypes.bhkNPCollisionObjectBufType:
            # bodyID indexes the shared bhkPhysicsSystem's body array. It defaults
            # to a sentinel; leaving it unset makes the engine dereference a bad
            # index in bhkNPCollisionObject::CreateInstance and crash, so the
            # caller must pass the body this node uses.
            if body_id is not None:
                buf.bodyID = body_id
        else:
            buf.bodyID = NODEID_NONE
            if body: buf.bodyID = body.id
        new_coll = _collision.NiCollisionObject.New(file=self.file, properties=buf, parent=self)
        return new_coll


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from . import collision as _collision  # noqa: E402
from . import niffile as _niffile  # noqa: E402
