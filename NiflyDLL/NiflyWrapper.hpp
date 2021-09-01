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
extern "C" NIFLY_API int getShapes(void* f, void** buf, int len, int start);
extern "C" NIFLY_API int getShapeBlockName(void* theShape, char* buf, int buflen);
extern "C" NIFLY_API int getVertsForShape(void* theNif, void* theShape, float* buf, int len, int start);
extern "C" NIFLY_API int getNormalsForShape(void* theNif, void* theShape, float* buf, int len, int start);
//extern "C" NIFLY_API int getRawVertsForShape(void* theNif, void* theShape, float* buf, int len, int start);
extern "C" NIFLY_API int getTriangles(void* theNif, void* theShape, uint16_t* buf, int len, int start);
extern "C" NIFLY_API void* makeGameSkeletonInstance(const char* gameName);
extern "C" NIFLY_API void* makeSkeletonInstance(const char* skelPath, const char* rootName);
extern "C" NIFLY_API void* loadSkinForNif(void* nifRef, const char* game);
extern "C" NIFLY_API void* loadSkinForNifSkel(void* nifRef, void* skel);
extern "C" NIFLY_API bool getShapeGlobalToSkin(void* nifRef, void* shapeRef, float* xform);
extern "C" NIFLY_API void getGlobalToSkin(void* nifSkinRef, void* shapeRef, void* xform);
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
extern "C" NIFLY_API void* createNifShapeFromData(void* parentNif,
	const char* shapeName,
	const float* verts,
	const float* uv_points,
	const float* norms,
	int vertCount,
	const uint16_t * tris, int triCount,
	uint16_t * optionsPtr);
extern "C" NIFLY_API void setTransform(void* theShape, void* buf);
extern "C" NIFLY_API int addNode(void* f, const char* name, const nifly::MatTransform* xf, void* parent);
extern "C" NIFLY_API void skinShape(void* f, void* shapeRef);
extern "C" NIFLY_API void getBoneSkinToBoneXform(void* animPtr, const char* shapeName, const char* boneName, float* xform);
extern "C" NIFLY_API void setShapeVertWeights(void* theFile, void* theShape, int vertIdx, const uint8_t * vertex_bones, const float* vertex_weights);
extern "C" NIFLY_API void setShapeBoneWeights(void* theFile, void* theShape, int boneIdx, VertexWeightPair * weights, int weightsLen);
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
extern "C" NIFLY_API int getColorsForShape(void* nifref, void* shaperef, float* colors, int colorLen);
extern "C" NIFLY_API void setColorsForShape(void* nifref, void* shaperef, float* colors, int colorLen);
extern "C" NIFLY_API void* createSkinForNif(void* nifPtr, const char* gameName);
extern "C" NIFLY_API void setGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr);
extern "C" NIFLY_API void addBoneToShape(void * anim, void * theShape, const char* boneName, void* xformPtr);
extern "C" NIFLY_API void setShapeGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr);
extern "C" NIFLY_API void setShapeWeights(void * anim, void * theShape, const char* boneName,
	VertexWeightPair * vertWeights, int vertWeightLen, nifly::MatTransform * skinToBoneXform);
extern "C" NIFLY_API int saveSkinnedNif(void * anim, const char8_t* filepath);

/* ********************* SHADERS ***************** */

enum BSLightingShaderPropertyShaderType : uint32_t {
	BSLSP_DEFAULT=0,
	BSLSP_ENVMAP,
	BSLSP_GLOWMAP,
	BSLSP_PARALLAX,
	BSLSP_FACE,
	BSLSP_SKINTINT,
	BSLSP_HAIRTINT,
	BSLSP_PARALLAXOCC,
	BSLSP_MULTITEXTURELANDSCAPE,
	BSLSP_LODLANDSCAPE,
	BSLSP_SNOW,
	BSLSP_MULTILAYERPARALLAX,
	BSLSP_TREEANIM,
	BSLSP_LODOBJECTS,
	BSLSP_MULTIINDEXSNOW,
	BSLSP_LODOBJECTSHD,
	BSLSP_EYE,
	BSLSP_CLOUD,
	BSLSP_LODLANDSCAPENOISE,
	BSLSP_MULTITEXTURELANDSCAPELODBLEND,
	BSLSP_DISMEMBERMENT
}; 
enum class ShaderProperty1: uint32_t {
    SPECULAR = 1,
    SKINNED = 1 << 1,
    TEMP_REFRACTION = 1 << 2,
    VERTEX_ALPHA = 1 << 3,
    GREYSCALE_COLOR = 1 << 4,
    GREYSCALE_ALPHA = 1 << 5,
    USE_FALLOFF = 1 << 6,
    ENVIRONMENT_MAPPING = 1 << 7,
    RECEIVE_SHADOWS = 1 << 8,
    CAST_SHADOWS = 1 << 9,
    FACEGEN_DETAIL_MAP = 1 << 10,
    PARALLAX = 1 << 11,
    MODEL_SPACE_NORMALS = 1 << 12,
    NON_PROJECTIVE_SHADOWS = 1 << 13,
    LANDSCAPE = 1 << 14,
    REFRACTION = 1 << 15,
    FIRE_REFRACTION = 1 << 16,
    EYE_ENVIRONMENT_MAPPING = 1 << 17,
    HAIR_SOFT_LIGHTING = 1 << 18,
    SCREENDOOR_ALPHA_FADE = 1 << 19,
    LOCALMAP_HIDE_SECRET = 1 << 20,
    FACEGEN_RGB_TINT = 1 << 21,
    OWN_EMIT = 1 << 22,
    PROJECTED_UV = 1 << 23,
    MULTIPLE_TEXTURES = 1 << 24,
    REMAPPABLE_TEXTURES = 1 << 25,
    DECAL = 1 << 26,
    DYNAMIC_DECAL = 1 << 27,
    PARALLAX_OCCLUSION = 1 << 28,
    EXTERNAL_EMITTANCE = 1 << 29,
    SOFT_EFFECT = 1 << 30,
    ZBUFFER_TEST = uint32_t(1 << 31)
};

enum class ShaderProperty2 : uint32_t {
	ZBUFFER_WRITE = 1,
	LOD_LANDSCAPE = 1 << 1,
	LOD_OBJECTS = 1 << 2,
	NO_FADE = 1 << 3,
	DOUBLE_SIDED = 1 << 4,
	VERTEX_COLORS = 1 << 5,
	GLOW_MAP = 1 << 6,
	ASSUME_SHADOWMASK = 1 << 7,
	PACKED_TANGENT = 1 << 8,
	MULTI_INDEX_SNOW = 1 << 9,
	VERTEX_LIGHTING = 1 << 10,
	UNIFORM_SCALE = 1 << 11,
	FIT_SLOPE = 1 << 12,
	BILLBOARD = 1 << 13,
	NO_LOD_LAND_BLEND = 1 << 14,
	ENVMAP_LIGHT_FADE = 1 << 15,
	WIREFRAME = 1 << 16,
	WEAPON_BLOOD = 1 << 17,
	HIDE_ON_LOCAL_MAP = 1 << 18,
	PREMULT_ALPHA = 1 << 19,
	CLOUD_LOD = 1 << 20,
	ANISOTROPIC_LIGHTING = 1 << 21,
	NO_TRANSPARENCY_MULTISAMPLING = 1 << 22,
	UNUSED01 = 1 << 23,
	MULTI_LAYER_PARALLAX = 1 << 24,
	SOFT_LIGHTING = 1 << 25,
	RIM_LIGHTING = 1 << 26,
	BACK_LIGHTING = 1 << 27,
	UNUSED02 = 1 << 28,
	TREE_ANIM = 1 << 29,
	EFFECT_LIGHTING = 1 << 30,
	HD_LOD_OBJECTS = uint32_t(1 << 31)
};

enum class BSLSPShaderType : uint32_t {
	Default = 0,
	Environment_Map,
	Glow_Shader,
	Parallax,
	Face_Tint,
	Skin_Tint,
	Hair_Tint,
	Parallax_Occ,
	Multitexture_Landscape,
	LOD_Landscape,
	Snow,
	MultiLayer_Parallax,
	Tree_Anim,
	LOD_Objects,
	Sparkle_Snow,
	LOD_Objects_HD,
	Eye_Envmap,
	Cloud,
	LOD_Landscape_Noise,
	Multitexture_Landscape_LOD_Blend,
	FO4_Dismemberment
};

struct BSLSPAttrs {
	uint32_t Shader_Type;
	uint32_t Shader_Flags_1;
	uint32_t Shader_Flags_2;
	float UV_Offset_U;
	float UV_Offset_V;
	float UV_Scale_U;
	float UV_Scale_V;
	float Emissive_Color_R;
	float Emissive_Color_G;
	float Emissive_Color_B;
	float Emissive_Color_A;
	float Emissmive_Mult;
	uint32_t Tex_Clamp_Mode;
	float Alpha;
	float Refraction_Str;
	float Glossiness;
	float Spec_Color_R;
	float Spec_Color_G;
	float Spec_Color_B;
	float Spec_Str;
	float Soft_Lighting;
	float Rim_Light_Power;
	float Skin_Tint_Alpha;
	float Skin_Tint_Color_R;
	float Skin_Tint_Color_G;
	float Skin_Tint_Color_B;
};

struct AlphaPropertyBuf {
	uint16_t flags;
	uint8_t threshold;
};

extern "C" NIFLY_API int getShaderName(void* nifref, void* shaperef, char* buf, int buflen);
extern "C" NIFLY_API uint32_t getShaderFlags1(void* nifref, void* shaperef);
extern "C" NIFLY_API uint32_t getShaderFlags2(void* nifref, void* shaperef);
extern "C" NIFLY_API int getShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, char* buf, int buflen);
extern "C" NIFLY_API uint32_t getShaderType(void* nifref, void* shaperef);
extern "C" NIFLY_API void getShaderAttrs(void* nifref, void* shaperef, BSLSPAttrs* buf);
extern "C" NIFLY_API void setShaderName(void* nifref, void* shaperef, char* name);
extern "C" NIFLY_API void setShaderType(void* nifref, void* shaperef, uint32_t shaderType);
extern "C" NIFLY_API void setShaderFlags1(void* nifref, void* shaperef, uint32_t flags);
extern "C" NIFLY_API void setShaderFlags2(void* nifref, void* shaperef, uint32_t flags);
extern "C" NIFLY_API void setShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, const char* buf);

extern "C" NIFLY_API void setShaderAttrs(void* nifref, void* shaperef, BSLSPAttrs* buf);
extern "C" NIFLY_API int getAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr);
extern "C" NIFLY_API void setAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr);

/* ********************* EXTRA DATA ********************* */
extern "C" NIFLY_API int getStringExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getStringExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen);
extern "C" NIFLY_API void setStringExtraData(void* nifref, void* shaperef, char* name, char* buf);
extern "C" NIFLY_API int getBGExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getBGExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen);
extern "C" NIFLY_API void setBGExtraData(void* nifref, void* shaperef, char* name, char* buf);

/* ********************* ERROR REPORTING ********************* */
extern "C" NIFLY_API void clearMessageLog();
extern "C" NIFLY_API int getMessageLog(char* buf, int buflen);
