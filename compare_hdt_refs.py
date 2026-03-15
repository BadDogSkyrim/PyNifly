import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

cloak_path = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\Artesian Cloaks of Skyrim FOMOD-17416-1-3-0\meshes\clothes\volsCloaks\FluffyCloak_F.nif"
tail_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

print("=== Comparing HDT Config References ===\n")

for label, path in [("Cloak", cloak_path), ("Tail", tail_path)]:
    print(f"=== {label} ===")
    nif = pynifly.NifFile(path)
    
    # Check all extra data in all nodes
    found_hdt = False
    for node_name, node in nif.nodes.items():
        if hasattr(node, 'string_data'):
            for sd in node.string_data:
                if hasattr(sd, 'string') and 'hdt' in sd.string.lower():
                    print(f"  Found HDT reference: {sd.name} = {sd.string}")
                    found_hdt = True
        
        # Also check root node extra data
        if hasattr(node, 'extra_data_list'):
            for extra in node.extra_data_list:
                if hasattr(extra, 'name'):
                    if 'hdt' in extra.name.lower() or 'HDT' in extra.name:
                        print(f"  Found extra data: {extra.name}")
                        if hasattr(extra, 'string_data'):
                            print(f"    Value: {extra.string_data}")
                        found_hdt = True
    
    if not found_hdt:
        print("  NO HDT config reference found!")
    
    # Check VirtualGround flags
    for s in nif.shapes:
        if s.name == "VirtualGround":
            print(f"  VirtualGround flags: {s.flags}")
    
    print()
