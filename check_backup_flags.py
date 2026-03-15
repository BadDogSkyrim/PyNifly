import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

base_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

for suffix in ["", ".backup", ".backup2", ".backup3", ".backup4"]:
    try:
        path = base_path + suffix
        nif = pynifly.NifFile(path)
        
        vg_flags = ct_flags = tail_flags = None
        for s in nif.shapes:
            if s.name == "VirtualGround":
                vg_flags = s.flags
            elif s.name == "CollisionTail":
                ct_flags = s.flags
            elif s.name == "TAIL":
                tail_flags = s.flags
        
        label = "CURRENT" if not suffix else suffix
        print(f"{label:12} - VG:{vg_flags:6}  CT:{ct_flags:6}  TAIL:{tail_flags:6}")
    except:
        print(f"{suffix or 'CURRENT':12} - Not found")
