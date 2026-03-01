#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bhk_autounpack.py
-----------------
Extract collision mesh from bhkPhysicsSystem Havok packfile BIN -> OBJ.

Run:
  python bhk_autounpack.py <input.bin>
  Output .obj is written next to the input file (same name, .obj).

Config flags (edit in this file):
  POLY_BEVEL_ENABLED   - enable/disable bevel for ConvexPolytopeShape
  POLY_BEVEL_WIDTH     - bevel width (units of the file)
  POLY_BEVEL_SEGMENTS  - bevel segments
  TRIANGULATE_OUTPUT   - triangulate polytopes (compressed mesh is always triangulated)

Notes:
  Primitive extraction is still in progress, as is the bevel component.
  TODO: parse physical properties (mass/inertia, friction, restitution) from
        hknpShapeMassProperties / hknpBSMaterialProperties / PhysicsSystemData.

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
"""

import struct
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math

# ── helpers ──────────────────────────────────────────────────────────────────

def u8(data: bytes, off: int) -> int:
    return data[off]

def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]

def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]

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

# Fixed bevel settings for convex polytopes (edge bevel)
POLY_BEVEL_ENABLED = False
POLY_BEVEL_WIDTH = 0.01
POLY_BEVEL_SEGMENTS = 2

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

def write_obj(path: str, verts: List[Vert3],
              faces: List[Tuple[Face, str]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# bhkPhysicsSystem collision mesh\n")
        f.write(f"# verts={len(verts)} faces={len(faces)}\n\n")
        f.write("o CollisionMesh\n")
        for x, y, z in verts:
            f.write(f"v {x:.6f} {z:.6f} {-y:.6f}\n")
        cur_group = None
        for face, g in faces:
            if g != cur_group:
                f.write(f"\ng {g}\n")
                cur_group = g
            f.write("f " + " ".join(str(i + 1) for i in face) + "\n")


# ── convex polytope extraction ───────────────────────────────────────────────

def parse_convex_polytope(data: bytes, shape_abs: int) -> Optional[Tuple[List[Vert3], List[Face]]]:
    """Parse an hknpConvexPolytopeShape and return (vertices, faces).

    Layout (inline shape, hk_2014.1.0):
      +0x30: numVertices (u16), verticesOffset (u16, from +0x30)
      +0x40: numVerts2 (u16), planesOff (u16), numPlanes (u16),
             facesOff (u16), numFaceVtxIndices (u16), faceVtxOff (u16)
      +0x50: vertices begin at +0x30 + verticesOffset (vec4 each, w = packed idx)
      faces: each 4 bytes: firstVtxIdx (u16), numVtx (u8), flags (u8)
      faceVtxIndices: u8 array of vertex indices per face
    """
    num_verts = u16(data, shape_abs + 0x30)
    vert_offset = u16(data, shape_abs + 0x32)

    header40 = [u16(data, shape_abs + 0x40 + i * 2) for i in range(6)]
    planes_off = header40[1]  # offset from +0x40
    num_planes = header40[2]
    faces_off  = header40[3]  # offset from +0x40
    num_fvi    = header40[4]  # total face vertex indices
    fvi_off    = header40[5]  # offset from +0x40

    if num_verts == 0 or num_planes == 0:
        return None

    # Read vertices (vec4 each, ignore w)
    vert_start = shape_abs + 0x30 + vert_offset
    verts: List[Vert3] = []
    for i in range(num_verts):
        v = vec4(data, vert_start + i * 16)
        verts.append((v[0], v[1], v[2]))

    # Read face vertex indices
    fvi_start = shape_abs + 0x40 + fvi_off
    fvi_bytes = data[fvi_start:fvi_start + num_fvi]

    def triangulate_faces_from_indices() -> List[Tri]:
        faces_start = shape_abs + 0x40 + faces_off
        out: List[Tri] = []
        for fi in range(num_planes):
            fo = faces_start + fi * 4
            first = u16(data, fo)
            count = u8(data, fo + 2)
            if count < 3:
                continue
            if first + count > len(fvi_bytes):
                continue
            face_indices = [fvi_bytes[first + j] for j in range(count)]
            # Skip clearly degenerate faces
            if len(set(face_indices)) < 3:
                continue
            for j in range(1, len(face_indices) - 1):
                a, b, c = face_indices[0], face_indices[j], face_indices[j + 1]
                if max(a, b, c) < num_verts:
                    out.append((a, b, c))
        return out

    def triangulate_faces_from_planes(verts_in: List[Vert3],
                                      planes_in: List[Tuple[float, float, float, float]]) -> List[Tri]:
        planes = planes_in
        out: List[Tri] = []
        eps = 1e-4

        for nx, ny, nz, d in planes:
            # Collect vertices on this plane
            on_plane: List[int] = []
            for vi, (x, y, z) in enumerate(verts_in):
                dist = nx * x + ny * y + nz * z + d
                if abs(dist) <= eps:
                    on_plane.append(vi)
            if len(on_plane) < 3:
                continue

            # Build local 2D basis on the plane
            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len == 0.0:
                continue
            nxn, nyn, nzn = nx / n_len, ny / n_len, nz / n_len
            # Choose a reference axis not parallel to the normal
            if abs(nxn) < 0.9:
                rx, ry, rz = 1.0, 0.0, 0.0
            else:
                rx, ry, rz = 0.0, 1.0, 0.0
            # u = normalize(cross(n, ref))
            ux, uy, uz = (nyn * rz - nzn * ry,
                          nzn * rx - nxn * rz,
                          nxn * ry - nyn * rx)
            u_len = math.sqrt(ux * ux + uy * uy + uz * uz)
            if u_len == 0.0:
                continue
            ux, uy, uz = ux / u_len, uy / u_len, uz / u_len
            # v = cross(n, u)
            vx, vy, vz = (nyn * uz - nzn * uy,
                          nzn * ux - nxn * uz,
                          nxn * uy - nyn * ux)

            # centroid
            cx = sum(verts_in[i][0] for i in on_plane) / len(on_plane)
            cy = sum(verts_in[i][1] for i in on_plane) / len(on_plane)
            cz = sum(verts_in[i][2] for i in on_plane) / len(on_plane)

            # sort by angle around normal
            def angle(i: int) -> float:
                px, py, pz = verts_in[i]
                dx, dy, dz = px - cx, py - cy, pz - cz
                x2 = dx * ux + dy * uy + dz * uz
                y2 = dx * vx + dy * vy + dz * vz
                return math.atan2(y2, x2)

            ring = sorted(on_plane, key=angle)
            # triangulate fan
            for j in range(1, len(ring) - 1):
                out.append((ring[0], ring[j], ring[j + 1]))
        return out

    def build_faces_from_planes(verts_in: List[Vert3],
                                planes_in: List[Tuple[float, float, float, float]]) -> List[Face]:
        planes = planes_in
        out: List[Face] = []
        eps = 1e-4

        for nx, ny, nz, d in planes:
            on_plane: List[int] = []
            for vi, (x, y, z) in enumerate(verts_in):
                dist = nx * x + ny * y + nz * z + d
                if abs(dist) <= eps:
                    on_plane.append(vi)
            if len(on_plane) < 3:
                continue

            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len == 0.0:
                continue
            nxn, nyn, nzn = nx / n_len, ny / n_len, nz / n_len
            if abs(nxn) < 0.9:
                rx, ry, rz = 1.0, 0.0, 0.0
            else:
                rx, ry, rz = 0.0, 1.0, 0.0
            ux, uy, uz = (nyn * rz - nzn * ry,
                          nzn * rx - nxn * rz,
                          nxn * ry - nyn * rx)
            u_len = math.sqrt(ux * ux + uy * uy + uz * uz)
            if u_len == 0.0:
                continue
            ux, uy, uz = ux / u_len, uy / u_len, uz / u_len
            vx, vy, vz = (nyn * uz - nzn * uy,
                          nzn * ux - nxn * uz,
                          nxn * uy - nyn * ux)

            cx = sum(verts_in[i][0] for i in on_plane) / len(on_plane)
            cy = sum(verts_in[i][1] for i in on_plane) / len(on_plane)
            cz = sum(verts_in[i][2] for i in on_plane) / len(on_plane)

            def angle(i: int) -> float:
                px, py, pz = verts_in[i]
                dx, dy, dz = px - cx, py - cy, pz - cz
                x2 = dx * ux + dy * uy + dz * uz
                y2 = dx * vx + dy * vy + dz * vz
                return math.atan2(y2, x2)

            ring = sorted(on_plane, key=angle)
            if len(ring) >= 3:
                out.append(tuple(ring))
        return out

    def intersect_planes(p1, p2, p3) -> Optional[Vert3]:
        (a1, b1, c1, d1) = p1
        (a2, b2, c2, d2) = p2
        (a3, b3, c3, d3) = p3
        det = (a1 * (b2 * c3 - b3 * c2)
               - b1 * (a2 * c3 - a3 * c2)
               + c1 * (a2 * b3 - a3 * b2))
        if abs(det) < 1e-8:
            return None
        dx = (-d1 * (b2 * c3 - b3 * c2)
              + b1 * (-d2 * c3 + d3 * c2)
              - c1 * (-d2 * b3 + d3 * b2))
        dy = (a1 * (-d2 * c3 + d3 * c2)
              - (-d1) * (a2 * c3 - a3 * c2)
              + c1 * (a2 * (-d3) - a3 * (-d2)))
        dz = (a1 * (b2 * (-d3) - b3 * (-d2))
              - b1 * (a2 * (-d3) - a3 * (-d2))
              + (-d1) * (a2 * b3 - a3 * b2))
        return (dx / det, dy / det, dz / det)

    def unique_points(points: List[Vert3], eps: float = 1e-5) -> List[Vert3]:
        out: List[Vert3] = []
        eps2 = eps * eps
        for p in points:
            keep = True
            for q in out:
                dx = p[0] - q[0]
                dy = p[1] - q[1]
                dz = p[2] - q[2]
                if dx * dx + dy * dy + dz * dz <= eps2:
                    keep = False
                    break
            if keep:
                out.append(p)
        return out

    planes_start = shape_abs + 0x40 + planes_off
    base_planes_raw = [vec4(data, planes_start + i * 16) for i in range(num_planes)]
    base_planes: List[Tuple[float, float, float, float]] = []
    for nx, ny, nz, d in base_planes_raw:
        n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
        if n_len == 0.0:
            continue
        base_planes.append((nx / n_len, ny / n_len, nz / n_len, d / n_len))

    # Edge bevel: add planes between adjacent face planes
    if POLY_BEVEL_ENABLED and POLY_BEVEL_WIDTH > 0.0 and POLY_BEVEL_SEGMENTS > 0 and len(base_planes) >= 4:
        eps = 1e-4
        plane_verts: List[set] = []
        for nx, ny, nz, d in base_planes:
            on_plane = set()
            for vi, (x, y, z) in enumerate(verts):
                if abs(nx * x + ny * y + nz * z + d) <= eps:
                    on_plane.add(vi)
            plane_verts.append(on_plane)

        bevel_planes: List[Tuple[float, float, float, float]] = []
        for i in range(len(base_planes)):
            n1x, n1y, n1z, d1 = base_planes[i]
            c1 = -d1
            for j in range(i + 1, len(base_planes)):
                n2x, n2y, n2z, d2 = base_planes[j]
                c2 = -d2
                shared = plane_verts[i].intersection(plane_verts[j])
                if len(shared) < 2:
                    continue
                sx, sy, sz = (n1x + n2x, n1y + n2y, n1z + n2z)
                s_len = math.sqrt(sx * sx + sy * sy + sz * sz)
                if s_len < 1e-6:
                    continue
                mx, my, mz = sx / s_len, sy / s_len, sz / s_len
                for s in range(1, POLY_BEVEL_SEGMENTS + 1):
                    w = POLY_BEVEL_WIDTH * (s / (POLY_BEVEL_SEGMENTS + 1))
                    c_m = (c1 + c2 - 2.0 * w) / s_len
                    d_m = -c_m
                    bevel_planes.append((mx, my, mz, d_m))

        all_planes = base_planes + bevel_planes
        candidates: List[Vert3] = []
        for a in range(len(all_planes)):
            for b in range(a + 1, len(all_planes)):
                for c in range(b + 1, len(all_planes)):
                    p = intersect_planes(all_planes[a], all_planes[b], all_planes[c])
                    if p is None:
                        continue
                    x, y, z = p
                    inside = True
                    for nx, ny, nz, d in all_planes:
                        if nx * x + ny * y + nz * z + d > eps:
                            inside = False
                            break
                    if inside:
                        candidates.append(p)
        beveled_verts = unique_points(candidates)
        if beveled_verts:
            if TRIANGULATE_OUTPUT:
                tris = triangulate_faces_from_planes(beveled_verts, all_planes)
                return (beveled_verts, tris) if tris else None
            faces = build_faces_from_planes(beveled_verts, all_planes)
            return (beveled_verts, faces) if faces else None

    tris = triangulate_faces_from_indices()
    plane_tris = triangulate_faces_from_planes(verts, base_planes)
    if len(plane_tris) > len(tris):
        tris = plane_tris

    if not tris:
        return None
    if TRIANGULATE_OUTPUT:
        return (verts, tris)
    faces = build_faces_from_planes(verts, base_planes)
    return (verts, faces) if faces else (verts, tris)


def apply_transform(verts: List[Vert3],
                    rot: Mat3,
                    trans: Tuple[float, float, float],
                    body: Optional[BodyTransform] = None) -> List[Vert3]:
    """Apply instance rotation+translation, then optional body rotation+translation."""
    result: List[Vert3] = []
    for x, y, z in verts:
        # Instance transform
        rx = rot[0][0] * x + rot[1][0] * y + rot[2][0] * z + trans[0]
        ry = rot[0][1] * x + rot[1][1] * y + rot[2][1] * z + trans[1]
        rz = rot[0][2] * x + rot[1][2] * y + rot[2][2] * z + trans[2]
        # Body transform
        if body is not None:
            bx = body.rotation[0][0]*rx + body.rotation[0][1]*ry + body.rotation[0][2]*rz + body.position[0]
            by = body.rotation[1][0]*rx + body.rotation[1][1]*ry + body.rotation[1][2]*rz + body.position[1]
            bz = body.rotation[2][0]*rx + body.rotation[2][1]*ry + body.rotation[2][2]*rz + body.position[2]
            rx, ry, rz = bx, by, bz
        result.append((rx, ry, rz))
    return result


def extract_compound_polytopes(
        data: bytes, data_start: int,
        fixups: Dict[int, int],
        gfixups: Dict[int, Tuple[int, int]],
        objects: List[Tuple[int, str]],
        body_transforms: Dict[int, BodyTransform],
) -> Tuple[List[Vert3], List[Tuple[Face, str]]]:
    """Extract convex polytope shapes from hknpDynamicCompoundShape instances."""

    all_verts: List[Vert3] = []
    all_tris: List[Tuple[Face, str]] = []

    # Build a map from rel_offset -> class name for quick lookup
    obj_map = {rel: cls for rel, cls in objects}

    # Find DynamicCompoundShape objects
    compounds = [(rel, cls) for rel, cls in objects if "DynamicCompoundShape" in cls
                 and "Data" not in cls]

    for comp_rel, comp_cls in compounds:
        comp_abs = data_start + comp_rel

        # Look up body transform for this compound shape
        body = body_transforms.get(comp_rel)

        # hkArray of instances at +0x60
        inst_arr_ptr = fixups.get(comp_rel + 0x60)
        inst_count = u32(data, comp_abs + 0x60 + 8) & 0x3FFFFFFF

        if inst_arr_ptr is None or inst_count == 0:
            continue

        inst_arr_abs = data_start + inst_arr_ptr

        INST_STRIDE = 0x80

        for i in range(inst_count):
            inst_abs = inst_arr_abs + i * INST_STRIDE
            inst_rel = inst_abs - data_start

            # Rotation matrix (3 rows of vec4, xyz used)
            r0 = vec4(data, inst_abs + 0x00)
            r1 = vec4(data, inst_abs + 0x10)
            r2 = vec4(data, inst_abs + 0x20)
            rot = ((r0[0], r0[1], r0[2]),
                   (r1[0], r1[1], r1[2]),
                   (r2[0], r2[1], r2[2]))

            # Translation
            t = vec4(data, inst_abs + 0x30)
            trans = (t[0], t[1], t[2])

            # Shape reference via global fixup at +0x50
            shape_ptr_rel = inst_rel + 0x50
            gf = gfixups.get(shape_ptr_rel)
            if gf is None:
                continue

            shape_rel = gf[1]
            shape_abs = data_start + shape_rel
            shape_cls = obj_map.get(shape_rel, "?")

            if "ConvexPolytopeShape" not in shape_cls:
                continue

            result = parse_convex_polytope(data, shape_abs)
            if result is None:
                continue

            local_verts, local_tris = result
            transformed = apply_transform(local_verts, rot, trans, body=body)

            base_idx = len(all_verts)
            all_verts.extend(transformed)

            group = f"Polytope_{i}"
            all_tris.extend(((tuple(idx + base_idx for idx in face)), group)
                            for face in local_tris)

    # Also extract standalone ConvexPolytopeShape objects (not part of a compound)
    compound_shape_rels = set()
    for comp_rel, comp_cls in compounds:
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

    for shape_rel, shape_cls in standalone:
        shape_abs = data_start + shape_rel
        result = parse_convex_polytope(data, shape_abs)
        if result is None:
            continue
        local_verts, local_tris = result
        base_idx = len(all_verts)
        all_verts.extend(local_verts)
        group = f"Polytope_standalone_{shape_rel:#x}"
        all_tris.extend(((tuple(idx + base_idx for idx in face)), group)
                        for face in local_tris)
    return all_verts, all_tris


# ── main extraction ──────────────────────────────────────────────────────────

def parse_bytes(data: bytes) -> Tuple[List[Vert3], List[Tuple[Face, str]]]:
    """Parse a raw Havok packfile and return (verts, faces).

    verts: list of (x, y, z) float tuples in Havok space.
    faces: list of ((i0, i1, ...), group_name) tuples.
    Raises RuntimeError if the data is not a valid packfile or yields no geometry.
    """
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
            inst_rot: Mat3 = ((r0[0], r0[1], r0[2]),
                              (r1[0], r1[1], r1[2]),
                              (r2[0], r2[1], r2[2]))

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
                    abs(comb_rot[i][j] - (1.0 if i == j else 0.0)) < 1e-6
                    for i in range(3) for j in range(3))
                is_zero_trans = all(abs(c) < 1e-6 for c in comb_trans)

                if not (is_identity_rot and is_zero_trans):
                    body_transforms[child_data_rel] = BodyTransform(
                        position=comb_trans, rotation=comb_rot)

    all_verts: List[Vert3] = []
    all_tris: List[Tuple[Face, str]] = []

    # ── extract compressed mesh shapes ──
    shapes = [(rel, cls) for rel, cls in objects
              if "hknpCompressedMeshShapeData" in cls]

    for shape_idx, (obj_rel, cls_name) in enumerate(shapes):
        obj_abs = data_start + obj_rel
        parse_bytes._large_cache = {}

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

        for si, sec in enumerate(secs):
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
                if not hasattr(parse_bytes, '_large_cache'):
                    parse_bytes._large_cache = {}
                cache_key = (shared_abs, total_shared)
                if cache_key not in parse_bytes._large_cache:
                    parse_bytes._large_cache[cache_key] = decode_large_vertices(
                        data, shared_abs, total_shared, obj_bb_min, obj_bb_max)
                global_large = parse_bytes._large_cache[cache_key]

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

            total_local = len(local_verts)
            total_sh_actual = len(shared_verts)
            idx_limit = total_local + total_sh_actual

            q_buf = quads_abs + first_q * quad_stride

            if idx_fmt == "u16":
                tris = decode_quads_u16(data, q_buf, num_q, idx_limit)
            else:
                tris = decode_quads_u8(data, q_buf, num_q, idx_limit)

            base_idx = len(all_verts)
            combined = local_verts + shared_verts
            if mesh_body is not None:
                transformed: List[Vert3] = []
                for x, y, z in combined:
                    bx = mesh_body.rotation[0][0]*x + mesh_body.rotation[0][1]*y + mesh_body.rotation[0][2]*z + mesh_body.position[0]
                    by = mesh_body.rotation[1][0]*x + mesh_body.rotation[1][1]*y + mesh_body.rotation[1][2]*z + mesh_body.position[1]
                    bz = mesh_body.rotation[2][0]*x + mesh_body.rotation[2][1]*y + mesh_body.rotation[2][2]*z + mesh_body.position[2]
                    transformed.append((bx, by, bz))
                combined = transformed
            all_verts.extend(combined)

            group = f"Mesh{shape_idx}_Section_{si}" if len(shapes) > 1 else f"Section_{si}"
            all_tris.extend((((a + base_idx, b + base_idx, c + base_idx)), group)
                            for a, b, c in tris)

    # ── extract convex polytope shapes ──
    poly_verts, poly_tris = extract_compound_polytopes(
        data, data_start, fixups, gfixups, objects, body_transforms)

    if poly_verts:
        base_idx = len(all_verts)
        all_verts.extend(poly_verts)
        all_tris.extend(((tuple(idx + base_idx for idx in face)), g)
                        for face, g in poly_tris)

    if not all_verts or not all_tris:
        raise RuntimeError("No geometry decoded.")

    return all_verts, all_tris


def extract_bhk_physics_system(in_path: str, out_path: str) -> None:
    data = open(in_path, "rb").read()
    all_verts, all_tris = parse_bytes(data)
    write_obj(out_path, all_verts, all_tris)

def _main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python bhk_autounpack.py <input.bin>")
        return 1
    in_path = sys.argv[1]
    out_path = in_path.rsplit(".", 1)[0] + ".obj" if "." in in_path else in_path + ".obj"
    extract_bhk_physics_system(in_path, out_path)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())