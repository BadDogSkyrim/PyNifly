import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\SkyFurry\Meshes\Actors\Character\BDBeastModels\Tail\BrushFemaleTail_1.nif"
nif = pynifly.NifFile(nif_path)

print("=== SkyFurry Brush Female Tail ===\n")

# Check for HDT config reference
print("HDT Config Reference:")
try:
    extra_data_list = list(nif.rootNode.extra_data())
    print(f"  Total extra data items: {len(extra_data_list)}")
    for ed in extra_data_list:
        print(f"  Extra data type: {type(ed).__name__}")
        if hasattr(ed, 'name'):
            print(f"    Name: {ed.name}")
        if hasattr(ed, 'string_data'):
            print(f"    String: {ed.string_data}")
except Exception as e:
    print(f" Error reading extra data: {e}")

print("\n=== All Shapes ===")
for shape in nif.shapes:
    print(f"\nShape: {shape.name}")
    print(f"  Vertices: {len(shape.verts)}")
    print(f"  Triangles: {len(shape.tris)}")
    print(f"  Flags: {shape.flags}")
    if hasattr(shape, 'bone_weights'):
        print(f"  Weighted to bones: {list(shape.bone_weights.keys())}")

# Check for VirtualGround specifically
print("\n=== VirtualGround Details (if exists) ===")
for shape in nif.shapes:
    if 'Virtual' in shape.name or 'Ground' in shape.name.lower():
        print(f"Found: {shape.name}")
        print(f"  Flags: {shape.flags}")
        print(f"  Vertices: {len(shape.verts)}")
        if hasattr(shape, 'bone_weights'):
            for bone_name in shape.bone_weights.keys():
                print(f"  Weighted to: {bone_name}")
        break
else:
    print("No VirtualGround shape found")
