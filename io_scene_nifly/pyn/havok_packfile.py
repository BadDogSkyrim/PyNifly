#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
havok_packfile.py
-----------------
Shared Havok packfile (hkx binary packfile, hk_2014.1.0) container parsing.

A Havok packfile has three sections -- `__classnames__`, `__types__`, `__data__`
-- a fixed-ish header, then per-section fixup tables (local/global/virtual) that
relocate pointers. FO4 uses this exact container for two unrelated payloads:
  * native collision / physics (bhkNPCollisionObject -> bhkPhysicsSystem), parsed
    by `bhk_autounpack.py`; and
  * cloth simulation (BSClothExtraData), parsed by `cloth_autounpack.py`.

This module owns the container layer both share: locating the sections, reading
the fixup tables, and resolving pointers / `hkArray<T>` fields. The class-specific
decoding lives in the two callers.

The low-level helpers (primitive readers, the fixup-table parsers, hkArray
resolution) are proven in `bhk_autounpack.py`; we re-export them here so there's a
single import surface and `bhk_autounpack` stays untouched. The one thing we
*don't* reuse is its section-header parser: it hardcodes the section-header start
at file offset 0x40, but that offset depends on the (variable-length) version
string in the header -- cloth blobs put it at 0x50. `parse_section_headers` below
locates the sections by scanning for their tag strings instead, which is robust to
that variation. (A later cleanup could move the shared helpers physically here and
have bhk_autounpack import them; for now the dependency points this way to avoid
disturbing the tested collision path.)
"""

# Dual-mode import so this works both inside the addon package and when a caller
# is run as a standalone script from the pyn/ directory.
try:
    from .bhk_autounpack import (
        u8, u16, u32, i32, u64, f32, vec3, vec4,
        trunc_f16_decode, quat_to_matrix, mat3_mul,
        SectionHdr,
        parse_local_fixups, parse_virtual_fixups, parse_global_fixups,
        hkarray_abs, hkarray_size,
    )
except ImportError:
    from bhk_autounpack import (
        u8, u16, u32, i32, u64, f32, vec3, vec4,
        trunc_f16_decode, quat_to_matrix, mat3_mul,
        SectionHdr,
        parse_local_fixups, parse_virtual_fixups, parse_global_fixups,
        hkarray_abs, hkarray_size,
    )

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


PACKFILE_MAGIC0 = 0x57E0E057
PACKFILE_MAGIC1 = 0x10C0C010

# Section tags always present, in file order.
SECTION_TAGS = ("__classnames__", "__types__", "__data__")

# Section-header field layout (relative to the tag/base), matching the layout
# bhk_autounpack assumes: name at +0x00, then the offsets below. Each header is
# 0x40 bytes; only the *start* of the run varies between blobs.
_SH_ABS_START = 0x14
_SH_LOCAL = 0x18
_SH_GLOBAL = 0x1C
_SH_VIRTUAL = 0x20
_SH_EXPORTS = 0x24
_SH_END = 0x2C


def is_havok_packfile(data: bytes) -> bool:
    """True if data begins with the hk packfile magic."""
    return len(data) >= 8 and u32(data, 0) == PACKFILE_MAGIC0 \
        and u32(data, 4) == PACKFILE_MAGIC1


def packfile_version(data: bytes) -> str:
    """Return the contents-version string (e.g. 'hk_2014.1.0-r1')."""
    # Null-terminated string living in the header; search a bounded window.
    start = 0x28
    end = data.index(b"\x00", start, start + 64) if b"\x00" in data[start:start + 64] else start
    return data[start:end].decode("ascii", errors="replace")


def parse_section_headers(data: bytes) -> Dict[str, SectionHdr]:
    """Locate the three packfile sections by scanning for their tag strings.

    Robust to the header-size variation (version-string length) that fixes the
    section-header run at 0x40 in some blobs and 0x50 in others. Field offsets
    within each 0x40-byte header match bhk_autounpack's layout.
    """
    hdrs: Dict[str, SectionHdr] = {}
    for tag in SECTION_TAGS:
        token = tag.encode("ascii")
        base = data.find(token)
        if base < 0:
            continue
        s = u32(data, base + _SH_ABS_START)
        hdrs[tag] = SectionHdr(
            name=tag, abs_start=s,
            local_fix=s + u32(data, base + _SH_LOCAL),
            global_fix=s + u32(data, base + _SH_GLOBAL),
            virt_fix=s + u32(data, base + _SH_VIRTUAL),
            exports=s + u32(data, base + _SH_EXPORTS),
            end=s + u32(data, base + _SH_END),
        )
    return hdrs


@dataclass
class HkObject:
    """One object in __data__: its class name and offsets."""
    index: int
    class_name: str
    rel: int            # offset within __data__ section
    abs_off: int        # absolute file offset
    size: int = 0       # bytes to the next object (or section end)


@dataclass
class HavokPackfile:
    """Parsed container: sections, fixup tables, and the object inventory.

    Use the helpers to resolve pointers and hkArray fields in `data`:
      * `ptr(obj_rel, field_off)` -> absolute offset the pointer at that field
        points to (via the local fixup table), or None if unset.
      * `array(obj_rel, field_off)` -> (abs_offset, count) for an hkArray<T>.
      * `gptr(obj_rel, field_off)` -> (section_index, dst_rel) global fixup.
    """
    data: bytes
    hdrs: Dict[str, SectionHdr]
    data_start: int
    cn_start: int
    local: Dict[int, int] = field(default_factory=dict)
    glob: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    objects: List[HkObject] = field(default_factory=list)

    def ptr(self, obj_rel: int, field_off: int) -> Optional[int]:
        """Absolute offset a pointer field points to (local fixup), or None."""
        dst = self.local.get(obj_rel + field_off)
        return (self.data_start + dst) if dst is not None else None

    def gptr(self, obj_rel: int, field_off: int) -> Optional[Tuple[int, int]]:
        """(dst_section_index, dst_rel) for a global (cross-section) pointer."""
        return self.glob.get(obj_rel + field_off)

    def array(self, obj_rel: int, field_off: int) -> Tuple[Optional[int], int]:
        """Resolve an hkArray<T> field: (abs_offset_or_None, count)."""
        abs_off = hkarray_abs(self.local, self.data_start, obj_rel, field_off)
        count = hkarray_size(self.data, self.data_start + obj_rel, field_off)
        return abs_off, count

    def cstr(self, abs_off: Optional[int], limit: int = 256) -> str:
        """Read a NUL-terminated ASCII string at an absolute offset."""
        if abs_off is None or abs_off < 0 or abs_off >= len(self.data):
            return ""
        end = self.data.find(b"\x00", abs_off, abs_off + limit)
        if end < 0:
            end = min(abs_off + limit, len(self.data))
        return self.data[abs_off:end].decode("ascii", errors="replace")

    def objects_of(self, class_name: str) -> List[HkObject]:
        return [o for o in self.objects if o.class_name == class_name]


def parse_packfile(data: bytes) -> HavokPackfile:
    """Parse a Havok packfile blob into a HavokPackfile (sections + objects).

    Raises RuntimeError if the magic or required sections are missing.
    """
    if not is_havok_packfile(data):
        raise RuntimeError("Not a Havok packfile (bad magic).")
    hdrs = parse_section_headers(data)
    if "__data__" not in hdrs or "__classnames__" not in hdrs:
        raise RuntimeError("Missing __data__ or __classnames__ section.")

    data_hdr = hdrs["__data__"]
    data_start = data_hdr.abs_start
    cn_start = hdrs["__classnames__"].abs_start

    local = parse_local_fixups(data, data_hdr)
    glob = parse_global_fixups(data, data_hdr)
    raw_objs = parse_virtual_fixups(data, data_hdr, cn_start)  # [(rel, class_name)]

    # Sort by offset so we can compute each object's size as the gap to the next.
    raw_objs = sorted(raw_objs, key=lambda o: o[0])
    section_end_rel = data_hdr.local_fix - data_start  # __data__ payload ends here
    objects: List[HkObject] = []
    for i, (rel, cls) in enumerate(raw_objs):
        nxt = raw_objs[i + 1][0] if i + 1 < len(raw_objs) else section_end_rel
        objects.append(HkObject(index=i, class_name=cls, rel=rel,
                                 abs_off=data_start + rel, size=max(0, nxt - rel)))

    return HavokPackfile(data=data, hdrs=hdrs, data_start=data_start,
                         cn_start=cn_start, local=local, glob=glob, objects=objects)


def classnames(data: bytes) -> List[str]:
    """All class names declared in the __classnames__ section (for reference)."""
    hdrs = parse_section_headers(data)
    if "__classnames__" not in hdrs:
        return []
    cn = hdrs["__classnames__"]
    out: List[str] = []
    pos = cn.abs_start
    end = min(cn.end, len(data))
    # Entries are: u32 signature, u8 separator(0x09), NUL-terminated name.
    while pos + 5 < end:
        # Skip the 4-byte signature + 1 separator byte, then read the name.
        name_start = pos + 5
        z = data.find(b"\x00", name_start, end)
        if z < 0:
            break
        name = data[name_start:z].decode("ascii", errors="replace")
        if name:
            out.append(name)
        pos = z + 1
        # Skip any padding NULs between entries.
        while pos < end and data[pos] == 0:
            pos += 1
    return out
