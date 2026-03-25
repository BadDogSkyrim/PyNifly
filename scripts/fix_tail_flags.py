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
    backup_path = nif_path + ".backup6"
    shutil.copy(nif_path, backup_path)
    print(f"  Backed up to: {backup_path}")
    
    # Load and modify
    nif = pynifly.NifFile(nif_path)
    
    print(f"\n  Before:")
    for s in nif.shapes:
        print(f"    {s.name:20} flags: {s.flags}")
    
    # Set flags based on shape type:
    # - Collision shapes (VirtualGround, CollisionBody, CollisionTail): 14 (hidden)
    # - Visible shapes (TAIL, Fur): 524302 (visible)
    for s in nif.shapes:
        if s.name in ["VirtualGround", "CollisionBody", "CollisionTail"]:
            s.flags = 14
        else:
            s.flags = 524302
    
    print(f"\n  After:")
    for s in nif.shapes:
        print(f"    {s.name:20} flags: {s.flags}")
    
    # Save
    nif.save()
    print(f"  Saved!\n")

print("Done! Collision shapes set to 14, visible shapes set to 524302")
