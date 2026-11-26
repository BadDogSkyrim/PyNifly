"""Convex hulls for Havok convex polytopes (FO4 hknpConvexPolytopeShape).

A polytope is a convex hull: vertices, faces (convex polygons wound counter-clockwise
seen from outside) and one plane per face.  Vanilla hulls (2026-11-24 survey of
20,292 polytopes) have:
  - faces merged across coplanar triangles -- a box is 6 quads, not 12 triangles;
  - at most 16 vertices to a face; a bigger polygon is split, the rest of it covered by
    further faces in the same plane;
  - face vertices up to about 0.1 game units off their plane, but every plane pushed
    out so no vertex lies outside it (by more than float noise).

polytope_faces() turns any mesh into such a hull.  If the mesh's own faces already
form a closed convex hull, they are kept (so a vanilla hull round-trips unchanged);
otherwise the hull is rebuilt from the vertices.  Pure Python; inputs are small (a
polytope holds at most 255 vertices).
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]

MAX_FACE_VERTS = 16
MAX_VERTS = 255


# ── vector helpers ───────────────────────────────────────────────────────────

def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                          a[0] * b[1] - a[1] * b[0])
def _len(a): return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def newell_normal(pts: Sequence[Vec3], loop: Sequence[int]) -> Vec3:
    """Unit normal of a polygon by Newell's method (robust for any convex loop)."""
    nx = ny = nz = 0.0
    for k in range(len(loop)):
        a, b = pts[loop[k]], pts[loop[(k + 1) % len(loop)]]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return _unit((nx, ny, nz))


# ── hull from points (incremental) ───────────────────────────────────────────

def _tri_plane(pts, t):
    n = _unit(_cross(_sub(pts[t[1]], pts[t[0]]), _sub(pts[t[2]], pts[t[0]])))
    return n, -_dot(n, pts[t[0]])


def hull_triangles(pts: Sequence[Vec3], eps: float) -> List[Tuple[int, int, int]]:
    """Triangles of the convex hull of pts, wound outward.  Points within eps of the
    hull's surface are left out.  Raises ValueError if the points are (nearly) flat."""
    n = len(pts)
    if n < 4:
        raise ValueError("a convex hull needs at least 4 points")
    # Initial tetrahedron from extreme points.
    i0 = min(range(n), key=lambda i: pts[i])
    i1 = max(range(n), key=lambda i: _len(_sub(pts[i], pts[i0])))
    d01 = _sub(pts[i1], pts[i0])
    if _len(d01) <= eps:
        raise ValueError("the points are all in one place")
    i2 = max(range(n), key=lambda i: _len(_cross(d01, _sub(pts[i], pts[i0]))) / _len(d01))
    nrm = _cross(d01, _sub(pts[i2], pts[i0]))
    if _len(nrm) / _len(d01) <= eps:
        raise ValueError("the points are all on one line")
    nrm = _unit(nrm)
    i3 = max(range(n), key=lambda i: abs(_dot(nrm, _sub(pts[i], pts[i0]))))
    if abs(_dot(nrm, _sub(pts[i3], pts[i0]))) <= eps:
        raise ValueError("the points are all in one plane")
    centre = tuple(sum(pts[i][k] for i in (i0, i1, i2, i3)) / 4 for k in range(3))

    faces: Dict[int, Tuple[Tuple[int, int, int], Vec3, float]] = {}
    next_id = [0]

    def add(t):
        nn, d = _tri_plane(pts, t)
        if _dot(nn, centre) + d > 0:          # wound inward: flip
            t = (t[0], t[2], t[1])
            nn, d = _tri_plane(pts, t)
        faces[next_id[0]] = (t, nn, d)
        next_id[0] += 1

    for t in ((i0, i1, i2), (i0, i1, i3), (i0, i2, i3), (i1, i2, i3)):
        add(t)

    # Add the remaining points, farthest-first, so that the hull settles early and
    # near-surface points are dropped rather than creating slivers.
    rest = [i for i in range(n) if i not in (i0, i1, i2, i3)]
    rest.sort(key=lambda i: -_len(_sub(pts[i], centre)))
    for p in rest:
        # The faces p sees, grown from the one it's farthest above through neighbouring
        # faces, so they're one piece and the hole they leave has one edge loop. Taking
        # every face it sees by a hair can leave disconnected patches where many faces are
        # nearly coplanar (round shapes: the Nuka-World teacups), and no closed hull.
        dist = {fid: _dot(nn, pts[p]) + d for fid, (t, nn, d) in faces.items()}
        seed = max(dist, key=dist.get)
        if dist[seed] <= eps:
            continue
        face_of = {}
        for fid, (t, _nn, _d) in faces.items():
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                face_of[e] = fid
        visible = {seed}
        stack = [seed]
        while stack:
            t = faces[stack.pop()][0]
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                g = face_of.get((b, a))
                if g is not None and g not in visible and dist[g] > eps:
                    visible.add(g)
                    stack.append(g)
        edges = set()
        for fid in visible:
            t = faces[fid][0]
            edges.update(((t[0], t[1]), (t[1], t[2]), (t[2], t[0])))
        horizon = [e for e in edges if (e[1], e[0]) not in edges]
        for fid in visible:
            del faces[fid]
        for a, b in horizon:
            t = (a, b, p)
            nn, d = _tri_plane(pts, t)
            faces[next_id[0]] = (t, nn, d)
            next_id[0] += 1

    tris = [t for t, _, _ in faces.values()]
    if not _closed(tris):
        raise ValueError("could not build a closed hull from these points")
    return tris


def _closed(loops) -> bool:
    """Every directed edge appears once and its reverse appears once."""
    edges = set()
    for lp in loops:
        for k in range(len(lp)):
            e = (lp[k], lp[(k + 1) % len(lp)])
            if e in edges:
                return False
            edges.add(e)
    return all((b, a) in edges for a, b in edges)


# ── merging coplanar faces ───────────────────────────────────────────────────

def _boundary_loop(loops: List[List[int]]) -> Optional[List[int]]:
    """The outer boundary of a set of faces forming a disc, as one loop."""
    edges = set()
    for lp in loops:
        for k in range(len(lp)):
            edges.add((lp[k], lp[(k + 1) % len(lp)]))
    bound = {a: b for a, b in edges if (b, a) not in edges}
    if not bound:
        return None
    start = next(iter(bound))
    loop = [start]
    while True:
        nxt = bound.get(loop[-1])
        if nxt is None:
            return None
        if nxt == start:
            break
        loop.append(nxt)
        if len(loop) > len(bound):
            return None
    return loop if len(loop) == len(bound) else None


def _merge_coplanar(pts, loops, eps) -> List[List[int]]:
    """Grow regions of edge-adjacent faces lying within eps of the seed face's plane,
    and replace each region by its boundary loop.  Largest faces seed first."""
    edge_face = {}
    for fi, lp in enumerate(loops):
        for k in range(len(lp)):
            edge_face[(lp[k], lp[(k + 1) % len(lp)])] = fi

    def area(lp):
        s = (0.0, 0.0, 0.0)
        for k in range(1, len(lp) - 1):
            c = _cross(_sub(pts[lp[k]], pts[lp[0]]), _sub(pts[lp[k + 1]], pts[lp[0]]))
            s = (s[0] + c[0], s[1] + c[1], s[2] + c[2])
        return _len(s)

    order = sorted(range(len(loops)), key=lambda i: -area(loops[i]))
    done = [False] * len(loops)
    out = []
    for seed in order:
        if done[seed]:
            continue
        nrm = newell_normal(pts, loops[seed])
        d = -max(_dot(nrm, pts[i]) for i in loops[seed])
        region = [seed]
        done[seed] = True
        stack = [seed]
        while stack:
            fi = stack.pop()
            lp = loops[fi]
            for k in range(len(lp)):
                fj = edge_face.get((lp[(k + 1) % len(lp)], lp[k]))
                if fj is None or done[fj]:
                    continue
                if all(abs(_dot(nrm, pts[i]) + d) <= eps for i in loops[fj]):
                    done[fj] = True
                    region.append(fj)
                    stack.append(fj)
        if len(region) == 1:
            out.append(list(loops[seed]))
            continue
        loop = _boundary_loop([loops[i] for i in region])
        if loop is None:                       # not a disc: keep the pieces
            out.extend(list(loops[i]) for i in region)
        else:
            out.append(loop)
    return out


def _drop_collinear(pts, loops, eps) -> List[List[int]]:
    """Remove loop vertices lying within eps of the line through their neighbours.
    On a convex hull such a vertex isn't a corner of any face, so it goes from every
    loop it's in."""
    out = []
    for lp in loops:
        changed = True
        lp = list(lp)
        while changed and len(lp) > 3:
            changed = False
            for k in range(len(lp)):
                a, v, b = pts[lp[k - 1]], pts[lp[k]], pts[lp[(k + 1) % len(lp)]]
                ab = _sub(b, a)
                lab = _len(ab)
                if lab <= eps or _len(_cross(ab, _sub(v, a))) / lab <= eps:
                    del lp[k]
                    changed = True
                    break
        if len(lp) >= 3:
            out.append(lp)
    return out


def _split_big(loops) -> List[List[int]]:
    """Split faces of more than MAX_FACE_VERTS vertices, as vanilla does: keep the
    first 16 as one face and cover the rest of the polygon with more faces."""
    out = []
    for lp in loops:
        lp = list(lp)
        while len(lp) > MAX_FACE_VERTS:
            out.append(lp[:MAX_FACE_VERTS])
            lp = [lp[MAX_FACE_VERTS - 1]] + lp[MAX_FACE_VERTS:] + [lp[0]]
        out.append(lp)
    return out


# ── the mesh's own faces, if they are already a hull ─────────────────────────

def _area_vector(pts, lp) -> Vec3:
    """Twice the polygon's area times its normal (Newell's sums, unnormalised)."""
    nx = ny = nz = 0.0
    for k in range(len(lp)):
        a, b = pts[lp[k]], pts[lp[(k + 1) % len(lp)]]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


def _mesh_is_hull(pts, loops, planar_eps) -> bool:
    """True when the faces are a closed surface whose every face, with its plane
    pushed out to contain all the points, has its own vertices within planar_eps of
    that plane -- i.e. a convex hull, flat to vanilla's tolerance.

    Closed is tested geometrically -- the faces' area vectors sum to zero -- not by
    pairing edges: vanilla hulls have T-junctions where a face over 16 vertices was
    split, and those are closed all the same."""
    if len(loops) < 4 or any(len(lp) < 3 or len(set(lp)) != len(lp) for lp in loops):
        return False
    av = [_area_vector(pts, lp) for lp in loops]
    total = sum(_len(a) for a in av)
    net = _len(tuple(sum(a[k] for a in av) for k in range(3)))
    if total <= 0 or net > 1e-3 * total:
        return False
    for lp in loops:
        nrm = newell_normal(pts, lp)
        if nrm == (0.0, 0.0, 0.0):
            return False
        top = max(_dot(nrm, p) for p in pts)
        if any(top - _dot(nrm, pts[i]) > planar_eps for i in lp):
            return False
    return True


# ── the whole job ────────────────────────────────────────────────────────────

def polytope_faces(verts: Sequence[Vec3], faces: Optional[Sequence[Sequence[int]]],
                   eps: float, planar_eps: float
                   ) -> Tuple[List[Vec3], List[List[int]]]:
    """Turn a mesh into a convex polytope: (vertices, faces).

    verts/faces: the mesh (faces may be None or any polygons).
    eps:         distance under which points count as coplanar/collinear (merging).
    planar_eps:  how far off its plane a kept mesh face's vertex may be.

    The vertices returned are the input vertices the faces use, in input order.
    Raises ValueError if no hull can be made, or it has more than 255 vertices.
    """
    pts = [tuple(float(c) for c in v) for v in verts]
    loops = [list(f) for f in (faces or [])]
    # Weld exact duplicates so a closed mesh with split vertices still counts as closed.
    first: Dict[Vec3, int] = {}
    remap = [first.setdefault(p, i) for i, p in enumerate(pts)]
    loops = [[remap[i] for i in lp] for lp in loops]
    used = sorted({i for lp in loops for i in lp})
    if loops and _mesh_is_hull([pts[i] for i in used],
                               [[used.index(i) for i in lp] for lp in loops], planar_eps):
        result = loops
    else:
        cand = sorted(set(remap))
        tris = hull_triangles([pts[i] for i in cand], eps)
        result = [[cand[i] for i in t] for t in tris]
    result = _merge_coplanar(pts, result, eps)
    result = _drop_collinear(pts, result, eps)
    result = _split_big(result)
    keep = sorted({i for lp in result for i in lp})
    if len(keep) > MAX_VERTS:
        raise ValueError(f"the hull has {len(keep)} vertices; a polytope holds at most "
                         f"{MAX_VERTS}")
    new_index = {old: k for k, old in enumerate(keep)}
    return [pts[i] for i in keep], [[new_index[i] for i in lp] for lp in result]


def face_planes(verts: Sequence[Vec3], faces: Sequence[Sequence[int]]
                ) -> List[Tuple[float, float, float, float]]:
    """One plane (nx, ny, nz, d) per face, normal outward, pushed out so that every
    vertex lies on or inside it (n.v + d <= 0), as vanilla's are."""
    out = []
    for lp in faces:
        n = newell_normal(verts, lp)
        out.append((n[0], n[1], n[2], -max(_dot(n, v) for v in verts)))
    return out


def min_half_angles(faces: Sequence[Sequence[int]], planes) -> List[int]:
    """Each face's minHalfAngle byte: the smallest angle between its normal and an
    edge-neighbour's, in units of 180/255 degrees, capped at 128 and at least 1.
    Matches vanilla exactly or within 1 for 86% of non-right-angle faces; at right
    angles vanilla is 127 or 128 by float noise (survey 2026-11-24)."""
    edge_faces: Dict[Tuple[int, int], List[int]] = {}
    for fi, lp in enumerate(faces):
        for k in range(len(lp)):
            a, b = lp[k], lp[(k + 1) % len(lp)]
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)
    out = []
    for fi, lp in enumerate(faces):
        best = None
        for k in range(len(lp)):
            a, b = lp[k], lp[(k + 1) % len(lp)]
            for fj in edge_faces[(min(a, b), max(a, b))]:
                if fj != fi:
                    c = max(-1.0, min(1.0, _dot(planes[fi][:3], planes[fj][:3])))
                    ang = math.degrees(math.acos(c))
                    best = ang if best is None else min(best, ang)
        val = 128 if best is None else round(best * 255 / 180)
        out.append(max(1, min(128, val)))
    return out
