"""Automated tests for pyNifly export/import addon

Convenient setup for running these tests here: 
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""
import bpy
from mathutils import Matrix, Vector, Quaternion
from test_tools import *
from pynifly import *
from blender_defs import *
from trihandler import *


TEST_BPY_ALL = 0
TEST_BODYPART_SKY = 0 ### Skyrim head
TEST_BODYPART_FO4 = 0 ### FO4 head
TEST_IMP_EXP_SKY_2 = 0 ### Body+Armor
TEST_SKIN_BONE_XF = 0 ### Argonian head
TEST_IMP_EXP_SKY = 1 ### Skyrim armor
TEST_ARMATURE_EXTEND = 0 ### FO4 head + body
TEST_ARMATURE_EXTEND_BT = 0
TEST_NEW_COLORS = 0
TEST_VERTEX_COLOR_IO = 0
TEST_BONE_HIERARCHY = 0
TEST_CAVE_GREEN = 0
TEST_FACEBONE_EXPORT = 0
TEST_HYENA_PARTITIONS = 0
TEST_BONE_XPORT_POS = 0
TEST_NIFTOOLS_NAMES = 0
TEST_BOW = 0
TEST_SCALING_COLL = 0
TEST_COLLISION_MULTI = 0
TEST_COLLISION_CONVEXVERT = 0
TEST_CONNECT_POINT = 0
TEST_PIPBOY = 0
TEST_FACEBONES = 0
TEST_BONE_XF = 0
TEST_IMP_ANIMATRON = 0


if TEST_BPY_ALL or TEST_BODYPART_SKY:
    # Basic test that a Skyrim bodypart is imported correctly. 
    # Verts are organized around the origin, but skin transform is put on the shape 
    # and that lifts them to the head position.  
    test_title("TEST_BODYPART_SKY", "Can import a Skyrim head with armature")
    clear_all()
    testfile = test_file("tests\Skyrim\malehead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    male_head = bpy.context.selected_objects[0]
    assert round(male_head.location.z, 0) == 120, "ERROR: Object not elevated to position"
    assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"
    minz = min(v[2] for v in male_head.bound_box)
    maxz = max(v[2] for v in male_head.bound_box)
    assert minz < 0, f"Head extends below origin: {minz}"
    assert maxz > 0, f"Head extends above origin: {maxz}"

    
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
    minz = min(v[2] for v in male_head.bound_box)
    maxz = max(v[2] for v in male_head.bound_box)
    assert minz < 0, f"Head extends below origin: {minz}"
    assert maxz > 0, f"Head extends above origin: {maxz}"


if TEST_BPY_ALL or TEST_IMP_EXP_SKY_2:
    # Basic test that the import/export round trip works on nifs with multiple bodyparts. 
    # The body in this nif has no skin transform and the verts are where they appear
    # to be. The armor does have the usual transform on the shape and the skin, and the
    # verts are all below the origin. They have to be loaded into one armature.
    test_title("TEST_IMP_EXP_SKY_2", "Can read the armor nif with two shapes and spit it back out")
    clear_all()

    testfile = test_file(r"tests/Skyrim/test.nif")
    outfile = test_file(r"tests/Out/TEST_IMP_EXP_SKY_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = find_shape('MaleBody')
    armor = find_shape('Armor')
    assert NearEqual(armor.location.z, 120, epsilon=1.0), \
        f"Armor is raised to match body: {armor.location.z}"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    armor.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nifout = NifFile(outfile)
    impnif = NifFile(testfile)
    compare_shapes(impnif.shape_dict['MaleBody'], nifout.shape_dict['MaleBody'], body)
    compare_shapes(impnif.shape_dict['Armor'], nifout.shape_dict['Armor'], armor)

    check_unweighted_verts(nifout.shape_dict['MaleBody'])
    check_unweighted_verts(nifout.shape_dict['Armor'])
    assert NearEqual(body.location.z, 0), f"{body.name} not in lifted position: {body.location.z}"
    assert NearEqual(armor.location.z, 120.343582, 0.01), f"{armor.name} in lifted position: {armor.location.z}"
    assert "NPC R Hand [RHnd]" not in bpy.data.objects, f"Did not create extra nodes representing the bones"
        

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
        assert pelvis.parent.name == 'NPC COM', f"Pelvis has correct parent: {pelvis.parent}"
        assert pelvis.matrix_local.translation[2] == pelvis_pose.matrix.translation[2], \
            f"Pelvis pose position matches bone position: {pelvis_pose.matrix.translation[2]}"

        bpy.ops.object.select_all(action='DESELECT')
        armor.select_set(True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM", scale_factor=scale_factor)

        nifout = NifFile(outfile)

        compare_shapes(armorin, nifout.shape_dict['Armor'], armor, scale=scale_factor)
        check_unweighted_verts(nifout.shape_dict['Armor'])

    do_test(1.0)
    do_test(0.1)
        

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


if TEST_BPY_ALL or TEST_CAVE_GREEN:
    # Regression: Make sure the transparency is exported on this nif.
    test_title("TEST_CAVE_GREEN", "Cave nif can be exported correctly")
    clear_all()
    testfile = test_file(r"tests\SkyrimSE\caveghall1way01.nif")
    outfile = test_file(r"tests/Out/TEST_CAVE_GREEN.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    roots = find_shape("L2_Roots:5")

    bpy.ops.object.select_all(action='DESELECT')
    roots.select_set(True)
    bpy.ops.object.duplicate()

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheck = NifFile(outfile)
    rootscheck = nifcheck.shape_dict["L2_Roots:5"]
    assert rootscheck.has_alpha_property, f"Roots have alpha: {rootscheck.has_alpha_property}"


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
    # Vertex colors are loaded into Blender's color attribute. Alpha is loaded
    # into the VERTEX_ALPHA color attribute. The FO4 eye AO nif is wierd because 
    # it doesn't set the alpha bit, but does expect the alpha information to be
    # used.
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


if TEST_BPY_ALL or TEST_BONE_XPORT_POS:
    # Since we use a reference skeleton to make bones, we have to be able to handle
    # the condition where the mesh is not human and the reference skeleton should not
    # be used.
    test_title("TEST_BONE_XPORT_POS", 
               "Test that bones named like vanilla bones but from a different skeleton export to the correct position")

    clear_all()
    testfile = test_file(r"tests\Skyrim\draugr.nif")
    outfile = test_file(r"tests/Out/TEST_BONE_XPORT_POS.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False)
    
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


if TEST_BPY_ALL or TEST_NIFTOOLS_NAMES:
    # We allow renaming bones according to the NifTools format. Someday this may allow
    # us to use their animation tools, but this is not that day.
    test_title("TEST_NIFTOOLS_NAMES", "Can import nif with niftools' naming convention")
    clear_all()

    # ------- Load --------
    testfile = test_file(r"tests\SkyrimSE\body1m_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones_niftools=True)

    arma = find_shape("Body1M_1.nif")
    assert "NPC Calf [Clf].L" in arma.data.bones, f"Bones follow niftools name conventions {arma.data.bones.keys()}"
    #assert arma.data.niftools.axis_forward == "Z", f"Forward axis set to Z"

    c = arma.data.bones["NPC Calf [Clf].L"]
    assert c.parent, f"Bones are put into a hierarchy: {c.parent}"
    assert c.parent.name == "NPC Thigh [Thg].L", f"Parent/child relationships are maintained in skeleton {c.parent.name}"

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

    
if TEST_BPY_ALL or TEST_CONNECT_POINT:
    # FO4 has a complex method of attaching shapes to other shapes in game, using
    # connect points. These can be created and manipulated in Blender.
    test_title("TEST_CONNECT_POINT", "Connect points are imported and exported")
    clear_all()

    testfile = test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    outfile = test_file(r"tests\Out\TEST_CONNECT_POINT.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    parentnames = ['P-Barrel', 'P-Casing', 'P-Grip', 'P-Mag', 'P-Scope']
    childnames = ['C-Receiver', 'C-Reciever']

    shotgun = next(filter(lambda x: x.name.startswith('CombatShotgunReceiver:0'), bpy.context.selected_objects))
    cpparents = list(filter(lambda x: x.name.startswith('BSConnectPointParents'), bpy.context.selected_objects))
    cpchildren = list(filter(lambda x: x.name.startswith('BSConnectPointChildren'), bpy.context.selected_objects))
    cpcasing = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Casing'), bpy.context.selected_objects))
    
    assert len(cpparents) == 5, f"Found parent connect points: {cpparents}"
    p = [x.name.split("::")[1] for x in cpparents]
    p.sort()
    assert p == parentnames, f"Found correct parentnames: {p}"

    assert cpchildren, f"Found child connect points: {cpchildren}"
    assert (cpchildren[0]['PYN_CONNECT_CHILD_0'] == "C-Receiver") or \
        (cpchildren[0]['PYN_CONNECT_CHILD_1'] == "C-Receiver"), \
        f"Did not find child name"

    assert NearEqual(cpcasing.rotation_quaternion.w, 0.9098), f"Have correct rotation: {cpcasing.rotation_quaternion}"
    assert cpcasing.parent.name == "CombatShotgunReceiver", f"Casing has correct parent {cpcasing.parent.name}"

    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    ## --------- Check ----------
    nifcheck = NifFile(outfile)
    pcheck = [x.name.decode() for x in nifcheck.connect_points_parent]
    pcheck.sort()
    assert pcheck ==parentnames, f"Wrote correct parent names: {pcheck}"
    pcasing = next(filter(lambda x: x.name.decode()=="P-Casing", nifcheck.connect_points_parent))
    assert NearEqual(pcasing.rotation[0], 0.909843564), "Have correct rotation: {p.casing.rotation[0]}"

    chnames = nifcheck.connect_points_child
    chnames.sort()
    assert chnames == childnames, f"Wrote correct child names: {chnames}"


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
    
    # Not sure what behavior is best. Node is in the nif, not used in the shape. 
    # Importing on the theory that everything in the nif should be imported, but not in shape or armature.
    assert len([obj for obj in bpy.data.objects if obj.name.startswith("BaseFemaleHead_faceBones.nif")]) == 1, \
        f"Didn't create an EMPTY for the root Node"
    assert "skin_bone_C_MasterEyebrow" in bpy.data.objects, f"Did load empty node for skin_bone_C_MasterEyebrow"
    assert "skin_bone_C_MasterEyebrow" not in head.parent.data.bones, f"Bone not loaded for parented bone skin_bone_C_MasterEyebrow"
    meb = bpy.data.objects["skin_bone_C_MasterEyebrow"]
    assert meb.location.z > 120, f"skin_bone_C_MasterEyebrow in correct position"
    
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

# Disabling this for now. Bone transforms are tested in reading/writing nifs--this
# test just isloates that function for convenience. 
if False: #TEST_BPY_ALL or TEST_BONE_XF:
    test_title("TEST_BONE_XF", "Test our method of putting transforms into blender bones")
    clear_all()

    armdata = bpy.data.armatures.new("TEST_BONE_XF")
    arma = bpy.data.objects.new("TEST_BONE_XF", armdata)
    bpy.context.view_layer.active_layer_collection.collection.objects.link(arma)

    def do_test(bone_name, xf):
        log.debug(f"---\n---Testing {bone_name}---")
        bpy.context.view_layer.objects.active = arma
        bpy.ops.object.mode_set(mode='EDIT')
        create_bone(arma.data, bone_name, xf, 'FO4', 1.0)
        bpy.ops.object.mode_set(mode='OBJECT')

        log.debug(f"New bone has matrix\n{arma.data.bones[bone_name].matrix}")

        # Get xf from bone, verify it didn't change
        bone = armdata.bones[bone_name]
        xfout = get_bone_global_xf(arma, bone_name, 'FO4', False)
        assert MatNearEqual(xfout, xf), f"Transforms preserved for {bone_name}: \n{xfout}\n == \n{xf}"

    print("---180 deg rotation around Z")
    xf = Matrix.LocRotScale(Vector((0, 0, 0)),
                            Matrix(((-1, 0, 0),
                                    (0, -1, 0),
                                    (0, 0, 1))),
                            None)
    do_test('BONE3', xf)

    print("---180 deg rotation around Y")
    xf = Matrix.LocRotScale( Vector((0, 0, 0)),
                                Matrix(((-1, 0, 0),
                                        (0, 1, 0),
                                        (0, 0, -1))),
                                None)
    do_test('BONE4', xf)

    xf = Matrix.LocRotScale( Vector((-0.0005, 2.5661, 115.5521)),
                                Matrix(((-1.0000, 0.0002, 0.0001),
                                        (0.0002, 0.9492, 0.3147),
                                        (-0.0001, 0.3147, -0.9492))),
                                None)
    do_test('BONE2', xf)

    xf = Matrix.LocRotScale(Vector((0.0000, 0.5394, 91.2848)),
                            Matrix(((0.0000, -0.0000, -1.0000),
                                    (-0.0343, 0.9994, -0.0000),
                                    (0.9994, 0.0343, 0.0000))),
                            None)
    do_test('BONE1', xf)

    xf = Matrix.LocRotScale(Vector((-2.6813, -11.7044, 59.6862)),
                            Matrix(((0.0048, -1.0000,  0.0020),
                                    (1.0000,  0.0048, -0.0000),
                                    (0.0000,  0.0020,  1.0000))),
                            None)
    do_test('BONE5', xf)


if TEST_BPY_ALL or TEST_IMP_ANIMATRON:
    # The animatrons are very complex and their pose and bind positions are different.
    # Not sure we can do a full round trip successfully even yet.
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
    assert spine2.matrix_local.translation.z > 30, f"SPINE2 in correct position: {spine2.matrix_local.translation}"

    cp_armorleg = find_shape("BSConnectPointParents::P-ArmorLleg")
    assert cp_armorleg["pynConnectParent"] == "LLeg_Thigh", f"Connect point has correct parent: {cp_armorleg['pynConnectParent']}"
    assert VNearEqual(cp_armorleg.location, Vector((33.7, -2.4, 1.5)), 0.1), f"Connect point at correct position"

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


print("""
############################################################
##                                                        ##
##                    TESTS DONE                          ##
##                                                        ##
############################################################
""")
