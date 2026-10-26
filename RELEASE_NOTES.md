# PyNifly 30.1.0 Release Notes

**Starfield cloth physics in Blender**

Hair, tails, skirts and coats that move with Starfield's cloth physics can now be seen,
edited, and built from scratch in Blender. See
[Starfield cloth](https://github.com/BadDogSkyrim/PyNifly/blob/main/docs/Starfield_Cloth.md)
for how.

## Starfield cloth

- **Cloth imports as pictures you can edit.** Under the `BSClothExtraData` empty you get the
  simulation mesh (its vertices are the particles that move), the collision shapes that
  keep it off the body, and the bone planes. Settings such as gravity, damping and
  iterations are Custom Properties on the sim mesh; per-particle and per-edge values are
  attributes.

- **Export writes what you see.** Move, add or delete particles; change which are pinned;
  add or remove links; set the bend stiffness of each edge; paint skin weights; move,
  scale, mirror, copy or delete collision shapes. Export builds the cloth data afresh
  from the pictures every time.

- **Collision shapes are read from their meshes.** Edit them like any mesh: scale, apply
  transforms, mirror one to the other leg with a negative scale. 

- **Bone planes keep cloth on one side of a plane that follows a bone.** Vanilla uses them
  to keep hair out of the face. A plane on `Root`, facing up a few centimetres above the
  feet, works as a floor and keeps a tail out of the ground. Starfield ignores Havok's own
  ground collision, so a plane is the way to do it.

- **New cloth from scratch.** Add an Empty named `BSClothExtraData` under the nif's root
  and model a mesh under it: pin the particles that follow the body, and give every
  particle a bone weight. Export fills in the rest with vanilla's usual values and leaves
  them on the mesh, so you can see and change them. Cloth can drive bones no skeleton
  has: name them whatever you like, give them parents in the armature, and weight the
  render mesh to them.

- Keep sim meshes simple. A flat strip works well. A closed tube twitches whatever the
  settings.

- Vertex groups whose names start with `*` are ignored on export, like `*` shape keys,
  so you can keep selections on a mesh.

## Starfield

- **Every LOD imports and exports.** A Starfield shape can hold up to four LODs. Import
  brings in one object per distinct `.mesh`, named `<shape>:LOD0`, `:LOD1-2` and so on,
  with the higher LODs hidden. Export gathers them back into one shape. To add LODs to
  your own mesh, name the objects `Rock:LOD0`, `Rock:LOD1`. Previously re-exporting a
  vanilla mesh dropped its LODs.
  - Some vanilla meshes (the hands, about a fifth of clothing) also carry LODs inside the
    `.mesh` file. Import warns about these; they aren't imported, and export drops them.

- **Clothes skinned to cloth bones import correctly.** The Collector outfit and others
  came in scrambled.

- **Crowd heads keep their eye positions.** Vanilla crowd heads carry a `BoneTranslations`
  block that places the eyes; it was dropped. It now imports as an Empty with a marker
  per eye and exports back. Put the eye bones at the eyeball centres and the markers on
  the eye bones, and the eyes turn in their sockets. For a new head, copy the Empty from
  an imported vanilla crowd head.

- **Facebones armature flag.** An armature's *Facebones armature* setting (Yes / No /
  Auto on the PyNifly Skeleton Export panel) says whether it's the face rig. Auto decides
  by bone names, as before. A crowd head whose mesh also carried the chargen face rig
  exported its companion skinned to the wrong rig and was invisible in game; set the
  crowd head's armature to Yes.

- **Crowd head morphs.** A crowd head (Starfield Morphs > crowd) writes only the
  performance `morph.dat`, with vanilla's crowd keys; each right-side key is merged into
  its left.

- **Body types.** Each `_`-prefixed shape key writes its own nif and now its own `.mesh`
  (they all shared one, so every body type came out as the last). A shape key named just
  `_` writes the plain nif, so `_`, `_thin` and `_overweight` give vanilla's names.

- Shape keys starting with `*` or `_` are never written to a `morph.dat`.

- A morph path naming a folder gets `morph.dat` added.

- An empty `morph.dat` is not written: a head part pointing at one crashes the Creation
  Kit. You get an error instead.

- Each loose `.mat` is written once per export, not once per nif.

## General

- **Exporting a selected shape brings its whole nif.** Select one shape under an imported
  nif and export writes the nif's root and everything visible under it, with the root's
  game and file name.

- **A shape parented to another mesh exports without that mesh**, under the mesh's parent at
  the same position, with a warning.

- **Hidden objects are never exported**, whichever way they're hidden: eye icon, disabled
  in viewports, or in a hidden or excluded collection.

## Starfield Convenience Scripts

*In github, not the kit*

- **New: `sf_tintbake.py`** bakes crowd-head variants. A crowd head has one texture, so the
  variety chargen gets from skin tones and tint layers has to be baked into separate
  heads. From a recipe, it picks a sample of tone, tint and eye combinations and writes
  each variant's texture, material and nifs (all body types, with companions), and a
  manifest for building the plugin. It also bakes tails to match each tone, teeth and
  beard options, with optional weights. See `docs/Crowd_Race_Instructions.md`.

- `sf_racecheck.py`:
    - Crowd races are checked through their NPCs' outfits: every head and tail nif,
      `.mesh`, material, texture and companion. A companion skinned to face bones fails;
      the crowd skeleton has none.
    - Tint groups must resolve to a group or a texture.
    - Face textures must all be one size, or the face goes black on the first tint
      change.
    - Every head part's morphs are checked; an empty `morph.dat` fails.
    - Playable head parts missing from the chargen option lists are warned about: chargen
      never offers them.
    - The official plugin list now matches the game's, so load-order form IDs are right.

## PyNifly-level fixes

*For script writers*

- **Starfield bone lists keep every slot.** A skin whose cloth bones have nodes in the nif
  returned only those bones, so weights and binds landed on the wrong bones. Fixed in nifly.

- `BSGeometry.get_shape_skin_to_bone(name)` works for Starfield; it always returned None.
  New: `add_mesh`, `set_weights_per_vertex`, `set_vert_weights(..., slot=)` for LOD slots,
  and `BoneTranslations`.

- New modules for Starfield cloth: `havok_tagfile` and `havok_graph` read and write Havok
  2019 tagfiles; `sf_cloth` reads a cloth; `sf_cloth_build` builds one.

## Known limitations

- **Some Starfield accessories still import out of place**: face-bone accessories (cap
  logos, eyepatches) and spacesuit backpacks, whose bones aren't in the reference
  skeleton.

- Editing compressible links and volume constraints on cloth isn't supported; they're
  kept as they are.

# PyNifly 30.0.0 Release Notes

**hkxcmd is gone**

PyNifly no longer ships or uses hkxcmd. All HKX import and export is native now. 

## Animation

- **hkxcmd is no longer used or shipped.** HKX export was the last thing that needed it.
  PyNifly reads and writes Skyrim LE/SE (hk_2010, binary or XML) and FO4 (hk_2014) HKX
  files itself. Any other HKX version gives a clear error instead of going through
  hkxcmd. NOTE that KF export is still available, so you can run through hkxcmd yourself 
  there's a need.

- **Animations on an armature imported from a skeleton nif export natively** (#439).
  These used to go through hkxcmd, which ignored XYZ (Euler) rotation keys, so every frame
  came out with the same rotation. It also dropped the last frame and wrote unnamed tracks.
  Now the animation exports against the armature's **Reference Skeleton** (an HKX
  skeleton, Skyrim or FO4), with one track per skeleton bone. Bones the armature doesn't
  have hold the skeleton's reference pose. The skeleton decides FO4 vs Skyrim; for Skyrim,
  the LE/SE setting decides. If there's no reference skeleton, you get an error telling
  you to set one. Alternatively, import the skeleton.hkx instead of the skeleton nif.

- **The NIF importer's HKX skeleton file option reads .hkx natively**, and FO4 skeletons
  work there now too.

- **HKX import sets the scene frame rate to the animation's** (#386). Animations exported
  at Blender's default 24 fps used to come out 25% long.

- **Long HKX animations keep every frame** (#386). Animations over 256 frames were off by a
  frame at each 256-frame block, with frozen frames at the block boundaries and the last
  frames lost. Fixed on import and export.

- **Skyrim HKX float tracks round-trip** (#386). Visibility and fade switches (hkVis,
  hkFade) import as animated properties on the armature and export back.

- **Animated scale in nif animations imports and exports** (#429), for objects and bones.
  Nif scale is uniform; if the X, Y and Z scale differ, export warns and uses one value.
  FO4 HKX already kept scale.

## Starfield

Starfield was extremely careless in creating body part nifs - may have spurious pose 
locations that make it difficult to line them up along seams. Best to import the skeleton
first, then import body parts with that selected.

- **Meshes imported onto a selected armature line up with it.** Importing female hands
  onto the body's armature, or eyes onto the head's, used to leave them slightly off
  (hands a few degrees, eyes drawn toward the centre of the head). If you select nothing,
  import works as before.

- **Skeletons with added bones import in place, at normal size.** SF Extended Skeleton's
  tail and ear bones now import correctly. Any converted skeleton now has normal-sized
  bone shapes in pose mode.

- **Alpha settings can take opacity from vertex colors.** The alpha component's "use
  vertex color" setting and its channel (red or alpha) are imported, previewed and
  exported. The channel is whatever is plugged into the component's Vertex Color input.
  Note: Using vertex alpha on a skin material makes the whole shape invisible in game (see
  `sf_racecheck` below). Use an opacity texture there.

- **The alpha and emissive components drive the preview live.** The alpha component
  computes the alpha (opacity, optionally times vertex color, alpha-tested against the
  threshold). The emissive component computes the emission (emissive color times tint, on
  only when Emissive Enable is set). Change their inputs and the viewport follows.

- **A layer's textures are whatever is plugged into it.** Material export found textures
  by tags it set on import, ignoring the wiring. So an image node you added and plugged
  into a layer was left out of the .mat, and one you unplugged was still written. Now the
  wiring decides, and an unplugged texture is removed from the material.

- **A head part's morphs are written once.** A head part with a `_facebones` companion
  wrote its morph.dat files twice, once for each nif.

## General

- **Effect shaders with the SPECULAR flag keep their material.** These imported with no
  material at all and exported as lighting shaders. Now the shader and the flag
  round-trip.

- **"Import mesh only" imports the mesh's own data**: UVs, vertex colors, smooth shading
  and custom normals. It still leaves out the armature, parenting, bone groups,
  partitions, LOD groups, material, collision and animation.

## Starfield Convenience Scripts

*In github, not the kit*

- **New: `uv_transfer.py`.** For when you join separate meshes (head, eyes, hands...) into
  one and give it new UVs, e.g. for a crowd head. It maps the joined mesh's UVs back to
  the original parts in Blender, then paints each part's textures into the new layout
  outside Blender. It handles one texture type at a time and can fill a part with a flat
  colour instead. Normal maps are rotated to follow each UV island. Faces that don't
  match any part are selected in Blender so you can see them.

- `sf_racecheck.py` has new checks for:
    - hair and beard head parts whose mask (NAM3) isn't registered in the follicle mask
      list, or points at a texture that isn't there. A .dds named like the mask does
      nothing on its own.
    - a material that exists neither as a loose file nor in the game's material database.
    - an unskinned shape in a head-part or body nif.
    - a skin material that takes opacity from vertex colors. The whole shape is invisible
      on a character, even though the Creation Kit draws it.
    - a skin addon whose Is Skin / Is Skin Hands flag doesn't match its slot. The flag
      picks the skin-tone texture, so a tail flagged Is Skin Hands takes the hands' colour.
    - The missing-phenotype-maps warning now names the missing files.

- `sf_texconv.py` converts additional layers of a texture set: `_opacity`, `_transmissive`,
  `_height` and `_id` (BC4) and `_emissive` (BC1 sRGB). They used to be skipped silently.

## PyNifly-level fixes

*For script writers*

- **`shape.textures` is writable** (#436). Assign a slot and it's written to the nif, for
  lighting and effect shaders. An unknown slot raises KeyError. FO4 textures that come
  from a material file are read-only (edit the material instead). `set_texture` still
  works to write the texture slots in the nif (for whatever good that does). Side fix: the
  lighting shader's Greyscale slot is now written; it was dropped.

## Known limitations

- **Skyrim HKX animated scale isn't supported.** FO4 HKX and nif animations keep scale.

- **Path animation is still not imported**, and some vanilla FO4 precombined meshes still
  crash on import (see 29.1.0).


# PyNifly 29.1.0 Release Notes

**Animated bones and animated collisions**

Named animations that move NiNode elements now import and export. Vanilla banners, the FO4
animatronics, and anything else whose animation drives the bones of a skinned mesh used to
come in with the animation dropped and a pile of "Target of controller not found"
warnings. Re-import any of these you've worked on.

## Animation

- **Animations on bones import as an armature.** A nif's named animation (a
  NiControllerManager sequence) that moves NiNode elements assembles them into an armature
  on import. Export re-creates the nodes from the armature bones, preserving round-trip
  fidelity (cf. Skyrim's banners and FO4's animatrons).

- **A NiControllerManager's second animation starts from its own beginning**, not from
  wherever the first one left off.

- **Animated objects with collision play their animation.** The collision follows the
  object instead of pinning it in place. Static objects are unchanged, so physics previews
  still work. Formerly, the collision would lock the animated object in place (cf. doors).

## Starfield

- **Eyes preview correctly**: Starfield has a special "eye" material that pulls the iris
  from one texture, the sclera from aother - with the radius of the iris defined in the
  material. Import now mimics this setup in Blender.

## Starfield Convenience Scripts

*In github, not the kit*

- `sf_racecheck.py` no longer needs `--plugin`. Without it, it checks your whole active
  load order, so a plugin that only overrides a race defined somewhere else can be
  checked.

- `sf_texconv.py` handles `_metal` textures.

## PyNifly-level fixes 

*For script writers*

- **`NifFile.close()`**, or `with NifFile(path) as nif:`, frees a nif as soon as you're
  done with it. A dropped NifFile otherwise holds its memory until Python gets around to a
  full garbage collection, which in a long-running script may be never. 

## Known limitations

- **Path animation is not imported.** Some objects move along a spline path (the gear
  door's blowing papers, birds, catapult projectiles). They import without that motion,
  and export drops it. You'll get one warning naming them. Support is planned.

- **Some vanilla precombined meshes crash on import.** A handful of FO4 `PreCombined`
  nifs make the nif loader overflow its stack. Precombined meshes aren't meant to be
  edited, but don't try to import them.


# PyNifly 29.0.0 Release Notes

**Major update to how we handle Starfield materials**

Starfield materials have a layered, hierarchical structure. In past versions, we pretty
much ignored this and flattened the structure on import, and wrote the flat file on
export. Turns out, you can't do that - the result shows in Creation Kit but not in game.
So this version handles material templates correctly. 

This will break existing Blend files. Import a nif with the material you want to use for
the base, make a copy of that, and make your edits. On export you'll get something that
works. See the [Starfield
page](https://github.com/BadDogSkyrim/PyNifly/wiki/Starfield-Notes) of the wiki for
details.

## Starfield materials

- **Materials are read with everything they inherit.** Most Starfield `.mat` inherit from
  a template material and only state the *changes*. We now read the whole hierarchy and
  remember what was in the nif's material and what was inherited. The Blender node tree is
  still the consolidation of the hierarchy, so the look in Blender is correct.

- **Material hierarchy is preserved on export.** Only the changes in the Blender shader
  nodes are written to the shape's material.

- **Object IDs are preserved.** PyNifly used to re-generate the `res:` IDs in a material
  on every export. That was wrong.

- **`SF Base` group nodes show you what a material inherits.** One group per material in
  the chain, nested — your material, the shader-model template it derives from, the root
  template under that. 

- **A new "PyNifly Material Chain" panel** in the shader editor sidebar. For the selected
  node it shows which material in the chain set each value, so you can tell what is yours
  from what you inherited. "Claim for this material" forces a value to be written even
  where it matches the parent — for when you set it deliberately and want it to stay put
  if the parent changes.

- **Whatever is at the output path is replaced outright.** PyNifly no longer patches the
  file it is overwriting; every node carries what it needs, so nothing is read off disk.

- **Layer counts are correct on import.** A material that declares fewer layers than the
  material it derives from has *deleted* those layers. PyNifly used to merge them back in,
  so such a material imported with layers its author had removed.

- **Fewer surprises from the material database.** Set the **Starfield .cdb path**
  preference if you have not: the root templates every material eventually derives from
  ship only inside it, and without it the bottom of every chain is missing.

## Checker tool

- In the `scripts/` folder, `sf_racecheck.py` will review your race definition and look
  for errors, because this is all freakishly complicated. It's in github, not in the kit -
  get it directly from there if needed.

- Give it a race to check and it will walk head parts, chargen lists, skin tint layers,
  nifs, and materials, looking for disconnects. 

## Starfield head parts

- **`AnimationFlagExtra` values corrected**, and PyNifly no longer expects one on
  eyelashes — vanilla eyelashes carry no such block, and absence is legal.

## Known limitations

- **Blend modes are not composited.** Every `SF Blend` node passes the base layer through
  and composites only the normal map. A material whose layers combine *albedo* will not
  look right in Blender. It exports correctly; this is a preview limitation. We're not
  sure yet how the blending is supposed to work; once we figure it out we'll update the
  importer.

- **A material authored from scratch in Blender is written flat**, which is the form that
  does not render in game. Import a vanilla material and modify it instead. (You can also
  set all the properties to represent inheritance, but that's also freakishly complicated.
  If we can figure out a simpler way to do this - that works with Blender shader nodes -
  we will.)

- **No "revert to inherited" yet.** The panel shows you what you have overridden; putting it
  back means re-importing.

- The `Known limitations` from 28.3.0 below still stand.

# PyNifly 28.3.0 Release Notes

Fixes to **Fallout 4 nifs that include a posed skeleton** -- power armor furniture,
animatronics, animated doors. Some imported crooked and re-exported wrong. Re-import any
you have in a .blend; an old .blend keeps the old placement.

## Fallout 4 rigs

- Fixes to **Fallout 4 nifs that include a posed skeleton** -- power armor furniture,
  animatronics, animated doors. Some imported crooked and re-exported wrong. Re-import any
  you have in a .blend; an old .blend keeps the old placement.

- **Embedded animations play back correctly.** Attachment points stood still
  while the bones they belong to moved.

- **They export correctly.** Re-exporting resulted in a flattened skeleton stuck in
  the bind pose with unweighted bones missing. PyNifly now detects that a nif needs bones in a hierarchy on import, and remembers that setting for export.

- **New export option, "Export All Bones"** (armature ▸ PyNifly Skeleton Export). Writes
  every bone in an armature, not only the ones a shape is skinned to -- needed by files
  that use bones as weapon or camera mounts. Set for you on import when the nif needs it.

- **A nif holding both a `C-` and a `P-` connect point of the same name** no longer
  confuses the import.

## General

- **A nif with more than 100 connect points imports all of them.** Everything past the
  hundredth was dropped silently, so a round trip through Blender truncated the file.
  Large ones also read far faster. NOTE: It's not clear the game engine handles more than
  100 connect points, so caveat modder.

- **Import sets flags in the armature's export panel.** "Rename Bones", "Export Bone
  Hierarchy" and "Export All Bones" are all set appropriately on import for convenience.

- **Warning when vertex colors come from an attribute that isn't active.** PyNifly exports
  the color attribute named `VERTEX_COLOR`, not whichever is active -- so painting into a
  new attribute and making it active exports your old colors. The warning names both.

- **Starfield `.mesh` and `morph.dat` files can be named after the shape** instead of by
  hash.

- **Starfield normal maps light correctly.** Starfield uses the opposite green-channel
  convention from Blender, so imported normals were flipped top-to-bottom -- bumps read as
  dents under side lighting. Re-import to fix a .blend you already have. If you bake your
  own Starfield normals, invert green on the way out.

## Known limitations

- Some animations embedded in nifs set a bone position at the start of the animation and
  never change it - they fix the bone in place. Some of these fix the bone at its bind
  position, so they do nothing. We don't export those fcurves, so we don't create those
  controllers. 

- Exporting with only the root object selected still the child connect point, if there is
  one. Select the whole scene, or at least child connect point and root.

- **"Create Bones" against a non-human skeleton** silently substitutes vanilla human bone
  positions; "Rename Bones" renames some, but not all, bones. Turn it off for creature and
  machine rigs OR provide the correct reference skeleton.

# PyNifly 28.2.0 Release Notes

Fixes to **HKX animation export**. If you have exported animations with an earlier
PyNifly, re-export them.

## Animation (HKX)

- **Exported animations no longer crash the game when they stop.** Thanks to
  sse-anim-tools for tracking it down (#418) and jarari for the Fallout 4 half (#415).

- **Annotations now survive export.** Native HKX export silently dropped every annotation
  event, so an animation that came in with footstep or sound triggers went out with none.

- Note: **Annotations are pose markers, not timeline markers.** They belong to the action,
  so they follow the animation instead of the scene, and several events can share a frame.
  To see them: open a **Dope Sheet**, switch it to **Action Editor**, and turn on
  **View > Show Pose Markers** — it's off by default. `M` adds a marker, `F2` renames it.

  If you have timeline markers in an existing .blend, they aren't converted — the native
  exporter never read them in the first place. Re-import the animation, or add the events
  as pose markers.

**Known limitation:** the legacy hkxcmd export path still reads scene timeline markers,
so annotations from a native import won't reach it. The whole legacy path is depreciated.


# PyNifly 28.1.0 Release Notes

Fixes to **Fallout 4 collisions** and **Starfield materials**. If you have
exported FO4 meshes with collision from an earlier PyNifly, re-export them.

## Fallout 4 collisions

- **Exported collision now names a real body.** `bhkNPCollisionObject` has a `bodyID`
  that indexes the physics system's body array, and PyNifly left it at its "unset"
  sentinel on every collision object it wrote, so no FO4 collision exported from Blender actually loaded. This affects every FO4 asset
  with collision.

- **Compressed-mesh collisions load, at any size.** Exported compressed meshes used to
  crash the game: the shape declared a fixed shape-key width and carried no
  bounding-volume tree. Both are now built properly. Meshes needing more than one section
  also export — the old limit surfaced as `AssertionError: max 255 verts per section`.

- **Collision with more than one body works.** The array of shape references was written
  incorrectly, so every body after the first got a null shape and the game
  crashed loading the cell. Body 0 lands in the right place either way, which is why
  single-body collision always appeared to work.

- **Collision stays where you put it.** A body's shape lives in its NIF node's space, but
  export wrote the vertices in world space, so the node transformed them a second time.
  Collision on any node that isn't at the origin ended up displaced by that node's
  translation. Geometry and the body transform are now both taken from the Blender object,
  so **moving a collision object in Blender moves the collision in game.**

- **Two-sided collision survives a round trip.** A surface is made solid from both sides
  by carrying the same triangle twice, wound opposite ways. Import compared triangles by
  their sorted vertex indices, decided the back face was a duplicate and dropped it —
  quietly turning a two-sided wall one-sided. Repeats now get their own copy of the
  vertices, so the triangle count comes back whole. This may increase the number of verts you see in Blender vs. the original nif.

- **Each body keeps its collision layer.** `collisionFilterInfo` decides what a body
  blocks, and nothing in Blender held it, so every exported body came out on the static
  layer. It now round-trips through the FO4 Physics property panel.

- **Each body keeps its own physics setup.** A dynamic body stays dynamic, and every body
  keeps its own material, quality and transform instead of being written as a copy of
  body 0.

- **A compound of compressed meshes is recognised as a compound** instead of being
  flattened into separate bodies on export.

- **Constraints are reported instead of vanishing.** A physics system can hold joints
  between its bodies. PyNifly reads none of them, and gives each collision object its own
  system, so a joint has nowhere to live — import now tells you how many are being lost
  rather than turning a hinged object into loose parts without a word. In vanilla these
  are robot armour, gore and exploded pieces; no architecture has any.

## Starfield materials

- **The `.mat` file is built from the Blender node tree.** Export no longer patches the
  file it read on import — the node tree is what you edited, so the node tree is what gets
  written. Layers can be added and reordered and the output follows.

- **Everything a material carries is preserved**, including the parts PyNifly doesn't
  model. Each node keeps the material objects it stands for, so fields and whole
  components we don't interpret survive a round trip instead of being dropped. All 36
  vanilla human materials rebuild with no field added, dropped or altered.

- **Node group names now carry a version** (`SF Layer v5`), and a group is never deleted.
  Previously a version mismatch rebuilt the group and orphaned every node still using it,
  which could damage materials in a `.blend` you were working in. Old unversioned groups
  from existing files keep working.

- **Export refuses to overwrite an existing `.mat` with a layerless material** — the case
  where PyNifly couldn't find the source material on import, which could destroy a
  hand-built one.

- **`MaterialID` and `AnimationFlagExtra` are read and written correctly**, and are no
  longer written twice.

- **No more `BSShaderTextureSet`** on Starfield shapes; textures come from the material.

- **A shape with internal geometry needs no external `.mesh`**, and is exported that way.

## Starfield head parts and morphs

- **Head parts export their `_faceBones` companion.** A Starfield head part is a pair of
  files — the head skinned to body bones, and a companion skinned to the `faceBone_*` rig
  — found by naming convention. PyNifly only knew how to do this for Fallout 4, and only
  recognised Fallout 4's bone prefix. The two nifs get **distinct** external `.mesh`
  files, which they must, since they hold different skin data.

- **Morphs are built from the split morph data**, so they match the `.mesh` they belong
  to, and shape-key names are normalised before they're classified and written.

## General

- **Export settings stick.** Root-level options are remembered when only the shape is
  selected, and for a scene with no PyNifly root at all.

- **`scripts/sf_racecheck.py`**, an auditor for Starfield custom races. There are a lot of
  special and non-obvious rules that can prevent a headpart from showing. Run this tool
  when custom-race headparts misbehave.

- Starfield material documentation rewritten for the build-from-node-tree design, with
  links to the online Bethesda Library.

## Upgrading

Nothing to migrate. The FO4 collision work adds one property to the FO4 Physics panel,
which defaults sensibly for objects that don't have it. Re-export FO4 meshes with
collision to pick up the fixes.

## Known limitations

- Some combinations of collision shapes in one physics system still aren't supported, and
  export will say so rather than write a bad file: a compressed mesh with several convex
  shapes, and most combinations involving a compound.
- Compound collision is preserved as-is, not regenerated — editing it in Blender has no
  effect, because the bounding-volume tree it needs isn't built yet.
- Capsule collision bodies aren't decoded and are dropped on import.
- Physics constraints aren't supported for any game.
- Fallout 4 meshes animated by a controller targeting skeleton bones (Diamond City's
  tarps and awnings, for example) lose the animation on export.

# PyNifly 28.0.0 Release Notes

Major new release! We added support for **Blender 5.2**, fixed **FO4 compound
collisions**, and are giving you a very early preview of **Starfield support**. We've also
moved from storing nif-specific properties in generic custom attributes and have put them
in **named property panels** (which is actually the major incompatibility, sorry). 

## New: Starfield support

Consider this experimental - what's here works, passes tests, etc. etc. But the
functionality is limited and I've only tried it out on a few bodyparts and some simple
statics.  

- **Import and export Starfield meshes.** Starfield stores geometry in external `.mesh`
  files referenced by a `BSGeometry` block in the NIF; PyNifly reads and writes both.
  - The folder and name of a nif's associated mesh can be set in Blender.
  - Multiple LOD levels are not yet supported.

- **Skinning.** Skinned bodies round-trip with their bones, bind transforms, and weights.
  SF meshes can have **more than 4 bone weights per vertex**, and that's supported.
  Verified in-game and in the Creation Kit.

- **Materials.** Starfield has a new, complex layered materials system. Our goal is to
  make it possible to visualize, create and modify these matierals directly in Blender. 
  
  - Import creates a shader that mimics the Starfield material to the extent possible.
   Every material layer and blend is represented as a group node in Blender, connected as
   in the material structure. 

  - Materials are compressed into a material database (`materialsbeta.cdb`) and may not be
    available as loose files. The importer will look for a loose file first (using our
    existing rules for finding texture files), then look in `materialsbeta`. You can set
    the path to that file in the addon's preferences. 

  - The standard in SF is that materials live in a subfolder under the `materials` folder.
    Vanilla SF materials files have a hashed folder and material file name. You can
    override both with comprehensible names ('mod'/'material') if you prefer. This is an
    option on export, should you prefer to manage your own materials.

- **Bodypart morphs.** In Starfield, morphs live in a `morph.dat` file associated with the
  nif through the bodypart's record. Morphs are not constrainted to headparts only.
  Headparts have two morph files: "performance" (expressions) and "chargen". There is no
  convention that the morph be named after the nif or saved with it - vanilla morphs are
  kept in a separate `meshes/morphs/` folder tree. So:
  
  - Load morphs expliclity with `import`/`Starfield morph with PyNifly`

  - Properties `chargen_path` and `performance_path` store the relative path of the morph
    file.

  - On export the morph files will be written to those paths if defined (and if the
    "export morphs/tri files" option is set), or to a generated path if not.

- We've added dedicated Starfield texture-path preferences and property panels.

## Fallout 4 fixes

- **Compound collions** Fallout 4 collisions may be a single object that combines multiple
  collisions (workbenches, for example). These are now represented in Blender and import
  and export without crashing the game. *Modifying* them is not yet supported - they use a
  bounding-volume tree format that we haven't implemented yet. The collision is shown in
  Blender as a `bhkPhysicsSystem` → `bhkCompound` group of the individual shapes.

- **The convex-radius collision visualization** now uses one node group per radius, so
  shapes with different convex radii are shown correctly.

- **A shape skinned to bones but parented under a non-identity node** (common in Fallout 4
  furniture) is now placed correctly on both import and export. Previously the node's
  offset was applied twice on import (the shape slid off its collision), and on export the
  skin transforms didn't carry the offset, so the shape rendered in the wrong place with
  skinning on (correct with skinning off) in NifSkope, Outfit Studio, and the game.

- **Static shapes that share a NIF with a skinned shape** are no longer given an empty
  skin binding. Fallout 4 furniture often mixes a skinned mesh with static decoration;
  exporting the static pieces with a (bone-less) skin instance crashed the game on load.
  They now export as plain static geometry.

## General improvements

- **Pynifly property panels** We've moved from custom properties on objects and materials
  to dedicated PyNifly-specific property panels. This should be easier to manage, but old
  blend files won't have the new properties. There's a migration path from old custom
  properties to new panels so this shouldn't be a major issue. 

- **Exporting dense  meshes is dramatically faster.** A per-vertex read of the UV layer
  scaled badly on modern Blender (over two minutes on a ~130k-loop body); it is now read
  in bulk, cutting that shape's export from ~120 s to ~3 s, with byte-identical output.

## Error reporting: duplicate triangles dropped on import

A Blender mesh holds at most one face per set of vertex indices, so a nif containing
the same triangle twice loses the copy. This has always happened; it just happened
silently, and some meshes lose a lot — SKYBCathedral's main shape drops 1,750 of
30,247, and Fallout 4's VltGearDoor01 loses roughly half of several shapes.

Import now reports how many went and from which shapes. They still can't be exported,
but you'll know. Partition and LOD assignment, both indexed by triangle, now map back
through the surviving triangles rather than sliding by one per dropped duplicate.

**Known issue:** zero-area triangles (two or more corners at the same position) have no
face normal, and Blender averages that (0,0,0) into every vertex of the surrounding
smooth fan — so a couple of invisible triangles can visibly corrupt the shading on the
good geometry around them. SKYBCathedral has 60, affecting 8 vertices. Removing them
fixes it, but that's mesh surgery on import, which we'd rather not do behind your back.
Delete them yourself if a shape shades oddly.

## Bugfix: collision convex radius was overwritten on export

The convex radius of a `bhkCompressedMeshShape` was hardcoded to PyNifly's per-game
default on export rather than carried through from the source. Vanilla shapes don't all
use the default (SEVMageTower05 is 0.001, SKYBCathedral 0.05), so a round trip changed
the collision margin.

## Animation fixes (Fallout 4 / Skyrim)

- **Linear rotation keys export.** Node/bone rotations stored as linear (rather than
  quadratic) keys now export instead of failing.

- **Rotation channels with mismatched key times are handled.** A NIF can store X/Y/Z
  rotation as three independent curves with different key times; import and export now
  put them on a common timeline when needed instead of mis-combining them (and the
  spurious "Keyframes do not align" warning is gone).

- **Node and root-node animations export.** Animations on a nif's ordinary nodes — and on
  the root node itself — are no longer dropped or written onto the wrong bone.

## New: Blender 5.2 support

- **PyNifly works on Blender 5.2.** Blender 5.2 changed how geometry-node modifier inputs
  are set, which broke collision import; fixed. The full test suite passes on 5.2 and 5.1.


# PyNifly 27.4.0 Release Notes

## Bugfix: export of nifs with many child nodes

- **Nifs whose root (or any node) has more than 128 children now export instead of
  failing with `IndexError: invalid index`.** Affected meshes with large skeletons such
  as the Fallout 4 EngineerScribe outfit. (Issue #406)

## New: full precision vertices export option

- **New "Full precision vertices" export option.** Fallout 4 shapes normally store
  vertices as 16-bit half-precision floats; this option stores them at full 32-bit
  precision instead. The checkbox defaults to the shape's current setting, so it round-trips
  automatically — check it to turn full precision on, clear it to turn it off. Previously
  this could only be controlled by hand-editing the shape's `hasFullPrecision` custom property.

# PyNifly 27.3.0 Release Notes

## Bugfix: animation float data

- **`NiFloatData` with "no interpolation" key types now loads instead of erroring.**

## New: drag-and-drop NIF import

- **Drop a `.nif` file into the 3D viewport to import it** using your import preferences.
  Drop several nifs together (e.g. _0 and _1 weights) and they combine as shape keys.
  (Requires Blender 4.1 or newer.)

## New: import into a new collection

- **New "Import into a new collection" add-on preference.** Already available on the
  import dialog, this lets you set the option as the default. 

## New: Fallout 4 half-precision vertex recenter (export)

- **New "Recenter half precision vertices" export option for FO4 skinned meshes.** FO4
  headparts must be positioned at roughly 120 units above the origin. Vertices are stored
  as 16-bit half-precision floats and that distance from the origin can cause visible
  chunkiness. Until now the modder had to add transforms to the shape so the local vertex
  positions could be small while still positioning the part correctly. With this option,
  the vertices are repositioned and the transform added at export (if needed) so the
  modder doesn't have to worry about it. Only affects FO4 skinned shapes. 
- Credit to wushen233 for this one.

## Error reporting: warn when a Fallout 4 body won't dismember

- **Incorrect segmentation now triggers a warning.** Importing or exporting an FO4
  body/outfit that has limb dismemberment segments but no cut offsets will not dismember
  in game. pyNifly now flags it on both import and export.

## Bugfix: Fallout 4 dismemberment cut points

- **Cut-point disks for parts covered by the segment's base bone are restored.**
  When the `.ssf` didn't list a subsegment individually (because it was covered by
  the segment's base bone, e.g. the body's right thigh), its cut points were dropped.
  pyNifly now falls back to the part's dismemberment material to find the bone.

## Bugfix: Fallout 4 KF (animation) export

- **The NifTools bone-rename setting is read correctly on KF export again.** It was
  being looked up under the wrong name, which could fail the KF export dialog and
  silently drop a per-armature override of the setting.

## Bugfix: Fallout 4 shader export crash

- **Exporting an FO4 shape no longer crashes on the grayscale-to-color flag.** A
  shape whose shader carried the pre-rename `GREYSCALE_COLOR` flag could crash on
  export; it now exports correctly.

## Other

- Revived two long-dormant tests; the test suite now runs with no skips.

# PyNifly 27.2.0 Release Notes

## Bugfix: Fallout 4 textures without a materials file

- **FO4 shapes that don't reference a materials file now import correctly.** Nearly all
  FO4 meshes use external materials files, but Creation Kit FaceGen output do not. 
  Facegen nifs use the nif's own shader properties and texture paths. These now load 
  correctly.

## Bugfix: Fallout 4 shader property reading

- **NIF-level shader flags survive the BGSM material load.** Flags the material
  can't represent — notably **SLSF1_Skinned** and **Own Emit** — were being
  dropped or cleared when a shape's BGSM material was read. They now carry through.
- **FO4-specific shader-flag checks are fixed.** Accessors for Hair, RGB Falloff,
  Alpha Test, Gradient Remap, VATS Target Draw All, and Transform Changed now resolve 
  to the correct FO4 flags.
- **Emissive color, grayscale-to-palette scale, and wetness values** read from the
  BGSM correctly. Emissive color was decoded with the wrong data type, and the
  grayscale and wetness values weren't being pulled from the material at all.

## Bugfix: console logging restored

- **Progress and diagnostic messages appear in the console again.** A refactor
  that (correctly) stopped the library modules from configuring logging had
  silenced INFO-level output; the add-on now sets up its own console handler
  (INFO normally, DEBUG when developing).

## Bugfix: HKX skeletons and animations honor orientation settings (issue #377)

- **HKX skeleton import now respects "Blender-friendly scene orientation."**
  Importing `skeleton.hkx` with that option on used to leave the skeleton at full
  NIF scale and orientation, mismatched against a Blender-oriented NIF import.
  The skeleton now scales and rotates to match, and any animation loaded onto it
  follows automatically. Works for Skyrim LE/SE and Fallout 4.
- **HKX skeleton import now supports "rotate bones pretty."** Bones can be brought
  in with the display-friendly orientation, just like NIF import. Animation import
  and export compensate for the pretty rotation, so animations play correctly and
  round-trip whether pretty bones are on or off.

# PyNifly 27.1.0 Release Notes

## New function: Skyrim skinned trees

- **Vanilla skinned trees now import and export with full fidelity.** Trees such
  as `treeaspen03` and `treepineforest02` round-trip through Blender, load in the
  Creation Kit, and animate in-game. The special block types are preserved:
  - **`NiSwitchNode`** (LOD / billboard switching) with its switch flags and
    active index. The invariant is enforced on export: a `NiSwitchNode` has
    exactly two children, and the second child has no skinned descendants.
  - **`BSMultiBoundNode` / `BSMultiBound` / `BSMultiBoundOBB`** culling bounds,
    including the oriented bounding box, represented in Blender and round-tripped exactly.
  - **`BSTreeNode`** with its `Bones1` / `Bones2` bone-group lists.
- **Bone references are deduplicated and aggregated by ID.** Vanilla trees list
  the same bone several times across skin partitions; these are now collapsed to
  a single Blender bone with aggregated weights.
- **Special tree nodes are named `<name>:<blocktype>` in the outliner** (e.g.
  `FadeNode Anim:BSMultiBoundNode`) so their special role is visible.
- **Unskinned shapes under a `NiSwitchNode`** (the LOD billboards) export as
  static `NiTriShape`, not skinned shapes.

## New function: FO4 dismemberment

- **Dismember cut offsets are handled correctly.** FO4 segmented meshes that
  define cut offsets (where a limb separates when dismembered) now round-trip:
  the offsets are preserved on the `FO4_CUT_OFFSETS` mesh property and written
  back out on export.
- **Cut points are visualized on import.** When a segment file (`.ssf`) can be found, 
  cuts are shown as disks perpendicular to the bearer bone, grouped under a `<mesh>_Cutpoints` collection (toggle them all via
  the eye icon) and bone-parented so the disks follow the pose. The bearer bone
  for each cut is read from the mesh's `.ssf` segment file — found alongside the
  NIF, or through the configured game data paths — so this works the same way for
  human and creature meshes. If no segment file can be found the visualization is
  skipped with a warning; the cut offsets still round-trip on the mesh property.
- **The segment file (`.ssf`) is written on export.** When a mesh carries cut
  points pynifly writes the matching `<nif-basename>.ssf` next to the exported
  NIF (the vanilla naming), built from the cutpoint disks — or, if you've removed
  the disks, from the mesh's segments. Move, add, or delete a disk and both the
  exported cuts and the `.ssf` follow. Note, the cutpoints must either be selected *or* 
  a collection with the correct name must exist.

## Bugfix: Pretty bones and bone-mounted collisions

- **Pretty bone orientation no longer introduces a difference between pose and rest.** Importing with
  "rotate bones pretty" on, a bone that carries a collision used to end up posed
  away from its rest position. Pose now equals rest.
- **Bone collisions are placed at the bone's real position**, not the cosmetic
  pretty frame. Branch capsules on a pretty-imported tree used to sit ~90°
  off the branch; they now follow the mesh regardless of the pretty setting.
- **Skinned trees whose bone NiNode and skin bind disagree import undeformed.**
  Some vanilla trees (`treepineforest02`) author a bone's NiNode at the origin
  while binding it hundreds of units away. The mesh now imports with pose equal
  to rest instead of being deformed off its authored geometry.

## Other bugfixes

- **`NiTriShape` exports correctly on Skyrim SE.** SSE shapes authored as
  `NiTriShape` are now written as `NiTriShape` rather than being forced to
  `BSTriShape`, fixing Creation Kit rejection of some meshes.
- **No more fabricated `bhkConvexTransformShape`.** Bone collision capsules in a
  `bhkListShape` are exported bare, as in vanilla, instead of being wrapped in a
  spurious identity `bhkConvexTransformShape` on export.
- **TRIP morph import fixed.** The TRIP file is now loaded before being passed to
  the morph importer, so TRIP morphs import correctly.
- **New "import cutpoints" option** surfaced (along with "write bodytri") in the
  add-on preferences.

---

# PyNifly 26.0.0 Release Notes

## Bugfixes (issue #392)

- **`NifFile.initialize(root_name=...)` now sets the name correctly for
  `NiControllerSequence` roots.** The name was previously stored on the block
  but not registered in the header string table, so reads via `properties.nameID`
  (which `NiSequence.name` uses) returned an empty string until the file was saved
  and reopened. The `if`/`else if` chain in `SetNifVersionWrap` was also cleaned
  up so non-default root types take only their own branch.
- **`NiShape.set_partitions()` now accepts the index list returned by
  `partition_tris` directly.** For Skyrim-style nifs the trilist may be either
  partition IDs (the older idiom) or partition-list indices (what
  `partition_tris` returns), auto-detected.

## Breaking change

- **`NifFile.createShapeFromData()` no longer flips the V coordinate on write.**
  UVs are now passed through unchanged so direct API users get a clean
  `createShapeFromData` → `shape.uvs` round-trip. Blender import/export still
  round-trips correctly because the Blender export path now applies the flip
  explicitly. Direct callers that were pre-flipping with `(u, 1-v)` to compensate
  must remove that workaround.

---

# PyNifly 25.14.0 Release Notes

## Native HKX Skeleton Export

- **Native skeleton.hkx export for Skyrim LE, SE, and Fallout 4.** Skeleton
  files are now written directly in binary HKX format without requiring hkxcmd.
  Supports all vanilla skeleton features: bone hierarchy, reference poses,
  lockTranslation flags, floatSlots, and referenceFloats.

  Previously, I've noted that the round trip probably loses important skeleton data. 
  This release maintains all the data that I know of. See [docs/hkx_skeleton_format.md](docs/hkx_skeleton_format.md) 
  and [docs/hkx_skeleton_format_fo4.md](docs/hkx_skeleton_format_fo4.md)
  for the details. If you see anything there that you know is wrong or missing, let
  me know.

- **Bone ordering preserved on export.** The original HKX bone order is stored
  on import and restored on export, ensuring animation compatibility (animations
  reference bones by index).

## Performance

- **Significant performance enhancements.** We've optimized the code in several areas.
  In particular, Blender 5.1 introduced a ~400x slowdown in
  per-element UV layer access. UV creation now uses `foreach_set` for bulk
  assignment, restoring import speed on 5.1 (67s down to 0.04s for a 3BBB mesh)
  and slightly improving earlier versions as well.

---

# PyNifly 25.13.0 Release Notes

## FO4 Vertex Colors, Vertex Alpha, and Materials

- **FO4 vertex color/alpha import overhauled.** Vertex colors and per-vertex alpha
  are now always imported into Blender (`COLOR` and `VERTEX_ALPHA` color attributes)
  whenever the BSTriShape's vertex format carries them, so the data round-trips
  faithfully on export. Whether the vertex alpha is wired into the diffuse shader
  is determined by material alpha settings rather than from vestigial NIF shader flags.
- **Tree materials.** Tree BGSMs (`BGSM.tree == True`) reuse the vertex alpha
  channel as wind-sway weight (trunk α=0, branch tips α=1), not as opacity. The
  importer now leaves vertex alpha unwired in the shader for tree materials so the
  trunk stays visible in Blender, while still preserving the data on round-trip.
- **AlphaProperty synthesized from BGSM.** When an FO4 nif has no `NiAlphaProperty`
  block but its BGSM has `alphblend0` or `alphatest` set, pynifly now synthesizes
  a Blender Alpha Property shader node from the BGSM fields so the imported
  material reflects what the engine will actually do. The synthesized node is
  flagged so export does NOT write a  `NiAlphaProperty` block back into
  the nif on round-trip.
- **BGSM lookup fixes.** Material file lookups now strip stray `Data\` prefixes
  from relative paths and strip absolute materials paths (of which vanilla has a few) to the "materials"
  component. The texture path preferences may end with /data or /textures; the materials path will
  be resolved either way. We no longer try to read the materials on _export_. 
- **`BSMeshLODTriShape` LOD groups.** All three LOD vertex groups (`LOD0`, `LOD1`,
  `LOD2`) are now always created on import, even when buckets are empty, so the
  user sees a consistent set regardless of which LOD levels the source nif uses.
- **The AlphaProperty shader node** no longer emits fractional alpha when alpha blend is not set.

## See Also

- New documentation: [docs/fo4_vertex_colors_and_shaders.md](docs/fo4_vertex_colors_and_shaders.md)

---

# PyNifly 25.12.0 Release Notes

## HKX Animation Export Fix

- **Skyrim SE and FO4 HKX animation export fixed.** Exported HKX animations were silently rejected by both games (T-pose in FO4, CTD in Skyrim SE). Multiple binary format issues have been corrected:
  - Skyrim SE: correct hk_2010 class signature hashes (were incorrectly using FO4's hk_2014 hashes), removed erroneous hkaDefaultAnimatedReferenceFrame object, fixed hkMemoryResourceContainer size, fixed inter-object fixups (local→global), fixed hkRootLevelContainer layout (no serialized base class).
  - FO4: correct file header (missing second magic word, missing padding block), fixed hkaAnimationContainer base class, fixed spline type field offset, fixed hkaDefaultAnimatedReferenceFrame field offsets, fixed pointer array alignment, added DONT_DEALLOCATE flags on empty arrays, fixed inter-object fixups (local→global).
  - Both games: quaternion encoding now uses 40-bit (rot_quant=1) matching vanilla files.

- **HKX animation extraction from Blender improved.** Animation data is now extracted via pose bone evaluation (scene.frame_set + depsgraph) instead of reading fcurves directly. This fixes compatibility with Blender 5.0+'s layered action system, which caused most bones to export with no animation data.

- **HKX export FPS setting honored.** The FPS value in the export dialog is now respected; previously it was silently overridden by the Blender scene FPS.

## Bug Fixes

- **FO4: Environment Mapping flag no longer written on export.** The Environment Mapping shader flag on FO4 NIF files causes CTDs in Fallout 4. PyNifly now suppresses this flag on all FO4 exports.

- **Skeleton bone scale preserved on import.** Skeleton NIFs with non-unit bone scale (e.g. the female beast race skeleton's hand bones at 0.85 scale) now correctly apply that scale to the pose bones in Blender.

- **Animation: Bezier handles for XYZ rotation keys.** Quadratic (Bezier) XYZ rotation keys now import with correct tangent handles, producing accurate interpolation curves. Previously the handles were not set, causing incorrect animation curves (e.g. Dwemer gears not rotating linearly).

- **Animation: FLT_MAX sentinels.** Exported NIF animation interpolators now use FLT_MAX sentinel values for base transforms, matching vanilla NIF convention.
