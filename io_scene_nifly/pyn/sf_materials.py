r"""Starfield layered `.mat` material reading.

Starfield replaced FO4's flat BGSM with a layered, graph-based material authored as JSON in a
`.mat` file (compiled into a global `materialsbeta.cdb`). A shape's `BSLightingShaderProperty.Name`
holds `Materials\...\Foo.mat` (relative to Data\, WITH the .mat extension); everything about the
material lives in the `.mat`/`.cdb`, not the NIF.

We read the **loose** `.mat` JSON only -- vanilla materials compiled into the `.cdb` must be
pre-extracted to loose `.mat` (e.g. fo76utils `sfmatexport`), consistent with PyNifly never
cracking archives for textures/meshes. This module is Blender-independent (pure JSON) so it can be
unit-tested at the pyn layer; `shader_io` does the node wiring.

The `.mat` is an object graph: a top-level `Objects` list, each with `Components` of the form
`{ "Data": {...}, "Index": n, "Type": "BSMaterial::Xxx" }`. The concrete texture files live in
`BSMaterial::MRTextureFile` components, keyed by their slot `Index`. See the Bethesda Library
`starfield-materials.md` for the full DOM.
"""

import copy
import hashlib
import json
import logging

log = logging.getLogger("pynifly")

# Texture slot index -> a stable slot name. Indices are the Starfield TextureSet convention
# (one single-channel/PBR texture per property, unlike FO4's packed maps). Non-texture slots
# (NormalIntensity float, settings-block fields) are intentionally absent.
SF_TEXTURE_SLOTS = {
    0: 'Albedo',        # _color, sRGB
    1: 'Normal',        # _normal, BC5 XY (Z reconstructed)
    2: 'Opacity',       # _opacity
    3: 'Roughness',     # _rough
    4: 'Metal',         # _metal
    5: 'AO',            # _ao
    6: 'Height',        # _height
    7: 'Emissive',      # _emissive, sRGB
    8: 'Transmissive',  # _transmissive (SSS mask)
    20: 'ID',           # _id / _mask
}

_TEXTURE_FILE_TYPE = 'BSMaterial::MRTextureFile'


# Reflected CRC-32 table for poly 0x04C11DB7, used with init=0 and no final XOR (NOT the
# zlib/PKZIP parameterisation, which inits to all-ones and inverts the result).
_CRC32_TABLE = []
for _b in range(256):
    _c = _b
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    _CRC32_TABLE.append(_c)


def material_id(material_path):
    """The MaterialID a Starfield shape carries for `material_path`.

    Every SF character shape has a `NiIntegerExtraData` named 'MaterialID' on the BSGeometry
    block holding this value -- 372 of the 373 shape nifs surveyed across vanilla and mod
    archives, all of which match this function. It's derived data, so the exporter computes it
    from the shader's material path rather than asking the user to maintain a hash by hand.

    The hashed string is the path lowercased with backslash separators, and it includes both
    the leading 'Materials\\' and the trailing '.mat' -- dropping either changes the result.
    """
    if not material_path:
        return 0
    crc = 0
    for c in material_path.replace('/', '\\').lower().encode('utf-8'):
        crc = (crc >> 8) ^ _CRC32_TABLE[(crc ^ c) & 0xFF]
    return crc & 0xFFFFFFFF


_LAYER_ID = 'BSMaterial::LayerID'
_MATERIAL_ID = 'BSMaterial::MaterialID'
_TEXTURESET_ID = 'BSMaterial::TextureSetID'
_BLEND_MODE = 'BSMaterial::BlendModeComponent'
_BLENDER_ID = 'BSMaterial::BlenderID'
# A blender can mask its composite with a vertex-color channel (Red/Green/Blue/Alpha) instead of
# (or as well as) a texture mask; a layer's material can multiply its albedo by the vertex color.
# Both are how Starfield meshes' vertex colors feed the shader -- see reference_sf_vertex_colors.
_COLOR_CHANNEL = 'BSMaterial::ColorChannelTypeComponent'
_OVERRIDE_COLOR = 'BSMaterial::MaterialOverrideColorTypeComponent'
_UVSTREAM_ID = 'BSMaterial::UVStreamID'
_UV_SCALE = 'BSMaterial::Scale'
_UV_OFFSET = 'BSMaterial::Offset'

_SHADER_MODEL = 'BSMaterial::ShaderModelComponent'
_TRANSLUCENCY = 'BSMaterial::TranslucencySettingsComponent'
_EMISSIVITY = 'BSMaterial::LayeredEmissivityComponent'
_ALPHA_SETTINGS = 'BSMaterial::AlphaSettingsComponent'
_HAIR = 'BSMaterial::HairSettingsComponent'

# Indexed component families -- several of one type on a node, distinguished by their `Index`
# rather than by being a singleton settings block. Modelled as {index: value} maps.
_PARAM_BOOL = 'BSMaterial::ParamBool'
_PARAM_FLOAT = 'BSMaterial::MaterialParamFloat'
_TEX_REPLACE = 'BSMaterial::TextureReplacement'
_LOD_MATERIAL_ID = 'BSMaterial::LODMaterialID'
_COLOR = 'BSMaterial::Color'

# A game-valid loose `.mat` is NOT a self-contained graph: every node must inherit its base DOM from
# the shipped Root template for its kind via a `Parent` link, carry a `CTName`, and have a unique
# `res:` id. Without these the game/CK can't build the material and renders it magenta (a flat graph
# only ever "worked" through NifSkope's/PyNifly's lenient parsers). Parent paths are the vanilla form
# (lowercase, no `Data\` prefix), verified against a shipped male_default.mat.
_CTNAME = 'BSComponentDB::CTName'
_ROOT_TEMPLATE = 'materials\\layered\\root\\'
_PARENT_LAYEREDMATERIAL = _ROOT_TEMPLATE + 'layeredmaterials.mat'
_PARENT_LAYER = _ROOT_TEMPLATE + 'layers.mat'
_PARENT_MATERIAL = _ROOT_TEMPLATE + 'materials.mat'
_PARENT_TEXTURESET = _ROOT_TEMPLATE + 'texturesets.mat'
_PARENT_UVSTREAM = _ROOT_TEMPLATE + 'uvstreams.mat'
_PARENT_BLENDER = _ROOT_TEMPLATE + 'blenders.mat'

# --- Root settings components, declaratively ---------------------------------------------------
# Every per-material settings component is one entry here, so parsing, writing and patching share
# one description instead of a hand-written block each. A field is (dict key, .mat field path,
# kind); a path is a string, or a tuple when the component nests its fields inside a typed wrapper
# (translucency and detail-blender both do), in which case `nest` names the wrapper's Type.
#
# Field lists are the UNION of what vanilla human-bodypart materials actually carry -- the cdb
# stores only fields that differ from the parent template, so components appear with varying field
# sets (EffectSettings ships as 4 fields on 4 materials and 6 on one). Covering the union matters
# because patching REPLACES a component's Data: a short field list would silently drop the rest.
#
# kinds: bool/float/int/str, 'color' (a BSMaterial::Color-wrapped XMFLOAT4), and 'layerindex'
# (the MATERIAL_LAYER_n spelling of an integer layer index).
_COMPONENT_SPECS = [
    ('translucency', _TRANSLUCENCY, {'Settings': 'BSMaterial::TranslucencySettings'}, [
        ('enabled',              'Enabled',                              'bool'),
        ('use_sss',              ('Settings', 'UseSSS'),                 'bool'),
        ('spec_lobe0_roughness', ('Settings', 'SpecLobe0RoughnessScale'), 'float', 1.0),
        ('spec_lobe1_roughness', ('Settings', 'SpecLobe1RoughnessScale'), 'float', 1.0),
    ]),
    ('emissive', _EMISSIVITY, None, [
        ('enabled',            'Enabled',          'bool'),
        ('first_layer_index',  'FirstLayerIndex',  'layerindex'),
        ('blender_mode',       'FirstBlenderMode', 'str'),
        ('tint',               'FirstLayerTint',   'color'),
    ]),
    ('alpha', _ALPHA_SETTINGS, None, [
        ('has_opacity', 'HasOpacity',         'bool'),
        ('threshold',   'AlphaTestThreshold', 'float', 0.5),
    ]),
    # HairSettingsComponent has ~26 fields; these are the authored/visually-relevant ones.
    ('hair', _HAIR, None, [
        ('enabled',              'Enabled',                   'bool'),
        ('is_spiky',             'IsSpikyHair',               'bool'),
        ('roughness',            'Roughness',                 'float'),
        ('spec_scale',           'SpecScale',                 'float'),
        ('backscatter_strength', 'BackscatterStrength',       'float'),
        ('backscatter_wrap',     'BackscatterWrap',           'float'),
        ('spec_transmission',    'SpecularTransmissionScale', 'float'),
        ('direct_transmission',  'DirectTransmissionScale',   'float'),
        ('diffuse_transmission', 'DiffuseTransmissionScale',  'float'),
        ('max_depth_offset',     'MaxDepthOffset',            'float'),
        ('dither_scale',         'DitherScale',               'float'),
    ]),
    ('eye', 'BSMaterial::EyeSettingsComponent', None, [
        ('enabled',                     'Enabled',                  'bool'),
        ('sclera_eye_roughness',        'ScleraEyeRoughness',       'float'),
        ('iris_depth_position',         'IrisDepthPosition',        'float'),
        ('iris_total_depth',            'IrisTotalDepth',           'float'),
        ('iris_depth_transition_ratio', 'IrisDepthTransitionRatio', 'float'),
        ('lighting_wrap',               'LightingWrap',             'float'),
        ('lighting_power',              'LightingPower',            'float'),
    ]),
    ('mouth', 'BSMaterial::MouthSettingsComponent', None, [
        ('enabled',  'Enabled', 'bool'),
        ('is_teeth', 'IsTeeth', 'bool'),
    ]),
    ('shader_route', 'BSMaterial::ShaderRouteComponent', None, [
        ('route', 'Route', 'str'),
    ]),
    ('effect', 'BSMaterial::EffectSettingsComponent', None, [
        ('receive_directional_shadows',     'ReceiveDirectionalShadows',    'bool'),
        ('receive_non_directional_shadows', 'ReceiveNonDirectionalShadows', 'bool'),
        ('depth_mv_fixup',                  'DepthMVFixup',                 'bool'),
        ('force_render_before_oit',         'ForceRenderBeforeOIT',         'bool'),
        ('no_half_res_optimization',        'NoHalfResOptimization',        'bool'),
        ('depth_bias_in_ulp',               'DepthBiasInUlp',               'float'),
    ]),
    ('lod_settings', 'BSMaterial::LevelOfDetailSettings', None, [
        ('num_lod_materials', 'NumLODMaterials', 'int'),
    ]),
    ('detail_blender', 'BSMaterial::DetailBlenderSettingsComponent',
     {'DetailBlenderSettings': 'BSMaterial::DetailBlenderSettings'}, [
        ('is_detail_blend_mask_supported',
         ('DetailBlenderSettings', 'IsDetailBlendMaskSupported'), 'bool'),
    ]),
]


def _components_of(obj, ctype):
    return [c for c in obj.get('Components', []) if c.get('Type') == ctype]


def _first_component_data(objects, ctype):
    """The Data dict of the first component of ctype found across all objects, or None.

    Settings components (translucency/emissivity/shader-model) are per-material singletons and
    aren't reliably attached to any one graph node, so we sweep every object for them."""
    for o in objects:
        if not isinstance(o, dict):
            continue
        for c in _components_of(o, ctype):
            d = c.get('Data')
            if isinstance(d, dict):
                return d
    return None


# --- Node identity and carried state -----------------------------------------------------------
# The references that define the graph's SHAPE. These are regenerated when a material is rebuilt
# (ids change, layers can be added or reordered), so they are the one thing a node does NOT carry.
_STRUCTURAL = {_LAYER_ID, _BLENDER_ID, _MATERIAL_ID, _TEXTURESET_ID, _UVSTREAM_ID,
               _LOD_MATERIAL_ID, _CTNAME}


def _ctname_of(obj):
    for c in _components_of(obj, _CTNAME):
        return (c.get('Data') or {}).get('Name', '')
    return ''


def _node_meta(obj, kind=None):
    """One graph object's identity and its components, carried on the Blender element it becomes.

    The node carries EVERYTHING the source object had except the structural references -- not just
    the components PyNifly doesn't model, but the full Data of the ones it does. That is what makes
    the node tree self-sufficient: rebuilding merges the modelled values over what was carried, so
    a component's unmodelled FIELDS survive as surely as an unmodelled component does
    (LayeredEmissivityComponent has 17 fields to our 4, and losing the other 13 was defect 4).

    Carrying `ID` and `Parent` keeps the identity and the inheritance the source gave the node,
    whatever parenting scheme that source used -- so rebuilding doesn't have to answer the open
    question of which scheme is correct."""
    if obj is None:
        return None
    return {'id': obj.get('ID', ''),
            'parent': obj.get('Parent', ''),
            'name': _ctname_of(obj),
            # An EMPTY structural reference is not a reference -- it is a declaration that the slot
            # exists and points at nothing (vanilla blenders declare an empty UVStreamID). Only
            # references that actually name something are dropped and regenerated.
            'components': [copy.deepcopy(c) for c in obj.get('Components', [])
                           if c.get('Type') != _CTNAME
                           and not (c.get('Type') in _STRUCTURAL
                                    and (c.get('Data') or {}).get('ID'))]}


def _as_bool(v, default=False):
    """`.mat` stores bools as the strings 'true'/'false'."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() == 'true'
    return default


def _as_float(v, default=0.0):
    """`.mat` stores scalars as strings."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _decode_xmfloat(color_data):
    """A `.mat` XMFLOAT color is nested `{ Value: { Type: 'XMFLOAT4', Data: {x,y,z,w} } }`.
    Return an (x, y, z, w) tuple of floats (missing channels default to 0.0, w to 1.0)."""
    val = (color_data or {}).get('Value') or {}
    d = val.get('Data') or {}
    return (_as_float(d.get('x')), _as_float(d.get('y')),
            _as_float(d.get('z')), _as_float(d.get('w'), 1.0))


def _layer_index(name, default=0):
    """'MATERIAL_LAYER_0' / 'BLEND_LAYER_1' -> the trailing integer."""
    if isinstance(name, str) and '_' in name:
        tail = name.rsplit('_', 1)[-1]
        if tail.isdigit():
            return int(tail)
    return default


def _field_default(spec_field):
    """A component field's default: the 4th element of its spec tuple, else the kind's zero."""
    if len(spec_field) > 3:
        return spec_field[3]
    return {'bool': False, 'float': 0.0, 'int': 0, 'str': '',
            'layerindex': 0, 'color': (0.0, 0.0, 0.0, 1.0)}[spec_field[2]]


def _read_field(data, path, kind, default):
    """Read one component field out of a `.mat` Data dict, decoding the `.mat`'s string/typed-node
    representation into plain Python. `path` is a field name, or a (wrapper, field) pair for a
    component that nests its fields inside a typed sub-node."""
    if isinstance(path, tuple):
        for step in path[:-1]:
            data = (data.get(step) or {}).get('Data') or {}
        path = path[-1]
    if kind == 'color':
        return _decode_xmfloat((data.get(path) or {}).get('Data'))
    raw = data.get(path)
    if kind == 'bool':
        return _as_bool(raw, default)
    if kind == 'float':
        return _as_float(raw, default)
    if kind == 'int':
        return int(_as_float(raw, default))
    if kind == 'layerindex':
        return _layer_index(raw, default)
    return raw if isinstance(raw, str) else default


def _extract_settings(objects, root=None):
    """Pull the material's settings-component params into a normalised, round-trippable dict.

    Only blocks that are actually present are included, so callers test membership. Values are
    decoded out of the `.mat`'s string/typed-node representation into plain Python
    (bool/float/tuple), driven by _COMPONENT_SPECS.

    Settings components live on the root LayeredMaterial, so `root` is read in preference to a
    sweep of every object -- a material whose LOD material is also in the document (as it is when
    the material is reconstructed from the cdb) has a second set of settings components on that
    LOD subtree, and a sweep can pick those up instead."""
    settings = {}
    # Settings components belong to the root. Only fall back to a sweep of every object when
    # there is no root at all (a flat, single-object material) -- otherwise a material whose LOD
    # material is also in the document contributes ITS settings components to ours.
    hosts = [root] if root is not None else list(objects)

    sm = _first_component_data(hosts, _SHADER_MODEL)
    if sm and sm.get('FileName'):
        settings['shader_model'] = sm['FileName']

    for key, ctype, _nest, fields in _COMPONENT_SPECS:
        data = _first_component_data(hosts, ctype)
        if data is None:
            continue
        settings[key] = {f[0]: _read_field(data, f[1], f[2], _field_default(f)) for f in fields}

    if root is not None:
        settings['node'] = _node_meta(root)
        bools = _indexed_bools(root)
        if bools:
            settings['param_bools'] = bools
        # Empty entries are kept: LOD levels are indexed, and a material that declares levels 0-2
        # with only level 2 populated says something different from one that declares only level 2.
        lods = {c.get('Index', 0): (c.get('Data') or {}).get('ID', '')
                for c in _components_of(root, _LOD_MATERIAL_ID)}
        if lods:
            settings['lod_materials'] = lods

    return settings


def _indexed_bools(obj):
    """{index: bool} from an object's ParamBool components. These are the shader model's own
    on/off knobs -- their meaning is defined by the shader, not the material format, so they are
    carried by index without inventing names for them."""
    return {c.get('Index', 0): _as_bool((c.get('Data') or {}).get('Value'))
            for c in _components_of(obj, _PARAM_BOOL)}


def _indexed_floats(obj):
    """{index: float} from an object's MaterialParamFloat components (shader-defined knobs, as
    ParamBool above)."""
    return {c.get('Index', 0): _as_float((c.get('Data') or {}).get('Value'))
            for c in _components_of(obj, _PARAM_FLOAT)}


def _texture_replacements(obj):
    """{slot index: {enabled, color}} from a texture set's TextureReplacement components -- a flat
    colour standing in for a texture slot. Only the keys actually present are recorded: vanilla
    ships plenty of `{Enabled: true}` with no Color (the colour comes from the parent template),
    and inventing one would change the material."""
    out = {}
    for c in _components_of(obj, _TEX_REPLACE):
        d = c.get('Data') or {}
        rep = {}
        if 'Enabled' in d:
            rep['enabled'] = _as_bool(d.get('Enabled'))
        if 'Color' in d:
            rep['color'] = _decode_xmfloat((d.get('Color') or {}).get('Data'))
        if rep:
            out[c.get('Index', 0)] = rep
    return out


def _first_color(obj):
    """The XMFLOAT4 of an object's BSMaterial::Color component, or None. (Unlike the Color a
    TextureReplacement carries, this one's Data holds the XMFLOAT4 directly.)"""
    for c in _components_of(obj, _COLOR):
        return _decode_xmfloat(c.get('Data'))
    return None


def _first_value(obj, ctype, field, kind='str'):
    """A single-field component's decoded value, or None when the component is absent."""
    for c in _components_of(obj, ctype):
        d = c.get('Data') or {}
        if field in d:
            return _as_bool(d[field]) if kind == 'bool' else d[field]
    return None


def _first_ref(obj, ctype):
    """The Data.ID of obj's first component of ctype (a res: id string), or None."""
    for c in _components_of(obj, ctype):
        d = c.get('Data')
        if isinstance(d, dict) and d.get('ID'):
            return d['ID']
    return None


def _textureset_slots(obj):
    """{slot_name: cleaned_path} from an object's MRTextureFile components."""
    out = {}
    for c in _components_of(obj, _TEXTURE_FILE_TYPE):
        slot = SF_TEXTURE_SLOTS.get(c.get('Index'))
        if slot is None:
            continue
        path = _clean_texture_path((c.get('Data') or {}).get('FileName'))
        if path:
            out.setdefault(slot, path)
    return out


def _clean_texture_path(filename):
    """Normalise a `.mat` texture path for PyNifly's loose-file search. `.mat` stores texture
    paths WITH the `Data\\` prefix and WITH the `.DDS` extension; strip a leading `Data\\` so the
    path is rooted at `textures\\...` like the rest of PyNifly's texture handling."""
    p = (filename or '').strip()
    if not p:
        return ''
    low = p.lower().replace('/', '\\')
    if low.startswith('data\\'):
        p = p[len('data\\'):]
    return p


def _decode_xmfloat2(data, default):
    """A `.mat` XMFLOAT2 is `{ Value: { Type: 'XMFLOAT2', Data: {x, y} } }`. Missing -> default."""
    d = ((data or {}).get('Value') or {}).get('Data') or {}
    if 'x' not in d and 'y' not in d:
        return default
    return (_as_float(d.get('x'), default[0]), _as_float(d.get('y'), default[1]))


def _uv_stream_of(obj, by_id):
    """The (scale, offset) tiling of an object's UVStream (via its UVStreamID). A UV stream is a
    loose bag of components -- Scale (XMFLOAT2, tiling) and Offset -- so read them by type.
    Missing stream or missing components fall back to identity (1,1)/(0,0)."""
    uv = by_id.get(_first_ref(obj, _UVSTREAM_ID))
    scale, offset = (1.0, 1.0), (0.0, 0.0)
    if uv:
        for c in uv.get('Components', []):
            if c.get('Type') == _UV_SCALE:
                scale = _decode_xmfloat2(c.get('Data'), (1.0, 1.0))
            elif c.get('Type') == _UV_OFFSET:
                offset = _decode_xmfloat2(c.get('Data'), (0.0, 0.0))
    return scale, offset


def _extract_layers(root, by_id):
    """The material's layers in composite order (base first). Each = its TextureSet slots + the
    UVStream tiling. Layer k's LayerID Index fixes the order; the UVStreamID sits on the layer
    (falling back to its material)."""
    layers = []
    for lc in sorted(_components_of(root, _LAYER_ID), key=lambda c: c.get('Index', 0)):
        layer = by_id.get((lc.get('Data') or {}).get('ID'))
        if not layer:
            continue
        mat = by_id.get(_first_ref(layer, _MATERIAL_ID))
        texset = by_id.get(_first_ref(mat, _TEXTURESET_ID)) if mat else None
        uv_host = layer if _first_ref(layer, _UVSTREAM_ID) else (mat or layer)
        scale, offset = _uv_stream_of(uv_host, by_id)
        # A MaterialOverrideColorTypeComponent on the layer's material (e.g. 'Multiply') multiplies
        # the layer albedo by the mesh's vertex color -- '' when the layer doesn't use vertex color.
        override = ''
        if mat:
            for c in mat.get('Components', []):
                if c.get('Type') == _OVERRIDE_COLOR:
                    override = (c.get('Data') or {}).get('Value', '') or override
        entry = {'textures': _textureset_slots(texset) if texset else {},
                 'uv_scale': scale, 'uv_offset': offset, 'override_color': override}
        # A layer collapses onto one Blender node, so the identity + residue of each of the .mat
        # objects behind it are kept separately, keyed by which object they came from.
        uv = by_id.get(_first_ref(uv_host, _UVSTREAM_ID))
        nodes = {'layer': _node_meta(layer), 'material': _node_meta(mat),
                 'textureset': _node_meta(texset), 'uvstream': _node_meta(uv)}
        # Vanilla hangs the UV stream off the layer on some materials and off the layer's material
        # on others; remember which, so rebuilding puts the reference back where it was.
        if nodes['material'] is not None and uv is not None and uv_host is mat:
            nodes['material']['owns_uvstream'] = True
        entry['nodes'] = {k: v for k, v in nodes.items() if v is not None}
        # The rest of what a layer's Material and TextureSet carry. Absent families are left out
        # entirely (as the settings blocks are) so a dict that never mentions them round-trips.
        if mat is not None:
            _set_if(entry, 'param_bools', _indexed_bools(mat))
            _set_if(entry, 'color', _first_color(mat))
        if texset is not None:
            _set_if(entry, 'mat_params', _indexed_floats(texset))
            _set_if(entry, 'tex_replace', _texture_replacements(texset))
            _set_if(entry, 'mip_bias',
                    _first_value(texset, 'BSMaterial::MipBiasSetting', 'DisableMipBiasHint', 'bool'))
            _set_if(entry, 'tex_resolution',
                    _first_value(texset, 'BSMaterial::TextureResolutionSetting', 'ResolutionHint'))
        layers.append(entry)
    return layers


def _set_if(d, key, value):
    """Record `value` under `key` only when there is something to record, so a material that has
    no such component produces a dict with no such key (and round-trips through a caller that
    never mentions it)."""
    if value is not None and value != {}:
        d[key] = value


def _extract_blenders(root, by_id):
    """The material's blenders in order. Blender k composites layer k+1 over the running
    composite: it carries a BlendModeComponent (Skin/Lerp/Additive/...) and a mask that is either
    a texture (MRTextureFile) or a vertex-color channel (ColorChannelTypeComponent: Red/Green/
    Blue/Alpha). There are (#layers - 1) of them."""
    blenders = []
    for bc in sorted(_components_of(root, _BLENDER_ID), key=lambda c: c.get('Index', 0)):
        b = by_id.get((bc.get('Data') or {}).get('ID'))
        if not b:
            continue
        mode, mask, channel = '', '', ''
        for c in b.get('Components', []):
            if c.get('Type') == _BLEND_MODE:
                mode = (c.get('Data') or {}).get('Value', '') or mode
            elif c.get('Type') == _TEXTURE_FILE_TYPE:
                mask = _clean_texture_path((c.get('Data') or {}).get('FileName')) or mask
            elif c.get('Type') == _COLOR_CHANNEL:
                channel = (c.get('Data') or {}).get('Value', '') or channel
        entry = {'mode': mode, 'mask': mask, 'channel': channel, 'node': _node_meta(b)}
        # A blender can own a UV stream of its own (male_default gives each of its four one). Its
        # tiling has no place in the Blender node tree, so the stream is carried whole and written
        # back untouched rather than dropped.
        buv = by_id.get(_first_ref(b, _UVSTREAM_ID))
        if buv is not None:
            entry['node']['uvstream'] = _node_meta(buv)
        # ParamBool is heaviest on blenders (74 of the 95 in vanilla human bodyparts).
        _set_if(entry, 'param_bools', _indexed_bools(b))
        _set_if(entry, 'mat_params', _indexed_floats(b))
        blenders.append(entry)
    return blenders


def parse_mat(text):
    """Parse a loose `.mat` (JSON text or bytes) into a normalised dict:

        { 'filename': <the material's own Filename, or ''>,
          'textures': { slot_name: cleaned_path, ... },     # base-layer-wins collapse (flat)
          'settings': { ... },                              # present settings blocks only
          'layers':   [ {textures, uv_scale, uv_offset, override_color}, ... ],  # base first
          'blenders': [ {mode, mask, channel}, ... ] }      # (#layers - 1) compositing blenders

    A layer's `override_color` (e.g. 'Multiply', or '') multiplies its albedo by the mesh's vertex
    color; a blender's `channel` (Red/Green/Blue/Alpha, or '') masks its composite with that vertex-
    color channel instead of a texture. Both are how vertex colors feed the SF shader.

    A `.mat` is a small object graph, so the PBR textures must be reached by following the
    material's layer chain -- root `LayerID` -> `MaterialID` -> `TextureSetID` -> the texture
    set's `MRTextureFile`s -- NOT by grabbing the first `MRTextureFile` in the file (which, on a
    layered material, is the *blender mask*, not the albedo). The base (first) layer wins per
    slot; later layers only fill slots the base leaves empty. Falls back to a non-blender
    MRTextureFile sweep for simple/flat materials. Returns None if the text isn't valid JSON.
    """
    if isinstance(text, (bytes, bytearray)):
        text = text.decode('utf-8-sig', 'replace')
    try:
        doc = json.loads(text)
    except (ValueError, TypeError) as e:
        log.warning(f"Could not parse .mat JSON: {e}")
        return None
    return parse_mat_doc(doc)


def parse_mat_doc(doc):
    """Same as parse_mat but for an already-parsed .mat dict (e.g. reconstructed by sf_cdb)."""
    if not isinstance(doc, dict):
        return None

    objects = doc.get('Objects', [])
    by_id = {o['ID']: o for o in objects if isinstance(o, dict) and 'ID' in o}

    # The root LayeredMaterial carries the LayerID + BlenderID components. Walk it for the full
    # layer/blender graph (P1); the flat `textures` below is the base-layer-wins collapse (P0).
    root = next((o for o in objects if _components_of(o, _LAYER_ID)), None)
    layers = _extract_layers(root, by_id) if root is not None else []
    blenders = _extract_blenders(root, by_id) if root is not None else []

    textures = {}
    for ly in layers:
        for slot, path in ly['textures'].items():
            textures.setdefault(slot, path)   # base layer wins

    # Fallback for flat/simple materials (no layer graph, or nothing resolved): sweep
    # MRTextureFile components, but skip blender objects so a blend mask isn't taken as albedo.
    if not textures:
        for o in objects:
            if _components_of(o, _BLEND_MODE):
                continue
            for slot, path in _textureset_slots(o).items():
                textures.setdefault(slot, path)

    return {'filename': doc.get('Filename', ''), 'textures': textures,
            'settings': _extract_settings(objects, root),
            'layers': layers, 'blenders': blenders}


# --- Writing loose .mat ------------------------------------------------------------------------
# The inverse of parse: turn a normalised material dict back into loose `.mat` JSON. Written
# self-contained (no template Parent) -- the ShaderModelComponent names the shader model, which is
# how the game/loose materials link to a template. Object IDs are synthetic but internally
# consistent (refs resolve within the file). Values are strings; colors are nested XMFLOAT2/4.

_SF_SLOT_INDEX = {name: idx for idx, name in SF_TEXTURE_SLOTS.items()}


def _enc_bool(b):
    return "true" if b else "false"


def _enc_float(f):
    return repr(float(f))   # repr() round-trips a Python float exactly


def _reprefix(path):
    """Re-add the `Data\\` prefix parse strips, so the written path matches the .mat convention."""
    return "Data\\" + path if path else ""


def _xmfloat(kind, values):
    """A `.mat` XMFLOAT2/4 value node: { Value: { Type: 'XMFLOATn', Data: {x,y[,z,w]} } }."""
    axes = ('x', 'y', 'z', 'w')
    return {"Value": {"Type": kind, "Data": {axes[i]: _enc_float(v) for i, v in enumerate(values)}}}


def _enc_field(value, kind):
    """Encode one component field back into the `.mat`'s string/typed-node representation."""
    if kind == 'bool':
        return _enc_bool(value)
    if kind == 'float':
        return _enc_float(value)
    if kind == 'int':
        return str(int(value))
    if kind == 'layerindex':
        return f"MATERIAL_LAYER_{int(value)}"
    if kind == 'color':
        return {"Type": _COLOR, "Data": _xmfloat("XMFLOAT4", value)}
    return value if isinstance(value, str) else str(value)


def _component_data(block, nest, fields):
    """Build a settings component's Data dict from a normalised block, per its field specs."""
    data = {}
    for f in fields:
        key, path, kind = f[0], f[1], f[2]
        value = block.get(key, _field_default(f))
        if isinstance(path, tuple):
            target = data
            for step in path[:-1]:
                wrapper = target.setdefault(step, {"Type": (nest or {}).get(step, ''), "Data": {}})
                target = wrapper["Data"]
            target[path[-1]] = _enc_field(value, kind)
        else:
            data[path] = _enc_field(value, kind)
    return data


def _settings_components(settings):
    """Rebuild the root's settings components from a normalised settings dict, for the blocks
    actually present. Driven by _COMPONENT_SPECS, so a newly modelled component is written as
    soon as it is described there."""
    comps = []
    if settings.get('shader_model'):
        comps.append({"Type": _SHADER_MODEL, "Index": 0,
                      "Data": {"FileName": settings['shader_model']}})
    for key, ctype, nest, fields in _COMPONENT_SPECS:
        block = settings.get(key)
        if block is not None:
            comps.append({"Type": ctype, "Index": 0,
                          "Data": _component_data(block, nest, fields)})
    for idx, val in sorted((settings.get('param_bools') or {}).items()):
        comps.append({"Type": _PARAM_BOOL, "Index": int(idx), "Data": {"Value": _enc_bool(val)}})
    # An LOD material reference names a whole separate material in the game's database, so it is
    # written back verbatim -- see _renamespace, which must not rewrite it.
    for idx, val in sorted((settings.get('lod_materials') or {}).items()):
        comps.append({"Type": _LOD_MATERIAL_ID, "Index": int(idx), "Data": {"ID": val}})
    return comps


def _indexed_components(node_data, key, ctype, encode):
    """Components for one indexed family ({index: value}) on a node."""
    return [{"Type": ctype, "Index": int(i), "Data": encode(v)}
            for i, v in sorted((node_data.get(key) or {}).items())]


def _tex_replace_components(layer):
    """TextureReplacement components for a layer's texture set, preserving which fields were
    present -- an entry recorded with only `enabled` is written with only Enabled."""
    comps = []
    for idx, rep in sorted((layer.get('tex_replace') or {}).items()):
        data = {}
        if 'enabled' in rep:
            data['Enabled'] = _enc_bool(rep['enabled'])
        if 'color' in rep:
            data['Color'] = {"Type": _COLOR, "Data": _xmfloat("XMFLOAT4", rep['color'])}
        comps.append({"Type": _TEX_REPLACE, "Index": int(idx), "Data": data})
    return comps


def _textureset_extras(layer):
    """The non-texture components a layer's TextureSet carries."""
    comps = _indexed_components(layer, 'mat_params', _PARAM_FLOAT,
                               lambda v: {"Value": _enc_float(v)})
    comps += _tex_replace_components(layer)
    if layer.get('mip_bias') is not None:
        comps.append({"Type": 'BSMaterial::MipBiasSetting', "Index": 0,
                      "Data": {"DisableMipBiasHint": _enc_bool(layer['mip_bias'])}})
    if layer.get('tex_resolution') is not None:
        comps.append({"Type": 'BSMaterial::TextureResolutionSetting', "Index": 0,
                      "Data": {"ResolutionHint": layer['tex_resolution']}})
    return comps


def _material_extras(layer):
    """The non-reference components a layer's Material carries."""
    comps = _indexed_components(layer, 'param_bools', _PARAM_BOOL,
                               lambda v: {"Value": _enc_bool(v)})
    if layer.get('color') is not None:
        comps.append({"Type": _COLOR, "Index": 0, "Data": _xmfloat("XMFLOAT4", layer['color'])})
    return comps


def _blender_extras(blender):
    """The indexed knob components a blender carries."""
    return (_indexed_components(blender, 'param_bools', _PARAM_BOOL,
                                lambda v: {"Value": _enc_bool(v)})
            + _indexed_components(blender, 'mat_params', _PARAM_FLOAT,
                                  lambda v: {"Value": _enc_float(v)}))


def _mat_basename(fn):
    """The material's short name (for CTName labels), from its `.mat` path stem."""
    stem = (fn or 'material').replace('/', '\\').split('\\')[-1]
    if stem.lower().endswith('.mat'):
        stem = stem[:-4]
    return stem or 'material'


def _id_namespace(fn):
    """A per-material 64-bit id namespace (`res:` words 2 and 3) derived deterministically from the
    material path. Mirrors vanilla, where nodes of one material share words 2-3 and vary word 1 --
    so a differently-named material gets a disjoint namespace and its `res:` ids never collide with
    another's in the material database. Deterministic (not random) so re-exports diff cleanly."""
    h = hashlib.sha256((fn or 'material').lower().replace('/', '\\').encode('utf-8')).digest()
    return int.from_bytes(h[0:4], 'big'), int.from_bytes(h[4:8], 'big')


def _renamespace(doc, filename):
    """Give every object in `doc` a fresh `res:` id in `filename`'s namespace, rewriting the
    references that point at them. A material copied from a vanilla one must not keep the
    vanilla ids: they identify the material in the game's database, so a duplicate id collides
    with the original. References live in component `Data.ID` fields."""
    ns_hi, ns_lo = _id_namespace(filename)
    remap = {}
    for i, o in enumerate(doc.get('Objects', [])):
        old = o.get('ID')
        if not isinstance(old, str) or not old:
            continue
        w1 = (ns_hi ^ (((i + 1) * 0x9E3779B1) & 0xFFFFFFFF)) & 0xFFFFFFFF
        remap[old] = f"res:{w1:08X}:{ns_hi:08X}:{ns_lo:08X}"
    for o in doc.get('Objects', []):
        if o.get('ID') in remap:
            o['ID'] = remap[o['ID']]
        for c in o.get('Components', []):
            d = c.get('Data')
            if isinstance(d, dict) and d.get('ID') in remap:
                d['ID'] = remap[d['ID']]
    return doc


def _rename_ctnames(doc, new_base, old_base=None):
    """Retarget the source material's CTNames onto the new material's base name, so a copy of
    `male_default` doesn't announce itself as `male_default` (names identify nodes alongside
    the ids). Suffixes like '_Layer1' are kept, and a node whose name came from somewhere else
    (a shader-model template) is left alone."""
    if old_base is None:
        # The material's own name is the ROOT's name. Guessing it as the shortest CTName in the
        # document goes wrong whenever a node keeps a name inherited from the shader-model
        # template: 'Eye1Layer_Layer3' is shorter than 'bloodshot_left_eye', so that layer was
        # taken to be the material and renamed on top of it.
        root = next((o for o in doc.get('Objects', []) if _components_of(o, _LAYER_ID)), None)
        old_base = _ctname_of(root) if root is not None else ''
    if not old_base:
        return doc
    for o in doc.get('Objects', []):
        for c in o.get('Components', []):
            if c.get('Type') == _CTNAME:
                d = c.setdefault('Data', {})
                nm = d.get('Name', '')
                if nm == old_base:
                    d['Name'] = new_base
                elif nm.startswith(old_base):
                    d['Name'] = new_base + nm[len(old_base):]
    return doc


def _set_component(obj, ctype, index, data):
    """Merge `data` into the first component of `ctype`/`index` on `obj`, appending one if absent.

    MERGE, not replace: a `.mat` component carries every field of its class, but PyNifly models
    only some of them (LayeredEmissivityComponent alone has 17 fields to our 4). Replacing the
    Data dict dropped the rest -- 969 authored field values across the 36 vanilla human materials.
    Callers pass only the fields they mean to change; everything else is left as it was."""
    for c in obj.get('Components', []):
        if c.get('Type') == ctype and c.get('Index', 0) == index:
            existing = c.get('Data')
            if isinstance(existing, dict) and isinstance(data, dict):
                _merge_data(existing, data)
            else:
                c['Data'] = data
            return
    obj.setdefault('Components', []).append({"Type": ctype, "Index": index, "Data": data})


def _merge_data(existing, new):
    """Merge one component Data dict into another, recursing into typed sub-nodes so a nested
    wrapper keeps the fields we don't write (translucency nests its params inside a `Settings`
    node; replacing that node wholesale lost SSSStrength/SSSWidth/TransmissiveScale)."""
    for k, v in new.items():
        old = existing.get(k)
        if (isinstance(old, dict) and isinstance(v, dict)
                and isinstance(old.get('Data'), dict) and isinstance(v.get('Data'), dict)):
            _merge_data(old['Data'], v['Data'])
        else:
            existing[k] = v


def _has_field(data, path):
    """Is this field physically present in a component's Data (following typed wrappers)?"""
    if isinstance(path, tuple):
        for step in path[:-1]:
            if not isinstance(data, dict) or step not in data:
                return False
            data = (data.get(step) or {}).get('Data') or {}
        path = path[-1]
    return isinstance(data, dict) and path in data


def _patch_component(obj, ctype, index, block, nest, fields):
    """Write a settings block onto an existing component, writing only the fields that actually
    say something new: one the source already carries whose value has changed, or one the source
    omits whose value differs from the field's declared default.

    Leaving unchanged fields alone keeps a patched material byte-stable -- re-encoding a value we
    never touched rewrites `6500` as `6500.0`, which is the same number but a gratuitous diff.
    Writing a field the source omitted is what keeps an edit alive: switch on a flag the source
    never mentioned and it still lands."""
    existing = None
    for c in obj.get('Components', []):
        if c.get('Type') == ctype and c.get('Index', 0) == index:
            existing = c.get('Data')
            break
    if existing is None:
        # A component the node didn't have. Its mere presence is meaningful -- a material WITH an
        # AlphaSettingsComponent at its defaults is not the same as one without -- so it is stated
        # in full rather than dropped for having nothing that differs from a default.
        _set_component(obj, ctype, index, _component_data(block, nest, fields))
        return
    wanted = []
    for f in fields:
        default = _field_default(f)
        value = block.get(f[0], default)
        if _has_field(existing, f[1]):
            if not _values_equal(value, _read_field(existing, f[1], f[2], default)):
                wanted.append(f)
        elif not _values_equal(value, default):
            wanted.append(f)
    if wanted:
        _set_component(obj, ctype, index, _component_data(block, nest, wanted))


def _values_equal(a, b):
    """Compare two decoded field values, tolerating float representation."""
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return len(a) == len(b) and all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9
    return a == b


def patch_mat_doc(doc, data, filename=None):
    """Patch the values PyNifly models into an existing `.mat` document, leaving everything else
    untouched, then re-namespace it for `filename`.

    Building a `.mat` from scratch drops every component outside the normalised dict --
    ParamBool, MaterialParamFloat, TextureReplacement and the detail UVStreams that vanilla skin
    materials rely on. Patching keeps them: the document on disk (or the one the material was
    imported from) is the base, and only the layers/blenders/settings the shader graph actually
    describes are overwritten.
    """
    doc = copy.deepcopy(doc)
    objects = doc.get('Objects', [])
    by_id = {o['ID']: o for o in objects if isinstance(o, dict) and 'ID' in o}
    root = next((o for o in objects if _components_of(o, _LAYER_ID)), None)
    if root is None:
        return None

    for i, ly in enumerate(data.get('layers', [])):
        lc = next((c for c in _components_of(root, _LAYER_ID) if c.get('Index', 0) == i), None)
        layer = by_id.get((lc.get('Data') or {}).get('ID')) if lc else None
        if layer is None:
            continue
        mat = by_id.get(_first_ref(layer, _MATERIAL_ID))
        texset = by_id.get(_first_ref(mat, _TEXTURESET_ID)) if mat else None
        if texset is not None:
            for slot, path in (ly.get('textures') or {}).items():
                if slot in _SF_SLOT_INDEX:
                    _set_component(texset, _TEXTURE_FILE_TYPE, _SF_SLOT_INDEX[slot],
                                   {"FileName": _reprefix(path)})
            for c in _textureset_extras(ly):
                _set_component(texset, c['Type'], c['Index'], c['Data'])
        if mat is not None and ly.get('override_color'):
            _set_component(mat, _OVERRIDE_COLOR, 0, {"Value": ly['override_color']})
        if mat is not None:
            for c in _material_extras(ly):
                _set_component(mat, c['Type'], c['Index'], c['Data'])
        # UV tiling lives on the layer's own UVStream (falling back to its material's), which is
        # also where the detail-layer streams the template carries live -- patch, never rebuild.
        uv_host = layer if _first_ref(layer, _UVSTREAM_ID) else (mat or layer)
        uv = by_id.get(_first_ref(uv_host, _UVSTREAM_ID))
        if uv is not None:
            # Only write a tiling component the stream already had, or one that says something --
            # a UV stream with no Scale is tiled 1:1, and writing an explicit identity Scale onto
            # all 48 of them (plus 65 identity Offsets) is noise, not fidelity.
            scale = tuple(ly.get('uv_scale', (1.0, 1.0)))
            offset = tuple(ly.get('uv_offset', (0.0, 0.0)))
            if scale != (1.0, 1.0) or _components_of(uv, _UV_SCALE):
                _set_component(uv, _UV_SCALE, 0, _xmfloat("XMFLOAT2", scale))
            if offset != (0.0, 0.0) or _components_of(uv, _UV_OFFSET):
                _set_component(uv, _UV_OFFSET, 0, _xmfloat("XMFLOAT2", offset))

    for i, b in enumerate(data.get('blenders', [])):
        bc = next((c for c in _components_of(root, _BLENDER_ID) if c.get('Index', 0) == i), None)
        bl = by_id.get((bc.get('Data') or {}).get('ID')) if bc else None
        if bl is None:
            continue
        if b.get('mode'):
            _set_component(bl, _BLEND_MODE, 0, {"Value": b['mode']})
        if b.get('mask'):
            _set_component(bl, _TEXTURE_FILE_TYPE, 0, {"FileName": _reprefix(b['mask'])})
        if b.get('channel'):
            _set_component(bl, _COLOR_CHANNEL, 0, {"Value": b['channel']})
        for c in _blender_extras(b):
            _set_component(bl, c['Type'], c['Index'], c['Data'])

    # Settings go on through the field-by-field patcher, so a component's unmodelled fields (and
    # a material's deliberately-short field lists) survive; the indexed families are whole-value
    # components, so they are simply set.
    settings = data.get('settings', {})
    if settings.get('shader_model'):
        _set_component(root, _SHADER_MODEL, 0, {"FileName": settings['shader_model']})
    for key, ctype, nest, fields in _COMPONENT_SPECS:
        block = settings.get(key)
        if block is not None:
            _patch_component(root, ctype, 0, block, nest, fields)
    for idx, val in sorted((settings.get('param_bools') or {}).items()):
        _set_component(root, _PARAM_BOOL, int(idx), {"Value": _enc_bool(val)})
    for idx, val in sorted((settings.get('lod_materials') or {}).items()):
        _set_component(root, _LOD_MATERIAL_ID, int(idx), {"ID": val})

    fn = filename or data.get('filename') or doc.get('Filename') or ''
    if fn:
        _rename_ctnames(doc, _mat_basename(fn))
        _renamespace(doc, fn)
        doc['Filename'] = fn
    return doc


def build_mat_doc(data, filename=None):
    """Build a complete `.mat` document from a normalised material dict.

    THE NODE TREE IS THE MATERIAL. Every object is emitted from what the dict says, in the order
    the dict lists it -- so a layer added in Blender is written like any other, which patching an
    existing document could never do (it looked each layer up in the source and skipped what wasn't
    there). Nothing is consulted on disk.

    Each node keeps the identity and inheritance it was imported with, from `nodes`/`node` entries:
    its `res:` id, its `Parent`, its `CTName`, and the components it carried. The modelled values
    are MERGED over those carried components, so an unmodelled component survives whole and an
    unmodelled FIELD of a modelled component survives too. A node with no such entry is new (added
    in Blender, or the whole material authored from scratch) and gets a fresh id and the shipped
    Root template for its kind as its Parent. Ids are then re-namespaced for `filename`, so a
    material derived from a vanilla one can't collide with it in the game's material database.
    """
    fn = filename or data.get('filename') or ''
    base = _mat_basename(fn)
    ns_hi, ns_lo = _id_namespace(fn)
    objects = []
    counter = [0]

    def new_id():
        # word 1 mixes the node counter with the namespace (golden-ratio odd multiplier -> a
        # bijection mod 2^32, so distinct counters give distinct, hash-looking words, never a
        # 0000000N placeholder).
        counter[0] += 1
        w1 = (ns_hi ^ ((counter[0] * 0x9E3779B1) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return f"res:{w1:08X}:{ns_hi:08X}:{ns_lo:08X}"

    def emit(meta, default_parent, default_name, comps, refs=()):
        """Append one node, preferring the identity and components it was imported with.

        `comps` are the modelled values, merged over what the node carried; `refs` are the
        structural references, which are always regenerated. Returns the node's id."""
        meta = meta or {}
        holder = {"Components": [copy.deepcopy(c) for c in (meta.get('components') or [])]}
        for c in comps:
            _set_component(holder, c['Type'], c.get('Index', 0), c['Data'])
        obj = {"Components": ([{"Type": _CTNAME, "Index": 0,
                                "Data": {"Name": meta.get('name') or default_name}}]
                              + holder['Components'] + list(refs)),
               "ID": meta.get('id') or new_id()}
        parent = meta.get('parent') or default_parent
        if parent:
            obj["Parent"] = parent
        objects.append(obj)
        return obj["ID"]

    settings = data.get('settings') or {}
    root_meta = settings.get('node') or {}
    root_refs = []

    def uv_node(meta, ly, default_name):
        """Emit a layer's UV stream, if it has one. A stream with no Scale is tiled 1:1, so an
        identity Scale is only written when the stream already stated one."""
        scale = tuple(ly.get('uv_scale', (1.0, 1.0)))
        offset = tuple(ly.get('uv_offset', (0.0, 0.0)))
        if not (meta or scale != (1.0, 1.0) or offset != (0.0, 0.0)):
            return None
        comps = []
        if scale != (1.0, 1.0) or _meta_has(meta, _UV_SCALE):
            comps.append({"Type": _UV_SCALE, "Index": 0, "Data": _xmfloat("XMFLOAT2", scale)})
        if offset != (0.0, 0.0) or _meta_has(meta, _UV_OFFSET):
            comps.append({"Type": _UV_OFFSET, "Index": 0, "Data": _xmfloat("XMFLOAT2", offset)})
        return emit(meta, _PARENT_UVSTREAM, default_name, comps)

    for i, ly in enumerate(data.get('layers', [])):
        nodes = ly.get('nodes') or {}
        ts_comps = [{"Type": _TEXTURE_FILE_TYPE, "Index": _SF_SLOT_INDEX[slot],
                     "Data": {"FileName": _reprefix(path)}}
                    for slot, path in ly.get('textures', {}).items() if slot in _SF_SLOT_INDEX]
        ts_comps += _textureset_extras(ly)
        ts_id = emit(nodes.get('textureset'), _PARENT_TEXTURESET,
                     f"{base}_TextureSet{i + 1}", ts_comps)

        uv_id = uv_node(nodes.get('uvstream'), ly, f"{base}_UVStream{i + 1}")
        # The stream hangs off whichever object owned it in the source (the layer, or its
        # material); a brand-new layer hangs it off the layer.
        uv_on_material = uv_id is not None and (nodes.get('material') or {}).get('owns_uvstream')

        mat_comps = []
        if ly.get('override_color'):
            mat_comps.append({"Type": _OVERRIDE_COLOR, "Index": 0,
                              "Data": {"Value": ly['override_color']}})
        mat_comps += _material_extras(ly)
        mat_refs = [{"Type": _TEXTURESET_ID, "Index": 0, "Data": {"ID": ts_id}}]
        if uv_on_material:
            mat_refs.append({"Type": _UVSTREAM_ID, "Index": 0, "Data": {"ID": uv_id}})
        mat_id = emit(nodes.get('material'), _PARENT_MATERIAL, f"{base}_Material{i + 1}",
                      mat_comps, mat_refs)

        layer_refs = [{"Type": _MATERIAL_ID, "Index": 0, "Data": {"ID": mat_id}}]
        if uv_id is not None and not uv_on_material:
            layer_refs.append({"Type": _UVSTREAM_ID, "Index": 0, "Data": {"ID": uv_id}})
        layer_id = emit(nodes.get('layer'), _PARENT_LAYER, f"{base}_Layer{i + 1}", [], layer_refs)
        root_refs.append({"Type": _LAYER_ID, "Index": i, "Data": {"ID": layer_id}})

    for i, b in enumerate(data.get('blenders', [])):
        bmeta = b.get('node') or {}
        bcomps = []
        if b.get('mode') or _meta_has(bmeta, _BLEND_MODE):
            bcomps.append({"Type": _BLEND_MODE, "Index": 0, "Data": {"Value": b.get('mode', '')}})
        if b.get('mask'):
            bcomps.append({"Type": _TEXTURE_FILE_TYPE, "Index": 0,
                           "Data": {"FileName": _reprefix(b['mask'])}})
        if b.get('channel'):
            bcomps.append({"Type": _COLOR_CHANNEL, "Index": 0, "Data": {"Value": b['channel']}})
        bcomps += _blender_extras(b)
        # A blender's own UV stream is carried whole -- PyNifly doesn't model its tiling.
        brefs = []
        if bmeta.get('uvstream'):
            buv = emit(bmeta['uvstream'], _PARENT_UVSTREAM, f"{base}_BlenderUVStream{i + 1}", [])
            brefs.append({"Type": _UVSTREAM_ID, "Index": 0, "Data": {"ID": buv}})
        blend_id = emit(bmeta, _PARENT_BLENDER, f"{base}_Blender{i + 1}", bcomps, brefs)
        root_refs.append({"Type": _BLENDER_ID, "Index": i, "Data": {"ID": blend_id}})

    for idx, val in sorted((settings.get('lod_materials') or {}).items()):
        root_refs.append({"Type": _LOD_MATERIAL_ID, "Index": int(idx), "Data": {"ID": val}})

    # The root's settings go on through the field-by-field patcher, over whatever it carried.
    root_holder = {"Components": [copy.deepcopy(c) for c in (root_meta.get('components') or [])]}
    if settings.get('shader_model'):
        _set_component(root_holder, _SHADER_MODEL, 0, {"FileName": settings['shader_model']})
    for key, ctype, nest, fields in _COMPONENT_SPECS:
        block = settings.get(key)
        if block is not None:
            _patch_component(root_holder, ctype, 0, block, nest, fields)
    for idx, val in sorted((settings.get('param_bools') or {}).items()):
        _set_component(root_holder, _PARAM_BOOL, int(idx), {"Value": _enc_bool(val)})

    root = {"Components": ([{"Type": _CTNAME, "Index": 0,
                             "Data": {"Name": root_meta.get('name') or base}}]
                           + root_holder['Components'] + root_refs),
            "Parent": root_meta.get('parent') or _PARENT_LAYEREDMATERIAL}
    if root_meta.get('id'):
        root["ID"] = root_meta['id']
    objects.insert(0, root)

    doc = {"Version": 1, "Objects": objects}
    if fn:
        doc["Filename"] = fn
        _rename_ctnames(doc, base, root_meta.get('name'))
        _renamespace(doc, fn)
    return doc


def material_content(data):
    """A normalised material dict with the carried node IDENTITY stripped -- the textures, tiling,
    settings and knobs, without the `res:` ids, Parent links and carried components that say where
    a node came from. What two materials should be compared on when the question is "do these
    describe the same material", not "is this the same file"."""
    out = {k: v for k, v in data.items() if k != 'settings'}
    out['settings'] = {k: v for k, v in (data.get('settings') or {}).items() if k != 'node'}
    out['layers'] = [{k: v for k, v in ly.items() if k != 'nodes'} for ly in data.get('layers', [])]
    out['blenders'] = [{k: v for k, v in b.items() if k != 'node'} for b in data.get('blenders', [])]
    return out


def _meta_has(meta, ctype):
    """Did the source object behind this node carry a component of `ctype`? Used to tell "the
    source stated this explicitly" from "the source left it at its class default"."""
    return any(c.get('Type') == ctype for c in (meta or {}).get('components') or [])


def write_mat(data, filename=None, template=None):
    """Serialize a normalised material dict (as parse_mat returns) to a GAME-VALID loose `.mat`.

    The document is built from the dict -- see build_mat_doc. `template` is accepted for callers
    that still pass the source document, but it is no longer needed: the identity, parenting and
    unmodelled components a template used to supply now travel with the material itself, and a
    template can only describe the material as it was BEFORE the user edited the node tree."""
    if template is not None and not (data.get('settings') or {}).get('node'):
        # A dict with no carried node identity never came from an import, so a template is the
        # only source of the scaffolding. (Materials authored in Blender have nothing to preserve.)
        patched = patch_mat_doc(template, data, filename)
        if patched is not None:
            return json.dumps(patched, indent=2)
    return json.dumps(build_mat_doc(data, filename), indent=2)


_cdb_cache = {}   # cdb path -> CdbFile (or False if it failed to load)


def material_textures_from_cdb(cdb_path, mat_ref):
    """Read a material straight from Starfield's `materialsbeta.cdb` (bypassing loose `.mat`
    files) and return its normalised `{slot: path}` textures, or None if the cdb can't be read
    or the material isn't in it. The parsed database is cached per path, so the one-time
    component scan is paid only once across an import."""
    cdb = _cdb_cache.get(cdb_path)
    if cdb is None:
        from . import sf_cdb
        try:
            cdb = sf_cdb.load_cdb(cdb_path)
        except Exception as e:
            log.warning(f"Could not read material database '{cdb_path}': {e}")
            _cdb_cache[cdb_path] = False
            return None
        _cdb_cache[cdb_path] = cdb
    if cdb is False:
        return None
    mat = cdb.get_material(mat_ref)
    if mat is None:
        return None
    parsed = parse_mat_doc(mat)
    return parsed['textures'] if parsed else None


def material_from_cdb(cdb_path, mat_ref):
    """Like material_textures_from_cdb but returns the FULL parsed dict (textures + settings +
    layers + blenders), or None. Shares the per-path cache."""
    cdb = _cdb_cache.get(cdb_path)
    if cdb is None:
        from . import sf_cdb
        try:
            cdb = sf_cdb.load_cdb(cdb_path)
        except Exception as e:
            log.warning(f"Could not read material database '{cdb_path}': {e}")
            _cdb_cache[cdb_path] = False
            return None
        _cdb_cache[cdb_path] = cdb
    if cdb is False:
        return None
    mat = cdb.get_material(mat_ref)
    return parse_mat_doc(mat) if mat is not None else None
