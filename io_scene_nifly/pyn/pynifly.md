# pynifly — Python API Reference

`pynifly.py` is a Python wrapper around `NiflyDLL.dll`, a C++ library for reading and
writing Bethesda NIF files (NetImmerse/Gamebryo format, `.nif`). Credit for NiflyDLL goes
to Ousnius and the Bodyslide/Outfit Studio folks. Pynifly exposes the contents of a NIF as
a hierarchy of Python objects that mirror the NIF block structure, with lazy-loaded
property buffers, helper properties for the most common operations, and factory methods
for building new blocks.

Supported games: **Skyrim LE**, **Skyrim SE**, and **Fallout 4**. There is limited support
for  **Fallout 76** and legacy NetImmerse formats.

---

## Table of Contents

1. [Setup](#setup)
2. [NifFile — file I/O and navigation](#niffile)
3. [NiObject — block base class](#niobject)
4. [NiNode — scene graph nodes](#ninode)
5. [NiShape — mesh geometry](#nishape)
6. [Skinning and bone weights](#skinning-and-bone-weights)
7. [Partitions and segments](#partitions-and-segments)
8. [Shaders and materials](#shaders-and-materials)
9. [Collision](#collision)
10. [Extra data blocks](#extra-data-blocks)
11. [Animation and controllers](#animation-and-controllers)
12. [Key types](#key-types)
13. [Module-level helpers](#module-level-helpers)
14. [Extending with new block types](#extending-with-new-block-types)
15. [Complete examples](#complete-examples)

---

## Setup

```python
from io_scene_nifly.pyn.pynifly import (
    NifFile, NiNode, NiShape,
)
from io_scene_nifly.pyn.nifdefs import PynBufferTypes, NODEID_NONE
```

`NiflyDLL.dll` is automatically found in the Blender addon directory when the module is
imported (via `niflydll.py`). Add io_scene_nifly.pyn to your Python path if using pynifly
outside of Blender. If the DLL is missing, an `ImportError` is raised.

---

## NifFile

`NifFile` is the entry point for all NIF access. It owns the DLL handle, manages all block
objects, and provides factory methods for creating new content.

### Loading an existing NIF

```python
nif = NifFile("path/to/file.nif")
print(nif.game)        # "SKYRIM", "SKYRIMSE", "FO4", …
print(nif.rootName)    # name of the root node
```

Raises `Exception` if the file cannot be opened.

### Creating a new NIF

```python
nif = NifFile()
nif.initialize(
    "FO4",              # game identifier
    "output/new.nif",   # output path
    root_type = "BSFadeNode",  # default "NiNode"
    root_name = "Scene Root",  # default "Scene Root"
)
# … add nodes, shapes, collision …
nif.save()
```

Game identifiers: `"SKYRIM"`, `"SKYRIMSE"`, `"FO4"`, `"FO76"`, `"STARFIELD"`.

### Core properties

| Property | Type | Description |
|----------|------|-------------|
| `game` | `str` | Game identifier (read from file or set by `initialize`). |
| `filepath` | `str` | Path passed to constructor or `initialize`. |
| `root` / `rootNode` | `NiNode` | Root node (always block 0). |
| `rootName` | `str` | Name of the root node. |
| `shapes` | `list[NiShape]` | All mesh shapes; loaded on first access. |
| `shape_dict` | `dict[str, NiShape]` | Shapes indexed by name. |
| `nodes` | `dict[str, NiNode]` | All named nodes. Node names are **not required to be unique**; this dict holds the last block registered for each name. Use `node_ids` for complete iteration. |
| `node_ids` | `dict[int, NiObject]` | All loaded blocks indexed by block ID. |
| `reference_skel` | `NifFile \| None` | Companion skeleton file (auto-located from the DLL folder). |
| `cloth_data` | `list[(str, bytes)]` | `(name, packfile_bytes)` pairs from `BSClothExtraData` blocks. Settable. |
| `connect_points_parent` | `list[ConnectPointBuf]` | FO4 parent connect-point descriptors. |
| `connect_points_child` | `list[str]` | FO4 child connect-point names. |
| `controller_managers` | `list[NiControllerManager]` | All `NiControllerManager` blocks. |

### Finding nodes and shapes

```python
# Shape by name
shape = nif.shape_dict["Body:0"]

# Node by name (last block registered for that name)
head = nif.nodes["NPC Head [Head]"]

# Any block by integer block ID
block = nif.read_node(id=42)

# Shape whose name starts with a prefix (convenience)
body = nif.shape_by_root("Body")

# Iterate all shapes
for shape in nif.shapes:
    print(shape.name, len(shape.verts), "verts")

# Iterate all loaded blocks
for block_id, block in nif.node_ids.items():
    print(block_id, block.blockname)
```

### Saving

```python
nif.save()   # writes to nif.filepath
```

`save()` also calls `_setShapeXform()` on every shape to flush local transforms.

### Logging

```python
NifFile.clear_log()       # clear the DLL error buffer
msg = NifFile.message_log()  # get the last error string
```

### Name conversion helpers

Bethesda uses different naming conventions in NIF files versus Blender. Blender names
for common elements are provided as a convenience.

```python
blender_n = nif.blender_name("NPC L Forearm [LLar]'")   # → "NPC Forearm.L"
nif_n     = nif.nif_name("NPC Forearm.L")              # → "NPC L Forearm [LLar]'"
```

### Creating mesh shapes

```python
shape = nif.createShapeFromData(
    "MyShape",
    verts   = [(x, y, z), ...],
    tris    = [(v0, v1, v2), ...],
    uvs     = [(u, v), ...],        # 1:1 with verts
    normals = [(nx, ny, nz), ...],  # 1:1 with verts; may be None
    props   = NiShapeBuf(),         # optional; sets bufType
    use_type = PynBufferTypes.BSTriShapeBufType,  # used if props is None
    parent  = nif.root,
)
```

Note: UV coordinates are flipped (`1 - v`) to match NIF convention.

### Creating nodes

It's possible to add nodes of arbitrary type. But it's usually better to use the
classes' "New" function.

```python
xf = TransformBuf()
xf.set_identity()
node = nif.add_node("MyNode", xf, parent=nif.root)
```

`add_node` takes:

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Node name. |
| `xform` | `TransformBuf` | Local transform. |
| `parent` | `NiNode \| None` | Parent node (root if omitted). |

### Generic block creation

Again, you'll usually want to use the class interface.

```python
buf = BSXFlagsBuf()
buf.flags = 202
block = nif.add_block("BSX", buf, parent=nif.root)
```

---

## NiObject

`NiObject` is the base class for every block in a NIF file. You will normally receive
instances from `NifFile.read_node()` or from `.New()` factory methods on subclasses, not
construct them directly.

### Core attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Block index within the NIF. `NODEID_NONE` if not in a file. |
| `file` | `NifFile` | The owning `NifFile`. |
| `blockname` | `str` | NIF block-type name as stored in the file (e.g. `"BSTriShape"`). |
| `buffer_type` | `int` | `PynBufferTypes` value identifying the ctypes buffer layout. |
| `properties` | `ctypes struct` | Low-level property buffer. First read lazy-loads from the DLL via `nifly.getBlock`. |

### Reading and writing properties

```python
buf = obj.properties        # loads from DLL on first access; returns ctypes struct
buf.someField = newValue
obj.properties = buf        # writes back immediately (calls nifly.setBlock)
# — or —
obj.write_properties()      # write the already-modified _properties buffer
```

### Class registries

After module load, `NiObject.register_subclasses()` populates two dicts:

```python
# Block-type name → Python class
cls = NiObject.block_types["BSTriShape"]

# PynBufferTypes int → Python class
cls = NiObject.buffer_types[PynBufferTypes.BSTriShapeBufType]
```

`NifFile.read_node()` uses these to instantiate the correct subclass for any block it reads.

---

## NiNode

`NiNode` represents a scene-graph node. Inherits
`NiObject → NiObjectNET → NiAVObject → NiNode`.

Bethesda-specific subclasses (`BSFadeNode`, `NiBone`, `BSFaceGenNiNode`, etc.) are
functionally identical; they exist only to carry the correct `buffer_type`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Node name. Settable — updates the NIF string table. |
| `transform` | `TransformBuf` | **Local** transform relative to the parent node. |
| `global_transform` | `TransformBuf` | **World** transform (accumulated from root). |
| `flags` | `int` | Node flags bitfield. |
| `parent` | `NiNode \| None` | Parent node (lazy-loaded from DLL). |
| `collision_object` | `NiCollisionObject \| None` | Collision block attached to this node. |
| `blender_name` | `str` | `name` converted to Blender conventions. |
| `nif_name` | `str` | `name` converted to NIF conventions. |

### Extra data

```python
# Get a single extra data block by type and/or name
bsxf = node.get_extra_data(blockname="BSXFlags")
bged = node.get_extra_data(blockname="BSBehaviorGraphExtraData", name="BGED")

# Get the Nth block of a given type
second = node.get_extra_data(blockname="NiStringExtraData", target_index=1)

# Iterate all extra data
for ed in node.extra_data():
    print(ed.blockname, ed.name)

# Iterate only a specific type
for ed in node.extra_data(blockname="NiStringExtraData"):
    print(ed.name, ed.string_data)
```

### Adding collision to a node

```python
coll_node = node.add_collision(
    body           = rigid_body_block,   # bhkRigidBody, or None for NP
    flags          = 129,
    collision_type = PynBufferTypes.bhkCollisionObjectBufType,
)
```

### NiNode subclasses

All of the following behave identically to `NiNode`:

`BSFaceGenNiNode`, `BSFadeNode`, `BSLeafAnimNode`, `BSMasterParticleSystem`,
`BSMultiBoundNode`, `BSOrderedNode`, `BSRangeNode`, `BSTreeNode`, `BSValueNode`,
`BSWeakReferenceNode`, `NiBillboardNode`, `NiBone`, `NiLODNode`, `NiSortAdjustNode`,
`NiSwitchNode`.

---

## NiShape

`NiShape` is the base class for all mesh geometry blocks. It inherits from `NiNode`, so it
also has `transform`, `global_transform`, extra data, and collision support.

Common concrete subclasses:

| Class | Games | Notes |
|-------|-------|-------|
| `BSTriShape` | Skyrim SE, FO4 | Standard triangle mesh |
| `NiTriShape` | Skyrim LE, Oblivion | Older format |
| `BSDynamicTriShape` | FO4 | Dynamic geometry |
| `BSSubIndexTriShape` | FO4 | Has FO4 segment data |
| `NiTriStrips` | Oblivion and earlier | Triangle-strip mesh |
| `BSMeshLODTriShape` | Skyrim SE | LOD mesh |
| `BSLODTriShape` | Skyrim | Older LOD mesh |

### Reading geometry

All geometry properties lazy-load from the DLL on first access.

```python
verts   = shape.verts     # list[(x, y, z)]  — NIF-space coordinates
tris    = shape.tris      # list[(v0, v1, v2)]
uvs     = shape.uvs       # list[(u, v)]      — 1:1 with verts
normals = shape.normals   # list[(x, y, z)]   — 1:1 with verts; may be None
colors  = shape.colors    # list[(r, g, b, a)] — 1:1 with verts; may be None
```

### Transform

```python
local_xf  = shape.transform         # TransformBuf, relative to parent
world_xf  = shape.global_transform  # TransformBuf, world space
```

### Shader and textures

See [Shaders and materials](#shaders-and-materials).

```python
shader  = shape.shader                    # NiShader subclass
diffuse = shape.textures.get("Diffuse")   # shortcut to shader.textures
shape.set_texture("Diffuse", "textures/actors/character/face.dds")
shape.save_shader_attributes()
```

### Alpha property

```python
if shape.has_alpha_property:
    ap = shape.alpha_property   # NiAlphaProperty
```

Enable alpha blending on a new shape:

```python
shape.has_alpha_property = True
shape.save_alpha_property()
```

---

## Skinning and bone weights

Skinning attaches a mesh to a skeleton so that bone transforms deform the vertex positions.

### Checking for skin data

```python
if shape.has_skin_instance:
    print("Skinned mesh")

if shape.has_global_to_skin:
    print("Has global-to-skin transform")
```

### Reading bone data

```python
bone_names = shape.bone_names   # ["NPC Spine", "NPC Spine1", ...]
bone_ids   = shape.bone_ids     # [block_id, ...]  — 1:1 with bone_names

# Global-to-skin offset transform (root mesh space → bind pose)
gts = shape.global_to_skin      # TransformBuf; calculated if not stored

# Skin-to-bone transform for a specific bone
s2b = shape.get_shape_skin_to_bone("NPC Spine")  # TransformBuf
```

### Reading vertex weights

```python
# Per-bone: {bone_name: [(vert_index, weight), ...], ...}
weights = shape.bone_weights

for bone, vw_pairs in weights.items():
    total = sum(w for _, w in vw_pairs)
    print(f"{bone}: {len(vw_pairs)} vertices, total weight {total:.3f}")

# Used bones (non-zero weights only)
used = shape.get_used_bones()
```

### Writing skin data

```python
shape.skin()                                   # create NiSkinData + NiSkinPartition
shape.set_global_to_skin(xf)                   # set the G→S offset
shape.add_bone("NPC Spine", xform=s2b_xf)      # register a bone
shape.setShapeWeights("NPC Spine",
    [(vert_idx, weight), ...])                  # weights must sum to ≤ 1 per vertex
```

### Weight helper utilities

Two module-level functions convert between the two common weight storage formats:

```python
# Convert list-of-per-vertex-dicts  →  per-bone dict
# weights_by_vert = [{bone_name: weight, ...}, ...]  — 1:1 with verts
weights_by_bone = get_weights_by_bone(weights_by_vert, used_groups)
# Returns {bone_name: [(vert_index, weight), ...], ...}
# - Only keeps bones present in `used_groups`
# - Keeps only the 4 heaviest weights per vertex
# - Normalises remaining weights to sum to 1

# Reverse conversion
weights_by_vert = get_weights_by_vertex(verts, weights_by_bone)
```

---

## Partitions and segments

Partitions (Skyrim) and segments (FO4) map each triangle to a body-part or material slot.

### Reading

```python
parts     = shape.partitions      # list[SkyPartition | FO4Segment]
part_tris = shape.partition_tris  # list[int] — 1:1 with shape.tris
seg_file  = shape.segment_file    # str — FO4 .ssf file reference, or ""
```

`FO4Segment` objects may have children:

```python
for seg in shape.partitions:
    print(seg.id, seg.name)
    if hasattr(seg, 'subsegments'):
        for sub in seg.subsegments:
            print("  ", sub.id, sub.name, sub.material)
```

### Writing

```python
shape.set_partitions(
    [SkyPartition(part_id=32), SkyPartition(part_id=35)],
    tri_list,   # [partition_id, ...]  — 1:1 with shape.tris
)
```

### Partition classes

| Class | Games | Notes |
|-------|-------|-------|
| `Partition` | base | Holds `id` and `name`; supports comparison |
| `SkyPartition` | Skyrim | Named via Skyrim body-part dict |
| `FO4Segment` | FO4 | May contain `FO4Subsegment` children |
| `FO4Subsegment` | FO4 | Has `user_slot`, `material`, and `parent` |

---

## Shaders and materials

A `NiShape` has one shader block that controls its visual appearance. `shape.shader` returns
the appropriate game-specific subclass.

### Accessing shader properties

```python
shader = shape.shader   # NiShader subclass

# Get all textures as a dict
textures = shader.textures   # {"Diffuse": "path", "Normal": "path", ...}
# or via shape shortcut
textures = shape.textures

# Set a texture
shader.set_texture("Diffuse", "textures/actors/character/male/MaleHead.dds")
shape.set_texture("Normal", "textures/actors/character/male/MaleHead_msn.dds")

# Write changes back to the NIF
shape.save_shader_attributes()
```

### Common texture slots

| Slot | Description |
|------|-------------|
| `Diffuse` | Base colour (albedo) |
| `Normal` | Normal / height map |
| `Specular` | Specular / gloss |
| `EnvMap` | Environment / cube map |
| `Glow` | Emissive / glow map |
| `InnerLayer` | FO4 complexion / inner texture |
| `Wrinkles` | FO4 wrinkle map |

### Shader classes by game

| Class | Used in |
|-------|---------|
| `BSLightingShaderProperty` | Skyrim SE and most FO4 meshes |
| `BSEffectShaderProperty` | Effect / glow / particle shaders |
| `BSDistantTreeShaderProperty` | Tree LOD (Skyrim SE) |
| `BSShaderPPLightingProperty` | Skyrim LE pre-SE |
| `NiShaderFO4` | FO4 — wraps the full `BGSM`/`BGEM` material system |

`NiShaderFO4` exposes many additional properties for FO4 material layers.

### Shader flags

Skyrim shaders expose their flags through boolean properties on the shader object:

```python
sh = shape.shader
print(sh.flag_vertex_alpha)   # True/False
sh.flag_skinned = True
sh.save_shader_attributes()
```

The flag names follow the `BSLightingShaderProperty` flag bit names.

---

## Collision

Bethesda NIFs use two collision systems:

- **Havok rigid-body collision** — used in all games; a node carries a `bhkCollisionObject`
  (or variant) which references a `bhkRigidBody` and a `bhkShape`.
- **FO4 native physics** — used for complex FO4 level-geometry; a `bhkNPCollisionObject`
  references a `bhkPhysicsSystem` that stores a raw Havok packfile blob.

### Accessing existing collision

```python
coll = node.collision_object   # NiCollisionObject subclass, or None
if coll:
    print(coll.blockname)      # e.g. "bhkCollisionObject"
    print(coll.flags)
```

### Havok rigid-body collision

```
NiNode
  └─ bhkCollisionObject  (or bhkBlendCollisionObject, etc.)
       ├─ .flags           → int
       └─ .body  ──────────→ bhkRigidBody (or bhkRigidBodyT)
                                 └─ .shape → bhkShape subclass
```

```python
body  = coll.body           # bhkRigidBody or bhkRigidBodyT
shape = body.shape          # bhkShape subclass

# Read shape properties by type
if shape.blockname == "bhkBoxShape":
    dims = shape.properties.dimensions     # (hx, hy, hz) half-extents

elif shape.blockname == "bhkCapsuleShape":
    p1     = shape.properties.point1
    p2     = shape.properties.point2
    radius = shape.properties.radius1

elif shape.blockname == "bhkSphereShape":
    radius = shape.properties.radius

elif shape.blockname == "bhkConvexVerticesShape":
    verts   = shape.vertices    # list[(x, y, z)]
    normals = shape.normals     # list[(x, y, z, w)]

elif shape.blockname == "bhkListShape":
    for child_shape in shape.children:
        print(child_shape.blockname)
```

#### Creating rigid-body collision

```python
# 1. Attach a collision object to a node
coll = root.add_collision(
    body           = None,
    flags          = 129,
    collision_type = PynBufferTypes.bhkCollisionObjectBufType)

# 2. Create a rigid body
body_buf = bhkRigidBodyBuf()
body_buf.mass = 10.0
body = coll.add_body(body_buf)

# 3. Add a box shape to the body
box_buf = bhkBoxShapeBuf()
box_buf.dimensions = (0.5, 0.5, 0.5)  # half-extents in Havok units
nif.add_shape(box_buf, parent=body)
```

#### Collision object types

| Class | `buffer_type` | Description |
|-------|--------------|-------------|
| `bhkCollisionObject` | `bhkCollisionObjectBufType` | Standard Havok collision |
| `bhkBlendCollisionObject` | `bhkBlendCollisionObjectBufType` | Blend collision (ragdolls) |
| `bhkNiCollisionObject` | `bhkNiCollisionObjectBufType` | NI collision |
| `bhkPCollisionObject` | `bhkPCollisionObjectBufType` | Phantom |
| `bhkSPCollisionObject` | `bhkSPCollisionObjectBufType` | Simple phantom |
| `bhkNPCollisionObject` | `bhkNPCollisionObjectBufType` | FO4 native physics |

#### Collision shape types

| Class | Description |
|-------|-------------|
| `bhkBoxShape` | Axis-aligned box |
| `bhkCapsuleShape` | Capsule (cylinder with hemispherical ends) |
| `bhkSphereShape` | Sphere |
| `bhkConvexVerticesShape` | Convex hull from a vertex list |
| `bhkConvexTransformShape` | Wrapper adding a transform to a child shape |
| `bhkListShape` | Compound shape (multiple children) |
| `bhkSimpleShapePhantom` | Non-colliding trigger volume |

### FO4 native physics (bhkNPCollisionObject)

FO4 uses this system for complex mesh collisions (level geometry, furniture, etc.).

```
NiNode
  └─ bhkNPCollisionObject
       └─ .physics_system  →  bhkPhysicsSystem
                                  ├─ .data      → bytes (raw Havok packfile)
                                  └─ .geometry  → (verts, faces) decoded geometry
```

```python
coll = root.collision_object         # bhkNPCollisionObject
ps   = coll.physics_system           # bhkPhysicsSystem

# Raw Havok packfile bytes (requires updated NiflyDLL)
raw = ps.data   # bytes, or b"" if DLL functions not available

# Decoded geometry
verts, faces = ps.geometry
# verts: list[(x, y, z)]  — Havok-unit coordinates
# faces: list[([v0, v1, v2], flags)]  — per-face indices and material flags
```

> **Note:** `ps.data` requires `getPhysicsSystemDataLen` / `getPhysicsSystemData` functions
> in the DLL. If these are absent the property returns `b""` silently, and `ps.geometry`
> returns empty lists.

#### Creating FO4 native-physics collision

Pass vertex/face geometry (preferred) or raw bytes:

```python
# From geometry (pack_convex_polytope is called internally)
coll = root.add_collision(
    body           = None,
    flags          = 0,
    collision_type = PynBufferTypes.bhkNPCollisionObjectBufType)

ps = bhkPhysicsSystem.New(
    nif,
    verts  = [(x, y, z), ...],
    faces  = [[v0, v1, v2], ...],
    parent = coll)

# From raw packfile bytes
ps = bhkPhysicsSystem.New(nif, data=raw_bytes, parent=coll)
```

Never call `bhk_autopack.pack_convex_polytope()` directly from application code;
always go through `bhkPhysicsSystem.New()`.

---

## Extra data blocks

Extra data blocks attach auxiliary metadata to nodes. They are discovered with
`node.get_extra_data()` and created with class-level `.New()` factory methods.

### BSXFlags

Extended Bethesda flags, typically attached to the root node.

```python
bsxf = root.get_extra_data(blockname="BSXFlags")
flags = bsxf.properties.flags   # int bitmask

# Create
bsxf = BSXFlags.New(nif, name="BSX", integer_value=202, parent=root)
```

Flag values are defined in `nifconstants.BSXFlagsValues`.

### BSBound

Bounding box for engine culling, attached to the root node.

```python
bound = root.get_extra_data(blockname="BSBound")
center       = bound.center        # (x, y, z)
half_extents = bound.half_extents  # (x, y, z)

# Create
bound = BSBound.New(nif,
    name         = "BBX",
    center       = (0, 0, 64),
    half_extents = (32, 32, 64),
    parent       = root)
```

### BSBehaviorGraphExtraData

Path to the Havok behaviour graph (`.hkx`), required for animated characters.

```python
bged = root.get_extra_data(blockname="BSBehaviorGraphExtraData")
print(bged.behavior_graph_file)       # str path
print(bged.controls_base_skeleton)    # bool

# Create
bged = BSBehaviorGraphExtraData.New(nif,
    name                   = "BGED",
    behavior_graph_file    = "Actors/Character/Behaviors/0_Master.hkx",
    controls_base_skeleton = False,
    parent                 = root)
```

### NiStringExtraData

An arbitrary named string, often used for weapon/armour slots (`"Prn"`, `"WeaponBack"`, …).

```python
sed = shape.get_extra_data(blockname="NiStringExtraData", name="Prn")
print(sed.string_data)   # e.g. "WeaponBack"
```

### NiIntegerExtraData

An arbitrary named integer.

```python
ied = node.get_extra_data(blockname="NiIntegerExtraData")
print(ied.integer_data)   # int

# Create
NiIntegerExtraData.New(nif, name="HDT", integer_value=1, parent=root)
```

### NiTextKeyExtraData

Named time points in an animation sequence.

```python
tked = node.get_extra_data(blockname="NiTextKeyExtraData")
for time, text in tked.keys:
    print(f"{time:.3f}  {text}")

# Create / modify
tked = NiTextKeyExtraData.New(nif, name="", keys=[], parent=node)
tked.add_key(0.0, "start")
tked.add_key(1.0, "end")
```

### BSFurnitureMarkerNode

Furniture interaction positions.

```python
fmn = root.get_extra_data(blockname="BSFurnitureMarkerNode")
for marker in fmn.furniture_markers:
    print(marker.offset, marker.heading, marker.animation_type)

# Create
fmn = BSFurnitureMarkerNode.New(nif,
    name              = "FRN",
    furniture_markers = [marker_buf_1, marker_buf_2],
    parent            = root)
```

### BSBoneLODExtraData

Maps bones to LOD levels. Read-only in the current API.

```python
blod = root.get_extra_data(blockname="BSBoneLODExtraData")
```

### BSConnectPointParents / BSConnectPointChildren

FO4 weapon attach-point data. Currently read-only; use `nif.connect_points_parent` /
`nif.connect_points_child` to access.

### Quick reference

| Class | `blockname` | Key properties |
|-------|-------------|----------------|
| `BSXFlags` | `"BSXFlags"` | `.properties.flags` (int) |
| `BSBound` | `"BSBound"` | `.center`, `.half_extents` |
| `BSBehaviorGraphExtraData` | `"BSBehaviorGraphExtraData"` | `.behavior_graph_file`, `.controls_base_skeleton` |
| `BSInvMarker` | `"BSInvMarker"` | `.properties.rotation`, `.properties.zoom` |
| `NiStringExtraData` | `"NiStringExtraData"` | `.string_data` |
| `NiIntegerExtraData` | `"NiIntegerExtraData"` | `.integer_data` |
| `NiTextKeyExtraData` | `"NiTextKeyExtraData"` | `.keys` list, `.add_key()` |
| `BSBound` | `"BSBound"` | `.center`, `.half_extents` |
| `BSFurnitureMarkerNode` | `"BSFurnitureMarkerNode"` | `.furniture_markers` |
| `BSBoneLODExtraData` | `"BSBoneLODExtraData"` | bone LOD levels |
| `BSConnectPointParents` | `"BSConnectPoint::Parents"` | connect-point descriptors |

---

## Animation and controllers

Animation data is stored in a hierarchy of controller objects linked to scene-graph nodes.

### Navigating controllers

```python
ctrl = node.controller          # first controller on the node
while ctrl:
    print(ctrl.blockname)
    interp = ctrl.interpolator  # NiInterpolator subclass
    ctrl   = ctrl.next_controller
```

### NiControllerManager and sequences

```python
for mgr in nif.controller_managers:
    for seq in mgr.controller_sequences:
        print(seq.name, seq.start_time, seq.stop_time)
        for link in seq.controller_links:
            print("  ", link.targetID, link.controllerType)
```

### Interpolator types

| Class | Purpose |
|-------|---------|
| `NiTransformInterpolator` | Position / rotation / scale track |
| `BSRotAccumTransfInterpolator` | Accumulated root transform |
| `NiFloatInterpolator` | Single float track |
| `NiBoolInterpolator` | Boolean (visibility) track |
| `NiPoint3Interpolator` | 3-component vector track |
| `NiBlend*Interpolator` | Blended variants of the above |

### Keyframe data

```python
td = interpolator.data          # NiTransformData, NiFloatData, or NiPosData

# NiTransformData
for key in td.translations:     # LinearVectorKey or QuadVectorKey
    print(key.time, key.value)
for key in td.rotations:        # LinearQuatKey
    print(key.time, key.value)
for key in td.scales:           # LinearScalarKey
    print(key.time, key.value)
```

### Controller classes (reference)

| Class | Description |
|-------|-------------|
| `NiTransformController` | Drives node position/rotation/scale |
| `NiMultiTargetTransformController` | Multi-bone transforms |
| `NiVisController` | Node visibility on/off |
| `NiAlphaController` / `BSNiAlphaPropertyTestRefController` | Alpha fade |
| `NiFloatInterpController` | Base for float shader controllers |
| `BSLightingShaderPropertyFloatController` | Lighting shader float parameter |
| `BSLightingShaderPropertyColorController` | Lighting shader colour |
| `BSEffectShaderPropertyFloatController` | Effect shader float parameter |
| `BSEffectShaderPropertyColorController` | Effect shader colour |

---

## Key types

### TransformBuf

`TransformBuf` (defined in `nifdefs.py`) represents a combined position + rotation + scale
transform.

```python
xf = TransformBuf()
xf.set_identity()

xf.translation = (x, y, z)            # 3-tuple of floats
xf.rotation    = [[r00, r01, r02],     # 3×3 row-major rotation matrix
                  [r10, r11, r12],
                  [r20, r21, r22]]
xf.scale       = 1.0

# Compose: parent_transform * child_transform
combined = parent_xf * child_xf

# Invert
inv = xf.invert()
```

### PynBufferTypes

`PynBufferTypes` (from `nifdefs.py`) is an `IntEnum` that tags the memory layout of every
property buffer. Each `NiObject` subclass sets `buffer_type` to one of these values, and the
ctypes struct passed to `nifly.getBlock` / `nifly.setBlock` must carry the same value in its
`bufType` field.

Common values:

| Name | Meaning |
|------|---------|
| `NiNodeBufType` | All `NiNode` subclasses |
| `NiShapeBufType` | Generic shape |
| `BSTriShapeBufType` | `BSTriShape` |
| `BSDynamicTriShapeBufType` | `BSDynamicTriShape` |
| `BSSubIndexTriShapeBufType` | `BSSubIndexTriShape` (FO4 segments) |
| `NiTriShapeBufType` | `NiTriShape` (Skyrim LE) |
| `NiTriStripsBufType` | `NiTriStrips` (Oblivion) |
| `BSLightingShaderPropertyBufType` | Skyrim/SE shader |
| `bhkCollisionObjectBufType` | Standard collision |
| `bhkNPCollisionObjectBufType` | FO4 native-physics collision |
| `bhkPhysicsSystemBufType` | FO4 Havok packfile data |
| `bhkRigidBodyBufType` | Rigid body |
| `bhkRigidBodyTBufType` | Rigid body (with transform) |
| `bhkBoxShapeBufType` | Box collision shape |
| `bhkCapsuleShapeBufType` | Capsule collision shape |
| `bhkConvexVerticesShapeBufType` | Convex-hull shape |
| `bhkListShapeBufType` | Compound shape |
| `BSXFlagsBufType` | `BSXFlags` extra data |
| `BSInvMarkerBufType` | Inventory marker extra data |

### NODEID_NONE

`NODEID_NONE = 0xFFFFFFFF` is the sentinel value indicating a null block reference.

```python
from io_scene_nifly.pyn.nifdefs import NODEID_NONE

if shape.properties.shaderID != NODEID_NONE:
    shader = nif.read_node(id=shape.properties.shaderID)
```

### read_node

`NifFile.read_node(id=None, handle=None, ...)` loads a block and returns an instance of the
most specific registered Python class:

```python
obj = nif.read_node(id=42)           # by block index
obj = nif.read_node(handle=ptr)      # by DLL handle (ctypes void*)
```

The class is chosen by looking up the block's `blockname` in `NiObject.block_types`.
If no matching class is registered the block is returned as a bare `NiNode`.

---

## Module-level helpers

| Function | Description |
|----------|-------------|
| `check_return(func, *args)` | Call a nifly DLL function that returns `0` on success; raise `Exception` on non-zero or if the error log is non-empty. |
| `check_msg(func, *args)` | Call a nifly function with any return type; raise if the error log is non-empty after the call. Returns the function's return value. |
| `check_id(func, *args)` | Call a nifly function that returns a block ID; raise if the result is `NODEID_NONE`. Returns the ID. |
| `get_weights_by_bone(weights_by_vert, used_groups)` | Re-pivot a per-vertex weight list into a per-bone dict; trims to 4 weights per vertex and normalises. |
| `get_weights_by_vertex(verts, weights_by_bone)` | Re-pivot a per-bone weight dict into a per-vertex list. |

---

## Extending with new block types

Add a subclass to `pynifly.py` and `NiObject.register_subclasses()` will pick it up
automatically at module load time (the call is at the bottom of the file).

```python
class MyNewBlock(NiObject):
    buffer_type = PynBufferTypes.MyNewBlockBufType   # add to nifdefs.py

    @classmethod
    def getbuf(cls, values=None):
        return MyNewBlockBuf(values)                 # ctypes struct from nifdefs.py

    @property
    def my_field(self):
        return self.properties.my_field
```

After that, `NifFile.read_node()` will return `MyNewBlock` instances for any block in a NIF
with the matching block-type name.

---

## HKX skeleton files

`hkxSkeletonFile` is a thin subclass of `NifFile` for Havok skeleton `.hkx` files (loaded
as converted XML). It exposes the same `nodes` and `shapes` interface.

```python
skel = hkxSkeletonFile("Actors/Character/CharacterAssets/skeleton.hkx")
print(skel.nodes.keys())
```

---

## Complete examples

### Reading a character mesh

```python
from io_scene_nifly.pyn.pynifly import NifFile

nif = NifFile("meshes/actors/character/character assets/malehead.nif")
print("Game:", nif.game)

for shape in nif.shapes:
    print(f"\n{shape.name}")
    print(f"  Vertices : {len(shape.verts)}")
    print(f"  Triangles: {len(shape.tris)}")
    print(f"  Diffuse  : {shape.textures.get('Diffuse', '(none)')}")
    if shape.has_skin_instance:
        print(f"  Bones    : {shape.bone_names[:4]} …")

# Check for flags on the root
bsxf = nif.root.get_extra_data(blockname="BSXFlags")
if bsxf:
    print("\nBSXFlags:", bsxf.properties.flags)
```

### Creating a simple FO4 static mesh

```python
from io_scene_nifly.pyn.pynifly import NifFile, TransformBuf
from io_scene_nifly.pyn.nifdefs import PynBufferTypes, NiShapeBuf

nif = NifFile()
nif.initialize("FO4", "output/cube.nif", root_type="BSFadeNode")

# Cube geometry
verts = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
         (-1,-1, 1),(1,-1, 1),(1,1, 1),(-1,1, 1)]
tris  = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),
         (0,1,5),(0,5,4),(1,2,6),(1,6,5),
         (2,3,7),(2,7,6),(3,0,4),(3,4,7)]
uvs   = [(0,0)] * 8

props = NiShapeBuf()
props.bufType = PynBufferTypes.BSTriShapeBufType

shape = nif.createShapeFromData(
    "Cube", verts, tris, uvs, normals=None,
    props=props, parent=nif.root)

nif.save()
```

### Reading FO4 native-physics collision geometry

```python
from io_scene_nifly.pyn.pynifly import NifFile

nif = NifFile("meshes/architecture/InsFloorMat01.nif")
coll = nif.root.collision_object

if coll and coll.blockname == "bhkNPCollisionObject":
    ps = coll.physics_system
    verts, faces = ps.geometry
    print(f"Collision: {len(verts)} verts, {len(faces)} faces")
    # verts: [(x, y, z), ...]  in Havok units
    # faces: [([v0, v1, v2], flags), ...]
```

### Cloning collision geometry from one NIF to another

```python
from io_scene_nifly.pyn.pynifly import NifFile, bhkPhysicsSystem
from io_scene_nifly.pyn.nifdefs import PynBufferTypes

src  = NifFile("source.nif")
dest = NifFile()
dest.initialize("FO4", "output.nif", root_type="BSFadeNode")

src_coll = src.root.collision_object
src_ps   = src_coll.physics_system
verts, face_pairs = src_ps.geometry
face_lists = [list(f) for f, _ in face_pairs]

# Attach collision to destination root
dest_coll = dest.root.add_collision(
    body           = None,
    flags          = 0,
    collision_type = PynBufferTypes.bhkNPCollisionObjectBufType)

bhkPhysicsSystem.New(dest, verts=verts, faces=face_lists, parent=dest_coll)

dest.save()
```
