import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"
nif = pynifly.NifFile(nif_path)

print("=== Duma Tail Nif Structure ===\n")

# Check for HDT config reference
print("HDT Config Reference:")
try:
    extra_data_list = nif.rootNode.extra_data()
    for ed in extra_data_list:
        if hasattr(ed, 'name') and 'HDT' in ed.name:
            print(f"  Name: {ed.name}")
            if hasattr(ed, 'string_data'):
                print(f"  Config: {ed.string_data}")
except:
    pass

print("\n=== Shapes ===")
for shape in nif.shapes:
    print(f"\nShape: {shape.name}")
    print(f"  Vertices: {len(shape.verts)}")
    print(f"  Triangles: {len(shape.tris)}")
    if hasattr(shape, 'flags'):
        print(f"  Flags: {shape.flags}")

# Check VirtualGround specifically
print("\n=== VirtualGround Details ===")
for shape in nif.shapes:
    if shape.name == "VirtualGround":
        print(f"Vertices: {len(shape.verts)}")
        for i, vert in enumerate(shape.verts):
            print(f"  Vertex {i}: {vert}")
        print(f"\nTriangles: {len(shape.tris)}")
        for i, tri in enumerate(shape.tris):
            print(f"  Triangle {i}: {tri}")
        print(f"\nBone weights:")
        if hasattr(shape, 'bone_weights'):
            for bone_name, weights in shape.bone_weights.items():
                print(f"  Bone: {bone_name}")
                print(f"    Weights: {weights}")
        break
else:
    print("NO VIRTUALGROUND FOUND!")
