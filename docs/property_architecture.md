# PyNifly Property Architecture

**Status:** design agreed; implementing (proof-of-concept slice first).
**Goal:** move PyNifly from generic per-object custom properties (`obj["pynX"]`) to typed,
game-sectioned `PropertyGroup`s surfaced in custom Panels, so game-specific data looks built-in.

**Decision (2026-07-08):** do the **full cross-game conversion now**, as a foundation phase *before*
the Starfield mesh work — not SF-first-with-legacy-deferred. Rationale: Starfield already forces a
major version, so the compat break is paid once; SF is then built on the final system from day one
(no coexistence/re-conversion); and we validate the whole approach on **FO4/Skyrim, which have
strong test coverage** (net catches regressions). Low risk — it's Blender-side refactoring guarded
by the suites.

**Approach:** build the infra + convert **one representative slice** (shader properties) first, run
the suites, evaluate the pattern; if good, roll out to the rest, then do the SF mesh work.

---

## 1. Current state (what we're moving from)

- NIF data stored as generic ID custom props: `obj["pynBlockName"]`, `obj["pynNodeFlags"]`, …
- Bulk-populated by `ninode.properties.extract(obj, ignore=NISHAPE_IGNORE, game=…)` — walks a buffer
  struct and writes each field to `obj[...]`. `NISHAPE_IGNORE` = fields *not* stored because
  recoverable from the Blender representation (handled by hand in import/export code).
- One `PropertyGroup` precedent (`nif/controller.py`); simple `register()` in `__init__.py`.

**The `extract()` model stays valid** (Bad Dog): pass-through properties (read → store → write back
unchanged) go through `extract()`; properties used in the Blender representation are hand-coded and
listed in the ignore list. The only change here is *where `extract()` writes* (typed group, not `obj[]`).

---

## 2. Target architecture

### 2.1 Typed groups, game-sectioned, per Blender data-type

A `bpy.types.PropertyGroup` per (data-type × concern), attached via `PointerProperty` to the ID type,
surfaced by a custom `Panel`. File-level data lives on the **NIF-root Empty** (per-nif, discoverable),
**not** on `Scene`.

```
NIF-root Empty (Object) → pyn        {game (user-settable enum), ...file-level}
Object                  → pyn        shared node fields: block_name, node_name, node_flags, …
                          pyn_sf     Starfield BSGeometry (on the BSGeometry Empty): is_internal_geom
                          pyn_sf_lod Starfield LOD child (on each LOD mesh object): mesh_path, lod_slot
                          pyn_fo4    FO4-specific node/shape fields (segment file, …)
                          pyn_sk     Skyrim-specific fields
Material                → pyn_shader shared shader fields (the bulk — see slice below)
                          pyn_sf_mat Starfield material: mat_path (.mat)
                          pyn_fo4_bgsm  FO4 BGSM-specific fields
```

- **Per-game fields = exactly what `extract()` writes today** (buffer-struct fields not in the ignore
  list), reorganized by game. Enumerated from `nifdefs` per group when built — no new field inventory.
- `mod_prefix` (e.g. `FSF`) is a **user/export setting → addon preferences / export operator**, not
  object data.
- Values persist in the `.blend` like custom props — purely a better front end + type system.

### 2.2 Panels — visibility keys off the user-settable `game` field

- A "PyNifly" panel per relevant Properties tab (Object, Material) draws the shared group + a
  **game-specific sub-block shown conditionally on the object's/nif's `game` field** — which the user
  can change. So porting Skyrim→SF = flip `game` to Starfield and the SF panel appears (same path
  serves authoring a new SF asset). **Panels follow the field, not the file's origin.**
- Typed widgets: enums→dropdowns, bools→checkboxes, paths→string fields with tooltips.

### 2.3 Registration

- Each `PropertyGroup`/`Panel` `register_class`'d in `register()`; each `PointerProperty` assigned to
  its ID type and cleared in `unregister()`. **Order:** a group must register before the ID assignment
  that references it; nested groups before containers.

### 2.4 Naming — separate per-game pointers

`obj.pyn` (shared) + `obj.pyn_sf`, `obj.pyn_fo4`, `obj.pyn_sk`, `obj.pyn_shader`, `obj.pyn_sf_mat`, …
Each game's group is its own registered PropertyGroup that every object nominally carries (empty for
other games — trivial overhead), so each game's module owns its group and games are added/removed
without touching a shared container. Fits the `sf_properties.py` / `fo4_properties.py` module split.

---

## 3. Migration (`.blend` backward-compat, at this conversion)

- `extract()` gains a mode that writes the typed per-game group instead of `obj[...]`; import/export
  read/write the groups.
- One-time **`.blend` migration**: on load of an old file, read legacy `obj["pynX"]` → the new groups
  (drive from the same `nifdefs` field lists). Break compat once, cleanly, at the major-version bump.

---

## 4. Phasing

1. **PoC slice — shader properties.** Build the properties-module infra (base + registration helper),
   a `pyn_shader` group (+ `pyn_sf_mat`/`pyn_fo4_bgsm` game blocks as the fields split), a Material
   panel, redirect the shader `extract()`/read-write to the group. Run the shader tests + full suite.
   **Evaluate the pattern here.**
2. **Roll out** to node/shape groups and the remaining subsystems (collision, controllers, etc.),
   game by game, tests green at each step.
3. **`.blend` migration** for legacy files.
4. **Then** the Starfield mesh work (`sf_geometry.py`, `sf_mesh.py`) on the finished property system.

---

## 5. Resolved decisions

1. Per-shape props on the **Object** (LODs are separate objects; matches current `obj[...]`). ✔
2. **Separate per-game pointers** (`pyn_sf`, `pyn_fo4`, …). ✔ (implications in §2.4)
3. `extract()` **kept** for pass-through props, now writing the typed group; hand-coded/ignore-list
   for Blender-represented props. Field→game comes from the buffer type / `extract()`'s `game` arg. ✔
4. Scope: architecture + SF detail now; other games' fields enumerated from `nifdefs` **as each group
   is built during rollout** (mechanical). ✔
5. File-level props on the **NIF-root Empty**, not Scene. Panels in Object/Material Properties tabs. ✔
