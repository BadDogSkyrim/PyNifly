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


def _components_of(obj, ctype):
    return [c for c in obj.get('Components', []) if c.get('Type') == ctype]


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


def parse_mat(text):
    """Parse a loose `.mat` (JSON text or bytes) into a normalised dict:

        { 'filename': <the material's own Filename, or ''>,
          'textures': { slot_name: cleaned_path, ... } }   # only non-empty slots

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
    if not isinstance(doc, dict):
        return None

    objects = doc.get('Objects', [])
    by_id = {o['ID']: o for o in objects if isinstance(o, dict) and 'ID' in o}

    textures = {}
    # Primary path: walk the layer graph from the root LayeredMaterial (the object carrying the
    # LayerID components), base layer first.
    root = next((o for o in objects if _components_of(o, _LAYER_ID)), None)
    if root is not None:
        layers = sorted(_components_of(root, _LAYER_ID), key=lambda c: c.get('Index', 0))
        for lc in layers:
            layer = by_id.get((lc.get('Data') or {}).get('ID'))
            if not layer:
                continue
            mat = by_id.get(_first_ref(layer, _MATERIAL_ID))
            if not mat:
                continue
            texset = by_id.get(_first_ref(mat, _TEXTURESET_ID))
            if not texset:
                continue
            for slot, path in _textureset_slots(texset).items():
                textures.setdefault(slot, path)   # base layer wins

    # Fallback for flat/simple materials (no layer graph, or nothing resolved): sweep
    # MRTextureFile components, but skip blender objects so a blend mask isn't taken as albedo.
    if not textures:
        for o in objects:
            if _components_of(o, _BLEND_MODE):
                continue
            for slot, path in _textureset_slots(o).items():
                textures.setdefault(slot, path)

    return {'filename': doc.get('Filename', ''), 'textures': textures}
