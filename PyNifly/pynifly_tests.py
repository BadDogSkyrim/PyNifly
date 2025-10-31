"""
######################################## TESTS ########################################

Regression tests for the pynifly layer.

As much of the import/export functionality as possible should be tested here.
Leave the tests in Blender to test Blender-specific functionality.

######################################## TESTS ########################################
"""
import os
# import struct
# from enum import Enum, IntFlag, IntEnum
# from math import asin, atan2, pi, sin, cos
# import xml.etree.ElementTree as xml
# from niflytools import *
# from nifdefs import *
# import xmltools
import codecs
import ctypes

from requests import head 
from niflytools import *
from nifdefs import *
import test_tools as TT
from pynifly import *
from test_nifchecker import CheckNif


"""Quick and dirty test harness."""

def _test_file(relative_path):
    """
    Given a relative path, return a working filepath to the file. If it's in 
    the output directory, delete it.
    """
    rp = relative_path.upper()
    if "TESTS/OUT" in rp or r"TESTS\OUT" in rp:
        if os.path.exists(relative_path):
            os.remove(relative_path)
    return relative_path


def _export_shape(old_shape: NiShape, new_nif: NifFile, properties=None, verts=None, parent=None):
    """ 
    Convenience routine to copy an existing shape from a source nif to a test file.

    Returns the created shape.
    """
    skinned = (len(old_shape.bone_weights) > 0)

    # Somehow the UV needs inversion. Probably a bug but we've lived with it so long...
    uv_inv = [(x, 1-y) for x, y in old_shape.uvs]

    if properties:
        new_prop:NiShapeBuf = properties
    else:
        new_prop:NiShapeBuf = old_shape.properties.copy()
    new_prop.nameID = new_prop.conrollerID = new_prop.collisionID = NODEID_NONE
    new_prop.skinInstanceID = new_prop.shaderPropertyID = new_prop.alphaPropertyID = NODEID_NONE
    new_shape = new_nif.createShapeFromData(old_shape.name, 
                                            verts if verts else old_shape.verts,
                                            old_shape.tris,
                                            uv_inv,
                                            old_shape.normals,
                                            props=new_prop,
                                            use_type=old_shape.properties.bufType,
                                            parent=parent
                                            )

    new_shape.set_colors(old_shape.colors)

    new_shape.transform = old_shape.transform.copy()
    oldxform = old_shape.global_to_skin
    if oldxform is None:
        oldxform = old_shape.transform
    new_shape_gts = oldxform # no inversion?
    if skinned: new_shape.set_global_to_skin(new_shape_gts)

    for bone_name, weights in old_shape.bone_weights.items():
        new_shape.add_bone(bone_name, old_shape.file.nodes[bone_name].global_transform)

    for bone_name, weights in old_shape.bone_weights.items():
        sbx = old_shape.get_shape_skin_to_bone(bone_name)
        new_shape.set_skin_to_bone_xform(bone_name, sbx)

        new_shape.setShapeWeights(bone_name, weights)

    # Copy shader property from the original nif. We have mucked with the properties 
    # because of handling materials files, so this ensures we get the original values.
    new_shape.shader.name = old_shape.shader.name
    p = BSLightingShaderProperty.getbuf()
    NifFile.nifly.getBlock(
            old_shape.file._handle, 
            old_shape.shader.id, 
            byref(p))
    new_shape.shader._properties = p

    new_shape.save_shader_attributes()

    alpha = AlphaPropertyBuf()
    if old_shape.has_alpha_property:
        new_shape.has_alpha_property = True
        new_shape.alpha_property.properties.flags = old_shape.alpha_property.properties.flags
        new_shape.alpha_property.properties.threshold = old_shape.alpha_property.properties.threshold
        # if old_shape.alpha_property.controller:
        #     assert old_shape.alpha_property.controller.blockname == 'NiAlphaPropertyTestRefController', \
        #         "Only handling NiAlphaPropertyTestRefController"
        #     controller_prop = old_shape.alpha_property.controller.properties.copy()
        #     controller_prop.targetID = NODEID_NONE
        #     controller_prop.nextControllerID = NODEID_NONE
        #     interpolator_prop = old_shape.alpha_property.controller.interpolator.properties.copy()
        #     data_prop = old_shape.alpha_property.controller.interpolator.data.properties.copy()

        new_shape.save_alpha_property()

    for k, t in old_shape.textures.items():
        new_shape.set_texture(k, t)

    new_shape.behavior_graph_data = old_shape.behavior_graph_data
    new_shape.string_data = old_shape.string_data

    if old_shape.shader.controller:
        old_controller = old_shape.shader.controller
        if isinstance(old_controller, NiFloatInterpController):
            blkname = ctypes.create_string_buffer(128)
            NifFile.nifly.getBlockname(new_nif._handle, new_shape.shader.id, blkname, 128)
            name = blkname.value.decode('utf-8') 
            
            controller_prop = old_controller.properties.copy()
            controller_prop.targetID = NODEID_NONE
            controller_prop.nextControllerID = NODEID_NONE
            interpolator_prop = old_controller.interpolator.properties.copy()
            data_prop = old_controller.interpolator.data.properties.copy()
            new_data = NiFloatData(
                file=new_nif,
                properties=data_prop,
                keys=old_controller.interpolator.data.keys
            )
            interpolator_prop.dataID = new_data.id
            new_interp = NiFloatInterpolator(
                file=new_nif,
                properties=interpolator_prop
            )
            controller_prop.interpolatorID = new_interp.id
            new_controller = BSEffectShaderPropertyFloatController(
                file=new_nif, 
                properties=controller_prop, 
                parent=new_shape.shader
            )
    
    return new_shape


def TEST_NIFDEFS():
    """Test nifdefs functionality."""
    # Easier to do it here.

    # The different shape buffers initialize their ID values, but can also be set from
    # a dictionary object.
    b = NiShapeBuf({"flags": 24, "collisionID": 4})
    assert b.flags == 24, f"Flags are correct"
    assert b.collisionID == 4, f"collisionID is set"
    assert b.shaderPropertyID == NODEID_NONE, f"shaderPropertyID is not set"

    b = BSLODTriShapeBuf({"flags": 24, "collisionID": 4})
    assert b.flags == 24, f"Flags are correct"
    assert b.collisionID == 4, f"collisionID is set"
    assert b.shaderPropertyID == NODEID_NONE, f"shaderPropertyID is not set"

    b = BSLODTriShapeBuf({"flags": 24, "collisionID": 4})
    assert b.flags == 24, f"Flags are correct"
    assert b.collisionID == 4, f"collisionID is set"
    assert b.shaderPropertyID == NODEID_NONE, f"shaderPropertyID is not set"

    # Can read and store shader property values.
    # Regression: parallaxInnerLayerTextureScale gave problems
    b = NiShaderBuf({"Shader_Type": BSLSPShaderType.Face_Tint, 
                        "parallaxInnerLayerTextureScale": "[0.949999988079071, 0.949999988079071]"})
    assert b.Shader_Type == BSLSPShaderType.Face_Tint, f"Have correct face tint"
    assert VNearEqual(b.parallaxInnerLayerTextureScale[:], [0.95, 0.95]), "Have correct parallaxInnerLayerTextureScale"


def TEST_READ():
    """Test reading various nifs"""
    testfile = r"tests\SkyrimSE\meshes\actors\character\character assets\maleheadkhajiit.nif"
    outfile = 'tests/out/TEST_KHAJIIT_RW.nif'
    nif = NifFile(testfile)
    CheckNif(nif)

    testfile = r"tests\SkyrimSE\eyesmale.nif"
    CheckNif(nif)


def TEST_RW_HEAD():
    """Test reading and writing the male head"""
    testfile = r"tests\Skyrim\malehead.nif"
    outfile = r"tests/Out/TEST_RW_HEAD.nif"

    nif = NifFile(testfile)
    CheckNif(nif)

    nifout = NifFile()
    nifout.initialize('SKYRIM', outfile)
    _export_shape(nif.shapes[0], nifout)
    trilist = [nif.shapes[0].partitions[t].id for t in nif.shapes[0].partition_tris]
    nifout.shapes[0].set_partitions(nif.shapes[0].partitions, trilist)
    nifout.save()

    nifcheck = NifFile(outfile)
    CheckNif(nifcheck, testfile)



def TEST_SHAPE_QUERY():
    """NifFile object gives access to a nif"""

    # NifFile can be read from a file. It provides game name and root node for that game.
    f1 = NifFile("tests/skyrim/test.nif")
    assert f1.game == "SKYRIM", "'game' property gives the game the nif is good for"
    assert f1.rootName == "Scene Root", "'rootName' is the name of the root node in the file: " + str(f1.rootName)
    assert f1.nodes[f1.rootName].blockname == 'NiNode', f"'blockname' is the type of block"

    # Same for FO4 nifs
    f2 = NifFile("tests/FO4/AlarmClock.nif")
    assert f2.game == "FO4", "ERROR: Test file not FO4"

    # getAllShapeNames returns names of meshes within the nif
    all_shapes = f1.getAllShapeNames()
    expected_shapes = set(["Armor", 'MaleBody'])
    assert set(all_shapes) == expected_shapes, \
        f'ERROR: Test shape names expected in {str(all_shapes)}'

    # The shapes property lists all the meshes in the nif, whatever the format, as NiShape
    assert len(f1.shapes) == 2, "ERROR: Test file does not have 2 shapes"

    # The shape name is the node name from the nif
    assert f1.shapes[0].name in expected_shapes, \
        f"ERROR: first shape name not expected: {f1.shapes[0].name}"
    
    # Find a particular shape using the shape dictionary
    armor = f1.shape_dict["Armor"]
    body = f1.shape_dict["MaleBody"]
    assert armor.name == "Armor", f"Error: Found wrong shape: {armor.name}"

    # The shape blockname is the type of block == type of shape
    assert armor.blockname == "NiTriShape", f"ERROR: Should be a trishape: {armor.blockname}"

    # Can check whether a shape is skinned.
    assert armor.has_skin_instance, f"ERROR: Armor should be skinned: {armor.has_skin_instance}"

    f2 = NifFile("tests/skyrim/noblecrate01.nif")
    assert not f2.shapes[0].has_skin_instance, "Error: Crate should not be skinned"

    # A NiShape's verts property is a list of triples containing x,y,z position
    verts = f2.shapes[0].verts
    assert len(verts) == 686, "ERROR: Did not import 686 verts"
    assert round(verts[0][0], 4) == -67.6339, "ERROR: First vert wrong"
    assert round(verts[0][1], 4) == -24.8498, "ERROR: First vert wrong"
    assert round(verts[0][2], 4) == 0.2476, "ERROR: First vert wrong"
    assert round(verts[685][0], 4) == -64.4469, "ERROR: Last vert wrong"
    assert round(verts[685][1], 4) == -16.3246, "ERROR: Last vert wrong"
    assert round(verts[685][2], 4) == 26.4362, "ERROR: Last vert wrong"

    # Normals follow the verts
    assert len(f2.shapes[0].normals) == 686, "ERROR: Expected 686 normals"
    assert (round(f2.shapes[0].normals[0][0], 4) == 0.0), "Error: First normal wrong"
    assert (round(f2.shapes[0].normals[0][1], 4) == -0.9776), "Error: First normal wrong"
    assert (round(f2.shapes[0].normals[0][2], 4) == 0.2104), "Error: First normal wrong"
    assert (round(f2.shapes[0].normals[685][0], 4) == 0.0), "Error: Last normal wrong"
    assert (round(f2.shapes[0].normals[685][1], 4) == 0.0), "Error: Last normal wrong"
    assert (round(f2.shapes[0].normals[685][2], 4) == 1.0), "Error: Last normal wrong"

    # A NiShape's tris property is a list of triples defining the triangles. Each triangle
    # is a triple of indices into the verts list.
    tris = f2.shapes[0].tris
    assert len(tris) == 258, "ERROR: Did not import 258 tris"
    assert tris[0] == (0, 1, 2), "ERROR: First tri incorrect"
    assert tris[1] == (2, 3, 0), "ERROR: Second tri incorrect"

    # We're using fixed-length buffers internally to pass these lists back and forth, but that
    # doesn't affect the caller.
    verts = body.verts 
    assert len(verts) == 2024, "ERROR: Wrong vert count for second shape - " + str(len(f1.shapes[1].verts))

    assert round(verts[0][0], 4) == 0.0, "ERROR: First vert wrong"
    assert round(verts[0][1], 4) == 8.5051, "ERROR: First vert wrong"
    assert round(verts[0][2], 4) == 96.5766, "ERROR: First vert wrong"
    assert round(verts[2023][0], 4) == -4.4719, "ERROR: Last vert wrong"
    assert round(verts[2023][1], 4) == 8.8933, "ERROR: Last vert wrong"
    assert round(verts[2023][2], 4) == 92.3898, "ERROR: Last vert wrong"
    tris = body.tris
    assert len(tris) == 3680, "ERROR: Wrong tri count for second shape - " + str(len(f1.shapes[1].tris))
    assert tris[0][0] == 0, "ERROR: First tri wrong"
    assert tris[0][1] == 1, "ERROR: First tri wrong"
    assert tris[0][2] == 2, "ERROR: First tri wrong"
    assert tris[3679][0] == 85, "ERROR: Last tri wrong"
    assert tris[3679][1] == 93, "ERROR: Last tri wrong"
    assert tris[3679][2] == 88, "ERROR: Last tri wrong"

    # The transformation on the nif is recorded as the transform property on the shape.
    # This isn't used on skinned nifs, tho it's often set on Skyrim's nifs.
    xfbody = body.transform
    assert VNearEqual(xfbody.translation, [0.0, 0.0, 0.0]), "ERROR: Body location not 0"
    assert xfbody.scale == 1.0, "ERROR: Body scale not 1"
    xfarm = armor.transform
    assert VNearEqual(xfarm.translation, [-0.0003, -1.5475, 120.3436]), "ERROR: Armor location not correct"

    # What really matters for skinned shapes is the global-to-skin transform, which is an 
    # offset for the entire # shape. It's stored explicitly in Skyrim's nifs, calculated 
    # in FO4's.
    # Note this is the inverse of the shape transform.
    g2sk = armor.global_to_skin
    assert VNearEqual(g2sk.translation, [0.0003, 1.5475, -120.3436]),\
        "ERROR: Global to skin incorrect: {g2sk.translation}"

    # Shapes have UVs. The UV map is a list of UV pairs, 1:1 with the list of verts. 
    # Nifs don't allow one vert to have two UV locations.
    uvs = f2.shapes[0].uvs
    assert len(uvs) == 686, "ERROR: UV count not correct"
    assert list(round(x, 4) for x in uvs[0]) == [0.4164, 0.419], "ERROR: First UV wrong"
    assert list(round(x, 4) for x in uvs[685]) == [0.4621, 0.4327], "ERROR: Last UV wrong"

    # Bones are represented as nodes on the NifFile. Bones don't have a special type
    # in the nif, so we just bring in all NiNodes. Bones have names and transforms.
    assert len([n for n in f1.nodes.values() if type(n) == NiNode]) == 30, "ERROR: Number of bones incorrect"
    uatw = f1.nodes["NPC R UpperarmTwist2 [RUt2]"]
    assert uatw.name == "NPC R UpperarmTwist2 [RUt2]", "ERROR: Node name wrong"
    assert VNearEqual(uatw.transform.translation, [15.8788, -5.1873, 100.1124]), \
        "ERROR: Location incorrect: {uatw.transform}"

    # A skinned shape has a list of bones that influence the shape. 
    # The bone_names property returns the names of these bones.
    try:
        assert 'NPC Spine [Spn0]' in body.bone_names, "ERROR: Spine not in shape: {body.bone_names}"
    except:
        print("ERROR: Did not find bone in list")
    
    # A shape has a list of bone_ids in the shape. These are just an index, 0..#-of-bones.
    # Nifly uses this to reference the bones, but we don't need it.
    assert len(body.bone_ids) == len(body.bone_names), "ERROR: Mismatch between names and IDs"

    # The bone_weights dictionary captures weights for each bone that influences a shape. 
    # The value lists (vertex-index, weight) for each vertex it influences.
    assert len(body.bone_weights['NPC L Foot [Lft ]']) == 13, "ERRROR: Wrong number of bone weights"


def TEST_BodyRegression():
    """Test troublesome nif file"""

    f = NifFile("tests/FO4/BodyRegression/MaleBody.nif")
    assert len(f.shapes[0].verts) > 39000, "Have very many verts"
    assert len(f.shapes[0].tris) > 76000, "Have very many tris"


def TEST_CREATE_TETRA():
    """Can create new files with content: tetrahedron"""
    # Vertices are a list of triples defining the coordinates of each vertex
    verts = [(0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (2.0, 2.0, 0.0),
                (1.0, 1.0, 2.0),
                (1.0, 1.0, 2.0),
                (1.0, 1.0, 2.0)]
    #Normals are 1:1 with vertices because nifs only allow one normal per vertex
    norms = [(-1.0, -1.0, -0.5),
                (1.0, -1.0, -1.0),
                (1.0, 2.0, -1.0),
                (0.0, 0.0, 1.0),
                (0.0, 0.0, 1.0),
                (0.0, 0.0, 1.0)]
    #Tris are a list of triples, indices into the vertex list
    tris = [(2, 1, 0),
            (1, 3, 0),
            (2, 4, 1),
            (5, 2, 0)]
    #UVs are 1:1 with vertices because only one UV point allowed per vertex.  Values
    #are in the range 0-1.
    uvs = [(0.4370, 0.8090),
            (0.7460, 0.5000),
            (0.4370, 0.1910),
            (0.9369, 1.0),
            (0.9369, 0.0),
            (0.0, 0.5000) ]
    
    # Create a nif with an empty NifFile object, then initializing it with game and filepath.
    # Can create a shape in one call by passing in these lists
    newf = NifFile()
    newf.initialize("SKYRIM", "tests/out/testnew01.nif")
    newf.rootNode.flags = 14
    newf.createShapeFromData("FirstShape", verts, tris, uvs, norms)
    newf.save()

    newf_in = NifFile("tests/out/testnew01.nif")
    assert newf_in.shapes[0].name == "FirstShape", "ERROR: Didn't get expected shape back"
    assert newf_in.rootNode.flags == 14, f"Have correct flags: {newf_in.rootNode.flags}"

    # Skyrim and FO4 work the same way
    newf2 = NifFile()
    newf2.initialize("FO4", "tests/out/testnew02.nif")
    newf2.createShapeFromData("FirstShape", verts, tris, uvs, norms,
                                use_type=PynBufferTypes.BSTriShapeBufType) # , is_skinned=False)
    newf2.save()

    newf2_in = NifFile("tests/out/testnew02.nif")
    assert newf2_in.shapes[0].name == "FirstShape", "ERROR: Didn't get expected shape back"
    assert newf2_in.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape, found {newf2_in.shapes[0].blockname}"

    #Transforms are set by putting them on the NiShape
    newf3 = NifFile()
    newf3.initialize("SKYRIM", "tests/out/testnew03.nif")
    shape = newf3.createShapeFromData("FirstShape", verts, tris, uvs, norms)
    shape.transform = TransformBuf().set_identity()
    shape.transform.translation = VECTOR3(1.0, 2.0, 3.0)
    shape.transform.scale = 1.5
    newf3.save()

    newf3_in = NifFile("tests/out/testnew03.nif")
    xf3 = newf3_in.shapes[0].transform
    assert VNearEqual(xf3.translation, (1.0, 2.0, 3.0)), "ERROR: Location transform wrong"
    assert xf3.scale == 1.5, "ERROR: Scale transform wrong"

def TEST_CREATE_WEIGHTS():
    """Can create tetrahedron with bone weights (Skyrim)"""
    verts = [(0.0, 1.0, -1.0), (0.866, -0.5, -1.0), (-0.866, -0.5, -1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
    norms = [(0.0, 0.9219, -0.3873), (0.7984, -0.461, -0.3873), (-0.7984, -0.461, -0.3873), (-0.8401, 0.4851, 0.2425), (0.8401, 0.4851, 0.2425), (0.0, -0.9701, 0.2425)]
    tris = [(0, 4, 1), (0, 1, 2), (1, 5, 2), (2, 3, 0)]
    uvs = [(0.46, 0.30), (0.80, 0.5), (0.46, 0.69), (0.0, 0.5), (0.86, 0.0), (0.86, 1.0)]
    
    # These weights are 1:1 with verts, listing the bones that influence the vert.
    weights = [{"Bone.001": 0.0974, "Bone.003": 0.9026},
                {"Bone.002": 0.0715, "Bone.003": 0.9285},
                {"Bone": 0.0000, "Bone.001": 0.0000, "Bone.002": 0.0000, "Bone.003": 1.0000},
                {"Bone": 0.9993, "Bone.003": 0.0007}, 
                {"Bone": 0.9993, "Bone.003": 0.0007},
                {"Bone": 0.9993, "Bone.003": 0.0007}]
    group_names = ["Bone", "Bone.001", "Bone.002", "Bone.003"]
    arma_bones = {"Bone": (0,0,0.5), "Bone.001": (-0.009,1.016,-0.988), 
                    "Bone.002": (0.858,-0.48,-0.96), "Bone.003": (-0.83,-0.559,-0.955)}
    bones = BoneDict([
        SkeletonBone('Bone', 'BONE1'),
        SkeletonBone("Bone.001", "BONE2"), 
        SkeletonBone("Bone.002", "BONE3"),
        SkeletonBone("Bone.003", "BONE4") ],
        {}, [])

    newf4 = NifFile()
    newf4.initialize("SKYRIM", "tests/out/testnew04.nif")
    # Need a skin to attach a mesh to an armature.  Can create the skin on the
    # NifFile, then on the NiShape, but putting it on the NifFile is optional.  The
    # shape will make sure its nif is set up.
    shape4 = newf4.createShapeFromData("WeightedTetra", verts, tris, uvs, norms)
    shape4.transform.translation = (0,0,0)
    shape4.transform.scale = 1.0
    shape4.skin()

    # It's sometimes convenient to have a bone and ask what verts it influences,
    # other times to have a vert and ask what bones influence it.  weights_by_bone
    # goes from weights by vert to by bone.
    weights_by_bone = get_weights_by_bone(weights, ['Bone', 'Bone.001', 'Bone.002', 'Bone.003'])
    used_bones = weights_by_bone.keys()

    # Need to add the bones to the shape before you can weight them.
    for b in arma_bones:
        xf = TransformBuf()
        xf.translation = arma_bones[b]
        shape4.add_bone(bones.nif_name(b), xf)

    # Transforms position parts relative to their parent or absolute in the global
    # reference frame.  The global to skin transform makes that translation.  Note
    # the skindata transform uses a block that only Skyrim nifs have.
    bodyPartXform = TransformBuf().set_identity()
    bodyPartXform.translation = VECTOR3(0.000256, 1.547526, -120.343582)
    shape4.set_global_to_skin(bodyPartXform)

    # SetShapeWeights sets the vertex weights from a bone
    for bone_name, weights in weights_by_bone.items():
        if (len(weights) > 0):
            nif_name = bones.nif_name(bone_name)
            xf = TransformBuf()
            xf.translation = arma_bones[bone_name]
            shape4.set_skin_to_bone_xform(nif_name, bodyPartXform)
            shape4.setShapeWeights(nif_name, weights)

    newf4.save()

    # The skin-to-bone transform is the local transform for the bone as it's used by
    # the skin.  This lets the game move the verts relative to the bone as it's moved
    # in animations.
    newf4in = NifFile("tests/out/testnew04.nif")
    newshape = newf4in.shapes[0]
    xform = newshape.get_shape_skin_to_bone("BONE2")
    assert not VNearEqual(xform.translation, [0.0, 0.0, 0.0]), "Error: Translation should not be null"


def TEST_READ_WRITE():
    """Basic load-and-store for Skyrim--Can read the armor nif and spit out armor and body separately"""
    testfile = "tests/Skyrim/test.nif"
    outfile1 = "tests/Out/TEST_READ_WRITE1.nif"
    outfile2 = "tests/Out/TEST_READ_WRITE2.nif"
    outfile3 = "tests/Out/TEST_READ_WRITE3.nif"
    if os.path.exists(outfile1):
        os.remove(outfile1)
    if os.path.exists(outfile2):
        os.remove(outfile2)
    if os.path.exists(outfile3):
        os.remove(outfile3)

    nif = NifFile(testfile)
    assert "Armor" in nif.getAllShapeNames(), "ERROR: Didn't read armor"
    assert "MaleBody" in nif.getAllShapeNames(), "ERROR: Didn't read body"

    the_armor = nif.shape_dict["Armor"]
    the_body = nif.shape_dict["MaleBody"]
    assert len(the_armor.verts) == 2115, "ERROR: Wrong number of verts"
    assert (len(the_armor.tris) == 3195), "ERROR: Wrong number of tris"

    assert int(the_armor.transform.translation[2]) == 120, "ERROR: Armor shape is raised up"
    assert the_armor.has_skin_instance, "Error: Armor should be skinned"

    """Can save armor to Skyrim"""
    new_nif = NifFile()
    new_nif.initialize("SKYRIM", outfile1)
    _export_shape(the_armor, new_nif)    
    new_nif.save()

    # Armor and body nifs are generally positioned below ground level and lifted up with a transform, 
    # approx 120 in the Z direction. The transform on the armor shape is actually irrelevant;
    # it's the global_to_skin and skin-to-bone transforms that matter.
    test_nif = NifFile(outfile1)
    armor01 = test_nif.shapes[0]
    assert int(armor01.transform.translation[2]) == 120, \
        f"ERROR: Armor shape should be set at 120 in '{outfile1}'"
    assert int(armor01.global_to_skin.translation[2]) == -120, \
        f"ERROR: Armor skin instance should be at -120 in {outfile1}"
    assert the_armor.global_to_skin.NearEqual(armor01.global_to_skin), "ERROR: global-to-skin differs: {armor01.global_to_skin}"
    ftxf = the_armor.get_shape_skin_to_bone('NPC L ForearmTwist1 [LLt1]')
    ftxf01 = armor01.get_shape_skin_to_bone('NPC L ForearmTwist1 [LLt1]')
    assert int(ftxf01.translation[2]) == -5, \
        f"ERROR: Skin transform Z should be -5.0, have {ftxf01.translation}"
    assert ftxf.NearEqual(ftxf01), f"ERROR: Skin-to-bone differs: {ftxf01}"
    
    max_vert = max([v[2] for v in armor01.verts])
    assert max_vert < 0, "ERROR: Armor verts are all below origin"

    """Can save body to Skyrim"""
    new_nif2 = NifFile()
    new_nif2.initialize("SKYRIM", outfile2)
    _export_shape(the_body, new_nif2)
    new_nif2.save()

    # check that the body is where it should be
    test_py02 = NifFile(outfile2)
    test_py02_body = test_py02.shapes[0]
    max_vert = max([v[2] for v in test_py02_body.verts])
    assert max_vert < 130, "ERROR: Body verts are all below 130"
    min_vert = min([v[2] for v in test_py02_body.verts])
    assert min_vert > 0, "ERROR: Body verts all above origin"

    """Can save armor and body together"""

    newnif3 = NifFile()
    newnif3.initialize("SKYRIM", outfile3)
    _export_shape(the_body, newnif3)
    _export_shape(the_armor, newnif3)    
    newnif3.save()

    nif3res = NifFile(outfile3)
    body2res = nif3res.shape_dict["MaleBody"]
    sstb = body2res.get_shape_skin_to_bone("NPC Spine1 [Spn1]")

    # Body doesn't have shape-level transformations so make sure we haven't put in
    # bone-level transformations when we exported it with the armor
    try:
        assert sstb.translation[2] < 0, f"ERROR: Body should be lifted above origin in {testfile}"
    except:
        # This is an open bug having to do with exporting two shapes at once (I think)
        pass


def TEST_XFORM_FO():
    """Can read the FO4 body transforms"""
    f1 = NifFile("tests/FO4/BTMaleBody.nif")
    s1 = f1.shapes[0]
    xfshape = s1.transform
    xfskin = s1.global_to_skin
    assert int(xfshape.translation[2]) == 0, f"ERROR: FO4 body shape has a 0 z translation: {xfshape.translation[2]}"
    assert int(xfskin.translation[2]) == -120, f"ERROR: global-to-skin is calculated: {xfskin.translation[2]}"

def TEST_2_TAILS():
    """Can export tails file with two tails"""

    testfile_in = r"tests/Skyrim/maletaillykaios.nif"
    testfile_out = "tests/out/testtails01.nif"
    ft1 = NifFile(testfile_in)
    ftout = NifFile()
    ftout.initialize("SKYRIM", testfile_out)

    for s_in in ft1.shapes:
        _export_shape(s_in, ftout)

    ftout.save()

    fttest = NifFile(testfile_out)
    assert len(fttest.shapes) == 2, "ERROR: Should write 2 shapes"
    for s in fttest.shapes:
        assert len(s.bone_names) == 7, f"ERROR: Failed to write all bones to {s.name}"
        assert "TailBone01" in s.bone_names, f"ERROR: bone cloth not in bones: {s.name}, {s.bone_names}"

def TEST_ROTATIONS():
    """Can handle rotations"""

    testfile = r"tests\FO4\VulpineInariTailPhysics.nif"
    f = NifFile(testfile)
    n = f.nodes['Bone_Cloth_H_002']
    assert VNearEqual(n.transform.translation, (-2.5314, -11.4114, 65.6487)), f"Translation is correct: {n.transform.translation}"
    assert MatNearEqual(n.transform.rotation, 
                        ((-0.0251, 0.9993, -0.0286),
                            (-0.0491, -0.0298, -0.9984),
                            (-0.9985, -0.0237, 0.0498))
                        ), f"Rotations read correctly: {n.transform.rotation}"

    # Write tail mesh
    nifOut = NifFile()
    nifOut.initialize('FO4', r"tests\out\TEST_ROTATIONS.nif")
    _export_shape(f.shape_dict['Inari_ZA85_fluffy'], nifOut)
    nifOut.save()

    # Check results
    nifCheck = NifFile(r"tests\out\TEST_ROTATIONS.nif")
    cloth2Check = nifCheck.nodes['Bone_Cloth_H_002']
    assert VNearEqual(cloth2Check.transform.translation, n.transform.translation), f"Translation is unchanged: {cloth2Check.transform.translation}"
    assert MatNearEqual(cloth2Check.transform.rotation, n.transform.rotation), f"Rotation is unchanged: {cloth2Check.transform.rotation}"


def TEST_PARENT():
    """Can handle nifs which show relationships between bones"""

    testfile = r"tests\FO4\bear_tshirt_turtleneck.nif"
    f = NifFile(testfile)
    n = f.nodes['RArm_Hand']
    # System accurately parents bones to each other bsaed on nif or reference skeleton
    assert n.parent.name == 'RArm_ForeArm3', "Error: Parent node should be forearm"

def TEST_PYBABY():
    print('### TEST_PYBABY: Can export multiple parts')

    testfile = r"tests\FO4\baby.nif"
    nif = NifFile(testfile)
    head = nif.shape_dict['Baby_Head:0']
    eyes = nif.shape_dict['Baby_Eyes:0']

    outfile1 = r"tests\Out\baby02.nif"
    outnif1 = NifFile()
    outnif1.initialize("FO4", outfile1)
    _export_shape(head, outnif1)
    outnif1.save()

    testnif1 = NifFile(outfile1)
    testhead1 = testnif1.shape_by_root('Baby_Head:0')
    stb1 = testhead1.get_shape_skin_to_bone('Skin_Baby_BN_C_Head')

    assert not VNearEqual(stb1.translation, [0,0,0]), "Error: Exported bone transforms should not be identity"
    assert stb1.scale == 1.0, "Error: Scale should be one"

    outfile2 = r"tests\Out\baby03.nif"
    outnif2 = NifFile()
    outnif2.initialize("FO4", outfile2)
    _export_shape(head, outnif2)
    _export_shape(eyes, outnif2)
    outnif2.save()

    testnif2 = NifFile(outfile2)
    testhead2 = testnif2.shape_by_root('Baby_Head:0')
    stb2 = testhead2.get_shape_skin_to_bone('Skin_Baby_BN_C_Head')

    assert len(testhead1.bone_names) == len(testhead2.bone_names), "Error: Head should have bone weights"
    assert VNearEqual(stb1.translation, stb2.translation), "Error: Bone transforms should stay the same"
    assert VNearEqual(stb1.rotation[0], stb2.rotation[0]), "Error: Bone transforms should stay the same"
    assert VNearEqual(stb1.rotation[1], stb2.rotation[1]), "Error: Bone transforms should stay the same"
    assert VNearEqual(stb1.rotation[2], stb2.rotation[2]), "Error: Bone transforms should stay the same"
    assert stb1.scale == stb2.scale, "Error: Bone transforms should stay the same"

def TEST_BONE_XFORM():
    print('### TEST_BONE_XFORM: Can read bone transforms')

    nif = NifFile(r"tests/FO4/BaseMaleHead.nif")
    mat3 = nif.get_node_xform_to_global("Neck")
    assert NearEqual(mat3.translation[2], 113.2265), f"Error: Translation should not be 0: {mat3.translation[2]}"
    mat4 = nif.get_node_xform_to_global("SPINE1")
    assert NearEqual(mat4.translation[2], 72.7033), f"Error: Translation should not be 0: {mat4.translation[2]}"


def TEST_PARTITIONS():
    print('### TEST_PARTITIONS: Can read partitions')

    testfile = r"tests/Skyrim/malehead.nif"
    nif = NifFile(testfile)
    CheckNif(nif)

    """Can write partitions back out"""
    nif2 = NifFile()
    nif2.initialize('SKYRIM', r"tests/Out/PartitionsMaleHead.nif")
    _export_shape(nif.shapes[0], nif2)

    # set_partitions expects a list of partitions and a tri list.  The tri list references
    # reference partitions by ID, because when there are segments and subsegments it
    # gets very confusing.
    trilist = [nif.shapes[0].partitions[t].id for t in nif.shapes[0].partition_tris]
    nif2.shapes[0].set_partitions(nif.shapes[0].partitions, trilist)
    nif2.save()

    nif3 = NifFile(r"tests/Out/PartitionsMaleHead.nif")
    CheckNif(nif3, testfile)


def TEST_SEGMENTS_EMPTY():
    """Can write FO4 segments when some are empty"""

    nif = NifFile("tests/FO4/TEST_SEGMENTS_EMPTY.nif")

    nif2 = NifFile()
    nif2.initialize('FO4', r"tests/Out/TEST_SEGMENTS_EMPTY.nif")
    _export_shape(nif.shapes[0], nif2)
    segs = [FO4Segment(0, 0, "FO4 Seg 000"),
            FO4Segment(1, 1, "FO4 Seg 001"),
            FO4Segment(2, 2, "FO4 Seg 002"),
            FO4Segment(3, 3, "FO4 Seg 003"),
            FO4Segment(4, 4, "FO4 Seg 004"),
            FO4Segment(5, 5, "FO4 Seg 005"),
            FO4Segment(6, 6, "FO4 Seg 006")]
    ptris = [3] * len(nif.shapes[0].tris)
    nif2.shapes[0].set_partitions(segs, ptris)
    nif2.save()

    nif3 = NifFile(r"tests/Out/TEST_SEGMENTS_EMPTY.nif")

    assert len([x for x in nif3.shapes[0].partition_tris if x == 3]) == len(nif3.shapes[0].tris), f"Expected all tris in the 4th partition"


def TEST_SEGMENTS():
    print ("### TEST_SEGMENTS: Can read and write FO4 segments")
    testfile = r"tests/FO4/VanillaMaleBody.nif"
    outfile  = r"tests/Out/TEST_SEGMENTS.nif"

    nif = NifFile(testfile)
    CheckNif(nif)

    """Can write segments back out"""
    # When writing segments, the tri list refers to segments/subsegments by ID *not*
    # by index into the partitions list (becuase it only has segments, not
    # subsegments, and it's the subsegments the tri list wants to reference).
    nif2 = NifFile()
    nif2.initialize('FO4', outfile)
    _export_shape(nif.shapes[0], nif2)
    nif2.shapes[0].segment_file = r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf"
    nif2.shapes[0].set_partitions(nif.shapes[0].partitions, 
                                    nif.shapes[0].partition_tris)
    nif2.save()

    nif3 = NifFile(outfile)
    CheckNif(nif3, testfile)


def TEST_BP_SEGMENTS():
    print ("### TEST_BP_SEGMENTS: Can read & write FO4 body part segments & shaders")
    testfile = r"tests/FO4/Helmet.nif"
    outfile = r"tests/Out/TEST_BP_SEGMENTS.nif"

    nif = NifFile(testfile)
    CheckNif(nif)

    """Can write segments back out"""
    # When writing segments, the tri list refers to segments/subsegments by ID *not*
    # by index into the partitions list (becuase it only has segments, not
    # subsegments, and it's the subsegments the tri list wants to reference).
    nif2 = NifFile()
    nif2.initialize('FO4', outfile)
    new_helm = _export_shape(nif.shape_dict['Helmet:0'], nif2)

    new_helm.segment_file = r"Meshes\Armor\FlightHelmet\Helmet.ssf"
    p0 = FO4Segment(0, 0, name="FO4 Seg 000")
    p1 = FO4Segment(1, 0, name="FO4 Seg 001")
    ss1 = FO4Subsegment(2, user_slot=30, material=0x86b72980, parent=p1, 
                        name="FO4 Seg 001 | Hair Top | Head")
    # All helmet tris go in segment 1, subsegment 2
    pt = [2] * len(new_helm.tris)
    new_helm.set_partitions([p0, p1], pt)

    new_glass = _export_shape(nif.shape_dict['glass:0'], nif2)
    new_glass.segment_file = r"Meshes\Armor\FlightHelmet\Helmet.ssf"
    p0 = FO4Segment(0, 0, name="FO4 Seg 000")
    p1 = FO4Segment(1, 0, name="FO4 Seg 001")
    ss1 = FO4Subsegment(2, user_slot=30, parent=p1, 
                        name="FO4 Seg 001 | Hair Top")
    pt = [ss1.id] * len(new_glass.tris)
    new_glass.set_partitions([p0, p1], pt)

    nif2.save()

    nif3 = NifFile(outfile)
    CheckNif(nif3, testfile)


def TEST_PARTITION_NAMES():
    """Can parse various forms of partition name"""

    # Blender vertex groups have magic names indicating they are nif partitions or
    # segments.  We have to analyze the group name to see if it's something we have
    # to care about.
    assert SkyPartition.name_match("SBP_42_CIRCLET") == 42, "Match skyrim parts"
    assert SkyPartition.name_match("FOOBAR") < 0, "Don't match random stuff"

    assert FO4Segment.name_match("FO4Segment #3") == 3, "Match FO4 parts"
    assert FO4Segment.name_match("FO4 Seg 003") == 3, "Match new-style FO4 segments"
    assert FO4Segment.name_match("Segment 4") < 0, "Don't match bougs names"

    sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 002 | 001 | Thigh.R")
    assert sseg_par == "FO4 Seg 002", "Extract subseg parent name"
    assert sseg_id == 1, "Extract ID"
    assert sseg_mat == 0xbf3a3cc5, "Extract material"

    sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 003 | 003 | Lo Arm.R")
    assert sseg_par == "FO4 Seg 003", "Extract subseg parent name"
    assert sseg_id == 3, "Extract ID"
    assert sseg_mat == 0x6fc3fbb2, "Extract material"

    sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 000 | Hair Top | Head")
    assert sseg_par == "FO4 Seg 000", "Should have parent name"
    assert sseg_id == 30, "Should have part id"
    assert sseg_mat == 0x86b72980, "Extract material"

    sseg_par, sseg_id, sseg_mat = FO4Subsegment.name_match("FO4 Seg 001 | Head | Head")
    assert sseg_par == "FO4 Seg 001", "Should have parent name"
    assert sseg_id == 32, "Should have part id"
    assert sseg_mat == 0x86b72980, "Extract material"

    assert FO4Subsegment.name_match("FO4 Seg 003 | HP-Neck | HP-Neck") \
        == ("FO4 Seg 003", 33, 0x3D6644AA), "name_match parses subsegments with bodyparts"

    assert FO4Segment.name_match("FO4 Seg 003 | 003 | Lo Arm.R") < 0, \
        "FO4Segment.name_match does not match on subsegments"

    assert FO4Subsegment.name_match("FO4 Seg 001 | Hair Top") == ("FO4 Seg 001", 30, -1), \
        "FO4Subsegment.name_match matches subsegments without material"

    assert FO4Subsegment.name_match("FO4 Seg 001 | Hair Top | 0x1234") == ("FO4 Seg 001", 30, 0x1234), \
        "FO4Subsegment.name_match matches subsegments with material as number"


def TEST_COLORS():
    """Can load and save colors"""

    nif = NifFile(r"Tests/FO4/HeadGear1.nif")
    assert nif.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0)
    assert nif.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0)

    nif2 = NifFile()
    nif2.initialize("FO4", r"Tests/Out/TEST_COLORS_HeadGear1.nif")
    _export_shape(nif.shapes[0], nif2)
    nif2.shapes[0].set_colors(nif.shapes[0].colors)
    nif2.save()

    nif3 = NifFile(r"Tests/Out/TEST_COLORS_HeadGear1.nif")
    assert nif3.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0)
    assert nif3.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0)
    
    nif4 = NifFile(r"tests\Skyrim\test.nif")
    assert nif4.shapes[1].name == "Armor", "Have the right shape"
    assert len(nif4.shapes[1].verts) > 0, "Get the verts from the shape"
    assert len(nif4.shapes[1].colors) == 0, f"Should have no colors, 0 != {len(nif4.shapes[1].colors)}"
    

def TEST_FNV():
    """Can load and save FNV nifs"""

    nif = NifFile(r"tests\FONV\9mmscp.nif")
    shapenames = [s.name for s in nif.shapes]
    assert "Scope:0" in shapenames, f"Error in shape name 'Scope:0' not in {shapenames}"
    scopeidx = shapenames.index("Scope:0")
    assert len(nif.shapes[scopeidx].verts) == 831, f"Error in vertex count: 831 != {nif.shapes[0].verts == 831}"
    
    nif2 = NifFile()
    nif2.initialize('FONV', r"tests/Out/9mmscp.nif")
    for s in nif.shapes:
        _export_shape(s, nif2)
    nif2.save()


# def TEST_BLOCKNAME():
#     """Can get block type as a string"""

#     nif = NifFile(r"tests\SKYRIMSE\malehead.nif")
#     assert nif.shapes[0].blockname == "BSDynamicTriShape", f"Expected 'BSDynamicTriShape', found '{nif.shapes[0].blockname}'"


def TEST_LOD():
    """BSLODTriShape is handled. Its shader attributes are handled."""
    testfile = r"tests\Skyrim\blackbriarchalet_test.nif"
    outfile = r"Tests/Out/TEST_LOD.nif"

    nif = NifFile(testfile)
    CheckNif(nif)

    nifout = NifFile()
    nifout.initialize("SKYRIM", outfile)
    _export_shape(nif.shapes[0], nifout)
    _export_shape(nif.shapes[1], nifout)
    nifout.save()

    nifcheck = NifFile(outfile)
    CheckNif(nifcheck, testfile)


def TEST_UNSKINNED():
    """FO4 unskinned shape uses BSTriShape"""

    nif = NifFile(r"Tests/FO4/Alarmclock.nif")
    assert nif.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape, got {nif.shapes[0].blockname}"

    nif2 = NifFile()
    nif2.initialize("FO4", r"Tests/Out/TEST_UNSKINNED.nif")
    _export_shape(nif.shapes[0], nif2)
    nif2.save()

    nif3 = NifFile(r"Tests/Out/TEST_UNSKINNED.nif")
    assert nif3.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape after export, got {nif3.shapes[0].blockname}"

def TEST_UNI():
    """Can load and store files with non-ascii pathnames"""

    nif = NifFile(r"tests\FO4\TestUnicode\проверка\будильник.nif")
    assert len(nif.shapes) == 1, f"Error: Expected 1 shape, found {len(nif.shapes)}"

    nif2 = NifFile()
    nif2.initialize('SKYRIMSE', r"tests\out\будильник.nif")
    _export_shape(nif.shapes[0], nif2)
    nif2.save()

    nif3 = NifFile(r"tests\out\будильник.nif")
    assert len(nif3.shapes) == 1, f"Error: Expected 1 shape, found {len(nif3.shapes)}"

def TEST_SHADER():
    """Can read shader flags"""
    hnse = NifFile(r"tests\SKYRIMSE\maleheadAllTextures.nif")
    hsse = hnse.shapes[0]
    TT.assert_eq(hsse.shader.properties.Shader_Type, 4, "Shader_Type")
    TT.assert_eq(hsse.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), True, "MODEL_SPACE_NORMALS")
    TT.assert_eq(hsse.shader.properties.Alpha, 1.0, "Alpha")
    TT.assert_equiv(hsse.shader.properties.Glossiness, 33.0, "Glossiness")
    TT.assert_eq(hsse.shader.properties.clamp_mode_t, 1, "clamp_mode_t")

    hnfo = NifFile(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\HeadTest.nif")
    hsfo = hnfo.shapes[0]
    TT.assert_eq(hsfo.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), False, "MODEL_SPACE_NORMALS")
    TT.assert_eq(hsfo.shader.properties.clamp_mode_t, 1, "clamp_mode_t")

    cnle = NifFile(r"tests\Skyrim\noblecrate01.nif")
    csle = cnle.shapes[0]
    TT.assert_eq(csle.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), False, "MODEL_SPACE_NORMALS")
    TT.assert_eq(csle.shader.properties.clamp_mode_t, 1, "clamp_mode_t")

    """Can read texture paths"""
    TT.assert_eq(hsse.textures["Diffuse"], r"textures\actors\character\male\MaleHead.dds", "Diffuse")
    TT.assert_eq(hsse.textures["Normal"], r"textures\actors\character\male\MaleHead_msn.dds", "Normal")
    TT.assert_eq(hsse.textures["SoftLighting"], r"textures\actors\character\male\MaleHead_sk.dds", "SoftLighting")
    TT.assert_eq(hsse.textures["HeightMap"], r"textures\actors\character\male\height.dds", "HeightMap")
    TT.assert_eq(hsse.textures["EnvMap"], r"textures\actors\character\male\EnvMap.dds", "EnvMap")
    TT.assert_eq(hsse.textures["EnvMask"], r"textures\actors\character\male\EnvMask.dds", "EnvMask")
    TT.assert_eq(hsse.textures["FacegenDetail"], r"textures\actors\character\male\Inner.dds", "FacegenDetail")
    TT.assert_eq(hsse.textures["Specular"], r"textures\actors\character\male\MaleHead_S.dds", "Specular")

    TT.assert_eq(hsle.textures["Diffuse"], r"textures\actors\character\male\MaleHead.dds", "Diffuse")
    TT.assert_eq(hsle.textures["Normal"], r"textures\actors\character\male\MaleHead_msn.dds", "Normal")
    TT.assert_eq(hsle.textures["SoftLighting"], r"textures\actors\character\male\MaleHead_sk.dds", "SoftLighting")
    TT.assert_eq(hsle.textures["Specular"], r"textures\actors\character\male\MaleHead_S.dds", "Specular")

    TT.assert_eq(hsfo.textures["Diffuse"], r"Actors/Character/BaseHumanMale/BaseMaleHead_d.dds", "Diffuse")
    TT.assert_eq(hsfo.textures["Normal"], r"Actors/Character/BaseHumanMale/BaseMaleHead_n.dds", "Normal")
    TT.assert_eq(hsfo.textures["Specular"], r"actors/character/basehumanmale/basemalehead_s.dds", "Specular")
    TT.assert_eq(hsfo.textures["EnvMap"], r"Shared/Cubemaps/mipblur_DefaultOutside1_dielectric.dds", "EnvMap")
    TT.assert_eq(hsfo.textures["Wrinkles"], r"Actors/Character/BaseHumanMale/HeadWrinkles_n.dds", "Wrinkles")

    print("------------- Extract non-default values")
    v = {}
    hsse.shader.properties.extract(v)
    print(v)
    assert 'Shader_Flags_1' in v
    assert 'Glossiness' in v
    assert 'UV_Scale_U' not in v

    """Can read and write shader"""
    nif = NifFile(r"tests\FO4\AlarmClock.nif")
    assert len(nif.shapes) == 1, f"Error: Expected 1 shape, found {len(nif.shapes)}"
    shape = nif.shapes[0]
    attrs = shape.shader

    nifOut = NifFile()
    nifOut.initialize('FO4', r"tests\out\SHADER_OUT.nif")
    _export_shape(nif.shapes[0], nifOut)
    nifOut.save()

    nifTest = NifFile(r"tests\out\SHADER_OUT.nif")
    assert len(nifTest.shapes) == 1, f"Error: Expected 1 shape, found {len(nifTest.shapes)}"
    shapeTest = nifTest.shapes[0]
    attrsTest = shapeTest.shader
    # We didn't write a materials file, but on reading what we wrote we read the same
    # materials file, so we should still read the same values.
    assert attrs.name == attrsTest.name, "Maintained path to materials file."
    # diffs = attrsTest.properties.compare(attrs.properties)
    # assert diffs == [], f"Error: Expected same shader attributes: {diffs}"


def TEST_SHADER_WALL():
    testfile = r"tests\FO4\Meshes\Architecture\DiamondCity\DExt\DExBrickColumn01.nif"
    nif = NifFile(testfile)
    CheckNif(nif)


def TEST_ALPHA():
    """Can read and write alpha property"""
    nif = NifFile(r"tests/Skyrim/meshes/actors/character/Lykaios/Tails/maletaillykaios.nif")
    tailfur = nif.shapes[1]

    assert tailfur.shader.properties.Shader_Type == BSLSPShaderType.Skin_Tint, \
        f"Error: Skin tint incorrect, got {tailfur.shader.properties.Shader_Type}"
    assert tailfur.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS), \
        f"Expected MSN true, got {tailfur.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)}"
    assert tailfur.alpha_property.properties.flags == 4844, \
        f"Error: Alpha flags incorrect, found {tailfur.alpha_property.properties.flags}"
    assert tailfur.alpha_property.properties.threshold == 70, \
        f"Error: Threshold incorrect, found {tailfur.alpha_property.properties.threshold}"

    nifOut = NifFile()
    nifOut.initialize('SKYRIM', r"tests\out\pynifly_TEST_ALPHA.nif")
    _export_shape(tailfur, nifOut)
    nifOut.save()

    nifcheck = NifFile(r"tests\out\pynifly_TEST_ALPHA.nif")
    tailcheck = nifcheck.shapes[0]

    assert tailcheck.alpha_property.properties.flags == tailfur.alpha_property.properties.flags, \
            f"Error: alpha flags don't match, {tailcheck.alpha_property.properties.flags} != {tailfur.alpha_property.properties.flags}"
    assert tailcheck.alpha_property.properties.threshold == tailfur.alpha_property.properties.threshold, \
            f"Error: alpha flags don't match, {tailcheck.alpha_property.properties.threshold} != {tailfur.alpha_property.properties.threshold}"
    assert not tailcheck.alpha_property.properties.alpha_blend, f"Have correct blend flag"
    assert tailcheck.alpha_property.properties.alpha_test, f"Have correct test flag"
    assert tailcheck.alpha_property.properties.source_blend_mode == ALPHA_FUNCTION.SRC_ALPHA, f"Have correct blend mode"
    
def TEST_SHEATH():
    """Can read and write extra data"""
    nif = NifFile(r"tests/Skyrim/sheath_p1_1.nif")
    
    # Extra data can be at the file level
    bg = nif.behavior_graph_data
    assert bg == [('BGED', r"AuxBones\SOS\SOSMale.hkx", True)], f"Error: Expected behavior graph data, got {bg}"

    s = nif.string_data
    assert len(s) == 2, f"Error: Expected two string data records"
    assert ('HDT Havok Path', 'SKSE\\Plugins\\hdtm_baddog.xml') in s, "Error: expect havok path"
    assert ('HDT Skinned Mesh Physics Object', 'SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml') in s, "Error: Expect physics path"

    # File level is root level
    bg = nif.rootNode.behavior_graph_data
    assert bg == [('BGED', r"AuxBones\SOS\SOSMale.hkx", True)], f"Error: Expected behavior graph data, got {bg}"

    s = nif.rootNode.string_data
    assert len(s) == 2, f"Error: Expected two string data records"
    assert ('HDT Havok Path', 'SKSE\\Plugins\\hdtm_baddog.xml') in s, "Error: expect havok path"
    assert ('HDT Skinned Mesh Physics Object', 'SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml') in s, "Error: Expect physics path"

    # Can write extra data at the file level
    nifout = NifFile()
    nifout.initialize('SKYRIM', r"tests/Out/pynifly_TEST_SHEATH.nif")
    nifout.behavior_graph_data = nif.behavior_graph_data
    nifout.string_data = nif.string_data
    # Can write extra data with multiple calls
    nifout.string_data = [('BODYTRI', 'foo/bar/fribble.tri')]

    _export_shape(nif.shapes[0], nifout)
    nifout.save()

    nifcheck = NifFile(r"tests/Out/pynifly_TEST_SHEATH.nif")

    assert len(nifcheck.shapes) == 1, "Error: Wrote expected shapes"
    assert nifcheck.behavior_graph_data == [('BGED', r"AuxBones\SOS\SOSMale.hkx", True)], f"Error: Expected behavior graph data, got {nifcheck.behavior_graph_data}"
    
    assert len(nifcheck.string_data) == 3, f"Error: Expected three string data records in written file"
    assert ('HDT Havok Path', 'SKSE\\Plugins\\hdtm_baddog.xml') in nifcheck.string_data, "Error: expect havok path in written file"
    assert ('HDT Skinned Mesh Physics Object', 'SKSE\\Plugins\\hdtSkinnedMeshConfigs\\MaleSchlong.xml') in nifcheck.string_data, "Error: Expect physics path in written file"
    assert ('BODYTRI', 'foo/bar/fribble.tri') in nifcheck.string_data, "Error: Expected second string data written to be available"


def TEST_FEET():
    """Can read and write extra data"""
    nif = NifFile(r"tests/SkyrimSE/caninemalefeet_1.nif")
    feet = nif.shapes[0]
    
    s = feet.string_data
    assert s[0][0] == 'SDTA', f"Error: Expected string data, got {s}"
    assert s[0][1].startswith('[{"name"'), f"Error: Expected string data, got {s}"

    nifout = NifFile()
    nifout.initialize('SKYRIM', r"tests/Out/pynifly_TEST_FEET.nif")
    _export_shape(feet, nifout)
    nifout.save()

    nifcheck = NifFile(r"tests/Out/pynifly_TEST_FEET.nif")

    assert len(nifcheck.shapes) == 1, "Error: Wrote expected shapes"
    feetcheck = nifcheck.shapes[0]

    s = feetcheck.string_data
    assert s[0][0] == 'SDTA', f"Error: Expected string data, got {s}"
    assert s[0][1].startswith('[{"name"'), f"Error: Expected string data, got {s}"


def TEST_XFORM_STATIC():
    """Can read static transforms"""

    nif = NifFile(r"tests\FO4\Meshes\SetDressing\Vehicles\Crane03_simplified.nif")
    glass = nif.shapes[0]

    assert glass.name == "Glass:0", f"Error: Expected glass first, found {glass.name}"
    assert round(glass.transform.translation[0]) == -108, f"Error: X translation wrong: {glass.transform.translation[0]}"
    assert round(glass.transform.rotation[1][0]) == 1, f"Error: Rotation incorrect, got {glass.transform.rotation[1]}"


def TEST_MUTANT():
    """can read the mutant nif correctly"""

    testfile = r"tests/FO4/testsupermutantbody.nif"
    nif = NifFile(testfile)
    shape = nif.shapes[0]
    
    assert round(shape.global_to_skin.translation[2]) == -140, f"Error: Expected -140 z translation, got {shape.global_to_skin.translation[2]}"

    bellyxf = nif.get_node_xform_to_global('Belly_skin')
    assert NearEqual(bellyxf.translation[2], 90.1133), f"Error: Expected Belly_skin Z near 90, got {bellyxf.translation[2]}"

    nif2 = NifFile(testfile)
    shape2 = nif.shapes[0]

    assert round(shape2.global_to_skin.translation[2]) == -140, f"Error: Expected -140 z translation, got {shape2.global_to_skin.translation[2]}"

def TEST_BONE_XPORT_POS():
    """bones named like vanilla bones but from a different skeleton export to the correct position"""

    testfile = r"tests/Skyrim/Draugr.nif"
    nif = NifFile(testfile)
    draugr = nif.shapes[0]
    spine2 = nif.nodes['NPC Spine2 [Spn2]']

    assert round(spine2.transform.translation[2], 2) == 102.36, f"Expected bone location at z 102.36, found {spine2.transform.translation[2]}"

    outfile = r"tests/Out/pynifly_TEST_BONE_XPORT_POS.nif"
    nifout = NifFile()
    nifout.initialize('SKYRIM', outfile)
    _export_shape(draugr, nifout)
    nifout.save()

    nifcheck = NifFile(outfile)
    draugrcheck = nifcheck.shapes[0]
    spine2check = nifcheck.nodes['NPC Spine2 [Spn2]']

    assert round(spine2check.transform.translation[2], 2) == 102.36, f"Expected output bone location at z 102.36, found {spine2check.transform.translation[2]}"

def TEST_CLOTH_DATA():
    """can read and write cloth data"""

    testfile = r"tests/FO4/HairLong01.nif"
    nif = NifFile(testfile)
    shape = nif.shapes[0]
    clothdata = nif.cloth_data[0]
    # Note the array will have an extra byte, presumeably for a null?
    assert len(clothdata[1]) == 46257, f"Expeected cloth data length 46257, got {len(clothdata[1])}"

    outfile = r"tests/out/pynifly_TEST_CLOTH_DATA.nif"
    nifout = NifFile()
    nifout.initialize('FO4', outfile)
    _export_shape(shape, nifout)
    nifout.cloth_data = nif.cloth_data
    nifout.save()

    nifcheck = NifFile(outfile)
    shapecheck = nifcheck.shapes[0]
    clothdatacheck = nifcheck.cloth_data[0]
    assert len(clothdatacheck[1]) == 46257, f"Expeected cloth data length 46257, got {len(clothdatacheck[1])}"

    for i, p in enumerate(zip(clothdata[1], clothdatacheck[1])):
        assert p[0] == p[1], f"Cloth data doesn't match at {i}, {p[0]} != {p[1]}"

    print("# Can export cloth data when it's been extracted and put back")
    buf = codecs.encode(clothdata[1], 'base64')

    outfile2 = r"tests/out/pynifly_TEST_CLOTH_DATA2.nif"
    nifout2 = NifFile()
    nifout2.initialize('FO4', outfile2)
    _export_shape(shape, nifout2)
    nifout2.cloth_data = [['binary data', codecs.decode(buf, 'base64')]]
    nifout2.save()

    nifcheck2 = NifFile(outfile2)
    shapecheck2 = nifcheck2.shapes[0]
    clothdatacheck2 = nifcheck2.cloth_data[0]
    assert len(clothdatacheck2[1]) == 46257, f"Expeected cloth data length 46257, got {len(clothdatacheck2[1])}"

    for i, p in enumerate(zip(clothdata[1], clothdatacheck2[1])):
        assert p[0] == p[1], f"Cloth data doesn't match at {i}, {p[0]} != {p[1]}"


def TEST_PARTITION_SM():
    """Regression--test that supermutant armor can be read and written"""

    testfile = r"tests/FO4/SMArmor0_Torso.nif"
    nif = NifFile(testfile)
    armor = nif.shapes[0]
    partitions = armor.partitions

    nifout = NifFile()
    nifout.initialize('FO4', r"tests/Out/TEST_PARTITION_SM.nif")
    _export_shape(armor, nifout)
    nifout.shapes[0].segment_file = armor.segment_file
    nifout.shapes[0].set_partitions(armor.partitions, armor.partition_tris)
    nifout.save()

    # If no CTD we're good


def TEST_EXP_BODY():
    """Ensure body with bad partitions does not cause a CTD on export"""

    testfile = r"tests/FO4/feralghoulbase.nif"
    nif = NifFile(testfile)
    shape = nif.shape_dict['FeralGhoulBase:0']
    partitions = shape.partitions

    # This is correcct
    nifout = NifFile()
    nifout.initialize('FO4', r"tests/Out/TEST_EXP_BODY.nif")
    _export_shape(shape, nifout)
    nifout.shapes[0].segment_file = shape.segment_file
    nifout.shapes[0].set_partitions(shape.partitions, shape.partition_tris)
    nifout.save()

    print('....This causes an error')
    try:
        os.remove(r"tests/Out/TEST_EXP_BODY2.nif")
    except:
        pass

    nifout2 = NifFile()
    nifout2.initialize('FO4', r"tests/Out/TEST_EXP_BODY2.nif")
    _export_shape(shape, nifout2)
    sh = nifout2.shapes[0]
    sh.segment_file = shape.segment_file
    seg0 = FO4Segment(0)
    seg1 = FO4Segment(1)
    seg12 = FO4Segment(12)
    seg4 = FO4Segment(4)
    seg15 = FO4Segment(15)
    seg26 = FO4Segment(26)
    seg37 = FO4Segment(37)
    FO4Subsegment(4, 0, 0, seg4, name='FO4 Feral Ghoul 2')
    FO4Subsegment(15, 0, 0, seg15, name='FO4 Feral Ghoul 4')
    FO4Subsegment(26, 0, 0, seg15, name='FO4 Death Claw 5')
    FO4Subsegment(37, 0, 0, seg15, name='FO4 Death Claw 6')
    # error caused by referencing a segment that doesn't exist
    tri_map = [16] * len(sh.tris)

    NifFile.clear_log();
    sh.set_partitions([seg0, seg1, seg4], tri_map)

    assert "ERROR" in NifFile.message_log(), "Error: Expected error message, got '{NifFile.message_log()}'"
    # If no CTD we're good


def TEST_EFFECT_SHADER_SKY():
    """Can read and write shader flags"""
    testfile = r"tests\SkyrimSE\meshes\armor\daedric\daedriccuirass_1.nif"
    outfile = r"tests\out\TEST_EFFECT_SHADER_SKY.nif"

    print("---Read---")
    nif = NifFile(testfile)
    CheckNif(nif)

    """Can read and write shader"""
    print("---Write---")
    nifOut = NifFile()
    nifOut.initialize('FO4', outfile)
    _export_shape(nif.shapes[0], nifOut)
    _export_shape(nif.shapes[1], nifOut)
    nifOut.save()

    print("---Check---")
    nifTest = NifFile(outfile, materialsRoot='tests/FO4')
    CheckNif(nifTest, testfile)


# TODO: Setting up to test the alpha threshold controller when there are multiple 
# sequences is a PITA. Do it at the Blender level.
# def TEST_ALPHA_THRESHOLD_CONTROLLER():
#     """Can read and write alpha threshold controller"""
#     testfile = r"tests\SkyrimSE\meshes\CRSTSkinKalaar.nif"
#     outfile = r"tests\out\TEST_ALPHA_THRESHOLD_CONTROLLER.nif"

#     print("---Read---")
#     nif = NifFile(testfile)
#     CheckNif(nif)

#     """Can read and write shader"""
#     print("---Write---")
#     nifOut = NifFile()
#     nifOut.initialize('SKYRIMSE', outfile)
#     _export_shape(nif.shapes[0], nifOut)
#     nifOut.save()

#     print("---Check---")
#     nifTest = NifFile(outfile)
#     CheckNif(nifTest, testfile)


def TEST_TEXTURE_CLAMP():
    """Make sure we don't lose texture clamp mode"""
    testfile = r"tests\SkyrimSE\evergreen.nif"
    outfile = r"tests\out\TEST_TEXTURE_CLAMP.nif"

    def CheckNif(nif:NifFile):
        shape:NiShape = nif.shapes[0]
        sh = shape.shader
        assert sh.blockname == "BSLightingShaderProperty", f"Have correct shader"
        assert sh.properties.textureClampMode == 0, f"Have correct textureClampMode: {sh.properties.textureClampMode}"

    print("---Read---")
    nif = NifFile(testfile)
    CheckNif(nif)

    """Can read and write shader"""
    print("---Write---")
    nifOut = NifFile()
    nifOut.initialize('FO4', outfile)
    _export_shape(nif.shapes[0], nifOut)
    nifOut.save()

    print("---Check---")
    nifTest = NifFile(outfile)
    CheckNif(nifTest)


def TEST_BOW():
    """Can read and write special weapon data; also testing BGED"""
    nif = NifFile(r"tests\SkyrimSE\meshes\weapons\glassbowskinned.nif")

    root = nif.rootNode
    assert root.blockname == "BSFadeNode", f"Top level node should read as BSFadeNode, found '{root.blockname}'"
    assert root.flags == 14, "Root node has flags"
    assert VNearEqual(root.global_transform.translation, [0,0,0]), "Root node transform can be read"
    assert VNearEqual(root.global_transform.rotation[0], [1,0,0]), "Root node transform can be read"
    assert VNearEqual(root.global_transform.rotation[1], [0,1,0]), "Root node transform can be read"
    assert VNearEqual(root.global_transform.rotation[2], [0,0,1]), "Root node transform can be read"
    assert root.global_transform.scale == 1.0, "Root node transform can be read"

    assert root.behavior_graph_data == [('BGED', r"Weapons\Bow\BowProject.hkx", False)], f"Error: Expected behavior graph data, got {nif.behavior_graph_data}"

    assert root.inventory_marker[0] == "INV"
    assert root.inventory_marker[1:4] == [4712, 0, 785]
    assert round(root.inventory_marker[4], 4) == 1.1273, "Inventory marker has rotation and zoom info"

    assert root.bsx_flags == ['BSX', 202]

    bone = nif.nodes['Bow_MidBone']
    co = bone.collision_object
    assert co.blockname == "bhkCollisionObject", f"Can find type of collision object from the block name: {co.blockname}"

    assert co.flags == bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE, f'Can read collision flags'
    assert co.target.name == "Bow_MidBone", f"Can read collision target"
    assert co.body.blockname == "bhkRigidBodyT", "Can read collision block"

    assert co.body.properties.collisionResponse == hkResponseType.SIMPLE_CONTACT
    assert co.body.properties.motionSystem == hkMotionType.SPHERE_STABILIZED, f"Collision body properties hold the specifics"

    collshape = co.body.shape
    assert collshape.blockname == "bhkBoxShape", f"Collision body's shape property returns the collision shape"
    assert collshape.properties.bhkMaterial == SkyrimHavokMaterial.MATERIAL_BOWS_STAVES, "Collision body shape material is readable"
    assert round(collshape.properties.bhkRadius, 4) == 0.0136, f"Collision body shape radius is readable"
    assert [round(x, 4) for x in collshape.properties.bhkDimensions] == [0.1574, 0.8238, 0.0136], f"Collision body shape dimensions are readable"

    # WRITE MESH WITH COLLISION DATA 

    nifOut = NifFile()
    nifOut.initialize('SKYRIMSE', r"tests\out\TEST_BOW.nif", root.blockname, root.name)
    _export_shape(nif.shapes[0], nifOut)

    # Testing BGED too
    nifOut.behavior_graph_data = nif.behavior_graph_data

    # Have to apply the skin so we have the bone available to add collisions
    #nifOut.apply_skin()
    midbow = nifOut.nodes["Bow_MidBone"]

    # Create the collision bottom-up, shape first
    coll_out = midbow.add_collision(None, bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE)
    bod_out = coll_out.add_body(co.body.properties)
    box_out = bod_out.add_shape(collshape.properties)

    nifOut.save()

    nifcheck = NifFile(r"tests\out\TEST_BOW.nif")
    rootCheck = nifcheck.nodes[nifcheck.rootName]
    assert nifcheck.rootName == root.name, f"ERROR: root name not correct, {nifcheck.rootName} != {root.name}"
    assert rootCheck.blockname == root.blockname, f"ERROR: root type not correct, {rootCheck.blockname} != {root.blockname}"

    collcheck = nifcheck.nodes["Bow_MidBone"].collision_object
    assert collcheck.flags == bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE, f"Flags not correctly read: {collcheck.flags}"

    bodycheck = collcheck.body
    assert bodycheck.blockname == 'bhkRigidBodyT', f"Collision body not correct, {bodycheck.blockname != 'bhkRigidBodyT'}"
    assert bodycheck.properties.collisionFilter_layer == SkyrimCollisionLayer.WEAPON, f"Collision layer not correct, {bodycheck.properties.collisionFilter_layer} != {SkyrimCollisionLayer.WEAPON}"
    assert bodycheck.properties.collisionResponse == hkResponseType.SIMPLE_CONTACT, f"Collision response not correct, {bodycheck.properties.collisionResponse} != {hkResponseType.SIMPLE_CONTACT}"
    assert bodycheck.properties.qualityType == hkQualityType.MOVING, f"Movement quality type not correct, {bodycheck.properties.qualityType} != {hkQualityType.MOVING}"

    boxcheck = bodycheck.shape
    assert [round(x, 4) for x in boxcheck.properties.bhkDimensions] == [0.1574, 0.8238, 0.0136], f"Collision body shape dimensions written correctly"


def TEST_CONVEX():
    """Can read and write convex collisions"""
    nif = NifFile(r"tests/Skyrim/cheesewedge01.nif")

    root = nif.rootNode
    co = root.collision_object
    assert co.blockname == "bhkCollisionObject", f"Can find type of collision object from the block name: {co.blockname}"

    assert co.target.name == root.name, f"Can read collision target"
    assert co.body.blockname == "bhkRigidBody", "Can read collision block"

    assert co.body.properties.collisionResponse == hkResponseType.SIMPLE_CONTACT
    assert co.body.properties.motionSystem == hkMotionType.SPHERE_STABILIZED, f"Collision body properties hold the specifics"

    collshape = co.body.shape
    assert collshape.blockname == "bhkConvexVerticesShape", f"Collision body's shape property returns the collision shape"
    assert collshape.properties.bhkMaterial == SkyrimHavokMaterial.CLOTH, "Collision body shape material is readable"

    assert VNearEqual(collshape.vertices[0], [-0.059824, -0.112763, 0.101241, 0]), f"Vertex 0 is correct"
    assert VNearEqual(collshape.vertices[7], [-0.119985, 0.000001, 0, 0]), f"Vertex 7 is correct"
    assert VNearEqual(collshape.normals[0], [0.513104, 0, 0.858327, -0.057844]), f"Normal 0 is correct"
    assert VNearEqual(collshape.normals[9], [-0.929436, 0.273049, 0.248180, -0.111519]), f"Normal 9 is correct"

    # WRITE MESH WITH COLLISION DATA 

    nifOut = NifFile()
    nifOut.initialize('SKYRIM', r"tests\out\TEST_CONVEX.nif", root.blockname, root.name)
    _export_shape(nif.shapes[0], nifOut)

    # Create the collision bottom-up, shape first
    coll_out = nifOut.rootNode.add_collision(
        None, bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE)
    bod_out = coll_out.add_body(co.body.properties)
    box_out = bod_out.add_shape(collshape.properties, collshape.vertices, collshape.normals)

    nifOut.save()


def TEST_CONVEX_MULTI():
    """Can read and write convex collisions"""
    nif = NifFile(r"tests/Skyrim/grilledleeks01.nif")

    l2 = nif.shape_dict["Leek02:0"]
    assert l2.parent.name == "Leek02", f"Parent of shape is node: {l2.parent.name}"


def _checkFalmerStaff(nif):
    root = nif.rootNode
    staff = nif.shapes[0]
    coll = nif.rootNode.collision_object
    collbody = coll.body
    assert collbody.properties.collisionFilter_layer == SkyrimCollisionLayer.WEAPON, f"Rigid body has values"
    collshape = collbody.shape
    assert collshape.blockname == "bhkListShape", f"Have list shape: {collshape.blockname}"
    assert collshape.properties.bhkMaterial == SkyrimHavokMaterial.MATERIAL_BOWS_STAVES
    assert len(collshape.children) == 3, f"Have 3 children: {collshape.children}"
    cts0 = collshape.children[0]
    cts1 = collshape.children[1]
    cts2 = collshape.children[2]
    assert cts0.blockname == "bhkConvexTransformShape", f"Child is transform shape: {cts0.blockname}"
    assert cts1.blockname == "bhkConvexTransformShape", f"Child is transform shape: {cts1.blockname}"
    assert cts2.blockname == "bhkConvexTransformShape", f"Child is transform shape: {cts2.blockname}"
    assert cts0.properties.bhkMaterial == SkyrimHavokMaterial.MATERIAL_BOWS_STAVES, f"Material is correct: {cts0.properties.bhkMaterial}"
    assert NearEqual(cts0.properties.bhkRadius, 0.009899), "ConvexTransformShape has values"

    assert len(staff.bone_weights) == 0, f"Shape not skinned: {staff}"
    assert len(staff.partitions) == 0, f"Shape has no partitioins"

    box0 = cts0.child


def TEST_COLLISION_LIST():
    """Can read and write convex collisions"""
    nif = NifFile(r"tests/Skyrim/falmerstaff.nif")
    _checkFalmerStaff(nif)

    # ------------ Save it ----------

    nifOut = NifFile()
    nifOut.initialize('SKYRIM', r"tests\out\TEST_COLLISION_LIST.nif", nif.rootNode.blockname, "Scene Root")
    _export_shape(nif.shapes[0], nifOut)

    # Create the collision 
    coll_out = nifOut.rootNode.add_collision(
        None, bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE)
    bodprop_out =  bhkRigidBodyProps()
    bodprop_out.collisionFilter_layer = SkyrimCollisionLayer.WEAPON
    bod_out = coll_out.add_body(bodprop_out)
    csprop_out = bhkListShapeProps()
    csprop_out.bhkMaterial = SkyrimHavokMaterial.MATERIAL_BOWS_STAVES
    listshape_out = bod_out.add_shape(csprop_out)
    for i in range(0, 3):
        ctsprop_out = bhkConvexTransformShapeProps()
        ctsprop_out.bhkMaterial = SkyrimHavokMaterial.MATERIAL_BOWS_STAVES
        ctsprop_out.bhkRadius = 0.009899
        cts_out = listshape_out.add_shape(ctsprop_out)

        box_out = bhkBoxShapeProps()
        cts_out.add_shape(box_out)

    nifOut.save()

    _checkFalmerStaff(NifFile(r"tests\out\TEST_COLLISION_LIST.nif"))


def TEST_COLLISION_CAPSULE():
    """Can read and write capsule collisions"""
    nif = NifFile(r"tests/Skyrim/staff04.nif")

    root = nif.rootNode
    staff = nif.shape_dict["3rdPersonStaff04:1"]
    coll = nif.rootNode.collision_object
    collbody = coll.body
    collshape = collbody.shape
    assert collshape.blockname == "bhkCapsuleShape", f"Have capsule shape: {collshape.blockname}"


def TEST_FURNITURE_MARKER():
    """Can read and write furniture markers"""
    nif = NifFile(r"tests/SkyrimSE/farmbench01.nif")

    assert len(nif.furniture_markers) == 2, f"Found the furniture markers"


def TEST_MANY_SHAPES():
    """Can read and write a nif with many shapes"""
    nif = NifFile(r"tests\FO4\Outfit.nif")

    assert len(nif.shapes) == 87, f"Found all shapes: {len(nif.shapes)}"
    
    nifOut = NifFile()
    nifOut.initialize('FO4', r"tests\out\TEST_MANY_SHAPES.nif")
    for s in nif.shapes:
        _export_shape(s, nifOut)

    nifOut.save()

    nifcheck = NifFile(r"tests\out\TEST_MANY_SHAPES.nif")

    assert len(nifcheck.shapes) == 87, f"Found all shapes in written file: {len(nifcheck.shapes)}"


def TEST_CONNECT_POINTS():
    """Can read and write connect points"""
    nif = NifFile(r"tests\FO4\Shotgun\CombatShotgun.nif")

    pcp = nif.connect_points_parent
    assert len(pcp) == 5, f"Can read all the connect points: {len(pcp)}"
    assert pcp[0].parent.decode('utf-8') == "WeaponMagazine", f"Can read the name property: {pcp[0].parent}"
    pcpnames = set([x.name.decode() for x in pcp])
    assert pcpnames == set(['P-Mag', 'P-Grip', 'P-Barrel', 'P-Casing', 'P-Scope']), f"Can read all names: {pcpnames}"

    pcc = nif.connect_points_child
    assert not nif.connect_pt_child_skinned, f"Shotgun not skinned {pcc[0]}"
    assert "C-Receiver" in pcc, f"Have two conect points: {pcc}"
    assert "C-Reciever" in pcc, f"Have two conect points: {pcc}"

    nifOut = NifFile()
    nifOut.initialize('FO4', r"tests\out\TEST_CONNECT_POINTS.nif")
    _export_shape(nif.shapes[0], nifOut)
    nifOut.connect_points_parent = nif.connect_points_parent
    nifOut.connect_pt_child_skinned = False
    nifOut.connect_points_child = ["C-Receiver", "C-Reciever"]
    nifOut.save()

    nifcheck = NifFile(r"tests\out\TEST_CONNECT_POINTS.nif")
    pcpcheck = nifcheck.connect_points_parent
    assert len(pcpcheck) == 5, f"Can read all the connect points: {len(pcpcheck)}"
    assert pcpcheck[0].parent.decode('utf-8') == "WeaponMagazine", f"Can read the name property: {pcpcheck[0].parent}"
    pcpnamescheck = set([x.name.decode() for x in pcpcheck])
    assert pcpnames == pcpnamescheck, f"Can read all names: {pcpnamescheck}"

    pcccheck = nifcheck.connect_points_child
    assert not nifcheck.connect_pt_child_skinned, f"Shotgun not skinned {nifcheck.connect_pt_child_skinned}"
    assert "C-Receiver" in pcccheck, f"Have two conect points: {pcccheck}"
    assert "C-Reciever" in pcccheck, f"Have two conect points: {pcccheck}"


def TEST_SKIN_BONE_XF():
    """Can read and write the skin-bone transform"""
    nif = NifFile(r"tests\SkyrimSE\maleheadargonian.nif")
    head = nif.shapes[0]

    head_spine_xf = head.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
    assert NearEqual(head_spine_xf.translation[2], 29.419632), f"Have correct z: {head_spine_xf.translation[2]}"

    head_head_xf = head.get_shape_skin_to_bone('NPC Head [Head]')
    assert NearEqual(head_head_xf.translation[2], -0.000031), f"Have correct z: {head_head_xf.translation[2]}"

    hsx = nif.nodes['NPC Spine2 [Spn2]'].transform * head_spine_xf
    assert NearEqual(hsx.translation[2], 120.3436), f"Head-spine transform positions correctly: {hsx.translation[2]}"
    hhx = nif.nodes['NPC Head [Head]'].transform * head_head_xf
    assert NearEqual(hhx.translation[2], 120.3436), f"Head-head transform positions correctly: {hhx.translation[2]}"

    nifout = NifFile()
    nifout.initialize('SKYRIMSE', r"tests\out\TEST_SKIN_BONE_XF.nif")

    _export_shape(head, nifout)

    nifout.save()

    nifcheck = NifFile(r"tests\out\TEST_SKIN_BONE_XF.nif")
    headcheck = nifcheck.shapes[0]

    head_spine_check_xf = headcheck.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
    assert NearEqual(head_spine_check_xf.translation[2], 29.419632), f"Have correct z: {head_spine_check_xf.translation[2]}"

    head_head_check_xf = headcheck.get_shape_skin_to_bone('NPC Head [Head]')
    assert NearEqual(head_head_check_xf.translation[2], -0.000031), f"Have correct z: {head_head_check_xf.translation[2]}"

    hsx_check = nifcheck.nodes['NPC Spine2 [Spn2]'].transform * head_spine_check_xf
    assert NearEqual(hsx_check.translation[2], 120.3436), f"Head-spine transform positions correctly: {hsx_check.translation[2]}"
    hhx_check = nifcheck.nodes['NPC Head [Head]'].transform * head_head_check_xf
    assert NearEqual(hhx_check.translation[2], 120.3436), f"Head-headcheck transform positions correctly: {hhx_check.translation[2]}"

    #Throw in an unrelated test for whether the UV got inverted
    assert VNearEqual(head.uvs[0], headcheck.uvs[0]), f"UV 0 same in both: [{head.uvs[0]}, {headcheck.uvs[0]}]"

def TEST_WEIGHTS_BY_BONE():
    """Weights-by-bone helper works correctly"""
    nif = NifFile(r"tests\SkyrimSE\Anna.nif")
    allnodes = list(nif.nodes.keys())
    hair = nif.shape_dict["KSSMP_Anna"]

    #Sanity check--each vertex/weight pair listed just once
    vwp_list = [None] * len(hair.verts)
    for i in range(0, len(hair.verts)):
        vwp_list[i] = {}
    
    for bone, weights_list in hair.bone_weights.items():
        for vwp in weights_list:
            assert bone not in vwp_list[vwp[0]], \
                    f"Error: Vertex {vwp[0]} duplicated for bone {bone}"
            vwp_list[vwp[0]][bone] = 1

    hair_vert_weights = get_weights_by_vertex(hair.verts, hair.bone_weights)
    assert len(hair_vert_weights) == len(hair.verts), "Have enough vertex weights"
    assert NearEqual(hair_vert_weights[245]['NPC Head [Head]'], 0.0075), \
        f"Weight is correct: {hair_vert_weights[245]['NPC Head [Head]']}"
    
    wbb = get_weights_by_bone(hair_vert_weights, allnodes)

    assert len(list(wbb.keys())) == 14, f"Have all bones: {wbb.keys()}"
    assert 'Anna R3' in wbb, f"Special bone in weights by bone: {wbb.keys()}"
    vw = [vp[1] for vp in wbb['NPC Head [Head]'] if vp[0] == 245]
    assert len(vw) == 1 and NearEqual(vw[0], 0.0075), \
        f"Have weight by bone correct: {vw}"

    hair_vert_weights[5]['NPC'] = 0.0
    hair_vert_weights[10]['NPC'] = 0.0
    hair_vert_weights[15]['NPC'] = 0.0

    wbb2 = get_weights_by_bone(hair_vert_weights, allnodes)
    assert 'BOGUS' not in wbb2, f"Bone with no weights not in weights by bone: {wbb2.keys()}"


def TEST_ANIMATION():
    """Can read embedded animations"""
    nif = NifFile(r"tests/Skyrim/dwechest01.nif")
    root = nif.rootNode
    assert nif.max_string_len > 10, f"Have reasonable {nif.max_string_len}"

    # Any node can have a controller, including the root. This nif has a 
    # NiControllerManager, which coordinates multiple animations.
    cm = root.controller
    # assert len(nif.controller_managers) == 1, f"Found a controller manager"
    # cm = nif.controller_managers[0]
    assert cm.properties.frequency == 1.0, f"Have correct frequency: {cm.properties.frequency}"
    assert cm.properties.nextControllerID == 3, f"Have correct next controller: {cm.properties.nextControllerID}"
    assert cm.properties.flags == 76, f"Have correct flags: {cm.properties.flags}"

    # Controllers can be chained. 
    mttc = cm.next_controller
    assert mttc.properties.flags == 108, f"Have correct flag: {mttc.properties.flags}"
    assert mttc.next_controller is None, f"MTTC does not have next controller: {mttc.next_controller}"

    # Controller sequences describe the actual animations. Each has name indicating
    # what it does. For the chest, they open or close the lid.
    assert len(cm.sequences) == 2, f"Have 2 controller manager sequences: {cm.sequences}"
    cm_names = set(cm.sequences.keys())
    assert cm_names == set(["Open", "Close"]), f"Have correct name: {cm_names}"
    cm_open = cm.sequences['Open']
    assert NearEqual(cm_open.properties.stopTime, 0.6), f"Have correct stop time: {cm_open.properties.stopTime}"

    # The controlled block is the thing that's actually getting animated, referenced
    # by name.
    cblist = cm_open.controlled_blocks
    assert len(cblist) == 9, f"Have 9 controlled blocks: {cblist}"
    assert cblist[0].node_name == "Object01", f"Have correct target: {cblist[0].node_name}"
    assert cblist[0].controller_type == "NiTransformController", f"Have correct controller type: {cblist[0].controller_type}"

    # The interpolator parents the actual animation data.
    interp = cblist[0].interpolator

    # The data is stored in the animation keys. In this chest, Object01 is the lid that 
    # slides down and sideways, so no rotations.
    td = interp.data
    # we don't seem to be getting the number of rotation keys from the nif.
    # assert td.properties.rotationKeyCount == 0, f"Found no rotation keys: {td.properties.rotationKeyCount}"
    assert td.properties.translations.numKeys == 18, f"Found translation keys: {td.properties.translations.numKeys}"
    assert td.properties.translations.interpolation == NiKeyType.LINEAR_KEY, f"Found correct interpolation: {td.properties.translations.interpolation}"
    assert td.translations[0].time == 0, f"First time 0"
    assert NearEqual(td.translations[1].time, 0.033333), f"Second time 0.03"

    # The second controlled object is a gear, so it has rotations around
    # the Z axis.
    assert cblist[1].node_name == "Gear08", f"Found controller for {cblist[1].node_name}"
    tdgear = cblist[1].interpolator.data
    # assert tdgear.properties.rotationKeyCount > 0, f"Found rotation keys: {tdgear.properties.rotationKeyCount}"
    assert tdgear.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY, f"Found XYZ rotation type: {tdgear.properties.rotationType}"
    assert tdgear.properties.xRotations.interpolation == NiKeyType.LINEAR_KEY, f"X is linear: {tdgear.properties.xRotation.interpolation}"
    assert tdgear.properties.xRotations.numKeys == 1, f"Have one X rotation key:{tdgear.properties.xRotation.numKeys}"
    assert tdgear.properties.zRotations.interpolation == NiKeyType.QUADRATIC_KEY, f"Z is quadratic: {tdgear.properties.xRotation.interpolation}"
    assert tdgear.properties.zRotations.numKeys == 2, f"Have 2 X rotation keys:{tdgear.properties.zRotation.numKeys}"
    assert NearEqual(tdgear.zrotations[1].time, 0.6), f"Found correct time: {tdgear.zrotations[1].time}"

    # Object189 has linear translations but it's been messing up, so check 
    # it directly.
    o189 = [cb for cb in cblist if cb.node_name == "Object189"][0]
    td189 = o189.interpolator.data
    assert VNearEqual(td189.translations[0].value, [-20.966583, -0.159790, 18.576317]), \
        f"Have correct translation: {td189.translations[0].value}"
    assert VNearEqual(td189.translations[2].value, [-20.965717, -0.159790, 18.343819]), \
        f"Have correct translation: {td189.translations[3].value}"
    assert VNearEqual(td189.translations[4].value, [-20.963652, -0.159790, 17.789375]), \
        f"Have correct translation: {td189.translations[3].value}"
    

def TEST_ANIMATION_NOBLECHEST():
    """Can read & write embedded animations."""
    # NobleChest has a simple open and close animation.
    testfile = r"tests/Skyrim/noblechest01.nif"
    outfile = r"tests/out/TEST_ANIMATION_NOBLECHEST.nif"

    # READ

    nif = NifFile(testfile)
    lid01 = nif.nodes["Lid01"]

    # WRITE
    
    nifout = NifFile()
    nifout.initialize("SKYRIM", outfile, "BSFadeNode", "NobleChest01")
    bodynode = nifout.add_node("Chest01", nif.nodes["Chest01"].transform)
    chestout = _export_shape(nif.nodes["Chest01:1"], nifout, parent=bodynode)
    lidnode = nifout.add_node("Lid01", lid01.transform)
    p = lidnode.properties.copy()
    p.flags = 524430  
    lidnode.properties = p
    
    lidout = _export_shape(nif.nodes["Lid01:1"], nifout, parent=lidnode)

    nifout.root.bsx_flags = ['BSX', 11]

    openmtt = NiMultiTargetTransformController.New(
        file=nifout, flags=108, target=nifout.root)

    cmout = NiControllerManager.New(
        file=nifout, 
        flags=TimeControllerFlags(active=True, cycle_type=CycleType.CLAMP),
        next_controller=openmtt,
        parent=nifout.root)

    # Text key extra data created along with its keys
    tk = NiTextKeyExtraData.New(
        file=nifout,
        keys=[(0.0, "start",), (0.5, "end",)])

    # Object palette created along with object references
    objp = NiDefaultAVObjectPalette.New(
        file=nifout,
        scene=nifout.rootNode,
        objects={
            chestout.name: chestout,
            lidout.name: lidout,
            lidnode.name: lidnode,
            bodynode.name: bodynode,
        },
        parent=cmout,
    )

    # Create a controller sequence for the manager. The relationship between them is set
    # by passing the manager as the parent.
    openseq = NiControllerSequence.New(
        file=nifout, 
        name="Open", 
        accum_root_name="NobleChest01",
        start_time=0,
        stop_time=0.5,
        cycle_type = CycleType.CLAMP,
        text_key_data = tk,
        parent=cmout, 
    )
    
    # Transform data. The transform type is set with the Transform Data block, both the
    # rotation type and the interpolation type for each dimension. Then the keys are
    # added.
    opendata = NiTransformData.New(
        file=nifout, 
        rotation_type=NiKeyType.XYZ_ROTATION_KEY,
        xyz_rotation_types=(NiKeyType.QUADRATIC_KEY, NiKeyType.QUADRATIC_KEY, NiKeyType.QUADRATIC_KEY, ),
        scale_type=NiKeyType.QUADRATIC_KEY)

    # Can add keys by frame or by curve
    opendata.add_xyz_rotation_keys("X", [NiAnimKeyFloatBuf(0, 0, 0, 0)])
    opendata.add_xyz_rotation_keys("Y", [NiAnimKeyFloatBuf(0, 0, 0, 0)])
    opendata.add_xyz_rotation_keys("Z", [NiAnimKeyFloatBuf(0, 0, 0, 0)])

    q1x = NiAnimKeyFloatBuf()
    q1x.time = 0.5
    q1x.value = -0.1222
    q1x.forward = q1x.backward = 0
    opendata.add_xyz_rotation_keys("X", [NiAnimKeyFloatBuf(0.5, -0.1222, 0, 0)])
    opendata.add_xyz_rotation_keys("Y", [NiAnimKeyFloatBuf(0.5, 0, 0, 0)])
    opendata.add_xyz_rotation_keys("Z", [NiAnimKeyFloatBuf(0.5, 0, 0, 0)])
    
    openinterp = NiTransformInterpolator.New(file=nifout, data_block=opendata)
    
    openseq.add_controlled_block(
        "Lid01",
        interpolator=openinterp,
        controller=openmtt,
        #node_name="Lid01",
        #controller_type="NiTransformController",
    )

    closeseq = NiControllerSequence.New(
        file=nifout, 
        name="Close", 
        accum_root_name="NobleChest01",
        start_time=0,
        stop_time=0.5,
        cycle_type = CycleType.CLAMP,
        parent=cmout, 
    )

    nifout.save()

    # CHECK

    nifcheck = NifFile(outfile)
    CheckNif(nifcheck, source=testfile)


def TEST_ANIMATION_ALDUIN():
    """Animated skinned nif"""
    nif = NifFile(r"tests/SkyrimSE/loadscreenalduinwall.nif")
    tail2 = nif.nodes["NPC Tail2"]
    assert tail2.controller is not None, f"Have transform controller"
    assert tail2.controller.blockname == "NiTransformController", f"Created type correctly"
    assert math.isclose(tail2.controller.properties.stopTime, 28, abs_tol=0.001), "Have correct stop time"
    tdtail2 = tail2.controller.interpolator.data
    assert tdtail2.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY, f"Have correct rotation type"
    assert tdtail2.properties.xRotations.numKeys == 16, f"Have correct number of keys"
    assert tdtail2.translations[0].time == 0, f"Have 0 time value"
    assert VNearEqual(tdtail2.translations[0].value, [94.485031, 0, 0]), f"Have 0 location value"
    assert tdtail2.translations[15].time == 28.0, f"Have 15 time value"
    assert VNearEqual(tdtail2.translations[15].value, [94.485031, 0, 0]), f"Have 0 location value"
    
    # Lots of these rotations are LINEAR_KEY which means they're coded as a sequence
    # of quaternions.
    thighl = nif.nodes["NPC LLegThigh"]
    tdthighl = thighl.controller.interpolator.data
    assert len(tdthighl.xrotations) == 0, f"Have xrotations"
    assert len(tdthighl.qrotations) == 161, f"Have quat rotations"
    assert NearEqual(tdthighl.qrotations[0].value[0], 0.2911), f"Have correct angle: {tdthighl.qrotations[0].value}"


def TEST_ANIMATION_SHADER():
    """Embedded animations on shaders"""
    testfile = r"tests/SkyrimSE/meshes/armor/daedric/daedriccuirass_1.nif"
    outfile = r"tests\out\TEST_ANIMATION_SHADER.nif"
    nif = NifFile(testfile)

    CheckNif(nif)

    nifout = NifFile()
    nifout.initialize('SKYRIM', outfile)
    _export_shape(nif.shape_dict['TorsoLow:0'], nifout)
    _export_shape(nif.shape_dict['MaleTorsoGlow'], nifout)
    nifout.save()
    assert NifFile.message_log() == "", f"No messages: {NifFile.message_log()}"

    nifcheck = NifFile(outfile)
    CheckNif(nifcheck, source=testfile)


def TEST_ANIMATION_SHADER_BSLSP():
    """Embedded animations on BSLightingShaderProperty shaders"""
    testfile = r"tests/SkyrimSE\voidshade_1.nif"
    outfile = r"tests\out\TEST_ANIMATION_SHADER_BSLSP.nif"

    nif = NifFile(testfile)
    CheckNif(nif)

    nifout = NifFile()
    nifout.initialize('SKYRIMSE', outfile)
    _export_shape(nif.shape_dict['head'], nifout)
    nifout.save()
    assert NifFile.message_log() == "", f"No messages: {NifFile.message_log()}"

    nifcheck = NifFile(outfile)
    CheckNif(nifcheck, source=testfile)


def TEST_ANIMATION_SHADER_SPRIGGAN():
    """Embedded animations on shaders"""
    # Tests cover all controller types used by spriggans: 
    # NiControllerManager
    # NiControllerSequence
    # ControllerLink
    # BSEffectShaderPropertyFloatController
    # BSLightingShaderPropertyColorController
    # BSLightingShaderPropertyFloatController
    # BSNiAlphaPropertyTestRefController
    # BSNiAlphaPropertyTestRefController
    # NiBlendFloatInterpolator
    # NiBlendPoint3Interpolator
    # NiFloatInterpolator
    # NiPoint3Interpolator
    # NiFloatData
    # NiPosData
    testfile = r"tests\Skyrim\spriggan.nif"
    outfile = r"tests\out\TEST_ANIMATION_SHADER_SPRIGGAN.nif"
    nif = NifFile(testfile)
    cm:NiControllerManager = nif.root.controller

    # CONTROLLER SEQUENCE: LeavesLandedLoop 
    leaveslanded:NiControllerSequence = cm.sequences["LeavesLandedLoop"]

    # CONTROLLER LINK: Spriggan hand covers 
    handcovers:ControllerLink = next(
        cl for cl in leaveslanded.controlled_blocks 
        if cl.node_name == "SprigganFxHandCovers"
    )
    handcoversctl:BSEffectShaderPropertyFloatController = handcovers.controller
    assert math.isclose(handcoversctl.properties.stopTime, 11.933, abs_tol=0.001), f"Have correct float controller"
    
    # Because they are managed by a ControllerSequence, they have a blend interpolator
    hcblendint:NiBlendFloatInterpolator = handcoversctl.interpolator
    assert hcblendint.properties.flags == InterpBlendFlags.MANAGER_CONTROLLED, f"Blend is manager controlled"

    # Float interpolator with data
    hcfi:NiFloatInterpolator = handcovers.interpolator
    hcdat:NiFloatData = hcfi.data
    assert hcdat.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY, f"Correct key type"
    assert math.isclose(hcdat.keys[1].time, 1.333, abs_tol=0.001), f"Correct key time"

    # CONTROLLER LINK: Spriggan leaves
    bodyctl:ControllerLink = next(
        cl for cl in leaveslanded.controlled_blocks 
        if cl.node_name == "SprigganHandLeaves"
    )
    leavesctl:BSNiAlphaPropertyTestRefController = bodyctl.controller
    assert math.isclose(leavesctl.properties.stopTime, 15.333, abs_tol=0.001), f"Have correct alpha controller"

    # CONTROLLER LINK: Spriggan body color
    bodyctl, body2ctl = [
        cl for cl in leaveslanded.controlled_blocks 
        if cl.node_name == "SprigganFxTestUnified:0"
    ]
    colorctl:BSLightingShaderPropertyColorController = bodyctl.controller
    assert math.isclose(colorctl.properties.stopTime, 15.2333, abs_tol=0.01), f"stopTime correct"
    assert colorctl.properties.controlledVariable == LightingShaderControlledColor.EMISSIVE

    colorblendinterp:NiBlendPoint3Interpolator = colorctl.interpolator
    colorblendinterp.properties.flags == InterpBlendFlags.MANAGER_CONTROLLED, f"Correct control"

    colorinterp:NiPoint3Interpolator = bodyctl.interpolator
    colordat:NiPosData = colorinterp.data
    assert colordat.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY, f"Correct key type"
    assert math.isclose(colordat.keys[1].time, 2.0, abs_tol=0.001), f"Time is correct"
    assert math.isclose(colordat.keys[1].value[0], 0.5294, abs_tol=0.001), f"Have correct value"
    assert math.isclose(colordat.keys[1].value[1], 0.992157, abs_tol=0.001), f"Value is correct"

    # CONTROLLER LINK: Spriggan body emissive
    emissctl:BSLightingShaderPropertyFloatController = body2ctl.controller
    assert math.isclose(emissctl.properties.stopTime, 15.333, abs_tol=0.001), "Emissive stop correct"
    assert emissctl.properties.controlledVariable == LightingShaderControlledVariable.Emissive_Multiple, "Have correct controlled variable"
    return

    glowshape = nif.shape_dict['MaleTorsoGlow']
    ctlr = glowshape.shader.controller
    assert ctlr, f"Have shader controller {ctlr.blockname}"
    assert ctlr.properties.flags == 72, f"Have controller flags"
    assert ctlr.properties.controlledVariable == EffectShaderControlledVariable.V_Offset, f"Have correct controlled variable"
    interp = ctlr.interpolator
    assert interp, f"Have interpolator"
    assert interp.data, f"Have interpolator data"
    d = interp.data
    assert d.properties.keys.numKeys == 3, f"Have correct number of keys"
    assert NearEqual(d.keys[1].time, 3.333), f"Have correct time at 1"
    assert NearEqual(d.keys[1].backward, -1), f"Have correct backwards value at 1"

    nifout = NifFile()
    nifout.initialize('SKYRIM', outfile)
    _export_shape(nif.shape_dict['TorsoLow:0'], nifout)
    _export_shape(nif.shape_dict['MaleTorsoGlow'], nifout)
    nifout.save()
    assert NifFile.message_log() == "", f"No messages: {NifFile.message_log()}"

    nifcheck = NifFile(outfile)
    glowcheck = nifcheck.shape_dict['MaleTorsoGlow']
    assert glowcheck.shader.controller, f"Have EffectShaderController"


def TEST_KF():
    """Read and write KF animation file"""
    nif = NifFile(r"tests/SkyrimSE/1hm_attackpowerright.kf")
    root = nif.rootNode

    # Root node of these KF files is a NiControllerSequence.
    assert root.blockname == "NiControllerSequence", f"Found correct block name: {root.blockname}"
    assert root.name == "1hm_attackpowerright", f"Have root node {root.name}"
    assert len(root.controlled_blocks) == 91, f"Have controlled blocks: {len(root.controlled_blocks)}"

    # Controlled Blocks define what gets animated, which isn't in this file.
    cb = root.controlled_blocks[0]
    assert cb.controller_type == "NiTransformController", f"Have correct controller type: {cb.controller_type}"
    
    # Interpolator and Data define the animation itself.
    ti = cb.interpolator
    td = ti.data
    assert td.properties.rotationType == NiKeyType.QUADRATIC_KEY, f"Have expected rotation type: {td.properties.rotationType}"
    assert len(td.qrotations) == 36, f"Have quadratc rotation keys: {len(td.qrotations)}"

    nifout = NifFile()
    nifout.initialize("SKYRIM", r"tests/Out/TEST_KF.kf", "NiControllerSequence", "testKF")

    rootout = nifout.rootNode
    rootout.properties = root.properties

    # First key: Linear translation.
    ti = NiTransformInterpolator.New(file=nifout, parent=nifout.rootNode)
    td = NiTransformData.New(
        file=nifout, 
        rotation_type=NiKeyType.QUADRATIC_KEY, 
        translate_type=NiKeyType.LINEAR_KEY, 
        parent=ti)
    td.add_translation_key(0, (-0.029318, -0.229634, 0))

    rootout.add_controlled_block(
        name="NPC Root [Root]",
        interpolator=ti,
        node_name = "NPC Root [Root]",
        controller_type = "NiTransformController")

    # Second key: Quadratic rotation.
    ti2 = NiTransformInterpolator.New(
        file=nifout, 
        parent=nifout.rootNode)
    td2 = NiTransformData.New(
        file=nifout,
        rotation_type=NiKeyType.QUADRATIC_KEY,
        parent=ti2)
    td2.add_qrotation_key(0, (0.8452, 0.0518, -0.0010, -0.5320))

    rootout.add_controlled_block(
        name="NPC Pelvis [Pelv]",
        interpolator=ti2,
        node_name = "NPC Root [Root]",
        controller_type = "NPC Pelvis [Pelv]")

    nifout.save()

    nifcheck = NifFile(r"tests/Out/TEST_KF.kf")
    assert nifcheck.rootNode.blockname == "NiControllerSequence", f"Have correct root node type"
    assert nifcheck.rootNode.name == "testKF", f"Root node has name"
    assert len(nifcheck.rootNode.controlled_blocks) > 0, f"Have controlled blocks {nifcheck.rootNode.controlled_blocks}"

    # Check first controlled block
    cb = nifcheck.rootNode.controlled_blocks[0]
    assert cb.properties.controllerID == NODEID_NONE, f"No controller for this block"
    assert cb.node_name == "NPC Root [Root]", f"Have correct node name"
    assert cb.controller_type == "NiTransformController", f"Have transform controller type"
    assert cb.properties.propType == NODEID_NONE, f"Do NOT have property type"

    # Check first Interpolator/Data pair
    ticheck = cb.interpolator
    tdcheck = ticheck.data
    assert len(tdcheck.translations) > 0, "Have translations"

    # Check second controlled block
    cb2 = nifcheck.rootNode.controlled_blocks[1]
    ti2 = cb2.interpolator
    td2 = ti2.data
    assert len(td2.qrotations) > 0, "Have rotations"


def TEST_SKEL():
    """Import of skeleton file with collisions"""
    nif = NifFile(r"tests/Skyrim/skeleton_vanilla.nif")
    npc = nif.nodes['NPC']
    assert npc.string_data[0][1] == "Human"

    # COM node has a bhkBlendCollisionObject
    com = nif.nodes['NPC COM [COM ]']
    com_col = com.collision_object
    assert com_col.blockname == "bhkBlendCollisionObject", f"Have collision object: {com.collision_object.blockname}"
    com_col.properties.heirGain == 1.0, f"Have unique property"
    com_shape = com_col.body.shape
    assert NearEqual(com_shape.properties.point1[0], -com_shape.properties.point2[0]), \
        f"Capsule shape symmetric around x-axis."
    assert NearEqual(com_shape.properties.point1[0], 0.041862), f"Have correct X location"
    assert NearEqual(com_shape.properties.bhkRadius, 0.130600), f"Have correct radius"

    # Spine1 node has a ragdoll node, which references two others
    spine1 = nif.nodes['NPC Spine1 [Spn1]']
    spine1_col = spine1.collision_object
    spine1_rb = spine1_col.body
    spine1_rag = spine1_rb.constraints[0]
    assert len(spine1_rag.entities) == 2, f"Have ragdoll entities"

    # The character bumper uses a bhkSimpleShapePhantom, with its own transform.
    bumper = nif.nodes['CharacterBumper']
    bumper_col = bumper.collision_object
    bumper_bod = bumper_col.body
    assert bumper_bod.blockname == "bhkSimpleShapePhantom"
    assert bumper_bod.properties.transform[0][0] != 0, f"Have a transform"


def TEST_COLLISION_SPHERE():
    """Can read and write sphere collisions"""
    nif = NifFile(r"tests/SkyrimSE\spitpotopen01.nif")

    anchor = nif.nodes["ANCHOR"]
    coll = anchor.collision_object
    collbody = coll.body
    collshape = collbody.shape
    assert collshape.blockname == "bhkSphereShape", f"Have sphere shape: {collshape.blockname}"
    
    hook = nif.nodes["L1_Hook"]
    hook_col = hook.collision_object
    hook_bod = hook_col.body
    assert hook_bod.blockname == "bhkRigidBodyT", "Have RigidBodyT"
    assert hook_bod.properties.bufType == PynBufferTypes.bhkRigidBodyTBufType


def TEST_TREE():
    """Test that the special nodes for trees work correctly."""

    def check_tree(nifcheck):
        assert nifcheck.rootNode.blockname == "BSLeafAnimNode", f"Have correct root node type"

        tree = nifcheck.shapes[0]
        assert tree.blockname == "BSMeshLODTriShape", f"Have correct shape node type"
        assert tree.shader.properties.shaderflags2_test(ShaderFlags2.TREE_ANIM), f"Tree animation set"
        assert tree.properties.vertexCount == 1059, f"Have correct vertex count"
        assert tree.properties.lodSize0 == 1126, f"Have correct lodSize0"

    testfile = _test_file(r"tests\FO4\TreeMaplePreWar01Orange.nif")
    outfile = _test_file(r"tests/Out/TEST_TREE.nif")

    nif = NifFile(testfile)
    check_tree(nif)

    print(f"------------- write")
    nifOut = NifFile()
    nifOut.initialize('FO4', outfile, nif.rootNode.blockname, nif.rootNode.name)
    _export_shape(nif.shapes[0], nifOut)
    nifOut.save()

    print(f"------------- check")
    nifCheck = NifFile(outfile)
    check_tree(nifCheck)


def TEST_DOCKSTEPSDOWNEND():
    """Test that BSLODTriShape nodes load correctly."""
    def check_dock(nif):
        assert nif.rootNode.blockname == "BSFadeNode", f"Have BSFadeNode as root: {nif.rootNode.blockname}"
        assert len(nif.shapes) == 3, "Have all shapes"
        s = nif.shape_dict["DockStepsDownEnd01:0 - L1_Supports:0"]
        assert s, f"Have supports shape"
        assert s.blockname == "BSLODTriShape", "Have BSLODTriShape"
        assert s.properties.level0 == 234, f"Have correct level0: {s.properties.level0}"
        assert s.properties.level1 == 88, f"Have correct level1: {s.properties.level1}"

    testfile = _test_file(r"tests\Skyrim\dockstepsdownend01.nif")
    outfile = _test_file(r"tests\out\TEST_DOCKSTEPSDOWNEND.nif")

    print("------------- read")
    nif = NifFile(testfile)
    check_dock(nif)

    print("------------- write")
    nifOut = NifFile()
    nifOut.initialize('SKYRIM', outfile, nif.rootNode.blockname, nif.rootNode.name)
    _export_shape(nif.shapes[0], nifOut)
    _export_shape(nif.shapes[1], nifOut)
    _export_shape(nif.shapes[2], nifOut)
    nifOut.save()

    print("------------- check")
    check_dock(NifFile(outfile))


def TEST_FULLPREC():
    """Test that we can set full precision on a shape."""
    testfile = _test_file(r"tests\FO4\OtterFemHead.nif")
    outfile = _test_file(r"tests\out\TEST_FULLPREC.nif")

    print("------------- read")
    nif = NifFile(testfile)

    head = nif.shapes[0]
    newverts = []
    for v in head.verts:
        newverts.append((v[0], v[1], v[2]+120,))

    print("------------- write")
    nifOut = NifFile()
    nifOut.initialize('FO4', outfile, nif.rootNode.blockname, nif.rootNode.name)
    p = nif.shapes[0].properties.copy()
    p.hasFullPrecision = True
    _export_shape(nif.shapes[0], nifOut, properties=p, verts=newverts)
    nifOut.save()

    print("------------- check")
    nifCheck = NifFile(outfile)
    assert nifCheck.shapes[0].properties.hasFullPrecision, f"Have full precision"


def TEST_SET_SKINTINT():
    """Test that we can set the skin tint shader."""
    testfile = _test_file(r"tests\FO4\Helmet.nif")
    outfile = _test_file(r"tests\out\TEST_SET_SKINTINT.nif")

    print("------------- read")
    nif = NifFile(testfile)
    helmet = nif.shape_dict["Helmet:0"]

    print("------------- write")
    nifOut = NifFile()
    nifOut.initialize('FO4', outfile, nif.rootNode.blockname, nif.rootNode.name)
    helmet.shader.properties.Shader_Type = BSLSPShaderType.Skin_Tint
    _export_shape(helmet, nifOut)
    nifOut.save()

    print("------------- check")
    nifCheck = NifFile(outfile)
    helmetcheck = nifCheck.shape_dict["Helmet:0"]
    assert helmetcheck.shader.properties.Shader_Type == BSLSPShaderType.Skin_Tint, \
        f"Have fixed shader type {helmetcheck.shader.properties.Shader_Type}"


def TEST_HKX_SKELETON():
    """Test read/write of hkx skeleton files (in XML format)."""
    pass
    # SKIPPING - This functionality is part of animation read/write, which is not
    # fully operational.

    # testfile = _test_file(r"tests/Skyrim/skeleton.hkx")
    # outfile = _test_file(r"tests/Out/TEST_XML_SKELETON.nif")

    # f = hkxSkeletonFile(testfile)
    # assert len(f.nodes) == 99, "Have all bones."
    # assert f.rootNode.name == "NPC Root [Root]"
    # assert len(f.shapes) == 0, "No shapes"
    # assert f.rootName == 'NPC Root [Root]', f"Have root name: {f.rootName}"

    # headbone = f.nodes["NPC Head [Head]"]
    # handbone = f.nodes["NPC L Hand [LHnd]"]
    # assert NearEqual(headbone.global_transform.translation[2], 120.3436), "Head bone where it should be."
    # assert NearEqual(handbone.global_transform.translation[0], -28.9358), f"L Hand bone where it should be" 

alltests = [t for k, t in sys.modules[__name__].__dict__.items() if k.startswith('TEST_')]
passed_tests = []
failed_tests = []
stop_on_fail = False


def execute_test(t):
    NifFile.clear_log()
    print(f"\n\n\n++++++++++++++++++++++++++++++ {t.__name__} ++++++++++++++++++++++++++++++")
    # the_test = __dict__[t]
    print(t.__doc__)
    if stop_on_fail:
        t()
    else:
        try:
            t()
            passed_tests.append(t)
        except:
            log.exception("Test failed with exception")
            failed_tests.append(t)
    print(f"------------- done")


def execute(start=None, testlist=None, exclude=[]):
    print("""\n
=====================================================================
======================= Running pynifly tests =======================
=====================================================================

""")
    if testlist:
        for test in testlist:
            if test not in passed_tests and test not in failed_tests:
                execute_test(test)
    else:
        doit = (start is None) 
        for t in alltests:
            if t == start: doit = True
            if doit and not t in exclude and t not in passed_tests and t not in failed_tests:
                execute_test(t)

    if stop_on_fail:
        print("""

============================================================================
======================= TESTS COMPLETED SUCCESSFULLY =======================
============================================================================
""")
    else:
        print(f"""
============================================================================
============================ TESTS PASSED ==================================
{", ".join([t.__name__ for t in passed_tests])}
============================ TESTS FAILED ==================================
{", ".join([t.__name__ for t in failed_tests])}
============================================================================
""")


if __name__ == "__main__":

    # Load from install location
    py_addon_path = os.path.dirname(os.path.realpath(__file__))
    #log.debug(f"PyNifly addon path: {py_addon_path}")
    if py_addon_path not in sys.path:
        sys.path.append(py_addon_path)
    dev_path = os.path.join(py_addon_path, "NiflyDLL.dll")
    hkxcmd_path = os.path.join(py_addon_path, "hkxcmd.exe")
    xmltools.XMLFile.SetPath(hkxcmd_path)
    os.chdir(py_addon_path)

    dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
    NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

    mylog = logging.getLogger("pynifly")
    logging.basicConfig()
    mylog.setLevel(logging.DEBUG)

    # ############## TESTS TO RUN #############
    stop_on_fail = True
    # execute(testlist=[TEST_ALPHA_THRESHOLD_CONTROLLER])
    # execute(start=TEST_KF, exclude=[TEST_SET_SKINTINT])
    execute(exclude=[TEST_SET_SKINTINT])
    #