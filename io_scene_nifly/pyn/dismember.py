"""FO4 dismemberment helpers — pure geometry and data, no Blender.

These functions are used by the Blender export path to:
- decide which dismember bone owns each subsegment (proximity to bone line segment),
- pick the "bearer" subsegment per bone (the one whose centroid is closest to the
  bone midpoint along the bone axis),
- compute cut offsets when a bearer carries none, using the verified recipe
  step ≈ bone_length / 9.5,
- assemble the SSF JSON content.

Format reference: ../../docs/file-formats/dismemberment.md (in the Bethesda Library).
"""
import math


# Dismember bone hierarchy (FO4 human). Each entry is parent -> child along the
# limb, so we can sample the bone as a line segment from head(parent) to
# head(child) for proximity + cut-offset math. Terminal bones (Hand, Foot) have
# no child here — vanilla doesn't carry cut offsets on them, so the supply step
# skips them.
FO4_HUMAN_DISMEMBER_CHILDREN = {
    "RArm_UpperArm": "RArm_ForeArm1",
    "RArm_ForeArm1": "RArm_Hand",
    "LArm_UpperArm": "LArm_ForeArm1",
    "LArm_ForeArm1": "LArm_Hand",
    "RLeg_Thigh":    "RLeg_Calf",
    "RLeg_Calf":     "RLeg_Foot",
    "LLeg_Thigh":    "LLeg_Calf",
    "LLeg_Calf":     "LLeg_Foot",
    "Neck":          "Head",  # if Head bone exists
}

# Dismember material hash -> nif skeleton bone name (FO4 human). The keys come
# from niflytools.fo4BoneIDs (PyNifly labels); the values are the actual FO4
# deform bone names that the dismemberment system addresses. Hardcoded because
# the PyNifly bone-name dict doesn't bridge dismember labels to FO4 bones, and
# Bethesda's set is fixed anyway.
FO4_MATERIAL_TO_BONE = {
    0xb2e2764f: "RArm_UpperArm",  # Up Arm.R
    0x6fc3fbb2: "RArm_ForeArm1",  # Lo Arm.R
    0xfc03dc25: "LArm_UpperArm",  # Up Arm.L
    0x212251d8: "LArm_ForeArm1",  # Lo Arm.L
    0xbf3a3cc5: "RLeg_Thigh",     # Thigh.R
    0x22324321: "RLeg_Calf",      # Calf.R
    0xc7e6bc92: "RLeg_Foot",      # Foot.R
    0x865d8d9e: "LLeg_Thigh",     # Thigh.L
    0x4630dac2: "LLeg_Calf",      # Calf.L
    0xa3e42571: "LLeg_Foot",      # Foot.L
    0xB1EC5379: "RArm_Hand",      # Hand.R
    0xD5EECA9A: "LArm_Hand",      # Hand.L
    0x0155094f: "Neck",           # Neck
    0x86b72980: "Head",           # Head
}


# --- geometry ---------------------------------------------------------------

def _proj_on_segment(p, a, b):
    """Project point p onto line segment a->b.

    Returns (t, dist) where t is the parametric position along the segment
    (unclamped, useful for ordering) and dist is the perpendicular distance
    from p to the segment (clamped at the endpoints).
    """
    abx, aby, abz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    apx, apy, apz = p[0] - a[0], p[1] - a[1], p[2] - a[2]
    ab2 = abx * abx + aby * aby + abz * abz
    if ab2 == 0.0:
        return 0.0, math.sqrt(apx * apx + apy * apy + apz * apz)
    t = (apx * abx + apy * aby + apz * abz) / ab2
    tc = max(0.0, min(1.0, t))
    cx = a[0] + tc * abx
    cy = a[1] + tc * aby
    cz = a[2] + tc * abz
    dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
    return t, math.sqrt(dx * dx + dy * dy + dz * dz)


def nearest_bone(point, bones):
    """Given a point and {name: (origin, child_origin)} bones, return the name
    of the bone whose line segment is closest to the point. Returns None if
    bones is empty."""
    best_name = None
    best_dist = float("inf")
    for name, (a, b) in bones.items():
        _, d = _proj_on_segment(point, a, b)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name


def along_bone(point, origin, child):
    """Distance of point along the bone axis (origin -> child), measured from
    origin. Same units as the input coordinates. Used to order subsegments
    proximal-to-distal and to find the bearer (the one closest to the midpoint).
    """
    abx, aby, abz = child[0] - origin[0], child[1] - origin[1], child[2] - origin[2]
    apx, apy, apz = point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]
    L2 = abx * abx + aby * aby + abz * abz
    if L2 == 0.0:
        return 0.0
    L = math.sqrt(L2)
    return (apx * abx + apy * aby + apz * abz) / L


def bone_length(origin, child):
    dx, dy, dz = child[0] - origin[0], child[1] - origin[1], child[2] - origin[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


# --- cut offsets ------------------------------------------------------------

# Empirically the per-bone cut grid in vanilla is step ~= bone_length / 9.5
# (verified against MaleBody.nif: length/step landed 8.96-9.88 across four
# bones). See ../../docs/file-formats/dismemberment.md for the data.
CUT_GRID_DIVISOR = 9.5
MAX_CUTS = 8  # NIF format: NumCutOffsets fits 0..8


def cut_offsets_for_span(bone_len, span_min, span_max, max_cuts=MAX_CUTS):
    """Generate cut offsets at k*step for integer k whose k*step falls within
    [span_min, span_max], with step = bone_len / 9.5.

    bone_len: distance from the bone's joint to its child joint.
    span_min/span_max: the subsegment's stretch along the bone (distances from
        the joint along the bone axis). Cuts outside this range are dropped.
    """
    if bone_len <= 0:
        return []
    step = bone_len / CUT_GRID_DIVISOR
    if step <= 0:
        return []
    # Use floor on both ends so grid points sitting just outside the subseg
    # span (within one step) are still picked. This matches vanilla, where
    # the proximal cut typically lands a hair inside the subseg's start
    # (e.g. RArm_UpperArm: subseg span ~7.6..13.3, cuts include k=4 at 7.566).
    k_lo = max(1, int(math.floor(span_min / step)))
    k_hi = max(k_lo - 1, int(math.floor(span_max / step)))
    cuts = [round(k * step, 4) for k in range(k_lo, k_hi + 1)]
    if len(cuts) > max_cuts:
        # Pick the middle slab so the cuts stay centered in the subseg span.
        start = (len(cuts) - max_cuts) // 2
        cuts = cuts[start:start + max_cuts]
    return cuts


# --- SSF JSON ---------------------------------------------------------------

def encode_ssf_ref(seg_index, subseg_index_within_segment):
    """Encode a segment/subsegment reference for a BoneDeltaList entry.
    seg_index and subseg_index are 0-based, both within their parent containers.
    """
    return (seg_index << 16) | (subseg_index_within_segment << 8)


def decode_ssf_ref(ref):
    """Inverse of encode_ssf_ref. Given a BoneDeltaList entry, return
    (seg_index, subseg_index_within_segment), both 0-based."""
    return ((ref >> 16) & 0xFF, (ref >> 8) & 0xFF)


def parse_ssf(text):
    """Parse SSF (segment file) JSON text.

    Returns {shape_name: {(seg_index, subseg_index): bone_name}} — for each
    shape, the segment/subsegment reference that a skeleton bone severs is
    mapped back to that bone. Import uses this to attach a subsegment's cut
    offsets to the right bone. A subsegment referenced by more than one bone
    keeps the last one seen (not expected in vanilla data)."""
    import json
    result = {}
    for shape_name, entry in json.loads(text).items():
        subseg_to_bone = {}
        for delta in entry.get("DeltaBones", []):
            bone = delta.get("BoneName")
            for ref in delta.get("BoneDeltaList", []):
                subseg_to_bone[decode_ssf_ref(ref)] = bone
        result[shape_name] = subseg_to_bone
    return result


def build_ssf_shape_entry(bone_to_bearer_ref, base_bone_name="DISABLED"):
    """Build one shape's SSF top-level entry from a bone -> encoded ref map.
    Returns a dict ready for json.dumps."""
    deltas = [{"BoneName": bn, "BoneDeltaList": [ref]}
              for bn, ref in bone_to_bearer_ref.items()]
    return {
        "BaseBoneName": base_bone_name,
        "DeltaBones": deltas,
        "uiNumDeltas": len(deltas),
    }


# --- orchestrator -----------------------------------------------------------

def supply_for_shape(shape_partitions, subseg_verts, bones, hash_to_bone_name):
    """Fill in missing cut offsets on each FO4 dismember subsegment and build
    the SSF bone->bearer-ref map for the shape.

    shape_partitions: dict-of-{name: partition} as returned by
        partitions_from_vert_groups. Order preserved.
    subseg_verts: {subseg_name: [(x,y,z), ...]} vertex positions for each
        subsegment (in the same coordinate space as `bones`).
    bones: {nif_bone_name: (origin, child_origin)} dismember bone line segments.
    hash_to_bone_name: {material_hash: nif_bone_name} reverse lookup.

    Returns {nif_bone_name: (seg_index, subseg_index_within_segment)} suitable
    for SSF encoding. Subsegments whose material has no matching bone (or
    whose bone has no entry in `bones`) are skipped.

    Mutates `shape_partitions`: for each bearer subsegment without cut_offsets,
    fills them in via the bone-length/9.5 formula scoped to the bearer's span.
    Subsegments that already carry cut_offsets are left untouched (round-trip
    case takes precedence over supply).
    """
    # Group subsegments by (segment, material). Order within material is the
    # original vg-name-sorted order, which is also their order in the segment.
    from collections import defaultdict
    by_material = defaultdict(list)  # (seg.id, material) -> [subseg, ...]
    seg_by_id = {}                   # seg.id -> segment object
    for part in shape_partitions.values():
        if type(part).__name__ != "FO4Subsegment":
            continue
        by_material[(part.parent.id, part.material)].append(part)
        seg_by_id[part.parent.id] = part.parent

    bone_to_bearer = {}

    for (seg_id, material), subs in by_material.items():
        seg = seg_by_id[seg_id]
        bone_name = hash_to_bone_name.get(material)
        if not bone_name or bone_name not in bones:
            continue
        origin, child = bones[bone_name]
        L = bone_length(origin, child)
        if L <= 0:
            continue
        midpoint = L * 0.5

        # Project each subseg's centroid along the bone; bearer = closest to
        # midpoint. Compute span from each subseg's verts (min..max along bone).
        ranked = []
        spans = {}
        for ss in subs:
            verts = subseg_verts.get(ss.name) or []
            if not verts:
                continue
            cx = sum(v[0] for v in verts) / len(verts)
            cy = sum(v[1] for v in verts) / len(verts)
            cz = sum(v[2] for v in verts) / len(verts)
            t_center = along_bone((cx, cy, cz), origin, child)
            proj = [along_bone(v, origin, child) for v in verts]
            spans[ss.name] = (min(proj), max(proj))
            ranked.append((abs(t_center - midpoint), ss))
        if not ranked:
            continue
        ranked.sort(key=lambda x: x[0])
        bearer = ranked[0][1]

        # Position of bearer within its parent segment's subsegments list
        # (0-based) — needed for the SSF BoneDeltaList encoding.
        try:
            sub_idx = seg.subsegments.index(bearer)
        except ValueError:
            sub_idx = 0
        bone_to_bearer[bone_name] = (seg.index, sub_idx)

        # Round-trip data wins: only supply if the bearer has no cuts already.
        if not getattr(bearer, "cut_offsets", None):
            smin, smax = spans[bearer.name]
            bearer.cut_offsets = cut_offsets_for_span(L, smin, smax)

    return bone_to_bearer
