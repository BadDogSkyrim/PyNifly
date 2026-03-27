#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anim_fo4.py — Read FO4 hkaSplineCompressedAnimation data.

No Blender dependencies.  Can be run standalone:

    python anim_fo4.py <file.hkx>          # binary HKX (native reader, no deps)
    python anim_fo4.py <file.xml>          # hkpackfile XML (from hkxpack-cli)

Produces an in-memory AnimationData structure with fully decompressed per-frame
translation / rotation / scale for every bone track, plus skeleton info if present.

Based on spline decompression from Dagobaking's skyrim-fo4-animation-conversion
(itself based on PredatorCZ/HavokLib, GPL-3.0).
"""

import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
#  Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BonePose:
    """Rest-pose for a single bone (local space)."""
    translation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])  # xyzw
    scale: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])


@dataclass
class Skeleton:
    """Skeleton definition parsed from an hkpackfile."""
    name: str = ""
    bones: List[str] = field(default_factory=list)
    parents: List[int] = field(default_factory=list)
    reference_pose: List[BonePose] = field(default_factory=list)

    def __repr__(self):
        return f"Skeleton('{self.name}', {len(self.bones)} bones)"


@dataclass
class TrackData:
    """Fully decompressed per-frame data for one bone track."""
    translations: List[List[float]] = field(default_factory=list)  # [frame][x,y,z]
    rotations: List[List[float]] = field(default_factory=list)     # [frame][x,y,z,w]
    scales: List[List[float]] = field(default_factory=list)        # [frame][x,y,z]


@dataclass
class Annotation:
    """A single annotation event."""
    time: float = 0.0
    text: str = ""


@dataclass
class AnimationData:
    """Complete parsed animation."""
    # Header info
    duration: float = 0.0
    num_frames: int = 0
    num_tracks: int = 0
    num_blocks: int = 0
    max_frames_per_block: int = 256
    block_duration: float = 8.5
    frame_duration: float = 1.0 / 30.0

    # Bone names (from annotationTracks/trackName, one per track)
    bone_names: List[str] = field(default_factory=list)

    # Per-track decompressed data
    tracks: List[TrackData] = field(default_factory=list)

    # Annotations (text events at specific times)
    annotations: List[Annotation] = field(default_factory=list)

    # Binding info (from hkaAnimationBinding)
    track_to_bone_indices: List[int] = field(default_factory=list)
    original_skeleton_name: str = ""
    blend_hint: int = 0  # 0=NORMAL, 1=ADDITIVE

    # Skeleton (if present in the same file)
    skeleton: Optional[Skeleton] = None

    def summary(self) -> str:
        """Return a human-readable summary of the animation."""
        lines = []
        lines.append(f"Duration:       {self.duration:.4f}s")
        lines.append(f"Frame count:    {self.num_frames}")
        fps = 1.0 / self.frame_duration if self.frame_duration > 0 else 0
        lines.append(f"Frame rate:     {fps:.1f} fps")
        lines.append(f"Track count:    {self.num_tracks}")
        lines.append(f"Blocks:         {self.num_blocks}")
        lines.append(f"Block duration: {self.block_duration:.4f}s")
        lines.append(f"Max frames/blk: {self.max_frames_per_block}")

        if self.skeleton:
            lines.append(f"Skeleton:       {self.skeleton.name} ({len(self.skeleton.bones)} bones)")

        if self.annotations:
            lines.append(f"Annotations:    {len(self.annotations)}")
            for a in self.annotations:
                lines.append(f"  {a.time:.4f}s  {a.text}")

        # Analyse which tracks have actual motion
        animated_pos = []
        animated_rot = []
        animated_scale = []
        static_rot = []
        identity_tracks = []

        for i, track in enumerate(self.tracks):
            name = self.bone_names[i] if i < len(self.bone_names) and self.bone_names[i] else f"Bone #{i}"
            has_pos = False
            has_rot = False
            has_scale = False

            if track.translations and len(track.translations) > 1:
                t0 = track.translations[0]
                for t in track.translations[1:]:
                    if any(abs(t[j] - t0[j]) > 1e-5 for j in range(3)):
                        has_pos = True
                        break

            if track.rotations and len(track.rotations) > 1:
                r0 = track.rotations[0]
                for r in track.rotations[1:]:
                    dot = sum(r0[j] * r[j] for j in range(4))
                    if abs(abs(dot) - 1.0) > 1e-5:
                        has_rot = True
                        break

            if track.scales and len(track.scales) > 1:
                s0 = track.scales[0]
                for s in track.scales[1:]:
                    if any(abs(s[j] - s0[j]) > 1e-5 for j in range(3)):
                        has_scale = True
                        break

            if has_pos:
                animated_pos.append(name)
            if has_rot:
                animated_rot.append(name)
            elif track.rotations:
                # Has rotation data but it's static
                r0 = track.rotations[0]
                is_identity = abs(r0[3]) > 0.9999 and sum(r0[j]**2 for j in range(3)) < 1e-6
                if not is_identity:
                    static_rot.append(name)
            if has_scale:
                animated_scale.append(name)

            if not has_pos and not has_rot and not has_scale:
                identity_tracks.append(name)

        lines.append("")
        lines.append(f"Animated rotation:    {len(animated_rot)} tracks")
        for name in animated_rot:
            lines.append(f"  {name}")

        lines.append(f"Static rotation:      {len(static_rot)} tracks")
        for name in static_rot:
            lines.append(f"  {name}")

        if animated_pos:
            lines.append(f"Animated position:    {len(animated_pos)} tracks")
            for name in animated_pos:
                lines.append(f"  {name}")

        if animated_scale:
            lines.append(f"Animated scale:       {len(animated_scale)} tracks")
            for name in animated_scale:
                lines.append(f"  {name}")

        lines.append(f"Identity/unused:      {len(identity_tracks)} tracks")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Quaternion helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _quat_normalize(q):
    mag = math.sqrt(sum(c * c for c in q))
    if mag < 1e-10:
        return [0.0, 0.0, 0.0, 1.0]
    return [c / mag for c in q]


# ═══════════════════════════════════════════════════════════════════════════════
#  Spline decompression primitives
# ═══════════════════════════════════════════════════════════════════════════════

def _align(offset, alignment=4):
    r = offset % alignment
    return offset + (alignment - r) if r else offset


def _read_8bit_scalar(data, offset, mn, mx):
    val = data[offset]
    return mn + (mx - mn) * (val / 255.0), offset + 1


def _read_16bit_scalar(data, offset, mn, mx):
    val = struct.unpack_from('<H', data, offset)[0]
    return mn + (mx - mn) * (val / 65535.0), offset + 2


def _read_32bit_quat(data, offset):
    cval = struct.unpack_from('<I', data, offset)[0]
    r_mask = (1 << 10) - 1
    r_frac = 1.0 / r_mask
    R = ((cval >> 18) & r_mask) * r_frac
    R = 1.0 - R * R
    phi_theta = float(cval & 0x3FFFF)
    phi = math.floor(math.sqrt(phi_theta))
    theta = 0.0
    if phi > 0.0:
        theta = (math.pi / 4.0) * (phi_theta - phi * phi) / phi
        phi = (math.pi / 2.0 / 511.0) * phi
    magnitude = math.sqrt(max(0, 1.0 - R * R))
    sp, cp = math.sin(phi), math.cos(phi)
    st, ct = math.sin(theta), math.cos(theta)
    result = [sp * ct * magnitude, sp * st * magnitude, cp * magnitude, R]
    sign_masks = [0x10000000, 0x20000000, 0x40000000, 0x80000000]
    for i in range(4):
        if cval & sign_masks[i]:
            result[i] = -result[i]
    return _quat_normalize(result), offset + 4


def _read_40bit_quat(data, offset):
    FRACTAL = 0.000345436
    raw = int.from_bytes(data[offset:offset + 5], 'little')
    a = (raw >> 0) & 0xFFF
    b = (raw >> 12) & 0xFFF
    c = (raw >> 24) & 0xFFF
    vals = [(v - 2049) * FRACTAL for v in (a, b, c)]
    sum_sq = sum(v * v for v in vals)
    w = math.sqrt(max(0, 1.0 - sum_sq))
    if (raw >> 38) & 1:
        w = -w
    shift = (raw >> 36) & 3
    if shift == 0:
        result = [w, vals[0], vals[1], vals[2]]
    elif shift == 1:
        result = [vals[0], w, vals[1], vals[2]]
    elif shift == 2:
        result = [vals[0], vals[1], w, vals[2]]
    else:
        result = [vals[0], vals[1], vals[2], w]
    return _quat_normalize(result), offset + 5


def _read_48bit_quat(data, offset):
    FRACTAL = 0.000043161
    MASK = (1 << 15) - 1
    HALF = MASK >> 1
    x_raw, y_raw, z_raw = struct.unpack_from('<HHH', data, offset)
    shift = ((y_raw >> 14) & 2) | ((x_raw >> 15) & 1)
    r_sign = (z_raw >> 15) != 0
    vals = [((v & MASK) - HALF) * FRACTAL for v in (x_raw, y_raw, z_raw)]
    sum_sq = sum(v * v for v in vals)
    w = math.sqrt(max(0, 1.0 - sum_sq))
    if r_sign:
        w = -w
    if shift == 0:
        result = [w, vals[0], vals[1], vals[2]]
    elif shift == 1:
        result = [vals[0], w, vals[1], vals[2]]
    elif shift == 2:
        result = [vals[0], vals[1], w, vals[2]]
    else:
        result = [vals[0], vals[1], vals[2], w]
    return _quat_normalize(result), offset + 6


def _read_uncompressed_quat(data, offset):
    x, y, z, w = struct.unpack_from('<ffff', data, offset)
    return _quat_normalize([x, y, z, w]), offset + 16


_QUAT_READERS = {
    0: _read_32bit_quat,
    1: _read_40bit_quat,
    2: _read_48bit_quat,
    5: _read_uncompressed_quat,
}

_QUAT_ALIGN = {0: 4, 1: 1, 2: 2, 3: 1, 4: 2, 5: 4}


def _read_quat(fmt, data, offset):
    reader = _QUAT_READERS.get(fmt, _read_40bit_quat)
    return reader(data, offset)


# ═══════════════════════════════════════════════════════════════════════════════
#  B-spline evaluation
# ═══════════════════════════════════════════════════════════════════════════════

def _find_knot_span(degree, value, num_cp, knots):
    if num_cp <= 0:
        return 0
    if value >= knots[num_cp]:
        return num_cp - 1
    low, high = degree, num_cp
    mid = (low + high) // 2
    for _ in range(100):
        if value < knots[mid]:
            high = mid
        elif value >= knots[mid + 1]:
            low = mid
        else:
            break
        mid = (low + high) // 2
    return mid


def _eval_bspline(knot_span, degree, t, knots, control_points):
    if len(control_points) == 0:
        return 0.0
    if len(control_points) == 1:
        return control_points[0]

    N = [0.0] * (degree + 1)
    N[0] = 1.0
    for i in range(1, degree + 1):
        for j in range(i - 1, -1, -1):
            denom = knots[knot_span + i - j] - knots[knot_span - j]
            A = (t - knots[knot_span - j]) / denom if denom >= 1e-10 else 0.0
            tmp = N[j] * A
            if j + 1 < len(N):
                N[j + 1] += N[j] - tmp
            N[j] = tmp

    # Scalar track
    if isinstance(control_points[0], (int, float)):
        result = 0.0
        for i in range(degree + 1):
            idx = knot_span - i
            if 0 <= idx < len(control_points):
                result += control_points[idx] * N[i]
        return result

    # Vector track (quaternion)
    dim = len(control_points[0])
    result = [0.0] * dim
    for i in range(degree + 1):
        idx = knot_span - i
        if 0 <= idx < len(control_points):
            for d in range(dim):
                result[d] += control_points[idx][d] * N[i]
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Track mask
# ═══════════════════════════════════════════════════════════════════════════════

class _TrackMask:
    __slots__ = ('pos_quant', 'rot_quant', 'scale_quant',
                 'pos_flags', 'rot_flags', 'scale_flags')

    def __init__(self, b0, b1, b2, b3):
        self.pos_quant = b0 & 0x03
        self.rot_quant = (b0 >> 2) & 0x0F
        self.scale_quant = (b0 >> 6) & 0x03
        self.pos_flags = b1
        self.rot_flags = b2
        self.scale_flags = b3

    def pos_type(self, axis):
        spline_bit = (self.pos_flags >> (axis + 4)) & 1
        if spline_bit:
            return 'spline'
        if (self.pos_flags >> axis) & 1:
            return 'static'
        return 'identity'

    def rot_type(self):
        if (self.rot_flags >> 4) & 0x0F:
            return 'spline'
        if self.rot_flags & 0x0F:
            return 'static'
        return 'identity'

    def scale_type(self, axis):
        spline_bit = (self.scale_flags >> (axis + 4)) & 1
        if spline_bit:
            return 'spline'
        if (self.scale_flags >> axis) & 1:
            return 'static'
        return 'identity'

    def has_any_pos_spline(self):
        return any(self.pos_type(a) == 'spline' for a in range(3))

    def has_any_scale_spline(self):
        return any(self.scale_type(a) == 'spline' for a in range(3))


# ═══════════════════════════════════════════════════════════════════════════════
#  Spline decompression — main routine
# ═══════════════════════════════════════════════════════════════════════════════

def _decompress_spline(data_bytes, num_tracks, num_frames, num_blocks,
                       max_frames_per_block, block_offsets,
                       mask_and_quant_size=0):
    """Decompress hkaSplineCompressedAnimation data blob.

    Returns list of TrackData (one per track), with per-frame translations,
    rotations, and scales fully evaluated.

    mask_and_quant_size: total size of the mask+quantization block at the start
    of each data block (includes transform masks + float track quantization bytes).
    If 0, computed as _align(4 * num_tracks, 4).
    """
    all_tracks = [TrackData() for _ in range(num_tracks)]
    if not mask_and_quant_size:
        mask_and_quant_size = _align(4 * num_tracks, 4)

    for block_idx in range(num_blocks):
        block_start = block_offsets[block_idx]
        first_frame = block_idx * max_frames_per_block
        if block_idx == num_blocks - 1:
            frames_in_block = num_frames - first_frame
        else:
            frames_in_block = max_frames_per_block

        # ── Parse masks (4 bytes per track) ──
        masks = []
        off = block_start
        for _ in range(num_tracks):
            masks.append(_TrackMask(data_bytes[off], data_bytes[off + 1],
                                    data_bytes[off + 2], data_bytes[off + 3]))
            off += 4
        # Skip past float track quantization bytes and any padding
        off = block_start + mask_and_quant_size

        # ── Per-track data ──
        for track_idx in range(num_tracks):
            mask = masks[track_idx]
            track = all_tracks[track_idx]

            # ─── POSITION ───
            pos_frames = []
            if mask.has_any_pos_spline():
                num_items = struct.unpack_from('<H', data_bytes, off)[0]
                degree = data_bytes[off + 2]
                off += 3
                num_knots = num_items + degree + 2
                knots = [float(data_bytes[off + k]) for k in range(num_knots)]
                off += num_knots
                off = _align(off, 4)

                axis_info = []
                for axis in range(3):
                    ptype = mask.pos_type(axis)
                    if ptype == 'spline':
                        mn = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                        mx = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                        axis_info.append(('spline', mn, mx))
                    elif ptype == 'static':
                        val = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                        axis_info.append(('static', val, val))
                    else:
                        axis_info.append(('identity', 0.0, 0.0))

                cps = [[] for _ in range(3)]
                for _ in range(num_items + 1):
                    for axis in range(3):
                        atype, mn, mx = axis_info[axis]
                        if atype == 'spline':
                            if mask.pos_quant == 0:
                                val, off = _read_8bit_scalar(data_bytes, off, mn, mx)
                            else:
                                val, off = _read_16bit_scalar(data_bytes, off, mn, mx)
                            cps[axis].append(val)
                off = _align(off, 4)

                for f in range(frames_in_block):
                    ft = float(f)
                    pos = [0.0, 0.0, 0.0]
                    for axis in range(3):
                        atype = axis_info[axis][0]
                        if atype == 'spline':
                            span = _find_knot_span(degree, ft, len(cps[axis]), knots)
                            pos[axis] = _eval_bspline(span, degree, ft, knots, cps[axis])
                        elif atype == 'static':
                            pos[axis] = axis_info[axis][1]
                    pos_frames.append(pos)
            else:
                pos = [0.0, 0.0, 0.0]
                for axis in range(3):
                    if mask.pos_type(axis) == 'static':
                        pos[axis] = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                pos_frames = [list(pos) for _ in range(frames_in_block)]

            off = _align(off, 4)
            track.translations.extend(pos_frames)

            # ─── ROTATION ───
            rot_frames = []
            rot_type = mask.rot_type()
            qfmt = mask.rot_quant
            qalign = _QUAT_ALIGN.get(qfmt, 4)

            if rot_type == 'spline':
                num_items = struct.unpack_from('<H', data_bytes, off)[0]
                degree = data_bytes[off + 2]
                off += 3
                num_knots = num_items + degree + 2
                knots = [float(data_bytes[off + k]) for k in range(num_knots)]
                off += num_knots
                if qalign > 1:
                    off = _align(off, qalign)

                quat_cps = []
                for _ in range(num_items + 1):
                    q, off = _read_quat(qfmt, data_bytes, off)
                    if quat_cps:
                        dot = sum(a * b for a, b in zip(q, quat_cps[-1]))
                        if dot < 0:
                            q = [-c for c in q]
                    quat_cps.append(q)

                for f in range(frames_in_block):
                    ft = float(f)
                    span = _find_knot_span(degree, ft, len(quat_cps), knots)
                    q = _eval_bspline(span, degree, ft, knots, quat_cps)
                    rot_frames.append(_quat_normalize(q))

            elif rot_type == 'static':
                if qalign > 1:
                    off = _align(off, qalign)
                q, off = _read_quat(qfmt, data_bytes, off)
                rot_frames = [list(q) for _ in range(frames_in_block)]
            else:
                rot_frames = [[0.0, 0.0, 0.0, 1.0] for _ in range(frames_in_block)]

            off = _align(off, 4)
            track.rotations.extend(rot_frames)

            # ─── SCALE ───
            scale_frames = []
            if mask.has_any_scale_spline():
                num_items = struct.unpack_from('<H', data_bytes, off)[0]
                degree = data_bytes[off + 2]
                off += 3
                num_knots = num_items + degree + 2
                knots = [float(data_bytes[off + k]) for k in range(num_knots)]
                off += num_knots
                off = _align(off, 4)

                axis_info = []
                for axis in range(3):
                    stype = mask.scale_type(axis)
                    if stype == 'spline':
                        mn = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                        mx = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                        axis_info.append(('spline', mn, mx))
                    elif stype == 'static':
                        val = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                        axis_info.append(('static', val, val))
                    else:
                        axis_info.append(('identity', 1.0, 1.0))

                cps = [[] for _ in range(3)]
                for _ in range(num_items + 1):
                    for axis in range(3):
                        atype, mn, mx = axis_info[axis]
                        if atype == 'spline':
                            if mask.scale_quant == 0:
                                val, off = _read_8bit_scalar(data_bytes, off, mn, mx)
                            else:
                                val, off = _read_16bit_scalar(data_bytes, off, mn, mx)
                            cps[axis].append(val)
                off = _align(off, 4)

                for f in range(frames_in_block):
                    ft = float(f)
                    s = [1.0, 1.0, 1.0]
                    for axis in range(3):
                        atype = axis_info[axis][0]
                        if atype == 'spline':
                            span = _find_knot_span(degree, ft, len(cps[axis]), knots)
                            s[axis] = _eval_bspline(span, degree, ft, knots, cps[axis])
                        elif atype == 'static':
                            s[axis] = axis_info[axis][1]
                    scale_frames.append(s)
            else:
                s = [1.0, 1.0, 1.0]
                for axis in range(3):
                    if mask.scale_type(axis) == 'static':
                        s[axis] = struct.unpack_from('<f', data_bytes, off)[0]; off += 4
                scale_frames = [list(s) for _ in range(frames_in_block)]

            off = _align(off, 4)
            track.scales.extend(scale_frames)

    return all_tracks


# ═══════════════════════════════════════════════════════════════════════════════
#  Binary HKX reader (native — no external tools)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  hk_2014.1.0-r1 packfile layout (FO4, 64-bit pointers):
#
#    0x00: File header (0x40 bytes)
#    0x40: padding11 value (2 bytes) — if 0x10, next 16 bytes are padding
#    0x50: Section header 0 __classnames__  (0x40 bytes each)
#    0x90: Section header 1 __types__       (empty)
#    0xD0: Section header 2 __data__
#    Then: classnames data, data section, fixup tables
#
#  hkaSplineCompressedAnimation struct (relative to object start):
#    +0x00  vtable ptr             (8, zeros in file)
#    +0x08  memSizeAndFlags etc    (8, serialise-ignored)
#    +0x10  type                   (4, enum — 3 = SPLINE_COMPRESSED)
#    +0x14  duration               (4, float)
#    +0x18  numberOfTransformTracks (4, int32)
#    +0x1C  numberOfFloatTracks    (4, int32)
#    +0x20  extractedMotion        (8, pointer)
#    +0x28  annotationTracks       (16, hkArray of hkaAnnotationTrack)
#    +0x38  numFrames              (4, int32)
#    +0x3C  numBlocks              (4, int32)
#    +0x40  maxFramesPerBlock      (4, int32)
#    +0x44  maskAndQuantizationSize (4, int32)
#    +0x48  blockDuration          (4, float)
#    +0x4C  blockInverseDuration   (4, float)
#    +0x50  frameDuration          (4, float)
#    +0x54  padding                (4)
#    +0x58  blockOffsets           (16, hkArray<u32>)
#    +0x68  floatBlockOffsets      (16, hkArray<u32>)
#    +0x78  transformOffsets       (16, hkArray<u32>)
#    +0x88  floatOffsets           (16, hkArray<u32>)
#    +0x98  data                   (16, hkArray<u8>)
#
#  hkaAnnotationTrack struct (0x18 bytes each):
#    +0x00  trackName              (8, string pointer)
#    +0x08  annotations            (16, hkArray of hkaAnnotation)
#
#  hkArray layout (16 bytes):
#    +0x00  data pointer           (8, resolved via local fixups)
#    +0x08  size                   (4, int32)
#    +0x0C  capacityAndFlags       (4, int32 — high bit = owned flag)

_HKX_MAGIC = b'\x57\xe0\xe0\x57'

def _u32(data, off):
    return struct.unpack_from('<I', data, off)[0]

def _i32(data, off):
    return struct.unpack_from('<i', data, off)[0]

def _f32(data, off):
    return struct.unpack_from('<f', data, off)[0]


def _parse_hkx_sections(data):
    """Parse v11 packfile section headers. Returns dict of name -> info.

    Standalone HKX v11 layout:
      0x00-0x3F  file header (64 bytes)
      0x40-0x4F  padding (16 bytes)
      0x50+      3 section headers, each 0x40 bytes
    Section header layout (relative to section header base):
      +0x00  name              (16 bytes, null-terminated)
      +0x10  marker            (4 bytes, 0xFF000000)
      +0x14  abs_data_start    (4 bytes, absolute file offset of section data)
      +0x18  local_fixup_off   (relative to abs_data_start)
      +0x1C  global_fixup_off  (relative to abs_data_start)
      +0x20  virtual_fixup_off (relative to abs_data_start)
      +0x24  exports_off       (relative to abs_data_start)
      +0x28  (unused)
      +0x2C  end_off           (relative to abs_data_start)
    """
    version = _u32(data, 0x0C)
    if version != 11:
        raise ValueError(f"Unsupported HKX version {version} (expected 11 for FO4)")

    # Section headers start at 0x50 in standalone HKX v11 files
    sec_start = 0x50

    sections = {}
    for i in range(3):
        base = sec_start + i * 0x40
        name = data[base:base + 16].split(b'\x00')[0].decode('ascii', errors='replace')
        s = _u32(data, base + 0x14)
        sections[name] = {
            'offset': s,
            'data1': s + _u32(data, base + 0x18),
            'data2': s + _u32(data, base + 0x1C),
            'data3': s + _u32(data, base + 0x20),
            'exports': s + _u32(data, base + 0x24),
            'end':   s + _u32(data, base + 0x2C),
        }
    return sections


def _parse_local_fixups(data, sec):
    """Parse local fixup table (data1): src_rel -> dst_rel within __data__."""
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
    """Parse virtual fixup table (data3): returns [(rel_offset, class_name)]."""
    objects = []
    pos = sec['data3']
    end = sec['exports']
    while pos + 12 <= end:
        src = _u32(data, pos)
        _u32(data, pos + 4)  # section index (unused)
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


def _read_hkarray_u32(data, data_abs, obj_rel, field_off, fixups):
    """Read an hkArray<uint32> field, returning a list of uint32 values."""
    arr_rel = obj_rel + field_off
    count = _u32(data, data_abs + arr_rel + 8)
    if count == 0:
        return []
    content_rel = fixups.get(arr_rel)
    if content_rel is None:
        return []
    content_abs = data_abs + content_rel
    return [_u32(data, content_abs + i * 4) for i in range(count)]


def _read_hkarray_u8(data, data_abs, obj_rel, field_off, fixups):
    """Read an hkArray<uint8> field, returning bytes."""
    arr_rel = obj_rel + field_off
    count = _u32(data, data_abs + arr_rel + 8)
    if count == 0:
        return b''
    content_rel = fixups.get(arr_rel)
    if content_rel is None:
        return b''
    content_abs = data_abs + content_rel
    return data[content_abs:content_abs + count]


def _read_null_string(data, abs_off):
    """Read a null-terminated ASCII string."""
    try:
        end = data.index(b'\x00', abs_off, abs_off + 256)
        return data[abs_off:end].decode('ascii', errors='replace')
    except ValueError:
        return ''


def _parse_animation_hkx(data) -> Optional[AnimationData]:
    """Parse hkaSplineCompressedAnimation from a binary HKX file."""
    if data[:4] != _HKX_MAGIC:
        return None

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
    anim.duration = _f32(data, a + 0x14)
    anim.num_tracks = _u32(data, a + 0x18)
    anim.num_frames = _u32(data, a + 0x38)
    anim.num_blocks = _u32(data, a + 0x3C)
    anim.max_frames_per_block = _u32(data, a + 0x40)
    mask_and_quant_size = _u32(data, a + 0x44)
    anim.block_duration = _f32(data, a + 0x48)
    anim.frame_duration = _f32(data, a + 0x50)

    block_offsets = _read_hkarray_u32(data, data_abs, anim_rel, 0x58, fixups)
    data_blob = _read_hkarray_u8(data, data_abs, anim_rel, 0x98, fixups)

    if not data_blob or not block_offsets:
        return None

    # ── Parse annotation tracks (bone names) ──
    # annotationTracks is an hkArray at anim+0x28
    ann_arr_rel = anim_rel + 0x28
    ann_count = _u32(data, data_abs + ann_arr_rel + 8)
    ann_content_rel = fixups.get(ann_arr_rel)

    if ann_content_rel is not None and ann_count > 0:
        # Each hkaAnnotationTrack is 0x18 bytes: string ptr (8) + hkArray (16)
        ANNTRACK_STRIDE = 0x18
        for i in range(ann_count):
            track_rel = ann_content_rel + i * ANNTRACK_STRIDE
            # The string pointer at track_rel is resolved via local fixup
            str_target_rel = fixups.get(track_rel)
            if str_target_rel is not None:
                name = _read_null_string(data, data_abs + str_target_rel)
                anim.bone_names.append(name)
            else:
                anim.bone_names.append('')

            # Check for annotation events within this track
            ann_events_rel = track_rel + 0x08  # annotations hkArray
            ann_events_count = _u32(data, data_abs + ann_events_rel + 8)
            ann_events_content_rel = fixups.get(ann_events_rel)
            if ann_events_content_rel is not None and ann_events_count > 0:
                # Each hkaAnnotation is 0x10 bytes: float time (4) + pad (4) + string ptr (8)
                for j in range(ann_events_count):
                    evt_rel = ann_events_content_rel + j * 0x10
                    evt_time = _f32(data, data_abs + evt_rel)
                    evt_str_rel = fixups.get(evt_rel + 0x08)
                    evt_text = ''
                    if evt_str_rel is not None:
                        evt_text = _read_null_string(data, data_abs + evt_str_rel)
                    anim.annotations.append(Annotation(time=evt_time, text=evt_text))

    # ── Parse hkaAnimationBinding (bone indices, skeleton name) ──
    for rel, cls in objects:
        if cls == 'hkaAnimationBinding':
            # bind_abs = data_abs + rel
            # +0x10: originalSkeletonName (string ptr)
            skel_name_rel = fixups.get(rel + 0x10)
            if skel_name_rel is not None:
                anim.original_skeleton_name = _read_null_string(data, data_abs + skel_name_rel)
            # +0x20: transformTrackToBoneIndices (hkArray<int16>)
            idx_arr_rel = rel + 0x20
            idx_count = _u32(data, data_abs + idx_arr_rel + 8)
            idx_content_rel = fixups.get(idx_arr_rel)
            if idx_content_rel is not None and idx_count > 0:
                idx_abs = data_abs + idx_content_rel
                anim.track_to_bone_indices = [
                    struct.unpack_from('<h', data, idx_abs + i * 2)[0]
                    for i in range(idx_count)
                ]
            break

    # ── Decompress spline data ──
    anim.tracks = _decompress_spline(
        data_blob, anim.num_tracks, anim.num_frames,
        anim.num_blocks, anim.max_frames_per_block, block_offsets,
        mask_and_quant_size
    )

    return anim


# ═══════════════════════════════════════════════════════════════════════════════
#  XML parsing (hkpackfile format — produced by hkxpack-cli)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_skeleton_xml(root) -> Optional[Skeleton]:
    """Extract the first non-ragdoll hkaSkeleton from an hkpackfile XML tree."""
    for obj in root.iter('hkobject'):
        if obj.attrib.get('class') != 'hkaSkeleton':
            continue
        name_p = obj.find(".//hkparam[@name='name']")
        if name_p is not None and name_p.text and 'Ragdoll' in name_p.text:
            continue

        skel = Skeleton()
        if name_p is not None and name_p.text:
            skel.name = name_p.text

        bones_p = obj.find(".//hkparam[@name='bones']")
        if bones_p is not None:
            for bone_obj in bones_p.findall('hkobject'):
                np = bone_obj.find("hkparam[@name='name']")
                skel.bones.append(np.text if np is not None and np.text else '')

        parents_p = obj.find(".//hkparam[@name='parentIndices']")
        if parents_p is not None and parents_p.text:
            skel.parents = [int(x) for x in parents_p.text.strip().split()]

        ref_p = obj.find(".//hkparam[@name='referencePose']")
        if ref_p is not None and ref_p.text:
            tuples = re.findall(r'\(([^)]+)\)', ref_p.text)
            for i in range(0, len(tuples) - 2, 3):
                t = [float(x) for x in tuples[i].split()]
                r = [float(x) for x in tuples[i + 1].split()]
                s = [float(x) for x in tuples[i + 2].split()]
                skel.reference_pose.append(BonePose(t[:3], r[:4], s[:3]))
        return skel

    return None


def _parse_animation_xml(root) -> Optional[AnimationData]:
    """Parse hkaSplineCompressedAnimation from an hkpackfile XML tree."""
    anim = AnimationData()

    anim_obj = None
    for obj in root.iter('hkobject'):
        if obj.attrib.get('class') == 'hkaSplineCompressedAnimation':
            anim_obj = obj
            break
    if anim_obj is None:
        return None

    block_offsets = []
    data_ints = []

    for param in anim_obj.findall('hkparam'):
        name = param.attrib.get('name', '')
        text = param.text.strip() if param.text else ''
        if name == 'duration':
            anim.duration = float(text)
        elif name == 'numberOfTransformTracks':
            anim.num_tracks = int(text)
        elif name == 'numFrames':
            anim.num_frames = int(text)
        elif name == 'numBlocks':
            anim.num_blocks = int(text)
        elif name == 'maxFramesPerBlock':
            anim.max_frames_per_block = int(text)
        elif name == 'blockDuration':
            anim.block_duration = float(text)
        elif name == 'frameDuration':
            anim.frame_duration = float(text)
        elif name == 'blockOffsets':
            block_offsets = [int(x) for x in text.split()]
        elif name == 'data':
            data_ints = [int(x) for x in text.split()]
        elif name == 'annotationTracks':
            for track_obj in param.findall('hkobject'):
                tn = track_obj.find("hkparam[@name='trackName']")
                anim.bone_names.append(tn.text if tn is not None and tn.text else '')
                ann_param = track_obj.find("hkparam[@name='annotations']")
                if ann_param is not None:
                    for ann_obj in ann_param.findall('hkobject'):
                        time_p = ann_obj.find("hkparam[@name='time']")
                        text_p = ann_obj.find("hkparam[@name='text']")
                        if time_p is not None and time_p.text:
                            a = Annotation()
                            a.time = float(time_p.text.strip())
                            a.text = text_p.text.strip() if text_p is not None and text_p.text else ''
                            anim.annotations.append(a)

    if not data_ints or not block_offsets:
        return None

    data_bytes = bytes(data_ints)
    anim.tracks = _decompress_spline(
        data_bytes, anim.num_tracks, anim.num_frames,
        anim.num_blocks, anim.max_frames_per_block, block_offsets
    )

    anim.skeleton = _parse_skeleton_xml(root)
    return anim


# ═══════════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════════

def is_fo4_hkx(filepath: str) -> bool:
    """Return True if filepath is a FO4 (hk_2014) binary HKX file."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(0x38)
        if len(header) < 0x38:
            return False
        if header[:4] != _HKX_MAGIC:
            return False
        version = struct.unpack_from('<I', header, 0x0C)[0]
        if version != 11:
            return False
        contents = header[0x28:0x38].split(b'\x00')[0].decode('ascii', errors='replace')
        return contents.startswith('hk_2014')
    except (OSError, IOError):
        return False


def _parse_skeleton_hkx(data: bytes) -> Optional[Skeleton]:
    """Parse hkaSkeleton from a binary HKX file."""
    if data[:4] != _HKX_MAGIC:
        return None

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

    # +0x10: name (string ptr)
    name_target = fixups.get(skel_rel + 0x10)
    if name_target is not None:
        skel.name = _read_null_string(data, data_abs + name_target)

    # +0x18: parentIndices (hkArray<int16>)
    pi_count = _u32(data, s + 0x18 + 8)
    pi_content = fixups.get(skel_rel + 0x18)
    if pi_content is not None and pi_count > 0:
        pi_abs = data_abs + pi_content
        skel.parents = [
            struct.unpack_from('<h', data, pi_abs + i * 2)[0]
            for i in range(pi_count)
        ]

    # +0x28: bones (hkArray<hkaBone>) — each hkaBone is 0x10: string ptr (8) + lockTranslation (4) + pad (4)
    bone_count = _u32(data, s + 0x28 + 8)
    bone_content = fixups.get(skel_rel + 0x28)
    if bone_content is not None and bone_count > 0:
        BONE_STRIDE = 0x10
        for i in range(bone_count):
            bone_rel = bone_content + i * BONE_STRIDE
            str_target = fixups.get(bone_rel)
            if str_target is not None:
                skel.bones.append(_read_null_string(data, data_abs + str_target))
            else:
                skel.bones.append('')

    # +0x38: referencePose (hkArray<hkQsTransform>) — each is 0x30 bytes: vec4 pos + vec4 rot + vec4 scale
    pose_count = _u32(data, s + 0x38 + 8)
    pose_content = fixups.get(skel_rel + 0x38)
    if pose_content is not None and pose_count > 0:
        POSE_STRIDE = 0x30
        for i in range(pose_count):
            p = data_abs + pose_content + i * POSE_STRIDE
            tx, ty, tz = _f32(data, p), _f32(data, p+4), _f32(data, p+8)
            rx, ry, rz, rw = _f32(data, p+16), _f32(data, p+20), _f32(data, p+24), _f32(data, p+28)
            sx, sy, sz = _f32(data, p+32), _f32(data, p+36), _f32(data, p+40)
            skel.reference_pose.append(BonePose([tx, ty, tz], [rx, ry, rz, rw], [sx, sy, sz]))

    return skel


def load_fo4_skeleton(filepath: str) -> Optional[Skeleton]:
    """Load a FO4 skeleton from a binary HKX file.

    Returns Skeleton with bone names, parent indices, and reference pose,
    or None if no hkaSkeleton was found.
    """
    filepath = str(filepath)
    with open(filepath, 'rb') as f:
        raw = f.read()

    if raw[:4] == _HKX_MAGIC:
        return _parse_skeleton_hkx(raw)

    # Try XML
    if raw[:5] == b'<?xml' or raw[:1] == b'<':
        try:
            tree = ET.parse(filepath)
        except ET.ParseError:
            return None
        root = tree.getroot()
        if root.tag == 'hkpackfile':
            return _parse_skeleton_xml(root)

    return None


def load_fo4_animation(filepath: str) -> AnimationData:
    """Load a FO4 animation from a binary HKX or hkpackfile XML.

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

    # Detect format by magic bytes
    if raw[:4] == _HKX_MAGIC:
        anim = _parse_animation_hkx(raw)
        if anim is None:
            raise ValueError("No hkaSplineCompressedAnimation found in HKX file.")
        return anim

    # Try XML
    if raw[:5] == b'<?xml' or raw[:1] == b'<':
        try:
            tree = ET.parse(filepath)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {e}")

        root = tree.getroot()
        if root.tag != 'hkpackfile':
            raise ValueError(
                f"Expected hkpackfile XML, got <{root.tag}>. "
                f"This may be a Skyrim tagfile — FO4 uses hkpackfile format."
            )

        anim = _parse_animation_xml(root)
        if anim is None:
            raise ValueError("No hkaSplineCompressedAnimation found in file.")
        return anim

    raise ValueError(f"Unrecognized file format (not HKX binary or XML).")


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: Writer helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _w_u8(v: int) -> bytes: return struct.pack('<B', v & 0xFF)
def _w_u16(v: int) -> bytes: return struct.pack('<H', v & 0xFFFF)
def _w_u32(v: int) -> bytes: return struct.pack('<I', v & 0xFFFFFFFF)
def _w_u64(v: int) -> bytes: return struct.pack('<Q', v & 0xFFFFFFFFFFFFFFFF)
def _w_i16(v: int) -> bytes: return struct.pack('<h', v)
def _w_f32(v: float) -> bytes: return struct.pack('<f', v)

def _pad16(data: bytes, fill: int = 0xFF) -> bytes:
    r = len(data) % 16
    return data + (bytes([fill]) * (16 - r) if r else b'')

def _pad4(data: bytearray) -> None:
    r = len(data) % 4
    if r:
        data.extend(b'\x00' * (4 - r))

def _hkarray(count: int) -> bytes:
    cap = (count | 0x80000000) if count > 0 else 0x80000000
    return _w_u64(0) + _w_u32(count) + _w_u32(cap)


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: Quaternion encoding (48-bit, format 2)
# ═══════════════════════════════════════════════════════════════════════════════

def _write_48bit_quat(q) -> bytes:
    """Encode a unit quaternion [x,y,z,w] as 6 bytes (48-bit compressed).

    Matches the reader's _read_48bit_quat exactly.
    """
    FRACTAL = 0.000043161
    MASK = (1 << 15) - 1
    HALF = MASK >> 1  # 16383

    # Find component with largest absolute value — it gets reconstructed
    abs_q = [abs(c) for c in q]
    shift = abs_q.index(max(abs_q))
    r_sign = q[shift] < 0

    # The 3 stored components (excluding the largest)
    vals = [q[j] for j in range(4) if j != shift]

    # Quantize each to 15-bit signed value
    raw = [min(MASK, max(0, int(round(v / FRACTAL + HALF)))) for v in vals]

    x_raw = raw[0] & MASK
    y_raw = raw[1] & MASK
    z_raw = raw[2] & MASK

    # Encode shift into high bits of x and y
    x_raw |= (shift & 1) << 15
    y_raw |= ((shift >> 1) & 1) << 15

    # Encode sign into high bit of z
    if r_sign:
        z_raw |= 1 << 15

    return struct.pack('<HHH', x_raw, y_raw, z_raw)


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: Scalar quantization
# ═══════════════════════════════════════════════════════════════════════════════

def _write_16bit_scalar(val: float, mn: float, mx: float) -> bytes:
    if abs(mx - mn) < 1e-30:
        return _w_u16(0)
    t = (val - mn) / (mx - mn)
    return _w_u16(min(65535, max(0, int(round(t * 65535)))))

def _write_8bit_scalar(val: float, mn: float, mx: float) -> bytes:
    if abs(mx - mn) < 1e-30:
        return _w_u8(0)
    t = (val - mn) / (mx - mn)
    return _w_u8(min(255, max(0, int(round(t * 255)))))


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: B-spline fitting
# ═══════════════════════════════════════════════════════════════════════════════

def _make_clamped_knots(n_cp: int, degree: int) -> List[int]:
    """Build a clamped uniform knot vector with integer values (uint8-storable).

    For n_cp control points and given degree, returns n_cp + degree + 1 knots.
    Knot range is [0, n_cp - degree - 1] for the standard clamped uniform form,
    BUT we remap to [0, max_t] where max_t = n_cp - 1 (matching frame indices).
    """
    if n_cp <= degree + 1:
        # Bezier-like: all knots clamped at 0 and n_cp-1
        return [0] * (degree + 1) + [n_cp - 1] * (degree + 1)

    max_t = n_cp - 1
    # Clamped: first (degree+1) at 0, last (degree+1) at max_t
    # Interior knots evenly spaced at integer values
    knots = [0] * (degree + 1)
    n_interior = n_cp - degree - 1
    for i in range(n_interior):
        knots.append(int(round((i + 1) * max_t / (n_interior + 1))))
    knots.extend([max_t] * (degree + 1))
    return knots


def _bspline_basis_row(degree: int, t: float, n_cp: int, knots: List) -> List[float]:
    """Evaluate all n_cp basis functions at parameter t.

    Returns a list of n_cp floats.
    """
    row = [0.0] * n_cp
    span = _find_knot_span(degree, t, n_cp, knots)

    # de Boor basis: compute the (degree+1) nonzero basis values
    N = [0.0] * (degree + 1)
    N[0] = 1.0
    for i in range(1, degree + 1):
        for j in range(i - 1, -1, -1):
            denom = knots[span + i - j] - knots[span - j]
            A = (t - knots[span - j]) / denom if denom >= 1e-10 else 0.0
            tmp = N[j] * A
            if j + 1 < len(N):
                N[j + 1] += N[j] - tmp
            N[j] = tmp

    for i in range(degree + 1):
        idx = span - i
        if 0 <= idx < n_cp:
            row[idx] = N[i]
    return row


def _solve_banded(matrix: List[List[float]], rhs: List[float]) -> List[float]:
    """Solve a banded linear system via Gaussian elimination with partial pivoting.

    matrix is N×N, rhs is length N. Returns solution vector.
    Modifies matrix and rhs in place.
    """
    n = len(rhs)
    for col in range(n):
        # Partial pivot
        max_row = col
        max_val = abs(matrix[col][col])
        for row in range(col + 1, min(col + 8, n)):
            if abs(matrix[row][col]) > max_val:
                max_val = abs(matrix[row][col])
                max_row = row
        if max_row != col:
            matrix[col], matrix[max_row] = matrix[max_row], matrix[col]
            rhs[col], rhs[max_row] = rhs[max_row], rhs[col]

        pivot = matrix[col][col]
        if abs(pivot) < 1e-30:
            continue

        for row in range(col + 1, min(col + 8, n)):
            factor = matrix[row][col] / pivot
            if abs(factor) < 1e-30:
                continue
            for k in range(col, min(col + 8, n)):
                matrix[row][k] -= factor * matrix[col][k]
            rhs[row] -= factor * rhs[col]

    # Back substitution
    result = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = rhs[i]
        for j in range(i + 1, min(i + 8, n)):
            s -= matrix[i][j] * result[j]
        if abs(matrix[i][i]) > 1e-30:
            result[i] = s / matrix[i][i]
    return result


def _fit_bspline_scalar(degree: int, knots: List, n_cp: int,
                        frame_values: List[float]) -> List[float]:
    """Find control points that exactly interpolate frame_values at t=0,1,...,N-1.

    Returns n_cp control points.
    """
    n_frames = len(frame_values)
    assert n_cp == n_frames, "Exact interpolation requires n_cp == n_frames"

    # Build collocation matrix
    matrix = [_bspline_basis_row(degree, float(i), n_cp, knots) for i in range(n_frames)]
    rhs = list(frame_values)
    return _solve_banded(matrix, rhs)


def _fit_bspline_quat(degree: int, knots: List, n_cp: int,
                      frame_quats: List[List[float]]) -> List[List[float]]:
    """Find quaternion control points by fitting each component independently.

    Returns n_cp quaternion control points [x,y,z,w].
    """
    cps = []
    for comp in range(4):
        vals = [q[comp] for q in frame_quats]
        cp_comp = _fit_bspline_scalar(degree, knots, n_cp, vals)
        cps.append(cp_comp)
    return [[cps[c][i] for c in range(4)] for i in range(n_cp)]


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: Spline compression
# ═══════════════════════════════════════════════════════════════════════════════

_EPS = 1e-5   # Tolerance for static/identity detection
_POS_QUANT = 1      # 16-bit position quantization
_ROT_QUANT = 2      # 48-bit quaternion
_SCALE_QUANT = 1    # 16-bit scale quantization


def _classify_axis(values: List[float], identity_val: float = 0.0) -> str:
    """Classify a single axis as 'identity', 'static', or 'spline'."""
    if all(abs(v - identity_val) < _EPS for v in values):
        return 'identity'
    v0 = values[0]
    if all(abs(v - v0) < _EPS for v in values):
        return 'static'
    return 'spline'


def _build_mask_bytes(track: TrackData, n_frames: int) -> Tuple[bytes, dict]:
    """Build the 4 mask bytes for a track and return axis classification info."""
    # Position
    pos_types = []
    for axis in range(3):
        vals = [track.translations[f][axis] for f in range(n_frames)]
        pos_types.append(_classify_axis(vals, 0.0))

    # Rotation
    quats = track.rotations[:n_frames]
    is_identity_rot = all(
        abs(q[0]) < _EPS and abs(q[1]) < _EPS and abs(q[2]) < _EPS and abs(abs(q[3]) - 1.0) < _EPS
        for q in quats)
    q0 = quats[0]
    is_static_rot = all(
        all(abs(q[j] - q0[j]) < _EPS for j in range(4))
        for q in quats)
    if is_identity_rot:
        rot_type = 'identity'
    elif is_static_rot:
        rot_type = 'static'
    else:
        rot_type = 'spline'

    # Scale
    scale_types = []
    for axis in range(3):
        vals = [track.scales[f][axis] for f in range(n_frames)]
        scale_types.append(_classify_axis(vals, 1.0))

    # Encode byte 0: quantization
    b0 = (_POS_QUANT & 0x03) | ((_ROT_QUANT & 0x0F) << 2) | ((_SCALE_QUANT & 0x03) << 6)

    # Encode byte 1: position flags
    b1 = 0
    for axis in range(3):
        if pos_types[axis] == 'static':
            b1 |= (1 << axis)
        elif pos_types[axis] == 'spline':
            b1 |= (1 << (axis + 4))
            b1 |= (1 << axis)  # Static bit also set for spline

    # Encode byte 2: rotation flags
    b2 = 0
    if rot_type == 'static':
        b2 = 0x0F
    elif rot_type == 'spline':
        b2 = 0xF0 | 0x0F

    # Encode byte 3: scale flags
    b3 = 0
    for axis in range(3):
        if scale_types[axis] == 'static':
            b3 |= (1 << axis)
        elif scale_types[axis] == 'spline':
            b3 |= (1 << (axis + 4))
            b3 |= (1 << axis)

    info = {'pos_types': pos_types, 'rot_type': rot_type, 'scale_types': scale_types}
    return bytes([b0, b1, b2, b3]), info


def _compress_block(all_tracks: List[TrackData], block_start_frame: int,
                    frames_in_block: int) -> bytes:
    """Compress one block of animation data for all tracks.

    Returns the compressed byte blob for this block.
    """
    num_tracks = len(all_tracks)
    out = bytearray()

    # 1. Write track masks
    masks = []
    infos = []
    for track in all_tracks:
        # Slice to this block's frames
        mask_bytes, info = _build_mask_bytes(track, frames_in_block)
        masks.append(mask_bytes)
        infos.append(info)
        out.extend(mask_bytes)
    _pad4(out)

    # 2. Per-track data
    for t_idx in range(num_tracks):
        track = all_tracks[t_idx]
        info = infos[t_idx]
        f0 = block_start_frame
        f1 = f0 + frames_in_block

        # ─── POSITION ───
        pos_types = info['pos_types']
        any_pos_spline = any(pt == 'spline' for pt in pos_types)

        if any_pos_spline:
            n_cp = frames_in_block
            degree = min(1, n_cp - 1)
            knots = _make_clamped_knots(n_cp, degree)

            # Header: num_items (u16) + degree (u8)
            out.extend(_w_u16(n_cp - 1))
            out.append(degree)
            # Knot vector
            for k in knots:
                out.append(min(255, k))
            _pad4(out)

            # Per-axis: min/max for spline, value for static
            axis_info = []
            for axis in range(3):
                ptype = pos_types[axis]
                vals = [track.translations[f][axis] for f in range(f0, f1)]
                if ptype == 'spline':
                    mn, mx = min(vals), max(vals)
                    if abs(mx - mn) < 1e-30:
                        mx = mn + 1e-6
                    out.extend(_w_f32(mn))
                    out.extend(_w_f32(mx))
                    axis_info.append(('spline', mn, mx, vals))
                elif ptype == 'static':
                    out.extend(_w_f32(vals[0]))
                    axis_info.append(('static', vals[0], vals[0], vals))
                else:
                    axis_info.append(('identity', 0.0, 0.0, vals))

            # Control points (interleaved across spline axes)
            for ax_idx, (atype, mn, mx, vals) in enumerate(axis_info):
                if atype == 'spline':
                    cps = _fit_bspline_scalar(degree, knots, n_cp, vals)
                    axis_info[ax_idx] = (atype, mn, mx, vals, cps)

            for cp_i in range(n_cp):
                for ax_idx, ai in enumerate(axis_info):
                    if ai[0] == 'spline':
                        cps = ai[4]
                        if _POS_QUANT == 0:
                            out.extend(_write_8bit_scalar(cps[cp_i], ai[1], ai[2]))
                        else:
                            out.extend(_write_16bit_scalar(cps[cp_i], ai[1], ai[2]))
            _pad4(out)
        else:
            # No splines — write static values only
            for axis in range(3):
                if pos_types[axis] == 'static':
                    val = track.translations[f0][axis]
                    out.extend(_w_f32(val))

        _pad4(out)

        # ─── ROTATION ───
        rot_type = info['rot_type']
        qalign = _QUAT_ALIGN.get(_ROT_QUANT, 4)

        if rot_type == 'spline':
            quats = [track.rotations[f] for f in range(f0, f1)]
            # Ensure quaternion continuity (flip if dot < 0)
            for i in range(1, len(quats)):
                dot = sum(quats[i][j] * quats[i-1][j] for j in range(4))
                if dot < 0:
                    quats[i] = [-c for c in quats[i]]

            n_cp = frames_in_block
            degree = min(1, n_cp - 1)
            knots = _make_clamped_knots(n_cp, degree)

            out.extend(_w_u16(n_cp - 1))
            out.append(degree)
            for k in knots:
                out.append(min(255, k))
            if qalign > 1:
                while len(out) % qalign:
                    out.append(0)

            # Fit B-spline to quaternions and write control points
            cps = _fit_bspline_quat(degree, knots, n_cp, quats)
            # Ensure CP continuity
            for i in range(1, len(cps)):
                dot = sum(cps[i][j] * cps[i-1][j] for j in range(4))
                if dot < 0:
                    cps[i] = [-c for c in cps[i]]

            for cp in cps:
                cp_n = _quat_normalize(cp)
                out.extend(_write_48bit_quat(cp_n))

        elif rot_type == 'static':
            if qalign > 1:
                while len(out) % qalign:
                    out.append(0)
            out.extend(_write_48bit_quat(track.rotations[f0]))

        # else identity: no data

        _pad4(out)

        # ─── SCALE ───
        scale_types = info['scale_types']
        any_scale_spline = any(st == 'spline' for st in scale_types)

        if any_scale_spline:
            n_cp = frames_in_block
            degree = min(1, n_cp - 1)
            knots = _make_clamped_knots(n_cp, degree)

            out.extend(_w_u16(n_cp - 1))
            out.append(degree)
            for k in knots:
                out.append(min(255, k))
            _pad4(out)

            axis_info = []
            for axis in range(3):
                stype = scale_types[axis]
                vals = [track.scales[f][axis] for f in range(f0, f1)]
                if stype == 'spline':
                    mn, mx = min(vals), max(vals)
                    if abs(mx - mn) < 1e-30:
                        mx = mn + 1e-6
                    out.extend(_w_f32(mn))
                    out.extend(_w_f32(mx))
                    axis_info.append(('spline', mn, mx, vals))
                elif stype == 'static':
                    out.extend(_w_f32(vals[0]))
                    axis_info.append(('static', vals[0], vals[0], vals))
                else:
                    axis_info.append(('identity', 1.0, 1.0, vals))

            for ax_idx, ai in enumerate(axis_info):
                if ai[0] == 'spline':
                    cps = _fit_bspline_scalar(degree, knots, n_cp, ai[3])
                    axis_info[ax_idx] = (ai[0], ai[1], ai[2], ai[3], cps)

            for cp_i in range(n_cp):
                for ax_idx, ai in enumerate(axis_info):
                    if ai[0] == 'spline':
                        cps = ai[4]
                        if _SCALE_QUANT == 0:
                            out.extend(_write_8bit_scalar(cps[cp_i], ai[1], ai[2]))
                        else:
                            out.extend(_write_16bit_scalar(cps[cp_i], ai[1], ai[2]))
            _pad4(out)
        else:
            for axis in range(3):
                if scale_types[axis] == 'static':
                    val = track.scales[f0][axis]
                    out.extend(_w_f32(val))

        _pad4(out)

    return bytes(out)


def _compress_all_blocks(anim: AnimationData) -> Tuple[bytes, List[int]]:
    """Compress all animation blocks. Returns (data_blob, block_offsets)."""
    max_fpb = anim.max_frames_per_block or 256
    num_blocks = anim.num_blocks or 1
    data = bytearray()
    block_offsets = []

    for block_idx in range(num_blocks):
        first_frame = block_idx * max_fpb
        if block_idx == num_blocks - 1:
            frames_in_block = anim.num_frames - first_frame
        else:
            frames_in_block = max_fpb

        # Slice tracks to this block's frame range
        block_tracks = []
        for track in anim.tracks:
            bt = TrackData()
            bt.translations = track.translations[first_frame:first_frame + frames_in_block]
            bt.rotations = track.rotations[first_frame:first_frame + frames_in_block]
            bt.scales = track.scales[first_frame:first_frame + frames_in_block]
            block_tracks.append(bt)

        block_offsets.append(len(data))
        block_data = _compress_block(block_tracks, 0, frames_in_block)
        data.extend(block_data)

    return bytes(data), block_offsets


# ═══════════════════════════════════════════════════════════════════════════════
#  Export: HKX packfile writer
# ═══════════════════════════════════════════════════════════════════════════════

_ANIM_CLASS_ENTRIES: List[Tuple[int, str]] = [
    (0x33D42383, 'hkClass'),
    (0xB0EFA719, 'hkClassMember'),
    (0x8A3609CF, 'hkClassEnum'),
    (0xCE6F8A6C, 'hkClassEnumItem'),
    (0x2772C11E, 'hkRootLevelContainer'),
    (0x26859F4C, 'hkaAnimationContainer'),
    (0x8C3B5F7E, 'hkaSplineCompressedAnimation'),
    (0x60F8E0B8, 'hkaDefaultAnimatedReferenceFrame'),
    (0x0FAF9150, 'hkaAnimationBinding'),
    (0x1DE13A73, 'hkMemoryResourceContainer'),
]


class _FixupBuilder:
    """Accumulates local, global, and virtual fixup entries."""
    def __init__(self):
        self.local: List[Tuple[int, int]] = []
        self.global_: List[Tuple[int, int, int]] = []
        self.virtual: List[Tuple[int, int, int]] = []

    def add_local(self, src_rel: int, dst_rel: int):
        self.local.append((src_rel, dst_rel))

    def add_global(self, src_rel: int, sec_idx: int, dst_rel: int):
        self.global_.append((src_rel, sec_idx, dst_rel))

    def add_virtual(self, obj_rel: int, sec_idx: int, name_off: int):
        self.virtual.append((obj_rel, sec_idx, name_off))

    def build_local_table(self) -> bytes:
        out = b''
        for src, dst in sorted(self.local):
            out += _w_u32(src) + _w_u32(dst)
        out += _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF)
        return out

    def build_global_table(self) -> bytes:
        out = b''
        for src, sec, dst in sorted(self.global_):
            out += _w_u32(src) + _w_u32(sec) + _w_u32(dst)
        out += _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF)
        return out

    def build_virtual_table(self) -> bytes:
        out = b''
        for obj, sec, noff in sorted(self.virtual):
            out += _w_u32(obj) + _w_u32(sec) + _w_u32(noff)
        out += _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF) + _w_u32(0xFFFFFFFF)
        return out


def _build_anim_classnames() -> Tuple[bytes, Dict[str, int]]:
    """Build __classnames__ section for animation HKX."""
    data = b''
    name_offs: Dict[str, int] = {}
    for hash_val, name in _ANIM_CLASS_ENTRIES:
        name_offs[name] = len(data) + 5
        data += struct.pack('<IB', hash_val, 0x09) + name.encode('ascii') + b'\x00'
    data = _pad16(data, fill=0xFF)
    return data, name_offs


def _anim_file_header(cn_name_off: int) -> bytes:
    """Build the 0x40-byte file header for a standalone HKX."""
    hdr = bytearray(0x40)
    hdr[0x00:0x04] = _HKX_MAGIC
    struct.pack_into('<i', hdr, 0x08, 0)          # userTag
    struct.pack_into('<i', hdr, 0x0C, 11)          # fileVersion
    hdr[0x10:0x14] = b'\x08\x01\x00\x01'          # layoutRules (64-bit LE)
    struct.pack_into('<i', hdr, 0x14, 3)           # numSections
    struct.pack_into('<i', hdr, 0x18, 2)           # contentsSectionIndex
    struct.pack_into('<i', hdr, 0x1C, 0)           # contentsSectionOffset
    struct.pack_into('<i', hdr, 0x20, 0)           # contentsClassNameSectionIndex
    struct.pack_into('<i', hdr, 0x24, cn_name_off) # contentsClassNameSectionOffset
    hdr[0x28:0x38] = b'hk_2014.1.0-r1\x00\xff'
    struct.pack_into('<i', hdr, 0x38, 0)           # flags
    struct.pack_into('<i', hdr, 0x3C, 21)          # maxPredicate
    return bytes(hdr)


def _anim_section_header(name: str, abs_start: int,
                         local_fix: int, global_fix: int,
                         virt_fix: int, exports: int) -> bytes:
    """Build a 0x40-byte section header."""
    hdr = bytearray(0x40)
    name_b = name.encode('ascii') + b'\x00'
    hdr[:len(name_b)] = name_b
    for i in range(len(name_b), 0x14):
        hdr[i] = 0xFF
    struct.pack_into('<I', hdr, 0x14, abs_start)
    struct.pack_into('<I', hdr, 0x18, local_fix - abs_start)
    struct.pack_into('<I', hdr, 0x1C, global_fix - abs_start)
    struct.pack_into('<I', hdr, 0x20, virt_fix - abs_start)
    struct.pack_into('<I', hdr, 0x24, exports - abs_start)
    struct.pack_into('<I', hdr, 0x28, exports - abs_start)
    struct.pack_into('<I', hdr, 0x2C, exports - abs_start)
    for i in range(0x30, 0x40):
        hdr[i] = 0xFF
    return bytes(hdr)


def _build_anim_data_section(anim: AnimationData, name_offs: Dict[str, int]) -> Tuple[bytes, '_FixupBuilder']:
    """Build the __data__ section object data for an animation HKX.

    Returns (object_data_bytes, fixup_builder).
    """
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

    # Compress the animation data
    spline_blob, block_offsets = _compress_all_blocks(anim)

    num_tracks = anim.num_tracks
    bone_names = anim.bone_names or [f"Bone{i}" for i in range(num_tracks)]
    skel_name = anim.original_skeleton_name or "Root"
    binding_indices = anim.track_to_bone_indices or list(range(num_tracks))

    # ═══ hkRootLevelContainer (0x00) ═══
    rlc_rel = rel()
    fx.add_virtual(rlc_rel, 0, name_offs['hkRootLevelContainer'])
    # namedVariants hkArray — 2 entries
    arr_rlc = write(_hkarray(2))
    align16()

    # namedVariant data: 2 entries, each 0x18 bytes (name_ptr + class_ptr + variant_ptr)
    nv_data_rel = rel()
    fx.add_local(arr_rlc, nv_data_rel)
    # Variant 0: animation container
    nv0_name = write(bytes(8))    # name ptr (patched)
    nv0_class = write(bytes(8))   # class ptr (patched)
    nv0_variant = write(bytes(8)) # variant ptr (patched)
    # Variant 1: resource data
    nv1_name = write(bytes(8))
    nv1_class = write(bytes(8))
    nv1_variant = write(bytes(8))
    align16()

    # Variant strings
    nv0_name_str = rel()
    write_string("Merged Animation Container")
    while len(data) % 2:
        data.append(0)
    nv0_class_str = rel()
    write_string("hkaAnimationContainer")
    while len(data) % 2:
        data.append(0)
    nv1_name_str = rel()
    write_string("Resource Data")
    while len(data) % 2:
        data.append(0)
    nv1_class_str = rel()
    write_string("hkMemoryResourceContainer")
    align16()

    # Fixups for variant name/class strings (local)
    fx.add_local(nv0_name, nv0_name_str)
    fx.add_local(nv0_class, nv0_class_str)
    fx.add_local(nv1_name, nv1_name_str)
    fx.add_local(nv1_class, nv1_class_str)

    # ═══ hkaAnimationContainer ═══
    ac_rel = rel()
    fx.add_virtual(ac_rel, 0, name_offs['hkaAnimationContainer'])
    fx.add_local(nv0_variant, ac_rel)  # RLC variant[0] → here

    # 6 hkArrays: skeletons(0), animations(1), bindings(1), attachments(0), skins(0), pad
    write(_hkarray(0))          # +0x00: skeletons
    arr_anims = write(_hkarray(1))  # +0x10: animations
    arr_binds = write(_hkarray(1))  # +0x20: bindings
    write(_hkarray(0))          # +0x30: attachments
    write(_hkarray(0))          # +0x40: skins
    write(bytes(0x30))          # pad to 0x80
    align16()

    # Animation pointer array (1 entry, 8 bytes)
    anim_ptr_array_rel = rel()
    fx.add_local(arr_anims, anim_ptr_array_rel)
    anim_ptr = write(bytes(8))  # ptr → hkaSplineCompressedAnimation

    # Binding pointer array (1 entry, 8 bytes)
    bind_ptr_array_rel = rel()
    fx.add_local(arr_binds, bind_ptr_array_rel)
    bind_ptr = write(bytes(8))  # ptr → hkaAnimationBinding
    align16()

    # ═══ hkaSplineCompressedAnimation ═══
    spline_rel = rel()
    fx.add_virtual(spline_rel, 0, name_offs['hkaSplineCompressedAnimation'])
    fx.add_local(anim_ptr, spline_rel)  # AnimContainer.animations[0] → here

    # hkaAnimation base: type(u32) + pad + ... (0x28 bytes base, then specific fields)
    # Simplified: write 0xA8 bytes for the full hkaSplineCompressedAnimation header
    spline_hdr = bytearray(0xA8)
    struct.pack_into('<I', spline_hdr, 0x00, 3)    # type = HK_SPLINE_COMPRESSED_ANIMATION
    # +0x10: annotationTracks hkArray → filled below
    struct.pack_into('<f', spline_hdr, 0x14, anim.duration)
    struct.pack_into('<I', spline_hdr, 0x18, num_tracks)
    # +0x20: extractedMotion ptr → filled below
    # +0x28: annotationTracks hkArray → filled below
    struct.pack_into('<I', spline_hdr, 0x38, anim.num_frames)
    struct.pack_into('<I', spline_hdr, 0x3C, anim.num_blocks or 1)
    struct.pack_into('<I', spline_hdr, 0x40, anim.max_frames_per_block or 256)
    # +0x44: maskAndQuantizationSize (will compute)
    struct.pack_into('<f', spline_hdr, 0x48, anim.block_duration)
    # +0x4C: inverseDuration
    if anim.duration > 0:
        struct.pack_into('<f', spline_hdr, 0x4C, 1.0 / anim.block_duration if anim.block_duration > 0 else 0.0)
    struct.pack_into('<f', spline_hdr, 0x50, anim.frame_duration)
    # hkArrays at known offsets (relative to spline_rel):
    # +0x58: blockOffsets
    # +0x68: floatBlockOffsets
    # +0x78: transformOffsets
    # +0x88: floatOffsets
    # +0x98: data (the spline blob)
    n_blocks = anim.num_blocks or 1
    struct.pack_into('<I', spline_hdr, 0x58 + 8, n_blocks)
    struct.pack_into('<I', spline_hdr, 0x58 + 12, n_blocks | 0x80000000)
    struct.pack_into('<I', spline_hdr, 0x98 + 8, len(spline_blob))
    struct.pack_into('<I', spline_hdr, 0x98 + 12, len(spline_blob) | 0x80000000)

    # Compute maskAndQuantizationSize (bytes of mask data per block = 4 * numTracks, aligned)
    mask_size = _align(4 * num_tracks, 4)
    struct.pack_into('<I', spline_hdr, 0x44, mask_size)

    # annotationTracks array
    struct.pack_into('<I', spline_hdr, 0x28 + 8, num_tracks)
    struct.pack_into('<I', spline_hdr, 0x28 + 12, num_tracks | 0x80000000)

    write(bytes(spline_hdr))
    align16()

    # Annotation track structs (0x18 each: name_ptr + annotations hkArray)
    annot_tracks_rel = rel()
    fx.add_local(spline_rel + 0x28, annot_tracks_rel)
    annot_track_offsets = []
    for i in range(num_tracks):
        at_rel = rel()
        annot_track_offsets.append(at_rel)
        write(bytes(8))      # name ptr
        write(_hkarray(0))   # annotations (empty for now)

    # Annotation track name strings
    for i in range(num_tracks):
        name_str_rel = rel()
        name = bone_names[i] if i < len(bone_names) else ""
        write_string(name)
        fx.add_local(annot_track_offsets[i], name_str_rel)
    align16()

    # Block offsets array
    block_off_data_rel = rel()
    fx.add_local(spline_rel + 0x58, block_off_data_rel)
    for bo in block_offsets:
        write(_w_u32(bo))
    align16()

    # Spline data blob
    spline_data_rel = rel()
    fx.add_local(spline_rel + 0x98, spline_data_rel)
    write(spline_blob)
    align16()

    # extractedMotion → hkaDefaultAnimatedReferenceFrame
    ref_frame_rel = rel()
    fx.add_virtual(ref_frame_rel, 0, name_offs['hkaDefaultAnimatedReferenceFrame'])
    fx.add_local(spline_rel + 0x20, ref_frame_rel)

    # hkaDefaultAnimatedReferenceFrame: 0x70 header + referenceFrameSamples
    ref_hdr = bytearray(0x70)
    # +0x10: up vec4 = (0,0,1,0)
    struct.pack_into('<ffff', ref_hdr, 0x10, 0.0, 0.0, 1.0, 0.0)
    # +0x20: forward vec4 = (0,1,0,0)
    struct.pack_into('<ffff', ref_hdr, 0x20, 0.0, 1.0, 0.0, 0.0)
    # +0x30: duration
    struct.pack_into('<f', ref_hdr, 0x30, anim.duration)
    # +0x58: referenceFrameSamples hkArray
    n_samples = anim.num_frames + 1
    struct.pack_into('<I', ref_hdr, 0x58 + 8, n_samples)
    struct.pack_into('<I', ref_hdr, 0x58 + 12, n_samples | 0x80000000)
    write(bytes(ref_hdr))

    # referenceFrameSamples data (vec4 per sample, all zeros = no root motion)
    ref_samples_rel = rel()
    fx.add_local(ref_frame_rel + 0x58, ref_samples_rel)
    write(bytes(16 * n_samples))
    align16()

    # ═══ hkaAnimationBinding ═══
    binding_rel = rel()
    fx.add_virtual(binding_rel, 0, name_offs['hkaAnimationBinding'])
    fx.add_local(bind_ptr, binding_rel)  # AnimContainer.bindings[0] → here

    bind_hdr = bytearray(0x58)
    # +0x10: originalSkeletonName ptr → filled below
    # +0x18: animation ptr → filled below (global to spline)
    # +0x20: transformTrackToBoneIndices hkArray
    struct.pack_into('<I', bind_hdr, 0x20 + 8, len(binding_indices))
    struct.pack_into('<I', bind_hdr, 0x20 + 12, len(binding_indices) | 0x80000000)
    # +0x30: floatTrackToFloatSlotIndices (empty)
    # +0x50: blendHint = 0
    write(bytes(bind_hdr))

    # Skeleton name string
    skel_name_rel = rel()
    write_string(skel_name)
    fx.add_local(binding_rel + 0x10, skel_name_rel)
    while len(data) % 2:
        data.append(0)

    # Animation ptr (local fixup within data section)
    fx.add_local(binding_rel + 0x18, spline_rel)

    # Binding indices array
    bind_idx_rel = rel()
    fx.add_local(binding_rel + 0x20, bind_idx_rel)
    for idx in binding_indices:
        write(_w_i16(idx))
    align16()

    # ═══ hkMemoryResourceContainer ═══
    mrc_rel = rel()
    fx.add_virtual(mrc_rel, 0, name_offs['hkMemoryResourceContainer'])
    fx.add_local(nv1_variant, mrc_rel)  # RLC variant[1] → here
    write(bytes(0x40))
    align16()

    return bytes(data), fx


def write_fo4_animation(filepath: str, anim: AnimationData) -> None:
    """Write an AnimationData to a FO4 HKX binary file.

    Parameters
    ----------
    filepath : str
        Output path for the .hkx file.
    anim : AnimationData
        Must have tracks, duration, num_frames, frame_duration populated.
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
    cn_data, name_offs = _build_anim_classnames()
    obj_data, fx = _build_anim_data_section(anim, name_offs)

    local_tbl = fx.build_local_table()
    global_tbl = fx.build_global_table()
    virt_tbl = fx.build_virtual_table()
    data_section = obj_data + local_tbl + global_tbl + virt_tbl

    # Standalone HKX layout:
    # 0x00: file header (0x40)
    # 0x40: 16 bytes padding
    # 0x50: section header 0 (0x40)
    # 0x90: section header 1 (0x40)
    # 0xD0: section header 2 (0x40)
    # 0x110: classnames data
    # cn_end: data section
    cn_start = 0x110
    cn_end = cn_start + len(cn_data)
    data_start = cn_end

    local_fix_abs = data_start + len(obj_data)
    global_fix_abs = local_fix_abs + len(local_tbl)
    virt_fix_abs = global_fix_abs + len(global_tbl)
    data_end = virt_fix_abs + len(virt_tbl)

    cn_name_off = name_offs['hkRootLevelContainer']
    hdr = _anim_file_header(cn_name_off)

    # 16-byte padding block at 0x40
    padding = bytearray(16)
    padding[0:2] = struct.pack('<H', 0x10)

    shdr0 = _anim_section_header('__classnames__', cn_start,
                                  cn_start + len(cn_data), cn_start + len(cn_data),
                                  cn_start + len(cn_data), cn_start + len(cn_data))
    shdr1 = _anim_section_header('__types__', cn_end,
                                  cn_end, cn_end, cn_end, cn_end)
    shdr2 = _anim_section_header('__data__', data_start,
                                  local_fix_abs, global_fix_abs,
                                  virt_fix_abs, data_end)

    result = hdr + bytes(padding) + shdr0 + shdr1 + shdr2 + cn_data + data_section

    with open(filepath, 'wb') as f:
        f.write(result)


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <animation.hkx|animation.xml>")
        sys.exit(1)

    filepath = sys.argv[1]

    print(f"Loading: {filepath}")
    print()

    anim = load_fo4_animation(filepath)
    print(anim.summary())


if __name__ == '__main__':
    main()
