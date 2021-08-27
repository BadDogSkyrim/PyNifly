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

/* ************************** UTILITY ************************** */

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


/* ******************* NIF FILE MANAGEMENT ********************* */

enum TargetGame StrToTargetGame(const char* gameName) {
    if (strcmp(gameName, "FO3") == 0) { return TargetGame::FO3; }
    else if (strcmp(gameName, "FONV") == 0) { return TargetGame::FONV; }
    else if (strcmp(gameName, "SKYRIM") == 0) { return TargetGame::SKYRIM; }
    else if (strcmp(gameName, "FO4") == 0) { return TargetGame::FO4; }
    else if (strcmp(gameName, "FO4VR") == 0) { return TargetGame::FO4VR; }
    else if (strcmp(gameName, "SKYRIMSE") == 0) { return TargetGame::SKYRIMSE; }
    else if (strcmp(gameName, "SKYRIMVR") == 0) { return TargetGame::SKYRIMVR; }
    else if (strcmp(gameName, "FO76") == 0) { return TargetGame::FO76; }
    else { return TargetGame::SKYRIM; }
}

NIFLY_API void* load(const char8_t* filename) {
    NifFile* nif = new NifFile();
    int errval = nif->Load(std::filesystem::path(filename));

    if (errval == 0) return nif;

    if (errval == 1) niflydll::LogWrite("File does not exist or is not a nif");
    if (errval == 2) niflydll::LogWrite("File is not a nif format we can read");

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

int NIFLY_API getVersion() {
    return 110;
};

NIFLY_API void* nifCreate() {
    return new NifFile;
}

NIFLY_API void destroy(void* f) {
    NifFile* theNif = static_cast<NifFile*>(f);
    theNif->Clear();
    delete theNif;
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

NIFLY_API int saveNif(void* the_nif, const char8_t* filename) {
    NifFile* nif = static_cast<NifFile*>(the_nif);
    return nif->Save(std::filesystem::path(filename));
}


/* ********************* NODE HANDLING ********************* */

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

NIFLY_API int addNode(void* f, const char* name, const MatTransform* xf, void* parent) {
    NifFile* nif = static_cast<NifFile*>(f);
    NiNode* parentNode = static_cast<NiNode*>(parent);
    NiNode* theNode = nif->AddNode(name, *xf, parentNode);
    return nif->GetBlockID(theNode);
}


/* ********************* SHAPE MANAGEMENT ********************** */

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
    for (int i=start, j=0; (j < len) && (i < shapes.size()); i++)
        buf[j++] = shapes[i];
    return int(shapes.size());
}

NIFLY_API int getShapeBlockName(void* theShape, char* buf, int buflen) {
    NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const char* blockname = shape->GetBlockName();
    strncpy_s(buf, buflen, blockname, buflen);
    //strncpy(buf, blockname, buflen);
    buf[buflen - 1] = '\0';
    return int(strlen(blockname));
}

NIFLY_API int getVertsForShape(void* theNif, void* theShape, float* buf, int len, int start)
/*
    Get a shape's verts.
    buf, len = buffer that receives triples. len is length of buffer in floats.
    start = vertex index to start with.
    */
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<nifly::Vector3> verts;
    nif->GetVertsForShape(shape, verts);
    for (int i = start, j = 0; j < len && i < verts.size(); i++) {
        buf[j++] = verts.at(i).x;
        buf[j++] = verts.at(i).y;
        buf[j++] = verts.at(i).z;
    }
    return int(verts.size());
}

NIFLY_API int getNormalsForShape(void* theNif, void* theShape, float* buf, int len, int start)
/*
    Get a shape's normals.
    buf, len = buffer that receives triples. len is length of buffer in floats.
    start = normal index to start with.
    */
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const std::vector<nifly::Vector3>* norms;
    norms = nif->GetNormalsForShape(shape);
    if (norms) {
        for (int i = start, j = 0; j < len && i < norms->size(); i++) {
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
/*
    Get a shape's tris.
    buf, len = buffer that receives triples. len is length of buffer in uint16's.
    start = tri index to start with.
    */
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<nifly::Triangle> shapeTris;
    shape->GetTriangles(shapeTris);
    for (int i=start, j=0; j < len && i < shapeTris.size(); i++) {
        buf[j++] = shapeTris.at(i).p1;
        buf[j++] = shapeTris.at(i).p2;
        buf[j++] = shapeTris.at(i).p3;
    }
    return int(shapeTris.size());
}

NIFLY_API int getUVs(void* theNif, void* theShape, float* buf, int len, int start)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const std::vector<nifly::Vector2>* uv = nif->GetUvsForShape(shape);
    for (int i = start, j = 0; j < len && i < uv->size(); i++) {
        buf[j++] = uv->at(i).u;
        buf[j++] = uv->at(i).v;
    }
    return int(uv->size());
}

NIFLY_API void* createNifShapeFromData(void* parentNif,
    const char* shapeName,
    const float* verts,
    const float* uv_points,
    const float* norms,
    int vertCount,
    const uint16_t* tris, int triCount,
    uint16_t* optionsPtr = nullptr)
    /* Create nif shape from the given data
    * verts = (float x, float y float z), ... 
    * uv_points = (float u, float v), matching 1-1 with the verts list
    * norms = (float, float, float) matching 1-1 with the verts list. May be null.
    * vertCount = number of verts in verts list (and uv pairs and normals in those lists)
    * tris = (uint16, uiint16, uint16) indices into the vertex list
    * triCount = # of tris in the tris list (buffer is 3x as long)
    * optionsPtr == 1: Create SSE head part (so use BSDynamicTriShape)
    *            == 2: Create FO4 BSTriShape (default is BSSubindexTriShape)
    *            may be omitted
    */
{
    NifFile* nif = static_cast<NifFile*>(parentNif);
    std::vector<Vector3> v;
    std::vector<Triangle> t;
    std::vector<Vector2> uv;
    std::vector<Vector3> n;

    for (int i = 0; i < vertCount; i++) {
        Vector3 thisv;
        thisv[0] = verts[i*3];
        thisv[1] = verts[i*3 + 1];
        thisv[2] = verts[i*3 + 2];
        v.push_back(thisv);

        Vector2 thisuv;
        thisuv.u = uv_points[i*2];
        thisuv.v = uv_points[i*2+1];
        uv.push_back(thisuv);

        if (norms) {
            Vector3 thisnorm;
            thisnorm[0] = norms[i*3];
            thisnorm[1] = norms[i*3+1];
            thisnorm[2] = norms[i*3+2];
            n.push_back(thisnorm);
        };
    }
    for (int i = 0; i < triCount; i++) {
        Triangle thist;
        thist[0] = tris[i*3];
        thist[1] = tris[i*3+1];
        thist[2] = tris[i*3+2];
        t.push_back(thist);
    }

    if (optionsPtr)
        return PyniflyCreateShapeFromData(nif, shapeName, &v, &t, &uv, &n, *optionsPtr);
    else
        return nif->CreateShapeFromData(shapeName, &v, &t, &uv, &n);
}


/* ********************* TRANSFORMS AND SKINNING ********************* */

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
    return static_cast<NiShape*>(shapeRef)->HasSkinInstance()? 1: 0;
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

NIFLY_API void* createSkinForNif(void* nifPtr, const char* gameName) {
    NifFile* nif = static_cast<NifFile*>(nifPtr);
    return CreateSkinForNif(nif, StrToTargetGame(gameName));
}

NIFLY_API void skinShape(void* nif, void* shapeRef)
{
    static_cast<NifFile*>(nif)->CreateSkinning(static_cast<nifly::NiShape*>(shapeRef));
}

NIFLY_API int saveSkinnedNif(void* anim, const char8_t* filepath) {
    /*
    Save skinned nif
    options: 1 = save as head part, uses BSDynamicTriShape on SSE
    */
    return SaveSkinnedNif(static_cast<AnimInfo*>(anim), std::filesystem::path(filepath));
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

NIFLY_API void setShapeGlobalToSkinXform(void* animPtr, void* shapePtr, void* gtsXformPtr) {
    SetShapeGlobalToSkinXform(static_cast<AnimInfo*>(animPtr),
        static_cast<NiShape*>(shapePtr),
        *static_cast<MatTransform*>(gtsXformPtr));
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



/* ************************* BONES AND WEIGHTS ************************* */

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

NIFLY_API int getShapeBoneNames(void* theNif, void* theShape, char* buf, int buflen) 
// Returns a list of bone names the shape uses. List is separated by \n characters.
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<std::string> names;
    nif->GetShapeBoneList(shape, names);

    std::string s = "";
    for (auto& sn : names) {
        if (s.length() > 0) s += "\n";
        s += sn;
    }
    if (buf) {
        int copylen = std::min((int)buflen - 1, (int)s.length());
        s.copy(buf, copylen, 0);
        buf[copylen] = '\0';
    };

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

NIFLY_API void addBoneToShape(void* anim, void* theShape, const char* boneName, void* xformPtr) {
    AddBoneToShape(static_cast<AnimInfo*>(anim), static_cast<NiShape*>(theShape),
        boneName, static_cast<MatTransform*>(xformPtr));
}

NIFLY_API void setShapeWeights(void* anim, void* theShape, const char* boneName,
    VertexWeightPair* vertWeights, int vertWeightLen, MatTransform* skinToBoneXform) {
    AnimWeight aw;
    for (int i = 0; i < vertWeightLen; i++) {
        aw.weights[vertWeights[i].vertex] = vertWeights[i].weight;
    };
    SetShapeWeights(static_cast<AnimInfo*>(anim), static_cast<NiShape*>(theShape), boneName, aw);
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


/* ************************** SHADERS ************************** */

NIFLY_API int getShaderName(void* nifref, void* shaperef, char* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    strncpy_s(buf, buflen, shader->name.get().c_str(), buflen);
    buf[buflen - 1] = '\0';

    return int(shader->name.get().length());
};

NIFLY_API uint32_t getShaderFlags1(void* nifref, void* shaperef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);

    return (bssh ? bssh->shaderFlags1 : 0);
}

NIFLY_API uint32_t getShaderFlags2(void* nifref, void* shaperef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);

    return (bssh ? bssh->shaderFlags2 : 0);
}

NIFLY_API int getShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, char* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    std::string texture;

    nif->GetTextureSlot(shape, texture, slotIndex);

    if (buflen > 1) {
        memcpy(buf, texture.data(), std::min(texture.size(), static_cast<size_t>(buflen - 1)));
        buf[texture.size()] = '\0';
    }

    return static_cast<int>(texture.length());
}

NIFLY_API uint32_t getShaderType(void* nifref, void* shaperef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    return shader->GetShaderType();
};

NIFLY_API void getShaderAttrs(void* nifref, void* shaperef, struct BSLSPAttrs* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);;
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
    BSLightingShaderProperty* bslsp = dynamic_cast<BSLightingShaderProperty*>(shader);
    NiTexturingProperty* txtProp = nif->GetTexturingProperty(shape);

    FillMemory(buf, sizeof(BSLSPAttrs), 0);

    buf->Shader_Type = shader->GetShaderType();
    if (bssh) buf->Shader_Flags_1 = bssh->shaderFlags1;
    if (bssh) buf->Shader_Flags_2 = bssh->shaderFlags2;
    buf->UV_Offset_U = shader->GetUVOffset().u;
    buf->UV_Offset_V = shader->GetUVOffset().v;
    buf->UV_Scale_U = shader->GetUVScale().u;
    buf->UV_Scale_V = shader->GetUVScale().v;
    buf->Emissive_Color_R = shader->GetEmissiveColor().r;
    buf->Emissive_Color_G = shader->GetEmissiveColor().g;
    buf->Emissive_Color_B = shader->GetEmissiveColor().b;
    buf->Emissive_Color_A = shader->GetEmissiveColor().a;
    buf->Emissmive_Mult = shader->GetEmissiveMultiple();
    if (txtProp) {
        NiSyncVector<ShaderTexDesc>* txtdesc = &txtProp->shaderTex;
        //buf->Tex_Clamp_Mode = txtdesc->data.clampMode;
    };
    buf->Alpha = shader->GetAlpha();
    buf->Glossiness = shader->GetGlossiness();
    buf->Spec_Color_R = shader->GetSpecularColor().x;
    buf->Spec_Color_G = shader->GetSpecularColor().y;
    buf->Spec_Color_B = shader->GetSpecularColor().z;
    buf->Spec_Str = shader->GetSpecularStrength();
    if (bslsp) {
        buf->Refraction_Str = bslsp->refractionStrength;
        buf->Soft_Lighting = bslsp->softlighting;
        buf->Rim_Light_Power = bslsp->rimlightPower;
        buf->Skin_Tint_Alpha = bslsp->skinTintAlpha;
        buf->Skin_Tint_Color_R = bslsp->skinTintColor[0];
        buf->Skin_Tint_Color_G = bslsp->skinTintColor[1];
        buf->Skin_Tint_Color_B = bslsp->skinTintColor[2];
    };
};

NIFLY_API int getAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    if (shape->HasAlphaProperty()) {
        NiAlphaProperty* alph = nif->GetAlphaProperty(shape);
        bufptr->flags = alph->flags;
        bufptr->threshold = alph->threshold;
        return 1;
    }
    else
        return 0;
}

NIFLY_API void setAlphaProperty(void* nifref, void* shaperef, AlphaPropertyBuf* bufptr) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    auto alphaProp = std::make_unique<NiAlphaProperty>();
    alphaProp->flags = bufptr->flags;
    alphaProp->threshold = bufptr->threshold;
    nif->AssignAlphaProperty(shape, std::move(alphaProp));
}

NIFLY_API void setShaderName(void* nifref, void* shaperef, char* name) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    shader->name.get() = name;
};

NIFLY_API void setShaderType(void* nifref, void* shaperef, uint32_t shaderType) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    return shader->SetShaderType(shaderType);
};

NIFLY_API void setShaderFlags1(void* nifref, void* shaperef, uint32_t flags) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);

    if (bssh) bssh->shaderFlags1 = flags;
}

NIFLY_API void setShaderFlags2(void* nifref, void* shaperef, uint32_t flags) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);

    if (bssh) bssh->shaderFlags2 = flags;
}

NIFLY_API void setShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, const char* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    std::string texture = buf;

    nif->SetTextureSlot(shape, texture, slotIndex);
}

NIFLY_API void setShaderAttrs(void* nifref, void* shaperef, struct BSLSPAttrs* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);;
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
    BSLightingShaderProperty* bslsp = dynamic_cast<BSLightingShaderProperty*>(shader);
    NiTexturingProperty* txtProp = nif->GetTexturingProperty(shape);

    shader->SetShaderType(buf->Shader_Type);
    if (bssh) {
        bssh->shaderFlags1 = buf->Shader_Flags_1;
        bssh->shaderFlags2 = buf->Shader_Flags_2;
    };
    //shader->SetUVOffset( = buf->UV_Offset_U = ;
    //buf->UV_Offset_V = shader->GetUVOffset().v;
    //buf->UV_Scale_U = shader->GetUVScale().u;
    //buf->UV_Scale_V = shader->GetUVScale().v;
    Color4 col = Color4(buf->Emissive_Color_R, 
        buf->Emissive_Color_G, 
        buf->Emissive_Color_B, 
        buf->Emissive_Color_A);
    shader->SetEmissiveColor(col);
    shader->SetEmissiveMultiple(buf->Emissmive_Mult);
    if (txtProp) {
        NiSyncVector<ShaderTexDesc>* txtdesc = &txtProp->shaderTex;
        //txtdesc->data.clampMode = buf->Tex_Clamp_Mode;
    };
    //shader->SetAlpha(buf->Alpha);
    shader->SetGlossiness(buf->Glossiness);
    Vector3 specCol = Vector3(buf->Spec_Color_R, buf->Spec_Color_G, buf->Spec_Color_B);
    shader->SetSpecularColor(specCol);
    shader->SetSpecularStrength(buf->Spec_Str);
    if (bslsp) {
        bslsp->refractionStrength = buf->Refraction_Str;
        bslsp->softlighting = buf->Soft_Lighting;
        bslsp->rimlightPower = buf->Rim_Light_Power;
        bslsp->skinTintAlpha = buf->Skin_Tint_Alpha;
        bslsp->skinTintColor[0] = buf->Skin_Tint_Color_R;
        bslsp->skinTintColor[1] = buf->Skin_Tint_Color_G;
        bslsp->skinTintColor[2] = buf->Skin_Tint_Color_B;
    };
};


/* ******************** SEGMENTS AND PARTITIONS ****************************** */

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

NIFLY_API int getSubsegments(void* nifref, void* shaperef, int segID, uint32_t* segments, int segLen) {
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
    /* partData = (uint16 flags, uint16 partID)... where partID is the body part ID
    * partDataLen = length of the buffer in uint16s
    * tris = list of segment indices matching 1-1 with shape triangles
    * 
        >>Needs to be called AFTER bone weights are set
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NiVector<BSDismemberSkinInstance::PartitionInfo> partInfos;
    std::vector<int> triParts;

    for (int i = 0; i < partDataLen*2; i += 2) {
        BSDismemberSkinInstance::PartitionInfo p;
        p.flags = static_cast<PartitionFlags>(partData[i]);
        p.partID = partData[i+1];
        partInfos.push_back(p);
    }

    for (int i = 0; i < triLen; i++) {
        triParts.push_back(tris[i]);
    }

    nif->SetShapePartitions(shape, partInfos, triParts, true);
    nif->UpdateSkinPartitions(shape);
}

NIFLY_API void setSegments(void* nifref, void* shaperef,
    uint16_t* segData, int segDataLen,
    uint32_t* subsegData, int subsegDataLen,
    uint16_t* tris, int triLen,
    const char* filename)
    /*
    * Create segments and subsegments in the nif
    * segData = [part_id, ...] list of internal IDs for each segment
    * subsegData = [[part_id, parent_id, user_slot, material], ...]
    * tris = [part_id, ...] matches 1:1 with the shape's tris, indicates which subsegment
    *   it's a part of
    * filename = null-terminated filename
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NifSegmentationInfo inf;
    inf.ssfFile = filename;

    for (int i = 0; i < segDataLen; i++) {
        NifSegmentInfo* seg = new NifSegmentInfo();
        seg->partID = segData[i];
        inf.segs.push_back(*seg);
    }

    for (int i = 0, j = 0; i < subsegDataLen; i++) {
        NifSubSegmentInfo sseg;
        sseg.partID = subsegData[j++];
        uint32_t parentID = subsegData[j++];
        sseg.userSlotID = subsegData[j++];
        sseg.material = subsegData[j++];

        for (auto& seg : inf.segs) {
            if (seg.partID == parentID) {
                seg.subs.push_back(sseg);
                break;
            }
        }
    }

    std::vector<int> triParts;
    for (int i = 0; i < triLen; i++) {
        triParts.push_back(tris[i]);
    }
    nif->SetShapeSegments(shape, inf, triParts);
    nif->UpdateSkinPartitions(shape);
}

/* ************************ VERTEX COLORS AND ALPHA ********************* */

NIFLY_API int getColorsForShape(void* nifref, void* shaperef, float* colors, int colorLen) {
    /*
        Return vertex colors.
        colorLen = # of floats buffer can hold, has to be 4x number of colors
        Return value is # of colors, which is # of vertices.
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    const std::vector<Color4>* theColors = nif->GetColorsForShape(shape->name.get());
    for (int i = 0, j = 0; j < colorLen && i < theColors->size(); i++) {
        colors[j++] = theColors->at(i).r;
        colors[j++] = theColors->at(i).g;
        colors[j++] = theColors->at(i).b;
        colors[j++] = theColors->at(i).a;
    }
    return int(theColors->size());
}

NIFLY_API void setColorsForShape(void* nifref, void* shaperef, float* colors, int colorLen) {
    /*
        Set vertex colors.
        colorLen = # of color values in the buf, must be same as # of vertices
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    std::vector<Color4> theColors;
    for (int i = 0, j = 0; i < colorLen; i++) {
        Color4 c;
        c.r = colors[j++];
        c.g = colors[j++];
        c.b = colors[j++];
        c.a = colors[j++];
        theColors.push_back(c);
    }
    nif->SetColorsForShape(shape->name.get(), theColors);
}

/* ***************************** EXTRA DATA ***************************** */

int getStringExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen)
/* Treats the NiStringExtraData nodes in the nif like an array--idx indicates
    which to return (0-based).
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    //NiShape* shape = static_cast<NiShape*>(shaperef);
    NiAVObject* source = nullptr;
    if (shaperef)
        source = static_cast<NiAVObject*>(shaperef);
    else
        source = nif->GetRootNode();

    int i = idx;
    for (auto& extraData : source->extraDataRefs) {
        NiStringExtraData* strData = hdr.GetBlock<NiStringExtraData>(extraData);
        if (strData) {
            if (i == 0) {
                *namelen = int(strData->name.get().size());
                *valuelen = int(strData->stringData.get().size());
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};

int getStringExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen)
/* Treats the NiStringExtraData nodes in the nif like an array--idx indicates
    which to return (0-based).
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    //NiShape* shape = static_cast<NiShape*>(shaperef);
    NiAVObject* source = nullptr;
    if (shaperef)
        source = static_cast<NiAVObject*>(shaperef);
    else
        source = nif->GetRootNode();

    int i = idx;
    for (auto& extraData : source->extraDataRefs) {
        NiStringExtraData* strData = hdr.GetBlock<NiStringExtraData>(extraData);
        if (strData) {
            if (i == 0) {
                strncpy_s(name, namelen, strData->name.get().c_str(), namelen - 1);
                strncpy_s(buf, buflen, strData->stringData.get().c_str(), buflen - 1);
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};

void setStringExtraData(void* nifref, void* shaperef, char* name, char* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiAVObject* target = nullptr;
    if (shaperef)
        target = static_cast<NiAVObject*>(shaperef);
    else
        target = nif->GetRootNode();
    
    if (target) {
        auto strdata = std::make_unique<NiStringExtraData>();
        strdata->name.get() = name;
        strdata->stringData.get() = buf;
        nif->AssignExtraData(target, std::move(strdata));
    }
};

int getBGExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* datalen)
/* Treats the NiBehaviorGraphExtraData nodes in the nif like an array--idx indicates
    which to return (0-based).
    Returns T/F depending on whether extra data exists
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    //NiShape* shape = static_cast<NiShape*>(shaperef);
    NiAVObject* source = nullptr;
    if (shaperef)
        source = static_cast<NiAVObject*>(shaperef);
    else
        source = nif->GetRootNode();

    int i = idx;
    for (auto& extraData : source->extraDataRefs) {
        BSBehaviorGraphExtraData* bgData = hdr.GetBlock<BSBehaviorGraphExtraData>(extraData);
        if (bgData) {
            if (i == 0) {
                *namelen = int(bgData->name.get().size());
                *datalen = int(bgData->behaviorGraphFile.get().size());
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};
int getBGExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen)
/* Treats the NiBehaviorGraphExtraData nodes in the nif like an array--idx indicates
    which to return (0-based).
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    //NiShape* shape = static_cast<NiShape*>(shaperef);
    NiAVObject* source = nullptr;
    if (shaperef)
        source = static_cast<NiAVObject*>(shaperef);
    else
        source = nif->GetRootNode();

    int i = idx;
    for (auto& extraData : source->extraDataRefs) {
        BSBehaviorGraphExtraData* bgData = hdr.GetBlock<BSBehaviorGraphExtraData>(extraData);
        if (bgData) {
            if (i == 0) {
                strncpy_s(name, namelen, bgData->name.get().c_str(), namelen - 1);
                strncpy_s(buf, buflen, bgData->behaviorGraphFile.get().c_str(), buflen - 1);
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};

void setBGExtraData(void* nifref, void* shaperef, char* name, char* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiAVObject* target = nullptr;
    if (shaperef)
        target = static_cast<NiAVObject*>(shaperef);
    else
        target = nif->GetRootNode();

    if (target) {
        auto strdata = std::make_unique<BSBehaviorGraphExtraData>();
        strdata->name.get() = name;
        strdata->behaviorGraphFile.get() = buf;
        nif->AssignExtraData(target, std::move(strdata));
    }
};

/* ********************* ERROR REPORTING ********************* */

void clearMessageLog() {
    niflydll::LogInit();
};

int getMessageLog(char* buf, int buflen) {
    return niflydll::LogGet(buf, buflen);
    //return niflydll::LogGetLen();
}
