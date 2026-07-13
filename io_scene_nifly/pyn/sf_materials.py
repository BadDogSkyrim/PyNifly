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


_LAYER_ID = 'BSMaterial::LayerID'
_MATERIAL_ID = 'BSMaterial::MaterialID'
_TEXTURESET_ID = 'BSMaterial::TextureSetID'
_BLEND_MODE = 'BSMaterial::BlendModeComponent'
_BLENDER_ID = 'BSMaterial::BlenderID'
_UVSTREAM_ID = 'BSMaterial::UVStreamID'
_UV_SCALE = 'BSMaterial::Scale'
_UV_OFFSET = 'BSMaterial::Offset'

_SHADER_MODEL = 'BSMaterial::ShaderModelComponent'
_TRANSLUCENCY = 'BSMaterial::TranslucencySettingsComponent'
_EMISSIVITY = 'BSMaterial::LayeredEmissivityComponent'
_ALPHA_SETTINGS = 'BSMaterial::AlphaSettingsComponent'


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


def _extract_settings(objects):
    """Pull the material's settings-component params into a normalised, round-trippable dict.

    Only blocks that are actually present are included, so callers test membership. Values are
    decoded out of the `.mat`'s string/typed-node representation into plain Python
    (bool/float/tuple). Covers the P0 shader-plan settings: shader-model identity, translucency
    (SSS), and layered emissivity. Alpha settings are added once a real sample is in hand."""
    settings = {}

    sm = _first_component_data(objects, _SHADER_MODEL)
    if sm and sm.get('FileName'):
        settings['shader_model'] = sm['FileName']

    tr = _first_component_data(objects, _TRANSLUCENCY)
    if tr is not None:
        inner = (tr.get('Settings') or {}).get('Data') or {}
        settings['translucency'] = {
            'enabled': _as_bool(tr.get('Enabled')),
            'use_sss': _as_bool(inner.get('UseSSS')),
            'spec_lobe0_roughness': _as_float(inner.get('SpecLobe0RoughnessScale'), 1.0),
            'spec_lobe1_roughness': _as_float(inner.get('SpecLobe1RoughnessScale'), 1.0),
        }

    em = _first_component_data(objects, _EMISSIVITY)
    if em is not None:
        tint = (em.get('FirstLayerTint') or {}).get('Data')
        settings['emissive'] = {
            'enabled': _as_bool(em.get('Enabled')),
            'first_layer_index': _layer_index(em.get('FirstLayerIndex')),
            'blender_mode': em.get('FirstBlenderMode', ''),
            'tint': _decode_xmfloat(tint),
        }

    # AlphaSettingsComponent is just HasOpacity (does the surface use alpha) + an alpha-test
    # clip threshold. SF has no none/test/blend mode here -- alpha is an opacity map (slot 2)
    # clipped at the threshold. The cdb only stores changed fields, so a material that leaves
    # AlphaTestThreshold at its class default won't list it -> default to 0.5.
    al = _first_component_data(objects, _ALPHA_SETTINGS)
    if al is not None:
        settings['alpha'] = {
            'has_opacity': _as_bool(al.get('HasOpacity')),
            'threshold': _as_float(al.get('AlphaTestThreshold'), 0.5),
        }

    return settings


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
        layers.append({'textures': _textureset_slots(texset) if texset else {},
                       'uv_scale': scale, 'uv_offset': offset})
    return layers


def _extract_blenders(root, by_id):
    """The material's blenders in order. Blender k composites layer k+1 over the running
    composite: it carries a BlendModeComponent (Skin/Lerp/Additive/...) and, usually, a mask
    MRTextureFile. There are (#layers - 1) of them."""
    blenders = []
    for bc in sorted(_components_of(root, _BLENDER_ID), key=lambda c: c.get('Index', 0)):
        b = by_id.get((bc.get('Data') or {}).get('ID'))
        if not b:
            continue
        mode, mask = '', ''
        for c in b.get('Components', []):
            if c.get('Type') == _BLEND_MODE:
                mode = (c.get('Data') or {}).get('Value', '') or mode
            elif c.get('Type') == _TEXTURE_FILE_TYPE:
                mask = _clean_texture_path((c.get('Data') or {}).get('FileName')) or mask
        blenders.append({'mode': mode, 'mask': mask})
    return blenders


def parse_mat(text):
    """Parse a loose `.mat` (JSON text or bytes) into a normalised dict:

        { 'filename': <the material's own Filename, or ''>,
          'textures': { slot_name: cleaned_path, ... },     # base-layer-wins collapse (flat)
          'settings': { ... },                              # present settings blocks only
          'layers':   [ {textures, uv_scale, uv_offset}, ... ],   # full layer graph, base first
          'blenders': [ {mode, mask}, ... ] }               # (#layers - 1) compositing blenders

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
            'settings': _extract_settings(objects),
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


def _settings_components(settings):
    """Rebuild the settings components (ShaderModel / Translucency / Emissive / Alpha) that
    _extract_settings reads, for the ones present in `settings`."""
    comps = []
    if settings.get('shader_model'):
        comps.append({"Type": _SHADER_MODEL, "Index": 0,
                      "Data": {"FileName": settings['shader_model']}})
    tr = settings.get('translucency')
    if tr is not None:
        comps.append({"Type": _TRANSLUCENCY, "Index": 0, "Data": {
            "Enabled": _enc_bool(tr['enabled']),
            "Settings": {"Type": "BSMaterial::TranslucencySettings", "Data": {
                "UseSSS": _enc_bool(tr['use_sss']),
                "SpecLobe0RoughnessScale": _enc_float(tr['spec_lobe0_roughness']),
                "SpecLobe1RoughnessScale": _enc_float(tr['spec_lobe1_roughness'])}}}})
    em = settings.get('emissive')
    if em is not None:
        comps.append({"Type": _EMISSIVITY, "Index": 0, "Data": {
            "Enabled": _enc_bool(em['enabled']),
            "FirstLayerIndex": f"MATERIAL_LAYER_{em['first_layer_index']}",
            "FirstBlenderMode": em['blender_mode'],
            "FirstLayerTint": {"Type": "BSMaterial::Color",
                               "Data": _xmfloat("XMFLOAT4", em['tint'])}}})
    al = settings.get('alpha')
    if al is not None:
        comps.append({"Type": _ALPHA_SETTINGS, "Index": 0, "Data": {
            "HasOpacity": _enc_bool(al['has_opacity']),
            "AlphaTestThreshold": _enc_float(al['threshold'])}})
    return comps


def write_mat(data, filename=None):
    """Serialize a normalised material dict (as parse_mat returns) back to loose `.mat` JSON text.
    Round-trips: parse_mat(write_mat(d)) reproduces d's textures/settings/layers/blenders."""
    objects = []
    counter = [0]

    def new_id():
        counter[0] += 1
        return f"res:{counter[0]:08X}:00000000:00000000"

    root = []   # the root LayeredMaterial's components (LayerID/BlenderID refs + settings)

    for i, ly in enumerate(data.get('layers', [])):
        layer_id, mat_id, ts_id = new_id(), new_id(), new_id()
        root.append({"Type": _LAYER_ID, "Index": i, "Data": {"ID": layer_id}})
        ts_comps = [{"Type": _TEXTURE_FILE_TYPE, "Index": _SF_SLOT_INDEX[slot],
                     "Data": {"FileName": _reprefix(path)}}
                    for slot, path in ly.get('textures', {}).items() if slot in _SF_SLOT_INDEX]
        objects.append({"ID": ts_id, "Components": ts_comps})
        objects.append({"ID": mat_id, "Components":
                        [{"Type": _TEXTURESET_ID, "Index": 0, "Data": {"ID": ts_id}}]})
        layer_comps = [{"Type": _MATERIAL_ID, "Index": 0, "Data": {"ID": mat_id}}]
        scale = tuple(ly.get('uv_scale', (1.0, 1.0)))
        offset = tuple(ly.get('uv_offset', (0.0, 0.0)))
        if scale != (1.0, 1.0) or offset != (0.0, 0.0):
            uv_id = new_id()
            uv_comps = []
            if scale != (1.0, 1.0):
                uv_comps.append({"Type": _UV_SCALE, "Index": 0, "Data": _xmfloat("XMFLOAT2", scale)})
            if offset != (0.0, 0.0):
                uv_comps.append({"Type": _UV_OFFSET, "Index": 0, "Data": _xmfloat("XMFLOAT2", offset)})
            objects.append({"ID": uv_id, "Components": uv_comps})
            layer_comps.append({"Type": _UVSTREAM_ID, "Index": 0, "Data": {"ID": uv_id}})
        objects.append({"ID": layer_id, "Components": layer_comps})

    for i, b in enumerate(data.get('blenders', [])):
        blend_id = new_id()
        root.append({"Type": _BLENDER_ID, "Index": i, "Data": {"ID": blend_id}})
        bcomps = [{"Type": _BLEND_MODE, "Index": 0, "Data": {"Value": b.get('mode', '')}}]
        if b.get('mask'):
            bcomps.append({"Type": _TEXTURE_FILE_TYPE, "Index": 0,
                           "Data": {"FileName": _reprefix(b['mask'])}})
        objects.append({"ID": blend_id, "Components": bcomps})

    root.extend(_settings_components(data.get('settings', {})))
    objects.insert(0, {"Components": root})

    doc = {"Version": 1, "Objects": objects}
    fn = filename or data.get('filename')
    if fn:
        doc["Filename"] = fn
    return json.dumps(doc, indent=2)


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
