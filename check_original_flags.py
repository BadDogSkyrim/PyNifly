import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

# Check the original source files
bhunp_path = r"c:\Users\hughr\OneDrive\SkyrimDev\BHUNP\Feline Tail HDT.nif"
game_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

for label, path in [("BHUNP original", bhunp_path), ("Game (current)", game_path)]:
    try:
        nif = pynifly.NifFile(path)
        flags_dict = {}
        for s in nif.shapes:
            flags_dict[s.name] = s.flags
        
        print(f"=== {label} ===")
        for name in ["VirtualGround", "CollisionTail", "CollisionBody", "TAIL", "Tail", "Fur"]:
            if name in flags_dict:
                print(f"  {name:20} flags: {flags_dict[name]}")
        print()
    except Exception as e:
        print(f"{label}: Error - {e}\n")
