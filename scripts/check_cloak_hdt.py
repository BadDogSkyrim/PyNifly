cloak_path = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\Artesian Cloaks of Skyrim FOMOD-17416-1-3-0\meshes\clothes\volsCloaks\FluffyCloak_F.nif"

print("=== Searching for HDT in cloak ===\n")

with open(cloak_path, 'rb') as f:
    data = f.read()
    
    # Search for various HDT-related strings
    for search_term in [b'HDT', b'hdt', b'cloak.xml', b'cape.xml', b'Skinned Mesh']:
        pos = data.find(search_term)
        if pos != -1:
            start = max(0, pos - 50)
            end = min(len(data), pos + 100)
            context = data[start:end]
            print(f"Found '{search_term.decode()}' at position {pos}")
            print(f"  Context: {context.decode('latin-1', errors='replace')}\n")
