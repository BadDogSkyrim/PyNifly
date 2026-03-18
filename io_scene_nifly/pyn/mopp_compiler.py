"""MOPP (Memory Optimized Partial Polytope) bytecode compiler and disassembler.

Compiles a BVH decision tree from collision triangles into the binary MOPP format
used by Havok physics in Skyrim LE/SE.

Reference: https://github.com/niftools/nifxml/wiki/Havok-MOPP-Data-format
"""

import math
from typing import List, Tuple, Optional, Sequence

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_mopp(
    verts: Sequence[Tuple[float, float, float]],
    triangles: Sequence[Tuple[int, int, int]],
    radius: float = 0.005,
    output_ids: Optional[List[int]] = None,
) -> Tuple[bytes, Tuple[float, float, float], float]:
    """Build MOPP bytecode for a set of triangles.

    Args:
        verts: Vertex positions in Havok space.
        triangles: Triangle index triples.
        radius: Collision radius (0.005 for Skyrim SE, 0.1 for Oblivion).
        output_ids: Per-triangle uint32 output IDs.  If *None*, sequential 0,1,2,…

    Returns:
        (mopp_bytes, origin, scale)
    """
    if not triangles:
        return b"", (0.0, 0.0, 0.0), 0.0

    if output_ids is None:
        output_ids = list(range(len(triangles)))

    # --- compute AABB expanded by radius ---
    xs = [verts[i][0] for tri in triangles for i in tri]
    ys = [verts[i][1] for tri in triangles for i in tri]
    zs = [verts[i][2] for tri in triangles for i in tri]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    origin = (min_x - radius, min_y - radius, min_z - radius)
    size_x = (max_x - min_x) + 2 * radius
    size_y = (max_y - min_y) + 2 * radius
    size_z = (max_z - min_z) + 2 * radius
    largest_dim = max(size_x, size_y, size_z)

    if largest_dim <= 0:
        largest_dim = 1e-6

    scale = 254.0 * 256.0 * 256.0 / largest_dim

    # --- build per-triangle AABBs (expanded by radius) ---
    tri_data = []
    for ti, tri in enumerate(triangles):
        v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        tmin = [min(v0[a], v1[a], v2[a]) - radius for a in range(3)]
        tmax = [max(v0[a], v1[a], v2[a]) + radius for a in range(3)]
        centroid = [(tmin[a] + tmax[a]) * 0.5 for a in range(3)]
        tri_data.append(_TriInfo(ti, output_ids[ti], tmin, tmax, centroid))

    # --- build BVH ---
    root = _build_bvh(tri_data, origin, largest_dim)

    # --- encode to bytecode ---
    code = _encode_node(root, origin, largest_dim)

    # --- prepend root bounding filters ---
    code = _add_root_filters(code, origin, largest_dim,
                             root.bbox_min, root.bbox_max)

    return bytes(code), origin, scale


def _derive_largest_dim(data: bytes, origin: Tuple[float, float, float]) -> Optional[float]:
    """Estimate largest_dim from root FILTER nodes and origin.

    Scans the first FILTER instructions to find the axis spanning 00..FF
    (the largest dimension). For that axis, origin is the expanded min
    so largest_dim ≈ -2 * origin[axis] (exact for symmetric objects).
    """
    filters = {}  # axis -> (lo_byte, hi_byte)
    pos = 0
    while pos < len(data) and len(filters) < 3:
        op = data[pos]
        if 0x26 <= op <= 0x28:
            filters[op - 0x26] = (data[pos + 1], data[pos + 2])
            pos += 3
        else:
            break

    if not filters:
        return None

    for axis, (lo, hi) in filters.items():
        if hi == 0xFF and lo == 0x00:
            ld = -2.0 * origin[axis]
            if ld > 0:
                return ld

    return None


def disassemble_mopp(
    mopp_bytes: bytes,
    origin: Optional[Tuple[float, float, float]] = None,
    scale: Optional[float] = None,
) -> List[str]:
    """Disassemble MOPP bytecode to human-readable indented tree.

    Args:
        mopp_bytes: Raw MOPP bytecode.
        origin: Optional origin for world-space annotation.
        scale: Optional scale for world-space annotation.

    Returns:
        List of text lines with tree-structured indentation.
    """
    if not mopp_bytes:
        return []

    data = mopp_bytes
    lines = []

    # Derive largest_dim from the root FILTER bounds + origin.
    # The first 3 instructions are typically FILTER X/Y/Z with lo..hi bytes.
    # The axis whose hi byte is 0xFF spans the full largest_dim.
    # largest_dim = 254 * (max_coord - origin[axis]) / (hi_byte - 1)
    # With hi=0xFF: largest_dim ≈ max_coord - origin[axis]
    largest_dim = None
    if origin is not None:
        largest_dim = _derive_largest_dim(data, origin)

    axis_names = ['X', 'Y', 'Z']

    def _world(axis: int, bound_byte: int, is_upper: bool) -> str:
        if origin is None or largest_dim is None or axis >= 3:
            return ""
        if is_upper:
            val = (bound_byte - 1) / 254.0 * largest_dim + origin[axis]
        else:
            val = bound_byte / 254.0 * largest_dim + origin[axis]
        return f"={val:.4f}"

    def _walk(pos: int, end: int, indent: int):
        """Recursively disassemble from *pos* up to (not including) *end*."""
        pad = "    " * indent
        while pos < end and pos < len(data):
            op = data[pos]

            if 0x01 <= op <= 0x04:
                shift = op
                xx, yy, zz = data[pos+1], data[pos+2], data[pos+3]
                lines.append(f"{pad}[{pos:04X}] RESCALE shift={shift} sub=({xx:02X},{yy:02X},{zz:02X})")
                pos += 4

            elif op == 0x05:
                cc = data[pos+1]
                target = pos + 2 + cc
                lines.append(f"{pad}[{pos:04X}] JUMP -> {target:04X}")
                return  # JUMP is a goto; target is shown in its own branch

            elif op == 0x06:
                cc = (data[pos+1] << 8) | data[pos+2]
                target = pos + 3 + cc
                lines.append(f"{pad}[{pos:04X}] JUMP -> {target:04X}")
                return  # JUMP is a goto; target is shown in its own branch

            elif op == 0x09:
                ii = data[pos+1]
                lines.append(f"{pad}[{pos:04X}] ADD_OUTPUT +0x{ii:02X}")
                pos += 2

            elif op == 0x0A:
                ii = (data[pos+1] << 8) | data[pos+2]
                lines.append(f"{pad}[{pos:04X}] ADD_OUTPUT +0x{ii:04X}")
                pos += 3

            elif op == 0x0B:
                ii = (data[pos+1] << 24) | (data[pos+2] << 16) | (data[pos+3] << 8) | data[pos+4]
                lines.append(f"{pad}[{pos:04X}] SET_OUTPUT 0x{ii:08X}")
                pos += 5

            elif 0x10 <= op <= 0x1C:
                # Split: BB AA CC — left child follows, right child at +CC
                axis = op - 0x10
                bb, aa, cc = data[pos+1], data[pos+2], data[pos+3]
                right_start = pos + 4 + cc
                aname = _split_axis_name(axis)
                w_hi = _world(axis, bb, True)
                w_lo = _world(axis, aa, False)
                lines.append(f"{pad}[{pos:04X}] SPLIT {aname}  <{bb:02X}{w_hi} | >={aa:02X}{w_lo}")
                lines.append(f"{pad}  if {aname} < {bb:02X}{w_hi}:")
                _walk(pos + 4, right_start, indent + 1)
                lines.append(f"{pad}  if {aname} >= {aa:02X}{w_lo}:")
                _walk(right_start, end, indent + 1)
                return  # both branches consumed the remaining range

            elif 0x20 <= op <= 0x22:
                # Half-split: XX CC — left follows, right at +CC
                axis = op - 0x20
                xx, cc = data[pos+1], data[pos+2]
                right_start = pos + 3 + cc
                aname = axis_names[axis]
                w = _world(axis, xx, True)
                lines.append(f"{pad}[{pos:04X}] SPLIT {aname}  bound={xx:02X}{w}")
                lines.append(f"{pad}  if {aname} < {xx:02X}{w}:")
                _walk(pos + 3, right_start, indent + 1)
                lines.append(f"{pad}  if {aname} >= {xx:02X}{w}:")
                _walk(right_start, end, indent + 1)
                return

            elif 0x23 <= op <= 0x25:
                # Split16: BB AA CC_hi CC_lo DD_hi DD_lo
                axis = op - 0x23
                bb, aa = data[pos+1], data[pos+2]
                cc = (data[pos+3] << 8) | data[pos+4]
                dd = (data[pos+5] << 8) | data[pos+6]
                instr_end = pos + 7
                lo_start = instr_end + cc
                hi_start = instr_end + dd
                aname = axis_names[axis]
                w_hi = _world(axis, bb, True)
                w_lo = _world(axis, aa, False)
                lines.append(f"{pad}[{pos:04X}] SPLIT16 {aname}  <{bb:02X}{w_hi} | >={aa:02X}{w_lo}")
                lines.append(f"{pad}  if {aname} < {bb:02X}{w_hi}:")
                _walk(lo_start, hi_start, indent + 1)
                lines.append(f"{pad}  if {aname} >= {aa:02X}{w_lo}:")
                _walk(hi_start, end, indent + 1)
                return

            elif 0x26 <= op <= 0x28:
                axis = op - 0x26
                aa, bb = data[pos+1], data[pos+2]
                aname = axis_names[axis]
                w_lo = _world(axis, aa, False)
                w_hi = _world(axis, bb, True)
                lines.append(f"{pad}[{pos:04X}] FILTER {aname}  {aa:02X}{w_lo}..{bb:02X}{w_hi}")
                pos += 3

            elif 0x29 <= op <= 0x2B:
                axis = op - 0x29
                aa = (data[pos+1] << 16) | (data[pos+2] << 8) | data[pos+3]
                bb = (data[pos+4] << 16) | (data[pos+5] << 8) | data[pos+6]
                aname = axis_names[axis]
                lines.append(f"{pad}[{pos:04X}] FILTER24 {aname}  {aa:06X}..{bb:06X}")
                pos += 7

            elif 0x30 <= op <= 0x4F:
                output_id = op - 0x30
                lines.append(f"{pad}[{pos:04X}] LEAF 0x{output_id:08X}")
                pos += 1

            elif op == 0x50:
                ii = data[pos+1]
                lines.append(f"{pad}[{pos:04X}] LEAF 0x{ii:08X}")
                pos += 2

            elif op == 0x51:
                ii = (data[pos+1] << 8) | data[pos+2]
                lines.append(f"{pad}[{pos:04X}] LEAF 0x{ii:08X}")
                pos += 3

            elif op == 0x52:
                ii = (data[pos+1] << 16) | (data[pos+2] << 8) | data[pos+3]
                lines.append(f"{pad}[{pos:04X}] LEAF 0x{ii:08X}")
                pos += 4

            else:
                lines.append(f"{pad}[{pos:04X}] UNKNOWN 0x{op:02X}")
                pos += 1

    _walk(0, len(data), 0)
    return lines


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hex_bytes(data: bytes, start: int, count: int) -> str:
    return " ".join(f"{data[start+i]:02X}" for i in range(count) if start + i < len(data))


def _split_axis_name(axis: int) -> str:
    """Return axis name for split opcodes 0x10-0x1C."""
    names = [
        'X', 'Y', 'Z',           # 0x10-0x12
        'YpZ', 'nYpZ',           # 0x13-0x14  Y+Z, FE/2-Y/2+Z/2
        'XpZ', 'nXpZ',           # 0x15-0x16  X+Z, FE/2+X/2-Z/2
        'XpY', 'nXpY',           # 0x17-0x18  X+Y, FE/2+X/2-Y/2
        'XpYpZ',                  # 0x19       X/3+Y/3+Z/3
        'XpYnZ', 'XnYpZ', 'nXpYpZ',  # 0x1A-0x1C
    ]
    if axis < len(names):
        return names[axis]
    return f"?{axis}"


class _TriInfo:
    """Per-triangle data for BVH construction."""
    __slots__ = ('index', 'output_id', 'bbox_min', 'bbox_max', 'centroid')

    def __init__(self, index, output_id, bbox_min, bbox_max, centroid):
        self.index = index
        self.output_id = output_id
        self.bbox_min = bbox_min
        self.bbox_max = bbox_max
        self.centroid = centroid


class _BVHNode:
    """Binary BVH node."""
    __slots__ = ('tris', 'left', 'right', 'split_axis', 'bbox_min', 'bbox_max')

    def __init__(self):
        self.tris = []          # leaf triangles (_TriInfo list)
        self.left = None        # _BVHNode or None
        self.right = None       # _BVHNode or None
        self.split_axis = -1    # 0=X, 1=Y, 2=Z
        self.bbox_min = [0, 0, 0]
        self.bbox_max = [0, 0, 0]


def _compute_bbox(tris: List[_TriInfo]):
    """Compute encompassing AABB of a list of _TriInfo."""
    bmin = [min(t.bbox_min[a] for t in tris) for a in range(3)]
    bmax = [max(t.bbox_max[a] for t in tris) for a in range(3)]
    return bmin, bmax


def _build_bvh(tris: List[_TriInfo], origin, largest_dim, depth=0) -> _BVHNode:
    """Recursively build a BVH from triangle AABBs."""
    node = _BVHNode()
    node.bbox_min, node.bbox_max = _compute_bbox(tris)

    # Leaf condition: 1 or 2 triangles, or max depth
    if len(tris) <= 2 or depth > 40:
        node.tris = tris
        return node

    # Choose split axis: longest AABB dimension, cycling on ties
    extents = [node.bbox_max[a] - node.bbox_min[a] for a in range(3)]
    max_ext = max(extents)
    tied = [a for a in range(3) if abs(extents[a] - max_ext) < 1e-9]
    axis = tied[depth % len(tied)]

    # Sort by centroid along split axis
    sorted_tris = sorted(tris, key=lambda t: t.centroid[axis])

    # Median split
    mid = len(sorted_tris) // 2
    if mid == 0:
        mid = 1

    left_tris = sorted_tris[:mid]
    right_tris = sorted_tris[mid:]

    # Degenerate case: all centroids identical on this axis
    if not left_tris or not right_tris:
        node.tris = tris
        return node

    node.split_axis = axis
    node.left = _build_bvh(left_tris, origin, largest_dim, depth + 1)
    node.right = _build_bvh(right_tris, origin, largest_dim, depth + 1)

    return node


def _encode_bound_upper(bound_max: float, origin_axis: float, largest_dim: float) -> int:
    """Encode an upper bound to a MOPP byte (exclusive comparison)."""
    val = math.floor(1 + 254.0 * (bound_max - origin_axis) / largest_dim)
    return max(0, min(255, val))


def _encode_bound_lower(bound_min: float, origin_axis: float, largest_dim: float) -> int:
    """Encode a lower bound to a MOPP byte (inclusive comparison)."""
    val = math.floor(254.0 * (bound_min - origin_axis) / largest_dim)
    return max(0, min(255, val))


def _emit_leaf(output_id: int) -> bytearray:
    """Emit leaf opcodes for a given output ID."""
    code = bytearray()
    if output_id <= 0x1F:
        # Opcodes 0x30..0x4F encode output IDs 0..31 in a single byte
        code.append(0x30 + output_id)
    elif output_id <= 0xFF:
        code.append(0x50)
        code.append(output_id)
    elif output_id <= 0xFFFF:
        code.append(0x51)
        code.append((output_id >> 8) & 0xFF)
        code.append(output_id & 0xFF)
    else:
        code.append(0x52)
        code.append((output_id >> 16) & 0xFF)
        code.append((output_id >> 8) & 0xFF)
        code.append(output_id & 0xFF)
    return code


def _encode_node(node: _BVHNode, origin, largest_dim) -> bytearray:
    """Recursively encode a BVH node to MOPP bytecode."""
    code = bytearray()

    # --- Leaf node ---
    if node.left is None and node.right is None:
        for tri in node.tris:
            code.extend(_emit_leaf(tri.output_id))
        return code

    # --- Internal split node ---
    axis = node.split_axis

    # Emit filter nodes for each axis at this level to tighten bounds
    # Only emit filters at root or when bounds are significantly tighter
    # than parent.  For simplicity, emit filters for all 3 axes at root.

    # Encode left and right children
    left_code = _encode_node(node.left, origin, largest_dim)
    right_code = _encode_node(node.right, origin, largest_dim)

    # Compute bound bytes for the split
    # left child: objects with coordinate < BB (upper bound of right)
    # right child: objects with coordinate >= AA (lower bound of right)
    # BB = upper bound of left child on split axis
    # AA = lower bound of right child on split axis
    bb = _encode_bound_upper(node.left.bbox_max[axis], origin[axis], largest_dim)
    aa = _encode_bound_lower(node.right.bbox_min[axis], origin[axis], largest_dim)

    # Determine jump size needed for the right child offset
    # The jump is from end of this instruction to start of right child code.
    # Left child code follows immediately after the split instruction.
    right_offset = len(left_code)

    if right_offset <= 255:
        # Use 1-byte jump: opcode 0x10+axis, BB, AA, CC
        code.append(0x10 + axis)
        code.append(bb)
        code.append(aa)
        code.append(right_offset)
    elif right_offset <= 65535:
        # Use 2-byte jumps: opcode 0x23+axis, BB, AA, CC_hi, CC_lo, DD_hi, DD_lo
        # CC = offset to right child from end of instruction (=len(left_code))
        # DD = offset to right child from end of instruction (same, since both go to right)
        # Actually: CC = jump for "< BB" branch, DD = jump for ">= AA" branch
        # For our tree: < BB -> left (immediately after), >= AA -> right (after left_code)
        # So CC is 0 (left is right after), DD is len(left_code)
        # Wait, re-reading the format:
        # 23: BB AA CC CC DD DD
        # If < BB, jump CC CC bytes. If >= AA, jump DD DD bytes.
        # So left branch = CC, right branch = DD
        # Our left follows immediately → CC = 0... but that seems odd.
        # Actually looking at the wiki more carefully: for 23-25,
        # "If smaller than BB, go to CC CC bytes after end of block.
        #  If >= AA, go to DD DD bytes after end of block."
        # So both are jumps. Left child at CC=0, right child at DD=len(left_code).
        code.append(0x23 + axis)
        code.append(bb)
        code.append(aa)
        code.append(0)  # CC high byte (left child at offset 0)
        code.append(0)  # CC low byte
        code.append((right_offset >> 8) & 0xFF)
        code.append(right_offset & 0xFF)
    else:
        # Tree too large for even 2-byte jump — shouldn't happen with
        # reasonable meshes. Fall back to emitting both children as leaves.
        for tri in node.tris or []:
            code.extend(_emit_leaf(tri.output_id))
        return code

    code.extend(left_code)
    code.extend(right_code)

    return code


def _add_root_filters(code: bytearray, origin, largest_dim,
                      bbox_min, bbox_max) -> bytearray:
    """Prepend axis filter nodes for the root bounding box."""
    prefix = bytearray()
    for axis in range(3):
        lo = _encode_bound_lower(bbox_min[axis], origin[axis], largest_dim)
        hi = _encode_bound_upper(bbox_max[axis], origin[axis], largest_dim)
        # Opcode 0x26+axis: filter on axis
        prefix.append(0x26 + axis)
        prefix.append(lo)
        prefix.append(hi)
    return prefix + code
