# PyNifly Layer Documentation

## Overview

The PyNifly layer provides a Python wrapper around the C++ NiflyDLL library for reading, writing, and manipulating NIF (NetImmerse File) format files used by Bethesda games (Skyrim, Fallout 4, etc.). This layer bridges the gap between the low-level C++ operations and high-level Python object-oriented programming.

## Architecture

### Core Components

**1. NiflyDLL (C++ Layer)**
- `NiflyDLL.dll` - Core C++ library handling NIF file operations
- `NiflyDefs.hpp` - C++ structure definitions and enums
- Provides low-level file I/O, memory management, and data structures

**2. PyNifly Python Wrapper**
- `pynifly.py` - Main Python wrapper with high-level classes
- `nifdefs.py` - Python ctypes structures mirroring C++ definitions  
- `niflytools.py` - Utility functions and math operations

### Key Files

- **`pynifly.py`** - Primary API with NiObject hierarchy and NifFile class
- **`nifdefs.py`** - Buffer structures, enums, and low-level definitions
- **`niflytools.py`** - Math utilities, transformations, skeleton management

## Core Classes

### NifFile
The main entry point for working with NIF files.

```python
# Load a NIF file
nif = NifFile("path/to/file.nif")

# Access root node and shapes
root = nif.root
shapes = nif.shapes

# Game-specific operations
game = nif.game  # "SKYRIM", "SKYRIMSE", "FO4", etc.
```

### NiObject Hierarchy
Base class for all NIF objects with automatic buffer management.

**Key Subclasses:**
- `NiObjectNET` - Named objects with controllers
- `NiAVObject` - Transformable objects  
- `NiNode` - Scene graph nodes
- `NiShape` - Geometry shapes (meshes)
- `NiProperty` - Material and rendering properties
- `NiExtraData` - Additional metadata blocks

### Buffer System
Python ctypes structures that mirror C++ definitions.

```python
# Example buffer usage
buf = NiIntegerExtraDataBuf()
buf.integerData = 178509022
node = nif.add_block("SkeletonID", buf, parent=root)
```

## Integration Patterns

### Reading NIF Files

```python
# Load and examine a NIF
nif = NifFile("skeleton.nif")

# Get integer extra data
skelid_id = NifFile.nifly.getExtraData(nif._handle, nif.root.id, b"SkeletonID")
if skelid_id != NODEID_NONE:
    buf = NiIntegerExtraDataBuf() 
    check_return(NifFile.nifly.getBlock, nif._handle, skelid_id, byref(buf))
    skeleton_id = buf.integerData
```

### Creating Objects

```python
# High-level creation
extra_data = NiIntegerExtraData.New(nif, "MyData", 12345, parent=nif.root)

# Low-level creation  
buf = NiIntegerExtraDataBuf()
buf.integerData = 67890
block = nif.add_block("LowLevelData", buf, nif.root)
```

### Property Access

```python
# Direct property manipulation
shape = nif.shapes[0]
shape.shader.properties.Glossiness = 80.0

# Extra data properties  
root = nif.root
bsx_flags = root.bsx_flags  # Returns [name, value] pair  
root.bsx_flags = ["BSX", 130]  # Set BSX flags
```

## Buffer Types and Enums

### PynBufferTypes
Enumeration matching C++ BUFFER_TYPES.

```python
# Buffer type constants
NiNodeBufType = 0
NiShapeBufType = 1  
NiIntegerExtraDataBufType = 62
COUNT = 63
```

### Structure Synchronization
Python structures must exactly match C++ layout.

**C++ Definition:**
```cpp
struct NiIntegerExtraDataBuf {
    uint16_t bufSize = sizeof(NiIntegerExtraDataBuf);
    uint16_t bufType = BUFFER_TYPES::NiIntegerExtraDataBufType;
    uint32_t nameID = nifly::NIF_NPOS;
    uint32_t integerData = 0;
};
```

**Python Definition:**
```python
class NiIntegerExtraDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("integerData", c_uint32),
    ]
```

## Error Handling

### Check Functions
Wrapper functions ensure proper error reporting.

```python
# Return value checking
check_return(NifFile.nifly.setBlock, nif._handle, id, byref(buf))

# Message checking with exceptions
id = check_msg(NifFile.nifly.addBlock, nif._handle, name, byref(buf), parent_id)
```

### Exception Chaining
Preserve original error context.

```python
try:
    # Operation that might fail
    result = some_operation()
except Exception as e:
    raise RuntimeError("Higher level context") from e
```

## Game Support

### Supported Games
- **Skyrim** - Original Skyrim
- **SkyrimSE** - Skyrim Special Edition  
- **FO4** - Fallout 4
- **FONV** - Fallout New Vegas (limited)

### Game-Specific Features

**Skyrim/SkyrimSE:**
- Face morphs and tinting
- Lighting shader properties
- Skeleton extra data

**Fallout 4:**  
- Segment/subsegment system
- Material files (.BGSM/.BGEM)
- Body part data

## Development Guidelines

### Adding New Buffer Types

1. **Add to C++ enum** (`NiflyDefs.hpp`)
2. **Create C++ structure** (`NiflyDefs.hpp`) 
3. **Add Python enum value** (`nifdefs.py`)
4. **Create Python structure** (`nifdefs.py`)
5. **Create Python class** (`pynifly.py`)
6. **Add tests** (`pynifly_tests.py`)

### Testing Requirements

All new functionality must include:
- Unit tests in `pynifly_tests.py`
- Integration tests with real NIF files
- Error condition testing
- Cross-game compatibility verification

#### Testing Guidelines

**Test Location:**
- All PyNifly layer tests must be added to `pynifly_tests.py`
- Use the established test framework and categorization system
- Follow existing naming conventions (`TEST_FEATURE_NAME`)

**API Usage Restrictions:**
- Tests should **NEVER** call nifly library routines directly (e.g., `NifFile.nifly.someFunction()`)
- Always use the high-level PyNifly API classes and methods
- This ensures tests validate the actual user-facing API, not internal implementation details

**Good Testing Practice:**
```python
# ✅ CORRECT - Use high-level API
def TEST_SKELETON_DEER():
    nif = NifFile("tests/SkyrimSE/deer_skeleton.nif")
    root = nif.root
    # Use PyNifly classes and properties
    
# ❌ WRONG - Direct nifly calls  
def TEST_BAD_EXAMPLE():
    nif = NifFile("test.nif")
    # Don't call NifFile.nifly.getExtraData() directly
    # Don't call NifFile.nifly.getBlock() directly
```

**Test Coverage:**
- Test both success and failure scenarios
- Verify cross-game compatibility where applicable
- Include edge cases and boundary conditions
- Test property getters and setters
- Validate object creation and destruction

### Code Style

- Follow existing naming conventions
- Use type hints where possible  
- Include comprehensive docstrings
- Handle errors gracefully with proper context

## Integration with Blender

The PyNifly layer serves as the foundation for the Blender addon:

- **Import/Export** - NIF to Blender mesh conversion
- **Materials** - Shader property mapping  
- **Animations** - Controller and sequence handling
- **Collision** - Physics object management

## Performance Considerations

- **Memory Management** - Automatic cleanup via `__del__` methods
- **Lazy Loading** - Properties loaded on first access
- **Bulk Operations** - Batch processing for large datasets
- **Native Code** - Critical operations delegated to C++ layer

## Future Extensions

### Planned Features
- Animation system improvements
- Enhanced material support
- Better error reporting
- Performance optimizations

### Extension Points
- Custom extra data types
- Game-specific specializations  
- Advanced shader property handling
- Automated testing framework

## Troubleshooting

### Common Issues

**Import Errors:**
- Verify `NiflyDLL.dll` is accessible
- Check Python path configuration
- Ensure ctypes compatibility

**Buffer Mismatches:**
- Verify structure field alignment
- Check enum value synchronization
- Validate buffer type assignments

**Memory Issues:**
- Confirm proper handle cleanup
- Check for circular references
- Monitor native memory usage

### Debug Tools

```python
# Enable debug logging
import logging
logging.getLogger("pynifly").setLevel(logging.DEBUG)

# Examine buffer contents
print(repr(buffer_instance))

# Check handle validity  
assert nif._handle is not None
```

## Performance Benchmarks

Typical performance characteristics:
- **File Loading**: 10-100ms for average NIF files
- **Shape Processing**: 1-10ms per shape
- **Property Access**: Sub-millisecond for cached properties
- **Buffer Operations**: Near-native C++ performance

## API Reference

### Primary Classes
- `NifFile` - File operations and management
- `NiObject` - Base class for all NIF objects
- `NiNode` - Scene graph nodes  
- `NiShape` - Mesh geometry
- `NiIntegerExtraData` - Integer metadata blocks

### Utility Functions  
- `check_return()` - Error checking for operations
- `check_msg()` - Error checking with messages
- `create_string_buffer()` - String buffer creation

### Constants
- `NODEID_NONE` - Invalid node identifier
- `PynBufferTypes.*` - Buffer type enumeration
- Game identifiers and flags