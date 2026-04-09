# Plan: Native Skyrim skeleton.hkx export (LE + SE)

## Summary
Goal is to allow an HKX skeleton to be generated from a Blender armature, for Skyrim LE, SE, and FO4.

Add `write_skyrim_skeleton(filepath, skel, ptr_size)` to [io_scene_nifly/hkx/anim_skyrim.py](../io_scene_nifly/hkx/anim_skyrim.py), refactor [skeleton_hkx.py](../io_scene_nifly/hkx/skeleton_hkx.py) so bone extraction returns a shared `Skeleton` dataclass, and rewire `ExportSkelHKX` in [export_hkx.py](../io_scene_nifly/hkx/export_hkx.py) with a Game enum and the native code path. Drop the hkxcmd dependency for skeletons entirely.

## hkaSkeleton on-disk layout (from `_parse_skeleton_hkx`, anim_skyrim.py:430-487)

`P = ptr_size` (4 LE, 8 SE), `arr_sz = P + 8`, `base_sz = 2*P`.

| Offset | Size | Field |
|---|---|---|
| 0x00 | base_sz | hkReferencedObject (vtable + memSizeAndFlags, zeroed) |
| base_sz | P | `name` (ptr → string) |
| base_sz + P | arr_sz | `parentIndices` hkArray<int16> |
| base_sz + P + arr_sz | arr_sz | `bones` hkArray<hkaBone> |
| base_sz + P + 2*arr_sz | arr_sz | `referencePose` hkArray<hkQsTransform> |
| ... + arr_sz | arr_sz | `referenceFloats` hkArray<float> (empty) |
| ... + arr_sz | arr_sz | `floatSlots` hkArray<hkStringPtr> (empty) |
| ... + arr_sz | arr_sz | `localFrames` hkArray<hkLocalFrameOnBone> (empty) |

LE total: 8 + 4 + 5×12 = **72 bytes**. SE total: 16 + 8 + 5×16 = **104 bytes** (verify alignment — pad to 16 if needed).

- **hkaBone stride**: parser uses `P+4` for LE (8 bytes), `16` for SE. Layout: `name_ptr(P) + lockTranslation(4) + pad`.
- **hkQsTransform**: 0x30 bytes always. `translation(16) + rotation(16) + scale(16)` — first 12 bytes of each are xyz/xyzw, last 4 padding.
- **parentIndices element**: int16 (parser at line 455 uses `<h`).

## Data section object order (mirror `_build_anim_data_section`)

1. **hkRootLevelContainer** — virtual fixup → class. `hkArray(2)` namedVariants header at offset 0.
2. NamedVariant data (2 entries × 3*P pointers) + 4 strings ("Merged Animation Container", "hkaAnimationContainer", "Resource Data", "hkMemoryResourceContainer") with local fixups for name+class ptrs.
3. **hkaAnimationContainer** — virtual fixup; global fixup nv0_variant→ac. Body: `base + skeletons(arr,1) + animations(arr,0) + bindings(arr,0) + attachments(arr,0) + skins(arr,0)`. Then skeleton ptr-array (1 entry).
4. **hkaSkeleton** — virtual fixup; global fixup `skel_ptr_array[0]` → skel. Body per layout above. Then in order:
   - skeleton name string (local fixup from `skel_rel + base_sz`)
   - parentIndices data: `count × int16` (local fixup from parentIndices array ptr)
   - bones array: `count × bone_stride` zeroed; **each bone has a name ptr** that needs a local fixup
   - bone name strings, each with local fixup back to the corresponding bone struct
   - referencePose data: `count × 0x30` packed (T+pad, R+pad, S+pad), local fixup from pose array ptr
5. **hkMemoryResourceContainer** — virtual fixup; global fixup nv1_variant→mrc. Same body as animation writer (anim_skyrim.py:964-974).

Align each top-level object to 16 bytes. Empty hkArrays still need their capacity set with the `0x80000000` flag (use `pack_arr_at` / `_hkarray`).

## Fixup enumeration

**Local** (within data section):
- nv0/nv1 name+class ptrs → variant name strings (4 total)
- skeletons hkArray ptr → skeleton ptr-array
- skeleton `name` field → name string
- `parentIndices` array ptr → int16 data
- `bones` array ptr → bone struct array
- Each bone's `name_ptr` → its name string (1 per bone)
- `referencePose` array ptr → hkQsTransform data

**Global** (cross-object pointers in data section):
- nv0_variant → hkaAnimationContainer
- nv1_variant → hkMemoryResourceContainer
- skeleton_ptr_array[0] → hkaSkeleton

**Virtual** (data → classnames):
- hkRootLevelContainer, hkaAnimationContainer, hkaSkeleton, hkMemoryResourceContainer

## Classnames section

Build a skeleton-specific list — `_ANIM_CLASS_ENTRIES_V8` includes spline/binding which we don't want. Either:
- (A) Add `_SKEL_CLASS_ENTRIES_V8` containing only `hkClass`, `hkClassMember`, `hkClassEnum`, `hkClassEnumItem`, `hkRootLevelContainer`, `hkaAnimationContainer`, `hkaSkeleton`, `hkMemoryResourceContainer` (8 entries) — **recommended**, matches vanilla skeleton.hkx layout.
- (B) Reuse the animation list. Slightly larger file but works.

Need the `hkaSkeleton` hash. Vanilla skeleton.hkx in the SkyrimSEAssets folder has it — extract it via a one-shot script (or hardcode after dumping). **Open question to resolve before coding: the hkaSkeleton 32-bit hash value.**

## Types section
The animation writer's section is a stub (all 3 section headers in anim_skyrim.py:1032 point to `cn_end` with zero length). Reuse as-is.

## skeleton_hkx.py refactor
Extract `ExportSkel.write_skel`/`write_pose`/`write_bones`/`write_parentindices` logic (skeleton_hkx.py:267-344) into a free function `extract_skeleton_from_armature(arma, selected_bones) -> Skeleton` that returns the dataclass from anim_fo4.py. Both the XML writer and the new native writer call it. The XML writer keeps working unchanged.

## Operator wiring (export_hkx.py:299)

```python
class ExportSkelHKX(bpy.types.Operator, ExportHelper):
    filename_ext = ".hkx"
    game: EnumProperty(items=[('SKYRIM_LE',...), ('SKYRIM_SE',...)], default='SKYRIM_SE')

    def __init__(self, ...):
        # Default from PYN_HKX_GAME_PROP / PYN_HKX_PTR_SIZE_PROP, mirroring ExportHKX.__init__
```
- Drop the inheritance from `skeleton_hkx.ExportSkel`. Drop the hkxcmd dance in `execute`.
- `execute`: extract `Skeleton` from active armature → `anim_skyrim.write_skyrim_skeleton(filepath, skel, ptr_size=8 if SKYRIM_SE else 4)`.
- `poll`: drop the `hkxcmd_path` requirement.

## Tests

The skeleton round-trip test from commit `1cf0a04` lives in tests/blender_tests.py (search for `skeleton`). Extend it:
- Add an SE round-trip (default) and an LE round-trip with different `ptr_size`.
- Pure-Python round-trip in tests/pynifly_tests.py: `load_skyrim_skeleton(vanilla) → write_skyrim_skeleton(tmp) → load_skyrim_skeleton(tmp)` and assert bone names, parents, and pose match.
- Vanilla baselines: SE skeleton.hkx in `C:/Modding/SkyrimSEAssets/...`; LE — find one in `reference_game_paths.md` or use the SE one with `ptr_size=4` write to validate format (won't be byte-identical to vanilla LE but should round-trip).
- After exporting from Blender, run the file through hkxcmd `CONVERT -V:XML` as a smoke test that the format is valid.

## hkaSkeleton fields not represented in a Blender armature

The Havok `hkaSkeleton` struct carries several fields that the import path silently
discards (`SkeletonArmature.bones_from_xml` only consumes name + parentIndices +
bone names + referencePose). For round-trip fidelity these need a story.

A scan of all 50 vanilla SE skeleton.hkx files turned up some surprises — see the
counts at the end of this section.

### `bones[].lockTranslation` (per-bone bool)
Tells the animation runtime that a bone's translation track must be ignored — the
bone stays at its rest-pose translation regardless of what an animation says about
it. Used pervasively in vanilla: 49 of 50 vanilla skeletons have it set on most
bones (the human skeleton has it on **94 of 99** bones; bear has 74/76; dragon
82/84). The only outlier is the 1st-person skeleton which leaves it false everywhere.

Bones that are typically **unlocked** (translation allowed) follow a clear pattern:
- `NPC Root [Root]` — master root, needs translation for root motion
- `NPC COM` / `Canine_COM` / `Horse_COM` — center of mass, translates for ragdoll/physics
- Human-only extras: `x_NPC LookNode [Look]`, `x_NPC Translate [Pos ]`, `x_NPC Rotate [Rot ]`
- Frost atronach unlocks its entire arm/leg chain (thigh/calf/upperarm/forearm) because
  those segments are physically stretchy in its walk cycle. (Bethesda typo: `NPC R Thigh`
  is labeled `[LThg]` in the file — preserved as-is.)

**Storage in Blender**: per-bone custom property `PYN_HKX_LOCK_TRANSLATION` (bool).
- **On import**: set the property on every bone to whatever the file said.
- **On export**: read the property. If missing (e.g. armature was built from scratch
  in Blender), apply this heuristic default:

  ```python
  def default_lock_translation(bone_name: str) -> bool:
      n = bone_name.strip()
      # Unlock root motion bones, COM bones, and the human special nodes
      if n.lower().endswith('root') or 'root' in n.lower().split():
          return False
      if 'COM' in n.upper().split() or n.endswith('_COM') or '[COM' in n:
          return False
      if n.startswith('x_NPC '):  # LookNode, Translate, Rotate
          return False
      return True
  ```

  Refine the heuristic against the vanilla unlock list above as needed; the goal is
  that exporting a Blender-built human-style skeleton matches vanilla without the
  user having to set anything.

### `referenceFloats` (hkArray<float>) and `floatSlots` (hkArray<hkStringPtr>)
Parallel arrays defining named float "channels" carried by the skeleton. The
animation system can bind float tracks to these slots, and game code reads them
to drive visibility flags, IK weights, etc.

In vanilla they're used for **weapon visibility flags** — the slot names are
`hkVis:Weapon`, `hkVis:WeaponSword`, `hkVis:WeaponAxe`, `hkVis:WeaponBow`,
`hkVis:WeaponDagger`, `hkVis:WeaponMace`, `hkVis:WeaponStaff`, `hkVis:WeaponBack`.
The runtime checks these to decide which weapon node to show on the actor.

Vanilla examples:
- Human `skeleton.hkx`, `skeleton_female.hkx`, 1st-person `skeletonfirst.hkx` —
  8 slots (full weapon set)
- Draugr `skeletons.hkx` — 2 slots
- Falmer `skeleton.hkx`, hmdaedra `skeleton.hkx` — 1 slot each
- All other 44 vanilla creature skeletons — 0 slots

Storage in Blender: armature object custom property (`PYN_HKX_FLOAT_SLOTS` = JSON
list of `[name, value]` pairs). For new Blender armatures, default to empty.

### `localFrames` (hkArray<hkLocalFrameOnBone>)
Array of `(hkLocalFrame*, boneIndex)` pairs — attaches arbitrary "local frame"
objects to bones. Used in some Havok skeletons for camera attachments, IK target
frames, magic node anchors, etc.

**Vanilla scan: zero of 50 skeletons populate this field.** Bethesda doesn't use it
in Skyrim. We can safely write an empty array on export and warn (rather than
error) if a future imported skeleton has a non-empty one.

### `hkaSkeleton.name` vs root bone name
The skeleton struct has its own name string distinct from any bone, but a scan of
all 50 vanilla SE skeletons found **zero** where `hkaSkeleton.name` differs from
`bones[0].name`. Force it to the root bone name on export, no custom prop needed.

### Per-bone reference scale
`referencePose` is a full TRS, but Blender edit-bone rest poses don't carry a
non-uniform rest scale. Vanilla skeletons all use `(1,1,1)` so this is theoretical
and we can ignore it; warn on import if a non-1.0 scale is encountered.

### Vanilla scan summary
50 vanilla SE `skeleton*.hkx` files scanned:

| Field | Files using it | Notes |
|---|---|---|
| `lockTranslation == true` on ≥1 bone | **49 / 50** | Pervasive; norm not exception |
| `referenceFloats` / `floatSlots` non-empty | 7 / 50 | All weapon visibility flags |
| `localFrames` non-empty | **0 / 50** | Unused in Skyrim |

### Recommendation (revised)
- **Phase 1** (this work): export from a Blender-native armature writes
  `lockTranslation = true` for every bone (matches vanilla default), empty
  `referenceFloats`/`floatSlots`/`localFrames`, and `name` = root bone name. This
  produces a file indistinguishable from vanilla for the common case of a
  Blender-built skeleton.
- **Phase 2** (round-trip preservation): on import, stash `lockTranslation` per
  bone, `floatSlots`/`referenceFloats` on the armature object, and warn loudly if
  any `localFrames` is encountered (then store as opaque blob if we ever need it).
  Re-export reads these custom props back. Required if users want to round-trip
  vanilla `skeleton.hkx` (e.g. the human or draugr skeleton).

Both phases are small. Phase 2 is worth doing in the same PR since the human
skeleton is the obvious test target and would otherwise lose its weapon-visibility
slots silently.

## Open questions / risks

1. **hkaSkeleton class hash** — must extract from a vanilla skeleton.hkx classnames section before coding. Quick: read 4 bytes preceding `"hkaSkeleton\0"` in vanilla `skeleton.hkx`.
2. **SE 8-byte alignment in hkaSkeleton body** — verify whether the 6 hkArrays each need 8-byte alignment between them; parser assumes contiguous (no inter-field padding) and that should hold since `arr_sz=16` is already 8-aligned.
3. **Bone count == 0** edge case — operator should refuse rather than write a degenerate file.
4. **lockTranslation** — currently always written false. Confirm we never need true.
5. **Reference pose coordinate convention** — the existing XML writer in skeleton_hkx.py:293-321 writes parent-relative TRS with quaternion as xyzw. The native writer must match exactly. The parser stores `[x,y,z,w]` (line 484). Same convention — good.
6. **Should the XML-only `ExportSkel` operator stay?** Recommend keeping it for users who want the XML for inspection / hkxcmd workflows; rename its menu label to "Export skeleton (XML)" to disambiguate.
7. **hkRootLevelContainer base class** — animation writer comments "no serialized base class header — hkArray at offset 0" (anim_skyrim.py:744). Apply the same in the skeleton writer.

## Concrete order of work

1. Dump hkaSkeleton hash from vanilla SE skeleton.hkx (one-shot Python).
2. Refactor `skeleton_hkx.py`: add `extract_skeleton_from_armature`.
3. Add `_SKEL_CLASS_ENTRIES_V8`, `_build_skel_classnames_v8`, `_build_skel_data_section`, `write_skyrim_skeleton` to `anim_skyrim.py`.
4. Pure-Python round-trip test in `pynifly_tests.py` against vanilla SE skeleton.
5. Wire `ExportSkelHKX` to native path with Game enum.
6. Blender round-trip test for both LE and SE.
7. Smoke test through hkxcmd → XML to confirm validity.
8. Update `MEMORY.md` if any non-obvious gotchas surface.
