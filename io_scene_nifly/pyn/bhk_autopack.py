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

# Class entries for compressed mesh packfiles (different shape classes).
_CM_CLASS_ENTRIES: List[Tuple[int, str]] = [
    (0x33D42383, 'hkClass'),
    (0xB0EFA719, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0xB857718B, 'hknpPhysicsSystemData'),
    (0x5F60D536, 'hknpCompressedMeshShape'),
    (0xA2BDFC59, 'hknpCompressedMeshShapeData'),
    (0x7C574867, 'hkRefCountedProperties'),
    (0xA3E47A9A, 'hknpBSMaterialProperties'),
]

# Class entries for two-body mixed packfiles (CM body + polytope body).
_MIXED_CLASS_ENTRIES: List[Tuple[int, str]] = [
    (0x33D42383, 'hkClass'),
    (0xB0EFA719, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0xB857718B, 'hknpPhysicsSystemData'),
    (0x5F60D536, 'hknpCompressedMeshShape'),
    (0xA2BDFC59, 'hknpCompressedMeshShapeData'),
    (0x7C574867, 'hkRefCountedProperties'),
    (0xA3E47A9A, 'hknpBSMaterialProperties'),
    (0x3CE9B3E3, 'hknpConvexPolytopeShape'),
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

# hknpCompressedMeshShape header (0xC0 bytes).
# Global fixups at +0x20 (→ hkRefCountedProperties) and +0x60 (→ ShapeData)
# patch those pointer fields at load time; they are left as zeros here.
_CM_SHAPE_HDR = bytes([
    # +0x00: vtable ptr (null, runtime-patched)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x08: parent class ptr (null)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x10: type flags
    0x04,0x02,0x07,0x02, 0x00,0x00,0x00,0x00,
    # +0x18: version hash
    0x15,0x7d,0x06,0x26, 0x00,0x00,0x00,0x00,
    # +0x20: hkRefCountedProperties ptr (null, global fixup)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x28: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x30: sentinel 0xFFFFFFFF + 12 zeros
    0xff,0xff,0xff,0xff, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x40..+0x5F: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x60: ShapeData ptr (null, global fixup)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x68..+0x8F: zeros (5 rows × 8 bytes = 40 bytes)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x90: 0x44 byte + 15 zeros
    0x44,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0xA0..+0xBF: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
])
assert len(_CM_SHAPE_HDR) == 0xC0

# hknpBSMaterialProperties (0x50 bytes, extracted from CapsuleExtStairsFree01.nif).
_BS_MAT_PROPS = bytes([
    # +0x00: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x10
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x02,0x00,0x00,0x00, 0x02,0x00,0x00,0x80,
    # +0x20: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x30
    0x01,0x00,0x00,0x00, 0xd4,0x03,0x40,0x06,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x40
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x01,0x00,0x00,0x00, 0x3d,0x62,0xeb,0xc0,
])
assert len(_BS_MAT_PROPS) == 0x50


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

    # The decoder reads faces_off and fvi_off relative to their own field positions:
    #   faces_off → field at +0x44, so decoder computes shape_abs + 0x44 + faces_off_stored
    #   fvi_off   → field at +0x48, so decoder computes shape_abs + 0x48 + fvi_off_stored
    # We store offsets so that the decoder lands at the right position:
    #   faces_off_stored = faces_off - 4   (0x44 - 0x40 = 4)
    #   fvi_off_stored   = fvi_off   - 8   (0x48 - 0x40 = 8)
    faces_off_stored = faces_off - 4
    fvi_off_stored   = fvi_off   - 8

    # +0x30 block: numVertices, verticesOffset=0x20, 12 zeros.
    block_30 = _w_u16(nv) + _w_u16(0x20) + bytes(12)

    # +0x40 block: header40[6], 4 zeros.
    block_40 = (
        _w_u16(nv)               +   # numVerts2
        _w_u16(planes_off)       +   # planesOff (from header40 base +0x40)
        _w_u16(nf)               +   # numPlanes
        _w_u16(faces_off_stored) +   # facesOff (relative to +0x44 field position)
        _w_u16(n_fvi)            +   # numFaceVtxIndices
        _w_u16(fvi_off_stored)   +   # fviOff (relative to +0x48 field position)
        bytes(4)                     # padding
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


# ── Compressed-mesh data section builder ─────────────────────────────────────

def _build_cm_data_section(verts: List[Vert3], tris: List[Face],
                            name_offs: Dict[str, int]) -> Tuple[bytes, '_FixupBuilder']:
    """Build the full __data__ section for a single-section compressed mesh packfile.

    Layout:
      rel 0x0000: hknpPhysicsSystemData   (0x80)
      rel 0x0080: body_properties         (0x50)
      rel 0x00D0: BodyCInfo               (0x60)
      rel 0x0130: ShapeEntry              (0x10)
      rel 0x0140: hknpCompressedMeshShape (0xC0)
      rel 0x0200: hkRefCountedProperties  (0x20)
      rel 0x0220: hknpBSMaterialProperties (0x50, padded to 16)
      rel 0x0270: hknpCompressedMeshShapeData header (0xA0)
      then: section struct (0x60), quads (nt×4 bytes), packed verts (nv×4 bytes)

    Vertices are quantized with 11-11-10 bits (qx, qy: 0..2047; qz: 0..1023)
    using the bounding box of the input vertex set as the quantization range.
    Each triangle (a,b,c) is stored as a degenerate quad [a,b,c,c].

    Constraints: nv ≤ 255, nt ≤ 255 (single-section limitation).
    """
    nv = len(verts)
    nt = len(tris)
    assert nv > 0 and nt > 0
    assert nv <= 255, f"pack_compressed_mesh: max 255 verts per section (got {nv})"
    assert nt <= 255, f"pack_compressed_mesh: max 255 quads per section (got {nt})"

    fx = _FixupBuilder()
    data = bytearray()

    def rel() -> int:
        return len(data)

    def write(b: bytes) -> int:
        off = rel()
        data.extend(b)
        return off

    # ── hknpPhysicsSystemData (0x80 bytes) ─────────────────────────────────
    psd_rel = rel()
    fx.add_virtual(psd_rel, 0, name_offs['hknpPhysicsSystemData'])

    write(_hkarray(0))              # +0x00 empty
    arr10_off = write(_hkarray(1))  # +0x10 body_props array
    write(_hkarray(0))              # +0x20 empty
    write(_hkarray(0))              # +0x30 empty
    arr40_off = write(_hkarray(1))  # +0x40 BodyCInfo array
    write(_hkarray(0))              # +0x50 empty
    arr60_off = write(_hkarray(1))  # +0x60 ShapeEntry array
    write(bytes(16))                # +0x70 zeros
    assert rel() == psd_rel + 0x80

    # ── body_properties (0x50 bytes) ───────────────────────────────────────
    body_props_rel = rel()
    write(_BODY_PROPS)
    fx.add_local(arr10_off, body_props_rel)
    assert rel() == psd_rel + 0xD0

    # ── BodyCInfo (0x60 bytes) ─────────────────────────────────────────────
    body_cinfo_rel = rel()
    write(_BODY_CINFO)
    fx.add_local(arr40_off, body_cinfo_rel)
    assert rel() == psd_rel + 0x130

    # ── ShapeEntry (0x10 bytes) ────────────────────────────────────────────
    shape_entry_rel = rel()
    write(bytes(16))
    fx.add_local(arr60_off, shape_entry_rel)
    assert rel() == psd_rel + 0x140

    # ── hknpCompressedMeshShape (0xC0 bytes) ───────────────────────────────
    shape_rel = rel()
    write(_CM_SHAPE_HDR)
    assert rel() == shape_rel + 0xC0

    fx.add_virtual(shape_rel, 0, name_offs['hknpCompressedMeshShape'])
    fx.add_global(body_cinfo_rel + 0x00, 2, shape_rel)
    fx.add_global(shape_entry_rel + 0x00, 2, shape_rel)
    shape_refprop_ptr_rel = shape_rel + 0x20   # → hkRefCountedProperties
    shape_data_ptr_rel    = shape_rel + 0x60   # → hknpCompressedMeshShapeData

    # ── hkRefCountedProperties (0x20 bytes) ───────────────────────────────
    refprop_rel = rel()
    write(_REF_COUNTED_PROPS)
    fx.add_virtual(refprop_rel, 0, name_offs['hkRefCountedProperties'])
    fx.add_local(refprop_rel + 0x00, refprop_rel + 0x10)
    fx.add_global(shape_refprop_ptr_rel, 2, refprop_rel)
    while rel() % 16:
        data.append(0)

    # ── hknpBSMaterialProperties (0x50 bytes) ─────────────────────────────
    bs_mat_rel = rel()
    write(_BS_MAT_PROPS)
    fx.add_global(refprop_rel + 0x10, 2, bs_mat_rel)
    fx.add_virtual(bs_mat_rel, 0, name_offs['hknpBSMaterialProperties'])
    while rel() % 16:
        data.append(0)

    # ── Vertex AABB and quantization scales ────────────────────────────────
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    def _safe_scale(mn: float, mx: float, max_q: int) -> float:
        return (mx - mn) / max_q if mx > mn else 1.0

    sx = _safe_scale(min_x, max_x, 2047)
    sy = _safe_scale(min_y, max_y, 2047)
    sz = _safe_scale(min_z, max_z, 1023)

    # ── Encode vertices as 11-11-10 packed u32 ─────────────────────────────
    packed_verts: List[int] = []
    for x, y, z in verts:
        qx = min(2047, max(0, round((x - min_x) / sx))) if sx != 1.0 or min_x != max_x else 0
        qy = min(2047, max(0, round((y - min_y) / sy))) if sy != 1.0 or min_y != max_y else 0
        qz = min(1023, max(0, round((z - min_z) / sz))) if sz != 1.0 or min_z != max_z else 0
        packed_verts.append(qx | (qy << 11) | (qz << 22))

    # ── Encode triangles as degenerate quads [a,b,c,c] ────────────────────
    quad_bytes = b''
    for face in tris:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        quad_bytes += bytes([a, b, c, c])

    # ── Compute array positions for local fixups ───────────────────────────
    sd_rel           = rel()          # start of ShapeData header
    sections_data_rel = sd_rel + 0xA0           # immediately after 0xA0 header
    quads_data_rel    = sections_data_rel + 0x60  # after 1 section struct
    verts_data_rel    = quads_data_rel + len(quad_bytes)

    # ── hknpCompressedMeshShapeData header (0xA0 bytes) ───────────────────
    fx.add_virtual(sd_rel, 0, name_offs['hknpCompressedMeshShapeData'])
    fx.add_global(shape_data_ptr_rel, 2, sd_rel)

    sd_hdr = bytearray(0xA0)
    struct.pack_into('<QII', sd_hdr, 0x00, 0, 0, 0x80000000)  # empty hkArray
    struct.pack_into('<QII', sd_hdr, 0x10, 0, 0, 0x80000000)  # hkArray<Section*> (empty)
    struct.pack_into('<ffff', sd_hdr, 0x20, min_x, min_y, min_z, 0.0)  # aabb_min
    struct.pack_into('<ffff', sd_hdr, 0x30, max_x, max_y, max_z, 0.0)  # aabb_max
    struct.pack_into('<QII', sd_hdr, 0x40, 0, 0, 0x80000000)  # unknown (zeros)
    struct.pack_into('<QII', sd_hdr, 0x50, 0, 1, 1 | 0x80000000)       # sections (count=1)
    struct.pack_into('<QII', sd_hdr, 0x60, 0, nt, nt | 0x80000000)     # quads (count=nt)
    struct.pack_into('<QII', sd_hdr, 0x70, 0, 0, 0x80000000)           # shidx (empty)
    struct.pack_into('<QII', sd_hdr, 0x80, 0, nv, nv | 0x80000000)     # verts (count=nv)
    struct.pack_into('<QII', sd_hdr, 0x90, 0, 0, 0x80000000)           # sharedVerts (empty)
    write(bytes(sd_hdr))
    assert rel() == sd_rel + 0xA0

    # Local fixups: ptr fields of the three populated hkArrays
    fx.add_local(sd_rel + 0x50, sections_data_rel)
    fx.add_local(sd_rel + 0x60, quads_data_rel)
    fx.add_local(sd_rel + 0x80, verts_data_rel)

    # ── Section struct (0x60 bytes) ────────────────────────────────────────
    sec = bytearray(0x60)
    struct.pack_into('<QII', sec, 0x00, 0, 0, 0x80000000)       # treeNodes (empty)
    struct.pack_into('<ffff', sec, 0x10, min_x, min_y, min_z, 0.0)  # aabb_min
    struct.pack_into('<ffff', sec, 0x20, max_x, max_y, max_z, 0.0)  # aabb_max
    struct.pack_into('<fff',  sec, 0x30, min_x, min_y, min_z)       # base
    struct.pack_into('<fff',  sec, 0x3C, sx, sy, sz)                # scale X/Y/Z
    struct.pack_into('<I',    sec, 0x48, 0)                         # firstPackedVertex
    struct.pack_into('<I',    sec, 0x4C, nv)   # (0 << 8) | nv — firstShidx=0, numPacked=nv
    struct.pack_into('<I',    sec, 0x50, nt)   # (0 << 8) | nt — firstQuad=0, numQuads=nt
    write(bytes(sec))
    assert rel() == sections_data_rel + 0x60

    # ── Quad data ──────────────────────────────────────────────────────────
    write(quad_bytes)
    assert rel() == verts_data_rel

    # ── Packed vertex data ─────────────────────────────────────────────────
    for pv in packed_verts:
        data.extend(struct.pack('<I', pv))

    while rel() % 16:
        data.append(0)

    return bytes(data), fx


# ── Two-body mixed data section builder ──────────────────────────────────────

def _build_mixed_data_section(
        cm_verts: List[Vert3], cm_tris: List[Face],
        poly_verts: List[Vert3], poly_faces: List[Face],
        name_offs: Dict[str, int]) -> Tuple[bytes, '_FixupBuilder']:
    """Build __data__ section for a two-body packfile: CM body + polytope body.

    Layout:
      rel 0x0000: hknpPhysicsSystemData (0x80) — body/shape counts = 2
      rel 0x0080: body_props[0] (0x50) — CM body material
      rel 0x00D0: body_props[1] (0x50) — polytope body material
      rel 0x0120: BodyCInfo[0] (0x60)  — shape ptr → CM shape
      rel 0x0180: BodyCInfo[1] (0x60)  — shape ptr → polytope shape
      rel 0x01E0: ShapeEntry[0] (0x10) — ptr → CM shape
      rel 0x01F0: ShapeEntry[1] (0x10) — ptr → polytope shape
      rel 0x0200: hknpCompressedMeshShape (0xC0)
      then: hkRefCountedProperties for CM (0x20, padded to 16)
      then: hknpBSMaterialProperties (0x50, padded to 16)
      then: hknpCompressedMeshShapeData header (0xA0) + section (0x60)
            + quads + packed verts (padded to 16)
      then: hknpConvexPolytopeShape (variable, padded to 16)
      then: hkRefCountedProperties for polytope (0x20, padded to 16)
      then: hknpShapeMassProperties (0x30, padded to 16)
    """
    nv_cm = len(cm_verts)
    nt_cm = len(cm_tris)
    assert nv_cm > 0 and nt_cm > 0
    assert nv_cm <= 255, f"pack_mixed CM: max 255 verts per section (got {nv_cm})"
    assert nt_cm <= 255, f"pack_mixed CM: max 255 quads per section (got {nt_cm})"

    fx = _FixupBuilder()
    data = bytearray()

    def rel() -> int:
        return len(data)

    def write(b: bytes) -> int:
        off = rel()
        data.extend(b)
        return off

    # ── hknpPhysicsSystemData (0x80 bytes) ───────────────────────────────────
    psd_rel = rel()   # = 0
    fx.add_virtual(psd_rel, 0, name_offs['hknpPhysicsSystemData'])

    write(_hkarray(0))              # +0x00 empty
    arr10_off = write(_hkarray(2))  # +0x10 body_props array (count=2)
    write(_hkarray(0))              # +0x20 empty
    write(_hkarray(0))              # +0x30 empty
    arr40_off = write(_hkarray(2))  # +0x40 BodyCInfo array (count=2)
    write(_hkarray(0))              # +0x50 empty
    arr60_off = write(_hkarray(2))  # +0x60 ShapeEntry array (count=2)
    write(bytes(16))                # +0x70 zeros
    assert rel() == psd_rel + 0x80

    # ── body_props[0] + body_props[1] (2 × 0x50 = 0xA0 bytes) ───────────────
    body_props_rel = rel()          # = 0x0080; array ptr points here
    write(_BODY_PROPS)              # body[0] — CM
    write(_BODY_PROPS)              # body[1] — polytope
    fx.add_local(arr10_off, body_props_rel)
    assert rel() == psd_rel + 0x120

    # ── BodyCInfo[0] + BodyCInfo[1] (2 × 0x60 = 0xC0 bytes) ─────────────────
    body_cinfo_rel = rel()          # = 0x0120; array ptr points here
    write(_BODY_CINFO)              # BodyCInfo[0] — CM body
    write(_BODY_CINFO)              # BodyCInfo[1] — polytope body
    fx.add_local(arr40_off, body_cinfo_rel)
    assert rel() == psd_rel + 0x1E0

    # ── ShapeEntry[0] + ShapeEntry[1] (2 × 0x10 = 0x20 bytes) ───────────────
    shape_entry_rel = rel()         # = 0x01E0; array ptr points here
    write(bytes(16))                # ShapeEntry[0] ptr → CM shape (global fixup)
    write(bytes(16))                # ShapeEntry[1] ptr → polytope shape (global fixup)
    fx.add_local(arr60_off, shape_entry_rel)
    assert rel() == psd_rel + 0x200

    # ── hknpCompressedMeshShape (0xC0 bytes) ─────────────────────────────────
    cm_shape_rel = rel()            # = 0x0200
    write(_CM_SHAPE_HDR)
    assert rel() == cm_shape_rel + 0xC0

    fx.add_virtual(cm_shape_rel, 0, name_offs['hknpCompressedMeshShape'])
    fx.add_global(body_cinfo_rel + 0x00, 2, cm_shape_rel)          # BodyCInfo[0] shape ptr
    fx.add_global(shape_entry_rel + 0x00, 2, cm_shape_rel)         # ShapeEntry[0] ptr
    cm_refprop_ptr_rel  = cm_shape_rel + 0x20
    cm_shapedata_ptr_rel = cm_shape_rel + 0x60

    # ── hkRefCountedProperties for CM (0x20 bytes) ───────────────────────────
    cm_refprop_rel = rel()
    write(_REF_COUNTED_PROPS)
    fx.add_virtual(cm_refprop_rel, 0, name_offs['hkRefCountedProperties'])
    fx.add_local(cm_refprop_rel + 0x00, cm_refprop_rel + 0x10)
    fx.add_global(cm_refprop_ptr_rel, 2, cm_refprop_rel)
    while rel() % 16:
        data.append(0)

    # ── hknpBSMaterialProperties (0x50 bytes) ────────────────────────────────
    bs_mat_rel = rel()
    write(_BS_MAT_PROPS)
    fx.add_global(cm_refprop_rel + 0x10, 2, bs_mat_rel)
    fx.add_virtual(bs_mat_rel, 0, name_offs['hknpBSMaterialProperties'])
    while rel() % 16:
        data.append(0)

    # ── CM ShapeData: quantise and encode ─────────────────────────────────────
    xs = [v[0] for v in cm_verts]
    ys = [v[1] for v in cm_verts]
    zs = [v[2] for v in cm_verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    sx = (max_x - min_x) / 2047 if max_x > min_x else 1.0
    sy = (max_y - min_y) / 2047 if max_y > min_y else 1.0
    sz = (max_z - min_z) / 1023 if max_z > min_z else 1.0

    packed_verts_cm: List[int] = []
    for x, y, z in cm_verts:
        qx = min(2047, max(0, round((x - min_x) / sx))) if sx != 1.0 or min_x != max_x else 0
        qy = min(2047, max(0, round((y - min_y) / sy))) if sy != 1.0 or min_y != max_y else 0
        qz = min(1023, max(0, round((z - min_z) / sz))) if sz != 1.0 or min_z != max_z else 0
        packed_verts_cm.append(qx | (qy << 11) | (qz << 22))

    quad_bytes = b''
    for face in cm_tris:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        quad_bytes += bytes([a, b, c, c])

    sd_rel            = rel()
    sections_data_rel = sd_rel + 0xA0
    quads_data_rel    = sections_data_rel + 0x60
    verts_data_rel    = quads_data_rel + len(quad_bytes)

    fx.add_virtual(sd_rel, 0, name_offs['hknpCompressedMeshShapeData'])
    fx.add_global(cm_shapedata_ptr_rel, 2, sd_rel)

    sd_hdr = bytearray(0xA0)
    struct.pack_into('<QII', sd_hdr, 0x00, 0, 0, 0x80000000)
    struct.pack_into('<QII', sd_hdr, 0x10, 0, 0, 0x80000000)
    struct.pack_into('<ffff', sd_hdr, 0x20, min_x, min_y, min_z, 0.0)
    struct.pack_into('<ffff', sd_hdr, 0x30, max_x, max_y, max_z, 0.0)
    struct.pack_into('<QII', sd_hdr, 0x40, 0, 0, 0x80000000)
    struct.pack_into('<QII', sd_hdr, 0x50, 0, 1, 1 | 0x80000000)
    struct.pack_into('<QII', sd_hdr, 0x60, 0, nt_cm, nt_cm | 0x80000000)
    struct.pack_into('<QII', sd_hdr, 0x70, 0, 0, 0x80000000)
    struct.pack_into('<QII', sd_hdr, 0x80, 0, nv_cm, nv_cm | 0x80000000)
    struct.pack_into('<QII', sd_hdr, 0x90, 0, 0, 0x80000000)
    write(bytes(sd_hdr))
    assert rel() == sd_rel + 0xA0

    fx.add_local(sd_rel + 0x50, sections_data_rel)
    fx.add_local(sd_rel + 0x60, quads_data_rel)
    fx.add_local(sd_rel + 0x80, verts_data_rel)

    sec = bytearray(0x60)
    struct.pack_into('<QII', sec, 0x00, 0, 0, 0x80000000)
    struct.pack_into('<ffff', sec, 0x10, min_x, min_y, min_z, 0.0)
    struct.pack_into('<ffff', sec, 0x20, max_x, max_y, max_z, 0.0)
    struct.pack_into('<fff',  sec, 0x30, min_x, min_y, min_z)
    struct.pack_into('<fff',  sec, 0x3C, sx, sy, sz)
    struct.pack_into('<I',    sec, 0x48, 0)
    struct.pack_into('<I',    sec, 0x4C, nv_cm)
    struct.pack_into('<I',    sec, 0x50, nt_cm)
    write(bytes(sec))

    write(quad_bytes)
    assert rel() == verts_data_rel

    for pv in packed_verts_cm:
        data.extend(struct.pack('<I', pv))
    while rel() % 16:
        data.append(0)

    # ── hknpConvexPolytopeShape (variable) ───────────────────────────────────
    poly_shape_rel = rel()
    write(_build_convex_polytope_shape(poly_verts, poly_faces))
    while rel() % 16:
        data.append(0)

    fx.add_virtual(poly_shape_rel, 0, name_offs['hknpConvexPolytopeShape'])
    fx.add_global(body_cinfo_rel + 0x60, 2, poly_shape_rel)         # BodyCInfo[1] shape ptr
    fx.add_global(shape_entry_rel + 0x10, 2, poly_shape_rel)        # ShapeEntry[1] ptr
    poly_refprop_ptr_rel = poly_shape_rel + 0x20

    # ── hkRefCountedProperties for polytope (0x20 bytes) ─────────────────────
    poly_refprop_rel = rel()
    write(_REF_COUNTED_PROPS)
    fx.add_virtual(poly_refprop_rel, 0, name_offs['hkRefCountedProperties'])
    fx.add_local(poly_refprop_rel + 0x00, poly_refprop_rel + 0x10)
    fx.add_global(poly_refprop_ptr_rel, 2, poly_refprop_rel)
    while rel() % 16:
        data.append(0)

    # ── hknpShapeMassProperties (0x30 bytes) ─────────────────────────────────
    massprop_rel = rel()
    write(_SHAPE_MASS_PROPS)
    fx.add_global(poly_refprop_rel + 0x10, 2, massprop_rel)
    fx.add_virtual(massprop_rel, 0, name_offs['hknpShapeMassProperties'])
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


def _build_classnames_cm() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section for a compressed mesh packfile."""
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in _CM_CLASS_ENTRIES:
        name_offs[name] = len(data) + 5   # 4-byte hash + 1-byte flag
        data += struct.pack('<IB', hash_val, 0x09) + name.encode('ascii') + b'\x00'
    data = _pad16(data, fill=0xFF)
    return data, name_offs


def _build_classnames_mixed() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section for a two-body (CM + polytope) packfile."""
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in _MIXED_CLASS_ENTRIES:
        name_offs[name] = len(data) + 5   # 4-byte hash + 1-byte flag
        data += struct.pack('<IB', hash_val, 0x09) + name.encode('ascii') + b'\x00'
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

def pack_compressed_mesh(verts: List[Vert3], tris: List[Face]) -> bytes:
    """Build Havok packfile bytes from a triangle mesh using hknpCompressedMeshShape.

    Vertices are quantized with 11-11-10 bits relative to the mesh bounding box.
    Each triangle (a, b, c) is stored as a degenerate quad [a, b, c, c].

    Args:
        verts: List of (x, y, z) tuples in Havok space.  Maximum 255.
        tris:  List of (a, b, c) triangle index tuples.  Maximum 255.

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile containing an
        hknpPhysicsSystemData with one static body carrying the
        hknpCompressedMeshShape/hknpCompressedMeshShapeData.
    """
    cn_data, name_offs = _build_classnames_cm()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    obj_data, fx = _build_cm_data_section(verts, tris, name_offs)

    local_tbl  = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl   = fx.build_virtual_table()

    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    cn_start   = 0x100
    cn_end     = cn_start + len(cn_data)
    data_start = cn_end

    local_fix_abs  = data_start + len(obj_data)
    global_fix_abs = local_fix_abs  + len(local_tbl)
    virt_fix_abs   = global_fix_abs + len(global_tbl)
    data_end       = virt_fix_abs   + len(virt_tbl)

    hdr = _file_header(cn_name_off)

    shdr0 = _section_header(
        '__classnames__', cn_start,
        local_fix=cn_start + len(cn_data),
        global_fix=cn_start + len(cn_data),
        virt_fix=cn_start + len(cn_data),
        exports=cn_start + len(cn_data),
    )
    shdr1 = _section_header(
        '__types__', cn_end,
        local_fix=cn_end, global_fix=cn_end,
        virt_fix=cn_end,  exports=cn_end,
    )
    shdr2 = _section_header(
        '__data__', data_start,
        local_fix=local_fix_abs,
        global_fix=global_fix_abs,
        virt_fix=virt_fix_abs,
        exports=data_end,
    )

    return hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section


def pack_mixed(cm_shape, poly_shape) -> bytes:
    """Build Havok packfile bytes for two bodies: one CM + one convex polytope.

    Args:
        cm_shape:   CollisionShape with shape_type=="compressed_mesh".
        poly_shape: CollisionShape with shape_type=="polytope".

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile with hknpPhysicsSystemData
        containing two static bodies (CM body + polytope body).
    """
    cn_data, name_offs = _build_classnames_mixed()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    obj_data, fx = _build_mixed_data_section(
        cm_shape.verts, cm_shape.faces,
        poly_shape.verts, poly_shape.faces,
        name_offs)

    local_tbl  = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl   = fx.build_virtual_table()

    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    cn_start   = 0x100
    cn_end     = cn_start + len(cn_data)
    data_start = cn_end

    local_fix_abs  = data_start + len(obj_data)
    global_fix_abs = local_fix_abs  + len(local_tbl)
    virt_fix_abs   = global_fix_abs + len(global_tbl)
    data_end       = virt_fix_abs   + len(virt_tbl)

    hdr = _file_header(cn_name_off)

    shdr0 = _section_header(
        '__classnames__', cn_start,
        local_fix=cn_start + len(cn_data),
        global_fix=cn_start + len(cn_data),
        virt_fix=cn_start + len(cn_data),
        exports=cn_start + len(cn_data),
    )
    shdr1 = _section_header(
        '__types__', cn_end,
        local_fix=cn_end, global_fix=cn_end,
        virt_fix=cn_end, exports=cn_end,
    )
    shdr2 = _section_header(
        '__data__', data_start,
        local_fix=local_fix_abs,
        global_fix=global_fix_abs,
        virt_fix=virt_fix_abs,
        exports=data_end,
    )

    return hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section


# ── Multi-body polytope data section builder ─────────────────────────────────

def _build_multi_poly_data_section(
        poly_pairs: List[Tuple[List[Vert3], List[Face]]],
        name_offs: Dict[str, int]) -> Tuple[bytes, '_FixupBuilder']:
    """Build the full __data__ section for an N-body all-polytope packfile.

    Each element of poly_pairs is a (verts, faces) tuple for one body.
    Layout:
      rel 0x0000:            hknpPhysicsSystemData (0x80)
      rel 0x0080:            body_props[0..N-1]   (N × 0x50)
      rel 0x0080+N*0x50:     BodyCInfo[0..N-1]    (N × 0x60)
      rel 0x0080+N*0xB0:     ShapeEntry[0..N-1]   (N × 0x10)
      rel 0x0080+N*0xC0:     shape[0] (variable) + RefCountedProps + MassProps
      ...                    shape[1] chain, ...
    """
    N = len(poly_pairs)
    assert N >= 1

    fx = _FixupBuilder()
    data = bytearray()

    def rel() -> int:
        return len(data)

    def write(b: bytes) -> int:
        off = rel()
        data.extend(b)
        return off

    # ── hknpPhysicsSystemData (0x80) ─────────────────────────────────────────
    psd_rel = rel()
    fx.add_virtual(psd_rel, 0, name_offs['hknpPhysicsSystemData'])
    write(_hkarray(0))              # +0x00: empty
    arr10_off = rel()
    write(_hkarray(N))              # +0x10: body_props (count=N)
    write(_hkarray(0))              # +0x20: empty
    write(_hkarray(0))              # +0x30: empty
    arr40_off = rel()
    write(_hkarray(N))              # +0x40: BodyCInfo (count=N)
    write(_hkarray(0))              # +0x50: empty
    arr60_off = rel()
    write(_hkarray(N))              # +0x60: ShapeEntry (count=N)
    write(bytes(16))                # +0x70: zeros
    assert rel() == psd_rel + 0x80

    # ── body_props[0..N-1] ───────────────────────────────────────────────────
    body_props_rel = rel()
    fx.add_local(arr10_off, body_props_rel)
    for _ in range(N):
        write(_BODY_PROPS)

    # ── BodyCInfo[0..N-1] ────────────────────────────────────────────────────
    body_arr_rel = rel()
    fx.add_local(arr40_off, body_arr_rel)
    body_cinfo_rels = []
    for _ in range(N):
        bc_rel = rel()
        body_cinfo_rels.append(bc_rel)
        write(_BODY_CINFO)

    # ── ShapeEntry[0..N-1] ───────────────────────────────────────────────────
    shape_arr_rel = rel()
    fx.add_local(arr60_off, shape_arr_rel)
    shape_entry_rels = []
    for _ in range(N):
        se_rel = rel()
        shape_entry_rels.append(se_rel)
        write(bytes(16))  # ptr=0 (patched by global fixup), 8 zeros

    # ── Per-body polytope chains ──────────────────────────────────────────────
    for i, (verts, faces) in enumerate(poly_pairs):
        # hknpConvexPolytopeShape (variable size, aligned to 16)
        shape_rel = rel()
        write(_build_convex_polytope_shape(verts, faces))
        while rel() % 16:
            data.append(0)

        fx.add_virtual(shape_rel, 0, name_offs['hknpConvexPolytopeShape'])
        fx.add_global(body_cinfo_rels[i] + 0x00, 2, shape_rel)
        fx.add_global(shape_entry_rels[i] + 0x00, 2, shape_rel)

        # hkRefCountedProperties (0x20)
        refprop_rel = rel()
        write(_REF_COUNTED_PROPS)
        fx.add_virtual(refprop_rel, 0, name_offs['hkRefCountedProperties'])
        fx.add_local(refprop_rel + 0x00, refprop_rel + 0x10)
        fx.add_global(shape_rel + 0x20, 2, refprop_rel)
        while rel() % 16:
            data.append(0)

        # hknpShapeMassProperties (0x30)
        massprop_rel = rel()
        write(_SHAPE_MASS_PROPS)
        fx.add_global(refprop_rel + 0x10, 2, massprop_rel)
        fx.add_virtual(massprop_rel, 0, name_offs['hknpShapeMassProperties'])
        while rel() % 16:
            data.append(0)

    return bytes(data), fx


def pack_multi_polytope(poly_shapes) -> bytes:
    """Pack N convex polytopes into a single Havok packfile (N-body system).

    Each body in the packfile carries one hknpConvexPolytopeShape.
    Uses the same __classnames__ as a single-polytope packfile.

    Args:
        poly_shapes: list of CollisionShape objects with shape_type='polytope'.
    Returns:
        Raw Havok packfile bytes.
    """
    cn_data, name_offs = _build_classnames()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    poly_pairs = [(s.verts, s.faces) for s in poly_shapes]
    obj_data, fx = _build_multi_poly_data_section(poly_pairs, name_offs)

    local_tbl  = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl   = fx.build_virtual_table()

    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    cn_start   = 0x100
    cn_end     = cn_start + len(cn_data)
    data_start = cn_end
    local_fix_abs  = data_start + len(obj_data)
    global_fix_abs = local_fix_abs  + len(local_tbl)
    virt_fix_abs   = global_fix_abs + len(global_tbl)
    data_end       = virt_fix_abs   + len(virt_tbl)

    hdr = _file_header(cn_name_off)

    shdr0 = _section_header(
        '__classnames__', cn_start,
        local_fix=cn_start + len(cn_data),
        global_fix=cn_start + len(cn_data),
        virt_fix=cn_start + len(cn_data),
        exports=cn_start + len(cn_data),
    )
    shdr1 = _section_header(
        '__types__', cn_end,
        local_fix=cn_end, global_fix=cn_end,
        virt_fix=cn_end,  exports=cn_end,
    )
    shdr2 = _section_header(
        '__data__', data_start,
        local_fix=local_fix_abs,
        global_fix=global_fix_abs,
        virt_fix=virt_fix_abs,
        exports=data_end,
    )

    return hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section


def pack_shapes(shapes) -> bytes:
    """Pack a list of CollisionShape objects into Havok packfile bytes.

    Supported shape compositions (matching what the decoder can produce):
      [compressed_mesh]             → pack_compressed_mesh (11-11-10 quantised)
      [polytope]                    → pack_convex_polytope (single body)
      [polytope, ...]               → pack_multi_polytope (N-body all-polytope)
      [compressed_mesh, polytope]   → pack_mixed (two-body)

    Combinations not listed above are not yet implemented and raise
    NotImplementedError rather than silently producing incorrect output.

    Args:
        shapes: List of CollisionShape objects (from bhk_autounpack).
    Returns:
        Raw Havok packfile bytes suitable for bhkPhysicsSystem.data.
    Raises:
        NotImplementedError: for unsupported shape combinations.
    """
    if len(shapes) == 1:
        s = shapes[0]
        if s.shape_type == "compressed_mesh":
            return pack_compressed_mesh(s.verts, s.faces)
        if s.shape_type == "polytope":
            return pack_convex_polytope(s.verts, s.faces)

    cm_list   = [s for s in shapes if s.shape_type == "compressed_mesh"]
    poly_list = [s for s in shapes if s.shape_type == "polytope"]

    if len(cm_list) == 0 and len(poly_list) == len(shapes):
        return pack_multi_polytope(poly_list)

    if len(cm_list) == 1 and len(poly_list) == 1 and len(shapes) == 2:
        return pack_mixed(cm_list[0], poly_list[0])

    types = [s.shape_type for s in shapes]
    raise NotImplementedError(
        f"pack_shapes: unsupported shape combination {types}; "
        f"mixed CM+multi-polytope packing is not yet implemented"
    )


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
