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

from .convex_hull import polytope_faces, face_planes, min_half_angles
from . import mass_props as MP
from .nifconstants import HAVOC_SCALE_FACTOR

# ── Type aliases ──────────────────────────────────────────────────────────────
Vert3 = Tuple[float, float, float]
Face  = List[int]

# Hull tolerances, in Havok units.  Points within 1e-4 game units of a plane count as
# on it (merging coplanar faces); a mesh face may be up to 0.1 game units off flat and
# still be kept as one face, as vanilla's are (2026-11-24 survey).
_HULL_EPS = 1e-4 / HAVOC_SCALE_FACTOR
_HULL_PLANAR_EPS = 0.1 / HAVOC_SCALE_FACTOR

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

# Class entries for a single-body compound (one hknpDynamicCompoundShape whose
# instances reference N hknpConvexPolytopeShapes). Same as the polytope set plus
# the compound class. Kept separate so the existing packers' output is unchanged.
_COMPOUND_CLASS_ENTRIES: List[Tuple[int, str]] = [
    (0x33D42383, 'hkClass'),
    (0xB0EFA719, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0xB857718B, 'hknpPhysicsSystemData'),
    (0x4620D11C, 'hknpDynamicCompoundShape'),
    (0x3CE9B3E3, 'hknpConvexPolytopeShape'),
    (0x7C574867, 'hkRefCountedProperties'),
    (0xE9191728, 'hknpShapeMassProperties'),
]


# The capsule's class entry; a packfile lists it only when it holds a capsule.
_CAPSULE_CLASS = (0x60A75F4C, 'hknpCapsuleShape')

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

# hknpPhysicsSystemData array strides (hk2014 SDK byte sizes) and the motionId
# a static body carries.
_MATERIAL_SIZE = 0x50
_MOTION_PROPS_SIZE = 0x40
_MOTION_CINFO_SIZE = 0x70
_REF_OBJ_SIZE = 0x08          # hkArray<Ptr<...>> — one pointer per entry
_MOTION_ID_STATIC = 0x7FFFFFFF

# hknpMotionProperties (0x40 bytes) — a shared preset the motionCinfos index.
# Fields at known offsets:
#   +0x08: gravityFactor (float32), +0x0C: 1.0 (constant)
#   +0x10: maxLinearVelocity (truncated float16 in upper 2 bytes)
#   +0x14: maxAngularVelocity (truncated float16 in upper 2 bytes)
#   +0x18: linearDamping (truncated float16 in upper 2 bytes)
#   +0x1C: angularDamping (truncated float16 in upper 2 bytes)
#   +0x20-+0x30: solver deactivation params
#   +0x34-+0x3F: deactivation settings, the same 12 bytes in all 5,884 vanilla
#                records.  Zeros here leave a body let go in mid-air frozen
#                until something hits it.
_DYN_MOTION = bytes([
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # +0x00: zeros
    0x00,0x00,0x80,0x3F, 0x00,0x00,0x80,0x3F,  # +0x08: gravityFactor=1.0, 1.0
    0x00,0xC0,0xD0,0x42, 0x00,0x90,0xFC,0x41,  # +0x10: maxLinVel=104.375, maxAngVel=31.570
    0x00,0x00,0xCD,0x3D, 0x00,0x00,0x4D,0x3D,  # +0x18: linDamp=0.100, angDamp=0.050
    0x7B,0x14,0x2E,0x3E, 0xD2,0x22,0xFB,0x3E,  # +0x20: solver params (0.170, 0.4905)
    0x0B,0xD7,0x23,0x3B, 0x0B,0xD7,0x23,0x3B,  # +0x28: 0.0025, 0.0025
    0x00,0x00,0x80,0x3F, 0xFF,0x67,0x9B,0x99,  # +0x30: 1.0, deactivation settings
    0x04,0x73,0x75,0x06, 0x73,0x00,0x00,0x00,  # +0x38:  (vanilla's constant)
])
assert len(_DYN_MOTION) == 0x40

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


def _body_physics_list(physics, num_bodies: int) -> List:
    """Normalize the `physics` argument into one entry per body.

    Callers pass either a single PhysicsProps (all bodies alike, which is what
    a Blender-authored collision gives us), a list of them (one per body, from a
    re-pack), or None.
    """
    from .bhk_autounpack import PhysicsProps
    if physics is None:
        return [None] * num_bodies
    if isinstance(physics, PhysicsProps):
        return [physics] * num_bodies
    out = list(physics)
    if len(out) < num_bodies:                     # pad rather than lose bodies
        out += [out[-1] if out else None] * (num_bodies - len(out))
    return out[:num_bodies]


_matrix_to_quat = MP.matrix_to_quat


def _body_pose(xf) -> Tuple[Vert3, Tuple[float, float, float, float]]:
    """A body transform's position and quaternion; None is the identity."""
    if xf is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
    quat = getattr(xf, 'quaternion', None) or _matrix_to_quat(xf.rotation)
    return tuple(xf.position), tuple(quat)


def _is_keyframed(p) -> bool:
    """A body moved by animation, not by physics: vanilla gives it no mass."""
    return bool(getattr(p, 'keyframed', False)) or p.mass <= 0.0


# hknpMotionCinfo +0x0C/+0x10 (maxLinearAccelerationDistancePerStep,
# maxRotationToPreventTunneling): 0x5F7FFFF0 in every vanilla record, dynamic or not.
_MOTION_UNLIMITED = 0x5F7FFFF0


def _build_motion_cinfo(physics, mp: Optional['MP.MassProps'], xf,
                        props_id: int) -> bytes:
    """One hknpMotionCinfo (0x70 bytes), worked out from the body's mass, its
    shape's mass properties (in the shape's space) and the body's pose.  See
    mass_props for what vanilla stores.

      +0x00 motionPropertiesId (u16; 0xFFFF for none), +0x02 enableDeactivation 1
      +0x04 inverseMass, +0x08 massFactor, +0x0C/+0x10 0x5F7FFFF0, then zeros
      +0x20 inverseInertiaLocal, +0x30 centerOfMassWorld, +0x40 orientation
      +0x50/+0x60 linear and angular velocity: at rest
    """
    keyframed = _is_keyframed(physics)
    if mp is None and not keyframed:
        raise ValueError("a dynamic body needs its shape's mass properties")
    pos, quat = _body_pose(xf)
    mv = MP.motion_values(0.0 if keyframed else physics.mass, mp, pos, quat)
    buf = bytearray(_MOTION_CINFO_SIZE)
    struct.pack_into('<HBB', buf, 0x00, props_id, 1, 0)
    struct.pack_into('<2f', buf, 0x04, mv.inverse_mass, mv.mass_factor)
    struct.pack_into('<2I', buf, 0x0C, _MOTION_UNLIMITED, _MOTION_UNLIMITED)
    struct.pack_into('<4f', buf, 0x20, *mv.inverse_inertia)
    struct.pack_into('<3f', buf, 0x30, *mv.com_world)
    struct.pack_into('<4f', buf, 0x40, *mv.orientation)
    return bytes(buf)


def _shape_radius(header: Optional[dict]) -> float:
    r = (header or {}).get('convex_radius')
    return DEFAULT_CONVEX_RADIUS if r is None else r


def _polytope_mass(verts: List[Vert3], faces: List[Face],
                   header: Optional[dict] = None) -> 'MP.MassProps':
    """The mass properties of the polytope _build_convex_polytope_shape writes."""
    return MP.polytope_mass(verts, faces, _shape_radius(header), _HULL_EPS,
                            _HULL_PLANAR_EPS)


def _body_transform_list(transforms, num_bodies: int) -> List:
    """Normalize the body-transform argument into one entry per body."""
    if transforms is None:
        return [None] * num_bodies
    if not isinstance(transforms, (list, tuple)):
        return [transforms] * num_bodies
    out = list(transforms)
    out += [None] * max(0, num_bodies - len(out))
    return out[:num_bodies]


def _build_psd_prefix(data: bytearray, fx: '_FixupBuilder', psd_name_off: int,
                      physics=None, num_bodies: int = 1, body_transforms=None,
                      shape_mass=None, constraints=()):
    """Write PSD + materials + [motionProperties + motionCinfos] + bodyCinfos
    + referencedObjects.

    shape_mass is each body's shape's MassProps (mass_props), in the shape's own
    space; a dynamic body's motion record is worked out from it.

    constraints (Constraint, from bhk_autounpack) get their constraintCinfos
    entries here, after the bodies, as vanilla lays them out; the caller writes
    each one's data object and points the entry at it.

    Returns (body_cinfo_rel, shape_entry_rel, constraint_entry_rel) so the caller
    can add global fixups.

    Every body gets its OWN material, motionId, collision filter and quality:
    a system can mix a static body with a dynamic one, and writing all of them
    as copies of body 0 turns a dynamic body static.  The nif still declares a
    dynamic bhkNPCollisionObject, so the game gets a null body back from
    bhkNPCollisionObject::CreateInstance and writes through it while loading.

    Vanilla invariants this reproduces (measured over 1500 systems):
      materials == numBodies, and body i uses material i
      motionCinfos == the number of dynamic bodies
      dynamic bodies' motionIds are 0..n-1 in body order
      each body moved by physics has its own motionProperties record, its
        motionPropertiesId its place among them; a keyframed body has none
        (0xFFFF) -- 1,533 and 336 motionCinfos (2026-11-25)
    """
    bodies = _body_physics_list(physics, num_bodies)
    xforms = _body_transform_list(body_transforms, num_bodies)
    masses = list(shape_mass) if shape_mass is not None else []
    masses += [None] * (num_bodies - len(masses))
    dyn_idx = [i for i, p in enumerate(bodies) if p is not None and p.is_dynamic]
    n_dyn = len(dyn_idx)
    moving = [i for i in dyn_idx if not _is_keyframed(bodies[i])]
    props_id = {i: k for k, i in enumerate(moving)}
    mp_raw = b''.join(_build_dyn_motion(bodies[i]) for i in moving)
    n_mp = len(moving)

    def rel():
        return len(data)
    def write(b):
        off = len(data)
        data.extend(b)
        return off

    # ── hknpPhysicsSystemData  (0x80 bytes) ──
    psd_rel = rel()
    fx.add_virtual(psd_rel, 0, psd_name_off)

    write(bytes(16))                            # +0x00: hkReferencedObject, zeros
    arr10_off = write(_hkarray(num_bodies))     # +0x10: materials (one per body)
    arr20_off = write(_hkarray(n_mp))           # +0x20: motionProperties
    arr30_off = write(_hkarray(n_dyn))          # +0x30: motionCinfos
    arr40_off = write(_hkarray(num_bodies))     # +0x40: bodyCinfos
    arr50_off = write(_hkarray(len(constraints)))   # +0x50: constraintCinfos
    arr60_off = write(_hkarray(num_bodies))     # +0x60: referencedObjects
    write(bytes(16))                            # +0x70: name
    assert rel() == psd_rel + 0x80

    # ── materials (0x50 × num_bodies) ──
    body_props_rel = rel()
    for p in bodies:
        write(_build_body_props(p))
    fx.add_local(arr10_off, body_props_rel)

    # ── motionProperties (0x40 each) ──
    if n_mp:
        motion_props_rel = write(mp_raw)
        fx.add_local(arr20_off, motion_props_rel)

    # ── motionCinfos (0x70 each, one per dynamic body) ──
    if n_dyn:
        motion_cinfo_rel = rel()
        for i in dyn_idx:
            entry = _build_motion_cinfo(bodies[i], masses[i], xforms[i],
                                        props_id.get(i, 0xFFFF))
            assert len(entry) == _MOTION_CINFO_SIZE, \
                f"motionCinfo must be {_MOTION_CINFO_SIZE} bytes, got {len(entry)}"
            write(entry)
        fx.add_local(arr30_off, motion_cinfo_rel)

    # ── bodyCinfos (0x60 × num_bodies) ──
    # motionId must be this body's slot in the motionCinfos array we just wrote,
    # not whatever the source called it -- we only keep the dynamic ones, so the
    # indices renumber.
    motion_slot = {b: k for k, b in enumerate(dyn_idx)}
    body_cinfo_rel = rel()
    for i, p in enumerate(bodies):
        cinfo = bytearray(_BODY_CINFO)
        struct.pack_into('<I', cinfo, 0x0C,
                         motion_slot.get(i, _MOTION_ID_STATIC))
        cinfo[0x10] = p.quality_id if p is not None else 0xFF
        struct.pack_into('<H', cinfo, 0x12, i)            # materialId == index
        struct.pack_into('<I', cinfo, 0x14,
                         p.collision_filter_info if p is not None else 1)
        # position (+0x30) / orientation (+0x40) PLACE the body.  Several bodies
        # commonly share one local mesh sitting at the origin and are spread out
        # by this alone -- DiamondRichBase01 is five such bodies -- so leaving it
        # at the origin stacks them all in the same spot.  Shapes whose vertices
        # are already in world space carry no transform and stay at the origin.
        xf = xforms[i]
        if xf is not None:
            pos, quat = _body_pose(xf)
            struct.pack_into('<3f', cinfo, 0x30, *pos)
            struct.pack_into('<4f', cinfo, 0x40, *quat)
        write(bytes(cinfo))
    fx.add_local(arr40_off, body_cinfo_rel)

    # ── constraintCinfos (0x18 each): data pointer (patched by the caller),
    #    bodyA, bodyB, 8 zero bytes ──
    constraint_entry_rel = rel()
    for c in constraints:
        write(struct.pack('<QII8x', 0, c.body_a, c.body_b))
    if constraints:
        fx.add_local(arr50_off, constraint_entry_rel)

    # ── referencedObjects (0x08 × num_bodies) ──
    # hkArray<Ptr<hkReferencedObject>> — a POINTER each, so the stride is 8, not
    # the 16 an hkArray element usually is.  Writing 16 put every entry after the
    # first at twice its offset, leaving the engine to read a null shape for
    # bodies 1..n-1 and store through it in bhkNPCollisionObject::CreateInstance.
    # Body 0 sits at offset 0 either way, which is why single-body collisions
    # never showed it.
    shape_entry_rel = rel()
    for _ in range(num_bodies):
        write(bytes(_REF_OBJ_SIZE))
    fx.add_local(arr60_off, shape_entry_rel)

    return body_cinfo_rel, shape_entry_rel, constraint_entry_rel


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



def _write_mass_chain(data: bytearray, fx: '_FixupBuilder', name_offs: Dict[str, int],
                      shape_rel: int, mp: 'MP.MassProps') -> None:
    """A polytope's hkRefCountedProperties (at shape +0x20) and the
    hknpShapeMassProperties it holds, worked out from the shape; each 16-aligned."""
    refprop_rel = len(data)
    data.extend(_REF_COUNTED_PROPS)
    fx.add_virtual(refprop_rel, 0, name_offs['hkRefCountedProperties'])
    fx.add_local(refprop_rel + 0x00, refprop_rel + 0x10)    # its array -> its entry
    fx.add_global(shape_rel + 0x20, 2, refprop_rel)
    while len(data) % 16:
        data.append(0)
    massprop_rel = len(data)
    data.extend(MP.shape_mass_properties_bytes(mp))
    fx.add_global(refprop_rel + 0x10, 2, massprop_rel)      # entry -> mass record
    fx.add_virtual(massprop_rel, 0, name_offs['hknpShapeMassProperties'])
    while len(data) % 16:
        data.append(0)

# hknpShape header fields every shape carries, written from the shape itself
# (CollisionShape.shape_flags / user_data / convex_radius).  A shape that leaves
# one as None gets its class's usual value, from the vanilla survey (2026-11-24):
#   flags:  polytope 0x0143 in 98% -- 0x40 is SUPPORTS_COLLISIONS_WITH_INTERIOR_
#           TRIANGLES, without which a piece sinks into triangle-mesh floors and
#           jitters; compressed mesh 0x0204; sphere 0x0111.
#   radius: 0.01 Havok units on 59% of polytopes.
#   userData: the material (fo4_havok_materials).  A new polytope is Metal, the
#           most common; a compressed mesh keeps the template's value, which works
#           in game (its per-triangle materials live in hknpBSMaterialProperties).
POLYTOPE_FLAGS = 0x0143
CM_FLAGS = 0x0204
SPHERE_FLAGS = 0x0111
DEFAULT_CONVEX_RADIUS = 0.01
CM_USER_DATA = 0x26067D15


def _default_material_id() -> int:
    from .fo4_havok_materials import material_id, DEFAULT_MATERIAL
    return material_id(DEFAULT_MATERIAL)


def shape_header_args(s) -> dict:
    """The header values a CollisionShape gives its packer, as keyword arguments."""
    return dict(shape_flags=getattr(s, 'shape_flags', None),
                user_data=getattr(s, 'user_data', None))


def _set_shape_header(buf: bytearray, off: int, flags: int, user_data: int,
                      convex_radius: Optional[float] = None) -> None:
    """Write hknpShape +0x10 flags, +0x14 convexRadius and +0x18 userData."""
    struct.pack_into('<H', buf, off + 0x10, flags)
    if convex_radius is not None:
        struct.pack_into('<f', buf, off + 0x14, convex_radius)
    struct.pack_into('<I', buf, off + 0x18, user_data)


# hknpConvexPolytopeShape header (+0x00 to +0x2F, 0x30 bytes).
# +0x00: vtable ptr (null, patched at runtime)
# +0x08: parent class ptr (null)
# +0x10: flags u16, numShapeKeyBits u8 (0), dispatchType u8 (1 = convex)
# +0x14: convexRadius f32
# +0x18: userData u64 (the material)
# +0x20: hkRefCountedProperties ptr (global fixup), +0x28 zeros
# Flags, radius and userData are written per shape by _build_convex_polytope_shape.
_CONVEX_HDR = bytes([
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # vtable ptr
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # parent class ptr
    0x00,0x00,0x00,0x01,                        # flags (per shape), keybits, dispatch
    0x00,0x00,0x00,0x00,                        # convexRadius (per shape)
    0x00,0x00,0x00,0x00,                        # userData (per shape)
    0x00,0x00,0x00,0x00,                        # userData, high half
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # properties ptr
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  # zeros
])
assert len(_CONVEX_HDR) == 0x30

# hknpCompressedMeshShape header (0xC0 bytes).
#
# Class layout (hk2014 SDK, via Grimrukh/soulstruct-havok):
#   hknpShape          +0x10 flags u16, +0x12 numShapeKeyBits u8,
#                      +0x13 dispatchType u8, +0x14 convexRadius f32,
#                      +0x18 userData u64, +0x20 properties ptr
#   hknpCompositeShape +0x30 edgeWeldingMap (hknpSparseCompactMap, 0x28 bytes:
#                        +0x30 secondaryKeyMask u32, +0x34 secondaryKeyBits u32,
#                        +0x38 primaryKeyToIndex hkArray<u16>,
#                        +0x48 valueAndSecondaryKeys hkArray<u16>)
#                      +0x58 shapeTagCodecInfo u32
#   hknpCompressedMeshShape
#                      +0x60 data ptr, +0x68 quadIsFlat hkBitField,
#                      +0x80 triangleIsInterior hkBitField
#
# Global fixups at +0x20 (→ hkRefCountedProperties) and +0x60 (→ ShapeData)
# patch those pointer fields at load time; they are left as zeros here.
# numShapeKeyBits (+0x12) is per-shape and is patched by _write_cm_shape.
_CM_SHAPE_HDR = bytes([
    # +0x00: vtable ptr (null, runtime-patched)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x08: parent class ptr (null)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x10: flags 0x0204, numShapeKeyBits (patched), dispatchType 0x02
    0x04,0x02,0x00,0x02, 0x00,0x00,0x00,0x00,
    # +0x18: userData
    0x15,0x7d,0x06,0x26, 0x00,0x00,0x00,0x00,
    # +0x20: hkRefCountedProperties ptr (null, global fixup)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x28: zeros
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x30: edgeWeldingMap — secondaryKeyMask 0xFFFFFFFF, secondaryKeyBits 0,
    #        then primaryKeyToIndex (ptr/size at +0x38/+0x40, cap at +0x44)
    0xff,0xff,0xff,0xff, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x40: primaryKeyToIndex size 0, capacityAndFlags = DONT_DEALLOCATE
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x80,
    # +0x48: valueAndSecondaryKeys ptr (null)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x50: valueAndSecondaryKeys size 0, capacityAndFlags = DONT_DEALLOCATE
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x80,
    # +0x58: shapeTagCodecInfo = 0xFFFFFFFF ("none"), 4 pad bytes
    0xff,0xff,0xff,0xff, 0x00,0x00,0x00,0x00,
    # +0x60: ShapeData ptr (null, global fixup)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x68..+0x8F: zeros (5 rows × 8 bytes = 40 bytes)
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    # +0x90: triangleIsInterior numBits (patched) + padding
    0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
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

# A padding plane: (0, 0, 0, -FLT_MAX), as Havok writes it in capsules.  No point is
# ever outside it.  (Vanilla polytopes' padding is junk left in the buffer, mostly
# (0,0,0,0), which every point is *on*; we don't copy that.)
_PAD_PLANE = struct.pack('<3fI', 0.0, 0.0, 0.0, 0xFF7FFFEE)


def _build_convex_polytope_shape(verts: List[Vert3],
                                  faces: List[Face],
                                  convex_radius: Optional[float] = None,
                                  shape_flags: Optional[int] = None,
                                  user_data: Optional[int] = None) -> bytes:
    """Build raw bytes for hknpConvexPolytopeShape, laid out as vanilla's are.

    verts/faces are a mesh; it needn't be a clean hull.  The hull is made from it by
    convex_hull.polytope_faces: the mesh's own faces when they already form a convex
    hull, else the hull of its vertices; either way coplanar faces merged (a box is 6
    quads) and faces over 16 vertices split.

    convex_radius, shape_flags and user_data are the shape's own; None gives the
    usual polytope value (see POLYTOPE_FLAGS).

    Layout, as in every vanilla polytope (2026-11-24 survey; offsets from the shape):
      +0x00: 0x30-byte header (_CONVEX_HDR, with this shape's flags/radius/userData)
      +0x30: vertices  hkRelArray (count, offset from +0x30 = 0x20), 12 zeros
      +0x40: planes    hkRelArray (count, offset from +0x40)
      +0x44: faces     hkRelArray (count, offset from +0x44)
      +0x48: indices   hkRelArray (count, offset from +0x48), 4 zeros
      +0x50: vertices, vec4 with w = 0x3F000000 | index; the count padded to a
             multiple of 4 with copies of the last vertex (its w too)
      then:  planes (nx, ny, nz, d), one per face, the count padded to a multiple
             of 4 with (0, 0, 0, -FLT_MAX) planes that no point is ever outside
      then:  faces: firstIndex u16, numIndices u8, minHalfAngle u8
      then:  face vertex indices (u8), starting on a 16-byte boundary
      padded to 16 bytes.
    """
    hverts, hfaces = polytope_faces(verts, faces, _HULL_EPS, _HULL_PLANAR_EPS)
    planes = face_planes(hverts, hfaces)
    angles = min_half_angles(hfaces, planes)

    nv = len(hverts)
    nf = len(hfaces)
    nv_pad = (nv + 3) // 4 * 4
    np_pad = (nf + 3) // 4 * 4

    fvi: List[int] = []
    face_data = b''
    for face, angle in zip(hfaces, angles):
        face_data += struct.pack('<HBB', len(fvi), len(face), angle)
        fvi.extend(face)

    verts_off = 0x50
    planes_off = verts_off + 16 * nv_pad
    faces_off = planes_off + 16 * np_pad
    fvi_off = _align16(faces_off + 4 * nf)

    buf = bytearray(_align16(fvi_off + len(fvi)))
    buf[0:0x30] = _CONVEX_HDR
    _set_shape_header(
        buf, 0,
        POLYTOPE_FLAGS if shape_flags is None else shape_flags,
        _default_material_id() if user_data is None else user_data,
        DEFAULT_CONVEX_RADIUS if convex_radius is None else convex_radius)
    struct.pack_into('<HH', buf, 0x30, nv_pad, verts_off - 0x30)
    struct.pack_into('<6H', buf, 0x40,
                     np_pad, planes_off - 0x40,
                     nf, faces_off - 0x44,
                     len(fvi), fvi_off - 0x48)
    for i in range(nv_pad):
        k = min(i, nv - 1)
        struct.pack_into('<3fI', buf, verts_off + 16 * i, *hverts[k], 0x3F000000 | k)
    for i in range(np_pad):
        if i < nf:
            struct.pack_into('<4f', buf, planes_off + 16 * i, *planes[i])
        else:
            buf[planes_off + 16 * i:planes_off + 16 * i + 16] = _PAD_PLANE
    buf[faces_off:faces_off + len(face_data)] = face_data
    buf[fvi_off:fvi_off + len(fvi)] = bytes(fvi)
    return bytes(buf)


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


# ── Capsule shape builder ────────────────────────────────────────────────────
#
# An hknpCapsuleShape is a convex polytope -- a thin box around the segment a-b --
# rounded by its convex radius (the capsule's radius), with a and b stored at
# +0x50/+0x60.  Every vanilla capsule (1,006, 2026-11-24 survey) has the same
# layout; only the geometry varies:
#   - 8 box vertices, 6 quad faces, planes padded to 8, minHalfAngle 4 per face;
#   - the box is e = 1% of the radius from the segment on every side, and past
#     each end;
#   - its axes are the segment direction d, p perpendicular to d with one zero
#     component -- (-dz, 0, dx) when |dz| > |dy|, else (-dy, dx, 0) -- and p x d;
#   - even vertices sit past b, odd ones past a, +p for 0,1,4,5 and +q for 4-7.
# That rule reproduces every vanilla box to 0.02% of the radius.
CAPSULE_FLAGS = 0x01C3
_CAPSULE_FACES = ((7, 6, 2, 3), (3, 2, 0, 1), (7, 5, 4, 6),
                  (1, 0, 4, 5), (1, 5, 7, 3), (2, 6, 4, 0))
_CAPSULE_SIZE = 0x1B0
_CAPSULE_PAD_PLANE = _PAD_PLANE


def capsule_from_points(points: List[Vert3]) -> Tuple[Vert3, Vert3, float]:
    """The (a, b, radius) of a capsule-shaped mesh, from its vertices.

    The two tips are the farthest-apart pair of vertices.  Every vertex of the cap
    at a tip T lies on the sphere of radius r centred r inside T along the axis u,
    so with w = v - T, r = |w|^2 / (2 w.u) exactly -- however coarse the mesh, and
    without needing an equator ring.  The cap's vertices are the ones in the half
    nearer T; r is their median.
    """
    n = len(points)
    assert n >= 2, "a capsule mesh needs vertices"
    best = (-1.0, 0, 1)
    for i in range(n):
        pi = points[i]
        for j in range(i + 1, n):
            pj = points[j]
            d2 = sum((pj[k] - pi[k]) ** 2 for k in range(3))
            if d2 > best[0]:
                best = (d2, i, j)
    t1, t2 = points[best[1]], points[best[2]]
    span = math.sqrt(best[0])
    u = [(t2[k] - t1[k]) / span for k in range(3)] if span > 0 else [0.0, 0.0, 1.0]
    rs = []
    for v in points:
        w = [v[k] - t1[k] for k in range(3)]
        along = sum(w[k] * u[k] for k in range(3))
        if 1e-9 * span < along < span / 2:
            rs.append(sum(x * x for x in w) / (2 * along))
    rs.sort()
    r = min(rs[len(rs) // 2], span / 2) if rs else 0.0
    a = tuple(t1[k] + r * u[k] for k in range(3))
    b = tuple(t2[k] - r * u[k] for k in range(3))
    return a, b, r


def capsule_box(a: Vert3, b: Vert3, radius: float) -> List[Vert3]:
    """The 8 vertices of the box Havok keeps inside a capsule (see above)."""
    d = [b[k] - a[k] for k in range(3)]
    length = math.sqrt(sum(x * x for x in d))
    d = [x / length for x in d] if length > 1e-12 else [0.0, 0.0, 1.0]
    p = [-d[2], 0.0, d[0]] if abs(d[2]) > abs(d[1]) + 1e-5 else [-d[1], d[0], 0.0]
    pl = math.sqrt(sum(x * x for x in p))
    p = [x / pl for x in p]
    q = [p[1] * d[2] - p[2] * d[1], p[2] * d[0] - p[0] * d[2], p[0] * d[1] - p[1] * d[0]]
    e = 0.01 * radius
    out = []
    for i in range(8):
        end = ([b[k] + e * d[k] for k in range(3)] if i % 2 == 0
               else [a[k] - e * d[k] for k in range(3)])
        sp = -e if i & 2 else e
        sq = e if i & 4 else -e
        out.append(tuple(end[k] + sp * p[k] + sq * q[k] for k in range(3)))
    return out


def _build_capsule_shape(ends: Tuple[Vert3, Vert3], radius: float,
                         shape_flags: Optional[int] = None,
                         user_data: Optional[int] = None) -> bytes:
    """Build raw bytes for an hknpCapsuleShape (0x1B0 bytes, as vanilla)."""
    a, b = ends
    verts = capsule_box(a, b, radius)
    buf = bytearray(_CAPSULE_SIZE)
    buf[0x13] = 1                                           # dispatchType: convex
    _set_shape_header(buf, 0,
                      CAPSULE_FLAGS if shape_flags is None else shape_flags,
                      _default_material_id() if user_data is None else user_data,
                      radius)
    struct.pack_into('<HH', buf, 0x30, 8, 0x40)            # vertices at +0x70
    # planes at +0xF0, faces at +0x170, indices at +0x190 (offsets from each field)
    struct.pack_into('<6H', buf, 0x40, 8, 0xB0, 6, 0x12C, 24, 0x148)
    struct.pack_into('<4f', buf, 0x50, *a, 1.0)
    struct.pack_into('<4f', buf, 0x60, *b, 1.0)
    for i, v in enumerate(verts):
        struct.pack_into('<3fI', buf, 0x70 + i * 16, *v, 0x3F000000 | i)
    for j, f in enumerate(_CAPSULE_FACES):
        struct.pack_into('<4f', buf, 0xF0 + j * 16, *_face_plane(verts, f))
        struct.pack_into('<HBB', buf, 0x170 + j * 4, 4 * j, 4, 4)
        buf[0x190 + 4 * j:0x194 + 4 * j] = bytes(f)
    buf[0x150:0x160] = buf[0x160:0x170] = _CAPSULE_PAD_PLANE
    return bytes(buf)


# ── Compressed-mesh section splitting ────────────────────────────────────────

# Per-section limits.  Vertices are indexed by single bytes in the quads and
# counted by a u8 (numPackedVertices), so 255 is the ceiling.  Quads are limited
# harder: a tree leaf stores its primitive as `index * 2` in a u8, so the
# highest addressable quad index is 127.  Vanilla agrees — the most quads seen
# in any vanilla section is 126.
_CM_MAX_SECTION_VERTS = 255
_CM_MAX_SECTION_QUADS = 127

# ── hkcdStaticTree node codecs ───────────────────────────────────────────────
#
# Both tree levels quantize a node's AABB against its PARENT's decoded AABB,
# 4 bits per bound per axis, with a square-law curve:
#
#     min = (hi_nibble^2 / 226) * parent_span + parent_min
#     max = parent_max - (lo_nibble^2 / 226) * parent_span
#
# Compression floors the nibbles, so a decoded box always CONTAINS the true box
# — conservative, which is what a collision BVH needs.
_CODEC_CURVE = 226.0


# Two empty hkcdSimdTreeNodes (112 bytes each): an hkcdFourAabb whose six
# 4-wide vectors alternate +FLT_MAX (the lo bounds) and -FLT_MAX (the hi
# bounds), so all four boxes are empty, followed by four zero link words.
_SIMD_TREE_NODE_SIZE = 112
_SIMD_TREE_NODE_COUNT = 2
_SIMD_TREE_EMPTY_NODES = (
    (struct.pack('<4I', *([0x7F7FFFEE] * 4)) +
     struct.pack('<4I', *([0xFF7FFFEE] * 4))) * 3 +
    struct.pack('<4I', 0, 0, 0, 0)
) * _SIMD_TREE_NODE_COUNT


# hknpCompressedMeshShape carries two hkBitFields the engine reads while
# querying the shape.  Leaving them empty crashes getLeafShapes; both must be
# sized against the key space even when every bit is clear:
#
#   +0x68 quadIsFlat          bit per quad slot ((section << 7) | localQuad),
#                             count = ceil(u78/32), u78 at +0x78 = (maxKey+2)//2
#   +0x80 triangleIsInterior  bit per primitive key,
#                             count = ceil(u90/32), u90 at +0x90 = maxKey+1
#
# quadIsFlat marks a quad the engine can test as one flat primitive.  Every
# quad we write is degenerate (a triangle padded to [a,b,c,c]), and vanilla
# clears the bit for all 16448/16448 degenerate quads it ships, so clear is the
# correct value for us.  triangleIsInterior marks a triangle whose edges the
# engine can skip when welding; vanilla leaves it clear ~87% of the time and the
# true rule needs silhouette/dihedral tests we don't attempt, so clear — "treat
# every edge as a boundary" — is both correct-conservative and what vanilla
# writes for an isolated triangle.
#
# These were both filled with ones for a while, which masked a real bug: the
# shape declared numShapeKeyBits = 7 regardless of its actual key width, so the
# engine decoded a bogus quad index and dereferenced a null hkArray<u16> inside
# getLeafShapes.  All-ones hid it because a set bit skips the lookup.  See
# _write_cm_shape.
_QUAD_IS_FLAT_FILL = 0x00000000
_TRI_IS_INTERIOR_FILL = 0x00000000


def _align4(n: int) -> int:
    return (n + 3) & ~3


def _align16(n: int) -> int:
    return (n + 15) & ~15


def _codec_compress_axis(mn: float, mx: float, pmn: float, pmz: float) -> int:
    """Quantize one axis of a child AABB against the parent's extent."""
    span = pmz - pmn
    if span <= 0.0:
        return 0
    snorm = _CODEC_CURVE / span
    lo = math.floor(math.sqrt(max((mn - pmn) * snorm, 0.0)))
    hi = math.floor(math.sqrt(max((mx - pmz) * -snorm, 0.0)))
    return (min(0xF, int(lo)) << 4) | min(0xF, int(hi))


def _codec_decompress_axis(byte: int, pmn: float, pmz: float):
    """Inverse of _codec_compress_axis — the box the engine will actually see."""
    span = pmz - pmn
    lo, hi = byte >> 4, byte & 0xF
    return (lo * lo / _CODEC_CURVE) * span + pmn, pmz - (hi * hi / _CODEC_CURVE) * span


class _BVNode:
    """A node in the temporary (uncompressed) BVH."""
    __slots__ = ('mn', 'mx', 'prim', 'left', 'right')

    def __init__(self, mn, mx, prim=None, left=None, right=None):
        self.mn, self.mx = mn, mx
        self.prim = prim           # leaf: primitive index; internal: None
        self.left, self.right = left, right

    @property
    def is_leaf(self) -> bool:
        return self.prim is not None


def _build_bvh(boxes) -> '_BVNode':
    """Build a binary BVH by median-splitting the longest axis.

    boxes: list of (prim_index, aabb_min, aabb_max).  Every primitive becomes
    exactly one leaf, so a set of N primitives yields 2N-1 nodes.
    """
    def bounds(items):
        mn = tuple(min(b[1][a] for b in items) for a in range(3))
        mx = tuple(max(b[2][a] for b in items) for a in range(3))
        return mn, mx

    def rec(items) -> '_BVNode':
        mn, mx = bounds(items)
        if len(items) == 1:
            return _BVNode(mn, mx, prim=items[0][0])
        axis = max(range(3), key=lambda a: mx[a] - mn[a])
        items.sort(key=lambda b: b[1][axis] + b[2][axis])
        half = len(items) // 2
        return _BVNode(mn, mx, left=rec(items[:half]), right=rec(items[half:]))

    return rec(list(boxes))


def _emit_axis4_tree(root: '_BVNode', dmn, dmx) -> List[bytes]:
    """Compress a BVH into hkcdStaticTree::Codec3Axis4 nodes (4 bytes each).

    data byte: even → leaf, primitive = data >> 1
               odd  → internal, left = i + 1, right = i + (data & 0xFE)
    """
    out: List[List[int]] = []

    def rec(node, pmn, pmz):
        idx = len(out)
        xyz = [_codec_compress_axis(node.mn[a], node.mx[a], pmn[a], pmz[a])
               for a in range(3)]
        out.append([xyz[0], xyz[1], xyz[2], 0])
        # Children quantize against THIS node's decoded box, not its true box.
        dec = [_codec_decompress_axis(xyz[a], pmn[a], pmz[a]) for a in range(3)]
        cmn = tuple(d[0] for d in dec)
        cmx = tuple(d[1] for d in dec)
        if node.is_leaf:
            out[idx][3] = (node.prim * 2) & 0xFF
        else:
            rec(node.left, cmn, cmx)
            offset = len(out) - idx        # always even: left subtree is odd-sized
            assert offset <= 0xFE, f"Codec3Axis4 right-child offset {offset} > 254"
            out[idx][3] = offset | 1
            rec(node.right, cmn, cmx)

    rec(root, dmn, dmx)
    return [bytes(n) for n in out]


def _emit_axis5_tree(root: '_BVNode', dmn, dmx) -> List[bytes]:
    """Compress a BVH into hkcdStaticTree::Codec3Axis5 nodes (5 bytes each).

    hiData bit 7 set → internal, and (hiData<<8|loData) & 0x7FFF is HALF the
    offset to the right child.  Leaves store the primitive index outright.
    The root's bounds are written as zeros (it spans the whole domain).
    """
    out: List[List[int]] = []

    def rec(node, pmn, pmz, is_root=False):
        idx = len(out)
        xyz = [_codec_compress_axis(node.mn[a], node.mx[a], pmn[a], pmz[a])
               for a in range(3)]
        out.append([xyz[0], xyz[1], xyz[2], 0, 0])
        dec = [_codec_decompress_axis(xyz[a], pmn[a], pmz[a]) for a in range(3)]
        cmn = tuple(d[0] for d in dec)
        cmx = tuple(d[1] for d in dec)
        if node.is_leaf:
            data = node.prim
            out[idx][3] = (data >> 8) & 0x7F
            out[idx][4] = data & 0xFF
        else:
            rec(node.left, cmn, cmx)
            data = (len(out) - idx) // 2
            out[idx][3] = ((data >> 8) & 0x7F) | 0x80
            out[idx][4] = data & 0xFF
            rec(node.right, cmn, cmx)
        if is_root:
            out[idx][0] = out[idx][1] = out[idx][2] = 0

    rec(root, dmn, dmx, is_root=True)
    return [bytes(n) for n in out]


def _split_cm_sections(verts: List[Vert3],
                       tris: List[Face]) -> List[Tuple[List[Vert3], List[Face]]]:
    """Partition a triangle mesh into sections that fit the per-section limits.

    Returns a list of (section_verts, section_tris) where every section has at
    most 255 verts and 255 triangles, and section_tris index section_verts.
    Vertices shared between sections are duplicated into each — cheaper than
    the shared-vertex (shidx) indirection vanilla uses, and the decoder treats
    both the same way.

    Triangles are grouped by recursive spatial bisection (split the longest
    axis of the centroid bounds at the median) so each section stays compact,
    which keeps its quantization fine.

    A mesh that already fits in one section is returned unchanged, vertex order
    and triangle order intact, so small collisions pack exactly as before.
    That fast path also keeps vertices no triangle references; the split path
    drops them, since sections are built up from the triangles.  Vanilla pads
    its vertex arrays with unused slots (often at the origin), so dropping them
    tightens the shape's bounds onto its actual geometry.
    """
    if len(verts) <= _CM_MAX_SECTION_VERTS and len(tris) <= _CM_MAX_SECTION_QUADS:
        return [(list(verts), [tuple(int(i) for i in t[:3]) for t in tris])]

    tri_idx = [[int(i) for i in t[:3]] for t in tris]
    centroids = [tuple(sum(verts[i][a] for i in t) / 3.0 for a in range(3))
                 for t in tri_idx]

    groups: List[List[int]] = []

    def bisect(group: List[int]) -> None:
        if (len(group) <= _CM_MAX_SECTION_QUADS
                and len({i for ti in group for i in tri_idx[ti]})
                    <= _CM_MAX_SECTION_VERTS):
            groups.append(group)
            return

        # Split the longest axis of the centroid bounds at the median.
        spans = [(max(centroids[t][a] for t in group)
                  - min(centroids[t][a] for t in group), a) for a in range(3)]
        _, axis = max(spans)
        # A median split always leaves both halves non-empty (a group this big
        # has at least two triangles), so the recursion always terminates —
        # even when every centroid is identical and the sort is a no-op.
        ordered = sorted(group, key=lambda t: centroids[t][axis])
        half = len(ordered) // 2
        bisect(ordered[:half])
        bisect(ordered[half:])

    bisect(list(range(len(tri_idx))))

    sections: List[Tuple[List[Vert3], List[Face]]] = []
    for group in groups:
        assert len(group) <= _CM_MAX_SECTION_QUADS
        sec_verts: List[Vert3] = []
        sec_tris: List[Face] = []
        vmap: Dict[int, int] = {}       # global vert index → index within section
        for ti in group:
            local = []
            for g in tri_idx[ti]:
                if g not in vmap:
                    vmap[g] = len(sec_verts)
                    sec_verts.append(verts[g])
                local.append(vmap[g])
            sec_tris.append(tuple(local))
        assert len(sec_verts) <= _CM_MAX_SECTION_VERTS
        sections.append((sec_verts, sec_tris))
    return sections


def _quantize_section(verts: List[Vert3]):
    """Return (aabb_min, aabb_max, scale, packed) for one section's vertices.

    Vertices are quantized to 11-11-10 bits (qx, qy: 0..2047; qz: 0..1023)
    against the section's own bounding box, so splitting a mesh into sections
    also tightens its quantization.
    """
    mn = tuple(min(v[i] for v in verts) for i in range(3))
    mx = tuple(max(v[i] for v in verts) for i in range(3))
    max_q = (2047, 2047, 1023)
    scale = tuple((mx[i] - mn[i]) / max_q[i] if mx[i] > mn[i] else 1.0
                  for i in range(3))

    packed: List[int] = []
    for v in verts:
        q = [0, 0, 0]
        for i in range(3):
            if mx[i] > mn[i]:
                q[i] = min(max_q[i], max(0, round((v[i] - mn[i]) / scale[i])))
        packed.append(q[0] | (q[1] << 11) | (q[2] << 22))
    return mn, mx, scale, packed


# ── Compressed-mesh shape writer ─────────────────────────────────────────────

def _write_cm_shape(data: bytearray, fx: '_FixupBuilder',
                    name_offs: Dict[str, int],
                    verts: List[Vert3], tris: List[Face],
                    body_cinfo_rel: int, shape_entry_rel: int,
                    header: Optional[dict] = None) -> None:
    """Append one hknpCompressedMeshShape body to a __data__ section.

    Writes the shape header, its hkRefCountedProperties/hknpBSMaterialProperties,
    and an hknpCompressedMeshShapeData split into as many sections as the
    geometry needs.  body_cinfo_rel/shape_entry_rel are THIS body's entries in
    the PSD prefix.
    """
    assert len(verts) > 0 and len(tris) > 0

    def rel() -> int:
        return len(data)

    def write(b: bytes) -> int:
        off = rel()
        data.extend(b)
        return off

    # ── hknpCompressedMeshShape (0xC0 bytes) ───────────────────────────────
    shape_rel = rel()
    write(_CM_SHAPE_HDR)
    assert rel() == shape_rel + 0xC0
    hdr = header or {}
    _set_shape_header(
        data, shape_rel,
        CM_FLAGS if hdr.get('shape_flags') is None else hdr['shape_flags'],
        CM_USER_DATA if hdr.get('user_data') is None else hdr['user_data'])

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
    # The hkArray at +0x10 has a non-zero count and its entries live inside the
    # object at +0x20.  Without this fixup the pointer stays null and the engine
    # dereferences it while loading the packfile.
    fx.add_local(bs_mat_rel + 0x10, bs_mat_rel + 0x20)
    while rel() % 16:
        data.append(0)

    # ── Split into sections and encode each one ────────────────────────────
    sections = _split_cm_sections(verts, tris)
    encoded = [(s_tris,) + _quantize_section(s_verts) for s_verts, s_tris in sections]

    total_quads = sum(len(t) for t, _, _, _, _ in encoded)
    total_verts = sum(len(p) for _, _, _, _, p in encoded)
    n_sec = len(encoded)

    # Whole-shape AABB spans every section.
    dmn = tuple(min(mn[a] for _, mn, _, _, _ in encoded) for a in range(3))
    dmx = tuple(max(mx[a] for _, _, mx, _, _ in encoded) for a in range(3))

    # ── Per-section BVHs (Codec3Axis4) ─────────────────────────────────────
    # The engine walks these at load; leaving them empty is a null-pointer
    # crash inside hkcdStaticMeshTree, not merely a slow query.
    sec_trees: List[List[bytes]] = []
    for s_tris, mn, mx, scale, packed in encoded:
        # Build against the DEQUANTIZED positions — what the engine actually
        # sees.  Using the pre-quantization positions yields node boxes that are
        # a fraction too tight, so a decoded vertex can sit outside its own leaf.
        s_verts = [(mn[0] + (p & 0x7FF) * scale[0],
                    mn[1] + ((p >> 11) & 0x7FF) * scale[1],
                    mn[2] + ((p >> 22) & 0x3FF) * scale[2]) for p in packed]
        boxes = []
        for qi, tri in enumerate(s_tris):
            pts = [s_verts[i] for i in tri]
            boxes.append((qi,
                          tuple(min(p[a] for p in pts) for a in range(3)),
                          tuple(max(p[a] for p in pts) for a in range(3))))
        sec_trees.append(_emit_axis4_tree(_build_bvh(boxes), mn, mx))

    # ── Top-level BVH over the sections (Codec3Axis5) ──────────────────────
    top_tree = _emit_axis5_tree(
        _build_bvh([(i, mn, mx) for i, (_, mn, mx, _, _) in enumerate(encoded)]),
        dmn, dmx)
    # Which top-level node is each section's leaf?  Leaves carry the section
    # index in their data field; internal nodes have bit 15 set.
    leaf_index = {}
    for i, nd in enumerate(top_tree):
        if not (nd[3] & 0x80):
            leaf_index[((nd[3] & 0x7F) << 8) | nd[4]] = i

    # One data run per section covering all its quads, all one material.
    # Run = {u16 value, u8 index, u8 count}.
    n_runs = n_sec

    # A primitive key is (sectionIndex << 8) | (localQuadIndex << 1) | triInQuad
    # — the section index sits ABOVE an 8-bit local field, which is the other
    # reason a section cannot hold more than 127 quads.  The highest key
    # therefore comes from the LAST section's last quad, not from a global quad
    # count; getting this wrong truncates bitsPerKey and the engine then decodes
    # a bogus section index (verified against 2998/3000 vanilla shapes).
    n_keys = total_quads
    last_nq = len(encoded[-1][0]) if encoded else 0
    max_key = (((n_sec - 1) << 8) | ((last_nq - 1) << 1)) if last_nq else 0
    bits_per_key = (max_key + 1).bit_length()

    # ── Lay out the variable-length blocks after the 0xD0 header ───────────
    sd_rel        = rel()
    top_rel       = sd_rel + 0xD0
    sections_rel  = _align16(top_rel + 5 * len(top_tree))
    sectree_rel   = sections_rel + 0x60 * n_sec
    sectree_offs  = []
    off = sectree_rel
    for t in sec_trees:
        sectree_offs.append(off)
        off += 4 * len(t)
    quads_rel     = _align4(off)
    runs_rel      = quads_rel + 4 * total_quads
    verts_rel     = runs_rel + 4 * n_runs
    simd_rel      = _align16(verts_rel + 4 * total_verts)
    # Shape-level bitmaps, sized against OUR key space (not the source mesh's —
    # we section differently, so the key space differs).
    n_quad_slots  = (max_key + 2) // 2
    n_key_slots   = max_key + 1
    words_a       = (n_quad_slots + 31) // 32
    words_b       = (n_key_slots + 31) // 32
    tbl_a_rel     = _align16(simd_rel + _SIMD_TREE_NODE_SIZE * _SIMD_TREE_NODE_COUNT)
    tbl_b_rel     = _align4(tbl_a_rel + 4 * words_a)

    # ── hknpCompressedMeshShapeData / meshTree header (0xD0 bytes) ─────────
    fx.add_virtual(sd_rel, 0, name_offs['hknpCompressedMeshShapeData'])
    fx.add_global(shape_data_ptr_rel, 2, sd_rel)

    sd = bytearray(0xD0)
    struct.pack_into('<QII', sd, 0x00, 0, 0, 0x80000000)   # hkReferencedObject
    struct.pack_into('<QII', sd, 0x10, 0, len(top_tree),
                     len(top_tree) | 0x80000000)           # meshTree nodes (Axis5)
    struct.pack_into('<ffff', sd, 0x20, dmn[0], dmn[1], dmn[2], 0.0)   # domain min
    struct.pack_into('<ffff', sd, 0x30, dmx[0], dmx[1], dmx[2], 0.0)   # domain max
    struct.pack_into('<iiI', sd, 0x40, n_keys, bits_per_key, max_key)
    struct.pack_into('<QII', sd, 0x50, 0, n_sec, n_sec | 0x80000000)   # sections
    struct.pack_into('<QII', sd, 0x60, 0, total_quads,
                     total_quads | 0x80000000)                         # primitives
    struct.pack_into('<QII', sd, 0x70, 0, 0, 0x80000000)               # shidx
    struct.pack_into('<QII', sd, 0x80, 0, total_verts,
                     total_verts | 0x80000000)                         # packedVertices
    struct.pack_into('<QII', sd, 0x90, 0, 0, 0x80000000)               # sharedVertices
    struct.pack_into('<QII', sd, 0xA0, 0, n_runs, n_runs | 0x80000000)  # dataRuns
    # simdTree (+0xB0): an hkArray at +0xB8 holding two empty-AABB nodes.  The
    # count must be matched by real data — vanilla points it at 32 bytes of
    # +/-FLT_MAX sentinels — or the engine dereferences a null pointer.
    struct.pack_into('<II', sd, 0xC0, _SIMD_TREE_NODE_COUNT,
                     _SIMD_TREE_NODE_COUNT | 0x80000000)
    write(bytes(sd))
    assert rel() == sd_rel + 0xD0

    fx.add_local(sd_rel + 0x10, top_rel)
    fx.add_local(sd_rel + 0x50, sections_rel)
    fx.add_local(sd_rel + 0x60, quads_rel)
    fx.add_local(sd_rel + 0x80, verts_rel)
    fx.add_local(sd_rel + 0xA0, runs_rel)
    fx.add_local(sd_rel + 0xB8, simd_rel)

    # ── Top-level tree nodes ───────────────────────────────────────────────
    for nd in top_tree:
        data.extend(nd)
    while rel() < sections_rel:
        data.append(0)

    # ── Section structs (0x60 bytes each) ──────────────────────────────────
    first_vert = 0
    first_quad = 0
    for i, (s_tris, mn, mx, scale, packed) in enumerate(encoded):
        nv, nt = len(packed), len(s_tris)
        assert nv <= _CM_MAX_SECTION_VERTS and nt <= _CM_MAX_SECTION_QUADS

        sec = bytearray(0x60)
        struct.pack_into('<QII', sec, 0x00, 0, len(sec_trees[i]),
                         len(sec_trees[i]) | 0x80000000)          # treeNodes
        fx.add_local(sections_rel + i * 0x60, sectree_offs[i])
        struct.pack_into('<ffff', sec, 0x10, mn[0], mn[1], mn[2], 0.0)  # domain min
        struct.pack_into('<ffff', sec, 0x20, mx[0], mx[1], mx[2], 0.0)  # domain max
        struct.pack_into('<fff',  sec, 0x30, mn[0], mn[1], mn[2])       # codecParms base
        struct.pack_into('<fff',  sec, 0x3C, *scale)                    # codecParms scale
        struct.pack_into('<I',    sec, 0x48, first_vert)                # firstPackedVertex
        # +0x4C packs (firstSharedVertexIndex << 8) | numPackedVertices; with no
        # shared vertices the index is 0, so this is just the count.  Vanilla
        # stores the count here AND at +0x58 — write both.
        struct.pack_into('<I',    sec, 0x4C, nv)                        # sharedVertices
        struct.pack_into('<I',    sec, 0x50, (first_quad << 8) | nt)    # primitives
        struct.pack_into('<I',    sec, 0x54, (i << 8) | 1)              # dataRuns
        sec[0x58] = nv                                                  # numPackedVertices
        sec[0x59] = 0                                                   # numSharedIndices
        struct.pack_into('<H', sec, 0x5A, leaf_index.get(i, 0))         # leafIndex
        sec[0x5C] = 0                                                   # page
        sec[0x5D] = 0                                                   # flags (vanilla: 0)
        write(bytes(sec))

        first_vert += nv
        first_quad += nt
    assert rel() == sectree_rel

    # ── Per-section tree nodes ─────────────────────────────────────────────
    for t in sec_trees:
        for nd in t:
            data.extend(nd)
    while rel() < quads_rel:
        data.append(0)

    # ── Quad data: each triangle (a,b,c) is a degenerate quad [a,b,c,c] ────
    for s_tris, _, _, _, _ in encoded:
        for a, b, c in s_tris:
            data.extend(bytes([a, b, c, c]))
    assert rel() == runs_rel

    # ── Primitive data runs: one per section, covering all of its quads ────
    for s_tris, _, _, _, _ in encoded:
        data.extend(struct.pack('<HBB', 0, 0, len(s_tris)))
    assert rel() == verts_rel

    # ── Packed vertex data ─────────────────────────────────────────────────
    for _, _, _, _, packed in encoded:
        for pv in packed:
            data.extend(struct.pack('<I', pv))
    while rel() < simd_rel:
        data.append(0)

    # ── simdTree nodes ─────────────────────────────────────────────────────
    # Every vanilla compressed mesh — from a single-quad floor to the 123-section
    # Diamond City ground — carries exactly two hkcdSimdTreeNodes, both empty.
    # A node is 112 bytes: an hkcdFourAabb (lx,hx,ly,hy,lz,hz as 4-wide vectors)
    # plus 4 link words.  Empty means min = +FLT_MAX, max = -FLT_MAX, links 0.
    # The count must be backed by the full 224 bytes; short-changing it sends
    # hkcdSimdTree::rayCast off the end of the buffer.
    assert rel() == simd_rel
    data.extend(_SIMD_TREE_EMPTY_NODES)

    # ── quadIsFlat / triangleIsInterior bitfields ──────────────────────────
    # Both are sized against the key space; leaving them empty makes
    # getLeafShapes read through a null pointer once the engine queries us.
    while rel() < tbl_a_rel:
        data.append(0)
    for _ in range(words_a):
        data.extend(struct.pack('<I', _QUAD_IS_FLAT_FILL))
    while rel() < tbl_b_rel:
        data.append(0)
    for _ in range(words_b):
        data.extend(struct.pack('<I', _TRI_IS_INTERIOR_FILL))

    struct.pack_into('<II', data, shape_rel + 0x70, words_a,
                     words_a | 0x80000000)
    struct.pack_into('<I',  data, shape_rel + 0x78, n_quad_slots)
    struct.pack_into('<II', data, shape_rel + 0x88, words_b,
                     words_b | 0x80000000)
    struct.pack_into('<I',  data, shape_rel + 0x90, n_key_slots)
    fx.add_local(shape_rel + 0x68, tbl_a_rel)
    fx.add_local(shape_rel + 0x80, tbl_b_rel)

    # hknpShape::numShapeKeyBits tells the engine how much of a shape key belongs
    # to this shape.  It must equal the data's bitsPerKey (700/700 vanilla shapes)
    # — a fixed value truncates or over-reads the key, the engine resolves a quad
    # that isn't there, and getLeafShapes walks off the end of the shape.
    assert bits_per_key <= 0xFF, f"numShapeKeyBits {bits_per_key} exceeds a byte"
    data[shape_rel + 0x12] = bits_per_key

    while rel() % 16:
        data.append(0)


# ── Compressed-mesh data section builder ─────────────────────────────────────

# ── Classnames section ────────────────────────────────────────────────────────

def _build_classnames_compound() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section for a single-body compound packfile."""
    return _build_classnames_from(_COMPOUND_CLASS_ENTRIES)


def _build_classnames_from(entries) -> Tuple[bytes, Dict[str, int]]:
    """Build a __classnames__ section listing exactly these (hash, name) entries."""
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in entries:
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
                         physics=None, transform=None,
                         header: Optional[dict] = None) -> bytes:
    """One body, an hknpCompressedMeshShape of a triangle mesh (see pack_system)."""
    return pack_system([_one_body('compressed_mesh', verts, tris, physics, transform,
                                  header)])


def pack_multi_cm(cm_shapes, physics=None) -> bytes:
    """N compressed-mesh bodies in one system (see pack_system).  physics is one
    PhysicsProps for all, or one per body; None keeps each shape's own."""
    return pack_system(_with_physics(cm_shapes, physics))


def pack_mixed(cm_shape, poly_shape, physics=None, cm_body: int = 0,
               body_transforms=None) -> bytes:
    """Two bodies, a compressed mesh and a polytope; cm_body is the mesh's slot."""
    shapes = [cm_shape, poly_shape] if cm_body == 0 else [poly_shape, cm_shape]
    shapes = _with_physics(shapes, physics)
    if body_transforms is not None:
        from dataclasses import replace
        shapes = [replace(s, transform=xf) for s, xf in zip(shapes, body_transforms)]
    return pack_system(shapes)


def _with_physics(shapes, physics):
    """shapes with physics applied: one PhysicsProps for all, one per shape, or None
    (each keeps its own)."""
    from dataclasses import replace
    from .bhk_autounpack import PhysicsProps
    if physics is None:
        return list(shapes)
    ps = [physics] * len(shapes) if isinstance(physics, PhysicsProps) else list(physics)
    return [replace(s, physics=p) for s, p in zip(shapes, ps)]


# ── Multi-body polytope data section builder ─────────────────────────────────

# hknpShape::m_userData (uint64 at +0x18). Application data Bethesda sets to a
# per-file value shared by a compound and all its children -- the engine does not
# interpret it. Vanilla differs per file (064003D4 / 2A1A6690 / B26A84C5); the
# existing convex-polytope template (_CONVEX_HDR +0x18) ships 0x7DFA6E05, which
# ships and works in game. We reuse that so the compound and its children agree,
# matching vanilla's invariant that they share one value.
_SHAPE_USER_DATA = 0x7DFA6E05

# hknpDynamicCompoundShape header (0x70 bytes), templated from vanilla
# WorkstationArmorB01. Opaque except: the instance hkArray at +0x60 (ptr via local
# fixup, size/cap patched per pack); m_userData at +0x18 (set below to match the
# children); and +0x10 (0x02060004) an opaque flag that matches both vanilla
# workbenches (the 11-shape cooking stove uses 0x02040004).
_COMPOUND_HEADER = bytearray.fromhex(
    "00000000000000000000000000000000"   # +0x00
    "04000602000000000000000000000000"   # +0x10  (+0x18 = m_userData, patched below)
    "00000000000000000000000000000000"   # +0x20
    "ffffffff000000000000000000000000"   # +0x30
    "00000000000000800000000000000000"   # +0x40  (empty hkArray)
    "0000000000000080ffffffff00000000"   # +0x50  (empty hkArray, +0x58 sentinel)
    "00000000000000000000000000000000"   # +0x60  (instance hkArray, patched)
)
struct.pack_into('<Q', _COMPOUND_HEADER, 0x18, _SHAPE_USER_DATA)
_COMPOUND_HEADER = bytes(_COMPOUND_HEADER)
assert len(_COMPOUND_HEADER) == 0x70


def _build_compound_instance(rotation, translation) -> bytes:
    """One hknpDynamicCompoundShape instance (0x80 bytes).

    rotation is a row-major 3x3; Havok stores it as three column vectors. The
    w-lane of each row and the +0x40 vector are constant metadata the decoder
    ignores (templated from vanilla). The shape pointer at +0x50 is left null for
    a global fixup to patch.
    """
    b = bytearray(0x80)

    def col(j):
        return (rotation[0][j], rotation[1][j], rotation[2][j])

    struct.pack_into('<3f', b, 0x00, *col(0)); struct.pack_into('<f', b, 0x0C, 0.5)
    struct.pack_into('<3f', b, 0x10, *col(1)); struct.pack_into('<f', b, 0x1C, 0.0)
    struct.pack_into('<3f', b, 0x20, *col(2)); struct.pack_into('<f', b, 0x2C, 0.5)
    struct.pack_into('<3f', b, 0x30, *translation); struct.pack_into('<f', b, 0x3C, 0.5)
    struct.pack_into('<4f', b, 0x40, 1.0, 1.0, 1.0, 1.0)
    # +0x50: shape pointer (global fixup patches it)
    struct.pack_into('<I', b, 0x58, 0xFFFFFFFF)
    return bytes(b)


_IDENT3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _build_compound_data_section(
        children, name_offs: Dict[str, int],
        physics=None) -> Tuple[bytes, '_FixupBuilder']:
    """Build the __data__ section for a single-body compound packfile.

    One rigid body whose shape is an hknpDynamicCompoundShape referencing N
    hknpConvexPolytopeShape children, each placed by a per-instance transform.

    children: list of (verts, faces, rotation3x3, translation) tuples. rotation
    and translation are in Havok space; translation already divided by the
    collision scale factor.
    """
    N = len(children)
    assert N >= 1

    fx = _FixupBuilder()
    data = bytearray()

    def rel():
        return len(data)

    def write(b):
        off = len(data)
        data.extend(b)
        return off

    def align16():
        while len(data) % 16:
            data.append(0)

    # Each child's mass, and the body's: the children as placed, together.
    child_mass = [_polytope_mass(verts, faces) for (verts, faces, _r, _t) in children]
    body_mass = MP.combined([MP.transformed(mp, rot or _IDENT3, trans)
                             for mp, (_v, _f, rot, trans) in zip(child_mass, children)])

    # ── PSD prefix: one body (body_props/BodyCInfo/ShapeEntry all size 1) ──
    body_cinfo_rel, shape_entry_rel, _ = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'], physics=physics, num_bodies=1,
        shape_mass=[body_mass])

    # ── hknpDynamicCompoundShape (the single body's shape) ──
    comp_rel = write(_COMPOUND_HEADER)
    fx.add_virtual(comp_rel, 0, name_offs['hknpDynamicCompoundShape'])
    fx.add_global(body_cinfo_rel + 0x00, 2, comp_rel)   # BodyCInfo.shape → compound
    fx.add_global(shape_entry_rel + 0x00, 2, comp_rel)  # ShapeEntry.shape → compound
    struct.pack_into('<I', data, comp_rel + 0x68, N)                 # instance count
    struct.pack_into('<I', data, comp_rel + 0x6C, 0x80000000 | N)    # capacity flags
    # hknpShape::numShapeKeyBits — the same rule as the compressed mesh: enough
    # bits to cover the largest key this shape can hand out, whose maximum is
    # N-1, so N.bit_length().  Verified against 1200/1200 vanilla compounds.
    # A fixed value here lets the engine decode an instance that isn't there.
    data[comp_rel + 0x12] = N.bit_length()
    align16()

    # ── Instance array (N × 0x80) ──
    inst_arr_rel = rel()
    fx.add_local(comp_rel + 0x60, inst_arr_rel)         # compound → instance array
    inst_rels = []
    for (_verts, _faces, rot, trans) in children:
        inst_rels.append(write(_build_compound_instance(rot or _IDENT3, trans)))
    align16()

    # ── Polytope child shapes (one per instance) ──
    for i, (verts, faces, _rot, _trans) in enumerate(children):
        shape_rel = rel()
        write(_build_convex_polytope_shape(verts, faces, user_data=_SHAPE_USER_DATA))
        align16()
        fx.add_virtual(shape_rel, 0, name_offs['hknpConvexPolytopeShape'])
        fx.add_global(inst_rels[i] + 0x50, 2, shape_rel)  # instance → its polytope
        _write_mass_chain(data, fx, name_offs, shape_rel, child_mass[i])

    return bytes(data), fx


def pack_compound(children, physics=None) -> bytes:
    """Pack a single-body compound: one rigid body whose shape is an
    hknpDynamicCompoundShape of N convex-polytope instances.

    children: list of (verts, faces, rotation3x3, translation). This is the
    inverse of the "compound" CollisionShape the decoder produces; it round-trips
    the FO4 armor/weapons workbenches, whose collision is one such compound body.
    """
    if not children:
        raise ValueError("pack_compound requires at least one child shape")

    cn_data, name_offs = _build_classnames_compound()
    cn_name_off = name_offs['hknpPhysicsSystemData']

    obj_data, fx = _build_compound_data_section(children, name_offs, physics=physics)

    local_tbl = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl = fx.build_virtual_table()

    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    cn_start = 0x100
    cn_end = cn_start + len(cn_data)
    data_start = cn_end
    local_fix_abs = data_start + len(obj_data)
    global_fix_abs = local_fix_abs + len(local_tbl)
    virt_fix_abs = global_fix_abs + len(global_tbl)
    data_end = virt_fix_abs + len(virt_tbl)

    hdr = _file_header(cn_name_off)
    shdr0 = _section_header(
        '__classnames__', cn_start,
        local_fix=cn_start + len(cn_data), global_fix=cn_start + len(cn_data),
        virt_fix=cn_start + len(cn_data), exports=cn_start + len(cn_data))
    shdr1 = _section_header(
        '__types__', cn_end,
        local_fix=cn_end, global_fix=cn_end, virt_fix=cn_end, exports=cn_end)
    shdr2 = _section_header(
        '__data__', data_start,
        local_fix=local_fix_abs, global_fix=global_fix_abs,
        virt_fix=virt_fix_abs, exports=data_end)

    return hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section


def pack_multi_polytope(poly_shapes, physics=None) -> bytes:
    """N convex bodies -- polytopes and capsules -- in one system (see pack_system)."""
    return pack_system(_with_physics(poly_shapes, physics))



# ── One physics system: any bodies, and their constraints ──────────────────────

_HINGE_CLASS = (0x51EA603A, 'hkpLimitedHingeConstraintData')

# hkpLimitedHingeConstraintData (0x130), vanilla's constant atoms; the frames, the
# friction torque and the limits are written over it.  Every one of 146 vanilla
# limited hinges has exactly these bytes (2026-11-25; see bhk_autounpack).
_LIMITED_HINGE = bytearray(0x130)
_LIMITED_HINGE[0x20:0x22] = b'\x02\x00'                       # setLocalTransforms
_LIMITED_HINGE[0xB0:0xC0] = bytes.fromhex('17000100eeff7f7feeff7f7ff0ff7f5f')  # stabilization
_LIMITED_HINGE[0xC0:0xC2] = b'\x12\x00'                       # angMotor, off
_LIMITED_HINGE[0xE8:0xF0] = bytes.fromhex('1100010001000000')  # angFriction, 1 axis
_LIMITED_HINGE[0xF8:0xFC] = bytes.fromhex('0e000100')          # angLimit, on
_LIMITED_HINGE[0x104:0x10C] = bytes.fromhex('0000803f0c000000')  # tau 1.0; 2dAng
_LIMITED_HINGE[0x118:0x124] = bytes.fromhex('0500000030000000eeff7f7f')  # ballSocket
_LIMITED_HINGE = bytes(_LIMITED_HINGE)


def _build_limited_hinge(c) -> bytes:
    """One hkpLimitedHingeConstraintData from a Constraint (bhk_autounpack)."""
    buf = bytearray(_LIMITED_HINGE)
    for off, rot, pivot in ((0x30, c.rot_a, c.pivot_a), (0x70, c.rot_b, c.pivot_b)):
        for k in range(3):
            struct.pack_into('<3f', buf, off + 16 * k, rot[0][k], rot[1][k], rot[2][k])
        struct.pack_into('<3f', buf, off + 0x30, *pivot)
    struct.pack_into('<f', buf, 0xF0, c.friction)
    struct.pack_into('<2f', buf, 0xFC, c.min_angle, c.max_angle)
    return bytes(buf)


def _write_sphere_shape(data: bytearray, fx: '_FixupBuilder', name_offs: Dict[str, int],
                        radius: float, header: Optional[dict],
                        body_cinfo_rel: int, shape_entry_rel: int,
                        center: Vert3 = (0.0, 0.0, 0.0)) -> None:
    """Append one hknpSphereShape (0x80 bytes, as all 175 vanilla spheres):
      +0x10 flags 0x01000111, radius, userData
      +0x30 the vertex array: 4 vertices, 0x10 on; +0x40 the vertices, each the
            centre (in the body's space), w = 0.5
    Havok reads all four, so writing fewer (we once wrote one) has it read the next
    object as vertices: a Mr Handy skeleton built that way ignored bullets and hung
    the game when it died."""
    shape_rel = len(data)
    buf = bytearray(0x80)
    struct.pack_into('<I', buf, 0x10, 0x01000000 | SPHERE_FLAGS)
    struct.pack_into('<f', buf, 0x14, radius)
    hdr = header or {}
    if hdr.get('shape_flags') is not None:
        struct.pack_into('<H', buf, 0x10, hdr['shape_flags'])
    if hdr.get('user_data') is not None:
        struct.pack_into('<I', buf, 0x18, hdr['user_data'])
    struct.pack_into('<HH', buf, 0x30, 4, 0x10)
    for k in range(4):
        struct.pack_into('<4f', buf, 0x40 + 16 * k, *center, 0.5)
    data.extend(buf)
    fx.add_virtual(shape_rel, 0, name_offs['hknpSphereShape'])
    fx.add_global(body_cinfo_rel, 2, shape_rel)
    fx.add_global(shape_entry_rel, 2, shape_rel)


def _system_classes(shapes, constraints) -> List[Tuple[int, str]]:
    """The classes a system's packfile lists: the base five, then each body kind's
    in the order the bodies first use them, then the constraints'."""
    per_kind = {
        'polytope': _CLASS_ENTRIES[5:],
        'capsule': [_CAPSULE_CLASS],
        'sphere': [(0x741E9012, 'hknpSphereShape')],
        'compressed_mesh': _CM_CLASS_ENTRIES[5:],
    }
    out = list(_CLASS_ENTRIES[:5])
    for s in shapes:
        for e in per_kind[s.shape_type]:
            if e not in out:
                out.append(e)
    if constraints:
        out.append(_HINGE_CLASS)
    return out


def _shape_header(s) -> dict:
    return dict(shape_header_args(s), convex_radius=s.convex_radius)


def _assemble_packfile(cn_data: bytes, name_offs: Dict[str, int], obj_data: bytes,
                       fx: '_FixupBuilder') -> bytes:
    """File header, the three section headers, classnames, data and its fixups."""
    local_tbl = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl = fx.build_virtual_table()
    cn_start = 0x100
    cn_end = cn_start + len(cn_data)
    data_start = cn_end
    local_fix_abs = data_start + len(obj_data)
    global_fix_abs = local_fix_abs + len(local_tbl)
    virt_fix_abs = global_fix_abs + len(global_tbl)
    data_end = virt_fix_abs + len(virt_tbl)
    hdr = _file_header(name_offs['hknpPhysicsSystemData'])
    shdr0 = _section_header('__classnames__', cn_start, local_fix=cn_end, global_fix=cn_end,
                            virt_fix=cn_end, exports=cn_end)
    shdr1 = _section_header('__types__', cn_end, local_fix=cn_end, global_fix=cn_end,
                            virt_fix=cn_end, exports=cn_end)
    shdr2 = _section_header('__data__', data_start, local_fix=local_fix_abs,
                            global_fix=global_fix_abs, virt_fix=virt_fix_abs,
                            exports=data_end)
    return (hdr + shdr0 + shdr1 + shdr2 + cn_data + obj_data
            + local_tbl + global_tbl + virt_tbl)


def pack_system(shapes, constraints=()) -> bytes:
    """Pack one physics system: every body in shapes, in order, and constraints
    between them.

    shapes are CollisionShapes (bhk_autounpack) of type polytope, capsule, sphere or
    compressed_mesh, each with its own transform (the body's pose) and physics.
    constraints are Constraints whose body_a/body_b index shapes.  Vanilla has one
    system per nif holding every body, joined or not.

    Layout, as vanilla's: the system's arrays (bodies, then constraint entries),
    each body's shape in body order, then the constraints' data objects.
    """
    shapes = list(shapes)
    constraints = list(constraints)
    for s in shapes:
        if s.shape_type not in ('polytope', 'capsule', 'sphere', 'compressed_mesh'):
            raise NotImplementedError(f"pack_system: can't pack a {s.shape_type} body")
    for c in constraints:
        if c.kind != 'limited_hinge':
            raise NotImplementedError(f"pack_system: can't pack a {c.kind} constraint")
        for b in (c.body_a, c.body_b):
            if not 0 <= b < len(shapes):
                raise ValueError(f"constraint joins body {b}; the system has {len(shapes)}")
    cn_data, name_offs = _build_classnames_from(_system_classes(shapes, constraints))

    masses = []
    for s in shapes:
        if s.shape_type == 'polytope':
            masses.append(_polytope_mass(s.verts, s.faces, _shape_header(s)))
        elif s.shape_type == 'capsule':
            masses.append(MP.capsule_mass(*s.capsule_ends, s.convex_radius))
        elif s.shape_type == 'sphere':
            masses.append(MP.sphere_mass(s.sphere_radius, tuple(s.sphere_center)))
        else:
            masses.append(MP.mesh_mass(s.verts, s.faces))

    fx = _FixupBuilder()
    data = bytearray()
    body_cinfo_rel, shape_entry_rel, constraint_rel = _build_psd_prefix(
        data, fx, name_offs['hknpPhysicsSystemData'],
        physics=[s.physics for s in shapes], num_bodies=len(shapes),
        body_transforms=[s.transform for s in shapes], shape_mass=masses,
        constraints=constraints)
    # The pointer array before the shapes is 8 bytes a body: pad to 16 as vanilla does.
    while len(data) % 16:
        data.append(0)

    for i, s in enumerate(shapes):
        bc = body_cinfo_rel + i * 0x60
        se = shape_entry_rel + i * _REF_OBJ_SIZE
        if s.shape_type == 'compressed_mesh':
            _write_cm_shape(data, fx, name_offs, s.verts, s.faces, bc, se,
                            header=shape_header_args(s))
        elif s.shape_type == 'sphere':
            _write_sphere_shape(data, fx, name_offs, s.sphere_radius, shape_header_args(s),
                                bc, se, tuple(s.sphere_center))
        elif s.shape_type == 'capsule':
            shape_rel = len(data)
            data.extend(_build_capsule_shape(s.capsule_ends, s.convex_radius,
                                             s.shape_flags, s.user_data))
            fx.add_virtual(shape_rel, 0, name_offs['hknpCapsuleShape'])
            fx.add_global(bc, 2, shape_rel)
            fx.add_global(se, 2, shape_rel)
        else:
            shape_rel = len(data)
            data.extend(_build_convex_polytope_shape(s.verts, s.faces, **_shape_header(s)))
            fx.add_virtual(shape_rel, 0, name_offs['hknpConvexPolytopeShape'])
            fx.add_global(bc, 2, shape_rel)
            fx.add_global(se, 2, shape_rel)
            while len(data) % 16:
                data.append(0)
            _write_mass_chain(data, fx, name_offs, shape_rel, masses[i])
        while len(data) % 16:
            data.append(0)

    for k, c in enumerate(constraints):
        rel = len(data)
        data.extend(_build_limited_hinge(c))
        fx.add_virtual(rel, 0, name_offs[_HINGE_CLASS[1]])
        fx.add_global(constraint_rel + k * 0x18, 2, rel)

    return _assemble_packfile(cn_data, name_offs, bytes(data), fx)


def _one_body(shape_type, verts, faces, physics, transform, header, **kw):
    from .bhk_autounpack import CollisionShape
    h = header or {}
    return CollisionShape(shape_type=shape_type, name='', transform=transform,
                          verts=list(verts), faces=list(faces),
                          convex_radius=_shape_radius(h) if shape_type == 'polytope' else 0.0,
                          children=[], physics=physics, shape_flags=h.get('shape_flags'),
                          user_data=h.get('user_data'), **kw)

def pack_shapes(shapes, constraints=()) -> bytes:
    """Pack a list of CollisionShape objects -- one per body, in body order, any mix
    of polytope, capsule, sphere and compressed mesh -- into one physics system.
    See pack_system.  A compound body is packed on its own, by pack_compound."""
    return pack_system(shapes, constraints)


def pack_sphere(radius: float, position=(0, 0, 0), physics=None,
                transform=None, header: Optional[dict] = None) -> bytes:
    """One sphere body (see pack_system).  Its centre is the body's position: the
    transform's, or position when there is none."""
    if transform is None:
        from .bhk_autounpack import BodyTransform
        transform = BodyTransform(position=tuple(position), rotation=MP.IDENTITY3,
                                  quaternion=(0.0, 0.0, 0.0, 1.0))
    return pack_system([_one_body('sphere', [], [], physics, transform, header,
                                  sphere_radius=radius)])


def pack_convex_polytope(verts: List[Vert3], faces: List[Face],
                         physics=None, transform=None,
                         header: Optional[dict] = None) -> bytes:
    """One body, an hknpConvexPolytopeShape: the hull of a mesh (see
    _build_convex_polytope_shape and pack_system).  verts are in Havok space."""
    return pack_system([_one_body('polytope', verts, faces, physics, transform, header)])


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
