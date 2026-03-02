#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bhk_autopack.py
---------------
Build a Havok hk_2014.1.0 packfile binary for FO4 bhkPhysicsSystem.

Reverse-engineered from bhk_autounpack.py and inspection of InsFloorMat01.nif.

Public API:
  pack_convex_polytope(verts, faces) -> bytes
      verts: list of (x, y, z) float tuples in Havok space
      faces: list of face vertex-index lists (each face is a convex polygon)
             Winding must be counter-clockwise when viewed from outside.
      Returns raw packfile bytes suitable for storing in bhkPhysicsSystem.data.

File structure (hk_2014.1.0 little-endian, 8-byte pointers):
  0x000: global file header (0x40 bytes)
  0x040: section header 0 __classnames__ (0x40 bytes)
  0x080: section header 1 __types__      (0x40 bytes, empty section)
  0x0C0: section header 2 __data__       (0x40 bytes)
  0x100: __classnames__ section data
  0x1C0: __data__ section data

__data__ fixed layout:
  rel 0x0000: hknpPhysicsSystemData  (0x80 bytes)
  rel 0x0080: body_properties        (0x50 bytes — material/quality data)
  rel 0x00D0: BodyCInfo              (0x60 bytes — one rigid body, identity xf)
  rel 0x0130: ShapeEntry             (0x10 bytes — shape reference)
  rel 0x0140: hknpConvexPolytopeShape (variable)
  rel ????:   hkRefCountedProperties (0x20 bytes)
  rel ????:   hknpShapeMassProperties (0x30 bytes)
  then: local / global / virtual fixup tables
"""

import struct
import math
from typing import Dict, List, Optional, Tuple

# ── Type aliases ──────────────────────────────────────────────────────────────
Vert3 = Tuple[float, float, float]
Face  = List[int]

# ── File header constants ─────────────────────────────────────────────────────
_MAGIC           = b'\x57\xE0\xE0\x57\x10\xC0\xC0\x10'
_FILE_VERSION    = 11       # hk_2014.1.0
_LAYOUT_RULES    = b'\x08\x01\x00\x01'   # ptrSize=8, LE, opts
_CONTENTS_VER    = b'hk_2014.1.0-r1\x00\xff'  # 16 bytes
_MAX_PREDICATE   = 21       # observed in reference binary

# ── Class name hashes (from reference binary, hk_2014.1.0) ───────────────────
_CLASS_ENTRIES: List[Tuple[int, str]] = [
    (0x33D42383, 'hkClass'),
    (0xB0EFA719, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0xB857718B, 'hknpPhysicsSystemData'),
    (0x3CE9B3E3, 'hknpConvexPolytopeShape'),
    (0x7C574867, 'hkRefCountedProperties'),
    (0xE9191728, 'hknpShapeMassProperties'),
]

# ── Fixed blob data (from InsFloorMat01.nif reference) ───────────────────────

# body_properties (rel 0x0080, 0x50 bytes) — physics material/quality data.
_BODY_PROPS = bytes([
    # 0x00-0x0F: zeros
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    # 0x10-0x1F: material values (friction ≈ 0.5, restitution ≈ 0.4, etc.)
    0x00,0xFF,0x00,0x3F, 0x00,0x3F,0xCD,0x3E,
    0x01,0x02,0x4C,0x3D, 0xEE,0xFF,0x7F,0x7F,
    # 0x20-0x2F: scale/damping (1.0, 1.0, zeros)
    0x00,0x00,0x80,0x3F, 0x00,0x00,0x80,0x3F,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # 0x30-0x3F: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0xA0,0x40,0x00,0x00, 0x00,0x00,0x00,0x00,
    # 0x40-0x4F: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
])
assert len(_BODY_PROPS) == 0x50

# BodyCInfo (rel 0x00D0, 0x60 bytes) — one static body at identity transform.
# +0x00: shape ptr (8 bytes, patched by global fixup)
# +0x08-+0x2F: body flags/IDs from reference
# +0x30: position (vec3 = 0,0,0) → +0x3C: 4 zeros
# +0x40: quaternion (0,0,0,1)     → +0x50-+0x5F: zeros
_BODY_CINFO = bytes([
    # +0x00: shape ptr (zeros, patched)
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    # +0x08-+0x0F: flags/IDs
    0xFF,0xFF,0xFF,0x7F, 0xFF,0xFF,0xFF,0x7F,
    # +0x10-+0x17
    0xFF,0x00,0x00,0x00, 0x01,0x00,0x00,0x00,
    # +0x18-+0x1F zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x20-+0x27 zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x28-+0x2F zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x30: position (0,0,0) + 4 bytes zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x40: quaternion (0,0,0,1): x=0,y=0,z=0,w=0x3F7FFFFF≈1
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0xFF,0xFF,0x7F,0x3F,
    # +0x50-+0x5F: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
])
assert len(_BODY_CINFO) == 0x60

# hkRefCountedProperties (rel varies, 0x20 bytes)
# +0x00: hkArray ptr (local fixup -> internal entry at +0x10)
# +0x08: count=1, capFlags=0x80000001
# +0x10: entry ptr (global fixup -> hknpShapeMassProperties)
# +0x18: type ID 0x0000F100
_REF_COUNTED_PROPS = bytes([
    # hkArray: ptr (patched), count=1, capFlags
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x01,0x00,0x00,0x00, 0x01,0x00,0x00,0x80,
    # entry: ptr (patched), type_id=0x0000F100
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0xF1,0x00,0x00, 0x00,0x00,0x00,0x00,
])
assert len(_REF_COUNTED_PROPS) == 0x20

# hknpShapeMassProperties (rel varies, 0x30 bytes) — default mass data.
_SHAPE_MASS_PROPS = bytes([
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x0B,0x75,0x00,0x2D,
    0x98,0x28,0x98,0x28, 0x2F,0x51,0x80,0x30,
    0x00,0x80,0x00,0x80, 0x00,0x80,0x30,0xF5,
    0xC8,0x2F,0xC3,0x3E, 0xC8,0x2F,0xC3,0x3E,
])
assert len(_SHAPE_MASS_PROPS) == 0x30

# Fixed part of hknpConvexPolytopeShape header (+0x00 to +0x2F, 0x30 bytes).
# +0x00: vtable ptr (null, patched at runtime)
# +0x08: parent class ptr (null)
# +0x10: shape type/flags (03 01 00 01)
# +0x14: convex_radius = 0.01 (0x3C23D70A)
# +0x18: large_convex_radius (huge float from reference)
# +0x1C-+0x2F: zeros
_CONVEX_HDR = bytes([
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # vtable ptr
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # parent class ptr
    0x03,0x01,0x00,0x01,                        # type/quality flags
    0x0A,0xD7,0x23,0x3C,                        # convex_radius = 0.01
    0x05,0x6E,0xFA,0x7D,                        # large radius (reference value)
    0x00,0x00,0x00,0x00,                        # pad
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # zeros
])
assert len(_CONVEX_HDR) == 0x30


# ── Low-level pack helpers ────────────────────────────────────────────────────

def _w_u8(v: int) -> bytes:  return struct.pack('<B', v & 0xFF)
def _w_u16(v: int) -> bytes: return struct.pack('<H', v & 0xFFFF)
def _w_u32(v: int) -> bytes: return struct.pack('<I', v & 0xFFFFFFFF)
def _w_u64(v: int) -> bytes: return struct.pack('<Q', v & 0xFFFFFFFFFFFFFFFF)
def _w_f32(v: float) -> bytes: return struct.pack('<f', v)
def _w_vec3(x: float, y: float, z: float) -> bytes: return struct.pack('<fff', x, y, z)
def _w_vec4(x: float, y: float, z: float, w: float) -> bytes:
    return struct.pack('<ffff', x, y, z, w)

def _pad16(data: bytes, fill: int = 0xFF) -> bytes:
    """Pad to 16-byte boundary."""
    r = len(data) % 16
    return data + (bytes([fill]) * (16 - r) if r else b'')

def _pad_to(data: bytes, n: int, fill: int = 0x00) -> bytes:
    """Pad bytes to length n."""
    return data + bytes([fill]) * (n - len(data))


# ── hkArray helper ───────────────────────────────────────────────────────────

def _hkarray(count: int) -> bytes:
    """Build a 16-byte hkArray with zero ptr (local fixup applied later).
    If count == 0 the ptr stays null and no fixup is recorded.
    capFlags = count | 0x80000000 (user-allocated).
    """
    cap_flags = (count | 0x80000000) if count > 0 else 0x80000000
    return _w_u64(0) + _w_u32(count) + _w_u32(cap_flags)


# ── Geometry helpers ─────────────────────────────────────────────────────────

def _face_plane(verts: List[Vert3], face: Face) -> Tuple[float, float, float, float]:
    """Compute outward plane equation (nx, ny, nz, d) for a convex-polytope face.

    Winding is CCW when viewed from outside → normal points outward.
    The plane equation satisfies: nx*x + ny*y + nz*z + d = 0 for a surface point.
    d = -dot(n, v0).
    """
    v0 = verts[face[0]]
    v1 = verts[face[1]]
    v2 = verts[face[2]]
    ax, ay, az = v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]
    bx, by, bz = v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]
    nx = ay*bz - az*by
    ny = az*bx - ax*bz
    nz = ax*by - ay*bx
    n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
    if n_len < 1e-10:
        return (0.0, 0.0, 1.0, 0.0)
    nx, ny, nz = nx/n_len, ny/n_len, nz/n_len
    d = -(nx*v0[0] + ny*v0[1] + nz*v0[2])
    return (nx, ny, nz, d)


# ── Convex polytope shape builder ────────────────────────────────────────────

def _build_convex_polytope_shape(verts: List[Vert3],
                                  faces: List[Face]) -> bytes:
    """Build raw bytes for hknpConvexPolytopeShape.

    Layout relative to object start:
      +0x00: fixed 0x30-byte header (_CONVEX_HDR)
      +0x30: numVertices (u16), verticesOffset=0x20 (u16), 12 zeros
      +0x40: 6×u16 (numVerts2, planesOff, numPlanes, facesOff, numFVI, fviOff), 4 zeros
      +0x50: vertices   (numVerts × 16 bytes, vec4 with w = 0x3F000000 | idx)
      +0x50+verts_size: planes  (numPlanes × 16 bytes, vec4)
      after planes: 28 bytes zeros (gap between planes and faces, see notes)
      after gap:    faces    (numPlanes × 4 bytes: firstFVI u16, numVtx u8, flags u8)
      after faces:  4 bytes zeros (alignment gap)
      after gap:    fvi      (numFVI × 1 byte, vertex indices per face)
      padded to 8-byte boundary
    """
    nv = len(verts)
    nf = len(faces)
    assert nv <= 255, "ConvexPolytopeShape: at most 255 vertices (u8 FVI)"
    assert nf > 0

    # Build FVI (face vertex index) flat array and face entries.
    fvi: List[int] = []
    face_entries: List[Tuple[int, int]] = []   # (firstFVI, numVtx)
    for face in faces:
        first = len(fvi)
        fvi.extend(face)
        face_entries.append((first, len(face)))
    n_fvi = len(fvi)

    # Compute plane equations.
    planes: List[Tuple[float, float, float, float]] = [_face_plane(verts, f) for f in faces]

    # Sizes of each section (relative to the header40 base at +0x40).
    # Vertices start 0x10 bytes after header40 base (= +0x50 from object start).
    verts_size    = nv   * 16
    planes_size   = nf   * 16
    _GAP_PLANES   = 28          # observed fixed gap after planes, before faces
    faces_size    = nf   * 4
    _GAP_FACES    = 4           # observed alignment gap after faces, before FVI
    fvi_size      = n_fvi * 1

    # Offsets relative to header40 base (+0x40).
    #   vertices: at +0x10 from header40 base (= +0x50 from object start, i.e. +0x20 from +0x30)
    planes_off    = 0x10 + verts_size
    faces_off     = planes_off + planes_size + _GAP_PLANES
    fvi_off       = faces_off  + faces_size  + _GAP_FACES

    # +0x30 block: numVertices, verticesOffset=0x20, 12 zeros.
    block_30 = _w_u16(nv) + _w_u16(0x20) + bytes(12)

    # +0x40 block: header40[6], 4 zeros.
    block_40 = (
        _w_u16(nv)          +   # numVerts2
        _w_u16(planes_off)  +   # planesOff (from header40 base)
        _w_u16(nf)          +   # numPlanes
        _w_u16(faces_off)   +   # facesOff
        _w_u16(n_fvi)       +   # numFaceVtxIndices
        _w_u16(fvi_off)     +   # fviOff
        bytes(4)                # padding
    )
    assert len(block_30) == 0x10
    assert len(block_40) == 0x10

    # Vertex data: vec4 (x, y, z, w) where w encodes packed index.
    vert_data = b''
    for i, (x, y, z) in enumerate(verts):
        w_bits = 0x3F000000 | i
        vert_data += _w_f32(x) + _w_f32(y) + _w_f32(z)
        vert_data += struct.pack('<I', w_bits)

    # Plane data: vec4 (nx, ny, nz, d).
    plane_data = b''
    for nx, ny, nz, d in planes:
        plane_data += _w_vec4(nx, ny, nz, d)

    # Gap between planes and faces (28 zeros).
    gap_planes = bytes(_GAP_PLANES)

    # Face entries: firstFVI (u16), numVtx (u8), flags (u8).
    face_data = b''
    for first, count in face_entries:
        face_data += struct.pack('<HBB', first, count, 0)

    # Gap between faces and FVI (4 zeros).
    gap_faces = bytes(_GAP_FACES)

    # FVI array.
    fvi_data = bytes(fvi)

    payload = (vert_data + plane_data + gap_planes +
               face_data + gap_faces  + fvi_data)

    shape = _CONVEX_HDR + block_30 + block_40 + payload
    # Align to 8 bytes.
    r = len(shape) % 8
    if r:
        shape += bytes(8 - r)
    return shape


# ── Data section builder ─────────────────────────────────────────────────────

class _FixupBuilder:
    """Accumulates local, global, and virtual fixup entries."""
    def __init__(self) -> None:
        self.local:   List[Tuple[int, int]]         = []  # (src_rel, dst_rel)
        self.global_: List[Tuple[int, int, int]]    = []  # (src_rel, sec_idx, dst_rel)
        self.virtual: List[Tuple[int, int, int]]    = []  # (obj_rel, sec_idx, name_off)

    def add_local(self, src_rel: int, dst_rel: int) -> None:
        self.local.append((src_rel, dst_rel))

    def add_global(self, src_rel: int, sec_idx: int, dst_rel: int) -> None:
        self.global_.append((src_rel, sec_idx, dst_rel))

    def add_virtual(self, obj_rel: int, sec_idx: int, name_off: int) -> None:
        self.virtual.append((obj_rel, sec_idx, name_off))

    def build_local_table(self) -> bytes:
        out = b''
        for src, dst in self.local:
            out += _w_u32(src) + _w_u32(dst)
        out += _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF)
        return out

    def build_global_table(self) -> bytes:
        out = b''
        for src, sec, dst in self.global_:
            out += _w_u32(src) + _w_u32(sec) + _w_u32(dst)
        out += _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF)
        return out

    def build_virtual_table(self) -> bytes:
        out = b''
        for obj, sec, noff in self.virtual:
            out += _w_u32(obj) + _w_u32(sec) + _w_u32(noff)
        out += _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF)
        return out


def _build_data_section(verts: List[Vert3], faces: List[Face],
                         name_offs: Dict[str, int]) -> Tuple[bytes, _FixupBuilder]:
    """Build the full __data__ section (object data only, without fixup tables).

    Returns (section_bytes, fixup_builder).
    The fixup_builder is populated with all fixup entries.
    The pointer field bytes within section_bytes are left as zeros;
    fixup tables specify where to patch them at load time.
    """
    fx = _FixupBuilder()
    data = bytearray()

    def rel() -> int:
        """Current write offset = relative position from data section start."""
        return len(data)

    def write(b: bytes) -> int:
        """Append bytes and return the start offset."""
        off = rel()
        data.extend(b)
        return off

    # ── hknpPhysicsSystemData  (rel=0x0000, 0x80 bytes) ──────────────────────
    psd_rel = rel()
    fx.add_virtual(psd_rel, 0, name_offs['hknpPhysicsSystemData'])

    # +0x00: empty hkArray
    write(_hkarray(0))
    # +0x10: hkArray<body_props*> count=1 → local fixup to rel=0x0080
    arr10_off = rel()
    write(_hkarray(1))
    # +0x20, +0x30: empty
    write(_hkarray(0))
    write(_hkarray(0))
    # +0x40: hkArray<BodyCInfo> count=1 → local fixup to rel=0x00D0
    arr40_off = rel()
    write(_hkarray(1))
    # +0x50: empty
    write(_hkarray(0))
    # +0x60: hkArray<ShapeEntry> count=1 → local fixup to rel=0x0130
    arr60_off = rel()
    write(_hkarray(1))
    # +0x70: zeros (8 bytes ptr + 8 bytes other)
    write(bytes(16))
    assert rel() == psd_rel + 0x80

    # ── body_properties  (rel=0x0080, 0x50 bytes) ─────────────────────────────
    body_props_rel = rel()
    write(_BODY_PROPS)
    assert rel() == psd_rel + 0xD0

    # Now record local fixup: hknpPhysicsSystemData+0x10 ptr → body_props_rel
    fx.add_local(arr10_off, body_props_rel)

    # ── BodyCInfo  (rel=0x00D0, 0x60 bytes) ──────────────────────────────────
    body_cinfo_rel = rel()
    write(_BODY_CINFO)
    assert rel() == psd_rel + 0x130

    fx.add_local(arr40_off, body_cinfo_rel)

    # ── ShapeEntry  (rel=0x0130, 0x10 bytes) ──────────────────────────────────
    shape_entry_rel = rel()
    write(bytes(16))  # ptr=0 (global fixup), plus 8 zeros
    assert rel() == psd_rel + 0x140

    fx.add_local(arr60_off, shape_entry_rel)

    # ── hknpConvexPolytopeShape  (rel=0x0140, variable) ───────────────────────
    shape_rel = rel()
    shape_bytes = _build_convex_polytope_shape(verts, faces)
    write(shape_bytes)
    # Align to 16 bytes.
    while rel() % 16:
        data.append(0)

    fx.add_virtual(shape_rel, 0, name_offs['hknpConvexPolytopeShape'])
    # BodyCInfo+0x00 (shape ptr) → global fixup → shape
    fx.add_global(body_cinfo_rel + 0x00, 2, shape_rel)
    # ShapeEntry+0x00 (shape ptr) → global fixup → shape
    fx.add_global(shape_entry_rel + 0x00, 2, shape_rel)
    # shape+0x20 (hkRefCountedProperties ptr) → recorded after refprop_rel is known
    shape_refprop_ptr_rel = shape_rel + 0x20

    # ── hkRefCountedProperties  (variable rel) ────────────────────────────────
    refprop_rel = rel()
    write(_REF_COUNTED_PROPS)
    fx.add_virtual(refprop_rel, 0, name_offs['hkRefCountedProperties'])
    # hkRefCountedProperties+0x00 (hkArray ptr) → local fixup → entry at +0x10
    fx.add_local(refprop_rel + 0x00, refprop_rel + 0x10)
    # shape+0x20 → hkRefCountedProperties (global fixup, now that refprop_rel is known)
    fx.add_global(shape_refprop_ptr_rel, 2, refprop_rel)
    # Align to 16 bytes.
    while rel() % 16:
        data.append(0)

    # ── hknpShapeMassProperties  (variable rel) ───────────────────────────────
    massprop_rel = rel()
    write(_SHAPE_MASS_PROPS)
    # hkRefCountedProperties entry ptr (+0x10) → global fixup → hknpShapeMassProperties
    fx.add_global(refprop_rel + 0x10, 2, massprop_rel)
    fx.add_virtual(massprop_rel, 0, name_offs['hknpShapeMassProperties'])
    # Align to 16 bytes.
    while rel() % 16:
        data.append(0)

    return bytes(data), fx


# ── Classnames section ────────────────────────────────────────────────────────

def _build_classnames() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section bytes and return name_offsets dict.

    Each entry: u32 hash + u8 0x09 + null-terminated name.
    name_offsets[name] = byte offset of name string within the section.
    Section is padded to 16-byte boundary with 0xFF.
    """
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in _CLASS_ENTRIES:
        name_offs[name] = len(data) + 5   # 4-byte hash + 1-byte flag
        data += struct.pack('<IB', hash_val, 0x09) + name.encode('ascii') + b'\x00'
    # Pad to 16-byte boundary with 0xFF.
    data = _pad16(data, fill=0xFF)
    return data, name_offs


# ── Section header builder ────────────────────────────────────────────────────

def _section_header(name: str, abs_start: int,
                    local_fix: int, global_fix: int,
                    virt_fix: int, exports: int) -> bytes:
    """Build a 0x40-byte section header.

    All fix/exports values are ABSOLUTE file offsets; they are written as
    relative offsets from abs_start in the header.
    """
    hdr = bytearray(0x40)
    name_b = name.encode('ascii') + b'\x00'
    hdr[:len(name_b)] = name_b
    # Pad name area (bytes after null up to 0x14) with 0xFF.
    for i in range(len(name_b), 0x14):
        hdr[i] = 0xFF
    struct.pack_into('<I', hdr, 0x14, abs_start)
    struct.pack_into('<I', hdr, 0x18, local_fix  - abs_start)
    struct.pack_into('<I', hdr, 0x1C, global_fix - abs_start)
    struct.pack_into('<I', hdr, 0x20, virt_fix   - abs_start)
    struct.pack_into('<I', hdr, 0x24, exports    - abs_start)
    struct.pack_into('<I', hdr, 0x28, exports    - abs_start)   # imports (= exports)
    struct.pack_into('<I', hdr, 0x2C, exports    - abs_start)   # end
    # Remaining bytes default to 0x00; reference pads with 0xFF from 0x30.
    for i in range(0x30, 0x40):
        hdr[i] = 0xFF
    return bytes(hdr)


# ── Global file header ────────────────────────────────────────────────────────

def _file_header(cn_name_off: int) -> bytes:
    """Build the 0x40-byte global packfile header.

    cn_name_off: offset of 'hknpPhysicsSystemData' within __classnames__ section.
    """
    hdr = bytearray(0x40)
    hdr[0x00:0x08] = _MAGIC
    struct.pack_into('<i',  hdr, 0x08, 0)                    # userTag
    struct.pack_into('<i',  hdr, 0x0C, _FILE_VERSION)
    hdr[0x10:0x14] = _LAYOUT_RULES
    struct.pack_into('<i',  hdr, 0x14, 3)                    # numSections
    struct.pack_into('<i',  hdr, 0x18, 2)                    # contentsSectionIndex (data=2)
    struct.pack_into('<i',  hdr, 0x1C, 0)                    # contentsSectionOffset
    struct.pack_into('<i',  hdr, 0x20, 0)                    # contentsClassNameSectionIndex (cn=0)
    struct.pack_into('<i',  hdr, 0x24, cn_name_off)          # contentsClassNameSectionOffset
    hdr[0x28:0x38] = _CONTENTS_VER
    struct.pack_into('<i',  hdr, 0x38, 0)                    # flags
    struct.pack_into('<i',  hdr, 0x3C, _MAX_PREDICATE)
    return bytes(hdr)


# ── Public API ────────────────────────────────────────────────────────────────

def pack_convex_polytope(verts: List[Vert3], faces: List[Face]) -> bytes:
    """Build Havok packfile bytes from a convex polytope mesh.

    Args:
        verts: List of (x, y, z) tuples in Havok space.
        faces: List of face index lists. Each face is a convex polygon
               whose vertices are ordered CCW when viewed from outside.
               All vertex indices reference the verts list.
               Maximum 255 vertices.

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile containing an
        hknpPhysicsSystemData with one static body carrying the shape.
    """
    # ── Classnames section ──
    cn_data, name_offs = _build_classnames()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    # ── Data section (object bytes only) ──
    obj_data, fx = _build_data_section(verts, faces, name_offs)

    # ── Fixup tables ──
    local_tbl  = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl   = fx.build_virtual_table()

    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    # ── Compute absolute offsets ──
    # Layout: 0x100 (4 headers) + cn_data + data_section
    cn_start   = 0x100
    cn_end     = cn_start + len(cn_data)
    data_start = cn_end                   # __types__ is empty, data starts right after cn

    local_fix_abs  = data_start + len(obj_data)
    global_fix_abs = local_fix_abs  + len(local_tbl)
    virt_fix_abs   = global_fix_abs + len(global_tbl)
    data_end       = virt_fix_abs   + len(virt_tbl)

    # ── Assemble file header and section headers ──
    hdr = _file_header(cn_name_off)

    # Section 0: __classnames__ (abs_start=cn_start, all fixup tables at end)
    shdr0 = _section_header(
        '__classnames__', cn_start,
        local_fix=cn_start + len(cn_data),
        global_fix=cn_start + len(cn_data),
        virt_fix=cn_start + len(cn_data),
        exports=cn_start + len(cn_data),
    )

    # Section 1: __types__ (empty — start = end = cn_end)
    shdr1 = _section_header(
        '__types__', cn_end,
        local_fix=cn_end, global_fix=cn_end,
        virt_fix=cn_end,  exports=cn_end,
    )

    # Section 2: __data__
    shdr2 = _section_header(
        '__data__', data_start,
        local_fix=local_fix_abs,
        global_fix=global_fix_abs,
        virt_fix=virt_fix_abs,
        exports=data_end,
    )

    return hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section


# ── Standalone test / round-trip helper ──────────────────────────────────────

def _make_box_verts_faces() -> Tuple[List[Vert3], List[Face]]:
    """Return vertices and faces for a unit box (for testing)."""
    verts: List[Vert3] = [
        (-0.5, -0.5, -0.5), ( 0.5, -0.5, -0.5),
        ( 0.5,  0.5, -0.5), (-0.5,  0.5, -0.5),
        (-0.5, -0.5,  0.5), ( 0.5, -0.5,  0.5),
        ( 0.5,  0.5,  0.5), (-0.5,  0.5,  0.5),
    ]
    faces: List[Face] = [
        [0, 3, 2, 1],  # -Z (bottom, CCW from -Z)
        [4, 5, 6, 7],  # +Z (top, CCW from +Z)
        [0, 1, 5, 4],  # -Y front
        [2, 3, 7, 6],  # +Y back
        [0, 4, 7, 3],  # -X left
        [1, 2, 6, 5],  # +X right
    ]
    return verts, faces


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 2:
        out = sys.argv[1]
    else:
        out = 'test_box.bin'
    verts, faces = _make_box_verts_faces()
    data = pack_convex_polytope(verts, faces)
    with open(out, 'wb') as f:
        f.write(data)
    print(f'Written {len(data)} bytes to {out}')
