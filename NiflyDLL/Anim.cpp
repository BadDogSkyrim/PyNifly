/*
BodySlide and Outfit Studio
See the included LICENSE file
*/
/* *******************************************************
	PYNIFLY DLL: Copied from OS with minimal changes to make updating easier
*/

#include "Anim.h"
#include "NifUtil.hpp"
/* +++ NiflyDLL Changes +++ */
//#include <wx/log.h>
//#include <wx/msgdlg.h>
#include "logger.hpp"
#include <unordered_set>

//extern ConfigurationManager Config;
/* +++ NiflyDLL Changes +++ */

using namespace nifly;

bool AnimInfo::AddShapeBone(const std::string& shape, const std::string& boneName) {
	for (auto &bone : shapeBones[shape])
		if (!bone.compare(boneName))
			return false;

	shapeSkinning[shape].boneNames[boneName] = (uint8_t) shapeBones[shape].size();
	shapeBones[shape].push_back(boneName);
	GetSkeleton()->RefBone(boneName);
	RecalcXFormSkinToBone(shape, boneName);
	return true;
}

bool AnimInfo::RemoveShapeBone(const std::string& shape, const std::string& boneName) {
	auto& bones = shapeBones[shape];
	if (std::find(bones.begin(), bones.end(), boneName) == bones.end())
		return false;

	bones.erase(std::remove(bones.begin(), bones.end(), boneName), bones.end());
	shapeSkinning[shape].RemoveBone(boneName);

	GetSkeleton()->ReleaseBone(boneName);

	if (refNif && refNif->IsValid()) {
		if (GetSkeleton()->GetBoneRefCount(boneName) <= 0) {
			if (refNif->CanDeleteNode(boneName))
				refNif->DeleteNode(boneName);
		}
	}

	return true;
}

void AnimInfo::Clear() {
	if (refNif && refNif->IsValid()) {
		for (auto &shapeBoneList : shapeBones) {
			for (auto &boneName : shapeBoneList.second) {
				GetSkeleton()->ReleaseBone(boneName);

				if (GetSkeleton()->GetBoneRefCount(boneName) <= 0) {
					if (refNif->CanDeleteNode(boneName))
						refNif->DeleteNode(boneName);
				}
			}
		}

		shapeSkinning.clear();
		for (auto &s : refNif->GetShapeNames())
			shapeBones[s].clear();

		refNif = nullptr;
	}
	else {
		for (auto &shapeBoneList : shapeBones)
			for (auto &boneName : shapeBoneList.second)
				GetSkeleton()->ReleaseBone(boneName);

		shapeSkinning.clear();
		shapeBones.clear();
	}
}

void AnimInfo::ClearShape(const std::string& shape) {
	if (shape.empty())
		return;

	for (auto &boneName : shapeBones[shape]) {
		GetSkeleton()->ReleaseBone(boneName);

		if (refNif && refNif->IsValid()) {
			if (GetSkeleton()->GetBoneRefCount(boneName) <= 0) {
				if (refNif->CanDeleteNode(boneName))
					refNif->DeleteNode(boneName);
			}
		}
	}

	shapeBones.erase(shape);
	shapeSkinning.erase(shape);
}

bool AnimInfo::HasSkinnedShape(NiShape* shape) const {
	if (!shape)
		return false;

	if (shapeSkinning.find(shape->name.get()) != shapeSkinning.end())
		return true;
	else
		return false;
}

void AnimInfo::DeleteVertsForShape(const std::string& shape, const std::vector<uint16_t>& indices) {
	if (indices.empty())
		return;

	int highestRemoved = indices.back();
	std::vector<int> indexCollapse = GenerateIndexCollapseMap(indices, highestRemoved + 1);

	auto& skin = shapeSkinning[shape];
	for (auto &w : skin.boneWeights) {
		ApplyIndexMapToMapKeys(w.second.weights, indexCollapse, -static_cast<int>(indices.size()));
	}
}

void AnimSkin::InsertVertexIndices(const std::vector<uint16_t>& indices) {
	if (indices.empty())
		return;

	int highestAdded = indices.back();
	std::vector<int> indexExpand = GenerateIndexExpandMap(indices, highestAdded + 1);

	for (auto &w : boneWeights) {
		ApplyIndexMapToMapKeys(w.second.weights, indexExpand, static_cast<int>(indices.size()));
	}
}

void AnimWeight::LoadFromNif(NifFile* loadFromFile, NiShape* shape, const int& index) {
	loadFromFile->GetShapeBoneWeights(shape, index, weights);
	loadFromFile->GetShapeTransformSkinToBone(shape, index, xformSkinToBone);
	loadFromFile->GetShapeBoneBounds(shape, index, bounds);
}

void AnimSkin::LoadFromNif(NifFile* loadFromFile, NiShape* shape, AnimSkeleton* skel) {
	bool gotGTS = loadFromFile->GetShapeTransformGlobalToSkin(shape, xformGlobalToSkin);
	std::vector<int> idList;
	loadFromFile->GetShapeBoneIDList(shape, idList);

	int newID = 0;
	std::vector<MatTransform> eachXformGlobalToSkin;
	for (auto &id : idList) {
		auto node = loadFromFile->GetHeader().GetBlock<NiNode>(id);
		if (!node) continue;
		boneWeights[newID].LoadFromNif(loadFromFile, shape, newID);
		boneNames[node->name.get()] = newID;
		if (!gotGTS) {
			// We don't have a global-to-skin transform, probably because
			// the NIF has BSSkinBoneData instead of NiSkinData (FO4 or
			// newer).  So calculate by:
			//Compose: skin -> bone -> global
			// and inverting.
			MatTransform xformBoneToGlobal;
			if (skel->GetBoneTransformToGlobal(node->name.get(), xformBoneToGlobal)) {
				std::string bn = node->name.get();
				MatTransform bw = boneWeights[newID].xformSkinToBone;
				MatTransform cmp = xformBoneToGlobal.ComposeTransforms(bw);
				MatTransform inv = cmp.InverseTransform();

				eachXformGlobalToSkin.push_back(xformBoneToGlobal.ComposeTransforms(boneWeights[newID].xformSkinToBone).InverseTransform());
			}
		}
		newID++;
	}
	if (!eachXformGlobalToSkin.empty())
		xformGlobalToSkin = CalcMedianMatTransform(eachXformGlobalToSkin);
}

bool AnimInfo::LoadFromNif(NifFile* nif, AnimSkeleton* skel) {
	Clear();

	SetSkeleton(skel);
	for (auto &s : nif->GetShapes())
		LoadFromNif(nif, s, skel);

	refNif = nif;
	return true;
}

bool AnimInfo::LoadFromNif(NifFile* nif, NiShape* shape, AnimSkeleton* skel, bool newRefNif) {
	std::vector<std::string> boneNames;
	std::string nonRefBones;

	if (newRefNif)
		refNif = nif;

	if (!shape)
		return false;

	std::string shapeName = shape->name.get();
	if (!nif->GetShapeBoneList(shape, boneNames)) {
/* +++ NiflyDLL Changes +++ */
//		LogWritef("No skinning found in shape '%s'.", shapeName);
		wxLogWarning("No skinning found in shape '%s'.", shapeName.c_str());
/* +++ NiflyDLL Changes +++ */
		return false;
	}

	for (auto& bn : boneNames) {
		//if (!GetSkeleton()->RefBone(bn)) {
		//	AnimBone* cstm = GetSkeleton()->LoadCustomBoneFromNif(nif, bn);
		//	if (!cstm->isStandardBone)
		//		nonRefBones += bn + ", ";
		//	GetSkeleton()->RefBone(bn);
		//}
		AnimBone* cstm = GetSkeleton()->LoadCustomBoneFromNif(nif, bn);
		if (!GetSkeleton()->RefBone(bn)) {
			AnimBone* cstm = GetSkeleton()->LoadCustomBoneFromNif(nif, bn);
			if (!cstm->isStandardBone)
				nonRefBones += bn + ", ";
			GetSkeleton()->RefBone(bn);
		}

		shapeBones[shapeName].push_back(bn);
	}

	shapeSkinning[shapeName].LoadFromNif(nif, shape, skel);

	if (!nonRefBones.empty())
		wxLogMessage("Bones in shape '%s' not found in reference skeleton and added as custom bones: %s", shapeName.c_str(), nonRefBones.c_str());

	return true;
}

bool AnimInfo::CloneShape(NifFile* nif, NiShape* shape, const std::string& newShape) {
	if (!shape || newShape.empty())
		return false;

	std::string shapeName = shape->name.get();

	std::vector<std::string> boneNames;
	if (!nif->GetShapeBoneList(shape, boneNames)) {
		wxLogWarning("No skinning found in shape '%s'.", shapeName.c_str());
		return false;
	}

	for (auto &bn : boneNames) {
		GetSkeleton()->RefBone(bn);
		shapeBones[newShape].push_back(bn);
	}

	shapeSkinning[newShape] = shapeSkinning[shapeName];
	return true;
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

std::unordered_map<uint16_t, float>* AnimInfo::GetWeightsPtr(const std::string& shape, const std::string& boneName) {
	int b = GetShapeBoneIndex(shape, boneName);
	if (b < 0)
		return nullptr;

	return &shapeSkinning[shape].boneWeights[b].weights;
}

bool AnimInfo::HasWeights(const std::string& shape, const std::string& boneName) {
	auto weights = GetWeightsPtr(shape, boneName);
	if (weights && weights->size() > 0)
		return true;

	return false;
}

void AnimInfo::GetWeights(const std::string& shape, const std::string& boneName, std::unordered_map<uint16_t, float>& outVertWeights) {
	auto weights = GetWeightsPtr(shape, boneName);
	if (weights)
		outVertWeights = *weights;
}

bool AnimInfo::GetXFormSkinToBone(const std::string& shape, const std::string& boneName, MatTransform& stransform) {
	int b = GetShapeBoneIndex(shape, boneName);
	if (b < 0)
		return false;

	stransform = shapeSkinning[shape].boneWeights[b].xformSkinToBone;
	return true;
}

void AnimInfo::SetXFormSkinToBone(const std::string& shape, const std::string& boneName, const MatTransform& stransform) {
	int b = GetShapeBoneIndex(shape, boneName);
	if (b < 0)
		return;

	shapeSkinning[shape].boneWeights[b].xformSkinToBone = stransform;
}

void AnimInfo::RecalcXFormSkinToBone(const std::string& shape, const std::string& boneName) {
	// Calculate a good default value for xformSkinToBone by:
	// Composing: bone -> global -> skin
	// then inverting
	MatTransform xformGlobalToSkin = shapeSkinning[shape].xformGlobalToSkin;
	MatTransform xformBoneToGlobal;
	GetSkeleton()->GetBoneTransformToGlobal(boneName, xformBoneToGlobal);
	MatTransform xformBoneToSkin = xformGlobalToSkin.ComposeTransforms(xformBoneToGlobal);
	SetXFormSkinToBone(shape, boneName, xformBoneToSkin.InverseTransform());
}

void AnimInfo::RecursiveRecalcXFormSkinToBone(const std::string& shape, AnimBone *bPtr) {
	RecalcXFormSkinToBone(shape, bPtr->boneName);
	for (AnimBone *cptr : bPtr->children)
		RecursiveRecalcXFormSkinToBone(shape, cptr);
}

void AnimInfo::ChangeGlobalToSkinTransform(const std::string& shape, const MatTransform &newTrans) {
	shapeSkinning[shape].xformGlobalToSkin = newTrans;
	for (const std::string &bone : shapeBones[shape])
		RecalcXFormSkinToBone(shape, bone);
}

bool AnimInfo::UpdateShapeSkinBounds(const std::string& shapeName, const int& boneIndex) {
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
	for (auto &w : shapeSkinning[shapeName].boneWeights[boneIndex].weights) {
		if (w.first >= verts.size())		// Incoming weights have a larger set of possible verts.
			return false;

		boundVerts.push_back(verts[w.first]);
	}

	BoundingSphere bounds(boundVerts);

	const MatTransform &xformSkinToBone = shapeSkinning[shapeName].boneWeights[boneIndex].xformSkinToBone;

	bounds.center = xformSkinToBone.ApplyTransform(bounds.center);
	bounds.radius *= xformSkinToBone.scale;
	shapeSkinning[shapeName].boneWeights[boneIndex].bounds = bounds;
	return true;
}

void AnimInfo::SetWeights(const std::string& shape, const std::string& boneName, std::unordered_map<uint16_t, float>& inVertWeights) {
	int bid = GetShapeBoneIndex(shape, boneName);
	if (bid == 0xFFFFFFFF)
		return;

	shapeSkinning[shape].boneWeights[bid].weights = inVertWeights;
}

void AnimInfo::CleanupBones() {
	for (auto &skin : shapeSkinning) {
		std::vector<std::string> bonesToDelete;

		for (auto &bone : skin.second.boneNames) {
			bool hasInfluence = false;
			for (auto &bw : skin.second.boneWeights[bone.second].weights) {
				if (bw.second > 0.0f) {
					hasInfluence = true;
					break;
				}
			}

			if (!hasInfluence)
				bonesToDelete.push_back(bone.first);
		}

		for (auto &bone : bonesToDelete)
			RemoveShapeBone(skin.first, bone);
	}
}

void AnimInfo::WriteToNif(NifFile* nif, const std::string& shapeException) {
	// Collect list of needed bones.  Also delete bones used by shapeException
	// and no other shape if they have no children and have root parent.
	std::unordered_set<const AnimBone *> neededBones;
	for (auto &bones : shapeBones) {
		for (auto &bone : bones.second) {
			const AnimBone *bptr = GetSkeleton()->GetBonePtr(bone);
			if (!bptr)
				continue;

			if (bones.first == shapeException) {
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
	std::unordered_map<std::string, int> boneIDMap;
	for (const AnimBone *bptr : neededBones) {
		NiNode *node = nif->FindBlockByName<NiNode>(bptr->boneName);
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
				NiNode *pNode = nif->FindBlockByName<NiNode>(bptr->parent->boneName);
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
	for (NiNode *node : nif->GetNodes()) {
		const AnimBone *bptr = GetSkeleton()->GetBonePtr(node->name.get());
		if (!bptr)
			continue;	// Don't touch bones we don't know about
		if (!bptr->isStandardBone)
			continue;	// Custom bones have already been set
		NiNode *pNode = nif->GetParentNode(node);
		if (!pNode || pNode == nif->GetRootNode())
			// Parent node is root: use xformToGlobal
			node->SetTransformToParent(bptr->xformToGlobal);
		else if (bptr->parent && pNode->name.get() == bptr->parent->boneName)
			// Parent node is bone's parent's node: use xformToParent
			node->SetTransformToParent(bptr->xformToParent);
		else {
			// The parent node does not match our skeletal structure, so we
			// must calculate the transform.
			const AnimBone *nparent = GetSkeleton()->GetBonePtr(pNode->name.get());
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
	for (auto &bones : shapeBones) {
		if (bones.first == shapeException)
			continue;
		std::vector<int> bids;
		for (auto &bone : bones.second) {
			auto it = boneIDMap.find(bone);
			if (it != boneIDMap.end())
				bids.push_back(it->second);
		}
		auto shape = nif->FindBlockByName<NiShape>(bones.first);
		nif->SetShapeBoneIDList(shape, bids);
	}

	bool incomplete = false;
	bool isFO = nif->GetHeader().GetVersion().IsFO4() || nif->GetHeader().GetVersion().IsFO76();

	for (auto &shapeBoneList : shapeBones) {
		if (shapeBoneList.first == shapeException)
			continue;

		auto shape = nif->FindBlockByName<NiShape>(shapeBoneList.first);
		if (!shape)
			continue;

		bool isBSShape = shape->HasType<BSTriShape>();

		std::unordered_map<uint16_t, VertexBoneWeights> vertWeights;
		for (auto &boneName : shapeBoneList.second) {
			AnimBone* bptr = GetSkeleton()->GetBonePtr(boneName);

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

			if (UpdateShapeSkinBounds(shapeBoneList.first, bid))
				nif->SetShapeBoneBounds(shapeBoneList.first, bid, bw.bounds);
		}

		if (isBSShape) {
			nif->ClearShapeVertWeights(shapeBoneList.first);

			for (auto &vid : vertWeights)
				nif->SetShapeVertWeights(shapeBoneList.first, vid.first, vid.second.boneIds, vid.second.weights);
		}
	}

	if (incomplete)
/* +++ NiflyDLL Changes +++ */
		niflydll::LogWriteWf("Bone information incomplete. Exported data will not contain correct bone entries! Be sure to load a reference NIF prior to export.");
	//	wxMessageBox(_("Bone information incomplete. Exported data will not contain correct bone entries! Be sure to load a reference NIF prior to export."), _("Export Warning"), wxICON_WARNING);
/* +++ NiflyDLL Changes +++ */
}

void AnimInfo::RenameShape(const std::string& shapeName, const std::string& newShapeName) {
	if (shapeSkinning.find(shapeName) != shapeSkinning.end()) {
		shapeSkinning[newShapeName] = std::move(shapeSkinning[shapeName]);
		shapeSkinning.erase(shapeName);
	}

	if (shapeBones.find(shapeName) != shapeBones.end()) {
		shapeBones[newShapeName] = move(shapeBones[shapeName]);
		shapeBones.erase(shapeName);
	}
}

AnimBone& AnimBone::LoadFromNif(
	/* Read a bone from the nif */
	AnimSkeleton* skel, // - Skeleton to add the bones to
	NifFile* skeletonNif, // - Nif to read the bones from
	int srcBlock, // > Bone's block ID in the nif
	AnimBone* inParent // - Not used
	// Returns self 
)  {
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
		std::string name = skeletonNif->GetNodeName(child.index);
		if (!name.empty()) {
			if (name == "_unnamed_")
				name = AnimSkeleton::getInstance().GenerateBoneName();

			AnimBone& bone = skel->AddStandardBone(name).LoadFromNif(
					skel, skeletonNif, child.index, this);
			children.push_back(&bone);
		}
	}

	return *this;
}

NiNode* AnimBone::AddToNif(NifFile *nif) const {
	NiNode *pnode = nullptr;
	if (parent) {
		pnode = nif->FindBlockByName<NiNode>(parent->boneName);
		if (!pnode)
			pnode = parent->AddToNif(nif);
	}
	return nif->AddNode(boneName, xformToParent, pnode);
}

void AnimSkeleton::Clear() {
	allBones.clear();
	customBones.clear();
	refSkeletonNif.Clear();
	rootBone.clear();
	unknownCount = 0;
}
/* +++ NiflyDLL Changes +++ */
//NiflyDLL//int AnimSkeleton::LoadFromNif(const std::string& fileName) {
//NiflyDLL//Get root from caller, not configuration
int AnimSkeleton::LoadFromNif(const std::string& fileName, std::string theRoot) {
/* +++ NiflyDLL Changes +++ */
	Clear();

	int error = refSkeletonNif.Load(fileName);
	if (error) {
		wxLogError("Failed to load skeleton '%s'!", fileName.c_str());
/* +++ NiflyDLL Changes +++ */
		//wxMessageBox(wxString::Format(_("Failed to load skeleton '%s'!"), fileName));
/* +++ NiflyDLL Changes +++ */
		return 1;
	}

/* +++ NiflyDLL Changes +++ */
	//NiflyDLL//rootBone = Config["Anim/SkeletonRootName"];
	rootBone = theRoot;
/* +++ NiflyDLL Changes +++ */
	int nodeID = refSkeletonNif.GetBlockID(refSkeletonNif.FindBlockByName<NiNode>(rootBone));
	if (nodeID == 0xFFFFFFFF) {
		wxLogError("Root '%s' not found in skeleton '%s'!", rootBone.c_str(), fileName.c_str());
/* +++ NiflyDLL Changes +++ */
		//NiflyDLL//wxMessageBox(wxString::Format(_("Root '%s' not found in skeleton '%s'!"), rootBone, fileName));
/* +++ NiflyDLL Changes +++ */
		return 2;
	}

	allBones.clear();
	customBones.clear();

	AddStandardBone(rootBone).LoadFromNif(this, &refSkeletonNif, nodeID, nullptr);
	wxLogMessage("Loaded skeleton '%s' with root '%s'.", fileName.c_str(), rootBone.c_str());
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

std::string AnimSkeleton::GenerateBoneName() {
/* +++ NiflyDLL Changes +++ */
	//return wxString::Format("UnnamedBone_%i", unknownCount++).ToStdString();
	char buf[256];
	snprintf(buf, 256, "UnnamedBone_%i", unknownCount++);
	return std::string(buf);
/* +++ NiflyDLL Changes +++ */
}

AnimBone *AnimSkeleton::LoadCustomBoneFromNif(NifFile *nif, const std::string &boneName) {
	NiNode *node = nif->FindBlockByName<NiNode>(boneName);
	if (!node) return nullptr;
	AnimBone *parentBone = nullptr;
	NiNode *parentNode = nif->GetParentNode(node);
	if (parentNode) {
		parentBone = GetBonePtr(parentNode->name.get());
		if (!parentBone)
			parentBone = LoadCustomBoneFromNif(nif, parentNode->name.get());
	}
	AnimBone& cstm = AddCustomBone(boneName);
	cstm.SetTransformBoneToParent(node->GetTransformToParent());
	cstm.SetParentBone(parentBone);
	return &cstm;
}

bool AnimSkeleton::RefBone(const std::string& boneName) {
	if (customBones.find(boneName) != customBones.end()) {
		customBones[boneName].refCount++;
		return true;
	}
	if (allBones.find(boneName) != allBones.end()) {
		allBones[boneName].refCount++;
		return true;
	}
	//if (customBones.find(boneName) != customBones.end()) {
	//	customBones[boneName].refCount++;
	//	return true;
	//}
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
	if (allowCustom && customBones.find(boneName) != customBones.end())
		return &customBones[boneName];

	if (allBones.find(boneName) != allBones.end())
		return &allBones[boneName];

	//if (allowCustom && customBones.find(boneName) != customBones.end())
	//	return &customBones[boneName];

	return nullptr;
}

AnimBone* AnimSkeleton::GetRootBonePtr() {
	return &allBones[rootBone];
}

bool AnimSkeleton::GetBoneTransformToGlobal(const std::string &boneName, MatTransform& xform) {
	auto bone = GetBonePtr(boneName, allowCustomTransforms);
	if (!bone)
		return false;

	xform = bone->xformToGlobal;
	//xform.scale = 1.0f; // Scale should be ignored?
	return true;
}

size_t AnimSkeleton::GetActiveBoneCount() const {
	size_t c = 0;
	for (auto &ab : allBones) {
		if (ab.second.refCount > 0) {
			c++;
		}
	}

	for (auto &cb : customBones) {
		if (cb.second.refCount > 0) {
			c++;
		}
	}

	return c;
}

size_t AnimSkeleton::GetActiveBoneNames(std::vector<std::string>& outBoneNames) const {
	size_t c = 0;
	for (auto &ab : allBones) {
		if (ab.second.refCount > 0) {
			outBoneNames.push_back(ab.first);
			c++;
		}
	}

	for (auto &cb : customBones) {
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

void AnimBone::UpdateTransformToGlobal() {
	if (parent)
		xformToGlobal = parent->xformToGlobal.ComposeTransforms(xformToParent);
	else
		xformToGlobal = xformToParent;
	for (AnimBone *cptr : children)
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
	for (AnimBone *cptr : children)
		cptr->UpdatePoseTransform();
}

void AnimBone::SetTransformBoneToParent(const MatTransform &ttp) {
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
