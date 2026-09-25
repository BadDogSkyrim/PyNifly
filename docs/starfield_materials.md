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

### A `.mat` is a derivation, and the chain is resolved first

A Starfield material normally states only what it CHANGES about another one. It names a
parent with `Import` and overrides selected components of that parent's objects. Of the
48,505 authored vanilla materials, **99.5% carry `Import`** and only **0.3% carry a
`ShaderModelComponent`** — the shader model belongs to the template they derive from.

So reading the file alone reads almost none of the material. PyNifly resolves the whole chain
(loose files, then the mod's own BA2 tree, then `materialsbeta.cdb`) and builds the node tree
from the **effective** material: what the engine would assemble. A chain normally ends in
`Materials\Layered\Root\*.mat`, which ships only inside the database — one more reason to set
the **Starfield .cdb path** preference.

A parent that cannot be found is reported, never silently skipped: "nothing to inherit" and
"could not look it up" produce very different materials and only one of them is right.

Two things follow, and they are what the rest of this page is about:

- The graph shows the material that renders, so on its own it cannot say which of those
  values this file owns. PyNifly stamps that on every node — see
  [Where a value came from](#where-a-value-came-from).
- Export must write the delta back, not the whole thing. See
  [Export](#the-material-is-written-as-a-derivation).

### The Blender graph

For Starfield, PyNifly writes a native **Principled BSDF** node, fed by group nodes that
represent the layered structure. Each node is stamped with special-purpose custom properties:

| Node | Purpose | Stamped with |
|---|---|---|
| `SF Layer` | one per layer | `pyn_sf_layer` (index) |
| `SF Blend <Mode>` | one per blender — `SF Blend Skin`, `SF Blend Lerp`, … | `pyn_sf_blend` |
| Image texture | one per texture slot | `pyn_sf_layer`, `pyn_sf_slot`, `pyn_sf_path` |
| Mapping | per-layer UV scale/offset (absent = 1:1) | `pyn_sf_layer` |
| `SF Base: <material>` | one per inherited material, nested one per level of the chain | `pyn_sf_base` |

A blend mode the material never declares becomes `SF Blend Default` (the shader model
decides -- vanilla eyes are like this); one we don't implement becomes `SF Blend Unknown`.
Neither is dropped, so the mode
still round-trips.

### Where a value came from

The graph shows the effective material, so "is this mine or did I inherit it?" has to be
recorded separately. Two places show it:

**`SF Base` group nodes.** One shared node group per inherited material, named for it, nested
one level per step up the chain:

```
material node tree                              <- this .mat: the objects it owns
  |_ SF Base: layered/shadermodels/eye1layer    <- the shader model: layers, blenders,
      |                                            ShaderModelComponent, EyeSettingsComponent
      |_ SF Base: layered/root/layeredmaterials <- the root template: defaults for the rest
```

Tab into one to see what that level supplies. They are a **view**: rebuilt from the resolver
on every import and never read back, so editing inside one cannot change what gets written —
it can only make the view wrong, and it is a shared datablock, so wrong for every material
that derives from the same parent.

**The PyNifly Material Chain panel** (shader editor sidebar > Item). For the selected node it
lists which material set each field, inherited values greyed. It also carries **Claim for this
material**, which forces a node's values to be written even where they match the parent. That
is the one case a diff cannot see: a value deliberately set to what the parent happens to say
is, by construction, indistinguishable from never having touched it.

Inherited values cannot be greyed in the graph itself — node sockets draw themselves and
Blender has no way to make one read-only. That is why there is a panel.

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
both — and because every node carries what it needs, **whatever is already at the output path is
replaced outright**. Nothing is read off disk, so nothing in the old file can survive by accident.

### The material is written as a derivation

The node tree holds the *effective* material — everything that reaches it, inherited and owned
alike. Writing that back out produces a file that parses, that the Creation Kit accepts, and
that renders **nothing** in game. What goes on disk is the delta.

So export resolves the chain again, at write time, and removes everything the parents already
say. Resolving rather than remembering is deliberate: export needs the chain anyway (for the
parents' object ids), and a value stashed at import can go stale, while the live parent cannot.
The consequence is what-you-see-is-what-you-get — a material does not change under you because
Bethesda patched a template — at the cost that a stale import pins values it did not mean to.
Re-import to pick up a changed parent.

Three rules here are load-bearing, and each can produce a file that parses and renders nowhere:

- **Ids are kept verbatim.** See [Material identity](#material-identity).
- **`Edges` come from the resolved chain**, not from what the file references locally: 1,138 of
  21,302 sampled objects are contained by something they never reference.
- **The root's `LayerID`/`BlenderID` list is written in full.** It is authoritative, not
  additive — declaring a shorter list is how a material deletes a layer. Inherit it and the
  deleted layer comes back.

A material with no `Import` — one authored from scratch in Blender — is written complete, which
is the form that does not render. If you are building a Starfield material from nothing, derive
it from a vanilla one instead.

### What still isn't editable

Preserved is not the same as editable. Components PyNifly has no Blender representation for ride
along untouched, but there is no way to *change* them from Blender — you get whatever the source
material had. Materials authored entirely in Blender can only contain what PyNifly models.

Closing that gap — modelling each remaining component on the Blender node it came from — is the
subject of [the material I/O plan](plan_starfield_material_io.md), continued in
[the inheritance plan](plan_sf_material_inheritance.md).

## Material identity

Two identifiers, and only one of them is derived from the material's path.

| Identifier | Where it lives | Derived from |
|---|---|---|
| `MaterialID` | `NiIntegerExtraData` on the shape's `BSGeometry` | CRC-32 of the lowercased material path |
| `res:` ID | words 1–3 of every object ID in the `.mat` | **nothing you can compute** — see below |

### `res:` IDs are a registered space, not a hash

PyNifly used to treat an object id's namespace (words 2–3) as a hash of the material path, and
re-namespaced every id on export so a material derived from a vanilla one "could not collide"
with it. That was invented, and it is fatal.

Measured across vanilla: word 2's top half is `0005` (74.8%) or `0006` (25.2%) — 99.99%
together — and word 3 has **118 distinct values game-wide**. A hashed namespace lands nowhere
near that space, and a material outside it is not in the database the engine looks in.

Proven in game, with a ladder of variants at one eye's path:

| | change from vanilla's authored `left_eye.mat` | in game |
|---|---|---|
| v0 | byte for byte | renders |
| v1 | + the iris texture repointed | renders |
| v2 | + its `res:` ids moved to a new namespace | **FAILS** |
| v3 | + only the ids' *first* field changed, namespace kept | renders |

v0 also disposes of the collision theory it was built on: a byte-for-byte duplicate of a
vanilla material, at a different path, renders perfectly.

**So ids are never re-minted.** An imported object keeps its id exactly; a genuinely new object
gets an unused first word inside a namespace the material already uses. Nothing short of
running the game catches getting this wrong — the file parses, the CK loads it, and the mesh is
simply invisible.

### You can still not move or rename a `.mat` by hand

The shape's `MaterialID` hashes the material path, so renaming or moving the file leaves the
geometry pointing at a hash of the old one. **Re-export instead** — PyNifly recomputes
`MaterialID` from the shader's material path. (The `res:` ids do not care where the file lives.)

### ✅ Resolved: re-saving to the same path no longer rewrites the ids

An earlier version gave every object a fresh `res:` ID when writing a material back to the path
it came from, which orphaned every external reference to those objects and could crash the
Creation Kit (`Bad path res:…:0074616D` — that last word is `"mat"` little-endian — followed by
an access violation on the null result).

The open design question that went with it — how to tell "overriding this material" from
"creating a copy of it" — turned out not to need answering. Neither case wants new ids.

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

- **Moved or renamed a `.mat` and the shape lost its material** — the `MaterialID` on the shape
  is a hash of the material's path. Re-export rather than moving the file by hand. (The `res:`
  ids are unaffected; they are not derived from the path.) See
  [Material identity](#material-identity).
- **Head part invisible in game but fine in the Creation Kit** — the classic symptom of a
  material whose `res:` ids are outside the registered space, or of a flat material written
  where a derivation was wanted. Both are fixed; if you see it with a current build, check
  first that the `.mat` really does carry an `Import`.
- **Swapped texture ignored on export** — the image datablock still points at the old file, or
  sits outside a `textures` tree so the stamp fallback wins.
- **Black face** — a layer with `MaterialOverrideColorTypeComponent = Multiply` over missing or
  black vertex colours. Check the mesh's `VERTEX_COLOR` layer before suspecting the material.
- **Magenta in game but fine in NifSkope** — the `.mat` isn't game-valid. NifSkope's renderer
  and PyNifly's reader are both lenient about this; the game is not. Note that the old rule of
  thumb here — "every node needs a `Parent` into a Root template, a `CTName` and a unique
  `res:` ID" — is wrong: 94.4% of vanilla child objects parent to a `res:` id rather than a
  template, and 67,234 objects carry no `CTName` at all. See
  [Starfield Materials & Textures](https://baddogskyrim.github.io/BethesdaLibrary/game-specific/starfield/materials/)
  for the requirements.
- **Import warns "could not find material"** — expected when the material is inside a BA2 or
  compiled into the `.cdb` with no preference set. Not an error in the shape.
