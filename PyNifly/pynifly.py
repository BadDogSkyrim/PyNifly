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


def load_nifly(nifly_path):
    nifly = cdll.LoadLibrary(nifly_path)
    nifly.addAnimKeyLinearTrans.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyLinearTransBuf)]
    nifly.addAnimKeyLinearTrans.restype = None
    nifly.addAnimKeyLinearQuat.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyLinearQuatBuf)]
    nifly.addAnimKeyLinearQuat.restype = None
    nifly.addAnimKeyQuadFloat.argtypes = [c_void_p, c_int, POINTER(NiAnimKeyFloatBuf)]
    nifly.addAnimKeyQuadFloat.restype = None
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
    nifly.getAnimKeyLinearXYZ.argtypes = [c_void_p, c_int, c_char, c_int, POINTER(NiAnimKeyLinearXYZBuf)]
    nifly.getAnimKeyLinearXYZ.restype = None
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
    # nifly.getCollConvexTransformShapeChildID.argtypes = [c_void_p, c_int]
    # nifly.getCollConvexTransformShapeChildID.restype = c_int
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

# These are the types of blocks we can create from an ID. Eventaully should probably
# be all of them. This could be done with reflection but we're keeping things simple.
block_types = {}


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
        #log.debug(f"New FO4 segment: {part_id}, {subsegments}, {name}")
        super().__init__(part_id, namedict=namedict, name=name)
        self._index = index
        self.subseg_count = subsegments
        self.subsegments = []

    @property
    def name(self):
        """ FO4 segments don't have proper names. Build a fake name from the ID
            """
        if self._name:
            return self._name
        else:
            return f"FO4 Seg " + '{:0>3d}'.format(self._index)

    @classmethod
    def name_match(cls, name):
        #bp = fo4Dict.bodypart(name)
        #if bp:
        #    return 1
        
        m = FO4Segment.fo4segmatch1.match(name)
        if m:
            return int(m.group(1))

        m = FO4Segment.fo4segmatch.match(name)
        if m:
            return int(m.group(1))
        else:
            return -1

class FO4Subsegment(FO4Segment):
    #fo4subsegm = re.compile('((\AFO4 \w+ [0-9]+) \| [\w\-\d\. ]+)')
    fo4subsegm1 = re.compile(r'(FO4 Seg [0-9]+) \| ([^\|]+)( \| (.+))?\Z')
    fo4subsegm = re.compile('\AFO4 *.*')
    fo4bpm = re.compile('\AFO4 *(\d+) - ')

    def __init__(self, part_id, user_slot, material, parent, namedict=fo4Dict, name=None):
        """ 
        part_id = unique id used inside the nif
        user_slot = user index 
        material = bone ID
        parent = parent segment
        namedict = dictionary to use
        name = name for the subsegment. If not provided, will be constructed.
        """
        #log.debug(f"New subsegment: {part_id}, {user_slot}, {material}")
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
        #bp = fo4Dict.bodypart(name)
        #if bp:
        #    return bp.parentname, bp.id, bp.material

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
    @classmethod
    def _getbuf(cls, values=None):
        """To be overwritten by subclasses."""
        assert False, "_getbuf should have been overwritten."    

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        self._handle = handle
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
    
    # def __getattr__(self, name):
    #     """Any attribute not on the object comes from the properties."""
    #     if name == '_properties': return None
    #     return self.properties.__getattribute__(name)
    
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
            self._properties = self._getbuf()
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

# --- Collisions --- #

class CollisionShape(NiObject):

    @classmethod
    def New(cls, collisiontype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        if properties:
            collisiontype = bufferTypeList[properties.bufType]
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

class CollisionBoxShape(CollisionShape):
    needsTransform = True

    @classmethod
    def _getbuf(cls, values=None):
        return bhkBoxShapeProps(values)
    
block_types['bhkBoxShape'] = CollisionBoxShape

class CollisionCapsuleShape(CollisionShape):
    needsTransform = False

    @classmethod
    def _getbuf(cls, values=None):
        return bhkCapsuleShapeProps(values)

block_types['bhkCapsuleShape'] = CollisionCapsuleShape

class CollisionSphereShape(CollisionShape):
    needsTransform = False

    @classmethod
    def _getbuf(cls, values=None):
        return bhkSphereShapeBuf(values)

block_types['bhkSphereShape'] = CollisionSphereShape

class CollisionConvexVerticesShape(CollisionShape):
    needsTransform = False

    @classmethod
    def _getbuf(cls, values=None):
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

block_types['bhkConvexVerticesShape'] = CollisionConvexVerticesShape


class CollisionListShape(CollisionShape):
    needsTransform = False

    @classmethod
    def _getbuf(cls, values=None):
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
                    self._children.append(CollisionShape.New(
                        id=idx, file=self.file, parent=self))
        
        return self._children

    def add_child(self, childnode):
        NifFile.nifly.addCollListChild(
            self.file._handle, self.id, childnode.id)

    def add_shape(self, childprops, transform=None):
        child = CollisionShape.New(file=self.file, properties=childprops, parent=self)
        if not self._children:
            self._children = []
        self._children.append(child)
        # NifFile.nifly.addCollListChild(
        #     self.file._handle, self.id, child.id)
        return child

block_types['bhkListShape'] = CollisionListShape


class CollisionConvexTransformShape(CollisionShape):
    needsTransform = False
    
    @classmethod
    def _getbuf(cls, values=None):
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
        child = CollisionShape.New(file=self.file, properties=childprops, parent=self)
        self._child = child
        self.properties.shapeID = child.id
        # NifFile.nifly.addCollListChild(
        #     self.file._handle, self.id, child.id)
        return child

    @property
    def child(self):
        if self._child: return self._child

        # ch = NifFile.nifly.getCollConvexTransformShapeChildID(self.file._handle, self.id)
        self._child = CollisionShape.New(id=self.properties.shapeID, file=self.file, parent=self)
        return self._child

    @child.setter
    def child(self, value):
        NifFile.nifly.setCollConvexTransformShapeChild(self.file._handle,
                                                       self.id,
                                                       value.id)

block_types['bhkConvexTransformShape'] = CollisionConvexTransformShape


class bhkConstraint(NiObject):
    @classmethod
    def _getbuf(cls, values=None):
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
    def _getbuf(cls, values=None):
        assert False, "bhkWorldObject should never be instantiated directly."

    @classmethod
    def get_buffer(cls, bodytype, values=None):
        return block_types[bodytype]._getbuf(values=values)

    @classmethod
    def New(cls, objtype=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        if properties:
            objtype = bufferTypeList[properties.bufType]
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
        # except:
        #     return None

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
            # shape_index = NifFile.nifly.getRigidBodyShapeID(self._file._handle, self.block_index)
            self._shape = CollisionShape.New(
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

    @classmethod
    def _getbuf(cls, values=None):
        return bhkRigidBodyProps(values)

block_types['bhkRigidBody'] = bhkRigidBody


class bhkRigidBodyT(bhkRigidBody):

    @classmethod
    def _getbuf(cls, values=None):
        buf = bhkRigidBodyProps(values)
        buf.bufType = PynBufferTypes.bhkRigidBodyTBufType
        return buf

block_types['bhkRigidBodyT'] = bhkRigidBodyT


class bhkSimpleShapePhantom(bhkWorldObject):

    @classmethod
    def _getbuf(cls, values=None):
        return bhkSimpleShapePhantomBuf(values)

block_types['bhkSimpleShapePhantom'] = bhkSimpleShapePhantom


class CollisionObject(NiObject):
    """Represents various collision objects."""

    @classmethod
    def _getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)

    @classmethod
    def New(cls, 
            collisiontype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        if properties:
            collisiontype = bufferTypeList[properties.bufType]
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
        # return NifFile.nifly.getCollFlags(self._handle)

    @property
    def target(self):
        """ Return the node that is the target of the collision object """
        targ = NifFile.nifly.getCollTarget(self.file._handle, self._handle)
        return self.file.nodeByHandle(targ)

    @property
    def body(self):
        """ Return the collision body object """
        if not self._body:
            # body_prop = bhkRigidBodyProps()
            # NifFile.nifly.getBlock(self.file._handle, self.properties.bodyID, byref(body_prop))
            if self.properties.bodyID != NODEID_NONE:
                self._body = bhkWorldObject.New(id=self.properties.bodyID, file=self.file, parent=self)
        return self._body

    # def add_rigid_body(self, blocktype, properties, collshape):
    def add_body(self, properties):
        """ Create a rigid body for this collision object """
        # rb_index = NifFile.nifly.addRigidBody(self._handle, blocktype.encode('utf-8'), collshape.block_index, properties)
        rb_index = NifFile.nifly.addBlock(
            self.file._handle, None, byref(properties), self.id)
        self._body = bhkWorldObject(id=rb_index, file=self.file, parent=self, properties=properties)
        return self._body

block_types['bhkCollisionObject'] = CollisionObject


class bhkNiCollisionObject(CollisionObject):
    @classmethod
    def _getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)

block_types['bhkNiCollisionObject'] = CollisionObject


class bhkPCollisionObject(bhkNiCollisionObject):
    @classmethod
    def _getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)

block_types['bhkPCollisionObject'] = bhkPCollisionObject


class bhkSPCollisionObject(CollisionObject):
    @classmethod
    def _getbuf(cls, values=None):
        return bhkSPCollisionObjectBuf(values)

block_types['bhkSPCollisionObject'] = bhkSPCollisionObject


class bhkBlendCollisionObject(CollisionObject):
    @classmethod
    def _getbuf(cls, values=None):
        return bhkBlendCollisionObjectBuf(values)

block_types['bhkBlendCollisionObject'] = bhkBlendCollisionObject


class NiAVObject(NiObject):
    def add_collision(self, body, flags=None):
        # targhandle = None
        # if target:
        #     targhandle = target._handle
        # new_coll_hndl = NifFile.nifly.addCollision(self._handle, targhandle, 
        #                                            body.block_index, flags)
        buf = bhkCollisionObjectBuf()
        if flags is not None: buf.flags = flags
        buf.bodyID = NODEID_NONE
        if body: buf.bodyID = body.id
        buf.targetID = self.id
        new_coll_id = NifFile.nifly.addBlock(self.file._handle, None, byref(buf), self.id)
        new_coll = CollisionObject(file=self.file, 
                                   id=new_coll_id, 
                                   properties=buf, 
                                   parent=self)
        return new_coll
    

# --- NiNode --- #

class NiNode(NiAVObject):
    @classmethod
    def _getbuf(cls, values=None):
        return NiNodeBuf(values)
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None, 
                 properties=None, name=""):
        super().__init__(handle=handle, file=file, id=id, parent=parent, 
                         properties=properties)
        self._name = name
        self._controller = None
        self._bgdata = None
        self._strdata = None
        self._clothdata = None
        self._clothdata = None
        
        if self._handle:
            # NifFile.nifly.getBlock(self.file._handle, 
            #                        self.id, 
            #                        byref(self._properties))
            self.properties
            buflen = self.file.max_string_len
            buf = create_string_buffer(buflen)
            NifFile.nifly.getNodeName(self._handle, buf, buflen)
            self._name = buf.value.decode('utf-8')

        if self._name:
            self.file.nodes[self._name] = self

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        self._name = value
        if self.file: self.file.register_node(self)
        
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
        # n = NifFile.nifly.getCollision(self.file._handle, self._handle)
        # if n:
        if self.properties.collisionID != NODEID_NONE:
            return CollisionObject.New(id=self.properties.collisionID, file=self.file, parent=self)
        else:
            return None

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

            # namebuf = (c_char * 128)()
            # rotbuf = (c_int * 3)();
            # zoombuf = (c_float * 1)();
            # if NifFile.nifly.getInvMarker(self._handle, namebuf, 128, rotbuf, zoombuf):
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

block_types["NiNode"] = NiNode
block_types["BSFadeNode"] = NiNode
block_types["BSLeafAnimNode"] = NiNode


class NiKeyFrameData(NiObject):
    pass


class LinearScalarKey:
    def __init__(self, buf:NiAnimKeyLinearXYZBuf):
        self.time = buf.time
        self.value = buf.value

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)
    
    def __str__(self): 
        return f"<LinearScalarKey>(time={self.time}, value={self.value:f})"

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
    def __init__(self, buf:NiAnimKeyFloatBuf):
        self.time = buf.time
        self.value = buf.value
        self.forward = buf.forward
        self.backward = buf.backward

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value) \
            and VNearEqual(self.forward, other.forward) \
            and VNearEqual(self.backward, other.backward) 

    def __str__(self): 
        return f"<QuadScalarKey>(time={self.time}, value={self.value[:]}, forward={self.forward[:]}, backward={self.backward[:]})"

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
                self._writequadkeys(keys)
            self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
            if parent: parent.data = self
        # elif self.id != NODEID_NONE:
        #     if self.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY:
        #         self._readquadkeys()

    def _writequadkeys(self, keys):
        """
        Write quadratic float keys.
        keys = list of QuadScalarKey 
        """
        buf = NiAnimKeyFloatBuf();
        for k in keys:
            buf.time = k.time
            buf.value = k.value
            buf.forward = k.forward
            buf.backward = k.backward
            NifFile.nifly.addAnimKeyQuadFloat(self.file._handle, self.id, buf)

    @property
    def keys(self):
        NifFile.clear_log()
        if self.id == NODEID_NONE: return None
        if self.properties.keys.interpolation != NiKeyType.QUADRATIC_KEY:
            return None
        keys = []
        for frame in range(0, self.properties.keys.numKeys):
            buf = NiAnimKeyFloatBuf()
            if NifFile.nifly.getAnimKeyQuadFloat(self.file._handle, self.id, frame, buf) != 0:
                raise Exception(f"Error reading NiFloatDataKey: {NifFile.message_log()}")            
            k = QuadScalarKey(buf)
            keys.append(k)
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
    def _getbuf(cls, values=None):
        return NiFloatDataBuf(values)
        
block_types["NiFloatData"] = NiFloatData


class NiPosData(NiObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None, keys=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._keys = None
        # # self.keys = keys
        # self._blockname = "NiFloatData"
        # if self._handle == None and self.id == NODEID_NONE:
        #     self.id = NifFile.nifly.addBlock(
        #         self.file._handle, 
        #         None, 
        #         byref(self.properties), 
        #         parent.id if parent else NODEID_NONE)
        #     if keys:
        #         self._writequadkeys(keys)
        #     self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
        #     if parent: parent.data = self
        # # elif self.id != NODEID_NONE:
        # #     if self.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY:
        # #         self._readquadkeys()

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

    def keys_add(self, t, v, f, b):
        """
        Write one key.
        """
        buf = NiAnimKeyQuadTransBuf()
        buf.time = t
        buf.value = v
        buf.forward = f[:]
        buf.backward = b[:]
        NifFile.nifly.addAnimKeyQuadTrans(self.file._handle, self.id, buf)

    @classmethod
    def _getbuf(cls, values=None):
        return NiPosDataBuf(values)
        
block_types["NiPosData"] = NiPosData


class NiTransformData(NiKeyFrameData):
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
    def _getbuf(cls, values=None):
        return NiTransformDataBuf(values)
    
    @classmethod 
    def New(cls, file, 
            rotation_type=NiKeyType.LINEAR_KEY, 
            xyz_rotation_types=(NiKeyType.QUADRATIC_KEY, )*3,
            translate_type=NiKeyType.LINEAR_KEY,
            scale_type=NiKeyType.LINEAR_KEY,
            parent=None):
        p:NiTransformDataBuf = NiTransformDataBuf()
        p.rotationType = rotation_type
        p.translations.interpolation = translate_type
        p.xRotations.interpolation = xyz_rotation_types[0]
        p.yRotations.interpolation = xyz_rotation_types[1]
        p.zRotations.interpolation = xyz_rotation_types[2]
        p.scales.interpolation = scale_type
        id = NifFile.nifly.addBlock(
            file._handle, 
            None, 
            byref(p), 
            parent.id if parent else NODEID_NONE)
        td = NiTransformData(file=file, id=id, properties=p, parent=parent)
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
            buf = NiAnimKeyLinearXYZBuf()
            NifFile.nifly.getAnimKeyLinearXYZ(self.file._handle, self.id, dimension, frame, buf)
            k = LinearScalarKey(buf)
        return k
    
    def add_translation_key(self, time, loc):
        """Add a key that does a translation. Keys must be added in time order."""
        buf = NiAnimKeyLinearTransBuf()
        buf.time = time
        buf.value = loc[:]
        NifFile.nifly.addAnimKeyLinearTrans(self.file._handle, self.id, buf)

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
                    self.file._handle, self.id, d, byref(q))

block_types["NiTransformData"] = NiTransformData


class NiInterpolator(NiObject):
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
    

class NiKeyBasedInterpolator(NiInterpolator):
    pass


class NiTransformInterpolator(NiKeyBasedInterpolator):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        # if self._handle == None and self.id == NODEID_NONE:
        #     self.id = NifFile.nifly.addBlock(
        #         self.file._handle, 
        #         None, 
        #         byref(self.properties), 
        #         parent.id if parent else NODEID_NONE)
        #     self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
        self._data = None
        
    @classmethod
    def _getbuf(cls, values=None):
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
        id = NifFile.nifly.addBlock(
            file._handle, 
            None, 
            byref(p), 
            parent.id if parent else NODEID_NONE)
        ti = NiTransformInterpolator(file=file, id=id, properties=p, parent=parent)
        return ti
    
block_types["NiTransformInterpolator"] = NiTransformInterpolator


class NiFloatInterpolator(NiKeyBasedInterpolator):
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
    def _getbuf(cls, values=None):
        return NiFloatInterpolatorBuf(values)

block_types["NiFloatInterpolator"] = NiFloatInterpolator


class NiPoint3Interpolator(NiKeyBasedInterpolator):

    @classmethod
    def _getbuf(cls, values=None):
        return NiPoint3InterpolatorBuf(values)

block_types["NiPoint3Interpolator"] = NiPoint3Interpolator
    

class NiBlendInterpolator(NiObject):
    """Abstract class"""
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
    def _getbuf(cls, values=None):
        return NiBlendInterpolatorBuf(values)
    

class NiBlendBoolInterpolator(NiBlendInterpolator):
    @property
    def value(self):
        return self.properties.boolValue
    
block_types["NiBlendBoolInterpolator"] = NiBlendBoolInterpolator

    
class NiBlendFloatInterpolator(NiBlendInterpolator):
    @property
    def value(self):
        return self.properties.floatValue
    
block_types["NiBlendFloatInterpolator"] = NiBlendFloatInterpolator

    
class NiBlendPoint3Interpolator(NiBlendInterpolator):
    @property
    def value(self):
        return self.properties.point3Value[:]
    
block_types["NiBlendPoint3Interpolator"] = NiBlendPoint3Interpolator

    
class NiBlendTransformInterpolator(NiBlendInterpolator):
    @property
    def value(self):
        return None
    
block_types["NiBlendTransformInterpolator"] = NiBlendTransformInterpolator

    
class NiTimeController(NiObject):
    """
    Abstract class for time controllers. Keeping the chain of subclasses below because
    we'll likely need them eventually.
    """
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = None
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
    
    def _default_import_func(ctlr, importer, nifnode):
        importer.warn(f"NYI: Import of controller {ctlr.id} {ctlr}")
    
    import_node = _default_import_func


class NiInterpController(NiTimeController):
    pass


class NiSingleInterpController(NiInterpController):
    def __init__(self, 
                 handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(
            handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._interpolator = None
        
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
    

class NiKeyframeController(NiSingleInterpController):
    pass


class NiTransformController(NiKeyframeController):
    def __init__(self, 
                 handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(
            handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = None
        self._properties = NiTransformControllerBuf()
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(self._properties))

block_types["NiTransformController"] = NiTransformController


class NiMultiTargetTransformController(NiInterpController):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._properties = NiMultiTargetTransformControllerBuf()
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(self._properties))
        # NifFile.nifly.getMultiTargetTransformController(
        #     self.file._handle, self.id, self.properties)

    @classmethod
    def _getbuf(cls, values=None):
        return NiMultiTargetTransformControllerBuf(values)
    
    @classmethod
    def New(cls, file, flags, target, parent=None):
        p = NiMultiTargetTransformControllerBuf()
        p.flags = flags
        p.targetID = target.id
        id = NifFile.nifly.addBlock(
            file._handle, 
            None, 
            byref(p), 
            parent.id if parent else NODEID_NONE)
        tc = NiMultiTargetTransformController(
            file=file, id=id, properties=p, parent=parent)
        return tc

block_types["NiMultiTargetTransformController"] = NiMultiTargetTransformController


class NiFloatInterpController(NiSingleInterpController):
    pass


class BSEffectShaderPropertyFloatController(NiFloatInterpController):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if self.id == NODEID_NONE and file and properties: 
            self.id = NifFile.nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def _getbuf(cls, values=None):
        return BSEffectShaderPropertyFloatControllerBuf(values)

block_types["BSEffectShaderPropertyFloatController"] = BSEffectShaderPropertyFloatController


class BSLightingShaderPropertyColorController(NiFloatInterpController):
    @classmethod
    def _getbuf(cls, values=None):
        return BSLightingShaderPropertyColorControllerBuf(values)

    @classmethod
    def New(cls, file, flags, target, 
            color_type=LightingShaderControlledColor.SPECULAR, 
            parent=None):
        p = BSLightingShaderPropertyColorControllerBuf()
        p.flags = flags
        p.targetID = target.id
        p.typeOfControlledColor = color_type
        id = NifFile.nifly.addBlock(
            file._handle, 
            None, 
            byref(p), 
            parent.id if parent else NODEID_NONE)
        tc = BSLightingShaderPropertyColorController(
            file=file, id=id, properties=p, parent=parent)
        return tc

block_types["BSLightingShaderPropertyColorController"] = BSLightingShaderPropertyColorController


class BSEffectShaderPropertyFloatController(NiFloatInterpController):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if self.id == NODEID_NONE and file and properties: 
            self.id = NifFile.nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def _getbuf(cls, values=None):
        return BSEffectShaderPropertyFloatControllerBuf(values)

block_types["BSEffectShaderPropertyFloatController"] = BSEffectShaderPropertyFloatController


class BSLightingShaderPropertyFloatController(NiFloatInterpController):
    @classmethod
    def _getbuf(cls, values=None):
        return BSLightingShaderPropertyFloatControllerBuf(values)

    @classmethod
    def New(cls, file, flags, target, 
            color_type=LightingShaderControlledFloat.Emissive_Multiple, 
            parent=None):
        p = BSLightingShaderPropertyFloatControllerBuf()
        p.flags = flags
        p.targetID = target.id
        p.typeOfControlledColor = color_type
        id = NifFile.nifly.addBlock(
            file._handle, 
            None, 
            byref(p), 
            parent.id if parent else NODEID_NONE)
        tc = BSLightingShaderPropertyFloatController(
            file=file, id=id, properties=p, parent=parent)
        return tc

block_types["BSLightingShaderPropertyFloatController"] = BSLightingShaderPropertyFloatController


class NiAlphaController(NiFloatInterpController):
    pass


class BSNiAlphaPropertyTestRefController(NiAlphaController):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = None

    @property
    def target(self):
        if self._target: return self._target
        if self.properties.targetID == NODEID_NONE: return None
        self._target = self.file.read_node(id=self.properties.targetID)
        return self._target

    @classmethod
    def _getbuf(cls, values=None):
        return BSNiAlphaPropertyTestRefControllerBuf(values)

block_types["BSNiAlphaPropertyTestRefController"] = BSNiAlphaPropertyTestRefController


class ControllerLink:

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
        # NifFile.nifly.getControlledBlocks(
        #     self.file._handle, self.id, self.properties.controlledBlocksCount, buf)
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
                             prop_type=None,
                             controller_type=None,
                             ctrlr_id=None,
                             interpolator_id=None):
        buf = ControllerLinkBuf()
        buf.interpolatorID = interpolator.id if interpolator else NODEID_NONE
        buf.controllerID = controller.id if controller else NODEID_NONE
        buf.priority = priority
        buf.nodeName = NODEID_NONE
        if node_name: 
            buf.nodeName = NifFile.nifly.addString(
                self.file._handle, node_name.encode('utf-8'))
        
        buf.propType = NODEID_NONE
        if prop_type: 
            buf.propType = NifFile.nifly.addString(
                self.file._handle, prop_type.encode('utf-8'))
        buf.ctrlType = NODEID_NONE
        if controller_type: 
            buf.ctrlType = NifFile.nifly.addString(
                self.file._handle, controller_type.encode('utf-8'))
        buf.ctrlID = NODEID_NONE
        if ctrlr_id: 
            buf.ctrlID = NifFile.nifly.addString(
                self.file._handle, ctrlr_id.encode('utf-8'))
        buf.interpID = NODEID_NONE
        if interpolator_id: 
            buf.interpID = NifFile.nifly.addString(
                self.file._handle, interpolator_id.encode('utf-8'))
        
        # NifFile.nifly.addControlledBlock(self.file._handle, self.id, name.encode('utf-8'), buf)
        NifFile.nifly.addBlock(self.file._handle, name.encode('utf-8'), byref(buf), self.id)
        if self._controlled_blocks is None: self._controlled_blocks = []
        self._controlled_blocks.append(ControllerLink(buf, self))

    def _default_import_func(self, importer):
        importer.warn(f"NYI: Import of NiSequence {self.id} {self.name}")
    
    import_node = _default_import_func
    



class NiTextKeyExtraData(NiObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._keys = None

    @classmethod 
    def _getbuf(cls, values=None):
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
        parentid = parent.id if parent else NODEID_NONE
        id = NifFile.nifly.addBlock(
            file._handle, name.encode('utf-8'), byref(p), parentid)
        if id != NODEID_NONE:
            tk = NiTextKeyExtraData(file=file, id=id, properties=p, parent=parent)
            for t, v in keys:
                tk.add_key(t, v)
            return tk
        else:
            raise Exception("Could not create NiTextKeyExtraData")

block_types["NiTextKeyExtraData"] = NiTextKeyExtraData
    

class NiControllerSequence(NiSequence):
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
    def _getbuf(cls, values=None):
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

        id = NifFile.nifly.addBlock(file._handle, 
                                    name.encode('utf-8'), 
                                    byref(p), 
                                    parent.id if parent else None)
        
        if id != NODEID_NONE:
            cs = NiControllerSequence(file=file, id=id, parent=parent, properties=p)
            cs._name = name
            if parent: parent.add_sequence(cs)
            return cs

block_types["NiControllerSequence"] = NiControllerSequence


class NiControllerManager(NiTimeController):

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
    def _getbuf(cls, values=None):
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
        id = NifFile.nifly.addBlock(file._handle, None, byref(p), p.targetID)
        if id != NODEID_NONE:
            cm = NiControllerManager(file=file, id=id, properties=p, parent=parent)
            cm._controller_manager_sequences = {}
            return cm
        else:
            raise Exception("Could not create NiControllerManager")
        
block_types["NiControllerManager"] = NiControllerManager


class NiDefaultAVObjectPalette(NiObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._objects = None

    @classmethod 
    def _getbuf(cls, values=None):
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
        NifFile.nifly.addAVObjectPaletteObject(
            self.file._handle,
            self.id,
            objname.encode('utf8'),
            obj.id
        )
    
    @classmethod
    def New(cls, file, scene=None, objects={}, parent=None):
        p = NiDefaultAVObjectPaletteBuf()
        p.sceneID = scene.id if scene else NODEID_NONE
        parentid = parent.id if parent else NODEID_NONE
        id = NifFile.nifly.addBlock(file._handle, None, byref(p), parentid)
        if id != NODEID_NONE:
            objp = NiDefaultAVObjectPalette(file=file, id=id, properties=p, parent=parent)
            for name, obj in objects.items():
                objp.add_object(name, obj)
            return objp
        else:
            raise Exception("Could not create NiControllerManager")

block_types["NiDefaultAVObjectPalette"] = NiDefaultAVObjectPalette


# --- Shaders -- #

class NiAlphaProperty(NiObject):
    @classmethod
    def _getbuf(cls, values=None):
        return AlphaPropertyBuf(values)

    @property
    def parent(self):
        if not self._parent:
            for sh in self.file.shapes:
                if sh.properties.alphaPropertyID == self.id:
                    self._parent = sh
                    break 
        return self._parent

block_types["NiAlphaProperty"] = NiAlphaProperty


class NiShader(NiObject):
    """
    Handles shader attributes for a Nif. In Skyrim, returns values from the underlying
    shader block. In FO4, most attributes come from the associated materials file.
    """
    @classmethod
    def _getbuf(cls, values=None):
        return NiShaderBuf(values)

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        
        self._name = None
        self._textures = None
        self._controller = None

    @property
    def name(self):
        if self._name == None:
            namebuf = (c_char * self.file.max_string_len)()
            NifFile.nifly.getString(
                self.file._handle, self.properties.nameID, self.file.max_string_len, namebuf)
            self._name = namebuf.value.decode('utf-8')
        return self._name
    
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

                if self.flags2_test(ShaderFlags2.GLOW_MAP):
                    self._textures["Glow"] = self._readtexture(f, s, 3)

                if self.flags2_test(ShaderFlags2.RIM_LIGHTING):
                    self._textures["RimLighting"] = self._readtexture(f, s, 3)

                if self.flags2_test(ShaderFlags2.SOFT_LIGHTING):
                    self._textures["SoftLighting"] = self._readtexture(f, s, 3)

                if self.flags2_test(ShaderFlags1.PARALLAX):
                    self._textures["HeightMap"] = self._readtexture(f, s, 4)

                if self.flags1_test(ShaderFlags1.GREYSCALE_COLOR):
                    self._textures["Greyscale"] = self._readtexture(f, s, 4)

                if self.flags1_test(ShaderFlags1.ENVIRONMENT_MAPPING) \
                    or self.flags2_test(ShaderFlags2.ENVMAP_LIGHT_FADE):
                    self._textures["EnvMap"] = self._readtexture(f, s, 5)

                if self.flags1_test(ShaderFlags1.ENVIRONMENT_MAPPING):
                    self._textures["EnvMask"] = self._readtexture(f, s, 6)

                if self.flags2_test(ShaderFlags2.MULTI_LAYER_PARALLAX):
                    self._textures["InnerLayer"] = self._readtexture(f, s, 7)

                if (self.flags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)
                    or self.flags1_test(ShaderFlags1.SPECULAR)):
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
            if slot == 'InnerLayer':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 6, texturepath.encode('utf-8'))
            if slot == 'Specular':
                NifFile.nifly.setShaderTextureSlot(
                    self.file._handle, self._parent._handle, 7, texturepath.encode('utf-8'))
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
    
    def flags1_test(self, flag):
        return self.properties.shaderflags1_test(flag)
    
    def flags1_set(self, flag):
        self.properties.shaderflags1_set(flag)
    
    def flags1_clear(self, flag):
        self.properties.shaderflags1_clear(flag)
    
    def flags2_test(self, flag):
        return self.properties.shaderflags2_test(flag)
        
    def flags2_set(self, flag):
        self.properties.shaderflags2_set(flag)
    
    def flags2_clear(self, flag):
        self.properties.shaderflags2_clear(flag)
    
block_types["BSLightingShaderProperty"] = NiShader
block_types["BSEffectShaderProperty"] = NiShader
block_types["BSShaderPPLightingProperty"] = NiShader


class NiShaderFO4(NiShader):
    """
    Shader for FO4 nifs. Alters NiShader behavior to get values from the materials file
    when necessary.
    """
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        
        self.materials = None
        if self.name:
            # Some FO4 nifs don't have materials files. Apparently (?) they use the shader
            # block attributes.
            # fullpath = extend_filenames(self.file.materialsRoot, 'meshes', [self.name])[0]
            fullpath = self.name
            if not os.path.exists(fullpath):
                # Target full path doesn't exist. Make it relative to our materials root.
                relpath = truncate_filename(self.name, 'materials')
                fullpath = os.path.join(self.file.materialsRoot, self.name)
            self.materials = bgsmaterial.MaterialFile.Open(fullpath)

    @property
    def textures(self):
        if self.materials:
            return self.materials.textures
        else:
            return super().textures

    @property
    def shaderflags1(self):
        if self.materials:
            v = self.properties.Shader_Flags_1
            v &= ~ShaderFlags1.DECAL | (
                ShaderFlags1.DECAL if self.materials.decal else 0)
            v &= ~ShaderFlags1.ENVIRONMENT_MAPPING | (
                ShaderFlags1.ENVIRONMENT_MAPPING if self.materials.environmentMapping else 0)
            v &= ~ShaderFlags1.ZBUFFER_TEST | (
                ShaderFlags1.ZBUFFER_TEST if self.materials.zbuffertest else 0)
            if self.materials.signature == b'BGSM':
                v &= ~ShaderFlags1.CAST_SHADOWS | (
                    ShaderFlags1.CAST_SHADOWS if self.materials.castShadows else 0)
                v &= ~ShaderFlags1.EXTERNAL_EMITTANCE | (
                    ShaderFlags1.EXTERNAL_EMITTANCE if self.materials.externalEmittance else 0)
                v &= ~ShaderFlags1.EYE_ENVIRONMENT_MAPPING | (
                    ShaderFlags1.EYE_ENVIRONMENT_MAPPING if self.materials.environmentMappingEye else 0)
                v &= ~ShaderFlags1.HAIR_SOFT_LIGHTING | (
                    ShaderFlags1.HAIR_SOFT_LIGHTING if self.materials.hair else 0)
                v &= ~ShaderFlags1.OWN_EMIT | (
                    ShaderFlags1.OWN_EMIT if self.materials.emitEnabled else 0)
                v &= ~ShaderFlags1.MODEL_SPACE_NORMALS | (
                    ShaderFlags1.MODEL_SPACE_NORMALS if self.materials.modelSpaceNormals else 0)
                v &= ~ShaderFlags1.RECEIVE_SHADOWS | (
                    ShaderFlags1.RECEIVE_SHADOWS if self.materials.receiveShadows else 0)
                v &= ~ShaderFlags1.SPECULAR | (
                    ShaderFlags1.SPECULAR if self.materials.specularEnabled else 0)
            if self.materials.signature == b'BGEM':
                v &= ~ShaderFlags1.USE_FALLOFF | (
                    ShaderFlags1.USE_FALLOFF if self.materials.falloffEnabled else 0)
            return v
        else:
            return self.properties.Shader_Flags_1
        
    @property
    def shaderflags2(self):
        """
        Return shader flags. Get flags held in the materials file from there, if any; get
        the rest from the shader flags in the nif.
        """
        v = self.properties.Shader_Flags_2
        if self.materials:
            v &= ~ShaderFlags2.DOUBLE_SIDED | (
                ShaderFlags2.DOUBLE_SIDED if self.materials.twoSided else 0)
            v &= ~ShaderFlags2.GLOW_MAP | (
                ShaderFlags2.GLOW_MAP if self.materials.glowmap else 0)
            v &= ~ShaderFlags2.ZBUFFER_WRITE | (
                ShaderFlags2.ZBUFFER_WRITE if self.materials.zbufferwrite else 0)
            if self.materials.signature == b'BGSM':
                v &= ~ShaderFlags2.ANISOTROPIC_LIGHTING | (
                    ShaderFlags2.ANISOTROPIC_LIGHTING if self.materials.anisoLighting else 0)
                v &= ~ShaderFlags2.ASSUME_SHADOWMASK | (
                    ShaderFlags2.ASSUME_SHADOWMASK if self.materials.assumeShadowmask else 0)
                v &= ~ShaderFlags2.BACK_LIGHTING | (
                    ShaderFlags2.BACK_LIGHTING if self.materials.backLighting else 0)
                v &= ~ShaderFlags2.RIM_LIGHTING | (
                    ShaderFlags2.RIM_LIGHTING if self.materials.rimLighting else 0)
                v &= ~ShaderFlags2.SOFT_LIGHTING | (
                    ShaderFlags2.SOFT_LIGHTING if self.materials.subsurfaceLighting else 0)
                v &= ~ShaderFlags2.TREE_ANIM | (
                    ShaderFlags2.TREE_ANIM if self.materials.tree else 0)
            if self.materials.signature == b'BGEM':
                v &= ~ShaderFlags2.EFFECT_LIGHTING | (
                    ShaderFlags2.EFFECT_LIGHTING if self.materials.effectLightingEnabled else 0)
            return v
        else:
            return self.properties.Shader_Flags_2
        
    def flags1_test(self, flag):
        return (self.shaderflags1 & flag) != 0
    
    def flags2_test(self, flag):
        return (self.shaderflags2 & flag) != 0
    

# --- NifShape --- #
class NiShape(NiNode):

    # @classmethod
    # def load_subclasses(cls):
    #     if cls.subtypes: return 
    #     cls.subtypes = {}
    #     for subc in cls.__subclasses__():
    #         cls.subtypes[subc.__name__] = subc

    @classmethod
    def New(cls, handle=None, shapetype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        # cls.load_subclasses()
        if properties:
            shapetype = bufferTypeList[properties.bufType]
        if not shapetype:
            if id == NODEID_NONE:
                id = NifFile.nifly.getBlockID(file._handle, handle)
            buf = create_string_buffer(128)
            NifFile.nifly.getBlockname(file._handle, id, buf, 128)
            shapetype = buf.value.decode('utf-8')
        try:
            if not handle and id == NODEID_NONE:
                id = NifFile.nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            if not handle:
                handle = NifFile.nifly.getBlockByID(id)
            
            s = file.read_node(
                handle=handle, id=id, parent=parent, properties=properties)
            return s
        except:
            NifFile.log.warning(f"Shape type is not implemented: {shapetype}")
            return None

    @classmethod
    def _getbuf(cls, values=None):
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
        self._shader_name = None
        self._alpha = None

    def _setShapeXform(self):
        NifFile.nifly.setTransform(self._handle, self.transform)

    @property
    def verts(self):
        if not self._verts:
            # totalCount = NifFile.nifly.getVertsForShape(
            #     self.file._handle, self._handle, None, 0, 0)
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
            # norms = (c_float*3)()
            # totalCount = NifFile.nifly.getNormalsForShape(
            #     self.file._handle, self._handle, norms, 0, 0)
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
    def shader_name(self):
        if self._shader_name is None:
            buflen = self.file.max_string_len
            buf = (c_char * buflen)()
            NifFile.nifly.getString(self.file._handle, self.shader.properties.nameID, buflen, buf)
            # buflen = NifFile.nifly.getShaderName(self.file._handle, self._handle, buf, buflen)
            self._shader_name = buf.value.decode('utf-8')
        return self._shader_name

    @shader_name.setter
    def shader_name(self, val):
        self._shader_name = val
        # NifFile.nifly.setShaderName(self.file._handle, self._handle, val.encode('utf-8'))

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
        # NifFile.nifly.setShaderTextureSlot(self.file._handle, self._handle, 
        #                                    slot, str.encode('utf-8'))
    
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
            name = self.shader_name
            if name is None: name = ''
            shader_id = NifFile.nifly.addBlock(
                self.file._handle, 
                self._shader_name.encode('utf-8'), 
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
            NifFile.nifly.addBlock(self.file._handle, None, 
                                   byref(self._alpha.properties), self.id)

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

        parts = list(filter(lambda x: type(x).__name__ in ["SkyPartition", "FO4Segment"], partitionlist))
        if len(parts) == 0:
            return

        #NifFile.log.debug(f"....Exporting partitions {[(type(p), p.name) for p in parts]}, ssf '{self._segment_file}'")

        parts_lookup = {}
        
        tbuf = (c_uint16 * len(trilist))()

        if type(parts[0]).__name__ == "SkyPartition":
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
                #NifFile.log.debug(f"....Exporting '{seg.name}'")
                for sseg in seg.subsegments:
                    #NifFile.log.debug(f"....Exporting '{seg.name}' subseg '{sseg.name}': {sseg.id}, {sseg.user_slot}, {hex(sseg.material)}")
                    sslist.extend([sseg.id, seg.id, sseg.user_slot, sseg.material])
            sbuf = (c_uint32 * len(sslist))()
            for i, s in enumerate(sslist):
                sbuf[i] = s

            #NifFile.log.debug(f"....Partition IDs: {[x for x in pbuf]}")
            #NifFile.log.debug(f"....setSegments({len(parts)}, int({len(sslist)}/4), {len(trilist)}, {trilist[0:4]})")
            NifFile.nifly.setSegments(self.file._handle, self._handle,
                                      pbuf, len(parts),
                                      sbuf, int(len(sslist)/4),
                                      tbuf, len(trilist),
                                      self._segment_file.encode('utf-8'))
            #NifFile.log.debug(f"......setSegments successful")

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
    @classmethod
    def _getbuf(cls, values=None):
        return NiShapeBuf(values)
    
block_types["NiTriShape"] = NiTriShape
    

# --- BSTriShape --- #
class BSTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        b = NiShapeBuf(values)
        b.bufType = PynBufferTypes.BSTriShapeBufType
        return b

block_types["BSTriShape"] = BSTriShape


# --- BSDynamicTriShape --- #
class BSDynamicTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        b = NiShapeBuf(values)
        b.bufType = PynBufferTypes.BSDynamicTriShapeBufType
        return b

block_types["BSDynamicTriShape"] = BSDynamicTriShape


# --- BSSubIndexTriShape --- #
class BSSubIndexTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        b = NiShapeBuf(values)
        b.bufType = PynBufferTypes.BSSubIndexTriShapeBufType
        return b

block_types["BSSubIndexTriShape"] = BSSubIndexTriShape


# --- NiTriStrips --- #
class NiTriStrips(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        return NiShapeBuf(values)

block_types["NiTriStrips"] = NiTriStrips


# --- BSMeshLODTriShape --- #
class BSMeshLODTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        return BSMeshLODTriShapeBuf(values)

block_types["BSMeshLODTriShape"] = BSMeshLODTriShape


# --- BSLODTriShape --- #
class BSLODTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        return BSLODTriShapeBuf(values)

block_types["BSLODTriShape"] = BSLODTriShape


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
        # NiNode(handle=self.root, file=self, name=self.rootName)


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
                            #is_skinned=False, is_effectsshader=False,
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
        self._shapes.append(sh)
        sh._handle = shape_handle

        return sh

    @property
    def rootName(self):
        """Return name of root node"""
        return self.root.name
        # buf = create_string_buffer(256)
        # NifFile.nifly.getRootName(self._handle, buf, 256)
        # return buf.value.decode('utf-8')
    
    @property
    def root(self):
        """Return handle of root node."""
        if self._root is None:
            #self._root = NifFile.nifly.getRoot(self._handle)
            self._root = self.read_node(0)
        return self._root

    @property 
    def rootNode(self) -> NiNode:
        """Return the root node of the nif. 
        NOT TRUE: Note this causes all nodes to be loaded and nif.nodes to be filled.
        """
        #return self.read_node(0)
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
        # if not self._shapes_loaded:
        #     self._shapes = []
        #     self._shape_dict = {}
        #     if self._handle:
        #         nfound = NifFile.nifly.getShapes(self._handle, None, 0, 0)
        #         PTRBUF = c_void_p * nfound
        #         buf = PTRBUF()
        #         nfound = NifFile.nifly.getShapes(self._handle, buf, nfound, 0)
        #         for i in range(nfound):
        #             new_shape = NiShape.New(file=self, handle=buf[i])
        #             if new_shape:
        #                 self._shapes.append(new_shape) # not handling too many shapes yet
        #                 self._shape_dict[new_shape.name] = new_shape
        #     self._shapes_loaded = True
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
            if self._handle:
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
            if self._handle:
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
        if bn in block_types:
            node = block_types[bn](
                id=id, file=self, handle=handle, properties=properties, parent=parent)
            self.node_ids[id] = node
            try:
                if node.name: self._nodes[node.name] = node
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
        new_collshape = CollisionShape.New(
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
        if filepath: self.load_from_file()


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
        if os.path.splitext(self.filepath)[1].upper() == ".HKX":
            self.xml_filepath = xmltools.XMLFile.hkx_to_xml(self.filepath)
        else:
            self.xml_filepath = self.filepath
    
        self.xmlfile = xml.parse(self.xml_filepath)
        self.xmlroot = self.xmlfile.getroot()

        self._root = NiNode(file=self, name=os.path.basename(self.filepath))
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
