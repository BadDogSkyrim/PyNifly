/*
* Wrapper layer to provide a DLL interface for Nifly.

  Data passed through simple buffers to prevent problems calling from different languages.
  
  Copyright (c) 2021, by Bad Dog
*/

/*
    TODO: Walk through and make sure all the memory allocated here gets released
    */
#include "pch.h" // use stdafx.h in Visual Studio 2017 and earlier
#include <iostream>
#include <filesystem>
#include <string>
#include <algorithm>
#include "niffile.hpp"
#include "bhk.hpp"
#include "NiflyFunctions.hpp"
#include "NiflyWrapper.hpp"

const int NiflyDDLVersion[3] = { 12, 0, 0 }; 
 
using namespace nifly;

/* ************************** UTILITY ************************** */

#define CheckID(shaperef) \
    if (!shaperef) { \
        niflydll::LogWriteEf("%s called on invalid node.", __FUNCTION__); \
        return 1; \
    }

#define CheckBuf(buf, expectedType, expectedBuf) \
    if (buf->bufType != expectedType || buf->bufSize != sizeof(expectedBuf)) { \
    niflydll::LogWriteEf("%s called with bad buffer: type=%d, size=%d.", __FUNCTION__, buf->bufType, buf->bufSize); \
    return 2; \
    }

#define CheckBuf2(buf, expectedType1, expectedType2, expectedBuf) \
    if ((buf->bufType != expectedType1 && buf->bufType != expectedType2) || buf->bufSize != sizeof(expectedBuf)) { \
    niflydll::LogWriteEf("%s called with bad buffer: type=%d, size=%d.", __FUNCTION__, buf->bufType, buf->bufSize); \
    return 2; \
    }


void assignQ(float* dest, Quaternion source) {
    dest[0] = source.w;
    dest[1] = source.x;
    dest[2] = source.y;
    dest[3] = source.z;
}

void assignVec3(float* dest, Vector3 source) {
    dest[0] = source.x;
    dest[1] = source.y;
    dest[2] = source.z;
}

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
    NifLoadOptions options;

    // **Expanded options not yet in Nifly
    //if (const char* index = strstr(filename, "\\meshes")) {
    //    options.loadMaterials = true;
    //    options.projectRoot = std::string(filename, index);
    //}
    int errval = nif->Load(std::filesystem::path(filename), options);

    if (errval == 0) return nif;

    if (errval == 1) niflydll::LogWrite("File does not exist or is not a nif");
    if (errval == 2) niflydll::LogWrite("File is not a nif format we can read");

    return nullptr;
}

NIFLY_API void* getRoot(void* f) 
/* Return the root node of the file.
    KF files may not have a NiNode as the root, so do the work here.
    */
{
    NifFile* theNif = static_cast<NifFile*>(f);
    NiHeader hdr = theNif->GetHeader();
    //return theNif->GetRootNode();
    return hdr.GetBlock<NiObject>(0u);
}

NIFLY_API int getRootName(void* f, char* buf, int len) {
    NifFile* theNif = static_cast<NifFile*>(f);
    NiHeader* hdr = &theNif->GetHeader();

    std::string name;
    nifly::NiObjectNET* root = theNif->GetRootNode();
    if (root)
        name = root->name.get();
    else {
        nifly::NiSequence* root = hdr->GetBlock<NiSequence>(uint32_t(0));
        name = root->name.get();
    }
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

NIFLY_API const int* getVersion() {
    return NiflyDDLVersion;
};

NIFLY_API void* nifCreate() {
    return new NifFile;
}

NIFLY_API void destroy(void* f) {
    NifFile* theNif = static_cast<NifFile*>(f);
    theNif->Clear();
    delete theNif;
}

void SetNifVersionWrap(NifFile* nif, enum TargetGame targ, const char* rootType, std::string name) {
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

    /* Replace root node with the correct type
    */
    if (strcmp(rootType, "BSFadeNode") == 0) {
        auto& hdr = nif->GetHeader();
        hdr.DeleteBlock(0u);

        auto rootNode = std::make_unique<BSFadeNode>();
        rootNode->name.get() = name;
        hdr.AddBlock(std::move(rootNode));
    }
    if (strcmp(rootType, "BSLeafAnimNode") == 0) {
        auto& hdr = nif->GetHeader();
        hdr.DeleteBlock(0u);

        auto rootNode = std::make_unique<BSLeafAnimNode>();
        rootNode->name.get() = name;
        hdr.AddBlock(std::move(rootNode));
    }
    else if (strcmp(rootType, "NiControllerSequence") == 0) {
        auto& hdr = nif->GetHeader();
        hdr.DeleteBlock(0u);

        auto rootNode = std::make_unique<NiControllerSequence>();
        rootNode->name.get() = name;
        hdr.AddBlock(std::move(rootNode));
    }
    //NiNode* root = nif->GetRootNode();
    //std::string nm = root->GetName();
    //root->SetName(name);
}

NIFLY_API void* createNif(const char* targetGameName, const char* rootType, const char* rootName) 
/*
    Set up to create a new nif. (Not actually created until save.)
    rootType is the block type of root to create, usually "NiNode". May be omitted.
*/
{
    TargetGame targetGame = StrToTargetGame(targetGameName);
    NifFile* workNif = new NifFile();
    std::string rootNameStr = rootName;
    SetNifVersionWrap(workNif, targetGame, rootType, rootNameStr);
    return workNif;
}

NIFLY_API int saveNif(void* the_nif, const char8_t* filename) {
    /*
        Write the nif out to a file.
        Returns 0 on success.
        */
    NifFile* nif = static_cast<NifFile*>(the_nif);

    for (auto& shape : nif->GetShapes())
    {
        nif->UpdateSkinPartitions(shape);
        shape->UpdateBounds();
        UpdateShapeSkinBoneBounds(nif, shape);
    }
    

    return nif->Save(std::filesystem::path(filename));
}


/* ********************* NODE HANDLING ********************* */

NIFLY_API int getNodeCount(void* theNif)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    return int(nif->GetNodes().size());
}

NIFLY_API void getNodes(void* theNif, void** buf)
/* 
* Return all NiNodes in the nif. Includes the root node.
*/
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    std::vector<nifly::NiNode*> nodes = nif->GetNodes();
    for (int i = 0; i < nodes.size(); i++)
        buf[i] = nodes[i];
}

NIFLY_API int getBlockID(void* nifref, void* blk) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiObject* obj = static_cast<NiObject*>(blk);
    return hdr->GetBlockID(obj);
}

NIFLY_API int getBlockname(void* nifref, int blockID, char* buf, int buflen) 
/*
    Return the blockname of the given NiObject.
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiObject* theNode = hdr->GetBlock<NiObject>(blockID);

    int namelen = 0;
    if (theNode) {
        std::string name = theNode->GetBlockName();
        int copylen = std::min((int)buflen - 1, (int)name.length());
        name.copy(buf, copylen, 0);
        namelen = name.length();
    }
    if (buflen > 0) buf[namelen] = '\0';
    return int(namelen);
}

NIFLY_API int getNodeBlockname(void* node, char* buf, int buflen) 
/* Return the blockname of the given NiObject. */
{
    nifly::NiObject* theNode = static_cast<nifly::NiObject*>(node);
    std::string name = theNode->GetBlockName();
    int copylen = std::min((int)buflen - 1, (int)name.length());
    name.copy(buf, copylen, 0);
    buf[name.length()] = '\0';
    return int(name.length());
}

NIFLY_API void getNode(void* node, NiNodeBuf* buf) {
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    buf->nameID = theNode->name.GetIndex();
    buf->controllerID = theNode->controllerRef.index;
    buf->extraDataCount = theNode->extraDataRefs.GetSize();
    buf->flags = theNode->flags;
    //buf->transform = theNode->transform;
    for (int i = 0; i < 3; i++) buf->translation[i] = theNode->transform.translation[i];
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++)
            buf->rotation[r][c] = theNode->transform.rotation[r][c];
    buf->scale = theNode->transform.scale;
    buf->collisionID = theNode->collisionRef.index;
    buf->childCount = theNode->childRefs.GetSize();
    buf->effectCount = theNode->effectRefs.GetSize();
}

int getNodeProperties(void* nifref, uint32_t id, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiNodeBuf* buf = static_cast<NiNodeBuf*>(inbuf);
    nifly::NiNode* node = hdr->GetBlock<NiNode>(id);

    CheckID(node);

    CheckBuf(buf, BUFFER_TYPES::NiNodeBufType, NiNodeBuf);

    getNode(node, buf);
    return 0;
}

void setNode(NiNode* theNode, NiNodeBuf* buf) {
    theNode->name.SetIndex(buf->nameID);
    theNode->controllerRef.index = buf->controllerID;
    theNode->flags = buf->flags;
    //buf->transform = theNode->transform;
    for (int i = 0; i < 3; i++) theNode->transform.translation[i] = buf->translation[i];
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++)
            theNode->transform.rotation[r][c] = buf->rotation[r][c];
    theNode->transform.scale = buf->scale;
    theNode->collisionRef.index = buf->collisionID;
}

int setNodeByID(void* nifref, uint32_t id, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiNodeBuf* buf = static_cast<NiNodeBuf*>(inbuf);
    nifly::NiNode* theNode = hdr->GetBlock<NiNode>(id);

    CheckID(theNode);

    CheckBuf(buf, BUFFER_TYPES::NiNodeBufType, NiNodeBuf);

    theNode->name.SetIndex(buf->nameID);
    theNode->controllerRef.index = buf->controllerID;
    theNode->flags = buf->flags;
    //buf->transform = theNode->transform;
    for (int i = 0; i < 3; i++) theNode->transform.translation[i] = buf->translation[i];
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++)
            theNode->transform.rotation[r][c] = buf->rotation[r][c];
    theNode->transform.scale = buf->scale;
    theNode->collisionRef.index = buf->collisionID;

    return 0;
}

NIFLY_API void* getNodeByID(void* theNif, uint32_t theID) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    NiHeader hdr = nif->GetHeader();
    nifly::NiObject* node = hdr.GetBlock<NiObject>(theID);
    return node;
}

// OBSOLETE
NIFLY_API int getNodeFlags(void* node) {
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    return theNode->flags;
}

// OBSOLETE
NIFLY_API void setNodeFlags(void* node, int theFlags) {
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    theNode->flags = theFlags;
}

NIFLY_API int getNodeName(void* node, char* buf, int buflen) {
    if (buflen > 0) buf[0] = '\0';
    std::string name;
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    if (theNode) 
        name = theNode->name.get();
    else {
        NiSequence* theSeq = static_cast<NiSequence*>(node);
        name = theNode->name.get();
    }

    if (name.length() == 0) return 0;

    int copylen = std::min((int)buflen - 1, (int)name.length());
    name.copy(buf, copylen, 0);
    buf[copylen] = '\0';

    return int(name.length());
}

NIFLY_API void* getNodeParent(void* theNif, void* node) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    return nif->GetParentNode(theNode);
}

NIFLY_API int getNodeChildren(void* nifRef, int nodeID, int buflen, int* buf)
/* Return children of the given node in the given list. 
    Note the children returned map to anything under the node in the NifSkope hierarchy, not
    just the nodes pointed to by the "Children" property.
    Returns the number of children actually found. 
*/
{
    NifFile* nif = static_cast<NifFile*>(nifRef);
    NiHeader* hdr = &nif->GetHeader();
    NiNode* parent = hdr->GetBlock<NiNode>(nodeID);

    std::set<nifly::NiRef*> children;
    parent->GetChildRefs(children);

    int i = 0;
    int childCount = 0;
    for (auto& child : children) {
        if (i < buflen)
            buf[i++] = child->index;
        else
            break;
    }

    return children.size();
}

NIFLY_API void* addNode(void* f, const char* name, void* xf, void* parent) {
    NifFile* nif = static_cast<NifFile*>(f);
    NiNode* parentNode = static_cast<NiNode*>(parent);
    MatTransform* xfptr = static_cast<MatTransform*>(xf);
    NiNode* theNode = nif->AddNode(name, *xfptr, parentNode);
    return theNode;
}

int createNode(void* f, const char* name, void* properties, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(f);
    NiHeader* hdr = &nif->GetHeader();
    NiNode* parentNode = hdr->GetBlock<NiNode>(parent);
    NiNodeBuf* buf = static_cast<NiNodeBuf*>(properties);

    CheckBuf(buf, BUFFER_TYPES::NiNodeBufType, NiNodeBuf);

    MatTransform xf;
    for (int i = 0; i < 3; i++) xf.translation[i] = buf->translation[i];
    for (int i = 0; i < 3; i++) 
        for (int j = 0; j < 3; j++) 
            xf.rotation[i][j] = buf->rotation[i][j];
    NiNode* theNode = nif->AddNode(name, xf, parentNode);
    
    return hdr->GetBlockID(theNode);
}

int assignControllerSequence(void* f, uint32_t id, void* b) {
    NifFile* nif = static_cast<NifFile*>(f);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerSequenceBuf* buf = static_cast<NiControllerSequenceBuf*>(b);
    NiControllerSequence* cs = hdr->GetBlock< NiControllerSequence>(id);

    CheckID(cs);

    CheckBuf(buf, BUFFER_TYPES::NiControllerSequenceBufType, NiControllerSequenceBuf);

    cs->arrayGrowBy = buf->arrayGrowBy;
    cs->weight = buf->weight;
    if (buf->textKeyID != NIF_NPOS) cs->textKeyRef.index = buf->textKeyID;
    cs->cycleType = CycleType(buf->cycleType);
    cs->frequency = buf->frequency;
    cs->startTime = buf->startTime;
    cs->stopTime = buf->stopTime;
    cs->accumRootName.SetIndex(buf->accumRootNameID);
    cs->accumRootName.get() = hdr->GetStringById(buf->accumRootNameID);
    if (buf->animNotesID != NIF_NPOS) cs->animNotesRef.index = buf->animNotesID;

    return 0;
}

NIFLY_API void* findNodeByName(void* theNif, const char* nodeName) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    return nif->FindBlockByName<NiObjectNET>(nodeName);
}

NIFLY_API int findBlockByName(void* theNif, const char* nodeName) {
    NifFile* nif = static_cast<NifFile*>(theNif);
    NiHeader hdr = nif->GetHeader();
    NiObjectNET* theBlock = nif->FindBlockByName<NiObjectNET>(nodeName);
    return nif->GetBlockID(theBlock);
}

NIFLY_API int findNodesByType(void* nifRef, void* parentRef, const char* blockname, int buflen, void** buf)
/* Return nodes in the nif by blockname.
    parent = Parent node; only direct children will be found.
    blockname = block name of desired children.
    buflen = length of buffer in uint32s. 
    buf = buffer to write with node IDs of found nodes. 
*/ 
{
    NifFile* nif = static_cast<NifFile*>(nifRef);
    NiHeader hdr = nif->GetHeader();
    NiNode* parent = static_cast<NiNode*>(parentRef);
    
    std::set<nifly::NiRef*> children;
    parent->GetChildRefs(children);

    int i = 0;
    int childCount = 0;
    std::string s = blockname;
    for (auto& child: children) {
        auto ch = hdr.GetBlock<NiObject>(child);
        if (ch && ch->GetBlockName() == s) {
            childCount++;
            if (i < buflen) buf[i++] = hdr.GetBlock<NiObject>(child);
        }
    }

    if (childCount == 0) {
        niflydll::LogWriteMf("Could not find block of type " + s);
    }

    return childCount;
}

NIFLY_API int getMaxStringLen(void* nifref) 
/* Return the max length of any string in the nif. Enables callers to allocate big enough
buffers conveniently.
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    int m = 0;
    for (int i = 0; i < hdr.GetStringCount(); i++)
        m = std::max(m, int(hdr.GetStringById(i).length()));
    return m;
}

NIFLY_API int getString(void* nifref, int strid, int buflen, char* buf) 
/* Return a string from the NIF given its ID. */ 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    
    std::string str = hdr->GetStringById(strid);
    int i;
    for (i = 0; i < buflen && i < str.length(); i++)
        buf[i] = str[i];
    if (i < buflen) buf[i] = '\0';

    return str.length();
}

NIFLY_API int addString(void* nifref, const char* buf) 
/* Add a string to the nif. */ 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();

    return hdr->AddOrFindStringId(buf);
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

void getShape(NiShape* theShape, NiShapeBuf* buf) {
    buf->nameID = theShape->name.GetIndex();
    buf->controllerID = theShape->controllerRef.index;
    buf->extraDataCount = theShape->extraDataRefs.GetSize();
    buf->flags = theShape->flags;
    //buf->transform = theNode->transform;
    for (int i = 0; i < 3; i++) buf->translation[i] = theShape->transform.translation[i];
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++)
            buf->rotation[r][c] = theShape->transform.rotation[r][c];
    buf->scale = theShape->transform.scale;
    buf->propertyCount = theShape->propertyRefs.GetSize();
    buf->collisionID = theShape->collisionRef.index;
    buf->hasVertices = theShape->HasVertices();
    buf->hasNormals = theShape->HasNormals();
    buf->hasVertexColors = theShape->HasVertexColors();
    for (int i=0; i < 3; i++) buf->boundingSphereCenter[i] = theShape->GetBounds().center[i];
    buf->boundingSphereRadius = theShape->GetBounds().radius;
    buf->vertexCount = theShape->GetNumVertices();
    buf->triangleCount = theShape->GetNumTriangles();
    buf->skinInstanceID = theShape->SkinInstanceRef()->index;
    buf->shaderPropertyID = theShape->ShaderPropertyRef()->index;
    buf->alphaPropertyID = theShape->AlphaPropertyRef()->index;
}

int getNiShape(void* nifref, uint32_t id, void* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiShapeBuf* b = static_cast<NiShapeBuf*>(buf);
    nifly::NiShape* node = hdr->GetBlock<NiShape>(id);

    CheckID(node);

    if (b->bufSize != sizeof(NiShapeBuf)) {
        niflydll::LogWrite("ERROR: NiShapeBuf buffer wrong size.");
        return 2;
    }

    getShape(node, b);

    // Nifly doesn't always properly return the shader in ShaderPropertyRefs, so 
    // go hunt it on our own.
    if (b->shaderPropertyID == NIF_NPOS) {
        for (auto& p : node->propertyRefs) {
            if (hdr->GetBlock<BSShaderProperty>(p.index)) {
                b->shaderPropertyID = p.index;
                break;
            }
        }
    }

    if (hdr->GetBlock<BSMeshLODTriShape>(id)) {
        b->bufType = BSMeshLODTriShapeBufType; 
        return 0;
    }
    if (hdr->GetBlock<BSSubIndexTriShape>(id)) {
        b->bufType = BSSubIndexTriShapeBufType;
        return 0;
    }
    if (hdr->GetBlock<BSDynamicTriShape>(id)) {
        b->bufType = BSDynamicTriShapeBufType; 
        return 0;
    }
    if (hdr->GetBlock<BSTriShape>(id)) {
        b->bufType = BSTriShapeBufType;
        return 0;
    }
    if (hdr->GetBlock<NiTriStrips>(id)) {
        b->bufType = NiTriStripsBufType;
        return 0;
    }

    return 0;
}

int getBSMeshLODTriShape(void* nifref, uint32_t id, void* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiShapeBuf* shapebuf = static_cast<NiShapeBuf*>(buf);
    BSMeshLODTriShapeBuf* meshShapeBuf = static_cast<BSMeshLODTriShapeBuf*>(buf);
    nifly::BSMeshLODTriShape* node = hdr->GetBlock<BSMeshLODTriShape>(id);

    CheckID(node);
    CheckBuf(shapebuf, BUFFER_TYPES::BSMeshLODTriShapeBufType, BSMeshLODTriShapeBuf);

    getShape(node, shapebuf);
    meshShapeBuf->lodSize0 = node->lodSize0;
    meshShapeBuf->lodSize1 = node->lodSize1;
    meshShapeBuf->lodSize2 = node->lodSize2;

    return 0;
}

NIFLY_API int getShapeBlockName(void* theShape, char* buf, int buflen) {
    NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const char* blockname = shape->GetBlockName();
    strncpy_s(buf, buflen, blockname, buflen);
    //strncpy(buf, blockname, buflen);
    buf[buflen - 1] = '\0';
    return int(strlen(blockname));
}

NIFLY_API int getVertsForShape(void* theNif, void* theShape, Vector3* buf, int len, int start)
/*
    Get a shape's verts.
    buf, len = buffer that receives triples. len is length of buffer in floats. 
    start = vertex index to start with.
    Returns number of verts in the nif.
    */
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    std::vector<nifly::Vector3> verts;
    nif->GetVertsForShape(shape, verts);
    for (int i = start, j = 0; i < verts.size() && j < len; i++, j += 3)
        buf[i] = verts.at(i);

    return int(verts.size());
}

NIFLY_API int getNormalsForShape(void* theNif, void* theShape, Vector3* buf, int len, int start)
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
        for (int i = start, j = 0; j < len && i < norms->size(); i++, j += 3)
            buf[i] = norms->at(i);
        return int(norms->size());
    }
    else
        return 0;
}

NIFLY_API int getTriangles(void* theNif, void* theShape, Triangle* buf, int len, int start)
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
    for (int i = start, j = 0; j < len && i < shapeTris.size(); i++, j += 3)
        buf[i] = shapeTris.at(i);

    return int(shapeTris.size());
}

NIFLY_API int getUVs(void* theNif, void* theShape, Vector2* buf, int len, int start)
{
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    const std::vector<nifly::Vector2>* uv = nif->GetUvsForShape(shape);
    for (int i = start, j = 0; j < len && i < uv->size(); i++, j += 2) 
        buf[i] = uv->at(i);

    return int(uv->size());
}

NIFLY_API void* createNifShapeFromData(void* parentNif,
    const char* shapeName,
    void* buffer,
    const Vector3* verts,
    const Vector2* uv_points,
    const Vector3* norms,
    const Triangle* tris, 
    void* parentRef)
    /* Create nif shape from the given data
    * verts = (float x, float y float z), ... 
    * uv_points = (float u, float v), matching 1-1 with the verts list
    * norms = (float, float, float) matching 1-1 with the verts list. May be null.
    * vertCount = number of verts in verts list (and uv pairs and normals in those lists)
    * tris = (uint16, uiint16, uint16) indices into the vertex list
    * triCount = # of tris in the tris list (buffer is 3x as long)
    * optionsPtr == 1: Create SSE head part (so use BSDynamicTriShape)
    *            == 2: Create FO4 BSTriShape (default is BSSubindexTriShape)
    *            == 4: Create FO4 BSEffectShaderProperty
    *            may be omitted
    * parentRef = Node to be parent of the new shape. Root if omitted.
    */
{
    NifFile* nif = static_cast<NifFile*>(parentNif);
    NiShapeBuf* buf = static_cast<NiShapeBuf*>(buffer);
    std::vector<Vector3> v;
    std::vector<Triangle> t;
    std::vector<Vector2> uv;
    std::vector<Vector3> n;

    for (int i = 0; i < buf->vertexCount; i++) {
        Vector3 thisv = verts[i];
        v.push_back(thisv);

        Vector2 thisuv = uv_points[i];
        uv.push_back(thisuv);

        if (norms) {
            Vector3 thisnorm = norms[i];
            n.push_back(thisnorm);
        };
    }
    for (int i = 0; i < buf->triangleCount; i++) {
        Triangle thist = tris[i];
        t.push_back(thist);
    }

    //uint16_t opt = 0;
    //if (optionsPtr) opt = *optionsPtr;
    NiNode* parent = nullptr;
    if (parentRef) parent = static_cast<NiNode*>(parentRef);

    NiShape* newShape = PyniflyCreateShapeFromData(nif, shapeName, 
            buf, &v, &t, &uv, &n, parent);

    if (buf->bufType == BSMeshLODTriShapeBufType) {
        BSMeshLODTriShape* meshShape = static_cast<BSMeshLODTriShape*>(newShape);
        BSMeshLODTriShapeBuf* meshBuf = static_cast<BSMeshLODTriShapeBuf*>(buf);
        meshShape->lodSize0 = meshBuf->lodSize0;
        meshShape->lodSize1 = meshBuf->lodSize1;
        meshShape->lodSize2 = meshBuf->lodSize2;
    }
    return newShape;
}


/* ********************* TRANSFORMS AND SKINNING ********************* */

NIFLY_API bool getShapeGlobalToSkin(void* nifRef, void* shapeRef, MatTransform* xform) 
/* Return the global-to-skin transform (on NiSkinData), if it exists. 
    FO4 meshes do not have this transform.
    Returns true if the transform exists.
    V9 warning: the call on the skin returned the inverse of this.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifRef);
    bool skinXfFound = nif->GetShapeTransformGlobalToSkin(static_cast<NiShape*>(shapeRef), *xform);
    if (!skinXfFound) {
        // Calculate the transform if it's not stored in the nif
        std::vector<MatTransform> eachXformGlobalToSkin;
        MatTransform boneXf;
        
    }
    return skinXfFound;
}

NIFLY_API void calcShapeGlobalToSkin(void* nifRef, void* shapeRef, MatTransform* xform) 
/*  Calculate the global-to-skin transform from the skin-to-bone transforms. 
    The calculation assumes the bone nodes are in vanilla position.

    NOTE This duplicates NifFile::CalcShapeTransformGLobalToSkin() -- but this averages all the transform
    whereas the NifFile version just returns the first it finds, which is probably fine TBH.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifRef);
    NiShape* shape = static_cast<NiShape*>(shapeRef);
    std::vector<MatTransform> eachXformGlobalToSkin;
    std::vector<int> idList;
    std::string bonename;

    xform->Clear();

    nif->GetShapeBoneIDList(shape, idList);
    int i = 0;
    for (auto& id: idList) {
        MatTransform thisXF, xformBoneToGlobal, xformSkinToBone;

        auto node = nif->GetHeader().GetBlock<NiNode>(id);
        if (!node) continue;
        bonename = node->name.get();
        
        // #### LOOKS LIKE A BUG ### - should be global transform, not to-parent
        xformBoneToGlobal = node->GetTransformToParent();
        if (nif->GetShapeTransformSkinToBone(shape, i, xformSkinToBone)) {
            thisXF = xformBoneToGlobal.ComposeTransforms(xformSkinToBone).InverseTransform();
            eachXformGlobalToSkin.push_back(thisXF);
        }
        i++;
    }
    if (!eachXformGlobalToSkin.empty())
        *xform = CalcMedianMatTransform(eachXformGlobalToSkin);
}

NIFLY_API int hasSkinInstance(void* shapeRef) {
    return static_cast<NiShape*>(shapeRef)->HasSkinInstance()? 1: 0;
}

NIFLY_API bool getShapeSkinToBone(void* nifPtr, void* shapePtr, const char* boneName, MatTransform& buf)
/* Return the skin-to-bone transform for the given bone in the given shape*/
{
    //MatTransform xf;
    bool hasXform = static_cast<NifFile*>(nifPtr)->GetShapeTransformSkinToBone(
        static_cast<NiShape*>(shapePtr),
        std::string(boneName),
        buf);
    //if (hasXform) XformToBuffer(buf, xf);
    return hasXform;
}

NIFLY_API void setShapeSkinToBone(void* nifPtr, void* shapePtr, const char* boneName, const MatTransform& buf)
/* 
    Set the skin-to-bone transform for the given bone in the given shape.

    Note the bone has to exist in the shape already. 
*/
{
    NifFile* nif = static_cast<NifFile*>(nifPtr);
    NiShape* shape = static_cast<NiShape*>(shapePtr);
    NiHeader hdr = nif->GetHeader();
    uint32_t boneID = shape->GetBoneID(hdr, boneName);

    if (boneID != NIF_NPOS)
        nif->SetShapeTransformSkinToBone(shape, boneID, buf);
}

// OBSOLETE
NIFLY_API void getNodeTransform(void* theNode, MatTransform* buf) {
    nifly::NiNode* node = static_cast<nifly::NiNode*>(theNode);
    *buf = node->GetTransformToParent();
}

NIFLY_API int getNodeTransformToGlobal(void* nifref, const char* nodeName, MatTransform* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    return nif->GetNodeTransformToGlobal(nodeName, *buf)? 1 : 0;
}

NIFLY_API void skinShape(void* nif, void* shapeRef)
{
    static_cast<NifFile*>(nif)->CreateSkinning(static_cast<nifly::NiShape*>(shapeRef));
}

NIFLY_API void setShapeGlobalToSkin(void* nifref, void* shaperef, MatTransform* xformBuf) {
    NifFile* nif = static_cast<nifly::NifFile*>(nifref);
    NiShape* shape = static_cast<nifly::NiShape*>(shaperef);
    nif->SetShapeTransformGlobalToSkin(shape, *xformBuf);
}

NIFLY_API void setTransform(void* theShape, MatTransform* buf) {
    NiShape* shape = static_cast<nifly::NiShape*>(theShape);
    shape->SetTransformToParent(*buf);
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
/* Returns a list of bone names the shape uses. List is separated by \n characters.
* buf = buffer to receive the list
* buflen = length of the buffer in chars
* returns actual length written to buf
*/
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

NIFLY_API int getShapeBoneWeightsCount(void* theNif, void* theShape, int boneIndex) {
    /* Get the count of bone weights associated with the given bone. */
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);

    std::unordered_map<uint16_t, float> boneWeights;
    return nif->GetShapeBoneWeights(shape, boneIndex, boneWeights);
}

NIFLY_API int getShapeBoneWeights(void* theNif, void* theShape, int boneIndex,
                                  struct VertexWeightPair* buf, int buflen) {
    /* Get the bone weights associated with the given bone for the given shape.
        boneIndex = index of bone in the list of bones associated with this shape 
        buf = Buffer to hold <vertex index, weight> for every vertex weighted to this bone.
        returns number of bones
    */
    NifFile* nif = static_cast<NifFile*>(theNif);
    nifly::NiShape* shape = static_cast<nifly::NiShape*>(theShape);

    std::unordered_map<uint16_t, float> boneWeights;
    int numWeights = nif->GetShapeBoneWeights(shape, boneIndex, boneWeights);

    int j = 0;
    for (const auto& [key, value] : boneWeights) {
        buf[j].vertex = key;
        buf[j++].weight = value;
        if (j >= buflen) break;
    }

    return numWeights;
}

NIFLY_API void* addBoneToNifShape(void* nifref, void* shaperef, const char* boneName,
    MatTransform* xformToParent, const char* parentName)
/*  Add a bone to a shape, adding a node for it if needed. 
* 
*   NOTE this call removes any skin/bone data--skin-to-bone transform and bone weights.
*   Add all bones to the shape first, then set skin-bone attributes.
* 
*   A NiNode is created for the bone if it doesn't already exist.
* 
*   xformToParent = Transform of the bone node must be present if the bone node doesn't yet exist.
*   parentName is the parent for the new bone; it must exist if given. May be null. 
*   Returns the handle of the NiNode representing the bone.
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiShape* shape = static_cast<NiShape*>(shaperef);

    // Add a node for the bone if not already there
    NiNode* node = nif->FindBlockByName<NiNode>(boneName);
    if (!node) {
        NiNode* pnode = nullptr;
        if (parentName) pnode = nif->FindBlockByName<NiNode>(parentName);
        node = nif->AddNode(boneName, *xformToParent, pnode);
    }

    std::vector<int> boneIDs;
    nif->GetShapeBoneIDList(shape, boneIDs);
    int boneIndex = uint32_t(boneIDs.size());
    boneIDs.push_back(hdr.GetBlockID(node));
    nif->SetShapeBoneIDList(shape, boneIDs);

    nif->SetShapeBoneTransform(shape, boneIndex, *xformToParent);

    return node;
}

NIFLY_API void setShapeBoneWeights(void* nifref, void* shaperef, const char* boneName,
    VertexWeightPair* vertWeightsIn, int vertWeightLen) 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiShape* shape = static_cast<NiShape*>(shaperef);
    bool isFO = hdr.GetVersion().IsFO4() || nif->GetHeader().GetVersion().IsFO76();
    int boneID = shape->GetBoneID(hdr, boneName);
    
    // Bone must have been added to skin already
    if (boneID == NIF_NPOS) {
        return;
    }

    auto bsTriShape = dynamic_cast<BSTriShape*>(shape);
    if (bsTriShape) {
        for (int i = 0; i < std::min(vertWeightLen, int(bsTriShape->vertData.size())); i++) {
            auto& vertex = bsTriShape->vertData[vertWeightsIn[i].vertex];
            bool found = false;
            for (int j = 0; j < 4 && !found; j++) {
                if (vertex.weightBones[j] == boneID) {
                    vertex.weights[j] = vertWeightsIn[i].weight;
                    found = true;
                }
            }
            if (!found) {
                int minIndex = 0;
                float minWeight = 1.0;
                for (int j = 0; j < 4; j++) {
                    if (vertex.weights[j] < minWeight) {
                        minWeight = vertex.weights[j];
                        minIndex = j;
                    }
                };
                if (minWeight < vertWeightsIn[i].weight) {
                    vertex.weights[minIndex] = vertWeightsIn[i].weight;
                    vertex.weightBones[minIndex] = boneID;
                }
            }
        }
    }
    else {
        std::unordered_map<uint16_t, float> vertWeights;
        for (int i = 0; i < vertWeightLen; i++) {
            vertWeights[vertWeightsIn[i].vertex] = vertWeightsIn[i].weight;
        }
        nif->SetShapeBoneWeights(shape->name.get(), boneID, vertWeights);
    }
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

NIFLY_API int getShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, char* buf, int buflen) 
/*
* Return the filepath associated with the requested texture slot. 
* For BSEffectShaderProperty the slots are: 
*   0 = source texture
*   1 = normal map
*   2 = <not used>
*   3 = greyscale
*   4 = environment map
*   5 = environment mask
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    NiShader* shader = nif->GetShader(shape);
    NiHeader hdr = nif->GetHeader();

    std::string texture;

    uint32_t val = nif->GetTextureSlot(shape, texture, slotIndex);

    if (buflen > 0) buf[0] = '\0';
    if (val == 0) return 0;

    if (buflen > 1) {
        memcpy(buf, texture.data(), std::min(texture.size(), static_cast<size_t>(buflen - 1)));
        buf[texture.size()] = '\0';
    }

    return static_cast<int>(texture.length());
};

int getNiShader(void* nifref, uint32_t id, void* buffer)
/*
    Get attributes for one of the NiShaderProperty types.
    Return value: 0 = success, 1 = no shader, or not a BSLightingShaderProperty
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BSShaderProperty* bssh = hdr->GetBlock<BSShaderProperty>(id);
    BSLightingShaderProperty* bslsp = hdr->GetBlock<BSLightingShaderProperty>(id);
    BSEffectShaderProperty* bsesp = hdr->GetBlock<BSEffectShaderProperty>(id);
    NiShaderBuf* buf = static_cast<NiShaderBuf*>(buffer);

    CheckID(bssh);
    CheckBuf2(buf, BUFFER_TYPES::NiShaderBufType, BUFFER_TYPES::BSEffectShaderPropertyBufType, NiShaderBuf);

    //NiTexturingProperty* txtProp = nif->GetTexturingProperty(shape);

    //FillMemory(buf, sizeof(BSLSPAttrs), 0);

    buf->nameID = bssh->name.GetIndex();
    buf->controllerID = bssh->controllerRef.index;
    buf->extraDataCount = bssh->extraDataRefs.GetSize();

    buf->Shader_Type = bssh->GetShaderType();
    buf->Shader_Flags_1 = bssh->shaderFlags1;
    buf->Shader_Flags_2 = bssh->shaderFlags2;
    buf->UV_Offset_U = bssh->GetUVOffset().u;
    buf->UV_Offset_V = bssh->GetUVOffset().v;
    buf->UV_Scale_U = bssh->GetUVScale().u;
    buf->UV_Scale_V = bssh->GetUVScale().v;

    buf->Emissive_Color_R = bssh->GetEmissiveColor().r;
    buf->Emissive_Color_G = bssh->GetEmissiveColor().g;
    buf->Emissive_Color_B = bssh->GetEmissiveColor().b;
    buf->Emissive_Color_A = bssh->GetEmissiveColor().a;
    buf->Emissmive_Mult = bssh->GetEmissiveMultiple();
    buf->Env_Map_Scale = bssh->GetEnvironmentMapScale();
    //if (txtProp) {
    //    NiSyncVector<ShaderTexDesc>* txtdesc = &txtProp->shaderTex;
    //    //buf->Tex_Clamp_Mode = txtdesc->data.clampMode;
    //};
    buf->Alpha = bssh->GetAlpha();
    buf->Glossiness = bssh->GetGlossiness();
    buf->Spec_Color_R = bssh->GetSpecularColor().x;
    buf->Spec_Color_G = bssh->GetSpecularColor().y;
    buf->Spec_Color_B = bssh->GetSpecularColor().z;
    buf->Spec_Str = bssh->GetSpecularStrength();
    if (bslsp) {
        buf->Refraction_Str = bslsp->refractionStrength;
        buf->Soft_Lighting = bslsp->softlighting;
        buf->Rim_Light_Power = bslsp->rimlightPower;
        buf->Skin_Tint_Alpha = bslsp->skinTintAlpha;
        buf->Skin_Tint_Color_R = bslsp->skinTintColor[0];
        buf->Skin_Tint_Color_G = bslsp->skinTintColor[1];
        buf->Skin_Tint_Color_B = bslsp->skinTintColor[2];
    }
    if (bsesp) {
        buf->bufType = BUFFER_TYPES::BSEffectShaderPropertyBufType;
        buf->Tex_Clamp_Mode = bsesp->textureClampMode & 0xFF;
        //buf->Lighting_Influence = bsesp->light;
        //buf->Env_Map_Min_LOD = bsesp->getEnvmapMinLOD();
        buf->Falloff_Start_Angle = bsesp->falloffStartAngle;
        buf->Falloff_Stop_Angle = bsesp->falloffStopAngle;
        buf->Falloff_Start_Opacity = bsesp->falloffStartOpacity;
        buf->Falloff_Stop_Opacity = bsesp->falloffStopOpacity;
        buf->Soft_Falloff_Depth = bsesp->softFalloffDepth;
    }

    return 0;
};

int getNiAlphaProperty(void* nifref, uint32_t id, void* buffer) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiAlphaPropertyBuf* bufptr = static_cast<NiAlphaPropertyBuf*>(buffer);
    NiAlphaProperty* alph = hdr->GetBlock<NiAlphaProperty>(id);

    CheckID(alph);
    CheckBuf(bufptr, BUFFER_TYPES::NiAlphaPropertyBufType, NiAlphaPropertyBuf);

    bufptr->flags = alph->flags;
    bufptr->threshold = alph->threshold;
    return 0;
}

int setNiAlphaProperty(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiAlphaPropertyBuf* bufptr = static_cast<NiAlphaPropertyBuf*>(buffer);
    
    CheckBuf(bufptr, BUFFER_TYPES::NiAlphaPropertyBufType, NiAlphaPropertyBuf);
    auto alphaProp = std::make_unique<NiAlphaProperty>();
    alphaProp->flags = bufptr->flags;
    alphaProp->threshold = bufptr->threshold;

    if (parent != NIF_NPOS) {
        NiShape* shape = hdr->GetBlock<NiShape>(parent);
        nif->AssignAlphaProperty(shape, std::move(alphaProp));
    }
}

NIFLY_API void setShaderTextureSlot(void* nifref, void* shaperef, int slotIndex, const char* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    std::string texture = buf;

    nif->SetTextureSlot(shape, texture, slotIndex);
}

int setNiShader(void* nifref, const char* name, void* buffer, uint32_t parent) {
    /* Create a shader for the shape "parent". Shaders must have a parent. */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiShape* shape;
    NiShader* shader;
    NiShaderBuf* buf = static_cast<NiShaderBuf*>(buffer);
    
    if (parent == NIF_NPOS) return NIF_NPOS;
    shape = hdr->GetBlock<NiShape>(parent);
    shader = nif->GetShader(shape);

    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
    BSLightingShaderProperty* bslsp = dynamic_cast<BSLightingShaderProperty*>(shader);
    BSEffectShaderProperty* bsesp = dynamic_cast<BSEffectShaderProperty*>(shader);
    NiTexturingProperty* txtProp = nif->GetTexturingProperty(shape);

    if (buf->bufType == BSEffectShaderPropertyBufType && !bsesp) {
        // Caller wants a BSEffectShaderProperty and hasn't got one... switch it over.
        std::unique_ptr<BSEffectShaderProperty> sh = std::make_unique<BSEffectShaderProperty>();
        int sh_id = nif->GetHeader().AddBlock(std::move(sh));
        shape->ShaderPropertyRef()->Clear();
        shape->ShaderPropertyRef()->index = sh_id;
        shader = nif->GetShader(shape);
        bssh = dynamic_cast<BSShaderProperty*>(shader);
        bslsp = dynamic_cast<BSLightingShaderProperty*>(shader);
        bsesp = dynamic_cast<BSEffectShaderProperty*>(shader);
    }
    shader->name.get() = name;
    shader->SetShaderType(buf->Shader_Type);
    if (bssh) {
        bssh->shaderFlags1 = buf->Shader_Flags_1;
        bssh->shaderFlags2 = buf->Shader_Flags_2;
    };

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
    shader->SetEnvironmentMapScale(buf->Env_Map_Scale);
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
    if (bsesp) {
        bsesp->textureClampMode = buf->Tex_Clamp_Mode;
        bsesp->falloffStartAngle = buf->Falloff_Start_Angle;
        bsesp->falloffStopAngle = buf->Falloff_Stop_Angle;
        bsesp->falloffStartOpacity = buf->Falloff_Start_Opacity;
        bsesp->falloffStopOpacity = buf->Falloff_Stop_Opacity;
        bsesp->softFalloffDepth = buf->Soft_Falloff_Depth;
        bsesp->envMapScale = buf->Env_Map_Scale;
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

    try {
        NifSegmentationInfo inf;
        inf.ssfFile = filename;
        std::unordered_set<uint32_t> allParts;

        for (int i = 0; i < segDataLen; i++) {
            NifSegmentInfo* seg = new NifSegmentInfo();
            seg->partID = segData[i];
            inf.segs.push_back(*seg);
            allParts.insert(seg->partID);
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
                    allParts.insert(sseg.partID);
                    break;
                }
            }
        }

        std::vector<int> triParts;
        for (int i = 0; i < triLen; i++) {
            // Checking for invalid segment references explicitly because the try/catch isn't working
            if (allParts.find(tris[i]) == allParts.end()) {
                niflydll::LogWrite("ERROR: Tri list references invalid segment, segments are not correct");
                return;
            }
            else
                triParts.push_back(tris[i]);
        }
        nif->SetShapeSegments(shape, inf, triParts);
        nif->UpdateSkinPartitions(shape);
    }
    catch (std::exception e) {
        niflydll::LogWrite("Error in setSegments, segments may not be correct");
    }
}

/* ************************ VERTEX COLORS AND ALPHA ********************* */

NIFLY_API int getColorsForShape(void* nifref, void* shaperef, Color4* colors, int colorLen) {
    /*
        Return vertex colors.
        colorLen = # of floats buffer can hold, has to be 4x number of colors
        Return value is # of colors, which is # of vertices.
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    const std::vector<Color4>* theColors = nif->GetColorsForShape(shape->name.get());
    for (int i = 0, j = 0; j < colorLen && i < theColors->size(); i++, j += 4)
        colors[i] = theColors->at(i);

    return int(theColors->size());
}

NIFLY_API void setColorsForShape(void* nifref, void* shaperef, Color4* colors, int colorLen) {
    /*
        Set vertex colors.
        colorLen = # of color values in the buf, must be same as # of vertices
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);
    std::vector<Color4> theColors;
    for (int i = 0; i < colorLen; i++) {
        Color4 c = colors[i];
        theColors.push_back(c);
    }
    nif->SetColorsForShape(shape->name.get(), theColors);
}

/* ***************************** EXTRA DATA ***************************** */

const char* ClothExtraDataName = "Binary Data";
const int ClothExtraDataNameLen = 11;

int getClothExtraDataLen(void* nifref, void* shaperef, int idx, int* namelen, int* valuelen)
/* Treats the BSClothExtraData nodes in the nif like an array--idx indicates
    which to return (0-based).
    (Probably there can be only one per file but code allows for more)
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
        BSClothExtraData* clothData = hdr.GetBlock<BSClothExtraData>(extraData);
        if (clothData) {
            if (i == 0) {
                *valuelen = int(clothData->data.size());
                *namelen = ClothExtraDataNameLen;
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};

int getClothExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, char* buf, int buflen)
/* Treats the BSClothExtraData nodes in the nif like an array--idx indicates
    which to return (0-based).
    (Probably there can be only one per file but code allows for more)
    Returns 1 if the extra data was found at requested index
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
        BSClothExtraData* clothData = hdr.GetBlock<BSClothExtraData>(extraData);
        if (clothData) {
            if (i == 0) {
                for (uint32_t j = 0; j < (uint32_t) buflen && j < clothData->data.size(); j++) {
                    buf[j] = clothData->data[j];
                }
                strncpy_s(name, namelen, ClothExtraDataName, ClothExtraDataNameLen);
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};

void setClothExtraData(void* nifref, void* shaperef, char* name, char* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiAVObject* target = nullptr;
    target = nif->GetRootNode();

    if (target) {
        auto clothData = std::make_unique<BSClothExtraData>();
        for (int i = 0; i < buflen; i++) {
            clothData->data.push_back(buf[i]);
        }
        int id = nif->GetHeader().AddBlock(std::move(clothData));
        if (id != 0xFFFFFFFF) {
            target->extraDataRefs.AddBlockRef(id);
        }
    }
};

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
int getBGExtraData(void* nifref, void* shaperef, int idx, char* name, int namelen, 
        char* buf, int buflen, uint16_t* ctrlBaseSkelP)
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
                *ctrlBaseSkelP = bgData->controlsBaseSkel;
                return 1;
            }
            else
                i--;
        }
    }
    return 0;
};

int getInvMarker(void* nifref, uint32_t id, void* inbuf)
/* 
* Returns the InvMarker node data, if any. Assumes there is only one.
*   name = receives the name--will be null terminated
*   namelen = length of the name buffer
*   rot = int[3] for X, Y, Z
*   zoom = zoom value
* Return value = true/false whether a BSInvMarker exists
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BSInvMarkerBuf* buf = static_cast<BSInvMarkerBuf*>(inbuf);
    BSInvMarker* invm = hdr->GetBlock<BSInvMarker>(id);

    if (!invm) {
        niflydll::LogWrite("getInvMarker not passed an inventory marker node");
        return 1;
    }

    CheckBuf(buf, BUFFER_TYPES::BSInvMarkerBufType, BSInvMarkerBuf);

    std::vector<NiStringRef*> strs;
    invm->GetStringRefs(strs);
    buf->stringRefCount = strs.size();
    buf->nameID = invm->name.GetIndex();
    buf->rot[0] = invm->rotationX;
    buf->rot[1] = invm->rotationY;
    buf->rot[2] = invm->rotationZ;
    buf->zoom = invm->zoom;

    return 0;
};

int getConnectPointParent(void* nifref, int index, ConnectPointBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiAVObject* source = nif->GetRootNode();

    int c = 0;

    for (auto& ed : source->extraDataRefs) {
        BSConnectPointParents* cpl = hdr.GetBlock<BSConnectPointParents>(ed);
        if (cpl) {
            for (auto& cp : cpl->connectPoints) {
                if (c == index) {
                    strncpy_s(buf->parent, cp.root.get().c_str(), 256);
                    buf->parent[255] = '\0';
                    strncpy_s(buf->name, cp.variableName.get().c_str(), 256);
                    buf->name[255] = '\0';
                    assignQ(buf->rotation, cp.rotation);
                    for (int i = 0; i < 3; i++) buf->translation[i] = cp.translation[i];
                    buf->scale = cp.scale;

                    return 1;
                }
                c++;
            };
        };
    };
    return 0;
}

void setConnectPointsParent(void* nifref, int buflen, ConnectPointBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);

    auto cplist = std::make_unique<BSConnectPointParents>();
    cplist->name.get() = "CPA";

    for (int i = 0; i < buflen; i++) {
        BSConnectPoint cp;
        cp.root = NiString(buf[i].parent);
        cp.variableName = NiString(buf[i].name);
        cp.rotation.w = buf[i].rotation[0];
        cp.rotation.x = buf[i].rotation[1];
        cp.rotation.y = buf[i].rotation[2];
        cp.rotation.z = buf[i].rotation[3];
        for (int j = 0; j < 3; j++) cp.translation[j] = buf[i].translation[j];
        cp.scale = buf[i].scale;
        cplist->connectPoints.push_back(cp);
    }
    nif->AssignExtraData(nif->GetRootNode(), std::move(cplist));
}

int getConnectPointChild(void* nifref, int index, char* buf) {
    /* Return child connect point information 
    *   index: connect point to return
    *   buf: associated name, must accept 256 characters
        returns 0: no child at index; -1: not skinned; 1: skinned */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiAVObject* source = nif->GetRootNode();

    int c = 0;

    for (auto& ed : source->extraDataRefs) {
        BSConnectPointChildren* cpl = hdr.GetBlock<BSConnectPointChildren>(ed);
        if (cpl) {
            for (auto& cp : cpl->targets) {
                if (c == index) {
                    strncpy_s(buf, 256, cp.get().c_str(), cp.length());
                    return cpl->skinned? 1: -1;
                }
                c++;
            };
        };
    };
    return 0;
}

void setConnectPointsChild(void* nifref, int isSkinned, int buflen, const char* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);

    auto cplist = std::make_unique<BSConnectPointChildren>();
    cplist->name.get() = "CPT";
    cplist->skinned = isSkinned;

    for (size_t i = 0; i < buflen; ) {
        NiString s = NiString(&buf[i]);
        cplist->targets.push_back(s);
        i += s.length() + 1;
    }
    nif->AssignExtraData(nif->GetRootNode(), std::move(cplist));
}

int getFurnMarker(void* nifref, int index, FurnitureMarkerBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiAVObject* source = nif->GetRootNode();

    int c = 0;

    for (auto& ed : source->extraDataRefs) {
        BSFurnitureMarker* fm = hdr.GetBlock<BSFurnitureMarker>(ed);
        if (fm) {
            for (auto& pos : fm->positions) {
                if (c == index) {
                    for (int i = 0; i < 3; i++) buf->offset[i] = pos.offset[i];
                    buf->heading = pos.heading;
                    buf->animationType = pos.animationType;
                    buf->entryPoints = pos.entryPoints;

                    return 1;
                }
                c++;
            };
        };
    };
    return 0;
}

void setFurnMarkers(void* nifref, int buflen, FurnitureMarkerBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);

    auto fm = std::make_unique<BSFurnitureMarkerNode>();
    
    for (int i=0; i < buflen; i++) {
        FurniturePosition pos;
        for (int j = 0; j < 3; j++) pos.offset[j] = buf[i].offset[j];
        pos.heading = buf[i].heading;
        pos.animationType = buf[i].animationType;
        pos.entryPoints = buf[i].entryPoints;
        fm->positions.push_back(pos);
    }
    nif->AssignExtraData(nif->GetRootNode(), std::move(fm));
}

//void setInvMarker(void* nifref, const char* name, int* rot, float* zoom)
int setInvMarker(void* nifref, const char* name, void* buffer, uint32_t parent)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BSInvMarkerBuf* buf = static_cast<BSInvMarkerBuf*>(buffer);

    auto inv = std::make_unique<BSInvMarker>();
    inv->name.get() = name;
    inv->rotationX = buf->rot[0];
    inv->rotationY = buf->rot[1];
    inv->rotationZ = buf->rot[2];
    inv->zoom = buf->zoom;
    
    NiAVObject* p = hdr->GetBlock<NiAVObject>(parent);
   return nif->AssignExtraData(p, std::move(inv));
}

int getBSXFlags(void* nifref, uint32_t id, void* inbuf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BSXFlags* f = hdr->GetBlock<BSXFlags>(id);
    BSXFlagsBuf* buf = static_cast<BSXFlagsBuf*>(inbuf);

    if (!f) {
        niflydll::LogWrite("getBSXFlags not passed an BSX Flags node");
        return 1;
    }

    CheckBuf(buf, BUFFER_TYPES::BSXFlagsBufType, BSXFlagsBuf);

    buf->integerData = f->integerData;
    return 0;
}

int setBSXFlags(void* nifref, const char* name, void* buffer, uint32_t parent)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BSXFlagsBuf* buf = static_cast<BSXFlagsBuf*>(buffer);

    CheckBuf(buf, BUFFER_TYPES::BSXFlagsBufType, BSXFlagsBuf);

    auto bsx = std::make_unique<BSXFlags>();
    bsx->name.get() = name;
    bsx->integerData = buf->integerData;
    return nif->AssignExtraData(hdr->GetBlock<NiNode>(parent), std::move(bsx));
}

void setBGExtraData(void* nifref, void* shaperef, char* name, char* buf, int controlsBaseSkel) {
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
        strdata->controlsBaseSkel = controlsBaseSkel;
        nif->AssignExtraData(target, std::move(strdata));
    }
};

/* ********************* ERROR REPORTING ********************* */

void clearMessageLog() {
    niflydll::LogInit();
};

int getMessageLog(char* buf, int buflen) {
    if (buf)
        return niflydll::LogGet(buf, buflen);
    else
        return niflydll::LogGetLen();
    //return niflydll::LogGetLen();
}


/* ***************************** COLLISION OBJECTS ***************************** */


int getCollisionObject(void* nifref, uint32_t blockID, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiCollisionObjectBuf* coBuf = static_cast<NiCollisionObjectBuf*>(inbuf);
    NiCollisionObject* node = hdr->GetBlock<NiCollisionObject>(blockID);

    CheckID(node);

    if (coBuf->bufSize < sizeof(NiCollisionObjectBuf)) {
        niflydll::LogWrite("ERROR: NiCollisionObjectBuf buffer wrong size.");
        return 2;
    }

    coBuf->targetID = node->targetRef.index;

    if (coBuf->bufType == BUFFER_TYPES::bhkNiCollisionObjectBufType ||
        coBuf->bufType == BUFFER_TYPES::bhkCollisionObjectBufType ||
        coBuf->bufType == BUFFER_TYPES::bhkPCollisionObjectBufType ||
        coBuf->bufType == BUFFER_TYPES::bhkSPCollisionObjectBufType) {
        bhkCollisionObjectBuf* collbuf = static_cast<bhkCollisionObjectBuf*>(inbuf);
        bhkNiCollisionObject* collNode = hdr->GetBlock<bhkNiCollisionObject>(blockID);
        std::vector<uint32_t> ch;
        node->GetChildIndices(ch);
        collbuf->bodyID = collNode->bodyRef.index;
        collbuf->flags = collNode->flags;
        collbuf->childCount = ch.size();
    }
    return 0;
};

int getBlendCollisionObject(void* nifref, uint32_t blockID, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkBlendCollisionObjectBuf* coBuf = static_cast<bhkBlendCollisionObjectBuf*>(inbuf);
    bhkBlendCollisionObject* node = hdr->GetBlock<bhkBlendCollisionObject>(blockID);

    CheckID(node);

    if (coBuf->bufSize < sizeof(bhkBlendCollisionObjectBuf)) {
        niflydll::LogWrite("ERROR: getBlendCollisionObject buffer wrong size.");
        return 2;
    }

    coBuf->targetID = node->targetRef.index;

    std::vector<uint32_t> ch;
    node->GetChildIndices(ch);
    coBuf->bodyID = node->bodyRef.index;
    coBuf->flags = node->flags;
    coBuf->childCount = ch.size();
    coBuf->heirGain = node->heirGain;
    coBuf->velGain = node->velGain;

    return 0;
};

void* getCollision(void* nifref, void* noderef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiNode* node = static_cast<nifly::NiNode*>(noderef);

    return hdr.GetBlock(node->collisionRef);
};

int setCollision(void* nifref, uint32_t id, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiCollisionObjectBuf* coBuf = static_cast<NiCollisionObjectBuf*>(inbuf);
    NiNode* theTarget = nullptr;
    uint32_t targetIndex = NIF_NPOS;
    uint32_t newid = NIF_NPOS;
    NiCollisionObject* co = hdr->GetBlock<NiCollisionObject>(id);

    CheckID(co);

    if (coBuf->targetID != NIF_NPOS) {
        NiAVObject* theTarget = hdr->GetBlock<NiAVObject>(coBuf->targetID);
        theTarget->collisionRef.index = newid;
    }

    if (coBuf->bufType == BUFFER_TYPES::bhkCollisionObjectBufType) {
        bhkCollisionObjectBuf* collBuf = static_cast<bhkCollisionObjectBuf*>(inbuf);
        bhkCollisionObject* c = static_cast<bhkCollisionObject*>(co);
        if (!c) {
            niflydll::LogWrite("ERROR: Node is not a bhkCollisionObject.");
            return 1;
        }
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkNiCollisionObjectBufType) {
        bhkNiCollisionObjectBuf* collBuf = static_cast<bhkNiCollisionObjectBuf*>(inbuf);
        bhkNiCollisionObject* c = static_cast<bhkNiCollisionObject*>(co);
        if (!c) {
            niflydll::LogWrite("ERROR: Node is not a bhkNiCollisionObject.");
            return 1;
        }
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkCollisionObjectBufType) {
        bhkCollisionObjectBuf* collBuf = static_cast<bhkCollisionObjectBuf*>(inbuf);
        bhkCollisionObject* c = static_cast<bhkCollisionObject*>(co);
        if (!c) {
            niflydll::LogWrite("ERROR: Node is not a bhkCollisionObject.");
            return 1;
        }
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkPCollisionObjectBufType) {
        bhkPCollisionObjectBuf* collBuf = static_cast<bhkPCollisionObjectBuf*>(inbuf);
        bhkPCollisionObject* c = static_cast<bhkPCollisionObject*>(co);
        if (!c) {
            niflydll::LogWrite("ERROR: Node is not a bhkPCollisionObject.");
            return 1;
        }
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkSPCollisionObjectBufType) {
        bhkSPCollisionObjectBuf* collBuf = static_cast<bhkSPCollisionObjectBuf*>(inbuf);
        bhkSPCollisionObject* c = static_cast<bhkSPCollisionObject*>(co);
        if (!c) {
            niflydll::LogWrite("ERROR: Node is not a bhkSPCollisionObject.");
            return 1;
        }
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
    }

    return 0;

};

int addCollision(void* nifref, const char* name, void* buf, uint32_t parent) 
/* 
*  name - ignored
*  buf - properties
*  parent - target object; if NIF_NPOS then get target from buf
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiCollisionObjectBuf* coBuf = static_cast<NiCollisionObjectBuf*>(buf);
    NiNode* theTarget = nullptr;
    uint32_t targetIndex = NIF_NPOS;
    uint32_t newid = NIF_NPOS;

    if (parent != NIF_NPOS) {
        targetIndex = parent;
        theTarget = hdr->GetBlock<NiNode>(parent);
    }
    else if (coBuf->targetID != NIF_NPOS) {
        targetIndex = coBuf->targetID;
        theTarget = hdr->GetBlock<NiNode>(coBuf->targetID);
    }
    else {
        targetIndex = 0;
        theTarget = nif->GetRootNode();
    }

    if (coBuf->bufType == BUFFER_TYPES::bhkCollisionObjectBufType) {
        bhkCollisionObjectBuf* collBuf = static_cast<bhkCollisionObjectBuf*>(buf);
        auto c = std::make_unique<bhkCollisionObject>();
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
        newid = nif->GetHeader().AddBlock(std::move(c));
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkNiCollisionObjectBufType) {
        bhkNiCollisionObjectBuf* collBuf = static_cast<bhkNiCollisionObjectBuf*>(buf);
        auto c = std::make_unique<bhkNiCollisionObject>();
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
        newid = nif->GetHeader().AddBlock(std::move(c));
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkCollisionObjectBufType) {
        bhkCollisionObjectBuf* collBuf = static_cast<bhkCollisionObjectBuf*>(buf);
        auto c = std::make_unique<bhkCollisionObject>();
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
        newid = nif->GetHeader().AddBlock(std::move(c));
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkPCollisionObjectBufType) {
        bhkPCollisionObjectBuf* collBuf = static_cast<bhkPCollisionObjectBuf*>(buf);
        auto c = std::make_unique<bhkPCollisionObject>();
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
        newid = nif->GetHeader().AddBlock(std::move(c));
    }
    else if (coBuf->bufType == BUFFER_TYPES::bhkSPCollisionObjectBufType) {
        bhkSPCollisionObjectBuf* collBuf = static_cast<bhkSPCollisionObjectBuf*>(buf);
        auto c = std::make_unique<bhkSPCollisionObject>();
        c->bodyRef.index = collBuf->bodyID;
        c->targetRef.index = targetIndex;
        c->flags = collBuf->flags;
        newid = nif->GetHeader().AddBlock(std::move(c));
    }

    if (theTarget) theTarget->collisionRef.index = newid;
    
    return newid;
};

int setRigidBody(void* nifref, uint32_t blockID, void* buffer) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkRigidBodyBuf* buf = static_cast<bhkRigidBodyBuf*>(buffer);
    bhkRigidBody* theBody = hdr->GetBlock<bhkRigidBody>(blockID);

    CheckID(theBody);

    if ((buf->bufType != BUFFER_TYPES::bhkRigidBodyBufType && buf->bufType != BUFFER_TYPES::bhkRigidBodyTBufType)
            || buf->bufSize != sizeof(bhkRigidBodyBuf)) {
		niflydll::LogWriteEf("%s called with bad buffer: type=%d, size=%d.", __FUNCTION__, buf->bufType, buf->bufSize); \
        return 2;
    }

    theBody->collisionFilter.layer = buf->collisionFilter_layer;
    theBody->collisionFilter.flagsAndParts = buf->collisionFilter_flags;
    theBody->collisionFilter.group = buf->collisionFilter_group;
    theBody->broadPhaseType = buf->broadPhaseType;
    theBody->prop.data = buf->prop_data;
    theBody->prop.size = buf->prop_size;
    theBody->prop.capacityAndFlags = buf->prop_flags;
    theBody->collisionResponse = static_cast<hkResponseType>(buf->collisionResponse);
    theBody->processContactCallbackDelay = buf->processContactCallbackDelay;
    theBody->collisionFilterCopy.layer = buf->collisionFilterCopy_layer;
    theBody->collisionFilterCopy.flagsAndParts = buf->collisionFilterCopy_flags;
    theBody->collisionFilterCopy.group = buf->collisionFilterCopy_group;
    theBody->translation.x = buf->translation_x;
    theBody->translation.y = buf->translation_y;
    theBody->translation.z = buf->translation_z;
    theBody->translation.w = buf->translation_w;
    theBody->rotation.x = buf->rotation_x;
    theBody->rotation.y = buf->rotation_y;
    theBody->rotation.z = buf->rotation_z;
    theBody->rotation.w = buf->rotation_w;
    theBody->linearVelocity.x = buf->linearVelocity_x;
    theBody->linearVelocity.y = buf->linearVelocity_y;
    theBody->linearVelocity.z = buf->linearVelocity_z;
    theBody->linearVelocity.w = buf->linearVelocity_w;
    theBody->angularVelocity.x = buf->angularVelocity_x;
    theBody->angularVelocity.y = buf->angularVelocity_y;
    theBody->angularVelocity.z = buf->angularVelocity_z;
    theBody->angularVelocity.w = buf->angularVelocity_w;
    for (int i = 0; i < 12; i++) theBody->inertiaMatrix[i] = buf->inertiaMatrix[i];
    theBody->center.x = buf->center_x;
    theBody->center.y = buf->center_y;
    theBody->center.z = buf->center_z;
    theBody->center.w = buf->center_w;
    theBody->mass = buf->mass;
    theBody->linearDamping = buf->linearDamping;
    theBody->angularDamping = buf->angularDamping;
    theBody->timeFactor = buf->timeFactor;
    theBody->gravityFactor = buf->gravityFactor;
    theBody->friction = buf->friction;
    theBody->rollingFrictionMult = buf->rollingFrictionMult;
    theBody->restitution = buf->restitution;
    theBody->maxLinearVelocity = buf->maxLinearVelocity;
    theBody->maxAngularVelocity = buf->maxAngularVelocity;
    theBody->penetrationDepth = buf->penetrationDepth;
    theBody->motionSystem = buf->motionSystem;
    theBody->deactivatorType = buf->deactivatorType;
    theBody->solverDeactivation = buf->solverDeactivation;
    theBody->qualityType = buf->qualityType;
    theBody->autoRemoveLevel = buf->autoRemoveLevel;
    theBody->responseModifierFlag = buf->responseModifierFlag;
    theBody->numShapeKeysInContactPointProps = buf->numShapeKeysInContactPointProps;
    theBody->forceCollideOntoPpu = buf->forceCollideOntoPpu;
    theBody->bodyFlagsInt = buf->bodyFlagsInt;
    theBody->bodyFlags = buf->bodyFlags;
    theBody->shapeRef.index = buf->shapeID;

    return 0;
};

int addRigidBody(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkRigidBodyBuf* buf = static_cast<bhkRigidBodyBuf*>(buffer);

    std::unique_ptr<bhkRigidBody> theBody;
    if (buf->bufType == bhkRigidBodyTBufType)
        theBody = std::make_unique<bhkRigidBodyT>();
    else
        theBody = std::make_unique<bhkRigidBody>();

    int newid = nif->GetHeader().AddBlock(std::move(theBody));

    if (setRigidBody(nifref, newid, buffer) == 0)
        if (parent != NIF_NPOS) {
            bhkNiCollisionObject* coll = hdr->GetBlock<bhkNiCollisionObject>(parent);
            if (coll) coll->bodyRef.index = newid;
        }

    return newid;
};

NIFLY_API void* getCollTarget(void* nifref, void* node) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkCollisionObject* theNode = static_cast<nifly::bhkCollisionObject*>(node);
    if (theNode)
        return hdr.GetBlock(theNode->targetRef);
    else
        return nullptr;
}

NIFLY_API int getCollFlags(void* node) {
    nifly::bhkCollisionObject* theNode = static_cast<nifly::bhkCollisionObject*>(node);
    if (theNode) {
        return theNode->flags;
    }
    else
        return 0;
}

NIFLY_API int getCollBodyBlockname(void* nifref, int nodeIndex, char* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkRigidBody* theBody = hdr.GetBlock<bhkRigidBody>(nodeIndex);

    if (theBody) {
        std::string name = theBody->GetBlockName();
        int copylen = std::min((int)buflen - 1, (int)name.length());
        name.copy(buf, copylen, 0);
        buf[copylen] = '\0';
        return int(name.length());
    }
    else
        return 0;
}

int getRigidBodyProps(void* nifref, uint32_t nodeIndex, void* inbuf)
/*
    Return the rigid body details. Return value = 1 if the node is a rigid body, 0 if not 
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::bhkWorldObject* theWO = hdr->GetBlock<bhkWorldObject>(nodeIndex);
    nifly::bhkRigidBody* theBody = hdr->GetBlock<bhkRigidBody>(nodeIndex);
    nifly::bhkRigidBody* theBodyT = hdr->GetBlock<bhkRigidBodyT>(nodeIndex);
    bhkRigidBodyBuf* buf = static_cast<bhkRigidBodyBuf*>(inbuf);

    if (!theWO and !theBody) {
        niflydll::LogWrite("ERROR: Node is not a bhkRigidBody.");
        return 1;
    }
    if (buf->bufSize != sizeof(bhkRigidBodyBuf)) {
        niflydll::LogWrite("getRigidBodyProps given wrong size buffer");
        return 2;
    }

    if (theBodyT) buf->bufType = BUFFER_TYPES::bhkRigidBodyTBufType;
    else buf->bufType = BUFFER_TYPES::bhkRigidBodyBufType;

    if (theWO) {
        std::vector<uint32_t> ch;
        theWO->GetChildIndices(ch);
        buf->childCount = ch.size();
        buf->shapeID = theWO->shapeRef.index;
        buf->collisionFilter_layer = theWO->collisionFilter.layer;
        buf->collisionFilter_flags = theWO->collisionFilter.flagsAndParts;
        buf->collisionFilter_group = theWO->collisionFilter.group;
        buf->broadPhaseType = theWO->broadPhaseType;
        buf->prop_data = theWO->prop.data;
        buf->prop_size = theWO->prop.size;
        buf->prop_flags = theWO->prop.capacityAndFlags;
    }
    if (theBody) {
        buf->collisionResponse = theBody->collisionResponse;
        buf->processContactCallbackDelay = theBody->processContactCallbackDelay;
        buf->collisionFilterCopy_layer = theBody->collisionFilterCopy.layer;
        buf->collisionFilterCopy_flags = theBody->collisionFilterCopy.flagsAndParts;
        buf->collisionFilterCopy_group = theBody->collisionFilterCopy.group;
        buf->translation_x = theBody->translation.x;
        buf->translation_y = theBody->translation.y;
        buf->translation_z = theBody->translation.z;
        buf->translation_w = theBody->translation.w;
        buf->rotation_x = theBody->rotation.x;
        buf->rotation_y = theBody->rotation.y;
        buf->rotation_z = theBody->rotation.z;
        buf->rotation_w = theBody->rotation.w;
        buf->linearVelocity_x = theBody->linearVelocity.x;
        buf->linearVelocity_y = theBody->linearVelocity.y;
        buf->linearVelocity_z = theBody->linearVelocity.z;
        buf->linearVelocity_w = theBody->linearVelocity.w;
        buf->angularVelocity_x = theBody->angularVelocity.x;
        buf->angularVelocity_y = theBody->angularVelocity.y;
        buf->angularVelocity_z = theBody->angularVelocity.z;
        buf->angularVelocity_w = theBody->angularVelocity.w;
        for (int i=0; i < 12; i++) buf->inertiaMatrix[i] = theBody->inertiaMatrix[i];
        buf->center_x = theBody->center.x;
        buf->center_y = theBody->center.y;
        buf->center_z = theBody->center.z;
        buf->center_w = theBody->center.w;
        buf->mass = theBody->mass;
        buf->linearDamping = theBody->linearDamping;
        buf->angularDamping = theBody->angularDamping;
        buf->timeFactor = theBody->timeFactor;
        buf->gravityFactor = theBody->gravityFactor;
        buf->friction = theBody->friction;
        buf->rollingFrictionMult = theBody->rollingFrictionMult;
        buf->restitution = theBody->restitution;
        buf->maxLinearVelocity = theBody->maxLinearVelocity;
        buf->maxAngularVelocity = theBody->maxAngularVelocity;
        buf->penetrationDepth = theBody->penetrationDepth;
        buf->motionSystem = theBody->motionSystem;
        buf->deactivatorType = theBody->deactivatorType;
        buf->solverDeactivation = theBody->solverDeactivation;
        buf->qualityType = theBody->qualityType;
        buf->autoRemoveLevel = theBody->autoRemoveLevel;
        buf->responseModifierFlag = theBody->responseModifierFlag;
        buf->numShapeKeysInContactPointProps = theBody->numShapeKeysInContactPointProps;
        buf->forceCollideOntoPpu = theBody->forceCollideOntoPpu;
        buf->constraintCount = theBody->constraintRefs.GetSize();
        buf->bodyFlagsInt = theBody->bodyFlagsInt;
        buf->bodyFlags = theBody->bodyFlags;
    }
    return 0;
}

int getSimpleShapePhantom(void* nifref, uint32_t nodeIndex, void* inbuf)
/*
    Return the rigid body details. Return value = 1 if the node is a rigid body, 0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::bhkSimpleShapePhantom* theBody = hdr->GetBlock<bhkSimpleShapePhantom>(nodeIndex);
    bhkSimpleShapePhantomBuf* buf = static_cast<bhkSimpleShapePhantomBuf*>(inbuf);

    CheckID(theBody);
    CheckBuf(buf, BUFFER_TYPES::bhkSimpleShapePhantomBufType, bhkSimpleShapePhantomBuf);

    std::vector<uint32_t> ch;
    theBody->GetChildIndices(ch);
    buf->childCount = ch.size();
    buf->shapeID = theBody->shapeRef.index;
    buf->collisionFilter_layer = theBody->collisionFilter.layer;
    buf->collisionFilter_flags = theBody->collisionFilter.flagsAndParts;
    buf->collisionFilter_group = theBody->collisionFilter.group;
    buf->broadPhaseType = theBody->broadPhaseType;
    buf->prop_data = theBody->prop.data;
    buf->prop_size = theBody->prop.size;
    buf->prop_flags = theBody->prop.capacityAndFlags;
    buf->transform = theBody->transform;

    return 0;
}



NIFLY_API int getRigidBodyConstraints(void* nifref, uint32_t nodeIndex, uint32_t* idList, int buflen)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkRigidBody* rb = hdr->GetBlock<bhkRigidBody>(nodeIndex);

    CheckID(rb);

    std::vector<uint32_t> constraintList;
    for (int i = 0; i < buflen; i++) {
        rb->constraintRefs.GetIndices(constraintList);
        idList[i] = constraintList[i];
    }

    return constraintList.size();
}

int getRagdollConstraint(void* nifref, uint32_t nodeIndex, void* inbuf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkRagdollConstraint* rd = hdr->GetBlock<bhkRagdollConstraint>(nodeIndex);
    bhkRagdollConstraintBuf* buf = static_cast<bhkRagdollConstraintBuf*>(inbuf);

    CheckID(rd);
    CheckBuf(buf, BUFFER_TYPES::bhkRagdollConstraintBufType, bhkRagdollConstraintBuf);

    buf->entityCount = rd->entityRefs.GetSize();
    buf->priority = rd->priority;
    buf->twistA = rd->ragdoll.twistA;
    buf->planeA = rd->ragdoll.planeA;
    buf->motorA = rd->ragdoll.motorA;
    buf->pivotA = rd->ragdoll.pivotA;
    buf->twistB = rd->ragdoll.twistB;
    buf->planeB = rd->ragdoll.planeB;
    buf->motorB = rd->ragdoll.motorB;
    buf->pivotB = rd->ragdoll.pivotB;
    buf->coneMaxAngle = rd->ragdoll.coneMaxAngle;
    buf->planeMinAngle = rd->ragdoll.planeMinAngle;
    buf->planeMaxAngle = rd->ragdoll.planeMaxAngle;
    buf->twistMinAngle = rd->ragdoll.twistMinAngle;
    buf->twistMaxAngle = rd->ragdoll.twistMaxAngle;
    buf->maxFriction = rd->ragdoll.maxFriction;
    buf->motorType = rd->ragdoll.motorDesc.motorType;
    buf->positionConstraint_tau = rd->ragdoll.motorDesc.motorPosition.tau;
    buf->positionConstraint_damping = rd->ragdoll.motorDesc.motorPosition.damping;
    buf->positionConstraint_propRV = rd->ragdoll.motorDesc.motorPosition.proportionalRecoveryVelocity;
    buf->positionConstraint_constRV = rd->ragdoll.motorDesc.motorPosition.constantRecoveryVelocity;
    buf->velocityConstraint_tau = rd->ragdoll.motorDesc.motorVelocity.tau;
    buf->velocityConstraint_velocityTarget = rd->ragdoll.motorDesc.motorVelocity.velocityTarget;
    buf->velocityConstraint_useVTFromCT = rd->ragdoll.motorDesc.motorVelocity.useVelocityTargetFromConstraintTargets;
    buf->springDamp_springConstant = rd->ragdoll.motorDesc.motorSpringDamper.springConstant;
    buf->springDamp_springDamping = rd->ragdoll.motorDesc.motorSpringDamper.springDamping;

    return 0;
}

NIFLY_API int getRagdollEntities(void* nifref, uint32_t nodeIndex, uint32_t* idList, int buflen)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkRagdollConstraint* rd = hdr->GetBlock<bhkRagdollConstraint>(nodeIndex);

    CheckID(rd);

    std::vector<uint32_t> entityList;
    for (int i = 0; i < buflen; i++) {
        rd->entityRefs.GetIndices(entityList);
        idList[i] = entityList[i];
    }

    return entityList.size();
}

void addCollisionChild(NifFile* nif, uint32_t parent, uint32_t childID) {
    /* Make the child the sub-shape of the parent collision shape thing. */
    if (parent == NIF_NPOS) return;

    NiHeader* hdr = &nif->GetHeader();
    bhkRigidBody* rb = hdr->GetBlock<bhkRigidBody>(parent);
    if (rb) {
        rb->shapeRef.index = childID;
        return;
    }

    bhkWorldObject* wo = hdr->GetBlock<bhkWorldObject>(parent);
    if (wo) {
        wo->shapeRef.index = childID;
    }

    bhkConvexTransformShape* cts = hdr->GetBlock<bhkConvexTransformShape>(parent);
    if (cts) {
        cts->shapeRef.index = childID;
        return;
    }

    bhkListShape* ls = hdr->GetBlock<bhkListShape>(parent);
    if (ls) {
        ls->subShapeRefs.AddBlockRef(childID);
        return;
    }

}

NIFLY_API int getCollConvexVertsShapeProps(void* nifref, uint32_t nodeIndex, void* buffer)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKConvexVertsShapeBuf* buf = static_cast<BHKConvexVertsShapeBuf*>(buffer);
    bhkConvexVerticesShape* sh = hdr->GetBlock<bhkConvexVerticesShape>(nodeIndex);

    CheckID(sh);
    CheckBuf(buf, BUFFER_TYPES::bhkConvexVerticesShapeBufType, BHKConvexVertsShapeBuf);

    buf->material = sh->GetMaterial();
    buf->radius = sh->radius;
    buf->vertsProp_data = sh->vertsProp.data;
    buf->vertsProp_size = sh->vertsProp.size;
    buf->vertsProp_flags = sh->vertsProp.capacityAndFlags;
    buf->normalsProp_data = sh->normalsProp.data;
    buf->normalsProp_size = sh->normalsProp.size;
    buf->normalsProp_flags = sh->normalsProp.capacityAndFlags;
    buf->vertsCount = sh->verts.size();
    buf->normalsCount = sh->normals.size();

    return 0;
};

int addCollConvexVertsShape(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKConvexVertsShapeBuf* buf = static_cast<BHKConvexVertsShapeBuf*>(buffer);

    auto sh = std::make_unique<bhkConvexVerticesShape>();
    sh->SetMaterial(buf->material);
    sh->radius = buf->radius;
    int newid = nif->GetHeader().AddBlock(std::move(sh));
    addCollisionChild(nif, parent, newid);
    return newid;
};

NIFLY_API int setCollConvexVerts(
        void* nifref, int id, float* verts, int vertcount, float* normals, int normcount) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkConvexVerticesShape* sh = hdr->GetBlock<bhkConvexVerticesShape>(id);

    CheckID(sh);

    for (int i = 0; i < vertcount * 4; i += 4) {
        Vector4 v = Vector4(verts[i], verts[i + 1], verts[i + 2], verts[i + 3]);
        sh->verts.push_back(v);
    };
    for (int i = 0; i < normcount * 4; i += 4) {
        Vector4 n = Vector4(normals[i], normals[i + 1], normals[i + 2], normals[i + 3]);
        sh->normals.push_back(n);
    }

    return 0;
};

NIFLY_API int getCollShapeVerts(void* nifref, int nodeIndex, float* buf, int buflen)
/*
    Return the collision shape vertices. Return number of vertices in shape. *buf may be null.
    buflen = number of verts the buffer can receive, so buf must be 4x this size.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    int vertCount = 0;

    nifly::bhkConvexVerticesShape* sh = hdr.GetBlock<bhkConvexVerticesShape>(nodeIndex);

    if (sh) {
        vertCount = sh->verts.size();
        for (int i = 0, j = 0; i < vertCount && j < buflen*4; i++) {
            buf[j++] = sh->verts[i].x;
            buf[j++] = sh->verts[i].y;
            buf[j++] = sh->verts[i].z;
            buf[j++] = sh->verts[i].w;
        };
        return vertCount;
    }
    else
        return 0;
}

NIFLY_API int getCollShapeNormals(void* nifref, int nodeIndex, float* buf, int buflen)
/*
    Return the collision shape vertices. Return number of vertices in shape. *buf may be null.
    buflen = number of verts the buffer can receive, so buf must be 4x this size.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    int vertCount = 0;

    nifly::bhkConvexVerticesShape* sh = hdr.GetBlock<bhkConvexVerticesShape>(nodeIndex);

    if (sh) {
        vertCount = sh->normals.size();
        for (int i = 0, j = 0; i < vertCount && j < buflen*4; i++) {
            buf[j++] = sh->normals[i].x;
            buf[j++] = sh->normals[i].y;
            buf[j++] = sh->normals[i].z;
            buf[j++] = sh->normals[i].w;
        };
        return vertCount;
    }
    else
        return 0;
}

int getCollBoxShapeProps(void* nifref, uint32_t nodeIndex, void* inbuf)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape, 
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::bhkBoxShape* sh = hdr->GetBlock<bhkBoxShape>(nodeIndex);
    bhkBoxShapeBuf* buf = static_cast<bhkBoxShapeBuf*>(inbuf);

    CheckBuf(buf, BUFFER_TYPES::bhkBoxShapeBufType, bhkBoxShapeBuf);

    if (!sh) {
        niflydll::LogWrite("getCollBoxShapeProps given wrong type of block");
        return 2;
    }

    buf->material = sh->GetMaterial();
    buf->radius = sh->radius;
    buf->dimensions_x = sh->dimensions.x;
    buf->dimensions_y = sh->dimensions.y;
    buf->dimensions_z = sh->dimensions.z;
    return 0;
}

int addCollBoxShape(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkBoxShapeBuf* buf = static_cast<bhkBoxShapeBuf*>(buffer);

    auto sh = std::make_unique<bhkBoxShape>();
    sh->SetMaterial(buf->material);
    sh->radius = buf->radius;
    sh->dimensions.x = buf->dimensions_x;
    sh->dimensions.y = buf->dimensions_y;
    sh->dimensions.z = buf->dimensions_z;
    int newid = hdr->AddBlock(std::move(sh));

    addCollisionChild(nif, parent, newid);

    return newid;
};

NIFLY_API int getCollListShapeProps(void* nifref, uint32_t nodeIndex, void* buffer)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKListShapeBuf* buf = static_cast<BHKListShapeBuf*>(buffer);
    nifly::bhkListShape* sh = hdr->GetBlock<bhkListShape>(nodeIndex);

    CheckID(sh);
    CheckBuf(buf, BUFFER_TYPES::bhkListShapeBufType, BHKListShapeBuf);

    buf->material = sh->GetMaterial();
    buf->childShape_data = sh->childShapeProp.data;
    buf->childShape_size = sh->childShapeProp.size;
    buf->childShape_flags = sh->childShapeProp.capacityAndFlags;
    buf->childFilter_data = sh->childFilterProp.data;
    buf->childFilter_size = sh->childFilterProp.size;
    buf->childFilter_flags = sh->childFilterProp.capacityAndFlags;

    std::vector<uint32_t> children;
    sh->GetChildIndices(children);
    buf->childCount = children.size(); 
    return 0;
}

NIFLY_API int getCollListShapeChildren(void* nifref, int nodeIndex, uint32_t* buf, int buflen)
/*
    Return the collision shape children.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    int childCount = 0;

    nifly::bhkListShape* sh = hdr.GetBlock<bhkListShape>(nodeIndex);

    if (sh) {
        std::vector<uint32_t> children;
        sh->GetChildIndices(children);
        childCount = int(children.size());
        for (int i = 0; i < childCount && i < buflen; i++) {
            buf[i] = children[i];
        };
        return childCount;
    }
    else
        return 0;
}

NIFLY_API int addCollListShape(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKListShapeBuf* buf = static_cast<BHKListShapeBuf*>(buffer);

    auto sh = std::make_unique<bhkListShape>();
    sh->SetMaterial(buf->material);
    sh->childShapeProp.data = buf->childShape_data;
    sh->childShapeProp.size = buf->childShape_size;
    sh->childShapeProp.capacityAndFlags = buf->childShape_flags;
    sh->childFilterProp.data = buf->childFilter_data;
    sh->childFilterProp.size = buf->childFilter_size;
    sh->childFilterProp.capacityAndFlags = buf->childFilter_flags;
    int newid = nif->GetHeader().AddBlock(std::move(sh));

    addCollisionChild(nif, parent, newid);

    return newid;
};

NIFLY_API void addCollListChild(void* nifref, const uint32_t id, uint32_t child_id) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkListShape* collList = hdr->GetBlock<bhkListShape>(id);

   collList->subShapeRefs.AddBlockRef(child_id);
};

int getCollConvexTransformShapeProps(
    void* nifref, uint32_t nodeIndex, void* buffer)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKConvexTransformShapeBuf* buf = static_cast<BHKConvexTransformShapeBuf*>(buffer);
    bhkConvexTransformShape* sh = hdr->GetBlock<bhkConvexTransformShape>(nodeIndex);

    CheckID(sh);
    CheckBuf(buf, BUFFER_TYPES::bhkConvexTransformShapeBufType, BHKConvexTransformShapeBuf);
    
    buf->shapeID = sh->shapeRef.index;
    buf->material = sh->material;
    buf->radius = sh->radius;
    for (int i = 0; i < 16; i++) {
        buf->xform[i] = sh->xform[i]; 
    };

    return 0;
}

int addCollConvexTransformShape(
        void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKConvexTransformShapeBuf* buf = static_cast<BHKConvexTransformShapeBuf*>(buffer);

    auto sh = std::make_unique<bhkConvexTransformShape>();
    //sh->SetMaterial(buf->material);
    sh->material = buf->material;
    sh->radius = buf->radius;
    for (int i = 0; i < 16; i++) {
        sh->xform[i] = buf->xform[i];
    };

    int newid = nif->GetHeader().AddBlock(std::move(sh));
    addCollisionChild(nif, parent, newid);

    return newid;
};

NIFLY_API void setCollConvexTransformShapeChild(
        void* nifref, const uint32_t id, uint32_t child_id) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    bhkConvexTransformShape* cts = hdr.GetBlock<bhkConvexTransformShape>(id);

    cts->shapeRef.index = child_id; 
};

int getCollCapsuleShapeProps(void* nifref, uint32_t nodeIndex, void* buffer)
/*
    Return the collision shape details. 
    Return value = 0 if the node is a known collision shape, <>0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKCapsuleShapeBuf* buf = static_cast<BHKCapsuleShapeBuf*>(buffer);
    bhkCapsuleShape* sh = hdr->GetBlock<bhkCapsuleShape>(nodeIndex);

    CheckID(sh);
    CheckBuf(buf, BUFFER_TYPES::bhkCapsuleShapeBufType, BHKCapsuleShapeBuf);

    buf->material = sh->GetMaterial();
    buf->radius = sh->radius;
    buf->radius1 = sh->radius1;
    buf->radius2 = sh->radius2;
    for (int i = 0; i < 3; i++) buf->point1[i] = sh->point1[i];
    for (int i = 0; i < 3; i++) buf->point2[i] = sh->point2[i];

    return 0;
}

int getCollSphereShapeProps(void* nifref, uint32_t nodeIndex, void* buffer)
/*
    Return the collision shape details. 
    Return value = 0 if the node is a known collision shape, <>0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    bhkSphereShapeBuf* buf = static_cast<bhkSphereShapeBuf*>(buffer);
    bhkSphereShape* sh = hdr->GetBlock<bhkSphereShape>(nodeIndex);

    CheckID(sh);
    CheckBuf(buf, BUFFER_TYPES::bhkSphereShapeBufType, bhkSphereShapeBuf);

    buf->material = sh->GetMaterial();
    buf->radius = sh->radius;

    return 0;
}

int addCollCapsuleShape(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    BHKCapsuleShapeBuf* buf = static_cast<BHKCapsuleShapeBuf*>(buffer);

    auto sh = std::make_unique<bhkCapsuleShape>();
    sh->SetMaterial(buf->material);
    sh->radius = buf->radius;
    sh->radius1 = buf->radius1;
    sh->radius2 = buf->radius2;
    for (int i = 0; i < 3; i++) sh->point1[i] = buf->point1[i];
    for (int i = 0; i < 3; i++) sh->point2[i] = buf->point2[i];
    
    int newid = nif->GetHeader().AddBlock(std::move(sh));

    addCollisionChild(nif, parent, newid);

    return newid;
};

/* ***************************** TRANSFORM OBJECTS ***************************** */

int getControllerManager(void* nifref, uint32_t id, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerManager* ncm = hdr->GetBlock<NiControllerManager>(id);
    NiControllerManagerBuf* buf = static_cast<NiControllerManagerBuf*>(inbuf);

    CheckID(ncm);

    CheckBuf(buf, BUFFER_TYPES::NiControllerManagerBufType, NiControllerManagerBuf);

    if (!ncm->nextControllerRef.IsEmpty())
        buf->nextControllerID = ncm->nextControllerRef.index;
    else
        buf->nextControllerID = NIF_NPOS;
    buf->flags = ncm->flags;
    buf->frequency = ncm->frequency;
    buf->phase = ncm->phase;
    buf->startTime = ncm->startTime;
    buf->stopTime = ncm->stopTime;
    buf->targetID = ncm->targetRef.index;
    buf->cumulative = ncm->cumulative;
    buf->controllerSequenceCount = ncm->controllerSequenceRefs.GetSize();
    buf->objectPaletteID = ncm->objectPaletteRef.index;

    return 0;
};

int addControllerManager(void* f, const char* name, void* inbuf, uint32_t parent) {
    /* Create a NiController Manager node. */
    NifFile* nif = static_cast<NifFile*>(f);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerManagerBuf* buf = static_cast<NiControllerManagerBuf*>(inbuf);

    //NiObjectNET* target = nullptr;
    //if (buf->targetID != NIF_NPOS) 
    //    target = hdr.GetBlock<NiObjectNET>(buf->targetID);
        
    CheckBuf(buf, BUFFER_TYPES::NiControllerManagerBufType, NiControllerManagerBuf);

    auto cm = std::make_unique<NiControllerManager>();
    cm->nextControllerRef.index = buf->nextControllerID;
    cm->flags = buf->flags;
    cm->frequency = buf->frequency;
    cm->phase = buf->phase;
    cm->startTime = buf->startTime;
    cm->stopTime = buf->stopTime;
    cm->cumulative = buf->cumulative;
    cm->objectPaletteRef.index = buf->objectPaletteID;
    cm->targetRef.index = buf->targetID;
    
    uint32_t newid = hdr->AddBlock(std::move(cm));

    if (buf->targetID != NIF_NPOS) {
        NiNode* target = hdr->GetBlock<NiNode>(buf->targetID);
        target->controllerRef.index = newid;
        //target->childRefs.AddBlockRef(newid);
    }

    return newid;
};

NIFLY_API int getControllerManagerSeq(
    void* nifref,  int cmID, int buflen, uint32_t* seqptrs) 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiControllerManager* ncm = hdr.GetBlock<NiControllerManager>(cmID);
    int i = 0;
    for (auto& cs : ncm->controllerSequenceRefs) {
        if (i >= buflen) break;
        seqptrs[i++] = cs.index;
    }
    return ncm->controllerSequenceRefs.GetSize();
}

NIFLY_API int getControllerManagerSequences(
    void* nifref,  void* ncmref, int buflen, uint32_t* seqptrs) 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiControllerManager* ncm = static_cast<NiControllerManager*>(ncmref);
    int i = 0;
    for (auto& cs : ncm->controllerSequenceRefs) {
        if (i >= buflen) break;
        seqptrs[i++] = cs.index;
    }
    return ncm->controllerSequenceRefs.GetSize();
}

int getControllerSequence(void* nifref, uint32_t csID, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiControllerSequence* cs = hdr.GetBlock< NiControllerSequence>(csID);
    NiControllerSequenceBuf* buf = static_cast<NiControllerSequenceBuf*>(inbuf);

    CheckID(cs);

    CheckBuf(buf, BUFFER_TYPES::NiControllerSequenceBufType, NiControllerSequenceBuf);

    buf->nameID = cs->name.GetIndex();
    buf->arrayGrowBy = cs->arrayGrowBy;
    buf->controlledBlocksCount = cs->controlledBlocks.size();
    buf->weight = cs->weight;
    buf->textKeyID = cs->textKeyRef.IsEmpty() ? NIF_NPOS : cs->textKeyRef.index;
    buf->cycleType = cs->cycleType;
    buf->frequency = cs->frequency;
    buf->startTime = cs->startTime;
    buf->stopTime = cs->stopTime;
    buf->managerID = cs->managerRef.index;
    buf->accumRootNameID = cs->accumRootName.GetIndex();
    buf->animNotesID = cs->animNotesRef.IsEmpty() ? NIF_NPOS : cs->animNotesRef.index;
    buf->animNotesCount = cs->animNotesRefs.GetSize();

    return 0;
}

int addControllerSequence(void* nifref, const char* name, void* inbuf, uint32_t parentID) 
/* Add a ControllerSequence block */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerSequenceBuf* buf = static_cast<NiControllerSequenceBuf*>(inbuf);

    auto cs = std::make_unique<NiControllerSequence>();
    uint32_t newid = hdr->AddBlock(std::move(cs));
    NiControllerSequence* csblock = hdr->GetBlock<NiControllerSequence>(newid);
    csblock->name.get() = name;
    if (assignControllerSequence(nifref, newid, buf)) return NIF_NPOS;

    uint32_t p = buf->managerID;
    if (parentID != NIF_NPOS) p = parentID;

    if (p != NIF_NPOS) {
        NiControllerManager* mgr = hdr->GetBlock<NiControllerManager>(p);
        mgr->controllerSequenceRefs.AddBlockRef(newid);
    }

    return newid;
}

int getControlledBlocks(void* nifref, uint32_t csID, void* buf) {
/* Return the "ControllerLink blocks, children of NiControllerSequence blocks. 
    blocks = Pointer to an ARRAY of ControllerLinkBuf blocks. Caller must allocate as many as there 
    are blocks.
    bufSize of first block must be set to the TOTAL length of the block array.
*/
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerSequence* cs = hdr->GetBlock<NiControllerSequence>(csID);
    ControllerLinkBuf* blocks = static_cast<ControllerLinkBuf*>(buf);

    CheckID(cs);

    if (blocks[0].bufSize < sizeof(ControllerLinkBuf) * cs->controlledBlocks.size()) {
        niflydll::LogWrite("ERROR: ControllerLinkBuf buffer wrong size.");
        return 2;
    }

    int i = 0;
    for (auto& cl : cs->controlledBlocks) {
        ControllerLinkBuf* b = &blocks[i];
        b->interpolatorID = cl.interpolatorRef.index;
        b->controllerID = cl.controllerRef.index;
        b->priority = cl.priority;
        b->nodeName = cl.nodeName.GetIndex();
        b->propType = cl.propType.GetIndex();
        b->ctrlType = cl.ctrlType.GetIndex();
        b->ctrlID = cl.ctrlID.GetIndex();
        b->interpID = cl.interpID.GetIndex();
        i++;
    }

    return 0;
}

//NIFLY_API void addControlledBlock(void* nifref, uint32_t csID, const char* name, ControllerLinkBuf* b) {
int addControlledBlock(void* nifref, const char* name, void* buffer, uint32_t parent) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    ControllerLinkBuf* b = static_cast<ControllerLinkBuf*>(buffer);
    NiControllerSequence* cs = hdr->GetBlock<NiControllerSequence>(parent);

    ControllerLink cl;
    cl.interpolatorRef.index = b->interpolatorID;
    cl.controllerRef.index = b->controllerID;
    cl.priority = b->priority;
    cl.nodeName.SetIndex(b->nodeName);
    cl.nodeName.get() = hdr->GetStringById(b->nodeName);
    cl.propType.SetIndex(b->propType);
    cl.propType.get() = hdr->GetStringById(b->propType);
    cl.ctrlType.SetIndex(b->ctrlType);
    cl.ctrlType.get() = hdr->GetStringById(b->ctrlType);
    cl.ctrlID.SetIndex(b->ctrlID);
    cl.ctrlID.get() = hdr->GetStringById(b->ctrlID);
    cl.interpID.SetIndex(b->interpID);
    cl.interpID.get() = hdr->GetStringById(b->interpID);

    cs->controlledBlocks.push_back(cl);

    NiMultiTargetTransformController* mttc
        = hdr->GetBlock<NiMultiTargetTransformController>(b->controllerID);
    if (mttc) {
        int targID = findBlockByName(nifref, cl.nodeName.get().c_str());
        mttc->targetRefs.AddBlockRef(targID);
    }

    return cs->controlledBlocks.size();
}

int getTransformInterpolator(void* nifref, uint32_t tiID, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformInterpolator* ti = hdr->GetBlock<NiTransformInterpolator>(tiID);
    NiTransformInterpolatorBuf* buf = static_cast<NiTransformInterpolatorBuf*>(inbuf);

    CheckID(ti);

    CheckBuf(buf, BUFFER_TYPES::NiTransformInterpolatorBufType, NiTransformInterpolatorBuf);

    for (int i=0; i < 3; i++) buf->translation[i] = ti->translation[i];
    buf->rotation[0] = ti->rotation.w;
    buf->rotation[1] = ti->rotation.x;
    buf->rotation[2] = ti->rotation.y;
    buf->rotation[3] = ti->rotation.z;
    buf->scale = ti->scale;
    buf->dataID = ti->dataRef.index;

    return 0;
}

int addTransformInterpolator(void* nifref, const char* name, void* inbuf, uint32_t parentID) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformInterpolatorBuf* buf = static_cast<NiTransformInterpolatorBuf*>(inbuf);

    CheckBuf(buf, BUFFER_TYPES::NiTransformInterpolatorBufType, NiTransformInterpolatorBuf);

    auto ti = std::make_unique<NiTransformInterpolator>();

    for (int i=0; i < 3; i++) ti->translation[i] = buf->translation[i];
    ti->rotation.w = buf->rotation[0];
    ti->rotation.x = buf->rotation[1];
    ti->rotation.y = buf->rotation[2];
    ti->rotation.z = buf->rotation[3];
    ti->scale = buf->scale;
    ti->dataRef.index = buf->dataID;

    return hdr->AddBlock(std::move(ti));
}

int getMultiTargetTransformController(void* nifref, uint32_t mttcID, void* inbuf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiMultiTargetTransformControllerBuf* buf = static_cast<NiMultiTargetTransformControllerBuf*>(inbuf);
    NiMultiTargetTransformController* mttc 
        = hdr.GetBlock<NiMultiTargetTransformController>(uint32_t(mttcID));

    CheckID(mttc);

    CheckBuf(buf, BUFFER_TYPES::NiMultiTargetTransformControllerBufType, NiMultiTargetTransformControllerBuf);

    buf->nextControllerID = mttc->nextControllerRef.index;
    buf->flags = mttc->flags;
    buf->frequency = mttc->frequency;
    buf->phase = mttc->phase;
    buf->startTime = mttc->startTime;
    buf->stopTime = mttc->stopTime;
    buf->targetID = mttc->targetRef.index;
    buf->targetCount = mttc->targetRefs.GetSize();

    return 0;
}

int addMultiTargetTransformController(void* nifref, const char* name, void* inbuf, uint32_t parentID) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiMultiTargetTransformControllerBuf* buf = static_cast<NiMultiTargetTransformControllerBuf*>(inbuf);

    CheckBuf(buf, BUFFER_TYPES::NiMultiTargetTransformControllerBufType, NiMultiTargetTransformControllerBuf);

    auto mttc = std::make_unique<NiMultiTargetTransformController>();
    mttc->nextControllerRef.index = buf->nextControllerID;
    mttc->flags = buf->flags;
    mttc->frequency = buf->frequency;
    mttc->phase = buf->phase;
    mttc->startTime = buf->startTime;
    mttc->stopTime = buf->stopTime;
    mttc->targetRef.index = buf->targetID;

    return hdr->AddBlock(std::move(mttc));
}

int getTransformController(void* nifref, uint32_t nodeIndex, void* inbuf)
/*
    Return a Transform Controller block.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformControllerBuf* buf = static_cast<NiTransformControllerBuf*>(inbuf);
    NiTransformController* sh = hdr->GetBlock<NiTransformController>(nodeIndex);

    CheckID(sh);

    CheckBuf(buf, BUFFER_TYPES::NiTransformControllerBufType, NiTransformControllerBuf);

    buf->flags = sh->flags;
    buf->frequency = sh->frequency;
    buf->phase = sh->phase;
    buf->startTime = sh->startTime;
    buf->stopTime = sh->stopTime;
    buf->targetIndex = sh->targetRef.index;
    buf->interpolatorIndex = sh->interpolatorRef.index;
    buf->nextControllerIndex = sh->nextControllerRef.index;
    return 0;
};

int addTransformController(void* nifref, const char* name, void* b, uint32_t parent)
/* Create a Transform Controller block. */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformControllerBuf* buf = static_cast<NiTransformControllerBuf*>(b);

    CheckBuf(buf, BUFFER_TYPES::NiTransformControllerBufType, NiTransformControllerBuf);
    auto sh = std::make_unique<NiTransformController>();
    sh->flags = buf->flags;
    sh->frequency = buf->frequency;
    sh->phase = buf->phase;
    sh->startTime = buf->startTime;
    sh->stopTime = buf->stopTime;
    sh->targetRef.index = buf->targetIndex;
    sh->interpolatorRef.index = buf->interpolatorIndex;
    sh->nextControllerRef.index = buf->nextControllerIndex;
    int newid = hdr->AddBlock(std::move(sh));

    if (parent != NIF_NPOS) {
        NiNode* p = hdr->GetBlock<NiNode>(parent);
        p->controllerRef.index = newid;
    }
    return newid;
};

int getTransformData(void* nifref, uint32_t nodeIndex, void* inbuf)
/*
    Return a Transform Data block.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiTransformData* sh = hdr->GetBlock<NiTransformData>(nodeIndex);
    NiTransformDataBuf* buf = static_cast<NiTransformDataBuf*>(inbuf);

    CheckID(sh);

    CheckBuf(buf, BUFFER_TYPES::NiTransformDataBufType, NiTransformDataBuf);

    buf->rotationType = sh->rotationType;
    buf->quaternionKeyCount = uint32_t(sh->quaternionKeys.size());
    buf->xRotations.interpolation = sh->xRotations.GetInterpolationType();
    buf->xRotations.numKeys = sh->xRotations.GetNumKeys();
    buf->yRotations.interpolation = sh->yRotations.GetInterpolationType();
    buf->yRotations.numKeys = sh->yRotations.GetNumKeys();
    buf->zRotations.interpolation = sh->zRotations.GetInterpolationType();
    buf->zRotations.numKeys = sh->zRotations.GetNumKeys();
    buf->translations.interpolation = sh->translations.GetInterpolationType();
    buf->translations.numKeys = sh->translations.GetNumKeys();
    buf->scales.interpolation = sh->scales.GetInterpolationType();
    buf->scales.numKeys = sh->scales.GetNumKeys();

    return 0;
};

int addTransformData(void* nifref, const char* name, void* b, uint32_t parent)
/*
    Add a Transform Data block. If supplied, parent is the NiTransformInterpolator that 
    uses this data.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformDataBuf* buf = static_cast<NiTransformDataBuf*>(b);
    
    CheckBuf(buf, BUFFER_TYPES::NiTransformDataBufType, NiTransformDataBuf);

    auto sh = std::make_unique<NiTransformData>();

    sh->rotationType = NiKeyType(buf->rotationType);
    sh->xRotations.SetInterpolationType(NiKeyType(buf->xRotations.interpolation));
    sh->yRotations.SetInterpolationType(NiKeyType(buf->yRotations.interpolation));
    sh->zRotations.SetInterpolationType(NiKeyType(buf->zRotations.interpolation));
    sh->translations.SetInterpolationType(NiKeyType(buf->translations.interpolation));
    sh->scales.SetInterpolationType(NiKeyType(buf->scales.interpolation));

    int td = hdr->AddBlock(std::move(sh));
    if (parent != NIF_NPOS) {
        NiTransformInterpolator* ti = hdr->GetBlock<NiTransformInterpolator>(parent);
        ti->dataRef.index = td;
    }

    return td;
};

void readKey(NiAnimKeyQuadXYZBuf& kb, NiAnimationKey<float> k) {
    kb.time = k.time;
    kb.value = k.value;
    kb.forward = k.forward;
    kb.backward = k.backward;
}

void setKey(NiAnimationKey<float>& k, NiAnimKeyQuadXYZBuf& kb) {
    k.time = kb.time;
    k.value = kb.value;
    k.forward = kb.forward;
    k.backward = kb.backward;
}

NIFLY_API void getAnimKeyQuadXYZ(void* nifref, int tdID, char dimension, int frame, NiAnimKeyQuadXYZBuf *buf)
/* Get the animation key for frame 'frame', for the dimension given. */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiTransformData* td = hdr.GetBlock<NiTransformData>(tdID);

    if (dimension == 'X') readKey(*buf, td->xRotations.GetKey(frame));
    else if (dimension == 'Y') readKey(*buf, td->yRotations.GetKey(frame));
    else if (dimension == 'Z') readKey(*buf, td->zRotations.GetKey(frame));
    else if (dimension == 'S') readKey(*buf, td->scales.GetKey(frame));
}

NIFLY_API void addAnimKeyQuadXYZ(void* nifref, int tdID, char dimension, NiAnimKeyQuadXYZBuf *buf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiTransformData* td = hdr->GetBlock<NiTransformData>(tdID);

    NiAnimationKey<float> k;
    setKey(k, *buf);
    if (dimension == 'X') td->xRotations.AddKey(k);
    else if (dimension == 'Y') td->yRotations.AddKey(k);
    else if (dimension == 'Z') td->zRotations.AddKey(k);
    else if (dimension == 'S') td->scales.AddKey(k);
}

NIFLY_API void getAnimKeyLinearXYZ(void* nifref, int tdID, char dimension, int frame, NiAnimKeyLinearXYZBuf *buf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiTransformData* td = hdr.GetBlock<NiTransformData>(tdID);

    NiAnimationKey<float> k;
    if (dimension == 'X') k = td->xRotations.GetKey(frame);
    if (dimension == 'Y') k = td->yRotations.GetKey(frame);
    if (dimension == 'Z') k = td->zRotations.GetKey(frame);

    buf->time = k.time; 
    buf->value = k.value;
}

NIFLY_API void getAnimKeyLinearQuat(void* nifref, int tdID, int frame, NiAnimKeyLinearQuatBuf* buf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiTransformData* td = hdr->GetBlock<NiTransformData>(tdID);

    NiAnimationKey<Quaternion> k = td->quaternionKeys[frame];

    buf->time = k.time;
    buf->value[0] = k.value.w;
    buf->value[1] = k.value.x;
    buf->value[2] = k.value.y;
    buf->value[3] = k.value.z;
}

NIFLY_API void addAnimKeyLinearQuat(void* nifref, int tdID, NiAnimKeyLinearQuatBuf* buf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiTransformData* td = hdr->GetBlock<NiTransformData>(tdID);

    NiAnimationKey<Quaternion> k;

    k.time = buf->time;
    k.value.w = buf->value[0];
    k.value.x = buf->value[1];
    k.value.y = buf->value[2];
    k.value.z = buf->value[3];

    td->quaternionKeys.push_back(k);
}

NIFLY_API void getAnimKeyLinearTrans(void* nifref, int tdID, int frame, NiAnimKeyLinearTransBuf *buf)
/* Return the linear animation key at frame "frame". */ {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiTransformData* td = hdr.GetBlock<NiTransformData>(tdID);
    
    auto k = td->translations.GetKey(frame);
    buf->time = k.time;
    buf->value[0] = k.value[0];
    buf->value[1] = k.value[1];
    buf->value[2] = k.value[2];
}

NIFLY_API void addAnimKeyLinearTrans(void* nifref, int tdID, NiAnimKeyLinearTransBuf *buf)
/* Add a linear animation key. Key frames must be added in order. 
    tdID = ID of parent NiTransformationData node. 
    */ 
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiTransformData* td = hdr->GetBlock<NiTransformData>(tdID);
    
    nifly::NiAnimationKey<Vector3> k;
    k.time = buf->time;
    k.value[0] = buf->value[0];
    k.value[1] = buf->value[1];
    k.value[2] = buf->value[2];
    td->translations.AddKey(k);
}


NIFLY_API void getAnimKeyQuadTrans(void* nifref, int tdID, int frame, NiAnimKeyQuadTransBuf *buf)
/* Return the quad animation key at frame "frame". */ {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiTransformData* td = hdr.GetBlock<NiTransformData>(tdID);
    
    auto k = td->translations.GetKey(frame);
    buf->time = k.time;
    for (int i=0; i < 3; i++) buf->value[i] = k.value[i];
    for (int i=0; i < 3; i++) buf->forward[i] = k.forward[i];
    for (int i=0; i < 3; i++) buf->backward[i] = k.backward[i];
}


NIFLY_API int getTransformDataValues(void* nifref, int nodeIndex, 
    NiAnimationKeyQuatBuf* qBuf, 
    NiAnimationKeyFloatBuf* xRotBuf, 
    NiAnimationKeyFloatBuf* yRotBuf, 
    NiAnimationKeyFloatBuf* zRotBuf,
    NiAnimationKeyVec3Buf* transBuf,
    NiAnimationKeyFloatBuf* scaleBuf
    )
/*
    Return the arrays of values associated with a Transform Data block. Buffer sizes must have been 
    allocated correctly by the caller according to values returned by getTransformData.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiTransformData* sh = hdr.GetBlock<NiTransformData>(nodeIndex);

    if (sh) {
        for (auto& q : sh->quaternionKeys) {
            assignQ(qBuf->backward, q.backward);
            assignQ(qBuf->forward, q.forward);
            qBuf->tbcBias = q.tbc.bias;
            qBuf->tbcContinuity = q.tbc.continuity;
            qBuf->tbcTension = q.tbc.tension;
            qBuf->time = q.time;
            qBuf->type = q.type;
            assignQ(qBuf->value, q.value);
            qBuf++;
        };

        for (uint32_t i = 0; i < sh->xRotations.GetNumKeys(); i++) {
            NiAnimationKey<float> k = sh->xRotations.GetKey(i);
            xRotBuf->backward = k.backward;
            xRotBuf->forward = k.forward;
            xRotBuf->tbcBias = k.tbc.bias;
            xRotBuf->tbcContinuity = k.tbc.continuity;
            xRotBuf->tbcTension = k.tbc.tension;
            xRotBuf->time = k.time;
            xRotBuf->type = k.type;
            xRotBuf->value = k.value;
            xRotBuf++;
        };

        for (uint32_t i = 0; i < sh->yRotations.GetNumKeys(); i++) {
            NiAnimationKey<float> k = sh->yRotations.GetKey(i);
            yRotBuf->backward = k.backward;
            yRotBuf->forward = k.forward;
            yRotBuf->tbcBias = k.tbc.bias;
            yRotBuf->tbcContinuity = k.tbc.continuity;
            yRotBuf->tbcTension = k.tbc.tension;
            yRotBuf->time = k.time;
            yRotBuf->type = k.type;
            yRotBuf->value = k.value;
            yRotBuf++;
        };

        for (uint32_t i = 0; i < sh->zRotations.GetNumKeys(); i++) {
            NiAnimationKey<float> k = sh->zRotations.GetKey(i);
            zRotBuf->backward = k.backward;
            zRotBuf->forward = k.forward;
            zRotBuf->tbcBias = k.tbc.bias;
            zRotBuf->tbcContinuity = k.tbc.continuity;
            zRotBuf->tbcTension = k.tbc.tension;
            zRotBuf->time = k.time;
            zRotBuf->type = k.type;
            zRotBuf->value = k.value;
            zRotBuf++;
        };

        for (uint32_t i = 0; i < sh->translations.GetNumKeys(); i++) {
            NiAnimationKey<Vector3> k = sh->translations.GetKey(i);
            assignVec3(transBuf->backward, k.backward);
            assignVec3(transBuf->forward, k.forward);
            transBuf->tbcBias = k.tbc.bias;
            transBuf->tbcContinuity = k.tbc.continuity;
            transBuf->tbcTension = k.tbc.tension;
            transBuf->time = k.time;
            transBuf->type = k.type;
            assignVec3(transBuf->value, k.value);
            transBuf++;
        };

        for (uint32_t i = 0; i < sh->scales.GetNumKeys(); i++) {
            NiAnimationKey<float> k = sh->scales.GetKey(i);
            scaleBuf->backward = k.backward;
            scaleBuf->forward = k.forward;
            scaleBuf->tbcBias = k.tbc.bias;
            scaleBuf->tbcContinuity = k.tbc.continuity;
            scaleBuf->tbcTension = k.tbc.tension;
            scaleBuf->time = k.time;
            scaleBuf->type = k.type;
            scaleBuf->value = k.value;
            scaleBuf++;
        };

        return 1;
    }
    else
        return 0;
};

NIFLY_API int getExtraData(void* nifref, uint32_t id, const char* extraDataBlockType) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiObjectNET* node = hdr->GetBlock<NiObjectNET>(id);

    if (!node) {
        niflydll::LogWrite("Node ID does not exist");
        return NIF_NPOS;
    }
    for (auto& ed : node->extraDataRefs) {
        NiExtraData* edBlock = hdr->GetBlock<NiExtraData>(ed.index);
        if (edBlock && (strcmp(edBlock->GetBlockName(), extraDataBlockType) == 0))
            return ed.index;
    }

    niflydll::LogWrite("Extra block type " + std::string(extraDataBlockType) 
        + " not associated with node " + std::to_string(id));
    return NIF_NPOS;
}

// Getter functions match 1:1 with BUFFER_TYPES
typedef int (*BlockGetterFunction)(void* nifref, uint32_t blockID, void* buf);
BlockGetterFunction getterFunctions[] = {
    getNodeProperties,
    getNiShape,
    getCollisionObject,
    getCollisionObject,
    getCollisionObject,
    getCollisionObject,
    getRigidBodyProps,
    getRigidBodyProps,
    getCollBoxShapeProps,
    getControllerManager,
    getControllerSequence,
    getTransformInterpolator,
    getTransformData,
    getControlledBlocks, // NiControllerLinkBufType
    getInvMarker, // BSInvMarkerBufType
    getBSXFlags,
    getMultiTargetTransformController,
    getTransformController,
    getCollisionObject, // bhkCollisionObjectBufType
    getCollCapsuleShapeProps, //bhkCapsuleShapeBufType,
    getCollConvexTransformShapeProps, //bhkConvexTransformShapeBufType,
    getCollConvexVertsShapeProps, //bhkConvexVerticesShapeBufType,
    getCollListShapeProps, //bhkListShapeBufTYpe
    getBlendCollisionObject, //bhkBlendCollisionObjectBufType
    getRagdollConstraint, //bhkRagdollConstraintBufType
    getSimpleShapePhantom, //bhkSimpleShapePhantomBufType
    getCollSphereShapeProps, //bhkSphereShapeBufType
    getBSMeshLODTriShape,
    getNiShader, //NiShaderBufType
    getNiAlphaProperty, //NiAlphaPropertyBuf
    getNiShape, //BSDynamicTriShapeBufType,
    getNiShape, //BSTriShapeBufType,
    getNiShape, //BSSubIndexTriShape
    getNiShader, //BSEffectShaderPropertyBufType
    getNiShape, //NiTriStripsBufType
    nullptr //END
};

NIFLY_API int getBlock(void* nifref, uint32_t blockID, void* buf)
/* Read block properties for any type of block. buf must be the appropriate type of buffer
    for the block type.

    Returns: 0 if block found and read; non-zero if not.
    */
{
    BlockBuf* theBuf = static_cast<BlockBuf*>(buf);
    if (!getterFunctions[theBuf->bufType]) return NIF_NPOS;
    return getterFunctions[theBuf->bufType](nifref, blockID, buf);
};


// Setter functions match 1:1 with BUFFER_TYPES
typedef int (*BlockSetterFunction)(void* nifref, uint32_t blockID, void* buf);
BlockSetterFunction setterFunctions[] = {
    setNodeByID,
    nullptr, // NiShape
    setCollision, //NiCollisionObjectBufType,
    setCollision, //bhkNiCollisionObjectBufType,
    setCollision, //bhkPCollisionObjectBufType,
    setCollision, //bhkSPCollisionObjectBufType,
    setRigidBody, //bhkRigidBodyBufType,
    setRigidBody, //bhkRigidBodyTBufType,
    nullptr, //bhkBoxShapeBufType,
    nullptr, //NiControllerManagerBufType,
    assignControllerSequence, //NiControllerSequenceBufType,
    nullptr, //NiTransformInterpolatorBufType,
    nullptr, //NiTransformDataBufType,
    nullptr, //NiControllerLinkBufType,
    nullptr, //BSInvMarkerBufType,
    nullptr, //BSXFlagsBufType,
    nullptr, //NiMultiTargetTransformControllerBufType,
    nullptr, //NiTransformControllerBufType
    setCollision, // bhkCollisionObjectBufType
    nullptr, //bhkCapsuleShapeBufType,
    nullptr, //bhkConvexTransformShapeBufType,
    nullptr, //bhkConvexVerticesShapeBufType,
    nullptr, //bhkListShapeBufTYpe
    nullptr, //bhkBlendCollisionObjectBufType
    nullptr, //bhkRagdollConstraintBufType
    nullptr, //bhkSimpleShapePhantomBufType
    nullptr, //bhkSphereShapeBufType
    nullptr, //BSMeshLODTriShapeBufType
    nullptr, //NiShaderBufType
    nullptr, //NiAlphaPropertyBufType
    nullptr, //BSDynamicTriShapeBufType,
    nullptr, //BSTriShapeBufType,
    nullptr, //BSSubIndexTriShape
    nullptr, //NiTriStripsBufType
    nullptr //END
};

NIFLY_API int setBlock(void* f, int id, void* buf)
/* Set the properties of block with id "id".
    Caller must ensure the buf is the correct type for the node.
    Returns 0 for success, non-zero for errors.
*/
{
    BlockBuf* theBuf = static_cast<BlockBuf*>(buf);
    if (!setterFunctions[theBuf->bufType]) return -1;
    return setterFunctions[theBuf->bufType](f, id, buf);
}

// Creator functions match 1:1 with BUFFER_TYPES
typedef int (*BlockCreatorFunction)(void* nifref, const char* name, void* buf, uint32_t parent);
BlockCreatorFunction creatorFunctions[] = {
    createNode,
    nullptr, // NiShape
    addCollision, //NiCollisionObjectBufType,
    addCollision, //bhkNiCollisionObjectBufType,
    addCollision, //bhkPCollisionObjectBufType,
    addCollision, //bhkSPCollisionObjectBufType,
    addRigidBody, //bhkRigidBodyBufType,
    addRigidBody, //bhkRigidBodyTBufType,
    addCollBoxShape, //bhkBoxShapeBufType,
    addControllerManager, //NiControllerManagerBufType,
    addControllerSequence, //NiControllerSequenceBufType,
    addTransformInterpolator, //NiTransformInterpolatorBufType,
    addTransformData, //NiTransformDataBufType,
    addControlledBlock, //NiControllerLinkBufType,
    setInvMarker, //BSInvMarkerBufType,
    setBSXFlags, //BSXFlagsBufType,
    addMultiTargetTransformController, //NiMultiTargetTransformControllerBufType,
    addTransformController, //NiTransformControllerBufType, 
    addCollision, // bhkCollisionObjectBufType
    addCollCapsuleShape, //bhkCapsuleShapeBufType,
    addCollConvexTransformShape, //bhkConvexTransformShapeBufType,
    addCollConvexVertsShape, //bhkConvexVerticesShapeBufType,
    addCollListShape, //bhkListShapeBufTYpe
    nullptr, //bhkBlendCollisionObjectBufType
    nullptr, //bhkRagdollConstraintBufType
    nullptr, //bhkSimpleShapePhantomBufType
    nullptr, //bhkSphereShapeBufType
    nullptr, // BSMeshLODTriShapeBufType
    setNiShader,  //NiShaderBufType
    setNiAlphaProperty, //NiAlphaPropertyBuf
    nullptr, //BSDynamicTriShapeBufType,
    nullptr, //BSTriShapeBufType,
    nullptr, //BSSubIndexTriShape
    setNiShader, //BSEffectShaderPropertyBufType
    nullptr, //NiTriStripsBufType
    nullptr //end
};

NIFLY_API int addBlock(void* f, const char* name, void* buf, int parent) {
    BlockBuf* theBuf = static_cast<BlockBuf*>(buf);
    if (!creatorFunctions[theBuf->bufType]) return NIF_NPOS;
    return creatorFunctions[theBuf->bufType](f, name, buf, parent);
}

