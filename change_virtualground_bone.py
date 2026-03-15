import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

nif_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"
nif = pynifly.NifFile(nif_path)

# Change VirtualGround bone weights from NPC Root to NPC Pelvis
for shape in nif.shapes:
    if shape.name == "VirtualGround":
        print(f"Current bone weights: {list(shape.bone_weights.keys())}")
        
        # Remove old weights
        shape.bone_weights.clear()
        
        # Add new weights to NPC Pelvis
        # bone_weights format is {bone_name: [(vert_id, weight), ...]}
        shape.bone_weights['NPC Pelvis [Pelv]'] = [(0, 1.0), (1, 1.0), (2, 1.0), (3, 1.0)]
        
        print(f"New bone weights: {list(shape.bone_weights.keys())}")

import shutil
backup_path = nif_path + ".backup3"
shutil.copy2(nif_path, backup_path)
print(f"Backup created: {backup_path}")

nif.save()
print(f"Saved with VirtualGround weighted to NPC Pelvis [Pelv]")
