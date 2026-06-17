#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cloth_autounpack.py
-------------------
Inspect the Havok cloth packfile stored in an FO4 `BSClothExtraData` block.

FO4 hair, dresses, dusters, coats, and robes carry a `BSClothExtraData` block
whose payload is a Havok packfile (hk_2014.1.0) describing a "Character Bone
Deforming Clothing" cloth simulation: an `hclClothData` graph of `hclSimClothData`
(particles + constraints), collidables/capsules, simulation operators, and an
`hkaSkeleton` (the bones the cloth deforms). PyNifly currently round-trips this
blob verbatim; this module unpacks it so we can see what's inside and document the
format (Phase 0 of giving cloth semantic import/export).

This is reconnaissance tooling, mirroring `bhk_autounpack.py`. The container layer
(sections, fixups, hkArray resolution) comes from `havok_packfile.py`; here we add
cloth-specific decoding plus a generic "find the hkArrays and string pointers in
each object" pass that surfaces structure without hardcoding every one of the ~20
HCL classes.

Run standalone:
    python cloth_autounpack.py <input.nif | raw_blob.bin> [--json]
"""

import sys
import json
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from .havok_packfile import (
        HavokPackfile, HkObject, parse_packfile, is_havok_packfile,
        packfile_version, u16, u32, i32, f32,
    )
except ImportError:
    from havok_packfile import (
        HavokPackfile, HkObject, parse_packfile, is_havok_packfile,
        packfile_version, u16, u32, i32, f32,
    )


# ── decoded structures ───────────────────────────────────────────────────────

@dataclass
class ClothSkeleton:
    name: str = ""
    bones: List[str] = field(default_factory=list)
    parents: List[int] = field(default_factory=list)
    # reference pose: list of (translation[3], rotation[4], scale[3])
    pose: List[Tuple[Tuple[float, float, float],
                     Tuple[float, float, float, float],
                     Tuple[float, float, float]]] = field(default_factory=list)


@dataclass
class HkArrayField:
    """A resolved hkArray<T> found inside an object: where it points and how big."""
    field_off: int      # offset of the field within the object
    abs_off: int        # absolute file offset of the array data
    count: int          # element count
    capacity: int       # capacity (lower 30 bits of capFlags)


@dataclass
class StringField:
    field_off: int
    value: str


@dataclass
class ObjectInfo:
    obj: HkObject
    arrays: List[HkArrayField] = field(default_factory=list)
    strings: List[StringField] = field(default_factory=list)


@dataclass
class ClothPackfile:
    version: str
    objects: List[ObjectInfo]
    skeleton: Optional[ClothSkeleton] = None
    # class_name -> count, for a quick inventory summary
    class_counts: Dict[str, int] = field(default_factory=dict)
    pf: Optional[HavokPackfile] = None


# ── hkaSkeleton decode (layout per hkx/anim_fo4.py::_parse_skeleton_hkx) ───────

# hkaSkeleton field offsets within the object (hk_2014.1.0, 64-bit):
#   +0x10 name (hkStringPtr)
#   +0x18 parentIndices (hkArray<int16>)
#   +0x28 bones         (hkArray<hkaBone>, stride 0x10: strptr(8)+lockTrans(1)+pad)
#   +0x38 referencePose (hkArray<hkQsTransform>, stride 0x30: pos vec4 / rot vec4 / scale vec4)
_SKEL_NAME = 0x10
_SKEL_PARENTS = 0x18
_SKEL_BONES = 0x28
_SKEL_POSE = 0x38
_BONE_STRIDE = 0x10
_POSE_STRIDE = 0x30


def decode_skeleton(pf: HavokPackfile, obj: HkObject) -> ClothSkeleton:
    """Decode an hkaSkeleton object's bone names, parents, and reference pose."""
    skel = ClothSkeleton()
    data, ds = pf.data, pf.data_start

    skel.name = pf.cstr(pf.ptr(obj.rel, _SKEL_NAME))

    pi_abs, pi_count = pf.array(obj.rel, _SKEL_PARENTS)
    if pi_abs is not None:
        skel.parents = [struct.unpack_from('<h', data, pi_abs + i * 2)[0]
                        for i in range(pi_count)]

    b_abs, b_count = pf.array(obj.rel, _SKEL_BONES)
    if b_abs is not None:
        b_rel = b_abs - ds
        for i in range(b_count):
            name_ptr = pf.ptr(b_rel + i * _BONE_STRIDE, 0)
            skel.bones.append(pf.cstr(name_ptr))

    p_abs, p_count = pf.array(obj.rel, _SKEL_POSE)
    if p_abs is not None:
        for i in range(p_count):
            p = p_abs + i * _POSE_STRIDE
            if p + _POSE_STRIDE > len(data):
                break
            pos = (f32(data, p), f32(data, p + 4), f32(data, p + 8))
            rot = (f32(data, p + 16), f32(data, p + 20), f32(data, p + 24), f32(data, p + 28))
            scl = (f32(data, p + 32), f32(data, p + 36), f32(data, p + 40))
            skel.pose.append((pos, rot, scl))
    return skel


# ── generic structure discovery ───────────────────────────────────────────────

def _looks_like_string_region(data: bytes, abs_off: int) -> Optional[str]:
    """If abs_off points at a short printable NUL-terminated string, return it."""
    if abs_off < 0 or abs_off >= len(data):
        return None
    end = data.find(b"\x00", abs_off, abs_off + 128)
    if end <= abs_off:
        return None
    chunk = data[abs_off:end]
    if all(32 <= b < 127 for b in chunk) and len(chunk) >= 2:
        return chunk.decode("ascii")
    return None


def discover_object(pf: HavokPackfile, obj: HkObject) -> ObjectInfo:
    """Scan one object for hkArray fields and string pointers via the fixup table.

    An hkArray<T> on 64-bit is {T* data; int32 size; int32 capFlags}. We treat any
    8-aligned field that (a) has a local fixup (so its pointer is relocated) and
    (b) whose +8 dword is a plausible size <= capacity, as an hkArray. A relocated
    pointer that instead lands in a printable string is reported as a string field.
    This reveals each object's layout without a hand-coded struct for every class.
    """
    info = ObjectInfo(obj=obj)
    data, ds = pf.data, pf.data_start
    # Walk candidate pointer fields at 8-byte granularity across the object body.
    off = 0
    while off + 8 <= obj.size:
        target = pf.ptr(obj.rel, off)
        if target is not None:
            size = u32(data, ds + obj.rel + off + 8) if off + 16 <= obj.size else 0
            capflags = u32(data, ds + obj.rel + off + 12) if off + 16 <= obj.size else 0
            capacity = capflags & 0x3FFFFFFF
            s = _looks_like_string_region(data, target)
            if s is not None and not (0 < size <= capacity and capacity > 0):
                info.strings.append(StringField(field_off=off, value=s))
            elif 0 < size <= capacity and capacity > 0:
                info.arrays.append(HkArrayField(field_off=off, abs_off=target,
                                                count=size, capacity=capacity))
        off += 8
    return info


def parse_cloth_packfile(data: bytes) -> ClothPackfile:
    """Parse a BSClothExtraData blob into an inspectable structure."""
    pf = parse_packfile(data)
    result = ClothPackfile(version=packfile_version(data), objects=[], pf=pf)
    for o in pf.objects:
        result.class_counts[o.class_name] = result.class_counts.get(o.class_name, 0) + 1
        result.objects.append(discover_object(pf, o))
    skels = pf.objects_of("hkaSkeleton")
    if skels:
        result.skeleton = decode_skeleton(pf, skels[0])
    return result


# ── reporting ──────────────────────────────────────────────────────────────--

def format_report(cp: ClothPackfile) -> str:
    out: List[str] = []
    pf = cp.pf
    out.append(f"Havok cloth packfile  version={cp.version}  objects={len(cp.objects)}")
    out.append("")
    out.append("Class inventory:")
    for cls, n in sorted(cp.class_counts.items(), key=lambda kv: -kv[1]):
        out.append(f"  {n:3d}  {cls}")
    out.append("")
    out.append("Objects (offset / size / resolved arrays & strings):")
    for oi in cp.objects:
        o = oi.obj
        out.append(f"  [{o.index:2d}] rel={o.rel:#08x} size={o.size:#07x} {o.class_name}")
        # Interleave string and array fields in offset order so the listing reads
        # top-to-bottom by address. (Only resolved pointers appear -- scalar fields
        # and null pointers between these lines are not shown.)
        lines = [(sf.field_off, f"str   {sf.value!r}") for sf in oi.strings]
        lines += [(af.field_off, f"array[{af.count}] @ {af.abs_off:#x} (cap {af.capacity})")
                  for af in oi.arrays]
        for off, text in sorted(lines):
            out.append(f"          +{off:#05x} {text}")
    if cp.skeleton:
        s = cp.skeleton
        out.append("")
        out.append(f"hkaSkeleton  name={s.name!r}  bones={len(s.bones)}  "
                   f"parents={len(s.parents)}  pose={len(s.pose)}")
        for i, b in enumerate(s.bones):
            par = s.parents[i] if i < len(s.parents) else None
            par_name = s.bones[par] if par is not None and 0 <= par < len(s.bones) else "-"
            out.append(f"    {i:2d}  parent={par:>3}({par_name})  {b}"
                       if par is not None else f"    {i:2d}  {b}")
    return "\n".join(out)


def _to_jsonable(cp: ClothPackfile) -> dict:
    return {
        "version": cp.version,
        "class_counts": cp.class_counts,
        "objects": [
            {
                "index": oi.obj.index,
                "class": oi.obj.class_name,
                "rel": oi.obj.rel,
                "size": oi.obj.size,
                "arrays": [{"field": a.field_off, "count": a.count,
                            "abs": a.abs_off, "capacity": a.capacity} for a in oi.arrays],
                "strings": [{"field": s.field_off, "value": s.value} for s in oi.strings],
            }
            for oi in cp.objects
        ],
        "skeleton": None if not cp.skeleton else {
            "name": cp.skeleton.name,
            "bones": cp.skeleton.bones,
            "parents": cp.skeleton.parents,
            "pose": cp.skeleton.pose,
        },
    }


def _cloth_blobs_from_nif(path: str) -> List[Tuple[str, bytes]]:
    """Return (name, bytes) for each BSClothExtraData blob in a nif."""
    try:
        from .pynifly import NifFile
    except ImportError:
        # Standalone: pynifly uses package-relative imports, so put io_scene_nifly
        # on the path and import it as part of the `pyn` package.
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)
        from pyn.pynifly import NifFile
    return NifFile(path).cloth_data


def _main(argv: List[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    as_json = "--json" in argv
    if not args:
        print(__doc__)
        return 2
    path = args[0]

    blobs: List[Tuple[str, bytes]]
    if path.lower().endswith(".nif"):
        blobs = _cloth_blobs_from_nif(path)
        if not blobs:
            print(f"No BSClothExtraData found in {path}")
            return 1
    else:
        with open(path, "rb") as f:
            blobs = [("(raw)", f.read())]

    for name, blob in blobs:
        if not is_havok_packfile(blob):
            print(f"{name}: not a Havok packfile ({len(blob)} bytes)")
            continue
        cp = parse_cloth_packfile(blob)
        if as_json:
            print(json.dumps(_to_jsonable(cp), indent=2))
        else:
            print(f"=== {name} ({len(blob)} bytes) ===")
            print(format_report(cp))
            print()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
