import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Dog\Tail\LykaiosFemTail_1.nif"
nif = pynifly.NifFile(nif_path)

print("=== Checking for HDT Config Reference ===\n")

# Check for string extra data in shapes
for shape in nif.shapes:
    print(f"Shape: {shape.name}")
    try:
        extra_data_list = shape.extra_data()
        if extra_data_list:
            print(f"  Extra data: {extra_data_list}")
            for ed in extra_data_list:
                print(f"    Type: {type(ed).__name__}, Value: {ed}")
    except:
        pass
    print()

# Check for string extra data in root node
print("\nRoot node extra data:")
try:
    extra_data_list = nif.rootNode.extra_data()
    if extra_data_list:
        print(f"  Extra data: {extra_data_list}")
        for ed in extra_data_list:
            print(f"    Type: {type(ed).__name__}")
            if hasattr(ed, 'name'):
                print(f"    Name: {ed.name}")
            if hasattr(ed, 'string_data'):
                print(f"    String: {ed.string_data}")
except Exception as e:
    print(f"  Error: {e}")

# Check all bones for extra data (SMP config might be on a bone node)
print("\n=== Checking skeleton nodes for HDT references ===")
for node_name in ['NPC', 'NPC Root [Root]', 'NPC COM [COM ]', 'NPC Spine [Spn0]', 'NPC Pelvis [Pelv]']:
    if node_name in nif.nodes:
        node = nif.nodes[node_name]
        try:
            extra_data_list = node.extra_data()
            if extra_data_list:
                print(f"\nNode: {node_name}")
                for ed in extra_data_list:
                    print(f"  Type: {type(ed).__name__}")
                    if hasattr(ed, 'name'):
                        print(f"    Name: {ed.name}")
                    if hasattr(ed, 'string_data'):
                        print(f"    String: {ed.string_data}")
        except:
            pass
