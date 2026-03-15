import sys
sys.path.insert(0, './io_scene_nifly')
from pyn import pynifly

sky_tail = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\SkyFurry\Meshes\Actors\Character\SFTails\KhajiitFemaleTail_1.nif"
our_tail = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

print("=== Comparing SkyFurry vs YAS Tails ===\n")

for label, path in [("SkyFurry", sky_tail), ("YAS", our_tail)]:
    print(f"=== {label} ===")
    nif = pynifly.NifFile(path)
    
    shapes = nif.shapes
    
    # Get VirtualGround
    vg = None
    for s in shapes:
        if s.name == "VirtualGround":
            vg = s
            break
    
    if vg:
        verts = vg.verts
        min_x = min(v[0] for v in verts)
        max_x = max(v[0] for v in verts)
        min_y = min(v[1] for v in verts)
        max_y = max(v[1] for v in verts)
        z = verts[0][2]
        print(f"VirtualGround size: X={min_x:.1f} to {max_x:.1f}, Y={min_y:.1f} to {max_y:.1f}, Z={z:.2f}")
        print(f"  Dimensions: {max_x-min_x:.1f} x {max_y-min_y:.1f}")
        print(f"  Flags: {vg.flags}")
    
    # Get visible tail shape
    for s in shapes:
        if s.name in ["TAIL", "Tail"]:
            print(f"{s.name} flags: {s.flags}")
            # Get bone names
            if hasattr(s, 'bone_weights'):
                bones = list(s.bone_weights.keys())
                tail_bones = [b for b in bones if 'Tail' in b]
                print(f"  Tail bones: {tail_bones[:5]}")
            break
    
    # Get CollisionTail
    for s in shapes:
        if s.name == "CollisionTail":
            print(f"CollisionTail flags: {s.flags}")
            if hasattr(s, 'bone_weights'):
                bones = list(s.bone_weights.keys())
                tail_bones = [b for b in bones if 'Tail' in b]
                print(f"  Tail bones: {tail_bones[:5]} ({len(tail_bones)} total)")
            break
    
    print()
