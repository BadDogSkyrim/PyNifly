import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"
nif = pynifly.NifFile(nif_path)

# Change VirtualGround flags from 14 (hidden) to 524302 (visible)
for shape in nif.shapes:
    if shape.name == "VirtualGround":
        print(f"Changing {shape.name} flags from {shape.flags} to 524302")
        shape.flags = 524302

# Save with backup
import shutil
backup_path = nif_path + ".backup2"
shutil.copy2(nif_path, backup_path)
print(f"Backup created: {backup_path}")

nif.save()
print(f"Saved with VirtualGround now visible")
