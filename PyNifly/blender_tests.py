"""Automated tests for pyNifly export/import addon

Convenient setup for running these tests here: 
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""
import os
import sys
import math
import pathlib
import bpy
import bpy_types
from mathutils import Matrix, Vector, Quaternion, Euler
import test_tools as TT
import niflytools as NT
import nifdefs
import pynifly as pyn
import xml.etree.ElementTree as xml
import blender_defs as BD
from trihandler import *

import importlib
import skeleton_hkx
import shader_io
importlib.reload(pyn)
importlib.reload(TT)
importlib.reload(BD)
importlib.reload(shader_io)
importlib.reload(skeleton_hkx)

log = logging.getLogger("pynifly")
log.setLevel(logging.DEBUG)


def TEST_BODYPART_SKY():
    # Basic test that a Skyrim bodypart is imported correctly. 
    # Verts are organized around the origin, but skin transform is put on the shape 
    # and that lifts them to the head position.  
    TT.test_title("TEST_BODYPART_SKY", "Can import a Skyrim head with armature")
    TT.clear_all()
    testfile = TT.test_file("tests\Skyrim\malehead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Importer leaves any imported shapes as the selected object.
    male_head = bpy.context.object
    assert male_head.name == 'MaleHeadIMF', f"Have correct name: {male_head.name}"
    
    # Importer creates an armature for the skinned shape.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma, f"Found armature"

    # Root node imported and parents other objects. We do not parent the head to the 
    # armature--it's not a parent/child relationship in the nif so this seems to reflect
    # the nif better.
    assert male_head.parent.name == "MaleHead.nif:ROOT", f"Head parented to root: {male_head.parent.name}"
    assert arma.parent.name == "MaleHead.nif:ROOT", f"armature parented to root: {arma.parent.name}"

    # Importer positions head conveniently.
    assert round(male_head.location.z, 0) == 120, "Should be elevated to position"
    maxz = max([v.co.z for v in male_head.data.vertices])
    assert TT.NearEqual(maxz, 11.5, epsilon=0.1), f"Max Z ~ 11.5: {maxz}"
    minz = min([v.co.z for v in male_head.data.vertices])
    assert TT.NearEqual(minz, -11, epsilon=0.1), f"Min Z ~ -11: {minz}"

    
def TEST_BODYPART_FO4():
    # Basic test that a FO4 bodypart imports correctly. 
    # Verts are organized around the origin but the skin-to-bone transforms are 
    # all consistent, so they are put on the shape.
    TT.test_title("TEST_BODYPART_FO4", "Can import a FO4 head with armature")
    TT.clear_all()
    testfile = TT.test_file("tests\FO4\BaseMaleHead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    male_head = bpy.data.objects["BaseMaleHead:0"]
    assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
    assert 'pynRoot' in male_head.parent, "Parenting mesh to root"
    maxz = max([v.co.z for v in male_head.data.vertices])
    assert TT.NearEqual(maxz, 8.3, epsilon=0.1), f"Max Z ~ 8.3: {maxz}"
    minz = min([v.co.z for v in male_head.data.vertices])
    assert TT.NearEqual(minz, -12.1, epsilon=0.1), f"Min Z ~ -12.1: {minz}"


def TEST_SKYRIM_XFORM():
    TT.test_title("TEST_SKYRIM_XFORM", "Can read & write the Skyrim shape transforms")
    TT.clear_all()
    testfile = TT.test_file(r"tests/Skyrim/MaleHead.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SKYRIM_XFORM.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert int(obj.location[2]) == 120, f"Shape offset not applied to head, found {obj.location[2]}"

    # Export the currently selected object, which import should have set to the head.
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nifcheck = pyn.NifFile(outfile)
    headcheck = nifcheck.shapes[0]

    # Make sure we didn't export the root
    assert headcheck.parent.name == nifcheck.rootName, f"Head parented to root"

    assert int(headcheck.transform.translation[2]) == 120, f"Shape offset not written correctly, found {headcheck.transform.translation[2]}"
    assert int(headcheck.global_to_skin.translation[2]) == -120, f"Shape global-to-skin not written correctly, found {headcheck.global_to_skin.translation[2]}"


def TEST_SKIN_BONE_XF():
    # The Argonian head has no global-to-skin transform and the bone pose locations are
    # exactly the vanilla locations, and yet the verts are organized around the origin.
    # The head is lifted into position with the skin-to-bone transforms (same way as FO4).
    TT.test_title("TEST_SKIN_BONE_XF", "Skin-to-bone transforms work correctly")
    TT.clear_all()

    testfile = TT.test_file(r"tests\SkyrimSE\maleheadargonian.nif")
    outfile = TT.test_file(r"tests\out\TEST_SKIN_BONE_XF.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TT.find_object("_ArgonianMaleHead", bpy.context.selected_objects, fn=lambda x: x.name)
    assert TT.NearEqual(head.location.z, 120.344), f"Head is positioned at head position: {head.location}"
    minz = min(v[2] for v in head.bound_box)
    maxz = max(v[2] for v in head.bound_box)
    assert minz < 0, f"Head extends below origin: {minz}"
    assert maxz > 0, f"Head extends above origin: {maxz}"

    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    spine2_xf = arma.data.bones['NPC Spine2'].matrix_local
    head_xf = arma.data.bones['NPC Head'].matrix_local
    assert TT.VNearEqual(head_xf.translation, (-0.0003, -1.5475, 120.3436)), f"Head position at 120: {head_xf.translation}"
    assert TT.VNearEqual(spine2_xf.translation, (0.0, -5.9318, 91.2488)), f"Spine2 position at 91: {spine2_xf.translation}"

    spine2_pose_xf = arma.pose.bones['NPC Spine2'].matrix
    head_pose_xf = arma.pose.bones['NPC Head'].matrix
    assert TT.VNearEqual(head_pose_xf.translation, Vector((-0.0003, -1.5475, 120.3436))), f"Head pose position at 120: {head_pose_xf.translation}"
    assert TT.VNearEqual(spine2_pose_xf.translation, Vector((0.0000, -5.9318, 91.2488))), f"Spine2 pose position at 91: {spine2_pose_xf.translation}"

    head_nif = pyn.NifFile(testfile)
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

    nifcheck = pyn.NifFile(outfile)
    headcheck = nifcheck.shapes[0]
    sk2b_spine = headcheck.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
    assert TT.NearEqual(sk2b_spine.translation[2], 29.419632), f"Have correct z: {sk2b_spine.translation[2]}"


def TEST_IMP_EXP_SKY():
    # Round trip of ordinary Skyrim armor, with and without scale factor.
    TT.test_title("TEST_IMP_EXP_SKY", "Can read the armor nif and spit it back out")

    testfile = TT.test_file(r"tests/Skyrim/armor_only.nif")

    def do_test(blendxf):
        log.debug(f"\nTesting with blender transform {blendxf}")
        TT.clear_all()
        outfile = TT.test_file(f"tests/Out/TEST_IMP_EXP_SKY_{blendxf}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=blendxf)

        impnif = pyn.NifFile(testfile)
        armorin = impnif.shape_dict['Armor']
        armor = TT.find_shape('Armor')

        vmin, vmax = TT.get_obj_bbox(armor)
        assert TT.VNearEqual(vmin, Vector([-30.32, -13.31, -90.03]), 0.1), f"Armor min is correct: {vmin}"
        assert TT.VNearEqual(vmax, Vector([30.32, 12.57, -4.23]), 0.1), f"Armor max is correct: {vmax}"
        assert TT.NearEqual(armor.location.z, 120.34, 0.01), f"{armor.name} in lifted position: {armor.location.z}"
        arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
        assert arma.name == BD.arma_name("Scene Root"), f"armor has parent: {arma}"

        pelvis = arma.data.bones['NPC Pelvis']
        pelvis_pose = arma.pose.bones['NPC Pelvis'] 
        assert pelvis.parent.name == 'CME LBody', f"Pelvis has correct parent: {pelvis.parent}"
        assert TT.VNearEqual(pelvis.matrix_local.translation, pelvis_pose.matrix.translation), \
            f"Pelvis pose position matches bone position: {pelvis.matrix_local.translation} == {pelvis_pose.matrix.translation}"

        bpy.ops.object.select_all(action='DESELECT')
        armor.select_set(True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM", use_blender_xf=blendxf)

        nifout = pyn.NifFile(outfile)

        TT.compare_shapes(armorin, nifout.shape_dict['Armor'], armor, e=0.01)
        TT.check_unweighted_verts(nifout.shape_dict['Armor'])

    do_test(False)
    do_test(True)
        

def TEST_IMP_EXP_SKY_2():
    # Basic test that the import/export round trip works on nifs with multiple bodyparts. 
    # The body in this nif has no skin transform and the verts are where they appear
    # to be. The armor does have the usual transform on the shape and the skin, and the
    # verts are all below the origin. They have to be loaded into one armature.
    TT.test_title("TEST_IMP_EXP_SKY_2", "Can read the armor nif with two shapes and spit it back out")
    TT.clear_all()

    #testfile = TT.test_file(r"tests/Skyrim/test.nif") 
    # 
    # The test.nif meshes are a bit wonky--one was pasted in by hand from SOS, the other
    # is a vanilla armor. The ForearmTwist2.L bind rotation is off by some hundredths.  
    # So do the test with the vanilla male body, which has two parts and is consistent.
    testfile = TT.test_file(r"tests/Skyrim/malebody_1.nif")
    # skelfile = TT.test_file(r"tests/Skyrim/skeleton_vanilla.nif")
    outfile = TT.test_file(r"tests/Out/TEST_IMP_EXP_SKY_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    assert len([x for x in bpy.data.objects if x.type=='ARMATURE']) == 1, \
        f"Both shapes brought in under one armor"
    body = TT.find_shape('MaleUnderwearBody:0')
    armor = TT.find_shape('MaleUnderwear_1')
    assert TT.VNearEqual(armor.location, (-0.0003, -1.5475, 120.3436)), \
        f"Armor is raised to match body: {armor.location}"

    BD.ObjectSelect([body, armor])
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nifout = pyn.NifFile(outfile)
    impnif = pyn.NifFile(testfile)  
    TT.compare_shapes(impnif.shape_dict['MaleUnderwearBody:0'], nifout.shape_dict['MaleUnderwearBody:0'], body, e=0.01)
    TT.compare_shapes(impnif.shape_dict['MaleUnderwear_1'], nifout.shape_dict['MaleUnderwear_1'], armor, e=0.01)

    TT.check_unweighted_verts(nifout.shape_dict['MaleUnderwearBody:0'])
    TT.check_unweighted_verts(nifout.shape_dict['MaleUnderwear_1'])
    assert TT.NearEqual(body.location.z, 120.343582, 0.01), f"{body.name} in lifted position: {body.location.z}"
    assert TT.NearEqual(armor.location.z, 120.343582, 0.01), f"{armor.name} in lifted position: {armor.location.z}"
    assert "NPC R Hand [RHnd]" not in bpy.data.objects, f"Did not create extra nodes representing the bones"
        

def TEST_IMP_EXP_FO4():
    TT.test_title("TEST_IMP_EXP_FO4", "Can read the body nif and spit it back out")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\BTMaleBody.nif")
    outfile = TT.test_file(r"tests/Out/TEST_IMP_EXP_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    impnif = pyn.NifFile(testfile)
    body = TT.find_shape('BaseMaleBody:0')
    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    bodyin = impnif.shape_dict['BaseMaleBody:0']

    assert not TT.VNearEqual(body.location, [0, 0, 0], epsilon=1), f"Body is repositioned: {body.location}"
    assert arma.name == BD.arma_name("Scene Root"), f"Body parented to armature: {arma.name}"
    assert arma.data.bones['Pelvis_skin'].matrix_local.translation.z > 0, f"Bones translated above ground: {arma.data.bones['NPC Pelvis'].matrix_local.translation}"
    assert "Scene Root" not in arma.data.bones, "Did not import the root node"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nifout = pyn.NifFile(outfile)
    bodyout = nifout.shape_dict['BaseMaleBody:0']

    TT.compare_shapes(bodyin, bodyout, body, e=0.001, ignore_translations=True)


def TEST_IMP_EXP_FO4_2():
    TT.test_title("TEST_IMP_EXP_FO4_2", "Can read the body armor with 2 parts")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\Pack_UnderArmor_03_M.nif")
    outfile = TT.test_file(r"tests/Out/TEST_IMP_EXP_FO4_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TT.find_shape('BaseMaleBody_03:0')
    armor = TT.find_shape('Pack_UnderArmor_03_M:0')
    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    assert body.location.z > 120, f"Body has correct transform: {body.location}"
    assert armor.location.z > 120, f"Armor has correct transform: {armor.location}"
    assert arma.data.bones['Neck'].matrix_local.translation.z > 100, \
        f"Neck has correct position: {arma.data.bones['Neck'].matrix_local.translation}"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    armor.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nifout = pyn.NifFile(outfile)
    bodyout = nifout.shape_dict['BaseMaleBody_03:0']
    armorout = nifout.shape_dict['Pack_UnderArmor_03_M:0']

    impnif = pyn.NifFile(testfile)
    bodyin = impnif.shape_dict['BaseMaleBody_03:0']
    armorin = impnif.shape_dict['Pack_UnderArmor_03_M:0']
    TT.compare_shapes(bodyin, bodyout, body, e=0.001, ignore_translations=True)
    TT.compare_shapes(armorin, armorout, armor, e=0.001, ignore_translations=True)


def TEST_ROUND_TRIP():
    # Test out basic import/export
    TT.test_title("TEST_ROUND_TRIP", "Can do the full round trip: nif -> blender -> nif -> blender")
    TT.clear_all()
    testfile = TT.test_file("tests/Skyrim/test.nif")
    outfile1 = TT.test_file("tests/Out/testSkyrim03.nif")

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


def TEST_BPY_PARENT_A():
    TT.test_title("TEST_BPY_PARENT_A", 'Maintain armature structure')
    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\test.nif")
    
    # Can intuit structure if it's not in the file
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.data.objects[BD.arma_name("Scene Root")]
    assert obj.data.bones['NPC Hand.R'].parent.name == 'CME Forearm.R', f"Error: Should find forearm as parent: {obj.data.bones['NPC Hand.R'].parent.name}"
    print(f"Found parent to hand: {obj.data.bones['NPC Hand.R'].parent.name}")


def TEST_BPY_PARENT_B():
    TT.test_title("TEST_BPY_PARENT_B", 'Maintain armature structure')
    TT.clear_all()
    testfile2 = TT.test_file(r"tests\FO4\bear_tshirt_turtleneck.nif")
    
    ## Can read structure if it comes from file
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    obj = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
    assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3.R', "Error: Should find forearm as parent"


def TEST_RENAME():
    TT.test_title("TEST_RENAME", "Test that NOT renaming bones works correctly")
    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\femalebody_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_rename_bones=False)

    body = bpy.context.object
    vgnames = [x.name for x in body.vertex_groups]
    vgxl = list(filter(lambda x: ".L" in x or ".R" in x, vgnames))
    assert len(vgxl) == 0, f"Expected no vertex groups renamed, got {vgxl}"

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    armnames = [b.name for b in arma.data.bones]
    armxl = list(filter(lambda x: ".L" in x or ".R" in x, armnames))
    assert len(armxl) == 0, f"Expected no bones renamed in armature, got {armxl}"


def TEST_CONNECTED_SKEL():
    # Check that the bones of the armature are connected correctly.
    TT.test_title('TEST_CONNECTED_SKEL', 'Can import connected skeleton')
    TT.clear_all()

    bpy.ops.object.select_all(action='DESELECT')
    testfile = TT.test_file(r"tests\FO4\vanillaMaleBody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    s = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert s.type == 'ARMATURE', f"Imported the skeleton {s}" 
    assert 'Leg_Thigh.L' in s.data.bones.keys(), "Error: Should have left thigh"
    lthigh = s.data.bones['Leg_Thigh.L']
    assert lthigh.parent.name == 'Pelvis', "Error: Thigh should connect to pelvis"
    assert TT.VNearEqual(lthigh.head_local, (-6.6151, 0.0005, 68.9113)), f"Thigh head in correct location: {lthigh.head_local}"
    
    # Tail location depends on whether we rotate the bones.
    # assert TT.VNearEqual(lthigh.tail_local, (-7.2513, -0.1925, 63.9557)), f"Thigh tail in correct location: {lthigh.tail_local}"


def TEST_DRAUGR_IMPORT_A():
    # This nif uses the draugr skeleton, which has bones named like human bones but with
    # different positions--BUT the hood was made for the human skeleton so the bind
    # position of its bones don't match the draugr skeleton. Bones defined by the hood are
    # given the human bind position--the rest come from the reference skeleton and use
    # those bind positions. 
    TT.test_title("TEST_DRAUGR_IMPORT_A", "Import hood, extend skeleton, non-vanilla pose")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\SkyrimSE\draugr lich01 hood.nif")
    skelfile = TT.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TT.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_A.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, do_create_bones=True)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TT.find_shape("Helmet")
    hood = TT.find_shape("Hood")
    bone1 = skel.data.bones['NPC UpperArm.R']
    pose1 = skel.pose.bones['NPC UpperArm.R']
    bone2 = skel.data.bones['NPC UpperarmTwist1.R']
    pose2 = skel.pose.bones['NPC UpperarmTwist1.R']

    # Bones referenced by the hood have bind position from humans but pose position from
    # draugr. The rest of them use bind and pose position from draugr.
    assert not TT.MatNearEqual(bone1.matrix_local, bone2.matrix_local), \
        f"Bones should NOT have the same bind position: \n{bone1.matrix_local} != \n{bone2.matrix_local}"
    assert TT.VNearEqual(pose1.matrix.translation, pose2.matrix.translation), \
        f"Bones should have same pose position: {pose1.matrix.translation} != {pose2.matrix.translation}"
    
    # Create_bones means that the bones are all connected up
    assert bone1.parent.name == 'NPC Clavicle.R', f"UpperArm parent correct: {bone1.parent.name}"
    assert bone2.parent.name == 'NPC UpperArm.R', f"UpperArmTwist parent correct: {bone2.parent.name}"
    

def TEST_DRAUGR_IMPORT_B():
    # This hood uses non-human bone node positions and we don't extend the skeleton, so
    # bones are given the bind position from the hood but the pose position from the nif.
    # Since the pose is not a pure translation, we do not put a transform on the hood
    # shape.
    TT.test_title("TEST_DRAUGR_IMPORT_B", "Import hood, don't extend skeleton, non-vanilla pose")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\SkyrimSE\draugr lich01 hood.nif")
    skelfile = TT.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TT.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_B.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, do_create_bones=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TT.find_shape("Helmet")
    hood = TT.find_shape("Hood")
    bone1 = arma.data.bones['NPC UpperarmTwist1.R']
    pose1 = arma.pose.bones['NPC UpperarmTwist1.R']

    # Lots of bones in this nif are not used in the hood. Bones used in the hood have pose
    # and bind locations. The rest only have pose locations and are brought in as Empties.
    assert not TT.VNearEqual(pose1.matrix.translation, bone1.matrix_local.translation), \
        f"Pose position is not bind position: {pose1.matrix.translation} != {bone1.matrix_local.translation}"
    

def TEST_DRAUGR_IMPORT_C():
    # The helm has bones that are in the draugr's vanilla bind position.
    TT.test_title("TEST_DRAUGR_IMPORT_C", "Import helm, don't extend skeleton")
    TT.clear_all()

    testfile = TT.test_file(r"tests\SkyrimSE\draugr lich01 helm.nif")
    skelfile = TT.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TT.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_C.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, do_create_bones=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TT.find_shape("Helmet")
    bone1 = skel.data.bones['NPC Head']
    pose1 = skel.pose.bones['NPC Head']

    assert not TT.VNearEqual(bone1.matrix_local.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not in vanilla bind position: {bone1.matrix_local.translation}"
    assert not TT.VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not posed in vanilla position: {pose1.matrix_local.translation}"


def TEST_DRAUGR_IMPORT_D():
    # Fo the helm, when we import WITH adding bones, we get a full draugr skeleton.
    TT.test_title("TEST_DRAUGR_IMPORT_D", "Import helm, do extend skeleton")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\SkyrimSE\draugr lich01 helm.nif")
    skelfile = TT.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TT.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_D.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, do_create_bones=True)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TT.find_shape("Helmet")
    bone1 = skel.data.bones['NPC Head']
    pose1 = skel.pose.bones['NPC Head']
    bone2 = skel.data.bones['NPC Spine2']
    pose2 = skel.pose.bones['NPC Spine2']

    assert TT.VNearEqual(bone1.matrix_local.translation, [-0.015854, -2.40295, 134.301]), \
        f"Head bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert not TT.VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436], epsilon=2.0), \
        f"Head bone not posed in vanilla position: {pose1.matrix.translation}"

    assert TT.VNearEqual(bone2.matrix_local.translation, [0.000004, -5.83516, 102.358]), \
        f"Spine bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert TT.VNearEqual(pose2.matrix.translation, [0.0000, -5.8352, 102.3579]), \
        f"Spine bone posed in draugr position: {pose2.matrix.translation}"
    
    assert bone2.parent.name == 'NPC Spine1', \
        f"Spine bone has correct parent: {bone2.parent.name}"
    

def TEST_DRAUGR_IMPORT_E():
    # This nif has two shapes and the bind positions differ. The hood bind position is
    # human, and it's posed to the draugr position. The draugr hood is bound at pose
    # position, so pose and bind positions are the same. The only solution is to import as
    # two skeletons and let the user sort it out. We could also add a flag to "import at
    # pose position". We lose the bind position info but end up with the shapes parented
    # to one armature.
    TT.test_title("TEST_DRAUGR_IMPORT_E", "Import of this draugr mesh positions hood correctly")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\SkyrimSE\draugr lich01 simple.nif")
    skelfile = TT.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TT.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_E.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, do_create_bones=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TT.find_shape("Helmet")
    hood = TT.find_shape("Hood")
    importnif = pyn.NifFile(testfile)
    importhelm = importnif.shape_dict['Helmet']
    importhood = importnif.shape_dict['Hood']
    print(f"Helm max y = {max(v[1] for v in importnif.shape_dict['Helmet'].verts)}")

    # No matter what transforms we apply to Blender shapes or how the skinning moves 
    # them about, the vert locations should match the nif.
    TT.assert_equiv(max(v.co.x for v in helm.data.vertices), 
                      max(v[0] for v in importhelm.verts), "helm max x")
    TT.assert_equiv(min(v.co.x for v in helm.data.vertices), 
                      min(v[0] for v in importhelm.verts), "helm min x")
    TT.assert_equiv(max(v.co.y for v in helm.data.vertices), 
                      max(v[1] for v in importhelm.verts), "helm max y")
    TT.assert_equiv(min(v.co.y for v in helm.data.vertices), 
                      min(v[1] for v in importhelm.verts), "helm min y")
    TT.assert_equiv(max(v.co.z for v in helm.data.vertices), 
                      max(v[2] for v in importhelm.verts), "helm max z")
    TT.assert_equiv(min(v.co.z for v in helm.data.vertices), 
                      min(v[2] for v in importhelm.verts), "helm min z")
    
    TT.assert_equiv(max(v.co.x for v in hood.data.vertices), 
                      max(v[0] for v in importhood.verts), "hood max x")
    TT.assert_equiv(min(v.co.x for v in hood.data.vertices), 
                      min(v[0] for v in importhood.verts), "hood min x")
    TT.assert_equiv(max(v.co.y for v in hood.data.vertices), 
                      max(v[1] for v in importhood.verts), "hood max y")
    TT.assert_equiv(min(v.co.y for v in hood.data.vertices), 
                      min(v[1] for v in importhood.verts), "hood min y")
    TT.assert_equiv(max(v.co.z for v in hood.data.vertices), 
                      max(v[2] for v in importhood.verts), "hood max z")
    TT.assert_equiv(min(v.co.z for v in hood.data.vertices), 
                      min(v[2] for v in importhood.verts), "hood min z")
    
    headbone = skel.data.bones['NPC Head']
    headpose = skel.pose.bones['NPC Head']

    # Helm bounding box has to be contained within the hood's bounding box (in world space).
    helm_bb = TT.get_obj_bbox(helm, worldspace=True)
    hood_bb = TT.get_obj_bbox(hood, worldspace=True)
    TT.assert_le(hood_bb[0][0], helm_bb[0][0], "min x")
    TT.assert_gt(hood_bb[1][0], helm_bb[1][0], "max x")
    TT.assert_le(hood_bb[0][1], helm_bb[0][1], "min y")
    TT.assert_gt(hood_bb[1][1], helm_bb[1][1], "max y")
    TT.assert_le(hood_bb[0][2], helm_bb[0][2], "min z")
    TT.assert_gt(hood_bb[1][2], helm_bb[1][2], "max z")

    # Because the hood came from the human skeleton but the helm from draugr, the bone
    # positions don't match. They had to be brought in under separate armatures.
    arma_helm = next(a.object for a in helm.modifiers if a.type == 'ARMATURE')
    arma_hood = next(a.object for a in hood.modifiers if a.type == 'ARMATURE')
    assert arma_helm != arma_hood, f"Parents are different: {arma_helm} != {arma_hood}"

    # Not extending skeletons, so each armature just has the bones needed
    assert arma_helm.data.bones.keys() == ["NPC Head"], f"Helm armature has correct bones: {helm.parent.data.bones.keys()}"

    # Hood has pose location different from rest
    bone1 = arma_hood.data.bones['NPC Head']
    pose1 = arma_hood.pose.bones['NPC Head']

    assert not TT.VNearEqual(bone1.matrix_local.translation, pose1.matrix.translation), \
        f"Pose and bind locaations differ: {bone1.matrix_local.translation} != {pose1.matrix.translation}"
    

def TEST_SCALING_BP():
    TT.test_title("TEST_SCALING_BP", "Can scale bodyparts")
    TT.clear_all()

    testfile = TT.test_file(r"tests\Skyrim\malebody_1.nif")
    outfile = TT.test_file(r"tests\Out\TEST_SCALING_BP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 rename_bones_niftools=True,
                                 use_blender_xf=True)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    b = arma.data.bones['NPC Spine1 [Spn1]']
    bw = arma.matrix_world @ b.matrix_local
    assert TT.NearEqual(bw.translation.z, 8.1443), f"Scale correctly applied: {bw.translation}"
    body = TT.find_shape("MaleUnderwearBody:0")
    blw = arma.matrix_world @ body.location
    assert TT.NearEqual(blw.z, 12, 0.1), f"Object translation correctly applied: {blw}"
    bodymax = max([(arma.matrix_world @ v.co).z for v in body.data.vertices])
    bodymin = min([(arma.matrix_world @ v.co).z for v in body.data.vertices])
    assert bodymax < 0, f"Max z is less than 0: {bodymax}"
    assert bodymin >= -12, f"Max z is greater than -12: {bodymin}"

    # Orientation - chest vertex in front of back.
    vchest = body.data.vertices[228].co
    vback = body.data.vertices[713].co
    assert vchest.y > vback.y, f"Chest is in front of back: {vchest.y} > {vback.y}"

    # But Blender orientation is the opposite.
    vchestw = arma.matrix_world @ body.data.vertices[228].co
    vbackw = arma.matrix_world @ body.data.vertices[713].co
    assert vchestw.y < vbackw.y, f"Chest is in front of back in blender: {vchestw.y} < {vbackw.y}"


    # Test export scaling is correct. We don't have to specify it because it will pick up
    # the scaling from the import by default.
    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM", 
                                 rename_bones_niftools=True) 

    nifcheck = pyn.NifFile(outfile)
    bodycheck = nifcheck.shape_dict["MaleUnderwearBody:0"]
    assert TT.NearEqual(bodycheck.transform.scale, 1.0), f"Scale is 1: {bodycheck.transform.scale}"
    assert TT.NearEqual(bodycheck.transform.translation[2], 120.3, 0.1), \
        f"Translation is correct: {list(bodycheck.transform.translation)}"
    bmaxout = max(v[2] for v in bodycheck.verts)
    bminout = min(v[2] for v in bodycheck.verts)
    assert bmaxout-bminout > 100, f"Shape scaled up on ouput: {bminout}-{bmaxout}"
    assert bodycheck.verts[228][1] > bodycheck.verts[713][1], f"Chest is in front of back: {bodycheck.verts[228][1]} > {bodycheck.verts[713][1]}"


def TEST_IMP_EXP_SCALE_2():
    # Regression: Making sure that the scale factor doesn't mess up importing under one
    # armature.
    TT.test_title("TEST_IMP_EXP_SCALE_2", "Can read the body nif scaled")
    TT.clear_all()

    testfile = TT.test_file(r"tests/Skyrim/malebody_1.nif")
    outfile = TT.test_file(r"tests/Out/TEST_IMP_EXP_SCALE_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)

    armatures = [x for x in bpy.data.objects if x.type=='ARMATURE']
    assert len(armatures) == 1, f"Have just one armature"
    body = TT.find_shape('MaleUnderwearBody:0')
    armor = TT.find_shape('MaleUnderwear_1')
    body_arma = next(a.object for a in body.modifiers if a.type == 'ARMATURE')
    armor_arma = next(a.object for a in armor.modifiers if a.type == 'ARMATURE')
    assert body_arma == armor_arma, f"Both shapes brought in under one armature"

    # We imported scaled down and rotated 180.
    assert TT.VNearEqual((armor_arma.matrix_world @ armor.location), (-0.0, 0.15475, 12.03436)), \
        f"Armor is raised to match body: {armor.location}"
    
    
def TEST_ARMATURE_EXTEND():
    # Can import a shape with an armature and then import another shape to the same armature. 
    TT.test_title("TEST_ARMATURE_EXTEND", "Can extend an armature with a second NIF")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\FO4\MaleBody.nif")
    testfile2 = TT.test_file(r"tests\FO4\BaseMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma.type == 'ARMATURE', f"Selected oject is child of armature: {arma.name}"
    bpy.context.view_layer.objects.active = arma
    assert "SPINE1" in arma.data.bones, "Found neck bone in skeleton"
    assert not "HEAD" in arma.data.bones, "Did not find head bone in skeleton"
    assert "Leg_Calf.L" in arma.data.bones, f"Loaded bones not used by shape"
    assert arma.data.bones['SPINE2'].matrix_local.translation.z > 0, \
        f"Armature in basic position: {arma.data.bones['SPINE2'].matrix_local.translation}"

    # When we import a shape where the pose-to-bind transform is consistent, we use that 
    # transform on the blender shape for ease of editing. We can then import another body
    # part to the same armature.
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    new_arma = next(a.object for a in bpy.context.object.modifiers if a.type == 'ARMATURE')
    assert new_arma == arma, f"Have same armature parent: {bpy.context.object.parent.name}"
    assert len([o for o in bpy.data.objects if o.type == 'ARMATURE']) == 1, f"Have only one armature"
    assert "HEAD" in arma.data.bones, "Found head bone in skeleton"

    head = TT.find_shape("BaseMaleHead:0")
    body = TT.find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = TT.find_vertex(head.data, target_v)
    v_body = TT.find_vertex(body.data, target_v)
    assert TT.VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        f"Head and body verts align"
    assert TT.MatNearEqual(head.matrix_world, body.matrix_world), f"Shape transforms match"


def TEST_ARMATURE_EXTEND_BT():
    # The Bodytalk body has bind positions consistent with vanilla, but the skin 
    # transform is different, which leaves a slight gap at the neck. For now, live 
    # with this.
    #  
    # The FO4 body nif does not use all bones from the skeleton, e.g. LLeg_Calf. If we're 
    # adding missing skeleton bones, we have to get them from the reference skeleton,
    # which pyNifly handles, and put them into the skeleton consistently with the rest.
    TT.test_title("TEST_ARMATURE_EXTEND", "Can extend an armature with a second NIF")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\FO4\BTBaseMaleBody.nif")
    testfile2 = TT.test_file(r"tests\FO4\BaseMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma.type == 'ARMATURE', f"Found armature"
    bpy.context.view_layer.objects.active = arma
    assert "SPINE1" in arma.data.bones, "Found neck bone in skeleton"
    assert not "HEAD" in arma.data.bones, "Did not find head bone in skeleton"
    assert "Leg_Calf.L" in arma.data.bones, f"Loaded bones not used by shape"
    assert arma.data.bones['SPINE2'].matrix_local.translation.z > 0, \
        f"Armature in basic position: {arma.data.bones['SPINE2'].matrix_local.translation}"

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    
    assert len([o for o in bpy.data.objects if o.type=='ARMATURE']) == 1, f"Have just one armature"
    assert "HEAD" in arma.data.bones, "Found head bone in skeleton"

    head = TT.find_shape("BaseMaleHead:0")
    body = TT.find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = TT.find_vertex(head.data, target_v)
    v_body = TT.find_vertex(body.data, target_v)
    assert TT.VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        f"Head and body verts align"
    # Shape transforms are different between vanilla head and BT body.
    #assert TT.MatNearEqual(head.matrix_world, body.matrix_world), f"Shape transforms match"


def TEST_EXPORT_WEIGHTS():
    # Simple test to see that when vertex groups are associated with bone weights they are
    # written correctly.
    # 
    # Also check that when we have multiple objects under a skeleton and only select one,
    # only that one gets written. 
    TT.test_title("TEST_EXPORT_WEIGHTS", "Import and export with weights")
    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\test.nif")
    filepath_armor = TT.test_file("tests/out/testArmorSkyrim02.nif")
    filepath_armor_fo = TT.test_file(r"tests\Out\testArmorFO02.nif")
    filepath_body = TT.test_file(r"tests\Out\testBodySkyrim02.nif")

    # Import body and armor
    bpy.ops.import_scene.pynifly(filepath=testfile)
    the_armor = bpy.data.objects["Armor"]
    the_body = bpy.data.objects["MaleBody"]
    assert 'NPC Foot.L' in the_armor.vertex_groups, f"ERROR: Left foot is in the groups: {the_armor.vertex_groups}"
    
    # Export armor only
    bpy.ops.object.select_all(action='DESELECT')
    the_armor.select_set(True)
    bpy.context.view_layer.objects.active = the_armor
    bpy.ops.export_scene.pynifly(filepath=filepath_armor, target_game='SKYRIM')
    assert os.path.exists(filepath_armor), "ERROR: File not created"

    # Check armor
    ftest = pyn.NifFile(filepath_armor)
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
    bnif = pyn.NifFile(filepath_body)
    assert len(bnif.shapes) == 1, f"Wrote one shape: {bnif.shape_dict.keys()}"


def TEST_WEIGHTS_EXPORT():
    TT.test_title("TEST_WEIGHTS_EXPORT", "Exporting this head weights all verts correctly")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_WEIGHTS_EXPORT.nif")

    head = TT.append_from_file("CheetahFemaleHead", True, r"tests\FO4\CheetahHead.blend", 
                            r"\Object", "CheetahFemaleHead")
    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)

    headcheck = nifcheck.shape_dict["CheetahFemaleHead"]
    bw = headcheck.bone_weights
    for vert_index, v in enumerate(headcheck.verts):
        weightfound = False
        for bn in headcheck.get_used_bones():
            index_list = [p[0] for p in bw[bn]]
            weightfound |= (vert_index in index_list)
        assert weightfound, f"Weight not found for vert #{vert_index}"


def TEST_0_WEIGHTS():
    TT.test_title("TEST_0_WEIGHTS", "Gives warning on export with 0 weights")
    TT.clear_all()
    testfile = TT.test_file(r"tests\Out\weight0.nif")

    baby = TT.append_from_file("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
    baby.parent.name == "BabyExportRoot", f"Error: Should have baby and armature"
    log.debug(f"Found object {baby.name}")
    try:
        bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")
    except RuntimeError:
        print("Caught expected runtime error")
    assert BD.UNWEIGHTED_VERTEX_GROUP in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


def TEST_TIGER_EXPORT():
    TT.test_title("TEST_TIGER_EXPORT", "Tiger head exports without errors")
    TT.clear_all()
    f = TT.test_file(r"tests/Out/TEST_TIGER_EXPORT.nif")
    fb = TT.test_file(r"tests/Out/TEST_TIGER_EXPORT_faceBones.nif")
    ftri = TT.test_file(r"tests/Out/TEST_TIGER_EXPORT.tri")
    fchargen = TT.test_file(r"tests/Out/TEST_TIGER_EXPORT_chargen.tri")

    TT.append_from_file("TigerMaleHead", True, r"tests\FO4\Tiger.blend", r"\Object", "TigerMaleHead")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["TigerMaleHead"].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects["TigerMaleHead"]
    bpy.ops.export_scene.pynifly(filepath=f, target_game='FO4', chargen_ext="_chargen")

    nif1 = pyn.NifFile(f)
    assert len(nif1.shapes) == 1, f"Expected tiger nif"
    assert os.path.exists(fb), "Facebones file created"
    assert os.path.exists(ftri), "Tri file created"
    assert os.path.exists(fchargen), "Chargen file created"


def TEST_3BBB():
    TT.test_title("TEST_3BBB", "Test that this mesh imports with the right transforms")
    TT.clear_all()

    testfile = TT.test_file(r"tests/SkyrimSE/3BBB_femalebody_1.nif")
    testfile2 = TT.test_file(r"tests/SkyrimSE/3BBB_femalehands_1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    obj = bpy.context.object
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert TT.NearEqual(obj.location[0], 0.0), f"Expected body to be centered on x-axis, got {obj.location}"

    print("## Test that the same armature is used for the next import")
    BD.ObjectSelect([arma], active=True)
    bpy.context.view_layer.objects.active = arma
    bpy.ops.import_scene.pynifly(filepath=testfile2)

    arma2 = next(m.object for m in bpy.context.object.modifiers if m.type == 'ARMATURE')
    assert arma2.name == arma.name, f"Should have parented to same armature: {arma2.name} != {arma.name}"


def TEST_SKEL():
    def do_test(use_xf):
        testname = "TEST_SKEL_" + str(use_xf)
        TT.test_title(testname, "Can import and export FO4 skeleton file with no shapes")
        TT.clear_all()
        testfile = TT.test_file(r"skeletons\FO4\skeleton.nif")
        outfile = TT.test_file(r"tests/out/" + testname + ".nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, 
                                     do_create_bones=False, use_blender_xf=use_xf)

        arma = [a for a in bpy.data.objects if a.type == 'ARMATURE'][0]
        assert 'Root' in arma.data.bones, "Have Root bone"
        rootbone = arma.data.bones['Root']
        assert 'Leg_Thigh.L' in arma.data.bones, "Have left thigh bone"
        assert 'RibHelper.L' in arma.data.bones, "Have rib helper bone"
        assert 'L_RibHelper.L' not in arma.data.bones, "Do not have nif name for bone"
        assert 'L_RibHelper' not in bpy.data.objects, "Do not have rib helper object"
        assert arma.data.bones['RibHelper.L'].parent.name == 'Chest', \
            f"Parent of ribhelper is chest: {arma.data.bones['RibHelper.L'].parent.name}"

        # COM bone's orientation matches that of the nif
        nif = pyn.NifFile(testfile)
        rootnode = nif.nodes["Root"]
        assert TT.MatNearEqual(rootbone.matrix, BD.transform_to_matrix(rootnode.transform)), \
            f"Bone transform matches nif: {rootbone.matrix}"

        # Parent connect points are children of the armature. Could also be children of the root
        # but they get transposed based on the armature bones' transforms.
        cp_lleg = bpy.data.objects['BSConnectPointParents::P-ArmorLleg']
        assert cp_lleg.parent.type == 'ARMATURE', f"cp_lleg has armature as parent: {cp_lleg.parent}"
        assert TT.NearEqual(cp_lleg.location[0], -8.748), \
            f"Armor left leg connect point at relative position: {cp_lleg.location}"

        BD.ObjectSelect([bpy.data.objects['skeleton.nif:ROOT']], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', 
                                    preserve_hierarchy=True, use_blender_xf=use_xf)

        skel_in = pyn.NifFile(testfile)
        skel_out = pyn.NifFile(outfile)
        assert "L_RibHelper" in skel_out.nodes, "Bones written to nif"
        pb = skel_out.nodes["L_RibHelper"].parent
        assert pb.name == "Chest", f"Have correct parent: {pb.name}"
        helm_cp_in = [x for x in skel_in.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
        helm_cp_out = [x for x in skel_out.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
        assert helm_cp_out.parent.decode('utf-8') == 'HEAD', f"Parent is correct: {helm_cp_out.parent}"
        assert TT.VNearEqual(helm_cp_in.translation, helm_cp_out.translation), \
            f"Connect point locations correct: {Vector(helm_cp_in.translation)} == {Vector(helm_cp_out.translation)}"
        
    do_test(False)
    do_test(True)


def TEST_SKEL_SKY():
    TT.test_title("TEST_SKEL_SKY", "Can import and export Skyrim skeleton file with no shapes")
    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    outfile = TT.test_file(r"tests/out/TEST_SKEL_SKY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    root = next(x for x in bpy.data.objects if 'pynRoot' in x)

    bumper_col = next(x for x in arma.children 
                   if x.name.startswith('bhkSPCollisionObject')
                   and x['pynCollisionTarget'] == 'CharacterBumper')
    assert bumper_col, "Have bumper collision"
    bumper_shape = bumper_col.children[0].children[0]
    bb = TT.get_obj_bbox(bumper_shape, worldspace=True)
    assert bb[1][2] - bb[0][2] > bb[1][0] - bb[0][0] \
        and bb[1][2] - bb[0][2] > bb[1][1] - bb[0][1], \
            f"Character bumper long dimension is vertical: {bb}"

    foot_col = [obj for obj in bpy.data.objects 
                    if 'pynCollisionTarget' in obj and obj['pynCollisionTarget'] == 'NPC Foot.R']
    assert foot_col, "Have foot collision object"



def TEST_HEADPART():
    # Tri files can be loaded up into a shape in blender as shape keys. On SE, when there
    # are shape keys a BSDynamicTriShape is used on export.
    TT.test_title("TEST_HEADPART", "Can read & write an SE head part")
    TT.clear_all()
    testfile = TT.test_file(r"tests/SKYRIMSE/malehead.nif")
    testtri = TT.test_file(r"tests/SKYRIMSE/malehead.tri")
    testfileout = TT.test_file(r"tests/out/TEST_HEADPART.nif")
    testfileout2 = TT.test_file(r"tests/out/TEST_HEADPART2.nif")
    testfileout3 = TT.test_file(r"tests/out/TEST_HEADPART3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    bpy.ops.import_scene.pyniflytri(filepath=testtri)

    assert len(obj.data.shape_keys.key_blocks) == 45, f"Expected key blocks 45 != {len(obj.data.shape_keys.key_blocks)}"
    assert obj.data.shape_keys.key_blocks[0].name == "Basis", f"Expected first key 'Basis' != {obj.data.shape_keys.key_blocks[0].name}"

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game='SKYRIMSE')
    
    nif2 = pyn.NifFile(testfileout)
    head2 = nif2.shapes[0]
    assert len(nif2.shapes) == 1, f"Expected single shape, 1 != {len(nif2.shapes)}"
    assert head2.blockname == "BSDynamicTriShape", f"Expected 'BSDynamicTriShape' != '{nif2.shapes[0].blockname}'"

    # We can export whatever shape is defined by the shape keys.
    obj.data.shape_keys.key_blocks['Blink.L'].value = 1
    obj.data.shape_keys.key_blocks['MoodHappy'].value = 1
    bpy.ops.export_scene.pynifly(filepath=testfileout2, target_game='SKYRIMSE', 
                                 export_modifiers=True)
    
    nif3 = pyn.NifFile(testfileout2)
    head3 = nif3.shapes[0]
    eyelid = TT.find_vertex(obj.data, [-2.52558, 7.31011, 124.389])
    mouth = TT.find_vertex(obj.data, [1.8877, 7.50949, 118.859])
    assert not TT.VNearEqual(head2.verts[eyelid], head3.verts[eyelid]), \
        f"Verts have moved: {head2.verts[eyelid]} != {head3.verts[eyelid]}"
    assert not TT.VNearEqual(head2.verts[mouth], head3.verts[mouth]), \
        f"Verts have moved: {head2.verts[mouth]} != {head3.verts[mouth]}"

    # We can export any modifiers
    obj.data.shape_keys.key_blocks['Blink.L'].value = 0
    obj.data.shape_keys.key_blocks['MoodHappy'].value = 0
    mod = obj.modifiers.new("Decimate", 'DECIMATE')
    mod.ratio = 0.2
    bpy.ops.export_scene.pynifly(filepath=testfileout3, target_game='SKYRIMSE', 
                                 export_modifiers=True)
    nif4 = pyn.NifFile(testfileout3)
    head4 = nif4.shapes[0]
    assert len(head4.verts) < 300, f"Head has decimated verts: {head4.verts}"


def TEST_TRI():
    TT.test_title("TEST_TRI", "Can load a tri file into an existing mesh")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\CheetahMaleHead.nif")
    testtri2 = TT.test_file(r"tests\FO4\CheetahMaleHead.tri")
    testtri3 = TT.test_file(r"tests\FO4\CheetahMaleHead.tri")
    testout2 = TT.test_file(r"tests\Out\CheetahMaleHead02.nif")
    testout2tri = TT.test_file(r"tests\Out\CheetahMaleHead02.tri")
    testout2chg = TT.test_file(r"tests\Out\CheetahMaleHead02chargen.tri")
    tricubenif = TT.test_file(r"tests\Out\tricube01.nif")
    tricubeniftri = TT.test_file(r"tests\Out\tricube01.tri")
    tricubenifchg = TT.test_file(r"tests\Out\tricube01chargen.tri")

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
    nif2 = pyn.NifFile(testout2)
    tri2 = TriFile.from_file(testout2tri)
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
    

def TEST_IMPORT_MULTI_OBJECTS():
    # When two files are selected for import, they are connected into a single armature.
    TT.test_title("TEST_IMPORT_MULTI_OBJECTS", "Can import 2 meshes as objects")
    TT.clear_all()

    testfiles = [{"name": TT.test_file(r"tests\SkyrimSE\malehead.nif")}, 
                 {"name": TT.test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    for ol_area in [a for a in bpy.context.screen.areas if a.type == 'OUTLINER']:
        for ol_region in [r for r in ol_area.regions if r.type == 'WINDOW']:
            override = {'area':ol_area, 'region': ol_region}
            bpy.ops.outliner.show_active(override)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 3, f"Have 3 meshes: {meshes}"
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    assert len(armatures) == 1, f"Have 1 armature: {armatures}"
    roots = [obj for obj in bpy.data.objects if 'pynRoot' in obj]
    assert len(roots) == 2, f"Have 2 roots: {roots}"
    for r in roots:
        assert r.parent == None, f"Roots do not have parents: {r}"
    bodyroot = next(obj for obj in roots if obj.name.startswith("Body"))
    invm = [obj for obj in bodyroot.children if 'InvMarker' in obj.name]
    assert len(invm) == 1, f"Have an inventory marker: {invm}"
    assert invm[0].type == 'CAMERA', f"Inventory marker is a camera: {invm[0].type}"


def TEST_IMPORT_AS_SHAPES():
    # When two files are selected for import, they are imported as shape keys if possible.
    TT.test_title("TEST_IMPORT_AS_SHAPES", "Can import 2 meshes as shape keys")
    TT.clear_all()

    testfiles = [{"name": TT.test_file(r"tests\SkyrimSE\body1m_0.nif")}, 
                 {"name": TT.test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 2, f"Have 2 meshes: {meshes}"
    sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
    assert set(sknames0) == set(['Basis', '_0', '_1']), f"Shape keys are named correctly: {sknames0}"
    sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
    assert set(sknames1) == set(['Basis', '_0', '_1']), f"Shape keys are named correctly: {sknames1}"
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    assert len(armatures) == 1, f"Have 1 armature: {armatures}"


def TEST_IMPORT_MULT_SHAPES():
    # When multiple files are selected for a single import, they are connected up as 
    # shape keys if possible.
    TT.test_title("TEST_IMPORT_MULT_SHAPES", "Can import >2 meshes as shape keys")
    TT.clear_all()

    testfiles = [{"name": TT.test_file(r"tests\FO4\PoliceGlasses\Glasses_Cat.nif")}, 
                    {"name": TT.test_file(r"tests\FO4\PoliceGlasses\Glasses_CatF.nif")}, 
                    {"name": TT.test_file(r"tests\FO4\PoliceGlasses\Glasses_Horse.nif")}, 
                    {"name": TT.test_file(r"tests\FO4\PoliceGlasses\Glasses_Hyena.nif")}, 
                    {"name": TT.test_file(r"tests\FO4\PoliceGlasses\Glasses_LionLyk.nif")}, 
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


def TEST_EXP_SK_RENAMED():
    if bpy.app.version[0] < 3: return

    # The export/import process can change left/right shape keys to better match Blender's
    # naming conventions.
    #
    # Doesn't work on 2.x. Not sure why.
    TT.test_title("TEST_EXP_SK_RENAMED", "Ensure renamed shape keys export properly")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_EXP_SK_RENAMED.nif")
    trifile = TT.test_file(r"tests/Out/TEST_EXP_SK_RENAMED.tri")
    chargenfile = TT.test_file(r"tests/Out/TEST_EXP_SK_RENAMEDchargen.tri")

    TT.append_from_file("BaseFemaleHead:0", True, r"tests\FO4\FemaleHead.blend", 
                     r"\Object", "BaseFemaleHead:0")

    head = bpy.data.objects["BaseFemaleHead:0"]
    initial_keys = set(head.data.shape_keys.key_blocks.keys())

    pyn.NifFile.clear_log()
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = bpy.data.objects["BaseFemaleHead:0"]
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert "ERROR" not in pyn.NifFile.message_log(), f"Error: Expected no error message, got: \n{pyn.NifFile.message_log()}---\n"

    assert not os.path.exists(chargenfile), f"Chargen file not created: {os.path.exists(chargenfile)}"

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected head nif"

    tri1 = TriFile.from_file(trifile)
    new_keys = set()
    d = BD.gameSkeletons["FO4"]
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


def TEST_SK_MULT():
    TT.test_title("TEST_SK_MULT", "Export multiple objects with only some shape keys")

    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_SK_MULT.nif")
    outfile0 = TT.test_file(r"tests/Out/TEST_SK_MULT_0.nif")
    outfile1 = TT.test_file(r"tests/Out/TEST_SK_MULT_1.nif")

    TT.append_from_file("CheMaleMane", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "CheMaleMane")
    TT.append_from_file("MaleTail", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "MaleTail")
    bpy.context.view_layer.objects.active = bpy.data.objects["CheMaleMane"]
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["CheMaleMane"].select_set(True)
    bpy.data.objects["MaleTail"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    nif1 = pyn.NifFile(outfile1)
    assert len(nif1.shapes) == 2, "Wrote the 1 file successfully"
    assert 'NPC Spine2 [Spn2]' in nif1.nodes, "Found spine2 bone"
    assert 'TailBone01' in nif1.nodes, "Found Tailbone01"
    assert 'NPC L Clavicle [LClv]' in nif1.nodes, "Found Clavicle"

    nif0 = pyn.NifFile(outfile0)
    assert len(nif0.shapes) == 2, "Wrote the 0 file successfully"
    assert 'NPC Spine2 [Spn2]' in nif0.nodes, "Found Spine2 in _0 file"
    assert 'TailBone01' in nif0.nodes, "Found tailbone01 in _0 file"
    assert 'NPC L Clavicle [LClv]' in nif0.nodes, "Found clavicle in _0 file"


def TEST_TRI2():
    TT.test_title("TEST_TRI2", "Regression: Test correct improt of tri")    
    TT.clear_all()
    testfile = TT.test_file(r"tests/Skyrim/OtterMaleHead.nif")
    trifile = TT.test_file(r"tests/Skyrim/OtterMaleHeadChargen.tri")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    bpy.ops.import_scene.pyniflytri(filepath=trifile)

    v1 = obj.data.shape_keys.key_blocks['VampireMorph'].data[1]
    assert v1.co[0] <= 30, "Shape keys not relative to current mesh"


def TEST_BAD_TRI():
    # Tri files have UVs in them, but it's mostly not used, and some tris have messed up
    # UVs. Make sure they can be read anyway.
    TT.test_title("TEST_BAD_TRI", "Tris with messed up UVs can be imported")
    TT.clear_all()

    testfile = TT.test_file(r"tests/Skyrim/bad_tri.tri")
    testfile2 = TT.test_file(r"tests/Skyrim/bad_tri_2.tri")
    
    bpy.ops.import_scene.pyniflytri(filepath=testfile)
    obj = bpy.context.object
    assert len(obj.data.vertices) == 6711, f"Expected 6711 vertices, found {len(obj.data.vertices)}"

    bpy.ops.import_scene.pyniflytri(filepath=testfile2)
    obj2 = bpy.context.object
    assert len(obj2.data.vertices) == 11254, f"Expected 11254 vertices, found {len(obj2.data.vertices)}"


def TEST_SEGMENTS():
    TT.test_title("TEST_SEGMENTS", "Can read FO4 segments")
    TT.clear_all()

    testfile = TT.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SEGMENTS.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert "FO4 Seg 003" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names: 'FO4 Seg 003'"
    assert "FO4 Seg 004 | 000 | Up Arm.L" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names: 'FO4 Seg 004 | 000 | Up Arm.L'"
    assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "Should have FO4 segment file read and saved for later use"

    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    
    nif2 = pyn.NifFile(outfile)
    assert len(nif2.shapes[0].partitions) == 7, f"Wrote the shape's 7 partitions: {[p.name for p in nif2.shapes[0].partitions]}"
    assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == nif2.shapes[0].segment_file, f"Nif should reference segment file, found '{nif2.shapes[0].segment_file}'"


def TEST_BP_SEGMENTS():
    TT.test_title("TEST_BP_SEGMENTS", "Can read FO4 bodypart segments")
    TT.clear_all()

    testfile = TT.test_file(r"tests/FO4/Helmet.nif")
    outfile = TT.test_file(r"tests/Out/TEST_BP_SEGMENTS.nif")
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
    
    nif2 = pyn.NifFile(outfile)
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


def TEST_EXP_SEGMENTS_BAD():
    # Game can get crashy if there are a bunch of empty segments at the end of the list.
    TT.test_title("TEST_EXP_SEGMENTS_BAD", "Verts export in the correct segments")
    TT.clear_all()

    outfile = TT.test_file(r"tests/Out/TEST_EXP_SEGMENTS_BAD.nif")

    TT.append_from_file("ArmorUnder", True, r"tests\FO4\ArmorExportsBadSegments.blend", r"\Object", "ArmorUnder")

    pyn.NifFile.clear_log()
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert "ERROR" not in pyn.NifFile.message_log(), f"Error: Expected no error message, got: \n{pyn.NifFile.message_log()}---\n"

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Single shape was exported"

    body = nif1.shapes[0]
    assert len(body.partitions) >= 4, "All important segments exported"
    assert len(body.partitions[3].subsegments) == 0, "4th partition (body) has no subsegments"
    assert len([x for x in body.partition_tris if x == 3]) == len(body.tris), f"All tris in the 4th partition--found {len([x for x in body.partition_tris if x == 3])}"
    assert len([x for x in body.partition_tris if x != 3]) == 0, f"Regression: No tris in the last partition (or any other)--found {len([x for x in body.partition_tris if x != 3])}"


def TEST_EXP_SEG_ORDER():
    if bpy.app.version[0] < 3: return 

    # Order matters for the segments, so make sure it's right.
    TT.test_title("TEST_EXP_SEG_ORDER", "Segments export in numerical order")
    outfile = TT.test_file(r"tests/Out/TEST_EXP_SEG_ORDER.nif")
    TT.clear_all()

    gen1bod = TT.append_from_file("SynthGen1Body", True, r"tests\FO4\SynthGen1BodyTest.blend", r"\Object", "SynthGen1Body")

    obj = bpy.data.objects["SynthGen1Body"]
    groups = [g for g in obj.vertex_groups if g.name.startswith('FO4')]
    assert len(groups) == 23, f"Groups properly appended from test file: {len(groups)}"

    pyn.NifFile.clear_log()
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = gen1bod
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert "ERROR" not in pyn.NifFile.message_log(), f"Error: Expected no error message, got: \n{pyn.NifFile.message_log()}---\n"

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Single shape was exported"

    # Third segment should be arm, with 5 subsegments
    body = nif1.shapes[0]
    assert len(body.partitions[2].subsegments) == 5, f"Right arm has 5 subsegments, found {len(body.partitions[2].subsegments)}"
    assert body.partitions[2].subsegments[0].material == 0xb2e2764f, "First subsegment is the upper right arm material"
    assert len(body.partitions[3].subsegments) == 0, "Torso has no subsegments"


def TEST_PARTITIONS():
    TT.test_title("TEST_PARTITIONS", "Can read Skyrim partions")
    TT.clear_all()
    testfile = TT.test_file(r"tests/Skyrim/MaleHead.nif")
    outfile = TT.test_file(r"tests/Out/TEST_PARTITIONS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert "SBP_130_HEAD" in obj.vertex_groups, "Skyrim body parts read in as vertex groups with sensible names"

    print("### Can write Skyrim partitions")
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nif2 = pyn.NifFile(outfile)
    head = nif2.shapes[0]
    assert len(nif2.shapes[0].partitions) == 3, "Have all skyrim partitions"
    assert set([p.id for p in head.partitions]) == set([130, 143, 230]), "Have all head parts"


def TEST_SHADER_LE():
    TT.test_title("TEST_SHADER_LE", "Shader attributes are read and turned into Blender shader nodes")
    TT.clear_all()

    fileLE = TT.test_file(r"tests\Skyrim\meshes\actors\character\character assets\malehead.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SHADER_LE.nif")
    bpy.ops.import_scene.pynifly(filepath=fileLE)

    nifLE = pyn.NifFile(fileLE)
    shaderAttrsLE = nifLE.shapes[0].shader_attributes
    headLE = bpy.context.object
    shadernodes = headLE.active_material.node_tree.nodes
    assert 'Principled BSDF' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    assert 'Image Texture' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    assert 'Normal Map' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    g = shadernodes['Principled BSDF'].inputs['Metallic'].default_value
    assert round(g, 4) == 33/BD.GLOSS_SCALE, f"Glossiness not correct, value is {g}"
    assert headLE.active_material['BSShaderTextureSet_2'] == r"textures\actors\character\male\MaleHead_sk.dds", f"Expected stashed texture path, found {headLE.active_material['BSShaderTextureSet_2']}"

    print("## Shader attributes are written on export")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifcheckLE = pyn.NifFile(outfile)
    
    assert nifcheckLE.shapes[0].textures[0].lower() == nifLE.shapes[0].textures[0].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[0]}' != '{nifLE.shapes[0].textures[0]}'"
    assert nifcheckLE.shapes[0].textures[1].lower() == nifLE.shapes[0].textures[1].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[1]}' != '{nifLE.shapes[0].textures[1]}'"
    assert nifcheckLE.shapes[0].textures[2].lower() == nifLE.shapes[0].textures[2].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[2]}' != '{nifLE.shapes[0].textures[2]}'"
    assert nifcheckLE.shapes[0].textures[7].lower() == nifLE.shapes[0].textures[7].lower(), \
        f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[7]}' != '{nifLE.shapes[0].textures[7]}'"
    assert nifcheckLE.shapes[0].shader_attributes == shaderAttrsLE, f"Error: Shader attributes not preserved:\n{nifcheckLE.shapes[0].shader_attributes}\nvs\n{shaderAttrsLE}"


def TEST_SHADER_SE():
    # Basic test of texture paths on shaders.
    TT.test_title("TEST_SHADER_SE", "Shader attributes are read and turned into Blender shader nodes")
    TT.clear_all()

    fileSE = TT.test_file(r"tests\skyrimse\meshes\armor\dwarven\dwarvenboots_envscale.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SHADER_SE.nif")
    
    bpy.ops.import_scene.pynifly(filepath=fileSE)
    nifSE = pyn.NifFile(fileSE)
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

    nifcheckSE = pyn.NifFile(outfile)
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


def TEST_SHADER_FO4():
    TT.test_title("TEST_SHADER_FO4", "Shader attributes are read and turned into Blender shader nodes")
    TT.clear_all()
    fileFO4 = TT.test_file(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\basemalehead.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SHADER_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=fileFO4)
    headFO4 = bpy.context.object
    
    nifFO4 = pyn.NifFile(fileFO4)
    shaderAttrsFO4 = nifFO4.shapes[0].shader_attributes
    sh = headFO4.active_material.node_tree.nodes["Principled BSDF"]
    assert sh, "Have shader node"
    txt = headFO4.active_material.node_tree.nodes["Image Texture"]
    assert txt and txt.image and txt.image.filepath, "ERROR: Didn't import images"

    print("## Shader attributes are written on export")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nifcheckFO4 = pyn.NifFile(outfile)
    
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


def TEST_SHADER_ALPHA():
    # Alpha property is translated into equivalent Blender nodes.
    #
    # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the
    # suffix.
    TT.test_title("TEST_SHADER_ALPHA", "Shader attributes are read and turned into Blender shader nodes")
    TT.clear_all()

    fileAlph = TT.test_file(r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SHADER_ALPH.nif")

    bpy.ops.import_scene.pynifly(filepath=fileAlph)
    
    nifAlph = pyn.NifFile(fileAlph)
    furshape = nifAlph.shape_dict["tail_fur"]
    tail = bpy.data.objects["tail_fur"]
    assert 'Principled BSDF' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert 'Image Texture' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert 'Attribute' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert 'Normal Map' in tail.active_material.node_tree.nodes.keys(), f"Have shader nodes: {tail.active_material.node_tree.nodes.keys()}"
    assert tail.active_material.blend_method == 'CLIP', f"Error: Alpha blend is '{tail.active_material.blend_method}', not 'CLIP'"

    print("## Shader attributes are written on export")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifCheck = pyn.NifFile(outfile)
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


def TEST_SHADER_3_3():
    TT.test_title("TEST_SHADER_3_3", "Shader attributes are read and turned into Blender shader nodes")
    TT.clear_all()

    TT.append_from_file("FootMale_Big", True, r"tests\SkyrimSE\feet.3.3.blend", 
                     r"\Object", "FootMale_Big")
    bpy.ops.object.select_all(action='DESELECT')
    obj = TT.find_shape("FootMale_Big")

    print("## Shader attributes are written on export")
    outfile = TT.test_file(r"tests/Out/TEST_SHADER_3_3.nif")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = pyn.NifFile(outfile)
    
    assert nifcheckSE.shapes[0].textures[0] == r"textures\actors\character\male\MaleBody_1.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[0]}'"
    assert nifcheckSE.shapes[0].textures[1] == r"textures\actors\character\male\MaleBody_1_msn.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[1]}'"
    assert nifcheckSE.shapes[0].textures[2] == r"textures\actors\character\male\MaleBody_1_sk.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[2]}'"
    assert nifcheckSE.shapes[0].textures[7] == r"textures\actors\character\male\MaleBody_1_S.dds", \
        f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[7]}'"


def TEST_TEXTURE_PATHS():
    TT.test_title("TEST_TEXTURE_PATHS", "Texture paths are correctly resolved")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\circletm1.nif")
    txtdir = TT.test_file(r"tests\SkyrimSE")

    # Use temp_override to redirect the texture directory
    assert type(bpy.context) == bpy_types.Context, f"Context type is expected :{type(bpy.context)}"
    txtdir_in = bpy.context.preferences.filepaths.texture_directory
    if hasattr(bpy.context, 'temp_override'):
        # Blender 3.5
        with bpy.context.temp_override():
            bpy.context.preferences.filepaths.texture_directory = txtdir
            bpy.ops.import_scene.pynifly(filepath=testfile)
    else:
            bpy.context.preferences.filepaths.texture_directory = txtdir
            bpy.ops.import_scene.pynifly(filepath=testfile)
    
    # Should have found the texture files
    circlet = TT.find_shape('M1:4')
    mat = circlet.active_material
    bsdf = mat.node_tree.nodes['Principled BSDF']
    diffuse = shader_io.get_image_filepath(bsdf.inputs['Base Color'])
    assert diffuse.endswith('Circlet.dds'), f"Found diffuse texture file: '{diffuse}'"
    norm = shader_io.get_image_filepath(bsdf.inputs['Normal'])
    assert norm.endswith('Circlet_n.png'), f"Found normal texture file: '{norm}'"


def TEST_CAVE_GREEN():
    # Regression: Make sure the transparency is exported on this nif.
    TT.test_title("TEST_CAVE_GREEN", "Cave nif can be exported correctly")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\meshes\dungeons\caves\green\smallhall\caveghall1way01.nif")
    outfile = TT.test_file(r"tests/Out/TEST_CAVE_GREEN.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    wall1 = bpy.data.objects["CaveGHall1Way01:2"]
    mat1 = wall1.active_material
    mix1 = mat1.node_tree.nodes['Principled BSDF'].inputs['Base Color'].links[0].from_node
    try:
        # Blender 3.5
        diff1 = mix1.inputs[6].links[0].from_node
    except:
        # Blender 3.1
        diff1 = mix1.inputs['Color1'].links[0].from_node

    assert diff1.image.filepath.lower()[0:-4].endswith("cavebasewall01"), f"Have correct wall diffuse: {diff1.image.filepath}"

    roots = TT.find_shape("L2_Roots:5")

    bpy.ops.object.select_all(action='DESELECT')
    roots.select_set(True)
    bpy.ops.object.duplicate()

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheck = pyn.NifFile(outfile)
    rootscheck = nifcheck.shape_dict["L2_Roots:5"]
    assert rootscheck.has_alpha_property, f"Roots have alpha: {rootscheck.has_alpha_property}"
    assert rootscheck.shader_attributes.shaderflags2_test(nifdefs.ShaderFlags2.VERTEX_COLORS), \
        f"Have vertex colors: {rootscheck.shader_attributes.shaderflags2_test(nifdefs.ShaderFlags2.VERTEX_COLORS)}"


def TEST_POT():
    TT.test_title("TEST_POT", "Test that pot shaders doesn't throw an error; also collisions")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\spitpotopen01.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)
    assert 'ANCHOR:0' in bpy.data.objects.keys()

    anchor = bpy.data.objects['ANCHOR']
    anchor_col = next(ch for ch in anchor.children if ch.name.startswith('bhkCollisionObject'))
    anchor_bod = next(bod for bod in anchor_col.children if bod.name.startswith('bhkRigidBody'))
    anchor_sh = next(sh for sh in anchor_bod.children if sh.name.startswith('bhkSphereShape'))
    assert anchor_sh, "Have collision shape for anchor"

    anchor_z = anchor.matrix_world.translation.z
    anchor_sh_z = anchor_sh.matrix_world.translation.z
    assert BD.NearEqual(anchor_z, anchor_sh_z), f"Near equal z locations: {anchor_z} == {anchor_sh_z}"

    hook = bpy.data.objects['L1_Hook']
    hook_col = next(ch for ch in hook.children if ch.name.startswith('bhkCollisionObject'))
    hook_bod = next(bod for bod in hook_col.children if bod.name.startswith('bhkRigidBody'))
    hook_sh = next(sh for sh in hook_bod.children if sh.name.startswith('bhkBoxShape'))
    assert hook_sh, "Have collision shape for hook"

    hook_z = hook.matrix_world.translation.z
    hook_sh_z = hook_sh.matrix_world.translation.z
    assert hook_z > hook_sh_z, f"Hook collision below hook: {hook_z} > {hook_sh_z}"


def TEST_NOT_FB():
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
    TT.test_title("TEST_NOT_FB", "Test that nif that looked like facebones skel can be imported")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\6SuitM_Test.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TT.find_shape("body_Cloth:0")
    minz = min(v.co.z for v in body.data.vertices)
    assert minz > -130, f"Min z location not stretched: {minz}"


def TEST_MULTI_IMP():
    # Fact is, this DOES mess up. we can import more than one nif at a time, which 
    # is what we're trying to test. But we might be importing Skyrim's _0 and _1 weight
    # bodyparts, so we'd like them to load as shape keys if possible. BUT two of these
    # nifs have the same vert count, so they get loaded as shape keys tho they shouldn't.
    #
    # TODO: Decide if this is work fixing, and how. Maybe key of the _0 and _1 file 
    # extensions?
    TT.test_title("TEST_MULTI_IMP", "Test that importing multiple hair parts doesn't mess up")
    TT.clear_all()

    testfile1 = TT.test_file(r"tests\FO4\FemaleHair25.nif")
    testfile2 = TT.test_file(r"tests\FO4\FemaleHair25_Hairline1.nif")
    testfile3 = TT.test_file(r"tests\FO4\FemaleHair25_Hairline2.nif")
    testfile4 = TT.test_file(r"tests\FO4\FemaleHair25_Hairline3.nif")
    bpy.ops.import_scene.pynifly(files=[{"name": testfile1}, 
                                        {"name": testfile2}, 
                                        {"name": testfile3}, 
                                        {"name": testfile4}])
    h = TT.find_shape("FemaleHair25:0")
    assert h.location.z > 120, f"Hair fully imported: {h.location}"


def TEST_WELWA():
    # The Welwa (bear skeleton) has bones similar to human bones--but they can't be
    # treated like the human skeleton. "Rename bones" is false on import and should be
    # remembered on the mesh and armature for export, so it's not explicitly specified on
    # export.
    TT.test_title("TEST_WELWA", "Can read and write shape with unusual skeleton")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\SkyrimSE\welwa.nif")
    outfile = TT.test_file(r"tests/Out/TEST_WELWA.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_rename_bones=False, do_create_bones=False)

    welwa = TT.find_shape("111")
    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    lipbone = skel.data.bones['NPC UpperLip']
    assert TT.VNearEqual(lipbone.matrix_local.translation, (0, 49.717827, 161.427307)), f"Found {lipbone.name} at {lipbone.matrix_local.translation}"
    spine1 = skel.data.bones['NPC Spine1']
    assert TT.VNearEqual(spine1.matrix_local.translation, (0, -50.551056, 64.465019)), f"Found {spine1.name} at {spine1.matrix_local.translation}"

    # Should remember that bones are not to be renamed.
    bpy.ops.object.select_all(action='DESELECT')
    welwa.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)

    assert "NPC Pelvis [Pelv]" not in nifcheck.nodes, f"Human pelvis name not written: {nifcheck.nodes.keys()}"


def TEST_MUTANT():
    TT.test_title("TEST_MUTANT", "Test that the supermutant body imports correctly the *second* time")
    TT.clear_all()
    testfile = TT.test_file(r"tests/FO4/testsupermutantbody.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_rename_bones=False, do_create_bones=False)

    testnif = pyn.NifFile(testfile)
    assert round(testnif.shapes[0].global_to_skin.translation[2]) == -140, f"Expected -140 z translation in first nif, got {testnif.shapes[0].global_to_skin.translation[2]}"

    sm1 = bpy.context.object
    assert round(sm1.location[2]) == 140, f"Expect first supermutant body at 140 Z, got {sm1.location[2]}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile, do_rename_bones=False, do_create_bones=False)
    sm2 = bpy.context.object
    assert sm2 != sm1, f"Second import created second object: {sm2.name}"
    assert round(sm2.location[2]) == 140, f"Expect supermutant body at 140 Z, got {sm2.location[2]}"

    
def TEST_EXPORT_HANDS():
    # When there are problems with the mesh we don't want to crash and burn.
    TT.test_title("TEST_EXPORT_HANDS", "Test that hand mesh doesn't throw an error")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_EXPORT_HANDS.nif")

    TT.append_from_file("SupermutantHands", True, r"tests\FO4\SupermutantHands.blend", r"\Object", "SupermutantHands")
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = bpy.data.objects["SupermutantHands"]
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    assert os.path.exists(outfile)


def TEST_PARTITION_ERRORS():
    if bpy.app.version[0] < 3: return

    # Partitions have to cleanly separate the faces into non-overlapping parts of the
    # shape. If that's not the case, we return an error.
    #
    # Doesn't run on 2.x, don't know why
    TT.test_title("TEST_PARTITION_ERRORS", "Partitions with errors raise errors")
    TT.clear_all()
    testfile = TT.test_file(r"tests/Out/TEST_TIGER_EXPORT.nif")

    TT.append_from_file("SynthMaleBody", True, r"tests\FO4\SynthBody02.blend", r"\Object", "SynthMaleBody")

    # Partitions must divide up the mesh cleanly--exactly 1 partition per tri
    bpy.context.view_layer.objects.active = bpy.data.objects["SynthMaleBody"]
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='FO4')
    
    # assert len(exporter.warnings) > 0, f"Error: Export should have generated warnings: {exporter.warnings}"
    # print(f"Exporter warnings: {exporter.warnings}")
    assert BD.MULTIPLE_PARTITION_GROUP in bpy.data.objects["SynthMaleBody"].vertex_groups, "Error: Expected group to be created for tris in multiple partitions"


def TEST_SHEATH():
    # The sheath has extra data nodes for Havok. These are imported as Blender empty
    # objects, and can be exported again.
    TT.test_title("TEST_SHEATH", "Extra data nodes are imported and exported")
    TT.clear_all()

    testfile = TT.test_file(r"tests/Skyrim/sheath_p1_1.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SHEATH.nif")
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
    nifCheck = pyn.NifFile(outfile)
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


def TEST_FEET():
    # Feet have extra data nodes that are children of the feet mesh. This parent/child
    # relationship must be preserved on import and export.
    TT.test_title("TEST_FEET", "Extra data nodes are imported and exported")
    TT.clear_all()
    testfile = TT.test_file(r"tests/SkyrimSE/caninemalefeet_1.nif")
    outfile = TT.test_file(r"tests/Out/TEST_FEET.nif")

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

    nifCheck = pyn.NifFile(outfile)
    feetShape = nifCheck.shapes[0]
    assert feetShape.string_data[0][0] == 'SDTA', "String data name written correctly"
    assert feetShape.string_data[0][1].startswith('[{"name"'), "String data value written correctly"


def TEST_SCALING():
    TT.test_title("TEST_SCALING", "Test that scale factors happen correctly")

    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\statuechampion.nif")
    testout = TT.test_file(r"tests\Out\TEST_SCALING.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    base = bpy.data.objects['basis1']
    assert int(base.scale[0]) == 10, f"ERROR: Base scale should be 10, found {base.scale[0]}"
    tail = bpy.data.objects['tail_base.001']
    assert round(tail.scale[0], 1) == 1.7, f"ERROR: Tail scale should be ~1.7, found {tail.scale}"
    assert round(tail.location[0], 0) == -158, f"ERROR: Tail x loc should be -158, found {tail.location}"

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=testout, target_game="SKYRIM")

    checknif = pyn.NifFile(testout)
    checkfoot = checknif.shape_dict['FootLowRes']
    assert checkfoot.transform.rotation[0][0] == 1.0, f"ERROR: Foot rotation matrix not identity: {checkfoot.transform}"
    assert TT.NearEqual(checkfoot.transform.scale, 1.0), f"ERROR: Foot scale not correct: {checkfoot.transform.scale}"

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


def TEST_SCALING_OBJ():
    TT.test_title("TEST_SCALING_OBJ", "Can scale simple object with furniture markers")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TT.test_file(r"tests\Out\TEST_SCALING_OBJ.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)

    bench = bpy.context.object
    bbmin, bbmax = TT.get_obj_bbox(bench, worldspace=True)
    assert bbmax[0] < 6.5, f"Bench is scaled down: {bbmax}" 
    assert bbmin[0] > -6.5, f"Bench is scaled down: {bbmin}" 
    # bmax = max([v.co.z for v in bench.data.vertices])
    # bmin = min([v.co.z for v in bench.data.vertices])
    # assert TT.VNearEqual(bench.scale, (1,1,1)), f"Bench scale factor is 1: {bench.scale}"
    # assert bmax < 3.1, f"Max Z is scaled down: {bmax}"
    # assert bmin >= 0, f"Min Z is correct: {bmin}"

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    fx0 = fmarkers[0].matrix_world
    fx1 = fmarkers[1].matrix_world
    assert fx0.translation.x > bbmin.x and fx0.translation.x < bbmax.x, f"Furniture marker within bench bounds"
    assert fx1.translation.x > bbmin.x and fx1.translation.x < bbmax.x, f"Furniture marker within bench bounds"
    # assert fmarkers[0].location.z < 3.4, f"Furniture marker location is correct: {fmarkers[0].location.z}"

    # -------- Export --------
    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    exporter = bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                            use_blender_xf=True)

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    bcheck = nifcheck.shapes[0]
    fmcheck = nifcheck.furniture_markers
    bchmax = max([v[2] for v in bcheck.verts])
    assert bchmax > 30, f"Max Z is scaled up: {bchmax}"
    assert len(fmcheck) == 2, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].offset[2] > 30, f"Furniture marker Z scaled up: {fmcheck[0].offset[2]}"


def TEST_UNIFORM_SCALE():
    TT.test_title("TEST_UNIFORM_SCALE", "Can export objects with uniform scaling")
    TT.clear_all()

    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TestCube"
    cube.scale = Vector((4.0, 4.0, 4.0))

    testfile = TT.test_file(r"tests\Out\TEST_UNIFORM_SCALE.nif")
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='SKYRIM')

    nifcheck = pyn.NifFile(testfile)
    shapecheck = nifcheck.shapes[0]
    assert TT.NearEqual(shapecheck.transform.scale, 4.0), f"Shape scaled x4: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert TT.VNearEqual(map(abs, v), [1,1,1]), f"All vertices at unit position: {v}"


def TEST_NONUNIFORM_SCALE():
    TT.test_title("TEST_NONUNIFORM_SCALE", "Can export objects with non-uniform scaling")
    TT.clear_all()

    testfile = TT.test_file(r"tests\Out\TEST_NONUNIFORM_SCALE.nif")
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TestCube"
    cube.scale = Vector((2.0, 4.0, 8.0))

    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='SKYRIM')

    nifcheck = pyn.NifFile(testfile)
    shapecheck = nifcheck.shapes[0]
    assert TT.NearEqual(shapecheck.transform.scale, 1.0), f"Nonuniform scale exported in verts so scale is 1: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert not TT.VNearEqual(map(abs, v), [1,1,1]), f"All vertices scaled away from unit position: {v}"


def TEST_TRIP_SE():
    # Special bodytri files allow for Bodyslide or FO4 body morphing.
    TT.test_title("TEST_TRIP_SE", "Bodypart tri extra data and file are written on export")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_TRIP_SE.nif")
    outfile1 = TT.test_file(r"tests/Out/TEST_TRIP_SE_1.nif")
    outfiletrip = TT.test_file(r"tests/Out/TEST_TRIP_SE.tri")

    TT.append_from_file("Penis_CBBE", True, r"tests\SkyrimSE\HorseFuta.blend", 
                     r"\Object", "Penis_CBBE")
    bpy.ops.object.select_all(action='DESELECT')
    obj = TT.find_shape("Penis_CBBE")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', write_bodytri=True)

    print(' ------- Check --------- ')
    nifcheck = pyn.NifFile(outfile1)

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


def TEST_TRIP():
    TT.test_title("TEST_TRIP", "Body tri extra data and file are written on export")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_TRIP.nif")
    outfiletrip = TT.test_file(r"tests/Out/TEST_TRIP.tri")

    TT.append_from_file("BaseMaleBody", True, r"tests\FO4\BodyTalk.blend", r"\Object", "BaseMaleBody")
    bpy.ops.object.select_all(action='DESELECT')
    body = TT.find_shape("BaseMaleBody")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', write_bodytri=True)

    print(' ------- Check --------- ')
    nifcheck = pyn.NifFile(outfile)

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


def TEST_COLORS():
    # Blender's vertex color layers are used to define vertex colors in the nif.
    TT.test_title("TEST_COLORS", "Can read & write vertex colors")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_COLORS_Plane.nif")
    TT.export_from_blend(r"tests\FO4\VertexColors.blend", "Plane",
                      "FO4", outfile)

    nif3 = pyn.NifFile(outfile)
    assert len(nif3.shapes[0].colors) > 0, f"Expected color layers, have: {len(nif3.shapes[0].colors)}"
    cd = nif3.shapes[0].colors
    assert cd[0] == (0.0, 1.0, 0.0, 1.0), f"First vertex found: {cd[0]}"
    assert cd[1] == (1.0, 1.0, 0.0, 1.0), f"Second vertex found: {cd[1]}"
    assert cd[2] == (1.0, 0.0, 0.0, 1.0), f"Second vertex found: {cd[2]}"
    assert cd[3] == (0.0, 0.0, 1.0, 1.0), f"Second vertex found: {cd[3]}"


def TEST_COLORS2():
    TT.test_title("TEST_COLORS2", "Can read & write vertex colors")
    TT.clear_all()
    testfile = TT.test_file(r"tests/FO4/HeadGear1.nif")
    testfileout = TT.test_file(r"tests/Out/TEST_COLORSB_HeadGear1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    colordata = obj.data.vertex_colors.active.data
    targetv = TT.find_vertex(obj.data, (1.62, 7.08, 0.37))
    assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
    for lp in obj.data.loops:
        if lp.vertex_index == targetv:
            assert colordata[lp.index].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[lp.index].color[:]}"

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game="FO4")

    nif2 = pyn.NifFile(testfileout)
    assert nif2.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not reread correctly: {nif2.shapes[0].colors[0]}"
    assert nif2.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0), f"Color 561 not reread correctly: {nif2.shapes[0].colors[561]}"


def TEST_NEW_COLORS():
    # Regression: There have been issues dealing with how Blender handles colors.
    TT.test_title("TEST_NEW_COLORS", "Can write vertex colors that were created in blender")
    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_NEW_COLORS.nif")

    TT.export_from_blend(r"tests\SKYRIMSE\BirdHead.blend",
                      "HeadWhole",
                      "SKYRIMSE",
                      outfile)

    nif = pyn.NifFile(r"tests/Out/TEST_NEW_COLORS.nif")
    shape = nif.shapes[0]
    assert shape.colors, f"Have colors in shape {shape.name}"
    assert shape.colors[10] == (1.0, 1.0, 1.0, 1.0), f"Colors are as expected: {shape.colors[10]}"
    assert shape.shader_attributes.shaderflags2_test(pyn.ShaderFlags2.VERTEX_COLORS), \
        f"ShaderFlags2 vertex colors set: {pyn.ShaderFlags2(shape.shader_attributes.Shader_Flags_2).fullname}"


def TEST_VERTEX_COLOR_IO():
    # On heads, vertex alpha and diffuse alpha work together to determine the final
    # transparency the user sees. We set up Blender shader nodes to provide the same
    # effect.
    TT.test_title("TEST_VERTEX_COLOR_IO", "Vertex colors can be read and written")
    TT.clear_all()
    testfile = TT.test_file(r"tests\FO4\FemaleEyesAO.nif")
    outfile = TT.test_file(r"tests/Out/TEST_VERTEX_COLOR_IO.nif", output=1)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    eyes = TT.find_shape("FemaleEyesAO:0")
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

    nifcheck = pyn.NifFile(outfile)
    eyescheck = nifcheck.shapes[0]
    min_a = min(c[3] for c in eyescheck.colors)
    max_a = max(c[3] for c in eyescheck.colors)
    assert min_a == 0, f"Minimum alpha is 0: {min_a}"
    assert max_a == 1, f"Max alpha is 1: {max_a}"


def TEST_VERTEX_ALPHA_IO():
    TT.test_title("TEST_VERTEX_ALPHA_IO", "Import & export shape with vertex alpha values")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\meshes\actors\character\character assets\maleheadkhajiit.nif")
    outfile = TT.test_file(r"tests/Out/TEST_VERTEX_ALPHA_IO.nif")

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

    nif = pyn.NifFile(testfile)
    head1 = nif.shapes[0]
    nif2 = pyn.NifFile(outfile)
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


def TEST_VERTEX_ALPHA():
    TT.test_title("TEST_VERTEX_ALPHA", "Export shape with vertex alpha values")

    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_VERTEX_ALPHA.nif")
    cube = TT.append_from_file("Cube", True, r"tests\Skyrim\AlphaCube.blend", r"\Object", "Cube")
    bpy.context.view_layer.objects.active = cube
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nifcheck = pyn.NifFile(outfile)
    shapecheck = nifcheck.shapes[0]

    assert shapecheck.shader_attributes.Shader_Flags_1 & pyn.ShaderFlags1.VERTEX_ALPHA, \
        f"Expected VERTEX_ALPHA set: {pyn.ShaderFlags1(shapecheck.shader_attributes.Shader_Flags_1).fullname}"
    assert shapecheck.colors[0][3] == 0.0, f"Expected 0, found {shapecheck.colors[0]}"
    for c in shapecheck.colors:
        assert c[0] == 1.0 and c[1] == 1.0 and c[2] == 1.0, \
            f"Expected all white verts in nif, found {c}"

    bpy.ops.import_scene.pynifly(filepath=outfile)
    objcheck = bpy.context.object
    colorscheck = objcheck.data.vertex_colors
    assert BD.ALPHA_MAP_NAME in colorscheck.keys(), \
        f"Expected alpha map, found {objcheck.data.vertex_colors.keys()}"

    assert min([c.color[1] for c in colorscheck[BD.ALPHA_MAP_NAME].data]) == 0, \
        f"Expected some 0 alpha values"
    for i, c in enumerate(objcheck.data.vertex_colors['Col'].data):
        assert c.color[:] == (1.0, 1.0, 1.0, 1.0), \
            f"Expected all white, full alpha in read object, found {i}: {c.color[:]}"


def TEST_BONE_HIERARCHY():
    # This hair has a complex custom bone hierarchy which have moved with havok.
    # Turns out the bones must be exported in a hierarchy for that to work.
    TT.test_title("TEST_BONE_HIERARCHY", "Bone hierarchy can be written on export")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\Anna.nif")
    outfile = TT.test_file(r"tests/Out/TESTS_BONE_HIERARCHY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    hair = TT.find_shape("KSSMP_Anna")
    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert skel

    print("# -------- Export --------")
    bpy.ops.object.select_all(action='DESELECT')
    hair.select_set(True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True,
                                 do_rename_bones=True)

    print("# ------- Check ---------")
    nifcheck = pyn.NifFile(outfile)
    haircheck = nifcheck.shape_dict["KSSMP_Anna"]

    com = nifcheck.nodes["NPC COM [COM ]"]
    assert TT.VNearEqual(com.transform.translation, (0, 0, 68.9113)), f"COM location is correct: \n{com.transform}"

    spine0 = nifcheck.nodes["NPC Spine [Spn0]"]
    assert TT.VNearEqual(spine0.transform.translation, (0, -5.239852, 3.791618)), f"spine0 location is correct: \n{spine0.transform}"
    spine0Rot = Matrix(spine0.transform.rotation).to_euler()
    assert TT.VNearEqual(spine0Rot, (-0.0436, 0, 0)), f"spine0 rotation correct: {spine0Rot}"

    spine1 = nifcheck.nodes["NPC Spine1 [Spn1]"]
    assert TT.VNearEqual(spine1.transform.translation, (0, 0, 8.748718)), f"spine1 location is correct: \n{spine1.transform}"
    spine1Rot = Matrix(spine1.transform.rotation).to_euler()
    assert TT.VNearEqual(spine1Rot, (0.1509, 0, 0)), f"spine1 rotation correct: {spine1Rot}"

    spine2 = nifcheck.nodes["NPC Spine2 [Spn2]"]
    assert spine2.parent.name == "NPC Spine1 [Spn1]", f"Spine2 parent is correct"
    assert TT.VNearEqual(spine2.transform.translation, (0, -0.017105, 9.864068), 0.01), f"Spine2 location is correct: \n{spine2.transform}"

    head = nifcheck.nodes["NPC Head [Head]"]
    assert TT.VNearEqual(head.transform.translation, (0, 0, 7.392755)), f"head location is correct: \n{head.transform}"
    headRot = Matrix(head.transform.rotation).to_euler()
    assert TT.VNearEqual(headRot, (0.1913, 0.0009, -0.0002), 0.01), f"head rotation correct: {headRot}"

    l3 = nifcheck.nodes["Anna L3"]
    assert l3.parent, f"'Anna L3' parent exists"
    assert l3.parent.name == 'Anna L2', f"'Anna L3' parent is '{l3.parent.name}'"
    assert TT.VNearEqual(l3.transform.translation, (0, 5, -6), 0.1), f"{l3.name} location correct: \n{l3.transform}"

    nif = pyn.NifFile(testfile)
    hair = nif.shape_dict["KSSMP_Anna"]
    assert set(hair.get_used_bones()) == set(haircheck.get_used_bones()), \
        f"The bones written to the shape match original: {haircheck.get_used_bones()}"

    sk2b = hair.get_shape_skin_to_bone("Anna L3")
    sk2bCheck = haircheck.get_shape_skin_to_bone("Anna L3")
    assert NT.XFNearEqual(sk2bCheck, sk2b), \
        f"Anna L3 skin-to-bone matches original: \n{sk2b}"


def TEST_FACEBONE_EXPORT():
    # Facebones are exported along with the regular nif as long as either they are 
    # both selected or if there's an armature modifier for both on the shape. 
    # This test doesn't check that second condition.
    TT.test_title("TEST_FACEBONE_EXPORT", "Test can export facebones + regular nif; shapes with hidden verts export correctly")
    TT.clear_all()

    outfile = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT.nif", output=True)
    outfile_fb = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif", output=True)
    outfile_tri = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT.tri", output=True)
    outfile_chargen = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri")
    outfile2 = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif", output=True)
    outfile2_fb = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif", output=True)

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = TT.append_from_file("HorseFemaleHead", False, r"tests\FO4\HeadFaceBones.blend", r"\Object", "HorseFemaleHead")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen")

    # Exporter generates normal and facebones nif file
    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, "Write the file successfully"
    assert len(nif1.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
    nif2 = pyn.NifFile(outfile_fb)
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

    nif3 = pyn.NifFile(outfile2)
    assert len(nif3.shapes) == 1, "Write the file successfully"
    assert len(nif3.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
    nif4 = pyn.NifFile(outfile2_fb)
    assert len(nif4.shapes) == 1
    assert len(nif4.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

    skinbones = [x for x in nif3.nodes.keys() if "skin_bone" in x]
    assert len(skinbones) == 0, f"Expected no skin_bone nodes in regular nif file; found {skinbones}"
    #assert len([x for x in nif4.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif4.nodes.keys()}"


def TEST_FACEBONE_EXPORT2():
    # Regression. Test that facebones and regular mesh are both exported.
    TT.test_title("TEST_FACEBONE_EXPORT2", "Test can export facebones + regular nif; shapes with hidden verts export correctly")
    TT.clear_all()

    outfile = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif")
    outfile_fb = TT.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif")

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = TT.append_from_file("FemaleHead.Export.001", False, r"tests\FO4\Animatron Space Simple.blend", r"\Object", "FemaleHead.Export.001")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen")

    outnif = pyn.NifFile(outfile)
    assert len(outnif.shapes) >= 1, f"Have shapes in export file: {outnif.shapes}"

    outniffb = pyn.NifFile(outfile_fb)
    assert len(outniffb.shapes) >= 1, f"Have shapes in facebones export file: {outniffb.shapes}"


def TEST_HYENA_PARTITIONS():
    # This Blender object has non-normalized weights--the weights for each vertex do 
    # not always add up to 1. That turns out to screw up the rendering. So check that 
    # the export normalizes them. This isn't done by pynifly or the wrapper layers.
    TT.test_title("TEST_HYENA_PARTITIONS", "Partitions export successfully, with warning")

    TT.clear_all()
    outfile = TT.test_file(r"tests/Out/TEST_HYENA_PARTITIONS.nif", output=True)

    head = TT.append_from_file("HyenaMaleHead", True, r"tests\FO4\HyenaHead.blend", r"\Object", "HyenaMaleHead")
    TT.append_from_file("Skeleton", True, r"tests\FO4\HyenaHead.blend", r"\Object", "Skeleton")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = head
    head.select_set(True)
    bpy.data.objects["FaceBones.Skel"].select_set(True)
    bpy.data.objects["Skeleton"].select_set(True)
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    #assert len(exporter.warnings) == 1, f"One warning reported ({exporter.warnings})"

    nif1 = pyn.NifFile(outfile)
    assert "HyenaMaleHead" in nif1.shape_dict, "Wrote the file successfully"

    head = nif1.shape_dict["HyenaMaleHead"]
    # Only track weights for the first 5000 verts
    vweights = [0.0] * 5000
    maxv = 0
    for group_weights in head.bone_weights.values():
        for weight_pair in group_weights:
            if weight_pair[0] < len(vweights):
                vweights[weight_pair[0]] += weight_pair[1]
                maxv = max(maxv, weight_pair[0])
    for i, w in enumerate(vweights[0:maxv]):
        assert TT.NearEqual(w, 1.0), f"Weights should be 1 for index {i}: {w}"

    # for i in range(0, 5000):
    #     weight_total = 0
    #     for group_weights in head.bone_weights.values():
    #         for weight_pair in group_weights:
    #             if weight_pair[0] == i:
    #                 weight_total += weight_pair[1]
    #     assert TT.NearEqual(weight_total, 1.0), f"Weights should total to 1 for index {i}: {weight_total}"        


def TEST_MULT_PART():
    # Check that we DON'T throw a multiple-partitions error when it's not necessary.
    TT.test_title("TEST_MULT_PART", "Export shape with face that might fall into multiple partititions")
    TT.clear_all()

    outfile = TT.test_file(r"tests/Out/TEST_MULT_PART.nif")
    TT.append_from_file("MaleHead", True, r"tests\SkyrimSE\multiple_partitions.blend", r"\Object", "MaleHead")
    obj = bpy.data.objects["MaleHead"]
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    assert "*MULTIPLE_PARTITIONS*" not in obj.vertex_groups, f"Exported without throwing *MULTIPLE_PARTITIONS* error"


def TEST_BONE_XPORT_POS():
    # Since we use a reference skeleton to make bones, we have to be able to handle
    # the condition where the mesh is not human and the reference skeleton should not
    # be used.
    TT.test_title("TEST_BONE_XPORT_POS", 
               "Test that bones named like vanilla bones but from a different skeleton export to the correct position")

    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\draugr.nif")
    outfile = TT.test_file(r"tests/Out/TEST_BONE_XPORT_POS.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)
    
    draugr = bpy.context.object
    draugr_arma = next(m.object for m in draugr.modifiers if m.type == 'ARMATURE')
    spine2 = draugr_arma.data.bones['NPC Spine2 [Spn2]']
    assert round(spine2.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2.head[2]}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["Body_Male_Naked"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # --- Check nif contents directly ---
    nifcheck = pyn.NifFile(outfile)
    body = nifcheck.shape_dict['Body_Male_Naked']
    spine2_check = nifcheck.nodes['NPC Spine2 [Spn2]']
    spine2_xf = spine2_check.transform
    assert round(spine2_xf.translation[2], 2) == 102.36, \
        f"Expected nif location at z 102.36, found {spine2_xf.translation[2]}"

    thigh_sk2b_check = body.get_shape_skin_to_bone('NPC L Thigh [LThg]')

    assert TT.VNearEqual(thigh_sk2b_check.translation, Vector([-4.0765, -4.4979, 78.4952])), \
        f"Expected skin-to-bone translation Z = 78.4952, found {thigh_sk2b_check.translation[:]}"
    impnif = pyn.NifFile(testfile)
    thsk2b = impnif.shapes[0].get_shape_skin_to_bone('NPC L Thigh [LThg]')
    assert thsk2b.NearEqual(thigh_sk2b_check), f"Entire skin-to-bone transform correct: {thigh_sk2b_check}"

    # --- Check we can import correctly ---
    bpy.ops.import_scene.pynifly(filepath=outfile)
    impcheck = pyn.NifFile(outfile)
    nifbone = impcheck.nodes['NPC Spine2 [Spn2]']
    assert round(nifbone.transform.translation[2], 2) == 102.36, f"Expected nif location at z 102.36, found {nifbone.transform.translation[2]}"

    draugrcheck = bpy.context.object
    draugrcheck_arma = next(m.object for m in draugrcheck.modifiers if m.type == 'ARMATURE')
    spine2check = draugrcheck_arma.data.bones['NPC Spine2 [Spn2]']
    assert round(spine2check.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2check.head[2]}"


def TEST_INV_MARKER():
    # Inventory markers are imported as cameras set up to reflect how the item will be
    # shown in the inventory.
    TT.test_title("TEST_INV_MARKER", "Can handle inventory markers")
    TT.clear_all()

    mx, z = BD.inv_to_cam([0, 0, 3141], 1.8875)
    mx_face = Matrix((
                ( 1.0000, -0.0000,  0.0000,  0),
                (-0.0000, -0.0000, -1.0000, -100),
                ( 0.0000,  1.0000, -0.0000,  0),
                ( 0.0000,  0.0000,  0.0000,  1.0000)))
    assert BD.MatNearEqual(mx, mx_face, epsilon=0.1), f"Inventory matrix is 180 around z: {mx.to_euler()}"

    # ------- Load --------
    testfile = TT.test_file(r"tests\SkyrimSE\Suzanne.nif")
    outfile1 = TT.test_file(r"tests/Out/TEST_INV_MARKER1.nif")
    outfile2 = TT.test_file(r"tests/Out/TEST_INV_MARKER2.nif")
    outfile3 = TT.test_file(r"tests/Out/TEST_INV_MARKER3.nif")
    outfile4 = TT.test_file(r"tests/Out/TEST_INV_MARKER4.nif")
    outfile5 = TT.test_file(r"tests/Out/TEST_INV_MARKER5.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    cam = next(obj for obj in bpy.data.objects if obj.type == 'CAMERA')
    suzanne = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    
    # Camera at [0, 100, 0] pointed back at origin. This is the default position. 
    # Camera is behind Suzanne. 
    cam.matrix_world = Matrix((
            (-1.0000,  0.0000, 0.0000,   0.0000),
            ( 0.0000, -0.0000, 1.0000, 100.0000),
            ( 0.0000,  1.0000, 0.0000,   0.0000),
            ( 0.0000,  0.0000, 0.0000,   1.0000) ))
    expobj = [obj for obj in bpy.context.scene.objects if 'pynRoot' not in obj]
    BD.ObjectSelect(expobj)
    bpy.ops.export_scene.pynifly(filepath=outfile1)

    nifch1 = pyn.NifFile(outfile1)
    assert nifch1.rootNode.inventory_marker[1:4] == [0, 0, 0], f"Have correct inventory marker: {nifch1.rootNode.inventory_marker}"

    # Camera at [0, -100, 0], pointed at origin. This puts the cam on the other side.
    # Camera pointed at Suzanne's face.
    cam.matrix_world = Matrix((
            ( 1.0000, -0.0000,  0.0000,  0),
            (-0.0000, -0.0000, -1.0000, -100),
            ( 0.0000,  1.0000, -0.0000,  0),
            ( 0.0000,  0.0000,  0.0000,  1.0000)))
    expobj = [obj for obj in bpy.context.scene.objects if 'pynRoot' not in obj]
    BD.ObjectSelect(expobj)
    bpy.ops.export_scene.pynifly(filepath=outfile2)

    nifch2 = pyn.NifFile(outfile2)
    assert BD.VNearEqual(nifch2.rootNode.inventory_marker[1:4], [0, 0, 3142], epsilon=2), \
        f"Have correct inventory marker: {nifch2.rootNode.inventory_marker}"

    # Camera on negative X axis, pointed at origin. Shows Suzanne looking to the right.
    cam.matrix_world = Matrix((
            ( 0.0000, 0.0000, -1.0000, -100.0000),
            (-1.0000, 0.0000, -0.0000,   -0.0000),
            ( 0.0000, 1.0000,  0.0000,    0.0000),
            ( 0.0000, 0.0000,  0.0000,    1.0000)))
    expobj = [obj for obj in bpy.context.scene.objects if 'pynRoot' not in obj]
    BD.ObjectSelect(expobj)
    bpy.ops.export_scene.pynifly(filepath=outfile3)

    nifch3 = pyn.NifFile(outfile3)
    assert BD.VNearEqual(nifch3.rootNode.inventory_marker[1:4], [0, 0, 1570], epsilon=2), \
        f"Have correct inventory marker: {nifch3.rootNode.inventory_marker}"

    # Inventory item can be oriented arbitrarily.
    suzanne.matrix_world = Matrix((
            (0.5702, -0.3352, -0.7501, 0.0000),
            (0.6928,  0.6869,  0.2196, 0.0000),
            (0.4416, -0.6448,  0.6238, 0.0000),
            (0.0000,  0.0000,  0.0000, 1.0000)))
    cam.matrix_world = Matrix((
            (-0.1333, -0.9077,  0.3978,  39.7837),
            ( 0.6190, -0.3898, -0.6819, -68.1890),
            ( 0.7740,  0.1553,  0.6138,  61.3801),
            ( 0.0000,  0.0000,  0.0000,   1.0000)))

    expobj = [obj for obj in bpy.context.scene.objects if 'pynRoot' not in obj]
    BD.ObjectSelect(expobj)
    bpy.ops.export_scene.pynifly(filepath=outfile4)

    # Large inventory item can be viewed by changing zoom factor.
    suzanne.matrix_world = Matrix((
            (2.8508, -1.6760, -3.7503, 0.0000),
            (3.4640,  3.4345,  1.0980, 0.0000),
            (2.2082, -3.2240,  3.1192, 0.0000),
            (0.0000,  0.0000,  0.0000, 1.0000)))
    cam.matrix_world = Matrix((
            (-0.1333, -0.9077,  0.3978,  39.7837),
            ( 0.6190, -0.3898, -0.6819, -68.1890),
            ( 0.7740,  0.1553,  0.6138,  61.3801),
            ( 0.0000,  0.0000,  0.0000,   1.0000)))
    cam.data.lens = 38

    expobj = [obj for obj in bpy.context.scene.objects if 'pynRoot' not in obj]
    BD.ObjectSelect(expobj)
    bpy.ops.export_scene.pynifly(filepath=outfile5)

    # Imports
    TT.clear_all()

    # First test had the camera at the neutral position (back of Suzanne's head).
    bpy.ops.import_scene.pynifly(filepath=outfile1)
    im = next(obj for obj in bpy.data.objects if obj.type=='CAMERA')
    assert BD.MatNearEqual(im.matrix_world, BD.CAMERA_NEUTRAL), f"Inventory matrix neutral: {im.matrix_world.to_euler()}"

    # Second test had the camera at the front of Suzanne's head.
    TT.clear_all()
    bpy.ops.import_scene.pynifly(filepath=outfile2)
    im = next(obj for obj in bpy.data.objects if obj.type=='CAMERA')
    assert BD.MatNearEqual(im.matrix_world, 
        Matrix((
            ( 1.0000, -0.0000, -0.0006,   -0.0593),
            (-0.0006, -0.0000, -1.0000, -100.0000),
            ( 0.0000,  1.0000, -0.0000,    0.0000),
            ( 0.0000,  0.0000,  0.0000,    1.0000)))
            ), f"Inventory matrix neutral: {im.matrix_world.to_euler()}"

    # Third test, suzanne looks right.
    TT.clear_all()
    bpy.ops.import_scene.pynifly(filepath=outfile3)
    im = next(obj for obj in bpy.data.objects if obj.type=='CAMERA')
    assert BD.MatNearEqual(im.matrix_world, 
        Matrix((
            ( 0.0002, -0.0000, -1.0000, -100.0000),
            (-1.0000,  0.0000, -0.0002,   -0.0204),
            ( 0.0000,  1.0000, -0.0000,    0.0000),
            ( 0.0000,  0.0000,  0.0000,    1.0000) ))
            ), f"Inventory matrix neutral: {im.matrix_world.to_euler()}"


def TEST_TREE():
    # Trees in FO4 use a special root node and a special shape node.
    TT.test_title("TEST_TREE", "Can read and write FO4 tree")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\FO4\TreeMaplePreWar01Orange.nif")
    outfile = TT.test_file(r"tests/Out/TEST_TREE.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    root = next(obj for obj in bpy.data.objects if 'pynRoot' in obj)
    assert root['pynBlockName'] == "BSLeafAnimNode", f"Have correct root type: {root['pynBlockName']}"
    
    # We don't do collisions for FO4
    assert len([obj for obj in bpy.data.objects if obj.name.startswith('bhk')]) == 0, \
        f"Have no collision objects."

    tree = next(obj for obj in bpy.data.objects if obj.name.startswith("Tree") and obj.type == 'MESH')
    assert tree['pynBlockName'] == "BSMeshLODTriShape", f"Have correct block type: {tree['pynBlockName']}"
    assert int(tree['lodSize0']) == 1126, f"Have correct LOD0 size"


def TEST_BOW():
    # The bow has a simple collision that we can import and export.
    # Note the bow nif as shipped by Bethesda throws errors on import, and the 
    # collision does not match the mesh closely at all. This test adjusts it on
    # export because it was too ugly.
    TT.test_title("TEST_BOW", "Can read and write bow")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TT.test_file(r"tests/Out/TEST_BOW.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    # Check root info
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    assert root["pynBlockName"] == 'BSFadeNode', "pynRootNode_BlockType holds the type of root node for the given shape"
    assert root["pynNodeName"] == "GlassBowSkinned.nif", "pynRootNode_Name holds the name for the root node"
    assert root["pynNodeFlags"] == "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR", f"'pynNodeFlags' holds the flags on the root node: {root['pynRootNode_Flags']}"

    # Check collision info
    coll = TT.find_shape('bhkCollisionObject', type='EMPTY')
    assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
    assert coll['pynCollisionTarget'] == 'Bow_MidBone', f"'Target' names the object the collision affects, in this case a bone: {coll['pynCollisionTarget']}"

    collbody = coll.children[0]
    assert collbody.name == 'bhkRigidBodyT', f"Child of collision is the collision body object"
    assert collbody['collisionFilter_layer'] == nifdefs.SkyrimCollisionLayer.WEAPON.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
    assert collbody["collisionResponse"] == nifdefs.hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"
    assert TT.VNearEqual(collbody.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), f"Collision body rotation correct: {collbody.rotation_quaternion}"

    collshape = collbody.children[0]
    assert collshape.name == 'bhkBoxShape', f"Collision shape is child of the collision body"
    assert collshape['bhkMaterial'] == 'MATERIAL_BOWS_STAVES', f"Shape material is a custom property: {collshape['bhkMaterial']}"
    assert round(collshape['bhkRadius'],4) == 0.0136, f"Radius property available as custom property: {collshape['bhkRadius']}"
    corner = map(abs, collshape.data.vertices[0].co)
    assert TT.VNearEqual(corner, [11.01445, 57.6582, 0.95413]), f"Collision shape in correct position: {corner}"

    bged = TT.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    assert bged['BSBehaviorGraphExtraData_Value'] == "Weapons\Bow\BowProject.hkx", f"BGED node contains bow project: {bged['BSBehaviorGraphExtraData_Value']}"

    strd = TT.find_shape("NiStringExtraData", type='EMPTY')
    assert strd['NiStringExtraData_Value'] == "WeaponBow", f"Str ED node contains bow value: {strd['NiStringExtraData_Value']}"

    bsxf = TT.find_shape("BSXFlags", type='EMPTY')
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    assert bsxf.parent == root, f"Extra data imported under root"
    assert bsxf['BSXFlags_Name'] == "BSX", f"BSX Flags contain name BSX: {bsxf['BSXFlags_Name']}"
    assert bsxf['BSXFlags_Value'] == "HAVOC | COMPLEX | DYNAMIC | ARTICULATED", "BSX Flags object contains correct flags: {bsxf['BSXFlags_Value']}"

    invm = TT.find_shape("BSInvMarker", type='CAMERA')
    assert invm['BSInvMarker_Name'] == "INV", f"Inventory marker shape has correct name: {invm['BSInvMarker_Name']}"
    assert invm['BSInvMarker_RotX'] == 4712, f"Inventory marker rotation correct: {invm['BSInvMarker_RotX']}"
    assert round(invm['BSInvMarker_Zoom'], 4) == 1.1273, f"Inventory marker zoom correct: {invm['BSInvMarker_Zoom']}"
    
    # ------- Export --------

    # Move the edge of the collision box so it covers the bow better
    for v in collshape.data.vertices:
        if v.co.x > 0:
            v.co.x = 16.5

    # Exporting the root object takes everything with it and sets root properties.
    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check Results --------

    impnif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    TT.compare_shapes(impnif.shape_dict['ElvenBowSkinned:0'],
                    nifcheck.shape_dict['ElvenBowSkinned:0'],
                    obj)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    bsxcheck = nifcheck.rootNode.bsx_flags
    assert bsxcheck == ["BSX", 202], f"BSX Flag node found: {bsxcheck}"

    bsinvcheck = nifcheck.rootNode.inventory_marker
    assert bsinvcheck[0:4] == ["INV", 4712, 0, 785], f"Inventory marker set: {bsinvcheck}"
    # assert round(bsinvcheck[4], 4) == 1.1273, f"Inventory marker zoom set: {bsinvcheck[4]}"

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert nifdefs.bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck.get_node_xform_to_global("Bow_MidBone")
    assert TT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = mbc_xf.as_matrix().to_euler()
    assert TT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck = collcheck.body
    p = bodycheck.properties
    assert p.collisionFilter_layer == nifdefs.SkyrimCollisionLayer.WEAPON, f"Have correct collision layer"
    assert TT.VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    assert TT.VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


def TEST_BOW2():
    TT.test_title("TEST_BOW2", "Can modify collision shape location")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile2 = TT.test_file(r"tests/Out/TEST_BOW2.nif")
    
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = TT.find_shape('ElvenBowSkinned')
    coll = TT.find_shape('bhkCollisionObject', type='EMPTY')
    collbody = coll.children[0]
    collshape = collbody.children[0]
    bged = TT.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TT.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TT.find_shape("BSXFlags", type='EMPTY')
    invm = TT.find_shape("BSInvMarker", type='CAMERA')

    # ------- Export --------
    # Move the edge of the collision box so it covers the bow better
    for v in collshape.data.vertices:
        if v.co.x > 0:
            v.co.x = 16.5

    # Move the collision object 
    coll.location = coll.location + Vector([5, 10, 0])
    collshape.location = collshape.location + Vector([-5, -10, 0])

    BD.ObjectSelect([obj, coll, bged, strd, bsxf, invm], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile2, target_game='SKYRIMSE')

    # ------- Check Results 2 --------

    nifcheck2 = pyn.NifFile(outfile2)

    midbowcheck2 = nifcheck2.nodes["Bow_MidBone"]
    collcheck2 = midbowcheck2.collision_object
    assert collcheck2.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck2.blockname}"
    assert nifdefs.bhkCOFlags(collcheck2.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck2.get_node_xform_to_global("Bow_MidBone")
    assert TT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = mbc_xf.as_matrix().to_euler()
    assert TT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck2 = collcheck2.body
    p = bodycheck2.properties
    assert TT.VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    assert TT.VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


def TEST_BOW3():
    # We can change the collision by editing the Blender shapes
    TT.test_title("TEST_BOW3", "Can modify collision shape type")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile3 = TT.test_file(r"tests/Out/TEST_BOW3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = TT.find_shape('ElvenBowSkinned')
    coll = TT.find_shape('bhkCollisionObject', type='EMPTY')
    collbody = coll.children[0]
    collshape = collbody.children[0]
    bged = TT.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TT.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TT.find_shape("BSXFlags", type='EMPTY')
    invm = TT.find_shape("BSInvMarker", type='EMPTY')

    # ------- Export --------

    # Move the collision object 
    for v in collshape.data.vertices:
        if TT.NearEqual(v.co.x, 11.01, epsilon=0.5):
            v.co.x = 16.875
            if v.co.y > 0:
                v.co.y = 26.72
            else:
                v.co.y = -26.72
    collshape.name = "bhkConvexVerticesShape"
    collbody.name = "bhkRigidBody"

    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile3, target_game='SKYRIMSE')
    
    # ------- Check Results 3 --------

    nifcheck3 = pyn.NifFile(outfile3)

    midbowcheck3 = nifcheck3.nodes["Bow_MidBone"]
    collcheck3 = midbowcheck3.collision_object
    assert collcheck3.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck3.blockname}"
    assert nifdefs.bhkCOFlags(collcheck3.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck3.get_node_xform_to_global("Bow_MidBone")
    assert TT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = mbc_xf.as_matrix().to_euler()
    assert TT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck3 = collcheck3.body

    cshapecheck3 = bodycheck3.shape
    assert cshapecheck3.blockname == "bhkConvexVerticesShape", f"Shape is convex vertices: {cshapecheck3.blockname}"
    assert TT.VNearEqual(cshapecheck3.vertices[0], (-0.73, -0.267, 0.014, 0.0)), f"Convex shape is correct"


def TEST_COLLISION_HIER():
    # These leeks are two shapes collected under an NiNode, with the collision on the 
    # NiNode. 
    TT.test_title("TEST_COLLISION_HIER", "Can read and write hierarchy of nodes containing shapes")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\Skyrim\grilledleekstest.nif")
    outfile = TT.test_file(r"tests/Out/TEST_COLLISION_HIER.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek4 = TT.find_shape("Leek04")
    leek0 = TT.find_shape("Leek04:0")
    leek1 = TT.find_shape("Leek04:1")
    c1 = TT.find_shape("bhkCollisionObject", type='EMPTY')
    rb = TT.find_shape("bhkRigidBody", type='EMPTY')
    cshape = TT.find_shape("bhkConvexVerticesShape")
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

    # Select the objects to export. Do this instead of exporting the root. Should still
    # work.
    leek4 = bpy.data.objects["Leek04"]
    bsxf = TT.find_shape("BSXFlags", type='EMPTY')
    invm = TT.find_shape("BSInvMarker", type='CAMERA')
    BD.ObjectSelect([leek4, bsxf, invm], active=True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check Results --------

    nifOrig = pyn.NifFile(testfile)
    l4NodeOrig = nifOrig.nodes["Leek04"]
    collOrig = l4NodeOrig.collision_object
    rbOrig = collOrig.body
    shOrig = rbOrig.shape

    nifcheck = pyn.NifFile(outfile)
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
    assert TT.VNearEqual(shCheck.vertices[0], shOrig.vertices[0]), f"Collision vertices match 0: {shCheck.vertices[0][:]} == {shOrig.vertices[0][:]}"
    assert TT.VNearEqual(shCheck.vertices[5], shOrig.vertices[5]), f"Collision vertices match 0: {shCheck.vertices[5][:]} == {shOrig.vertices[5][:]}"


def TEST_NORM():
    TT.test_title("TEST_NORM", "Normals are read correctly")
    TT.clear_all()
    testfile = TT.test_file(r"tests/FO4/CheetahMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TT.find_shape("CheetahMaleHead")

    head.data.calc_normals_split()

    vi =  TT.find_vertex(head.data, (-4.92188, 0.646485, -10.0156), epsilon=0.01)
    targetvert = head.data.vertices[vi]
    assert targetvert.normal.x < -0.5, \
        f"Vertex normal for vertex {targetvert.index} as expected: {targetvert.normal}"

    vertloops = [l.index for l in head.data.loops if l.vertex_index == targetvert.index]
    custnormal = head.data.loops[vertloops[0]].normal
    print(f"TEST_NORM custnormal: loop {vertloops[0]} has normal {custnormal}")
    assert TT.VNearEqual(custnormal, [-0.1772, 0.4291, 0.8857]), \
        f"Custom normal different from vertex normal: {custnormal}"


def TEST_ROGUE01():
    # Custom split normals change the direction light bounces off an object. They may be
    # set to eliminate seams between parts of a mesh, or between two meshes.
    TT.test_title("TEST_ROGUE01", "Mesh with wonky normals exports correctly")
    TT.clear_all()
    testfile = TT.test_file(r"tests/Out/TEST_ROGUE01.nif")

    obj = TT.append_from_file("MHelmetLight:0", False, r"tests\FO4\WonkyNormals.blend", r"\Object", "MHelmetLight:0")
    assert obj.name == "MHelmetLight:0", "Got the right object"
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")

    nif2 = pyn.NifFile(testfile)
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


def TEST_ROGUE02():
    # Shape keys and custom normals interfere with each other. If a shape key warps the
    # mesh, what direction should a custom normal face after the warp? We just preserve
    # the direction and leave it to the user to separate out the shape key if they don't
    # like the result.
    TT.test_title("TEST_ROGUE02", "Shape keys export normals correctly")
    TT.clear_all()
    testfile = TT.test_file(r"tests/Out/TEST_ROGUE02.nif")
    outfile = TT.test_file(r"tests/Out/TEST_ROGUE02_warp.nif")

    TT.export_from_blend(r"tests\Skyrim\ROGUE02-normals.blend",
                         "Plane", "SKYRIM", testfile, "_warp")

    nif2 = pyn.NifFile(outfile)
    shape2 = nif2.shapes[0]
    assert len(shape2.verts) == 25, f"Export shouldn't create extra vertices, found {len(shape2.verts)}"
    v = [round(x, 1) for x in shape2.verts[18]]
    assert v == [0.0, 0.0, 0.2], f"Vertex found at incorrect position: {v}"
    n = [round(x, 1) for x in shape2.normals[8]]
    assert n == [0, 1, 0], f"Normal should point along y axis, instead: {n}"


def TEST_NORMAL_SEAM():
    TT.test_title("TEST_NORMAL_SEAM", "Normals on a split seam are seamless")
    TT.clear_all()
    testfile = TT.test_file(r"tests/Out/TEST_NORMAL_SEAM.nif")
    outfile = TT.test_file(r"tests/Out/TEST_NORMAL_SEAM_Dog.nif")

    TT.export_from_blend(r"tests\FO4\TestKnitCap.blend", "MLongshoremansCap:0",
                      "FO4", testfile)

    nif2 = pyn.NifFile(outfile)
    shape2 = nif2.shapes[0]
    target_vert = [i for i, v in enumerate(shape2.verts) if TT.VNearEqual(v, (0.00037, 7.9961, 9.34375))]

    assert len(target_vert) == 2, f"Expect vert to have been split: {target_vert}"
    assert TT.VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


def TEST_NIFTOOLS_NAMES():
    # We allow renaming bones according to the NifTools format. Someday this may allow
    # us to use their animation tools, but this is not that day.
    TT.test_title("TEST_NIFTOOLS_NAMES", "Can import nif with niftools' naming convention")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\Skyrim\malebody_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones_niftools=True, 
                                 do_create_bones=False, use_blender_xf=True)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')

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

        inif = pyn.NifFile(testfile)
        skel = inif.reference_skel
        skel_calf = skel.nodes['CME L Thigh [LThg]']
        c = arma.data.bones["NPC Calf [Clf].L"]
        assert c.parent, f"Bones are put into a hierarchy: {c.parent}"
        assert c.parent.name == 'CME L Thigh [LThg]', f"Parent/child relationships are maintained: {c.parent.name}"

        body = TT.find_shape("MaleUnderwearBody1:0")
        assert "NPC Calf [Clf].L" in body.vertex_groups, f"Vertex groups follow niftools naming convention: {body.vertex_groups.keys()}"


def TEST_COLLISION_MULTI():
    TT.test_title("TEST_COLLISION_MULTI", "Can read and write shape with multiple collision shapes")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\Skyrim\grilledleeks01.nif")
    outfile = TT.test_file(r"tests/Out/TEST_COLLISION_MULTI.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek1 = TT.find_shape("Leek01", type='EMPTY')
    leek10 = TT.find_shape("Leek01:0")
    leek11 = TT.find_shape("Leek01:1")
    leek2 = TT.find_shape("Leek02", type='EMPTY')
    leek3 = TT.find_shape("Leek03", type='EMPTY')
    leek4 = TT.find_shape("Leek04", type='EMPTY')
    c1 = TT.find_shape("bhkCollisionObject", leek1.children, type='EMPTY')
    c2 = TT.find_shape("bhkCollisionObject", leek2.children, type='EMPTY')
    assert set(leek1.children) == set( (c1, leek10, leek11) ), f"Children of Leek01 are correct: {leek1.children} == {c1}, {leek10}, {leek11}"
    
    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check ---------
    nif = pyn.NifFile(outfile)
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


def TEST_COLLISION_CONVEXVERT():
    def do_test(bx):
        TT.test_title("TEST_COLLISION_CONVEXVERT", "Can read and write shape with convex verts collision shape at scale {bx}")
        TT.clear_all()

        # ------- Load --------
        testfile = TT.test_file(r"tests\Skyrim\cheesewedge01.nif")
        outfile = TT.test_file(f"tests/Out/TEST_COLLISION_CONVEXVERT.{bx}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        # Check transform
        obj = TT.find_shape('CheeseWedge')
        assert TT.VNearEqual(obj.location, (0,0,0)), f"Cheese wedge at right location: {obj.location}"
        assert TT.VNearEqual(obj.rotation_euler, (0,0,0)), f"Cheese wedge not rotated: {obj.rotation_euler}"
        assert obj.scale == Vector((1,1,1)), f"Cheese wedge scale 1"

        # Check collision info
        coll = TT.find_shape('bhkCollisionObject', type='EMPTY')
        assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
        assert 'pynRoot' in coll.parent, f"Collision shape's parent is root"

        collbody = coll.children[0]
        assert collbody.name == 'bhkRigidBody', f"Child of collision is the collision body object"
        assert collbody['collisionFilter_layer'] == nifdefs.SkyrimCollisionLayer.CLUTTER.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
        assert collbody["collisionResponse"] == nifdefs.hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"

        collshape = collbody.children[0]
        assert collshape.name == 'bhkConvexVerticesShape', f"Collision shape is child of the collision body"
        assert collshape['bhkMaterial'] == 'CLOTH', f"Shape material is a custom property: {collshape['bhkMaterial']}"
        obj = TT.find_shape('CheeseWedge01', collection=bpy.context.selected_objects)
        xmax1 = max([v.co.x for v in obj.data.vertices])
        xmax2 = max([v.co.x for v in collshape.data.vertices])
        assert abs(xmax1 - xmax2) < 0.5, f"Max x vertex nearly the same: {xmax1} == {xmax2}"
        corner = collshape.data.vertices[0].co
        assert TT.VNearEqual(corner, (-4.18715, -7.89243, 7.08596)), f"Collision shape in correct position: {corner}"

        # ------- Export --------

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', use_blender_xf=bx)

        # ------- Check Results --------

        niforig = pyn.NifFile(testfile)
        rootorig = niforig.rootNode
        collorig = rootorig.collision_object
        bodyorig = collorig.body
        cvsorig = bodyorig.shape

        nifcheck = pyn.NifFile(outfile)
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
        assert cvscheck.properties.bhkMaterial == nifdefs.SkyrimHavokMaterial.CLOTH, \
            "Collision body shape material is readable"

        minxch = min(v[0] for v in cvscheck.vertices)
        maxxch = max(v[0] for v in cvscheck.vertices)
        minxorig = min(v[0] for v in cvsorig.vertices)
        maxxorig = max(v[0] for v in cvsorig.vertices)

        assert TT.NearEqual(minxch, minxorig), f"Vertex x is correct: {minxch} == {minxorig}"
        assert TT.NearEqual(maxxch, maxxorig), f"Vertex x is correct: {maxxch} == {maxxorig}"

        # Re-import
        #
        # There have been issues with importing the exported nif and having the 
        # collision be wrong
        TT.clear_all()
        bpy.ops.import_scene.pynifly(filepath=outfile)

        impcollshape = TT.find_shape("bhkConvexVerticesShape")
        impcollshape = TT.find_shape("bhkConvexVerticesShape")
        zmin = min([v.co.z for v in impcollshape.data.vertices])
        assert zmin >= -0.01, f"Minimum z is positive: {zmin}"

    do_test(False)
    do_test(True)

    
def TEST_COLLISION_CAPSULE():
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    def do_test(bx):
        TT.test_title("TEST_COLLISION_CAPSULE", 
                    f"Can read and write shape with collision capsule shapes with Blender transforms {bx}")
        TT.clear_all()

        # ------- Load --------
        testfile = TT.test_file(r"tests\Skyrim\staff04.nif")
        outfile = TT.test_file(f"tests/Out/TEST_COLLISION_CAPSULE.{bx}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        staff = TT.find_shape("3rdPersonStaff04")
        coll = TT.find_shape("bhkCollisionObject", type="EMPTY")
        collbody = coll.children[0]
        collshape = collbody.children[0]
        strd = TT.find_shape("NiStringExtraData", type="EMPTY")
        bsxf = TT.find_shape("BSXFlags", type="EMPTY")
        invm = TT.find_shape("BSInvMarker", type="EMPTY")

        # The staff has bits that stick out, so its bounding box is a bit larger than
        # the collision's.
        staffmin, staffmax = TT.get_obj_bbox(staff, worldspace=True)
        collmin, collmax = TT.get_obj_bbox(collshape, worldspace=True)
        assert staffmax[0] > collmax[0], f"Staff surrounds collision: {staffmax}, {collmax}"
        assert staffmax[1] > collmax[1], f"Staff surrounds collision: {staffmax}, {collmax}"
        assert staffmax[2] > collmax[2], f"Staff surrounds collision: {staffmax}, {collmax}"
        assert staffmin[0] < collmin[0], f"Staff surrounds collision: {staffmax}, {collmax}"
        assert staffmin[1] < collmin[1], f"Staff surrounds collision: {staffmax}, {collmax}"
        assert staffmin[2] < collmin[2], f"Staff surrounds collision: {staffmax}, {collmax}"

        # -------- Export --------
        BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', use_blender_xf=bx)

        # ------- Check ---------
        nifcheck = pyn.NifFile(outfile)
        staffcheck = nifcheck.shape_dict["3rdPersonStaff04:1"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        shapecheck = rbcheck.shape
        assert shapecheck.blockname == "bhkCapsuleShape", f"Got a capsule collision back {shapecheck.blockname}"

        niforig = pyn.NifFile(testfile)
        collorig = niforig.rootNode.collision_object
        rborig = collorig.body
        shapeorig = rborig.shape
        assert TT.NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), \
            f"Wrote the correct radius: {shapecheck.properties.radius1}"
        
        assert TT.NearEqual(shapeorig.properties.point1[1], 
                            shapecheck.properties.point1[1],
                            epsilon=0.05), \
            f"Wrote the correct radius: {shapecheck.properties.point1[1]}"

    do_test(False)
    do_test(True)


def TEST_COLLISION_CAPSULE2():
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    def do_test(bx):
        TT.test_title("TEST_COLLISION_CAPSULE2", 
                    f"Can read and write shape with collision capsule shapes with Blender transforms {bx}")
        TT.clear_all()

        # ------- Load --------
        testfile = TT.test_file(r"tests\Skyrim\staff04-collision.nif")
        outfile = TT.test_file(f"tests/Out/TEST_COLLISION_CAPSULE2.{bx}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        staff = TT.find_shape("3rdPersonStaff04")
        coll = TT.find_shape("bhkCollisionObject", type="EMPTY")
        collbody = coll.children[0]
        collshape = collbody.children[0]

        # -------- Export --------
        BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', use_blender_xf=bx)

        # ------- Check ---------
        nifcheck = pyn.NifFile(outfile)
        staffcheck = nifcheck.shape_dict["3rdPersonStaff04:1"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        shapecheck = rbcheck.shape
        assert shapecheck.blockname == "bhkCapsuleShape", f"Got a capsule collision back {shapecheck.blockname}"

        niforig = pyn.NifFile(testfile)
        collorig = niforig.rootNode.collision_object
        rborig = collorig.body
        shapeorig = rborig.shape
        assert TT.NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), \
            f"Wrote the correct radius: {shapecheck.properties.radius1}"
        
        assert TT.NearEqual(shapeorig.properties.point1[1], 
                            shapecheck.properties.point1[1]), \
            f"Wrote the correct radius: {shapecheck.properties.point1[1]}"

    do_test(False)
    do_test(True)


def TEST_COLLISION_LIST():
    def run_test(bx):
        TT.test_title("TEST_COLLISION_LIST", 
                    f"Can read and write shape with collision list and collision transform shapes with Blender transform {bx}")
        TT.clear_all()

        # ------- Load --------
        testfile = TT.test_file(r"tests\Skyrim\falmerstaff.nif")
        outfile = TT.test_file(f"tests/Out/TEST_COLLISION_LIST{bx}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        staff = TT.find_shape("Staff3rdPerson:0")
        coll = TT.find_shape("bhkCollisionObject", type='EMPTY')
        collbody = coll.children[0]
        collshape = collbody.children[0]
        strd = TT.find_shape("NiStringExtraData", type='EMPTY')
        bsxf = TT.find_shape("BSXFlags", type='EMPTY')
        invm = TT.find_shape("BSInvMarker", type='EMPTY')

        assert collshape.name.startswith("bhkListShape"), f"Found list collision shape: {collshape.name}"
        assert len(collshape.children) == 3, f" Collision shape has children"
    
        # -------- Export --------
        BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', use_blender_xf=bx)

        # ------- Check ---------
        niforig = pyn.NifFile(testfile)
        stafforig = niforig.shape_dict["Staff3rdPerson:0"]
        collorig = niforig.rootNode.collision_object
        listorig = collorig.body.shape
        xfshapesorig = listorig.children[:]
        xfshapematorig = [s.properties.bhkMaterial for s in xfshapesorig]

        nifcheck = pyn.NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff3rdPerson:0"]
        collcheck = nifcheck.rootNode.collision_object
        listcheck = collcheck.body.shape
        xfshapescheck = listcheck.children[:]
        xfshapematcheck = [s.properties.bhkMaterial for s in xfshapescheck]

        assert xfshapematcheck == xfshapematorig, \
            f"Materials written to ConvexTransformShape: {xfshapematcheck} == {xfshapematorig}"

        assert listcheck.blockname == "bhkListShape", f"Got a list collision back {listcheck.blockname}"
        assert len(listcheck.children) == 3, f"Got our list elements back: {len(listcheck.children)}"

        convex_xf_shape = listcheck.children[0]
        convex_xf = Matrix(convex_xf_shape.properties.transform)
        assert convex_xf.to_scale()[0] == 1.0, f"Have the correct scale: {convex_xf.to_scale()}"
        assert convex_xf_shape.child.blockname == "bhkBoxShape", f"Found the box shape"

        cts45check = None
        for cts in listcheck.children:
            erot = Matrix(cts.transform).to_euler()
            if TT.NearEqual(erot.x, math.radians(45)):
                cts45check = cts
        boxdiag = cts45check.child
        assert TT.NearEqual(boxdiag.properties.bhkDimensions[1], 0.170421), f"Diagonal box has correct size: {boxdiag.properties.bhkDimensions[1]}"

    run_test(True)
    run_test(False)


def TEST_CHANGE_COLLISION():
    TT.test_title("TEST_CHANGE_COLLISION", "Changing collision type works correctly")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TT.test_file(r"tests/Out/TEST_CHANGE_COLLISION.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    coll = TT.find_shape('bhkCollisionObject', type='EMPTY')
    collbody = coll.children[0]
    collshape = TT.find_shape('bhkBoxShape')
    bged = TT.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TT.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TT.find_shape("BSXFlags", type='EMPTY')
    invm = TT.find_shape("BSInvMarker", type='EMPTY')
    assert collshape.name == 'bhkBoxShape', f"Found collision shape"
    
    collshape.name = "bhkConvexVerticesShape"

    # ------- Export --------

    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check Results --------

    nifcheck = pyn.NifFile(outfile)
    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    bodycheck = collcheck.body
    assert bodycheck.properties.bufType == nifdefs.PynBufferTypes.bhkRigidBodyBufType, f"Have correct buffer type"

    names = [x[0] for x in nifcheck.behavior_graph_data]
    assert "BGED" in names, f"Error: Expected BGED in {names}"
    bgedCheck = nifcheck.behavior_graph_data[0]
    log.debug(f"BGED value is {bgedCheck}")
    assert bgedCheck == ("BGED", "Weapons\\Bow\\BowProject.hkx", False), f"Extra data value = {bgedCheck}"
    assert not bgedCheck[2], f"Extra data controls base skeleton: {bgedCheck}"


def TEST_COLLISION_XFORM():
    if bpy.app.version[0] >= 3:
        # Blender V2.x does not import the whole parent chain when appending an object from
        # another file, so don't try to run this on that version.
        TT.test_title("TEST_COLLISION_XFORM", "Can read and write shape with collision capsule shapes")
        TT.clear_all()

        # ------- Load --------
        outfile = TT.test_file(r"tests/Out/TEST_COLLISION_XFORM.nif")

        TT.append_from_file("Staff", True, r"tests\SkyrimSE\staff.blend", r"\Object", "Staff")
        TT.append_from_file("BSInvMarker", True, r"tests\SkyrimSE\staff.blend", r"\Object", "BSInvMarker")
        TT.append_from_file("BSXFlags", True, r"tests\SkyrimSE\staff.blend", r"\Object", "BSXFlags")
        TT.append_from_file("NiStringExtraData", True, r"tests\SkyrimSE\staff.blend", r"\Object", "NiStringExtraData")
        TT.append_from_file("bhkConvexVerticesShape.002", True, r"tests\SkyrimSE\staff.blend", r"\Object", "bhkConvexVerticesShape.002")

        # -------- Export --------
        BD.ObjectSelect([
            TT.find_shape("Staff"),
            TT.find_shape("bhkCollisionObject", type="EMPTY"), 
            TT.find_shape("NiStringExtraData", type='EMPTY'),
            TT.find_shape("BSXFlags", type='EMPTY'),
            TT.find_shape("BSInvMarker", type='EMPTY'),
            ], active=True)

        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

        # ------- Check ---------
        # NOTE the collision is only on one of the tines
        nifcheck = pyn.NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        listcheck = rbcheck.shape
        cvShapes = [c for c in listcheck.children if c.blockname == "bhkConvexVerticesShape"]
        maxz = max([v[2] for v in cvShapes[0].vertices])
        assert maxz < 0, f"All verts on collisions shape on negative z axis: {maxz}"

        
def TEST_CONNECT_POINT():
    # FO4 has a complex method of attaching shapes to other shapes in game, using
    # connect points. These can be created and manipulated in Blender.
    TT.test_title("TEST_CONNECT_POINT", "Connect points are imported and exported")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    outfile = TT.test_file(r"tests\Out\TEST_CONNECT_POINT.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    parentnames = set(['P-Barrel', 'P-Casing', 'P-Grip', 'P-Mag', 'P-Scope'])
    childnames = ['C-Receiver', 'C-Reciever']

    # Empties are not left selected by import
    shotgun = next(filter(lambda x: x.name.startswith('CombatShotgunReceiver:0'), 
                          bpy.context.selected_objects))
    cpparents = list(filter(lambda x: x.name.startswith('BSConnectPointParents'), 
                            bpy.data.objects))
    cpchildren = list(filter(lambda x: x.name.startswith('BSConnectPointChildren'), 
                             bpy.data.objects))
    cpcasing = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Casing'), 
                           bpy.data.objects))
    
    assert len(cpparents) == 5, f"Found parent connect points: {cpparents}"
    p = set(x.name.split("::")[1] for x in cpparents)
    assert p == parentnames, f"Found correct parentnames: {p}"

    assert cpchildren, f"Found child connect points: {cpchildren}"
    assert (cpchildren[0]['PYN_CONNECT_CHILD_0'] == "C-Receiver") or \
        (cpchildren[0]['PYN_CONNECT_CHILD_1'] == "C-Receiver"), \
        f"Did not find child name"

    # assert TT.NearEqual(cpcasing.rotation_quaternion.w, 0.9098), f"Have correct rotation: {cpcasing.rotation_quaternion}"
    assert cpcasing.parent.name == "CombatShotgunReceiver", f"Casing has correct parent {cpcasing.parent.name}"

    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    ## --------- Check ----------
    nifsrc = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    pcheck = set(x.name.decode() for x in nifcheck.connect_points_parent)
    assert pcheck == parentnames, f"Wrote correct parent names: {pcheck}"
    pcasingsrc = [cp for cp in nifsrc.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    pcasing = [cp for cp in nifcheck.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    assert TT.VNearEqual(pcasing.rotation[:], pcasingsrc.rotation[:]), f"Have correct rotation: {pcasing}"

    chnames = nifcheck.connect_points_child
    chnames.sort()
    assert chnames == childnames, f"Wrote correct child names: {chnames}"


def TEST_WEAPON_PART():
    # When a connect point is selected and then another part is imported that connects
    # to that point, they are connected in Blender.
    TT.test_title("TEST_WEAPON_PART", "Weapon parts are imported at the parent connect point")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    partfile = TT.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel_1.nif")
    partfile2 = TT.test_file(r"tests\FO4\Shotgun\DrumMag.nif")
    outfile = TT.test_file(r"tests\Out\TEST_WEAPON_PART.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)

    barrelpcp = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Barrel'), 
                            bpy.data.objects))
    assert barrelpcp, f"Found the connect point for barrel parts"
    magpcp = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Mag'), 
                         bpy.data.objects))
    assert magpcp, f"Found the connect point for magazine parts"

    BD.ObjectSelect([barrelpcp], active=True)

    bpy.ops.import_scene.pynifly(filepath=partfile, do_create_bones=False, do_rename_bones=False)

    barrelccp = next((x for x in bpy.data.objects 
                      if x.name.startswith('BSConnectPointChildren')), 
                      None)
    assert barrelccp, f"Barrel's child connect point found {barrelccp}"
    assert barrelccp.parent == barrelpcp, f"Child connect point parented to parent connect point: {barrelccp.parent}"


def TEST_IMPORT_MULT_CP():
    # When multiple weapon parts are imported in one command, they are connected up
    TT.test_title("TEST_IMPORT_MULT_CP", "Can import multiple files and connect up the connect points")
    TT.clear_all()

    testfiles = [{"name": TT.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")}, 
                 {"name": TT.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel.nif")}, 
                 {"name": TT.test_file(r"tests\FO4\Shotgun\Stock.nif")} ]
    bpy.ops.import_scene.pynifly(files=testfiles, do_rename_bones=False, do_create_bones=False)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 5, f"Have 5 meshes: {meshes}"
    barrelparent = [obj for obj in bpy.data.objects if obj.name == 'BSConnectPointParents::P-Barrel']
    assert len(barrelparent) == 1, f"Have barrel parent connect point {barrelparent}"
    barrelchild = [obj for obj in bpy.data.objects \
                if obj.name.startswith('BSConnectPointChildren')
                        and obj['PYN_CONNECT_CHILD_0'] == 'C-Barrel']
    assert len(barrelchild) == 1, f"Have a single barrel child {barrelchild}"
    

def TEST_FURN_MARKER1():
    TT.test_title("TEST_FURN_MARKER1", "Furniture markers work")
    TT.clear_all()

    testfile = TT.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TT.test_file(r"tests\Out\TEST_FURN_MARKER1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 2, f"Found furniture markers: {fmarkers}"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    bench = TT.find_shape("FarmBench01:5")
    bench.select_set(True)
    bsxf = TT.find_shape("BSXFlags", type='EMPTY')
    bsxf.select_set(True)
    for f in bpy.data.objects:
        if f.name.startswith("BSFurnitureMarker"):
            f.select_set(True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 2, f"Wrote the furniture marker correctly: {len(fmcheck)}"


def TEST_FURN_MARKER2():
    TT.test_title("TEST_FURN_MARKER2", "Furniture markers work")

    TT.clear_all()

    testfile = TT.test_file(r"tests\SkyrimSE\commonchair01.nif")
    outfile = TT.test_file(r"tests\Out\TEST_FURN_MARKER2.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 1, f"Found furniture markers: {fmarkers}"
    assert TT.VNearEqual(fmarkers[0].rotation_euler, (-math.pi/2, 0, 0)), f"Marker points the right direction"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    TT.find_shape("CommonChair01:0").select_set(True)
    TT.find_shape("BSXFlags", type='EMPTY').select_set(True)
    TT.find_shape("BSFurnitureMarkerNode", type='EMPTY').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 1, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].entry_points == 13, f"Entry point data is correct: {fmcheck[0].entry_points}"


def TEST_FO4_CHAIR():
    TT.test_title("TEST_FO4_CHAIR", "Furniture markers are imported and exported")
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\FederalistChairOffice01.nif")
    outfile = TT.test_file(r"tests\Out\TEST_FO4_CHAIR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 4, f"Found furniture markers: {fmarkers}"
    mk = bpy.data.objects['BSFurnitureMarkerNode']
    assert TT.VNearEqual(mk.rotation_euler, (-math.pi/2, 0, 0)), \
        f"Marker {mk.name} points the right direction: {mk.rotation_euler, (-math.pi/2, 0, 0)}"

    # -------- Export --------
    chair = TT.find_shape("FederalistChairOffice01:2")
    fmrk = list(filter(lambda x: x.name.startswith('BSFurnitureMarkerNode'), bpy.data.objects))
    
    bpy.ops.object.select_all(action='DESELECT')
    chair.select_set(True)
    for fm in bpy.data.objects: 
        if fm.name.startswith('BSFurnitureMarkerNode'):
            fm.select_set(True)
    bpy.context.view_layer.objects.active = chair
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 4, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].entry_points == 0, f"Entry point data is correct: {fmcheck[0].entry_points}"


def TEST_PIPBOY():
    TT.test_title("TEST_PIPBOY", "Test pipboy import/export--very complex node hierarchy")
    TT.clear_all()

    def cmp_xf(a, b):
        axf = a.xform_to_global.as_matrix()
        bxf = b.xform_to_global.as_matrix()
        assert TT.MatNearEqual(axf, bxf), f"{a.name} transform preserved: \n{axf}\n != \n{bxf}"

    testfile = TT.test_file(r"tests\FO4\PipBoy_Simple.nif")
    outfile = TT.test_file(f"tests/Out/TEST_PIPBOY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    nifcheck = pyn.NifFile(outfile)
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

    niftest = pyn.NifFile(testfile)
    td1test = niftest.nodes["TapeDeck01"]
    tdltest = niftest.nodes["TapeDeckLid"]
    tdlmtest = niftest.nodes["TapeDeckLid_mesh"]
    tdlm1test = niftest.shape_dict["TapeDeckLid_mesh:1"]

    cmp_xf(td1, td1test)
    cmp_xf(tdl, tdltest)
    cmp_xf(tdlm, tdlmtest)
    cmp_xf(tdlm1, tdlm1test)


def TEST_BABY():
    # Non-human skeleton, lots of shapes under one armature.
    TT.test_title('TEST_BABY', 'Can export baby parts')
    TT.clear_all()

    # Can intuit structure if it's not in the file
    testfile = TT.test_file(r"tests\FO4\baby.nif")
    outfile = TT.test_file(r"tests\Out\TEST_BABY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)
    
    head = bpy.data.objects['Baby_Head:0']
    eyes = bpy.data.objects['Baby_Eyes:0']

    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    eyes.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    testnif = pyn.NifFile(outfile)
    testhead = testnif.shape_by_root('Baby_Head')
    testeyes = testnif.shape_by_root('Baby_Eyes')
    assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
    assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"
    assert testhead.blockname == "BSSubIndexTriShape", f"Error: Expected BSSubIndexTriShape on skinned shape, got {testhead.blockname}"


def TEST_ROTSTATIC():
    TT.test_title("TEST_ROTSTATIC", "Test that statics are transformed according to the shape transform")
    TT.clear_all()

    testfile = TT.test_file(r"tests/Skyrim/rotatedbody.nif")
    outfile = TT.test_file(r"tests/Out/TEST_ROTSTATIC.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = bpy.data.objects["LykaiosBody"]
    head = bpy.data.objects["FemaleHead"]
    assert body.rotation_euler[0] != (0.0, 0.0, 0.0), f"Expected rotation, got {body.rotation_euler}"

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nifcheck = pyn.NifFile(outfile)
    assert "LykaiosBody" in nifcheck.shape_dict.keys(), f"Expected LykaiosBody shape, found {[s.name for s in nifcheck.shapes]}"
    bodycheck = nifcheck.shape_dict["LykaiosBody"]

    m = Matrix(bodycheck.transform.rotation)
    assert int(m.to_euler()[0]*180/math.pi) == 90, f"Expected 90deg rotation, got {m.to_euler()}"


def TEST_ROTSTATIC2():
    TT.test_title("TEST_ROTSTATIC2", "Test that statics are transformed according to the shape transform")
    TT.clear_all()

    testfile = TT.test_file(r"tests/FO4/Meshes/SetDressing/Vehicles/Crane03_simplified.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    glass = bpy.data.objects["Glass:0"]
    assert int(glass.location[0]) == -107, f"Locaation is incorret, got {glass.location[:]}"
    assert round(glass.matrix_world[0][1], 4) == -0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[0][1], 4)} != -0.9971"
    assert round(glass.matrix_world[2][2], 4) == 0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[2][2], 4)} != 59.2036"


def TEST_FACEBONES():
    # A few of the facebones have transforms that don't match the rest. The skin-to-bone
    # transforms have to be handled correctly or the face comes in slightly warped.
    # Also the skin_bone_C_MasterEyebrow is included in the nif but not used in the head.
    TT.test_title("TEST_FACEBONES", "Can read and write facebones correctly")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests\FO4\BaseFemaleHead_faceBones.nif")
    outfile = TT.test_file(f"tests/Out/TEST_FACEBONES.nif", output=1)
    resfile = TT.test_file(f"tests/Out/TEST_FACEBONES_facebones.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = TT.find_shape("BaseFemaleHead_faceBones:0")
    maxy = max([v.co.y for v in head.data.vertices])
    assert maxy < 11.8, f"Max y not too large: {maxy}"

    head_arma = next(m.object for m in head.modifiers if m.type == 'ARMATURE')
    assert head_arma['PYN_RENAME_BONES'], f"Armature remembered that bones were renamed {head.parent.name}"
    assert head['PYN_RENAME_BONES'], f"Head remembered that bones were renamed {head.name}"
    
    # Not sure what behavior is best. Node is in the nif, not used in the shape. Since we
    # are extending the armature, we import the bone as part of the armature.
    assert len([obj for obj in bpy.data.objects if "pynRoot" in obj]) == 1, \
        f"Have the root Node"
    assert "skin_bone_C_MasterEyebrow" not in bpy.data.objects, \
        f"No separate empty node for skin_bone_C_MasterEyebrow"
    assert "skin_bone_C_MasterEyebrow" in head_arma.data.bones, \
        f"Bone is loaded for parented bone skin_bone_C_MasterEyebrow"
    assert head_arma.data.bones['skin_bone_C_MasterEyebrow'].matrix_local.translation.z < 150, \
        f"Eyebrow in reasonable location"
    sbme_pose = head_arma.pose.bones["skin_bone_C_MasterEyebrow"]
    assert sbme_pose.matrix.translation.x < 1e+30 and sbme_pose.matrix.translation.x > -1e+30, \
        f"Pose location not stupid: {sbme_pose.matrix.translation}"
    # meb = bpy.data.objects["skin_bone_C_MasterEyebrow"]
    # assert meb.location.z > 120, f"skin_bone_C_MasterEyebrow in correct position"
    
    assert not TT.VNearEqual(head.data.vertices[1523].co, Vector((1.7168, 5.8867, -4.1643))), \
        f"Vertex is at correct place: {head.data.vertices[1523].co}"

    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nifgood = pyn.NifFile(testfile)
    nifch = pyn.NifFile(resfile)
    for nm in nifgood.nodes:
        # Skip root node and bones that aren't actually used
        if nm not in ['BaseFemaleHead_faceBones.nif', 'skin_bone_C_MasterEyebrow']:
            assert nm in nifch.nodes, f"Found node {nm} in output file"
            assert NT.XFNearEqual(nifch.nodes[nm].transform, nifgood.nodes[nm].transform), f"""
Transforms for output and input node {nm} match:
{nifch.nodes[nm].transform}
{nifgood.nodes[nm].transform}
"""
            assert NT.XFNearEqual(nifch.nodes[nm].xform_to_global, nifgood.nodes[nm].xform_to_global), f"""
Transforms for output and input node {nm} match:
{nifch.nodes[nm].xform_to_global}
{nifgood.nodes[nm].xform_to_global}
"""

def TEST_FACEBONES_RENAME():
    TT.test_title("TEST_FACEBONES_RENAME", "Facebones are renamed from Blender to the game's names")
    TT.clear_all()

    testfile = TT.test_file(r"tests/FO4/basemalehead_facebones.nif")
    outfile = TT.test_file(r"tests/Out/TEST_FACEBONES_RENAME.nif")
    outfile2 = TT.test_file(r"tests/Out/TEST_FACEBONES_RENAME_facebones.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    arma = next(m.object for m in obj.modifiers if m.type == 'ARMATURE')
    assert 'skin_bone_Dimple.R' in obj.vertex_groups.keys(), f"Expected munged vertex groups"
    assert 'skin_bone_Dimple.R' in arma.data.bones.keys(), f"Expected munged bone names"
    assert 'skin_bone_R_Dimple' not in obj.vertex_groups.keys(), f"Expected munged vertex groups"
    assert 'skin_bone_R_Dimple' not in arma.data.bones.keys(), f"Expected munged bone names"

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nif2 = pyn.NifFile(outfile2)
    assert 'skin_bone_R_Dimple' in nif2.shapes[0].bone_names, f"Expected game bone names, got {nif2.shapes[0].bone_names[0:10]}"
    

def TEST_IMP_ANIMATRON():
    # The animatrons are very complex and their pose and bind positions are different. The
    # two shapes have slightly different bind positions, though they are a small offset
    # from each other.
    TT.test_title("TEST_IMP_ANIMATRON", "Can read a FO4 animatron nif")
    TT.clear_all()

    testfile = TT.test_file(r"tests/FO4/AnimatronicNormalWoman-body.nif")
    outfile = TT.test_file(r"tests/Out/TEST_IMP_ANIMATRON.nif")
    outfile_fb = TT.test_file(r"tests/Out/TEST_IMP_ANIMATRON.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)

    sh = TT.find_shape('BodyLo:0')
    minv, maxv = TT.get_obj_bbox(sh)
    assert TT.VNearEqual(minv, Vector((-13.14, -7.83, 38.6)), 0.1), f"Bounding box min correct: {minv}"
    assert TT.VNearEqual(maxv, Vector((14.0, 12.66, 133.5)), 0.1), f"Bounding box max correct: {maxv}"

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    spine2 = arma.data.bones['SPINE2']
    hand = arma.data.bones['RArm_Hand']
    handpose = arma.pose.bones['RArm_Hand']
    assert spine2.matrix_local.translation.z > 30, f"SPINE2 in correct position: {spine2.matrix_local.translation}"
    assert TT.VNearEqual(handpose.matrix.translation, [18.1848, 2.6116, 68.6298]), f"Hand position matches Nif: {handpose.matrix.translation}"

    thighl = arma.data.bones['LLeg_Thigh']
    cp_armorleg = TT.find_shape("BSConnectPointParents::P-ArmorLleg", type='EMPTY')
    assert cp_armorleg["pynConnectParent"] == "LLeg_Thigh", f"Connect point has correct parent: {cp_armorleg['pynConnectParent']}"
    # assert TT.VNearEqual(cp_armorleg.location, thighl.matrix_local.translation, 0.1), \
    #     f"Connect point at correct position: {cp_armorleg.location} == {thighl.matrix_local.translation}"

    assert arma, f"Found armature '{arma.name}'"
    lleg_thigh = arma.data.bones['LLeg_Thigh']
    assert lleg_thigh.parent, f"LLeg_Thigh has parent"
    assert lleg_thigh.parent.name == 'Pelvis', f"LLeg_Thigh parent is {lleg_thigh.parent.name}"

    bpy.ops.object.select_all(action='DESELECT')
    sh.select_set(True)
    TT.find_shape('BodyLo:1').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True,
                                 export_pose=True)

    impnif = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile_fb)
    sh_out = nifout.shapes[0]
    assert sh_out.name == 'BodyLo:0', f"Exported shape: {sh_out.name}"
    minv_out, maxv_out = TT.get_shape_bbox(sh_out)
    assert TT.VNearEqual(minv_out, minv), f"Minimum bounds equal: {minv_out} == {minv}"
    assert TT.VNearEqual(maxv_out, maxv), f"Minimum bounds equal: {maxv_out} == {maxv}"
    sp2_out = nifout.nodes['SPINE2']
    assert sp2_out.parent.name == 'SPINE1', f"SPINE2 has parent {sp2_out.parent.name}"
    sp2_in = impnif.nodes['SPINE2']
    assert TT.MatNearEqual(BD.transform_to_matrix(sp2_out.transform), BD.transform_to_matrix(sp2_in.transform)), \
        f"Transforms are equal: \n{sp2_out.transform}\n==\n{sp2_in.transform}"
        

def TEST_CUSTOM_BONES():
    # These nifs have bones that are not part of the vanilla skeleton.
    TT.test_title('TEST_CUSTOM_BONES', 'Can handle custom bones correctly')
    TT.clear_all()

    testfile = TT.test_file(r"tests\FO4\VulpineInariTailPhysics.nif")
    testfile = TT.test_file(r"tests\FO4\BrushTail_Male_Simple.nif")
    outfile = TT.test_file(r"tests\Out\TEST_CUSTOM_BONES.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    nifimp = pyn.NifFile(testfile)
    bone_in_xf = nifimp.nodes['Bone_Cloth_H_003'].xform_to_global.as_matrix()

    obj = bpy.data.objects['BrushTailBase']
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    test_in = pyn.NifFile(outfile)
    new_xf = test_in.nodes['Bone_Cloth_H_003'].xform_to_global.as_matrix()
    assert TT.MatNearEqual(bone_in_xf, new_xf), f"Bone 'Bone_Cloth_H_003' preserved (new/original):\n{new_xf}\n==\n{bone_in_xf}"
        

def TEST_COTH_DATA():
    # Cloth data is extra bones that are enabled by HDT-type physics. Since they aren't 
    # part of the skeleton they can create problems.
    TT.test_title("TEST_COTH_DATA", "Can read and write cloth data")
    TT.clear_all()

    testfile = TT.test_file(r"tests/FO4/HairLong01.nif")
    outfile = TT.test_file(r"tests/Out/TEST_COTH_DATA.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    assert 'BSClothExtraData' in bpy.data.objects.keys(), f"Found no cloth extra data in {bpy.data.objects.keys()}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["HairLong01:0"].select_set(True)
    bpy.data.objects["BSClothExtraData"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected hair nif"
    assert len(nif1.cloth_data) == 1, f"Expected cloth data"
    assert len(nif1.cloth_data[0][1]) == 46257, f"Expected 46257 bytes of cloth data, found {len(nif1.cloth_data[0][1])}"


def TEST_SCALING_COLL():
    # Collisions have to be scaled with everything else if the import/export
    # has a scale factor.

    # Primarily tests collisions, but this nif has everything: collisions, root node as
    # fade node, bone hierarchy, extra data nodes. So tests for those and also  
    # UV orientation and texture handling
    TT.test_title("TEST_SCALING_COLL", "Collisions scale correctly on import and export")
    TT.clear_all()

    # ------- Load --------
    testfile = TT.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TT.test_file(r"tests/Out/TEST_SCALING_COLL.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    obj = TT.find_shape("ElvenBowSkinned:0")

    # Make sure the bone positions didn't get messed up by use_blender_xf.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    mxbind = arma.data.bones['Bow_StringBone1'].matrix_local
    mxpose = arma.pose.bones['Bow_StringBone1'].matrix
    assert BD.MatNearEqual(mxbind, mxpose), f"Bind position same as pose position"

    # # After import with a scale factor, imported object records the scale factor
    # assert 'PYN_SCALE_FACTOR' in obj, f"Scale fector recorded on {obj.name}"
    # assert TT.NearEqual(obj['PYN_SCALE_FACTOR'], 0.1), f"Scale factor is correct on {obj.name}: {obj['PYN_SCALE_FACTOR']}"
    # assert 'PYN_SCALE_FACTOR' in obj.parent, f"Scale fector recorded on {obj.name.parent}"
    # assert TT.NearEqual(obj.parent['PYN_SCALE_FACTOR'], 0.1), f"Scale factor is correct on {obj.parent.name}: {obj.parent['PYN_SCALE_FACTOR']}"

    # Check collision info
    midbone = arma.data.bones['Bow_MidBone']
    midbonew = arma.matrix_world @ midbone.matrix_local
    coll = TT.find_shape("bhkCollisionObject", type="EMPTY")
    assert TT.VNearEqual(coll.matrix_world.translation, midbonew.translation), f"Collision positioned at target bone"

    collbody = coll.children[0]
    assert collbody.name == 'bhkRigidBodyT', f"Child of collision is the collision body object"
    assert TT.VNearEqual(collbody.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), \
        f"Collision body rotation correct: {collbody.rotation_quaternion}"

    # Scale factor applied to bow
    objmin, objmax = TT.get_obj_bbox(obj, worldspace=True)
    assert objmax.y - objmin.y < 12, f"Bow is properly scaled: {objmax - objmin}"

    # Collision box bounds close to bow bounds.
    collbox = TT.find_shape('bhkBoxShape')
    assert TT.close_bounds(obj, collbox), f"Collision just covers bow"
    
    print("--Testing export")

    # Move the edge of the collision box so it covers the bow better
    for v in collbox.data.vertices:
        if v.co.x > 0:
            v.co.x += 6
    # collbody.matrix_local = collbody.matrix_local @ Matrix.Translation(Vector((4, 0, 0)))

    collbox.update_from_editmode()
    boxmin, boxmax = TT.get_obj_bbox(collbox, worldspace=True)
    assert TT.VNearEqual(objmax, boxmax, epsilon=1.0), f"Collision just covers bow: {objmax} ~~ {boxmax}"

    # ------- Export and Check Results --------

    # We want the special properties of the root node. 
    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)

    # Depend on the defaults stored on the armature for scale factor
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True)

    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)

    TT.compare_shapes(nif.shape_dict['ElvenBowSkinned:0'],
                      nifcheck.shape_dict['ElvenBowSkinned:0'],
                      obj)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert nifdefs.bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    TT.compare_bones('Bow_MidBone', nif, nifcheck, e=0.001)
    TT.compare_bones('Bow_StringBone2', nif, nifcheck, e=0.001)

    # Re-import the nif to make sure collisions are right. Could test them in the nif
    # directly but the math is gnarly.
    TT.clear_all()
    
    bpy.ops.import_scene.pynifly(filepath=outfile, use_blender_xf=True)
    obj = TT.find_shape("ElvenBowSkinned:0")
    box = TT.find_shape("bhkBoxShape")
    assert TT.close_bounds(obj, box), f"Collision box covers bow."


def TEST_IMP_NORMALS():
    TT.test_title("TEST_IMP_NORMALS", "Can import normals from nif shape")
    TT.clear_all()

    testfile = TT.test_file(r"tests/Skyrim/cube.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # all loop custom normals point off at diagonals
    obj = bpy.context.object
    obj.data.calc_normals_split()
    for l in obj.data.loops:
        for i in [0, 1, 2]:
            assert round(abs(l.normal[i]), 3) == 0.577, f"Expected diagonal normal, got loop {l.index}/{i} = {l.normal[i]}"


def TEST_UV_SPLIT():
    TT.test_title("TEST_UV_SPLIT", "Can split UVs properly")
    TT.clear_all()
    filepath = TT.test_file("tests/Out/TEST_UV_SPLIT.nif")

    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.export_scene.pynifly(filepath=filepath, target_game="SKYRIM")
    
    nif_in = pyn.NifFile(filepath)
    obj = nif_in.shapes[0]
    assert len(obj.verts) == 14, f"Verts were split: {len(obj.verts)}"
    assert len(obj.uvs) == 14, f"Same number of UV points: {len(obj.uvs)}"
    assert TT.VNearEqual(obj.verts[2], obj.verts[10]), f"Split verts at same location {obj.verts[2]}, {obj.verts[10]}"
    assert not TT.VNearEqual(obj.uvs[2], obj.uvs[10]), f"Split UV at different location {obj.uvs[2]}, {obj.uvs[10]}"


def TEST_JIARAN():
    TT.test_title("TEST_JIARAN", "Armature with no stashed transforms exports correctly")
    TT.clear_all()
    outfile =TT.test_file(r"tests/Out/TEST_JIARAN.nif")
     
    TT.export_from_blend(r"tests\SKYRIMSE\jiaran.blend", "hair.001", 'SKYRIMSE', outfile)

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected Jiaran nif"


def TEST_SKEL_HKX_IMPORT():
    TT.test_title("TEST_SKEL_HKX_IMPORT", "Skeleton import")
    TT.clear_all()
    testfile = TT.test_file("tests/Skyrim/skeleton.hkx")
    # outfile = TT.test_file("tests/out/TEST_SKEL_HKX.xml")

    bpy.ops.import_scene.skeleton_xml(filepath=testfile)
    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)


def TEST_SKEL_HKX():
    TT.test_title("TEST_SKEL_HKX", "Skeleton export")
    TT.clear_all()
    testfile = TT.test_file("tests/Skyrim/skeletonbeast_vanilla.nif")
    outfile = TT.test_file("tests/out/TEST_SKEL_HKX.xml")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    arma = bpy.data.objects[BD.arma_name('skeletonBeast.nif')]
    BD.ObjectSelect([arma], active=True)

    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        b.bone.select = b.name.startswith('TailBone')

    bpy.ops.export_scene.skeleton_xml(filepath=outfile)

    xcheck = xml.parse(outfile)
    xroot = xcheck.getroot()

    # Check we have various key elements
    assert xroot.tag == 'hkpackfile', f"Type is hkpackfile: {xroot.tag}"
    xsec = xroot[0]
    assert xsec.tag == 'hksection', f"Type is hksection: {xsec.tag}"
    assert xsec.attrib['name'] == "__data__", f"Have correct name on section: {xsec.attrib['name']}"
    assert len(xsec[:]) > 0, f"Have children: {xsec[:]}"
    xskel = [x for x in xsec if x.attrib['class'] == 'hkaSkeleton']
    assert len(xskel) > 0, f"Have skeletons: {xskel}"
    assert xskel[0].tag == 'hkobject', f"Type is hkobject: {xskel[0].tag}"
    nameparam = xskel[0].find("./hkparam[@name='name']")
    assert nameparam.text == 'TailBone01', f"Name parameter correct: {nameparam.text}"
    xbones = xskel[0].find("./hkparam[@name='bones']")
    assert xbones is not None, f"Have bones: {xbones}"
    xpose = xskel[0].find("./hkparam[@name='referencePose']")
    assert xpose is not None, f"Have pose: {xpose}"

    # RootLevelContainer has forward references to animation and memory resource
    # containers. Make sure they are correct.
    rlc = xroot.find("./hksection/hkobject[@class='hkRootLevelContainer']/hkparam[@name='namedVariants']")
    ch1 = rlc[0]
    class1 = ch1.find("./hkparam[@name='className']").text
    var1 = ch1.find("./hkparam[@name='variant']").text
    assert class1 in ['hkaAnimationContainer', 'hkMemoryResourceContainer'], f"Found correct forward ref: {class1}"
    ref1 = xsec.find(f"./hkobject[@name='{var1}']")
    assert ref1 != None, f"Found forward ref {var1}"
    assert ref1.attrib['class'] == class1, f"Forward ref correct: {ref1.attrib['class']} == {class1}"
    ch2 = rlc[1]
    class2 = ch2.find("./hkparam[@name='className']").text
    var2 = ch2.find("./hkparam[@name='variant']").text
    assert class2 in ['hkaAnimationContainer', 'hkMemoryResourceContainer'], f"Found correct forward ref: {class2}"
    ref2 = xsec.find(f"./hkobject[@name='{var2}']")
    assert ref2 != None, f"Found forward ref {var2}"
    assert ref2.attrib['class'] == class2, f"Forward ref correct: {ref2.attrib['class']} == {class2}"

    # Similar for hkaAnimationContainer
    skelref = xroot.find("./hksection/hkobject[@class='hkaAnimationContainer']/hkparam[@name='skeletons']")
    assert xskel[0].attrib['name'] == skelref.text, f"Forward ref correct: {xskel[0].attrib['name']} == {skelref.text}"


def TEST_SKEL_SOS_HKX():
    return # TODO: Finish this functionality
    TT.test_title("TEST_SKEL_SOS_HKX", "Skeleton export")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\skeletonbeast_xpse.nif")
    outfile = TT.test_file("tests/out/TEST_SKEL_SOS_HKX.xml")

    target_bones = ['NPC GenitalsBase [GenBase]',
                    'NPC GenitalsScrotum [GenScrot]',
                    'NPC Genitals01 [Gen01]',
                    'NPC Genitals02 [Gen02]',
                    'NPC Genitals03 [Gen03]',
                    'NPC Genitals04 [Gen04]',
                    'NPC Genitals05 [Gen05]',
                    'NPC Genitals06 [Gen06]']

    bpy.ops.import_scene.pynifly(filepath=testfile, do_rename_bones=False)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma and arma.type=='ARMATURE', f"Loaded armature: {arma}"
    bpy.ops.object.select_all(action='DESELECT')
    BD.ObjectSelect([arma], active=True)

    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        b.bone.select = b.name in target_bones

    bs = [b for b in arma.pose.bones if b.bone.select]
    assert len(bs) == 8, f"Selected bones: {bs}"
    bpy.ops.export_scene.skeleton_hkx(filepath=outfile)

    xout = xml.parse(outfile)
    rootout = xout.getroot()
    skel_elem = rootout.find("./*hkobject[@class='hkaSkeleton']")
    assert skel_elem, "Have skeleton element"
    pi_elem = skel_elem.find("./hkparam[@name='parentIndices']")
    assert pi_elem.text.split() == ['-1', '0', '0', '2', '3', '4', '5', '6'], \
        f"parentIndices correct: {pi_elem.text}"
    
    bones_elem = skel_elem.find("./hkparam[@name='bones']")
    name_elems = bones_elem.findall("./hkobject/hkparam[@name='name']")
    names = [e.text for e in name_elems]
    assert names == target_bones, f"Have correct bones: {names}"


def TEST_FONV():
    TT.test_title("TEST_FONV", "Basic FONV mesh import and export")
    TT.clear_all()
    testfile = TT.test_file("tests/FONV/9mmscp.nif")
    outfile =TT.test_file(r"tests/Out/TEST_FONV.nif")
     
    bpy.ops.import_scene.pynifly(filepath=testfile)
    grip = bpy.data.objects['Ninemm:0']
    coll = bpy.data.objects['bhkConvexVerticesShape']
    colbb = TT.get_obj_bbox(coll)
    assert grip is not None, f"Have grip"
    assert TT.VNearEqual(colbb[0], (-4.55526, -6.1704, -1.2513), epsilon=0.1), f"Collision bounding box near correct min: {colbb}"
    assert TT.VNearEqual(colbb[1], (15.6956, 10.2399, 1.07098), epsilon=2.0), f"Collision bounding box near correct max: {colbb}"
    # TODO: Check collision object. It's coming in 10x the size

    bpy.ops.object.select_all(action="SELECT")
    BD.ObjectActive(grip)

    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifin = pyn.NifFile(testfile)
    gripin = nifin.shape_dict["Ninemm:0"]
    nifout = pyn.NifFile(outfile)
    assert nifout.game == 'FO3', f"Have correct game: {nifout.game}"
    gripout = nifout.shape_dict["Ninemm:0"]
    TT.compare_shapes(gripin, gripout, grip)

    collin = nifin.rootNode.collision_object
    colbodyin = collin.body
    colshapein = colbodyin.shape
    collout = nifout.rootNode.collision_object
    colbodyout = collout.body
    colshapeout = colbodyout.shape
    assert colshapeout.properties.bhkMaterial == colshapein.properties.bhkMaterial, \
        f"Collision material matches: {colshapeout.properties.bhkMaterial} == {colshapein.properties.bhkMaterial}"
    
    minxin = min(v[0] for v in colshapein.vertices)
    minxout = min(v[0] for v in colshapeout.vertices)
    assert TT.NearEqual(minxin, minxout), f"Min collision shape bounds equal X: {minxin} == {minxout}"
    maxzin = max(v[2] for v in colshapein.vertices)
    maxzout = max(v[2] for v in colshapeout.vertices)
    assert TT.NearEqual(maxzin, maxzout), f"Max collision shape bounds equal Z: {maxzin} == {maxzout}"


def TEST_FONV_BOD():
    TT.test_title("TEST_FONV_BOD", "Basic FONV body part import and export")
    TT.clear_all()
    testfile = TT.test_file(r"tests\FONV\outfitf_simple.nif")
    outfile =TT.test_file(r"tests/Out/TEST_FONV_BOD.nif")
     
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = bpy.data.objects['Arms01']
    bodybb = TT.get_obj_bbox(body)
    assert TT.NearEqual(bodybb[0][0], -44.4, epsilon=0.1), f"Min X correct: {bodybb[0][0]}"
    assert TT.NearEqual(bodybb[1][2], 110.4, epsilon=0.1), f"Max Z correct: {bodybb[1][2]}"

    BD.ObjectSelect([body], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    testnif = pyn.NifFile(testfile)
    outnif = pyn.NifFile(outfile)
    TT.compare_shapes(testnif.shape_dict["Arms01"], 
                   outnif.shape_dict["Arms01"],
                   body)


def TEST_ANIM_CHEST():
    TT.test_title("TEST_ANIM_CHEST", "Read and write the animation of chest opening and shutting.")
    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\noblechest01.nif")
    outfile =TT.test_file(r"tests/Out/TEST_ANIM_CHEST.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    lid = bpy.data.objects["Lid01"]
    assert lid.animation_data is not None
    assert lid.animation_data.action.name.startswith("Lid01_Open"), f"Animation has correct name: {lid.animation_data.action.name}"
    assert len([x for x in bpy.data.actions if x.name.startswith("Lid01_Close")]) > 0, f"Have close animation in actions: {bpy.data.actions.keys()}"


def TEST_ANIM_CRATE():
    TT.test_title("TEST_ANIM_CRATE", "Read and write the animation of chest opening and shutting.")
    TT.clear_all()
    testfile = TT.test_file(r"tests\Skyrim\dwechest01.nif")
    outfile =TT.test_file(r"tests/Out/TEST_ANIM_CRATE.nif")
    bpy.context.scene.frame_end = 37
    bpy.context.scene.render.fps = 60 

    bpy.ops.import_scene.pynifly(filepath=testfile)
    lid = bpy.data.objects["Box01"]
    assert lid.animation_data is not None
    assert lid.animation_data.action.name.startswith("Box01_Open"), f"Animation has correct name: {lid.animation_data.action.name}"
    assert len([x for x in bpy.data.actions if x.name.startswith("Box01_Close")]) > 0, f"Have close animation in actions: {bpy.data.actions.keys()}"
    assert len(lid.animation_data.action.fcurves) > 0, f"Have curves: {len(lid.animation_data.action.fcurves)}"
    assert lid.animation_data.action.fcurves[0].data_path == "location", f"Have correct data path"

    gear07 = bpy.data.objects["Gear07"]
    assert gear07.animation_data.action.name.startswith("Gear07_Open"), f"Gear animation exists"
    assert len(gear07.animation_data.action.fcurves) > 0, f"Have curves"
    gear07z = gear07.animation_data.action.fcurves[2]
    assert gear07z.data_path == "rotation_euler", f"Have correct data path: {gear07z.data_path}"
    assert BD.NearEqual(gear07z.keyframe_points[1].co[0], 37.0), f"Have correct time: {gear07z.keyframe_points[1].co}"
    assert BD.NearEqual(gear07z.keyframe_points[1].co[1], 3.14159), f"Have correct value: {gear07z.keyframe_points[1].co}"

    gear07obj = gear07.children[0]
    assert len(gear07obj.data.vertices) == 476, f"Have right number of vertices"

def TEST_ANIM_ALDUIN():
    # ###### WIP. Only test if explicitly selected. #####
    TT.test_title("TEST_ANIM_ALDUIN", "Read and write animation using bones.")
    TT.clear_all()
    testfile = TT.test_file(r"tests\SkyrimSE\loadscreenalduinwall.nif")
    outfile = TT.test_file(r"tests/Out/TEST_ANIM_ALDUIN.nif")

    def check_xf(node: pyn.NiNode):
        """Check that the transform on the first animation keyframe is the same as the
        transform on the parent interpolator. This animation starts at the base pose
        position so all frame 0 transforms should be null."""
        c:pyn.NiTimeController = node.controller
        ti:pyn.NiTransformInterpolator = c.interpolator
        td:pyn.NiTransformData = ti.data

        if td.properties.rotationType == pyn.NiKeyType.XYZ_ROTATION_KEY:
            f0 = [td.xrotations[0].value, td.yrotations[0].value, td.zrotations[0].value]
            e = Euler(f0, 'XYZ')
            q = e.to_quaternion()
        elif td.properties.rotationType == pyn.NiKeyType.LINEAR_KEY:
            q = Quaternion(td.qrotations[0].value)
            e = q.to_euler()

        print(e)
        print(q)
        print(q.to_axis_angle())
        # m = BD.transform_to_matrix(combone.properties.transform)
        tiq = Quaternion(ti.properties.rotation)
        assert TT.MatNearEqual(tiq.to_matrix(), e.to_matrix()), f"{node.name} First keyframe has same rotation as parent TD: {tiq.to_euler()} == {e}"
        nullq = tiq.inverted() @ e.to_quaternion()
        assert TT.MatNearEqual(nullq.to_matrix(), Matrix.Identity(4)), f"{node.name} can invert rotation: {nullq}"
        ve = Vector([round(v, 6) % math.pi for v in e[0:3]])
        vtiq = Vector([round(v, 6) % math.pi for v in tiq.to_euler()[0:3]])
        nulle = Euler(ve - vtiq, 'XYZ')
        # if not TT.MatNearEqual(nulle.to_matrix(), Matrix.Identity(3)):
        #     assert TT.MatNearEqual(nulle.to_matrix(), Matrix.Identity(3)), f"{node.name} can invert euler rotation: {nulle}"

        tiv = Vector(ti.properties.translation)
        v = Vector(td.translations[0].value)
        assert TT.VNearEqual(tiv, v), f"{node.name} translations are the same: {tiv} == {v}"
        assert TT.VNearEqual(v - tiv, [0,0,0]), f"{node.name} can subtract vector"

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 do_create_bones=False, 
                                 do_rename_bones=False,
                                 do_import_animations=True,
                                 use_blender_xf=True)
    
    nif = pyn.NifFile(testfile)
    check_xf(nif.nodes["NPC COM"])
    check_xf(nif.nodes["NPC Pelvis"])
    check_xf(nif.nodes["NPC LLegThigh"])
    check_xf(nif.nodes["NPC LLegCalf"])
    check_xf(nif.nodes["NPC LFinger12"])
    check_xf(nif.nodes["NPC LLBrow"])
    assert 'pynRoot' in bpy.data.objects["MagicEffectsNode"].parent, f"Magic effect node not orphaned"

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    lcalf = arma.data.bones['NPC LLegCalf']
    lcalfp = arma.pose.bones['NPC LLegCalf']

    def dump_anim():
        """Dump keyframe 0 animation data if any. If no animation data, dump pose
        locations."""
        if arma.animation_data:
            act = arma.animation_data.action
            for f in act.fcurves:
                print(f"{f.data_path}: {f.keyframe_points[0].co[1]:0.4f}")

            comrot = [f for f in act.fcurves if f.data_path == 'pose.bones["NPC COM"].rotation_euler']
            xyzrot = [comrot[0].keyframe_points[0].co[1], 
                    comrot[1].keyframe_points[0].co[1], 
                    comrot[2].keyframe_points[0].co[1]]
            e = Euler(xyzrot, 'XYZ')
            q = e.to_quaternion()
            print(xyzrot)
            print(e)
            print(q)
        else:
            for b in arma.pose.bones:
                print(f"{b.name}: {b.matrix.translation}\n\t{b.matrix.to_quaternion()}")
            # thighfc = [f for f in act.fcurves if "LLegThigh" in f.data_path] 
            # print(thighfc[0].data_path)
            # for i in range(0, 7): print(f"LLegThigh {i}: {thighfc[i].keyframe_points[0].co[1]:0.4f}")
            # calffc = [f for f in act.fcurves if "LLegCalf" in f.data_path]
            # print(f"{calffc[0].data_path}")
            # for i in range(0, 7): print(f"LLegCalf {i}: {calffc[i].keyframe_points[0].co[1]:0.4f}")

    # Dump the entire Pelvis location curves from Blender and from the nif.
    if arma.animation_data and arma.animation_data.action:
        pelvc = [c for c in arma.animation_data.action.fcurves if "NPC Pelvis" in c.data_path]
        locc = [c for c in pelvc if "location" in c.data_path]
        print("---Blender X Curve---")
        lastv = Vector()
        for i, xyz in enumerate(zip(locc[0].keyframe_points, 
                                  locc[1].keyframe_points, 
                                  locc[2].keyframe_points)):
            v = Vector((xyz[0].co[1], xyz[1].co[1], xyz[2].co[1]))
            difv = v - lastv
            print(f"\t{i}\t{v}  \t{difv}")
            lastv = v

    print("---Nif Translation Data---")
    pelv = nif.nodes["NPC Pelvis"]
    td = pelv.controller.interpolator.data
    lastv = Vector()
    for i, k in enumerate(td.translations):
        v = Vector(k.value)
        difv = v - lastv
        print(f"\t{i}\t{v}\t{difv}")
        lastv = v
        

def TEST_ANIM_KF():
    # Can import a KF animation
    TT.test_title("TEST_ANIM_KF", "Read and write KF animation.")
    TT.clear_all()

    testfile = TT.test_file(r"tests\SkyrimSE\1hm_staggerbacksmallest.kf")
    testfile2 = TT.test_file(r"tests\SkyrimSE\1hm_attackpowerright.kf")
    skelfile = TT.test_file(r"tests\SkyrimSE\skeleton_vanilla.nif")
    outfile2 = TT.test_file(r"tests/Out/TEST_ANIM_KF.kf")

    bpy.context.scene.render.fps = 60

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=False,
                                 do_import_animations=False,
                                 use_blender_xf=False)
    
    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile)

    assert bpy.data.actions[0].name.startswith("1hm_staggerbacksmallest")

    # Loading a second animation shouldn't screw things up.
    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile2)

    assert len([a for a in bpy.data.actions if a.name.startswith("1hm_attackpowerright")])

    ### Export ###

    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.export_scene.pynifly_kf(filepath=outfile2)

    kforig = pyn.NifFile(testfile2)
    csorig = kforig.rootNode
    cb2orig = [cb for cb in csorig.controlled_blocks if cb.node_name == 'NPC L Thigh [LThg]'][0]
    ti_thigh_in = cb2orig.interpolator
    td_thigh_in = ti_thigh_in.data
    ti2qorig = Quaternion(ti_thigh_in.properties.rotation)
    print(f"Original Interpolator rotation: {ti2qorig}")
    k20orig = Quaternion(td_thigh_in.qrotations[0].value[:])
    print(f"Original Key rotation: {k20orig}")
    curve20orig = Quaternion(ti2qorig.inverted() @ k20orig)
    print(f"Calculated curve quaternion: {curve20orig}")

    # The animation we wrote is correctNiControllerSequence
    kfout = pyn.NifFile(outfile2)
    csout = kfout.rootNode
    assert csout.name == 'TEST_ANIM_KF', f"Have good root node name: {kfout.rootNode.name}"
    assert csout.blockname == 'NiControllerSequence', f"Have good root node name: {kfout.rootNode.name}"
    assert csout.properties.cycleType == nifdefs.CycleType.CYCLE_CLAMP, f"Have correct cycle type"
    assert BD.NearEqual(csout.properties.stopTime, 1.166667), f"Have correct stop time"
    cb0 = csout.controlled_blocks[0]
    ti0 = cb0.interpolator
    td0 = ti0.data
    assert td0.properties.translations.interpolation == pyn.NiKeyType.LINEAR_KEY, f"Have correct key type: {td0.translations.interpolation}"
    assert td0.translations[0].time == 0, f"First time is 0: {td0.translations[0].time}"
    assert BD.VNearEqual(td0.translations[0].value, (0.0, 0.0001, 57.8815)), f"Have correct translation: {td0.translations[0].value}"

    controlled_block_thigh_out = [cb for cb in csout.controlled_blocks if cb.node_name == 'NPC L Thigh [LThg]'][0]
    ti_thigh_out = controlled_block_thigh_out.interpolator
    td_thigh_out = ti_thigh_out.data

    # The interpolator's transform must be correct (to match the bone).
    assert BD.VNearEqual(ti_thigh_out.properties.translation, ti_thigh_in.properties.translation), \
        f"Thigh Interpolator translation correct: {ti_thigh_out.properties.translation[:]} == {ti_thigh_in.properties.translation[:]}"
    mxout = Quaternion(ti_thigh_out.properties.rotation).to_matrix()
    mxorig = Quaternion(ti_thigh_in.properties.rotation).to_matrix()
    assert BD.MatNearEqual(mxout, mxorig), \
        f"Thigh Interpolator rotation correct: {mxout} == {mxorig}"
    
    # We've calculated the rotations properly--the rotation we wrote matches the original.
    k2mx = Quaternion(td_thigh_out.qrotations[0].value).to_matrix()
    k2mxorig = Quaternion(td_thigh_in.qrotations[0].value).to_matrix()
    assert BD.MatNearEqual(k2mx, k2mxorig), f"Have same rotation keys: {k2mx} == {k2mxorig}"

    # Time signatures are calculated correctly.
    # We output at 30 fps so the number isn't exact.
    klast_out = td_thigh_out.qrotations[-1]
    klast_in = td_thigh_in.qrotations[-1]
    assert BD.NearEqual(klast_out.time, klast_in.time), \
        f"Have correct final time signature: {klast_out.time} == {klast_in.time}"

    # Check feet transforms
    cb_foot_in = [cb for cb in csorig.controlled_blocks if cb.node_name == 'NPC L Foot [Lft ]'][0]
    ti_foot_in = cb_foot_in.interpolator
    td_foot_in = ti_foot_in.data
    cb_foot_out = [cb for cb in csout.controlled_blocks if cb.node_name == 'NPC L Foot [Lft ]'][0]
    ti_foot_out = cb_foot_out.interpolator
    td_foot_out = ti_foot_out.data
    assert BD.VNearEqual(ti_foot_out.properties.translation, ti_foot_in.properties.translation), \
        f"Foot Interpolator translation correct: {ti_foot_out.properties.translation[:]} == {ti_foot_in.properties.translation[:]}"
    mxout = Quaternion(ti_foot_out.properties.rotation).to_matrix()
    mxin = Quaternion(ti_foot_in.properties.rotation).to_matrix()
    assert BD.MatNearEqual(mxout, mxin), \
        f"Foot Interpolator rotation correct: {mxout} == {mxin}"

    assert len(td_foot_out.qrotations) > 30 and len(td_foot_out.qrotations) < 40, \
        f"Have reasonable number of frames: {td_foot_out.qrotations}"


def TEST_ANIM_KF_RENAME():
    # Animation import/export works even if bones are renamed.
    TT.test_title("TEST_ANIM_KF_RENAME", "Read and write KF animation with renamed bones.")
    TT.clear_all()

    testfile = TT.test_file(r"tests\Skyrim\sneakmtidle_original.kf")
    skelfile = TT.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    outfile = TT.test_file(r"tests\Out\TEST_ANIM_KF_RENAME.kf")

    bpy.context.scene.render.fps = 30
    # bpy.context.scene.frame_end = 665

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_animations=False,
                                 use_blender_xf=True)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile)

    assert len([fc for fc in arma.animation_data.action.fcurves if 'NPC Pelvis' in fc.data_path]) > 0, f"Animating translated bone names"

    ### Export ###

    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.export_scene.pynifly_kf(filepath=outfile)

    ### Check ###

    nifin = pyn.NifFile(testfile)
    cbin = next(x for x in nifin.rootNode.controlled_blocks if x.node_name == 'NPC L Foot [Lft ]')
    tdin = cbin.interpolator.data

    nifcheck = pyn.NifFile(outfile)
    names = [cb.node_name for cb in nifcheck.rootNode.controlled_blocks]
    assert 'NPC Pelvis [Pelv]' in names, f"Have nif name"
    assert 'NPC Pelvis' not in names, f"Don't have Blender name"

    footcb = next(x for x in nifcheck.rootNode.controlled_blocks if x.node_name == 'NPC L Foot [Lft ]')
    foottd = footcb.interpolator.data
    assert len(foottd.qrotations) == 333, f"Have correct number of rotation frames: {len(foottd.qrotations)}"
    assert 250 <= len(foottd.translations) <= 333, f"Have correct number of translation frames: {len(foottd.translations)}"
    timeinterval = foottd.qrotations[10].time - foottd.qrotations[9].time
    assert BD.NearEqual(timeinterval, 1/30), f"Have correct rotation time interval: {timeinterval}"
    timeinterval = foottd.translations[10].time - foottd.translations[9].time
    assert BD.NearEqual(timeinterval, 1/30), f"Have correct location time interval: {timeinterval}"

    assert BD.NearEqual(foottd.qrotations[10].time, tdin.qrotations[10].time), f"Have near time signatures"
    # assert BD.VNearEqual(foottd.qrotations[10].value, tdin.qrotations[10].value), f"Have near quaternion values"
    # assert BD.NearEqual(foottd.translations[10].time, tdin.translations[10].time), f"Have near time signatures"
    assert BD.VNearEqual(foottd.translations[10].value, tdin.translations[1].value), f"Have near quaternion values"

    comcb_in = next(x for x in nifin.rootNode.controlled_blocks if x.node_name == 'NPC COM [COM ]')
    comtd_in = comcb_in.interpolator.data
    commax_in = max(x.value[1] for x in comtd_in.translations)
    commin_in = min(x.value[1] for x in comtd_in.translations)
    comcb = next(x for x in nifcheck.rootNode.controlled_blocks if x.node_name == 'NPC COM [COM ]')
    comtd = comcb.interpolator.data
    commax = max(x.value[1] for x in comtd.translations)
    commin = min(x.value[1] for x in comtd.translations)
    assert BD.NearEqual(commax, commax_in), f"Max com movement {commax} == {commax_in}"
    assert BD.NearEqual(commin, commin_in), f"Max com movement {commin} == {commin_in}"


def TEST_ANIM_HKX():
    # Can import a HKX animation
    TT.test_title("TEST_ANIM_HKX", "Read and write HKX animation.")
    TT.clear_all()

    # Check that this works when there are spaces in the path name
    testfile = TT.test_file(r"tests\Skyrim\meshes\actors\character\character animations\1hm_staggerbacksmallest.hkx")
    # testfile2 = TT.test_file(r"tests\Skyrim\1hm_attackpowerright.hkx")
    skelfile = TT.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkx_skel = TT.test_file(r"tests\Skyrim\skeleton.hkx")
    outfile = TT.test_file(r"tests/Out/created animations/TEST_ANIM_HKX.hkx")

    bpy.context.scene.render.fps = 60

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_animations=False,
                                 use_blender_xf=True)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile, 
                                     reference_skel=hkx_skel)

    assert len([fc for fc in arma.animation_data.action.fcurves if 'NPC Pelvis' in fc.data_path]) > 0, f"Animating translated bone names"

    bpy.ops.export_scene.pynifly_hkx(filepath=outfile, reference_skel=hkx_skel)

    assert os.path.exists(outfile)

def LOAD_RIG():
    """Load an animation rig for play."""
    TT.test_title("LOAD_RIG", "Load some body parts.")
    TT.clear_all()
    skelfile = TT.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkxskelfile = TT.test_file(r"tests\Skyrim\skeleton.hkx")
    bpfile1 = TT.test_file(r"tests\Skyrim\malebody_1.nif")
    bpfile2 = TT.test_file(r"tests\Skyrim\malehands_1.nif")
    bpfile3 = TT.test_file(r"tests\Skyrim\malefeet_1.nif")
    bpfile4 = TT.test_file(r"tests\Skyrim\malehead.nif")

    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_animations=False,
                                 use_blender_xf=True)
    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.context.object['PYN_SKELETON_FILE'] = hkxskelfile
    bpy.ops.import_scene.pynifly(files=[{"name": bpfile1}, 
                                        {"name": bpfile2}, 
                                        {"name": bpfile3}, 
                                        {"name": bpfile4}],
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_animations=False,
                                 use_blender_xf=True)


# LOAD_RIG()  ### Not a test--Load up some shapes for play

# --- Quick and Dirty Test Harness ---

# If clear, all tests run in the order they are defined.
# If set, this and all following tests will be run.
# Use to resume a test run from the point it failed.
first_test = 'TEST_FONV'  

# If set, run this test only.
sole_test = ''

m = sys.modules[__name__]

if sole_test: 
    m.__dict__[sole_test]()
else:
    all_tests = [k for k in m.__dict__.keys() if k.startswith('TEST_')]
    doit = True
    if first_test: doit = False
    for name in all_tests:
        if name == first_test: doit = True
        if doit and name.startswith('TEST_'): 
            m.__dict__[name]()
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

print("""
############################################################
##                                                        ##
##                    TESTS DONE                          ##
##                                                        ##
############################################################
""")
