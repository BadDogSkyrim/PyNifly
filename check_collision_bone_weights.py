import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"
nif = pynifly.NifFile(nif_path)

print("=== Bone Weights for All Collision Shapes ===\n")

for shape in nif.shapes:
    if 'Collision' in shape.name or 'Virtual' in shape.name:
        print(f"\n{shape.name}:")
        if hasattr(shape, 'bone_weights'):
            for bone_name in shape.bone_weights.keys():
                print(f"  Weighted to: {bone_name}")
                # Show a few sample weights
                weights = shape.bone_weights[bone_name]
                if len(weights) <= 5:
                    print(f"    All weights: {weights}")
                else:
                    print(f"    Sample weights (first 3): {weights[:3]}")
                    print(f"    Total vertices: {len(weights)}")
