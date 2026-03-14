# PyNifly Animation Guide

PyNifly can import and export HKX animation files for Skyrim LE, Skyrim SE, and Fallout 4. This is done natively in Python -- no external tools like hkxcmd are required.

## Supported Formats

| Game | Import | Export | Pointer Size |
|------|--------|--------|-------------|
| Skyrim LE | Yes | Yes | 32-bit |
| Skyrim SE | Yes | Yes | 64-bit |
| Fallout 4 | Yes | Yes | 64-bit |

PyNifly auto-detects which game format an HKX file uses. Skyrim LE vs SE is distinguished by pointer size in the file header.

## Basic Workflow

The recommended workflow is:

1. **Import the game skeleton** from an HKX file (not the skeleton.nif file!)
2. **Import the NIF mesh** onto the skeleton (optional, for visual reference)
3. **Import the HKX animation** onto the skeleton (or not, if your're starting from scratch)
4. Edit the animation in Blender
5. **Export the HKX animation**

### Step 1: Import the Skeleton

Use **File > Import > Import HKX (PyNifly)** and select the game's skeleton HKX file.

Common skeleton files:
- **Skyrim human**: `meshes/actors/character/character assets/skeleton.hkx`
- **FO4 human**: `meshes/actors/character/characterassets/skeleton.hkx`
- Other creatures have their own skeleton files in their respective folders.

This creates a Blender armature with all the skeleton's bones. PyNifly stores the bone list and game type on the armature so that animation import and export work automatically afterward. 

The HKX skeleton has information the nif skeleton does not have (extra bones, bone order) so just using the nif skeleton won't do.

### Step 2: Import a Mesh (Optional)

With the armature selected, use **File > Import > Import NIF (PyNifly)** to bring in a body or creature mesh. The mesh will be skinned to the armature automatically.

### Step 3: Import an Animation (Optional)

With the armature selected, use **File > Import > Import HKX (PyNifly)** and select an animation HKX file. The animation is loaded as a Blender action on the armature. Annotation events from the HKX file become timeline markers.

Edit the animation to your heart's content.

### Step 4: Export an Animation

With the armature selected, use **File > Export > Export HKX (PyNifly)**. Choose the output path and the target game format (Skyrim LE, Skyrim SE, or FO4).

No reference skeleton file is needed -- PyNifly uses the bone data stored on the armature from the skeleton import.

## Import Options

| Option | Description |
|--------|-------------|
| **Use Blender Orientation** | Apply Blender's coordinate system (Z-up). Leave off to keep game coordinates. |
| **Rename Bones** | Convert bone names to Blender L/R conventions (e.g., "NPC L Hand" becomes "NPC Hand.L"). |
| **Rename Bones NifTools** | Use NifTools naming conventions instead. |
| **Reference Skeleton** | Path to an HKX skeleton file. Only needed for the legacy hkxcmd workflow (see below). |

## Export Options

| Option | Description |
|--------|-------------|
| **Game** | Target game: FO4, Skyrim LE, or Skyrim SE. |
| **FPS** | Frames per second. Default 30, which matches the standard for Bethesda animations. |
| **Reference Skeleton** | Only needed for the legacy hkxcmd workflow. |

## Annotation Markers

HKX animation files can contain annotation events (text labels at specific times), used by the game engine to trigger sounds, effects, etc.

- **On import**, annotations become Blender timeline markers.
- **On export**, timeline markers are written back as annotations.

## Tips

- **Set the frame rate** before importing. Bethesda animations typically use 30 FPS. Set this in Blender's Output Properties before importing.
- **Bone renaming** should be consistent. Use the same rename settings for skeleton import and animation import/export.
- **Skyrim LE vs SE**: The skeleton determines which format is exported. If you imported a Skyrim LE skeleton (32-bit pointers), the export will default to LE format, and vice versa for SE. You can import a LE animation on a SE skeleton, so conversion between games is easy.
- **Multiple animations**: You can import multiple animations onto the same skeleton. Each import creates a new Blender action. Switch between them in the Action Editor.

## Legacy Workflow (hkxcmd)

If your armature was imported from a NIF file rather than an HKX skeleton, PyNifly falls back to using hkxcmd.exe for animation conversion. This requires:

- `hkxcmd.exe` present in the addon folder
- A **Reference Skeleton** HKX file specified in the import/export options

The native workflow (importing the HKX skeleton first) is recommended, as it requires no external tools and supports all three game formats.
