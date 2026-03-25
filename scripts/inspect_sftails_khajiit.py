import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\SkyFurry\Meshes\Actors\Character\SFTails\KhajiitFemaleTail_1.nif"
nif = pynifly.NifFile(nif_path)

print("=== SkyFurry Khajiit Female Tail (SFTails) ===\n")

# Check for HDT config reference
print("HDT Config Reference:")
try:
    extra_data_list = list(nif.rootNode.extra_data())
    for ed in extra_data_list:
        if hasattr(ed, 'name'):
            print(f"  Name: {ed.name}")
            if hasattr(ed, 'string_data'):
                print(f"  Config: {ed.string_data}")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== All Shapes ===")
for shape in nif.shapes:
    print(f"\nShape: {shape.name}")
    print(f"  Vertices: {len(shape.verts)}")
    print(f"  Triangles: {len(shape.tris)}")
    print(f"  Flags: {shape.flags}")
    if hasattr(shape, 'bone_weights'):
        print(f"  Weighted to bones: {list(shape.bone_weights.keys())}")

# Check for VirtualGround specifically
print("\n=== VirtualGround/Collision Details ===")
for shape in nif.shapes:
    if 'Virtual' in shape.name or 'Ground' in shape.name or 'Collision' in shape.name:
        print(f"\nShape: {shape.name}")
        print(f"  Flags: {shape.flags}")
        print(f"  Vertices: {len(shape.verts)}")
        print(f"  Sample vertices:")
        for i, vert in enumerate(shape.verts[:4]):
            print(f"    Vertex {i}: {vert}")
        if hasattr(shape, 'bone_weights'):
            for bone_name in shape.bone_weights.keys():
                weights = shape.bone_weights[bone_name]
                print(f"  Weighted to: {bone_name}")
                if len(weights) <= 5:
                    print(f"    All weights: {weights}")
                else:
                    print(f"    Sample: {weights[:3]}")
