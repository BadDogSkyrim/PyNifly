"""Transforms, scaling and geometry tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('FO4', 'XFORM')
def TEST_FO4_SKINNED_UNDER_NODE():
    """A skinned shape parented to a non-identity node is placed correctly.

    An FO4 skinned shape's verts are placed entirely by the armature: its bones
    carry the nif's bind position as their rest and the nif's node position as
    their pose, so the armature modifier maps the verts from skin space to
    world. The shape stays parented to its nif parent node, so that node's
    transform must not also land on the object -- that applies it twice.

    In the vanilla armor workbench the bench is skinned under the
    'WorkstationArmor' node, which sits at (27.85, 36.81, 0). Every bone's
    pose-to-rest delta is exactly that offset, and the object was picking it up
    from the parent as well, sliding the bench off its collision.

    NOTE: this checks the EVALUATED mesh. The armature is a modifier, so raw
    vertex coordinates (what edit mode shows) do NOT reflect where the shape
    actually lands -- reading `v.co` here hides the bug completely.
    """
    testfile = TTB.test_file(r"tests\FO4\WorkstationArmorB01.nif")

    # Animation import is irrelevant here and warns about this nif's keyframes.
    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=False)

    depsgraph = bpy.context.evaluated_depsgraph_get()

    def evaluated_pts(obj):
        """World-space verts AFTER modifiers (i.e. after the armature deforms)."""
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        pts = [obj_eval.matrix_world @ v.co for v in mesh.vertices]
        obj_eval.to_mesh_clear()
        return pts

    top = bpy.data.objects['WorkstationArmor:0']
    assert top.find_armature() is not None, "bench top is skinned"
    assert top.parent and TT.is_equiv(
        list(top.parent.matrix_world.translation), [27.85, 36.81, 0.0],
        "bench top's parent node carries the offset", e=0.01)

    pts = evaluated_pts(top)
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    assert TT.is_equiv([min(xs), max(xs)], [-71.52, 96.10],
                       "bench top x bounds where the armature puts it", e=0.5)
    assert TT.is_equiv([min(ys), max(ys)], [-33.00, 62.42],
                       "bench top y bounds where the armature puts it", e=0.5)

    # Scene-level invariant: the collision is built to cover the bench, so the
    # far corner of all the collision shapes together should land near the far
    # corner of all the meshes together. This catches a shape sliding off its
    # collision without relying on any one shape's expected coordinates.
    # The meshes do legitimately overhang a little (the gear sticks out ~7 past
    # any collision), so allow some slop -- the doubled-offset bug puts these
    # 32 (x) and 37 (y) apart, well outside it.
    mesh_pts, coll_pts = [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not len(o.data.vertices): continue
        if o.name.startswith('bhk'):
            coll_pts.extend(evaluated_pts(o))
        else:
            mesh_pts.extend(evaluated_pts(o))

    assert TT.is_lt(abs(max(p.x for p in mesh_pts) - max(p.x for p in coll_pts)), 10,
                    "max X of all meshes is near max X of all collisions")
    assert TT.is_lt(abs(max(p.y for p in mesh_pts) - max(p.y for p in coll_pts)), 10,
                    "max Y of all meshes is near max Y of all collisions")

    # Export and check the skin frame. A shape skinned under the non-identity
    # 'WorkstationArmor' node must fold that node's offset into global-to-skin, or
    # the skinned placement diverges from the unskinned one (NifSkope/the engine
    # render the shape offset when skinning is on). The node sits at ~(27.85, 36.81),
    # so global-to-skin is its negation -- matching vanilla.
    outfile = TTB.test_file(r"tests\Out\TEST_FO4_SKINNED_UNDER_NODE.nif")
    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    try:
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    except RuntimeError as e:
        assert "unweighted vertices" in str(e), f"unexpected export error: {e}"

    src = pyn.NifFile(testfile)
    dst = pyn.NifFile(outfile)
    for sn in ('WorkstationArmor:0', 'WorkstationArmor:1'):
        vg2s = [s for s in src.shapes if s.name == sn][0].global_to_skin
        eg2s = [s for s in dst.shapes if s.name == sn][0].global_to_skin
        assert TT.is_equiv(list(eg2s.translation), list(vg2s.translation),
                           f"{sn} exported global-to-skin matches vanilla", e=0.1)


@TT.category('FO4', 'XFORM')
def TEST_FO4_UNSKINNED_SHAPES_STAY_UNSKINNED():
    """Static shapes sharing a nif with a skinned shape don't get a skin instance.

    The exporter hands the file's armature to every shape, so a shape with no
    vertex groups naming armature bones used to be written with a skin instance
    holding zero bones (and every vertex reported unweighted). The game follows
    that empty skin instance to a null pointer and crashes in
    BSSkin::Instance::UpdateModelBound -- confirmed in game on this nif, on
    'm_Refraction:0'.

    The vanilla armor workbench is the case: a skinned bench plus 15 static
    shapes (fire, dirt, wood, gears, refraction) in one nif.
    """
    testfile = TTB.test_file(r"tests\FO4\WorkstationArmorB01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_FO4_UNSKINNED_SHAPES.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=False)
    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    src = pyn.NifFile(testfile)
    dst = pyn.NifFile(outfile)
    exported = {s.name: s for s in dst.shapes}

    for s in src.shapes:
        e = exported.get(s.name)
        assert e, f"{s.name} was exported"
        assert TT.is_eq(bool(e.has_skin_instance), bool(s.has_skin_instance),
                        f"{s.name} skinned-ness matches vanilla")
        if e.has_skin_instance:
            # A skin instance with no bones is the null the game dies on.
            assert TT.is_gt(len(e.get_used_bones()), 0,
                            f"{s.name} skin instance has bones")


@TT.category('SKYRIM', 'SCALING')
def TEST_SCALING():
    """Test that scale factors happen correctly"""

    testfile = TTB.test_file(r"tests\Skyrim\Meshes\statuechampion.nif")
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


@TT.category('SKYRIM', 'SCALING')
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


@TT.category('SKYRIM', 'SCALING')
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
    assert NT.NearEqual(shapecheck.transform.scale, 1.0), \
        f"Nonuniform scale exported in verts so scale is 1: {shapecheck.transform.scale}"
    for v in shapecheck.verts:
        assert not NT.VNearEqual(map(abs, v), [1,1,1]), f"All vertices scaled away from unit position: {v}"


@TT.category('SKYRIMSE', 'INVENTORY_MARKER')
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
    assert TT.is_equiv(mx, mx_face, e=0.1), f"Inventory matrix is 180 around z: {mx.to_euler()}"

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
    inv_marker = nifch1.rootNode.get_extra_data(blockname='BSInvMarker', name='INV')
    assert TT.is_eq(inv_marker.rotation, (0, 0, 0), f"Have correct inventory marker: {inv_marker.rotation}")

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
    inv_marker2 = nifch2.rootNode.get_extra_data(blockname='BSInvMarker', name='INV')
    assert TT.is_equiv(inv_marker2.rotation, (0, 0, 3142), e=2), \
        f"Have correct inventory marker: {inv_marker2.rotation}"

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
    inv_marker3 = nifch3.rootNode.get_extra_data(blockname='BSInvMarker', name='INV')
    assert TT.is_equiv(inv_marker3.rotation, (0, 0, 1570), e=2), \
        f"Have correct inventory marker: {inv_marker3.rotation}"

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
    assert TT.is_equiv(im.matrix_world, BD.CAMERA_NEUTRAL), f"Inventory matrix neutral: {im.matrix_world.to_euler()}"

    # Second test had the camera at the front of Suzanne's head.
    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=outfile2)
    im = next(obj for obj in bpy.data.objects if obj.type=='CAMERA')
    assert TT.is_equiv(im.matrix_world, 
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
    assert TT.is_equiv(im.matrix_world, 
        Matrix((
            ( 0.0002, -0.0000, -1.0000, -100.0000),
            (-1.0000,  0.0000, -0.0002,   -0.0204),
            ( 0.0000,  1.0000, -0.0000,    0.0000),
            ( 0.0000,  0.0000,  0.0000,    1.0000) ))
            ), f"Inventory matrix neutral: {im.matrix_world.to_euler()}"


@TT.category('SKYRIM', 'TREE')
def TEST_TREE_SKINNED_BONES():
    """Skinned tree imports one vertex group per unique bone (no .001 duplicates).

    treeaspen03.nif's skinned shapes store a partition-palette-aligned bone list
    (each bone repeated once per SkinPartition). The importer must collapse
    those repeats to a single vertex group per bone, with weights aggregated.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    BONES = {"TrunkBone", "BranchBoughBone01", "BranchBone01",
             "BranchBoughBone02", "BranchBone02"}

    skinned = [o for o in bpy.data.objects
               if o.type == 'MESH' and any(vg.name == "TrunkBone" for vg in o.vertex_groups)]
    assert len(skinned) >= 1, "Found at least one skinned tree mesh"

    for mesh in skinned:
        names = [vg.name for vg in mesh.vertex_groups]
        dupes = [n for n in names if any(n.startswith(b + ".") for b in BONES)]
        assert not dupes, f"{mesh.name} has duplicate bone vgroups: {dupes}"
        bone_vgs = {n for n in names if n in BONES}
        assert bone_vgs == BONES, f"{mesh.name} has all 5 unique bones, no more: {sorted(bone_vgs)}"


@TT.category('SKYRIM', 'XFORM')
def TEST_ROTSTATIC():
    """Test that statics are transformed according to the shape transform"""
    testfile = TTB.test_file(r"tests/Skyrim/Meshes/rotatedbody.nif")
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


@TT.category('FO4', 'XFORM')
def TEST_ROTSTATIC2():
    """Test that statics are transformed according to the shape transform"""

    testfile = TTB.test_file(r"tests/FO4/Meshes/SetDressing/Vehicles/Crane03_simplified.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    glass = bpy.data.objects["Glass:0"]
    assert int(glass.location[0]) == -107, f"Locaation is incorret, got {glass.location[:]}"
    assert round(glass.matrix_world[0][1], 4) == -0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[0][1], 4)} != -0.9971"
    assert round(glass.matrix_world[2][2], 4) == 0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[2][2], 4)} != 59.2036"


@TT.category('SKYRIMSE', 'TREE')
def TEST_NISWITCHNODE_IMPORT():
    """NiSwitchNode switch flags survive import as custom props on the Empty.

    treeaspen03 has two nested NiSwitchNodes (outer flags=3, inner flags=1).
    They import as Empties carrying the switch flags, so export can recreate the
    block (export uses the generic pynBlockName -> getbuf(values=obj) path).
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    switches = [o for o in bpy.data.objects
                if o.get('pynBlockName') == 'NiSwitchNode']
    assert TT.is_eq(len(switches), 2, "Two NiSwitchNode empties imported")
    flags = sorted(s.pyn_switchnode.switchFlags for s in switches)
    assert TT.is_eq(flags, [1, 3], "Switch flags preserved on import")


@TT.category('SKYRIMSE', 'TREE')
def TEST_TREE_EXPORT():
    """Skinned tree exports without unweighted-vertex errors.

    The leaf-card shapes live under a NiSwitchNode's unskinned (LOD) branch and
    carry no bone weights. The exporter passes the file armature to every shape;
    these must export as static geometry rather than being skinned (which would
    report every vertex as unweighted and abort the export).
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_TREE_EXPORT.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    for o in bpy.data.objects:
        o.select_set(True)
    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    bpy.context.view_layer.objects.active = root
    # Raises if any shape reports unweighted vertices.
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifout = pyn.NifFile(outfile)
    skinned = [s for s in nifout.shapes if s.bone_names]
    unskinned = [s for s in nifout.shapes if not s.bone_names]
    assert TT.is_gt(len(skinned), 1, f"Skinned body shapes exported: {len(skinned)}")
    assert TT.is_gt(len(unskinned), 1, f"Static LOD shapes exported unskinned: {len(unskinned)}")


@TT.category('SKYRIMSE', 'TREE')
def TEST_BSMULTIBOUND_ROUNDTRIP():
    """BSMultiBoundNode OBB imports as a wire cube and round-trips on export.

    The OBB bounding box becomes a child cube whose local transform encodes
    center/rotation/half-extents; export rebuilds BSMultiBound -> BSMultiBoundOBB.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_BSMULTIBOUND.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    cube = next((o for o in bpy.data.objects if o.get('pynMultiBoundOBB')), None)
    assert cube is not None, "OBB cube created on import"
    assert cube.parent.get('pynBlockName') == 'BSMultiBoundNode', "cube parented to MBN"
    # dimensions = 2 x half-extents (size = 372.5, 433.43, 504.0)
    assert TT.is_equiv(tuple(cube.dimensions), (745.0, 866.87, 1008.0),
                        "OBB cube dimensions = 2x half-extents", e=1.0)

    for o in bpy.data.objects:
        o.select_set(True)
    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifout = pyn.NifFile(outfile)
    mbn = next(n for n in nifout.nodes.values() if n.blockname == 'BSMultiBoundNode')
    obb = mbn.multibound.data
    assert obb.blockname == 'BSMultiBoundOBB', "OBB block recreated"
    assert TT.is_equiv(tuple(obb.size), (372.5, 433.43, 504.0),
                        "OBB half-extents round-trip", e=0.5)


@TT.category('SKYRIMSE', 'TREE')
def TEST_BSTREENODE_ROUNDTRIP():
    """BSTreeNode Bones1/Bones2 pointer arrays survive import -> export.

    Bones1 is the armature root, Bones2 the remaining bones. They import as
    nif-name lists on the root Empty and export re-resolves them to nodes.
    """
    import json
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_BSTREENODE.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    assert root.get('pynBlockName') == 'BSTreeNode', "Root is a BSTreeNode"
    assert TT.is_eq(json.loads(root['pynBSTreeBones1']), ['TrunkBone'],
                     "Bones1 stored on import")

    for o in bpy.data.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifout = pyn.NifFile(outfile)
    tn = nifout.read_node(id=0)
    assert tn.blockname == 'BSTreeNode', f"Exported root is BSTreeNode: {tn.blockname}"
    assert TT.is_eq(tn.bones1, ['TrunkBone'], "Bones1 round-trips")
    assert TT.is_eq(len(tn.bones2), 4, f"Bones2 round-trips (4 bones): {tn.bones2}")


@TT.category('SKYRIMSE', 'TREE')
def TEST_VANILLA_TREEASPEN_ROUNDTRIP():
    """Full vanilla skinned tree: import -> export -> re-read, structurally intact.

    Integration of the whole skinned-tree effort: single armature, NiSwitchNode
    flags + skinned-first child ordering (invariant: child[1] is unskinned),
    BSMultiBound OBB, and BSTreeNode Bones1/Bones2.
    """
    from ctypes import c_int, create_string_buffer
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_VANILLA_TREEASPEN.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert TT.is_eq(len(armatures), 1, "Single armature for the whole tree")

    for o in bpy.data.objects:
        o.select_set(True)
    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nif = pyn.NifFile(outfile)
    h = nif._handle
    shape_skin = {sh.id: bool(sh.bone_names) for sh in nif.shapes}

    def blockname(nid):
        b = create_string_buffer(128); pyn.nifly.getBlockname(h, nid, b, 128)
        return b.value.decode('utf-8')

    def children(nid):
        buf = (c_int * 64)(); n = pyn.nifly.getNodeChildren(h, nid, 64, buf)
        return [buf[i] for i in range(n)]

    def subtree_skinned(nid):
        if nid in shape_skin:
            return shape_skin[nid]
        return any(subtree_skinned(c) for c in children(nid))

    switch_ids = []
    def collect(nid):
        if blockname(nid) == 'NiSwitchNode':
            switch_ids.append(nid)
        for c in children(nid):
            collect(c)
    collect(nif.rootNode.id)

    # Both NiSwitchNodes, flags preserved, invariant holds (child[1] unskinned).
    assert TT.is_eq(len(switch_ids), 2, "Both NiSwitchNodes exported")
    flags = sorted(nif.read_node(id=s).switch_flags for s in switch_ids)
    assert TT.is_eq(flags, [1, 3], "Switch flags preserved")
    for sid in switch_ids:
        ch = children(sid)
        assert TT.is_eq(len(ch), 2, f"Switch {sid} has exactly 2 children")
        assert subtree_skinned(ch[0]), f"Switch {sid} child[0] is the skinned branch"
        assert not subtree_skinned(ch[1]), f"Switch {sid} child[1] is unskinned (invariant)"

    # BSMultiBound OBB and BSTreeNode bones preserved.
    mbn = next(n for n in nif.nodes.values() if n.blockname == 'BSMultiBoundNode')
    assert mbn.multibound.data.blockname == 'BSMultiBoundOBB', "BSMultiBound OBB preserved"
    tn = nif.read_node(id=0)
    assert tn.blockname == 'BSTreeNode', "Root BSTreeNode preserved"
    assert TT.is_eq(tn.bones1, ['TrunkBone'], "BSTreeNode Bones1 preserved")
