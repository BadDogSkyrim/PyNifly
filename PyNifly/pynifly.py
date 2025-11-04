"""
Wrapper around nifly to provide python-friendly access to nifs

Check the first test to see basic functionality exercised.
"""

import os
import struct
from enum import Enum, IntFlag, IntEnum
from math import asin, atan2, pi, sin, cos
import re
import logging
from ctypes import *
from typing import ValuesView # c_void_p, c_int, c_bool, c_char_p, c_wchar_p, c_float, c_uint8, c_uint16, c_uint32, create_string_buffer, Structure, cdll, pointer, addressof
import xml.etree.ElementTree as xml
from niflytools import *
from nifdefs import *
import xmltools

nifly = None

def load_nifly(nifly_path):
    nifly = cdll.LoadLibrary(nifly_path)
    nifly.addAnimKeyLinearTrans.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyLinearTransBuf)]
    nifly.addAnimKeyLinearTrans.restype = None
    nifly.addAnimKeyLinearQuat.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyLinearQuatBuf)]
    nifly.addAnimKeyLinearQuat.restype = None
    nifly.addAnimKeyLinear.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyLinearBuf)]
    nifly.addAnimKeyLinear.restype = None
    nifly.addAnimKeyQuadFloat.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyFloatBuf)]
    nifly.addAnimKeyQuadFloat.restype = None
    nifly.addAnimKeyQuadTrans.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyQuadTransBuf)]
    nifly.addAnimKeyQuadTrans.restype = None
    nifly.addAnimKeyQuadXYZ.argtypes = [c_void_p, c_int, c_char, POINTER(NiAnimKeyFloatBuf)]
    nifly.addAnimKeyQuadXYZ.restype = None
    nifly.addAVObjectPaletteObject.argtypes = [c_void_p, c_uint32, c_char_p, c_uint32]
    nifly.addAVObjectPaletteObject.restype = c_int
    nifly.addBoneToNifShape.argtypes = [c_void_p, c_void_p, c_char_p, POINTER(TransformBuf), c_char_p]
    nifly.addBoneToNifShape.restype = c_void_p
    nifly.addBlock.argtypes = [c_void_p, c_char_p, c_void_p, c_int]
    nifly.addBlock.restype = c_int
    nifly.addCollListChild.argtypes = [c_void_p, c_uint32, c_uint32]
    nifly.addCollListChild.restype = None
    nifly.addNode.argtypes = [c_void_p, c_char_p, POINTER(TransformBuf), c_void_p]
    nifly.addNode.restype = c_void_p
    nifly.addString.argtypes = [c_void_p, c_char_p]
    nifly.addString.restype = c_int
    nifly.addTextKey.argtypes = [c_void_p, c_uint32, c_float, c_char_p]
    nifly.addTextKey.restype = c_int
    nifly.calcShapeGlobalToSkin.argtypes = [c_void_p, c_void_p, POINTER(TransformBuf)]
    nifly.calcShapeGlobalToSkin.restype = None
    nifly.clearMessageLog.argtypes = []
    nifly.clearMessageLog.restype = None
    nifly.createNif.argtypes = [c_char_p, c_char_p, c_char_p]
    nifly.createNif.restype = c_void_p
    nifly.createNifShapeFromData.argtypes = [
        c_void_p, # nif
        c_char_p, # name
        c_void_p, # buffer
        c_void_p, # verts
        c_void_p, # UV
        c_void_p, # normals
        c_void_p, # tris
        c_void_p # parent
        ]
    nifly.createNifShapeFromData.restype = c_void_p
    nifly.destroy.argtypes = [c_void_p]
    nifly.destroy.restype = None
    nifly.findNodeByName.argtypes = [c_void_p, c_char_p]
    nifly.findNodeByName.restype = c_void_p
    nifly.findNodesByType.argtypes = [c_void_p, c_void_p, c_char_p, c_int, c_void_p]
    nifly.findNodesByType.restype = c_int
    nifly.getAllShapeNames.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getAllShapeNames.restype = c_int
    nifly.getAnimKeyLinearQuat.argtypes = [c_void_p, c_int, c_int, POINTER(NiAnimKeyLinearQuatBuf)]
    nifly.getAnimKeyLinearQuat.restype = None
    nifly.getAnimKeyLinearTrans.argtypes = [c_void_p, c_int, c_int, POINTER(NiAnimKeyLinearTransBuf)]
    nifly.getAnimKeyLinearTrans.restype = None
    nifly.getAnimKeyLinearXYZ.argtypes = [c_void_p, c_int, c_char, c_int, POINTER(NiAnimKeyLinearBuf)]
    nifly.getAnimKeyLinearXYZ.restype = None
    nifly.getAnimKeyLinear.argtypes = [c_void_p, c_int, c_int, POINTER(NiAnimKeyLinearBuf)]
    nifly.getAnimKeyLinear.restype = c_int
    nifly.getAnimKeyQuadFloat.argtypes = [c_void_p, c_int, c_int, POINTER(NiAnimKeyFloatBuf)]
    nifly.getAnimKeyQuadFloat.restype = c_int
    nifly.getAnimKeyQuadTrans.argtypes = [c_void_p, c_int, c_int, POINTER(NiAnimKeyQuadTransBuf)]
    nifly.getAnimKeyQuadTrans.restype = None
    nifly.getAnimKeyQuadXYZ.argtypes = [c_void_p, c_int, c_char, c_int, POINTER(NiAnimKeyFloatBuf)]
    nifly.getAnimKeyQuadXYZ.restype = None
    nifly.getAVObjectPaletteObject.argtypes = [c_void_p, c_uint32, c_int, c_int, c_char_p, POINTER(c_uint32)]
    nifly.getAVObjectPaletteObject.restype = c_int
    nifly.getBGExtraData.argtypes = [c_void_p, c_void_p, c_int, c_char_p, c_int, c_char_p, c_int, c_void_p]
    nifly.getBGExtraData.restype = c_int
    nifly.getBGExtraDataLen.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_void_p]
    nifly.getBGExtraDataLen.restype = c_int
    nifly.getBlock.argtypes = [c_void_p, c_int, c_void_p]
    nifly.getBlock.restype = c_int
    nifly.getBlockID.argtypes = [c_void_p, c_void_p]
    nifly.getBlockID.restype = c_int
    nifly.getBlockname.argtypes = [c_void_p, c_int, c_char_p, c_int]
    nifly.getBlockname.restype = c_int
    nifly.getClothExtraData.argtypes = [c_void_p, c_void_p, c_int, c_char_p, c_int, c_char_p, c_int]
    nifly.getClothExtraData.restype = c_int
    nifly.getClothExtraDataLen.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_void_p]
    nifly.getClothExtraDataLen.restype = c_int
    nifly.getCollListShapeChildren.argtypes = [c_void_p, c_int, c_void_p, c_int]
    nifly.getCollListShapeChildren.restype = c_int
    nifly.getCollShapeNormals.argtypes = [c_void_p, c_int, c_void_p, c_int]
    nifly.getCollShapeNormals.restype = c_int
    nifly.getCollShapeVerts.argtypes = [c_void_p, c_int, c_void_p, c_int]
    nifly.getCollShapeVerts.restype = c_int
    nifly.getCollTarget.argtypes = [c_void_p, c_void_p]
    nifly.getCollTarget.restype = c_void_p
    nifly.getColorsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getColorsForShape.restype = c_int
    nifly.getConnectPointChild.argtypes = [c_void_p, c_int, c_char_p]
    nifly.getConnectPointChild.restype = c_int
    nifly.getConnectPointParent.argtypes = [c_void_p, c_int, POINTER(ConnectPointBuf)]
    nifly.getConnectPointParent.restype = c_int
    nifly.getControllerManagerSequences.argtypes = [c_void_p, c_void_p, c_int, POINTER(c_uint32)]
    nifly.getControllerManagerSequences.restype = c_int
    nifly.getExtraData.argtypes = [c_void_p, c_int, c_char_p]
    nifly.getExtraData.restype = c_uint32
    nifly.getFurnMarker.argtypes = [c_void_p, c_int, POINTER(FurnitureMarkerBuf)]
    nifly.getFurnMarker.restype = c_int
    nifly.getGameName.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getGameName.restype = c_int
    nifly.getMaxStringLen.argtypes = [c_void_p]
    nifly.getMaxStringLen.restype = c_int
    nifly.getMessageLog.argtypes = [c_char_p, c_int]
    nifly.getMessageLog.restype = c_int
    nifly.getNiTextKey.argtypes = [c_void_p, c_uint32, c_int, POINTER(TextKeyBuf)]
    nifly.getNiTextKey.restype = c_int
    nifly.getNode.argtypes = [c_void_p, POINTER(NiNodeBuf)]
    nifly.getNode.restype = None
    nifly.getNodeBlockname.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getNodeBlockname.restype = c_int
    nifly.getNodeByID.argtypes = [c_void_p, c_int]
    nifly.getNodeByID.restype = c_void_p
    nifly.getNodeCount.argtypes = [c_void_p]
    nifly.getNodeCount.restype = c_int
    nifly.getNodeName.argtypes = [c_void_p, c_void_p, c_int]
    nifly.getNodeName.restype = c_int
    nifly.getNodeParent.argtypes = [c_void_p, c_void_p]
    nifly.getNodeParent.restype = c_void_p
    nifly.getNodes.argtypes = [c_void_p, c_void_p]
    nifly.getNodes.restype = None
    nifly.getNodeTransformToGlobal.argtypes = [c_void_p, c_char_p, POINTER(TransformBuf)]
    nifly.getNodeTransformToGlobal.restype = c_int
    nifly.getNormalsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getNormalsForShape.restype = c_int
    nifly.getPartitions.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getPartitions.restype = c_int
    nifly.getPartitionTris.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getPartitionTris.restype = c_int
    nifly.getRagdollEntities.argtypes = [c_void_p, c_int, c_void_p, c_int]
    nifly.getRagdollEntities.restype = c_int
    nifly.getRigidBodyConstraints.argtypes = [c_void_p, c_int, c_void_p, c_int]
    nifly.getRigidBodyConstraints.restype = c_int
    nifly.getRoot.argtypes = [c_void_p]
    nifly.getRoot.restype = c_void_p
    nifly.getRootName.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getRootName.restype = c_int
    nifly.getSegmentFile.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getSegmentFile.restype = c_int
    nifly.getSegments.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getSegments.restype = c_int
    nifly.getShaderTextureSlot.argtypes = [c_void_p, c_void_p, c_int, c_char_p, c_int]
    nifly.getShaderTextureSlot.restype = c_int
    nifly.getShapeBlockName.argtypes = [c_void_p, c_void_p, c_int]
    nifly.getShapeBlockName.restypes = c_int
    nifly.getShapeBoneCount.argtypes = [c_void_p, c_void_p]
    nifly.getShapeBoneCount.restype = c_int
    nifly.getShapeBoneIDs.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getShapeBoneIDs.restype = c_int
    nifly.getShapeBoneNames.argtypes = [c_void_p, c_void_p, c_char_p, c_int]
    nifly.getShapeBoneNames.restype = c_int
    nifly.getShapeBoneWeights.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_int]
    nifly.getShapeBoneWeights.restype = c_int
    nifly.getShapeBoneWeightsCount.argtypes = [c_void_p, c_void_p, c_int]
    nifly.getShapeBoneWeightsCount.restype = c_int
    nifly.getShapeGlobalToSkin.argtypes = [c_void_p, c_void_p, POINTER(TransformBuf)]
    nifly.getShapeGlobalToSkin.restype = c_bool
    nifly.getShapeName.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getShapeName.restype = c_int
    nifly.getShapes.argtypes = [c_void_p, c_void_p, c_int, c_int]
    nifly.getShapes.restype = c_int
    nifly.getShapeSkinToBone.argtypes = [c_void_p, c_void_p, c_char_p, POINTER(TransformBuf)]
    nifly.getShapeSkinToBone.restype = c_bool
    nifly.getString.argtypes = [c_void_p, c_int, c_int, c_char_p]
    nifly.getString.restype = None
    nifly.getStringExtraData.argtypes = [c_void_p, c_void_p, c_int, c_char_p, c_int, c_char_p, c_int]
    nifly.getStringExtraData.restype = c_int
    nifly.getStringExtraDataLen.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_void_p]
    nifly.getStringExtraDataLen.restype = c_int
    nifly.getSubsegments.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_int]
    nifly.getSubsegments.restype = c_int
    nifly.getTriangles.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getTriangles.restype = c_int
    nifly.getUVs.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getUVs.restype = c_int
    nifly.getVertsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getVertsForShape.restype = c_int
    nifly.hasSkinInstance.argtypes = [c_void_p]
    nifly.hasSkinInstance.restype = c_int
    nifly.load.argtypes = [c_char_p]
    nifly.load.restype = c_void_p
    nifly.saveNif.argtypes = [c_void_p, c_char_p]
    nifly.saveNif.restype = c_int
    nifly.segmentCount.argtypes = [c_void_p, c_void_p]
    nifly.segmentCount.restype = c_int
    nifly.setBGExtraData.argtypes = [c_void_p, c_void_p, c_char_p, c_char_p, c_int]
    nifly.setBGExtraData.restype = None
    nifly.setBlock.argtypes = [c_void_p, c_int, c_void_p] 
    nifly.setBlock.restype = None
    nifly.setClothExtraData.argtypes = [c_void_p, c_void_p, c_char_p, c_char_p, c_int]
    nifly.setClothExtraData.restype = None
    nifly.setCollConvexTransformShapeChild.argtypes = [c_void_p, c_uint32, c_uint32]
    nifly.setCollConvexTransformShapeChild.restype = None
    nifly.setCollConvexVerts.argtypes = [c_void_p, c_int, c_void_p, c_int, c_void_p, c_int]
    nifly.setCollConvexVerts.restype = c_int
    nifly.setColorsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.setColorsForShape.restype = None
    nifly.setConnectPointsChild.argtypes = [c_void_p, c_int, c_int, c_char_p]
    nifly.setConnectPointsChild.restype = None
    nifly.setConnectPointsParent.argtypes = [c_void_p, c_int, POINTER(ConnectPointBuf)]
    nifly.setConnectPointsParent.restype = None
    nifly.setController.argtypes = [c_void_p, c_int, c_int]
    nifly.setController.restype = c_int
    nifly.setFurnMarkers.argtypes = [c_void_p, c_int, POINTER(FurnitureMarkerBuf)]
    nifly.setFurnMarkers.restype = None
    nifly.setNodeFlags.argtypes = [c_void_p, c_int]
    nifly.setNodeFlags.restype = None
    nifly.setPartitions.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_void_p, c_int]
    nifly.setPartitions.restype = None
    nifly.setSegments.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_void_p, c_int, c_void_p, c_int, c_char_p]
    nifly.setSegments.restype = None
    nifly.setShaderTextureSlot.argtypes = [c_void_p, c_void_p, c_int, c_char_p]
    nifly.setShapeBoneIDList.argtypes = [c_void_p, c_void_p, c_void_p, c_int]  
    nifly.setShapeBoneWeights.argtypes = [c_void_p, c_void_p, c_char_p, POINTER(VERTEX_WEIGHT_PAIR), c_int]
    nifly.setShapeBoneWeights.restype = None
    nifly.setShapeGlobalToSkin.argtypes = [c_void_p, c_void_p, POINTER(TransformBuf)]
    nifly.setShapeGlobalToSkin.restype = None
    nifly.setShapeSkinToBone.argtypes = [c_void_p, c_void_p, c_char_p, POINTER(TransformBuf)]
    nifly.setShapeSkinToBone.restype = None
    nifly.setStringExtraData.argtypes = [c_void_p, c_void_p, c_char_p, c_char_p]
    nifly.setStringExtraData.restype = None
    nifly.setTransform.argtypes = [c_void_p, POINTER(TransformBuf)]
    nifly.setTransform.restype = None
    nifly.skinShape.argtypes = [c_void_p, c_void_p]
    nifly.skinShape.restype = None

    pynStructure.nifly = nifly
    pynStructure.logger = logging.getLogger("pynifly")

    return nifly


# --- Helper Routines --- #

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
    skymatch = re.compile('SBP_([0-9]+)_\w+')

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
    fo4segmatch = re.compile('FO4\w+ \#*([0-9]+)\Z')
    fo4segmatch1 = re.compile('FO4 Seg +([0-9]+)\Z')

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
            return f"FO4 Seg " + '{:0>3d}'.format(self.index)

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
    fo4subsegm = re.compile('\AFO4 *.*')
    fo4bpm = re.compile('\AFO4 *(\d+) - ')

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
            except:
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

class ExtraDataType(Enum):
    BehaviorGraph = 1
    String = 2
    Cloth = 3
    InvMarker = 4
    BSXFlags = 5

def _read_extra_data(nifHandle, shapeHandle, edtype):
    ed = []
    if not nifHandle: return ed

    namelen = c_int()
    valuelen = c_int()

    if edtype == ExtraDataType.BehaviorGraph:
        len_func = NifFile.nifly.getBGExtraDataLen
        get_func = NifFile.nifly.getBGExtraData
    elif edtype == ExtraDataType.String:
        len_func = NifFile.nifly.getStringExtraDataLen
        get_func = NifFile.nifly.getStringExtraData
    elif edtype == ExtraDataType.Cloth:
        len_func = NifFile.nifly.getClothExtraDataLen
        get_func = NifFile.nifly.getClothExtraData

    for i in range(0, 1000):
        exists = len_func(nifHandle, shapeHandle, 
                          i,
                          byref(namelen),
                          byref(valuelen))
        if not exists:
            break

        name = (c_char * (namelen.value+1))()
        val = (c_char * (valuelen.value+1))()
               
        if edtype == ExtraDataType.BehaviorGraph:
            controlsBaseSkel = c_uint16()
            get_func(nifHandle, shapeHandle,
                     i,
                     name, namelen.value+1,
                     val, valuelen.value+1,
                     byref(controlsBaseSkel))
        else:
            get_func(nifHandle, shapeHandle,
                     i,
                     name, namelen.value+1,
                     val, valuelen.value+1)
                
        if edtype == ExtraDataType.Cloth:
            ed.append((name.value.decode('utf-8'), val.raw))
        elif edtype == ExtraDataType.BehaviorGraph:
            ed.append((name.value.decode('utf-8'), val.value.decode('utf-8'), (controlsBaseSkel.value != 0)))
        else:
            ed.append((name.value.decode('utf-8'), val.value.decode('utf-8')))
    
    return ed

def _write_extra_data(nifhandle, shapehandle, edtype, val):
    if edtype == ExtraDataType.Cloth:
        set_func = NifFile.nifly.setClothExtraData
    elif edtype == ExtraDataType.BehaviorGraph:
        set_func = NifFile.nifly.setBGExtraData
    else:
        set_func = NifFile.nifly.setStringExtraData

    for s in val:
        if edtype == ExtraDataType.Cloth:
            set_func(nifhandle, shapehandle, s[0].encode('utf-8'), s[1], len(s[1])-1)
        elif edtype == ExtraDataType.BehaviorGraph:
            set_func(nifhandle, shapehandle, s[0].encode('utf-8'), s[1].encode('utf-8'), s[2])
        else:
            set_func(nifhandle, shapehandle, s[0].encode('utf-8'), s[1].encode('utf-8'))


# --- NiObject -- #
class NiObject:
    """ Represents any block in a nif file. """
    
    # These are the types of blocks we can create from an ID. Eventaully should probably
    # be all of them. This could be done with reflection but we're keeping things simple.
    block_types = {}
    buffer_types = [None] * PynBufferTypes.COUNT

    # Buffer used to pass properties across the DLL layer. Overridden by subtypes.
    buffer_type = -1
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        self._handle = handle
        self._controller = None
        self.file:NifFile = file
        self.id = id
        if handle is None and id != NODEID_NONE and file is not None:
            self._handle = NifFile.nifly.getNodeByID(file._handle, id)
        if self.id == NODEID_NONE and handle is not None and file is not None:
            self.id = NifFile.nifly.getBlockID(self.file._handle, self._handle)
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
                buf = create_string_buffer(128)
                NifFile.nifly.getBlockname(self.file._handle, self.id, buf, 128)
                self._blockname = buf.value.decode('utf-8')
        return self._blockname
    
    @property
    def properties(self):
        if not self._properties:
            self._properties = self.getbuf()
            if self.id != NODEID_NONE and self.file._handle:
                NifFile.clear_log()
                err = NifFile.nifly.getBlock(
                    self.file._handle, 
                    self.id, 
                    byref(self._properties))
                if err != 0:
                    raise Exception(NifFile.message_log())
        return self._properties
    
    @properties.setter
    def properties(self, value):
        self._properties = value.copy()
        NifFile.nifly.setBlock(self.file._handle, self.id, byref(self._properties))

    def register_subclasses():
        """Register all subclasses for easy finding."""
        subclasses = list(NiObject.__subclasses__())
        while subclasses:
            sc = subclasses.pop(0)
            NiObject.block_types[sc.__name__] = sc
            NiObject.buffer_types[sc.buffer_type] = sc
            subclasses = subclasses + sc.__subclasses__()

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
        NifFile.nifly.setController(self.file._handle, self.id, c.id)
    
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
            NifFile.nifly.getNodeName(self._handle, buf, buflen)
            self._name = buf.value.decode('utf-8')

        if self._name:
            self.file.nodes[self._name] = self

    @property
    def name(self):
        if self._name == None:
            namebuf = (c_char * self.file.max_string_len)()
            NifFile.nifly.getString(
                self.file._handle, self._properties.nameID, self.file.max_string_len, namebuf)
            self._name = namebuf.value.decode('utf-8')
        return self._name
    
    @name.setter
    def name(self, value):
        self._name = value
        if self.file: self.file.register_node(self)
        
    @property
    def behavior_graph_data(self):
        if self._bgdata is None:
            self._bgdata = _read_extra_data(self.file._handle, self._handle,
                                           ExtraDataType.BehaviorGraph)
        return self._bgdata

    @behavior_graph_data.setter
    def behavior_graph_data(self, val):
        self._bgdata = val
        _write_extra_data(self.file._handle, self._handle, 
                         ExtraDataType.BehaviorGraph, self._bgdata)

    @property
    def string_data(self):
        if self._strdata is None:
            self._strdata = _read_extra_data(self.file._handle, self._handle,
                                           ExtraDataType.String)
        return self._strdata

    @string_data.setter
    def string_data(self, val):
        self._strdata = val
        _write_extra_data(self.file._handle, self._handle, 
                         ExtraDataType.String, self._strdata)

    @property
    def cloth_data(self):
        if self._clothdata is None:
            self._clothdata = _read_extra_data(self.file._handle, 
                                               self._handle,
                                               ExtraDataType.Cloth)
        return self._clothdata

    @cloth_data.setter
    def cloth_data(self, val):
        self._clothdata = val
        _write_extra_data(self.file._handle, self._handle, 
                         ExtraDataType.Cloth, self._clothdata)


class NiProperty(NiObjectNET):
    pass


# --- Collisions --- #

class bhkShape(NiObject):
    @classmethod
    def New(cls, collisiontype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        if properties:
            collisiontype = cls.buffer_types[properties.bufType].__name__
        elif not collisiontype:
            buf = create_string_buffer(128)
            NifFile.nifly.getBlockname(file._handle, id, buf, 128)
            collisiontype = buf.value.decode('utf-8')
        try:
            if id == NODEID_NONE:
                id = NifFile.nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            return file.read_node(
                id=id, parent=parent, properties=properties)
        except:
            return None


class bhkBoxShape(bhkShape):
    buffer_type = PynBufferTypes.bhkBoxShapeBufType
    needsTransform = True
    buffer_type = PynBufferTypes.bhkBoxShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkBoxShapeProps(values)


class bhkCapsuleShape(bhkShape):
    buffer_type = PynBufferTypes.bhkCapsuleShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkCapsuleShapeProps(values)


class bhkSphereShape(bhkShape):
    buffer_type = PynBufferTypes.bhkSphereShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkSphereShapeBuf(values)


class bhkConvexVerticesShape(bhkShape):
    buffer_type = PynBufferTypes.bhkConvexVerticesShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkConvexVerticesShapeProps(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        super().__init__(handle=handle, id=id, file=file, parent=parent, 
                         properties=properties)
        self._vertices = None
        self._normals = None

    @property
    def vertices(self):
        if not self._vertices:
            verts = (VECTOR4 * self.properties.vertsCount)()
            NifFile.nifly.getCollShapeVerts(self.file._handle, 
                                            self.id, 
                                            verts, self.properties.vertsCount)
            self._vertices = [tuple(v) for v in verts]
        return self._vertices

    @property
    def normals(self):
        if not self._normals:
            norms = (VECTOR4 * self.properties.normalsCount)()
            NifFile.nifly.getCollShapeNormals(self.file._handle, 
                                              self.id, 
                                              norms, self.properties.normalsCount)
            self._normals = [tuple(v) for v in norms]
        return self._normals


class bhkListShape(bhkShape):
    buffer_type = PynBufferTypes.bhkListShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkListShapeProps(values)

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._children = None

    @property
    def children(self):
        if not self._children:
            if self.properties.childCount == 0:
                self._children = []
            else:
                buf = (c_uint32 * self.properties.childCount)()
                NifFile.nifly.getCollListShapeChildren(self.file._handle,
                                                       self.id,
                                                       buf, self.properties.childCount)
                self._children = []
                for idx in buf:
                    self._children.append(bhkShape.New(
                        id=idx, file=self.file, parent=self))
        
        return self._children

    def add_child(self, childnode):
        NifFile.nifly.addCollListChild(
            self.file._handle, self.id, childnode.id)

    def add_shape(self, childprops, transform=None):
        child = bhkShape.New(file=self.file, properties=childprops, parent=self)
        if not self._children:
            self._children = []
        self._children.append(child)
        return child


class bhkConvexTransformShape(bhkShape):
    buffer_type = PynBufferTypes.bhkConvexTransformShapeBufType
    needsTransform = False
    
    @classmethod
    def getbuf(cls, values=None):
        return bhkConvexTransformShapeProps(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, 
                 properties=None, transform=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, 
                         parent=parent)
        if transform:
            self._set_transform(transform)
        self._child = None

    def _set_transform(self, xf):
        pt = self._props.transform
        for r in range(0, 4):
            for c in range(0, 4):
                pt[c*4+r] = xf[r][c]

    @property
    def transform(self):
        t = self.properties.transform
        return ((t[0][0], t[1][0], t[2][0], t[3][0]),
                (t[0][1], t[1][1], t[2][1], t[3][1]),
                (t[0][2], t[1][2], t[2][2], t[3][2]),
                (t[0][3], t[1][3], t[2][3], t[3][3]))

    def add_shape(self, childprops):
        child = bhkShape.New(file=self.file, properties=childprops, parent=self)
        self._child = child
        self.properties.shapeID = child.id
        return child

    @property
    def child(self):
        if self._child: return self._child
        self._child = bhkShape.New(id=self.properties.shapeID, file=self.file, parent=self)
        return self._child

    @child.setter
    def child(self, value):
        NifFile.nifly.setCollConvexTransformShapeChild(self.file._handle,
                                                       self.id,
                                                       value.id)


class bhkConstraint(NiObject):
    buffer_type = PynBufferTypes.bhkRagdollConstraintBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkRagdollConstraintBuf(values)
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._entities = None

    @property
    def entities(self):
        if self._entities: return self._entities

        buf = (c_uint32 * self.properties.entityCount)()
        NifFile.nifly.getRagdollEntities(
            self.file._handle, self.id, byref(buf), self.properties.entityCount)
        self._entities = []
        for constr_id in buf:
            self._entities.append(bhkWorldObject(file=self.file, id=constr_id, parent=self))
        
        return self._entities       


class bhkWorldObject(NiObject):
    @classmethod
    def getbuf(cls, values=None):
        assert False, "bhkWorldObject should never be instantiated directly."

    @classmethod
    def get_buffer(cls, bodytype, values=None):
        return NiObject.block_types[bodytype].getbuf(values=values)

    @classmethod
    def New(cls, objtype=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        if properties:
            objtype = cls._buftype_name(properties.bufType)
        elif not objtype:
            buf = create_string_buffer(128)
            NifFile.nifly.getBlockname(file._handle, id, buf, 128)
            objtype = buf.value.decode('utf-8')
        # try:
        if id == NODEID_NONE:
            id = NifFile.nifly.addBlock(
                file._handle, 
                None, 
                byref(properties), 
                parent.id if parent else None)
        return file.read_node(id=id, parent=parent, properties=properties)

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._shape = None
        self._constraints = None

    @property 
    def constraints(self):
        if self._constraints: return self._constraints

        buf = (c_uint32 * self.properties.constraintCount)()
        NifFile.nifly.getRigidBodyConstraints(
            self.file._handle, self.id, byref(buf), self.properties.constraintCount)
        self._constraints = []
        for constr_id in buf:
            self._constraints.append(bhkConstraint(file=self.file, id=constr_id, parent=self))
        
        return self._constraints

    @property
    def shape(self):
        if not self._shape:
            shape_index =self.properties.shapeID
            self._shape = bhkShape.New(
                id=shape_index, file=self.file, parent=self)
        return self._shape

    def add_shape(self, properties, vertices=None, normals=None, transform=None):
        """ Create collision shape 
            bhkConvexVerticesShape - vertices can be vectors of 3 points. Normals must be 
                vectors of 4 elements: x, y, z (setting direction), and w (length)
            bhkBoxShape & others - All data passed in through the properties
        """
        return self.file.add_shape(properties=properties, parent=self, 
                                   vertices=vertices, normals=normals, transform=transform)


class bhkRigidBody(bhkWorldObject):
    buffer_type = PynBufferTypes.bhkRigidBodyBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkRigidBodyProps(values)


class bhkRigidBodyT(bhkRigidBody):
    @classmethod
    def getbuf(cls, values=None):
        buf = bhkRigidBodyProps(values)
        buf.bufType = PynBufferTypes.bhkRigidBodyTBufType
        return buf


class bhkSimpleShapePhantom(bhkWorldObject):
    buffer_type = PynBufferTypes.bhkSimpleShapePhantomBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkSimpleShapePhantomBuf(values)


class NiCollisionObject(NiObject):
    """Represents various collision objects."""
    buffer_type = PynBufferTypes.NiCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)

    @classmethod
    def New(cls, 
            collisiontype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        if properties:
            collisiontype = cls._buftype_name(properties.bufType)
        elif not collisiontype:
            buf = create_string_buffer(128)
            NifFile.nifly.getBlockname(file._handle, id, buf, 128)
            collisiontype = buf.value.decode('utf-8')
        try:
            if id == NODEID_NONE:
                id = NifFile.nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            return file.read_node(id=id, parent=parent, properties=properties)
        except:
            return None

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._body = None

    @property
    def flags(self):
        """ Return the collision object flags """
        return self.properties.flags

    @property
    def target(self):
        """ Return the node that is the target of the collision object """
        targ = NifFile.nifly.getCollTarget(self.file._handle, self._handle)
        return self.file.nodeByHandle(targ)

    @property
    def body(self):
        """ Return the collision body object """
        if not self._body:
            if self.properties.bodyID != NODEID_NONE:
                self._body = bhkWorldObject.New(id=self.properties.bodyID, file=self.file, parent=self)
        return self._body

    def add_body(self, properties):
        """ Create a rigid body for this collision object """
        rb_index = NifFile.nifly.addBlock(
            self.file._handle, None, byref(properties), self.id)
        self._body = bhkWorldObject(id=rb_index, file=self.file, parent=self, properties=properties)
        return self._body


class bhkNPCollisionObject(NiCollisionObject):
    pass


class bhkNiCollisionObject(NiCollisionObject):
    buffer_type = PynBufferTypes.bhkNiCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)


class bhkCollisionObject(bhkNiCollisionObject):
    buffer_type = PynBufferTypes.bhkCollisionObjectBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkCollisionObjectBuf(values)


class bhkPCollisionObject(bhkNiCollisionObject):
    buffer_type = PynBufferTypes.bhkPCollisionObjectBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)


class bhkSPCollisionObject(bhkPCollisionObject):
    buffer_type = PynBufferTypes.bhkSPCollisionObjectBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkSPCollisionObjectBuf(values)


class bhkBlendCollisionObject(bhkCollisionObject):
    buffer_type = PynBufferTypes.bhkBlendCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkBlendCollisionObjectBuf(values)


class NiAVObject(NiObjectNET):
    def add_collision(self, body, flags=None):
        buf = bhkCollisionObjectBuf()
        if flags is not None: buf.flags = flags
        buf.bodyID = NODEID_NONE
        if body: buf.bodyID = body.id
        buf.targetID = self.id
        new_coll_id = NifFile.nifly.addBlock(self.file._handle, None, byref(buf), self.id)
        new_coll = NiCollisionObject(file=self.file, 
                                   id=new_coll_id, 
                                   properties=buf, 
                                   parent=self)
        return new_coll
    

# --- NiNode --- #

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
    def blender_name(self, nif_name):
        return self.file.dict.blender_name(nif_name)

    @property
    def nif_name(self, blender_name):
        return self.file.dict.nif_name(blender_name)
    
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
        NifFile.nifly.setNodeFlags(self._handle, value)

    @property
    def blender_name(self):
        return self.file.blender_name(self.name)

    @property
    def parent(self):
        if self._parent is None and self.file._handle is not None:
            parent_handle = NifFile.nifly.getNodeParent(self.file._handle, self._handle)
            if parent_handle is not None:
                for n in self.file.nodes.values():
                    if n._handle == parent_handle:
                        self._parent = n
        return self._parent

    @property
    def global_transform(self):
        if self.file._handle:
            buf = TransformBuf()
            NifFile.nifly.getNodeTransformToGlobal(self.file._handle, self.name.encode('utf-8'), buf)
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

    @property
    def bsx_flags(self):
        """ Returns bsx flags as [name, value] pair """
        if not self.file._handle: return None
        buf = BSXFlagsBuf()
        bsxf_id = NifFile.nifly.getExtraData(self.file._handle, self.id, b"BSXFlags")
        if NifFile.nifly.getBlock(self.file._handle, bsxf_id, byref(buf)) == 0:
            return ["BSX", buf.integerData]
        else:
            return None

    @bsx_flags.setter
    def bsx_flags(self, val):
        """ Sets BSX flags using [name, value] pair """
        buf = BSXFlagsBuf()
        buf.integerData = val[1]
        NifFile.nifly.addBlock(self.file._handle, val[0].encode('utf-8'), byref(buf), self.id)

    @property
    def inventory_marker(self):
        """ Reads BSInvMarker as [name, x, y, z, zoom] """
        if not self.file._handle: return []
        buf = BSInvMarkerBuf()
        namebuf = create_string_buffer(256)
        im_id = NifFile.nifly.getExtraData(self.file._handle, self.id, b"BSInvMarker")
        if im_id != NODEID_NONE:
            NifFile.nifly.getBlock(self.file._handle, im_id, byref(buf))
            NifFile.nifly.getString(self.file._handle, buf.nameID, 256, namebuf)

            return [namebuf.value.decode('utf-8'), buf.rot0, buf.rot1, buf.rot2, buf.zoom]
        else:
            return []

    @inventory_marker.setter
    def inventory_marker(self, val):
        """ WRites BSInvMarker as [name, x, y, z, zoom] """
        buf = BSInvMarkerBuf()
        buf.rot0 = val[1]
        buf.rot1 = val[2]
        buf.rot2 = val[3]
        buf.zoom = val[4]
        NifFile.nifly.addBlock(self.file._handle, val[0].encode('utf-8'), byref(buf), self.id)


class BSFaceGenNiNode(NiNode):
    pass

class BSFadeNode(NiNode):
    pass

class BSLeafAnimNode(NiNode):
    pass

class BSMasterParticleSystem(NiNode):
    pass

class BSMultiBoundNode(NiNode):
    pass

class BSOrderedNode(NiNode):
    pass

class BSRangeNode(NiNode):
    pass

class BSTreeNode(NiNode):
    pass

class BSValueNode(NiNode):
    pass

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
    pass

class NiKeyFrameData(NiObject):
    pass


class LinearScalarKey:
    def __init__(self, buf:NiAnimKeyLinearBuf=None):
        if buf:
            self.time = buf.time
            self.value = buf.value
        self.addKey = NifFile.nifly.addAnimKeyLinear

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)
    
    def __str__(self): 
        return f"<LinearScalarKey>(time={self.time}, value={self.value:f})"

    def getbuf(self):
        buf = NiAnimKeyLinearBuf()
        buf.time = self.time
        buf.value = self.value
        return buf


class LinearVectorKey:
    def __init__(self, buf):
        self.time = buf.time
        self.value = [buf.value[0], buf.value[1], buf.value[2]]

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)

    def __str__(self): 
        return f"<LinearVectorKey>(time={self.time}, value=[{self.value[0]:f}, {self.value[1]:f}, {self.value[2]:f}])"


class LinearQuatKey:
    def __init__(self, buf):
        self.time = buf.time
        self.value = [buf.value[0], buf.value[1], buf.value[2], buf.value[3]]

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)

    def __str__(self): 
        return f"<LinearQuatKey>(time={self.time}, value=[{self.value[0]:f}, {self.value[1]:f}, {self.value[2]:f}, {self.value[3]:f}])"


class QuadScalarKey:

    def __init__(self, buf:NiAnimKeyFloatBuf=None):
        if buf:
            self.time = buf.time
            self.value = buf.value
            self.forward = buf.forward
            self.backward = buf.backward
        self.addKey = NifFile.nifly.addAnimKeyQuadFloat

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value) \
            and VNearEqual(self.forward, other.forward) \
            and VNearEqual(self.backward, other.backward) 

    def __str__(self): 
        return f"<QuadScalarKey>(time={self.time}, value={self.value[:]}, forward={self.forward[:]}, backward={self.backward[:]})"
    
    def getbuf(self):
        buf = NiAnimKeyFloatBuf()
        buf.time = self.time
        buf.value = self.value
        buf.forward = self.forward
        buf.backward = self.backward
        return buf


class QuadVectorKey:
    time = 0.0
    value = []
    forward = 0.0
    backward = 0.0

    def __init__(self, buf:NiAnimKeyQuadTransBuf):
        self.time = buf.time
        self.value = buf.value[:]
        self.forward = buf.forward[:]
        self.backward = buf.backward[:]

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value) \
            and VNearEqual(self.forward, other.forward) \
            and VNearEqual(self.backward, other.backward) 

    def __str__(self): 
        return f"<QuadVectorKey>(time={self.time}, value={self.value[:]}, forward={self.forward[:]}, backward={self.backward[:]})"


class NiFloatData(NiObject):
    buffer_type = PynBufferTypes.NiFloatDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None, keys=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        # self.keys = keys
        if self._handle == None and self.id == NODEID_NONE:
            self.id = NifFile.nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            if keys:
                for k in keys:
                    buf = k.getbuf()
                    k.addKey(self.file._handle, self.id, buf)
            self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
            if parent: parent.data = self

    @property
    def keys(self):
        NifFile.clear_log()
        if self.id == NODEID_NONE: return None
        keys = []
        if self.properties.keys.interpolation in (
                NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY):
            for frame in range(0, self.properties.keys.numKeys):
                if self.properties.keys.interpolation == NiKeyType.LINEAR_KEY:
                    buf = NiAnimKeyLinearBuf()
                    if NifFile.nifly.getAnimKeyLinear(self.file._handle, self.id, frame, buf) != 0:
                        raise Exception(f"Error reading NiFloatDataKey: {NifFile.message_log()}")            
                    k = LinearScalarKey(buf)
                else:
                    buf = NiAnimKeyFloatBuf()
                    if NifFile.nifly.getAnimKeyQuadFloat(self.file._handle, self.id, frame, buf) != 0:
                        raise Exception(f"Error reading NiFloatDataKey: {NifFile.message_log()}")            
                    k = QuadScalarKey(buf)
                keys.append(k)
        else:
            raise Exception(f"Unknown controller key type: {self.properties.keys.interpolation}")
        return keys

    def keys_add(self, k):
        """
        Write quadratic float key.
        """
        buf = NiAnimKeyFloatBuf()
        buf.time = k.time
        buf.value = k.value
        buf.forward = k.forward
        buf.backward = k.backward
        NifFile.nifly.addAnimKeyQuadFloat(self.file._handle, self.id, buf)

    @classmethod
    def getbuf(cls, values=None):
        return NiFloatDataBuf(values)
        

class NiPosData(NiObject):
    buffer_type = PynBufferTypes.NiPosDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None, keys=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._keys = None

    def _writequadkeys(self, keys):
        """
        Write quadratic float keys.
        keys = list of NiAnimKeyQuadTransBuf 
        """
        for k in keys:
            NifFile.nifly.addAnimKeyQuadTrans(self.file._handle, self.id, k)

    @property
    def keys(self):
        if (self._keys is None) and (self.id != NODEID_NONE):
            NifFile.clear_log()
            if self.properties.keys.interpolation != NiKeyType.QUADRATIC_KEY:
                raise Exception(f"Unknown controller key type: {self.properties.keys.interpolation}")
            self._keys = []
            for frame in range(0, self.properties.keys.numKeys):
                buf = NiAnimKeyQuadTransBuf()
                NifFile.nifly.getAnimKeyQuadTrans(self.file._handle, self.id, frame, buf) 
                self._keys.append(buf)
        return self._keys


    def add_key(self, key):
        """
        Write one key.
        """
        buf = NiAnimKeyQuadTransBuf()
        buf.time = key.time
        buf.value = key.value
        buf.forward = key.forward
        buf.backward = key.backward
        NifFile.nifly.addAnimKeyQuadTrans(self.file._handle, self.id, buf)


    @classmethod
    def New(cls, file, interpolation, parent=None):
        p = NiPosDataBuf()
        p.keys.interpolation = interpolation

        pd = file.add_block(None, p, parent)

        return pd


    @classmethod
    def getbuf(cls, values=None):
        return NiPosDataBuf(values)
        

class NiTransformData(NiKeyFrameData):
    buffer_type = PynBufferTypes.NiTransformDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        
        self.xrotations = []
        self.yrotations = []
        self.zrotations = []
        self.qrotations = []
        self.translations = []
        self.scales = []

        if self.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
            self._readxyzrot()
        elif self.properties.rotationType in [NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY]:
            self._readlinrot()

        for frame in range(0, self.properties.translations.numKeys):
            k = None
            if self.properties.translations.interpolation == NiKeyType.LINEAR_KEY:
                buf = NiAnimKeyLinearTransBuf()
                NifFile.nifly.getAnimKeyLinearTrans(self.file._handle, self.id, frame, buf)
                k = LinearVectorKey(buf)
            elif self.properties.translations.interpolation == NiKeyType.QUADRATIC_KEY:
                buf = NiAnimKeyQuadTransBuf()
                NifFile.nifly.getAnimKeyQuadTrans(self.file._handle, self.id, frame, buf)
                k = QuadVectorKey(buf)
            else:
                NifFile.log.warning(f"Found unknown key type: {self.properties.translations.interpolation}")
            if k: self.translations.append(k)

    @classmethod
    def getbuf(cls, values=None):
        return NiTransformDataBuf(values)
    
    @classmethod 
    def New(cls, file, 
            rotation_type=NiKeyType.LINEAR_KEY, 
            xyz_rotation_types=(NiKeyType.QUADRATIC_KEY, )*3,
            translate_type=NiKeyType.LINEAR_KEY,
            scale_type=NiKeyType.LINEAR_KEY,
            properties=None,
            parent=None):
        p:NiTransformDataBuf = properties
        if not p:
            p = NiTransformDataBuf()
            p.rotationType = rotation_type
            p.translations.interpolation = translate_type
            p.xRotations.interpolation = xyz_rotation_types[0]
            p.yRotations.interpolation = xyz_rotation_types[1]
            p.zRotations.interpolation = xyz_rotation_types[2]
            p.scales.interpolation = scale_type
        td = file.add_block(None, p, parent)
        return td
    
    def _readlinrot(self):
        """Read keys when the type is LINEAR_KEY or QUADRATIC_KEY. These are time, value
        pairs where the value is a quaternion. 
        """
        for frame in range(0, self.properties.rotationKeyCount):
            buf = NiAnimKeyLinearQuatBuf()
            NifFile.nifly.getAnimKeyLinearQuat(self.file._handle, self.id, frame, buf)
            k = LinearQuatKey(buf)
            self.qrotations.append(k)

    def _readxyzrot(self):
        """Read keys when the type is XYZ_ROTATION_KEY. X, Y, and Z values are in separate
        lists and each can have a different key type. """
        for d, p, v in [('X', self.properties.xRotations, self.xrotations), 
                        ('Y', self.properties.yRotations, self.yrotations), 
                        ('Z', self.properties.zRotations, self.zrotations)]:
            for f in range(0, p.numKeys):
                k = self._readrotkey(d, f, p)
                v.append(k)

    def _readrotkey(self, d, frame, rots):
        dimension = c_char()
        dimension.value = d.encode('utf-8')
        if rots.interpolation == NiKeyType.QUADRATIC_KEY:
            buf = NiAnimKeyFloatBuf()
            NifFile.nifly.getAnimKeyQuadXYZ(self.file._handle, self.id, dimension, frame, buf)
            k = QuadScalarKey(buf)
        elif rots.interpolation == NiKeyType.LINEAR_KEY:
            buf = NiAnimKeyLinearBuf()
            NifFile.nifly.getAnimKeyLinearXYZ(self.file._handle, self.id, dimension, frame, buf)
            k = LinearScalarKey(buf)
        return k

    def add_translation_key(self, time, loc):
        """Add a key that does a translation. Keys must be added in time order."""
        buf = NiAnimKeyLinearTransBuf()
        buf.time = time
        buf.value = loc[:]
        NifFile.nifly.addAnimKeyLinearTrans(self.file._handle, self.id, buf)

    def add_quad_translation_keys(self, keys):
        """
        Add tranlation keys with quadratic interpolation.
        keys = [NiAnimKeyQuadTransBuf, ...]
        """
        for k in keys:
            NifFile.nifly.addAnimKeyQuadTrans(self.file._handle, self.id, k)

    def add_qrotation_key(self, time, q):
        """
        Add a key that does a rotation given as a quaternion, linear interpolation. 
        Keys must be added in time order.
        """
        buf = NiAnimKeyLinearQuatBuf()
        buf.time = time
        buf.value = q[:]
        NifFile.nifly.addAnimKeyLinearQuat(self.file._handle, self.id, buf)

    def add_xyz_rotation_keys(self, dimension, key_list):
        """
        Add XYZ rotation keys.
        key_list = [NiAnimKeyFloatBuf, ...]
        """
        keytype = ''
        if dimension == "X": 
            keytype = self.properties.xRotations.interpolation
        elif dimension == "Y": 
            keytype = self.properties.yRotations.interpolation
        elif dimension == "Z": 
            keytype = self.properties.zRotations.interpolation
        elif dimension == "S": 
            keytype = self.properties.scales.interpolation
        
        if keytype == NiKeyType.QUADRATIC_KEY:
            d = c_char()
            d.value = dimension.encode('utf-8')
            for q in key_list:
                NifFile.nifly.addAnimKeyQuadXYZ(
                    self.file._handle, self.id, d, byref(q.getbuf()))


class NiInterpolator(NiObject):
    buffer_type = PynBufferTypes.NiBlendInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._data = None

    @property
    def data(self):
        if self._data: return self._data
        if self.properties.dataID == NODEID_NONE: return None
        self._data = self.file.read_node(id=self.properties.dataID, parent=self)
        return self._data

    @data.setter
    def data(self, c):
        self._data = c
        self.properties.dataID = c.id

    def _default_import_func(interp, importer, nifnode):
        importer.warn(f"NYI: Import of interpolator {interp.id} {interp}")
    
    import_node = _default_import_func

    @classmethod
    def New(cls, file, data=None, parent=None):
        p = cls.getbuf()
        p.dataID = (data.id if data else NODEID_NONE)
        interp = file.add_block(None, p, parent)
        if data:
            interp._data = data
        return interp


class NiKeyBasedInterpolator(NiInterpolator):
    pass


class NiTransformInterpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiTransformInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._data = None

    @property
    def rotation(self):
        return self.properties.rotation
        
    @classmethod
    def getbuf(cls, values=None):
        return NiTransformInterpolatorBuf(values)
    
    @classmethod
    def New(cls, file, 
            translation=(0,0,0), rotation=(1,0,0,0), scale=1.0, 
            data_block=None, parent=None):
        p = NiTransformInterpolatorBuf()
        p.translation = translation
        p.rotation = rotation[:]
        p.scale = scale
        p.dataID = data_block.id if data_block else NODEID_NONE
        ti = file.add_block(None, p, parent)
        return ti

class BSRotAccumTransfInterpolator(NiTransformInterpolator):
    pass


class NiFloatInterpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiFloatInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if self.id == NODEID_NONE and file and properties:
            self.id = NifFile.nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
            if parent: parent.interpolator = self
        self._data = None
        
    @classmethod
    def getbuf(cls, values=None):
        return NiFloatInterpolatorBuf(values)


class NiPoint3Interpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiPoint3InterpolatorBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiPoint3InterpolatorBuf(values)
    

class NiBlendInterpolator(NiObject):
    """Abstract class"""
    buffer_type = PynBufferTypes.NiBlendInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if parent: parent.interpolator = self
        
    @property
    def data(self):
        if self._data: return self._data
        if self.properties.dataID == NODEID_NONE: return None
        self._data = NiFloatData(file=self.file, id=self.properties.dataID)
        return self._data

    @data.setter
    def data(self, c):
        self._data = c
        self.properties.dataID = c.id

    @classmethod
    def getbuf(cls, values=None):
        return NiBlendInterpolatorBuf(values)
    
    @classmethod
    def New(cls, file, parent=None):
        p = cls.getbuf()
        intp = file.add_block(None, p, parent)
        return intp
    
    def _default_creator(exporter):
        raise Exception("NYI: Export unknown blend interpolator")
    
    blend_interpolator = _default_creator
    

class NiBlendBoolInterpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendBoolInterpolatorBufType

    @property
    def value(self):
        return self.properties.boolValue
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendBoolInterpolatorBufType
        return b

    
class NiBlendFloatInterpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendFloatInterpolatorBufType

    @property
    def value(self):
        return self.properties.floatValue
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendFloatInterpolatorBufType
        return b
    
    
class NiBlendPoint3Interpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendPoint3InterpolatorBufType

    @property
    def value(self):
        return self.properties.point3Value[:]
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendPoint3InterpolatorBufType
        return b
    
    
class NiBlendTransformInterpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendTransformInterpolatorBufType

    @property
    def value(self):
        return None
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendTransformInterpolatorBufType
        return b

    
class NiTimeController(NiObject):
    """
    Abstract class for time controllers. Keeping the chain of subclasses below because
    we'll likely need them eventually.
    """
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = target
        if parent: parent.controller = self

    @property 
    def next_controller(self):
        if self.properties.nextControllerID == NODEID_NONE:
            return None
        else:
            return self.file.read_node(self.properties.nextControllerID)
        
    @property
    def target(self):
        if self._target: return self._target
        if self.properties.targetID == NODEID_NONE: return None
        self._target = self.file.read_node(id=self.properties.targetID)
        return self._target
    
    @property
    def is_cyclic(self):
        f = TimeControllerFlags()
        f.flags = self.properties.flags
        return f.cycle_type == CycleType.LOOP
    
    def _default_import_func(ctlr, importer, nifnode=None):
        raise Exception(f"NYI: Import of controller {ctlr.id} {ctlr}")
    
    def _default_fcurve_export(exporter, fcurves, target_obj):
        raise Exception(f"NYI: Export of fcurves on {target_obj.name}")
    
    import_node = _default_import_func
    fcurve_exporter = _default_fcurve_export


class NiInterpController(NiTimeController):
    pass


class NiSingleInterpController(NiInterpController):
    buffer_type = PynBufferTypes.NiSingleInterpControllerBufType

    def __init__(self, 
                 handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(
            handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = target
        self._interpolator = interpolator
        
    @property
    def interpolator(self):
        if self._interpolator: return self._interpolator
        if self.properties.interpolatorID == NODEID_NONE: return None
        self._interpolator = self.file.read_node(
            id=self.properties.interpolatorID, parent=self)
        return self._interpolator
    
    @interpolator.setter
    def interpolator(self, c):
        self._interpolator = c
        self.properties.interpolatorID = c.id

    @property
    def target(self):
        if self._target: return self._target
        if self.properties.targetID == NODEID_NONE: return None
        self._target = self.file.read_node(id=self.properties.targetID)
        return self._target

    @classmethod
    def New(cls, file, 
            flags=108, 
            next_controller=None, 
            start_time=sys.float_info.max, stop_time=-sys.float_info.max, 
            frequency=1.0,
            phase=0,
            interpolator=None, 
            target=None, 
            var=0, 
            parent=None):
        p = cls.getbuf()
        p.flags = flags
        p.nextControllerID = (next_controller.id if next_controller else NODEID_NONE)
        p.startTime = start_time
        p.stopTime = stop_time
        p.frequency = frequency
        p.phase = phase
        p.controlledVariable = var
        if target: p.targetID = (target.id if target else NODEID_NONE)
        if interpolator: p.interpolatorID = (interpolator.id if interpolator else NODEID_NONE)
        c = file.add_block(None, p, parent)
        c._target = target
        c._interpolator = interpolator
        return c


class NiKeyframeController(NiSingleInterpController):
    pass


class NiTransformController(NiKeyframeController):
    buffer_type = PynBufferTypes.NiTransformControllerBufType

    def __init__(self, 
                 handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(
            handle=handle, file=file, id=id, properties=properties, parent=parent,
            target=target, interpolator=interpolator)
        self._target = None
        self._properties = NiTransformControllerBuf()
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(self._properties))

    @classmethod
    def getbuf(cls, values=None):
        return NiTransformControllerBuf(values)
    

class NiMultiTargetTransformController(NiInterpController):
    buffer_type = PynBufferTypes.NiMultiTargetTransformControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        self._properties = NiMultiTargetTransformControllerBuf()
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(self._properties))

    @classmethod
    def getbuf(cls, values=None):
        return NiMultiTargetTransformControllerBuf(values)
    
    @classmethod
    def New(cls, file, flags, target, parent=None):
        p = NiMultiTargetTransformControllerBuf()
        p.flags = flags
        p.targetID = target.id
        tc = file.add_block(None, p, parent)
        tc._target = target
        return tc


class NiFloatInterpController(NiSingleInterpController):
    pass


class BSEffectShaderPropertyFloatController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        if self.id == NODEID_NONE and file and properties: 
            self.id = NifFile.nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def getbuf(cls, values=None):
        return BSEffectShaderPropertyFloatControllerBuf(values)


class BSEffectShaderPropertyColorController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyColorControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        if self.id == NODEID_NONE and file and properties: 
            self.id = NifFile.nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def getbuf(cls, values=None):
        return BSEffectShaderPropertyColorControllerBuf(values)


class BSLightingShaderPropertyColorController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSLightingShaderPropertyColorControllerBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSLightingShaderPropertyColorControllerBuf(values)

    @classmethod
    def New(cls, file, flags, target, 
            start_time, stop_time,
            interpolator=None,
            next_controller=None,
            var=LightingShaderControlledColor.SPECULAR,
            parent=None):
        p = BSLightingShaderPropertyColorControllerBuf()
        p.flags = flags
        p.startTime = start_time
        p.stopTime = stop_time
        p.targetID = target.id
        p.nextControllerID = next_controller.id if next_controller else NODEID_NONE
        p.interpolatorID = interpolator.id if interpolator else NODEID_NONE
        p.typeOfControlledColor = var
        tc = file.add_block(None, p, parent)
        return tc


class BSEffectShaderPropertyFloatController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyFloatControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        if self.id == NODEID_NONE and file and properties: 
            self.id = NifFile.nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def getbuf(cls, values=None):
        return BSEffectShaderPropertyFloatControllerBuf(values)


class BSLightingShaderPropertyFloatController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSLightingShaderPropertyFloatControllerBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSLightingShaderPropertyFloatControllerBuf(values)


class NiAlphaController(NiFloatInterpController):
    pass


class BSNiAlphaPropertyTestRefController(NiAlphaController):
    buffer_type = PynBufferTypes.BSNiAlphaPropertyTestRefControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)

    @classmethod
    def getbuf(cls, values=None):
        return BSNiAlphaPropertyTestRefControllerBuf(values)


class ControllerLink:
    buffer_type = PynBufferTypes.NiControllerLinkBufType


    def __init__(self, props:ControllerLinkBuf, parent):
        self.properties = props.copy()
        self.parent = parent
        self._controller = None
        self._nodename = None
        self._controller_type = None
        self._property_type = None
        self._interpolator = None

    @property
    def node_name(self):
        if self._nodename is None: 
            self._nodename = self.parent.file.get_string(self.properties.nodeName)
        return self._nodename
    
    @property
    def controller_type(self):
        if self._controller_type is None: 
            self._controller_type = self.parent.file.get_string(self.properties.ctrlType)
        return self._controller_type
    
    @property
    def property_type(self):
        if self._property_type is None: 
            self._property_type = self.parent.file.get_string(self.properties.propType)
        return self._property_type
    
    @property
    def interpolator(self):
        if self._interpolator: return self._interpolator
        self._interpolator = self.parent.file.read_node(
            id=self.properties.interpolatorID, parent=self.parent)
        return self._interpolator

    @property
    def controller(self):
        if self._controller: return self._controller
        if self.properties.controllerID == NODEID_NONE: return None
        self._controller = self.parent.file.read_node(id=self.properties.controllerID, parent=self)
        return self._controller
    
    @controller.setter
    def controller(self, node):
        self._controller = node
    
    @classmethod
    def New(cls, node_name, controller_type, file, properties=ControllerLinkBuf(), 
            parent=None):
        properties.nodeName = NifFile.nifly.addString(
            file._handle, node_name.encode('utf-8'))
        properties.ctrlType = NifFile.nifly.addString(
            file._handle, controller_type.encode('utf-8'))
        parent.add_controlled_block(
            node_name,
            properties.interpolatorID,
        )
        

class NiSequence(NiObject):
    buffer_type = PynBufferTypes.NiControllerSequenceBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._name = None
        self._controlled_blocks = None

    @property
    def name(self):
        if self._name: return self._name

        namebuf = (c_char * 128)()
        NifFile.nifly.getString(
            self.file._handle, self.properties.nameID, 128, namebuf)
        self._name = namebuf.value.decode('utf-8')

        return self._name
    
    @property
    def controlled_blocks(self):
        if self._controlled_blocks is not None: return self._controlled_blocks

        buf = (ControllerLinkBuf * self.properties.controlledBlocksCount)()
        for i in range(0, self.properties.controlledBlocksCount):
            buf[i].bufType = PynBufferTypes.NiControllerLinkBufType
            buf[i].bufSize = sizeof(ControllerLinkBuf)
        buf[0].bufSize = sizeof(ControllerLinkBuf) * self.properties.controlledBlocksCount
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(buf))
        self._controlled_blocks = []
        for b in buf:
            self._controlled_blocks.append(ControllerLink(b, self))
        return self._controlled_blocks

    def add_controlled_block(self,
                             name:str,
                             interpolator=None,
                             controller=None,
                             priority=0,
                             node_name=None,
                             #prop_type=None,
                             controller_type=None,
                             #ctrlr_id=None,
                             #interpolator_id=None,
                             ):
        buf = ControllerLinkBuf()
        buf.interpolatorID = interpolator.id if interpolator else NODEID_NONE
        buf.controllerID = controller.id if controller else NODEID_NONE
        buf.priority = priority
        buf.nodeName = NODEID_NONE
        buf.ctrlType = NODEID_NONE
        buf.ctrlID = NODEID_NONE
        buf.propType = NODEID_NONE
        if node_name is None:
            if name:
                node_name = name
            elif controller:
                if isinstance(controller.target, (NiShader, NiAlphaProperty,)):
                    node_name = controller.target.parent.name
                else:
                    node_name = controller.target.name
            else:
                node_name = ''
        buf.nodeName = NifFile.nifly.addString(
            self.file._handle, node_name.encode('utf-8'))

        if controller: 
            prop_type = controller.target.blockname
            buf.propType = NifFile.nifly.addString(
                self.file._handle, prop_type.encode('utf-8'))

            if controller_type is None:
                controller_type = controller.blockname

        if controller_type is None: 
            buf.ctrlType = NODEID_NONE
        else:
            buf.ctrlType = NifFile.nifly.addString(
                self.file._handle, controller_type.encode('utf-8'))

        # Not adding the controller ID or interpoator ID string values because those can
        # change when nifly does cleanup on save. If this turns out to be a problem, we'll
        # have to set them after cleanup.
        buf.interpID = NODEID_NONE
        
        NifFile.nifly.addBlock(self.file._handle, name.encode('utf-8'), byref(buf), self.id)
        if self._controlled_blocks is None: self._controlled_blocks = []
        self._controlled_blocks.append(ControllerLink(buf, self))

    def _default_import_func(self, importer):
        importer.warn(f"NYI: Import of NiSequence {self.id} {self.name}")
    
    import_node = _default_import_func


class NiTextKeyExtraData(NiObject):
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
                valuebuf = create_string_buffer(256)
                NifFile.nifly.getNiTextKey(
                    self.file._handle, self.id, i, byref(buf))
                n = NifFile.nifly.getString(
                    self.file._handle, buf.valueID, 256, valuebuf)
                self._keys.append((buf.time, valuebuf.value.decode('utf-8'),))
        return self._keys
    
    def add_key(self, time, val):
        if self._keys is None: self._keys = []
        err = NifFile.nifly.addTextKey(
            self.file._handle, self.id, time, val.encode('utf-8'))
        self._keys.append((time, val,))

    @classmethod
    def New(cls, file, name='', keys=[], parent=None):
        p = NiTextKeyExtraDataBuf()
        tk = file.add_block(name, p, parent)
        for t, v in keys:
            tk.add_key(t, v)
        return tk


class NiControllerSequence(NiSequence):
    buffer_type = PynBufferTypes.NiControllerSequenceBufType
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._text_key_data = None

    @property
    def accumRootName(self):
        namebuf = (c_char * self.file.max_string_len)()
        NifFile.nifly.getString(
            self.file._handle, 
            self.properties.accumRootNameID, 
            self.file.max_string_len, 
            namebuf)
        return namebuf.value.decode('utf-8')

    @property
    def is_cyclic(self):
        return self.properties.cycleType == 0
    
    @property
    def text_key_data(self) -> NiTextKeyExtraData:
        if self._text_key_data is None:
            self._text_key_data = self.file.read_node(
                id=self.properties.textKeyID)
        return self._text_key_data

    @classmethod
    def getbuf(cls, values=None):
        return NiControllerSequenceBuf(values)
    
    @classmethod
    def New(cls, file, name, accum_root_name=None, frequency=1, phase=0,
            start_time=0, stop_time=0, cycle_type=CycleType.CLAMP, weight=1.0,
            text_key_data=None, parent=None, 
            ):
        """
        Create a new controller sequence block.
        """
        p = NiControllerSequenceBuf()
        p.frequency = frequency
        p.phase = phase
        p.startTime = start_time
        p.stopTime = stop_time
        p.cycleType = cycle_type
        p.textKeyID = text_key_data.id if text_key_data else NODEID_NONE
        p.weight = weight

        if parent: p.managerID = parent.id
        if accum_root_name is not None:
            p.accumRootNameID = NifFile.nifly.addString(
                file._handle, 
                accum_root_name.encode('utf-8'))

        cs = file.add_block(name, p, parent)
        cs._name = name
        if parent: parent.add_sequence(cs)
        return cs


class NiControllerManager(NiTimeController):
    buffer_type = PynBufferTypes.NiControllerManagerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._properties = NiControllerManagerBuf()
        self._controller_manager_sequences = None
        self._object_palette = None
        NifFile.nifly.getBlock(self.file._handle, 
                               self.id, 
                               byref(self._properties))

    @property
    def sequences(self):
        if self._controller_manager_sequences != None:
            return self._controller_manager_sequences
        
        cms_count = NifFile.nifly.getControllerManagerSequences(
            self.file._handle, self._handle, 0, None)
        cmsids = (c_uint32 * cms_count)()
        NifFile.nifly.getControllerManagerSequences(
            self.file._handle, self._handle, cms_count, cmsids)
        
        self._controller_manager_sequences = {}
        for id in cmsids:
            cs = NiControllerSequence(id=id, file=self.file)
            self._controller_manager_sequences[cs.name] = cs

        return self._controller_manager_sequences
    
    def add_sequence(self, seq):
        """
        Add the given controller sequence to the mananger.

        The nif file is not changed. 
        """
        self._controller_manager_sequences[seq.name] = seq

    @property
    def object_palette(self):
        if self._object_palette != None:
            return self._object_palette
        elif self.properties.objectPaletteID == NODEID_NONE:
            return None
        else:
            self._object_palette = self.file.read_node(
                self.properties.objectPaletteID)
            return self._object_palette

    @classmethod
    def getbuf(cls, values=None):
        return NiControllerManagerBuf(values)
    
    @classmethod
    def New(cls, file, flags:TimeControllerFlags, next_controller=None, 
            object_palette=None, parent=None):
        """
        Create a new controller manager block within the target file.
        """
        p = NiControllerManagerBuf()
        p.targetID = parent.id if parent else NODEID_NONE
        p.nextControllerID = next_controller.id if next_controller else NODEID_NONE
        p.flags = flags.flags
        p.objectPaletteID = object_palette.id if object_palette else NODEID_NONE
        cm = file.add_block(None, p, parent)
        cm._controller_manager_sequences = {}
        return cm


class NiDefaultAVObjectPalette(NiObject):
    buffer_type = PynBufferTypes.NiDefaultAVObjectPaletteBufType
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._objects = None

    @classmethod 
    def getbuf(cls, values=None):
        return NiDefaultAVObjectPaletteBuf(values)
    
    @property
    def objects(self):
        """
        Objects returned as dict {}"object name": object, ...}
        """
        if self._objects is None:
            self._objects = {}
            for i in range(0, self.properties.objCount):
                name = create_string_buffer(256)
                refid = (c_uint32)()
                NifFile.nifly.getAVObjectPaletteObject(
                    self.file._handle,
                    self.id,
                    i, 
                    256, name,
                    refid
                )
                refnode = self.file.read_node(refid.value)
                self._objects[name.value.decode('utf-8')] = refnode
        return self._objects
    
    def add_object(self, objname, obj):
        if self._objects is None: 
            self._objects = {}
        if objname not in self._objects:
            NifFile.nifly.addAVObjectPaletteObject(
                self.file._handle,
                self.id,
                objname.encode('utf8'),
                obj.id
            )
            self._objects[objname] = obj
    
    @classmethod
    def New(cls, file, scene=None, objects={}, parent=None):
        p = NiDefaultAVObjectPaletteBuf()
        p.sceneID = scene.id if scene else NODEID_NONE
        objp = file.add_block(None, p, parent)
        for name, obj in objects.items():
            objp.add_object(name, obj)
        return objp


# --- Shaders -- #

class NiAlphaProperty(NiObject):
    @classmethod
    def getbuf(cls, values=None):
        return AlphaPropertyBuf(values)

    @property
    def parent(self):
        if not self._parent:
            for sh in self.file.shapes:
                if sh.properties.alphaPropertyID == self.id:
                    self._parent = sh
                    break 
        return self._parent


class NiShader(NiProperty):
    """
    Handles shader attributes for a Nif. In Skyrim, returns values from the underlying
    shader block. In FO4, most attributes come from the associated materials file.
    """
    buffer_type = PynBufferTypes.NiShaderBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiShaderBuf(values)

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        
        self._textures = None

    @property
    def parent(self):
        if not self._parent:
            for sh in self.file.shapes:
                if sh.properties.shaderPropertyID == self.id:
                    self._parent = sh
                    break 
        return self._parent

    def _readtexture(self, niffile, shape, layer):
        bufsize = 500
        buf = create_string_buffer(bufsize)
        NifFile.nifly.getShaderTextureSlot(niffile, shape, layer-1, buf, bufsize)
        return buf.value.decode('utf-8')

    @property
    def textures(self):
        if self._textures is None:
            self._textures = {}
            if self.properties.bufType == PynBufferTypes.BSLightingShaderPropertyBufType:
                f = self.file._handle
                s = self._parent._handle
                self._textures["Diffuse"] = self._readtexture(f, s, 1)
                self._textures["Normal"] = self._readtexture(f, s, 2)

                if self.properties.shaderflags2_test(ShaderFlags2.GLOW_MAP):
                    self._textures["Glow"] = self._readtexture(f, s, 3)

                try:
                    # Skyrim only
                    if self.properties.shaderflags2_test(ShaderFlags2.RIM_LIGHTING):
                        self._textures["RimLighting"] = self._readtexture(f, s, 3)
                    if self.properties.shaderflags2_test(ShaderFlags2.SOFT_LIGHTING):
                        self._textures["SoftLighting"] = self._readtexture(f, s, 3)
                    if self.properties.shaderflags1_test(ShaderFlags1.PARALLAX):
                        self._textures["HeightMap"] = self._readtexture(f, s, 4)
                    if self.properties.shaderflags1_test(ShaderFlags1.GREYSCALE_COLOR):
                        self._textures["Greyscale"] = self._readtexture(f, s, 4)
                    if self.properties.shaderflags2_test(ShaderFlags2.ENVMAP_LIGHT_FADE):
                        self._textures["EnvMap"] = self._readtexture(f, s, 5)
                    if self.properties.shaderflags1_test(ShaderFlags1.FACEGEN_DETAIL_MAP):
                        self._textures["FacegenDetail"] = self._readtexture(f, s, 7)
                except:
                    pass

                if (self.properties.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING) 
                        or self.properties.shaderflags1_test(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)):
                    self._textures["EnvMap"] = self._readtexture(f, s, 5)
                    self._textures["EnvMask"] = self._readtexture(f, s, 6)

                if self.properties.shaderflags2_test(ShaderFlags2.MULTI_LAYER_PARALLAX):
                    self._textures["InnerLayer"] = self._readtexture(f, s, 7)

                if (self.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)
                    or self.properties.shaderflags1_test(ShaderFlags1.SPECULAR)):
                    self._textures["Specular"] = self._readtexture(f, s, 8)

            if self.properties.bufType == PynBufferTypes.BSEffectShaderPropertyBufType:
                self._textures['Diffuse'] = self.properties.sourceTexture.decode()
                self._textures['Greyscale'] = self.properties.greyscaleTexture.decode()
                self._textures['EnvMap'] = self.properties.envMapTexture.decode()
                self._textures['Normal'] = self.properties.normalTexture.decode()
                self._textures['EnvMapMask'] = self.properties.envMaskTexture.decode()
                self._textures['EmitGradient'] = self.properties.emitGradientTexture.decode()

        return self._textures

    def set_texture(self, slot:str, texturepath):
        """Set texture in the named slot to the given string."""
        if self.properties.bufType == PynBufferTypes.BSLightingShaderPropertyBufType:
            if slot == 'Diffuse':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 0, texturepath.encode('utf-8'))
            if slot == 'Normal':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 1, texturepath.encode('utf-8'))
            if slot in ['Glow', 'RimLighting', 'SoftLighting']:
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 2, texturepath.encode('utf-8'))
            if slot == 'HeightMap':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 3, texturepath.encode('utf-8'))
            if slot == 'EnvMap':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 4, texturepath.encode('utf-8'))
            if slot == 'EnvMask':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 5, texturepath.encode('utf-8'))
            if slot in ['FacegenDetail', 'InnerLayer']:
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 6, texturepath.encode('utf-8'))
            if slot == 'Specular':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 7, texturepath.encode('utf-8'))
                
            if slot == 'Wrinkles':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 8, texturepath.encode('utf-8'))
        if self.properties.bufType == PynBufferTypes.BSEffectShaderPropertyBufType:
            if slot == 'Diffuse':
                self.properties.sourceTexture = texturepath.encode('utf-8')
            if slot == 'Greyscale':
                self.properties.greyscaleTexture = texturepath.encode('utf-8')
            if slot == 'EnvMap':
                self.properties.envMapTexture = texturepath.encode('utf-8')
            if slot == 'Normal':
                self.properties.normalTexture = texturepath.encode('utf-8')
            if slot == 'EnvMapMask':
                self.properties.envMaskTexture = texturepath.encode('utf-8')
            if slot == 'EmitGradient':
                self.properties.emitGradientTexture = texturepath.encode('utf-8')

    # Individual getter routines for shader flags so the caller doesn't have to worry
    # about Skyrim vs FO4.

    @property
    def flag_vertex_alpha(self):
        return self.properties.shaderflags1_test(ShaderFlags1.VERTEX_ALPHA)

    @property
    def flag_facegen_RBG_tint(self):
        return self.properties.shaderflags1_test(ShaderFlags1.FACEGEN_RGB_TINT)

    @property
    def flag_greyscale_color(self):
        return self.properties.shaderflags1_test(ShaderFlags1.GREYSCALE_COLOR)

    @property
    def flag_greyscale_alpha(self):
        return self.properties.shaderflags1_test(ShaderFlags1.GREYSCALE_ALPHA)

    @property
    def flag_decal(self):
        return self.properties.shaderflags1_test(ShaderFlags1.DECAL)

    @property
    def flag_environment_mapping(self):
        return self.properties.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING)

    @property
    def flag_zbuffer_test(self):
        return self.properties.shaderflags1_test(ShaderFlags1.ZBUFFER_TEST)

    @property
    def flag_cast_shadows(self):
        return self.properties.shaderflags1_test(ShaderFlags1.CAST_SHADOWS)
        
    @property
    def flag_external_emittance(self):
        return self.properties.shaderflags1_test(ShaderFlags1.EXTERNAL_EMITTANCE)
        
    @property
    def flag_eye_environment_mapping(self):
        return self.properties.shaderflags1_test(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)

    @property
    def flag_hair(self):
        return self.properties.shaderflags1_test(ShaderFlags1.HAIR)

    @property
    def flag_own_emit(self):
        return self.properties.shaderflags1_test(ShaderFlags1.OWN_EMIT)

    @property
    def flag_model_space_normals(self):
        return self.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)

    @property
    def flag_rgb_falloff(self):
        return self.properties.shaderflags1_test(ShaderFlags1.RGB_FALLOFF)

    @property
    def flag_specular(self):
        return self.properties.shaderflags1_test(ShaderFlags1.SPECULAR)
        
    @property
    def flag_use_falloff(self):
        return self.properties.shaderflags1_test(ShaderFlags1.USE_FALLOFF)

    @property
    def flag_double_sided(self):
        return self.properties.shaderflags2_test(ShaderFlags2.DOUBLE_SIDED)

    @property
    def flag_vertex_colors(self):
        return self.properties.shaderflags2_test(ShaderFlags2.VERTEX_COLORS)

    @property
    def flag_no_fade(self):
        return self.properties.shaderflags2_test(ShaderFlags2.NO_FADE)

    @property
    def flag_glow_map(self):
        return self.properties.shaderflags2_test(ShaderFlags2.GLOW_MAP)

    @property
    def flag_zbuffer_write(self):
        return self.properties.shaderflags2_test(ShaderFlags2.ZBUFFER_WRITE)

    @property
    def flag_anisotropic_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.ANISOTROPIC_LIGHTING)

    @property
    def flag_transform_changed(self):
        return self.properties.shaderflags2_test(ShaderFlags2.TRANSFORM_CHANGED)

    @property
    def flag_vats_target_draw_all(self):
        return self.properties.shaderflags2_test(ShaderFlags2.VATS_TARGET_DRAW_ALL)

    @property
    def flag_gradient_remap(self):
        return self.properties.shaderflags2_test(ShaderFlags2.GRADIENT_REMAP)

    @property
    def flag_alpha_test(self):
        return self.properties.shaderflags2_test(ShaderFlags2.ALPHA_TEST)

    @property
    def flag_tree_anim(self):
        return self.properties.shaderflags2_test(ShaderFlags2.TREE_ANIM)
        
    @property
    def flag_effect_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.EFFECT_LIGHTING)

    @property
    def flag_rim_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.RIM_LIGHTING)

    @property
    def flag_soft_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.SOFT_LIGHTING)

    @property
    def texture_clamp_mode(self):
        return self.properties.textureClampMode
    
    @texture_clamp_mode.setter
    def texture_clamp_mode(self, value):
        self.properties.textureClampMode = value

class BSDistantTreeShaderProperty(NiShader):
    pass

class BSEffectShaderProperty(NiShader):
    pass

class BSLightingShaderProperty(NiShader):
    pass

class BSShaderLightingProperty(NiShader):
    pass

class BSShaderNoLightingProperty(NiShader):
    pass

class BSShaderPPLightingProperty(NiShader):
    pass

class BSShaderProperty(NiShader):
    pass

class BSSkyShaderProperty(NiShader):
    pass

class BSWaterShaderProperty(NiShader):
    pass

class DistantLODShaderProperty(NiShader):
    pass

class HairShaderProperty(NiShader):
    pass

class Lighting30ShaderProperty(NiShader):
    pass

class NiMaterialProperty(NiShader):
    pass

class SkyShaderProperty(NiShader):
    pass

class TallGrassShaderProperty(NiShader):
    pass

class TileShaderProperty(NiShader):
    pass

class VolumetricFogShaderProperty(NiShader):
    pass

class WaterShaderProperty(NiShader):
    pass


class BSEffectShaderProperty(NiShader):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyBufType

    @classmethod
    def getbuf(cls, values=None):
        b = NiShaderBuf(values)
        b.bufType = PynBufferTypes.BSEffectShaderPropertyBufType
        return b


class BSShaderPPLightingProperty(NiShader):
    buffer_type = PynBufferTypes.BSShaderPPLightingPropertyBufType

    @classmethod
    def getbuf(cls, values=None):
        b = NiShaderBuf(values)
        b.bufType = PynBufferTypes.BSShaderPPLightingPropertyBufType
        return b


class NiShaderFO4(NiShader):
    """
    Shader for FO4 nifs. Alters NiShader behavior to get values from the materials file
    when necessary.
    """
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        self.materials = None
        self._checked_for_materials = False
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        
    def _load_properties_from_materials(self):
        """Load materials properties into shader properties so the rest of the world doesn't have to care."""
        if not self.materials: return

        p = self._properties
        p.textureClampMode = self.materials.tileFlags
        p.UV_Offset_U = self.materials.UV_Offset_U
        p.UV_Offset_V = self.materials.UV_Offset_V
        p.UV_Scale_U = self.materials.UV_Scale_U
        p.UV_Scale_V = self.materials.UV_Scale_V
        p.Alpha = self.materials.Alpha
        p.Env_Map_Scale = self.materials.environmentMappingMaskScale
        p.Emissive_Color[0] = self.materials.emittanceColor[0]
        p.Emissive_Color[1] = self.materials.emittanceColor[1]
        p.Emissive_Color[2] = self.materials.emittanceColor[2]
        p.Emissive_Color[3] = 1.0
        p.Emissive_Mult = self.materials.emittanceMult
        p.Refraction_Str = self.materials.refractionPower
        p.Glossiness = self.materials.smoothness
        p.Rim_Light_Power = self.materials.rimPower
        p.subsurfaceRolloff = self.materials.subsurfaceRolloff
        p.fresnelPower = self.materials.fresnelPower

        # Shader flags 1
        p.Shader_Flags_1 = 0
        p.Shader_Flags_2 = 0
        if self.materials.decal:
            p.shaderflags1_set(ShaderFlags1.DECAL)
        else:
            p.shaderflags1_clear(ShaderFlags1.DECAL)

        if self.materials.environmentMapping:
            p.shaderflags1_set(ShaderFlags1.ENVIRONMENT_MAPPING)
        else:
            p.shaderflags1_clear(ShaderFlags1.ENVIRONMENT_MAPPING)

        if self.materials.zbuffertest:
            p.shaderflags1_set(ShaderFlags1.ZBUFFER_TEST)
        else:
            p.shaderflags1_clear(ShaderFlags1.ZBUFFER_TEST)

        if self.materials.twoSided:
            p.shaderflags2_set(ShaderFlags2.DOUBLE_SIDED)
        else:
            p.shaderflags2_clear(ShaderFlags2.DOUBLE_SIDED)

        if self.materials.glowmap:
            p.shaderflags2_set(ShaderFlags2.GLOW_MAP)
        else:
            p.shaderflags2_clear(ShaderFlags2.GLOW_MAP)

        if self.materials.zbufferwrite:
            p.shaderflags2_set(ShaderFlags2.ZBUFFER_WRITE)
        else:
            p.shaderflags2_clear(ShaderFlags2.ZBUFFER_WRITE)

        if self.materials.grayscaleToPaletteColor:
            p.shaderflags1_set(ShaderFlags1.GREYSCALE_COLOR)
        else:
            p.shaderflags1_clear(ShaderFlags1.GREYSCALE_COLOR)

        if self.materials.signature == b'BGSM':
            if self.materials.skinTint:
                p.shaderflags1_set(ShaderFlags1.FACEGEN_RGB_TINT)
            else:
                p.shaderflags1_clear(ShaderFlags1.FACEGEN_RGB_TINT)

            if self.materials.castShadows:
                p.shaderflags1_set(ShaderFlags1.CAST_SHADOWS)
            else:
                p.shaderflags1_clear(ShaderFlags1.CAST_SHADOWS)

            if self.materials.anisoLighting:
                p.shaderflags2_set(ShaderFlags2.ANISOTROPIC_LIGHTING)
            else:
                p.shaderflags2_clear(ShaderFlags2.ANISOTROPIC_LIGHTING)

            if self.materials.tree:
                p.shaderflags2_set(ShaderFlags2.TREE_ANIM)
            else:
                p.shaderflags2_clear(ShaderFlags2.TREE_ANIM)

            if self.materials.externalEmittance:
                p.shaderflags1_set(ShaderFlags1.EXTERNAL_EMITTANCE)
            else:
                p.shaderflags1_clear(ShaderFlags1.EXTERNAL_EMITTANCE)

            if self.materials.environmentMappingEye:
                p.shaderflags1_set(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)
            else:
                p.shaderflags1_clear(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)

            if self.materials.hair:
                p.shaderflags1_set(ShaderFlags1.HAIR_SOFT_LIGHTING)
            else:
                p.shaderflags1_clear(ShaderFlags1.HAIR_SOFT_LIGHTING)

            if self.materials.emitEnabled:
                p.shaderflags1_set(ShaderFlags1.OWN_EMIT)
            else:
                p.shaderflags1_clear(ShaderFlags1.OWN_EMIT)

            if self.materials.modelSpaceNormals:
                p.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
            else:
                p.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)

            if self.materials.specularEnabled:
                p.shaderflags1_set(ShaderFlags1.SPECULAR)
            else:
                p.shaderflags1_clear(ShaderFlags1.SPECULAR)

        if self.materials.signature == b'BGEM':
            if self.materials.falloffEnabled:
                p.shaderflags1_set(ShaderFlags1.USE_FALLOFF)
            else:
                p.shaderflags1_clear(ShaderFlags1.USE_FALLOFF)

            if self.materials.effectLightingEnabled:
                p.shaderflags2_set(ShaderFlags2.EFFECT_LIGHTING)
            else:
                p.shaderflags2_clear(ShaderFlags2.EFFECT_LIGHTING)

    @property
    def properties(self):
        """
        Return shader properties. Return the materials file properties if any; caller will
        have to deal with any properties that differ between FO4 and Skyrim. Return the
        properties buffer if no materials file.
        """
        if not self._properties:
            super().properties

        if not self._checked_for_materials:
            # Find and read the materials file if any. This is where the shader properties
            # will come from. Some FO4 nifs don't have materials files. Apparently (?)
            # they use the shader block attributes.
            self._name = None
            if self.name:
                fullpath = find_referenced_file(self.name, self.file.filepath, root='materials', 
                                                alt_path=self.file.materialsRoot)
                if fullpath:
                    self.materials = bgsmaterial.MaterialFile.Open(fullpath)
                    self._load_properties_from_materials()
            self._checked_for_materials = True

        return self._properties
        
    @property
    def textures(self):
        if self.materials:
            return self.materials.textures
        else:
            return super().textures

    @property
    def shaderflags1(self):
        if self.materials:
            v = 0
            v &= ~ShaderFlags1FO4.DECAL | (
                ShaderFlags1FO4.DECAL if self.materials.decal else 0)
            v &= ~ShaderFlags1FO4.ENVIRONMENT_MAPPING | (
                ShaderFlags1FO4.ENVIRONMENT_MAPPING if self.materials.environmentMapping else 0)
            v &= ~ShaderFlags1FO4.ZBUFFER_TEST | (
                ShaderFlags1FO4.ZBUFFER_TEST if self.materials.zbuffertest else 0)
            if self.materials.signature == b'BGSM':
                v &= ~ShaderFlags1FO4.CAST_SHADOWS | (
                    ShaderFlags1FO4.CAST_SHADOWS if self.materials.castShadows else 0)
                v &= ~ShaderFlags1FO4.EXTERNAL_EMITTANCE | (
                    ShaderFlags1FO4.EXTERNAL_EMITTANCE if self.materials.externalEmittance else 0)
                v &= ~ShaderFlags1FO4.EYE_ENVIRONMENT_MAPPING | (
                    ShaderFlags1FO4.EYE_ENVIRONMENT_MAPPING if self.materials.environmentMappingEye else 0)
                v &= ~ShaderFlags1FO4.HAIR | (
                    ShaderFlags1FO4.HAIR if self.materials.hair else 0)
                v &= ~ShaderFlags1FO4.OWN_EMIT | (
                    ShaderFlags1FO4.OWN_EMIT if self.materials.emitEnabled else 0)
                v &= ~ShaderFlags1FO4.MODEL_SPACE_NORMALS | (
                    ShaderFlags1FO4.MODEL_SPACE_NORMALS if self.materials.modelSpaceNormals else 0)
                v &= ~ShaderFlags1FO4.RGB_FALLOFF | (
                    ShaderFlags1FO4.RGB_FALLOFF if self.materials.receiveShadows else 0)
                v &= ~ShaderFlags1FO4.SPECULAR | (
                    ShaderFlags1FO4.SPECULAR if self.materials.specularEnabled else 0)
            if self.materials.signature == b'BGEM':
                v &= ~ShaderFlags1FO4.USE_FALLOFF | (
                    ShaderFlags1FO4.USE_FALLOFF if self.materials.falloffEnabled else 0)
            return v
        else:
            return self.properties.Shader_Flags_1
    
    @property
    def shaderflags2(self):
        """
        Return shader flags. Get flags held in the materials file from there, if any; get
        the rest from the shader flags in the nif.
        """
        if self.materials:
            v = 0
            v &= ~ShaderFlags2FO4.DOUBLE_SIDED | (
                ShaderFlags2FO4.DOUBLE_SIDED if self.materials.twoSided else 0)
            v &= ~ShaderFlags2FO4.GLOW_MAP | (
                ShaderFlags2FO4.GLOW_MAP if self.materials.glowmap else 0)
            v &= ~ShaderFlags2FO4.ZBUFFER_WRITE | (
                ShaderFlags2FO4.ZBUFFER_WRITE if self.materials.zbufferwrite else 0)
            if self.materials.signature == b'BGSM':
                v &= ~ShaderFlags2FO4.ANISOTROPIC_LIGHTING | (
                    ShaderFlags2FO4.ANISOTROPIC_LIGHTING if self.materials.anisoLighting else 0)
                v &= ~ShaderFlags2FO4.TRANSFORM_CHANGED | (
                    ShaderFlags2FO4.TRANSFORM_CHANGED if self.materials.assumeShadowmask else 0)
                v &= ~ShaderFlags2FO4.VATS_TARGET_DRAW_ALL | (
                    ShaderFlags2FO4.VATS_TARGET_DRAW_ALL if self.materials.backLighting else 0)
                v &= ~ShaderFlags2FO4.GRADIENT_REMAP | (
                    ShaderFlags2FO4.GRADIENT_REMAP if self.materials.rimLighting else 0)
                v &= ~ShaderFlags2FO4.ALPHA_TEST | (
                    ShaderFlags2FO4.ALPHA_TEST if self.materials.subsurfaceLighting else 0)
                v &= ~ShaderFlags2FO4.TREE_ANIM | (
                    ShaderFlags2FO4.TREE_ANIM if self.materials.tree else 0)
            if self.materials.signature == b'BGEM':
                v &= ~ShaderFlags2FO4.EFFECT_LIGHTING | (
                    ShaderFlags2FO4.EFFECT_LIGHTING if self.materials.effectLightingEnabled else 0)
            return v
        else:
            return self.properties.Shader_Flags_2
        
    def flags1_test(self, flag):
        return (self.shaderflags1 & flag) != 0
    
    def flags2_test(self, flag):
        return (self.shaderflags2 & flag) != 0


# --- NifShape --- #
class NiShape(NiNode):
    buffer_type = PynBufferTypes.NiShapeBufType

    @classmethod
    def New(cls, handle=None, shapetype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        # cls.load_subclasses()
        if properties:
            shapetype = cls._buftype_name(properties.bufType)
        if not shapetype:
            if id == NODEID_NONE:
                id = NifFile.nifly.getBlockID(file._handle, handle)
            buf = create_string_buffer(128)
            NifFile.nifly.getBlockname(file._handle, id, buf, 128)
            shapetype = buf.value.decode('utf-8')
        try:
            new_shape = False
            if not handle and id == NODEID_NONE:
                new_shape = True
                id = NifFile.nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            if not handle:
                handle = NifFile.nifly.getBlockByID(id)
            
            s = file.read_node(
                handle=handle, id=id, parent=parent, properties=properties)
            if new_shape:
                s._partitions = []
            return s
        except:
            NifFile.log.warning(f"Shape type is not implemented: {shapetype}")
            return None

    @classmethod
    def getbuf(cls, values=None):
        return NiShapeBuf(values)
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None, 
                 properties=None, name=""):
        super().__init__(handle=handle, file=file, id=id, parent=parent, 
                         properties=properties, name=name)
        self._bone_ids = None
        self._bone_names = None
        self._normals = None
        self._colors = None
        self._scale = 1.0
        self._tris = None
        self._uvs = None
        self._textures = None
        self._is_skinned = False
        self._verts = None
        self._weights = None
        self._partitions = None
        self._partition_tris = None
        self._segment_file = ''
        self.is_head_part = False
        self._shader = None
        self._alpha = None

    def _setShapeXform(self):
        NifFile.nifly.setTransform(self._handle, self.transform)

    @property
    def verts(self):
        if not self._verts:
            verts = (c_float * 3 * self.properties.vertexCount)()
            NifFile.nifly.getVertsForShape(
                self.file._handle, self._handle, verts, self.properties.vertexCount * 3, 0)
            self._verts = [(v[0], v[1], v[2]) for v in verts]
        return self._verts

    @property
    def colors(self):
        """Returns colors as a list of 4-tuples representing color values, 1:1 with vertices."""
        if self._colors is None:
            if self.properties.hasVertexColors:
                buflen = self.properties.vertexCount
                buf = (c_float * 4 * buflen)()
                NifFile.nifly.getColorsForShape(self.file._handle, self._handle, buf, buflen*4)
                self._colors = [(c[0], c[1], c[2], c[3]) for c in buf]
            else:
                self._colors = []
        return self._colors
    
    @property
    def normals(self):
        if not self._normals:
            buflen = self.properties.vertexCount 
            if buflen > 0:
                norms = (c_float * 3 * buflen)()
                NifFile.nifly.getNormalsForShape(
                        self.file._handle, self._handle, norms, buflen * 3, 0)
                self._normals = [(n[0], n[1], n[2]) for n in norms]
        return self._normals

    @property
    def tris(self):
        if self._tris is None:
            triCount = self.properties.triangleCount
            buf = (c_uint16 * 3 * triCount)()
            NifFile.nifly.getTriangles(
                    self.file._handle, self._handle, buf, triCount * 3, 0)
            self._tris = [(t[0], t[1], t[2]) for t in buf]
        return self._tris

    def _read_partitions(self):
        self._partitions = []
        buf = (c_uint16 * 2)()
        pc = NifFile.nifly.getPartitions(self.file._handle, self._handle, None, 0)
        buf = (c_uint16 * 2 * pc)()
        pc = NifFile.nifly.getPartitions(self.file._handle, self._handle, buf, pc)
        for i in range(pc):
            self._partitions.append(SkyPartition(buf[i][1], buf[i][0], namedict=self.file.dict))
    
    def _read_segments(self, num):
        self._partitions = []
        buf = (c_int * 2 * num)()
        pc = NifFile.nifly.getSegments(self.file._handle, self._handle, buf, num)
        for i in range(num):
            p = FO4Segment(part_id=buf[i][0], index=i, subsegments=buf[i][1], namedict=self.file.dict)
            self._partitions.append(p)
            buf2 = (c_uint32 * 3 * p.subseg_count)()
            ssn = NifFile.nifly.getSubsegments(self.file._handle, self._handle, p.id, buf2, p.subseg_count)
            for i in range(ssn):
                ss = FO4Subsegment(part_id=buf2[i][0], 
                                   user_slot=buf2[i][1], 
                                   material=buf2[i][2], 
                                   parent=p, 
                                   namedict=self.file.dict)

    @property
    def partitions(self):
        if self._partitions is None:
            segc = NifFile.nifly.segmentCount(self.file._handle, self._handle)
            if segc > 0:
                self._read_segments(segc)
            else:
                self._read_partitions()
        return self._partitions

    @property
    def partition_tris(self):
        """Returns a list of partition indices matching 1-1 with tris"""
        if self._partition_tris is None:
            buf = (c_uint16 * 1)()
            pc = NifFile.nifly.getPartitionTris(self.file._handle, self._handle, None, 0)
            buf = (c_uint16 * pc)()
            pc = NifFile.nifly.getPartitionTris(self.file._handle, self._handle, buf, pc)
            self._partition_tris = [0] * pc
            for i in range(pc):
                self._partition_tris[i] = buf[i]
        return self._partition_tris

    @property
    def segment_file(self):
        buflen = NifFile.nifly.getSegmentFile(self.file._handle, self._handle, None, 0)+1
        buf = (c_char * buflen)()
        buflen = NifFile.nifly.getSegmentFile(self.file._handle, self._handle, buf, buflen)
        self._segment_file = buf.value.decode('utf-8')
        return self._segment_file

    @segment_file.setter
    def segment_file(self, val):
        self._segment_file = val
    
    @property
    def uvs(self):
        if self._uvs is None:
            uvCount = self.properties.vertexCount
            buf = (c_float * 2 * uvCount)()
            NifFile.nifly.getUVs(
                    self.file._handle, self._handle, buf, uvCount * 2, 0)
            self._uvs = [(uv[0], uv[1]) for uv in buf]
        return self._uvs

    @property
    def shader_block_name(self):
        buf = create_string_buffer(128)
        NifFile.nifly.getBlockname(self.file._handle, self.properties.shaderPropertyID, buf, 128)
        return buf.value.decode('utf-8')

    @property
    def shaderflags1(self):
        return NifFile.nifly.getShaderFlags1(self.file._handle, self._handle)

    @shaderflags1.setter
    def shaderflags1(self, val):
        NifFile.nifly.setShaderFlags(self.file._handle, self._handle, val);

    @property
    def textures(self):
        return self.shader.textures

    def set_texture(self, slot:str, texturepath):
        """Set texture in the named slot to the given string."""
        self.shader.set_texture(slot, texturepath)
    
    @property
    def shader(self):
        """
        Returns a NiShaderBuf-like object associated with the shape. For Skyrim, this is
        the shader block; for FO4 it's the materials file associated with the shape's
        shader.
        """
        if self._shader is None:
            if self.file.game == 'FO4':
                self._shader = NiShaderFO4(
                    file=self.file, id=self.properties.shaderPropertyID, parent=self)
            else:
                self._shader = NiShader(
                    file=self.file, id=self.properties.shaderPropertyID, parent=self)

        return self._shader

    def save_shader_attributes(self):
        """
        Write out the shader attributes. FO4 files will have the shader properties written
        to the nif, not to a separate materials file.
        """
        if self._shader and self._shader._properties:
            name = self.shader.name
            if name is None: name = ''
            shader_id = NifFile.nifly.addBlock(
                self.file._handle, 
                self._shader.name.encode('utf-8'), 
                byref(self._shader._properties), 
                self.id)
            self._shader.id = shader_id
            self.properties.shaderPropertyID = shader_id

    @property
    def has_alpha_property(self):
        return self.alpha_property != None
    
    @has_alpha_property.setter
    def has_alpha_property(self, val):
        if val and not self._alpha:
            self._alpha = NiAlphaProperty(file=self.file, parent=self)
    
    @property
    def alpha_property(self):
        if self._alpha is None and self.properties.alphaPropertyID != NODEID_NONE:
            self._alpha = NiAlphaProperty(
                file=self.file, id=self.properties.alphaPropertyID, parent=self)
        return self._alpha

    def save_alpha_property(self):
        if self._alpha:
            alpha_id = NifFile.nifly.addBlock(
                self.file._handle, None, 
                byref(self._alpha.properties), self.id)
            self._alpha.id = alpha_id
            self.properties.alphaPropertyID = alpha_id

    @property
    def bone_names(self):
        """ List of bone names in the shape """
        if self._bone_names is None:
            bufsize = 300
            buf = create_string_buffer(bufsize+1)
            actualsize = NifFile.nifly.getShapeBoneNames(self.file._handle, self._handle, buf, bufsize)
            if actualsize > bufsize:
                buf = create_string_buffer(actualsize+1)
                NifFile.nifly.getShapeBoneNames(self.file._handle, self._handle, buf, actualsize+1)
            bn = buf.value.decode('utf-8').split('\n')
            self._bone_names = list(filter((lambda n: len(n) > 0), bn))
        return self._bone_names
        
    @property
    def bone_ids(self):
        if self._bone_ids is None:
            id_count = NifFile.nifly.getShapeBoneCount(self.file._handle, self._handle)
            BUFDEF = c_int * id_count
            buf = BUFDEF()
            NifFile.nifly.getShapeBoneIDs(self.file._handle, self._handle, buf, id_count)
            self._bone_ids = list(buf)
        return self._bone_ids

    def _bone_weights(self, bone_id):
        # Weights for all vertices (that are weighted to it)
        BUFSIZE = NifFile.nifly.getShapeBoneWeightsCount(self.file._handle, self._handle, bone_id)
        BUFDEF = VERTEX_WEIGHT_PAIR * BUFSIZE
        buf = BUFDEF()
        NifFile.nifly.getShapeBoneWeights(self.file._handle, self._handle,
                                          bone_id, buf, BUFSIZE)
        out = [(x.vertex, x.weight) for x in buf]
        return out

    @property
    def bone_weights(self):
        """ Dictionary of bone weights
            returns {bone-name: [(vertex-index, weight), ...], ...}
            """
        if self._weights is None:
            self._weights = {}
            for bone_idx, name in enumerate(self.bone_names):
                self._weights[name] = self._bone_weights(bone_idx)
        return self._weights

    def get_used_bones(self):
        """
        Return bones that have non-zero weights
        NOTE not really filtering out non-zero weights rn
        """
        return list(self.bone_weights.keys())

    @property
    def has_skin_instance(self):
        """ Determine whether this mash has a NiSkinData block.
            WARNING CURRENTLY BROKEN 
            """
        return NifFile.nifly.hasSkinInstance(self._handle)

    @property
    def has_global_to_skin(self):
        """Determine whether the shape has the global-to-skin transform."""
        buf = TransformBuf()
        return NifFile.nifly.getShapeGlobalToSkin(self.file._handle, self._handle, buf)
    
    def calc_global_to_skin(self):
        """Calculate the global-to-skin transform (whether or not it exists)."""
        buf = TransformBuf()
        NifFile.nifly.calcShapeGlobalToSkin(self.file._handle, self._handle, buf)
        return buf
    
    @property
    def global_to_skin(self):
        """Return the global-to-skin transform on this shape; calculate it if not
        present. Calculated by averaging the skin-to-bone (pose) transforms on all the
        bones. 
        """
        buf = TransformBuf()
        has_xform = NifFile.nifly.getShapeGlobalToSkin(self.file._handle, self._handle, buf)
        if not has_xform:
            NifFile.nifly.calcShapeGlobalToSkin(self.file._handle, self._handle, buf)
        return buf

    def get_shape_skin_to_bone(self, bone_name):
        """ Return the skin-to-bone transform, getting it from the nif data """
        buf = TransformBuf()
        xform_found = NifFile.nifly.getShapeSkinToBone(self.file._handle, 
                                                       self._handle, 
                                                       bone_name.encode('utf-8'),
                                                       buf)
        if xform_found:
            return buf
        else:
            return None

    def set_skin_to_bone_xform(self, bone_name, xform: TransformBuf):
        """Set the skin-to-bone transform on the shape's skin, using the skin."""
        NifFile.nifly.setShapeSkinToBone(self.file._handle, 
                                         self._handle,
                                         bone_name.encode('utf-8'),
                                         xform)


    # #############  Creating shapes #############

    def skin(self):
        NifFile.nifly.skinShape(self.file._handle, self._handle)
        self._is_skinned = True

    def set_global_to_skin(self, transform):
        """ Sets the skin transform which offsets the vert locations. This allows a head
            to have verts around the origin but to be positioned properly when skinned.
            Works whether or not there is a SkinInstance block
            """
        if not self._is_skinned:
            self.skin()
        NifFile.nifly.setShapeGlobalToSkin(self.file._handle, self._handle, transform)

    def add_bone(self, bone_name, xform=None, parent_name=None):
        """Add bone to shape. This resets all the shape's bone information, so 
        skin-to-bone transforms and bone weights will need to be reset.
        Add all bones first, then set transforms and weights.
        """
        if not self._is_skinned:
            self.skin()
        if xform:
            buf = xform
        else:
            buf = TransformBuf() 
            buf.set_identity()
        
        par = None
        if parent_name:
            par = parent_name.encode('utf-8')
        
        h = NifFile.nifly.addBoneToNifShape(self.file._handle, self._handle, 
                                            bone_name.encode('utf-8'), buf,
                                            par)
        NiNode(handle=h, file=self.file, name=bone_name)

        
    def setShapeWeights(self, bone_name, vert_weights):
        """ Set the weights for a bone in a shape. 
        """
        VERT_BUF_DEF = VERTEX_WEIGHT_PAIR * len(vert_weights)
        vert_buf = VERT_BUF_DEF()
        for i, vw in enumerate(vert_weights):
            vert_buf[i].vertex = vw[0]
            vert_buf[i].weight = vw[1]
        xfbuf = TransformBuf()

        NifFile.nifly.setShapeBoneWeights(self.file._handle, self._handle, 
                                      bone_name.encode('utf-8'),
                                      vert_buf, len(vert_weights))
       
    def set_partitions(self, partitionlist, trilist):
        """ Set the partitions for a shape
            partitionlist = list of Partition objects, either Skyrim or FO. Any Subsegments in the
                list are ignored. Subsegments are found separately under Partitions.
            trilist = 1:1 with shape tris, gives the ID of the tri's partition
            """
        if len(partitionlist) == 0:
            return
        
        # In FO4, create a clean list of segments covering subsegments in partitionlist.
        # In Skyrim, just use the partitionlist as given.
        if self.file.game == 'FO4':
            pdict = {}
            maxid = max([p.id for p in partitionlist])
            for p in partitionlist:
                if type(p).__name__ == "FO4Subsegment":
                    seg_new = p.parent
                elif type(p).__name__ == "FO4Segment":
                    seg_new = p
                if not seg_new.name in pdict:
                    pdict[seg_new.name] = seg_new
                # All prior segments must also be included
                for i in range(0, seg_new.index):
                    if not f"FO4 Seg {i:03d}" in pdict:
                        maxid += 1
                        pdict[f"FO4 Seg {i:03d}"] = FO4Segment(part_id=maxid, index=i)
            parts = list(pdict.values())
            parts.sort(key=lambda x: x.index)
        else:
            parts = list(filter(
                lambda x: type(x).__name__ == "SkyPartition", 
                partitionlist))

        if len(parts) == 0:
            return

        parts_lookup = {}
        
        tbuf = (c_uint16 * len(trilist))()

        if self.file.game in ['SKYRIM', 'SKYRIMSE']:
            # the trilist passed in refers to partition IDs, but nifly wants indices into
            # the given partition list.
            pbuf = (c_uint16 * 2 * len(parts))()
            for i, p in enumerate(parts):
                pbuf[i][0] = 0
                pbuf[i][1] = p.id 
                parts_lookup[p.id] = i

            for i, t in enumerate(trilist):
                try:
                    tbuf[i] = parts_lookup[trilist[i]]
                except:
                    # Report the error unless the id is 0--that means we couldn't assign the 
                    # partition and that error has already been reported
                    if not trilist[i] == 0:
                        if i < len(trilist):
                            log.error(f"Tri at index {i} assigned partition id {trilist[i]}, but no such partition defined")
                            log.error(f"Partitions are {parts_lookup.items()}")
                        else:
                            log.error(f"Tri at index {i} assigned partition, but only {len(trilist)} tris defined")
                    tbuf[i] = pbuf[0][1] # Export with the first partition so we get something out

            NifFile.nifly.setPartitions(self.file._handle, self._handle,
                                        pbuf, len(parts),
                                        tbuf, len(trilist))
        else:
            # For segments, the trilist has to refer to IDs becuase of referring to subsegments.
            pbuf = (c_uint16 * len(parts))()
            for i, p in enumerate(parts):
                pbuf[i] = p.id 
                parts_lookup[p.id] = i

            for i, t in enumerate(trilist): 
                tbuf[i] = trilist[i]

            sslist = []
            for seg in parts:
                for sseg in seg.subsegments:
                    sslist.extend([sseg.id, seg.id, sseg.user_slot, sseg.material])
            sbuf = (c_uint32 * len(sslist))()
            for i, s in enumerate(sslist):
                sbuf[i] = s

            NifFile.nifly.setSegments(self.file._handle, self._handle,
                                      pbuf, len(parts),
                                      sbuf, int(len(sslist)/4),
                                      tbuf, len(trilist),
                                      self._segment_file.encode('utf-8'))

    def set_colors(self, colors):
        buf = (c_float * 4 * len(colors))()
        for i, c in enumerate(colors):
            buf[i][0] = c[0]
            buf[i][1] = c[1]
            buf[i][2] = c[2]
            buf[i][3] = c[3]
        NifFile.nifly.setColorsForShape(self.file._handle, self._handle, 
                                        buf, len(colors))


# --- NiTriShape --- #
class NiTriShape(NiShape):
    buffer_type = PynBufferTypes.NiTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiTriShapeBuf(values)
    
class BSSegmentedTriShape(NiTriShape):
    pass

class NiScreenElements(NiTriShape):
    pass
    

# --- BSTriShape --- #
class BSTriShape(NiShape):
    buffer_type = PynBufferTypes.BSTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        b = BSTriShapeBuf(values)
        b.bufType = PynBufferTypes.BSTriShapeBufType
        return b


# --- BSDynamicTriShape --- #
class BSDynamicTriShape(NiShape):
    buffer_type = PynBufferTypes.BSDynamicTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        b = BSDynamicTriShapeBuf(values)
        b.bufType = PynBufferTypes.BSDynamicTriShapeBufType
        return b


# --- BSSubIndexTriShape --- #
class BSSubIndexTriShape(NiShape):
    buffer_type = PynBufferTypes.BSSubIndexTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        b = BSSubIndexTriShapeBuf(values)
        b.bufType = PynBufferTypes.BSSubIndexTriShapeBufType
        return b


# --- NiTriStrips --- #
class NiTriStrips(NiShape):
    buffer_type = PynBufferTypes.NiTriStripsBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiTriStripsBuf(values)


# --- BSMeshLODTriShape --- #
class BSMeshLODTriShape(NiShape):
    buffer_type = PynBufferTypes.BSMeshLODTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSMeshLODTriShapeBuf(values)


# --- BSLODTriShape --- #
class BSLODTriShape(NiShape):
    buffer_type = PynBufferTypes.BSLODTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSLODTriShapeBuf(values)


# --- NifFile --- #
class NifFile:
    """ NifFile represents the file itself. Corresponds approximately to a NifFile in the 
        Nifly layer, but we've hidden the AnimInfo object in here too.
        """
    nifly = None
    log = logging.getLogger("pynifly")

    def Load(nifly_path):
        NifFile.nifly = load_nifly(nifly_path)
        NifFile.nifly_path = nifly_path
    
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
        if not filepath is None:
            self._handle = NifFile.nifly.load(filepath.encode('utf-8'))
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
        self._load_shapes()

    def __del__(self):
        if self._handle:
            NifFile.nifly.destroy(self._handle)

    @property
    def max_string_len(self):
        """Length of buffer required for the longest string stored in the nif + one for
        the trailing null byte. Return at least 128 because reasons.
        """
        if self._handle:
            return max(128, NifFile.nifly.getMaxStringLen(self._handle)+1)
        else:
            return 128
        
    @property
    def reference_skel(self):
        if self._ref_skel:
            return self._ref_skel

        # We don't actually know which skeleton to use. Assume the basic human skeleton.
        g = "SKYRIM" if self._game == "SKYRIMSE" else self._game
        if g:
            skel_path = os.path.join(os.path.dirname(NifFile.nifly_path), "Skeletons", g, "skeleton.nif")
            if os.path.exists(skel_path):
                self._ref_skel = NifFile(skel_path)
                return self._ref_skel

        return None


    def initialize(self, target_game, filepath, root_type="NiNode", root_name='Scene Root'):
        self.filepath = filepath
        self._game = target_game
        rt = 0
        self._handle = NifFile.nifly.createNif(target_game.encode('utf-8'),
                                               root_type.encode('utf-8'),
                                               root_name.encode('utf-8'))
        self.dict = gameSkeletons[target_game]
        # Get the root node into the nodes list so it can be found.
        self.read_node(0)


    def save(self):
        for sh in self.shapes:
            sh._setShapeXform()

        if self._skin_handle:
            NifFile.nifly.saveSkinnedNif(self._skin_handle, self.filepath.encode('utf-8'))
        else:
            NifFile.nifly.saveNif(self._handle, self.filepath.encode('utf-8'))


    def get_string(self, string_id):
        buflen = self.max_string_len
        buf = (c_char * buflen)()
        NifFile.nifly.getString(self._handle, string_id, buflen, buf)
        return buf.value.decode('utf-8')


    def add_block(self, name, buf, parent=None):
        """
        Add a block defined by the given buffer to the nif file, with error-checking.
        Returns the new object created.
        """
        NifFile.clear_log()
        id = NifFile.nifly.addBlock(
            self._handle, 
            (name.encode('utf-8') if name else None), 
            byref(buf), 
            parent.id if parent else NODEID_NONE)
        if id == NODEID_NONE:
            raise Exception(f"Could not create node {buf.bufType}/{NiObject._buftype_name(buf.bufType)}, error: {NifFile.message_log()}")
        cls = NiObject.buffer_types[buf.bufType]
        blk = cls(file=self, id=id, properties=buf, parent=parent)
        return blk


    def add_node(self, name, xform, parent=None):
        """Add NiNode object to the file."""
        phandle = None
        if parent:
            if type(parent) == str:
                phandle = NifFile.nifly.findNodeByName(self._handle, parent.encode('utf-8'))
            else:
                phandle = parent._handle
        nodeh = NifFile.nifly.addNode(self._handle, name.encode('utf-8'), xform, phandle)
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
        for i, u in enumerate(uvs): uvbuf[i] = (u[0], 1-u[1])

        shape_handle = NifFile.nifly.createNifShapeFromData(
            self._handle, 
            shape_name.encode('utf-8'), 
            byref(shapebuf),
            vertbuf, uvbuf, normbuf, 
            tribuf, 
            parenthandle)
        
        if self._shapes is None:
            self._shapes = []
        sh = NiShape(handle=shape_handle, file=self, parent=parent)
        sh.name = shape_name
        sh._partitions = []
        self._shapes.append(sh)
        sh._handle = shape_handle

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
            buf = create_string_buffer(50)
            NifFile.nifly.getGameName(self._handle, buf, 50)
            self._game = buf.value.decode('utf-8')
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
        NifFile.nifly.getAllShapeNames(self._handle, buf, 300)
        return buf.value.decode('utf-8').split('\n')

    @property
    def shape_dict(self):
        self.shapes
        return self._shape_dict

    def _load_shapes(self):
        self._shapes = []
        self._shape_dict = {}
        if self._handle:
            nfound = NifFile.nifly.getShapes(self._handle, None, 0, 0)
            PTRBUF = c_void_p * nfound
            buf = PTRBUF()
            nfound = NifFile.nifly.getShapes(self._handle, buf, nfound, 0)
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
        if n.id == 0: self._root = n

    @property
    def nodes(self):
        """Dictionary of nodes in the nif, indexed by node name"""
        if self._nodes is None:
            self._nodes = {}
            nodeCount = NifFile.nifly.getNodeCount(self._handle)
            PTRBUF = c_void_p * nodeCount
            buf = PTRBUF()
            NifFile.nifly.getNodes(self._handle, buf)
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
            if NifFile.nifly.getNodeTransformToGlobal(self._handle, name.encode('utf-8'), buf):
                return buf
        else:
            return self.nodes[name].global_transform.copy()

        if self.reference_skel:
            NifFile.nifly.getNodeTransformToGlobal(self.reference_skel._handle, 
                                                   name.encode('utf-8'), 
                                                   buf)
        return buf


    @property
    def cloth_data(self):
        if self._clothdata is None:
            self._clothdata = _read_extra_data(self._handle, 
                                               None,
                                               ExtraDataType.Cloth)
        return self._clothdata

    @cloth_data.setter
    def cloth_data(self, val):
        self._clothdata = val
        _write_extra_data(self._handle, None, 
                         ExtraDataType.Cloth, self._clothdata)

    @property
    def behavior_graph_data(self):
        if self._bgdata is None:
            self._bgdata = _read_extra_data(self._handle, None,
                                           ExtraDataType.BehaviorGraph)
        return self._bgdata

    @behavior_graph_data.setter
    def behavior_graph_data(self, val):
        self._bgdata = val
        _write_extra_data(self._handle, None, 
                         ExtraDataType.BehaviorGraph, self._bgdata)

    @property
    def string_data(self):
        if self._strdata is None:
            self._strdata = _read_extra_data(self._handle, None,
                                           ExtraDataType.String)
        return self._strdata

    @string_data.setter
    def string_data(self, val):
        self._strdata = val
        _write_extra_data(self._handle, None, 
                         ExtraDataType.String, self._strdata)

    @property
    def furniture_markers(self):
        if not self._furniture_markers:
            self._furniture_markers = []
            if self._handle:
                for i in range(0, 100):
                    buf = FurnitureMarkerBuf()
                    if not NifFile.nifly.getFurnMarker(self._handle, i, buf):
                        break
                    self._furniture_markers.append(buf)
        return self._furniture_markers

    @furniture_markers.setter
    def furniture_markers(self, value):
        bufs = (FurnitureMarkerBuf * len(value))()
        for i, v in enumerate(value):
            bufs[i] = v
        NifFile.nifly.setFurnMarkers(self._handle, len(value), bufs)


    @property
    def connect_points_parent(self):
        """Reads a nif's parent connect points as a list of ConnectPointBuf
        Name and parent name limited to 256 characters
        """
        if not self._connect_pt_par:
            self._connect_pt_par = []
            if self._handle and isinstance(self.rootNode, NiNode):
                for i in range(0, 100):
                    buf = ConnectPointBuf()
                    if not NifFile.nifly.getConnectPointParent(self._handle, i, buf):
                        break
                    self._connect_pt_par.append(buf)
        return self._connect_pt_par

    @connect_points_parent.setter
    def connect_points_parent(self, value):
        bufs = (ConnectPointBuf * len(value))()
        for i, v in enumerate(value):
            bufs[i] = v
        NifFile.nifly.setConnectPointsParent(self._handle, len(value), bufs)

    @property
    def connect_points_child(self):
        """Reads a nif's child connect point names as [name, name, ...]
        where bool = skinned/not skinned
        name = child connect point names, limited to 256 characters"""
        if not self._connect_pt_child:
            self._connect_pt_child = []
            if self._handle and isinstance(self.rootNode, NiNode):
                for i in range(0, 100):
                    buf = (c_char * 256)() 
                    is_skinned = c_char()
                    v = NifFile.nifly.getConnectPointChild(self._handle, i, buf)
                    if v == 0:
                        break
                    self.connect_pt_child_skinned = (v > 0)
                    self._connect_pt_child.append(buf.value.decode('utf-8'))
        return self._connect_pt_child

    @connect_points_child.setter
    def connect_points_child(self, value):
        buf = create_string_buffer(('\0'.join(value)).encode())
        NifFile.nifly.setConnectPointsChild(self._handle, self.connect_pt_child_skinned, len(buf), buf)


    @property
    def controller_managers(self):
        cm_count = NifFile.nifly.findNodesByType(self._handle, self.root, 
                                                 "NiControllerManager".encode('utf-8'), 
                                                 0, None)
        cmrefs = (c_void_p * cm_count)()
        NifFile.nifly.findNodesByType(self._handle, self.root, 
                                      "NiControllerManager".encode('utf-8'), 
                                      cm_count, cmrefs)
        v = []
        for i in range(0, cm_count):
            v.append(NiControllerManager(
                file=self, handle=cmrefs[i], parent=self.root))
        return v

    @staticmethod
    def clear_log():
        if NifFile.nifly:
            NifFile.nifly.clearMessageLog()

    @staticmethod
    def message_log():
        msgsize = NifFile.nifly.getMessageLog(None, 0)+2
        buf = create_string_buffer(msgsize)
        NifFile.nifly.getMessageLog(buf, msgsize)
        return buf.value.decode('utf-8')

    def read_node(self, id=None, handle=None, properties=None, parent=None):
        """
        Return a node object for the given node ID. The node might be anything, so use the
        block name to determine what kind of object to create. 
        """
        if id is None:
            id = NifFile.nifly.getBlockID(self._handle, handle)
        if id in self.node_ids:
            return self.node_ids[id]

        buf = (c_char * (128))()
        NifFile.nifly.getBlockname(self._handle, id, buf, 128)
        bn = buf.value.decode('utf-8')
        if bn in NiObject.block_types:
            node = NiObject.block_types[bn](
                id=id, file=self, handle=handle, properties=properties, parent=parent)
            self.node_ids[id] = node
            try:
                if hasattr(node, 'name') and node.name and isinstance(node, NiNode): 
                    self._nodes[node.name] = node
            except:
                pass
            return node
        else:
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

        collshape_index = NifFile.nifly.addBlock(
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

            NifFile.nifly.setCollConvexVerts(
                self._handle, collshape_index,
                vertbuf, len(vertices), normbuf, len(normals))
        
        return new_collshape


class hkxSkeletonFile(NifFile):
    """
    Represents a hkx skeleton file. Extends and replaces NifFile's functionality to
    read a XML file instead of a nif. 
    """

    def __init__(self, filepath=None):
        super().__init__(filepath=None)
        self.filepath = filepath
        self.xmlfile = None
        self.xmlroot = None
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
        if self.xmlroot:
            # Prevent recursive call from NiNode().
            return
        
        if os.path.splitext(self.filepath)[1].upper() == ".HKX":
            self.xml_filepath = xmltools.XMLFile.hkx_to_xml(self.filepath)
        else:
            self.xml_filepath = self.filepath
    
        self.xmlfile = xml.parse(self.xml_filepath)
        self.xmlroot = self.xmlfile.getroot()

        self._root = NiNode(file=self, name=os.path.basename(self.xml_filepath))
        self._root.id = 0
        self._root._blockname = "BSFadeNode"
        self._root.properties.transform.set_identity()
        self.register_node(self._root)

        skel = self.xmlroot.find(".//*[@class='hkaSkeleton']")
        skelname = skel.find("./*[@name='name']").text
        parentIndices = [int(x) for x in skel.find("./*[@name='parentIndices']").text.split()]

        bonelist = []
        skelbones = skel.find("./*[@name='bones']")
        for b in skelbones.iter('hkobject'):
            bonelist.append(b.find("./*[@name='name']").text)

        pose = skel.find("./*[@name='referencePose']")
        poselist = pose.text.strip(' ()\t\n').split(')')

        mxWorld = [None] * len(bonelist)
        i = j = 0
        while i < len(poselist) and j < len(bonelist):
            parent = None
            parentname = None
            if parentIndices[j] >= 0:
                parentname = bonelist[parentIndices[j]]
                if parentname in self.nodes:
                    parent = self.nodes[parentname]

            loc = rot = None
            loclist = poselist[i].strip(' ()\t\n').split()
            if len(loclist) == 3:
                loc = [float(x) for x in loclist]
            else:
                self.warn(f"Pose list does not have translation at index {j}: {poselist[i]}")

            rotlist = poselist[i+1].strip(' ()\t\n').split()
            if len(rotlist) == 4:
                # Note this quaternion may not be normalized
                rot = quaternion_to_matrix(
                    [float(rotlist[3]), float(rotlist[0]), float(rotlist[1]), float(rotlist[2])])
            else:
                self.warn(f"Pose list does not have good rotation at index {j}: {poselist[i+1]}")

            scalelist = poselist[i+2].strip(' ()\t\n').split()
            if len(scalelist) == 3:
                scale = [float(x) for x in scalelist]
            else:
                self.warn(f"Pose list does not have good scale at index {j}: {poselist[i+2]}")
            
            if loc and rot and scale:
                buf = NiNodeBuf()
                buf.transform.translation = VECTOR3(*loc)
                buf.transform.rotation = MATRIX3(VECTOR3(*rot[0]), VECTOR3(*rot[1]), VECTOR3(*rot[2]))
                buf.transform.scale = scale[0]
                n = NiNode(file=self, parent=parent, 
                           properties=buf, name=bonelist[j])
                n.id = j+1
                n._blockname = "NiNode"
                self.register_node(n)

            i += 3
            j += 1
        
        
    @property
    def nodes(self):
        """Overwrites "nodes" property to get them from the XML file, not a nif file."""
        if self._nodes is None:
            self._nodes = {}
            self.load_from_file()
        return self._nodes

NiObject.register_subclasses()