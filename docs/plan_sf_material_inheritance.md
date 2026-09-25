# Plan: Starfield material inheritance

**Status:** COMPLETE, 2026-09-24. All five phases done, and the derived-export path
verified in game. Successor to
[plan_starfield_material_io.md](plan_starfield_material_io.md), whose open question 1 —
"what actually makes a `.mat` valid?" — this answers.

We will priorize a rendering in Blender that reflects reality, is complete, offers full control of what aspects of a shader are written to the exported material and what are left on the parent, and provides round-trip with full fidelity. We do not much care about continuity or compatibility with the existing implementation or with minimizing the amount of change.

Since vanilla materials have three natural layers - individual material -> shader model template -> root template, it makes sense to reveal those layers in the Blender shader we build.

## The short version

A Starfield `.mat` is normally a **derivation**: it names a parent material with `Import`,
and its objects override selected components of the parent's objects. PyNifly reads and
writes the **flattened** form instead. Flattened materials load in the Creation Kit and
render there, and they do not render in game.

We got here by testing against the wrong reference. `00StarfieldAssets\materials` is a
**CDB dump** — our own reader's flattened rendering of the compiled database, not what
Bethesda authored. Every "this matches vanilla exactly" check in this codebase was made
against it.

## What it cost

A custom fox eye material, invisible in game, correct in the CK. We chased it through the
NIF (`AnimationFlagExtra`, root flags, node transforms), the `.mesh` (vertex colours, the
SNORM scale margin), the plugin records, the skeleton, the `res:` ID namespaces and the
material's component list — all clean, all irrelevant. The material was semantically
identical to vanilla and still invisible, because it was the wrong *kind* of document.

The rule this plan is built on: **round-trip fidelity is not game-validity** — already
written in the previous plan's Risks, and still the thing that bites.

## The format, measured

All figures from **`C:\Modding\Starfield\Mods\Starfield Materials Loose`** (the CK source
drop, authored form), 48,505 materials parsed, 1 unparseable. Do not re-derive these from
`00StarfieldAssets`.

| Fact | Measurement |
|---|---|
| Carry `Import` | **48,280 / 48,505 (99.5%)** |
| `Import` entries | 1 in 41,217; **2–7 in 7,063** — multiple inheritance is real |
| Root `Parent` is a material path | **48,260 (99.5%)**; a Root template in 211; absent in 34 |
| Root carries `ShaderModelComponent` | **123 (0.3%)** — these are the ShaderModel templates themselves |
| Child `Parent` is a `res:` ID | **316,695 (94.4%)**; Root template 13,415; other path 5,476 |
| `Edges` on every child | **48,417 / 48,471 materials** |
| Edge types | `BSComponentDB2::OuterEdge` 335,517; **`BSMaterial::MaterialParent` 523** |
| Children with **no components** | 49,276 — pure inheritance placeholders |
| Children with **no `CTName`** | 67,234 |
| Components carrying `Version` | `MRTextureFile` v2 ×161,174, v1 ×54,956; `TextureSetID` v3 ×42,858 … |

### Chain shape

Chains are shallow and regular:

```
Actors\Human\Faces\left_eye.mat        15 objs, no ShaderModelComponent
  -> Layered\ShaderModels\Eye1Layer.mat  15 objs, ShaderModelComponent = Eye1Layer
       -> res:00000000:00000000:6E617274        (terminator, CDB only)

Actors\Human\Faces\Teeth\NNTeeth.mat    5 objs, no ShaderModelComponent
  -> Layered\ShaderModels\1LayerMouth.mat 5 objs, ShaderModelComponent = 1LayerMouth
       -> Data\Materials\Layered\Root\LayeredMaterials.mat   (CDB only, no file)
```

Consequences:

- **The shader model lives on the template, not on the concrete material.** Anything that
  asks "what shader model is this?" by reading the local file is wrong for 99.7% of
  materials.
- **The chain terminates in objects that exist only in the CDB.** `Layered\Root\*.mat` has
  no files anywhere. A resolver must reach the compiled database.
- Likewise the settings components: `EyeSettingsComponent` on `Eye1Layer.mat`,
  `MouthSettingsComponent` on `1LayerMouth.mat`. A derived material that overrides neither
  is correct, and our new `sf_racecheck` check would wrongly pass it (see Tests).

### `Edges` — what they are

**An edge is the component database's relationship primitive.** A `.mat` is not a tree of
nested objects: it is a flat list of database entities, and edges are how the graph between
them is expressed. Each edge has exactly three fields — `Type`, `To`, `EdgeIndex` — and
`EdgeIndex` was `0` in all 27,418 sampled, presumably a slot number for multi-valued
relations. An object almost always carries exactly one edge; 27 of 31,395 carried two.

Two types exist, doing different jobs:

| type | count | means |
|---|---|---|
| `BSComponentDB2::OuterEdge` | 27,385 | **containment** — "my outer object is X". `"<this>"` = the material's root. This is what reassembles the flat object list into a tree. |
| `BSMaterial::MaterialParent` | 33 | **inheritance**, the same relation the `Parent` field carries, expressed as an edge. Points at a template *path* (`Data\Materials\Layered\Root\Layers.mat`), not an id. In `Stinger_Base.mat` objects carry both kinds at once. |

Keep the two axes apart — conflating them is how this went wrong:

| | means | points at |
|---|---|---|
| `Parent` **field** | inheritance: "I override / derive from that object" | an object in a **parent material** |
| `OuterEdge` | containment: "I belong to that object here" | the **owning object in this document** |

Containment is the inverse of the component references that point downward — Layer*n*'s
`MaterialID` → Material*n*, and Material*n*'s `OuterEdge` → Layer*n*:

| object | `To` |
|---|---|
| Blender*n*, Layer*n* (held by the root) | `"<this>"` |
| Material*n* | Layer*n*'s id |
| TextureSet*n* | Material*n*'s id |
| UVStream of a layer | Layer*n*'s id |
| UVStream of a blender | Blender*n*'s id |

It is an **inbound ownership edge**, not a self-reference. Pointing everything at
`"<this>"` produces a file that parses, resolves and renders nowhere.

> ⚠ **Export cannot derive edges from local references alone.** Checked over 3,000
> materials: the `OuterEdge` matches the inverse of a local reference 20,161 times and
> **fails to 1,138 times**, always for the same reason — the object is referenced by nothing
> in the local file, because the reference lives in the **parent**. A pure override still
> declares its container even though the pointer establishing that containment is inherited.
> So Phase 3 needs the resolved chain to emit edges correctly; a local-only exporter will
> silently produce another file that parses and renders nowhere.

### Components merge FIELD BY FIELD

An override restates only the fields it changes; the rest show through from underneath.
Authored `left_eye.mat` gives `EyeSettingsComponent` its six iris numbers and never mentions
`Enabled`, which comes from the `Eye1Layer` template:

```
merged   {"Enabled": "true", "IrisDepthPosition": "0.0944", "IrisTotalDepth": "0.0029", ...}
             Enabled            <- Layered\ShaderModels\Eye1Layer.mat
             IrisDepthPosition  <- Actors\Human\Faces\left_eye.mat
```

Confirmed against the compiled database, whose composed `left_eye.mat` holds exactly those
seven fields. Replacing a component's payload wholesale drops the fields the author chose
not to restate **and still yields something that looks like a complete component** — which
is what makes it dangerous. Found by a test, not by reading.

**This sets the granularity of the whole design: the unit of ownership is a FIELD, not a
component.** `pyn_sf_owned` / `pyn_sf_override` are per field, and provenance is recorded
per field — one component routinely has two origins.

### Where a material is read from

The resolver prefers a **loose file** and falls back to the **compiled database**, matching
the game's override semantics. Consequence, accepted deliberately: a material present in
both is read in its authored form, *without* the defaults the compiler materialises. That is
the right trade for this purpose — compiler defaults must not be written into a derived file
as though the author had stated them.

### `res:` ids — a registered space, not free bits

`res:AAAAAAAA:BBBBBBBB:CCCCCCCC`. Over every id occurrence in the authored tree:

- **field B's top 16 bits are `0005` (74.8%) or `0006` (25.2%)** — 99.99% of all ids. Only
  10 distinct values exist at all; the rest appear four times or fewer.
- **field C has 118 distinct values** game-wide, the common ones all `A0`–`A7`.
- **None of PyNifly's generated namespaces appear anywhere in vanilla** — not
  `B2A1B27E:6CCDA1BF`, `2AF5882A:32F70D8D`, `9CFCFDD9:B4060A78` or `782A2915:04B7C816`,
  in either field.

`_id_namespace(filename)` hashes the material path into 64 random-looking bits, landing
outside the space the database recognises. **This is the bug** — see Phase 0.

### What shipped mods actually do

| mod | packaging | form | renders |
|---|---|---|---|
| Lupus | loose | derived | yes |
| Felid | BA2 | derived | yes |
| vanilla | CDB | derived (authored) | yes |
| PyNifly today | loose | **flat** | no |

Packaging is a red herring: Lupus ships loose and works. Not one shipped material in either
mod is flat. Also worth knowing before designing custom-material features: **Felid does not
customise eye materials at all** — its `left_eye.mat` is md5-identical to vanilla's
authored file, and none of its eleven eye materials reference a single Felid-specific
texture.

## Blender representation

### Requirements

1. The node tree must still show **what renders** — the effective material after inheritance.
2. It must be possible to tell, per element, **what this file owns and what it inherited**.
3. Parents must be **read**, not assumed: they carry properties that change the Blender
   representation (the shader model itself, blend modes, texture slots).
4. Export must write **only what this file owns**, in derived form.
5. A user must be able to *add* a local override to an inherited element, and to *remove*
   one so the element falls back to the parent.

### Recommended scheme: effective tree + provenance + a read-only base group

Three parts. The first two are the substance; the third is what makes it legible.

**(a) Resolve the chain on import.** A new `sf_matchain` module resolves `Import` targets
recursively and merges parent → child into one *effective* material, keeping for every
object and every component the **origin** — which material in the chain last set it. Search
order for a parent: loose file tree → the mod's own BA2 → `materialsbeta.cdb` (we already
have `pyn.sf_cdb`). Resolution failures are reported, never silently flattened.

**(b) Provenance on every node and property.** The node tree is built from the effective
material exactly as today, so the look is unchanged and Bad Dog's "the node tree is the
material" principle holds. Each node gains:

| property | meaning |
|---|---|
| `pyn_sf_origin` | the material path this node's object came from, or `<local>` |
| `pyn_sf_owned` | the set of component keys **this** file sets (the override delta) |

A node whose `pyn_sf_origin` is a parent and whose `pyn_sf_owned` is empty is purely
inherited and exports as a bare placeholder (id + Parent + Edge + `CTName`) — which is
exactly what 49,276 vanilla objects are.

Editing a value adds its key to `pyn_sf_owned`. A "Revert to inherited" operator removes
it. The UI shows inherited values greyed with the source material named, local values
normal — the same affordance Blender uses for library overrides, which is the idiom users
already know.

> **[BD] How is this enforced? Does Blender let us discover value edits and grey out
> inherited values, or does the user have to edit these properties?**
>
> Blender gives us **no general "this value was edited" signal**. `update=` callbacks exist
> on our own `PropertyGroup` properties, so typed scalars and flags can self-mark — but the
> things users actually edit most (a node socket's `default_value`, an image datablock on a
> Texture node, a link being re-routed) have no per-property callback. The only generic hook
> is `depsgraph_update_post`, which tells you *something* changed, not what.
>
> Nor can inherited values be greyed out: node sockets draw themselves, and we cannot make
> an individual socket read-only. Greying is available only in our own panels, over our own
> properties.
>
> So the owned-set is **computed, not tracked**. At import we keep a snapshot of the
> inherited values (already implied by the resolver). At export we diff the current tree
> against that snapshot: anything that differs is owned. No live tracking, nothing to keep
> in sync, and it survives the user restructuring the tree — same reasoning that made the
> node tree authoritative in the first place.
>
> The one case a diff cannot see is **"I deliberately set this to the same value the parent
> has"**, which matters when the parent might later change. For that, and only that, an
> explicit per-node **Override** toggle in the `SF Layer` / `SF Blend` panel forces a value
> into the owned-set. Automatic for everything ordinary, explicit where intent cannot be
> inferred.
>
> ~~Practical consequence: the snapshot must be stored per node, so export can diff without
> re-resolving the chain.~~ **Superseded — see below.**

[The above makes sense - but if we have pyn_sf_origin saying where a value originally came from and pyn_sf_override saying "regardless of where it came from it should be considered as part of this material now", maybe we should reconsider doing the diff on export (below). Instead of stashing the values we read on import, we could use pyn_sf_origin to find the current value in the external file on export - if it is the same and pyn_sf_override is not set, it's an inherited value. The set of pyn_sf_origin values is the set of material this material inherits from. What do you think? - BD ]

> **Agreed — resolve at export, don't stash.** And there is a stronger argument for it than
> the one above: **export has to resolve the chain anyway.** It needs the parent's object
> ids (inherited objects keep them verbatim) and it needs each object's container to emit
> `Edges`, which provably cannot be derived from local references. Once the resolver has run
> for those two reasons, a stored snapshot is redundant data whose only distinctive property
> is that it can go stale. Drop it.
>
> Three consequences worth writing down:
>
> - **`pyn_sf_origin` becomes display-only.** The export decision needs just the *effective*
>   inherited value — one value, after the merge — and `pyn_sf_override`. Which ancestor it
>   came from matters to the user, not to the writer. Keep it for the UI and for the `SF
>   Base` grouping; don't make correctness depend on it.
> - **Keep `Import` stored explicitly.** It is tempting to derive it from the set of origins,
>   but a declared parent that happens to contribute no surviving value would vanish from
>   the list, and with 7,063 materials carrying 2–7 entries the *order* matters too
>   (open question 3). Origins corroborate `Import`; they don't replace it.
> - **It changes the semantics when a parent changes**, and this is the real trade. Say the
>   template had albedo = A, you imported and never touched it, and the template later
>   becomes B. Resolve-at-export sees your tree holding A against a parent saying B, calls
>   it *owned*, and writes A. Stash-and-diff would have called it inherited and let the
>   material silently become B. Resolve-at-export is therefore **what-you-see-is-what-you-
>   get**, which I think is the right default — a material should not change under the user
>   because Bethesda patched a template. The cost is that a stale import pins values it
>   didn't mean to. Re-importing is the cure, and the UI can say "3 values differ from the
>   current parent" to make it visible.

**(c) The chain as nested `SF Base` group nodes — one per level.** Per the brief at the top
of this plan, the three natural levels are made visible rather than implied:

```
material node tree                     <- this .mat: the objects it owns
  └ SF Base: ShaderModels/Eye1Layer    <- the shader model: layer/blender skeleton,
      │                                   ShaderModelComponent, EyeSettingsComponent
      └ SF Base: Root/LayeredMaterials <- the root template: defaults for everything unset
```

[Or, alternatively, these SF Base group nodes could themselves be the cached values we read on import. I'm still inclined towards doing the diff on export, though. -BD]

> **Agreed, and with resolve-at-export settled these groups must NOT be the comparison
> basis.** They are a *view*: rebuilt from the resolver, never trusted. If they were the
> cache they would inherit every problem the stashed snapshot had, plus a new one — they are
> shared datablocks, so one material's stale copy would be every derived material's stale
> copy. Rebuild them on import and whenever the chain is re-resolved.

One node-group datablock per parent material, named for it, **shared** by every material
that derives from it — open `SF Base: ShaderModels/Eye1Layer` once and you are looking at
the same datablock the other eye materials use. A chain of three nests two deep, and the
survey says chains are almost always exactly this deep.

They are **read-only and never exported**: rebuilt from the resolver on import, and export
walks only the outermost level. Editing inside one would silently change every material
deriving from it, so the UI must refuse it.

This is what makes "what came from where" visible at a glance instead of being a property
you have to think to look at.

[Downside: inherited vs local is represented as properties on the nodes. That's easy to overlook. The explicit SF Base group node helps to mitigate this. Not a blocker; still worth implementing this approach and seeing how it works out. -BD]

### Alternatives considered

- **Nested groups as the authoritative structure** (edit the parent through the child).
  True to the format, but inheritance here is per-object component override, not a pipeline
  stage, so it maps badly onto node sockets and makes ordinary edits awkward.
- **Import flattened, export flattened** (today). Cheapest, and the CK accepts it. Rejected:
  it does not render in game, which is the whole point.
- **Import flattened, export derived by diffing against the parent at export time.** No
  Blender-side model needed, and much less work. **Rejected** — BD: "it hides the true
  structure of SF materials files, so it fails to teach the user what they're really dealing
  with", and the brief explicitly does not trade fidelity for a smaller change. Note that
  the *diff mechanism* survives anyway as the way the owned-set is computed (see (b)); what
  is rejected is diffing as a substitute for representing the hierarchy.

## Phases

**Phase 0 — prove the target form in game. ✅ DONE 2026-09-24, and it found the cause.**

A ladder of variants, each one step further from vanilla's authored `left_eye.mat` /
`right_eye.mat`, deployed at the fox path with the nif pointing there:

| variant | change from vanilla's authored file | in game |
|---|---|---|
| **v0** | byte-for-byte copy, at the fox path | **renders** |
| **v1** | v0 + the iris `FileName` → a fox texture (added a slot-0 override on the right eye, which inherits its iris) | **renders** |
| **v2** | v0 + in-file `res:` ids moved to a new **namespace**, refs and `Edges` remapped consistently | **FAILS** |
| **v3** | v0 + only the ids' **first field** changed, namespace kept | **renders** |

Read together:

- **The derived form is sufficient**, and a content override on top of it is fine (v1).
- **Re-namespacing the ids is what breaks the material** (v2) — and
  `sf_materials._renamespace` does exactly that on every export. Its docstring argues the
  opposite ("a duplicate id collides with the original"); **v0 disproves that**, and Felid
  ships `left_eye.mat` md5-identical to vanilla's at a Felid path and it renders.
- **New object identities are legal** inside a namespace the database knows (v3). So a
  derived material *can* mint objects — PyNifly can add a layer — as long as it does not
  invent a namespace.

**The rule for export:** never invent a namespace. Inherited objects keep their id verbatim;
new objects allocate an unused first field **within the parent's namespace**. That is what
v3 does and roughly what Felid's `child_left_eye.mat` does (`0005F669:A2A909D2` — a fresh B
sharing vanilla's C).

**Phase 1 — the resolver.** `sf_matchain`: resolve `Import` chains against loose / BA2 /
CDB, merge to an effective material, record origins. No Blender. Testable on its own
against the authored tree.

**Phase 2 — import through the resolver. ✅ DONE 2026-09-24.** The node tree is built from
the *effective* material rather than the raw file, and the chain (`pyn_sf_chain`) and
provenance (`pyn_sf_origin`) are recorded as it is built. No `pyn_sf_owned`: with
resolve-at-export settled, the owned set is computed at write time, and only the explicit
`pyn_sf_override` flags will be stored. The rendered result did not change — what changed is
that inherited values now arrive at all.

`pyn_sf_origin` is `{'origin': <material>, 'fields': {<field>: <material>}}`, keyed by node
kind where one node stands for several `.mat` objects. `fields` lists only what disagrees
with the object's own origin, so an object inherited whole costs one string. It goes on the
material (the root object), each SF Layer node, each SF Blend node, and each settings
component node — the last asked of the chain per component rather than read off the object,
because the root's *record* is always local while the components hanging off it usually
aren't.

What it measures on authored `left_eye.mat`: every one of its 15 reachable objects is local,
and 35 fields of the root plus a scatter on the layer objects come from `Eye1Layer.mat`
through their `Parent` chain. An object-level answer alone would have called the whole
material local — which is precisely the flat file that renders nowhere.

**Phase 3 — derived export.** ⏳ The writer is done and tested (`sf_matchain.derive`); it
is not yet wired into the exporter.

`derive(doc, parents, imports)` is the inverse of resolution: it takes the complete material
the node tree holds and removes everything the parents already say. Correctness is not
textual -- the test is that resolving the result produces the same effective material -- but
on authored `left_eye.mat` the output is **identical to Bethesda's own file**: same 15
objects, same 30 components, same ids, Versions, Parents and Edges. Across 249 derived
vanilla materials it reproduces the authored form except where the authored file redundantly
restates what its parent already says.

Five format facts came out of diffing against authored files, each of which we had wrong:

| | |
|---|---|
| `Edges` index with **`EdgeIndex`**, not `Index` | 3,438 of 3,438 |
| an object with nothing to say has **no `Components` key** at all | 498 of 3,938 objects |
| component **`Version`** belongs to the DECLARATION, not the material | the compiled database carries none on any component; vanilla ships `MRTextureFile` at v1 and v2 |
| a nested typed wrapper keeps its `Type` **and `Version`** when anything inside survives | |
| a **partial** typed value is legal -- an `XMFLOAT4` may state `x,y,z` and inherit `w` | 24 in a 700-material sample, and the inherited `w` is 1 in one case and 0 in another |

**Wired into export.** `recover_sf_material` recovers the declared `Import` list off the
material; `write_sf_materials` resolves it with `sf_matchain.resolve_parents` (one synthetic
document importing all of them, so 2-7 parents merge by the same rules a real material's
would) and hands the chain to `write_mat`, which derives against it. A material with no
`Import` is written complete, which is the from-scratch author's problem.

Gone from that path: **`_renamespace`** -- the Phase 0 bug, and the cause of
`project_sf_mat_renamespace_same_path` -- and the template-patch fallback with it. Whatever
is at the path is replaced outright; every node already carries the identity and components
of the object it came from, so nothing needs reading off disk.

Import and export now ask for search roots through one function, because they must get the
same answer: a parent findable on import but not on export would silently turn inherited
values into owned ones.

**✅ VERIFIED IN GAME, 2026-09-24.** Bad Dog imported the vanilla eye, changed its texture,
exported, and it renders correctly in game. That is the whole chain -- resolve on import,
node tree, recover, derive, write -- doing the job end to end, with PyNifly writing the file
rather than a hand-edited ladder. It closes the question the previous plan could not answer.

Three things here are load-bearing and each can produce a file that parses and renders
nowhere:

- **Ids.** Inherited objects keep their id verbatim; new objects take an unused first field
  **inside the parent's namespace**. Never mint a namespace — that is the Phase 0 bug.
- **Edges.** Emitted from the resolved chain, not from local references: 1,138 of 21,302
  sampled objects are contained by something they do not reference locally (see `Edges`
  above).
- **No `ShaderModelComponent`** on a derived root. It belongs to the template, and 99.7% of
  authored materials omit it.
- **The root's `LayerID` / `BlenderID` list is written in full, never inherited.** It is
  authoritative, not additive: that is how a derived material drops a layer (open question
  7). Inherit it and a deleted layer comes back. **The RESOLVER had this wrong too**, and it
  was found while building the writer -- see open question 7.

**Phase 4 — the `SF Base` group node and the UI. ✅ DONE 2026-09-24.**

- **`SF Base` groups.** One shared node-group datablock per inherited material, named for it,
  nested one level per step up the chain, each holding the layers, blends and settings that
  level supplies. Rebuilt from the resolver on every import; never read back. Export walks
  the material's own tree only, so editing inside one cannot corrupt a written file -- it can
  only make the view wrong, for every material sharing it. Chain levels that live only in the
  database are rebuilt from it (`sf_matchain.resolve_level`) rather than read as missing
  files.
- **A node-editor panel** (`PYN_PT_sf_provenance`, sidebar > Item) showing the chain, and for
  the selected node which material set each field, inherited values greyed.
- **Claim for this material** (`pynifly.sf_claim_node`) sets `pyn_sf_override` on a node, and
  `derive(keep=...)` then writes that object whole. This is the one thing about ownership
  that has to be STORED: a value deliberately set to what the parent happens to say is, by
  construction, indistinguishable from never having touched it.

**Not done: revert-to-inherited.** It needs a socket-to-`.mat`-field mapping that only the
settings components have, so the button would be a lie on every other node. Re-importing is
the honest cure until that mapping exists.

**Greying inherited values in the shader graph itself remains impossible** -- node sockets
draw themselves and cannot be made read-only. The panel is where provenance can be shown,
which is why it is a panel.

**Phase 5 — docs. ✅ DONE 2026-09-24.**

`docs/starfield_materials.md`: the inheritance story, where a value came from (`SF Base`
groups and the panel), derived export, and a rewritten **Material identity** section. The
"known issue: re-saving rewrites the `res:` ids" section and the open design question that
went with it are gone — neither case wants new ids, so there was nothing to decide. The
"every node needs a `Parent` into a Root template, a `CTName` and a unique `res:` ID" rule of
thumb is corrected in place: 94.4% of vanilla child objects parent to a `res:` id, and 67,234
objects carry no `CTName`.

Bethesda Library, `game-specific/starfield/materials.md`: inheritance and the three merge
rules, resource ids as a registered space with the in-game ladder, `Edges` as containment,
and component versions. It had said a complete loose graph works; it does not. Also noted
there that NifSkope's exporter mints fresh resource ids, which is the same failure by another
route.

(The fourth item once listed here — that `00StarfieldAssets` is a flattened dump — stopped
being true when Bad Dog replaced that tree with the authored one.)

## Tests

The existing material tests encode the flat form as correct. They must change.

| test | change |
|---|---|
| `TEST_SF_MAT_GAME_VALID` | **Rewrite.** It asserts every node has a `Parent` into a Root template, a `CTName`, and a unique `res:` id. Measured: 94.4% of children parent to a `res:` id, 67,234 have no `CTName`. It is asserting the wrong rule and would fail every authored vanilla material. |
| `TEST_SF_MAT_PARSE` / `_WRITE` / `_PRESERVES_TEMPLATE` / `_COMPONENTS` / `_BUILD_FROM_TREE` | Extend to derived input; keep flat coverage only as a legacy-read case. |
| `TEST_SF_RACECHECK_SHADER_SETTINGS` (new, this session) | **Make inheritance-aware.** It reads the root's `ShaderModelComponent`, which 99.7% of authored materials don't have, and would wrongly pass a derived material that inherits both model and settings. Needs the resolver, and its fixtures move to the authored tree. |
| `TEST_SF_MATCHAIN_ORIGINS`, `TEST_SF_MAT_PROVENANCE` (new, Phase 2) | Pin provenance at both levels: the resolver's `origin_map()` / `component_origin()`, and the stamps the node build leaves on a real derivation. |
| `TEST_SF_MAT_ROUNDTRIP`, `TEST_SF_MAT_COMPONENT_ROUNDTRIP`, `TEST_SF_HEAD_MATERIAL` (Blender) | Round-trip must now preserve the chain and the owned-set, not just the flattened content. |
| `TEST_SF_CDB_READ` | Unchanged, but see the asset-tree note — it needs `materialsbeta.cdb` to survive. |

**Fixtures.** The nine `.mat` files under `tests/tests/SF/materials/` are flattened copies.
(Phase 2 added two authored ones beside them — `Faces/left_eye.mat` and the
`Layered/ShaderModels/Eye1Layer.mat` it imports — so `TEST_SF_MAT_PROVENANCE` has a real
chain to resolve. The flattened nine stay until Phase 3, because the round-trip tests
currently encode the flat form.)
Replace them with authored equivalents and add at least one genuine derivation with a
parent that is only in the CDB, so the resolver's hardest path is covered. These stay real
game assets, not synthetic fixtures.

**New tests.** Chain resolution depth and multi-`Import` merge order; origin/owned
correctness; derived export byte-compared against a hand-verified target; the `Edges`
ownership rule; a flat file still reading correctly (back-compat).

**In-game check per phase.** Per the previous plan's Risks — a census diff proves nothing
renders, and this saga is the proof.

## The asset tree

`00StarfieldAssets\materials` should be replaced with the contents of `Starfield Materials
Loose`. It is 10,530 flattened materials versus 48,505 authored ones, and it has actively
misled this work.

Two things to get right when doing it:

1. **`materialsbeta.cdb` (105 MB) lives in `00StarfieldAssets\materials` and is not in the
   Loose tree.** `TEST_SF_CDB_READ` reads it at `TT.SF_ASSETS/materials/materialsbeta.cdb`.
   Preserve it, or move the test's path.
2. Only two tests reference `TT.SF_ASSETS/materials` today (lines 1093 and 2441 of
   `pynifly_tests.py`), so the blast radius is small — but both are affected, one by the
   content change and one by the `.cdb`.

Worth keeping the old tree somewhere as `00StarfieldAssets-cdbdump` rather than deleting:
it is the only local record of what the compiled database flattens to, which is useful when
reasoning about what the engine actually sees.

## Open questions

1. ~~**Is the derived form sufficient?**~~ **Closed by Phase 0.** Yes, and the cause of the
   failures was `_renamespace`. See Phase 0 for the ladder.
2. **Which namespace do new objects go in?** v3 proves a fresh first field inside an
   existing namespace works. Untested: whether *any* `0005xxxx`/`0006xxxx` namespace is
   accepted or only ones already in the database. The safe implementation — reuse the
   parent's namespace — sidesteps this, but it is worth knowing, because it decides whether
   a mod can ever own a namespace of its own. Also unknown: how to pick a first field with
   no risk of colliding with an unrelated object already in that namespace.
3. **Multiple `Import`** (7,063 materials): what is the merge order, and do later entries
   win? Untested.
4. **`BSMaterial::MaterialParent` edges** (523): a second edge type we have never written.
   What owns them?
5. ~~**Component `Version` fields**~~ **Answered — it belongs to the declaration, not to
   the material.** `materialsbeta.cdb`, which is the engine's own composed form, carries
   **no `Version` on any component**. So it describes how a document wrote its own
   declaration: a material that restates a component without a version does not inherit its
   parent's. `sf_matchain` now tracks which material set it and writes it back only there.
   Tree-wide, 3,054 of 11,934 sampled components carry one; `MRTextureFile` ships at v1 and
   v2 and `TextureSetID` at v1 and v3, so it cannot be hardcoded.
6. ~~**Should PyNifly author custom eye materials at all?**~~ **Withdrawn — badly phrased.**
   PyNifly writes whatever the user asks for, custom eye materials included; that is not a
   question for this plan. What remains is a *documentation* note: no shipped race
   customises its eye materials, eye colour comes from the `EyeColor` AVMD group, and an
   author reaching for a custom eye material may be solving the wrong problem. Belongs in
   the Bethesda Library, not in PyNifly's behaviour.

7. ~~**How does a derived material express a DELETION?**~~ **Answered — by re-declaring a
   shorter reference list on the root.** Measured over 5,129 single-`Import` materials whose
   parent is on disk: 5,126 declare exactly as many `LayerID`s as their parent, **1 declares
   fewer, 1 declares more**. The example:

   ```
   ExoticsCrystalShard01_Green_Glow.mat   root: BlenderID×1, LayerID×1   6 objects
     Import -> ExoticsCrystalShard02_Blue_Glow.mat
                                          root: BlenderID×1, LayerID×2  11 objects
   ```

   The child re-points `LayerID[0]` at its own layer object and simply never references the
   second; the dropped objects are not mentioned at all. So the root's reference list is
   authoritative, not additive — which is what makes both deletion and addition work.

   **Consequence for Phase 3:** export must always write the root's full `LayerID` /
   `BlenderID` list from the node tree, never inherit it. Getting this wrong is silent —
   inherit the list and a deleted layer returns; write a partial list and a layer vanishes.

   **The resolver had it wrong as well, and that was an IMPORT defect** (found 2026-09-24
   while building the writer). It merged the list per `(type, index)` like every other
   component, so a material declaring one layer over a three-layer ancestor imported with
   three. Measured against `materialsbeta.cdb` — the engine's own composed form — over 2,000
   materials: **1,984 agreed before the fix, 1,995 after**, with none broken.

   Two further points the measurement settled:

   - **Layers and blenders are ONE declaration.** The most-derived document that states any
     of the list states all of it. A material declaring `LayerID[0]` alone over a chain with
     two blenders composes to *no* blenders, while one declaring `LayerID[0]` +
     `BlenderID[0]` keeps its blender — 47 vanilla materials are the second case, and
     treating the two types independently gets every one of them wrong.
   - **A blender can outnumber the layers it could composite**: 47 materials compose to one
     layer and one blender, so "blenders are capped at layers − 1" is false. That guess cost
     a measurement to disprove.

   Five materials in 2,000 still disagree, all declaring `LayerID[0]` with no blender; two
   want the parent's blender kept and three compose to no layers at all. Not yet explained.

## Risks

- ~~**Phase 0 may fail.**~~ It didn't; the target form is proven and the cause is known.
- **Namespace allocation** is the one place export can still produce a file that parses and
  does not render. It needs an in-game check of its own, not just a round-trip test.
- **Invasiveness.** Provenance touches import, export, the node tree and the UI. Accepted
  per the brief — fidelity over minimising change — but it means no partial landing: a
  half-migrated exporter that writes derived ids with flat structure is worse than either.
- **The CDB dependency.** The chain terminates in the compiled database, so import now
  depends on `pyn.sf_cdb` and on the user having the `.cdb`. Needs a graceful degradation
  story: what does import do when the chain cannot be resolved?
- **Back-compat.** Materials imported under the flat model carry no provenance. Re-import,
  or treat everything as locally owned.
