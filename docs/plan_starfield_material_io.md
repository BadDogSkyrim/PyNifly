# Plan: Starfield Material I/O

Status: **draft, revision 3.** Nothing here is built except where marked *(done)*.

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

**Modelled (16 of the 31):** the layer/blender graph and its IDs, `MRTextureFile`, `UVStreamID` +
`Scale`, `BlendModeComponent`, `ColorChannelTypeComponent`,
`MaterialOverrideColorTypeComponent`, `ShaderModelComponent`, `AlphaSettingsComponent`,
`TranslucencySettingsComponent`, `LayeredEmissivityComponent`, `HairSettingsComponent`, `CTName`.

**Three live defects** in code sitting in the working tree. ("Source document" = the original
`.mat`, either the file being overwritten or the one the shader names.)

1. **Layers added in Blender are silently dropped on export.** The exporter looks up `LayerID[i]`
   in the source document and skips any layer the source lacks. Verified: 6-layer material + a
   7th added in Blender exports with 6.
2. **`LODMaterialID` references are corrupted.** The re-namespacing pass rewrites every
   `Data.ID`, but an LOD reference points at a *different material in the database* — not at an
   object in this file. Rewriting it points it at nothing. Rule to apply: **only re-namespace IDs
   that name an object present in the document.**
3. **Silent degradation.** With no source document, export rebuilds from what PyNifly models and
   says nothing about what it dropped.

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
  materials by bare ID with the target absent from the file. Those IDs must be preserved
  verbatim, never re-namespaced (defect 2).
- **Identity.** A stable handle for matching a node back to what it was imported as, independent
  of position in the tree.

IDs of objects we *do* write are still regenerated per target filename, so a derived material
can't collide with the vanilla one it came from.

## Phases

Build the representation first, then the export that uses it.

### Phase 1 — import what we can represent (classes A + B)

Model the 13 remaining component families into the shader graph and typed property groups:

- `TextureReplacement` → class A. A flat colour filling a texture slot; belongs beside the
  texture nodes. 20 of 36 human materials.
- `ParamBool`, `MaterialParamFloat` → class B, on the node that owns them (root → material,
  blender → `SF Blend`, texture set/material → `SF Layer`), keyed by index. The format docs call
  these "knobs defined by the shader model", so expose indexed values; don't invent names for
  indices whose meaning we don't know.
- Face/skin set: finish `Translucency` and `Hair`; add `EyeSettings`, `MouthSettings`,
  `DetailBlenderSettings`. Bodypart-heavy and directly relevant to the head work.
- `ShaderRouteComponent`, `EffectSettingsComponent`, `Color` → class B on the owning element.
- `LevelOfDetailSettings`, `MipBiasSetting`, `TextureResolutionSetting` → class B, panel only.
  Streaming plumbing, not appearance. *(Agreed: panel.)*
- `LODMaterialID` → material-level property, preserved verbatim. Whether PyNifly ever
  imports/exports the LOD material itself is **TBD**.

Acceptance: for a vanilla skin material, every component above is visible and editable.

### Phase 2 — capture what we can't (class C)

- On import, store unmodelled components as residue on the Blender node they came from.
- No panel summary — it would go stale and mislead; anyone who cares can read the JSON.
- Acceptance: across all 36 human materials, model + residue accounts for **every** component,
  with nothing unaccounted for.

### Phase 3 — export

- Build the document from the node tree: emit each node from its modelled values plus its
  residue, in tree order.
- A layer with no residue is built from scratch — this is the fix for defect 1, and it falls out
  of the design rather than being a special case.
- Re-namespace only IDs naming objects present in the document (defect 2).
- Warn on degradation (defect 3).
- Retire the on-disk source-document lookup: it goes stale, and the node tree replaces it.
- Acceptance: import → export → component census identical across all 36 human materials **with
  no source file on disk**; plus reorder-a-layer and add-a-layer round trips; plus at least one
  in-game/CK check.

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
