import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = 'C:/Steam/steamapps/common/Skyrim Special Edition/Data/meshes/YAS/Dog/Tail/LykaiosFemTail_1.nif'
nif = pynifly.NifFile(nif_path)

print('=== Checking all shapes for collision flags ===\n')

for s in nif.shapes:
    print(f'Shape: {s.name}')
    print(f'  Flags: {s.properties.flags}')
    print(f'  Has shader: {s.shader is not None}')
    print(f'  Shader property ID: {s.properties.shaderPropertyID}')
    print(f'  Alpha property ID: {s.properties.alphaPropertyID}')
    
    # Check if it's marked as hidden or non-rendering
    if s.properties.flags == 14:
        print(f'  ⚠️  Flags = 14 (hidden/non-rendering - typical for collision meshes)')
    elif s.properties.flags == 524302:
        print(f'  ✓ Flags = 524302 (visible rendering mesh)')
    
    # Check shader
    if s.shader:
        print(f'  Shader name: {s.shader.blockname if hasattr(s.shader, "blockname") else "unknown"}')
    else:
        print(f'  ⚠️  NO SHADER (might not render or be recognized)')
    
    print()

# Check if there's a BSXFlags extra data that might disable collision
print('\n=== Checking for BSXFlags or other extra data ===')
for name, block in nif.dict.items():
    if hasattr(block, 'blockname'):
        if 'BSX' in block.blockname or 'Flags' in block.blockname:
            print(f'Found: {block.blockname}')
            if hasattr(block, 'integer_data'):
                print(f'  Integer data: {block.integer_data}')
            if hasattr(block, 'name'):
                print(f'  Name: {block.name}')
