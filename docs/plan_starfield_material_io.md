# Plan: Starfield Material I/O

Status: **revision 5. Phases 1–3 are built.** Phase 4 (the non-human tail and the docs) is not.

## Goal

Import a Starfield `.mat`, edit it in Blender, and export a material as capable as the one that
came in — with nothing silently lost, whether or not PyNifly understands every part of it.

Three creation paths, all of which have to work:

1. **Round trip** — import a material, change something, export over it.
2. **Derive** — import a vanilla NIF and its material, edit the mesh and shader, export to a new
   mod under a new material name. *This is the normal modding workflow.* There is no existing
   file at the destination, so everything needed to write the material has to be in the `.blend`.
3. **From scratch** — author a material in Blender with no import behind it. Must be possible;
   such a material can only contain what PyNifly models, which is the argument for modelling
   components rather than only preserving them.

Non-goal for now: **material animation** (`BSBind::ControllerComponent` /
`BSBind::DirectoryComponent`). Preserve the components; don't interpret them.

## Scope: human bodyparts

| scope | materials | component types |
|---|---|---|
| all bodyparts + worn | 1007 | 44 |
| all bodyparts | 440 | 42 |
| **human** (`meshes/actors/human`) | **36** | **31** |
| human family (`+ human_crowd, child, mannequin, corpse`) | 69 | **31** |

Restricting to human is what makes this tractable — bodyparts generally does not (42 of 44 types
appear on some bodypart). The family boundary doesn't matter: adding `human_crowd`, `child`,
`mannequin` and `corpse` doubles the materials and adds **zero** new component types, so we don't
have to decide whether a mannequin is a human.

**Of the 31 types human bodyparts use, PyNifly models 16. Excluding the two `BSBind::*`
animation components, that leaves 13 component families for complete coverage.**

Dropped by the human scope (11): `DecalSettings`, `LayeredEdgeFalloff`, `UVStreamParamBool`,
`EmissiveSettings`, `TextureAddressMode`, `Collision`, `Opacity`, `Offset`, `Distortion`,
`TextureFile`, `FlowSettings`.

Note the LOD/streaming group is an *armor* concern, not a human-bodypart one — `MipBiasSetting`
2 of 36 human materials vs 541 worn, `TextureResolutionSetting` 1 vs 532, `LevelOfDetailSettings`
3 vs 528. What's actually heavy on human bodyparts is `ParamBool` (22), `TextureReplacement`
(20), `MaterialParamFloat` (12), and the face/skin set: `Translucency` (15), `Hair` (12, and zero
outside human), `Eye` (6), `Mouth` (2), `DetailBlender` (1).

13 is small enough to model properly. Preservation is then a safety net for the unexpected, not
the mechanism the design rests on.

Full data: `census_split.json`, `census_human.json` (session scratch).

## Current state

**Modelled (29 of the 31, after Phase 1):** the layer/blender graph and its IDs, `MRTextureFile`,
`UVStreamID` + `Scale`, `BlendModeComponent`, `ColorChannelTypeComponent`,
`MaterialOverrideColorTypeComponent`, `ShaderModelComponent`, `AlphaSettingsComponent`,
`TranslucencySettingsComponent`, `LayeredEmissivityComponent`, `HairSettingsComponent`, `CTName`,
plus the Phase 1 thirteen: `ParamBool`, `MaterialParamFloat`, `TextureReplacement`, `Color`,
`EyeSettingsComponent`, `MouthSettingsComponent`, `ShaderRouteComponent`,
`EffectSettingsComponent`, `DetailBlenderSettingsComponent`, `LevelOfDetailSettings`,
`LODMaterialID`, `MipBiasSetting`, `TextureResolutionSetting`.

**Not modelled (2):** `BSBind::ControllerComponent` and `BSBind::DirectoryComponent` — material
animation, preserved but not interpreted (Phase 2 residue).

**Defects.** ("Source document" = the original `.mat`, either the file being overwritten or the
one the shader names.)

1. **Layers added in Blender are silently dropped on export.** The exporter looks up `LayerID[i]`
   in the source document and skips any layer the source lacks. Verified: 6-layer material + a
   7th added in Blender exports with 6. *Still open — Phase 3.*
2. ~~**`LODMaterialID` references are corrupted.**~~ **Misdiagnosed; the mechanism was different.**
   `_renamespace` builds its remap from the IDs of objects *in the document* and only rewrites a
   reference it finds there, so it already implemented the rule this plan prescribed. Measured on
   `Generic_FacialJewelry`: patching re-namespaces the LOD reference *and* the LOD subtree the cdb
   supplies with it, so the reference still resolves; writing from scratch (where the LOD material
   is not among our objects) leaves the vanilla ID verbatim, pointing at vanilla's LOD material in
   the database. Both are correct. The real loss was that `LODMaterialID` **wasn't modelled at
   all**, so a from-scratch write dropped it. *Fixed in Phase 1.*
3. **Silent degradation.** With no source document, export rebuilds from what PyNifly models and
   says nothing about what it dropped. *Still open — Phase 3.*
4. **Patching REPLACED a component's `Data`** instead of merging into it, so every field of a
   component that PyNifly didn't model was destroyed on write — `LayeredEmissivityComponent` alone
   has 17 fields to our 4. Found by measurement, not by inspection: **969 authored field values
   were being dropped across the 36 vanilla human materials**, plus 115 components invented
   (identity UV `Scale`/`Offset`) and 105 fields added. This was pre-existing and silent.
   *Fixed in Phase 1; the corpus now round-trips with zero fields added, dropped or altered.*

## Architecture

Three representation classes:

| Class | For | Where it lives |
|---|---|---|
| **A. Shader graph** | things that change the look and that people edit | nodes |
| **B. Typed properties** | scalars and flags | property groups on the material / on nodes |
| **C. Per-node residue** | components we don't model | a JSON string **on the Blender node the component came from** |

### The shader node tree is the material

Class C is Bad Dog's design, and it replaces the "captured document" idea I had in revision 2.
The objection that killed the old approach: a stored copy of the document goes stale the moment
the user restructures the tree. Swap two layers in the node graph and a separately-stored
document still describes the old order, silently. **Users will expect the node tree to be
authoritative, and it should be.**

Storing residue on the node it came from makes restructuring work for free: reorder layers and
the residue moves with them; delete a layer and its residue goes with it; add one and there's no
residue, so it's built fresh. There is no second copy of the structure to fall out of sync,
because the structure *is* the node tree.

### Every material object maps to a Blender element

This is what makes per-node residue viable, and it's verified rather than assumed. Across all 36
human materials, **every object is reachable from the root by the six known reference types —
zero unreachable objects.** So there is always a node to hang residue on:

| `.mat` object | Blender element | components seen on it (human materials) |
|---|---|---|
| root LayeredMaterial | the **material** | `ShaderModel`, `LayeredEmissivity`, `ParamBool`×17, `Translucency`, `AlphaSettings`, `Hair`, `LODMaterialID`, `Eye`, `BSBind`×2, `ShaderRoute`, `EffectSettings`, `LevelOfDetail`, `Mouth`, `DetailBlender` |
| Layer | **`SF Layer`** node | refs only — nothing unmodelled |
| Material (of a layer) | **`SF Layer`** node | `MaterialOverrideColorType`, `Color`, `ParamBool` |
| TextureSet | **`SF Layer`** node | `MRTextureFile`, `TextureReplacement`×57, `MaterialParamFloat`, `MipBias`, `TextureResolution` |
| UVStream | **Mapping** node | `Scale` |
| Blender | **`SF Blend`** node | **`ParamBool`×74**, `UVStreamID`, `BlendMode`, `MRTextureFile`, `MaterialParamFloat`, `ColorChannel` |
| LOD material | material-level property | a bare `res:` reference into the database |

`ParamBool` on blenders (74 occurrences) is exactly the case Bad Dog raised: it becomes a
property on the `SF Blend` group node and travels with it.

Layer, Material and TextureSet all collapse onto one `SF Layer` node, so residue stored there is
keyed by which of the three it came from — `{"material": [...], "textureset": [...]}`.

### Carrying `res:` IDs

Each node also keeps the `res:` ID it was imported with (`pyn_sf_id`). Two uses:

- **Cross-material references.** `LODMaterialID` names a whole separate material living in the
  database, not an object in the file — Felid's shipped loose `.mat`s reference vanilla LOD
  materials by bare ID with the target absent from the file. Those IDs are preserved verbatim
  because `_renamespace` only rewrites references whose target is an object in the document; see
  defect 2, which turned out to be already handled.
- **Identity.** A stable handle for matching a node back to what it was imported as, independent
  of position in the tree.

IDs of objects we *do* write are still regenerated per target filename, so a derived material
can't collide with the vanilla one it came from.

## Phases

Build the representation first, then the export that uses it.

### Phase 1 — import what we can represent (classes A + B) — **done**

All 13 families are modelled, in `sf_materials._COMPONENT_SPECS` (a declarative table that
parse/write/patch share, so the 11 Phase-4 families are mostly a matter of describing them) and on
the Blender side in `shader_io._SF_COMPONENTS` plus per-node properties.

Two things measurement changed:

- **Field lists are the UNION of what vanilla carries, not what we interpret.** The cdb stores only
  fields that differ from the parent template, so a component appears with varying field sets
  (`EffectSettingsComponent` ships as 4 fields on four materials and 6 on one). Because patching
  writes a component's Data, a short field list silently drops the rest — defect 4 above.
- **Write only what says something.** A field is written when the source already carries it *and
  the value changed*, or when the source omits it *and the value differs from the field's default*.
  The first keeps a patched material byte-stable (re-encoding an untouched `6500` as `6500.0` is
  the same number and a gratuitous diff); the second keeps an edit alive when the user switches on
  a flag the source never mentioned.

Verified against the corpus (`fidelity.py` in the session scratch): all 36 vanilla human materials
patch back with **0 components and 0 fields added, dropped or altered**. Tests:
`TEST_SF_MAT_COMPONENTS` (pyn layer) and `TEST_SF_MAT_COMPONENT_ROUNDTRIP` (through the real node
build and back), over six vanilla fixtures chosen by set cover so they exercise all 13 families.

What was built:

- `TextureReplacement` → class A, an RGB node feeding that slot's `SF Layer` input. Measurement
  settled the semantics: a replacement never coexists with a texture in the same slot (0 of 11
  across the fixtures), so it *stands in for* a missing texture rather than tinting one. 5 of the
  11 carry no colour of their own — the colour comes from the parent template, which we can't
  resolve, so those stay a flag rather than an RGB node with an invented colour.
- `ParamBool`, `MaterialParamFloat` → class B, one scalar custom property per index on the node
  that owns them (root → the material, blender → `SF Blend`, layer material/texture set →
  `SF Layer`). Indexed, not named: the `.mat` gives them an `Index` and nothing else.
- Face/skin set: `EyeSettings`, `MouthSettings`, `DetailBlenderSettings` added alongside the
  existing `Translucency` and `Hair`, each as its own settings group node.
- `ShaderRouteComponent`, `EffectSettingsComponent` → their own group nodes; `Color` → a property
  on the owning `SF Layer` node.
- `LevelOfDetailSettings` → a group node; `MipBiasSetting`, `TextureResolutionSetting` →
  properties on the `SF Layer` node. Streaming plumbing, not appearance.
- `LODMaterialID` → a material-level property per LOD level, carried as an opaque `res:` id.
  Whether PyNifly ever imports/exports the LOD material itself is still **TBD**.

The six new settings components are value-holders with no outputs: they configure engine behaviour
the Blender preview doesn't reproduce, so the node carries the values honestly rather than
pretending to render them.

### Phase 2 — capture what we can't (class C) — **done**

Each Blender node carries the `.mat` objects it stands for, as JSON: `pyn_sf_nodes` on an `SF
Layer` node (which stands for up to four — layer, material, texture set, uv stream), `pyn_sf_node`
on an `SF Blend` node and on the material.

**Wider than "residue" as planned.** A node carries not just the components PyNifly doesn't model,
but the full `Data` of the ones it does, plus the object's `res:` id, `Parent` and `CTName`. Two
reasons measurement forced that:

- **Unmodelled FIELDS matter as much as unmodelled components.** `LayeredEmissivityComponent` has
  17 fields and PyNifly models 4. Residue at component granularity would have kept nothing, because
  the component itself *is* modelled — and losing its other 13 fields was defect 4.
- **Carrying `Parent` sidesteps open question 1.** A rebuilt node keeps whatever parenting scheme
  its source used, so we don't have to decide which of the two observed schemes is correct in
  order to write a correct file.

The structural references (`LayerID`/`BlenderID`/`MaterialID`/`TextureSetID`/`UVStreamID`) are the
one thing a node does *not* carry — they define the graph's shape and are regenerated, which is
what lets layers be added and reordered. An *empty* such reference is kept, though: vanilla
blenders declare an empty `UVStreamID`, and a declaration pointing at nothing is not a reference.

No panel summary — it would go stale and mislead.

### Phase 3 — export — **done**

`build_mat_doc` builds the document from the material itself, consulting nothing on disk. Each node
is emitted from its carried components with the modelled values merged over them.

- **Defect 1 fixed.** A layer added in Blender has no carried state, so it gets a fresh id and the
  Root template for its kind, and is emitted like any other. Nothing is looked up in a source
  document, so there is nothing to fail to find.
- **Defect 3 dissolved rather than warned about.** With the state on the nodes there is no
  degradation to report. The one real hazard left was different: a material imported from a `.mat`
  PyNifly *couldn't find* has no layers, and exporting it wrote a stub over a good file. Export now
  refuses that and says why.
- The on-disk template lookup is kept only for a material whose nodes carry nothing — one imported
  before PyNifly recorded any of this. It is no longer the mechanism.

Two things measurement changed here too:

- **Blenders can own a UV stream.** `male_default` gives each of its four one. Its tiling has no
  place in the Blender node tree, so the stream is carried whole and written back untouched rather
  than modelled or dropped.
- **`_rename_ctnames` guessed the material's name as the shortest `CTName` in the document.** That
  is wrong whenever a node keeps a name inherited from its shader-model template:
  `Eye1Layer_Layer3` is shorter than `bloodshot_left_eye`, so that layer was taken to be the
  material and renamed on top of it. The root's name is the answer.

Acceptance met: all 36 vanilla human materials rebuilt **from their parsed dicts alone, with no
file on disk**, come back with **0 fields added, dropped or altered**. The only objects not
reproduced are the LOD-material subtrees on the 3 materials that have one — deliberate, since we
reference vanilla's LOD material by id rather than copying it into our file. Add-a-layer is covered
by `TEST_SF_MAT_BUILD_FROM_TREE`; the same rebuild through the real Blender node tree is covered by
`TEST_SF_MAT_COMPONENT_ROUNDTRIP`.

**Validated in the CK and in game** (Bad Dog, 2026-07-29): the vanilla male head and body imported
to Blender and exported back both render correctly. That is the check this plan's first risk says
a census diff can never substitute for.

### Phase 4 — the tail and the docs

The 11 non-human component families as they come up; `Channel` and `FlipbookComponent` are
worn-only and can wait. Update [starfield_materials.md](starfield_materials.md), including the
correction below. Push format facts to the Bethesda Library — the `MaterialID` CRC, and that
`LODMaterialID` is a cross-material database reference.

## A correction owed to the docs

[starfield_materials.md](starfield_materials.md) currently says every node needs a `Parent` into
one of the six `Materials\Layered\Root\*.mat` templates. **Felid's shipped, working materials
don't do that** — their root is parented to a *ShaderModel* template
(`Data\MATERIALS\Layered\ShaderModels\Character2Layer.mat`) and their other nodes are parented to
other `res:` IDs, including IDs not present in the file:

```
Parent values in felid naked_f_body_swimsuit.mat:
  Data\MATERIALS\Layered\ShaderModels\Character2Layer.mat   (root, no ID)
  Data\MATERIALS\Layered\ShaderModels\1LayerStandard.mat
  res:73A324D1:0005E4D1:A0676790   ... 14 nodes parented to other res: IDs
```

So there is more than one valid parenting scheme, and the "must be a Root template" rule is too
strong. The magenta diagnosis from 2026-07-23 may have identified *a* cause without identifying
*the* rule. Worth resolving before we design against it — see open questions.

## Open questions

1. **What actually makes a `.mat` valid?** Two schemes observed (Root-template parenting, and
   ShaderModel + `res:` chaining). Which does PyNifly emit, and is one more robust? This is a
   format question for the Bethesda Library, and it gates confidence in export.
2. **`LODMaterialID`** — preserve the reference (settled); import/export the LOD material itself
   is TBD.
3. **fo76utils** — documentation only; PyNifly reads the `.cdb` directly now, so the reference
   may just be removed.

## Risks

- **Round-trip fidelity is not game-validity.** A census diff proves nothing renders. Every phase
  needs an in-game or CK check. This has bitten repeatedly on the Lykaios head: several
  "verified" fixes changed nothing observable.
- **Unknown parenting rules** (open question 1) could mean a byte-perfect round trip still fails
  in game for a *derived* material, where IDs and parents change.
- **The census covers human bodyparts.** Worn items add 11 component families; weapons, ships and
  set dressing are each expected to bring their own, and are out of scope here.
