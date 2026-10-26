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
  - **Skin weights**: every particle is skinned to the skeleton, through vertex groups named for
    the bones, up to four per particle. Pinned particles follow them; free ones use them as the
    anchor for local range. A vertex group whose name starts with `*` is yours (a selection to
    keep, say) and export ignores it, as it does a `*` shape key.
  - **Hinges**: the edge attribute `cloth_bend` is the bend stiffness at an edge two triangles
    share, from 0 to 1; 0 means no hinge spring. A hinge works across the edge, on the two
    triangles' four particles, so it doesn't care whether the edge is also a link: on a strip
    the diagonals often aren't links but are still hinges. Every inner edge of a strip is a
    hinge, rungs and diagonals alike, so to free a stretch of strip, zero them all.
  - **Local range**: a cloth can have up to four local-range sets, each limiting how far its
    particles stray from where the skeleton puts them. Set N has the vertex attributes
    `cloth_rangeN_max` (and `_max_normal`, `_min_normal`, sometimes `_stiffness`); -1 means the
    particle isn't in the set. The set's own settings are properties: `cloth_rangeN_stiffness`,
    `cloth_rangeN_name`, `cloth_rangeN_shape`, `cloth_rangeN_normal`.
  - **`cloth_particle`** is each vertex's particle number in the cloth as imported, and
    `cloth_collision_mask` which collision shapes it hits (bit k = the cloth's k-th shape).
    Leave both alone.
  - **The cloth's settings** are Custom Properties on the object, one per setting (see below).
  - **Carried-over constraints**: `cloth_carried` lists the constraint sets Blender doesn't show
    yet (compressible links, volume). Export keeps them; one that uses a deleted
    particle is dropped, with a warning.
- **Collision shapes**: one mesh per capsule, tapered capsule or sphere, named for it (for example
  `C_Hips_Capsule`). Its Custom Properties say which shape it is and which bone it follows.
- **Bone planes**: one square per plane, named `Plane:<bone>`. A bone plane keeps particles on
  one side of a plane that rides a bone: the side the square's face normal points to. Its
  Custom Properties are `cloth_plane_bone` and `cloth_plane_stiffness` (0 to 1). The particles
  it holds are the sim mesh's vertex group `plane:<the square's name>`. Vanilla uses them on the
  head to keep hair out of the face, on the neck for ponytails, and under the hips to stop skirt
  flaps flipping up.

Export never writes any of these as shapes. It builds the cloth data afresh from them, so what
they show is what goes out.

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
| `cloth_link_stiffness`, `cloth_stretch_stiffness` | The stiffness of every standard link, and of every stretch link, from 0 to 1. Vanilla uses one value per cloth. |
| `cloth_stretch_slack` | How far a stretch link lets its particles get apart, as a multiple of their rest distance. Vanilla uses 1.0 mostly, up to 1.43. |
| `cloth_driven_bones` | The bones the cloth moves, separated by commas. Each one follows the sim triangle nearest it. |
| `cloth_transfer_bone` | The bone whose movement the cloth takes on (see the transfer settings below). Vanilla uses the head for hair, the chest or hips for clothing. |
| `cloth_transfer_translation`, `cloth_transfer_rotation` | Whether the cloth takes on the body's own movement. |
| `cloth_transfer_translation_min` / `_max` | How much of the body's movement it takes on (0 to 1), at low and at high speed. |
| `cloth_transfer_rotation_min` / `_max` | The same for turning. |
| `cloth_transfer_translation_speeds`, `cloth_transfer_rotation_speeds` | The low and high speeds those blend between. |

Total mass isn't shown: it's the sum of the particle masses, and export updates it for you.

## What you can change

Everything the sim mesh and collision shapes show. Then export as usual.

1. **A setting:** edit its Custom Property.
2. **A particle's mass, radius or friction:** select the sim mesh in Edit Mode, select the
   particles, make the attribute active in *Object Data properties → Attributes*, and use
   *Mesh → Set Attribute*.
3. **A particle's rest position:** move the vertex.
4. **Pinning:** add particles to the `cloth_pinned` vertex group, or take them out. A particle
   taken out needs a mass; if `cloth_mass` is 0 it gets the cloth's usual mass, with a warning.
5. **A new link:** in Edit Mode, add an edge between two particles. Then select the edge, make
   `cloth_link` the active attribute, and use *Mesh → Set Attribute* to set it to 1 for a standard
   link or 2 for a stretch link. Its rest length is the particles' distance apart.
6. **Removing a link:** set its edge's `cloth_link` to 0, or delete the edge.
7. **Hinge stiffness:** select the edges and set `cloth_bend`, from 0 (folds freely) to 1
   (stiffest). At 0 nothing resists the two triangles folding along that edge; links still
   keep the particles their distance apart.
8. **Adding or deleting particles:** add or delete vertices. A new particle needs skin weights
   (a vertex group for at least one bone); its other values default to the cloth's usual ones.
9. **Skin weights:** paint or edit the bone vertex groups as for any skinned mesh.
10. **A collision shape:** export reads each shape from its mesh as it stands, so anything
    goes: move, rotate or scale it, apply its transforms, mirror it with a negative scale, or
    reshape it in Edit Mode. A capsule's axis runs through its two poles, or along the mesh's
    longest direction if it has none; its radius is the furthest the vertices sit from the
    axis; a rounded end is at its widest ring, a flat end one radius in. A tapered capsule
    keeps a radius for each end. Scaling across a shape changes its radius; along it, its
    length.
11. **Adding a collision shape:** duplicate one (Shift+D), or mirror a copy across to the other
    leg, and set its `cloth_bone` to the bone it should follow. Or add any mesh under the
    `BSClothExtraData` empty -- a cylinder or UV sphere will do -- with Custom Properties
    `cloth_shape` (`capsule`, `tapered_capsule` or `sphere`) and `cloth_bone`. A new shape
    collides with every free particle.
12. **Removing a collision shape:** delete the object.
13. **A bone plane:** move or rotate its square; flip it to keep particles on the other side.
    Change which particles it holds through its `plane:` vertex group.
14. **Adding a bone plane:** add a Plane mesh under the `BSClothExtraData` empty, give it a
    Custom Property `cloth_plane_bone` (and optionally `cloth_plane_stiffness`), and give the
    sim mesh a vertex group `plane:<the plane's name>` holding the particles. A plane on `Root`,
    facing up a few centimetres above the feet and holding every free particle, works as a
    floor (tested on a fox tail): `Root` stays at the feet when the actor crouches or lies down.
    It's flat, at the actor's feet, so not right on slopes or stairs. It holds particle centres;
    raise it if the mesh around them still dips into the ground.
15. **Removing a bone plane:** delete the square, or empty its group.

Starfield ignores Havok's own ground collision (`landscapeCollisionEnabled`; tried 2026-10-25),
so a bone plane is the way to keep cloth off the floor.

A standard link between two pinned particles is dropped, since neither can move.

## Making a new cloth

A mesh with no cloth can get one, built entirely from what you model.

1. Under the nif's root, add an Empty named `BSClothExtraData`.
2. Under that empty, model the sim mesh: vertices for particles, triangles between them. Any
   mesh under the empty is a piece of cloth, except collision shapes and plane squares;
   several meshes make several pieces.
3. Put the particles that follow the body in a vertex group `cloth_pinned`.
4. Give every particle a skin weight, a vertex group named for a bone. That's the bone the
   particle hangs from: pinned particles follow it, and free ones use it as their anchor
   (for local range). Vanilla weights hair to the head bone and skirts to the legs.
5. Add collision shapes and bone planes as described above, if you want them.

Export builds the cloth, and fills in on the sim mesh whatever you left out, so you can see
and change what went out:

- **Links:** every edge is a standard link (`cloth_link` 1).
- **Hinges:** every edge two triangles share gets `cloth_bend` 0.5.
- **Particles:** mass 0.08, radius 0.02 m, friction 0.5: vanilla's most common values.
- **Settings:** gravity (0, 0, −9.81), damping 0.9, 1 iteration, 1 sub-step, link
  stiffness 1, and vanilla's usual motion transfer.
- **Driven bones** (`cloth_driven_bones`): the armature's bones that aren't in Starfield's
  own skeleton, face bones aside: the cloth's own bones, such as a tail's or a ponytail's.
- **Transfer bone** (`cloth_transfer_bone`): the bone the cloth takes on the body's movement
  from. It defaults to the bone the pinned particles are weighted to most.

The cloth carries its own skeleton: the bones it uses and their parents up to `Root`, posed as
the armature has them. A bone the armature doesn't have, such as `Root` for a floor plane, comes
from PyNifly's reference Starfield skeleton. Give the cloth's own bones parents in the armature
(a tail's first bone parented to `C_Hips`, and so on), since the cloth's skeleton takes them
from there.

A new cloth starts loose: one iteration and hinges at 0.5 hold a strip only lightly. Raise
`cloth_iterations` and `cloth_bend` to stiffen it (see below).

Keep the sim mesh simple. A flat strip, as vanilla hair uses, works well. A closed tube (tried
on a fox tail, 2026-10-26) twitches and twists: every hinge shares its triangles with its
neighbours, so they fight each other, and stiffer hinges or more iterations make it worse. With
its hinges at 0 it stops twitching, but the links alone make it rigid, with a kink by the body.

## Kinds of link

- **Standard links** keep two particles at their rest distance, pushing as well as pulling.
- **Stretch links** only stop two particles getting further apart than their rest distance. Vanilla
  runs them from the pinned root to the tip so the whole length can't stretch.

Neither kind resists bending. A chain of links bends freely at every particle, so a cloth with
only neighbour-to-neighbour links hangs like a rope. A link that skips a particle (from each
particle to the one two along) adds some resistance to bending, but only once the cloth is
noticeably bent.

To make a cloth resist bending from the start, set `cloth_bend` on the edges two sim triangles
share. Each becomes a hinge spring, which is what vanilla hair uses; vanilla sets a stiffness
for each hinge, commonly 0.5 to 0.8.

Stiffness and `cloth_iterations` work together: the solver applies the stiffness once per
iteration. With 1 iteration even 0.999 barely holds; a fox tail looks right at 4 iterations and
stiffness 0.9.
