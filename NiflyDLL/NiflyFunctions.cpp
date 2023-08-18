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
#include "NiflyDefs.hpp"
#include "NiflyFunctions.hpp"

using namespace nifly;

typedef std::string String;

/* Yes, they're statics. And not a class in sight. Bite me. */
static std::filesystem::path projectRoot;

static String curSkeletonPath;
static String curGameDataPath; // Get this from OS if it turns out we need it
std::string curRootName;

void FindProjectRoot() {
	char path[MAX_PATH] = { 0 };
	HMODULE hm = NULL;

	if (!projectRoot.empty()) return;

	if (GetModuleHandleEx(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
			GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
			(LPCSTR)&SkeletonFile, &hm) == 0) {
		//int ret = GetLastError();
		niflydll::LogWrite("Failed to get a handle to the DLL module");
	}
	if (GetModuleFileName(hm, (LPSTR)path, sizeof(path)) == 0)
	{
		//int ret = GetLastError();
		niflydll::LogWrite("Failed to get the filename of the DLL");
	}
	
	projectRoot = std::filesystem::path(path).parent_path();
}

String SkeletonFile(enum TargetGame game, String& rootName) {
	String skeletonPath;

	FindProjectRoot();
	switch (game) {
	case TargetGame::FO3:
	case TargetGame::FONV:
		rootName = "Bip01";
		break;
	case TargetGame::SKYRIM:
	case TargetGame::SKYRIMSE:
	case TargetGame::SKYRIMVR:
		curSkeletonPath = (projectRoot / "skeletons/Skyrim/skeleton.nif").string();
		rootName = "NPC Root [Root]";
		break;
	case TargetGame::FO4:
	case TargetGame::FO4VR:
		curSkeletonPath = (projectRoot / "skeletons/FO4/skeleton.nif").string();
		rootName = "Root";
		break;
	}
	return curSkeletonPath;
}

void SetNifVersion(NifFile* nif, enum TargetGame targ) {
	NiVersion version;

	switch (targ) {
	case TargetGame::FO3:
	case TargetGame::FONV:
		version.SetFile(V20_2_0_7);
		version.SetUser(11);
		version.SetStream(34);
		break;
	case TargetGame::SKYRIM:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(83);
		break;
	case TargetGame::FO4:
	case TargetGame::FO4VR:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(130);
		break;
	case TargetGame::SKYRIMSE:
	case TargetGame::SKYRIMVR:
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(100);
		break;
	case TargetGame::FO76:
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

std::vector<Vector3> GetShapeBoneVerts(NifFile* nif, NiShape* shape, int boneIndex) {
/* Return a vector of vertex coordinates for vertices affected by a shape's bone.
	boneIndex = index of bone within the shape.
*/
	NiHeader hdr = nif->GetHeader();
	std::vector<Vector3> verts;
	if (!shape->IsSkinned())
		return verts;

	BSTriShape* bsTriShape = dynamic_cast<BSTriShape*>(shape);
	if (bsTriShape) {
		verts.reserve(bsTriShape->GetNumVertices());
		for (uint16_t vertexIndex = 0; vertexIndex < bsTriShape->GetNumVertices(); vertexIndex++) {
			auto& vertex = bsTriShape->vertData[vertexIndex];
			for (size_t i = 0; i < 4; i++) {
				if (vertex.weightBones[i] == boneIndex && vertex.weights[i] >= EPSILON)
					verts.push_back(vertex.vert);
			}
		}
	}
	else {
		NiSkinInstance* skinInst = hdr.GetBlock<NiSkinInstance>(shape->SkinInstanceRef());
		if (!skinInst)
			return verts;

		NiSkinData* skinData = hdr.GetBlock(skinInst->dataRef);
		if (!skinData || boneIndex >= int(skinData->numBones))
			return verts;

		NiGeometryData* geom = shape->GetGeomData();
		NiSkinData::BoneData* bone = &skinData->bones[boneIndex];

		for (SkinWeight& sw : bone->vertexWeights)
			if (sw.weight >= EPSILON)
				verts.push_back(geom->vertices[sw.index]);
	}

	return verts;
}

void UpdateShapeSkinBoneBounds(NifFile* nif, NiShape* shape) 
/* Update the bone bounding spheres on all bones in the shape. */
{
		
	std::vector<int> boneIDlist;
	nif->GetShapeBoneIDList(shape, boneIDlist);

	for (uint32_t boneIndex = 0; boneIndex < boneIDlist.size(); boneIndex++) {
		std::vector<Vector3> boundVerts = GetShapeBoneVerts(nif, shape, boneIndex);
		BoundingSphere boneBounds = BoundingSphere(boundVerts);
		MatTransform sk2b;
		nif->GetShapeTransformSkinToBone(shape, boneIndex, sk2b);
		boneBounds.center = sk2b.ApplyTransform(boneBounds.center);
		boneBounds.radius *= sk2b.scale;
		nif->SetShapeBoneBounds(shape->name.get(), boneIndex, boneBounds);
	}
}

//void AddCustomBoneRef(
//	AnimInfo* anim,
//	const std::string boneName, 
//	const std::string* parentBone,
//	const MatTransform* xformToParent) 
//{
//	AnimSkeleton* skel = anim->GetSkeleton();
//	
//	// Use the provided transform in preference to any transform from the reference skeleton
//	if (xformToParent || !skel->RefBone(boneName)) {
//		// Not in skeleton, add it
//		AnimBone& customBone = skel->AddCustomBone(boneName);
//		customBone.SetTransformBoneToParent(*xformToParent);
//		if (parentBone)
//			customBone.SetParentBone(skel->GetBonePtr(*parentBone, true));
//	}
//};
//
//void GetGlobalToSkin(AnimInfo* anim, NiShape* theShape, MatTransform* outXform) {
//	*outXform = anim->shapeSkinning[theShape->name.get()].xformGlobalToSkin;
//}

///* Create a skin for a nif, represented by AnimInfo */
//AnimInfo* CreateSkinForNif(NifFile* nif, enum TargetGame game) 
///* Create an AnimInfo skin for an entire nif, based on the reference skeleton for the target game. */
//{
//	AnimInfo* anim = new AnimInfo();
//	std::string rootName = "";
//	std::string fname = SkeletonFile(game, rootName);
//	AnimSkeleton* skel = AnimSkeleton::MakeInstance();
//	skel->LoadFromNif(fname, rootName); 
//	anim->SetSkeleton(skel);
//	anim->SetRefNif(nif);
//	return anim;
//}
//
///* Set the skin transform of a shape */
//void SetGlobalToSkinXform(AnimInfo* anim, NiShape* theShape, const MatTransform& gtsXform) {
//	String shapeName = theShape->name.get();
//	anim->shapeSkinning[shapeName].xformGlobalToSkin = gtsXform;
//	theShape->SetTransformToParent(theShape->GetTransformToParent());
//}

//void AddBoneToShape(AnimInfo* anim, NiShape* theShape, std::string boneName,
//	MatTransform* boneXform, const char* parentName)
//{
//	std::string pn;
//	std::string* pp = nullptr;
//	if (parentName) {
//		pn = std::string(parentName);
//		pp = &pn;
//	};
//	AddCustomBoneRef(anim, boneName, pp, boneXform); 
//	anim->AddShapeBone(theShape->name.get(), boneName);
//}

//void SetShapeGlobalToSkinXform(AnimInfo* anim, nifly::NiShape* theShape, const nifly::MatTransform& gtsXform)
//{
//	anim->ChangeGlobalToSkinTransform(theShape->name.get(), gtsXform);
//	anim->GetRefNif()->SetShapeTransformGlobalToSkin(theShape, gtsXform);
//}
//
//void SetShapeWeights(AnimInfo* anim, nifly::NiShape* theShape, std::string boneName, AnimWeight& theWeightSet)
//{
//	anim->SetWeights(theShape->name.get(), boneName, theWeightSet.weights);
//}
//
//int SaveSkinnedNif(AnimInfo* anim, std::filesystem::path filepath)
//{
//	NifFile* theNif = anim->GetRefNif();
//	anim->WriteToNif(theNif, "None");
//	for (auto& shape : theNif->GetShapes())
//		theNif->UpdateSkinPartitions(shape);
//
//	return theNif->Save(filepath);
//}

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
	NiShapeBuf* buf,
	const std::vector<Vector3>* v,
	const std::vector<Triangle>* t,
	const std::vector<Vector2>* uv,
	const std::vector<Vector3>* norms,
	NiNode* parentRef
/* 
	Copy of the nifly routine but handles BSDynamicTriShapes and BSEffectShaderProperties,
	also parents other than root
	* options == 1: Create SSE head part (so use BSDynamicTriShape)
	*            == 2: Create FO4 BSTriShape (default is BSSubindexTriShape)
	*            == 4: Create FO4 BSEffectShaderProperty
	*            may be omitted
	*/
) {
	auto rootNode = nif->GetRootNode();
	auto parentNode = nif->GetRootNode();
	if (!rootNode)
		return nullptr;
	if (parentRef)
		parentNode = parentRef;

	NiVersion& version = nif->GetHeader().GetVersion();

	NiShape* shapeResult = nullptr;
	if (version.IsSSE()) {
		std::unique_ptr<BSTriShape> triShape;
		bool isSkinned = false;

		if (buf->bufType == BUFFER_TYPES::BSDynamicTriShapeBufType) {
			triShape = std::make_unique<BSDynamicTriShape>();
			isSkinned = true; // If a headpart, it's skinned
		}
		else {
			triShape = std::make_unique<BSTriShape>();
		}
		triShape->Create(version, v, t, uv, norms);
		triShape->SetSkinned(isSkinned);

		auto nifTexset = std::make_unique<BSShaderTextureSet>(version);

		auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
		nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
		nifShader->SetSkinned(isSkinned);

		triShape->name.get() = shapeName;

		int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
		triShape->ShaderPropertyRef()->index = shaderID;

		shapeResult = triShape.get();

		int shapeID = nif->GetHeader().AddBlock(std::move(triShape));
		parentNode->childRefs.AddBlockRef(shapeID);
	}
	else if (version.IsFO4() || version.IsFO76()) {
		std::unique_ptr<BSTriShape> triShape;

		if (buf->bufType == BUFFER_TYPES::BSTriShapeBufType) {
			// Need to make a BSTriShape
			triShape = std::make_unique<BSTriShape>();
		}
		else {
			triShape = std::make_unique<BSSubIndexTriShape>();
		}
		triShape->Create(version, v, t, uv, norms);
		triShape->SetSkinned(false);
		triShape->name.get() = shapeName;

		std::unique_ptr<BSShaderProperty> nifShader;
		if (0) { // (options & 4) {
			// Make a BSEffectShader
			nifShader = std::make_unique<BSEffectShaderProperty>();
		}
		else {
			// Make a BSLightingShader
			auto nifTexset = std::make_unique<BSShaderTextureSet>(version);
			nifShader = std::make_unique<BSLightingShaderProperty>(version);
			nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));

			std::string wetShaderName = "template/OutfitTemplate_Wet.bgsm";
			nifShader->SetWetMaterialName(wetShaderName);
		}
		nifShader->SetSkinned(false);

		int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
		triShape->ShaderPropertyRef()->index = shaderID;

		shapeResult = triShape.get();

		int shapeID = nif->GetHeader().AddBlock(std::move(triShape));
		parentNode->childRefs.AddBlockRef(shapeID);
	}
	else {
		auto nifTexset = std::make_unique<BSShaderTextureSet>(nif->GetHeader().GetVersion());

		int shaderID{};
		std::unique_ptr<BSLightingShaderProperty> nifShader = nullptr;
		std::unique_ptr<BSShaderPPLightingProperty> nifShaderPP = nullptr;

		if (version.IsSK()) {
			nifShader = std::make_unique<BSLightingShaderProperty>(nif->GetHeader().GetVersion());
			nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
			nifShader->SetSkinned(false);
			shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
		}
		else {
			nifShaderPP = std::make_unique<BSShaderPPLightingProperty>();
			nifShaderPP->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
			nifShaderPP->SetSkinned(false);
			shaderID = nif->GetHeader().AddBlock(std::move(nifShaderPP));
		}

		auto nifTriShape = std::make_unique<NiTriShape>();
		if (version.IsSK())
			nifTriShape->ShaderPropertyRef()->index = shaderID;
		else
			nifTriShape->propertyRefs.AddBlockRef(shaderID);

		nifTriShape->name.get() = shapeName;

		auto nifShapeData = std::make_unique<NiTriShapeData>();
		nifShapeData->Create(nif->GetHeader().GetVersion(), v, t, uv, norms);
		nifTriShape->SetGeomData(nifShapeData.get());

		int dataID = nif->GetHeader().AddBlock(std::move(nifShapeData));
		nifTriShape->DataRef()->index = dataID;
		nifTriShape->SetSkinned(false);

		shapeResult = nifTriShape.get();

		int shapeID = nif->GetHeader().AddBlock(std::move(nifTriShape));
		parentNode->childRefs.AddBlockRef(shapeID);
	}

	return shapeResult;
}

//AnimSkeleton* MakeSkeleton(enum TargetGame theGame) {
//	AnimSkeleton* skel = AnimSkeleton::MakeInstance();
//	std::string root;
//	std::string fn = SkeletonFile(theGame, root);
//	skel->LoadFromNif(fn, root);
//	return skel;
//};

