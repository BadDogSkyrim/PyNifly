import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

tail_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

nif = pynifly.NifFile(tail_path)

print("=== All Extra Data in Tail ===\n")

# Check root node
root = nif.rootNode
if hasattr(root, 'string_data'):
    print("Root string_data:")
    for sd in root.string_data:
        print(f"  {sd.name}: {sd.string}")

# Check all shapes for extra data
for s in nif.shapes:
    if hasattr(s, 'string_data'):
        print(f"\nShape '{s.name}' string_data:")
        for sd in s.string_data:
            print(f"  {sd.name}: {sd.string}")
    
    if hasattr(s, 'extra_data'):
        print(f"\nShape '{s.name}' extra_data:")
        for ed in s.extra_data:
            print(f"  {ed}")

# Check the NIF structure for BSXFlags
if hasattr(nif, 'bsxflags'):
    print(f"\nBSXFlags: {nif.bsxflags}")

# Let's also just print ALL attributes of the root
print("\n=== Root Node Attributes ===")
for attr in dir(root):
    if not attr.startswith('_'):
        try:
            val = getattr(root, attr)
            if not callable(val) and 'data' in attr.lower():
                print(f"{attr}: {val}")
        except:
            pass
