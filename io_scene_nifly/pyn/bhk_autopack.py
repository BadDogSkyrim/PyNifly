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

# ── Collision volume helpers (for density computation) ────────────────────────

def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _face_normal(verts, face):
    """Compute outward unit normal for a convex face (CCW winding from outside)."""
    v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
    n = _cross(_sub(v1, v0), _sub(v2, v0))
    length = math.sqrt(_dot(n, n))
    if length < 1e-12:
        return (0, 0, 1)
    return (n[0]/length, n[1]/length, n[2]/length)

def _solve3x3(A, b):
    """Solve 3×3 linear system Ax=b via Cramer's rule. Returns None if singular."""
    a0, a1, a2 = A
    det = (a0[0]*(a1[1]*a2[2]-a1[2]*a2[1])
         - a0[1]*(a1[0]*a2[2]-a1[2]*a2[0])
         + a0[2]*(a1[0]*a2[1]-a1[1]*a2[0]))
    if abs(det) < 1e-15:
        return None
    inv = 1.0 / det
    x = ((b[0]*(a1[1]*a2[2]-a1[2]*a2[1])
        - a0[1]*(b[1]*a2[2]-a1[2]*b[2])
        + a0[2]*(b[1]*a2[1]-a1[1]*b[2])) * inv)
    y = ((a0[0]*(b[1]*a2[2]-a1[2]*b[2])
        - b[0]*(a1[0]*a2[2]-a1[2]*a2[0])
        + a0[2]*(a1[0]*b[2]-b[1]*a2[0])) * inv)
    z = ((a0[0]*(a1[1]*b[2]-b[1]*a2[1])
        - a0[1]*(a1[0]*b[2]-b[1]*a2[0])
        + b[0]*(a1[0]*a2[1]-a1[1]*a2[0])) * inv)
    return (x, y, z)

def _polytope_face_offset_volume(verts: List[Vert3], faces: List[Face],
                                  convex_radius: float) -> float:
    """Compute volume of the face-offset polytope.

    Each face plane is moved outward by convex_radius. The new polytope vertices
    are found by intersecting triples of offset planes. Only vertices inside all
    planes are kept. Volume is computed via the divergence theorem.
    """
    if not verts or not faces or convex_radius <= 0:
        # Without convex_radius, use raw hull volume
        return _raw_hull_volume(verts, faces)

    # Build unique face planes from the input faces.
    # Group coplanar faces by normal direction (dot > 0.999).
    planes = []  # list of (nx, ny, nz, d) where nx*x+ny*y+nz*z <= d
    for face in faces:
        n = _face_normal(verts, face)
        d = _dot(n, verts[face[0]]) + convex_radius  # offset outward
        # Check if this plane is already in the list (coplanar face)
        dup = False
        for pn, pd in [(p[:3], p[3]) for p in planes]:
            if abs(_dot(n, pn) - 1.0) < 0.001 and abs(d - pd) < 1e-6:
                dup = True
                break
        if not dup:
            planes.append((n[0], n[1], n[2], d))

    if len(planes) < 4:
        return _raw_hull_volume(verts, faces)

    # Find vertices by intersecting all triples of planes
    offset_verts = []
    np = len(planes)
    for i in range(np):
        for j in range(i+1, np):
            for k in range(j+1, np):
                A = (planes[i][:3], planes[j][:3], planes[k][:3])
                b = (planes[i][3], planes[j][3], planes[k][3])
                pt = _solve3x3(A, b)
                if pt is None:
                    continue
                # Check that this vertex satisfies all plane inequalities
                inside = True
                for p in planes:
                    if _dot(p[:3], pt) > p[3] + 1e-6:
                        inside = False
                        break
                if inside:
                    offset_verts.append(pt)

    if len(offset_verts) < 4:
        return _raw_hull_volume(verts, faces)

    # Compute volume using signed tetrahedra from origin
    # For a convex hull, use each offset plane's face as a fan.
    # Simpler: compute centroid, then sum signed tet volumes.
    cx = sum(v[0] for v in offset_verts) / len(offset_verts)
    cy = sum(v[1] for v in offset_verts) / len(offset_verts)
    cz = sum(v[2] for v in offset_verts) / len(offset_verts)

    # Build convex hull faces from offset vertices by projecting each plane's
    # vertices into 2D and sorting by angle.
    vol = 0.0
    for p in planes:
        n = p[:3]
        d = p[3]
        # Collect vertices on this plane
        face_verts = []
        for vi, v in enumerate(offset_verts):
            if abs(_dot(n, v) - d) < 1e-5:
                face_verts.append(v)
        if len(face_verts) < 3:
            continue
        # Sort by angle in the plane
        fc = (sum(v[0] for v in face_verts)/len(face_verts),
              sum(v[1] for v in face_verts)/len(face_verts),
              sum(v[2] for v in face_verts)/len(face_verts))
        # Build local 2D frame on the plane
        u = _sub(face_verts[0], fc)
        ulen = math.sqrt(_dot(u, u))
        if ulen < 1e-12:
            continue
        u = (u[0]/ulen, u[1]/ulen, u[2]/ulen)
        w = _cross(n, u)
        angles = []
        for v in face_verts:
            dv = _sub(v, fc)
            angles.append(math.atan2(_dot(dv, w), _dot(dv, u)))
        sorted_verts = [v for _, v in sorted(zip(angles, face_verts))]
        # Fan triangulation from sorted_verts[0]
        for ti in range(1, len(sorted_verts)-1):
            a = sorted_verts[0]
            b = sorted_verts[ti]
            c = sorted_verts[ti+1]
            # Signed volume of tetrahedron (centroid, a, b, c)
            ab = _sub(b, a)
            ac = _sub(c, a)
            ad = _sub((cx, cy, cz), a)
            vol += _dot(_cross(ab, ac), ad) / 6.0

    return abs(vol)


def _raw_hull_volume(verts: List[Vert3], faces: List[Face]) -> float:
    """Compute volume of a convex hull from its vertices and face indices.

    Uses the signed tetrahedron method from the origin.
    """
    vol = 0.0
    for face in faces:
        if len(face) < 3:
            continue
        v0 = verts[face[0]]
        for i in range(1, len(face) - 1):
            v1 = verts[face[i]]
            v2 = verts[face[i+1]]
            vol += _dot(v0, _cross(v1, v2)) / 6.0
    return abs(vol)


def compute_collision_volume(verts: List[Vert3], faces: List[Face],
                              convex_radius: float,
                              shape_type: str,
                              sphere_radius: float = 0.0) -> float:
    """Compute the collision volume for density calculation.

    For polytopes, this is the face-offset polytope volume.
    For spheres, this is 4/3 π r³.
    For compressed meshes, uses expanded AABB.
    """
    if shape_type == 'sphere':
        return (4.0 / 3.0) * math.pi * sphere_radius ** 3

    if shape_type == 'compressed_mesh':
        if not verts:
            return 1.0
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        dx = max(xs) - min(xs) + 2 * convex_radius
        dy = max(ys) - min(ys) + 2 * convex_radius
        dz = max(zs) - min(zs) + 2 * convex_radius
        return dx * dy * dz

    # Polytope
    return _polytope_face_offset_volume(verts, faces, convex_radius)


def compute_density(mass: float, verts: List[Vert3], faces: List[Face],
                    convex_radius: float, shape_type: str,
                    sphere_radius: float = 0.0) -> float:
    """Compute density = mass / collision_volume."""
    if mass <= 0:
        return 0.0
    vol = compute_collision_volume(verts, faces, convex_radius,
                                    shape_type, sphere_radius)
    if vol < 1e-12:
        return 0.0
    return mass / vol


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

# Class entries for sphere shape packfiles.
_SPHERE_CLASS_ENTRIES: List[Tuple[int, str]] = [
    (0x33D42383, 'hkClass'),
    (0xB0EFA719, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0xB857718B, 'hknpPhysicsSystemData'),
    (0x741E9012, 'hknpSphereShape'),
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

# dyn_motion (0x40 bytes) — per-body motion properties for dynamic bodies.
# Fields at known offsets:
#   +0x08: gravityFactor (float32), +0x0C: 1.0 (constant)
#   +0x10: maxLinearVelocity (truncated float16 in upper 2 bytes)
#   +0x14: maxAngularVelocity (truncated float16 in upper 2 bytes)
#   +0x18: linearDamping (truncated float16 in upper 2 bytes)
#   +0x1C: angularDamping (truncated float16 in upper 2 bytes)
#   +0x20-+0x24: solver deactivation params (computed, left as defaults)
_DYN_MOTION = bytes([
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # +0x00: zeros
    0x00,0x00,0x80,0x3F, 0x00,0x00,0x80,0x3F,  # +0x08: gravityFactor=1.0, 1.0
    0x00,0xC0,0xD0,0x42, 0x00,0x90,0xFC,0x41,  # +0x10: maxLinVel=104.375, maxAngVel=31.570
    0x00,0x00,0xCD,0x3D, 0x00,0x00,0x4D,0x3D,  # +0x18: linDamp=0.100, angDamp=0.050
    0x7B,0x14,0x2E,0x3E, 0xD2,0x22,0xFB,0x3E,  # +0x20: solver params (0.170, 0.4905)
    0x0B,0xD7,0x23,0x3B, 0x0B,0xD7,0x23,0x3B,  # +0x28: 0.0025, 0.0025
    0x00,0x00,0x80,0x3F, 0x00,0x00,0x00,0x00,  # +0x30: 1.0, pad
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # +0x38: pad
])
assert len(_DYN_MOTION) == 0x40

# dyn_inertia template (0x40 bytes) — fields that vary are patched at write time.
_DYN_INERTIA_TEMPLATE = bytes([
    0x00,0x00,0x01,0x00,                        # +0x00: flags (0x0000, 0x0100)
    0x00,0x00,0x80,0x3F,                        # +0x04: inv_mass (1.0 = placeholder)
    0x00,0x00,0x80,0x3F,                        # +0x08: density (1.0 = placeholder)
    0xF0,0xFF,0x7F,0x5F,                        # +0x0C: sentinel
    0xF0,0xFF,0x7F,0x5F,                        # +0x10: sentinel
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # +0x14: zeros
    0x00,0x00,0x00,0x00,                        # +0x1C: zeros
    0x00,0x00,0x80,0x3F,                        # +0x20: Ixx (1.0 = placeholder)
    0x00,0x00,0x80,0x3F,                        # +0x24: Iyy (1.0 = placeholder)
    0x00,0x00,0x80,0x3F,                        # +0x28: Izz (1.0 = placeholder)
    0x00,0x00,0x80,0x3F,                        # +0x2C: 1.0 (scale)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # +0x30: position (0,0,0)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # +0x38: pad
])
assert len(_DYN_INERTIA_TEMPLATE) == 0x40


def _build_body_props(physics) -> bytes:
    """Build 0x50 bytes of body_props, encoding friction and restitution.

    Friction and restitution are stored as truncated float16 (upper 16 bits
    of float32) within the body_props material region at +0x10.
    Other physics fields (damping, gravity, velocity) are in BodyCInfo.
    """
    from .bhk_autounpack import trunc_f16_encode
    buf = bytearray(_BODY_PROPS)
    if physics is not None:
        fric_u16 = trunc_f16_encode(physics.friction)
        rest_u16 = trunc_f16_encode(physics.restitution)
        struct.pack_into('<H', buf, 0x12, fric_u16)
        struct.pack_into('<H', buf, 0x14, fric_u16)  # duplicate
        struct.pack_into('<H', buf, 0x16, rest_u16)
    return bytes(buf)


def _build_dyn_motion(physics) -> bytes:
    """Build 0x40 bytes of dyn_motion, patching gravity/damping/velocity fields."""
    buf = bytearray(_DYN_MOTION)
    if physics is not None:
        struct.pack_into('<f', buf, 0x08, physics.gravity_factor)
        struct.pack_into('<f', buf, 0x10, physics.max_linear_velocity)
        struct.pack_into('<f', buf, 0x14, physics.max_angular_velocity)
        struct.pack_into('<f', buf, 0x18, physics.linear_damping)
        struct.pack_into('<f', buf, 0x1c, physics.angular_damping)
    return bytes(buf)


def _build_dyn_inertia(physics) -> bytes:
    """Build 0x40 bytes of dyn_inertia from PhysicsProps."""
    buf = bytearray(_DYN_INERTIA_TEMPLATE)
    if physics is not None and physics.mass != 0:
        inv_mass = 1.0 / physics.mass
        struct.pack_into('<f', buf, 0x04, inv_mass)
        struct.pack_into('<f', buf, 0x08, physics.density)
        struct.pack_into('<f', buf, 0x20, physics.inertia[0])
        struct.pack_into('<f', buf, 0x24, physics.inertia[1])
        struct.pack_into('<f', buf, 0x28, physics.inertia[2])
    return bytes(buf)


def _build_psd_prefix(data: bytearray, fx: '_FixupBuilder', psd_name_off: int,
                      physics=None, num_bodies: int = 1):
    """Write PSD + body_props + [dyn_motion + dyn_inertia] + BodyCInfo + ShapeEntry.

    Returns (body_cinfo_rel, shape_entry_rel) so the caller can add global fixups.
    For multi-body, writes `num_bodies` copies of body_props/BodyCInfo/ShapeEntry.
    """
    is_dyn = physics is not None and physics.is_dynamic

    def rel():
        return len(data)
    def write(b):
        off = len(data)
        data.extend(b)
        return off

    # ── hknpPhysicsSystemData  (0x80 bytes) ──
    psd_rel = rel()
    fx.add_virtual(psd_rel, 0, psd_name_off)

    write(_hkarray(0))                          # +0x00: unused
    arr10_off = write(_hkarray(num_bodies))     # +0x10: body_props
    arr20_off = write(_hkarray(1 if is_dyn else 0))  # +0x20: dyn_motion
    arr30_off = write(_hkarray(1 if is_dyn else 0))  # +0x30: dyn_inertia
    arr40_off = write(_hkarray(num_bodies))     # +0x40: BodyCInfo
    write(_hkarray(0))                          # +0x50: unused
    arr60_off = write(_hkarray(num_bodies))     # +0x60: ShapeEntry
    write(bytes(16))                            # +0x70: pad
    assert rel() == psd_rel + 0x80

    # ── body_props (0x50 × num_bodies) ──
    body_props_rel = rel()
    for _ in range(num_bodies):
        write(_build_body_props(physics))
    fx.add_local(arr10_off, body_props_rel)

    # ── dyn_motion (0x40, dynamic only) ──
    if is_dyn:
        dyn_motion_rel = rel()
        write(_build_dyn_motion(physics))
        fx.add_local(arr20_off, dyn_motion_rel)

    # ── dyn_inertia (0x40, dynamic only) ──
    if is_dyn:
        dyn_inertia_rel = rel()
        write(_build_dyn_inertia(physics))
        fx.add_local(arr30_off, dyn_inertia_rel)

    # ── BodyCInfo (0x60 × num_bodies) ──
    body_cinfo_rel = rel()
    for _ in range(num_bodies):
        write(_BODY_CINFO)
    fx.add_local(arr40_off, body_cinfo_rel)

    # ── ShapeEntry (0x10 × num_bodies) ──
    shape_entry_rel = rel()
    for _ in range(num_bodies):
        write(bytes(16))
    fx.add_local(arr60_off, shape_entry_rel)

    return body_cinfo_rel, shape_entry_rel


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
                         name_offs: Dict[str, int],
                         physics=None) -> Tuple[bytes, '_FixupBuilder']:
    """Build the full __data__ section (object data only, without fixup tables).

    Returns (section_bytes, fixup_builder).
    The fixup_builder is populated with all fixup entries.
    The pointer field bytes within section_bytes are left as zeros;
    fixup tables specify where to patch them at load time.
    """
    fx = _FixupBuilder()
    data = bytearray()

    def rel() -> int:
        return len(data)

    def write(b: bytes) -> int:
        off = rel()
        data.extend(b)
        return off

    # ── PSD prefix: PSD + body_props + [dyn_motion + dyn_inertia] + BodyCInfo + ShapeEntry
    body_cinfo_rel, shape_entry_rel = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'], physics=physics)

    # ── hknpConvexPolytopeShape  (variable rel) ─────────────────────────────
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
                            name_offs: Dict[str, int],
                            physics=None) -> Tuple[bytes, '_FixupBuilder']:
    """Build the full __data__ section for a single-section compressed mesh packfile.

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

    # ── PSD prefix
    body_cinfo_rel, shape_entry_rel = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'], physics=physics)

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
        name_offs: Dict[str, int],
        physics=None) -> Tuple[bytes, '_FixupBuilder']:
    """Build __data__ section for a two-body packfile: CM body + polytope body."""
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

    # ── PSD prefix: PSD + body_props×2 + [dyn arrays] + BodyCInfo×2 + ShapeEntry×2
    body_cinfo_rel, shape_entry_rel = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'],
        physics=physics, num_bodies=2)

    # ── hknpCompressedMeshShape (0xC0 bytes) ─────────────────────────────────
    cm_shape_rel = rel()
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


def _build_classnames_sphere() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section for a sphere shape packfile."""
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in _SPHERE_CLASS_ENTRIES:
        name_offs[name] = len(data) + 5
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

def pack_compressed_mesh(verts: List[Vert3], tris: List[Face],
                         physics=None) -> bytes:
    """Build Havok packfile bytes from a triangle mesh using hknpCompressedMeshShape.

    Vertices are quantized with 11-11-10 bits relative to the mesh bounding box.
    Each triangle (a, b, c) is stored as a degenerate quad [a, b, c, c].

    Args:
        verts: List of (x, y, z) tuples in Havok space.  Maximum 255.
        tris:  List of (a, b, c) triangle index tuples.  Maximum 255.
        physics: Optional PhysicsProps for mass/inertia/material.

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile containing an
        hknpPhysicsSystemData with one body carrying the
        hknpCompressedMeshShape/hknpCompressedMeshShapeData.
    """
    cn_data, name_offs = _build_classnames_cm()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    obj_data, fx = _build_cm_data_section(verts, tris, name_offs, physics=physics)

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


def pack_mixed(cm_shape, poly_shape, physics=None) -> bytes:
    """Build Havok packfile bytes for two bodies: one CM + one convex polytope.

    Args:
        cm_shape:   CollisionShape with shape_type=="compressed_mesh".
        poly_shape: CollisionShape with shape_type=="polytope".
        physics:    Optional PhysicsProps for material/dynamics.

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile with hknpPhysicsSystemData
        containing two bodies (CM body + polytope body).
    """
    cn_data, name_offs = _build_classnames_mixed()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    obj_data, fx = _build_mixed_data_section(
        cm_shape.verts, cm_shape.faces,
        poly_shape.verts, poly_shape.faces,
        name_offs, physics=physics)

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
        name_offs: Dict[str, int],
        physics=None) -> Tuple[bytes, '_FixupBuilder']:
    """Build the full __data__ section for an N-body all-polytope packfile.

    Each element of poly_pairs is a (verts, faces) tuple for one body.
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

    # ── PSD prefix: PSD + body_props×N + [dyn arrays] + BodyCInfo×N + ShapeEntry×N
    body_cinfo_rel, shape_entry_rel = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'],
        physics=physics, num_bodies=N)

    # Compute per-body offsets from the base returned by _build_psd_prefix
    body_cinfo_rels = [body_cinfo_rel + i * 0x60 for i in range(N)]
    shape_entry_rels = [shape_entry_rel + i * 0x10 for i in range(N)]

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


def pack_multi_polytope(poly_shapes, physics=None) -> bytes:
    """Pack N convex polytopes into a single Havok packfile (N-body system).

    Each body in the packfile carries one hknpConvexPolytopeShape.
    Uses the same __classnames__ as a single-polytope packfile.

    Args:
        poly_shapes: list of CollisionShape objects with shape_type='polytope'.
        physics:     Optional PhysicsProps for material/dynamics.
    Returns:
        Raw Havok packfile bytes.
    """
    cn_data, name_offs = _build_classnames()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    poly_pairs = [(s.verts, s.faces) for s in poly_shapes]
    obj_data, fx = _build_multi_poly_data_section(poly_pairs, name_offs,
                                                   physics=physics)

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
      [sphere]                      → pack_sphere (single sphere body)

    Combinations not listed above are not yet implemented and raise
    NotImplementedError rather than silently producing incorrect output.

    Args:
        shapes: List of CollisionShape objects (from bhk_autounpack).
    Returns:
        Raw Havok packfile bytes suitable for bhkPhysicsSystem.data.
    Raises:
        NotImplementedError: for unsupported shape combinations.
    """
    physics = shapes[0].physics if shapes else None

    if len(shapes) == 1:
        s = shapes[0]
        if s.shape_type == "compressed_mesh":
            return pack_compressed_mesh(s.verts, s.faces, physics=physics)
        if s.shape_type == "polytope":
            return pack_convex_polytope(s.verts, s.faces, physics=physics)
        if s.shape_type == "sphere":
            xf = s.transform
            position = xf.position if xf is not None else (0, 0, 0)
            return pack_sphere(s.sphere_radius, position=position, physics=physics)

    cm_list   = [s for s in shapes if s.shape_type == "compressed_mesh"]
    poly_list = [s for s in shapes if s.shape_type == "polytope"]

    if len(cm_list) == 0 and len(poly_list) == len(shapes):
        return pack_multi_polytope(poly_list, physics=physics)

    if len(cm_list) == 1 and len(poly_list) == 1 and len(shapes) == 2:
        return pack_mixed(cm_list[0], poly_list[0], physics=physics)

    types = [s.shape_type for s in shapes]
    raise NotImplementedError(
        f"pack_shapes: unsupported shape combination {types}; "
        f"mixed CM+multi-polytope packing is not yet implemented"
    )


def pack_sphere(radius: float, position=(0, 0, 0), physics=None) -> bytes:
    """Build Havok packfile bytes for a single hknpSphereShape.

    The sphere packfile is simpler than polytope — it has no
    hkRefCountedProperties or hknpShapeMassProperties objects.

    Args:
        radius: Sphere radius in Havok space.
        position: (x, y, z) body center in Havok space.
        physics: Optional PhysicsProps for mass/inertia/material.

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile containing an
        hknpPhysicsSystemData with one body carrying the sphere shape.
    """
    # ── Classnames section ──
    cn_data, name_offs = _build_classnames_sphere()

    # ── Data section ──
    fx = _FixupBuilder()
    data = bytearray()

    def rel() -> int:
        return len(data)

    def write(b: bytes) -> int:
        off = rel()
        data.extend(b)
        return off

    # ── PSD prefix: PSD + body_props + [dyn arrays] + BodyCInfo + ShapeEntry
    body_cinfo_rel, shape_entry_rel = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'], physics=physics)

    # Patch BodyCInfo position (+0x30) with sphere center.
    if position != (0, 0, 0):
        struct.pack_into('<fff', data, body_cinfo_rel + 0x30,
                         position[0], position[1], position[2])

    # ── hknpSphereShape (0x50 bytes) ──
    # Layout from reference (Poolball_Cue.nif):
    #   +0x00: 16 bytes zeros (vtable/parent)
    #   +0x10: flags 0x01000111, radius (float), hash, zeros
    #   +0x20: 16 bytes zeros
    #   +0x30: flags 0x00100004, 12 bytes zeros
    #   +0x40: 12 bytes zeros, float 0.5
    shape_rel = rel()
    sphere_data = bytearray(0x50)
    struct.pack_into('<I', sphere_data, 0x10, 0x01000111)
    struct.pack_into('<f', sphere_data, 0x14, radius)
    struct.pack_into('<I', sphere_data, 0x30, 0x00100004)
    struct.pack_into('<f', sphere_data, 0x4C, 0.5)
    write(bytes(sphere_data))

    fx.add_virtual(shape_rel, 0, name_offs['hknpSphereShape'])
    fx.add_global(body_cinfo_rel + 0x00, 2, shape_rel)
    fx.add_global(shape_entry_rel + 0x00, 2, shape_rel)

    # Align to 16 bytes
    while rel() % 16:
        data.append(0)

    obj_data = bytes(data)

    # ── Fixup tables ──
    local_tbl  = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl   = fx.build_virtual_table()

    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    # ── Compute absolute offsets ──
    cn_start   = 0x100
    cn_end     = cn_start + len(cn_data)
    data_start = cn_end
    cn_name_off = name_offs['hknpPhysicsSystemData']

    local_fix_abs  = data_start + len(obj_data)
    global_fix_abs = local_fix_abs  + len(local_tbl)
    virt_fix_abs   = global_fix_abs + len(global_tbl)
    data_end       = virt_fix_abs   + len(virt_tbl)

    hdr = _file_header(cn_name_off)
    shdr0 = _section_header('__classnames__', cn_start,
                            local_fix=cn_start + len(cn_data),
                            global_fix=cn_start + len(cn_data),
                            virt_fix=cn_start + len(cn_data),
                            exports=cn_start + len(cn_data))
    shdr1 = _section_header('__types__', cn_end,
                            local_fix=cn_end, global_fix=cn_end,
                            virt_fix=cn_end, exports=cn_end)
    shdr2 = _section_header('__data__', data_start,
                            local_fix=local_fix_abs,
                            global_fix=global_fix_abs,
                            virt_fix=virt_fix_abs,
                            exports=data_end)

    return hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section


def pack_convex_polytope(verts: List[Vert3], faces: List[Face],
                         physics=None) -> bytes:
    """Build Havok packfile bytes from a convex polytope mesh.

    Args:
        verts: List of (x, y, z) tuples in Havok space.
        faces: List of face index lists. Each face is a convex polygon
               whose vertices are ordered CCW when viewed from outside.
               All vertex indices reference the verts list.
               Maximum 255 vertices.
        physics: Optional PhysicsProps for mass/inertia/material.

    Returns:
        Raw bytes of a valid hk_2014.1.0 packfile containing an
        hknpPhysicsSystemData with one body carrying the shape.
    """
    # ── Classnames section ──
    cn_data, name_offs = _build_classnames()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    # ── Data section (object bytes only) ──
    obj_data, fx = _build_data_section(verts, faces, name_offs, physics=physics)

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
