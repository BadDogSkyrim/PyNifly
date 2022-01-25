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
		niflydll::LogWrite("Failed to get a handle to the DLL module");
	}
	if (GetModuleFileName(hm, (LPSTR)path, sizeof(path)) == 0)
	{
		int ret = GetLastError();
		niflydll::LogWrite("Failed to get the filename of the DLL");
	}
	
	projectRoot = std::filesystem::path(path).parent_path();
}

String SkeletonFile(enum TargetGame game, String& rootName) {
	String skeletonPath;

	FindProjectRoot();
	switch (game) {
	case FO3:
	case FONV:
		rootName = "Bip01";
		break;
	case SKYRIM:
	case SKYRIMSE:
	case SKYRIMVR:
		curSkeletonPath = (projectRoot / "skeletons/Skyrim/skeleton.nif").string();
		rootName = "NPC Root [Root]";
		break;
	case FO4:
	case FO4VR:
		curSkeletonPath = (projectRoot / "skeletons/FO4/skeleton.nif").string();
		rootName = "Root";
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
	AnimInfo* anim,
	const std::string& boneName, 
	const std::string* parentBone, 
	const MatTransform* xformToParent) 
{
	AnimSkeleton* skel = anim->GetSkeleton();
	
	// Use the provided transform in preference to any transform from the reference skeleton
	if (xformToParent || !skel->RefBone(boneName)) {
		// Not in skeleton, add it
		AnimBone& customBone = skel->AddCustomBone(boneName);
		customBone.SetTransformBoneToParent(*xformToParent);
		if (parentBone)
			customBone.SetParentBone(skel->GetBonePtr(*parentBone, true));
	}
};

void GetGlobalToSkin(AnimInfo* anim, NiShape* theShape, MatTransform* outXform) {
	*outXform = anim->shapeSkinning[theShape->name.get()].xformGlobalToSkin;
}

/* Create a skin for a nif, represented by AnimInfo */
AnimInfo* CreateSkinForNif(NifFile* nif, enum TargetGame game) 
/* Create an AnimInfo skin for an entire nif, based on the reference skeleton for the target game. */
{
	AnimInfo* anim = new AnimInfo();
	std::string rootName = "";
	std::string fname = SkeletonFile(game, rootName);
	AnimSkeleton* skel = AnimSkeleton::MakeInstance();
	skel->LoadFromNif(fname, rootName); 
	anim->SetSkeleton(skel);
	anim->SetRefNif(nif);
	return anim;
}

/* Set the skin transform of a shape */
void SetGlobalToSkinXform(AnimInfo* anim, NiShape* theShape, const MatTransform& gtsXform) {
	String shapeName = theShape->name.get();
	anim->shapeSkinning[shapeName].xformGlobalToSkin = gtsXform;
	theShape->SetTransformToParent(theShape->GetTransformToParent());
}

void AddBoneToShape(AnimInfo* anim, NiShape* theShape, std::string boneName, 
	MatTransform* boneXform)
{
	AddCustomBoneRef(anim, boneName, nullptr, boneXform);
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

int SaveSkinnedNif(AnimInfo* anim, std::filesystem::path filepath)
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

NiShape* PyniflyCreateShapeFromData(NifFile* nif, 
	const std::string& shapeName,
	const std::vector<Vector3>* v,
	const std::vector<Triangle>* t,
	const std::vector<Vector2>* uv,
	const std::vector<Vector3>* norms,
	uint32_t options
/* 
	Copy of the nifly routine but handles BSDynamicTriShapes and BSEffectShaderProperties
	* options == 1: Create SSE head part (so use BSDynamicTriShape)
	*            == 2: Create FO4 BSTriShape (default is BSSubindexTriShape)
	*            == 4: Create FO4 BSEffectShaderProperty
	*            may be omitted
	*/
) {
	auto rootNode = nif->GetRootNode();
	if (!rootNode)
		return nullptr;

	NiVersion& version = nif->GetHeader().GetVersion();

	NiShape* shapeResult = nullptr;
	if (version.IsSSE() && (options & 1)) {
		std::unique_ptr<BSTriShape> triShape;
		triShape = std::make_unique<BSDynamicTriShape>();
		triShape->Create(version, v, t, uv, norms);
		triShape->SetSkinned(true); // If a headpart, it's skinned

		auto nifTexset = std::make_unique<BSShaderTextureSet>(version);

		auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
		nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
		nifShader->SetSkinned(true);

		triShape->name.get() = shapeName;

		int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
		triShape->ShaderPropertyRef()->index = shaderID;

		shapeResult = triShape.get();

		int shapeID = nif->GetHeader().AddBlock(std::move(triShape));
		rootNode->childRefs.AddBlockRef(shapeID);
	}
	else if (version.IsFO4() && ((options & 2) || (options & 4))) {
		if (options & 2) {
			// Need to make a BSTriShape
			auto nifBSTriShape = std::make_unique<BSTriShape>();
			nifBSTriShape->Create(version, v, t, uv, norms);
			nifBSTriShape->SetSkinned(false);
			nifBSTriShape->name.get() = shapeName;

			if (options & 4) {
				// Make a BSEffectShader
				auto nifShader = std::make_unique<BSEffectShaderProperty>();

				nifShader->SetSkinned(false);

				int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
				nifBSTriShape->ShaderPropertyRef()->index = shaderID;
				shapeResult = nifBSTriShape.get();

				int shapeID = nif->GetHeader().AddBlock(std::move(nifBSTriShape));
				rootNode->childRefs.AddBlockRef(shapeID);
			}
			else {
				// Make a BSLightingShader
				auto nifTexset = std::make_unique<BSShaderTextureSet>(version);

				auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
				nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));

				std::string wetShaderName = "template/OutfitTemplate_Wet.bgsm";
				nifShader->SetWetMaterialName(wetShaderName);
				nifShader->SetSkinned(false);

				int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
				nifBSTriShape->ShaderPropertyRef()->index = shaderID;

				shapeResult = nifBSTriShape.get();

				int shapeID = nif->GetHeader().AddBlock(std::move(nifBSTriShape));
				rootNode->childRefs.AddBlockRef(shapeID);
			}
		}
		else {
			// Need to make a BSSubindexTriShape
			// Duplicates the entire block above, sue me
			auto nifBSTriShape = std::make_unique<BSSubIndexTriShape>();
			nifBSTriShape->Create(version, v, t, uv, norms);
			nifBSTriShape->SetSkinned(false);
			nifBSTriShape->name.get() = shapeName;

			if (options & 4) {
				// Make a BSEffectShader
				auto nifShader = std::make_unique<BSEffectShaderProperty>();
				nifShader->SetSkinned(false);

				int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
				nifBSTriShape->ShaderPropertyRef()->index = shaderID;
				shapeResult = nifBSTriShape.get();

				int shapeID = nif->GetHeader().AddBlock(std::move(nifBSTriShape));
				rootNode->childRefs.AddBlockRef(shapeID);
			}
			else {
				// Make a BSLightingShader
				auto nifTexset = std::make_unique<BSShaderTextureSet>(version);

				auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
				nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));

				std::string wetShaderName = "template/OutfitTemplate_Wet.bgsm";
				nifShader->SetWetMaterialName(wetShaderName);
				nifShader->SetSkinned(false);

				int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
				nifBSTriShape->ShaderPropertyRef()->index = shaderID;

				shapeResult = nifBSTriShape.get();

				int shapeID = nif->GetHeader().AddBlock(std::move(nifBSTriShape));
				rootNode->childRefs.AddBlockRef(shapeID);
			}
		}
	}
	else {
		shapeResult = nif->CreateShapeFromData(shapeName, v, t, uv, norms);
	}

	return shapeResult;
}

AnimSkeleton* MakeSkeleton(enum TargetGame theGame) {
	AnimSkeleton* skel = AnimSkeleton::MakeInstance();
	std::string root;
	std::string fn = SkeletonFile(theGame, root);
	skel->LoadFromNif(fn, root);
	return skel;
};

