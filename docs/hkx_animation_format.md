# HKX Animation Format (FO4 + Skyrim)

PyNifly implements complete HKX animation import/export in pure Python for
Fallout 4 and Skyrim LE/SE, with no dependency on external tools like hkxcmd.

## Overview

Bethesda games store character animations in Havok HKX files — binary packfiles
containing compressed animation tracks, skeleton definitions, and event
annotations. Each animation file references a skeleton, and together they define
how bones move over time.

```
Skeleton.hkx          ← bone hierarchy + rest pose
  referenced by
Animation.hkx         ← compressed bone transforms per frame
  applied to
Character NIF          ← mesh with skinned bones
```

## File Relationships

A character's animation system involves three file types:

**Skeleton HKX** (e.g. `skeleton.hkx`)
- Defines bone names, hierarchy (parent indices), and reference pose
- One per character type (human, dog, deathclaw, etc.)
- Contains: `hkaSkeleton`

**Animation HKX** (e.g. `idle.hkx`, `walk.hkx`)
- Contains compressed bone transforms for each frame
- References a skeleton by name via the binding
- Contains: `hkaSplineCompressedAnimation`, `hkaAnimationBinding`, annotations

**Character NIF** (e.g. `body.nif`)
- Skinned mesh with bone weights
- Bones must match the skeleton's bone names
- NIF bones are a subset of the full skeleton

## HKX Packfile Structure

### File Layout

```
0x00    File header (0x40 bytes)
0x40    Padding block (16 bytes, FO4 only)
0x50    Section header 0: __classnames__
0x90    Section header 1: __types__ (empty)
0xD0    Section header 2: __data__
0x110   Classnames data
        Data section (objects + fixup tables)
```

### Version Differences

| | FO4 | Skyrim SE | Skyrim LE |
|---|-----|-----------|-----------|
| Havok version | hk_2014.1.0-r1 | hk_2010.2.0-r1 | hk_2010.2.0-r1 |
| File version | 11 | 8 | 8 |
| Pointer size | 8 bytes | 8 bytes | 4 bytes |
| Padding block | Yes (16 bytes) | No | No |
| Section header | 0x40 bytes | 0x30 bytes | 0x30 bytes |
| hkArray size | 16 bytes | 16 bytes | 12 bytes |

### Pointer Resolution (Fixups)

HKX files don't store raw pointers. Instead, three fixup tables resolve
references at load time:

**Local fixups** — within the __data__ section:
```
(source_offset, destination_offset)     terminated by (0xFFFFFFFF, 0xFFFFFFFF)
```
Maps a pointer field to the data it points to. Used for hkArray data pointers,
string pointers, and object references within the same section.

**Virtual fixups** — class instantiation:
```
(object_offset, section_index, classname_offset)
```
Marks where each Havok object starts and what class it is. The parser uses
these to find `hkaSplineCompressedAnimation`, `hkaAnimationBinding`, etc.

**Global fixups** — cross-section references (rarely used in animation files).

## Havok Classes

### hkaSkeleton

Defines the bone hierarchy and rest pose.

```
+0x10   name            string pointer
+0x18   parentIndices   hkArray<int16>     parent bone index per bone (-1 = root)
+0x28   bones           hkArray<hkaBone>   bone names
+0x38   referencePose   hkArray<hkQsTransform>   local rest transforms
```

Each `hkQsTransform` is 48 bytes:
```
+0x00   translation     vec4 (xyz + pad)    16 bytes
+0x10   rotation        quaternion (xyzw)   16 bytes
+0x20   scale           vec4 (xyz + pad)    16 bytes
```

Note: Havok quaternions are stored as (x, y, z, w), not Blender's (w, x, y, z).

### hkaSplineCompressedAnimation

The main animation data. Bone transforms are stored as B-spline compressed
blocks.

```
+0x10   type                int32 (3 = SPLINE_COMPRESSED)
+0x14   duration            float32 (seconds)
+0x18   numTransformTracks  int32
+0x1C   numFloatTracks      int32 (usually 0)
+0x20   extractedMotion     pointer (root motion, usually zeros)
+0x28   annotationTracks    hkArray<hkaAnnotationTrack>
+0x38   numFrames           int32
+0x3C   numBlocks           int32
+0x40   maxFramesPerBlock   int32 (typically 256)
+0x44   maskAndQuantSize    int32 (bytes of mask data per block)
+0x48   blockDuration       float32
+0x4C   blockInvDuration    float32 (1 / blockDuration)
+0x50   frameDuration       float32 (1 / (numFrames - 1))
+0x58   blockOffsets         hkArray<uint32>
+0x98   data                hkArray<uint8>   ← the compressed spline blob
```

(Offsets shown for FO4 64-bit; Skyrim offsets differ due to pointer size.)

### hkaAnimationBinding

Links an animation to a skeleton, mapping tracks to bones.

```
+0x10   originalSkeletonName    string pointer
+0x18   animation               pointer to hkaSplineCompressedAnimation
+0x20   transformTrackToBone    hkArray<int16>
+0x40   blendHint              int32 (0=NORMAL, 1=ADDITIVE)
```

`transformTrackToBone[i]` tells you which skeleton bone index track `i`
animates. An animation may only animate a subset of the skeleton's bones.

### hkaAnnotationTrack

Text events at specific times (sound cues, effect triggers, etc.).

```
+0x00   trackName       string pointer (bone name this track belongs to)
+0x08   annotations     hkArray<hkaAnnotation>
```

Each annotation is `{float time, string text}`.

## Spline Compression

Animation tracks are divided into blocks (typically 256 frames each). Each
block is independently compressed using B-spline fitting.

### Per-Track Mask Bytes

Each track has 4 mask bytes that describe how its channels are stored:

```
Byte 0: quantization format
    Bits [0:2]  Position quantization (0=8-bit, 1=16-bit)
    Bits [2:6]  Rotation quantization (typically 2 = 48-bit quaternion)
    Bits [6:8]  Scale quantization

Byte 1: position flags
    Bits [0:3]  Static flag per axis (X, Y, Z)
    Bits [4:7]  Spline flag per axis

Byte 2: rotation flags
    Bits [0:4]  Static flag
    Bits [4:8]  Spline flag

Byte 3: scale flags (same layout as position)
```

Three states per channel:
- **Identity** — no bits set; use default (0,0,0 for position; 0,0,0,1 for rotation; 1,1,1 for scale)
- **Static** — static bit set; one value stored, constant across all frames
- **Spline** — spline bit set; B-spline with control points

### Spline Data

For each spline channel, the data contains:

```
numItems    uint16      control point count - 1
degree      uint8       B-spline degree (typically 1 = linear)
knots       uint8[]     knot vector (numItems + degree + 2 values)
[padding to 4-byte alignment]
```

Followed by the control points in quantized form.

### Quantization

**Position/Scale (16-bit per axis):**
```
Stored:  min (float32), max (float32), then uint16 control points
Decode:  value = min + (max - min) * (uint16 / 65535.0)
```

**Rotation (48-bit quaternion):**

Three components stored as 15-bit signed values; the fourth (largest) is
reconstructed from the unit quaternion constraint.

```
6 bytes = 3 x uint16

shift = ((y_raw >> 14) & 2) | ((x_raw >> 15) & 1)    # which component reconstructed
sign  = (z_raw >> 15) != 0                             # sign of reconstructed component

stored[i] = ((raw[i] & 0x7FFF) - 0x3FFF) * 0.000043161

reconstructed = sqrt(max(0, 1 - sum(stored[i]^2)))
if sign: reconstructed = -reconstructed
```

The `shift` value (0-3) determines which of w/x/y/z is the reconstructed
component.

### B-Spline Evaluation

Control points are evaluated using De Boor's algorithm. With degree 1 (linear),
this reduces to simple linear interpolation between adjacent control points.

The knot vector determines which control points influence each frame. For
degree-1 splines with N control points, knots are typically:

```
[0, 0, 1, 2, 3, ..., N-2, N-1, N-1]    (clamped uniform)
```

## Blender Integration

### Skeleton Import

1. Parse `hkaSkeleton` from HKX
2. Compute global transforms by chaining local reference poses up the hierarchy
3. Create Blender armature with bones positioned at global transforms
4. Store bone name list on armature as `PYN_HKX_BONES` custom property

### Animation Import

The key challenge is converting between HKX's absolute bone-local transforms
and Blender's delta-from-rest-pose representation.

**For NORMAL animations (blendHint=0):**
```
rotation_delta = rest_rotation.inverted() @ anim_rotation
translation_delta = rest_rotation.inverted() @ (anim_translation - rest_translation)
```

**For ADDITIVE animations (blendHint=1):**
```
rotation_delta = anim_rotation       (already a delta)
translation_delta = anim_translation
```

Bone mapping uses `transformTrackToBone` indices from the binding to map
animation tracks to skeleton bones.

### Animation Export

Reverse of import:
1. Sample Blender pose bones at each frame
2. Convert back to HKX absolute transforms
3. Classify each channel (identity/static/spline)
4. Fit B-splines to frame values
5. Quantize and pack into blocks
6. Build HKX packfile with fixup tables

### Armature Properties

Custom properties stored on Blender armatures:

| Property | Description |
|----------|-------------|
| `PYN_HKX_BONES` | Semicolon-separated NIF bone names |
| `PYN_HKX_GAME` | 'FO4' or 'SKYRIM' |
| `PYN_HKX_PTR_SIZE` | 4 (LE) or 8 (SE/FO4) |
| `PYN_HKX_ADDITIVE` | True if additive animation |

## Annotations (Timeline Markers)

HKX annotations map to Blender timeline markers:

```
HKX:     {time: 0.5, text: "SoundPlay.footstep"}
Blender: marker at frame 15 (at 30 fps) named "SoundPlay.footstep"
```

## Limitations

- No root motion export (reference frame samples always zero)
- No float tracks (morph target animations)
- B-spline degree limited to 0 (constant) and 1 (linear), not cubic
- All annotation events stored on track 0

## Architecture

```
[HKX Binary File]
        |
        v
[Packfile Parser]  ──  parse sections, fixups, find objects by class
        |
        v
[Object Extraction]  ──  read hkaSplineCompressedAnimation fields
        |
        v
[Spline Decompression]  ──  expand B-splines to per-frame values
        |
        v
[AnimationData]  ──  in-memory, fully expanded
        |                           |
        v (import)                  v (export)
[Blender fcurves]              [B-spline Fitting]
                                    |
                                    v
                               [Block Compression]
                                    |
                                    v
                               [HKX Binary File]
```

## Using the Tools

### Load and Inspect an Animation

```python
import sys
sys.path.insert(0, 'io_scene_nifly/hkx')
from anim_fo4 import load_fo4_animation

anim = load_fo4_animation("idle.hkx")
print(f"{anim.duration:.2f}s, {anim.num_frames} frames, {anim.num_tracks} tracks")
for i, name in enumerate(anim.bone_names):
    t = anim.tracks[i]
    print(f"  {name}: {len(t.rotations)} rot keys, {len(t.translations)} pos keys")
```

### Load a Skeleton

```python
from anim_fo4 import load_fo4_skeleton

skel = load_fo4_skeleton("skeleton.hkx")
for i, bone in enumerate(skel.bones):
    parent = skel.parents[i]
    pose = skel.reference_pose[i]
    print(f"  {bone} (parent={parent}) pos={pose.translation} rot={pose.rotation}")
```

### Write an Animation

```python
from anim_fo4 import write_fo4_animation, AnimationData, TrackData

anim = AnimationData()
anim.duration = 1.0
anim.num_frames = 31
anim.num_tracks = 1
anim.bone_names = ["Pelvis"]
anim.tracks = [TrackData(
    translations=[[0, 0, i * 0.01] for i in range(31)],
    rotations=[[0, 0, 0, 1]] * 31,
    scales=[[1, 1, 1]] * 31,
)]
write_fo4_animation("output.hkx", anim)
```

## References

- PyNifly source: `io_scene_nifly/hkx/anim_fo4.py`, `anim_skyrim.py`
- Havok SDK documentation (not publicly available)
- [niftools wiki](https://github.com/niftools/nifxml/wiki)
