"""MOPP tree verifier — tests correctness and quality of MOPP bytecode.

Can be used from tests or run standalone:
    python mopp_verifier.py <nif_file>

Tests:
1. Correctness: every triangle is reachable from points inside its AABB.
2. Completeness: every leaf output ID refers to a valid triangle.
3. Tightness: random points outside all triangle AABBs produce few/no hits.
"""

import math
import random
import sys
from typing import List, Tuple, Optional, Set, Sequence


def walk_mopp(data: bytes, origin: Tuple[float, float, float],
              largest_dim: float, point: Tuple[float, float, float],
              ) -> Set[int]:
    """Walk the MOPP tree with a query point, return all output IDs reached.

    Args:
        data: MOPP bytecode.
        origin: MOPP origin (expanded AABB min).
        largest_dim: The largest AABB dimension (for coordinate scaling).
        point: Query point in Havok space (x, y, z).

    Returns:
        Set of output IDs (uint32) that the point reaches.
    """
    if not data or largest_dim <= 0:
        return set()

    # Scale the point to MOPP coordinate space (0..254 range, as floats)
    sx = 254.0 * (point[0] - origin[0]) / largest_dim
    sy = 254.0 * (point[1] - origin[1]) / largest_dim
    sz = 254.0 * (point[2] - origin[2]) / largest_dim

    results = set()
    output_base = 0
    _walk_recursive(data, 0, len(data), sx, sy, sz, output_base, results)
    return results


def _walk_recursive(data, pos, end, sx, sy, sz, output_base, results):
    """Recursive MOPP tree walker."""
    while pos < end and pos < len(data):
        op = data[pos]

        if 0x01 <= op <= 0x04:
            # Rescale: subtract offsets and shift
            shift = op
            xx, yy, zz = data[pos+1], data[pos+2], data[pos+3]
            sx = (sx - xx) * (1 << shift)
            sy = (sy - yy) * (1 << shift)
            sz = (sz - zz) * (1 << shift)
            pos += 4

        elif op == 0x05:
            cc = data[pos+1]
            pos = pos + 2 + cc
            end = len(data)  # JUMP is a goto — may leave current subtree

        elif op == 0x06:
            cc = (data[pos+1] << 8) | data[pos+2]
            pos = pos + 3 + cc
            end = len(data)  # JUMP is a goto — may leave current subtree

        elif op == 0x09:
            output_base += data[pos+1]
            pos += 2

        elif op == 0x0A:
            output_base += (data[pos+1] << 8) | data[pos+2]
            pos += 3

        elif op == 0x0B:
            output_base = ((data[pos+1] << 24) | (data[pos+2] << 16)
                           | (data[pos+3] << 8) | data[pos+4])
            pos += 5

        elif 0x10 <= op <= 0x1C:
            # Split: BB AA CC — left child follows, right at +CC
            axis = op - 0x10
            bb, aa, cc = data[pos+1], data[pos+2], data[pos+3]
            coord = _get_coord(axis, sx, sy, sz)
            right_start = pos + 4 + cc
            # Visit left if coord < bb
            if coord < bb:
                _walk_recursive(data, pos + 4, right_start,
                                sx, sy, sz, output_base, results)
            # Visit right if coord >= aa
            if coord >= aa:
                _walk_recursive(data, right_start, end,
                                sx, sy, sz, output_base, results)
            return

        elif 0x20 <= op <= 0x22:
            # Half-split: XX CC
            axis = op - 0x20
            xx, cc = data[pos+1], data[pos+2]
            coord = _get_coord(axis, sx, sy, sz)
            right_start = pos + 3 + cc
            if coord < xx:
                _walk_recursive(data, pos + 3, right_start,
                                sx, sy, sz, output_base, results)
            if coord >= xx:
                _walk_recursive(data, right_start, end,
                                sx, sy, sz, output_base, results)
            return

        elif 0x23 <= op <= 0x25:
            # Split16: BB AA CC CC DD DD
            axis = op - 0x23
            bb, aa = data[pos+1], data[pos+2]
            cc = (data[pos+3] << 8) | data[pos+4]
            dd = (data[pos+5] << 8) | data[pos+6]
            coord = _get_coord(axis, sx, sy, sz)
            instr_end = pos + 7
            lo_start = instr_end + cc
            hi_start = instr_end + dd
            if coord < bb:
                _walk_recursive(data, lo_start, hi_start,
                                sx, sy, sz, output_base, results)
            if coord >= aa:
                _walk_recursive(data, hi_start, end,
                                sx, sy, sz, output_base, results)
            return

        elif 0x26 <= op <= 0x28:
            # Filter: AA BB — proceed only if coord in [AA, BB)
            axis = op - 0x26
            aa, bb = data[pos+1], data[pos+2]
            coord = _get_coord(axis, sx, sy, sz)
            if coord < aa or coord >= bb:
                return  # filtered out
            pos += 3

        elif 0x29 <= op <= 0x2B:
            # Filter24: 3-byte bounds
            axis = op - 0x29
            # These compare against full 24-bit coordinates
            aa = (data[pos+1] << 16) | (data[pos+2] << 8) | data[pos+3]
            bb = (data[pos+4] << 16) | (data[pos+5] << 8) | data[pos+6]
            # Scale coord to 24-bit range
            coord24 = _get_coord(axis, sx, sy, sz) * 256.0 * 256.0
            if coord24 < aa or coord24 >= bb:
                return
            pos += 7

        elif 0x30 <= op <= 0x4F:
            results.add(output_base + (op - 0x30))
            pos += 1

        elif op == 0x50:
            results.add(output_base + data[pos+1])
            pos += 2

        elif op == 0x51:
            results.add(output_base + ((data[pos+1] << 8) | data[pos+2]))
            pos += 3

        elif op == 0x52:
            results.add(output_base + ((data[pos+1] << 16)
                                       | (data[pos+2] << 8) | data[pos+3]))
            pos += 4

        else:
            # Unknown opcode — skip it
            pos += 1


def _get_coord(axis: int, sx: float, sy: float, sz: float) -> float:
    """Get the MOPP coordinate for the given axis index.

    Axes 0-2 are X, Y, Z. Axes 3+ are diagonals per the wiki.
    All values are in the 0..254 scaled coordinate space.
    """
    if axis == 0: return sx          # X
    if axis == 1: return sy          # Y
    if axis == 2: return sz          # Z
    if axis == 3: return sy/2 + sz/2           # YpZ: Y/2 + Z/2
    if axis == 4: return 127 - sy/2 + sz/2     # nYpZ: FE/2 - Y/2 + Z/2
    if axis == 5: return sx/2 + sz/2           # XpZ: X/2 + Z/2
    if axis == 6: return 127 + sx/2 - sz/2     # nXpZ: FE/2 + X/2 - Z/2
    if axis == 7: return sx/2 + sy/2           # XpY: X/2 + Y/2
    if axis == 8: return 127 + sx/2 - sy/2     # nXpY: FE/2 + X/2 - Y/2
    if axis == 9: return sx/3 + sy/3 + sz/3    # XpYpZ
    if axis == 10: return 254/3 + sx/3 + sy/3 - sz/3  # XpYnZ (approximate)
    if axis == 11: return 254/3 + sx/3 - sy/3 + sz/3  # XnYpZ (approximate)
    if axis == 12: return 254/3 - sx/3 + sy/3 + sz/3  # nXpYpZ (approximate)
    return 0


def _triangle_aabb(verts, tri, radius):
    """Compute AABB for a triangle, expanded by radius."""
    v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
    bmin = [min(v0[a], v1[a], v2[a]) - radius for a in range(3)]
    bmax = [max(v0[a], v1[a], v2[a]) + radius for a in range(3)]
    return bmin, bmax


def verify_correctness(
    mopp_bytes: bytes,
    origin: Tuple[float, float, float],
    largest_dim: float,
    verts: Sequence[Tuple[float, float, float]],
    tris: Sequence[Tuple[int, int, int]],
    output_ids: Sequence[int],
    radius: float = 0.005,
    samples_per_tri: int = 10,
    seed: int = 42,
) -> Tuple[bool, List[str]]:
    """Verify every triangle is reachable from points inside its AABB.

    Returns:
        (passed, messages) — passed is True if no false negatives found.
    """
    rng = random.Random(seed)
    messages = []
    passed = True

    for ti, tri in enumerate(tris):
        bmin, bmax = _triangle_aabb(verts, tri, radius)
        oid = output_ids[ti]
        missed = 0

        for _ in range(samples_per_tri):
            # Random point inside the triangle's expanded AABB
            px = rng.uniform(bmin[0], bmax[0])
            py = rng.uniform(bmin[1], bmax[1])
            pz = rng.uniform(bmin[2], bmax[2])

            hits = walk_mopp(mopp_bytes, origin, largest_dim, (px, py, pz))
            if oid not in hits:
                missed += 1

        if missed > 0:
            passed = False
            messages.append(
                f"FAIL: triangle {ti} (output 0x{oid:08X}) missed by "
                f"{missed}/{samples_per_tri} sample points")

    if passed:
        messages.append(f"OK: all {len(tris)} triangles reachable "
                        f"({samples_per_tri} samples each)")
    return passed, messages


def verify_completeness(
    mopp_bytes: bytes,
    origin: Tuple[float, float, float],
    largest_dim: float,
    valid_output_ids: Set[int],
    verts: Sequence[Tuple[float, float, float]],
    tris: Sequence[Tuple[int, int, int]],
    radius: float = 0.005,
    num_samples: int = 1000,
    seed: int = 42,
) -> Tuple[bool, List[str]]:
    """Verify all leaf output IDs in the tree refer to valid triangles.

    Samples random points inside the global AABB and collects all output IDs
    the tree produces. Checks each against the valid set.

    Returns:
        (passed, messages)
    """
    rng = random.Random(seed)
    messages = []

    # Global AABB
    all_coords = [verts[i] for tri in tris for i in tri]
    gmin = [min(v[a] for v in all_coords) - radius for a in range(3)]
    gmax = [max(v[a] for v in all_coords) + radius for a in range(3)]

    seen_ids = set()
    for _ in range(num_samples):
        px = rng.uniform(gmin[0], gmax[0])
        py = rng.uniform(gmin[1], gmax[1])
        pz = rng.uniform(gmin[2], gmax[2])
        hits = walk_mopp(mopp_bytes, origin, largest_dim, (px, py, pz))
        seen_ids.update(hits)

    invalid = seen_ids - valid_output_ids
    passed = len(invalid) == 0
    if invalid:
        for oid in sorted(invalid):
            messages.append(f"FAIL: tree produces output 0x{oid:08X} "
                            f"which is not a valid triangle ID")
    messages.append(f"Seen {len(seen_ids)} unique output IDs, "
                    f"{len(invalid)} invalid")
    return passed, messages


def verify_tightness(
    mopp_bytes: bytes,
    origin: Tuple[float, float, float],
    largest_dim: float,
    verts: Sequence[Tuple[float, float, float]],
    tris: Sequence[Tuple[int, int, int]],
    radius: float = 0.005,
    num_samples: int = 1000,
    seed: int = 42,
) -> Tuple[float, List[str]]:
    """Measure how many false positives the tree produces.

    Samples random points outside all triangle AABBs and counts
    how many leaf hits occur. Returns average hits per outside point.

    Returns:
        (avg_hits, messages)
    """
    rng = random.Random(seed)
    messages = []

    # Precompute per-triangle AABBs
    tri_aabbs = [_triangle_aabb(verts, tri, radius) for tri in tris]

    # Global AABB (slightly expanded to sample outside edges)
    all_coords = [verts[i] for tri in tris for i in tri]
    gmin = [min(v[a] for v in all_coords) - 2 * radius for a in range(3)]
    gmax = [max(v[a] for v in all_coords) + 2 * radius for a in range(3)]

    total_hits = 0
    outside_count = 0

    for _ in range(num_samples):
        px = rng.uniform(gmin[0], gmax[0])
        py = rng.uniform(gmin[1], gmax[1])
        pz = rng.uniform(gmin[2], gmax[2])

        # Check if point is inside any triangle's AABB
        inside_any = False
        for bmin, bmax in tri_aabbs:
            if (bmin[0] <= px <= bmax[0] and
                bmin[1] <= py <= bmax[1] and
                bmin[2] <= pz <= bmax[2]):
                inside_any = True
                break

        if not inside_any:
            hits = walk_mopp(mopp_bytes, origin, largest_dim, (px, py, pz))
            total_hits += len(hits)
            outside_count += 1

    if outside_count > 0:
        avg = total_hits / outside_count
        messages.append(f"Tightness: {avg:.2f} avg hits for {outside_count} "
                        f"outside points ({total_hits} total false positives)")
    else:
        avg = 0.0
        messages.append("No outside points sampled (mesh fills entire AABB)")

    return avg, messages


def verify_all(
    mopp_bytes: bytes,
    origin: Tuple[float, float, float],
    largest_dim: float,
    verts: Sequence[Tuple[float, float, float]],
    tris: Sequence[Tuple[int, int, int]],
    output_ids: Sequence[int],
    radius: float = 0.005,
) -> Tuple[bool, List[str]]:
    """Run all verification checks.

    Returns:
        (passed, messages)
    """
    all_messages = []
    all_passed = True

    all_messages.append("=== Correctness ===")
    ok, msgs = verify_correctness(mopp_bytes, origin, largest_dim,
                                   verts, tris, output_ids, radius)
    all_messages.extend(msgs)
    if not ok:
        all_passed = False

    all_messages.append("\n=== Completeness ===")
    ok, msgs = verify_completeness(mopp_bytes, origin, largest_dim,
                                    set(output_ids), verts, tris, radius)
    all_messages.extend(msgs)
    if not ok:
        all_passed = False

    all_messages.append("\n=== Tightness ===")
    avg, msgs = verify_tightness(mopp_bytes, origin, largest_dim,
                                  verts, tris, radius)
    all_messages.extend(msgs)

    return all_passed, all_messages


# --- Standalone usage ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mopp_verifier.py <nif_file>")
        print("Verifies the MOPP tree in a NIF file for correctness.")
        sys.exit(1)

    import os
    os.chdir(os.path.join(os.path.dirname(__file__), '..', 'io_scene_nifly'))
    sys.path.insert(0, '.')
    from pyn.pynifly import NifFile

    nif_path = sys.argv[1]
    nif = NifFile(nif_path)
    root = nif.root
    c = root.collision_object
    if c is None:
        print("No collision object on root")
        sys.exit(1)

    cb = c.body
    cs = cb.shape
    if cs.blockname != "bhkMoppBvTreeShape":
        print(f"Shape is {cs.blockname}, not bhkMoppBvTreeShape")
        sys.exit(1)

    mopp_bytes, origin, scale = cs.mopp_data
    if not mopp_bytes:
        print("No MOPP data (DLL may not support reading MOPP code)")
        sys.exit(1)

    child = cs.child
    verts = child.vertices
    tris = child.triangles

    # Derive largest_dim from origin (same as disassembler)
    sys.path.insert(0, os.path.join('..', 'io_scene_nifly', 'pyn'))
    from mopp_compiler import _derive_largest_dim
    largest_dim = _derive_largest_dim(mopp_bytes, origin)
    if largest_dim is None:
        print("Could not derive largest_dim from MOPP data")
        sys.exit(1)

    # For vanilla NIFs we don't know the output_id mapping, so we can only
    # test completeness and tightness, not per-triangle correctness.
    # Collect all IDs the tree can produce.
    print(f"MOPP: {len(mopp_bytes)} bytes, {len(verts)} verts, {len(tris)} tris")
    print(f"Origin: ({origin[0]:.4f}, {origin[1]:.4f}, {origin[2]:.4f})")
    print(f"Largest dim: {largest_dim:.4f}")
    print()

    radius = 0.005

    print("=== Tightness ===")
    avg, msgs = verify_tightness(mopp_bytes, origin, largest_dim,
                                  verts, tris, radius)
    for m in msgs:
        print(m)
