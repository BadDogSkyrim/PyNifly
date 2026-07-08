# Starfield NIF Import/Export — Implementation Plan

Plan for adding Starfield support to PyNifly. Grounded in the format research in the
Bethesda Library (`docs/file-formats/starfield-*.md`) and the design decisions below.
Sequenced import-first (validate against known vanilla assets before tackling export).

Testing follows the project TDD rule: failing test at the lowest level that can express
the bug → fix → confirm; full suite (DLL `TestDLL.cpp` + pyn-layer + blender) at check-in.
Rebuild the Debug DLL after each C++ change.

---

## Design decisions (settled)

- **`.mesh` is external, referenced from `BSGeometry`.** Positions int16/32767×Scale, UDEC3
  normals/tangents, float16 UVs, `{u16 bone, u16 weight}` skinning (variable count — the vanilla
  body uses **6**, not 4), meshlets+cull = derived (regenerate on export).
- **Scale/units DECIDED: game units, same as Skyrim/FO4** (not raw metric). nifly applies
  `havokScale` (69.969) on **both** read (`unpack`) and write (`pack`) — so we get SSE-sized
  positions for free and round-trip is FP-exact (same constant both ways; int16 quantization is the
  real precision floor). Game units keeps Starfield in the same magnitude regime as PyNifly's
  existing tolerance/epsilon code, matches Outfit Studio (also nifly/69.969) for interop, and lets
  the existing configurable import scale apply identically. Metric would mean fighting nifly and
  breaking magnitude-dependent logic — only worth it as a deliberate *tool-wide* move, not
  Starfield-only. 69.969-vs-69.9866 is a ~0.02% absolute-size question, irrelevant to round-trip.
- **Blender representation:** NIF-root Empty → **`BSGeometry` Empty (always, even single-LOD)** →
  **one child mesh object per LOD** (`.mesh` files are genuinely independent meshes — cannot be
  faked with vertex/face groups). Support all **4 LOD slots** from the start.
  - The Empty owns everything shared/non-geometry: node name, transform, shader/material ref,
    skin instance + `SkinAttach` bone list, alpha property, flags.
  - Each child owns: its geometry, its weights/vertex-groups, the shared material, and its
    round-trip metadata (below).
- **Mesh-path round-trip:** on import, store each shape's `.mesh` path(s) **verbatim** (the raw
  `meshName` — no `geometries\` root, no `.mesh` ext) + an explicit **LOD-slot index (0–3)** +
  the internal/external `0x200` flag. On export, write back to the recorded path (round-trip /
  in-place replacer); if a child has **no** recorded path (newly added), fall back to
  auto-forming `geometries\<prefix>\<name>.mesh`. User can hand-edit the path to redirect
  (import vanilla → change path → export as a new standalone asset).
- **Asset namespace:** short mod prefix **`FSF`** used across ALL shared, flat global folders —
  `geometries\FSF\`, `meshes\FSF\`, `textures\FSF\`, `materials\FSF\`, `meshes\morphs\FSF\` —
  and record EditorIDs (`FSF_...`). Mind the **46-char** BSGeometry mesh-path limit. Collision
  avoidance is probability+discipline, not guaranteed. PyNifly exporter gets a configurable
  "mod prefix" field that auto-forms the prefixed path (don't rely on Blender object names).
- **Property architecture:** move from generic custom-property dicts to typed **PropertyGroups +
  custom Panels**, game-sectioned (shared + per-game FO4/Skyrim/Starfield). Design the **whole**
  cross-game scheme up front; implement the **Starfield** part now; leave FO4/Skyrim on legacy
  custom props for now and convert them **all at once at a major version bump** (break backward
  compat once, cleanly) — not piecemeal.
- **Materials:** a loose `.mat` (JSON) is sufficient to ship — **no `.cdb` writer needed**.
- **Loose files only, no BA2 reading** (decided 2026-07-07). Consistent with how PyNifly already
  resolves textures/materials (it never cracks archives). `.mesh` resolves via the existing loose-file
  search; users extract vanilla assets to loose (BSArch/BAE) as they already do. BA2 reading is deferred
  — it would require a load-order-resolution subsystem (active archives, override precedence) with no
  authoring-workflow payoff.
- **nifly update is low-risk:** `main` mirrors upstream and already has the SF `.mesh` I/O
  (`BSGeometryMeshData::Sync`, `Load/SaveExternalShapeData`, `GetExternalGeometryPathRefs`);
  PyNifly's own nifly edits are a small isolated set on `BD_PyNifly_Edits` touching unrelated
  code (shader env-map, bone-weights, fade-node, segments). Merge is additive and fully testable.

---

## Code & test organization

Keep all SF work on its own **`starfield` feature branch** (PyNifly repo). The nifly-fork upstream
merge is a *separate* branch in that repo (throwaway/test first → adopt into `BD_PyNifly_Edits` only
after suites pass).

SF handling is large and game-specific → give it its own modules, mirroring how `nif/` already
splits `collision.py` / `shader_io.py` / etc. Keep game **detection/dispatch thin** in the core files
(`import_nif.py`/`export_nif.py` just detect `game == 'SF'` and delegate); put SF **logic** in:

- `nif/sf_geometry.py` — SF `BSGeometry`/`.mesh` import **and** export (Empty+LOD-children build,
  loose-`.mesh` resolve, pack/unpack).
- `nif/sf_properties.py` — Starfield PropertyGroups + panel (Stage 1). Becomes the template for the
  eventual per-game property modules (`fo4_*.py`/`skyrim_*.py`) at the legacy conversion.
- `pyn/sf_mesh.py` — `.mesh` format handling / `BSGeometry` mesh-data at the wrapper level (keeps it
  out of the already-5,300-line `pynifly.py`; revives the old removed `sfmesh.py` idea, done right).
- `nifdefs.py` — SF buffer structs stay here, grouped in a clear SF block.
- *(optional)* `NiflyDLL/NiflyWrapperSF.cpp` for SF DLL exports — only if it grows; verify the
  function-table setup splits cleanly first.

Tests: **split SF out** (the current `blender_tests.py` is ~11.5k lines, `pynifly_tests.py` ~5.4k):

- `tests/sf_tests.py` (pyn-layer) and `tests/sf_blender_tests.py` (Blender).
- Confirm how `test_runner.py` / the suites aggregate tests (master list vs auto-discovery) and wire
  the new files in.

## Stage 0 — nifly foundation & de-risk — ✅ DONE (2026-07-08)

- [x] **Base branch = `main`**, not `BD_PyNifly_Edits`. Verified: PyNifly builds against `main`;
      `BD_PyNifly_Edits`'s 3 customizations (env-map-scale, BSFadeNode/segment, `GetShapeBoneWeights`-0)
      are superseded by upstream / not needed (bone-weight tests pass). Approach became a clean
      **fast-forward of `main` to `upstream/main`** (`965a1da`), not a merge.
- [x] **3 wrapper API adaptations** in `NiflyWrapper.cpp` (from upstream's shader refactor, *not*
      our customizations): `buf->shaderFlags` — upstream deleted the legacy `uint16 shaderFlags` from
      `BSShaderProperty`; field kept for buffer ABI, now vestigial (read→default 1, write dropped).
      `textureClampMode` — now a strongly-typed `TexClampMode` enum → explicit cast on write.
- [x] Built Debug + Test DLLs; **DLL tests 73/73 pass, pyn suite all pass (+18 anim)**. Shader/clamp/
      bone-weight tests confirm the adaptations are correct.
- [x] Merged nifly provides: `BSGeometryMeshData::Sync`, `Load/SaveExternalShapeData`,
      `GenerateMeshlets`, internal/external `0x200`, `GetExternalGeometryPathRefs`, `BSSkin::*`,
      `IsSF` = **172–175**, **`SkinAttach` bone-name fallback** (closes the open item below).
- [x] ~~Open item: SkinAttach string names~~ — RESOLVED: upstream commit `b523a58` adds the SkinAttach
      bone-name fallback.

**Repo state (uncommitted — Bad Dog to review/commit):** nifly local `main` fast-forwarded to
`upstream/main` (34 ahead of `origin/main`, **not pushed**); PyNifly `NiflyWrapper.cpp` has the 3
fixes (uncommitted on `main`); throwaway `sf-merge-test` branch exists (deletable). Blender-test suite
not yet run (heavier; run before final adoption).

## Stage 1 — Property architecture (design whole, implement Starfield)

Design the ultimate cross-game scheme; implement only Starfield now.

- [ ] **Design doc: the ultimate PropertyGroup scheme** (all games), mapping NIF concept → Blender
      data type → PropertyGroup:
  - NIF file (root Empty / Scene): `pyn_nif` — game/version, source path, mod-prefix setting.
  - Node / shape (Object): shared `pyn_node`; per-game `pyn_sf_geom` (BSGeometry: internal flag,
    per-slot mesh paths), `pyn_fo4_shape`, `pyn_sk_shape`.
  - LOD child (Object): `pyn_sf_lod` — `mesh_path` (verbatim `meshName`), `lod_slot` (0–3).
  - Shader/material (Material): shared `pyn_shader`; `pyn_sf_material` (.mat ref, layered),
    `pyn_fo4_bgsm`.
  - Skin/bones (Armature/Bone), collision, etc. — enumerate for the full design; implement later.
  - Registration lifecycle (PointerProperty registration order), and a **migration story** for
    existing `.blend` files (the future big-bang legacy conversion reads old custom props → new
    groups at the major-version bump).
- [ ] **Implement the Starfield groups + a "Starfield" Panel** (Properties editor, game-conditional
      `poll`/draw). Import writes them; export reads them. Legacy FO4/Skyrim stay on custom props.
- [ ] Schema is largely derivable from the existing `nifdefs` buffer structs.

## Stage 2 — DLL wrapper (NiflyDLL)

New wrapper functions (root `NiflyWrapper.cpp`; `getXxxLen`/`getXxxData` pattern for blobs):

- [ ] `BSGeometry` read: mesh-path refs (per slot), internal/external flag, LOD count, shader &
      skin refs.
- [ ] **`.mesh` resolve + read — LOOSE FILES ONLY** (BA2 deferred, see below): resolve the path via
      the **same loose-file search PyNifly already uses for textures** (Data folder + configurable
      search paths). If not found loose, fail with a clear "extract `<path>` from the BA2 first"
      message. Feed the loaded bytes to `LoadExternalShapeData`. Expose verts/tris/UV/normals/
      tangents/colors/weights.
- [ ] `.mesh` write: `SaveExternalShapeData` to a resolved path; meshlet+cull regen via nifly
      `GenerateMeshlets`.
- [ ] Skin: bone-name list (`SkinAttach`), per-vertex `{bone,weight}` (variable count).
- [ ] `TestDLL.cpp` tests at each step (read a real vanilla `.mesh`, round-trip bytes).

## Stage 3 — Python ctypes layer (`io_scene_nifly/pyn`)

- [ ] `nifdefs.py`: buffer structs for BSGeometry + mesh data (+ `PynBufferTypes` entries).
- [ ] `niflydll.py`: signatures for the new DLL functions (set directly, no try/except guards).
- [ ] `pynifly.py`: `BSGeometry` NiObject subclass + mesh/LOD access; NifFile SF read/write.
- [ ] pyn-layer tests (`tests/pynifly_tests.py`, no Blender) — parse a real `.mesh`, check counts.

## Stage 4 — Blender import (`nif/import_nif.py`)

- [ ] Detect Starfield (stream 172–175). Build the NIF-root Empty.
- [ ] `BSGeometry` → **Empty**; each LOD `.mesh` → **child mesh object**. Resolve+read via DLL.
- [ ] Geometry: positions come from nifly **already in game units** (havokScale applied), so treat
      like FO4/SSE and apply the existing configurable import scale; UDEC3 normals, float16 UVs,
      colors; weights → vertex groups (variable count, handle >4).
- [ ] Skin: build armature from `SkinAttach` bone names; bind each child.
- [ ] Material: read `.mat` → Blender shader (reuse the FO4 material-path plumbing; MVP = layer-1
      Principled, note multi-layer). Normal reconstruct-Z + green-invert.
- [ ] Populate the Starfield PropertyGroups (mesh paths, LOD slots, internal flag, .mat ref).
- [ ] Blender tests (`tests/blender_tests.py`, via `test_runner.py`) — import a vanilla body/head,
      assert structure/counts/bones.

## Stage 5 — Blender export

- [ ] Empty+children → `BSGeometry` + N `.mesh` files. Mesh-path from recorded prop (round-trip) or
      `geometries\<prefix>\<name>.mesh` fallback; enforce the **46-char** limit; honor internal/
      external flag.
- [ ] Pack geometry (int16 positions, UDEC3 normals **packed by PyNifly** — nifly's encoder has the
      `&=`/`|=` bug, or use the fixed merged version), regenerate meshlets+cull.
- [ ] Skin, material (emit loose `.mat` — clone a shipped template `Skin5Layer`/`Hair1Layer`,
      regen resource IDs, swap textures/params).
- [ ] Round-trip tests: import → export → re-import, assert fidelity (paths, LOD slots, geometry).

## Stage 6 — Materials (`.mat`), deeper pass

- [ ] Fuller `.mat` import (layered → Principled-per-layer composited by blenders) and export
      (template clone). Can follow Stage 4/5 once geometry round-trips.

## Later (separate phase) — morphs / chargen

- [ ] `morph.dat` R/W (port OS `SFMorphFile`: `MDAT`, per-vertex sparse deltas, ÷havokScale) and
      chargen wiring — deferred to the mod-building phase.

---

## Risks / open questions

- ~~Exact **havokScale** constant / unit convention~~ — **DECIDED**: game units via nifly's 69.969
  (see Design decisions). Round-trip FP-exact; the constant choice is a ~0.02% absolute-size question,
  not a round-trip concern.
- **SkinAttach** vs nifly's boneRefs model (Stage 0 open item).
- **BA2 read deferred** — loose files only for now (reuse the texture-path search). Importing a vanilla
  shape requires extracting both the NIF and its `.mesh` to loose (BSArch/BAE), by design. Revisit BA2
  reading only if the load-order subsystem it needs becomes worth it.
- Property-migration for existing `.blend` files at the eventual major-version legacy conversion.

## References

- Format docs: `Bethesda Library/docs/file-formats/starfield-{meshes,materials,chargen,plugins}.md`
- Reference impls: `ousnius/nifly` (`main`), Outfit Studio (`OutfitProject`), fo76utils/nifskope,
  SesamePaste233/StarfieldMeshConverter (`MeshIO.cpp`/`MorphIO.cpp`).
- Local tools: BSArch (`-sf1`), SF1Dump/xDump, extracted assets in `C:\tmp\sf_verify\`.
