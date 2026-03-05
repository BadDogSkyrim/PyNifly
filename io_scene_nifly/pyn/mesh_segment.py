"""
mesh_segment.py
---------------
Segment a triangle mesh into groups that each satisfy per-section vertex and
triangle limits (default ≤255 each), as required by Havok bhkCompressedMesh
sections and MOPP data.

Public API
----------
    segment_mesh(verts, tris, max_verts=255, max_tris=255) -> List[List[int]]

Each returned sub-list is a list of face indices (indices into *tris*) whose
unique vertex count and triangle count both fit within the requested limits.
Every input face appears in exactly one output group.
"""

from __future__ import annotations
from typing import List, Sequence, Tuple


def segment_mesh(
    verts: Sequence[Tuple[float, float, float]],
    tris: List[Tuple[int, int, int]],
    max_verts: int = 255,
    max_tris: int = 255,
) -> List[List[int]]:
    """Return face-index groups; each satisfies max_verts unique verts and max_tris triangles.

    Args:
        verts:     Sequence of (x, y, z) vertex positions.
        tris:      List of (a, b, c) face index tuples referencing *verts*.
        max_verts: Maximum unique vertices allowed per section (default 255).
        max_tris:  Maximum triangles allowed per section (default 255).

    Returns:
        A list of groups; each group is a sorted list of face indices.
        Every face index 0..len(tris)-1 appears in exactly one group.
    """
    result: List[List[int]] = []

    def _fits(face_indices: List[int]) -> bool:
        if len(face_indices) > max_tris:
            return False
        unique_verts = {v for fi in face_indices for v in tris[fi]}
        return len(unique_verts) <= max_verts

    def _centroid(fi: int) -> Tuple[float, float, float]:
        a, b, c = tris[fi]
        return (
            (verts[a][0] + verts[b][0] + verts[c][0]) / 3.0,
            (verts[a][1] + verts[b][1] + verts[c][1]) / 3.0,
            (verts[a][2] + verts[b][2] + verts[c][2]) / 3.0,
        )

    def _split_spatially(face_indices: List[int]) -> Tuple[List[int], List[int]]:
        centroids = [_centroid(fi) for fi in face_indices]

        # Find bounding box of centroids, pick longest axis.
        xs = [c[0] for c in centroids]
        ys = [c[1] for c in centroids]
        zs = [c[2] for c in centroids]
        ranges = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        axis = ranges.index(max(ranges))

        # Median centroid value along that axis.
        vals = [centroids[i][axis] for i in range(len(face_indices))]
        vals_sorted = sorted(vals)
        median = vals_sorted[len(vals_sorted) // 2]

        left = [face_indices[i] for i, v in enumerate(vals) if v <= median]
        right = [face_indices[i] for i, v in enumerate(vals) if v > median]

        # Degenerate guard: if either half is empty, fall back to count-based split.
        if not left or not right:
            mid = len(face_indices) // 2
            left = face_indices[:mid]
            right = face_indices[mid:]

        return left, right

    def _recurse(face_indices: List[int]) -> None:
        if not face_indices:
            return
        if _fits(face_indices):
            result.append(sorted(face_indices))
            return
        left, right = _split_spatially(face_indices)
        _recurse(left)
        _recurse(right)

    all_faces = list(range(len(tris)))
    _recurse(all_faces)
    return result
