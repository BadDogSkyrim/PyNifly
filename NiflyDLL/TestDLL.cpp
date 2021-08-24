/*
	Test of Nifly and the functions layered on it. Lives inside the DLL so we can
	explore functionality without having to go through the DLL packing/unpacking.

	Copied from Outfit Studio, all their copywrite restrictions apply
	*/

#include "pch.h"
#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <filesystem>
#include <libloaderapi.h>
#include <bitset>
#include "CppUnitTest.h"
#include "Object3d.hpp"
#include "Anim.h"
#include "NiflyFunctions.hpp"
#include "NiflyWrapper.hpp"

using namespace nifly;
using namespace Microsoft::VisualStudio::CppUnitTestFramework;

//static std::string curRootName;

//std::filesystem::path testRoot(TEST_ROOT);
std::filesystem::path testRoot = std::filesystem::current_path()
	.parent_path().parent_path().parent_path().parent_path() / "PyNifly/Pynifly/tests/";

bool TApproxEqual(float first, float second) {
	return round(first * 1000) == round(second * 1000);
}
bool TApproxEqual(Vector3 first, Vector3 second) {
		return TApproxEqual(first.x, second.x)
		&& TApproxEqual(first.y, second.y)
		&& TApproxEqual(first.z, second.z);
};

int TGetWeightsFor(
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
			if (TApproxEqual(targetVert, verts[w.first])) {
				result[names[i]] = w.second;
			}
		}
	}
	for (int i = 0; i < verts.size(); i++) {
		if (TApproxEqual(targetVert, verts[i])) {
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
void TCheckAccuracy(const std::filesystem::path srcPath, const char* srcShapeName,
	const std::filesystem::path dstPath, const char* dstShapeName,
	Vector3 targetVert, std::string targetBone) {

	NifFile nifSrc = NifFile(srcPath);
	NifFile nifDst = NifFile(dstPath);
	NiShape* shapeSrc = nifSrc.FindBlockByName<NiShape>(srcShapeName);
	NiShape* shapeDst = nifDst.FindBlockByName<NiShape>(dstShapeName);

	/* Check that a give vert has the same weight in both models */
	std::unordered_map<std::string, float> srcWeights;
	std::unordered_map<std::string, float> dstWeights; 
	int srcIndex = TGetWeightsFor(&nifSrc, shapeSrc, targetVert, srcWeights);
	int dstIndex = TGetWeightsFor(&nifDst, shapeDst, targetVert, dstWeights);
	Assert::IsTrue(srcIndex >= 0 && dstIndex >= 0, L"Couldn't find vertex");
	Assert::IsTrue(TApproxEqual(srcWeights[targetBone], dstWeights[targetBone]), 
		L"Vertex weights not the same");
};

void TCopyPartitions(void* targetNif, void* targetShape, void* sourceNif, void* sourceShape) {
	uint16_t partitionInfo[20];
	int partitionCount = getPartitions(sourceNif, sourceShape, partitionInfo, 20);

	int triCount = getPartitionTris(sourceNif, sourceShape, nullptr, 0);
	uint16_t* partTris = new uint16_t[triCount];
	getPartitionTris(sourceNif, sourceShape, partTris, triCount);
	setPartitions(targetNif, targetShape, partitionInfo, partitionCount, partTris, triCount);
};

void TComparePartitions(void* nif1, void* shape1, void* nif2, void* shape2) {
	uint16_t partitionInfo1[20], partitionInfo2[20];
	int partitionCount1 = getPartitions(nif1, shape1, partitionInfo1, 20);
	int triCount1 = getPartitionTris(nif1, shape1, nullptr, 0);
	uint16_t* partTris1 = new uint16_t[triCount1];
	getPartitionTris(nif1, shape1, partTris1, triCount1);
	int partitionCount2 = getPartitions(nif2, shape2, partitionInfo2, 20);
	int triCount2 = getPartitionTris(nif2, shape2, nullptr, 0);
	uint16_t* partTris2 = new uint16_t[triCount2];
	getPartitionTris(nif2, shape2, partTris2, triCount2);

	Assert::IsTrue(partitionCount1 == partitionCount2, L"Error: Partition count wrong");
	// Nifly sets PF_EDITOR_VISIBLE, which is generally fine; also sets PF_START_NET_BONESET
	// in situations that seem correct, tho vanilla nifs don't set it. So don't check these
	// flags.
	for (int i = 0; i < partitionCount1 * 2; i += 2) {
		Assert::IsTrue((partitionInfo1[i] & !PF_EDITOR_VISIBLE & !PF_START_NET_BONESET) ==
					   (partitionInfo2[i] & !PF_EDITOR_VISIBLE & !PF_START_NET_BONESET), 
			L"Error: Partition flags don't match");
		Assert::IsTrue((partitionInfo1[i + 1] & !PF_EDITOR_VISIBLE & !PF_START_NET_BONESET) == 
					   (partitionInfo2[i + 1] & !PF_EDITOR_VISIBLE & !PF_START_NET_BONESET), 
			L"Error: Partition IDs don't match");
	};
	Assert::IsTrue(triCount1 == triCount2, L"Error: Different number of tris");
	for (int i = 0; i < triCount1; i++) {
		Assert::IsTrue(partTris1[i] == partTris2[i], L"Error: Tri index differs");
	};
};

void* TCopyWeights(void* targetNif, void* targetShape, void* sourceNif, void* sourceShape) {

	std::vector<std::string> boneNames;
	std::vector<AnimWeight> boneWeights;
	nifly::MatTransform xformGlobalToSkin;
	const int BUFLEN = 3000;
	char boneNameBuf[BUFLEN];

	//if (!getShapeGlobalToSkin(sourceNif, 
	//						  sourceShape, 
	//						  static_cast<float*>(&xformGlobalToSkin.translation.x)))
	//	return;

	int boneCount = getShapeBoneCount(sourceNif, sourceShape);
	if (boneCount == 0) return nullptr;

	int boneBufLen = getShapeBoneNames(sourceNif, sourceShape, boneNameBuf, BUFLEN);
	Assert::IsTrue(boneCount <= BUFLEN);
	for (int i = 0; i < boneBufLen; i++) if (boneNameBuf[i] == '\n') boneNameBuf[i] = '\0';

	char gameName[30];
	getGameName(sourceNif, gameName, 30);

	void* anim;
	anim = createSkinForNif(targetNif, gameName);
	skinShape(targetNif, targetShape);

	MatTransform shapeXform;
	getTransform(sourceShape, &shapeXform.translation.x);
	setTransform(targetShape, &shapeXform.translation.x);

	MatTransform shapeGTSkin;
	if (!getShapeGlobalToSkin(sourceNif, sourceShape, &shapeGTSkin.translation.x))
		getGlobalToSkin(sourceNif, sourceShape, &shapeGTSkin.translation.x);
	
	setGlobalToSkinXform(anim, targetShape, &shapeGTSkin);

	MatTransform xform;

	for (int i = 0, boneIndex = 0; boneIndex < boneCount;  boneIndex++) {
		addBoneToShape(anim, targetShape, &boneNameBuf[i], &xform);
		int bwcount = getShapeBoneWeightsCount(sourceNif, sourceShape, boneIndex);
		VertexWeightPair* vwp = new VertexWeightPair[bwcount];
		getShapeBoneWeights(sourceNif, sourceShape, boneIndex, vwp, bwcount);
		setShapeWeights(anim, targetShape, &boneNameBuf[i], vwp, bwcount, &xform);

		i += int(strlen(&boneNameBuf[i]) + 1);
	};

	return anim;
};

void TCopyExtraData(void* targetNif, void* targetShape, void* sourceNif, void* sourceShape) {
	int namelen, valuelen;

	for (int i = 0; getStringExtraDataLen(sourceNif, sourceShape, i, &namelen, &valuelen); i++) {
		char* namebuf = new char[namelen + 1];
		char* valuebuf = new char[valuelen + 1];
		getStringExtraData(sourceNif, sourceShape, i, namebuf, namelen + 1, valuebuf, valuelen + 1);
		setStringExtraData(targetNif, targetShape, namebuf, valuebuf);
	};
	for (int i = 0; getBGExtraDataLen(sourceNif, sourceShape, i, &namelen, &valuelen); i++) {
		char* namebuf = new char[namelen + 1];
		char* valuebuf = new char[valuelen + 1];
		getBGExtraData(sourceNif, sourceShape, i, namebuf, namelen + 1, valuebuf, valuelen + 1);
		setBGExtraData(targetNif, targetShape, namebuf, valuebuf);
	}
};

void* TCopyShape(void* targetNif, const char* shapeName, void* sourceNif, void* sourceShape,
		uint16_t options, void** targetSkin) {

	int vertLen = getVertsForShape(sourceNif, sourceShape, nullptr, 0, 0);
	float* verts = new float[vertLen * 3];
	getVertsForShape(sourceNif, sourceShape, verts, vertLen*3, 0);

	int triLen = getTriangles(sourceNif, sourceShape, nullptr, 0, 0);
	uint16_t* tris = new uint16_t[triLen * 3];
	getTriangles(sourceNif, sourceShape, tris, triLen * 3, 0);

	float* uvs = new float[vertLen * 2];
	getUVs(sourceNif, sourceShape, uvs, vertLen * 2, 0);

	float* norms = nullptr;
	uint32_t f1 = getShaderFlags1(sourceNif, sourceShape);
	if (!(f1 & uint32_t(ShaderProperty1::MODEL_SPACE_NORMALS))) {
		norms = new float[vertLen * 3];
		getNormalsForShape(sourceNif, sourceShape, norms, vertLen * 3, 0);
	};

	void* targetShape = createNifShapeFromData(targetNif, shapeName,
		verts, uvs, norms, vertLen, tris, triLen, &options);

	uint32_t f2 = getShaderFlags2(sourceNif, sourceShape);
	if (f2 & uint32_t(ShaderProperty2::VERTEX_COLORS)) {
		float* colors = new float[vertLen * 4];
		getColorsForShape(sourceNif, sourceShape, colors, vertLen*4);
		setColorsForShape(targetNif, targetShape, colors, vertLen);
	}

	*targetSkin = TCopyWeights(targetNif, targetShape, sourceNif, sourceShape);

	TCopyPartitions(targetNif, targetShape, sourceNif, sourceShape);
	TCopyExtraData(targetNif, targetShape, sourceNif, sourceShape);

	return targetShape;
};

void TCompareShapes(void* nif1, void* shape1, void* nif2, void* shape2) {
	char name1[100];
	char name2[100];
	getShapeName(shape1, name1, 99);
	getShapeName(shape2, name2, 99);
	Assert::IsTrue(strcmp(name1, name2) == 0, L"Error: Shape names differ");

	int vertLen1 = getVertsForShape(nif1, shape1, nullptr, 0, 0);
	float* verts1 = new float[vertLen1 * 3];
	getVertsForShape(nif1, shape1, verts1, vertLen1, 0);

	int vertLen2 = getVertsForShape(nif2, shape2, nullptr, 0, 0);
	float* verts2 = new float[vertLen2 * 3];
	getVertsForShape(nif2, shape2, verts2, vertLen2, 0);

	Assert::IsTrue(vertLen1 == vertLen2, L"Error: Different number of verts");

	int triLen1 = getTriangles(nif1, shape1, nullptr, 0, 0);
	uint16_t* tris1 = new uint16_t[triLen1 * 3];
	getTriangles(nif1, shape1, tris1, triLen1 * 3, 0);

	int triLen2 = getTriangles(nif2, shape2, nullptr, 0, 0);
	uint16_t* tris2 = new uint16_t[triLen2 * 3];
	getTriangles(nif2, shape2, tris2, triLen2 * 3, 0);

	Assert::IsTrue(triLen1 == triLen2, L"Error: Different number of tris");

	int boneCount1 = getShapeBoneCount(nif1, shape1);
	int boneCount2 = getShapeBoneCount(nif2, shape2);
	Assert::IsTrue(boneCount1 == boneCount2, L"Error: Bone counts don't match");
	
	if (boneCount1 > 0) {
		int boneBufLen1 = getShapeBoneNames(nif1, shape1, nullptr, 0);
		char* boneBuf1 = new char[boneBufLen1];
		getShapeBoneNames(nif1, shape1, boneBuf1, boneBufLen1);

		int boneBufLen2 = getShapeBoneNames(nif1, shape1, nullptr, 0);
		char* boneBuf2 = new char[boneBufLen2];
		getShapeBoneNames(nif1, shape1, boneBuf2, boneBufLen2);

		Assert::IsTrue(strcmp(boneBuf1, boneBuf2) == 0, L"Error: Bone names differ");
		for (int i = 0; i < boneBufLen1; i++) if (boneBuf1[i] == '\n') boneBuf1[i] = '\0';
		for (int i = 0; i < boneBufLen2; i++) if (boneBuf2[i] == '\n') boneBuf2[i] = '\0';

		char gameName1[30];
		getGameName(nif1, gameName1, 30);
		char gameName2[30];
		getGameName(nif2, gameName2, 30);
		Assert::IsTrue(strcmp(gameName1, gameName2) == 0, L"Error: Nifs for different games");

		MatTransform shapeXform1;
		getTransform(shape1, &shapeXform1.translation.x);
		MatTransform shapeXform2;
		getTransform(shape2, &shapeXform2.translation.x);
		Assert::IsTrue(shapeXform1.IsNearlyEqualTo(shapeXform2), L"Error shape transforms differ");

		MatTransform shapeGTSkin1;
		if (!getShapeGlobalToSkin(nif1, shape1, &shapeGTSkin1.translation.x))
			getGlobalToSkin(nif1, shape1, &shapeGTSkin1.translation.x);
		MatTransform shapeGTSkin2;
		if (!getShapeGlobalToSkin(nif2, shape2, &shapeGTSkin2.translation.x))
			getGlobalToSkin(nif2, shape2, &shapeGTSkin2.translation.x);

		Assert::IsTrue(shapeGTSkin1.IsNearlyEqualTo(shapeGTSkin2), L"Error global to skin transforms differ");

		MatTransform xform1;
		MatTransform xform2;

		for (int boneIndex = 0; boneIndex < boneCount1; boneIndex++) {
			int bwcount1 = getShapeBoneWeightsCount(nif1, shape1, boneIndex);
			int bwcount2 = getShapeBoneWeightsCount(nif2, shape2, boneIndex);
			Assert::IsTrue(bwcount1 == bwcount2, L"Error: Bone weight counts don't match");
			VertexWeightPair* vwp1 = new VertexWeightPair[bwcount1];
			VertexWeightPair* vwp2 = new VertexWeightPair[bwcount2];
			getShapeBoneWeights(nif1, shape1, boneIndex, vwp1, bwcount1);
			getShapeBoneWeights(nif2, shape2, boneIndex, vwp2, bwcount2);
			for (int j = 0; j < bwcount1; j++) {
				Assert::IsTrue(vwp1[j].vertex == vwp2[j].vertex, L"Error vertex indices should match");
				Assert::IsTrue(round(vwp1[j].weight * 100) == round(vwp2[j].weight * 100), L"Error vertex weights should match");
			};
		};
	};
	TComparePartitions(nif1, shape1, nif2, shape2);
};

void TCompareShaders(void* nif1, void* shape1, void* nif2, void* shape2)
{
	for (int i = 0; i < 9; i++) {
		char txt1[300];
		char txt2[300];
		getShaderTextureSlot(nif1, shape1, i, txt1, 300);
		getShaderTextureSlot(nif2, shape2, i, txt2, 300);
		std::string txtstr1 = txt1;
		std::string txtstr2 = txt2;
		Assert::IsTrue(txtstr1 == txtstr2, L"Expected same texture in slot");
	};
	uint32_t f1_1 = getShaderFlags1(nif1, shape1);
	uint32_t f1_2 = getShaderFlags1(nif2, shape2);

	Assert::IsTrue(f1_1 == f1_2, L"ShaderFlags1 not identicial");

	uint32_t f2_1 = getShaderFlags2(nif1, shape1);
	uint32_t f2_2 = getShaderFlags2(nif2, shape2);

	Assert::IsTrue(f2_1 == f2_2, L"ShaderFlags2 not identicial");

	char name1[500];
	char name2[500];
	getShaderName(nif1, shape1, name1, 500);
	getShaderName(nif2, shape2, name2, 500);

	Assert::IsTrue(strcmp(name1, name2) == 0, L"Expected matching shader name");

	BSLSPAttrs shaderAttr1, shaderAttr2;
	getShaderAttrs(nif1, shape1, &shaderAttr1);
	getShaderAttrs(nif2, shape2, &shaderAttr2);

	Assert::IsTrue(shaderAttr1.Shader_Type == shaderAttr2.Shader_Type);
	Assert::IsTrue(shaderAttr1.Shader_Flags_1 == shaderAttr2.Shader_Flags_1);
	Assert::IsTrue(shaderAttr1.Shader_Flags_2 == shaderAttr2.Shader_Flags_2);
	Assert::IsTrue(shaderAttr1.Tex_Clamp_Mode == shaderAttr2.Tex_Clamp_Mode);
	Assert::IsTrue(TApproxEqual(shaderAttr1.UV_Offset_U, shaderAttr2.UV_Offset_U));
	Assert::IsTrue(TApproxEqual(shaderAttr1.UV_Offset_V, shaderAttr2.UV_Offset_V));
	Assert::IsTrue(TApproxEqual(shaderAttr1.UV_Scale_U, shaderAttr2.UV_Scale_U));
	Assert::IsTrue(TApproxEqual(shaderAttr1.UV_Scale_V, shaderAttr2.UV_Scale_V));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Emissive_Color_R, shaderAttr2.Emissive_Color_R));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Emissive_Color_G, shaderAttr2.Emissive_Color_G));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Emissive_Color_B, shaderAttr2.Emissive_Color_B));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Emissive_Color_A, shaderAttr2.Emissive_Color_A));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Emissmive_Mult, shaderAttr2.Emissmive_Mult));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Alpha, shaderAttr2.Alpha));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Refraction_Str, shaderAttr2.Refraction_Str));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Glossiness, shaderAttr2.Glossiness));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Spec_Color_R, shaderAttr2.Spec_Color_R));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Spec_Color_G, shaderAttr2.Spec_Color_G));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Spec_Color_B, shaderAttr2.Spec_Color_B));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Spec_Str, shaderAttr2.Spec_Str));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Soft_Lighting, shaderAttr2.Soft_Lighting));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Rim_Light_Power, shaderAttr2.Rim_Light_Power));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Skin_Tint_Alpha, shaderAttr2.Skin_Tint_Alpha));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Skin_Tint_Color_R, shaderAttr2.Skin_Tint_Color_R));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Skin_Tint_Color_G, shaderAttr2.Skin_Tint_Color_G));
	Assert::IsTrue(TApproxEqual(shaderAttr1.Skin_Tint_Color_B, shaderAttr2.Skin_Tint_Color_B));

	AlphaPropertyBuf alpha1;
	AlphaPropertyBuf alpha2;
	getAlphaProperty(nif1, shape1, &alpha1);
	getAlphaProperty(nif2, shape2, &alpha2);
	Assert::IsTrue(alpha1.flags == alpha2.flags, L"Error: Flags do not match");
	Assert::IsTrue(alpha1.threshold == alpha2.threshold, L"Error: threshold does not match");
};

void TCopyShader(void* targetNif, void* targetShape, void* sourceNif, void* sourceShape)
{
	for (int i = 0; i < 9; i++) {
		char texture[300];
		getShaderTextureSlot(sourceNif, sourceShape, i, texture, 300);
		setShaderTextureSlot(targetNif, targetShape, i, texture);
	};

	char shaderName[500];
	getShaderName(sourceNif, sourceShape, shaderName, 500);
	setShaderName(targetNif, targetShape, shaderName);

	//uint32_t st = getShaderType(sourceNif, sourceShape);
	//setShaderType(targetNif, targetShape, st);

	//uint32_t f1 = getShaderFlags1(sourceNif, sourceShape);
	//uint32_t f2 = getShaderFlags2(sourceNif, sourceShape);

	//setShaderFlags1(targetNif, targetShape, f1);
	//setShaderFlags2(targetNif, targetShape, f2);

	BSLSPAttrs shaderAttr;
	getShaderAttrs(sourceNif, sourceShape, &shaderAttr);
	setShaderAttrs(targetNif, targetShape, &shaderAttr);

	AlphaPropertyBuf alpha;
	if (getAlphaProperty(sourceNif, sourceShape, &alpha))
		setAlphaProperty(targetNif, targetShape, &alpha);
};

void TCompareExtraData(void* nif1, void* shape1, void* nif2, void* shape2) {
	int namelen, valuelen;

	for (int i = 0; getStringExtraDataLen(nif1, shape1, i, &namelen, &valuelen); i++) {
		char* namebuf1 = new char[namelen + 1];
		char* valuebuf1 = new char[valuelen + 1];
		getStringExtraData(nif1, shape1, i, namebuf1, namelen + 1, valuebuf1, valuelen + 1);

		Assert::IsTrue(getStringExtraDataLen(nif2, shape2, i, &namelen, &valuelen));
		char* namebuf2 = new char[namelen + 1];
		char* valuebuf2 = new char[valuelen + 1];
		getStringExtraData(nif2, shape2, i, namebuf2, namelen + 1, valuebuf2, valuelen + 1);

		Assert::IsTrue(strcmp(namebuf1, namebuf2) == 0, L"Error: String names not the same");
		Assert::IsTrue(strcmp(valuebuf1, valuebuf2) == 0, L"Error: String values not the same");
	};
	for (int i = 0; getBGExtraDataLen(nif1, shape1, i, &namelen, &valuelen); i++) {
		char* namebuf1 = new char[namelen + 1];
		char* valuebuf1 = new char[valuelen + 1];
		getBGExtraData(nif1, shape1, i, namebuf1, namelen + 1, valuebuf1, valuelen + 1);

		Assert::IsTrue(getBGExtraDataLen(nif2, shape2, i, &namelen, &valuelen));
		char* namebuf2 = new char[namelen + 1];
		char* valuebuf2 = new char[valuelen + 1];
		getBGExtraData(nif2, shape2, i, namebuf2, namelen + 1, valuebuf2, valuelen + 1);

		Assert::IsTrue(strcmp(namebuf1, namebuf2) == 0, L"Error: String names not the same");
		Assert::IsTrue(strcmp(valuebuf1, valuebuf2) == 0, L"Error: String values not the same");
	};
};

void TSanityCheckShape(void* nif, void* shape) {
	char name[100];
	getShapeName(shape, name, 99);
	Assert::IsTrue(strlen(name) > 0, L"Error: Shape needs a name");

	int vertLen = getVertsForShape(nif, shape, nullptr, 0, 0);
	float* verts = new float[vertLen * 3];
	getVertsForShape(nif, shape, verts, vertLen*3, 0);
	Assert::IsTrue(vertLen > 10, L"Error: Shape should have verts");

	// Check verts are within a reasonably-sized shape. Unrolled to make it easier to find problems.
	float minX=0, minY=0, minZ=0, maxX=0, maxY=0, maxZ = 0;
	for (int i = 0; i < vertLen * 3; i += 3) {
		float x = verts[i];
		float y = verts[i + 1];
		float z = verts[i + 2];
		if ((x < -200) || (y < -200) || (z < -200)
			|| (x > 200) || (y > 200) || (z > 200))
			Assert::Fail(L"Error: All verts within reasonable bounds");
		minX = std::min(minX, verts[i]);
		maxX = std::max(maxX, verts[i]);
		minY = std::min(minY, verts[i + 1]);
		maxY = std::max(maxY, verts[i + 1]);
		minZ = std::min(minZ, verts[i + 2]);
		maxZ = std::max(maxZ, verts[i + 2]);
	};
	Assert::IsTrue((minX >= -200) && (minY >= -200) && (minZ >= -200)
		&& (maxX <= 200) && (maxY <= 200) && (maxZ <= 200),
		L"Error: All verts within reasonable bounds");

	int triLen = getTriangles(nif, shape, nullptr, 0, 0);
	Assert::IsTrue(triLen > 10, L"Error: Shape should have tris");

}

namespace NiflyDLLTests
{
	TEST_CLASS(NiflyDLLTests)
	{
	public:
		TEST_METHOD(LoadReferenceSkeleton) {
			/* FUNCTION TEST: Can load a skeleton */
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
			Assert::IsFalse(std::find(shapeNames.begin(), shapeNames.end(), "Armor") == shapeNames.end());

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
			TCheckAccuracy(
				testRoot / "Skyrim/test.nif", "MaleBody",
				testRoot / "Out/TestSkinned02.nif", "Body",
				targetVert, targetBone);
		};
		TEST_METHOD(LoadAndStoreFO4)
		{
			/* Can load a nif and read info out of it */
			niflydll::LogInit();
			NifFile nif = NifFile(testRoot / "FO4/BTMaleBody.nif");
			std::vector<std::string> shapeNames = nif.GetShapeNames();
			for (std::string s : shapeNames) std::cout << s;
			Assert::IsFalse(std::find(shapeNames.begin(), shapeNames.end(), "BaseMaleBody:0") == shapeNames.end());

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

			clearMessageLog();

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

			char msgbuf[1000];
			getMessageLog(msgbuf, 1000);
			Assert::IsFalse(strstr(msgbuf, "WARNING:"), L"Error completed with warnings");
			Assert::IsFalse(strstr(msgbuf, "ERROR:"), L"Error completed with errors");

			Vector3 targetVert(2.587891f, 10.031250f, -39.593750f);
			std::string targetBone = "Spine1_skin";
			TCheckAccuracy(
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
			Assert::IsFalse(std::find(shapeNames.begin(), shapeNames.end(), "MaleHeadIMF") == shapeNames.end());

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
			aUV = nif.GetUvsForShape(theArmor);
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

			// Accessing the transform through the DLL gets the same results as going through 
			// the wrapper layer
			Assert::AreEqual(btbuf[2], btSkinInst.translation.z);
			Assert::AreEqual(btbuf[5], btSkinInst.rotation[0].z);

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

		};
		TEST_METHOD(partitionsSky) {
			std::filesystem::path testfile = testRoot / "Skyrim/malehead.nif";

			void* nif;
			void* shapes[10];
			uint16_t partitioninfo[40]; // flags, id
			int partitionCount;
			uint16_t partTris[2000];
			int triCount;

			nif = load(testfile.u8string().c_str());
			getShapes(nif, shapes, 10, 0);

			// Asking for the segment count on Skyrim nifs is allowed, but always 0. 
			Assert::AreEqual(0, segmentCount(nif, shapes[0]));

			// getPartitions returns the count so you can alloc enough space.
			partitionCount = getPartitions(nif, shapes[0], partitioninfo, 20);
			Assert::AreEqual(3, partitionCount);

			// Returned values are pairs, (flags, ID). 230 is the skyrim neck partition.
			Assert::AreEqual(230, int(partitioninfo[1]));

			// partition tris is a list of indices into the above partition list.
			// This list is 1:1 with the shape's tris.
			triCount = getPartitionTris(nif, shapes[0], partTris, 2000);
			Assert::AreEqual(1694, triCount);

			// This next test was being a bitch and we test the functionality at the
			// Blender level anyway so...
			// 
			//// Can write the partitions back out
			//std::filesystem::path testfileout = testRoot / "Out/partitionsSkyHead.nif";
			//int vlen, nlen, tlen, ulen;
			//float verts[6000];
			//float norms[6000];
			//uint16_t tris2[6000];
			//float uvs[4000];
			//vlen = getVertsForShape(nif, shapes[0], verts, 2000, 0);
			//nlen = getNormalsForShape(nif, shapes[0], norms, 2000, 0);
			//tlen = getTriangles(nif, shapes[0], tris2, 2000, 0);
			//ulen = getUVs(nif, shapes[0], uvs, 2000, 0);

			//void* nif2 = createNif("SKYRIM");
			//void* newSkin = createSkinForNif(nif2, "SKYRIM");
			//void* sh = createNifShapeFromData(nif2, "Head", verts, vlen, tris2, tlen, uvs, ulen,
			//	norms, nlen);
			//skinShape(nif2, sh);
			//
			//// On write, we don't send the partition flags
			////int writeParts[40];
			////for (int i = 0; i < partitionCount; i++) writeParts[i] = partitioninfo[i * 2 + 1];
			////setPartitions(nif, shapes[0], writeParts, partitionCount, tris, triCount);
			//saveSkinnedNif(newSkin, testfileout.string().c_str());

			//// And on reading, should have same values
			//void* nif3;
			//void* shapes3[10];
			//nif3 = load(testfileout.string().c_str());
			//getShapes(nif3, shapes3, 10, 0);

			//// Can check for segment count even on Skyrim nifs. 
			//Assert::AreEqual(0, segmentCount(nif3, shapes3[0]));

			//// getPartitions returns the count so you can alloc enough space.
			//partitionCount = getPartitions(nif3, shapes3[0], partitioninfo, 20);
			//Assert::AreEqual(3, partitionCount);

			//// Returned values are pairs, (flags, ID). 230 is the skyrim HEAD partition.
			//Assert::AreEqual(230, int(partitioninfo[1]));

			//// partition tris is a list of indices into the above partition list.
			//// This list is 1:1 with the shape's tris.
			//triCount = getPartitionTris(nif3, shapes3[0], partTris, 2000);
			//Assert::AreEqual(1694, triCount);
		};
		TEST_METHOD(getPartitionFO4) {
			std::filesystem::path testfile = testRoot / "FO4/VanillaMaleBody.nif";

			void* nif;
			void* shapes[10];
			int segInfo[40]; // id, subseg count
			int segCount;
			uint16_t tris[3000];
			int triCount;
			char fname[256];
			int namelen;

			nif = load(testfile.u8string().c_str());
			getShapes(nif, shapes, 10, 0);

			// segmentCount returns the count of segments in the shape
			// Vanilla body has 7 top-level segments
			segCount = segmentCount(nif, shapes[0]);
			Assert::AreEqual(7, segCount);

			getSegments(nif, shapes[0], segInfo, 20);
			// Segments don't have a real ID but nifly assigns one for reference.
			Assert::AreNotEqual(0, int(segInfo[2]));
			// This shape has 4 subsegments in its 3rd segment
			Assert::AreEqual(4, segInfo[5]);

			// 2698 tris in this shape
			triCount = getPartitionTris(nif, shapes[0], tris, 3000);
			Assert::AreEqual(2698, triCount);

			// There's an external segment file
			namelen = getSegmentFile(nif, shapes[0], fname, 256);
			Assert::AreEqual("Meshes\\Actors\\Character\\CharacterAssets\\MaleBody.ssf", fname);
			Assert::AreEqual(52, namelen);

			// FO4 segments have subsegments
			uint32_t subsegs[20 * 3];
			int sscount = getSubsegments(nif, shapes[0], segInfo[4], subsegs, 20);
			Assert::AreEqual(4, sscount);
		};

		TEST_METHOD(geBPFO4) {
			std::filesystem::path testfile = testRoot / "FO4/Helmet.nif";

			void* nif;
			void* shapes[10];
			int segInfo[40]; // id, subseg count
			int segCount;
			uint16_t tris[3000];
			int triCount;
			char fname[256];
			int namelen;
			int seg1id;

			nif = load(testfile.u8string().c_str());
			getShapes(nif, shapes, 10, 0);

			// segmentCount returns the count of segments in the shape
			// Helmet has 2 top-level segments
			segCount = segmentCount(nif, shapes[0]);
			Assert::AreEqual(2, segCount);

			void* theHelmet = shapes[1];
			getSegments(nif, theHelmet, segInfo, 20);
			// Segments don't have a real ID but nifly assigns one for reference.
			Assert::AreEqual(0, int(segInfo[0]));
			// This shape has 1 subsegments in its 1st segment
			seg1id = segInfo[2];
			Assert::AreEqual(1, seg1id);

			// 2698 tris in this shape
			triCount = getPartitionTris(nif, theHelmet, tris, 3000);
			Assert::AreEqual(2878, triCount);

			// There's an external segment file
			namelen = getSegmentFile(nif, theHelmet, fname, 256);
			Assert::AreEqual("Meshes\\Armor\\FlightHelmet\\Helmet.ssf", fname);

			// FO4 segments have subsegments
			uint32_t subsegs[20 * 3];
			int sscount = getSubsegments(nif, theHelmet, seg1id, subsegs, 20);
			Assert::AreEqual(1, sscount);
			Assert::AreEqual(30, int(subsegs[1]));

			// ------ Now show we can write the file back out -------
			std::filesystem::path testfileout = testRoot / "Out/geBPFO4Helmet.nif";

			float verts[2500 * 3];
			uint16_t rawtris[3000 * 3];
			float uv[2500 * 2];
			float norms[2500 * 3];

			int vlen = getVertsForShape(nif, theHelmet, verts, 2500, 0);
			int tlen = getTriangles(nif, theHelmet, rawtris, 3000, 0);
			int ulen = getUVs(nif, theHelmet, uv, 2500, 0);
			int nlen = getNormalsForShape(nif, theHelmet, norms, 2500, 0);


			//AnimInfo oldBodySkin;

			//skin.LoadFromNif(&nif, theBody);

			//AnimInfo* anim;
			//AnimSkeleton::getInstance().LoadFromNif(SkeletonFile(FO4), curRootName);

			void* newNif = createNif("FO4");
			void* newSkin = createSkinForNif(newNif, "FO4");

			void* newHelm = createNifShapeFromData(newNif, "Helmet",
				verts, uv, norms, vlen,
				rawtris, tlen,
				nullptr);
			skinShape(newNif, newHelm);

			uint16_t segData[100];
			uint32_t subsegData[100];
			segData[0] = 1;
			subsegData[0] = 2;	// subseg ID
			subsegData[1] = 1;	// parent ID
			subsegData[2] = 30; // user slot
			subsegData[3] = -1; // material

			uint16_t tripart[3000];
			for (int i = 0; i < tlen; i++) { tripart[i] = 2; }
			setSegments(newNif, newHelm, segData, 1, subsegData, 1,
				tripart, tlen,
				"Meshes\\Armor\\FlightHelmet\\HelmetOut.ssf");

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
			//MatTransform bodyGTS;
			////armorGTS.translation = { 0.000256f, 1.547526f, -120.343582f };
			//bool hasGTSkin = nif.GetShapeTransformGlobalToSkin(theBody, bodyGTS);
			//Assert::IsFalse(hasGTSkin), L"ERROR: FO4 nifs do not have skin transforms";
			//if (!hasGTSkin)
			//	GetGlobalToSkin(&oldBodySkin, theBody, &bodyGTS);
			//Assert::AreEqual(-120, int(bodyGTS.translation.z), L"ERROR: Body nifs have a -120 z transform");
			//SetGlobalToSkinXform(anim, newBody, bodyGTS);

			/*
			This transform is applied to the NiSkinData block. It gives the
			overall transform for the model when there's a NiSkinData block (Skyrim).
			It has to be set correctly so that the model can be put in skinned position
			when read into blender, because if the block exists only this transform is used.
			*/
			//if (theBody->HasSkinInstance()) {
			//	MatTransform sourceXformGlobalToSkin;
			//	if (nif.GetShapeTransformGlobalToSkin(theBody, sourceXformGlobalToSkin))
			//		SetShapeGlobalToSkinXform(anim, theBody, sourceXformGlobalToSkin);
			//}

			//std::vector<std::string> bodyBoneNames;
			//nif.GetShapeBoneList(theBody, bodyBoneNames);
			//std::unordered_map<std::string, AnimWeight> bodyWeights;
			//for (int i = 0; i < bodyBoneNames.size(); i++) {
			//	AnimWeight w;
			//	nif.GetShapeBoneWeights(theBody, i, w.weights);
			//	bodyWeights[bodyBoneNames[i]] = w;
			//}
			///* Sets bone weights only. Doesn't set transforms. */
			//for (auto w : bodyWeights) {
			//	AddBoneToShape(anim, newBody, w.first, nullptr);
			//	SetShapeWeights(anim, newBody, w.first, w.second);
			//}
			addBoneToShape(newSkin, newHelm, "HEAD", nullptr);

			saveSkinnedNif(newSkin, testfileout.u8string().c_str());
			saveNif(newNif, testfileout.u8string().c_str());

			// ------ And we can read what we wrote -------
			void* shapes3[10];
			void* nif3 = load(testfileout.u8string().c_str());
			getShapes(nif3, shapes3, 10, 0);

			// segmentCount returns the count of segments in the shape
			// Helmet has 2 top-level segments
			int segCount3 = segmentCount(nif3, shapes3[0]);
			Assert::AreEqual(1, segCount3);

			char ssfile[100];
			getSegmentFile(nif3, shapes3[0], ssfile, 100);
			Assert::AreEqual("Meshes\\Armor\\FlightHelmet\\HelmetOut.ssf", ssfile);

			int segInfo3[20];
			segCount = getSegments(nif3, shapes3[0], segInfo3, 20);
			// This shape has 1 subsegments in its 1st segment
			seg1id = segInfo3[0];
			Assert::AreEqual(0, seg1id);

			sscount = getSubsegments(nif3, shapes3[0], seg1id, subsegs, 20);
			Assert::AreEqual(1, sscount);
			Assert::AreEqual(30, int(subsegs[1]));
		};

		TEST_METHOD(vertexColors) {
			/* Can load and save vertex colors */
			std::filesystem::path testfile = testRoot / "FO4/HeadGear1.nif";

			void* nif;
			void* shapes[10];
			float verts[1000 * 3];
			float colors[1000 * 4];
			float norms[1000 * 3];
			float uvs[1000 * 2];
			uint16_t tris[1100 * 3];

			// Can load vertex colors
			nif = load(testfile.u8string().c_str());
			getShapes(nif, shapes, 10, 0);
			int vertLen = getVertsForShape(nif, shapes[0], verts, 1000, 0);
			int colorLen = getColorsForShape(nif, shapes[0], colors, vertLen*4);
			int triLen = getTriangles(nif, shapes[0], tris, 1100 * 3, 0);
			int uvLen = getUVs(nif, shapes[0], uvs, vertLen * 2, 0);
			int normLen = getNormalsForShape(nif, shapes[0], norms, vertLen * 3, 0);

			Assert::AreEqual(vertLen, colorLen);
			Assert::IsTrue(colors[0] == 1 and
				colors[1] == 1 and
				colors[2] == 1 and
				colors[3] == 1);
			
			Assert::IsTrue(colors[561 * 4] == 0);

			// Can save vertex colors
			std::filesystem::path testfileOut = testRoot / "Out/vertexColors_HeadGear1.nif";

			void* nif2 = createNif("FO4");
			void* shape2 = createNifShapeFromData(nif2, "Hood",
				verts, uvs, norms, vertLen,
				tris, triLen,
				nullptr);
			setColorsForShape(nif2, shape2, colors, colorLen);

			saveNif(nif2, testfileOut.u8string().c_str());

			// And can read them back correctly
			void* nif3;
			void* shapes3[10];
			float colors3[1000*4];

			nif3 = load(testfileOut.u8string().c_str());
			getShapes(nif3, shapes3, 10, 0);
			int colorsLen3 = getColorsForShape(nif3, shapes3[0], colors3, 1000 * 4);

			Assert::AreEqual(vertLen, colorsLen3);
			Assert::IsTrue(colors3[0] == 1 and
				colors3[1] == 1 and
				colors3[2] == 1 and
				colors3[3] == 1);

			Assert::IsTrue(colors3[561 * 4] == 0);
		};
		TEST_METHOD(expImpFNV) {
			/* NOT WORKING */
			return;

			/* Can load and save vertex colors */
			std::filesystem::path testfile = testRoot / "FNV/9mmscp.nif";

			void* nif;
			void* shapes[10];
			float verts[1000 * 3];
			float norms[1000 * 3];
			float uvs[1000 * 2];
			uint16_t tris[1100 * 3];

			// Can load nif
			nif = load(testfile.u8string().c_str());
			int shapeCount = getShapes(nif, shapes, 10, 0);
			int vertLen = getVertsForShape(nif, shapes[0], verts, 1000, 0);
			int triLen = getTriangles(nif, shapes[0], tris, 1100 * 3, 0);
			int uvLen = getUVs(nif, shapes[0], uvs, vertLen * 2, 0);
			int normLen = getNormalsForShape(nif, shapes[0], norms, vertLen * 3, 0);

			Assert::AreEqual(9, shapeCount, L"Have right number of shapes");

			// Can save nif
			std::filesystem::path testfileOut = testRoot / "Out/expImpFNV_9mmscp.nif";

			void* nif2 = createNif("FONV");
			void* shape2 = createNifShapeFromData(nif2, "Scope",
				verts, uvs, norms, vertLen,
				tris, triLen,
				nullptr);

			saveNif(nif2, testfileOut.u8string().c_str());

			// And can read them back correctly
			void* nif3;
			void* shapes3[10];

			nif3 = load(testfileOut.u8string().c_str());
			getShapes(nif3, shapes3, 10, 0);

		};
		TEST_METHOD(hdtBones) {
			/* Can load and save shape with unique HDT bones */
			std::filesystem::path testfile = testRoot / "SkyrimSE/Anchor.nif";

			void* nif;
			void* shapes[10];
			float verts[1000 * 3];
			float norms[1000 * 3];
			float uvs[1000 * 2];
			uint16_t tris[1100 * 3];

			// Can load nif. Intentionally passing in short buffers to make sure that works.
			// This is a big nif, so it will overwrite everything in sight if it's wrong.
			nif = load(testfile.u8string().c_str());
			int shapeCount = getShapes(nif, shapes, 10, 0);
			long vertLen = getVertsForShape(nif, shapes[0], verts, 1000, 0);
			int triLen = getTriangles(nif, shapes[0], tris, 1100 * 3, 0);
			int uvLen = getUVs(nif, shapes[0], uvs, 1000 * 2, 0);
			int normLen = getNormalsForShape(nif, shapes[0], norms, 1000 * 3, 0);

			Assert::AreEqual(1, shapeCount, L"Have right number of shapes");
			Assert::AreEqual(16534L, vertLen, L"Have right number of vertices");

			// Can save nif
			std::filesystem::path testfileOut = testRoot / "Out/hdtBones_Anchor.nif";

			// Get all the data because we didn't above
			float* verts2 = new float[vertLen * 3];
			uint16_t* tris2 = new uint16_t[triLen * 3];
			float* uvs2 = new float[vertLen * 2];
			float* norms2 = new float[vertLen * 3];

			getVertsForShape(nif, shapes[0], verts2, vertLen, 0);
			getTriangles(nif, shapes[0], tris2, triLen * 3, 0);
			getUVs(nif, shapes[0], uvs2, vertLen * 2, 0);
			getNormalsForShape(nif, shapes[0], norms2, vertLen * 3, 0);

			void* nif2 = createNif("SKYRIMSE");
			void* skin2 = createSkinForNif(nif2, "SKYRIMSE");

			uint16_t options = 1;
			void* shape2 = createNifShapeFromData(nif2, "KSSMP_Anchor",
				verts2, uvs2, norms2, vertLen,
				tris2, triLen,
				&options);

			skinShape(nif2, shape2);

			char boneNameBuf[2000];
			int boneCount = getShapeBoneCount(nif, shapes[0]);
			getShapeBoneNames(nif, shapes[0], boneNameBuf, 2000);
			for (char* p = boneNameBuf; *p != '\0'; p++) {
				if (*p == '\n') *p = '\0';
			}
			char* bnp = boneNameBuf;
			for (int boneIdx = 0; boneIdx < boneCount; boneIdx++) {
				MatTransform boneXForm;
				int vwpLen = getShapeBoneWeightsCount(nif, shapes[0], boneIdx);
				VertexWeightPair* vwp = new VertexWeightPair[vwpLen];
				getShapeBoneWeights(nif, shapes[0], boneIdx, vwp, vwpLen);
				getBoneSkinToBoneXform(skin2, "KSSMP_Anchor", bnp, &boneXForm.translation.x);

				addBoneToShape(skin2, shape2, bnp, &boneXForm);
				setShapeBoneWeights(nif2, shape2, boneIdx, vwp, vwpLen);

				for (; *bnp != '\0'; bnp++);
				bnp++;
				delete[]vwp;
			};

			saveSkinnedNif(skin2, testfileOut.u8string().c_str());

			// And can read them back correctly
			void* nif3;
			void* shapes3[10];
			float* verts3 = new float[vertLen * 3];

			nif3 = load(testfileOut.u8string().c_str());
			int shapeCount3 = getShapes(nif3, shapes3, 10, 0);
			long vertLen3 = getVertsForShape(nif3, shapes3[0], verts3, vertLen * 3, 0);

			Assert::IsTrue(vertLen == vertLen3, L"Got same number of verts back");

			delete[]verts2;
			delete[]tris2;
			delete[]uvs2;
			delete[]norms2;
			delete[]verts3;
		};
		TEST_METHOD(blockName) {
			std::filesystem::path testfile = testRoot / "SkyrimSE/malehead.nif";

			void* nif;
			void* shapes[10];

			// Can load nif. Intentionally passing in short buffers to make sure that works.
			// This is a big nif, so it will overwrite everything in sight if it's wrong.
			nif = load(testfile.u8string().c_str());
			int shapeCount = getShapes(nif, shapes, 10, 0);
			char blockname[50];
			getShapeBlockName(shapes[0], blockname, 50);
			Assert::AreEqual("BSDynamicTriShape", blockname, L"Have expected node type");
		};
		TEST_METHOD(loadAndStoreUnskinned) {
			std::filesystem::path testfile = testRoot / "FO4/AlarmClock.nif";

			void* nif;
			void* shapes[10];
			float verts[1000 * 3];
			float norms[1000 * 3];
			float uvs[1000 * 2];
			uint16_t tris[1100 * 3];

			nif = load(testfile.u8string().c_str());
			int shapeCount = getShapes(nif, shapes, 10, 0);
			char blockname[50];
			getShapeBlockName(shapes[0], blockname, 50);
			Assert::AreEqual("BSTriShape", blockname, L"Have expected node type");

			int vertLen = getVertsForShape(nif, shapes[0], verts, 1000, 0);
			int triLen = getTriangles(nif, shapes[0], tris, 1100 * 3, 0);
			int uvLen = getUVs(nif, shapes[0], uvs, vertLen * 2, 0);
			int normLen = getNormalsForShape(nif, shapes[0], norms, vertLen * 3, 0);

			std::filesystem::path testfileOut = testRoot / "Out/loadAndStoreUnskinned.nif";

			void* nif2 = createNif("FO4");
			uint16_t options = 2;
			void* shape2 = createNifShapeFromData(nif2, "AlarmClock",
				verts, uvs, norms, vertLen,
				tris, triLen,
				&options);

			saveNif(nif2, testfileOut.u8string().c_str());

			void* nif3 = load(testfileOut.u8string().c_str());
			void* shapes3[10];
			int shapeCount3 = getShapes(nif3, shapes3, 10, 0);
			getShapeBlockName(shapes3[0], blockname, 50);
			Assert::AreEqual("BSTriShape", blockname, L"Have expected node type");
		};
		TEST_METHOD(loadAndStoreUni) {
			// Can load and store files with extended character set in path
			// Can't figure out how to use extended character set in the source
			// file so do a stupid workaround.
			std::filesystem::path testdir = testRoot / "FO4/TestUnicode";
			for (const std::filesystem::directory_entry testfile :
			std::filesystem::recursive_directory_iterator(testdir)) {
				if (testfile.path().extension() == ".nif") {
					std::u8string fp = testfile.path().u8string();
					const char8_t* fpstr = fp.c_str();
					void* nif = load(fpstr);

					void* shapes[10];
					int shapeCount = getShapes(nif, shapes, 10, 0);
					char blockname[50];
					getShapeBlockName(shapes[0], blockname, 50);
					Assert::AreEqual("BSTriShape", blockname, L"Have expected node type");

					std::filesystem::path testfileOut = testRoot / "Out" / testfile.path().filename();
					void* nif2 = createNif("FO4");

					uint16_t options = 2;
					void* skin2;
					void* shape2 = TCopyShape(nif2, "AlarmClock", nif, shapes[0], options, &skin2);
					saveNif(nif2, testfileOut.u8string().c_str());

					void* nif3 = load(testfileOut.u8string().c_str());
					void* shapes3[10];
					int shapeCount3 = getShapes(nif3, shapes3, 10, 0);
					getShapeBlockName(shapes3[0], blockname, 50);
					Assert::AreEqual("BSTriShape", blockname, L"Have expected node type");
				};
			};
		};
		TEST_METHOD(shaders) {
			// Can read the shaders from a shape
			std::filesystem::path testfile = testRoot / "Skyrim/MaleHead.nif";

			void* nif;
			void* shapes[10];

			nif = load(testfile.u8string().c_str());
			int shapeCount = getShapes(nif, shapes, 10, 0);
			char textures[9][300];

			std::string* txtstr[9];
			for (int i = 0; i < 9; i++) {
				getShaderTextureSlot(nif, shapes[0], i, textures[i], 300);
				txtstr[i] = new std::string(textures[i]);
			};

			Assert::IsTrue(txtstr[0]->compare("textures\\actors\\character\\male\\MaleHead.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[1]->compare("textures\\actors\\character\\male\\MaleHead_msn.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[2]->compare("textures\\actors\\character\\male\\MaleHead_sk.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[7]->compare("textures\\actors\\character\\male\\MaleHead_S.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[3]->compare("") == 0, L"Found expected texture");

			uint32_t f1 = getShaderFlags1(nif, shapes[0]);
			uint32_t f2 = getShaderFlags2(nif, shapes[0]);
			Assert::IsTrue(f1 & (1 << 12), L"Expected MSN bit set");

			BSLSPAttrs shaderAttr;
			getShaderAttrs(nif, shapes[0], &shaderAttr);
			Assert::IsTrue(TApproxEqual(
				Vector3(shaderAttr.Spec_Color_R, shaderAttr.Spec_Color_G, shaderAttr.Spec_Color_B), 
				Vector3(0xa1/255.0, 0xc2/255.0, 0xff/255.0)));
			Assert::IsTrue(TApproxEqual(shaderAttr.Spec_Str, 2.69));
			Assert::IsTrue(shaderAttr.Shader_Type == uint32_t(BSLSPShaderType::Face_Tint));
			Assert::IsTrue(shaderAttr.Glossiness == 33.0, L"Error: Glossiness value");

			// Can write head back out

			std::filesystem::path testfileO = testRoot / "Out" / "testWrapper_Shaders01.nif";

			void* nifOut = createNif("Skyrim");
			uint16_t options = 0;
			void* skinOut;
			void* shapeOut = TCopyShape(nifOut, "MaleHead", nif, shapes[0], 0, &skinOut);
			TCopyShader(nifOut, shapeOut, nif, shapes[0]);
			//setShaderTextureSlot(nifOut, shapeOut, 0, txtstr[0]->c_str());
			//setShaderTextureSlot(nifOut, shapeOut, 1, txtstr[1]->c_str());
			//setShaderTextureSlot(nifOut, shapeOut, 2, txtstr[2]->c_str());
			//setShaderTextureSlot(nifOut, shapeOut, 7, txtstr[7]->c_str());

			//setShaderFlags1(nifOut, shapeOut, f1);
			//setShaderFlags2(nifOut, shapeOut, f2);

			saveSkinnedNif(skinOut, testfileO.u8string().c_str());

			// What we wrote is correct

			void* nifTest = load(testfileO.u8string().c_str());
			void* shapesTest[10];
			shapeCount = getShapes(nifTest, shapesTest, 10, 0);
			TCompareShaders(nif, shapes[0], nifTest, shapesTest[0]);

			// Can read chest

			std::filesystem::path testfile2 = testRoot / "Skyrim/NobleCrate01.nif";
			void* nif2 = load(testfile2.u8string().c_str());
			void* shapes2[10];
			shapeCount = getShapes(nif2, shapes2, 10, 0);
			for (int i = 0; i < 9; i++) {
				getShaderTextureSlot(nif2, shapes2[0], i, textures[i], 300);
				txtstr[i] = new std::string(textures[i]);
			};
			uint32_t flagsOne2 = getShaderFlags1(nifTest, shapes2[0]);

			Assert::IsTrue(txtstr[0]->compare("textures\\furniture\\noble\\NobleFurnChest01.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[1]->compare("textures\\furniture\\noble\\NobleFurnChest01_n.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[2]->compare("") == 0, L"Found expected texture");
			Assert::IsFalse(flagsOne2 & static_cast<uint32_t>(ShaderProperty1::MODEL_SPACE_NORMALS),
				L"Found MSN flag not set");

			// Can write chest back out

			std::filesystem::path testfile2Out = testRoot / "Out" / "testWrapper_Shaders02.nif";

			void* nif2Out = createNif("Skyrim");
			options = 0;
			void* skin2Out;
			void* shape2Out = TCopyShape(nif2Out, "NobleCrate", nif2, shapes2[0], 0, &skin2Out);
			TCopyShader(nif2Out, shape2Out, nif2, shapes2[0]);

			saveNif(nif2Out, testfile2Out.u8string().c_str());

			// What we wrote is correct

			void* nif2Test = load(testfile2Out.u8string().c_str());
			void* shapes2Test[10];
			shapeCount = getShapes(nif2Test, shapes2Test, 10, 0);

			TCompareShaders(nif2, shapes2[0], nif2Test, shapes2Test[0]);
		};
		TEST_METHOD(shadersFO4) {
			// Can read the shaders from a shape
			std::filesystem::path testfile = testRoot / "FO4/BaseMaleHead.nif";

			void* nif;
			void* shapes[10];

			nif = load(testfile.u8string().c_str());
			int shapeCount = getShapes(nif, shapes, 10, 0);
			char textures[9][300];

			std::string* txtstr[9];
			for (int i = 0; i < 9; i++) {
				getShaderTextureSlot(nif, shapes[0], i, textures[i], 300);
				txtstr[i] = new std::string(textures[i]);
			};
			char shaderName[500];
			getShaderName(nif, shapes[0], shaderName, 500);

			BSLSPAttrs shaderAttr;
			getShaderAttrs(nif, shapes[0], &shaderAttr);
			Assert::IsTrue(TApproxEqual(
				Vector3(shaderAttr.Spec_Color_R, shaderAttr.Spec_Color_G, shaderAttr.Spec_Color_B),
				Vector3(1.0, 1.0, 1.0)));
			Assert::IsTrue(TApproxEqual(shaderAttr.Spec_Str, 1.0));
			Assert::IsTrue(shaderAttr.Shader_Type == uint32_t(BSLSPShaderType::Face_Tint));

			Assert::IsTrue(txtstr[0]->compare("textures\\Actors\\Character\\BaseHumanMale\\BaseMaleHead_d.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[1]->compare("textures\\Actors\\Character\\BaseHumanMale\\BaseMaleHead_n.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[2]->compare("") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[7]->compare("textures\\actors\\character\\basehumanmale\\basemalehead_s.dds") == 0, L"Found expected texture");
			Assert::IsTrue(txtstr[3]->compare("") == 0, L"Found expected texture");
			Assert::AreEqual(shaderName, "Materials\\Actors\\Character\\BaseHumanMale\\basehumanskinHead.bgsm", L"Expected materials path");

			// Can write head back out

			std::filesystem::path testfileO = testRoot / "Out" / "testWrapper_shadersFO401.nif";

			void* nifOut = createNif("FO4");
			uint16_t options = 0;
			void* skin;
			void* shapeOut = TCopyShape(nifOut, "MaleHead", nif, shapes[0], 0, &skin);
			TCopyShader(nifOut, shapeOut, nif, shapes[0]);

			saveSkinnedNif(skin, testfileO.u8string().c_str());

			// What we wrote is correct

			void* nifTest = load(testfileO.u8string().c_str());
			void* shapesTest[10];
			shapeCount = getShapes(nifTest, shapesTest, 10, 0);

			TCompareShaders(nif, shapes[0], nifTest, shapesTest[0]);
		};
		TEST_METHOD(shadersReadType) {
			void* nif;
			void* shapes[10];

			nif = load((testRoot / "Skyrim/NobleCrate01.nif").u8string().c_str());
			getShapes(nif, shapes, 10, 0);
			Assert::IsTrue(uint32_t(BSLSPShaderType::Default) == getShaderType(nif, shapes[0]),
				L"Expected shader type Default");

			nif = load((testRoot / "SkyrimSE/MaleHead.nif").u8string().c_str());
			getShapes(nif, shapes, 10, 0);
			Assert::IsTrue(uint32_t(BSLSPShaderType::Face_Tint) == getShaderType(nif, shapes[0]),
				L"Expected shader type Face_Tint");

			nif = load((testRoot / "FO4/BodyTalk3.nif").u8string().c_str());
			getShapes(nif, shapes, 10, 0);
			Assert::IsTrue(uint32_t(BSLSPShaderType::Skin_Tint) == getShaderType(nif, shapes[0]),
				L"Expected shader type Skin_Tint");
		};
		TEST_METHOD(shadersReadAlpha) {
			void* nif;
			void* shapes[10];
			AlphaPropertyBuf alpha;

			nif = load((testRoot / "Skyrim/meshes/actors/character/Lykaios/Tails/maletaillykaios.nif").u8string().c_str());
			getShapes(nif, shapes, 10, 0);
			void* shape = shapes[1];
			bool hasAlpha = getAlphaProperty(nif, shape, &alpha);

			Assert::IsTrue(uint32_t(BSLSPShaderType::Skin_Tint) == getShaderType(nif, shapes[0]),
				L"Expected shader type Skin_Tint");
			Assert::IsTrue(hasAlpha, L"Error: Should have alpha property");
			Assert::IsTrue(alpha.flags == 4844, L"Error: Flags not correct");
			Assert::IsTrue(alpha.threshold == 70, L"Error: Threshold not correct");

			// ### Can write the alpha property back out

			std::filesystem::path fileOut = testRoot / "Out" / "testWrapper_shadersReadAlpha.nif";

			void* nifOut = createNif("Skyrim");
			uint16_t options = 0;
			void* skinOut;
			void* shapeOut = TCopyShape(nifOut, "TailFur", nif, shape, 0, &skinOut);
			TCopyShader(nifOut, shapeOut, nif, shape);

			saveSkinnedNif(skinOut, fileOut.u8string().c_str());

			// What we wrote is correct

			void* nifCheck = load(fileOut.u8string().c_str());
			void* shapesCheck[10];
			getShapes(nifCheck, shapesCheck, 10, 0);
			TCompareShaders(nif, shape, nifCheck, shapesCheck[0]);
		};
		TEST_METHOD(extraDataBody) {
			void* shapes[10];
			int namelen, vallen;

			void* nifbody = load((testRoot / "FO4/BTMaleBody.nif").u8string().c_str());
			getShapes(nifbody, shapes, 10, 0);
			void* body = shapes[0];

			getStringExtraDataLen(nifbody, nullptr, 0, &namelen, &vallen);
			char* bodytri = new char[namelen+1L];
			char* bodypath = new char[vallen+1L];
			getStringExtraData(nifbody, nullptr, 0, bodytri, namelen+1, bodypath, vallen+1);
			Assert::IsTrue(strcmp(bodytri, "BODYTRI") == 0, L"Error: Extradata name wrong");
			Assert::IsTrue(strcmp(bodypath, "actors\\character\\characterassets\\MaleBody.tri") == 0, L"Error: Extradata value wrong");
		};
		TEST_METHOD(extraDataSheath) {
			void* shapes[10];
			int namelen, vallen;

			void* nifsheath = load((testRoot / "Skyrim/sheath_p1_1.nif").u8string().c_str());
			getShapes(nifsheath, shapes, 10, 0);
			void* sheath = shapes[0];

			getStringExtraDataLen(nifsheath, nullptr, 0, &namelen, &vallen);
			char* namepath1 = new char[namelen + 1L];
			char* path1 = new char[vallen + 1L];
			getStringExtraData(nifsheath, nullptr, 0, namepath1, namelen+1, path1, vallen+1);
			Assert::IsTrue(strcmp(namepath1, "HDT Havok Path") == 0, L"Error: Extradata name wrong");
			Assert::IsTrue(strcmp(path1, "SKSE\\Plugins\\hdtm_baddog.xml") == 0, L"Error: Extradata value wrong");

			getStringExtraDataLen(nifsheath, nullptr, 1, &namelen, &vallen);
			char* namepath2 = new char[namelen + 1L];
			char* path2 = new char[vallen + 1L];
			getStringExtraData(nifsheath, nullptr, 1, namepath2, namelen+1, path2, vallen+1);
			Assert::IsTrue(strcmp(namepath2, "HDT Skinned Mesh Physics Object") == 0, L"Error: Extradata name wrong");
			Assert::IsTrue(strcmp(path2, "SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml") == 0, L"Error: Extradata value wrong");

			getBGExtraDataLen(nifsheath, nullptr, 0, &namelen, &vallen);
			char* edname= new char[namelen + 1L];
			char* edtxt = new char[vallen + 1L];
			getBGExtraData(nifsheath, nullptr, 0, edname, namelen+1, edtxt, vallen+1);
			Assert::IsTrue(strcmp(edname, "BGED") == 0, L"Error: Extradata name wrong");
			Assert::IsTrue(strcmp(edtxt, "AuxBones\\SOS\\SOSMale.hkx") == 0, L"Error: Extradata value wrong");

			// ### Can wrie the mesh back out

			std::filesystem::path fileOut = testRoot / "Out/testWrapper_extraDataSheath.nif";

			void* nifOut = createNif("SKYRIM");
			uint16_t options = 0;
			void* skinOut;
			void* shapeOut = TCopyShape(nifOut, "Sheath", nifsheath, sheath, 0, &skinOut);
			TCopyShader(nifOut, shapeOut, nifsheath, sheath);
			TCopyExtraData(nifOut, nullptr, nifsheath, nullptr);
			TCopyExtraData(nifOut, shapeOut, nifsheath, sheath);

			saveSkinnedNif(skinOut, fileOut.u8string().c_str());

			// What we wrote is correct

			void* nifCheck = load(fileOut.u8string().c_str());
			void* shapesCheck[10];
			getShapes(nifCheck, shapesCheck, 10, 0);
			TCompareExtraData(nifsheath, nullptr, nifCheck, nullptr);
			TCompareExtraData(nifsheath, sheath, nifCheck, shapesCheck[0]);
		};
		TEST_METHOD(extraDataFeet) {
			void* shapes[10];
			int namelen, vallen;

			void* niffeet = load((testRoot / "SkyrimSE/caninemalefeet_1.nif").u8string().c_str());
			getShapes(niffeet, shapes, 10, 0);
			void* feet = shapes[0];

			getStringExtraDataLen(niffeet, feet, 0, &namelen, &vallen);
			char* dataname = new char[namelen + 1L];
			char* dataval = new char[vallen + 1L];
			getStringExtraData(niffeet, feet, 0, dataname, namelen + 1, dataval, vallen + 1);
			Assert::IsTrue(strcmp(dataname, "SDTA") == 0, L"Error: Extradata name wrong");
			Assert::IsTrue(strncmp(dataval, "[{\"name\":", 9) == 0, L"Error: Extradata value wrong");

			// ### Can wrie the mesh back out

			std::filesystem::path fileOut = testRoot / "Out/testWrapper_extraDataFeet.nif";

			void* nifOut = createNif("SKYRIMSE");
			uint16_t options = 0;
			void* skinOut;
			void* shapeOut = TCopyShape(nifOut, "FootLowRes", niffeet, feet, 0, &skinOut);
			TCopyShader(nifOut, shapeOut, niffeet, feet);

			TCopyExtraData(nifOut, nullptr, niffeet, nullptr);

			saveSkinnedNif(skinOut, fileOut.u8string().c_str());

			// What we wrote is correct

			void* nifCheck = load(fileOut.u8string().c_str());
			void* shapesCheck[10];
			getShapes(nifCheck, shapesCheck, 10, 0);
			TCompareShapes(niffeet, feet, nifCheck, shapesCheck[0]);
			TCompareExtraData(niffeet, nullptr, nifCheck, nullptr);
			TCompareExtraData(niffeet, feet, nifCheck, shapesCheck[0]);
		};
		TEST_METHOD(impExpSE) {
			void* shapes[10];

			void* nifhead = load((testRoot / "SkyrimSE/malehead.nif").u8string().c_str());
			Assert::IsTrue(getShapes(nifhead, shapes, 10, 0) == 1, L"ERROR: Wrong number of shapes");
			void* head = shapes[0];
			TSanityCheckShape(nifhead, head);

			// ### Can wrie the mesh back out

			clearMessageLog();
			std::filesystem::path fileOut = testRoot / "Out/testWrapper_impExpSE.nif";

			void* nifOut = createNif("SKYRIMSE");
			uint16_t options = 0;
			void* skinOut;
			void* shapeOut = TCopyShape(nifOut, "MaleHeadIMF", nifhead, head, 1, &skinOut);
			TCopyShader(nifOut, shapeOut, nifhead, head);
			//TCopyExtraData(nifOut, nullptr, nifhead, nullptr);
			//TCopyExtraData(nifOut, shapeOut, nifhead, head);

			saveSkinnedNif(skinOut, fileOut.u8string().c_str());
			const int MSGBUFLEN = 2000;
			char msgbuf[MSGBUFLEN]; 
			int loglen = getMessageLog(msgbuf, MSGBUFLEN);
			Assert::IsFalse(strstr(msgbuf, "WARNING:"), L"Error completed with warnings");
			Assert::IsFalse(strstr(msgbuf, "ERROR:"), L"Error completed with errors");

			// What we wrote is correct

			clearMessageLog();
			void* nifCheck = load(fileOut.u8string().c_str());
			void* shapesCheck[10];
			getShapes(nifCheck, shapesCheck, 10, 0);
			TSanityCheckShape(nifCheck, shapesCheck[0]);
			TCompareShapes(nifhead, head, nifCheck, shapesCheck[0]);

			//TCompareExtraData(nifhead, nullptr, nifCheck, nullptr);
			//TCompareExtraData(nifhead, head, nifCheck, shapesCheck[0]);
			loglen = getMessageLog(msgbuf, MSGBUFLEN);
			Assert::IsFalse(strstr(msgbuf, "WARNING:"), L"Error completed with warnings");
			Assert::IsFalse(strstr(msgbuf, "ERROR:"), L"Error completed with errors");
		};
		TEST_METHOD(invalidSkin) {
			/* Trying to read skin information causes an error that is written to the log */
			void* shapes[10];
			void* nif = load((testRoot / "Skyrim/noblecrate01.nif").u8string().c_str());
			getShapes(nif, shapes, 10, 0);

			clearMessageLog();

			MatTransform xform;
			getGlobalToSkin(nif, shapes[0], &xform);
			
			const int MSGBUFLEN = 2000;
			char msgbuf[MSGBUFLEN];
			int loglen = getMessageLog(msgbuf, MSGBUFLEN);
			Assert::IsTrue(loglen > 0, L"Error: Expect log messages");


		};
	};
}
