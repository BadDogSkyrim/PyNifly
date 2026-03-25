import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

tail_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

nif = pynifly.NifFile(tail_path)

print("=== Checking for HDT Config Reference ===\n")

# The HDT config is stored as NiStringExtraData on the root node
root = nif.rootNode

print(f"Root node type: {type(root).__name__}")
print(f"Root node name: {root.name if hasattr(root, 'name') else 'N/A'}")

# Check for extra data
if hasattr(root, 'extra_data_list'):
    print(f"\nExtra data list ({len(root.extra_data_list)} items):")
    for extra in root.extra_data_list:
        print(f"  {extra}")
else:
    print("\nNo extra_data_list attribute")

# Try the string_data approach
if hasattr(root, 'string_data'):
    print(f"\nString data list ({len(root.string_data)} items):")
    for sd in root.string_data:
        print(f"  Name: {sd.name}")
        if hasattr(sd, 'string'):
            print(f"    String: {sd.string}")
else:
    print("\nNo string_data attribute")

# Check all top-level blocks
print(f"\n=== All NIF blocks ===")
for i, block in enumerate(nif.shapes):
    if hasattr(block, 'string_data'):
        print(f"Shape {i} ({block.name}) has string_data:")
        for sd in block.string_data:
            print(f"  {sd.name}: {sd.string if hasattr(sd, 'string') else 'N/A'}")
