# PyNifly Developer Guide

This document provides guidelines and best practices for developers contributing to the PyNifly project.

## Overview

PyNifly is a Blender addon that provides import/export functionality for NIF files used in Bethesda games (Skyrim LE/SE, Fallout 4, Fallout 76, Fallout New Vegas, and Fallout 3). The project uses Bodyslide/Outfit Studio's Nifly library as its core.

## Project Structure

```
PyNifly/
├── io_scene_nifly/          # Main addon code
│   ├── __init__.py          # Blender addon entry point, preferences, register()
│   ├── blender_defs.py      # Shared Blender helpers (ObjectSelect, transforms, ...)
│   ├── pyn/                 # Pure-python nif layer -- NO bpy import allowed here
│   ├── nif/                 # NIF import/export (import_nif, export_nif, shader_io,
│   │                        #   collision, controller, pyn_props, connectpoint)
│   ├── hkx/                 # HKX animation and skeleton I/O
│   ├── kf/                  # KF animation files
│   ├── tri/                 # TRI / TRIP morph files
│   ├── sfmorph/             # Starfield facial morphs
│   ├── osd/                 # Bodyslide OSD sliders
│   ├── util/                # settings, ReprObject
│   └── scripts/             # Standalone dev tools (not part of the addon proper)
├── tests/
│   ├── blender_tests.py     # Aggregator + harness (do_tests, execute_test, TestLogHandler)
│   ├── blender/             # The Blender tests themselves, split by domain
│   │   ├── common.py        # Shared imports, helpers, log handler -- `from .common import *`
│   │   └── test_*.py        # animation, bodyparts, collision, fo4, geometry,
│   │                        #   shaders, skyrim, starfield, tri
│   ├── pynifly_tests.py     # pyn-layer tests (no Blender)
│   ├── anim_tests.py        # HKX animation tests (no Blender)
│   ├── test_tools.py        # TT.* check routines and decorators
│   ├── test_tools_bpy.py    # TTB.* Blender-side helpers
│   ├── test_nifchecker.py   # Per-fixture Check_* routines
│   └── tests/               # Test fixtures (nifs, blends, textures)
├── docs/                    # Format references and plan documents
├── NiflyDLL/                # C++ Nifly wrapper
├── test_runner.py           # Blender test entry point
├── pynifly_test_runner.py   # pyn-layer test entry point
└── anim_test_runner.py      # HKX animation test entry point
```

**The `pyn/` boundary is load-bearing.** Nothing under `io_scene_nifly/pyn/` may import `bpy`.
That is what lets the pyn-layer tests run without Blender, and it is worth protecting.

### Adding a test

Put it in the `tests/blender/test_*.py` matching its subject and give it a `@TT.category`.
Nothing else is needed -- `blender_tests.py` star-imports every module in the package, and
`do_tests` finds anything named `TEST_*` in that namespace.

## Writing Tests

When writing tests for PyNifly, always use the check routines provided in `tests/test_tools.py`. These functions provide consistent error reporting and logging.

### Available Check Routines

#### Equality Checks
- `is_eq(actual, expected, message)` - Check exact equality
- `is_equiv(actual, expected, message, epsilon=0.0001)` - Check near equality (for floats/vectors/matrices)

#### Inequality Checks
- `is_neq(actual, expected, message)` - Check inequality
- `is_lt(actual, expected, message)` - Check less than
- `is_le(actual, expected, message)` - Check less than or equal
- `is_gt(actual, expected, message)` - Check greater than
- `is_ge(actual, expected, message)` - Check greater than or equal

#### Container Checks
- `is_contains(element, collection, message)` - Check whether element is in collection
- `is_notcontains(element, collection, message)` - Check whether element is not in collection
- `is_seteq(actual, expected, message)` - Check whether two collections have same members
- `is_samemembers(actual, expected, message)` - Check whether the two are set-equal--same members and length

#### Specialized Checks
- `is_true(value, message)` - Check truthiness
- `is_patheq(actual, expected, message)` - Check path equality
- `is_matnearequal(m1, m2, message, epsilon=0.001)` - Check matrix near equality
- `get_property(nif, path)` - Walk a dotted/list path into a nif and return the value

#### `assert_*` variants
Every `is_*` has an `assert_*` twin that raises instead of returning a bool, so it can be used
without wrapping in `assert`: `assert_eq`, `assert_ne`, `assert_equiv`, `assert_equiv_not`,
`assert_lt`, `assert_le`, `assert_gt`, `assert_ge`, `assert_contains`, `assert_seteq`,
`assert_samemembers`, `assert_patheq`, `assert_pathendswith`, `assert_eq_nocase`,
`assert_exists`, `assert_true`, `assert_property`. Both styles are in use; prefer
`assert TT.is_eq(...)` in new tests.

### Test Example

```python
@TT.category('SKYRIM', 'MESH')
def TEST_EXAMPLE():
    """Example test showing proper check routine usage."""
    testfile = TTB.test_file(r"tests\Skyrim\example.nif")
    
    bpy.ops.import_scene.pynifly(filepath=testfile)
    
    # Use check routines instead of raw assert statements
    obj = bpy.data.objects['ExampleMesh']
    assert TT.is_eq(len(obj.data.vertices), 1024, "Vertex count")
    assert TT.is_equiv(obj.location, [0.0, 0.0, 0.0], "Object location")
    assert TT.is_contains("ExampleMaterial", [m.name for m in obj.data.materials], "Has material")
    
    # Export and verify
    outfile = TTB.test_file(r"tests/out/TEST_EXAMPLE.nif")
    bpy.ops.export_scene.pynifly(filepath=outfile)
    
    nif = pyn.NifFile(outfile)
    vertex_count = TT.get_property(nif, ['ExampleMesh', 'vertex_count'])
    assert TT.is_eq(vertex_count, 1024, "Exported vertex count")
```

### Test Guidelines

1. **Always use test_tools check routines** instead of raw `assert` statements
2. **Provide descriptive messages** for all checks to aid debugging
3. **Use appropriate categories** with the `@TT.category()` decorator. This allows tests for the same functionality to be identified and run.
4. **Clean up after tests** - mostly not necessary--the test harness will clean up Blender between tests. Preserve nif outputs for later review.
5. **Test both import and export** when possible
6. **Use consistent naming** - test functions should start with `TEST_`
7. **Check warnings** - Importer and exporter are designed to give a warning and continue rather than failing completely. These warnings will cause the test to fail (as they generally should). Use `@TT.expect_errors()` to cause the harness to ignore them.

### Test Categories

Use the `@TT.category()` decorator to classify tests. Multiple categories can be applied to a single test.

These are the categories actually in use. They drive three things: `do_tests(categories=[...])`
selection, the FO4-vs-Skyrim texture directory `execute_test` sets, and the minimum Blender
version a test needs.

#### Game Versions
- `'SKYRIM'` - Skyrim LE  ·  `'SKYRIMSE'` - Skyrim SE/AE  ·  `'FO4'` - Fallout 4
- `'FONV'` - Fallout New Vegas  ·  `'STARFIELD'` - Starfield

`'FO4'` is not just a label: `execute_test` points Blender at the FO4 texture directory for
tests carrying it, and the Skyrim one for everything else. Tag FO4 tests accordingly.

#### Feature Types
- `'BODYPART'` - body parts, heads, hands  ·  `'ARMATURE'` - armatures and bones
- `'FACEBONES'` - FO4 facebones  ·  `'FACEGEN'` - facegen
- `'SHADER'` - materials and texturing  ·  `'EXTRA_DATA'` - extra data blocks
- `'TRI'` - .tri/.trip morphs  ·  `'SHAPEKEY'` - Blender shape keys
- `'ANIMATION'` - animation embedded in NIFs  ·  `'HKX'` - HKX and KF animation files
- `'PARTITIONS'` - partitions and segments  ·  `'CONNECTPOINT'` - FO4 attachment points
- `'COLLISION'` / `'PHYSICS'` / `'MOPP'` - collision shapes, bodies, MOPP trees
- `'TREE'` - BSTreeNode / NiSwitchNode  ·  `'LOD'` - level of detail
- `'FURNITURE'` - furniture markers  ·  `'INVENTORY_MARKER'` - inventory markers
- `'OSD'` - Bodyslide OSD sliders  ·  `'IMPORT'` / `'SETTINGS'` - operator options

#### Transform and Geometry
- `'XFORM'` - transforms  ·  `'SCALING'` - scaling  ·  `'GEOMETRY'` - mesh geometry

#### Minimum Blender version
`test_categories` in `blender_tests.py` maps a category to the lowest Blender it can run on.
Only two carry a real constraint: **`'ANIMATION'` and `'HKX'` require 4.4**, because animation
import and export are gated on `bpy.types.ActionSlot`. Everything else is listed at `(3,0)`,
which means "no constraint beyond the addon's own 4.0 floor". A test that depends on an
imported action needs `'ANIMATION'` even if animation is not its subject, or it will fail on
Blender 4.0-4.3.

For a one-off limit unrelated to a category, use `@TT.min_version(5, 1, 0)`.

**Watch for near-duplicates.** `'BODYPARTS'`, `'SHAPEKEYS'` and `'FURNITUREMARKER'` exist in the
suite as typos of `'BODYPART'`, `'SHAPEKEY'` and `'FURNITURE'`. They silently create a separate
category that nothing selects and that has no declared version minimum. Check the list above
before inventing a name.

#### Example Usage
```python
@TT.category('SKYRIM', 'BODYPART', 'ARMATURE')
def TEST_SKYRIM_HEAD():
    """Test importing Skyrim character head with skeleton."""
    # Test implementation...

@TT.category('FO4', 'SHADER', 'ANIMATION')  
def TEST_FO4_ANIMATED_MATERIAL():
    """Test FO4 material with animation controllers."""
    # Test implementation...
```

### Test Decorators

Additional decorators available:
- `@TT.skip_test` - Skip a test
- `@TT.error_level(level)` - Set allowed error level
- `@TT.expect_errors(errlist)` - Expect specific errors
- `@TT.parameterize(names, values)` - Run test with multiple parameter sets

## Code Style

1. Follow PEP 8 for Python code style
2. Use meaningful variable names
3. Add docstrings to all public functions and classes
4. Keep functions focused and reasonably sized
5. Use type hints where appropriate

## Error Handling

When adding error handling to the codebase:

1. **Preserve exception chains** using `raise ... from e` to maintain original error context
2. **Add meaningful context** to error messages
3. **Use appropriate exception types** (don't catch all exceptions unless necessary)
4. **Log errors appropriately** using the logging system

Example:
```python
try:
    shape[fieldname] = v
except (OverflowError, TypeError) as e:
    raise Exception(f"Error setting property {fieldname} <- {v}") from e
```

## Building and Testing

## Testing the pynifly layer

The `pyn` module is a self-contained python module for manipulating nif files. It has its own set of tests that run independently of Blender. Where feasible, functionality should be tested at this level (because running and debugging tests is simpler).

Tests are run with `pynifly_test_runner.py`.

### Testing the Blender layer

These need Blender, but not a Blender window. Headless is the normal way to run them:

```
PYNIFLY_DEV_ROOT="c:/Modding" \
  "/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" \
  --background --python c:/Modding/PyNifly/test_runner.py
```

`PYNIFLY_DEV_ROOT` is the **parent** of the PyNifly checkout, not the checkout itself --
`niflydll.py` appends `PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll` to it to find the DLL.

The addon must resolve to the working tree. Each Blender version has its own addons directory
(`%APPDATA%\Blender Foundation\Blender\<ver>\scripts\addons\io_scene_nifly`); it should be a
junction to `io_scene_nifly/`, not a copy, or you will test stale code and be baffled:
`cmd /c mklink /J "<addons>\io_scene_nifly" "C:\Modding\PyNifly\io_scene_nifly"`.

You can also run it from Blender's text editor by loading `test_runner.py` and running it.

### Running specific tests or categories

`test_runner.py` is a scratch file -- edit its `do_tests()` call freely:
```python
# Everything (the default)
tests.blender_tests.do_tests(target_tests=[], test_all=True, stop_on_fail=False)

# One test, and stop on the first failure
tests.blender_tests.do_tests(target_tests=[TEST_SHADER_SE], test_all=False, stop_on_fail=True)

# A whole category
tests.blender_tests.do_tests(categories=['COLLISION'])
```

Two gotchas when a test fails only in a full run:
- `stop_on_fail=False` swallows `AssertionError` silently -- a failing test appears in the
  final list with no message. Set `stop_on_fail=True` to see which assertion, but note that
  `execute_test`'s stop path calls `breakpoint()`, which **hangs headless Blender**.
- A test fails if any `pynifly` log record exceeds INFO, whitelist aside. If a test fails with
  no obvious assertion, look for a stray WARNING rather than a broken check.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Debugging

- Use Blender's console for debugging import/export issues
- Enable debug logging in the addon preferences
- Use Visual Studio Code with Python extensions for C++ debugging
- Check the Blender system console for detailed error messages

## Resources

- [Project Wiki](https://github.com/BadDogSkyrim/PyNifly/wiki)
- [NIF Format Documentation](https://github.com/niftools/nifxml)
- [Blender Python API](https://docs.blender.org/api/current/)
- [Bodyslide/Outfit Studio](https://github.com/ousnius/BodySlide-and-Outfit-Studio)