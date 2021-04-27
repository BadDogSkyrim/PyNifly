// TestNifly.cpp : 
// Not a real test suite. Just handy for calling through the wrapper when it's misbehaving.
//

#include <iostream>
#include <string>
#include <unordered_map>
#include "Object3d.hpp"
#include "NiflyWrapper.hpp"
#include "TestNifly.h"

using namespace nifly;

#define TEST_FILE "D:/OneDrive/Dev/PyNifly/PyNifly/tests/Skyrim/test.nif"

void Test1() {
    void* shapes[10];
    void* nif;
    float g2shape[13];
    float g2skin[13];
    bool hasG2skin;

    nif = load("D:/OneDrive/Dev/PyNifly/PyNifly/tests/FO4/BTMaleBody.nif");
    getShapes(nif, shapes, 10, 0);
    getGlobalToSkin(nif, shapes[0], g2shape);
    hasG2skin = getShapeGlobalToSkin(nif, shapes[0], g2skin);

    nif = load("D:/OneDrive/Dev/PyNifly/PyNifly/tests/Skyrim/malehead.nif");
    getShapes(nif, shapes, 10, 0);
    getGlobalToSkin(nif, shapes[0], g2shape);
    hasG2skin = getShapeGlobalToSkin(nif, shapes[0], g2skin);
}

int main()
{
    Test1();

    /* print("### Can create tetrahedron with bone weights (Skyrim)"); */
    const int verts1_len = 6;
    float verts1[] = {
        0.0f, 1.0f, -1.0f,
        0.866f, -0.5f, -1.0f,
        -0.866f, -0.5f, -1.0f,
        0.0f, 0.0f, 1.0f,
        0.0f, 0.0f, 1.0f,
        0.0f, 0.0f, 1.0f };
    float norms1[] = {
        0.0f, 0.9219f, -0.3873f,
        0.7984f, -0.461f, -0.3873f,
        -0.7984f, -0.461f, -0.3873f,
        -0.8401f, 0.4851f, 0.2425f,
        0.8401f, 0.4851f, 0.2425f,
        0.0f, -0.9701f, 0.2425f };
    const int tris1_len = 4;
    int tris1[] = { 0, 4, 1, 0, 1, 2, 1, 5, 2, 2, 3, 0 };
    float uvs1[] = {
        0.46f, 0.30f,
        0.80f, 0.5f,
        0.46f, 0.69f,
        0.0f, 0.5f,
        0.86f, 0.0f,
        0.86f, 1.0f };
    float weights1[][4] = {
        {0.0f,   0.0974f, 0.0f,    0.9026f},
        {0.0f,   0.0f,    0.0715f, 0.9285f},
        {0.0f,   0.00f,   0.0f,    1.0000f },
        {0.9f,   0.0f,    0.0f,    0.1f },
        {0.9f,   0.0f,    0.0f,    0.1f },
        {0.9f,   0.0f,    0.0f,    0.1f } };
     const int bone_count = 4;
     VertexWeightPair weights_by_bone[bone_count][verts1_len] = {
        {{3, 0.9f}, {4, 0.9f}, {5, 0.9f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f} },
        {{0, 0.0974f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f}},
        {{1, 0.0715f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f}, {0, 0.0f}},
        {{0, 0.9026f}, {1, 0.9285f}, {2, 1.0f}, {3, 0.1f}, {3, 0.1f}, {3, 0.1f}}
    };
    int weights_by_bone_len[bone_count] = { 3, 1, 1, 6 };
    const char* group_names[] = { "Bone", "Bone.001", "Bone.002", "Bone.003" };
    const char* bone_names[] = { 
        "NPC L Calf [LClf]", 
        "NPC Pelvis [Pelv]", 
        "NPC Spine2 [Spn2]", 
        "NPC R Hand [RHnd]" };
    int result;
    //arma_bones = { "Bone": (0,0,0.5), "Bone.001" : (-0.009,1.016,-0.988),
    //                "Bone.002" : (0.858,-0.48,-0.96), "Bone.003" : (-0.83,-0.559,-0.955) }
    //export_names = { "Bone": ("NPC L Calf [LClf]", None),
    //                "Bone.001" : ("BONE2", None),
    //                "Bone.002" : ("BONE3", None),
    //                "Bone.003" : ("BONE4", None) }

    const char* filename4 = "D:/OneDrive/Dev/PyNifly/PyNifly/tests/Out/testnew04.nif";
    void* newf4 = createNif("SKYRIM");
    void* skin = createSkinForNif(newf4, "SKYRIM");
    void* shape4 = createNifShapeFromData(newf4, "WeightedTetra", 
        verts1, verts1_len*3, tris1, tris1_len*3, uvs1, verts1_len*2, norms1, verts1_len*3);
    skinShape(newf4, shape4);
    
    for (const char* b : bone_names) {
        addBoneToShape(skin, shape4);
    }

    for (int i = 0; i < bone_count; i++) {
        MatTransform stbXform;
        setShapeWeights(skin, shape4, bone_names[i], weights_by_bone[i],
            weights_by_bone_len[i], &stbXform);
    };

    result = saveSkinnedNif(skin, filename4);

    /* create tetrahedron with bone weights (Skyrim)") */
    const int verts_count = 6;
    float verts[] = {
         0.0f,    1.0f, -1.0f,
         0.866f, -0.5f, -1.0f,
        -0.866f, -0.5f, -1.0f,
         0.0f,    0.0f,  1.0f,
         0.0f,    0.0f,  1.0f,
         0.0f,    0.0f,  1.0f };
    float norms[] = {
        0.0f, 0.9219f, -0.3873f,
        0.7984f, -0.461f, -0.3873f,
        -0.7984f, -0.461f, -0.3873f,
        -0.8401f, 0.4851f, 0.2425f,
        0.8401f, 0.4851f, 0.2425f,
        0.0f, -0.9701f, 0.2425f };
    const int tris_count = 4;
    int tris[] = {
        0, 4, 1,
        0, 1, 2,
        1, 5, 2,
        2, 3, 0 };
    float uvs[] = {
        0.46f, 0.30f,
        0.80f, 0.5f,
        0.46f, 0.69f,
        0.0f, 0.5f,
        0.86f, 0.0f,
        0.86f, 1.0f };
    float weights[] = {
        1, 0.0974f, 3, 0.9026f, 0, 0.0, 0, 0.0,
        2, 0.0715f, 3, 0.9285f, 0, 0.0, 0, 0.0,
        0, 0.0000, 1, 0.0000, 2, 0.0000, 3, 1.0000f,
        0, 0.9993f, 3, 0.0007f, 0, 0.0, 0, 0.0,
        0, 0.9993f, 3, 0.0007f, 0, 0.0, 0, 0.0,
        0, 0.9993f, 3, 0.0007f, 0, 0.0, 0, 0.0
        };
    const int bones_count = 4;
    const char *bones[] = { "Bone", "Bone.001", "Bone.002", "Bone.003" };

    float arma_bones[] = {
        0.0f, 0.0f, 0.5f,
        -0.009f, 1.016f, -0.988f,
        0.858f, -0.48f, -0.96f,
        -0.83f, -0.559f, -0.955f };

    const float vertex_weights[][4] = {
        {0.25f, 0.75f, 0.0f, 0.0f},
        {0.6f, 0.3f, 0.1f, 0.0f},
        {1.0f, 0.0f, 0.0f, 0.0f},
        {0.3f, 0.3f, 0.4f, 0.0f},
        {0.3f, 0.3f, 0.4f, 0.0f},
        {0.3f, 0.3f, 0.4f, 0.0f},
    };
    MatTransform boneXform;
    int boneIDs[bones_count];
    const MatTransform identityXform;
    void* rootNode;
    void* shape;
    VertexWeightPair vw[bones_count * verts_count];

    //------------------------------------------------------
    void* nif = createNif("SKYRIM");
    rootNode = getRoot(nif);

    for (int i = 0; i < bones_count; i++) {
        /* want bone xform to global CS here -- different for each bone */
        //MatTransform bone2global;
        boneXform.translation.x = arma_bones[i * 3];
        boneXform.translation.y = arma_bones[i * 3 + 1];
        boneXform.translation.z = arma_bones[i * 3 + 2];
        boneXform.scale = 1;
        boneIDs[i] = addNode(nif, bones[i], &boneXform, rootNode);
    }
    shape = createNifShapeFromData(nif, "Tetra",
        verts, verts_count * 3, 
        tris, tris_count * 3, 
        uvs, verts_count * 2, 
        norms, verts_count*3);

    skinShape(nif, shape);
    setShapeBoneIDList(nif, shape, boneIDs, bones_count);
    for (int bone_index = 0; bone_index < bones_count; bone_index++) {
        int vw_index = 0;
        for (int vertex_index = 0; vertex_index < verts_count; vertex_index++) {
            if (vertex_weights[vertex_index][bone_index] > 0) {
                vw[vw_index].vertex = vertex_index;
                vw[vw_index++].weight = vertex_weights[vertex_index][bone_index];
            }
        }
        setShapeBoneWeights(nif, shape, bone_index, vw, vw_index);
    }

    saveNif(nif, "testWeightsSkyrim.nif");

    //------------------------------------------------------
    nif = createNif("FO4");
    rootNode = getRoot(nif);

    for (int i = 0; i < bones_count; i++) {
        /* want bone xform to global CS here -- different for each bone */
        //MatTransform bone2global;
        boneXform.translation.x = arma_bones[i * 3];
        boneXform.translation.y = arma_bones[i * 3 + 1];
        boneXform.translation.z = arma_bones[i * 3 + 2];
        boneXform.scale = 1;
        boneIDs[i] = addNode(nif, bones[i], &boneXform, rootNode);
    }
    shape = createNifShapeFromData(nif, "Tetra",
        verts, verts_count * 3,
        tris, tris_count * 3,
        uvs, verts_count * 2,
        norms, verts_count * 3);

    skinShape(nif, shape);
    setShapeBoneIDList(nif, shape, boneIDs, bones_count);
    for (int vert_index = 0; vert_index < verts_count; vert_index++) {
        uint8_t thisBoneList[4];
        float thisWeightList[4];
        for (int i = 0; i < 4; i++) {
            thisBoneList[i] = i;
            thisWeightList[i] = vertex_weights[vert_index][i];
        }
        setShapeVertWeights(nif, shape, vert_index, thisBoneList, thisWeightList);
    }

    saveNif(nif, "testWeightsFO4.nif");


    //for (int this_bone = 0; this_bone < 3; this_bone++) {
    //    VertexWeightPair vw[20];
    //    int vwCount = 0;
    //    for (int vert_index = 0; vert_index < 6; vert_index++) {
    //        for (int i = 0; i < 4; i++) {
    //            if (vertex_bones[vert_index][i] == this_bone) {
    //                vw[vwCount].vertex = vert_index;
    //                vw[vwCount++].weight = vertex_weights[vert_index][i];
    //            }
    //        }
    //    }
    //    setShapeBoneWeights(nif, shape, this_bone, vw, vwCount);
    //}

    // saveNif(nif, "testfile.nif");

    //const char* shapename = "Cube";
    //float verts2[] = {1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, -1.0, -1.0, 1.0, 1.0, -1.0, 1.0, -1.0, -1.0, -1.0, 1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0, 1.0, -1.0, -1.0, 1.0 };
    //int tris2[] = { 4, 2, 0, 2, 7, 3, 6, 5, 8, 1, 9, 10, 0, 3, 1, 11, 1, 5, 4, 12, 2, 2, 13, 7, 6, 11, 5, 1, 3, 9, 0, 2, 3, 11, 0, 1 };
    //float uvs2[] = { 0.875, 0.5, 0.625, 0.75, 0.625, 0.5, 0.625, 0.75, 0.375, 1.0, 0.375, 0.75, 0.625, 0.0, 0.375, 0.25, 0.375, 0.0, 0.375, 0.5, 0.125, 0.75, 0.125, 0.5, 0.625, 0.5, 0.375, 0.75 };

    //nif = createNif("FO4");
    //void *newshape = createNifShapeFromData(nif, shapename,
    //    verts2, 14 * 3, tris2, 12 * 3, uvs2, 14 * 2, nullptr, 0);
    //float xfbuf[4] = { 1.0, 2.0, 3.0, 1.5 };
    //setTransform(newshape, xfbuf);
    //saveNif(nif, "testfile2.nif");

    //nifDestroy(f);
}

// Run program: Ctrl + F5 or Debug > Start Without Debugging menu
// Debug program: F5 or Debug > Start Debugging menu

// Tips for Getting Started: 
//   1. Use the Solution Explorer window to add/manage files
//   2. Use the Team Explorer window to connect to source control
//   3. Use the Output window to see build output and other messages
//   4. Use the Error List window to view errors
//   5. Go to Project > Add New Item to create new code files, or Project > Add Existing Item to add existing code files to the project
//   6. In the future, to open this project again, go to File > Open > Project and select the .sln file
