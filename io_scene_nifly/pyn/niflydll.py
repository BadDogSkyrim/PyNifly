"""
NiflyDLL loader - handles loading and configuring the NiflyDLL.dll library
"""

import os
import sys
import logging
from ctypes import *
from .niflytools import *
from .nifdefs import *

# Locate the DLL and other files we need either in their development or install locations.
nifly_path = None
pynifly_dev_root = None
pynifly_dev_path = None
pynifly_addon_path = None

if 'PYNIFLY_DEV_ROOT' in os.environ:
    pynifly_addon_path = os.path.dirname(os.path.realpath(__file__))
    pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
    pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\io_scene_nifly")
    nifly_path = os.path.join(pynifly_dev_root, r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll")
    logging.getLogger("pynifly").setLevel(logging.DEBUG)
else:
    pynifly_addon_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    logging.getLogger("pynifly").setLevel(logging.INFO)

if nifly_path and os.path.exists(nifly_path):
    if pynifly_dev_path not in sys.path:
        sys.path.insert(0, pynifly_dev_path)
else:
    # Load from install location
    if pynifly_addon_path not in sys.path:
        sys.path.append(pynifly_addon_path)
    nifly_path = os.path.join(pynifly_addon_path, "NiflyDLL.dll")

# Load and configure the library
nifly = cdll.LoadLibrary(nifly_path)

# Configure all the function signatures
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
nifly.addAllBonesToShape.argtypes = [c_void_p, c_void_p, c_int, POINTER(c_int)]
nifly.addAllBonesToShape.restype = None
nifly.addFurnitureMarkerPosition.argtypes = [c_void_p, c_int, POINTER(FurnitureMarkerDataBuf)]
nifly.addFurnitureMarkerPosition.restype = c_int
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
nifly.findBlockByName.argtypes = [c_void_p, c_char_p]
nifly.findBlockByName.restype = c_int
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
nifly.getBoneLODInfo.argtypes = [c_void_p, c_int, c_void_p, c_int]
nifly.getBoneLODInfo.restype = c_int
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
nifly.getControllerManagerSeq.argtypes = [c_void_p, c_int, c_int, POINTER(c_uint32)]
nifly.getControllerManagerSeq.restype = c_int
nifly.getControlledBlocks.argtypes = [c_void_p, c_int, c_int, c_void_p]
nifly.getControlledBlocks.restype = c_int
nifly.getExtraTargets.argtypes = [c_void_p, c_uint32, c_int, POINTER(c_uint32)]
nifly.getExtraTargets.restype = c_int
nifly.getTransformDataValues.argtypes = [c_void_p, c_int, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p]
nifly.getTransformDataValues.restype = c_int
nifly.getExtraData.argtypes = [c_void_p, c_int, c_char_p, c_char_p, c_int]
nifly.getExtraData.restype = c_uint32
nifly.getFurnitureMarkerPosition.argtypes = [c_void_p, c_int, c_int, POINTER(FurnitureMarkerDataBuf)]
nifly.getFurnitureMarkerPosition.restype = c_int
nifly.getGameName.argtypes = [c_void_p, c_char_p, c_int]
nifly.getGameName.restype = c_int
nifly.getVersion.argtypes = []
nifly.getVersion.restype = POINTER(c_int)
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
nifly.getNodeChildren.argtypes = [c_void_p, c_int, c_int, POINTER(c_int)]
nifly.getNodeChildren.restype = c_int
nifly.getNodeCount.argtypes = [c_void_p]
nifly.getNodeCount.restype = c_int
nifly.getNodeFlags.argtypes = [c_void_p]
nifly.getNodeFlags.restype = c_int
nifly.getNodeName.argtypes = [c_void_p, c_void_p, c_int]
nifly.getNodeName.restype = c_int
nifly.getNodeParent.argtypes = [c_void_p, c_void_p]
nifly.getNodeParent.restype = c_void_p
nifly.getNodes.argtypes = [c_void_p, c_void_p]
nifly.getNodes.restype = None
nifly.getNodeTransformToGlobal.argtypes = [c_void_p, c_char_p, POINTER(TransformBuf)]
nifly.getNodeTransformToGlobal.restype = c_int
nifly.getNodeTransform.argtypes = [c_void_p, POINTER(TransformBuf)]
nifly.getNodeTransform.restype = None
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
nifly.getShapeBlockName.argtypes = [c_void_p, c_char_p, c_int]
nifly.getShapeBlockName.restype = c_int
nifly.getShapeBoneCount.argtypes = [c_void_p, c_void_p]
nifly.getShapeBoneCount.restype = c_int
nifly.getShapeBoneIDs.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
nifly.getShapeBoneIDs.restype = c_int
nifly.getShapeBoneNames.argtypes = [c_void_p, c_void_p, c_char_p, c_int]
nifly.getShapeBoneNames.restype = c_int
nifly.getShapeBoneWeights.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_int]
nifly.getShapeBoneWeights.restype = c_int
nifly.getShapeSkinWeights.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_int]
nifly.getShapeSkinWeights.restype = c_int
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
nifly.loadShapeNames.argtypes = [c_char_p, c_char_p, c_int]
nifly.loadShapeNames.restype = c_int
nifly.saveNif.argtypes = [c_void_p, c_char_p]
nifly.saveNif.restype = c_int
nifly.segmentCount.argtypes = [c_void_p, c_void_p]
nifly.segmentCount.restype = c_int
nifly.setBGExtraData.argtypes = [c_void_p, c_void_p, c_char_p, c_char_p, c_int]
nifly.setBGExtraData.restype = None
nifly.setBlock.argtypes = [c_void_p, c_int, c_void_p] 
nifly.setBlock.restype = c_int
nifly.setBoneLOD.argtypes = [c_void_p, c_int, c_int, c_void_p]
nifly.setBoneLOD.restype = c_int
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
nifly.setIntegerExtraData.argtypes = [c_void_p, c_void_p, c_char_p, c_uint32]
nifly.setIntegerExtraData.restype = None
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

# Set up pynStructure globals
pynStructure.nifly = nifly
pynStructure.logger = logging.getLogger("pynifly")