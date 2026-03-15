import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = 'C:/Steam/steamapps/common/Skyrim Special Edition/Data/meshes/YAS/Dog/Tail/LykaiosFemTail_1.nif'
nif = pynifly.NifFile(nif_path)

print('=== NIF FILE INFO ===')
print(f'File: {nif_path}')
print(f'Game: {nif.game}')

print(f'\nShapes ({len(nif.shapes)}):')
for s in nif.shapes:
    print(f'  - {s.name}')

print('\n=== Checking VirtualGround shape ===')
for s in nif.shapes:
    if s.name == 'VirtualGround':
        print(f'VirtualGround found!')
        print(f'  Vertices: {len(s.verts)}')
        print(f'  Triangles: {len(s.tris)}')
        
        # Check bone weights
        if hasattr(s, 'bone_names') and s.bone_names:
            print(f'\n  Weighted to {len(s.bone_names)} bones:')
            for bone in s.bone_names:
                print(f'    - {bone}')
        
        # Check actual vertex positions
        if hasattr(s, 'verts') and s.verts:
            print(f'\n  Vertex positions:')
            for i, v in enumerate(s.verts):
                print(f'    Vertex {i}: ({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})')
            
            min_z = min(v[2] for v in s.verts)
            max_z = max(v[2] for v in s.verts)
            print(f'\n  Z-height range: {min_z:.2f} to {max_z:.2f}')
        
        break

# Now check where NPC Root actually is positioned
print('\n=== Checking NPC Root position ===')
if 'NPC Root [Root]' in nif.nodes:
    root = nif.nodes['NPC Root [Root]']
    print(f'NPC Root [Root] found')
    if hasattr(root, 'transform'):
        print(f'  Transform: {root.transform}')
    if hasattr(root, 'position'):
        print(f'  Position: {root.position}')
else:
    print('NPC Root [Root] not found in nodes')
    print('Available nodes with "Root" in name:')
    for name in nif.nodes.keys():
        if 'root' in name.lower():
            print(f'  - {name}')
