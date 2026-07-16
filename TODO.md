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

## Euler rotation import: misaligned X/Y/Z keyframe times

**Status:** partially addressed 2026-07-15. **Export side is DONE** — see "2." below;
`_export_euler_curves` now resamples misaligned channels onto the union of their key
times (`_resample_euler_curves`), so export no longer raises and no longer depends on
the `rotate_bones_pretty` display option. Test: `TEST_FO4_EULER_CURVES_UNALIGNED`.
**Still open: the import-side warning (1.)** — the junk key times below.

Importing vanilla `Meshes/Furniture/Workstations/WorkbenchArmor/WorkstationArmorB01.nif`
warns twice:

```
WARNING: Keyframes do not align for 'pose.bones["WorkstationArmorSpindleBone"]. Animations may be incorrect.
WARNING: Keyframes do not align for 'pose.bones["WorkstationArmorGearBBone"]. Animations may be incorrect.
```

Source: `io_scene_nifly/nif/controller.py:1482`. An XYZ_ROTATION_KEY (`rotationType=4`)
`NiTransformData` needs all 3 Euler channels to share time signatures; the importer zips
them index-wise and warns when they don't line up. Two **separate** problems hide behind
that one warning:

**1. Garbage key times on single-key channels (the warning above).** Both bones have
`numKeys=1` on all 3 channels, all **values 0.0**, but some channel times come back as
**-447392.4375** (bits `0e74dac8`) — identical across both bones and channels, so it's
deterministic, not random uninit:

| bone | x (time, value) | y | z |
|---|---|---|---|
| GearBBone | (0.0, -0.0) | (**-447392.4375**, 0.0) | (**-447392.4375**, 0.0) |
| SpindleBone | (**-447392.4375**, -0.0) | (**-447392.4375**, -0.0) | (0.0, 0.0) |

Not cosmetic: each channel inserts its keyframe at *its own* time
(`controller.py:1496-1500`, `x.time * fps * ANIMATION_TIME_ADJUST + 1`), so we plant
keyframes at a wildly negative frame. Two hypotheses, undecided — needs a raw-bytes read
of the block to settle:
- **Vanilla junk:** a single key is a constant, so the engine likely never reads its time,
  and the exporter left garbage. Plausible and harmless in-game — but we should sanitize
  (a lone key belongs at the animation start, not frame -447392).
- **PyNifly misread:** wrong offset/stride for LINEAR (`interp=1`) keys in this block.
  Note the two clean bones nearby use `interp=2` (QUADRATIC) and read fine (times 0.0/38.8).

**2. Genuinely different key counts per channel (separate bug, same file).**
`SuperSpraySmoke003-Emitter` has `nkeys x=5 y=5 z=4`. Here the channels really do have
different time signatures, which the code's own comment admits is legal but hopes never
happens. `zip()` silently truncates to the shortest channel — so we drop a key and pair
mismatched times (`[1] x=0.5333 y=0.5333 z=1.4667`). Correct fix is to resample the three
channels onto a common timeline rather than zipping by index.

Dodged in `TEST_FO4_SKINNED_UNDER_NODE` with `import_animations=False`. See
[project_skinned_under_node](memory).

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
