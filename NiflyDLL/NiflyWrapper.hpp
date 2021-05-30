// MathLibrary.h - Contains declarations of math functions
#pragma once
#include <string>
#include "Object3d.hpp"


#ifdef NIFLYDLL_EXPORTS
	#define NIFLY_API __declspec(dllexport)
#else
	#define NIFLY_API __declspec(dllimport)
#endif

class INifFile {
public:
	virtual void getShapeNames(char* buf, int len) = 0;
	virtual void destroy() = 0;
};

struct VertexWeightPair {
	uint16_t vertex;
	float weight;
};

struct BoneWeight {
	uint16_t bone_index;
	float weight;
};

extern "C" NIFLY_API int getVersion();
extern "C" NIFLY_API void* load(const char* filename);
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
extern "C" NIFLY_API int getShapes(void* f, void** buf, int len, int start);
extern "C" NIFLY_API int getVertsForShape(void* theNif, void* theShape, float* buf, int len, int start);
extern "C" NIFLY_API int getNormalsForShape(void* theNif, void* theShape, float* buf, int len, int start);
//extern "C" NIFLY_API int getRawVertsForShape(void* theNif, void* theShape, float* buf, int len, int start);
extern "C" NIFLY_API int getTriangles(void* theNif, void* theShape, uint16_t* buf, int len, int start);
extern "C" NIFLY_API bool getShapeGlobalToSkin(void* nifRef, void* shapeRef, float* xform);
extern "C" NIFLY_API void getGlobalToSkin(void* nifRef, void* shapeRef, void* xform);
extern "C" NIFLY_API int hasSkinInstance(void* shapeRef);
extern "C" NIFLY_API bool getShapeSkinToBone(void* nifPtr, void* shapePtr, const char* boneName, float* xform);
extern "C" NIFLY_API void getTransform(void* theShape, float* buf);
extern "C" NIFLY_API void getNodeTransform(void* theNode, float* buf);
extern "C" NIFLY_API int getUVs(void* theNif, void* theShape, float* buf, int len, int start);
extern "C" NIFLY_API int getNodeCount(void* theNif);
extern "C" NIFLY_API void getNodes(void* theNif, void** buf);
extern "C" NIFLY_API int getNodeName(void* theNode, char* buf, int buflen);
extern "C" NIFLY_API void* getNodeParent(void* theNif, void* node);
extern "C" NIFLY_API void getNodeXformToGlobal(void* anim, const char* boneName, float* xformBuf);
extern "C" NIFLY_API void* createNif(const char* targetGame);
extern "C" NIFLY_API void* createNifShapeFromData(void* parentNif, const char* shapeName, 
	const float* verts, int verts_len, const uint16_t* tris, int tris_len, 
	const float* uv_points, int uv_len, const float* norms, int norms_len,
	uint16_t *options);
extern "C" NIFLY_API void setTransform(void* theShape, float* buf);
extern "C" NIFLY_API int addNode(void* f, const char* name, const nifly::MatTransform* xf, void* parent);
extern "C" NIFLY_API void skinShape(void* f, void* shapeRef);
extern "C" NIFLY_API void getBoneSkinToBoneXform(void* animPtr, const char* shapeName, const char* boneName, float* xform);
extern "C" NIFLY_API void setShapeVertWeights(void* theFile, void* theShape, int vertIdx, const uint8_t * vertex_bones, const float* vertex_weights);
extern "C" NIFLY_API void setShapeBoneWeights(void* theFile, void* theShape, int boneIdx, VertexWeightPair * weights, int weightsLen);
extern "C" NIFLY_API void setShapeBoneIDList(void* f, void* shapeRef, int* boneIDList, int listLen);
extern "C" NIFLY_API int saveNif(void* the_nif, const char* filename);
extern "C" NIFLY_API int segmentCount(void* nifref, void* shaperef);
extern "C" NIFLY_API int getSegmentFile(void* nifref, void* shaperef, char* buf, int buflen);
extern "C" NIFLY_API int getSegments(void* nifref, void* shaperef, int* segments, int segLen);
extern "C" NIFLY_API int getSubsegments(void* nifref, void* shaperef, int segID, uint32_t* segments, int segLen);
extern "C" NIFLY_API int getPartitions(void* nifref, void* shaperef, uint16_t* partitions, int partLen);
extern "C" NIFLY_API int getPartitionTris(void* nifref, void* shaperef, uint16_t* tris, int triLen);
extern "C" NIFLY_API void setPartitions(void* nifref, void* shaperef, uint16_t * partData, int partDataLen, uint16_t * tris, int triLen);
extern "C" NIFLY_API void setSegments(void* nifref, void* shaperef, uint16_t * segData, int segDataLen, uint32_t * subsegData, int subsegDataLen, uint16_t * tris, int triLen, const char* filename);
extern "C" NIFLY_API int getColorsForShape(void* nifref, void* shaperef, float* colors, int colorLen);
extern "C" NIFLY_API void setColorsForShape(void* nifref, void* shaperef, float* colors, int colorLen);
extern "C" NIFLY_API void* createSkinForNif(void* nifPtr, const char* gameName);
extern "C" NIFLY_API void setGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr);
extern "C" NIFLY_API void addBoneToShape(void * anim, void * theShape, const char* boneName, void* xformPtr);
extern "C" NIFLY_API void setShapeGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr);
extern "C" NIFLY_API void setShapeWeights(void * anim, void * theShape, const char* boneName,
	VertexWeightPair * vertWeights, int vertWeightLen, nifly::MatTransform * skinToBoneXform);
extern "C" NIFLY_API int saveSkinnedNif(void * anim, const char* filepath);
