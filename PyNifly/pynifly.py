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
    nifly.getAnimKeyQuadTrans.argtypes = [c_void_p, c_int, c_int, POINTER(NiAnimKeyQuadTransBuf)]
    nifly.getAnimKeyQuadTrans.restype = None
    nifly.getAnimKeyQuadXYZ.argtypes = [c_void_p, c_int, c_char, c_int, POINTER(NiAnimKeyQuadXYZBuf)]
    nifly.getAnimKeyQuadXYZ.restype = None
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
        self.file = file
        self.id = id
        if handle is None and id != NODEID_NONE and file is not None:
            self._handle = NifFile.nifly.getNodeByID(file._handle, id)
        if self.id == NODEID_NONE and handle is not None and file is not None:
            self.id = NifFile.nifly.getBlockID(self.file._handle, self._handle)
        self._parent = parent
        self._properties = properties
        self._blockname = None
    
    def __getattr__(self, name):
        """Any attribute not on the object comes from the properties."""
        return self.properties.__getattribute__(name)
    
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
        if self._properties == None:
            self._properties = self._getbuf()
            if self.id != NODEID_NONE and self.file._handle:
                NifFile.nifly.getBlock(self.file._handle, 
                                       self.id, 
                                       byref(self._properties))
        return self._properties
    
    @properties.setter
    def properties(self, value):
        self._properties = value.copy()
        NifFile.nifly.setBlock(self.file._handle, self.id, byref(self._properties))


# --- Collisions --- #

class CollisionShape(NiObject):
    subtypes = {}

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
            return cls.subtypes[collisiontype](
                id=id, file=file, parent=parent, properties=properties)
        except:
            return None

class CollisionBoxShape(CollisionShape):
    needsTransform = True

    @classmethod
    def _getbuf(cls, values=None):
        return bhkBoxShapeProps(values)
    
CollisionShape.subtypes['bhkBoxShape'] = CollisionBoxShape

class CollisionCapsuleShape(CollisionShape):
    needsTransform = False

    @classmethod
    def _getbuf(cls, values=None):
        return bhkCapsuleShapeProps(values)

CollisionShape.subtypes['bhkCapsuleShape'] = CollisionCapsuleShape

class CollisionSphereShape(CollisionShape):
    needsTransform = False

    @classmethod
    def _getbuf(cls, values=None):
        return bhkSphereShapeBuf(values)

CollisionShape.subtypes['bhkSphereShape'] = CollisionSphereShape

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

CollisionShape.subtypes['bhkConvexVerticesShape'] = CollisionConvexVerticesShape


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

CollisionShape.subtypes['bhkListShape'] = CollisionListShape


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

CollisionShape.subtypes['bhkConvexTransformShape'] = CollisionConvexTransformShape


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
    subtypes = {}

    @classmethod
    def _getbuf(cls, values=None):
        assert False, "bhkWorldObject should never be instantiated directly."

    @classmethod
    def get_buffer(cls, bodytype, values=None):
        return cls.subtypes[bodytype]._getbuf(values=values)

    @classmethod
    def New(cls, objtype=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        if properties:
            objtype = bufferTypeList[properties.bufType]
        elif not objtype:
            buf = create_string_buffer(128)
            NifFile.nifly.getBlockname(file._handle, id, buf, 128)
            objtype = buf.value.decode('utf-8')
        try:
            if id == NODEID_NONE:
                id = NifFile.nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            return cls.subtypes[objtype](
                id=id, file=file, parent=parent, properties=properties)
        except:
            return None

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

bhkWorldObject.subtypes['bhkRigidBody'] = bhkRigidBody

class bhkRigidBodyT(bhkRigidBody):

    @classmethod
    def _getbuf(cls, values=None):
        buf = bhkRigidBodyProps(values)
        buf.bufType = PynBufferTypes.bhkRigidBodyTBufType
        return buf

bhkWorldObject.subtypes['bhkRigidBodyT'] = bhkRigidBodyT

class bhkSimpleShapePhantom(bhkWorldObject):

    @classmethod
    def _getbuf(cls, values=None):
        return bhkSimpleShapePhantomBuf(values)

bhkWorldObject.subtypes['bhkSimpleShapePhantom'] = bhkSimpleShapePhantom

class CollisionObject(NiObject):
    """Represents a bhkNiCollisionObject."""
    subtypes = {}

    @classmethod
    def _getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)

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
            if collisiontype in cls.subtypes:
                return cls.subtypes[collisiontype](
                    id=id, file=file, parent=parent, properties=properties)
            else:
                return CollisionObject(id=id, file=file, parent=parent, properties=properties)
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
    

class bhkBlendCollisionObject(CollisionObject):

    @classmethod
    def _getbuf(cls, values=None):
        return bhkBlendCollisionObjectBuf(values)

CollisionObject.subtypes['bhkBlendCollisionObject'] = bhkBlendCollisionObject


class NiAVObject(NiObject):
    def add_collision(self, body, flags):
        # targhandle = None
        # if target:
        #     targhandle = target._handle
        # new_coll_hndl = NifFile.nifly.addCollision(self._handle, targhandle, 
        #                                            body.block_index, flags)
        buf = bhkCollisionObjectBuf()
        buf.flags = flags
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
            NifFile.nifly.getBlock(self.file._handle, 
                                   self.id, 
                                   byref(self.properties))

            buflen = self.file.max_string_len
            buf = create_string_buffer(buflen)
            NifFile.nifly.getNodeName(self._handle, buf, buflen)
            self.name = buf.value.decode('utf-8')

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
        
        self._controller = self.file.read_node(node_id=self.properties.controllerID, parent=self)
        return self._controller

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
    def __init__(self, buf:NiAnimKeyQuadXYZBuf):
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


class NiTransformData(NiKeyFrameData):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, props=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=props, parent=parent)
        if self._handle == None and self.id == NODEID_NONE:
            self.id = NifFile.nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
        self._blockname = "NiTransformData"
        
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
            buf = NiAnimKeyQuadXYZBuf()
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
        """Add a key that does a rotation given as a quaternion, linear interpolation. 
        Keys must be added in time order."""
        buf = NiAnimKeyLinearQuatBuf()
        buf.time = time
        buf.value = q[:]
        NifFile.nifly.addAnimKeyLinearQuat(self.file._handle, self.id, buf)



class NiTransformInterpolator(NiObject):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, props=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=props, parent=parent)
        if self._handle == None and self.id == NODEID_NONE:
            self.id = NifFile.nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            self._handle = NifFile.nifly.getNodeByID(self.file._handle, self.id)
        self._data = None
        self._blockname = "NiTransformInterpolator"
        
    @classmethod
    def _getbuf(cls, values=None):
        return NiTransformInterpolatorBuf(values)
    
    @property
    def data(self):
        if self._data: return self._data

        self._data = NiTransformData(file=self.file, id=self.properties.dataID)
        return self._data

        
class NiTimeController(NiObject):
    """Abstract class for time controllers. Keeping the chain of subclasses below
    because we'll likely need them eventually.
    """
    @property 
    def next_controller(self):
        if self.properties.nextControllerID == NODEID_NONE:
            return None
        else:
            return self.file.read_node(self.properties.nextControllerID)


class NiInterpController(NiTimeController):
    pass


class NiSingleInterpController(NiInterpController):
    @property 
    def interpolator(self):
        if self.properties.interpolatorID == NODEID_NONE:
            return None
        else:
            return self.file.read_node(node_id=self.properties.interpolatorID,
                                       parent=self)


class NiKeyframeController(NiSingleInterpController):
    pass


class NiTransformController(NiKeyframeController):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None):
        super().__init__(handle=handle, file=file, id=id, parent=parent)
        self._properties = NiTransformControllerBuf()
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(self._properties))
        # NifFile.nifly.getTransformController(self.file._handle, self.id, self.properties)


class NiMultiTargetTransformController(NiInterpController):
    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None):
        super().__init__(handle=handle, file=file, id=id)
        self._properties = NiMultiTargetTransformControllerBuf()
        NifFile.nifly.getBlock(self.file._handle, self.id, byref(self._properties))
        # NifFile.nifly.getMultiTargetTransformController(
        #     self.file._handle, self.id, self.properties)
    

class ControllerLink:
    _nodename = None
    _controller_type = None
    _interpolator = None

    def __init__(self, props:ControllerLinkBuf, parent):
        self.properties = props.copy()
        self.parent = parent

    @property
    def node_name(self):
        if self._nodename: return self._nodename

        buflen = self.parent.file.max_string_len
        buf = (c_char * buflen)()
        NifFile.nifly.getString(self.parent.file._handle, 
                                self.properties.nodeName,
                                buflen, buf)
        self._nodename = buf.value.decode('utf-8')
        return self._nodename
    
    @property
    def controller_type(self):
        if self._controller_type: return self._controller_type

        buflen = self.parent.file.max_string_len
        buf = (c_char * buflen)()
        NifFile.nifly.getString(self.parent.file._handle, 
                                self.properties.ctrlType,
                                buflen, buf)
        self._controller_type = buf.value.decode('utf-8')
        return self._controller_type
    
    @property
    def interpolator(self):
        if self._interpolator: return self._interpolator
        self._interpolator = NiTransformInterpolator(
            file=self.parent.file, id=self.properties.interpolatorID
        )
        return self._interpolator


class NiSequence(NiObject):
    _name = None
    _controlled_blocks = None

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


class NiControllerSequence(NiSequence):
    @classmethod
    def _getbuf(cls, values=None):
        return NiControllerSequenceBuf(values)
    
    def __init__(self, handle=None, file=None, parent=None, id=NODEID_NONE):
        super().__init__(handle=handle, file=file, parent=parent, id=id)
        self._blockname = "NiControllerSequence"


class NiControllerManager(NiTimeController):
    _controller_manager_sequences = None

    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None):
        super().__init__(handle=handle, file=file, id=id, parent=parent)
        self._properties = NiControllerManagerBuf()
        NifFile.nifly.getBlock(self.file._handle, 
                               self.id, 
                               byref(self._properties))

    @property
    def sequences(self):
        if self._controller_manager_sequences:
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
    

# --- NiShader -- #
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

    @property
    def name(self):
        if self._name == None:
            namebuf = (c_char * self.file.max_string_len)()
            NifFile.nifly.getString(
                self.file._handle, self.nameID, self.file.max_string_len, namebuf)
            self._name = namebuf.value.decode('utf-8')
        return self._name

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

                if self.properties.shaderflags2_test(ShaderFlags2.RIM_LIGHTING):
                    self._textures["RimLighting"] = self._readtexture(f, s, 3)

                if self.properties.shaderflags2_test(ShaderFlags2.SOFT_LIGHTING):
                    self._textures["SoftLighting"] = self._readtexture(f, s, 3)

                if self.properties.shaderflags2_test(ShaderFlags1.PARALLAX):
                    self._textures["HeightMap"] = self._readtexture(f, s, 4)

                if self.properties.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING) \
                    or self.properties.shaderflags2_test(ShaderFlags2.ENVMAP_LIGHT_FADE):
                    self._textures["EnvMap"] = self._readtexture(f, s, 5)

                if self.properties.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING):
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
            self.materials = bgsmaterial.MaterialFile.Open(fullpath, logger=NifFile.log)

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
        
    def shaderflags1_test(self, flag):
        return (self.shaderflags1 & flag) != 0
    
    def shaderflags2_test(self, flag):
        return (self.shaderflags2 & flag) != 0
    

# --- NifShape --- #
class NiShape(NiNode):
    subtypes = None

    @classmethod
    def load_subclasses(cls):
        if cls.subtypes: return 
        cls.subtypes = {}
        for subc in cls.__subclasses__():
            cls.subtypes[subc.__name__] = subc

    @classmethod
    def New(cls, handle=None, shapetype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        cls.load_subclasses()
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
            
            return cls.subtypes[shapetype](
                handle=handle, id=id, file=file, parent=parent, properties=properties)
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
            NifFile.nifly.getString(self.file._handle, self.shader.nameID, buflen, buf)
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
                    file=self.file, id=self.shaderPropertyID, parent=self)
            else:
                self._shader = NiShader(
                    file=self.file, id=self.shaderPropertyID, parent=self)

        return self._shader

    def save_shader_attributes(self):
        """
        Write out the shader attributes. FO4 files will have the shader properties written
        to the nif, not to a separate materials file.
        """
        if self._shader and self._shader._properties:
            name = self.shader_name
            if name is None: name = ''
            NifFile.nifly.addBlock(self.file._handle, self._shader_name.encode('utf-8'), 
                                   byref(self._shader._properties), self.id)

    @property
    def has_alpha_property(self):
        return self.alpha_property != None
    
    @has_alpha_property.setter
    def has_alpha_property(self, val):
        if val and not self._alpha:
            self._alpha = AlphaPropertyBuf()
    
    @property
    def alpha_property(self):
        if self._alpha is None and self.properties.alphaPropertyID != NODEID_NONE:
            buf = AlphaPropertyBuf()
            NifFile.nifly.getBlock(self.file._handle, self.properties.alphaPropertyID, byref(buf))
            self._alpha = buf
        return self._alpha

    def save_alpha_property(self):
        if self._alpha:
            NifFile.nifly.addBlock(self.file._handle, None, 
                                   byref(self._alpha), self.id)

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
        #if self.file._skin_handle is None:
        #    self.file.createSkin()
        if not self._is_skinned:
            self.skin()
        NifFile.nifly.setShapeGlobalToSkin(self.file._handle, self._handle, transform)
        #NifFile.nifly.setGlobalToSkinXform(self.file._skin_handle, self._handle, transform)

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

    #def set_global_to_skindata(self, xform):
    #    """ Sets the NiSkinData transformation. Only call this on nifs that have them. """
    #    NifFile.nifly.setShapeGlobalToSkin(self.file._handle, self._handle, xform)
    #    #if self.file._skin_handle is None:
    #    #    self.file.createSkin()
    #    #if not self._is_skinned:
    #    #    self.skin()
    #    #NifFile.nifly.setShapeGlobalToSkinXform(self.file._skin_handle, self._handle, xform)
        
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
        #NifFile.nifly.setShapeWeights(self.file._skin_handle, self._handle, 
        #                              bone_name.encode('utf-8'),
        #                              vert_buf, len(vert_weights), xfbuf)
       
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
    

# --- BSTriShape --- #
class BSTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        b = NiShapeBuf(values)
        b.bufType = PynBufferTypes.BSTriShapeBufType
        return b
    

# --- BSDynamicTriShape --- #
class BSDynamicTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        b = NiShapeBuf(values)
        b.bufType = PynBufferTypes.BSDynamicTriShapeBufType
        return b
    

# --- BSSubIndexTriShape --- #
class BSSubIndexTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        b = NiShapeBuf(values)
        b.bufType = PynBufferTypes.BSSubIndexTriShapeBufType
        return b
    

# --- NiTriStrips --- #
class NiTriStrips(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        return NiShapeBuf(values)
    

# --- BSMeshLODTriShape --- #
class BSMeshLODTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
        return BSMeshLODTriShapeBuf(values)
    

# --- BSLODTriShape --- #
class BSLODTriShape(NiShape):
    @classmethod
    def _getbuf(cls, values=None):
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
        self._shapes = None
        self._shape_dict = {}
        self._nodes = None
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
        return self.read_node(0)
    
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
        return self.dict.blender_name(nif_name)

    def nif_name(self, blender_name):
        return self.dict.nif_name(blender_name)
    
    def getAllShapeNames(self):
        buf = create_string_buffer(300)
        NifFile.nifly.getAllShapeNames(self._handle, buf, 300)
        return buf.value.decode('utf-8').split('\n')

    @property
    def shape_dict(self):
        self.shapes
        return self._shape_dict

    @property
    def shapes(self):
        if self._shapes is None:
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
                this_node = NiNode(handle=h, file=self)
        return self._nodes

    def nodeByHandle(self, desired_handle):
        """ Returns the node with the given handle. If not found assumes it's a node that 
        doesn't appear in the nodes list and makes a NiNode for it. """
        for n in self.nodes.values():
            if n._handle == desired_handle:
                return n
        return NiNode(desired_handle, self)


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
        """Reads a nif's child connect points as a pair of [bool, (name, name, ...)]
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

    # These are the types of blocks we can create from an ID. Eventaully should probably
    # be all of them. This could be done with reflection but we're keeping things simple.
    block_types = {
        "NiNode": NiNode,
        "BSFadeNode": NiNode,
        "BSLeafAnimNode": NiNode,
        "NiMultiTargetTransformController": NiMultiTargetTransformController,
        "NiControllerSequence": NiControllerSequence,
        "NiTransformController": NiTransformController,
        "NiTransformInterpolator": NiTransformInterpolator,
        "NiControllerManager": NiControllerManager,
    }

    def read_node(self, node_id, parent=None):
        """Return a node object for the given node ID. The node might be anything,
        so use the block name to determine what kind of object to create. 
        """
        matches = [n for n in self.nodes.values() if n.id == node_id]
        if matches: return matches[0]

        buf = (c_char * (128))()
        NifFile.nifly.getBlockname(self._handle, node_id, buf, 128)
        bn = buf.value.decode('utf-8')
        if bn in NifFile.block_types:
            return NifFile.block_types[bn](id=node_id, file=self, parent=parent)
        else:
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

        n = NiNode(file=self, name=os.path.basename(self.filepath))
        n.id = 0
        n._blockname = "BSFadeNode"
        n.properties.transform.set_identity()
        self.register_node(n)

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

#
# ######################################## TESTS ########################################
#
#   As much of the import/export functionality as possible should be tested here.
#   Leave the tests in Blender to test Blender-specific functionality.
#
# ######################################## TESTS ########################################
#

class ModuleTest:
    """Quick and dirty test harness."""

    def __init__(self, logger):
        self.log = logger


    def test_file(relative_path):
        """
        Given a relative path, return a working filepath to the file. If it's in 
        the output directory, delete it.
        """
        rp = relative_path.upper()
        if "TESTS/OUT" in rp or r"TESTS\OUT" in rp:
            if os.path.exists(relative_path):
                os.remove(relative_path)
        return relative_path

    
    def export_shape(old_shape: NiShape, new_nif: NifFile):
        """ Convenience routine to copy existing shape """
        skinned = (len(old_shape.bone_weights) > 0)

        # Somehow the UV needs inversion. Probably a bug but we've lived with it so long...
        uv_inv = [(x, 1-y) for x, y in old_shape.uvs]

        # new_props = old_shape.properties.copy()
        # new_props.nameID = new_props.controllerID = new_props.skinInstanceID = NODEID_NONE
        # new_props.shaderPropertyID = new_props.alphaPropertyID = NODEID_NONE
        new_prop:NiShapeBuf = old_shape.properties.copy()
        new_prop.nameID = new_prop.conrollerID = new_prop.collisionID = NODEID_NONE
        new_prop.skinInstanceID = new_prop.shaderPropertyID = new_prop.alphaPropertyID = NODEID_NONE
        new_shape = new_nif.createShapeFromData(old_shape.name, 
                                                old_shape.verts,
                                                old_shape.tris,
                                                uv_inv,
                                                old_shape.normals,
                                                props=new_prop,
                                                use_type = old_shape.properties.bufType,
                                                )
        new_shape.transform = old_shape.transform.copy()
        oldxform = old_shape.global_to_skin
        if oldxform is None:
            oldxform = old_shape.transform
        new_shape_gts = oldxform # no inversion?
        if skinned: new_shape.set_global_to_skin(new_shape_gts)
        #if old_shape.parent.game in ("SKYRIM", "SKYRIMSE"):
        #    new_shape.set_global_to_skindata(new_shape_gts) # only for skyrim
        #else:
        #    new_shape.set_global_to_skin(new_shape_gts)

        for bone_name, weights in old_shape.bone_weights.items():
            new_shape.add_bone(bone_name, old_shape.file.nodes[bone_name].global_transform)

        for bone_name, weights in old_shape.bone_weights.items():
            sbx = old_shape.get_shape_skin_to_bone(bone_name)
            new_shape.set_skin_to_bone_xform(bone_name, sbx)

            new_shape.setShapeWeights(bone_name, weights)

        new_shape.shader_name = old_shape.shader_name
        new_shape.shader.properties.bufType = old_shape.shader.properties.bufType
        old_shape.shader.properties.copyto(new_shape.shader.properties)

        new_shape.save_shader_attributes()

        alpha = AlphaPropertyBuf()
        if old_shape.has_alpha_property:
            new_shape.has_alpha_property = True
            new_shape.alpha_property.flags = old_shape.alpha_property.flags
            new_shape.alpha_property.threshold = old_shape.alpha_property.threshold
            new_shape.save_alpha_property()

        # for i, t in enumerate(old_shape.textures):
        #     if len(t) > 0:
        #         new_shape.set_texture(i, t)
        for k, t in old_shape.textures.items():
            new_shape.set_texture(k, t)

        new_shape.behavior_graph_data = old_shape.behavior_graph_data
        new_shape.string_data = old_shape.string_data


    def TEST_NIFDEFS():
        """Test nifdefs functionality."""
        # Easier to do it here.

        # The different shape buffers initialize their ID values, but can also be set from
        # a dictionary object.
        b = NiShapeBuf({"flags": 24, "collisionID": 4})
        assert b.flags == 24, f"Flags are correct"
        assert b.collisionID == 4, f"collisionID is set"
        assert b.shaderPropertyID == NODEID_NONE, f"shaderPropertyID is not set"

        b = BSLODTriShapeBuf({"flags": 24, "collisionID": 4})
        assert b.flags == 24, f"Flags are correct"
        assert b.collisionID == 4, f"collisionID is set"
        assert b.shaderPropertyID == NODEID_NONE, f"shaderPropertyID is not set"

        b = blockBuffers['BSLODTriShape']({"flags": 24, "collisionID": 4})
        assert b.flags == 24, f"Flags are correct"
        assert b.collisionID == 4, f"collisionID is set"
        assert b.shaderPropertyID == NODEID_NONE, f"shaderPropertyID is not set"

        # Can read and store shader property values.
        # Regression: parallaxInnerLayerTextureScale gave problems
        b = NiShaderBuf({"Shader_Type": BSLSPShaderType.Face_Tint, 
                         "parallaxInnerLayerTextureScale": "[0.949999988079071, 0.949999988079071]"})
        assert b.Shader_Type == BSLSPShaderType.Face_Tint, f"Have correct face tint"
        assert VNearEqual(b.parallaxInnerLayerTextureScale[:], [0.95, 0.95]), "Have correct parallaxInnerLayerTextureScale"


    def TEST_SHAPE_QUERY():
        """NifFile object gives access to a nif"""

        # NifFile can be read from a file. It provides game name and root node for that game.
        f1 = NifFile("tests/skyrim/test.nif")
        assert f1.game == "SKYRIM", "'game' property gives the game the nif is good for"
        assert f1.rootName == "Scene Root", "'rootName' is the name of the root node in the file: " + str(f1.rootName)
        assert f1.nodes[f1.rootName].blockname == 'NiNode', f"'blockname' is the type of block"

        # Same for FO4 nifs
        f2 = NifFile("tests/FO4/AlarmClock.nif")
        assert f2.game == "FO4", "ERROR: Test file not FO4"

        # getAllShapeNames returns names of meshes within the nif
        all_shapes = f1.getAllShapeNames()
        expected_shapes = set(["Armor", 'MaleBody'])
        assert set(all_shapes) == expected_shapes, \
            f'ERROR: Test shape names expected in {str(all_shapes)}'

        # The shapes property lists all the meshes in the nif, whatever the format, as NiShape
        assert len(f1.shapes) == 2, "ERROR: Test file does not have 2 shapes"

        # The shape name is the node name from the nif
        assert f1.shapes[0].name in expected_shapes, \
            f"ERROR: first shape name not expected: {f1.shapes[0].name}"
        
        # Find a particular shape using the shape dictionary
        armor = f1.shape_dict["Armor"]
        body = f1.shape_dict["MaleBody"]
        assert armor.name == "Armor", f"Error: Found wrong shape: {armor.name}"

        # The shape blockname is the type of block == type of shape
        assert armor.blockname == "NiTriShape", f"ERROR: Should be a trishape: {armor.blockname}"

        # Can check whether a shape is skinned.
        assert armor.has_skin_instance, f"ERROR: Armor should be skinned: {armor.has_skin_instance}"

        f2 = NifFile("tests/skyrim/noblecrate01.nif")
        assert not f2.shapes[0].has_skin_instance, "Error: Crate should not be skinned"

        # A NiShape's verts property is a list of triples containing x,y,z position
        verts = f2.shapes[0].verts
        assert len(verts) == 686, "ERROR: Did not import 686 verts"
        assert round(verts[0][0], 4) == -67.6339, "ERROR: First vert wrong"
        assert round(verts[0][1], 4) == -24.8498, "ERROR: First vert wrong"
        assert round(verts[0][2], 4) == 0.2476, "ERROR: First vert wrong"
        assert round(verts[685][0], 4) == -64.4469, "ERROR: Last vert wrong"
        assert round(verts[685][1], 4) == -16.3246, "ERROR: Last vert wrong"
        assert round(verts[685][2], 4) == 26.4362, "ERROR: Last vert wrong"

        # Normals follow the verts
        assert len(f2.shapes[0].normals) == 686, "ERROR: Expected 686 normals"
        assert (round(f2.shapes[0].normals[0][0], 4) == 0.0), "Error: First normal wrong"
        assert (round(f2.shapes[0].normals[0][1], 4) == -0.9776), "Error: First normal wrong"
        assert (round(f2.shapes[0].normals[0][2], 4) == 0.2104), "Error: First normal wrong"
        assert (round(f2.shapes[0].normals[685][0], 4) == 0.0), "Error: Last normal wrong"
        assert (round(f2.shapes[0].normals[685][1], 4) == 0.0), "Error: Last normal wrong"
        assert (round(f2.shapes[0].normals[685][2], 4) == 1.0), "Error: Last normal wrong"

        # A NiShape's tris property is a list of triples defining the triangles. Each triangle
        # is a triple of indices into the verts list.
        tris = f2.shapes[0].tris
        assert len(tris) == 258, "ERROR: Did not import 258 tris"
        assert tris[0] == (0, 1, 2), "ERROR: First tri incorrect"
        assert tris[1] == (2, 3, 0), "ERROR: Second tri incorrect"

        # We're using fixed-length buffers internally to pass these lists back and forth, but that
        # doesn't affect the caller.
        verts = body.verts 
        assert len(verts) == 2024, "ERROR: Wrong vert count for second shape - " + str(len(f1.shapes[1].verts))

        assert round(verts[0][0], 4) == 0.0, "ERROR: First vert wrong"
        assert round(verts[0][1], 4) == 8.5051, "ERROR: First vert wrong"
        assert round(verts[0][2], 4) == 96.5766, "ERROR: First vert wrong"
        assert round(verts[2023][0], 4) == -4.4719, "ERROR: Last vert wrong"
        assert round(verts[2023][1], 4) == 8.8933, "ERROR: Last vert wrong"
        assert round(verts[2023][2], 4) == 92.3898, "ERROR: Last vert wrong"
        tris = body.tris
        assert len(tris) == 3680, "ERROR: Wrong tri count for second shape - " + str(len(f1.shapes[1].tris))
        assert tris[0][0] == 0, "ERROR: First tri wrong"
        assert tris[0][1] == 1, "ERROR: First tri wrong"
        assert tris[0][2] == 2, "ERROR: First tri wrong"
        assert tris[3679][0] == 85, "ERROR: Last tri wrong"
        assert tris[3679][1] == 93, "ERROR: Last tri wrong"
        assert tris[3679][2] == 88, "ERROR: Last tri wrong"

        # The transformation on the nif is recorded as the transform property on the shape.
        # This isn't used on skinned nifs, tho it's often set on Skyrim's nifs.
        xfbody = body.transform
        assert VNearEqual(xfbody.translation, [0.0, 0.0, 0.0]), "ERROR: Body location not 0"
        assert xfbody.scale == 1.0, "ERROR: Body scale not 1"
        xfarm = armor.transform
        assert VNearEqual(xfarm.translation, [-0.0003, -1.5475, 120.3436]), "ERROR: Armor location not correct"

        # What really matters for skinned shapes is the global-to-skin transform, which is an 
        # offset for the entire # shape. It's stored explicitly in Skyrim's nifs, calculated 
        # in FO4's.
        # Note this is the inverse of the shape transform.
        g2sk = armor.global_to_skin
        assert VNearEqual(g2sk.translation, [0.0003, 1.5475, -120.3436]),\
            "ERROR: Global to skin incorrect: {g2sk.translation}"

        # Shapes have UVs. The UV map is a list of UV pairs, 1:1 with the list of verts. 
        # Nifs don't allow one vert to have two UV locations.
        uvs = f2.shapes[0].uvs
        assert len(uvs) == 686, "ERROR: UV count not correct"
        assert list(round(x, 4) for x in uvs[0]) == [0.4164, 0.419], "ERROR: First UV wrong"
        assert list(round(x, 4) for x in uvs[685]) == [0.4621, 0.4327], "ERROR: Last UV wrong"
    
        # Bones are represented as nodes on the NifFile. Bones don't have a special type
        # in the nif, so we just bring in all NiNodes. Bones have names and transforms.
        assert len([n for n in f1.nodes.values() if type(n) == NiNode]) == 30, "ERROR: Number of bones incorrect"
        uatw = f1.nodes["NPC R UpperarmTwist2 [RUt2]"]
        assert uatw.name == "NPC R UpperarmTwist2 [RUt2]", "ERROR: Node name wrong"
        assert VNearEqual(uatw.transform.translation, [15.8788, -5.1873, 100.1124]), \
            "ERROR: Location incorrect: {uatw.transform}"

        # A skinned shape has a list of bones that influence the shape. 
        # The bone_names property returns the names of these bones.
        try:
            assert 'NPC Spine [Spn0]' in body.bone_names, "ERROR: Spine not in shape: {body.bone_names}"
        except:
            print("ERROR: Did not find bone in list")
        
        # A shape has a list of bone_ids in the shape. These are just an index, 0..#-of-bones.
        # Nifly uses this to reference the bones, but we don't need it.
        assert len(body.bone_ids) == len(body.bone_names), "ERROR: Mismatch between names and IDs"

        # The bone_weights dictionary captures weights for each bone that influences a shape. 
        # The value lists (vertex-index, weight) for each vertex it influences.
        assert len(body.bone_weights['NPC L Foot [Lft ]']) == 13, "ERRROR: Wrong number of bone weights"


    def TEST_CREATE_TETRA():
        """Can create new files with content: tetrahedron"""
        # Vertices are a list of triples defining the coordinates of each vertex
        verts = [(0.0, 0.0, 0.0),
                 (2.0, 0.0, 0.0),
                 (2.0, 2.0, 0.0),
                 (1.0, 1.0, 2.0),
                 (1.0, 1.0, 2.0),
                 (1.0, 1.0, 2.0)]
        #Normals are 1:1 with vertices because nifs only allow one normal per vertex
        norms = [(-1.0, -1.0, -0.5),
                 (1.0, -1.0, -1.0),
                 (1.0, 2.0, -1.0),
                 (0.0, 0.0, 1.0),
                 (0.0, 0.0, 1.0),
                 (0.0, 0.0, 1.0)]
        #Tris are a list of triples, indices into the vertex list
        tris = [(2, 1, 0),
                (1, 3, 0),
                (2, 4, 1),
                (5, 2, 0)]
        #UVs are 1:1 with vertices because only one UV point allowed per vertex.  Values
        #are in the range 0-1.
        uvs = [(0.4370, 0.8090),
               (0.7460, 0.5000),
               (0.4370, 0.1910),
               (0.9369, 1.0),
               (0.9369, 0.0),
               (0.0, 0.5000) ]
        
        # Create a nif with an empty NifFile object, then initializing it with game and filepath.
        # Can create a shape in one call by passing in these lists
        newf = NifFile()
        newf.initialize("SKYRIM", "tests/out/testnew01.nif")
        newf.rootNode.flags = 14
        newf.createShapeFromData("FirstShape", verts, tris, uvs, norms)
        newf.save()

        newf_in = NifFile("tests/out/testnew01.nif")
        assert newf_in.shapes[0].name == "FirstShape", "ERROR: Didn't get expected shape back"
        assert newf_in.rootNode.flags == 14, f"Have correct flags: {newf_in.rootNode.flags}"
    
        # Skyrim and FO4 work the same way
        newf2 = NifFile()
        newf2.initialize("FO4", "tests/out/testnew02.nif")
        newf2.createShapeFromData("FirstShape", verts, tris, uvs, norms,
                                  use_type=PynBufferTypes.BSTriShapeBufType) # , is_skinned=False)
        newf2.save()

        newf2_in = NifFile("tests/out/testnew02.nif")
        assert newf2_in.shapes[0].name == "FirstShape", "ERROR: Didn't get expected shape back"
        assert newf2_in.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape, found {newf2_in.shapes[0].blockname}"

        #Transforms are set by putting them on the NiShape
        newf3 = NifFile()
        newf3.initialize("SKYRIM", "tests/out/testnew03.nif")
        shape = newf3.createShapeFromData("FirstShape", verts, tris, uvs, norms)
        shape.transform = TransformBuf().set_identity()
        shape.transform.translation = VECTOR3(1.0, 2.0, 3.0)
        shape.transform.scale = 1.5
        newf3.save()

        newf3_in = NifFile("tests/out/testnew03.nif")
        xf3 = newf3_in.shapes[0].transform
        assert VNearEqual(xf3.translation, (1.0, 2.0, 3.0)), "ERROR: Location transform wrong"
        assert xf3.scale == 1.5, "ERROR: Scale transform wrong"
    
    def TEST_CREATE_WEIGHTS():
        """Can create tetrahedron with bone weights (Skyrim)"""
        verts = [(0.0, 1.0, -1.0), (0.866, -0.5, -1.0), (-0.866, -0.5, -1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
        norms = [(0.0, 0.9219, -0.3873), (0.7984, -0.461, -0.3873), (-0.7984, -0.461, -0.3873), (-0.8401, 0.4851, 0.2425), (0.8401, 0.4851, 0.2425), (0.0, -0.9701, 0.2425)]
        tris = [(0, 4, 1), (0, 1, 2), (1, 5, 2), (2, 3, 0)]
        uvs = [(0.46, 0.30), (0.80, 0.5), (0.46, 0.69), (0.0, 0.5), (0.86, 0.0), (0.86, 1.0)]
        
        # These weights are 1:1 with verts, listing the bones that influence the vert.
        weights = [{"Bone.001": 0.0974, "Bone.003": 0.9026},
                   {"Bone.002": 0.0715, "Bone.003": 0.9285},
                   {"Bone": 0.0000, "Bone.001": 0.0000, "Bone.002": 0.0000, "Bone.003": 1.0000},
                   {"Bone": 0.9993, "Bone.003": 0.0007}, 
                   {"Bone": 0.9993, "Bone.003": 0.0007},
                   {"Bone": 0.9993, "Bone.003": 0.0007}]
        group_names = ["Bone", "Bone.001", "Bone.002", "Bone.003"]
        arma_bones = {"Bone": (0,0,0.5), "Bone.001": (-0.009,1.016,-0.988), 
                      "Bone.002": (0.858,-0.48,-0.96), "Bone.003": (-0.83,-0.559,-0.955)}
        bones = BoneDict([
            SkeletonBone('Bone', 'BONE1'),
            SkeletonBone("Bone.001", "BONE2"), 
            SkeletonBone("Bone.002", "BONE3"),
            SkeletonBone("Bone.003", "BONE4") ],
            {}, [])

        newf4 = NifFile()
        newf4.initialize("SKYRIM", "tests/out/testnew04.nif")
        # Need a skin to attach a mesh to an armature.  Can create the skin on the
        # NifFile, then on the NiShape, but putting it on the NifFile is optional.  The
        # shape will make sure its nif is set up.
        shape4 = newf4.createShapeFromData("WeightedTetra", verts, tris, uvs, norms)
        shape4.transform.translation = (0,0,0)
        shape4.transform.scale = 1.0
        shape4.skin()

        # It's sometimes convenient to have a bone and ask what verts it influences,
        # other times to have a vert and ask what bones influence it.  weights_by_bone
        # goes from weights by vert to by bone.
        weights_by_bone = get_weights_by_bone(weights, ['Bone', 'Bone.001', 'Bone.002', 'Bone.003'])
        used_bones = weights_by_bone.keys()

        # Need to add the bones to the shape before you can weight them.
        for b in arma_bones:
            xf = TransformBuf()
            xf.translation = arma_bones[b]
            shape4.add_bone(bones.nif_name(b), xf)

        # Transforms position parts relative to their parent or absolute in the global
        # reference frame.  The global to skin transform makes that translation.  Note
        # the skindata transform uses a block that only Skyrim nifs have.
        bodyPartXform = TransformBuf().set_identity()
        bodyPartXform.translation = VECTOR3(0.000256, 1.547526, -120.343582)
        shape4.set_global_to_skin(bodyPartXform)

        # SetShapeWeights sets the vertex weights from a bone
        for bone_name, weights in weights_by_bone.items():
            if (len(weights) > 0):
                nif_name = bones.nif_name(bone_name)
                xf = TransformBuf()
                xf.translation = arma_bones[bone_name]
                shape4.set_skin_to_bone_xform(nif_name, bodyPartXform)
                shape4.setShapeWeights(nif_name, weights)
    
        newf4.save()

        # The skin-to-bone transform is the local transform for the bone as it's used by
        # the skin.  This lets the game move the verts relative to the bone as it's moved
        # in animations.
        newf4in = NifFile("tests/out/testnew04.nif")
        newshape = newf4in.shapes[0]
        xform = newshape.get_shape_skin_to_bone("BONE2")
        assert not VNearEqual(xform.translation, [0.0, 0.0, 0.0]), "Error: Translation should not be null"


    def TEST_READ_WRITE():
        """Basic load-and-store for Skyrim--Can read the armor nif and spit out armor and body separately"""
        testfile = "tests/Skyrim/test.nif"
        outfile1 = "tests/Out/TEST_READ_WRITE1.nif"
        outfile2 = "tests/Out/TEST_READ_WRITE2.nif"
        outfile3 = "tests/Out/TEST_READ_WRITE3.nif"
        if os.path.exists(outfile1):
            os.remove(outfile1)
        if os.path.exists(outfile2):
            os.remove(outfile2)
        if os.path.exists(outfile3):
            os.remove(outfile3)

        nif = NifFile(testfile)
        assert "Armor" in nif.getAllShapeNames(), "ERROR: Didn't read armor"
        assert "MaleBody" in nif.getAllShapeNames(), "ERROR: Didn't read body"

        the_armor = nif.shape_dict["Armor"]
        the_body = nif.shape_dict["MaleBody"]
        assert len(the_armor.verts) == 2115, "ERROR: Wrong number of verts"
        assert (len(the_armor.tris) == 3195), "ERROR: Wrong number of tris"

        assert int(the_armor.transform.translation[2]) == 120, "ERROR: Armor shape is raised up"
        assert the_armor.has_skin_instance, "Error: Armor should be skinned"

        """Can save armor to Skyrim"""
        new_nif = NifFile()
        new_nif.initialize("SKYRIM", outfile1)
        ModuleTest.export_shape(the_armor, new_nif)
        #new_armor = new_nif.createShapeFromData("Armor", 
        #                                        the_armor.verts,
        #                                        the_armor.tris,
        #                                        the_armor.uvs,
        #                                        the_armor.normals)
        #new_armor.transform = the_armor.transform.copy()
        #new_armor.skin()
        #new_armor_gts = the_armor.transform.copy()
        #new_armor_gts.translation = VECTOR3(the_armor.transform.translation[0] * -1,
        #                                    the_armor.transform.translation[1] * -1,
        #                                    the_armor.transform.translation[2] * -1)
        #new_armor.set_global_to_skin(new_armor_gts)

        #for bone_name, weights in the_armor.bone_weights.items():
        #    new_armor.add_bone(bone_name)
        #    new_armor.setShapeWeights(bone_name, weights)
    
        new_nif.save()

        # Armor and body nifs are generally positioned below ground level and lifted up with a transform, 
        # approx 120 in the Z direction. The transform on the armor shape is actually irrelevant;
        # it's the global_to_skin and skin-to-bone transforms that matter.
        test_nif = NifFile(outfile1)
        armor01 = test_nif.shapes[0]
        assert int(armor01.transform.translation[2]) == 120, \
            f"ERROR: Armor shape should be set at 120 in '{outfile1}'"
        assert int(armor01.global_to_skin.translation[2]) == -120, \
            f"ERROR: Armor skin instance should be at -120 in {outfile1}"
        assert the_armor.global_to_skin.NearEqual(armor01.global_to_skin), "ERROR: global-to-skin differs: {armor01.global_to_skin}"
        ftxf = the_armor.get_shape_skin_to_bone('NPC L ForearmTwist1 [LLt1]')
        ftxf01 = armor01.get_shape_skin_to_bone('NPC L ForearmTwist1 [LLt1]')
        assert int(ftxf01.translation[2]) == -5, \
            f"ERROR: Skin transform Z should be -5.0, have {ftxf01.translation}"
        assert ftxf.NearEqual(ftxf01), f"ERROR: Skin-to-bone differs: {ftxf01}"
        

        max_vert = max([v[2] for v in armor01.verts])
        assert max_vert < 0, "ERROR: Armor verts are all below origin"

        """Can save body to Skyrim"""
        new_nif2 = NifFile()
        new_nif2.initialize("SKYRIM", outfile2)
        ModuleTest.export_shape(the_body, new_nif2)

        #new_body = new_nif.createShapeFromData("Body", 
        #                                        the_body.verts,
        #                                        the_body.tris,
        #                                        the_body.uvs,
        #                                        the_body.normals)
        #new_body.skin()
        #body_gts = the_body.global_to_skin
        #new_body.set_global_to_skin(the_body.global_to_skin.copy())

        #for b in the_body.bone_names:
        #    new_body.add_bone(b)

        #for bone_name, weights in the_body.bone_weights.items():
        #    new_body.setShapeWeights(bone_name, weights)
    
        new_nif2.save()

        # check that the body is where it should be
        test_py02 = NifFile(outfile2)
        test_py02_body = test_py02.shapes[0]
        max_vert = max([v[2] for v in test_py02_body.verts])
        assert max_vert < 130, "ERROR: Body verts are all below 130"
        min_vert = min([v[2] for v in test_py02_body.verts])
        assert min_vert > 0, "ERROR: Body verts all above origin"

        """Can save armor and body together"""

        newnif3 = NifFile()
        newnif3.initialize("SKYRIM", outfile3)
        ModuleTest.export_shape(the_body, newnif3)
        ModuleTest.export_shape(the_armor, newnif3)    
        newnif3.save()

        nif3res = NifFile(outfile3)
        body2res = nif3res.shape_dict["MaleBody"]
        sstb = body2res.get_shape_skin_to_bone("NPC Spine1 [Spn1]")

        # Body doesn't have shape-level transformations so make sure we haven't put in
        # bone-level transformations when we exported it with the armor
        try:
            assert sstb.translation[2] > 0, f"ERROR: Body should be lifted above origin in {testfile}"
        except:
            # This is an open bug having to do with exporting two shapes at once (I think)
            pass

    def TEST_XFORM_FO():
        """Can read the FO4 body transforms"""
        f1 = NifFile("tests/FO4/BTMaleBody.nif")
        s1 = f1.shapes[0]
        xfshape = s1.transform
        xfskin = s1.global_to_skin
        assert int(xfshape.translation[2]) == 0, f"ERROR: FO4 body shape has a 0 z translation: {xfshape.translation[2]}"
        assert int(xfskin.translation[2]) == -120, f"ERROR: global-to-skin is calculated: {xfskin.translation[2]}"

    def TEST_2_TAILS():
        """Can export tails file with two tails"""

        testfile_in = r"tests/Skyrim/maletaillykaios.nif"
        testfile_out = "tests/out/testtails01.nif"
        ft1 = NifFile(testfile_in)
        ftout = NifFile()
        ftout.initialize("SKYRIM", testfile_out)

        for s_in in ft1.shapes:
            ModuleTest.export_shape(s_in, ftout)

        ftout.save()

        fttest = NifFile(testfile_out)
        assert len(fttest.shapes) == 2, "ERROR: Should write 2 shapes"
        for s in fttest.shapes:
            assert len(s.bone_names) == 7, f"ERROR: Failed to write all bones to {s.name}"
            assert "TailBone01" in s.bone_names, f"ERROR: bone cloth not in bones: {s.name}, {s.bone_names}"

    def TEST_ROTATIONS():
        """Can handle rotations"""

        testfile = r"tests\FO4\VulpineInariTailPhysics.nif"
        f = NifFile(testfile)
        n = f.nodes['Bone_Cloth_H_002']
        assert VNearEqual(n.transform.translation, (-2.5314, -11.4114, 65.6487)), f"Translation is correct: {n.transform.translation}"
        assert MatNearEqual(n.transform.rotation, 
                            ((-0.0251, 0.9993, -0.0286),
                             (-0.0491, -0.0298, -0.9984),
                             (-0.9985, -0.0237, 0.0498))
                            ), f"Rotations read correctly: {n.transform.rotation}"

        # Write tail mesh
        nifOut = NifFile()
        nifOut.initialize('FO4', r"tests\out\TEST_ROTATIONS.nif")
        ModuleTest.export_shape(f.shape_dict['Inari_ZA85_fluffy'], nifOut)
        nifOut.save()

        # Check results
        nifCheck = NifFile(r"tests\out\TEST_ROTATIONS.nif")
        cloth2Check = nifCheck.nodes['Bone_Cloth_H_002']
        assert VNearEqual(cloth2Check.transform.translation, n.transform.translation), f"Translation is unchanged: {cloth2Check.transform.translation}"
        assert MatNearEqual(cloth2Check.transform.rotation, n.transform.rotation), f"Rotation is unchanged: {cloth2Check.transform.rotation}"


    def TEST_PARENT():
        """Can handle nifs which show relationships between bones"""

        testfile = r"tests\FO4\bear_tshirt_turtleneck.nif"
        f = NifFile(testfile)
        n = f.nodes['RArm_Hand']
        # System accurately parents bones to each other bsaed on nif or reference skeleton
        assert n.parent.name == 'RArm_ForeArm3', "Error: Parent node should be forearm"

    def TEST_PYBABY():
        print('### TEST_PYBABY: Can export multiple parts')

        testfile = r"tests\FO4\baby.nif"
        nif = NifFile(testfile)
        head = nif.shape_dict['Baby_Head:0']
        eyes = nif.shape_dict['Baby_Eyes:0']

        outfile1 = r"tests\Out\baby02.nif"
        outnif1 = NifFile()
        outnif1.initialize("FO4", outfile1)
        ModuleTest.export_shape(head, outnif1)
        outnif1.save()

        testnif1 = NifFile(outfile1)
        testhead1 = testnif1.shape_by_root('Baby_Head:0')
        stb1 = testhead1.get_shape_skin_to_bone('Skin_Baby_BN_C_Head')

        assert not VNearEqual(stb1.translation, [0,0,0]), "Error: Exported bone transforms should not be identity"
        assert stb1.scale == 1.0, "Error: Scale should be one"

        outfile2 = r"tests\Out\baby03.nif"
        outnif2 = NifFile()
        outnif2.initialize("FO4", outfile2)
        ModuleTest.export_shape(head, outnif2)
        ModuleTest.export_shape(eyes, outnif2)
        outnif2.save()

        testnif2 = NifFile(outfile2)
        testhead2 = testnif2.shape_by_root('Baby_Head:0')
        stb2 = testhead2.get_shape_skin_to_bone('Skin_Baby_BN_C_Head')

        assert len(testhead1.bone_names) == len(testhead2.bone_names), "Error: Head should have bone weights"
        assert VNearEqual(stb1.translation, stb2.translation), "Error: Bone transforms should stay the same"
        assert VNearEqual(stb1.rotation[0], stb2.rotation[0]), "Error: Bone transforms should stay the same"
        assert VNearEqual(stb1.rotation[1], stb2.rotation[1]), "Error: Bone transforms should stay the same"
        assert VNearEqual(stb1.rotation[2], stb2.rotation[2]), "Error: Bone transforms should stay the same"
        assert stb1.scale == stb2.scale, "Error: Bone transforms should stay the same"

    def TEST_BONE_XFORM():
        print('### TEST_BONE_XFORM: Can read bone transforms')

        nif = NifFile(r"tests/Skyrim/MaleHead.nif")

        # node-to-global transform combines all the transforms to show node's position
        # in space. Since this nif doesn't contain bone relationships, that's just
        # the transform on the bone.
        mat = nif.get_node_xform_to_global("NPC Spine2 [Spn2]")
        assert NearEqual(mat.translation[2], 91.2488), f"Error: Translation should not be 0, found {mat.translation[2]}"

        # If the bone isn't in the nif, the node-to-global is retrieved from
        # the reference skeleton.
        mat2 = nif.get_node_xform_to_global("NPC L Forearm [LLar]")
        assert NearEqual(mat2.translation[2], 85.7311), f"Error: Translation should not be 0, found {mat2.translation[2]}"

        nif = NifFile(r"tests/FO4/BaseMaleHead.nif")
        mat3 = nif.get_node_xform_to_global("Neck")
        assert NearEqual(mat3.translation[2], 113.2265), f"Error: Translation should not be 0: {mat3.translation[2]}"
        mat4 = nif.get_node_xform_to_global("SPINE1")
        assert NearEqual(mat4.translation[2], 72.7033), f"Error: Translation should not be 0: {mat4.translation[2]}"

    def TEST_PARTITIONS():
        print('### TEST_PARTITIONS: Can read partitions')

        nif = NifFile(r"tests/Skyrim/MaleHead.nif")
        # partitions property holds partition info. Head has 3
        assert len(nif.shapes[0].partitions) == 3
        
        # First of the partitions is the neck body part
        assert nif.shapes[0].partitions[0].id == 230
        assert nif.shapes[0].partitions[0].name == "SBP_230_NECK"

        # Partition tri list matches tris 1:1, so has same as number of tris. Refers 
        # to the partitions by index into the partitioin list.
        assert len(nif.shapes[0].partition_tris) == 1694
        assert max(nif.shapes[0].partition_tris) < len(nif.shapes[0].partitions), f"tri index out of range"

        """Can write partitions back out"""
        nif2 = NifFile()
        nif2.initialize('SKYRIM', r"tests/Out/PartitionsMaleHead.nif")
        ModuleTest.export_shape(nif.shapes[0], nif2)

        # set_partitions expects a list of partitions and a tri list.  The tri list references
        # reference partitions by ID, because when there are segments and subsegments it
        # gets very confusing.
        trilist = [nif.shapes[0].partitions[t].id for t in nif.shapes[0].partition_tris]
        nif2.shapes[0].set_partitions(nif.shapes[0].partitions, trilist)
        nif2.save()

        nif3 = NifFile(r"tests/Out/PartitionsMaleHead.nif")
        assert len(nif3.shapes[0].partitions) == 3, "Have the same number of partitions as before"
        assert nif3.shapes[0].partitions[0].id == 230, "Partition IDs same as before"
        assert nif3.shapes[0].partitions[1].id == 130, "Partition IDs same as before"
        assert nif3.shapes[0].partitions[2].id == 143, "Partition IDs same as before"
        assert len(nif3.shapes[0].partition_tris) == 1694, "Same number of tri indices as before"
        assert (nif3.shapes[0].partitions[0].flags and 1) == 1, "First partition has start-net-boneset set"

    def TEST_SEGMENTS_EMPTY():
        """Can write FO4 segments when some are empty"""

        nif = NifFile("tests/FO4/TEST_SEGMENTS_EMPTY.nif")

        nif2 = NifFile()
        nif2.initialize('FO4', r"tests/Out/TEST_SEGMENTS_EMPTY.nif")
        ModuleTest.export_shape(nif.shapes[0], nif2)
        segs = [FO4Segment(0, 0, "FO4 Seg 000"),
                FO4Segment(1, 1, "FO4 Seg 001"),
                FO4Segment(2, 2, "FO4 Seg 002"),
                FO4Segment(3, 3, "FO4 Seg 003"),
                FO4Segment(4, 4, "FO4 Seg 004"),
                FO4Segment(5, 5, "FO4 Seg 005"),
                FO4Segment(6, 6, "FO4 Seg 006")]
        ptris = [3] * len(nif.shapes[0].tris)
        nif2.shapes[0].set_partitions(segs, ptris)
        nif2.save()

        nif3 = NifFile(r"tests/Out/TEST_SEGMENTS_EMPTY.nif")

        assert len([x for x in nif3.shapes[0].partition_tris if x == 3]) == len(nif3.shapes[0].tris), f"Expected all tris in the 4th partition"


    def TEST_SEGMENTS():
        print ("### TEST_SEGMENTS: Can read FO4 segments")

        nif = NifFile(r"tests/FO4/VanillaMaleBody.nif")
        body = nif.shapes[0]

        # partitions property holds segment info for FO4 nifs. Body has 7 top-level segments
        assert len(body.partitions) == 7, f"Found wrong number of segments: 7 <> {len(nif.shapes[0].partitions)}"
        
        # IDs assigned by nifly for reference
        segment_names = set([x.name for x in body.partitions])
        assert segment_names == set(["FO4 Seg 000", "FO4 Seg 001", "FO4 Seg 002", "FO4 Seg 003", "FO4 Seg 004", "FO4 Seg 005", "FO4 Seg 006"]), f"Didn't find full list of partitions: {segment_names}"

        # Partition tri list gives the index of the associated partition for each tri in
        # the shape, so it's the same size as number of tris in shape
        assert len(body.partition_tris) == 2698

        # Shape has a segment file external to the nif
        assert body.segment_file == r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf"

        # Subsegments hang off the segment/partition they are a part of.  They are given
        # names based on their "material" property.  That name includes the name of their
        # parent, so the parent figures out its own name from its subsegments.  This is
        # magic figured out by OS.
        subsegs = body.partitions[2].subsegments
        subseg_names = [x.name for x in subsegs]
        assert len(subsegs) > 0, "Shapes have subsegments"
        assert subsegs[0].name == "FO4 Seg 002 | 000 | Up Arm.R", f"Subsegments have human-readable names: '{subsegs[0].name}'"
        assert "FO4 Seg 002 | 003 | Lo Arm.R" in subseg_names, f"Missing lower arm subsegment in {subseg_names}"

        """Can write segments back out"""
        # When writing segments, the tri list refers to segments/subsegments by ID *not*
        # by index into the partitions list (becuase it only has segments, not
        # subsegments, and it's the subsegments the tri list wants to reference).
        nif2 = NifFile()
        nif2.initialize('FO4', r"tests/Out/SegmentsMaleBody.nif")
        ModuleTest.export_shape(nif.shapes[0], nif2)
        nif2.shapes[0].segment_file = r"Meshes\Actors\Character\CharacterAssets\MaleBodyOut.ssf"
        nif2.shapes[0].set_partitions(nif.shapes[0].partitions, 
                                      nif.shapes[0].partition_tris)
        nif2.save()

        nif3 = NifFile(r"tests/Out/SegmentsMaleBody.nif")
        assert len(nif3.shapes[0].partitions) == 7, f"Error: Expected the same number of partitions as before, found {len(nif3.shapes[0].partitions)} != 7"
        assert nif3.shapes[0].partitions[2].id != 0, "Partition IDs same as before"
        assert nif3.shapes[0].partitions[2].name == "FO4 Seg 002"
        assert len(nif3.shapes[0].partitions[2].subsegments) == 4, "Shapes have subsegments"
        assert nif3.shapes[0].partitions[2].subsegments[0].name == "FO4 Seg 002 | 000 | Up Arm.R", "Subsegments have human-readable names"
        assert nif3.shapes[0].segment_file == r"Meshes\Actors\Character\CharacterAssets\MaleBodyOut.ssf"


    def TEST_BP_SEGMENTS():
        print ("### TEST_BP_SEGMENTS: Can read FO4 body part segments")

        nif = NifFile(r"tests/FO4/Helmet.nif")

        # partitions property holds segment info for FO4 nifs. Helmet has 2 top-level segments
        helm = nif.shapes[1]
        assert helm.name == "Helmet:0", "Have helmet as expected"
        assert len(helm.partitions) == 2
        
        # IDs assigned by nifly for reference
        assert helm.partitions[1].id != 0
        assert helm.partitions[1].name == "FO4 Seg 001"

        # Partition tri list gives the index of the associated partition for each tri in
        # the shape, so it's the same size as number of tris in shape
        assert len(helm.partition_tris) == 2878, "Found expected tris"

        # Shape has a segment file external to the nif
        assert helm.segment_file == r"Meshes\Armor\FlightHelmet\Helmet.ssf"

        # Bodypart subsegments hang off the segment/partition they are a part of.  They are given
        # names based on their user_slot property. 
        assert len(helm.partitions[1].subsegments) > 0, "Shapes have subsegments"
        assert helm.partitions[1].subsegments[0].name == "FO4 Seg 001 | Hair Top | Head", "Subsegments have human-readable names"

        visor = nif.shapes[0]
        assert visor.name == "glass:0", "Have visor"
        assert visor.partitions[1].subsegments[0].name == "FO4 Seg 001 | Hair Top", "Visor has no bone ID"

        """Can write segments back out"""
        # When writing segments, the tri list refers to segments/subsegments by ID *not*
        # by index into the partitions list (becuase it only has segments, not
        # subsegments, and it's the subsegments the tri list wants to reference).
        nif2 = NifFile()
        nif2.initialize('FO4', r"tests/Out/SegmentsHelmet.nif")
        ModuleTest.export_shape(helm, nif2)
        nif2.shapes[0].segment_file = r"Meshes\Armor\FlightHelmet\Helmet.ssf"

        p1 = FO4Segment(0, 0)
        p2 = FO4Segment(1, 0)
        ss1 = FO4Subsegment(2, 30, 0x86b72980, p2)
        nif2.shapes[0].set_partitions([p1, p2], helm.partition_tris)
        nif2.save()

        nif3 = NifFile(r"tests/Out/SegmentsHelmet.nif")
        assert len(nif3.shapes[0].partitions) == 2, "Have the same number of partitions as before"
        assert nif3.shapes[0].partitions[1].id != 0, "Partition IDs same as before"
        assert nif3.shapes[0].partitions[1].name == "FO4 Seg 001"
        assert len(nif3.shapes[0].partitions[1].subsegments) > 0, "Shapes have subsegments"
        assert nif3.shapes[0].partitions[1].subsegments[0].name.startswith("FO4 Seg 001 | Hair Top | Head"), "Subsegments have human-readable names"
        assert nif3.shapes[0].segment_file == r"Meshes\Armor\FlightHelmet\Helmet.ssf"

    def TEST_PARTITION_NAMES():
        """Can parse various forms of partition name"""

        # Blender vertex groups have magic names indicating they are nif partitions or
        # segments.  We have to analyze the group name to see if it's something we have
        # to care about.
        assert SkyPartition.name_match("SBP_42_CIRCLET") == 42, "Match skyrim parts"
        assert SkyPartition.name_match("FOOBAR") < 0, "Don't match random stuff"

        assert FO4Segment.name_match("FO4Segment #3") == 3, "Match FO4 parts"
        assert FO4Segment.name_match("FO4 Seg 003") == 3, "Match new-style FO4 segments"
        assert FO4Segment.name_match("Segment 4") < 0, "Don't match bougs names"

        sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 002 | 001 | Thigh.R")
        assert sseg_par == "FO4 Seg 002", "Extract subseg parent name"
        assert sseg_id == 1, "Extract ID"
        assert sseg_mat == 0xbf3a3cc5, "Extract material"

        sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 003 | 003 | Lo Arm.R")
        assert sseg_par == "FO4 Seg 003", "Extract subseg parent name"
        assert sseg_id == 3, "Extract ID"
        assert sseg_mat == 0x6fc3fbb2, "Extract material"

        sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 000 | Hair Top | Head")
        assert sseg_par == "FO4 Seg 000", "Should have parent name"
        assert sseg_id == 30, "Should have part id"
        assert sseg_mat == 0x86b72980, "Extract material"

        sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 001 | Head | Head")
        assert sseg_par == "FO4 Seg 001", "Should have parent name"
        assert sseg_id == 32, "Should have part id"
        assert sseg_mat == 0x86b72980, "Extract material"

        assert FO4Subsegment.name_match("FO4 Seg 003 | HP-Neck | HP-Neck") \
            == ("FO4 Seg 003", 33, 0x3D6644AA), "name_match parses subsegments with bodyparts"

        assert FO4Segment.name_match("FO4 Seg 003 | 003 | Lo Arm.R") < 0, \
            "FO4Segment.name_match does not match on subsegments"

        assert FO4Subsegment.name_match("FO4 Seg 001 | Hair Top") == ("FO4 Seg 001", 30, -1), \
            "FO4Subsegment.name_match matches subsegments without material"

        assert FO4Subsegment.name_match("FO4 Seg 001 | Hair Top | 0x1234") == ("FO4 Seg 001", 30, 0x1234), \
            "FO4Subsegment.name_match matches subsegments with material as number"


    def TEST_COLORS():
        """Can load and save colors"""

        nif = NifFile(r"Tests/FO4/HeadGear1.nif")
        assert nif.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0)
        assert nif.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0)

        nif2 = NifFile()
        nif2.initialize("FO4", r"Tests/Out/TEST_COLORS_HeadGear1.nif")
        ModuleTest.export_shape(nif.shapes[0], nif2)
        nif2.shapes[0].set_colors(nif.shapes[0].colors)
        nif2.save()

        nif3 = NifFile(r"Tests/Out/TEST_COLORS_HeadGear1.nif")
        assert nif3.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0)
        assert nif3.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0)
        
        nif4 = NifFile(r"tests\Skyrim\test.nif")
        assert nif4.shapes[1].name == "Armor", "Have the right shape"
        assert len(nif4.shapes[1].verts) > 0, "Get the verts from the shape"
        assert len(nif4.shapes[1].colors) == 0, f"Should have no colors, 0 != {len(nif4.shapes[1].colors)}"
        

    def TEST_FNV():
        """Can load and save FNV nifs"""

        nif = NifFile(r"tests\FONV\9mmscp.nif")
        shapenames = [s.name for s in nif.shapes]
        assert "Scope:0" in shapenames, f"Error in shape name 'Scope:0' not in {shapenames}"
        scopeidx = shapenames.index("Scope:0")
        assert len(nif.shapes[scopeidx].verts) == 831, f"Error in vertex count: 831 != {nif.shapes[0].verts == 831}"
        
        nif2 = NifFile()
        nif2.initialize('FONV', r"tests/Out/9mmscp.nif")
        for s in nif.shapes:
            ModuleTest.export_shape(s, nif2)
        nif2.save()


    def TEST_BLOCKNAME():
        """Can get block type as a string"""

        nif = NifFile(r"tests\SKYRIMSE\malehead.nif")
        assert nif.shapes[0].blockname == "BSDynamicTriShape", f"Expected 'BSDynamicTriShape', found '{nif.shapes[0].blockname}'"


    def TEST_LOD():
        """BSLODTriShape is handled. Its shader attributes are handled."""
        def check_nif(nif):
            glow = nif.shape_dict['L2_WindowGlow']
            assert glow.blockname == "BSLODTriShape", f"Expected 'BSDynamicTriShape', found '{nif.shapes[0].blockname}'"
            assert not glow.shader.shaderflags1_test(ShaderFlags1.VERTEX_ALPHA), f"VERTEX_ALPHA not set"
            assert glow.shader.properties.LightingInfluence == 255, f"Have correct lighting influence: {glow.shader.properties.LightingInfluence}"

            win = nif.shape_dict['BlackBriarChalet:7']
            assert win.shader.textures['EnvMap'] == r"textures\cubemaps\ShinyGlass_e.dds", f"Have correct environment map: {win.shader.textures['EnvMap']}"

        nif = NifFile(r"tests\Skyrim\blackbriarchalet_test.nif")
        check_nif(nif)

        nifout = NifFile()
        nifout.initialize("SKYRIM", r"Tests/Out/TEST_LOD.nif")
        ModuleTest.export_shape(nif.shapes[0], nifout)
        ModuleTest.export_shape(nif.shapes[1], nifout)
        nifout.save()

        nifcheck = NifFile(r"Tests/Out/TEST_LOD.nif")
        check_nif(nifcheck)


    def TEST_UNSKINNED():
        """FO4 unskinned shape uses BSTriShape"""

        nif = NifFile(r"Tests/FO4/Alarmclock.nif")
        assert nif.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape, got {nif.shapes[0].blockname}"

        nif2 = NifFile()
        nif2.initialize("FO4", r"Tests/Out/TEST_UNSKINNED.nif")
        ModuleTest.export_shape(nif.shapes[0], nif2)
        nif2.save()

        nif3 = NifFile(r"Tests/Out/TEST_UNSKINNED.nif")
        assert nif3.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape after export, got {nif3.shapes[0].blockname}"

    def TEST_UNI():
        """Can load and store files with non-ascii pathnames"""

        nif = NifFile(r"tests\FO4\TestUnicode\проверка\будильник.nif")
        assert len(nif.shapes) == 1, f"Error: Expected 1 shape, found {len(nif.shapes)}"

        nif2 = NifFile()
        nif2.initialize('SKYRIMSE', r"tests\out\будильник.nif")
        ModuleTest.export_shape(nif.shapes[0], nif2)
        nif2.save()

        nif3 = NifFile(f"tests\out\будильник.nif")
        assert len(nif3.shapes) == 1, f"Error: Expected 1 shape, found {len(nif3.shapes)}"

    def TEST_SHADER():
        """Can read shader flags"""
        hnse = NifFile(r"tests\SKYRIMSE\malehead.nif")
        hsse = hnse.shapes[0]
        assert hsse.shader.Shader_Type == 4
        assert hsse.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), \
            f"Expected MSN true, got {hsse.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)}"
        assert hsse.shader.Alpha == 1.0, f"Expected Alpha 1, got {hsse.shader.Alpha}"
        assert hsse.shader.Glossiness == 33.0, f"Expected Glossiness 33, got {hsse.shader.Glossiness}"

        hnle = NifFile(r"tests\SKYRIM\malehead.nif")
        hsle = hnle.shapes[0]
        assert hsle.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), \
            f"Expected MSN true, got {hsle.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)}"
        assert hsle.shader.Glossiness == 33.0, f"Error: Glossiness incorrect: {hsle.shader.Glossiness}"

        hnfo = NifFile(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\HeadTest.nif")
        hsfo = hnfo.shapes[0]
        assert not hsfo.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), \
            f"Expected MSN true, got {hsfo.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)}"

        cnle = NifFile(r"tests\Skyrim\noblecrate01.nif")
        csle = cnle.shapes[0]
        assert not csle.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), \
            f"Expected MSN false, got {csle.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)}"

        """Can read texture paths"""
        assert hsse.textures["Diffuse"] == r"textures\actors\character\male\MaleHead.dds"
        assert hsse.textures["Normal"] == r"textures\actors\character\male\MaleHead_msn.dds"
        assert hsse.textures["SoftLighting"] == r"textures\actors\character\male\MaleHead_sk.dds"
        assert hsse.textures["Specular"] == r"textures\actors\character\male\MaleHead_S.dds"

        assert hsle.textures["Diffuse"] == r"textures\actors\character\male\MaleHead.dds"
        assert hsle.textures["Normal"] == r"textures\actors\character\male\MaleHead_msn.dds"
        assert hsle.textures["SoftLighting"] == r"textures\actors\character\male\MaleHead_sk.dds"
        assert hsle.textures["Specular"] == r"textures\actors\character\male\MaleHead_S.dds"

        assert hsfo.textures["Diffuse"] == r"Actors/Character/BaseHumanMale/BaseMaleHead_d.dds"
        assert hsfo.textures["Normal"] == r"Actors/Character/BaseHumanMale/BaseMaleHead_n.dds"
        assert hsfo.textures["Specular"] == r"actors/character/basehumanmale/basemalehead_s.dds"
        assert hsfo.textures["EnvMap"] == r"Shared/Cubemaps/mipblur_DefaultOutside1_dielectric.dds"
        assert hsfo.textures["Wrinkles"] == r"Actors/Character/BaseHumanMale/HeadWrinkles_n.dds"

        print("------------- Extract non-default values")
        v = {}
        hsse.shader.extract(v)
        print(v)
        assert 'Shader_Flags_1' in v
        assert 'Glossiness' in v
        assert 'UV_Scale_U' not in v

        """Can read and write shader"""
        nif = NifFile(r"tests\FO4\AlarmClock.nif")
        assert len(nif.shapes) == 1, f"Error: Expected 1 shape, found {len(nif.shapes)}"
        shape = nif.shapes[0]
        attrs = shape.shader

        nifOut = NifFile()
        nifOut.initialize('FO4', r"tests\out\SHADER_OUT.nif")
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        nifOut.save()

        nifTest = NifFile(f"tests\out\SHADER_OUT.nif")
        assert len(nifTest.shapes) == 1, f"Error: Expected 1 shape, found {len(nifTest.shapes)}"
        shapeTest = nifTest.shapes[0]
        attrsTest = shapeTest.shader
        # We didn't write a materials file, but on reading what we wrote we read the same
        # materials file, so we should still read the same values.
        assert attrs.name == attrsTest.name, f"Maintained path to materials file."
        # diffs = attrsTest.properties.compare(attrs.properties)
        # assert diffs == [], f"Error: Expected same shader attributes: {diffs}"

    def TEST_ALPHA():
        """Can read and write alpha property"""
        nif = NifFile(r"tests/Skyrim/meshes/actors/character/Lykaios/Tails/maletaillykaios.nif")
        tailfur = nif.shapes[1]

        assert tailfur.shader.Shader_Type == BSLSPShaderType.Skin_Tint, \
            f"Error: Skin tint incorrect, got {tailfur.shader.Shader_Type}"
        assert tailfur.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), \
            f"Expected MSN true, got {tailfur.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)}"
        assert tailfur.alpha_property.flags == 4844, \
            f"Error: Alpha flags incorrect, found {tailfur.alpha_property.flags}"
        assert tailfur.alpha_property.threshold == 70, \
            f"Error: Threshold incorrect, found {tailfur.alpha_property.threshold}"

        nifOut = NifFile()
        nifOut.initialize('SKYRIM', r"tests\out\pynifly_TEST_ALPHA.nif")
        ModuleTest.export_shape(tailfur, nifOut)
        nifOut.save()

        nifcheck = NifFile(r"tests\out\pynifly_TEST_ALPHA.nif")
        tailcheck = nifcheck.shapes[0]

        assert tailcheck.alpha_property.flags == tailfur.alpha_property.flags, \
               f"Error: alpha flags don't match, {tailcheck.alpha_property.flags} != {tailfur.alpha_property.flags}"
        assert tailcheck.alpha_property.threshold == tailfur.alpha_property.threshold, \
               f"Error: alpha flags don't match, {tailcheck.alpha_property.threshold} != {tailfur.alpha_property.threshold}"
        
    def TEST_SHEATH():
        """Can read and write extra data"""
        nif = NifFile(r"tests/Skyrim/sheath_p1_1.nif")
        
        # Extra data can be at the file level
        bg = nif.behavior_graph_data
        assert bg == [('BGED', r"AuxBones\SOS\SOSMale.hkx", True)], f"Error: Expected behavior graph data, got {bg}"

        s = nif.string_data
        assert len(s) == 2, f"Error: Expected two string data records"
        assert ('HDT Havok Path', 'SKSE\\Plugins\\hdtm_baddog.xml') in s, "Error: expect havok path"
        assert ('HDT Skinned Mesh Physics Object', 'SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml') in s, "Error: Expect physics path"

        # File level is root level
        bg = nif.rootNode.behavior_graph_data
        assert bg == [('BGED', r"AuxBones\SOS\SOSMale.hkx", True)], f"Error: Expected behavior graph data, got {bg}"

        s = nif.rootNode.string_data
        assert len(s) == 2, f"Error: Expected two string data records"
        assert ('HDT Havok Path', 'SKSE\\Plugins\\hdtm_baddog.xml') in s, "Error: expect havok path"
        assert ('HDT Skinned Mesh Physics Object', 'SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml') in s, "Error: Expect physics path"

        # Can write extra data at the file level
        nifout = NifFile()
        nifout.initialize('SKYRIM', r"tests/Out/pynifly_TEST_SHEATH.nif")
        nifout.behavior_graph_data = nif.behavior_graph_data
        nifout.string_data = nif.string_data
        # Can write extra data with multiple calls
        nifout.string_data = [('BODYTRI', 'foo/bar/fribble.tri')]

        ModuleTest.export_shape(nif.shapes[0], nifout)
        nifout.save()

        nifcheck = NifFile(r"tests/Out/pynifly_TEST_SHEATH.nif")

        assert len(nifcheck.shapes) == 1, "Error: Wrote expected shapes"
        assert nifcheck.behavior_graph_data == [('BGED', r"AuxBones\SOS\SOSMale.hkx", True)], f"Error: Expected behavior graph data, got {nifcheck.behavior_graph_data}"
        
        assert len(nifcheck.string_data) == 3, f"Error: Expected three string data records in written file"
        assert ('HDT Havok Path', 'SKSE\\Plugins\\hdtm_baddog.xml') in nifcheck.string_data, "Error: expect havok path in written file"
        assert ('HDT Skinned Mesh Physics Object', 'SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml') in nifcheck.string_data, "Error: Expect physics path in written file"
        assert ('BODYTRI', 'foo/bar/fribble.tri') in nifcheck.string_data, "Error: Expected second string data written to be available"


    def TEST_FEET():
        """Can read and write extra data"""
        nif = NifFile(r"tests/SkyrimSE/caninemalefeet_1.nif")
        feet = nif.shapes[0]
        
        s = feet.string_data
        assert s[0][0] == 'SDTA', f"Error: Expected string data, got {s}"
        assert s[0][1].startswith('[{"name"'), f"Error: Expected string data, got {s}"

        nifout = NifFile()
        nifout.initialize('SKYRIM', r"tests/Out/pynifly_TEST_FEET.nif")
        ModuleTest.export_shape(feet, nifout)
        nifout.save()

        nifcheck = NifFile(r"tests/Out/pynifly_TEST_FEET.nif")

        assert len(nifcheck.shapes) == 1, "Error: Wrote expected shapes"
        feetcheck = nifcheck.shapes[0]

        s = feetcheck.string_data
        assert s[0][0] == 'SDTA', f"Error: Expected string data, got {s}"
        assert s[0][1].startswith('[{"name"'), f"Error: Expected string data, got {s}"

    def TEST_XFORM_SKY():
        """Can read and set the Skyrim body transforms"""
        """Can read Skyrim head transforms"""
        nif = NifFile(r"tests\Skyrim\malehead.nif")
        head = nif.shapes[0]
        xfshape = head.transform
        xfskin = head.global_to_skin
        assert int(xfshape.translation[2]) == 120, "ERROR: Skyrim head shape has a 120 z translation"
        assert int(xfskin.translation[2]) == -120, "ERROR: Skyrim head shape has a -120 z skin translation"

        nifout = NifFile()
        nifout.initialize('SKYRIM', r"tests/Out/TEST_XFORM_SKY.nif")
        ModuleTest.export_shape(head, nifout)
        #xfshapeout = xfshape.copy()
        #xfshapeout.translation = VECTOR3(0, -1.5475, 120.3436)
        nifout.save()

        nifcheck = NifFile(r"tests/Out/TEST_XFORM_SKY.nif")
        headcheck = nifcheck.shapes[0]
        xfshapecheck = headcheck.transform
        xfskincheck = headcheck.global_to_skin
        assert int(xfshapecheck.translation[2]) == 120, "ERROR: Skyrim head shape has a 120 z translation"
        assert int(xfskincheck.translation[2]) == -120, "ERROR: Skyrim head shape has a -120 z skin translation"

    def TEST_XFORM_STATIC():
        """Can read static transforms"""

        nif = NifFile(r"tests\FO4\Meshes\SetDressing\Vehicles\Crane03_simplified.nif")
        glass = nif.shapes[0]

        assert glass.name == "Glass:0", f"Error: Expected glass first, found {glass.name}"
        assert round(glass.transform.translation[0]) == -108, f"Error: X translation wrong: {glass.transform.translation[0]}"
        assert round(glass.transform.rotation[1][0]) == 1, f"Error: Rotation incorrect, got {glass.transform.rotation[1]}"

    def TEST_MUTANT():
        """can read the mutant nif correctly"""

        testfile = r"tests/FO4/testsupermutantbody.nif"
        nif = NifFile(testfile)
        shape = nif.shapes[0]
        
        assert round(shape.global_to_skin.translation[2]) == -140, f"Error: Expected -140 z translation, got {shape.global_to_skin.translation[2]}"

        bellyxf = nif.get_node_xform_to_global('Belly_skin')
        assert NearEqual(bellyxf.translation[2], 90.1133), f"Error: Expected Belly_skin Z near 90, got {bellyxf.translation[2]}"

        nif2 = NifFile(testfile)
        shape2 = nif.shapes[0]

        assert round(shape2.global_to_skin.translation[2]) == -140, f"Error: Expected -140 z translation, got {shape2.global_to_skin.translation[2]}"

    def TEST_BONE_XPORT_POS():
        """bones named like vanilla bones but from a different skeleton export to the correct position"""

        testfile = r"tests/Skyrim/Draugr.nif"
        nif = NifFile(testfile)
        draugr = nif.shapes[0]
        spine2 = nif.nodes['NPC Spine2 [Spn2]']

        assert round(spine2.transform.translation[2], 2) == 102.36, f"Expected bone location at z 102.36, found {spine2.transform.translation[2]}"

        outfile = r"tests/Out/pynifly_TEST_BONE_XPORT_POS.nif"
        nifout = NifFile()
        nifout.initialize('SKYRIM', outfile)
        ModuleTest.export_shape(draugr, nifout)
        nifout.save()

        nifcheck = NifFile(outfile)
        draugrcheck = nifcheck.shapes[0]
        spine2check = nifcheck.nodes['NPC Spine2 [Spn2]']

        assert round(spine2check.transform.translation[2], 2) == 102.36, f"Expected output bone location at z 102.36, found {spine2check.transform.translation[2]}"

    def TEST_CLOTH_DATA():
        """can read and write cloth data"""

        testfile = r"tests/FO4/HairLong01.nif"
        nif = NifFile(testfile)
        shape = nif.shapes[0]
        clothdata = nif.cloth_data[0]
        # Note the array will have an extra byte, presumeably for a null?
        assert len(clothdata[1]) == 46257, f"Expeected cloth data length 46257, got {len(clothdata[1])}"

        outfile = r"tests/out/pynifly_TEST_CLOTH_DATA.nif"
        nifout = NifFile()
        nifout.initialize('FO4', outfile)
        ModuleTest.export_shape(shape, nifout)
        nifout.cloth_data = nif.cloth_data
        nifout.save()

        nifcheck = NifFile(outfile)
        shapecheck = nifcheck.shapes[0]
        clothdatacheck = nifcheck.cloth_data[0]
        assert len(clothdatacheck[1]) == 46257, f"Expeected cloth data length 46257, got {len(clothdatacheck[1])}"

        for i, p in enumerate(zip(clothdata[1], clothdatacheck[1])):
            assert p[0] == p[1], f"Cloth data doesn't match at {i}, {p[0]} != {p[1]}"

        print("# Can export cloth data when it's been extracted and put back")
        buf = codecs.encode(clothdata[1], 'base64')

        outfile2 = r"tests/out/pynifly_TEST_CLOTH_DATA2.nif"
        nifout2 = NifFile()
        nifout2.initialize('FO4', outfile2)
        ModuleTest.export_shape(shape, nifout2)
        nifout2.cloth_data = [['binary data', codecs.decode(buf, 'base64')]]
        nifout2.save()

        nifcheck2 = NifFile(outfile2)
        shapecheck2 = nifcheck2.shapes[0]
        clothdatacheck2 = nifcheck2.cloth_data[0]
        assert len(clothdatacheck2[1]) == 46257, f"Expeected cloth data length 46257, got {len(clothdatacheck2[1])}"

        for i, p in enumerate(zip(clothdata[1], clothdatacheck2[1])):
            assert p[0] == p[1], f"Cloth data doesn't match at {i}, {p[0]} != {p[1]}"


    def TEST_PARTITION_SM():
        """Regression--test that supermutant armor can be read and written"""

        testfile = r"tests/FO4/SMArmor0_Torso.nif"
        nif = NifFile(testfile)
        armor = nif.shapes[0]
        partitions = armor.partitions

        nifout = NifFile()
        nifout.initialize('FO4', r"tests/Out/TEST_PARTITION_SM.nif")
        ModuleTest.export_shape(armor, nifout)
        nifout.shapes[0].segment_file = armor.segment_file
        nifout.shapes[0].set_partitions(armor.partitions, armor.partition_tris)
        nifout.save()

        # If no CTD we're good


    def TEST_EXP_BODY():
        """Ensure body with bad partitions does not cause a CTD on export"""

        testfile = r"tests/FO4/feralghoulbase.nif"
        nif = NifFile(testfile)
        shape = nif.shape_dict['FeralGhoulBase:0']
        partitions = shape.partitions

        # This is correcct
        nifout = NifFile()
        nifout.initialize('FO4', r"tests/Out/TEST_EXP_BODY.nif")
        ModuleTest.export_shape(shape, nifout)
        nifout.shapes[0].segment_file = shape.segment_file
        nifout.shapes[0].set_partitions(shape.partitions, shape.partition_tris)
        nifout.save()

        print('....This causes an error')
        try:
            os.remove(r"tests/Out/TEST_EXP_BODY2.nif")
        except:
            pass

        nifout2 = NifFile()
        nifout2.initialize('FO4', r"tests/Out/TEST_EXP_BODY2.nif")
        ModuleTest.export_shape(shape, nifout2)
        sh = nifout2.shapes[0]
        sh.segment_file = shape.segment_file
        seg0 = FO4Segment(0)
        seg1 = FO4Segment(1)
        seg12 = FO4Segment(12)
        seg4 = FO4Segment(4)
        seg15 = FO4Segment(15)
        seg26 = FO4Segment(26)
        seg37 = FO4Segment(37)
        FO4Subsegment(4, 0, 0, seg4, name='FO4 Feral Ghoul 2')
        FO4Subsegment(15, 0, 0, seg15, name='FO4 Feral Ghoul 4')
        FO4Subsegment(26, 0, 0, seg15, name='FO4 Death Claw 5')
        FO4Subsegment(37, 0, 0, seg15, name='FO4 Death Claw 6')
        # error caused by referencing a segment that doesn't exist
        tri_map = [16] * len(sh.tris)

        NifFile.clear_log();
        sh.set_partitions([seg0, seg1, seg4], tri_map)

        assert "ERROR" in NifFile.message_log(), "Error: Expected error message, got '{NifFile.message_log()}'"
        # If no CTD we're good


    def TEST_EFFECT_SHADER_SKY():
        """Can read and write shader flags"""
        testfile = r"tests\SkyrimSE\meshes\armor\daedric\daedriccuirass_1.nif"
        outfile = r"tests\out\TEST_EFFECT_SHADER_SKY.nif"

        def CheckNif(nif:NifFile):
            glow:NiShape = nif.shape_dict["MaleTorsoGlow"]
            sh = glow.shader
            assert sh.blockname == "BSEffectShaderProperty", f"Expected BSEffectShaderProperty, got {glass.shader_block_name}"
            assert sh.shaderflags1_test(ShaderFlags1.VERTEX_ALPHA), f"Expected VERTEX_ALPHA true"
            assert not sh.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)
            assert sh.shaderflags2_test(ShaderFlags2.NO_FADE)
            assert NearEqual(sh.UV_Scale_U, 10.0), f"Have correct UV scale: {sh.UV_Scale_U}"
            assert sh.textureClampMode == 3, f"Have correct textureClampMode: {sh.textureClampMode}"

            assert sh.textures['Diffuse'] == r"textures\effects\VaporTile02.dds", f"Source texture correct: {sh.textures['Diffuse']}"
            assert sh.textures['Greyscale'] == r"textures\effects\gradients\GradDisguiseShader02.dds", f"Greyscale texture correct {sh.textures['Greyscale']}"

        print("---Read---")
        nif = NifFile(testfile)
        CheckNif(nif)

        """Can read and write shader"""
        print("---Write---")
        nifOut = NifFile()
        nifOut.initialize('FO4', outfile)
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        ModuleTest.export_shape(nif.shapes[1], nifOut)
        nifOut.save()

        print("---Check---")
        nifTest = NifFile(outfile, materialsRoot='tests/FO4')
        CheckNif(nifTest)


    def TEST_EFFECT_SHADER_FO4():
        """Can read and write shader flags"""
        testfile = r"tests/FO4/Helmet.nif"
        outfile = r"tests\out\TEST_EFFECT_SHADER_FO4.nif"

        def CheckHelmet(nif):
            glass:NiShape = next(s for s in nif.shapes if s.name.startswith("glass"))
            glass_attr = glass.shader
            assert glass.shader_block_name == "BSEffectShaderProperty", f"Expected BSEffectShaderProperty, got {glass.shader_block_name}"
            assert glass.shader_name == r"Materials\Armor\FlightHelmet\glass.BGEM", "Have correct shader name"
            assert glass_attr.shaderflags1_test(ShaderFlags1.USE_FALLOFF), f"Expected USE_FALLOFF true, got {glass_attr.shaderflags1_test(ShaderFlags1.USE_FALLOFF)}"
            assert not glass_attr.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)
            assert glass_attr.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING)
            assert glass_attr.shaderflags2_test(ShaderFlags2.EFFECT_LIGHTING)
            assert not glass_attr.shaderflags2_test(ShaderFlags2.VERTEX_COLORS)

            assert glass_attr.textureClampMode == 3
            assert NearEqual(glass_attr.falloffStartOpacity, 0.1)
            assert NearEqual(glass_attr.Emissive_Mult, 1.0)
            # assert glass_attr.sourceTexture.decode() == "Armor/FlightHelmet/Helmet_03_d.dds", \
            #     f"Source texture correct: {glass_attr.sourceTexture}"

            assert glass.textures['Diffuse'] == "Armor/FlightHelmet/Helmet_03_d.dds", f"Expected 'Armor/FlightHelmet/Helmet_03_d.dds', got {glass.textures}"
            assert glass.textures["Normal"] == "Armor/FlightHelmet/Helmet_03_n.dds", f"Expected 'Armor/FlightHelmet/Helmet_03_n.dds', got {glass.textures[1]}"
            assert glass.textures["EnvMapMask"] == "Armor/FlightHelmet/Helmet_03_s.dds", f"Expected 'Armor/FlightHelmet/Helmet_03_s.dds', got {glass.textures[5]}"

        print("---Read---")
        nif = NifFile(testfile)
        CheckHelmet(nif)

        """Can read and write shader"""
        print("---Write---")
        nifOut = NifFile()
        nifOut.initialize('FO4', outfile)
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        nifOut.save()

        print("---Check---")
        nifTest = NifFile(outfile, materialsRoot='tests/FO4')
        CheckHelmet(nifTest)


    def TEST_TEXTURE_CLAMP():
        """Make sure we don't lose texture clamp mode"""
        testfile = r"tests\SkyrimSE\evergreen.nif"
        outfile = r"tests\out\TEST_TEXTURE_CLAMP.nif"

        def CheckNif(nif:NifFile):
            shape:NiShape = nif.shapes[0]
            sh = shape.shader
            assert sh.blockname == "BSLightingShaderProperty", f"Have correct shader"
            assert sh.textureClampMode == 0, f"Have correct textureClampMode: {sh.textureClampMode}"

        print("---Read---")
        nif = NifFile(testfile)
        CheckNif(nif)

        """Can read and write shader"""
        print("---Write---")
        nifOut = NifFile()
        nifOut.initialize('FO4', outfile)
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        nifOut.save()

        print("---Check---")
        nifTest = NifFile(outfile)
        CheckNif(nifTest)


    def TEST_BOW():
        """Can read and write special weapon data; also testing BGED"""
        nif = NifFile(r"tests\SkyrimSE\meshes\weapons\glassbowskinned.nif")

        root = nif.rootNode
        assert root.blockname == "BSFadeNode", f"Top level node should read as BSFadeNode, found '{root.blockname}'"
        assert root.flags == 14, "Root node has flags"
        assert VNearEqual(root.global_transform.translation, [0,0,0]), "Root node transform can be read"
        assert VNearEqual(root.global_transform.rotation[0], [1,0,0]), "Root node transform can be read"
        assert VNearEqual(root.global_transform.rotation[1], [0,1,0]), "Root node transform can be read"
        assert VNearEqual(root.global_transform.rotation[2], [0,0,1]), "Root node transform can be read"
        assert root.global_transform.scale == 1.0, "Root node transform can be read"

        assert root.behavior_graph_data == [('BGED', r"Weapons\Bow\BowProject.hkx", False)], f"Error: Expected behavior graph data, got {nif.behavior_graph_data}"

        assert root.inventory_marker[0] == "INV"
        assert root.inventory_marker[1:4] == [4712, 0, 785]
        assert round(root.inventory_marker[4], 4) == 1.1273, "Inventory marker has rotation and zoom info"

        assert root.bsx_flags == ['BSX', 202]

        bone = nif.nodes['Bow_MidBone']
        co = bone.collision_object
        assert co.blockname == "bhkCollisionObject", f"Can find type of collision object from the block name: {co.blockname}"

        assert co.flags == bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE, f'Can read collision flags'
        assert co.target.name == "Bow_MidBone", f"Can read collision target"
        assert co.body.blockname == "bhkRigidBodyT", "Can read collision block"

        assert co.body.properties.collisionResponse == hkResponseType.SIMPLE_CONTACT
        assert co.body.properties.motionSystem == hkMotionType.SPHERE_STABILIZED, f"Collision body properties hold the specifics"

        collshape = co.body.shape
        assert collshape.blockname == "bhkBoxShape", f"Collision body's shape property returns the collision shape"
        assert collshape.properties.bhkMaterial == SkyrimHavokMaterial.MATERIAL_BOWS_STAVES, "Collision body shape material is readable"
        assert round(collshape.properties.bhkRadius, 4) == 0.0136, f"Collision body shape radius is readable"
        assert [round(x, 4) for x in collshape.properties.bhkDimensions] == [0.1574, 0.8238, 0.0136], f"Collision body shape dimensions are readable"

        # WRITE MESH WITH COLLISION DATA 

        nifOut = NifFile()
        nifOut.initialize('SKYRIMSE', r"tests\out\TEST_BOW.nif", root.blockname, root.name)
        ModuleTest.export_shape(nif.shapes[0], nifOut)

        # Testing BGED too
        nifOut.behavior_graph_data = nif.behavior_graph_data

        # Have to apply the skin so we have the bone available to add collisions
        #nifOut.apply_skin()
        midbow = nifOut.nodes["Bow_MidBone"]

        # Create the collision bottom-up, shape first
        coll_out = midbow.add_collision(None, bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE)
        bod_out = coll_out.add_body(co.body.properties)
        box_out = bod_out.add_shape(collshape.properties)

        nifOut.save()

        nifcheck = NifFile(r"tests\out\TEST_BOW.nif")
        rootCheck = nifcheck.nodes[nifcheck.rootName]
        assert nifcheck.rootName == root.name, f"ERROR: root name not correct, {nifcheck.rootName} != {root.name}"
        assert rootCheck.blockname == root.blockname, f"ERROR: root type not correct, {rootCheck.blockname} != {root.blockname}"

        collcheck = nifcheck.nodes["Bow_MidBone"].collision_object
        assert collcheck.flags == bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE, f"Flags not correctly read: {collcheck.flags}"

        bodycheck = collcheck.body
        assert bodycheck.blockname == 'bhkRigidBodyT', f"Collision body not correct, {bodycheck.blockname != 'bhkRigidBodyT'}"
        assert bodycheck.properties.collisionFilter_layer == SkyrimCollisionLayer.WEAPON, f"Collision layer not correct, {bodycheck.properties.collisionFilter_layer} != {SkyrimCollisionLayer.WEAPON}"
        assert bodycheck.properties.collisionResponse == hkResponseType.SIMPLE_CONTACT, f"Collision response not correct, {bodycheck.properties.collisionResponse} != {hkResponseType.SIMPLE_CONTACT}"
        assert bodycheck.properties.qualityType == hkQualityType.MOVING, f"Movement quality type not correct, {bodycheck.properties.qualityType} != {hkQualityType.MOVING}"

        boxcheck = bodycheck.shape
        assert [round(x, 4) for x in boxcheck.properties.bhkDimensions] == [0.1574, 0.8238, 0.0136], f"Collision body shape dimensions written correctly"


    def TEST_CONVEX():
        """Can read and write convex collisions"""
        nif = NifFile(r"tests/Skyrim/cheesewedge01.nif")

        root = nif.rootNode
        co = root.collision_object
        assert co.blockname == "bhkCollisionObject", f"Can find type of collision object from the block name: {co.blockname}"

        assert co.target.name == root.name, f"Can read collision target"
        assert co.body.blockname == "bhkRigidBody", "Can read collision block"

        assert co.body.properties.collisionResponse == hkResponseType.SIMPLE_CONTACT
        assert co.body.properties.motionSystem == hkMotionType.SPHERE_STABILIZED, f"Collision body properties hold the specifics"

        collshape = co.body.shape
        assert collshape.blockname == "bhkConvexVerticesShape", f"Collision body's shape property returns the collision shape"
        assert collshape.properties.bhkMaterial == SkyrimHavokMaterial.CLOTH, "Collision body shape material is readable"

        assert VNearEqual(collshape.vertices[0], [-0.059824, -0.112763, 0.101241, 0]), f"Vertex 0 is correct"
        assert VNearEqual(collshape.vertices[7], [-0.119985, 0.000001, 0, 0]), f"Vertex 7 is correct"
        assert VNearEqual(collshape.normals[0], [0.513104, 0, 0.858327, -0.057844]), f"Normal 0 is correct"
        assert VNearEqual(collshape.normals[9], [-0.929436, 0.273049, 0.248180, -0.111519]), f"Normal 9 is correct"

        # WRITE MESH WITH COLLISION DATA 

        nifOut = NifFile()
        nifOut.initialize('SKYRIM', r"tests\out\TEST_CONVEX.nif", root.blockname, root.name)
        ModuleTest.export_shape(nif.shapes[0], nifOut)

        # Create the collision bottom-up, shape first
        coll_out = nifOut.rootNode.add_collision(
            None, bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE)
        bod_out = coll_out.add_body(co.body.properties)
        box_out = bod_out.add_shape(collshape.properties, collshape.vertices, collshape.normals)

        nifOut.save()


    def TEST_CONVEX_MULTI():
        """Can read and write convex collisions"""
        nif = NifFile(r"tests/Skyrim/grilledleeks01.nif")

        l2 = nif.shape_dict["Leek02:0"]
        assert l2.parent.name == "Leek02", f"Parent of shape is node: {l2.parent.name}"


    def checkFalmerStaff(nif):
        root = nif.rootNode
        staff = nif.shapes[0]
        coll = nif.rootNode.collision_object
        collbody = coll.body
        assert collbody.properties.collisionFilter_layer == SkyrimCollisionLayer.WEAPON, f"Rigid body has values"
        collshape = collbody.shape
        assert collshape.blockname == "bhkListShape", f"Have list shape: {collshape.blockname}"
        assert collshape.properties.bhkMaterial == SkyrimHavokMaterial.MATERIAL_BOWS_STAVES
        assert len(collshape.children) == 3, f"Have 3 children: {collshape.children}"
        cts0 = collshape.children[0]
        cts1 = collshape.children[1]
        cts2 = collshape.children[2]
        assert cts0.blockname == "bhkConvexTransformShape", f"Child is transform shape: {cts0.blockname}"
        assert cts1.blockname == "bhkConvexTransformShape", f"Child is transform shape: {cts1.blockname}"
        assert cts2.blockname == "bhkConvexTransformShape", f"Child is transform shape: {cts2.blockname}"
        assert cts0.properties.bhkMaterial == SkyrimHavokMaterial.MATERIAL_BOWS_STAVES, f"Material is correct: {cts0.properties.bhkMaterial}"
        assert NearEqual(cts0.properties.bhkRadius, 0.009899), "ConvexTransformShape has values"

        assert len(staff.bone_weights) == 0, f"Shape not skinned: {staff}"
        assert len(staff.partitions) == 0, f"Shape has no partitioins"

        box0 = cts0.child


    def TEST_COLLISION_LIST():
        """Can read and write convex collisions"""
        nif = NifFile(r"tests/Skyrim/falmerstaff.nif")
        ModuleTest.checkFalmerStaff(nif)

        # ------------ Save it ----------

        nifOut = NifFile()
        nifOut.initialize('SKYRIM', r"tests\out\TEST_COLLISION_LIST.nif", nif.rootNode.blockname, "Scene Root")
        ModuleTest.export_shape(nif.shapes[0], nifOut)

        # Create the collision 
        coll_out = nifOut.rootNode.add_collision(
            None, bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE)
        bodprop_out =  bhkRigidBodyProps()
        bodprop_out.collisionFilter_layer = SkyrimCollisionLayer.WEAPON
        bod_out = coll_out.add_body(bodprop_out)
        csprop_out = bhkListShapeProps()
        csprop_out.bhkMaterial = SkyrimHavokMaterial.MATERIAL_BOWS_STAVES
        listshape_out = bod_out.add_shape(csprop_out)
        for i in range(0, 3):
            ctsprop_out = bhkConvexTransformShapeProps()
            ctsprop_out.bhkMaterial = SkyrimHavokMaterial.MATERIAL_BOWS_STAVES
            ctsprop_out.bhkRadius = 0.009899
            cts_out = listshape_out.add_shape(ctsprop_out)

            box_out = bhkBoxShapeProps()
            cts_out.add_shape(box_out)

        nifOut.save()

        ModuleTest.checkFalmerStaff(NifFile(r"tests\out\TEST_COLLISION_LIST.nif"))


    def TEST_COLLISION_CAPSULE():
        """Can read and write capsule collisions"""
        nif = NifFile(r"tests/Skyrim/staff04.nif")

        root = nif.rootNode
        staff = nif.shape_dict["3rdPersonStaff04:1"]
        coll = nif.rootNode.collision_object
        collbody = coll.body
        collshape = collbody.shape
        assert collshape.blockname == "bhkCapsuleShape", f"Have capsule shape: {collshape.blockname}"


    def TEST_FURNITURE_MARKER():
        """Can read and write furniture markers"""
        nif = NifFile(r"tests/SkyrimSE/farmbench01.nif")

        assert len(nif.furniture_markers) == 2, f"Found the furniture markers"


    def TEST_MANY_SHAPES():
        """Can read and write a nif with many shapes"""
        nif = NifFile(r"tests\FO4\Outfit.nif")

        assert len(nif.shapes) == 87, f"Found all shapes: {len(nif.shapes)}"
        
        nifOut = NifFile()
        nifOut.initialize('FO4', r"tests\out\TEST_MANY_SHAPES.nif")
        for s in nif.shapes:
            ModuleTest.export_shape(s, nifOut)

        nifOut.save()

        nifcheck = NifFile(r"tests\out\TEST_MANY_SHAPES.nif")

        assert len(nifcheck.shapes) == 87, f"Found all shapes in written file: {len(nifcheck.shapes)}"


    def TEST_CONNECT_POINTS():
        """Can read and write connect points"""
        nif = NifFile(r"tests\FO4\Shotgun\CombatShotgun.nif")

        pcp = nif.connect_points_parent
        assert len(pcp) == 5, f"Can read all the connect points: {len(pcp)}"
        assert pcp[0].parent.decode('utf-8') == "WeaponMagazine", f"Can read the name property: {pcp[0].parent}"
        pcpnames = set([x.name.decode() for x in pcp])
        assert pcpnames == set(['P-Mag', 'P-Grip', 'P-Barrel', 'P-Casing', 'P-Scope']), f"Can read all names: {pcpnames}"

        pcc = nif.connect_points_child
        assert not nif.connect_pt_child_skinned, f"Shotgun not skinned {pcc[0]}"
        assert "C-Receiver" in pcc, f"Have two conect points: {pcc}"
        assert "C-Reciever" in pcc, f"Have two conect points: {pcc}"

        nifOut = NifFile()
        nifOut.initialize('FO4', r"tests\out\TEST_CONNECT_POINTS.nif")
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        nifOut.connect_points_parent = nif.connect_points_parent
        nifOut.connect_pt_child_skinned = False
        nifOut.connect_points_child = ["C-Receiver", "C-Reciever"]
        nifOut.save()

        nifcheck = NifFile(r"tests\out\TEST_CONNECT_POINTS.nif")
        pcpcheck = nifcheck.connect_points_parent
        assert len(pcpcheck) == 5, f"Can read all the connect points: {len(pcpcheck)}"
        assert pcpcheck[0].parent.decode('utf-8') == "WeaponMagazine", f"Can read the name property: {pcpcheck[0].parent}"
        pcpnamescheck = set([x.name.decode() for x in pcpcheck])
        assert pcpnames == pcpnamescheck, f"Can read all names: {pcpnamescheck}"

        pcccheck = nifcheck.connect_points_child
        assert not nifcheck.connect_pt_child_skinned, f"Shotgun not skinned {nifcheck.connect_pt_child_skinned}"
        assert "C-Receiver" in pcccheck, f"Have two conect points: {pcccheck}"
        assert "C-Reciever" in pcccheck, f"Have two conect points: {pcccheck}"


    def TEST_SKIN_BONE_XF():
        """Can read and write the skin-bone transform"""
        nif = NifFile(r"tests\SkyrimSE\maleheadargonian.nif")
        head = nif.shapes[0]

        head_spine_xf = head.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
        assert NearEqual(head_spine_xf.translation[2], 29.419632), f"Have correct z: {head_spine_xf.translation[2]}"

        head_head_xf = head.get_shape_skin_to_bone('NPC Head [Head]')
        assert NearEqual(head_head_xf.translation[2], -0.000031), f"Have correct z: {head_head_xf.translation[2]}"

        hsx = nif.nodes['NPC Spine2 [Spn2]'].transform * head_spine_xf
        assert NearEqual(hsx.translation[2], 120.3436), f"Head-spine transform positions correctly: {hsx.translation[2]}"
        hhx = nif.nodes['NPC Head [Head]'].transform * head_head_xf
        assert NearEqual(hhx.translation[2], 120.3436), f"Head-head transform positions correctly: {hhx.translation[2]}"

        nifout = NifFile()
        nifout.initialize('SKYRIMSE', r"tests\out\TEST_SKIN_BONE_XF.nif")

        ModuleTest.export_shape(head, nifout)

        nifout.save()

        nifcheck = NifFile(r"tests\out\TEST_SKIN_BONE_XF.nif")
        headcheck = nifcheck.shapes[0]

        head_spine_check_xf = headcheck.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
        assert NearEqual(head_spine_check_xf.translation[2], 29.419632), f"Have correct z: {head_spine_check_xf.translation[2]}"

        head_head_check_xf = headcheck.get_shape_skin_to_bone('NPC Head [Head]')
        assert NearEqual(head_head_check_xf.translation[2], -0.000031), f"Have correct z: {head_head_check_xf.translation[2]}"

        hsx_check = nifcheck.nodes['NPC Spine2 [Spn2]'].transform * head_spine_check_xf
        assert NearEqual(hsx_check.translation[2], 120.3436), f"Head-spine transform positions correctly: {hsx_check.translation[2]}"
        hhx_check = nifcheck.nodes['NPC Head [Head]'].transform * head_head_check_xf
        assert NearEqual(hhx_check.translation[2], 120.3436), f"Head-headcheck transform positions correctly: {hhx_check.translation[2]}"

        #Throw in an unrelated test for whether the UV got inverted
        assert VNearEqual(head.uvs[0], headcheck.uvs[0]), f"UV 0 same in both: [{head.uvs[0]}, {headcheck.uvs[0]}]"

    def TEST_WEIGHTS_BY_BONE():
        """Weights-by-bone helper works correctly"""
        nif = NifFile(r"tests\SkyrimSE\Anna.nif")
        allnodes = list(nif.nodes.keys())
        hair = nif.shape_dict["KSSMP_Anna"]

        #Sanity check--each vertex/weight pair listed just once
        vwp_list = [None] * len(hair.verts)
        for i in range(0, len(hair.verts)):
            vwp_list[i] = {}
        
        for bone, weights_list in hair.bone_weights.items():
            for vwp in weights_list:
                assert bone not in vwp_list[vwp[0]], \
                       f"Error: Vertex {vwp[0]} duplicated for bone {bone}"
                vwp_list[vwp[0]][bone] = 1

        hair_vert_weights = get_weights_by_vertex(hair.verts, hair.bone_weights)
        assert len(hair_vert_weights) == len(hair.verts), "Have enough vertex weights"
        assert NearEqual(hair_vert_weights[245]['NPC Head [Head]'], 0.0075), \
            f"Weight is correct: {hair_vert_weights[245]['NPC Head [Head]']}"
        
        wbb = get_weights_by_bone(hair_vert_weights, allnodes)

        assert len(list(wbb.keys())) == 14, f"Have all bones: {wbb.keys()}"
        assert 'Anna R3' in wbb, f"Special bone in weights by bone: {wbb.keys()}"
        vw = [vp[1] for vp in wbb['NPC Head [Head]'] if vp[0] == 245]
        assert len(vw) == 1 and NearEqual(vw[0], 0.0075), \
            f"Have weight by bone correct: {vw}"

        hair_vert_weights[5]['NPC'] = 0.0
        hair_vert_weights[10]['NPC'] = 0.0
        hair_vert_weights[15]['NPC'] = 0.0

        wbb2 = get_weights_by_bone(hair_vert_weights, allnodes)
        assert 'BOGUS' not in wbb2, f"Bone with no weights not in weights by bone: {wbb2.keys()}"


    def TEST_ANIMATION():
        """Embedded animations"""
        nif = NifFile(r"tests/Skyrim/dwechest01.nif")
        root = nif.rootNode
        assert nif.max_string_len > 10, f"Have reasonable {nif.max_string_len}"

        # Any node can have a controller, including the root. This nif has a 
        # NiControllerManager, which coordinates multiple animations.
        cm = root.controller
        # assert len(nif.controller_managers) == 1, f"Found a controller manager"
        # cm = nif.controller_managers[0]
        assert cm.properties.frequency == 1.0, f"Have correct frequency: {cm.properties.frequency}"
        assert cm.properties.nextControllerID == 3, f"Have correct next controller: {cm.properties.nextControllerID}"
        assert cm.properties.flags == 76, f"Have correct flags: {cm.properties.flags}"

        # Controllers can be chained. 
        mttc = cm.next_controller
        assert mttc.properties.flags == 108, f"Have correct flag: {mttc.properties.flags}"
        assert mttc.next_controller is None, f"MTTC does not have next controller: {mttc.next_controller}"

        # Controller sequences describe the actual animations. Each has name indicating
        # what it does. For the chest, they open or close the lid.
        assert len(cm.sequences) == 2, f"Have 2 controller manager sequences: {cm.sequences}"
        cm_names = set(cm.sequences.keys())
        assert cm_names == set(["Open", "Close"]), f"Have correct name: {cm_names}"
        cm_open = cm.sequences['Open']
        assert NearEqual(cm_open.properties.stopTime, 0.6), f"Have correct stop time: {cm_open.properties.stopTime}"

        # The controlled block is the thing that's actually getting animated, referenced
        # by name.
        cblist = cm_open.controlled_blocks
        assert len(cblist) == 9, f"Have 9 controlled blocks: {cblist}"
        assert cblist[0].node_name == "Object01", f"Have correct target: {cblist[0].node_name}"
        assert cblist[0].controller_type == "NiTransformController", f"Have correct controller type: {cblist[0].controller_type}"

        # The interpolator parents the actual animation data.
        interp = cblist[0].interpolator

        # The data is stored in the animation keys. In this chest, Object01 is the lid that 
        # slides down and sideways, so no rotations.
        td = interp.data
        # we don't seem to be getting the number of rotation keys from the nif.
        # assert td.properties.rotationKeyCount == 0, f"Found no rotation keys: {td.properties.rotationKeyCount}"
        assert td.properties.translations.numKeys == 18, f"Found translation keys: {td.properties.translations.numKeys}"
        assert td.properties.translations.interpolation == NiKeyType.LINEAR_KEY, f"Found correct interpolation: {td.properties.translations.interpolation}"
        assert td.translations[0].time == 0, f"First time 0"
        assert NearEqual(td.translations[1].time, 0.033333), f"Second time 0.03"

        # The second controlled object is a gear, so it has rotations around
        # the Z axis.
        assert cblist[1].node_name == "Gear08", f"Found controller for {cblist[1].node_name}"
        tdgear = cblist[1].interpolator.data
        # assert tdgear.properties.rotationKeyCount > 0, f"Found rotation keys: {tdgear.properties.rotationKeyCount}"
        assert tdgear.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY, f"Found XYZ rotation type: {tdgear.properties.rotationType}"
        assert tdgear.properties.xRotations.interpolation == NiKeyType.LINEAR_KEY, f"X is linear: {tdgear.properties.xRotation.interpolation}"
        assert tdgear.properties.xRotations.numKeys == 1, f"Have one X rotation key:{tdgear.properties.xRotation.numKeys}"
        assert tdgear.properties.zRotations.interpolation == NiKeyType.QUADRATIC_KEY, f"Z is quadratic: {tdgear.properties.xRotation.interpolation}"
        assert tdgear.properties.zRotations.numKeys == 2, f"Have 2 X rotation keys:{tdgear.properties.zRotation.numKeys}"
        assert NearEqual(tdgear.zrotations[1].time, 0.6), f"Found correct time: {tdgear.zrotations[1].time}"

        # Object189 has linear translations but it's been messing up, so check 
        # it directly.
        o189 = [cb for cb in cblist if cb.node_name == "Object189"][0]
        td189 = o189.interpolator.data
        assert VNearEqual(td189.translations[0].value, [-20.966583, -0.159790, 18.576317]), \
            f"Have correct translation: {td189.translations[0].value}"
        assert VNearEqual(td189.translations[2].value, [-20.965717, -0.159790, 18.343819]), \
            f"Have correct translation: {td189.translations[3].value}"
        assert VNearEqual(td189.translations[4].value, [-20.963652, -0.159790, 17.789375]), \
            f"Have correct translation: {td189.translations[3].value}"


    def TEST_ANIMATION_ALDUIN():
        """Animated skinned nif"""
        nif = NifFile(r"tests/SkyrimSE/loadscreenalduinwall.nif")
        tail2 = nif.nodes["NPC Tail2"]
        assert tail2.controller is not None, f"Have transform controller"
        assert tail2.controller.blockname == "NiTransformController", f"Created type correctly"
        tdtail2 = tail2.controller.interpolator.data
        assert tdtail2.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY, f"Have correct rotation type"
        assert tdtail2.properties.xRotations.numKeys == 16, f"Have correct number of keys"
        assert tdtail2.translations[0].time == 0, f"Have 0 time value"
        assert VNearEqual(tdtail2.translations[0].value, [94.485031, 0, 0]), f"Have 0 location value"
        assert tdtail2.translations[15].time == 28.0, f"Have 15 time value"
        assert VNearEqual(tdtail2.translations[15].value, [94.485031, 0, 0]), f"Have 0 location value"
        
        # Lots of these rotations are LINEAR_KEY which means they're coded as a sequence
        # of quaternions.
        thighl = nif.nodes["NPC LLegThigh"]
        tdthighl = thighl.controller.interpolator.data
        assert len(tdthighl.xrotations) == 0, f"Have xrotations"
        assert len(tdthighl.qrotations) == 161, f"Have quat rotations"
        assert NearEqual(tdthighl.qrotations[0].value[0], 0.2911), f"Have correct angle: {tdthighl.qrotations[0].value}"


    def TEST_KF():
        """Read and write KF animation file"""
        nif = NifFile(r"tests/SkyrimSE/1hm_attackpowerright.kf")
        root = nif.rootNode

        # Root node of these KF files is a NiControllerSequence.
        assert root.blockname == "NiControllerSequence", f"Found correct block name: {root.blockname}"
        assert root.name == "1hm_attackpowerright", f"Have root node {root.name}"
        assert len(root.controlled_blocks) == 91, f"Have controlled blocks: {len(root.controlled_blocks)}"

        # Controlled Blocks define what gets animated, which isn't in this file.
        cb = root.controlled_blocks[0]
        assert cb.controller_type == "NiTransformController", f"Have correct controller type: {cb.controller_type}"
        
        # Interpolator and Data define the animation itself.
        ti = cb.interpolator
        td = ti.data
        assert td.properties.rotationType == NiKeyType.QUADRATIC_KEY, f"Have expected rotation type: {td.properties.rotationType}"
        assert len(td.qrotations) == 36, f"Have quadratc rotation keys: {len(td.qrotations)}"

        nifout = NifFile()
        nifout.initialize("SKYRIM", r"tests/Out/TEST_KF.kf", "NiControllerSequence", "testKF")

        rootout = nifout.rootNode
        rootout.properties = root.properties

        # First key: Linear translation.
        tiprops = NiTransformInterpolatorBuf()
        ti = NiTransformInterpolator(file=nifout, parent=nifout.rootNode)
        tdprops = NiTransformDataBuf()
        tdprops.translations.interpolation = NiKeyType.LINEAR_KEY
        td = NiTransformData(file=nifout, props=tdprops, parent=ti)
        td.add_translation_key(0, (-0.029318, -0.229634, 0))

        rootout.add_controlled_block(
            name="NPC Root [Root]",
            interpolator=ti,
            node_name = "NPC Root [Root]",
            controller_type = "NiTransformController")

        # Second key: Quadratic rotation.
        tiprops = NiTransformInterpolatorBuf()
        ti = NiTransformInterpolator(file=nifout, parent=nifout.rootNode)
        tdprops = NiTransformDataBuf()
        tdprops.rotationType = NiKeyType.QUADRATIC_KEY
        td = NiTransformData(file=nifout, props=tdprops, parent=ti)
        td.add_qrotation_key(0, (0.8452, 0.0518, -0.0010, -0.5320))

        rootout.add_controlled_block(
            name="NPC Pelvis [Pelv]",
            interpolator=ti,
            node_name = "NPC Root [Root]",
            controller_type = "NPC Pelvis [Pelv]")

        nifout.save()

        nifcheck = NifFile(r"tests/Out/TEST_KF.kf")
        assert nifcheck.rootNode.blockname == "NiControllerSequence", f"Have correct root node type"
        assert nifcheck.rootNode.name == "testKF", f"Root node has name"
        assert len(nifcheck.rootNode.controlled_blocks) > 0, f"Have controlled blocks {nifcheck.rootNode.controlled_blocks}"

        # Check first controlled block
        cb = nifcheck.rootNode.controlled_blocks[0]
        assert cb.properties.controllerID == NODEID_NONE, f"No controller for this block"
        assert cb.node_name == "NPC Root [Root]", f"Have correct node name"
        assert cb.controller_type == "NiTransformController", f"Have transform controller type"
        assert cb.properties.propType == NODEID_NONE, f"Do NOT have property type"

        # Check first Interpolator/Data pair
        ticheck = cb.interpolator
        tdcheck = ticheck.data
        assert len(tdcheck.translations) > 0, "Have translations"

        # Check second controlled block
        cb2 = nifcheck.rootNode.controlled_blocks[1]
        ti2 = cb2.interpolator
        td2 = ti2.data
        assert len(td2.qrotations) > 0, "Have rotations"

    def TEST_SKEL():
        """Import of skeleton file with collisions"""
        nif = NifFile(r"tests/Skyrim/skeleton_vanilla.nif")
        npc = nif.nodes['NPC']
        assert npc.string_data[0][1] == "Human"

        # COM node has a bhkBlendCollisionObject
        com = nif.nodes['NPC COM [COM ]']
        com_col = com.collision_object
        assert com_col.blockname == "bhkBlendCollisionObject", f"Have collision object: {com.collision_object.blockname}"
        com_col.properties.heirGain == 1.0, f"Have unique property"
        com_shape = com_col.body.shape
        assert NearEqual(com_shape.properties.point1[0], -com_shape.properties.point2[0]), \
            f"Capsule shape symmetric around x-axis."
        assert NearEqual(com_shape.properties.point1[0], 0.041862), f"Have correct X location"
        assert NearEqual(com_shape.properties.bhkRadius, 0.130600), f"Have correct radius"

        # Spine1 node has a ragdoll node, which references two others
        spine1 = nif.nodes['NPC Spine1 [Spn1]']
        spine1_col = spine1.collision_object
        spine1_rb = spine1_col.body
        spine1_rag = spine1_rb.constraints[0]
        assert len(spine1_rag.entities) == 2, f"Have ragdoll entities"

        # The character bumper uses a bhkSimpleShapePhantom, with its own transform.
        bumper = nif.nodes['CharacterBumper']
        bumper_col = bumper.collision_object
        bumper_bod = bumper_col.body
        assert bumper_bod.blockname == "bhkSimpleShapePhantom"
        assert bumper_bod.properties.transform[0][0] != 0, f"Have a transform"


    def TEST_COLLISION_SPHERE():
        """Can read and write sphere collisions"""
        nif = NifFile(r"tests/SkyrimSE\spitpotopen01.nif")

        anchor = nif.nodes["ANCHOR"]
        coll = anchor.collision_object
        collbody = coll.body
        collshape = collbody.shape
        assert collshape.blockname == "bhkSphereShape", f"Have sphere shape: {collshape.blockname}"
        
        hook = nif.nodes["L1_Hook"]
        hook_col = hook.collision_object
        hook_bod = hook_col.body
        assert hook_bod.blockname == "bhkRigidBodyT", "Have RigidBodyT"
        assert hook_bod.properties.bufType == PynBufferTypes.bhkRigidBodyTBufType

    
    def TEST_TREE():
        """Test that the special nodes for trees work correctly."""

        def check_tree(nifcheck):
            assert nifcheck.rootNode.blockname == "BSLeafAnimNode", f"Have correct root node type"

            tree = nifcheck.shapes[0]
            assert tree.blockname == "BSMeshLODTriShape", f"Have correct shape node type"
            assert tree.shader.shaderflags2_test(ShaderFlags2.TREE_ANIM), f"Tree animation set"
            assert tree.properties.vertexCount == 1059, f"Have correct vertex count"
            assert tree.properties.lodSize0 == 1126, f"Have correct lodSize0"

        testfile = ModuleTest.test_file(r"tests\FO4\TreeMaplePreWar01Orange.nif")
        outfile = ModuleTest.test_file(r"tests/Out/TEST_TREE.nif")

        nif = NifFile(testfile)
        check_tree(nif)

        print(f"------------- write")
        nifOut = NifFile()
        nifOut.initialize('FO4', outfile, nif.rootNode.blockname, nif.rootNode.name)
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        nifOut.save()

        print(f"------------- check")
        nifCheck = NifFile(outfile)
        check_tree(nifCheck)


    def TEST_DOCKSTEPSDOWNEND():
        """Test that BSLODTriShape nodes load correctly."""
        def check_dock(nif):
            assert nif.rootNode.blockname == "BSFadeNode", f"Have BSFadeNode as root: {nif.rootNode.blockname}"
            assert len(nif.shapes) == 3, "Have all shapes"
            s = nif.shape_dict["DockStepsDownEnd01:0 - L1_Supports:0"]
            assert s, f"Have supports shape"
            assert s.blockname == "BSLODTriShape", "Have BSLODTriShape"
            assert s.properties.level0 == 234, f"Have correct level0: {s.properties.level0}"
            assert s.properties.level1 == 88, f"Have correct level1: {s.properties.level1}"

        testfile = ModuleTest.test_file(r"tests\Skyrim\dockstepsdownend01.nif")
        outfile = ModuleTest.test_file(r"tests\out\TEST_DOCKSTEPSDOWNEND.nif")

        print("------------- read")
        nif = NifFile(testfile)
        check_dock(nif)

        print("------------- write")
        nifOut = NifFile()
        nifOut.initialize('SKYRIM', outfile, nif.rootNode.blockname, nif.rootNode.name)
        ModuleTest.export_shape(nif.shapes[0], nifOut)
        ModuleTest.export_shape(nif.shapes[1], nifOut)
        ModuleTest.export_shape(nif.shapes[2], nifOut)
        nifOut.save()

        print("------------- check")
        check_dock(NifFile(outfile))


    def TEST_HKX_SKELETON():
        """Test read/write of hkx skeleton files (in XML format)."""
        pass
        # SKIPPING - This functionality is part of animation read/write, which is not
        # fully operational.

        # testfile = ModuleTest.test_file(r"tests/Skyrim/skeleton.hkx")
        # outfile = ModuleTest.test_file(r"tests/Out/TEST_XML_SKELETON.nif")

        # f = hkxSkeletonFile(testfile)
        # assert len(f.nodes) == 99, "Have all bones."
        # assert f.rootNode.name == "NPC Root [Root]"
        # assert len(f.shapes) == 0, "No shapes"
        # assert f.rootName == 'NPC Root [Root]', f"Have root name: {f.rootName}"

        # headbone = f.nodes["NPC Head [Head]"]
        # handbone = f.nodes["NPC L Hand [LHnd]"]
        # assert NearEqual(headbone.global_transform.translation[2], 120.3436), "Head bone where it should be."
        # assert NearEqual(handbone.global_transform.translation[0], -28.9358), f"L Hand bone where it should be" 

    
    @property
    def all_tests(self):
        return [t for k, t in ModuleTest.__dict__.items() if k.startswith('TEST_')]

        
    def execute_test(self, t):
        print(f"\n------------- {t.__name__} -------------")
        # the_test = ModuleTest.__dict__[t]
        print(t.__doc__)
        t()
        print(f"------------- done")

    
    def execute(self, start=None, test=None):
        print("""\n
=====================================================================
======================= Running pynifly tests =======================
=====================================================================

""")
        if test:
            self.execute_test(test)
        else:
            doit = (start is None) 
            for t in self.all_tests:
                if t == start: doit = True
                if doit:
                    self.execute_test(t)

        print("""

============================================================================
======================= TESTS COMPLETED SUCCESSFULLY =======================
============================================================================
""")


if __name__ == "__main__":
    import codecs
    # import quickhull

    # Load from install location
    py_addon_path = os.path.dirname(os.path.realpath(__file__))
    #log.debug(f"PyNifly addon path: {py_addon_path}")
    if py_addon_path not in sys.path:
        sys.path.append(py_addon_path)
    dev_path = os.path.join(py_addon_path, "NiflyDLL.dll")
    hkxcmd_path = os.path.join(py_addon_path, "hkxcmd.exe")
    xmltools.XMLFile.SetPath(hkxcmd_path)

    dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
    NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

    mylog = logging.getLogger("pynifly")
    logging.basicConfig()
    mylog.setLevel(logging.DEBUG)
    tester = ModuleTest(mylog)

    tester.execute()
    # tester.execute(start=ModuleTest.TEST_KF)
    # tester.execute(test=ModuleTest.TEST_LOD)
