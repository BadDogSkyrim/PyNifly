"""Triangle stripification for bhkCompressedMeshShapeData chunks.

Converts a flat triangle list into triangle strips + leftover flat triangles,
matching the format used by Havok's compressed mesh chunks where strips are
stored as sequences of vertex indices with alternating winding.

A strip of N indices produces N-2 triangles:
  - Even k: (indices[k], indices[k+1], indices[k+2])
  - Odd  k: (indices[k], indices[k+2], indices[k+1])  (flipped winding)
"""

from typing import List, Tuple, Dict, Set
from collections import defaultdict


def _same_winding(a, b, c, orig):
    """Check if triangle (a, b, c) has the same winding as orig = (x, y, z).

    Same winding means (a,b,c) is a cyclic permutation of (x,y,z):
      (x,y,z), (y,z,x), or (z,x,y).
    Different winding is an anti-cyclic permutation:
      (x,z,y), (z,y,x), or (y,x,z).
    """
    x, y, z = orig
    return (a, b, c) in ((x, y, z), (y, z, x), (z, x, y))


def stripify(
    tris: List[Tuple[int, int, int]],
) -> Tuple[List[List[int]], List[Tuple[int, int, int]]]:
    """Convert triangles into triangle strips plus leftover flat triangles.

    Args:
        tris: List of (v0, v1, v2) index triples.

    Returns:
        (strips, leftovers)
        strips: List of strips, each a list of vertex indices.
        leftovers: Triangles that could not be incorporated into strips.
    """
    if not tris:
        return [], []

    # Build edge→triangle adjacency.
    # An edge is a frozenset of two vertex indices.
    edge_tris: Dict[frozenset, List[int]] = defaultdict(list)
    for ti, (a, b, c) in enumerate(tris):
        edge_tris[frozenset((a, b))].append(ti)
        edge_tris[frozenset((b, c))].append(ti)
        edge_tris[frozenset((a, c))].append(ti)

    # Build triangle→neighbor adjacency (triangles sharing an edge)
    neighbors: Dict[int, Set[int]] = defaultdict(set)
    for edge, tri_list in edge_tris.items():
        for i in range(len(tri_list)):
            for j in range(i + 1, len(tri_list)):
                neighbors[tri_list[i]].add(tri_list[j])
                neighbors[tri_list[j]].add(tri_list[i])

    used = set()
    strips = []

    # Greedy strip building: start from triangles with fewest neighbors (edges of mesh)
    order = sorted(range(len(tris)), key=lambda ti: len(neighbors[ti]))

    for start_ti in order:
        if start_ti in used:
            continue

        strip = _build_strip(start_ti, tris, neighbors, edge_tris, used)
        if strip is not None and len(strip) >= 4:
            strips.append(strip)
        elif strip is not None:
            # Strip too short (single triangle) — put it back for leftovers
            used.discard(start_ti)

    # Collect leftover triangles
    leftovers = [tris[ti] for ti in range(len(tris)) if ti not in used]

    return strips, leftovers


def _build_strip(
    start_ti: int,
    tris: List[Tuple[int, int, int]],
    neighbors: Dict[int, Set[int]],
    edge_tris: Dict[frozenset, List[int]],
    used: Set[int],
) -> List[int]:
    """Build a single triangle strip starting from the given triangle.

    Returns a list of vertex indices forming the strip, or None if the
    triangle is already used.
    """
    if start_ti in used:
        return None

    a, b, c = tris[start_ti]
    used.add(start_ti)

    # The strip starts as [a, b, c] matching the original triangle winding.
    # Only extend forward — reverse+extend can create invalid triangles.
    strip = [a, b, c]
    _extend_strip_forward(strip, tris, edge_tris, used)

    return strip


def _extend_strip_forward(
    strip: List[int],
    tris: List[Tuple[int, int, int]],
    edge_tris: Dict[frozenset, List[int]],
    used: Set[int],
):
    """Extend a strip forward by finding adjacent unused triangles.

    Modifies strip in place. The trailing edge of the strip is
    (strip[-2], strip[-1]) for even-length extensions and
    (strip[-1], strip[-2]) for odd. A new triangle sharing that edge
    contributes its third vertex.
    """
    while True:
        n = len(strip)
        # The trailing edge depends on parity of the number of triangles so far.
        # Triangle count = n - 2.
        tri_count = n - 2
        if tri_count % 2 == 0:
            # Even: trailing edge is (strip[-2], strip[-1])
            edge = frozenset((strip[-2], strip[-1]))
        else:
            # Odd: trailing edge is (strip[-1], strip[-2])
            edge = frozenset((strip[-2], strip[-1]))

        # Find an unused triangle sharing this edge
        candidates = edge_tris.get(edge, [])
        next_ti = None
        for ti in candidates:
            if ti not in used:
                next_ti = ti
                break

        if next_ti is None:
            break

        # Find the third vertex of the new triangle (not on the shared edge)
        a, b, c = tris[next_ti]
        edge_verts = set(edge)
        third = None
        for v in (a, b, c):
            if v not in edge_verts:
                third = v
                break

        if third is None:
            # Degenerate triangle (two vertices the same)
            break

        # Check winding: the engine will decode this triangle based on
        # the current tri_count parity. Verify it matches the original.
        strip.append(third)
        n = len(strip)
        tri_count = n - 2
        if (tri_count - 1) % 2 == 0:
            decoded = (strip[-3], strip[-2], strip[-1])
        else:
            decoded = (strip[-3], strip[-1], strip[-2])

        if not _same_winding(decoded[0], decoded[1], decoded[2], tris[next_ti]):
            # Winding mismatch — this triangle would be flipped.
            # Remove it and stop extending.
            strip.pop()
            break

        used.add(next_ti)
