import os
import re

config_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\SKSE\Plugins\hdtSkinnedMeshConfigs"

# Get all tail config files
files = [f for f in os.listdir(config_path) if f.startswith('HDTTail') and f.endswith('.xml')]

for filename in files:
    filepath = os.path.join(config_path, filename)
    
    print(f"\n=== Processing {filename} ===")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already has <shared>private</shared>
    if '<shared>private</shared>' in content:
        print(f"  Already has private shared, skipping")
        continue
    
    # Find VirtualGround and add <shared>private</shared> after <tag>ground</tag>
    pattern = r'(<per-triangle-shape name="VirtualGround">.*?<tag>ground</tag>)(.*?</per-triangle-shape>)'
    
    def add_shared(match):
        before = match.group(1)
        after = match.group(2)
        return before + '\n\t\t<shared>private</shared>' + after
    
    new_content = re.sub(pattern, add_shared, content, flags=re.DOTALL)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  Added <shared>private</shared> to VirtualGround")
    else:
        print(f"  No changes made")

print("\n=== All tail configs processed ===")
