# Starfield Support in PyNifly

Starfield diverges from Skyrim/FO4 more than any previous Bethesda title: the geometry
lives outside the NIF, materials are a graph-based JSON format compiled into a database,
and the head/face system is driven by files that no record points at. These pages
document what PyNifly knows about each piece.

## Scope: these docs vs the Bethesda Library

Two doc sets, two jobs:

- **[Bethesda Modding Library](https://baddogskyrim.github.io/BethesdaLibrary/)**
  ([Starfield section](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/overview/))
  defines the **formats and semantics** — what a `.mat` is, how the `.mesh` is encoded, what the
  records mean. It's game documentation and is not about any particular tool.
- **These pages** describe **how PyNifly works**: what it imports, what it writes, how a format
  concept is represented in Blender, and what it does and doesn't preserve. They lean on the
  Bethesda docs for format detail rather than restating it.

So a question like "what is a root template" is answered there; "what does PyNifly do about root
templates when it writes a `.mat`" is answered here.

## The short version

| | Skyrim / FO4 | Starfield |
|---|---|---|
| Geometry | in the NIF (`BSTriShape`) | external `.mesh` under `Data\geometries\`, named by hash |
| Shape block | `BSTriShape` / `BSSubIndexTriShape` | `BSGeometry` |
| Textures | `BSShaderTextureSet` in the NIF | named `.mat` — **no texture set in the NIF at all** |
| Material | `.bgsm` / `.bgem` (flat) | `.mat` (layered object graph), usually compiled into `materialsbeta.cdb` |
| Skin | `NiSkinInstance` + bone `NiNode`s | `SkinAttach` / `BSSkin::Instance` / `BSSkin::BoneData`, **no bone nodes in the file** |
| Head morphs | `.tri` | `morph.dat`, split chargen / performance |
| Head parts | one NIF | a **pair**: `<name>.nif` + `<name>_facebones.nif`, each with its own `.mesh` |

## Pages

- **[Materials and shaders](starfield_materials.md)** — the `.mat` object graph, how PyNifly
  maps it to a Blender shader graph and back, and what makes a loose `.mat` game-valid.
  *(written)*

Planned, in rough priority order:

- **Geometry and the external `.mesh`** — `BSGeometry`, `meshName`, the `geometries\` tree,
  internal geometry (flag `0x200`), vertex splitting at UV seams, LOD slots.
- **Shape extra data** — `MaterialID` (a CRC-32 of the material path, generated on export),
  `AnimationFlagExtra`, and the shape-flags convention (`14` external / `526` internal).
  Some of this is already in [starfield_materials.md](starfield_materials.md#materialid).
- **Skinning and skeletons** — how bone transforms are recovered without bone `NiNode`s,
  and the reference-skeleton requirement.
- **Morphs** — `morph.dat` layout, the chargen/performance split and how a shape key is
  classified, and the rule that morph vertex count must equal the `.mesh` vertex count.
- **Head parts and FaceGen** — the facebones pairing convention, what the race record has to
  declare, and the `BSFaceDB` head-build graph.

Plugin-side record wiring (RACE / HDPT / MRPH, chargen morph groups, skin tones) is game
data rather than PyNifly behaviour and is documented in the Bethesda Library instead.

## Format facts owed to the Bethesda Library

Things established while working on PyNifly that belong in the format docs, not here:

- **`MaterialID` NiIntegerExtraData** on the `BSGeometry` — present on 372 of 373 shape NIFs
  surveyed across vanilla and mod archives; the value is a reflected CRC-32 (poly `0x04C11DB7`,
  init `0`, no final XOR) of the material path lowercased with backslashes, including the
  `Materials\` prefix and `.mat` extension. Needs distinguishing from the unrelated
  `BSMaterial::MaterialID` component inside a `.mat`.
- **`AnimationFlagExtra`** — a `NiIntegersExtraData` on the shape, one value; hair/beards `31`,
  eyes/teeth/tongue/brows/lashes `255`, male head `32`. Not yet implemented in PyNifly.
- **No `BSShaderTextureSet` in Starfield NIFs** — 0 of 438 sampled.
- **Shape flags are only ever `14` or `526`** — `526` is `14 | 0x200`, and `0x200` is the
  internal-geometry bit. The correlation with internal geometry was exact across 2548 shapes.
