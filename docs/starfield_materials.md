# Starfield Materials in PyNifly

How PyNifly imports a Starfield `.mat` into a Blender shader graph, recovers it on export, and
what it does and doesn't preserve.

Part of the [Starfield support](starfield.md) notes.

**This page does not document the `.mat` format.** That lives in the Bethesda Library
(`docs/game-specific/starfield/`): [Bad Dog: Links should be to the online betheseda library, not local]

| For | See |
|---|---|
| Architecture, the `.mat` JSON, root templates, shader models, component blocks | `materials.md` |
| A fully annotated real 2-layer skin material | `material-worked-example.md` |
| Reading materials out of `materialsbeta.cdb` | `cdb-format.md` |
| `BSGeometry`, the external `.mesh`, skinning | `meshes.md` |

Terms used below — layer, blender, TextureSet, UVStream, root template, `res:` ID — are defined
there.

## Import

### Finding the material

The shape's `BSLightingShaderProperty.Name` holds the material path. PyNifly resolves it in
order:

1. **A loose `.mat`** on disk, through the same search PyNifly uses for textures and meshes.
2. **`materialsbeta.cdb`**, if the **Starfield .cdb path** preference points at it.
3. Otherwise it warns and the shape imports untextured.

Step 2 is why that preference exists: vanilla materials are compiled into the database, so
without it every vanilla material has to be pre-extracted (e.g. fo76utils `sfmatexport`). [BD: We need to double-check this reference - isn't fo76utils fallout-=only?]
The warning is also normal — and harmless — for a mod whose materials are inside its BA2.

### The Blender graph

For Starfield, PyNifly writes a native **Principled BSDF** node, fed by group nodes that
represent the layered structure. Each node is stamped with special-purpose custom properties:

| Node | Purpose | Stamped with |
|---|---|---|
| `SF Layer` | one per layer | `pyn_sf_layer` (index) |
| `SF Blend <Mode>` | one per blender — `SF Blend Skin`, `SF Blend Lerp`, … | `pyn_sf_blend` |
| Image texture | one per texture slot | `pyn_sf_layer`, `pyn_sf_slot`, `pyn_sf_path` |
| Mapping | per-layer UV scale/offset (absent = 1:1) | `pyn_sf_layer` |

An unrecognised blend mode becomes `SF Blend Unknown` rather than being dropped, so the mode
still round-trips.

The mesh's vertex colour layer is named `VERTEX_COLOR` in Blender. It matters: vanilla
head materials set `MaterialOverrideColorTypeComponent = Multiply` on a layer, which
multiplies that layer's albedo by the mesh's vertex colour — so a head with no vertex
colours, or black ones, renders black. That's a material behaviour, not a PyNifly one, but
it's the first thing to check when a face comes out black.

## Export

### The node is the source of truth

A texture path is derived from **the image actually assigned to the node** — its location on
disk, sliced from the `textures` directory onward. The `pyn_sf_path` stamp recorded at import is
only a fallback, for images that are packed, missing, or stored outside a `textures` tree.

Same rule as FO4/Skyrim (node = truth, property = fallback). Note that if you move the textures 
on disk you must point the shader texture nodes to the new location so they will be written
to the `.mat` file correctly. 

### What PyNifly models

[BD: Edit to remove references to internal procedures. PyNifly users shouldn't need that, 
and shouldn't need to know we use a dict internally.]

`recover_sf_material` walks the shader graph back into the same normalised dict `parse_mat`
produces: per-layer textures, UV scale/offset, override colour; per-blender mode, mask and
channel; and the settings blocks (shader model, translucency, emissive, alpha, hair).

That dict is a **lossy projection of the format**. Vanilla skin carries a good deal it doesn't
describe:

| Component | vanilla `male_default.mat` | in PyNifly's dict |
|---|---|---|
| `ParamBool` | 18 | — |
| `MaterialParamFloat` | 4 | — |
| `TextureReplacement` | 2 | — |
| `UVStreamID` | 11 | 5 |
| objects total | 34 | 29 |

### Patching, not rebuilding

Because of that gap, export **patches an existing `.mat` document** rather than building one
from the dict. `write_mat(data, filename, template)` writes the modelled values into the
template in place and leaves every other component untouched, then re-namespaces the `res:` IDs
for the target filename and retargets the `CTName`s — so a material derived from a vanilla one
can't collide with it in the material database.

Template precedence:

1. **The `.mat` being overwritten**, if one exists — a hand-edited material survives re-export.
2. **The material the shader names**, resolved through the normal search paths — a material
   derived from a vanilla one keeps its structure even when written to a new path.
3. **Nothing** — build from scratch. Correct for a material authored entirely in Blender, but
   the result can only contain what PyNifly models.

Rebuilding from the dict was the old behaviour, and it destroyed the first column of the table
above on every export.

**This is a workaround, not the end state.** The real fix is to model those components in
Blender so they are editable; patching means that until then they are at least preserved.

### Writing materials at all is optional

Materials are only written when the **export materials** option is on, and only for materials
with a recoverable SF graph. The option is sticky per nif.

## What PyNifly writes into the NIF

Two Starfield-specific behaviours on the NIF side, both about materials:

- **No `BSShaderTextureSet`.** Starfield takes its textures from the `.mat`; no vanilla SF NIF
  carries a texture set. PyNifly used to write one anyway (from both the Python shader export
  and the DLL's shape-creation path); it no longer does for SF.
- **`MaterialID` is generated.** Every Starfield character shape carries a `NiIntegerExtraData`
  named `MaterialID` on its `BSGeometry`, holding a CRC-32 of the material path. It's derived
  data, so PyNifly computes it on export from the shader's material path rather than asking you
  to maintain a hash. `pyn.sf_materials.material_id(path)` is the function.

  ⚠️ **Not the same thing as `BSMaterial::MaterialID`**, which is a component *inside* the `.mat`
  that references a Material node. Same name, unrelated meaning.

## Gotchas

- **Swapped texture ignored on export** — the image datablock still points at the old file, or
  sits outside a `textures` tree so the stamp fallback wins.
- **Black face** — a layer with `MaterialOverrideColorTypeComponent = Multiply` over missing or
  black vertex colours. Check the mesh's `VERTEX_COLOR` layer before suspecting the material.
- **Magenta in game but fine in NifSkope** — the `.mat` isn't game-valid (missing `Parent`
  links, `CTName`s, or unique `res:` IDs). NifSkope's renderer and PyNifly's reader are both
  lenient about this; the game is not. See `materials.md` for the requirements.
- **Import warns "could not find material"** — expected when the material is inside a BA2 or
  compiled into the `.cdb` with no preference set. Not an error in the shape.
