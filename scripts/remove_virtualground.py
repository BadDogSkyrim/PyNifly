import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly
import shutil

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"
nif = pynifly.NifFile(nif_path)

print(f"Shapes before: {[s.name for s in nif.shapes]}")

# Remove VirtualGround shape
shapes_to_keep = [s for s in nif.shapes if s.name != "VirtualGround"]
print(f"\nRemoving VirtualGround shape...")
print(f"Shapes to keep: {[s.name for s in shapes_to_keep]}")

# Create backup
backup_path = nif_path + ".backup4"
shutil.copy2(nif_path, backup_path)
print(f"\nBackup created: {backup_path}")

# Can't directly remove shapes in PyNifly, need to rebuild
print("\nWARNING: PyNifly doesn't support removing shapes directly.")
print("You'll need to remove the VirtualGround shape in NifSkope or Blender.")
print("\nSteps:")
print("1. Open the nif in NifSkope")
print("2. Find and delete the VirtualGround BSTriShape")
print("3. Save the file")
