# PyNifly Import/Export Options

This document describes the options available when importing and exporting files with PyNifly. Most options appear in the file browser sidebar when you invoke the operator, and many have default values set in the addon preferences (Edit > Preferences > Add-ons > PyNifly).

---

## NIF Import

**Menu:** File > Import > Nif File (.nif)

| Option | Default | Description |
|--------|---------|-------------|
| **Use Blender orientation and scale** (`blender_xf`) | Off | Rotates the scene 90° and scales to Blender conventions. Without this, nif coordinates are used directly. Most meshes will have their back to you. |
| **Create vanilla bones** (`create_bones`) | On | Fills in missing bones from the vanilla skeleton so the armature hierarchy is complete. |
| **Blender-friendly bone names** (`rename_bones`) | On | Renames bones to follow Blender's `.L`/`.R` naming convention for mirroring and symmetry tools. Mutually exclusive with NifTools renaming. |
| **NifTools bone names** (`rename_bones_niftools`) | Off | Renames bones using NifTools' naming scheme instead of Blender's convention. |
| **Orient bones to show structure** (`rotate_bones_pretty`) | Off | Rotates bones so they visually follow the skeleton hierarchy rather than all pointing in the default direction. Cosmetic only. |
| **Import animations** (`import_animations`) | On | Imports any animations embedded in the nif as Blender actions. |
| **Import collisions** (`import_collisions`) | On | Imports collision shapes (bhkCollisionObject, bhkNPCollisionObject, etc.) as Blender objects with rigid body physics. |
| **Import tri files** (`import_tris`) | On | Automatically looks for `.tri` files and imports them as shape keys. Finds tri files according to the game's conventions--name_of_nif.tri for expression morphs and name_of_nif_chargen.tri for chargen morphs. |
| **Import as shape keys** (`import_shapekeys`) | On | When importing multiple files at once, merges similar meshes as shape keys on a single object. |
| **Apply skinning transforms** (`apply_skinning`) | Off | Bakes any transforms defined in the shape's skin partition into the final mesh vertices. |
| **Import pose position** (`import_pose`) | Off | Creates the armature from the bones' pose position rather than the bind position. Pose position is what you see in nifskope by default; bind position is what you see with the "bone" option clicked OFF. |
| **Mesh only** (`mesh_only`) | Off | Imports only mesh data — no armature, collisions, or other elements. |
| **Smart editor markers** (`smart_editor_markers`) | Off | When connect points have an editor marker use the editor marker as the location of the connect point so there aren't duplicate objects to manage in Blender. |
| **Create collection** (`create_collection`) | Off | Places each imported nif into its own new Blender collection. |
| **Reference skeleton** (`reference_skel`) | (empty) | Path to a skeleton nif to use as the bone hierarchy reference instead of the built-in vanilla skeleton. The built-in skeleton assumes a human actor, so use this if you're dealing with creatures. |

---

## NIF Export

**Menu:** File > Export > Nif File (.nif)

| Option | Default | Description |
|--------|---------|-------------|
| **Target game** (`target_game`) | (auto) | Which game format to export for: Skyrim, Skyrim SE, Fallout 4, Fallout 76, or Fallout 3/NV. The exporter tries to detect this from Blender object characteristics if available. |
| **Use Blender orientation and scale** (`blender_xf`) | Off | Reverses the Blender orientation/scale transform on export. Must match whatever was used on import. |
| **Blender-friendly bone names** (`rename_bones`) | On | Converts bone names back from Blender's `.L`/`.R` convention to nif names. Must match the import setting. |
| **NifTools bone names** (`rename_bones_niftools`) | Off | Converts bone names back from NifTools convention to nif names. |
| **Orient bones to show structure** (`rotate_bones_pretty`) | Off | Reverses pretty bone orientation on export. Must match the import setting. |
| **Preserve bone hierarchy** (`preserve_hierarchy`) | Off | Keeps the bone parent-child hierarchy as-is in the exported nif, instead of flattening them. Use this for skeletons and anything you will apply physics to. |
| **Write BODYTRI reference** (`write_bodytri`) | Off | Adds an extra data node in the nif pointing to the BODYTRI file for body morphs. Not needed when exporting for BodySlide (it writes its own). |
| **Export pose position** (`export_pose`) | Off | Exports bones in their posed position rather than bind position. |
| **Export modifiers** (`export_modifiers`) | Off | Applies all active modifiers (including shape keys) before exporting. |
| **Export animations** (`export_animations`) | Off | Embeds Blender animations into the nif as NiTransformController data. |
| **Export vertex colors** (`export_colors`) | On | Writes vertex color attributes to the nif as vertex colors. |
| **Chargen extension** (`chargen_ext`) | (empty) | Custom extension for chargen tri files (without the file extension). Used for face-part nifs. |

---

## KF Animation Import

**Menu:** File > Import > KF Animation File (.kf)

| Option | Default | Description |
|--------|---------|-------------|
| **Use Blender orientation and scale** (`blender_xf`) | Off | Same as NIF import. |
| **Blender-friendly bone names** (`rename_bones`) | On | Same as NIF import. |
| **NifTools bone names** (`rename_bones_niftools`) | Off | Same as NIF import. |

---

## KF Animation Export

**Menu:** File > Export > KF Animation File (.kf)

| Option | Default | Description |
|--------|---------|-------------|
| **Frames per second** (`fps`) | 30 | Frame rate for the exported animation. |
| **Blender-friendly bone names** (`rename_bones`) | On | Converts bone names back to nif convention. |
| **NifTools bone names** (`rename_bones_niftools`) | Off | Converts bone names back from NifTools convention. |

---

## HKX Animation Import

**Menu:** File > Import > HKX Animation File (.hkx)

| Option | Default | Description |
|--------|---------|-------------|
| **Use Blender orientation and scale** (`blender_xf`) | Off | Same as NIF import. |
| **Blender-friendly bone names** (`rename_bones`) | On | Same as NIF import. |
| **NifTools bone names** (`rename_bones_niftools`) | Off | Same as NIF import. |
| **Reference skeleton** (`reference_skel`) | (empty) | Path to the HKX skeleton file needed to bind animation data to the correct bones. |

---

## HKX Animation Export

**Menu:** File > Export > HKX Animation File (.hkx)

| Option | Default | Description |
|--------|---------|-------------|
| **Reference skeleton** (`reference_skel`) | (empty) | Path to the HKX skeleton file for animation binding. |
| **Frames per second** (`fps`) | 30 | Frame rate for the exported animation. |

---

## TRI File Import

**Menu:** File > Import > Tri File (.tri)

| Option | Default | Description |
|--------|---------|-------------|
| **Apply to active object** (`do_apply_active`) | On (if active object is a mesh) | Applies the tri morphs as shape keys on the currently selected mesh rather than creating new geometry. |

---

## Skeleton XML Import/Export

**Menu:** File > Import/Export > Skeleton XML (.xml)

No user-configurable options. Imports or exports a skeleton hierarchy in XML format.

---

## Skeleton HKX Export

**Menu:** File > Export > Skeleton HKX (.hkx)

No user-configurable options. Exports a skeleton in HKX format.

---

## Addon Preferences

**Location:** Edit > Preferences > Add-ons > PyNifly

These settings provide default values for the import/export operators, so you don't have to set them every time.

| Setting | Default | Description |
|---------|---------|-------------|
| **Blender-friendly bone names** | On | Default for `rename_bones` on all operators. |
| **NifTools-friendly bone names** | Off | Default for `rename_bones_niftools` on all operators. |
| **Import tri files when found** | On | Default for `import_tris` on NIF import. |
| **Import as shape keys** | On | Default for `import_shapekeys` on NIF import. |
| **Blender-friendly scene orientation** | Off | Default for `blender_xf` on all operators. |
| **Skyrim Texture Paths 1–4** | (empty) | Directories where Blender looks for Skyrim textures to set up materials. |
| **Fallout Texture Paths 1–4** | (empty) | Directories where Blender looks for Fallout textures to set up materials. |

---

## Tips

- **Matching import/export settings:** Options like `rename_bones`, `rotate_bones_pretty`, and `blender_xf` transform data on import. The same options must be enabled on export to reverse the transformation. Mismatched settings will produce incorrect results.
- **Bone renaming is mutually exclusive:** Enable either Blender-friendly (`rename_bones`) or NifTools (`rename_bones_niftools`) bone names, not both.
- **Target game auto-detection:** On export, the target game may be detected from the armature, or from the original if you started from an imported nif. You usually only need to set it manually for meshes built from scratch or if you're exporting to a different game.
- **Texture paths:** Set these in addon preferences so that materials display correctly in Blender's viewport. Point them to your game's extracted texture directories.
