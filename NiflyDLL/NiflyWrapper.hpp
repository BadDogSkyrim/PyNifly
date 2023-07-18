// MathLibrary.h - Contains declarations of math functions
#pragma once
#include <string>
#include "Object3d.hpp"
#include "animation.hpp"


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

/* ********************* STRUCTURES ***************** */

enum BSLightingShaderPropertyShaderType : uint32_t {
	BSLSP_DEFAULT = 0,
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
enum class ShaderProperty1 : uint32_t {
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

/* BSLightingShaderProperty Attributes */
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
	float Environment_Map_Scale;
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

/* BSEffectShaderProperty Attributes */
struct BSESPAttrs {
	uint32_t Shader_Flags_1;
	uint32_t Shader_Flags_2;
	float UV_Offset_U;
	float UV_Offset_V;
	float UV_Scale_U;
	float UV_Scale_V;
	uint32_t Tex_Clamp_Mode;
	unsigned char Lighting_Influence;
	unsigned char Env_Map_Min_LOD;
	float Falloff_Start_Angle;
	float Falloff_Stop_Angle;
	float Falloff_Start_Opacity;
	float Falloff_Stop_Opacity;
	float Emissive_Color_R;
	float Emissive_Color_G;
	float Emissive_Color_B;
	float Emissive_Color_A;
	float Emissmive_Mult;
	float Soft_Falloff_Depth;
	float Env_Map_Scale;
};

struct NiNodeBuf {
	uint16_t bufSize;
	uint32_t nameID;
	uint32_t controllerID;
	uint16_t extraDataCount;
	uint32_t flags;
	//MatTransform transform;
	float translation[3];
	float rotation[3][3];
	float scale;
	uint32_t collisionID;
	uint16_t childCount;
	uint16_t effectCount;
};

struct NiShapeBuf {
	uint16_t bufSize;
	uint32_t nameID;
	uint32_t controllerID;
	uint16_t extraDataCount;
	uint32_t flags;
	//MatTransform transform
	float translation[3];
	float rotation[3][3];
	float scale;
	uint16_t propertyCount;
	uint32_t collisionID;
	uint8_t hasVertices;
	uint8_t hasNormals;
	uint8_t hasVertexColors;
	uint8_t hasUV;
	float boundingSphereCenter[3];
	float boundingSphereRadius;
	uint16_t vertexCount;
	uint16_t triangleCount;
	uint32_t skinInstanceID;
	uint32_t shaderPropertyID;
	uint32_t alphaPropertyID;
};

struct AlphaPropertyBuf {
	uint16_t flags;
	uint8_t threshold;
};

struct BHKRigidBodyBuf {
	uint8_t collisionFilter_layer;
	uint8_t collisionFilter_flags;
	uint16_t collisionFilter_group;
	uint8_t broadPhaseType;
	uint32_t prop_data;
	uint32_t prop_size;
	uint32_t prop_flags;
	uint8_t collisionResponse;
	uint8_t unusedByte1 = 0;
	uint16_t processContactCallbackDelay;
	uint32_t unkInt1;
	uint8_t collisionFilterCopy_layer;
	uint8_t collisionFilterCopy_flags;
	uint16_t collisionFilterCopy_group;
	uint16_t unkShorts2[6]{};
	float translation_x;
	float translation_y;
	float translation_z;
	float translation_w;
	float rotation_x;
	float rotation_y;
	float rotation_z;
	float rotation_w;
	float linearVelocity_x;
	float linearVelocity_y;
	float linearVelocity_z;
	float linearVelocity_w;
	float angularVelocity_x;
	float angularVelocity_y;
	float angularVelocity_z;
	float angularVelocity_w;
	float inertiaMatrix[12]{};
	float center_x;
	float center_y;
	float center_z;
	float center_w;
	float mass;
	float linearDamping;
	float angularDamping;
	float timeFactor;	// User Version >= 12
	float gravityFactor; // User Version >= 12
	float friction;
	float rollingFrictionMult; // User Version >= 12
	float restitution;
	float maxLinearVelocity;
	float maxAngularVelocity;
	float penetrationDepth;
	uint8_t motionSystem;
	uint8_t deactivatorType;
	uint8_t solverDeactivation;
	uint8_t qualityType;
	uint8_t autoRemoveLevel;
	uint8_t responseModifierFlag;
	uint8_t numShapeKeysInContactPointProps;
	uint8_t forceCollideOntoPpu;
	uint32_t unusedInts1[3]{};
	uint8_t unusedBytes2[3]{};
	uint32_t bodyFlagsInt;
	uint16_t bodyFlags;
};

struct BHKBoxShapeBuf {
	uint32_t material;
	float radius;
	float dimensions_x;
	float dimensions_y;
	float dimensions_z;
};

struct BHKCapsuleShapeBuf {
	uint32_t material;
	float radius;
	float point1[3];
	float radius1;
	float point2[3];
	float radius2;
};

struct BHKListShapeBuf {
	uint32_t material;
	uint32_t childShape_data;
	uint32_t childShape_size;
	uint32_t childShape_flags;
	uint32_t childFilter_data;
	uint32_t childFilter_size;
	uint32_t childFilter_flags;
};

struct BHKConvexVertsShapeBuf {
	uint32_t material;
	float radius;
	uint32_t vertsProp_data;
	uint32_t vertsProp_size;
	uint32_t vertsProp_flags;
	uint32_t normalsProp_data;
	uint32_t normalsProp_size;
	uint32_t normalsProp_flags;
};

struct BHKConvexTransformShapeBuf {
	uint32_t material;
	float radius;
	float xform[16];
};

struct FurnitureMarkerBuf {
	float offset[3];
	float heading;
	uint16_t animationType;
	uint16_t entryPoints;
};

struct ConnectPointBuf {
	char parent[256];
	char name[256];
	float rotation[4];
	float translation[3];
	float scale;
};

struct NiControllerManagerBuf {
	uint16_t bufSize;
	uint32_t nextControllerID;
	uint16_t flags = 0x000C;
	float frequency = 1.0f;
	float phase = 0.0f;
	float startTime = nifly::NiFloatMax;
	float stopTime = nifly::NiFloatMin;
	uint32_t targetID;
	uint8_t cumulative = 0;
	uint16_t controllerSequenceCount;
	uint32_t objectPaletteID;
};

struct NiMultiTargetTransformControllerBuf {
	uint32_t nextControllerID;
	uint16_t flags = 0x000C;
	float frequency = 1.0f;
	float phase = 0.0f;
	float startTime = nifly::NiFloatMax;
	float stopTime = nifly::NiFloatMin;
	uint32_t targetID;
	uint16_t targetCount;
};

struct NiControllerSequenceBuf {
	uint16_t bufSize;
	uint32_t nameID;
	uint32_t arrayGrowBy = 0;
	uint16_t controlledBlocksCount;
	float weight = 1.0f;
	uint32_t textKeyID;
	uint32_t cycleType = nifly::CYCLE_LOOP;
	float frequency = 0.0f;
	float startTime = 0.0f;
	float stopTime = 0.0f;
	uint32_t managerID;
	uint32_t accumRootNameID;
	uint32_t animNotesID;
	uint16_t animNotesCount;
};

struct ControllerLinkBuf {
	uint16_t bufSize;
	uint32_t interpolatorID;
	uint32_t controllerID;
	uint8_t priority = 0;
	uint32_t nodeName;
	uint32_t propType;
	uint32_t ctrlType;
	uint32_t ctrlID;
	uint32_t interpID;
};

struct NiTransformInterpolatorBuf {
	uint16_t bufSize;
	float translation[3];
	float rotation[4];
	float scale = 0.0f;
	uint32_t dataID;
};

struct NiTransformControllerBuf {
	uint32_t interpolatorIndex;
	uint32_t nextControllerIndex;
	uint16_t flags;
	/* Controller flags.
		Bit 0 : Anim type, 0 = APP_TIME 1 = APP_INIT
		Bit 1 - 2 : Cycle type, 00 = Loop 01 = Reverse 10 = Clamp
		Bit 3 : Active
		Bit 4 : Play backwards
		Bit 5 : Is manager controlled
		Bit 6 : Always seems to be set in Skyrim and Fallout NIFs, unknown function */
	float frequency;
	float phase;
	float startTime;
	float stopTime;
	uint32_t targetIndex;
};

struct NiAnimationKeyQuatBuf {
	uint32_t type;
	float time;
	float value[4];
	float forward[4];
	float backward[4];
	float tbcTension = 0.0f;
	float tbcBias = 0.0f;
	float tbcContinuity = 0.0f;
};

struct NiAnimationKeyVec3Buf {
	uint32_t type;
	float time;
	float value[3];
	float forward[3];
	float backward[3];
	float tbcTension = 0.0f;
	float tbcBias = 0.0f;
	float tbcContinuity = 0.0f;
};

struct NiAnimationKeyFloatBuf {
	uint32_t type;
	float time;
	float value;
	float forward;
	float backward;
	float tbcTension = 0.0f;
	float tbcBias = 0.0f;
	float tbcContinuity = 0.0f;
};

struct NiAnimatinoKeyGroupBuf {
	uint32_t numKeys;
	uint32_t interpolation;
};

struct NiTransformDataBuf {
	uint16_t bufSize;
	uint32_t rotationType;
	uint32_t quaternionKeyCount;
	NiAnimatinoKeyGroupBuf xRotations;
	NiAnimatinoKeyGroupBuf yRotations;
	NiAnimatinoKeyGroupBuf zRotations;
	NiAnimatinoKeyGroupBuf translations;
	NiAnimatinoKeyGroupBuf scales;
};

struct NiAnimKeyLinearTransBuf {
	float time = 0.0f;
	float value[3];
};

struct NiAnimKeyQuadTransBuf {
	float time = 0.0f;
	float value[3];
	float forward[3];
	float backward[3];
};

struct NiAnimKeyLinearXYZBuf {
	float time = 0.0f;
	float value;
};

struct NiAnimKeyQuadXYZBuf {
	float time = 0.0f;
	float value = 0.0f;
	float forward = 0.0f;
	float backward = 0.0f;
};

struct NiAnimKeyLinearQuatBuf {
	float time = 0.0f;
	float value[4];
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
extern "C" NIFLY_API void* getNodeController(void* nifref, void* node, NiControllerManagerBuf * buf);
extern "C" NIFLY_API void* getNodeParent(void* theNif, void* node);
extern "C" NIFLY_API void* createNif(const char* targetGame, const char* rootType, const char* rootName);
extern "C" NIFLY_API void* createNifShapeFromData(void* parentNif, const char* shapeName, const nifly::Vector3* verts, const nifly::Vector2* uv_points, const nifly::Vector3* norms, int vertCount, const nifly::Triangle* tris, int triCount, uint16_t * optionsPtr = nullptr, void* parentRef = nullptr);
extern "C" NIFLY_API void setTransform(void* theShape, nifly::MatTransform* buf);
extern "C" NIFLY_API int getNodeChildren(void* nifRef, int nodeID, int buflen, int* buf);
extern "C" NIFLY_API void* addNode(void* f, const char* name, void* xf, void* parent);
extern "C" NIFLY_API int getBlockID(void* nifref, void* block);
extern "C" NIFLY_API int addBlock(void* f, const char* name, const char* type, void* buf, int parent);
extern "C" NIFLY_API int getBlock(void* nifref, uint32_t blockID, const char* blocktype, void* buf);
extern "C" NIFLY_API void setBlock(void* f, int id, const char* type, void* buf);
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

extern "C" NIFLY_API int getShaderName(void* nifref, void* shaperef, char* buf, int buflen);
extern "C" NIFLY_API uint32_t getShaderFlags1(void* nifref, void* shaperef);
extern "C" NIFLY_API uint32_t getShaderFlags2(void* nifref, void* shaperef);
extern "C" NIFLY_API int getShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, char* buf, int buflen);
extern "C" NIFLY_API uint32_t getShaderType(void* nifref, void* shaperef);
extern "C" NIFLY_API int getShaderAttrs(void* nifref, void* shaperef, BSLSPAttrs* buf);
extern "C" NIFLY_API const char* getShaderBlockName(void* nifref, void* shaperef);
extern "C" NIFLY_API int getEffectShaderAttrs(void* nifref, void* shaperef, BSESPAttrs* buf);
extern "C" NIFLY_API void setShaderName(void* nifref, void* shaperef, char* name);
extern "C" NIFLY_API void setShaderType(void* nifref, void* shaperef, uint32_t shaderType);
extern "C" NIFLY_API void setShaderFlags1(void* nifref, void* shaperef, uint32_t flags);
extern "C" NIFLY_API void setShaderFlags2(void* nifref, void* shaperef, uint32_t flags);
extern "C" NIFLY_API void setShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, const char* buf);

extern "C" NIFLY_API void setShaderAttrs(void* nifref, void* shaperef, BSLSPAttrs* buf);
extern "C" NIFLY_API void setEffectShaderAttrs(void* nifref, void* shaperef, BSESPAttrs* buf);
extern "C" NIFLY_API int getAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr);
extern "C" NIFLY_API void setAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr);

/* ********************* EXTRA DATA ********************* */
extern "C" NIFLY_API int getStringExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getStringExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen);
extern "C" NIFLY_API void setStringExtraData(void* nifref, void* shaperef, char* name, char* buf);
extern "C" NIFLY_API int getBGExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen);
extern "C" NIFLY_API int getBGExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen, uint16_t* ctrlBaseSkelP);
extern "C" NIFLY_API int getInvMarker(void* nifref, char* name, int namelen, int* rot, float* zoom);
extern "C" NIFLY_API int getConnectPointParent(void* nifref, int index, ConnectPointBuf* buf);
extern "C" NIFLY_API void setConnectPointsParent(void* nifref, int buflen, ConnectPointBuf* buf);
extern "C" NIFLY_API int getConnectPointChild(void* nifref, int index, char* buf);
extern "C" NIFLY_API void setConnectPointsChild(void* nifref, int isSkinned, int buflen, const char* buf);
extern "C" NIFLY_API void setInvMarker(void* nifref, const char* name, int* rot, float* zoom);
extern "C" NIFLY_API int getFurnMarker(void* nifref, int index, FurnitureMarkerBuf* buf);
extern "C" NIFLY_API void setFurnMarkers(void* nifref, int buflen, FurnitureMarkerBuf * buf);
extern "C" NIFLY_API int getBSXFlags(void* nifref, int* buf);
extern "C" NIFLY_API void setBSXFlags(void* nifref, const char* name, uint32_t flags);
extern "C" NIFLY_API void setBGExtraData(void* nifref, void* shaperef, char* name, char* buf, int controlsBaseSkel);

/* ********************* ERROR REPORTING ********************* */
extern "C" NIFLY_API void clearMessageLog();
extern "C" NIFLY_API int getMessageLog(char* buf, int buflen);

/* ********************* COLLISIONS ********************* */
extern "C" NIFLY_API void* getCollision(void* nifref, void* noderef);
extern "C" NIFLY_API void* addCollision(void* nifref, void* targetref, int body_index, int flags);
extern "C" NIFLY_API int getCollBlockname(void* node, char* buf, int buflen);
extern "C" NIFLY_API int getCollBodyID(void* nifref, void* node);
extern "C" NIFLY_API int addRigidBody(void* nifref, const char* type, uint32_t collShapeIndex, BHKRigidBodyBuf* buf);
extern "C" NIFLY_API void* getCollTarget(void* nifref, void* node);
extern "C" NIFLY_API int getCollFlags(void* node);
extern "C" NIFLY_API int getCollBodyBlockname(void* nif, int nodeIndex, char* buf, int buflen);
extern "C" NIFLY_API int getRigidBodyProps(void* nifref, int nodeIndex, BHKRigidBodyBuf * buf);
extern "C" NIFLY_API int getRigidBodyShapeID(void* nifref, int nodeIndex);
extern "C" NIFLY_API int getCollShapeBlockname(void* nifref, int nodeIndex, char* buf, int buflen);
extern "C" NIFLY_API int getCollConvexVertsShapeProps(void* nifref, int nodeIndex, BHKConvexVertsShapeBuf* buf);
extern "C" NIFLY_API int addCollConvexVertsShape(void* nifref, const BHKConvexVertsShapeBuf* buf, float* verts, int vertcount, float* normals, int normcount);
extern "C" NIFLY_API int getCollShapeVerts(void* nifref, int nodeIndex, float* buf, int buflen);
extern "C" NIFLY_API int getCollShapeNormals(void* nifref, int nodeIndex, float* buf, int buflen);
extern "C" NIFLY_API int getCollBoxShapeProps(void* nifref, int nodeIndex, BHKBoxShapeBuf* buf);
extern "C" NIFLY_API int addCollBoxShape(void* nifref, const BHKBoxShapeBuf * buf);
extern "C" NIFLY_API int getCollListShapeProps(void* nifref, int nodeIndex, BHKListShapeBuf * buf);
extern "C" NIFLY_API int getCollListShapeChildren(void* nifref, int nodeIndex, uint32_t * buf, int buflen);

extern "C" NIFLY_API int addCollListShape(void* nifref, const BHKListShapeBuf* buf);

extern "C" NIFLY_API void addCollListChild(void* nifref, const uint32_t id, uint32_t child_id);

extern "C" NIFLY_API int setCollListChildren(void* nifref, const uint32_t id, uint32_t* buf, int buflen);

extern "C" NIFLY_API int getCollConvexTransformShapeProps(void* nifref, int nodeIndex, BHKConvexTransformShapeBuf* buf);

extern "C" NIFLY_API int getCollConvexTransformShapeChildID(void* nifref, int nodeIndex);

extern "C" NIFLY_API int addCollConvexTransformShape(void* nifref, const BHKConvexTransformShapeBuf* buf);

extern "C" NIFLY_API void setCollConvexTransformShapeChild(void* nifref, const uint32_t id, uint32_t child_id);

extern "C" NIFLY_API int getCollCapsuleShapeProps(void* nifref, int nodeIndex, BHKCapsuleShapeBuf* buf);

extern "C" NIFLY_API int addCollCapsuleShape(void* nifref, const BHKCapsuleShapeBuf* buf);

extern "C" NIFLY_API void getControllerManager(void* ncmref, NiControllerManagerBuf * buf);
int addControllerManager(void* f, const char* name, NiControllerManagerBuf * buf, void* parent);
extern "C" NIFLY_API int getControllerManagerSequences(void* nifref, void* ncmref, int buflen, uint32_t* seqptrs);
extern "C" NIFLY_API int getControllerManagerSeq(void* nifref, int ncmID, int buflen, uint32_t* seqptrs);
extern "C" NIFLY_API void getControllerSequence(void* nifref, uint32_t csID, NiControllerSequenceBuf * buf);
int addControllerSequence(void* nifref, const char* name, NiControllerSequenceBuf* buf);
extern "C" NIFLY_API int getControlledBlocks(void* nifref, uint32_t csID, int buflen, ControllerLinkBuf * blocks);
extern "C" NIFLY_API void addControlledBlock(void* nifref, uint32_t csID, const char* name, ControllerLinkBuf * b);
extern "C" NIFLY_API void getMultiTargetTransformController(void* nifref, int mttcID, NiMultiTargetTransformControllerBuf * buf);
int addMultiTargetTransformController(void* nifref, NiMultiTargetTransformControllerBuf* buf);
extern "C" NIFLY_API int getTransformController(void* nifref, int nodeIndex, NiTransformControllerBuf* buf);
extern "C" NIFLY_API int addTransformController(void* nifref, NiTransformControllerBuf * buf, int parent);
void getTransformInterpolator(void* nifref, uint32_t tiID, NiTransformInterpolatorBuf * buf);
int addTransformInterpolator(void* nifref, NiTransformInterpolatorBuf* buf);
int getTransformData(void* nifref, int nodeIndex, NiTransformDataBuf * buf);
int addTransformData(void* nifref, NiTransformDataBuf* buf, int parent);
extern "C" NIFLY_API void getAnimKeyQuadXYZ(void* nifref, int tdID, char dimension, int frame, NiAnimKeyQuadXYZBuf * buf);
extern "C" NIFLY_API void addAnimKeyQuadXYZ(void* nifref, int tdID, char dimension, NiAnimKeyQuadXYZBuf * buf);
extern "C" NIFLY_API void getAnimKeyLinearXYZ(void* nifref, int tdID, char dimension, int frame, NiAnimKeyLinearXYZBuf * buf);
extern "C" NIFLY_API void getAnimKeyLinearQuat(void* nifref, int tdID, int frame, NiAnimKeyLinearQuatBuf * buf);
extern "C" NIFLY_API void addAnimKeyLinearQuat(void* nifref, int tdID, NiAnimKeyLinearQuatBuf * buf);
extern "C" NIFLY_API void getAnimKeyLinearTrans(void* nifref, int tdID, int frame, NiAnimKeyLinearTransBuf * buf);
extern "C" NIFLY_API void getAnimKeyQuadTrans(void* nifref, int tdID, int frame, NiAnimKeyQuadTransBuf * buf);
extern "C" NIFLY_API void addAnimKeyLinearTrans(void* nifref, int tdID, NiAnimKeyLinearTransBuf * buf);
extern "C" NIFLY_API int getTransformDataValues(void* nifref, int nodeIndex,
	NiAnimationKeyQuatBuf * qBuf,
	NiAnimationKeyFloatBuf * xRotBuf,
	NiAnimationKeyFloatBuf * yRotBuf,
	NiAnimationKeyFloatBuf * zRotBuf,
	NiAnimationKeyVec3Buf * transBuf,
	NiAnimationKeyFloatBuf * scaleBuf
);