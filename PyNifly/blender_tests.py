"""Automated tests for pyNifly export/import addon

Convenient setup for running these tests here: 
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""
import os
import sys
import shutil 
import math
from pathlib import Path
import bpy
import bpy_types
from mathutils import Matrix, Vector, Quaternion, Euler
import test_tools as TT
import test_tools_bpy as TTB
import niflytools as NT
import nifdefs
import pynifly as pyn
import xml.etree.ElementTree as xml
import blender_defs as BD
from trihandler import *
from test_nifchecker import CheckNif

import importlib
import skeleton_hkx
import shader_io
import controller
importlib.reload(pyn)
importlib.reload(TT)
importlib.reload(BD)
importlib.reload(shader_io)
importlib.reload(controller)
importlib.reload(skeleton_hkx)

log = logging.getLogger("pynifly")
log.setLevel(logging.DEBUG)


class TestLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("pynifly")
        self.log.addHandler(self)
        self.expect_error = logging.WARNING
        self.max_error = 0

    def __del__(self):
        if self.log:
            self.log.removeHandler(self)

    def emit(self, record):
        self.max_error = max(self.max_error, record.levelno)

    def start(self):
        """
        Start logging for an operation. Return the log and its handler.
        """
        self.max_error = 0
        self.expect_error = logging.WARNING
        
    def check(self):
        assert self.max_error <= self.expect_error, \
            f"No errors reported during test {self.max_error} > {self.expect_error}"        

    def finish(self):
        self.check()        

    @classmethod
    def New(cls):
        lh = TestLogHandler()
        lh.start()
        return lh


test_loghandler:TestLogHandler = TestLogHandler.New()


def TEST_BODYPART_SKY():
    """Basic test that a Skyrim bodypart is imported correctly. """
    # Verts are organized around the origin, but skin transform is put on the shape 
    # and that lifts them to the head position.  
    testfile = TTB.test_file("tests\Skyrim\malehead.nif")
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
    assert NT.NearEqual(maxz, 11.5, epsilon=0.1), f"Max Z ~ 11.5: {maxz}"
    minz = min([v.co.z for v in male_head.data.vertices])
    assert NT.NearEqual(minz, -11, epsilon=0.1), f"Min Z ~ -11: {minz}"

    
def TEST_BODYPART_FO4():
    """Basic test that a FO4 bodypart imports correctly. """
    # Verts are organized around the origin but the skin-to-bone transforms are 
    # all consistent, so they are put on the shape.
    testfile = TTB.test_file("tests\FO4\BaseMaleHead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    male_head = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH'][0]
    assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
    assert 'pynRoot' in male_head.parent, "Parenting mesh to root"
    maxz = max([v.co.z for v in male_head.data.vertices])
    TT.assert_equiv(maxz, 8.3, "Max Z", e=0.1)
    minz = min([v.co.z for v in male_head.data.vertices])
    TT.assert_equiv(minz, -12.1, "Min Z", e=0.1)


def TEST_BODYPART_XFORM():
    """Test the body can be brought in with extended skeleton and Blender transform."""
    # On import, a transform can be applied to make it convenient for handling in Blender.
    # And the bones in the nif can be extended with the reference skeleton. Using the
    # child body because it creates problems that the adult body does not.
    testfile = TTB.test_file(r"tests\Skyrim\childbody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 do_create_bones=True,
                                 use_blender_xf=True,
                                 do_rename_bones=True)

    # Importer leaves any imported shapes as the selected object.
    body = bpy.context.object
    assert body.name == 'BODY', f"Have correct name: {body.name}"
    
    # Importer creates an armature for the skinned shape.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma, f"Found armature"

    # Root node imported and parents other objects. 
    root_object = next(n for n in bpy.data.objects if 'pynRoot' in n)
    assert body.parent == root_object, f"Body parented to root."
    assert root_object.scale == Vector((0.1,0.1,0.1,)), f"Root applies a 1/10 scale."

    # The new bones from the reference skeleton have the same transform and scale as the
    # ones that came from the nif.
    bonez_max = max(b.head.z for b in arma.data.bones)
    vertz_max = max((body.matrix_local @ v.co).z for v in body.data.vertices)
    assert bonez_max < vertz_max, f"Armature entirely within body."

    spine1 = arma.data.bones['NPC Spine1']
    assert "CME Spine" == spine1.parent.name, f"Spine1 has correct parent."

    
def TEST_SKYRIM_XFORM():
    """Can read & write the Skyrim shape transforms"""
    testfile = TTB.test_file(r"tests/Skyrim/malehead.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SKYRIM_XFORM.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert int(obj.location[2]) == 120, f"Shape offset not applied to head, found {obj.location[2]}"

    # Export the currently selected object, which import should have set to the head.
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nifcheck = pyn.NifFile(outfile)
    CheckNif(nifcheck, source=testfile)


def TEST_FO4_XFORM():
    """Can read & write FO4 shape transforms"""
    testfile = TTB.test_file(r"tests/FO4/BaseMaleHead.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_FO4_XFORM1.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_FO4_XFORM2.nif")

    # Reading the nif and calculating the offset from bone offsets
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 do_create_bones=True,
                                 do_import_tris=False,
                                 do_import_pose=False)

    obj = bpy.context.object

    BD.ObjectSelect([obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile1,
                                 export_pose=False)

    # # Change obj transform and export again. 
    # BD.ObjectSelect([obj], active=True)
    # bpy.ops.object.transform_apply()
    # bpy.ops.export_scene.pynifly(filepath=outfile2)

    # Testing simple round trip. Export should have same transforms.
    
    nif1:pyn.NiShape = pyn.NifFile(outfile1)
    head1 = nif1.shapes[0]
    xf1 = BD.transform_to_matrix(head1.get_shape_skin_to_bone('Chest'))
    nif0 = pyn.NifFile(testfile)
    head0:pyn.NiShape = nif0.shapes[0]
    xf0 = BD.transform_to_matrix(head0.get_shape_skin_to_bone('Chest'))

    assert BD.MatNearEqual(xf0, xf1), f"Matrices are near equal: \n{xf0}\n=\n{xf1}"


def TEST_SKIN_BONE_XFORM():
    """Skin-to-bone transforms work correctly"""
    # The Argonian head has no global-to-skin transform and the bone pose locations are
    # exactly the vanilla locations, and yet the verts are organized around the origin.
    # The head is lifted into position with the skin-to-bone transforms (same way as FO4).

    testfile = TTB.test_file(r"tests\SkyrimSE\maleheadargonian.nif")
    outfile = TTB.test_file(r"tests\out\TEST_SKIN_BONE_XF.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TTB.find_object("_ArgonianMaleHead")
    assert NT.NearEqual(head.location.z, 120.344), f"Head is positioned at head position: {head.location}"
    minz = min(v[2] for v in head.bound_box)
    maxz = max(v[2] for v in head.bound_box)
    assert minz < 0, f"Head extends below origin: {minz}"
    assert maxz > 0, f"Head extends above origin: {maxz}"

    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    spine2_xf = arma.data.bones['NPC Spine2'].matrix_local
    head_xf = arma.data.bones['NPC Head'].matrix_local
    assert NT.VNearEqual(head_xf.translation, (-0.0003, -1.5475, 120.3436)), f"Head position at 120: {head_xf.translation}"
    assert NT.VNearEqual(spine2_xf.translation, (0.0, -5.9318, 91.2488)), f"Spine2 position at 91: {spine2_xf.translation}"

    spine2_pose_xf = arma.pose.bones['NPC Spine2'].matrix
    head_pose_xf = arma.pose.bones['NPC Head'].matrix
    assert NT.VNearEqual(head_pose_xf.translation, Vector((-0.0003, -1.5475, 120.3436))), f"Head pose position at 120: {head_pose_xf.translation}"
    assert NT.VNearEqual(spine2_pose_xf.translation, Vector((0.0000, -5.9318, 91.2488))), f"Spine2 pose position at 91: {spine2_pose_xf.translation}"

    head_nif = pyn.NifFile(testfile)
    head_nishape = head_nif.shapes[0]
    def print_xf(sh, bn):
        print(f"-----{bn}-----")
        global_xf = BD.transform_to_matrix(head_nif.nodes[bn].global_transform)
        sk2b_xf = BD.transform_to_matrix(head_nishape.get_shape_skin_to_bone(bn))
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
    assert NT.NearEqual(sk2b_spine.translation[2], 29.419632), f"Have correct z: {sk2b_spine.translation[2]}"


def do_bodypart_alignment_fo4(create_bones, estimate_offset, use_pose):
    """Should be able to write bodyparts and have the transforms match exactly."""
    headfile = TTB.test_file(r"tests\FO4\FoxFemaleHead.nif")
    skelfile = TTB.test_file(r"tests\FO4\skeleton.nif")
    bodyfile = TTB.test_file(r"tests\FO4\CanineFemBody.nif")
    headout = TTB.test_file(r"tests\out\TEST_BODYPART_ALIGHMENT_FO4_head.nif", output=True)
    bodyout = TTB.test_file(r"tests\out\TEST_BODYPART_ALIGHMENT_FO4_body.nif", output=True)

    # Read the body parts using the same skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile, 
                                 do_create_bones=create_bones,
                                 do_import_pose=use_pose)
    skel = [x for x in bpy.context.selected_objects if x.type == 'ARMATURE'][0]
    assert skel.type == 'ARMATURE', f"Have armature"
    BD.ObjectSelect([skel], active=True)
    bpy.ops.import_scene.pynifly(filepath=bodyfile, 
                                 do_create_bones=create_bones,
                                 do_import_pose=use_pose)
    body = bpy.context.object
    bodyarma = body.modifiers['Armature'].object
    TT.assert_eq(bodyarma, skel, "existing skeleton")
    BD.ObjectSelect([skel], active=True)
    bpy.ops.import_scene.pynifly(filepath=headfile, 
                                 do_create_bones=create_bones,
                                 do_import_pose=use_pose)
    head = bpy.context.object
    if estimate_offset:
        assert BD.NearEqual(head.location.z, 120.8, epsilon=0.1), f"Head in correct location"
    else:
        assert BD.NearEqual(head.location.z, 0), f"Head in correct location"
    assert len([x for x in bpy.context.view_layer.objects if x.type=='ARMATURE']) == 1, \
        f"Used same armature for all imports"

    # Write the body parts
    BD.ObjectSelect([body], active=True)
    bpy.ops.export_scene.pynifly(filepath=bodyout)
    BD.ObjectSelect([head], active=True)
    bpy.ops.export_scene.pynifly(filepath=headout)

    # Any verts in the same locations must have the same transforms.
    headNifCheck = pyn.NifFile(headout)
    headCheck = headNifCheck.shapes[0]
    bodyNifCheck = pyn.NifFile(bodyout)
    bodyCheck = bodyNifCheck.shapes[0]
    matchingPairsHB = [(3, 327), (16, 219), (1915, 1)]
    for hvi, bvi in matchingPairsHB:
        assert BD.VNearEqual(headCheck.verts[hvi], bodyCheck.verts[bvi]), "Matching verts at same location"
    # for i, vh in enumerate(headCheck.verts):
    #     for j, vb in enumerate(bodyCheck.verts):
    #         if BD.VNearEqual(vh, vb):
    #             print(f"Head {i} == Body {j}")
    for bn in ['Chest', 'Chest_skin', 'RArm_Collarbone_skin']:
        print(bn)
        print(headCheck.get_shape_skin_to_bone(bn).translation[:])
        print(bodyCheck.get_shape_skin_to_bone(bn).translation[:])
        assert BD.VNearEqual(headCheck.get_shape_skin_to_bone(bn).translation[:], 
                             bodyCheck.get_shape_skin_to_bone(bn).translation[:],
                             epsilon=0.0001), \
            f"Translations don't match: {headCheck.get_shape_skin_to_bone(bn).translation[:]} != {bodyCheck.get_shape_skin_to_bone(bn).translation[:]}"

def TEST_BODYPART_ALIGNMENT_FO4_1():
    """Read & write bodyparts and have the transforms match exactly, when estimating global-to-skin offset."""
    do_bodypart_alignment_fo4(create_bones=False, 
                              estimate_offset=True, 
                              use_pose=True)

## Now useing a better calc for the transform--don't need "estimate_offset"
# def TEST_BODYPART_ALIGNMENT_FO4_2():
#     """Read & write bodyparts and have the transforms match exactly, when NOT estimating global-to-skin offset."""
#     do_bodypart_alignment_fo4(create_bones=False, estimate_offset=False, use_pose=False)


def TEST_IMP_EXP_SKY():
    """Can read the armor nif and spit it back out"""
    # Round trip of ordinary Skyrim armor, with and without scale factor.

    testfile = TTB.test_file(r"tests/Skyrim/armor_only.nif")

    def do_test(game, blendxf):
        TTB.clear_all()
        xftext = '_XF' if blendxf else ''
        print(f"---Testing {'with' if blendxf else 'without'} blender transform for {game}")
        outfile = TTB.test_file(f"tests/Out/TEST_IMP_EXP_SKY_{game}{xftext}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=blendxf)
        armor = [obj for obj in bpy.context.selected_objects if obj.name.startswith('Armor')][0]

        impnif = pyn.NifFile(testfile)
        armorin = impnif.shape_dict['Armor']

        # Armor is in the right place.
        vmin, vmax = TTB.get_obj_bbox(armor)
        assert NT.VNearEqual(vmin, Vector([-30.32, -13.31, -90.03]), 0.1), f"Armor min is correct: {vmin}"
        assert NT.VNearEqual(vmax, Vector([30.32, 12.57, -4.23]), 0.1), f"Armor max is correct: {vmax}"
        assert NT.NearEqual(armor.location.z, 120.34, 0.01), f"{armor.name} in lifted position: {armor.location.z}"

        # Armor has one body partition (even tho 2 partitions in the nif, both are 32).
        TT.assert_contains("SBP_32_BODY", armor.vertex_groups, "Body partition")
        bp = armor.vertex_groups["SBP_32_BODY"]
        for i, v in enumerate(armor.data.vertices):
                TT.assert_contains(bp.index, [vg.group for vg in v.groups], f"Vertex {i} groups")

        # Armor has an armature.
        arma = armor.modifiers["Armature"].object
        assert arma.type == 'ARMATURE', f"armor has armature: {arma}"

        pelvis = arma.data.bones['NPC Pelvis']
        pelvis_pose = arma.pose.bones['NPC Pelvis'] 
        assert pelvis.parent.name == 'CME LBody', f"Pelvis has correct parent: {pelvis.parent}"
        assert NT.VNearEqual(pelvis.matrix_local.translation, pelvis_pose.matrix.translation), \
            f"Pelvis pose position matches bone position: {pelvis.matrix_local.translation} == {pelvis_pose.matrix.translation}"

        bpy.ops.object.select_all(action='DESELECT')
        armor.select_set(True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game=game, 
                                     use_blender_xf=blendxf, intuit_defaults=False)

        nifout = pyn.NifFile(outfile)
        armorout = nifout.shape_dict['Armor']
        assert nifout.game == game, f"Wrote correct game format: {nifout.game} == {game}"
        TTB.compare_shapes(armorin, armorout, armor, e=0.01)
        TTB.check_unweighted_verts(armorout)

    do_test('SKYRIMSE', False)
    do_test('SKYRIM', False)
    do_test('SKYRIM', True)
    do_test('SKYRIMSE', True)
        

def TEST_IMP_EXP_SKY_2():
    """Can read the armor nif with two shapes and spit it back out"""
    # Basic test that the import/export round trip works on nifs with multiple bodyparts. 
    # The body in this nif has no skin transform and the verts are where they appear
    # to be. The armor does have the usual transform on the shape and the skin, and the
    # verts are all below the origin. They have to be loaded into one armature.

    #testfile = TTB.test_file(r"tests/Skyrim/test.nif") 
    # 
    # The test.nif meshes are a bit wonky--one was pasted in by hand from SOS, the other
    # is a vanilla armor. The ForearmTwist2.L bind rotation is off by some hundredths.  
    # So do the test with the vanilla male body, which has two parts and is consistent.
    testfile = TTB.test_file(r"tests/Skyrim/malebody_1.nif")
    # skelfile = TTB.test_file(r"tests/Skyrim/skeleton_vanilla.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_SKY_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    assert len([x for x in bpy.data.objects if x.type=='ARMATURE']) == 1, \
        f"Both shapes brought in under one armor"
    body = TTB.find_shape('MaleUnderwearBody:0')
    armor = TTB.find_shape('MaleUnderwear_1')
    assert NT.VNearEqual(armor.location, (-0.0003, -1.5475, 120.3436)), \
        f"Armor is raised to match body: {armor.location}"

    BD.ObjectSelect([body, armor])
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nifout = pyn.NifFile(outfile)
    impnif = pyn.NifFile(testfile)  
    TTB.compare_shapes(impnif.shape_dict['MaleUnderwearBody:0'], nifout.shape_dict['MaleUnderwearBody:0'], body, e=0.01)
    TTB.compare_shapes(impnif.shape_dict['MaleUnderwear_1'], nifout.shape_dict['MaleUnderwear_1'], armor, e=0.01)

    TTB.check_unweighted_verts(nifout.shape_dict['MaleUnderwearBody:0'])
    TTB.check_unweighted_verts(nifout.shape_dict['MaleUnderwear_1'])
    assert NT.NearEqual(body.location.z, 120.343582, 0.01), f"{body.name} in lifted position: {body.location.z}"
    assert NT.NearEqual(armor.location.z, 120.343582, 0.01), f"{armor.name} in lifted position: {armor.location.z}"
    assert "NPC R Hand [RHnd]" not in bpy.data.objects, f"Did not create extra nodes representing the bones"
        

def TEST_CHILDHEAD():
    """The child head has face tint but tangent space normals. Check it exports correctly."""

    testfile = TTB.test_file(r"tests\SkyrimSE\childhead.nif")
    outfile = TTB.test_file(r"tests/out/TEST_CHILDHEAD.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = bpy.context.object
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    nifout = pyn.NifFile(outfile)
    CheckNif(nifout, source=testfile)


def TEST_IMP_EXP_FO4():
    """Can read the body nif and spit it back out"""

    testfile = TTB.test_file(r"tests\FO4\BTMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    impnif = pyn.NifFile(testfile)
    body = TTB.find_shape('BaseMaleBody:0')
    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    bodyin = impnif.shape_dict['BaseMaleBody:0']

    assert not NT.VNearEqual(body.location, [0, 0, 0], epsilon=1), f"Body is repositioned: {body.location}"
    assert arma.name == BD.arma_name("Scene Root"), f"Body parented to armature: {arma.name}"
    assert arma.data.bones['Pelvis_skin'].matrix_local.translation.z > 0, f"Bones translated above ground: {arma.data.bones['NPC Pelvis'].matrix_local.translation}"
    assert "Scene Root" not in arma.data.bones, "Did not import the root node"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nifout = pyn.NifFile(outfile)
    bodyout = nifout.shape_dict['BaseMaleBody:0']

    TTB.compare_shapes(bodyin, bodyout, body, e=0.001, ignore_translations=True)


def TEST_IMP_EXP_FO4_2():
    """Can read the body armor with 2 parts"""

    testfile = TTB.test_file(r"tests\FO4\Pack_UnderArmor_03_M.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_FO4_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TTB.find_shape('BaseMaleBody_03:0')
    armor = TTB.find_shape('Pack_UnderArmor_03_M:0')
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
    TTB.compare_shapes(bodyin, bodyout, body, e=0.001, ignore_translations=True)
    TTB.compare_shapes(armorin, armorout, armor, e=0.001, ignore_translations=True)
    for tl in ['Diffuse', 'Normal', 'Specular']:
        TT.assert_patheq(bodyin.textures[tl], bodyout.textures[tl], f"{tl} textures match")


def TEST_IMP_EXP_FO4_3():
    """Can read clothes + body and they come in sensibly"""

    testfile = TTB.test_file(r"tests\FO4\bathrobe.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_FO4_3.nif")

    # Setting do_import_pose=False results in a good import but the 
    # shapes jump around in edit mode.
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 do_create_bones=False,
                                 do_import_pose=True)
    body = TTB.find_shape('CBBE')
    robe = TTB.find_shape('OutfitF_0')
    bodymax = max((body.matrix_world @ v.co).z for v in body.data.vertices)
    robemax = max((robe.matrix_world @ v.co).z for v in robe.data.vertices)
    assert bodymax < robemax, f"Robe goes higher than body: {robemax} > {bodymax}"
    bodymin = min((body.matrix_world @ v.co).z for v in body.data.vertices)
    robemin = min((robe.matrix_world @ v.co).z for v in robe.data.vertices)
    assert robemin < bodymin, f"Robe extends below body: {robemin} < {bodymin}"



def TEST_ROUND_TRIP():
    """Can do the full round trip: nif -> blender -> nif -> blender"""
    testfile = TTB.test_file("tests/Skyrim/test.nif")
    outfile1 = TTB.test_file("tests/Out/TEST_ROUND_TRIP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    armor1 = bpy.data.objects["Armor"]
    assert int(armor1.location.z) == 120, "ERROR: Armor moved above origin by 120 to skinned position"
    maxz = max([v.co.z for v in armor1.data.vertices])
    minz = min([v.co.z for v in armor1.data.vertices])
    assert maxz < 0 and minz > -130, "Error: Vertices are positioned below origin"
    assert len(armor1.data.vertex_colors) == 0, "ERROR: Armor should have no colors"

    arma = bpy.data.objects["Scene Root:ARMATURE"]
    handl = arma.data.bones["NPC Hand.L"]
    handlx = handl.matrix_local @ arma.matrix_world
    assert 40 < handlx.translation.z < 100, f"Hand bone in correct location: {handlx.translation.z}"

    print("Exporting  to test file")
    bpy.ops.object.select_all(action='DESELECT')
    armor1.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile1, target_game='SKYRIM')
    assert os.path.exists(outfile1), "ERROR: Created output file"

    print("Re-importing exported file")
    TTB.clear_all()
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=outfile1)

    armor2 = [x for x in bpy.data.objects if x.name.startswith("Armor")][0]

    assert int(armor2.location.z) == 120, f"ERROR: Exported armor is re-imported with same position: {armor2.location}"
    for v in armor2.data.vertices:
        assert -120 < v.co.z < 0, f"Vertices positioned below origin: {v.co}"
        

def TEST_BPY_PARENT_A():
    """Maintain armature structure"""
    testfile = TTB.test_file(r"tests\Skyrim\test.nif")
    
    # Can intuit structure if it's not in the file
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.data.objects[BD.arma_name("Scene Root")]
    assert obj.data.bones['NPC Hand.R'].parent.name == 'CME Forearm.R', f"Error: Should find forearm as parent: {obj.data.bones['NPC Hand.R'].parent.name}"
    print(f"Found parent to hand: {obj.data.bones['NPC Hand.R'].parent.name}")


def TEST_BPY_PARENT_B():
    """Maintain armature structure"""
    testfile2 = TTB.test_file(r"tests\FO4\bear_tshirt_turtleneck.nif")
    
    ## Can read structure if it comes from file
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    obj = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
    assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3.R', "Error: Should find forearm as parent"


def TEST_RENAME():
    """Test that NOT renaming bones works correctly"""
    testfile = TTB.test_file(r"tests\Skyrim\femalebody_1.nif")

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
    """Can import connected skeleton"""
    # Check that the bones of the armature are connected correctly.

    bpy.ops.object.select_all(action='DESELECT')
    testfile = TTB.test_file(r"tests\FO4\vanillaMaleBody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    s = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert s.type == 'ARMATURE', f"Imported the skeleton {s}" 
    assert 'Leg_Thigh.L' in s.data.bones.keys(), "Error: Should have left thigh"
    lthigh = s.data.bones['Leg_Thigh.L']
    assert lthigh.parent.name == 'Pelvis', "Error: Thigh should connect to pelvis"
    assert NT.VNearEqual(lthigh.head_local, (-6.6151, 0.0005, 68.9113)), f"Thigh head in correct location: {lthigh.head_local}"
    
    # Tail location depends on whether we rotate the bones.
    # assert NT.VNearEqual(lthigh.tail_local, (-7.2513, -0.1925, 63.9557)), f"Thigh tail in correct location: {lthigh.tail_local}"


# ### Following test works but probably duplicates others. 
# def TEST_HELM_SMP():
#     """Import helm with different parts at different offsets."""
#     testfile = TTB.test_file(r"tests\SkyrimSE\helmet-SMP.nif")
#     outfile = TTB.test_file(r"tests\SkyrimSE\TEST_HELM_SMP.nif")
#     bpy.ops.import_scene.pynifly(filepath=testfile, 
#                                  use_blender_xf=True,
#                                  do_create_bones=False,
#                                  do_import_pose=False)

#     root = [obj for obj in bpy.context.selected_objects if 'pynRoot' in obj][0]
#     BD.ObjectSelect([root], active=True)
#     bpy.ops.export_scene.pynifly(filepath=outfile, preserve_hierarchy=True)
    
#     nifout = pyn.NifFile(outfile)


def TEST_DRAUGR_IMPORT_A():
    """Import hood, extend skeleton, non-vanilla pose"""
    # This nif uses the draugr skeleton, which has bones named like human bones but with
    # different positions--BUT the hood was made for the human skeleton so the bind
    # position of its bones don't match the draugr skeleton. Bones defined by the hood are
    # given the human bind position--the rest come from the reference skeleton and use
    # those bind positions. 

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\draugr lich01 hood.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_A.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 do_create_bones=True,
                                 do_import_pose=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    hood = TTB.find_shape("Hood")

    bonemaxz = max(b.head.z for b in arma.data.bones)
    hoodmaxz = max(v.co.z for v in hood.data.vertices)
    assert hoodmaxz > bonemaxz, f"Hood covers skeleton"

    # Pose position reflects the draugr skeleton, but bind position is the human position. 
    bone1 = arma.data.bones['NPC Head']
    pose1 = arma.pose.bones['NPC Head']
    assert pose1.head.z > bone1.head.z+10, f"Pose well above bind positions"
    

def TEST_DRAUGR_IMPORT_B():
    """Import hood, don't extend skeleton, non-vanilla pose"""
    # This hood uses non-human bone node positions and we don't extend the skeleton, so
    # bones are given the bind position from the hood but the pose position from the nif.
    # Since the pose is not a pure translation, we do not put a transform on the hood
    # shape.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\draugr lich01 hood.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_B.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 do_create_bones=False,
                                 do_import_pose=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    hood = TTB.find_shape("Hood")
    bone1 = arma.data.bones['NPC UpperarmTwist1.R']
    pose1 = arma.pose.bones['NPC UpperarmTwist1.R']

    # Lots of bones in this nif are not used in the hood. Bones used in the hood have pose
    # and bind locations. The rest only have pose locations and are brought in as Empties.
    assert not NT.VNearEqual(pose1.matrix.translation, bone1.matrix_local.translation), \
        f"Pose position is not bind position: {pose1.matrix.translation} != {bone1.matrix_local.translation}"
    

def TEST_DRAUGR_IMPORT_C():
    """Import helm, don't extend skeleton"""
    # The helm has bones that are in the draugr's vanilla bind position.

    testfile = TTB.test_file(r"tests\SkyrimSE\draugr lich01 helm.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_C.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 do_create_bones=False,
                                 do_import_pose=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    bone1 = skel.data.bones['NPC Head']
    pose1 = skel.pose.bones['NPC Head']

    assert not NT.VNearEqual(bone1.matrix_local.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not in vanilla bind position: {bone1.matrix_local.translation}"
    assert not NT.VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not posed in vanilla position: {pose1.matrix_local.translation}"


def TEST_DRAUGR_IMPORT_D():
    """Import helm, do extend skeleton"""
    # Fo the helm, when we import WITH adding bones, we get a full draugr skeleton.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\draugr lich01 helm.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_D.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 do_create_bones=True,
                                 do_import_pose=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    bone1 = skel.data.bones['NPC Head']
    pose1 = skel.pose.bones['NPC Head']
    bone2 = skel.data.bones['NPC Spine2']
    pose2 = skel.pose.bones['NPC Spine2']

    assert NT.VNearEqual(bone1.matrix_local.translation, [-0.015854, -2.40295, 134.301]), \
        f"Head bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert not NT.VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436], epsilon=2.0), \
        f"Head bone not posed in vanilla position: {pose1.matrix.translation}"

    assert NT.VNearEqual(bone2.matrix_local.translation, [0.000004, -5.83516, 102.358]), \
        f"Spine bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert NT.VNearEqual(pose2.matrix.translation, [0.0000, -5.8352, 102.3579]), \
        f"Spine bone posed in draugr position: {pose2.matrix.translation}"
    
    assert bone2.parent.name == 'NPC Spine1', \
        f"Spine bone has correct parent: {bone2.parent.name}"
    

def TEST_DRAUGR_IMPORT_E():
    """Import of this draugr mesh positions hood correctly"""
    # This nif has two shapes and the bind positions differ. The hood bind position is
    # human, and it's posed to the draugr position. The draugr hood is bound at pose
    # position, so pose and bind positions are the same. The only solution is to import as
    # two skeletons and let the user sort it out. We lose the bind position info but end up with the shapes parented
    # to one armature.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\draugr lich01 simple.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_E.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 do_create_bones=False,
                                 do_import_pose=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    hood = TTB.find_shape("Hood")
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
    helm_bb = TTB.get_obj_bbox(helm, worldspace=True)
    hood_bb = TTB.get_obj_bbox(hood, worldspace=True)
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

    assert not NT.VNearEqual(bone1.matrix_local.translation, pose1.matrix.translation), \
        f"Pose and bind locaations differ: {bone1.matrix_local.translation} != {pose1.matrix.translation}"
    

def TEST_SCALING_BP():
    """Can scale bodyparts"""

    testfile = TTB.test_file(r"tests\Skyrim\malebody_1.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SCALING_BP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 rename_bones_niftools=True,
                                 use_blender_xf=True)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    b = arma.data.bones['NPC Spine1 [Spn1]']
    bw = arma.matrix_world @ b.matrix_local
    assert NT.NearEqual(bw.translation.z, 8.1443), f"Scale correctly applied: {bw.translation}"
    body = TTB.find_shape("MaleUnderwearBody:0")
    blw = arma.matrix_world @ body.location
    assert NT.NearEqual(blw.z, 12, 0.1), f"Object translation correctly applied: {blw}"
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
    assert NT.NearEqual(bodycheck.transform.scale, 1.0), f"Scale is 1: {bodycheck.transform.scale}"
    assert NT.NearEqual(bodycheck.transform.translation[2], 120.3, 0.1), \
        f"Translation is correct: {list(bodycheck.transform.translation)}"
    bmaxout = max(v[2] for v in bodycheck.verts)
    bminout = min(v[2] for v in bodycheck.verts)
    assert bmaxout-bminout > 100, f"Shape scaled up on ouput: {bminout}-{bmaxout}"
    assert bodycheck.verts[228][1] > bodycheck.verts[713][1], f"Chest is in front of back: {bodycheck.verts[228][1]} > {bodycheck.verts[713][1]}"


def TEST_IMP_EXP_SCALE_2():
    """Can read the body nif scaled"""
    # Regression: Making sure that the scale factor doesn't mess up importing under one
    # armature.

    testfile = TTB.test_file(r"tests/Skyrim/malebody_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_SCALE_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)

    armatures = [x for x in bpy.data.objects if x.type=='ARMATURE']
    assert len(armatures) == 1, f"Have just one armature"
    body = TTB.find_shape('MaleUnderwearBody:0')
    armor = TTB.find_shape('MaleUnderwear_1')
    body_arma = next(a.object for a in body.modifiers if a.type == 'ARMATURE')
    armor_arma = next(a.object for a in armor.modifiers if a.type == 'ARMATURE')
    assert body_arma == armor_arma, f"Both shapes brought in under one armature"

    # We imported scaled down and rotated 180.
    assert NT.VNearEqual((armor_arma.matrix_world @ armor.location), (-0.0, 0.15475, 12.03436)), \
        f"Armor is raised to match body: {armor.location}"
    
    
def TEST_ARMATURE_EXTEND():
    """Can extend an armature with a second NIF"""
    # Can import a shape with an armature and then import another shape to the same armature. 

    # ------- Load --------
    testfile = TTB.test_file(r"tests\FO4\MaleBody.nif")
    testfile2 = TTB.test_file(r"tests\FO4\BaseMaleHead.nif")

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

    head = TTB.find_shape("BaseMaleHead:0")
    body = TTB.find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = TTB.find_vertex(head.data, target_v)
    v_body = TTB.find_vertex(body.data, target_v)
    assert NT.VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        f"Head and body verts align"
    
    # For FO4, we give a generous fudge factor.
    assert TTB.MatNearEqual(head.matrix_world, body.matrix_world, epsilon=0.1), f"Shape transforms match"


def TEST_ARMATURE_EXTEND_BT():
    """Can extend an armature with a second NIF"""
    # The Bodytalk body has bind positions consistent with vanilla, but the skin 
    # transform is different, which leaves a slight gap at the neck. For now, live 
    # with this.
    #  
    # The FO4 body nif does not use all bones from the skeleton, e.g. LLeg_Calf. If we're 
    # adding missing skeleton bones, we have to get them from the reference skeleton,
    # which pyNifly handles, and put them into the skeleton consistently with the rest.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\FO4\BTBaseMaleBody.nif")
    testfile2 = TTB.test_file(r"tests\FO4\BaseMaleHead.nif")

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

    head = TTB.find_shape("BaseMaleHead:0")
    body = TTB.find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = TTB.find_vertex(head.data, target_v)
    v_body = TTB.find_vertex(body.data, target_v)
    assert NT.VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        f"Head and body verts align"
    # Shape transforms are different between vanilla head and BT body.
    #assert TTB.MatNearEqual(head.matrix_world, body.matrix_world), f"Shape transforms match"


def TEST_EXPORT_WEIGHTS():
    """Import and export with weights"""
    # Simple test to see that when vertex groups are associated with bone weights they are
    # written correctly.
    # 
    # Also check that when we have multiple objects under a skeleton and only select one,
    # only that one gets written. 
    testfile = TTB.test_file(r"tests\Skyrim\test.nif")
    filepath_armor = TTB.test_file("tests/out/testArmorSkyrim02.nif")
    filepath_armor_fo = TTB.test_file(r"tests\Out\testArmorFO02.nif")
    filepath_body = TTB.test_file(r"tests\Out\testBodySkyrim02.nif")

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
    """Exporting this head weights all verts correctly"""
    outfile = TTB.test_file(r"tests/Out/TEST_WEIGHTS_EXPORT.nif")

    head = TTB.append_from_file("CheetahFemaleHead", True, r"tests\FO4\CheetahHead.blend", 
                            r"\Object", "CheetahFemaleHead")
    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)

    # Check that every vertex is weighted to at least one bone.
    headcheck = nifcheck.shape_dict["CheetahFemaleHead"]
    vert_weights = [0] * len(headcheck.verts)
    for bn, vertlist in headcheck.bone_weights.items():
        for vi, wgt in vertlist:
            vert_weights[vi] = 1
    assert min(vert_weights) == 1, f"Have a weight for every vertex"



def TEST_0_WEIGHTS():
    """Gives warning on export with 0 weights"""
    testfile = TTB.test_file(r"tests\Out\weight0.nif")

    baby = TTB.append_from_file("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
    baby.parent.name == "BabyExportRoot", f"Error: Should have baby and armature"
    log.debug(f"Found object {baby.name}")
    try:
        bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")
    except RuntimeError:
        print("Caught expected runtime error")
    assert BD.UNWEIGHTED_VERTEX_GROUP in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


def TEST_TIGER_EXPORT():
    """Tiger head exports without errors"""
    f = TTB.test_file(r"tests/Out/TEST_TIGER_EXPORT.nif")
    fb = TTB.test_file(r"tests/Out/TEST_TIGER_EXPORT_faceBones.nif")
    ftri = TTB.test_file(r"tests/Out/TEST_TIGER_EXPORT.tri")
    fchargen = TTB.test_file(r"tests/Out/TEST_TIGER_EXPORT_chargen.tri")

    TTB.append_from_file("TigerMaleHead", True, r"tests\FO4\Tiger.blend", r"\Object", "TigerMaleHead")

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
    """Test that this mesh imports with the right transforms"""

    testfile = TTB.test_file(r"tests/SkyrimSE/3BBB_femalebody_1.nif")
    testfile2 = TTB.test_file(r"tests/SkyrimSE/3BBB_femalehands_1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    obj = bpy.context.object
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert NT.NearEqual(obj.location[0], 0.0), f"Expected body to be centered on x-axis, got {obj.location}"

    print("## Test that the same armature is used for the next import")
    BD.ObjectSelect([arma], active=True)
    bpy.context.view_layer.objects.active = arma
    bpy.ops.import_scene.pynifly(filepath=testfile2)

    arma2 = next(m.object for m in bpy.context.object.modifiers if m.type == 'ARMATURE')
    assert arma2.name == arma.name, f"Should have parented to same armature: {arma2.name} != {arma.name}"


def TEST_CONNECT_SKEL():
    """Can import and export FO4 skeleton file with no shapes"""
    def do_test(use_xf):
        print(f"Can import and export FO4 skeleton file with no shapes, transform {use_xf}")
        TTB.clear_all()
        testname = "TEST_SKEL_" + str(use_xf)
        testfile = TTB.test_file(r"skeletons\FO4\skeleton.nif")
        outfile = TTB.test_file(r"tests/out/" + testname + ".nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, 
                                     do_create_bones=False, 
                                     use_blender_xf=use_xf)

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
        assert TTB.MatNearEqual(rootbone.matrix, BD.transform_to_matrix(rootnode.transform)), \
            f"Bone transform matches nif: {rootbone.matrix}"

        # Parent connect points are children of the armature. Could also be children of the root
        # but they get transposed based on the armature bones' transforms.
        cp_lleg = bpy.data.objects['BSConnectPointParents::P-ArmorLleg']
        assert cp_lleg.parent.type == 'ARMATURE', f"cp_lleg has armature as parent: {cp_lleg.parent}"
        assert NT.NearEqual(cp_lleg.location[0], 33.745487), \
            f"Armor left leg connect point at position: {cp_lleg.location}"

        BD.ObjectSelect([bpy.data.objects['skeleton.nif:ROOT']], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', 
                                     preserve_hierarchy=True, 
                                     use_blender_xf=use_xf)

        skel_in = pyn.NifFile(testfile)
        skel_out = pyn.NifFile(outfile)
        assert "L_RibHelper" in skel_out.nodes, "Bones written to nif"
        pb = skel_out.nodes["L_RibHelper"].parent
        assert pb.name == "Chest", f"Have correct parent: {pb.name}"
        helm_cp_in = [x for x in skel_in.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
        helm_cp_out = [x for x in skel_out.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
        assert helm_cp_out.parent.decode('utf-8') == 'HEAD', f"Parent is correct: {helm_cp_out.parent}"
        assert NT.VNearEqual(helm_cp_in.translation, helm_cp_out.translation), \
            f"Connect point locations correct: {Vector(helm_cp_in.translation)} == {Vector(helm_cp_out.translation)}"
        
    do_test(False)
    do_test(True)


def TEST_SKEL_SKY():
    """Can import and export Skyrim skeleton file with no shapes"""
    testfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    outfile = TTB.test_file(r"tests/out/TEST_SKEL_SKY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    root = next(x for x in bpy.data.objects if 'pynRoot' in x)

    bumper_bone = arma.pose.bones['CharacterBumper']
    bumper_constr = bumper_bone.constraints[0]
    bumper_col = bumper_constr.target
    assert bumper_col, "Have bumper collision"
    bb = TTB.get_obj_bbox(bumper_col, worldspace=True)
    assert bb[1][2] - bb[0][2] > bb[1][0] - bb[0][0] \
        and bb[1][2] - bb[0][2] > bb[1][1] - bb[0][1], \
            f"Character bumper long dimension is vertical: {bb}"

    foot_bone = arma.pose.bones['NPC Foot.R']
    foot_constr = foot_bone.constraints[0]
    foot_col = foot_constr.target
    assert foot_col, "Have foot collision object"


def TEST_HEADPART():
    """Can read & write an SE head part"""
    # Tri files can be loaded up into a shape in blender as shape keys. On SE, when there
    # are shape keys a BSDynamicTriShape is used on export.
    testfile = TTB.test_file(r"tests/SKYRIMSE/malehead.nif")
    testtri = TTB.test_file(r"tests/SKYRIMSE/malehead.tri")
    testfileout = TTB.test_file(r"tests/out/TEST_HEADPART.nif")
    testfileout2 = TTB.test_file(r"tests/out/TEST_HEADPART2.nif")
    testfileout3 = TTB.test_file(r"tests/out/TEST_HEADPART3.nif")

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
    eyelid = TTB.find_vertex(obj.data, [-2.52558, 7.31011, 124.389])
    mouth = TTB.find_vertex(obj.data, [1.8877, 7.50949, 118.859])
    assert not NT.VNearEqual(head2.verts[eyelid], head3.verts[eyelid]), \
        f"Verts have moved: {head2.verts[eyelid]} != {head3.verts[eyelid]}"
    assert not NT.VNearEqual(head2.verts[mouth], head3.verts[mouth]), \
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


def TEST_TRI_SIMPLE():
    """Can create and export a mesh with shapekeys to a tri file."""
    tricubenif = TTB.test_file(r"tests\Out\tricube01.nif")
    tricubeniftri = TTB.test_file(r"tests\Out\tricube01.tri")
    tricubenifchg = TTB.test_file(r"tests\Out\tricube01chargen.tri")

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
    

def TEST_TRI():
    """Can load a tri file into an existing mesh"""

    testfile = TTB.test_file(r"tests\FO4\CheetahMaleHead.nif")
    testtri2 = TTB.test_file(r"tests\FO4\CheetahMaleHead.tri")
    testtri3 = TTB.test_file(r"tests\FO4\CheetahMaleHead.tri")
    testout2 = TTB.test_file(r"tests\Out\CheetahMaleHead02.nif")
    testout2tri = TTB.test_file(r"tests\Out\CheetahMaleHead02.tri")
    testout2chg = TTB.test_file(r"tests\Out\CheetahMaleHead02chargen.tri")

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


def TEST_TRI_EYES():
    """Child eyes tris are odd--handle them correctly."""
    testfile = TTB.test_file(r"tests\Skyrim\eyeschild.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)


def TEST_TRI_HIMBO():
    """HIMBO tris are odd."""
    testfile = TTB.test_file(r"tests\SkyrimSE\himbo.nif")
    testfile2 = TTB.test_file(r"tests\SkyrimSE\himbo.tri")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    assert len(bpy.data.objects) > 2, f"Have more than 2 objects: {bpy.data.objects}"
    bpy.ops.import_scene.pyniflytri(filepath=testfile2)


def TEST_TRI_WILLOW():
    """Import tri file correctly"""
    testfile = TTB.test_file(r"tests\FONV\headfemale_willow.tri")
    bpy.ops.import_scene.pyniflytri(filepath=testfile)
    assert bpy.context.object.name is not None, f"Imported tri file: {bpy.context.object.name}"


def TEST_TRI_BASEMALEHEAD():
    """Import tri file correctly when the nif has more verts than the tri."""
    testfile = TTB.test_file(r"tests\FO4\basemalehead.nif")
    testfile2 = TTB.test_file(r"tests\FO4\basemalehead.tri")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    assert bpy.context.object.name is not None, f"Imported nif file: {bpy.context.object.name}"
    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 1, f"Have one mesh: {meshes}"
    mesh = meshes[0]
    assert mesh.data.shape_keys is not None, "Mesh has shape keys"
    assert len(mesh.data.shape_keys.key_blocks) > 5, f"Expected more than 5 shape keys, got {len(mesh.data.shape_keys.key_blocks)}"


def TEST_IMPORT_MULTI_OBJECTS():
    """Can import 2 meshes as objects"""
    # When two files are selected for import, they are connected into a single armature.

    testfiles = [{"name": TTB.test_file(r"tests\SkyrimSE\malehead.nif")}, 
                 {"name": TTB.test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
    bpy.ops.import_scene.pynifly(files=testfiles)

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
    """Can import 2 meshes as shape keys"""

    testfiles = [{"name": TTB.test_file(r"tests\SkyrimSE\body1m_0.nif")}, 
                 {"name": TTB.test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
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
    """Can import >2 meshes as shape keys"""
    # When multiple files are selected for a single import, they are connected up as 
    # shape keys if possible.

    testfiles = [{"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_Cat.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_CatF.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_Horse.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_Hyena.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_LionLyk.nif")}, 
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
    """Ensure renamed shape keys export properly"""
    if bpy.app.version[0] < 3: return

    # The export/import process can change left/right shape keys to better match Blender's
    # naming conventions.
    #
    # Doesn't work on 2.x. Not sure why.
    outfile = TTB.test_file(r"tests/Out/TEST_EXP_SK_RENAMED.nif")
    trifile = TTB.test_file(r"tests/Out/TEST_EXP_SK_RENAMED.tri")
    chargenfile = TTB.test_file(r"tests/Out/TEST_EXP_SK_RENAMEDchargen.tri")

    TTB.append_from_file("BaseFemaleHead:0", True, r"tests\FO4\FemaleHead.blend", 
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
    """Export multiple objects with only some shape keys"""

    outfile = TTB.test_file(r"tests/Out/TEST_SK_MULT.nif")
    outfile0 = TTB.test_file(r"tests/Out/TEST_SK_MULT_0.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_SK_MULT_1.nif")

    TTB.append_from_file("CheMaleMane", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "CheMaleMane")
    TTB.append_from_file("MaleTail", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "MaleTail")
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


def TEST_NOSETTINGS():
    """Can import with all settings off (regression)."""
    testfile = TTB.test_file("tests\SkyrimSE\circlet_celebrimbor.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_NOSETTINGS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 do_create_bones=False,
                                 use_blender_xf=False,
                                 do_rename_bones=False,
                                 do_import_animations=False,
                                 do_import_collisions=False,
                                 do_import_tris=False,
                                 rename_bones_niftools=False,
                                 do_import_shapes=False,
                                 do_apply_skinning=False,
                                 do_import_pose=False,)                                                                                           


def TEST_CIRCLET():
    """This high-precision circlet imports correctly and can be exported as a ground object."""
    testfile = TTB.test_file("tests\SkyrimSE\circlet_celebrimbor.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_CIRCLET.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 do_create_bones=False,
                                 use_blender_xf=False,
                                 do_rename_bones=False,
                                 do_import_animations=False,
                                 do_import_collisions=False,
                                 do_import_tris=False,
                                 rename_bones_niftools=False,
                                 do_import_shapes=False,
                                 do_apply_skinning=False,
                                 do_import_pose=False,)                                                                                           
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    bbox = TTB.get_obj_bbox(obj, worldspace=True)
    TT.assert_lt(bbox[0][0], -2, "X")
    TT.assert_gt(bbox[1][0], 2, "X")
    TT.assert_eq(TTB.find_vertex(obj.data, [0.0, 0.0, 0.0]), -1, "No vertex near origin")


def TEST_TRI2():
    """Regression: Test correct improt of tri"""
    testfile = TTB.test_file(r"tests/Skyrim/OtterMaleHead.nif")
    trifile = TTB.test_file(r"tests/Skyrim/OtterMaleHeadChargen.tri")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    bpy.ops.import_scene.pyniflytri(filepath=trifile)

    v1 = obj.data.shape_keys.key_blocks['VampireMorph'].data[1]
    assert v1.co[0] <= 30, "Shape keys not relative to current mesh"


def TEST_BAD_TRI():
    """Tris with messed up UVs can be imported"""
    # Tri files have UVs in them, but it's mostly not used, and some tris have messed up
    # UVs. Make sure they can be read anyway.

    testfile = TTB.test_file(r"tests/Skyrim/bad_tri.tri")
    testfile2 = TTB.test_file(r"tests/Skyrim/bad_tri_2.tri")
    
    bpy.ops.import_scene.pyniflytri(filepath=testfile)
    obj = bpy.context.object
    assert len(obj.data.vertices) == 6711, f"Expected 6711 vertices, found {len(obj.data.vertices)}"

    bpy.ops.import_scene.pyniflytri(filepath=testfile2)
    obj2 = bpy.context.object
    assert len(obj2.data.vertices) == 11254, f"Expected 11254 vertices, found {len(obj2.data.vertices)}"


def TEST_SEGMENTS():
    """Can read FO4 segments"""

    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SEGMENTS.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object

    # FO4 segments have convenient names
    TT.assert_contains("FO4 Seg 003", obj.vertex_groups, "Segment 003")
    TT.assert_contains("FO4 Seg 004 | 000 | Up Arm.L", obj.vertex_groups, "Upper Arm Left")

    # The vertex groups actually have vertices in them.
    verts = TTB.vertices_in_group(obj, "FO4 Seg 004 | 000 | Up Arm.L")
    assert len(verts) > 3, f"Have verts in group: {len(verts)}"
    assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "Should have FO4 segment file read and saved for later use"

    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    
    nif2 = pyn.NifFile(outfile)
    CheckNif(nif2, testfile)
    

def TEST_BP_SEGMENTS():
    """Can read FO4 bodypart segments"""

    testfile = TTB.test_file(r"tests/FO4/Helmet.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_BP_SEGMENTS.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    helmet = bpy.data.objects['Helmet:0']
    visor = bpy.data.objects['glass:0']
    assert helmet.name == "Helmet:0", "Read the helmet object"
    assert "FO4 Seg 001 | Hair Top | Head" in helmet.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
    assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == helmet['FO4_SEGMENT_FILE'], "FO4 segment file read and saved for later use"

    assert visor.name == "glass:0", "Read the visor object"
    assert "FO4 Seg 001 | Hair Top" in visor.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
    TT.assert_eq(visor.active_material['envMapTexture'], "shared/cubemaps/shinyglass_e.dds", 
                 "Environment map texture")

    print("### Can write FO4 segments")
    bpy.ops.object.select_all(action='SELECT')
    e = bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")
    test_loghandler.check()

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
    """Verts export in the correct segments"""
    # Game can get crashy if there are a bunch of empty segments at the end of the list.

    outfile = TTB.test_file(r"tests/Out/TEST_EXP_SEGMENTS_BAD.nif")

    TTB.append_from_file("ArmorUnder", True, r"tests\FO4\ArmorExportsBadSegments.blend", r"\Object", "ArmorUnder")

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
    """Segments export in numerical order"""
    if bpy.app.version[0] < 3: return 

    # Order matters for the segments, so make sure it's right.
    outfile = TTB.test_file(r"tests/Out/TEST_EXP_SEG_ORDER.nif")

    gen1bod = TTB.append_from_file("SynthGen1Body", True, r"tests\FO4\SynthGen1BodyTest.blend", r"\Object", "SynthGen1Body")

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
    """Can read Skyrim partions"""
    testfile = TTB.test_file(r"tests/Skyrim/malehead.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_PARTITIONS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    TT.assert_contains("SBP_130_HEAD", obj.vertex_groups, "Head part")

    # Verts are correctly assigned to head parts.
    neckgroup = obj.vertex_groups["SBP_230_NECK"]
    maxz = -sys.float_info.max
    for v in obj.data.vertices:
        for vg in v.groups:
            if vg.group == neckgroup.index:
                maxz = max(maxz, v.co.z)
    assert -3 < maxz < -2, f"Neck verts are all low on head"

    print("### Can write Skyrim partitions")
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")
    
    nif2 = pyn.NifFile(outfile)
    CheckNif(nif2, testfile)


def TEST_PARTITIONS_EMPTY():
    """Do not write empty partitions"""
    testfile = TTB.test_file(r"tests\SkyrimSE\Head_EmptyPartition.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_PARTITIONS_EMPTY.nif")

    TTB.append_from_file("MaleHeadIMF", True, testfile, r"\Object", "MaleHeadIMF")
    obj = TTB.find_shape("MaleHeadIMF")

    BD.ObjectSelect([obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")
    
    nif2 = pyn.NifFile(outfile)
    head = nif2.shapes[0]
    assert len(nif2.shapes[0].partitions) == 2, "Have only partitions with content"
    assert set([p.id for p in head.partitions]) == set([130, 230]), "Have all head parts"


def TEST_SHADER_LE():
    """Shader attributes are read and turned into Blender shader nodes"""

    fileLE = TTB.test_file(r"tests\Skyrim\meshes\actors\character\character assets\malehead.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_LE.nif")
    bpy.ops.import_scene.pynifly(filepath=fileLE, use_blender_xf=True)

    nifLE = pyn.NifFile(fileLE)
    shaderAttrsLE = nifLE.shapes[0].shader.properties
    headLE = bpy.context.object
    shadernodes = headLE.active_material.node_tree.nodes
    assert 'SkyrimShader:Face' in shadernodes, \
        f"Shader nodes complete: {shadernodes.keys()}"
    bsdf = shadernodes['SkyrimShader:Face']
    assert 'Diffuse_Texture' in shadernodes, f"Shader nodes complete: {shadernodes.keys()}"
    assert bsdf.inputs['Normal'].is_linked, f"Have a normal map"
    assert bsdf.inputs['Diffuse'].is_linked, f"Have a base color"
    g = bsdf.inputs['Glossiness'].default_value
    assert round(g, 4) == 33, f"Glossiness not correct, value is {g}"
    assert headLE.active_material['BSShaderTextureSet_SoftLighting'] == r"textures\actors\character\male\MaleHead_sk.dds", \
        f"Expected stashed texture path, found {headLE.active_material['BSShaderTextureSet_2']}"

    print("## Shader attributes are written on export")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifcheckLE = pyn.NifFile(outfile)
    
    check = nifcheckLE.shapes[0].textures
    original = nifLE.shapes[0].textures
    assert set(check.keys()) == set(original.keys()), f"Have same keys: {set(check.keys())}"
    for k in check:
        assert check[k].lower() == original[k].lower(), f"Value of {k} texture matches"

    checkattrs = nifcheckLE.shapes[0].shader.properties
    assert not checkattrs.compare(shaderAttrsLE), \
        f"Shader properties correct: {checkattrs.compare(shaderAttrsLE)}"


def TEST_SHADER_SE():
    """Shader attributes are read and turned into Blender shader nodes"""
    # Basic test of texture paths on shaders.

    fileSE = TTB.test_file(r"tests\SkyrimSE\meshes\armor\dwarven\dwarvenboots_envscale.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_SE.nif")
    
    bpy.ops.import_scene.pynifly(filepath=fileSE, use_blender_xf=True)
    nifSE = pyn.NifFile(fileSE)
    nifboots = nifSE.shapes[0]
    shaderAttrsSE = nifboots.shader.properties
    boots = bpy.context.object
    shadernodes = boots.active_material.node_tree.nodes
    TT.assert_gt(len(shadernodes), 4, "Number of shader nodes")
    TT.assert_eq(boots.active_material['Env_Map_Scale'], shaderAttrsSE.Env_Map_Scale, "environment map scale")
    TT.assert_eq(bpy.data.materials["Shoes.Mat"].node_tree.nodes["UV_Converter"].inputs[4].default_value, 1, "Wrap U")

    print("## Shader attributes are written on export")
    bpy.ops.object.select_all(action='DESELECT')
    boots.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = pyn.NifFile(outfile)
    CheckNif(nifcheckSE, fileSE)
    bootcheck = nifcheckSE.shapes[0]
    
    TT.assert_samemembers(bootcheck.textures.keys(), nifboots.textures.keys(), "Same textures")
    for k in bootcheck.textures:
        TT.assert_patheq(bootcheck.textures[k], nifboots.textures[k], f"{k} texture")

    diffs = bootcheck.shader.properties.compare(shaderAttrsSE)
    TT.assert_samemembers(diffs, [], f"difference in shader properties: {diffs}")
    TT.assert_eq(bootcheck.has_alpha_property, False, "has_alpha_property")


def TEST_SHADER_FO4():
    """Shader attributes are read and turned into Blender shader nodes"""
    fileFO4 = TTB.test_file(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\basemalehead.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_FO4.nif")
    matin = TTB.test_file(r"tests\FO4\Materials\Actors\Character\BaseHumanMale\basehumanskinHead.bgsm")
    matout = TTB.test_file(r"tests\Out\Materials\Actors\Character\BaseHumanMale\basehumanskinHead.bgsm")

    bpy.ops.import_scene.pynifly(filepath=fileFO4, use_blender_xf=True)
    headFO4 = bpy.context.object
    
    nifFO4 = pyn.NifFile(fileFO4)
    shapeorig = nifFO4.shapes[0]
    for t in ['Diffuse_Texture', 'Normal_Texture', 'Specular_Texture']:
        txt = headFO4.active_material.node_tree.nodes[t]
        assert txt and txt.image and txt.image.filepath, f"Imported texture {t}"

    # Shader attributes are written on export

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # Put the materials file where the importer will find it.
    if not os.path.exists(matout):
        matdirout = os.path.split(matout)[0]
        shutil.os.makedirs(matdirout, exist_ok=True)
        shutil.copy(matin, matout)

    nifcheckFO4 = pyn.NifFile(outfile)
    
    shapecheck = nifcheckFO4.shapes[0]

    assert set(shapecheck.textures.keys()) == set(shapeorig.textures.keys()), \
        f"Have same keys: {shapecheck.textures.keys()} == {shapeorig.textures.keys()}"
    for k in shapecheck.textures:
        TT.assert_patheq(shapecheck.textures[k], shapeorig.textures[k], f"Texture {k} matches")

    assert not shapecheck.properties.compare(shapeorig.properties), \
        f"Shader attributes preserved: {shapecheck.properties.compare(shapeorig.properties)}"
    assert shapecheck.name == shapeorig.name, f"Error: Shader name not preserved: '{shapecheck.shader_name}' != '{shapeorig.shader_name}'"


def TEST_SHADER_GRAYSCALE_COLOR():
    """Test that grayscale color is handled directly"""
    testfile = TTB.test_file(r"tests\FO4\FemaleHair25.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_GRAYSCALE_COLOR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    h = TTB.find_shape("FemaleHair25:0")
    m = h.active_material
    bsdf = m.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node

    # Greyscale palette correct
    vecnode = BD.find_node(bsdf.inputs['Diffuse'], 'ShaderNodeTexImage')[0]
    assert Path(vecnode.image.filepath).parts.index('haircolor_lgrad_d.dds') >= 0,  "Vector palette"
    difnode = BD.find_node(vecnode.inputs['Vector'], 'ShaderNodeTexImage')[0]
    assert Path(difnode.image.filepath).parts.index('haircurly_d.dds') >= 0,  "Diffuse texture"
    
    # UV scale correct
    uvnode = m.node_tree.nodes['UV_Converter']
    TT.assert_eq(uvnode.inputs['Scale U'].default_value, 
                 uvnode.inputs['Scale V'].default_value, 
                 1.0, 
                 "UV Scale")
    
    # Vertex alpha correct
    alpha = bsdf.inputs['Alpha Property'].links[0].from_node
    vertalph = alpha.inputs['Vertex Alpha'].links[0].from_node
    TT.assert_eq(vertalph.attribute_type, 'GEOMETRY', "Geometry type") 
    TT.assert_eq(vertalph.attribute_name, 'VERTEX_ALPHA', "Attribute name")

    # Specular texture connected
    specnode = BD.find_node(bsdf.inputs['Smooth Spec'], 'ShaderNodeTexImage')[0]
    assert Path(specnode.image.filepath).parts.index('haircurly_s.dds') >= 0, "specular"

    # Test export
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # Testing the attributes on the shader node, which is fine because they do get set.
    n1 = pyn.NifFile(testfile)
    n2 = pyn.NifFile(outfile)
    hair1 = n1.shapes[0]
    hair2 = n2.shapes[0]
    TT.assert_eq(hair2.shader.properties.UV_Scale_U, hair1.shader.properties.UV_Scale_U, "UV scale U")
    TT.assert_eq(hair2.properties.hasVertexColors, hair1.properties.hasVertexColors, "Vertex colors")


def TEST_SHADER_SCALE():
    """UV offset and scale are preserved."""
    testfile = TTB.test_file(r"tests\SkyrimSE\maleorchair27.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_SCALE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    n = pyn.NifFile(outfile)
    hair = n.shapes[0]
    assert hair.shader.properties.UV_Scale_U == 1.5, f"Have correct scale: {hair.shader.properties.UV_Scale_U}"


def TEST_SHADER_ALL():
    """Test that all texture slots are imported and exported correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\maleheadAllTextures.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_ALL.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    n = pyn.NifFile(outfile)
    head = n.shapes[0]
    TT.assert_eq_nocase(Path(head.shader.textures['Diffuse']).name, 'MaleHead.dds', 'diffuse texture')
    TT.assert_eq_nocase(Path(head.shader.textures['Normal']).name, 'MaleHead_msn.dds', 'MSN texture')
    TT.assert_eq_nocase(Path(head.shader.textures['SoftLighting']).name, 'MaleHead_sk.dds', 'Subsurface texture')
    TT.assert_eq_nocase(Path(head.shader.textures['HeightMap']).name, 'height.dds', 'Height map texture')
    TT.assert_eq_nocase(Path(head.shader.textures['EnvMap']).name, 'EnvMap.dds', 'Environment map texture')
    TT.assert_eq_nocase(Path(head.shader.textures['EnvMask']).name, 'EnvMask.dds', 'Environment mask texture')
    TT.assert_eq_nocase(Path(head.shader.textures['FacegenDetail']).name, 'Inner.dds', 'Facegen texture')
    TT.assert_eq_nocase(Path(head.shader.textures['Specular']).name, 'MaleHead_S.dds', 'Specular texture')
    TT.assert_eq(len(head.shader.textures), 8, "Head texture count")


def TEST_SHADER_EYE():
    """Test that all texture slots are imported and exported correctly."""
    testfile2 = TTB.test_file(r"tests\SkyrimSE\eyesmale.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_SHADER_EYE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile2)
    bpy.ops.export_scene.pynifly(filepath=outfile2)

    n = pyn.NifFile(outfile2)
    CheckNif(n, source=testfile2)


def TEST_SHADER_LIGHTBULB():
    """Test that effect shader imports correctly."""
    testfile = TTB.test_file(r"tests\FO4\WorkshopLightbulbHanging01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_LIGHTBULB.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.data.objects['BulbGlow:2']
    TT.assert_contains("Fallout 4 Effect", obj.active_material.node_tree.nodes, "Effect shader")
    TT.assert_eq(obj.active_material['BS_Shader_Block_Name'], "BSEffectShaderProperty", "Shader block name")
    assert obj.active_material.node_tree.nodes["Fallout 4 Effect"].inputs['Alpha Property'].is_linked, \
        "Alpha linked"

    bpy.ops.export_scene.pynifly(filepath=outfile)
    n = pyn.NifFile(outfile)
    TT.assert_contains('BulbGlow:2', n.shape_dict, "glow shape")
    TT.assert_contains('Bulb001:3', n.shape_dict, "bulb shape")


def TEST_ANIM_SHADER_GLOW():
    """Glow shader elements and other extra attributes work correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\armor\daedric\daedriccuirass_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_GLOW.nif")

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile)
    glow = bpy.data.objects['MaleTorsoGlow']

    # Check the shader
    shadernodes = glow.active_material.node_tree.nodes
    shader = shadernodes['Material Output'].inputs['Surface'].links[0].from_node
    alpha = shader.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, True, "Alpha Blend")
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, False, "Alpha Test")

    # Check the shader animation is correct.
    action = glow.active_material.node_tree.animation_data.action
    assert action.use_cyclic, f"Cyclic animation: {action.use_cyclic}"

    uv_node = shadernodes['UV_Converter']
    bpy.context.scene.frame_set(0)
    assert uv_node.inputs['Offset V'].default_value == 1, \
        f"V offset starts at 0: {uv_node.inputs['Offset V'].default_value}"
    bpy.context.scene.frame_set(400)
    assert 0.1 < uv_node.inputs['Offset V'].default_value < 0.9, f"V offset is changing: {uv_node.inputs['Offset V'].default_value}"
    bpy.context.scene.frame_set(0)

    ### WRITE ###

    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 export_colors=True,
                                 export_animations=True)

    ### CHECK ###

    # n = pyn.NifFile(testfile)
    nout = pyn.NifFile(outfile)
    CheckNif(nout, source=testfile)


def TEST_ANIM_SHADER_BSLSP():
    """Controllers on BSLightingShaders work correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\voidshade_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIM_SHADER_BSLSP.nif")

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TTB.find_object('head')

    # Check the shader
    shadernodes = head.active_material.node_tree.nodes
    shader = shadernodes['Material Output'].inputs['Surface'].links[0].from_node
    alpha = shader.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, True, "Alpha Blend")
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, False, "Alpha Test")

    # Check the shader animation is correct.
    action = head.active_material.node_tree.animation_data.action
    assert action.use_cyclic, f"Cyclic animation: {action.use_cyclic}"

    uv_node = shadernodes['UV_Converter']
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    TT.assert_eq(uv_node.inputs['Offset V'].default_value, 1, "Offset V")
    bpy.context.scene.frame_set(385)
    bpy.context.view_layer.update()
    assert 0.0 <= uv_node.inputs['Offset V'].default_value <= 0.5, f"V offset is changing: {uv_node.inputs['Offset V'].default_value}"
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    ### WRITE ###

    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 export_colors=True,
                                 export_animations=True)

    ### CHECK ###

    # n = pyn.NifFile(testfile)
    nout = pyn.NifFile(outfile)
    CheckNif(nout, source=testfile)


def Spriggan_LeavesLandedLoop_Check(lllaction):
    # LeavesLandedLoop has correct range
    TT.assert_eq(lllaction.frame_range[0], 1, "Frame start")
    TT.assert_equiv(lllaction.frame_range[1], 50, "Frame end", e=1)

    # Is controlling correct targets
    TT.assert_eq(len(lllaction.slots), 4, "LeavesLandedLoop requires 4 slots")
    scene_objs = BD.ReprObjectCollection.New(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    lllanims = [ad for ad in controller.all_named_animations(scene_objs) if ad.name == 'LeavesLandedLoop']
    llltargets = [ad.target_obj.blender_obj.name for ad in lllanims]
    TT.assert_samemembers(llltargets, 
                          ['SprigganFxHandCovers',
                           'SprigganBodyLeaves', 
                           'SprigganHandLeaves', 
                           'SprigganFxTestUnified:0', 
                           ],
                          "LeavesLandedLoop controlled targets")

    # Fcurve targets correct
    fcurve_targets = [fc.data_path for fc in BD.action_fcurves(lllaction)]
    TT.assert_samemembers(
        fcurve_targets,
        ['nodes["SkyrimShader:Effect"].inputs["Alpha Adjust"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Strength"].default_value'],
        "fcurve data_path values")
    
    # Is controlling SprigganFxHandCovers correctly
    lllhcbag = next((cb for cb in lllaction.layers[0].strips[0].channelbags
                    if 'Alpha Adjust' in cb.fcurves[0].data_path), None)
    TT.assert_eq(len(lllhcbag.fcurves), 1, "SprigganFxHandCovers fcurves")
    TT.assert_eq(len(lllhcbag.fcurves[0].keyframe_points), 3, "SprigganFxHandCovers keyframes")
    TT.assert_equiv(lllhcbag.fcurves[0].keyframe_points[0].co[1], 0, "First keyframe value")
    TT.assert_equiv(lllhcbag.fcurves[0].keyframe_points[-1].co[1], 0, "Last keyframe value")
    
    # Is controlling SprigganBodyLeaves correctly.
    lllfxbag = next((cb for cb in lllaction.layers[0].strips[0].channelbags
                     if 'Alpha Threshold' in cb.fcurves[0].data_path
                        and len(cb.fcurves[0].keyframe_points) == 7), None)
    assert lllfxbag is not None, "Found SprigganBodyLeaves channelbag"
    TT.assert_eq(len(lllfxbag.fcurves), 1, "SprigganBodyLeaves fcurves")
    TT.assert_equiv(lllfxbag.fcurves[0].keyframe_points[0].co[1], 0, "First keyframe value")
    TT.assert_equiv(lllfxbag.fcurves[0].keyframe_points[1].co[1], 70, "Second keyframe value")
    TT.assert_equiv(lllfxbag.fcurves[0].keyframe_points[2].co[1], 0, "Third keyframe value")


def Spriggan_KillFX_Check(kfxaction):
    """Check that the KillFx animation sequence was imported correctly."""
    # KillFX has correct range
    TT.assert_eq(kfxaction.frame_range[0], 1, "Frame start")
    TT.assert_equiv(kfxaction.frame_range[1], 49, "Frame end", e=1)

    # Is controlling correct targets
    TT.assert_eq(len(kfxaction.slots), 4, "KillFX requires 4 slots")

    # Fcurve targets correct
    fcurve_targets = [fc.data_path for fc in BD.action_fcurves(kfxaction)]
    TT.assert_samemembers(
        fcurve_targets,
        ['nodes["SkyrimShader:Effect"].inputs["Alpha Adjust"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Strength"].default_value'],
        "fcurve data_path values")

    # Is controlling SprigganFxHandCovers correctly
    kfxhcbag = [cb for cb in kfxaction.layers[0].strips[0].channelbags
                    if 'Alpha Adjust' in cb.fcurves[0].data_path][0]
    TT.assert_eq(len(kfxhcbag.fcurves), 1, "SprigganFxHandCovers fcurves")
    TT.assert_eq(len(kfxhcbag.fcurves[0].keyframe_points), 2, "KillFX SprigganFxHandCovers keyframes")
    TT.assert_equiv(kfxhcbag.fcurves[0].keyframe_points[0].co[1], 0, "KillFX SprigganFxHandCovers First keyframe value")
    TT.assert_equiv(kfxhcbag.fcurves[0].keyframe_points[-1].co[1], 0, "KillFX SprigganFxHandCovers Last keyframe value")

    # Is controlling SprigganBodyLeaves correctly.
    kfxfxbag = next((cb for cb in kfxaction.layers[0].strips[0].channelbags
                    if len(cb.fcurves) > 1), None)
    TT.assert_eq(len(kfxfxbag.fcurves), 4, "KillFXSprigganBodyLeaves fcurves")
    TT.assert_contains("Emission Strength", kfxfxbag.fcurves[3].data_path, "KillFX SprigganBodyLeaves controlled property")
    TT.assert_eq(len(kfxfxbag.fcurves[3].keyframe_points), 2, "KillFX SprigganBodyLeaves keyframes")
    TT.assert_equiv(kfxfxbag.fcurves[3].keyframe_points[0].co[1], 8, "KillFX SprigganBodyLeaves First keyframe value")
    TT.assert_equiv(kfxfxbag.fcurves[3].keyframe_points[1].co[1], 0, "KillFX SprigganBodyLeaves Second keyframe value")



    # scene_objs = BD.ReprObjectCollection.New(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    # kfxanims = [ad for ad in controller.all_named_animations(scene_objs) if ad.name == 'KillFX']
    # kfxtargets = [ad.target_obj.blender_obj.name for ad in kfxanims]
    # TT.assert_samemembers(kfxtargets, 
    #                       ['SprigganFxHandCovers',
    #                        'SprigganBodyLeaves', 
    #                        'SprigganHandLeaves', 
    #                        'SprigganFxTestUnified:0', 
    #                        ],
    #                       "KillFX controlled targets")
    
    # # Is controlling SprigganFxHandCovers correctly
    # kfxhcanim = next(ad for ad in kfxanims if ad.target_obj.blender_obj.name == 'SprigganFxHandCovers')
    # kfxhcbag = kfxaction.layers[0].strips[0].channelbag(kfxhcanim.slot)
    # TT.assert_eq(len(kfxhcbag.fcurves), 1, "SprigganFxHandCovers fcurves")
    # TT.assert_contains("Alpha Adjust", kfxhcbag.fcurves[0].data_path, "KillFX SprigganFxHandCovers controlled property")
    # TT.assert_eq(len(kfxhcbag.fcurves[0].keyframe_points), 2, "KillFX SprigganFxHandCovers keyframes")
    # TT.assert_equiv(kfxhcbag.fcurves[0].keyframe_points[0].co[1], 0, "KillFX SprigganFxHandCovers First keyframe value")
    # TT.assert_equiv(kfxhcbag.fcurves[0].keyframe_points[-1].co[1], 0, "KillFX SprigganFxHandCovers Last keyframe value")
    
    # # Is controlling SprigganBodyLeaves correctly.
    # kfxfxanim = next(ad for ad in kfxanims if ad.target_obj.blender_obj.name == 'SprigganBodyLeaves')
    # kfxfxbag = kfxaction.layers[0].strips[0].channelbag(kfxhcanim.slot)
    # TT.assert_eq(len(kfxfxbag.fcurves), 1, "KillFXSprigganBodyLeaves fcurves")
    # TT.assert_contains("Alpha Threshold", kfxfxbag.fcurves[0].data_path, "KillFX SprigganBodyLeaves controlled property")
    # TT.assert_eq(len(kfxfxbag.fcurves[0].keyframe_points), 7, "KillFX SprigganBodyLeaves keyframes")
    # TT.assert_equiv(kfxfxbag.fcurves[0].keyframe_points[0].co[1], 9.444294, "KillFX SprigganBodyLeaves First keyframe value")
    # TT.assert_equiv(kfxfxbag.fcurves[0].keyframe_points[1].co[1], 0.000000, "KillFX SprigganBodyLeaves Second keyframe value")
    # TT.assert_equiv(kfxfxbag.fcurves[0].keyframe_points[2].co[1], 131.984894, "KillFX SprigganBodyLeaves Third keyframe value")


def TEST_ANIM_SHADER_SPRIGGAN():
    """Test that the special spriggan elements work correctly."""
    # Spriggan with limited controllers
    testfile = TTB.test_file(r"tests\Skyrim\spriggan.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIM_SHADER_SPRIGGAN.nif")

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Have a glow map
    bod = TTB.find_object('SprigganFxTestUnified:0')
    assert len([x for x in bod.active_material.node_tree.nodes 
                if x.type=='TEX_IMAGE' and x.image and 'spriggan_g' in x.image.name.lower()]
                ), f"Spriggan loaded with glow map"
    
    # Have all animations
    # act_names = [a.name.split('|') for a in bpy.data.actions if a.name.startswith('ANIM|')]
    expected_animations = [
        'LeavesLandedLoop',
        'LeavesScared',
        'LeavesAwayLoop',
        'LeavesLanding',
        'LeavesToHand',
        'LeavesOnHandLoop',
        'LeavesOffHand',
        'LeavesToHandDark',
        'LeavesOnHandDarkLoop',
        'LeavesOffHandDark',
        'KillFX',]
    TT.assert_samemembers(bpy.data.actions.keys(), expected_animations, "Animation names")

    Spriggan_KillFX_Check(bpy.data.actions['KillFX'])
    Spriggan_LeavesLandedLoop_Check(bpy.data.actions['LeavesLandedLoop'])

    # Can properly apply KillFX 
    controller.apply_animation("KillFX", bpy.context.scene)
    handleaves = TTB.find_object("SprigganHandLeaves")
    bpy.context.scene.frame_current = 1
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    TT.assert_equiv(handleaves.active_material.node_tree.nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value,
                    255,
                    "Alpha Threshold at frame 1")
    bpy.context.scene.frame_current = 40
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    TT.assert_equiv(handleaves.active_material.node_tree.nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value,
                    255,
                    "Alpha Threshold at frame 40")

    # Can properly apply LeavesLandedLoop 
    controller.apply_animation("LeavesLandedLoop", bpy.context.scene)
    bpy.context.scene.frame_current = 1
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    fxbody = TTB.find_object("SprigganFxTestUnified:0")
    TT.assert_equiv(fxbody.active_material.node_tree.nodes["SkyrimShader:Default"]
                        .inputs["Emission Strength"].default_value,
                    8,
                    "Emission Strength at frame 1",
                    e=0.1)
    bpy.context.scene.frame_current = 9
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    TT.assert_equiv(fxbody.active_material.node_tree.nodes["SkyrimShader:Default"]
                        .inputs["Emission Strength"].default_value,
                    6,
                    "Emission Strength at frame 9",
                    e=0.1)
    bpy.context.scene.frame_current = 18
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    TT.assert_equiv(fxbody.active_material.node_tree.nodes["SkyrimShader:Default"]
                        .inputs["Emission Strength"].default_value,
                    13.1765,
                    "Emission Strength at frame 18",
                    e=0.1)

    
    ### WRITE ###
    
    bpy.ops.export_scene.pynifly(filepath=outfile)
    testnif = pyn.NifFile(testfile)
    testbod = testnif.shape_dict['SprigganFxTestUnified:0']
    nifout = pyn.NifFile(outfile)
    bodout = nifout.shape_dict['SprigganFxTestUnified:0']
    assert bodout.shader.properties.shaderflags2_test(nifdefs.ShaderFlags2.GLOW_MAP), \
        f"Glow map flag is set"
    assert bodout.shader.textures['Glow'].lower().endswith('spriggan_g.dds')
    leavesout = nifout.shape_dict['SprigganBodyLeaves']
    TT.assert_eq(leavesout.shader.blockname, 'BSEffectShaderProperty', f"Leaf shader block type")

    outcm:pyn.NiControllerManager = nifout.root.controller
    TT.assert_equiv(outcm.properties.frequency, 1.0, "Controller Manager frequency")
    TT.assert_seteq([s for s in outcm.sequences], expected_animations, "Sequence names")

    for csname, cs in outcm.sequences.items():
        for cb in cs.controlled_blocks:
            assert cb.node_name is not None and cb.node_name != '', f"Have actual node name for sequence {csname}"    
            assert cb.property_type is not None and cb.property_type != '', f"Have actual property type for sequence {csname}"    
            assert cb.controller_type is not None and cb.controller_type != '', f"Have actual controller type for sequence {csname}"
            assert cb.interpolator.id != pyn.NODEID_NONE and cb.interpolator.id != 0, f"Have interpolator for sequence {csname}"
            assert cb.controller.id != pyn.NODEID_NONE and cb.controller.id != 0, f"Have controller for sequence {csname}"

    lllseq:pyn.NiControllerSequence = outcm.sequences['LeavesLandedLoop']
    bodyleavescb:pyn.ControllerLink = [b for b in lllseq.controlled_blocks 
                                       if b.node_name == 'SprigganBodyLeaves'][0]
    ctlr = bodyleavescb.controller
    isinstance(ctlr, pyn.BSNiAlphaPropertyTestRefController), f"Have alpha controller"


def TEST_SHADER_ALPHA():
    """Shader attributes are read and turned into Blender shader nodes"""
    # Alpha property is translated into equivalent Blender nodes.
    #
    # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the
    # suffix.

    fileAlph = TTB.test_file(r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_ALPH.nif")

    bpy.ops.import_scene.pynifly(filepath=fileAlph)
    
    nifAlph = pyn.NifFile(fileAlph)
    furshape = nifAlph.shape_dict["tail_fur"]
    tail = bpy.data.objects["tail_fur"]
    TT.assert_contains('SkyrimShader:Default', tail.active_material.node_tree.nodes.keys(), "Shader")
    bsdf = tail.active_material.node_tree.nodes['SkyrimShader:Default']
    assert bsdf.inputs['Normal'].is_linked, f"Have normal map"
    TT.assert_contains('Diffuse_Texture', tail.active_material.node_tree.nodes.keys(), "Diffuse texture node")
    alpha = bsdf.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, True, "Alpha Test")
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, False, "Alpha Blend")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifCheck = pyn.NifFile(outfile)
    checkfurshape = nifCheck.shape_dict["tail_fur"]
    
    TT.assert_seteq(checkfurshape.shader.textures.keys(), furshape.shader.textures.keys(), "Textures")
    for k in checkfurshape.shader.textures:
        TT.assert_eq(checkfurshape.shader.textures[k], furshape.shader.textures[k], f"{k} texture")
    diffs = checkfurshape.shader.properties.compare(furshape.shader.properties)
    assert not diffs, f"No difference in properties: {diffs}"

    assert checkfurshape.has_alpha_property, f"Have alpha property"
    TT.assert_eq(checkfurshape.alpha_property.properties.flags, furshape.alpha_property.properties.flags, 
                 "Alpha flags")
    TT.assert_eq(checkfurshape.alpha_property.properties.threshold, furshape.alpha_property.properties.threshold, 
                 "Alpha threshold")
    

def TEST_SHADER_3_3():
    """Shader attributes are read and turned into Blender shader nodes"""
    # This older shader connects to the Principled BSDF "Subsurface" import port which
    # went away in V4.0, so it ain't never gonna work.
    if bpy.app.version[0] >= 4: return

    TTB.append_from_file("FootMale_Big", True, r"tests\SkyrimSE\feet.3.3.blend", 
                     r"\Object", "FootMale_Big")
    bpy.ops.object.select_all(action='DESELECT')
    obj = TTB.find_shape("FootMale_Big")

    print("## Shader attributes are written on export")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_3_3.nif")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = pyn.NifFile(outfile)
    
    shaderch = nifcheckSE.shapes[0].shader
    assert shaderch.textures['Diffuse'] == r"textures\actors\character\male\MaleBody_1.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['Diffuse']}'"
    assert shaderch.textures['Normal'] == r"textures\actors\character\male\MaleBody_1_msn.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['Normal']}'"
    assert shaderch.textures["SoftLighting"] == r"textures\actors\character\male\MaleBody_1_sk.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['SoftLighting']}'"
    assert shaderch.textures['Specular'] == r"textures\actors\character\male\MaleBody_1_S.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['Specular']}'"


def TEST_SHADER_EFFECT():
    """BSEffectShaderProperty attributes are read & written correctly."""
    testfile = TTB.test_file(r"tests\Skyrim\blackbriarchalet_test.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_EFFECT.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    CheckNif(nifcheck, source=testfile)
    # glow = nif.shape_dict["L2_WindowGlow"]
    # glowcheck = nifcheck.shape_dict["L2_WindowGlow"]

    # assert glow.blockname == glowcheck.blockname == "BSLODTriShape", \
    #     f"Created a LOD shape: {glowcheck.blockname}"
    # assert glow.properties.flags == glowcheck.properties.flags, f"Have correct flags: {glowcheck.properties.flags}"
    # assert glow.shader.blockname == glowcheck.shader.blockname, f"Have correct shader: {glowcheck.shader.blockname}"
    # ### Currently writing VERTEX_ALPHA even tho it wasn't originally set.
    # assert glow.shader.properties.Shader_Flags_1 == glowcheck.shader.properties.Shader_Flags_1, \
    #     f"Have correct shader flags 1: {pyn.ShaderFlags1(glow.shader.properties.Shader_Flags_1).fullname}"
    # assert glow.shader.properties.Shader_Flags_2 == glowcheck.shader.properties.Shader_Flags_2, \
    #     f"Have correct shader flags 1: {pyn.ShaderFlags1(glow.shader.properties.Shader_Flags_2).fullname}"
    # assert glow.shader.properties.LightingInfluence == glowcheck.shader.properties.LightingInfluence, \
    #     f"Have correct lighting influence: {glowcheck.shader.properties.LightingInfluence}"

    # win = nif.shape_dict["BlackBriarChalet:7"]
    # wincheck = nifcheck.shape_dict["BlackBriarChalet:7"]
    # assert BD.VNearEqual(win.shader.properties.parallaxInnerLayerTextureScale,
    #                      wincheck.shader.properties.parallaxInnerLayerTextureScale), \
    #     f"Have correct parallax: {wincheck.shader.properties.parallaxInnerLayerTextureScale}"
    # assert r"textures\cubemaps\ShinyGlass_e.dds" \
    #     == win.shader.textures['EnvMap'] == wincheck.shader.textures['EnvMap'], \
    #     f"Have correct envronment map: {wincheck.shader.textures['EnvMap']}"
    # assert r"textures\architecture\riften\RiftenWindowInner01.dds" \
    #     == win.shader.textures['InnerLayer'] == wincheck.shader.textures['InnerLayer'], \
    #     f"Have correct InnerLayer: {wincheck.shader.textures['InnerLayer']}"
    

def TEST_SHADER_EFFECT_GLOWINGONE():
    """BSEffectShaderProperty attributes are read & written correctly."""
    testfile = TTB.test_file(r"tests\FO4\glowingoneTEST.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_EFFECT_GLOWINGONE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=False)

    # Check we have segments and subsegments.
    body = TTB.find_object("GlowingOneBody:0")
    TT.assert_contains('FO4 Seg 006 | 008 | Ghoul Foot.L', body.vertex_groups, "Foot segment")

    # Simplify.
    
    # # Have to export the root object for the flags to carry over.
    BD.ObjectSelect([o for o in bpy.context.scene.objects if 'pynRoot' in o], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)

    # Make sure root node flags got carried over.
    TT.assert_eq(nifcheck.rootNode.properties.flags,
                 nif.rootNode.properties.flags,
                 "Root node flags")

    # The 'flash' body has an effect shader with alpha. The alpha node uses blending, but
    # with peculiar settings that seem to mimic translucency even tho the diffuse alpha is
    # opaque.
    glow = nif.shape_dict["GlowingOneBodyFlash:1"]
    glowcheck = nifcheck.shape_dict["GlowingOneBodyFlash:1"]

    # Check the shader.
    TT.assert_eq(glow.blockname, glowcheck.blockname, "BSSubIndexTriShape", "Shape type")
    TT.assert_eq(glow.properties.flags, glowcheck.properties.flags, "Shape flags")
    TT.assert_eq(glow.shader.blockname, glowcheck.shader.blockname, "Shader type")
    TT.assert_eq(glow.shader.properties.sourceTexture.upper(), 
                 glowcheck.shader.properties.sourceTexture.upper(), 
                 "Source texture")
    TT.assert_eq(glow.shader.properties.greyscaleTexture.upper(), 
                 glowcheck.shader.properties.greyscaleTexture.upper(), 
                 "Grayscale texture")
    
    # Shader knows it has a controller.
    assert glowcheck.shader.controller is not None, f"Shader has a controller"
    
    # Check the alpha
    alphacheck = glowcheck.alpha_property
    TT.assert_eq(alphacheck.properties.flags, 4109, "Alpha flags")

    # "PartA" sequence has a color controller that affects the emissive color of
    # "GlowingOneGlowFXstreak:0". (Which is not emissive color at all--emissive color is
    # used for the palette color of the greyscale texture.)
    cm:pyn.NiControllerManager = nifcheck.rootNode.controller
    seq:pyn.NiControllerSequence = cm.sequences["partA"]
    cblist = [cb for cb in seq.controlled_blocks if cb.node_name == "GlowingOneGlowFXstreak:0"]
    TT.assert_samemembers([b.controller_type for b in cblist], 
                          ["BSEffectShaderPropertyColorController", 
                           "BSEffectShaderPropertyFloatController", 
                           "BSEffectShaderPropertyFloatController"],
                          "PartA Controller types")
    cb = [b for b in cblist if b.controller_type == "BSEffectShaderPropertyColorController"][0]
    
    # Interpolator data has reasonable values, including forward/back values.
    dat = cb.interpolator.data
    dat1 = dat.keys[1]
    TT.assert_equiv(dat1.time, 0.3, "Key 1 time")
    TT.assert_equiv(dat1.value[0], 0.894199, "Key 1 value")
    TT.assert_equiv(dat1.backward[0], -0.151786, "Key 1 backward", e=0.1)


def TEST_TEXTURE_PATHS():
    """Texture paths are correctly resolved"""
    testfile = TTB.test_file(r"tests\SkyrimSE\circletm1.nif")
    txtdir = TTB.test_file(r"tests\SkyrimSE")

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
    circlet = TTB.find_shape('M1:4')
    mat = circlet.active_material
    bsdf = mat.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
    diffuse = shader_io.get_image_filepath(bsdf.inputs['Diffuse'])
    TT.assert_eq_nocase(Path(diffuse).name, 'Circlet.dds', f"diffuse texture path")
    norm = shader_io.get_image_filepath(bsdf.inputs['Normal'])
    TT.assert_eq_nocase(Path(norm).name, 'Circlet_n.png', "normal texture path")


def TEST_CAVE_GREEN():
    """Cave nif can be exported correctly"""
    # Regression: Make sure the transparency is exported on this nif.
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\dungeons\caves\green\smallhall\caveghall1way01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_CAVE_GREEN.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    wall1 = bpy.data.objects["CaveGHall1Way01:2"]
    mat1 = wall1.active_material
    bsdf = mat1.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
    # mix1 = bsdf.inputs['Diffuse'].links[0].from_node
    # try:
    #     # Blender 3.5
    #     diff1 = mix1.inputs[6].links[0].from_node
    # except:
    #     # Blender 3.1
    #     diff1 = mix1.inputs['Color1'].links[0].from_node

    diff1 = BD.find_node(bsdf.inputs['Diffuse'], 'ShaderNodeTexImage')[0]
    assert diff1.image.filepath.lower()[0:-4].endswith("cavebasewall01"), \
        f"Have correct wall diffuse: {diff1.image.filepath}"
    
    assert bsdf.inputs['Vertex Color'].is_linked, "Vertex Color linked to node"
    n = BD.find_node(bsdf.inputs['Vertex Color'], 'ShaderNodeAttribute')[0]
    assert n.attribute_name == "Col", f"Using vertex colors"
    assert n.attribute_type == "GEOMETRY", f"Using vertex colors"

    roots = TTB.find_shape("L2_Roots:5")

    bpy.ops.object.select_all(action='DESELECT')
    roots.select_set(True)
    bpy.ops.object.duplicate()

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheck = pyn.NifFile(outfile)
    rootscheck = nifcheck.shape_dict["L2_Roots:5"]
    assert rootscheck.has_alpha_property, f"Roots have alpha: {rootscheck.has_alpha_property}"
    assert rootscheck.shader.properties.shaderflags2_test(nifdefs.ShaderFlags2.VERTEX_COLORS), \
        f"Have vertex colors: {rootscheck.shader.properties.shaderflags2_test(nifdefs.ShaderFlags2.VERTEX_COLORS)}"


def TEST_POT():
    """Test that pot shaders doesn't throw an error; also collisions"""
    testfile = TTB.test_file(r"tests\SkyrimSE\spitpotopen01.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)
    assert 'ANCHOR:0' in bpy.data.objects.keys()

    anchor = bpy.data.objects['ANCHOR']
    anchor_sh = anchor.constraints[0].target
    assert anchor_sh, "Have collision shape for anchor"

    anchor_z = anchor.matrix_world.translation.z
    anchor_sh_z = anchor_sh.matrix_world.translation.z
    assert BD.NearEqual(anchor_z, anchor_sh_z), f"Near equal z locations: {anchor_z} == {anchor_sh_z}"

    hook = bpy.data.objects['L1_Hook']
    hook_sh = hook.constraints[0].target
    assert hook_sh, "Have collision shape for hook"

    hook_z = hook.matrix_world.translation.z
    hook_sh_z = hook_sh.matrix_world.translation.z
    assert BD.NearEqual(hook_z, hook_sh_z), f"Hook collision near hook: {hook_z} > {hook_sh_z}"
    for v in hook_sh.data.vertices:
        assert v.co.z < 0, f"Hook verts all below hook anchor point: {v.co}"


def TEST_BRICKWALL():
    """FO4 brick wall with greyscale, wild UV."""
    testfile = TTB.test_file(r"tests\FO4\Meshes\Architecture\DiamondCity\DExt\DExBrickColumn01.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)
    # This nif has clamped UVs in the nif, but the materials says they wrap. Make sure they wrap.
    TT.assert_eq(bpy.data.materials["DExBrickColumn01:0.Mat"].node_tree.nodes["UV_Converter"].inputs[4].default_value,
                    1, "UV S is clamped")
    assert bpy.data.materials["DExBrickColumn01:0.Mat"].node_tree.nodes["Fallout 4 MTS - Greyscale To Palette Vector"], "Have palette node"


def TEST_NOT_FB():
    """Test that nif that looked like facebones skel can be imported"""
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

    testfile = TTB.test_file(r"tests\FO4\6SuitM_Test.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TTB.find_shape("body_Cloth:0")
    minz = min(v.co.z for v in body.data.vertices)
    assert minz > -130, f"Min z location not stretched: {minz}"


def TEST_MULTI_IMP():
    """Test that importing multiple hair parts doesn't mess up"""
    # Fact is, this DOES mess up. we can import more than one nif at a time, which 
    # is what we're trying to test. But we might be importing Skyrim's _0 and _1 weight
    # bodyparts, so we'd like them to load as shape keys if possible. BUT two of these
    # nifs have the same vert count, so they get loaded as shape keys tho they shouldn't.
    #
    # TODO: Decide if this is worth fixing, and how. Maybe key off the _0 and _1 file 
    # extensions?

    testfile1 = TTB.test_file(r"tests\FO4\FemaleHair25.nif")
    testfile2 = TTB.test_file(r"tests\FO4\FemaleHair25_Hairline1.nif")
    testfile3 = TTB.test_file(r"tests\FO4\FemaleHair25_Hairline2.nif")
    testfile4 = TTB.test_file(r"tests\FO4\FemaleHair25_Hairline3.nif")
    bpy.ops.import_scene.pynifly(files=[{"name": testfile1}, 
                                        {"name": testfile2}, 
                                        {"name": testfile3}, 
                                        {"name": testfile4}])
    h = TTB.find_shape("FemaleHair25:0")
    assert h.location.z > 120, f"Hair fully imported: {h.location}"


def TEST_WELWA():
    """Can read and write shape with unusual skeleton"""
    # The Welwa (bear skeleton) has bones similar to human bones--but they can't be
    # treated like the human skeleton. "Rename bones" is false on import and should be
    # remembered on the mesh and armature for export, so it's not explicitly specified on
    # export.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\welwa.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_WELWA.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_rename_bones=False, do_create_bones=False)

    welwa = TTB.find_shape("111")
    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    lipbone = skel.data.bones['NPC UpperLip']
    assert NT.VNearEqual(lipbone.matrix_local.translation, (0, 49.717827, 161.427307)), f"Found {lipbone.name} at {lipbone.matrix_local.translation}"
    spine1 = skel.data.bones['NPC Spine1']
    assert NT.VNearEqual(spine1.matrix_local.translation, (0, -50.551056, 64.465019)), f"Found {spine1.name} at {spine1.matrix_local.translation}"

    # Should remember that bones are not to be renamed.
    bpy.ops.object.select_all(action='DESELECT')
    welwa.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)

    assert "NPC Pelvis [Pelv]" not in nifcheck.nodes, f"Human pelvis name not written: {nifcheck.nodes.keys()}"


def TEST_MUTANT():
    """Test that the supermutant body imports correctly the *second* time"""
    testfile = TTB.test_file(r"tests/FO4/testsupermutantbody.nif")

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
    """Test that hand mesh doesn't throw an error"""
    # When there are problems with the mesh we don't want to crash and burn.
    outfile = TTB.test_file(r"tests/Out/TEST_EXPORT_HANDS.nif")

    TTB.append_from_file("SupermutantHands", True, r"tests\FO4\SupermutantHands.blend", r"\Object", "SupermutantHands")
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = bpy.data.objects["SupermutantHands"]
    test_loghandler.expect_error = logging.ERROR
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    assert os.path.exists(outfile)


def TEST_PARTITION_ERRORS():
    """Partitions with errors raise errors"""
    if bpy.app.version[0] < 3: return

    # Partitions have to cleanly separate the faces into non-overlapping parts of the
    # shape. If that's not the case, we return an error.
    #
    # Doesn't run on 2.x, don't know why
    testfile = TTB.test_file(r"tests/Out/TEST_TIGER_EXPORT.nif")

    TTB.append_from_file("SynthMaleBody", True, r"tests\FO4\SynthBody02.blend", r"\Object", "SynthMaleBody")

    # Partitions must divide up the mesh cleanly--exactly 1 partition per tri
    bpy.context.view_layer.objects.active = bpy.data.objects["SynthMaleBody"]
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='FO4')
    
    # assert len(exporter.warnings) > 0, f"Error: Export should have generated warnings: {exporter.warnings}"
    # print(f"Exporter warnings: {exporter.warnings}")
    assert BD.MULTIPLE_PARTITION_GROUP in bpy.data.objects["SynthMaleBody"].vertex_groups, "Error: Expected group to be created for tris in multiple partitions"


def TEST_SHEATH():
    """Extra data nodes are imported and exported"""
    # The sheath has extra data nodes for Havok. These are imported as Blender empty
    # objects, and can be exported again.

    testfile = TTB.test_file(r"tests/Skyrim/sheath_p1_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHEATH.nif")
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
    """Extra data nodes are imported and exported"""
    # Feet have extra data nodes that are children of the feet mesh. This parent/child
    # relationship must be preserved on import and export.
    testfile = TTB.test_file(r"tests/SkyrimSE/caninemalefeet_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FEET.nif")

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
    """Test that scale factors happen correctly"""

    testfile = TTB.test_file(r"tests\Skyrim\statuechampion.nif")
    testout = TTB.test_file(r"tests\Out\TEST_SCALING.nif")
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
    assert NT.NearEqual(checkfoot.transform.scale, 1.0), f"ERROR: Foot scale not correct: {checkfoot.transform.scale}"

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
    """Can scale simple object with furniture markers"""
    testfile = TTB.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SCALING_OBJ.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)

    bench = bpy.context.object
    bbmin, bbmax = TTB.get_obj_bbox(bench, worldspace=True)
    assert bbmax[0] < 6.5, f"Bench is scaled down: {bbmax}" 
    assert bbmin[0] > -6.5, f"Bench is scaled down: {bbmin}" 
    # bmax = max([v.co.z for v in bench.data.vertices])
    # bmin = min([v.co.z for v in bench.data.vertices])
    # assert NT.VNearEqual(bench.scale, (1,1,1)), f"Bench scale factor is 1: {bench.scale}"
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
    """Can export objects with uniform scaling"""

    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TestCube"
    cube.scale = Vector((4.0, 4.0, 4.0))

    testfile = TTB.test_file(r"tests\Out\TEST_UNIFORM_SCALE.nif")
    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='SKYRIM')

    nifcheck = pyn.NifFile(testfile)
    shapecheck = nifcheck.shapes[0]
    assert NT.NearEqual(shapecheck.transform.scale, 4.0), f"Shape scaled x4: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert NT.VNearEqual(map(abs, v), [1,1,1]), f"All vertices at unit position: {v}"


def TEST_NONUNIFORM_SCALE():
    """Can export objects with non-uniform scaling"""

    testfile = TTB.test_file(r"tests\Out\TEST_NONUNIFORM_SCALE.nif")
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TestCube"
    cube.scale = Vector((2.0, 4.0, 8.0))

    bpy.ops.export_scene.pynifly(filepath=testfile, target_game='SKYRIM')

    nifcheck = pyn.NifFile(testfile)
    shapecheck = nifcheck.shapes[0]
    assert NT.NearEqual(shapecheck.transform.scale, 1.0), f"Nonuniform scale exported in verts so scale is 1: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert not NT.VNearEqual(map(abs, v), [1,1,1]), f"All vertices scaled away from unit position: {v}"


def TEST_TRIP_SE():
    """Bodypart tri extra data and file are written on export"""
    # Special bodytri files allow for Bodyslide or FO4 body morphing.
    outfile = TTB.test_file(r"tests/Out/TEST_TRIP_SE.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_TRIP_SE_1.nif")
    outfiletrip = TTB.test_file(r"tests/Out/TEST_TRIP_SE.tri")

    TTB.append_from_file("Penis_CBBE", True, r"tests\SkyrimSE\HorseFuta.blend", 
                     r"\Object", "Penis_CBBE")
    bpy.ops.object.select_all(action='DESELECT')
    obj = TTB.find_shape("Penis_CBBE")
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
    """Body tri extra data and file are written on export"""
    outfile = TTB.test_file(r"tests/Out/TEST_TRIP.nif")
    outfiletrip = TTB.test_file(r"tests/Out/TEST_TRIP.tri")

    TTB.append_from_file("BaseMaleBody", True, r"tests\FO4\BodyTalk.blend", r"\Object", "BaseMaleBody")
    bpy.ops.object.select_all(action='DESELECT')
    body = TTB.find_shape("BaseMaleBody")
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
    """Can read & write vertex colors"""
    # Blender's vertex color layers are used to define vertex colors in the nif.
    outfile = TTB.test_file(r"tests/Out/TEST_COLORS_Plane.nif")
    TTB.export_from_blend(r"tests\FO4\VertexColors.blend", "Plane",
                      "FO4", outfile)

    nif3 = pyn.NifFile(outfile)
    assert len(nif3.shapes[0].colors) > 0, f"Expected color layers, have: {len(nif3.shapes[0].colors)}"
    cd = nif3.shapes[0].colors
    assert cd[0] == (0.0, 1.0, 0.0, 1.0), f"First vertex found: {cd[0]}"
    assert cd[1] == (1.0, 1.0, 0.0, 1.0), f"Second vertex found: {cd[1]}"
    assert cd[2] == (1.0, 0.0, 0.0, 1.0), f"Second vertex found: {cd[2]}"
    assert cd[3] == (0.0, 0.0, 1.0, 1.0), f"Second vertex found: {cd[3]}"


def TEST_COLORS2():
    """Can read & write vertex colors"""
    testfile = TTB.test_file(r"tests/FO4/HeadGear1.nif")
    testfileout = TTB.test_file(r"tests/Out/TEST_COLORS2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert obj.data.attributes['Col'].domain == 'POINT', f"Have vertec colors in Blender"
    colordata = obj.data.attributes['Col'].data
    targetv = TTB.find_vertex(obj.data, (1.62, 7.08, 0.37))
    assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
    assert colordata[targetv].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[targetv].color[:]}"
    # for lp in obj.data.loops:
    #     if lp.vertex_index == targetv:
    #         assert colordata[lp.index].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[lp.index].color[:]}"

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game="FO4")

    nif2 = pyn.NifFile(testfileout)
    assert nif2.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not reread correctly: {nif2.shapes[0].colors[0]}"
    assert nif2.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0), f"Color 561 not reread correctly: {nif2.shapes[0].colors[561]}"


def TEST_COLORS3():
    """Can read & write vertex colors & alpha"""
    testfile = TTB.test_file(r"tests\FO4\FemaleHair05_Hairline.nif")
    # testfile = TTB.test_file(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\Hair\Male\Hair26_Hairline.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLORS3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    nif = pyn.NifFile(testfile)
    c1229_nif = nif.shapes[0].colors[1229]
    blend_alphamap = bpy.context.object.data.attributes['VERTEX_ALPHA']
    c1229_blend = blend_alphamap.data[1229].color
    TT.assert_equiv(c1229_blend[0], c1229_nif[3], "Vertex alpha", e=1.0/255.0)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nif2 = pyn.NifFile(outfile)
    colors = nif.shapes[0].colors
    colors2 = nif2.shapes[0].colors
    for i in range(0, len(colors)):
        TTB.test_floatarray(f"color {i}", colors[i], colors2[i], epsilon=(1.0/255.0))
        # assert colors[i] == colors2[i], f"Have correct colors, {colors[i]} == {colors2[i]}"


def TEST_NEW_COLORS():
    """Can write vertex colors that were created in blender"""
    # Regression: There have been issues dealing with how Blender handles colors.
    outfile = TTB.test_file(r"tests/Out/TEST_NEW_COLORS.nif")

    TTB.export_from_blend(r"tests\SKYRIMSE\BirdHead.blend",
                      "HeadWhole",
                      "SKYRIMSE",
                      outfile)

    nif = pyn.NifFile(outfile)
    shape = nif.shapes[0]
    assert shape.colors, f"Have colors in shape {shape.name}"
    assert shape.colors[10] == (1.0, 1.0, 1.0, 1.0), f"Colors are as expected: {shape.colors[10]}"
    assert shape.shader.properties.shaderflags2_test(pyn.ShaderFlags2.VERTEX_COLORS), \
        f"ShaderFlags2 vertex colors set: {pyn.ShaderFlags2(shape.shader.Shader_Flags_2).fullname}"


def TEST_COLOR_CUBES():
    """Can write vertex colors that were created in blender"""
    # Two shapes with the same name, both with vertex colors. Exporter should not get
    # confused.
    blendfile = TTB.test_file(r"tests\SKYRIM\ColorCubes.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_COLOR_CUBES.nif")

    bpy.ops.wm.append(filepath=blendfile,
                        directory=blendfile + r"\Object",
                        filename="Cube")
    bpy.ops.wm.append(filepath=blendfile,
                        directory=blendfile + r"\Object",
                        filename="Cube.001")
    
    BD.ObjectSelect(bpy.context.scene.objects, active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nif = pyn.NifFile(outfile)

    # Find the cube at the origin
    bluegreen = next(s for s in nif.shapes if Vector(s.transform.translation) == Vector((0,0,0)))
    redgreen = next(s for s in nif.shapes if Vector(s.transform.translation) != Vector((0,0,0)))
    
    assert bluegreen.colors
    for c in bluegreen.colors:
        assert c == (0, 0, 1, 1) or c == (0, 1, 0, 1), f"Color is red or green: {c}"
    assert redgreen.colors
    for c in redgreen.colors:
        assert c == (1, 0, 0, 1) or c == (0, 1, 0, 1), f"Color is red or green: {c}"
        

def TEST_NOTEXTURES():
    """Can read a nif with no texture paths."""
    testfile = TTB.test_file(r"tests/FO4/HeadGear1 - NoTextures.nif")
    testfileout = TTB.test_file(r"tests/Out/TEST_NOTEXTURES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert obj.data.attributes['Col'].domain == 'POINT', "Have vertex colors"
    colordata = obj.data.attributes['Col'].data
    targetv = TTB.find_vertex(obj.data, (1.62, 7.08, 0.37))
    assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
    assert colordata[targetv].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[targetv].color[:]}"


def TEST_VERTEX_COLOR_IO():
    """Vertex colors can be read and written"""
    # On heads, vertex alpha and diffuse alpha work together to determine the final
    # transparency the user sees. We set up Blender shader nodes to provide the same
    # effect.
    testfile = TTB.test_file(r"tests\FO4\FemaleEyesAO.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_VERTEX_COLOR_IO.nif", output=1)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    eyes = TTB.find_shape("FemaleEyesAO:0")
    assert eyes.active_material["Shader_Flags_2"].find("VERTEX_COLORS") >= 0, \
        f"Eyes have colors: {eyes.active_material['Shader_Flags_2']}"
    
    if bpy.app.version >= (3, 5, 0):
        # Color data handled differently in older versions
        colors = eyes.data.color_attributes.active_color.data
        max_r = max(c.color[0] for c in colors)
        min_r = min(c.color[0] for c in colors)
        assert max_r == 0, f"Have no white verts: {max_r}"
        assert min_r == 0, f"Have some black verts: {min_r}"

        # BSEffectShaderProperty is assumed to use the alpha channel if the shape has
        # transparency, whether or not ShaderFlagflag is set. Alpha is represented as ordinary
        # color on the VERTEX_ALPHA color attribute.
        colors = eyes.data.color_attributes['VERTEX_ALPHA'].data
        max_a = max(c.color[0] for c in colors)
        min_a = min(c.color[0] for c in colors)
        assert math.isclose(max_a, 1.0, abs_tol=0.001), f"Have some opaque verts: {max_a}"
        assert math.isclose(min_a, 0, abs_tol=0.001), f"Have some transparent verts: {min_a}"

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
    """Import & export shape with vertex alpha values"""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\actors\character\character assets\maleheadkhajiit.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_VERTEX_ALPHA_IO.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)

    head = bpy.context.object
    nodes = head.active_material.node_tree.nodes
    shader = nodes["SkyrimShader:Face"]
    assert shader, f"Found shader"
    diffuse = BD.find_node(shader.inputs["Diffuse"], "ShaderNodeTexImage")[0]
    TT.assert_eq(diffuse.bl_idname, "ShaderNodeTexImage", "diffuse shader node")
    TT.assert_eq_nocase(Path(diffuse.image.filepath).stem, 'KhajiitMaleHead', "diffuse file name")
    assert shader.inputs['Alpha Property'].is_linked, f"Have alpha map"

    bpy.ops.export_scene.pynifly(filepath=outfile)

    # nif = pyn.NifFile(testfile)
    # head1 = nif.shapes[0]
    nif2 = pyn.NifFile(outfile)
    CheckNif(nif2, testfile)
    # head2 = nif2.shapes[0]

    # assert head2.has_alpha_property, f"Error: Did not write alpha property"
    # assert head2.alpha_property.properties.flags == head1.alpha_property.properties.flags, f"Error: Alpha flags incorrect: {head2.alpha_property.properties.flags} != {head1.alpha_property.properties.flags}"
    # assert head2.alpha_property.properties.threshold == head1.alpha_property.properties.threshold, f"Error: Alpha flags incorrect: {head2.alpha_property.properties.threshold} != {head1.alpha_property.properties.threshold}"

    # assert head2.textures['Diffuse'] == head1.textures['Diffuse'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['Diffuse']}' != '{head1.textures['Diffuse']}'"
    # assert head2.textures['Normal'] == head1.textures['Normal'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['Normal']}' != '{head1.textures['Normal']}'"
    # assert head2.textures['SoftLighting'] == head1.textures['SoftLighting'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['SoftLighting']}' != '{head1.textures['SoftLighting']}'"
    # assert head2.textures['Specular'] == head1.textures['Specular'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['Specular']}' != '{head1.textures['Specular']}'"
    # dif = head2.shader.properties.compare(head1.shader.properties)
    # assert not dif, f"Error: Shader attributes not preserved: {dif}"


def TEST_ALPHA_THRESHOLD_CHANGE():
    """Regression: Alpha threshold should not change on export."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\CRSTSkinKalaar.nif")
    outfile1 = TTB.test_file(r"tests\Out\TEST_ALPHA_THRESHOLD_CHANGE1.nif")
    outfile2 = TTB.test_file(r"tests\Out\TEST_ALPHA_THRESHOLD_CHANGE2.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    controller.apply_animation("stage1", bpy.context.scene)
    bpy.context.scene.frame_current = 1
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)

    obj = bpy.context.object
    mat = bpy.context.object.active_material
    alphanode = mat.node_tree.nodes['AlphaProperty']
    TT.assert_equiv(alphanode.inputs['Alpha Threshold'].default_value, 6.0, "Alpha Threshold pre-export")

    bpy.ops.export_scene.pynifly(filepath=outfile1)
    TT.assert_equiv(alphanode.inputs['Alpha Threshold'].default_value, 6.0, "Alpha Threshold post-export")

    nifout = pyn.NifFile(outfile1)
    assert nifout.shapes[0].alpha_property.controller is not None, f"Have alpha property controller"

    # The alpha property can have only one controller, so all sequences must reference it.
    TT.assert_samemembers(nifout.root.controller.sequences.keys(),
                          ("stage1", "stage2", "stage3"),
                          "animation sequences")
    TT.assert_eq(nifout.root.controller.sequences['stage1'].controlled_blocks[0].controller.id,
                 nifout.root.controller.sequences['stage2'].controlled_blocks[0].controller.id,
                 "alpha property controller")
    TT.assert_eq(nifout.root.controller.sequences['stage1'].controlled_blocks[0].controller.id,
                 nifout.root.controller.sequences['stage3'].controlled_blocks[0].controller.id,
                 "alpha property controller")

    ## TODO: Ensure extra targets are correct
    ## TODO: Check the output nif visually. See that stage3 does the full fade out.    
    # # Not really sure what extra targets do, but make sure they're right
    # TT.assert_eq(len(nifout.root.controller.next_controller.extra_targets), 1, "extra targets count")


def TEST_VERTEX_ALPHA():
    """Export shape with vertex alpha values"""
    outfile = TTB.test_file(r"tests/Out/TEST_VERTEX_ALPHA.nif")

    #---Create a shape
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    cube.data.materials.append(bpy.data.materials.new("Material"))
    cube.active_material.use_nodes = True
    if bpy.app.version[0] >= 4:
        bpy.ops.geometry.color_attribute_add(
            name='COLOR', domain='POINT', data_type='FLOAT_COLOR', color=(1, 1, 1, 1))

        #store alpha 0.5
        bpy.ops.geometry.color_attribute_add(
            name=BD.ALPHA_MAP_NAME, domain='POINT', data_type='FLOAT_COLOR', color=(0.5, 0.5, 0.5, 1))

        #check that 0.5 is in fact stored as 188 after internal linear->sRGB conversion
        # for i, c in enumerate(bpy.context.object.data.vertex_colors[BD.ALPHA_MAP_NAME].data):
        #     assert math.floor(c.color[1] * 255) == 188, \
        #         f"Expected sRGB color {188.0 / 255.0}, found {i}: {c.color[:]}"

        #---Export it and check the NIF

        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

        nifcheck = pyn.NifFile(outfile)
        shapecheck = nifcheck.shapes[0]

        assert shapecheck.shader.properties.shaderflags1_test(pyn.ShaderFlags1.VERTEX_ALPHA), \
            f"Expected VERTEX_ALPHA set: {pyn.ShaderFlags1(shapecheck.shader.Shader_Flags_1).fullname}"

        #check that the NIF has alpha 0.5 (to byte precision only)
            # Works when alpha is read with alph.color
        assert math.isclose(shapecheck.colors[0][3], 0.5, abs_tol=(1.0 / 255.0)), \
            f"Expected alpha 0.5, found {shapecheck.colors[0][3]}"

        for c in shapecheck.colors:
            assert c[0] == 1.0 and c[1] == 1.0 and c[2] == 1.0, \
                f"Expected all white verts in nif, found {c}"

        #---Import it back

        bpy.ops.import_scene.pynifly(filepath=outfile)
        objcheck = bpy.context.object
        try:
            alphamap = objcheck.data.attributes[BD.ALPHA_MAP_NAME]
        except:
            alphamap = objcheck.data.vertex_colors[BD.ALPHA_MAP_NAME]
        assert alphamap.name == BD.ALPHA_MAP_NAME, f"Expected alpha map"

        #check that imported color is still 188
        for i, c in enumerate(alphamap.data):
            TT.assert_equiv(c.color[1], 0.5, "alpha value")

        for i, c in enumerate(objcheck.data.attributes['Col'].data):
            TT.assert_equiv(c.color, (1.0, 1.0, 1.0, 1.0), "color value")


def TEST_BONE_HIERARCHY():
    """Bone hierarchy can be written on export"""
    # This hair has a complex custom bone hierarchy which have moved with havok.
    # Turns out the bones must be exported in a hierarchy for that to work.
    testfile = TTB.test_file(r"tests\SkyrimSE\Anna.nif")
    outfile = TTB.test_file(r"tests/Out/TESTS_BONE_HIERARCHY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile, do_import_pose=0)

    hair = TTB.find_shape("KSSMP_Anna")
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
    assert NT.VNearEqual(com.transform.translation, (0, 0, 68.9113)), f"COM location is correct: \n{com.transform}"

    spine0 = nifcheck.nodes["NPC Spine [Spn0]"]
    assert NT.VNearEqual(spine0.transform.translation, (0, -5.239852, 3.791618)), f"spine0 location is correct: \n{spine0.transform}"
    spine0Rot = Matrix(spine0.transform.rotation).to_euler()
    assert NT.VNearEqual(spine0Rot, (-0.0436, 0, 0)), f"spine0 rotation correct: {spine0Rot}"

    spine1 = nifcheck.nodes["NPC Spine1 [Spn1]"]
    assert NT.VNearEqual(spine1.transform.translation, (0, 0, 8.748718)), f"spine1 location is correct: \n{spine1.transform}"
    spine1Rot = Matrix(spine1.transform.rotation).to_euler()
    assert NT.VNearEqual(spine1Rot, (0.1509, 0, 0)), f"spine1 rotation correct: {spine1Rot}"

    spine2 = nifcheck.nodes["NPC Spine2 [Spn2]"]
    assert spine2.parent.name == "NPC Spine1 [Spn1]", f"Spine2 parent is correct"
    assert NT.VNearEqual(spine2.transform.translation, (0, -0.017105, 9.864068), 0.01), f"Spine2 location is correct: \n{spine2.transform}"

    ### Currently the original has different bind and pose positions. We export with bind and pose the same. 
    # head = nifcheck.nodes["NPC Head [Head]"]
    # assert NT.VNearEqual(head.transform.translation, (0, 0, 7.392755)), f"head location is correct: \n{head.transform}"
    # headRot = Matrix(head.transform.rotation).to_euler()
    # assert NT.VNearEqual(headRot, (0.1913, 0.0009, -0.0002), 0.01), f"head rotation correct: {headRot}"

    l3 = nifcheck.nodes["Anna L3"]
    assert l3.parent, f"'Anna L3' parent exists"
    assert l3.parent.name == 'Anna L2', f"'Anna L3' parent is '{l3.parent.name}'"
    assert NT.VNearEqual(l3.transform.translation, (0, 5, -6), 0.1), f"{l3.name} location correct: \n{l3.transform}"

    nif = pyn.NifFile(testfile)
    hair = nif.shape_dict["KSSMP_Anna"]
    assert set(hair.get_used_bones()) == set(haircheck.get_used_bones()), \
        f"The bones written to the shape match original: {haircheck.get_used_bones()}"

    sk2b = hair.get_shape_skin_to_bone("Anna L3")
    sk2bCheck = haircheck.get_shape_skin_to_bone("Anna L3")
    assert NT.XFNearEqual(sk2bCheck, sk2b), \
        f"Anna L3 skin-to-bone matches original: \n{sk2b}"


def TEST_FACEBONE_EXPORT():
    """Test can export facebones + regular nif; shapes with hidden verts export correctly"""
    # Facebones are exported along with the regular nif as long as either they are 
    # both selected or if there's an armature modifier for both on the shape. 
    # This test doesn't check that second condition.

    outfile = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT.nif", output=True)
    outfile_fb = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif", output=True)
    outfile_tri = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT.tri", output=True)
    outfile_chargen = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri")
    outfile2 = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif", output=True)
    outfile2_fb = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif", output=True)

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = TTB.append_from_file("HorseFemaleHead", False, r"tests\FO4\HeadFaceBones.blend", r"\Object", "HorseFemaleHead")
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
    """Test can export facebones + regular nif; shapes with hidden verts export correctly"""
    # Regression. Test that facebones and regular mesh are both exported.

    outfile = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif")
    outfile_fb = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif")

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = TTB.append_from_file("FemaleHead.Export.001", False, r"tests\FO4\Animatron Space Simple.blend", r"\Object", "FemaleHead.Export.001")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen")

    outnif = pyn.NifFile(outfile)
    assert len(outnif.shapes) >= 1, f"Have shapes in export file: {outnif.shapes}"

    outniffb = pyn.NifFile(outfile_fb)
    assert len(outniffb.shapes) >= 1, f"Have shapes in facebones export file: {outniffb.shapes}"


def TEST_HYENA_PARTITIONS():
    """Partitions export successfully, with warning"""
    # This Blender object has non-normalized weights--the weights for each vertex do 
    # not always add up to 1. That turns out to screw up the rendering. So check that 
    # the export normalizes them. This isn't done by pynifly or the wrapper layers.

    outfile = TTB.test_file(r"tests/Out/TEST_HYENA_PARTITIONS.nif", output=True)

    head = TTB.append_from_file("HyenaMaleHead", True, r"tests\FO4\HyenaHead.blend", r"\Object", "HyenaMaleHead")
    TTB.append_from_file("Skeleton", True, r"tests\FO4\HyenaHead.blend", r"\Object", "Skeleton")

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
        assert NT.NearEqual(w, 1.0), f"Weights should be 1 for index {i}: {w}"

    # for i in range(0, 5000):
    #     weight_total = 0
    #     for group_weights in head.bone_weights.values():
    #         for weight_pair in group_weights:
    #             if weight_pair[0] == i:
    #                 weight_total += weight_pair[1]
    #     assert NT.NearEqual(weight_total, 1.0), f"Weights should total to 1 for index {i}: {weight_total}"        


def TEST_MULT_PART():
    """Export shape with face that might fall into multiple partititions"""
    # Check that we DON'T throw a multiple-partitions error when it's not necessary.

    outfile = TTB.test_file(r"tests/Out/TEST_MULT_PART.nif")
    TTB.append_from_file("MaleHead", True, r"tests\SkyrimSE\multiple_partitions.blend", r"\Object", "MaleHead")
    obj = bpy.data.objects["MaleHead"]
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    assert "*MULTIPLE_PARTITIONS*" not in obj.vertex_groups, f"Exported without throwing *MULTIPLE_PARTITIONS* error"


def TEST_BONE_XPORT_POS():
    """Vanilla bones coming from a different skeleton export correctly."""
    # Since we use a reference skeleton to make bones, we have to be able to handle
    # the condition where the mesh is not human and the reference skeleton should not
    # be used.
    testfile = TTB.test_file(r"tests\Skyrim\draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_BONE_XPORT_POS.nif", output=True)
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

    assert NT.VNearEqual(thigh_sk2b_check.translation, Vector([-4.0765, -4.4979, 78.4952])), \
        f"Expected skin-to-bone translation Z = 78.4952, found {thigh_sk2b_check.translation[:]}"
    impnif = pyn.NifFile(testfile)
    thsk2b = impnif.shapes[0].get_shape_skin_to_bone('NPC L Thigh [LThg]')
    assert thsk2b.NearEqual(thigh_sk2b_check), f"Entire skin-to-bone transform correct: {thigh_sk2b_check}"

    # --- Check we can import correctly ---
    bpy.ops.import_scene.pynifly(filepath=outfile, do_rename_bones=False)
    impcheck = pyn.NifFile(outfile)
    nifbone = impcheck.nodes['NPC Spine2 [Spn2]']
    TT.assert_equiv(nifbone.transform.translation[2], 102.36, "Spine2 translation in nif", e=0.01)

    draugrcheck = bpy.context.object
    draugrcheck_arma = next(m.object for m in draugrcheck.modifiers if m.type == 'ARMATURE')
    spine2check = draugrcheck_arma.data.bones['NPC Spine2 [Spn2]']
    TT.assert_equiv(spine2check.matrix_local.translation[2], 102.36, "Spine2 translation in blender", e=0.01)


def TEST_INV_MARKER():
    """Can handle inventory markers"""
    # Inventory markers are imported as cameras set up to reflect how the item will be
    # shown in the inventory.

    mx, z = BD.inv_to_cam([0, 0, 3141], 1.8875)
    mx_face = Matrix((
                ( 1.0000, -0.0000,  0.0000,  0),
                (-0.0000, -0.0000, -1.0000, -100),
                ( 0.0000,  1.0000, -0.0000,  0),
                ( 0.0000,  0.0000,  0.0000,  1.0000)))
    assert BD.MatNearEqual(mx, mx_face, epsilon=0.1), f"Inventory matrix is 180 around z: {mx.to_euler()}"

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\Suzanne.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_INV_MARKER1.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_INV_MARKER2.nif")
    outfile3 = TTB.test_file(r"tests/Out/TEST_INV_MARKER3.nif")
    outfile4 = TTB.test_file(r"tests/Out/TEST_INV_MARKER4.nif")
    outfile5 = TTB.test_file(r"tests/Out/TEST_INV_MARKER5.nif")

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
    TTB.clear_all()

    # First test had the camera at the neutral position (back of Suzanne's head).
    bpy.ops.import_scene.pynifly(filepath=outfile1)
    im = next(obj for obj in bpy.data.objects if obj.type=='CAMERA')
    assert BD.MatNearEqual(im.matrix_world, BD.CAMERA_NEUTRAL), f"Inventory matrix neutral: {im.matrix_world.to_euler()}"

    # Second test had the camera at the front of Suzanne's head.
    TTB.clear_all()
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
    TTB.clear_all()
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
    """Can read and write FO4 tree"""
    # Trees in FO4 use a special root node and a special shape node.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\FO4\TreeMaplePreWar01Orange.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_TREE.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    root = next(obj for obj in bpy.data.objects if 'pynRoot' in obj)
    assert root['pynBlockName'] == "BSLeafAnimNode", f"Have correct root type: {root['pynBlockName']}"
    
    # We don't do collisions for FO4
    assert len([obj for obj in bpy.data.objects if obj.name.startswith('bhk')]) == 0, \
        f"Have no collision objects."

    tree = next(obj for obj in bpy.data.objects if obj.name.startswith("Tree") and obj.type == 'MESH')
    assert 'TREE_ANIM' in tree.active_material['Shader_Flags_2'], f"Have shader flags"
    assert tree['pynBlockName'] == "BSMeshLODTriShape", f"Have correct block type: {tree['pynBlockName']}"
    assert int(tree['lodSize0']) == 1126, f"Have correct LOD0 size"

    # ------- Export
    BD.ObjectSelect([tree, root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # ------- Check
    nifcheck = pyn.NifFile(outfile)
    assert nifcheck.rootNode.blockname == "BSLeafAnimNode", f"Have correct root node type"
    treecheck = nifcheck.shapes[0]
    assert treecheck.blockname == "BSMeshLODTriShape", f"Have correct shape node type"
    assert treecheck.shader.properties.shaderflags2_test(pyn.ShaderFlags2.TREE_ANIM), f"Tree animation set"
    assert treecheck.properties.vertexCount == 1059, f"Have correct vertex count"
    assert treecheck.properties.lodSize0 == 1126, f"Have correct lodSize0"


def CheckBow(nif, nifcheck, bow):
    """Check that the glass bow nif is correct."""
    TTB.compare_shapes(nif.shape_dict['ElvenBowSkinned:0'], 
                      nifcheck.shape_dict['ElvenBowSkinned:0'],
                      bow)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    # Check the midbone transform
    mbc_xf = nifcheck.get_node_xform_to_global("Bow_MidBone")
    assert NT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = BD.transform_to_matrix(mbc_xf).to_euler()
    assert NT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    # check the collisions
    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert nifdefs.bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    bodycheck = collcheck.body
    p = bodycheck.properties
    assert p.collisionFilter_layer == nifdefs.SkyrimCollisionLayer.WEAPON, f"Have correct collision layer"
    assert NT.VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"

    boxcheck = bodycheck.shape
    assert boxcheck.blockname == 'bhkBoxShape', f"Box shape block correct"

    # Rotation and dimensions are related. Could check the bounds, which is a lot of math.
    # Instead check the values, but make sure the values give a good collision.
    #assert NT.VNearEqual(p.rotation[:], [0.0, 0.0, 0.0, 1.0]), f"Collision body rotation correct: {p.rotation[:]}"
    dimv = Vector(boxcheck.properties.bhkDimensions)
    p = bodycheck.properties
    rot = Quaternion((p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2],))
    dimv.rotate(rot)
    assert dimv.x > dimv.y > dimv.z, f"Have good collision bounds: {dimv}"

    bsxcheck = nifcheck.rootNode.bsx_flags
    assert bsxcheck == ["BSX", 202], f"BSX Flag node found: {bsxcheck}"

    bsinvcheck = nifcheck.rootNode.inventory_marker
    assert bsinvcheck[0:4] == ["INV", 4712, 0, 785], f"Inventory marker set: {bsinvcheck}"
    # assert round(bsinvcheck[4], 4) == 1.1273, f"Inventory marker zoom set: {bsinvcheck[4]}"


def TEST_COLLISION_BOW_SCALE():
    """Collisions scale correctly on import and export"""
    # Collisions have to be scaled with everything else if the import/export
    # has a scale factor.

    # Primarily tests collisions, but this nif has everything: collisions, root node as
    # fade node, bone hierarchy, extra data nodes. So tests for those and also  
    # UV orientation and texture handling

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW_SCALE.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 use_blender_xf=True, 
                                 do_import_pose=False)

    # ------- Check --------
    bow = TTB.find_shape("ElvenBowSkinned:0")

    # Check shape size
    assert BD.VNearEqual(bow.scale, Vector((1,1,1))), "Have 1x scale"
    maxy = max(v.co.y for v in bow.data.vertices)
    miny = min(v.co.y for v in bow.data.vertices)
    assert BD.NearEqual(maxy, 64.4891), f"Have correct max y: {maxy}"
    assert BD.NearEqual(miny, -50.5509), f"Have correct min y: {miny}"

    # Make sure the bone positions didn't get messed up by use_blender_xf.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    mxbind = arma.data.bones['Bow_StringBone1'].matrix_local
    mxpose = arma.pose.bones['Bow_StringBone1'].matrix
    assert BD.MatNearEqual(mxbind, mxpose), f"Bind position same as pose position"

    # Check collision info
    midbone = arma.data.bones['Bow_MidBone']
    midbonew = arma.matrix_world @ midbone.matrix_local
    coll = arma.pose.bones['Bow_MidBone'].constraints[0].target
    assert NT.VNearEqual(coll.matrix_world.translation, midbonew.translation), \
        f"Collision positioned at target bone"

    q = coll.matrix_world.to_quaternion()
    assert NT.VNearEqual(q, (0.7071, 0.0, 0.0, 0.7071)), \
        f"Collision body rotation correct: {coll.rotation_quaternion}"

    # Scale factor applied to bow
    objmin, objmax = TTB.get_obj_bbox(bow, worldspace=True)
    assert objmax.y - objmin.y < 12, f"Bow is properly scaled: {objmax - objmin}"

    # Collision box bounds close to bow bounds.
    collbox = TTB.find_shape('bhkBoxShape')
    assert TTB.close_bounds(bow, collbox), f"Collision just covers bow"

    # Quick unit test--getting box info should be correct in world coordinates.
    c, d, r = BD.find_box_info(collbox)
    dworld = collbox.matrix_world.to_quaternion().inverted() @ (r @ d)
    dworld = Vector([abs(n) for n in dworld])

    # The rotation should result is the long axis aligned with y, short with z
    assert dworld.y > dworld.x > dworld.z, f"Have correct rotation"

    # Centerpoint of collision box is just offset from origin
    assert BD.VNearEqual(c, Vector((0.6402, 0.0143, 0.002))), f"Centerpoint correct: {c}"

    print("--Testing export")

    # Move the edge of the collision box so it covers the bow better
    for v in collbox.data.vertices:
        if v.co.x < 0:
            v.co.x -= 0.1
        if v.co.y > 0:
            v.co.y += 6

    collbox.update_from_editmode()
    boxmin, boxmax = TTB.get_obj_bbox(collbox, worldspace=True)
    assert NT.VNearEqual(objmax, boxmax, epsilon=1.0), f"Collision just covers bow: {objmax} ~~ {boxmax}"

    # ------- Export and Check Results --------

    # We want the special properties of the root node. 
    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)

    # Depend on the defaults stored on the armature for scale factor
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True)

    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)

    TTB.compare_shapes(nif.shape_dict['ElvenBowSkinned:0'],
                      nifcheck.shape_dict['ElvenBowSkinned:0'],
                      bow)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert nifdefs.bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    TTB.compare_bones('Bow_MidBone', nif, nifcheck, e=0.001)
    TTB.compare_bones('Bow_StringBone2', nif, nifcheck, e=0.001)


    # Re-import the nif to make sure collisions are right. Could test them in the nif
    # directly but the math is gnarly.
    TTB.clear_all()

    bpy.ops.import_scene.pynifly(filepath=outfile, 
                                 use_blender_xf=True,
                                 do_import_pose=False)
    bow = bpy.context.object
    arma = bow.modifiers['Armature'].object
    bone = arma.pose.bones['Bow_MidBone']
    box = bone.constraints[0].target
    mina, maxa = TTB.get_obj_bbox(bow, worldspace=True)
    minb, maxb = TTB.get_obj_bbox(box, worldspace=True)
    assert minb[0] < mina[0], f"Box min x less than bow min"
    assert minb[1] < mina[1], f"Box min y less than bow min"
    assert maxb[0] > maxa[0], f"Box max x greater than bow max"
    assert maxb[1] > maxa[1], f"Box max y greater than bow max"


def TEST_COLLISION_BOW():
    """Can read and write bow"""
    # The bow has a simple collision that we can import and export.
    # Note the bow nif as shipped by Bethesda throws errors on import, and the 
    # collision does not match the mesh closely at all. This test adjusts it on
    # export because it was too ugly.

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    # Check root info
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    assert root["pynBlockName"] == 'BSFadeNode', "pynRootNode_BlockType holds the type of root node for the given shape"
    assert root["pynNodeName"] == "GlassBowSkinned.nif", "pynRootNode_Name holds the name for the root node"
    assert root["pynNodeFlags"] == "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR", f"'pynNodeFlags' holds the flags on the root node: {root['pynRootNode_Flags']}"
    assert len([c for c in root.children if c.type=='MESH']) == 1, f"Have one mesh"
    
    # Check shape size
    bow = TTB.find_shape("ElvenBowSkinned:0")
    maxy = max(v.co.y for v in bow.data.vertices)
    miny = min(v.co.y for v in bow.data.vertices)
    assert BD.NearEqual(maxy, 64.4891), f"Have correct max y: {maxy}"
    assert BD.NearEqual(miny, -50.5509), f"Have correct min y: {miny}"

    # Check armature
    arma = bow.modifiers['Armature'].object
    assert len(arma.data.bones) == 7, f"Have right number of bones"
    maxx = max(b.matrix_local.translation.x for b in arma.data.bones)
    minx = min(b.matrix_local.translation.x for b in arma.data.bones)
    maxy = max(b.matrix_local.translation.y for b in arma.data.bones)
    miny = min(b.matrix_local.translation.y for b in arma.data.bones)
    assert maxx > 1.0, f"Armature bind position stretches wide enough"
    assert miny < -10.0, f"Armature bind stretches low enough"
    assert maxy > 50.0, f"Armature bind position stretches high enough"
    assert miny < -50.0, f"Armature bind stretches low enough"

    # Check collision info
    coll = arma.pose.bones['Bow_MidBone'].constraints['bhkCollisionConstraint'].target
    assert coll.name == 'bhkBoxShape', f"Collision shape is box"
    assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
    assert coll['collisionFilter_layer'] == nifdefs.SkyrimCollisionLayer.WEAPON.name, \
        f"Collsion filter layer is loaded as string: {coll['collisionFilter_layer']}"

    # Default collision response is 1 = SIMPLE_CONTACT, so no property for it.
    # assert coll["collisionResponse"] == nifdefs.hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"

    # assert NT.VNearEqual(coll.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), f"Collision body rotation correct: {collbody.rotation_quaternion}"

    assert coll['bhkMaterial'] == 'MATERIAL_BOWS_STAVES', f"Shape material is a custom property: {coll['bhkMaterial']}"
    assert round(coll['bhkRadius'],4) == 0.0136, f"Radius property available as custom property: {coll['bhkRadius']}"

    # Covers the bow closely in the Y axis
    bowmax = max((bow.matrix_world @ v.co).y for v in bow.data.vertices)
    boxmax = max((coll.matrix_world @ v.co).y for v in coll.data.vertices)
    assert BD.NearEqual(bowmax, boxmax, epsilon=0.1), f"Collision matches bow up"
    bowmin = min((bow.matrix_world @ v.co).y for v in bow.data.vertices)
    boxmin = min((coll.matrix_world @ v.co).y for v in coll.data.vertices)
    assert BD.NearEqual(bowmin, boxmin+0.25, epsilon=0.1), f"Collision matches bow down"

    # Covers the bow badly in the X axis
    bowmax = max((bow.matrix_world @ v.co).x for v in bow.data.vertices)
    boxmax = max((coll.matrix_world @ v.co).x for v in coll.data.vertices)
    assert BD.NearEqual(bowmax, boxmax+5.4, epsilon=0.1), f"Collision matches bow up"
    bowmin = min((bow.matrix_world @ v.co).x for v in bow.data.vertices)
    boxmin = min((coll.matrix_world @ v.co).x for v in coll.data.vertices)
    assert BD.NearEqual(bowmin, boxmin+1.25, epsilon=0.1), f"Collision matches bow down"

    # Check extra data
    bged = TTB.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    assert bged['BSBehaviorGraphExtraData_Value'] == "Weapons\Bow\BowProject.hkx", f"BGED node contains bow project: {bged['BSBehaviorGraphExtraData_Value']}"

    strd = TTB.find_shape("NiStringExtraData", type='EMPTY')
    assert strd['NiStringExtraData_Value'] == "WeaponBow", f"Str ED node contains bow value: {strd['NiStringExtraData_Value']}"

    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    assert bsxf.parent == root, f"Extra data imported under root"
    assert bsxf['BSXFlags_Name'] == "BSX", f"BSX Flags contain name BSX: {bsxf['BSXFlags_Name']}"
    assert bsxf['BSXFlags_Value'] == "HAVOC | COMPLEX | DYNAMIC | ARTICULATED", "BSX Flags object contains correct flags: {bsxf['BSXFlags_Value']}"

    invm = TTB.find_shape("BSInvMarker", type='CAMERA')
    assert invm['BSInvMarker_Name'] == "INV", f"Inventory marker shape has correct name: {invm['BSInvMarker_Name']}"
    assert invm['BSInvMarker_RotX'] == 4712, f"Inventory marker rotation correct: {invm['BSInvMarker_RotX']}"
    assert round(invm['BSInvMarker_Zoom'], 4) == 1.1273, f"Inventory marker zoom correct: {invm['BSInvMarker_Zoom']}"

    # Check shape as deformed by armature
    BD.ObjectSelect([bow], active=True)
    bpy.ops.object.duplicate()
    bpy.context.object.name = 'TEST_COLLISION_BOW_COPY'
    for m in bow.modifiers:
        if m.type == 'ARMATURE':
            bpy.ops.object.modifier_apply(modifier=m.name)
    maxy = max(v.co.y for v in bow.data.vertices)
    miny = min(v.co.y for v in bow.data.vertices)
    assert BD.NearEqual(maxy, 64.4891), f"Have correct max y: {maxy}"
    assert BD.NearEqual(miny, -50.5509), f"Have correct min y: {miny}"

    # ------- Export --------

    # Move the edge of the collision box so it covers the bow better
    for v in coll.data.vertices:
        if v.co.y > 0:
            v.co.y += 5.4

    # Exporting the root object takes everything with it and sets root properties.
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True)

    # ------- Check Results --------
    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    CheckBow(nif, nifcheck, bow)

def TEST_COLLISION_BOW2():
    """Can modify collision shape location."""

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW2.nif")
    
    bpy.ops.import_scene.pynifly(filepath=testfile)
    bow = bpy.context.object
    root = bow.parent
    arma = bow.modifiers['Armature'].object
    coll = arma.pose.bones['Bow_MidBone'].constraints['bhkCollisionConstraint'].target
    bged = TTB.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TTB.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    invm = TTB.find_shape("BSInvMarker", type='CAMERA')

    # ------- Export --------
    # Move the edge of the collision box so it covers the bow better
    for v in coll.data.vertices:
        if v.co.y > 0:
            v.co.y += 5.4

    # Move the collision object 
    coll.location = coll.location + Vector([5, 10, 0])

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile2, target_game='SKYRIMSE')

    # ------- Check Results 2 --------
    nif = pyn.NifFile(testfile)
    nifcheck2 = pyn.NifFile(outfile2)
    CheckBow(nif, nifcheck2, bow)

    # midbowcheck2 = nifcheck2.nodes["Bow_MidBone"]
    # collcheck2 = midbowcheck2.collision_object
    # assert collcheck2.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck2.blockname}"
    # assert nifdefs.bhkCOFlags(collcheck2.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # # Full check of locations and rotations to make sure we got them right
    # mbc_xf = nifcheck2.get_node_xform_to_global("Bow_MidBone")
    # assert NT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    # m = BD.transform_to_matrix(mbc_xf).to_euler()
    # assert NT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    # bodycheck2 = collcheck2.body
    # p = bodycheck2.properties
    # assert NT.VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    # assert NT.VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


def TEST_COLLISION_BOW3():
    """Can modify collision shape type"""
    # We can change the collision by editing the Blender shapes. Collision shape has a
    # rotation and no scale. Check with and without Blender transform.

    def do_test(bl):
        # ------- Load --------
        testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
        outfile3 = TTB.test_file(f"tests/Out/TEST_COLLISION_BOW3_{bl}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=(bl=='BLENDER'))
        bow = bpy.context.object
        root = bow.parent
        arma = bow.modifiers['Armature'].object
        coll = arma.pose.bones['Bow_MidBone'].constraints['bhkCollisionConstraint'].target

        # ------- Export --------

        # Move the collision object 
        for v in coll.data.vertices:
            if NT.NearEqual(v.co.y, 3.3, epsilon=0.5):
                v.co.y = 9.3
                if v.co.x > 0:
                    v.co.x = 30.6
                else:
                    v.co.x = -19.5
        coll.name = "bhkConvexVerticesShape"

        BD.ObjectSelect([root], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile3, target_game='SKYRIMSE')
        
        # ------- Check Results 3 --------

        nifcheck3 = pyn.NifFile(outfile3)

        midbowcheck3 = nifcheck3.nodes["Bow_MidBone"]
        collcheck3 = midbowcheck3.collision_object
        assert collcheck3.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck3.blockname}"
        assert nifdefs.bhkCOFlags(collcheck3.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

        # Full check of locations and rotations to make sure we got them right
        mbc_xf = nifcheck3.get_node_xform_to_global("Bow_MidBone")
        assert NT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
        m = BD.transform_to_matrix(mbc_xf).to_euler()
        assert NT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

        bodycheck3 = collcheck3.body

        cshapecheck3 = bodycheck3.shape
        assert cshapecheck3.blockname == "bhkConvexVerticesShape", f"Shape is convex vertices: {cshapecheck3.blockname}"
        assert NT.VNearEqual(cshapecheck3.vertices[0], (-0.73, -0.267, 0.014, 0.0)), f"Convex shape is correct"

    do_test('NATURAL')
    do_test('BLENDER')


def TEST_COLLISION_HIER():
    """Can read and write hierarchy of nodes containing shapes"""
    # These leeks are two shapes collected under an NiNode, with the collision on the 
    # NiNode. 

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\grilledleekstest.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_HIER.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek0 = TTB.find_shape("Leek04:0")
    leek1 = TTB.find_shape("Leek04:1")
    leek4 = leek0.parent
    assert leek4.name == 'Leek04', f"Have correct parent"
    assert leek0.parent == leek1.parent, f"Have correct parent/child relationships"
    assert len(leek4.constraints) > 0, f"Have constraint on parent"
    cshape = leek4.constraints[0].target
    assert cshape, f"Have collision shape"
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
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    invm = TTB.find_shape("BSInvMarker", type='CAMERA')
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
    assert NT.VNearEqual(shCheck.vertices[0], shOrig.vertices[0]), f"Collision vertices match 0: {shCheck.vertices[0][:]} == {shOrig.vertices[0][:]}"
    assert NT.VNearEqual(shCheck.vertices[5], shOrig.vertices[5]), f"Collision vertices match 0: {shCheck.vertices[5][:]} == {shOrig.vertices[5][:]}"


def TEST_NORM():
    """Normals are read correctly"""
    testfile = TTB.test_file(r"tests/FO4/CheetahMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TTB.find_shape("CheetahMaleHead")

    if hasattr(head.data, "calc_normals_split"):
        head.data.calc_normals_split()

    targetvert = head.data.vertices[3071]
    TT.assert_equiv(targetvert.normal, [-0.207843, 0.435294, 0.874510], "vertex normal", e=0.01)

    vertloops = [l.index for l in head.data.loops if l.vertex_index == targetvert.index]
    custnormal = head.data.loops[vertloops[0]].normal
    TT.assert_equiv(custnormal, [-0.207843, 0.435294, 0.874510], "loop normal", e=0.01)
    # print(f"TEST_NORM custnormal: loop {vertloops[0]} has normal {custnormal}")
    # assert NT.VNearEqual(custnormal, [-0.1772, 0.4291, 0.8857]), \
    #     f"Custom normal different from vertex normal: {custnormal}"


def TEST_SPLIT_NORMALS():
    """Mesh with wonky normals exports correctly"""
    # Custom split normals change the direction light bounces off an object. They may be
    # set to eliminate seams between parts of a mesh, or between two meshes.

    testfile = TTB.test_file(r"tests/Out/TEST_SPLIT_NORMALS.nif")

    obj = TTB.append_from_file("MHelmetLight:0", 
                              False, 
                              r"tests\FO4\WonkyNormals.blend", 
                              r"\Object", 
                              "MHelmetLight:0")
    assert obj.name == "MHelmetLight:0", "Got the right object"

    bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")

    nif2 = pyn.NifFile(testfile)
    shape2 = nif2.shapes[0]

    TTB.test_floatarray("Normal 44", shape2.normals[44], [0, 0, 1], epsilon=0.1)
    TTB.test_floatarray("Vert 12 location", shape2.verts[12], [6.82, 0.58, 9.05], epsilon=0.01)
    TTB.test_floatarray("Vert 5 location", shape2.verts[5], [0.13, 9.24, 8.91], epsilon=0.01)
    TTB.test_floatarray("Vert 33 location", shape2.verts[33], [-3.21, -1.75, 12.94], epsilon=0.01)

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
    """Shape keys export normals correctly"""
    # Shape keys and custom normals interfere with each other. If a shape key warps the
    # mesh, what direction should a custom normal face after the warp? We just preserve
    # the direction and leave it to the user to separate out the shape key if they don't
    # like the result.
    testfile = TTB.test_file(r"tests/Out/TEST_ROGUE02.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ROGUE02_warp.nif")

    TTB.export_from_blend(r"tests\Skyrim\ROGUE02-normals.blend",
                         "Plane", "SKYRIM", testfile, "_warp")

    nif2 = pyn.NifFile(outfile)
    shape2 = nif2.shapes[0]
    assert len(shape2.verts) == 25, f"Export shouldn't create extra vertices, found {len(shape2.verts)}"
    v = [round(x, 1) for x in shape2.verts[18]]
    assert v == [0.0, 0.0, 0.2], f"Vertex found at incorrect position: {v}"
    n = [round(x, 1) for x in shape2.normals[8]]
    assert n == [0, 1, 0], f"Normal should point along y axis, instead: {n}"


def TEST_NORMAL_SEAM():
    """Normals on a split seam are seamless"""
    testfile = TTB.test_file(r"tests/Out/TEST_NORMAL_SEAM.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_NORMAL_SEAM_Dog.nif")

    TTB.export_from_blend(r"tests\FO4\TestKnitCap.blend", "MLongshoremansCap:0",
                      "FO4", testfile)

    nif2 = pyn.NifFile(outfile)
    shape2 = nif2.shapes[0]
    target_vert = [i for i, v in enumerate(shape2.verts) if NT.VNearEqual(v, (0.00037, 7.9961, 9.34375))]

    assert len(target_vert) == 2, f"Expect vert to have been split: {target_vert}"
    assert NT.VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


def TEST_NIFTOOLS_NAMES():
    """Can import nif with niftools' naming convention"""
    # We allow renaming bones according to the NifTools format. Someday this may allow
    # us to use their animation tools, but this is not that day.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\malebody_1.nif")

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

        body = TTB.find_shape("MaleUnderwearBody1:0")
        assert "NPC Calf [Clf].L" in body.vertex_groups, f"Vertex groups follow niftools naming convention: {body.vertex_groups.keys()}"


def TEST_COLLISION_MULTI():
    """Can read and write shape with multiple collision shapes"""

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\grilledleeks01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_MULTI.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek10 = TTB.find_shape("Leek01:0")
    leek11 = TTB.find_shape("Leek01:1")
    leek1 = leek10.parent
    leek1 == leek10.parent == leek11.parent, f"Parent/child relationships correct"
    assert leek1.name == "Leek01", f"Have correct parent"
    assert len(leek1.constraints) > 0, f"Leek has constraints"
    
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
    """"Can read and write shape with convex verts collision shape at scale."""
    def do_test(bx):
        print(f"<<<Can read and write shape with convex verts collision shape at scale {bx}>>>")
        TTB.clear_all()

        # ------- Load --------
        testfile = TTB.test_file(r"tests\Skyrim\cheesewedge01.nif")
        outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_CONVEXVERT.{'BL' if bx else 'NAT'}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        # Check transform
        cheese = TTB.find_shape('CheeseWedge')
        assert NT.VNearEqual(cheese.location, (0,0,0)), f"Cheese wedge at right location: {cheese.location}"
        assert NT.VNearEqual(cheese.rotation_euler, (0,0,0)), f"Cheese wedge not rotated: {cheese.rotation_euler}"
        assert cheese.scale == Vector((1,1,1)), f"Cheese wedge scale 1"

        # Check collision info
        root = cheese.parent
        constr = [c for c in root.constraints if c.type == 'COPY_TRANSFORMS']
        assert constr, f"Have constraints on root"
        coll = constr[0].target
        assert coll, f"Have collision object"
        assert coll.rigid_body, f"Collision object has physics"
        assert coll.rigid_body.type == 'ACTIVE'
        assert BD.NearEqual(coll.rigid_body.mass, 2.5 / nifdefs.HSF), f"Have correct mass"
        assert BD.NearEqual(coll.rigid_body.friction, 0.5 / nifdefs.HSF), f"Have correct friction"
        assert coll['bhkMaterial'] == 'CLOTH', f"Shape material is a custom property: {coll['bhkMaterial']}"

        xmax1 = max([v.co.x for v in cheese.data.vertices])
        xmax2 = max([v.co.x for v in coll.data.vertices])
        assert abs(xmax1 - xmax2) < 0.5, f"Max x vertex nearly the same: {xmax1} == {xmax2}"
        corner = coll.data.vertices[0].co
        assert NT.VNearEqual(corner, (-4.18715, -7.89243, 7.08596)), f"Collision shape in correct position: {corner}"

        # ------- Export --------

        BD.ObjectSelect([root], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', 
                                     use_blender_xf=bx)

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

        assert NT.NearEqual(minxch, minxorig), f"Vertex x is correct: {minxch} == {minxorig}"
        assert NT.NearEqual(maxxch, maxxorig), f"Vertex x is correct: {maxxch} == {maxxorig}"

        # Re-import
        #
        # There have been issues with importing the exported nif and having the 
        # collision be wrong
        TTB.clear_all()
        bpy.ops.import_scene.pynifly(filepath=outfile)

        impcollshape = TTB.find_shape("bhkConvexVerticesShape")
        impcollshape = TTB.find_shape("bhkConvexVerticesShape")
        zmin = min([v.co.z for v in impcollshape.data.vertices])
        assert zmin >= -0.01, f"Minimum z is positive: {zmin}"

    do_test(True)
    do_test(False)

    
def TEST_COLLISION_CAPSULE():
    """Can read and write shape with collision capsule shapes with and without Blender transforms"""
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    def do_test(bx):
        print(f"<<<Can read and write shape with collision capsule shapes with Blender transforms {bx}>>>")
        TTB.clear_all()

        # ------- Load --------
        testfile = TTB.test_file(r"tests\Skyrim\staff04.nif")
        outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_CAPSULE.{'BL' if bx else 'NAT'}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        staff = TTB.find_shape("3rdPersonStaff04")
        coll = staff.parent.constraints[0].target
        assert coll['bhkMaterial'] == 'SOLID_METAL', f"Have correct material"
        strd = TTB.find_shape("NiStringExtraData", type="EMPTY")
        bsxf = TTB.find_shape("BSXFlags", type="EMPTY")
        invm = TTB.find_shape("BSInvMarker", type="EMPTY")

        # The staff has bits that stick out, so its bounding box is a bit larger than
        # the collision's.
        staffmin, staffmax = TTB.get_obj_bbox(staff, worldspace=True)
        collmin, collmax = TTB.get_obj_bbox(coll, worldspace=True)
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
        assert NT.NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), \
            f"Wrote the correct radius: {shapecheck.properties.radius1}"
        
        assert NT.NearEqual(shapeorig.properties.point1[1], 
                            shapecheck.properties.point1[1],
                            epsilon=0.05), \
            f"Wrote the correct radius: {shapecheck.properties.point1[1]}"

    do_test(False)
    do_test(True)


def TEST_COLLISION_CAPSULE2():
    """Can read and write shape with collision capsule shapes with and without Blender transforms."""
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    def do_test(bx):
        print(f"<<<Can read and write shape with collision capsule shapes with Blender transforms {bx}>>>")
        TTB.clear_all()

        # ------- Load --------
        testfile = TTB.test_file(r"tests\Skyrim\staff04-collision.nif")
        outfile = TTB.test_file(
            f"tests/Out/TEST_COLLISION_CAPSULE2.{'BL' if bx else 'NAT'}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=bx)

        staff = TTB.find_shape("3rdPersonStaff04")
        root = staff.parent
        collshape = root.constraints[0].target

        # -------- Export --------
        BD.ObjectSelect([root], active=True)
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
        assert NT.NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), \
            f"Wrote the correct radius: {shapecheck.properties.radius1}"
        
        assert NT.NearEqual(shapeorig.properties.point1[1], 
                            shapecheck.properties.point1[1],
                            epsilon=0.002), \
            f"Wrote the correct point location: {shapecheck.properties.point1[1]}"

    do_test(False)
    do_test(True)


def TEST_COLLISION_LIST():
    """
    Can read and write shape with collision list and collision transform shapes with and
    without Blender transform.
    """
    def run_test(bx):
        print(f"<<<Can read and write shape with collision list and collision transform shapes with Blender transform {bx}>>>")
        TTB.clear_all()

        # ------- Load --------
        testfile = TTB.test_file(r"tests\Skyrim\falmerstaff.nif")
        outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_LIST_{bx}.nif")

        bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=(bx=='BLENDER'))

        staff = TTB.find_shape("Staff3rdPerson:0")
        root = staff.parent
        collshape = root.constraints[0].target
        assert collshape.name.startswith('bhkListShape'), "Have list shape"
        yvals = set(round(obj.location.y, 1) for obj in collshape.children)
        expectedy = set(map(lambda x: round(x*BD.HSF, 1), [0.632, -0.19, 0.9]))
        assert yvals == expectedy, f"Have expected y vals: {yvals} == {expectedy}"

        assert collshape.name.startswith("bhkListShape"), f"Found list collision shape: {collshape.name}"
        assert len(collshape.children) == 3, f" Collision shape has children"
    
        # -------- Export --------
        BD.ObjectSelect([root], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', 
                                     use_blender_xf=(bx=='BLENDER'))

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

        # Check that the ConvexTransforms put the collision shapes in the right place,
        # no matter what order they're written.
        xflist = set(round(xfs.transform[1][3], 3) for xfs in xfshapesorig)
        xfcheck = set(round(xfs.transform[1][3], 3) for xfs in xfshapescheck)
        assert xflist == xfcheck, f"Have same transforms in both files"

        cts45check = None
        for cts in listcheck.children:
            erot = Matrix(cts.transform).to_euler()
            theta = round(math.degrees(erot.x))
            if NT.NearEqual(theta % 45, 0): # Is some multiple of 45
                cts45check = cts
        boxdiag = cts45check.child
        assert NT.NearEqual(boxdiag.properties.bhkDimensions[1], 0.170421), f"Diagonal box has correct size: {boxdiag.properties.bhkDimensions[1]}"

    # run_test('BLENDER')
    run_test('NATURAL')


def TEST_COLLISION_BOW_CHANGE():
    """Changing collision type works correctly"""

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW_CHANGE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    arma = obj.modifiers['Armature'].object
    bone = arma.pose.bones['Bow_MidBone']
    collshape = bone.constraints[0].target
    bged = TTB.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TTB.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    invm = TTB.find_shape("BSInvMarker", type='EMPTY')
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
    """
    Can read and write shape with collision we build ourselves in Blender.
    """
    # TriShapes provide for a collision to be attached to them directly but vanilla Skyrim
    # nifs never do that. So make a root node and attach the collision to that.
    #
    # Note we then have to export the root node or we don't get the collisions.
    if bpy.app.version[0] > 3:
        # Blender V2.x does not import the whole parent chain when appending an object from
        # another file, so don't try to run this on that version.

        # ------- Load --------
        blendfile = TTB.test_file(r"tests/SkyrimSE/staff.blend")
        outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_XFORM.nif")
        
        bpy.ops.object.add(radius=1.0, type='EMPTY')
        root = bpy.context.object
        root.name = 'Root'

        staff = TTB.append_from_file("Staff", True, blendfile, r"\Object", "Staff")
        inv = TTB.append_from_file("BSInvMarker", True, blendfile, r"\Object", "BSInvMarker")
        flg = TTB.append_from_file("BSXFlags", True, blendfile, r"\Object", "BSXFlags")
        ext = TTB.append_from_file("NiStringExtraData", True, blendfile, r"\Object", "NiStringExtraData")
        c1 = TTB.append_from_file("bhkCapsuleShape", True, blendfile, r"\Object", "bhkCapsuleShape")
        c2 = TTB.append_from_file("bhkConvexVerticesShape", True, blendfile, r"\Object", "bhkConvexVerticesShape")
        c3 = TTB.append_from_file("bhkConvexVerticesShape.001", True, blendfile, r"\Object", "bhkConvexVerticesShape.001")
        c4 = TTB.append_from_file("bhkConvexVerticesShape.002", True, blendfile, r"\Object", "bhkConvexVerticesShape.002")
        listcollision = TTB.append_from_file("bhkListShape", True, blendfile, r"\Object", "bhkListShape")
        c1.parent = listcollision
        c2.parent = listcollision
        c3.parent = listcollision
        c4.parent = listcollision
        
        # Append screwed positions up, so fix them.
        for c in [c1, c2, c3, c4, listcollision]:
            for v in c.data.vertices:
                v.co = v.co + Vector((0, listcollision.location.y, 0))

        if len(root.constraints) == 0: constr = root.constraints.new('COPY_TRANSFORMS')
        root.constraints[0].target = listcollision
        root['pynRoot'] = True
        staff.parent = root
        inv.parent = root
        flg.parent = root
        ext.parent = root
        for obj in bpy.data.objects:
            if obj.name.startswith('bhkListShape') and obj.name != 'bhkListShape':
                BD.ObjectSelect([obj], active=True)
                bpy.ops.object.delete()

        # -------- Export --------
        BD.ObjectSelect([root], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

        # ------- Check ---------
        nifcheck = pyn.NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        listcheck = rbcheck.shape
        capsules = [c.child for c in listcheck.children if c.child.blockname == "bhkCapsuleShape"]
        assert capsules[0].properties.point1[1] < 0 < capsules[0].properties.point2[1], \
            f"Capsule crosses origin"
        
        capcts = listcheck.children[0] 
        capshape = capcts.child
        assert capshape.blockname == 'bhkCapsuleShape', f"Have the capsule"
        capmaxy = (capcts.transform[1][3] + capshape.properties.point2[1]) * BD.HSF
        assert BD.NearEqual(capmaxy, 67, epsilon=1.0), f"Capsule max y correct: {capmaxy}"

        capminy = (capcts.transform[1][3] + capshape.properties.point1[1]) * BD.HSF
        assert BD.NearEqual(capminy, -73.4, epsilon=1.0), f"Capsule min y correct: {capminy}"

        
def TEST_CONNECT_POINT():
    """Connect points import/export correctly"""
    # FO4 has a complex method of attaching shapes to other shapes in game, using
    # connect points. These can be created and manipulated in Blender.
    # 
    # Also check that the default shape type created is BSTriShape

    testfile = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_CONNECT_POINT.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    parentnames = set(['P-Barrel', 'P-Casing', 'P-Grip', 'P-Mag', 'P-Scope'])
    childnames = ['C-Receiver', 'C-Reciever']

    # Empties are not left selected by import
    root = next(o for o in bpy.context.scene.objects if 'pynRoot' in o)
    shotgun = next(o for o in bpy.context.scene.objects if o.name.startswith('CombatShotgunReceiver:0'))
    cpparents = [o for o in bpy.context.scene.objects if o.name.startswith('BSConnectPointParents')]
    cpchildren = [o for o in bpy.context.scene.objects if o.name.startswith('BSConnectPointChildren')]
    cpcasing = next(o for o in bpy.context.scene.objects if o.name.startswith('BSConnectPointParents::P-Casing'))
    
    assert len(cpparents) == 5, f"Found parent connect points: {cpparents}"
    p = set(x.name.split("::")[1] for x in cpparents)
    assert p == parentnames, f"Found correct parentnames: {p}"

    assert cpchildren, f"Found child connect points: {cpchildren}"
    assert (cpchildren[0]['PYN_CONNECT_CHILD_0'] == "C-Receiver") or \
        (cpchildren[0]['PYN_CONNECT_CHILD_1'] == "C-Receiver"), \
        f"Did not find child name"

    # assert NT.NearEqual(cpcasing.rotation_quaternion.w, 0.9098), f"Have correct rotation: {cpcasing.rotation_quaternion}"
    assert cpcasing.parent.name == "CombatShotgunReceiver", f"Casing has correct parent {cpcasing.parent.name}"

    # Shapes remember their block type
    shotgun['pynBlockName'] == 'BSTriShape'

    # Remove it so we can test the default is correct.
    del shotgun['pynBlockName']

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
    assert NT.VNearEqual(pcasing.rotation[:], pcasingsrc.rotation[:]), f"Have correct rotation: {pcasing}"

    chnames = nifcheck.connect_points_child
    TT.assert_samemembers(chnames, childnames, "child connect point names")

    sgcheck = nifcheck.shape_dict['CombatShotgunReceiver:0']
    assert sgcheck.blockname == 'BSTriShape', f"Have correct blockname: {sgcheck.blockname}"


def TEST_CONNECT_POINT_MULT():
    """Regression: Blend file creates duplicate connect points."""

    testfile = TTB.test_file(r"tests\FO4\rifleCP.blend")
    outfile = TTB.test_file(r"tests\Out\TEST_CONNECT_POINT_MULT.nif")

    fp = os.path.join(TT.pynifly_dev_path, testfile)
    bpy.ops.wm.append(filepath=fp,
                      directory=fp + r"\Collection",
                      filename="RECEIVER",
                      use_recursive=True)

    chcp = bpy.data.objects['BSConnectPointChildren::C-Receiver']
    BD.ObjectSelect([chcp], active=True)    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    parentnames = ['P-Barrel', 'P-Casing', 'P-Grip', 'P-Grip2', 'P-Mag', 'P-Scope', 'P-Stock']
    childnames = ['C-Receiver']

    ## --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    chnames = nifcheck.connect_points_child
    TT.assert_samemembers(chnames, childnames, "child connect point names")
    parnames = [p.name.decode() for p in nifcheck.connect_points_parent]
    TT.assert_samemembers(parnames, parentnames, "parent connect point names")
    return

    pcheck = set(x.name.decode() for x in nifcheck.connect_points_parent)
    assert pcheck == parentnames, f"Wrote correct parent names: {pcheck}"
    pcasingsrc = [cp for cp in nifsrc.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    pcasing = [cp for cp in nifcheck.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    assert NT.VNearEqual(pcasing.rotation[:], pcasingsrc.rotation[:]), f"Have correct rotation: {pcasing}"


    sgcheck = nifcheck.shape_dict['CombatShotgunReceiver:0']
    assert sgcheck.blockname == 'BSTriShape', f"Have correct blockname: {sgcheck.blockname}"


def TEST_CONNECT_WEAPON_PART():
    """Selected connect points used to parent new import"""
    # When a connect point is selected and then another part is imported that connects
    # to that point, they are connected in Blender.
    
    testfile = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    partfile = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel_1.nif")
    partfile2 = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunGlowPinSight.nif")

    # Import of mesh with parent connect points works correctly.
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 do_create_bones=False, 
                                 do_rename_bones=False, 
                                 do_create_collections=True)

    barrelpcp = TTB.assert_exists('BSConnectPointParents::P-Barrel')
    magpcp = TTB.assert_exists('BSConnectPointParents::P-Mag')
    scopepcp = TTB.assert_exists('BSConnectPointParents::P-Scope')

    # Import of child mesh connects correctly.
    BD.ObjectSelect([barrelpcp, magpcp, scopepcp], active=True)
    bpy.ops.import_scene.pynifly(filepath=partfile, 
                                 do_create_bones=False, 
                                 do_rename_bones=False, 
                                 do_create_collections=True)
    
    barrelccp = TTB.find_object('BSConnectPointChildren::C-Barrel')
    assert barrelccp, f"Barrel's child connect point found {barrelccp}"
    assert barrelccp.constraints['Copy Transforms'].target == barrelpcp, \
        f"Child connect point connected to parent connect point: {barrelccp.constraints['Copy Transforms'].target}"

    BD.ObjectSelect([barrelpcp, magpcp, scopepcp], active=True)
    bpy.ops.import_scene.pynifly(filepath=partfile2, 
                                 do_create_bones=False, 
                                 do_rename_bones=False, 
                                 do_create_collections=True)
    
    scopeccp = TTB.find_object('BSConnectPointChildren::C-Scope')
    assert scopeccp, f"Scope's child connect point found {scopeccp}"
    assert scopeccp.constraints['Copy Transforms'].target == scopepcp, \
        f"Child connect point connected to parent connect point: {scopeccp.constraints['Copy Transforms'].target}"
    

def TEST_CONNECT_IMPORT_MULT():
    """When multiple weapon parts are imported in one command, they are connected up"""

    testfiles = [{"name": TTB.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")}, 
                 {"name": TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel.nif")}, 
                 {"name": TTB.test_file(r"tests\FO4\Shotgun\Stock.nif")} ]
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
    """Furniture markers work"""

    testfile = TTB.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_FURN_MARKER1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 2, f"Found furniture markers: {fmarkers}"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    bench = TTB.find_shape("FarmBench01:5")
    bench.select_set(True)
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
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
    """Furniture markers work"""

    testfile = TTB.test_file(r"tests\SkyrimSE\commonchair01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_FURN_MARKER2.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 1, f"Found furniture markers: {fmarkers}"
    assert NT.VNearEqual(fmarkers[0].rotation_euler, (-math.pi/2, 0, 0)), f"Marker points the right direction"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    TTB.find_shape("CommonChair01:0").select_set(True)
    TTB.find_shape("BSXFlags", type='EMPTY').select_set(True)
    TTB.find_shape("BSFurnitureMarkerNode", type='EMPTY').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    fmcheck = nifcheck.furniture_markers

    assert len(fmcheck) == 1, f"Wrote the furniture marker correctly: {len(fmcheck)}"
    assert fmcheck[0].entry_points == 13, f"Entry point data is correct: {fmcheck[0].entry_points}"


def TEST_FO4_CHAIR():
    """Furniture markers are imported and exported"""

    testfile = TTB.test_file(r"tests\FO4\FederalistChairOffice01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_FO4_CHAIR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert len(fmarkers) == 4, f"Found furniture markers: {fmarkers}"
    # Lowest points forward off the seat
    seatmarker = [m for m in fmarkers if BD.NearEqual(m.location.z, 34, epsilon=1)]
    assert len(seatmarker) == 1, f"Have one marker on the seat"
    mk = seatmarker[0]
    assert NT.VNearEqual(mk.rotation_euler, (-math.pi/2, 0, 0)), \
        f"Marker {mk.name} points the right direction: {mk.rotation_euler, (-math.pi/2, 0, 0)}"

    # -------- Export --------
    chair = TTB.find_shape("FederalistChairOffice01:2")
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
    """
    Test pipboy import/export. Very complex node hierarchy. Animations on multiple nodes
    but no controller sequences.
    """

    def cmp_xf(a, b):
        axf = BD.transform_to_matrix(a.global_transform)
        bxf = BD.transform_to_matrix(b.global_transform)
        assert TTB.MatNearEqual(axf, bxf), f"{a.name} transform preserved: \n{axf}\n != \n{bxf}"

    testfile = TTB.test_file(r"tests\FO4\PipBoy_Simple.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_PIPBOY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    TT.assert_true(bpy.data.objects['TapeDeckLid'].animation_data is not None, \
                   "TapeDeckLid animation data")
    TT.assert_eq(max([fc.keyframe_points[-1].co[0] 
                      for fc in BD.action_fcurves(bpy.data.objects['TapeDeckLid'].animation_data.action)]), 
                      49, 
                      "Max keyframe")
    TT.assert_eq(bpy.context.scene.frame_end, 49, "Scene end frame")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    nifcheck = pyn.NifFile(outfile)
    TT.assert_true(nifcheck.nodes.get("PipboyBody"), f"Exported PipboyBody")
    TT.assert_true(nifcheck.nodes.get("TapeDeck01"), f"Exported TapeDeck01")
    TT.assert_eq(nifcheck.nodes["TapeDeck01"].parent.name, nifcheck.nodes["PipboyBody"].name, 
                 f"TapeDeck01 parent")
    TT.assert_eq(nifcheck.nodes["TapeDeckLid"].parent.name, nifcheck.nodes["TapeDeck01"].name, 
                 f"TapeDeckLid parent")
    TT.assert_eq(nifcheck.nodes["TapeDeckLid_mesh"].parent.name, nifcheck.nodes["TapeDeckLid"].name, 
                 f"TapeDeckLid_mesh parent")
    TT.assert_eq(nifcheck.shape_dict["TapeDeckLid_mesh:1"].parent.name,
                 nifcheck.nodes["TapeDeckLid_mesh"].name, 
                 f"TapeDeckLid_mesh:1 parent")

    niftest = pyn.NifFile(testfile)

    cmp_xf(nifcheck.nodes["TapeDeck01"], niftest.nodes["TapeDeck01"])
    cmp_xf(nifcheck.nodes["TapeDeckLid"], niftest.nodes["TapeDeckLid"])
    cmp_xf(nifcheck.nodes["TapeDeckLid_mesh"], niftest.nodes["TapeDeckLid_mesh"])
    cmp_xf(nifcheck.shape_dict["TapeDeckLid_mesh:1"], niftest.shape_dict["TapeDeckLid_mesh:1"])

    assert nifcheck.rootNode.controller is None, "Root controller is None"
    assert nifcheck.nodes["PipboyBody"].controller is not None, "PipboyBody controller is not None"
    assert nifcheck.nodes["TapeDeckLid"].controller is not None, "TapeDeckLid controller is not None"


def TEST_BABY():
    """Non-human skeleton, lots of shapes under one armature."""
    # Can intuit structure if it's not in the file
    testfile = TTB.test_file(r"tests\FO4\baby.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_BABY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, do_create_bones=False, do_rename_bones=False)
    
    head = bpy.data.objects['Baby_Head:0']
    eyes = bpy.data.objects['Baby_Eyes:0']
    assert head['pynBlockName'] == "BSTriShape", f"Error: Expected BSTriShape on skinned shape, got {testhead.blockname}"

    BD.ObjectSelect([head, eyes], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True)

    testnif = pyn.NifFile(outfile)
    testhead = testnif.shape_by_root('Baby_Head')
    testeyes = testnif.shape_by_root('Baby_Eyes')
    assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
    assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"
    assert testhead.blockname == "BSTriShape", f"Error: Expected BSTriShape on skinned shape, got {testhead.blockname}"


def TEST_ROTSTATIC():
    """Test that statics are transformed according to the shape transform"""
    testfile = TTB.test_file(r"tests/Skyrim/rotatedbody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ROTSTATIC.nif")
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
    """Test that statics are transformed according to the shape transform"""

    testfile = TTB.test_file(r"tests/FO4/Meshes/SetDressing/Vehicles/Crane03_simplified.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    glass = bpy.data.objects["Glass:0"]
    assert int(glass.location[0]) == -107, f"Locaation is incorret, got {glass.location[:]}"
    assert round(glass.matrix_world[0][1], 4) == -0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[0][1], 4)} != -0.9971"
    assert round(glass.matrix_world[2][2], 4) == 0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[2][2], 4)} != 59.2036"


def TEST_FACEBONES():
    """Can read and write facebones correctly"""
    # A few of the facebones have transforms that don't match the rest. The skin-to-bone
    # transforms have to be handled correctly or the face comes in slightly warped.
    # Also the skin_bone_C_MasterEyebrow is included in the nif but not used in the head.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\FO4\BaseFemaleHead_faceBones.nif")
    goodfile = TTB.test_file(r"tests\FO4\BaseFemaleHead.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_FACEBONES.nif", output=1)
    resfile = TTB.test_file(f"tests/Out/TEST_FACEBONES_facebones.nif", output=1)

    # Facebones files have NiTransformController nodes for reasons I don't understand. We
    # don't want to muck with those.
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 do_import_animations=False)

    head = TTB.find_shape("BaseFemaleHead_faceBones:0")
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
    
    assert not NT.VNearEqual(head.data.vertices[1523].co, Vector((1.7168, 5.8867, -4.1643))), \
        f"Vertex is at correct place: {head.data.vertices[1523].co}"

    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # For unknown reasons, FO4 facebones files have different transforms from the base
    # head. When we export, we export a nif that can be used as a base head. So check what
    # we wrote against the base head, not the facebones file we started with.
    nifgood = pyn.NifFile(goodfile)
    nifch = pyn.NifFile(outfile)
    for nm, n in nifgood.nodes.items():
        if n.parent is not None and nm not in ["Neck", "BaseFemaleHead:0"]:
            # Skip root node and bones that aren't actually used. 
            # Skip shape because names and transforms will be different.
            assert nm in nifch.nodes, f"Found node {nm} in output file"
            assert NT.XFNearEqual(nifch.nodes[nm].transform, n.transform), f"""
Transforms for output and input node {nm} match:
{nifch.nodes[nm].transform}
{n.transform}
"""
            assert NT.XFNearEqual(nifch.nodes[nm].global_transform, nifgood.nodes[nm].global_transform), f"""
Transforms for output and input node {nm} match:
{nifch.nodes[nm].global_transform}
{nifgood.nodes[nm].global_transform}
"""

def TEST_FACEBONES_RENAME():
    """Facebones are renamed from Blender to the game's names"""

    testfile = TTB.test_file(r"tests/FO4/basemalehead_facebones.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FACEBONES_RENAME.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_FACEBONES_RENAME_facebones.nif")
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
    

def TEST_ANIM_ANIMATRON():
    """Can read a FO4 animatron nif"""
    # The animatrons are very complex and their pose and bind positions are different. The
    # two shapes have slightly different bind positions, though they are a small offset
    # from each other.

    testfile = TTB.test_file(r"tests/FO4/AnimatronicNormalWoman-body.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIM_ANIMATRON.nif")
    outfile_fb = TTB.test_file(r"tests/Out/TEST_ANIM_ANIMATRON.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 do_create_bones=False, 
                                 do_rename_bones=False, 
                                 do_import_pose=False)

    sh = TTB.find_shape('BodyLo:0')
    arms = TTB.find_shape('BodyLo:1')
    minv, maxv = TTB.get_obj_bbox(sh)
    assert NT.VNearEqual(minv, Vector((-13.14, -7.83, 38.6)), 0.1), f"Bounding box min correct: {minv}"
    assert NT.VNearEqual(maxv, Vector((14.0, 12.66, 133.5)), 0.1), f"Bounding box max correct: {maxv}"


    arma = arms.modifiers[0].object
    spine2 = arma.data.bones['SPINE2']
    hand = arma.data.bones['RArm_Hand']
    handpose = arma.pose.bones['RArm_Hand']
    assert spine2.matrix_local.translation.z > 30, f"SPINE2 in correct position: {spine2.matrix_local.translation}"
    assert NT.VNearEqual(handpose.matrix.translation, [18.1848, 2.6116, 68.6298]), f"Hand position matches Nif: {handpose.matrix.translation}"

    # thighl = arma.data.bones['LLeg_Thigh']
    # cp_armorleg = TTB.find_shape("BSConnectPointParents::P-ArmorLleg", type='EMPTY')
    # assert cp_armorleg["pynConnectParent"] == "LLeg_Thigh", f"Connect point has correct parent: {cp_armorleg['pynConnectParent']}"
    # assert NT.VNearEqual(cp_armorleg.location, thighl.matrix_local.translation, 0.1), \
    #     f"Connect point at correct position: {cp_armorleg.location} == {thighl.matrix_local.translation}"

    assert arma, f"Found armature '{arma.name}'"
    lleg_thigh = arma.data.bones['LLeg_Thigh']
    assert lleg_thigh.parent, f"LLeg_Thigh has parent"
    assert lleg_thigh.parent.name == 'Pelvis', f"LLeg_Thigh parent is {lleg_thigh.parent.name}"

    bpy.ops.object.select_all(action='DESELECT')
    sh.select_set(True)
    TTB.find_shape('BodyLo:1').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', preserve_hierarchy=True,
                                 export_pose=True)

    impnif = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile_fb)
    sh_out = nifout.shapes[0]
    assert sh_out.name == 'BodyLo:0', f"Exported shape: {sh_out.name}"
    minv_out, maxv_out = TTB.get_shape_bbox(sh_out)
    assert NT.VNearEqual(minv_out, minv), f"Minimum bounds equal: {minv_out} == {minv}"
    assert NT.VNearEqual(maxv_out, maxv), f"Minimum bounds equal: {maxv_out} == {maxv}"
    sp2_out = nifout.nodes['SPINE2']
    assert sp2_out.parent.name == 'SPINE1', f"SPINE2 has parent {sp2_out.parent.name}"
    sp2_in = impnif.nodes['SPINE2']
    assert TTB.MatNearEqual(BD.transform_to_matrix(sp2_out.transform), BD.transform_to_matrix(sp2_in.transform)), \
        f"Transforms are equal: \n{sp2_out.transform}\n==\n{sp2_in.transform}"


def TEST_ANIMATRON_2():
    """Can read the FO4 astronaut animatron nif"""
    # The animatrons are very complex and their pose and bind positions are different. The
    # two shapes have slightly different bind positions, though they are a small offset
    # from each other.
    testfile = TTB.test_file(r"tests\FO4\AnimatronicSpaceMan.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIMATRON_2.nif")
    outfile_fb = TTB.test_file(r"tests/Out/TEST_ANIMATRON_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 do_create_bones=False, 
                                 do_rename_bones=False, 
                                 do_import_pose=True)
 

def TEST_CUSTOM_BONES():
    """Can handle custom bones correctly"""
    # These nifs have bones that are not part of the vanilla skeleton.

    testfile = TTB.test_file(r"tests\FO4\VulpineInariTailPhysics.nif")
    testfile = TTB.test_file(r"tests\FO4\BrushTail_Male_Simple.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_CUSTOM_BONES.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    nifimp = pyn.NifFile(testfile)
    bone_in_xf = BD.transform_to_matrix(nifimp.nodes['Bone_Cloth_H_003'].global_transform)

    obj = bpy.data.objects['BrushTailBase']
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    test_in = pyn.NifFile(outfile)
    new_xf = BD.transform_to_matrix(test_in.nodes['Bone_Cloth_H_003'].global_transform)
    assert TTB.MatNearEqual(bone_in_xf, new_xf), f"Bone 'Bone_Cloth_H_003' preserved (new/original):\n{new_xf}\n==\n{bone_in_xf}"
        

def TEST_COTH_DATA():
    """Can read and write cloth data"""
    # Cloth data is extra bones that are enabled by HDT-type physics. Since they aren't 
    # part of the skeleton they can create problems.
    #
    # Also tests that we handle grayscale shading while we're here.

    testfile = TTB.test_file(r"tests/FO4/HairLong01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COTH_DATA.nif")
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


def TEST_IMP_NORMALS():
    """Can import normals from nif shape"""

    testfile = TTB.test_file(r"tests/Skyrim/cube.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # all loop custom normals point off at diagonals
    obj = bpy.context.object
    try:
        obj.data.calc_normals_split()
    except:
        pass
    for l in obj.data.loops:
        for i in [0, 1, 2]:
            assert round(abs(l.normal[i]), 3) == 0.577, f"Expected diagonal normal, got loop {l.index}/{i} = {l.normal[i]}"


def TEST_UV_SPLIT():
    """Can split UVs properly"""
    filepath = TTB.test_file("tests/Out/TEST_UV_SPLIT.nif")

    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.export_scene.pynifly(filepath=filepath, target_game="SKYRIM")
    
    nif_in = pyn.NifFile(filepath)
    obj = nif_in.shapes[0]
    assert len(obj.verts) == 14, f"Verts were split: {len(obj.verts)}"
    assert len(obj.uvs) == 14, f"Same number of UV points: {len(obj.uvs)}"
    assert NT.VNearEqual(obj.verts[2], obj.verts[10]), f"Split verts at same location {obj.verts[2]}, {obj.verts[10]}"
    assert not NT.VNearEqual(obj.uvs[2], obj.uvs[10]), f"Split UV at different location {obj.uvs[2]}, {obj.uvs[10]}"


def TEST_JIARAN():
    """Armature with no stashed transforms exports correctly"""
    outfile =TTB.test_file(r"tests/Out/TEST_JIARAN.nif")
     
    TTB.export_from_blend(r"tests\SKYRIMSE\jiaran.blend", "hair.001", 'SKYRIMSE', outfile)

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected Jiaran nif"


def TEST_SKEL_HKX_IMPORT():
    """Skeletons can be imported from HKX files."""
    testfile = TTB.test_file("tests/Skyrim/skeleton.hkx")
    # outfile = TTB.test_file("tests/out/TEST_SKEL_HKX.xml")

    # bpy.ops.import_scene.skeleton_xml(filepath=testfile)
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile)
    
    rootobj = next(x for x in bpy.data.objects if 'pynRoot' in x)
    assert BD.VNearEqual(rootobj.scale, [1,1,1]), f"Scale is 1.0"

    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')

    rootbone = arma.data.bones["NPC Root"]
    assert rootbone, f"Have root bone"

    headbone = arma.data.bones["NPC Head"]
    handbone = arma.data.bones["NPC Hand.L"]
    assert BD.NearEqual(headbone.matrix_local.translation[2], 120.3436), f"Head bone where it should be" 
    assert BD.NearEqual(handbone.matrix_local.translation[0], -28.9358), f"L Hand bone where it should be" 
    assert headbone.parent.name == "NPC Neck", f"Bone has correct parent."
    # bonesvert = sorted(arma.data.bones, key=lambda b: b.matrix_local.translation)
    # assert BD.NearEqual(bonesvert[0].matrix_local.translation[2], 0), f"Lowest bone at 0"
    # assert BD.NearEqual(bonesvert[-1].matrix_local.translation[2], 124), f"Highest bone near 124"

    BD.ObjectSelect([arma], active=True)


def TEST_SKEL_XML():
    """Can export selected bones as a skeleton XML file."""
    # TODO: Decide if this functionality is worth it, or whether we should turn this into 
    # exporting in HKX format. Note TEST_SKEL_TAIL_HKX tests export in HKX format.
    testfile = TTB.test_file("tests/Skyrim/skeletonbeast_vanilla.nif")
    outfile = TTB.test_file("tests/out/TEST_SKEL_XML.xml")

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

    incheck = pyn.NifFile(testfile)
    outcheck = pyn.hkxSkeletonFile(outfile)
    inhead = incheck.nodes["TailBone05"]
    outhead = outcheck.nodes["TailBone05"]
    assert inhead.properties.transform.NearEqual(outhead.properties.transform), f"Have same tail transform"


def TEST_SKEL_TAIL_HKX():
    """Can import and export a HKX skeleton file."""
    testfile = TTB.test_file(r"tests\Skyrim\tailskeleton.hkx")
    outfile = TTB.test_file("tests/out/TEST_SKEL_TAIL_HKX.hkx")

    bpy.ops.import_scene.pynifly_hkx(filepath=testfile, 
                                     use_blender_xf=False, 
                                     do_rename_bones=False, 
                                     do_import_collisions=False)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma and arma.type=='ARMATURE', f"Loaded armature: {arma}"
    bpy.ops.object.select_all(action='DESELECT')
    BD.ObjectSelect([arma], active=True)

    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        b.bone.select = True

    bpy.ops.export_scene.skeleton_hkx(filepath=outfile)

    hkx_in = pyn.hkxSkeletonFile(testfile)
    hkx_out = pyn.hkxSkeletonFile(outfile)
    tbin = hkx_in.nodes['TailBone03']
    tbout = hkx_out.nodes['TailBone03']
    assert tbin.parent.name == tbout.parent.name, "Have same parents"
    assert tbin.properties.transform.NearEqual(tbout.properties.transform), "Have same transforms"

    # TT.hide_all()
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile, 
                                     use_blender_xf=False, 
                                     do_rename_bones=False, 
                                     do_import_collisions=False)
    
    armacheck = bpy.context.object
    assert BD.MatNearEqual(arma.data.bones['TailBone01'].matrix_local, 
                           armacheck.data.bones['TailBone01'].matrix_local), \
        f"Have matching transforms."


def TEST_AUXBONES_EXTRACT():
    """Can extract an auxbones skeleton from a full skeleton."""
    testfile = TTB.test_file(r"tests\Skyrim\skeletonbeast_vanilla.nif")
    outfile = TTB.test_file("tests/out/TEST_AUXBONES_EXTRACT.hkx")
    checkfile = TTB.test_file(r"tests\Skyrim\tailskeleton.hkx")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 use_blender_xf=False, 
                                 do_rename_bones=False, 
                                 do_import_collisions=False)
    
    arma = bpy.context.object
    assert arma and arma.type=='ARMATURE', f"Loaded armature: {arma}"

    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        b.bone.select = ("TailBone" in b.name)

    bpy.ops.export_scene.skeleton_hkx(filepath=outfile)

    hkx_check = pyn.hkxSkeletonFile(checkfile)
    hkx_out = pyn.hkxSkeletonFile(outfile)
    assert len(hkx_check.nodes) == len(hkx_out.nodes), "All nodes exported"
    for nodename in [n for n in hkx_check.nodes if n != hkx_check.rootName]:
        nodecheck = hkx_check.nodes[nodename]
        nodeout = hkx_out.nodes[nodename]
        assert nodecheck.transform.NearEqual(nodeout.transform), \
            f"Transforms match on {nodename}"
        if nodecheck.parent:
            assert nodecheck.parent.name == nodeout.parent.name, f"Bones have same parent"
        else:
            assert nodeout.parent == None, f"Neither bone has parent"
    assert hkx_check.root.transform.NearEqual(hkx_out.root.transform), f"Root transforms match"


def TEST_FONV():
    """Basic FONV mesh import and export"""
    testfile = TTB.test_file("tests/FONV/9mmscp.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_FONV.nif")
     
    bpy.ops.import_scene.pynifly(filepath=testfile)
    grip = bpy.data.objects['Ninemm:0']
    coll = bpy.data.objects['bhkConvexVerticesShape']
    colbb = TTB.get_obj_bbox(coll)
    assert grip is not None, f"Have grip"
    assert NT.VNearEqual(colbb[0], (-4.55526, -6.1704, -1.2513), epsilon=0.1), f"Collision bounding box near correct min: {colbb}"
    assert NT.VNearEqual(colbb[1], (15.6956, 10.2399, 1.07098), epsilon=2.0), f"Collision bounding box near correct max: {colbb}"
    # TODO: Check collision object. It's coming in 10x the size

    bpy.ops.object.select_all(action="SELECT")
    BD.ObjectActive(grip)

    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifin = pyn.NifFile(testfile)
    gripin = nifin.shape_dict["Ninemm:0"]
    nifout = pyn.NifFile(outfile)
    assert nifout.game == 'FO3', f"Have correct game: {nifout.game}"
    gripout = nifout.shape_dict["Ninemm:0"]
    TTB.compare_shapes(gripin, gripout, grip)

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
    assert NT.NearEqual(minxin, minxout), f"Min collision shape bounds equal X: {minxin} == {minxout}"
    maxzin = max(v[2] for v in colshapein.vertices)
    maxzout = max(v[2] for v in colshapeout.vertices)
    assert NT.NearEqual(maxzin, maxzout), f"Max collision shape bounds equal Z: {maxzin} == {maxzout}"


def TEST_FONV_BOD():
    """Basic FONV body part import and export"""
    testfile = TTB.test_file(r"tests\FONV\outfitf_simple.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_FONV_BOD.nif")
     
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = bpy.data.objects['Arms01']
    bodybb = TTB.get_obj_bbox(body)
    assert NT.NearEqual(bodybb[0][0], -44.4, epsilon=0.1), f"Min X correct: {bodybb[0][0]}"
    assert NT.NearEqual(bodybb[1][2], 110.4, epsilon=0.1), f"Max Z correct: {bodybb[1][2]}"

    BD.ObjectSelect([body], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    testnif = pyn.NifFile(testfile)
    outnif = pyn.NifFile(outfile)
    TTB.compare_shapes(testnif.shape_dict["Arms01"], 
                   outnif.shape_dict["Arms01"],
                   body)


def TEST_ANIM_NOBLECHEST():
    """Read and write the animation of chest opening and shutting."""
    # The chest has two top-level named animations, Open and Close
    testfile = TTB.test_file(r"tests\Skyrim\noblechest01.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_ANIM_NOBLECHEST.nif")

    #### READ ####

    bpy.context.scene.render.fps = 30
    bpy.ops.import_scene.pynifly(filepath=testfile)

    lid = bpy.data.objects["Lid01"]
    animations = ["Open", "Close"]
    assert lid.animation_data is not None
    TT.assert_contains(lid.animation_data.action.name, animations, "animations exist")
    TT.assert_samemembers(animations, bpy.data.actions.keys(), "Have all animations")
    TT.assert_gt(bpy.context.scene.frame_end, 12, "Have enough frames for animation")

    cur_fps = bpy.context.scene.render.fps
    end_frame = 0.5 * cur_fps + 1
    TT.assert_seteq([m.name for m in lid.animation_data.action.pose_markers], ["start", "end"], "Have markers")
    # assert bpy.context.scene.timeline_markers[1].name == "end", f"Marker exists"
    # assert bpy.context.scene.timeline_markers[1].frame == end_frame, f"Correct frame"
    TT.assert_equiv(lid.animation_data.action.pose_markers[1].frame, 16, "Have markers on action", e=0.0001)
    # assert math.isclose(
    #     bpy.data.actions["ANIM|Close|Lid01"]["pynMarkers"]["end"], 0.5, abs_tol=0.0001), f"Have markers on aactions"

    ### WRITE ###

    chestroot = bpy.data.objects['NobleChest01:ROOT']
    BD.ObjectSelect([chestroot], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    ### CHECK ###

    nifcheck = pyn.NifFile(outfile)
    
    # Controller Manager
    CheckNif(nifcheck, testfile)


def TEST_ANIM_DWEMER_CHEST():
    """Read and write the animation of chest opening and shutting."""
    testfile = TTB.test_file(r"tests\Skyrim\dwechest01.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_ANIM_DWEMER_CHEST.nif")

    #### READ ####

    bpy.context.scene.frame_end = 37
    bpy.context.scene.render.fps = 60 

    bpy.ops.import_scene.pynifly(filepath=testfile)
    lid = bpy.data.objects["Box01"]
    # animations = ['ANIM|Close|Box01', 'ANIM|Close|Gear07', 'ANIM|Close|Gear08', 
    #               'ANIM|Close|Gear09', 'ANIM|Close|Handle', 'ANIM|Close|Object01', 
    #               'ANIM|Close|Object02', 'ANIM|Close|Object188', 'ANIM|Close|Object189',
    #               'ANIM|Open|Box01', 'ANIM|Open|Gear07', 'ANIM|Open|Gear08', 
    #               'ANIM|Open|Gear09', 'ANIM|Open|Handle', 'ANIM|Open|Object01', 
    #               'ANIM|Open|Object02', 'ANIM|Open|Object188', 'ANIM|Open|Object189']
    animations = ['Close', 'Open']
    for anim in animations:
        TT.assert_contains(anim, bpy.data.actions, f"Animations")
    assert lid.animation_data is not None
    TT.assert_contains(lid.animation_data.action.name, animations, "Active animation")
    TT.assert_gt(len(lid.animation_data.action.fcurves), 0, "Have curves")
    TT.assert_eq(lid.animation_data.action.fcurves[0].data_path, "location", "data path")

    gear07 = bpy.data.objects["Gear07"]
    TT.assert_contains(gear07.animation_data.action.name, animations, "Gear animation")
    gear_slot = gear07.animation_data.action_slot
    gear_fcurves = None
    cb = gear07.animation_data.action.layers[0].strips[0].channelbag(gear_slot)
    if cb:
        gear_fcurves = cb.fcurves
    assert gear_fcurves, "Have gear fcurves from action slot"
    TT.assert_eq(len(gear_fcurves), 3, "Have curves")
    gear07z = gear_fcurves[2]
    TT.assert_eq(gear07z.data_path, "rotation_euler", "Have correct data path")
    TT.assert_equiv(gear07z.keyframe_points[-1].co[0], 37.0, "Have correct time")
    TT.assert_equiv(gear07z.keyframe_points[0].co[1], 0, "Start Z value")
    TT.assert_equiv(gear07z.keyframe_points[-1].co[1], 3.1416, "End Z value")

    gear07obj = gear07.children[0]
    TT.assert_eq(len(gear07obj.data.vertices), 476, "Have right number of vertices")

    #### WRITE ####

    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj],
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    #### CHECK ####

    nif2:pyn.NifFile = pyn.NifFile(outfile)
    cm2:pyn.NiControllerManager = nif2.root.controller
    mtt2:pyn.NiMultiTargetTransformController = cm2.next_controller
    # TT.assert_seteq([n.name for n in mtt2.extra_targets],
    #                 ["Object01", "Object02", "Object188", "Object189", "Gear07", 
    #                  "Gear08", "Gear09", "Handle", "Box01"],
    #                  f"MultiTargetTransformController {mtt2.id} extra targets")
    TT.assert_samemembers([s for s in cm2.sequences], ["Open", "Close"], "Controller Sequences")
    open2:pyn.NiControllerSequence = cm2.sequences["Close"]
    openblk:pyn.ControllerLink = next(b for b in open2.controlled_blocks if b.node_name == "Object01")
    TT.assert_eq(openblk.controller.id, mtt2.id, "Controller IDs")


def TEST_ANIM_ALDUIN():
    """Read and write animation using bones."""
    testfile = TTB.test_file(r"tests\SkyrimSE\loadscreenalduinwall.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIM_ALDUIN.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 do_create_bones=False, 
                                 do_rename_bones=False,
                                 do_import_animations=True,
                                 use_blender_xf=True)
    
    # Didn't rename the bones on import
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert "NPC COM" in arma.data.bones, "Have 'NPC COM'"

    # Transforms are correct for selected bones
    nif = pyn.NifFile(testfile)
    TT.assert_contains("MagicEffectsNode", arma.data.bones, "Have magic effect node")

    lcalf = arma.data.bones['NPC LLegCalf']
    lcalfp = arma.pose.bones['NPC LLegCalf']
    TT.assert_eq(lcalfp.rotation_mode, "QUATERNION", "L calf bone rotation mode")
    lcalf_fc = [fc for fc in arma.animation_data.action.fcurves 
                if 'NPC LLegCalf' in fc.data_path and 'location' not in fc.data_path]
    TT.assert_seteq([fc.keyframe_points[5].interpolation for fc in lcalf_fc], ['LINEAR'], "Left calf keyframe interpolation")

    # This nif has an alpha threshold, tho apparently not used, and vertex alpha. Make
    # sure the values come in correctly.
    alduin = TTB.find_object('AlduinAnim:0')
    anodes = alduin.active_material.node_tree.nodes
    bsdf = [s for s in anodes if 'Shader' in s.name][0]
    alpha = bsdf.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Threshold'].default_value, 5, "Alpha Threshold")
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, True, "Alpha Test")
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, False, "Alpha Blend")

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
        
    ### EXPORT ###

    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 preserve_hierarchy=True,)

    # No nodes are emitted more than once--no duplicate names.
    nifcheck = pyn.NifFile(outfile)
    TT.assert_eq(len(nifcheck.node_ids), len(nifcheck.nodes), "No dup node names")
    rootbone = nifcheck.nodes['NPC Root [Root]']

    # Eyes are skinned
    eyes = nifcheck.nodes['AlduinAnim:1']
    TT.assert_seteq(eyes.bone_names, ['NPC Head'], "Eyes are skinned to head")

    # Rootbone's controller sets the time frame
    rootctlr = rootbone.controller
    TT.assert_equiv(rootctlr.properties.stopTime, 28.0, "stopTime")

    # We have not changed the name to "NPC COM [COM ]" because we picked up the setting
    # from the armature.
    assert "NPC COM" in nifcheck.nodes, "Have 'NPC COM'"
    
    # Check all the bone and interpolator transforms.
    TTB.check_bone_controllers(nif, nifcheck, ["NPC Root [Root]", "NPC COM", "NPC Pelvis"])
    nodenames1 = set()
    for s in nif.shapes:
        for bn in s.bone_names:
            nodenames1.add(bn)
    nodenames2 = set()
    for s in nifcheck.shapes:
        for bn in s.bone_names:
            nodenames2.add(bn)
    TT.assert_seteq(nodenames2, nodenames1, "Nodes")
    TTB.check_bone_controllers(nif, nifcheck, nodenames2)

    # combone_in:pyn.NiNode = nif.nodes['NPC COM']
    # cominterp_in:pyn.NiTransformInterpolator = combone_in.controller.interpolator
    # assert NT.VNearEqual(cominterp.properties.translation, cominterp_in.properties.translation), f"Have correct translation"
    # assert NT.VNearEqual(cominterp.properties.rotation, cominterp_in.properties.rotation), f"Have correct rotation"

    # Neck hub rotates around Z with quadratic interpolation.
    neckhub:pyn.NiNode = nifcheck.nodes['NPC NeckHub']
    neckctlr:pyn.NiTransformController = neckhub.controller
    neckinterp:pyn.NiTransformInterpolator = neckctlr.interpolator
    neckdat:pyn.NiTransformData = neckinterp.data
    TT.assert_gt(len(neckdat.zrotations), 0, "Neck Z rotation count")
    TT.assert_eq(neckdat.properties.zRotations.interpolation, pyn.NiKeyType.QUADRATIC_KEY, "Rotation type")


def TEST_ANIM_KF():
    """Read and write KF animation."""
    if bpy.app.version < (3, 5, 0): return

    testfile = TTB.test_file(r"tests\SkyrimSE\1hm_staggerbacksmallest.kf")
    testfile2 = TTB.test_file(r"tests\SkyrimSE\1hm_attackpowerright.kf")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_vanilla.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_ANIM_KF.kf")

    bpy.context.scene.render.fps = 30

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=False,
                                 do_import_animations=False,
                                 do_import_collisions=False,
                                 use_blender_xf=False)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect(arma, active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile)

    a = arma.animation_data.action
    TT.assert_eq(a.name, "1hm_staggerbacksmallest", "action name")
    TT.assert_gt(len(a.fcurves), 0, "fcurve count")

    # Check that the head moves over the course of the animation
    bpy.context.scene.frame_set(1)
    headpos = arma.pose.bones["NPC COM [COM ]"].location.copy()
    bpy.context.scene.frame_set(8)
    headpos2 = arma.pose.bones["NPC COM [COM ]"].location.copy()
    TT.assert_equiv_not(headpos, headpos2, "Head motion", e=0.001)

    # Loading a second animation shouldn't screw things up.
    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile2)

    TT.assert_eq(arma.animation_data.action.name, "1hm_attackpowerright", "action name after second import")
    TT.assert_eq(bpy.context.scene.frame_end, 36, "end frame")

    TT.assert_contains("1hm_staggerbacksmallest", bpy.data.actions, "first action still exists")

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

    # The animation we wrote is correct
    kfout = pyn.NifFile(outfile2)
    csout = kfout.rootNode
    TT.assert_eq(csout.name, 'TEST_ANIM_KF', "root node name")
    TT.assert_eq(csout.blockname, 'NiControllerSequence', "block type")
    TT.assert_eq(csout.properties.cycleType, nifdefs.CycleType.CLAMP, "cycle type")
    TT.assert_equiv(csout.properties.stopTime, 1.166667, "stop time")
    cb0 = csout.controlled_blocks[0]
    ti0 = cb0.interpolator
    td0 = ti0.data
    TT.assert_eq(td0.properties.translations.interpolation, pyn.NiKeyType.LINEAR_KEY, "key type")
    TT.assert_eq(td0.translations[0].time, 0, "First time value")
    TT.assert_equiv(td0.translations[0].value, (0.0, 0.0001, 57.8815), "translation", e=0.001)

    # Text key extra data
    TT.assert_eq([x[1] for x in csout.text_key_data.keys], 
                 [x[1] for x in csorig.text_key_data.keys], 
                 "text key labels")
    TT.assert_equiv([x[0] for x in csout.text_key_data.keys], 
                    [x[0] for x in csorig.text_key_data.keys], 
                    "text key values")

    controlled_block_thigh_out = [cb for cb in csout.controlled_blocks if cb.node_name == 'NPC L Thigh [LThg]'][0]
    ti_thigh_out = controlled_block_thigh_out.interpolator
    td_thigh_out = ti_thigh_out.data

    # The interpolator's transform must be correct (to match the bone).
    TT.assert_equiv(ti_thigh_out.properties.translation, ti_thigh_in.properties.translation, "Thigh Interpolator translation")
    mxout = Quaternion(ti_thigh_out.properties.rotation).to_matrix()
    mxorig = Quaternion(ti_thigh_in.properties.rotation).to_matrix()
    TT.assert_equiv(mxout, mxorig, "Thigh Interpolator rotation")
    
    # We've calculated the rotations properly--the rotation we wrote matches the original.
    k2mx = Quaternion(td_thigh_out.qrotations[0].value).to_matrix()
    k2mxorig = Quaternion(td_thigh_in.qrotations[0].value).to_matrix()
    TT.assert_equiv(k2mx, k2mxorig, "rotation keys")

    # Time signatures are calculated correctly.
    # We output at 30 fps so the number isn't exact.
    klast_out = td_thigh_out.qrotations[-1]
    klast_in = td_thigh_in.qrotations[-1]
    TT.assert_equiv(klast_out.time, klast_in.time, "final time signature")

    # Check feet transforms
    cb_foot_in = [cb for cb in csorig.controlled_blocks if cb.node_name == 'NPC L Foot [Lft ]'][0]
    ti_foot_in = cb_foot_in.interpolator
    td_foot_in = ti_foot_in.data
    cb_foot_out = [cb for cb in csout.controlled_blocks if cb.node_name == 'NPC L Foot [Lft ]'][0]
    ti_foot_out = cb_foot_out.interpolator
    td_foot_out = ti_foot_out.data
    TT.assert_equiv(ti_foot_out.properties.translation, ti_foot_in.properties.translation, "Foot Interpolator translation")
    mxout = Quaternion(ti_foot_out.properties.rotation).to_matrix()
    mxin = Quaternion(ti_foot_in.properties.rotation).to_matrix()
    TT.assert_equiv(mxout, mxin, "Foot Interpolator rotation")

    assert len(td_foot_out.qrotations) > 30 and len(td_foot_out.qrotations) < 40, \
        f"Have reasonable number of frames: {td_foot_out.qrotations}"


def TEST_ANIM_KF_RENAME():
    """Read and write KF animation with renamed bones."""
    if bpy.app.version < (3, 5, 0): return

    testfile = TTB.test_file(r"tests\Skyrim\sneakmtidle_original.kf")
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_ANIM_KF_RENAME.kf")

    bpy.context.scene.render.fps = 30
    # bpy.context.scene.frame_end = 665

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_animations=False,
                                 do_import_collisions=False,
                                 use_blender_xf=True)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile)

    anim = arma.animation_data.action
    assert len([fc for fc in anim.fcurves if 'NPC Pelvis' in fc.data_path]) > 0, f"Animating translated bone names"
    translation_curve = [fc for fc in anim.fcurves if 'Foot.L' in fc.data_path and 'location' in fc.data_path][0]
    TT.assert_eq(translation_curve.keyframe_points[0].interpolation, 'LINEAR', "Keyframe point interpolation")

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

    footcb:pyn.ControllerLink = next(x for x in nifcheck.rootNode.controlled_blocks if x.node_name == 'NPC L Foot [Lft ]')
    TT.assert_eq(footcb.controller_type, 'NiTransformController', "Controller Type")
    foottd = footcb.interpolator.data
    TT.assert_eq(len(foottd.qrotations), 333, f"Number of L Foot rotations")
    TT.assert_eq(foottd.properties.translations.interpolation, pyn.NiKeyType.LINEAR_KEY, "L Foot translation interpolation")
    TT.assert_eq(len(foottd.translations), 2, "Number of translation frames")
    timeinterval = foottd.qrotations[10].time - foottd.qrotations[9].time
    TT.assert_equiv(timeinterval, 1/30, "Rotation time interval")
    TT.assert_equiv(foottd.translations[1].time, 8.5333, "Second keyframe time")

    TT.assert_equiv(foottd.qrotations[10].time, tdin.qrotations[10].time, "time signatures")
    TT.assert_equiv(foottd.translations[1].value, tdin.translations[1].value, f"translation values")

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
    """Can import and export a HKX animation."""
    if bpy.app.version < (3, 5, 0): return

    # Check that this works when there are spaces in the path name
    testfile = TTB.test_file(r"tests\Skyrim\meshes\actors\character\character animations\1hm_staggerbacksmallest.hkx")
    # testfile2 = TTB.test_file(r"tests\Skyrim\1hm_attackpowerright.hkx")
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    outfile = TTB.test_file(r"tests/Out/created animations/TEST_ANIM_HKX.hkx")

    Path(outfile).parent.mkdir(parents=True, exist_ok=True)

    bpy.context.scene.render.fps = 30

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_collisions=False,
                                 do_import_animations=False,
                                 use_blender_xf=True)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile, 
                                     reference_skel=hkx_skel)

    assert len([fc for fc in arma.animation_data.action.fcurves if 'NPC Pelvis' in fc.data_path]) > 0, \
        f"Animating translated bone names"

    bpy.ops.export_scene.pynifly_hkx(filepath=outfile, reference_skel=hkx_skel)

    assert os.path.exists(outfile)


def TEST_ANIM_HKX_2():
    """Can import and export a non-human HKX animation."""
    if bpy.app.version < (3, 5, 0): return

    testfile = TTB.test_file(r"tests\Skyrim\troll.nif")
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_troll.nif")
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton_troll.hkx")
    hkx_anim = TTB.test_file(r"tests\Skyrim\troll_h2hattackleftd.hkx")
    outfile = TTB.test_file(r"tests/Out/created animations/TEST_ANIM_HKX_2.hkx")

    Path(outfile).parent.mkdir(parents=True, exist_ok=True)

    bpy.context.scene.render.fps = 30

    # Load the skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=False,
                                 do_import_collisions=False,
                                 do_import_animations=False)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    
    # Load the mesh
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Import an animation
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                     reference_skel=hkx_skel)
    
    assert arma.animation_data.action is not None, f"Have animation loaded"
    act = arma.animation_data.action
    clavcurv = [c for c in act.fcurves if c.data_path.startswith('pose.bones["NPC L Clavicle [LClv]"]')]
    assert len(clavcurv) > 0, f"Have LClv curves"

    # # Create a simple pose animation
    # BD.ObjectSelect([arma], active=True)
    # bpy.ops.object.mode_set(mode = 'POSE')
    # bpy.ops.pose.select_all(action='SELECT')
    # bpy.data.scenes["Scene"].frame_current = 1
    # bpy.ops.anim.keyframe_insert()
    # bpy.data.scenes["Scene"].frame_current = 2
    # bpy.ops.anim.keyframe_insert()
    # bpy.ops.object.mode_set(mode = 'OBJECT')

    # Export the animation
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile, reference_skel=hkx_skel)

    assert os.path.exists(outfile)


def TEST_ANIM_AUXBONES():
    """Can import and export an animation on an auxbones skeleton."""
    # SKIPPING
    print("Skipping TEST_ANIM_AUXBONES")
    # testfile = TTB.test_file(r"tests\Skyrim\SOSFastErect.hkx")
    # skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    # hkx_skel = TTB.test_file(r"tests\Skyrim\SOSskeleton.hkx")
    # outfile = TTB.test_file(r"tests/Out/created animations/TEST_ANIM_AUXBONES.hkx")

    # bpy.context.scene.render.fps = 60

    # # Animations are loaded into a skeleton
    # bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
    #                                  do_rename_bones=False,
    #                                  do_import_collisions=False,
    #                                  do_import_animations=False,
    #                                  use_blender_xf=False)
    
    # arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    # BD.ObjectSelect([arma], active=True)
    
    # bpy.ops.import_scene.pynifly_hkx(filepath=testfile, 
    #                                  reference_skel=hkx_skel)

    # baseb = arma.data.bones['NPC GenitalsBase [GenBase]']
    # poseb = arma.pose.bones['NPC GenitalsBase [GenBase]']
    # assert BD.MatNearEqual(baseb.matrix_local, poseb.matrix), f"Starting from base bone position"

    # bpy.ops.export_scene.pynifly_hkx(filepath=outfile, reference_skel=hkx_skel)

    # assert os.path.exists(outfile)


def TEST_IMPORT_TAIL():
    """Regression: Import of a single bodypart onto a skeleton should work correctly."""

    testfile = TTB.test_file(r"tests\Skyrim\meshes\actors\character\character animations\1hm_staggerbacksmallest.hkx")
    # testfile2 = TTB.test_file(r"tests\Skyrim\1hm_attackpowerright.hkx")
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    outfile = TTB.test_file(r"tests/Out/created animations/TEST_ANIM_HKX.hkx")

    bpy.context.scene.render.fps = 60

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 do_create_bones=False, 
                                 do_rename_bones=True,
                                 do_import_collisions=False,
                                 do_import_animations=False,
                                 use_blender_xf=True)
    

def TEST_TEXTURE_CLAMP():
    """Make sure we don't lose texture clamp mode."""
    testfile = TTB.test_file(r"tests\SkyrimSE\evergreen.nif")
    outfile = TTB.test_file(r"tests\out\TEST_TEXTURE_CLAMP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifin = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile)
    TT.assert_eq(nifin.shapes[0].shader.properties.textureClampMode,
            nifout.shapes[0].shader.properties.textureClampMode, \
            "clamp mode")


def TEST_MISSING_MAT():
    """We import and export properly even when files are missing."""
    testfile = TTB.test_file(r"tests\FO4\malehandsalt.nif")
    outfile = TTB.test_file(r"tests\out\TEST_MISSING_MAT.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    hands = bpy.context.object
    mat = hands.active_material
    assert mat['BSLSP_Shader_Name'] == r"Materials\foo\basehumanmaleskinhands.bgsm", \
        f"Have correct materials: {mat['BS_Shader_Block_Name']}"
    # assert 'SKIN_TINT' in mat['Shader_Flags_1'], f"Have correct flags: {mat['Shader_Flags_1']}"
    assert mat['Shader_Type'] == 'Skin_Tint', f"Have correct shader type: {mat['Shader_Type']}"
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifin = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile)
    assert (nifin.shapes[0].shader.properties.textureClampMode 
            == nifout.shapes[0].shader.properties.textureClampMode), \
        f"Preserved texture clamp mode: {nifout.shapes[0].shader.textureClampMode}"


def TEST_MISSING_FILES():
    """Write a good nif even if texture and materials files are missing."""
    blendfile = TTB.test_file(r"tests\FO4\Gloves.blend")
    outfile = TTB.test_file(r"tests\out\TEST_MISSING_FILES.nif")

    # Can't load the test blend file in 3.x
    if bpy.app.version[0] <= 3: return

    # append all objects starting with 'house'
    with bpy.data.libraries.load(blendfile) as (data_from, data_to):
        data_to.objects = [obj for obj in data_from.objects]

    # link them to scene
    scene = bpy.context.scene
    for obj in data_to.objects:
        if obj is not None:
            scene.collection.objects.link(obj)

    hands = next(obj for obj in bpy.context.scene.objects if obj.name.startswith('BaseMaleHands'))
    hands.active_material['BS_Shader_Block_Name'] = "BSLightingShaderProperty"
    hands.active_material['Shader_Type'] = "Skin_Tint"
    hands.active_material['BSShaderTextureSet_Diffuse'] = "actors/character/basehumanmale/basemalehands_d.dds"
    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj],
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    handsout = nifout.shape_dict['BaseMaleHands3rd_fitted:0']
    assert handsout.shader.name == r"Materials\actors\Character\BaseHumanMale\basehumanmaleskinhands.bgsm", \
        f"Have correct shader name: {handsout.shader.name}"
    # NOT WORKING: We should be able to set the shader type this way but in fact it's 
    # not working all the way down to the nifly level. Not sure why.
    # assert handsout.shader.properties.Shader_Type == nifdefs.BSLSPShaderType.Skin_Tint, \
    #     f"Have correct shader: {handsout.shader.properties.Shader_Type}"
    assert r"textures\actors\character\basehumanmale\basemalehands_d.dds" == handsout.textures['Diffuse'], \
        f"Have diffuse in texture list: {handsout.textures}"


def TEST_FULL_PRECISION():
    """Can set full precision."""
    testfile = TTB.test_file(r"tests\FO4\OtterFemHead.nif")
    outfile = TTB.test_file(r"tests\out\TEST_FULL_PRECISION.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    
    head = bpy.context.object
    deltaz = head.location.z
    for v in head.data.vertices:
        v.co.z += deltaz
    head.location.z += -deltaz
    head['hasFullPrecision'] = 1

    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    assert nifout.shapes[0].properties.hasFullPrecision, \
        f"Has full precision: {nifout.shapes[0].properties.hasFullPrecision}"


def TEST_EMPTY_NODES():
    """Empty nodes export with the rest."""
    testfile = TTB.test_file(r"tests\Skyrim\farmhouse01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_EMPTY_NODES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    root = [obj for obj in bpy.data.objects if 'pynRoot' in obj][0]
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    assert "L2_Ivy" in nifout.nodes, f"Has empty node"


def TEST_EMPTY_FLAGS():
    """Empty pyNodeFlags doesn't cause an error."""
    testfile = TTB.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_EMPTY_FLAGS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    
    obj = bpy.context.object
    assert obj['pynNodeFlags'] != "", f"pynNodeFlags is not empty"

    obj['pynNodeFlags'] = "XYZ"
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    assert "FarmBench01:5" in nifout.nodes, f"Has object"
    assert nifout.nodes["FarmBench01:5"].properties.flags == 0, f"Has zero flags"


def TEST_COLLISION_PROPERTIES():
    """Test some specific collision property values."""
    testfile = TTB.test_file(r"tests\SkyrimSE\SteelDagger.nif")
    outfile = TTB.test_file(r"tests\out\TEST_COLLISION_PROPERTIES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    root = [obj for obj in bpy.data.objects if 'pynRoot' in obj][0]
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    coll = nifout.rootNode.collision_object
    body = coll.body
    assert body.properties.broadPhaseType == nifdefs.BroadPhaseType.ENTITY, "Have correct broad phase type"
    assert body.properties.collisionResponse2 == nifdefs.hkResponseType.SIMPLE_CONTACT, "Have correct CollisionResponse2"
    assert body.properties.processContactCallbackDelay == 65535, "Have correct processContactCallbackDelay"
    assert body.properties.rollingFrictionMult == 0, "Have correct rollingFrictionMult"
    assert body.properties.motionSystem == nifdefs.hkMotionType.SPHERE_STABILIZED, "Have correct motionSystem"
    assert body.properties.solverDeactivation == nifdefs.hkSolverDeactivation.LOW, "Have correct solverDeactivation"
    assert body.properties.qualityType == nifdefs.hkQualityType.MOVING, "Have correct qualityType"


def XXX_TEST_COLLISION_FO4():
    """
    FO4 collision export: Not working. Requires an update to Nifly to handle FO4-format
    bhkRigidBody blocks.
    """
    testfile = TTB.test_file(r"tests\FO4\AlarmClock_Bare.nif")
    outfile = TTB.test_file(r"tests\out\TEST_COLLISION_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, use_blender_xf=True)
    root = [obj for obj in bpy.data.objects if 'pynRoot' in obj][0]
    clock = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH'][0]

    BD.ObjectSelect([clock], active=True)
    bpy.ops.object.duplicate()
    collobj = bpy.context.object
    collobj.name = "bhkConvexVerticesShape"

    bpy.ops.object.add(type='EMPTY')
    rb = bpy.context.object
    rb.name = "bhkRigidBody"
    rb['broadPhaseType'] = "ENTITY"
    collobj.parent = rb

    bpy.ops.object.add(type='EMPTY')
    coll = bpy.context.object
    coll.name = "bhkCollisionObject"
    coll['pynCollisionFlags'] = "SYNC_ON_UPDATE"
    rb.parent = coll
    coll.parent = root

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    coll = nifout.rootNode.collision_object
    body = coll.body
    assert coll.body
    # assert body.properties.broadPhaseType == nifdefs.BroadPhaseType.ENTITY, "Have correct broad phase type"
    # assert body.properties.collisionResponse2 == nifdefs.hkResponseType.SIMPLE_CONTACT, "Have correct CollisionResponse2"
    # assert body.properties.processContactCallbackDelay == 65535, "Have correct processContactCallbackDelay"
    # assert body.properties.rollingFrictionMult == 0, "Have correct rollingFrictionMult"
    # assert body.properties.motionSystem == nifdefs.hkMotionType.SPHERE_STABILIZED, "Have correct motionSystem"
    # assert body.properties.solverDeactivation == nifdefs.hkSolverDeactivation.LOW, "Have correct solverDeactivation"
    # assert body.properties.qualityType == nifdefs.hkQualityType.MOVING, "Have correct qualityType"


def TEST_FACEGEN():
    # FO4 facegen files are wonky. They have bones in the right positions, but without the
    # proper rotations. Fixing the rotations in the nif file shows the mesh undistorted.
    # So we need to figure out how to do the equivalent on import. Probably we should also
    # have an explicit "facgen" flag so the importer doesn't have to guess.
    """
    FO4 facegen import works--imported head is not distorted.
    """
    testfile = TTB.test_file(r"tests\FO4\facegen.nif")

    # Can't import pose locations for facegen files. This is testing that it works
    # correctly anyway.
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 do_create_bones=False,
                                 do_import_pose=True)
    head = [obj for obj in bpy.context.selected_objects if obj.name.startswith('FFODeerMaleHead')][0]
    eyes = [obj for obj in bpy.context.selected_objects if obj.name.startswith('FFOUngulateMaleEyes')][0]

    # Head in world coordinates should be taller than wide.
    diag = TTB.get_obj_bbox(head, worldspace=True);
    assert diag[1].x-diag[0].x < diag[1].z-diag[0].z, f"Head is taller than wide: {diag[1]-diag[0]}"
    exmin = min((eyes.matrix_world @ v.co).x for v in eyes.data.vertices)
    exmax = max((eyes.matrix_world @ v.co).x for v in eyes.data.vertices)
    assert BD.NearEqual(exmin, -4.7, epsilon=0.1), f"Eye min X correct: {exmin}"
    assert BD.NearEqual(exmax, 4.7, epsilon=0.1), f"Eye max X correct: {exmax}"


def UNITTEST_CUBE_INFO1():
    """Unit test to ensure we can analyze a rotated cube."""
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0,))
    cube = bpy.context.object
    cube.scale = Vector((1, 2, 3,))
    cube.rotation_mode = 'XYZ'
    testrot = (0.35, 1.4, 0)
    cube.rotation_euler = testrot
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    c, d, r = BD.find_box_info(bpy.context.object)
    assert BD.VNearEqual(c, (0, 0, 0)), f"Centerpoint at origin: {c}"
    assert BD.VNearEqual(d, (2, 4, 6)), f"Have correct dimensions: {d}"
    assert BD.VNearEqual(testrot, r.to_euler()[0:3]), f"Have correct rotation: {r}"


def UNITTEST_CUBE_INFO2():
    """Unit test to ensure we can analyze a rotated, translated cube."""
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0,))
    cube = bpy.context.object
    dims = Vector((1, 2, 3,))
    cube.scale = dims
    cube.rotation_mode = 'XYZ'
    testrot = (0.35, 1.4, 0.9)
    cube.rotation_euler = testrot
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    offset = Vector((3, 4, 5,))
    for v in cube.data.vertices:
        v.co += offset
    
    c, d, r = BD.find_box_info(bpy.context.object)
    # Centerpoint is returned as the world location of the geometric center.
    assert BD.VNearEqual(c, offset), f"Centerpoint at translated location: {c}"
    # Dimensions are in the box's local frame of reference. 
    assert BD.VNearEqual(d, dims*2), f"Have correct dimensions: {d}"
    # Rotation is what's required to rotate an aligned box to the actual box's position.
    assert BD.VNearEqual(testrot, r.to_euler()[0:3]), f"Have correct rotation: {r}"


def UNITTEST_CUBE_INFO3():
    """Unit test to ensure we can analyze a cube with translations and rotations on the object."""
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0,))
    cube = bpy.context.object
    dims = Vector((1, 2, 3,))
    cube.scale = dims
    cube.rotation_mode = 'XYZ'
    testrot = (0.35, 1.4, 0.9)
    cube.rotation_euler = testrot
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    offset = Vector((3, 4, 5,))
    for v in cube.data.vertices:
        v.co += offset
    
    objoffset = Vector((6, 7, 8,))
    objscale = 0.1
    cube.location = objoffset
    cube.scale = (objscale,)*3
    c, d, r = BD.find_box_info(bpy.context.object)
    # Centerpoint is returned as the world location of the geometric center.
    assert BD.VNearEqual(c, objoffset+cube.scale*offset), f"Centerpoint at translated location: {c}"
    # Dimensions are in world scale. 
    assert BD.VNearEqual(d, dims*2*cube.scale), f"Have correct dimensions: {d}"
    # Rotation is what's required to rotate an aligned box to the actual box's position.
    assert BD.VNearEqual(testrot, r.to_euler()[0:3]), f"Have correct rotation: {r}"


def LOAD_RIG():
    """Load an animation rig for play. Has to be invoked explicitly."""
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkxskelfile = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    bpfile1 = TTB.test_file(r"tests\Skyrim\malebody_1.nif")
    bpfile2 = TTB.test_file(r"tests\Skyrim\malehands_1.nif")
    bpfile3 = TTB.test_file(r"tests\Skyrim\malefeet_1.nif")
    bpfile4 = TTB.test_file(r"tests\Skyrim\malehead.nif")

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



# --- Quick and Dirty Test Harness ---

def testfrom(starttest):
    try:
        return alltests[alltests.index(starttest):]
    except:
        return alltests

def execute_test(t, passed_tests, failed_tests,stop_on_fail=True):
        # t = sys.modules[__name__].__dict__[t.__name__]
        if not t: return

        print (f"\n\n\n++++++++++++++++++++++++++++++ {t.__name__} ++++++++++++++++++++++++++++++")

        if t.__doc__: print (f"{t.__doc__}")
        TTB.clear_all()

        test_loghandler.start()
        if stop_on_fail:
            t()
            test_loghandler.finish()
            passed_tests.append(t)
        else:
            try:
                t()
                test_loghandler.finish()
                passed_tests.append(t)
            except:
                failed_tests.append(t)

        print (f"------------------------------ {t.__name__} ------------------------------\n")


def do_tests(
        target_tests=None,
        run_all=True,
        stop_on_fail=False,
        startfrom=None,
        exclude=[]):
    """Do tests in testlist. Can pass in a single test."""
    if not target_tests: 
        target_tests = [t for k, t in sys.modules[__name__].__dict__.items() if k.startswith('TEST_')]
        assert TEST_ANIM_NOBLECHEST in target_tests, "Have test"
    passed_tests = []
    failed_tests = []

    failed_tests = []
    try:
        for t in target_tests:
            break
    except:
        target_tests = [target_tests]

    startindex = 0
    if startfrom:
        try:
            startindex = target_tests.index(startfrom)
        except:
            pass
    for t in target_tests:
        if t not in exclude and t not in passed_tests and t not in failed_tests:
            execute_test(t, passed_tests, failed_tests, stop_on_fail=stop_on_fail)
    if run_all:
        for t in target_tests:
            if t not in exclude and t not in passed_tests and t not in failed_tests:
                execute_test(t, passed_tests, failed_tests, stop_on_fail=stop_on_fail)

    print(f"\n\n===Succesful tests===")
    print(", ".join([t.__name__ for t in passed_tests]))
    print(f"\n\n===Failed tests===")
    print(", ".join([t.__name__ for t in failed_tests]))
    if not failed_tests:
        print(f"""


=============================================================================
===                                                                       ===
===                      SUCCESS: {len(passed_tests):3d} test{"s" if len(passed_tests) != 1 else ""} passed{"" if len(passed_tests) != 1 else " "}                        ===
===                                                                       ===
=============================================================================
""")
    else:
        print(f"""


=============================================================================
===                                                                       ===
===                           TESTS FAILED                                ===
===                                                                       ===
{", ".join([t.__name__ for t in failed_tests])}
===                                                                       ===
=============================================================================
""")


def show_all_tests():
    for t in alltests:
        print(f"{t.__name__:25}{t.__doc__}")


if __name__ == "__main__":
    print("""
=============================================================================
===                                                                       ===
===                               TESTING                                 ===
===                                                                       ===
=============================================================================
""")

    if not bpy.data:
        # If running outside blender, just list tests.
        show_all_tests()
    else:
        # Tests of nifs with bones in a hierarchy
        # target_tests = [
        #     TEST_COLLISION_BOW_SCALE, TEST_BONE_HIERARCHY, TEST_COLLISION_BOW, 
        #     TEST_COLLISION_BOW2, TEST_COLLISION_BOW3, TEST_COLLISION_BOW_CHANGE, 
        #     TEST_ANIM_ANIMATRON, TEST_FACEGEN,]

        # All tests with animations
        # target_tests = [t for t in alltests if '_ANIM_' in t.__name__]

        # All tests with collisions
        # do_tests([t for t in alltests if 'COLL' in t.__name__])

        do_tests(
            target_tests=[ TEST_ANIM_SHADER_BSLSP ], run_all=False, stop_on_fail=True,
            # target_tests=[t for t in alltests if 'HKX' in t.__name__], run_all=False, stop_on_fail=True,
            )
        

