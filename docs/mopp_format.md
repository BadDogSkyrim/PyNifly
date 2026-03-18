# MOPP Bytecode Format

MOPP (Memory Optimized Partial Polytope) is a binary BVH (Bounding Volume
Hierarchy) used by Havok physics to accelerate collision detection in Skyrim
and other Bethesda games. The MOPP tree lives in a `bhkMoppBvTreeShape` block
and wraps a child shape containing the actual collision geometry.

## NIF Block Hierarchy

```
bhkCollisionObject
  └─ bhkRigidBody
       └─ bhkMoppBvTreeShape        ← MOPP bytecode + origin + scale
            └─ bhkCompressedMeshShape   (Skyrim SE)
            or bhkPackedNiTriStripsShape (Skyrim LE)
```

## How MOPP Works

The MOPP tree is a spatial search structure. Given a query (a point, ray, or
bounding volume), the engine walks the tree from root to leaves. Each internal
node tests the query against a splitting plane and directs traversal to one or
both children. Leaf nodes report which triangles the query might intersect.

The narrowphase then does exact geometry tests on only those candidate
triangles — typically a tiny fraction of the total mesh.

## Coordinate System

MOPP bytecode operates in a scaled integer coordinate space (0-254 range per
axis). The conversion from Havok world coordinates is:

```
scaled = 254.0 * (world_coord - origin[axis]) / largest_dim
```

Where:
- `origin` is the expanded AABB minimum (stored in the bhkMoppBvTreeShape)
- `largest_dim` is the largest axis extent of the expanded AABB
- The `scale` field stored in the NIF is 1.0 for Skyrim and is ignored

The root of the MOPP tree typically has three FILTER instructions that
establish the bounding box on each axis.

## Opcodes

### Rescale (0x01-0x04)

```
01-04  XX YY ZZ
```

Shift = opcode value (1-4). Subtracts (XX, YY, ZZ) from the current scaled
coordinates and multiplies by `2^shift`. Used to increase precision when
descending deep into the tree. Vanilla Skyrim NIFs use these; our compiler
does not (sufficient precision for typical meshes).

### Jump (0x05-0x06)

```
05  CC          → jump CC bytes forward (from end of instruction)
06  CC CC       → jump CC_CC bytes forward (16-bit offset)
```

Unconditional goto. Used by vanilla Havok to share subtrees between branches
(compression optimization). The target may be in a sibling branch's code.

### Output Base (0x09-0x0B)

```
09  II          → output_base += II
0A  II II       → output_base += II_II
0B  II II II II → output_base = II_II_II_II
```

Sets or adjusts a base value that is added to all subsequent LEAF output IDs.
Used for compression when consecutive leaves share a common prefix.

### Split (0x10-0x1C)

```
10-12  BB AA CC     → axis-aligned split (X/Y/Z), 1-byte jump
13-1C  BB AA CC     → diagonal split, 1-byte jump
```

- Axis = opcode - 0x10 (0=X, 1=Y, 2=Z, 3+=diagonals)
- If query coordinate < BB: traverse left child (immediately follows)
- If query coordinate >= AA: traverse right child (at offset CC from end of instruction)
- When AA < BB, there is an overlap zone where both children are traversed

Diagonal axes (vanilla only, our compiler uses 0-2):

| Opcode | Axis | Coordinate |
|--------|------|-----------|
| 0x13 | YpZ | (Y + Z) / 2 |
| 0x14 | nYpZ | 127 - Y/2 + Z/2 |
| 0x15 | XpZ | (X + Z) / 2 |
| 0x16 | nXpZ | 127 + X/2 - Z/2 |
| 0x17 | XpY | (X + Y) / 2 |
| 0x18 | nXpY | 127 + X/2 - Y/2 |
| 0x19 | XpYpZ | (X + Y + Z) / 3 |
| 0x1A | XpYnZ | body diagonal |
| 0x1B | XnYpZ | body diagonal |
| 0x1C | nXpYpZ | body diagonal |

### Half-Split (0x20-0x22)

```
20-22  XX CC     → split with single threshold
```

Like Split but with one threshold value instead of separate hi/lo bounds.

### Split16 (0x23-0x25)

```
23-25  BB AA CC CC DD DD    → 16-bit jump offsets
```

Same as Split but with 2-byte offsets for both children. Used when a subtree
exceeds 255 bytes.

- If coordinate < BB: jump to CC_CC bytes after end of instruction
- If coordinate >= AA: jump to DD_DD bytes after end of instruction

### Filter (0x26-0x28)

```
26-28  AA BB     → axis-aligned bounding filter
```

- Axis = opcode - 0x26 (0=X, 1=Y, 2=Z)
- If query coordinate < AA or >= BB: stop traversal (filtered out)
- Otherwise: continue to next instruction

Narrows the active region on one axis. The root typically has three filters
establishing the global AABB.

### Filter24 (0x29-0x2B)

```
29-2B  AA AA AA BB BB BB    → 24-bit precision filter
```

Same as Filter but with 3-byte bounds for higher precision.

### Leaf (0x30-0x52)

```
30-4F              → output_base + (opcode - 0x30)   (inline, 0-31)
50  II             → output_base + II                 (8-bit)
51  II II          → output_base + II_II              (16-bit)
52  II II II       → output_base + II_II_II           (24-bit)
```

Terminal node — reports a triangle ID to the collision system. The ID encodes
which triangle to test in the narrowphase.

### Output ID Encoding for bhkCompressedMeshShapeData

For compressed mesh (SE), the output ID encodes chunk index, winding, and
triangle-within-chunk:

```
output_id = (chunk_index << bitsPerWIndex) | (winding << bitsPerIndex) | tri_in_chunk
```

Where:
- `chunk_index` is 1-based (0 = bigTris)
- `winding` is 0 (CCW) or 1 (CW) — from triangle strip alternation
- `tri_in_chunk` is the triangle's position within the chunk
- `bitsPerIndex` and `bitsPerWIndex` are stored in the data block

For packed strips (LE), output IDs are sequential triangle indices.

## Using the Disassembler

### From Python

```python
from pyn.mopp_compiler import disassemble_mopp
from pyn.pynifly import NifFile

nif = NifFile("path/to/file.nif")
cs = nif.root.collision_object.body.shape  # bhkMoppBvTreeShape
mopp_bytes, origin, scale = cs.mopp_data

lines = disassemble_mopp(mopp_bytes, origin, scale)
for line in lines:
    print(line)
```

### Output Format

The disassembler produces an indented tree showing the MOPP structure:

```
[0000] FILTER Z  00=-0.0010..33=0.3809
[0003] FILTER Y  00=-0.3590..5F=0.3590
[0006] FILTER X  00=-0.9700..FF=0.9700
[0009] SPLIT16 Z  <33=0.3809 | >=30=0.3656
  if Z < 33=0.3809:
    [0010] SPLIT16 Y  <5F=0.3590 | >=4F=0.2444
      if Y < 5F=0.3590:
        [0017] SPLIT XpZ  <1C | >=0C
          if XpZ < 1C:
            [001B] JUMP -> 002B
          if XpZ >= 0C:
            ...
  if Z >= 30=0.3656:
    [01B6] FILTER Y  0D=-0.2597..51=0.2520
    ...
```

Each line shows:
- `[XXXX]` — byte offset in the MOPP data
- Instruction mnemonic and parameters
- `XX=Y.YYYY` — raw byte value = world-space Havok coordinate (when origin is known)
- Indentation reflects tree depth; splits show both child branches

### Standalone Usage

```
cd io_scene_nifly/pyn
python mopp_compiler.py path/to/file.nif
```

### World-Space Annotations

When `origin` is provided, the disassembler derives `largest_dim` from the root
FILTER nodes (the axis spanning 00..FF) and annotates bound bytes with
world-space Havok coordinates. For example, `33=0.3809` means byte value 0x33
maps to Z=0.3809 in Havok space.

Diagonal axis values (XpZ, nYpZ, etc.) are not annotated since they combine
multiple axes.

## Using the Verifier

The MOPP verifier (`tests/mopp_verifier.py`) tests tree quality:

```python
from mopp_verifier import verify_all

passed, messages = verify_all(
    mopp_bytes, origin, largest_dim,
    verts, tris, output_ids, radius=0.005)
for m in messages:
    print(m)
```

Three checks:
1. **Correctness** — sample random points in each triangle's AABB; verify the
   triangle's output ID is in the walker's result set. Catches false negatives.
2. **Completeness** — sample random points globally; verify all returned output
   IDs are valid. Catches garbage leaf values.
3. **Tightness** — sample points outside all triangle AABBs; count false
   positive hits. Lower is better (fewer unnecessary narrowphase tests).

### Standalone Usage

```
cd tests
python mopp_verifier.py path/to/file.nif
```

Runs tightness analysis on a NIF's MOPP tree.

## Using the Compiler

```python
from pyn.mopp_compiler import compile_mopp

# verts: list of (x, y, z) in Havok space
# tris: list of (i, j, k) vertex index triples
# output_ids: optional per-triangle IDs (default: sequential 0, 1, 2, ...)
code, origin, scale = compile_mopp(verts, tris, radius=0.005, output_ids=None)
```

The compiler builds an axis-aligned BVH with median splits. It does not use
diagonal splits, shared subtrees, or output base compression — these are
vanilla Havok optimizations that produce smaller trees but are not functionally
required.

## Comparison: Our Compiler vs Vanilla Havok

For the noblecrate01 collision (52 triangles):

| | Vanilla | Ours |
|---|---------|------|
| Size | 506 bytes | 205 bytes |
| Split types | Axis + diagonal | Axis only |
| Shared subtrees | Yes (JUMP) | No |
| Output compression | SET_OUTPUT + relative | Direct |
| Tightness | ~2 avg false positives | ~20 avg false positives |

Our tree is actually smaller (fewer instructions due to no diagonals) but
looser (more false positives for the narrowphase). Both produce correct
collision behavior in-game.

## References

- [niftools wiki: Havok MOPP Data format](https://github.com/niftools/nifxml/wiki/Havok-MOPP-Data-format)
- PyNifly source: `io_scene_nifly/pyn/mopp_compiler.py`
- PyNifly verifier: `tests/mopp_verifier.py`
