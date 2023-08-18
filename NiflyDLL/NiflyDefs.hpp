// MathLibrary.h - Contains declarations of math functions
#pragma once
#include <string>
#include "BasicTypes.hpp"
#include "Object3d.hpp"
#include "animation.hpp"


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

enum BUFFER_TYPES : uint16_t {
	NiNodeBufType = 0, // Used for NiNode and BSFadeNode
	NiShapeBufType,
	NiCollisionObjectBufType,
	bhkNiCollisionObjectBufType,
	bhkPCollisionObjectBufType,
	bhkSPCollisionObjectBufType,
	bhkRigidBodyBufType,
	bhkRigidBodyTBufType,
	bhkBoxShapeBufType,
	NiControllerManagerBufType,
	NiControllerSequenceBufType,
	NiTransformInterpolatorBufType,
	NiTransformDataBufType,
	NiControllerLinkBufType,
	BSInvMarkerBufType,
	BSXFlagsBufType,
	NiMultiTargetTransformControllerBufType,
	NiTransformControllerBufType,
	bhkCollisionObjectBufType,
	bhkCapsuleShapeBufType,
	bhkConvexTransformShapeBufType,
	bhkConvexVerticesShapeBufType,
	bhkListShapeBufType,
	bhkBlendCollisionObjectBufType,
	bhkRagdollConstraintBufType,
	bhkSimpleShapePhantomBufType,
	bhkSphereShapeBufType,
	BSMeshLODTriShapeBufType,
	NiShaderBufType,
	NiAlphaPropertyBufType,
	BSDynamicTriShapeBufType,
	BSTriShapeBufType,
	BSSubIndexTriShapeBufType,
	BSEffectShaderPropertyBufType
};

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

/* To make it simpler to deal with shaders, there's only one buffer for all of them.
Fields will be filled out depending on type.
*/
struct NiShaderBuf {
	uint16_t bufSize = sizeof(NiShaderBuf);
	uint16_t bufType = BUFFER_TYPES::NiShaderBufType;
	uint32_t nameID;
	uint32_t controllerID;
	uint16_t extraDataCount;
	/* BSShaderPropertyBuf */
	uint32_t Shader_Type;
	uint32_t Shader_Flags_1;
	uint32_t Shader_Flags_2;
	float Env_Map_Scale;
	float UV_Offset_U;
	float UV_Offset_V;
	float UV_Scale_U;
	float UV_Scale_V;
	uint32_t Tex_Clamp_Mode;
	float Emissive_Color_R;
	float Emissive_Color_G;
	float Emissive_Color_B;
	float Emissive_Color_A;
	float Emissmive_Mult;
	/* BSLightingShaderProperty */
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
	/* BSEffectShaderProperty */
	unsigned char Lighting_Influence;
	unsigned char Env_Map_Min_LOD;
	float Falloff_Start_Angle;
	float Falloff_Stop_Angle;
	float Falloff_Start_Opacity;
	float Falloff_Stop_Opacity;
	float Soft_Falloff_Depth;
};

struct BlockBuf {
	uint16_t bufSize = sizeof(BlockBuf);
	uint16_t bufType = -1;
};

struct NiNodeBuf {
	uint16_t bufSize = sizeof(NiNodeBuf);
	uint16_t bufType = BUFFER_TYPES::NiNodeBufType;
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

struct BSInvMarkerBuf {
	uint16_t bufSize = sizeof(BSInvMarkerBuf);
	uint16_t bufType = BUFFER_TYPES::BSInvMarkerBufType;
	uint32_t nameID;
	uint16_t stringRefCount;
	uint16_t rot[3];
	float zoom = 1.0f;
};

struct BSXFlagsBuf {
	uint16_t bufSize = sizeof(BSXFlagsBuf);
	uint16_t bufType = BUFFER_TYPES::BSXFlagsBufType;
	uint32_t nameID;
	uint16_t stringRefCount;
	uint32_t integerData;
};

struct NiShapeBuf {
	uint16_t bufSize = sizeof(NiShapeBuf);
	uint16_t bufType = BUFFER_TYPES::NiShapeBufType;
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

struct BSMeshLODTriShapeBuf : NiShapeBuf {
	uint32_t lodSize0 = 0;
	uint32_t lodSize1 = 0;
	uint32_t lodSize2 = 0;
};

struct NiAlphaPropertyBuf {
	uint16_t bufSize = sizeof(NiAlphaPropertyBuf);
	uint16_t bufType = BUFFER_TYPES::NiAlphaPropertyBufType;
	uint32_t nameID;
	uint32_t controllerID;
	uint16_t extraDataCount;
	uint16_t flags;
	uint8_t threshold;
};

struct NiCollisionObjectBuf {
	uint16_t bufSize = sizeof(NiCollisionObjectBuf);
	uint16_t bufType = BUFFER_TYPES::NiCollisionObjectBufType;
	uint32_t targetID;
};

struct bhkNiCollisionObjectBuf {
	uint16_t bufSize = sizeof(bhkNiCollisionObjectBuf);
	uint16_t bufType = BUFFER_TYPES::bhkNiCollisionObjectBufType;
	uint32_t targetID;
	uint16_t flags;
	uint32_t bodyID;
	uint16_t childCount;
};

struct bhkCollisionObjectBuf {
	uint16_t bufSize = sizeof(bhkNiCollisionObjectBuf);
	uint16_t bufType = BUFFER_TYPES::bhkCollisionObjectBufType;
	uint32_t targetID;
	uint16_t flags;
	uint32_t bodyID;
	uint16_t childCount;
};

struct bhkBlendCollisionObjectBuf {
	uint16_t bufSize = sizeof(bhkBlendCollisionObjectBuf);
	uint16_t bufType = BUFFER_TYPES::bhkBlendCollisionObjectBufType;
	uint32_t targetID;
	uint16_t flags;
	uint32_t bodyID;
	uint16_t childCount;
	float heirGain;
	float velGain;
};

struct bhkPCollisionObjectBuf {
	uint16_t bufSize = sizeof(bhkPCollisionObjectBuf);
	uint16_t bufType = BUFFER_TYPES::bhkPCollisionObjectBufType;
	uint32_t targetID;
	uint16_t flags;
	uint32_t bodyID;
	uint16_t childCount;
};

struct bhkSPCollisionObjectBuf {
	uint16_t bufSize = sizeof(bhkSPCollisionObjectBuf);
	uint16_t bufType = BUFFER_TYPES::bhkSPCollisionObjectBufType;
	uint32_t targetID;
	uint16_t flags;
	uint32_t bodyID;
	uint16_t childCount;
};

struct bhkRigidBodyBuf {
	uint16_t bufSize = sizeof(bhkRigidBodyBuf);
	uint16_t bufType = BUFFER_TYPES::bhkRigidBodyBufType;
	uint32_t shapeID;
	uint8_t collisionFilter_layer;
	uint8_t collisionFilter_flags;
	uint16_t collisionFilter_group;
	uint8_t broadPhaseType;
	uint32_t prop_data;
	uint32_t prop_size;
	uint32_t prop_flags;
	uint16_t childCount;
	uint8_t collisionResponse;
	uint16_t processContactCallbackDelay;
	uint8_t collisionFilterCopy_layer;
	uint8_t collisionFilterCopy_flags;
	uint16_t collisionFilterCopy_group;
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
	uint16_t constraintCount;
	uint32_t bodyFlagsInt;
	uint16_t bodyFlags;
};

struct bhkSimpleShapePhantomBuf {
	uint16_t bufSize = sizeof(bhkSimpleShapePhantomBuf);
	uint16_t bufType = BUFFER_TYPES::bhkSimpleShapePhantomBufType;
	uint32_t shapeID;
	uint8_t collisionFilter_layer;
	uint8_t collisionFilter_flags;
	uint16_t collisionFilter_group;
	uint8_t broadPhaseType;
	uint32_t prop_data;
	uint32_t prop_size;
	uint32_t prop_flags;
	uint16_t childCount;
	nifly::Matrix4 transform;
};

struct bhkBoxShapeBuf {
	uint16_t bufSize = sizeof(bhkBoxShapeBuf);
	uint16_t bufType = BUFFER_TYPES::bhkBoxShapeBufType;
	uint32_t material;
	float radius;
	float dimensions_x;
	float dimensions_y;
	float dimensions_z;
};

struct BHKCapsuleShapeBuf {
	uint16_t bufSize = sizeof(BHKCapsuleShapeBuf);
	uint16_t bufType = BUFFER_TYPES::bhkCapsuleShapeBufType;
	uint32_t material;
	float radius;
	float point1[3];
	float radius1;
	float point2[3];
	float radius2;
};

struct bhkSphereShapeBuf {
	uint16_t bufSize = sizeof(bhkSphereShapeBuf);
	uint16_t bufType = BUFFER_TYPES::bhkSphereShapeBufType;
	uint32_t material;
	float radius;
};

struct BHKListShapeBuf {
	uint16_t bufSize = sizeof(BHKListShapeBuf);
	uint16_t bufType = BUFFER_TYPES::bhkListShapeBufType;
	uint32_t material;
	uint32_t childShape_data;
	uint32_t childShape_size;
	uint32_t childShape_flags;
	uint32_t childFilter_data;
	uint32_t childFilter_size;
	uint32_t childFilter_flags;
	uint32_t childCount;
};

struct BHKConvexVertsShapeBuf {
	uint16_t bufSize = sizeof(BHKConvexVertsShapeBuf);
	uint16_t bufType = BUFFER_TYPES::bhkConvexVerticesShapeBufType;
	uint32_t material;
	float radius;
	uint32_t vertsProp_data;
	uint32_t vertsProp_size;
	uint32_t vertsProp_flags;
	uint32_t normalsProp_data;
	uint32_t normalsProp_size;
	uint32_t normalsProp_flags;
	uint32_t vertsCount;
	uint32_t normalsCount;
};

struct BHKConvexTransformShapeBuf {
	uint16_t bufSize = sizeof(BHKConvexTransformShapeBuf);
	uint16_t bufType = BUFFER_TYPES::bhkConvexTransformShapeBufType;
	uint32_t shapeID;
	uint32_t material;
	float radius;
	float xform[16];
};

struct bhkRagdollConstraintBuf {
	uint16_t bufSize = sizeof(bhkRagdollConstraintBuf);
	uint16_t bufType = BUFFER_TYPES::bhkRagdollConstraintBufType;
	uint16_t entityCount = 0;
	uint32_t priority = 0;
	nifly::Vector4 twistA;
	nifly::Vector4 planeA;
	nifly::Vector4 motorA;
	nifly::Vector4 pivotA;
	nifly::Vector4 twistB;
	nifly::Vector4 planeB;
	nifly::Vector4 motorB;
	nifly::Vector4 pivotB;
	float coneMaxAngle = 0.0f;
	float planeMinAngle = 0.0f;
	float planeMaxAngle = 0.0f;
	float twistMinAngle = 0.0f;
	float twistMaxAngle = 0.0f;
	float maxFriction = 0.0f;
	uint8_t motorType = 0;
	// bhkPositionConstraintMotor motorPosition;
	float positionConstraint_tau = 0.8f;
	float positionConstraint_damping = 1.0f;
	float positionConstraint_propRV = 2.0f;
	float positionConstraint_constRV = 1.0f;
	// bhkVelocityConstraintMotor motorVelocity;
	float velocityConstraint_tau = 0.0f;
	float velocityConstraint_velocityTarget = 0.0f;
	uint8_t velocityConstraint_useVTFromCT = 0;
	// bhkSpringDamperConstraintMotor motorSpringDamper;
	float springDamp_springConstant = 0.0f;
	float springDamp_springDamping = 0.0f;
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
	uint16_t bufSize = sizeof(NiControllerManagerBuf);
	uint16_t bufType = BUFFER_TYPES::NiControllerManagerBufType;
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
	uint16_t bufSize = sizeof(NiMultiTargetTransformControllerBuf);
	uint16_t bufType = BUFFER_TYPES::NiMultiTargetTransformControllerBufType;
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
	uint16_t bufSize = sizeof(NiControllerSequenceBuf);
	uint16_t bufType = BUFFER_TYPES::NiControllerSequenceBufType;
	uint32_t nameID = nifly::NIF_NPOS;
	uint32_t arrayGrowBy = 0;
	uint16_t controlledBlocksCount = 0;
	float weight = 1.0f;
	uint32_t textKeyID = nifly::NIF_NPOS;
	uint32_t cycleType = nifly::CYCLE_LOOP;
	float frequency = 0.0f;
	float startTime = 0.0f;
	float stopTime = 0.0f;
	uint32_t managerID = nifly::NIF_NPOS;
	uint32_t accumRootNameID = nifly::NIF_NPOS;
	uint32_t animNotesID = nifly::NIF_NPOS;
	uint16_t animNotesCount = 0;
};

struct ControllerLinkBuf {
	uint16_t bufSize = sizeof(ControllerLinkBuf);
	uint16_t bufType = BUFFER_TYPES::NiControllerLinkBufType;
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
	uint16_t bufSize = sizeof(NiTransformInterpolatorBuf);
	uint16_t bufType = BUFFER_TYPES::NiTransformInterpolatorBufType;
	float translation[3];
	float rotation[4];
	float scale = 0.0f;
	uint32_t dataID;
};

struct NiTransformControllerBuf {
	uint16_t bufSize = sizeof(NiTransformControllerBuf);
	uint16_t bufType = BUFFER_TYPES::NiTransformControllerBufType;
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
	uint16_t bufSize = sizeof(NiTransformDataBuf);
	uint16_t bufType = BUFFER_TYPES::NiTransformDataBufType;
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

