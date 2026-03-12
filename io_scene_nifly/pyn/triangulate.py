"""Triangulate polygons using minimum-angle ear clipping.

Clips the ear with the smallest interior angle first, producing well-shaped
triangles even for long skinny polygons. Works entirely in 3D — no projection
needed, so non-planar polygons are handled correctly.
"""

import math


def _sub(a, b):
    """Vector subtraction a - b."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    """3D cross product."""
    return (a[1]*b[2] - a[2]*b[1],
            a[2]*b[0] - a[0]*b[2],
            a[0]*b[1] - a[1]*b[0])


def _dot(a, b):
    """3D dot product."""
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _length(v):
    """Vector length."""
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])


def _polygon_normal(coords):
    """Compute polygon normal using Newell's method."""
    n = len(coords)
    nx = ny = nz = 0.0
    for i in range(n):
        cur = coords[i]
        nxt = coords[(i + 1) % n]
        nx += (cur[1] - nxt[1]) * (cur[2] + nxt[2])
        ny += (cur[2] - nxt[2]) * (cur[0] + nxt[0])
        nz += (cur[0] - nxt[0]) * (cur[1] + nxt[1])
    return (nx, ny, nz)


def _angle_at(coords, prev_i, cur_i, nxt_i):
    """Compute the interior angle at vertex cur between edges to prev and nxt."""
    a = _sub(coords[prev_i], coords[cur_i])
    b = _sub(coords[nxt_i], coords[cur_i])
    dot = _dot(a, b)
    cross_len = _length(_cross(a, b))
    return math.atan2(cross_len, dot)


def _is_convex(coords, prev_i, cur_i, nxt_i, normal):
    """Check if vertex cur_i is convex (interior angle < 180) relative to the polygon normal."""
    edge_a = _sub(coords[nxt_i], coords[cur_i])
    edge_b = _sub(coords[prev_i], coords[cur_i])
    return _dot(_cross(edge_a, edge_b), normal) > 0


def _project_onto_plane(p, plane_pt, normal, normal_len_sq):
    """Project point p onto the plane defined by plane_pt and normal."""
    diff = _sub(p, plane_pt)
    dist = _dot(diff, normal) / normal_len_sq
    return (p[0] - dist * normal[0],
            p[1] - dist * normal[1],
            p[2] - dist * normal[2])


def _point_in_triangle_3d(p, a, b, c):
    """Check if point p is inside triangle abc in 3D.

    Projects p onto the triangle's plane along the triangle normal first,
    then uses barycentric coordinates to test containment.
    """
    tri_normal = _cross(_sub(b, a), _sub(c, a))
    n_len_sq = _dot(tri_normal, tri_normal)
    if n_len_sq == 0:
        return False  # degenerate triangle

    pp = _project_onto_plane(p, a, tri_normal, n_len_sq)

    # Barycentric coordinate test
    v0 = _sub(c, a)
    v1 = _sub(b, a)
    v2 = _sub(pp, a)

    dot00 = _dot(v0, v0)
    dot01 = _dot(v0, v1)
    dot02 = _dot(v0, v2)
    dot11 = _dot(v1, v1)
    dot12 = _dot(v1, v2)

    inv_denom = dot00 * dot11 - dot01 * dot01
    if inv_denom == 0:
        return False

    u = (dot11 * dot02 - dot01 * dot12) / inv_denom
    v = (dot00 * dot12 - dot01 * dot02) / inv_denom

    return u >= 0 and v >= 0 and (u + v) <= 1


def _dist_sq(a, b):
    """Squared distance between two 3D points."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx*dx + dy*dy + dz*dz


def _is_convex_quad(coords, a, b, c, d, normal):
    """Check if quad abcd is convex (all interior angles < 180)."""
    return (_is_convex(coords, d, a, b, normal) and
            _is_convex(coords, a, b, c, normal) and
            _is_convex(coords, b, c, d, normal) and
            _is_convex(coords, c, d, a, normal))


def _flip_edges(coords, triangles, normal):
    """Flip interior edges where the alternative diagonal is shorter.

    For each pair of triangles sharing an edge, if the quad they form is convex
    and the other diagonal is shorter, flip to use the shorter diagonal.
    """
    # Build adjacency: map each edge (as sorted pair) to the list of triangle indices
    edge_to_tris = {}
    for ti, (a, b, c) in enumerate(triangles):
        for e in [(a, b), (b, c), (a, c)]:
            key = (min(e), max(e))
            edge_to_tris.setdefault(key, []).append(ti)

    changed = True
    while changed:
        changed = False
        for edge, tri_list in list(edge_to_tris.items()):
            if len(tri_list) != 2:
                continue

            ti0, ti1 = tri_list
            t0 = triangles[ti0]
            t1 = triangles[ti1]

            # Find the shared edge verts and the two opposite verts
            shared = set(t0) & set(t1)
            if len(shared) != 2:
                continue
            s0, s1 = shared
            # opp0 is the vert in t0 not on the shared edge
            opp0 = [v for v in t0 if v not in shared][0]
            # opp1 is the vert in t1 not on the shared edge
            opp1 = [v for v in t1 if v not in shared][0]

            # Current diagonal length vs alternative
            cur_len_sq = _dist_sq(coords[s0], coords[s1])
            alt_len_sq = _dist_sq(coords[opp0], coords[opp1])

            if alt_len_sq >= cur_len_sq:
                continue

            # Check the quad is convex before flipping — order the quad correctly.
            # The quad is: s0, opp0, s1, opp1 but we need consistent winding.
            # Walk t0 to find the order of s0, opp0, s1, then append opp1.
            # t0 has verts (s0, opp0, s1) in some order — find the cyclic order.
            idx_s0 = t0.index(s0)
            idx_opp0 = t0.index(opp0)
            idx_s1 = t0.index(s1)
            # Arrange so we go s0 -> opp0 -> s1 in t0's winding
            if (idx_s0 + 1) % 3 == idx_opp0:
                quad = [s0, opp0, s1, opp1]
            else:
                quad = [s0, opp1, s1, opp0]

            if not _is_convex_quad(coords, *quad, normal):
                continue

            # Flip: replace both triangles, preserving the quad's winding.
            # For CCW quad [q0, q1, q2, q3], diagonal q1-q3 gives
            # (q0, q1, q3) and (q1, q2, q3).
            new_t0 = (quad[0], quad[1], quad[3])
            new_t1 = (quad[1], quad[2], quad[3])
            triangles[ti0] = new_t0
            triangles[ti1] = new_t1

            # Rebuild adjacency: remove old triangle edges, add new ones.
            def _tri_edges(tri):
                return [(min(tri[i], tri[j]), max(tri[i], tri[j]))
                        for i, j in ((0,1), (1,2), (0,2))]

            for key in _tri_edges(t0):
                if key in edge_to_tris and ti0 in edge_to_tris[key]:
                    edge_to_tris[key].remove(ti0)
            for key in _tri_edges(t1):
                if key in edge_to_tris and ti1 in edge_to_tris[key]:
                    edge_to_tris[key].remove(ti1)

            for key in _tri_edges(new_t0):
                edge_to_tris.setdefault(key, []).append(ti0)
            for key in _tri_edges(new_t1):
                edge_to_tris.setdefault(key, []).append(ti1)

            changed = True
            break  # restart after a flip

    return triangles


def _triangulate_quad(coords):
    """Fast path for quads: pick the shorter diagonal."""
    # Diagonal 0-2 vs diagonal 1-3
    d02 = _dist_sq(coords[0], coords[2])
    d13 = _dist_sq(coords[1], coords[3])
    if d02 <= d13:
        return [(0, 1, 2), (0, 2, 3)]
    else:
        return [(0, 1, 3), (1, 2, 3)]


def triangulate(coords):
    """Triangulate a polygon using minimum-angle ear clipping.

    Args:
        coords: Sequence of (x, y, z) vertex coordinates forming the polygon.

    Returns:
        List of (i, j, k) index triples into coords forming triangles.
    """
    n = len(coords)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]
    if n == 4:
        return _triangulate_quad(coords)

    normal = _polygon_normal(coords)

    # Working list of active vertex indices
    indices = list(range(n))
    triangles = []

    while len(indices) > 3:
        best_pos = None
        best_angle = float('inf')
        m = len(indices)

        for pos in range(m):
            prev_i = indices[(pos - 1) % m]
            cur_i = indices[pos]
            nxt_i = indices[(pos + 1) % m]

            if not _is_convex(coords, prev_i, cur_i, nxt_i, normal):
                continue

            # Any other vertex inside this ear triangle?
            is_ear = True
            for j in range(m):
                vi = indices[j]
                if vi == prev_i or vi == cur_i or vi == nxt_i:
                    continue
                if _point_in_triangle_3d(coords[vi], coords[prev_i], coords[cur_i], coords[nxt_i]):
                    is_ear = False
                    break

            if is_ear:
                angle = _angle_at(coords, prev_i, cur_i, nxt_i)
                if angle < best_angle:
                    best_angle = angle
                    best_pos = pos

        if best_pos is None:
            # No ear found — the polygon normal may be flipped (inward-facing
            # face).  Reverse it and retry before falling back to fan.
            normal = (-normal[0], -normal[1], -normal[2])
            for pos in range(m):
                prev_i = indices[(pos - 1) % m]
                cur_i = indices[pos]
                nxt_i = indices[(pos + 1) % m]

                if not _is_convex(coords, prev_i, cur_i, nxt_i, normal):
                    continue

                is_ear = True
                for j in range(m):
                    vi = indices[j]
                    if vi == prev_i or vi == cur_i or vi == nxt_i:
                        continue
                    if _point_in_triangle_3d(coords[vi], coords[prev_i], coords[cur_i], coords[nxt_i]):
                        is_ear = False
                        break

                if is_ear:
                    angle = _angle_at(coords, prev_i, cur_i, nxt_i)
                    if angle < best_angle:
                        best_angle = angle
                        best_pos = pos

        if best_pos is None:
            # Truly degenerate polygon — fall back to fan
            for i in range(1, m - 1):
                triangles.append((indices[0], indices[i], indices[i + 1]))
            break

        prev_i = indices[(best_pos - 1) % m]
        cur_i = indices[best_pos]
        nxt_i = indices[(best_pos + 1) % m]
        triangles.append((prev_i, cur_i, nxt_i))
        indices.pop(best_pos)

    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))

    if len(triangles) > 1:
        _flip_edges(coords, triangles, normal)

    return triangles
