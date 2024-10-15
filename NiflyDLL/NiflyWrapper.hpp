// MathLibrary.h - Contains declarations of math functions
#pragma once
#include <string>
#include "BasicTypes.hpp"
#include "Object3d.hpp"
#include "animation.hpp"
#include "niflydefs.hpp"

#ifdef NIFLYDLL_EXPORTS
	#define NIFLY_API __declspec(dllexport)
#else
	#define NIFLY_API __declspec(dllimport)
#endif

extern "C" NIFLY_API const int* getVersion();
extern "C" NIFLY_API void* load(const char8_t* filename);
extern "C" NIFLY_API void* getRoot(void* f);
extern "C" NIFLY_API int getRootName(void* f, char* buf, int len);
extern "C" NIFLY_API int getGameName(void* f, char* buf, int len);
extern "C" NIFLY_API int getAllShapeNames(void* f, char* buf, int len);
extern "C" NIFLY_API int getShapeName(void* theShape, char* buf, int len);
extern "C" NIFLY_API int loadShapeNames(const char* filename, char* buf, int len);
extern "C" NIFLY_API void destroy(void * f);
extern "C" NIFLY_API int getShapeBoneCount(void* theNif, void* theShape);
extern "C" NIFLY_API int getShapeBoneIDs(void* theNif, void* theShape, int* buf, int bufsize);
extern "C" NIFLY_API int getShapeBoneNames(void* theNif, void* theShape, char* buf, int buflen);
extern "C" NIFLY_API int getShapeBoneWeightsCount(void* theNif, void* theShape, int boneIndex);
extern "C" NIFLY_API int getShapeBoneWeights(void* theNif, void* theShape, int boneIndex, VertexWeightPair * buf, int buflen);
extern "C" NIFLY_API int getShapeSkinWeights(void* theNif, void* theShape, int boneIndex, BoneWeight * buf, int buflen);
extern "C" NIFLY_API void addAllBonesToShape(void* nifref, void* shaperef, int boneCount, int* boneIDs);
extern "C" NIFLY_API int getShapes(void* f, void** buf, int len, int start);
void getShape(nifly::NiShape* theShape, NiShapeBuf* buf);
extern "C" NIFLY_API int getShapeBlockName(void* theShape, char* buf, int buflen);
extern "C" NIFLY_API int getVertsForShape(void* theNif, void* theShape, nifly::Vector3* buf, int len, int start);
extern "C" NIFLY_API int getNormalsForShape(void* theNif, void* theShape, nifly::Vector3* buf, int len, int start);
extern "C" NIFLY_API int getTriangles(void* theNif, void* theShape, nifly::Triangle* buf, int len, int start);
extern "C" NIFLY_API bool getShapeGlobalToSkin(void* nifRef, void* shapeRef, nifly::MatTransform* xform);
extern "C" NIFLY_API void calcShapeGlobalToSkin(void* nifRef, void* shapeRef, nifly::MatTransform * xform);
extern "C" NIFLY_API int hasSkinInstance(void* shapeRef);
extern "C" NIFLY_API bool getShapeSkinToBone(void* nifPtr, void* shapePtr, const  char* boneName, nifly::MatTransform& buf);
extern "C" NIFLY_API void setShapeSkinToBone(void* nifPtr, void* shapePtr, const char* boneName, const nifly::MatTransform & buf);
extern "C" NIFLY_API void getTransform(void* theShape, float* buf);
extern "C" NIFLY_API void getNodeTransform(void* theNode, nifly::MatTransform* buf);
extern "C" NIFLY_API int getNodeTransformToGlobal(void* nifref, const char* nodeName, nifly::MatTransform* buf);
extern "C" NIFLY_API int getUVs(void* theNif, void* theShape, nifly::Vector2* buf, int len, int start);
extern "C" NIFLY_API int getNodeCount(void* theNif);
extern "C" NIFLY_API void getNodes(void* theNif, void** buf);
extern "C" NIFLY_API int getBlockname(void* nifref, int blockID, char* buf, int buflen);
extern "C" NIFLY_API int getNodeBlockname(void* node, char* buf, int buflen);
extern "C" NIFLY_API int getNodeFlags(void* node);
extern "C" NIFLY_API void setNodeFlags(void* node, int theFlags);
extern "C" NIFLY_API int getNodeName(void* theNode, char* buf, int buflen);
extern "C" NIFLY_API void* getNodeParent(void* theNif, void* node);
extern "C" NIFLY_API void* createNif(const char* targetGame, const char* rootType, const char* rootName);
extern "C" NIFLY_API void* createNifShapeFromData(void* parentNif, 
	const char* shapeName, 
	void* buffer,
	const nifly::Vector3* verts, 
	const nifly::Vector2* uv_points, 
	const nifly::Vector3* norms, 
	const nifly::Triangle* tris, 
	void* parentRef = nullptr);
extern "C" NIFLY_API void setTransform(void* theShape, nifly::MatTransform* buf);
extern "C" NIFLY_API int getNodeChildren(void* nifRef, int nodeID, int buflen, int* buf);
extern "C" NIFLY_API void* addNode(void* f, const char* name, void* xf, void* parent);
extern "C" NIFLY_API int getBlockID(void* nifref, void* block);
extern "C" NIFLY_API int addBlock(void* f, const char* name, void* buf, int parent);
extern "C" NIFLY_API int getBlock(void* nifref, uint32_t blockID, void* buf);
extern "C" NIFLY_API int setBlock(void* f, int id, void* buf);
extern "C" NIFLY_API void getNode(void* node, NiNodeBuf * buf);
extern "C" NIFLY_API void* getNodeByID(void* theNif, uint32_t theID);
extern "C" NIFLY_API void* findNodeByName(void* theNif, const char* nodeName);
extern "C" NIFLY_API int findBlockByName(void* theNif, const char* nodeName);
extern "C" NIFLY_API int findNodesByType(void* nifRef, void* parentRef, const char* blockname, int buflen, void** buf);
extern "C" NIFLY_API int getMaxStringLen(void* nifref);
extern "C" NIFLY_API int getString(void* nifref, int strid, int buflen, char* buf);
extern "C" NIFLY_API int addString(void* nifref, const char* buf);
extern "C" NIFLY_API void skinShape(void* f, void* shapeRef);
extern "C" NIFLY_API void setShapeVertWeights(void* theFile, void* theShape, int vertIdx, const uint8_t * vertex_bones, const float* vertex_weights);
extern "C" NIFLY_API void setShapeBoneWeightsFlex(void* nifref, void* shaperef, const char* boneName, VertexWeightPair * vertWeightsIn, int vertWeightLen);
extern "C" NIFLY_API void setShapeBoneWeights(void* theFile, void* theShape, const char* boneName, VertexWeightPair * weights, int weightsLen);
extern "C" NIFLY_API void setShapeBoneIDList(void* f, void* shapeRef, int* boneIDList, int listLen);
extern "C" NIFLY_API int saveNif(void* the_nif, const char8_t* filename);
extern "C" NIFLY_API int segmentCount(void* nifref, void* shaperef);
extern "C" NIFLY_API int getSegmentFile(void* nifref, void* shaperef, char* buf, int buflen);
extern "C" NIFLY_API int getSegments(void* nifref, void* shaperef, int* segments, int segLen);
extern "C" NIFLY_API int getSubsegments(void* nifref, void* shaperef, int segID, uint32_t* segments, int segLen);
extern "C" NIFLY_API int getPartitions(void* nifref, void* shaperef, uint16_t* partitions, int partLen);
extern "C" NIFLY_API int getPartitionTris(void* nifref, void* shaperef, uint16_t* tris, int triLen);
extern "C" NIFLY_API void setPartitions(void* nifref, void* shaperef, uint16_t * partData, int partDataLen, uint16_t * tris, int triLen);
extern "C" NIFLY_API void setSegments(void* nifref, void* shaperef, uint16_t * segData, int segDataLen, uint32_t * subsegData, int subsegDataLen, uint16_t * tris, int triLen, const char* filename);
extern "C" NIFLY_API int getColorsForShape(void* nifref, void* shaperef, nifly::Color4* colors, int colorLen);
extern "C" NIFLY_API void setColorsForShape(void* nifref, void* shaperef, nifly::Color4* colors, int colorLen);
extern "C" NIFLY_API int getClothExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getClothExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen);
extern "C" NIFLY_API void setClothExtraData(void* nifref, void* shaperef, char* name, char* buf, int buflen);
extern "C" NIFLY_API void addBoneToSkin(void* anim, const char* boneName, void* xformPtr, const char* parentName);
extern "C" NIFLY_API void addBoneToShape(void * anim, void * theShape, const char* boneName, void* xformPtr, const char* parentName);
extern "C" NIFLY_API void* addBoneToNifShape(void* nifref, void* shaperef, const char* boneName, nifly::MatTransform* xformToParent, const char* parentName);
extern "C" NIFLY_API void setShapeGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr);
extern "C" NIFLY_API void setShapeGlobalToSkin(void* nifref, void* shaperef, nifly::MatTransform* xformBuf);
extern "C" NIFLY_API void setShapeWeights(void * anim, void * theShape, const char* boneName,
	VertexWeightPair * vertWeights, int vertWeightLen, nifly::MatTransform * skinToBoneXform);

extern "C" NIFLY_API int getShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, char* buf, int buflen);
extern "C" NIFLY_API void setShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, const char* buf);

//extern "C" NIFLY_API int getAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr);
//extern "C" NIFLY_API void setAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr);

/* ********************* EXTRA DATA ********************* */
extern "C" NIFLY_API int getStringExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getStringExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen);
extern "C" NIFLY_API void setStringExtraData(void* nifref, void* shaperef, char* name, char* buf);
extern "C" NIFLY_API int getBGExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getBGExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen, uint16_t* ctrlBaseSkelP);
extern "C" NIFLY_API int getConnectPointParent(void* nifref, int index, ConnectPointBuf* buf);
extern "C" NIFLY_API void setConnectPointsParent(void* nifref, int buflen, ConnectPointBuf* buf);
extern "C" NIFLY_API int getConnectPointChild(void* nifref, int index, char* buf);
extern "C" NIFLY_API void setConnectPointsChild(void* nifref, int isSkinned, int buflen, const char* buf);
extern "C" NIFLY_API int getFurnMarker(void* nifref, int index, FurnitureMarkerBuf* buf);
extern "C" NIFLY_API void setFurnMarkers(void* nifref, int buflen, FurnitureMarkerBuf * buf);
extern "C" NIFLY_API int getBSXFlags(void* nifref, int* buf);
extern "C" NIFLY_API void setBGExtraData(void* nifref, void* shaperef, char* name, char* buf, int controlsBaseSkel);

/* ********************* ERROR REPORTING ********************* */
extern "C" NIFLY_API void clearMessageLog();
extern "C" NIFLY_API int getMessageLog(char* buf, int buflen);

/* ********************* COLLISIONS ********************* */
extern "C" NIFLY_API int getRigidBodyConstraints(void* nifref, uint32_t nodeIndex, uint32_t * idList, int buflen);
extern "C" NIFLY_API int getRagdollEntities(void* nifref, uint32_t nodeIndex, uint32_t* idList, int buflen);
extern "C" NIFLY_API void* getCollTarget(void* nifref, void* node);
extern "C" NIFLY_API int setCollConvexVerts(void* nifref, int id, float* verts, int vertcount, float* normals, int normcount);
extern "C" NIFLY_API int getCollShapeVerts(void* nifref, int nodeIndex, float* buf, int buflen);
extern "C" NIFLY_API int getCollShapeNormals(void* nifref, int nodeIndex, float* buf, int buflen);
extern "C" NIFLY_API int getCollListShapeChildren(void* nifref, int nodeIndex, uint32_t * buf, int buflen);
extern "C" NIFLY_API void addCollListChild(void* nifref, const uint32_t id, uint32_t child_id);
extern "C" NIFLY_API int setCollListChildren(void* nifref, const uint32_t id, uint32_t* buf, int buflen);
extern "C" NIFLY_API void setCollConvexTransformShapeChild(void* nifref, const uint32_t id, uint32_t child_id);
int addControllerManager(void* f, const char* name, NiControllerManagerBuf * buf, void* parent);
extern "C" NIFLY_API int getControllerManagerSequences(void* nifref, void* ncmref, int buflen, uint32_t* seqptrs);
extern "C" NIFLY_API int getControllerManagerSeq(void* nifref, int ncmID, int buflen, uint32_t* seqptrs);
extern "C" NIFLY_API void getControllerSequence(void* nifref, uint32_t csID, NiControllerSequenceBuf * buf);
int addControllerSequence(void* nifref, const char* name, NiControllerSequenceBuf* buf);
extern "C" NIFLY_API int getControlledBlocks(void* nifref, uint32_t csID, int buflen, ControllerLinkBuf * blocks);
int addMultiTargetTransformController(void* nifref, NiMultiTargetTransformControllerBuf* buf);
extern "C" NIFLY_API void getAnimKeyQuadXYZ(void* nifref, int tdID, char dimension, int frame, NiAnimKeyQuadXYZBuf * buf);
extern "C" NIFLY_API void addAnimKeyQuadXYZ(void* nifref, int tdID, char dimension, NiAnimKeyQuadXYZBuf * buf);
extern "C" NIFLY_API int getAnimKeyQuadFloat(void* nifref, int tdID, int frame, NiAnimKeyQuadXYZBuf* buf);
extern "C" NIFLY_API void addAnimKeyQuadFloat(void* nifref, int dataBlockID, NiAnimKeyQuadXYZBuf* buf);
extern "C" NIFLY_API void getAnimKeyLinearXYZ(void* nifref, int tdID, char dimension, int frame, NiAnimKeyLinearXYZBuf * buf);
extern "C" NIFLY_API void getAnimKeyLinearQuat(void* nifref, int tdID, int frame, NiAnimKeyLinearQuatBuf * buf);
extern "C" NIFLY_API void addAnimKeyLinearQuat(void* nifref, int tdID, NiAnimKeyLinearQuatBuf * buf);
extern "C" NIFLY_API void getAnimKeyLinearTrans(void* nifref, int tdID, int frame, NiAnimKeyLinearTransBuf * buf);
extern "C" NIFLY_API void getAnimKeyQuadTrans(void* nifref, int tdID, int frame, NiAnimKeyQuadTransBuf * buf);
extern "C" NIFLY_API void addAnimKeyQuadTrans(void* nifref, int tdID, NiAnimKeyQuadTransBuf* buf);
extern "C" NIFLY_API void addAnimKeyLinearTrans(void* nifref, int tdID, NiAnimKeyLinearTransBuf * buf);
extern "C" NIFLY_API int getTransformDataValues(void* nifref, int nodeIndex,
	NiAnimationKeyQuatBuf * qBuf,
	NiAnimationKeyFloatBuf * xRotBuf,
	NiAnimationKeyFloatBuf * yRotBuf,
	NiAnimationKeyFloatBuf * zRotBuf,
	NiAnimationKeyVec3Buf * transBuf,
	NiAnimationKeyFloatBuf * scaleBuf
);
extern "C" NIFLY_API int getExtraData(void* nifref, uint32_t id, const char* extraDataName);
extern "C" NIFLY_API int getAVObjectPaletteObject(
	void* nifref, uint32_t paletteID, int objindex, int namesize, char* name, uint32_t& objid);

extern "C" NIFLY_API int addAVObjectPaletteObject(void* nifref, uint32_t paletteID, char* name, int objid);

extern "C" NIFLY_API int getNiTextKey(void* nifref, uint32_t tkedID, int keyindex, void* b);

extern "C" NIFLY_API int addTextKey(void* nifref, uint32_t tkedID, float time, const char* name);

