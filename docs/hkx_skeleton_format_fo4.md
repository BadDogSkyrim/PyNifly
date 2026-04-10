# FO4 HKX skeleton file format

Notes on the binary `skeleton.hkx` format used by Fallout 4
(`hk_2014.1.0` packfile, 64-bit pointers exclusively). Findings come
from reverse engineering all 8 vanilla FO4 skeleton files; the writer in
[`io_scene_nifly/hkx/anim_fo4.py`](../io_scene_nifly/hkx/anim_fo4.py)
(`write_fo4_skeleton`) and the parser in the same file
(`_parse_skeleton_hkx`) implement parsing and writing.

For the surrounding packfile container (file header, section headers,
fixup tables, hkArray layout) see [`hkx_animation_format.md`](hkx_animation_format.md)
— skeleton and animation files share the same wrapper. This document
covers only what's specific to FO4 skeletons.

For the Skyrim equivalent (hk_2010), see
[`hkx_skeleton_format.md`](hkx_skeleton_format.md).

## Key differences from Skyrim

| | Skyrim LE/SE | Fallout 4 |
|---|---|---|
| Havok version | hk_2010.2.0-r1 | hk_2014.1.0 |
| Pointer size | 4 (LE) or 8 (SE) | Always 8 |
| hkaSkeleton hash | `0x366E8220` | `0xFEC1CEDB` |
| hkaSkeleton arrays | 6 | 7 (extra `partitions`) |
| hkaBone stride | 8 (LE) / 16 (SE) | Always 16 |
| Bone naming convention | `NPC Root [Root]` | `Root` |
| Float slots | Up to 8 (human) | 0 across all vanilla |
| hkxcmd support | LE only (ptr_size=4) | None (64-bit only) |

## Object graph

Identical to Skyrim — a skeleton.hkx contains four Havok objects in the
`__data__` section:

```
hkRootLevelContainer
  └─ namedVariants[2]
       ├─ "Merged Animation Container" → hkaAnimationContainer
       │                                   └─ skeletons[1] → hkaSkeleton
       └─ "Resource Data"               → hkMemoryResourceContainer
```

`hkaAnimationContainer.animations`, `bindings`, `attachments`, and
`skins` are all empty for a skeleton-only file. Only `skeletons[]` is
populated, with exactly one entry. `hkMemoryResourceContainer` is empty.

## hkaSkeleton struct layout

Pointer size `P` is always 8. `arr_sz = 16` (hkArray = ptr(8) +
count(4) + capacityAndFlags(4)). `base_sz = 16` (hkReferencedObject
base, vtable(8) + memSizeAndFlags(8)).

| Offset | Size | Field | Notes |
|---|---|---|---|
| `0x00` | 16 | hkReferencedObject base | Zeroed in file |
| `0x10` | 8 | `name` | Pointer to null-terminated string |
| `0x18` | 16 | `parentIndices` | hkArray\<int16\> |
| `0x28` | 16 | `bones` | hkArray\<hkaBone\> |
| `0x38` | 16 | `referencePose` | hkArray\<hkQsTransform\> |
| `0x48` | 16 | `referenceFloats` | hkArray\<float\> |
| `0x58` | 16 | `floatSlots` | hkArray\<hkStringPtr\> |
| `0x68` | 16 | `localFrames` | hkArray\<hkLocalFrameOnBone\> |
| `0x78` | 16 | `partitions` | hkArray\<hkaPartition\> (FO4 only) |

Total size: `16 + 8 + 7×16 = 136 bytes (0x88)`, padded to `0x90`.

The 7th array (`partitions`) is the only structural difference from
Skyrim's hkaSkeleton. It is always empty in vanilla FO4 files.

### hkaBone

| Offset | Size | Field |
|---|---|---|
| `0x00` | 8 | `name` (string ptr) |
| `0x08` | 4 | `lockTranslation` (int32, treated as bool) |
| `0x0C` | 4 | padding (aligns to 16) |

Bone stride is always **16 bytes (`0x10`)**.

### hkQsTransform (referencePose entry)

48 bytes (`0x30`), identical to Skyrim — SIMD-aligned, three vec4 fields:

| Offset | Size | Field |
|---|---|---|
| `0x00` | 16 | translation (3 floats + pad) |
| `0x10` | 16 | rotation (xyzw quaternion) |
| `0x20` | 16 | scale (3 floats + pad) |

### parentIndices

Array of `int16`, one per bone. `-1` for top-level (root) bones.
Children always come after their parent in the bone list.

## Class names section

A skeleton-only file's `__classnames__` section contains these classes:

| Hash | Tag | Name |
|---|---|---|
| `0x33D42383` | `0x09` | `hkClass` |
| `0xB0EFA719` | `0x09` | `hkClassMember` |
| `0x8A3609CF` | `0x09` | `hkClassEnum` |
| `0xCE6F8A6C` | `0x09` | `hkClassEnumItem` |
| `0x2772C11E` | `0x09` | `hkRootLevelContainer` |
| `0x26859F4C` | `0x09` | `hkaAnimationContainer` |
| `0xFEC1CEDB` | `0x09` | `hkaSkeleton` |
| `0x1DE13A73` | `0x09` | `hkMemoryResourceContainer` |

Note that `hkClass`, `hkClassMember`, `hkaAnimationContainer`, and
`hkMemoryResourceContainer` all have **different hashes** from Skyrim's
hk_2010 versions. Only `hkClassEnum`, `hkClassEnumItem`, and
`hkRootLevelContainer` share the same hashes.

## Vanilla survey

A scan of all 8 vanilla FO4 `skeleton*.hkx` files. These shaped the
design of the writer.

### `lockTranslation` (per-bone bool)

| File | Bones | Locked | Unlocked bones |
|---|---|---|---|
| Human `skeleton.hkx` | 95 | 93 | `Root`, `COM` |
| Human `_1stPerson/skeleton.hkx` | 94 | 0 | (all unlocked) |
| CreateABot | 116 | 114 | `Root`, `COM` |
| Deathclaw | 86 | 84 | `Root`, `COM` |
| Alien | 83 | 81 | `Root`, `COM` |
| Bloatfly | 46 | 44 | `Root`, `Pelvis` |
| Brahmin | 47 | 45 | `Root [Root]`, `Pelvis` |
| Cat | 35 | 11 | (extensive — see below) |

The dominant pattern is simple: only `Root` and `COM` (or `Pelvis` for
some creatures) are unlocked. FO4 is much more consistent than Skyrim
here — no `x_NPC` scratch nodes.

**Cat** is the outlier: it unlocks the entire body chain (spine, neck,
head, all four legs, ears, jaw) — 24 of 35 bones. Similar to Skyrim's
frost atronach, this is presumably because the cat's walk cycle uses
translation on limb joints.

**1st-person skeleton** has zero locked bones, same pattern as Skyrim.
Likely an oversight; the 1st-person camera doesn't run physics.

**Brahmin** is the only file that uses Skyrim-style bracket naming
(`Root [Root]`) instead of the plain `Root` convention used everywhere
else in FO4.

### `referenceFloats` and `floatSlots`

**Zero of 8 vanilla FO4 skeletons populate float slots.** This is a
significant difference from Skyrim, where the human skeleton carries 8
float slots for visibility/fade control. FO4 presumably handles weapon
visibility and prop fading through a different mechanism.

The writer still supports float slots for round-tripping (modded
skeletons may use them), but the default is empty.

### `localFrames`

**Zero of 8 vanilla FO4 skeletons populate this field.** Same as
Skyrim. The writer always emits an empty array.

### `partitions`

**Zero of 8 vanilla FO4 skeletons populate partitions.** This array
exists in FO4's hkaSkeleton but is never used. The writer always emits
an empty array.

### `hkaSkeleton.name` vs root bone name

Same as Skyrim: across all 8 vanilla files, the skeleton `name` field
always matches `bones[0].name`. The writer forces them equal.

## hkMemoryResourceContainer struct layout

Empty in skeleton-only files. Total size is 80 bytes (`0x50`).
The `externalLinks` and `objectData` arrays have
`capacityAndFlags = 0x80000000` (empty-but-flagged).

## Round-trip preservation in PyNifly

Same properties as Skyrim — see
[`hkx_skeleton_format.md`](hkx_skeleton_format.md#round-trip-preservation-in-pynifly).

| Field | Stored on | Property |
|---|---|---|
| `bones[].lockTranslation` | per-bone | `PYN_HKX_LOCK_TRANSLATION` (bool) |
| `floatSlots` | armature object | `PYN_HKX_FLOAT_SLOTS` (`;`-joined string) |
| `referenceFloats` | armature object | `PYN_HKX_REFERENCE_FLOATS` (float list) |

If `PYN_HKX_LOCK_TRANSLATION` is missing, the export uses a default
heuristic: unlock `Root` and `COM`, lock everything else.

`localFrames` and `partitions` are not preserved — no vanilla file uses
either.

**Bone ordering** is critical — see the Skyrim doc for details on
`PYN_HKX_BONES` and the reorder logic in
`extract_skeleton_from_armature`.
