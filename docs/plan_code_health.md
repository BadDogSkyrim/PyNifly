# Plan: code health burn-down

Status: **Phases 1-5 complete** (2026-08-21), except the CI action (CH-5.2), which is deliberately deferred. Phase 6 not started. Audit run against `main` @ `2064a5c`.

Actions are coded `CH-<phase>.<n>` and referred to by code. `CH-S*` are standing habits (never
ticked off); `CH-X*` are things deliberately excluded, listed so they don't get re-litigated.

## Problem

Five months of heavy feature work (V25.13 → 28.1.0) added 30% to the addon. The question was
whether the codebase is spiralling. It isn't — the structural indicators that predict
unmaintainability are all healthy:

| indicator | measure |
|---|---|
| import cycles across 66 modules | **0** |
| `bpy` imports inside `pyn/` | **0** — the format layer stays Blender-free |
| source growth V25.13 → HEAD | 36,252 → 47,188 lines (+30%) |
| test growth over the same span | 16,520 → 23,340 lines (**+41%**) |
| `NifExporter` attributes declared in `__init__` | 45 of 50 |
| `NifImporter` attributes declared in `__init__` | 34 of 35 |
| tracked build artifacts | none |

What did change is pace and concentration. The last two releases added **8,596 lines against
3,523 in the six before them** — a 2.4× acceleration, almost entirely in Starfield materials
(`sf_materials` 1,216, `sf_cdb` 727, `sf_morph` 373, `shader_io` +1,355) and FO4 collision
(`bhk_autopack` +1,369, `collision` +461).

So this is a burn-down list, not a refactor project. Nothing here is architectural. The items
are ordered by payoff-per-hour, and each one is independently shippable.

## The failure mode to actually worry about

**Duplication that diverges quietly.** `tri/export_tri.py` is the proof case: a complete,
unreferenced copy of `trifile.py` + `tripfile.py` that has already fallen one bugfix behind the
original and ships in every release zip. If a fix ever lands in the fork instead of the real
file, that's an afternoon gone.

The same shape is starting in `hkx/`, where `anim_fo4.py` and `anim_skyrim.py` share 61
duplicated 12-line blocks and 18 identically-named helpers. That one is defensible — the two
Havok packfile versions genuinely differ — but the shared byte-level primitives (`align`,
`_hkarray`, `write_string`, the `_u`/`_f` readers) are the part that shouldn't drift, because a
fix to one will not reach the other.

---

## Phase 1 — dead code and one-liners

Under two hours total. No design decisions in any of it.

- [x] **CH-1.1** — **Delete `io_scene_nifly/tri/export_tri.py`** (780 lines). Unreferenced — the only grep
      hit is `NifExporter.export_tris`, an unrelated method name. Redefines `TRIHeader`,
      `TriFile` and `TripFile` in full; 307 duplicated 12-line windows against `trifile.py`, 76
      against `tripfile.py`. Already behind: `trifile.py` took the logging fix in `2513435`, the
      fork didn't.
- [x] **CH-1.2** — **`tests/blender_tests.py:13696`** — rename the local `test_categories` to
      `seen_categories`. It currently rebinds the module-level dict to a `set` before calling
      `do_tests`, and `execute_test:11886` calls `.get()` on that global. All 282 tests carry a
      category, so running the file as `__main__` (i.e. from Blender's text editor) raises
      `AttributeError` on the first test. Invisible via `test_runner.py`, which imports rather
      than executes.
- [x] **CH-1.3** — **`anim_test_runner.py`** — `testlist=[TEST_FO4_ANIM_ROUNDTRIP]` runs 1 of 18 anim tests.
      Point it at the full list, then fix whatever rotted; `anim_tests.py` hasn't been touched
      since 2026-04-06.
- [x] **CH-1.4** — **13 invalid escape sequences** (`SyntaxWarning` today, `SyntaxError` in a future Python).
      Shipping: `blender_defs.py:43`, `skeleton_hkx.py:26`, `skeleton_hkx.py:27`. Tests:
      `blender_tests.py` lines 144, 174, 2402, 2421, 4748, 4749, 4750, 5498, 5785, 7394.
- [x] **CH-1.5** — **Prune `TODO.md`.** Two of seven items are marked RESOLVED and were never removed. The
      headline item is worse than stale — it asserts export "never sets `body_id`" and that all
      three `body_id` hits in `collision.py` are import-side. Both are false: export sets it at
      `collision.py:1431`, `:1488` and `:1567`, and RELEASE_NOTES 28.1.0 announces the fix as a
      headline feature. The compound-physics crash may still be open, but it needs re-diagnosing
      against current code.

### Phase 1 results (2026-08-20)

Six items done (CH-1.6 was added mid-phase, below). **All 446 tests pass**: 282 Blender,
146 pyn, 18 anim.

- **CH-1.3 found the actual rot, and it wasn't the tests.** `anim_test_runner.py` set
  `PYNIFLY_DEV_ROOT` to the repo root, but `niflydll.py:22` and `test_runner.py:8` both treat it
  as the **parent** of the checkout (they append `PyNifly\...`). The DLL path resolved to
  `...\PyNifly\PyNifly\NiflyDLL.dll`, so the runner died at import — it has been unable to run
  *anything*, including the one test it was pointed at. With the root fixed, **all 18 pass**;
  nothing had rotted.
- **CH-1.5 went further than planned.** The headline TODO item wasn't merely stale — it is fully
  resolved. All three of its "to fix" pieces are in the code (`pynCollisionCompound` +
  `pynCollisionBodyID` at `collision.py:678`, `pack_compound` at `bhk_autopack.py:2172`, `body_id`
  set at `collision.py:1431/1488/1567`), it is covered by `TEST_FO4_COMPOUND_PHYSICS_ROUNDTRIP`,
  and it is announced in RELEASE_NOTES 28.0.0. Removed; the residual BVH-regeneration work is
  noted on the item that owns it. TODO.md went 276 → 150 lines, 7 items → 4, all genuinely open.
- **CH-1.4** removed all 13 invalid escapes; a full-repo rescan reports **0** warnings and 0
  compile failures. Every edited literal keeps its exact value (raw-string conversion only).

### Two pre-existing failures found and fixed (CH-1.6)

`TEST_BODYPART_SKY` and `TEST_COLLISION_BOW` were failing on unmodified `HEAD` before Phase 1
started (confirmed by re-running both against a clean checkout). Neither was an assertion in the
test body — both died in `test_loghandler.finish()` on un-whitelisted `WARNING`s:

```
Could not find texture Diffuse: 'textures\actors\character\male\MaleHead.dds'
Could not find texture EnvMap:  'textures\cubemaps\Ore_Gold_e.dds'
```

The cause was environmental, not code: `PYNIFLY_TEXTURES_SKYRIM` in `tests/test_tools_bpy.py:24`
pointed at `C:\Modding\SkyrimSEAssets\00 Vanilla Assets`, which does not exist. The FO4
equivalent, `C:\Modding\FalloutAssets\00 FO4 Assets`, *was* correct — which is why FO4 tests in
the same run passed while Skyrim ones failed.

- [x] **CH-1.6** — Repoint `PYNIFLY_TEXTURES_SKYRIM` to `C:\Modding\SkyrimSE\00 Vanilla Assets`
      (Bad Dog, 2026-08-20). Verified the directory and all three missing textures exist there
      before changing it.

**Full Blender suite after the fix: 282 / 282 pass, 0 failed, 0 skipped** (147s, Blender 5.1).
So the stale constant was the only thing broken — nothing else was hiding behind it.

Combined with the pyn (146) and anim (18) suites, **all 446 tests now pass.**

---

## Phase 2 — exception hygiene in `shader_io.py`

108 bare `except:` clauses across the addon; 32 are in `shader_io.py`, 39 addon-wide swallow
silently (`except: pass`). `shader_io.py` is the pilot — fix the pattern here, then apply it to
`import_nif.py` (16), `controller.py` (13) and `blender_defs.py` (9).

### The principle

**Feature detection, not version detection.** `bpy.app.version` encodes outside knowledge that
goes stale and that Blender can invalidate by backporting. The addon has only two such checks
today and shouldn't gain more.

But probing *by failing* is not the only form of feature detection, and it's the form that
can't tell "this Blender lacks the API" apart from "my code has a bug". Where the capability can
be asked about directly, ask:

```python
# probe by failing — a bug in any of the 16 statements runs the 4.0 fallback on a false premise
try:
    grp.inputs.new('NodeSocketColor', 'Diffuse')
    ...15 more...
except:
    grp.interface.new_socket('Diffuse', in_out='INPUT', socket_type='NodeSocketColor')

# probe by asking — same feature detection, no version knowledge, nothing swallowed
if hasattr(grp, 'inputs'):
    ...
else:
    ...
```

Three rules, in priority order:

1. **`hasattr` where the capability is nameable** — `hasattr(grp, 'inputs')`,
   `hasattr(bpy.types, 'ShaderNodeSeparateColor')`. Exact, version-agnostic, cannot hide a bug.
2. **Where a probe genuinely must run the call, name the exception** — `except RuntimeError` for
   an unknown node idname, `except AttributeError` for a missing API.
3. **The try block wraps only the statement that can raise.** This matters more than the except
   clause. Current worst offenders: `shader_io.py:2013` (**37 statements**), `:1317` (**23**),
   `:1066` (**16**), `:3155` (**9**).

### What the 32 sites actually are

Only 15 are Blender compat. The rest are unrelated things written as exception control flow, and
they carry no compat argument at all.

| category | n | lines | fix |
|---|---|---|---|
| Blender version compat | 15 | 940, 950, 986, 994, 1083, 1203, 1277, 1340, 1426, 1461, 1542, 1569, 1575, 1615, 1626 | `hasattr` probe, resolved once |
| "is this arg a socket or a raw value?" | 7 | 1001, 1634, 1643, 1671, 1677, 1683, 1689 | `isinstance(x, bpy.types.NodeSocket)` |
| dict lookup with a default | 2 | 1838, 3003 | `.get(key, default)` |
| our *own* old node-group socket names | 1 | 2965 | `Wrap U` vs legacy `Clamp S` — see note below |
| oversized block swallowing real failures | 3 | 1447, 2050, 3164 | shrink the try; keep the log at 2050 |
| misc `except: pass` | 4 | 1918, 2169, 2861, 3104 | narrow or delete |

- [x] **CH-2.1** — **The 9 non-compat sites** (socket-vs-value ×7, dict lookup ×2). Mechanical, covered by the
      existing shader tests, and settle nothing about the compat question — do these first
      regardless of where the rest lands.
- [x] **CH-2.2** — **The 3 latched globals.** `shader_io.py:940` (`SEPARATOR_*`), `:986` (`COMBINER_*`),
      `:1615` (`MIXNODE_*`) each mutate a module-level global inside a bare handler, so the first
      failure of any kind latches the whole session onto the Blender 3.x node names. Replace with
      a `hasattr(bpy.types, ...)` probe resolved once at import.
- [x] **CH-2.3** — **The node-group interface sites** (1083, 1277, 1340, 1426, 1461, 1542) — `grp.inputs` /
      `grp.outputs` (3.x) vs `grp.interface.new_socket` (4.0+). One `hasattr(grp, 'inputs')`
      branch. This also fixes the 16- and 23-statement try blocks.
- [x] **CH-2.4** — **Shrink `:2013`** (FO4 greyscale-to-palette, 37 statements) and **`:3164`** (alpha
      property, 9 statements) to wrap only what can raise. `:2013` at least logs a traceback
      today; keep that.
- [x] **CH-2.5** — **Check whether `:1569`/`:1575` are dead.** They fall back from `mesh.color_attributes` to
      `mesh.vertex_colors`, which mattered before Blender 3.2. `bl_info` declares 4.0 minimum.
- [x] **CH-2.6** — **Decide the real minimum Blender version and make the docstrings agree.** `bl_info` says
      `(4, 0, 0)`; `make_separator` and `make_combiner` claim "Safe for all Blender 3.x and 4.0";
      `test_categories` lists minimums of `(3,0)`. Three sources, three answers.
- [x] **CH-2.7** — **Then apply the same pass** to `import_nif.py` (16), `controller.py` (13),
      `blender_defs.py` (9).

**Note on `:2965`.** `Wrap U` vs legacy `Clamp S` is compat with *our own* previously-shipped
`UV_Converter` node group, not with Blender. That's the same class of problem the SF layer groups
solved by putting the version in the group name (`SF Layer v5`) so old and new coexist at no cost.
Worth considering the same treatment rather than a fallback branch — but it's a separate decision,
not part of this phase.

### Phase 2 results (2026-08-20)

**Bare `except:` addon-wide: 108 -> 36. Zero remain in `shader_io.py` (was 32), `import_nif.py`
(16), `controller.py` (13) or `blender_defs.py` (9).** The 36 left are in files outside this
phase's scope: `pyn/` (14), `hkx/` (7), `export_nif.py` (4), `collision.py` (3), `tri/` (3).

Verified on **three Blender versions**: 5.1 **282/282**, 5.2 **282/282**, 4.2 **278/282** (the 4
are pre-existing, see below). Plus 146 pyn and 18 anim tests.

#### The version question, settled with measurement

Probing bpy directly on 4.2 / 4.5 / 5.1 / 5.2 showed every "Blender 3.x" branch in `shader_io.py`
is unreachable on any version the addon can load on:

| capability | 4.2 | 4.5 | 5.1 | 5.2 |
|---|---|---|---|---|
| `NodeTree.inputs` / `.outputs` | no | no | no | no |
| `NodeTree.interface` | yes | yes | yes | yes |
| `ShaderNodeSeparateColor` / `CombineColor` | yes | yes | yes | yes |
| `ShaderNodeSeparateRGB` / `CombineRGB` (the *fallback*) | yes | yes | **no** | **no** |
| Principled BSDF `Specular` / `Subsurface` | no | no | no | no |
| `mesh.color_attributes` | yes | yes | yes | yes |

`bl_info["blender"]` is `(4, 0, 0)` and Blender refuses to enable an addon below its declared
minimum, so those branches cannot execute. The fallback node names were themselves removed in
Blender 5.0, so the fallback would have been broken even if it did fire. **Bad Dog's call: delete
them** rather than convert to `hasattr`. `shader_io.py` lost 112 lines.

#### Two real bugs the bare handlers were hiding

- **`export_nif.py:2838` called `ObjectSelect([selected_objs])`** with stray brackets --
  `selected_objs` is already `context.selected_objects`. `ObjectSelect` then called
  `select_set()` on the inner *list*, raising `AttributeError`, which the bare handler swallowed.
  **Restoring the user's selection after an export has never worked.** Surfaced the moment the
  handler was narrowed. Fixed the caller rather than re-hiding it; the other 15
  `ObjectSelect([obj])` call sites are correct (single object into a list).
- **`import_grayscale`'s "no greyscale texture" path was itself broken.** The `else` branch
  formatted `self.shape.textures['Greyscale']` -- the very key it had just established was
  missing -- so it raised `KeyError` inside the handler, and the outer bare `except:` turned it
  into a misleading "Could not load shader nodes from assets file" while skipping the rest of the
  node setup. Now uses `.get()`.

#### CH-2.8 (added mid-phase): Blender 4.2 was 156/282 failing on main

Not caused by Phase 2 -- confirmed by running the pre-Phase-2 tree on 4.2 and diffing the failure
sets (identical, 156 each). One systemic cause: animation export is gated on
`hasattr(bpy.types, 'ActionSlot')` (Blender 4.4+), so on 4.0-4.3 the exporter warns on **every**
export, and `test_loghandler.finish()` fails every test that exports.

- [x] **CH-2.8** -- `ALWAYS_EXPECTED` in `blender_tests.py` now adds that message when
      `ActionSlot` is absent, detected by capability rather than version to match how the
      exporter gates it. **Blender 4.2: 156 failures -> 4.**

#### CH-2.9: the last 4 Blender 4.2 failures, diagnosed and cleared

All four were in the pre-Phase-2 baseline. Three distinct causes:

- **`TEST_BRIARHEART_ROOT_EXPORT` + `TEST_EXPORT_BONE_ROTATION_RESPECTS_SETTING`** (spotted by
  Bad Dog): `Briarheart.blend` was saved by **Blender 5.1** (`bpy.data.version` = 5.1.29) and
  .blend files are not forward-compatible -- 4.2 answers *"not a blend file"*. It is also the only
  **zstd**-compressed fixture of the 43, which is the tell: 5.x defaults to zstd on save while the
  rest were written by 2.9x-4.x. Gated both tests with `@TT.min_version(5, 1, 0)` rather than lose
  fixture content by re-saving from an older Blender.
- **`TEST_WORKSHOP_DOOR_CONNECT_POINTS`**: asserts `len(bpy.data.actions) > 0`, but animation
  import is gated on `ActionSlot` (4.4+), so 4.2 imports none. Tagged `('FO4','CONNECTPOINT')`
  but genuinely depends on animation; added `'ANIMATION'`, which already carries a `(4,4)`
  minimum in `test_categories`, so the existing skip machinery handles it.
- **`TEST_SF_FACEBONES_EXPORT`**: a **real user-facing bug on Blender 4.x**, not a test artifact.
  `ShaderExporter.__init__` guarded `if blender_obj.active_material:` but then did
  `self.material.node_tree.nodes` unconditionally. Blender 5.x removed non-node materials so
  `node_tree` is always present there; on 4.x `bpy.data.materials.new()` yields
  `use_nodes = False` and `node_tree = None`. **Any 4.x user exporting a mesh whose material never
  had "Use Nodes" switched on got "Export of nif failed" and nothing more.** Now warns and exports
  without shader properties. The test also sets `use_nodes = True` so it exercises the same path
  on every version.

**`TT.min_version` had never worked.** It wrote `fn.__dict__["min_version"]` while
`execute_test` reads `min_blender_version`, and stored a `set` rather than a tuple (so the
comparison against `bpy.app.version` would have raised even with a matching key). Its one existing
use was a no-op. Fixed as part of gating Briarheart.

**Result: Blender 4.2 goes 156 failures -> 4 -> 0.** 235 passed, 47 skipped (the ANIMATION and
HKX categories already required 4.4, plus the three newly gated). 5.1 and 5.2 stay 282/282.

#### Notes for later

- `make_maprange` appends the **socket** to `nodelist` where `make_mixnode` appends `socket.node`.
  `relative_loc` reads `.location`/`.width`, which a socket doesn't have -- so that path would
  raise if ever reached with a socket and no `location`/`neighbor` argument. Preserved verbatim
  rather than "fixed" silently; worth a look.
- `make_specular` assigns `m = make_mixnode(...)` and never uses `m`.
- The `Wrap U` / `Clamp S` site (now `except KeyError`) is compat with **our own** older
  `UV_Converter` node group, not with Blender -- still the separate decision noted above.

---

## Phase 3 — test infrastructure drift

Three drifts, small individually, all away from rules we set deliberately.

- [x] **CH-3.1** — **Retire the 12 remaining `CHK.CheckNif` call sites** — `blender_tests.py` lines 235, 939,
      2502, 3066, 4695 and 7 more. `CheckNif` was retired as an experiment that didn't work out;
      replace each with explicit assertions as those tests get touched. Opportunistic, not a
      sitting.
- [x] **CH-3.2** — **Bring `@TT.expect_errors` back down.** It now guards **72 of 282** Blender tests (26%).
      Most of them exist because post-export re-import can't find textures or materials — which is
      what the `NifFile` fallback search-path work is for. That plan is the fix; this is the
      metric that says it's worth doing.
- [x] **CH-3.3** — **Split `blender_tests.py`.** 13,708 lines / 656 KB / 282 tests in one file. Not urgent and
      not risky, but only worth starting when nothing else is in flight.

### Phase 3 results so far (2026-08-20)

4.2 235 passed / 5.1 and 5.2 282 passed / pyn 146 / anim 18.

**CH-3.1 — `CheckNif` retired. It was 35 call sites, not 12**: my audit only counted
`blender_tests.py`, but `pynifly_tests.py` had 23 more. Built an exact call map by instrumenting
the dispatcher and running both suites, so every rewrite is evidence-based rather than inferred.

Removed the `test_files` registry and the `CheckNif` dispatcher -- the "per-file setup" that was
the actual objection -- and pointed each site at the specific checker it was already resolving to
(`CHK.Check_malehead(nif)` etc.). `Check_kalaar` was registered but never invoked; deleted.
`CheckNif_voidshade` renamed `Check_voidshade` for consistency.

*Not* done: inlining each checker's assertions into its test. `Check_malehead` alone is 86 lines
and is called from 4 sites; full inlining would add well over a thousand lines to the two files
CH-3.3 exists to shrink. The residual "too rigid" complaint is that e.g. `TEST_SKYRIM_XFORM`
(transforms) and `TEST_PARTITIONS` (partitions) both run all 86 malehead assertions. The fix is to
split the big checkers into focused pieces (`Check_malehead_transforms` / `_partitions` /
`_shader`) so each test opts into what it is about -- worth doing, but it belongs with CH-3.3.

**CH-3.2 — `expect_errors` 72 -> 56 tests, 122 -> 83 whitelist strings.** Rather than guess which
were band-aids, instrumented the log handler to record which whitelist entries actually match a
message, ran the full suite on **4.2, 5.1 and 5.2**, and took the union. 42 of 122 entries never
matched anything on any version -- stale suppressions left behind after the underlying warnings
were fixed. Removed those; 19 decorators went away entirely.

The measurement also found a bug it was not looking for. **Three decorators passed a bare string
instead of a tuple** -- `@TT.expect_errors('Unknown block type: NiBinaryExtraData')` and
`@TT.expect_errors( ("references invalid group"))` (parens, no comma). `expect_errors` stored it
verbatim and the handler did `any(e in msg for e in self.expected_errors)`, which iterates a
string **character by character** -- so any message containing `r`, `e`, `f`... was suppressed.
**`TEST_EXPORT_HANDS`, `TEST_FACEBONES` and `TEST_FACEBONES_RENAME` had all error checking
silently disabled** and would have passed no matter what the addon logged. `expect_errors` now
coerces a bare string to a one-tuple so it cannot recur, and all three tests pass with only their
stated message suppressed -- the character matching had not been hiding anything else.

**Caveat, found 2026-08-21 -- and the underlying cause has since been fixed properly.**
The pruning rested on *one observation per Blender version*.
`TEST_FACEGEN_SE` names YAS/Lykaios textures that live in a mod folder rather than the vanilla
assets directory the suite points at, so whether they resolve depends on machine state. Its
`'Could not find texture'` / `'Could not load'` entries measured as never-firing on all three
versions, were pruned, and later fired on 5.2 -- breaking that test.

Rather than restore the whitelist, the fixture now carries its own textures (Bad Dog's call:
*"I'd really prefer to have the textures in the fixtures"*). Two changes were needed, because
only fixing the first left the second half of the round trip still warning:

1. `facegen.nif` moved to `tests/tests/SkyrimSE/meshes/`. `find_referenced_file` searches
   relative to the nif **only if `'meshes'` is in the nif's path** -- otherwise that branch is
   skipped entirely. All 12 referenced textures were added under the sibling `textures/` tree
   as 64x64 DXT5 placeholders per the FFO recipe: **26.8 MB of source art -> 50 KB**.
2. The re-import half reads `tests/tests/Out/TEST_FACEGEN_SE.nif`, which has no `meshes`
   component either, so the fixture tree is now registered on the addon's alternate-path
   preferences by `TTB.test_file` alongside the `texture_directory` it already sets. Slots 1-2
   were empty, so nothing configured was clobbered.

The general caveat still stands for the other removals: anything environment-dependent could
have been pruned the same way. Treat the 42 as "measured once", not "proven dead".

The remaining 83 entries look legitimate: warnings the test deliberately provokes (19x "assigned
to more than one partition", "will not dismember in game"), and unsupported-feature notices
("Unknown block type: ...", "bhkPhysicsSystem decode failed"). The **materials/texture** band-aid
class is smaller than the audit assumed, so `project_niffile_fallback_paths` is worth doing on its
own merits but is not what is holding this number up.

#### CH-3.3 — `blender_tests.py` split into `tests/blender/`

13,708 lines in one file became a package of nine domain modules plus a 218-line aggregator:

| module | lines | module | lines |
|---|---|---|---|
| `test_animation.py` | 2,835 | `test_shaders.py` | 1,206 |
| `test_collision.py` | 2,230 | `test_skyrim.py` | 649 |
| `test_bodyparts.py` | 1,982 | `test_tri.py` | 574 |
| `test_starfield.py` | 1,539 | `test_geometry.py` | 573 |
| `test_fo4.py` | 1,450 | `common.py` | 485 |

**File assignment came from the `@TT.category` decorators, not from judgement.** Every one of the
282 tests carries one, so a priority list (STARFIELD > HKX/ANIMATION > PHYSICS/COLLISION/MOPP >
SHADER > TRI > PARTITIONS/CONNECTPOINT > BODYPART/ARMATURE > XFORM/TREE > FO4 > SKYRIM) decides
the file. The tie-break is feature-file-wins unless the test is about game-specific behaviour.

**Nothing was retyped.** The file was carved into 339 ordered top-level blocks covering every
line, each block moved verbatim, and the leftovers (imports, the reload preamble, `log`,
`ALWAYS_EXPECTED`, `TestLogHandler`, `test_loghandler`, and the 9 shared helpers) collected into
`common.py`. `TEST_NOBLECHEST.category = {'ANIMATION'}` -- a bare attribute assignment sitting
between two functions -- was detected and kept with its test.

`common.py` ends with an explicit `__all__` built from `globals()`: a bare `import *` skips
leading-underscore names, which would have dropped `_np_bodies`, `_uparm_r_cuts` and friends.

**Verification was set equality, not a pass count.** The passing-test set was captured on 4.2,
5.1 and 5.2 before the split and compared after: **identical on all three** (235 / 282 / 282),
zero lost, zero gained. Since discovery order changed (dict insertion order across nine star
imports rather than one file's source order), that also demonstrates no test depended on the old
ordering. pyn 146 and anim 18 unchanged.

`test_runner.py` now reloads `tests.blender.*` before the aggregator -- reloading
`blender_tests` alone re-runs its star imports against modules already in `sys.modules`, so an
edit to a test file would have been silently ignored.

**CH-3.1's residual is closed, not deferred.** Splitting the big checkers so each test opts into
only the relevant assertions was offered and declined -- Bad Dog, 2026-08-20: *"I'm happy for the
one test to check everything. It's not wrong."* A fixture checker asserting everything about that
fixture is fine; what was wrong with `CheckNif` was the registry and the magic dispatch, both of
which are gone. See CH-X4.

---

## Phase 4 — docs that contradict the code

- [x] **CH-4.1** — **`README.md`** — last commit 2026-03-18, before Starfield material I/O, FO4 collision
      export, SF morphs and the HKX skeleton writers all shipped. It's the file users read.
- [x] **CH-4.2** — **`DEVELOPERS.md`** (2026-03-12) and **`PROJECT_PLAN.md`** (2026-03-31) — same vintage.
      Decide whether `PROJECT_PLAN.md` still has a job now that `docs/plan_*.md` carries the real
      planning.

### Phase 4 results (2026-08-20)

**README** — the version line was fixed in Phase 2; the feature list still said "Supports FO4,
Skyrim LE, Skyrim SE" and predated everything shipped since March. Now covers Starfield, FO4
dismemberment cut offsets, collision *export* (Skyrim MOPP and FO4 native physics), hkx skeleton
export, trees/switch nodes, and the named property panels.

**DEVELOPERS.md** — had four things that were actively wrong, not merely stale:

- The project tree listed four directories; there are twelve. It also still described
  `tests/blender_tests.py` as "main test cases". Rewritten, with the `pyn/` no-`bpy` rule stated
  explicitly and a note on where to put a new test.
- The example called `ND.NifFile(outfile)` — an alias that does not exist anywhere in the suite.
  Now `pyn.NifFile`.
- The check-routine list was missing `is_neq`, `is_le`, `is_true`, `get_property` and the entire
  `assert_*` family (17 functions).
- The category list included `'FO3'` and `'MESH'`, neither of which is a category, and omitted
  twelve that are in use — including `'STARFIELD'`, `'HKX'` and `'MOPP'`. The `do_tests` example
  selected `categories=['SKYRIM', 'MESH']`, which would have matched nothing.

Also replaced the "open Blender, load the script into the text editor" instructions with the
headless command, since that is how these are actually run, plus the two traps that cost time:
`PYNIFLY_DEV_ROOT` is the **parent** of the checkout, and the per-version addons directory must
be a junction rather than a copy.

Two facts worth recording that came out of checking the category list:

- **Only `'ANIMATION'` and `'HKX'` carry a real version minimum** (4.4). The other 19 entries in
  `test_categories` are `(3,0)`, i.e. no constraint beyond the addon's own 4.0 floor. Twelve
  categories in use are not declared at all and default to `(0,0)` — harmless, but the dict is
  not the taxonomy it looks like.
- **`'BODYPARTS'`, `'SHAPEKEYS'` and `'FURNITUREMARKER'` were typos** of `'BODYPART'`,
  `'SHAPEKEY'` and `'FURNITURE'`, used by 2, 1 and 3 tests, silently creating a parallel category
  nothing could select. **Fixed on request** (2026-08-20): the six sites renamed, the canonical
  list moved to `TT.TEST_CATEGORIES` in `test_tools.py` and completed with the twelve categories
  that were in use but undeclared, and `@TT.category` now raises `ValueError` on an unknown name
  so the next typo fails at import. All three targets were declared `(3,0)` and the typo forms
  defaulted to `(0,0)`, so nothing was gated differently -- passing sets identical on 4.2/5.1/5.2.

**PROJECT_PLAN.md** — kept; it holds reminders and format notes that have no other home. Given a
header saying what belongs there versus `docs/plan_*.md` and `TODO.md`. Its one "Open Issue", the
UV V-flip in the core library, is **done** — resolved exactly as the note proposed. There is no
`1-v` left anywhere in `pynifly.py`; the flip is now in the Blender export path at
`export_nif.py:2028`. Moved to Done with that evidence.

Its FO4 packfile offset table looked like a duplicate of `docs/fo4_havok_packfile_format.md` and
was nearly deleted as such. **It is not** — the offset sets barely overlap because the two use
different bases (that document covers the packfile as a whole; this table is the `body_props`
array). Cross-referenced both ways instead.

---

## Phase 5 — guardrails

There is no `.github/`, no ruff or flake8 config, and no pre-commit. Nothing catches the class of
defect that costs nothing to fix and everything to find later — Phase 1's escape sequences are
exactly that class.

- [x] **CH-5.1** — **Add a ruff config with a deliberately narrow rule set.** `W605` (invalid escapes), `F401`
      (unused imports), `E722` (bare except) as a warning only, so it reports without blocking
      while Phase 2 runs. Resist enabling more; a linter that shouts is a linter that gets muted.
- [ ] **CH-5.2** — **A push-triggered GitHub action that runs ruff.** The test suite needs Blender so CI can't
      run it, but lint costs nothing.
- [x] **CH-5.3** — **43 stray `print()` calls in shipping modules** — `sf_cdb` 9, `anim_skyrim` 9,
      `cloth_autounpack` 7, `bgsmaterial` 7, `bhk_autounpack` 3, and 8 more. The rule is
      `log.debug`, not `print`. Excludes `io_scene_nifly/scripts/`, which is standalone tooling.

### Phase 5 results (2026-08-21)

`ruff check .` **passes at zero**, and the guards were verified by injecting a duplicate
class, a mutable default and a bad escape into a file -- all three caught.

**CH-5.1 -- `ruff.toml`.** Ruff is a local tool (`pip install ruff`; the VS Code extension is
where it earns its keep). The rule set is chosen so the tree is at **zero**, because zero is
what turns a new finding into a signal; a standing backlog is a dashboard nobody reads.

Selected: `F`, `E4`, `E7`, `E9`, `W6`, `B006`, `B023`. Getting there needed real fixes:

- **`F811` found three classes defined twice in `pynifly.py`** -- `BSEffectShaderProperty`,
  `BSShaderPPLightingProperty` (both 2-line stubs shadowed by real definitions later) and
  `BSEffectShaderPropertyFloatController`, whose first copy carried the **wrong**
  `buffer_type`. Both copies stay alive in `NiObject.__subclasses__()`, so
  `register_subclasses()` registered both and the later one won:
  `buffer_types[BSEffectShaderPropertyBufType]` held a `NiFloatInterpController`. Anything
  constructing an effect-shader block *by buffer type* got the wrong class. Deleted the dead
  definitions; `TEST_NO_DUPLICATE_BLOCK_CLASSES` fails before and passes after.
- `F541` -- 444 f-strings with no placeholders, auto-fixed.
- `E713`/`E714`/`E401`/`E703` -- 31 auto-fixed.

Explicitly ignored, each annotated in the file with its count and reason, as **debt rather
than policy**: `F401` (153), `F841` (170), `E722` (53), `E721` (29), `E711` (20), plus the
`F403`/`F405` that the `tests/blender` star-import design requires and the `E701`/`E702`
that are Bad Dog's house style.

Two rule families were measured and rejected on evidence rather than taste: **bugbear's
`B006` and `B023` were the only ones worth keeping** -- of the other 203 bugbear findings,
the bug-shaped ones were false positives on this code. `SIM`/`UP`/`PL`/`C4` add ~4,700
findings and nothing of value here.

**CH-5.3 -- the "43 stray `print()`" figure was wrong.** Classifying each call by what
encloses it: 28 sit under `if _DEBUG:` or inside `__main__`/CLI blocks, and of the 15 left,
13 are in self-test harnesses (`TEST_READ_BGSM`, `execute_test`, `TEST_CAM`), a CLI entry
point (`sf_cdb._cli`) or a print-by-design helper (`_print_with_parent`). **Exactly one was
on a runtime path**: `connectpoint.connection_name_root` printed
`"WARNING: connection name malformed"` instead of logging it -- so it bypassed the log
handler entirely and could never fail a test. Now `log.warning`.

**CH-5.2 -- the GitHub action is deliberately not done.** The suite needs Blender so CI
cannot run it, and for a solo developer with no PR flow a push-triggered lint adds little
over the editor extension. Left open rather than closed, in case that changes.

---

## Phase 6 — test the untested new code

- [ ] **CH-6.1** — **`pyn/sf_cdb.py` — 727 lines, zero test references** in any of the three test files. It's
      the only module from the recent push without tests, and it's pure `pyn/` code with no
      Blender dependency, so it's the easy kind to cover. One functional test in
      `pynifly_tests.py` against a real `materialsbeta.cdb` slice — open it, pull a known
      material, assert its fields — covers the parser's spine.

---

## Standing habits, not scheduled work

These don't get ticked off; they change what happens the next time a file is opened.

**CH-S1 — Split before you extend.** Five functions are past the size where a reader holds the whole
thing in their head. Don't refactor them speculatively — they work and they're tested. But the
next time one of them is opened to change behaviour, split the part being touched out first.

| lines | cc | location |
|---|---|---|
| 310 | 64 | `bhk_autounpack.py:1059` `extract_bhk_physics_system` |
| 269 | 62 | `export_nif.py:1907` `export_shape` |
| 271 | 50 | `bhk_autopack.py:1355` `_write_cm_shape` |
| 196 | 54 | `anim_fo4.py:426` `_decompress_spline` |
| 206 | 50 | `pynifly.py:805` `Create` |

`extract_bhk_physics_system` is the one worth doing deliberately rather than opportunistically,
since FO4 collision is still active work.

**CH-S2 — Watch the `hkx/` byte-level helpers.** `anim_fo4.py` and `anim_skyrim.py` maintain their own
copies of `align`, `_hkarray`, `write_string`, `_u`, `_f`, `_i`, `_w_u`, `_read_hkarray_u`,
`rel` and `_parse_*`. The format divergence justifies two files; it doesn't justify two copies of
the primitives. If one of these needs a fix, fix both — or lift that set into a shared module.

## Deliberately not doing

- **CH-X1 — Chasing the 44% docstring coverage number.** The worst file is `nifdefs.py` at 2%, which is
  mostly ctypes struct declarations that don't want prose. Coverage as a target would make it
  worse.
- **CH-X2 — Breaking up `NifExporter` (1,982 lines / 54 methods) or `NifImporter` (2,093 / 52).** They're
  large but not chaotic — late-bound state is what makes big classes unworkable and it's
  essentially absent (45 of 50 and 34 of 35 attributes declared up front). The cost of splitting
  them exceeds the benefit right now.
- **CH-X4 — Splitting the fixture checkers in `test_nifchecker.py` by topic.** `Check_malehead`
  asserts transforms, block types, partitions, shader properties and textures, and four tests call
  it. Declined 2026-08-20: a checker that asserts everything about a fixture is not wrong, and the
  breadth was never the problem -- the `CheckNif` registry and dispatch were, and those are gone.
- **CH-X3 — Merging `anim_fo4.py` and `anim_skyrim.py`.** The packfile versions genuinely differ. See the
  standing habit above instead.

---

*Audit method: AST analysis for size/complexity/attribute discipline, a 12-line-window hash scan
for duplication, and an import-graph walk for cycles and layering. Structural only — this was not
a bug hunt.*
