#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bhk_autounpack.py
-----------------
Extract collision mesh from FO4 bhkPhysicsSystem Havok packfile bytes.

Can be run standalone against a .nif file:
  python bhk_autounpack.py <input.nif>
  Output is written to bhk_autounpack.obj next to this script.

Config flags (edit in this file):
  TRIANGULATE_OUTPUT   - triangulate polytopes (compressed mesh is always triangulated)

Notes:
  Convex polytopes are returned as the raw inner hull (no Minkowski expansion applied
  here).  The convexRadius per shape is returned alongside the geometry so the caller
  can apply expansion (e.g. Blender Displace + Bevel modifiers) at a higher level.

Pure packfile parsing — no heuristics, no buffer scoring, no guessing.
Uses local/virtual fixups and known hknpCompressedMeshShapeData layout.

hknpCompressedMeshShapeData layout (hk_2014.1.0):
  +0x10: hkArray<Section*>  (unused here)
  +0x20: aabb_min  (vec4)
  +0x30: aabb_max  (vec4)
  +0x50: hkArray<Section>   sections
  +0x60: hkArray<u32>       quadIndices
  +0x70: hkArray<u16>       sharedVertexMapping (per-section shidx -> global large vert)
  +0x80: hkArray<u32>       packedVertices
  +0x90: hkArray<u64>       sharedVertices (large 21-21-22 encoded, object-level AABB)

Section struct (stride 0x60):
  +0x00: hkArray<u8>   treeNodes
  +0x10: aabb_min (vec4)
  +0x20: aabb_max (vec4)
  +0x30: base     (vec3)
  +0x3C: scaleX, +0x40: scaleY, +0x44: scaleZ
  +0x48: firstPackedVertex  (u32)
  +0x4C: packed(firstShidxEntry << 8 | numPackedVertices)  — byte-packed when fits u8
  +0x50: packed(firstQuad << 8 | numQuads)                 — byte-packed when fits u8
  +0x54: packed(firstIdx << 8 | count)  (BVH/chunk related, not shared verts)
  +0x58: packed field (purpose TBD)
  +0x5C: (reserved)

Packed vertex: u32 -> 11-bit X | 11-bit Y | 10-bit Z
Quad: 4x u8 indices (or 4x u16 for large meshes)
Axis: OBJ writes (x, z, -y) for Creation Engine orientation.

hknpConvexPolytopeShape layout (hk_2014.1.0):
  +0x14: float convexRadius  — Minkowski expansion radius
  +0x30: [u16 numVertices, u16 verticesOffset]   base = +0x30
  +0x40: [u16 numFaces,    u16 planesOffset]     base = +0x40
  +0x44: [u16 numPlanes,   u16 facesOffset]      base = +0x44
  +0x48: [u16 numFVI,      u16 fviOffset]        base = +0x48
"""

import struct
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math
from pathlib import Path

# ── helpers ──────────────────────────────────────────────────────────────────

def u8(data: bytes, off: int) -> int:
    return data[off]

def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]

def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]

def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]

def u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]

def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0]

def vec3(data: bytes, off: int) -> Tuple[float, float, float]:
    return struct.unpack_from("<fff", data, off)

def vec4(data: bytes, off: int) -> Tuple[float, float, float, float]:
    return struct.unpack_from("<ffff", data, off)

Vert3 = Tuple[float, float, float]
Tri = Tuple[int, int, int]
Face = Tuple[int, ...]
Mat3 = Tuple[Tuple[float, float, float],
             Tuple[float, float, float],
             Tuple[float, float, float]]

# Output triangulation toggle (polytopes only; compressed mesh stays triangulated)
TRIANGULATE_OUTPUT = False


def quat_to_matrix(qx: float, qy: float, qz: float, qw: float) -> Mat3:
    """Convert quaternion (x,y,z,w) to 3x3 rotation matrix (row-major)."""
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return (
        (1 - 2 * (yy + zz),     2 * (xy - wz),     2 * (xz + wy)),
        (    2 * (xy + wz), 1 - 2 * (xx + zz),     2 * (yz - wx)),
        (    2 * (xz - wy),     2 * (yz + wx), 1 - 2 * (xx + yy)),
    )


def mat3_mul(a: Mat3, b: Mat3) -> Mat3:
    """Multiply two 3x3 matrices."""
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )  # type: ignore


def unpack_vertex(v: int) -> Tuple[int, int, int]:
    """11-11-10 packed vertex."""
    return (v & 0x7FF), ((v >> 11) & 0x7FF), ((v >> 22) & 0x3FF)


def decode_large_vertices(data: bytes, buf_abs: int, count: int,
                          bb_min: Tuple[float, float, float],
                          bb_max: Tuple[float, float, float]) -> List[Vert3]:
    """Decode count packed 21-21-22 large vertices (u64 each).

    Uses the object-level AABB for quantization boundaries.
    Format: x = bits[0:20], y = bits[21:41], z = bits[42:63].
    """
    verts: List[Vert3] = []
    sx = (bb_max[0] - bb_min[0]) / ((1 << 21) - 1)
    sy = (bb_max[1] - bb_min[1]) / ((1 << 21) - 1)
    sz = (bb_max[2] - bb_min[2]) / ((1 << 22) - 1)
    for i in range(count):
        off = buf_abs + i * 8
        if off + 8 > len(data):
            break
        v = u64(data, off)
        qx = v & 0x1FFFFF
        qy = (v >> 21) & 0x1FFFFF
        qz = (v >> 42) & 0x3FFFFF
        verts.append((bb_min[0] + qx * sx,
                      bb_min[1] + qy * sy,
                      bb_min[2] + qz * sz))
    return verts

# ── packfile parsing ─────────────────────────────────────────────────────────

@dataclass
class SectionHdr:
    name: str
    abs_start: int
    local_fix: int
    global_fix: int
    virt_fix: int
    exports: int
    end: int


def parse_section_headers(data: bytes) -> Dict[str, SectionHdr]:
    """Parse the 3 packfile section headers at offset 0x40."""
    hdrs: Dict[str, SectionHdr] = {}
    for i in range(3):
        base = 0x40 + i * 0x40
        raw = data[base:base + 19].split(b"\x00")[0]
        if not raw:
            continue
        name = raw.decode("ascii", errors="replace")
        s = u32(data, base + 0x14)
        hdrs[name] = SectionHdr(
            name=name, abs_start=s,
            local_fix=s + u32(data, base + 0x18),
            global_fix=s + u32(data, base + 0x1C),
            virt_fix=s + u32(data, base + 0x20),
            exports=s + u32(data, base + 0x24),
            end=s + u32(data, base + 0x2C),
        )
    return hdrs


def parse_local_fixups(data: bytes, hdr: SectionHdr) -> Dict[int, int]:
    """src_rel -> dst_rel within __data__ section."""
    fix: Dict[int, int] = {}
    pos = hdr.local_fix
    end = min(hdr.global_fix, len(data))
    while pos + 8 <= end:
        src = u32(data, pos)
        dst = u32(data, pos + 4)
        if src == 0xFFFFFFFF:
            break
        fix[src] = dst
        pos += 8
    return fix


def parse_virtual_fixups(data: bytes, hdr: SectionHdr, cn_start: int) -> List[Tuple[int, str]]:
    """Return list of (rel_offset, class_name) for objects in __data__."""
    objs: List[Tuple[int, str]] = []
    pos = hdr.virt_fix
    end = min(hdr.exports, len(data))
    while pos + 12 <= end:
        src = u32(data, pos)
        _sec = u32(data, pos + 4)
        name_off = u32(data, pos + 8)
        if src == 0xFFFFFFFF:
            break
        abs_name = cn_start + name_off
        cls = ""
        try:
            ne = data.index(b"\x00", abs_name, abs_name + 128)
            cls = data[abs_name:ne].decode("ascii", errors="replace")
        except ValueError:
            cls = f"?{name_off:#x}"
        objs.append((src, cls))
        pos += 12
    return objs


def parse_global_fixups(data: bytes, hdr: SectionHdr) -> Dict[int, Tuple[int, int]]:
    """src_rel -> (dst_section_index, dst_rel) for __data__ section."""
    fix: Dict[int, Tuple[int, int]] = {}
    pos = hdr.global_fix
    end = min(hdr.virt_fix, len(data))
    while pos + 12 <= end:
        src = u32(data, pos)
        sec = u32(data, pos + 4)
        dst = u32(data, pos + 8)
        if src == 0xFFFFFFFF:
            break
        fix[src] = (sec, dst)
        pos += 12
    return fix


@dataclass
class BodyTransform:
    position: Vert3
    rotation: Mat3  # from quaternion


@dataclass
class CollisionShape:
    """A single decoded collision shape from a Havok packfile.

    shape_type values:
      "compressed_mesh" — hknpCompressedMeshShapeData (triangle mesh)
      "polytope"        — hknpConvexPolytopeShape (convex hull)
      "sphere"          — hknpSphereShape (radius-based sphere)
      "compound"        — hknpDynamicCompoundShape container; geometry in children

    transform holds the body/instance position+rotation from the packfile.
    Vertices are in local (untransformed) space; the caller applies transform.
    convex_radius is the Minkowski expansion radius (0.0 for non-polytope shapes).
    sphere_radius is set only for shape_type="sphere" (Havok-space radius).
    """
    shape_type: str
    name: str
    transform: Optional[BodyTransform]      # None = identity
    verts: List[Vert3]                      # empty for compound and sphere
    faces: List[Face]                       # indices into verts; empty for compound and sphere
    convex_radius: float                    # 0.0 for compressed_mesh and compound
    children: List['CollisionShape']        # non-empty only for compound
    sphere_radius: float = 0.0             # Havok-space radius for sphere shapes


def parse_body_transforms(
        data: bytes, data_start: int,
        fixups: Dict[int, int],
        gfixups: Dict[int, Tuple[int, int]],
        objects: List[Tuple[int, str]],
) -> Dict[int, BodyTransform]:
    """Parse hknpPhysicsSystemData to extract per-body transforms.

    Returns a mapping: shape_object_rel -> BodyTransform.

    Layout of hknpPhysicsSystemData:
      +0x40: hkArray<BodyCInfo>  (stride 0x60, pos at +0x30, quat at +0x40)
      +0x60: hkArray<ShapeEntry> (stride 0x30, shape pointer at +0x00/+0x08)
    Body N and ShapeEntry N are matched by index.
    """
    result: Dict[int, BodyTransform] = {}

    psd_list = [(rel, cls) for rel, cls in objects if "hknpPhysicsSystemData" in cls]
    if not psd_list:
        return result

    for psd_rel, _ in psd_list:
        psd_abs = data_start + psd_rel

        # Body array at +0x40 (stride 0x60, position at +0x30, quaternion at +0x40)
        body_count = u32(data, psd_abs + 0x40 + 8) & 0x3FFFFFFF
        body_arr_dst = fixups.get(psd_rel + 0x40)
        if body_arr_dst is None or body_count == 0:
            continue
        body_arr_abs = data_start + body_arr_dst

        BODY_STRIDE = 0x60
        BODY_POS_OFF = 0x30
        BODY_QUAT_OFF = 0x40

        for i in range(body_count):
            body_rel = body_arr_dst + i * BODY_STRIDE
            body_abs = body_arr_abs + i * BODY_STRIDE

            # Shape pointer at body+0x00 via global fixup
            gf = gfixups.get(body_rel + 0x00)
            if gf is None:
                continue
            shape_rel = gf[1]

            pos = (f32(data, body_abs + BODY_POS_OFF),
                   f32(data, body_abs + BODY_POS_OFF + 4),
                   f32(data, body_abs + BODY_POS_OFF + 8))
            q = vec4(data, body_abs + BODY_QUAT_OFF)
            rot = quat_to_matrix(q[0], q[1], q[2], q[3])
            bt = BodyTransform(position=pos, rotation=rot)
            result[shape_rel] = bt

            # Also map sub-objects (e.g. CompressedMeshShape -> ShapeData)
            for sub_off in range(0, 0x100, 8):
                sub_gf = gfixups.get(shape_rel + sub_off)
                if sub_gf is not None and sub_gf[1] != shape_rel:
                    result[sub_gf[1]] = bt

    return result


# ── hkArray read helpers ─────────────────────────────────────────────────────

def hkarray_abs(fixups: Dict[int, int], data_start: int, obj_rel: int, field_off: int) -> Optional[int]:
    """Resolve hkArray pointer via local fixup -> absolute file offset."""
    dst = fixups.get(obj_rel + field_off)
    return (data_start + dst) if dst is not None else None


def hkarray_size(data: bytes, obj_abs: int, field_off: int) -> int:
    """Read hkArray size (lower 30 bits of the size/capFlags field)."""
    return u32(data, obj_abs + field_off + 8) & 0x3FFFFFFF


# ── mesh extraction ──────────────────────────────────────────────────────────


def decode_vertices(data: bytes, buf_abs: int, count: int,
                    base: Tuple[float, float, float],
                    scale: Tuple[float, float, float]) -> List[Vert3]:
    """Decode count packed 11-11-10 vertices."""
    verts: List[Vert3] = []
    bx, by, bz = base
    sx, sy, sz = scale
    for i in range(count):
        off = buf_abs + i * 4
        if off + 4 > len(data):
            break
        v = u32(data, off)
        qx, qy, qz = unpack_vertex(v)
        verts.append((bx + qx * sx, by + qy * sy, bz + qz * sz))
    return verts


def decode_quads_u8(data: bytes, buf_abs: int, count: int,
                    num_local: int) -> List[Tri]:
    """Decode quads with u8 indices, emit triangles."""
    tris: List[Tri] = []
    for i in range(count):
        off = buf_abs + i * 4
        if off + 4 > len(data):
            break
        a, b, c, d = data[off], data[off + 1], data[off + 2], data[off + 3]
        if max(a, b, c, d) >= num_local:
            continue
        tris.append((a, b, c))
        if c != d:
            tris.append((a, c, d))
    return tris


def decode_quads_u16(data: bytes, buf_abs: int, count: int,
                     num_local: int) -> List[Tri]:
    """Decode quads with u16 indices, emit triangles."""
    tris: List[Tri] = []
    for i in range(count):
        off = buf_abs + i * 8
        if off + 8 > len(data):
            break
        a = u16(data, off)
        b = u16(data, off + 2)
        c = u16(data, off + 4)
        d = u16(data, off + 6)
        if max(a, b, c, d) >= num_local:
            continue
        tris.append((a, b, c))
        if c != d:
            tris.append((a, c, d))
    return tris


def detect_index_format(data: bytes, quad_abs: int, num_quads: int,
                        num_local: int) -> str:
    """Detect whether quad indices are u8 or u16."""
    if num_local > 255:
        return "u16"

    # Sample quads as u8 and u16, count out-of-range indices
    sample = min(num_quads, 256)
    bad_u8 = 0
    bad_u16 = 0
    for i in range(sample):
        off8 = quad_abs + i * 4
        if off8 + 4 <= len(data):
            for j in range(4):
                if data[off8 + j] >= num_local:
                    bad_u8 += 1
        off16 = quad_abs + i * 8
        if off16 + 8 <= len(data):
            for j in range(4):
                if u16(data, off16 + j * 2) >= num_local:
                    bad_u16 += 1
    return "u16" if (bad_u16 < bad_u8) else "u8"


# ── section struct parsing ───────────────────────────────────────────────────

SECTION_STRIDE = 0x60  # known stride for hknpCompressedMeshShapeData::Section

# Field offsets within Section struct
SEC_AABB_MIN       = 0x10
SEC_AABB_MAX       = 0x20
SEC_BASE           = 0x30
SEC_SCALE_X        = 0x3C
SEC_SCALE_Y        = 0x40
SEC_SCALE_Z        = 0x44
SEC_FIRST_VERTEX   = 0x48
SEC_VERT_PACKED    = 0x4C   # packed: (firstShidxEntry << 8) | numPackedVertices
SEC_QUAD_PACKED    = 0x50   # packed: (firstQuad << 8) | numQuads
SEC_UNK54_PACKED   = 0x54   # packed: unknown BVH-related field
SEC_UNK58          = 0x58
SEC_UNK5C          = 0x5C


def read_sections(data: bytes, sections_abs: int, count: int,
                  total_verts: int, total_quads: int,
                  total_shared: int, total_shidx: int) -> List[dict]:
    """Read all Section structs and compute derived counts.

    Packed fields at +0x4C, +0x50 always use the convention:
      low byte   = this section's count
      upper bytes = first-index (cumulative offset from preceding sections)
    This holds regardless of whether totals exceed 255.

    The per-section shared vertex count is determined by the shidx slice:
      this section's firstShidx .. next section's firstShidx
    (or total_shidx for the last section).
    """
    raw: List[dict] = []
    for i in range(count):
        o = sections_abs + i * SECTION_STRIDE

        # +0x4C: packed vertexInfo — low byte = numPackedVertices, upper = firstShidxEntry
        vert_raw = u32(data, o + SEC_VERT_PACKED)
        num_packed  = vert_raw & 0xFF
        first_shidx = (vert_raw >> 8) & 0xFFFFFF

        # +0x50: packed quadInfo — low byte = numQuads, upper = firstQuad
        quad_raw = u32(data, o + SEC_QUAD_PACKED)
        num_quads  = quad_raw & 0xFF
        first_quad = (quad_raw >> 8) & 0xFFFFFF

        raw.append({
            "base":         vec3(data, o + SEC_BASE),
            "scale":        (f32(data, o + SEC_SCALE_X),
                             f32(data, o + SEC_SCALE_Y),
                             f32(data, o + SEC_SCALE_Z)),
            "first_vertex": u32(data, o + SEC_FIRST_VERTEX),
            "num_quads":    num_quads,
            "first_quad":   first_quad,
            "first_shared": first_shidx,
        })

    # Compute num_vertices from firstVertex differences (always reliable).
    # Compute num_shared from firstShidx differences.
    sections: List[dict] = []
    for i, s in enumerate(raw):
        next_fv = raw[i + 1]["first_vertex"] if i + 1 < count else total_verts
        s["num_vertices"] = next_fv - s["first_vertex"]

        next_shidx = raw[i + 1]["first_shared"] if i + 1 < count else total_shidx
        s["num_shared"] = next_shidx - s["first_shared"]

        sections.append(s)

    return sections


# ── OBJ writer ───────────────────────────────────────────────────────────────

def write_obj(path: str, shapes: List[CollisionShape]) -> None:
    def _flat(ss: List[CollisionShape]) -> List[CollisionShape]:
        out: List[CollisionShape] = []
        for s in ss:
            if s.shape_type == "compound":
                out.extend(_flat(s.children))
            elif s.verts:
                out.append(s)
        return out

    flat = _flat(shapes)
    total_v = sum(len(s.verts) for s in flat)
    total_f = sum(len(s.faces) for s in flat)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# bhkPhysicsSystem collision mesh\n")
        f.write(f"# verts={total_v} faces={total_f}\n\n")
        vert_base = 1
        for s in flat:
            f.write(f"\no {s.name}\ng {s.name}\n")
            for x, y, z in s.verts:
                f.write(f"v {x:.6f} {z:.6f} {-y:.6f}\n")
            for face in s.faces:
                f.write("f " + " ".join(str(i + vert_base) for i in face) + "\n")
            vert_base += len(s.verts)


# ── convex polytope extraction ───────────────────────────────────────────────

def parse_convex_polytope(data: bytes, shape_abs: int) -> Optional[Tuple[List[Vert3], List[Face], float]]:
    """Parse an hknpConvexPolytopeShape and return (vertices, faces, convex_radius).

    Layout (hk_2014.1.0, all offsets relative to shape_abs):
      +0x14: float convexRadius  — Minkowski expansion radius; returned to caller
      +0x30: [u16 numVertices, u16 verticesOffset]   base = +0x30
      +0x40: [u16 numFaces,    u16 planesOffset]     base = +0x40
      +0x44: [u16 numPlanes,   u16 facesOffset]      base = +0x44
      +0x48: [u16 numFVI,      u16 fviOffset]        base = +0x48

    The returned vertices are the raw inner hull vertices (not Minkowski-expanded).
    The caller is responsible for applying convex_radius (e.g. via Blender modifiers).
    """
    if shape_abs + 0x50 > len(data):
        return None

    num_verts   = u16(data, shape_abs + 0x30)
    vert_offset = u16(data, shape_abs + 0x32)
    num_planes  = u16(data, shape_abs + 0x44)
    faces_off   = u16(data, shape_abs + 0x46)
    num_fvi     = u16(data, shape_abs + 0x48)
    fvi_off     = u16(data, shape_abs + 0x4A)

    if num_verts == 0 or num_planes == 0:
        return None

    vert_start  = shape_abs + 0x30 + vert_offset
    faces_start = shape_abs + 0x44 + faces_off
    fvi_start   = shape_abs + 0x48 + fvi_off

    # Read inner vertices (vec4 each, w component ignored)
    inner_verts: List[Vert3] = []
    for i in range(num_verts):
        vo = vert_start + i * 16
        if vo + 16 > len(data):
            return None
        v = vec4(data, vo)
        inner_verts.append((v[0], v[1], v[2]))

    if fvi_start + num_fvi > len(data):
        return None

    # Read face records (polygon winding per face)
    face_polys: List[List[int]] = []
    for fi in range(num_planes):
        fo = faces_start + fi * 4
        if fo + 4 > len(data):
            break
        first = u16(data, fo)
        cnt = u8(data, fo + 2)
        if cnt < 3 or first + cnt > num_fvi:
            face_polys.append([])
            continue
        poly: List[int] = []
        ok = True
        for k in range(cnt):
            idx = u8(data, fvi_start + first + k)
            if idx >= num_verts:
                ok = False
                break
            poly.append(idx)
        face_polys.append(poly if ok and len(set(poly)) >= 3 else [])

    # Read convexRadius — stored per-shape at +0x14
    convex_radius = f32(data, shape_abs + 0x14) if shape_abs + 0x18 <= len(data) else 0.0

    # Emit the raw inner polytope faces (no Minkowski expansion).
    # convex_radius is returned to the caller for application at a higher level.
    verts = list(inner_verts)
    tris: List[Face] = []
    tri_set: set = set()

    def add_tri(a: int, b: int, c: int) -> None:
        if a == b or b == c or a == c:
            return
        key = tuple(sorted((a, b, c)))
        if key not in tri_set:
            tri_set.add(key)
            tris.append((a, b, c))

    for poly in face_polys:
        for k in range(1, len(poly) - 1):
            add_tri(poly[0], poly[k], poly[k + 1])

    if not tris:
        return None
    return (verts, tris, convex_radius)



def extract_compound_polytopes(
        data: bytes, data_start: int,
        fixups: Dict[int, int],
        gfixups: Dict[int, Tuple[int, int]],
        objects: List[Tuple[int, str]],
        body_transforms: Dict[int, BodyTransform],
) -> List[CollisionShape]:
    """Extract convex polytope shapes from hknpDynamicCompoundShape instances.

    Returns a list of CollisionShape objects.  Each hknpDynamicCompoundShape
    becomes a "compound" CollisionShape (no geometry) whose children are
    "polytope" CollisionShapes carrying local-space verts and their instance
    transforms.  Standalone ConvexPolytopeShapes (not part of any compound)
    are returned as top-level "polytope" CollisionShapes.

    Transforms are NOT applied to vertices; they are stored on each shape so
    the caller (e.g. Blender) can set object location/rotation accordingly.
    """
    result: List[CollisionShape] = []

    obj_map = {rel: cls for rel, cls in objects}

    compounds = [(rel, cls) for rel, cls in objects if "DynamicCompoundShape" in cls
                 and "Data" not in cls]

    for comp_idx, (comp_rel, _) in enumerate(compounds):
        comp_abs = data_start + comp_rel
        body = body_transforms.get(comp_rel)

        inst_arr_ptr = fixups.get(comp_rel + 0x60)
        inst_count = u32(data, comp_abs + 0x60 + 8) & 0x3FFFFFFF
        if inst_arr_ptr is None or inst_count == 0:
            continue

        inst_arr_abs = data_start + inst_arr_ptr
        INST_STRIDE = 0x80

        comp_name = "Compound" if len(compounds) == 1 else f"Compound_{comp_idx}"
        compound_shape = CollisionShape(
            shape_type="compound",
            name=comp_name,
            transform=body,
            verts=[],
            faces=[],
            convex_radius=0.0,
            children=[],
        )

        for i in range(inst_count):
            inst_abs = inst_arr_abs + i * INST_STRIDE
            inst_rel = inst_abs - data_start

            r0 = vec4(data, inst_abs + 0x00)
            r1 = vec4(data, inst_abs + 0x10)
            r2 = vec4(data, inst_abs + 0x20)
            # Havok stores the rotation as three column vectors (hkRotation column-major).
            # Transpose to row-major so standard M*v multiplication works correctly.
            rot: Mat3 = ((r0[0], r1[0], r2[0]),
                         (r0[1], r1[1], r2[1]),
                         (r0[2], r1[2], r2[2]))
            t = vec4(data, inst_abs + 0x30)
            trans = (t[0], t[1], t[2])

            gf = gfixups.get(inst_rel + 0x50)
            if gf is None:
                continue
            shape_rel = gf[1]
            shape_abs = data_start + shape_rel
            if "ConvexPolytopeShape" not in obj_map.get(shape_rel, ""):
                continue

            parsed = parse_convex_polytope(data, shape_abs)
            if parsed is None:
                continue
            local_verts, local_tris, convex_radius = parsed

            inst_transform = BodyTransform(position=trans, rotation=rot)
            compound_shape.children.append(CollisionShape(
                shape_type="polytope",
                name=f"Polytope_{i}",
                transform=inst_transform,
                verts=local_verts,
                faces=local_tris,
                convex_radius=convex_radius,
                children=[],
            ))

        if compound_shape.children:
            result.append(compound_shape)

    # Collect all polytope rels that belong to a compound instance
    compound_shape_rels: set = set()
    for comp_rel, _ in compounds:
        comp_abs = data_start + comp_rel
        inst_arr_ptr = fixups.get(comp_rel + 0x60)
        inst_count = u32(data, comp_abs + 0x60 + 8) & 0x3FFFFFFF
        if inst_arr_ptr is not None:
            inst_arr_abs = data_start + inst_arr_ptr
            for i in range(inst_count):
                inst_rel = (inst_arr_abs + i * 0x80) - data_start
                gf = gfixups.get(inst_rel + 0x50)
                if gf:
                    compound_shape_rels.add(gf[1])

    standalone = [(rel, cls) for rel, cls in objects
                  if "ConvexPolytopeShape" in cls and rel not in compound_shape_rels]

    for shape_rel, _ in standalone:
        shape_abs = data_start + shape_rel
        parsed = parse_convex_polytope(data, shape_abs)
        if parsed is None:
            continue
        local_verts, local_tris, convex_radius = parsed
        result.append(CollisionShape(
            shape_type="polytope",
            name=f"Polytope_standalone_{shape_rel:#x}",
            transform=body_transforms.get(shape_rel),
            verts=local_verts,
            faces=local_tris,
            convex_radius=convex_radius,
            children=[],
        ))

    return result


# ── main extraction ──────────────────────────────────────────────────────────

def extract_bhk_physics_system(
        in_path: Optional[str] = None,
        out_path: Optional[str] = None,
        raw_data: Optional[bytes] = None,
) -> List[CollisionShape]:
    """Extract all collision geometry from a raw Havok packfile blob.

    Returns a list of CollisionShape objects.  Vertices are in local space;
    each shape carries its own transform (body or instance position/rotation)
    so the caller can apply it at the object level.

    Args:
        in_path:  Path to a raw packfile .bin (optional; use raw_data instead).
        out_path: If given, writes an OBJ file at this path.
        raw_data: Raw packfile bytes (preferred when called from pynifly).
    """
    if raw_data is not None:
        data = raw_data
    else:
        if in_path is None:
            raise RuntimeError("in_path or raw_data must be provided")
        data = open(in_path, "rb").read()
    use_shared = True

    # ── parse packfile ──
    hdrs = parse_section_headers(data)
    if "__data__" not in hdrs or "__classnames__" not in hdrs:
        raise RuntimeError("Missing __data__ or __classnames__ section header.")

    data_hdr = hdrs["__data__"]
    data_start = data_hdr.abs_start
    cn_start = hdrs["__classnames__"].abs_start

    fixups = parse_local_fixups(data, data_hdr)
    gfixups = parse_global_fixups(data, data_hdr)
    objects = parse_virtual_fixups(data, data_hdr, cn_start)

    # ── parse body transforms from PhysicsSystemData ──
    body_transforms = parse_body_transforms(data, data_start, fixups, gfixups, objects)

    # ── propagate compound instance transforms to child mesh data objects ──
    obj_map = {rel: cls for rel, cls in objects}
    compounds = [(rel, cls) for rel, cls in objects
                 if "DynamicCompoundShape" in cls and "Data" not in cls]

    for comp_rel, comp_cls in compounds:
        comp_abs = data_start + comp_rel
        comp_body = body_transforms.get(comp_rel)

        inst_arr_ptr = fixups.get(comp_rel + 0x60)
        inst_count = u32(data, comp_abs + 0x60 + 8) & 0x3FFFFFFF
        if inst_arr_ptr is None or inst_count == 0:
            continue

        inst_arr_abs = data_start + inst_arr_ptr
        INST_STRIDE = 0x80

        for i in range(inst_count):
            inst_abs = inst_arr_abs + i * INST_STRIDE
            inst_rel = inst_abs - data_start

            r0 = vec4(data, inst_abs + 0x00)
            r1 = vec4(data, inst_abs + 0x10)
            r2 = vec4(data, inst_abs + 0x20)
            # Havok stores columns; transpose to row-major.
            inst_rot: Mat3 = ((r0[0], r1[0], r2[0]),
                              (r0[1], r1[1], r2[1]),
                              (r0[2], r1[2], r2[2]))

            t = vec4(data, inst_abs + 0x30)
            inst_trans = (t[0], t[1], t[2])

            gf = gfixups.get(inst_rel + 0x50)
            if gf is None:
                continue
            child_shape_rel = gf[1]
            child_shape_cls = obj_map.get(child_shape_rel, "")

            if "CompressedMeshShape" in child_shape_cls and "Data" not in child_shape_cls:
                data_gf = gfixups.get(child_shape_rel + 0x60)
                if data_gf is None:
                    continue
                child_data_rel = data_gf[1]

                if comp_body is not None:
                    comb_rot = mat3_mul(comp_body.rotation, inst_rot)
                    tx = (comp_body.rotation[0][0] * inst_trans[0] +
                          comp_body.rotation[0][1] * inst_trans[1] +
                          comp_body.rotation[0][2] * inst_trans[2] + comp_body.position[0])
                    ty = (comp_body.rotation[1][0] * inst_trans[0] +
                          comp_body.rotation[1][1] * inst_trans[1] +
                          comp_body.rotation[1][2] * inst_trans[2] + comp_body.position[1])
                    tz = (comp_body.rotation[2][0] * inst_trans[0] +
                          comp_body.rotation[2][1] * inst_trans[1] +
                          comp_body.rotation[2][2] * inst_trans[2] + comp_body.position[2])
                    comb_trans = (tx, ty, tz)
                else:
                    comb_rot = inst_rot
                    comb_trans = inst_trans

                is_identity_rot = all(
                    abs(comb_rot[ii][jj] - (1.0 if ii == jj else 0.0)) < 1e-6
                    for ii in range(3) for jj in range(3))
                is_zero_trans = all(abs(c) < 1e-6 for c in comb_trans)

                if not (is_identity_rot and is_zero_trans):
                    body_transforms[child_data_rel] = BodyTransform(
                        position=comb_trans,
                        rotation=comb_rot,
                    )

    all_shapes: List[CollisionShape] = []

    # ── extract compressed mesh shapes ──
    mesh_shapes = [(rel, cls) for rel, cls in objects
                   if "hknpCompressedMeshShapeData" in cls]

    for shape_idx, (obj_rel, _) in enumerate(mesh_shapes):
        obj_abs = data_start + obj_rel
        extract_bhk_physics_system._large_cache = {}

        mesh_body = body_transforms.get(obj_rel)

        sections_abs   = hkarray_abs(fixups, data_start, obj_rel, 0x50)
        sections_count = hkarray_size(data, obj_abs, 0x50)
        quads_abs      = hkarray_abs(fixups, data_start, obj_rel, 0x60)
        total_quads    = hkarray_size(data, obj_abs, 0x60)
        shidx_abs      = hkarray_abs(fixups, data_start, obj_rel, 0x70)
        total_shidx    = hkarray_size(data, obj_abs, 0x70)
        verts_abs      = hkarray_abs(fixups, data_start, obj_rel, 0x80)
        total_verts    = hkarray_size(data, obj_abs, 0x80)
        shared_abs     = hkarray_abs(fixups, data_start, obj_rel, 0x90)
        total_shared   = hkarray_size(data, obj_abs, 0x90)

        obj_bb_min = vec3(data, obj_abs + 0x20)
        obj_bb_max = vec3(data, obj_abs + 0x30)

        if sections_abs is None or sections_count == 0:
            continue
        if verts_abs is None or quads_abs is None:
            continue
        if total_verts == 0 or total_quads == 0:
            continue

        idx_fmt = "u8"
        quad_stride = 4

        secs = read_sections(data, sections_abs, sections_count,
                             total_verts, total_quads, total_shared, total_shidx)

        shape_verts: List[Vert3] = []
        shape_faces: List[Face] = []

        for sec in secs:
            first_v   = sec["first_vertex"]
            num_v     = sec["num_vertices"]
            num_q     = sec["num_quads"]
            first_q   = sec["first_quad"]
            first_sh  = sec["first_shared"]
            num_sh    = sec["num_shared"]

            if num_q == 0:
                continue
            if num_v == 0 and num_sh == 0:
                continue

            v_buf = verts_abs + first_v * 4
            local_verts = decode_vertices(data, v_buf, num_v,
                                          sec["base"], sec["scale"])

            shared_verts: List[Vert3] = []
            if use_shared and shared_abs is not None and num_sh > 0:
                if not hasattr(extract_bhk_physics_system, '_large_cache'):
                    extract_bhk_physics_system._large_cache = {}
                cache_key = (shared_abs, total_shared)
                if cache_key not in extract_bhk_physics_system._large_cache:
                    extract_bhk_physics_system._large_cache[cache_key] = decode_large_vertices(
                        data, shared_abs, total_shared, obj_bb_min, obj_bb_max)
                global_large = extract_bhk_physics_system._large_cache[cache_key]

                if shidx_abs is not None and total_shidx > 0:
                    for k in range(num_sh):
                        map_off = shidx_abs + (first_sh + k) * 2
                        if map_off + 2 <= len(data):
                            gi = u16(data, map_off)
                            if gi < len(global_large):
                                shared_verts.append(global_large[gi])
                            else:
                                shared_verts.append((0.0, 0.0, 0.0))
                        else:
                            shared_verts.append((0.0, 0.0, 0.0))
                else:
                    for k in range(num_sh):
                        if first_sh + k < len(global_large):
                            shared_verts.append(global_large[first_sh + k])
                        else:
                            shared_verts.append((0.0, 0.0, 0.0))

            idx_limit = len(local_verts) + len(shared_verts)
            q_buf = quads_abs + first_q * quad_stride

            if idx_fmt == "u16":
                tris = decode_quads_u16(data, q_buf, num_q, idx_limit)
            else:
                tris = decode_quads_u8(data, q_buf, num_q, idx_limit)

            # Face indices are relative to this shape's local vertex list
            base_idx = len(shape_verts)
            shape_verts.extend(local_verts + shared_verts)
            shape_faces.extend((a + base_idx, b + base_idx, c + base_idx)
                               for a, b, c in tris)

        if shape_verts and shape_faces:
            mesh_name = "CompressedMesh" if len(mesh_shapes) == 1 else f"CompressedMesh_{shape_idx}"
            all_shapes.append(CollisionShape(
                shape_type="compressed_mesh",
                name=mesh_name,
                transform=mesh_body,
                verts=shape_verts,
                faces=shape_faces,
                convex_radius=0.0,
                children=[],
            ))

    # ── extract convex polytope shapes ──
    all_shapes.extend(extract_compound_polytopes(
        data, data_start, fixups, gfixups, objects, body_transforms))

    # ── extract sphere shapes ──
    sphere_objects = [(rel, cls) for rel, cls in objects
                      if "hknpSphereShape" in cls]
    for shape_idx, (obj_rel, _) in enumerate(sphere_objects):
        obj_abs = data_start + obj_rel
        radius = f32(data, obj_abs + 0x14)
        sphere_body = body_transforms.get(obj_rel)
        name = "SphereShape" if len(sphere_objects) == 1 else f"SphereShape_{shape_idx}"
        all_shapes.append(CollisionShape(
            shape_type="sphere",
            name=name,
            transform=sphere_body,
            verts=[],
            faces=[],
            convex_radius=0.0,
            children=[],
            sphere_radius=radius,
        ))

    if not all_shapes:
        raise RuntimeError("No geometry decoded.")

    if out_path is not None:
        write_obj(out_path, all_shapes)

    return all_shapes


# ── pynifly compatibility wrapper ────────────────────────────────────────────

def parse_bytes(data: bytes) -> List[CollisionShape]:
    """Parse a raw Havok packfile and return a list of CollisionShape objects.

    This is the primary entry point used by bhkPhysicsSystem.geometry in pynifly.
    Each shape carries local-space geometry and a transform (position/rotation)
    that the caller should apply at the object level.
    """
    return extract_bhk_physics_system(raw_data=data)


# ── NIF-level entry point ─────────────────────────────────────────────────────

HAVOK_MAGIC = bytes((0x57, 0xE0, 0xE0, 0x57, 0x10, 0xC0, 0xC0, 0x10))


def _read_len_u8_string(data: bytes, off: int) -> Tuple[str, int]:
    ln = u8(data, off)
    off += 1
    s = data[off:off + ln].decode("utf-8", errors="replace")
    off += ln
    if s.endswith("\x00"):
        s = s[:-1]
    return s, off


def _extract_ninode_transform(block: bytes, num_blocks: int) -> dict:
    def score(t_off: int) -> float:
        if t_off + 0x34 + 4 > len(block):
            return -1e9
        r = [f32(block, t_off + 0x0C + i * 4) for i in range(9)]
        s = f32(block, t_off + 0x30)
        score_v = 0.0
        if not all(math.isfinite(x) for x in (r + [s])):
            score_v -= 1e6
        else:
            l0 = math.sqrt(r[0] * r[0] + r[1] * r[1] + r[2] * r[2])
            l1 = math.sqrt(r[3] * r[3] + r[4] * r[4] + r[5] * r[5])
            l2 = math.sqrt(r[6] * r[6] + r[7] * r[7] + r[8] * r[8])
            d01 = r[0] * r[3] + r[1] * r[4] + r[2] * r[5]
            d02 = r[0] * r[6] + r[1] * r[7] + r[2] * r[8]
            d12 = r[3] * r[6] + r[4] * r[7] + r[5] * r[8]
            score_v -= abs(l0 - 1.0) + abs(l1 - 1.0) + abs(l2 - 1.0)
            score_v -= abs(d01) + abs(d02) + abs(d12)
            score_v -= abs(s - 1.0)
        co = i32(block, t_off + 0x34)
        if not (co == -1 or (0 <= co < num_blocks)):
            score_v -= 500.0
        nchild = i32(block, t_off + 0x38) if t_off + 0x3C <= len(block) else -1
        if nchild < 0 or nchild > 4096:
            score_v -= 500.0
        return score_v

    t_off = max((0x10, 0x14, 0x18, 0x1C), key=score)
    tx, ty, tz = f32(block, t_off + 0x00), f32(block, t_off + 0x04), f32(block, t_off + 0x08)
    rot: Mat3 = (
        (f32(block, t_off + 0x0C), f32(block, t_off + 0x10), f32(block, t_off + 0x14)),
        (f32(block, t_off + 0x18), f32(block, t_off + 0x1C), f32(block, t_off + 0x20)),
        (f32(block, t_off + 0x24), f32(block, t_off + 0x28), f32(block, t_off + 0x2C)),
    )
    scale = f32(block, t_off + 0x30)
    co = i32(block, t_off + 0x34)
    nchild = i32(block, t_off + 0x38) if t_off + 0x3C <= len(block) else 0
    children: List[int] = []
    cl_off = t_off + 0x3C
    if 0 <= nchild <= 4096 and cl_off + nchild * 4 <= len(block):
        for i in range(nchild):
            children.append(i32(block, cl_off + i * 4))
    return {"t": (tx, ty, tz), "r": rot, "s": scale if math.isfinite(scale) else 1.0, "co": co, "children": children}


def _parse_nif_blocks(nif_data: bytes) -> Tuple[List[dict], int]:
    nl = nif_data.find(b"\n")
    if nl < 0:
        raise RuntimeError("NIF header newline not found")
    off = nl + 1
    file_version = u32(nif_data, off)
    off += 4
    if file_version != 0x14020007:
        raise RuntimeError("Only FO4 NIF version 0x14020007 is supported")
    off += 1  # endian flag
    off += 4  # user version
    num_blocks = u32(nif_data, off)
    off += 4
    off += 4  # user version2
    for _ in range(4):
        _, off = _read_len_u8_string(nif_data, off)

    num_block_types = u16(nif_data, off)
    off += 2
    block_types: List[str] = []
    for _ in range(num_block_types):
        ln = u32(nif_data, off)
        off += 4
        block_types.append(nif_data[off:off + ln].decode("utf-8", errors="replace"))
        off += ln
    block_type_index = [u16(nif_data, off + i * 2) for i in range(num_blocks)]
    off += num_blocks * 2
    block_sizes = [u32(nif_data, off + i * 4) for i in range(num_blocks)]
    off += num_blocks * 4
    num_strings = u32(nif_data, off)
    off += 4
    off += 4  # max_string_len
    strings: List[str] = []
    for _ in range(num_strings):
        ln = u32(nif_data, off)
        off += 4
        strings.append(nif_data[off:off + ln].decode("utf-8", errors="replace"))
        off += ln
    num_groups = u32(nif_data, off)
    off += 4
    for _ in range(num_groups):
        n = u32(nif_data, off)
        off += 4 + n * 4

    cur = off
    blocks: List[dict] = []
    for i in range(num_blocks):
        btype = block_types[block_type_index[i]]
        sz = block_sizes[i]
        blob = nif_data[cur:cur + sz]
        info = {"id": i, "type": btype, "offset": cur, "size": sz, "blob": blob, "transform": None}
        if btype == "NiNode" and len(blob) >= 0x44:
            info["transform"] = _extract_ninode_transform(blob, num_blocks)
        blocks.append(info)
        cur += sz
    return blocks, num_blocks


def _resolve_collision_physics_pairs(blocks: List[dict]) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for b in blocks:
        if b["type"] != "NiNode" or b["transform"] is None:
            continue
        co = b["transform"]["co"]
        if not (0 <= co < len(blocks)):
            continue
        if blocks[co]["type"] != "bhkNPCollisionObject":
            continue
        co_blob: bytes = blocks[co]["blob"]
        phys = set()
        for o in range(0, max(0, len(co_blob) - 3)):
            v = i32(co_blob, o)
            if 0 <= v < len(blocks) and blocks[v]["type"] == "bhkPhysicsSystem":
                phys.add(v)
        for pid in sorted(phys):
            pairs.append((b["id"], pid))
    return pairs


def extract_havok_from_nif(in_path: str, out_path: str) -> None:
    """Standalone entry point: read a .nif, extract all collision geometry, write OBJ."""
    nif_data = Path(in_path).read_bytes()
    blocks, _ = _parse_nif_blocks(nif_data)
    pairs = _resolve_collision_physics_pairs(blocks)
    if not pairs:
        raise RuntimeError("No NiNode->bhkNPCollisionObject->bhkPhysicsSystem links found.")

    # Same bhkPhysicsSystem can be referenced by several NiNodes.
    # Decode each only once.
    phys_ids: List[int] = []
    seen_phys = set()
    for _, phys_id in pairs:
        if phys_id not in seen_phys:
            seen_phys.add(phys_id)
            phys_ids.append(phys_id)

    all_shapes: List[CollisionShape] = []
    decoded = 0

    for phys_id in phys_ids:
        blob: bytes = blocks[phys_id]["blob"]
        if blob.startswith(HAVOK_MAGIC):
            hk = blob
        elif len(blob) >= 12 and blob[4:12] == HAVOK_MAGIC:
            hk = blob[4:]
        else:
            continue

        shapes = extract_bhk_physics_system(raw_data=hk)
        prefix = f"phys_{phys_id}"
        for s in shapes:
            s.name = f"{prefix}_{s.name}"
        all_shapes.extend(shapes)
        decoded += 1

    if decoded == 0 or not all_shapes:
        raise RuntimeError("No embedded Havok payloads decoded from linked bhkPhysicsSystem blocks.")
    write_obj(out_path, all_shapes)


def _main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python bhk_autounpack.py <input.nif>")
        return 1
    in_path = sys.argv[1]
    if not in_path.lower().endswith(".nif"):
        print("Input must be a .nif file.")
        return 1
    out_path = str((Path(__file__).resolve().parent / "bhk_autounpack.obj"))
    extract_havok_from_nif(in_path, out_path)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
