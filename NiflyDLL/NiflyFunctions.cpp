/*
	Functions and classes allowing convenient manipulation of nif files. Provides a layer
	of abstraction for creating nifs that Nifly provides for reading them. Copied
	from Outfit Studio.

	TODO: Split out the Anim* stuff from OS into files that better match the OS files
	for easier sync.
	*/
#include "pch.h" 
#include "object3d.hpp"
#include "geometry.hpp"
#include "NifFile.hpp"
#include "NifUtil.hpp"
#include "Anim.h"
#include "NiflyFunctions.hpp"

using namespace nifly;

typedef std::string String;

/* Yes, they're statics. And not a class in sight. Bite me. */
static std::filesystem::path projectRoot;

static String curSkeletonPath;
static String curGameDataPath; // Get this from OS if it turns out we need it
std::string curRootName;

void FindProjectRoot() {
	char path[MAX_PATH];
	HMODULE hm = NULL;

	if (!projectRoot.empty()) return;

	if (GetModuleHandleEx(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
			GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
			(LPCSTR)&SkeletonFile, &hm) == 0) {
		int ret = GetLastError();
		LogWrite("Failed to get a handle to the DLL module");
	}
	if (GetModuleFileName(hm, (LPSTR)path, sizeof(path)) == 0)
	{
		int ret = GetLastError();
		LogWrite("Failed to get the filename of the DLL");
	}
	
	projectRoot = std::filesystem::path(path).parent_path();
}

String SkeletonFile(enum TargetGame game) {
	String skeletonPath;

	FindProjectRoot();
	switch (game) {
	case FO3:
	case FONV:
		curRootName = "Bip01";
		break;
	case SKYRIM:
	case SKYRIMSE:
	case SKYRIMVR:
		curSkeletonPath = (projectRoot / "skeletons/Skyrim/skeleton.nif").string();
		curRootName = "NPC Root [Root]";
		break;
	case FO4:
	case FO4VR:
		curSkeletonPath = (projectRoot / "skeletons/FO4/skeleton.nif").string();
		curRootName = "Root";
		break;
	}
	return curSkeletonPath;
}

void SetNifVersion(NifFile* nif, enum TargetGame targ) {
	NiVersion version;

	switch (targ) {
	case FO3:
	case FONV:
		version.SetFile(V20_2_0_7);
		version.SetUser(11);
		version.SetStream(34);
		break;
	case SKYRIM:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(83);
		break;
	case FO4:
	case FO4VR:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(130);
		break;
	case SKYRIMSE:
	case SKYRIMVR:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(100);
		break;
	case FO76:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(155);
		break;
	}

	nif->Create(version);
	//NiNode* root = nif->GetRootNode();
	//String nm = root->GetName();
	//root->SetName("Scene Root");
}

void AddCustomBoneRef(
	const std::string& boneName, 
	const std::string* parentBone, 
	const MatTransform* xformToParent) 
{
	AnimSkeleton* skel = &AnimSkeleton::getInstance();
	if (!skel->RefBone(boneName)) {
		// Not in skeleton, add it
		AnimBone& customBone = AnimSkeleton::getInstance().AddCustomBone(boneName);
		customBone.SetTransformBoneToParent(*xformToParent);
		if (parentBone)
			customBone.SetParentBone(AnimSkeleton::getInstance().GetBonePtr(*parentBone, true));
	}
};

void GetGlobalToSkin(AnimInfo* anim, NiShape* theShape, MatTransform* outXform) {
	*outXform = anim->shapeSkinning[theShape->name.get()].xformGlobalToSkin;
}

/* Create a skin for a nif, represented by AnimInfo */
AnimInfo* CreateSkinForNif(NifFile* nif, enum TargetGame game) {
	AnimInfo* anim = new AnimInfo();
	std::string fname = SkeletonFile(game);
	AnimSkeleton::getInstance().LoadFromNif(fname, curRootName); 
	anim->SetRefNif(nif);
	return anim;
}

/* Set the skin transform of a shape */
void SetGlobalToSkinXform(AnimInfo* anim, NiShape* theShape, const MatTransform& gtsXform) {
	String shapeName = theShape->name.get();
	anim->shapeSkinning[shapeName].xformGlobalToSkin = gtsXform;
	theShape->SetTransformToParent(theShape->GetTransformToParent());
}

/* Create shape from given shape data. Copied from OS */
NiShape* XXXCreateShapeFromData(
	NifFile* nif,
	const char* shapeName,
	const std::vector<Vector3>* verts,
	const std::vector<Triangle>* tris,
	const std::vector<Vector2>* uv,
	const std::vector<Vector3>* norms) 
{
	NiHeader& hdr = nif->GetHeader();
	NiVersion vers = hdr.GetVersion();
	auto rootNode = nif->GetRootNode();
	if (!rootNode) return nullptr;

	NiShape* shapeResult = nullptr;

	if (vers.IsFO3() || vers.IsSK()) {
		auto nifTexset = std::make_unique<BSShaderTextureSet>(hdr.GetVersion());

		int shaderID;
		std::unique_ptr<BSLightingShaderProperty> nifShader = nullptr;
		std::unique_ptr<BSShaderPPLightingProperty> nifShaderPP = nullptr;
		if (vers.IsFO3()) {
			nifShaderPP = std::make_unique<BSShaderPPLightingProperty>();
			nifShaderPP->TextureSetRef()->index = hdr.AddBlock(std::move(nifTexset));
			nifShaderPP->SetSkinned(false);
			shaderID = hdr.AddBlock(std::move(nifShaderPP));
		}
		else {
			nifShader = std::make_unique<BSLightingShaderProperty>(hdr.GetVersion());
			nifShader->TextureSetRef()->index = hdr.AddBlock(std::move(nifTexset));
			nifShader->SetSkinned(false);
			shaderID = hdr.AddBlock(std::move(nifShader));
		};

		auto nifTriShape = std::make_unique<NiTriShape>();
		if (vers.IsFO3())
			nifTriShape->propertyRefs.AddBlockRef(shaderID);
		else
			nifTriShape->ShaderPropertyRef()->index = shaderID;

		nifTriShape->name.get() = shapeName;

		auto nifShapeData = std::make_unique<NiTriShapeData>();
		nifShapeData->Create(hdr.GetVersion(), verts, tris, uv, norms);
		nifTriShape->SetGeomData(nifShapeData.get());

		int dataID = hdr.AddBlock(std::move(nifShapeData));
		nifTriShape->DataRef()->index = dataID;
		nifTriShape->SetSkinned(false);

		shapeResult = nifTriShape.get();

		int shapeID = hdr.AddBlock(std::move(nifTriShape));
		rootNode->childRefs.AddBlockRef(shapeID);
	}
	else if (vers.IsFO4() || vers.IsFO76()) {
		auto nifBSTriShape = std::make_unique<BSSubIndexTriShape>();

		nifBSTriShape->Create(hdr.GetVersion(), verts, tris, uv, norms);
		nifBSTriShape->SetSkinned(false);

		auto nifTexset = std::make_unique<BSShaderTextureSet>(hdr.GetVersion());

		auto nifShader = std::make_unique<BSLightingShaderProperty>(hdr.GetVersion());
		nifShader->TextureSetRef()->index = hdr.AddBlock(std::move(nifTexset));

		String wetShaderName = "template/OutfitTemplate_Wet.bgsm";
		nifShader->SetWetMaterialName(wetShaderName);
		nifShader->SetSkinned(false);

		nifBSTriShape->name.get() = shapeName;

		int shaderID = hdr.AddBlock(std::move(nifShader));
		nifBSTriShape->ShaderPropertyRef()->index = shaderID;

		shapeResult = nifBSTriShape.get();

		int shapeID = hdr.AddBlock(std::move(nifBSTriShape));
		rootNode->childRefs.AddBlockRef(shapeID);
	}
	else {
		auto triShape = std::make_unique<BSTriShape>();
		triShape->Create(hdr.GetVersion(), verts, tris, uv, norms);
		triShape->SetSkinned(false);

		auto nifTexset = std::make_unique<BSShaderTextureSet>(hdr.GetVersion());

		auto nifShader = std::make_unique<BSLightingShaderProperty>(hdr.GetVersion());
		nifShader->TextureSetRef()->index = hdr.AddBlock(std::move(nifTexset));
		nifShader->SetSkinned(false);

		triShape->name.get() = shapeName;

		int shaderID = hdr.AddBlock(std::move(nifShader));
		triShape->ShaderPropertyRef()->index = shaderID;

		shapeResult = triShape.get();

		int shapeID = hdr.AddBlock(std::move(triShape));
		rootNode->childRefs.AddBlockRef(shapeID);
	}

	//SetTextures(shapeResult);
	//std::vector<Vector3> liveNorms;
	//nif->SetNormalsForShape(shapeResult, liveNorms);
	nif->CalcTangentsForShape(shapeResult);
	return shapeResult;
}

void AddBoneToShape(AnimInfo* anim, NiShape* theShape, std::string boneName, 
	MatTransform* boneXform)
{
	AddCustomBoneRef(boneName, nullptr, boneXform);
	anim->AddShapeBone(theShape->name.get(), boneName);
}

void SetShapeGlobalToSkinXform(AnimInfo* anim, nifly::NiShape* theShape, const nifly::MatTransform& gtsXform)
{
	anim->ChangeGlobalToSkinTransform(theShape->name.get(), gtsXform);
	anim->GetRefNif()->SetShapeTransformGlobalToSkin(theShape, gtsXform);
}

void SetShapeWeights(AnimInfo* anim, nifly::NiShape* theShape, std::string boneName, AnimWeight& theWeightSet)
{
	anim->SetWeights(theShape->name.get(), boneName, theWeightSet.weights);
}

int SaveSkinnedNif(AnimInfo* anim, std::string filepath)
{
	NifFile* theNif = anim->GetRefNif();
	anim->WriteToNif(theNif, "None");
	for (auto& shape : theNif->GetShapes())
		theNif->UpdateSkinPartitions(shape);

	return theNif->Save(filepath);
}

void GetPartitions(
	NifFile* workNif,
	NiShape* shape,
	NiVector<BSDismemberSkinInstance::PartitionInfo>& partitions,
	std::vector<int>& indices) 
{
	NiVector<BSDismemberSkinInstance::PartitionInfo> partitionInfo;
	std::vector<Triangle> tris;
	shape->GetTriangles(tris);

	std::vector<int> triParts;
	NifSegmentationInfo inf;
	if (!workNif->GetShapeSegments(shape, inf, triParts)) {
		workNif->GetShapePartitions(shape, partitionInfo, triParts);
	};

	partitions = partitionInfo;
	indices = triParts;
}

