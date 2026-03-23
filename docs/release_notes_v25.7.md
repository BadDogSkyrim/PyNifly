## PyNifly V25.7 Release Notes

### Skyrim Collision Export (MOPP)

- **New: Export MOPP collision meshes for Skyrim SE and LE.** On import, `bhkMoppBvTreeShape` blocks are unpacked into Blender mesh objects with rigid body physics. On export, these are repacked as `bhkMoppBvTreeShape` wrapping a `bhkCompressedMeshShape` (SE) or `bhkPackedNiTriStripsShape` (LE), with auto-generated MOPP BVH bytecode.
- Per-chunk collision materials supported via `SKY_HAV_MAT_` vertex groups (SE).
- Multi-chunk meshes exported correctly (tested up to 923 verts, 5 chunks, 4 materials).
- Includes MOPP disassembler and verifier tools for debugging (`pyn/mopp_compiler.py`, `tests/mopp_verifier.py`).
- Note: MOPP BVH tree generation uses a straightforward axis-aligned median-split algorithm. It produces correct results and we believe it's efficient enough for the game engine, but it's not as optimized as vanilla Havok-generated MOPP trees. Feedback welcome.

### FO4 Collision Improvements

- FO4 collision objects are now positioned correctly whether there are one or many collision objects in the NIF.
- Collision constraints are no longer applied to FO4 NIFs with child connect points, since these are designed as components of a larger whole.
- Additional FO4 physics fields (friction, restitution, damping, gravity factor, mass, density, inertia) are decoded and preserved on import/export.
- FO4 sphere collision shapes now import at the correct position (body center) rather than at the origin.
- Sphere collisions use `CONVEX_HULL` rigid body shape in Blender, eliminating the phantom wireframe overlay at the origin.
- `collision_margin` is now set in Blender from Havok `convex_radius` on import, and read back on export. Users can adjust collision margin in the Physics tab.

### Animation Import Fix

- Importing a NIF no longer shrinks the scene frame range. Previously, importing a file with a short animation (e.g. a 2-frame on/off switch) would set the scene's end frame to 2, breaking rigid body simulation and timeline playback for everything else in the scene. The frame range is now only extended, never reduced.

### Notes

- Actions operate on real objects. Collisions constrain how real objects can move. If you have a collision on an object that's being animated, set the collision constraint's influence to 0 so the animation plays correctly.

### Documentation

- Added `docs/fo4_havok_packfile_format.md` — full reference for the FO4 Havok binary packfile format used by `bhkPhysicsSystem`.
- Added `docs/mopp_format.md` — reference for MOPP bytecode format, compiler, disassembler, and verifier.
- Added `docs/hkx_animation_format.md` — reference for the FO4 HKX animation binary format.
