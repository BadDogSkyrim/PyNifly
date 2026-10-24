# Starfield cloth: viewing and editing it in Blender

Starfield hair, tails and loose clothing move by cloth simulation. The simulation lives in the nif's
`BSClothExtraData` block. PyNifly draws it in Blender when you import, lets you change its values, and
writes the changes back when you export.

The simulation doesn't move the mesh directly. It moves a small set of **particles**, joined by
**links**. Those particles form a few triangles, and each triangle drives one bone. The mesh you
see is skinned to those bones as usual. **Collision shapes** on the body keep the particles from
passing through it.

## What you see after importing

Everything appears under the `BSClothExtraData` empty, drawn as wireframe in front of the mesh.

- **The sim mesh**, named `Cloth:<piece name>`: one per piece of cloth.
  - **Vertex = particle**, at its rest position.
  - **Face = sim triangle.** Each one drives a bone.
  - **Edge = link.** The edge attribute `cloth_link` says which kind: 1 standard, 2 stretch, 3 both,
    0 not a link.
  - **Per-particle values** are vertex attributes: `cloth_mass`, `cloth_radius`, `cloth_friction`.
  - **Pinned particles** are in the vertex group `cloth_pinned`. A pinned particle has mass 0 and
    follows the skeleton; the free ones are simulated.
  - **The cloth's settings** are Custom Properties on the object, one per setting (see below).
- **Collision shapes**: one mesh per capsule, tapered capsule or sphere, named for it (for example
  `C_Hips_Capsule`). Its Custom Properties say which shape it is and which bone it follows.

Export never writes any of these as shapes. They are pictures of the cloth data.

## Reading the values

- **Object Data properties → Attributes** lists the attributes.
- **The Spreadsheet** editor (it's in the Geometry Nodes workspace) shows the values. Pick
  **Vertex** for particles or **Edge** for links.
- **To find one particle's row:** in Edit Mode select it, then turn on the Spreadsheet's
  *Selected Only* filter. The row number is the particle number.
- **To see particle numbers in the 3D view:** turn on *Preferences → Interface → Developer Extras*,
  then *Viewport Overlays → Indices*.

## The settings

These are Custom Properties on the sim mesh (Object properties tab).

| Property | What it does |
| --- | --- |
| `cloth_gravity` | Gravity, in metres per second squared. Vanilla uses (0, 0, -9.81); some mods use half that. Lower makes the cloth hang less, and also makes it float. |
| `cloth_damping` | How fast motion dies away, per second. Lower swings longer. |
| `cloth_iterations` | Solver passes per step. More makes links hold their lengths more firmly. Stiffer links need more passes. |
| `cloth_sub_steps` | Simulation steps per frame. More is steadier and costs more. |
| `cloth_bend_stiffness` | How strongly the cloth resists bending at each edge two sim triangles share, from 0 to 1. 0 means the cloth has no bend constraints. Set it above 0 and export adds them; the cloth's rest shape is the shape it holds. Vanilla hair commonly uses 0.5 to 0.8. |
| `cloth_transfer_translation`, `cloth_transfer_rotation` | Whether the cloth takes on the body's own movement. |
| `cloth_transfer_translation_min` / `_max` | How much of the body's movement it takes on (0 to 1), at low and at high speed. |
| `cloth_transfer_rotation_min` / `_max` | The same for turning. |
| `cloth_transfer_translation_speeds`, `cloth_transfer_rotation_speeds` | The low and high speeds those blend between. |

Total mass isn't shown: it's the sum of the particle masses, and export updates it for you.

## What you can change

1. **A setting:** edit its Custom Property.
2. **A particle's mass, radius or friction:** select the sim mesh in Edit Mode, select the
   particles, make the attribute active in *Object Data properties → Attributes*, and use
   *Mesh → Set Attribute*.
3. **A capsule or sphere:** move, rotate or scale the object. Scaling across it changes the radius;
   scaling along it changes the length.
4. **A new link:** in Edit Mode, add an edge between two particles. Then select the edge, make
   `cloth_link` the active attribute, and use *Mesh → Set Attribute* to set it to 1 for a standard
   link or 2 for a stretch link. Its rest length is the particles' distance apart, and its
   stiffness is 1.

Then export as usual. Only what you changed is written; the rest of the cloth data goes out exactly
as it came in.

### What isn't written yet

These are warned about in the export log and left as they were:

- moving a particle
- changing which particles are pinned
- removing a link the cloth already had
- editing a tapered capsule

Adding or deleting a particle refuses the whole edit: the export log says so and the cloth goes out
exactly as imported.

## Kinds of link

- **Standard links** keep two particles at their rest distance, pushing as well as pulling.
- **Stretch links** only stop two particles getting further apart than their rest distance. Vanilla
  runs them from the pinned root to the tip so the whole length can't stretch.

Neither kind resists bending. A chain of links bends freely at every particle, so a cloth with
only neighbour-to-neighbour links hangs like a rope. A link that skips a particle (from each
particle to the one two along) adds some resistance to bending, but only once the cloth is
noticeably bent.

To make a cloth resist bending from the start, use `cloth_bend_stiffness`. It adds a spring at
every edge two sim triangles share, which is what vanilla hair uses.

Stiffness and `cloth_iterations` work together: the solver applies the stiffness once per
iteration. With 1 iteration even 0.999 barely holds; a fox tail looks right at 4 iterations and
stiffness 0.9.
