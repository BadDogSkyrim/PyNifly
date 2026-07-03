# PyNifly 27.3.0 Release Notes

## Bugfix: animation float data

- **`NiFloatData` with "no interpolation" key types now loads instead of erroring.**

## Bugfix: export of nifs with many child nodes

- **Nifs whose root (or any node) has more than 128 children now export instead of
  failing with `IndexError: invalid index`.** Affected meshes with large skeletons such
  as the Fallout 4 EngineerScribe outfit. (Issue #406)

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
