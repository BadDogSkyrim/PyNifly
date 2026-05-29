# Plan: FO4 dismemberment cut offsets in PyNifly

Status: **Phases 0–4 done** (v1). Full pipeline: round-trip preservation plus
supply step that generates cut offsets from bone geometry (`step ≈ length/9.5`)
and writes an SSF file keyed by actual shape name. Verified end-to-end on
vanilla MaleBody — the generated SSF is byte-equivalent to vanilla `MaleBody.ssf`.

Format reference (not duplicated here): `Bethesda Library/docs/file-formats/dismemberment.md`.

## Problem

Custom FO4 humanoid bodies exported via PyNifly don't dismember in game at all.
Reported on `Meshes/FFO/Body/DogMaleBody.nif` (Furry Fallout). The body's segment
structure is byte-identical to vanilla `MaleBody.nif` (same 7 segments / 25 total,
same dismember material hashes, same `.ssf` path) **except every subsegment's
`Num Cut Offsets` is 0**. Cut offsets are the slice planes the engine uses to sever
a limb; with none, nothing can be cut → no dismemberment.

Not a round-trip regression: the cut offsets were most likely **never present** in
this body's authoring chain. So the fix is twofold — (a) carry cut offsets through
the pipeline so they're never dropped, and (b) be able to **supply** them for a
body that has none.

## Where the data lives (confirmed)

nifly already models cut offsets end to end — no nifly library change needed:

- `NifSubSegmentInfo.extraData` (`std::vector<float>`) — the wrapper-facing field,
  one list per subsegment (`Nifly/include/Geometry.hpp`).
- In file: `BSSITSSubSegmentDataRecord` (`numData` + `extraData`).
- `BSSubIndexTriShape::GetSegmentation` reads file → `subs[].extraData`
  (`Geometry.cpp:1401`); `SetSegmentation` writes `sub.extraData` → file
  (`Geometry.cpp:1498-1499`); `Sync` serializes the block automatically. nifly is a
  pure pass-through — it never computes or defaults cut offsets.

The gap is entirely in PyNifly's own layers:

| Layer | File | Gap |
|-------|------|-----|
| C++ wrapper | `NiflyDLL/NiflyWrapper.cpp` | `getSubsegments` (~L2055) returns only `[partID, userSlot, material]` — drops `extraData`. `setSegments` (~L2149) never sets `NifSubSegmentInfo.extraData`. |
| DLL sigs | `io_scene_nifly/pyn/niflydll.py` | No getter/setter for the per-subsegment float list. |
| pyn | `io_scene_nifly/pyn/pynifly.py` | `FO4Subsegment` has no cut-offset attr; `_read_segments` (~L4052) doesn't read it; `set_partitions` (~L4362) doesn't write it. |
| Blender | `nif/import_nif.py`, `nif/export_nif.py` | Cut offsets not stored on import / restored on export. Not recoverable from Blender geometry → must be a custom prop. |

### Examples

The vanilla male body ("C:\Modding\FalloutAssets\00 FO4 Assets\Meshes\Actors\Character\CharacterAssets\MaleBody.nif"): 
- PSDB 0, placeholder
- PSDB 1, placeholder
- PSDB 2, whole right arm segment, index 2
- PSDB 3, first upper right arm subsegment, index 3001185871, no cuts
- PSDB 4, second upper right arm subsegment, index 3001185871, all cuts
- PSDB 5, third upper right arm subsegment, index 3001185871, no cuts
- PSDB 6, only lower right arm subsegment, index 1875114930, all cuts
- etc


### Key invariant (must respect)

Cut offsets are a **per-subsegment** payload. There is one shared-data record per
segment AND per subsegment (record count == Total Segments), but the cut-offset
*floats* are sparse: plain segment records always carry 0, and among a body part's
subsegments typically only one carries a nonzero list (0–8 floats). The Blender
data model must therefore key cut offsets to the *individual subsegment*, never a
flat per-shape blob, or the floats land on the wrong record.

## Proposed wrapper API (additive, doesn't break existing calls)

**Read** — new Len+Data getter (matches `getClothExtraDataLen`/`Data` pattern):

```c
// Returns count of cut offsets for the subsegment with the given partID.
// Fills buf (floats) if non-null and buflen large enough.
int getSubsegmentCutOffsets(void* nif, void* shape, int subsegID,
                            float* buf, int buflen);
```

**Write** — extend `setSegments` with two parallel arrays, one entry of `cutCounts`
per subsegment (same order as `subsegData`), `cutData` the concatenated floats:

```c
void setSegments(..., uint16_t* tris, int triLen, const char* filename,
                 uint32_t* cutCounts, int cutCountsLen,
                 float* cutData, int cutDataLen);
```

`setSegments` distributes `cutData` into each `NifSubSegmentInfo.extraData` by
`cutCounts`, then hands the populated `NifSegmentationInfo` to nifly as today.

> C++ changes require a Debug DLL rebuild (I do this myself — see
> `feedback_dll_rebuilds`). Verify the Debug target is the one built before Blender
> testing.

## pyn layer

- `FO4Subsegment.__init__`: add `self.cut_offsets = []`.
- `_read_segments`: after creating each `FO4Subsegment`, call
  `getSubsegmentCutOffsets` and store into `cut_offsets`.
- `set_partitions` (FO4 branch): build `cutCounts` + `cutData` from each
  subsegment's `cut_offsets` in the same order the `sslist` is built; pass to the
  extended `setSegments`.

## Blender layer

- **Import** (`mesh_create_partition_groups`): store a mapping
  `{subsegment vertex-group name: [cut floats]}` as an object custom prop
  (`FO4_CUT_OFFSETS`, JSON-encoded). Only non-empty lists need storing.
- **Export** (`partitions_from_vert_groups` / shape export): when reconstructing
  each `FO4Subsegment`, look its name up in `FO4_CUT_OFFSETS` and set
  `cut_offsets`. Missing → empty (then the supply step below may fill it).

## The "supply" problem (the part that actually fixes the dog body)

Plumbing alone preserves cut offsets but won't help a body that never had them. We
need to **generate** cut offsets when a subsegment lacks them on export.

**v1 approach — generate from bone geometry** (chosen):

For each bearer subsegment, compute its bone's length from the armature
(`bone_length` = joint→child distance), set `step = bone_length / 9.5`, and emit
cut offsets at `k · step` for the integer run of `k` that covers the bearer's
stretch along the bone. This is the recipe verified against vanilla `skeleton.nif`
(length÷step landed 8.96–9.88 across all four human limb bones; cuts span up to
~0.7 of the bone). Works for any skeleton with available bone positions — human,
ghoul, dog, anything.

Alternatives considered and deferred:

- **Static table keyed by material hash.** Would hardcode vanilla MaleBody's cut
  lists per material. Cheaper but doesn't generalize beyond known human-skeleton
  materials; the formula handles those cases too.
- **Donor-NIF copy.** Point at a vanilla body, copy cut offsets by material. More
  UI, no clear advantage over the formula.

## Phased plan (TDD — failing test first at the lowest level)

- ✅ **Phase 0 — pyn read test.** `TEST_FO4_CUT_OFFSETS_READ` in `pynifly_tests.py`
  asserts vanilla bearer subsegments carry the expected cut-offset lists.
- ✅ **Phase 1 — read path.** `getSubsegmentCutOffsets` (Len+Data getter) in
  `NiflyWrapper.cpp`/`.hpp`; DLL sig in `niflydll.py`; `FO4Subsegment.cut_offsets`
  populated in `_read_segments`.
- ✅ **Phase 2 — write path.** `setSegments` extended with `cutCounts` + `cutData`
  parallel arrays; pyn `set_partitions` builds them from each subseg's
  `cut_offsets`. `TEST_FO4_CUT_OFFSETS_ROUNDTRIP` confirms all 37 vanilla cut
  floats survive a write→read round-trip on the right subsegments.
- ✅ **Phase 3 — Blender round-trip.** Import stashes a JSON `{vg_name: [cuts]}`
  dict as `FO4_CUT_OFFSETS` on the mesh object; export decodes it and attaches
  each list to its matching `FO4Subsegment`. `TEST_FO4_CUT_OFFSETS_ROUNDTRIP` in
  `blender_tests.py` confirms all 37 vanilla cut floats survive an
  import→export→re-read cycle in headless Blender.
- ✅ **Phase 4 — create on export.** `pyn/dismember.py` holds the pure helpers
  (`nearest_bone`, `along_bone`, `cut_offsets_for_span`, `encode_ssf_ref`,
  `build_ssf_shape_entry`, `supply_for_shape`, plus `FO4_HUMAN_DISMEMBER_CHILDREN`
  and `FO4_MATERIAL_TO_BONE` tables). The Blender exporter
  (`NifExporter._fo4_supply_and_ssf` / `_fo4_write_ssf`) extracts bone head_local
  positions and vert positions in armature-local space, calls `supply_for_shape`,
  accumulates per-shape SSF entries, and writes `<nifbase>.ssf` alongside the NIF
  after `self.nif.save()`. Unit tests: `TEST_FO4_DISMEMBER_HELPERS` and
  `TEST_FO4_DISMEMBER_SUPPLY` in `pynifly_tests.py`. End-to-end Blender test:
  `TEST_FO4_SSF_GENERATED` — clears `FO4_CUT_OFFSETS` on import so the supply
  step must regenerate, then asserts cuts present and SSF written with all 8
  human dismember bones. Generated SSF for vanilla MaleBody is byte-equivalent
  to vanilla `MaleBody.ssf`.

  **Not in v1 (deferred, still likely to ship):**
  - Export operator toggle to disable SSF generation (for users who hand-edit
    their own SSF and want PyNifly to leave it alone).
  - Attachment-slot subsegments carrying cuts (e.g. Pip-Boy slot 60 needs cut
    offsets so it detaches with the forearm).

## Future if it matters (probably never)

- **Per-garment k-subset matching.** v1 generates the consecutive run of `k`
  that covers the bearer's span (no gaps). Vanilla garments each pick their
  own subset of `k` on the same grid, sometimes with gaps (Fatigues Calf skips
  k=5; Pip-Boy skips k=3). The gaps look intentionally authored. Net effect
  of not matching them: cuts land at slightly different positions than vanilla
  would for the same garment. Functionally it still dismembers — the limb just
  separates a hair higher or lower than Bethesda chose. Skip unless someone
  flags weird cut placement in-game. We genuinely don't understand the
  runtime use of cut points yet, so no point polishing them.

### Phase 4 details

- Compare armature bones to our materials table, translating bone names back from Blender to nif names first, if necessary. (No new table.) Only bones in both lists matter.
- Subsegments are defined by vertex groups with the subsegment name pattern (e.g. "FO4 Seg 002 | 002 | Up Arm.R"). Determine which subsegment goes with which bone by proximity, treating the "bone" as the entire line segment from the bone position to its child bone position. Identify the subsegment closest to the middle of the bone for use later. 
- This is a good place for a unit test. Validate we can properly map a vertex group to such a line segment.
- Determine subsegment materials with this mapping.
- Per-segment data follows the vanilla pattern: 
  - each segment and each subsegment gets a per-segment data block (PSDB for short). 
  - If the PSDB corresponds to a segment, index is segment index, bone ID is 0xFFFFFFFF, no cut offsets. 
  - If PDSB corresponds to a subsegment:
    - index is 1-n within that segment
    - bone ID is the corresponding bone material
    - PSDBs corresponding to a bone id all occur sequetially and correspond to subsegments spaced along the bone in order. Find the subsegment closest to the middle of the bone and put all cuts on the corresponding PSDB. 
- **Write the SSF file** to the export directory. The SSF content is generated from
  the bone→bearer-subseg map built above.
  - **Filename:** use the `FO4_SEGMENT_FILE` custom prop value if present; otherwise
    default to `<nifname>.ssf` written next to the NIF.
  - **Export option to disable SSF generation:** when set, write nothing — trust
    whatever the `FO4_SEGMENT_FILE` prop points at. (Don't try to guess whether a
    referenced SSF is a vanilla file or whether it's valid for what the user did.)
  - **JSON structure — v1 conservative pattern** (the `MaleBody.ssf`-style layout):

    ```json
    {
      "<shape name>": {
        "BaseBoneName": "DISABLED",
        "DeltaBones": [
          { "BoneName": "<FO4 bone name>", "BoneDeltaList": [ <encoded ref> ] }
          // ...one entry per dismember bone present in this shape's bone→bearer map...
        ],
        "uiNumDeltas": <count of DeltaBones entries>
      }
      // ...one top-level entry per skinned dismember shape in the NIF...
    }
    ```

    Top-level key is the NIF shape name (e.g. `"BaseMaleBody:0"`). Multi-shape NIFs
    get one top-level entry per shape (matching `FatiguesM.ssf`'s multi-shape layout).
  - **`BoneDeltaList` encoding:** for each (bone, bearer subseg) pair, emit one int:

    ```
    value = (segment_index << 16) | (subseg_index_within_segment << 8)
    ```

    `subseg_index_within_segment` is 0-based (e.g. vanilla `RArm_UpperArm` =
    `0x020100` = seg 2, sub 1 — the second subseg of seg 2, which is the human upper
    arm's bearer).
  - **`BaseBoneName`:** v1 always writes `"DISABLED"` (matches `MaleBody.ssf` and the
    dog body's expected pattern). Real SSFs vary — `FatiguesM.ssf` uses `"DISABLED"`,
    `"Generic"`, *and* a real bone name across its four shape entries — but the
    semantics aren't confirmed and are part of the experts question.
  - **Variants we are NOT reproducing in v1** (call out so v2 has a list):
    minimal `BaseBoneName`-only entries with no `DeltaBones` (`FatiguesM.ssf`'s
    `pipboyArm:0`); `"DISABLED"` used as a *`BoneName`* inside `DeltaBones`;
    selective omission of bones from the `DeltaBones` list (vanilla `FatiguesM.ssf`
    omits `LArm_ForeArm1` from `Body:0` because the Pip-Boy shape handles that side
    separately). Users needing these patterns can disable SSF generation and supply
    their own SSF.

## Phase 5: Full handling of cutpoints on import

On looking at cutpoints for various models it's clear that 
- Cutpoints divide up long limb bones not joints
- They are usually equally spaced along the bone, but
- Some models deviate from that scheme because of peculiarities of the model itself.

Therefore, it's useful to give the modeler full control over cut points.

Our current scheme of visualizing cutpoints as disks slightly larger than the limb, parented to the associated bone and collected under one collection, is good.

The issue is correctly associating cutpoints with bones.

- Cutpoints are distances along a bone, stored in per-segment data blocks mapping 1:1 with segments and subsegments.
- A cutpoint block is associated with a dismember material ("Bone ID" slot in nifskope).
- Our table `fo4BoneIDs` translates material to human-readable name. BUT these names aren't bone names. They seem to be arbitrary. They don't appear in nifs or ssf files.
- Definition: "BLS" means the line segment from a bone to its child on the same limb, e.g. from RArm_UpperArm to RArm_ForeArm1.
- On import we need to associate a cutpoint block with a bone, to position the cutpoints correctly. But there's no obvious association. We know the vertex group that corresponds to the subsegment but that doesn't have a hard link to the bone. We know the material, but our material table doesn't identify bones.
- The ssf file associates bone name with subsegment. If we read this on import we know the bone a subsegment is associated with.
- We also need to identify the BLS or at least the direction of the cutpoint's bone (we don't care how far away the child bone is)
- Bone orientation usually (or always?) indicates the BLS direction. With the "pretty" bone orientation ON on import the +Y direction is the BLS; with it off, the +X direction is the BLS.

Proposed changes to our current implementation:
- Read the ssf file on import. Use the same rules as for materials files to resolve the relative path. Use this information to map subsegment (and thus cuts) to bone. If the ssf file can't be found, skip cutpoint representation entirely with a warning. We currently stash the cutpoint info, so it will be available on export.
- Rely on bone orientation as described above to determine the BLS and cutpoint direction. 
- Currently we name the cutpoints based on vertex group name. Instead, name them based on bone name: "Arm_UpperArm.R n", where n is the index of the cutpoint.
- Name the cutpoint collection with the name of the associated object + "_" + "Cutpoints"
- Add a custom property to each cutpoint disk to record the material (bone id) associated with the cutpoint.

Also, small tweaks:
- If the user is importing to a collection the cutpoint collection should be a child of the new collection we create for the import
- Cutpoint disks should not have the "in front" visual display

Stop for visual testing here before phase 6. In particular we will test that the bone orientation works for positioning cut point disks.


## Phase 6: Handling cutpoints on export

On export, we should use the cutpoint collection (if any) to create cutpoints. 
- The cutpoint parent bone identifies the bone. The cutpoint disk's distance from the bone is the cut value. Our existing PYN_ROTATE_BONES_PRETTY custom property tells us whether to use +X or +Y.
- The cutpoint custom property identifies the material. If missing we look it up in FO4_MATERIAL_TO_BONE. If not there, we generate our own hash with a warning

If there are no cutpoint disks in the export, use the stashed custom properties if any.

## Phase 7: Non-humans

Expand the FO4_MATERIAL_TO_BONE to cover everything in fo4BoneIDs and use it on import if there's no ssf file available. (It's already used on export to get the material ID from the bone name.) Some materials will map to multiple bone names, but only one of those should exist in the import. We have to check all uses of FO4_MATERIAL_TO_BONE to handle a list and do this disambiguation.

## Open questions

1. **Which subsegment must carry the cut list?** Vanilla puts it on one specific
   subsegment per part (e.g. the *middle* of three "Up Arm.R"). Does the engine
   require that exact position, or just that *some* subsegment of that material
   carries the floats? Determines how precisely the supply step must replicate
   vanilla. Resolve empirically (in-game test).
2. ~~**Does `numData` need to match across the duplicate subsegments**, or is a
   single bearer enough?~~ **Resolved by Phase 4 design:** single bearer (the subseg
   closest to the bone midpoint). Vanilla precedent supports it; ghoul calves split
   the list across two consecutive subsegs but a single bearer is expected to work.
   Validate in game; revisit if not.
3. **Female vs male tables** — confirm `FemaleBody.ssf`/cut offsets differ enough to
   warrant separate tables, or whether one human table suffices.
4. ~~Custom-prop format for `FO4_CUT_OFFSETS`~~ — **Resolved:** JSON dict keyed by
   vertex-group name, e.g. `{"FO4 Seg 002 | 001 | Up Arm.R": [7.6055, 9.5069,
   11.4083, 13.3096], ...}`. Only non-empty lists stored.

## Test files

- Vanilla: `tests/FO4/VanillaMaleBody.nif` (already in suite as `TEST_SEGMENTS`).
- Failing real-world: `DogMaleBody.nif` (Furry Fallout) — for in-game verification.
- Scratch scripts (in `c:\tmp`): `parse_segshared.py` (raw cut-offset dump),
  `inspect_segments.py`, `roundtrip_segments.py`.
