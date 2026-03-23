## PyNifly V25.9 Release Notes

### BSDecalPlacementVectorExtraData Support

- Full import/export support for BSDecalPlacementVectorExtraData, the NIF extra data type used by the engine for blood splatter, dirt, and other decal placement on body and armor meshes.
- On import, decal data is represented as an Empty with the vector blocks stored as a JSON custom property.
- Round-trips losslessly — exported NIFs have identical decal placement data to the original.
- Previously these blocks generated "Unknown block type" warnings and were silently dropped on export.

### MOPP Collision Fixes

- Fixed bitsPerIndex and bitsPerWIndex in exported CompressedMeshShape data. Previously these were computed dynamically (giving values like 6 or 7), but all vanilla Skyrim SE files use fixed constants (17 and 18). Incorrect values could cause broken collision detection in-game.
- Fixed single-material CompressedMeshShape meshes losing their Havok material on round-trip. Single materials are now stored as a vertex group, consistent with multi-material handling.
- Fixed SE material not being passed through bhkMoppBvTreeShape to the child CompressedMeshShape.

### Blender Extensions Compatibility

- As required by Blender extensions review, removed feature to search game folders for textures and matierals on import. Use the texture file paths in PyNifly's preferences instead. 
- Module reloading updated to match the official Blender extensions handbook.
- Addon preferences use `__package__` instead of hardcoded string.
- Removed standalone test blocks and sfmesh.py from shipped package.
