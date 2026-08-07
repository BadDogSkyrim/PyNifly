# Starfield Materials in PyNifly

How PyNifly imports a Starfield `.mat` into a Blender shader graph, recovers it on export, and
what it does and doesn't preserve.

Part of the [Starfield support](starfield.md) notes.

**This page does not document the `.mat` format.** That lives in the
[Bethesda Modding Library](https://baddogskyrim.github.io/BethesdaLibrary/):

| For | See |
|---|---|
| Architecture, the `.mat` JSON, root templates, shader models, component blocks | [Starfield Materials & Textures](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/materials/) |
| A fully annotated real 2-layer skin material | [Material worked example](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/material-worked-example/) |
| Reading materials out of `materialsbeta.cdb` | [The CDB format](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/cdb-format/) |
| `BSGeometry`, the external `.mesh`, skinning | [Starfield meshes](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/meshes/) |

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
without it every vanilla material has to be pre-extracted first.

PyNifly can read the database directly if you need loose copies for reference:

```
python -m pyn.sf_cdb <materialsbeta.cdb> <path.mat | list-of-paths.txt> [outdir]
```

The database stores materials by resource ID with **no file paths**, so it can't be enumerated —
extracting a material means already knowing its path.

The "could not find material" warning is also normal — and harmless — for a mod whose materials
are inside its BA2.

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

### The material is built from the node tree

**The node tree is the material.** Every object in the written `.mat` is emitted from what the
shader graph says, in the order the graph gives it. Nothing on disk is consulted, and nothing is
copied forward just because it used to be there.

That matters most for things you *add*. A layer created in Blender is written like any other
layer — which the previous approach could not do, because it worked by editing a copy of the
original document and could only find layers that already existed in it.

Each node also keeps the **identity and inheritance it was imported with**: its `res:` ID, its
`Parent` link, its name, and every component it carried. The values PyNifly models are merged
*over* those carried components. Two consequences, both deliberate:

- A component PyNifly doesn't model survives whole.
- An unmodelled *field* of a component PyNifly does model survives too.

So round-tripping a vanilla material through Blender does not quietly strip it. A node with no
imported identity — one you added, or a material authored from scratch — gets a fresh ID and the
appropriate shipped Root template as its `Parent`.

Earlier versions rebuilt the file from only what PyNifly modelled, and destroyed everything else
on every export. The version after that patched the original document in place, which preserved
the unmodelled parts but could not express anything new. The current behaviour is meant to give
both.

### What still isn't editable

Preserved is not the same as editable. Components PyNifly has no Blender representation for ride
along untouched, but there is no way to *change* them from Blender — you get whatever the source
material had. Materials authored entirely in Blender can only contain what PyNifly models.

Closing that gap — modelling each remaining component on the Blender node it came from — is the
subject of [the material I/O plan](plan_starfield_material_io.md).

## Material identity

Two separate identifiers are derived from **the material's path**, and both are why a `.mat`
cannot simply be moved.

| Identifier | Where it lives | Derived from |
|---|---|---|
| `res:` ID namespace | words 2–3 of every object ID in the `.mat` | hash of the material path |
| `MaterialID` | `NiIntegerExtraData` on the shape's `BSGeometry` | CRC-32 of the lowercased material path |

### You can't move or rename a `.mat` by hand

Renaming the file, or moving it to a new folder, breaks both:

- The shape's `MaterialID` still hashes the **old** path, so the geometry no longer resolves to
  the material.
- The object IDs still sit in the old path's namespace.

**Re-export instead.** PyNifly recomputes `MaterialID` from the shader's material path and
re-namespaces the IDs to match, so the two stay consistent. This bites hardest when relocating a
mod out of vanilla paths into its own tree: move the files and the plugin paths, then re-export
the NIF so the shape's `MaterialID` follows.

### ⚠️ Known issue: re-saving to the same path rewrites the `res:` IDs

Writing a material back to **the path it came from** currently gives every object a fresh `res:`
ID anyway. That is wrong, and it can crash the Creation Kit.

A `res:` ID is an object's identity in the game's global material database, and other assets
reference those objects by ID. Overriding a vanilla material with a loose file that has all-new
IDs orphans every one of those references. Observed on a vanilla male head round-tripped to
`materials\Actors\Human\Faces\male_default.mat`:

| | object IDs | namespaces | shared with vanilla |
|---|---|---|---|
| vanilla (from the `.cdb`) | 33 | 5 | — |
| PyNifly's loose override | 33 | 1 | **0** |

The CK log showed 9 × `Bad path res:…:0074616D` (that last word is `"mat"` little-endian — so
unresolvable *material* references), followed by an access violation on the null result. Those
lines appear in no earlier crash log.

Note that vanilla materials legitimately span **several** namespaces in one file: nodes owned by
a shader-model template live in the template's namespace, not the material's. "One namespace per
material" was never the real convention.

**Why it happens.** The per-node identity is carried correctly all the way through the build —
each node still knows its original ID — and is then overwritten wholesale by a final
re-namespacing pass over the finished document. The information needed to do better is already
there; it is being discarded at the last step.

**Open design question — not yet resolved.** The tension is real in both directions:

- Writing to the **same** path means *overriding* that material. IDs must be preserved, or
  external references break.
- Writing to a **new** path means *creating* a material. IDs must change, or the copy collides
  with its source in the database and silently overrides it everywhere.

So the rule wants to be "identity follows the path" — re-namespace only on a path change. What
makes that harder than it sounds is deciding what the source path *is*:

- The material may have been read from `materialsbeta.cdb`, where there is no loose file it
  "came from" — but overriding it still means keeping its IDs.
- The material path can be retargeted in Blender, so the shader's current name may not be where
  the nodes were imported from.
- A material may carry nodes from more than one namespace, so "the" source path may be
  ambiguous at the document level even when it's clear per node.

A per-node rule (keep a carried ID, mint only for new nodes) handles the multi-namespace case
naturally, but on its own it makes a save-as into a colliding duplicate. Whether the right answer
is a path comparison, a per-node rule, an explicit "override vanilla" export choice, or some
combination is still open.

### Writing materials at all is optional

Materials are only written when the **export materials** option is on, and only for materials
with a recoverable SF graph. The option is sticky per nif.

## What PyNifly writes into the NIF

Two Starfield-specific behaviours on the NIF side, both about materials:

- **No `BSShaderTextureSet`.** Starfield takes its textures from the `.mat`; no vanilla SF NIF
  carries a texture set. PyNifly used to write one anyway (from both the Python shader export
  and the DLL's shape-creation path); it no longer does for SF.
- **`MaterialID` is generated.** Every Starfield character shape carries a `NiIntegerExtraData`
  named `MaterialID` on its `BSGeometry`, holding a CRC-32 of the material path (see
  [Material identity](#material-identity)). It's derived data, so PyNifly computes it on export
  from the shader's material path rather than asking you to maintain a hash.

  ⚠️ **Not the same thing as `BSMaterial::MaterialID`**, which is a component *inside* the `.mat`
  that references a Material node. Same name, unrelated meaning.

## Gotchas

- **Moved or renamed a `.mat` and the shape lost its material** — both the `MaterialID` on the
  shape and the `res:` ID namespace are derived from the material's path. Re-export rather than
  moving the file by hand. See [Material identity](#material-identity).
- **CK crashes after overriding a vanilla material** — re-saving to the same path currently
  rewrites the `res:` IDs, orphaning external references. Known issue, documented above.
- **Swapped texture ignored on export** — the image datablock still points at the old file, or
  sits outside a `textures` tree so the stamp fallback wins.
- **Black face** — a layer with `MaterialOverrideColorTypeComponent = Multiply` over missing or
  black vertex colours. Check the mesh's `VERTEX_COLOR` layer before suspecting the material.
- **Magenta in game but fine in NifSkope** — the `.mat` isn't game-valid (missing `Parent`
  links, `CTName`s, or unique `res:` IDs). NifSkope's renderer and PyNifly's reader are both
  lenient about this; the game is not. See
  [Starfield Materials & Textures](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/materials/)
  for the requirements.
- **Import warns "could not find material"** — expected when the material is inside a BA2 or
  compiled into the `.cdb` with no preference set. Not an error in the shape.
