/*
	Test of Nifly and the functions layered on it. Lives inside the DLL so we can
	explore functionality without having to go through the DLL packing/unpacking.

	Copied from Outfit Studio, all their copywrite restrictions apply
	*/

#include "pch.h"
#include <iostream>
#include <string>
#include <unordered_map>
#include <filesystem>
#include <libloaderapi.h>
#include "CppUnitTest.h"
#include "Object3d.hpp"
#include "Anim.h"
#include "NiflyFunctions.hpp"
#include "NiflyWrapper.hpp"

using namespace nifly;
using namespace Microsoft::VisualStudio::CppUnitTestFramework;

static std::string curRootName;

//std::filesystem::path testRoot(TEST_ROOT);
std::filesystem::path testRoot = std::filesystem::current_path()
	.parent_path().parent_path().parent_path().parent_path() / "PyNifly/Pynifly/tests/";

bool ApproxEqual(float first, float second) {
	return round(first * 1000) == round(second * 1000);
}
bool ApproxEqual(Vector3 first, Vector3 second) {
		return ApproxEqual(first.x, second.x)
		&& ApproxEqual(first.y, second.y)
		&& ApproxEqual(first.z, second.z);
};

int GetWeightsFor(
		NifFile* nif, NiShape* shape, Vector3 targetVert,
		std::unordered_map<std::string, float>& result)
{
	std::vector<std::string> names;
	std::vector<Vector3> verts;
	//std::vector<Vector3> rawverts;
	int target_index = -1;
	
	nif->GetShapeBoneList(shape, names);
	nif->GetVertsForShape(shape, verts);
	//nif->GetVertsForShape(shape, rawverts);

	for (int i = 0; i < names.size(); i++) {
		std::unordered_map<uint16_t, float> weights;
		nif->GetShapeBoneWeights(shape, i, weights);
		for (auto w : weights) {
			if (ApproxEqual(targetVert, verts[w.first])) {
				result[names[i]] = w.second;
			}
		}
	}
	for (int i = 0; i < verts.size(); i++) {
		if (ApproxEqual(targetVert, verts[i])) {
			target_index = i;
		}
	}
	//for (int i = 0; i < rawverts.size(); i++) {
	//	if (ApproxEqual(targetVert, rawverts[i])) {
	//		target_index = i;
	//	}
	//}
	return target_index;
}

/* Compare source and destination nif shapes to ensure they are the same*/
void CheckAccuracy(const std::filesystem::path srcPath, const char* srcShapeName,
	const std::filesystem::path dstPath, const char* dstShapeName,
	Vector3 targetVert, std::string targetBone) {

	NifFile nifSrc = NifFile(srcPath);
	NifFile nifDst = NifFile(dstPath);
	NiShape* shapeSrc = nifSrc.FindBlockByName<NiShape>(srcShapeName);
	NiShape* shapeDst = nifDst.FindBlockByName<NiShape>(dstShapeName);

	/* Check that a give vert has the same weight in both models */
	std::unordered_map<std::string, float> srcWeights;
	std::unordered_map<std::string, float> dstWeights; 
	int srcIndex = GetWeightsFor(&nifSrc, shapeSrc, targetVert, srcWeights);
	int dstIndex = GetWeightsFor(&nifDst, shapeDst, targetVert, dstWeights);
	Assert::IsTrue(srcIndex >= 0 && dstIndex >= 0, L"Couldn't find vertex");
	Assert::IsTrue(ApproxEqual(srcWeights[targetBone], dstWeights[targetBone]), 
		L"Vertex weights not the same");
};

namespace NiflyDLLTests
{
	TEST_CLASS(NiflyDLLTests)
	{
	public:
		TEST_METHOD(LoadReferenceSkeleton) {
			/* Can load a skeleton */
			AnimSkeleton::getInstance().LoadFromNif(SkeletonFile(SKYRIM), curRootName);

			AnimSkeleton skel = AnimSkeleton::getInstance();
			std::string rootName = skel.GetRootBonePtr()->boneName;
			Assert::AreEqual(std::string("NPC Root [Root]"), rootName);
			int nodeCount = int(skel.refSkeletonNif.GetNodes().size());

			NifFile nif = NifFile(SkeletonFile(FO4));
			NiNode* node = nif.FindBlockByName<NiNode>("LArm_Hand");
			NiNode* parent = nif.GetParentNode(node);
			std::string parentName = nif.GetNodeName(nif.GetBlockID(parent));
			Assert::AreEqual("LArm_ForeArm3", parentName.c_str());
		}
		TEST_METHOD(LoadAndStoreSkyrim)
		{
			/* Can load a nif and read info out of it */
			NifFile nif = NifFile(testRoot / "Skyrim/test.nif");
			std::vector<std::string> shapeNames = nif.GetShapeNames();
			for (std::string s : shapeNames) std::cout << s;
			Assert::IsFalse(find(shapeNames, "Armor") == shapeNames.end());

			NiShape* theArmor = nif.FindBlockByName<NiShape>("Armor");
			std::vector < Vector3 > verts;
			std::vector<Triangle> tris;
			const std::vector<Vector2>* uv;
			const std::vector<Vector3>* norms;

			nif.GetVertsForShape(theArmor, verts);
			Assert::AreEqual(2115, int(verts.size()));
			theArmor->GetTriangles(tris);
			Assert::AreEqual(3195, int(tris.size()));
			uv = nif.GetUvsForShape(theArmor);
			Assert::AreEqual(2115, int(uv->size()));
			norms = nif.GetNormalsForShape(theArmor);
			Assert::AreEqual(2115, int(norms->size()));

			NifFile newNif = NifFile();
			SetNifVersion(&newNif, SKYRIM);
			NiShape* newArmor = newNif.CreateShapeFromData("Armor", &verts, &tris, uv, norms);
			newNif.Save(testRoot / "Out/TestSaveUnskinned01.nif");
			Assert::IsTrue(std::filesystem::exists(testRoot / "Out/TestSaveUnskinned01.nif"));

			/* >> Can get skin info directly from the nif */

			std::vector<std::string> armorBoneNames;
			std::vector<AnimWeight> armorWeights;
			nifly::MatTransform armorXformGlobalToSkin;
			nif.GetShapeTransformGlobalToSkin(theArmor, armorXformGlobalToSkin);
			nif.GetShapeBoneList(theArmor, armorBoneNames);
			for (int i = 0; i < armorBoneNames.size(); i++) {
				AnimWeight w;
				nif.GetShapeBoneWeights(theArmor, i, w.weights);
				armorWeights.push_back(w);
			}
			Assert::AreEqual(27, int(armorBoneNames.size()));
			Assert::AreEqual(27, int(armorWeights.size()));
			Assert::AreEqual(-120, int(armorXformGlobalToSkin.translation.z));

			/* >> Can save just the armor as a skinned object */
			AnimInfo* anim;
			AnimSkeleton::getInstance().LoadFromNif(SkeletonFile(SKYRIM), curRootName);

			NifFile newNifSkind = NifFile();
			SetNifVersion(&newNifSkind, SKYRIM);
			anim = CreateSkinForNif(&newNifSkind, SKYRIM);

			newArmor = newNifSkind.CreateShapeFromData("Armor", &verts, &tris, uv, norms);
			newNifSkind.CreateSkinning(newArmor);

			/* Transform the global frame of reference to the skin's FoR.
			* This transform lifts the whole shape *up* to normal position by changing the
			* transforms on all the bones associated with the shape. With this transform
			* NPC L Foot [Lft ]:
				Rot  Y -124.31  P 0.11  R 164.37
				Tra  X -13.2327  Y 94.8649  Z -63.7509
			  Without:
				Rot  Y -124.31  P 0.11  R 164.37
				Tra  X -13.8866  Y -3.6996  Z 5.3110
			*/
			MatTransform armorGTSkin;
			bool hasGTSkin = nif.GetShapeTransformGlobalToSkin(theArmor, armorGTSkin);
			Assert::IsTrue(hasGTSkin), L"ERROR: Skyrim nifs have skin transforms";

			AnimInfo oldArmorSkin;
			oldArmorSkin.LoadFromNif(&nif, theArmor);
			MatTransform armorGTShape;
			GetGlobalToSkin(&oldArmorSkin, theArmor, &armorGTShape);
			Assert::AreEqual(-120, int(armorGTSkin.translation.z), L"ERROR: Body nifs have a -120 z transform");
			SetGlobalToSkinXform(anim, newArmor, armorGTShape);

			/* Just add bones by name. Any info about transform comes from skeleton */
			std::vector<std::string> armorBones;
			nif.GetShapeBoneList(theArmor, armorBones);
			// Reorder bones to demonstrate order doesn't matter
			std::sort(armorBones.begin(), armorBones.end());
			std::reverse(armorBones.begin(), armorBones.end());
			for (auto b : armorBones) {
				AddBoneToShape(anim, newArmor, b, nullptr);
			};

			MatTransform boneXform;
			AnimSkin* armorSkin = &anim->shapeSkinning["Armor"];
			int calfBoneIdx = anim->GetShapeBoneIndex("Armor", "NPC L Calf [LClf]");
			Assert::AreEqual(-120, int(armorSkin->xformGlobalToSkin.translation.z));
			//Assert::AreEqual(1, armorSkin->boneNames["NPC L Calf[LClf]"]);
			Assert::AreEqual(-1, int(armorSkin->boneWeights[calfBoneIdx].xformSkinToBone.translation.x));
			Assert::AreEqual(-14, int(armorSkin->boneWeights[calfBoneIdx].xformSkinToBone.translation.y));
			Assert::AreEqual(-86, int(armorSkin->boneWeights[calfBoneIdx].xformSkinToBone.translation.z));

			/* This transform is applied to the NiSkinData but doesn't put the
			   shape into proper position. It does not affect the transforms on the bones.
			*/
			if (theArmor->HasSkinInstance()) {
				MatTransform sourceXformGlobalToSkin;
				nif.GetShapeTransformGlobalToSkin(theArmor, sourceXformGlobalToSkin);
				SetShapeGlobalToSkinXform(anim, newArmor, sourceXformGlobalToSkin);
			}

			/* Sets bone weights only. Doesn't set transforms. */
			for (int i = 0; i < armorWeights.size(); i++) {
				AddBoneToShape(anim, newArmor, armorBoneNames[i], nullptr);
				SetShapeWeights(anim, newArmor, armorBoneNames[i], armorWeights[i]);
			}

			SaveSkinnedNif(anim, (testRoot / "Out/TestSkinned01.nif").string());
			Assert::IsTrue(std::filesystem::exists(testRoot / "Out/TestSkinned01.nif"));

			/* The body has its own issues */
			NiShape* theBody = nif.FindBlockByName<NiShape>("MaleBody");

			nif.GetVertsForShape(theBody, verts);
			Assert::AreEqual(2024, int(verts.size()));
			theBody->GetTriangles(tris);
			uv = nif.GetUvsForShape(theBody);
			norms = nif.GetNormalsForShape(theBody);

			std::vector<std::string> bodyBoneNames;
			std::vector<int> bodyBoneIDs;
			std::unordered_map<std::string, AnimWeight> bodyWeights;
			nifly::MatTransform bodyXformGlobalToSkin;
			nif.GetShapeTransformGlobalToSkin(theBody, bodyXformGlobalToSkin);
			nif.GetShapeBoneList(theBody, bodyBoneNames);
			nif.GetShapeBoneIDList(theBody, bodyBoneIDs);
			for (int i = 0; i < bodyBoneNames.size(); i++) {
				AnimWeight w;
				nif.GetShapeBoneWeights(theBody, i, w.weights);
				bodyWeights[bodyBoneNames[i]] = w;
			}

			newNifSkind = NifFile();
			SetNifVersion(&newNifSkind, SKYRIM);
			anim = CreateSkinForNif(&newNifSkind, SKYRIM);

			NiShape* newBody = newNifSkind.CreateShapeFromData("Body", &verts, &tris, uv, norms);
			newNifSkind.CreateSkinning(newBody);

			for (auto w : bodyWeights) {
				AddBoneToShape(anim, newBody, w.first, nullptr);
				SetShapeWeights(anim, newBody, w.first, w.second);
			}

			SaveSkinnedNif(anim, (testRoot / "Out/TestSkinned02.nif").string());
			Assert::IsTrue(std::filesystem::exists(testRoot / "Out/TestSkinned02.nif"));

			Vector3 targetVert(12.761050f, -0.580783f, 21.823328f); // vert 358
			std::string targetBone = "NPC R Calf [RClf]"; // should be 1.0
			CheckAccuracy(
				testRoot / "Skyrim/test.nif", "MaleBody",
				testRoot / "Out/TestSkinned02.nif", "Body",
				targetVert, targetBone);
		};
		TEST_METHOD(LoadAndStoreFO4)
		{
			/* Can load a nif and read info out of it */
			LogInit();
			NifFile nif = NifFile(testRoot / "FO4/BTMaleBody.nif");
			std::vector<std::string> shapeNames = nif.GetShapeNames();
			for (std::string s : shapeNames) std::cout << s;
			Assert::IsFalse(find(shapeNames, "BaseMaleBody:0") == shapeNames.end());

			NiShape* theBody = nif.FindBlockByName<NiShape>("BaseMaleBody:0");
			std::vector < Vector3 > verts;
			//const std::vector < Vector3 >* rawVerts;
			std::vector<Triangle> tris;
			const std::vector<Vector2>* uv;
			const std::vector<Vector3>* norms;

			nif.GetVertsForShape(theBody, verts);
			//rawVerts = nif.GetRawVertsForShape(theBody);
			//Assert::AreEqual(8717, int(rawVerts->size()));
			theBody->GetTriangles(tris);
			Assert::AreEqual(16202, int(tris.size()));
			uv = nif.GetUvsForShape(theBody);
			Assert::AreEqual(8717, int(uv->size()));
			norms = nif.GetNormalsForShape(theBody);
			Assert::AreEqual(8717, int(norms->size()));

			AnimInfo oldBodySkin;
			oldBodySkin.LoadFromNif(&nif, theBody);

			AnimInfo* anim;
			AnimSkeleton::getInstance().LoadFromNif(SkeletonFile(FO4), curRootName);

			NifFile newNif = NifFile();
			SetNifVersion(&newNif, FO4);
			anim = CreateSkinForNif(&newNif, FO4);

			NiShape* newBody = newNif.CreateShapeFromData("Body", &verts, &tris, uv, norms);
			newNif.CreateSkinning(newBody);

			/* Transform the global frame of reference to the skin's FoR.
			* This transform lifts the whole shape *up* to normal position by changing the
			* transforms on all the bones associated with the shape. With this transform
			* NPC L Foot [Lft ]:
				Rot  Y -124.31  P 0.11  R 164.37
				Tra  X -13.2327  Y 94.8649  Z -63.7509
			  Without:
				Rot  Y -124.31  P 0.11  R 164.37
				Tra  X -13.8866  Y -3.6996  Z 5.3110
			*/
			MatTransform bodyGTS;
			//armorGTS.translation = { 0.000256f, 1.547526f, -120.343582f };
			bool hasGTSkin = nif.GetShapeTransformGlobalToSkin(theBody, bodyGTS);
			Assert::IsFalse(hasGTSkin), L"ERROR: FO4 nifs do not have skin transforms";
			if (!hasGTSkin)
				GetGlobalToSkin(&oldBodySkin, theBody, &bodyGTS);
			Assert::AreEqual(-120, int(bodyGTS.translation.z), L"ERROR: Body nifs have a -120 z transform");
			SetGlobalToSkinXform(anim, newBody, bodyGTS);

			/* 
			This transform is applied to the NiSkinData block. It gives the
			overall transform for the model when there's a NiSkinData block (Skyrim). 
			It has to be set correctly so that the model can be put in skinned position 
			when read into blender, because if the block exists only this transform is used.
			*/
			if (theBody->HasSkinInstance()) {
				MatTransform sourceXformGlobalToSkin;
				if (nif.GetShapeTransformGlobalToSkin(theBody, sourceXformGlobalToSkin))
					SetShapeGlobalToSkinXform(anim, theBody, sourceXformGlobalToSkin);
			}

			std::vector<std::string> bodyBoneNames;
			nif.GetShapeBoneList(theBody, bodyBoneNames);
			std::unordered_map<std::string, AnimWeight> bodyWeights;
			for (int i = 0; i < bodyBoneNames.size(); i++) {
				AnimWeight w;
				nif.GetShapeBoneWeights(theBody, i, w.weights);
				bodyWeights[bodyBoneNames[i]] = w;
			}
			/* Sets bone weights only. Doesn't set transforms. */
			for (auto w : bodyWeights) {
				AddBoneToShape(anim, newBody, w.first, nullptr);
				SetShapeWeights(anim, newBody, w.first, w.second);
			}

			SaveSkinnedNif(anim, (testRoot / "Out/TestSkinnedFO01.nif").string());

			Assert::AreEqual(0, LogGetLen(), L"Generated messages");

			Vector3 targetVert(2.587891f, 10.031250f, -39.593750f);
			std::string targetBone = "Spine1_skin";
			CheckAccuracy(
				testRoot / "FO4/BTMaleBody.nif", "BaseMaleBody:0",
				testRoot / "Out/TestSkinnedFO01.nif", "Body",
				targetVert, "Spine1_skin");
		};
		/* Here's about skinning */
		TEST_METHOD(SkinTransformsFO4)
		{
			/* FO4 */
			NifFile nif = NifFile(testRoot / "FO4/BTMaleBody.nif");
			NiShape* theBody = nif.FindBlockByName<NiShape>("BaseMaleBody:0");
			AnimInfo bodySkin;
			bodySkin.LoadFromNif(&nif, theBody);

			/* Whether there's a skin instance just says the shape is skinned */
			Assert::IsTrue(theBody->HasSkinInstance(), L"ERROR: This is a skinned shape");

			/* Skyrim has transforms on the NiSkinInstance. FO4 nifs don't */
			MatTransform bodyg2skinInst;
			Assert::IsFalse(nif.GetShapeTransformGlobalToSkin(theBody, bodyg2skinInst),
				L"FO4 nifs do not have skin instance");

			/* But FO4 nifs do have a GTS transform, which is calculated from the bones.
			   The calculation happened when we loaded the nif into the bodySkin. */
			MatTransform bodyg2skin;
			GetGlobalToSkin(&bodySkin, theBody, &bodyg2skin);
			Assert::AreEqual(-120, int(bodyg2skin.translation.z), L"ERROR: should have -120 translation");

			/* The -120z transform means all the body verts are below the 0 point */
			std::vector < Vector3 > verts;
			nif.GetVertsForShape(theBody, verts);
			float minVert = verts[0].z;
			float maxVert = verts[0].z;
			for (auto v : verts) {
				minVert = std::min(v.z, minVert);
				maxVert = std::max(v.z, maxVert);
			}
			Assert::IsTrue(minVert > -130 && maxVert < 0, L"ERROR: Body verts below origin");
		};
		TEST_METHOD(SkinTransformsSkyrim)
		{
			/* Skyrim */
			NifFile nifHead = NifFile(testRoot / "Skyrim/MaleHead.nif");
			std::vector<std::string> shapeNames = nifHead.GetShapeNames();
			Assert::IsFalse(find(shapeNames, "MaleHeadIMF") == shapeNames.end());

			NiShape* theHead = nifHead.FindBlockByName<NiShape>("MaleHeadIMF");
			AnimInfo headSkin;
			headSkin.LoadFromNif(&nifHead, theHead);

			/* This one is also skinned */
			Assert::IsTrue(theHead->HasSkinInstance(), L"ERROR: This is a skinned shape");

			/* And there's a NiSkinInstance */
			MatTransform headg2skinInst;
			Assert::IsTrue(nifHead.GetShapeTransformGlobalToSkin(theHead, headg2skinInst),
				L"Skyrim nifs have skin instance");

			/* You can still ask for the global-to-skin transform but it just gives the same thing */
			MatTransform headg2skin;
			GetGlobalToSkin(&headSkin, theHead, &headg2skin);
			Assert::AreEqual(-120, int(headg2skin.translation.z), L"ERROR: should have -120 translation");
			Assert::AreEqual(headg2skinInst.translation.z, headg2skin.translation.z,
				L"ERROR: should have -120 translation");

			/* The -120z transform means all the head verts are around the 0 point */
			std::vector < Vector3 > verts;
			nifHead.GetVertsForShape(theHead, verts);
			float minVert = verts[0].z;
			float maxVert = verts[0].z;
			for (auto v : verts) {
				minVert = std::min(v.z, minVert);
				maxVert = std::max(v.z, maxVert);
			}
			Assert::IsTrue(minVert > -15 && maxVert < 15, L"ERROR: Head verts centered around origin");
		};
		TEST_METHOD(SkinTransformsOnBones)
		{
			/* This file has transforms only on bones */
			NifFile nif = NifFile(testRoot / "Skyrim/ArmorOffset.nif");

			NiShape* shape = nif.FindBlockByName<NiShape>("Armor");
			AnimInfo skin;
			skin.LoadFromNif(&nif, shape);

			/* And there's a NiSkinInstance */
			MatTransform gtshape;
			bool haveGTS = nif.GetShapeTransformGlobalToSkin(shape, gtshape);
			MatTransform gtsCalc;
			nif.CalcShapeTransformGlobalToSkin(shape, gtsCalc);
			MatTransform gts;
			GetGlobalToSkin(&skin, shape, &gts); // Similar to CalcShapeTransform

			/* All the z translations are 0 because for skyrim nifs we just look at
			   NiSkinData and it's 0 for this nif */
			Assert::IsTrue(haveGTS, L"Skyrim nifs have skin instance");
			Assert::AreEqual(0, int(gtshape.translation.z), L"Global-to-shape is -120");

			/* You can still ask for the global-to-skin transform but it just gives the same thing */
			Assert::AreEqual(0, int(gts.translation.z), L"Global-to-skin is -120 translation");
			Assert::AreEqual(gtshape.translation.z, gts.translation.z,
				L"ERROR: should have -120 translation");

			/* The -120z transform means all the head verts are around the 0 point */
			std::vector < Vector3 > verts;
			nif.GetVertsForShape(shape, verts);
			float minVert = verts[0].z;
			float maxVert = verts[0].z;
			for (auto v : verts) {
				minVert = std::min(v.z, minVert);
				maxVert = std::max(v.z, maxVert);
			}
			Assert::IsTrue(minVert > -130 && maxVert < 0, L"ERROR: Armor verts all below origin");
		};
		TEST_METHOD(UnkownBones) {
			/* We can deal with bones that aren't part of the standard skeleton */

			/* Shapes have bones that aren't known in the skeleton */
			NifFile nif = NifFile(testRoot / "FO4/VulpineInariTailPhysics.nif");
			NiShape* shape = nif.FindBlockByName<NiShape>("Inari_ZA85_fluffy");
			NiNode* bone1 = nif.FindBlockByName<NiNode>("Bone_Cloth_H_002");
			Assert::IsNotNull(shape, L"ERROR: Can read shape from nif");
			Assert::IsNotNull(bone1, L"ERROR: Can read non-standard bone from nif");

			/* We can get the transform (location) of that bone */
			MatTransform boneXform;
			nif.GetNodeTransformToGlobal("Bone_Cloth_H_002", boneXform);
			Assert::AreNotEqual(0.0f, boneXform.translation.z, L"ERROR: Can read bone's transform");
			
			/* We read all the info we need about the shape */
			std::vector < Vector3 > verts;
			std::vector<Triangle> tris;
			const std::vector<Vector2>* uv;
			const std::vector<Vector3>* norms;

			nif.GetVertsForShape(shape, verts);
			shape->GetTriangles(tris);
			uv = nif.GetUvsForShape(shape);
			norms = nif.GetNormalsForShape(shape);

			AnimInfo oldSkin;
			oldSkin.LoadFromNif(&nif, shape);

			MatTransform shapeGTS;
			GetGlobalToSkin(&oldSkin, shape, &shapeGTS);

			std::vector<std::string> boneNames;
			nif.GetShapeBoneList(shape, boneNames);

			std::unordered_map<std::string, MatTransform> boneXforms;
			for (auto b : boneNames) {
				MatTransform xform;
				nif.GetNodeTransformToGlobal(b, xform);
				boneXforms[b] = xform;
			};
			 
			std::unordered_map<std::string, AnimWeight> shapeWeights;
			for (int i = 0; i < boneNames.size(); i++) {
				AnimWeight w;
				nif.GetShapeBoneWeights(shape, i, w.weights);
				shapeWeights[boneNames[i]] = w;
			}

			/* We can export the shape with the bones in their locations as read */
			AnimInfo* newSkin;
			AnimSkeleton::getInstance().LoadFromNif(SkeletonFile(FO4), curRootName);

			NifFile newNif = NifFile();
			SetNifVersion(&newNif, FO4);
			newSkin = CreateSkinForNif(&newNif, FO4);

			NiShape* newShape = newNif.CreateShapeFromData("Tail", &verts, &tris, uv, norms);
			newNif.CreateSkinning(newShape);

			SetGlobalToSkinXform(newSkin, newShape, shapeGTS);

			/* Sets bone weights only. Doesn't set transforms. */
			for (auto w : shapeWeights) {
				AddBoneToShape(newSkin, newShape, w.first, &boneXforms[w.first]);
				SetShapeWeights(newSkin, newShape, w.first, w.second);
			}

			SaveSkinnedNif(newSkin, (testRoot / "Out/TestSkinnedFO02.nif").string());

			/* Resulting file has the special bones */
			NifFile newnif = NifFile(testRoot / "Out/TestSkinnedFO02.nif");
			NiNode* theBone = nif.FindBlockByName<NiNode>("Bone_Cloth_H_002");
			Assert::IsNotNull(theBone, L"ERROR: Cloth bone expected in file");
		}
		TEST_METHOD(SaveMulti) {
			/* We can save shapes with different transforms in the same file */
			std::filesystem::path testfile = testRoot / "Skyrim/Test.nif";
			NifFile nif = NifFile(testfile);
			
			/* Read the armor */
			NiShape* theArmor = nif.FindBlockByName<NiShape>("Armor");
			AnimInfo armorSkin;
			armorSkin.LoadFromNif(&nif, theArmor);
			MatTransform armorSkinInst;
			nif.GetShapeTransformGlobalToSkin(theArmor, armorSkinInst);
			MatTransform armorXform;
			nif.GetNodeTransform("Armor", armorXform);

			std::vector < Vector3 > aVerts;
			std::vector<Triangle> aTris;
			const std::vector<Vector2>* aUV;
			const std::vector<Vector3>* aNorms;

			nif.GetVertsForShape(theArmor, aVerts);
			theArmor->GetTriangles(aTris);
			aUV= nif.GetUvsForShape(theArmor);
			aNorms = nif.GetNormalsForShape(theArmor);

			std::vector<std::string> armorBones;
			nif.GetShapeBoneList(theArmor, armorBones);
			std::unordered_map<std::string, AnimWeight> armorWeights;
			for (int i = 0; i < armorBones.size(); i++) {
				AnimWeight w;
				nif.GetShapeBoneWeights(theArmor, i, w.weights);
				armorWeights[armorBones[i]] = w;
			};

			/* Read the body */
			NiShape* theBody = nif.FindBlockByName<NiShape>("MaleBody");
			AnimInfo bodySkin;
			bodySkin.LoadFromNif(&nif, theBody);
			MatTransform bodySkinInst;
			nif.GetShapeTransformGlobalToSkin(theBody, bodySkinInst);

			std::vector < Vector3 > bVerts;
			std::vector<Triangle> bTris;
			const std::vector<Vector2>* bUV;
			const std::vector<Vector3>* bNorms;

			nif.GetVertsForShape(theBody, bVerts);
			theBody->GetTriangles(bTris);
			bUV = nif.GetUvsForShape(theBody);
			bNorms = nif.GetNormalsForShape(theBody);

			std::vector<std::string> bodyBones;
			nif.GetShapeBoneList(theBody, bodyBones);
			std::unordered_map<std::string, AnimWeight> bodyWeights;
			for (int i = 0; i < bodyBones.size(); i++) {
				AnimWeight w;
				nif.GetShapeBoneWeights(theBody, i, w.weights);
				bodyWeights[bodyBones[i]] = w;
			};

			/* Save the armor */
			NifFile newNif = NifFile();
			SetNifVersion(&newNif, SKYRIM);
			AnimInfo* newSkin = CreateSkinForNif(&newNif, SKYRIM);
			NiShape* newArmor = newNif.CreateShapeFromData("Armor", &aVerts, &aTris, aUV, aNorms);
			newNif.CreateSkinning(newArmor);
			newNif.SetShapeTransformGlobalToSkin(newArmor, armorXform);
			SetGlobalToSkinXform(newSkin, newArmor, armorSkinInst);
			for (auto w : armorWeights) {
				AddBoneToShape(newSkin, newArmor, w.first);
				SetShapeWeights(newSkin, newArmor, w.first, w.second);
			}

			/* Save the body */
			NiShape* newBody = newNif.CreateShapeFromData("Body", &bVerts, &bTris, bUV, bNorms);
			newNif.CreateSkinning(newBody);
			SetGlobalToSkinXform(newSkin, newBody, bodySkinInst);
			for (auto w : bodyWeights) {
				AddBoneToShape(newSkin, newBody, w.first);
				SetShapeWeights(newSkin, newBody, w.first, w.second);
			}

			SaveSkinnedNif(newSkin, (testRoot / "Out/TestMulti01.nif").string());

			NifFile testNif = NifFile((testRoot / "Out/TestMulti01.nif").string());
			NiShape* testBody = testNif.FindBlockByName<NiShape>("Body");
			MatTransform sstb;
			testNif.GetShapeTransformSkinToBone(testBody, "NPC Spine1 [Spn1]", sstb);
			// Is this correct? Nif looks okay
			Assert::AreEqual(-81, int(sstb.translation.z), L"ERROR: Translation should move shape up");
		}
		TEST_METHOD(getXformFromSkel) {
			float buf[13];
			NifFile nif = NifFile(testRoot / "Skyrim/MaleHead.nif");
			AnimInfo* anim = static_cast<AnimInfo*>(createSkinForNif(&nif, "SKYRIM"));

			for (int i = 0; i < 13; i++) { buf[i] = 0.0f; };
			getNodeXformToGlobal(anim, "NPC Spine2 [Spn2]", buf);
			Assert::AreNotEqual(0.0f, buf[0], L"Error: Should not have null transform");

			for (int i = 0; i < 13; i++) { buf[i] = 0.0f; };
			getNodeXformToGlobal(anim, "NPC L Forearm [LLar]", buf);
			Assert::AreNotEqual(0.0f, buf[0], L"Error: Should not have null transform");

			NifFile nif2 = NifFile(testRoot / "FO4/BaseMaleHead.nif");
			AnimInfo* anim2 = static_cast<AnimInfo*>(createSkinForNif(&nif2, "FO4"));

			for (int i = 0; i < 13; i++) { buf[i] = 0.0f; };
			getNodeXformToGlobal(anim2, "Neck", buf);
			Assert::AreNotEqual(0.0f, buf[0], L"Error: Should not have null transform");

			for (int i = 0; i < 13; i++) { buf[i] = 0.0f; };
			getNodeXformToGlobal(anim2, "SPINE1", buf);
			Assert::AreNotEqual(0.0f, buf[0], L"Error: Should not have null transform");

			//print("FO4 LArm_UpperTwist1: ", nif.get_node_xform_to_global('LArm_UpperTwist1'))
			//	print("FO4 LArm_UpperTwist1_skin: ", nif.get_node_xform_to_global('LArm_UpperTwist1_skin'))
			//	print("SKYRIM NPC L Forearm [LLar]: ", nif.get_node_xform_to_global('NPC L Forearm [LLar]'))
		}
		TEST_METHOD(checkGTSOffset) {
			std::filesystem::path testfile = testRoot / "FO4/VanillaMaleBody.nif";
			std::filesystem::path testfile2 = testRoot / "FO4/BTMaleBody.nif";

			/* THIS WORKS -- ROTATIONS ARE THE SAME */
			NifFile nif = NifFile(testfile);

			NiShape* vbody = nif.FindBlockByName<NiShape>("BaseMaleBody:0");
			AnimInfo vskin;
			vskin.LoadFromNif(&nif, vbody);
			MatTransform vSkinInst;
			vSkinInst = vskin.shapeSkinning["BaseMaleBody:0"].xformGlobalToSkin;

			NifFile nif2 = NifFile(testfile2);

			NiShape* btbody = nif2.FindBlockByName<NiShape>("BaseMaleBody:0");
			AnimInfo btskin;
			btskin.LoadFromNif(&nif2, btbody);
			MatTransform btSkinInst;
			btSkinInst = btskin.shapeSkinning["BaseMaleBody:0"].xformGlobalToSkin;

			/* TESTING THROUGH THE WRAPPER LAYER -- RESULTS SHOULD BE THE SAME */
			float vbuf[13];
			NifFile nifw = NifFile(testfile);
			NiShape* vbodyw = nifw.FindBlockByName<NiShape>("BaseMaleBody:0");

			for (int i = 0; i < 13; i++) { vbuf[i] = 0.0f; };
			getGlobalToSkin(&nifw, vbodyw, vbuf);

			float btbuf[13];
			NifFile btnifw = NifFile(testfile2);
			NiShape* btbodyw = btnifw.FindBlockByName<NiShape>("BaseMaleBody:0");

			for (int i = 0; i < 13; i++) { btbuf[i] = 0.0f; };
			getGlobalToSkin(&btnifw, btbodyw, btbuf);

			/* ************************************** */
			/* Test fails - fix the GTS conversion    */
			//Assert::AreEqual(round(vSkinInst.translation.x * 1000), round(btSkinInst.translation.x * 1000));
			//Assert::AreEqual(round(vSkinInst.translation.y * 1000), round(btSkinInst.translation.y * 1000));
			//Assert::AreEqual(round(vSkinInst.translation.z * 1000), round(btSkinInst.translation.z * 1000));
			//for (int i = 0; i < 3; i++)
			//	for (int j = 0; j < 3; j++)
			//		Assert::AreEqual(
			//			round(btSkinInst.rotation[i][j] * 1000),
			//			round(vSkinInst.rotation[i][j] * 1000));

			//for (int i = 0; i < 13; i++)
			//	Assert::AreEqual(round(vbuf[i]*1000), round(btbuf[i])*1000);

		}
	};
}
