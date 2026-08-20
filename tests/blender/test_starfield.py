"""Starfield tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


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

    # Alpha is a real test: opacity > threshold -> Alpha, via a GREATER_THAN node whose threshold
    # input is driven by the alpha component (single editable source), not baked into the node.
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    assert bsdf.inputs['Alpha'].is_linked, "Alpha is driven"
    clip = bsdf.inputs['Alpha'].links[0].from_node
    assert clip.type == 'MATH' and clip.operation == 'GREATER_THAN', \
        f"Alpha fed by a GREATER_THAN alpha-test node, got {clip.type}/{getattr(clip,'operation',None)}"
    assert clip.inputs[0].is_linked, "Opacity map feeds the alpha test"
    thr_src = clip.inputs[1].links[0].from_node if clip.inputs[1].is_linked else None
    assert thr_src == p, "Threshold driven by the SF AlphaSettingsComponent node (single source)"


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
    import json, shutil
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

    BD.ObjectSelect([root, head, arma], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SF", intuit_defaults=False)

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
    from an SF nif) autogenerates its external .mesh path. Starfield block names carry a ':'
    (e.g. 'Head:0'), which is illegal in a Windows filename and silently redirects the .mesh
    write into an NTFS alternate data stream -- so the geometry loads nowhere and the head is
    invisible in-game/CK. The autogen must (a) sanitize the name to a legal path and (b) record
    the generated meshName back onto the object's SF geometry props (which didn't exist because
    the shape wasn't imported from SF)."""
    import os
    # Unit-level: the sanitizer strips the ':index' illegal char and Blender's '.001' dedup
    # suffix, and never yields an empty component.
    from io_scene_nifly.nif.sf_geometry import sanitize_mesh_component
    assert sanitize_mesh_component("MaleHead:0") == "MaleHead_0", "colon sanitized"
    assert sanitize_mesh_component("MaleHead.001") == "MaleHead", "Blender .001 suffix stripped"
    assert sanitize_mesh_component("Head:0.002") == "Head_0", "suffix + colon together"
    assert sanitize_mesh_component(":::") == "___", "never empty"

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

    # (a) The autogenerated meshName must be a legal path -- no characters illegal in a Windows
    # filename ('\' is the legitimate path separator, so it's excluded from the check).
    from pyn.pynifly import NifFile
    nif = NifFile(outfile)
    mp = nif.shapes[0].mesh_path(0)
    assert not any(c in mp for c in '<>:"|?*'), f"Autogen meshName is a legal path: {mp!r}"

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
    import os, shutil
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
    import os, shutil
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
