# PyNifly TODO

## FO4 single-body COMPOUND physics crashes the game on export

**Status:** open, characterized 2026-07-16 (not yet fixed). Pre-existing; unrelated to
the skinning/animation work of 2026-07-15/16. Was masked by the zero-bone-skin crash
(fixed) — the game now gets past `BSSkin::Instance::UpdateModelBound` and dies later.

**Symptom:** exporting the vanilla FO4 armor workbench
(`WorkstationArmorB01.nif`) and loading it in game crashes with
`EXCEPTION_ACCESS_VIOLATION` in `bhkNPCollisionObject::CreateInstance(bhkWorld&)`
(write to `[rax+0x88]`, rax from a bad body lookup). Crash log
`crash-2026-07-16-08-43-16.log`.

**Immediate cause:** the exported `bhkNPCollisionObject.body_id = 0xFFFFFFFF`
(4294967295). The engine uses body_id to index the physics system's body array;
0xFFFFFFFF is out of bounds → garbage pointer → fault. Export **never sets body_id**:
`collision.py::export_collisions` (~1345) calls `add_collision(None, ...,
bhkNPCollisionObjectBufType)` with no body_id, so it defaults to 0xFFFFFFFF. (Only the
*import* path reads body_id; grep `body_id` in collision.py = 3 hits, all import.)
NOTE: this means the legit N-body case — e.g. VltGearDoor01 24-body — likely also
exports body_id=0xFFFFFFFF; either its test doesn't verify in game, or something else
sets it. Check before fixing.

**Deeper structural cause — compound flattening:** vanilla is **1 rigid body whose
shape is a `compound`** (hknp compound / list) containing **36 convex polytope
children**, referenced by body_id=0. PyNifly collapses this into the same Blender
representation it uses for genuine *N-body* systems, and re-exports it as N bodies:
- **Import** (`import_bhkNPCollisionObject`, `_collect` ~587): recurses into the
  compound and flattens all 36 children into flat sibling meshes
  (`bhkPhysicsSystem_poly.000..035`) under one `bhkPhysicsSystem` empty. The fact that
  they were ONE body's compound is **recorded nowhere** — indistinguishable afterward
  from 36 separate bodies.
- **Export** (`pack_shapes` → `pack_multi_polytope`, bhk_autopack.py): 36 polytopes →
  **36 independent rigid bodies**. There is **no packer** that emits "1 body, 1
  compound/list shape, N polytope children" (packers are: compressed_mesh, mixed,
  multi_polytope=N-body, sphere, convex_polytope). So even the structure is wrong, not
  just body_id.

**What vanilla expects:** 1 `bhkNPCollisionObject` (body_id=0) → 1 rigid body → 1
compound shape → 36 convex polytope children.

**To fix (three pieces):**
1. Import must record body grouping — whether shapes belong to one compound body vs N
   separate bodies (e.g. a `pynCompound`/body-index marker per shape object).
2. A `pack_compound` packer: one body, a compound/list shape, N polytope children.
3. Export must set the collision object's body_id (0 for the single-compound case; the
   correct per-node index for multi-body — apparently unset there too).

**Repro (headless, no game needed):**
`scratchpad/repro_coll.py` — import vanilla `tests/FO4/WorkstationArmorB01.nif`,
export, read back: `co.body_id == 0xFFFFFFFF`, `physics_system.geometry` = 36 polytope
shapes instead of 1 compound. Vanilla via `NifFile`: body_id=0, geometry=1 compound
(36 children), packfile has `hknpConvexPolytopeShape`=1 + `hknpPhysicsSystemData`=1.

## Euler rotation import: misaligned X/Y/Z keyframe times — DONE

**Status:** RESOLVED 2026-07-16 (both export and import).

**Export** (`_export_euler_curves`): resamples misaligned channels onto the union of
their key times (`_resample_euler_curves`) before the quaternion conversion, so export
no longer raises "NYI: keyframes at different times" and no longer depends on the
`rotate_bones_pretty` display option. Test `TEST_FO4_EULER_CURVES_UNALIGNED`.

**Import** (`_import_transform_data`): restructured. The three Euler channels are
independent unless a base (parent) or pretty-bone rotation must be applied — that
combines them through a quaternion, which needs all three at the same instant.
- `not need_conversion`: import each channel on its own key times (with tangents).
  Correct for any per-channel count/alignment — Blender evaluates the fcurves
  independently. This replaced the old zip-by-index equal-count branch.
- `need_conversion`: resample all three onto the union of their key times, then combine
  and convert (mirrors export). Per-channel key type (BEZIER/LINEAR) preserved.
The old "Keyframes do not align" warning is **removed** — obsolete now that both paths
handle misalignment. Also fixes the pre-existing `zip()`-truncation bug on genuinely
different per-channel counts (e.g. SuperSpraySmoke 5/5/4) and the mis-combine of
misaligned channels under a parent/pretty rotation.

**Still latent (minor):** the `-447392.4375` junk key times (vanilla garbage on lone
constant keys, confirmed real not a misread) still produce keyframes at frame ~-10.7M
and now, post-resample, one such key per channel. Harmless (value 0, constant), but see
the next item for the planned cleanup.

## FO4 compound collision: regenerate the BVH tree (currently preserved)

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

## Export should surface (create) the PyNifly property panels — all games

**Status:** open (Bad Dog, 2026-07-17).

**Problem:** an author-created object never shows its PyNifly property panels, so the
only way a modder can see or set the values PyNifly writes (Starfield morph paths, and
the equivalent for every other typed group) is via the Python console
(`obj.pyn_sf_morph.chargen_path = ...` + setting the `pyn_sf_morph_migrated` custom
prop). That is not an acceptable UI. Concretely: Bad Dog exported a Lykaios head, the
chargen/performance `morph.dat` files were written (paths auto-derived from the nif
anchor), but **no PyNifly property panels appeared** on the object, so there was nothing
to inspect or edit. This is **not Starfield-specific** — we now have typed property
panels for the other games too and they have the same problem.

**Why they don't show:** the typed groups (block groups + hand-wired groups like
`pyn_sf_morph`) are registered type-wide on `bpy.types.Object`, so every object *has* the
group — but the `PYN_PT_block` panel `poll`/`draw` gate on a per-group `<attr>_migrated`
custom prop (`_migkey`), which is only set when the value came in through an *import*. An
author-created object never gets it, so the panel stays hidden even after export writes
real files/data for it.

**Idea:** on export (any game), **materialize the relevant property groups** for each
exported object — set the fields to the values the exporter actually resolved/derived
(e.g. the chargen/performance paths from `resolve_morph_paths`, and likewise for other
groups the export path fills in) and set the `_migrated` key so `PYN_PT_block` renders
them. After exporting, the modder should see panels showing what PyNifly wrote and be
able to change them and re-export. Use the existing helpers (`pyn_props.set_group` for
hand-wired groups — sets fields + the migrated flag; the block-group equivalent for
buffer-derived groups).

**Scope / care:**
- Cover the typed groups relevant to whatever was exported, across all games — not just
  `pyn_sf_morph`. An author-made shape should end up with the same editable panels an
  imported one has.
- Only surface a group when it's actually meaningful for that object/export (don't
  create empty/irrelevant panels on every object — e.g. don't add SF-morph fields to an
  object with no shape keys). Gate on relevance, not on game.
- Write back the **resolved** values in the same representation import uses (e.g. morph
  paths relative-to-`meshes`, so they stay re-homeable).
- Idempotent: re-export shouldn't stomp a value the user has since edited — only fill
  when empty, or reflect what was actually written without overwriting an explicit value.

## Starfield `.mat` writer must be diff-only (don't clobber inherited fields)

**Status:** open (found 2026-07-13, latent — `write_sf_materials` defaults OFF).

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
