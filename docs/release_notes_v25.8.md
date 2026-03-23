## PyNifly V25.8 Release Notes

### MOPP Collision Export Improvements

- MOPP and CompressedMeshShape properties now round-trip fully: `buildType`, `bitsPerIndex`, `bitsPerWIndex`, `maskIndex`, `maskWIndex`, `error`, `materialType`, `userData`, and `unkFloat` are preserved through import/export.
- Removed the separate `setCollCompressedMeshParams` DLL call — all CompressedMeshShape data-block parameters are now set in a single `addBlock` call, simplifying the export path.
- DLL function signatures no longer use `try/except AttributeError` guards — the DLL is always built alongside the Python code.

### Blender Extensions Compatibility

- Module reloading updated to use the official Blender extensions pattern (`_needs_reload = "bpy" in locals()`) in all `__init__.py` files, including sub-packages.
- Addon preferences now use `__package__` instead of a hardcoded string, as required by the Blender extensions program.
- `gamefinder.py` stripped of Xbox/Game Pass and Epic Games filesystem traversal. Remaining Steam/Bethesda Launcher registry lookups are gated behind debug mode (`PYNIFLY_DEV_ROOT`).
- Removed `if __name__ == "__main__"` standalone test blocks from all shipped modules.
- Removed `sfmesh.py` (Starfield exploration script) from the package.

### Testing

- New `TEST_FACEGEN_SE` test: imports a Skyrim SE facegen NIF, verifies all head parts are positioned correctly, exports all shapes, and checks the round-trip preserves geometry.
- Added MOPP benchmark script and compressed mesh comparison tool for future MOPP quality tuning.
