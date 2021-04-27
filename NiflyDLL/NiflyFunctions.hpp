/*
	Functions and classes allowing convenient manipulation of nif files. Provides a layer
	of abstraction for creating nifs that Nifly provides for reading them.

	Copied from Outfit Studio, all their copywrite restrictions apply
	*/
#include "object3d.hpp"
#include "NifFile.hpp"
#include "NifUtil.hpp"
#include <map>

#pragma once

enum TargetGame {
	FO3, FONV, SKYRIM, FO4, SKYRIMSE, FO4VR, SKYRIMVR, FO76
};


struct VertexBoneWeights {
	std::vector<uint8_t> boneIds;
	std::vector<float> weights;

	void Add(const uint8_t inBoneId, const float inWeight) {
		if (inWeight == 0.0f)
			return;

		for (int i = 0; i < weights.size(); ++i) {
			if (inWeight < weights[i])
				continue;

			weights.insert(weights.begin() + i, inWeight);
			boneIds.insert(boneIds.begin() + i, inBoneId);
			return;
		}

		weights.push_back(inWeight);
		boneIds.push_back(inBoneId);
	}
};

class AnimBone {
public:
	std::string boneName = "bogus";		// bone names are node names in the nif file
	bool isStandardBone = false;
	AnimBone* parent = nullptr;
	std::vector<AnimBone*> children;
	// xformToGlobal: transforms from this bone's CS to the global CS.
	nifly::MatTransform xformToGlobal;
	// xformToParent: transforms from this bone's CS to its parent's CS.
	nifly::MatTransform xformToParent;
	// pose rotation and translation vectors
	nifly::Vector3 poseRotVec, poseTranVec;
	nifly::MatTransform xformPoseToGlobal;

	int refCount = 0;					// reference count of this bone

	AnimBone& LoadFromNif(nifly::NifFile* skeletonNif, int srcBlock, AnimBone* parent = nullptr);
	// AddToNif adds this bone to the given nif, as well as its parent
	// if missing, recursively.  The new bone's NiNode is returned.
	nifly::NiNode* AddToNif(nifly::NifFile* nif) const;
	// SetTransformBoneToParent sets xformToParent and updates xformToGlobal
	// and xformPoseToGlobal, for this and for descendants.
	void SetTransformBoneToParent(const nifly::MatTransform& ttp);
	// UpdateTransformToGlobal updates xformToGlobal for this and for
	// descendants.  This should only be called from itself,
	// SetTransformBoneToParent, and SetParentBone.
	void UpdateTransformToGlobal();
	// UpdatePoseTransform updates xformPoseToGlobal for this and all
	// descendants.  Call it after poseRotVec, poseTranVec, or
	// xformToGlobal is changed.
	void UpdatePoseTransform();
	// SetParentBone updates "parent" of this and "children" of the old
	// and new parents.  It also calls UpdateTransformToGlobal and
	// UpdatePoseTranform.
	void SetParentBone(AnimBone* newParent);
};

// Vertex to weight value association. Also keeps track of skin-to-bone transform and bounding sphere.
class AnimWeight {
public:
	std::unordered_map<uint16_t, float> weights;
	nifly::MatTransform xformSkinToBone;
	nifly::BoundingSphere bounds;

	void LoadFromNif(nifly::NifFile* loadFromFile, nifly::NiShape* shape, const int& index);
};

// Bone to weight list association.
class AnimSkin {
public:
	std::unordered_map<int, AnimWeight> boneWeights;
	std::unordered_map<std::string, int> boneNames;
	nifly::MatTransform xformGlobalToSkin;

	void LoadFromNif(nifly::NifFile* loadFromFile, nifly::NiShape* shape);

	void RemoveBone(const std::string& boneName) {
		auto bone = boneNames.find(boneName);
		if (bone == boneNames.end())
			return;

		int boneID = bone->second;
		std::unordered_map<int, AnimWeight> bwTemp;
		for (auto& bw : boneWeights) {
			if (bw.first > boneID)
				bwTemp[bw.first - 1] = std::move(bw.second);
			else if (bw.first < boneID)
				bwTemp[bw.first] = std::move(bw.second);
		}

		boneWeights.clear();

		for (auto& bw : bwTemp)
			boneWeights[bw.first] = std::move(bw.second);

		boneNames.erase(boneName);
		for (auto& bn : boneNames)
			if (bn.second > boneID)
				bn.second--;
	}

	void InsertVertexIndices(const std::vector<uint16_t>& indices);
};

/* Represents animation weighting to a common skeleton across multiple shapes, sourced from nif files*/
class AnimInfo {
private:
	nifly::NifFile* refNif = nullptr;

public:
	std::map<std::string, std::vector<std::string>> shapeBones;
	std::unordered_map<std::string, AnimSkin> shapeSkinning;		// Shape to skin association.

	nifly::NifFile* GetRefNif() { return refNif; };
	const nifly::NifFile* GetRefNif() const { return refNif; };
	void SetRefNif(nifly::NifFile* nif) { refNif = nif; };

	// Returns true if a new bone is added, false if the bone already exists.
	bool AddShapeBone(const std::string& shape, const std::string& boneName);
//	bool RemoveShapeBone(const std::string& shape, const std::string& boneName);

	void Clear();
//	void ClearShape(const std::string& shape);
//	bool HasSkinnedShape(nifly::NiShape* shape) const;
//	void DeleteVertsForShape(const std::string& shape, const std::vector<uint16_t>& indices);

	// Loads the skinning information contained in the nif for all shapes.
	// Returns false if there is no skinning information.
	bool LoadFromNif(nifly::NifFile* nif);
	bool LoadFromNif(nifly::NifFile* nif, nifly::NiShape* shape, bool newRefNif = true);
	//bool CloneShape(nifly::NifFile* nif, nifly::NiShape* shape, const std::string& newShape);

	int GetShapeBoneIndex(const std::string& shapeName, const std::string& boneName) const;
	//std::unordered_map<uint16_t, float>* GetWeightsPtr(const std::string& shape, const std::string& boneName);
	//bool HasWeights(const std::string& shape, const std::string& boneName);
	//void GetWeights(const std::string& shape, const std::string& boneName, std::unordered_map<uint16_t, float>& outVertWeights);
	void SetWeights(const std::string& shape, const std::string& boneName, std::unordered_map<uint16_t, float>& inVertWeights);
	//bool GetXFormSkinToBone(const std::string& shape, const std::string& boneName, nifly::MatTransform& stransform);
	void SetXFormSkinToBone(const std::string& shape, const std::string& boneName, const nifly::MatTransform& stransform);
	// RecalcXFormSkinToBone recalculates a shape bone's xformSkinToBone
	// from other transforms.
	void RecalcXFormSkinToBone(const std::string& shape, const std::string& boneName);
	//// RecursiveRecalcXFormSkinToBone calls RecalcXFormSkinToBone for the
	//// given bone and all its descendants.
	//void RecursiveRecalcXFormSkinToBone(const std::string& shape, AnimBone* bPtr);
	//ChangeGlobalToSkinTransform sets the global-to-skin transform for a
	// shape and updates all skin-to-bone transforms.
	void ChangeGlobalToSkinTransform(const std::string& shape, const nifly::MatTransform& newTrans);
	bool CalcShapeSkinBounds(const std::string& shapeName, const int& boneIndex);
	//void CleanupBones();
	void WriteToNif(nifly::NifFile* nif, const std::string& shapeException);

	//void RenameShape(const std::string& shapeName, const std::string& newShapeName);
};

/* AnimSkeleton
   Represents a game's skeleton for animating bodies and other objects.
   */
class AnimSkeleton {
	std::map<std::string, AnimBone> allBones;
	std::map<std::string, AnimBone> customBones;
	std::string rootBone;
	int unknownCount = 0;
	bool allowCustomTransforms = true;

	AnimSkeleton() {}

public:
	static AnimSkeleton& getInstance() {
		static AnimSkeleton instance;
		return instance;
	}

	nifly::NifFile refSkeletonNif;

	void Clear();
	
	int LoadForGame(enum TargetGame game);
	int LoadFromNif(const std::string& fileName);
	AnimBone& AddStandardBone(const std::string& boneName);
	AnimBone& AddCustomBone(const std::string& boneName);
	std::string GenerateBoneName();
	AnimBone* LoadCustomBoneFromNif(nifly::NifFile* nif, const std::string& boneName);

	bool RefBone(const std::string& boneName);
	bool ReleaseBone(const std::string& boneName);
	int GetBoneRefCount(const std::string& boneName);

	AnimBone* GetBonePtr(const std::string& boneName, const bool allowCustom = true);
	AnimBone* GetRootBonePtr();
	bool GetBoneTransformToGlobal(const std::string& boneName, nifly::MatTransform& xform);

	int GetActiveBoneNames(std::vector<std::string>& outBoneNames) const;
	void DisableCustomTransforms();
};

void LogInit();

void LogWrite(std::string msg);

int LogGetLen();

void LogGet(char* buf, int len);

std::string SkeletonFile(enum TargetGame game);

void SetNifVersion(nifly::NifFile* nif, enum TargetGame targ);

void AddCustomBoneRe(const std::string& boneName, const std::string* parentBone = nullptr,
	const nifly::MatTransform* xformToParent = nullptr);

AnimInfo* CreateSkinForNif(nifly::NifFile* nif, enum TargetGame game);

void GetGlobalToSkin(AnimInfo* anim, nifly::NiShape* theShape, nifly::MatTransform* outXform);
	
void SetGlobalToSkinXform(AnimInfo* anim, nifly::NiShape* theShape, const nifly::MatTransform& gtsXform);

nifly::NiShape* CreateShapeFromData(nifly::NifFile* nif, const char* shapeName,
	const std::vector<nifly::Vector3>* verts, const std::vector<nifly::Triangle>* tris,
	const std::vector<nifly::Vector2>* uv, const std::vector<nifly::Vector3>* norms);

void AddBoneToShape(AnimInfo* anim, nifly::NiShape* theShape, std::string boneName, nifly::MatTransform* boneXform=nullptr);

void SetShapeGlobalToSkinXform(AnimInfo* anim, nifly::NiShape* theShape, const nifly::MatTransform& gtsXform);

void SetShapeWeights(AnimInfo* anim, nifly::NiShape* theShape, std::string boneName, AnimWeight& theWeightSet);

int SaveSkinnedNif(AnimInfo* anim, std::string filepath);