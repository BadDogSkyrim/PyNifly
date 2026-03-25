import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

sky_tail = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\SkyFurry\Meshes\Actors\Character\SFTails\KhajiitFemaleTail_1.nif"

nif = pynifly.NifFile(sky_tail)

print("=== SkyFurry Tail HDT Reference ===\n")

# Try to access the internal NIF structure
# PyNifly might expose the raw blocks
if hasattr(nif, 'blocks'):
    print(f"Found {len(nif.blocks)} blocks\n")
    for i, block in enumerate(nif.blocks):
        block_type = type(block).__name__
        if 'String' in block_type or 'Extra' in block_type:
            print(f"Block {i}: {block_type}")
            if hasattr(block, 'name'):
                print(f"  Name: {block.name}")
            if hasattr(block, 'string'):
                print(f"  String: {block.string}")
            if hasattr(block, 'string_data'):
                print(f"  StringData: {block.string_data}")

# Check the raw file structure by reading it directly
print("\n=== Looking for 'HDT' string in file ===")
with open(sky_tail, 'rb') as f:
    data = f.read()
    hdt_pos = data.find(b'HDT')
    if hdt_pos != -1:
        # Read surrounding context (100 bytes before and after)
        start = max(0, hdt_pos - 100)
        end = min(len(data), hdt_pos + 200)
        context = data[start:end]
        # Try to decode
        try:
            print(f"Found 'HDT' at position {hdt_pos}")
            print(f"Context (as text): {context.decode('latin-1', errors='replace')}")
        except:
            print(f"Found 'HDT' at position {hdt_pos} (binary data)")
