/*
* Wrapper layer to provide a DLL interface for Nifly.

  Data passed through simple buffers to prevent problems calling from different languages.
  
  Copyright (c) 2021, by Bad Dog
*/
#include "pch.h" // use stdafx.h in Visual Studio 2017 and earlier
#include <iostream>
#include <filesystem>
#include <string>
#include <algorithm>
#include "niffile.hpp"
#include "NiflyFunctions.hpp"
#include "NiflyWrapper.hpp"

using namespace nifly;

void XformToBuffer(float* xform, MatTransform& tmp) {
    int i = 0;
    xform[i++] = tmp.translation.x;
    xform[i++] = tmp.translation.y;
    xform[i++] = tmp.translation.z;
    xform[i++] = tmp.rotation[0][0];
    xform[i++] = tmp.rotation[0][1];
    xform[i++] = tmp.rotation[0][2];
    xform[i++] = tmp.rotation[1][0];
    xform[i++] = tmp.rotation[1][1];
    xform[i++] = tmp.rotation[1][2];
    xform[i++] = tmp.rotation[2][0];
    xform[i++] = tmp.rotation[2][1];
    xform[i++] = tmp.rotation[2][2];
    xform[i++] = tmp.scale;
}
NIFLY_API void* nifCreate() {
    return new NifFile;
}

NIFLY_API void* load(const char* filename) {
    NifFile* nif = new NifFile();
    int errval = nif->Load(std::filesystem::path(filename));

    if (errval == 0) return nif;

    if (errval == 1) LogWrite("File does not exist or is not a nif");
    if (errval == 2) LogWrite("File is not a nif format we can read");

    return nullptr;
}

NIFLY_API void* getRoot(void* f) {
    NifFile* theNif = static_cast<NifFile*>(f);
    return theNif->GetRootNode();
}

NIFLY_API int getRootName(void* f, char* buf, int len) {
    NifFile* theNif = static_cast<NifFile*>(f);
    nifly::NiNode* root = theNif->GetRootNode();
    std::string name = root->name.get();
    int copylen = std::min((int)len - 1, (int)name.length());
    name.copy(buf, copylen, 0);
    buf[copylen] = '\0';
    return int(name.length());
}

NIFLY_API int getGameName(void* f, char* buf, int len) {
    NifFile* theNif = static_cast<NifFile*>(f);
    NiHeader hdr = theNif->GetHeader();
    NiVersion vers = hdr.GetVersion();
    std::string name = "";
    if (vers.IsFO3()) { name = "FO3"; }
    else if (vers.IsSK()) { name = "SKYRIM"; }
    else if (vers.IsSSE()) { name = "SKYRIMSE"; }
    else if (vers.IsFO4()) { name = "FO4"; }
    else if (vers.IsFO76()) { name = "FO76"; }

    int copylen = std::min((int)len - 1, (int)name.length());
    name.copy(buf, copylen, 0);
    buf[copylen] = '\0';
    return int(name.length());
}

int NIFLY_API getAllShapeNames(void* f, char* buf, int len) {
    NifFile* theNif = static_cast<NifFile*>(f);
    std::vector<std::string> names = theNif->GetShapeNames();
    std::string s = "";
    for (auto& sn : names) {
        if (s.length() > 0) s += "\n";
        s += sn;
    }
    int copylen = std::min((int)len - 1, (int)s.length());
    s.copy(buf, copylen, 0);
    buf[copylen] = '\0';

    return int(names.size());
}

NIFLY_API int getShapeName(void* theShape, char* buf, int len) {
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::string name = shape->name.get();
    int copylen = std::min((int)len - 1, (int)name.length());
    name.copy(buf, copylen, 0);
    buf[copylen] = '\0';
    return int(name.length());
}

int NIFLY_API loadShapeNames(const char* filename, char* buf, int len) {
    NifFile* theNif = new NifFile(std::filesystem::path(filename));
    std::vector<std::string> names = theNif->GetShapeNames();
    std::string s = "";
    for (auto& sn : names) {
        if (s.length() > 0) s += "\n";
        s += sn;
    }
    int copylen = std::min((int)len - 1, (int)s.length());
    s.copy(buf, copylen, 0);
    buf[copylen] = '\0';

    theNif->Clear();
    delete theNif;
    return int(names.size());
}
int NIFLY_API getShapes(void* f, void** buf, int len, int start) {
    NifFile* theNif = static_cast<NifFile*>(f);
    std::vector<nifly::NiShape*> shapes = theNif->GetShapes();
    for (int i=start, j=0; (i < start+len) && (i < shapes.size()); i++)
        buf[j++] = shapes[i];
    return int(shapes.size());
}
NIFLY_API int getVertsForShape(void* theNif, void* theShape, float* buf, int len, int start)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<nifly::Vector3> verts;
    nif->GetVertsForShape(shape, verts);
    for (int i = start, j = 0; i < start + len && i < verts.size(); i++) {
        buf[j++] = verts.at(i).x;
        buf[j++] = verts.at(i).y;
        buf[j++] = verts.at(i).z;
    }
    return int(verts.size());
}
NIFLY_API int getNormalsForShape(void* theNif, void* theShape, float* buf, int len, int start)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const std::vector<nifly::Vector3>* norms;
    norms = nif->GetNormalsForShape(shape);
    if (norms) {
        for (int i = start, j = 0; i < start + len && i < norms->size(); i++) {
            buf[j++] = norms->at(i).x;
            buf[j++] = norms->at(i).y;
            buf[j++] = norms->at(i).z;
        }
        return int(norms->size());
    }
    else
        return 0;
}
//NIFLY_API int getRawVertsForShape(void* theNif, void* theShape, float* buf, int len, int start)
//{
//    NifFile* nif = static_cast<NifFile*>(theNif);
//    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
//    const std::vector<nifly::Vector3>* verts = nif->GetRawVertsForShape(shape);
//    for (int i = start, j = 0; i < start + len && i < verts->size(); i++) {
//        buf[j++] = verts->at(i).x;
//        buf[j++] = verts->at(i).y;
//        buf[j++] = verts->at(i).z;
//    }
//    return verts->size();
//}
NIFLY_API int getTriangles(void* theNif, void* theShape, uint16_t* buf, int len, int start)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<nifly::Triangle> shapeTris;
    shape->GetTriangles(shapeTris);
    for (int i=start, j=0; i < start+len && i < shapeTris.size(); i++) {
        buf[j++] = shapeTris.at(i).p1;
        buf[j++] = shapeTris.at(i).p2;
        buf[j++] = shapeTris.at(i).p3;
    }
    return int(shapeTris.size());
}
NIFLY_API bool getShapeGlobalToSkin(void* nifRef, void* shapeRef, float* xform) {
    NifFile* nif = static_cast<NifFile*>(nifRef);
    MatTransform tmp;
    bool skinInstFound = nif->GetShapeTransformGlobalToSkin(static_cast<NiShape*>(shapeRef), tmp);
    if (skinInstFound) XformToBuffer(xform, tmp);
    return skinInstFound;
}
NIFLY_API void getGlobalToSkin(void* nifRef, void* shapeRef, void* xform) {
    AnimInfo skin;
    skin.LoadFromNif(static_cast<NifFile*>(nifRef), static_cast<NiShape*>(shapeRef));
    GetGlobalToSkin(&skin, static_cast<NiShape*>(shapeRef), 
        static_cast<MatTransform*>(xform));
}
NIFLY_API int hasSkinInstance(void* shapeRef) {
    return int(static_cast<NiShape*>(shapeRef)->HasSkinInstance()? 1: 0);
}
NIFLY_API bool getShapeSkinToBone(void* nifPtr, void* shapePtr, const  char* boneName, float* buf) {
    MatTransform xf;
    bool hasXform = static_cast<NifFile*>(nifPtr)->GetShapeTransformSkinToBone(
        static_cast<NiShape*>(shapePtr),
        std::string(boneName),
        xf);
    if (hasXform) XformToBuffer(buf, xf);
    return hasXform;
}
NIFLY_API void getTransform(void* theShape, float* buf) {
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    nifly::MatTransform xf = shape->GetTransformToParent();
    XformToBuffer(buf, xf);
}
NIFLY_API void getNodeTransform(void* theNode, float* buf) {
    nifly::NiNode* node = static_cast<nifly::NiNode*>(theNode);
    nifly::MatTransform xf;
    xf = node->GetTransformToParent();
    XformToBuffer(buf, xf);
}
NIFLY_API int getUVs(void* theNif, void* theShape, float* buf, int len, int start)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const std::vector<nifly::Vector2>* uv = nif->GetUvsForShape(shape);
    for (int i = start, j = 0; i < start + len && i < uv->size(); i++) {
        buf[j++] = uv->at(i).u;
        buf[j++] = uv->at(i).v;
    }
    return int(uv->size());
}
NIFLY_API int getNodeCount(void* theNif)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    return int(nif->GetNodes().size());
}
NIFLY_API void getNodes(void* theNif, void** buf)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    std::vector<nifly::NiNode*> nodes = nif->GetNodes();
    for (int i = 0; i < nodes.size(); i++)
        buf[i] = nodes[i];
}
NIFLY_API int getNodeName(void* node, char* buf, int buflen) {
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    std::string name = theNode->name.get();
    int copylen = std::min((int)buflen - 1, (int)name.length());
    name.copy(buf, copylen, 0);
    buf[name.length()] = '\0';
    return int(name.length());
}
NIFLY_API void* getNodeParent(void* theNif, void* node) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    return nif->GetParentNode(theNode);
}
NIFLY_API void getNodeXformToGlobal(void* anim, const char* boneName, float* xformBuf) {
    // Get the transform from the nif if there, from the reference skeleton if not.
    // Requires an AnimInfo because this is a skinned nif, after all. It's creating the 
    // AnimInfo that loads the skeleton.
    NifFile* nif = static_cast<AnimInfo*>(anim)->GetRefNif();
    MatTransform mat;

    for (int i = 0; i < 13; i++) { xformBuf[i] = 0.0f; }
    if (nif->GetNodeTransformToGlobal(boneName, mat)) {
        XformToBuffer(xformBuf, mat);
    }
    else {
        AnimSkeleton* skel = &AnimSkeleton::getInstance();
        AnimBone* thisBone = skel->GetBonePtr(boneName);
        if (thisBone) {
            XformToBuffer(xformBuf, thisBone->xformToGlobal);
        }
    }
}
NIFLY_API void getBoneSkinToBoneXform(void* animPtr, const char* shapeName,
    const char* boneName, float* xform) {
    AnimInfo* anim = static_cast<AnimInfo*>(animPtr);
    int boneIdx = anim->GetShapeBoneIndex(shapeName, boneName);
    AnimSkin* skin = &anim->shapeSkinning[boneName];
    XformToBuffer(xform, skin->boneWeights[boneIdx].xformSkinToBone);
}
NIFLY_API void destroy(void* f) {
    NifFile* theNif = static_cast<NifFile*>(f);
    theNif->Clear();
    delete theNif;
}
NIFLY_API int getShapeBoneCount(void* theNif, void* theShape) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<int> bonelist;
    return nif->GetShapeBoneIDList(shape, bonelist);
}
NIFLY_API int getShapeBoneIDs(void* theNif, void* theShape, int* buf, int bufsize) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<int> bonelist;
    nif->GetShapeBoneIDList(shape, bonelist);
    for (int i = 0; i < bufsize && i < bonelist.size(); i++)
        buf[i] = bonelist[i];
    return int(bonelist.size());
}
NIFLY_API int getShapeBoneNames(void* theNif, void* theShape, char* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<std::string> names;
    nif->GetShapeBoneList(shape, names);

    std::string s = "";
    for (auto& sn : names) {
        if (s.length() > 0) s += "\n";
        s += sn;
    }
    int copylen = std::min((int)buflen - 1, (int)s.length());
    s.copy(buf, copylen, 0);
    buf[copylen] = '\0';

    return(int(s.length()));
}
NIFLY_API int getShapeBoneWeightsCount(void* theNif, void* theShape, int boneID) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);

    std::unordered_map<uint16_t, float> boneWeights;
    return nif->GetShapeBoneWeights(shape, boneID, boneWeights);
}

NIFLY_API int getShapeBoneWeights(void* theNif, void* theShape, int boneID,
                                  struct VertexWeightPair* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);

    std::vector<std::string> names;
    nif->GetShapeBoneList(shape, names);
    
    std::vector<int> bonelist;
    nif->GetShapeBoneIDList(shape, bonelist);

    std::unordered_map<uint16_t, float> boneWeights;
    int numWeights = nif->GetShapeBoneWeights(shape, boneID, boneWeights);

    int j = 0;
    for (const auto& [key, value] : boneWeights) {
        buf[j].vertex = key;
        buf[j++].weight = value;
        if (j >= buflen) break;
    }

    return numWeights;
}

int NIFLY_API getVersion() {
    return 110;
};

/* ******************** NIF CREATION *************************************** */

//enum TargetGame {FO3, FONV, SKYRIM, FO4, SKYRIMSE, FO4VR, SKYRIMVR, FO76, UNKNOWN_TARGET};

enum TargetGame StrToTargetGame(const char* gameName) {
    if (strcmp(gameName, "FO3") == 0) { return TargetGame::FO3; }
    else if (strcmp(gameName, "SKYRIM") == 0) { return TargetGame::SKYRIM; }
    else if (strcmp(gameName, "FO4") == 0) { return TargetGame::FO4; }
    else if (strcmp(gameName, "FO4VR") == 0) { return TargetGame::FO4VR; }
    else if (strcmp(gameName, "SKYRIMSE") == 0) { return TargetGame::SKYRIMSE; }
    else if (strcmp(gameName, "SKYRIMVR") == 0) { return TargetGame::SKYRIMVR; }
    else if (strcmp(gameName, "FO76") == 0) { return TargetGame::FO76; }
    else { return TargetGame::SKYRIM; }
}

void SetNifVersionWrap(NifFile* nif, enum TargetGame targ) {
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
    //std::string nm = root->GetName();
    //root->SetName("Scene Root");
}

NIFLY_API void* createNif(const char* targetGameName) {
    TargetGame targetGame = StrToTargetGame(targetGameName);
    NifFile* workNif = new NifFile();
    SetNifVersionWrap(workNif, targetGame);
    return workNif;
}

NIFLY_API void* createNifShapeFromData(void* parentNif,
    const char* shapeName,
    const float* verts, int verts_len,
    const uint16_t* tris, int tris_len,
    const float* uv_points, int uv_len,
    const float* norms, int norms_len) {

    NifFile *nif = static_cast<NifFile*>(parentNif);
    std::vector<Vector3> v;
    std::vector<Triangle> t;
    std::vector<Vector2> uv;
    std::vector<Vector3> n;

    for (int i = 0; i < verts_len;) {
        Vector3 thisv;
        thisv[0] = verts[i++];
        thisv[1] = verts[i++];
        thisv[2] = verts[i++];
        v.push_back(thisv);
    }
    for (int i = 0; i < tris_len;) {
        Triangle thist;
        thist[0] = tris[i++];
        thist[1] = tris[i++];
        thist[2] = tris[i++];
        t.push_back(thist);
    }
    for (int i = 0; i < uv_len;) {
        Vector2 thisuv;
        thisuv.u = uv_points[i++];
        thisuv.v = uv_points[i++];
        uv.push_back(thisuv);
    }
    for (int i = 0; i < norms_len;) {
        Vector3 thisnorm;
        thisnorm[0] = norms[i++];
        thisnorm[1] = norms[i++];
        thisnorm[2] = norms[i++];
        n.push_back(thisnorm);
    }

    return nif->CreateShapeFromData(shapeName, &v, &t, &uv, &n);
}

NIFLY_API void* createSkinForNif(void* nifPtr, const char* gameName) {
    NifFile* nif = static_cast<NifFile*>(nifPtr);
    return CreateSkinForNif(nif, StrToTargetGame(gameName));
}

NIFLY_API void setGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr) {
    if (static_cast<NiShape*>(shapePtr)->HasSkinInstance()) {
        SetShapeGlobalToSkinXform(static_cast<AnimInfo*>(animPtr),
            static_cast<NiShape*>(shapePtr),
            *static_cast<MatTransform*>(gtsXformPtr));
    }
    else {
        SetGlobalToSkinXform(
            static_cast<AnimInfo*>(animPtr),
            static_cast<NiShape*>(shapePtr),
            *static_cast<MatTransform*>(gtsXformPtr));
    }
}

NIFLY_API void addBoneToShape(void* anim, void* theShape, const char* boneName, void* xformPtr) {
    AddBoneToShape(static_cast<AnimInfo*>(anim), static_cast<NiShape*>(theShape), 
        boneName, static_cast<MatTransform*>(xformPtr));
}

NIFLY_API void setShapeGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr) {
    SetShapeGlobalToSkinXform(static_cast<AnimInfo*>(animPtr), 
                              static_cast<NiShape*>(shapePtr), 
                              *static_cast<MatTransform*>(gtsXformPtr));
}

NIFLY_API void setShapeWeights(void* anim, void* theShape, const char* boneName,
    VertexWeightPair* vertWeights, int vertWeightLen, MatTransform* skinToBoneXform) {
    AnimWeight aw;
    for (int i = 0; i < vertWeightLen; i++) {
        aw.weights[vertWeights[i].vertex] = vertWeights[i].weight;
    };
    SetShapeWeights(static_cast<AnimInfo*>(anim), static_cast<NiShape*>(theShape), boneName, aw);
}

NIFLY_API int saveSkinnedNif(void* anim, const char* filepath) {
    return SaveSkinnedNif(static_cast<AnimInfo*>(anim), std::string(filepath));
}

NIFLY_API void setTransform(void* theShape, float* buf) {
    NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    MatTransform xf;
    xf.translation.x = buf[0];
    xf.translation.y = buf[1];
    xf.translation.z = buf[2];
    xf.scale = buf[12];
    shape->SetTransformToParent(xf);
}

NIFLY_API int addNode(void* f, const char* name, const MatTransform* xf, void* parent) {
    NifFile* nif = static_cast<NifFile*>(f);
    NiNode* parentNode= static_cast<NiNode*>(parent);
    NiNode* theNode = nif->AddNode(name, *xf, parentNode);
    return nif->GetBlockID(theNode);
}

NIFLY_API void skinShape(void* nif, void* shapeRef)
{
    static_cast<NifFile*>(nif)->CreateSkinning(static_cast<nifly::NiShape*>(shapeRef));
}

NIFLY_API void setShapeVertWeights(void* theFile, void* theShape, 
        int vertIdx, const uint8_t* vertex_bones, const float* vertex_weights) {
    NifFile* nif = static_cast<NifFile*>(theFile);
    NiShape* shape = static_cast<nifly::NiShape*>(theShape);

    std::vector<uint8_t> boneids;
    std::vector<float> weights;
    for (int i = 0; i < 4; i++) {
        if (vertex_weights[i] > 0) {
            boneids.push_back(vertex_bones[i]);
            weights.push_back(vertex_weights[i]);
        };
    };
    nif->SetShapeVertWeights(shape->name.get(), vertIdx, boneids, weights);
}
NIFLY_API void setShapeBoneWeights(void* theFile, void* theShape, 
    int boneIdx, VertexWeightPair* weights, int weightsLen)
{
    NifFile* nif = static_cast<NifFile*>(theFile);
    NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::unordered_map<uint16_t, float> weight_map;
    for (int i = 0; i < weightsLen; i++) {
        weight_map[weights[i].vertex] = weights[i].weight;
    }
    nif->SetShapeBoneWeights(shape->name.get(), boneIdx, weight_map);
}
NIFLY_API void setShapeBoneIDList(void* theFile, void* shapeRef, int* boneIDList, int listLen)
{
    NifFile* nif = static_cast<NifFile*>(theFile);
    NiShape* shape = static_cast<nifly::NiShape*>(shapeRef);
    std::vector<int> bids;
    for (int i = 0; i < listLen; i++) {
        bids.push_back(boneIDList[i]);
    }
    nif->SetShapeBoneIDList(shape, bids);
}

NIFLY_API int saveNif(void* the_nif, const char* filename) {
    NifFile* nif = static_cast<NifFile*>(the_nif);
    return nif->Save(std::filesystem::path(filename));
}

NIFLY_API int segmentCount(void* nifref, void* shaperef) {
    /*
        Return count of segments associated with the shape.
        If not FO4 nif or no segments returns 0
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NifSegmentationInfo segInfo;
    std::vector<int> triParts;
    if (nif->GetShapeSegments(shape, segInfo, triParts))
        return int(segInfo.segs.size());
    else
        return 0;
}
NIFLY_API int getSegmentFile(void* nifref, void* shaperef, char* buf, int buflen) {
    /*
        Return segment file associated with the shape
        If not FO4 nif or no segments returns ''
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NifSegmentationInfo segInfo;
    std::vector<int> triParts;
    if (nif->GetShapeSegments(shape, segInfo, triParts)) {
        if (buflen > 0) {
            int copylen = std::min((int)buflen - 1, (int)segInfo.ssfFile.size());
            segInfo.ssfFile.copy(buf, copylen, 0);
            buf[copylen] = '\0';
        }
        return int(segInfo.ssfFile.size());
    }
    else {
        if (buflen > 0) buf[0] = '\0';
        return 0;
    }
}
NIFLY_API int getSegments(void* nifref, void* shaperef, int* segments, int segLen) {
    /*
        Return segments associated with a shape. Only for FO4-style nifs.
        segments -> (int ID, int count_of_subsegments)...
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NifSegmentationInfo segInfo;
    std::vector<int> indices;

    if (nif->GetShapeSegments(shape, segInfo, indices)) {
        for (int i = 0, j = 0; i < segLen * 2 && j < int(segInfo.segs.size()); j++) {
            segments[i++] = segInfo.segs[j].partID;
            segments[i++] = int(segInfo.segs[j].subs.size());
        }
        return int(segInfo.segs.size());
    }
    return 0;
}
NIFLY_API int getSubsegments(void* nifref, void* shaperef, int segID, int* segments, int segLen) {
    /*
        Return subsegments associated with a shape. Only for FO4-style nifs.
        segments -> (int ID, userSlotID, material)...
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NifSegmentationInfo segInfo;
    std::vector<int> indices;

    if (nif->GetShapeSegments(shape, segInfo, indices)) {
        for (auto& s: segInfo.segs) {
            if (s.partID == segID) {
                for (int i = 0, j = 0; i < segLen * 3 && j < int(s.subs.size()); j++) {
                    segments[i++] = s.subs[j].partID;
                    segments[i++] = s.subs[j].userSlotID;
                    segments[i++] = s.subs[j].material;
                }
                return int(s.subs.size());
            }
        }
        return 0;
    }
    return 0;
}

NIFLY_API int getPartitions(void* nifref, void* shaperef, uint16_t* partitions, int partLen) {
/*
    Return a list of partitions associated with the shape. Only for skyrim-style nifs.
    partitions = (uint16 flags, uint16 partID)... where partID is the body part ID
*/
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NiVector<BSDismemberSkinInstance::PartitionInfo> partInfos;
    NifSegmentationInfo segInfo;
    std::vector<int> indices;

    GetPartitions(nif, shape, partInfos, indices);

    for (int i = 0, j = 0; i < partLen * 2 && j < int(partInfos.size()); j++) {
        partitions[i++] = partInfos[j].flags;
        partitions[i++] = partInfos[j].partID;
    }
    return int(partInfos.size());
}

NIFLY_API int getPartitionTris(void* nifref, void* shaperef, uint16_t* tris, int triLen) {
/* 
    Return a list of segment indices matching 1-1 with the shape's triangles.
    Used for both skyrim and fo4-style nifs
*/
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NiVector<BSDismemberSkinInstance::PartitionInfo> partInfos;
    std::vector<int> indices;

    GetPartitions(nif, shape, partInfos, indices);

    for (int i = 0; i < triLen && i < int(indices.size()); i++) {
        tris[i] = indices[i];
    }
    return int(indices.size());
}

NIFLY_API void setPartitions(void* nifref, void* shaperef, 
    uint16_t* partData, int partDataLen, 
    uint16_t* tris, int triLen) 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NiVector<BSDismemberSkinInstance::PartitionInfo> partInfos;
    std::vector<int> triParts;

    for (int i = 0; i < partDataLen; i++) {
        BSDismemberSkinInstance::PartitionInfo p;
        p.partID = partData[i];
        p.flags = PF_EDITOR_VISIBLE;
        partInfos.push_back(p);
    }

    for (int i = 0; i < triLen; i++) {
        triParts.push_back(tris[i]);
    }

    nif->SetShapePartitions(shape, partInfos, triParts, true);
}