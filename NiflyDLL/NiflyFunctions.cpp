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
#include "NiflyFunctions.hpp"

using namespace nifly;

typedef std::string String;

/* Yes, they're statics. And not a class in sight. Bite me. */
static std::filesystem::path projectRoot;

static String curSkeletonPath;
static String curGameDataPath; // Get this from OS if it turns out we need it
static String curRootName;

static std::vector<String> messageLog;

void LogInit() {
	messageLog.clear();
}

void LogWrite(std::string msg) {
	//std::ostringstream stringStream;
	//stringStream << "Hello";
	//std::string copyOfStr = stringStream.str();

	messageLog.push_back(msg);
}

int LogGetLen() {
	int len = 0;
	for (String s : messageLog) {
		len += s.size() + 1;
	}
	return len;
}

void LogGet(char* buf, int len) {
	String outStr;
	for (String s : messageLog) {
		outStr += s + '\n';
	};
	strcpy_s(buf, len - 1, outStr.c_str());
	buf[len - 1] = '\0';
}

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

void AddCustomBoneRef(const std::string& boneName, const std::string* parentBone = nullptr, 
		const MatTransform* xformToParent = nullptr) 
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
	AnimSkeleton::getInstance().LoadFromNif(SkeletonFile(game)); 
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
NiShape* CreateShapeFromData(
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


/* ************************* AnimSkeleton **************************** */

bool AnimInfo::LoadFromNif(NifFile* nif) {
	Clear();

	for (auto& s : nif->GetShapes())
		LoadFromNif(nif, s);

	refNif = nif;
	return true;
}

bool AnimInfo::LoadFromNif(NifFile* nif, NiShape* shape, bool newRefNif) {
	std::vector<String> boneNames;
	String nonRefBones;

	if (newRefNif)
		refNif = nif;

	if (!shape)
		return false;

	String shapeName = shape->name.get();
	if (!nif->GetShapeBoneList(shape, boneNames)) {
		//wxLogWarning("No skinning found in shape '%s'.", shapeName);
		return false;
	}

	for (auto& bn : boneNames) {
		if (!AnimSkeleton::getInstance().RefBone(bn)) {
			AnimBone* cstm = AnimSkeleton::getInstance().LoadCustomBoneFromNif(nif, bn);
			if (!cstm->isStandardBone)
				nonRefBones += bn + "\n";
			AnimSkeleton::getInstance().RefBone(bn);
		}

		shapeBones[shapeName].push_back(bn);
	}

	shapeSkinning[shapeName].LoadFromNif(nif, shape);

	//if (!nonRefBones.empty())
	//	wxLogMessage("Bones in shape '%s' not found in reference skeleton and added as custom bones:\n%s", shapeName, nonRefBones);

	return true;
}

void AnimInfo::Clear() {
	if (refNif && refNif->IsValid()) {
		for (auto& shapeBoneList : shapeBones) {
			for (auto& boneName : shapeBoneList.second) {
				AnimSkeleton::getInstance().ReleaseBone(boneName);

				if (AnimSkeleton::getInstance().GetBoneRefCount(boneName) <= 0) {
					if (refNif->CanDeleteNode(boneName))
						refNif->DeleteNode(boneName);
				}
			}
		}

		shapeSkinning.clear();
		for (auto& s : refNif->GetShapeNames())
			shapeBones[s].clear();

		refNif = nullptr;
	}
	else {
		for (auto& shapeBoneList : shapeBones)
			for (auto& boneName : shapeBoneList.second)
				AnimSkeleton::getInstance().ReleaseBone(boneName);

		shapeSkinning.clear();
		shapeBones.clear();
	}
}

void AnimInfo::WriteToNif(NifFile* nif, const std::string& shapeException) {
	// Collect list of needed bones.  Also delete bones used by shapeException
	// and no other shape if they have no children and have root parent.
	std::unordered_set<const AnimBone*> neededBones;
	for (auto& bones : shapeBones) {
		for (auto& bone : bones.second) {
			const AnimBone* bptr = AnimSkeleton::getInstance().GetBonePtr(bone);
			if (!bptr)
				continue;

			if ((shapeException != "") && bones.first == shapeException) {
				if (bptr->refCount <= 1) {
					if (nif->CanDeleteNode(bone))
						nif->DeleteNode(bone);
				}
				continue;
			}

			neededBones.insert(bptr);
		}
	}

	// Make sure each needed bone has a node by creating it if necessary.
	// Also, for each custom bone, set parent and transform to parent.
	// Also, generate map of bone names to node IDs.
	std::unordered_map<String, int> boneIDMap;
	for (const AnimBone* bptr : neededBones) {
		NiNode* node = nif->FindBlockByName<NiNode>(bptr->boneName);
		if (!node) {
			if (bptr->isStandardBone)
				// If new standard bone, add to root and use xformToGlobal
				node = nif->AddNode(bptr->boneName, bptr->xformToGlobal);
			else
				// If new custom bone, add to parent, recursively
				node = bptr->AddToNif(nif);
		}
		else if (!bptr->isStandardBone) {
			// If old (exists in nif) custom bone...
			if (!bptr->parent) {
				// If old custom bone with no parent, set parent node to root.
				nif->SetParentNode(node, nullptr);
			}
			else {
				// If old custom bone with parent, find parent bone's node
				NiNode* pNode = nif->FindBlockByName<NiNode>(bptr->parent->boneName);
				if (!pNode)
					// No parent: add parent recursively.
					pNode = bptr->parent->AddToNif(nif);
				nif->SetParentNode(node, pNode);
			}
			node->SetTransformToParent(bptr->xformToParent);
		}
		boneIDMap[bptr->boneName] = nif->GetBlockID(node);
	}

	// Set the node-to-parent transform for every standard-bone node,
	// even ones we don't use.
	for (NiNode* node : nif->GetNodes()) {
		const AnimBone* bptr = AnimSkeleton::getInstance().GetBonePtr(node->name.get());
		if (!bptr)
			continue;	// Don't touch bones we don't know about
		if (!bptr->isStandardBone)
			continue;	// Custom bones have already been set
		NiNode* pNode = nif->GetParentNode(node);
		if (!pNode || pNode == nif->GetRootNode())
			// Parent node is root: use xformToGlobal
			node->SetTransformToParent(bptr->xformToGlobal);
		else if (bptr->parent && pNode->name.get() == bptr->parent->boneName)
			// Parent node is bone's parent's node: use xformToParent
			node->SetTransformToParent(bptr->xformToParent);
		else {
			// The parent node does not match our skeletal structure, so we
			// must calculate the transform.
			const AnimBone* nparent = AnimSkeleton::getInstance().GetBonePtr(pNode->name.get());
			if (nparent) {
				MatTransform p2g = nparent->xformToGlobal;
				// Now compose: bone cs -> global cs -> parent node's bone cs
				MatTransform b2p = p2g.InverseTransform().ComposeTransforms(bptr->xformToGlobal);
				node->SetTransformToParent(b2p);
			}
			// if nparent is nullptr, give up: the node has an unknown
			// parent, so we can't sensibly set its node-to-parent transform.
		}
	}

	// Generate bone node ID list for each shape and set it.
	for (auto& bones : shapeBones) {
		if (bones.first == shapeException)
			continue;
		std::vector<int> bids;
		for (auto& bone : bones.second) {
			auto it = boneIDMap.find(bone);
			if (it != boneIDMap.end())
				bids.push_back(it->second);
		}
		auto shape = nif->FindBlockByName<NiShape>(bones.first);
		nif->SetShapeBoneIDList(shape, bids);
	}

	bool incomplete = false;
	bool isFO = nif->GetHeader().GetVersion().IsFO4() || nif->GetHeader().GetVersion().IsFO76();

	for (auto& shapeBoneList : shapeBones) {
		if (shapeBoneList.first == shapeException)
			continue;

		auto shape = nif->FindBlockByName<NiShape>(shapeBoneList.first);
		if (!shape)
			continue;

		bool isBSShape = shape->HasType<BSTriShape>();

		std::unordered_map<uint16_t, VertexBoneWeights> vertWeights;
		for (auto& boneName : shapeBoneList.second) {
			AnimBone* bptr = AnimSkeleton::getInstance().GetBonePtr(boneName);

			int bid = GetShapeBoneIndex(shapeBoneList.first, boneName);
			AnimWeight& bw = shapeSkinning[shapeBoneList.first].boneWeights[bid];

			if (isBSShape)
				for (auto vw : bw.weights)
					vertWeights[vw.first].Add(bid, vw.second);

			nif->SetShapeTransformSkinToBone(shape, bid, bw.xformSkinToBone);
			if (!bptr)
				incomplete = true;
			if (!isFO)
				nif->SetShapeBoneWeights(shapeBoneList.first, bid, bw.weights);

			if (CalcShapeSkinBounds(shapeBoneList.first, bid))
				nif->SetShapeBoneBounds(shapeBoneList.first, bid, bw.bounds);
		}

		if (isBSShape) {
			nif->ClearShapeVertWeights(shapeBoneList.first);

			for (auto& vid : vertWeights)
				nif->SetShapeVertWeights(shapeBoneList.first, vid.first, vid.second.boneIds, vid.second.weights);
		}
	}

	//if (incomplete)
	//	wxMessageBox(_("Bone information incomplete. Exported data will not contain correct bone entries! Be sure to load a reference NIF prior to export."), _("Export Warning"), wxICON_WARNING);
}

int AnimInfo::GetShapeBoneIndex(const std::string& shapeName, const std::string& boneName) const {
	const auto& skin = shapeSkinning.find(shapeName);
	if (skin != shapeSkinning.end()) {
		const auto& bone = skin->second.boneNames.find(boneName);
		if (bone != skin->second.boneNames.end())
			return bone->second;
	}

	return -1;
}

bool AnimInfo::CalcShapeSkinBounds(const std::string& shapeName, const int& boneIndex) {
	if (!refNif || !refNif->IsValid())	// Check for existence of reference nif
		return false;

	if (shapeSkinning.find(shapeName) == shapeSkinning.end())	// Check for shape in skinning data
		return false;

	auto shape = refNif->FindBlockByName<NiShape>(shapeName);

	std::vector<Vector3> verts;
	refNif->GetVertsForShape(shape, verts);
	if (verts.size() == 0)	// Check for empty shape
		return false;

	std::vector<Vector3> boundVerts;
	for (auto& w : shapeSkinning[shapeName].boneWeights[boneIndex].weights) {
		if (w.first >= verts.size())		// Incoming weights have a larger set of possible verts.
			return false;

		boundVerts.push_back(verts[w.first]);
	}

	BoundingSphere bounds(boundVerts);

	const MatTransform& xformSkinToBone = shapeSkinning[shapeName].boneWeights[boneIndex].xformSkinToBone;

	bounds.center = xformSkinToBone.ApplyTransform(bounds.center);
	bounds.radius *= xformSkinToBone.scale;
	shapeSkinning[shapeName].boneWeights[boneIndex].bounds = bounds;
	return true;
}

void AnimInfo::ChangeGlobalToSkinTransform(const std::string& shape, const MatTransform& newTrans) {
	shapeSkinning[shape].xformGlobalToSkin = newTrans;
	for (const String& bone : shapeBones[shape])
		RecalcXFormSkinToBone(shape, bone);
}

void AnimInfo::RecalcXFormSkinToBone(const std::string& shape, const std::string& boneName) {
	// Calculate a good default value for xformSkinToBone by:
	// Composing: bone -> global -> skin
	// then inverting
	MatTransform xformGlobalToSkin = shapeSkinning[shape].xformGlobalToSkin;
	MatTransform xformBoneToGlobal;
	AnimSkeleton::getInstance().GetBoneTransformToGlobal(boneName, xformBoneToGlobal);
	MatTransform xformBoneToSkin = xformGlobalToSkin.ComposeTransforms(xformBoneToGlobal);
	SetXFormSkinToBone(shape, boneName, xformBoneToSkin.InverseTransform());
}

void AnimInfo::SetXFormSkinToBone(const std::string& shape, const std::string& boneName, const MatTransform& stransform) {
	int b = GetShapeBoneIndex(shape, boneName);
	if (b < 0)
		return;

	shapeSkinning[shape].boneWeights[b].xformSkinToBone = stransform;
}

bool AnimInfo::AddShapeBone(const std::string& shape, const std::string& boneName) {
	for (auto& bone : shapeBones[shape])
		if (!bone.compare(boneName))
			return false;

	shapeSkinning[shape].boneNames[boneName] = shapeBones[shape].size();
	shapeBones[shape].push_back(boneName);
	AnimSkeleton::getInstance().RefBone(boneName);
	RecalcXFormSkinToBone(shape, boneName);
	return true;
}

void AnimInfo::SetWeights(const std::string& shape, const std::string& boneName, std::unordered_map<uint16_t, float>& inVertWeights) {
	int bid = GetShapeBoneIndex(shape, boneName);
	if (bid == 0xFFFFFFFF)
		return;

	shapeSkinning[shape].boneWeights[bid].weights = inVertWeights;
}


/* ************************* AnimSkeleton **************************** */

void AnimSkeleton::Clear() {
	allBones.clear();
	customBones.clear();
	refSkeletonNif.Clear();
	rootBone.clear();
	unknownCount = 0;
}

int AnimSkeleton::LoadFromNif(const std::string& fileName) {
	Clear();

	int error = refSkeletonNif.Load(fileName);
	if (error) {
		//wxLogError("Failed to load skeleton '%s'!", fileName);
		//wxMessageBox(wxString::Format(_("Failed to load skeleton '%s'!"), fileName));
		LogWrite("Error: Failed to load skeleton '" + fileName + "'");
		return 1;
	}

	rootBone = curRootName;
	int nodeID = refSkeletonNif.GetBlockID(refSkeletonNif.FindBlockByName<NiNode>(rootBone));
	if (nodeID == 0xFFFFFFFF) {
		//wxLogError("Root '%s' not found in skeleton '%s'!", rootBone, fileName);
		//wxMessageBox(wxString::Format(_("Root '%s' not found in skeleton '%s'!"), rootBone, fileName));
		LogWrite("Error: Root '" + rootBone + "' not found in skeleton '" + fileName + "'");
		return 2;
	}

	allBones.clear();
	customBones.clear();

	AddStandardBone(rootBone).LoadFromNif(&refSkeletonNif, nodeID, nullptr);
	//wxLogMessage("Loaded skeleton '%s' with root '%s'.", fileName, rootBone);
	return 0;
}

AnimBone& AnimSkeleton::AddStandardBone(const std::string& boneName) {
	return allBones[boneName];
}

AnimBone& AnimSkeleton::AddCustomBone(const std::string& boneName) {
	AnimBone* cb = &customBones[boneName];
	cb->boneName = boneName;
	return *cb;
}

String AnimSkeleton::GenerateBoneName() {
	return "UnnamedBone_" + std::to_string(unknownCount++);
}

AnimBone* AnimSkeleton::LoadCustomBoneFromNif(NifFile* nif, const std::string& boneName) {
	NiNode* node = nif->FindBlockByName<NiNode>(boneName);
	if (!node) return nullptr;
	AnimBone* parentBone = nullptr;
	NiNode* parentNode = nif->GetParentNode(node);
	if (parentNode) {
		parentBone = GetBonePtr(parentNode->name.get());
		if (!parentBone)
			parentBone = LoadCustomBoneFromNif(nif, parentNode->name.get());
	}
	AnimBone& cstm = AnimSkeleton::getInstance().AddCustomBone(boneName);
	cstm.SetTransformBoneToParent(node->GetTransformToParent());
	cstm.SetParentBone(parentBone);
	return &cstm;
}

bool AnimSkeleton::RefBone(const std::string& boneName) {
	if (allBones.find(boneName) != allBones.end()) {
		allBones[boneName].refCount++;
		return true;
	}
	if (customBones.find(boneName) != customBones.end()) {
		customBones[boneName].refCount++;
		return true;
	}
	return false;
}

bool AnimSkeleton::ReleaseBone(const std::string& boneName) {
	if (allBones.find(boneName) != allBones.end()) {
		allBones[boneName].refCount--;
		return true;
	}
	if (customBones.find(boneName) != customBones.end()) {
		customBones[boneName].refCount--;
		return true;
	}
	return false;
}

int AnimSkeleton::GetBoneRefCount(const std::string& boneName) {
	if (allBones.find(boneName) != allBones.end())
		return allBones[boneName].refCount;

	if (customBones.find(boneName) != customBones.end())
		return customBones[boneName].refCount;

	return 0;
}

AnimBone* AnimSkeleton::GetBonePtr(const std::string& boneName, const bool allowCustom) {
	if (allBones.find(boneName) != allBones.end())
		return &allBones[boneName];

	if (allowCustom && customBones.find(boneName) != customBones.end())
		return &customBones[boneName];

	return nullptr;
}

AnimBone* AnimSkeleton::GetRootBonePtr() {
	return &allBones[rootBone];
}

bool AnimSkeleton::GetBoneTransformToGlobal(const std::string& boneName, MatTransform& xform) {
	auto bone = GetBonePtr(boneName, allowCustomTransforms);
	if (!bone)
		return false;

	xform = bone->xformToGlobal;
	//xform.scale = 1.0f; // Scale should be ignored?
	return true;
}

int AnimSkeleton::GetActiveBoneNames(std::vector<std::string>& outBoneNames) const {
	int c = 0;
	for (auto& ab : allBones) {
		if (ab.second.refCount > 0) {
			outBoneNames.push_back(ab.first);
			c++;
		}
	}

	for (auto& cb : customBones) {
		if (cb.second.refCount > 0) {
			outBoneNames.push_back(cb.first);
			c++;
		}
	}
	return c;
}

void AnimSkeleton::DisableCustomTransforms() {
	allowCustomTransforms = false;
}

/* ************************* AnimWeight **************************** */

void AnimBone::UpdateTransformToGlobal() {
	if (parent)
		xformToGlobal = parent->xformToGlobal.ComposeTransforms(xformToParent);
	else
		xformToGlobal = xformToParent;
	for (AnimBone* cptr : children)
		cptr->UpdateTransformToGlobal();
}

void AnimBone::UpdatePoseTransform() {
	// this bone's pose -> this bone -> parent bone's pose -> global
	MatTransform xformPoseToBone;
	xformPoseToBone.translation = poseTranVec;
	xformPoseToBone.rotation = RotVecToMat(poseRotVec);
	MatTransform xformPoseToParent = xformToParent.ComposeTransforms(xformPoseToBone);
	if (parent)
		xformPoseToGlobal = parent->xformPoseToGlobal.ComposeTransforms(xformPoseToParent);
	else
		xformPoseToGlobal = xformPoseToParent;
	for (AnimBone* cptr : children)
		cptr->UpdatePoseTransform();
}

void AnimBone::SetTransformBoneToParent(const MatTransform& ttp) {
	xformToParent = ttp;
	UpdateTransformToGlobal();
	UpdatePoseTransform();
}

void AnimBone::SetParentBone(AnimBone* newParent) {
	if (parent == newParent)
		return;
	if (parent) {
		//std::erase(parent->children, this);
		auto it = std::remove(parent->children.begin(), parent->children.end(), this);
		parent->children.erase(it, parent->children.end());
	}
	parent = newParent;
	if (parent)
		parent->children.push_back(this);
	UpdateTransformToGlobal();
	UpdatePoseTransform();
}

AnimBone& AnimBone::LoadFromNif(NifFile* skeletonNif, int srcBlock, AnimBone* inParent) {
	parent = inParent;
	isStandardBone = false;
	auto node = skeletonNif->GetHeader().GetBlock<NiNode>(srcBlock);
	if (!node)
		return *this;
	isStandardBone = true;

	boneName = node->name.get();
	refCount = 0;

	SetTransformBoneToParent(node->GetTransformToParent());

	for (auto& child : node->childRefs) {
		String name = skeletonNif->GetNodeName(child.index);
		if (!name.empty()) {
			if (name == "_unnamed_")
				name = AnimSkeleton::getInstance().GenerateBoneName();

			AnimBone& bone = AnimSkeleton::getInstance().AddStandardBone(name).LoadFromNif(skeletonNif, child.index, this);
			children.push_back(&bone);
		}
	}

	return *this;
}

NiNode* AnimBone::AddToNif(NifFile* nif) const {
	NiNode* pnode = nullptr;
	if (parent) {
		pnode = nif->FindBlockByName<NiNode>(parent->boneName);
		if (!pnode)
			pnode = parent->AddToNif(nif);
	}
	return nif->AddNode(boneName, xformToParent, pnode);
}

/* ************************* AnimWeight **************************** */

void AnimWeight::LoadFromNif(NifFile* loadFromFile, NiShape* shape, const int& index) {
	loadFromFile->GetShapeBoneWeights(shape, index, weights);
	loadFromFile->GetShapeTransformSkinToBone(shape, index, xformSkinToBone);
	loadFromFile->GetShapeBoneBounds(shape, index, bounds);
}

/* ************************* AnimSkin **************************** */

void AnimSkin::LoadFromNif(NifFile* loadFromFile, NiShape* shape) {
	bool gotGTS = loadFromFile->GetShapeTransformGlobalToSkin(shape, xformGlobalToSkin);
	std::vector<int> idList;
	loadFromFile->GetShapeBoneIDList(shape, idList);

	int newID = 0;
	std::vector<MatTransform> eachXformGlobalToSkin;
	for (auto& id : idList) {
		auto node = loadFromFile->GetHeader().GetBlock<NiNode>(id);
		if (!node) continue;
		boneWeights[newID].LoadFromNif(loadFromFile, shape, newID);
		boneNames[node->name.get()] = newID;
		if (!gotGTS) {
			// We don't have a global-to-skin transform, probably because
			// the NIF has BSSkinBoneData instead of NiSkinData (FO4 or
			// newer).  So calculate by:
			// Compose: skin -> bone -> global
			// and inverting.
			MatTransform xformBoneToGlobal;
			if (AnimSkeleton::getInstance().GetBoneTransformToGlobal(node->name.get(), xformBoneToGlobal)) {
				eachXformGlobalToSkin.push_back(xformBoneToGlobal.ComposeTransforms(boneWeights[newID].xformSkinToBone).InverseTransform());
			}
		}
		newID++;
	}
	if (!eachXformGlobalToSkin.empty())
		xformGlobalToSkin = CalcMedianMatTransform(eachXformGlobalToSkin);
}

void AnimSkin::InsertVertexIndices(const std::vector<uint16_t>& indices) {
	if (indices.empty())
		return;

	int highestAdded = indices.back();
	std::vector<int> indexExpand = GenerateIndexExpandMap(indices, highestAdded + 1);

	for (auto& w : boneWeights) {
		ApplyIndexMapToMapKeys(w.second.weights, indexExpand, indices.size());
	}
}

class AnimPartition {
public:
	int bodypart;									// Body part number (from BSDismembermentSkinInstance/partiitons).
	std::vector<nifly::Triangle> tris;				// Points are indices to the verts list for this partition. (eg. starting at 0).
	std::vector<int> verts;							// All referenced verts in this partition.
	std::vector<int> bones;							// All referenced bones in this partition.
	std::vector<std::vector<float>> vertWeights;	// Vert order list of weights per vertex.
	std::vector<std::vector<int>> vertBones;		// Vert order list of bones per vertex.
};

