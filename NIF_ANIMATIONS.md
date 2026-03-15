# NIF Animations

Some nifs have animations embedded in them: chests and doors that open and close, flags that wave, dwemer gears that turn, and so forth. PyNifly imports and exports these animations.

For character animations in HKX files, see [ANIMATIONS.md](ANIMATIONS.md).

Video tutorial covering basic functionality [here](https://youtu.be/OFuoH80JOIY?si=PmT9vg-eu_5FiISF).

## What Can Be Animated

PyNifly supports several types of animation embedded in nif files:

- **Transform animations** -- position, rotation, and scale of objects and bones (NiTransformController)
- **Shader float animations** -- emissive multiple, alpha, glossiness, U/V offset and scale (BSLightingShaderPropertyFloatController,  BSEffectShaderPropertyFloatController)
- **Shader color animations** -- emission color, specular color (BSLightingShaderPropertyColorController, BSEffectShaderPropertyColorController)
- **Alpha threshold animations** -- for fade effects (BSNiAlphaPropertyTestRefController)
- **Visibility animations** -- toggling objects visible/invisible (NiVisController)

Both linear and Bezier interpolation are supported for keyframes.

## Import

**Import Animations** is on by default in the NIF import options. Uncheck it if you only want the mesh.

### Named Animations

A nif may contain multiple named animations -- for example a chest with "Open" and "Close" animations. Each animation is represented as a Blender Action.

- Actions are marked as assets with the "fake user" flag so they persist in the blend file.
- The action name matches the animation name in the nif.
- A single animation can affect multiple objects (e.g. a Dwemer chest with multiple gears and levers all moving together).

To switch between animations, use **F3 > "Apply Nif Animation"** and choose the one you want. This sets the correct action and action slot on every affected object.

### Animated Clutter

Animated clutter often has the animation on a parent node rather than on the mesh itself. On import, these parent nodes become Blender empties with the animation attached. Moving the empty moves all its children.

### Annotations and Text Keys

Some animations have text annotations at specific times (NiTextKeyExtraData), used for synchronizing events like door-slamming sounds. These appear as markers on the action's timeline. You may need to enable marker visibility with **View > Show Markers** in an animation editor.

### Frame Rate

Blender's FPS setting controls how many frames you get. A 10-second animation at 24 FPS gives 240 frames; at 60 FPS it gives 600 frames. Set the FPS before importing if you want smoother results.

## Export

- **All named animations** in the file are exported if they affect any object being exported, whether active or not.
- Animated meshes are exported at the position of the **first frame** of the currently active animation. Remove the animation before export if you don't want that.
- The default export frame rate is 30 FPS. You can change this in export options.
- Euler rotation keyframes support both linear and Bezier interpolation. Quaternion rotations are exported with linear interpolation; if Bezier quaternion curves are present, they are sampled at the export frame rate.
- Scale animations are not currently exported.

## Building Animations from Scratch

If you're creating new animations rather than editing imported ones, there are a couple of custom properties you need to know about:

- **pynActionSlots** -- This property on an object maps animation names to action slots. Its value looks like `Open|Object003||Close|Object003`, meaning when the "Open" action is applied, this object gets the "Object003" slot. This is set automatically on import, but if you're building from scratch you'll need to set it up so each object gets the right slot.

- **pynController** -- Set this custom property to `NiControllerSequence` on an Action to tell PyNifly to export it as a named animation with a Controller Manager. Without this, PyNifly won't create the NiControllerManager/NiControllerSequence structure in the nif.

## Under the Hood

Notes on how animations are structured in the nif. You shouldn't need this to use PyNifly, but it helps if you're debugging or building complex setups.

- If there are multiple named animations, the root node has a **NiControllerManager**. The Controller Manager doesn't control anything directly -- it parents one or more Controller Sequences.
- **NiControllerSequence** blocks are the individual named animations. The name allows them to be triggered by the game (e.g. "Open", "Close").
- Each NiControllerSequence contains **Controlled Blocks** -- one per animated target. Each references a target (a node or shader), an interpolator, and a controller.
- The interpolator references a **Data block** (NiTransformData, NiFloatData, etc.) which holds the actual keyframes.
- In Blender, each Controlled Block maps to one or more fcurves within an Action Slot. Multiple Controlled Blocks can share an Action if they're part of the same named animation.
