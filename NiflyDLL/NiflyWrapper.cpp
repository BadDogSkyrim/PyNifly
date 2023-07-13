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

const int NiflyDDLVersion[3] = { 10, 3, 0 };
 
using namespace nifly;

/* ************************** UTILITY ************************** */

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

NIFLY_API void* createNif(const char* targetGameName, const char* rootType, const char* rootName) {
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

NIFLY_API int getBlock(void* nifref, uint32_t blockID, const char* blocktype, void* buf) 
/* Read block properties for any type of block. buf must be the appropriate type of buffer 
    for the block type.

    Returns: True if block found and read; false if not.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    if (strcmp(blocktype, "NiNode") == 0) {
        nifly::NiNode* node = hdr->GetBlock<NiNode>(blockID);
        getNode(node, static_cast<NiNodeBuf*>(buf));
    }
    if (strcmp(blocktype, "BSFadeNode") == 0) {
        nifly::BSFadeNode* node = hdr->GetBlock<BSFadeNode>(blockID);
        getNode(node, static_cast<NiNodeBuf*>(buf));
    }
    else if (strcmp(blocktype, "NiControllerManager") == 0) {
        nifly::NiControllerManager* node = hdr->GetBlock<NiControllerManager>(blockID);
        getControllerManager(node, static_cast<NiControllerManagerBuf*>(buf));
    }
    else if (strcmp(blocktype, "NiTransformController") == 0) {
        getTransformController(nifref, blockID, static_cast<NiTransformControllerBuf*>(buf));
    }
    else if (strcmp(blocktype, "NiMultiTargetTransformController") == 0) {
        getMultiTargetTransformController(nifref, blockID, static_cast<NiMultiTargetTransformControllerBuf*>(buf));
    }
    else if (strcmp(blocktype, "NiControllerSequence") == 0) {
        getControllerSequence(nifref, blockID, static_cast<NiControllerSequenceBuf*>(buf));
    }
    else if (strcmp(blocktype, "NiTransformInterpolator") == 0) {
        getTransformInterpolator(nifref, blockID, static_cast<NiTransformInterpolatorBuf*>(buf));
    }
    else if (strcmp(blocktype, "NiTransformData") == 0) {
        getTransformData(nifref, blockID, static_cast<NiTransformDataBuf*>(buf));
    }
    else
        return 0;
    return 1;
};

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

NIFLY_API void* getNodeController(void* nifref, void* node, NiControllerManagerBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiNode* theNode = static_cast<nifly::NiNode*>(node);
    if (!theNode) return nullptr;

    if (theNode->controllerRef.IsEmpty()) return nullptr;

    auto ctrlr = hdr.GetBlock<NiControllerManager>(theNode->controllerRef.index);
    if (ctrlr) getControllerManager(ctrlr, buf);

    return ctrlr;
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

NIFLY_API int addBlock(void* f, const char* name, const char* type, void* buf, int parent) {
    NifFile* nif = static_cast<NifFile*>(f);
    NiHeader* hdr = &nif->GetHeader();

    if (strcmp(type, "NiNode") == 0) {
        NiNodeBuf* nodeBuf = static_cast<NiNodeBuf*>(buf);
        NiNode* parNode = nullptr;
        if (parent != NIF_NPOS) parNode = hdr->GetBlock<NiNode>(parent);
        NiNode* theNode = static_cast<NiNode*>(addNode(f, name, &nodeBuf->translation[0], parNode));
        return hdr->GetBlockID(theNode);
    }
    if (strcmp(type, "NiControllerManager") == 0) {
        NiControllerManagerBuf* cmBuf = static_cast<NiControllerManagerBuf*>(buf);
        return addControllerManager(f, name, cmBuf, nullptr);
    }
    if (strcmp(type, "NiControllerSequence") == 0) {
        NiControllerSequenceBuf* csBuf = static_cast<NiControllerSequenceBuf*>(buf);
        return addControllerSequence(f, name, csBuf);
    }
    if (strcmp(type, "NiMultiTargetTransformController") == 0) {
        return addMultiTargetTransformController(f, static_cast<NiMultiTargetTransformControllerBuf*>(buf));
    }
    if (strcmp(type, "NiTransformInterpolator") == 0) {
        return addTransformInterpolator(f, static_cast<NiTransformInterpolatorBuf*>(buf));
    }
    if (strcmp(type, "NiTransformData") == 0) {
        return addTransformData(f, static_cast<NiTransformDataBuf*>(buf), parent);
    }
    if (strcmp(type, "NiTransformController") == 0) {
        return addTransformController(f, static_cast<NiTransformControllerBuf*>(buf), parent);
    }
    else {
        return NIF_NPOS;
    }
}

void assignControllerSequence(NiHeader* hdr, NiControllerSequence* cs, NiControllerSequenceBuf* buf) {
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
}

NIFLY_API void setBlock(void* f, int id, const char* type, void* buf)
/* Set the properties of block with id "id". 
    Caller must ensure the buf is the correct type for the node. 
*/
{
    NifFile* nif = static_cast<NifFile*>(f);
    NiHeader* hdr = &nif->GetHeader();

    if (strcmp(type, "NiNode") == 0) {
        auto block = hdr->GetBlock<NiNode>(id);
        NiNodeBuf* nodeBuf = static_cast<NiNodeBuf*>(buf);
        setNode(block, nodeBuf);
    }
    else if (strcmp(type, "BSFadeNode") == 0) {
        auto block = hdr->GetBlock<BSFadeNode>(id);
        NiNodeBuf* nodeBuf = static_cast<NiNodeBuf*>(buf);
        setNode(block, nodeBuf);
    }
    else if (strcmp(type, "NiControllerSequence") == 0) {
        NiControllerSequence* block = hdr->GetBlock<NiControllerSequence>(id);
        NiControllerSequenceBuf* nodeBuf = static_cast<NiControllerSequenceBuf*>(buf);
        assignControllerSequence(hdr, block, nodeBuf);
    }
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
    const Vector3* verts,
    const Vector2* uv_points,
    const Vector3* norms,
    int vertCount,
    const Triangle* tris, int triCount,
    uint16_t* optionsPtr,
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
    std::vector<Vector3> v;
    std::vector<Triangle> t;
    std::vector<Vector2> uv;
    std::vector<Vector3> n;

    for (int i = 0; i < vertCount; i++) {
        Vector3 thisv = verts[i];
        v.push_back(thisv);

        Vector2 thisuv = uv_points[i];
        uv.push_back(thisuv);

        if (norms) {
            Vector3 thisnorm = norms[i];
            n.push_back(thisnorm);
        };
    }
    for (int i = 0; i < triCount; i++) {
        Triangle thist = tris[i];
        t.push_back(thist);
    }

    uint16_t opt = 0;
    if (optionsPtr) opt = *optionsPtr;
    NiNode* parent = nullptr;
    if (parentRef) parent = static_cast<NiNode*>(parentRef);

    return PyniflyCreateShapeFromData(nif, shapeName, 
            &v, &t, &uv, &n, opt, parent);
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
            //Normalize weights in some kind of finalization step.
            //float sum = vertex.weights[0] + vertex.weights[1] + vertex.weights[2] + vertex.weights[3];
            //for (int j = 0; j < 4; j++) vertex.weights[j] = vertex.weights[j] / sum;
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

NIFLY_API int getShaderName(void* nifref, void* shaperef, char* buf, int buflen) {
/*
    Returns length of name string, -1 if there is no shader
*/
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);

    if (!shader)
        return -1;
    else {
        strncpy_s(buf, buflen, shader->name.get().c_str(), buflen);
        buf[buflen - 1] = '\0';
    };

    return int(shader->name.get().length());
};

NIFLY_API uint32_t getShaderFlags1(void* nifref, void* shaperef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    if (!shader)
        return 0;
    else {
        BSLightingShaderProperty* bssh = dynamic_cast<BSLightingShaderProperty*>(shader);
        if (bssh) return bssh->shaderFlags1;
        BSEffectShaderProperty* bses = dynamic_cast<BSEffectShaderProperty*>(shader);
        if (bses) return bses->shaderFlags1;
        return 0;
    }
}

NIFLY_API uint32_t getShaderFlags2(void* nifref, void* shaperef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    
    if (!shader)
        return 0;
    else {
        BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
        return (bssh ? bssh->shaderFlags2 : 0);
    };
}

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

NIFLY_API const char* getShaderBlockName(void* nifref, void* shaperef) {
    /* Returns name of the shader block property, e.g. "BSLightingShaderProperty"
    * Return value is null if shader is not BSLightingShader or BSEffectShader.
    */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);
    const char* blockName = nullptr;
 
    if (shader) {
        BSLightingShaderProperty* sp = dynamic_cast<BSLightingShaderProperty*>(shader);
        if (sp)
            blockName = sp->BlockName;
        else {
            BSEffectShaderProperty* ep = dynamic_cast<BSEffectShaderProperty*>(shader);
            if (ep)
                blockName = ep->BlockName;
        }
    };
    
    return blockName;
};

NIFLY_API uint32_t getShaderType(void* nifref, void* shaperef) {
/*
    Return value: 0 = no shader or not a LSLightingShader; anything else is the shader type
*/
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);

    if (!shader)
        return 0;
    else
        return shader->GetShaderType();
};

NIFLY_API int getShaderAttrs(void* nifref, void* shaperef, struct BSLSPAttrs* buf)
/*
    Get attributes for a BSLightingShaderProperty
    Return value: 0 = success, 1 = no shader, or not a BSLightingShaderProperty
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);

    if (!shader) return 1;

    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
    BSLightingShaderProperty* bslsp = dynamic_cast<BSLightingShaderProperty*>(shader);

    if (!bslsp) return 1;

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
    buf->Environment_Map_Scale = shader->GetEnvironmentMapScale();
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

    return 0;
};

NIFLY_API int getEffectShaderAttrs(void* nifref, void* shaperef, struct BSESPAttrs* buf)
/*
    Get attributes for a BSEffectShaderProperty
    Return value: 0 = success, 1 = no shader, or not a BSEffectShaderProperty
*/
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);

    if (!shader) return 1;

    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
    BSEffectShaderProperty* bsesp = dynamic_cast<BSEffectShaderProperty*>(shader);

    if (!bsesp) return 1;

    FillMemory(buf, sizeof(BSESPAttrs), 0);

    if (bssh) buf->Shader_Flags_1 = bssh->shaderFlags1;
    if (bssh) buf->Shader_Flags_2 = bssh->shaderFlags2;
    buf->UV_Offset_U = shader->GetUVOffset().u;
    buf->UV_Offset_V = shader->GetUVOffset().v;
    buf->UV_Scale_U = shader->GetUVScale().u;
    buf->UV_Scale_V = shader->GetUVScale().v;
    buf->Tex_Clamp_Mode = bsesp->textureClampMode;
    //buf->Lighting_Influence = bsesp->light;
    //buf->Env_Map_Min_LOD = bsesp->getEnvmapMinLOD();
    buf->Falloff_Start_Angle = bsesp->falloffStartAngle;
    buf->Falloff_Stop_Angle = bsesp->falloffStopAngle;
    buf->Falloff_Start_Opacity = bsesp->falloffStartOpacity;
    buf->Falloff_Stop_Opacity = bsesp->falloffStopOpacity;
    buf->Emissive_Color_R = shader->GetEmissiveColor().r;
    buf->Emissive_Color_G = shader->GetEmissiveColor().g;
    buf->Emissive_Color_B = shader->GetEmissiveColor().b;
    buf->Emissive_Color_A = shader->GetEmissiveColor().a;
    buf->Emissmive_Mult = shader->GetEmissiveMultiple();
    buf->Soft_Falloff_Depth = bsesp->softFalloffDepth;
    buf->Env_Map_Scale = shader->GetEnvironmentMapScale();

    return 0;
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
    shader->SetEnvironmentMapScale(buf->Environment_Map_Scale);
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

NIFLY_API void setEffectShaderAttrs(void* nifref, void* shaperef, struct BSESPAttrs* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiShape* shape = static_cast<NiShape*>(shaperef);

    NiShader* shader = nif->GetShader(shape);;
    BSShaderProperty* bssh = dynamic_cast<BSShaderProperty*>(shader);
    BSEffectShaderProperty* bsesp= dynamic_cast<BSEffectShaderProperty*>(shader);
    NiTexturingProperty* txtProp = nif->GetTexturingProperty(shape);

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

int getInvMarker(void* nifref, char* name, int namelen, int* rot, float* zoom)
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
    NiHeader hdr = nif->GetHeader();
    NiAVObject* source = nif->GetRootNode();

    for (auto& extraData : source->extraDataRefs) {
        BSInvMarker* invm = hdr.GetBlock<BSInvMarker>(extraData);
        if (invm) {
            strncpy_s(name, namelen, invm->name.get().c_str(), namelen - 1);
            rot[0] = invm->rotationX;
            rot[1] = invm->rotationY;
            rot[2] = invm->rotationZ;
            *zoom = invm->zoom;
            return 1;
        }
    }
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

void setInvMarker(void* nifref, const char* name, int* rot, float* zoom)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    auto inv = std::make_unique<BSInvMarker>();
    inv->name.get() = name;
    inv->rotationX = rot[0];
    inv->rotationY = rot[1];
    inv->rotationZ = rot[2];
    inv->zoom = *zoom;
    nif->AssignExtraData(nif->GetRootNode(), std::move(inv));
}

int getBSXFlags(void* nifref, int* buf)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiAVObject* source = nif->GetRootNode();

    for (auto& extraData : source->extraDataRefs) {
        BSXFlags* f = hdr.GetBlock<BSXFlags>(extraData);
        if (f) {
            *buf = f->integerData;
            return 1;
        }
    }
    return 0;
}

void setBSXFlags(void* nifref, const char* name, uint32_t flags)
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    auto bsx = std::make_unique<BSXFlags>();
    bsx->name.get() = name;
    bsx->integerData = flags;
    nif->AssignExtraData(nif->GetRootNode(), std::move(bsx));
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

void* getCollision(void* nifref, void* noderef) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::NiNode* node = static_cast<nifly::NiNode*>(noderef);

    return hdr.GetBlock(node->collisionRef);
};

NIFLY_API void* addCollision(void* nifref, void* targetref, int body_index, int flags) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkRigidBody* theBody = nif->GetHeader().GetBlock<bhkRigidBody>(body_index);
    nifly::NiNode* targ;
    if (targetref)
        targ = static_cast<nifly::NiNode*>(targetref);
    else
        targ = nif->GetRootNode();

    auto c = std::make_unique<bhkCollisionObject>();
    c->bodyRef.index = body_index;
    c->targetRef.index = nif->GetHeader().GetBlockID(targ);
    c->flags = flags;
    uint32_t newid = nif->GetHeader().AddBlock(std::move(c));
    targ->collisionRef.index = newid;
    
    return nif->GetHeader().GetBlock(targ->collisionRef);
};

NIFLY_API int getCollBlockname(void* node, char* buf, int buflen) {
    nifly::bhkCollisionObject* theNode = static_cast<nifly::bhkCollisionObject*>(node);
    if (theNode) {
        std::string name = theNode->GetBlockName();
        int copylen = std::min((int)buflen - 1, (int)name.length());
        name.copy(buf, copylen, 0);
        buf[copylen] = '\0';
        return int(name.length());
    }
    else
        return 0;
}

NIFLY_API int getCollBodyID(void* nifref, void* node) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkCollisionObject* theNode = static_cast<nifly::bhkCollisionObject*>(node);
    if (theNode)
        return theNode->bodyRef.index;
    else
        return 0;
}

NIFLY_API int addRigidBody(void* nifref, const char* type, uint32_t collShapeIndex, BHKRigidBodyBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    std::unique_ptr<bhkRigidBody> theBody;
    if (strcmp(type, "bhkRigidBodyT") == 0)
        theBody = std::make_unique<bhkRigidBodyT>();
    else
        theBody = std::make_unique<bhkRigidBody>();

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
    theBody->shapeRef.index = collShapeIndex;
    int newid = nif->GetHeader().AddBlock(std::move(theBody));

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

NIFLY_API int getRigidBodyProps(void* nifref, int nodeIndex, BHKRigidBodyBuf* buf)
/*
    Return the rigid body details. Return value = 1 if the node is a rigid body, 0 if not 
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkWorldObject* theWO = hdr.GetBlock<bhkWorldObject>(nodeIndex);
    nifly::bhkRigidBody* theBody = hdr.GetBlock<bhkRigidBody>(nodeIndex);

    if (theWO) {
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
        buf->bodyFlagsInt = theBody->bodyFlagsInt;
        buf->bodyFlags = theBody->bodyFlags;
        return 1;
    }
    else
        return 0;
}

NIFLY_API int getRigidBodyShapeID(void* nifref, int nodeIndex) {
    /* Returns the block index of the collision shape */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkRigidBody* theBody = hdr.GetBlock<bhkRigidBody>(nodeIndex);
    if (theBody)
        return theBody->shapeRef.index;
    else
        return -1;
}

NIFLY_API int getCollShapeBlockname(void* nifref, int nodeIndex, char* buf, int buflen) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkShape* theBody = hdr.GetBlock<bhkShape>(nodeIndex);

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

NIFLY_API int getCollConvexVertsShapeProps(void* nifref, int nodeIndex, BHKConvexVertsShapeBuf* buf)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkConvexVerticesShape* sh = hdr.GetBlock<bhkConvexVerticesShape>(nodeIndex);

    if (sh) {
        buf->material = sh->GetMaterial();
        buf->radius = sh->radius;
        buf->vertsProp_data = sh->vertsProp.data;
        buf->vertsProp_size = sh->vertsProp.size;
        buf->vertsProp_flags = sh->vertsProp.capacityAndFlags;
        buf->normalsProp_data = sh->normalsProp.data;
        buf->normalsProp_size = sh->normalsProp.size;
        buf->normalsProp_flags = sh->normalsProp.capacityAndFlags;
        return 1;
    }
    else
        return 0;
};

NIFLY_API int addCollConvexVertsShape(void* nifref, const BHKConvexVertsShapeBuf* buf, 
        float* verts, int vertcount, float* normals, int normcount) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    auto sh = std::make_unique<bhkConvexVerticesShape>();
    sh->SetMaterial(buf->material);
    sh->radius = buf->radius;
    for (int i = 0; i < vertcount * 4; i += 4) {
        Vector4 v = Vector4(verts[i], verts[i + 1], verts[i + 2], verts[i + 3]);
        sh->verts.push_back(v);
    };
    for (int i = 0; i < normcount * 4; i += 4) {
        Vector4 n = Vector4(normals[i], normals[i + 1], normals[i + 2], normals[i + 3]);
        sh->normals.push_back(n);
    }
    int newid = nif->GetHeader().AddBlock(std::move(sh));
    return newid;
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

NIFLY_API int getCollBoxShapeProps(void* nifref, int nodeIndex, BHKBoxShapeBuf* buf)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape, 
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkBoxShape* sh = hdr.GetBlock<bhkBoxShape>(nodeIndex);

    if (sh) {
        buf->material = sh->GetMaterial();
        buf->radius = sh->radius;
        buf->dimensions_x = sh->dimensions.x;
        buf->dimensions_y = sh->dimensions.y;
        buf->dimensions_z = sh->dimensions.z;
        return 1;
    }
    else
        return 0;
}

NIFLY_API int addCollBoxShape(void* nifref, const BHKBoxShapeBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    auto sh = std::make_unique<bhkBoxShape>();
    sh->SetMaterial(buf->material);
    sh->radius = buf->radius;
    sh->dimensions.x = buf->dimensions_x;
    sh->dimensions.y = buf->dimensions_y;
    sh->dimensions.z = buf->dimensions_z;
    int newid = nif->GetHeader().AddBlock(std::move(sh));
    return newid;
};

NIFLY_API int getCollListShapeProps(void* nifref, int nodeIndex, BHKListShapeBuf* buf)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkListShape* sh = hdr.GetBlock<bhkListShape>(nodeIndex);

    if (sh) {
        buf->material = sh->GetMaterial();
        buf->childShape_data = sh->childShapeProp.data;
        buf->childShape_size = sh->childShapeProp.size;
        buf->childShape_flags = sh->childShapeProp.capacityAndFlags;
        buf->childFilter_data = sh->childFilterProp.data;
        buf->childFilter_size = sh->childFilterProp.size;
        buf->childFilter_flags = sh->childFilterProp.capacityAndFlags;
        return 1;
    }
    else
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

NIFLY_API int addCollListShape(void* nifref, const BHKListShapeBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    auto sh = std::make_unique<bhkListShape>();
    sh->SetMaterial(buf->material);
    sh->childShapeProp.data = buf->childShape_data;
    sh->childShapeProp.size = buf->childShape_size;
    sh->childShapeProp.capacityAndFlags = buf->childShape_flags;
    sh->childFilterProp.data = buf->childFilter_data;
    sh->childFilterProp.size = buf->childFilter_size;
    sh->childFilterProp.capacityAndFlags = buf->childFilter_flags;
    int newid = nif->GetHeader().AddBlock(std::move(sh));
    return newid;
};

NIFLY_API void addCollListChild(void* nifref, const uint32_t id, uint32_t child_id) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    bhkListShape* collList = hdr.GetBlock<bhkListShape>(id);

   collList->subShapeRefs.AddBlockRef(child_id);
};

NIFLY_API int getCollConvexTransformShapeProps(
    void* nifref, int nodeIndex, BHKConvexTransformShapeBuf* buf)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkConvexTransformShape* sh = hdr.GetBlock<bhkConvexTransformShape>(nodeIndex);

    if (sh) {
        buf->material = sh->material;
        buf->radius = sh->radius;
        for (int i = 0; i < 16; i++) {
            buf->xform[i] = sh->xform[i]; 
        };
        return 1;
    }
    else
        return 0;
}

NIFLY_API int getCollConvexTransformShapeChildID(void* nifref, int nodeIndex) {
    /* Returns the block index of the collision shape */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkConvexTransformShape* sh = hdr.GetBlock<bhkConvexTransformShape>(nodeIndex);
    if (sh)
        return sh->shapeRef.index;
    else
        return -1;
}

NIFLY_API int addCollConvexTransformShape(void* nifref, const BHKConvexTransformShapeBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    auto sh = std::make_unique<bhkConvexTransformShape>();
    //sh->SetMaterial(buf->material);
    sh->material = buf->material;
    sh->radius = buf->radius;
    for (int i = 0; i < 16; i++) {
        sh->xform[i] = buf->xform[i];
    };

    int newid = nif->GetHeader().AddBlock(std::move(sh));
    return newid;
};

NIFLY_API void setCollConvexTransformShapeChild(
        void* nifref, const uint32_t id, uint32_t child_id) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    bhkConvexTransformShape* cts = hdr.GetBlock<bhkConvexTransformShape>(id);

    cts->shapeRef.index = child_id;
};

NIFLY_API int getCollCapsuleShapeProps(void* nifref, int nodeIndex, BHKCapsuleShapeBuf* buf)
/*
    Return the collision shape details. Return value = 1 if the node is a known collision shape,
    0 if not
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    nifly::bhkCapsuleShape* sh = hdr.GetBlock<bhkCapsuleShape>(nodeIndex);

    if (sh) {
        buf->material = sh->GetMaterial();
        buf->radius = sh->radius;
        buf->radius1 = sh->radius1;
        buf->radius2 = sh->radius2;
        for (int i = 0; i < 3; i++) buf->point1[i] = sh->point1[i];
        for (int i = 0; i < 3; i++) buf->point2[i] = sh->point2[i];
        return 1;
    }
    else
        return 0;
}

int addCollCapsuleShape(void* nifref, const BHKCapsuleShapeBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();

    auto sh = std::make_unique<bhkCapsuleShape>();
    sh->SetMaterial(buf->material);
    sh->radius = buf->radius;
    sh->radius1 = buf->radius1;
    sh->radius2 = buf->radius2;
    for (int i = 0; i < 3; i++) sh->point1[i] = buf->point1[i];
    for (int i = 0; i < 3; i++) sh->point2[i] = buf->point2[i];
    
    int newid = nif->GetHeader().AddBlock(std::move(sh));
    return newid;
};

/* ***************************** TRANSFORM OBJECTS ***************************** */

NIFLY_API void getControllerManager(void* ncmref, NiControllerManagerBuf* buf) {
    /* Return properties of a NiController Manager node. */
    NiControllerManager* ncm = static_cast<NiControllerManager*>(ncmref);
    buf->nextControllerID = ncm->nextControllerRef.index;
    buf->flags = ncm->flags;
    buf->frequency = ncm->frequency;
    buf->phase = ncm->phase;
    buf->startTime = ncm->startTime;
    buf->stopTime = ncm->stopTime;
    buf->targetID = ncm->targetRef.index;
    buf->cumulative = ncm->cumulative;
    buf->controllerSequenceCount = ncm->controllerSequenceRefs.GetSize();
    buf->objectPaletteID = ncm->objectPaletteRef.index;
};

int addControllerManager(void* f, const char* name, NiControllerManagerBuf* buf, void* parent) {
    /* Create a NiController Manager node. */
    NifFile* nif = static_cast<NifFile*>(f);
    NiHeader* hdr = &nif->GetHeader();

    //NiObjectNET* target = nullptr;
    //if (buf->targetID != NIF_NPOS) 
    //    target = hdr.GetBlock<NiObjectNET>(buf->targetID);
        
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

void getControllerSequence(void* nifref, uint32_t csID, NiControllerSequenceBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiControllerSequence* cs = hdr.GetBlock< NiControllerSequence>(csID);

    if (buf->bufSize == sizeof(NiControllerSequenceBuf)) {
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
    }
    else
        niflydll::LogWrite("getControllerSequence given wrong size buffer");
}

int addControllerSequence(void* nifref, const char* name, NiControllerSequenceBuf* buf) 
/* Add a ControllerSequence block */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();

    auto cs = std::make_unique<NiControllerSequence>();
    uint32_t newid = hdr->AddBlock(std::move(cs));
    NiControllerSequence* csblock = hdr->GetBlock<NiControllerSequence>(newid);
    csblock->name.get() = name;
    assignControllerSequence(hdr, csblock, buf);

    if (buf->managerID != NIF_NPOS) {
        NiControllerManager* mgr = hdr->GetBlock<NiControllerManager>(buf->managerID);
        mgr->controllerSequenceRefs.AddBlockRef(newid);
    }

    return newid;
}

NIFLY_API int getControlledBlocks(void* nifref, uint32_t csID, int buflen, ControllerLinkBuf* blocks) {
/* Return the "ControllerLink blocks, children of NiControllerSequence blocks */
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerSequence* cs = hdr->GetBlock<NiControllerSequence>(csID);

    if (!cs) {
        niflydll::LogWrite("Error: getControlledBlocks called on invalid block type.");
    }

    int i = 0;
    for (auto& cl : cs->controlledBlocks) {
        if (i >= buflen) break;
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

    return cs->controlledBlocks.size();
}

NIFLY_API void addControlledBlock(void* nifref, uint32_t csID, const char* name, ControllerLinkBuf* b) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiControllerSequence* cs = hdr->GetBlock<NiControllerSequence>(csID);

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
}

void getTransformInterpolator(void* nifref, uint32_t tiID, NiTransformInterpolatorBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformInterpolator* ti = hdr->GetBlock<NiTransformInterpolator>(tiID);

    if (!ti) {
        niflydll::LogWrite("ERROR: Node is not a NiTransformInterpolator.");
        return;
    }

    if (buf->bufSize != sizeof(NiTransformInterpolatorBuf)) {
        niflydll::LogWrite("ERROR: NiTransformInterpolator buffer wrong size.");
        return;
    }
    for (int i=0; i < 3; i++) buf->translation[i] = ti->translation[i];
    buf->rotation[0] = ti->rotation.w;
    buf->rotation[1] = ti->rotation.x;
    buf->rotation[2] = ti->rotation.y;
    buf->rotation[3] = ti->rotation.z;
    buf->scale = ti->scale;
    buf->dataID = ti->dataRef.index;
}

int addTransformInterpolator(void* nifref, NiTransformInterpolatorBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();

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

NIFLY_API void getMultiTargetTransformController(void* nifref, int mttcID, 
        NiMultiTargetTransformControllerBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader hdr = nif->GetHeader();
    NiMultiTargetTransformController* mttc 
        = hdr.GetBlock<NiMultiTargetTransformController>(uint32_t(mttcID));
    buf->nextControllerID = mttc->nextControllerRef.index;
    buf->flags = mttc->flags;
    buf->frequency = mttc->frequency;
    buf->phase = mttc->phase;
    buf->startTime = mttc->startTime;
    buf->stopTime = mttc->stopTime;
    buf->targetID = mttc->targetRef.index;
    buf->targetCount = mttc->targetRefs.GetSize();
}

int addMultiTargetTransformController(void* nifref, NiMultiTargetTransformControllerBuf* buf) {
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();

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

NIFLY_API int getTransformController(void* nifref, int nodeIndex, NiTransformControllerBuf* buf)
/*
    Return a Transform Controller block.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    NiTransformController* sh = hdr->GetBlock<NiTransformController>(nodeIndex);

    if (sh) {
        buf->flags = sh->flags;
        buf->frequency = sh->frequency;
        buf->phase = sh->phase;
        buf->startTime = sh->startTime;
        buf->stopTime = sh->stopTime;
        buf->targetIndex = sh->targetRef.index;
        buf->interpolatorIndex = sh->interpolatorRef.index;
        buf->nextControllerIndex = sh->nextControllerRef.index;
        return 1;
    }
    else
        return 0;
};

NIFLY_API int addTransformController(void* nifref, NiTransformControllerBuf* buf, int parent)
/* Create a Transform Controller block. */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();

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

int getTransformData(void* nifref, int nodeIndex, NiTransformDataBuf* buf)
/*
    Return a Transform Data block.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    nifly::NiTransformData* sh = hdr->GetBlock<NiTransformData>(nodeIndex);

    if (buf->bufSize == sizeof(NiTransformDataBuf)) {
        if (sh) {
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
            return 1;
        }
        else {
            niflydll::LogWrite("ERROR: Passed node is not a NiTransformData.");
            return 0;
        }
    }
    else {
        niflydll::LogWrite("ERROR: NiTransformDataBuf wrong size.");
        return 0;
    }
};

int addTransformData(void* nifref, NiTransformDataBuf* buf, int parent)
/*
    Add a Transform Data block. If supplied, parent is the NiTransformInterpolator that 
    uses this data.
    */
{
    NifFile* nif = static_cast<NifFile*>(nifref);
    NiHeader* hdr = &nif->GetHeader();
    
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

