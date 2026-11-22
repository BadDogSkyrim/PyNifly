# PyNifly TODO

## FO4 compound collision: regenerate the BVH tree (currently preserved)

*(The single-body compound **crash** is fixed and shipped in 28.0.0 — import groups the
polytopes under `bhkPhysicsSystem` → `bhkCompound`, export writes the original packfile
back verbatim and sets `body_id`. Covered by `TEST_FO4_COMPOUND_PHYSICS_ROUNDTRIP`.
Regenerating the tree, below, is what remains.)*

**Status:** open (2026-07-17). Compound export currently PRESERVES the original
packfile (byte-identical) rather than regenerating it — see below. This item is to
finish true regeneration so edited/new compound collisions can be exported.

**Context:** An FO4 `hknpDynamicCompoundShape` (armor/weapons/cooking workbenches,
BOSRadarDish, etc.) is one rigid body whose shape is a compound of N convex polytopes.
The compound object is **0xD0 bytes** (not 0x70) and carries, after the templated
header: an AABB min (+0x80 vec4) / max (+0x90 vec4), and at +0xC0 a global-fixup
pointer to a separate **`hknpDynamicCompoundShapeData`** object. That Data object holds
the **bounding-volume BVH tree** — for the armor bench, 73 nodes × 32 bytes over 36
leaves. Node layout: `min(vec3,12) + field(4) + max(vec3,12) + link(u16,u16 at +0x1C)`
where the link encodes child/leaf references (e.g. `02 00 23 00`, `03 00 14 00`). The
engine walks this tree in `hknpDynamicCompoundShape::updateAabb` at load; without it
(or with garbage where the +0xC0 pointer should be) it dereferences bad memory and
crashes. `pack_compound` (bhk_autopack.py) emits the header + instances + polytopes but
NOT the 0x80-0xD0 bounding region or the Data/tree — so a from-scratch pack crashes the
game. `_export_compound_body` warns and refuses in that case.

**Current preserve approach (shipped):** import stashes the raw packfile (base64) on the
`bhkCompound` empty as `pynPhysicsData` plus `pynCollisionBodyID`; export writes those
bytes back verbatim and sets body_id. Byte-identical to vanilla, loads in game. The
two-level `bhkPhysicsSystem -> bhkCompound -> polytopes` hierarchy is still built for
viewing, but editing collision **geometry** in Blender does not round-trip (the stashed
bytes win). Test `TEST_FO4_COMPOUND_PHYSICS_ROUNDTRIP` asserts byte-identical + tree
present. `pack_compound` and its round-trip test (`TEST_FO4_COMPOUND_ROUNDTRIP`) remain
as the geometry-packing half, ready for when the tree is added.

**To finish (regenerate):**
1. Decode the node link encoding (the `(u16,u16)` at node +0x1C) and the tree's
   traversal/escape-index scheme. Compare across the 3 vanilla benches (36/33/11 leaves).
2. Implement BVH construction over the N instance AABBs (median-split/SAH) emitting that
   node format + the `hknpDynamicCompoundShapeData` object + the compound's +0x80/+0x90
   AABB and +0xC0 pointer (global fixup). Add `hknpDynamicCompoundShapeData` to the
   compound classnames (hash `0xF33DC3CC`).
3. Also revisit `+0x10` (0x02060004 for the benches, 0x02040004 for the 11-leaf stove) —
   likely encodes tree depth/node count; derive it rather than templating.
4. Switch `_export_compound_body` to regenerate when geometry changed (keep preserve as
   the fast path for unmodified collision).

**START HERE — reuse the Skyrim MOPP tree code (Bad Dog's tip, 2026-07-17):** we already
BUILD BVH bytecode for Skyrim MOPP collisions (`bhkMoppBvTreeShape` — see the MOPP
compiler and `project_mopp_export`/`project_mopp_output_id_encoding` memories, and the
`TEST_MOPP_*` pyn tests). The FO4 hknp compound tree format is probably NOT identical but
very likely similar (both are AABB BVHs over collision shapes). Diff the two node formats
first; the MOPP builder's spatial-partition logic may port directly.

## Constrain imported key times to the animation's time frame

**Status:** open (idea from Bad Dog, 2026-07-16).

An animation/controller has a defined time range (start_time/stop_time on the
NiTransformController, and the importer already tracks `importer.start_time` /
`importer.end_time`). Some vanilla keys carry times far outside that range — most
visibly the `-447392.4375` junk times on the armor workbench's lone constant keys, which
land at blender frame ~-10.7M and pollute the timeline (see the item above).

**Idea:** clamp/constrain imported key times to the animation's own time frame. A key
whose time falls outside [start, stop] is either garbage (a lone constant key, where the
time is meaningless) or out-of-range noise; snapping it into range keeps the fcurve
timeline sane without changing the animation (a constant channel is unaffected, and
in-range keys are untouched).

**Where:** `_import_transform_data` in `io_scene_nifly/nif/controller.py` (and the sibling
key-import paths — translations, quaternion, float). The controller's start/stop times
are available at import; a lone key could simply be placed at the start.

**Care:** don't distort genuine multi-key animations — only clamp keys that are actually
out of the controller's declared range, and be sure a legitimately short animation isn't
mistaken for garbage. Add a test with the workbench asserting no imported key lands
before frame 0 (or the animation start).

## Scene frame range isn't set from imported animations

**Status:** DONE 2026-11-03 (build 69, uncommitted). Nif import sets the scene range from the
first action it records, then widens it for the rest; a controller manager then sets it to its
first sequence (`apply_action` sets the range exactly). HKX import sets it to the animation.
Tests: TEST_NIF_IMPORT_SETS_SCENE_RANGE, TEST_HKX_IMPORT_SETS_SCENE_RANGE.

Importing Skyrim `dungeons\imperial\jail\impjaildoor01.nif` leaves the scene at Blender's
default frames 1-250, although its Open/Close sequences run about 30 frames (stop times
1.0s and 0.967s). `_record_slot` in `io_scene_nifly/nif/controller.py` only ever widens the
scene range (`min`/`max` against the current start/end), so it can't shrink the default 250.
`apply_action` does the same. Fix: on import, set the scene range from the animation rather
than widening it -- probably to the first/active animation's range, since the sequences can
differ in length. Test with the jail door: scene end frame matches Open's last key.

## Warn when a Starfield morph is exported to a file not named `morph.dat`

**Status:** superseded 2026-10-21 (build 44, uncommitted): a path whose last part isn't a `.dat`
is taken as the folder and `morph.dat` is added (`sf_morph.with_morph_filename`;
TEST_SF_MORPH_FILENAME, TEST_SF_MORPH_DIR_PATH_EXPORT). A path naming some other `.dat` is still
written verbatim, unwarned.

The game reads a head part's morphs as `<MRPH TCMP or TMPP folder>\morph.dat`, so the file must be
named exactly `morph.dat`. Export takes the Starfield Morphs paths (`pyn_sf_morph.chargen_path` /
`performance_path`) as the file to write, verbatim, so a path that names a folder is written as a
file with that folder's name. Bad Dog's `FSFFox_Ruff01` (2026-10-03) had
`meshes/morphs/FSFFox/Male/Chargen/FSFFox_Ruff01` and got extension-less `FSFFox_Ruff01` files
with correct contents, which the game can't find, and which then block the folder of the same name.

**Do:** warn when the resolved chargen or performance output's filename isn't `morph.dat`
(case-insensitive), naming the shape and the path, and saying the field should end in
`\morph.dat` (or `\{shape}\morph.dat`). Warn, don't refuse: an explicit path is the author's call.

**Where:** `io_scene_nifly/sfmorph/export_sfmorph.py`, where the two outputs are resolved (after
`substitute_shape` / `resolve_morph_output`). Test: a shape whose `chargen_path` names a folder
exports with a warning that names it; a `.../morph.dat` path exports without one.

## Don't write a Starfield morph.dat with no morph data

**Status:** done 2026-10-23 (uncommitted): `write_sf_morphs` skips a group with zero records and
logs an ERROR naming the shape. **Changed 2026-11-18 (Bad Dog):** it now WRITES the file anyway
(the user asked for it; a missing morph.dat is harder to find than a bad one) and logs a WARNING
that it won't work in game and crashes the CK. `sf_racecheck` still FAILs such a file.
TEST_SF_MORPH_EMPTY_WRITTEN.

A `morph.dat` whose keys are all empty has a key list but **zero morph-data records**, and the
Creation Kit crashes on it: `CreationRendererPrivate::MorphRenderPass` logs "invalid buffers" and
reads through a null pointer (`CreationKit.exe+60D9403`, CKPE crash 2026-10-05). Bad Dog's
`FSFFox_Ruff01` had 123 shape keys, none of which moved a vertex (a hair-to-mesh conversion that
never filled them), and export wrote both morph files with 0 records. Vanilla Wildman's beard
morphs carry 289,386 / 340,921.

**Do:** in SF morph export, if a shape's keys produce no morph data at all, don't write that
morph.dat and warn loudly, naming the shape and saying the head part's MRPH would crash the CK.

**Don't** warn about individual empty keys. Partly-empty morphs are normal on non-face parts:
vanilla beards typically have 9+ empty keys, `afro_curls_m` chargen 65 of 84, human teeth
performance 10 of 29 (measured 2026-09-15). A key that moves nothing is just a name with no bits
set. The face is the one place a single empty key matters -- a key the race DECLARES (`MPGM`) must
have data -- and that's `sf_racecheck`'s job, since export doesn't know the race.

**Where:** `io_scene_nifly/sfmorph/export_sfmorph.py`. Test: a shape whose keys are all copies of
Basis exports no morph.dat and warns; one real key plus one empty key writes the file with no
warning.

## Starfield `.mat` writer must be diff-only (don't clobber inherited fields)

**Status:** back burner (Bad Dog 2026-10-23: doubts people use materials that way). Found
2026-07-13, latent — `write_sf_materials` defaults OFF.

`sf_materials.settings_components` (~line 392) writes the **whole** `_HAIR_FIELDS`
set (and the other settings components) unconditionally. Starfield `.mat` storage
is **diff-only against the parent chain** in `materialsbeta.cdb`: fields absent
from a loose `.mat` inherit from a parent template. Verified via the cdb reader on
Bob hair (`Medium_Hair_Shared`): the loose `.mat` omits `MaxDepthOffset` and
`DitherScale`, but the engine resolves them to **0.01** and **1.0** from a parent.
Our parser defaults those to `0.0`, so an opt-in export re-emits them as explicit
`0.0` — **silently clobbering the inherited values**. `BackscatterStrength` is a
pure C++ constructor default (not stored in the cdb at all; only the field *name*
is in the reflection schema) — writing an explicit `0.0` changes it too if the real
default is nonzero.

**Direction (Bad Dog, 2026-07-13):** NOT plain diff-only omission — that silently
turns "unset" into "absent" and is an opportunity for things to go wrong. Prefer an
**explicit "value not present" signal** per field (a real presence marker / sentinel
/ Optional wrapper) so the parser, the Blender representation, and the writer all
*definitively* know whether a field was authored, rather than inferring it from a
default-value comparison. The writer then emits a field iff it's explicitly present.
Applies to hair + all settings components. Add a Bob round-trip test asserting the
exported `.mat` introduces no `MaxDepthOffset`/`DitherScale`/`Backscatter*` keys that
vanilla didn't have. Not urgent (`write_sf_materials` defaults OFF).

## Logging: stop forcing the `pynifly` logger level from inside the library

**Status:** partially addressed 2026-06-09. Remaining: the dev/prod level toggle.

**Done:** removed the import-time `logging.basicConfig(encoding='utf-8',
level=logging.DEBUG)` calls in `io_scene_nifly/nif/connectpoint.py` and
`io_scene_nifly/pyn/niflytools.py`. A library must not call `basicConfig` — it
installs a root StreamHandler and forces DEBUG on the *whole* root logger,
which hijacks the host app's logging config (any later `basicConfig` is a no-op
unless `force=True`).

**Still to decide — `io_scene_nifly/pyn/niflydll.py` (~line 23):**

```python
if 'PYNIFLY_DEV_ROOT' in os.environ:
    ...
    logging.getLogger("pynifly").setLevel(logging.DEBUG)   # dev: chatty
else:
    ...
    logging.getLogger("pynifly").setLevel(logging.INFO)    # prod
```

This is intentional — when developing PyNifly we want `pynifly` at DEBUG by
default. But it's an **import-time** side effect on the `pynifly` logger, so it
**overrides whatever the host app already configured**. Concretely: a consumer
(the FO4 furrifier) sets `getLogger("pynifly").setLevel(WARNING)` at startup;
`niflydll` is imported later (lazily, on first nif/tri op) and clobbers that
back to DEBUG. The consumer then needs extra workarounds (floor the log
*handler*, not just the logger) to keep PyNifly's DEBUG chatter out of its UI.

Goal: keep "DEBUG by default when developing PyNifly" WITHOUT overriding a host
app that has deliberately set the `pynifly` level. Options to weigh:

- Set the level only if the host hasn't: `if getLogger("pynifly").level ==
  logging.NOTSET: setLevel(...)` — but import order still makes this fragile.
- Move it out of import side-effects into an explicit opt-in the dev harness
  calls, e.g. `pynifly.enable_dev_logging()` — libraries shouldn't touch levels
  at import at all; let the app (incl. the dev test runner) decide.
- Keep the env-var intent but apply it from a small `init()` the dev entry
  points call, not from module import.

Principle: a library configures *no* logging — no handlers, no levels, ideally
just `logging.getLogger("pynifly").addHandler(logging.NullHandler())`. The app
(or dev harness) owns levels and handlers.

## Skeleton import: take rest positions from the file, even with "Create bones" on

With "Create bones" on, the importer replaces the rest position of every bone the file
has with the reference skeleton's, and poses it from the file. Right for a mesh nif, whose
bone nodes can sit at bind offsets; wrong for a skeleton nif, whose nodes ARE the rest
pose. Importing SF Extended Skeleton's FEMALE skeleton against our MALE reference left 72
bones posed away from their rest, up to 2.2 units (`ArmMass`, `Biceps`, `Thigh_Twist`).

Fix: a nif with no shapes (a skeleton) always takes rest from its own nodes. "Create
bones" still adds reference bones the file lacks. Mesh imports unchanged. (Agreed with Bad
Dog 2026-10-11.)

## Skeleton import: size each bone to reach its child

Every imported bone is a fixed 5 units long (`BONE_LEN`, `FACEBONE_LEN` = 2 in
`blender_defs.py`), scaled with the import. On a whole skeleton the hands and face, with joints a
unit or two apart, become a blob of overlapping bones that hides the skeleton (Bad Dog, Starfield
crowd skeleton, 2026-11-11). Size a bone to the distance to its child instead, along the bone's
axis, falling back to the fixed length for a leaf or a child that sits sideways.

Bad Dog's worry: octahedral bones are drawn with a width proportional to length, so a long
bone (spine to neck, hips to a far child) becomes a huge octahedron. Options to weigh: cap the
length (e.g. at today's 5); use the nearest child, not the first; or set the armature to Stick
display on import. Length must stay display-only: check that export ignores it before changing.

## Facebones armature: an explicit flag instead of guessing from bone names

**Status:** done: `pyn_facebones` on the armature, with a panel toggle (`PYN_OT_set_facebones`);
import and export honour it.

`BD.is_facebones` (blender_defs.py) decides an armature is a facebones rig when it has
more than 5 bones prefixed `skin_bone_`/`faceBone_`. Starfield crowd heads break this: they
ship a `<name>_facebones.nif` companion, but it has no face bones at all — same 55 bones,
same shape name, same LOD0 `.mesh` as the plain nif, just without the extra LODs (the
crowd `skeleton_facebones.nif` likewise equals `skeleton.nif`). So a crowd rig never
qualifies and the companion is never written.

Fix: a PyNifly property on the armature marking it as the facebones armature. Set it on
import when the armature comes from a `_facebones` nif (or passes the name test); export
honours the flag and falls back to the name test when it's unset, so existing files keep
working. A flagged SF armature with no `faceBone_*` bones writes the companion the way
vanilla crowds do: LOD0 only, pointing at the same `.mesh` (no `_fb` mesh suffix).
Needs a panel toggle so it can be set by hand. (Bad Dog 2026-10-16.)

## Starfield eye bones: do non-human heads need their own eye positions?

**Status:** waiting on Bad Dog's in-game check (2026-10-16).

Vanilla Starfield eye nifs are skinned to `L_Eye`/`R_Eye` only, so the eyes go wherever the
actor's eye bones are, and (presumably) look around by rotating them. The skeleton's eye bones
sit where a human's eyes are (female L_Eye (0.0426, 0.0794, 0.0321) m from `C_Head`). Crowd heads
put their eyes elsewhere -- af_md1's are ~5 mm further out and wider -- and each carries a
`BoneTranslations` extra-data block `BoneTrn` giving its own L_Eye/R_Eye offsets from `C_Head`
(metres), equal to the eye positions its skin binds imply. That looks like the engine moving the
eye bones to fit the head, so the eyes turn about their own centres.

FSFFoxRace heads would have the same problem: fox eyes sit far from the human eye bones, so if
the eyes rotate about the bones, they'd swing about the wrong point and slide out of the sockets
when they look around. FO4 moved eyes by sliding the UVs, so this never came up there.

**Check first (in game):** do fox eyes appear to rotate incorrectly in the head?

If they do:
- Find out how a chargen head moves the eye bones (a crowd head uses `BoneTrn`; whether a
  player/NPC head can carry one, or chargen/facebones does it instead, is unknown).
- PyNifly drops `BoneTranslations` on import ("Unknown block type") and never writes it. Either
  round-trip it as extra data, or generate it on export from the eye bones' binds (it equals
  them on vanilla crowd heads), so a new head gets correct values with nothing typed in.

See memory `reference_sf_bonetranslations`.

## Export: what to do with hidden objects

**Status:** done 2026-10-19 (build 42): hidden objects aren't exported. A hidden child of an
exported object is skipped with a log line; a hidden `:LOD1`+ slot exports with its LOD0, which
collects its slots by name. Test: TEST_SF_HIDDEN_NOT_EXPORTED (the headless failure was the hidden
object exported as an extra shape). 2026-10-23 (uncommitted): every kind of hidden counts (`visible_get`: eye, viewport-disabled, hidden or excluded collection), and `ObjectSelect` warns naming any object it couldn't select and why. TEST_SF_HIDDEN_KINDS_NOT_EXPORTED, TEST_OBJECTSELECT_REPORTS_FAILURE.

Exporting a root exports every object under it, hidden or not, and a hidden mesh fails:
`extract_mesh_data` puts each shape in edit mode, Blender refuses for a hidden object, and
`ObjectSelect` swallows the failure, so the error reads "mode_set.poll() Context missing active
object". Hit exporting `CanineFemTailBrush.nif` with a hidden `CanineFemTailBodynTail` under the
root (he unparented it as the workaround).

Bad Dog's instinct: anything hidden should not be exported. The catch: Starfield LOD import hides
the `:LOD1`+ children on purpose, and they must export. The headless tests don't hit the poll
failure, so LOD export from the GUI probably fails today. Options:
- skip hidden objects (with a log line), but treat `:LOD` children of an exported LOD0 as part of it;
- or export hidden objects, unhiding them temporarily while reading the mesh.
Either way, test it in a way that reproduces the GUI failure, and make `ObjectSelect` failures
loud instead of silent.

## Export: which parents come along

**Status:** done 2026-10-23 (uncommitted). Any selected shape under a pynRoot, reached through Empties (or armatures) only, brings the root and everything visible under it (`nif_root_above`). A shape under a mesh exports without it, under the mesh's parent at the same world position, with a warning (`mesh_ancestor`); the settings anchor (`find_settings_root`) stops at a mesh too. Hide a sibling to leave it out. TEST_EXPORT_SELECTED_CHILD_BRINGS_ROOT, TEST_EXPORT_MESH_PARENT_FLATTENED; TEST_IMP_EXP_SKY and TEST_EXPORT_WEIGHTS updated to the new rule.

Rule so far: a node is exported only if it's selected, is under a selected node, or is referenced
by a selected object (armature, collision). Exporting a mesh parented to another mesh breaks that:
`FSFFox_Ruff04` (a converted hair mesh parented to `CanineMaleHead` in Blender) was written as
`Scene Root -> NiNode CanineMaleHead -> BSGeometry`, and `_faceBones` the same. The game didn't show
the head part until he cleared the parent; head-part nifs want the geometry right under the root.

Two directions, possibly both:
- An unselected parent isn't exported; the child goes under the root with its world transform
  (warn, at least for Starfield head parts).
- If the active object is a child of a root node, export that root and everything under it.

These pull against each other (the second would export `CanineMaleHead` itself here), so settle
which rule wins before building.

## Far future: animated tails in Starfield

Tails move only by cloth today. A Skyrim-style tail project (`meshes\auxbones\tail`: a behavior, a skeleton and about 320 clips that run alongside the body's) would allow wags and reactions. Starfield's graphs (`.agx`) are plain XML, but its clips (`.af`) are undocumented and PyNifly can't read them, and nobody knows yet if the game reads an edited loose `.agx`. First step if this ever comes up: change a value in a loose human `.agx`, and try to decode the small `tail_boneweights.af`. Notes in the furry-race project memory.
