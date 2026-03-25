import sys
sys.path.insert(0, './io_scene_nifly')

tail_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\meshes\YAS\Duma\FelineFemTail_Duma_1.nif"

print("=== Searching for HDT in YAS tail ===\n")

with open(tail_path, 'rb') as f:
    data = f.read()
    hdt_pos = data.find(b'HDT')
    if hdt_pos != -1:
        start = max(0, hdt_pos - 50)
        end = min(len(data), hdt_pos + 150)
        context = data[start:end]
        print(f"Found 'HDT' at position {hdt_pos}")
        print(f"Context: {context.decode('latin-1', errors='replace')}")
    else:
        print("NO 'HDT' string found in file!")
        
    # Also search for the config filename
    config_pos = data.find(b'HDTTailLykaiosFemale.xml')
    if config_pos != -1:
        print(f"\nFound config filename at position {config_pos}")
    else:
        print("\nNO config filename found!")
