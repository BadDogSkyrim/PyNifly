"""Fallout 4: partitions, connect points, furniture tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('FO4', 'SETTINGS')
def TEST_DRAGDROP_IMPORT():
    """Drag-and-drop import path: Blender's FileHandler invokes the importer with
    'directory' + 'files' set (and no filepath). The operator must resolve the
    files from the directory and import them. This exercises that path the same
    way a viewport drop does, minus the interactive bits."""
    import os
    testfile = TTB.test_file(r"tests/FO4/BaseMaleHead.nif")
    nifdir = os.path.dirname(testfile)

    # Simulate a single-file drop: directory + files, no filepath.
    bpy.ops.import_scene.pynifly(
        directory=nifdir + os.sep,
        files=[{"name": "BaseMaleHead.nif"}])

    head = TTB.find_object("BaseMaleHead:0")
    assert head is not None, "drag-and-drop import created the head mesh"
    assert TT.is_eq(int(head.location.z), 120, "imported head at head position")


@TT.category('FO4', 'BODYPART', 'ARMATURE', 'CONNECTPOINT')
@TT.expect_errors( ("Unknown block type: bhkRagdollSystem",
                    "bhkPhysicsSystem decode failed: No geometry decoded") )
@TT.parameterize(("xf", "bonerot"), [("NONE", "NONE"),
                                     ("BLENDER", "NONE"),
                                     ("NONE", "PRETTY"),
                                     ("BLENDER", "PRETTY")])
def TEST_CONNECT_SKEL(xf, bonerot):
    """Can import and export FO4 skeleton file with no shapes"""
    print(f"Can import and export FO4 skeleton file with no shapes, transform {xf}, bone rotation {bonerot}")
    testname = f"TEST_SKEL_{xf}_{bonerot}"
    testfile = TTB.test_file(r"skeletons\FO4\skeleton.nif")
    outfile = TTB.test_file(r"tests/out/" + testname + ".nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                    create_bones=False, 
                                    blender_xf=(xf == "BLENDER"),
                                    rotate_bones_pretty=(bonerot == "PRETTY"),
                                    )

    arma = [a for a in bpy.data.objects if a.type == 'ARMATURE'][0]
    assert TT.is_contains('Root', arma.data.bones, "Root bone")
    rootbone = arma.data.bones['Root']
    assert TT.is_contains('Leg_Thigh.L', arma.data.bones, "Have left thigh bone")
    assert TT.is_contains('RibHelper.L', arma.data.bones, "Have rib helper bone")
    assert TT.is_notcontains('L_RibHelper.L', arma.data.bones, "Do not have nif name for bone")
    assert TT.is_notcontains('L_RibHelper', bpy.data.objects, "Do not have rib helper object")
    assert TT.is_eq(arma.data.bones['RibHelper.L'].parent.name, 'Chest', "ribhelper parent")

    # Root bone's orientation matches that of the nif
    nif = pyn.NifFile(testfile)
    rootnode = nif.nodes["Root"]
    rbm = rootbone.matrix_local @ BD.game_rotations[BD.game_axes['FO4']][1]
    assert TT.is_matnearequal(rbm, BD.transform_to_matrix(rootnode.transform), 
                                "Bone transform matches nif")

    # Parent connect points are children of the armature. Could also be children of the root
    # but they get transposed based on the armature bones' transforms.
    cp_lleg = bpy.data.objects['BSConnectPointParents::P-ArmorLleg']
    assert TT.is_eq(cp_lleg.parent.type, 'ARMATURE', f"P-ArmorLleg parent")
    
    log.debug(f"cp_lleg location blender xf={xf} bone rot={bonerot}: {cp_lleg.matrix_world.translation}")
    expected_loc = Vector((-8.7480, -3.1508, 35.2600))
    if xf == "BLENDER":
        expected_loc = expected_loc * Vector((-0.1, -0.1, 0.1))
    assert TT.is_equiv(cp_lleg.matrix_world.translation, expected_loc,
                        f"P-ArmorLleg world location with Blender xf {xf}")

    # Import settings should have been remembered
    BD.ObjectSelect([bpy.data.objects['skeleton.nif:ROOT']])
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                    target_game='FO4', 
                                    blender_xf=(xf == "BLENDER"),
                                    preserve_hierarchy=True,
                                    rotate_bones_pretty=(bonerot == "PRETTY"),
                                    intuit_defaults=False,)

    skel_in = pyn.NifFile(testfile)
    skel_out = pyn.NifFile(outfile)
    assert TT.is_contains("L_RibHelper", skel_out.nodes, "Bones written to nif")
    assert TT.is_eq(skel_out.nodes["L_RibHelper"].parent.name, "Chest", f"RibHelper parent")
    helm_cp_in = [x for x in skel_in.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
    helm_cp_out = [x for x in skel_out.connect_points_parent if x.name.decode('utf-8') == 'P-ArmorHelmet'][0]
    assert TT.is_eq(helm_cp_out.parent.decode('utf-8'), 'HEAD', f"ArmorHelmet parent")
    assert TT.is_equiv(helm_cp_in.translation, helm_cp_out.translation[:], "ArmorHelmet location")


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors( ('Some faces have been assigned to more than one partition',) )
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
    CHK.Check_fo4MaleBody(nif2)
    

@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FO4_CUT_OFFSETS_ROUNDTRIP():
    """Cut offsets (dismemberment slice planes) survive Blender import/export.

    Import vanilla MaleBody, verify the FO4_CUT_OFFSETS object prop carries the
    per-subsegment cut lists; re-export; re-read the exported NIF and verify the
    cut floats land back on the same subsegments. All 37 vanilla cuts expected.
    """
    import json
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FO4_CUT_OFFSETS_ROUNDTRIP.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object

    # Custom prop carries the per-subseg cut lists, keyed by vertex-group name.
    raw = obj.get('FO4_CUT_OFFSETS')
    assert raw, "FO4_CUT_OFFSETS custom prop populated on import"
    cuts = json.loads(raw)
    assert TT.is_equiv(cuts["FO4 Seg 002 | 001 | Up Arm.R"],
                       [7.6055, 9.5069, 11.4083, 13.3096],
                       "Up Arm.R bearer cut offsets in prop", e=0.001)
    total_in = sum(len(v) for v in cuts.values())
    assert TT.is_eq(total_in, 37, "all vanilla cut offsets captured in prop")

    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nif2 = pyn.NifFile(outfile)
    chk_subs = {}
    for seg in nif2.shapes[0].partitions:
        for ss in seg.subsegments:
            chk_subs[ss.name] = ss
    total_out = sum(len(ss.cut_offsets) for ss in chk_subs.values())
    assert TT.is_eq(total_out, 37, "cut offsets preserved through Blender round-trip")
    assert TT.is_equiv(chk_subs["FO4 Seg 002 | 001 | Up Arm.R"].cut_offsets,
                       [7.6055, 9.5069, 11.4083, 13.3096],
                       "Up Arm.R bearer cuts after export", e=0.001)
    assert TT.is_equiv(chk_subs["FO4 Seg 002 | 003 | Lo Arm.R"].cut_offsets,
                       [5.6032, 7.4710, 9.3387, 11.2065, 13.0742],
                       "Lo Arm.R bearer cuts after export", e=0.001)


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
def TEST_FO4_CUT_DISKS_IMPORTED():
    """Cut-offset visualization disks are created on FO4 import, linked into a
    `<obj>_Cutpoints` collection and bone-parented to the dismember bone the
    SSF assigns, with the first Up Arm.R disk landing at the expected world
    position along the bone's limb axis (from bone orientation, not the
    hierarchy).

    Bone identity comes from MaleBody.ssf (a sibling fixture of the NIF):
    subseg (seg 2, sub 1) -> RArm_UpperArm -> Blender `Arm_UpperArm.R`. The
    limb axis is bone local +X (rotate-bones-pretty defaults OFF) and the first
    cut value is 7.6055.
    """
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = bpy.data.objects.get("BaseMaleBody:0")
    assert body is not None, "imported the body"
    arma = body.find_armature()
    assert arma is not None, "found the armature"

    # The grouping collection must exist with disks linked into it, and be
    # nested under the mesh's own collection.
    coll = bpy.data.collections.get(f"{body.name}_Cutpoints")
    assert coll is not None, "per-shape Cutpoints collection created"
    assert TT.is_gt(len(coll.objects), 0, "at least one cut disk in the collection")
    assert coll.name in [c.name for c in body.users_collection[0].children], \
        "Cutpoints collection nested under the mesh's collection"

    bone = arma.data.bones.get("Arm_UpperArm.R") or arma.data.bones.get("RArm_UpperArm")
    assert bone is not None, "upper-arm bone present"

    # Disk named "Cutpoint <bone> <n>"; first cut on the Up Arm.R bearer.
    disk_name = f"Cutpoint {bone.name} 0"
    disk = bpy.data.objects.get(disk_name)
    assert disk is not None, f"disk {disk_name} exists"

    # Disk records its dismember material (Up Arm.R class) as a hex string.
    assert TT.is_eq(disk.get('FO4_CUT_MATERIAL'), "0xb2e2764f",
                    "disk records the dismember material hash")

    # Disk must be parented to its dismember bone.
    assert TT.is_eq(disk.parent, arma, "disk parented to armature")
    assert TT.is_eq(disk.parent_type, 'BONE', "disk parent_type is BONE")
    assert TT.is_eq(disk.parent_bone, bone.name,
                    "disk parent_bone is the upper-arm bone")

    # Limb axis from bone orientation: +Y if pretty else +X (default OFF -> +X).
    pretty = bool(arma.get("PYN_ROTATE_BONES_PRETTY", False))
    axis = bone.matrix_local.to_3x3().col[1 if pretty else 0].normalized()
    expected_local = bone.head_local + axis * 7.6055
    expected_world = arma.matrix_world @ expected_local
    actual_world = disk.matrix_world.translation

    assert TT.is_equiv(list(actual_world), list(expected_world),
                       "first Up Arm.R cut disk at expected world position",
                       e=0.01)

    # Disk Z axis (cylinder normal) should align with the bone's limb axis —
    # otherwise the disk wouldn't be orthogonal to the bone.
    expected_axis_world = (arma.matrix_world.to_3x3() @ axis).normalized()
    disk_z_world = (disk.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    cos_a = abs(disk_z_world.dot(expected_axis_world))
    assert TT.is_gt(cos_a, 0.99,
                    f"disk normal aligns with bone axis (cos={cos_a:.4f})")


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
def TEST_FO4_CUT_DISKS_BASE_BONE():
    """A cut subseg covered by the SSF's BaseBoneName (not a DeltaBone) still
    gets its disk.

    Pack_UnderArmor_03_M's body SSF lists only the LEFT thigh in DeltaBones;
    the RIGHT thigh (subseg 5,0 'Thigh.R') is the segment's base bone
    (BaseBoneName 'RLeg_Thigh') and isn't enumerated. The importer used to find
    no SSF entry for it, warn, and skip its cut disk. The subseg's dismember
    material hash is the canonical bone link, so the disk must still be built.
    """
    testfile = TTB.test_file(r"tests\FO4\Pack_UnderArmor_03_M.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = bpy.data.objects.get("BaseMaleBody_03:0")
    assert body is not None, "imported the body"
    arma = body.find_armature()
    assert arma is not None, "found the armature"

    # Right-thigh bone (RLeg_Thigh -> renamed Leg_Thigh.R by default).
    rthigh = arma.data.bones.get("Leg_Thigh.R") or arma.data.bones.get("RLeg_Thigh")
    assert rthigh is not None, "right-thigh bone present"

    coll = bpy.data.collections.get(f"{body.name}_Cutpoints")
    assert coll is not None, "Cutpoints collection created"

    # A disk bone-parented to the right thigh must exist -- this is the cut that
    # used to be dropped because it was only in BaseBoneName, not DeltaBones.
    rthigh_disks = [o for o in coll.objects
                    if o.parent_type == 'BONE' and o.parent_bone == rthigh.name]
    assert TT.is_gt(len(rthigh_disks), 0,
                    "right-thigh cut disk created from base bone")
    assert TT.is_eq(rthigh_disks[0].get('FO4_CUT_MATERIAL'), "0xbf3a3cc5",
                    "right-thigh disk records RLeg_Thigh material hash")


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors((
    'Could not find materials file',
    'Could not find texture',
    'Could not load diffuse texture',
    'Could not load normal texture',
    'Target of controller not found',
    ))
def TEST_FO4_CUT_DISKS_GHOUL():
    """Cut visualization generalizes beyond humans. The Feral Ghoul is a
    creature with its own skeleton and its own dismember bone names
    (RUPPERARM, LCALF, RForeArm1, ...). Bone identity comes purely from the
    shape's SSF (FeralGhoulBase.ssf, a sibling fixture), so the disks attach
    to the correct creature bones without any human-specific table.
    """
    testfile = TTB.test_file(r"tests/FO4/FeralGhoulBase.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = bpy.data.objects.get("FeralGhoulBase:0")
    assert body is not None, "imported the ghoul body"
    arma = body.find_armature()
    assert arma is not None, "found the ghoul armature"

    # Cuts preserved on the mesh as a custom prop.
    assert 'FO4_CUT_OFFSETS' in body.keys(), "cut offsets on the mesh prop"

    # Cutpoints collection created with disks, nested under the mesh's collection.
    coll = bpy.data.collections.get(f"{body.name}_Cutpoints")
    assert coll is not None, "Cutpoints collection created for the creature"
    assert TT.is_gt(len(coll.objects), 0, "at least one cut disk created")

    # Every disk is bone-parented to a creature bone the SSF named (NOT a
    # human bone), and records its dismember material. The ghoul SSF bones
    # are upper-case creature names like RUPPERARM / LCALF.
    ssf_bones = {"RUPPERARM", "LUPPERARM", "RForeArm1", "LForeArm1",
                 "RTHIGH", "LTHIGH", "RCALF", "LCALF"}
    for disk in coll.objects:
        assert TT.is_eq(disk.parent_type, 'BONE', f"{disk.name} bone-parented")
        assert disk.parent_bone in arma.data.bones, \
            f"{disk.name} parent bone '{disk.parent_bone}' exists in armature"
        assert disk.parent_bone in ssf_bones, \
            f"{disk.name} attached to an SSF creature bone (got '{disk.parent_bone}')"
        assert disk.get('FO4_CUT_MATERIAL'), f"{disk.name} records its material"


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FO4_CUT_DISKS_EXPORT():
    """Phase 6: the cutpoint disks are authoritative on export. Moving a disk
    changes the cut offset written to the NIF — the edited disk geometry drives
    the export, overriding the round-tripped FO4_CUT_OFFSETS prop.
    """
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FO4_CUT_DISKS_EXPORT.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = bpy.data.objects.get("BaseMaleBody:0")
    arma = body.find_armature()
    assert body is not None and arma is not None, "imported body + armature"

    # The first Up Arm.R disk sits at the vanilla cut 7.6055 along the bone.
    disk = bpy.data.objects.get("Cutpoint Arm_UpperArm.R 0")
    assert disk is not None, "Up Arm.R cut disk 0 exists"
    bone = arma.data.bones["Arm_UpperArm.R"]
    pretty = bool(arma.get("PYN_ROTATE_BONES_PRETTY", False))
    axis_local = bone.matrix_local.to_3x3().col[1 if pretty else 0].normalized()
    axis_world = (arma.matrix_world.to_3x3() @ axis_local).normalized()

    # Slide the disk +5.0 distally along the bone: 7.6055 -> ~12.6055, a value
    # neither the round-trip prop nor the supply formula would ever produce.
    MOVE = 5.0
    disk.matrix_world = Matrix.Translation(axis_world * MOVE) @ disk.matrix_world

    body.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nif2 = pyn.NifFile(outfile)
    shape = nif2.shapes[0]
    UPARM = 0xb2e2764f
    cuts = []
    for seg in shape.partitions:
        for ss in getattr(seg, 'subsegments', []):
            if ss.material == UPARM and ss.cut_offsets:
                cuts.extend(ss.cut_offsets)
    assert TT.is_eq(len(cuts), 4, f"Up Arm.R bearer still carries 4 cuts (got {cuts})")
    # The moved disk's value is present; the original 7.6055 is gone.
    assert any(abs(c - 12.6055) < 0.1 for c in cuts), \
        f"moved disk reflected in export (~12.6 expected, got {sorted(cuts)})"
    assert not any(abs(c - 7.6055) < 0.1 for c in cuts), \
        f"original cut position vacated by the move (got {sorted(cuts)})"

    # An SSF was generated and the shape points at it.
    assert nif2.shapes[0].segment_file, "segment_file points at generated SSF"


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FO4_CUT_DISKS_EXPORT_SELECTED():
    """Selected cutpoint disks export even when they aren't in the body's
    name-matched collection. Models the "copy vanilla cutpoints onto another
    body" workflow: the donor disks live in a differently-named collection, so
    only the selection drives the export.
    """
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FO4_CUT_DISKS_EXPORT_SELECTED.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = bpy.data.objects.get("BaseMaleBody:0")

    # Break the collection name-match and the round-trip prop, so the ONLY way
    # cuts can reach the export is via the selected disks.
    coll = bpy.data.collections.get(f"{body.name}_Cutpoints")
    assert coll is not None, "cut disks imported"
    coll.name = "Donor_Cutpoints"
    if 'FO4_CUT_OFFSETS' in body.keys():
        del body['FO4_CUT_OFFSETS']

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    for d in coll.objects:
        d.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    cuts = _uparm_r_cuts(pyn.NifFile(outfile))
    # Disk path (selected) reproduces vanilla's exact 4 cuts; the formula
    # fallback would instead emit 6 cuts starting ~3.78.
    assert TT.is_eq(len(cuts), 4, f"Up Arm.R has vanilla's 4 cuts (got {cuts})")
    assert all(abs(c - e) < 0.05 for c, e in
               zip(cuts, [7.6055, 9.5069, 11.4083, 13.3096])), \
        f"cuts match vanilla, i.e. came from the selected disks (got {cuts})"


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FO4_CUT_DISKS_EXPORT_DUP_COLLECTION():
    """The cutpoint collection name-match tolerates Blender's .001 suffix.
    Duplicating a body yields e.g. CanineMaleBody_Cutpoints.001; the exact
    lookup misses it, so we strip the disambiguation suffix before matching.
    """
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FO4_CUT_DISKS_EXPORT_DUP.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = bpy.data.objects.get("BaseMaleBody:0")

    coll = bpy.data.collections.get(f"{body.name}_Cutpoints")
    assert coll is not None, "cut disks imported"
    coll.name = f"{body.name}_Cutpoints.001"   # simulate Blender duplicate suffix
    if 'FO4_CUT_OFFSETS' in body.keys():
        del body['FO4_CUT_OFFSETS']

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)                       # disks NOT selected — collection match must find them
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    cuts = _uparm_r_cuts(pyn.NifFile(outfile))
    assert TT.is_eq(len(cuts), 4, f"Up Arm.R has vanilla's 4 cuts (got {cuts})")
    assert all(abs(c - e) < 0.05 for c, e in
               zip(cuts, [7.6055, 9.5069, 11.4083, 13.3096])), \
        f"cuts match vanilla, i.e. the .001 collection was matched (got {cuts})"


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
def TEST_FO4_CUT_DISKS_IMPORT_OPTION():
    """import_cutpoints=False suppresses the cut-disk visualization, but the cut
    data is still preserved on the mesh (so it round-trips on export)."""
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, import_cutpoints=False)

    body = bpy.data.objects.get("BaseMaleBody:0")
    assert body is not None, "imported body"
    assert 'FO4_CUT_OFFSETS' in body.keys(), "cut data preserved with viz disabled"
    assert bpy.data.collections.get(f"{body.name}_Cutpoints") is None, \
        "no Cutpoints collection when import_cutpoints is False"
    disks = [o for o in bpy.data.objects if 'FO4_CUTPOINT' in o]
    assert TT.is_eq(len(disks), 0, f"no cut disks created (got {len(disks)})")


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors(('will not dismember in game',))
def TEST_FO4_MISSING_CUTS_WARN():
    """A body/outfit with limb dismember segments but no cut offsets is flagged
    on import with a warning (it won't dismember in game), instead of being
    imported silently.

    MOutfit_bad.nif has a body + jacket + jeans, each carrying limb segments
    (Up Arm/Lo Arm/Thigh/Calf) but zero cut offsets everywhere.
    """
    import logging
    testfile = TTB.test_file(r"tests/FO4/Meshes/MOutfit_bad.nif")

    # Collect every pynifly log record emitted during the import.
    records = []
    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())
    plog = logging.getLogger("pynifly")
    h = _Collector()
    plog.addHandler(h)
    try:
        bpy.ops.import_scene.pynifly(filepath=testfile)
    finally:
        plog.removeHandler(h)

    dismember_warnings = [m for m in records if "will not dismember in game" in m]
    assert TT.is_gt(len(dismember_warnings), 0,
                    "import warned that the outfit will not dismember in game")
    # All three shapes should be called out (body, jacket, jeans).
    assert TT.is_gt(len(dismember_warnings), 2,
                    f"each limb-segmented shape warned (got {len(dismember_warnings)})")


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FO4_SSF_GENERATED():
    """Phase 4: cut offsets are supplied from bone geometry and an SSF file is
    written alongside the exported NIF.

    Imports vanilla MaleBody, *clears* its FO4_CUT_OFFSETS so the supply step
    has to regenerate from the formula, exports, then verifies (a) the exported
    NIF carries non-zero cut offsets on the bearer subsegments, (b) an SSF file
    sits next to the NIF, and (c) the SSF contains the expected shape entry
    with DeltaBones for each dismember bone the supply step recognized.
    """
    import os, json
    testfile = TTB.test_file(r"tests/FO4/VanillaMaleBody.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_FO4_SSF_GENERATED.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    # Force the supply *formula* to regenerate cuts from geometry: drop the
    # round-trip prop AND the cutpoint disks (otherwise the Phase 6 disk path
    # would drive the export). This mirrors a body that arrived with no SSF and
    # no cuts at all — the dog-body case the supply step exists for.
    if 'FO4_CUT_OFFSETS' in obj.keys():
        del obj['FO4_CUT_OFFSETS']
    disk_coll = bpy.data.collections.get(f"{obj.name}_Cutpoints")
    if disk_coll:
        for d in list(disk_coll.objects):
            bpy.data.objects.remove(d, do_unlink=True)
        bpy.data.collections.remove(disk_coll)

    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    # (a) NIF has cut offsets.
    nif2 = pyn.NifFile(outfile)
    chk_subs = {}
    for seg in nif2.shapes[0].partitions:
        for ss in seg.subsegments:
            chk_subs[ss.name] = ss
    total_cuts = sum(len(ss.cut_offsets) for ss in chk_subs.values())
    assert TT.is_gt(total_cuts, 20,
                    "supply step produced a reasonable number of cuts")

    # (b) SSF written next to the NIF.
    ssf_path = os.path.splitext(outfile)[0] + ".ssf"
    assert os.path.exists(ssf_path), f"SSF file written at {ssf_path}"

    # (c) SSF content has the expected shape entry and bones.
    with open(ssf_path, "r", encoding="utf-8") as f:
        ssf = json.load(f)
    assert TT.is_eq(list(ssf.keys()), ["BaseMaleBody:0"],
                    "SSF top-level key is the shape name")
    entry = ssf["BaseMaleBody:0"]
    bone_names = sorted(d["BoneName"] for d in entry["DeltaBones"])
    expected_bones = sorted([
        "RArm_UpperArm", "RArm_ForeArm1",
        "LArm_UpperArm", "LArm_ForeArm1",
        "RLeg_Thigh", "RLeg_Calf",
        "LLeg_Thigh", "LLeg_Calf",
    ])
    assert TT.is_eq(bone_names, expected_bones,
                    "SSF DeltaBones covers all 8 human dismember bones")
    assert TT.is_eq(entry["BaseBoneName"], "DISABLED", "BaseBoneName default")
    assert TT.is_eq(entry["uiNumDeltas"], len(expected_bones), "uiNumDeltas")


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
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
    TT.assert_eq(visor.active_material.pyn_shader.envMapTexture, "shared/cubemaps/shinyglass_e.dds",
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


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
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


@TT.category('FO4', 'BODYPART', 'PARTITIONS')
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


@TT.category('SKYRIM', 'BODYPART', 'PARTITIONS')
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
    CHK.Check_malehead(nif2)


@TT.category('SKYRIM', 'PARTITIONS')
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


@TT.category('FO4')
@TT.expect_errors(("is not in the armature",))
def TEST_MUTANT():
    """Test that the supermutant body imports correctly the *second* time"""
    testfile = TTB.test_file(r"tests/FO4/testsupermutantbody.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, create_bones=False)

    testnif = pyn.NifFile(testfile)
    assert round(testnif.shapes[0].global_to_skin.translation[2]) == -140, f"Expected -140 z translation in first nif, got {testnif.shapes[0].global_to_skin.translation[2]}"

    sm1 = bpy.context.object
    assert round(sm1.location[2]) == 140, f"Expect first supermutant body at 140 Z, got {sm1.location[2]}"

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, create_bones=False)
    sm2 = bpy.context.object
    assert sm2 != sm1, f"Second import created second object: {sm2.name}"
    assert round(sm2.location[2]) == 140, f"Expect supermutant body at 140 Z, got {sm2.location[2]}"


@TT.category('FO4')    
@TT.expect_errors(("references invalid group",))
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


@TT.category('FO4', 'PARTITIONS')
@TT.expect_errors( ("Some faces have been assigned to more than one partition",))
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


@TT.category('SKYRIMSE', 'SCALING', 'FURNITURE')
def TEST_SCALING_OBJ():
    """Can scale simple object with furniture markers"""
    testfile = TTB.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SCALING_OBJ.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)

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
                                            blender_xf=True)

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    bcheck = nifcheck.shapes[0]
    fmcheck = nifcheck.root.get_extra_data(name='FRN')
    bchmax = max([v[2] for v in bcheck.verts])
    assert bchmax > 30, f"Max Z is scaled up: {bchmax}"
    assert len(fmcheck.furniture_markers) == 2, f"Wrote the furniture marker correctly: {len(fmcheck.furniture_markers)}"
    assert fmcheck.furniture_markers[0].offset[2] > 30, f"Furniture marker Z scaled up: {fmcheck.furniture_markers[0].offset[2]}"


@TT.category('FO4', 'PARTITIONS')
@TT.expect_errors(('Wrote faces without partitions', 'Some faces are in multiple partitions',
                   'in no partition'))
def TEST_HYENA_PARTITIONS():
    """Partitions export successfully, with warnings"""
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


@TT.category('SKYRIMSE', 'PARTITIONS')
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


@TT.category('FO4')
def TEST_TREE():
    """Can read and write FO4 tree"""
    # Trees in FO4 use a special root node and a special shape node.

    # ------- Load --------
    testfile = TTB.test_file(r"tests\FO4\meshes\TreeMaplePreWar01Orange.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_TREE.nif", output=True)

    # Read expected LOD sizes from the source NIF
    nif_in = pyn.NifFile(testfile)
    tree_shape = nif_in.shapes[0]
    lod0_size = tree_shape.properties.lodSize0
    lod1_size = tree_shape.properties.lodSize1
    lod2_size = tree_shape.properties.lodSize2

    bpy.ops.import_scene.pynifly(filepath=testfile)
    root = next(obj for obj in bpy.data.objects if 'pynRoot' in obj)
    assert root['pynBlockName'] == "BSLeafAnimNode", f"Have correct root type: {root['pynBlockName']}"

    tree = next(obj for obj in bpy.data.objects if obj.name.startswith("Tree") and obj.type == 'MESH')
    assert 'TREE_ANIM' in tree.active_material.pyn_shader.Shader_Flags_2, f"Have shader flags"
    assert tree['pynBlockName'] == "BSMeshLODTriShape", f"Have correct block type: {tree['pynBlockName']}"
    assert TT.is_eq(lod0_size, 1126, "Have correct LOD0 size")

    # LOD sizes not stored as custom properties — recovered from vertex groups
    assert 'lodSize0' not in tree, "lodSize not stored as custom property"

    # Check all 3 LOD vertex groups were created on import.
    lod_groups = [g.name for g in tree.vertex_groups if g.name in BD.LOD_GROUP_NAMES]
    assert TT.is_eq(sorted(lod_groups), ["LOD0", "LOD1", "LOD2"], "Have all 3 LOD vertex groups")

    # Check Mask modifier was added
    lod_mod = tree.modifiers.get("LOD")
    assert lod_mod is not None, "Have LOD mask modifier"
    assert TT.is_eq(lod_mod.type, 'MASK', "LOD modifier is a mask")

    # Verify LOD sizes sum to total face count
    total_lod = lod0_size + lod1_size + lod2_size
    assert TT.is_eq(total_lod, len(tree.data.polygons),
                     "LOD sizes sum to total face count")

    # ------- Export
    BD.ObjectSelect([tree, root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # ------- Check
    TTB.stage_materials_for(outfile)
    nifcheck = pyn.NifFile(outfile)
    assert nifcheck.rootNode.blockname == "BSLeafAnimNode", f"Have correct root node type"
    treecheck = nifcheck.shapes[0]
    assert treecheck.blockname == "BSMeshLODTriShape", f"Have correct shape node type"
    assert treecheck.shader.properties.shaderflags2_test(pyn.ShaderFlags2.TREE_ANIM), f"Tree animation set"
    assert TT.is_eq(treecheck.properties.vertexCount, 1059, "Have correct vertex count")
    assert TT.is_eq(treecheck.properties.lodSize0, lod0_size, "LOD0 size round-trips")
    assert TT.is_eq(treecheck.properties.lodSize1, lod1_size, "LOD1 size round-trips")
    assert TT.is_eq(treecheck.properties.lodSize2, lod2_size, "LOD2 size round-trips")

    # Verify LOD2 triangles reference the same vertices as in the source NIF.
    # LOD2 tris are the last lodSize2 entries in the triangle list.
    lod2_start = lod0_size + lod1_size
    src_lod2_vert_indices = set()
    for tri in tree_shape.tris[lod2_start:]:
        src_lod2_vert_indices.update(tri)
    src_lod2_verts = sorted(tuple(round(c, 3) for c in tree_shape.verts[vi])
                            for vi in src_lod2_vert_indices)

    exp_lod2_vert_indices = set()
    for tri in treecheck.tris[lod2_start:]:
        exp_lod2_vert_indices.update(tri)
    exp_lod2_verts = sorted(tuple(round(c, 3) for c in treecheck.verts[vi])
                            for vi in exp_lod2_vert_indices)

    assert TT.is_eq(exp_lod2_verts, src_lod2_verts,
                     "LOD2 triangles reference the same vertices after round-trip")


@TT.category('FO4', 'CONNECTPOINT')
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
    assert "C-Receiver" in cpchildren[0].pyn_connectpoint.child_names.split('\n'), \
        f"Did not find child name"

    # assert NT.NearEqual(cpcasing.rotation_quaternion.w, 0.9098), f"Have correct rotation: {cpcasing.rotation_quaternion}"
    assert cpcasing.parent.name == "CombatShotgunReceiver", f"Casing has correct parent {cpcasing.parent.name}"

    # Shapes remember their block type
    assert TT.is_eq(shotgun['pynBlockName'], 'BSTriShape', f"blockname")

    proj_node = TTB.find_shape("ProjectileNode", type="EMPTY")
    barrel_cp = TTB.find_shape("BSConnectPointParents::P-Barrel", type="EMPTY")
    assert TT.is_equiv(proj_node.matrix_world, barrel_cp.matrix_world, f"Projectile node and barrel cp transform")

    # -------- Export --------
    # Testing intuited defaults
    # Remove blockname so we can test the default is correct.
    del shotgun['pynBlockName']
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    ## --------- Check ----------
    nifsrc = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    pcheck = set(x.name.decode() for x in nifcheck.connect_points_parent)
    assert TT.is_samemembers(pcheck, parentnames, f"parent names")
    assert TT.is_eq(len(casingsrc_list := [cp for cp in nifsrc.connect_points_parent 
                                           if cp.name.decode()=="P-Casing"]),
                    1, f"Have one casing connect point in source")
    pcasingsrc = casingsrc_list[0]
    assert TT.is_eq(len(pcasing_list := [cp for cp in nifcheck.connect_points_parent 
                                         if cp.name.decode()=="P-Casing"]),
                    1, f"Have one casing connect point in check")
    pcasing = pcasing_list[0]
    assert TT.is_equiv(pcasing.rotation[:], pcasingsrc.rotation[:], f"P-Casing rotation")

    chnames = nifcheck.connect_points_child
    assert TT.is_samemembers(chnames, childnames, "child connect point names")

    sgcheck = nifcheck.shape_dict['CombatShotgunReceiver:0']
    assert TT.is_eq(sgcheck.blockname, 'BSTriShape', f"blockname")


@TT.category('FO4', 'CONNECTPOINT')
def TEST_CONNECT_POINT_MULT():
    """Regression: Blend file creates duplicate connect points."""

    testfile = TTB.test_file(r"tests\FO4\rifleCP.blend")
    outfile = TTB.test_file(r"tests\Out\TEST_CONNECT_POINT_MULT.nif")

    fp = os.path.join(TT.pynifly_dev_path, testfile)
    bpy.ops.wm.append(filepath=fp,
                      directory=fp + r"\Collection",
                      filename="RECEIVER",
                      use_recursive=True)

    # Export 

    chcp = bpy.data.objects['BSConnectPointChildren::C-Receiver']
    BD.ObjectSelect([chcp])
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    parentnames = ['P-Barrel', 'P-Casing', 'P-Grip', 'P-Grip2', 'P-Mag', 'P-Scope', 'P-Stock']
    childnames = ['C-Receiver']

    ## --------- Check ----------
    assert os.path.exists(outfile), f"Output file exists: {outfile}"
    nifcheck = pyn.NifFile(outfile)
    chnames = nifcheck.connect_points_child
    TT.assert_samemembers(chnames, childnames, "child connect point names")
    parnames = [p.name.decode() for p in nifcheck.connect_points_parent]
    TT.assert_samemembers(parnames, parentnames, "parent connect point names")
    return # TODO: Why is the rest of this commented out?

    pcheck = set(x.name.decode() for x in nifcheck.connect_points_parent)
    assert pcheck == parentnames, f"Wrote correct parent names: {pcheck}"
    pcasingsrc = [cp for cp in nifsrc.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    pcasing = [cp for cp in nifcheck.connect_points_parent if cp.name.decode()=="P-Casing"][0]
    assert NT.VNearEqual(pcasing.rotation[:], pcasingsrc.rotation[:]), f"Have correct rotation: {pcasing}"


    sgcheck = nifcheck.shape_dict['CombatShotgunReceiver:0']
    assert sgcheck.blockname == 'BSTriShape', f"Have correct blockname: {sgcheck.blockname}"


@TT.category('FO4', 'CONNECTPOINT')
def TEST_CONNECT_WEAPON_PART():
    """Selected connect points used to parent new import"""
    # When a connect point is selected and then another part is imported that connects
    # to that point, they are connected in Blender.
    
    testfile = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")
    partfile = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel_1.nif")
    partfile2 = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunGlowPinSight.nif")
    pretty = True

    # Import of mesh with parent connect points works correctly.
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False, 
                                 rename_bones=False, 
                                 create_collection=True)

    barrelpcp = TTB.assert_exists('BSConnectPointParents::P-Barrel')
    magpcp = TTB.assert_exists('BSConnectPointParents::P-Mag')
    scopepcp = TTB.assert_exists('BSConnectPointParents::P-Scope')

    # Import of child mesh connects correctly.
    BD.ObjectSelect([barrelpcp, magpcp, scopepcp], active=True)
    bpy.ops.import_scene.pynifly(filepath=partfile, 
                                 create_bones=False, 
                                 rename_bones=False, 
                                 create_collection=True)
    
    # Barrel is connected to receiver
    barrel = TTB.assert_exists('CombatShotgunBarrel:0')
    barrelccp = TTB.assert_exists('BSConnectPointChildren::C-Barrel')
    assert TT.is_eq(barrelccp.constraints['Copy Transforms'].target, barrelpcp, 
                    f"connection to parent")
    # Barrel physical location is correct in relation to receiver
    barrel_min_y = min((barrel.matrix_world @ v.co).y for v in barrel.data.vertices)
    barrel_max_y = max((barrel.matrix_world @ v.co).y for v in barrel.data.vertices)
    assert TT.is_equiv(barrel_min_y, barrelpcp.location.y+0.5, "Barrel location", e=0.5)
    assert TT.is_equiv(barrel_max_y-barrel_min_y, 21, "Barrel length", e=1.0)

    # Barrel collision follows the barrel, not left behind at the origin.
    # The barrel NIF has two meshes; the collision covers both, so compare
    # against combined bounds of all barrel meshes.
    barrel_meshes = [o for o in bpy.data.objects
                     if o.type == 'MESH' and o.name.startswith('CombatShotgunBarrel:')]
    all_barrel_ys = []
    for m in barrel_meshes:
        all_barrel_ys.extend((m.matrix_world @ v.co).y for v in m.data.vertices)
    all_min_y = min(all_barrel_ys)
    all_max_y = max(all_barrel_ys)

    # The barrel is in a constrained system (C-Barrel constrained to P-Barrel),
    # so the collision should be parented to C-Barrel and discovered via
    # custom property rather than a constraint.
    barrel_coll = TTB.find_object('bhkPhysicsSystem.001')
    assert TT.is_neq(barrel_coll, None, "Barrel collision exists")
    assert TT.is_eq(barrel_coll.parent, barrelccp,
                     "Barrel collision parented to child connect point")

    # Barrel root should have pynCollisionTarget instead of constraint
    barrel_root = TTB.find_object('CombatShotgunBarrel:ROOT')
    barrel_constrs = [c for c in barrel_root.constraints
                      if c.name == 'bhkCollisionConstraint']
    assert TT.is_eq(len(barrel_constrs), 0,
                     "No bhkCollisionConstraint in constrained system")
    assert TT.is_neq(barrel_root.get('pynCollisionTarget'), None,
                      "pynCollisionTarget property set")

    coll_min_y = min((barrel_coll.matrix_world @ v.co).y
                     for v in barrel_coll.data.vertices)
    coll_max_y = max((barrel_coll.matrix_world @ v.co).y
                     for v in barrel_coll.data.vertices)
    log.debug(f"Barrel meshes y=[{all_min_y:.2f}, {all_max_y:.2f}], "
              f"collision y=[{coll_min_y:.2f}, {coll_max_y:.2f}]")
    assert TT.is_lt(abs(coll_min_y - all_min_y), 5.0,
                     "Collision y-min near barrel meshes y-min")
    assert TT.is_lt(abs(coll_max_y - all_max_y), 5.0,
                     "Collision y-max near barrel meshes y-max")

    BD.ObjectSelect([barrelpcp, magpcp, scopepcp], active=True)
    bpy.ops.import_scene.pynifly(filepath=partfile2, 
                                 create_bones=False, 
                                 rename_bones=False, 
                                 create_collection=True)
    
    scopeccp = TTB.find_object('BSConnectPointChildren::C-Scope')
    assert TT.is_neq(scopeccp, None, "Scope child connect point found")
    assert TT.is_eq(scopeccp.constraints['Copy Transforms'].target, scopepcp,
                     "Scope child CP connected to parent CP")

    # Sight collision covers the FrontSight005:0 mesh
    frontsight = TTB.find_object('FrontSight005:0')
    assert TT.is_neq(frontsight, None, "FrontSight005:0 mesh exists")
    sight_colls = [o for o in bpy.data.objects
                   if o.name.startswith('bhkPhysicsSystem')
                   and o.get('pynCollisionShapeType')
                   and o.parent == scopeccp]
    assert TT.is_gt(len(sight_colls), 0, "Sight has collision under scope CP")
    sight_coll = sight_colls[0]

    _, _, fs_min_y, fs_max_y, _, _ = TTB.world_bounds(frontsight)
    _, _, sc_min_y, sc_max_y, _, _ = TTB.world_bounds(sight_coll)
    log.debug(f"FrontSight005 y=[{fs_min_y:.2f}, {fs_max_y:.2f}], "
              f"sight collision y=[{sc_min_y:.2f}, {sc_max_y:.2f}], "
              f"shape_type={sight_coll.get('pynCollisionShapeType')}, "
              f"parent={sight_coll.parent}, "
              f"matrix_world={sight_coll.matrix_world}")
    assert TT.is_lt(abs(sc_min_y - fs_min_y), 5.0,
                     "Sight collision y-min near FrontSight005 y-min")
    assert TT.is_lt(abs(sc_max_y - fs_max_y), 5.0,
                     "Sight collision y-max near FrontSight005 y-max")


@TT.category('FO4', 'CONNECTPOINT')
def TEST_CONNECT_IMPORT_MULT():
    """When multiple weapon parts are imported in one command, they are connected up"""

    testfiles = [{"name": TTB.test_file(r"tests\FO4\Shotgun\CombatShotgun.nif")}, 
                 {"name": TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel.nif")}, 
                 {"name": TTB.test_file(r"tests\FO4\Shotgun\Stock.nif")} ]
    bpy.ops.import_scene.pynifly(files=testfiles, rename_bones=False, create_bones=False)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH'
              and obj.get("pynRigidBody", "") != 'bhkPhysicsSystem']
    assert len(meshes) == 5, f"Have 5 meshes: {meshes}"
    barrelparent = [obj for obj in bpy.data.objects if obj.name == 'BSConnectPointParents::P-Barrel']
    assert len(barrelparent) == 1, f"Have barrel parent connect point {barrelparent}"
    barrelchild = [obj for obj in bpy.data.objects \
                if obj.name.startswith('BSConnectPointChildren')
                        and 'C-Barrel' in obj.pyn_connectpoint.child_names.split('\n')]
    assert len(barrelchild) == 1, f"Have a single barrel child {barrelchild}"
    

@TT.category('FO4', 'CONNECTPOINT')
def TEST_CONNECT_WORKSHOP():
    """Test meshes with many connect points, some with the same names."""

    testfile = TTB.test_file(r"tests\FO4\ShackPrefabMid01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_CONNECT_WORKSHOP.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False, 
                                 create_bones=False, smart_editor_markers=False)

    ### Read ###
    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects 
                      if obj.name.startswith('BSConnectPointParents')]), 17), \
        "Number of connect points"
    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects 
                      if obj.name.startswith('BSConnectPointParents::P-Floor')]), 4), \
        "Number of floor connect points"
    
    ### Write ###
    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj], active=True)    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    ### Check ###
    nif = pyn.NifFile(outfile)
    assert TT.is_eq(len(nif.connect_points_parent), 17), "Number of connect points"
    ccp_names = [c.name.decode('utf-8') for c in nif.connect_points_parent]
    assert TT.is_eq(len([c for c in ccp_names if c == 'P-Floor']), 4), "Number of floor connect points"
    assert TT.is_eq(len([c for c in ccp_names if c == 'P-WS-Origin']), 1), "Number of origin connect points"
    

@TT.category('FO4', 'CONNECTPOINT')
def TEST_CONNECT_WORKSHOP2():
    """Connect point editor markers have smart handling."""

    testfile = TTB.test_file(r"tests\FO4\ShackPrefabMid01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_CONNECT_WORKSHOP2.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, 
        rename_bones=False, create_bones=False, smart_editor_markers=True)

    print('### Read ###')
    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects 
                        if obj.name.startswith('BSConnectPointParents')]), 
                    17, 
                    "Number of connect points")
    # smart_edit_markers uses the editor marker shape for connect points.
    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects 
                        if obj.name.startswith('EditorMarker')]), 
                    0, 
                    "Number of editor markers")
    
    print('### Write ###')
    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj], active=True)    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    print('### Check ###')
    nif = pyn.NifFile(outfile)

    # Have connect points
    assert TT.is_eq(len(nif.connect_points_parent), 17, "connect point count")

    # Have editor markers created on export
    emarkers = [n for id, n in nif.node_ids.items() if n.name.startswith("EditorMarker")]
    assert TT.is_eq(len(emarkers), 16), "editor marker count"
    ccp_names = [c.name.decode('utf-8') for c in nif.connect_points_parent]
    assert TT.is_eq(len([c for c in ccp_names if c == 'P-Floor']), 4), \
                     "Number of floor connect points"
    assert TT.is_eq(len([c for c in ccp_names if c == 'P-WS-Origin']), 1), \
                     "Number of origin connect points"
    
    # Editor markers are distributed reasonably
    assert TT.is_eq(len([em for em in emarkers if em.transform.translation[0] > 0.5]), 6, "X location")
    assert TT.is_eq(len([em for em in emarkers if em.transform.translation[1] > 0.5]), 6, "Y location")
    assert TT.is_eq(len([em for em in emarkers if em.transform.translation[2] > 0.5]), 4, "Z location")
    assert TT.is_eq(len([em for em in emarkers 
                            if BD.NearEqual(em.transform.translation[0], 0.0, epsilon=0.5)
                                and BD.NearEqual(em.transform.translation[1], 0.0, epsilon=0.5)]),
                    0, "Origin location")


@TT.category('SKYRIMSE', 'FURNITURE')
def TEST_FARMBENCH():
    """Furniture markers work"""

    testfile = TTB.test_file(r"tests\SkyrimSE\farmbench01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_FARMBENCH.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert TT.is_eq(len(fmarkers), 2, f"furniture marker count in import")

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
    fmcheck = nifcheck.root.get_extra_data(blockname='BSFurnitureMarkerNode')
    assert fmcheck, "BSFurnitureMarkerNode exists"
    assert TT.is_eq(fmcheck.position_count, 2, f"furniture marker position count")
    assert TT.is_eq(len(fmcheck.furniture_markers), 2, f"furniture marker list length")


@TT.category('SKYRIMSE', 'FURNITURE')
def TEST_COMMONCHAIR():
    """Furniture markers work"""

    testfile = TTB.test_file(r"tests\SkyrimSE\commonchair01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_COMMONCHAIR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert TT.is_eq(len(fmarkers), 1, f"Found furniture markers: {fmarkers}")
    assert TT.is_equiv(fmarkers[0].rotation_euler, (-math.pi/2, 0, 0)), f"Marker points the right direction"

    # -------- Export --------
    bpy.ops.object.select_all(action='DESELECT')
    TTB.find_shape("CommonChair01:0").select_set(True)
    TTB.find_shape("BSXFlags", type='EMPTY').select_set(True)
    TTB.find_shape("BSFurnitureMarkerNode", type='EMPTY').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # --------- Check ----------
    nifcheck = pyn.NifFile(outfile)
    fmcheck = nifcheck.root.get_extra_data(blockname='BSFurnitureMarkerNode')
    assert fmcheck, "BSFurnitureMarkerNode exists"
    assert TT.is_eq(fmcheck.position_count, 1, f"furniture marker position count")
    assert TT.is_eq(len(fmcheck.furniture_markers), 1, f"furniture marker list length")
    assert TT.is_eq(fmcheck.furniture_markers[0].entry_points, 13, f"Entry point data is correct")


@TT.category('FO4', 'FURNITURE')
def TEST_FO4_CHAIR():
    """Furniture markers are imported and exported"""

    testfile = TTB.test_file(r"tests\FO4\FederalistChairOffice01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_FO4_CHAIR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
    
    assert TT.is_eq(len(fmarkers), 4, f"Found furniture markers: {fmarkers}")
    # Lowest points forward off the seat
    seatmarker = [m for m in fmarkers if BD.NearEqual(m.location.z, 34, epsilon=1)]
    assert TT.is_eq(len(seatmarker), 1, f"Have one marker on the seat")
    mk = seatmarker[0]
    assert TT.is_equiv(mk.rotation_euler, (-math.pi/2, 0, 0)), \
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
    TTB.stage_materials_for(outfile)
    nifcheck = pyn.NifFile(outfile)
    fmcheck = nifcheck.root.get_extra_data(blockname='BSFurnitureMarkerNode')
    assert fmcheck, "BSFurnitureMarkerNode exists"
    assert TT.is_eq(fmcheck.position_count, 4, f"furniture marker position count")
    assert TT.is_eq(len(fmcheck.furniture_markers), 4, f"furniture marker list length")
    assert TT.is_eq(fmcheck.furniture_markers[0].entry_points, 0, f"Entry point data is correct")
        

@TT.category('FO4', 'EXTRA_DATA')
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


@TT.category('FO4')
def TEST_DUP_NAMES():
    """Nifs with duplicate names import correctly."""
    testfile = TTB.test_file(r"tests\FO4\Meshes\TerminalOn.nif")
    outfile = TTB.test_file(r"tests\out\TEST_DUP_NAMES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects if obj.get('pynRoot', False)]),
                    1, "Root object count")
    assert TT.is_eq(bpy.context.scene.objects['TerminalOn'].parent.name,
                    'TerminalOn:ROOT', "Parent name")
    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects 
                         if obj.name.startswith('ScreenType:0')]),
                    2, "ScreenType:0 count")
    assert TT.is_eq(len([obj for obj in bpy.context.scene.objects if obj.type == 'MESH'
                         and obj.get('pynRigidBody', '') != 'bhkPhysicsSystem']),
                    7, "Mesh count")
    assert TT.is_eq(len(bpy.context.scene.objects['TerminalOn'].children), 3, 
                    "TerminaOn child count")


@TT.category('FO4', 'IMPORT', 'PARTITIONS')
@TT.expect_errors(("Could not find materials file",))
def TEST_IMPORT_DUPLICATE_TRIS_PARTITIONS():
    """Partitions stay on the right faces when duplicate triangles are dropped.

    partition_tris is 1:1 with the *source* triangles, so every dropped duplicate
    slides the assignments after it by one unless import maps faces back through
    tri_map. LBoot's L_Boot has 284 duplicates among 1786 triangles.

    Caveat: this locks in the behaviour but doesn't currently discriminate --
    in every fixture we have, the duplicates sit inside a single partition run,
    so the shift happens to land on the same partition value. Checked with
    scratchpad/partshift.py; no vanilla asset in tests/tests exercises it."""
    testfile = TTB.test_file(r"tests\FO4\LBoot.nif")

    shape = [s for s in pyn.NifFile(testfile).shapes if s.name == "L_Boot"][0]
    tris = shape.tris
    part_tris = shape.partition_tris
    dups = len(tris) - len(set(frozenset(t) for t in tris))
    assert TT.is_gt(dups, 0, f"fixture really has duplicate tris ({dups})")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = TTB.find_object("L_Boot")
    mesh = obj.data

    # Rebuild the expected assignment straight from the nif: walk the source
    # triangles in order, skipping duplicates exactly as import does, and check
    # each surviving one landed in the vertex group its source partition names.
    # partition_tris indexes the flattened partition list the importer builds:
    # each partition followed by its subsegments (FO4 dismemberment).
    partition_names = []
    for p in shape.partitions:
        partition_names.append(p.name)
        for sseg in getattr(p, "subsegments", ()):
            partition_names.append(sseg.name)
    groups = {vg.index: vg.name for vg in obj.vertex_groups}
    seen = set()
    expected = []
    for i, t in enumerate(tris):
        key = frozenset(t)
        if key in seen:
            continue
        seen.add(key)
        expected.append(partition_names[part_tris[i]])
    assert TT.is_eq(len(expected), len(mesh.polygons),
                    "one expected partition per imported face")

    wrong = 0
    for face, want in zip(mesh.polygons, expected):
        vi = mesh.loops[face.loop_start].vertex_index
        names = {groups[g.group] for g in mesh.vertices[vi].groups}
        if want not in names:
            wrong += 1
    assert TT.is_eq(wrong, 0,
                    f"every face is in its source partition ({wrong} of "
                    f"{len(mesh.polygons)} misassigned)")
