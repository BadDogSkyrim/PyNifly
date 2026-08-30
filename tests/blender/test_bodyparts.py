"""Body parts, armatures and facebones tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('SKYRIM', 'BODYPART')
def TEST_BODYPART_SKY():
    """Basic test that a Skyrim bodypart is imported correctly. """
    # Verts are organized around the origin, but skin transform is put on the shape 
    # and that lifts them to the head position.  
    testfile = TTB.test_file(r"tests\Skyrim\malehead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Importer leaves any imported shapes as the selected object.
    male_head = bpy.context.object
    assert male_head.name == 'MaleHeadIMF', f"Have correct name: {male_head.name}"
    
    # Importer creates an armature for the skinned shape.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma, "Found armature"

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


@TT.category('FO4', 'BODYPART')
def TEST_BODYPART_FO4():
    """Basic test that a FO4 bodypart imports correctly. """
    # Verts are organized around the origin but the skin-to-bone transforms are 
    # all consistent, so they are put on the shape.
    testfile = TTB.test_file(r"tests\FO4\BaseMaleHead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    male_head = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH'][0]
    assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
    assert 'pynRoot' in male_head.parent, "Parenting mesh to root"
    maxz = max([v.co.z for v in male_head.data.vertices])
    TT.assert_equiv(maxz, 8.3, "Max Z", e=0.1)
    minz = min([v.co.z for v in male_head.data.vertices])
    TT.assert_equiv(minz, -12.1, "Min Z", e=0.1)


@TT.category('SKYRIM', 'BODYPART', 'XFORM')
def TEST_BODYPART_XFORM():
    """Test the body can be brought in with extended skeleton and Blender transform."""
    # On import, a transform can be applied to make it convenient for handling in Blender.
    # And the bones in the nif can be extended with the reference skeleton. Using the
    # child body because it creates problems that the adult body does not.
    testfile = TTB.test_file(r"tests\Skyrim\childbody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=True,
                                 blender_xf=True,
                                 rename_bones=True)

    # Importer leaves any imported shapes as the selected object.
    body = bpy.context.object
    assert body.name == 'BODY', f"Have correct name: {body.name}"
    
    # Importer creates an armature for the skinned shape.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma, "Found armature"

    # Root node imported and parents other objects. 
    root_object = next(n for n in bpy.data.objects if 'pynRoot' in n)
    assert body.parent == root_object, "Body parented to root."
    assert root_object.scale == Vector((0.1,0.1,0.1,)), "Root applies a 1/10 scale."

    # The new bones from the reference skeleton have the same transform and scale as the
    # ones that came from the nif.
    bonez_max = max(b.head.z for b in arma.data.bones)
    vertz_max = max((body.matrix_local @ v.co).z for v in body.data.vertices)
    assert bonez_max < vertz_max, "Armature entirely within body."

    spine1 = arma.data.bones['NPC Spine1']
    assert "CME Spine" == spine1.parent.name, "Spine1 has correct parent."


@TT.category('SKYRIM', 'BODYPART', 'XFORM')    
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
    CHK.Check_malehead(nifcheck)


@TT.category('FO4', 'BODYPART', 'XFORM')
def TEST_FO4_XFORM():
    """Can read & write FO4 shape transforms"""
    testfile = TTB.test_file(r"tests/FO4/BaseMaleHead.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_FO4_XFORM1.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_FO4_XFORM2.nif")

    # Reading the nif and calculating the offset from bone offsets
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 create_bones=True,
                                 import_tris=False,
                                 import_pose=False)

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

    assert NT.MatNearEqual(xf0, xf1), f"Matrices are near equal: \n{xf0}\n=\n{xf1}"


@TT.category('FO4', 'BODYPART', 'XFORM')
def TEST_FO4_RECENTER_HALF_PRECISION():
    """FO4 skinned verts authored far from the origin can be recentered near
    the bodypart origin on export (so 16-bit half-precision storage doesn't
    quantize them badly), with placement preserved by the shape transform.

    Fixture: a normal FO4 head sits with its verts centered around the origin
    and the object lifted ~120 up. We bake that lift into the mesh so the verts
    sit up at the head position with NO object transform centering them — the
    uncentered authoring this feature targets. Exporting with the option ON
    should pull the stored verts back to the origin while keeping the head in
    the same world position.
    """
    testfile = TTB.test_file(r"tests/FO4/BaseMaleHead.nif")
    out_on = TTB.test_file(r"tests/Out/TEST_FO4_RECENTER_ON.nif")
    out_off = TTB.test_file(r"tests/Out/TEST_FO4_RECENTER_OFF.nif")

    # --- Build the uncentered fixture -----------------------------------
    bpy.ops.import_scene.pynifly(filepath=testfile, import_tris=False)
    head = bpy.context.object
    assert head.find_armature() is not None, "head is skinned"

    # Bake the ~120-up position into the verts: object transform becomes
    # identity, verts now sit up at the head location.
    BD.ObjectSelect([head], active=True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    maxz_in = max((head.matrix_world @ v.co).z for v in head.data.vertices)
    assert maxz_in > 100, f"fixture verts sit up at head height: {maxz_in}"
    assert NT.NearEqual(head.matrix_local.translation.length, 0.0, 0.001), \
        "fixture object transform is identity (verts are not centered)"

    # --- Export both ways ------------------------------------------------
    BD.ObjectSelect([head], active=True)
    bpy.ops.export_scene.pynifly(filepath=out_off, target_game='FO4',
                                 export_recenter_half_precision=False)
    BD.ObjectSelect([head], active=True)
    bpy.ops.export_scene.pynifly(filepath=out_on, target_game='FO4',
                                 export_recenter_half_precision=True)

    def max_abs_coord(shape):
        return max(max(abs(v[0]), abs(v[1]), abs(v[2])) for v in shape.verts)

    off_shape = pyn.NifFile(out_off).shapes[0]
    on_shape = pyn.NifFile(out_on).shapes[0]

    # Sanity: with the option off the stored verts stay up at head height.
    assert TT.is_gt(max_abs_coord(off_shape), 100,
                    "recenter OFF: stored verts remain far from origin")

    # The feature: with the option on the stored verts are pulled near origin.
    assert TT.is_lt(max_abs_coord(on_shape), 20,
                    f"recenter ON: stored verts near origin "
                    f"(max |coord|={max_abs_coord(on_shape):.2f})")

    # Placement must be preserved: re-importing either export must land the
    # head in the same world position.
    bpy.ops.import_scene.pynifly(filepath=out_off, import_tris=False)
    head_off = bpy.context.object
    bpy.ops.import_scene.pynifly(filepath=out_on, import_tris=False)
    head_on = bpy.context.object

    bb_off = [head_off.matrix_world @ Vector(c) for c in head_off.bound_box]
    bb_on = [head_on.matrix_world @ Vector(c) for c in head_on.bound_box]
    for p_off, p_on in zip(bb_off, bb_on):
        assert TT.is_equiv(list(p_on), list(p_off),
                           "recenter preserves head world placement", e=0.1)


@TT.category('SKYRIM', 'BODYPART', 'XFORM')
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

    # Export

    BD.ObjectSelect([head], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    # Check

    nifcheck = pyn.NifFile(outfile)
    headcheck = nifcheck.shapes[0]
    sk2b_spine = headcheck.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
    assert NT.NearEqual(sk2b_spine.translation[2], 29.419632), f"Have correct z: {sk2b_spine.translation[2]}"


@TT.category('FO4', 'BODYPART', 'XFORM')
@TT.expect_errors((
    'bhkPhysicsSystem decode failed',
    'Unknown block type: bhkRagdollSystem',
    'will not dismember in game',
    ))
@TT.parameterize(("create_bones",   "estimate_offset",  "use_pose",),
                 [(False,           True,               True),])
def TEST_BODYPART_ALIGNMENT_FO4_1(create_bones, estimate_offset, use_pose):
    """Should be able to write bodyparts and have the transforms match exactly."""
    headfile = TTB.test_file(r"tests\FO4\Meshes\FoxFemaleHead.nif")
    skelfile = TTB.test_file(r"tests\FO4\skeleton.nif")
    bodyfile = TTB.test_file(r"tests\FO4\Meshes\CanineFemBody.nif")
    headout = TTB.test_file(r"tests\out\TEST_BODYPART_ALIGHMENT_FO4_head.nif", output=True)
    bodyout = TTB.test_file(r"tests\out\TEST_BODYPART_ALIGHMENT_FO4_body.nif", output=True)

    # Read the body parts using the same skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile, 
                                 create_bones=create_bones,
                                 import_pose=use_pose)
    skel = [x for x in bpy.context.scene.objects if x.type == 'ARMATURE'][0]
    assert TT.is_eq(skel.type, 'ARMATURE', "Have armature")
    BD.ObjectSelect([skel], active=True)
    bpy.ops.import_scene.pynifly(filepath=bodyfile, 
                                 create_bones=create_bones,
                                 import_pose=use_pose)
    body = bpy.context.object
    bodyarma = body.modifiers['Armature'].object
    assert TT.is_eq(bodyarma, skel), "existing skeleton"
    BD.ObjectSelect([skel], active=True)
    bpy.ops.import_scene.pynifly(filepath=headfile, 
                                 create_bones=create_bones,
                                 import_pose=use_pose)
    head = bpy.context.object
    if estimate_offset:
        assert TT.is_equiv(head.location.z, 120.8, e=0.1), "Head in correct location"
    else:
        assert TT.is_equiv(head.location.z, 0, e=0.1), "Head in correct location"
    assert TT.is_eq(len([x for x in bpy.context.view_layer.objects if x.type=='ARMATURE']), 1, 
        "Used same armature for all imports")

    # Validate that a known set of vertex pairs are at the same location.
    matchingPairsHB = [(3, 327), (16, 219), (1915, 1)]
    for hvi, bvi in matchingPairsHB:
        head_world_pos = head.matrix_world @ head.data.vertices[hvi].co
        body_world_pos = body.matrix_world @ body.data.vertices[bvi].co
        assert TT.is_equiv(head_world_pos, body_world_pos, e=0.0005), \
            "Matching verts at same world location"

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
    for hvi, bvi in matchingPairsHB:
        assert TT.is_equiv(headCheck.verts[hvi], bodyCheck.verts[bvi], e=0.0005), \
            "Matching verts at same location"
    # for i, vh in enumerate(headCheck.verts):
    #     for j, vb in enumerate(bodyCheck.verts):
    #         if BD.VNearEqual(vh, vb):
    #             print(f"Head {i} == Body {j}")
    for bn in ['Chest', 'Chest_skin', 'RArm_Collarbone_skin']:
        print(bn)
        print(headCheck.get_shape_skin_to_bone(bn).translation[:])
        print(bodyCheck.get_shape_skin_to_bone(bn).translation[:])
        assert TT.is_equiv(headCheck.get_shape_skin_to_bone(bn).translation[:], 
                           bodyCheck.get_shape_skin_to_bone(bn).translation[:],
                           e=0.0005), \
            "skin to bone translations"


@TT.category('SKYRIM', 'BODYPART')
@TT.parameterize(("game",       "blendxf",  "pretty"), 
                 [('SKYRIMSE',  "NATURAL",  "NIF"),
                  ('SKYRIM',    "NATURAL",  "NIF"),
                  ('SKYRIM',    "BLENDER",  "NIF"),
                  ('SKYRIMSE',  "BLENDER",  "NIF"),
                  ('SKYRIMSE',  "NATURAL",  "PRETTY"),
                  ('SKYRIMSE',  "BLENDER",  "PRETTY"),
                  ])
def TEST_IMP_EXP_SKY(game, blendxf, pretty):
    """Can read the armor nif and spit it back out"""
    # Round trip of ordinary Skyrim armor, with and without scale factor.

    testfile = TTB.test_file(r"tests/Skyrim/armor_only.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_IMP_EXP_SKY_{game}_{blendxf}_{pretty}.nif")

    ### IMPORT ###

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 blender_xf=(blendxf=="BLENDER"),
                                 rotate_bones_pretty=(pretty=="PRETTY"))
    armor = [obj for obj in bpy.context.selected_objects if obj.name.startswith('Armor')][0]

    impnif = pyn.NifFile(testfile)
    armorin = impnif.shape_dict['Armor']

    root = next(n for n in bpy.data.objects if 'pynRoot' in n)
    TT.assert_eq(root.name, 'Scene Root:ROOT', "Root node name")

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

    ### EXPORT ###

    root.name = "ArmorRoot"

    BD.ObjectSelect([armor], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                 target_game=game, 
                                 blender_xf=(blendxf=="BLENDER"), 
                                 rotate_bones_pretty=(pretty=="PRETTY"),
                                 intuit_defaults=False)

    nifout = pyn.NifFile(outfile)
    # Exported with the armor selected; gets a default root node nmae.
    assert TT.is_eq(nifout.rootNode.name, "Scene Root"), "Root node name in output nif"

    armorout = nifout.shape_dict['Armor']
    assert nifout.game == game, f"Wrote correct game format: {nifout.game} == {game}"
    TTB.compare_shapes(armorin, armorout, armor, e=0.01)
    TTB.check_unweighted_verts(armorout)

    TT.assert_eq(nifout.nodes['NPC Pelvis [Pelv]'].flags, 
                    NiAVFlags.SELECTIVE_UPDATE 
                    + NiAVFlags.SELECTIVE_UPDATE_TRANSF
                    + NiAVFlags.SELECTIVE_UPDATE_CONTR,
                    "bone flags")
        

@TT.category('SKYRIM', 'BODYPART')
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
        "Both shapes brought in under one armor"
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
    assert "NPC R Hand [RHnd]" not in bpy.data.objects, "Did not create extra nodes representing the bones"


@TT.category('FO4', 'BODYPART')
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


@TT.category('FO4', 'BODYPART')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_IMP_EXP_FO4_2():
    """Can read the body armor with 2 parts"""

    testfile = TTB.test_file(r"tests\FO4\Pack_UnderArmor_03_M.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_FO4_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TTB.find_shape('BaseMaleBody_03:0')
    armor = TTB.find_shape('Pack_UnderArmor_03_M:0')
    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    TT.assert_gt(body.location.z, 120, "Body transform")
    TT.assert_gt(armor.location.z, 120, "Armor transform")
    TT.assert_gt(arma.data.bones['Neck'].matrix_local.translation.z, 100, "Neck position")
    assert armor.active_material, "Armor has material"

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    armor.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    TTB.stage_materials_for(testfile, outfile)
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


@TT.category('FO4', 'BODYPART')
@TT.expect_errors(('not found in SSF',))
def TEST_IMP_EXP_FO4_3():
    """Can read clothes + body and they come in sensibly"""

    testfile = TTB.test_file(r"tests\FO4\meshes\bathrobe.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_FO4_3.nif")

    # Setting import_pose=False results in a good import but the 
    # shapes jump around in edit mode.
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False,
                                 import_pose=True)
    body = TTB.find_shape('CBBE')
    robe = TTB.find_shape('OutfitF_0')
    bodymax = max((body.matrix_world @ v.co).z for v in body.data.vertices)
    robemax = max((robe.matrix_world @ v.co).z for v in robe.data.vertices)
    assert bodymax < robemax, f"Robe goes higher than body: {robemax} > {bodymax}"
    bodymin = min((body.matrix_world @ v.co).z for v in body.data.vertices)
    robemin = min((robe.matrix_world @ v.co).z for v in robe.data.vertices)
    assert robemin < bodymin, f"Robe extends below body: {robemin} < {bodymin}"


@TT.category('SKYRIM', 'BODYPART')
def TEST_ROUND_TRIP():
    """Can do the full round trip: nif -> blender -> nif -> blender"""
    testfile = TTB.test_file("tests/Skyrim/test.nif")
    outfile1 = TTB.test_file("tests/Out/TEST_ROUND_TRIP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    armor1 = bpy.data.objects["Armor"]
    assert TT.is_eq(int(armor1.location.z), 120), \
        "Armor moved above origin by 120 to skinned position"
    maxz = max([v.co.z for v in armor1.data.vertices])
    minz = min([v.co.z for v in armor1.data.vertices])
    assert TT.is_lt(maxz, 0), "Max Z is below origin"
    assert TT.is_gt(minz, -130), "Min Z is above -130"
    assert TT.is_eq(len(armor1.data.vertex_colors), 0), "Armor should have no colors"

    # Because the base offsets for the two shapes are different, there are two armatures.
    # Find the one with the hand bone.
    arma = [a for a in bpy.data.objects 
            if a.type == 'ARMATURE' and 'NPC Hand.L' in a.data.bones][0]
    assert arma, "Found armature with hand bone"
    handl = arma.data.bones["NPC Hand.L"]
    handlx = handl.matrix_local @ arma.matrix_world
    assert TT.is_gt(handlx.translation.z, 40), f"Hand bone Z > 40: {handlx.translation.z}"
    assert TT.is_lt(handlx.translation.z, 100), f"Hand bone Z < 100: {handlx.translation.z}"

    print("Exporting  to test file")
    bpy.ops.object.select_all(action='DESELECT')
    armor1.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile1, target_game='SKYRIM')
    assert TT.is_eq(os.path.exists(outfile1), True), "Created output file"

    print("Re-importing exported file")
    TTB.clear_all()
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=outfile1)

    armor2 = [x for x in bpy.data.objects if x.name.startswith("Armor")][0]

    assert TT.is_eq(int(armor2.location.z), 120), f"Exported armor is re-imported with same position: {armor2.location}"
    for v in armor2.data.vertices:
        assert TT.is_gt(v.co.z, -120), f"Vertex Z > -120: {v.co}"
        assert TT.is_lt(v.co.z, 0), f"Vertex Z < 0: {v.co}"
        

@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
@TT.parameterize(("game",       "blendxf",  "pretty"), 
                 [('SKYRIMSE',  "NATURAL",  "NIF"),
                  ('SKYRIMSE',  "BLENDER",  "NIF"),
                  ('SKYRIMSE',  "NATURAL",  "PRETTY"),
                  ('SKYRIMSE',  "BLENDER",  "PRETTY"),
                  ])
def TEST_BPY_PARENT_A(game, blendxf, pretty):
    """Maintain armature structure"""
    testfile = TTB.test_file(r"tests\Skyrim\test.nif")

    # Can intuit structure if it's not in the file
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 blender_xf=(blendxf=="BLENDER"),
                                 rotate_bones_pretty=(pretty=="PRETTY"),
                                 create_bones=True,)
    arma = next(x for x in bpy.data.objects
                if x.type == 'ARMATURE' and 'NPC Hand.R' in x.data.bones)
    assert arma, "Found armature with hand bone"
    assert TT.is_eq(arma.data.bones['NPC Hand.R'].parent.name, 'CME Forearm.R'), "hand parent"

    # Both shapes should share one armature and have similar bounding boxes
    armatures = [x for x in bpy.data.objects if x.type == 'ARMATURE']
    assert TT.is_eq(len(armatures), 1, "Should have exactly one armature")
    body = next(x for x in bpy.data.objects if x.name.startswith('MaleBody'))
    armor = next(x for x in bpy.data.objects if x.name.startswith('Armor'))
    body_bb = TTB.get_obj_bbox(body, worldspace=True)
    armor_bb = TTB.get_obj_bbox(armor, worldspace=True)
    assert NT.VNearEqual(body_bb[0], armor_bb[0], epsilon=20), \
        f"Armor and body bounding box mins should be similar: {body_bb[0]} vs {armor_bb[0]}"
    assert NT.VNearEqual(body_bb[1], armor_bb[1], epsilon=20), \
        f"Armor and body bounding box maxs should be similar: {body_bb[1]} vs {armor_bb[1]}"


@TT.category('FO4', 'BODYPART', 'ARMATURE')
@TT.expect_errors(("Could not find texture Diffuse",
                   "Could not find texture Normal",
                   "Could not load diffuse texture",
                   "Could not load normal texture",
                   "Could not find materials file",))
def TEST_BPY_PARENT_B():
    """Maintain armature structure"""
    testfile2 = TTB.test_file(r"tests\FO4\meshes\bear_tshirt_turtleneck.nif")
    
    ## Can read structure if it comes from file
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    obj = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
    assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
    assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3.R', "Error: Should find forearm as parent"


@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_RENAME():
    """Test that NOT renaming bones works correctly"""
    testfile = TTB.test_file(r"tests\Skyrim\Meshes\femalebody_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False)

    body = bpy.context.object
    vgnames = [x.name for x in body.vertex_groups]
    vgxl = list(filter(lambda x: ".L" in x or ".R" in x, vgnames))
    assert len(vgxl) == 0, f"Expected no vertex groups renamed, got {vgxl}"

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    armnames = [b.name for b in arma.data.bones]
    armxl = list(filter(lambda x: ".L" in x or ".R" in x, armnames))
    assert len(armxl) == 0, f"Expected no bones renamed in armature, got {armxl}"


@TT.category('FO4', 'BODYPART', 'ARMATURE')
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
#                                  blender_xf=True,
#                                  create_bones=False,
#                                  import_pose=False)

#     root = [obj for obj in bpy.context.selected_objects if 'pynRoot' in obj][0]
#     BD.ObjectSelect([root], active=True)
#     bpy.ops.export_scene.pynifly(filepath=outfile, preserve_hierarchy=True)
    
#     nifout = pyn.NifFile(outfile)


@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_DRAUGR_IMPORT_A():
    """Import hood, extend skeleton, non-vanilla pose"""
    # This nif uses the draugr skeleton, which has bones named like human bones but with
    # different positions--BUT the hood was made for the human skeleton so the bind
    # position of its bones don't match the draugr skeleton. Bones defined by the hood are
    # given the human bind position--the rest come from the reference skeleton and use
    # those bind positions. 

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\draugr lich01 hood.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_A.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 create_bones=True,
                                 rename_bones=False,
                                 import_pose=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    hood = TTB.find_shape("Hood")

    bonemaxz = max(b.head.z for b in arma.data.bones)
    hoodmaxz = max(v.co.z for v in hood.data.vertices)
    assert hoodmaxz > bonemaxz, "Hood covers skeleton"

    # Pose position reflects the draugr skeleton, but bind position is the human position. 
    bone1 = arma.data.bones['NPC Head [Head]']
    pose1 = arma.pose.bones['NPC Head [Head]']
    assert pose1.head.z > bone1.head.z+10, "Pose well above bind positions"
    

@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_DRAUGR_IMPORT_B():
    """Import hood, don't extend skeleton, non-vanilla pose"""
    # This hood uses non-human bone node positions and we don't extend the skeleton, so
    # bones are given the bind position from the hood but the pose position from the nif.
    # Since the pose is not a pure translation, we do not put a transform on the hood
    # shape.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\draugr lich01 hood.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_B.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 create_bones=False,
                                 rename_bones=False,
                                 import_pose=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    hood = TTB.find_shape("Hood")
    bone1 = arma.data.bones['NPC R UpperarmTwist1 [RUt1]']
    pose1 = arma.pose.bones['NPC R UpperarmTwist1 [RUt1]']

    # Lots of bones in this nif are not used in the hood. Bones used in the hood have pose
    # and bind locations. The rest only have pose locations and are brought in as Empties.
    assert not NT.VNearEqual(pose1.matrix.translation, bone1.matrix_local.translation), \
        f"Pose position is not bind position: {pose1.matrix.translation} != {bone1.matrix_local.translation}"
    

@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_DRAUGR_IMPORT_C():
    """Import helm, don't extend skeleton"""
    # The helm has bones that are in the draugr's vanilla bind position.

    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\draugr lich01 helm.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_C.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 create_bones=False,
                                 rename_bones=False,
                                 import_pose=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    bone1 = skel.data.bones['NPC Head [Head]']
    pose1 = skel.pose.bones['NPC Head [Head]']

    assert not NT.VNearEqual(bone1.matrix_local.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not in vanilla bind position: {bone1.matrix_local.translation}"
    assert not NT.VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436]), \
        f"Head bone not posed in vanilla position: {pose1.matrix_local.translation}"


@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_DRAUGR_IMPORT_D():
    """Import helm, do extend skeleton"""
    # Fo the helm, when we import WITH adding bones, we get a full draugr skeleton.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\draugr lich01 helm.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_D.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 create_bones=True,
                                 rename_bones=False,
                                 import_pose=False)

    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    helm = TTB.find_shape("Helmet")
    bone1 = skel.data.bones['NPC Head [Head]']
    pose1 = skel.pose.bones['NPC Head [Head]']
    bone2 = skel.data.bones['NPC Spine2 [Spn2]']
    pose2 = skel.pose.bones['NPC Spine2 [Spn2]']

    assert NT.VNearEqual(bone1.matrix_local.translation, [-0.015854, -2.40295, 134.301]), \
        f"Head bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert not NT.VNearEqual(pose1.matrix.translation, [-0.0003, -1.5475, 120.3436], epsilon=2.0), \
        f"Head bone not posed in vanilla position: {pose1.matrix.translation}"

    assert NT.VNearEqual(bone2.matrix_local.translation, [0.000004, -5.83516, 102.358]), \
        f"Spine bone in vanilla bind position: {bone1.matrix_local.translation}"
    assert NT.VNearEqual(pose2.matrix.translation, [0.0000, -5.8352, 102.3579]), \
        f"Spine bone posed in draugr position: {pose2.matrix.translation}"
    
    assert bone2.parent.name == 'NPC Spine1 [Spn1]', \
        f"Spine bone has correct parent: {bone2.parent.name}"
    

@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_DRAUGR_IMPORT_E():
    """Import of this draugr mesh positions hood correctly"""
    # This nif has two shapes and the bind positions differ. The hood bind position is
    # human, and it's posed to the draugr position. The draugr hood is bound at pose
    # position, so pose and bind positions are the same. The only solution is to import as
    # two skeletons and let the user sort it out. We lose the bind position info but end up with the shapes parented
    # to one armature.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\draugr lich01 simple.nif")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DRAUGR_IMPORT_E.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, reference_skel=skelfile, 
                                 create_bones=False,
                                 rename_bones=False,
                                 import_pose=False)

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
    
    headbone = skel.data.bones['NPC Head [Head]']
    headpose = skel.pose.bones['NPC Head [Head]']

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
    assert arma_helm.data.bones.keys() == ["NPC Head [Head]"], f"Helm armature has correct bones: {helm.parent.data.bones.keys()}"

    # Hood has pose location different from rest
    bone1 = arma_hood.data.bones['NPC Head [Head]']
    pose1 = arma_hood.pose.bones['NPC Head [Head]']

    assert not NT.VNearEqual(bone1.matrix_local.translation, pose1.matrix.translation), \
        f"Pose and bind locaations differ: {bone1.matrix_local.translation} != {pose1.matrix.translation}"
    

@TT.category('SKYRIM', 'BODYPART', 'SCALING')
def TEST_SCALING_BP():
    """Can scale bodyparts"""

    testfile = TTB.test_file(r"tests\Skyrim\malebody_1.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SCALING_BP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 rename_bones_niftools=True,
                                 blender_xf=True)

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


@TT.category('SKYRIM', 'BODYPART', 'SCALING')
def TEST_IMP_EXP_SCALE_2():
    """Can read the body nif scaled"""
    # Regression: Making sure that the scale factor doesn't mess up importing under one
    # armature.

    testfile = TTB.test_file(r"tests/Skyrim/malebody_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_IMP_EXP_SCALE_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)

    armatures = [x for x in bpy.data.objects if x.type=='ARMATURE']
    assert len(armatures) == 1, "Have just one armature"
    body = TTB.find_shape('MaleUnderwearBody:0')
    armor = TTB.find_shape('MaleUnderwear_1')
    body_arma = next(a.object for a in body.modifiers if a.type == 'ARMATURE')
    armor_arma = next(a.object for a in armor.modifiers if a.type == 'ARMATURE')
    assert body_arma == armor_arma, "Both shapes brought in under one armature"

    # We imported scaled down and rotated 180.
    assert NT.VNearEqual((armor_arma.matrix_world @ armor.location), (-0.0, 0.15475, 12.03436)), \
        f"Armor is raised to match body: {armor.location}"
    

@TT.category('FO4', 'BODYPART', 'ARMATURE')
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
    assert "HEAD" not in arma.data.bones, "Did not find head bone in skeleton"
    assert "Leg_Calf.L" in arma.data.bones, "Loaded bones not used by shape"
    assert arma.data.bones['SPINE2'].matrix_local.translation.z > 0, \
        f"Armature in basic position: {arma.data.bones['SPINE2'].matrix_local.translation}"

    # When we import a shape where the pose-to-bind transform is consistent, we use that 
    # transform on the blender shape for ease of editing. We can then import another body
    # part to the same armature.
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    new_arma = next(a.object for a in bpy.context.object.modifiers if a.type == 'ARMATURE')
    assert new_arma == arma, f"Have same armature parent: {bpy.context.object.parent.name}"
    assert len([o for o in bpy.data.objects if o.type == 'ARMATURE']) == 1, "Have only one armature"
    assert "HEAD" in arma.data.bones, "Found head bone in skeleton"

    head = TTB.find_shape("BaseMaleHead:0")
    body = TTB.find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = TTB.find_vertex(head.data, target_v)
    v_body = TTB.find_vertex(body.data, target_v)
    assert NT.VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        "Head and body verts align"
    
    # For FO4, we give a generous fudge factor.
    assert TTB.MatNearEqual(head.matrix_world, body.matrix_world, epsilon=0.1), "Shape transforms match"


@TT.category('FO4', 'BODYPART', 'ARMATURE')
@TT.expect_errors(("will not dismember in game",))
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
    assert arma.type == 'ARMATURE', "Found armature"
    bpy.context.view_layer.objects.active = arma
    assert "SPINE1" in arma.data.bones, "Found neck bone in skeleton"
    assert "HEAD" not in arma.data.bones, "Did not find head bone in skeleton"
    assert "Leg_Calf.L" in arma.data.bones, "Loaded bones not used by shape"
    assert arma.data.bones['SPINE2'].matrix_local.translation.z > 0, \
        f"Armature in basic position: {arma.data.bones['SPINE2'].matrix_local.translation}"

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly(filepath=testfile2)
    
    assert len([o for o in bpy.data.objects if o.type=='ARMATURE']) == 1, "Have just one armature"
    assert "HEAD" in arma.data.bones, "Found head bone in skeleton"

    head = TTB.find_shape("BaseMaleHead:0")
    body = TTB.find_shape("BaseMaleBody")
    target_v = Vector((0.00016, 4.339844, -12.101563))
    v_head = TTB.find_vertex(head.data, target_v)
    v_body = TTB.find_vertex(body.data, target_v)
    assert NT.VNearEqual(head.data.vertices[v_head].co, body.data.vertices[v_body].co), \
        "Head and body verts align"
    # Shape transforms are different between vanilla head and BT body.
    #assert TTB.MatNearEqual(head.matrix_world, body.matrix_world), f"Shape transforms match"


@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
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


# Briarheart.blend was saved by Blender 5.1 (bpy.data.version 5.1.29) and .blend files
# are not forward-compatible -- 4.x reports "not a blend file". Gate both tests that
# load it rather than lose the fixture's content by re-saving from an older Blender.
@TT.min_version(5, 1, 0)
@TT.category('SKYRIMSE', 'BODYPART', 'ARMATURE')
def TEST_BRIARHEART_ROOT_EXPORT():
    """Exporting a root with mixed armature sources picks the mesh-modifier armature."""
    # Briarheart.blend has BriarHeart:ROOT (EMPTY pynRoot) whose children include both
    # a stub armature (BriarHeart_0.nif:ARMATURE, 13 bones) and three skinned meshes
    # whose Armature modifiers point to a separate, complete armature (56 bones) that
    # lives under a different root. When the user exports BriarHeart:ROOT, the
    # mesh-declared armature must win over the child stub — otherwise bone weights
    # for bones missing from the stub get dropped.
    testfile = TTB.test_file(r"tests\SkyrimSE\Briarheart.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_BRIARHEART_ROOT_EXPORT.nif")

    with bpy.data.libraries.load(testfile) as (data_from, data_to):
        data_to.objects = [obj for obj in data_from.objects]
    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)

    root = bpy.data.objects["BriarHeart:ROOT"]
    BD.ObjectSelect([root], active=True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheck = pyn.NifFile(outfile)
    flesh = nifcheck.shape_dict.get("BriarheartFlesh")
    assert flesh is not None, f"Have BriarheartFlesh shape: {list(nifcheck.shape_dict.keys())}"

    # BriarheartFlesh has weights on Clavicle.L, UpperArm.L, UpperarmTwist1.L,
    # Spine1, Spine2. UpperArm.L and UpperarmTwist1.L are NOT in the 13-bone stub
    # — only present in the full 56-bone armature reached via the mesh's modifier.
    # If the stub wins, those two bones get filtered out by trim_weights.
    used = set(flesh.get_used_bones())
    required = {"NPC L UpperArm [LUar]", "NPC L UpperarmTwist1 [LUt1]"}
    missing = required - used
    assert not missing, \
        f"BriarheartFlesh missing arm bones (used={sorted(used)}, missing={sorted(missing)})"


# Briarheart.blend was saved by Blender 5.1 (bpy.data.version 5.1.29) and .blend files
# are not forward-compatible -- 4.x reports "not a blend file". Gate both tests that
# load it rather than lose the fixture's content by re-saving from an older Blender.
@TT.min_version(5, 1, 0)
@TT.category('SKYRIMSE', 'ARMATURE')
def TEST_EXPORT_BONE_ROTATION_RESPECTS_SETTING():
    """Export must apply its own rotate_bones_pretty setting, not whatever stale
    value BD.game_rotations happens to hold from the last import.

    Bug: BD.game_rotations is a module-level global set by the IMPORT path
    based on rotate_bones_pretty. The EXPORT path collects self.rotate_bones_pretty
    but never pushes it into BD.game_rotations — it just reads whatever's there.
    So if a session imports nif A with rotate_bones_pretty=True (sets global to
    _pretty), then opens a blend whose armature was imported with
    rotate_bones_pretty=False (bones stored raw, matching vanilla orientation),
    exporting that blend writes wrong bone rotations because get_bone_xform
    multiplies raw bones by Rx(-90°) it shouldn't apply.

    Symptom: NifSkope renders the exported nif fine with skinning off, but warps
    badly with skinning on — and any tool that rewrites bone positions from a
    skeleton DB (Outfit Studio, the game) will warp the mesh.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\Briarheart.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_EXPORT_BONE_ROTATION_RESPECTS_SETTING.nif")

    with bpy.data.libraries.load(testfile) as (data_from, data_to):
        data_to.objects = [obj for obj in data_from.objects]
    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)

    # Briarheart.blend's armatures were imported with rotate_bones_pretty=False,
    # so their bones' matrix_local matches the vanilla nif orientation directly.
    # Simulate session contamination: force the global to the WRONG state, as if
    # an earlier import in this session had used rotate_bones_pretty=True.
    BD.game_rotations = BD.game_rotations_pretty

    root = bpy.data.objects["BriarHeart:ROOT"]
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE',
                                 rotate_bones_pretty=False)

    # Vanilla rotations for these bones (from vanilla skeleton.nif).
    expected = {
        "NPC Spine1 [Spn1]": [
            [1.0, 0.0, 0.0],
            [0.0, 0.994, -0.107],
            [0.0, 0.107, 0.994]],
        "NPC Spine2 [Spn2]": [
            [1.0, 0.0, 0.0],
            [0.0, 0.991, 0.134],
            [0.0, -0.134, 0.991]],
        "NPC L UpperArm [LUar]": [
            [-0.907, -0.077, -0.413],
            [-0.087, 0.996, 0.006],
            [0.411, 0.041, -0.911]],
    }

    out_nif = pyn.NifFile(outfile)
    bad = []
    for bn, exp_R in expected.items():
        assert bn in out_nif.nodes, f"Bone {bn} present in exported nif"
        out_R = out_nif.nodes[bn].global_transform.rotation
        for i in range(3):
            for j in range(3):
                if abs(out_R[i][j] - exp_R[i][j]) > 0.01:
                    bad.append((bn, i, j, out_R[i][j], exp_R[i][j]))
    assert not bad, (
        "Exported bone rotation differs from vanilla (export ignored its "
        "rotate_bones_pretty setting and used the stale module global):\n"
        + "\n".join(f"  {bn}[{i}][{j}]: exported={o:.4f}  expected={e:.4f}"
                    for bn, i, j, o, e in bad))


@TT.category('FO4', 'BODYPART', 'ARMATURE')
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
    assert min(vert_weights) == 1, "Have a weight for every vertex"


@TT.category('FO4', 'BODYPART', 'ARMATURE')
@TT.expect_errors( ("Some vertices are not weighted to the armature",) )
def TEST_0_WEIGHTS():
    """Gives warning on export with 0 weights"""
    testfile = TTB.test_file(r"tests\Out\weight0.nif")

    baby = TTB.append_from_file("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
    baby.parent.name == "BabyExportRoot", "Error: Should have baby and armature"
    log.debug(f"Found object {baby.name}")
    try:
        bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")
    except RuntimeError:
        print("Caught expected runtime error")
    assert BD.UNWEIGHTED_VERTEX_GROUP in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


@TT.category('FO4', 'BODYPART', 'ARMATURE')
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
    bpy.ops.export_scene.pynifly(filepath=f, target_game='FO4', chargen_ext="_chargen", 
                                 intuit_defaults=False)

    nif1 = pyn.NifFile(f)
    assert len(nif1.shapes) == 1, "Expected tiger nif"
    assert os.path.exists(fb), "Facebones file created"
    assert os.path.exists(ftri), "Tri file created"
    assert os.path.exists(fchargen), "Chargen file created"


@TT.category('SKYRIM', 'BODYPART', 'XFORM')
def TEST_3BBB():
    """Test that this mesh imports with the right transforms"""

    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/3BBB_femalebody_1.nif")
    testfile2 = TTB.test_file(r"tests/SkyrimSE/meshes/3BBB_femalehands_1.nif")
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
        

@TT.category('SKYRIMSE', 'BODYPART', 'ARMATURE')
def TEST_WOLF_SKEL():
    """Can import and export the wolf skeleton with collisions"""
    testname = "TEST_WOLF_SKEL"
    testfile = TTB.test_file(
        r"tests\SkyrimSE\meshes\actors\canine\character assets wolf\skeleton.nif")
    outfile = TTB.test_file(r"tests/out/TEST_WOLF_SKEL.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False, 
                                 rename_bones=False)
    
    root = next(x for x in bpy.data.objects if 'pynRoot' in x)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert 'Canine_COM' in arma.data.bones, "Have COM bone"
    assert arma.pose.bones['Canine_COM'].constraints, "Have COM constraints"
    assert TT.is_contains("BSBound:BBX", [obj.name for obj in root.children], "Have BBX object")
    assert TT.is_contains("BSBoneLOD:BSBoneLOD", [obj.name for obj in root.children], "Have Bone LOD object")

    ### EXPORT ###

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                 target_game='SKYRIMSE', 
                                 preserve_hierarchy=True,
                                 intuit_defaults=False,)
    
    ### CHECK ###
    nif2 = pyn.NifFile(outfile)
    assert nif2.nodes['Canine_COM'], "Have COM node"
    assert nif2.nodes['Canine_COM'].collision_object, "Have COM node collisions"

    bsb:pyn.BSBound = nif2.root.get_extra_data(blockname="BSBound")
    assert bsb, "Have BSBound"
    assert TT.is_equiv(bsb.center[:], (0, 0, 39.42), "BSBound center", e=0.01)
    assert TT.is_equiv(bsb.half_extents[:], (20.11, 74.17, 39.42), "BSBound half_extents", e=0.01)

    bonelod:pyn.BSBoneLODExtraData = nif2.root.get_extra_data(blockname="BSBoneLODExtraData")

    lod_list = bonelod.lod_data
    assert TT.is_eq(len(lod_list), 3), "BSBoneLOD count"
    assert TT.is_eq(lod_list[1], ("Canine_LFrontLegToe", 2200)), "BSBoneLOD level 1 data"
    assert TT.is_eq(lod_list[2], ("Canine_LFrontLegPalm", 3500)), "BSBoneLOD level 2 data"
    

@TT.category('SKYRIMSE', 'BODYPART', 'ARMATURE')
def TEST_DEER_SKEL():
    """
    Can import and export the deer skeleton with collisions. This one tends to create
    circular dependencies in the collisions.
    """
    testfile = TTB.test_file(
        r"tests\SkyrimSE\deer_skeleton.nif")
    outfile = TTB.test_file(r"tests/out/TEST_DEER_SKEL.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False, 
                                 rename_bones=False)
    
    root = next(x for x in bpy.data.objects if 'pynRoot' in x)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert 'Elk_COM' in arma.data.bones, "Have COM bone"
    assert arma.pose.bones['Elk_COM'].constraints, "Have COM constraints"
    assert TT.is_contains("BSBound:BBX", [obj.name for obj in root.children], "Have BBX object")
    assert TT.is_contains("BSBoneLOD:BSBoneLOD", [obj.name for obj in root.children], "Have Bone LOD object")
    
    # Check for SkeletonID 
    skel_id_obj = next((obj for obj in root.children if obj.name.startswith("NiIntegerExtraData")), None)
    assert skel_id_obj, "Have SkeletonID object"
    assert TT.is_eq(skel_id_obj.pyn_niintdata.name, "SkeletonID", "SkeletonID name value")
    assert skel_id_obj.pyn_niintdata.is_property_set('value'), "SkeletonID has Data property"
    # Held as a decimal string: the nif field is a uint32, which Blender's IntProperty
    # (signed 32-bit) can't represent across its whole range.
    assert TT.is_eq(skel_id_obj.pyn_niintdata.value, '178509022', "SkeletonID Data value")

    ### EXPORT ###

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                 target_game='SKYRIMSE', 
                                 preserve_hierarchy=True,
                                 intuit_defaults=False,)
    
    ### CHECK ###
    nif2 = pyn.NifFile(outfile)
    assert nif2.nodes['Elk_COM'], "Have COM node"
    assert nif2.nodes['Elk_COM'].collision_object, "Have COM node collisions"
    
    # Check Elk_COM collision structure
    elk_collision = nif2.nodes['Elk_COM'].collision_object
    assert TT.is_eq(elk_collision.blockname, "bhkCollisionObject", "Elk_COM collision object type")
    assert elk_collision.body, "Elk_COM collision has body"
    assert TT.is_eq(elk_collision.body.blockname, "bhkRigidBody", "Elk_COM collision body type")
    assert TT.is_eq(elk_collision.body.properties.collisionFilter_layer, SkyrimCollisionLayer.BIPED, 
                    "Elk_COM collision layer is BIPED")

    assert (bnd := nif2.root.get_extra_data(blockname="BSBound")), "Have BSBound"
    assert TT.is_equiv(bnd.center[:], (0, 0, 89.930107), "BSBound center", e=0.0001)
    assert TT.is_equiv(bnd.half_extents[:], (38.973213, 105.170235, 89.930107), \
                       "BSBound half_extents", e=0.01)

    assert (bonelod := nif2.root.get_extra_data(blockname="BSBoneLODExtraData")), "Have BSBoneLOD"
    assert TT.is_eq(bonelod.name, "BSBoneLOD", "BSBoneLOD name")
    assert TT.is_eq(len(bonelod.lod_data), 1, "BSBoneLOD level count")
    assert TT.is_eq(bonelod.lod_data[0][0], "ElkLRearHoof", "BSBoneLOD level 1 target")
    assert TT.is_eq(bonelod.lod_data[0][1], 2048, "BSBoneLOD level 1 value")
    
    # Check Character Controller collision properties
    char_controller = nif2.nodes.get("Character Controller")
    assert char_controller, "Have Character Controller node"
    assert char_controller.collision_object, "Character Controller has collision"
    assert TT.is_eq(char_controller.collision_object.blockname, "bhkSPCollisionObject", 
                    "Character Controller collision type")
    assert char_controller.collision_object.body, "Character Controller has collision body"
    assert TT.is_eq(char_controller.collision_object.body.blockname, "bhkSimpleShapePhantom", 
                    "Character Controller collision body")
    assert char_controller.collision_object.body.shape, "Character Controller collision body has shape"
    assert TT.is_eq(char_controller.collision_object.body.shape.blockname, "bhkListShape", 
                    "Character Controller collision body shape")
    


@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_SKEL_SKY():
    """Can import and export Skyrim skeleton file with no shapes"""
    testfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    outfile = TTB.test_file(r"tests/out/TEST_SKEL_SKY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False)

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


@TT.category('SKYRIMSE', 'ARMATURE')
def TEST_SKEL_BEAST_POSE():
    """Skeleton-only NIF has pose location matching bind location for all bones.
    The beast skeleton has hand bones with scale 0.851680 in the NIF. Verify that
    the imported pose reflects those transforms correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\skeletonbeast_female.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')

    nif = pyn.NifFile(testfile)

    # Hand bone has local scale 0.851680 in the NIF. Check pose scale matches.
    rhand = arma.pose.bones['NPC Hand.R']
    rhand_nif = nif.nodes['NPC R Hand [RHnd]']
    assert NT.NearEqual(rhand_nif.transform.scale, 0.851680, epsilon=0.0001), \
        f"NIF hand bone has expected local scale: {rhand_nif.transform.scale}"
    assert NT.NearEqual(rhand.scale[0], rhand_nif.transform.scale, epsilon=0.001), \
        f"Pose hand bone scale matches NIF: {rhand.scale[0]} != {rhand_nif.transform.scale}"

    # Finger has local scale 1.0 but inherits global scale 0.851680 from hand.
    rfinger = arma.pose.bones['NPC Finger00.R']
    rfinger_nif = nif.nodes['NPC R Finger00 [RF00]']
    assert NT.NearEqual(rfinger_nif.transform.scale, 1.0, epsilon=0.0001), \
        f"NIF finger bone has unit local scale: {rfinger_nif.transform.scale}"
    assert NT.NearEqual(rfinger.scale[0], 1.0, epsilon=0.001), \
        f"Pose finger bone has unit local scale: {rfinger.scale[0]}"


@TT.category('SKYRIMSE', 'BODYPART')
def TEST_IMPORT_MULTI_OBJECTS():
    """Can import 2 meshes as objects"""
    # When two files are selected for import, they are connected into a single armature.

    testfiles = [{"name": TTB.test_file(r"tests\SkyrimSE\malehead.nif")}, 
                 {"name": TTB.test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    TT.assert_eq(len(meshes), 3, "mesh count")
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    TT.assert_eq(len(armatures), 1, "armature count")
    roots = [obj for obj in bpy.data.objects if 'pynRoot' in obj]
    TT.assert_eq(len(roots), 2, "root count")
    for r in roots:
        assert r.parent == None, f"Roots do not have parents: {r}"
    bodyroot = next(obj for obj in roots if obj.name.startswith("Body"))
    invm = [obj for obj in bodyroot.children if 'InvMarker' in obj.name]
    TT.assert_eq(len(invm), 1, "inventory marker")
    TT.assert_eq(invm[0].type, 'CAMERA', "Inventory marker type")


@TT.category('FO4', 'ARMATURE')
@TT.expect_errors(("will not dismember in game",))
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


@TT.category('FO4', 'ARMATURE')
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


@TT.category('SKYRIMSE', 'ARMATURE')
def TEST_WELWA():
    """Can read and write shape with unusual skeleton"""
    # The Welwa (bear skeleton) has bones similar to human bones--but they can't be
    # treated like the human skeleton. "Rename bones" is false on import and should be
    # remembered on the mesh and armature for export, so it's not explicitly specified on
    # export.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\SkyrimSE\Meshes\welwa.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_WELWA.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, create_bones=False)

    welwa = TTB.find_shape("111")
    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    lipbone = skel.data.bones['NPC UpperLip']
    assert TT.is_equiv(lipbone.matrix_local.translation, (0, 49.717827, 161.427307), "Upperlib translation")
    spine1 = skel.data.bones['NPC Spine1']
    assert TT.is_equiv(spine1.matrix_local.translation, (0, -50.551056, 64.465019), "Spine1 translation")
    assert TT.is_contains("NPC Pelvis", skel.data.bones.keys(), "Welwa pelvis")
    assert TT.is_notcontains("NPC Pelvis [Pelv]", skel.data.bones.keys(), "Pelvis renamed")

    # Should remember that bones are not to be renamed.
    BD.ObjectSelect([welwa])
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', intuit_defaults=True)

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)

    assert TT.is_contains("NPC Pelvis", nifcheck.nodes, "Welwa pelvis name in nif")
    assert TT.is_notcontains("NPC Pelvis [Pelv]", nifcheck.nodes, "Human pelvis name in nif")


@TT.category('SKYRIMSE', 'ARMATURE')
def TEST_BONE_HIERARCHY():
    """Bone hierarchy can be written on export"""
    # This hair has a complex custom bone hierarchy which have moved with havok.
    # Turns out the bones must be exported in a hierarchy for that to work.
    testfile = TTB.test_file(r"tests\SkyrimSE\Meshes\Anna.nif")
    outfile = TTB.test_file(r"tests/Out/TESTS_BONE_HIERARCHY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile, import_pose=0)

    hair = TTB.find_shape("KSSMP_Anna")
    skel = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert skel

    print("# -------- Export --------")
    bpy.ops.object.select_all(action='DESELECT')
    hair.select_set(True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True,
                                 rename_bones=True,
                                 intuit_defaults=False)

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
    assert spine2.parent.name == "NPC Spine1 [Spn1]", "Spine2 parent is correct"
    assert NT.VNearEqual(spine2.transform.translation, (0, -0.017105, 9.864068), 0.01), f"Spine2 location is correct: \n{spine2.transform}"

    ### Currently the original has different bind and pose positions. We export with bind and pose the same. 
    # head = nifcheck.nodes["NPC Head [Head]"]
    # assert NT.VNearEqual(head.transform.translation, (0, 0, 7.392755)), f"head location is correct: \n{head.transform}"
    # headRot = Matrix(head.transform.rotation).to_euler()
    # assert NT.VNearEqual(headRot, (0.1913, 0.0009, -0.0002), 0.01), f"head rotation correct: {headRot}"

    l3 = nifcheck.nodes["Anna L3"]
    assert l3.parent, "'Anna L3' parent exists"
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


@TT.category('SKYRIM', 'ARMATURE')
@TT.expect_errors( ("Some faces have been assigned to more than one partition",) )
def TEST_BONE_XPORT_POS():
    """Vanilla bones coming from a different skeleton export correctly."""
    # Since we use a reference skeleton to make bones, we have to be able to handle
    # the condition where the mesh is not human and the reference skeleton should not
    # be used.
    testfile = TTB.test_file(r"tests\Skyrim\draugr.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_BONE_XPORT_POS.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    
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
    bpy.ops.import_scene.pynifly(filepath=outfile, rename_bones=False)
    impcheck = pyn.NifFile(outfile)
    nifbone = impcheck.nodes['NPC Spine2 [Spn2]']
    TT.assert_equiv(nifbone.transform.translation[2], 102.36, "Spine2 translation in nif", e=0.01)

    draugrcheck = bpy.context.object
    draugrcheck_arma = next(m.object for m in draugrcheck.modifiers if m.type == 'ARMATURE')
    spine2check = draugrcheck_arma.data.bones['NPC Spine2 [Spn2]']
    TT.assert_equiv(spine2check.matrix_local.translation[2], 102.36, "Spine2 translation in blender", e=0.01)


@TT.category('SKYRIM', 'ARMATURE')
def TEST_NIFTOOLS_NAMES():
    """Can import nif with niftools' naming convention"""
    # We allow renaming bones according to the NifTools format. Someday this may allow
    # us to use their animation tools, but this is not that day.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\malebody_1.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones_niftools=True, 
                                 create_bones=False, blender_xf=True)
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
        assert "skeleton.nif" not in arma.data.bones, "Root node not imported as bone"
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


@TT.category('FO4', 'ARMATURE')
def TEST_BABY():
    """Non-human skeleton, lots of shapes under one armature."""
    # Can intuit structure if it's not in the file
    testfile = TTB.test_file(r"tests\FO4\baby.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_BABY.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    
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


@TT.category('FO4', 'FACEBONES')
@TT.expect_errors(("Unknown block type: NiBinaryExtraData",))
def TEST_FACEBONES():
    """Can read and write facebones correctly"""
    # A few of the facebones have transforms that don't match the rest. The skin-to-bone
    # transforms have to be handled correctly or the face comes in slightly warped.
    # Also the skin_bone_C_MasterEyebrow is included in the nif but not used in the head.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\FO4\BaseFemaleHead_faceBones.nif")
    goodfile = TTB.test_file(r"tests\FO4\BaseFemaleHead.nif")
    outfile = TTB.test_file("tests/Out/TEST_FACEBONES.nif", output=1)
    resfile = TTB.test_file("tests/Out/TEST_FACEBONES_facebones.nif", output=1)

    # Facebones files have NiTransformController nodes for reasons I don't understand. We
    # don't want to muck with those.
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 import_animations=False)

    head = TTB.find_shape("BaseFemaleHead_faceBones:0")
    maxy = max([v.co.y for v in head.data.vertices])
    assert maxy < 11.8, f"Max y not too large: {maxy}"

    head_arma = next(m.object for m in head.modifiers if m.type == 'ARMATURE')
    assert head_arma['PYN_RENAME_BONES'], f"Armature remembered that bones were renamed {head.parent.name}"
    assert head['PYN_RENAME_BONES'], f"Head remembered that bones were renamed {head.name}"
    
    # Not sure what behavior is best. Node is in the nif, not used in the shape. Since we
    # are extending the armature, we import the bone as part of the armature.
    assert len([obj for obj in bpy.data.objects if "pynRoot" in obj]) == 1, \
        "Have the root Node"
    assert "skin_bone_C_MasterEyebrow" not in bpy.data.objects, \
        "No separate empty node for skin_bone_C_MasterEyebrow"
    assert "skin_bone_C_MasterEyebrow" in head_arma.data.bones, \
        "Bone is loaded for parented bone skin_bone_C_MasterEyebrow"
    assert head_arma.data.bones['skin_bone_C_MasterEyebrow'].matrix_local.translation.z < 150, \
        "Eyebrow in reasonable location"
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

@TT.category('FO4', 'FACEBONES')
@TT.expect_errors(("Unknown block type: NiBinaryExtraData",))
def TEST_FACEBONES_RENAME():
    """Facebones are renamed from Blender to the game's names"""

    testfile = TTB.test_file(r"tests/FO4/basemalehead_facebones.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FACEBONES_RENAME.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_FACEBONES_RENAME_facebones.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    arma = next(m.object for m in obj.modifiers if m.type == 'ARMATURE')
    assert 'skin_bone_Dimple.R' in obj.vertex_groups.keys(), "Expected munged vertex groups"
    assert 'skin_bone_Dimple.R' in arma.data.bones.keys(), "Expected munged bone names"
    assert 'skin_bone_R_Dimple' not in obj.vertex_groups.keys(), "Expected munged vertex groups"
    assert 'skin_bone_R_Dimple' not in arma.data.bones.keys(), "Expected munged bone names"

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nif2 = pyn.NifFile(outfile2)
    assert 'skin_bone_R_Dimple' in nif2.shapes[0].bone_names, f"Expected game bone names, got {nif2.shapes[0].bone_names[0:10]}"
 

@TT.category('FO4', 'ARMATURE')
@TT.expect_errors(("Could not find materials file",))
def TEST_CUSTOM_BONES():
    """Can handle custom bones correctly"""
    # These nifs have bones that are not part of the vanilla skeleton.

    testfile = TTB.test_file(r"tests\FO4\Meshes\VulpineInariTailPhysics.nif")
    testfile = TTB.test_file(r"tests\FO4\Meshes\BrushTail_Male_Simple.nif")
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


@TT.category('SKYRIMSE', 'ARMATURE')
def TEST_JIARAN():
    """Armature with no stashed transforms exports correctly"""
    outfile =TTB.test_file(r"tests/Out/TEST_JIARAN.nif")
     
    TTB.export_from_blend(r"tests\SKYRIMSE\jiaran.blend", "hair.001", 'SKYRIMSE', outfile)

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, "Expected Jiaran nif"


@TT.category('FO4', 'BODYPART')
@TT.expect_errors(("Could not find materials file",))
def TEST_FULL_PRECISION():
    """Can set full precision."""
    testfile = TTB.test_file(r"tests\FO4\Meshes\OtterFemHead.nif")
    outfile = TTB.test_file(r"tests\out\TEST_FULL_PRECISION.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    
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


@TT.category('FO4', 'BODYPART')
@TT.expect_errors(("Could not find materials file",))
def TEST_FULL_PRECISION_OPTION():
    """The export dialog's full-precision option sets/clears the shape's hasFullPrecision property."""
    testfile = TTB.test_file(r"tests\FO4\Meshes\OtterFemHead.nif")
    out_on = TTB.test_file(r"tests\out\TEST_FULL_PRECISION_OPTION_on.nif")
    out_off = TTB.test_file(r"tests\out\TEST_FULL_PRECISION_OPTION_off.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    head = bpy.context.object
    assert not head.get('hasFullPrecision'), "Fixture starts without full precision"

    # Setting the option writes the property and the nif flag.
    BD.ObjectSelect([head], active=True)
    bpy.ops.export_scene.pynifly(filepath=out_on, target_game='FO4',
                                 export_full_precision=True, intuit_defaults=False)
    assert head['hasFullPrecision'], "Option set the object's hasFullPrecision property"
    assert pyn.NifFile(out_on).shapes[0].properties.hasFullPrecision, \
        "Option stored full precision in the nif"

    # Clearing the option removes the property and exports half precision.
    BD.ObjectSelect([head], active=True)
    bpy.ops.export_scene.pynifly(filepath=out_off, target_game='FO4',
                                 export_full_precision=False, intuit_defaults=False)
    assert 'hasFullPrecision' not in head, "Option cleared the object's hasFullPrecision property"
    assert not pyn.NifFile(out_off).shapes[0].properties.hasFullPrecision, \
        "Option stored half precision in the nif"


@TT.category('FO4', 'ARMATURE')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FO4_MANY_CHILDREN_EXPORT():
    """Export a nif whose root has >128 children (issue #406).

    EngineerScribe MOutfit's root NiNode has 132 direct children (bones + shapes).
    _reorder_switch_children walked children through a fixed 128-int buffer and
    then indexed range(count) past it, raising 'IndexError: invalid index'.
    Export must handle an arbitrary number of children.
    """
    from ctypes import c_int
    testfile = TTB.test_file(r"tests\FO4\MOutfit.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FO4_MANY_CHILDREN.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    for o in bpy.data.objects:
        o.select_set(True)
    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    bpy.context.view_layer.objects.active = root
    # This raised IndexError before the fix.
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    nif = pyn.NifFile(outfile)
    # The two PipBoy on/off objects are shape-key morph variants of
    # ScribeOutfitFullCap:0, so 6 exported objects -> 4 shapes.
    assert len(nif.shapes) == 4, f"All shapes exported: {len(nif.shapes)}"
    n = pyn.nifly.getNodeChildren(nif._handle, nif.rootNode.id, 0, None)
    assert n > 128, f"Root's many children survived round-trip: {n}"
