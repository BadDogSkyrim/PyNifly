"""NiNode and its subclasses, and the multibound blocks they carry."""

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
from .base import NiAVObject, NiObject


log = logging.getLogger("pynifly")


class NiNode(NiAVObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None, 
                 properties=None, name=""):
        super().__init__(handle=handle, file=file, id=id, parent=parent, 
                         properties=properties, name=name)
        
    buffer_type = PynBufferTypes.NiNodeBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiNodeBuf(values)
    
    @property
    def blender_name(self):
        return self.file.dict.blender_name(self.name)

    @property
    def nif_name(self):
        return self.file.dict.nif_name(self.name)
    
    @property
    def transform(self):
        return self.properties.transform
    
    @transform.setter
    def transform(self, value):
        self.properties.transform = value

    @property
    def flags(self):
        return self.properties.flags

    @flags.setter
    def flags(self, value):
        self.properties.flags = value
        nifly.setNodeFlags(self._handle, value)

    @property
    def parent(self):
        if self._parent is None and self.file._handle is not None:
            parent_handle = nifly.getNodeParent(self.file._handle, self._handle)
            parent_id = nifly.getBlockID(self.file._handle, parent_handle)
            if parent_id != -1 and parent_id != NODEID_NONE:
                self._parent = self.file.read_node(id=parent_id)
        return self._parent

    @property
    def global_transform(self):
        if self.file._handle:
            buf = TransformBuf()
            nifly.getNodeTransformToGlobal(self.file._handle, self.name.encode('utf-8'), buf)
            return buf
        
        if not self.parent:
            return self.transform
        
        return self.parent.global_transform * self.transform
    
    
    @property
    def collision_object(self):
        if self.properties.collisionID != NODEID_NONE:
            return NiCollisionObject.New(id=self.properties.collisionID, file=self.file, parent=self)
        else:
            return None


    def _extra_data_id(self, blockname=None, name=None, target_index=0):
        """The nif block ID of the target extra data, or NODEID_NONE if the node has no
        extra data at that index. Distinguishes "no such block" from "block we can't read"."""
        if not self.file._handle: return NODEID_NONE

        return nifly.getExtraData(self.file._handle, self.id,
                                  blockname.encode('utf-8') if blockname else None,
                                  name.encode('utf-8') if name else None,
                                  target_index)


    def get_extra_data(self, blockname=None, name=None, target_index=0):
        """
        Search for the target extra data.
        blockname = the type of extra data to find. May be omitted.
        name = the name of the extra data to find. May be omitted.
        target_index = The index of the extra data, starting from 0.
        """
        ex_id = self._extra_data_id(blockname, name, target_index)
        if ex_id == NODEID_NONE:
            return None
        return self.file.read_node(id=ex_id, parent=self)


    def extra_data(self, blockname=None, name=None):
        """Convenience routine to walk all extra data on a node.

        A block whose TYPE PyNifly has no class for reads back as None -- read_node logs
        "Unknown block type". Skip it and keep walking: stopping there hides every block
        behind it. The Starfield head hits exactly that, with the unimplemented
        NiIntegersExtraData sitting ahead of the NiIntegerExtraData carrying MaterialID.
        """
        i = 0
        while True:
            ex_id = self._extra_data_id(blockname, name, i)
            if ex_id == NODEID_NONE:
                break
            ed = self.file.read_node(id=ex_id, parent=self)
            if ed:
                yield ed
            i += 1


class BSFaceGenNiNode(NiNode):
    pass


class BSFadeNode(NiNode):
    pass


class BSLeafAnimNode(NiNode):
    pass


class BSMasterParticleSystem(NiNode):
    pass


class BSMultiBoundNode(NiNode):
    buffer_type = PynBufferTypes.BSMultiBoundNodeBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSMultiBoundNodeBuf(values)

    @property
    def culling_mode(self):
        """BSCPCullingType (0=normal, 1=allpass, 2=allfail, 3=ignore, 4=force)."""
        return self.properties.cullingMode

    @culling_mode.setter
    def culling_mode(self, value):
        self.properties.cullingMode = value

    @property
    def multibound(self):
        """The BSMultiBound block referenced by this node, or None."""
        mbid = self.properties.multiBoundID
        if mbid == NODEID_NONE:
            return None
        return self.file.read_node(id=mbid)


class BSMultiBound(NiObject):
    buffer_type = PynBufferTypes.BSMultiBoundBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSMultiBoundBuf(values)

    @property
    def data(self):
        """The BSMultiBoundData (e.g. BSMultiBoundOBB) block, or None."""
        did = self.properties.dataID
        if did == NODEID_NONE:
            return None
        return self.file.read_node(id=did)


class BSMultiBoundOBB(NiObject):
    buffer_type = PynBufferTypes.BSMultiBoundOBBBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSMultiBoundOBBBuf(values)

    @property
    def center(self):
        return self.properties.center

    @property
    def size(self):
        return self.properties.size

    @property
    def rotation(self):
        return self.properties.rotation


class BSOrderedNode(NiNode):
    pass


class BSRangeNode(NiNode):
    pass


class BSTreeNode(NiNode):
    """Root node of a skinned tree. Carries Bones1/Bones2 node-pointer arrays
    (Bones1 is typically the armature root; Bones2 the remaining bones)."""

    def _get_bone_names(self, which):
        n = nifly.getBSTreeNodeBones(self.file._handle, self.id, which, None, 0)
        if n <= 0:
            return []
        buf = (c_uint32 * n)()
        nifly.getBSTreeNodeBones(self.file._handle, self.id, which, buf, n)
        names = []
        for bid in buf:
            node = self.file.read_node(id=bid)
            if node and node.name:
                names.append(node.name)
        return names

    @property
    def bones1(self):
        return self._get_bone_names(1)

    @property
    def bones2(self):
        return self._get_bone_names(2)

    def set_bone_ids(self, which, node_ids):
        """Set Bones1 (which=1) or Bones2 (which=2) to the given node ids."""
        arr = (c_uint32 * len(node_ids))(*node_ids)
        nifly.setBSTreeNodeBones(self.file._handle, self.id, which, arr, len(node_ids))


class BSValueNode(NiNode):
    buffer_type = PynBufferTypes.BSValueNodeBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSValueNodeBuf(values)


class BSWeakReferenceNode(NiNode):
    pass


class NiBillboardNode(NiNode):
    pass


class NiBone(NiNode):
    pass


class NiLODNode(NiNode):
    pass


class NiSortAdjustNode(NiNode):
    pass


class NiSwitchNode(NiNode):
    buffer_type = PynBufferTypes.NiSwitchNodeBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiSwitchNodeBuf(values)

    @property
    def switch_flags(self):
        """NiSwitchFlags: 0=UPDATE_ONLY_ACTIVE_CHILD, 1=UPDATE_CONTROLLERS."""
        return self.properties.switchFlags

    @switch_flags.setter
    def switch_flags(self, value):
        self.properties.switchFlags = value

    @property
    def active_index(self):
        """Index of the active child."""
        return self.properties.switchActiveIndex

    @active_index.setter
    def active_index(self, value):
        self.properties.switchActiveIndex = value


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .collision import (NiCollisionObject)  # noqa: E402
