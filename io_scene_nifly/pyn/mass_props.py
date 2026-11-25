"""Mass properties of FO4 (hknp) collision shapes, computed from the shape alone.

What vanilla stores, measured over every dynamic body in Fallout 4 (2026-11-25; see
C:/tmp/fo4_collision/phase4/notes.md):

- The solid is the shape as Havok collides with it, near enough:
  - a convex polytope with its face planes pushed out by the convex radius;
  - a capsule: a cylinder with hemispherical ends;
  - a sphere.
- hknpShapeMassProperties holds the solid at density 1 (mass == volume): its volume,
  its centre of mass, and its inertia's principal moments and axes, packed.
- The inertia is INERTIA_FACTOR (1.5) times the solid's, on every body.
- A body's hknpMotionCinfo follows from that and the body's mass:
  - inverseMass = 1/mass;
  - massFactor = mass/volume;
  - inverseInertiaLocal = 1/(principal moment * mass/volume), w = 1;
  - centerOfMassWorld = body position + body rotation * centre of mass;
  - orientation = body rotation * principal axes.

Everything here is pure Python; Blender's numpy isn't needed.
"""
import math
import struct
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .convex_hull import polytope_faces, face_planes

Vec3 = Tuple[float, float, float]
Mat3 = Tuple[Vec3, Vec3, Vec3]
Quat = Tuple[float, float, float, float]       # (x, y, z, w)

INERTIA_FACTOR = 1.5

IDENTITY3: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


@dataclass
class MassProps:
    """A solid at density 1: volume, centre of mass, and inertia about the centre of
    mass, all in the shape's own space.  The inertia is the solid's; INERTIA_FACTOR is
    applied when it is written."""
    volume: float
    com: Vec3
    inertia: Mat3


# ── small vector helpers ─────────────────────────────────────────────────────

def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _scale(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                          a[0] * b[1] - a[1] * b[0])


def mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return (_dot(m[0], v), _dot(m[1], v), _dot(m[2], v))


def mat_mul(a: Mat3, b: Mat3) -> Mat3:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def transpose(m: Mat3) -> Mat3:
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def _mat_add(a, b):
    return tuple(tuple(a[i][j] + b[i][j] for j in range(3)) for i in range(3))


def _mat_scale(a, s):
    return tuple(tuple(a[i][j] * s for j in range(3)) for i in range(3))


def _point_inertia(d: Vec3, m: float) -> Mat3:
    """Inertia of a point mass m at offset d (the parallel-axis term)."""
    dd = _dot(d, d)
    return tuple(tuple(m * ((dd if i == j else 0.0) - d[i] * d[j]) for j in range(3))
                 for i in range(3))


# ── quaternions ──────────────────────────────────────────────────────────────

def quat_to_matrix(q: Quat) -> Mat3:
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def matrix_to_quat(m) -> Quat:
    """3x3 rotation matrix -> (x, y, z, w), the inverse of quat_to_matrix.

    Uses the largest diagonal term as the pivot so the division is never by a
    near-zero, which is what makes the naive trace formula lose precision on
    180-degree rotations.
    """
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        return ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s,
                (m[1][0] - m[0][1]) / s, 0.25 * s)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        return (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s,
                (m[2][1] - m[1][2]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        return ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s,
                (m[0][2] - m[2][0]) / s)
    s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
    return ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s,
            (m[1][0] - m[0][1]) / s)


def quat_mul(a: Quat, b: Quat) -> Quat:
    """a * b: rotate by b, then by a."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


# ── solids ───────────────────────────────────────────────────────────────────

def solid_mass(pts: Sequence[Vec3], tris: Sequence[Sequence[int]]) -> MassProps:
    """Volume, centre of mass and inertia (density 1) of a closed mesh whose faces
    are wound outward.  Faces may be polygons; they are fanned."""
    vol = 0.0
    c = [0.0, 0.0, 0.0]
    S = [[0.0] * 3 for _ in range(3)]       # integral of x_i x_j over the solid
    for f in tris:
        a = pts[f[0]]
        for k in range(1, len(f) - 1):
            b, cc = pts[f[k]], pts[f[k + 1]]
            d = _dot(a, _cross(b, cc)) / 6.0     # signed volume of (origin, a, b, cc)
            vol += d
            s = _add(_add(a, b), cc)
            for i in range(3):
                c[i] += d * s[i] / 4.0
                for j in range(3):
                    S[i][j] += d / 20.0 * (s[i] * s[j] + a[i] * a[j] + b[i] * b[j]
                                           + cc[i] * cc[j])
    if abs(vol) < 1e-30:
        raise ValueError("the shape has no volume")
    com = (c[0] / vol, c[1] / vol, c[2] / vol)
    C = [[S[i][j] - vol * com[i] * com[j] for j in range(3)] for i in range(3)]
    tr = C[0][0] + C[1][1] + C[2][2]
    inertia = tuple(tuple((tr if i == j else 0.0) - C[i][j] for j in range(3))
                    for i in range(3))
    return MassProps(vol, com, inertia)


def _clip(faces: List[List[Vec3]], plane, eps: float) -> List[List[Vec3]]:
    """A convex polyhedron (outward-wound face loops) cut by plane n.x + d <= 0."""
    n, d = plane[:3], plane[3]
    out, cut = [], []
    for loop in faces:
        dist = [_dot(n, p) + d for p in loop]
        if all(x <= eps for x in dist):
            out.append(loop)
            cut.extend(p for p, x in zip(loop, dist) if x >= -eps)
            continue
        kept = []
        for k in range(len(loop)):
            p, q = loop[k], loop[(k + 1) % len(loop)]
            dp, dq = dist[k], dist[(k + 1) % len(loop)]
            if dp <= eps:
                kept.append(p)
                if dp >= -eps:
                    cut.append(p)
            if (dp < -eps and dq > eps) or (dp > eps and dq < -eps):
                x = _add(p, _scale(_sub(q, p), dp / (dp - dq)))
                kept.append(x)
                cut.append(x)
        if len(kept) >= 3:
            out.append(kept)
    cap = []
    for p in cut:                               # the points on the cutting plane, once
        if all(_dot(_sub(p, c), _sub(p, c)) > eps * eps for c in cap):
            cap.append(p)
    if len(cap) >= 3:
        # Order them counter-clockwise about n, so the cap faces outward.
        c = _scale(tuple(sum(p[i] for p in cap) for i in range(3)), 1.0 / len(cap))
        u = _sub(cap[0], c)
        u = _scale(u, 1.0 / math.sqrt(_dot(u, u)))
        v = _cross(n, u)
        cap.sort(key=lambda p: math.atan2(_dot(_sub(p, c), v), _dot(_sub(p, c), u)))
        out.append(cap)
    return out


def expanded_polytope(verts: Sequence[Vec3], faces: Sequence[Sequence[int]],
                      radius: float) -> List[List[Vec3]]:
    """The polytope whose face planes are the hull's pushed out by radius, as
    outward-wound face loops.

    It is cut out of a box around the hull by each plane in turn, which needs no hull
    building and doesn't mind any number of planes meeting at a corner (pushing planes
    out makes that common: where 4 faces met, there is now a small edge)."""
    planes = face_planes(verts, faces)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    size = max(hi[i] - lo[i] for i in range(3)) + radius
    eps = 1e-9 * size
    # A corner of angle t moves out by radius / sin(t/2), so the box starts well clear.
    margin = 100.0 * size
    lo = [x - margin for x in lo]
    hi = [x + margin for x in hi]
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    poly = [[(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],   # -z
            [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],   # +z
            [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],   # -y
            [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],   # +y
            [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],   # -x
            [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]]   # +x
    for nx, ny, nz, d in planes:
        poly = _clip(poly, (nx, ny, nz, d - radius), eps)
    return poly


def _loops_mass(loops: List[List[Vec3]]) -> MassProps:
    pts, faces = [], []
    for lp in loops:
        faces.append(list(range(len(pts), len(pts) + len(lp))))
        pts.extend(lp)
    return solid_mass(pts, faces)


def polytope_mass(verts: Sequence[Vec3], faces: Optional[Sequence[Sequence[int]]],
                  radius: float, eps: float, planar_eps: float) -> MassProps:
    """Mass properties of a convex polytope as written: the hull polytope_faces makes
    from verts/faces, with its planes pushed out by the convex radius."""
    hverts, hfaces = polytope_faces(verts, faces, eps, planar_eps)
    if radius <= 0.0:
        return solid_mass(hverts, hfaces)
    return _loops_mass(expanded_polytope(hverts, hfaces, radius))


def capsule_mass(a: Vec3, b: Vec3, radius: float) -> MassProps:
    """A cylinder from a to b with hemispherical ends, radius r."""
    axis = _sub(b, a)
    h = math.sqrt(_dot(axis, axis))
    r = radius
    vc = math.pi * r * r * h
    vs = 4.0 / 3.0 * math.pi * r ** 3
    vol = vc + vs
    i_axis = vc * r * r / 2 + vs * 2 * r * r / 5
    i_perp = (vc * (h * h / 12 + r * r / 4)
              + vs * (2 * r * r / 5 + h * h / 4 + 3 * h * r / 8))
    u = _scale(axis, 1.0 / h) if h > 0 else (0.0, 0.0, 1.0)
    inertia = tuple(tuple(i_perp * (1.0 if i == j else 0.0) + (i_axis - i_perp) * u[i] * u[j]
                          for j in range(3)) for i in range(3))
    return MassProps(vol, _scale(_add(a, b), 0.5), inertia)


def sphere_mass(radius: float, center: Vec3 = (0.0, 0.0, 0.0)) -> MassProps:
    vol = 4.0 / 3.0 * math.pi * radius ** 3
    i = vol * 2 * radius * radius / 5
    return MassProps(vol, center, ((i, 0.0, 0.0), (0.0, i, 0.0), (0.0, 0.0, i)))


def mesh_mass(verts: Sequence[Vec3], tris: Sequence[Sequence[int]]) -> MassProps:
    """A triangle mesh: its own volume if it is closed, else its bounding box."""
    try:
        mp = solid_mass(verts, tris)
        if mp.volume > 0:
            return mp
    except ValueError:
        pass
    lo = tuple(min(v[i] for v in verts) for i in range(3))
    hi = tuple(max(v[i] for v in verts) for i in range(3))
    d = [max(hi[i] - lo[i], 1e-6) for i in range(3)]
    vol = d[0] * d[1] * d[2]
    diag = ((d[1] ** 2 + d[2] ** 2), (d[0] ** 2 + d[2] ** 2), (d[0] ** 2 + d[1] ** 2))
    return MassProps(vol, _scale(_add(lo, hi), 0.5),
                     tuple(tuple(vol * diag[i] / 12 if i == j else 0.0 for j in range(3))
                           for i in range(3)))


def transformed(mp: MassProps, rotation: Mat3, translation: Vec3) -> MassProps:
    """mp moved into a parent space: x' = rotation x + translation."""
    return MassProps(mp.volume, _add(mat_vec(rotation, mp.com), translation),
                     mat_mul(mat_mul(rotation, mp.inertia), transpose(rotation)))


def combined(parts: Sequence[MassProps]) -> MassProps:
    """Several solids at density 1, in one space, as one."""
    vol = sum(p.volume for p in parts)
    com = _scale(tuple(sum(p.com[i] * p.volume for p in parts) for i in range(3)), 1 / vol)
    inertia = ((0.0,) * 3,) * 3
    for p in parts:
        inertia = _mat_add(inertia, _mat_add(p.inertia, _point_inertia(_sub(p.com, com),
                                                                       p.volume)))
    return MassProps(vol, com, inertia)


# ── principal axes ───────────────────────────────────────────────────────────

def principal_axes(m: Mat3) -> Tuple[Vec3, Mat3]:
    """Eigenvalues and eigenvectors of a symmetric 3x3 (Jacobi).

    Returns (moments, R): m = R diag(moments) R^T, R's columns the axes, det R = +1.
    A tensor that is already diagonal comes back as it is, with R the identity."""
    a = [list(r) for r in m]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    scale = max(abs(a[i][j]) for i in range(3) for j in range(3)) or 1.0
    for _ in range(50):
        off = abs(a[0][1]) + abs(a[0][2]) + abs(a[1][2])
        if off <= 1e-15 * scale:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(a[p][q]) <= 1e-18 * scale:
                continue
            theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
            t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1))
            c = 1 / math.sqrt(t * t + 1)
            s = t * c
            for k in range(3):          # columns p, q
                akp, akq = a[k][p], a[k][q]
                a[k][p] = c * akp - s * akq
                a[k][q] = s * akp + c * akq
            for k in range(3):          # rows p, q
                apk, aqk = a[p][k], a[q][k]
                a[p][k] = c * apk - s * aqk
                a[q][k] = s * apk + c * aqk
            for k in range(3):
                vkp, vkq = v[k][p], v[k][q]
                v[k][p] = c * vkp - s * vkq
                v[k][q] = s * vkp + c * vkq
    R = tuple(tuple(r) for r in v)
    det = _dot(R[0], _cross(R[1], R[2]))
    if det < 0:                         # a reflection: flip the last axis
        R = tuple((r[0], r[1], -r[2]) for r in R)
    return (a[0][0], a[1][1], a[2][2]), R


# ── Havok encodings ──────────────────────────────────────────────────────────

def pack_vector3(v: Vec3) -> bytes:
    """hkPackedVector3: three int16 mantissas and an int16 holding the high half of
    a float, the shared scale.  Value = mantissa * 65536 * that float, so the scale
    is 2^(E-14) for the largest component's exponent E, which keeps every mantissa
    under 2^15."""
    m = max(abs(x) for x in v)
    if m == 0.0 or not math.isfinite(m):
        return bytes(8)
    e = math.frexp(m)[1] - 1                  # m = 1.x * 2^e
    if e + 97 < 1:
        return bytes(8)                       # too small to hold: zero
    scale = 2.0 ** (e - 14)
    vals = [max(-32767, min(32767, int(round(x / scale)))) for x in v]
    return struct.pack('<3hH', *vals, (e + 97) << 7)


def unpack_vector3(b: bytes, off: int = 0) -> Vec3:
    x, y, z, e = struct.unpack_from('<3hH', b, off)
    scale = struct.unpack('<f', struct.pack('<I', e << 16))[0] * 65536.0
    return (x * scale, y * scale, z * scale)


def pack_unit_quat(q: Quat) -> bytes:
    """hkPackedUnitVector<4>: each component as round(x * 30000) + 0x8000."""
    return struct.pack('<4H', *(max(0, min(0xFFFF, int(round(x * 30000.0)) + 0x8000))
                                for x in q))


def unpack_unit_quat(b: bytes, off: int = 0) -> Quat:
    return tuple((u - 0x8000) / 30000.0 for u in struct.unpack_from('<4H', b, off))


def normalize_quat(q: Quat) -> Quat:
    n = math.sqrt(sum(x * x for x in q))
    return tuple(x / n for x in q)


def havok_principal(mp: MassProps) -> Tuple[Vec3, Quat]:
    """The principal moments as Havok stores them (INERTIA_FACTOR applied) and the
    rotation from principal to shape space."""
    moments, R = principal_axes(mp.inertia)
    return (tuple(INERTIA_FACTOR * max(m, 0.0) for m in moments),
            normalize_quat(matrix_to_quat(R)))


def shape_mass_properties_bytes(mp: MassProps) -> bytes:
    """The 0x30-byte hknpShapeMassProperties object for a shape (density 1)."""
    moments, q = havok_principal(mp)
    return (bytes(16) + pack_vector3(mp.com) + pack_vector3(moments)
            + pack_unit_quat(q) + struct.pack('<2f', mp.volume, mp.volume))


@dataclass
class MotionValues:
    """The mass part of an hknpMotionCinfo."""
    inverse_mass: float
    mass_factor: float
    inverse_inertia: Tuple[float, float, float, float]
    com_world: Vec3
    orientation: Quat


def motion_values(mass: float, mp: Optional[MassProps], position: Vec3,
                  rotation: Quat) -> MotionValues:
    """A body's motion record from its mass, its shape's mass properties, and where
    the body is.  mass 0 is a keyframed body: no inverse mass or inertia, massFactor
    1, centre of mass at the body, oriented as the body."""
    if mass <= 0.0 or mp is None:
        return MotionValues(0.0, 1.0, (0.0, 0.0, 0.0, 0.0), tuple(position),
                            tuple(rotation))
    moments, q_axes = havok_principal(mp)
    k = mass / mp.volume
    inv = tuple(1.0 / (m * k) if m > 0 else 0.0 for m in moments)
    com_w = _add(position, mat_vec(quat_to_matrix(rotation), mp.com))
    return MotionValues(1.0 / mass, k, inv + (1.0,), com_w,
                        normalize_quat(quat_mul(rotation, q_axes)))
