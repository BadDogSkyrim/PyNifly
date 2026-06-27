# FO4 Cloth Packfile Format — BSClothExtraData (hk_2014.1.0)

Fallout 4 stores cloth physics for hair, dresses, dusters, coats, and robes in a
`BSClothExtraData` block on the NIF. Its payload (`BSClothExtraData.Binary Data`)
is a **Havok packfile** — the same container format as FO4 native collision
(`bhkPhysicsSystem`, see [fo4_havok_packfile_format.md](fo4_havok_packfile_format.md))
— but its objects are Havok **Cloth (HCL)** classes describing a "Character Bone
Deforming Clothing" simulation, plus an embedded `hkaSkeleton`.

PyNifly currently round-trips this blob **verbatim** (DLL
`getClothExtraData`/`setClothExtraData` → `NifFile.cloth_data` as `(name, bytes)` →
import stores base64 on a `BSClothExtraData` empty object → export writes it back).
This document is the Phase-0 result of unpacking it: what's inside, and the tooling
to inspect it. Semantic import/export (regenerating cloth for edited/new garments)
is future work and is **not** implemented.

## Inspecting a blob

```
cd io_scene_nifly
python pyn/cloth_autounpack.py <file.nif>          # readable dump
python pyn/cloth_autounpack.py <file.nif> --json   # machine-readable graph
python pyn/cloth_autounpack.py <raw_blob.bin>      # a pre-extracted blob
```

Parsing API (`pyn/cloth_autounpack.py`): `parse_cloth_packfile(bytes) ->
ClothPackfile` (object inventory + decoded `hkaSkeleton` + per-object hkArray/string
discovery). The container layer lives in `pyn/havok_packfile.py`
(`parse_packfile`, `HavokPackfile`).

## Container layout

Standard hk_2014.1.0 64-bit packfile (little-endian, 8-byte pointers): a header,
three sections (`__classnames__`, `__types__`, `__data__`), and per-section fixup
tables (local/global/virtual) that relocate pointers.

**Gotcha vs the collision packfiles:** the section-header run does **not** always
start at file offset `0x40`. Collision blobs put it there, but cloth blobs put it
at `0x50` — the offset depends on the variable-length contents-version string in
the header. `havok_packfile.parse_section_headers` locates the sections by scanning
for their tag strings (`__classnames__` etc.) instead of hardcoding `0x40`, so it
works for both. (`bhk_autounpack.parse_section_headers` hardcodes `0x40` and would
fail on cloth blobs.)

Object enumeration comes from the **virtual fixup table** — each entry gives an
object's offset within `__data__` and its class name (via `__classnames__`).
`hkArray<T>` fields are `{T* data; int32 size; int32 capacityAndFlags}` (16 bytes);
the data pointer is relocated by a **local fixup**, and `size`/`capacity` are read
inline. `havok_packfile.HavokPackfile.array()` / `.ptr()` resolve these.

## Object graph

```
hkRootLevelContainer                 ← named variants: the cloth(s) + the skeleton
  ├─ hclClothData "…Clothing"        ← ONE PER SIMULATED CLOTH PIECE
  │    ├─ hclSimClothData "…Cloth"   ← particles + per-particle data
  │    │    ├─ hclStandardLinkConstraintSet   "standardLinks"
  │    │    ├─ hclStretchLinkConstraintSet    "StretchLink Constraint"
  │    │    ├─ hclBendStiffnessConstraintSet  "BendStiffness Constraint"
  │    │    ├─ hclLocalRangeConstraintSet     "LocalRange Constraint"
  │    │    └─ hclVolumeConstraintMx          (some garments only)
  │    ├─ hclSimClothPose "DefaultClothPose"  ← per-particle rest positions
  │    ├─ hclCollidable + hclCapsuleShape / hclTaperedCapsuleShape  (body collision)
  │    ├─ buffer/transform defs (hclScratchBufferDefinition, hclBufferDefinition,
  │    │    hclTransformSetDefinition)
  │    ├─ operators: hclObjectSpaceSkinPNOperator "Skin Simulation",
  │    │    hclMoveParticlesOperator, hclSimulateOperator,
  │    │    hclSimpleMeshBoneDeformOperator, hclCopyVerticesOperator /
  │    │    hclGatherAllVerticesOperator
  │    └─ hclClothState "Simulate", "Animate"  (operator pipelines per state)
  └─ hkaSkeleton "Root"              ← ONE, SHARED across all cloth pieces
```

Key structural facts (confirmed across the samples below):

- **One `hkaSkeleton` and one `hkRootLevelContainer` per blob**, regardless of how
  many cloth pieces. The skeleton is the full FO4 body skeleton (Root → COM →
  Pelvis → …), 200+ bones. The cloth's bone-deform/skin operators reference these
  bones, and the `hclCollidable`s are capsules placed on body bones (named
  `Collidable_Head…`, `Collidable_Neck_Low_skin…`, etc.).
- **The whole cloth sub-graph repeats per simulated piece.** A duster has 4
  `hclClothData`/`hclSimClothData` sets (4 flaps); a bathrobe has 2; hair and the
  slinky dress have 1.
- Shape class varies by asset: hair uses `hclTaperedCapsuleShape`, garments use
  `hclCapsuleShape`. Vert-gather operator varies (`hclCopyVerticesOperator` vs
  `hclGatherAllVerticesOperator`, sometimes both).
- In `hclSimClothData`, the first big array (field `+0x38`) is the **particle list**
  and its count matches `hclSimClothPose`'s pose array and the skin operator's
  per-particle arrays (113 for HairLong01). This particle count — and how particles
  map to mesh vertices — is the crux of any future semantic round-trip.

### Cross-sample inventory

| Asset | blob bytes | objects | cloth pieces | shape class | skeleton bones |
|---|---|---|---|---|---|
| `HairLong01.nif` (hair) | 46257 | 25 | 1 | hclTaperedCapsuleShape | 201 |
| `SlinkyDress/DressF.nif` | 95681 | 25 | 1 | hclCapsuleShape | 216 |
| `Bathrobe/OutfitF.nif` | 100177 | 44 | 2 | hclCapsuleShape | 257 |
| `DLC04/.../WesternDuster_m.nif` | 89873 | 82 | 4 | hclCapsuleShape (+hclVolumeConstraintMx) | 232 |

## hkaSkeleton decode

Decoded explicitly because it's the human-meaningful anchor. Layout (hk_2014.1.0,
64-bit), identical to the FO4 skeleton HKX parsed by
`hkx/anim_fo4.py::_parse_skeleton_hkx`:

```
+0x10  name           hkStringPtr
+0x18  parentIndices  hkArray<int16>
+0x28  bones          hkArray<hkaBone>      stride 0x10: {strptr(8); lockTrans(1); pad}
+0x38  referencePose  hkArray<hkQsTransform> stride 0x30: pos vec4 / rot quat vec4 / scale vec4
```

`cloth_autounpack.decode_skeleton` returns bone names, parent indices, and the
reference pose. HairLong01 → `name='Root'`, 201 bones (`Root`, `AnimObjectA`, …,
`COM`, `Pelvis`, `LLeg_Thigh`, …).

## Generic structure discovery

We do **not** yet hand-decode every one of the ~20 HCL classes. Instead
`cloth_autounpack.discover_object` walks each object at 8-byte granularity and, via
the local fixup table, reports:
- **hkArray fields** — any field with a relocated pointer whose inline
  `size`/`capacity` are consistent (`0 < size <= capacity`); reported as
  `+offset array[count]`.
- **string fields** — a relocated pointer landing in a printable NUL-terminated
  region; reported as `+offset str '…'`.

This surfaces each object's layout (names, array sizes) without a per-class struct,
which is enough to read the graph and is the foundation for hand-decoding specific
classes later.

### Annotated HairLong01 dump (excerpt)

```
[ 0] hkRootLevelContainer   +0x18 str 'hclClothData'  +0x30 str 'hkaSkeleton'  +0x00 array[2]
[ 1] hclClothData           +0x10 str 'Character Bone Deforming Clothing'  (+5 arrays)
[ 2] hclSimClothData        +0x30 str 'Simulation Cloth'
       +0x38 array[113]  ← particles      +0x58 array[510]   +0x48/+0x68 array[22]
       +0xf8/+0x108 array[113]  (per-particle data)
[ 3] hclCollidable          +0x10 str 'Collidable_Neck_Low_skin001'
[ 9] hclStandardLinkConstraintSet   'standardLinks'   +0x20 array[231]
[10] hclLocalRangeConstraintSet     'LocalRange Constraint'   +0x20 array[91]
[11] hclStretchLinkConstraintSet    'StretchLink Constraint'  +0x20 array[91]
[12] hclBendStiffnessConstraintSet  'BendStiffness Constraint' +0x20 array[189]
[13] hclSimClothPose                'DefaultClothPose'        +0x18 array[113]  ← rest pose
[14] hclScratchBufferDefinition     'Hair_Sim_Mesh'
[17] hclObjectSpaceSkinPNOperator   'Skin Simulation'
[24] hkaSkeleton                    'Root'  (201 bones)
```

## Decoding array element contents — what we can't rely on

The inspector finds *where* arrays are and their counts, but an `hkArray` header
stores only `{pointer, size, capacity}` — **not the element size**, so element
strides/types aren't recoverable from the container alone. Two hoped-for shortcuts
are dead ends for FO4 cloth:

- **No embedded reflection.** The `__types__` section is **empty** (length 0) in
  these blobs — FO4 ships them stripped of type metadata. So the file is not
  self-describing; a reflection-driven decoder has nothing to read.
- **`hkxcmd` can't convert them.** Our bundled `hkxcmd` (1.4.0.0) is a Skyrim-era
  hk_2010 tool; `Convert` reports "File is not loadable" on hk_2014 cloth.

So decoding element layouts (particle structs, constraint elements, the bone-deform
map) requires **documented Havok 2014 `hcl*` class definitions** (SDK metadata /
community RE) — a real reverse-engineering task, deferred until needed.

## Finding: vanilla hair cloth is template reuse, not per-mesh authoring

Across all 364 vanilla hair nifs (`…/CharacterAssets/Hair/{Female,Male}`):

- Only **28 carry cloth data** (14 styles × base + `_faceBones`); 336 have none.
- Every blob is byte-*unique*, **but** they cluster into **3 templates by size**
  (46257 / 32193 / 30625 bytes). Within a size class the blobs differ by only
  **4–36 bytes** out of 30–46 KB. The particles, constraint sets, bone-deform map,
  and `hkaSkeleton` are **byte-identical** across all 22 of the 46257-size hairs.
- **All per-style differences are confined to the two `hclClothState` objects**
  ("Simulate" / "Animate"): ~5 small inline values per state, located inside the
  six `array[7]` buffer regions (object offsets ~+0x168..+0x208). They are **not
  pointers** (no fixups) and **do not decode as sane float32** (denormal garbage),
  so they aren't the tunable "stiffness/gravity" params first guessed. Interpreting
  them needs the Havok `hclClothState` class layout; given they sit in the
  per-operator dependency/buffer structures and read as near-garbage, a live
  hypothesis is they're **incidental Havok-cloth-compiler scheduling output**, not
  semantic parameters. Unconfirmed — needs the class def (Option A) to settle.

Implication for semantic import/export: Bethesda did **not** fit a particle lattice
per hairstyle — they reused ~3 authored sims and nudged a few floats; the hair mesh
just rides the 9 `Hair_*_Cloth*` bones via ordinary skin weights (which PyNifly
already handles). So hair cloth round-trip looks achievable **without** decoding or
regenerating the particle lattice: recognize/attach the matching template, surface
the few cloth-state floats as editable params, and rely on normal bone weighting.
Garments (e.g. the 4-piece duster) are not yet checked for the same reuse pattern.

## Open questions for semantic import/export (Phase 1+)

- **The cloth-state floats** — what the per-style parameters actually tune (next).
- **Particle ↔ mesh-vertex mapping.** Only relevant if we ever need to author a new
  lattice rather than reuse a template; for vanilla hair it appears unnecessary.
- **Constraint / particle element layouts.** Need Havok 2014 `hcl*` class defs (see
  above). Deferred.
- **Garment template reuse.** Do dresses/dusters reuse a small set of templates the
  way hair does, or are they more bespoke?

## Files

- `pyn/havok_packfile.py` — shared Havok packfile container parser (`parse_packfile`,
  `HavokPackfile`, robust `parse_section_headers`). Re-exports the proven fixup/array
  helpers from `bhk_autounpack.py`.
- `pyn/cloth_autounpack.py` — cloth-specific inspector (`parse_cloth_packfile`,
  `decode_skeleton`, `discover_object`, standalone CLI).
- Test: `TEST_FO4_CLOTH_UNPACK` in `tests/pynifly_tests.py` (parses HairLong01's
  blob and pins the object inventory + skeleton). `TEST_CLOTH_DATA` continues to
  cover the verbatim round-trip.
