# Animation & HKX issues: triage (2026-11-02)

38 open GitHub issues touch animation, HKX or skeletons. This sorts them by root cause.
"Code" notes come from reading `hkx/` today, not from running anything.

## A. Additive and partial animations — DONE ✓

| Issue | What |
|---|---|
| #381 items 5, 6 | **FIXED 91d9bff.** FO4 blendHint read/write; partial export writes only driven bones; additive round-trips as deltas. |
| #381 item 7 | **FIXED 91d9bff.** FO4 1st-person "six block" format is hkaLosslessCompressedAnimation (not quantized). Full reader+writer implemented. |
| #434 | **FIXED 91d9bff.** Export resets undriven bones' leftover pose and writes only driven bones for KEYED actions. |
| #442 | **FIXED 91d9bff.** Interleaved-uncompressed reader+writer (Skyrim native; FO4 reader, writes lossless). |

Action settings in Dope Sheet sidebar "PyNifly" panel: blend hint (NORMAL/ADDITIVE), tracks (ALL/KEYED), compression (SPLINE/LOSSLESS/UNCOMPRESSED). In-game verified 11-03.

## B. Export writes files other tools reject — DONE ✓

| Issue | What |
|---|---|
| #440 | **FIXED c9412c7.** Two LE-only layout bugs: hkaSplineCompressedAnimation sized 0x80 not 0x84, and hkMemoryResourceContainer field order wrong. Annotations now survive; hkxcmd + HBPP accept our output. |

## C. Root motion, paired animations, compression options — DONE ✓

| Issue | What |
|---|---|
| #381 item 4 | **FIXED 2983a03.** Root motion (hkaDefaultAnimatedReferenceFrame) read/write for FO4 and Skyrim. Action setting: AUTO/EXTRACT/KEEP. |
| #381 item 3 | **FIXED 2983a03.** Paired sync offset (hkSimpleLocalFrame) round-tripped via SyncAnimOffset Empty. **Note:** game does NOT use the offset at runtime — actor positioning comes from behavior graph/AI packages. Data preserved for CK/authoring fidelity. |
| #381 items 1, 2 | **FIXED 91d9bff+2983a03.** Compression choice per action; rotation quantization bits recorded on import and used on export. |
| #442 | Moved to A (interleaved reader/writer). |
| #239 | Very likely fixed by root motion support — retest to confirm. |
| #287 | Predates native rewrite; retest. |

In-game verified 11-03: RunForward runs, turns turn, paired kill (GoodNeighbor) plays correctly on clean vanilla FO4.

## D. Skeletons: HKX vs NIF, custom skeletons

| Issue | What |
|---|---|
| #446 | **FIXED 088be10.** Import onto an existing armature matches bone names regardless of case. |
| #312 | Animations on a PyNifly-made custom HKX skeleton come out wonky (2025, pre-rewrite; retest). |
| #384, #361 | New creature skeleton → export errors / nothing happens (Need more info). |
| #354 | Skeleton nif export drops nodes; `bhkSimpleShapePhantom` collision breaks it. |
| #247 | SMP hair skeleton: duplicate names, AnimObjectA/B and CharacterBumper dropped (2024). |
| #76 | Bone scale: import fixed; default export writes scale 1.0 and displaces nodes (fine with Export Pose). |
| #112 | Bone roll differs from NifTools by 90° about the bone axis (FBX→HKX tool compatibility). |
| #395 | Enhancement: reference skeleton path in add-on preferences. |

## E. Animation inside NIFs (controllers)

| Issue | What |
|---|---|
| #352 | VltGearDoor01: `Paper:0` offset by its animated parent `VisibilityController` (10.28 units). |
| #244 | Several NiControllerSequences in one nif: only one exported (2024; probably fixed since the noble chest work; retest). |
| #385 | In-nif frequency etc.: fixed; what's left was Blender easing (user error). Close candidate. |
| #400 | `export_kf.py` bug, screenshot only. Look at the screenshot. |
| #422 | Enhancement: preview VFX UV-offset animation and billboards in the viewport. |
| #358, #350 | Need more info / question; probably close. |

Also from TODO/memory, no issue numbers:
- imported key times outside the animation's range
- ~~the scene frame range not set from imported nif animations~~ DONE (build 70)
- the FO4 bone-targeted multi-target controller dropped
- NiPathInterpolator → Bezier/Follow Path (marked next cycle)
- 572 "Target of controller not found" log lines in a full test run

## F. Workflow enhancements

| Issue | What |
|---|---|
| #443 | Bulk import of HKX files as separate Actions; the user has a working loop prototype. Cheap win. |

## G. Housekeeping: probably closeable

- **Obsolete since 30.0 (native SE/LE, no hkxcmd):** #171, #235, #236, #250, #256, #307
  (can't import / LE-only / conversion EXE). A comment ("native SE and LE import since 30.0")
  and close.
- **Answered, orientation:** #240, #255 ("Orient bones along limb" exists now).
- **Labelled Fixed, shipped:** #363, #372, #386, #399, #429, #439. Your rule is
  label + comment + leave open; these have shipped in 30.x, so they can close.

## Progress (2026-11-03)

**DONE:** B (#440), D (#446), A (additive/partial/lossless/interleaved: #381 items 1-7, #434, #442), C (root motion/paired/compression: #381 items 1-4). All in-game verified on clean vanilla FO4. Commits c9412c7, 088be10, 91d9bff, 2983a03 (not yet pushed).

**Next:**
1. Label/comment #434, #442, #381 on GitHub.
2. **E**: animations in NIFs (controllers).
3. **F #443**: bulk HKX import.
4. **G**: housekeeping closes.
5. Retest #239, #287 (may already be fixed by root motion / native rewrite).