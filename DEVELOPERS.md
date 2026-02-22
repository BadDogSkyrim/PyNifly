# PyNifly Developer Guide

This document provides guidelines and best practices for developers contributing to the PyNifly project.

## Overview

PyNifly is a Blender addon that provides import/export functionality for NIF files used in Bethesda games (Skyrim LE/SE, Fallout 4, Fallout 76, Fallout New Vegas, and Fallout 3). The project uses Bodyslide/Outfit Studio's Nifly library as its core.

## Project Structure

```
PyNifly/
├── io_scene_nifly/          # Main addon code
│   ├── __init__.py          # Blender addon entry point
│   ├── animation.py         # Animation handling
│   ├── blender_defs.py      # Blender integration definitions
│   ├── nif/                 # NIF import/export logic
│   ├── pyn/                 # Python wrapper for Nifly
│   └── ...
├── tests/                   # Test suite
│   ├── blender_tests.py     # Main test cases
│   ├── test_tools.py        # Test utilities and check functions
│   └── ...
├── NiflyDLL/               # C++ Nifly wrapper
└── test_runner.py          # Test execution script
```

## Writing Tests

When writing tests for PyNifly, always use the check routines provided in `tests/test_tools.py`. These functions provide consistent error reporting and logging.

### Available Check Routines

#### Equality Checks
- `is_eq(actual, expected, message)` - Check exact equality
- `is_equiv(actual, expected, message, epsilon=0.0001)` - Check near equality (for floats/vectors/matrices)

#### Inequality Checks
- `is_lt(actual, expected, message)` - Check less than
- `is_gt(actual, expected, message)` - Check greater than
- `is_ge(actual, expected, message)` - Check greater than or equal

#### Container Checks
- `is_contains(element, collection, message)` - Check if element is in collection
- `is_notcontains(element, collection, message)` - Check if element is not in collection
- `is_seteq(actual, expected, message)` - Check if two collections have same members
- `is_samemembers(actual, expected, message)` - Check same members and length

#### Specialized Checks
- `is_patheq(actual, expected, message)` - Check path equality
- `is_matnearequal(m1, m2, message, epsilon=0.001)` - Check matrix near equality

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
    
    nif = ND.NifFile(outfile)
    vertex_count = TT.get_property(nif, ['ExampleMesh', 'vertex_count'])
    assert TT.is_eq(vertex_count, 1024, "Exported vertex count")
```

### Test Guidelines

1. **Always use test_tools check routines** instead of raw `assert` statements
2. **Provide descriptive messages** for all checks to aid debugging
3. **Use appropriate categories** with the `@TT.category()` decorator
4. **Clean up after tests** - remove created objects and files
5. **Test both import and export** when possible
6. **Use consistent naming** - test functions should start with `TEST_`

### Test Categories

Use the `@TT.category()` decorator to classify tests. Multiple categories can be applied to a single test.

#### Game Versions
- `'SKYRIM'` - Skyrim LE (The Elder Scrolls V: Skyrim)
- `'SKYRIMSE'` - Skyrim SE/AE (Special Edition/Anniversary Edition)  
- `'FO4'` - Fallout 4
- `'FONV'` - Fallout New Vegas
- `'FO3'` - Fallout 3

#### Feature Types
- `'BODYPART'` - Character body parts, heads, hands, etc.
- `'ARMATURE'` - Skeletal armatures and bone systems
- `'SHADER'` - Material shaders and texturing
- `'TRI'` - Morph data (.tri files) for facial expressions and body morphs
- `'SHAPEKEY'` - Blender shape keys (morph targets)
- `'ANIMATION'` - Skeletal animations and controllers
- `'PARTITIONS'` - Mesh partitions for skinning and dismemberment
- `'COLLISION'` - Physics collision shapes and bodies
- `'EXTRA_DATA'` - NIF extra data blocks and custom properties

#### Transform and Geometry
- `'XFORM'` - Transform operations (rotation, translation, scale)
- `'SCALING'` - Mesh and object scaling operations
- `'PHYSICS'` - Physics properties and constraints

#### Specialized Categories  
- `'CONNECTPOINT'` - FO4 weapon/armor attachment points
- `'FURNITURE'` - Furniture marker objects
- `'SETTINGS'` - Addon preferences and configuration

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

### Running Tests

Tests are executed within Blender itself:

1. Open Blender
2. Load `test_runner.py` into Blender's text editor
3. Edit the call to `tests.blender_tests.do_tests()` to specify which tests to run
4. Run the script within Blender

### Running Specific Test Categories

Edit the `do_tests()` call in `test_runner.py` to specify categories:
```python
# Run all tests
tests.blender_tests.do_tests()

# Run specific categories
tests.blender_tests.do_tests(categories=['SKYRIM', 'MESH'])
```

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