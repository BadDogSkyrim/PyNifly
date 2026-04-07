# FO4 Vertex Colors, Vertex Alpha, and Shader Properties

Working notes on how Fallout 4 actually uses vertex colors, vertex alpha, and
alpha properties — collected as we fix import/export bugs in pynifly. Intended
to grow into user-facing documentation.

## TL;DR

In FO4, the `BSLightingShaderProperty` shader flags (`SLSF1_VERTEX_ALPHA`,
`SLSF2_VERTEX_COLORS`, etc.) are essentially **vestigial**. The engine ignores
them. What actually matters is:

1. **The shape's vertex format** — whether the BSTriShape's `vertexDesc`
   includes the per-vertex colors bit. If yes, the vertex stream carries an
   RGBA value per vertex. If no, there is no vertex color data at all.
2. **The BGSM material file** — fields like `alphblend0` (alpha blend) and
   `alphatest` (alpha test) decide whether the alpha channel is consumed at
   render time. The BGSM has **no** `vertexColors` / `vertexAlpha` toggle of
   its own.
3. **The texture's alpha channel** — combined multiplicatively with vertex
   alpha and the material's `Alpha` scalar.

The `NiAlphaProperty` block on the shape is **optional**. The engine will still
do alpha blending / testing based on the BGSM even if no `NiAlphaProperty`
exists in the nif.

### Vanilla examples

- `Meshes\Landscape\Trees\TreeElmFree01.nif` — `TreeElmFree01:0 - L1_TreeElmFree01:0`
  has 1522 verts; 490 of them have alpha > 0 and the rest are alpha = 0.
  **Note:** this is a tree BGSM, so the per-vertex alpha is wind-sway weight,
  not an opacity mask (see Rule 1 and the tree exception below).
- `Meshes\SetDressing\LightFixtures\WorkshopLightbulbHanging01.nif` —
  `Bulb001:3` has the vertex_colors bit set in its BSTriShape vertex format
  and 156 verts of `(1,1,1,1)` (uniformly opaque, white). Shows that the bit
  can be present even when the data is a no-op. `BulbGlow:2` in the same file
  does **not** have the bit set, so its `colors` array is empty (length 0,
  not None) — illustrates the difference between "no vertex colors at all"
  vs. "vertex colors present but trivial".

## Rule 1: Vertex colors + alpha import

For FO4 import:

- **Vertex colors** are imported into the `COLOR` attribute whenever
  `shape.properties.hasVertexColors` is true.
- **Vertex alpha** is imported into the `VERTEX_ALPHA` attribute whenever
  colors are imported. The per-vertex alpha data always round-trips, so
  export can write the same bytes back regardless of how the material uses
  them.
- Whether the `VERTEX_ALPHA` attribute is **wired into the shader as
  opacity** is a separate decision made by the shader importer: for tree
  materials (`BGSM.tree == True`) it is not wired, because those materials
  reuse vertex alpha as wind-sway weights rather than opacity.

Shader flags (`SLSF1_VERTEX_ALPHA`, `SLSF2_VERTEX_COLORS`, `GREYSCALE_COLOR`,
the effect-shader special case, etc.) should not be consulted in the FO4 path.

### Always preserve, conditionally wire

Two separate concerns must not be conflated:

1. **Preserving the data on round-trip.** If the source nif has per-vertex
   color or alpha bytes, the importer must store them in Blender so the
   exporter can write the same bytes back. Skipping this loses author intent
   permanently.
2. **Wiring the data into the visible shader.** Blender's preview should show
   what the engine will show. Whether vertex alpha drives opacity depends on
   how the BGSM uses it (as opacity, as a sway weight, as something else).

The pynifly importer always loads the `COLOR` and `VERTEX_ALPHA` color
attributes when the vertex format carries colors. The shader importer then
decides whether to wire `VERTEX_ALPHA` into the diffuse output. For tree
materials it explicitly does **not** wire it, because vertex alpha is
sway-weight data that the tree shader consumes separately.

### The tree exception: vertex alpha is wind-sway weight, not visibility

For tree materials (`BGSM.tree = True`), the per-vertex alpha holds wind-sway
weights consumed by the tree shader, **not** a visibility input. Trunk verts
have α=0 (no sway) and branch tips have α≈1 (maximum sway). For non-tree
materials the engine combines vertex alpha with texture alpha and feeds the
product to the alpha test, so a vertex with α=0 makes its corner invisible.
The tree shader breaks that rule and consumes vertex alpha as a sway weight
instead, so importing it as opacity would make the trunk go invisible in
Blender even though it renders fine in-game.

Empirical evidence from `Meshes\Landscape\Trees\TreeMaplePreWar01Orange.nif`
(BGSM `MaplePreWarAtlasOrange.BGSM`, `tree=True, alphatest=True,
alphatestref=175`): plotting per-vertex α against horizontal distance from the
Z axis shows a clean monotonic relationship (Pearson r ≈ 0.56):

| dist from Z axis | n verts | mean α | α=0 verts |
|---|---|---|---|
| 5 – 15 | 16 | 0.08 | 14 / 16 |
| 15 – 30 | 55 | 0.11 | 45 / 55 |
| 30 – 60 | 96 | 0.28 | 57 / 96 |
| 60 – 120 | 169 | 0.68 | 27 / 169 |
| 120 – 300 | 487 | 0.77 | 41 / 487 |

That is the signature of a sway weight, not an opacity mask. Trunk = 0 sway,
outer branches = full sway.

### Counter-example: alphatest-only with real vertex alpha

`Meshes\SetDressing\Rubble\TrashEdge01.nif` — `L1_TrashEdge01:0` has BGSM
`DebrisGroundTile.BGSM` with `alphblend0=0, alphatest=True, tree=False`. Its
per-vertex alpha is real visibility data: in-game the shader multiplies
vertex α by texture α and the alpha test discards the corners where the
product falls below the threshold. Verified in Blender — the imported mesh
matches the in-game appearance once vertex alpha is wired into the diffuse
output. The `tree=False` clause is what distinguishes this case from the
maple.

> ⚠️ Open question: the legacy importer also force-enabled vertex colors for
> any `BSEffectShaderProperty` and force-enabled vertex alpha for
> `GREYSCALE_COLOR` shaders. Those branches were removed in favor of the rule
> above. Grayscale-to-palette and effect-shader test cases need to be
> re-verified to confirm the rule still does the right thing.

## Rule 2: NiAlphaProperty is optional in FO4

Skyrim required a `NiAlphaProperty` block on the shape for any kind of alpha
effect. FO4 does **not**: the engine drives alpha behaviour from the BGSM's
`alphblend0` / `alphatest` fields plus the texture and vertex alpha. The
`NiAlphaProperty` block, if present, just provides additional/legacy controls.

This means:

- Vanilla FO4 shapes regularly ship with vertex alpha and an alphatest BGSM
  but **no** `NiAlphaProperty` in the nif. Example:
  `Meshes\SetDressing\Rubble\TrashEdge01.nif` — `L1_TrashEdge01:0` has
  `hasVertexColors=1`, vertex alphas with both 0 and 1, no NiAlphaProperty
  block, and `materials\Landscape\Ground\DebrisGroundTile.BGSM` /
  `materials\SetDressing\Rubble\RubTrashPiles01.BGSM` with `alphatest=True`.
- `Meshes\Landscape\Trees\TreeMaplePreWar01Orange.nif` also has no
  `NiAlphaProperty` block. Its BGSM is `tree=True, alphatest=True`. The
  engine alpha-tests the leaf card textures to get the leaf silhouettes,
  and uses vertex alpha separately as wind-sway weight. No NiAlphaProperty
  is needed or present.
- An importer that only creates a Blender `AlphaProperty` node when a NIF
  `NiAlphaProperty` block exists will silently strip the visual alpha effect
  from such shapes.

### Implication for pynifly import (implemented)

When importing an FO4 shape:

1. If a `NiAlphaProperty` block exists, build the Blender `AlphaProperty`
   shader node from it. On export, write the block back as before.
2. If no `NiAlphaProperty` block exists but the BGSM has `alphblend0` and/or
   `alphatest`, **synthesize** a Blender `AlphaProperty` node from the BGSM's
   alpha fields so the material in Blender reflects what the engine will do.
   Threshold comes from BGSM `alphatestref`.
3. Mark the material with a custom property (`pyn_synthetic_alpha_from_bgsm`)
   so the exporter does not write a phantom `NiAlphaProperty` block back to
   the nif on round-trip.

## Rule 3: BGSM has no vertex-color / vertex-alpha toggle

There is no field in the BGSM format that says "this material uses vertex
colors" or "this material uses vertex alpha". Whether vertex colors are
multiplied into the shader output is decided by the *vertex format* of the
shape, not the material. Whether the alpha channel is blended is decided by
`alphblend0` / `alphatest`.

This is different from how some Skyrim docs/tools describe it, and is the
source of the confusion that led to the original bug.

### Vanilla examples

- `Meshes\SetDressing\LightFixtures\WorkshopLightbulbHanging01.nif` —
  `Bulb001:3` carries vertex colors (the format bit is set) but its BGSM does
  nothing special with them; the vertex stream is uniformly white/opaque and
  the appearance of the bulb is driven entirely by the texture and material.
  Shows that "shape has vertex colors" does not imply "material consumes
  them" — and conversely, the BGSM has no field that says "use them".
- `Meshes\SetDressing\Rubble\TrashEdge01.nif` — opposite case: the BGSM has
  no `vertexColors` / `vertexAlpha` field at all, but the shape's vertex
  format includes colors and the rendered decal uses the per-vertex alpha
  as a real opacity mask (combined with the texture's alpha channel and
  the material's `alphatest`). The decision to consume vertex alpha is
  made by the vertex format bit plus the BGSM's alpha-test/blend state,
  not by any "vertex colors" toggle.

## Test fixtures

- `tests/tests/FO4/meshes/TrashEdge01.nif` (`TEST_TRASH_EDGE`) — non-tree
  decal mesh:
  - `L1_TrashEdge01:0`: `hasVertexColors=1`, real per-vertex alpha (0 and 1)
    that the engine consumes as opacity, no NiAlphaProperty block, BGSM
    `DebrisGroundTile.BGSM` with `alphblend0=0, alphatest=True, tree=False`.
    Verifies that vertex colors+alpha are imported, the Alpha Property
    shader node is synthesized from the BGSM, vertex alpha round-trips, and
    no `NiAlphaProperty` block is written back on export.
  - `L2_TrashDecal01:1`: `hasVertexColors=0`, no NiAlphaProperty, BGSM with
    `alphatest=True`. The shape should not get vertex colors or alpha — its
    alpha behaviour is purely texture-driven.
  - Also exercises LOD edge cases (empty LOD0/LOD1 buckets).
- `tests/tests/FO4/TreeMaplePreWar01Orange.nif` (`TEST_TREE`) — tree mesh:
  - BGSM `MaplePreWarAtlasOrange.BGSM` with `tree=True, alphatest=True`.
  - 1059 verts with `hasVertexColors=1`. Per-vertex alpha is wind-sway
    weight (Pearson r ≈ 0.56 with horizontal distance from Z axis); 185
    verts including the trunk have α=0. Verifies that the trunk stays
    visible in Blender (vertex alpha is NOT wired into the diffuse output)
    while still importing the data into the `VERTEX_ALPHA` color attribute
    so wind-sway weights round-trip on export.

## Related code

- `io_scene_nifly/nif/import_nif.py` — `import_colors` (Rule 1)
- `io_scene_nifly/nif/shader_io.py` — `import_material`, `import_shader_alpha`
  (synthesized AlphaProperty for FO4; tree-material opt-out from wiring
  `VERTEX_ALPHA`)
- `io_scene_nifly/pyn/bgsmaterial.py` — `alphblend0`, `alphatest`, `tree`
  field definitions
- `io_scene_nifly/pyn/pynifly.py` — `_load_properties_from_materials`
  (BGSM → shader property translation; does not touch vertex-color/alpha
  interpretation)
