# Skyrim HKX skeleton file format

Notes on the binary `skeleton.hkx` format used by Skyrim LE and SE
(`hk_2010.2.0-r1` packfile, classversion 8). For the FO4 equivalent
(hk_2014), see [`hkx_skeleton_format_fo4.md`](hkx_skeleton_format_fo4.md).

Findings come from reverse
engineering all 50 vanilla SE skeleton files; the writer in
[`io_scene_nifly/hkx/anim_skyrim.py`](../io_scene_nifly/hkx/anim_skyrim.py)
(`write_skyrim_skeleton`) and the parser in the same file
(`_parse_skeleton_hkx`) implement parsing and writing.

For the surrounding packfile container (file header, section headers,
fixup tables, hkArray layout) see [`hkx_animation_format.md`](hkx_animation_format.md)
— skeleton and animation files share the same wrapper. This document
covers only what's specific to skeletons.

## Object graph

A skeleton.hkx contains four Havok objects in the `__data__` section:

```
hkRootLevelContainer
  └─ namedVariants[2]
       ├─ "Merged Animation Container" → hkaAnimationContainer
       │                                   └─ skeletons[1] → hkaSkeleton
       └─ "Resource Data"               → hkMemoryResourceContainer
```

`hkaAnimationContainer.animations`, `bindings`, `attachments`, and
`skins` are all empty for a skeleton-only file. Only `skeletons[]` is
populated, with exactly one entry. `hkMemoryResourceContainer.resourceHandles`
and `children` are empty.

## hkaSkeleton struct layout

Pointer size `P` is 4 (LE) or 8 (SE), read from byte `0x10` of the file
header. Animation files commonly use `P=4`; vanilla `skeleton.hkx` always
uses `P=8`. `arr_sz = P + 8` (hkArray = ptr + count(4) + capacityAndFlags(4)).
`base_sz = 2*P` (hkReferencedObject base, vtable + memSizeAndFlags).

| Offset | Size | Field | Notes |
|---|---|---|---|
| `0x00` | base_sz | hkReferencedObject base | Zeroed in file; resolved at load time |
| base_sz | P | `name` | Pointer to null-terminated string |
| base_sz + P | arr_sz | `parentIndices` | hkArray<int16> |
| base_sz + P + arr_sz | arr_sz | `bones` | hkArray<hkaBone> |
| base_sz + P + 2·arr_sz | arr_sz | `referencePose` | hkArray<hkQsTransform> |
| base_sz + P + 3·arr_sz | arr_sz | `referenceFloats` | hkArray<float> |
| base_sz + P + 4·arr_sz | arr_sz | `floatSlots` | hkArray<hkStringPtr> |
| base_sz + P + 5·arr_sz | arr_sz | `localFrames` | hkArray<hkLocalFrameOnBone> |

LE total size: `8 + 4 + 6×12 = 84 bytes`. SE total: `16 + 8 + 6×16 = 120 bytes`.

### hkaBone

| Offset | Size | Field |
|---|---|---|
| `0x00` | P | `name` (string ptr) |
| P | 4 | `lockTranslation` (int32, treated as bool) |
| P+4 | pad | aligns total to `8` (LE) or `16` (SE) |

Bone stride is **8 bytes (LE)** or **16 bytes (SE)**.

### hkQsTransform (referencePose entry)

48 bytes (`0x30`), same on both LE and SE — SIMD-aligned, three vec4 fields:

| Offset | Size | Field |
|---|---|---|
| `0x00` | 16 | translation (3 floats + pad) |
| `0x10` | 16 | rotation (xyzw quaternion) |
| `0x20` | 16 | scale (3 floats + pad) |

### parentIndices

Array of `int16`, one per bone. `-1` for top-level (root) bones.
Children always come *after* their parent in the bone list — vanilla
files preserve this convention and the writer assumes it.

## Class names section

A skeleton-only file's `__classnames__` section is small. Only these
classes are needed (in vanilla order):

| Hash | Tag | Name |
|---|---|---|
| `0x75585EF6` | `0x09` | `hkClass` |
| `0x5C7EA4C2` | `0x09` | `hkClassMember` |
| `0x8A3609CF` | `0x09` | `hkClassEnum` |
| `0xCE6F8A6C` | `0x09` | `hkClassEnumItem` |
| `0x2772C11E` | `0x09` | `hkRootLevelContainer` |
| `0x8DC20333` | `0x09` | `hkaAnimationContainer` |
| `0x366E8220` | `0x09` | `hkaSkeleton` |
| `0x4762F92A` | `0x09` | `hkMemoryResourceContainer` |

The **`hkaSkeleton` hash `0x366E8220`** was extracted from the human SE
`skeleton.hkx` and verified identical across all 50 vanilla SE skeletons
(humans, draugr, dragons, atronachs, animals, dwemer, daedra, etc.) —
the hash identifies the *class*, not the skeleton instance.

`hkaAnimationContainer` reuses the same hash whether the container holds
an animation or only a skeleton.

## Vanilla survey

A scan of all 50 vanilla SE `skeleton*.hkx` files turned up the
following patterns. These shaped the design of the writer.

### `lockTranslation` (per-bone bool)

When true, the animation runtime ignores the bone's translation track
and keeps it at its rest-pose position. Used pervasively:

| File | Bones | Locked |
|---|---|---|
| Human `skeleton.hkx` | 99 | 94 |
| Human `skeleton_female.hkx` | 99 | 94 |
| Bear | 76 | 74 |
| Dragon | 84 | 82 |
| Draugr | 84 | 82 |
| Wolf | 50 | 48 |
| Frost atronach | 20 | 10 |
| 1st-person `skeletonfirst.hkx` | 99 | **0** |

Bones that are typically **unlocked** (translation allowed) follow a
clear pattern across every vanilla skeleton:

- `NPC Root [Root]` — master root, must translate for root motion
- `NPC COM` / `Canine_COM` / `Horse_COM` — center of mass, translates
  for ragdoll/physics
- Human-only extras: `x_NPC LookNode [Look]`, `x_NPC Translate [Pos ]`,
  `x_NPC Rotate [Rot ]` — animation system scratch nodes for IK and
  procedural motion

The frost atronach is the outlier: it unlocks its entire arm and leg
chain (thigh / calf / upperarm / forearm on both sides) because those
segments are physically stretchy in its walk cycle. Note the typo in
Bethesda's data — `NPC R Thigh` is labeled `[LThg]` and `NPC R Calf` is
labeled `[LClf]` — preserved verbatim.

The 1st-person skeleton is the *only* vanilla file with zero locked
bones. May be an oversight; in-game it doesn't matter because the
1st-person camera doesn't run physics.

### `referenceFloats` and `floatSlots`

Parallel arrays of named float "channels" the skeleton carries. The
animation system can bind float tracks to these slots; game code reads
them to drive visibility flags, fade values, etc.

In vanilla, the slot names use two prefixes:

- `hkVis:` — visibility flag for a node (`hkVis:Weapon`,
  `hkVis:WeaponSword`, `hkVis:Shield`, `hkVis:NPC L MagicNode [LMag]`,
  …). The runtime hides/shows the corresponding node based on the slot
  value.
- `hkFade:` — opacity/fade value (`hkFade:AnimObjectA`,
  `hkFade:AnimObjectB`, `hkFade:AnimObjectL`, `hkFade:AnimObjectR`).
  Used for prop fade-in/out during animations.

Vanilla files that populate these:

| File | Slot count | Slot names |
|---|---|---|
| Human `skeleton.hkx` | 8 | `hkFade:AnimObjectA/B/L/R`, `hkVis:Shield`, `hkVis:NPC L MagicNode [LMag]`, `hkVis:NPC R MagicNode [RMag]`, `hkVis:Weapon` |
| Human `skeleton_female.hkx` | 8 | (same as above) |
| 1st-person `skeletonfirst.hkx` | 8 | (same as above) |
| Draugr `skeletons.hkx` (and `f.hkx`, plain `skeleton.hkx`) | 2 | `hkVis:Weapon` variants |
| Falmer | 1 | `hkVis:Weapon` |
| HMDaedra (DLC2) | 1 | `hkVis:Weapon` |

The remaining 44 of 50 vanilla skeletons have zero float slots.
`referenceFloats` parallels the slot list — vanilla always writes
zeroes, but it's a real `float[]`.

### `localFrames`

Array of `(hkLocalFrame*, boneIndex)` pairs that attach arbitrary
"local frame" objects to bones (camera attachments, IK target frames,
magic node anchors, etc.).

**Zero of 50 vanilla skeletons populate this field.** Bethesda doesn't
use it in Skyrim. The writer always emits an empty array.

### `hkaSkeleton.name` vs root bone name

The struct has its own name string distinct from any bone. Across all
50 vanilla skeletons, **zero** have a `name` that differs from
`bones[0].name`. The writer forces them equal on export and the
importer doesn't bother tracking them separately.

## hkxcmd quirks

`hkxcmd CONVERT` is 32-bit only and refuses to load `ptr_size=8` files,
so it can't read vanilla SE skeletons directly. It does load
`ptr_size=4` (LE) output from our writer.

Two padding gotchas were discovered while making hkxcmd accept our
output:

1. **Section header name field** must be NUL-padded with a single
   `0xFF` sentinel at byte `0x13`. Our writer originally filled the
   pad with all `0xFF`, which hkxcmd silently rejects (treating the
   first 0xFF as the end-of-string marker but then reading garbage
   from the offset table). Fix is in `_skyrim_section_header`.

2. **Bone name strings** must start at a 2-byte aligned offset. If a
   bone-name pointer lands on an odd offset, hkxcmd reads it as an
   empty string and produces `<hkparam name="name"></hkparam>` for
   that bone. Fix is `align_to(2)` before each bone-name string write.

Neither bug affects the in-game runtime — Skyrim loaded our broken
files just fine — but they make the output un-debuggable via hkxcmd.

## hkMemoryResourceContainer struct layout

Empty in skeleton-only files. Layout:

| Offset | Size | Field |
|---|---|---|
| `0x00` | base_sz | hkReferencedObject base |
| base_sz | P | `name` (string ptr, typically null) |
| base_sz + P | arr_sz | `resourceHandles` (empty) |
| base_sz + P + arr_sz | P | unknown ptr (null) |
| base_sz + 2*P + arr_sz | arr_sz | `externalLinks` (empty, flagged) |
| base_sz + 2*P + 2*arr_sz | arr_sz | `objectData` (empty, flagged) |

Total: `base_sz + 2*P + 3*arr_sz`. Empty arrays have
`capacityAndFlags = 0x80000000`.

## Round-trip preservation in PyNifly

Custom Blender properties are used to round-trip Havok-only fields
that have no native Blender representation:

| Field | Stored on | Property |
|---|---|---|
| `bones[].lockTranslation` | per-bone | `PYN_HKX_LOCK_TRANSLATION` (bool) |
| `floatSlots` | armature object | `PYN_HKX_FLOAT_SLOTS` (`;`-joined string) |
| `referenceFloats` | armature object | `PYN_HKX_REFERENCE_FLOATS` (float list) |

If `PYN_HKX_LOCK_TRANSLATION` is missing on a bone (for armatures
created from scratch in Blender), the export uses
`_default_lock_translation()` to apply the vanilla heuristic: unlock
Root / COM / `x_NPC *` bones, lock everything else.

`localFrames` is not preserved — no vanilla file uses it, and we'd
need to round-trip `hkLocalFrame` as an opaque blob if a non-vanilla
skeleton ever populates it. The importer warns instead if it finds a populated `localFrames`.

**Bone ordering** is critical — animations reference bones by index.
Blender does not preserve bone insertion order in `armature.data.bones`.
The importer stores the original HKX bone order in `PYN_HKX_BONES`
(`;`-joined string on the armature object), and
`extract_skeleton_from_armature` reorders by this property on export.
