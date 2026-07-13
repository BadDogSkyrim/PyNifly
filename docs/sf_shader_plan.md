# Starfield material → Blender shader: project plan

**Status:** draft for review/edit · **Owner:** Bad Dog · **Last updated:** 2026-07-11

A living plan for representing Starfield's layered PBR materials as Blender shader graphs that
we can both *preview* and *write back out* to `.mat`. Edit freely — the "Decided" section is the
current agreement; "Open" is what we're still kicking around.

---

## Decided (locked-in choices)

1. **Build for export, not preview-only.** The graph is editable *source of truth* we can walk
   back into a `.mat`. Everything below is constrained by "must be recoverable." We'll still get a
   good preview along the way, but export is the requirement, not a nice-to-have.
2. **Flat nodes first; collapse into node groups later.** Prototype each feature with explicit,
   visible flat nodes — easier to see and manipulate while we're figuring out the shape. Once a
   pattern is stable, refactor it into a reusable node group (`SF Layer` / `SF Blend` / `SF
   Material`). The group library is still the end state; flat is the path to it.
3. **Bring layering in early.** Don't defer multi-layer blending to the end — stand up a real
   2-layer material early so we build experience with blend modes/masks while everything is still
   simple and flat.
4. **Parameters live in one contained, visible node.** No scattered single-value nodes and no
   hidden-only custom props. All scalar/color params for a material go on a single **"SF
   Parameters" node** with one input per value — visible on the graph, editable, but contained.
   (Implementation note below; this node doubles as the export param source.)

---

## Locked P0 spec — the "SF Parameters" node (2026-07-12)

A value-holder **node group** named `SF Parameters`. Its **input sockets are the param store** —
each shows an editable field on the node when unconnected (decision 4). Driving params also get an
**output socket** (internal pass-through) wired into the Principled; held params have no output and
are read straight off the input on export. Generated **procedurally in code** during flat-first;
authored into `shaders.blend` @ Blender 4.0 at P3 (collapse-to-groups).

**Bools use real `NodeSocketBool`** (a checkbox — rejects `5` in a boolean field, signalling intent
to the modder). `Alpha Mode` = Int socket (0 none/1 test/2 blend). **`Shader Model` is a STRING, and
Blender shader node trees have NO string socket** (5.1 socket types: Float/Int/Bool/Vector/Color/
Menu/Shader/Bundle/Closure) — so it's held as a **custom property on the same params node** (still one
contained node, round-trippable by name via `node["Shader Model"]`). Magic-string enum values,
documented, remain a later option.

| Socket (round-trip key) | Type | Role | `.mat` source | Default | Drives |
|---|---|---|---|---|---|
| `Translucency Enable` | Bool | stored | `TranslucencySettingsComponent.Enabled` | off | (with Use SSS) Subsurface |
| `Use SSS` | Bool | stored | `TranslucencySettings.UseSSS` | off | (with above) Subsurface Weight |
| `Spec Lobe 0 Roughness` | Float | held | `SpecLobe0RoughnessScale` | 1.0 | — |
| `Spec Lobe 1 Roughness` | Float | held | `SpecLobe1RoughnessScale` | 1.0 | — |
| `Emissive Enable` | Bool | driving | `LayeredEmissivityComponent.Enabled` | off | Emission gate |
| `Emissive Tint` | Color RGBA | driving | `emissive.tint` (XMFLOAT4) | (1,1,1,1) | Emission Color × |
| `Has Opacity` | Bool | held | `AlphaSettingsComponent.HasOpacity` | off | gates Opacity→Alpha wiring |
| `Alpha Test Threshold` | Float | held | `AlphaSettingsComponent.AlphaTestThreshold` | 0.5 | material clip threshold |
| `Shader Model` | String (custom prop) | held (identity) | `ShaderModelComponent.FileName` | "" | — (export template) |

**Translucency is two hierarchical flags** (outer component-enable + inner SSS-mode-select). Both are
stored independently — do NOT collapse to one bool, or export can't reconstruct the original two.
Subsurface Weight is driven by `AND(Translucency Enable, Use SSS)` inside the group.

**Round-trip contract:** identify the node by its `node_tree` datablock name starting `"SF Parameters"`
(stable vs. instance-label rename / localization — not the instance label). Read a param via
`node.inputs["<socket name>"].default_value`; socket *names* are the stable keys (we author them;
Blender doesn't localize custom socket names). Import sets those defaults; export walks them back.

---

## Goal & scope

Author and round-trip Starfield materials in Blender: import a `.mat` (loose or from
`materialsbeta.cdb`) into a faithful, editable node graph; edit it; export it back to a `.mat`.
Priority is the furry-race asset path — **skin, faces, fur** — which in practice means
**1–2 layers + subsurface (+ hair)**. Broad environment/armor materials (many layers, decals,
terrain) are breadth we add after the core round-trip works.

---

## The SF material model (what we're mirroring)

```
LayeredMaterial
 ├─ Layer[0..N]      each: TextureSet (per-slot maps) + UVStream (tiling/offset) + Material params
 ├─ Blender[0..N-1]  how layer k composites over k-1: mask texture + blend mode + params
 └─ settings components on the composited surface:
      AlphaSettings         opacity mode (none/test/blend) + threshold
      EmissiveSettings      emissive color/scale, adaptive/luminous emittance
      TranslucencySettings  subsurface: transmittance, thickness, SSS color   ← skin/fur
      HairSettings          anisotropic roughness, backscatter tint           ← fur
      DecalSettings         decal projection/blend
      EffectSettings        transparency/refraction/blending (glass, FX)
      DetailBlender / GlobalLayer / Flipbook (animated) / Terrain (landscape)
```

Texture slots we index today: 0 Albedo · 1 Normal (BC5 XY, Z reconstructed) · 2 Opacity ·
3 Roughness · 4 Metal · 5 AO · 6 Height · 7 Emissive · 8 Transmissive (SSS mask).
Confirmed cdb component types: `LayerID, MaterialID, TextureSetID, UVStreamID, BlenderID,
LayeredMaterialID, BlendModeComponent, MRTextureFile`.

**Where we are today:** `import_sf_material` builds a native Principled BSDF, **base layer only** —
albedo (×AO) → Base Color, roughness → Roughness, metal → Metallic, emissive → Emission, BC5
normal reconstruct → Normal. Raw slot paths + the `.mat` path are stashed. This is the floor.

---

## Architecture

**End state:** a small node-group library mirroring the `.mat` graph, feeding one native
Principled BSDF, so the same graph reads on import and writes on export. 

[Assuming this library lives in a blender file, it has to be blender 4.0 so people using
older versions of blender can use it. We already ship a "shaders" blend file - unless
there's a good reason, our new group nodes should live here.]

| Group (eventual) | Mirrors | Contract |
|---|---|---|
| `SF Layer` | one Layer (TextureSet + UVStream + params) | UV → a *PBR bundle* (base color, roughness, metallic, normal, AO, opacity, emissive, SSS-mask) |
| `SF Blend` | one Blender | two PBR bundles + mask/mode → one bundle |
| `SF Material` | settings components | bundle + params → drives Principled (+ side nodes where it can't) |

[I don't know if we'll want one layer node and one blend node or if we'll, for example,
want a different blend node for each type of blend. We can decide when we see the details.]

**Path there (per decision 2):** build the above *inline as flat nodes* first. A single layer is a
flat chain of texture nodes → math/mix nodes → the surface. A blend is flat Mix nodes driven by a
mask. Only once the topology is stable do we box each repeated pattern into the matching group. The
flat and grouped forms must produce the **same export read-back**, so the refactor is behavior-
preserving.

**PBR "bundle":** Blender has no struct socket, so a bundle is a fixed, named set of wires carried
between layers/blends (base color, roughness, metallic, normal, AO, opacity, emissive, SSS-mask).
Flat, that's a labeled cluster of noodles; grouped, it's the group's socket set.

### The "SF Parameters" node (decision 4)
All non-texture values (alpha threshold, emissive scale/color, SSS transmittance/thickness/color,
blend factors, UV tiling, hair params, …) live on **one** node per material, one input per value,
labeled. Likely implementation: a **node group used purely as a value holder** — its interface *is*
the parameter list, shown as editable fields on the node, outputs wired only where a value actually
drives something. This is the one place a node group appears during the "flat first" phase, because
it's a data container, not shader logic — and it's exactly what export reads (walk the group's
named inputs → `.mat` params). Alternative (a bespoke custom node) is possible but heavier; default
to the value-holder group unless it gets awkward.

### The export contract (because B is locked)
For the graph to be recoverable to a `.mat`, we hold these invariants from day one — flat or grouped:
- **Stable naming**: texture image nodes, the parameters node, and layer/blend clusters carry
  predictable names/labels so the exporter can find them. [Really stable *labels* - shader nodes carry both names and labels, and the labels could changed, e.g. for foreign languages.]
- **Params only in the SF Parameters node** (not baked into arbitrary Math node defaults).
- **Texture role is unambiguous**: each image node maps to a known slot (already stashed as
  `BSShaderTextureSet_<slot>`; keep that or move it onto the layer's identity).
- **Layer/blend topology is discoverable**: the order of layers and which mask drives which blend
  must be walkable. Grouping later makes this easier, not harder.
Every phase's exit criterion includes: *we can read this phase's params back out of the graph.*

---

## Feature → Blender mapping

| SF feature | Blender target | Status / notes |
|---|---|---|
| Albedo · Roughness · Metallic | Principled Base Color / Roughness / Metallic | done |
| AO | multiply into Base Color | done |
| Normal (BC5 XY) | Z-reconstruct → Normal Map | done; BC5_SNORM still needs a `.png` sidecar until Blender decodes it |
| Opacity + AlphaSettings | Principled Alpha + material blend mode + clip threshold | test→CLIP, blend→BLEND |
| EmissiveSettings | Emission Color + Strength | map luminous/adaptive emittance → strength |
| TranslucencySettings (SSS) | Principled **Subsurface** (weight/radius/color) + transmissive mask | **highest single value for skin/fur** |
| Multi-layer blend | flat Mix nodes → later `SF Blend` group, mask + mode | brought early per decision 3 |
| UVStream (tiling/offset) | Mapping node feeding the layer's texture nodes | part of `SF Layer` |
| HairSettings | Principled anisotropy + Sheen/Coat approximation, backscatter tint | fur; may need a sub-group |
| Height | bump/displacement (parallax not native → approximate) | low priority |
| Decal / Effect | separate handling (projection; transparent/refractive BSDF) | breadth |
| Flipbook (animated) | image sequence / driver | breadth |

---

## Phased plan

Flat-first, layering-early, export-proven-continuously. Each phase is "done" only when its params
round-trip out of the graph.

- **P0 — Flat single layer + settings + SSS. ✅ DONE (2026-07-12).** Principled + flat nodes for
  Opacity/AlphaSettings, EmissiveSettings, **TranslucencySettings → Subsurface**, all routed through the
  **SF Parameters** node. Params round-trip off the node (export contract proven). Skin (SSS) validated in
  Blender + in-game; hair alpha (`HasOpacity` + `AlphaTestThreshold` → Opacity→Alpha + clip) validated on
  the real `Medium_Hair_Shared` cdb material. Tests: TEST_SF_MAT_PARSE, TEST_SF_PARAMS, TEST_SF_ALPHA.
  **HairSettings** parsed-but-inert, deferred to P4 (see below).
- **P1 — Flat two-layer material. ✅ DONE (2026-07-12).** Parser exposes `layers` (textures + UV
  tiling) + `blenders` (mode + mask). Node graph: base PBR + a later layer's detail normal composited
  via the procedural **SF Normal Blend (RNM)** group, tiled by the layer UV scale, masked by the
  blender (mask-weighted; `Skin` treated as a plain masked composite — by eye). Verified on vanilla
  skin (base UV 1:1, detail normal tiled 50×, Skin+mask); look/strength confirmed by Bad Dog. Tests:
  TEST_SF_MAT_PARSE (2-layer graph), TEST_SF_LAYERED (RNM wiring). **Note (Bad Dog):** SF's tiled
  detail-normal seams at UV islands and their neck mask flattens it — we reproduce it faithfully;
  it's now editable source for furry materials. `.mat` *writer* to recover it = P2.
- **P2 — `.mat` writer + round-trip. ✅ DONE (2026-07-13).** `sf_materials.write_mat(data)` emits a
  self-contained loose `.mat` (no template Parent; ShaderModelComponent names the model); IDs synthetic
  but internally consistent. Recovery = `shader_io.recover_sf_material` walking the graph: SF Parameters
  node (settings), SF Layer / SF Blend **marker** nodes (structure), stamped image nodes (`pyn_sf_path`
  etc. = exact .mat paths). Export writes it to the output tree (`materials/` sibling of `meshes/`),
  **opt-in** via `write_sf_materials` export flag (off by default — may overwrite a source .mat in place).
  Tests: TEST_SF_MAT_WRITE, TEST_SF_MAT_ROUNDTRIP, TEST_SF_EXPORT (.mat written+reparses). Caveats: texture
  *path* edits don't flow (stamped at import); MaterialOverrideColor + blender ParamBools/float not captured.
- **P3 — Real node groups (bundle-carrying). Bundle contract LOCKED (2026-07-13, Bad Dog).** The P2 markers
  are lightweight tags that don't carry content; replace with real groups that carry the **PBR bundle**:
  channels `Base Color · Roughness · Metallic · Normal · AO · Opacity · Emissive · SSS/Transmissive`
  (AO/Opacity/SSS each their own channel — stay close to the raw model; Height later). **Normal travels as
  reconstructed [0,1] RGB**, converted to a Normal Map only at `SF Material`. `SF Layer` = one group type
  (raw slot textures in → processed bundle out; UV tiling + BC5 reconstruct inside); every layer is an
  instance. `SF Blend` = **one group per blend TYPE** (name = mode: `SF Blend Skin`, `Lerp`, …), all sharing
  the interface `(bundle A, bundle B, Mask, + type-specific params) → bundle`; recovery reads mode from the
  group name. `SF Material` = bundle + SF Parameters → Principled. Chain reads `Layer→Blend→…→SF Material→
  Principled`; recovery walks the connected groups (topology gives order for free). Build order: SF Layer +
  SF Material + SF Blend Skin to reproduce today's skin through the new structure, prove the same round-trip,
  then add blend types/channels as real materials need them. Rework `recover_sf_material` onto the groups;
  keep write_mat + opt-in writer as-is.
- **P4 — Hair/fur.** `HairSettingsComponent` → Blender **Sheen** (+ anisotropy) sub-group; calibrate on a
  vanilla hair `.mat`. Real field set (from `Medium_Hair_Shared`, cdb class def): `Enabled`, `IsSpikyHair`,
  `SpecScale`, `SpecularTransmissionScale`, `DirectTransmissionScale`, `DiffuseTransmissionScale`,
  `Roughness`, `ContactShadowSoftening`, **`BackscatterStrength`**, **`BackscatterWrap`**, `VariationStrength`,
  `IndirectSpecularScale`, `IndirectSpecularTransmissionScale`, `IndirectSpecRoughness`, `EdgeMask*`,
  `MaxDepthOffset`, `DitherScale`, `DitherDistance*`, **`Tangent`** (vec3) + `TangentBend`,
  `DepthOffsetMaskVertexColorChannel`, `AOVertexColorChannel`. Likely map: `BackscatterStrength`→Sheen Weight,
  `Roughness`→Sheen Roughness, `Tangent`/`TangentBend`→Anisotropic direction. (Bad Dog: SSS is pointless for
  fur; sheen/backscatter is what sells it.)
- **P5 — Breadth.** More layers, decals, effect/transparency, height/parallax, flipbooks, terrain.

P0, P1, P4 are the furry-race critical path; P2/P3 keep us honest on export; P5 is coverage.

---

## Open questions / hard spots

1. **Blend-mode semantics** — SF blender modes/masks aren't 1:1 with Blender Mix modes; match
   visually against sampled vanilla multi-layer `.mat`s (P1).
2. **SSS parameter mapping** — SF transmittance/thickness → Principled Subsurface weight/radius/scale
   is an approximation; calibrate on a known skin material (P0).
3. **Hair/fur on cards** — Blender's Principled Hair BSDF is for strands, not sheet/card fur; likely
   stay on Principled + sheen/anisotropy. Needs an experiment (P4).
4. **cdb param coverage** — confirm we can pull *all* settings-component params (emissive scale, SSS
   values, alpha threshold, blend factors) from the cdb, not just texture paths.
5. **BC5_SNORM normals** — Blender can't decode; import prefers a `.png` sidecar. Inherited by every
   normal path; not a blocker for the shader design.
6. **Params node implementation** — value-holder node group (recommended) vs bespoke custom node.

---

## Decisions still needed

- **Blend modes**: match-by-eye against vanilla (pragmatic) vs dig out SF's exact blend math from
  the RE'd material runtime (accurate, slower)? — pick when we hit P1. [I'm happy to do it by eye, unless there's some blend mode we can't interpret at all.]
- **Params node**: confirm the value-holder-group implementation is acceptable, or you want a custom
  node with a nicer UI. {Good for now}
- **`.mat` writer scope**: loose `.mat` only, or also author-time cdb entries? (Loose is enough for
  modding; the game reads loose `.mat` fine.) [Loose is fine]
