import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly
import shutil

nif_paths = [
    r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_0.nif",
    r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"
]

for nif_path in nif_paths:
    print(f"Processing: {nif_path}")
    
    # Backup
    backup_path = nif_path + ".backup5"
    shutil.copy(nif_path, backup_path)
    print(f"  Backed up to: {backup_path}")
    
    # Load and modify
    nif = pynifly.NifFile(nif_path)
    
    print(f"\n  Before:")
    for s in nif.shapes:
        print(f"    {s.name:20} flags: {s.flags}")
    
    # Change ALL shapes to flags=14
    for s in nif.shapes:
        s.flags = 14
    
    print(f"\n  After:")
    for s in nif.shapes:
        print(f"    {s.name:20} flags: {s.flags}")
    
    # Save
    nif.save()
    print(f"  Saved!\n")

print("Done! All shape flags changed to 14 to match SkyFurry.")
