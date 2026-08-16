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
