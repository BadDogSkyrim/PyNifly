#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anim_skyrim.py — Read/write Skyrim LE/SE hkaSplineCompressedAnimation data.

No Blender dependencies.  Can be run standalone:

    python anim_skyrim.py <file.hkx>       # binary HKX (hk_2010, 32-bit)
    python anim_skyrim.py <file.xml>       # hkpackfile XML skeleton

Skyrim HKX files use Havok hk_2010.2.0-r1 packfile format with 32-bit pointers.
The spline compression data itself is identical to FO4 — only the container
structs differ (4-byte pointers, 12-byte hkArrays).

Based on format analysis of Skyrim LE .hkx files and the FO4 implementation
in anim_fo4.py.  Spline decompression from Dagobaking's
skyrim-fo4-animation-conversion (itself based on PredatorCZ/HavokLib, GPL-3.0).
"""

import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Shared code from the FO4 module — data structures, spline decompression,
# quaternion encoding, B-spline fitting, XML parsing are all identical.
try:
    from .anim_fo4 import (
        AnimationData, Annotation, BonePose, Skeleton, TrackData,
        _decompress_spline, _parse_skeleton_xml, _parse_animation_xml,
        _read_null_string,
        _compress_all_blocks, _write_48bit_quat, _write_16bit_scalar,
        _write_8bit_scalar, _FixupBuilder,
        _w_u8, _w_u16, _w_u32, _w_i16, _w_f32,
        _pad16, _pad4, _hkarray, _align,
    )
except ImportError:
    from anim_fo4 import (
        AnimationData, Annotation, BonePose, Skeleton, TrackData,
        _decompress_spline, _parse_skeleton_xml, _parse_animation_xml,
        _read_null_string,
        _compress_all_blocks, _write_48bit_quat, _write_16bit_scalar,
        _write_8bit_scalar, _FixupBuilder,
        _w_u8, _w_u16, _w_u32, _w_i16, _w_f32,
        _pad16, _pad4, _hkarray, _align,
    )

import xml.etree.ElementTree as ET


# ═══════════════════════════════════════════════════════════════════════════════
#  Binary HKX reader — Skyrim (hk_2010.2.0-r1, 32-bit pointers)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Packfile layout differences from FO4 (hk_2014, 64-bit):
#
#    - File header: version 8 (not 11), layoutRules byte 0 = 4 (not 8)
#    - No padding block between file header and section headers
#    - Section headers are 0x30 bytes each (not 0x40)
#    - Sections start at 0x40 (not 0x50)
#    - Pointers are 4 bytes (not 8)
#    - hkArray is 12 bytes: ptr(4) + size(4) + capacityAndFlags(4)
#      (FO4: ptr(8) + size(4) + cap(4) = 16 bytes)
#
#  hkaSplineCompressedAnimation struct (32-bit, hk_2010):
#    +0x00  vtable ptr             (4, zeros in file)
#    +0x04  memSizeAndFlags        (4)
#    +0x08  type                   (4, enum — 5 = SPLINE_COMPRESSED in hk_2010)
#    +0x0C  duration               (4, float)
#    +0x10  numberOfTransformTracks (4)
#    +0x14  numberOfFloatTracks    (4)
#    +0x18  extractedMotion        (4, pointer)
#    +0x1C  annotationTracks       (12, hkArray<hkaAnnotationTrack>)
#    +0x28  numFrames              (4)
#    +0x2C  numBlocks              (4)
#    +0x30  maxFramesPerBlock      (4)
#    +0x34  maskAndQuantizationSize (4)
#    +0x38  blockDuration          (4, float)
#    +0x3C  blockInverseDuration   (4, float)
#    +0x40  frameDuration          (4, float)
#    +0x44  blockOffsets           (12, hkArray<u32>)
#    +0x50  floatBlockOffsets      (12, hkArray<u32>)
#    +0x5C  transformOffsets       (12, hkArray<u32>)
#    +0x68  floatOffsets           (12, hkArray<u32>)
#    +0x74  data                   (12, hkArray<u8>)
#
#  hkaAnnotationTrack (32-bit, 0x10 bytes):
#    +0x00  trackName              (4, string pointer)
#    +0x04  annotations            (12, hkArray<hkaAnnotation>)
#
#  hkaAnnotation (32-bit, 0x08 bytes):
#    +0x00  time                   (4, float)
#    +0x04  text                   (4, string pointer)
#
#  hkaAnimationBinding (32-bit):
#    +0x00  vtable ptr             (4)
#    +0x04  memSizeAndFlags        (4)
#    +0x08  originalSkeletonName   (4, string pointer)
#    +0x0C  animation              (4, pointer)
#    +0x10  transformTrackToBoneIndices (12, hkArray<int16>)
#    +0x1C  floatTrackToFloatSlotIndices (12, hkArray<int16>)
#    +0x28  blendHint              (4, int32)
#
#  hkArray layout (32-bit, 12 bytes):
#    +0x00  data pointer           (4, resolved via local fixups)
#    +0x04  size                   (4, int32)
#    +0x08  capacityAndFlags       (4, int32 — high bit = owned flag)
#
#  hkaSkeleton (32-bit):
#    +0x00  vtable ptr             (4)
#    +0x04  memSizeAndFlags        (4)
#    +0x08  name                   (4, string pointer)
#    +0x0C  parentIndices          (12, hkArray<int16>)
#    +0x18  bones                  (12, hkArray<hkaBone>)
#    +0x24  referencePose          (12, hkArray<hkQsTransform>)
#
#  hkaBone (32-bit, 0x08 bytes):
#    +0x00  name                   (4, string pointer)
#    +0x04  lockTranslation        (4, int32)
#
#  hkQsTransform (0x30 bytes, same as 64-bit — SIMD-aligned):
#    +0x00  translation            (16 bytes: 3 floats + pad)
#    +0x10  rotation               (16 bytes: 4 floats xyzw)
#    +0x20  scale                  (16 bytes: 3 floats + pad)

_HKX_MAGIC = b'\x57\xe0\xe0\x57'

# Section header starts immediately after file header (0x40), no padding.
_SEC_HDR_START = 0x40
_SEC_HDR_SIZE = 0x30


def _u32(data, off):
    return struct.unpack_from('<I', data, off)[0]

def _i32(data, off):
    return struct.unpack_from('<i', data, off)[0]

def _f32(data, off):
    return struct.unpack_from('<f', data, off)[0]


# ── Section parsing ──────────────────────────────────────────────────────────

def _parse_hkx_sections(data):
    """Parse v8 packfile section headers (32-bit, hk_2010).

    Section headers are 0x30 bytes each, starting at file offset 0x40.
    Layout per header:
      +0x00  name              (16 bytes, null-terminated)
      +0x10  marker            (4 bytes)
      +0x14  abs_data_start    (4 bytes, absolute file offset)
      +0x18  local_fixup_off   (relative to abs_data_start)
      +0x1C  global_fixup_off
      +0x20  virtual_fixup_off
      +0x24  exports_off
      +0x28  imports_off
      +0x2C  end_off
    """
    sections = {}
    for i in range(3):
        base = _SEC_HDR_START + i * _SEC_HDR_SIZE
        name = data[base:base + 16].split(b'\x00')[0].decode('ascii', errors='replace')
        s = _u32(data, base + 0x14)
        sections[name] = {
            'offset': s,
            'data1': s + _u32(data, base + 0x18),   # local fixups
            'data2': s + _u32(data, base + 0x1C),   # global fixups
            'data3': s + _u32(data, base + 0x20),   # virtual fixups
            'exports': s + _u32(data, base + 0x24),
            'end':   s + _u32(data, base + 0x2C),
        }
    return sections


def _parse_local_fixups(data, sec):
    """Parse local fixup table: src_rel -> dst_rel within __data__."""
    fixups = {}
    pos = sec['data1']
    end = sec['data2']
    while pos + 8 <= end:
        src = _u32(data, pos)
        dst = _u32(data, pos + 4)
        if src == 0xFFFFFFFF:
            break
        fixups[src] = dst
        pos += 8
    return fixups


def _parse_virtual_fixups(data, sec, cn_start):
    """Parse virtual fixup table: returns [(rel_offset, class_name)]."""
    objects = []
    pos = sec['data3']
    end = sec['exports']
    while pos + 12 <= end:
        src = _u32(data, pos)
        _u32(data, pos + 4)  # section index
        name_off = _u32(data, pos + 8)
        if src == 0xFFFFFFFF:
            break
        abs_name = cn_start + name_off
        try:
            ne = data.index(b'\x00', abs_name, abs_name + 256)
            cls = data[abs_name:ne].decode('ascii', errors='replace')
        except ValueError:
            cls = f'?{name_off:#x}'
        objects.append((src, cls))
        pos += 12
    return objects


# ── hkArray helpers (32-bit: ptr=4, size at +4) ─────────────────────────────

def _read_hkarray_u32(data, data_abs, obj_rel, field_off, fixups, ptr_size=4):
    """Read hkArray<uint32> from a packfile."""
    arr_rel = obj_rel + field_off
    count = _u32(data, data_abs + arr_rel + ptr_size)  # size after pointer
    if count == 0:
        return []
    content_rel = fixups.get(arr_rel)
    if content_rel is None:
        return []
    content_abs = data_abs + content_rel
    return [_u32(data, content_abs + i * 4) for i in range(count)]


def _read_hkarray_u8(data, data_abs, obj_rel, field_off, fixups, ptr_size=4):
    """Read hkArray<uint8> from a packfile."""
    arr_rel = obj_rel + field_off
    count = _u32(data, data_abs + arr_rel + ptr_size)
    if count == 0:
        return b''
    content_rel = fixups.get(arr_rel)
    if content_rel is None:
        return b''
    content_abs = data_abs + content_rel
    return data[content_abs:content_abs + count]


# ── Animation parser ─────────────────────────────────────────────────────────

def _parse_animation_hkx(data) -> Optional[AnimationData]:
    """Parse hkaSplineCompressedAnimation from a Skyrim binary HKX file.

    Handles both 4-byte (LE) and 8-byte (SE) pointer packfiles.
    """
    if data[:4] != _HKX_MAGIC:
        return None

    ptr_size = data[0x10]  # 4 (LE) or 8 (SE)

    sections = _parse_hkx_sections(data)
    cn_sec = sections.get('__classnames__')
    data_sec = sections.get('__data__')
    if not cn_sec or not data_sec:
        return None

    cn_start = cn_sec['offset']
    data_abs = data_sec['offset']

    fixups = _parse_local_fixups(data, data_sec)
    objects = _parse_virtual_fixups(data, data_sec, cn_start)

    # Find hkaSplineCompressedAnimation
    anim_rel = None
    for rel, cls in objects:
        if cls == 'hkaSplineCompressedAnimation':
            anim_rel = rel
            break
    if anim_rel is None:
        return None

    a = data_abs + anim_rel
    anim = AnimationData()

    # ── Compute struct offsets based on pointer size ──
    # hkReferencedObject base: vtable(ptr) + refcount, padded to 2*ptr_size
    base = 2 * ptr_size
    # hkaAnimation members (ints/floats pack tightly after base):
    #   type(4) + duration(4) + numTransformTracks(4) + numFloatTracks(4)
    #   extractedMotion(ptr) + annotationTracks(hkArray)
    arr_size = ptr_size + 8   # hkArray = ptr + count(4) + cap(4)
    o_type = base
    o_duration = base + 4
    o_num_tracks = base + 8
    o_num_float_tracks = base + 12
    o_extracted_motion = base + 16
    o_ann_tracks = o_extracted_motion + ptr_size
    # hkaSplineCompressedAnimation members (after base class):
    spline_base = o_ann_tracks + arr_size
    o_num_frames = spline_base
    o_num_blocks = spline_base + 4
    o_max_frames = spline_base + 8
    o_mask_quant = spline_base + 12
    o_block_dur = spline_base + 16
    # blockInverseDuration (4 bytes) then frameDuration
    o_frame_dur = spline_base + 24
    # Align to ptr_size before first array field (pointer needs alignment)
    o_block_offsets = (spline_base + 28 + ptr_size - 1) & ~(ptr_size - 1)
    o_float_block_offsets = o_block_offsets + arr_size
    o_transform_offsets = o_float_block_offsets + arr_size
    o_float_offsets = o_transform_offsets + arr_size
    o_data = o_float_offsets + arr_size

    anim.duration = _f32(data, a + o_duration)
    anim.num_tracks = _u32(data, a + o_num_tracks)
    num_float_tracks = _u32(data, a + o_num_float_tracks)
    anim.num_frames = _u32(data, a + o_num_frames)
    anim.num_blocks = _u32(data, a + o_num_blocks)
    anim.max_frames_per_block = _u32(data, a + o_max_frames)
    mask_and_quant_size = _u32(data, a + o_mask_quant)
    anim.block_duration = _f32(data, a + o_block_dur)
    anim.frame_duration = _f32(data, a + o_frame_dur)

    block_offsets = _read_hkarray_u32(data, data_abs, anim_rel, o_block_offsets, fixups, ptr_size)
    data_blob = _read_hkarray_u8(data, data_abs, anim_rel, o_data, fixups, ptr_size)

    if not data_blob or not block_offsets:
        return None

    # ── Parse annotation tracks (bone names) ──
    ann_arr_rel = anim_rel + o_ann_tracks
    ann_count = _u32(data, data_abs + ann_arr_rel + ptr_size)
    ann_content_rel = fixups.get(ann_arr_rel)

    if ann_content_rel is not None and ann_count > 0:
        # hkaAnnotationTrack: string ptr + hkArray = ptr_size + arr_size
        ANNTRACK_STRIDE = ptr_size + arr_size
        for i in range(ann_count):
            track_rel = ann_content_rel + i * ANNTRACK_STRIDE
            str_target_rel = fixups.get(track_rel)
            if str_target_rel is not None:
                name = _read_null_string(data, data_abs + str_target_rel)
                anim.bone_names.append(name)
            else:
                anim.bone_names.append('')

            # Annotation events hkArray within the track (at +ptr_size)
            ann_events_rel = track_rel + ptr_size
            ann_events_count = _u32(data, data_abs + ann_events_rel + ptr_size)
            ann_events_content_rel = fixups.get(ann_events_rel)
            if ann_events_content_rel is not None and ann_events_count > 0:
                # hkaAnnotation: float time(4) + pad(ptr_size-4) + string ptr(ptr_size)
                EVT_STRIDE = ptr_size + ptr_size  # time(4)+pad + ptr
                for j in range(ann_events_count):
                    evt_rel = ann_events_content_rel + j * EVT_STRIDE
                    evt_time = _f32(data, data_abs + evt_rel)
                    evt_str_rel = fixups.get(evt_rel + ptr_size)
                    evt_text = ''
                    if evt_str_rel is not None:
                        evt_text = _read_null_string(data, data_abs + evt_str_rel)
                    anim.annotations.append(Annotation(time=evt_time, text=evt_text))

    # ── Parse hkaAnimationBinding ──
    # Layout: base(2*ptr) + originalSkeletonName(ptr) + animation(ptr)
    #         + transformTrackToBoneIndices(arr) + floatTrackToFloatSlotIndices(arr)
    #         + blendHint(4)
    bind_name_off = 2 * ptr_size
    bind_anim_off = bind_name_off + ptr_size
    bind_idx_off = bind_anim_off + ptr_size

    for rel, cls in objects:
        if cls == 'hkaAnimationBinding':
            skel_name_rel = fixups.get(rel + bind_name_off)
            if skel_name_rel is not None:
                anim.original_skeleton_name = _read_null_string(data, data_abs + skel_name_rel)
            idx_arr_rel = rel + bind_idx_off
            idx_count = _u32(data, data_abs + idx_arr_rel + ptr_size)
            idx_content_rel = fixups.get(idx_arr_rel)
            if idx_content_rel is not None and idx_count > 0:
                idx_abs = data_abs + idx_content_rel
                anim.track_to_bone_indices = [
                    struct.unpack_from('<h', data, idx_abs + i * 2)[0]
                    for i in range(idx_count)
                ]
            # blendHint follows the two hkArray fields
            arr_sz = ptr_size + 4 + 4  # hkArray: ptr + size + capacityAndFlags
            blend_hint_off = bind_idx_off + 2 * arr_sz
            anim.blend_hint = _u32(data, data_abs + rel + blend_hint_off)
            break

    # ── Decompress spline data ──
    anim.tracks = _decompress_spline(
        data_blob, anim.num_tracks, anim.num_frames,
        anim.num_blocks, anim.max_frames_per_block, block_offsets,
        mask_and_quant_size
    )

    return anim


# ── Skeleton parser (binary, 32-bit) ─────────────────────────────────────────

def _parse_skeleton_hkx(data: bytes) -> Optional[Skeleton]:
    """Parse hkaSkeleton from a Skyrim binary HKX file.

    Handles both 4-byte and 8-byte pointer packfiles (byte 0x10 of header).
    Animations typically use 4-byte ptrs; vanilla skeleton.hkx uses 8-byte.
    """
    if data[:4] != _HKX_MAGIC:
        return None

    ptr_size = data[0x10]  # 4 or 8

    sections = _parse_hkx_sections(data)
    cn_sec = sections.get('__classnames__')
    data_sec = sections.get('__data__')
    if not cn_sec or not data_sec:
        return None

    cn_start = cn_sec['offset']
    data_abs = data_sec['offset']

    fixups = _parse_local_fixups(data, data_sec)
    objects = _parse_virtual_fixups(data, data_sec, cn_start)

    # Find hkaSkeleton
    skel_rel = None
    for rel, cls in objects:
        if cls == 'hkaSkeleton':
            skel_rel = rel
            break
    if skel_rel is None:
        return None

    s = data_abs + skel_rel
    skel = Skeleton()

    # hkaSkeleton layout depends on pointer size.
    # hkReferencedObject base: vtable(ptr_size) + refcount(4), padded to 2*ptr_size.
    # Then: name(ptr_size), parentIndices(hkArray), bones(hkArray), referencePose(hkArray)
    # hkArray: ptr(ptr_size) + count(4) + capFlags(4), padded to ptr_size alignment.
    base_size = 2 * ptr_size  # hkReferencedObject padded
    arr_size = ptr_size + 8   # hkArray: ptr + count + cap (no extra padding needed)
    # But count is at ptr_size offset within the array
    count_off = ptr_size  # offset of count within an hkArray

    name_off = base_size
    pi_off = name_off + ptr_size  # parentIndices array
    bones_off = pi_off + arr_size  # bones array
    pose_off = bones_off + arr_size  # referencePose array

    # Name
    name_target = fixups.get(skel_rel + name_off)
    if name_target is not None:
        skel.name = _read_null_string(data, data_abs + name_target)

    # parentIndices (hkArray<int16>)
    pi_count = _u32(data, s + pi_off + count_off)
    pi_content = fixups.get(skel_rel + pi_off)
    if pi_content is not None and pi_count > 0:
        pi_abs = data_abs + pi_content
        skel.parents = [
            struct.unpack_from('<h', data, pi_abs + i * 2)[0]
            for i in range(pi_count)
        ]

    # bones (hkArray<hkaBone>)
    # hkaBone: name ptr (ptr_size) + lockTranslation (4), padded
    bone_stride = ptr_size + 4
    if ptr_size == 8:
        bone_stride = 16  # 8-byte aligned
    bone_count = _u32(data, s + bones_off + count_off)
    bone_content = fixups.get(skel_rel + bones_off)
    if bone_content is not None and bone_count > 0:
        for i in range(bone_count):
            bone_rel = bone_content + i * bone_stride
            str_target = fixups.get(bone_rel)
            if str_target is not None:
                skel.bones.append(_read_null_string(data, data_abs + str_target))
            else:
                skel.bones.append('')

    # referencePose (hkArray<hkQsTransform>)
    # hkQsTransform is 0x30 bytes (same regardless of pointer size)
    pose_count = _u32(data, s + pose_off + count_off)
    pose_content = fixups.get(skel_rel + pose_off)
    if pose_content is not None and pose_count > 0:
        POSE_STRIDE = 0x30
        for i in range(pose_count):
            p = data_abs + pose_content + i * POSE_STRIDE
            tx, ty, tz = _f32(data, p), _f32(data, p+4), _f32(data, p+8)
            rx, ry, rz, rw = _f32(data, p+16), _f32(data, p+20), _f32(data, p+24), _f32(data, p+28)
            sx, sy, sz = _f32(data, p+32), _f32(data, p+36), _f32(data, p+40)
            skel.reference_pose.append(BonePose([tx, ty, tz], [rx, ry, rz, rw], [sx, sy, sz]))

    return skel


# ═══════════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════════

def is_skyrim_hkx(filepath: str) -> bool:
    """Return True if filepath is a Skyrim (hk_2010) binary HKX file or
    an XML hkpackfile containing a skeleton (used by Skyrim)."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(0x38)
        if len(header) < 0x38:
            # Could be an XML file — check for hkpackfile tag
            return _is_hkpackfile_xml(filepath)
        if header[:4] != _HKX_MAGIC:
            return _is_hkpackfile_xml(filepath)
        version = struct.unpack_from('<I', header, 0x0C)[0]
        if version not in (8, 9, 10):  # hk_2010 uses version 8
            return False
        contents = header[0x28:0x38].split(b'\x00')[0].decode('ascii', errors='replace')
        return contents.startswith('hk_2010')
    except (OSError, IOError):
        return False


def _is_hkpackfile_xml(filepath: str) -> bool:
    """Return True if filepath is an XML hkpackfile (e.g. Skyrim skeleton.hkx)."""
    try:
        with open(filepath, 'rb') as f:
            head = f.read(256)
        return b'<hkpackfile' in head
    except (OSError, IOError):
        return False


def load_skyrim_animation(filepath: str) -> AnimationData:
    """Load a Skyrim animation from a binary HKX or hkpackfile XML.

    Parameters
    ----------
    filepath : str
        Path to a .hkx (binary) or .xml (hkpackfile) file.

    Returns
    -------
    AnimationData with fully decompressed tracks.

    Raises
    ------
    ValueError  if the file cannot be parsed.
    """
    filepath = str(filepath)

    with open(filepath, 'rb') as f:
        raw = f.read()

    # Binary HKX
    if raw[:4] == _HKX_MAGIC:
        anim = _parse_animation_hkx(raw)
        if anim is None:
            raise ValueError("No hkaSplineCompressedAnimation found in HKX file.")
        return anim

    # Try XML (hkpackfile format — e.g. from hkxpack-cli)
    if ET is not None and (raw[:5] == b'<?xml' or raw[:1] == b'<'):
        try:
            tree = ET.parse(filepath)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {e}")

        root = tree.getroot()
        if root.tag != 'hkpackfile':
            raise ValueError(f"Expected hkpackfile XML, got <{root.tag}>.")

        anim = _parse_animation_xml(root)
        if anim is None:
            raise ValueError("No hkaSplineCompressedAnimation found in XML.")
        return anim

    raise ValueError(f"Unrecognized file format (not HKX binary or XML).")


def load_skyrim_skeleton(filepath: str) -> Optional[Skeleton]:
    """Load a Skyrim skeleton from a binary HKX or hkpackfile XML file.

    Returns Skeleton or None if no hkaSkeleton found.
    """
    filepath = str(filepath)
    with open(filepath, 'rb') as f:
        raw = f.read()

    if raw[:4] == _HKX_MAGIC:
        return _parse_skeleton_hkx(raw)

    # Try XML
    if ET is not None and (raw[:5] == b'<?xml' or raw[:1] == b'<'):
        try:
            tree = ET.parse(filepath)
        except ET.ParseError:
            return None
        root = tree.getroot()
        if root.tag == 'hkpackfile':
            return _parse_skeleton_xml(root)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: HKX packfile writer (hk_2010, 32-bit)
# ═══════════════════════════════════════════════════════════════════════════════

# Class name hashes for hk_2010 classnames section.
# These differ from FO4 (hk_2014) hashes.
_ANIM_CLASS_ENTRIES_V8: List[Tuple[int, str]] = [
    (0x75585EF6, 'hkClass'),
    (0x7EA4C2A4, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0x2772C11E, 'hkRootLevelContainer'),
    (0x26859F4C, 'hkaAnimationContainer'),
    (0x792EE0BB, 'hkaSplineCompressedAnimation'),
    (0xB8E0F860, 'hkaDefaultAnimatedReferenceFrame'),
    (0x66EAC971, 'hkaAnimationBinding'),
    (0x1DE13A73, 'hkMemoryResourceContainer'),
]


def _w_u32_32(v: int) -> bytes:
    """Write a 32-bit pointer (4 bytes, placeholder for fixup)."""
    return struct.pack('<I', v & 0xFFFFFFFF)


def _hkarray32(count: int) -> bytes:
    """Write an hkArray header for 32-bit: ptr(4) + size(4) + cap(4) = 12 bytes."""
    cap = (count | 0x80000000) if count > 0 else 0x80000000
    return _w_u32(0) + _w_u32(count) + _w_u32(cap)


def _hkarray(count: int, ptr_size: int) -> bytes:
    """Write an hkArray header: ptr(ptr_size) + size(4) + cap(4)."""
    cap = (count | 0x80000000) if count > 0 else 0x80000000
    return bytes(ptr_size) + _w_u32(count) + _w_u32(cap)


def _ptr(ptr_size: int) -> bytes:
    """Write a null pointer placeholder of the given size."""
    return bytes(ptr_size)


def _build_anim_classnames_v8() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section for a Skyrim animation HKX."""
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in _ANIM_CLASS_ENTRIES_V8:
        name_offs[name] = len(data) + 5
        data += struct.pack('<IB', hash_val, 0x09) + name.encode('ascii') + b'\x00'
    data = _pad16(data, fill=0xFF)
    return data, name_offs


def _skyrim_file_header(cn_name_off: int, ptr_size: int = 4) -> bytes:
    """Build the 0x40-byte file header for a Skyrim HKX."""
    hdr = bytearray(0x40)
    hdr[0x00:0x04] = _HKX_MAGIC
    hdr[0x04:0x08] = b'\x10\xc0\xc0\x10'
    struct.pack_into('<i', hdr, 0x08, 0)          # userTag
    struct.pack_into('<i', hdr, 0x0C, 8)           # fileVersion = 8
    hdr[0x10] = ptr_size                           # pointer size (4=LE, 8=SE)
    hdr[0x11:0x14] = b'\x01\x00\x01'              # littleEndian, reusePadding, emptyBaseClass
    struct.pack_into('<i', hdr, 0x14, 3)           # numSections
    struct.pack_into('<i', hdr, 0x18, 2)           # contentsSectionIndex
    struct.pack_into('<i', hdr, 0x1C, 0)           # contentsSectionOffset
    struct.pack_into('<i', hdr, 0x20, 0)           # contentsClassNameSectionIndex
    struct.pack_into('<i', hdr, 0x24, cn_name_off) # contentsClassNameSectionOffset
    hdr[0x28:0x38] = b'hk_2010.2.0-r1\x00\xff'
    struct.pack_into('<i', hdr, 0x38, 0)           # flags
    struct.pack_into('<i', hdr, 0x3C, -1)          # maxPredicate = 0xFFFFFFFF
    return bytes(hdr)


def _skyrim_section_header(name: str, abs_start: int,
                           local_fix: int, global_fix: int,
                           virt_fix: int, exports: int) -> bytes:
    """Build a 0x30-byte section header for Skyrim HKX."""
    hdr = bytearray(_SEC_HDR_SIZE)
    name_b = name.encode('ascii') + b'\x00'
    hdr[:len(name_b)] = name_b
    for i in range(len(name_b), 0x14):
        hdr[i] = 0xFF
    struct.pack_into('<I', hdr, 0x14, abs_start)
    struct.pack_into('<I', hdr, 0x18, local_fix - abs_start)
    struct.pack_into('<I', hdr, 0x1C, global_fix - abs_start)
    struct.pack_into('<I', hdr, 0x20, virt_fix - abs_start)
    struct.pack_into('<I', hdr, 0x24, exports - abs_start)
    struct.pack_into('<I', hdr, 0x28, exports - abs_start)  # imports
    struct.pack_into('<I', hdr, 0x2C, exports - abs_start)  # end
    return bytes(hdr)


def _build_anim_data_section(anim: AnimationData,
                              name_offs: Dict[str, int],
                              ptr_size: int = 4) -> Tuple[bytes, '_FixupBuilder']:
    """Build __data__ section for a Skyrim animation HKX.

    ptr_size=4 for LE (32-bit), ptr_size=8 for SE (64-bit).
    """
    P = ptr_size
    arr_sz = P + 8  # hkArray: ptr + count(4) + cap(4)
    base_sz = 2 * P  # hkReferencedObject: vtable(P) + refcount, padded to 2*P

    fx = _FixupBuilder()
    data = bytearray()

    def rel():
        return len(data)

    def write(b):
        off = len(data)
        data.extend(b)
        return off

    def write_string(s: str) -> int:
        off = rel()
        data.extend(s.encode('ascii') + b'\x00')
        return off

    def align16():
        while len(data) % 16:
            data.append(0)

    def align_to(n):
        while len(data) % n:
            data.append(0)

    def write_arr(count):
        return write(_hkarray(count, P))

    def write_ptr():
        return write(_ptr(P))

    def pack_arr_at(buf, off, count):
        """Pack hkArray count+cap into a bytearray at offset (ptr is zeroed)."""
        struct.pack_into('<I', buf, off + P, count)
        struct.pack_into('<I', buf, off + P + 4, count | 0x80000000)

    # Compress animation
    spline_blob, block_offsets = _compress_all_blocks(anim)

    num_tracks = anim.num_tracks
    bone_names = anim.bone_names or [f"Bone{i}" for i in range(num_tracks)]
    skel_name = anim.original_skeleton_name or "Root"
    binding_indices = anim.track_to_bone_indices or list(range(num_tracks))

    # ═══ hkRootLevelContainer ═══
    rlc_rel = rel()
    fx.add_virtual(rlc_rel, 0, name_offs['hkRootLevelContainer'])
    arr_rlc = write_arr(2)
    align16()

    # namedVariant data: 2 entries, each 3*P bytes (name_ptr + class_ptr + variant_ptr)
    nv_data_rel = rel()
    fx.add_local(arr_rlc, nv_data_rel)
    nv0_name = write_ptr()
    nv0_class = write_ptr()
    nv0_variant = write_ptr()
    nv1_name = write_ptr()
    nv1_class = write_ptr()
    nv1_variant = write_ptr()
    align16()

    # Variant strings
    nv0_name_str = rel()
    write_string("Merged Animation Container")
    align_to(2)
    nv0_class_str = rel()
    write_string("hkaAnimationContainer")
    align_to(2)
    nv1_name_str = rel()
    write_string("Resource Data")
    align_to(2)
    nv1_class_str = rel()
    write_string("hkMemoryResourceContainer")
    align16()

    fx.add_local(nv0_name, nv0_name_str)
    fx.add_local(nv0_class, nv0_class_str)
    fx.add_local(nv1_name, nv1_name_str)
    fx.add_local(nv1_class, nv1_class_str)

    # ═══ hkaAnimationContainer ═══
    ac_rel = rel()
    fx.add_virtual(ac_rel, 0, name_offs['hkaAnimationContainer'])
    fx.add_local(nv0_variant, ac_rel)

    write(bytes(base_sz))              # vtable + memSizeAndFlags
    write_arr(0)                       # skeletons
    arr_anims = write_arr(1)           # animations
    arr_binds = write_arr(1)           # bindings
    write_arr(0)                       # attachments
    write_arr(0)                       # skins
    align16()

    # Animation pointer array (1 entry)
    anim_ptr_array_rel = rel()
    fx.add_local(arr_anims, anim_ptr_array_rel)
    anim_ptr = write_ptr()

    # Binding pointer array (1 entry)
    bind_ptr_array_rel = rel()
    fx.add_local(arr_binds, bind_ptr_array_rel)
    bind_ptr = write_ptr()
    align16()

    # ═══ hkaSplineCompressedAnimation ═══
    # Compute struct offsets (same logic as reader)
    o_type = base_sz
    o_duration = base_sz + 4
    o_num_tracks = base_sz + 8
    o_num_float = base_sz + 12
    o_extr_motion = base_sz + 16
    o_ann_tracks = o_extr_motion + P
    spline_base = o_ann_tracks + arr_sz
    o_num_frames = spline_base
    o_num_blocks = spline_base + 4
    o_max_frames = spline_base + 8
    o_mask_quant = spline_base + 12
    o_block_dur = spline_base + 16
    o_block_inv = spline_base + 20
    o_frame_dur = spline_base + 24
    o_block_offsets = (spline_base + 28 + P - 1) & ~(P - 1)
    o_float_block_off = o_block_offsets + arr_sz
    o_transform_off = o_float_block_off + arr_sz
    o_float_off = o_transform_off + arr_sz
    o_data = o_float_off + arr_sz
    spline_struct_size = _align(o_data + arr_sz, 16)

    spline_rel = rel()
    fx.add_virtual(spline_rel, 0, name_offs['hkaSplineCompressedAnimation'])
    fx.add_local(anim_ptr, spline_rel)

    spline_hdr = bytearray(spline_struct_size)
    struct.pack_into('<I', spline_hdr, o_type, 5)  # SPLINE_COMPRESSED
    struct.pack_into('<f', spline_hdr, o_duration, anim.duration)
    struct.pack_into('<I', spline_hdr, o_num_tracks, num_tracks)
    struct.pack_into('<I', spline_hdr, o_num_float, 0)
    pack_arr_at(spline_hdr, o_ann_tracks, num_tracks)
    struct.pack_into('<I', spline_hdr, o_num_frames, anim.num_frames)
    n_blocks = anim.num_blocks or 1
    struct.pack_into('<I', spline_hdr, o_num_blocks, n_blocks)
    struct.pack_into('<I', spline_hdr, o_max_frames, anim.max_frames_per_block or 256)
    mask_size = _align(4 * num_tracks, 4)
    struct.pack_into('<I', spline_hdr, o_mask_quant, mask_size)
    struct.pack_into('<f', spline_hdr, o_block_dur, anim.block_duration)
    if anim.block_duration > 0:
        struct.pack_into('<f', spline_hdr, o_block_inv, 1.0 / anim.block_duration)
    struct.pack_into('<f', spline_hdr, o_frame_dur, anim.frame_duration)
    pack_arr_at(spline_hdr, o_block_offsets, n_blocks)
    pack_arr_at(spline_hdr, o_data, len(spline_blob))
    write(bytes(spline_hdr))

    # Annotation track structs: name_ptr(P) + hkArray(arr_sz) each
    # All annotation events go on track 0 (standard convention).
    ann_events = anim.annotations if anim.annotations else []
    anntrack_stride = P + arr_sz
    annot_tracks_rel = rel()
    fx.add_local(spline_rel + o_ann_tracks, annot_tracks_rel)
    annot_track_offsets = []
    for i in range(num_tracks):
        at_rel = rel()
        annot_track_offsets.append(at_rel)
        write_ptr()              # name ptr
        ann_count_for_track = len(ann_events) if i == 0 else 0
        write_arr(ann_count_for_track)

    # Annotation event arrays — track 0 events
    ann_events_data_rel = None
    ann_event_offsets = []  # relative offsets of each event's string ptr field
    if ann_events:
        ann_events_data_rel = rel()
        # hkaAnnotation: float time(4) + pad(P-4) + string ptr(P)
        EVT_STRIDE = P + P
        for evt in ann_events:
            evt_rel = rel()
            # time float + padding
            write(struct.pack('<f', evt.time))
            if P > 4:
                write(b'\x00' * (P - 4))
            # string ptr (placeholder)
            ann_event_offsets.append(rel())
            write_ptr()
        align16()

        # Fixup: track 0's annotation hkArray → event data
        fx.add_local(annot_track_offsets[0] + P, ann_events_data_rel)

    # Annotation event strings
    for i, evt in enumerate(ann_events):
        evt_str_rel = rel()
        write_string(evt.text or "")
        fx.add_local(ann_event_offsets[i], evt_str_rel)
    if ann_events:
        align16()

    # Annotation track name strings
    for i in range(num_tracks):
        name_str_rel = rel()
        name = bone_names[i] if i < len(bone_names) else ""
        write_string(name)
        fx.add_local(annot_track_offsets[i], name_str_rel)
    align16()

    # Block offsets array
    block_off_data_rel = rel()
    fx.add_local(spline_rel + o_block_offsets, block_off_data_rel)
    for bo in block_offsets:
        write(_w_u32(bo))
    align16()

    # Spline data blob
    spline_data_rel = rel()
    fx.add_local(spline_rel + o_data, spline_data_rel)
    write(spline_blob)
    align16()

    # extractedMotion → hkaDefaultAnimatedReferenceFrame
    ref_frame_rel = rel()
    fx.add_virtual(ref_frame_rel, 0, name_offs['hkaDefaultAnimatedReferenceFrame'])
    fx.add_local(spline_rel + o_extr_motion, ref_frame_rel)

    # hkaDefaultAnimatedReferenceFrame layout:
    # base(base_sz) + up(16) + forward(16) + duration(4) + pad(4) +
    # referenceFrameSamples hkArray(arr_sz)
    o_rf_up = base_sz
    o_rf_fwd = base_sz + 16
    o_rf_dur = base_sz + 32
    o_rf_samples = (base_sz + 40 + P - 1) & ~(P - 1)
    ref_struct_size = _align(o_rf_samples + arr_sz, 16)

    ref_hdr = bytearray(ref_struct_size)
    struct.pack_into('<ffff', ref_hdr, o_rf_up, 0.0, 0.0, 1.0, 0.0)
    struct.pack_into('<ffff', ref_hdr, o_rf_fwd, 0.0, 1.0, 0.0, 0.0)
    struct.pack_into('<f', ref_hdr, o_rf_dur, anim.duration)
    n_samples = anim.num_frames + 1
    pack_arr_at(ref_hdr, o_rf_samples, n_samples)
    write(bytes(ref_hdr))

    ref_samples_rel = rel()
    fx.add_local(ref_frame_rel + o_rf_samples, ref_samples_rel)
    write(bytes(16 * n_samples))  # vec4 per sample, all zeros
    align16()

    # ═══ hkaAnimationBinding ═══
    # base(base_sz) + originalSkeletonName(P) + animation(P)
    # + transformTrackToBoneIndices(arr_sz) + floatTrackToFloatSlotIndices(arr_sz)
    # + blendHint(4)
    o_bind_name = base_sz
    o_bind_anim = base_sz + P
    o_bind_idx = base_sz + 2 * P
    o_bind_float_idx = o_bind_idx + arr_sz
    o_bind_hint = o_bind_float_idx + arr_sz
    bind_struct_size = _align(o_bind_hint + 4, 16)

    binding_rel = rel()
    fx.add_virtual(binding_rel, 0, name_offs['hkaAnimationBinding'])
    fx.add_local(bind_ptr, binding_rel)

    bind_hdr = bytearray(bind_struct_size)
    pack_arr_at(bind_hdr, o_bind_idx, len(binding_indices))
    struct.pack_into('<I', bind_hdr, o_bind_hint, anim.blend_hint)
    write(bytes(bind_hdr))

    # Skeleton name string
    skel_name_rel = rel()
    write_string(skel_name)
    fx.add_local(binding_rel + o_bind_name, skel_name_rel)
    align_to(2)

    # Animation pointer
    fx.add_local(binding_rel + o_bind_anim, spline_rel)

    # Binding indices array
    bind_idx_rel = rel()
    fx.add_local(binding_rel + o_bind_idx, bind_idx_rel)
    for idx in binding_indices:
        write(_w_i16(idx))
    align16()

    # ═══ hkMemoryResourceContainer ═══
    mrc_rel = rel()
    fx.add_virtual(mrc_rel, 0, name_offs['hkMemoryResourceContainer'])
    fx.add_local(nv1_variant, mrc_rel)
    mrc_size = _align(base_sz + arr_sz, 16)
    write(bytes(mrc_size))
    align16()

    return bytes(data), fx


def write_skyrim_animation(filepath: str, anim: AnimationData,
                           ptr_size: int = 4) -> None:
    """Write an AnimationData to a Skyrim HKX binary file (hk_2010).

    Parameters
    ----------
    filepath : str
        Output path for the .hkx file.
    anim : AnimationData
        Must have tracks, duration, num_frames, frame_duration populated.
    ptr_size : int
        4 for Skyrim LE (32-bit), 8 for Skyrim SE (64-bit).
    """
    # Fill in defaults
    if not anim.num_blocks:
        max_fpb = anim.max_frames_per_block or 256
        anim.num_blocks = max(1, (anim.num_frames + max_fpb - 1) // max_fpb)
    if not anim.block_duration:
        anim.block_duration = anim.duration / anim.num_blocks if anim.num_blocks > 0 else anim.duration
    if not anim.frame_duration:
        anim.frame_duration = anim.duration / max(1, anim.num_frames - 1) if anim.num_frames > 1 else 1.0 / 30.0

    # Build sections
    cn_data, name_offs = _build_anim_classnames_v8()
    obj_data, fx = _build_anim_data_section(anim, name_offs, ptr_size)

    local_tbl = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl = fx.build_virtual_table()
    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    # Skyrim HKX layout (no padding block):
    # 0x00: file header (0x40)
    # 0x40: section header 0 (0x30)
    # 0x70: section header 1 (0x30)
    # 0xA0: section header 2 (0x30)
    # 0xD0: classnames data
    # cn_end: data section
    cn_start = 0x40 + 3 * _SEC_HDR_SIZE  # = 0xD0
    cn_end = cn_start + len(cn_data)
    data_start = cn_end

    local_fix_abs = data_start + len(obj_data)
    global_fix_abs = local_fix_abs + len(local_tbl)
    virt_fix_abs = global_fix_abs + len(global_tbl)
    data_end = virt_fix_abs + len(virt_tbl)

    cn_name_off = name_offs['hkRootLevelContainer']
    hdr = _skyrim_file_header(cn_name_off, ptr_size)

    shdr0 = _skyrim_section_header('__classnames__', cn_start,
                                    cn_start + len(cn_data), cn_start + len(cn_data),
                                    cn_start + len(cn_data), cn_start + len(cn_data))
    shdr1 = _skyrim_section_header('__types__', cn_end,
                                    cn_end, cn_end, cn_end, cn_end)
    shdr2 = _skyrim_section_header('__data__', data_start,
                                    local_fix_abs, global_fix_abs,
                                    virt_fix_abs, data_end)

    result = hdr + shdr0 + shdr1 + shdr2 + cn_data + data_section

    with open(filepath, 'wb') as f:
        f.write(result)


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <animation.hkx|skeleton.hkx>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"Loading: {filepath}")
    print()

    # Try skeleton first (XML skeletons are common for Skyrim)
    skel = load_skyrim_skeleton(filepath)
    if skel:
        print(f"Skeleton: {skel.name}")
        print(f"  Bones: {len(skel.bones)}")
        for i, b in enumerate(skel.bones):
            parent = skel.parents[i] if i < len(skel.parents) else -1
            print(f"    [{i:3d}] {b}  (parent={parent})")
        print()

    # Try animation
    try:
        anim = load_skyrim_animation(filepath)
        print(anim.summary())
    except ValueError as e:
        if not skel:
            print(f"Error: {e}")
