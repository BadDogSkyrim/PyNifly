"""Skyrim, Skyrim SE and FONV specifics tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('SETTINGS')
def TEST_NOSETTINGS():
    """Can import with all settings off (regression)."""
    testfile = TTB.test_file(r"tests\SkyrimSE\Meshes\circlet_celebrimbor.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_NOSETTINGS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 create_bones=False,
                                 blender_xf=False,
                                 rename_bones=False,
                                 import_animations=False,
                                 import_collisions=False,
                                 import_tris=False,
                                 rename_bones_niftools=False,
                                 import_shapekeys=False,
                                 apply_skinning=False,
                                 import_pose=False,)                                                                                           


@TT.category('SKYRIMSE')
def TEST_CIRCLET():
    """This high-precision circlet imports correctly and can be exported as a ground object."""
    testfile = TTB.test_file(r"tests\SkyrimSE\Meshes\circlet_celebrimbor.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_CIRCLET.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 create_bones=False,
                                 blender_xf=False,
                                 rename_bones=False,
                                 import_animations=False,
                                 import_collisions=False,
                                 import_tris=False,
                                 rename_bones_niftools=False,
                                 import_shapekeys=False,
                                 apply_skinning=False,
                                 import_pose=False,)                                                                                           
    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    bbox = TTB.get_obj_bbox(obj, worldspace=True)
    TT.assert_lt(bbox[0][0], -2, "X")
    TT.assert_gt(bbox[1][0], 2, "X")
    TT.assert_eq(TTB.find_vertex(obj.data, [0.0, 0.0, 0.0]), -1, "No vertex near origin")


@TT.category('SKYRIM', 'EXTRA_DATA')
def TEST_SHEATH():
    """Extra data nodes are imported and exported"""
    # The sheath has extra data nodes for Havok. These are imported as Blender empty
    # objects, and can be exported again.

    testfile = TTB.test_file(r"tests/Skyrim/Meshes/sheath_p1_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHEATH.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    bglist = [obj for obj in bpy.data.objects if obj.name.startswith("BSBehaviorGraphExtraData")]
    slist = [obj for obj in bpy.data.objects if obj.name.startswith("NiStringExtraData")]
    bgnames = set([obj.pyn_bsbehavior.name for obj in bglist])
    assert TT.is_eq(bgnames, set(["BGED"]), "BG extra data properties")
    snames = set([obj.pyn_nistrdata.name for obj in slist])
    assert TT.is_eq(snames, set(["HDT Havok Path", "HDT Skinned Mesh Physics Object"]), 
        "string extra data properties")

    # Write and check
    print('------- Can write extra data -------')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')


    print('------ Extra data checks out----')
    nifCheck:pyn.NiFile = pyn.NifFile(outfile)
    sheathShape = nifCheck.shapes[0]

    names = [x.name for x in nifCheck.root.extra_data(blockname="BSBehaviorGraphExtraData")]
    assert TT.is_contains("BGED", names, "BGED exists")
    bgedCheck = nifCheck.root.get_extra_data(name="BGED")
    assert TT.is_eq(bgedCheck.behavior_graph_file, r"AuxBones\SOS\SOSMale.hkx", 
                    "Extra data value")
    assert TT.is_eq(bgedCheck.controls_base_skeleton, True, "controls base skeleton")

    strings = [sd.name for sd in nifCheck.root.extra_data(blockname="NiStringExtraData")]
    assert TT.is_contains("HDT Havok Path", strings, "havoc path")
    assert TT.is_contains("HDT Skinned Mesh Physics Object", strings, "physics object")


@TT.category('SKYRIM', 'EXTRA_DATA')
def TEST_FEET():
    """Extra data nodes are imported and exported"""
    # Feet have extra data nodes that are children of the feet mesh. This parent/child
    # relationship must be preserved on import and export.
    testfile = TTB.test_file(r"tests/SkyrimSE/Meshes/caninemalefeet_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FEET.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    feet = bpy.data.objects['FootLowRes']
    assert TT.is_eq(len(feet.children), 1, "Feet have children")
    assert TT.is_eq(feet.children[0].pyn_nistrdata.name, "SDTA", "Feet have extra data child")
    assert TT.is_eq(feet.children[0].pyn_nistrdata.value.startswith('[{"name"'), True, "Feet have string data")

    # Write and check that it's correct. Only the feet have to be selected--the extra data
    # goes because the object is a child of the feet object.
    bpy.ops.object.select_all(action='DESELECT')
    feet.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifCheck = pyn.NifFile(outfile)
    feetShape = nifCheck.shapes[0]
    strdata = feetShape.get_extra_data(blockname="NiStringExtraData")
    assert TT.is_eq(strdata.name, 'SDTA', "String data name")
    assert TT.is_eq(strdata.string_data.startswith('[{"name"'), True, "String data value")


@TT.category('SKYRIM', 'EXTRA_DATA')
def TEST_FEET_MULTI():
    """Extra data nodes are exported only once"""
    # These feet have multiple "shell" layers, each with its own extra data. Ensure the
    # extra data is only written once.
    testfile = TTB.test_file(r"tests/SkyrimSE/Meshes/felinefuzzyfeet.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FEET_MULTI.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    feet = bpy.data.objects['FootLowRes']
    TT.assert_eq(len(feet.children), 1, "Feet children")
    TT.assert_eq(feet.children[0].pyn_nistrdata.name, "SDTA", "extra data child name")
    assert feet.children[0].pyn_nistrdata.value.startswith('[{"name"'), "Feet have string data"

    ### WRITE ###
     
    BD.ObjectSelect([root for root in bpy.context.scene.objects if root.get('pynRoot', False)], 
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    ### CHECK ###

    nifCheck = pyn.NifFile(outfile)
    TT.assert_eq(nifCheck.root.get_extra_data(blockname="NiStringExtraData"), None, 
        "No string data on root")
    for shape in nifCheck.shapes:
        strdata = [sd for sd in shape.extra_data(blockname="NiStringExtraData")]
        TT.assert_eq(len(strdata), 1, f"{shape.name} has one extra data")
        assert strdata[0].name == 'SDTA', "String data name written correctly"
        assert strdata[0].string_data.startswith('[{"name"'), "String data value written correctly"


@TT.category('SKYRIM', 'EXTRA_DATA')
@TT.expect_errors(("Could not find texture", "Could not load"))
def TEST_DECAL_PLACEMENT():
    """BSDecalPlacementVectorExtraData round-trip."""
    import json

    testfile = TTB.test_file(r"tests\SkyrimSE\malebody_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_DECAL_PLACEMENT.nif", output=True)

    # --- pyn-layer: read original decal data ---
    nif_orig = pyn.NifFile(testfile)
    orig_decals = []
    for ed in nif_orig.rootNode.extra_data(blockname="BSDecalPlacementVectorExtraData"):
        orig_decals.append((ed.name, ed.vector_blocks))
    for shape in nif_orig.shapes:
        for ed in shape.extra_data(blockname="BSDecalPlacementVectorExtraData"):
            orig_decals.append((ed.name, ed.vector_blocks))
    log.info(f"Original decal extra data count: {len(orig_decals)}")
    TT.assert_gt(len(orig_decals), 0, "original has decal data")

    for name, blocks in orig_decals:
        log.info(f"  '{name}': {len(blocks)} blocks")
        for bi, block in enumerate(blocks):
            log.info(f"    block[{bi}]: {len(block)} vectors")
            TT.assert_gt(len(block), 0, f"block {bi} has vectors")

    # --- Blender import ---
    bpy.ops.import_scene.pynifly(filepath=testfile, create_collection=True)
    import_coll = bpy.context.collection

    decal_objs = [o for o in import_coll.all_objects
                  if o.name.startswith("BSDecalPlacementVectorExtraData")]
    TT.assert_gt(len(decal_objs), 0, "decal empties imported")

    for dobj in decal_objs:
        dname = dobj.pyn_bsdecal.name
        dval = json.loads(dobj.pyn_bsdecal.value)
        log.info(f"Imported decal '{dname}': {len(dval)} blocks")
        TT.assert_gt(len(dval), 0, f"decal '{dname}' has blocks")

    # --- Export ---
    BD.ObjectSelect(list(import_coll.all_objects), active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --- Verify exported NIF ---
    nif_out = pyn.NifFile(outfile)
    out_decals = []
    for ed in nif_out.rootNode.extra_data(blockname="BSDecalPlacementVectorExtraData"):
        out_decals.append((ed.name, ed.vector_blocks))
    for shape in nif_out.shapes:
        for ed in shape.extra_data(blockname="BSDecalPlacementVectorExtraData"):
            out_decals.append((ed.name, ed.vector_blocks))
    TT.assert_eq(len(out_decals), len(orig_decals), "decal count preserved")

    for (orig_name, orig_blocks), (out_name, out_blocks) in zip(orig_decals, out_decals):
        TT.assert_eq(out_name, orig_name, "decal name preserved")
        TT.assert_eq(len(out_blocks), len(orig_blocks), f"block count for '{orig_name}'")
        for bi, (ob, nb) in enumerate(zip(orig_blocks, out_blocks)):
            TT.assert_eq(len(nb), len(ob), f"vector count block[{bi}] of '{orig_name}'")
            for vi, (ov, nv) in enumerate(zip(ob, nb)):
                TT.assert_equiv(nv[0][0], ov[0][0], f"point.x [{bi}][{vi}]")
                TT.assert_equiv(nv[0][1], ov[0][1], f"point.y [{bi}][{vi}]")
                TT.assert_equiv(nv[0][2], ov[0][2], f"point.z [{bi}][{vi}]")
                TT.assert_equiv(nv[1][0], ov[1][0], f"normal.x [{bi}][{vi}]")
                TT.assert_equiv(nv[1][1], ov[1][1], f"normal.y [{bi}][{vi}]")
                TT.assert_equiv(nv[1][2], ov[1][2], f"normal.z [{bi}][{vi}]")


@TT.category('SKYRIM', 'OSD')
def TEST_OSD_IMPORT():
    """Can import a BodySlide OSD file as shape keys."""
    niffile = TTB.test_file(r"tests\SkyrimSE\Bodyslide\BD HIMBO Bandit 3.nif")
    osdfile = TTB.test_file(r"tests\SkyrimSE\Bodyslide\BD HIMBO Bandit 3.osd")

    # Import the NIF to get the mesh
    bpy.ops.import_scene.pynifly(filepath=niffile,
                                 rename_bones=False,
                                 blender_xf=False)

    # Select all mesh objects for OSD import
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    assert len(meshes) > 0, "NIF has mesh objects"
    log.debug(f"Mesh objects for OSD: {[m.name for m in meshes]}")
    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]

    # Import OSD
    bpy.ops.import_scene.pynifly_osd(filepath=osdfile)

    # Find the shape that got shape keys
    obj = next((o for o in meshes if o.data.shape_keys is not None), None)
    assert obj is not None, "At least one mesh got shape keys from OSD"
    keys = obj.data.shape_keys.key_blocks
    assert TT.is_gt(len(keys), 10, f"Got multiple shape keys: {len(keys)}")

    # Check that Basis exists and a known slider is present
    assert 'Basis' in keys, "Has Basis shape key"
    slider_names = [k.name for k in keys]
    log.debug(f"Shape keys: {slider_names[:10]}...")
    assert any('Biceps' in n for n in slider_names), \
        f"Has a Biceps slider, got: {slider_names[:5]}..."


@TT.category('FONV')
@TT.expect_errors(("Could not find image shader node",))
def TEST_FONV():
    """Basic FONV mesh import and export"""
    testfile = TTB.test_file("tests/FONV/9mmscp.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_FONV.nif")
     
    bpy.ops.import_scene.pynifly(filepath=testfile)
    grip = bpy.data.objects['Ninemm:0']
    coll = bpy.data.objects['bhkConvexVerticesShape']
    colbb = TTB.get_obj_bbox(coll)
    assert grip is not None, "Have grip"
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


@TT.category('FONV')
@TT.expect_errors(("Could not find image shader node",))
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


@TT.category('SKYRIM')
@TT.expect_errors(("Skyrim LE does not support per-chunk materials",))
def TEST_EMPTY_NODES():
    """Empty nodes export with the rest."""
    testfile = TTB.test_file(r"tests\Skyrim\farmhouse01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_EMPTY_NODES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    root = [obj for obj in bpy.data.objects if 'pynRoot' in obj][0]
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    assert "L2_Ivy" in nifout.nodes, "Has empty node"


@TT.category('SKYRIM')
@TT.expect_errors(("Error setting pynNodeFlags",))
def TEST_EMPTY_FLAGS():
    """Empty pyNodeFlags doesn't cause an error."""
    testfile = TTB.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_EMPTY_FLAGS.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    
    obj = bpy.context.object
    assert obj['pynNodeFlags'] != "", "pynNodeFlags is not empty"

    obj['pynNodeFlags'] = "XYZ"
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    assert "FarmBench01:5" in nifout.nodes, "Has object"
    assert nifout.nodes["FarmBench01:5"].properties.flags == 0, "Has zero flags"


@TT.category('SKYRIM')
def TEST_NO_SHADER():
    """Shapes with no shader import with no material and export with no shader."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\loincloth_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_NO_SHADER.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Check which shapes have shaders in the source NIF
    nifin = pyn.NifFile(testfile)
    shapes_without_shader = []
    shapes_with_shader = []
    for s in nifin.shapes:
        if s.properties.shaderPropertyID == pyn.NODEID_NONE:
            shapes_without_shader.append(s.name)
        else:
            shapes_with_shader.append(s.name)

    assert TT.is_gt(len(shapes_without_shader), 0,
                     "Source NIF has shapes without shaders")
    assert TT.is_gt(len(shapes_with_shader), 0,
                     "Source NIF has shapes with shaders")

    # Shapes without shader should have no Blender material and display as wireframe
    for name in shapes_without_shader:
        obj = TTB.find_shape(name)
        assert TT.is_eq(obj.active_material, None,
                         f"Shape '{name}' has no material")
        assert TT.is_eq(obj.display_type, 'WIRE',
                         f"Shape '{name}' displays as wireframe")

    # Shapes with shader should have a material
    for name in shapes_with_shader:
        obj = TTB.find_shape(name)
        assert obj.active_material is not None, f"Shape '{name}' has a material"

    # Export all shapes
    bpy.ops.object.select_all(action='DESELECT')
    for name in shapes_without_shader + shapes_with_shader:
        TTB.find_shape(name).select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    # Check skin instance types on import
    # VirtualGround has NiSkinInstance in the source NIF
    vg = TTB.find_shape("VirtualGround")
    if vg:
        assert TT.is_eq(vg.get("pynSkinInstanceType", ""), "NiSkinInstance",
                         "VirtualGround has NiSkinInstance custom property")

    # Verify roundtrip: shapes without shader should still have no shader
    nifout = pyn.NifFile(outfile)
    for name in shapes_without_shader:
        shape_out = nifout.shape_dict[name]
        assert TT.is_eq(shape_out.properties.shaderPropertyID, pyn.NODEID_NONE,
                         f"Exported shape '{name}' has no shader")

    # Shapes with shader should still have a shader
    for name in shapes_with_shader:
        shape_out = nifout.shape_dict[name]
        assert shape_out.properties.shaderPropertyID != pyn.NODEID_NONE, \
            f"Exported shape '{name}' has a shader"

    # VirtualGround should roundtrip as NiSkinInstance (no partitions)
    if 'VirtualGround' in nifout.shape_dict:
        vg_out = nifout.shape_dict['VirtualGround']
        assert TT.is_eq(vg_out.skin_instance_name, "NiSkinInstance",
                         "VirtualGround exports with NiSkinInstance")

    # Shapes with partitions should still have BSDismemberSkinInstance
    for name in shapes_with_shader:
        shape_out = nifout.shape_dict[name]
        if shape_out.skin_instance_name:
            assert TT.is_eq(shape_out.skin_instance_name, "BSDismemberSkinInstance",
                             f"Shape '{name}' keeps BSDismemberSkinInstance")


@TT.category('SKYRIM')
def TEST_PRETTY_BONE_POSITIONS():
    """Pretty bone rotations preserve bone world positions."""
    testfile = TTB.test_file(r"tests\SkyrimSE\skeleton_vanilla.nif")

    for pretty in [False, True]:
        label = "pretty" if pretty else "plain"

        bpy.ops.import_scene.pynifly(filepath=testfile,
                                     rotate_bones_pretty=pretty,
                                     create_bones=False)
        arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')

        # Force dep graph evaluation before reading pose matrices.
        bpy.context.view_layer.update()

        # Pose should match rest — both position and orientation.
        pos_mismatches = []
        rot_mismatches = []
        for pb in arma.pose.bones:
            bone = arma.data.bones[pb.name]
            rest_mat = bone.matrix_local
            pose_mat = pb.matrix
            pos_diff = (pose_mat.translation - rest_mat.translation).length
            if pos_diff > 0.001:
                pos_mismatches.append(f"  {pb.name}: pos_diff={pos_diff:.4f}")
            rot_diff = max(abs(rest_mat[i][j] - pose_mat[i][j])
                          for i in range(3) for j in range(3))
            if rot_diff > 0.01:
                rot_mismatches.append(f"  {pb.name}: rot_diff={rot_diff:.4f}")
        if pos_mismatches:
            log.error(f"[{label}] {len(pos_mismatches)} bones with position mismatch:\n"
                      + "\n".join(pos_mismatches[:10]))
        if rot_mismatches:
            log.error(f"[{label}] {len(rot_mismatches)} bones with rotation mismatch:\n"
                      + "\n".join(rot_mismatches[:10]))
        assert TT.is_eq(len(pos_mismatches), 0, f"[{label}] all bone positions match")
        assert TT.is_eq(len(rot_mismatches), 0, f"[{label}] all bone rotations match")

        if not pretty:
            plain_positions = {b.name: b.matrix_local.translation.copy()
                               for b in arma.data.bones}
            TTB.clear_all()
        else:
            pretty_positions = {b.name: b.matrix_local.translation.copy()
                                for b in arma.data.bones}

    # Both imports should have the same bones
    assert TT.is_eq(sorted(plain_positions.keys()), sorted(pretty_positions.keys()),
                     "Same bones in both imports")

    # Bone head positions should match — pretty only changes orientation, not position.
    for name in plain_positions:
        assert TT.is_equiv(pretty_positions[name], plain_positions[name],
                            f"Bone '{name}' position matches", e=0.001)

    # Export the pretty-rotated skeleton and verify bone transforms match the original.
    outfile = TTB.test_file(r"tests\Out\TEST_PRETTY_BONE_POSITIONS.nif", output=True)
    root = TTB.find_shape("skeleton.nif:ROOT", type='EMPTY')
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nif_orig = pyn.NifFile(testfile)
    nif_out = pyn.NifFile(outfile)
    for bone_name in nif_orig.nodes:
        if bone_name in nif_out.nodes:
            xf_orig = BD.transform_to_matrix(
                nif_orig.get_node_xform_to_global(bone_name))
            xf_out = BD.transform_to_matrix(
                nif_out.get_node_xform_to_global(bone_name))
            assert TTB.MatNearEqual(xf_out, xf_orig, 0.01), \
                f"Bone '{bone_name}' transform preserved:\n{xf_out}\n!=\n{xf_orig}"


@TT.category('SKYRIMSE')
def TEST_TREE_DIVERGENT_BIND_POSE():
    """A skinned tree whose bone NiNode and skin bind position disagree must still
    import with pose == rest (import_pose=False).

    treepineforest02 authors TrunkBone's NiNode at the origin while the skin binds
    it ~601 units away. With import_pose=False the bone rest is the bind position,
    so the pose must stay at rest -- it must NOT be dragged to the divergent NiNode
    (which produced a 601-unit pose/rest gap on TrunkBone and a spurious second
    armature). Pose == rest for every bone in every armature.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\treepineforest02.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rotate_bones_pretty=True)
    bpy.context.view_layer.update()
    armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert armatures, "Imported a skinned tree with an armature"

    mismatches = []
    for arma in armatures:
        for pb in arma.pose.bones:
            rest = arma.data.bones[pb.name].matrix_local
            diff = max(abs(rest[i][j] - pb.matrix[i][j])
                       for i in range(4) for j in range(4))
            if diff > 0.01:
                mismatches.append(f"{arma.name}/{pb.name}: maxdiff={diff:.3f}")
    assert not mismatches, \
        "Tree bone pose must equal rest even when NiNode and bind disagree:\n" \
        + "\n".join(mismatches)


@TT.category('SKYRIMSE')
def TEST_COLLISION_TAIL():
    """Tail collision mesh cap faces should round-trip without gaps."""
    testfile = TTB.test_file(r"tests\SkyrimSE\Tail Collision.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_TAIL.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    tail = TTB.find_shape("CollisionTail")

    # Find verts near y=-30.2653 and add cap faces to close the gap at the
    # end of the mesh where the positive-x and negative-x halves are open.
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(tail.data)
    bm.verts.ensure_lookup_table()

    # Merge coincident verts (the mesh has duplicates at seams).
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.01)
    bm.verts.ensure_lookup_table()

    near_verts = [v for v in bm.verts if abs(v.co.y - (-30.2653)) < 1.0]
    assert TT.is_gt(len(near_verts), 4, "Found enough verts near y=-30.2653")

    # Sort in circular order around centroid (in the xz plane) so we can
    # create a well-formed face.
    cx = sum(v.co.x for v in near_verts) / len(near_verts)
    cz = sum(v.co.z for v in near_verts) / len(near_verts)
    near_verts.sort(key=lambda v: math.atan2(v.co.z - cz, v.co.x - cx))

    # Create a cap face (ngon) connecting all the near verts.
    try:
        bm.faces.new(near_verts)
    except ValueError:
        pass  # degenerate or already exists

    bm.to_mesh(tail.data)
    bm.free()
    tail.data.update()

    # Export
    BD.ObjectSelect([tail], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # Validate: in the exported NIF, verts near y=-30.2653 should have no
    # geometric gaps in the cap.  UV splitting may duplicate verts at the
    # same position, so we check by position rather than by vertex index.
    nif_out = pyn.NifFile(outfile)
    shape = nif_out.shapes[0]
    verts_out = shape.verts
    tris_out = shape.tris

    near_out = {i for i in range(len(verts_out))
                if abs(verts_out[i][1] - (-30.2653)) < 1.0}
    assert TT.is_gt(len(near_out), 4, "Exported file has verts near y=-30.2653")

    # Round positions so coincident verts (from UV splits) map to the same key.
    def pos_key(vi):
        v = verts_out[vi]
        return (round(v[0], 2), round(v[1], 2), round(v[2], 2))

    from collections import Counter
    edge_count = Counter()
    for tri in tris_out:
        for a, b in [(tri[0], tri[1]), (tri[1], tri[2]), (tri[0], tri[2])]:
            ek = tuple(sorted([pos_key(a), pos_key(b)]))
            edge_count[ek] += 1

    # A boundary edge (count==1) between two near-y positions is a gap.
    near_positions = {pos_key(i) for i in near_out}
    gaps = [(e, c) for e, c in edge_count.items()
            if c == 1 and e[0] in near_positions and e[1] in near_positions]
    assert TT.is_eq(len(gaps), 0,
                     f"No gaps among cap verts ({len(gaps)} boundary edges)")


@TT.category('SKYRIM', 'IMPORT')
def TEST_IMPORT_DUPLICATE_TRIS_WARNS():
    """Triangles Blender can't represent are reported, not silently dropped.

    Blender holds at most one face per set of vertex indices, so mesh.validate()
    quietly deletes coincident duplicates. caveghall1way01's L2_Roots:8 has 12."""
    import logging
    testfile = TTB.test_file(
        r"tests\SkyrimSE\meshes\dungeons\caves\green\smallhall\caveghall1way01.nif")

    shape = [s for s in pyn.NifFile(testfile).shapes if s.name == "L2_Roots:8"][0]
    dups = len(shape.tris) - len(set(frozenset(t) for t in shape.tris))
    assert TT.is_gt(dups, 0, f"fixture really has duplicate tris ({dups})")

    messages = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    cap = _Cap(level=logging.WARNING)
    pyn_log = logging.getLogger("pynifly")
    pyn_log.addHandler(cap)
    try:
        bpy.ops.import_scene.pynifly(filepath=testfile)
    finally:
        pyn_log.removeHandler(cap)

    warned = [m for m in messages
              if "L2_Roots:8" in m and f"{dups} duplicate" in m]
    assert TT.is_neq(warned, [],
                     f"duplicate-triangle drop was reported (saw {messages[:3]})")
