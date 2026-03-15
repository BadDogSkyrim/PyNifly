import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Dog\Tail\LykaiosFemTail_1.nif"
nif = pynifly.NifFile(nif_path)

# Find the VirtualGround shape
for shape in nif.shapes:
    if shape.name == "VirtualGround":
        print(f"=== VirtualGround Bone Weights ===\n")
        print(f"Vertices: {len(shape.verts)}")
        print(f"Vertex positions:")
        for i, vert in enumerate(shape.verts):
            print(f"  Vertex {i}: {vert}")
        print(f"\nTriangles: {len(shape.tris)}")
        for i, tri in enumerate(shape.tris):
            print(f"  Triangle {i}: {tri}")
        print(f"\nBone weights:")
        if hasattr(shape, 'bone_weights'):
            for bone_name, weights in shape.bone_weights.items():
                print(f"  Bone: {bone_name}")
                print(f"    Type: {type(weights)}")
                print(f"    Weights: {weights}")
        else:
            print("  No bone_weights attribute")
        
        # Check if shape is skinned
        if hasattr(shape, 'get_shape_skin_to_bone'):
            print(f"\nSkin to bone transform:")
            for bone_name in nif.nodes.keys():
                try:
                    transform = shape.get_shape_skin_to_bone(bone_name)
                    if transform:
                        print(f"  {bone_name}: {transform}")
                except:
                    pass
        break
