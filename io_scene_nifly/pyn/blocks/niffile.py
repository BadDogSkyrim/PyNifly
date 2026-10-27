"""NifFile: one nif on disk, opened or created through the DLL. Also the HKX skeleton file."""

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


# --- NifFile --- #
class NifFile:
    """ NifFile represents the file itself. Corresponds approximately to a NifFile in the 
        Nifly layer, but we've hidden the AnimInfo object in here too.
        """
    has_extra_data = True
    log = logging.getLogger("pynifly")

    def Load(path):
        # No longer needed since library loads automatically
        pass
    
    def __init__(self, filepath=None, materialsRoot=None):
        """
        Initialize the nif file object.
        For ease of testing, materialsRoot indicates where to find the materials files. If
        not provided, the nif's own path will be used.
        """
        self.filepath = filepath
        self._handle = None
        self._game = None
        self._root = None
        if filepath is not None:
            self._handle = nifly.load(str(filepath).encode('utf-8'))
            if not self._handle:
                raise Exception(f"Could not open '{filepath}' as nif")
        self._skin_handle = None
        if self.game is not None:
            self.dict = gameSkeletons[self.game]
        self._bgdata = None
        self._strdata = None
        self._clothdata = None
        self._furniture_markers = None
        self._connect_pt_par = None
        self._connect_pt_child = None
        self.connect_pt_child_skinned = False
        self._ref_skel = None
        self.materialsRoot = ''
        if materialsRoot:
            self.materialsRoot = materialsRoot  
        elif filepath: 
            self.materialsRoot = extend_filenames(filepath, 'meshes')
        self._shape_dict = {}
        self.node_ids = {}
        self._nodes = None
        self._shapes = None
        self._max_string_len = None
        self._load_shapes()

    def __del__(self):
        if self._handle:
            nifly.destroy(self._handle)

    def close(self):
        """Free the native nif now. Nodes and shapes point back at their file, so
        a dropped NifFile is a reference cycle: the native memory waits for a
        full garbage collection, which in a long-running process with a large
        heap may never come. Call this when done with a nif (or use the NifFile
        as a context manager). The NifFile and every node/shape taken from it
        are unusable afterwards. Idempotent."""
        if self._handle:
            nifly.destroy(self._handle)
            self._handle = None
        # Freeing the native nif isn't enough: the Python wrappers form their own
        # cycles (file <-> root node, shape <-> shader) and the shapes cache their
        # geometry as lists, several MB per head. Empty the wrappers so all of it
        # frees by refcount instead of waiting on the cycle collector.
        wrappers = list(self._shapes or []) + list((self._nodes or {}).values())
        if self._root is not None:
            wrappers.append(self._root)
        for w in wrappers:
            w.__dict__.clear()
        self._root = None
        self._shapes = None
        self._nodes = None
        self._shape_dict = {}
        self.node_ids = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def max_string_len(self):
        """Length of buffer required for the longest string stored in the nif + one for
        the trailing null byte. Return at least 128 because reasons.

        Cached after first call: the DLL scans every string to compute this, and it's
        called once per string read. Recomputing each time is O(strings²).
        """
        if self._max_string_len is not None:
            return self._max_string_len
        if self._handle:
            self._max_string_len = max(128, nifly.getMaxStringLen(self._handle)+1)
        else:
            self._max_string_len = 128
        return self._max_string_len
        
    @property
    def reference_skel(self):
        if self._ref_skel:
            return self._ref_skel

        # We don't actually know which skeleton to use. Assume the basic human skeleton.
        g = "SKYRIM" if self._game == "SKYRIMSE" else self._game
        if g:
            skel_path = os.path.join(os.path.dirname(nifly_path), "Skeletons", g, "skeleton.nif")
            if os.path.exists(skel_path):
                self._ref_skel = NifFile(skel_path)
                return self._ref_skel

        return None


    def initialize(self, target_game, filepath, root_type="NiNode", root_name='Scene Root'):
        self.filepath = filepath
        self._game = target_game
        rt = 0
        self._handle = nifly.createNif(target_game.encode('utf-8'),
                                               root_type.encode('utf-8'),
                                               root_name.encode('utf-8'))
        self.dict = gameSkeletons[target_game]
        # Get the root node into the nodes list so it can be found.
        self.read_node(0)


    def save(self):
        for sh in self.shapes:
            sh._setShapeXform()

        if self._skin_handle:
            nifly.saveSkinnedNif(self._skin_handle, self.filepath.encode('utf-8'))
        else:
            nifly.saveNif(self._handle, self.filepath.encode('utf-8'))


    def get_string(self, string_id):
        buflen = self.max_string_len
        buf = (c_char * buflen)()
        check_msg(nifly.getString, self._handle, string_id, buflen, buf)
        return buf.value.decode('utf-8')


    def add_block(self, name, buf, parent=None):
        """
        Add a block defined by the given buffer to the nif file, with error-checking.
        Returns the new object created.
        """
        id = check_msg(nifly.addBlock,
            self._handle, 
            (name.encode('utf-8') if name else None), 
            byref(buf), 
            parent.id if parent else NODEID_NONE)
        if id == NODEID_NONE or id == -1:
            raise Exception(f"Could not create node {buf.bufType}/{NiObject._buftype_name(buf.bufType)}, error: {NifFile.message_log()}")
        cls = NiObject.buffer_types[buf.bufType]
        blk = cls(file=self, id=id, properties=buf, parent=parent)
        return blk


    def add_node(self, name, xform, parent=None):
        """Add NiNode object to the file."""
        phandle = None
        if parent:
            if type(parent) == str:
                phandle = nifly.findNodeByName(self._handle, parent.encode('utf-8'))
            else:
                phandle = parent._handle
        nodeh = nifly.addNode(self._handle, name.encode('utf-8'), xform, phandle)
        return NiNode(handle=nodeh, file=self, parent=parent)


    def createShapeFromData(self, shape_name, verts, tris, uvs, normals, 
                            props:NiShapeBuf=None,
                            use_type=PynBufferTypes.NiShapeBufType, 
                            parent=None):
        """ Create the shape from the data provided
            shape_name = Name of shape
            verts = [(x, y, z)...] vertex location
            tris = [(v1, v2, v3)...] triangles
            uvs = [(u, v)...] uvs, as many as there are verts
            normals = [(x, y, z)...] UVs, as many as there are verts
            props = Properties for the new shape; use defaults if omitted
            use_tyep = Block type for the new shape; only used if props omitted
            parent = Parent object or root
            """
        if props:
            shapebuf = props
        else:
            shapebuf = NiShapeBuf()
            shapebuf.bufType = use_type
        shapebuf.vertexCount = len(verts)
        shapebuf.triangleCount = len(tris)

        parenthandle = None
        if parent:
            parenthandle = parent._handle

        VERTBUFDEF = c_float * 3 * len(verts)
        vertbuf = VERTBUFDEF()
        normbuf = None
        norm_len = 0
        for i in range(0, len(verts)):
            vertbuf[i] = verts[i]
        if normals:
            normbuf = VERTBUFDEF()
            norm_len = len(normals)
            for i in range(norm_len):
                normbuf[i] = normals[i]
        
        TRIBUFDEF = c_uint16 * 3 * len(tris)
        tribuf = TRIBUFDEF()
        for i, t in enumerate(tris): tribuf[i] = t

        UVBUFDEF = c_float * 2 * len(uvs)
        uvbuf = UVBUFDEF()
        for i, u in enumerate(uvs): uvbuf[i] = (u[0], u[1])

        shape_handle = nifly.createNifShapeFromData(
            self._handle, 
            shape_name.encode('utf-8'), 
            byref(shapebuf),
            vertbuf, uvbuf, normbuf, 
            tribuf, 
            parenthandle)
        
        if self._shapes is None:
            self._shapes = []
        # Starfield renderables are BSGeometry blocks (the DLL creates one for any SF nif);
        # wrap the handle in the matching class so the caller gets the .mesh setters/save_mesh.
        shape_class = BSGeometry if self.game == 'SF' else NiShape
        sh = shape_class(handle=shape_handle, file=self, parent=parent)
        sh._name = shape_name
        sh._partitions = []
        self._shapes.append(sh)
        sh._handle = shape_handle
        self.shape_dict[sh.name] = sh

        return sh

    @property
    def rootName(self):
        """Return name of root node"""
        return self.root.name
    
    @property
    def root(self):
        """Return handle of root node."""
        if self._root is None:
            self._root = self.read_node(0)
        return self._root

    @property 
    def rootNode(self) -> NiNode:
        """Return the root node of the nif. 
        NOT TRUE: Note this causes all nodes to be loaded and nif.nodes to be filled.
        """
        return self.root
    
    @property
    def game(self):
        """Return name of the game the Nif file is for"""
        if self._game is None and self._handle is not None:
            self._game = dll_string(nifly.getGameName, self._handle, size=50)
            self.dict = gameSkeletons[self._game]
        return self._game

    def blender_name(self, nif_name):
        """Convert name in nif to name for blender"""
        return self.dict.blender_name(nif_name)

    def nif_name(self, blender_name):
        """Convert name in blender to name for nif"""
        return self.dict.nif_name(blender_name)
    
    def getAllShapeNames(self):
        buf = create_string_buffer(300)
        nifly.getAllShapeNames(self._handle, buf, 300)
        return buf.value.decode('utf-8').split('\n')

    @property
    def shape_dict(self):
        self.shapes
        return self._shape_dict

    def _load_shapes(self):
        self._shapes = []
        self._shape_dict = {}
        if self._handle:
            nfound = nifly.getShapes(self._handle, None, 0, 0)
            PTRBUF = c_void_p * nfound
            buf = PTRBUF()
            nfound = nifly.getShapes(self._handle, buf, nfound, 0)
            for i in range(nfound):
                new_shape = NiShape.New(file=self, handle=buf[i])
                if new_shape:
                    self._shapes.append(new_shape) # not handling too many shapes yet
                    self._shape_dict[new_shape.name] = new_shape
        self._shapes_loaded = True

    @property
    def shapes(self):
        return self._shapes
    
    def shape_by_root(self, rootname):
        """ Convenience routine to find a shape by the beginning part of its name """
        for s in self.shapes:
            if s.name.startswith(rootname):
                return s
        return None


    def register_node(self, n):
        if n.name: self.nodes[n.name] = n
        if n.id != NODEID_NONE: self.node_ids[n.id] = n
        if n.id == 0: self._root = n
        if isinstance(n, NiShape) and n.name:
            self._shape_dict[n.name] = n


    def unregister_name(self, n):
        if n.name: del self.nodes[n.name]
        if isinstance(n, NiShape) and n.name in self._shape_dict:
            del self._shape_dict[n.name]


    @property
    def nodes(self):
        """Dictionary of nodes in the nif, indexed by node name."""
        # Node names do not have to be unique, except in the case of skeleton bones. 
        # nodes should not be used to find all nodes; use node_ids for that.
        if self._nodes is None:
            self._nodes = {}
            nodeCount = nifly.getNodeCount(self._handle)
            PTRBUF = c_void_p * nodeCount
            buf = PTRBUF()
            nifly.getNodes(self._handle, buf)
            for h in buf:
                this_node = self.read_node(handle=h)
        return self._nodes


    def nodeByHandle(self, desired_handle):
        """ 
        Returns the node with the given handle. If not found assumes it's a node that
        doesn't appear in the nodes list and makes a NiNode for it. 
        """
        for n in self.node_ids.values():
            if n._handle == desired_handle:
                return n
        return self.read_node(handle=desired_handle)


    def get_node_xform_to_global(self, name):
        """ Get the xform-to-global either from the nif or the reference skeleton """
        if self._handle:
            buf = TransformBuf()
            buf.set_identity()
            if nifly.getNodeTransformToGlobal(self._handle, name.encode('utf-8'), buf):
                return buf
        else:
            return self.nodes[name].global_transform.copy()

        if self.reference_skel:
            nifly.getNodeTransformToGlobal(self.reference_skel._handle, 
                                                   name.encode('utf-8'), 
                                                   buf)
        return buf


    @property
    def cloth_data(self):
        """Get cloth extra data as list of (name, binary_data) tuples"""
        if self._clothdata is None:
            self._clothdata = []
            if not self._handle: 
                return self._clothdata

            # Find all cloth extra data using the direct C API
            namelen = c_int()
            valuelen = c_int()

            for i in range(0, 1000):
                exists = nifly.getClothExtraDataLen(self._handle, None, 
                                              i,
                                              byref(namelen),
                                              byref(valuelen))
                if not exists:
                    break

                name = (c_char * (namelen.value+1))()
                val = (c_char * (valuelen.value+1))()
                       
                nifly.getClothExtraData(self._handle, None,
                                 i,
                                 name, namelen.value+1,
                                 val, valuelen.value+1)
                        
                self._clothdata.append((name.value.decode('utf-8'), val.raw))
        
        return self._clothdata

    @cloth_data.setter
    def cloth_data(self, val):
        """Set cloth extra data from list of (name, binary_data) tuples"""
        self._clothdata = val
        # Write cloth extra data using the direct C API
        for s in val:
            nifly.setClothExtraData(self._handle, None, 
                                           s[0].encode('utf-8'), s[1], len(s[1])-1)


    @property
    def connect_points_parent(self):
        """Reads a nif's parent connect points as a list of ConnectPointBuf
        Name and parent name limited to 256 characters
        """
        if not self._connect_pt_par:
            self._connect_pt_par = []
            if self._handle and isinstance(self.rootNode, NiNode):
                cnt = nifly.getConnectPointParentCount(self._handle)
                if cnt:
                    bufs = (ConnectPointBuf * cnt)()
                    cnt = nifly.getConnectPointParents(self._handle, cnt, bufs)
                    self._connect_pt_par = list(bufs[0:cnt])
        return self._connect_pt_par

    @connect_points_parent.setter
    def connect_points_parent(self, value):
        bufs = (ConnectPointBuf * len(value))()
        for i, v in enumerate(value):
            bufs[i] = v
        nifly.setConnectPointsParent(self._handle, len(value), bufs)

    @property
    def connect_points_child(self):
        """Reads a nif's child connect point names as [name, name, ...].
        Sets connect_pt_child_skinned as a side effect."""
        if not self._connect_pt_child:
            self._connect_pt_child = []
            if self._handle and isinstance(self.rootNode, NiNode):
                buflen = nifly.getConnectPointChildLen(self._handle)
                if buflen:
                    buf = (c_char * buflen)()
                    v = nifly.getConnectPointChildren(self._handle, buflen, buf)
                    if v:
                        self.connect_pt_child_skinned = (v > 0)
                        self._connect_pt_child = [
                            n.decode('utf-8') for n in buf.raw.split(b'\0')[0:-1]]
        return self._connect_pt_child

    @connect_points_child.setter
    def connect_points_child(self, value):
        buf = create_string_buffer(('\0'.join(value)).encode())
        nifly.setConnectPointsChild(self._handle, self.connect_pt_child_skinned, len(buf), buf)


    @property
    def controller_managers(self):
        cm_count = nifly.findNodesByType(self._handle, self.root, 
                                                 "NiControllerManager".encode('utf-8'), 
                                                 0, None)
        cmrefs = (c_void_p * cm_count)()
        nifly.findNodesByType(self._handle, self.root, 
                                      "NiControllerManager".encode('utf-8'), 
                                      cm_count, cmrefs)
        v = []
        for i in range(0, cm_count):
            v.append(NiControllerManager(
                file=self, handle=cmrefs[i], parent=self.root))
        return v

    @staticmethod
    def clear_log():
        nifly.clearMessageLog()

    @staticmethod
    def message_log():
        msgsize = nifly.getMessageLog(None, 0)+2
        buf = create_string_buffer(msgsize)
        nifly.getMessageLog(buf, msgsize)
        return buf.value.decode('utf-8')

    def read_node(self, id=None, handle=None, properties=None, parent=None):
        """
        Return a node object for the given node ID. The node might be anything, so use the
        block name to determine what kind of object to create. 
        """
        if id is None:
            id = nifly.getBlockID(self._handle, handle)
        if id in self.node_ids:
            return self.node_ids[id]

        buf = (c_char * (self.max_string_len))()
        check_msg(nifly.getBlockname, self._handle, id, buf, self.max_string_len)
        bn = buf.value.decode('utf-8')
        if bn == "BSConnectPoint::Parents": bn = "BSConnectPointParents"
        if bn == "BSConnectPoint::Children": bn = "BSConnectPointChildren"
        if bn in NiObject.block_types:
            node = NiObject.block_types[bn](
                id=id, file=self, handle=handle, properties=properties, parent=parent)
            self.node_ids[id] = node
            try:
                if hasattr(node, 'name') and node.name and isinstance(node, NiNode): 
                    self._nodes[node.name] = node
            except Exception:
                pass
            return node
        else:
            # Starfield skin blocks are consumed internally (bone names via GetShapeBoneList,
            # per-vertex weights from the loaded .mesh) and have no Blender representation.
            if bn not in ("SkinAttach", "BSSkin::Instance", "BSSkin::BoneData"):
                log.warning(f"Unknown block type: {bn}")
            return None


    def add_shape(self, properties, parent=None, vertices=None, normals=None, transform=None):
        """ Create collision shape in the Nif file. It can be connected to a body later.
            bhkConvexVerticesShape - vertices can be vectors of 3 points. Normals must be 
                vectors of 4 elements: x, y, z (setting direction), and w (length)
        """
        if properties.bufType == PynBufferTypes.bhkConvexTransformShapeBufType:
            if transform:
                for r in range(0,4):
                    for c in range(0,4):
                        properties.transform[c][r] = transform[r][c]

        collshape_index = nifly.addBlock(
            self._handle, None, byref(properties), 
            parent.id if parent else NODEID_NONE)
        new_collshape = bhkShape.New(
            id=collshape_index, file=self, properties=properties, parent=parent)
        
        if properties.bufType == PynBufferTypes.bhkConvexVerticesShapeBufType:
            vertbuf = (VECTOR4 * len(vertices))()
            normbuf = (VECTOR4 * len(normals))()
            for i, v in enumerate(vertices):
                vertbuf[i] = (v[0], v[1], v[2], 0)
            for i, n in enumerate(normals):
                normbuf[i][0], normbuf[i][1], normbuf[i][2], normbuf[i][3] = n[:]

            nifly.setCollConvexVerts(
                self._handle, collshape_index,
                vertbuf, len(vertices), normbuf, len(normals))
        
        return new_collshape


class hkxSkeletonFile(NifFile):
    """
    Represents a hkx skeleton file. Extends and replaces NifFile's functionality to
    read a XML file instead of a nif. 
    """
    has_extra_data = False

    def __init__(self, filepath=None):
        super().__init__(filepath=None)
        self.filepath = filepath
        self._loaded = False
        self._game = "SKYRIM"
        self.dict = gameSkeletons[self._game]
        if filepath: 
            self.load_from_file()


    @property
    def name(self):
        if self.filepath:
            return Path(self.filepath).stem
        else:
            return "None"
        

    def load_from_file(self):
        """
        Load the skeleton from a HKX or XML file. Since the XML spreads bone information
        across multiple constructs it's more convenient to load it all at once.
        """
        if self._loaded:
            # Prevent recursive call from NiNode().
            return
        self._loaded = True

        if os.path.splitext(self.filepath)[1].upper() == ".HKX":
            bonelist, parentIndices, poses = self._read_hkx()
        else:
            bonelist, parentIndices, poses = self._read_xml()

        for j, (name, pose) in enumerate(zip(bonelist, poses)):
            if pose is None:
                continue
            loc, quat, scale = pose
            parent = None
            if parentIndices[j] >= 0:
                parentname = bonelist[parentIndices[j]]
                if parentname in self.nodes:
                    parent = self.nodes[parentname]

            # Note this quaternion may not be normalized. Stored x, y, z, w.
            rot = PM.quaternion_to_matrix([quat[3], quat[0], quat[1], quat[2]])
            buf = NiNodeBuf()
            buf.transform.translation = VECTOR3(*loc)
            buf.transform.rotation = MATRIX3(VECTOR3(*rot[0]), VECTOR3(*rot[1]), VECTOR3(*rot[2]))
            buf.transform.scale = scale[0]
            n = NiNode(file=self, parent=parent, properties=buf, name=name)
            # The skeleton's own root bone (bone 0, no parent) is the file
            # root: giving it id 0 makes register_node record it as _root.
            n.id = j
            n._blockname = "NiNode"
            self.register_node(n)


    def _read_hkx(self):
        """Bones, parent indices and reference poses from a binary HKX skeleton, read
        natively. The readers live in the Blender-side hkx package, whose __init__ needs
        bpy; outside Blender, import them straight from its folder."""
        try:
            from ...hkx import anim_fo4, anim_skyrim
        except ImportError:
            import sys
            hkx_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   'hkx')
            if hkx_dir not in sys.path:
                sys.path.append(hkx_dir)
            import anim_fo4
            import anim_skyrim

        if anim_fo4.is_fo4_hkx(self.filepath):
            skel = anim_fo4.load_fo4_skeleton(self.filepath)
            self._game = "FO4"
            self.dict = gameSkeletons[self._game]
        else:
            skel = anim_skyrim.load_skyrim_skeleton(self.filepath)
        if skel is None:
            raise ValueError(f"No skeleton in {self.filepath}")
        poses = [(p.translation, p.rotation, p.scale) for p in skel.reference_pose]
        return skel.bones, skel.parents, poses


    def _read_xml(self):
        """Bones, parent indices and reference poses from an hkpackfile XML skeleton. A pose
        that can't be read is None, and that bone is skipped."""
        root = xml.parse(self.filepath).getroot()
        skel = root.find(".//*[@class='hkaSkeleton']")
        parentIndices = [int(x) for x in skel.find("./*[@name='parentIndices']").text.split()]

        bonelist = []
        skelbones = skel.find("./*[@name='bones']")
        for b in skelbones.iter('hkobject'):
            bonelist.append(b.find("./*[@name='name']").text)

        pose = skel.find("./*[@name='referencePose']")
        poselist = pose.text.strip(' ()\t\n').split(')')

        def floats(text, n):
            vals = text.strip(' ()\t\n').split()
            return [float(x) for x in vals] if len(vals) == n else None

        poses = []
        for j in range(len(bonelist)):
            i = 3 * j
            if i + 2 >= len(poselist):
                poses.append(None)
                continue
            loc, quat, scale = (floats(poselist[i], 3), floats(poselist[i+1], 4),
                                floats(poselist[i+2], 3))
            if not (loc and quat and scale):
                self.warn(f"Pose list is not translation, rotation, scale at index {j}: "
                          f"{poselist[i:i+3]}")
                poses.append(None)
            else:
                poses.append((loc, quat, scale))
        return bonelist, parentIndices, poses

        
    @property
    def nodes(self):
        """Overwrites "nodes" property to get them from the XML file, not a nif file."""
        if self._nodes is None:
            self._nodes = {}
            self.load_from_file()
        return self._nodes


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .base import (NiObject, check_msg, dll_string)  # noqa: E402
from .collision import (bhkShape)  # noqa: E402
from .nodes import (NiNode)  # noqa: E402
from .anim import (NiControllerManager)  # noqa: E402
from .shapes import (BSGeometry, NiShape)  # noqa: E402
