/*
nifly
C++ NIF library for the Gamebryo/NetImmerse File Format
See the included GPLv3 LICENSE file
*/

#pragma once

#include "Animation.hpp"
#include "BasicTypes.hpp"
#include "ExtraData.hpp"

namespace nifly {
class NiObjectNET : public NiCloneableStreamable<NiObjectNET, NiObject> {
public:
	NiStringRef name;

	bool bBSLightingShaderProperty = false;
	uint32_t bslspShaderType = 0; // BSLightingShaderProperty && User Version >= 12

	NiBlockRef<NiTimeController> controllerRef;
	NiBlockRefArray<NiExtraData> extraDataRefs;

	void Sync(NiStreamReversible& stream);
	void GetStringRefs(std::vector<NiStringRef*>& refs) override;
	void GetChildRefs(std::set<NiRef*>& refs) override;
	void GetChildIndices(std::vector<uint32_t>& indices) override;
};

class NiProperty;
class NiCollisionObject;

class NiAVObject : public NiCloneableStreamable<NiAVObject, NiObjectNET> {
public:
	uint32_t flags = 524302;
	/* "transform" is the coordinate system (CS) transform from this
	object's CS to its parent's CS.
	Recommendation: rename "transform" to "transformToParent". */
	MatTransform transform;

	NiBlockRefArray<NiProperty> propertyRefs;
	NiBlockRef<NiCollisionObject> collisionRef;

	void Sync(NiStreamReversible& stream);
	void GetChildRefs(std::set<NiRef*>& refs) override;
	void GetChildIndices(std::vector<uint32_t>& indices) override;

	const MatTransform& GetTransformToParent() const { return transform; }
	void SetTransformToParent(const MatTransform& t) { transform = t; }
};

class AVObject {
public:
	NiString name;
	NiBlockPtr<NiAVObject> objectRef;

	void Sync(NiStreamReversible& stream) {
		name.Sync(stream, 4);
		objectRef.Sync(stream);
	}

	void GetPtrs(std::set<NiPtr*>& ptrs) { ptrs.insert(&objectRef); }
};

class NiAVObjectPalette : public NiCloneable<NiAVObjectPalette, NiObject> {};

class NiDefaultAVObjectPalette : public NiCloneableStreamable<NiDefaultAVObjectPalette, NiAVObjectPalette> {
public:
	NiBlockPtr<NiAVObject> sceneRef;
	NiSyncVector<AVObject> objects;

	static constexpr const char* BlockName = "NiDefaultAVObjectPalette";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
	void GetPtrs(std::set<NiPtr*>& ptrs) override;
};

class NiCamera : public NiCloneableStreamable<NiCamera, NiAVObject> {
public:
	uint16_t obsoleteFlags = 0;
	float frustumLeft = 0.0f;
	float frustumRight = 0.0f;
	float frustumTop = 0.0f;
	float frustomBottom = 0.0f;
	float frustumNear = 0.0f;
	float frustumFar = 0.0f;
	bool useOrtho = false;
	float viewportLeft = 0.0f;
	float viewportRight = 0.0f;
	float viewportTop = 0.0f;
	float viewportBottom = 0.0f;
	float lodAdjust = 0.0f;

	NiBlockRef<NiAVObject> sceneRef;
	uint32_t numScreenPolygons = 0;
	uint32_t numScreenTextures = 0;

	static constexpr const char* BlockName = "NiCamera";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
	void GetChildRefs(std::set<NiRef*>& refs) override;
	void GetChildIndices(std::vector<uint32_t>& indices) override;
};

class NiSequenceStreamHelper : public NiCloneable<NiSequenceStreamHelper, NiObjectNET> {
public:
	static constexpr const char* BlockName = "NiSequenceStreamHelper";
	const char* GetBlockName() override { return BlockName; }
};

class NiPalette : public NiCloneableStreamable<NiPalette, NiObject> {
public:
	bool hasAlpha = false;
	NiVector<ByteColor4> palette = NiVector<ByteColor4>(256);

	static constexpr const char* BlockName = "NiPalette";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
};

enum PixelFormat : uint32_t {
	PX_FMT_RGB8,
	PX_FMT_RGBA8,
	PX_FMT_PAL8,
	PX_FMT_DXT1 = 4,
	PX_FMT_DXT5 = 5,
	PX_FMT_DXT5_ALT = 6,
};

enum PixelTiling : uint32_t { PX_TILE_NONE, PX_TILE_XENON, PX_TILE_WII, PX_TILE_NV_SWIZZLED };

enum PixelComponent : uint32_t {
	PX_COMP_RED,
	PX_COMP_GREEN,
	PX_COMP_BLUE,
	PX_COMP_ALPHA,
	PX_COMP_COMPRESSED,
	PX_COMP_OFFSET_U,
	PX_COMP_OFFSET_V,
	PX_COMP_OFFSET_W,
	PX_COMP_OFFSET_Q,
	PX_COMP_LUMA,
	PX_COMP_HEIGHT,
	PX_COMP_VECTOR_X,
	PX_COMP_VECTOR_Y,
	PX_COMP_VECTOR_Z,
	PX_COMP_PADDING,
	PX_COMP_INTENSITY,
	PX_COMP_INDEX,
	PX_COMP_DEPTH,
	PX_COMP_STENCIL,
	PX_COMP_EMPTY
};

enum PixelRepresentation : uint32_t {
	PX_REP_NORM_INT,
	PX_REP_HALF,
	PX_REP_FLOAT,
	PX_REP_INDEX,
	PX_REP_COMPRESSED,
	PX_REP_UNKNOWN,
	PX_REP_INT
};

struct PixelFormatComponent {
	PixelComponent type = PX_COMP_RED;
	PixelRepresentation convention = PX_REP_NORM_INT;
	uint8_t bitsPerChannel = 0;
	bool isSigned = false;
};

struct MipMapInfo {
	uint32_t width = 0;
	uint32_t height = 0;
	uint32_t offset = 0;
};

class TextureRenderData : public NiCloneableStreamable<TextureRenderData, NiObject> {
public:
	PixelFormat pixelFormat = PX_FMT_RGB8;
	uint8_t bitsPerPixel = 0;
	uint32_t rendererHint = 0xFFFFFFFF;
	uint32_t extraData = 0;
	uint8_t flags = 0;
	PixelTiling pixelTiling = PX_TILE_NONE;

	PixelFormatComponent channels[4]{};
	NiBlockRef<NiPalette> paletteRef;

	NiVector<MipMapInfo> mipmaps;
	uint32_t bytesPerPixel = 0;

	void Sync(NiStreamReversible& stream);
	void GetChildRefs(std::set<NiRef*>& refs) override;
	void GetChildIndices(std::vector<uint32_t>& indices) override;
};

enum PlatformID : uint32_t { PLAT_ANY, PLAT_XENON, PLAT_PS3, PLAT_DX9, PLAT_WII, PLAT_D3D10 };

class NiPersistentSrcTextureRendererData
	: public NiCloneableStreamable<NiPersistentSrcTextureRendererData, TextureRenderData> {
public:
	uint32_t numPixels = 0;
	uint32_t padNumPixels = 0;
	uint32_t numFaces = 0;
	PlatformID platform = PLAT_ANY;

	std::vector<std::vector<uint8_t>> pixelData;

	static constexpr const char* BlockName = "NiPersistentSrcTextureRendererData";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
};

class NiPixelData : public NiCloneableStreamable<NiPixelData, TextureRenderData> {
public:
	uint32_t numPixels = 0;
	uint32_t numFaces = 0;

	std::vector<std::vector<uint8_t>> pixelData;

	static constexpr const char* BlockName = "NiPixelData";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
};

enum PixelLayout : uint32_t {
	PX_LAY_PALETTIZED_8,
	PX_LAY_HIGH_COLOR_16,
	PX_LAY_TRUE_COLOR_32,
	PX_LAY_COMPRESSED,
	PX_LAY_BUMPMAP,
	PX_LAY_PALETTIZED_4,
	PX_LAY_DEFAULT,
	PX_LAY_SINGLE_COLOR_8,
	PX_LAY_SINGLE_COLOR_16,
	PX_LAY_SINGLE_COLOR_32,
	PX_LAY_DOUBLE_COLOR_32,
	PX_LAY_DOUBLE_COLOR_64,
	PX_LAY_FLOAT_COLOR_32,
	PX_LAY_FLOAT_COLOR_64,
	PX_LAY_FLOAT_COLOR_128,
	PX_LAY_SINGLE_COLOR_4,
	PX_LAY_DEPTH_24_X8,
};

enum MipMapFormat : uint32_t { MIP_FMT_NO, MIP_FMT_YES, MIP_FMT_DEFAULT };

enum AlphaFormat : uint32_t { ALPHA_NONE, ALPHA_BINARY, ALPHA_SMOOTH, ALPHA_DEFAULT };

class NiTexture : public NiCloneable<NiTexture, NiObjectNET> {};

class NiSourceTexture : public NiCloneableStreamable<NiSourceTexture, NiTexture> {
public:
	bool useExternal = true;
	bool useInternal = true;
	NiStringRef fileName;

	// NiPixelData if < 20.2.0.4 or !persistentRenderData
	// else NiPersistentSrcTextureRendererData
	NiBlockRef<TextureRenderData> dataRef;

	PixelLayout pixelLayout = PX_LAY_PALETTIZED_4;
	MipMapFormat mipMapFormat = MIP_FMT_DEFAULT;
	AlphaFormat alphaFormat = ALPHA_DEFAULT;
	bool isStatic = true;
	bool directRender = true;
	bool persistentRenderData = false;

	static constexpr const char* BlockName = "NiSourceTexture";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
	void GetStringRefs(std::vector<NiStringRef*>& refs) override;
	void GetChildRefs(std::set<NiRef*>& refs) override;
	void GetChildIndices(std::vector<uint32_t>& indices) override;
};

class NiSourceCubeMap : public NiCloneable<NiSourceCubeMap, NiSourceTexture> {
public:
	static constexpr const char* BlockName = "NiSourceCubeMap";
	const char* GetBlockName() override { return BlockName; }
};

enum TexFilterMode : uint32_t {
	FILTER_NEAREST,
	FILTER_BILERP,
	FILTER_TRILERP,
	FILTER_NEAREST_MIPNEAREST,
	FILTER_NEAREST_MIPLERP,
	FILTER_BILERP_MIPNEAREST
};

enum TexClampMode : uint32_t { CLAMP_S_CLAMP_T, CLAMP_S_WRAP_T, WRAP_S_CLAMP_T, WRAP_S_WRAP_T };

enum EffectType : uint32_t {
	EFFECT_PROJECTED_LIGHT,
	EFFECT_PROJECTED_SHADOW,
	EFFECT_ENVIRONMENT_MAP,
	EFFECT_FOG_MAP
};

enum CoordGenType : uint32_t {
	CG_WORLD_PARALLEL,
	CG_WORLD_PERSPECTIVE,
	CG_SPHERE_MAP,
	CG_SPECULAR_CUBE_MAP,
	CG_DIFFUSE_CUBE_MAP
};

class NiDynamicEffect : public NiCloneableStreamable<NiDynamicEffect, NiAVObject> {
public:
	bool switchState = false;
	NiBlockPtrArray<NiNode> affectedNodes;

	void Sync(NiStreamReversible& stream);
	void GetPtrs(std::set<NiPtr*>& ptrs) override;
};

class NiTextureEffect : public NiCloneableStreamable<NiTextureEffect, NiDynamicEffect> {
public:
	Matrix3 modelProjectionMatrix;
	Vector3 modelProjectionTranslation;
	TexFilterMode textureFiltering = FILTER_TRILERP;
	TexClampMode textureClamping = WRAP_S_WRAP_T;
	EffectType textureType = EFFECT_ENVIRONMENT_MAP;
	CoordGenType coordinateGenerationType = CG_SPHERE_MAP;
	NiBlockRef<NiSourceTexture> sourceTexture;
	uint8_t clippingPlane = 0;
	NiPlane plane;

	static constexpr const char* BlockName = "NiTextureEffect";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
	void GetChildRefs(std::set<NiRef*>& refs) override;
	void GetChildIndices(std::vector<uint32_t>& indices) override;
};

class NiLight : public NiCloneableStreamable<NiLight, NiDynamicEffect> {
public:
	float dimmer = 0.0f;
	Color3 ambientColor;
	Color3 diffuseColor;
	Color3 specularColor;

	void Sync(NiStreamReversible& stream);
};

class NiAmbientLight : public NiCloneable<NiAmbientLight, NiLight> {
public:
	static constexpr const char* BlockName = "NiAmbientLight";
	const char* GetBlockName() override { return BlockName; }
};

class NiDirectionalLight : public NiCloneable<NiDirectionalLight, NiLight> {
public:
	static constexpr const char* BlockName = "NiDirectionalLight";
	const char* GetBlockName() override { return BlockName; }
};

class NiPointLight : public NiCloneableStreamable<NiPointLight, NiLight> {
public:
	float constantAttenuation = 0.0f;
	float linearAttenuation = 0.0f;
	float quadraticAttenuation = 0.0f;

	static constexpr const char* BlockName = "NiPointLight";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
};

class NiSpotLight : public NiCloneableStreamable<NiSpotLight, NiPointLight> {
public:
	float outerSpotAngle = 0.0f;
	float innerSpotAngle = 0.0f;
	float exponent = 1.0f;

	static constexpr const char* BlockName = "NiSpotLight";
	const char* GetBlockName() override { return BlockName; }

	void Sync(NiStreamReversible& stream);
};
} // namespace nifly
