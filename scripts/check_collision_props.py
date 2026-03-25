import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly
import shutil

# Make a backup first
nif_path = 'C:/Steam/steamapps/common/Skyrim Special Edition/Data/meshes/YAS/Dog/Tail/LykaiosFemTail_1.nif'
backup_path = nif_path + '.backup'
shutil.copy2(nif_path, backup_path)
print(f'Created backup: {backup_path}')

nif = pynifly.NifFile(nif_path)

print('=== Searching for collision properties ===')

# Check VirtualGround shape for collision properties
for s in nif.shapes:
    if s.name == 'VirtualGround':
        print(f'\nVirtualGround shape found')
        print(f'Available attributes: {[attr for attr in dir(s) if not attr.startswith("_")]}')
        
        # Check for collision-related attributes
        if hasattr(s, 'collision'):
            print(f'Has collision property: {s.collision}')
        if hasattr(s, 'collision_object'):
            print(f'Has collision_object: {s.collision_object}')
        if hasattr(s, 'properties'):
            print(f'Properties object: {type(s.properties)}')
            props_attrs = [attr for attr in dir(s.properties) if not attr.startswith('_')]
            print(f'Properties attributes: {props_attrs[:20]}...')
        
        # Look in the shape_dict for extra data
        shape_obj = nif.shape_dict.get(s.name)
        if shape_obj:
            print(f'\nShape dict entry found')
            print(f'Type: {type(shape_obj)}')

# Look for BSClothExtraData or similar
print('\n=== Checking for cloth/physics extra data ===')
for block_name, block in nif.dict.items():
    if hasattr(block, 'blockname'):
        if 'Cloth' in block.blockname or 'Physics' in block.blockname or 'Extra' in block.blockname:
            print(f'Found: {block.blockname} (ID: {block_name})')
            if hasattr(block, 'name'):
                print(f'  Name: {block.name}')
            # Try to access its properties
            block_attrs = [attr for attr in dir(block) if not attr.startswith('_') and not callable(getattr(block, attr))]
            print(f'  Attributes: {block_attrs[:15]}')
