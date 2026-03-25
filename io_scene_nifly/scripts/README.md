# PyNifly Scripts

Utility scripts for inspecting and debugging NIF files. These ship with the PyNifly addon and can be run from the command line.

All scripts require the PyNifly DLL to be built and accessible. Run from the PyNifly repository root or ensure `io_scene_nifly` is on your Python path.

---

## dump_collision.py

Dumps the full collision structure of a Skyrim SE NIF file: rigid body properties, MOPP tree, compressed mesh chunks (vertices, indices, strips, welding), and a complete MOPP bytecode disassembly.

**Usage:**
```
python io_scene_nifly/scripts/dump_collision.py <nif_path>
```

**Example:**
```
python io_scene_nifly/scripts/dump_collision.py tests/tests/SkyrimSE/rocks01.nif
```

**Output includes:**
- Block listing and collision object linkage
- Rigid body properties (rotation, translation, friction, etc.)
- bhkMoppBvTreeShape properties (MOPP origin, scale, build type)
- bhkCompressedMeshShape properties (radius, error, bit widths)
- Per-chunk details: vertices, indices, strip lengths, welding info, triangle decomposition with world coordinates
- Full MOPP bytecode disassembly showing the BVH tree structure

---

## dump_collision_mesh.py

Exports the collision mesh geometry from a NIF file as a Wavefront OBJ file. Useful for visualizing collision shapes in Blender or other 3D tools, especially for checking face orientation.

**Usage:**
```
python io_scene_nifly/scripts/dump_collision_mesh.py <input_nif> <output_obj>
```

**Example:**
```
python io_scene_nifly/scripts/dump_collision_mesh.py tests/tests/SkyrimSE/rocks01.nif C:/tmp/rocks_collision.obj
```

**Tips:**
- Import the OBJ in Blender and enable **Viewport Overlays > Face Orientation** to check normals. Blue = outward (correct), red = inward (flipped).
- Compare vanilla and exported collision meshes side-by-side to spot winding issues.

---

## mopp_verifier.py

Tests MOPP bytecode for correctness and quality by walking the BVH tree with sample query points.

**Standalone usage:**
```
python io_scene_nifly/scripts/mopp_verifier.py <nif_path>
```

**Checks performed:**
- **Surface reachability**: samples points on each triangle's surface using barycentric coordinates and verifies the MOPP tree returns a hit.
- **Correctness** (requires output IDs): verifies each triangle is reachable from points inside its AABB.
- **Completeness**: random sampling across the global AABB to find any invalid output IDs.
- **Tightness**: measures false positive rate — how many hits occur for points outside all triangle AABBs.

**Also used programmatically** in PyNifly's test suite (`pynifly_tests.py`) to verify collision round-trips.

---

## mopp_benchmark.py

Compares MOPP quality between vanilla Havok-compiled bytecode and PyNifly's compiler across a set of NIF files. Measures false positive rate and code size.

**Usage:**
```
python io_scene_nifly/scripts/mopp_benchmark.py [--nifs-dir DIR] [--max N] [--samples N] [--out FILE]
```

**Defaults:**
- `--nifs-dir`: `C:/Modding/SkyrimSEAssets/00 Vanilla Assets/meshes/architecture`
- `--max`: 40 (maximum number of NIFs to test)
- `--samples`: 500 (random sample points per mesh)
- `--out`: `C:/tmp/mopp_quality_comparison.csv`

**Output:** CSV with columns for filename, triangle count, vanilla false positive rate, our false positive rate, vanilla MOPP size, and our MOPP size. Summary statistics printed to console.

---

## CheckNifSegmentation.py

Lists FO4 NIF files with problematic segmentation for hair meshes. Checks for missing partitions and incorrect subsegment structure.

**Usage:** Edit the `target_directory` variable in the script, then run:
```
python io_scene_nifly/scripts/CheckNifSegmentation.py
```

**Note:** Requires FO4 mesh files at the configured path.
