# pynifly — Python wrapper for NiflyDLL

`pynifly.py` is the main Python interface to the NiflyDLL C++ library. It provides a
high-level, object-oriented API for reading and writing NIF files (NetImmerse Format), the
binary 3D asset format used by Bethesda games (Skyrim, Fallout 4, etc.).

---

## Quick start

```python
from pyn.pynifly import NifFile

# --- Read a NIF ---
nif = NifFile("path/to/mesh.nif")
print(nif.game)        # "SKYRIMSE"
print(nif.rootName)    # "Scene Root"

for shape in nif.shapes:
    print(shape.name, len(shape.verts), "verts")
    print("  shader:", shape.shader_block_name)
    print("  diffuse:", shape.textures.get("Diffuse"))

# --- Create a new NIF ---
nif = NifFile()
nif.initialize("SKYRIMSE", "out.nif")
nif.save()
```

---

## Architecture

```
NifFile                         ← the file itself
  └─ NiNode (root)              ← scene graph root
       ├─ NiNode (child nodes)
       │    └─ NiShape          ← mesh (verts, tris, UVs, skinning, shader)
       │    └─ NiCollisionObject ← linked collision
       └─ NiExtraData blocks    ← metadata (flags, markers, behaviour graphs)
```

All blocks in a NIF are subclasses of `NiObject`. Every `NiObject` wraps a *buffer struct*
defined in `nifdefs.py`; the buffer is filled by the DLL when the object is first accessed
via its `properties` attribute.

The DLL is accessed through the module-level `nifly` object loaded by `niflydll.py`.

---

## NifFile

The top-level class. Load a NIF by passing a path; create a new one by calling
`initialize()` after construction.

### Construction

```python
nif = NifFile("mesh.nif")                  # load existing
nif = NifFile()                            # blank
nif.initialize("FO4", "out.nif")           # set game + output path
```

`initialize(target_game, filepath, root_type="NiNode", root_name="Scene Root")`
creates the root node and registers the file with nifly.

### File operations

| Method / Property | Description |
|---|---|
| `nif.save()` | Write the NIF to `nif.filepath`. |
| `nif.game` | Game string: `"SKYRIM"`, `"SKYRIMSE"`, `"FO4"`, `"FO76"`, … |
| `nif.filepath` | Path used by the last `save()` / load. |
| `NifFile.message_log()` | Static. Returns the last nifly error string. |
| `NifFile.clear_log()` | Static. Clears the error buffer. |

### Navigating the scene graph

| Property / Method | Returns | Description |
|---|---|---|
| `nif.root` / `nif.rootNode` | `NiNode` | Root node (block 0). |
| `nif.nodes` | `dict[str, NiNode]` | All named nodes, keyed by name. |
| `nif.node_ids` | `dict[int, NiObject]` | All loaded blocks, keyed by block ID. |
| `nif.shapes` | `list[NiShape]` | All mesh shapes in the NIF. |
| `nif.shape_dict` | `dict[str, NiShape]` | Shapes keyed by name. |
| `nif.read_node(id)` | `NiObject` | Look up any block by integer block ID. |

### Shapes

```python
shape = nif.shape_dict["Helmet:0"]
verts  = shape.verts     # list of (x, y, z)
tris   = shape.tris      # list of (i0, i1, i2)
uvs    = shape.uvs       # list of (u, v)
normals = shape.normals  # list of (x, y, z)
```

Creating a mesh shape:

```python
new_shape = nif.createShapeFromData(
    "MyShape",
    verts=[(0,0,0), (1,0,0), (0,1,0)],
    tris=[(0,1,2)],
    uvs=[(0,0), (1,0), (0,1)],
    normals=[(0,0,1), (0,0,1), (0,0,1)],
    props=BSTriShapeProps(),
    parent=nif.root,
)
```

### Nodes

```python
node = nif.add_node("MyNode", xform=TransformBuf(), parent=nif.root)
nif.nodes["Bip01"]            # access by name
nif.nodes["Bip01"].children   # not directly available; traverse via DLL
```

### Extra data

Extra data blocks attach metadata to nodes. They are accessed through `NiNode`:

```python
bsx  = root.get_extra_data(blockname="BSXFlags", name="BSX")
bged = root.get_extra_data(blockname="BSBehaviorGraphExtraData", name="BGED")
for ed in root.extra_data(blockname="NiStringExtraData"):
    print(ed.name, ed.string_data)
```

### Cloth data

```python
for name, raw_bytes in nif.cloth_data:
    print(name, len(raw_bytes), "bytes")
```

### Connect points (FO4)

```python
for cp in nif.connect_points_parent:
    print(cp.name.decode())
```

### Animation controller managers

```python
for mgr in nif.controller_managers:
    for seq in mgr.sequences:
        print(seq.name)
```

### Name conversion

NIF names use forward slashes (`Actors/Character`) while Blender uses colons.
Use these helpers when crossing the boundary:

```python
blender = nif.blender_name("Actors/Character/Animations/NPC_Behavior.hkx")
nif_n   = nif.nif_name(blender)
```

---

## NiObject — base class for all blocks

Every block in a NIF inherits from `NiObject`. You rarely construct these directly;
`NifFile.read_node()` creates the right subclass from the DLL's block-name string.

| Property / Method | Description |
|---|---|
| `obj.blockname` | Block type name as stored in the NIF (e.g. `"BSTriShape"`). |
| `obj.id` | Integer block ID. |
| `obj.file` | Owning `NifFile`. |
| `obj.properties` | Lazy-loaded buffer struct (filled by `nifly.getBlock`). Write back with `obj.write_properties()`. |
| `obj.getbuf(values)` | Class method. Return a new empty buffer struct for this type. |

`NiObject.register_subclasses()` is called once at module load (line 4570) to populate
`NiObject.block_types` (name → class) and `NiObject.buffer_types` (bufType int → class).

---

## NiNode — scene graph node

Inherits `NiObjectNET → NiAVObject → NiNode`.

```python
node = nif.nodes["Bip01 Head"]
print(node.name)
print(node.flags)
xf = node.global_transform   # TransformBuf relative to world root
co = node.collision_object   # NiCollisionObject or None
```

### Extra data on nodes

```python
ed = node.get_extra_data(blockname="BSBehaviorGraphExtraData", name="BGED")
if ed:
    print(ed.behavior_graph_file)
```

### Named subclasses

All of the following behave like `NiNode` but carry their own `buffer_type`:

`BSFadeNode`, `BSLeafAnimNode`, `BSMasterParticleSystem`, `BSMultiBoundNode`,
`BSOrderedNode`, `BSRangeNode`, `BSTreeNode`, `BSValueNode`, `BSWeakReferenceNode`,
`NiBillboardNode`, `NiBone`, `NiLODNode`, `NiSortAdjustNode`, `NiSwitchNode`,
`BSFaceGenNiNode`.

---

## NiShape — mesh geometry

Inherits `NiNode → NiShape`. Concrete types: `BSTriShape`, `NiTriShape`,
`BSSubIndexTriShape`, `BSDynamicTriShape`, `BSMeshLODTriShape`, `NiTriStrips`, …

### Geometry

| Property | Type | Description |
|---|---|---|
| `shape.verts` | `list[(x,y,z)]` | Vertex positions. |
| `shape.tris` | `list[(i,j,k)]` | Triangle indices. |
| `shape.uvs` | `list[(u,v)]` | UV coordinates (1:1 with verts). |
| `shape.normals` | `list[(x,y,z)]` | Per-vertex normals. |
| `shape.colors` | `list[(r,g,b,a)]` | Per-vertex colours, or `None`. |

### Shader and textures

```python
shader = shape.shader           # NiShader subclass
diffuse = shape.textures.get("Diffuse", "")
shape.set_texture("Diffuse", "textures/actors/character/face.dds")
shader.save_shader_attributes() # write changes to nif
```

### Skinning

```python
if shape.has_skin_instance:
    for bone in shape.bone_names:
        weights = shape.bone_weights[bone]  # [(vert_idx, weight), ...]
```

Add skinning when building a new shape:

```python
shape.skin()
shape.add_bone("Bip01 Head", xform=TransformBuf())
shape.setShapeWeights("Bip01 Head", [(0, 1.0), (1, 0.8)])
```

### Partitions (Skyrim) and Segments (FO4)

```python
# Skyrim
parts = shape.partitions           # list[SkyPartition]
tri_parts = shape.partition_tris   # list[int], 1:1 with shape.tris

# FO4
segs = shape.partitions            # list[FO4Segment]
```

---

## Collision classes

### Standard collision (Skyrim / FO4 with bhkRigidBody)

```
NiCollisionObject
  └─ NiCollisionObject subclasses:
       bhkCollisionObject, bhkBlendCollisionObject,
       bhkPCollisionObject, bhkSPCollisionObject
           └─ .body  → bhkWorldObject (bhkRigidBody / bhkRigidBodyT / bhkSimpleShapePhantom)
                           └─ .shape → bhkShape subclass
```

```python
co = node.collision_object          # NiCollisionObject or None
body = co.body                      # bhkRigidBody / bhkRigidBodyT
shape = body.shape                  # bhkBoxShape, bhkCapsuleShape, etc.
print(co.flags, body.properties.mass)
```

Collision shapes: `bhkBoxShape`, `bhkCapsuleShape`, `bhkSphereShape`,
`bhkConvexVerticesShape`, `bhkListShape`, `bhkConvexTransformShape`.

### FO4 native physics (bhkNPCollisionObject)

FO4 level geometry uses a native Havok packfile blob stored in a `bhkPhysicsSystem` block,
referenced by `bhkNPCollisionObject`.

```python
co = root.collision_object
assert co.blockname == "bhkNPCollisionObject"

ps = co.physics_system              # bhkPhysicsSystem
raw = ps.data                       # bytes — raw Havok packfile
verts, faces = ps.geometry          # decoded via bhk_autounpack.parse_bytes
# verts: list[(x,y,z)] in Havok units
# faces: list[((i0,i1,i2), group_name)]
```

> **Note:** `ps.data` requires two DLL functions (`getPhysicsSystemDataLen` /
> `getPhysicsSystemData`) that must be present in the NiflyDLL build. If they are absent
> `ps.data` returns `b""` silently.

---

## Animation classes

### Interpolators

| Class | Buffer type | Purpose |
|---|---|---|
| `NiTransformInterpolator` | `NiTransformInterpolatorBufType` | Position/rotation/scale track |
| `NiFloatInterpolator` | `NiFloatInterpolatorBufType` | Single float track |
| `NiBoolInterpolator` | `NiBoolInterpolatorBufType` | Boolean track |
| `NiPoint3Interpolator` | `NiPoint3InterpolatorBufType` | 3-component vector track |
| `NiBlend*Interpolator` | — | Blended versions of the above |

Each interpolator links to a data block:

```python
interp = some_controller.interpolator
data = interp.data       # NiTransformData, NiFloatData, etc.
```

### Keyframe data

| Class | Keys |
|---|---|
| `NiTransformData` | Translation, rotation, scale keys |
| `NiFloatData` | Scalar float keys |
| `NiPosData` | Position (vector) keys |

Key types: `LinearScalarKey`, `LinearVectorKey`, `LinearQuatKey`,
`QuadScalarKey`, `QuadVectorKey`.

### Controllers

| Class | Purpose |
|---|---|
| `NiTransformController` | Per-bone transform animation |
| `NiMultiTargetTransformController` | Drives multiple bones |
| `NiVisController` | Visibility on/off |
| `NiAlphaController` | Alpha fade |
| `BSLightingShaderPropertyFloatController` | Shader float parameter |
| `BSLightingShaderPropertyColorController` | Shader colour parameter |
| `BSEffectShaderProperty{Float,Color}Controller` | Effect shader parameters |

```python
ctrl = node.controller                  # first controller on node
ctrl.next_controller                    # linked list of additional controllers
ctrl.interpolator                       # associated interpolator
ctrl.is_cyclic                          # True if looping
```

### Sequences

`NiControllerSequence` wraps a named animation clip. Access via
`NifFile.controller_managers`:

```python
mgr = nif.controller_managers[0]
for seq in mgr.sequences:
    print(seq.name, seq.start_time, seq.stop_time)
    for link in seq.controller_links:
        print(" ", link.node_name, link.property_type)
```

---

## Shader classes

`NiShader` is the base; the concrete classes carry game-specific buffer types.

| Class | Used in |
|---|---|
| `BSLightingShaderProperty` | Skyrim / FO4 standard meshes |
| `BSEffectShaderProperty` | Effect, glow, and particle shaders |
| `BSDistantTreeShaderProperty` | Tree LOD |
| `BSShaderPPLightingProperty` | Skyrim pre-SE |

```python
sh = shape.shader
print(sh.name)
print(sh.textures)                # dict slot→path

# Shader flags
print(sh.flag_vertex_alpha)       # bool property
sh.flag_vertex_alpha = True
sh.save_shader_attributes()       # write back

# Alpha property
ap = shape.alpha_property
shape.has_alpha_property = True
```

---

## Extra data classes

Extra data blocks are attached to nodes and carry supplementary metadata.

| Class | `blockname` | Key properties |
|---|---|---|
| `BSXFlags` | `"BSXFlags"` | `.flags` (int) |
| `BSBehaviorGraphExtraData` | `"BSBehaviorGraphExtraData"` | `.behavior_graph_file`, `.controls_base_skeleton` |
| `BSInvMarker` | `"BSInvMarker"` | `.rotation` (tuple), `.zoom` |
| `NiStringExtraData` | `"NiStringExtraData"` | `.string_data` |
| `NiIntegerExtraData` | `"NiIntegerExtraData"` | `.integer_data` |
| `NiTextKeyExtraData` | `"NiTextKeyExtraData"` | `.text_keys` list |
| `BSBound` | `"BSBound"` | `.center`, `.half_extents` |
| `BSFurnitureMarkerNode` | `"BSFurnitureMarkerNode"` | `.furniture_markers` |
| `BSBoneLODExtraData` | `"BSBoneLODExtraData"` | bone LOD levels |
| `BSConnectPointParents` | `"BSConnectPointParents"` | `.connect_points` |

---

## Module-level helpers

| Function | Purpose |
|---|---|
| `check_return(func, *args)` | Call a nifly DLL function; raise on non-zero return or error log. |
| `check_msg(func, *args)` | Call a nifly function; raise if the error log is non-empty. |
| `check_id(func, *args)` | Call a nifly function that returns an ID; raise if `NODEID_NONE`. |
| `get_weights_by_bone(weights_by_vert, used_groups)` | Re-pivot vertex weight list → per-bone dict. |
| `get_weights_by_vertex(verts, weights_by_bone)` | Re-pivot per-bone dict → per-vertex list. |

---

## Partition / Segment helpers

| Class | Used for |
|---|---|
| `Partition` | Abstract base |
| `SkyPartition` | Skyrim body-part partitions (head, hands, …) |
| `FO4Segment` | FO4 material segments |
| `FO4Subsegment` | Sub-divisions of FO4 segments |

---

## HKX skeleton files

`hkxSkeletonFile` is a thin subclass of `NifFile` that loads Havok skeleton `.hkx` (or
converted XML) files. It exposes the same `nodes` / `shapes` interface so the rest of the
codebase can treat skeletons and NIFs uniformly.

```python
skel = hkxSkeletonFile("Actors/Character/CharacterAssets/skeleton.hkx")
print(skel.nodes)
```

---

## Registering new block types

Any new `NiObject` subclass added to this module is automatically picked up by
`NiObject.register_subclasses()` (called once at the bottom of the file). Set:

```python
class MyNewBlock(NiObject):
    buffer_type = PynBufferTypes.MyNewBlockBufType  # add to nifdefs.py

    @classmethod
    def getbuf(cls, values=None):
        return MyNewBlockBuf(values)
```

After that, `NifFile.read_node()` will create `MyNewBlock` objects whenever it encounters
a block with that name in a NIF file.
