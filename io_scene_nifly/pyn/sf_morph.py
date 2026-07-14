r"""Starfield facial morph (`morph.dat`) reading and writing.

Starfield stores facial/body morph targets in binary `morph.dat` files (magic ``MDAT``),
one per mesh part, at paths like ``meshes/morphs/human/female/chargen/head/morph.dat``.
A ``morph.dat`` is a set of NAMED per-vertex position deltas over a base mesh -- the same
data Blender models as **shape keys**. Two flavours share the identical format:

* ``chargen`` -- creator sliders / phenotype presets (e.g. ``female_af_md1_Chin``, ``Thin``).
* ``performance`` -- FACS action units driving expression + lip-sync (``jawOpen``, ``browLowererL``).

nifly has no morph support, so this is a standalone pure-Python codec (Blender-independent, so it
unit-tests at the pyn layer). Reference format: SesamePaste233/StarfieldMeshConverter
(``src/MorphIO.cpp``) + Outfit Studio ``SFMorphFile``; verified byte-exact against vanilla
2026-07-14.

Binary layout (little-endian)::

    "MDAT"                         4 bytes magic
    num_axis        u32            == 3
    num_vertices    u32
    num_shape_keys  u32
    num_shape_keys x [ u32 len + utf8 name ]
    num_morph_data  u32
    num_offsets     u32            == num_vertices
    num_morph_data x morph_data (16 bytes each):
        u16 offset[3]              position delta, half-float, METRIC (.mesh units)
        u16 target_vert_color      single scalar, /65535
        u32 normal                 delta normal, DEC3N signed
        u32 tangent                delta tangent, DEC3N signed
    num_offsets x IOffset (20 bytes each):
        u32 start                  index into morph_data where this vertex's run begins
        u32 marker[4]              128-bit field; bit k set => shape key k deforms this vertex

The record array is **dense over vertices** (one IOffset each) but **sparse over keys**: a vertex
only carries records for the keys that actually move it. The set marker bits, enumerated in
ascending order, map 1:1 to that vertex's consecutive ``morph_data`` records.

Position deltas are metric (raw ``.mesh`` units); multiply by ``HAVOK_SCALE`` to reach the game
units PyNifly imports geometry in (matching the SF ``.mesh`` importer). This module is *lossless*:
:meth:`MorphFile.from_bytes` -> :meth:`MorphFile.to_bytes` reproduces the input byte-for-byte.
:meth:`MorphFile.from_deltas` builds a new file from positions alone (normal/tangent/color are not
recoverable from Blender shape keys, so they are written as neutral defaults -- the "positions-only"
authoring path).
"""

import re
import struct
import logging

log = logging.getLogger("pynifly")

MAGIC = b'MDAT'
NUM_AXIS = 3

# Metric (.mesh) units -> PyNifly game units. Same constant nifly applies to SF .mesh positions,
# so morph deltas land in the same space as imported geometry.
HAVOK_SCALE = 69.969

# Cap imposed by the 4x32-bit marker field.
MAX_KEYS = 128

# Starfield performance (expression) morphs: the runtime-animated action units + tongue morphs +
# the Hat/Mask headgear-hide morphs. Everything NOT in this set is a chargen slider. Used to route
# each shape key to the performance/ vs chargen/ output file. Verified from vanilla
# performance/head + performance/tongue morph.dat (2026-07-14); the female head is the AU superset.
SF_EXPRESSION_MORPHS = frozenset({
    "Hat", "HideEar", "Mask",
    # primary action units
    "browLowererL", "browLowererR", "innerBrowRaiseL", "innerBrowRaiseR",
    "outerBrowRaiseL", "outerBrowRaiseR",
    "eyeClosedL", "eyeClosedR", "eyeOpenL", "eyeOpenR", "eyeUp", "eyeDown", "eyeLeft", "eyeRight",
    "lidTightenerL", "lidTightenerR", "squintL", "squintR",
    "cheekPuffL", "cheekPuffR", "cheekRaiseL", "cheekRaiseR", "cheekSuckL", "cheekSuckR",
    "dimplerL", "dimplerR",
    "noseWrinkleL", "noseWrinkleR", "noseDepressor", "nostrilCompressor", "nostrilDilator",
    "nasolabialFurrowL", "nasolabialFurrowR",
    "jawOpen", "jawClench", "jawLeft", "jawRight", "jawThrust",
    "upperLipRaiseL", "upperLipRaiseR", "upperLipDownL", "upperLipDownR", "upperLipFunnel",
    "upperLipPuff", "upperLipSuck", "upperLipThickness",
    "lowerLipDepressL", "lowerLipDepressR", "lowerLipUpL", "lowerLipUpR", "lowerLipFunnel",
    "lowerLipPuff", "lowerLipSuck", "lowerLipThickness",
    "lipCornerPullL", "lipCornerPullR", "lipCornerDepressL", "lipCornerDepressR",
    "lipCornerInL", "lipCornerInR", "lipStretchL", "lipStretchR",
    "lipPucker", "lipPress", "lipTighten", "lipZipperL", "lipZipperR", "sharpLipPullL", "sharpLipPullR",
    "chinRaise", "chinRaiseUpperlipTweak", "neckFlexL", "neckFlexR", "swallow",
    # combination / corrective morphs
    "c_jawdrop", "c_eyesClosed50L", "c_eyesClosed50R",
    "c_eyeDown_eyeClosedL", "c_eyeDown_eyeClosedR", "c_eyeUp_eyeClosedL", "c_eyeUp_eyeClosedR",
    "c_eyeLeft_eyeClosedL", "c_eyeLeft_eyeClosedR", "c_eyeRight_eyeClosedL", "c_eyeRight_eyeClosedR",
    "c_squintL_eyesClosedL", "c_squintR_eyesClosedR", "c_squintL_cheekRaiserL", "c_squintR_cheekRaiserR",
    "c_cheekRaiserL_eyesClosedL", "c_cheekRaiserL_eyesClosedR",
    "c_innerBrowRaiserL_browLowererL", "c_innerBrowRaiserR_browLowererR",
    "c_puckerer_lowerFunneler", "c_puckerer_upperFunneler",
    # tongue-specific
    "tongueIn", "tongueOut", "tongueUp", "tongueDown", "tongueLeft", "tongueRight",
    "tongueCurlUp", "tongueCurlDown", "tongueThick", "tongueThinner",
})


_DUP_SUFFIX = re.compile(r'\.\d{3}$')


def is_expression_morph(name):
    """True if shape-key `name` is a Starfield performance (expression) morph -> the performance/
    file; False = a chargen slider -> the chargen/ file. Blender's '.NNN' duplicate suffix is
    stripped before matching."""
    return _DUP_SUFFIX.sub('', name) in SF_EXPRESSION_MORPHS


# --- morph.dat path handling (store relative-to-'meshes' so morphs re-home with the nif) -------
# A morph.dat lives under Data/meshes/morphs/...; the nif under Data/meshes/.... Both share the
# 'meshes' root, so storing the morph path from 'meshes' onward lets export re-home it under a new
# nif's meshes root (go up from the nif to 'meshes', join the stored relative path).

def split_at_meshes(path):
    """Split `path` at its 'meshes' directory (case-insensitive, last occurrence). Returns
    ``(data_root, 'meshes/...tail')`` with forward slashes, or ``(None, None)`` if there is no
    'meshes' segment."""
    if not path:
        return None, None
    parts = str(path).replace('\\', '/').split('/')
    idx = None
    for i, p in enumerate(parts):
        if p.lower() == 'meshes':
            idx = i
    if idx is None:
        return None, None
    return '/'.join(parts[:idx]), '/'.join(parts[idx:])


def morph_relpath(path):
    """The morph.dat path rooted at 'meshes' (relative), for stashing on import. Falls back to the
    full path if there's no 'meshes' segment."""
    _root, rel = split_at_meshes(path)
    return rel if rel is not None else str(path)


def resolve_morph_output(stored, anchor):
    """Resolve a stored morph path against an export `anchor` (the nif's output path). An absolute
    `stored` passes through (explicit override). A relative `stored` (rooted at 'meshes') is joined
    to the Data root found by going up from `anchor` to its 'meshes' segment; if `anchor` has no
    'meshes', the anchor's directory is treated as the Data root."""
    import os
    if not stored:
        return ''
    if os.path.isabs(stored):
        return stored
    data_root, _ = split_at_meshes(anchor)
    if data_root is None:
        data_root = os.path.dirname(str(anchor)) if anchor else '.'
    return os.path.normpath(os.path.join(data_root, stored.replace('/', os.sep)))


def swap_morph_tree(path):
    """Swap a morph path between its 'chargen' and 'performance' sibling trees (either direction),
    or return '' if the path has neither segment."""
    low = path.lower()
    for sep in ('\\', '/'):
        if f'{sep}chargen{sep}' in low:
            return path.replace(f'{sep}chargen{sep}', f'{sep}performance{sep}')
        if f'{sep}performance{sep}' in low:
            return path.replace(f'{sep}performance{sep}', f'{sep}chargen{sep}')
    return ''

# target_vert_color is an RGB565 target vertex colour (SF vertex colour drives material masks --
# hair/clothing morphs vary it per channel; face/body morphs leave it a constant gray). Not
# recoverable from a Blender shape key, so newly-authored (positions-only) records get the vanilla
# default gray. 0xBDF7 == RGB565 (0.74, 0.75, 0.74), the value in nearly every vanilla face record.
DEFAULT_TARGET_COLOR = 0xBDF7

_HEADER = struct.Struct('<4sIII')      # magic, num_axis, num_vertices, num_shape_keys
_U32 = struct.Struct('<I')
_RECORD = struct.Struct('<HHHHII')     # off[0], off[1], off[2], color, normal, tangent
_IOFFSET = struct.Struct('<IIIII')     # start, marker[0..3]


# --- packing helpers (match SGB utils.cpp exactly) ---------------------------------------------

def _half_to_float(u):
    return struct.unpack('<e', struct.pack('<H', u))[0]


def _float_to_half(f):
    return struct.unpack('<H', struct.pack('<e', f))[0]


def _dec3n_to_vec(n):
    """Decode a DEC3N-packed uint32 to a signed (x, y, z) tuple."""
    return (
        (n & 1023) / 511.5 - 1.0,
        ((n >> 10) & 1023) / 511.5 - 1.0,
        ((n >> 20) & 1023) / 511.5 - 1.0,
    )


def _vec_to_dec3n(v, w=1):
    """Encode a signed (x, y, z) to a DEC3N uint32 (truncating, as SGB does)."""
    n = int((v[0] + 1.0) * 511.5) & 1023
    n |= (int((v[1] + 1.0) * 511.5) & 1023) << 10
    n |= (int((v[2] + 1.0) * 511.5) & 1023) << 20
    n |= (int(w) & 3) << 30
    return n


def _marker_bits(marker):
    """(m0, m1, m2, m3) -> ascending list of set key indices."""
    keys = []
    for word_i, word in enumerate(marker):
        base = word_i * 32
        while word:
            b = (word & -word).bit_length() - 1   # lowest set bit
            keys.append(base + b)
            word &= word - 1
    return keys


def _bits_marker(keys):
    """Iterable of key indices -> (m0, m1, m2, m3)."""
    marker = [0, 0, 0, 0]
    for k in keys:
        if k >= MAX_KEYS:
            raise ValueError(f"Morph key index {k} exceeds the {MAX_KEYS}-key cap")
        marker[k >> 5] |= 1 << (k & 31)
    return tuple(marker)


class MorphFile:
    """A parsed Starfield ``morph.dat``.

    Attributes:
        num_vertices: vertex count of the base mesh this morph applies to.
        morph_names:  shape-key names, in index order (index = marker bit position).
        records:      raw ``(off0, off1, off2, color, normal, tangent)`` tuples, verbatim.
        offsets:      per-vertex ``(start, (m0, m1, m2, m3))`` tuples (len == num_vertices).
    """

    def __init__(self):
        self.num_vertices = 0
        self.morph_names = []
        self.records = []
        self.offsets = []

    # --- reading -------------------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data):
        self = cls()
        magic, num_axis, num_vertices, num_keys = _HEADER.unpack_from(data, 0)
        if magic != MAGIC:
            raise ValueError(f"Not a Starfield morph.dat (magic {magic!r})")
        if num_axis != NUM_AXIS:
            log.warning("Unexpected morph.dat num_axis=%d (expected 3)", num_axis)
        self.num_vertices = num_vertices

        p = _HEADER.size
        for _ in range(num_keys):
            (nlen,) = _U32.unpack_from(data, p); p += _U32.size
            self.morph_names.append(data[p:p + nlen].decode('utf-8')); p += nlen

        num_morph_data, num_offsets = struct.unpack_from('<II', data, p); p += 8
        if num_offsets != num_vertices:
            log.warning("morph.dat num_offsets=%d != num_vertices=%d", num_offsets, num_vertices)

        for _ in range(num_morph_data):
            self.records.append(_RECORD.unpack_from(data, p)); p += _RECORD.size

        for _ in range(num_offsets):
            start, m0, m1, m2, m3 = _IOFFSET.unpack_from(data, p); p += _IOFFSET.size
            self.offsets.append((start, (m0, m1, m2, m3)))

        if p != len(data):
            log.warning("morph.dat: parsed %d of %d bytes", p, len(data))
        return self

    @classmethod
    def from_file(cls, path):
        with open(path, 'rb') as f:
            return cls.from_bytes(f.read())

    # --- writing (lossless) --------------------------------------------------------------------

    def to_bytes(self):
        out = bytearray()
        out += _HEADER.pack(MAGIC, NUM_AXIS, self.num_vertices, len(self.morph_names))
        for name in self.morph_names:
            nb = name.encode('utf-8')
            out += _U32.pack(len(nb)) + nb
        out += struct.pack('<II', len(self.records), len(self.offsets))
        for rec in self.records:
            out += _RECORD.pack(*rec)
        for start, marker in self.offsets:
            out += _IOFFSET.pack(start, *marker)
        return bytes(out)

    def to_file(self, path):
        with open(path, 'wb') as f:
            f.write(self.to_bytes())

    # --- positions view (for Blender shape keys) -----------------------------------------------

    def key_deltas(self, scale=HAVOK_SCALE):
        """Return ``{morph_name: {vertex_index: (dx, dy, dz)}}`` in game units.

        Only vertices a key actually moves appear (sparse). Position deltas only -- the stored
        normal/tangent/color channels are not returned (positions-only representation).
        """
        result = {name: {} for name in self.morph_names}
        n = len(self.records)
        for v, (start, marker) in enumerate(self.offsets):
            keys = _marker_bits(marker)
            if not keys:
                continue
            end = self.offsets[v + 1][0] if v + 1 < len(self.offsets) else n
            if end - start != len(keys):
                log.warning("vertex %d: %d records but %d marker bits", v, end - start, len(keys))
            for i, k in enumerate(keys):
                off0, off1, off2, _color, _nrm, _tan = self.records[start + i]
                dx = _half_to_float(off0) * scale
                dy = _half_to_float(off1) * scale
                dz = _half_to_float(off2) * scale
                result[self.morph_names[k]][v] = (dx, dy, dz)
        return result

    # --- building from positions (for Blender export) ------------------------------------------

    @classmethod
    def from_deltas(cls, morph_names, num_vertices, deltas, scale=HAVOK_SCALE):
        """Build a positions-only morph.dat from per-key vertex deltas (game units).

        Args:
            morph_names:  shape-key names, in the desired key-index order.
            num_vertices: base-mesh vertex count.
            deltas:       ``{morph_name: {vertex_index: (dx, dy, dz)}}`` -- sparse; only the
                          vertices a key moves need entries.
            scale:        game units -> metric divisor (default HAVOK_SCALE).

        Normal/tangent deltas are written neutral (zero) and colour as DEFAULT_TARGET_COLOR --
        these channels are not recoverable from a Blender shape key.
        """
        if len(morph_names) > MAX_KEYS:
            raise ValueError(f"{len(morph_names)} morphs exceeds the {MAX_KEYS}-key cap")

        self = cls()
        self.num_vertices = num_vertices
        self.morph_names = list(morph_names)

        color = DEFAULT_TARGET_COLOR & 0xFFFF   # raw RGB565
        zero_n = _vec_to_dec3n((0.0, 0.0, 0.0))

        # Records are grouped by vertex, keys ascending within each vertex.
        for v in range(num_vertices):
            moved = [(k, deltas[name][v])
                     for k, name in enumerate(morph_names)
                     if v in deltas.get(name, ())]
            start = len(self.records)
            self.offsets.append((start, _bits_marker(k for k, _ in moved)))
            for _k, (dx, dy, dz) in moved:
                self.records.append((
                    _float_to_half(dx / scale),
                    _float_to_half(dy / scale),
                    _float_to_half(dz / scale),
                    color, zero_n, zero_n,
                ))
        return self
