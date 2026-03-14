import sys
sys.path.insert(0, r'C:\Modding\PyNifly\io_scene_nifly')
from pynifly import NifFile

nif_path = r'C:\steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Dog\Tail\LykaiosFemTail_1.nif'
nif = NifFile(nif_path)

print(f"NIF file: {nif_path}")
print(f"Number of shapes: {len(nif.shapes)}\n")

for shape in nif.shapes:
    print(f"Shape: {shape.name}")
    print(f"  Bones ({len(shape.bone_names)}): {list(shape.bone_names)[:30]}")
    print()
