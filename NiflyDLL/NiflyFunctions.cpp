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

	if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
			GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
			(LPCSTR) & SkeletonFile, &hm) == 0) {
		//int ret = GetLastError();
		niflydll::LogWrite("Failed to get a handle to the DLL module");
	}
	if (GetModuleFileNameA(hm, (LPSTR)path, sizeof(path)) == 0)
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
	case TargetGame::SF:
		curSkeletonPath = (projectRoot / "skeletons/SF/skeleton.nif").string();
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
	case TargetGame::SF:
		// Starfield: file 20.2.0.7, user 12, stream 172-175. Vanilla base-game
		// assets use 172; nifly's IsSF() accepts the whole range.
		version.SetFile(V20_2_0_7);
		version.SetUser(12);
		version.SetStream(172);
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

// Compute per-vertex tangents for a Starfield BSGeometryMeshData from its verts/UVs/normals/
// tris, matching the vanilla convention. nifly's other shape types get this free in Create
// (BSTriShape/NiTriShapeData each override CalcTangentSpace), but BSGeometryMeshData inherits
// NiGeometryData's no-op, so we do it here.
//
// Verified against a vanilla body .mesh:
//   * the stored tangent is the U-direction (Lengyel's sdir), 100% of verts;
//   * the bitangent is reconstructed as cross(normal, tangent) * sign, where the 2-bit W is
//     3 when the per-vertex UV Jacobian determinant is positive and 0 when negative (the two
//     values 0/3 are the only ones vanilla uses; normals always carry W=1).
static void ComputeExternalMeshTangents(BSGeometryMeshData& md) {
	size_t nv = md.vertices.size();
	if (nv == 0 || md.uvSets.empty() || md.uvSets[0].size() != nv
		|| md.normals.size() != nv || md.tris.empty())
		return;

	std::vector<Vector3> tan(nv, Vector3(0.0f, 0.0f, 0.0f));
	std::vector<double> detsum(nv, 0.0);
	const std::vector<Vector2>& uvs = md.uvSets[0];

	for (const Triangle& tri : md.tris) {
		uint16_t i1 = tri.p1, i2 = tri.p2, i3 = tri.p3;
		if (i1 >= nv || i2 >= nv || i3 >= nv) continue;

		const Vector3& v1 = md.vertices[i1];
		const Vector3& v2 = md.vertices[i2];
		const Vector3& v3 = md.vertices[i3];

		float x1 = v2.x - v1.x, x2 = v3.x - v1.x;
		float y1 = v2.y - v1.y, y2 = v3.y - v1.y;
		float z1 = v2.z - v1.z, z2 = v3.z - v1.z;

		float s1 = uvs[i2].u - uvs[i1].u, s2 = uvs[i3].u - uvs[i1].u;
		float t1 = uvs[i2].v - uvs[i1].v, t2 = uvs[i3].v - uvs[i1].v;

		float det = s1 * t2 - s2 * t1;
		float r = (det >= 0.0f) ? 1.0f : -1.0f;
		// U-direction (the stored tangent), sign-corrected per triangle so mirrored islands
		// still accumulate coherently.
		Vector3 sdir((t2 * x1 - t1 * x2) * r, (t2 * y1 - t1 * y2) * r, (t2 * z1 - t1 * z2) * r);
		sdir.Normalize();

		tan[i1] += sdir; tan[i2] += sdir; tan[i3] += sdir;
		detsum[i1] += det; detsum[i2] += det; detsum[i3] += det;
	}

	md.tangents.assign(nv, Vector3(1.0f, 0.0f, 0.0f));
	md.tangentWs.assign(nv, 3);
	for (size_t i = 0; i < nv; i++) {
		Vector3 n = md.normals[i];
		Vector3 t = tan[i];
		if (t.IsZero())
			t = Vector3(n.y, n.z, n.x);        // arbitrary seed; orthonormalized below
		// Gram-Schmidt: make the tangent perpendicular to the normal, then normalize.
		t = t - n * n.dot(t);
		t.Normalize();
		md.tangents[i] = t;
		md.tangentWs[i] = (detsum[i] > 0.0) ? 3 : 0;
	}
}

NiShape* PyniflyCreateShape(NifFile* nif,
	const std::string& shapeName,
	NiShapeBuf* buf,
	const std::vector<Vector3>* v,
	const std::vector<Triangle>* t,
	const std::vector<Vector2>* uv,
	const std::vector<Vector3>* norms,
	NiNode* parentRef
) {
	/* 
	Copy of the nifly routine but handles BSDynamicTriShapes (and other subtypes of NiShape) 
	and BSEffectShaderProperties, also parents other than root.
	*/
	auto rootNode = nif->GetRootNode();
	auto parentNode = nif->GetRootNode();
	if (!rootNode)
		return nullptr;
	if (parentRef)
		parentNode = parentRef;

	NiVersion& version = nif->GetHeader().GetVersion();

	NiShape* shapeResult = nullptr;
	if (version.IsSF()) {
		// Starfield: every renderable is a BSGeometry whose geometry lives in external
		// .mesh files (flag 0x200 off). Build the block + one mesh (LOD) slot populated
		// from the passed data. Tangents, colors, meshName and skin are filled in by the
		// dedicated setBSGeometry* setters after creation (no read counterpart on the
		// generic Create path). The .mesh bytes are produced later by saveBSGeometryMeshData.
		auto bsGeom = std::make_unique<BSGeometry>();
		bsGeom->name.get() = shapeName;
		bsGeom->SetInternalGeomData(false);   // external geometry

		BSGeometryMesh* mesh = bsGeom->AddMesh();
		mesh->internalGeom = false;
		mesh->flags = 64;                     // observed constant on vanilla meshes
		BSGeometryMeshData& md = mesh->meshData;
		md.version = 1;                       // .mesh format version (game reads 0..2)

		// Populate verts/uvs/normals through nifly's Create: it sets the protected
		// numVertices and sizes vertices/uvSets/normals consistently (a direct assign
		// would be truncated later by SetVertices' resize-to-numVertices). Create ignores
		// the triangle argument, so the tris go in separately.
		md.Create(version, v, t, uv, norms);
		if (t) md.tris = *t;
		// Compute tangents from the geometry (BSGeometryMeshData has no real CalcTangentSpace,
		// unlike the other shape types). setBSGeometryTangents can still override afterward.
		ComputeExternalMeshTangents(md);

		// Per-mesh scale: the packer stores each position as
		//   int16 = component / (scale * havokScale) * 32767,
		// so scale must cover the largest game-unit extent (÷havokScale = metric).
		const float havokScale = 69.969f;
		float maxCoord = 0.0f;
		if (v) for (const auto& p : *v) {
			maxCoord = std::max(maxCoord,
				std::max(std::fabs(p.x), std::max(std::fabs(p.y), std::fabs(p.z))));
		}
		md.scale = (maxCoord > 0.0f) ? (maxCoord / havokScale) : 1.0f;

		if (buf->shaderPropertyID != NO_SHADER_REF) {
			auto nifTexset = std::make_unique<BSShaderTextureSet>(version);
			auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
			nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
			nifShader->SetSkinned(false);
			int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
			bsGeom->ShaderPropertyRef()->index = shaderID;
		}

		shapeResult = bsGeom.get();
		int shapeID = nif->GetHeader().AddBlock(std::move(bsGeom));
		parentNode->childRefs.AddBlockRef(shapeID);
	}
	else if (version.IsSSE() && buf->bufType == BUFFER_TYPES::NiTriShapeBufType) {
		// SSE files can legitimately contain NiTriShapes -- e.g. the lowest-LOD
		// billboards of vanilla skinned trees. Build NiTriShape + NiTriShapeData.
		auto nifTriShape = std::make_unique<NiTriShape>();
		nifTriShape->name.get() = shapeName;

		auto nifShapeData = std::make_unique<NiTriShapeData>();
		nifShapeData->Create(version, v, t, uv, norms);
		nifTriShape->SetGeomData(nifShapeData.get());
		int dataID = nif->GetHeader().AddBlock(std::move(nifShapeData));
		nifTriShape->DataRef()->index = dataID;
		nifTriShape->SetSkinned(false);

		if (buf->shaderPropertyID != NO_SHADER_REF) {
			auto nifTexset = std::make_unique<BSShaderTextureSet>(version);
			auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
			nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
			nifShader->SetSkinned(false);
			int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
			nifTriShape->ShaderPropertyRef()->index = shaderID;
		}

		shapeResult = nifTriShape.get();
		int shapeID = nif->GetHeader().AddBlock(std::move(nifTriShape));
		parentNode->childRefs.AddBlockRef(shapeID);
	}
	else if (version.IsSSE()) {
		std::unique_ptr<BSTriShape> triShape;
		bool isSkinned = false;

		if (buf->bufType == BUFFER_TYPES::BSDynamicTriShapeBufType) {
			triShape = std::make_unique<BSDynamicTriShape>();
			isSkinned = true; // If a headpart, it's skinned
		}
		else if (buf->bufType == BUFFER_TYPES::BSMeshLODTriShapeBufType) {
			triShape = std::make_unique<BSMeshLODTriShape>();
		}
		else if (buf->bufType == BUFFER_TYPES::BSSubIndexTriShapeBufType) {
			triShape = std::make_unique<BSSubIndexTriShape>();
		}
		else {
			triShape = std::make_unique<BSTriShape>();
		}
		triShape->Create(version, v, t, uv, norms);
		triShape->SetSkinned(isSkinned);
		shapeResult = triShape.get();

		if (buf->shaderPropertyID != NO_SHADER_REF) {
			auto nifTexset = std::make_unique<BSShaderTextureSet>(version);
			auto nifShader = std::make_unique<BSLightingShaderProperty>(version);
			nifShader->TextureSetRef()->index = nif->GetHeader().AddBlock(std::move(nifTexset));
			nifShader->SetSkinned(isSkinned);
			int shaderID = nif->GetHeader().AddBlock(std::move(nifShader));
			shapeResult->ShaderPropertyRef()->index = shaderID;
		}

		shapeResult->name.get() = shapeName;

		int shapeID;
		shapeID = nif->GetHeader().AddBlock(std::move(triShape));
		parentNode->childRefs.AddBlockRef(shapeID);
	}
	else if (version.IsFO4() || version.IsFO76()) {
		std::unique_ptr<BSTriShape> triShape;

		if (buf->bufType == BUFFER_TYPES::BSTriShapeBufType) {
			// Need to make a BSTriShape
			triShape = std::make_unique<BSTriShape>();
		}
		else if (buf->bufType == BUFFER_TYPES::BSMeshLODTriShapeBufType) {
			triShape = std::make_unique<BSMeshLODTriShape>();
		}
		else {
			triShape = std::make_unique<BSSubIndexTriShape>();
		}
		triShape->Create(version, v, t, uv, norms);
		triShape->SetSkinned(false);
		triShape->name.get() = shapeName;

		if (buf->shaderPropertyID != NO_SHADER_REF) {
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
		}

		shapeResult = triShape.get();

		int shapeID = nif->GetHeader().AddBlock(std::move(triShape));
		parentNode->childRefs.AddBlockRef(shapeID);
	}
	else {
		/* Skyrim LE and friends. */
		int shaderID = -1;

		if (buf->shaderPropertyID != NO_SHADER_REF) {
			auto nifTexset = std::make_unique<BSShaderTextureSet>(nif->GetHeader().GetVersion());

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
		}

		if (buf->bufType == BUFFER_TYPES::BSLODTriShapeBufType) {
			// Special handling because BSLODTriShape is not a subclass of BSTriShape.
			auto shape = std::make_unique<BSLODTriShape>();
			if (shaderID >= 0)
				shape->ShaderPropertyRef()->index = shaderID;
			shape->name.get() = shapeName;
			auto shapeData = std::make_unique<NiTriShapeData>();
			shapeData->Create(nif->GetHeader().GetVersion(), v, t, uv, norms);
			shape->SetGeomData(shapeData.get());
			int dataID = nif->GetHeader().AddBlock(std::move(shapeData));
			shape->DataRef()->index = dataID;
			shape->SetSkinned(false);
			shapeResult = shape.get();
			int shapeID = nif->GetHeader().AddBlock(std::move(shape));
			parentNode->childRefs.AddBlockRef(shapeID);
		}
		else {
			auto nifTriShape = std::make_unique<NiTriShape>();
			if (shaderID >= 0) {
				if (version.IsSK())
					nifTriShape->ShaderPropertyRef()->index = shaderID;
				else
					nifTriShape->propertyRefs.AddBlockRef(shaderID);
			}

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
	}

	return shapeResult;
}



