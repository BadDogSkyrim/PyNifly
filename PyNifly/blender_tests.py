"""Automated tests for pyNifly export/import addon

Convenient setup for running these tests here: 
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""
import bpy
from mathutils import Matrix, Vector, Quaternion
from test_tools import *
from pynifly import *
from blender_defs import *


TEST_BPY_ALL = False
TEST_VERTEX_COLOR_IO = False
TEST_BONE_HIERARCHY = False
TEST_SCALING_COLL = True


if TEST_BPY_ALL or TEST_VERTEX_COLOR_IO:
    test_title("TEST_VERTEX_COLOR_IO", "Vertex colors can be read and written")
    clear_all()
    testfile = test_file(r"tests\FO4\FemaleEyesAO.nif")
    outfile = test_file(r"tests/Out/TEST_VERTEX_COLOR_IO.nif", output=1)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    eyes = find_shape("FemaleEyesAO:0")
    assert eyes.active_material["Shader_Flags_2"].find("VERTEX_COLORS") >= 0, \
        f"Eyes have colors: {eyes.active_material['Shader_Flags_2']}"
    colors = eyes.data.color_attributes.active_color.data
    max_r = max(c.color[0] for c in colors)
    min_r = min(c.color[0] for c in colors)
    assert max_r == 0, f"Have no white verts: {max_r}"
    assert min_r == 0, f"Have some black verts: {min_r}"

    # BSEffectShaderProperty is assumed to use the alpha channel whether or not the flag is set.
    # Alpha is represented as ordinary color on the VERTEX_ALPHA color attribute
    colors = eyes.data.color_attributes['VERTEX_ALPHA'].data
    max_a = max(c.color[0] for c in colors)
    min_a = min(c.color[0] for c in colors)
    assert max_a == 1.0, f"Have some opaque verts: {max_a}"
    assert min_a == 0, f"Have some transparent verts: {min_a}"

    bpy.ops.object.select_all(action='DESELECT')
    eyes.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    assert os.path.exists(outfile), f"File created: {outfile}"

    nifcheck = NifFile(outfile)
    eyescheck = nifcheck.shapes[0]
    min_a = min(c[3] for c in eyescheck.colors)
    max_a = max(c[3] for c in eyescheck.colors)
    assert min_a == 0, f"Minimum alpha is 0: {min_a}"
    assert max_a == 1, f"Max alpha is 1: {max_a}"


if TEST_BPY_ALL or TEST_BONE_HIERARCHY:
    test_title("TEST_BONE_HIERARCHY", "Bone hierarchy can be written on export")
    clear_all()
    testfile = test_file(r"tests\SkyrimSE\Anna.nif")
    outfile = test_file(r"tests/Out/TESTS_BONE_HIERARCHY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    hair = find_shape("KSSMP_Anna")
    skel = hair.parent
    assert skel

    print("# -------- Export --------")
    bpy.ops.object.select_all(action='DESELECT')
    hair.select_set(True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True,
                                 rename_bones=True)

    print("# ------- Check ---------")
    nifcheck = NifFile(outfile)
    haircheck = nifcheck.shape_dict["KSSMP_Anna"]

    com = nifcheck.nodes["NPC COM [COM ]"]
    assert VNearEqual(com.transform.translation, (0, 0, 68.9113)), f"COM location is correct: \n{com.transform}"

    spine0 = nifcheck.nodes["NPC Spine [Spn0]"]
    assert VNearEqual(spine0.transform.translation, (0, -5.239852, 3.791618)), f"spine0 location is correct: \n{spine0.transform}"
    spine0Rot = Matrix(spine0.transform.rotation).to_euler()
    assert VNearEqual(spine0Rot, (-0.0436, 0, 0)), f"spine0 rotation correct: {spine0Rot}"

    spine1 = nifcheck.nodes["NPC Spine1 [Spn1]"]
    assert VNearEqual(spine1.transform.translation, (0, 0, 8.748718)), f"spine1 location is correct: \n{spine1.transform}"
    spine1Rot = Matrix(spine1.transform.rotation).to_euler()
    assert VNearEqual(spine1Rot, (0.1509, 0, 0)), f"spine1 rotation correct: {spine1Rot}"

    spine2 = nifcheck.nodes["NPC Spine2 [Spn2]"]
    assert spine2.parent.name == "NPC Spine1 [Spn1]", f"Spine2 parent is correct"
    assert VNearEqual(spine2.transform.translation, (0, -0.017105, 9.864068), 0.01), f"Spine2 location is correct: \n{spine2.transform}"

    head = nifcheck.nodes["NPC Head [Head]"]
    assert VNearEqual(head.transform.translation, (0, 0, 7.392755)), f"head location is correct: \n{head.transform}"
    headRot = Matrix(head.transform.rotation).to_euler()
    assert VNearEqual(headRot, (0.1913, 0.0009, -0.0002), 0.01), f"head rotation correct: {headRot}"

    l3 = nifcheck.nodes["Anna L3"]
    assert l3.parent, f"'Anna L3' parent exists"
    assert l3.parent.name == 'Anna L2', f"'Anna L3' parent is '{l3.parent.name}'"
    assert VNearEqual(l3.transform.translation, (0, 5, -6), 0.1), f"{l3.name} location correct: \n{l3.transform}"

    nif = NifFile(testfile)
    hair = nif.shape_dict["KSSMP_Anna"]
    assert set(hair.get_used_bones()) == set(haircheck.get_used_bones()), \
        f"The bones written to the shape match original: {haircheck.get_used_bones()}"

    sk2b = haircheck.get_shape_skin_to_bone("Anna L3")
    assert sk2b.NearEqual(hair.get_shape_skin_to_bone("Anna L3")), \
        f"Anna L3 skin-to-bone matches original: \n{sk2b}"


if TEST_BPY_ALL or TEST_SCALING_COLL:
    test_title("TEST_SCALING_COLL", "Collisions scale correctly on import and export")
    # Primarily tests collisions, but also tests fade node, extra data nodes, 
    # UV orientation, and texture handling
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = test_file(r"tests/Out/TEST_SCALING_COLL.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=0.1)
    obj = find_shape("ElvenBowSkinned:0")

    # After import with a scale factor, imported object records the scale factor
    assert 'PYN_SCALE_FACTOR' in obj, f"Scale fector recorded on {obj.name}"
    assert NearEqual(obj['PYN_SCALE_FACTOR'], 0.1), f"Scale factor is correct on {obj.name}: {obj['PYN_SCALE_FACTOR']}"
    assert 'PYN_SCALE_FACTOR' in obj.parent, f"Scale fector recorded on {obj.name.parent}"
    assert NearEqual(obj.parent['PYN_SCALE_FACTOR'], 0.1), f"Scale factor is correct on {obj.parent.name}: {obj.parent['PYN_SCALE_FACTOR']}"

    # Check collision info
    coll = find_shape('bhkCollisionObject')
    assert VNearEqual(coll.location, (0.130636, 0.637351, -0.001978)), \
        f"Collision location properly scaled: {coll.location}"

    collbody = coll.children[0]
    assert collbody.name == 'bhkRigidBodyT', f"Child of collision is the collision body object"
    assert VNearEqual(collbody.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), \
        f"Collision body rotation correct: {collbody.rotation_quaternion}"
    assert VNearEqual(collbody.location, (0.65169, -0.770812, 0.0039871)), \
        f"Collision body is in correct location: {collbody.location}"

    collshape = collbody.children[0]
    assert collshape.name == 'bhkBoxShape', f"Collision shape is child of the collision body"
    assert NearEqual(collshape['bhkRadius'], 0.00136), f"Radius is properly scaled: {collshape['bhkRadius']}"
    assert VNearEqual(collshape.data.vertices[0].co, (-1.10145, 5.76582, 0.09541)), \
        f"Collision shape is properly scaled 0: {collshape.data.vertices[0].co}"
    assert VNearEqual(collshape.data.vertices[7].co, (1.10145, 5.76582, -0.09541)), \
        f"Collision shape is properly scaled 7: {collshape.data.vertices[7].co}"
    assert VNearEqual(collshape.location, (0,0,0)), f"Collision shape centered on parent: {collshape.location}"
    
    print("--Testing export")

    # Move the edge of the collision box so it covers the bow better
    for v in collshape.data.vertices:
        if v.co.x > 0:
            v.co.x = 1.65

    # ------- Export and Check Results --------

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    coll.select_set(True)

    # Depend on the defaults stored on the armature for scale factor
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True)

    nif = NifFile(testfile)
    nifcheck = NifFile(outfile)
    compare_shapes(nif.shape_dict['ElvenBowSkinned:0'],
                   nifcheck.shape_dict['ElvenBowSkinned:0'],
                   obj,
                   scale=0.1)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    compare_bones('Bow_MidBone', nif, nifcheck)
    compare_bones('Bow_StringBone2', nif, nifcheck)

    bodycheck = collcheck.body
    p = bodycheck.properties
    assert VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    assert VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


print("""
############################################################
##                                                        ##
##                    TESTS DONE                          ##
##                                                        ##
############################################################
""")
