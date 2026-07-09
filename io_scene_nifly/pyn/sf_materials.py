"""Starfield layered `.mat` material reading.

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


def _iter_components(doc):
    """Yield every component dict across all objects in a parsed `.mat` document, in document
    order (so the first-declared layer's texture set wins for a given slot)."""
    for obj in doc.get('Objects', []):
        for comp in obj.get('Components', []):
            yield comp


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

    Texture slots are taken from the first `MRTextureFile` that supplies a non-empty FileName for
    a given index (the first-declared layer dominates). Returns None if the text isn't valid JSON.
    """
    if isinstance(text, (bytes, bytearray)):
        text = text.decode('utf-8-sig', 'replace')
    try:
        doc = json.loads(text)
    except (ValueError, TypeError) as e:
        log.warning(f"Could not parse .mat JSON: {e}")
        return None

    textures = {}
    for comp in _iter_components(doc):
        if comp.get('Type') != _TEXTURE_FILE_TYPE:
            continue
        idx = comp.get('Index')
        slot = SF_TEXTURE_SLOTS.get(idx)
        if slot is None or slot in textures:
            continue  # unknown slot, or an earlier layer already filled it
        path = _clean_texture_path((comp.get('Data') or {}).get('FileName'))
        if path:
            textures[slot] = path

    return {'filename': doc.get('Filename', '') if isinstance(doc, dict) else '',
            'textures': textures}
