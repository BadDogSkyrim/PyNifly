# PyNifly Next Release Notes

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
