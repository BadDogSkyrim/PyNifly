import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

cloak_path = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\Artesian Cloaks of Skyrim FOMOD-17416-1-3-0\meshes\clothes\volsCloaks\FluffyCloak_F.nif"

print("=== Artesian Cloak Inspection ===\n")

nif = pynifly.NifFile(cloak_path)

# Check for HDT config reference
print("Extra data:")
for block in nif.nodes.values():
    if hasattr(block, 'string_data'):
        for sd in block.string_data:
            if hasattr(sd, 'string'):
                print(f"  {sd.name}: {sd.string}")
print()

# List all shapes
print("=== All Shapes ===")
for s in nif.shapes:
    print(f"\nShape: {s.name}")
    print(f"  Vertices: {len(s.verts)}")
    print(f"  Triangles: {len(s.tris)}")
    print(f"  Flags: {s.flags}")
    if hasattr(s, 'bone_weights'):
        bones = list(s.bone_weights.keys())
        print(f"  Weighted to: {len(bones)} bones")
        cloak_bones = [b for b in bones if 'CB ' in b or 'Cloak' in b]
        if cloak_bones:
            print(f"  Cloak bones: {cloak_bones[:5]}")

# VirtualGround details
print("\n=== VirtualGround Details ===")
for s in nif.shapes:
    if s.name == "VirtualGround":
        print(f"Vertices: {len(s.verts)}")
        print(f"Sample vertices:")
        for i in range(min(4, len(s.verts))):
            print(f"  Vertex {i}: {s.verts[i]}")
        if hasattr(s, 'bone_weights'):
            print(f"Weighted to bones: {list(s.bone_weights.keys())}")
        break
