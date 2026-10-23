"""Starfield tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('STARFIELD')
# The vanilla skeleton carries the Havok ragdoll rig, which we don't read. Nothing to do
# with bone units, and out of scope here.
@TT.expect_errors(('Unknown block type: bhkRagdollSystem',
                   'bhkPhysicsSystem decode failed'))
def TEST_SF_SKELETON_IMPORT():
    """Starfield's own skeleton.nif imports as one coherent armature, not two half-scales.

    It is the one vanilla file that carries bone NiNode transforms AND carries them in Havok
    metres; 348 of the 354 vanilla human nifs carry no positioned bone nodes at all. With
    'create bones' on, rest comes from our reference skeleton (game units) while pose comes
    from the file, so the two used to disagree by ~70x: rest looked right and every bone
    posed into a 1.7-unit ball at the origin.

    Positions are pinned against the reference skeleton in absolute terms -- a uniform
    rescale is invisible to a check that only compares the armature with itself.
    """
    testfile = os.path.join(
        TT.SF_ASSETS, r"meshes\actors\human\characterassets\skeleton.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    arma = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    assert TT.is_eq(len(arma.data.bones), 114, "bone count")

    # Pose sits on rest: an unposed skeleton must import with nothing displaced.
    off = [b.name for b in arma.data.bones
           if ((arma.matrix_world @ arma.pose.bones[b.name].head)
               - (arma.matrix_world @ b.head_local)).length > 0.01]
    assert TT.is_eq(len(off), 0, f"bones posed away from rest ({off[:4]})")

    # And in the right units -- the reference skeleton's, which is what the .mesh geometry
    # and skin binds of every other SF nif are in. In the file's own metres this is 1.63.
    head = arma.matrix_world @ arma.data.bones['Head.C'].head_local
    assert TT.is_equiv(head.z, 114.2446, "Head.C rests at game-unit height", e=0.01)


@TT.category('STARFIELD')
def TEST_SF_IMPORT_ONTO_EXISTING_ARMATURE():
    """Starfield: hands imported onto the body's selected armature line up with the body.

    Vanilla female body, hands and head share one skin space: every bone two of them have in
    common has an identical skin bind. But a Starfield nif carries no bone nodes, so import
    places each mesh by matching its binds against the reference skeleton -- and vanilla's
    binds disagree with the skeleton by up to 2 units and 7 degrees, so the answer depended on
    which bones the file uses. Imported onto the body's armature, the hands landed 3.6 degrees
    and 0.6 units away from the body, their wrists 1-3 units off. A Starfield mesh imported
    with an armature selected now takes its placement from that armature's bones.

    Only a selected armature is used: with nothing selected, the hands get their own armature
    as before.
    """
    body_file = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    hands_file = TTB.test_file(r"tests\SF\meshes\hands_3rd_f.nif")

    # CONTROL: nothing selected -> the hands make their own armature.
    bpy.ops.import_scene.pynifly(filepath=body_file)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None
    bpy.ops.import_scene.pynifly(filepath=hands_file)
    armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert TT.is_eq(len(armatures), 2, "with nothing selected, the hands get their own armature")
    TTB.clear_all()

    # The body's armature selected -> the hands join it, placed by its bones.
    bpy.ops.import_scene.pynifly(filepath=body_file)
    body = TTB.find_shape("Naked_F:0")
    arma = body.modifiers['Armature'].object
    rest_before = {b.name: (arma.matrix_world @ b.head_local).copy() for b in arma.data.bones}

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly(filepath=hands_file)
    hands = TTB.find_shape("Hands_3rd_F:0")

    armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert TT.is_eq(len(armatures), 1, "the hands joined the body's armature, no second one")
    assert hands.modifiers['Armature'].object is arma, "the hands are bound to the body's armature"

    # Same skin space, so the same placement -- to float precision, not approximately.
    assert TT.is_equiv(hands.matrix_world, body.matrix_world, "hands placed exactly like the body",
                       e=0.001)

    # The body's bones stay where they were; the hands only add their own.
    moved = [n for n, p in rest_before.items()
             if (arma.matrix_world @ arma.data.bones[n].head_local - p).length > 0.001]
    assert TT.is_eq(moved, [], "no existing bone moved")
    assert 'Wrist_Twist.R' in arma.data.bones or 'R_Wrist_Twist' in arma.data.bones, \
        "the shared wrist bone is there"


@TT.category('STARFIELD')
def TEST_SF_IMPORT_EYE_ONTO_HEAD_ARMATURE():
    """Starfield: an eye imported onto the head's selected armature sits in its socket.

    The eye binds only L_Eye, which the head doesn't use, so there's no shared bone to place
    it by. The reference skeleton's eye bone sits about 0.22 units further in than the eye's
    own bind, so placing the eye from the skeleton put it that far toward the centre of the
    face. Vanilla head parts share the head's skin space, so a mesh that shares no bones with
    the selected armature now takes the placement of the meshes already on it.
    """
    head_file = TTB.test_file(r"tests\SF\meshes\malehead.nif")
    eye_file = TTB.test_file(r"tests\SF\meshes\lefteye.nif")

    bpy.ops.import_scene.pynifly(filepath=head_file)
    head = TTB.find_shape("MaleHead:0")
    arma = head.modifiers['Armature'].object

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly(filepath=eye_file)
    eye = TTB.find_shape("LeftEye:1")

    assert eye.modifiers['Armature'].object is arma, "the eye is bound to the head's armature"
    assert TT.is_equiv(eye.matrix_world, head.matrix_world,
                       "the eye shares the head's placement, so it sits in its socket", e=0.001)


@TT.category('STARFIELD')
def TEST_SF_IMPORT():
    """Starfield: import a BSGeometry body, resolving + reading its external .mesh."""
    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TTB.find_shape("Naked_F:0")
    assert body is not None, "Imported the body mesh"

    # Starfield representation: a BSGeometry Empty (block container) parents one mesh child
    # per LOD. Single-LOD here, so one child named "<shape>:LOD0" under the container Empty,
    # which is flagged with the block-type naming convention "BSGeometry:<shape>".
    empty = bpy.data.objects.get("BSGeometry:Naked_F:0")
    assert empty is not None and empty.type == 'EMPTY', "BSGeometry container is an Empty"
    assert empty['pynBlockName'] == 'BSGeometry', "Empty carries the BSGeometry block name"
    assert body.name == "Naked_F:0:LOD0", f"Mesh child is the LOD0 child, got {body.name}"
    assert body.parent is empty, "Mesh child is parented to the BSGeometry Empty"
    # The Empty is identity relative to its parent -> the child's world transform is
    # unchanged by the wrap (verified by the upright/at-origin checks further down).
    assert empty.parent is not None and 'pynRoot' in empty.parent, \
        "BSGeometry Empty hangs off the NIF root"

    assert len(body.data.vertices) == 6616, f"Vertex count: {len(body.data.vertices)}"
    assert len(body.data.polygons) == 12132, f"Polygon count: {len(body.data.polygons)}"
    assert body.data.uv_layers, "Has a UV layer"
    # Per-vertex skin weights import as vertex groups (one per SkinAttach bone).
    assert len(body.vertex_groups) == 38, f"Bone vertex groups: {len(body.vertex_groups)}"
    assert body.active_material, "Has a material"

    # Bone names convert to Blender-friendly form via the SF dictionary: the L_/R_/C_
    # side prefix becomes a .L/.R/.C suffix (so Blender mirror/symmetry works).
    assert 'Thigh.L' in body.vertex_groups and 'L_Thigh' not in body.vertex_groups, \
        "Vertex groups use Blender .L naming"
    assert 'Chest.C' in body.vertex_groups, "Centre bones use .C naming"

    # The shape binds to a real armature, built from the BSSkinBoneData bind transforms
    # (read by index, since SF carries no NiNode boneRefs).
    arma_mod = next((m for m in body.modifiers if m.type == 'ARMATURE'), None)
    assert arma_mod and arma_mod.object, "Body is bound to an armature"
    arma = arma_mod.object
    assert 'Thigh.L' in arma.data.bones and 'Hips.C' in arma.data.bones, "Bones renamed"

    # Connected skeleton: the SF reference skeleton supplies the hierarchy (and the
    # connecting bones above the weighted set), so there is a single root and every
    # other bone is parented — not a flat pile of unconnected weighted bones.
    roots = [b for b in arma.data.bones if b.parent is None]
    assert len(roots) == 1, f"Single root bone, got {[b.name for b in roots]}"
    assert len(arma.data.bones) >= 38, f"At least the weighted bones: {len(arma.data.bones)}"

    # Bones must land in game-unit space (not 1/70th metric): the DLL scales the raw
    # (metric) bind translation by havokScale, and the bundled SF reference skeleton is
    # pre-scaled to match. A body-sized armature spans ~100 units, far above metric scale.
    heads = [arma.matrix_world @ b.head_local for b in arma.data.bones]
    extent = max(max(h[i] for h in heads) - min(h[i] for h in heads) for i in range(3))
    assert extent > 30, f"Bones span game-unit distances (extent {extent:.1f}), not metric/collapsed"

    # The skin->world transform (recovered from the reference skeleton, since SF has no
    # bone NiNodes) puts the mesh + its weighted bones into skeleton space: the body
    # stands upright (Z is the tall axis) and NO bone sits below the origin -- the
    # weighted bones land at the same skeleton positions as the connecting bones, not in
    # the raw, head-at-origin skin space.
    assert min(h.z for h in heads) > -5, \
        f"No bones below the origin (min Z {min(h.z for h in heads):.1f})"
    wv = [body.matrix_world @ v.co for v in body.data.vertices]
    span = [max(v[i] for v in wv) - min(v[i] for v in wv) for i in range(3)]
    assert span[2] > span[0] and span[2] > span[1], \
        f"Body stands upright (Z is the tall axis): spans {[round(s) for s in span]}"
    assert min(v.z for v in wv) > -5, \
        f"Body sits at/above the origin (min Z {min(v.z for v in wv):.1f})"

    # The external .mesh path / LOD slot / internal flag are recorded on the object for
    # round-trip (they can't be recovered from the Blender mesh). Stored verbatim (the raw
    # meshName: no 'geometries\' root, no '.mesh' extension) for byte-exact write-back.
    sfg = body.pyn_sf_geometry
    assert sfg.mesh_path and 'geometries' not in sfg.mesh_path.lower() \
        and not sfg.mesh_path.lower().endswith('.mesh'), \
        f"Verbatim external .mesh path recorded: {sfg.mesh_path!r}"
    assert sfg.mesh_path == body.pyn_sf_geometry.mesh_path  # sanity: same group
    assert sfg.lod_slot == 0, f"LOD slot 0 recorded, got {sfg.lod_slot}"
    assert sfg.is_internal is False, "External geometry (not internal 0x200) recorded"
    # Source per-vertex influence count recorded (this body uses 6, > the Skyrim/FO4 cap of 4).
    assert sfg.weights_per_vertex == 6, \
        f"Source weightsPerVertex recorded: {sfg.weights_per_vertex}"


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_EXPORT_DEFAULT_FLAGS():
    """A BSGeometry made from a plain Blender mesh gets flags 14, what vanilla uses.

    Across 2,548 vanilla shapes only two flag values exist: 14 for a shape with an external
    .mesh, and 526 (14 | SAVE_EXT_GEOM_DATA) for embedded geometry. Export always writes an
    external .mesh, so 14 is right. Flags come from pynNodeFlags, which only an imported shape
    has, so a mesh the user modelled used to get whatever the block defaulted to. Explicit
    pynNodeFlags still win."""
    outfile = TTB.test_file(r"tests\Out\TEST_SF_EXPORT_DEFAULT_FLAGS\meshes\cubes.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    bpy.ops.mesh.primitive_cube_add()
    plain = bpy.context.object
    plain.name = "PlainCube"
    bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
    flagged = bpy.context.object
    flagged.name = "FlaggedCube"
    flagged['pynNodeFlags'] = NiAVFlags(NiAVFlags.HIDDEN | NiAVFlags.SELECTIVE_UPDATE).fullname

    # intuit_defaults=False, as the export dialog does: otherwise the game is guessed from the
    # objects, and plain cubes say Skyrim.
    BD.ObjectSelect([plain, flagged], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", intuit_defaults=False)

    shapes = {s.name: s for s in pyn.NifFile(outfile).shapes}
    assert TT.is_eq(set(shapes), {"PlainCube", "FlaggedCube"}, "Both cubes exported")
    assert all(s.blockname == 'BSGeometry' for s in shapes.values()), "Exported as Starfield"
    assert TT.is_eq(shapes["PlainCube"].flags, 14, "Modelled mesh gets vanilla BSGeometry flags")
    assert TT.is_eq(shapes["FlaggedCube"].flags,
                    NiAVFlags.HIDDEN | NiAVFlags.SELECTIVE_UPDATE, "Explicit pynNodeFlags kept")


@TT.category('STARFIELD', 'GEOMETRY')
@TT.expect_errors(("Could not find material",))  # the .mat lives in the mod's BA2, not loose
def TEST_SF_INTERNAL_GEOMETRY():
    """A shape with internal (embedded) geometry imports without an external .mesh.

    Starfield BSGeometry normally points at an external .mesh, but flag 0x200 means the mesh
    data is embedded in the nif and meshName is empty. Vanilla never ships these; mod-authored
    heads do (this fixture is Felid's). load_geometry used to run the resolver anyway and warn
    "Could not find external .mesh for 'X': ''" on a file whose geometry had read fine.

    Also covers the extra-data walk: this shape's MaterialID must survive to Blender.
    """
    testfile = TTB.test_file(r"tests\SF\meshes\felidmalehead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = next(o for o in bpy.data.objects if o.type == 'MESH')
    assert TT.is_eq(len(head.data.vertices), 9773, "Embedded geometry imported")

    matid = bpy.data.objects.get('NiIntegerExtraData:MaterialID')
    assert matid, "MaterialID extra data imported"
    assert TT.is_eq(matid.parent.name, head.name, "MaterialID parented to the shape")
    g = matid.pyn_niintdata
    assert TT.is_eq(g.name, 'MaterialID', "Extra data name")
    assert TT.is_eq(g.value, '3297623742', "MaterialID value (uint32, kept as a string)")


@TT.category('STARFIELD', 'GEOMETRY', 'SHADER')
def TEST_SF_EXTRA_DATA_ROUNDTRIP():
    """Starfield MaterialID round-trips onto the shape, and no texture set is invented.

    Every Starfield character shape carries NiIntegerExtraData 'MaterialID' -- a CRC of the
    material path -- on the BSGeometry itself. It used to export as a bare NiNode named
    'NiIntegerExtraData:MaterialID' (no classifier branch, so the Empty fell through to the
    generic node path and export_integer_data never saw it), losing the block entirely.

    Starfield also has no NIF texture set; the exporter used to walk the Principled graph and
    write a BSShaderTextureSet no vanilla SF nif has.
    """
    testfile = TTB.test_file(r"tests\SF\meshes\malehead.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SF_EXTRA_DATA_ROUNDTRIP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_collection=True)
    head = next(o for o in bpy.data.objects if o.type == 'MESH')

    matid = bpy.data.objects.get('NiIntegerExtraData:MaterialID')
    assert matid, "MaterialID imported"
    assert TT.is_eq(matid.pyn_niintdata.value, '1388984028', "Imported MaterialID value")

    BD.ObjectSelect([o for o in bpy.data.objects], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF')

    nifcheck = pyn.NifFile(outfile)
    shape = nifcheck.shapes[0]
    eddict = dict((ed.name, ed) for ed in shape.extra_data())
    assert 'MaterialID' in eddict, "MaterialID written on the SHAPE, not the root"
    assert TT.is_eq(eddict['MaterialID'].integer_data, 1388984028, "Exported MaterialID value")

    rootnames = [n.name for n in nifcheck.nodes.values()]
    assert 'NiIntegerExtraData:MaterialID' not in rootnames, \
        "Extra data is not exported as a stray NiNode"

    # Starfield's textures come from the .mat, and no vanilla SF nif carries a texture set.
    assert TT.is_eq(shape.shader.properties.textureSetID, pyn.NODEID_NONE,
                    "No BSShaderTextureSet written for Starfield")
    with open(outfile, 'rb') as f:
        assert b'BSShaderTextureSet' not in f.read(2048), \
            "BSShaderTextureSet absent from the block-type table"


@TT.category('STARFIELD', 'GEOMETRY', 'SHADER')
def TEST_SF_MATERIAL_ID_GENERATED():
    """A Starfield shape with no imported MaterialID gets one generated from its material path.

    MaterialID is a CRC of the shader's material path, and every vanilla shape carries one --
    but a head authored in Blender has no extra-data Empty to write back. Deleting the imported
    Empty here stands in for that: export must still put the right MaterialID on the shape.
    """
    testfile = TTB.test_file(r"tests\SF\meshes\malehead.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MATERIAL_ID_GENERATED.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    matid = bpy.data.objects['NiIntegerExtraData:MaterialID']
    bpy.data.objects.remove(matid, do_unlink=True)
    assert 'NiIntegerExtraData:MaterialID' not in bpy.data.objects, "Imported MaterialID removed"

    BD.ObjectSelect([o for o in bpy.data.objects], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF')

    shape = pyn.NifFile(outfile).shapes[0]
    eddict = dict((ed.name, ed) for ed in shape.extra_data())
    assert 'MaterialID' in eddict, "MaterialID generated for a shape that had none"
    # CRC of 'Materials\Actors\Human\Faces\male_default.mat' -- what vanilla malehead.nif holds.
    assert TT.is_eq(eddict['MaterialID'].integer_data, 1388984028, "Generated MaterialID value")
    assert TT.is_eq(len([e for e in shape.extra_data() if e.name == 'MaterialID']), 1,
                    "Exactly one MaterialID block")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MATERIAL():
    """Starfield: import the layered .mat as a native Principled-BSDF PBR material.

    SF carries no NIF texture set -- the shader Name points at a loose .mat listing one
    texture per PBR property. We resolve + parse it, wire each map to the matching Principled
    input (normal Z reconstructed from BC5 XY), and stash the raw slot paths for round-trip.
    """
    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TTB.find_shape("Naked_F:0")  # the LOD0 mesh child
    mat = body.active_material
    assert mat, "Body has a material"

    # Raw .mat slot paths are stashed for round-trip + the panel (Data\ prefix stripped).
    assert mat['BSShaderTextureSet_Albedo'] == r"Textures\SF\test\body_color.dds", \
        f"Albedo path stashed: {mat.get('BSShaderTextureSet_Albedo')}"
    assert mat['BSShaderTextureSet_Normal'] == r"Textures\SF\test\body_normal.dds", \
        f"Normal path stashed: {mat.get('BSShaderTextureSet_Normal')}"
    # The material's own .mat path is kept for export round-trip.
    assert mat['BSLSP_Shader_Name'].lower().endswith('naked_f_body.mat'), \
        f"Material .mat path kept: {mat.get('BSLSP_Shader_Name')}"

    # A native Principled BSDF wired from the PBR maps.
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    assert bsdf, "Has a Principled BSDF"
    assert bsdf.inputs['Base Color'].is_linked, "Base Color wired (albedo x AO)"
    assert bsdf.inputs['Roughness'].is_linked, "Roughness wired"
    assert bsdf.inputs['Metallic'].is_linked, "Metallic wired"
    assert bsdf.inputs['Normal'].is_linked, "Normal wired"

    # One image node per resolved map (albedo/normal/rough/metal/ao).
    teximgs = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
    assert len(teximgs) == 5, f"One image node per PBR map: {len(teximgs)}"
    # Normal Z is reconstructed (BC5 XY) -> a Normal Map node fed by combine/math nodes.
    assert any(n.type == 'NORMAL_MAP' for n in nt.nodes), "Normal reconstructed via Normal Map"


def eval_normal_socket(socket, want):
    """Evaluate one channel of a reconstructed-normal RGB socket by walking the node graph
    backwards. Handles only the node types the reconstruct builds (RGB constant, SeparateColor,
    CombineColor, Math), so it tests what the graph COMPUTES rather than how it is laid out."""
    def value(sock):
        n = sock.node
        if n.type == 'RGB':
            return n.outputs['Color'].default_value[:3]
        if n.type == 'SEPARATE_COLOR':
            rgb = inp(n.inputs['Color'])
            return rgb['RGB'.index(sock.name[0])]
        if n.type == 'COMBINE_COLOR':
            return [inp(n.inputs[c]) for c in ('Red', 'Green', 'Blue')]
        if n.type == 'MATH':
            a, b, c = (inp(i) for i in n.inputs[:3])
            op = n.operation
            if op == 'MULTIPLY_ADD':
                return a * b + c
            if op == 'MULTIPLY':
                return a * b
            if op == 'ADD':
                return a + b
            if op == 'SUBTRACT':
                return a - b
            if op == 'MAXIMUM':
                return max(a, b)
            if op == 'SQRT':
                return math.sqrt(max(a, 0.0))
            raise AssertionError(f"evaluator does not know Math op {op!r}")
        raise AssertionError(f"evaluator does not know node type {n.type!r}")

    def inp(socket_in):
        if socket_in.is_linked:
            return value(socket_in.links[0].from_socket)
        v = socket_in.default_value
        return v[:3] if hasattr(v, '__len__') else v

    return value(socket)['RGB'.index(want[0])]


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_NORMAL_GREEN():
    """Starfield normal maps are DirectX-convention (green = -Y); Blender is OpenGL (+Y), so
    the BC5 reconstruct must INVERT green on the way in.

    Measured, not assumed: a real normal map's slope field must be curl-free, and for both
    `male_default_normal.dds` and the Creation Kit's own FaceGen bake the curl residual is
    ~2x smaller with green flipped. The importer used to pass green straight through, which
    lights every Starfield normal backwards in Y. Export writes only the .mat's texture paths
    -- never pixels -- so there is nothing to re-invert on the way out.

    Red must pass through untouched (X is the same in both conventions) and blue is the
    reconstructed Z, which squares Y and so is a control: it must not move.
    """
    from io_scene_nifly.nif.shader_io import _reconstruct_normal_rgb

    mat = bpy.data.materials.new("pyn_normal_green")
    mat.use_nodes = True
    nt = mat.node_tree

    # A file-space normal tilted +Y: UNORM green 0.75 -> y = +0.5. Red 0.5 -> x = 0.
    src = nt.nodes.new('ShaderNodeRGB')
    src.outputs['Color'].default_value = (0.5, 0.75, 0.0, 1.0)
    out = _reconstruct_normal_rgb(nt, src.outputs['Color'], (0, 0))

    green = eval_normal_socket(out, 'Green')
    assert TT.is_eq(round(green, 4), 0.25,
                    "Green inverted: DirectX -Y in the file is +Y (0.25) in Blender")

    red = eval_normal_socket(out, 'Red')
    assert TT.is_eq(round(red, 4), 0.5, "Red passes through unchanged")

    # z = sqrt(1 - 0^2 - 0.5^2) = 0.8660 -> encoded 0.5*z + 0.5.
    blue = eval_normal_socket(out, 'Blue')
    assert TT.is_eq(round(blue, 4), round(0.5 * math.sqrt(0.75) + 0.5, 4),
                    "Blue is the reconstructed Z, unaffected by the green flip")

    bpy.data.materials.remove(mat)


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_LOD_IMPORT():
    """Starfield: every LOD slot of a BSGeometry imports, one mesh child per distinct .mesh.

    A vanilla crowd head has four slots on three .mesh files -- slots 1 and 2 share one (ABBC).
    They come in under the shape's container Empty as ':LOD0', ':LOD1-2' and ':LOD3', each with
    its own geometry, all weighted to the one armature and sharing the material. Only LOD0
    shows; the others are hidden."""
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'female',
                            'crowd_female_af_md1.nif')
    bpy.ops.import_scene.pynifly(filepath=testfile)

    empty = bpy.data.objects.get("BSGeometry:crowd_female_af_md1:0")
    assert TT.is_true(empty is not None, "BSGeometry container imported")
    children = {c.name: c for c in empty.children}
    assert TT.is_eq(sorted(children),
                    ["crowd_female_af_md1:0:LOD0", "crowd_female_af_md1:0:LOD1-2",
                     "crowd_female_af_md1:0:LOD3"],
                    "one child per distinct .mesh, named by the slots it fills")

    lod0 = children["crowd_female_af_md1:0:LOD0"]
    lod12 = children["crowd_female_af_md1:0:LOD1-2"]
    lod3 = children["crowd_female_af_md1:0:LOD3"]
    assert TT.is_eq([len(o.data.vertices) for o in (lod0, lod12, lod3)], [4179, 1022, 806],
                    "each LOD has its own geometry")
    assert TT.is_eq((lod0.hide_get(), lod12.hide_get(), lod3.hide_get()), (False, True, True),
                    "only LOD0 shows")

    armas = {next(m.object for m in o.modifiers if m.type == 'ARMATURE')
             for o in (lod0, lod12, lod3)}
    assert TT.is_eq(len(armas), 1, "all LODs bound to the one armature")
    for o in (lod12, lod3):
        assert TT.is_gt(len(o.vertex_groups), 10, f"{o.name} carries its bone weights")
        assert TT.is_true(o.active_material is lod0.active_material,
                          f"{o.name} shares LOD0's material")
    assert TT.is_eq([o.pyn_sf_geometry.mesh_path == '' for o in (lod0, lod12, lod3)],
                    [False, False, False], "each LOD records its .mesh")
    assert TT.is_eq(len({o.pyn_sf_geometry.mesh_path for o in (lod0, lod12, lod3)}), 3,
                    "three distinct .mesh paths")


def _sf_slot_meshes(nif_path, shape):
    """Load every LOD slot of a re-read exported shape from the .mesh files written beside the
    nif. Returns per-slot (vertex count, set of weighted vertices)."""
    out = []
    for slot, p in enumerate(shape.mesh_paths()):
        mesh_file = os.path.join(os.path.dirname(nif_path), 'geometries', p + '.mesh')
        with open(mesh_file, 'rb') as f:
            assert shape.load_mesh(f.read(), slot), f"slot {slot} .mesh loads"
        weighted = {vi for bn in shape.bone_names for vi, w in shape.bone_weights[bn] if w > 0}
        out.append((len(shape.verts), weighted))
    return out


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_LOD_ROUNDTRIP():
    """Starfield: a BSGeometry's LODs export back into ONE block with all its slots.

    The crowd head imports as LOD0, LOD1-2 and LOD3 objects; export gathers them into one
    BSGeometry with four slots on three .mesh files, slots 1 and 2 sharing one as the original
    does. Each slot keeps its geometry and its weights, under one bone list."""
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'female',
                            'crowd_female_af_md1.nif')
    outfile = TTB.test_file(r"tests\Out\TEST_SF_LOD_ROUNDTRIP.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF')

    nif = pyn.NifFile(outfile)
    assert TT.is_eq([s.name for s in nif.shapes], ["crowd_female_af_md1:0"],
                    "one BSGeometry for all the LODs")
    shape = nif.shapes[0]
    paths = shape.mesh_paths()
    assert TT.is_eq(len(paths), 4, "four slots")
    assert TT.is_eq((paths[1] == paths[2], len(set(paths))), (True, 3),
                    "slots 1 and 2 share a .mesh; three files in all")
    slots = _sf_slot_meshes(outfile, shape)
    assert TT.is_eq([n for n, _ in slots], [4179, 1022, 1022, 806], "each slot's vertex count")
    for slot, (n, weighted) in enumerate(slots):
        assert TT.is_eq(len(weighted), n, f"every vertex of slot {slot} is weighted")


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_LOD_NEW():
    """Starfield: LODs made in Blender. Objects named '<shape>:LOD0' and '<shape>:LOD1' under
    the same parent export as one BSGeometry '<shape>' with two slots, each written to its own
    generated .mesh."""
    outfile = TTB.test_file(r"tests\Out\TEST_SF_LOD_NEW.nif")
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=10)
    lod0 = bpy.context.object
    lod0.name = "Rock:LOD0"
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=10)
    lod1 = bpy.context.object
    lod1.name = "Rock:LOD1"
    n0, n1 = len(lod0.data.vertices), len(lod1.data.vertices)

    BD.ObjectSelect([lod0, lod1], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    nif = pyn.NifFile(outfile)
    assert TT.is_eq([s.name for s in nif.shapes], ["Rock"], "one BSGeometry named for the LODs")
    shape = nif.shapes[0]
    paths = shape.mesh_paths()
    assert TT.is_eq((len(paths), len(set(paths))), (2, 2), "two slots, two .mesh files")
    counts = [n for n, _ in _sf_slot_meshes(outfile, shape)]
    assert TT.is_true(counts[0] >= n0 and n1 <= counts[1] < counts[0],
                      f"LOD0 then the smaller LOD1 ({counts}; Blender {n0}, {n1})")


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_LOD_INTERNAL_WARNS():
    """A .mesh can hold reduced triangle lists over its own vertices -- a second LOD mechanism,
    separate from slots. The vanilla hands carry three. PyNifly doesn't import them, so import
    says so: export will write the .mesh without them."""
    import logging
    messages = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    cap = _Cap(level=logging.WARNING)
    pyn_log = logging.getLogger("pynifly")
    pyn_log.addHandler(cap)
    try:
        bpy.ops.import_scene.pynifly(filepath=TTB.test_file(r"tests\SF\meshes\hands_3rd_f.nif"))
    finally:
        pyn_log.removeHandler(cap)

    warned = [m for m in messages if "Hands_3rd_F:0" in m and "3 reduced triangle lists" in m]
    assert TT.is_neq(warned, [], f"internal LOD lists reported (saw {messages[:3]})")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_PARAMS():
    """Starfield: the .mat's non-texture settings land on PER-COMPONENT value-holder group nodes
    (SF TranslucencySettings, SF LayeredEmissivityComponent, ...), one per .mat settings component,
    each recoverable by socket name and driving the Principled. The skin fixture has translucency +
    emissive but no AlphaSettings (opaque). SSS Weight = AND(Translucency Enable, Use SSS) drives
    Subsurface Weight.
    """
    from io_scene_nifly.nif.shader_io import (sf_component_node_of, SF_SHADER_MODEL_PROP,
                                              SF_SUBSURFACE_SCALE)

    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    body = TTB.find_shape("Naked_F:0")
    mat = body.active_material
    nt = mat.node_tree

    # Translucency component node, recovered by socket name.
    tr = sf_component_node_of(mat, 'translucency')
    assert tr is not None, "SF TranslucencySettings node present"
    tin = tr.inputs
    assert tin["Translucency Enable"].default_value is True, "Translucency enabled"
    assert tin["Use SSS"].default_value is True, "Use SSS enabled"
    assert abs(tin["Spec Lobe 0 Roughness"].default_value - 0.93) < 1e-4, \
        f"spec lobe 0: {tin['Spec Lobe 0 Roughness'].default_value}"
    assert abs(tin["Spec Lobe 1 Roughness"].default_value - 1.15) < 1e-4, \
        f"spec lobe 1: {tin['Spec Lobe 1 Roughness'].default_value}"

    # Emissive component node.
    em = sf_component_node_of(mat, 'emissive')
    assert em is not None, "SF LayeredEmissivityComponent node present"
    assert em.inputs["Emissive Enable"].default_value is False, "Emissive disabled (skin)"
    tint = tuple(em.inputs["Emissive Tint"].default_value)
    assert abs(tint[0] - 0.9) < 1e-4 and abs(tint[1] - 0.1) < 1e-4 and abs(tint[2] - 0.1) < 1e-4, \
        f"Emissive tint recovered: {tint}"

    # The emissive component computes the emission itself: the layer's Emissive goes in, the
    # tinted colour and the strength (0 unless Emissive Enable) come out to the Principled.
    assert TT.is_true(em.inputs["Emissive"].is_linked, "layer Emissive feeds the component")
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    for bsdf_in, out in (('Emission Color', "Emissive Color"),
                         ('Emission Strength', "Emissive Strength")):
        lk = bsdf.inputs[bsdf_in].links[0]
        assert TT.is_eq((lk.from_node, lk.from_socket.name), (em, out),
                        f"{bsdf_in} comes from the emissive component's {out}")

    # Shader-model identity is a string -> a material custom property.
    assert mat[SF_SHADER_MODEL_PROP] == "BodySkin2Layer", \
        f"Shader-model identity kept: {mat.get(SF_SHADER_MODEL_PROP)!r}"
    # Opaque skin -> no AlphaSettings component -> no such node.
    assert sf_component_node_of(mat, 'alpha') is None, "no AlphaSettings node for opaque skin"

    # SSS drives the Principled Subsurface Weight from the translucency component's output.
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    ssw = bsdf.inputs.get('Subsurface Weight')
    assert ssw is not None and ssw.is_linked, "Subsurface Weight is driven"
    assert ssw.links[0].from_node == tr, "Subsurface Weight fed by the translucency component"
    # Scatter Scale is baked to game-unit scale (Blender's default is microscopic on a ~70x mesh).
    assert abs(bsdf.inputs['Subsurface Scale'].default_value - SF_SUBSURFACE_SCALE) < 1e-4, \
        f"Subsurface Scale baked to game units: {bsdf.inputs['Subsurface Scale'].default_value}"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_ALPHA():
    """Starfield P0: an AlphaSettingsComponent (HasOpacity + AlphaTestThreshold) drives cutout
    alpha -- the opacity map (slot 2) wires into Principled Alpha, the threshold sets the
    material clip, and both values are held on the SF Parameters node for round-trip.

    Driven directly through _build_sf_nodes with a synthetic settings/resolved pair (the real
    hair material lives in the cdb) so the test needs no game assets.
    """
    from io_scene_nifly.nif.shader_io import ShaderImporter, sf_component_node_of

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_ao.png")  # content irrelevant; test wiring
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_Alpha_Test")
    mat.use_nodes = True
    si.material = mat
    settings = {'shader_model': 'Hair1Layer',
                'alpha': {'has_opacity': True, 'threshold': 0.3333}}
    si._build_sf_nodes({'Albedo': tex, 'Opacity': tex}, settings)

    # Alpha values held on the SF AlphaSettingsComponent node (the export source).
    p = sf_component_node_of(mat, 'alpha')
    assert p is not None, "SF AlphaSettingsComponent node present"
    assert p.inputs["Has Opacity"].default_value is True, "Has Opacity stored"
    assert abs(p.inputs["Alpha Test Threshold"].default_value - 0.3333) < 1e-4, \
        f"Alpha test threshold stored: {p.inputs['Alpha Test Threshold'].default_value}"

    # The component computes the alpha itself: the opacity map goes in, the tested alpha comes
    # out, so editing its inputs changes the preview with no rewiring.
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    assert TT.is_true(bsdf.inputs['Alpha'].is_linked, "Alpha is driven")
    lk = bsdf.inputs['Alpha'].links[0]
    assert TT.is_eq((lk.from_node, lk.from_socket.name), (p, "Alpha Out"),
                    "Alpha comes from the alpha component")
    assert TT.is_true(p.inputs["Opacity"].is_linked, "Opacity map feeds the alpha component")

    # Without opacity the component is still wired, so ticking Has Opacity takes effect live.
    mat2 = bpy.data.materials.new("SF_Alpha_Test_Off")
    mat2.use_nodes = True
    si2 = ShaderImporter()
    si2.material = mat2
    si2._build_sf_nodes({'Albedo': tex, 'Opacity': tex},
                        {'shader_model': 'Hair1Layer', 'alpha': {'has_opacity': False}})
    p2 = sf_component_node_of(mat2, 'alpha')
    bsdf2 = next(n for n in mat2.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    assert TT.is_true(bsdf2.inputs['Alpha'].is_linked
                      and bsdf2.inputs['Alpha'].links[0].from_node == p2,
                      "Alpha wired to the component even with Has Opacity off")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_ALPHA_VERTEX():
    """Starfield: an alpha component that takes its opacity from the vertex colors.

    `UseVertexColor` (inside the component's AlphaBlenderSettings) is held on the SF
    AlphaSettingsComponent node. `VertexColorChannel` is what is plugged into its Vertex Color
    input, as in the game: the vertex alpha is PyNifly's VERTEX_ALPHA attribute, the red channel
    is VERTEX_COLOR's. Both are written back, and plugging in another channel changes the one
    written."""
    from io_scene_nifly.nif.shader_io import (ShaderImporter, sf_component_node_of,
                                              recover_sf_material)
    from pyn.sf_materials import write_mat, parse_mat

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_ao.png")
    for channel, attr in (('Alpha', 'VERTEX_ALPHA'), ('Red', 'VERTEX_COLOR')):
        si = ShaderImporter()
        mat = bpy.data.materials.new(f"SF_AlphaVertex_{channel}")
        mat.use_nodes = True
        mat['BSLSP_Shader_Name'] = r'MATERIALS\Test\Decal.mat'
        si.material = mat
        settings = {'shader_model': '1LayerStandard',
                    'alpha': {'has_opacity': True, 'threshold': 0.0, 'use_vertex_color': True,
                              'vertex_color_channel': channel}}
        si._build_sf_nodes({'Albedo': tex, 'Opacity': tex}, settings)

        p = sf_component_node_of(mat, 'alpha')
        assert TT.is_true(p.inputs["Use Vertex Color"].default_value, "Use Vertex Color stored")
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        assert TT.is_eq(bsdf.inputs['Alpha'].links[0].from_node, p,
                        f"{channel}: Alpha comes from the alpha component")

        # The channel the .mat names is plugged into the component.
        src = p.inputs["Vertex Color"].links[0].from_node
        if src.type == 'SEPARATE_COLOR':
            assert TT.is_eq(p.inputs["Vertex Color"].links[0].from_socket.name, channel,
                            f"{channel}: separator output")
            src = src.inputs[0].links[0].from_node
        assert TT.is_eq((src.type, src.attribute_name), ('ATTRIBUTE', attr),
                        f"{channel}: reads {attr}")

        rec = recover_sf_material(mat)
        back = parse_mat(write_mat(rec))['settings']['alpha']
        assert TT.is_eq((back['use_vertex_color'], back['vertex_color_channel']), (True, channel),
                        f"{channel}: vertex-color settings round-trip")

    # Rewiring the Red material to the vertex alpha makes it an Alpha-channel material.
    va = mat.node_tree.nodes.new('ShaderNodeAttribute')
    va.attribute_name = 'VERTEX_ALPHA'
    mat.node_tree.links.new(va.outputs['Fac'], p.inputs["Vertex Color"])
    back = parse_mat(write_mat(recover_sf_material(mat)))['settings']['alpha']
    assert TT.is_eq(back['vertex_color_channel'], 'Alpha', "channel follows the wiring")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_TEXTURE_BY_SOCKET():
    """Starfield: a layer's textures are the images plugged into it.

    Export used to find a layer's textures by the slot and layer import stamped on each image
    node, ignoring the wiring. An image node added by hand and plugged into a layer's Opacity
    input carried no stamp and was silently left out of the .mat; a stamped AO node that had been
    unplugged was still exported. The socket an image feeds now names its slot, and a slot that
    had a texture but has nothing plugged in is reported as removed, so the writer drops the file
    the texture set carried."""
    from io_scene_nifly.nif.shader_io import (ShaderImporter, recover_sf_material, _is_group,
                                              SF_LAYER_GROUP)
    from pyn.sf_materials import write_mat, parse_mat

    color = TTB.test_file(r"tests\SF\textures\SF\test\body_color.png")
    ao = TTB.test_file(r"tests\SF\textures\SF\test\body_ao.png")
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_TexBySocket")
    mat.use_nodes = True
    mat['BSLSP_Shader_Name'] = r'MATERIALS\Test\Tail.mat'
    si.material = mat
    si._build_sf_nodes({'Albedo': (color, r'Textures\SF\test\body_color.dds'),
                        'AO': (ao, r'Textures\SF\test\body_ao.dds')},
                       {'shader_model': '1LayerStandard'})
    nt = mat.node_tree
    layer = next(n for n in nt.nodes if _is_group(n, SF_LAYER_GROUP))

    # Unplug the AO image, leaving the node in the tree.
    ao_node = next(n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.get('pyn_sf_slot') == 'AO')
    for lk in list(ao_node.outputs['Color'].links):
        nt.links.remove(lk)
    # Plug a new, unstamped image into Opacity, through a reroute.
    op = nt.nodes.new('ShaderNodeTexImage')
    op.image = bpy.data.images.load(ao, check_existing=True)
    rr = nt.nodes.new('NodeReroute')
    nt.links.new(op.outputs['Color'], rr.inputs[0])
    nt.links.new(rr.outputs[0], layer.inputs['Opacity'])

    ly = recover_sf_material(mat)['layers'][0]
    assert TT.is_eq(sorted(ly['textures']), ['Albedo', 'Opacity'], "textures are what's plugged in")
    assert TT.is_eq(ly['textures']['Opacity'].lower(), r'textures\sf\test\body_ao.dds',
                    "the plugged image's game path")
    assert TT.is_eq(ly.get('removed_textures'), ['AO'], "the unplugged slot is reported removed")

    back = parse_mat(write_mat(recover_sf_material(mat)))['layers'][0]['textures']
    assert TT.is_eq(sorted(back), ['Albedo', 'Opacity'], "and the .mat says the same")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_HAIR():
    """Starfield P4: HairSettings lands on its own SF HairSettingsComponent node (per-component
    settings groups), holds the ~11 hair params for round-trip, and drives Principled Sheen
    (Backscatter -> Sheen Weight, Roughness -> Sheen Roughness). Transmission scales are held only.
    """
    from io_scene_nifly.nif.shader_io import (ShaderImporter, sf_component_node_of,
                                              recover_sf_material)
    from pyn.sf_materials import write_mat, parse_mat

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_color.png")
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_Hair_Test")
    mat.use_nodes = True
    si.material = mat
    mat['BSLSP_Shader_Name'] = r'MATERIALS\Test\Hair.mat'
    hair = {'enabled': True, 'is_spiky': False, 'roughness': 0.25, 'spec_scale': 0.0,
            'backscatter_strength': 0.4, 'backscatter_wrap': 0.1, 'spec_transmission': 0.675,
            'direct_transmission': 0.2375, 'diffuse_transmission': 0.7, 'max_depth_offset': 0.01,
            'dither_scale': 1.0}
    si._build_sf_nodes({'Albedo': tex}, {'shader_model': 'Hair1Layer', 'hair': hair})

    # Its own component node, holding the hair params (including the held-only transmission scales).
    h = sf_component_node_of(mat, 'hair')
    assert h is not None, "SF HairSettingsComponent node present"
    assert h.inputs["Hair Enable"].default_value is True, "hair enabled"
    assert abs(h.inputs["Roughness"].default_value - 0.25) < 1e-4, "roughness held"
    assert abs(h.inputs["Diffuse Transmission"].default_value - 0.7) < 1e-4, "transmission held"

    # Drives Principled Sheen from the hair node.
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    if 'Sheen Weight' in bsdf.inputs:
        assert bsdf.inputs['Sheen Weight'].is_linked, "Sheen Weight driven"
        assert bsdf.inputs['Sheen Weight'].links[0].from_node == h, "Sheen from the hair component"

    # Round-trips out of the graph.
    data = recover_sf_material(mat)
    back = parse_mat(write_mat(data))
    assert back['settings']['hair'] == data['settings']['hair'], \
        f"hair round-trips: {back['settings'].get('hair')}"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_LAYERED():
    """Starfield P3: a two-layer material is built as SF Layer groups chained through an SF Blend
    group carrying the PBR bundle; the Skin blend RNM-composites the detail normal over the base
    (RNM now lives *inside* the SF Blend Skin group), tiled by the detail layer's UV scale.

    Driven through _build_sf_nodes directly with a synthetic 2-layer/1-blender graph (test PNGs,
    no game assets).
    """
    from io_scene_nifly.nif.shader_io import (ShaderImporter, SF_LAYER_GROUP, SF_BLEND_GROUP,
                                              SF_NORMAL_BLEND_GROUP)

    alb = TTB.test_file(r"tests\SF\textures\SF\test\body_color.png")
    nrm = TTB.test_file(r"tests\SF\textures\SF\test\body_normal.png")
    mask = TTB.test_file(r"tests\SF\textures\SF\test\body_ao.png")
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_Layered_Test")
    mat.use_nodes = True
    si.material = mat
    resolved = {'Albedo': alb, 'Normal': nrm}
    layers_resolved = [
        {'textures': {'Albedo': alb, 'Normal': nrm}, 'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0)},
        {'textures': {'Normal': nrm}, 'uv_scale': (50.0, 50.0), 'uv_offset': (0.0, 0.0)},
    ]
    blenders_resolved = [{'mode': 'Skin', 'mask': mask}]
    si._build_sf_nodes(resolved, {}, layers_resolved, blenders_resolved)
    nt = mat.node_tree

    # Matched via the production helper: group datablocks carry a version suffix ("SF Layer v5"),
    # and a plain startswith would also match "SF LayeredEmissivityComponent".
    from io_scene_nifly.nif.shader_io import _is_group

    def groups(prefix):
        return [n for n in nt.nodes if _is_group(n, prefix)]

    # Two SF Layer groups (one per layer) each carrying the bundle.
    assert len(groups(SF_LAYER_GROUP)) == 2, f"two SF Layer groups: {len(groups(SF_LAYER_GROUP))}"

    # One SF Blend group, fed both layers' bundles + the mask.
    blends = groups(SF_BLEND_GROUP)
    assert len(blends) == 1, f"one SF Blend group: {len(blends)}"
    blend = blends[0]
    assert blend.inputs['A Normal'].is_linked and blend.inputs['B Normal'].is_linked, \
        "both layer bundles wired into the blend"
    assert blend.inputs['Mask'].is_linked, "blend mask wired"
    # The RNM math lives inside the SF Blend Skin group now.
    assert any(_is_group(inner, SF_NORMAL_BLEND_GROUP)
               for inner in blend.node_tree.nodes), "SF Blend Skin uses the RNM group internally"

    # Detail layer's 50x tiling comes through a Mapping node.
    assert any(n.type == 'MAPPING' for n in nt.nodes), "detail UV tiling via a Mapping node"

    # Principled Normal is fed from the bundle (through a Normal Map node).
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    assert bsdf.inputs['Normal'].is_linked, "Principled Normal wired"
    assert bsdf.inputs['Normal'].links[0].from_node.type == 'NORMAL_MAP', \
        "Normal fed via a Normal Map node"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_ROUNDTRIP():
    """Starfield P2: recover a material's graph back to a .mat and round-trip it.

    Build a 2-layer material (with .mat-stamped image nodes + SF Layer/Blend markers + the SF
    Parameters node), recover_sf_material() walks it back to a normalised dict, write_mat() emits a
    loose .mat, and parse_mat() reads it -- reproducing the layers/blenders/settings. Proves the
    graph is the recoverable source of truth (the 'build for export' payoff)."""
    from io_scene_nifly.nif.shader_io import ShaderImporter, recover_sf_material
    from pyn.sf_materials import write_mat, parse_mat

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_normal.png")
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_RT_Test")
    mat.use_nodes = True
    si.material = mat
    mat['BSLSP_Shader_Name'] = r'MATERIALS\Test\Body.mat'
    settings = {'shader_model': 'BodySkin2Layer',
                'translucency': {'enabled': True, 'use_sss': True,
                                 'spec_lobe0_roughness': 0.93, 'spec_lobe1_roughness': 1.15},
                'emissive': {'enabled': False, 'first_layer_index': 0, 'blender_mode': 'Lerp',
                             'tint': (0.9, 0.1, 0.1, 1.0)},
                'alpha': {'has_opacity': False, 'threshold': 0.5}}
    # Resolved entries are (filepath, .mat-path) so image nodes get stamped for recovery.
    A = (tex, r'Textures\Skin\color.dds'); N = (tex, r'Textures\Skin\normal.dds')
    D = (tex, r'Textures\Skin\detail.dds'); M = (tex, r'Textures\Skin\mask.dds')
    resolved = {'Albedo': A, 'Normal': N}
    layers_resolved = [
        {'textures': {'Albedo': A, 'Normal': N}, 'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0)},
        {'textures': {'Normal': D}, 'uv_scale': (50.0, 50.0), 'uv_offset': (0.0, 0.0)}]
    blenders_resolved = [{'mode': 'Skin', 'mask': M}]
    si._build_sf_nodes(resolved, settings, layers_resolved, blenders_resolved)

    # Recovery reads texture paths from the ASSIGNED image (the graph is the source of truth), so
    # give each stamped node an image sitting at its intended game location. Deriving that back
    # reproduces the .mat-relative path -- the same path the import stamp carries.
    from io_scene_nifly.nif.shader_io import PYN_SF_PATH
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and PYN_SF_PATH in n:
            img = bpy.data.images.new(os.path.basename(n[PYN_SF_PATH]), 8, 8)
            img.filepath = r"C:\Game\Data" + "\\" + n[PYN_SF_PATH]
            n.image = img

    data = recover_sf_material(mat)
    assert data is not None, "recovered a material dict from the graph"
    # Structure recovered from markers + stamped images.
    assert len(data['layers']) == 2, f"two layers recovered: {len(data['layers'])}"
    assert data['layers'][0]['textures'].get('Albedo') == r'Textures\Skin\color.dds', \
        f"base albedo path recovered: {data['layers'][0]['textures']}"
    assert data['layers'][1]['textures'] == {'Normal': r'Textures\Skin\detail.dds'}, \
        f"detail layer recovered: {data['layers'][1]['textures']}"
    assert data['layers'][1]['uv_scale'] == (50.0, 50.0), \
        f"detail tiling recovered: {data['layers'][1]['uv_scale']}"
    assert data['blenders'] == [{'mode': 'Skin', 'mask': r'Textures\Skin\mask.dds', 'channel': ''}], \
        f"blender recovered: {data['blenders']}"
    assert data['settings']['shader_model'] == 'BodySkin2Layer', "shader model recovered"
    assert data['settings']['translucency']['use_sss'] is True, "SSS recovered"
    assert data['filename'] == r'MATERIALS\Test\Body.mat', "material path recovered"

    # Full write -> parse round-trip of the recovered data.
    back = parse_mat(write_mat(data))
    # Compared on material CONTENT: a re-parsed material also carries each node's identity (its
    # res: id, Parent and components), which the hand-built dict above has no reason to have.
    from pyn.sf_materials import material_content
    back_c, data_c = material_content(back), material_content(data)
    assert back_c['layers'] == data_c['layers'], f"layers round-trip: {back_c['layers']}"
    assert back_c['blenders'] == data_c['blenders'], f"blenders round-trip: {back_c['blenders']}"
    assert back_c['settings'] == data_c['settings'], f"settings round-trip: {back_c['settings']}"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_UNWIRED_LAYER_DROPPED():
    """Starfield: a layer that can't reach the Material Output is NOT exported.

    The node tree is the material, so what isn't wired isn't in it. Bad Dog simplified a head
    material by feeding layer 0 straight into the Principled BSDF, orphaning the blend chain --
    and the exported .mat still carried all 6 layers, because recovery collected every stamped
    node regardless of connectivity. Here: build 2 layers + 1 blender, rewire layer 0 direct,
    and only layer 0 should survive recovery."""
    from io_scene_nifly.nif.shader_io import (ShaderImporter, recover_sf_material, _is_group,
                                              SF_LAYER_GROUP, SF_BLEND_GROUP, PYN_SF_LAYER,
                                              PYN_SF_PATH)

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_normal.png")
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_Unwired_Test")
    mat.use_nodes = True
    si.material = mat
    mat['BSLSP_Shader_Name'] = r'MATERIALS\Test\Body.mat'
    A = (tex, r'Textures\Skin\color.dds'); N = (tex, r'Textures\Skin\normal.dds')
    D = (tex, r'Textures\Skin\detail.dds'); M = (tex, r'Textures\Skin\mask.dds')
    layers_resolved = [
        {'textures': {'Albedo': A, 'Normal': N}, 'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0)},
        {'textures': {'Normal': D}, 'uv_scale': (50.0, 50.0), 'uv_offset': (0.0, 0.0)}]
    si._build_sf_nodes({'Albedo': A, 'Normal': N}, {}, layers_resolved, [{'mode': 'Skin', 'mask': M}])
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and PYN_SF_PATH in n:
            img = bpy.data.images.new(os.path.basename(n[PYN_SF_PATH]), 8, 8)
            img.filepath = r"C:\Game\Data" + "\\" + n[PYN_SF_PATH]
            n.image = img

    # Both layers are wired as built, so both export.
    assert len(recover_sf_material(mat)['layers']) == 2, "both layers recovered while wired"

    # Bypass the blend chain: layer 0 straight into the BSDF, blend outputs cut.
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    layer0 = next(n for n in nt.nodes
                  if _is_group(n, SF_LAYER_GROUP) and n.get(PYN_SF_LAYER) == 0)
    blend = next(n for n in nt.nodes if _is_group(n, SF_BLEND_GROUP))
    for link in [lk for lk in nt.links if lk.from_node == blend]:
        nt.links.remove(link)
    nt.links.new(layer0.outputs['Base Color'], bsdf.inputs['Base Color'])

    data = recover_sf_material(mat)
    assert len(data['layers']) == 1, \
        f"only the wired layer exports: {len(data['layers'])} layers"
    assert data['layers'][0]['textures'].get('Albedo') == r'Textures\Skin\color.dds', \
        f"the surviving layer is layer 0: {data['layers'][0]['textures']}"
    assert data['blenders'] == [], f"the orphaned blender is dropped: {data['blenders']}"


@TT.category('STARFIELD')
def TEST_SF_ANIMATION_FLAG_ROUNDTRIP():
    """Starfield: AnimationFlagExtra survives import and export.

    NiIntegersExtraData is PLURAL -- an array of uint32, a different block type from
    NiIntegerExtraData. PyNifly couldn't read it at all: importing a vanilla head logged "Unknown
    block type" and the block was gone from anything exported. 273 of the 373 vanilla shape nifs
    surveyed carry one, on the BSGeometry block; the male head's value is 32.

    Found while diffing Bad Dog's invisible Lykaios head against vanilla. It turned out NOT to be
    the cause -- he pasted the block in by hand and the head stayed invisible -- but a block every
    vanilla head carries and we silently drop is worth closing regardless.
    """
    testfile = TTB.test_file(r"tests\SF\meshes\malehead.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SF_ANIMATION_FLAG_ROUNDTRIP.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    ed = TTB.find_shape("NiIntegersExtraData:AnimationFlagExtra", type='EMPTY')
    assert ed is not None, "the plural extra-data block was imported"
    from io_scene_nifly.nif import pyn_props
    g = pyn_props.get_group(ed, 'pyn_niintsdata')
    assert TT.is_eq(g.name, 'AnimationFlagExtra', "name imported")
    assert TT.is_eq(g.value, '32', "the male head's animation flag is 32")
    # It hangs off the SHAPE, not the root -- that is where the engine looks for it.
    assert ed.parent is not None and ed.parent.type == 'MESH', \
        f"parented to the shape, not the root: {ed.parent.name if ed.parent else None}"

    for o in bpy.data.objects:
        o.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF')

    nifout = pyn.NifFile(outfile)
    shape = nifout.shapes[0]
    blocks = {e.name: e for e in shape.extra_data() if e.blockname == 'NiIntegersExtraData'}
    assert TT.is_eq(sorted(blocks), ['AnimationFlagExtra'], "written back onto the shape")
    assert TT.is_eq(blocks['AnimationFlagExtra'].values, [32], "with its value intact")
    # The singular block is a different type and must not be confused with it. It must also appear
    # exactly ONCE: the derived-MaterialID pass tested for an existing block by NAME, and a block
    # added during an export reports an empty name until the file is written and read back, so
    # every imported head came out with two.
    ints = [e.name for e in shape.extra_data() if e.blockname == 'NiIntegerExtraData']
    assert TT.is_eq(ints, ['MaterialID'], "the singular block exports once, as itself")
    # Same shape of bug on the root: creating an SF shape makes the DLL add a default BSXFlags,
    # and the exporter used to add a second on top of it.
    bsx = [e.name for e in nifout.rootNode.extra_data() if e.blockname == 'BSXFlags']
    assert TT.is_eq(bsx, ['BSX'], "exactly one BSXFlags on the root")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_GROUP_VERSION_KEEPS_OLD_MATERIALS():
    """Bumping an SF node group's version must not touch the materials already using it.

    The version is part of the group's NAME ('SF Layer v5') and a group is never removed. A .blend
    accumulates materials built by different versions of the add-on, and a shared datablock can
    only be one version at a time -- so the old approach, deleting the group and building the new
    one, orphaned every node still using it: node_tree became None and the sockets and links went
    with it.

    Real case: Bad Dog imported a vanilla male head into a file holding a work-in-progress Lykaios
    head. The import rebuilt SF Layer at the new version and cut all six of the Lykaios material's
    layer nodes loose, along with every link in the material.
    """
    from io_scene_nifly.nif.shader_io import (ShaderImporter, ensure_sf_layer_group, _is_group,
                                              SF_LAYER_GROUP, PYN_SF_LAYER)
    from io_scene_nifly.nif import shader_io as S

    old_group = ensure_sf_layer_group()
    mat = bpy.data.materials.new("SF_OldVersion")
    mat.use_nodes = True
    nt = mat.node_tree
    node = nt.nodes.new('ShaderNodeGroup')
    node.node_tree = old_group
    node[PYN_SF_LAYER] = 0
    img = nt.nodes.new('ShaderNodeTexImage')
    bsdf = nt.nodes['Principled BSDF']
    nt.links.new(img.outputs['Color'], node.inputs['Albedo'])
    nt.links.new(node.outputs['Base Color'], bsdf.inputs['Base Color'])

    saved = S._SF_GROUP_VERSION
    try:
        S._SF_GROUP_VERSION = saved + 1000      # as a real bump would
        new_group = ensure_sf_layer_group()
    finally:
        S._SF_GROUP_VERSION = saved

    assert TT.is_neq(new_group, old_group, "the bump built a NEW group datablock")
    assert TT.is_true(old_group.name in bpy.data.node_groups,
                      "the old group still exists -- nothing was removed")
    assert TT.is_eq(node.node_tree, old_group, "the old material still points at its own group")
    assert TT.is_true(node.inputs['Albedo'].is_linked, "its incoming link survived")
    assert TT.is_true(node.outputs['Base Color'].is_linked, "its outgoing link survived")
    assert TT.is_true(_is_group(node, SF_LAYER_GROUP),
                      "and it still reads as an SF Layer group, so export still finds its layers")

    # 'SF Layer' must not match 'SF LayeredEmissivityComponent' -- a plain startswith did, which is
    # why layer counts could never be taken by name.
    emissive = nt.nodes.new('ShaderNodeGroup')
    emissive.node_tree = S.ensure_sf_component_group('emissive')
    assert TT.is_true(not _is_group(emissive, SF_LAYER_GROUP),
                      "the emissivity settings group is not mistaken for a layer")
    assert TT.is_true(S.is_sf_component_node(emissive, 'emissive'),
                      "but it is still recognised as its own component")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_VERTEX_COLOR_OVERRIDE_NO_COLORS():
    """A vertex-color albedo multiply is only wired up when the mesh HAS vertex colors.

    MaterialOverrideColorTypeComponent 'Multiply' means the layer's albedo is multiplied by the
    mesh's vertex color, and PyNifly builds that as a MULTIPLY mix fed by a VERTEX_COLOR Attribute
    node. But Blender's Attribute node evaluates to ZERO when the named attribute doesn't exist,
    so on a mesh with no vertex colors the multiply turned the whole surface BLACK.

    Real case: vanilla `naked_m.nif`. Its material's base layer says Multiply, its mesh carries no
    color attribute, and the body imported black. The game treats an absent vertex color as white,
    so the faithful rendering is the albedo untouched.

    The component is still recorded on the layer either way -- it is part of the material and has
    to survive export whether or not this mesh gives us anything to multiply by.
    """
    from io_scene_nifly.nif.shader_io import (ShaderImporter, recover_sf_material,
                                              PYN_SF_OVERRIDE_COLOR_TYPE, COLOR_MAP_NAME)

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_normal.png")
    A = (tex, r'Textures\Skin\color.dds')
    layers = [{'textures': {'Albedo': A}, 'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0),
               'override_color': 'Multiply'}]

    def build(has_colors):
        si = ShaderImporter()
        mat = bpy.data.materials.new(f"SF_VC_{has_colors}")
        mat.use_nodes = True
        si.material = mat
        si._build_sf_nodes({'Albedo': A}, {}, layers, [], has_vertex_colors=has_colors)
        return mat

    # No vertex colors: nothing multiplies the albedo, and no Attribute node is left dangling.
    bare = build(False)
    nodes = bare.node_tree.nodes
    assert TT.is_eq([n for n in nodes if n.type == 'ATTRIBUTE'
                     and n.attribute_name == COLOR_MAP_NAME], [],
                    "no VERTEX_COLOR Attribute node on a mesh without vertex colors")
    assert TT.is_eq([n.label for n in nodes if n.label == 'Vertex Color x Albedo'], [],
                    "no albedo multiply on a mesh without vertex colors")
    # ...but the material still says what it is, so export writes the component back.
    layer_node = next(n for n in nodes if n.get(PYN_SF_OVERRIDE_COLOR_TYPE) is not None)
    assert TT.is_eq(layer_node[PYN_SF_OVERRIDE_COLOR_TYPE], 'Multiply',
                    "the override is still recorded for export")
    assert TT.is_eq(recover_sf_material(bare)['layers'][0]['override_color'], 'Multiply',
                    "and it recovers off the graph")

    # With vertex colors, the multiply is built as before.
    withc = build(True)
    nodes = withc.node_tree.nodes
    assert TT.is_true(any(n.type == 'ATTRIBUTE' and n.attribute_name == COLOR_MAP_NAME
                          for n in nodes), "VERTEX_COLOR Attribute node when the mesh has colors")
    assert TT.is_true(any(n.label == 'Vertex Color x Albedo' for n in nodes),
                      "albedo multiply when the mesh has colors")
    assert TT.is_eq(recover_sf_material(withc)['layers'][0]['override_color'], 'Multiply',
                    "override recovers either way")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_PROVENANCE():
    """Starfield: an imported material knows what it inherited and from where.

    A `.mat` is a DERIVATION -- authored `left_eye.mat` names `Eye1Layer.mat` with `Import`
    and restates only what it changes, leaving the shader model, the eye settings' `Enabled`
    and most of its layers to the template. Import resolves that chain, so the node tree
    shows the EFFECTIVE material: correct to render from, and on its own unable to say which
    of those values this file actually owns. Writing an inherited value back as if it were
    local is how a derivation becomes the flat file that renders nowhere, so the answer is
    stamped as the tree is built.

    The fixtures are the authored vanilla files, both of them -- the point of the test is a
    real chain, and a flattened copy has no chain to find. Textures are left unresolved;
    this is about provenance, not pixels.
    """
    import json
    from io_scene_nifly.nif.shader_io import ShaderImporter, PYN_SF_IMPORT, PYN_SF_ORIGIN, _group_base
    from pyn.sf_matchain import LOCAL

    path = TTB.test_file(r"tests\SF\materials\Actors\Human\Faces\left_eye.mat")
    local = json.load(open(path, encoding='utf-8-sig'))
    assert TT.is_eq(local.get('Import'), ['materials/layered/shadermodels/eye1layer.mat'],
                    "the fixture is the authored file, and it derives from the template")

    si = ShaderImporter()
    si.material = bpy.data.materials.new("SF_Provenance")
    si.material.use_nodes = True
    si._sf_altpaths = []
    parsed = si._sf_read_material(path)
    assert parsed is not None, "the material read"

    # CONTROL: what the local file says on its own, versus what arrived.
    assert TT.is_eq(
        any(c['Type'].endswith('ShaderModelComponent')
            for c in local['Objects'][0].get('Components', [])),
        False, "the authored file names no shader model")
    assert TT.is_eq(parsed['settings'].get('shader_model'), 'Eye1Layer',
                    "and the template's arrived through the chain")
    # The chain is recorded on the material. Its tail depends on whether a material
    # database is configured -- the Root templates ship only inside one -- so what is
    # pinned here is the part that always resolves: this file, then the template it names.
    chain = json.loads(si.material['pyn_sf_chain'])
    assert TT.is_eq(chain[0], 'left_eye.mat', f"the chain starts with the material: {chain}")
    assert TT.is_eq('eye1layer' in chain[1].lower(), True,
                    f"and continues into the template it imports: {chain}")
    # What it DECLARES is kept separately and verbatim -- that is what export writes back.
    assert TT.is_eq(json.loads(si.material[PYN_SF_IMPORT]), local['Import'],
                    f"the Import list survives as written: {si.material.get(PYN_SF_IMPORT)}")

    stripped = [dict(ly, textures={}) for ly in parsed['layers']]
    blends = [dict(b, mask=None) for b in parsed['blenders']]
    si._build_sf_nodes({}, parsed['settings'], stripped, blends)

    def origin(owner):
        raw = owner.get(PYN_SF_ORIGIN)
        return json.loads(raw) if raw else None

    # The material stands for the root object, whose RECORD is local however much of what
    # hangs off it is not -- so the fields carry the real answer.
    root = origin(si.material)
    assert root is not None, "the material carries provenance"
    assert TT.is_eq(root['origin'], LOCAL, "the root object is this file's")
    inherited = root.get('fields', {})
    model = 'BSMaterial::ShaderModelComponent[0].FileName'
    assert model in inherited, f"the shader model is marked inherited: {sorted(inherited)[:6]}"
    assert TT.is_eq('eye1layer' in inherited[model].lower(), True,
                    f"and names the template: {inherited[model]}")

    nodes = si.material.node_tree.nodes
    # The eye settings node: the six iris numbers are this file's, `Enabled` is not. Per
    # FIELD, because a component merges field by field -- the whole reason a wholesale
    # replace loses exactly what the author chose not to restate.
    eye = next((n for n in nodes if 'EyeSettings' in (n.node_tree.name if n.type == 'GROUP'
                                                      else '')), None)
    assert eye is not None, "the material built an eye settings node"
    eo = origin(eye)
    assert eo is not None, "which carries provenance of its own"
    assert TT.is_eq(eo['origin'], LOCAL, "this file does set the eye settings")
    assert TT.is_eq('eye1layer' in eo['fields']['Enabled'].lower(), True,
                    f"but not Enabled: {eo['fields']}")
    assert 'IrisDepthPosition' not in eo.get('fields', {}),         "the iris numbers it did restate are its own"

    # The eye's two blenders declare no blend mode ANYWHERE in the chain -- Eye1Layer.mat
    # has none, where Skin5Layer.mat gives all five of the head's blenders one. That is the
    # material saying nothing, not us failing to read it, so the graph says Default rather
    # than Unknown; Unknown is reserved for a mode we were given and don't implement. The first
    # is the iris/sclera blend, which the eye shader cuts by UV radius, so it previews as Eye
    # (TEST_SF_EYE_IRIS_PREVIEW) -- still with no mode of its own.
    blends = sorted((n for n in nodes if n.get('pyn_sf_blend') is not None),
                    key=lambda n: n['pyn_sf_blend'])
    assert TT.is_eq(len(blends), 2, f"two blend nodes: {len(blends)}")
    assert TT.is_eq([n.get('pyn_sf_mode') for n in blends], ['', ''],
                    "and neither carries a mode")
    assert TT.is_eq([_group_base(n.node_tree.name) for n in blends],
                    ['SF Blend Eye', 'SF Blend Default'], "iris/sclera as Eye, the other Default")

    # A layer stands for up to four .mat objects, so its provenance is keyed by which.
    layers = [n for n in nodes if n.get('pyn_sf_layer') is not None and n.type == 'GROUP']
    assert len(layers) > 0, "the material built layer nodes"
    keyed = [origin(n) for n in layers]
    assert all(k for k in keyed), f"every layer node carries provenance: {keyed}"
    assert TT.is_eq(all(set(k) <= {'layer', 'material', 'textureset', 'uvstream'} for k in keyed),
                    True, f"keyed by which object it stands for: {[sorted(k) for k in keyed]}")

    # And the substance. This eye declares all three of its layers itself, so every object
    # is local -- but their components are not: each layer object PARENTS to one of the
    # template's, and fields it does not restate show through. That is the case the
    # object-level origin cannot express and the one export has to get right.
    assert TT.is_eq(all(e['origin'] == LOCAL for k in keyed for e in k.values()), True,
                    "left_eye.mat declares its own layer objects")
    from_template = {f: src for k in keyed for e in k.values()
                     for f, src in e.get('fields', {}).items()}
    assert TT.is_eq(len(from_template) > 0, True,
                    "yet fields on them still come from the template it parents into")
    assert TT.is_eq(all('eye1layer' in src.lower() for src in from_template.values()), True,
                    f"and they name it: {sorted(set(from_template.values()))}")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_EYE_IRIS_PREVIEW():
    """Starfield functional: an eye previews with the sclera outside the iris, as in game.

    Eye1Layer has an iris layer and a sclera layer and a blender between them with no mode
    and no mask -- nothing in any file says where one stops. The shader decides: the iris
    shows out to a UV RADIUS of `IrisDepthTransitionRatio` from the texture centre, the
    sclera beyond it. Measured in game 2026-09-25: a test mesh with its UVs scaled 2x showed a
    half-size iris and none of the rings painted outside it, which a depth-based cut would
    have shown.

    So this renders the material's Base Color on a UV plane and samples it either side of the
    cut, against the real textures (64x64 fixtures from the game). The cut must also follow
    the settings node: raising the radius there has to move it, or the preview disagrees
    with the game the moment someone edits the value.
    """
    import numpy as np
    from io_scene_nifly.nif.shader_io import ShaderImporter, recover_sf_material

    path = TTB.test_file(r"tests\SF\materials\Actors\Human\Faces\left_eye.mat")
    texdir = TTB.test_file(r"tests\SF\textures\Actors\human\faces\Eyes")

    si = ShaderImporter()
    si.material = bpy.data.materials.new("SF_EyePreview")
    si.material.use_nodes = True
    si._sf_altpaths = []
    parsed = si._sf_read_material(path)
    assert TT.is_equiv(parsed['settings']['eye']['iris_depth_transition_ratio'], 0.16,
                       "vanilla cuts the iris at UV radius 0.16", e=1e-4)

    # Albedo and normal: the two colours that meet at the cut, and the two normals that would.
    faces = os.path.dirname(texdir)

    def fixtures_only(ly):
        keep = {}
        for slot in ('Albedo', 'Normal'):
            mp = ly.get('textures', {}).get(slot)
            if mp:
                rel = mp.replace('\\', '/').lower().split('/faces/')[1][:-4] + '.png'
                keep[slot] = (next(os.path.join(dp, f) for dp, _, fs in os.walk(faces)
                                   for f in fs if os.path.join(dp, f).replace('\\', '/').lower()
                                   .endswith(rel)), mp)
        return dict(ly, textures=keep)
    layers = [fixtures_only(ly) for ly in parsed['layers']]
    iris_png, sclera_png = layers[0]['textures']['Albedo'][0], layers[1]['textures']['Albedo'][0]
    assert TT.is_eq(sorted(layers[1]['textures']), ['Albedo', 'Normal'],
                    "the sclera layer brings a normal of its own")
    si._build_sf_nodes({}, parsed['settings'], layers,
                       [dict(b, mask=None) for b in parsed['blenders']],
                       has_vertex_colors=False)
    mat = si.material
    nt = mat.node_tree

    # The cut is computed inside the blend node; all the material feeds it is the radius.
    blend = next(n for n in nt.nodes if n.get('pyn_sf_blend') == 0)

    def layers_node(i):
        return next(n for n in nt.nodes if n.type == 'GROUP' and n.get('pyn_sf_layer') == i)
    assert TT.is_eq('Mask' in blend.inputs, False, "the eye blend takes no mask")
    radius_from = blend.inputs['Iris Radius'].links[0].from_node
    assert TT.is_eq('EyeSettings' in radius_from.node_tree.name, True,
                    "its radius comes from the eye settings node")
    assert TT.is_eq(any(n.type in ('TEX_COORD', 'VECT_MATH') for n in nt.nodes), False,
                    "and the mask arithmetic is not out in the material")

    # Render a socket through an emission shader so nothing else in the BSDF (metalness,
    # roughness) changes what the bake sees.
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    emit = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])

    def show(socket):
        nt.links.new(socket, emit.inputs['Color'])
    target = nt.nodes.new('ShaderNodeTexImage')
    target.image = bpy.data.images.new("SF_EyeBake", 64, 64, float_buffer=True)
    nt.nodes.active = target

    bpy.ops.mesh.primitive_plane_add()
    plane = bpy.context.object
    plane.data.materials.append(mat)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 1

    def texel(img, u, v):
        w, h = img.size
        px = np.array(img.pixels[:]).reshape(h, w, 4)
        return px[min(h - 1, int(v * h)), min(w - 1, int(u * w)), :3]

    def fixture(png, u, v):
        img = bpy.data.images.load(png, check_existing=True)
        c = texel(img, u, v)   # stored sRGB; the shader sees it linear
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

    def bake(socket, r):
        show(socket)
        bpy.ops.object.bake(type='EMIT', use_clear=True)
        return texel(target.image, 0.5 + r, 0.5)

    def shows(r):
        """Which texture the preview's Base Color shows at UV radius r: 'iris', 'sclera', or
        'mix' when it is measurably neither."""
        u, v = 0.5 + r, 0.5
        got = bake(blend.outputs['Base Color'], r)
        d_iris = np.linalg.norm(got - fixture(iris_png, u, v))
        d_sclera = np.linalg.norm(got - fixture(sclera_png, u, v))
        apart = np.linalg.norm(fixture(iris_png, u, v) - fixture(sclera_png, u, v))
        log.debug(f"r={r}: got {got}, iris {d_iris:.4f}, sclera {d_sclera:.4f}")
        if min(d_iris, d_sclera) > 0.1 * apart:
            return 'mix'
        return 'iris' if d_iris < d_sclera else 'sclera'

    assert TT.is_eq(shows(0.1), 'iris', "inside the radius the iris shows")
    assert TT.is_eq(shows(0.3), 'sclera', "outside it the sclera does")
    # The edge is soft: the iris fades out over the last 0.035 inside the radius.
    assert TT.is_equiv(blend.inputs['Iris Feather'].default_value, 0.035,
                       "fading over 0.035 of UV radius", e=1e-6)
    assert TT.is_eq(shows(0.1425), 'mix', "inside the fade the two textures mix")

    # The cut follows the settings node, live.
    eye = next(n for n in nt.nodes if n.type == 'GROUP' and n.node_tree
               and 'EyeSettings' in n.node_tree.name)
    eye.inputs['Iris Depth Transition'].default_value = 0.35
    assert TT.is_eq(shows(0.3), 'iris', "a larger radius on the settings node widens the iris")
    assert TT.is_eq(shows(0.1), 'iris', "and the centre is still iris")

    # The normal is the iris layer's, straight through: a hard-masked blend of the sclera's
    # detail normal cut a visible seam at the iris edge. CONTROL: out on the sclera the two
    # layers' normals really do differ, so passing the base through is a choice made there.
    eye.inputs['Iris Depth Transition'].default_value = 0.16
    base_n = bake(layers_node(0).outputs['Normal'], 0.3)
    sclera_n = bake(layers_node(1).outputs['Normal'], 0.3)
    assert TT.is_gt(float(np.linalg.norm(base_n - sclera_n)), 0.01,
                    "the sclera's normal differs from the iris layer's")
    for r in (0.1, 0.3):
        assert TT.is_equiv(float(np.linalg.norm(bake(blend.outputs['Normal'], r)
                                                - bake(layers_node(0).outputs['Normal'], r))),
                           0.0, f"the blend passes the iris layer's normal through at r={r}",
                           e=1e-4)

    # Only the preview changed: the blender still exports as the material declared it.
    # Recovery reads what the output reaches, so the BSDF goes back on first.
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    blender = recover_sf_material(mat)['blenders'][0]
    assert TT.is_eq(blender['mode'], '', "the blender still has no mode")
    assert TT.is_eq(blender['mask'], '', "nor a mask texture")
    assert TT.is_eq(blender['channel'], '', "nor a mask channel")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_BASE_GROUPS():
    """Starfield: what a material inherits is VISIBLE in the graph, one group per level.

    Provenance stamps answer "where did this value come from" one node at a time, which you
    have to think to ask. `SF Base` groups answer "what is under me" by being in the graph:
    one node group per inherited material, named for it, each containing the next level down
    and the layers, blends and settings that level actually supplies.

    They are a view and never a source. The material's own tree is what export reads, so the
    test that matters is the last one: adding them changes nothing about what comes out.
    """
    import json
    from io_scene_nifly.nif.shader_io import (ShaderImporter, SF_BASE_GROUP, PYN_SF_BASE,
                                              recover_sf_material, _is_group,
                                              SF_LAYER_GROUP)

    mats = TTB.test_file(r"tests\SF\materials")
    src = os.path.join(mats, r"Actors\Human\Faces\left_eye.mat")

    si = ShaderImporter()
    si.material = bpy.data.materials.new("SF_BaseGroups")
    si.material.use_nodes = True
    si._sf_altpaths = []
    parsed = si._sf_read_material(src)
    stripped = [dict(ly, textures={}) for ly in parsed['layers']]
    blends = [dict(b, mask=None) for b in parsed['blenders']]
    si._build_sf_nodes({}, parsed['settings'], stripped, blends)

    before = recover_sf_material(si.material)
    node = si._build_sf_base_chain(si._sf_chain)
    assert node is not None, "the eye inherits, so it gets a base group"

    # Named for the material it stands for, and it is the parent -- not this material.
    assert TT.is_eq(node.node_tree.name.startswith(SF_BASE_GROUP + ':'), True,
                    f"named as a base group: {node.node_tree.name}")
    assert TT.is_eq('eye1layer' in node[PYN_SF_BASE].lower(), True,
                    f"and stands for the template it derives from: {node[PYN_SF_BASE]}")

    # It holds the template's own content -- this is the point of it being a group rather
    # than a label. Eye1Layer supplies the layer skeleton and the eye settings.
    contents = list(node.node_tree.nodes)
    assert TT.is_eq(any(_is_group(n, SF_LAYER_GROUP) for n in contents), True,
                    f"the template's layers are inside it: {[n.name for n in contents]}")
    assert TT.is_eq(any(n.type == 'GROUP' and n.node_tree
                        and 'EyeSettings' in n.node_tree.name for n in contents), True,
                    "as are the eye settings it supplies")

    # A chain of three nests two deep. The tail (the Root template) resolves only when a
    # material database is configured, so the nesting is asserted only when it is there.
    chain = json.loads(si.material['pyn_sf_chain'])
    nested = [n for n in contents if n.type == 'GROUP' and n.node_tree
              and n.node_tree.name.startswith(SF_BASE_GROUP + ':')]
    assert TT.is_eq(len(nested), 1 if len(chain) > 2 else 0,
                    f"one group per level of the chain {chain}: {[n.node_tree.name for n in nested]}")

    # A view, not a stage: it is wired to nothing.
    links = [ln for ln in si.material.node_tree.links
             if ln.from_node is node or ln.to_node is node]
    assert TT.is_eq(links, [], "the base group is not wired into the shading path")

    # THE test: the material exports exactly as it did before the view existed.
    after = recover_sf_material(si.material)
    assert TT.is_eq(len(after['layers']), len(before['layers']), "same layers recovered")
    assert TT.is_eq(len(after['blenders']), len(before['blenders']), "same blenders recovered")
    assert TT.is_eq(after['settings'], before['settings'], "same settings recovered")
    assert TT.is_eq(after['imports'], before['imports'], "same Import list recovered")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_DERIVED_EXPORT():
    """Starfield: a material imported from a derivation is EXPORTED as one.

    The node tree holds the effective material -- everything that reaches it, inherited and
    owned alike. Writing that back out produces a file that parses, that the Creation Kit
    accepts, and that renders nothing in game. What has to go on disk is the delta, with
    every inherited id verbatim.

    So this drives the real path: import the authored eye through the resolver, build the
    node tree, recover it, write it, and then check the FILE -- that it declares what it
    derives from, that it says less than the complete material, that its ids are the ones it
    came in with, and that resolving it gives the material back.
    """
    import json
    from io_scene_nifly.nif.shader_io import ShaderImporter, recover_sf_material
    from pyn import sf_materials
    from pyn.sf_matchain import resolve_material, resolve_parents

    mats = TTB.test_file(r"tests\SF\materials")
    src = os.path.join(mats, r"Actors\Human\Faces\left_eye.mat")
    authored = json.load(open(src, encoding='utf-8-sig'))

    si = ShaderImporter()
    si.material = bpy.data.materials.new("SF_DerivedExport")
    si.material.use_nodes = True
    si._sf_altpaths = []
    parsed = si._sf_read_material(src)
    stripped = [dict(ly, textures={}) for ly in parsed['layers']]
    blends = [dict(b, mask=None) for b in parsed['blenders']]
    si._build_sf_nodes({}, parsed['settings'], stripped, blends)

    data = recover_sf_material(si.material)
    assert TT.is_eq(data['imports'], authored['Import'],
                    f"the recovered material still knows what it derives from: {data['imports']}")

    parents = resolve_parents(data['imports'], src, search=[mats])
    written = json.loads(sf_materials.write_mat(data, filename=data['filename'],
                                                parents=parents))
    complete = json.loads(sf_materials.write_mat(data, filename=data['filename']))

    # It is a derivation, and it says so.
    assert TT.is_eq(written.get('Import'), authored['Import'],
                    f"the written file declares its parent: {written.get('Import')}")
    n_written = sum(len(o.get('Components') or ()) for o in written['Objects'])
    n_complete = sum(len(o.get('Components') or ()) for o in complete['Objects'])
    assert TT.is_eq(n_written < n_complete, True,
                    f"and says less than the complete form: {n_written} vs {n_complete}")

    # THE bug this whole exercise was about: ids must be the ones the material came in with.
    # A material whose ids have been moved to an invented namespace parses, loads in the CK
    # and renders NOTHING in game, and no check short of running the game catches it.
    authored_ids = {o['ID'] for o in authored['Objects'] if o.get('ID')}
    written_ids = {o['ID'] for o in written['Objects'] if o.get('ID')}
    assert TT.is_eq(written_ids, authored_ids,
                    f"every id survives: {len(written_ids & authored_ids)} of "
                    f"{len(authored_ids)} kept, {len(written_ids - authored_ids)} invented")

    # And it still means the same thing: resolving what we wrote gives the material back.
    back = resolve_material(src, search=[mats], doc=written)
    got = sf_materials.parse_mat_doc(back.to_doc())
    assert TT.is_eq(got['settings'].get('shader_model'), 'Eye1Layer',
                    "the shader model still resolves through the chain")
    assert TT.is_eq(len(got['layers']), len(parsed['layers']), "same layer count")
    assert TT.is_eq(len(got['blenders']), len(parsed['blenders']), "same blender count")
    # Field for field, within float32: the values made a round trip through Blender's
    # sockets, so 0.58 comes back as 0.5799999833106995. What matters is that all seven are
    # there and unchanged in value -- including `Enabled`, which this material does not own
    # and which therefore has to have been read from the template and written back to it.
    ours, want = got['settings'].get('eye'), parsed['settings'].get('eye')
    assert TT.is_eq(sorted(ours), sorted(want), "the same eye settings fields come back")
    for k in want:
        same = (abs(ours[k] - want[k]) < 1e-5 if isinstance(want[k], float)
                else ours[k] == want[k])
        assert same, f"eye settings {k}: {ours[k]} vs {want[k]}"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_COMPONENT_ROUNDTRIP():
    """Starfield: every component family a human bodypart material uses survives the node tree.

    The shader graph is the source of truth on export, so anything the graph can't hold is lost
    however well the parser reads it. This drives real vanilla materials through the actual node
    build and back: parse -> _build_sf_nodes -> recover_sf_material -> patch the original document,
    then check the result FIELD FOR FIELD against what we started with.

    The six fixtures were picked by set cover over the 36 materials referenced by vanilla
    `meshes/actors/human` nifs, so between them they exercise all thirteen families that were
    previously unmodelled -- the shader knobs (ParamBool/MaterialParamFloat), texture
    replacements, eye/mouth/effect/shader-route/LOD/detail-blender settings, and the layer Color.

    Textures are deliberately left unresolved: this test is about everything else a material
    carries, and _build_sf_nodes needs real image files to place image nodes. Patching writes only
    the textures it is given, so leaving them out leaves the document's own texture paths intact
    and the field-for-field comparison still holds.
    """
    import json
    from io_scene_nifly.nif.shader_io import ShaderImporter, recover_sf_material
    from pyn.sf_materials import parse_mat_doc, patch_mat_doc, build_mat_doc

    def flat_fields(data, prefix=''):
        """A component's Data flattened to {dotted field: value}, through typed wrappers."""
        if not isinstance(data, dict):
            return {prefix.rstrip('.'): data}
        out = {}
        for k, v in data.items():
            if k == 'Type':
                continue
            if isinstance(v, dict):
                out.update(flat_fields(v.get('Data', v), prefix + k + '.'))
            else:
                out[prefix + k] = v
        return out

    def fields_of(doc):
        """{(object position, type, index, dotted field): value} -- position identifies a node
        across the rewrite, since patching preserves object order but renames CTNames."""
        flat = flat_fields
        out = {}
        for i, o in enumerate(doc.get('Objects', [])):
            for c in o.get('Components', []):
                if c.get('Type') == 'BSComponentDB::CTName':
                    continue
                for fld, val in flat(c.get('Data')).items():
                    out[(i, c.get('Type'), c.get('Index', 0), fld)] = val
        return out

    fixtures = [r"Faces\male_default.mat", r"Faces\bloodshot_left_eye.mat",
                r"Faces\Jewelry\Generic_FacialJewelry.mat", r"Eyebrows\Male_Eyebrows01.mat",
                r"Faces\Teeth\Mouth.mat", r"Naked_Body\Male\Naked_M_Body_Swimsuit.mat"]
    for n, rel in enumerate(fixtures):
        path = TTB.test_file(os.path.join(r"tests\SF\materials\Actors\Human", rel))
        with open(path, encoding='utf-8-sig') as f:
            doc = json.load(f)
        parsed = parse_mat_doc(doc)

        si = ShaderImporter()
        mat = bpy.data.materials.new(f"SF_Comp_{n}")
        mat.use_nodes = True
        si.material = mat
        mat['BSLSP_Shader_Name'] = parsed.get('filename') or rel
        stripped = [dict(ly, textures={}) for ly in parsed['layers']]
        blends = [dict(b, mask=None) for b in parsed['blenders']]
        si._build_sf_nodes({}, parsed['settings'], stripped, blends)

        data = recover_sf_material(mat)
        assert data is not None, f"{rel}: recovered a material dict from the graph"
        assert TT.is_eq(len(data['layers']), len(parsed['layers']), f"{rel}: layer count")
        assert TT.is_eq(len(data['blenders']), len(parsed['blenders']), f"{rel}: blender count")
        for i, (got, want) in enumerate(zip(data['layers'], parsed['layers'])):
            for key in ('param_bools', 'mat_params', 'tex_replace', 'color',
                        'mip_bias', 'tex_resolution', 'override_color'):
                assert TT.is_eq(got.get(key), want.get(key), f"{rel}: layer {i} {key}")
        for i, (got, want) in enumerate(zip(data['blenders'], parsed['blenders'])):
            for key in ('param_bools', 'mat_params'):
                assert TT.is_eq(got.get(key), want.get(key), f"{rel}: blender {i} {key}")
        for key in ('param_bools', 'lod_materials', 'eye', 'mouth', 'shader_route', 'effect',
                    'lod_settings', 'detail_blender', 'translucency', 'alpha', 'hair'):
            assert TT.is_eq(data['settings'].get(key), parsed['settings'].get(key),
                            f"{rel}: settings {key}")

        # The end-to-end guarantee: writing the recovered material back over its own source must
        # not disturb a single field.
        patched = patch_mat_doc(doc, data, r"Materials\Test\Copy.mat")
        before, after = fields_of(doc), fields_of(patched)
        assert TT.is_eq(sorted(set(after) - set(before)), [], f"{rel}: no field invented")
        assert TT.is_eq(sorted(set(before) - set(after)), [], f"{rel}: no field dropped")
        differing = [k for k in before if k[3] != 'ID' and str(before[k]) != str(after[k])]
        assert TT.is_eq(differing, [], f"{rel}: no field altered")

        # And the stronger one: build the material from the NODE TREE ALONE, with no source
        # document at all. This is what export actually does, and it only works if the Blender
        # nodes carry each .mat object's id, Parent, name and components. Built under the
        # material's own name, so nodes keep their names and can be matched by them -- object
        # ORDER is free to differ, content is not.
        built = build_mat_doc(data, data.get('filename') or rel)

        def by_name(d):
            res = {}
            for o in d.get('Objects', []):
                nm = next((c['Data']['Name'] for c in o.get('Components', [])
                           if c.get('Type') == 'BSComponentDB::CTName'), '<noname>').lower()
                res[(nm, '<Parent>', 0, 'Parent')] = o.get('Parent', '')
                for c in o.get('Components', []):
                    if c.get('Type') == 'BSComponentDB::CTName':
                        continue
                    for fld, val in flat_fields(c.get('Data')).items():
                        res[(nm, c.get('Type'), c.get('Index', 0), fld)] = val
            return res

        # The LOD material is a separate material in the game's database; we reference it by id
        # rather than copying its subtree into our file, so its nodes are expected to be absent.
        want = {k: v for k, v in by_name(doc).items() if '_verylow' not in k[0]}
        got = by_name(built)
        assert TT.is_eq(sorted(set(want) - set(got)), [],
                        f"{rel}: nothing dropped building from the node tree alone")
        differing = [k for k in want if k in got and k[3] != 'ID' and str(want[k]) != str(got[k])]
        assert TT.is_eq(differing, [], f"{rel}: nothing altered building from the node tree alone")


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_IMAGE_SWAP():
    """Starfield: the shader graph is the source of truth for texture paths on export.

    Import stamps each image node with its .mat-relative path (pyn_sf_path). When the artist SWAPS
    the image datablock -- e.g. a tailored Lykaios albedo/AO over the imported human one -- recovery
    must follow the ASSIGNED image, deriving a Textures\\...\\*.dds game path from it. The stamp is
    only a fallback for images that don't resolve under a 'textures' tree (matches how FO4/Skyrim
    export reads the node, not a stored property). Regression: the swap was ignored and the human
    paths re-exported, so the head stayed pink in-game."""
    from io_scene_nifly.nif.shader_io import (ShaderImporter, recover_sf_material,
                                              PYN_SF_LAYER, PYN_SF_SLOT, PYN_SF_PATH, PYN_SF_BLEND)

    tex = TTB.test_file(r"tests\SF\textures\SF\test\body_normal.png")
    si = ShaderImporter()
    mat = bpy.data.materials.new("SF_Swap_Test")
    mat.use_nodes = True
    si.material = mat
    mat['BSLSP_Shader_Name'] = r'MATERIALS\Test\Body.mat'
    # Stamp the base-layer albedo with the HUMAN path, as a real import would.
    HUMAN_ALBEDO = r'Textures\Actors\human\faces\Chargen\male_default_sk3_color.dds'
    A = (tex, HUMAN_ALBEDO); N = (tex, r'Textures\Skin\normal.dds')
    M = (tex, r'Textures\Skin\mask.dds')
    layers_resolved = [{'textures': {'Albedo': A, 'Normal': N},
                        'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0)},
                       {'textures': {'Normal': N}, 'uv_scale': (9.0, 9.0), 'uv_offset': (0.0, 0.0)}]
    blenders_resolved = [{'mode': 'Skin', 'mask': M}]
    si._build_sf_nodes({'Albedo': A, 'Normal': N}, None, layers_resolved, blenders_resolved)

    def stamped(pred):
        return next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and pred(n))
    alb = stamped(lambda n: n.get(PYN_SF_SLOT) == 'Albedo' and n.get(PYN_SF_LAYER) == 0)
    assert alb[PYN_SF_PATH] == HUMAN_ALBEDO, "sanity: albedo stamped with the human path pre-swap"

    # Swap in a tailored albedo living under a game 'Textures' tree. The file need not exist -- we
    # only set the datablock's filepath (recovery reads the path, not the pixels).
    def swap_image(node, game_abs_path):
        img = bpy.data.images.new(os.path.basename(game_abs_path), 8, 8)
        img.filepath = game_abs_path
        node.image = img
    swap_image(alb, r"C:\Steam\steamapps\common\Starfield\Data\Textures\FSF\Lykaios\Head\LykaiosMaleHead_col.png")

    data = recover_sf_material(mat)
    assert data['layers'][0]['textures']['Albedo'] == r'Textures\FSF\Lykaios\Head\LykaiosMaleHead_col.dds', \
        f"swapped albedo follows the assigned image, not the stamp: {data['layers'][0]['textures']}"

    # A swapped blend MASK is honored the same way.
    mask_node = stamped(lambda n: n.get(PYN_SF_BLEND) == 0)
    swap_image(mask_node, r"C:\Steam\steamapps\common\Starfield\Data\Textures\FSF\Lykaios\Head\lykaios_mask.png")
    data = recover_sf_material(mat)
    assert data['blenders'][0]['mask'] == r'Textures\FSF\Lykaios\Head\lykaios_mask.dds', \
        f"swapped mask follows the assigned image: {data['blenders'][0]}"

    # An UNSWAPPED node whose image still can't resolve under a 'textures' tree falls back to its
    # stamp (never silently drops the path).
    orphan = bpy.data.images.new("orphan", 8, 8)  # no filepath -> unresolvable
    alb.image = orphan
    data = recover_sf_material(mat)
    assert data['layers'][0]['textures']['Albedo'] == HUMAN_ALBEDO, \
        f"unresolvable image falls back to the stamp: {data['layers'][0]['textures']}"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_HEAD_MATERIAL():
    """Starfield functional: import the vanilla male head (male_default.mat, 6 layers / 5 blends)
    and confirm the whole material path lands on the real graph. Checks: head mesh in place; 6 SF
    Layer + 5 SF Blend nodes; per-layer UV tiling; blend masks are the channel-packed face-detail
    mask TEXTURES (a couple sampling a specific channel -- chin=Green, lips=Blue); and the vertex-
    color path (base layer multiplies albedo by VERTEX_COLOR -- an unpainted layer renders the head
    black in-game). Textures are 64x64 fixtures copied from the game. Recovery + write/parse round-
    trip the masks/channels/scales/override."""
    from io_scene_nifly.nif.shader_io import recover_sf_material, COLOR_MAP_NAME
    from pyn.sf_materials import write_mat, parse_mat

    testfile = TTB.test_file(r"tests\SF\meshes\malehead.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = TTB.find_shape("MaleHead:0:LOD0")
    assert head is not None, "imported the head mesh"
    # Right position: the head sits at head height (world z ~96-125) and is centred on X, not
    # dumped at the origin or doubled off somewhere.
    ws = [head.matrix_world @ v.co for v in head.data.vertices]
    zmax = max(v.z for v in ws)
    xmid = (min(v.x for v in ws) + max(v.x for v in ws)) / 2
    assert 100 < zmax < 140, f"head at head height (world z max {zmax:.1f})"
    assert abs(xmid) < 5, f"head centred on X ({xmid:.2f})"
    assert COLOR_MAP_NAME in head.data.color_attributes, "mesh carries the VERTEX_COLOR attribute"

    nodes = head.active_material.node_tree.nodes
    data = recover_sf_material(head.active_material)

    # 6 layers / 5 blends -- counted from the stamped graph via recovery. (A plain "SF Layer"
    # name-prefix count is wrong: it also matches the "SF LayeredEmissivityComponent" settings node.)
    assert len(data['layers']) == 6, f"6 SF layers: {len(data['layers'])}"
    assert len(data['blenders']) == 5, f"5 SF blends: {len(data['blenders'])}"

    # Per-layer UV tiling (the detail layers tile 9x-14x over the base).
    scales = [tuple(l['uv_scale']) for l in data['layers']]
    assert scales == [(1.0, 1.0), (9.0, 9.0), (10.0, 10.0), (14.0, 14.0), (14.0, 14.0), (14.0, 14.0)], \
        f"per-layer UV scales: {scales}"

    # Blend masks are the mask TEXTURES; ColorChannelTypeComponent (chin=Green, lips=Blue) selects a
    # channel of that texture. The texture must survive alongside the channel -- the 'young lips'
    # regression was the channel replacing male_lips_mask with a bare vertex-color channel.
    masks = [(b['mask'], b['channel']) for b in data['blenders']]
    lips = next((mc for mc in masks if 'lips_mask' in mc[0].lower()), None)
    assert lips is not None, f"lips mask texture kept as the blend mask: {masks}"
    assert lips[1] == 'Blue', f"lips blends via its mask's Blue channel: {lips}"
    assert [b['channel'] for b in data['blenders']] == ['', 'Green', 'Blue', '', ''], \
        f"mask channels: {[b['channel'] for b in data['blenders']]}"

    # Vertex color enters via the base layer's albedo multiply (the black-head mechanism), fed by a
    # VERTEX_COLOR Attribute node.
    assert any(n.type == 'ATTRIBUTE' and n.attribute_name == COLOR_MAP_NAME for n in nodes), \
        "a VERTEX_COLOR Attribute node was created"
    # ...and it names an attribute the mesh really has. The node is only safe because this head
    # carries vertex colors; on a mesh without them it would evaluate to zero and blacken the
    # albedo, which is what happened to naked_m.
    assert TT.is_eq(TTB.dangling_attribute_nodes(head), [],
                    "the Attribute node names an attribute the mesh has")
    assert data['layers'][0]['override_color'] == 'Multiply', \
        f"base-layer albedo x vertex-color recovered: {data['layers'][0].get('override_color')}"

    # The recovered material round-trips to a .mat (masks/channels/scales/override preserved).
    back = parse_mat(write_mat(data))
    assert [(b['mask'], b['channel']) for b in back['blenders']] == masks, "masks + channels survive"
    assert [tuple(l['uv_scale']) for l in back['layers']] == scales, "UV scales survive"
    assert back['layers'][0]['override_color'] == 'Multiply', "override survives"


@TT.category('STARFIELD')
def TEST_SF_MATERIALS_FLAG_STICKY():
    """The 'export materials' flag (write_sf_materials) is sticky per-nif, like the other export
    options. Regression: it was missing from the consolidated export-settings group, so it never
    persisted -- every export dialog reopened with it off, even after the user turned it on."""
    from io_scene_nifly.nif import pyn_props
    root = bpy.data.objects.new("SF_StickyRoot", None)
    bpy.context.scene.collection.objects.link(root)

    # Untouched: not reported, so the operator keeps its own default (dialog seeds from prefs).
    assert 'write_sf_materials' not in pyn_props.read_export_settings(root, None), \
        "an unset flag defers to the operator default"

    # After an export stores it, it reads back sticky off the nif root.
    pyn_props.write_export_settings(root, None, {'write_sf_materials': True})
    assert pyn_props.read_export_settings(root, None).get('write_sf_materials') is True, \
        "the flag persists on the nif root and reads back True"
    assert root.pyn_export.write_sf_materials is True, "stored on the typed export group"


@TT.category('STARFIELD')
def TEST_SF_MATERIALS_FLAG_STICKY_ON_EXPORT():
    """Root-level export settings must persist when the user exports with only the SHAPE
    selected, not the nif root Empty.

    Regression: _discover_settings walks up the parent chain to find the nif root when reading
    sticky settings, but set_objects only assigned self.root_object if a pynRoot was directly in
    the selection. Exporting a selected mesh therefore left root_object None, and
    write_export_settings silently skipped every root-anchored field -- so 'export materials'
    (and the other root options) read back sticky but never wrote back."""
    import os
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MATERIALS_FLAG_STICKY_ON_EXPORT\meshes\cube.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    root = bpy.data.objects.new("StickyExportRoot", None)
    bpy.context.scene.collection.objects.link(root)
    root['pynRoot'] = True
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    cube.name = "StickyCube"
    cube.parent = root

    assert not root.pyn_export.is_property_set('write_sf_materials'), "starts unset"

    # Select ONLY the shape -- the root Empty stays unselected, as when a user clicks the mesh.
    # intuit_defaults=False mirrors what invoke() does for a dialog-driven export: these
    # settings are the user's authoritative choice, so they persist.
    BD.ObjectSelect([cube], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF",
                                 write_sf_materials=True, intuit_defaults=False)

    assert root.pyn_export.write_sf_materials is True, \
        "the flag persisted onto the nif root even though only the shape was selected"


@TT.category('STARFIELD', 'SHADER')
def TEST_SF_MAT_EXPORT_PRESERVES_EXISTING():
    """Exporting materials over an existing .mat preserves what PyNifly doesn't model.

    write_sf_materials regenerated the .mat from the shader graph, dropping vanilla skin's
    ParamBool / MaterialParamFloat / TextureReplacement components and most of its UVStreams.
    That destroyed Bad Dog's hand-built Lykaios material on a routine re-export and broke the
    head in the CK. The export now patches the material it's about to overwrite.
    """
    import json
    import shutil
    testfile = TTB.test_file(r"tests\SF\meshes\malehead.nif")
    # test_file() deletes what it's given when it's under tests/Out -- so only ever hand it the
    # FILE, and derive the directory. Passing the directory raises WinError 5 on the second run.
    outfile = TTB.test_file(
        r"tests\Out\TEST_SF_MAT_EXPORT_PRESERVES_EXISTING\meshes\malehead.nif", output=True)
    outdir = os.path.dirname(os.path.dirname(outfile))
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    # Put the rich vanilla material where the export will write, as the user's existing file.
    src_mat = TTB.test_file(r"tests\SF\materials\Actors\Human\Faces\male_default.mat")
    dst_mat = os.path.join(outdir, "materials", "Actors", "Human", "Faces", "male_default.mat")
    os.makedirs(os.path.dirname(dst_mat), exist_ok=True)
    shutil.copyfile(src_mat, dst_mat)

    def census(path):
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
        c = {}
        for o in doc.get('Objects', []):
            for comp in o.get('Components', []):
                t = comp.get('Type', '').replace('BSMaterial::', '')
                c[t] = c.get(t, 0) + 1
        return c, len(doc.get('Objects', []))

    before, nobj_before = census(dst_mat)
    assert TT.is_eq(before.get('ParamBool'), 18, "the existing material is the rich vanilla one")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    BD.ObjectSelect([o for o in bpy.data.objects], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF",
                                 write_sf_materials=True, intuit_defaults=False)

    assert os.path.exists(dst_mat), "the material was written"
    after, nobj_after = census(dst_mat)
    assert TT.is_eq(nobj_after, nobj_before, "object count preserved")
    for ctype in ('ParamBool', 'MaterialParamFloat', 'TextureReplacement', 'UVStreamID'):
        assert TT.is_eq(after.get(ctype), before.get(ctype),
                        f"{ctype} survived the re-export")


@TT.category('STARFIELD')
def TEST_SF_MATERIALS_FLAG_STICKY_NO_ROOT():
    """Root-level export settings persist even when the scene has NO pynRoot at all.

    Regression: find_settings_root walks the parent chain for a 'pynRoot' marker and returns
    None if there isn't one, and write_export_settings skips every root-anchored field when the
    anchor is None -- silently. A head modelled in Blender rather than imported from a nif has
    no root Empty, so 'export materials' could never become sticky for it no matter how many
    times the user ticked the box. (Such an export writes a nif whose root is named
    'Scene Root', the no-root-object fallback -- the tell.)
    """
    import os
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MATERIALS_FLAG_STICKY_NO_ROOT\meshes\cube.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    # A shape authored from scratch: no root Empty, nothing carrying 'pynRoot'.
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    cube.name = "NoRootCube"
    assert not any('pynRoot' in o for o in bpy.data.objects), "scene has no nif root"

    assert not cube.pyn_export.is_property_set('write_sf_materials'), "starts unset"

    BD.ObjectSelect([cube], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF",
                                 write_sf_materials=True, intuit_defaults=False)

    from io_scene_nifly.nif import pyn_props
    anchor = pyn_props.find_settings_root(cube)
    assert anchor is not None, "an anchor is resolved even with no pynRoot in the scene"
    assert TT.is_eq(anchor.name, cube.name, "falls back to the shape's topmost ancestor")
    assert anchor.pyn_export.write_sf_materials is True, \
        "the flag persisted with no nif root to anchor it"

    # And it reads back, which is what 'sticky' means to the user.
    assert pyn_props.read_export_settings(anchor, None).get('write_sf_materials') is True, \
        "reads back sticky on the next export"


def _crowd_head_with_markers():
    """Import vanilla's male crowd head af_md1; return (LOD0 object, its armature, the
    BoneTranslations Empty, {bone: marker})."""
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'male',
                            'crowd_head_af_md1.nif')
    bpy.ops.import_scene.pynifly(filepath=testfile)
    lod0 = bpy.data.objects["crowd_head_af_md1:0:LOD0"]
    arma = next(m.object for m in lod0.modifiers if m.type == 'ARMATURE')
    block = bpy.data.objects.get("BoneTranslations:BoneTrn")
    markers = {c.name.split(':', 1)[1]: c for c in block.children} if block else {}
    return lod0, arma, block, markers


def _bone_translations(nif_path):
    nif = pyn.NifFile(nif_path)
    bts = [e for e in nif.rootNode.extra_data() if e.blockname == 'BoneTranslations']
    return {b.name: dict(b.translations) for b in bts}


VANILLA_AF_MD1_EYES = {'L_Eye': (0.0316, 0.0788, 0.0323), 'R_Eye': (0.0326, 0.0805, -0.0312)}


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_BONETRANS_IMPORT():
    """A crowd head's BoneTranslations imports as an Empty, 'BoneTranslations:BoneTrn', with a
    marker per entry where that eye bone sits: C_Head moved by the entry. For a vanilla head the
    block equals the binds, so each marker lands on the armature's own eye bone."""
    lod0, arma, block, markers = _crowd_head_with_markers()
    assert TT.is_true(block is not None, "the block imports as an Empty")
    assert TT.is_true('pynRoot' in block.parent, "it hangs off the nif root")
    assert TT.is_eq(sorted(markers), ['L_Eye', 'R_Eye'], "one marker per entry")
    for nif_bone, marker in markers.items():
        bone = next(b for b in arma.data.bones if b.name in (nif_bone, 'Eye.' + nif_bone[0]))
        want = arma.matrix_world @ bone.head_local
        got = marker.matrix_world.translation
        assert TT.is_true((got - want).length < 0.01,
                          f"{nif_bone} marker at the eye bone ({got[:]} vs {want[:]})")


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_BONETRANS_ROUNDTRIP():
    """Export writes BoneTranslations from the Empty, into the plain nif and the facebones
    companion alike (every vanilla companion carries it too), measured against the export
    armature's C_Head. Moving a marker moves the value: up 1 cm is +0.01 on C_Head's x axis,
    which points up."""
    outfile = TTB.test_file(r"tests\Out\TEST_SF_BONETRANS_ROUNDTRIP\meshes\crowdhead.nif",
                            output=True)
    outfile_fb = TTB.test_file(
        r"tests\Out\TEST_SF_BONETRANS_ROUNDTRIP\meshes\crowdhead_faceBones.nif", output=True)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    lod0, arma, block, markers = _crowd_head_with_markers()
    arma.pyn_facebones = True             # a crowd head: the companion is a copy of the nif

    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    for path in (outfile, outfile_fb):
        bt = _bone_translations(path)
        assert TT.is_eq(list(bt), ['BoneTrn'], f"{os.path.basename(path)} carries BoneTrn")
        for bone, want in VANILLA_AF_MD1_EYES.items():
            got = bt['BoneTrn'][bone]
            assert TT.is_true(all(abs(a - w) < 0.0001 for a, w in zip(got, want)),
                              f"{os.path.basename(path)} {bone} = {got}, vanilla {want}")

    # Drag the left marker up 1 cm (in game units, HAVOC_SCALE_FACTOR per metre).
    from io_scene_nifly.pyn.nifconstants import HAVOC_SCALE_FACTOR
    m = markers['L_Eye'].matrix_world.copy()
    m.translation.z += 0.01 * HAVOC_SCALE_FACTOR
    markers['L_Eye'].matrix_world = m
    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)
    got = _bone_translations(outfile)['BoneTrn']['L_Eye']
    want = VANILLA_AF_MD1_EYES['L_Eye']
    assert TT.is_true(abs(got[0] - (want[0] + 0.01)) < 0.0002
                      and abs(got[1] - want[1]) < 0.0002 and abs(got[2] - want[2]) < 0.0002,
                      f"moving the marker up 1 cm moves L_Eye along C_Head's x: {got}")


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_BONETRANS_NONE():
    """No Empty, no block: export never makes BoneTranslations up."""
    outfile = TTB.test_file(r"tests\Out\TEST_SF_BONETRANS_NONE.nif", output=True)
    lod0, arma, block, markers = _crowd_head_with_markers()
    for o in list(markers.values()) + [block]:
        bpy.data.objects.remove(o)
    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)
    assert TT.is_eq(_bone_translations(outfile), {}, "no BoneTranslations written")


def _face_rig(name, parent=None):
    """An armature of six faceBone_* bones -- enough for the name test to call it a face rig."""
    data = bpy.data.armatures.new(name + "Data")
    arma = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(arma)
    arma.parent = parent
    bpy.context.view_layer.objects.active = arma
    bpy.ops.object.mode_set(mode='EDIT')
    for i, bn in enumerate(['faceBone_C_Chin', 'faceBone_L_Cheek', 'faceBone_R_Cheek',
                            'faceBone_L_EarMaster', 'faceBone_R_EarMaster',
                            'faceBone_C_NoseRidge']):
        b = data.edit_bones.new(bn)
        b.head = (i * 0.1, 0, 0)
        b.tail = (i * 0.1, 0, 1)
    bpy.ops.object.mode_set(mode='OBJECT')
    return arma


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_FACEBONES_FLAG_CROWD():
    """An armature marked as the facebones armature wins over one only the bone names point to,
    and a marked armature with no faceBone_* bones writes the companion the way vanilla crowd
    heads ship it: the same nif again, LOD0 only, on the same .mesh.

    The fox crowd head came out invisible because its mesh also carried the chargen face rig:
    export found that rig by its bone names and skinned the companion to 46 bones a crowd
    actor's skeleton doesn't have. The game draws the head from the companion."""
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'male',
                            'crowd_head_af_md1.nif')
    outfile = TTB.test_file(r"tests\Out\TEST_SF_FACEBONES_FLAG_CROWD\meshes\crowdhead.nif",
                            output=True)
    outfile_fb = TTB.test_file(
        r"tests\Out\TEST_SF_FACEBONES_FLAG_CROWD\meshes\crowdhead_faceBones.nif", output=True)
    outdir = os.path.dirname(outfile)
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    lod0 = bpy.data.objects["crowd_head_af_md1:0:LOD0"]
    crowd_arma = next(m.object for m in lod0.modifiers if m.type == 'ARMATURE')
    crowd_arma.pyn_facebones = True
    decoy = _face_rig("ChargenFaceRig", parent=crowd_arma.parent)
    lod0.modifiers.new("FaceRig", 'ARMATURE').object = decoy

    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    plain = pyn.NifFile(outfile).shapes[0]
    assert TT.is_true(os.path.exists(outfile_fb), "the companion is written")
    fb = pyn.NifFile(outfile_fb).shapes[0]
    assert TT.is_eq(fb.mesh_paths(), plain.mesh_paths()[:1],
                    "the companion is LOD0 only, on the plain nif's own .mesh")
    assert TT.is_eq(list(fb.bone_names), list(plain.bone_names),
                    "the companion is skinned like the plain nif, not to the decoy face rig")
    fb_meshes = [f for _, _, fs in os.walk(os.path.join(os.path.dirname(outdir), 'geometries'))
                 for f in fs if f.endswith('_fb.mesh')]
    assert TT.is_eq(fb_meshes, [], "no separate facebones .mesh is written")


@TT.category('STARFIELD')
def TEST_SF_FILE_KEY_MESHES():
    """Each '_'-prefixed shape key writes its own nif AND its own .mesh files.

    The fox crowd head was exported with _Thin/_average/_Overweight keys for the three body types:
    three nifs came out, all pointing at one .mesh, which each wrote over the last -- every body
    type got the last one's geometry. The key goes on the .mesh name ('FSF\\Head_thin'); a name
    with no room for it under the 46-character cap gets a hash of name + key instead. A crowd
    head's companion is a copy of its own key's nif, on that key's .mesh."""
    from pyn.sf_meshpath import MESH_NAME_MAX
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'male',
                            'crowd_head_af_md1.nif')
    outfile = TTB.test_file(r"tests\Out\TEST_SF_FILE_KEY_MESHES\meshes\crowdhead.nif")
    outdir = os.path.dirname(os.path.dirname(outfile))
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(os.path.dirname(outfile))
    bpy.ops.import_scene.pynifly(filepath=testfile)

    lods = [o for o in bpy.data.objects if o.type == 'MESH']
    for obj in lods:
        obj.shape_key_add(name='Basis')
        for i, key in enumerate(('_thin', '_overweight')):
            sk = obj.shape_key_add(name=key)
            for p in sk.data:
                p.co.x += 0.5 * (i + 1)
    lod0 = bpy.data.objects["crowd_head_af_md1:0:LOD0"]
    lod0.pyn_sf_geometry.mesh_path = 'FSF'
    crowd_arma = next(m.object for m in lod0.modifiers if m.type == 'ARMATURE')
    crowd_arma.pyn_facebones = True

    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    paths = {}
    for key in ('_thin', '_overweight'):
        nif = os.path.join(outdir, 'meshes', f'crowdhead{key}.nif')
        assert TT.is_true(os.path.exists(nif), f"wrote {nif}")
        paths[key] = pyn.NifFile(nif).shapes[0].mesh_paths()
        fb = pyn.NifFile(os.path.join(outdir, 'meshes', f'crowdhead{key}_faceBones.nif'))
        assert TT.is_eq(fb.shapes[0].mesh_paths(), paths[key][:1],
                        f"the {key} companion is on the {key} nif's own .mesh")
    assert TT.is_eq(paths['_thin'][0], 'FSF\\crowd_head_af_md1_0_LOD0_thin',
                    "an explicit folder gets the key on the shape's name")
    for slot, (thin, fat) in enumerate(zip(paths['_thin'], paths['_overweight'])):
        assert TT.is_true(thin != fat, f"slot {slot}: each key has its own .mesh ({thin})")
        for name in (thin, fat):
            assert TT.is_true(len(name) <= MESH_NAME_MAX, f"slot {slot}: {name} fits the cap")
            assert TT.is_true(os.path.exists(os.path.join(outdir, 'geometries', name + '.mesh')),
                              f"slot {slot}: {name}.mesh was written")
    thin0, fat0 = (open(os.path.join(outdir, 'geometries', paths[k][0] + '.mesh'), 'rb').read()
                   for k in ('_thin', '_overweight'))
    assert TT.is_true(thin0 != fat0, "the two .mesh files hold different geometry")


@TT.category('STARFIELD')
def TEST_SF_FILE_KEY_PLAIN():
    """A shape key named just '_' writes the plain nif -- no suffix -- from its own shape.

    With file keys, only keyed files are written, so the body types had to be _thin, _overweight
    and an invented _average. '_' gives vanilla's names directly: crowdhead.nif,
    crowdhead_thin.nif, crowdhead_overweight.nif, each on its own .mesh, the plain one named as
    if there were no keys."""
    import numpy as np
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'male',
                            'crowd_head_af_md1.nif')
    outfile = TTB.test_file(r"tests\Out\TEST_SF_FILE_KEY_PLAIN\meshes\crowdhead.nif")
    outdir = os.path.dirname(os.path.dirname(outfile))
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(os.path.dirname(outfile))
    bpy.ops.import_scene.pynifly(filepath=testfile)

    for obj in [o for o in bpy.data.objects if o.type == 'MESH']:
        obj.shape_key_add(name='Basis')
        for key, dx in (('_', 0.75), ('_thin', 0.25), ('_overweight', 1.25)):
            sk = obj.shape_key_add(name=key, from_mix=False)
            for p in sk.data:
                p.co.x += dx
    lod0 = bpy.data.objects["crowd_head_af_md1:0:LOD0"]
    lod0.pyn_sf_geometry.mesh_path = 'FSF'
    next(m.object for m in lod0.modifiers if m.type == 'ARMATURE').pyn_facebones = True

    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    meshdir = os.path.dirname(outfile)
    assert TT.is_eq(sorted(f for f in os.listdir(meshdir)
                           if f.endswith('.nif') and not f.lower().endswith('_facebones.nif')),
                    ['crowdhead.nif', 'crowdhead_overweight.nif', 'crowdhead_thin.nif'],
                    "the '_' key writes the plain nif, the others their suffixed ones")
    centres = {}
    for key, name in (('_', 'crowdhead'), ('_thin', 'crowdhead_thin'),
                      ('_overweight', 'crowdhead_overweight')):
        shape = pyn.NifFile(os.path.join(meshdir, name + '.nif')).shapes[0]
        mp = shape.mesh_paths()[0]
        if key == '_':
            assert TT.is_eq(mp, 'FSF\\crowd_head_af_md1_0_LOD0', "the plain nif's .mesh has no suffix")
        with open(os.path.join(outdir, 'geometries', mp + '.mesh'), 'rb') as f:
            shape.load_mesh(f.read(), 0)
        centres[key] = np.mean(np.array(shape.verts), axis=0)
    to_thin = centres['_'] - centres['_thin']
    span = centres['_overweight'] - centres['_thin']
    assert TT.is_true(np.dot(to_thin, span) > 0 and np.linalg.norm(to_thin) < np.linalg.norm(span),
                      f"the plain nif is the '_' shape, between thin and overweight: {centres}")


@TT.category('STARFIELD')
def TEST_SF_HIDDEN_NOT_EXPORTED():
    """A hidden object isn't exported, except a LOD slot hidden on import, which exports with its
    LOD0.

    Exporting a root took every child of a BSGeometry, hidden or not: a hidden old copy of the fox
    crowd head under the same parent went into the export, and the GUI export died putting it in
    edit mode ("mode_set.poll() Context missing active object"). The crowd head's LOD1+ are
    hidden on import and must still fill their slots."""
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'male',
                            'crowd_head_af_md1.nif')
    outfile = TTB.test_file(r"tests\Out\TEST_SF_HIDDEN_NOT_EXPORTED\meshes\crowdhead.nif",
                            output=True)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)
    lod0 = bpy.data.objects["crowd_head_af_md1:0:LOD0"]
    assert TT.is_true(any(o.hide_get() for o in lod0.parent.children),
                      "the further LODs are hidden on import")
    old = lod0.copy()
    old.data = lod0.data.copy()
    old.name = "crowd_head_old"
    bpy.context.scene.collection.objects.link(old)
    old.parent = lod0.parent
    old.hide_set(True)

    BD.ObjectSelect([o for o in bpy.data.objects if not o.hide_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    nif = pyn.NifFile(outfile)
    assert TT.is_eq([s.name for s in nif.shapes], ['crowd_head_af_md1:0'],
                    "the hidden copy isn't exported")
    assert TT.is_eq(len(nif.shapes[0].mesh_paths()), 4, "the hidden LODs still fill their slots")


@TT.category('STARFIELD')
def TEST_SF_HIDDEN_KINDS_NOT_EXPORTED():
    """Every way of hiding an object keeps it out of the export, not just the eye icon: disabled
    in viewports, in a hidden collection, in a collection excluded from the view layer. Blender
    can't put any of them in edit mode either."""
    testfile = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human_crowd', 'mesh', 'male',
                            'crowd_head_af_md1.nif')
    outfile = TTB.test_file(r"tests\Out\TEST_SF_HIDDEN_KINDS_NOT_EXPORTED\meshes\crowdhead.nif",
                            output=True)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)
    lod0 = bpy.data.objects["crowd_head_af_md1:0:LOD0"]

    def copy(name, coll):
        o = lod0.copy()
        o.data = lod0.data.copy()
        o.name = name
        coll.objects.link(o)
        o.parent = lod0.parent
        return o

    scene = bpy.context.scene
    copy("crowd_head_disabled", scene.collection).hide_viewport = True
    hidden_coll = bpy.data.collections.new("HiddenColl")
    scene.collection.children.link(hidden_coll)
    copy("crowd_head_hiddencoll", hidden_coll)
    hidden_coll.hide_viewport = True
    excluded_coll = bpy.data.collections.new("ExcludedColl")
    scene.collection.children.link(excluded_coll)
    copy("crowd_head_excluded", excluded_coll)
    bpy.context.view_layer.layer_collection.children["ExcludedColl"].exclude = True

    BD.ObjectSelect([o for o in bpy.data.objects if o.visible_get()], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SF', intuit_defaults=False)

    nif = pyn.NifFile(outfile)
    assert TT.is_eq([s.name for s in nif.shapes], ['crowd_head_af_md1:0'],
                    "no hidden copy is exported, however it's hidden")
    assert TT.is_eq(len(nif.shapes[0].mesh_paths()), 4, "the hidden LODs still fill their slots")


@TT.category('STARFIELD')
@TT.expect_errors(('Could not select',))
def TEST_OBJECTSELECT_REPORTS_FAILURE():
    """ObjectSelect says so when an object can't be selected. It used to swallow the failure, and
    the export died later on an unrelated-looking "mode_set.poll() Context missing active
    object"."""
    import logging
    seen = []

    class Grab(logging.Handler):
        def emit(self, record):
            seen.append((record.levelno, record.getMessage()))

    me = bpy.data.meshes.new("selmesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    shown = bpy.data.objects.new("SelShown", me)
    hidden = bpy.data.objects.new("SelHidden", me)
    disabled = bpy.data.objects.new("SelDisabled", me)
    for o in (shown, hidden, disabled):
        bpy.context.scene.collection.objects.link(o)
    hidden.hide_set(True)
    disabled.hide_viewport = True

    grab = Grab()
    logging.getLogger("pynifly").addHandler(grab)
    try:
        BD.ObjectSelect([shown])
        assert TT.is_eq(seen, [], "a visible object selects quietly")
        BD.ObjectSelect([hidden, disabled])
    finally:
        logging.getLogger("pynifly").removeHandler(grab)

    warned = [m for lv, m in seen if lv == logging.WARNING]
    assert TT.is_eq(len(warned), 2, f"one warning per object that couldn't be selected: {seen}")
    assert 'SelHidden' in warned[0] and 'hidden' in warned[0], warned[0]
    assert 'SelDisabled' in warned[1] and 'disabled' in warned[1], warned[1]


@TT.category('STARFIELD')
def TEST_SF_FACEBONES_FLAG_OFF():
    """An armature marked NOT facebones is an ordinary armature even though its bone names say
    otherwise: the shape is skinned to it in the plain nif, and no companion is written."""
    outfile = TTB.test_file(r"tests\Out\TEST_SF_FACEBONES_FLAG_OFF\meshes\head.nif", output=True)
    outfile_fb = outfile.replace("head.nif", "head_faceBones.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    if os.path.exists(outfile_fb):
        os.remove(outfile_fb)

    root = bpy.data.objects.new("HeadRoot", None)
    bpy.context.scene.collection.objects.link(root)
    root['pynRoot'] = True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6)
    head = bpy.context.object
    head.parent = root
    rig = _face_rig("FaceRig", parent=root)
    rig.pyn_facebones = False
    head.vertex_groups.new(name='faceBone_C_Chin').add(
        list(range(len(head.data.vertices))), 1.0, 'REPLACE')
    head.modifiers.new("Armature", 'ARMATURE').object = rig

    BD.ObjectSelect([root, head, rig], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", intuit_defaults=False)

    assert TT.is_true(os.path.exists(outfile), "wrote the plain nif")
    assert TT.is_eq(list(pyn.NifFile(outfile).shapes[0].bone_names), ['faceBone_C_Chin'],
                    "the plain nif is skinned to the armature")
    assert TT.is_true(not os.path.exists(outfile_fb), "no companion for an armature marked No")


@TT.category('STARFIELD')
def TEST_SF_FACEBONES_FLAG_IMPORT():
    """Importing a _facebones nif marks the armature it creates as the facebones armature;
    importing the plain nif leaves the flag unset, so the bone names decide."""
    folder = os.path.join(TT.SF_ASSETS, 'meshes', 'actors', 'human', 'characterassets', 'male')
    bpy.ops.import_scene.pynifly(filepath=os.path.join(folder, 'malehead_facebones.nif'))
    armas = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert TT.is_eq(len(armas), 1, "one armature")
    assert TT.is_true(armas[0].is_property_set('pyn_facebones') and armas[0].pyn_facebones,
                      "the _facebones import marks its armature")

    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=os.path.join(folder, 'malehead.nif'))
    arma = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    assert TT.is_true(not arma.is_property_set('pyn_facebones'), "the plain import leaves it unset")


@TT.category('STARFIELD')
def TEST_SF_FACEBONES_EXPORT():
    """Starfield head parts ship as a <name>.nif + <name>_faceBones.nif pair; the facebones
    variant is skinned to the faceBone_* rig and carries its OWN external .mesh.

    Regression: facebones export was gated to FO4/FO76, and is_facebones() only recognised
    FO4's 'skin_bone_' prefix -- so a correctly-rigged Starfield head silently exported
    without its companion file, and the game had no head geometry to build."""
    import os
    from io_scene_nifly import blender_defs as _BD

    assert _BD.is_facebones(['faceBone_C_Chin', 'faceBone_L_Cheek', 'faceBone_R_Cheek',
                             'faceBone_L_EarMaster', 'faceBone_R_EarMaster',
                             'faceBone_C_NoseRidge']), "SF faceBone_ prefix is recognised"
    assert not _BD.is_facebones(['C_Head', 'C_Neck1', 'C_Spine2']), "body bones are not facebones"

    outfile = TTB.test_file(r"tests\Out\TEST_SF_FACEBONES_EXPORT\meshes\sfhead.nif", output=True)
    outfile_fb = TTB.test_file(r"tests\Out\TEST_SF_FACEBONES_EXPORT\meshes\sfhead_faceBones.nif",
                               output=True)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    root = bpy.data.objects.new("SFHeadRoot", None)
    bpy.context.scene.collection.objects.link(root)
    root['pynRoot'] = True

    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6)
    head = bpy.context.object
    head.name = "SFHead"
    head.parent = root

    # Give it a material so both nifs of the pair exercise MaterialID generation -- vanilla's
    # head and head_facebones carry the same id, and a Blender-authored head has no imported
    # extra-data Empty to supply one.
    headmat = bpy.data.materials.new("SFHead.Mat")
    # Blender 4.x creates materials with Use Nodes off (node_tree is None); 5.x always
    # has a node tree. Set it explicitly so the test exercises the same path everywhere.
    headmat.use_nodes = True
    headmat['BSLSP_Shader_Name'] = r"Materials\Test\SFHead.mat"
    head.data.materials.append(headmat)

    fb_bones = ['faceBone_C_Chin', 'faceBone_L_Cheek', 'faceBone_R_Cheek',
                'faceBone_L_EarMaster', 'faceBone_R_EarMaster', 'faceBone_C_NoseRidge']
    arma_data = bpy.data.armatures.new("SFFaceBonesData")
    arma = bpy.data.objects.new("SFFaceBones", arma_data)
    bpy.context.scene.collection.objects.link(arma)
    arma.parent = root
    bpy.context.view_layer.objects.active = arma
    bpy.ops.object.mode_set(mode='EDIT')
    for i, bn in enumerate(fb_bones):
        b = arma_data.edit_bones.new(bn)
        b.head = (i * 0.1, 0, 0)
        b.tail = (i * 0.1, 0, 1)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Weight every vertex to one facebone so the shape is skinned to the facebones rig.
    vg = head.vertex_groups.new(name=fb_bones[0])
    vg.add(list(range(len(head.data.vertices))), 1.0, 'REPLACE')
    head.modifiers.new("Armature", 'ARMATURE').object = arma

    # A shape key, so the export writes morphs. Morphs belong to the head part, not to either
    # nif, so they must be written once -- not again by the facebones pass.
    head.shape_key_add(name="Basis")
    key = head.shape_key_add(name="Wildman_JawOpen")
    key.data[0].co.z += 0.5

    messages = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    cap = _Cap(level=logging.INFO)
    pyn_log = logging.getLogger("pynifly")
    pyn_log.addHandler(cap)
    try:
        BD.ObjectSelect([root, head, arma], active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", intuit_defaults=False)
    finally:
        pyn_log.removeHandler(cap)

    morph_writes = [m for m in messages if m.startswith("Wrote Starfield morph")]
    assert TT.is_neq(morph_writes, [], "the shape key was written as a morph")
    assert TT.is_eq(len(morph_writes), len(set(morph_writes)),
                    f"each morph.dat written once, not again for the facebones nif: {morph_writes}")

    assert os.path.exists(outfile), "wrote the base nif"
    assert os.path.exists(outfile_fb), f"wrote the facebones companion nif at {outfile_fb}"

    nif_fb = pyn.NifFile(outfile_fb)
    assert len(nif_fb.shapes) == 1, "facebones nif has the shape"
    fb_shape = nif_fb.shapes[0]
    assert [b for b in fb_shape.bone_names if b.startswith('faceBone_')], \
        f"facebones nif is skinned to faceBone_* bones; got {fb_shape.bone_names}"

    # The two nifs must reference DIFFERENT external .mesh files -- vanilla does, and sharing
    # one means the facebones skin overwrites the base geometry's .mesh on disk.
    base_shape = pyn.NifFile(outfile).shapes[0]
    base_mesh = base_shape.mesh_paths()[0]
    fb_mesh = fb_shape.mesh_paths()[0]
    assert base_mesh != fb_mesh, \
        f"base and facebones nifs reference distinct .mesh paths (both were {base_mesh})"

    # Both halves of the pair carry MaterialID, generated from the material path. CRC of
    # 'Materials\Test\SFHead.mat'; vanilla gives its head and head_facebones the same id.
    for label, s in (("base", base_shape), ("facebones", fb_shape)):
        ids = [e.integer_data for e in s.extra_data() if e.name == 'MaterialID']
        assert TT.is_eq(len(ids), 1, f"{label} nif has exactly one MaterialID")
        assert TT.is_eq(ids[0], 2441678231, f"{label} nif MaterialID value")

    geodir = os.path.join(os.path.dirname(os.path.dirname(outfile)), "geometries")
    written = []
    for r, _d, files in os.walk(geodir):
        written += [f for f in files if f.endswith(".mesh")]
    assert len(written) >= 2, f"wrote a separate .mesh for each nif; found {written}"


@TT.category('STARFIELD')
@TT.expect_errors(('Could not find SF texture',))
def TEST_SF_MAT_WRITTEN_ONCE():
    """Starfield: one export writes each loose .mat once, however many nifs use it.

    A head with '_', '_thin' and '_overweight' file keys writes three nifs on one material; it was
    written three times, once per nif."""
    import logging
    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MAT_WRITTEN_ONCE\meshes\body.nif")
    outdir = os.path.dirname(os.path.dirname(outfile))
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(os.path.dirname(outfile))

    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = TTB.find_shape("Naked_F:0:LOD0")
    body.shape_key_add(name='Basis', from_mix=False)
    for key in ('_', '_thin', '_overweight'):
        body.shape_key_add(name=key, from_mix=False)

    class Count(logging.Handler):
        def __init__(self):
            super().__init__(logging.INFO)
            self.mats = []
        def emit(self, record):
            if record.getMessage().startswith('Wrote loose .mat'):
                self.mats.append(record.getMessage())
    counter = Count()
    logging.getLogger('pynifly').addHandler(counter)
    try:
        BD.ObjectSelect(list(bpy.context.scene.objects))
        bpy.context.view_layer.objects.active = body
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", write_sf_materials=True)
    finally:
        logging.getLogger('pynifly').removeHandler(counter)

    meshdir = os.path.dirname(outfile)
    assert TT.is_eq(sorted(f for f in os.listdir(meshdir) if f.endswith('.nif')),
                    ['body.nif', 'body_overweight.nif', 'body_thin.nif'], "three nifs written")
    assert TT.is_eq(len(counter.mats), 1, f"the shared material written once: {counter.mats}")


@TT.category('STARFIELD')
@TT.expect_errors(('Could not find SF texture',))
def TEST_SF_EXPORT():
    """Starfield round-trip: import a BSGeometry body, export it (NIF + external .mesh),
    re-import the result and confirm geometry, bones, and weights survive.

    The re-import warns that the material is missing -- the exported nif's Out/ tree has no
    materials/ sibling -- which is expected and whitelisted; the geometry/skin is the point.
    """
    import os
    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SF_EXPORT\meshes\naked_f.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = TTB.find_shape("Naked_F:0:LOD0")
    assert body is not None, "Imported the LOD0 body mesh"
    v_in = len(body.data.vertices)
    p_in = len(body.data.polygons)
    vg_in = len(body.vertex_groups)

    # Export by selecting the WHOLE imported hierarchy (root Empty + BSGeometry container Empty +
    # mesh + armature) -- the natural user action. The BSGeometry container Empty must NOT be
    # emitted as a NiNode (it's represented by the shape block); routing it through export_node
    # crashes on add_block(NiShape). Selecting only the leaf mesh dodged that path.
    BD.ObjectSelect(list(bpy.context.scene.objects))
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", write_sf_materials=True)

    # The external .mesh must have been written into a geometries/ tree beside meshes/.
    import os
    geodir = os.path.join(os.path.dirname(os.path.dirname(outfile)), "geometries")
    meshes_written = []
    for root, _dirs, files in os.walk(geodir):
        meshes_written += [os.path.join(root, f) for f in files if f.endswith(".mesh")]
    assert meshes_written, f"Wrote an external .mesh under {geodir}"

    # Weights-per-vertex is not capped at 4: this vanilla body uses 6 influences/vertex, and the
    # export must preserve that (Skyrim/FO4 trim to 4; Starfield allows more). Read it from the
    # written .mesh header (version, index count+indices, scale, then weightsPerVertex).
    import struct
    md = open(meshes_written[0], 'rb').read()
    o = 4
    o += 4 + struct.unpack_from('<I', md, o)[0] * 2
    o += 4
    wpv = struct.unpack_from('<I', md, o)[0]
    assert wpv > 4, f"weightsPerVertex preserved, not capped at 4: {wpv}"

    # A loose .mat was recovered from the body's shader graph and written to the output tree
    # (materials/ sibling of meshes/), and it re-parses.
    from pyn.sf_materials import parse_mat
    matdir = os.path.join(os.path.dirname(os.path.dirname(outfile)), "materials")
    mats_written = []
    for root, _d, files in os.walk(matdir):
        mats_written += [os.path.join(root, f) for f in files if f.endswith(".mat")]
    assert mats_written, f"Wrote a loose .mat under {matdir}"
    with open(mats_written[0], encoding='utf-8') as f:
        remat = parse_mat(f.read())
    assert remat is not None and remat['layers'], "written .mat re-parses with a layer"

    # Re-import the exported nif (resolves the .mesh from the geometries/ sibling). Deselect
    # first so it imports as a fresh object, not a shape key on the active mesh.
    BD.ObjectSelect([], active=None)
    bpy.ops.import_scene.pynifly(filepath=outfile)
    # Two imports now exist; grab the most-recently-added matching body mesh.
    bodies = [o for o in bpy.data.objects
              if o.type == 'MESH' and o.name.startswith("Naked_F:0:LOD0")]
    assert len(bodies) >= 2, f"Re-imported the body ({[b.name for b in bodies]})"
    body2 = bodies[-1]

    assert len(body2.data.vertices) == v_in, \
        f"Vertex count round-trips: {len(body2.data.vertices)} vs {v_in}"
    assert len(body2.data.polygons) == p_in, \
        f"Polygon count round-trips: {len(body2.data.polygons)} vs {p_in}"
    assert len(body2.vertex_groups) == vg_in, \
        f"Bone vertex groups round-trip: {len(body2.vertex_groups)} vs {vg_in}"
    assert 'Thigh.L' in body2.vertex_groups, "Bone naming survives (Thigh.L)"
    arma_mod = next((m for m in body2.modifiers if m.type == 'ARMATURE'), None)
    assert arma_mod and arma_mod.object, "Re-imported body is bound to an armature"


@TT.category('STARFIELD')
def TEST_SF_MESH_NAME_SANITIZE():
    """Starfield export: a shape with no recorded meshName (freshly authored, not round-tripped
    from an SF nif) generates its external .mesh path. Starfield block names carry a ':' (e.g.
    'Head:0'), which is illegal in a Windows filename and silently redirects the .mesh write into
    an NTFS alternate data stream -- so the geometry loads nowhere and the head is invisible
    in-game/CK. The generated name must (a) be a legal path and (b) be recorded back onto the
    object's SF geometry props (which didn't exist because the shape wasn't imported from SF), so
    it's pinned and a later rename can't move the .mesh.

    A generated name is a vanilla-shaped <20hex>\\<20hex> and so can't carry an illegal character;
    the sanitizer still guards the DERIVED filename, the case where the author supplies a directory
    and the name comes from the object."""
    import os
    # Unit-level: the sanitizer strips the ':index' illegal char and Blender's '.001' dedup
    # suffix, and never yields an empty component.
    from io_scene_nifly.nif.sf_geometry import sanitize_mesh_component, resolve_mesh_name
    assert sanitize_mesh_component("MaleHead:0") == "MaleHead_0", "colon sanitized"
    assert sanitize_mesh_component("MaleHead.001") == "MaleHead", "Blender .001 suffix stripped"
    assert sanitize_mesh_component("Head:0.002") == "Head_0", "suffix + colon together"
    assert sanitize_mesh_component(":::") == "___", "never empty"
    # ...and it is what guards the derived-filename path, where the object name reaches the disk.
    assert resolve_mesh_name("FSF", "MaleHead:0", r"C:\x.blend") == r"FSF\MaleHead_0", \
        "a directory-form path sanitizes the object name it derives the filename from"

    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MESH_NAME_SANITIZE\meshes\naked_f.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = TTB.find_shape("Naked_F:0:LOD0")
    assert body is not None, "Imported the LOD0 body mesh"

    # Simulate a freshly-authored shape: clear the recorded meshName so export must autogen
    # from the object's block name (which contains the illegal ':').
    body.pyn_sf_geometry.mesh_path = ''

    BD.ObjectSelect(list(bpy.context.scene.objects))
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF")

    # (a) The generated meshName must be a legal path -- no characters illegal in a Windows
    # filename ('\' is the legitimate path separator, so it's excluded from the check) -- and
    # vanilla-shaped, which is what keeps it under the 46-character cap even with '_fb'.
    from pyn.pynifly import NifFile
    from pyn.sf_meshpath import MESH_NAME_MAX
    nif = NifFile(outfile)
    mp = nif.shapes[0].mesh_path(0)
    assert not any(c in mp for c in '<>:"|?*'), f"Generated meshName is a legal path: {mp!r}"
    assert len(mp) == 41 and mp.count('\\') == 1, f"vanilla-shaped <20hex>\\<20hex>: {mp!r}"
    assert len(mp) + len('_fb') <= MESH_NAME_MAX, "leaves room for the facebones suffix"

    # ...and the .mesh was written as a REAL loose file (not an alternate data stream), non-empty.
    from io_scene_nifly.nif.sf_geometry import resolve_mesh_output_path
    meshpath = resolve_mesh_output_path(outfile, mp)
    assert os.path.isfile(meshpath) and os.path.getsize(meshpath) > 0, \
        f"External .mesh written as a real loose file: {meshpath}"

    # (b) The SF geometry props were created/recorded on the object with the generated meshName.
    assert body.pyn_sf_geometry.mesh_path == mp, \
        f"Generated meshName recorded on the object's SF props: {body.pyn_sf_geometry.mesh_path!r}"


@TT.category('STARFIELD')
def TEST_SF_MORPH():
    """Starfield round-trip: apply a vanilla morph.dat to an imported body as shape keys,
    export it back, and confirm the deltas survive.

    The vanilla chargen body morph.dat (Overweight/Thin/Strong) is authored against the same
    6616-vertex body, in the same vertex order the importer preserves -- so applying it produces
    correct shape keys and re-exporting reproduces the original per-vertex deltas (positions only).
    """
    import os
    from pyn.sf_morph import MorphFile

    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    morphfile = TTB.test_file(r"tests\SF\morphs\female_chargen_body_morph.dat")
    outdat = TTB.test_file(r"tests\Out\TEST_SF_MORPH\body_morph.dat")
    os.makedirs(os.path.dirname(outdat), exist_ok=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = TTB.find_shape("Naked_F:0:LOD0")
    assert body is not None, "Imported the LOD0 body mesh"
    assert len(body.data.vertices) == 6616, f"Body vertex count: {len(body.data.vertices)}"

    # Import the morph.dat as shape keys onto the active body.
    BD.ObjectSelect([body])
    bpy.context.view_layer.objects.active = body
    bpy.ops.import_scene.pyniflysfmorph(filepath=morphfile)

    kb = body.data.shape_keys.key_blocks
    assert "Basis" in kb, "Basis shape key created"
    for name in ("Overweight", "Thin", "Strong"):
        assert name in kb, f"Shape key {name!r} created"

    # Overweight moves nearly the whole body; vtx0's delta matches the known vanilla value.
    basis0 = kb["Basis"].data[0].co
    ow0 = kb["Overweight"].data[0].co
    d0 = (ow0[0] - basis0[0], ow0[1] - basis0[1], ow0[2] - basis0[2])
    assert abs(d0[0] - 0.5039) < 0.02 and abs(d0[1] - 0.8242) < 0.02 and abs(d0[2] - 1.0377) < 0.02, \
        f"Overweight vtx0 delta matches vanilla: {tuple(round(c, 3) for c in d0)}"

    # Import recorded the source path on pyn_sf_morph.chargen_path (round-trip default); redirect
    # to the Out dir so this test doesn't overwrite its own vanilla fixture. Body morphs are all
    # chargen (no expression AUs), so they write to the chargen path.
    body.pyn_sf_morph.chargen_path = outdat
    body.pyn_sf_morph.performance_path = ""

    # Export back to a morph.dat and re-read it; per-vertex deltas match the original vanilla file
    # (same vertex indexing), confirming the full import->shape-key->export chain round-trips.
    bpy.ops.export_scene.pyniflysfmorph(filepath=outdat)
    assert os.path.exists(outdat), "Exported a morph.dat"

    original = MorphFile.from_file(morphfile).key_deltas()
    exported = MorphFile.from_file(outdat).key_deltas()
    maxerr = 0.0
    for name in ("Overweight", "Thin", "Strong"):
        assert set(original[name]) == set(exported[name]), \
            f"{name}: same moved-vertex set ({len(original[name])} vs {len(exported[name])})"
        for vi, a in original[name].items():
            for ca, cb in zip(a, exported[name][vi]):
                maxerr = max(maxerr, abs(ca - cb))
    assert maxerr < 0.02, f"Exported deltas match vanilla within precision: max err {maxerr}"


def _sf_shapes(names, mesh_paths):
    """Build a minimal Starfield export scene: a root Empty with one flat quad per name, each
    carrying the given pyn_sf_geometry.mesh_path. Returns (root, [objects])."""
    root = bpy.data.objects.new("SFPathRoot", None)
    bpy.context.scene.collection.objects.link(root)
    root['pynRoot'] = True
    objs = []
    for i, (nm, mp) in enumerate(zip(names, mesh_paths)):
        me = bpy.data.meshes.new(nm + "Mesh")
        me.from_pydata([(i, 0, 0), (i + 1, 0, 0), (i, 1, 0), (i + 1, 1, 0)], [], [(0, 1, 3, 2)])
        me.uv_layers.new()   # the nif exporter reads the active UV layer; from_pydata makes none
        me.update()
        o = bpy.data.objects.new(nm, me)
        bpy.context.scene.collection.objects.link(o)
        o.parent = root
        o.pyn_sf_geometry.mesh_path = mp
        objs.append(o)
    return root, objs


@TT.category('STARFIELD', 'GEOMETRY')
def TEST_SF_MESH_PATH_DIRECTORY():
    """Starfield export: a mesh_path holding just a DIRECTORY names the .mesh after the object.

    This is the split-a-shape workflow: model head/mouth/tongue as one object, split it into three,
    and each part needs its own external .mesh. With the directory form all three carry the same
    property value and still write three distinct files -- no per-object path editing. A value with
    a separator stays verbatim, which is what makes an imported shape write back to the .mesh it
    came from.
    """
    import os
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MESH_PATH_DIRECTORY\meshes\parts.nif", output=True)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    names = ["LykHead", "LykMouth", "LykTongue"]
    # Same stored value on every object -- exactly what a split leaves behind.
    root, objs = _sf_shapes(names, ["FSF"] * 3)

    BD.ObjectSelect([root] + objs, active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", intuit_defaults=False)

    nif = pyn.NifFile(outfile)
    got = sorted(s.mesh_path(0) for s in nif.shapes)
    assert got == [r"FSF\LykHead", r"FSF\LykMouth", r"FSF\LykTongue"], \
        f"each shape got its own .mesh path under the shared directory: {got}"

    # ...and three real files on disk, one per shape.
    geodir = os.path.join(os.path.dirname(os.path.dirname(outfile)), "geometries", "FSF")
    for nm in names:
        p = os.path.join(geodir, nm + ".mesh")
        assert os.path.isfile(p) and os.path.getsize(p) > 0, f"wrote {p}"

    # The stored property is untouched -- it's a directory, not a resolved path, so it keeps
    # working if the objects are renamed again.
    assert all(o.pyn_sf_geometry.mesh_path == "FSF" for o in objs), \
        "directory-form mesh_path is not rewritten to a resolved path on export"


@TT.category('STARFIELD', 'GEOMETRY')
@TT.expect_errors(("both export to .mesh path",))  # the collision warning is the point of the test
def TEST_SF_MESH_PATH_COLLISION():
    """Starfield export: two shapes resolving to one .mesh are suffixed, not silently merged.

    Generated names can't collide, but explicit ones can -- the same path typed on two shapes, or
    two objects that sanitize alike ('Head' and 'Head.001' both give 'Head'). Last-write-wins would
    produce a nif that loads and renders the wrong geometry, so the second shape is written to
    '<name>_1' and the export warns.
    """
    import os
    outfile = TTB.test_file(r"tests\Out\TEST_SF_MESH_PATH_COLLISION\meshes\dup.nif", output=True)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    # Both objects name the same explicit .mesh.
    root, objs = _sf_shapes(["DupA", "DupB"], [r"FSF\Shared", r"FSF\Shared"])

    BD.ObjectSelect([root] + objs, active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", intuit_defaults=False)

    nif = pyn.NifFile(outfile)
    got = sorted(s.mesh_path(0) for s in nif.shapes)
    assert got == [r"FSF\Shared", r"FSF\Shared_1"], \
        f"the second shape was suffixed rather than overwriting the first: {got}"

    geodir = os.path.join(os.path.dirname(os.path.dirname(outfile)), "geometries", "FSF")
    for nm in ("Shared.mesh", "Shared_1.mesh"):
        p = os.path.join(geodir, nm)
        assert os.path.isfile(p) and os.path.getsize(p) > 0, f"both .mesh files written: {p}"


@TT.category('STARFIELD')
def TEST_SF_MORPH_SHAPE_TOKEN_EXPORT():
    """Starfield: '{shape}' in a morph path resolves to the object's name on export.

    The .mesh answer (a directory, filename from the shape) doesn't transfer to morphs: the
    filename is always morph.dat and the shape name is an interior segment whose position varies
    by layout. So the token, which works for any layout. Both siblings must carry the substituted
    name -- the performance path is derived from the chargen one by swapping the tree segment, and
    substituting after that swap would leave a raw '{shape}' in one of them.
    """
    import os
    from pyn.sf_morph import MorphFile

    me = bpy.data.meshes.new("sftokenmesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    me.update()
    obj = bpy.data.objects.new("LykaiosMaleMouth", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    obj.shape_key_add(name="jawOpen").data[0].co.z += 1.0        # -> performance
    obj.shape_key_add(name="Overweight").data[1].co.x += 0.5     # -> chargen

    out = TTB.test_file(r"tests\Out\TEST_SF_MORPH_SHAPE_TOKEN\meshes\mouth.nif", output=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # Vanilla ordering: the chargen/performance segment sits BEFORE the part.
    obj.pyn_sf_morph.chargen_path = r"meshes\morphs\FSF\male\chargen\{shape}\morph.dat"
    obj.pyn_sf_morph.performance_path = ""

    BD.ObjectSelect([obj])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pyniflysfmorph(filepath=out)

    root = os.path.dirname(os.path.dirname(out))
    cp = os.path.join(root, "meshes", "morphs", "FSF", "male", "chargen",
                      "LykaiosMaleMouth", "morph.dat")
    pp = os.path.join(root, "meshes", "morphs", "FSF", "male", "performance",
                      "LykaiosMaleMouth", "morph.dat")
    assert os.path.isfile(cp), f"chargen morph landed at the substituted path: {cp}"
    assert os.path.isfile(pp), f"the swapped sibling carries the shape name too: {pp}"
    assert MorphFile.from_file(cp).morph_names == ["Overweight"], "chargen holds the slider"
    assert MorphFile.from_file(pp).morph_names == ["jawOpen"], "performance holds the action unit"

    # The token survives on the property -- it's a value the user set, so export must not
    # overwrite it with the resolved path or the next shape would inherit this one's name.
    assert "{shape}" in obj.pyn_sf_morph.chargen_path, \
        f"the token is not stomped by the write-back: {obj.pyn_sf_morph.chargen_path!r}"


@TT.category('STARFIELD')
def TEST_SF_MORPH_SKIP_HELPER_KEYS():
    """Starfield: shape keys starting with '*' or '_' never go into a morph.dat.

    '*' marks a working key (ear poses, eye placement) and '_' a file key; the .tri export
    already skipped both, the morph.dat export didn't (Ruff04 shipped *CanineEarBackR etc.)."""
    import os
    from pyn.sf_morph import MorphFile

    me = bpy.data.meshes.new("sfhelpermesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    me.update()
    obj = bpy.data.objects.new("RuffHelpers", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    obj.shape_key_add(name="jawOpen").data[0].co.z += 1.0        # -> performance
    obj.shape_key_add(name="Overweight").data[1].co.x += 0.5     # -> chargen
    obj.shape_key_add(name="*CanineEarBackR").data[2].co.y += 0.5
    obj.shape_key_add(name="_thin").data[3].co.x -= 0.5

    out = TTB.test_file(r"tests\Out\TEST_SF_MORPH_SKIP_HELPER_KEYS\meshes\ruff.nif", output=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    obj.pyn_sf_morph.chargen_path = r"meshes\morphs\FSF\chargen\Ruff\morph.dat"
    obj.pyn_sf_morph.performance_path = ""

    BD.ObjectSelect([obj])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pyniflysfmorph(filepath=out)

    root = os.path.dirname(os.path.dirname(out))
    cp = os.path.join(root, "meshes", "morphs", "FSF", "chargen", "Ruff", "morph.dat")
    pp = os.path.join(root, "meshes", "morphs", "FSF", "performance", "Ruff", "morph.dat")
    assert MorphFile.from_file(cp).morph_names == ["Overweight"], \
        f"helper keys left out of chargen: {MorphFile.from_file(cp).morph_names}"
    assert MorphFile.from_file(pp).morph_names == ["jawOpen"]


@TT.category('STARFIELD')
@TT.expect_errors(('no morph data',))
def TEST_SF_MORPH_EMPTY_NOT_WRITTEN():
    """Starfield: a morph group whose keys move no vertex isn't written. Its morph.dat would have
    keys but zero records, and the CK crashes on it ("invalid buffers" in MorphRenderPass; Ruff01's
    123 unfilled keys). One real key alongside empty ones is fine -- vanilla beards do that."""
    import os
    from pyn.sf_morph import MorphFile

    me = bpy.data.meshes.new("sfemptymesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    me.update()
    obj = bpy.data.objects.new("RuffEmpty", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    obj.shape_key_add(name="Overweight")                         # chargen, empty
    obj.shape_key_add(name="Thin")                               # chargen, empty
    obj.shape_key_add(name="jawOpen").data[0].co.z += 1.0        # performance, real
    obj.shape_key_add(name="lipPress")                           # performance, empty

    out = TTB.test_file(r"tests\Out\TEST_SF_MORPH_EMPTY_NOT_WRITTEN\meshes\ruff.nif", output=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    obj.pyn_sf_morph.chargen_path = r"meshes\morphs\FSF\chargen\Ruff\morph.dat"
    obj.pyn_sf_morph.performance_path = ""

    root = os.path.dirname(os.path.dirname(out))
    cp = os.path.join(root, "meshes", "morphs", "FSF", "chargen", "Ruff", "morph.dat")
    pp = os.path.join(root, "meshes", "morphs", "FSF", "performance", "Ruff", "morph.dat")
    if os.path.exists(cp):
        os.remove(cp)

    BD.ObjectSelect([obj])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pyniflysfmorph(filepath=out)

    assert not os.path.exists(cp), f"empty chargen morph written: {cp}"
    assert MorphFile.from_file(pp).morph_names == ["jawOpen", "lipPress"], \
        f"partly-empty performance morph: {MorphFile.from_file(pp).morph_names}"


@TT.category('STARFIELD')
@TT.expect_errors(('crowd morph',))
def TEST_SF_MORPH_CROWD_EXPORT():
    """Starfield: a head flagged Crowd writes only a performance morph.dat with vanilla's 11
    crowd keys, each L key carrying its R partner's movement; no chargen file."""
    import os
    from pyn.sf_morph import MorphFile

    me = bpy.data.meshes.new("sfcrowdmesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    me.update()
    obj = bpy.data.objects.new("CrowdHead", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis", from_mix=False)
    obj.shape_key_add(name="jawOpen", from_mix=False).data[0].co.z += 1.0
    obj.shape_key_add(name="browLowererL", from_mix=False).data[1].co.z -= 1.0
    obj.shape_key_add(name="browLowererR", from_mix=False).data[2].co.z -= 1.0
    obj.shape_key_add(name="lipFunnel", from_mix=False).data[3].co.x += 1.0      # not a crowd key
    obj.shape_key_add(name="Overweight", from_mix=False).data[3].co.y += 1.0     # chargen

    out = TTB.test_file(r"tests\Out\TEST_SF_MORPH_CROWD_EXPORT\meshes\crowd.nif", output=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    obj.pyn_sf_morph.chargen_path = ""
    obj.pyn_sf_morph.performance_path = r"meshes\morphs\FSF_Crowd\male\performance\morph.dat"
    obj.pyn_sf_morph.crowd = True

    BD.ObjectSelect([obj])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pyniflysfmorph(filepath=out)

    root = os.path.dirname(os.path.dirname(out))
    pp = os.path.join(root, "meshes", "morphs", "FSF_Crowd", "male", "performance", "morph.dat")
    cp = os.path.join(root, "meshes", "morphs", "FSF_Crowd", "male", "chargen", "morph.dat")
    assert os.path.isfile(pp), f"crowd morph written to the performance path: {pp}"
    assert not os.path.exists(cp), "no chargen morph for a crowd head"
    mf = MorphFile.from_file(pp)
    assert mf.morph_names == ["browLowererL", "jawOpen"], f"vanilla's order: {mf.morph_names}"
    brow = mf.key_deltas()["browLowererL"]
    assert set(brow) == {1, 2}, f"browLowererL moves both sides: {sorted(brow)}"


@TT.category('STARFIELD')
def TEST_SF_MORPH_DIR_PATH_EXPORT():
    """Starfield: morph paths given as folders (no morph.dat on the end) get morph.dat added.

    Without it the morph was written to a file named after the folder, which the MRPH record
    can't point at."""
    import os
    from pyn.sf_morph import MorphFile

    me = bpy.data.meshes.new("sfdirmesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    me.update()
    obj = bpy.data.objects.new("RuffDir", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    obj.shape_key_add(name="jawOpen").data[0].co.z += 1.0        # -> performance
    obj.shape_key_add(name="Overweight").data[1].co.x += 0.5     # -> chargen

    out = TTB.test_file(r"tests\Out\TEST_SF_MORPH_DIR_PATH_EXPORT\meshes\ruff.nif", output=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    obj.pyn_sf_morph.chargen_path = r"meshes\morphs\FSF\chargen\Ruff"
    obj.pyn_sf_morph.performance_path = "meshes\\morphs\\FSF\\performance\\Ruff\\"

    BD.ObjectSelect([obj])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pyniflysfmorph(filepath=out)

    root = os.path.dirname(os.path.dirname(out))
    cp = os.path.join(root, "meshes", "morphs", "FSF", "chargen", "Ruff", "morph.dat")
    pp = os.path.join(root, "meshes", "morphs", "FSF", "performance", "Ruff", "morph.dat")
    assert os.path.isfile(cp), f"chargen morph.dat added to the folder: {cp}"
    assert os.path.isfile(pp), f"performance morph.dat added to the folder: {pp}"
    assert MorphFile.from_file(cp).morph_names == ["Overweight"]
    assert MorphFile.from_file(pp).morph_names == ["jawOpen"]


@TT.category('STARFIELD')
def TEST_SF_MORPH_SPLIT():
    """Starfield: morph export splits shape keys into performance + chargen morph.dat files.

    Expression/action-unit keys (e.g. jawOpen) go to the performance/ file; chargen sliders (e.g.
    Overweight) go to the chargen/ file. The two output paths come from the object's pyn_sf_morph
    group.
    """
    import os
    from pyn.sf_morph import MorphFile

    me = bpy.data.meshes.new("sfsplitmesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    me.update()
    obj = bpy.data.objects.new("SFSplitHead", me)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    kj = obj.shape_key_add(name="jawOpen")       # -> performance
    kj.data[0].co.z += 1.0
    ko = obj.shape_key_add(name="Overweight")    # -> chargen
    ko.data[1].co.x += 0.5

    cp = TTB.test_file(r"tests\Out\TEST_SF_MORPH_SPLIT\chargen\head\morph.dat")
    pp = TTB.test_file(r"tests\Out\TEST_SF_MORPH_SPLIT\performance\head\morph.dat")
    for p in (cp, pp):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    obj.pyn_sf_morph.chargen_path = cp
    obj.pyn_sf_morph.performance_path = pp

    BD.ObjectSelect([obj])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pyniflysfmorph(filepath=cp)

    assert os.path.exists(cp), "Chargen morph.dat written"
    assert os.path.exists(pp), "Performance morph.dat written"
    cm = MorphFile.from_file(cp)
    pm = MorphFile.from_file(pp)
    assert cm.morph_names == ["Overweight"], f"Chargen file holds the slider: {cm.morph_names}"
    assert pm.morph_names == ["jawOpen"], f"Performance file holds the action unit: {pm.morph_names}"


@TT.category('STARFIELD')
def TEST_SF_MORPH_NIFEXPORT():
    """Starfield: exporting the nif writes the shape's morph.dat files, gated by write_tris.

    Morphs are written alongside the nif (anchored on the nif's output path). With no prior morph
    path on the shape, they default to meshes/morphs/<nifstem>/{chargen,performance}/morph.dat under
    the nif's meshes root. write_tris=False skips them entirely.
    """
    import os
    import shutil
    from pyn.sf_morph import MorphFile

    # Clean prior output so the write_tris-off assertion can't see stale files.
    for sub in ("TEST_SF_MORPH_NIFEXPORT", "TEST_SF_MORPH_NIFEXPORT_OFF"):
        d = os.path.dirname(TTB.test_file(os.path.join("tests", "Out", sub, "marker")))
        shutil.rmtree(d, ignore_errors=True)

    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = TTB.find_shape("Naked_F:0:LOD0")
    body.shape_key_add(name="Basis")
    kj = body.shape_key_add(name="jawOpen")     # -> performance
    kj.data[0].co.z += 1.0
    ko = body.shape_key_add(name="Overweight")  # -> chargen
    ko.data[1].co.x += 0.5

    def morph_paths(outnif):
        meshes = os.path.dirname(os.path.dirname(outnif))                 # .../meshes
        stem = os.path.splitext(os.path.basename(outnif))[0]
        return (os.path.join(meshes, "morphs", stem, "chargen", "morph.dat"),
                os.path.join(meshes, "morphs", stem, "performance", "morph.dat"))

    # Export with morphs ON (default): both files land under the nif's meshes/morphs tree.
    outnif = TTB.test_file(r"tests\Out\TEST_SF_MORPH_NIFEXPORT\meshes\FSF\FoxBody.nif")
    os.makedirs(os.path.dirname(outnif), exist_ok=True)
    BD.ObjectSelect(list(bpy.context.scene.objects))
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outnif, target_game="SF")
    cp, pp = morph_paths(outnif)
    assert os.path.exists(cp), f"chargen morph written on nif export: {cp}"
    assert os.path.exists(pp), f"performance morph written on nif export: {pp}"
    assert MorphFile.from_file(cp).morph_names == ["Overweight"], "chargen file has the slider"
    assert MorphFile.from_file(pp).morph_names == ["jawOpen"], "performance file has the AU"

    # Turn morphs off via the sticky setting on the nif root; re-export writes no morph files.
    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    root.pyn_export.write_tris = False
    outnif2 = TTB.test_file(r"tests\Out\TEST_SF_MORPH_NIFEXPORT_OFF\meshes\FSF\FoxBody.nif")
    os.makedirs(os.path.dirname(outnif2), exist_ok=True)
    bpy.ops.export_scene.pynifly(filepath=outnif2, target_game="SF")
    cp2, pp2 = morph_paths(outnif2)
    assert not os.path.exists(cp2) and not os.path.exists(pp2), "write_tris off skips morph export"


@TT.category('STARFIELD')
def TEST_SF_MORPH_MESH_MATCH():
    """SF morph.dat must be 1:1 with the exported .mesh's POST-SPLIT vertex set.

    The .mesh export splits verts at UV/normal seams (N -> N+k render verts); the morph must grow
    the same way (each split vertex reuses its source delta) or the game's ApplyChargenMorph fails
    on a vertex-count mismatch -- exactly what broke the Lykaios head facegen (Geometry[5558] vs
    Morph[5405]). Regression: SF morph export rebuilt from the RAW shape keys (Blender count) instead
    of the export's split morphdict, so any seam-splitting head desynced mesh vs morph."""
    import os
    import shutil
    from pyn.sf_morph import MorphFile

    d = os.path.dirname(TTB.test_file(os.path.join("tests", "Out", "TEST_SF_MORPH_MESH_MATCH", "m")))
    shutil.rmtree(d, ignore_errors=True)

    # Two tris sharing the diagonal (verts 0 & 2), with a UV seam down it so both shared verts
    # carry two UVs -> the .mesh export splits each (4 Blender verts -> 6 render verts). A chargen
    # shape key moves v0, whose split copy must inherit the same delta.
    me = bpy.data.meshes.new("SplitHead")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2), (0, 2, 3)])
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for i, uv in enumerate([(0, 0), (1, 0), (1, 1),          # face0 loops: v0,v1,v2
                            (0.5, 0), (0.5, 1), (0, 1)]):     # face1 loops: v0,v2,v3 (v0/v2 differ)
        uvl.data[i].uv = uv
    body = bpy.data.objects.new("SplitHead", me)
    bpy.context.scene.collection.objects.link(body)
    body["PYN_GAME"] = "SF"                    # so game discovery exports as Starfield (.mesh + morph.dat)
    blender_verts = len(me.vertices)          # 4
    body.shape_key_add(name="Basis")
    ko = body.shape_key_add(name="Overweight")   # -> chargen
    ko.data[0].co.x += 0.5                        # move v0 (splits) -> its render-copy must move too

    outnif = TTB.test_file(r"tests\Out\TEST_SF_MORPH_MESH_MATCH\meshes\FSF\SplitHead.nif")
    os.makedirs(os.path.dirname(outnif), exist_ok=True)
    BD.ObjectSelect([body])
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outnif, target_game="SF")

    cp = os.path.join(os.path.dirname(os.path.dirname(outnif)), "morphs", "SplitHead", "chargen", "morph.dat")
    assert os.path.exists(cp), f"chargen morph written: {cp}"
    morph_verts = MorphFile.from_file(cp).num_vertices

    # Re-import into a clean scene to read the exported .mesh's real (post-split) vertex count.
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.pynifly(filepath=outnif)
    mesh_verts = max(len(o.data.vertices) for o in bpy.data.objects if o.type == 'MESH')

    assert mesh_verts > blender_verts, \
        f"precondition: the mesh splits verts on export ({blender_verts} -> {mesh_verts})"
    assert morph_verts == mesh_verts, \
        f"morph matches the exported .mesh's split vertex count, not the raw Blender count " \
        f"(morph={morph_verts}, mesh={mesh_verts}, blender={blender_verts})"


@TT.category('STARFIELD')
def TEST_SF_MORPH_PANEL_SURFACES():
    """Exporting an author-created SF head surfaces its morph paths in the PyNifly panel.

    An object whose shape keys were built in Blender (not imported from a morph.dat) never
    got the pyn_sf_morph group's `_migrated` flag, so PYN_PT_block stayed hidden even though
    export wrote real morph.dat files -- the modder had nothing to inspect or edit. Export
    now records the resolved paths back on the group (relative-to-meshes, import's own
    representation) and marks it migrated, and must not stomp a path the user set."""
    import os

    testfile = TTB.test_file(r"tests\SF\meshes\naked_f.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    body = TTB.find_shape("Naked_F:0:LOD0")
    body.shape_key_add(name="Basis")
    kj = body.shape_key_add(name="jawOpen")     # -> performance
    kj.data[0].co.z += 1.0
    ko = body.shape_key_add(name="Overweight")  # -> chargen
    ko.data[1].co.x += 0.5

    # Author-created: the morph group exists (registered type-wide) but was never migrated,
    # so the panel wouldn't show it.
    assert not body.get('pyn_sf_morph_migrated'), \
        "precondition: an author-created head has no migrated morph group"

    outnif = TTB.test_file(r"tests\Out\TEST_SF_MORPH_PANEL_SURFACES\meshes\FSF\FoxBody.nif")
    os.makedirs(os.path.dirname(outnif), exist_ok=True)
    BD.ObjectSelect(list(bpy.context.scene.objects))
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outnif, target_game="SF")

    # The group is now migrated, so the panel polls visible with the head active.
    assert body.get('pyn_sf_morph_migrated'), "export marked the morph group migrated"
    assert pyn_props.PYN_PT_block.poll(bpy.context), "the PyNifly block panel now shows"

    # Both resolved paths are recorded relative-to-meshes (re-homeable), not absolute.
    cp = body.pyn_sf_morph.chargen_path
    pp = body.pyn_sf_morph.performance_path
    assert cp and not os.path.isabs(cp), f"chargen path recorded, relative-to-meshes: {cp!r}"
    assert pp and not os.path.isabs(pp), f"performance path recorded, relative-to-meshes: {pp!r}"
    assert cp.replace('\\', '/').startswith("meshes/morphs/"), f"chargen under meshes tree: {cp!r}"
    assert "chargen" in cp and "performance" in pp, "paths landed in the right sibling trees"

    # Idempotent: an explicit path the user set survives a re-export unchanged.
    body.pyn_sf_morph.chargen_path = r"meshes\morphs\Custom\chargen\morph.dat"
    outnif2 = TTB.test_file(r"tests\Out\TEST_SF_MORPH_PANEL_SURFACES2\meshes\FSF\FoxBody.nif")
    os.makedirs(os.path.dirname(outnif2), exist_ok=True)
    bpy.ops.export_scene.pynifly(filepath=outnif2, target_game="SF")
    assert body.pyn_sf_morph.chargen_path == r"meshes\morphs\Custom\chargen\morph.dat", \
        f"export didn't stomp the user's explicit path: {body.pyn_sf_morph.chargen_path!r}"


@TT.category('STARFIELD', 'ARMATURE')
@TT.expect_errors(("Unknown block type: bhkRagdollSystem", "bhkPhysicsSystem decode failed"))
def TEST_SF_SKELETON_EXTRA_BONES():
    """Bones a Starfield skeleton adds to the vanilla set import in place, at normal length.

    Starfield's skeleton nifs are in Havok metres. Vanilla bones take their rest from our
    reference skeleton, but an added bone (an extended skeleton's tail and ears) is read
    from the file, so it needs the unit conversion. Against the female skeleton the
    conversion used to decline -- its proportions differ from our male reference -- and the
    tail landed 70x too close to the origin. Converting it then stretched the bone 70x too.

    The fixture is vanilla's female skeleton.nif plus one bone, C_Tail_Root under C_Hips,
    at the local transform SF Extended Skeleton gives it.
    """
    from io_scene_nifly.pyn.nifconstants import HAVOC_SCALE_FACTOR
    testfile = TTB.test_file(r"tests\SF\skeleton_female_tailroot.nif")
    tail_metres = pyn.NifFile(testfile).nodes['C_Tail_Root'].global_transform.translation[:]

    bpy.ops.import_scene.pynifly(filepath=testfile, rename_bones=False)
    arma = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    tail = arma.data.bones['C_Tail_Root']
    spine = arma.data.bones['C_Spine']

    head = arma.matrix_world @ tail.head_local
    want = [v * HAVOC_SCALE_FACTOR for v in tail_metres]
    assert TT.is_equiv(head.z, want[2], "tail root sits at hip height, in game units", e=0.5)
    assert TT.is_equiv(head.y, want[1], "tail root sits behind the hips", e=0.5)
    assert TT.is_equiv(tail.length, spine.length, "the added bone is as long as a vanilla one",
                       e=0.01)

    # The pose gets the same unit conversion, and it must move the bones, not scale them:
    # a pose scale of 70 draws every octahedron 70x too big.
    worst = max(max(pb.matrix.to_scale()) for pb in arma.pose.bones)
    assert TT.is_equiv(worst, 1.0, "posed bones are unscaled", e=0.01)
    posed = arma.matrix_world @ arma.pose.bones['C_Tail_Root'].head
    assert TT.is_equiv(posed.z, want[2], "posed tail root sits at hip height", e=0.5)


def _uv_transfer():
    """scripts/uv_transfer.py, freshly loaded."""
    scripts = str(Path(__file__).resolve().parents[2] / 'scripts')
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import uv_transfer
    return importlib.reload(uv_transfer)


def _uv_transfer_rig():
    """The vanilla hands and left eye as two parts, and a target made by joining copies of them,
    the way a crowd head is made. The target's hand UVs are turned 90 degrees and halved into
    the lower-left quarter; its eye UVs are quartered into the upper right. Returns
    (target, hands, eye, n_hand_faces)."""
    import numpy as np
    bpy.ops.import_scene.pynifly(filepath=TTB.test_file(r"tests\SF\meshes\hands_3rd_f.nif"))
    hands = TTB.find_shape("Hands_3rd_F:0")
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None
    bpy.ops.import_scene.pynifly(filepath=TTB.test_file(r"tests\SF\meshes\lefteye.nif"))
    eye = TTB.find_shape("LeftEye:1")

    copies = []
    for o in (hands, eye):
        c = o.copy()
        c.data = o.data.copy()
        c.modifiers.clear()
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    n_hand = len(copies[0].data.polygons)
    BD.ObjectSelect(copies, active=True)
    bpy.ops.object.join()
    target = bpy.context.view_layer.objects.active
    target.name = "CrowdTarget"

    me = target.data
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2)
    hand_loops = me.polygons[n_hand].loop_start   # hand faces come first: theirs was active
    h = uv[:hand_loops] - 0.5
    uv[:hand_loops] = np.stack([-h[:, 1], h[:, 0]], axis=1) * 0.5 + 0.25
    uv[hand_loops:] = uv[hand_loops:] * 0.25 + 0.7
    me.uv_layers.active.data.foreach_set('uv', uv.ravel())
    return target, hands, eye, n_hand


@TT.category('STARFIELD', 'SHADER')
def TEST_UV_TRANSFER_MAP():
    """uv_transfer maps each triangle of a joined mesh to the part triangle it came from.

    A crowd head is several parts (head, eyes, mouth, hands) joined into one mesh with one
    texture, its UVs repacked. The map ties each of its triangles to the part triangle it is a
    copy of, so the parts' textures can be copied in triangle by triangle. Faces deleted from
    the joined mesh are fine; a face that has moved off its part is an error, named so it can
    be fixed."""
    import bmesh
    import numpy as np
    U = _uv_transfer()
    target, hands, eye, n_hand = _uv_transfer_rig()

    # Faces removed from the joined mesh on purpose: fine.
    bm = bmesh.new()
    bm.from_mesh(target.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in range(5)], context='FACES')
    bm.to_mesh(target.data)
    bm.free()
    n_hand -= 5

    m = U.build_map(target, [hands, eye])
    target.data.calc_loop_triangles()
    assert TT.is_eq(len(m['part']), len(target.data.loop_triangles), "every triangle mapped")
    assert TT.is_eq(sorted(m['parts']), sorted([hands.name, eye.name]), "parts named")

    # Each triangle carries its part's own UVs: the target's are the part's, moved.
    hand_i = list(m['parts']).index(hands.name)
    is_hand = m['part'] == hand_i
    s = m['src_uv'][is_hand] - 0.5
    want = np.stack([-s[..., 1], s[..., 0]], axis=-1) * 0.5 + 0.25
    assert TT.is_true(np.allclose(m['tgt_uv'][is_hand], want, atol=1e-5),
                      "hand triangles carry their own UVs from the hands")
    s = m['src_uv'][~is_hand]
    assert TT.is_true(np.allclose(m['tgt_uv'][~is_hand], s * 0.25 + 0.7, atol=1e-5),
                      "eye triangles carry their own UVs from the eye")

    rep = U.map_report(m)
    assert TT.is_eq((rep[hands.name]['rotation'], round(rep[hands.name]['scale'], 3)), (90, 0.5),
                    "hands reported turned 90 degrees and halved")
    assert TT.is_eq((rep[eye.name]['rotation'], round(rep[eye.name]['scale'], 3)), (0, 0.25),
                    "eye reported quartered")

    # A vertex moved off its part: an error naming every face that uses it.
    v = target.data.polygons[0].vertices[0]
    target.data.vertices[v].co.z += 1.0
    users = {p.index for p in target.data.polygons if v in p.vertices}
    try:
        U.build_map(target, [hands, eye])
        assert False, "a moved vertex must stop the map"
    except U.MapError as e:
        assert TT.is_eq(set(e.faces), users, "the faces using the moved vertex are named")


@TT.category('STARFIELD', 'SHADER')
def TEST_UV_TRANSFER_PAINT():
    """uv_transfer paints a part's texture onto the joined mesh's UV layout.

    Colour lands where the triangle went. A normal map is also turned with its triangle: the
    hands' UVs are turned 90 degrees here, and a normal copied without turning would light
    them from the wrong side."""
    import numpy as np
    U = _uv_transfer()
    target, hands, eye, n_hand = _uv_transfer_rig()
    m = U.build_map(target, [hands, eye])

    def load(name):
        im = bpy.data.images.load(os.path.join(TT.SF_ASSETS, r"textures\actors\human\hands", name))
        im.colorspace_settings.name = 'Non-Color'
        w, h = im.size
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        return px.reshape(h, w, 4)[::-1, :, :3].copy()   # top row first, as files store it

    # The hands' quarter is 1024 pixels across at size 2048, as is the source: no shrinking.
    size = 2048
    is_hand = m['part'] == list(m['parts']).index(hands.name)
    tris = np.flatnonzero(is_hand)[::40]

    def compare(out, src, f):
        """Mean of f(painted pixel, source texel) at each test triangle's centre pixel."""
        errs = []
        for t in tris:
            T, S = m['tgt_uv'][t], m['src_uv'][t]
            c = T.mean(axis=0)
            ix, iy = int(c[0] * size), int((1 - c[1]) * size)
            p = np.array([(ix + 0.5) / size, 1 - (iy + 0.5) / size])
            A = np.column_stack([T[1] - T[0], T[2] - T[0]])
            if abs(np.linalg.det(A)) < 1e-12:
                continue
            b = np.linalg.solve(A, p - T[0])
            su = S[0] + b[0] * (S[1] - S[0]) + b[1] * (S[2] - S[0])
            h, w = src.shape[:2]
            sx, sy = int(su[0] % 1 * w), int((1 - su[1] % 1) * h)
            errs.append(f(out[iy, ix], src[sy, sx]))
        return float(np.mean(errs))

    color = load("defaulthandsf_sk1_color.png")
    out = U.paint(m, {hands.name: color, eye.name: (0.5, 0.5, 0.5)}, size=size)
    assert TT.is_eq(out.shape[:2], (size, size), "painted at the asked size")
    err = compare(out, color, lambda a, b: np.abs(a - b).mean())
    assert TT.is_true(err < 0.01, f"hand colour lands where its triangles went: {err:.3f}")

    normal = load("defaulthandsf_normal.png")
    out = U.paint(m, {hands.name: normal, eye.name: (0.5, 0.5, 1.0)}, size=size, normal=True)

    def xy(px):   # DirectX green: the stored green points down the texture
        return np.array([px[0] * 2 - 1, -(px[1] * 2 - 1)])

    turned = compare(out, normal, lambda a, b: np.abs(xy(a) - np.array([-xy(b)[1], xy(b)[0]])).mean())
    copied = compare(out, normal, lambda a, b: np.abs(xy(a) - xy(b)).mean())
    assert TT.is_true(turned < 0.01, f"normals turned with their triangles: {turned:.3f}")
    assert TT.is_true(copied > 3 * turned, f"CONTROL: a plain copy is wrong: {copied:.3f}")


@TT.category('STARFIELD', 'SHADER')
def TEST_UV_TRANSFER_SELECT_FAILED():
    """uv_transfer shows the faces that don't match by selecting them, and only them.

    It used to set just the faces' select flags. Edit Mode in vertex select mode shows vertex
    flags, so Bad Dog saw whatever vertices were selected before: a finger that had matched
    fine, and none of the faces that hadn't."""
    U = _uv_transfer()
    target, hands, eye, n_hand = _uv_transfer_rig()
    me = target.data
    me.vertices.foreach_set('select', [True] * len(me.vertices))   # a stale selection
    me.edges.foreach_set('select', [True] * len(me.edges))
    me.polygons.foreach_set('select', [True] * len(me.polygons))

    bad = [0, 7, n_hand + 3]
    U.select_faces(target, bad)
    want_v = {v for f in bad for v in me.polygons[f].vertices}
    want_e = {me.loops[li].edge_index for f in bad
              for li in range(me.polygons[f].loop_start,
                              me.polygons[f].loop_start + me.polygons[f].loop_total)}
    assert TT.is_eq({p.index for p in me.polygons if p.select}, set(bad), "only those faces")
    assert TT.is_eq({v.index for v in me.vertices if v.select}, want_v, "only their vertices")
    assert TT.is_eq({e.index for e in me.edges if e.select}, want_e, "only their edges")


@TT.category('STARFIELD', 'SHADER')
def TEST_UV_TRANSFER_MATERIAL_PARTS():
    """uv_transfer treats each material of a part object as a part of its own.

    Bad Dog joined the teeth into the head object; they keep their own material and texture.
    As one part, the teeth sampled the head texture and came out the colour of its empty
    background. A part object with several materials in use is now one part per material,
    named "<object>:<material>", each painted from its own texture."""
    import numpy as np
    U = _uv_transfer()
    target, hands, eye, n_hand = _uv_transfer_rig()

    # Give the source hands a second material on the left half of their UV layout. (By
    # region, not face by face: the two hands share their UVs, and faces painting the same
    # pixels share a texture.)
    second = bpy.data.materials.new("HandsSecond")
    hands.data.materials.append(second)
    first = hands.data.materials[0].name
    me = hands.data
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2)
    mi = [int(uv[p.loop_start:p.loop_start + p.loop_total, 0].mean() < 0.5) for p in me.polygons]
    me.polygons.foreach_set('material_index', mi)

    m = U.build_map(target, [hands, eye])
    names = [str(n) for n in m['parts']]
    want = sorted([f"{hands.name}:{first}", f"{hands.name}:HandsSecond", eye.name])
    assert TT.is_eq(sorted(names), want, "one part per material in use")

    # Each hand triangle belongs to the part of the material its source face has.
    target.data.calc_loop_triangles()
    tri_poly = np.empty(len(target.data.loop_triangles), np.int32)
    target.data.loop_triangles.foreach_get('polygon_index', tri_poly)
    is_hand = tri_poly < n_hand
    part_name = np.array(names)[m['part']]
    want_part = np.where(np.array(mi)[np.minimum(tri_poly, n_hand - 1)] == 1,
                         f"{hands.name}:HandsSecond", f"{hands.name}:{first}")
    assert TT.is_true((part_name[is_hand] == want_part[is_hand]).all(),
                      "hand triangles split by their source face's material")

    # Painted from its own texture: two flat colours land on their own triangles. Only
    # triangles big enough to own their centre pixel are measured.
    size = 2048
    out = U.paint(m, {f"{hands.name}:{first}": (1.0, 0.0, 0.0),
                      f"{hands.name}:HandsSecond": (0.0, 0.0, 1.0),
                      eye.name: (0.0, 1.0, 0.0)}, size=size, pad=0)
    T = m['tgt_uv'] * size
    area = np.abs((T[:, 1, 0] - T[:, 0, 0]) * (T[:, 2, 1] - T[:, 0, 1])
                  - (T[:, 2, 0] - T[:, 0, 0]) * (T[:, 1, 1] - T[:, 0, 1])) / 2
    hits = {'r': 0, 'b': 0, 'wrong': 0}
    for t in np.flatnonzero(is_hand & (area > 30)):
        c = m['tgt_uv'][t].mean(axis=0)
        px = out[int((1 - c[1]) * size), int(c[0] * size)]
        want_c = (0.0, 0.0, 1.0) if part_name[t].endswith("HandsSecond") else (1.0, 0.0, 0.0)
        if np.allclose(px[:3], want_c):
            hits['b' if want_c[2] else 'r'] += 1
        else:
            hits['wrong'] += 1
    assert TT.is_true(hits['r'] > 50 and hits['b'] > 50 and hits['wrong'] == 0,
                      f"each material painted with its own colour: {hits}")
