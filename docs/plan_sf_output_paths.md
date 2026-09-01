# Plan: Starfield output paths (.mesh and morph.dat)

Status: **BUILT 2026-09-01, both suites green** (282 Blender / 148 pyn + 18 anim, 0 failed).
Not yet verified in game.

## Goal

Make the stored output paths for a Starfield shape express *where things go*, not *what one
particular shape was called*, so that splitting or duplicating a shape in Blender doesn't require
hand-editing a path on every copy.

The driving workflow: **model head, mouth and tongue as one object, then split it into three for
export.** Today both output paths — the external `.mesh` and the `morph.dat` pair — are copied
verbatim onto all three split objects, all three point at the original's files, and each one has
to be corrected by hand or the exports silently overwrite each other.

Both halves share one decision — *does this stored value name a file, or is it a stem to derive
from?* — so they're planned and built together.

---

## Measured facts this plan rests on

Established 2026-09-01 against the unpacked vanilla assets and Bad Dog's shipped Lykaios race.

- **Vanilla `.mesh` paths are uniformly one directory deep.** 364,377 `.mesh` files under
  `geometries\`, **100% at exactly one level**, every `meshName` **exactly 41 characters** —
  20 hex + `\` + 20 hex. The component-length set is literally `[20]`. Zero exceptions.
- **One level with a human-readable name is proven in game.** Bad Dog's rendering Lykaios head
  uses `FSF\LykaiosMaleHead`, with `geometries\FSF\LykaiosMaleHead.mesh` on disk, alongside
  `FSF\LykaiosMaleHead_fb` for the facebones companion.
- **Two levels has never been tried by anyone**, in vanilla, in this project, or in the wider
  tooling. Outfit Studio derives `NifName\ShapeName_Index` — also one level.
- **The `meshName` string must be ≤ 46 characters or the shape renders invisible in-game.**
  Sourced: the ExoRace author's *Creating a Playable Race* guide, recorded in the Bethesda Library
  at [`docs/game-specific/starfield/meshes.md`](https://baddogskyrim.github.io/BethesdaLibrary/)
  under Starfield → Meshes. PyNifly has never checked it, through an entire invisible-head saga.
- **The 40-hex name is not a computed or verified hash.** The game doesn't check it and no tool
  derives it from the mesh bytes (the only hashing in the pipeline is the CRC-32 resource ID for
  materials). We are free to invent our own digest with no compatibility risk.

The 46-character cap also retroactively justifies the `_fb` suffix on the facebones companion: a
vanilla-shaped hash is 41 characters, `+ _fb` is 44 — under. `_facebones` would be 51, over.

---

## Part 1 — the external `.mesh` path

### Today

`pyn_sf_geometry.mesh_path` holds the verbatim `meshName`: directory **and** filename, with no
`geometries\` root and no `.mesh` extension.

`export_sf_shape` ([sf_geometry.py:163](../io_scene_nifly/nif/sf_geometry.py#L163)) uses it whole,
and only generates a name when it's empty:

```python
mesh_name = grp.mesh_path if (grp and grp.mesh_path) else ''
if not mesh_name:
    mesh_name = 'FSF\\' + sanitize_mesh_component(sf_base_name(obj))
```

So directory-plus-derived-filename already exists — as the fallback, with `FSF\` hardcoded. This
plan promotes it to the normal case and replaces the fallback with a vanilla-shaped hash.

### The rule

Exactly one directory level. There is no trailing-separator convention and no ambiguity: a value
with a separator is directory + filename, a value without one is a directory.

| `mesh_path` | resolves to |
|---|---|
| *(empty)* | `<20hex>\<20hex>` — generated, then written back to the property |
| `FSF` | `FSF\<shape>` |
| `FSF\WolfHead` | `FSF\WolfHead` — verbatim, user owns keeping it distinct |
| `022faa031bcfca93c813\0b3a78e1d720af51f83d` | verbatim (the vanilla import case) |

A value containing a **second separator** is rejected with a clear message. We don't know that two
levels fails, but nothing has ever loaded one, one level already does everything we need, and the
failure mode would be an invisible shape — the exact class of bug this project keeps paying for.

### The generated name

When `mesh_path` is empty, generate a vanilla-shaped `<20hex>\<20hex>` from a digest of:

**the .blend file's path + the object's raw Blender name.**

- The **.blend path** makes the name unique across mods, so two projects that both contain a
  `Head` never collide in the shared `geometries\` tree. It's preferred over the nif output path
  because it's stable when you export the same shape to a test folder and then to the real mod.
  When the .blend is unsaved and has no path, fall back to the export nif's path.
- The **raw** object name, `.NNN` suffix and all, is what makes this fix the problem it's here to
  fix: `Head`, `Head.001` and `Head.002` digest differently, so freshly split objects get distinct
  `.mesh` files *before* they're renamed. (Contrast `sanitize_mesh_component`, which strips `.NNN`
  and would map all three to one name.)
- Split one digest into two 20-hex components. 41 characters, one level, indistinguishable in
  shape from a shipped asset, and still under 46 with `_fb`.

**Moving or renaming the .blend changes the digest only for shapes generated afterwards.** The
generated name is written back into `mesh_path` on first export and pinned from then on, so it is
a first-export-only input, not an ongoing dependency.

### Where `<shape>` comes from

The **Blender mesh object's name**, sanitized by the existing `sanitize_mesh_component`. Not the
BSGeometry block name — the object name is what keeps the correspondence one-to-one when a single
object is split into several, and it's what the author actually controls.

It also disambiguates LOD children for free: an imported LOD child is named `MaleHead:0:LOD0`,
which sanitizes to `MaleHead_0_LOD0`. No separate LOD-slot suffix is needed.

### Import is unchanged

Import continues to record the source `meshName` verbatim — directory and filename — so a
re-export writes back to the same `.mesh` and the byte-exact in-place replacement of a vanilla
asset still works. Existing `.blend` files need no migration: their stored values contain a
separator, so they read as fully-specified and behave exactly as before.

### Facebones

The `_faceBones` companion still appends `_fb` after the name is settled, in both the derived and
the explicit case. Without it the pair shares one `.mesh` and the facebones skin overwrites the
base geometry — the trap `TEST_SF_FACEBONES_EXPORT` exists to catch.

---

## Part 2 — the `morph.dat` paths

### Why the same rule doesn't transfer

For a `.mesh` the shape name is the filename, so dropping the last segment is enough. For a morph
the filename is always `morph.dat` and the shape name is an **interior** segment:

```
meshes/morphs/FSF/male/chargen/LykaiosMaleHead/morph.dat
                               ^^^^^^^^^^^^^^^ the shape
```

There is nothing to drop. And the segment's *position* isn't fixed either — vanilla and Felid put
the chargen/performance segment **before** the part:

| | layout |
|---|---|
| vanilla | `meshes\morphs\Human\Male\Chargen\Head\morph.dat` |
| Felid | `meshes/morphs/felid/male/chargen/felideyebrows_default/morph.dat` |
| ours, older | `meshes/morphs/FSF/Lykaios/LykaiosMaleHead/chargen/morph.dat` |

All are legal: the engine takes the directory from the `MRPH` record's `TCMP`/`TMPP`, not by
convention. Bad Dog is moving FSF onto the vanilla ordering, but a derivation rule that assembles
a fixed tail could only ever express one of them.

### The rule: a `{shape}` token

`chargen_path` / `performance_path` may contain the literal token `{shape}`, replaced on export
with the Blender mesh object's name (same sanitization as the `.mesh` filename).

```
meshes/morphs/FSF/male/chargen/{shape}/morph.dat        <- vanilla ordering, what we're moving to
meshes/morphs/FSF/Lykaios/{shape}/chargen/morph.dat     <- part-before-tree, still supported
```

A path with no token is used verbatim, exactly as today. Rejected alternative: storing a root
directory and appending a fixed `<shape>/<tree>/morph.dat` tail — barely less code, and it
forecloses the vanilla ordering.

`{shape}` is **not** accepted in `mesh_path`. The directory-or-file rule already covers that case,
and two mechanisms for one idea is worse than one each.

### Interaction with the existing machinery

- `swap_morph_tree` still fills an unset sibling, so setting `chargen_path` alone yields both
  files. Substitute the token **before** the swap so both paths carry the same shape name.
- `morph_relpath` write-back ([export_sfmorph.py:187](../io_scene_nifly/sfmorph/export_sfmorph.py#L187))
  records a *resolved* path back onto the group where the user left one empty. It must **not**
  stomp a token the user typed — same rule the code already applies to explicit paths.

---

## Duplicate output paths: warn and auto-suffix

The generated `.mesh` name can no longer collide (distinct objects digest differently), but two
shapes can still land on one output path when the author typed the same explicit path twice, or
when two objects sanitize to the same `<shape>`.

**Warn, don't fail. Auto-suffix `_1`, `_2`, … to disambiguate**, naming both objects and the path
chosen in the warning.

- The **first** shape the export reaches keeps the unsuffixed path. That's Blender's own object
  order (`bpy.context.selected_objects`, walked in `add_object`), not a name sort — deterministic
  for an unchanged scene, which is what matters, and it avoids a pre-pass over every shape purely
  to order the warning.
- For a `.mesh`, the suffix goes on the **filename**: `FSF\Head` → `FSF\Head_1`.
- For a `morph.dat`, the filename is fixed, so the suffix goes on its **immediate parent
  directory**: `.../chargen/Head/morph.dat` → `.../chargen/Head_1/morph.dat`.
- Suffixes are **not** written back to the property — they're recomputed deterministically each
  export, and writing them back would freeze a name the author is being told to fix.

---

## Shared implementation notes

- Both "is this a file or a stem" decisions live in one testable place per format, callable
  without Blender: the `.mesh` split in `nif/sf_geometry.py`, the token substitution in
  `pyn/sf_morph.py` beside `morph_relpath` / `swap_morph_tree`, so the pyn-layer suite covers
  them.
- Accept `/` and `\` interchangeably on input, as the surrounding code already does.
- **Enforce the 46-character `meshName` cap on export**, with a message naming the shape and the
  over-long path. Never truncate — a truncated path is an invisible shape. This is owed
  independently of this plan.
- The two `~46 chars` comments in [sf_geometry.py](../io_scene_nifly/nif/sf_geometry.py#L162)
  state the cap without its source; point them at the Bethesda Library page.
- Property docstrings in [pyn_props.py:669-698](../io_scene_nifly/nif/pyn_props.py#L669-L698)
  state the verbatim-only contract for both groups and need rewriting.

## Tests

Lowest level first, per the project's test-first rule.

| level | test |
|---|---|
| pyn | `.mesh` path split: the four rows of the Part 1 table |
| pyn | a second separator in `mesh_path` is rejected |
| pyn | generated name is `<20hex>\<20hex>`, 41 chars, and is stable for the same (blend, object) |
| pyn | `Head` / `Head.001` / `Head.002` generate three different names |
| pyn | `{shape}` substitution, incl. no-token passthrough and both layout orderings |
| pyn | token substitution happens before `swap_morph_tree`, so both siblings agree |
| pyn | 46-character cap check fires on an over-long name |
| Blender | directory-only `mesh_path` derives the filename from the object name |
| Blender | two objects resolving to one `.mesh` warn and auto-suffix, both files written |
| Blender | two objects resolving to one `morph.dat` warn and auto-suffix on the parent dir |
| Blender | split-into-three round trip: one object → three, one export, three distinct `.mesh` files and three distinct `morph.dat` pairs |
| Blender | regression: imported vanilla path still round-trips verbatim to the same `.mesh` |

Existing tests that assert the old contract and will move: the verbatim-path assertion in
[test_starfield.py:78-83](../tests/blender/test_starfield.py#L78-L83), `TEST_SF_MESH_NAME_SANITIZE`,
and `TEST_SF_FACEBONES_EXPORT`'s distinct-`.mesh` check (which then passes for a better reason).

## Backwards compatibility

Nothing to migrate. Old `.blend` files store fully-specified paths with a separator and no token,
so both rules read them as verbatim and behave as they do today. Per project policy, compatibility
is only owed back to the last released version (28.2.0).

## Resolved

1. **Duplicate outputs** — warning plus auto-suffix, not a hard failure. *(Bad Dog)*
2. **`{shape}` in `mesh_path`** — no; the directory-or-file rule covers it. *(Bad Dog)*
3. **Anything else keyed off the object name that a rename would disturb** — none known. *(Bad Dog)*
