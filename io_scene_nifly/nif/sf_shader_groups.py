"""Starfield shading in Blender: the node groups a Starfield material is built from, the
properties stamped on its nodes, and where a material file is found.

Shared by sf_shader_import (building a material from a .mat) and sf_shader_export (reading
one back)."""

import json
import os
import logging
from contextlib import suppress
import bpy
from .. import __package__ as base_package
from ..blender_defs import ALPHA_MAP_NAME, COLOR_MAP_NAME
from .shader_nodes import (make_mixnode, make_separator)

log = logging.getLogger("pynifly")

# --- Starfield "SF Parameters" value-holder node group -----------------------------------------
# One contained node per SF material holds every non-texture param (SSS/emissive/alpha settings +
# the shader-model identity). Its INPUT sockets are the param store -- each shows an editable field
# on the node -- and a few OUTPUT sockets carry driving values into the Principled BSDF. This is
# the export param source: walk the inputs by socket NAME to recover the .mat settings. See
# docs/sf_shader_plan.md "Locked P0 spec". Generated procedurally now; moves to shaders.blend at P3.
# Default Principled Subsurface Scale for imported skin/fur. SF meshes import at GAME units
# (nifly applies havokScale ~= 70, so 1 m ~= 70 units), where Blender's default scatter scale of
# ~0.05 is microscopic. 0.05 * havokScale ~= 3.5 reproduces Blender's intended skin look at game
# scale (calibrated by eye, Bad Dog 2026-07-12). Render-tuning constant, on the Principled node.
SF_SUBSURFACE_SCALE = 3.5

# The shader-model identity (template name) is a string with no shader socket -> a material
# custom property.
SF_SHADER_MODEL_PROP = 'pyn_sf_shader_model'


def _sf_new_socket(iface, name, in_out, socket_type):
    """bpy interface.new_socket wrapper (Blender 4.0+ node-tree interface API)."""
    return iface.new_socket(name, in_out=in_out, socket_type=socket_type)


# --- Per-.mat-component settings groups --------------------------------------------------------
# Each root-level settings component (TranslucencySettings, LayeredEmissivity, AlphaSettings,
# HairSettings) gets its OWN value-holder group named after the component (Bad Dog: don't dump
# every param on one node -- there are a million possible params). Each is added only when the
# material has that component; its INPUT sockets are the param store, a few OUTPUT sockets drive
# the Principled, and recovery/write walk them by the group name (== the .mat component).
#
# fields: (socket name, socket type, default, settings key). A None socket type = a string that
#   has no shader socket, held as a node custom property. inputs (optional): sockets the material
#   wires into, same shape as fields but not stored in the .mat. outputs: (name, type).
#   wire(gin,gout,ng) builds the internal driving wiring. build(nt, node, block) and
#   recover(node, block) (optional) carry a setting the material's wiring records instead of a
#   socket value.
def _wire_translucency(gin, gout, ng):
    # SSS Weight = Translucency Enable * Use SSS (both flags kept; product = AND on 0/1).
    m = ng.nodes.new('ShaderNodeMath'); m.operation = 'MULTIPLY'; m.location = (0, 100)
    ng.links.new(gin.outputs["Translucency Enable"], m.inputs[0])
    ng.links.new(gin.outputs["Use SSS"], m.inputs[1])
    ng.links.new(m.outputs[0], gout.inputs["SSS Weight"])


def _wire_emissive(gin, gout, ng):
    """The component's own semantics, so its inputs drive the preview live: the layer's emissive
    colour times the tint, at strength 1 when Emissive Enable is on and 0 when it is off."""
    m = make_mixnode(ng, gin.outputs["Emissive"], gin.outputs["Emissive Tint"],
                     output=gout.inputs["Emissive Color"], location=(0, 0))
    m.label = "Emissive x tint"
    ng.links.new(gin.outputs["Emissive Enable"], gout.inputs["Emissive Strength"])


def _wire_alpha(gin, gout, ng):
    """The component's own semantics, so its inputs drive the preview live: with Has Opacity off
    the shape is opaque; with it on, the opacity -- scaled by the Vertex Color input when Use
    Vertex Color is on -- is alpha-tested against the threshold. Which vertex channel that is
    is the wiring outside the group (see _alpha_vertex_source)."""
    n, L = ng.nodes, ng.links

    def mix(label, fac, a, b, loc):
        m = n.new('ShaderNodeMix'); m.data_type = 'FLOAT'; m.label = label; m.location = loc
        L.new(fac, m.inputs['Factor'])
        for sock, v in ((m.inputs['A'], a), (m.inputs['B'], b)):
            if hasattr(v, 'node'):
                L.new(v, sock)
            else:
                sock.default_value = v
        return m.outputs['Result']

    vert = mix("Vertex color if used", gin.outputs["Use Vertex Color"], 1.0,
               gin.outputs["Vertex Color"], (-150, -200))
    scaled = n.new('ShaderNodeMath'); scaled.operation = 'MULTIPLY'; scaled.location = (0, 0)
    scaled.label = "Opacity x vertex color"
    L.new(gin.outputs["Opacity"], scaled.inputs[0])
    L.new(vert, scaled.inputs[1])
    test = n.new('ShaderNodeMath'); test.operation = 'GREATER_THAN'; test.location = (150, 0)
    test.label = "Alpha test"
    L.new(scaled.outputs['Value'], test.inputs[0])
    L.new(gin.outputs["Alpha Test Threshold"], test.inputs[1])
    out = mix("Opaque unless Has Opacity", gin.outputs["Has Opacity"], 1.0,
              test.outputs['Value'], (300, 100))
    gout.location = (500, 0)
    L.new(out, gout.inputs["Alpha Out"])


_VERTEX_CHANNELS = ('Red', 'Green', 'Blue', 'Alpha')


def _alpha_vertex_source(nt, node, block):
    """Plug the vertex channel the .mat names (VertexColorChannel) into the alpha component's
    Vertex Color input. The game reads that channel of the vertex color; PyNifly imports the
    vertex alpha as its own VERTEX_ALPHA attribute and the rest as VERTEX_COLOR. The wiring is the
    record of the channel: export reads it back from whatever is plugged in."""
    channel = block.get('vertex_color_channel', 'Red')
    x, y = node.location
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_type = 'GEOMETRY'
    attr.location = (x - 450, y)
    if channel == 'Alpha':
        attr.attribute_name = ALPHA_MAP_NAME
        out = attr.outputs['Fac']
    else:
        attr.attribute_name = COLOR_MAP_NAME
        sep = make_separator(nt, attr.outputs['Color'], (x - 250, y))
        out = sep.outputs[channel if channel in _VERTEX_CHANNELS else 'Red']
    nt.links.new(out, node.inputs['Vertex Color'])


def _alpha_vertex_channel(node, block):
    """The vertex channel plugged into the alpha component (the reverse of _alpha_vertex_source):
    VERTEX_ALPHA is the Alpha channel, a separated VERTEX_COLOR output is that channel. Anything
    else -- or nothing -- writes the game's default, Red."""
    channel = 'Red'
    sock = node.inputs.get('Vertex Color')
    link = sock.links[0] if sock is not None and sock.is_linked else None
    while link is not None and link.from_node.type == 'REROUTE':
        ins = link.from_node.inputs[0]
        link = ins.links[0] if ins.is_linked else None
    if link is not None:
        src = link.from_node
        if src.type == 'ATTRIBUTE' and src.attribute_name == ALPHA_MAP_NAME:
            channel = 'Alpha'
        elif src.type == 'SEPARATE_COLOR' and link.from_socket.name in _VERTEX_CHANNELS:
            channel = link.from_socket.name
    block['vertex_color_channel'] = channel


def _wire_none(gin, gout, ng):
    """A value-holder with nothing to drive. The mouth/effect/LOD components configure engine
    behaviour PyNifly's preview doesn't reproduce, so their group node carries the values (visible,
    editable, round-tripped) without pretending to render them."""


def _wire_hair(gin, gout, ng):
    # First-pass hair -> Sheen: fuzzy-rim weight from backscatter, roughness through. Transmission
    # scales are held (round-trip) but not wired yet (no clean Principled home for hair translucency).
    ng.links.new(gin.outputs["Backscatter Strength"], gout.inputs["Sheen Weight"])
    ng.links.new(gin.outputs["Roughness"], gout.inputs["Sheen Roughness"])


def _wire_eye(gin, gout, ng):
    """The iris radius, passed out so the eye blend's mask can read it live. Measured in game:
    `IrisDepthTransitionRatio` is the UV radius, from the texture centre, out to which the iris
    layer shows; the sclera layer shows beyond it. The other eye settings drive refraction and
    lighting the preview does not reproduce."""
    ng.links.new(gin.outputs["Iris Depth Transition"], gout.inputs["Iris Radius"])


_SF_COMPONENT_VERSION = 6 # 2: the eye settings output their iris radius
                            # 3: the alpha settings hold their vertex-color source
                            # 4: the alpha settings compute the alpha (Opacity in, Alpha Out)
                            # 5: ... and take the vertex channel as an input (Vertex Color)
                            # 6: the emissive settings compute the emission (Emissive in)
_SF_COMPONENTS = {
    'translucency': {
        'group': 'SF TranslucencySettings',
        'fields': [
            ("Translucency Enable",   'NodeSocketBool',  False, 'enabled'),
            ("Use SSS",               'NodeSocketBool',  False, 'use_sss'),
            ("Spec Lobe 0 Roughness", 'NodeSocketFloat', 1.0,   'spec_lobe0_roughness'),
            ("Spec Lobe 1 Roughness", 'NodeSocketFloat', 1.0,   'spec_lobe1_roughness'),
        ],
        'outputs': [("SSS Weight", 'NodeSocketFloat')],
        'wire': _wire_translucency,
    },
    'emissive': {
        'group': 'SF LayeredEmissivityComponent',
        'fields': [
            ("Emissive Enable", 'NodeSocketBool',  False,           'enabled'),
            ("Emissive Layer",  'NodeSocketInt',   0,               'first_layer_index'),
            ("Emissive Tint",   'NodeSocketColor', (1., 1., 1., 1.), 'tint'),
            ("Blend Mode",      None,              '',              'blender_mode'),
        ],
        'inputs': [("Emissive", 'NodeSocketColor', (0., 0., 0., 1.), None)],
        'outputs': [("Emissive Color", 'NodeSocketColor'),
                    ("Emissive Strength", 'NodeSocketFloat')],
        'wire': _wire_emissive,
    },
    'alpha': {
        'group': 'SF AlphaSettingsComponent',
        'fields': [
            ("Has Opacity",          'NodeSocketBool',  False, 'has_opacity'),
            ("Alpha Test Threshold", 'NodeSocketFloat', 0.5,   'threshold'),
            ("Use Vertex Color",     'NodeSocketBool',  False, 'use_vertex_color'),
        ],
        'inputs': [("Opacity",      'NodeSocketFloat', 1.0, None),
                   ("Vertex Color", 'NodeSocketFloat', 1.0, None)],
        'outputs': [("Alpha Out", 'NodeSocketFloat')],
        'wire': _wire_alpha,
        'build': _alpha_vertex_source,      # VertexColorChannel = what's plugged into Vertex Color
        'recover': _alpha_vertex_channel,
    },
    'hair': {
        'group': 'SF HairSettingsComponent',
        'fields': [
            ("Hair Enable",          'NodeSocketBool',  False, 'enabled'),
            ("Is Spiky",             'NodeSocketBool',  False, 'is_spiky'),
            ("Roughness",            'NodeSocketFloat', 0.0,   'roughness'),
            ("Spec Scale",           'NodeSocketFloat', 0.0,   'spec_scale'),
            ("Backscatter Strength", 'NodeSocketFloat', 0.0,   'backscatter_strength'),
            ("Backscatter Wrap",     'NodeSocketFloat', 0.0,   'backscatter_wrap'),
            ("Spec Transmission",    'NodeSocketFloat', 0.0,   'spec_transmission'),
            ("Direct Transmission",  'NodeSocketFloat', 0.0,   'direct_transmission'),
            ("Diffuse Transmission", 'NodeSocketFloat', 0.0,   'diffuse_transmission'),
            ("Max Depth Offset",     'NodeSocketFloat', 0.0,   'max_depth_offset'),
            ("Dither Scale",         'NodeSocketFloat', 0.0,   'dither_scale'),
        ],
        'outputs': [("Sheen Weight", 'NodeSocketFloat'), ("Sheen Roughness", 'NodeSocketFloat')],
        'wire': _wire_hair,
    },
    # The remaining per-material components. Field keys match sf_materials._COMPONENT_SPECS, which
    # is what parses and writes them; here they get a node so they are visible and editable.
    'eye': {
        'group': 'SF EyeSettingsComponent',
        'fields': [
            ("Eye Enable",                'NodeSocketBool',  False, 'enabled'),
            ("Sclera Eye Roughness",      'NodeSocketFloat', 0.0,   'sclera_eye_roughness'),
            ("Iris Depth Position",       'NodeSocketFloat', 0.0,   'iris_depth_position'),
            ("Iris Total Depth",          'NodeSocketFloat', 0.0,   'iris_total_depth'),
            ("Iris Depth Transition",     'NodeSocketFloat', 0.0,   'iris_depth_transition_ratio'),
            ("Lighting Wrap",             'NodeSocketFloat', 0.0,   'lighting_wrap'),
            ("Lighting Power",            'NodeSocketFloat', 0.0,   'lighting_power'),
        ],
        'outputs': [("Iris Radius", 'NodeSocketFloat')],
        'wire': _wire_eye,
    },
    'mouth': {
        'group': 'SF MouthSettingsComponent',
        'fields': [
            ("Mouth Enable", 'NodeSocketBool', False, 'enabled'),
            ("Is Teeth",     'NodeSocketBool', False, 'is_teeth'),
        ],
        'outputs': [],
        'wire': _wire_none,
    },
    'shader_route': {
        'group': 'SF ShaderRouteComponent',
        'fields': [
            ("Route", None, '', 'route'),   # a name ('Effect', 'Deferred'), so a custom prop
        ],
        'outputs': [],
        'wire': _wire_none,
    },
    'effect': {
        'group': 'SF EffectSettingsComponent',
        'fields': [
            ("Receive Directional Shadows",     'NodeSocketBool',  False, 'receive_directional_shadows'),
            ("Receive Non-Directional Shadows", 'NodeSocketBool',  False, 'receive_non_directional_shadows'),
            ("Depth MV Fixup",                  'NodeSocketBool',  False, 'depth_mv_fixup'),
            ("Force Render Before OIT",         'NodeSocketBool',  False, 'force_render_before_oit'),
            ("No Half Res Optimization",        'NodeSocketBool',  False, 'no_half_res_optimization'),
            ("Depth Bias In Ulp",               'NodeSocketFloat', 0.0,   'depth_bias_in_ulp'),
        ],
        'outputs': [],
        'wire': _wire_none,
    },
    'lod_settings': {
        'group': 'SF LevelOfDetailSettings',
        'fields': [
            ("Num LOD Materials", 'NodeSocketInt', 0, 'num_lod_materials'),
        ],
        'outputs': [],
        'wire': _wire_none,
    },
    'detail_blender': {
        'group': 'SF DetailBlenderSettingsComponent',
        'fields': [
            ("Detail Blend Mask Supported", 'NodeSocketBool', False,
             'is_detail_blend_mask_supported'),
        ],
        'outputs': [],
        'wire': _wire_none,
    },
}


def ensure_sf_component_group(key):
    """Build (or return the cached) value-holder group for a .mat settings component."""
    spec = _SF_COMPONENTS[key]
    ng, fresh = _ensure_group(spec['group'], 'pyn_sf_comp_version', _SF_COMPONENT_VERSION)
    if not fresh:
        return ng
    iface = ng.interface
    for name, stype, default, _key in spec.get('inputs', []) + spec['fields']:
        if stype is None:
            continue   # string custom-prop field, no socket
        s = _sf_new_socket(iface, name, 'INPUT', stype)
        if default is not None:
            with suppress(Exception):
                s.default_value = default
    for oname, otype in spec['outputs']:
        _sf_new_socket(iface, oname, 'OUTPUT', otype)
    gin = ng.nodes.new('NodeGroupInput'); gin.location = (-400, 0)
    gout = ng.nodes.new('NodeGroupOutput'); gout.location = (300, 0)
    spec['wire'](gin, gout, ng)
    return ng


def is_sf_component_node(node, key):
    return _is_group(node, _SF_COMPONENTS[key]['group'])


def sf_component_node_of(material, key):
    """The component group node of the given kind in a material, or None."""
    if not (material and material.node_tree):
        return None
    return next((n for n in material.node_tree.nodes if is_sf_component_node(n, key)), None)


def add_sf_component_node(nt, key, block, location):
    """Add + populate a component group node from a parsed settings block dict."""
    spec = _SF_COMPONENTS[key]
    node = nt.nodes.new('ShaderNodeGroup')
    node.node_tree = ensure_sf_component_group(key)
    node.location = location
    node.label = spec['group']
    for name, stype, _default, skey in spec['fields']:
        if skey not in block:
            continue
        val = block[skey]
        if stype is None:
            node[name] = val   # string custom-prop
        elif stype == 'NodeSocketColor':
            node.inputs[name].default_value = tuple(val)
        else:
            node.inputs[name].default_value = val
    if 'build' in spec:
        spec['build'](nt, node, block)
    return node


def recover_sf_component(node, key):
    """Read a component group node's inputs back into a settings block dict."""
    spec = _SF_COMPONENTS[key]
    block = {}
    for name, stype, default, skey in spec['fields']:
        if stype is not None and name not in node.inputs:
            block[skey] = default   # a node from an older group version, built before this field
        elif stype is None:
            block[skey] = node.get(name, default)
        elif stype == 'NodeSocketColor':
            block[skey] = tuple(node.inputs[name].default_value)
        elif stype == 'NodeSocketBool':
            block[skey] = bool(node.inputs[name].default_value)
        elif stype == 'NodeSocketInt':
            block[skey] = int(node.inputs[name].default_value)
        else:
            block[skey] = node.inputs[name].default_value
    if 'recover' in spec:
        spec['recover'](node, block)
    return block


def _reconstruct_normal_rgb(tree, color_out, loc):
    """Build a BC5 XY -> full [0,1] RGB normal reconstruct (Z = sqrt(1-x^2-y^2)) on `tree`, fed by
    the `color_out` socket. Returns the recombined RGB output socket. Reusable in a material tree
    or inside a node group (SF Layer)."""
    n, L = tree.nodes, tree.links
    x, y = loc

    def math(op, v0=None, v1=None, v2=None, dx=0, dy=0):
        m = n.new('ShaderNodeMath'); m.operation = op; m.location = (x + dx, y + dy)
        for i, v in enumerate((v0, v1, v2)):
            if v is None:
                continue
            if hasattr(v, 'node'):
                L.new(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m

    sep = n.new('ShaderNodeSeparateColor'); sep.location = (x, y)
    L.new(color_out, sep.inputs['Color'])
    # Starfield normals are DirectX-convention (green = -Y); Blender is OpenGL (+Y). Flip green
    # the moment it comes off the file, so everything downstream -- the Z reconstruct, the RNM
    # detail blend, the Normal Map node -- works in Blender's convention. Measured rather than
    # assumed: a real normal map's slope field must be curl-free, and both a shipped SF normal
    # and the Creation Kit's own FaceGen bake have ~2x less curl residual with green flipped.
    # Nothing to undo on export -- SF export writes the .mat's texture paths, never pixels.
    green = math('SUBTRACT', 1.0, sep.outputs['Green'], None, 0, -250).outputs['Value']
    rx = math('MULTIPLY_ADD', sep.outputs['Red'], 2.0, -1.0, 200, 100)
    ry = math('MULTIPLY_ADD', green, 2.0, -1.0, 200, -100)
    rx2 = math('MULTIPLY', rx.outputs['Value'], rx.outputs['Value'], None, 400, 100)
    ry2 = math('MULTIPLY', ry.outputs['Value'], ry.outputs['Value'], None, 400, -100)
    ssum = math('ADD', rx2.outputs['Value'], ry2.outputs['Value'], None, 600, 0)
    inv = math('SUBTRACT', 1.0, ssum.outputs['Value'], None, 800, 0)
    clamp = math('MAXIMUM', inv.outputs['Value'], 0.0, None, 1000, 0)
    nz = math('SQRT', clamp.outputs['Value'], None, None, 1200, 0)
    bcol = math('MULTIPLY_ADD', nz.outputs['Value'], 0.5, 0.5, 1400, 0)
    comb = n.new('ShaderNodeCombineColor'); comb.location = (x + 1600, y)
    L.new(sep.outputs['Red'], comb.inputs['Red'])
    L.new(green, comb.inputs['Green'])
    L.new(bcol.outputs['Value'], comb.inputs['Blue'])
    return comb.outputs['Color']


# --- Starfield "SF Normal Blend" group (Reoriented Normal Mapping) ------------------------------
# Composites a detail normal over a base normal using RNM (Barré-Brisebois & Hill) -- the correct
# way to layer normals (a naive Mix flattens detail). Both inputs are reconstructed tangent-space
# normals as [0,1] RGB (see _sf_normal_rgb); Factor (the blend mask) lerps base <-> reoriented so
# mask=0 is pure base, mask=1 is full detail. Output is [0,1] RGB for a Normal Map node.
SF_NORMAL_BLEND_GROUP = "SF Normal Blend"
_SF_NORMAL_BLEND_VERSION = 1


def ensure_sf_normal_blend_group():
    ng, fresh = _ensure_group(SF_NORMAL_BLEND_GROUP, 'pyn_sf_nblend_version',
                              _SF_NORMAL_BLEND_VERSION)
    if not fresh:
        return ng
    iface = ng.interface
    _sf_new_socket(iface, "Base Normal", 'INPUT', 'NodeSocketColor')
    _sf_new_socket(iface, "Detail Normal", 'INPUT', 'NodeSocketColor')
    fac = _sf_new_socket(iface, "Factor", 'INPUT', 'NodeSocketFloat')
    with suppress(Exception):
        fac.default_value = 1.0
        fac.min_value, fac.max_value = 0.0, 1.0
    _sf_new_socket(iface, "Normal", 'OUTPUT', 'NodeSocketColor')

    n = ng.nodes
    links = ng.links
    gin = n.new('NodeGroupInput'); gin.location = (-800, 0)
    gout = n.new('NodeGroupOutput'); gout.location = (900, 0)

    def vmath(op, loc, v1=None, v2=None):
        m = n.new('ShaderNodeVectorMath'); m.operation = op; m.location = loc
        if v1 is not None: m.inputs[1].default_value = v1
        if v2 is not None: m.inputs[2].default_value = v2
        return m

    # Decode to [-1,1]. t = base*(2,2,2)+(-1,-1,0) (RNM keeps base z positive); base_dec is the
    # plain [-1,1] base normal used as the mask-lerp endpoint.
    t = vmath('MULTIPLY_ADD', (-500, 150), (2, 2, 2), (-1, -1, 0))
    links.new(gin.outputs["Base Normal"], t.inputs[0])
    u = vmath('MULTIPLY_ADD', (-500, -150), (-2, -2, 2), (1, 1, -1))
    links.new(gin.outputs["Detail Normal"], u.inputs[0])
    base_dec = vmath('MULTIPLY_ADD', (-500, 380), (2, 2, 2), (-1, -1, -1))
    links.new(gin.outputs["Base Normal"], base_dec.inputs[0])

    dot = vmath('DOT_PRODUCT', (-250, 0)); links.new(t.outputs[0], dot.inputs[0]); links.new(u.outputs[0], dot.inputs[1])
    sep = n.new('ShaderNodeSeparateXYZ'); sep.location = (-250, 200); links.new(t.outputs[0], sep.inputs[0])
    s = n.new('ShaderNodeMath'); s.operation = 'DIVIDE'; s.location = (-50, 100)
    links.new(dot.outputs['Value'], s.inputs[0]); links.new(sep.outputs['Z'], s.inputs[1])
    ts = vmath('SCALE', (150, 100)); links.new(t.outputs[0], ts.inputs[0]); links.new(s.outputs['Value'], ts.inputs[3])
    r = vmath('SUBTRACT', (350, 50)); links.new(ts.outputs[0], r.inputs[0]); links.new(u.outputs[0], r.inputs[1])
    rn = vmath('NORMALIZE', (500, 50)); links.new(r.outputs[0], rn.inputs[0])

    # Mask-lerp base <-> reoriented, then re-encode to [0,1] RGB.
    mix = n.new('ShaderNodeMix'); mix.data_type = 'VECTOR'; mix.location = (650, 200)
    links.new(gin.outputs["Factor"], mix.inputs[0])  # float Factor
    links.new(base_dec.outputs[0], mix.inputs[4])   # A (vector)
    links.new(rn.outputs[0], mix.inputs[5])          # B (vector)
    enc = vmath('MULTIPLY_ADD', (800, 200), (0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    links.new(mix.outputs[1], enc.inputs[0])         # vector result
    links.new(enc.outputs[0], gout.inputs["Normal"])
    return ng


# --- Starfield bundle-carrying layer/blend groups (P3) -----------------------------------------
# The real SF Layer / SF Blend groups carry the PBR "bundle" -- a fixed set of channels flowing
# Layer -> Blend -> ... -> Principled. `SF Layer` takes a layer's sampled slot textures and emits
# the bundle (BC5 normal reconstruct inside; Normal stays [0,1] RGB); UV tiling + a layer index
# ride as recovery metadata. `SF Blend Skin` composites two bundles (currently: pass bundle A
# through, RNM its Normal with B's -- the only channel skin's detail layer touches); the group
# name IS the blend mode, so recovery reads it without a prop. Texture paths still ride on the
# image nodes feeding each layer (pyn_sf_path stamps). Recovery walks the connected groups.
SF_LAYER_GROUP = "SF Layer"
SF_BLEND_GROUP = "SF Blend"        # prefix; concrete groups are "SF Blend Skin", "SF Blend Lerp", ...
_SF_GROUP_VERSION = 5   # 5: SF Layer inputs reordered to match the .mat texture-slot numbering

# The PBR bundle: (channel name, socket type). Carried between layers and blends.
_SF_BUNDLE = [
    ("Base Color",       'NodeSocketColor'),
    ("Roughness",        'NodeSocketFloat'),
    ("Metallic",         'NodeSocketFloat'),
    ("Normal",           'NodeSocketColor'),   # reconstructed [0,1] RGB
    ("AO",               'NodeSocketFloat'),
    ("Opacity",          'NodeSocketFloat'),
    ("Emissive",         'NodeSocketColor'),
    ("SSS Transmissive", 'NodeSocketFloat'),   # transmissive mask -- where SSS happens (tint = Base Color)
]
_SF_BUNDLE_NAMES = [n for n, _ in _SF_BUNDLE]

# The SF Layer group's raw texture inputs -> which bundle channel they feed, as
# (.mat slot index, socket name, bundle channel, default).
#
# Listed IN SLOT ORDER, which is the order the sockets appear on the node: a layer's inputs then
# read down the group in the same order its TextureSet lists them in the .mat, so socket 3 is the
# material's slot 3. The stacked image nodes follow the same order, since _build_sf_layer sorts
# them by socket position.
#
# All are Color inputs (image nodes output Color); Color->Float channels auto-convert by luminance.
# (Bad Dog: keep them Color -- a scalar map still varies per-texel and should invite a texture.)
# Normal is the odd one out: it feeds the BC5 reconstruct inside the group rather than passing
# straight through to its bundle channel. Slots 6 (Height) and 20 (ID) have no input yet.
_SF_LAYER_TEX_INPUTS = [
    (0, "Albedo",           "Base Color",       (1.0, 1.0, 1.0, 1.0)),
    (1, "Normal Tex",       "Normal",           (0.5, 0.5, 1.0, 1.0)),
    (2, "Opacity",          "Opacity",          (1.0, 1.0, 1.0, 1.0)),
    (3, "Roughness",        "Roughness",        (0.5, 0.5, 0.5, 1.0)),
    (4, "Metallic",         "Metallic",         (0.0, 0.0, 0.0, 1.0)),
    (5, "AO",               "AO",               (1.0, 1.0, 1.0, 1.0)),
    (7, "Emissive",         "Emissive",         (0.0, 0.0, 0.0, 1.0)),
    (8, "SSS Transmissive", "SSS Transmissive", (0.0, 0.0, 0.0, 1.0)),
]
SF_NORMAL_INPUT = "Normal Tex"

# custom-property keys stamped for export recovery
PYN_SF_PATH = 'pyn_sf_path'     # verbatim .mat-relative texture path (Data\-stripped)
PYN_SF_SLOT = 'pyn_sf_slot'     # slot name (Albedo/Normal/Mask/...)
PYN_SF_LAYER = 'pyn_sf_layer'   # owning layer index (on image + SF Layer node)
PYN_SF_TEX_SLOTS = 'pyn_sf_tex_slots'   # slots import gave an image node (on SF Layer node)
PYN_SF_BLEND = 'pyn_sf_blend'   # blender index (on SF Blend node)
PYN_SF_MODE = 'pyn_sf_mode'     # blend mode string (also encoded in the group name)
# MaterialOverrideColorTypeComponent, off the layer's MATERIAL -- how the layer's albedo is
# combined with the mesh's vertex color ('Multiply' is the only value vanilla human bodyparts use).
# Not a blend mode: that is BlendModeComponent, which rides on an SF Blend node as PYN_SF_MODE.
PYN_SF_OVERRIDE_COLOR_TYPE = 'pyn_sf_override_color_type'

# Indexed knob families. ParamBool and MaterialParamFloat are the shader model's own switches and
# scalars -- the .mat gives them an Index and nothing else, so PyNifly carries them by index rather
# than inventing names for meanings it doesn't know. Each index becomes its own scalar custom
# property on the node that owns it (a layer's SF Layer node, a blend's SF Blend node, or the
# material for the root's), which keeps them visible and editable in Blender's property panel.
PYN_SF_PARAM_BOOL = 'pyn_sf_parambool_'      # + index
PYN_SF_PARAM_FLOAT = 'pyn_sf_matparam_'      # + index
PYN_SF_TEX_REPLACE = 'pyn_sf_texreplace_'    # + texture slot index (an 'enabled' flag)
PYN_SF_LOD_MATERIAL = 'pyn_sf_lodmaterial_'  # + LOD level; a res: id naming a material in the db
PYN_SF_COLOR = 'pyn_sf_color'                # a layer material's Color (XMFLOAT4)
PYN_SF_MIP_BIAS = 'pyn_sf_mip_bias'
PYN_SF_TEX_RESOLUTION = 'pyn_sf_tex_resolution'
PYN_SF_REPLACE_SLOT = 'pyn_sf_replace_slot'  # on an RGB node: which slot it stands in for

# The .mat objects a Blender node stands for, as JSON: their res: ids, Parent links, CTNames and
# the components they carried. This is what lets export rebuild the material from the node tree
# alone instead of patching the file it came from -- the node knows its own identity, its
# inheritance, and everything about it PyNifly doesn't model. An SF Layer node stands for up to
# four objects (layer / material / texture set / uv stream) so it holds a dict of them; an SF
# Blend node and the material each stand for one.
PYN_SF_NODES = 'pyn_sf_nodes'   # on an SF Layer node: {kind: meta}
PYN_SF_NODE = 'pyn_sf_node'     # on an SF Blend node and on the material: one meta

# Where each of those objects -- and each FIELD of each of its components -- came from in
# the material's Import chain: `{'origin': <material>, 'fields': {<field>: <material>}}`,
# or that keyed by node kind where a node stands for several objects. The tree shows the
# EFFECTIVE material, so it cannot otherwise say which of the values on it this file owns
# and which it inherited, and writing an inherited value back as though it were local is
# how a derivation turns into the flat file that renders nowhere.
#
# Display and diagnosis only. The export decision compares against the resolved chain at
# write time rather than trusting these -- a stamp records what the parent said when the
# material was imported, which is not the same claim.
PYN_SF_ORIGIN = 'pyn_sf_origin'
PYN_SF_IMPORT = 'pyn_sf_import'   # on the material: its `Import` list, verbatim
PYN_SF_CHAIN = 'pyn_sf_chain'     # on the material: the resolved chain, for display
PYN_SF_OVERRIDE = 'pyn_sf_override'  # on a node: treat everything on it as this file's
PYN_SF_BASE = 'pyn_sf_base'       # on an SF Base group node: which material it stands for

# One node group per inherited material, named for it and SHARED by everything deriving from
# it, nested one level per step up the chain:
#
#   material node tree                      <- this .mat: the objects it owns
#     |_ SF Base: layered/shadermodels/eye1layer
#         |_ SF Base: layered/root/layeredmaterials
#
# A view, never a source: rebuilt from the resolver on every import and never read back.
# Export walks the material's own tree only, so editing inside one cannot corrupt a written
# file -- it can only make the view wrong, for every material sharing the datablock.
SF_BASE_GROUP = 'SF Base'


def _stamp_json(owner, key, value):
    """Store carried .mat state as JSON. A custom property could hold the dict directly, but it
    would come back as an IDPropertyGroup with ints for bools and no way to tell an empty list
    from an absent one -- and this state has to survive the round trip byte-for-byte."""
    if value:
        owner[key] = json.dumps(value)


def _recover_json(owner, key):
    raw = owner.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        log.warning(f"Could not read carried Starfield material state from {key}")
        return None


def _stamp_indexed(node, prefix, mapping):
    """Write an {index: value} family out as one scalar custom property per index."""
    for idx, val in (mapping or {}).items():
        node[prefix + str(idx)] = val


def _recover_indexed(node, prefix, cast):
    """Read an {index: value} family back off a node's custom properties."""
    out = {}
    for key in node.keys():
        if key.startswith(prefix):
            tail = key[len(prefix):]
            if tail.isdigit():
                out[int(tail)] = cast(node[key])
    return out

# --- SF material graph layout ------------------------------------------------------------------
# Columns, left -> right: textures | layers | blend row | BSDF. A 6-layer head is wide + tall, so
# columns share an X and rows share a Y to stay legible. Textures sit inside _build_sf_layer at
# (layer_x - SF_LAYER_TEX_DX); since every layer shares SF_X_LAYER, all textures share one X too.
SF_X_LAYER = -1400              # every SF Layer group node shares this X
SF_LAYER_TEX_DX = 600           # image nodes sit this far left of their layer node
SF_LAYER_TOP_Y = 0              # layer-0 (and its top texture) share the blend/BSDF row (Y=0)
SF_X_BLEND0 = -200              # leftmost blend X (right of the layer column)
SF_BLEND_DX = 450               # X gap between successive blends in the chain
SF_BLEND_Y = 0                  # the blend row Y (== BSDF Y)
SF_BSDF_GAP = 1000              # X from the last blend (or lone layer) to the BSDF -- extra space
SF_BLEND_WIDTH = 280            # blend + settings-component node width (2x the group default 140)
SF_LAYER_NODE_W = 300           # SF Layer group node width (also its node.width)
SF_LAYER_NODE_H = 430           # approx SF Layer node height (headless can't measure dimensions)
SF_TEX_DY = 280                 # close vertical spacing between a layer's stacked texture nodes
SF_TEX_NODE_H = 260             # approx texture image-node height (for content-driven layer spacing)
SF_LAYER_GAP = 60               # vertical gap between one layer's bottom and the next layer's top
SF_MASK_GAP = 40                # X gap from a layer node to its blend's mask node
SF_COMP_BASE_Y = 400            # bottom-most settings-component Y (sits above the blend row)
SF_COMP_DY = 350                # vertical gap between stacked settings-component nodes
SF_BASE_Y = 1400                # the SF Base group node, clear above everything else


def _versioned(name, version):
    """The datablock name for a version of a group: 'SF Layer' + 5 -> 'SF Layer v5'."""
    return f"{name} v{version}"


def _group_base(group_name):
    """A group datablock's name with any ' vN' version suffix removed."""
    base, _, tail = group_name.rpartition(' v')
    return base if base and tail.isdigit() else group_name


def _ensure_group(name, version_key='pyn_sf_group_version', version=None):
    """The node group for `name` at the current version, built if this .blend hasn't got it.

    THE VERSION IS PART OF THE NAME, and a group is never removed. A .blend accumulates materials
    built by different versions of the add-on, and a shared datablock can only be one version at a
    time -- so the old approach (delete the group, build the new one) orphaned every node still
    using it: `node_tree` becomes None, and the sockets and links go with it. Bad Dog hit exactly
    that, importing a vanilla head into a file holding a work-in-progress Lykaios head.

    Keeping old versions costs a few unused datablocks and needs no migration step: materials go on
    pointing at the group they were built with, which still exists and still works, while new
    materials get the current one. Materials of the same version still share a definition."""
    version = _SF_GROUP_VERSION if version is None else version
    full = _versioned(name, version)
    ng = bpy.data.node_groups.get(full)
    if ng is not None:
        return ng, False
    ng = bpy.data.node_groups.new(full, 'ShaderNodeTree')
    ng[version_key] = version
    return ng, True


def ensure_sf_layer_group():
    """One texture set -> the PBR bundle. Inputs: the layer's sampled slot textures (Color) + UV
    Scale/Offset (recovery metadata). Outputs: the bundle. BC5 normal is reconstructed inside."""
    ng, fresh = _ensure_group(SF_LAYER_GROUP)
    if not fresh:
        return ng
    iface = ng.interface
    for _slot, name, _bundle, default in _SF_LAYER_TEX_INPUTS:
        s = _sf_new_socket(iface, name, 'INPUT', 'NodeSocketColor')
        with suppress(Exception):
            s.default_value = default
    # UV tiling lives on a shared Mapping node per layer (not the group -- feeding it back here
    # would cycle group->image->group), so no UV inputs on the group.
    for name, stype in _SF_BUNDLE:
        _sf_new_socket(iface, name, 'OUTPUT', stype)

    gin = ng.nodes.new('NodeGroupInput'); gin.location = (-1700, 0)
    gout = ng.nodes.new('NodeGroupOutput'); gout.location = (300, 0)
    L = ng.links
    for _slot, name, bundle, _default in _SF_LAYER_TEX_INPUTS:
        if name == SF_NORMAL_INPUT:
            L.new(_reconstruct_normal_rgb(ng, gin.outputs[name], (-1400, -500)),
                  gout.inputs[bundle])
        else:
            L.new(gin.outputs[name], gout.inputs[bundle])
    return ng


def _ensure_sf_base_group(label):
    """The shared node group standing for one inherited material, emptied for rebuilding.

    Shared on purpose: open `SF Base: layered/shadermodels/eye1layer` from any eye material
    and it is the same datablock. Rebuilt rather than reused because it is a view of what the
    resolver just read, and a stale view of a template is a stale view for every material
    that derives from it.
    """
    name = f"{SF_BASE_GROUP}: {label}"
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    ng.use_fake_user = True
    return ng


def _ensure_sf_blend_group(suffix):
    """Build (or fetch) an SF Blend group named "SF Blend <suffix>". All modes currently share one
    body: pass every channel through from A, except Normal = RNM(A.Normal, B.Normal, Mask). The
    suffix distinguishes concrete groups so an unimplemented mode reads as its own node in the
    graph (a visible signal that its blend isn't really processed) rather than masquerading as Skin."""
    name = SF_BLEND_GROUP + " " + suffix
    ng, fresh = _ensure_group(name)
    if not fresh:
        return ng
    iface = ng.interface
    for prefix in ("A ", "B "):
        for chan, stype in _SF_BUNDLE:
            _sf_new_socket(iface, prefix + chan, 'INPUT', stype)
    _sf_new_socket(iface, "Mask", 'INPUT', 'NodeSocketFloat')
    for chan, stype in _SF_BUNDLE:
        _sf_new_socket(iface, chan, 'OUTPUT', stype)

    gin = ng.nodes.new('NodeGroupInput'); gin.location = (-600, 0)
    gout = ng.nodes.new('NodeGroupOutput'); gout.location = (300, 0)
    L = ng.links
    for chan, _stype in _SF_BUNDLE:
        if chan == "Normal":
            continue
        L.new(gin.outputs["A " + chan], gout.inputs[chan])
    rnm = ng.nodes.new('ShaderNodeGroup'); rnm.node_tree = ensure_sf_normal_blend_group()
    rnm.location = (-100, -200)
    L.new(gin.outputs["A Normal"], rnm.inputs["Base Normal"])
    L.new(gin.outputs["B Normal"], rnm.inputs["Detail Normal"])
    L.new(gin.outputs["Mask"], rnm.inputs["Factor"])
    L.new(rnm.outputs["Normal"], gout.inputs["Normal"])
    return ng


def ensure_sf_blend_skin_group():
    """The `Skin` blend group (B over A, Normal RNM-composited)."""
    return _ensure_sf_blend_group("Skin")


def sf_blend_group_for(mode):
    """The SF Blend group for a blend mode.

    Only `Skin` is implemented. The other two names are different claims and are kept apart:

    * **Default** -- the material declares no `BlendModeComponent` anywhere in its chain, so
      the shader model decides. Vanilla eyes are like this: both of `left_eye.mat`'s blenders
      carry a name and four `ParamBool`s and nothing else, where `male_default.mat` gives all
      five of its blenders a mode and a mask texture. Nothing is missing; the material really
      does say nothing.
    * **Unknown** -- the material names a mode we do not implement. Something IS missing.

    Both share the Skin body for now. The true mode rides on PYN_SF_MODE either way, so export
    round-trips it regardless of which group the graph shows.
    """
    if mode == 'Skin':
        return ensure_sf_blend_skin_group()
    return _ensure_sf_blend_group("Default" if not mode else "Unknown")


_SF_BLEND_EYE_VERSION = 2   # own count, apart from the other groups. 2: soft edge (Iris Feather)


def ensure_sf_blend_eye_group():
    """The iris/sclera blend of an Eye1Layer material, mask and all.

    The material gives this blender no mode and no mask; the eye shader makes the cut itself.
    Measured in game, 2026-09-25: the iris layer (A) shows out to a UV radius of
    `IrisDepthTransitionRatio` from the texture centre, the sclera layer (B) beyond it. (A mesh
    with its UVs scaled 2x showed a half-size iris; a cut by depth would have kept it full size.)

    So the group takes an `Iris Radius` in place of a Mask and computes the cut inside, from
    the UV. Base Color fades from A to B over `Iris Feather` inside the radius -- a preview
    choice, not a .mat field: a hard cut looked wrong, and 0.035 matched vanilla's brown iris
    by eye (Bad Dog, 2026-09-25). Normal is A's alone: hard-masking in B's detail normal cut a
    visible seam at the iris edge. Everything else is A's, as in every other blend."""
    ng, fresh = _ensure_group(SF_BLEND_GROUP + " Eye", version=_SF_BLEND_EYE_VERSION)
    if not fresh:
        return ng
    iface = ng.interface
    for prefix in ("A ", "B "):
        for chan, stype in _SF_BUNDLE:
            _sf_new_socket(iface, prefix + chan, 'INPUT', stype)
    s = _sf_new_socket(iface, "Iris Radius", 'INPUT', 'NodeSocketFloat')
    s.default_value = 0.16   # vanilla's
    s = _sf_new_socket(iface, "Iris Feather", 'INPUT', 'NodeSocketFloat')
    s.default_value = 0.035
    for chan, stype in _SF_BUNDLE:
        _sf_new_socket(iface, chan, 'OUTPUT', stype)

    gin = ng.nodes.new('NodeGroupInput'); gin.location = (-900, 0)
    gout = ng.nodes.new('NodeGroupOutput'); gout.location = (300, 0)
    L = ng.links
    for chan, _stype in _SF_BUNDLE:
        if chan != "Base Color":
            L.new(gin.outputs["A " + chan], gout.inputs[chan])

    # Mask: 0 inside the iris, 1 outside -- UV distance from the centre against the radius,
    # rising smoothly over the feather just inside it.
    tc = ng.nodes.new('ShaderNodeTexCoord'); tc.location = (-900, 400)
    off = ng.nodes.new('ShaderNodeVectorMath'); off.operation = 'SUBTRACT'
    off.location = (-700, 400)
    off.inputs[1].default_value = (0.5, 0.5, 0.0)
    dist = ng.nodes.new('ShaderNodeVectorMath'); dist.operation = 'LENGTH'
    dist.location = (-500, 400)
    start = ng.nodes.new('ShaderNodeMath'); start.operation = 'SUBTRACT'
    start.location = (-500, 600)
    cut = ng.nodes.new('ShaderNodeMapRange'); cut.interpolation_type = 'SMOOTHSTEP'
    cut.location = (-300, 400)
    cut.label = "Iris Mask"
    L.new(tc.outputs['UV'], off.inputs[0])
    L.new(off.outputs['Vector'], dist.inputs[0])
    L.new(gin.outputs["Iris Radius"], start.inputs[0])
    L.new(gin.outputs["Iris Feather"], start.inputs[1])
    L.new(dist.outputs['Value'], cut.inputs['Value'])
    L.new(start.outputs['Value'], cut.inputs['From Min'])
    L.new(gin.outputs["Iris Radius"], cut.inputs['From Max'])
    make_mixnode(ng, gin.outputs["A Base Color"], gin.outputs["B Base Color"],
                 output=gout.inputs["Base Color"], factor=cut.outputs['Result'],
                 blend_type='MIX', location=(-100, 200))
    return ng


def _is_group(node, group_name):
    """Is this node an instance of `group_name` (at any version, and of any variant)?

    Matched on the base name with the ' vN' suffix stripped, either exactly or followed by a
    space -- so 'SF Blend' finds 'SF Blend Skin v5' and 'SF Blend Default v4', while 'SF Layer'
    finds 'SF Layer v5' but NOT 'SF LayeredEmissivityComponent v1'. A plain startswith matched
    that last one, which is why layer counts had to be taken from recovery rather than by name."""
    if getattr(node, 'type', '') != 'GROUP' or node.node_tree is None:
        return False
    base = _group_base(node.node_tree.name)
    return base == group_name or base.startswith(group_name + ' ')


def sf_cdb_path():
    """The configured Starfield `materialsbeta.cdb` (expanded), or None if unset or absent.

    The six `Materials\\Layered\\Root` templates ship only inside it, so without it the tail
    of every chain goes unresolved -- on import that loses whatever they supply, and on export
    it turns inherited values into owned ones and writes them out.
    """
    try:
        raw = bpy.context.preferences.addons[base_package].preferences.sf_cdb_path
    except Exception:
        return None
    if not raw:
        return None
    p = bpy.path.abspath(raw)
    return p if os.path.isfile(p) else None


def sf_material_search(matpath, altpaths=None, extra=()):
    """Materials-tree roots to resolve a material's `Import` chain against: the tree the
    material itself sits in, plus any alternate asset roots that have one.

    Import and export ask the same question and must get the same answer -- export resolves
    the chain to work out what NOT to write, so a parent it cannot find there but could find
    on import would silently turn inherited values into owned ones.
    """
    from ..pyn import sf_matchain
    roots = [sf_matchain.tree_root(matpath)]
    for p in extra:
        if p:
            r = sf_matchain.tree_root(p)
            if r not in roots:
                roots.append(r)
    for alt in (altpaths or []):
        cand = os.path.join(alt, 'materials')
        if os.path.isdir(cand) and cand not in roots:
            roots.append(cand)
    return roots


# slot name -> (SF Layer group input, colorspace)
SF_SLOT_TO_LAYER_INPUT = {
    'Albedo': ('Albedo', 'sRGB'), 'Normal': ('Normal Tex', 'Non-Color'),
    'Roughness': ('Roughness', 'Non-Color'), 'Metal': ('Metallic', 'Non-Color'),
    'AO': ('AO', 'Non-Color'), 'Opacity': ('Opacity', 'Non-Color'),
    'Emissive': ('Emissive', 'sRGB'), 'Transmissive': ('SSS Transmissive', 'Non-Color'),
}
