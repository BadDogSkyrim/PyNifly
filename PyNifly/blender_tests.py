"""Automated tests for pyNifly export/import addon

Convenient setup for running these tests here: 
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""
import bpy
from mathutils import Matrix, Vector
from test_tools import *
from pynifly import *
from blender_defs import *
from trihandler import *


TEST_BPY_ALL = 0
TEST_BODYPART_SKY = 0  ### Skyrim head
TEST_BODYPART_FO4 = 0  ### FO4 head
TEST_SKYRIM_XFORM = 0  ### Read & write the Skyrim shape transforms
TEST_SKIN_BONE_XF = 0  ### Argonian head
TEST_IMP_EXP_SKY = 0  ### Skyrim armor
TEST_IMP_EXP_SKY_2 = 0  ### Body+Underwear
TEST_IMP_EXP_FO4 = 0  ### Can read the body nif and spit it back out
TEST_IMP_EXP_FO4_2 = 0  ### Can read body armor with 2 parts
TEST_ROUND_TRIP = 0  ### Full round trip: nif -> blender -> nif -> blender
TEST_BPY_PARENT_A = 0  ### Skeleton armature bones correctly parented
TEST_BPY_PARENT_B = 0  ### Skeleton armature bones correctly parented
TEST_RENAME = 0  ### Bone renaming for Blender conventions disabled
TEST_CONNECTED_SKEL = 0  ### Can import connected skeleton
TEST_DRAUGR_IMPORT_A = 0  ### Import hood, extend skeleton, non-vanilla pose 
TEST_DRAUGR_IMPORT_B = 0  ### Import hood, don't extend skeleton, non-vanilla pose
TEST_DRAUGR_IMPORT_C = 0  ### Import helm, don't extend skeleton
TEST_DRAUGR_IMPORT_D = 0  ### Import helm, do extend skeleton
TEST_DRAUGR_IMPORT_E = 0  ### Import helm and hood together
TEST_SCALING_BP = 0  ### Import and export bodypart with scale factor
TEST_IMP_EXP_SCALE_2 = 0  ### Import nif with 2 meshes scaled
TEST_ARMATURE_EXTEND = 0  ### FO4 head + body
TEST_ARMATURE_EXTEND_BT = 0  ### Import two nifs that share a skeleton
TEST_EXPORT_WEIGHTS = 0  ### Import and export with weights
TEST_WEIGHTS_EXPORT = 0  ### Exporting this head weights all verts correctly
TEST_0_WEIGHTS = 0  ### Gives warning on export with 0 weights
TEST_TIGER_EXPORT = 0  ### Tiger head export
TEST_3BBB = 0  ### Test that mesh imports with correct transforms
TEST_SKEL = 0  ### Import skeleton file with no shapes
TEST_HEADPART = 0  ### Read & write SE head part with tris
TEST_TRI = 0  ### Can load a tri file into an existing mesh
TEST_IMPORT_AS_SHAPES = 0  ### Import 2 meshes as shape keys
TEST_IMPORT_MULT_SHAPES = 0  ### Import >2 meshes as shape keys
TEST_EXP_SK_RENAMED = 0  ### Ensure renamed shape keys export properly
TEST_SK_MULT = 0  ### Export multiple objects with only some shape keys
TEST_TRI2 = 0  ### Regression: Test correct import of tri
TEST_BAD_TRI = 0  ### Tris with messed up UV
TEST_TRIP_SE = 0  ### Bodypart tri extra data and file are written on export
TEST_TRIP = 0  ### Body tri extra data and file are written on export
TEST_COLORS = 0  ### Read & write vertex colors
TEST_COLORS2 = 0  ### Read & write vertex colors
TEST_NEW_COLORS = 0  ### Can write vertex colors that were created in blender
TEST_VERTEX_COLOR_IO = 0  ### Vertex colors can be read and written
TEST_SHADER_GLOW = 0  ### BSEffectShaderProperty
TEST_VERTEX_ALPHA_IO = 0  ### Vertex alpha affects Blender visible alpha
TEST_VERTEX_ALPHA = 0  ### Export shape with vertex alpha values
TEST_BONE_HIERARCHY = 0  ### Import and export bone hierarchy
TEST_SEGMENTS = 0  ### FO4 segments
TEST_BP_SEGMENTS = 0  ### Another test of FO4 segments
TEST_EXP_SEGMENTS_BAD = 0  ### Verts export in the correct FO4 segments
TEST_EXP_SEG_ORDER = 0  ### Segments export in numerical order
TEST_PARTITIONS = 0  ### Read Skyrim partitions
TEST_SHADER_LE = 0  ### Shader attributes Skyrim LE
TEST_SHADER_SE = 0  ### Shader attributes Skyrim SE 
TEST_SHADER_FO4 = 0  ### Shader attributes are read and turned into Blender shader nodes
TEST_SHADER_ALPHA = 0  ### Alpha property handled correctly
TEST_SHADER_3_3 = 0  ### Shader attributes are read and turned into Blender shader nodes
TEST_CAVE_GREEN = 0  ### Use vertex colors in shader
TEST_POT = 0  ### Pot shader doesn't throw an error
TEST_NOT_FB = 0  ### Nif that looked like facebones skel can be imported
TEST_MULTI_IMP = 0  ### Importing multiple hair parts doesn't mess up
TEST_WELWA = 0  ### Shape with unusual skeleton
TEST_MUTANT = 0  ### Supermutant body imports correctly the *second* time
TEST_EXPORT_HANDS = 0  ### Hand mesh with errors doesn't crash
TEST_PARTITION_ERRORS = 0  ### Partitions with errors raise errors
TEST_SHEATH = 0  ### Extra data nodes are imported and exported
TEST_FEET = 0  ### Extra data nodes are imported and exported
TEST_SCALING = 0  ### Scale factors applied correctly
TEST_SCALING_OBJ = 0  ### Scale simple objects
TEST_UNIFORM_SCALE = 0  ### Export objects with uniform scaling
TEST_NONUNIFORM_SCALE = 0  ### Export objects with non-uniform scaling
TEST_FACEBONE_EXPORT = 0
TEST_FACEBONE_EXPORT2 = 0  ### Facebones with odd armature
TEST_HYENA_PARTITIONS = 0
TEST_MULT_PART = 0  ### Export shape with face that might fall into multiple partititions
TEST_BONE_XPORT_POS = 0
TEST_NORM = 0  ### Normals are read correctly
TEST_ROGUE01 = 0  ### Custom split normals export correctly
TEST_ROGUE02 = 0  ### Objects with shape keys export normals correctly
TEST_NORMAL_SEAM = 0  ### Custom normals can make a seam seamless
TEST_NIFTOOLS_NAMES = 0
TEST_BOW = 1  ### Read and write bow
TEST_BOW2 = 1  ### Modify collision shape location
TEST_BOW3 = 1  ### Modify collision shape type
TEST_COLLISION_HIER = 1  ### Read and write collision of hierarchy of nodes
TEST_SCALING_COLL = 1
TEST_COLLISION_MULTI = 1
TEST_COLLISION_CONVEXVERT = 1
TEST_COLLISION_CAPSULE = 1  ### Collision capsule shapes with scale
TEST_COLLISION_LIST = 1  ### Collision list and collision transform shapes with scale
TEST_CHANGE_COLLISION = 1  ### Changing collision type 
TEST_COLLISION_XFORM = 1  ### Read and write shape with collision capsule shapes
TEST_CONNECT_POINT = 1  ### Connect points are imported and exported
TEST_WEAPON_PART = 1  ### Weapon parts are imported at the parent connect point
TEST_IMPORT_MULT_CP = 1  ### Import multiple files and connect up the connect points
TEST_FURN_MARKER1 = 1  ### Skyrim furniture markers 
TEST_FURN_MARKER2 = 1  ### Skyrim furniture markers
TEST_FO4_CHAIR = 1  ### FO4 furniture markers 
TEST_PIPBOY = 1
TEST_BABY = 1  ### FO4 baby 
TEST_ROTSTATIC = 1  ### Statics are transformed according to the shape transform
TEST_ROTSTATIC2 = 1  ### Statics are transformed according to the shape transform
TEST_FACEBONES = 1
TEST_FACEBONES_RENAME = 1  ### Facebones are correctly renamed from Blender to the game's names
TEST_BONE_XF = 1
TEST_IMP_ANIMATRON = 1
TEST_CUSTOM_BONES = 1  ### Can handle custom bones correctly
TEST_COTH_DATA = 1  ## Handle cloth data
TEST_IMP_NORMALS = 1  ### Can import normals from nif shape
TEST_UV_SPLIT = 1  ### Split UVs properly
TEST_JIARAN = 1  ### Armature with no stashed transforms exports correctly

log = logging.getLogger("pynifly")
log.setLevel(logging.DEBUG)

if TEST_BPY_ALL or TEST_BODYPART_SKY:
    # Basic test that a Skyrim bodypart is imported correctly. 
    # Verts are organized around the origin, but skin transform is put on the shape 
    # and that lifts them to the head position.  
    test_title("TEST_BODYPART_SKY", "Can import a Skyrim head with armature")
    clear_all()
    testfile = test_file("tests\Skyrim\malehead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    male_head = bpy.context.object
    assert round(male_head.location.z, 0) == 120, "ERROR: Object not elevated to position"
    assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"
    maxz = max([v.co.z for v in male_head.data.vertices])
    assert NearEqual(maxz, 11.5, epsilon=0.1), f"Max Z ~ 11.5: {maxz}"
    minz = min([v.co.z for v in male_head.data.vertices])
    assert NearEqual(minz, -11, epsilon=0.1), f"Min Z ~ -11: {minz}"

    
if TEST_BPY_ALL or TEST_BODYPART_FO4:
    # Basic test that a FO4 bodypart imports correctly. 
    # Verts are organized around the origin but the skin-to-bone transforms are 
    # all consistent, so they are put on the shape.
    test_title("TEST_BODYPART_FO4", "Can import a FO4 head with armature")
    clear_all()
    testfile = test_file("tests\FO4\BaseMaleHead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    male_head = bpy.data.objects["BaseMaleHead:0"]
    assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
    assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"
    maxz = max([v.co.z for v in male_head.data.vertices])
    assert NearEqual(maxz, 8.3, epsilon=0.1), f"Max Z ~ 8.3: {maxz}"
    minz = min([v.co.z for v in male_head.data.vertices])
    assert NearEqual(minz, -12.1, epsilon=0.1), f"Min Z ~ -12.1: {minz}"


if TEST_BPY_ALL or TEST_SKYRIM_XFORM:
    test_title("TEST_SKYRIM_XFORM", "Can read & write the Skyrim shape transforms")
    clear_all()
    testfile = test_file(r"tests/Skyrim/MaleHead.nif")
    outfile = test_file(r"tests/Out/TEST_SKYRIM_XFORM.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert int(obj.location[2]) == 120, f"Shape offset not applied to head, found {obj.location[2]}"

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nifcheck = NifFile(outfile)
    headcheck = nifcheck.shapes[0]
    assert int(headcheck.transform.translation[2]) == 120, f"Shape offset not written correctly, found {headcheck.transform.translation[2]}"
    assert int(headcheck.global_to_skin.translation[2]) == -120, f"Shape global-to-skin not written correctly, found {headcheck.global_to_skin.translation[2]}"


if TEST_BPY_ALL or TEST_SKIN_BONE_XF:
    # The Argonian head has no global-to-skin transform and the bone pose locations are
    # exactly the vanilla locations, and yet the verts are organized around the origin.
    # The head is lifted into position with the skin-to-bone transforms (same way as FO4).
    test_title("TEST_SKIN_BONE_XF", "Skin-to-bone transforms work correctly")
    clear_all()

    testfile = test_file(r"tests\SkyrimSE\maleheadargonian.nif")
    outfile = test_file(r"tests\out\TEST_SKIN_BONE_XF.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = find_object("_ArgonianMaleHead", bpy.context.selected_objects, fn=lambda x: x.name)
    assert NearEqual(head.location.z, 120.344), f"Head is positioned at head position: {head.location}"
    minz = min(v[2] for v in head.bound_box)
    maxz = max(v[2] for v in head.bound_box)
    assert minz < 0, f"Head extends below origin: {minz}"
    assert maxz > 0, f"Head extends above origin: {maxz}"

    arma = head.parent
    spine2_xf = arma.data.bones['NPC Spine2'].matrix_local
    head_xf = arma.data.bones['NPC Head'].matrix_local
    assert VNearEqual(head_xf.translation, (-0.0003, -1.5475, 120.3436)), f"Head position at 120: {head_xf.translation}"
    assert VNearEqual(spine2_xf.translation, (0.0, -5.9318, 91.2488)), f"Spine2 position at 91: {spine2_xf.translation}"

    spine2_pose_xf = arma.pose.bones['NPC Spine2'].matrix
    head_pose_xf = arma.pose.bones['NPC Head'].matrix
    assert VNearEqual(head_pose_xf.translation, Vector((-0.0003, -1.5475, 120.3436))), f"Head pose position at 120: {head_pose_xf.translation}"
    assert VNearEqual(spine2_pose_xf.translation, Vector((0.0000, -5.9318, 91.2488))), f"Spine2 pose position at 91: {spine2_pose_xf.translation}"

    head_nif = NifFile(testfile)
    head_nishape = head_nif.shapes[0]
    def print_xf(sh, bn):
        print(f"-----{bn}-----")
        global_xf = head_nif.nodes[bn].xform_to_global.as_matrix()
        sk2b_xf = head_nishape.get_shape_skin_to_bone(bn).as_matrix()
        bind_xf = sk2b_xf.inverted()
        print(f"global xf = \n{global_xf}")
        #print(f"Head sk2b = \n{head_sk2b_orig}")
        print(f"bind xf = \n{bind_xf}")

    print_xf(head_nishape, "NPC Head [Head]")
    print_xf(head_nishape, "NPC Spine2 [Spn2]")

    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    nifcheck = NifFile(outfile)
    headcheck = nifcheck.shapes[0]
    sk2b_spine = headcheck.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
    assert NearEqual(sk2b_spine.translation[2], 29.419632), f"Have correct z: {sk2b_spine.translation[2]}"


if TEST_BPY_ALL or TEST_IMP_EXP_SKY:
    # Round trip of ordinary Skyrim armor, with and without scale factor.
    test_title("TEST_IMP_EXP_SKY", "Can read the armor nif and spit it back out")

    testfile = test_file(r"tests/Skyrim/armor_only.nif")
    impnif = NifFile(testfile)

    def do_test(scale_factor):
        log.debug(f"\nTesting with scale factor {scale_factor}")
        clear_all()
        outfile = test_file(f"tests/Out/TEST_IMP_EXP_SKY_{scale_factor}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=scale_factor)

        armorin = impnif.shape_dict['Armor']
        armor = find_shape('Armor')

        vmin, vmax = get_obj_bbox(armor)
        assert VNearEqual(vmin, Vector([-30.32, -13.31, -90.03])*scale_factor, 0.1), f"Armor min is correct: {vmin}"
        assert VNearEqual(vmax, Vector([30.32, 12.57, -4.23])*scale_factor, 0.1), f"Armor max is correct: {vmax}"
        assert NearEqual(armor.location.z, 120.34*scale_factor, 0.01), f"{armor.name} in lifted position: {armor.location.z}"
        arma = armor.parent
        assert arma.name == "Scene Root", f"armor has parent: {arma}"

        pelvis = arma.data.bones['NPC Pelvis']
        pelvis_pose = arma.pose.bones['NPC Pelvis'] 
        assert pelvis.parent.name == 'CME LBody', f"Pelvis has correct parent: {pelvis.parent}"
        assert VNearEqual(pelvis.matrix_local.translation, pelvis_pose.matrix.translation), \
            f"Pelvis pose position matches bone position: {pelvis.matrix_local.translation} == {pelvis_pose.matrix.translation}"

        bpy.ops.object.select_all(action='DESELECT')
        armor.select_set(True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM", scale_factor=scale_factor)

        nifout = NifFile(outfile)

        compare_shapes(armorin, nifout.shape_dict['Armor'], armor, scale=scale_factor, e=0.01)
        check_unweighted_verts(nifout.shape_dict['Armor'])

    do_test(1.0)
    do_test(0.1)
        

if TEST_BPY_ALL or TEST_IMP_EXP_SKY_2:
    # Basic test that the import/export round trip works on nifs with multiple bodyparts. 
    # The body in this nif has no skin transform and the verts are where they appear
    # to be. The armor does have the usual transform on the shape and the skin, and the
    # verts are all below the origin. They have to be loaded into one armature.
    test_title("TEST_IMP_EXP_SKY_2", "Can read the armor nif with two shapes and spit it back out")
    clear_all()

    #testfile = test_file(r"tests/Skyrim/test.nif") 
    # 
    # The test.nif meshes are a bit wonky--one was pasted in by hand from SOS, the other
    # is a vanilla armor. The ForearmTwist2.L bind rotation is off by some hundredths.  
    # So do the test with the vanilla male body, which has two parts and is consistent.
    testfile = test_file(r"tests/Skyrim/malebody_1.nif")
    # skelfile = test_file(r"tests/Skyrim/skeleton_vanilla.nif")
    outfile = test_file(r"tests/Out/TEST_IMP_EXP_SKY_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    assert len([x for x in bpy.data.objects if x.type=='ARMATURE']) == 1, \
        f"Both shapes brought in under one armor"
    body = find_shape('MaleUnderwearBody:0')
    armor = find_shape('MaleUnderwear_1')
    assert VNearEqual(armor.location, (-0.0003, -1.5475, 120.3436)), \
        f"Armor is raised to match body: {armor.location}"

    ObjectSelect([body, armor])
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nifout = NifFile(outfile)
    impnif = NifFile(testfile)  
    compare_shapes(impnif.shape_dict['MaleUnderwearBody:0'], nifout.shape_dict['MaleUnderwearBody:0'], body, e=0.01)
    compare_shapes(impnif.shape_dict['MaleUnderwear_1'], nifout.shape_dict['MaleUnderwear_1'], armor, e=0.01)

    check_unweighted_verts(nifout.shape_dict['MaleUnderwearBody:0'])
    check_unweighted_verts(nifout.shape_dict['MaleUnderwear_1'])
    assert NearEqual(body.location.z, 120.343582, 0.01), f"{body.name} in lifted position: {body.location.z}"
    assert NearEqual(armor.location.z, 120.343582, 0.01), f"{armor.name} in lifted position: {armor.location.z}"
    assert "NPC R Hand [RHnd]" not in bpy.data.objects, f"Did not create extra nodes representing the bones"
        

if TEST_BPY_ALL or TEST_IMP_EXP_FO4:
    test_title("TEST_IMP_EXP_FO4", "Can read the body nif and spit it back out")
    clear_all()

    testfile = test_file(r"tests\FO4\BTMaleBody.nif")
    outfile = test_file(r"tests/Out/TEST_IMP_EXP_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    impnif = NifFile(testfile)
    body = find_shape('BaseMaleBody:0')
    arma = body.parent
    bodyin = impnif.shape_dict['BaseMaleBody:0']

    assert not VNearEqual(body.location, [0, 0, 0], epsilon=1), f"Body is repositioned: {body.location}"
    assert arma.name == "Scene Root", f"Body parented to armature: {arma.name}"
    assert arma.data.bones['Pelvis_skin'].matrix_local.translation.z > 0, f"Bones translated above ground: {arma.data.bones['NPC Pelvis'].matrix_local.translation}"
    assert "Scene Root" not in arma.data.bones, "Did not import the root node"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nifout = NifFile(outfile)
    bodyout = nifout.shape_dict['BaseMaleBody:0']

    compare_shapes(bodyin, bodyout, body, e=0.001, ignore_translations=True)


if TEST_BPY_ALL or TEST_IMP_EXP_FO4_2:
    test_title("TEST_IMP_EXP_FO4_2", "Can read the body armor with 2 parts")
    clear_all()

    testfile = test_file(r"tests\FO4\Pack_UnderArmor_03_M.nif")
    outfile = test_file(r"tests/Out/TEST_IMP_EXP_FO4_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = find_shape('BaseMaleBody_03:0')
    armor = find_shape('Pack_UnderArmor_03_M:0')
    arma = body.parent
    assert body.location.z > 120, f"Body has correct transform: {body.location}"
    assert armor.location.z > 120, f"Armor has correct transform: {armor.location}"
    assert arma.data.bones['Neck'].matrix_local.translation.z > 100, \
        f"Neck has correct position: {arma.data.bones['Neck'].matrix_local.translation}"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    armor.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nifout = NifFile(outfile)
    bodyout = nifout.shape_dict['BaseMaleBody_03:0']
    armorout = nifout.shape_dict['Pack_UnderArmor_03_M:0']

    impnif = NifFile(testfile)
    bodyin = impnif.shape_dict['BaseMaleBody_03:0']
    armorin = impnif.shape_dict['Pack_UnderArmor_03_M:0']
    compare_shapes(bodyin, bodyout, body, e=0.001, ignore_translations=True)
    compare_shapes(armorin, armorout, armor, e=0.001, ignore_translations=True)


if TEST_BPY_ALL or TEST_ROUND_TRIP:
    # Test out basic import/export
    test_title("TEST_ROUND_TRIP", "Can do the full round trip: nif -> blender -> nif -> blender")
    clear_all()
    testfile = test_file("tests/Skyrim/test.nif")
    outfile1 = test_file("tests/Out/testSkyrim03.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    armor1 = bpy.data.objects["Armor"]
    assert int(armor1.location.z) == 120, "ERROR: Armor moved above origin by 120 to skinned position"
    maxz = max([v.co.z for v in armor1.data.vertices])
    minz = min([v.co.z for v in armor1.data.vertices])
    assert maxz < 0 and minz > -130, "Error: Vertices are positioned below origin"
    assert len(armor1.data.vertex_colors) == 0, "ERROR: Armor should have no colors"

    print("Exporting  to test file")
    bpy.ops.object.select_all(action='DESELECT')
    armor1.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile1, target_game='SKYRIM')
    assert os.path.exists(outfile1), "ERROR: Created output file"

    print("Re-importing exported file")
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=outfile1)

    armor2 = bpy.data.objects["Armor.001"]

    assert int(armor2.location.z) == 120, f"ERROR: Exported armor is re-imported with same position: {armor2.location}"
    maxz = max([v.co.z for v in armor2.data.vertices])
    minz = min([v.co.z for v in armor2.data.vertices])
    assert maxz < 0 and minz > -130, "Error: Vertices from exported armor are positioned below origin"


if TEST_BPY_ALL or TEST_BPY_PARENT_A:
    test_title("TEST_BPY_PARENT_A", 'Maintain armature structure')
    clear_all()
    testfile = test_file(r"tests\Skyrim\test.nif")
    
    # Can intuit structure if it's not in the file
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.data.objects["Scene Root"]
    assert obj.data.bones['NPC Hand.R'].parent.name == 'CME Forearm.R', f"Error: Should find forearm as parent: {obj.data.bones['NPC Hand.R'].parent.name}"
    print(f"Found parent to hand: {obj.data.bones['NPC Hand.R'].parent.name}")


if TEST_BPY_ALL or TEST_BPY_PARENT_B:
    test_title("TEST_BPY_PARENT_B", 'Maintain armature structure')
    clear_all()
    testfile2 = test_file(r"tests\FO4\bear_tshirt_turtleneck.nif")
    
    ## Can read structure if it comes from file
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    obj = bpy.data.objects["Scene Root"]
    assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
    assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3.R', "Error: Should find forearm as parent"


if TEST_BPY_ALL or TEST_RENAME:
    test_title("TEST_RENAME", "Test that NOT renaming bones works correctly")
    clear_all()
    testfile = test_file(r"tests\Skyrim\femalebody_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False)

    body = bpy.context.object
    vgnames = [x.name for x in body.vertex_groups]
    vgxl = list(filter(lambda x: ".L" in x or ".R" in x, vgnames))
    assert len(vgxl) == 0, f"Expected no vertex groups renamed, got {vgxl}"

    armnames = [b.name for b in body.parent.data.bones]
    armxl = list(filter(lambda x: ".L" in x or ".R" in x, armnames))
    assert len(armxl) == 0, f"Expected no bones renamed in armature, got {armxl}"


if TEST_BPY_ALL or TEST_CONNECTED_SKEL:
    # Check that the bones of the armature are connected correctly.
    test_title('TEST_CONNECTED_SKEL', 'Can import connected skeleton')
    clear_all()

    bpy.ops.object.select_all(action='DESELECT')
    testfile = test_file(r"tests\FO4\vanillaMaleBody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    s = bpy.data.objects[r"BASE meshes\Actors\Character\CharacterAssets\MaleBody.nif"]
    assert s.type == 'ARMATURE', f"Imported the skeleton {s}" 
    assert 'Leg_Thigh.L' in s.data.bones.keys(), "Error: Should have left thigh"
    lthigh = s.data.bones['Leg_Thigh.L']
    assert lthigh.parent.name == 'Pelvis', "Error: Thigh should connect to pelvis"
    assert VNearEqual(lthigh.head_local, (-6.6151, 0.0005, 68.9113)), f"Thigh head in correct location: {lthigh.head_local}"
    assert VNearEqual(lthigh.tail_local, (-7.2513, -0.1925, 63.9557)), f"Thigh tail in correct location: {lthigh.tail_local}"


if TEST_DRAUGR_IMPORT_A or TEST_BPY_ALL:
    # This nif uses the draugr skeleton, which has bones named like human bones but with
    # different positions--BUT the hood was made for the human skeleton so the bind
    # position of its bones don't match the draugr skeleton. Bones defined by the hood are
    # given the human bind position--the rest come from the reference skeleton and use
    # those bind positions. 
    test_title("TEST_DRAUGR_IMPORT1", "Import hood, extend skeleton, non-vanilla pose")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\SkyrimSE\draugr lich01 hood.nif")
    skelfile = test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = test_file(r"tests/Out/TEST_DRAUGR_IMPORT1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, create_bones=True)

    helm = find_shape("Helmet")
    hood = find_shape("Hood")
    skel = find_shape("Scene Root")
    bone1 = skel.data.bones['NPC UpperArm.R']
    pose1 = skel.pose.bones['NPC UpperArm.R']
    bone2 = skel.data.bones['NPC UpperarmTwist1.R']
    pose2 = skel.pose.bones['NPC UpperarmTwist1.R']

    # Bones referenced by the hood have bind position from humans but pose position from
    # draugr. The rest of them use bind and pose position from draugr.
    assert not MatNearEqual(bone1.matrix_local, bone2.matrix_local), \
        f"Bones should NOT have the same bind position: \n{bone1.matrix_local} != \n{bone2.matrix_local}"
    assert VNearEqual(pose1.matrix.translation, pose2.matrix.translation), \
        f"Bones should have same pose position: {pose1.matrix.translation} != {pose2.matrix.translation}"
    
    # Create_bones means that the bones are all connected up
    assert bone1.parent.name == 'NPC Clavicle.R', f"UpperArm parent correct: {bone1.parent.name}"
    assert bone2.parent.name == 'NPC UpperArm.R', f"UpperArmTwist parent correct: {bone2.parent.name}"
    

if TEST_DRAUGR_IMPORT_B or TEST_BPY_ALL:
    # This hood uses non-human bone node positions and we don't extend the skeleton, so
    # bones are given the bind position from the hood but the pose position from the nif.
    # Since the pose is not a pure translation, we do not put a transform on the hood
    # shape.
    test_title("TEST_DRAUGR_IMPORT_B", "Import hood, don't extend skeleton, non-vanilla pose")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\SkyrimSE\draugr lich01 hood.nif")
    skelfile = test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = test_file(r"tests/Out/TEST_DRAUGR_IMPORT_B.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, create_bones=False)

    helm = find_shape("Helmet")
    hood = find_shape("Hood")
    arma = find_shape("Scene Root")
    bone1 = arma.data.bones['NPC UpperarmTwist1.R']
    pose1 = arma.pose.bones['NPC UpperarmTwist1.R']

    # Lots of bones in this nif are not used in the hood. Bones used in the hood have pose
    # and bind locations. The rest only have pose locations and are brought in as Empties.
    assert not VNearEqual(pose1.matrix.translation, bone1.matrix_local.translation), \
        f"Pose position is not bind position: {pose1.matrix.translation} != {bone1.matrix_local.translation}"
    

if TEST_DRAUGR_IMPORT_C or TEST_BPY_ALL:
    # The helm has bones that are in the draugr's vanilla bind position.
    test_title("TEST_DRAUGR_IMPORT_C", "Import helm, don't extend skeleton")
    clear_all()

    testfile = test_file(r"tests\SkyrimSE\draugr lich01 helm.nif")
    skelfile = test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = test_file(r"tests/Out/TEST_DRAUGR_IMPORT_C.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, create_bones=False)

    helm = find_shape("Helmet")
    skel = find_shape("Scene Root")
    bone1 = skel.data.bones['NPC Head']
    pose1 = skel.pose.bones['NPC Head']

    assert not VNearEqual(bone1.matrix_local.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not in vanilla bind position: {bone1.matrix_local.translation}"
    assert not VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not posed in vanilla position: {pose1.matrix_local.translation}"


if TEST_DRAUGR_IMPORT_D or TEST_BPY_ALL:
    # Fo the helm, when we import WITH adding bones, we get a full draugr skeleton.
    test_title("TEST_DRAUGR_IMPORT_D", "Import helm, do extend skeleton")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\SkyrimSE\draugr lich01 helm.nif")
    skelfile = test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = test_file(r"tests/Out/TEST_DRAUGR_IMPORT_D.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, create_bones=True)

    helm = find_shape("Helmet")
    skel = find_shape("Scene Root")
    bone1 = skel.data.bones['NPC Head']
    pose1 = skel.pose.bones['NPC Head']
    bone2 = skel.data.bones['NPC Spine2']
    pose2 = skel.pose.bones['NPC Spine2']

    assert VNearEqual(bone1.matrix_local.translation, [-0.015854, -2.40295, 134.301]), \
        f"Head bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert not VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436], epsilon=2.0), \
        f"Head bone not posed in vanilla position: {pose1.matrix.translation}"

    assert VNearEqual(bone2.matrix_local.translation, [0.000004, -5.83516, 102.358]), \
        f"Spine bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert VNearEqual(pose2.matrix.translation, [0.0000, -5.8352, 102.3579]), \
        f"Spine bone posed in draugr position: {pose2.matrix.translation}"
    
    assert bone2.parent.name == 'NPC Spine1', \
        f"Spine bone has correct parent: {bone2.parent.name}"
    

if TEST_DRAUGR_IMPORT_E or TEST_BPY_ALL:
    # This nif has two shapes and the bind positions differ. The hood bind position is
    # human, and it's posed to the draugr position. The draugr hood is bound at pose
    # position, so pose and bind positions are the same. The only solution is to import as
    # two skeletons and let the user sort it out. We could also add a flag to "import at
    # pose position". We lose the bind position info but end up with the shapes parented
    # to one armature.
    test_title("TEST_DRAUGR_IMPORT_E", "Import of this draugr mesh positions hood correctly")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\SkyrimSE\draugr lich01 simple.nif")
    skelfile = test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = test_file(r"tests/Out/TEST_DRAUGR_IMPORT_E.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, create_bones=False)

    helm = find_shape("Helmet")
    hood = find_shape("Hood")
    importnif = NifFile(testfile)
    importhelm = importnif.shape_dict['Helmet']
    importhood = importnif.shape_dict['Hood']
    print(f"Helm max y = {max(v[1] for v in importnif.shape_dict['Helmet'].verts)}")

    # No matter what transforms we apply to Blender shapes or how the skinning moves 
    # them about, the vert locations should match the nif.
    assert_near_equal(max(v.co.x for v in helm.data.vertices), 
                      max(v[0] for v in importhelm.verts), "helm max x")
    assert_near_equal(min(v.co.x for v in helm.data.vertices), 
                      min(v[0] for v in importhelm.verts), "helm min x")
    assert_near_equal(max(v.co.y for v in helm.data.vertices), 
                      max(v[1] for v in importhelm.verts), "helm max y")
    assert_near_equal(min(v.co.y for v in helm.data.vertices), 
                      min(v[1] for v in importhelm.verts), "helm min y")
    assert_near_equal(max(v.co.z for v in helm.data.vertices), 
                      max(v[2] for v in importhelm.verts), "helm max z")
    assert_near_equal(min(v.co.z for v in helm.data.vertices), 
                      min(v[2] for v in importhelm.verts), "helm min z")
    
    assert_near_equal(max(v.co.x for v in hood.data.vertices), 
                      max(v[0] for v in importhood.verts), "hood max x")
    assert_near_equal(min(v.co.x for v in hood.data.vertices), 
                      min(v[0] for v in importhood.verts), "hood min x")
    assert_near_equal(max(v.co.y for v in hood.data.vertices), 
                      max(v[1] for v in importhood.verts), "hood max y")
    assert_near_equal(min(v.co.y for v in hood.data.vertices), 
                      min(v[1] for v in importhood.verts), "hood min y")
    assert_near_equal(max(v.co.z for v in hood.data.vertices), 
                      max(v[2] for v in importhood.verts), "hood max z")
    assert_near_equal(min(v.co.z for v in hood.data.vertices), 
                      min(v[2] for v in importhood.verts), "hood min z")
    
    skel = find_shape("Scene Root")
    headbone = skel.data.bones['NPC Head']
    headpose = skel.pose.bones['NPC Head']

    # Helm bounding box has to be contained within the hood's bounding box (in world space).
    helm_bb = get_obj_bbox(helm, worldspace=True)
    hood_bb = get_obj_bbox(hood, worldspace=True)
    assert_less_than(hood_bb[0][0], helm_bb[0][0], "min x")
    assert_greater_than(hood_bb[1][0], helm_bb[1][0], "max x")
    assert_less_than(hood_bb[0][1], helm_bb[0][1], "min y")
    assert_greater_than(hood_bb[1][1], helm_bb[1][1], "max y")
    assert_less_than(hood_bb[0][2], helm_bb[0][2], "min z")
    assert_greater_than(hood_bb[1][2], helm_bb[1][2], "max z")

    # Because the hood came from the human skeleton but the helm from draugr, the bone
    # positions don't match. They had to be brought in under separate armatures.
    assert helm.parent != hood.parent, f"Parents are different: {helm.parent} != {hood.parent}"

    # Not extending skeletons, so each armature just has the bones needed
    assert helm.parent.data.bones.keys() == ["NPC Head"], f"Helm armature has correct bones: {helm.parent.data.bones.keys()}"

    # Hood has pose location different from rest
    bone1 = hood.parent.data.bones['NPC Head']
    pose1 = hood.parent.pose.bones['NPC Head']

    assert not VNearEqual(bone1.matrix_local.translation, pose1.matrix.translation), \
        f"Pose and bind locaations differ: {bone1.matrix_local.translation} != {pose1.matrix.translation}"
    

if TEST_BPY_ALL or TEST_SCALING_BP:
    test_title("TEST_SCALING_BP", "Can scale bodyparts")
    clear_all()

    testfile = test_file(r"tests\Skyrim\malebody_1.nif")
    outfile = test_file(r"tests\Out\TEST_SCALING_BP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 rename_bones_niftools=True,
                                 scale_factor=0.1)

    arma = find_shape("MaleBody_1.nif")
    b = arma.data.bones['NPC Spine1 [Spn1]']
    assert NearEqual(b.matrix_local.translation.z, 8.1443), f"Scale correctly applied: {b.matrix_local.translation}"
    body = find_shape("MaleUnderwearBody:0")
    assert NearEqual(body.location.z, 12, 0.1), f"Object translation correctly applied: {body.location}"
    bodymax = max([v.co.z for v in body.data.vertices])
    bodymin = min([v.co.z for v in body.data.vertices])
    assert bodymax < 0, f"Max z is less than 0: {bodymax}"
    assert bodymin >= -12, f"Max z is greater than -12: {bodymin}"

    # Test export scaling is correct
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM", 
                                 rename_bones_niftools=True, scale_factor=0.1) \

    nifcheck = NifFile(outfile)
    bodycheck = nifcheck.shape_dict["MaleUnderwearBody:0"]
    assert NearEqual(bodycheck.transform.scale, 1.0), f"Scale is 1: {bodycheck.transform.scale}"
    assert NearEqual(bodycheck.transform.translation[2], 120.3, 0.1), \
        f"Translation is correct: {list(bodycheck.transform.translation)}"
    bmaxout = max(v[2] for v in bodycheck.verts)
    bminout = min(v[2] for v in bodycheck.verts)
    assert bmaxout-bminout > 100, f"Shape scaled up on ouput: {bminout}-{bmaxout}"


if TEST_BPY_ALL or TEST_IMP_EXP_SCALE_2:
    # Regression: Making sure that the scale factor doesn't mess up importing under one
    # armature.
    test_title("TEST_IMP_EXP_SCALE_2", "Can read the body nif scaled")
    clear_all()

    testfile = test_file(r"tests/Skyrim/malebody_1.nif")
    outfile = test_file(r"tests/Out/TEST_IMP_EXP_SCALE_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=0.1)

    assert len([x for x in bpy.data.objects if x.type=='ARMATURE']) == 1, \
        f"Both shapes brought in under one armor"
    body = find_shape('MaleUnderwearBody:0')
    armor = find_shape('MaleUnderwear_1')
    assert VNearEqual(armor.location, (-0.0, -0.15475, 12.03436)), \
        f"Armor is raised to match body: {armor.location}"
    
    
if TEST_BPY_ALL or TEST_ARMATURE_EXTEND:
    # Can import a shape with an armature and then import another shape to the same armature. 
    test_title("TEST_ARMATURE_EXTEND", "Can extend an armature with a second NIF")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\FO4\MaleBody.nif")
    testfile2 = test_file(r"tests\FO4\BaseMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    arma = bpy.data.objects[r"BASE meshes\Actors\Character\CharacterAssets\MaleBody.nif"]
    bpy.context.view_layer.objects.active = arma
    assert "SPINE1" in arma.data.bones, "Found neck bone in skeleton"
    assert not "HEAD" in arma.data.bones, "Did not find head bone in skeleton"
    assert "Leg_Calf.L" in arma.data.bones, f"Loaded bones not used by shape"
    assert arma.data.bones['SPINE2'].matrix_local.translation.z > 0, \
        f"Armature in basic position: {arma.data.bones['SPINE2'].matrix_local.translation}"

    # When we import a shape where the pose-to-bind transform is consistent, we use that 
    # transform on the blender shape for ease of editing. We can then import another body
    # part to the same armature.
    bpy.ops.object.select_all(action='DESELECT')
    arma.select_set(True)
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    assert not "BaseMaleHead.nif" in bpy.data.objects, "Head import did not create new skeleton"
    assert "HEAD" in arma.data.bones, "Found head bone in skeleton"

    head = find_shape("BaseMaleHead:0")
    body = find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = find_vertex(head.data, target_v)
    v_body = find_vertex(body.data, target_v)
    assert VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        f"Head and body verts align"
    assert MatNearEqual(head.matrix_world, body.matrix_world), f"Shape transforms match"


if TEST_BPY_ALL or TEST_ARMATURE_EXTEND_BT:
    # The Bodytalk body has bind positions consistent with vanilla, but the skin 
    # transform is different, which leaves a slight gap at the neck. For now, live 
    # with this.
    #  
    # The FO4 body nif does not use all bones from the skeleton, e.g. LLeg_Calf. If we're 
    # adding missing skeleton bones, we have to get them from the reference skeleton,
    # which pyNifly handles, and put them into the skeleton consistently with the rest.
    test_title("TEST_ARMATURE_EXTEND", "Can extend an armature with a second NIF")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\FO4\BTBaseMaleBody.nif")
    testfile2 = test_file(r"tests\FO4\BaseMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    arma = bpy.data.objects[r"Scene Root"]
    bpy.context.view_layer.objects.active = arma
    assert "SPINE1" in arma.data.bones, "Found neck bone in skeleton"
    assert not "HEAD" in arma.data.bones, "Did not find head bone in skeleton"
    assert "Leg_Calf.L" in arma.data.bones, f"Loaded bones not used by shape"
    assert arma.data.bones['SPINE2'].matrix_local.translation.z > 0, \
        f"Armature in basic position: {arma.data.bones['SPINE2'].matrix_local.translation}"

    bpy.ops.object.select_all(action='DESELECT')
    arma.select_set(True)
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    assert not "BaseMaleHead.nif" in bpy.data.objects, "Head import did not create new skeleton"
    assert "HEAD" in arma.data.bones, "Found head bone in skeleton"

    head = find_shape("BaseMaleHead:0")
    body = find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = find_vertex(head.data, target_v)
    v_body = find_vertex(body.data, target_v)
    assert VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        f"Head and body verts align"
    # Shape transforms are different between vanilla head and BT body.
    #assert MatNearEqual(head.matrix_world, body.matrix_world), f"Shape transforms match"


if TEST_BPY_ALL or TEST_EXPORT_WEIGHTS:
    # Simple test to see that when vertex groups are associated with bone weights they are
    # written correctly.
    # 
    # Also check that when we have multiple objects under a skeleton and only select one,
    # only that one gets written. 
    test_title("TEST_EXPORT_WEIGHTS", "Import and export with weights")
    clear_all()
    testfile = test_file(r"tests\Skyrim\test.nif")
    filepath_armor = test_file("tests/out/testArmorSkyrim02.nif")
    filepath_armor_fo = test_file(r"tests\Out\testArmorFO02.nif")
    filepath_body = test_file(r"tests\Out\testBodySkyrim02.nif")

    # Import body and armor
    bpy.ops.import_scene.pynifly(filepath=testfile)
    the_armor = bpy.data.objects["Armor"]
    the_body = bpy.data.objects["MaleBody"]
    assert 'NPC Foot.L' in the_armor.vertex_groups, f"ERROR: Left foot is in the groups: {the_armor.vertex_groups}"
    
    # Export armor
    bpy.ops.object.select_all(action='DESELECT')
    the_armor.select_set(True)
    bpy.context.view_layer.objects.active = the_armor
    bpy.ops.export_scene.pynifly(filepath=filepath_armor, target_game='SKYRIM')
    assert os.path.exists(filepath_armor), "ERROR: File not created"

    # Check armor
    ftest = NifFile(filepath_armor)
    assert len(ftest.shapes) == 1, f"Wrote one shape: {ftest.shape_dict.keys()}"
    assert ftest.shapes[0].name[0:5] == "Armor", "ERROR: Armor not read"
    gts = ftest.shapes[0].global_to_skin
    assert int(gts.translation[2]) == -120, f"ERROR: Armor offset not correct: {gts.translation[2]}"

    # Write armor to FO4 (wrong skeleton but whatevs, just see that it doesn't crash)
    bpy.ops.export_scene.pynifly(filepath=filepath_armor_fo, target_game='FO4')
    assert os.path.exists(filepath_armor_fo), f"ERROR: File {filepath_armor_fo} not created"

    # Write body 
    bpy.ops.object.select_all(action='DESELECT')
    the_body.select_set(True)
    bpy.context.view_layer.objects.active = the_body
    bpy.ops.export_scene.pynifly(filepath=filepath_body, target_game='SKYRIM')
    assert os.path.exists(filepath_body), f"ERROR: File {filepath_body} not created"
    bnif = NifFile(filepath_body)
    assert len(bnif.shapes) == 1, f"Wrote one shape: {bnif.shape_dict.keys()}"


if TEST_BPY_ALL or TEST_WEIGHTS_EXPORT:
    test_title("TEST_WEIGHTS_EXPORT", "Exporting this head weights all verts correctly")
    clear_all()
    outfile = test_file(r"tests/Out/TEST_WEIGHTS_EXPORT.nif")

    head = append_from_file("CheetahFemaleHead", True, r"tests\FO4\CheetahHead.blend", 
                            r"\Object", "CheetahFemaleHead")
    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # ------- Check ---------
    nifcheck = NifFile(outfile)

    headcheck = nifcheck.shape_dict["CheetahFemaleHead"]
    bw = headcheck.bone_weights
    for vert_index, v in enumerate(headcheck.verts):
        weightfound = False
        for bn in headcheck.get_used_bones():
            index_list = [p[0] for p in bw[bn]]
            weightfound |= (vert_index in index_list)
        assert weightfound, f"Weight not found for vert #{vert_index}"


if TEST_BPY_ALL or TEST_0_WEIGHTS:
    test_title("TEST_0_WEIGHTS", "Gives warning on export with 0 weights")
    clear_all()
    testfile = test_file(r"tests\Out\weight0.nif")

    baby = append_from_file("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
    baby.parent.name == "BabyExportRoot", f"Error: Should have baby and armature"
    log.debug(f"Found object {baby.name}")
    try:
        bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")
    except RuntimeError:
        print("Caught expected runtime error")
    assert UNWEIGHTED_VERTEX_GROUP in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


if TEST_BPY_ALL or TEST_TIGER_EXPORT:
    test_title("TEST_TIGER_EXPORT", "Tiger head exports without errors")
    clear_all()
    f = test_file(r"tests/Out/TEST_TIGER_EXPORT.nif")
    fb = test_file(r"tests/Out/TEST_TIGER_EXPORT_faceBones.nif")
    ftri = test_file(r"tests/Out/TEST_TIGER_EXPORT.tri")
    fchargen = test_file(r"tests/Out/TEST_TIGER_EXPORT_chargen.tri")

    append_from_file("TigerMaleHead", True, r"tests\FO4\Tiger.blend", r"\Object", "TigerMaleHead")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["TigerMaleHead"].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects["TigerMaleHead"]
    bpy.ops.export_scene.pynifly(filepath=f, target_game='FO4', chargen_ext="_chargen")

    nif1 = NifFile(f)
    assert len(nif1.shapes) == 1, f"Expected tiger nif"
    assert os.path.exists(fb), "Facebones file created"
    assert os.path.exists(ftri), "Tri file created"
    assert os.path.exists(fchargen), "Chargen file created"


if TEST_BPY_ALL or TEST_3BBB:
    test_title("TEST_3BBB", "Test that this mesh imports with the right transforms")
    clear_all()

    testfile = test_file(r"tests/SkyrimSE/3BBB_femalebody_1.nif")
    testfile2 = test_file(r"tests/SkyrimSE/3BBB_femalehands_1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    obj = bpy.context.object
    assert NearEqual(obj.location[0], 0.0), f"Expected body to be centered on x-axis, got {obj.location}"

    print("## Test that the same armature is used for the next import")
    arma = bpy.data.objects['Scene Root']
    bpy.ops.object.select_all(action='DESELECT')
    arma.select_set(True)
    bpy.context.view_layer.objects.active = arma
    bpy.ops.import_scene.pynifly(filepath=testfile2)

    arma2 = bpy.context.object.parent
    assert arma2.name == arma.name, f"Should have parented to same armature: {arma2.name} != {arma.name}"


if TEST_BPY_ALL or TEST_SKEL:
    test_title("TEST_SKEL", "Can import skeleton file with no shapes")
    clear_all()
    testfile = test_file(r"skeletons\FO4\skeleton.nif")
    outfile = test_file(r"tests/out/TEST_SKEL.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    arma = bpy.data.objects["skeleton.nif"]
    assert 'Leg_Thigh.L' in arma.data.bones, "Have left thigh bone"
    assert 'RibHelper.L' in arma.data.bones, "Have rib helper bone"
    assert 'L_RibHelper.L' not in arma.data.bones, "Do not have nif name for bone"
    assert 'L_RibHelper' not in bpy.data.objects, "Do not have rib helper object"
    assert arma.data.bones['RibHelper.L'].parent.name == 'Chest', \
        f"Parent of ribhelper is chest: {arma.data.bones['RibHelper.L'].parent.name}"

    cp_lleg = bpy.data.objects['BSConnectPointParents::P-ArmorLleg']
    assert cp_lleg.parent == arma, f"cp_lleg has armature as parent: {cp_lleg.parent}"
    assert NearEqual(cp_lleg.location[0], 4.91351), \
        f"Armor left leg connect point at relative position: {cp_lleg.location}"

    bpy.data.objects['skeleton.nif'].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    skel_in = NifFile(testfile)
    skel_out = NifFile(outfile)
    assert "L_RibHelper" in skel_out.nodes, "Bones written to nif"
    pb = skel_out.nodes["L_RibHelper"].parent
    assert pb.name == "Chest", f"Have correct parent: {pb.name}"
    helm_cp_in = [x for x in skel_in.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
    helm_cp_out = [x for x in skel_out.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
    assert helm_cp_out.parent.decode('utf-8') == 'HEAD', f"Parent is correct: {helm_cp_out.parent}"
    assert VNearEqual(helm_cp_in.translation, helm_cp_out.translation), \
        f"Connect point locations correct: {helm_cp_in.translation[:]} == {helm_cp_out.translation[:]}"


if TEST_BPY_ALL or TEST_HEADPART:
    # Tri files can be loaded up into a shape in blender as shape keys. On SE, when there
    # are shape keys a BSDynamicTriShape is used on export.
    test_title("TEST_HEADPART", "Can read & write an SE head part")
    clear_all()
    testfile = test_file(r"tests/SKYRIMSE/malehead.nif")
    testtri = test_file(r"tests/SKYRIMSE/malehead.tri")
    testfileout = test_file(r"tests/out/TEST_HEADPART.nif")
    testfileout2 = test_file(r"tests/out/TEST_HEADPART2.nif")
    testfileout3 = test_file(r"tests/out/TEST_HEADPART3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    bpy.ops.import_scene.pyniflytri(filepath=testtri)

    assert len(obj.data.shape_keys.key_blocks) == 45, f"Expected key blocks 45 != {len(obj.data.shape_keys.key_blocks)}"
    assert obj.data.shape_keys.key_blocks[0].name == "Basis", f"Expected first key 'Basis' != {obj.data.shape_keys.key_blocks[0].name}"

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game='SKYRIMSE')
    
    nif2 = NifFile(testfileout)
    head2 = nif2.shapes[0]
    assert len(nif2.shapes) == 1, f"Expected single shape, 1 != {len(nif2.shapes)}"
    assert head2.blockname == "BSDynamicTriShape", f"Expected 'BSDynamicTriShape' != '{nif2.shapes[0].blockname}'"

    # We can export whatever shape is defined by the shape keys.
    obj.data.shape_keys.key_blocks['Blink.L'].value = 1
    obj.data.shape_keys.key_blocks['MoodHappy'].value = 1
    bpy.ops.export_scene.pynifly(filepath=testfileout2, target_game='SKYRIMSE', 
                                 export_modifiers=True)
    
    nif3 = NifFile(testfileout2)
    head3 = nif3.shapes[0]
    eyelid = find_vertex(obj.data, [-2.52558, 7.31011, 124.389])
    mouth = find_vertex(obj.data, [1.8877, 7.50949, 118.859])
    assert not VNearEqual(head2.verts[eyelid], head3.verts[eyelid]), \
        f"Verts have moved: {head2.verts[eyelid]} != {head3.verts[eyelid]}"
    assert not VNearEqual(head2.verts[mouth], head3.verts[mouth]), \
        f"Verts have moved: {head2.verts[mouth]} != {head3.verts[mouth]}"

    # We can export any modifiers
    obj.data.shape_keys.key_blocks['Blink.L'].value = 0
    obj.data.shape_keys.key_blocks['MoodHappy'].value = 0
    mod = obj.modifiers.new("Decimate", 'DECIMATE')
    mod.ratio = 0.2
    bpy.ops.export_scene.pynifly(filepath=testfileout3, target_game='SKYRIMSE', 
                                 export_modifiers=True)
    nif4 = NifFile(testfileout3)
    head4 = nif4.shapes[0]
    assert len(head4.verts) < 300, f"Head has decimated verts: {head4.verts}"


if TEST_BPY_ALL or TEST_TRI:
    test_title("TEST_TRI", "Can load a tri file into an existing mesh")
    clear_all()

    testfile = test_file(r"tests\FO4\CheetahMaleHead.nif")
    testtri2 = test_file(r"tests\FO4\CheetahMaleHead.tri")
    testtri3 = test_file(r"tests\FO4\CheetahMaleHead.tri")
    testout2 = test_file(r"tests\Out\CheetahMaleHead02.nif")
    testout2tri = test_file(r"tests\Out\CheetahMaleHead02.tri")
    testout2chg = test_file(r"tests\Out\CheetahMaleHead02chargen.tri")
    tricubenif = test_file(r"tests\Out\tricube01.nif")
    tricubeniftri = test_file(r"tests\Out\tricube01.tri")
    tricubenifchg = test_file(r"tests\Out\tricube01chargen.tri")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    if obj.type == "ARMATURE":
        obj = obj.children[0]
        bpy.context.view_layer.objects.active = obj

    log.debug(f"Importing tri with {bpy.context.object.name} selected")
    bpy.ops.import_scene.pyniflytri(filepath=testtri2)

    assert len(obj.data.shape_keys.key_blocks) >= 47, f"Error: {obj.name} should have enough keys ({obj.data.shape_keys.key_blocks.keys()})"

    print("### Can import a simple tri file as its own object")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None
    bpy.ops.import_scene.pyniflytri(filepath=testtri3)
    triobj = bpy.context.object
    assert triobj.name.startswith("CheetahMaleHead.tri"), f"Error: Should be named like tri file, found {triobj.name}"
    assert "LJaw" in triobj.data.shape_keys.key_blocks.keys(), "Error: Should be no keys missing"
    
    print('### Can export a shape with tris')

    bpy.ops.export_scene.pynifly(filepath=testout2, target_game="FO4")
    
    print('### Exported shape and tri match')
    nif2 = NifFile(os.path.join(pynifly_dev_path, testout2))
    tri2 = TriFile.from_file(os.path.join(pynifly_dev_path, testout2tri))
    assert not os.path.exists(testout2chg), f"{testout2chg} should not have been created"
    assert len(nif2.shapes[0].verts) == len(tri2.vertices), f"Error vert count should match, {len(nif2.shapes[0].verts)} vs {len(tri2.vertices)}"
    assert len(nif2.shapes[0].tris) == len(tri2.faces), f"Error vert count should match, {len(nif2.shapes[0].tris)} vs {len(tri2.faces)}"
    assert tri2.header.morphNum == len(triobj.data.shape_keys.key_blocks)-1, \
        f"Error: morph count should match, file={tri2.header.morphNum} vs {triobj.name}={len(triobj.data.shape_keys.key_blocks)}"
    
    print('### Tri and chargen export as expected')

    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TriCube"
    sk1 = cube.shape_key_add()
    sk1.name = "Aah"
    sk2 = cube.shape_key_add()
    sk2.name = "CombatAnger"
    sk3 = cube.shape_key_add()
    sk3.name = "*Extra"
    sk4 = cube.shape_key_add()
    sk4.name = "BrowIn"
    bpy.ops.export_scene.pynifly(filepath=tricubenif, target_game='SKYRIM')

    assert os.path.exists(tricubenif), f"Error: Should have exported {tricubenif}"
    assert os.path.exists(tricubeniftri), f"Error: Should have exported {tricubeniftri}"
    assert os.path.exists(tricubenifchg), f"Error: Should have exported {tricubenifchg}"
    
    cubetri = TriFile.from_file(tricubeniftri)
    assert "Aah" in cubetri.morphs, f"Error: 'Aah' should be in tri"
    assert "BrowIn" not in cubetri.morphs, f"Error: 'BrowIn' should not be in tri"
    assert "*Extra" not in cubetri.morphs, f"Error: '*Extra' should not be in tri"
    
    cubechg = TriFile.from_file(tricubenifchg)
    assert "Aah" not in cubechg.morphs, f"Error: 'Aah' should not be in chargen"
    assert "BrowIn" in cubechg.morphs, f"Error: 'BrowIn' should be in chargen"
    assert "*Extra" not in cubechg.morphs, f"Error: '*Extra' should not be in chargen"
    

if TEST_BPY_ALL or TEST_IMPORT_AS_SHAPES:
    # When two files are selected for import, they are imported as shape keys if possible.
    test_title("TEST_IMPORT_AS_SHAPES", "Can import 2 meshes as shape keys")
    clear_all()

    testfiles = [{"name": test_file(r"tests\SkyrimSE\body1m_0.nif")}, 
                 {"name": test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 2, f"Have 2 meshes: {meshes}"
    sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
    assert set(sknames0) == set(['Basis', '_0', '_1']), f"Shape keys are named correctly: {sknames0}"
    sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
    assert set(sknames1) == set(['Basis', '_0', '_1']), f"Shape keys are named correctly: {sknames1}"
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    assert len(armatures) == 1, f"Have 1 armature: {armatures}"


if TEST_BPY_ALL or TEST_IMPORT_MULT_SHAPES:
    # When multiple files are selected for a single import, they are connected up as 
    # shape keys if possible.
    test_title("TEST_IMPORT_MULT_SHAPES", "Can import >2 meshes as shape keys")
    clear_all()

    testfiles = [{"name": test_file(r"tests\FO4\PoliceGlasses\Glasses_Cat.nif")}, 
                    {"name": test_file(r"tests\FO4\PoliceGlasses\Glasses_CatF.nif")}, 
                    {"name": test_file(r"tests\FO4\PoliceGlasses\Glasses_Horse.nif")}, 
                    {"name": test_file(r"tests\FO4\PoliceGlasses\Glasses_Hyena.nif")}, 
                    {"name": test_file(r"tests\FO4\PoliceGlasses\Glasses_LionLyk.nif")}, 
                    ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 2, f"Have 2 meshes: {meshes}"
    sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
    assert set(sknames0) == set(['Basis', '_Cat', '_CatF', '_Horse', '_Hyena', '_LionLyk']), f"Shape keys are named correctly: {sknames0}"
    sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
    assert set(sknames1) == set(['Basis', '_Cat', '_CatF', '_Horse', '_Hyena', '_LionLyk']), f"Shape keys are named correctly: {sknames1}"
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    assert len(armatures) == 1, f"Have 1 armature: {armatures}"


if (TEST_BPY_ALL or TEST_EXP_SK_RENAMED) and bpy.app.version[0] >= 3:
    # The export/import process can change left/right shape keys to better match Blender's
    # naming conventions.
    #
    # Doesn't work on 2.x. Not sure why.
    test_title("TEST_EXP_SK_RENAMED", "Ensure renamed shape keys export properly")
    clear_all()
    outfile = test_file(r"tests/Out/TEST_EXP_SK_RENAMED.nif")
    trifile = test_file(r"tests/Out/TEST_EXP_SK_RENAMED.tri")
    chargenfile = test_file(r"tests/Out/TEST_EXP_SK_RENAMEDchargen.tri")

    append_from_file("BaseFemaleHead:0", True, r"tests\FO4\FemaleHead.blend", 
                     r"\Object", "BaseFemaleHead:0")

    head = bpy.data.objects["BaseFemaleHead:0"]
    initial_keys = set(head.data.shape_keys.key_blocks.keys())

    NifFile.clear_log()
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = bpy.data.objects["BaseFemaleHead:0"]
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert "ERROR" not in NifFile.message_log(), f"Error: Expected no error message, got: \n{NifFile.message_log()}---\n"

    assert not os.path.exists(chargenfile), f"Chargen file not created: {os.path.exists(chargenfile)}"

    nif1 = NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected head nif"

    tri1 = TriFile.from_file(trifile)
    new_keys = set()
    d = gameSkeletons["FO4"]
    for m in tri1.morphs.keys():
        if m in d.morph_dic_blender:
            new_keys.add(d.morph_dic_blender[m])
        else:
            new_keys.add(m)

    assert new_keys == initial_keys, f"Got same keys back as written: {new_keys - initial_keys} / {initial_keys - new_keys}"
    assert len(tri1.morphs) == 51, f"Expected 51 morphs, got {len(tri1.morphs)} morphs: {tri1.morphs.keys()}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=outfile)
    obj = bpy.context.object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)

    bpy.ops.import_scene.pyniflytri(filepath=trifile)

    assert len(obj.data.shape_keys.key_blocks) == 51, f"Expected key blocks 51 != {len(obj.data.shape_keys.key_blocks)}"
    assert 'Smile.L' in obj.data.shape_keys.key_blocks, f"Expected key 'Smile.L' in {obj.data.shape_keys.key_blocks.keys()}"


if TEST_BPY_ALL or TEST_SK_MULT:
    test_title("TEST_SK_MULT", "Export multiple objects with only some shape keys")

    clear_all()
    outfile = test_file(r"tests/Out/TEST_SK_MULT.nif")
    outfile0 = test_file(r"tests/Out/TEST_SK_MULT_0.nif")
    outfile1 = test_file(r"tests/Out/TEST_SK_MULT_1.nif")

    append_from_file("CheMaleMane", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "CheMaleMane")
    append_from_file("MaleTail", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "MaleTail")
    bpy.context.view_layer.objects.active = bpy.data.objects["CheMaleMane"]
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["CheMaleMane"].select_set(True)
    bpy.data.objects["MaleTail"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    nif1 = NifFile(outfile1)
    assert len(nif1.shapes) == 2, "Wrote the 1 file successfully"
    assert 'NPC Spine2 [Spn2]' in nif1.nodes, "Found spine2 bone"
    assert 'TailBone01' in nif1.nodes, "Found Tailbone01"
    assert 'NPC L Clavicle [LClv]' in nif1.nodes, "Found Clavicle"

    nif0 = NifFile(outfile0)
    assert len(nif0.shapes) == 2, "Wrote the 0 file successfully"
    assert 'NPC Spine2 [Spn2]' in nif0.nodes, "Found Spine2 in _0 file"
    assert 'TailBone01' in nif0.nodes, "Found tailbone01 in _0 file"
    assert 'NPC L Clavicle [LClv]' in nif0.nodes, "Found clavicle in _0 file"


if TEST_BPY_ALL or TEST_TRI2:
    test_title("TEST_TRI2", "Regression: Test correct improt of tri")    
    clear_all()
    testfile = test_file(r"tests/Skyrim/OtterMaleHead.nif")
    trifile = test_file(r"tests/Skyrim/OtterMaleHeadChargen.tri")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    bpy.ops.import_scene.pyniflytri(filepath=trifile)

    v1 = obj.data.shape_keys.key_blocks['VampireMorph'].data[1]
    assert v1.co[0] <= 30, "Shape keys not relative to current mesh"


if TEST_BPY_ALL or TEST_BAD_TRI:
    # Tri files have UVs in them, but it's mostly not used, and some tris have messed up
    # UVs. Make sure they can be read anyway.
    test_title("TEST_BAD_TRI", "Tris with messed up UVs can be imported")
    clear_all()

    testfile = test_file(r"tests/Skyrim/bad_tri.tri")
    testfile2 = test_file(r"tests/Skyrim/bad_tri_2.tri")
    
    bpy.ops.import_scene.pyniflytri(filepath=testfile)
    obj = bpy.context.object
    assert len(obj.data.vertices) == 6711, f"Expected 6711 vertices, found {len(obj.data.vertices)}"

    bpy.ops.import_scene.pyniflytri(filepath=testfile2)
    obj2 = bpy.context.object
    assert len(obj2.data.vertices) == 11254, f"Expected 11254 vertices, found {len(obj2.data.vertices)}"


if TEST_BPY_ALL or TEST_SEGMENTS:
    test_title("TEST_SEGMENTS", "Can read FO4 segments")
    clear_all()

    testfile = test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = test_file(r"tests/Out/TEST_SEGMENTS.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert "FO4 Seg 003" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names: 'FO4 Seg 003'"
    assert "FO4 Seg 004 | 000 | Up Arm.L" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names: 'FO4 Seg 004 | 000 | Up Arm.L'"
    assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "Should have FO4 segment file read and saved for later use"

    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    
    nif2 = NifFile(outfile)
    assert len(nif2.shapes[0].partitions) == 7, "Wrote the shape's 7 partitions"
    assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == nif2.shapes[0].segment_file, f"Nif should reference segment file, found '{nif2.shapes[0].segment_file}'"


if TEST_ALL or TEST_BP_SEGMENTS:
    test_title("TEST_BP_SEGMENTS", "Can read FO4 bodypart segments")
    clear_all()

    testfile = test_file(r"tests/FO4/Helmet.nif")
    outfile = test_file(r"tests/Out/TEST_BP_SEGMENTS.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    helmet = bpy.data.objects['Helmet:0']
    visor = bpy.data.objects['glass:0']
    assert helmet.name == "Helmet:0", "Read the helmet object"
    assert "FO4 Seg 001 | Hair Top | Head" in helmet.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
    assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == helmet['FO4_SEGMENT_FILE'], "FO4 segment file read and saved for later use"

    assert visor.name == "glass:0", "Read the visor object"
    assert "FO4 Seg 001 | Hair Top" in visor.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"

    print("### Can write FO4 segments")
    bpy.ops.object.select_all(action='SELECT')
    e = bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    
    nif2 = NifFile(outfile)
    helm2 = nif2.shape_dict["Helmet:0"]
    assert helm2.name == "Helmet:0", "Have the helmet in the nif file"
    assert len(helm2.partitions) == 2, "Have all FO4 partitions"
    ss30 = None
    for p in helm2.partitions:
        for s in p.subsegments:
            if s.user_slot == 30:
                ss30 = s
                break
    assert ss30 is not None, "Mesh has FO4Subsegment 30"
    assert ss30.material == 0x86b72980, "FO4Subsegment 30 should have correct material"
    assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == nif2.shapes[0].segment_file, "Nif references segment file"

    visor2 = nif2.shape_dict["glass:0"]
    assert visor2.name == "glass:0", "Have the visor in the nif file"
    assert len(helm2.partitions) == 2, "Visor has all FO4 partitions"
    assert visor2.partitions[1].subsegments[0].user_slot == 30, "Visor has subsegment 30"


if TEST_BPY_ALL or TEST_EXP_SEGMENTS_BAD:
    # Game can get crashy if there are a bunch of empty segments at the end of the list.
    test_title("TEST_EXP_SEGMENTS_BAD", "Verts export in the correct segments")
    clear_all()

    outfile = test_file(r"tests/Out/TEST_EXP_SEGMENTS_BAD.nif")

    append_from_file("ArmorUnder", True, r"tests\FO4\ArmorExportsBadSegments.blend", r"\Object", "ArmorUnder")

    NifFile.clear_log()
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert "ERROR" not in NifFile.message_log(), f"Error: Expected no error message, got: \n{NifFile.message_log()}---\n"

    nif1 = NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Single shape was exported"

    body = nif1.shapes[0]
    assert len(body.partitions) >= 4, "All important segments exported"
    assert len(body.partitions[3].subsegments) == 0, "4th partition (body) has no subsegments"
    assert len([x for x in body.partition_tris if x == 3]) == len(body.tris), f"All tris in the 4th partition--found {len([x for x in body.partition_tris if x == 3])}"
    assert len([x for x in body.partition_tris if x != 3]) == 0, f"Regression: No tris in the last partition (or any other)--found {len([x for x in body.partition_tris if x != 3])}"


if (TEST_BPY_ALL or TEST_EXP_SEG_ORDER) and bpy.app.version[0] >= 3:
    # Order matters for the segments, so make sure it's right.
    test_title("TEST_EXP_SEG_ORDER", "Segments export in numerical order")
    outfile = test_file(r"tests/Out/TEST_EXP_SEG_ORDER.nif")
    clear_all()

    gen1bod = append_from_file("SynthGen1Body", True, r"tests\FO4\SynthGen1BodyTest.blend", r"\Object", "SynthGen1Body")

    obj = bpy.data.objects["SynthGen1Body"]
    groups = [g for g in obj.vertex_groups if g.name.startswith('FO4')]
    assert len(groups) == 23, f"Groups properly appended from test file: {len(groups)}"

    NifFile.clear_log()
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = gen1bod
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert "ERROR" not in NifFile.message_log(), f"Error: Expected no error message, got: \n{NifFile.message_log()}---\n"

    nif1 = NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Single shape was exported"

    # Third segment should be arm, with 5 subsegments
    body = nif1.shapes[0]
    assert len(body.partitions[2].subsegments) == 5, f"Right arm has 5 subsegments, found {len(body.partitions[2].subsegments)}"
    assert body.partitions[2].subsegments[0].material == 0xb2e2764f, "First subsegment is the upper right arm material"
    assert len(body.partitions[3].subsegments) == 0, "Torso has no subsegments"


if TEST_BPY_ALL or TEST_PARTITIONS:
    test_title("TEST_PARTITIONS", "Can read Skyrim partions")
    clear_all()
    testfile = test_file(r"tests/Skyrim/MaleHead.nif")
    outfile = test_file(r"tests/Out/TEST_PARTITIONS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert "SBP_130_HEAD" in obj.vertex_groups, "Skyrim body parts read in as vertex groups with sensible names"

    print("### Can write Skyrim partitions")
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nif2 = NifFile(outfile)
    head = nif2.shapes[0]
    assert len(nif2.shapes[0].partitions) == 3, "Have all skyrim partitions"
    assert set([p.id for p in head.partitions]) == set([130, 143, 230]), "Have all head parts"


if TEST_BPY_ALL or TEST_SHADER_LE:
    test_title("TEST_SHADER_LE", "Shader attributes are read and turned into Blender shader nodes")
    clear_all()

    fileLE = test_file(r"tests\Skyrim\meshes\actors\character\character assets\malehead.nif")
    outfile = test_file(r"tests/Out/TEST_SHADER_LE.nif")
    bpy.ops.import_scene.pynifly(filepath=fileLE)

    nifLE = NifFile(fileLE)
    shaderAttrsLE = nifLE.shapes[0].shader_attributes
    headLE = bpy.context.object
    shadernodes = headLE.active_material.node_tree.nodes
    assert 'Principled BSDF' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    assert 'Image Texture' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    assert 'Normal Map' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    g = shadernodes['Principled BSDF'].inputs['Metallic'].default_value
    assert round(g, 4) == 33/GLOSS_SCALE, f"Glossiness not correct, value is {g}"
    assert headLE.active_material['BSShaderTextureSet_2'] == r"textures\actors\character\male\MaleHead_sk.dds", f"Expected stashed texture path, found {headLE.active_material['BSShaderTextureSet_2']}"

    print("## Shader attributes are written on export")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifcheckLE = NifFile(outfile)
    
    assert nifcheckLE.shapes[0].textures[0].lower() == nifLE.shapes[0].textures[0].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[0]}' != '{nifLE.shapes[0].textures[0]}'"
    assert nifcheckLE.shapes[0].textures[1].lower() == nifLE.shapes[0].textures[1].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[1]}' != '{nifLE.shapes[0].textures[1]}'"
    assert nifcheckLE.shapes[0].textures[2].lower() == nifLE.shapes[0].textures[2].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[2]}' != '{nifLE.shapes[0].textures[2]}'"
    assert nifcheckLE.shapes[0].textures[7].lower() == nifLE.shapes[0].textures[7].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[7]}' != '{nifLE.shapes[0].textures[7]}'"
    assert nifcheckLE.shapes[0].shader_attributes == shaderAttrsLE, f"Error: Shader attributes not preserved:\n{nifcheckLE.shapes[0].shader_attributes}\nvs\n{shaderAttrsLE}"


if TEST_BPY_ALL or TEST_SHADER_SE:
    # Basic test of texture paths on shaders.
    test_title("TEST_SHADER_SE", "Shader attributes are read and turned into Blender shader nodes")
    clear_all()

    fileSE = test_file(r"tests\skyrimse\meshes\armor\dwarven\dwarvenboots_envscale.nif")
    outfile = test_file(r"tests/Out/TEST_SHADER_SE.nif")
    
    bpy.ops.import_scene.pynifly(filepath=fileSE)
    nifSE = NifFile(fileSE)
    nifboots = nifSE.shapes[0]
    shaderAttrsSE = nifboots.shader_attributes
    boots = bpy.context.object
    shadernodes = boots.active_material.node_tree.nodes
    assert len(shadernodes) >= 5, "ERROR: Didn't import shader nodes"
    shader = shadernodes['Principled BSDF']
    assert boots.active_material['Env_Map_Scale'] == shaderAttrsSE.Env_Map_Scale, \
        f"Read the correct environment map scale: {boots.active_material['Env_Map_Scale']}"
    assert not shader.inputs['Alpha'].is_linked, f"No alpha property"

    print("## Shader attributes are written on export")
    bpy.ops.object.select_all(action='DESELECT')
    boots.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = NifFile(outfile)
    bootcheck = nifcheckSE.shapes[0]
    
    assert bootcheck.textures[0].lower() == nifboots.textures[0].lower(), \
        f"Error: Texture paths not preserved: '{bootcheck.textures[0]}' != '{nifboots.textures[0]}'"
    assert bootcheck.textures[1].lower() == nifboots.textures[1].lower(), \
        f"Error: Texture paths not preserved: '{bootcheck.textures[1]}' != '{nifboots.textures[1]}'"
    assert bootcheck.textures[2].lower() == nifboots.textures[2].lower(), \
        f"Error: Texture paths not preserved: '{bootcheck.textures[2]}' != '{nifboots.textures[2]}'"
    assert bootcheck.textures[4] == nifboots.textures[4], \
        f"Error: Texture paths not preserved: '{bootcheck.textures[4]}' != '{nifboots.textures[4]}'"
    assert bootcheck.textures[7].lower() == nifboots.textures[7].lower(), \
        f"Error: Texture paths not preserved: '{bootcheck.textures[7]}' != '{nifboots.textures[7]}'"
    assert bootcheck.shader_attributes.Env_Map_Scale == shaderAttrsSE.Env_Map_Scale, \
        f"Error: Shader attributes not preserved:\n{bootcheck.shader_attributes}\nvs\n{shaderAttrsSE}"
    assert not bootcheck.has_alpha_property, "Boots have no alpha"
    assert bootcheck.shader_attributes.Env_Map_Scale == shaderAttrsSE.Env_Map_Scale, \
        f"Environment map scale written correctly: {bootcheck.shader_attributes.Env_Map_Scale}"


if TEST_BPY_ALL or TEST_SHADER_FO4:
    test_title("TEST_SHADER_FO4", "Shader attributes are read and turned into Blender shader nodes")
    clear_all()
    fileFO4 = test_file(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\basemalehead.nif")
    outfile = test_file(r"tests/Out/TEST_SHADER_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=fileFO4)
    headFO4 = bpy.context.object
    
    nifFO4 = NifFile(fileFO4)
    shaderAttrsFO4 = nifFO4.shapes[0].shader_attributes
    sh = headFO4.active_material.node_tree.nodes["Principled BSDF"]
    assert sh, "Have shader node"
    txt = headFO4.active_material.node_tree.nodes["Image Texture"]
    assert txt and txt.image and txt.image.filepath, "ERROR: Didn't import images"

    print("## Shader attributes are written on export")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nifcheckFO4 = NifFile(outfile)
    
    assert nifcheckFO4.shapes[0].textures[0] == nifFO4.shapes[0].textures[0], \
        f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[0]}' != '{nifFO4.shapes[0].textures[0]}'"
    assert nifcheckFO4.shapes[0].textures[1] == nifFO4.shapes[0].textures[1], \
        f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[1]}' != '{nifFO4.shapes[0].textures[1]}'"
    assert nifcheckFO4.shapes[0].textures[2] == nifFO4.shapes[0].textures[2], \
        f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[2]}' != '{nifFO4.shapes[0].textures[2]}'"
    assert nifcheckFO4.shapes[0].textures[7] == nifFO4.shapes[0].textures[7], \
        f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[7]}' != '{nifFO4.shapes[0].textures[7]}'"
    assert nifcheckFO4.shapes[0].shader_attributes == shaderAttrsFO4, f"Error: Shader attributes not preserved:\n{nifcheckFO4.shapes[0].shader_attributes}\nvs\n{shaderAttrsFO4}"
    assert nifcheckFO4.shapes[0].shader_name == nifFO4.shapes[0].shader_name, f"Error: Shader name not preserved: '{nifcheckFO4.shapes[0].shader_name}' != '{nifFO4.shapes[0].shader_name}'"


if TEST_BPY_ALL or TEST_SHADER_ALPHA:
    # Alpha property is translated into equivalent Blender nodes.
    #
    # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the
    # suffix.
    test_title("TEST_SHADER_ALPHA", "Shader attributes are read and turned into Blender shader nodes")
    clear_all()

    fileAlph = test_file(r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
    outfile = test_file(r"tests/Out/TEST_SHADER_ALPH.nif")

    bpy.ops.import_scene.pynifly(filepath=fileAlph)
    
    nifAlph = NifFile(fileAlph)
    furshape = nifAlph.shape_dict["tail_fur"]
    tail = bpy.data.objects["tail_fur"]
    assert 'Principled BSDF' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert 'Image Texture' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert 'Attribute' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert 'Normal Map' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert tail.active_material.blend_method == 'CLIP', f"Error: Alpha blend is '{tail.active_material.blend_method}', not 'CLIP'"

    print("## Shader attributes are written on export")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifCheck = NifFile(outfile)
    checkfurshape = nifCheck.shape_dict["tail_fur"]
    
    assert checkfurshape.textures[0] == furshape.textures[0], \
        f"Error: Texture paths not preserved: '{checkfurshape.textures[0]}' != '{furshape.textures[0]}'"
    assert checkfurshape.textures[1] == furshape.textures[1], \
        f"Error: Texture paths not preserved: '{checkfurshape.textures[1]}' != '{furshape.textures[1]}'"
    assert checkfurshape.textures[2] == furshape.textures[2], \
        f"Error: Texture paths not preserved: '{checkfurshape.textures[2]}' != '{furshape.textures[2]}'"
    assert checkfurshape.textures[7] == furshape.textures[7], \
        f"Error: Texture paths not preserved: '{checkfurshape.textures[7]}' != '{furshape.textures[7]}'"
    assert checkfurshape.shader_attributes == furshape.shader_attributes, f"Error: Shader attributes not preserved:\n{checkfurshape.shader_attributes}\nvs\n{furshape.shader_attributes}"

    assert checkfurshape.has_alpha_property, f"Error: Did not write alpha property"
    assert checkfurshape.alpha_property.flags == furshape.alpha_property.flags, f"Error: Alpha flags incorrect: {checkfurshape.alpha_property.flags} != {furshape.alpha_property.flags}"
    assert checkfurshape.alpha_property.threshold == furshape.alpha_property.threshold, f"Error: Alpha flags incorrect: {checkfurshape.alpha_property.threshold} != {furshape.alpha_property.threshold}"


if TEST_BPY_ALL or TEST_SHADER_3_3:
    test_title("TEST_SHADER_3_3", "Shader attributes are read and turned into Blender shader nodes")
    clear_all()

    append_from_file("FootMale_Big", True, r"tests\SkyrimSE\feet.3.3.blend", 
                     r"\Object", "FootMale_Big")
    bpy.ops.object.select_all(action='DESELECT')
    obj = find_shape("FootMale_Big")

    print("## Shader attributes are written on export")
    outfile = test_file(r"tests/Out/TEST_SHADER_3_3.nif")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = NifFile(outfile)
    
    assert nifcheckSE.shapes[0].textures[0] == r"textures\actors\character\male\MaleBody_1.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[0]}'"
    assert nifcheckSE.shapes[0].textures[1] == r"textures\actors\character\male\MaleBody_1_msn.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[1]}'"
    assert nifcheckSE.shapes[0].textures[2] == r"textures\actors\character\male\MaleBody_1_sk.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[2]}'"
    assert nifcheckSE.shapes[0].textures[7] == r"textures\actors\character\male\MaleBody_1_S.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[7]}'"


if TEST_BPY_ALL or TEST_CAVE_GREEN:
    # Regression: Make sure the transparency is exported on this nif.
    test_title("TEST_CAVE_GREEN", "Cave nif can be exported correctly")
    clear_all()
    testfile = test_file(r"tests\SkyrimSE\meshes\dungeons\caves\green\smallhall\caveghall1way01.nif")
    outfile = test_file(r"tests/Out/TEST_CAVE_GREEN.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    wall1 = bpy.data.objects["CaveGHall1Way01:2"]
    mat1 = wall1.active_material
    mix1 = mat1.node_tree.nodes['Principled BSDF'].inputs['Base Color'].links[0].from_node
    diff1 = mix1.inputs[6].links[0].from_node
    assert diff1.image.filepath.lower().endswith("cavebasewall01.dds"), f"Have correct wall diffuse: {diff1.image.filepath}"

    roots = find_shape("L2_Roots:5")

    bpy.ops.object.select_all(action='DESELECT')
    roots.select_set(True)
    bpy.ops.object.duplicate()

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheck = NifFile(outfile)
    rootscheck = nifcheck.shape_dict["L2_Roots:5"]
    assert rootscheck.has_alpha_property, f"Roots have alpha: {rootscheck.has_alpha_property}"
    assert rootscheck.shader_attributes.shaderflags2_test(ShaderFlags2.VERTEX_COLORS), \
        f"Have vertex colors: {rootscheck.shader_attributes.shaderflags2_test(ShaderFlags2.VERTEX_COLORS)}"


if TEST_BPY_ALL or TEST_POT:
    test_title("TEST_POT", "Test that pot shaders doesn't throw an error")
    clear_all()
    testfile = test_file(r"tests\SkyrimSE\spitpotopen01.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    assert 'ANCHOR:0' in bpy.data.objects.keys()


if TEST_BPY_ALL or TEST_NOT_FB:
    # This nif has a body where the skin-to-bone transforms don't define a simple translation
    # (they are off by a few decimal points). It also has a hood that does have the usual
    # translation, but it's loaded second onto an armature that was not translated. So it's 
    # messed up, but the test isn't checking for that.
    # 
    # It would be rational for the hood to load into a second armature in this situation, 
    # and that's probably the only real solution. But the FO4 body+head are off by a really 
    # small fraction and I'd like those to load into the same armature without problem. It
    # might be possible to cover both by reducing the sensitivity of the check enough that 
    # the head+body passes, but this set of clothes doesn't.
    #
    # TODO: Figure out a fix, expand the test.
    test_title("TEST_NOT_FB", "Test that nif that looked like facebones skel can be imported")
    clear_all()

    testfile = test_file(r"tests\FO4\6SuitM_Test.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = find_shape("body_Cloth:0")
    minz = min(v.co.z for v in body.data.vertices)
    assert minz > -130, f"Min z location not stretched: {minz}"


if TEST_BPY_ALL or TEST_MULTI_IMP:
    # Fact is, this DOES mess up. we can import more than one nif at a time, which 
    # is what we're trying to test. But we might be importing Skyrim's _0 and _1 weight
    # bodyparts, so we'd like them to load as shape keys if possible. BUT two of these
    # nifs have the same vert count, so they get loaded as shape keys tho they shouldn't.
    #
    # TODO: Decide if this is work fixing, and how. Maybe key of the _0 and _1 file 
    # extensions?
    test_title("TEST_MULTI_IMP", "Test that importing multiple hair parts doesn't mess up")
    clear_all()

    testfile1 = test_file(r"tests\FO4\FemaleHair25.nif")
    testfile2 = test_file(r"tests\FO4\FemaleHair25_Hairline1.nif")
    testfile3 = test_file(r"tests\FO4\FemaleHair25_Hairline2.nif")
    testfile4 = test_file(r"tests\FO4\FemaleHair25_Hairline3.nif")
    bpy.ops.import_scene.pynifly(files=[{"name": testfile1}, 
                                        {"name": testfile2}, 
                                        {"name": testfile3}, 
                                        {"name": testfile4}])
    h = find_shape("FemaleHair25:0")
    assert h.location.z > 120, f"Hair fully imported: {h.location}"


if TEST_BPY_ALL or TEST_WELWA:
    # The Welwa (bear skeleton) has bones similar to human bones--but they can't be
    # treated like the human skeleton. "Rename bones" is false on import and should be
    # remembered on the mesh and armature for export, so it's not explicitly specified on
    # export.
    test_title("TEST_WELWA", "Can read and write shape with unusual skeleton")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\SkyrimSE\welwa.nif")
    outfile = test_file(r"tests/Out/TEST_WELWA.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, create_bones=False)

    welwa = find_shape("111")
    skel = welwa.parent
    lipbone = skel.data.bones['NPC UpperLip']
    assert VNearEqual(lipbone.matrix_local.translation, (0, 49.717827, 161.427307)), f"Found {lipbone.name} at {lipbone.matrix_local.translation}"
    spine1 = skel.data.bones['NPC Spine1']
    assert VNearEqual(spine1.matrix_local.translation, (0, -50.551056, 64.465019)), f"Found {spine1.name} at {spine1.matrix_local.translation}"

    # Should remember that bones are not to be renamed.
    bpy.ops.object.select_all(action='DESELECT')
    welwa.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check ---------
    nifcheck = NifFile(outfile)

    assert "NPC Pelvis [Pelv]" not in nifcheck.nodes, f"Human pelvis name not written: {nifcheck.nodes.keys()}"


if TEST_BPY_ALL or TEST_MUTANT:
    test_title("TEST_MUTANT", "Test that the supermutant body imports correctly the *second* time")
    clear_all()
    testfile = test_file(r"tests/FO4/testsupermutantbody.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, create_bones=False)

    testnif = NifFile(testfile)
    assert round(testnif.shapes[0].global_to_skin.translation[2]) == -140, f"Expected -140 z translation in first nif, got {imp.nif.shapes[0].global_to_skin.translation[2]}"

    sm1 = bpy.context.object
    assert round(sm1.location[2]) == 140, f"Expect first supermutant body at 140 Z, got {sm1.location[2]}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, create_bones=False)
    sm2 = bpy.context.object
    assert sm2 != sm1, f"Second import created second object: {sm2.name}"
    assert round(sm2.location[2]) == 140, f"Expect supermutant body at 140 Z, got {sm2.location[2]}"

    
if TEST_BPY_ALL or TEST_EXPORT_HANDS:
    # When there are problems with the mesh we don't want to crash and burn.
    test_title("TEST_EXPORT_HANDS", "Test that hand mesh doesn't throw an error")
    clear_all()
    outfile = test_file(r"tests/Out/TEST_EXPORT_HANDS.nif")

    append_from_file("SupermutantHands", True, r"tests\FO4\SupermutantHands.blend", r"\Object", "SupermutantHands")
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = bpy.data.objects["SupermutantHands"]
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    assert os.path.exists(outfile)


if (TEST_BPY_ALL or TEST_PARTITION_ERRORS) and bpy.app.version[0] >= 3:
    # Partitions have to cleanly separate the faces into non-overlapping parts of the
    # shape. If that's not the case, we return an error.
    #
    # Doesn't run on 2.x, don't know why
    test_title("TEST_PARTITION_ERRORS", "Partitions with errors raise errors")
    clear_all()
    testfile = test_file(r"tests/Out/TEST_TIGER_EXPORT.nif")

    append_from_file("SynthMaleBody", True, r"tests\FO4\SynthBody02.blend", r"\Object", "SynthMaleBody")

    # Partitions must divide up the mesh cleanly--exactly 1 partition per tri
    bpy.context.view_layer.objects.active = bpy.data.objects["SynthMaleBody"]
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='FO4')
    
    # assert len(exporter.warnings) > 0, f"Error: Export should have generated warnings: {exporter.warnings}"
    # print(f"Exporter warnings: {exporter.warnings}")
    assert MULTIPLE_PARTITION_GROUP in bpy.data.objects["SynthMaleBody"].vertex_groups, "Error: Expected group to be created for tris in multiple partitions"


if TEST_BPY_ALL or TEST_SHEATH:
    # The sheath has extra data nodes for Havok. These are imported as Blender empty
    # objects, and can be exported again.
    test_title("TEST_SHEATH", "Extra data nodes are imported and exported")
    clear_all()

    testfile = test_file(r"tests/Skyrim/sheath_p1_1.nif")
    outfile = test_file(r"tests/Out/TEST_SHEATH.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    bglist = [obj for obj in bpy.data.objects if obj.name.startswith("BSBehaviorGraphExtraData")]
    slist = [obj for obj in bpy.data.objects if obj.name.startswith("NiStringExtraData")]
    bgnames = set([obj['BSBehaviorGraphExtraData_Name'] for obj in bglist])
    assert bgnames == set(["BGED"]), f"Error: Expected BG extra data properties, found {bgnames}"
    snames = set([obj['NiStringExtraData_Name'] for obj in slist])
    assert snames == set(["HDT Havok Path", "HDT Skinned Mesh Physics Object"]), \
        f"Error: Expected string extra data properties, found {snames}"

    # Write and check
    print('------- Can write extra data -------')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')


    print('------ Extra data checks out----')
    nifCheck = NifFile(outfile)
    sheathShape = nifCheck.shapes[0]

    names = [x[0] for x in nifCheck.behavior_graph_data]
    assert "BGED" in names, f"Error: Expected BGED in {names}"
    bgedCheck = nifCheck.behavior_graph_data[0]
    log.debug(f"BGED value is {bgedCheck}")
    assert bgedCheck[1] == "AuxBones\SOS\SOSMale.hkx", f"Extra data value = AuxBones/SOS/SOSMale.hkx: {bgedCheck}"
    assert bgedCheck[2], f"Extra data controls base skeleton: {bgedCheck}"

    strings = [x[0] for x in nifCheck.string_data]
    assert "HDT Havok Path" in strings, f"Error expected havoc path in {strings}"
    assert "HDT Skinned Mesh Physics Object" in strings, f"Error: Expected physics object in {strings}"


if TEST_BPY_ALL or TEST_FEET:
    # Feet have extra data nodes that are children of the feet mesh. This parent/child
    # relationship must be preserved on import and export.
    test_title("TEST_FEET", "Extra data nodes are imported and exported")
    clear_all()
    testfile = test_file(r"tests/SkyrimSE/caninemalefeet_1.nif")
    outfile = test_file(r"tests/Out/TEST_FEET.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    feet = bpy.data.objects['FootLowRes']
    assert len(feet.children) == 1, "Feet have children"
    assert feet.children[0]['NiStringExtraData_Name'] == "SDTA", "Feet have extra data child"
    assert feet.children[0]['NiStringExtraData_Value'].startswith('[{"name"'), f"Feet have string data"

    # Write and check that it's correct. Only the feet have to be selected--the extra data
    # goes because the object is a child of the feet object.
    bpy.ops.object.select_all(action='DESELECT')
    feet.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifCheck = NifFile(outfile)
    feetShape = nifCheck.shapes[0]
    assert feetShape.string_data[0][0] == 'SDTA', "String data name written correctly"
    assert feetShape.string_data[0][1].startswith('[{"name"'), "String data value written correctly"


if TEST_BPY_ALL or TEST_SCALING:
    test_title("TEST_SCALING", "Test that scale factors happen correctly")

    clear_all()
    testfile = test_file(r"tests\Skyrim\statuechampion.nif")
    testout = test_file(r"tests\Out\TEST_SCALING.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    base = bpy.data.objects['basis1']
    assert int(base.scale[0]) == 10, f"ERROR: Base scale should be 10, found {base.scale[0]}"
    tail = bpy.data.objects['tail_base.001']
    assert round(tail.scale[0], 1) == 1.7, f"ERROR: Tail scale should be ~1.7, found {tail.scale}"
    assert round(tail.location[0], 0) == -158, f"ERROR: Tail x loc should be -158, found {tail.location}"

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=testout, target_game="SKYRIM")

    checknif = NifFile(testout)
    checkfoot = checknif.shape_dict['FootLowRes']
    assert checkfoot.transform.rotation[0][0] == 1.0, f"ERROR: Foot rotation matrix not identity: {checkfoot.transform}"
    assert NearEqual(checkfoot.transform.scale, 1.0), f"ERROR: Foot scale not correct: {checkfoot.transform.scale}"

    zmax = max([v[2] for v in checkfoot.verts])
    zmin = min([v[2] for v in checkfoot.verts])
    assert zmax > 140, f"Foot is not scaled: {zmin} - {zmax}"
    assert zmin > 85, f"Foot is not scaled: {zmin} - {zmax}"

    checkbase = checknif.shape_dict['basis3']
    assert checkbase.transform.rotation[0][0] == 1.0, f"ERROR: Base rotation matrix not identity: {checkbase.transform.rotation}"
    assert checkbase.transform.scale == 10.0, f"ERROR: Base scale not correct: {checkbase.transform.scale}"
    zmax = max([v[2] for v in checkbase.verts])
    zmin = min([v[2] for v in checkbase.verts])
    assert zmax < 81, f"basis3 is not scaled: {zmin} - {zmax}"
    assert zmin < 15, f"basis3 is not scaled: {zmin} - {zmax}"


if TEST_BPY_ALL or TEST_SCALING_OBJ:
    test_title("TEST_SCALING_OBJ", "Can scale simple object with furniture markers")
    clear_all()
    testfile = test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = test_file(r"tests\Out\TEST_SCALING_OBJ.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=0.1)

    bench = bpy.context.object
    bmax = max([v.co.z for v in bench.data.vertices])
    bmin = min([v.co.z for v in bench.data.vertices])
    assert VNearEqual(bench.scale, (1,1,1)), f"Bench scale factor is 1: {bench.scale}"
    assert bmax < 3.1, f"Max Z is scaled down: {bmax}"
    assert bmin >= 0, f"Min Z is correct: {bmin}"

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    assert fmarkers[0].location.z < 3.4, f"Furniture marker location is correct: {fmarkers[0].location.z}"

    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    exporter = bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                            scale_factor=0.1)

    # --------- Check ----------
    nifcheck = NifFile(outfile)
    bcheck = nifcheck.shapes[0]
    fmcheck = nifcheck.furniture_markers
    bchmax = max([v[2] for v in bcheck.verts])
    assert bchmax > 30, f"Max Z is scaled up: {bchmax}"
    assert len(fmcheck) == 2, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].offset[2] > 30, f"Furniture marker Z scaled up: {fmcheck[0].offset[2]}"


if TEST_BPY_ALL or TEST_UNIFORM_SCALE:
    test_title("TEST_UNIFORM_SCALE", "Can export objects with uniform scaling")
    clear_all()

    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TestCube"
    cube.scale = Vector((4.0, 4.0, 4.0))

    testfile = test_file(r"tests\Out\TEST_UNIFORM_SCALE.nif")
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='SKYRIM')

    nifcheck = NifFile(testfile)
    shapecheck = nifcheck.shapes[0]
    assert NearEqual(shapecheck.transform.scale, 4.0), f"Shape scaled x4: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert VNearEqual(map(abs, v), [1,1,1]), f"All vertices at unit position: {v}"


if TEST_BPY_ALL or TEST_NONUNIFORM_SCALE:
    test_title("TEST_NONUNIFORM_SCALE", "Can export objects with non-uniform scaling")
    clear_all()

    testfile = test_file(r"tests\Out\TEST_NONUNIFORM_SCALE.nif")
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TestCube"
    cube.scale = Vector((2.0, 4.0, 8.0))

    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='SKYRIM')

    nifcheck = NifFile(testfile)
    shapecheck = nifcheck.shapes[0]
    assert NearEqual(shapecheck.transform.scale, 1.0), f"Nonuniform scale exported in verts so scale is 1: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert not VNearEqual(map(abs, v), [1,1,1]), f"All vertices scaled away from unit position: {v}"


if TEST_BPY_ALL or TEST_TRIP_SE:
    # Special bodytri files allow for Bodyslide or FO4 body morphing.
    test_title("TEST_TRIP_SE", "Bodypart tri extra data and file are written on export")
    clear_all()
    outfile = test_file(r"tests/Out/TEST_TRIP_SE.nif")
    outfile1 = test_file(r"tests/Out/TEST_TRIP_SE_1.nif")
    outfiletrip = test_file(r"tests/Out/TEST_TRIP_SE.tri")

    append_from_file("Penis_CBBE", True, r"tests\SkyrimSE\HorseFuta.blend", 
                     r"\Object", "Penis_CBBE")
    bpy.ops.object.select_all(action='DESELECT')
    obj = find_shape("Penis_CBBE")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', write_bodytri=True)

    print(' ------- Check --------- ')
    nifcheck = NifFile(outfile1)

    bodycheck = nifcheck.shape_dict["Penis_CBBE"]
    assert bodycheck.name == "Penis_CBBE", f"Penis found in nif"

    stringdata = bodycheck.string_data
    assert stringdata, f"Found string data: {stringdata}"
    sd = stringdata[0]
    assert sd[0] == 'BODYTRI', f"Found BODYTRI string data"
    assert sd[1].endswith("TEST_TRIP_SE.tri"), f"Found correct filename"

    tripcheck = TripFile.from_file(outfiletrip)
    assert len(tripcheck.shapes) == 1, f"Found shape"
    bodymorphs = tripcheck.shapes['Penis_CBBE']
    assert len(bodymorphs) == 27, f"Found enough morphs: {len(bodymorphs)}"
    assert "CrotchBack" in bodymorphs.keys(), f"Found 'CrotchBack' in {bodymorphs.keys()}"


if TEST_BPY_ALL or TEST_TRIP:
    test_title("TEST_TRIP", "Body tri extra data and file are written on export")
    clear_all()
    outfile = test_file(r"tests/Out/TEST_TRIP.nif")
    outfiletrip = test_file(r"tests/Out/TEST_TRIP.tri")

    append_from_file("BaseMaleBody", True, r"tests\FO4\BodyTalk.blend", r"\Object", "BaseMaleBody")
    bpy.ops.object.select_all(action='DESELECT')
    body = find_shape("BaseMaleBody")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', write_bodytri=True)

    print(' ------- Check --------- ')
    nifcheck = NifFile(outfile)

    bodycheck = nifcheck.shape_dict["BaseMaleBody"]
    assert bodycheck.name == "BaseMaleBody", f"Body found in nif"

    stringdata = nifcheck.string_data
    assert stringdata, f"Found string data: {stringdata}"
    sd = stringdata[0]
    assert sd[0] == 'BODYTRI', f"Found BODYTRI string data"
    assert sd[1].endswith("TEST_TRIP.tri"), f"Found correct filename"

    tripcheck = TripFile.from_file(outfiletrip)
    assert len(tripcheck.shapes) == 1, f"Found shape"
    bodymorphs = tripcheck.shapes['BaseMaleBody']
    assert len(bodymorphs) > 30, f"Found enough morphs: {len(len(bodymorphs))}"
    assert "BTShoulders" in bodymorphs.keys(), f"Found 'BTShoulders' in {bodymorphs.keys()}"


if TEST_BPY_ALL or TEST_COLORS:
    # Blender's vertex color layers are used to define vertex colors in the nif.
    test_title("TEST_COLORS", "Can read & write vertex colors")
    clear_all()
    outfile = test_file(r"tests/Out/TEST_COLORS_Plane.nif")
    export_from_blend(r"tests\FO4\VertexColors.blend", "Plane",
                      "FO4", outfile)

    nif3 = NifFile(outfile)
    assert len(nif3.shapes[0].colors) > 0, f"Expected color layers, have: {len(nif3.shapes[0].colors)}"
    cd = nif3.shapes[0].colors
    assert cd[0] == (0.0, 1.0, 0.0, 1.0), f"First vertex found: {cd[0]}"
    assert cd[1] == (1.0, 1.0, 0.0, 1.0), f"Second vertex found: {cd[1]}"
    assert cd[2] == (1.0, 0.0, 0.0, 1.0), f"Second vertex found: {cd[2]}"
    assert cd[3] == (0.0, 0.0, 1.0, 1.0), f"Second vertex found: {cd[3]}"


if TEST_BPY_ALL or TEST_COLORS2:
    test_title("TEST_COLORS2", "Can read & write vertex colors")
    clear_all()
    testfile = test_file(r"tests/FO4/HeadGear1.nif")
    testfileout = test_file(r"tests/Out/TEST_COLORSB_HeadGear1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    colordata = obj.data.vertex_colors.active.data
    targetv = find_vertex(obj.data, (1.62, 7.08, 0.37))
    assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
    for lp in obj.data.loops:
        if lp.vertex_index == targetv:
            assert colordata[lp.index].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[lp.index].color[:]}"

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game="FO4")

    nif2 = NifFile(testfileout)
    assert nif2.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not reread correctly: {nif2.shapes[0].colors[0]}"
    assert nif2.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0), f"Color 561 not reread correctly: {nif2.shapes[0].colors[561]}"


if TEST_BPY_ALL or TEST_NEW_COLORS:
    # Regression: There have been issues dealing with how Blender handles colors.
    test_title("TEST_NEW_COLORS", "Can write vertex colors that were created in blender")
    clear_all()
    export_from_blend(r"tests\SKYRIMSE\BirdHead.blend",
                      "HeadWhole",
                      "SKYRIMSE",
                      r"tests/Out/TEST_NEW_COLORS.nif")

    nif = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_NEW_COLORS.nif"))
    shape = nif.shapes[0]
    assert shape.colors, f"Have colors in shape {shape.name}"
    assert shape.colors[10] == (1.0, 1.0, 1.0, 1.0), f"Colors are as expected: {shape.colors[10]}"
    assert shape.shader_attributes.shaderflags2_test(ShaderFlags2.VERTEX_COLORS), \
        f"ShaderFlags2 vertex colors set: {ShaderFlags2(shape.shader_attributes.Shader_Flags_2).fullname}"


if TEST_BPY_ALL or TEST_VERTEX_COLOR_IO:
    # On heads, vertex alpha and diffuse alpha work together to determine the final
    # transparency the user sees. We set up Blender shader nodes to provide the same
    # effect.
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


if TEST_BPY_ALL or TEST_VERTEX_ALPHA_IO:
    test_title("TEST_VERTEX_ALPHA_IO", "Import & export shape with vertex alpha values")
    clear_all()
    testfile = test_file(r"tests\SkyrimSE\meshes\actors\character\character assets\maleheadkhajiit.nif")
    outfile = test_file(r"tests/Out/TEST_VERTEX_ALPHA_IO.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = bpy.context.object
    nodes = head.active_material.node_tree.nodes
    shader = nodes["Principled BSDF"]
    assert shader, f"Found Principled BSDF node"
    mixnode = shader.inputs["Base Color"].links[0].from_node
    diffuse = mixnode.inputs[6].links[0].from_node
    assert diffuse.name == "Image Texture", f"Found correct diffuse type {diffuse.name}"
    assert diffuse.image.filepath.endswith('KhajiitMaleHead.dds'), f"Filepath correct: {diffuse.image.filepath}"
    map1 = shader.inputs['Alpha'].links[0].from_node
    assert map1.bl_idname == "ShaderNodeMapRange", f"Found first map: {map1}"
    map2 = map1.inputs['To Min'].links[0].from_node
    assert map2.bl_idname == "ShaderNodeMapRange", f"Found second map: {map2}"
    attr = map2.inputs['Value'].links[0].from_node
    assert attr.bl_idname == "ShaderNodeAttribute", f"Found attribute node: {attr}"
    assert map1.inputs['Value'].links[0].from_node == diffuse, f"Alpha path correct: {map1.inputs['Value'].links[0].from_node}"

    bpy.ops.export_scene.pynifly(filepath=outfile)

    nif = NifFile(testfile)
    head1 = nif.shapes[0]
    nif2 = NifFile(outfile)
    head2 = nif2.shapes[0]

    assert head2.has_alpha_property, f"Error: Did not write alpha property"
    assert head2.alpha_property.flags == head1.alpha_property.flags, f"Error: Alpha flags incorrect: {head2.alpha_property.flags} != {head1.alpha_property.flags}"
    assert head2.alpha_property.threshold == head1.alpha_property.threshold, f"Error: Alpha flags incorrect: {head2.alpha_property.threshold} != {head1.alpha_property.threshold}"

    assert head2.textures[0] == head1.textures[0], \
        f"Error: Texture paths not preserved: '{head2.textures[0]}' != '{head1.textures[0]}'"
    assert head2.textures[1] == head1.textures[1], \
        f"Error: Texture paths not preserved: '{head2.textures[1]}' != '{head1.textures[1]}'"
    assert head2.textures[2] == head1.textures[2], \
        f"Error: Texture paths not preserved: '{head2.textures[2]}' != '{head1.textures[2]}'"
    assert head2.textures[7] == head1.textures[7], \
        f"Error: Texture paths not preserved: '{head2.textures[7]}' != '{head1.textures[7]}'"
    assert head2.shader_attributes == head1.shader_attributes, f"Error: Shader attributes not preserved:\n{head2.shader_attributes}\nvs\n{head1.shader_attributes}"


if TEST_BPY_ALL or TEST_VERTEX_ALPHA:
    test_title("TEST_VERTEX_ALPHA", "Export shape with vertex alpha values")

    clear_all()
    outfile = test_file(r"tests/Out/TEST_VERTEX_ALPHA.nif")
    cube = append_from_file("Cube", True, r"tests\Skyrim\AlphaCube.blend", r"\Object", "Cube")
    bpy.context.view_layer.objects.active = cube
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nifcheck = NifFile(outfile)
    shapecheck = nifcheck.shapes[0]

    assert shapecheck.shader_attributes.Shader_Flags_1 & ShaderFlags1.VERTEX_ALPHA, f"Expected VERTEX_ALPHA set: {ShaderFlags1(shapecheck.shader_attributes.Shader_Flags_1).fullname}"
    assert shapecheck.colors[0][3] == 0.0, f"Expected 0, found {shapecheck.colors[0]}"
    for c in shapecheck.colors:
        assert c[0] == 1.0 and c[1] == 1.0 and c[2] == 1.0, f"Expected all white verts in nif, found {c}"

    bpy.ops.import_scene.pynifly(filepath=outfile)
    objcheck = bpy.context.object
    colorscheck = objcheck.data.vertex_colors
    assert ALPHA_MAP_NAME in colorscheck.keys(), f"Expected alpha map, found {objcheck.data.vertex_colors.keys()}"

    assert min([c.color[1] for c in colorscheck[ALPHA_MAP_NAME].data]) == 0, f"Expected some 0 alpha values"
    for i, c in enumerate(objcheck.data.vertex_colors['Col'].data):
        assert c.color[:] == (1.0, 1.0, 1.0, 1.0), f"Expected all white, full alpha in read object, found {i}: {c.color[:]}"


if TEST_BPY_ALL or TEST_BONE_HIERARCHY:
    # This hair has a complex custom bone hierarchy which have moved with havok.
    # Turns out the bones must be exported in a hierarchy for that to work.
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


if TEST_BPY_ALL or TEST_FACEBONE_EXPORT:
    # Facebones are exported along with the regular nif as long as either they are 
    # both selected or if there's an armature modifier for both on the shape. 
    # This test doesn't check that second condition.
    test_title("TEST_FACEBONE_EXPORT", "Test can export facebones + regular nif; shapes with hidden verts export correctly")
    clear_all()

    outfile = test_file(r"tests/Out/TEST_FACEBONE_EXPORT.nif", output=True)
    outfile_fb = test_file(r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif", output=True)
    outfile_tri = test_file(r"tests/Out/TEST_FACEBONE_EXPORT.tri", output=True)
    outfile_chargen = test_file(r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri")
    outfile2 = test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif", output=True)
    outfile2_fb = test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif", output=True)

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = append_from_file("HorseFemaleHead", False, r"tests\FO4\HeadFaceBones.blend", r"\Object", "HorseFemaleHead")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen")

    # Exporter generates normal and facebones nif file
    nif1 = NifFile(outfile)
    assert len(nif1.shapes) == 1, "Write the file successfully"
    assert len(nif1.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
    nif2 = NifFile(outfile_fb)
    assert len(nif2.shapes) == 1
    assert len(nif2.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

    # No facebones in the normal file
    # (Not sure if facebones nif needs the normal bones--they are there in vanilla)
    assert len([x for x in nif1.nodes.keys() if "skin_bone" in x]) == 0, f"Expected no skin_bone nodes in regular nif file; found {nif1.nodes.keys()}"
    #assert len([x for x in nif1.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif2.nodes.keys()}"

    # Exporter generates a single tri file named after the normal file
    tri1 = TriFile.from_file(outfile_tri)
    assert len(tri1.morphs) > 0
    tri2 = TriFile.from_file(outfile_chargen)
    assert len(tri2.morphs) > 0

    # Same behavior if the shape is parented to the facebones skeleton and the normal skeleton is 
    # exported
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active  = bpy.data.objects['HorseFemaleHead']
    bpy.ops.object.parent_clear(type='CLEAR')
    bpy.context.view_layer.objects.active  = bpy.data.objects['FaceBonesSkel']
    bpy.data.objects['HorseFemaleHead'].select_set(True)
    bpy.ops.object.parent_set(type='ARMATURE_NAME') 
    bpy.data.objects['FullBodySkel'].select_set(True)

    # Export shape with facebones parent
    bpy.ops.export_scene.pynifly(filepath=outfile2, target_game='FO4')

    nif3 = NifFile(outfile2)
    assert len(nif3.shapes) == 1, "Write the file successfully"
    assert len(nif3.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
    nif4 = NifFile(outfile2_fb)
    assert len(nif4.shapes) == 1
    assert len(nif4.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

    skinbones = [x for x in nif3.nodes.keys() if "skin_bone" in x]
    assert len(skinbones) == 0, f"Expected no skin_bone nodes in regular nif file; found {skinbones}"
    #assert len([x for x in nif4.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif4.nodes.keys()}"


if TEST_BPY_ALL or TEST_FACEBONE_EXPORT2:
    # Regression. Test that facebones and regular mesh are both exported.
    test_title("TEST_FACEBONE_EXPORT2", "Test can export facebones + regular nif; shapes with hidden verts export correctly")
    clear_all()

    outfile = test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif")
    outfile_fb = test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif")

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = append_from_file("FemaleHead.Export.001", False, r"tests\FO4\Animatron Space Simple.blend", r"\Object", "FemaleHead.Export.001")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen")

    outnif = NifFile(outfile)
    assert len(outnif.shapes) >= 1, f"Have shapes in export file: {outnif.shapes}"

    outniffb = NifFile(outfile_fb)
    assert len(outniffb.shapes) >= 1, f"Have shapes in facebones export file: {outniffb.shapes}"


if TEST_BPY_ALL or TEST_HYENA_PARTITIONS:
    # This Blender object has non-normalized weights--the weights for each vertex do 
    # not always add up to 1. That turns out to screw up the rendering. So check that 
    # the export normalizes them. This isn't done by pynifly or the wrapper layers.
    test_title("TEST_HYENA_PARTITIONS", "Partitions export successfully, with warning")

    clear_all()
    outfile = test_file(r"tests/Out/TEST_HYENA_PARTITIONS.nif", output=True)

    head = append_from_file("HyenaMaleHead", True, r"tests\FO4\HyenaHead.blend", r"\Object", "HyenaMaleHead")
    append_from_file("Skeleton", True, r"tests\FO4\HyenaHead.blend", r"\Object", "Skeleton")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = head
    head.select_set(True)
    bpy.data.objects["FaceBones.Skel"].select_set(True)
    bpy.data.objects["Skeleton"].select_set(True)
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    #assert len(exporter.warnings) == 1, f"One warning reported ({exporter.warnings})"

    nif1 = NifFile(outfile)
    assert "HyenaMaleHead" in nif1.shape_dict, "Wrote the file successfully"

    head = nif1.shape_dict["HyenaMaleHead"]
    for i in range(0, 5000):
        weight_total = 0
        for group_weights in head.bone_weights.values():
            for weight_pair in group_weights:
                if weight_pair[0] == i:
                    weight_total += weight_pair[1]
        assert NearEqual(weight_total, 1.0), f"Weights should total to 1 for index {i}: {weight_total}"        


if TEST_BPY_ALL or TEST_MULT_PART:
    # Check that we DON'T throw a multiple-partitions error when it's not necessary.
    test_title("TEST_MULT_PART", "Export shape with face that might fall into multiple partititions")
    clear_all()

    outfile = test_file(r"tests/Out/TEST_MULT_PART.nif")
    append_from_file("MaleHead", True, r"tests\SkyrimSE\multiple_partitions.blend", r"\Object", "MaleHead")
    obj = bpy.data.objects["MaleHead"]
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    assert "*MULTIPLE_PARTITIONS*" not in obj.vertex_groups, f"Exported without throwing *MULTIPLE_PARTITIONS* error"


if TEST_BPY_ALL or TEST_BONE_XPORT_POS:
    # Since we use a reference skeleton to make bones, we have to be able to handle
    # the condition where the mesh is not human and the reference skeleton should not
    # be used.
    test_title("TEST_BONE_XPORT_POS", 
               "Test that bones named like vanilla bones but from a different skeleton export to the correct position")

    clear_all()
    testfile = test_file(r"tests\Skyrim\draugr.nif")
    outfile = test_file(r"tests/Out/TEST_BONE_XPORT_POS.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    
    draugr = bpy.context.object
    spine2 = draugr.parent.data.bones['NPC Spine2 [Spn2]']
    assert round(spine2.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2.head[2]}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["Body_Male_Naked"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # --- Check nif contents directly ---
    nifcheck = NifFile(outfile)
    body = nifcheck.shape_dict['Body_Male_Naked']
    spine2_check = nifcheck.nodes['NPC Spine2 [Spn2]']
    spine2_xf = spine2_check.transform
    assert round(spine2_xf.translation[2], 2) == 102.36, \
        f"Expected nif location at z 102.36, found {spine2_xf.translation[2]}"

    thigh_sk2b_check = body.get_shape_skin_to_bone('NPC L Thigh [LThg]')

    assert VNearEqual(thigh_sk2b_check.translation, Vector([-4.0765, -4.4979, 78.4952])), \
        f"Expected skin-to-bone translation Z = 78.4952, found {thigh_sk2b_check.translation[:]}"
    impnif = NifFile(testfile)
    thsk2b = impnif.shapes[0].get_shape_skin_to_bone('NPC L Thigh [LThg]')
    assert thsk2b.NearEqual(thigh_sk2b_check), f"Entire skin-to-bone transform correct: {thigh_sk2b_check}"

    # --- Check we can import correctly ---
    bpy.ops.import_scene.pynifly(filepath=outfile)
    impcheck = NifFile(outfile)
    nifbone = impcheck.nodes['NPC Spine2 [Spn2]']
    assert round(nifbone.transform.translation[2], 2) == 102.36, f"Expected nif location at z 102.36, found {nifbone.transform.translation[2]}"

    draugrcheck = bpy.context.object
    spine2check = draugrcheck.parent.data.bones['NPC Spine2 [Spn2]']
    assert round(spine2check.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2check.head[2]}"


if TEST_BPY_ALL or TEST_BOW:
    # The bow has a simple collision that we can import and export.
    # Note the bow nif as shipped by Bethesda throws errors on import, and the 
    # collision does not match the mesh closely at all. This test adjusts it on
    # export because it was too ugly.
    test_title("TEST_BOW", "Can read and write bow")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = test_file(r"tests/Out/TEST_BOW.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Check root info
    obj = bpy.context.object
    assert obj["pynRootNode_BlockType"] == 'BSFadeNode', "pynRootNode_BlockType holds the type of root node for the given shape"
    assert obj["pynRootNode_Name"] == "GlassBowSkinned.nif", "pynRootNode_Name holds the name for the root node"
    assert obj["pynRootNode_Flags"] == "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR", f"'pynRootNode_Flags' holds the flags on the root node: {obj['pynRootNode_Flags']}"

    # Check collision info
    coll = find_shape('bhkCollisionObject')
    assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
    assert coll['pynCollisionTarget'] == 'Bow_MidBone', f"'Target' names the object the collision affects, in this case a bone: {coll['pynCollisionTarget']}"

    collbody = coll.children[0]
    assert collbody.name == 'bhkRigidBodyT', f"Child of collision is the collision body object"
    assert collbody['collisionFilter_layer'] == SkyrimCollisionLayer.WEAPON.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
    assert collbody["collisionResponse"] == hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"
    assert VNearEqual(collbody.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), f"Collision body rotation correct: {collbody.rotation_quaternion}"

    collshape = collbody.children[0]
    assert collshape.name == 'bhkBoxShape', f"Collision shape is child of the collision body"
    assert collshape['bhkMaterial'] == 'MATERIAL_BOWS_STAVES', f"Shape material is a custom property: {collshape['bhkMaterial']}"
    assert round(collshape['bhkRadius'],4) == 0.0136, f"Radius property available as custom property: {collshape['bhkRadius']}"
    corner = map(abs, collshape.data.vertices[0].co)
    assert VNearEqual(corner, [11.01445, 57.6582, 0.95413]), f"Collision shape in correct position: {corner}"

    bged = find_shape("BSBehaviorGraphExtraData")
    assert bged['BSBehaviorGraphExtraData_Value'] == "Weapons\Bow\BowProject.hkx", f"BGED node contains bow project: {bged['BSBehaviorGraphExtraData_Value']}"

    strd = find_shape("NiStringExtraData")
    assert strd['NiStringExtraData_Value'] == "WeaponBow", f"Str ED node contains bow value: {strd['NiStringExtraData_Value']}"

    bsxf = find_shape("BSXFlags")
    assert bsxf['BSXFlags_Name'] == "BSX", f"BSX Flags contain name BSX: {bsxf['BSXFlags_Name']}"
    assert bsxf['BSXFlags_Value'] == "HAVOC | COMPLEX | DYNAMIC | ARTICULATED", "BSX Flags object contains correct flags: {bsxf['BSXFlags_Value']}"

    invm = find_shape("BSInvMarker")
    assert invm['BSInvMarker_Name'] == "INV", f"Inventory marker shape has correct name: {invm['BSInvMarker_Name']}"
    assert invm['BSInvMarker_RotX'] == 4712, f"Inventory marker rotation correct: {invm['BSInvMarker_RotX']}"
    assert round(invm['BSInvMarker_Zoom'], 4) == 1.1273, f"Inventory marker zoom correct: {invm['BSInvMarker_Zoom']}"
    
    # ------- Export --------

    # Move the edge of the collision box so it covers the bow better
    for v in collshape.data.vertices:
        if v.co.x > 0:
            v.co.x = 16.5

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check Results --------

    impnif = NifFile(testfile)
    nifcheck = NifFile(outfile)
    compare_shapes(impnif.shape_dict['ElvenBowSkinned:0'],
                    nifcheck.shape_dict['ElvenBowSkinned:0'],
                    obj)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    bsxcheck = nifcheck.bsx_flags
    assert bsxcheck == ["BSX", 202], f"BSX Flag node found: {bsxcheck}"

    bsinvcheck = nifcheck.inventory_marker
    assert bsinvcheck[0:4] == ["INV", 4712, 0, 785], f"Inventory marker set: {bsinvcheck}"
    assert round(bsinvcheck[4], 4) == 1.1273, f"Inventory marker zoom set: {bsinvcheck[4]}"

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck.get_node_xform_to_global("Bow_MidBone")
    assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = mbc_xf.as_matrix().to_euler()
    assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck = collcheck.body
    p = bodycheck.properties
    assert VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    assert VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


if TEST_BPY_ALL or TEST_BOW2:
    test_title("TEST_BOW2", "Can modify collision shape location")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile2 = test_file(r"tests/Out/TEST_BOW2.nif")
    
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = find_shape('ElvenBowSkinned')
    coll = find_shape('bhkCollisionObject')
    collbody = coll.children[0]
    collshape = collbody.children[0]
    bged = find_shape("BSBehaviorGraphExtraData")
    strd = find_shape("NiStringExtraData")
    bsxf = find_shape("BSXFlags")
    invm = find_shape("BSInvMarker")

    # ------- Export --------
    # Move the edge of the collision box so it covers the bow better
    for v in collshape.data.vertices:
        if v.co.x > 0:
            v.co.x = 16.5

    # Move the collision object 
    coll.location = coll.location + Vector([5, 10, 0])
    collshape.location = collshape.location + Vector([-5, -10, 0])

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    coll.select_set(True)
    bged.select_set(True)
    strd.select_set(True)
    bsxf.select_set(True)
    invm.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile2, target_game='SKYRIMSE')

    # ------- Check Results 2 --------

    nifcheck2 = NifFile(outfile2)

    midbowcheck2 = nifcheck2.nodes["Bow_MidBone"]
    collcheck2 = midbowcheck2.collision_object
    assert collcheck2.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck2.blockname}"
    assert bhkCOFlags(collcheck2.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck2.get_node_xform_to_global("Bow_MidBone")
    assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = mbc_xf.as_matrix().to_euler()
    assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck2 = collcheck2.body
    p = bodycheck2.properties
    assert VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    assert VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


if TEST_BPY_ALL or TEST_BOW3:
    # We can change the collision by editing the Blender shapes
    test_title("TEST_BOW3", "Can modify collision shape type")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile3 = test_file(r"tests/Out/TEST_BOW3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = find_shape('ElvenBowSkinned')
    coll = find_shape('bhkCollisionObject')
    collbody = coll.children[0]
    collshape = collbody.children[0]
    bged = find_shape("BSBehaviorGraphExtraData")
    strd = find_shape("NiStringExtraData")
    bsxf = find_shape("BSXFlags")
    invm = find_shape("BSInvMarker")

    # ------- Export --------

    # Move the collision object 
    for v in collshape.data.vertices:
        if NearEqual(v.co.x, 11.01, epsilon=0.5):
            v.co.x = 16.875
            if v.co.y > 0:
                v.co.y = 26.72
            else:
                v.co.y = -26.72
    collshape.name = "bhkConvexVerticesShape"
    collbody.name = "bhkRigidBody"

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    coll.select_set(True)
    bged.select_set(True)
    strd.select_set(True)
    bsxf.select_set(True)
    invm.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile3, target_game='SKYRIMSE')
    
    # ------- Check Results 3 --------

    nifcheck3 = NifFile(outfile3)

    midbowcheck3 = nifcheck3.nodes["Bow_MidBone"]
    collcheck3 = midbowcheck3.collision_object
    assert collcheck3.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck3.blockname}"
    assert bhkCOFlags(collcheck3.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck3.get_node_xform_to_global("Bow_MidBone")
    assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = mbc_xf.as_matrix().to_euler()
    assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck3 = collcheck3.body

    cshapecheck3 = bodycheck3.shape
    assert cshapecheck3.blockname == "bhkConvexVerticesShape", f"Shape is convex vertices: {cshapecheck3.blockname}"
    assert VNearEqual(cshapecheck3.vertices[0], (-0.73, -0.267, 0.014, 0.0)), f"Convex shape is correct"


if TEST_BPY_ALL or TEST_COLLISION_HIER:
    # These leeks are two shapes collected under an NiNode, with the collision on the 
    # NiNode. 
    test_title("TEST_COLLISION_HIER", "Can read and write hierarchy of nodes containing shapes")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\Skyrim\grilledleekstest.nif")
    outfile = test_file(r"tests/Out/TEST_COLLISION_HIER.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek4 = find_shape("Leek04")
    leek0 = find_shape("Leek04:0")
    leek1 = find_shape("Leek04:1")
    c1 = find_shape("bhkCollisionObject")
    rb = find_shape("bhkRigidBody")
    cshape = find_shape("bhkConvexVerticesShape")
    assert c1.parent.name == "Leek04" in bpy.data.objects, f"Target is a valid object: {c1.parent.name}"
    assert leek0.parent.name == "Leek04" in bpy.data.objects, f"Target is a valid object: {leek0.parent.name}"
    assert leek1.parent.name == "Leek04" in bpy.data.objects, f"Target is a valid object: {leek1.parent.name}"
    xf = cshape.matrix_world
    minx = min((xf @ v.co).x for v in cshape.data.vertices)
    maxx = max((xf @ v.co).x for v in cshape.data.vertices)
    miny = min((xf @ v.co).y for v in cshape.data.vertices)
    maxy = max((xf @ v.co).y for v in cshape.data.vertices)
    assert abs(minx - -12.2) < 0.1, f"Minimum x of collision shape is correct: {minx}"
    assert abs(maxx - -5.5) < 0.1, f"Maximum x of collision shape is correct: {maxx}"
    assert abs(miny - -2.4) < 0.1, f"Minimum y of collision shape is correct: {miny}"
    assert abs(maxy - 1.7) < 0.1, f"Maximum y of collision shape is correct: {maxy}"

    # ------- Export --------

    bpy.ops.object.select_all(action='DESELECT')
    leek4 = find_shape("BSXFlags")
    bsxf = find_shape("BSXFlags")
    invm = find_shape("BSInvMarker")
    leek4.select_set(True)
    leek0.select_set(True)
    leek1.select_set(True)
    bsxf.select_set(True)
    invm.select_set(True)
    bpy.context.view_layer.objects.active = leek4
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check Results --------

    nifOrig = NifFile(testfile)
    l4NodeOrig = nifOrig.nodes["Leek04"]
    collOrig = l4NodeOrig.collision_object
    rbOrig = collOrig.body
    shOrig = rbOrig.shape

    nifcheck = NifFile(outfile)
    leek4Check = nifcheck.nodes['Leek04']
    coCheck = leek4Check.collision_object
    rbCheck = coCheck.body
    shCheck = rbCheck.shape
    assert shCheck.blockname == "bhkConvexVerticesShape", f"Have our convex vert shape"
    l0Check = nifcheck.shape_dict["Leek04:0"]
    l1Check = nifcheck.shape_dict["Leek04:1"]
    assert l0Check.parent.name == "Leek04", f"Shapes are under the grouping node: {l0Check.parent.name}"
    assert l1Check.parent.name == "Leek04", f"Shapes are under the grouping node: {l1Check.parent.name}"
    # Vertices match. Depends on verts not getting re-ordered.
    assert VNearEqual(shCheck.vertices[0], shOrig.vertices[0]), f"Collision vertices match 0: {shCheck.vertices[0][:]} == {shOrig.vertices[0][:]}"
    assert VNearEqual(shCheck.vertices[5], shOrig.vertices[5]), f"Collision vertices match 0: {shCheck.vertices[5][:]} == {shOrig.vertices[5][:]}"


if TEST_BPY_ALL or TEST_NORM:
    test_title("TEST_NORM", "Normals are read correctly")
    clear_all()
    testfile = test_file(r"tests/FO4/CheetahMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = find_shape("CheetahMaleHead")

    head.data.calc_normals_split()

    vi =  find_vertex(head.data, (-4.92188, 0.646485, -10.0156), epsilon=0.01)
    targetvert = head.data.vertices[vi]
    assert targetvert.normal.x < -0.5, \
        f"Vertex normal for vertex {targetvert.index} as expected: {targetvert.normal}"

    vertloops = [l.index for l in head.data.loops if l.vertex_index == targetvert.index]
    custnormal = head.data.loops[vertloops[0]].normal
    print(f"TEST_NORM custnormal: loop {vertloops[0]} has normal {custnormal}")
    assert VNearEqual(custnormal, [-0.1772, 0.4291, 0.8857]), \
        f"Custom normal different from vertex normal: {custnormal}"


if TEST_BPY_ALL or TEST_ROGUE01:
    # Custom split normals change the direction light bounces off an object. They may be
    # set to eliminate seams between parts of a mesh, or between two meshes.
    test_title("TEST_ROGUE01", "Mesh with wonky normals exports correctly")
    clear_all()
    testfile = test_file(r"tests/Out/TEST_ROGUE01.nif")

    obj = append_from_file("MHelmetLight:0", False, r"tests\FO4\WonkyNormals.blend", r"\Object", "MHelmetLight:0")
    assert obj.name == "MHelmetLight:0", "Got the right object"
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")

    nif2 = NifFile(testfile)
    shape2 = nif2.shapes[0]

    assert round(shape2.normals[44][0]) == 0, f"Normal should point sraight up, found {shape2.normals[44]}"
    assert round(shape2.normals[44][1]) == 0, f"Normal should point sraight up, found {shape2.normals[44]}"
    assert round(shape2.normals[44][2]) == 1, f"Normal should point sraight up, found {shape2.normals[44]}"

    assert 6.82 == round(shape2.verts[12][0], 2), f"Vert location wrong: 6.82 != {shape2.verts[12][0]}"
    assert 0.58 == round(shape2.verts[12][1], 2), f"Vert location wrong: 0.58 != {shape2.verts[12][0]}"
    assert 9.05 == round(shape2.verts[12][2], 2), f"Vert location wrong: 9.05 != {shape2.verts[12][0]}"
    assert 0.13 == round(shape2.verts[5][0], 2), f"Vert location wrong: 0.13 != {shape2.verts[5][0]}"
    assert 9.24 == round(shape2.verts[5][1], 2), f"Vert location wrong: 9.24 != {shape2.verts[5][0]}"
    assert 8.91 == round(shape2.verts[5][2], 2), f"Vert location wrong: 8.91 != {shape2.verts[5][0]}"
    assert -3.21 == round(shape2.verts[33][0], 2), f"Vert location wrong: -3.21 != {shape2.verts[33][0]}"
    assert -1.75 == round(shape2.verts[33][1], 2), f"Vert location wrong: -1.75 != {shape2.verts[33][0]}"
    assert 12.94 == round(shape2.verts[33][2], 2), f"Vert location wrong: 12.94 != {shape2.verts[33][0]}"

    # Original has a tri <12, 13, 14>. Find it in the original and then in the exported object

    found = -1
    target = set([12, 13, 14])
    for p in obj.data.polygons:
        ps = set([obj.data.loops[lp].vertex_index for lp in p.loop_indices])
        if ps == target:
            print(f"Found triangle in source mesh at {p.index}")
            found = p.index
            break
    assert found >= 0, "Triangle not in source mesh"

    found = -1
    for i, t in enumerate(shape2.tris):
        if set(t) == target:
            print(f"Found triangle in target mesh at {i}")
            found = i
            break
    assert found >= 0, "Triangle not in output mesh"


if TEST_BPY_ALL or TEST_ROGUE02:
    # Shape keys and custom normals interfere with each other. If a shape key warps the
    # mesh, what direction should a custom normal face after the warp? We just preserve
    # the direction and leave it to the user to separate out the shape key if they don't
    # like the result.
    test_title("TEST_ROGUE02", "Shape keys export normals correctly")
    clear_all()
    testfile = test_file(r"tests/Out/TEST_ROGUE02.nif")
    outfile = test_file(r"tests/Out/TEST_ROGUE02_warp.nif")

    export_from_blend(r"tests\Skyrim\ROGUE02-normals.blend",
                        "Plane",
                        "SKYRIM",
                        testfile,
                        "_warp")

    nif2 = NifFile(outfile)
    shape2 = nif2.shapes[0]
    assert len(shape2.verts) == 25, f"Export shouldn't create extra vertices, found {len(shape2.verts)}"
    v = [round(x, 1) for x in shape2.verts[18]]
    assert v == [0.0, 0.0, 0.2], f"Vertex found at incorrect position: {v}"
    n = [round(x, 1) for x in shape2.normals[8]]
    assert n == [0, 1, 0], f"Normal should point along y axis, instead: {n}"


if TEST_BPY_ALL or TEST_NORMAL_SEAM:
    test_title("TEST_NORMAL_SEAM", "Normals on a split seam are seamless")
    clear_all()
    testfile = test_file(r"tests/Out/TEST_NORMAL_SEAM.nif")
    outfile = test_file(r"tests/Out/TEST_NORMAL_SEAM_Dog.nif")

    export_from_blend(r"tests\FO4\TestKnitCap.blend", "MLongshoremansCap:0",
                      "FO4", testfile)

    nif2 = NifFile(outfile)
    shape2 = nif2.shapes[0]
    target_vert = [i for i, v in enumerate(shape2.verts) if VNearEqual(v, (0.00037, 7.9961, 9.34375))]

    assert len(target_vert) == 2, f"Expect vert to have been split: {target_vert}"
    assert VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


if TEST_BPY_ALL or TEST_NIFTOOLS_NAMES:
    # We allow renaming bones according to the NifTools format. Someday this may allow
    # us to use their animation tools, but this is not that day.
    test_title("TEST_NIFTOOLS_NAMES", "Can import nif with niftools' naming convention")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\Skyrim\malebody_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones_niftools=True, 
                                 create_bones=False, scale_factor=0.1)
    arma = find_shape("MaleBody_1.nif")

    ObjectSelect([arma])
    ObjectActive(arma)
    bpy.ops.object.mode_set(mode='EDIT')
    print(f"Bone roll for 'NPC Calf [Clf].L' = {arma.data.edit_bones['NPC Calf [Clf].L'].roll}")
    for b in arma.data.edit_bones:
        b.roll += -90 * pi / 180
    print(f"Bone roll for 'NPC Calf [Clf].L' = {arma.data.edit_bones['NPC Calf [Clf].L'].roll}")
    bpy.ops.object.mode_set(mode='OBJECT')
    arma.update_from_editmode()

    bpy.ops.object.select_all(action='DESELECT')
    have_niftools = False
    try:
        bpy.ops.import_scene.nif(filepath=testfile, scale_correction=0.1)
        have_niftools = True
    except:
        pass

    if have_niftools:
        assert False, "Only one armature imported--scale factor didn't result in 2"
        assert "skeleton.nif" not in arma.data.bones, f"Root node not imported as bone"
        assert "NPC Calf [Clf].L" in arma.data.bones, f"Bones follow niftools name conventions {arma.data.bones.keys()}"
        #assert arma.data.niftools.axis_forward == "Z", f"Forward axis set to Z"
        assert 'NPC L Thigh [LThg]' not in arma.data.bones, f"No vanilla bone names: {arma.data.bones['NPC L Thigh [LThg]']}"

        inif = NifFile(testfile)
        skel = inif.reference_skel
        skel_calf = skel.nodes['CME L Thigh [LThg]']
        c = arma.data.bones["NPC Calf [Clf].L"]
        assert c.parent, f"Bones are put into a hierarchy: {c.parent}"
        assert c.parent.name == 'CME L Thigh [LThg]', f"Parent/child relationships are maintained: {c.parent.name}"

        body = find_shape("MaleUnderwearBody1:0")
        assert "NPC Calf [Clf].L" in body.vertex_groups, f"Vertex groups follow niftools naming convention: {body.vertex_groups.keys()}"


if TEST_BPY_ALL or TEST_COLLISION_MULTI:
    test_title("TEST_COLLISION_MULTI", "Can read and write shape with multiple collision shapes")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\Skyrim\grilledleeks01.nif")
    outfile = test_file(r"tests/Out/TEST_COLLISION_MULTI.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek1 = find_shape("Leek01")
    leek10 = find_shape("Leek01:0")
    leek11 = find_shape("Leek01:1")
    leek2 = find_shape("Leek02")
    leek3 = find_shape("Leek03")
    leek4 = find_shape("Leek04")
    c1 = find_shape("bhkCollisionObject", leek1.children)
    c2 = find_shape("bhkCollisionObject", leek2.children)
    assert set(leek1.children) == set( (c1, leek10, leek11) ), f"Children of Leek01 are correct: {leek1.children} == {c1}, {leek10}, {leek11}"
    
    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check ---------
    nif = NifFile(outfile)
    l1 = nif.nodes["Leek01"]
    l4 = nif.nodes["Leek04"]
    assert l1.collision_object.body.shape.blockname == "bhkConvexVerticesShape", f"Have the correct collisions"
    assert l4.collision_object.body.shape.blockname == "bhkConvexVerticesShape", f"Have the correct collisions"
    l10 = nif.shape_dict["Leek01:0"]
    l11 = nif.shape_dict["Leek01:1"]
    assert l10.parent.name == "Leek01", f"Leek01:0 parent correct: {l10.parent.name}"
    assert l11.parent.name == "Leek01", f"Leek01:0 parent correct: {l11.parent.name}"
    l40 = nif.shape_dict["Leek04:0"]
    l41 = nif.shape_dict["Leek04:1"]
    assert l40.parent.name == "Leek04", f"Leek04:0 parent correct: {l40.parent.name}"
    assert l41.parent.name == "Leek04", f"Leek04:0 parent correct: {l41.parent.name}"


if TEST_BPY_ALL or TEST_COLLISION_CONVEXVERT:
    def do_test(sf):
        test_title("TEST_COLLISION_CONVEXVERT", "Can read and write shape with convex verts collision shape at scale {sf}")
        clear_all()

        # ------- Load --------
        testfile = test_file(r"tests\Skyrim\cheesewedge01.nif")
        outfile = test_file(f"tests/Out/TEST_COLLISION_CONVEXVERT.{sf}.nif", output=True)

        bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=sf)
        #NifImporter.do_import(testfile, scale=sf)

        # Check transform
        obj = find_shape('CheeseWedge')
        assert VNearEqual(obj.location, (0,0,0)), f"Cheese wedge at right location"
        assert VNearEqual(obj.rotation_euler, (0,0,0)), f"Cheese wedge not rotated"
        assert obj.scale == Vector((1,1,1)), f"Cheese wedge scale 1"

        # Check collision info
        coll = find_shape('bhkCollisionObject')
        assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
        assert coll.parent == None, f"Collision shape has no parent"

        collbody = coll.children[0]
        assert collbody.name == 'bhkRigidBody', f"Child of collision is the collision body object"
        assert collbody['collisionFilter_layer'] == SkyrimCollisionLayer.CLUTTER.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
        assert collbody["collisionResponse"] == hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"

        collshape = collbody.children[0]
        assert collshape.name == 'bhkConvexVerticesShape', f"Collision shape is child of the collision body"
        assert collshape['bhkMaterial'] == 'CLOTH', f"Shape material is a custom property: {collshape['bhkMaterial']}"
        obj = find_shape('CheeseWedge01', collection=bpy.context.selected_objects)
        xmax1 = max([v.co.x for v in obj.data.vertices])
        xmax2 = max([v.co.x for v in collshape.data.vertices])
        assert abs(xmax1 - xmax2) < 0.5*sf, f"Max x vertex nearly the same: {xmax1} == {xmax2}"
        corner = collshape.data.vertices[0].co
        assert VNearEqual(corner, (-4.18715*sf, -7.89243*sf, 7.08596*sf)), f"Collision shape in correct position: {corner}"

        # ------- Export --------

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', scale_factor=sf)

        # ------- Check Results --------

        niforig = NifFile(testfile)
        rootorig = niforig.rootNode
        collorig = rootorig.collision_object
        bodyorig = collorig.body
        cvsorig = bodyorig.shape

        nifcheck = NifFile(outfile)
        rootcheck = nifcheck.rootNode
        collcheck = rootcheck.collision_object
        bodycheck = collcheck.body
        cvscheck = bodycheck.shape

        assert rootcheck.name == "CheeseWedge01", f"Root node name incorrect: {rootcheck.name}"
        assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"

        assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
        assert collcheck.target == rootcheck, f"Target of collision is root: {rootcheck.name}"

        assert bodycheck.blockname == "bhkRigidBody", f"Correctly wrote bhkRigidBody: {bodycheck.blockname}"

        assert cvscheck.blockname == "bhkConvexVerticesShape", f"Collision body's shape property returns the collision shape"
        assert cvscheck.properties.bhkMaterial == SkyrimHavokMaterial.CLOTH, \
            "Collision body shape material is readable"

        minxch = min(v[0] for v in cvscheck.vertices)
        maxxch = max(v[0] for v in cvscheck.vertices)
        minxorig = min(v[0] for v in cvsorig.vertices)
        maxxorig = max(v[0] for v in cvsorig.vertices)

        assert NearEqual(minxch, minxorig), f"Vertex x is correct: {minxch} == {minxorig}"
        assert NearEqual(maxxch, maxxorig), f"Vertex x is correct: {maxxch} == {maxxorig}"

        # Re-import
        #
        # There have been issues with importing the exported nif and having the 
        # collision be wrong
        clear_all()
        bpy.ops.import_scene.pynifly(filepath=outfile)

        impcollshape = find_shape("bhkConvexVerticesShape")
        zmin = min([v.co.z for v in impcollshape.data.vertices])
        assert zmin >= -0.01*sf, f"Minimum z is positive: {zmin}"

    do_test(1.0)
    do_test(0.1)

    
if TEST_BPY_ALL or TEST_COLLISION_CAPSULE:
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    def do_test(sf):
        test_title("TEST_COLLISION_CAPSULE", 
                    f"Can read and write shape with collision capsule shapes with scale {sf}")
        clear_all()

        # ------- Load --------
        testfile = test_file(r"tests\Skyrim\staff04.nif")
        outfile = test_file(f"tests/Out/TEST_COLLISION_CAPSULE.{sf}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=sf)

        staff = find_shape("3rdPersonStaff04")
        coll = find_shape("bhkCollisionObject")
        collbody = coll.children[0]
        collshape = collbody.children[0]
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

        staffmax = max((staff.matrix_world @ v.co).y for v in staff.data.vertices)
        staffmin = min((staff.matrix_world @ v.co).y for v in staff.data.vertices)
        assert NearEqual(staffmax, 68.94*sf, 0.1), f"Staff max y correct: {staffmax} == {68.94*sf}"
        assert NearEqual(staffmin, -73.88*sf, 0.1), f"Staff min y correct: {staffmin} == {-73.88*sf}"

        assert collshape.name.startswith("bhkCapsuleShape"), f"Found list collision shape: {collshape.name}"
        collmax = max((collshape.matrix_world @ v.co).y for v in collshape.data.vertices)
        collmin = min((collshape.matrix_world @ v.co).y for v in collshape.data.vertices)
        assert NearEqual(staffmax, collmax, 5), f"Collision top near staff top: {collmax} ~ {staffmax}"
        assert NearEqual(staffmin, collmin, 5), f"Collision bottom near staff botton: {collmin} ~ {staffmin}"
        v = collshape.data.vertices[5]
        assert NearEqual(v.co.z, 67.4*sf) or NearEqual(v.co.y, -67.4*sf), \
        f"Found verts where expected for {collshape.name}: {v.co}"
        assert VNearEqual(collshape.location, (0, -2.8*sf, 0.79*sf), 0.1*sf), \
            f"Collision in right location for {collshape.name}: {collshape.location})"

        # -------- Export --------
        bpy.ops.object.select_all(action='DESELECT')
        staff.select_set(True)
        coll.select_set(True)
        bsxf.select_set(True)
        invm.select_set(True)
        strd.select_set(True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', scale_factor=sf)

        # ------- Check ---------
        nifcheck = NifFile(outfile)
        staffcheck = nifcheck.shape_dict["3rdPersonStaff04:1"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        shapecheck = rbcheck.shape
        assert shapecheck.blockname == "bhkCapsuleShape", f"Got a capsule collision back {shapecheck.blockname}"

        niforig = NifFile(testfile)
        collorig = niforig.rootNode.collision_object
        rborig = collorig.body
        shapeorig = rborig.shape
        assert NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), f"Wrote the correct radius: {shapecheck.properties.radius1}"
        assert NearEqual(shapeorig.properties.point1[1], shapecheck.properties.point1[1]), f"Wrote the correct radius: {shapecheck.properties.point1[1]}"

    do_test(1.0)
    do_test(0.1)


if TEST_BPY_ALL or TEST_COLLISION_LIST:
    def run_test(sf):
        test_title("TEST_COLLISION_LIST", 
                    f"Can read and write shape with collision list and collision transform shapes with scale {sf}")
        clear_all()

        # ------- Load --------
        testfile = test_file(r"tests\Skyrim\falmerstaff.nif")
        outfile = test_file(f"tests/Out/TEST_COLLISION_LIST{sf}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, scale_factor=sf)

        staff = find_shape("Staff3rdPerson:0")
        coll = find_shape("bhkCollisionObject")
        collbody = coll.children[0]
        collshape = collbody.children[0]
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

        assert collshape.name.startswith("bhkListShape"), f"Found list collision shape: {collshape.name}"
        assert len(collshape.children) == 3, f" Collision shape has children"
    
        # -------- Export --------
        bpy.ops.object.select_all(action='DESELECT')
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")
        staff.select_set(True)
        coll.select_set(True)
        bsxf.select_set(True)
        invm.select_set(True)
        strd.select_set(True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', scale_factor=sf)

        # ------- Check ---------
        niforig = NifFile(testfile)
        stafforig = niforig.shape_dict["Staff3rdPerson:0"]
        collorig = niforig.rootNode.collision_object
        listorig = collorig.body.shape
        xfshapesorig = listorig.children[:]
        xfshapematorig = [s.properties.bhkMaterial for s in xfshapesorig]

        nifcheck = NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff3rdPerson:0"]
        collcheck = nifcheck.rootNode.collision_object
        listcheck = collcheck.body.shape
        xfshapescheck = listcheck.children[:]
        xfshapematcheck = [s.properties.bhkMaterial for s in xfshapescheck]

        assert xfshapematcheck == xfshapematorig, \
            f"Materials written to ConvexTransformShape: {xfshapematcheck} == {xfshapematorig}"

        assert listcheck.blockname == "bhkListShape", f"Got a list collision back {listcheck.blockname}"
        assert len(listcheck.children) == 3, f"Got our list elements back: {len(listcheck.children)}"

        cts0check = listcheck.children[0]
        assert cts0check.child.blockname == "bhkBoxShape", f"Found the box shape"

        cts45check = [cts for cts in listcheck.children if NearEqual(cts.transform[1][1], 0.7071, 0.01)]
        boxdiag = cts45check[0].child
        assert NearEqual(boxdiag.properties.bhkDimensions[1], 0.170421), f"Diagonal box has correct size: {boxdiag.properties.bhkDimensions[1]}"

    run_test(1.0)
    run_test(0.1)


if TEST_BPY_ALL or TEST_CHANGE_COLLISION:
    test_title("TEST_CHANGE_COLLISION", "Changing collision type works correctly")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = test_file(r"tests/Out/TEST_CHANGE_COLLISION.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    coll = find_shape('bhkCollisionObject')
    collbody = coll.children[0]
    collshape = find_shape('bhkBoxShape')
    bged = find_shape("BSBehaviorGraphExtraData")
    strd = find_shape("NiStringExtraData")
    bsxf = find_shape("BSXFlags")
    invm = find_shape("BSInvMarker")
    assert collshape.name == 'bhkBoxShape', f"Found collision shape"
    
    collshape.name = "bhkConvexVerticesShape"

    # ------- Export --------

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    coll.select_set(True)
    bged.select_set(True)
    strd.select_set(True)
    bsxf.select_set(True)
    invm.select_set(True)
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check Results --------

    nifcheck = NifFile(outfile)
    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    bodycheck = collcheck.body

    names = [x[0] for x in nifcheck.behavior_graph_data]
    assert "BGED" in names, f"Error: Expected BGED in {names}"
    bgedCheck = nifcheck.behavior_graph_data[0]
    log.debug(f"BGED value is {bgedCheck}")
    assert bgedCheck == ("BGED", "Weapons\\Bow\\BowProject.hkx", False), f"Extra data value = {bgedCheck}"
    assert not bgedCheck[2], f"Extra data controls base skeleton: {bgedCheck}"


if (TEST_BPY_ALL or TEST_COLLISION_XFORM) and bpy.app.version[0] >= 3:
    # Blender V2.x does not import the whole parent chain when appending an object from
    # another file, so don't try to run this on that version.
    test_title("TEST_COLLISION_XFORM", "Can read and write shape with collision capsule shapes")
    clear_all()

    # ------- Load --------
    outfile = test_file(r"tests/Out/TEST_COLLISION_XFORM.nif")

    append_from_file("Staff", True, r"tests\SkyrimSE\staff.blend", r"\Object", "Staff")
    append_from_file("BSInvMarker", True, r"tests\SkyrimSE\staff.blend", r"\Object", "BSInvMarker")
    append_from_file("BSXFlags", True, r"tests\SkyrimSE\staff.blend", r"\Object", "BSXFlags")
    append_from_file("NiStringExtraData", True, r"tests\SkyrimSE\staff.blend", r"\Object", "NiStringExtraData")
    append_from_file("bhkConvexVerticesShape.002", True, r"tests\SkyrimSE\staff.blend", r"\Object", "bhkConvexVerticesShape.002")

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    find_shape("Staff").select_set(True)
    find_shape("bhkCollisionObject").select_set(True)
    find_shape("NiStringExtraData").select_set(True)
    find_shape("BSXFlags").select_set(True)
    find_shape("BSInvMarker").select_set(True)
    bpy.context.view_layer.objects.active = find_shape("Staff")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check ---------
    # NOTE the collision is only on one of the tines
    nifcheck = NifFile(outfile)
    staffcheck = nifcheck.shape_dict["Staff"]
    collcheck = nifcheck.rootNode.collision_object
    rbcheck = collcheck.body
    listcheck = rbcheck.shape
    cvShapes = [c for c in listcheck.children if c.blockname == "bhkConvexVerticesShape"]
    maxz = max([v[2] for v in cvShapes[0].vertices])
    assert maxz < 0, f"All verts on collisions shape on negative z axis: {maxz}"

        
if TEST_BPY_ALL or TEST_CONNECT_POINT:
    # FO4 has a complex method of attaching shapes to other shapes in game, using
    # connect points. These can be created and manipulated in Blender.
    test_title("TEST_CONNECT_POINT", "Connect points are imported and exported")
    clear_all()

    testfile = test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    outfile = test_file(r"tests\Out\TEST_CONNECT_POINT.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    parentnames = set(['P-Barrel', 'P-Casing', 'P-Grip', 'P-Mag', 'P-Scope'])
    childnames = ['C-Receiver', 'C-Reciever']

    shotgun = next(filter(lambda x: x.name.startswith('CombatShotgunReceiver:0'), bpy.context.selected_objects))
    cpparents = list(filter(lambda x: x.name.startswith('BSConnectPointParents'), bpy.context.selected_objects))
    cpchildren = list(filter(lambda x: x.name.startswith('BSConnectPointChildren'), bpy.context.selected_objects))
    cpcasing = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Casing'), bpy.context.selected_objects))
    
    assert len(cpparents) == 5, f"Found parent connect points: {cpparents}"
    p = set(x.name.split("::")[1] for x in cpparents)
    assert p == parentnames, f"Found correct parentnames: {p}"

    assert cpchildren, f"Found child connect points: {cpchildren}"
    assert (cpchildren[0]['PYN_CONNECT_CHILD_0'] == "C-Receiver") or \
        (cpchildren[0]['PYN_CONNECT_CHILD_1'] == "C-Receiver"), \
        f"Did not find child name"

    # assert NearEqual(cpcasing.rotation_quaternion.w, 0.9098), f"Have correct rotation: {cpcasing.rotation_quaternion}"
    assert cpcasing.parent.name == "CombatShotgunReceiver", f"Casing has correct parent {cpcasing.parent.name}"

    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    ## --------- Check ----------
    nifsrc = NifFile(testfile)
    nifcheck = NifFile(outfile)
    pcheck = set(x.name.decode() for x in nifcheck.connect_points_parent)
    assert pcheck == parentnames, f"Wrote correct parent names: {pcheck}"
    pcasingsrc = [cp for cp in nifsrc.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    pcasing = [cp for cp in nifcheck.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    assert VNearEqual(pcasing.rotation[:], pcasingsrc.rotation[:]), f"Have correct rotation: {pcasing}"

    chnames = nifcheck.connect_points_child
    chnames.sort()
    assert chnames == childnames, f"Wrote correct child names: {chnames}"


if TEST_BPY_ALL or TEST_WEAPON_PART:
    # When a connect point is selected and then another part is imported that connects
    # to that point, they are connected in Blender.
    test_title("TEST_WEAPON_PART", "Weapon parts are imported at the parent connect point")
    clear_all()

    testfile = test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    partfile = test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel_1.nif")
    partfile2 = test_file(r"tests\FO4\Shotgun\DrumMag.nif")
    outfile = test_file(r"tests\Out\TEST_WEAPON_PART.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    barrelpcp = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Barrel'), bpy.context.selected_objects))
    assert barrelpcp, f"Found the connect point for barrel parts"
    magpcp = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Mag'), bpy.context.selected_objects))
    assert magpcp, f"Found the connect point for magazine parts"

    bpy.context.view_layer.objects.active = barrelpcp
    bpy.ops.import_scene.pynifly(filepath=partfile, create_bones=False, rename_bones=False)
    barrelccp = next(filter(lambda x: x.name.startswith('BSConnectPointChildren'), bpy.context.selected_objects))
    assert barrelccp, f"Barrel's child connect point found {barrelccp}"
    assert barrelccp.parent == barrelpcp, f"Child connect point parented to parent connect point: {barrelccp.parent}"


if TEST_BPY_ALL or TEST_IMPORT_MULT_CP:
    # When multiple weapon parts are imported in one command, they are connected up
    test_title("TEST_IMPORT_MULT_CP", "Can import multiple files and connect up the connect points")
    clear_all()

    testfiles = [{"name": test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")}, 
                 {"name": test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel.nif")}, 
                 {"name": test_file(r"tests\FO4\Shotgun\Stock.nif")} ]
    bpy.ops.import_scene.pynifly(files=testfiles, rename_bones=False, create_bones=False)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 5, f"Have 5 meshes: {meshes}"
    barrelparent = [obj for obj in bpy.data.objects if obj.name == 'BSConnectPointParents::P-Barrel']
    assert len(barrelparent) == 1, f"Have barrel parent connect point {barrelparent}"
    barrelchild = [obj for obj in bpy.data.objects \
                if obj.name.startswith('BSConnectPointChildren')
                        and obj['PYN_CONNECT_CHILD_0'] == 'C-Barrel']
    assert len(barrelchild) == 1, f"Have a single barrel child {barrelchild}"
    

if TEST_BPY_ALL or TEST_FURN_MARKER1:
    test_title("TEST_FURN_MARKER1", "Furniture markers work")
    clear_all()

    testfile = test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = test_file(r"tests\Out\TEST_FURN_MARKER1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 2, f"Found furniture markers: {fmarkers}"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    bench = find_shape("FarmBench01:5")
    bench.select_set(True)
    bsxf = find_shape("BSXFlags")
    bsxf.select_set(True)
    for f in bpy.data.objects:
        if f.name.startswith("BSFurnitureMarker"):
            f.select_set(True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --------- Check ----------
    nifcheck = NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 2, f"Wrote the furniture marker correctly: {len(fmcheck)}"


if TEST_BPY_ALL or TEST_FURN_MARKER2:
    test_title("TEST_FURN_MARKER2", "Furniture markers work")

    clear_all()

    testfile = test_file(r"tests\SkyrimSE\commonchair01.nif")
    outfile = test_file(r"tests\Out\TEST_FURN_MARKER2.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 1, f"Found furniture markers: {fmarkers}"
    assert VNearEqual(fmarkers[0].rotation_euler, (-pi/2, 0, 0)), f"Marker points the right direction"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    find_shape("CommonChair01:0").select_set(True)
    find_shape("BSXFlags").select_set(True)
    find_shape("BSFurnitureMarkerNode").select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --------- Check ----------
    nifcheck = NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 1, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].entry_points == 13, f"Entry point data is correct: {fmcheck[0].entry_points}"


if TEST_BPY_ALL or TEST_FO4_CHAIR:
    test_title("TEST_FO4_CHAIR", "Furniture markers are imported and exported")
    clear_all()

    testfile = test_file(r"tests\FO4\FederalistChairOffice01.nif")
    outfile = test_file(r"tests\Out\TEST_FO4_CHAIR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 4, f"Found furniture markers: {fmarkers}"
    mk = bpy.data.objects['BSFurnitureMarkerNode']
    assert VNearEqual(mk.rotation_euler, (-pi/2, 0, 0)), \
        f"Marker {mk.name} points the right direction: {mk.rotation_euler, (-pi/2, 0, 0)}"

    # -------- Export --------
    chair = find_shape("FederalistChairOffice01:2")
    fmrk = list(filter(lambda x: x.name.startswith('BSFurnitureMarkerNode'), bpy.data.objects))
    
    bpy.ops.object.select_all(action='DESELECT')
    chair.select_set(True)
    for fm in bpy.data.objects: 
        if fm.name.startswith('BSFurnitureMarkerNode'):
            fm.select_set(True)
    bpy.context.view_layer.objects.active = chair
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # --------- Check ----------
    nifcheck = NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 4, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].entry_points == 0, f"Entry point data is correct: {fmcheck[0].entry_points}"


if TEST_BPY_ALL or TEST_PIPBOY:
    test_title("TEST_PIPBOY", "Test pipboy import/export--very complex node hierarchy")
    clear_all()

    def cmp_xf(a, b):
        axf = a.xform_to_global.as_matrix()
        bxf = b.xform_to_global.as_matrix()
        assert MatNearEqual(axf, bxf), f"{a.name} transform preserved: \n{axf}\n != \n{bxf}"

    testfile = test_file(r"tests\FO4\PipBoy_Simple.nif")
    outfile = test_file(f"tests/Out/TEST_PIPBOY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    nifcheck = NifFile(outfile)
    pbb = nifcheck.nodes["PipboyBody"]
    assert pbb, f"Exported PipboyBody"
    td1 = nifcheck.nodes["TapeDeck01"]
    assert td1.parent.name == pbb.name, f"TapeDeck01 has parent {td1.parent.name}"
    tdl = nifcheck.nodes["TapeDeckLid"]
    assert tdl.parent.name == td1.name, f"TapeDeckLid has parent {tdl.parent.name}"
    tdlm = nifcheck.nodes["TapeDeckLid_mesh"]
    assert tdlm.parent.name == tdl.name, f"TapeDeckLid_mesh has parent {tdlm.parent.name}"
    tdlm1 = nifcheck.shape_dict["TapeDeckLid_mesh:1"]
    assert tdlm1.parent.name == tdlm.name, f"TapeDeckLid_mesh:1 has parent {tdlm1.parent.name}"

    niftest = NifFile(testfile)
    td1test = niftest.nodes["TapeDeck01"]
    tdltest = niftest.nodes["TapeDeckLid"]
    tdlmtest = niftest.nodes["TapeDeckLid_mesh"]
    tdlm1test = niftest.shape_dict["TapeDeckLid_mesh:1"]

    cmp_xf(td1, td1test)
    cmp_xf(tdl, tdltest)
    cmp_xf(tdlm, tdlmtest)
    cmp_xf(tdlm1, tdlm1test)


if TEST_BPY_ALL or TEST_BABY:
    # Non-human skeleton, lots of shapes under one armature.
    test_title('TEST_BABY', 'Can export baby parts')
    clear_all()

    # Can intuit structure if it's not in the file
    testfile = test_file(r"tests\FO4\baby.nif")
    outfile = test_file(r"tests\Out\TEST_BABY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    
    head = bpy.data.objects['Baby_Head:0']
    eyes = bpy.data.objects['Baby_Eyes:0']

    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    eyes.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    testnif = NifFile(outfile)
    testhead = testnif.shape_by_root('Baby_Head')
    testeyes = testnif.shape_by_root('Baby_Eyes')
    assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
    assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"
    assert testhead.blockname == "BSSubIndexTriShape", f"Error: Expected BSSubIndexTriShape on skinned shape, got {testhead.blockname}"


if TEST_BPY_ALL or TEST_ROTSTATIC:
    test_title("TEST_ROTSTATIC", "Test that statics are transformed according to the shape transform")
    clear_all()

    testfile = test_file(r"tests/Skyrim/rotatedbody.nif")
    outfile = test_file(r"tests/Out/TEST_ROTSTATIC.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = bpy.data.objects["LykaiosBody"]
    head = bpy.data.objects["FemaleHead"]
    assert body.rotation_euler[0] != (0.0, 0.0, 0.0), f"Expected rotation, got {body.rotation_euler}"

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nifcheck = NifFile(outfile)
    assert "LykaiosBody" in nifcheck.shape_dict.keys(), f"Expected LykaiosBody shape, found {[s.name for s in nifcheck.shapes]}"
    bodycheck = nifcheck.shape_dict["LykaiosBody"]

    m = Matrix(bodycheck.transform.rotation)
    assert int(m.to_euler()[0]*180/pi) == 90, f"Expected 90deg rotation, got {m.to_euler()}"


if TEST_BPY_ALL or TEST_ROTSTATIC2:
    test_title("TEST_ROTSTATIC2", "Test that statics are transformed according to the shape transform")
    clear_all()

    testfile = test_file(r"tests/FO4/Meshes/SetDressing/Vehicles/Crane03_simplified.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    glass = bpy.data.objects["Glass:0"]
    assert int(glass.location[0]) == -107, f"Locaation is incorret, got {glass.location[:]}"
    assert round(glass.matrix_world[0][1], 4) == -0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[0][1], 4)} != -0.9971"
    assert round(glass.matrix_world[2][2], 4) == 0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[2][2], 4)} != 59.2036"


if TEST_BPY_ALL or TEST_FACEBONES:
    # A few of the facebones have transforms that don't match the rest. The skin-to-bone
    # transforms have to be handled correctly or the face comes in slightly warped.
    # Also the skin_bone_C_MasterEyebrow is included in the nif but not used in the head.
    test_title("TEST_FACEBONES", "Can read and write facebones correctly")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\FO4\BaseFemaleHead_faceBones.nif")
    outfile = test_file(f"tests/Out/TEST_FACEBONES.nif", output=1)
    resfile = test_file(f"tests/Out/TEST_FACEBONES_facebones.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = find_shape("BaseFemaleHead_faceBones:0")
    maxy = max([v.co.y for v in head.data.vertices])
    assert maxy < 11.8, f"Max y not too large: {maxy}"

    assert head.parent['PYN_RENAME_BONES'], f"Armature remembered that bones were renamed {head.parent.name}"
    assert head['PYN_RENAME_BONES'], f"Head remembered that bones were renamed {head.name}"
    
    # Not sure what behavior is best. Node is in the nif, not used in the shape. Since we
    # are extending the armature, we import the bone.
    assert len([obj for obj in bpy.data.objects if obj.name.startswith("BaseFemaleHead_faceBones.nif")]) == 1, \
        f"Didn't create an EMPTY for the root Node"
    assert "skin_bone_C_MasterEyebrow" not in bpy.data.objects, f"Did load empty node for skin_bone_C_MasterEyebrow"
    assert "skin_bone_C_MasterEyebrow" in head.parent.data.bones, f"Bone not loaded for parented bone skin_bone_C_MasterEyebrow"
    # meb = bpy.data.objects["skin_bone_C_MasterEyebrow"]
    # assert meb.location.z > 120, f"skin_bone_C_MasterEyebrow in correct position"
    
    assert not VNearEqual(head.data.vertices[1523].co, Vector((1.7168, 5.8867, -4.1643))), \
        f"Vertex is at correct place: {head.data.vertices[1523].co}"

    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nifgood = NifFile(testfile)
    nifch = NifFile(resfile)
    for nm in nifgood.nodes:
        # Skip root node and bones that aren't actually used
        if nm not in ['BaseFemaleHead_faceBones.nif', 'skin_bone_C_MasterEyebrow']:
            assert nm in nifch.nodes, f"Found node {nm} in output file"
            assert XFNearEqual(nifch.nodes[nm].transform, nifgood.nodes[nm].transform), f"""
Transforms for output and input node {nm} match:
{nifch.nodes[nm].transform}
{nifgood.nodes[nm].transform}
"""
            assert XFNearEqual(nifch.nodes[nm].xform_to_global, nifgood.nodes[nm].xform_to_global), f"""
Transforms for output and input node {nm} match:
{nifch.nodes[nm].xform_to_global}
{nifgood.nodes[nm].xform_to_global}
"""

if TEST_BPY_ALL or TEST_FACEBONES_RENAME:
    test_title("TEST_FACEBONES_RENAME", "Facebones are renamed from Blender to the game's names")
    clear_all()

    testfile = test_file(r"tests/FO4/basemalehead_facebones.nif")
    outfile = test_file(r"tests/Out/TEST_FACEBONES_RENAME.nif")
    outfile2 = test_file(r"tests/Out/TEST_FACEBONES_RENAME_facebones.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert 'skin_bone_Dimple.R' in obj.vertex_groups.keys(), f"Expected munged vertex groups"
    assert 'skin_bone_Dimple.R' in obj.parent.data.bones.keys(), f"Expected munged bone names"
    assert 'skin_bone_R_Dimple' not in obj.vertex_groups.keys(), f"Expected munged vertex groups"
    assert 'skin_bone_R_Dimple' not in obj.parent.data.bones.keys(), f"Expected munged bone names"

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nif2 = NifFile(outfile2)
    assert 'skin_bone_R_Dimple' in nif2.shapes[0].bone_names, f"Expected game bone names, got {nif2.shapes[0].bone_names[0:10]}"
    

if TEST_BPY_ALL or TEST_IMP_ANIMATRON:
    # The animatrons are very complex and their pose and bind positions are different. The
    # two shapes have slightly different bind positions, though they are a small offset
    # from each other.
    test_title("TEST_IMP_ANIMATRON", "Can read a FO4 animatron nif")
    clear_all()

    testfile = test_file(r"tests/FO4/AnimatronicNormalWoman-body.nif")
    outfile = test_file(r"tests/Out/TEST_IMP_ANIMATRON.nif")
    outfile_fb = test_file(r"tests/Out/TEST_IMP_ANIMATRON.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)

    sh = find_shape('BodyLo:0')
    minv, maxv = get_obj_bbox(sh)
    assert VNearEqual(minv, Vector((-13.14, -7.83, 38.6)), 0.1), f"Bounding box min correct: {minv}"
    assert VNearEqual(maxv, Vector((14.0, 12.66, 133.5)), 0.1), f"Bounding box max correct: {maxv}"

    arma = find_shape("AnimatronicNormalWoman")
    spine2 = arma.data.bones['SPINE2']
    hand = arma.data.bones['RArm_Hand']
    handpose = arma.pose.bones['RArm_Hand']
    assert spine2.matrix_local.translation.z > 30, f"SPINE2 in correct position: {spine2.matrix_local.translation}"
    assert VNearEqual(handpose.matrix.translation, [18.1848, 2.6116, 68.6298]), f"Hand position matches Nif: {handpose.matrix.translation}"

    thighl = arma.data.bones['LLeg_Thigh']
    cp_armorleg = find_shape("BSConnectPointParents::P-ArmorLleg")
    assert cp_armorleg["pynConnectParent"] == "LLeg_Thigh", f"Connect point has correct parent: {cp_armorleg['pynConnectParent']}"
    # assert VNearEqual(cp_armorleg.location, thighl.matrix_local.translation, 0.1), \
    #     f"Connect point at correct position: {cp_armorleg.location} == {thighl.matrix_local.translation}"

    arma = find_shape('AnimatronicNormalWoman')
    assert arma, f"Found armature '{arma.name}'"
    lleg_thigh = arma.data.bones['LLeg_Thigh']
    assert lleg_thigh.parent, f"LLeg_Thigh has parent"
    assert lleg_thigh.parent.name == 'Pelvis', f"LLeg_Thigh parent is {lleg_thigh.parent.name}"

    bpy.ops.object.select_all(action='DESELECT')
    sh.select_set(True)
    find_shape('BodyLo:1').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True,
                                 export_pose=True)

    impnif = NifFile(testfile)
    nifout = NifFile(outfile_fb)
    sh_out = nifout.shapes[0]
    assert sh_out.name == 'BodyLo:0', f"Exported shape: {sh_out.name}"
    minv_out, maxv_out = get_shape_bbox(sh_out)
    assert VNearEqual(minv_out, minv), f"Minimum bounds equal: {minv_out} == {minv}"
    assert VNearEqual(maxv_out, maxv), f"Minimum bounds equal: {maxv_out} == {maxv}"
    sp2_out = nifout.nodes['SPINE2']
    assert sp2_out.parent.name == 'SPINE1', f"SPINE2 has parent {sp2_out.parent.name}"
    sp2_in = impnif.nodes['SPINE2']
    assert MatNearEqual(transform_to_matrix(sp2_out.transform), transform_to_matrix(sp2_in.transform)), \
        f"Transforms are equal: \n{sp2_out.transform}\n==\n{sp2_in.transform}"
        

if TEST_BPY_ALL or TEST_CUSTOM_BONES:
    # These nifs have bones that are not part of the vanilla skeleton.
    test_title('TEST_CUSTOM_BONES', 'Can handle custom bones correctly')
    clear_all()

    testfile = test_file(r"tests\FO4\VulpineInariTailPhysics.nif")
    testfile = test_file(r"tests\FO4\BrushTail_Male_Simple.nif")
    outfile = test_file(r"tests\Out\TEST_CUSTOM_BONES.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    nifimp = NifFile(testfile)
    bone_in_xf = nifimp.nodes['Bone_Cloth_H_003'].xform_to_global.as_matrix()

    obj = bpy.data.objects['BrushTailBase']
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    test_in = NifFile(outfile)
    new_xf = test_in.nodes['Bone_Cloth_H_003'].xform_to_global.as_matrix()
    assert MatNearEqual(bone_in_xf, new_xf), f"Bone 'Bone_Cloth_H_003' preserved (new/original):\n{new_xf}\n==\n{bone_in_xf}"
        

if TEST_BPY_ALL or TEST_COTH_DATA:
    # Cloth data is extra bones that are enabled by HDT-type physics. Since they aren't 
    # part of the skeleton they can create problems.
    test_title("TEST_COTH_DATA", "Can read and write cloth data")
    clear_all()

    testfile = test_file(r"tests/FO4/HairLong01.nif")
    outfile = test_file(r"tests/Out/TEST_COTH_DATA.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    assert 'BSClothExtraData' in bpy.data.objects.keys(), f"Found no cloth extra data in {bpy.data.objects.keys()}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["HairLong01:0"].select_set(True)
    bpy.data.objects["BSClothExtraData"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nif1 = NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected hair nif"
    assert len(nif1.cloth_data) == 1, f"Expected cloth data"
    assert len(nif1.cloth_data[0][1]) == 46257, f"Expected 46257 bytes of cloth data, found {len(nif1.cloth_data[0][1])}"


if TEST_BPY_ALL or TEST_SCALING_COLL:
    # Collisions have to be scaled with everything else if the import/export
    # has a scale factor.
    # Primarily tests collisions, but this nif has everything: collisions, root node 
    # as fade node, bone hierarchy, extra data nodes. So tests for those and also  
    # UV orientation and texture handling
    test_title("TEST_SCALING_COLL", "Collisions scale correctly on import and export")
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
    
    # Max y dimensions of collision box and bow should be close
    coll_max = collshape.matrix_world @ Vector(collshape.bound_box[6])
    print(f"Collision {Vector(collshape.bound_box[6])} -> {coll_max}")
    bow_max = obj.matrix_world @ Vector(obj.bound_box[6])
    print(f"Bow {Vector(obj.bound_box[6])} -> {bow_max}")
    assert NearEqual(coll_max[1], bow_max[1], epsilon=0.1), \
        f"Collision box just covers bow: {coll_max} ~ {bow_max}"

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


if TEST_BPY_ALL or TEST_IMP_NORMALS:
    test_title("TEST_IMP_NORMALS", "Can import normals from nif shape")
    clear_all()

    testfile = test_file(r"tests/Skyrim/cube.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # all loop custom normals point off at diagonals
    obj = bpy.context.object
    obj.data.calc_normals_split()
    for l in obj.data.loops:
        for i in [0, 1, 2]:
            assert round(abs(l.normal[i]), 3) == 0.577, f"Expected diagonal normal, got loop {l.index}/{i} = {l.normal[i]}"


if TEST_BPY_ALL or TEST_UV_SPLIT:
    test_title("TEST_UV_SPLIT", "Can split UVs properly")
    clear_all()
    filepath = test_file("tests/Out/testUV01.nif")

    verts = [(-1.0, -1.0, 0.0), 
                (1.0, -1.0, 0.0), (-1.0, 1.0, 0.0), (1.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)]
    norms = [(0.0, 0.0, 1.0), (0.0, 0.0, 2.0), (0.0, 0.0, 3.0), (0.0, 0.0, 4.0), (0.0, 0.0, 5.0), (0.0, 0.0, 6.0)]
    weights = [{0: 0.4},
                {0: 0.6},
                {0: 1.0},
                {0: 0.8},
                {0: 0.3},
                {0: 0.1}]
    tris  = [(1, 5, 4),
                (4, 2, 0),
                (1, 3, 5),
                (4, 5, 2)]
    loops = [1, 5, 4,
                4, 2, 0,
                1, 3, 5,
                4, 5, 2]
    uvs = [(0.9, 0.1), # vert 1 (tri 0)
            (0.6, 0.9), # vert 5
            (0.6, 0.1), # vert 4
            (0.4, 0.1), # vert 4 (tri 1)
            (0.1, 0.9), # vert 2
            (0.1, 0.1), # vert 0
            (0.9, 0.1), # vert 1 (tri 2)
            (0.9, 0.9), # vert 3
            (0.6, 0.9), # vert 5
            (0.4, 0.1), # vert 4 (tri 3)
            (0.4, 0.9), # vert 5
            (0.1, 0.9)] # vert 2
    new_mesh = bpy.data.meshes.new("TestUV")
    new_mesh.from_pydata(verts, [], tris)
    newuv = new_mesh.uv_layers.new(do_init=False)
    for i, this_uv in enumerate(uvs):
        newuv.data[i].uv = this_uv
    new_object = bpy.data.objects.new("TestUV", new_mesh)
    new_object.data.uv_layers.active = newuv
    bpy.context.collection.objects.link(new_object)
    bpy.context.view_layer.objects.active = new_object
    new_object.select_set(True)

    bpy.ops.export_scene.pynifly(filepath=filepath, target_game="SKYRIM")
    
    nif_in = NifFile(filepath)
    plane = nif_in.shapes[0]
    assert len(plane.verts) == 8, "Error: Exported nif doesn't have correct verts"
    assert len(plane.uvs) == 8, "Error: Exported nif doesn't have correct UV"
    assert plane.verts[5] == plane.verts[7], "Error: Split vert at different locations"
    assert plane.uvs[5] != plane.uvs[7], "Error: Split vert has different UV locations"


if TEST_BPY_ALL or TEST_JIARAN:
    test_title("TEST_JIARAN", "Armature with no stashed transforms exports correctly")
    clear_all()
    outfile =test_file(r"tests/Out/TEST_JIARAN.nif")
     
    export_from_blend(r"tests\SKYRIMSE\jiaran.blend", "hair.001", 'SKYRIMSE', outfile)

    nif1 = NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected Jiaran nif"


print("""
############################################################
##                                                        ##
##                    TESTS DONE                          ##
##                                                        ##
############################################################
""")
