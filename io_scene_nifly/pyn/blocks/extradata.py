"""Extra data blocks: bounds, furniture markers, text keys, string and integer data,
behaviour graphs, inventory markers, BSX flags and connect points."""

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
from .base import NiObject


log = logging.getLogger("pynifly")


class NiExtraData(NiObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._name = None

    @property
    def name(self):
        if self._name == None:
            namebuf = (c_char * self.file.max_string_len)()
            nifly.getString(
                self.file._handle, self.properties.nameID, self.file.max_string_len, namebuf)
            self._name = namebuf.value.decode('utf-8')
        return self._name
    
    @name.setter
    def name(self, value):
        self._name = value
        if self.file and self.id != NODEID_NONE:
            self.properties.nameID = nifly.addString(
                self.file._handle, value.encode('utf-8'))
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))


class BSBound(NiExtraData):
    buffer_type = PynBufferTypes.BSBoundBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSBoundBuf(values)
    
    @property
    def center(self):
        return (self.properties.center[:])
    
    @center.setter
    def center(self, value):
        for i in range(0, 3):
            self.properties.center[i] = value[i]

    @property
    def half_extents(self):
        return (self.properties.halfExtents[:])
    
    @half_extents.setter
    def half_extents(self, value):
        for i in range(0, 3):
            self.properties.halfExtents[i] = value[i]

    @classmethod
    def New(cls, file, name='', center=(0, 0, 0), half_extents=(0, 0, 0), parent=None):
        p = BSBoundBuf()
        for i in range(0, 3):
            p.center[i] = center[i]
            p.halfExtents[i] = half_extents[i]
        return file.add_block(name, p, parent)


class BSFurnitureMarkerNode(NiExtraData):
    buffer_type = PynBufferTypes.BSFurnitureMarkerNodeBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._furniture_markers = None

    @classmethod
    def getbuf(cls, values=None):
        return BSFurnitureMarkerNodeBuf(values)
    
    @property
    def position_count(self):
        """
        Number of furniture marker positions.
        """
        return self.properties.position_count
    
    @property
    def furniture_markers(self) -> List[FurnitureMarkerDataBuf]:
        """
        Get furniture marker data as list of FurnitureMarkerDataBuf objects.
        """
        if self._furniture_markers is None:
            self._furniture_markers = []
            if self.properties.position_count > 0:
                # Get each furniture marker position individually
                for i in range(self.properties.position_count):
                    marker = FurnitureMarkerDataBuf()
                    result = nifly.getFurnitureMarkerPosition(
                        self.file._handle, self.id, i, byref(marker))
                    if result == 0:
                        # Create a copy of the marker data
                        marker_copy = FurnitureMarkerDataBuf()
                        marker_copy.offset[0] = marker.offset[0]
                        marker_copy.offset[1] = marker.offset[1]
                        marker_copy.offset[2] = marker.offset[2]
                        marker_copy.heading = marker.heading
                        marker_copy.animation_type = marker.animation_type
                        marker_copy.entry_points = marker.entry_points
                        self._furniture_markers.append(marker_copy)
        return self._furniture_markers
    
    @furniture_markers.setter
    def furniture_markers(self, value: List[FurnitureMarkerDataBuf]):
        """
        Set furniture marker data from list of FurnitureMarkerDataBuf objects.
        """
        self._furniture_markers = value
        self.properties.position_count = len(value)
        if self.file and self.id != NODEID_NONE:
            # Update the position count first
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))
            
            # Add each furniture marker position
            if value:
                for marker in value:
                    marker_buf = FurnitureMarkerDataBuf()
                    marker_buf.offset[0] = float(marker.offset[0])
                    marker_buf.offset[1] = float(marker.offset[1])
                    marker_buf.offset[2] = float(marker.offset[2])
                    marker_buf.heading = float(marker.heading)
                    marker_buf.animation_type = int(marker.animation_type)
                    marker_buf.entry_points = int(marker.entry_points)
                    check_return(nifly.addFurnitureMarkerPosition, 
                                self.file._handle, self.id, byref(marker_buf))

    @classmethod
    def New(cls, file, name='', furniture_markers=None, parent=None):
        """
        Create a new BSFurnitureMarkerNode.
        
        Args:
            file: NifFile to add the node to
            name: Name for the node
            furniture_markers: List of FurnitureMarkerDataBuf objects
            parent: Parent node
        """
        if furniture_markers is None:
            furniture_markers = []
        p = BSFurnitureMarkerNodeBuf()
        fm_node = file.add_block(name, p, parent)
        
        # Add each furniture marker position directly
        if furniture_markers:
            for marker in furniture_markers:
                marker_buf = FurnitureMarkerDataBuf()
                marker_buf.offset[0] = float(marker.offset[0])
                marker_buf.offset[1] = float(marker.offset[1])
                marker_buf.offset[2] = float(marker.offset[2])
                marker_buf.heading = float(marker.heading)
                marker_buf.animation_type = int(marker.animation_type)
                marker_buf.entry_points = int(marker.entry_points)
                check_return(nifly.addFurnitureMarkerPosition, 
                            file._handle, fm_node.id, byref(marker_buf))
        return fm_node


class NiTextKeyExtraData(NiExtraData):
    buffer_type = PynBufferTypes.NiTextKeyExtraDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._keys = None

    @classmethod 
    def getbuf(cls, values=None):
        return NiTextKeyExtraDataBuf(values)

    @property 
    def keys(self):
        """
        Text keys returned as [(time, "value"), ...]
        """
        if self._keys is None:
            self._keys = []
            for i in range(0, self.properties.textKeyCount):
                buf = TextKeyBuf()
                nifly.getNiTextKey(
                    self.file._handle, self.id, i, byref(buf))
                self._keys.append((buf.time, self.file.get_string(buf.valueID),))
        return self._keys
    
    def add_key(self, time, val):
        if self._keys is None: self._keys = []
        err = nifly.addTextKey(
            self.file._handle, self.id, time, val.encode('utf-8'))
        self._keys.append((time, val,))

    @classmethod
    def New(cls, file, name='', keys=(), parent=None):
        p = NiTextKeyExtraDataBuf()
        tk = file.add_block(name, p, parent)
        for t, v in keys:
            tk.add_key(t, v)
        return tk


class NiIntegerExtraData(NiExtraData):
    buffer_type = PynBufferTypes.NiIntegerExtraDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod 
    def getbuf(cls, values=None):
        return NiIntegerExtraDataBuf(values)

    @property 
    def integer_data(self):
        """
        Integer value stored in this extra data block.
        """
        return self.properties.integerData
    
    @integer_data.setter
    def integer_data(self, value):
        """
        Set the integer value for this extra data block.
        """
        self.properties.integerData = value
        if self.file and self.id != NODEID_NONE:
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))

    @classmethod
    def New(cls, file, name='', integer_value=0, parent=None):
        p = NiIntegerExtraDataBuf()
        p.integerData = integer_value
        return file.add_block(name, p, parent)


class NiIntegersExtraData(NiExtraData):
    """PLURAL -- a different block type from NiIntegerExtraData, holding an ARRAY of uint32.

    Starfield stores 'AnimationFlagExtra' this way: 273 of 373 vanilla shape nifs carry one, on the
    BSGeometry block. Values seen are hair 31, beards 47, eyes/teeth/tongue/eyebrows/tears 255,
    male head 32. Eyelashes carry no block at all -- the only part in human\\characterassets that
    doesn't -- so absence is legal and must not be "corrected" on export. It is authored data, not
    derived, so it round-trips verbatim rather than being recomputed on export."""
    buffer_type = PynBufferTypes.NiIntegersExtraDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod
    def getbuf(cls, values=None):
        return NiIntegersExtraDataBuf(values)

    @property
    def values(self):
        """The block's integers, as a list."""
        n = self.properties.integerCount
        if not n:
            return []
        buf = (c_uint32 * n)()
        got = nifly.getNiIntegersExtraDataValues(self.file._handle, self.id, buf, n)
        return list(buf[:got])

    @values.setter
    def values(self, v):
        v = list(v)
        buf = (c_uint32 * len(v))(*v)
        nifly.setNiIntegersExtraDataValues(self.file._handle, self.id, buf, len(v))
        self.properties.integerCount = len(v)

    @classmethod
    def New(cls, file, name='', values=None, parent=None):
        values = list(values or [])
        p = NiIntegersExtraDataBuf()
        p.integerCount = len(values)
        block = file.add_block(name, p, parent)
        if values:
            block.values = values
        return block


class BoneTranslations(NiExtraData):
    """Starfield: (bone name, position) pairs on the root node.

    Every vanilla crowd head carries one named 'BoneTrn' -- 102 of 102, and nothing else does --
    giving L_Eye and R_Eye relative to C_Head, in metres, in C_Head's frame: where that face has
    its eyes. The engine moves the actor's eye bones there; without it a crowd head's eyes are drawn
    at the skeleton's eye bones (the European face's), off by up to a centimetre. Authored data:
    PyNifly writes one only when Blender has it."""
    buffer_type = PynBufferTypes.BoneTranslationsBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod
    def getbuf(cls, values=None):
        return BoneTranslationsBuf(values)

    @property
    def translations(self):
        """[(bone name, (x, y, z))], in file order."""
        n = self.properties.translationCount
        if not n:
            return []
        vbuf = (c_float * 3 * n)()
        need = nifly.getBoneTranslationsData(self.file._handle, self.id, None, 0, vbuf, n)
        names = create_string_buffer(need + 1)
        nifly.getBoneTranslationsData(self.file._handle, self.id, names, need + 1, vbuf, n)
        bones = names.value.decode('utf-8').split('\n')
        return [(bones[i], (vbuf[i][0], vbuf[i][1], vbuf[i][2])) for i in range(n)]

    @translations.setter
    def translations(self, entries):
        entries = list(entries)
        vbuf = (c_float * 3 * len(entries))(*[tuple(v) for _, v in entries])
        names = '\n'.join(b for b, _ in entries).encode('utf-8')
        nifly.setBoneTranslationsData(self.file._handle, self.id, names, vbuf, len(entries))
        self.properties.translationCount = len(entries)

    @classmethod
    def New(cls, file, name='', translations=None, parent=None):
        translations = list(translations or [])
        p = BoneTranslationsBuf()
        p.translationCount = len(translations)
        block = file.add_block(name, p, parent)
        if translations:
            block.translations = translations
        return block


class BSBehaviorGraphExtraData(NiExtraData):
    buffer_type = PynBufferTypes.BSBehaviorGraphExtraDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod 
    def getbuf(cls, values=None):
        return BSBehaviorGraphExtraDataBuf(values)

    @property 
    def behavior_graph_file(self):
        """
        Behavior graph file path stored in this extra data block.
        """
        if self.properties.behaviorGraphFileID == NODEID_NONE:
            return ""
        namebuf = (c_char * self.file.max_string_len)()
        nifly.getString(
            self.file._handle, self.properties.behaviorGraphFileID, self.file.max_string_len, namebuf)
        return namebuf.value.decode('utf-8')
    
    @behavior_graph_file.setter
    def behavior_graph_file(self, value):
        """
        Set the behavior graph file path for this extra data block.
        """
        self.properties.behaviorGraphFileID = nifly.addString(
            self.file._handle, value.encode('utf-8'))
        if self.file and self.id != NODEID_NONE:
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))

    @property 
    def controls_base_skeleton(self):
        """
        Boolean flag indicating whether this behavior graph controls the base skeleton.
        """
        return bool(self.properties.controlsBaseSkeleton)
    
    @controls_base_skeleton.setter
    def controls_base_skeleton(self, value):
        """
        Set the controls base skeleton flag for this extra data block.
        """
        self.properties.controlsBaseSkeleton = 1 if value else 0
        if self.file and self.id != NODEID_NONE:
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))

    @classmethod
    def New(cls, file, name='', behavior_graph_file='', controls_base_skeleton=False, parent=None):
        p = BSBehaviorGraphExtraDataBuf()
        p.behaviorGraphFileID = nifly.addString(file._handle, behavior_graph_file.encode('utf-8'))
        p.controlsBaseSkeleton = 1 if controls_base_skeleton else 0
        return file.add_block(name, p, parent)


class BSDecalPlacementVectorExtraData(NiExtraData):
    buffer_type = PynBufferTypes.BSDecalPlacementVectorExtraDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod
    def getbuf(cls, values=None):
        return BSDecalPlacementVectorExtraDataBuf(values)

    @property
    def vector_blocks(self):
        """Return list of vector blocks; each block is a list of (point, normal) tuples.

        point and normal are each (x, y, z) float tuples.
        """
        blocks = []
        for bi in range(self.properties.numVectorBlocks):
            count = c_uint16()
            nifly.getDecalVectorBlockCount(
                self.file._handle, self.id, bi, byref(count))
            vectors = []
            for vi in range(count.value):
                vbuf = DecalVectorBuf()
                nifly.getDecalVector(
                    self.file._handle, self.id, bi, vi, byref(vbuf))
                vectors.append((tuple(vbuf.point), tuple(vbuf.normal)))
            blocks.append(vectors)
        return blocks

    @classmethod
    def New(cls, file, name='', vector_blocks=None, parent=None):
        p = BSDecalPlacementVectorExtraDataBuf()
        p.numVectorBlocks = len(vector_blocks) if vector_blocks else 0
        node = file.add_block(name, p, parent)
        if vector_blocks:
            for bi, block in enumerate(vector_blocks):
                nifly.addDecalVectorBlock(file._handle, node.id)
                for point, normal in block:
                    vbuf = DecalVectorBuf()
                    vbuf.point[:] = point
                    vbuf.normal[:] = normal
                    nifly.addDecalVector(
                        file._handle, node.id, bi, byref(vbuf))
        return node


class NiStringExtraData(NiExtraData):
    buffer_type = PynBufferTypes.NiStringExtraDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod 
    def getbuf(cls, values=None):
        return NiStringExtraDataBuf(values)

    @property 
    def string_data(self):
        """
        String value stored in this extra data block.
        """
        if self.properties.stringDataID == NODEID_NONE:
            return ""
        namebuf = (c_char * self.file.max_string_len)()
        nifly.getString(
            self.file._handle, self.properties.stringDataID, self.file.max_string_len, namebuf)
        return namebuf.value.decode('utf-8')
    
    @string_data.setter
    def string_data(self, value):
        """
        Set the string value for this extra data block.
        """
        self.properties.stringDataID = nifly.addString(
            self.file._handle, value.encode('utf-8'))
        if self.file and self.id != NODEID_NONE:
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))

    @classmethod
    def New(cls, file, name='', string_value='', parent=None):
        p = NiStringExtraDataBuf()
        p.stringDataID = nifly.addString(file._handle, string_value.encode('utf-8'))
        return file.add_block(name, p, parent)


class BSBoneLODExtraData(NiExtraData):
    buffer_type = PynBufferTypes.BSBoneLODBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._lod_data = None

    @classmethod 
    def getbuf(cls, values=None):
        return BSBoneLODBuf(values)

    @property 
    def lod_data(self):
        """
        LOD data returned as [(bone_name, distance), ...]
        """
        if self._lod_data is None:
            self._lod_data = []
            if self.properties.lodCount > 0:
                lodbuf = (BoneLODInfoBuf * self.properties.lodCount)()
                check_msg(nifly.getBoneLODInfo, self.file._handle, self.id, byref(lodbuf), self.properties.lodCount)
                for li in lodbuf:
                    self._lod_data.append((self.file.get_string(li.nameID), li.distance))
        return self._lod_data
    
    @lod_data.setter
    def lod_data(self, value):
        """
        Set the LOD data for this extra data block.
        value: [(bone_name, distance), ...]
        """
        self._lod_data = value
        self.properties.lodCount = len(value)
        if self.file and self.id != NODEID_NONE:
            check_return(nifly.setBlock, self.file._handle, self.id, byref(self.properties))
            
            # Set the LOD info array
            lodbuf = (BoneLODInfoBuf * len(value))()
            for i, (bone_name, distance) in enumerate(value):
                lodbuf[i].distance = distance
                lodbuf[i].nameID = check_msg(
                    nifly.addString, self.file._handle, bone_name.encode('utf-8'))
            check_return(nifly.setBoneLOD, self.file._handle, self.id, len(value), byref(lodbuf))

    @classmethod
    def New(cls, file, name='', lodlist=None, parent=None):
        if lodlist is None:
            lodlist = []
        p = BSBoneLODBuf()
        p.lodCount = len(lodlist)
        bone_lod = file.add_block(name, p, parent)
        lodbuf = (BoneLODInfoBuf * len(lodlist))()
        for i, lod in enumerate(lodlist):
            lodbuf[i].distance = lod[1]
            lodbuf[i].nameID = check_msg(
                nifly.addString, file._handle, lod[0].encode('utf-8'))
        check_return(nifly.setBoneLOD, 
                     file._handle, bone_lod.id, len(lodlist), byref(lodbuf))
        return bone_lod


class BSInvMarker(NiExtraData):
    buffer_type = PynBufferTypes.BSInvMarkerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod 
    def getbuf(cls, values=None):
        return BSInvMarkerBuf(values)

    @property 
    def rotation(self):
        """
        Rotation values for inventory marker as (x, y, z) tuple.
        """
        return (self.properties.rot0, self.properties.rot1, self.properties.rot2)
    
    @rotation.setter
    def rotation(self, value):
        """
        Set the rotation values for inventory marker.
        value: (x, y, z) tuple
        """
        if len(value) != 3:
            raise ValueError("Rotation tuple must have exactly 3 values (x, y, z)")
        self.properties.rot0 = int(value[0])
        self.properties.rot1 = int(value[1])
        self.properties.rot2 = int(value[2])
        if self.file and self.id != NODEID_NONE:
            nifly.setBlock(self.file._handle, self.id, byref(self.properties))

    @property 
    def zoom(self):
        """
        Zoom value for inventory marker.
        """
        return self.properties.zoom
    
    @zoom.setter
    def zoom(self, value):
        """
        Set the zoom value for inventory marker.
        """
        self.properties.zoom = float(value)
        if self.file and self.id != NODEID_NONE:
            nifly.setBlock(self.file._handle, self.id, byref(self.properties))

    @classmethod
    def New(cls, file, name='INV', rotation=(0, 0, 0), zoom=1.0, parent=None):
        p = BSInvMarkerBuf()
        p.rot0 = int(rotation[0])
        p.rot1 = int(rotation[1])
        p.rot2 = int(rotation[2])
        p.zoom = float(zoom)
        return file.add_block(name, p, parent)


class BSXFlags(NiExtraData):
    buffer_type = PynBufferTypes.BSXFlagsBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

    @classmethod 
    def getbuf(cls, values=None):
        return BSXFlagsBuf(values)

    @property 
    def flags(self) -> BSXFlagsValues:
        """
        BSX flags integer value.
        """
        return BSXFlagsValues(self.properties.integerData)
    
    @flags.setter
    def flags(self, value):
        """
        Set the BSX flags integer value.
        """
        self.properties.integerData = int(value)
        if self.file and self.id != NODEID_NONE:
            nifly.setBlock(self.file._handle, self.id, byref(self.properties))

    @classmethod
    def New(cls, file, name='BSX', flags=0, parent=None):
        p = BSXFlagsBuf()
        p.integerData = int(flags)
        return file.add_block(name, p, parent)


class BSConnectPointParents(NiExtraData):
    """
    These are a type of extra data but they get special handling. So this definition
    is a dummy so that reading extra data doesn't trip over them.
    TODO: Handle them like furniture markers.
    """
    buffer_type = PynBufferTypes.NiNodeBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._parents = None


class BSConnectPointChildren(NiExtraData):
    """Dummy class so BSConnectPoint::Children blocks are recognised and silently skipped."""
    buffer_type = PynBufferTypes.NiNodeBufType

    @classmethod 
    def getbuf(cls, values=None):
        return NiNodeBuf(values)


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .base import (check_msg, check_return)  # noqa: E402
