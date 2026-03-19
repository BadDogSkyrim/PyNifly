# FO4 Havok Packfile Format (hk_2014.1.0)

Fallout 4 stores collision geometry in `bhkPhysicsSystem` blocks as raw
Havok packfile blobs. Each packfile is a self-contained binary containing
one `hknpPhysicsSystemData` object with one or more rigid bodies and their
collision shapes.

## NIF Block Hierarchy

```
bhkNPCollisionObject
  ├─ dataID  → bhkPhysicsSystem     ← raw packfile bytes in .data
  └─ bodyID  → index into bodies array
```

Multiple NIF nodes can reference the same `bhkPhysicsSystem`, each selecting
a different body by `bodyID`.

## File Structure

All values are little-endian. Pointers are 8 bytes (64-bit packfile format).

The file has a fixed-size header region (0x100 bytes) followed by variable-length
section data. The header region contains exactly one global file header and
three section headers.

```
0x000–0x03F: Global file header      (0x40 bytes, exactly one)
0x040–0x07F: Section header 0        (__classnames__)
0x080–0x0BF: Section header 1        (__types__, always empty)
0x0C0–0x0FF: Section header 2        (__data__)
0x100+:      __classnames__ data
             __data__ section (objects)
             local fixup table
             global fixup table
             virtual fixup table
```

The __classnames__ section maps hash values to class names (like
`hknpConvexPolytopeShape`). The __data__ section contains the actual physics
objects — the PhysicsSystemData, body info, and shape geometry. The __types__
section is always empty in FO4 packfiles.

Because the packfile is a flat byte stream, pointers can't hold real addresses.
Instead, every pointer slot is written as zeros during construction, and three
**fixup tables** at the end of the file tell the loader how to patch them:

- **Local fixups** resolve pointers within the data section (e.g. an hkArray
  pointing to its element data a few hundred bytes later).
- **Global fixups** resolve pointers between sections (e.g. a BodyCInfo's
  shape pointer targeting a shape object elsewhere in the data section, or
  a reference into classnames).
- **Virtual fixups** associate each object with its class name, so the loader
  knows what type each blob of bytes represents.

## Global File Header (0x40 bytes)

| Offset | Size | Field | Value |
|--------|------|-------|-------|
| 0x00 | 8 | magic | `57 E0 E0 57 10 C0 C0 10` |
| 0x08 | 4 | userTag | 0 |
| 0x0C | 4 | fileVersion | 11 |
| 0x10 | 4 | layoutRules | `08 01 00 01` (ptrSize=8, little-endian) |
| 0x14 | 4 | numSections | 3 |
| 0x18 | 4 | contentsSectionIndex | 2 (data section) |
| 0x1C | 4 | contentsSectionOffset | 0 |
| 0x20 | 4 | contentsClassNameIndex | 0 |
| 0x24 | 4 | contentsClassNameOffset | offset of `hknpPhysicsSystemData` in classnames |
| 0x28 | 18 | contentsVersion | `hk_2014.1.0-r1\0\xFF` |
| 0x38 | 4 | flags | 0 |
| 0x3C | 4 | maxPredicate | 21 |

## Section Headers (0x40 bytes each)

Three section headers at offsets 0x40, 0x80, 0xC0:

| Offset | Size | Field |
|--------|------|-------|
| 0x00 | 20 | sectionName (null-terminated, padded with 0xFF) |
| 0x14 | 4 | absStart (absolute file offset of section data) |
| 0x18 | 4 | localFixup (relative to absStart) |
| 0x1C | 4 | globalFixup (relative to absStart) |
| 0x20 | 4 | virtualFixup (relative to absStart) |
| 0x24 | 4 | exports (= end of data, before fixups) |
| 0x28 | 4 | imports (same as exports) |
| 0x2C | 4 | end (same as exports) |
| 0x30 | 16 | padding (0xFF) |

The `exports` and `imports` fields exist in the Havok packfile spec for
linking multiple packfiles together — an exporting packfile exposes named
symbols, and an importing packfile references them. FO4 NIF packfiles are
always self-contained, so these fields are unused and set equal to the end
of the object data (i.e. where the fixup tables begin).

## Classnames Section

Sequence of entries, each:

```
u32  hash
u8   0x09          (type flag)
char name[]        (null-terminated)
```

Padded to 16-byte boundary with 0xFF.

Class entries vary by shape type. All packfiles include:

- `hkClass`, `hkClassMember`, `hkClassEnum`, `hkClassEnumItem`
- `hknpPhysicsSystemData`

Polytope adds: `hknpConvexPolytopeShape`, `hkRefCountedProperties`,
`hknpShapeMassProperties`.

Compressed mesh adds: `hknpCompressedMeshShape`, `hknpCompressedMeshShapeData`,
`hknpBSMaterialProperties`.

Sphere adds: `hknpSphereShape`.

Compound adds: `hknpDynamicCompoundShape`.

## Data Section Layout

The data section always begins with an `hknpPhysicsSystemData`, followed by
per-body arrays, then the shape objects. A typical single-polytope layout:

```
+0x0000: hknpPhysicsSystemData       (0x80 bytes)
+0x0080: body_props[N]               (0x110 bytes each)
         [dyn_motion, if dynamic]    (0x40 bytes)
         [dyn_inertia, if dynamic]   (0x40 bytes)
+0x....: BodyCInfo[N]                (0x60 bytes each)
+0x....: ShapeEntry[N]               (0x10 bytes each)
+0x....: shape objects (polytope, compressed mesh, sphere, etc.)
+0x....: hkRefCountedProperties      (0x20 bytes, polytope/CM only)
+0x....: hknpShapeMassProperties     (0x30 bytes, polytope/CM only)
```

## hknpPhysicsSystemData (PSD, 0x80 bytes)

Six `hkArray` slots (16 bytes each) plus 16 bytes padding:

| Offset | Array | Count |
|--------|-------|-------|
| 0x00 | (unused) | 0 |
| 0x10 | body_props | num_bodies |
| 0x20 | dyn_motion | 1 if dynamic, else 0 |
| 0x30 | dyn_inertia | 1 if dynamic, else 0 |
| 0x40 | BodyCInfo | num_bodies |
| 0x50 | (unused) | 0 |
| 0x60 | ShapeEntry | num_bodies |
| 0x70 | (padding) | — |

Each `hkArray` is 16 bytes:

```
+0x00: u64  pointer     (local fixup → array data)
+0x08: u32  size
+0x0C: u32  capacity    (= size | 0x80000000)
```

## body_props (0x110 bytes per body)

Physics material and simulation parameters.

| Offset | Size | Field | Encoding |
|--------|------|-------|----------|
| 0x00 | 2 | friction | truncated float16 |
| 0x04 | 2 | restitution | truncated float16 |
| 0x48 | 4 | gravityFactor | float32 |
| 0x50 | 2 | maxLinearVelocity | truncated float16 |
| 0x54 | 2 | maxAngularVelocity | truncated float16 |
| 0x58 | 2 | linearDamping | truncated float16 |
| 0x5C | 2 | angularDamping | truncated float16 |
| 0x84 | 4 | inverseMass | float32 (1.0/mass) |
| 0x88 | 4 | density | float32 (mass/volume) |
| 0x10A | 1 | collisionResponse | 0=contact, 1=none |

### Truncated Float16 Encoding

The upper 16 bits of a 32-bit IEEE float, stored as a `u16`:

```python
# Decode
value = struct.unpack('<f', struct.pack('<I', u16 << 16))[0]

# Encode
u16 = struct.unpack('<I', struct.pack('<f', value))[0] >> 16
```

This gives ~3 decimal digits of precision. Vanilla defaults: friction=0.5,
restitution=0.4.

## BodyCInfo (0x60 bytes per body)

Rigid body definition — shape pointer, position, and orientation.

| Offset | Size | Field |
|--------|------|-------|
| 0x00 | 8 | shape pointer (global fixup → shape object) |
| 0x08 | 8 | flags (`7FFFFFFF 7FFFFFFF`) |
| 0x10 | 8 | type/count fields |
| 0x18 | 24 | (zeros) |
| 0x30 | 12 | position (x, y, z) float32, Havok space |
| 0x3C | 4 | (padding) |
| 0x40 | 16 | quaternion (x, y, z, w) float32, identity = (0,0,0,1) |
| 0x50 | 16 | (zeros) |

### Body Transform Semantics

- **Non-identity rotation**: body transform = NIF node's world transform.
  Apply to vertices to get world-space positions.
- **Identity rotation**: position is centre-of-mass, not node position.
  Vertices are in node-local space. Don't apply transform to verts.
- **Sphere shapes**: the shape object has no geometry, just a radius. The
  body position is the sphere center in Havok space.

## ShapeEntry (0x10 bytes per body)

```
+0x00: u64  shape pointer (global fixup → shape object)
+0x08: u64  (reserved, zeros)
```

## dyn_motion (0x40 bytes, dynamic bodies only)

Data for the PSD +0x20 array. Engine defaults for dynamic simulation.
Usually constant across all FO4 NIFs.

| Offset | Size | Field | Default |
|--------|------|-------|---------|
| 0x08 | 4 | gravityFactor | 1.0 |
| 0x10 | 4 | maxLinearVelocity | 104.375 |
| 0x14 | 4 | maxAngularVelocity | 31.57 |
| 0x18 | 4 | linearDamping | 0.1 |
| 0x1C | 4 | angularDamping | 0.05 |

## dyn_inertia (0x40 bytes, dynamic bodies only)

Data for the PSD +0x30 array. Per-body mass and inertia tensor.

| Offset | Size | Field |
|--------|------|-------|
| 0x04 | 4 | inverseMass (float32, 1/mass) |
| 0x08 | 4 | density (float32, mass/volume) |
| 0x20 | 4 | inertia_xx (float32) |
| 0x24 | 4 | inertia_yy (float32) |
| 0x28 | 4 | inertia_zz (float32) |

## Shape Objects

### hknpConvexPolytopeShape (variable size)

Convex hull defined by vertices, face planes, and a face-vertex-index array.

```
+0x00: 0x30-byte fixed header
+0x30: u16 numVertices, u16 verticesOffset (=0x20), 12 bytes zeros
+0x40: u16 numVerts2, u16 planesOff, u16 numPlanes,
       u16 facesOff, u16 numFVI, u16 fviOff, 4 bytes zeros
+0x50: vertices[]     (numVerts × 16 bytes)
       planes[]       (numPlanes × 16 bytes)
       28-byte gap
       faces[]        (numPlanes × 4 bytes)
       4-byte gap
       fvi[]          (numFVI × 1 byte)
       [padded to 8-byte boundary]
```

**Vertex (16 bytes):** `float x, y, z; u32 w` where `w = 0x3F000000 | (index & 0xFF)`.

**Face (4 bytes):** `u16 firstFVI; u8 numVtx; u8 flags`.

**FVI:** flat array of vertex indices, one byte each.

The 0x30-byte fixed header is mostly undeciphered. Known fields:

| Offset | Size | Field |
|--------|------|-------|
| 0x00 | 16 | vtable/parent pointers (zeros) |
| 0x10 | 4 | type/quality flags (0x01000103) |
| 0x14 | 4 | convex_radius (float32) |
| 0x18 | 4 | large_convex_radius (purpose unclear) |
| 0x1C | 20 | unknown (zeros) |

### hknpCompressedMeshShape (0xC0 bytes) + ShapeData

Two objects: a shape header (0xC0) pointing to a ShapeData (0xA0+).

**ShapeData arrays:**

| Offset | Array | Contents |
|--------|-------|----------|
| 0x20 | aabb_min | vec4 (min corner of bounding box) |
| 0x30 | aabb_max | vec4 (max corner of bounding box) |
| 0x50 | sections | Section structs (0x60 each) |
| 0x60 | quadIndices | Packed quad/triangle indices |
| 0x80 | packedVertices | 11-11-10 bit packed vertices |

**Packed vertex encoding (u32):**

```
qx = (v >>  0) & 0x7FF     (11 bits)
qy = (v >> 11) & 0x7FF     (11 bits)
qz = (v >> 22) & 0x3FF     (10 bits)

x = section.base_x + qx * section.scale_x
y = section.base_y + qy * section.scale_y
z = section.base_z + qz * section.scale_z
```

### hknpSphereShape (0x50 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0x10 | 4 | flags (0x01000111) |
| 0x14 | 4 | radius (float32, Havok space) |
| 0x30 | 4 | flags2 (0x00100004) |
| 0x4C | 4 | value (0.5) |

The sphere center is stored in the BodyCInfo position field, not in the
shape object itself.

### hknpDynamicCompoundShape

Container for multiple child shapes with per-instance transforms. Each
instance references a child shape (typically `hknpConvexPolytopeShape`)
and carries a position/rotation transform.

## Fixup Tables

Three fixup tables follow the data section objects, in order.

### Local Fixups

Resolve pointers within the same section (e.g. hkArray → its data).

```
u32 src_offset    (offset in data section where pointer lives)
u32 dst_offset    (offset in data section the pointer targets)
```

Terminated by `FFFFFFFF FFFFFFFF`.

### Global Fixups

Resolve pointers between sections (e.g. BodyCInfo shape_ptr → shape object,
or hkRefCountedProperties → classnames).

```
u32 src_offset    (offset in data section)
u32 section_idx   (0=classnames, 1=types, 2=data)
u32 dst_offset    (offset in target section)
```

Terminated by `FFFFFFFF FFFFFFFF FFFFFFFF`.

### Virtual Fixups

Associate objects with their class names (for type identification).

```
u32 obj_offset    (offset in data section where object starts)
u32 section_idx   (always 0 = classnames)
u32 name_offset   (offset in classnames section)
```

Terminated by `FFFFFFFF FFFFFFFF FFFFFFFF`.

## Fields NOT in the Packfile

These `bhkRigidBody` properties from Skyrim's collision system have no
equivalent in the FO4 packfile format:

- `penetrationDepth`
- `motionSystem`
- `deactivatorType`
- `qualityType`

## References

- PyNifly parser: `io_scene_nifly/pyn/bhk_autounpack.py`
- PyNifly packer: `io_scene_nifly/pyn/bhk_autopack.py`
- PyNifly collision import/export: `io_scene_nifly/nif/collision.py`
