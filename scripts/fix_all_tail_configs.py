import os
import re
import shutil

config_path = r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\SKSE\Plugins\hdtSkinnedMeshConfigs"

# Get all tail config files except the one we already fixed
files = [f for f in os.listdir(config_path) if f.startswith('HDTTail') and f.endswith('.xml')]

for filename in files:
    filepath = os.path.join(config_path, filename)
    
    print(f"\n=== Processing {filename} ===")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find VirtualGround block
    vg_start = -1
    vg_end = -1
    for i, line in enumerate(lines):
        if '<per-triangle-shape name="VirtualGround">' in line:
            vg_start = i
        if vg_start >= 0 and '</per-triangle-shape>' in line:
            vg_end = i
            break
    
    if vg_start < 0:
        print(f"  No VirtualGround found, skipping")
        continue
    
    print(f"  VirtualGround currently at line {vg_start + 1}")
    
    # If already at top (line 3-5), just check for penetration fix
    if vg_start <= 5:
        needs_fix = False
        for i in range(vg_start, vg_end + 1):
            if '<penetration>' in lines[i]:
                lines[i] = lines[i].replace('<penetration>', '<prenetration>')
                lines[i] = lines[i].replace('</penetration>', '</prenetration>')
                needs_fix = True
        
        if needs_fix:
            print(f"  Fixing penetration -> prenetration")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"  Fixed!")
        else:
            print(f"  Already at top, no changes needed")
        continue
    
    # Backup
    shutil.copy(filepath, filepath + '.backup')
    print(f"  Created backup: {filename}.backup")
    
    # Extract VirtualGround block
    vg_block = lines[vg_start:vg_end + 1]
    
    # Fix penetration -> prenetration in block
    for i in range(len(vg_block)):
        vg_block[i] = vg_block[i].replace('<penetration>', '<prenetration>')
        vg_block[i] = vg_block[i].replace('</penetration>', '</prenetration>')
    
    # Remove old VirtualGround block
    new_lines = lines[:vg_start] + lines[vg_end + 1:]
    
    # Find insertion point (after <system> tag)
    insert_at = -1
    for i, line in enumerate(new_lines):
        if '<system ' in line:
            # Find next non-blank, non-comment line
            insert_at = i + 1
            while insert_at < len(new_lines) and (new_lines[insert_at].strip() == '' or new_lines[insert_at].strip().startswith('<!--')):
                insert_at += 1
            break
    
    # Insert VirtualGround at top
    final_lines = new_lines[:insert_at] + ['\n'] + vg_block + ['\n'] + new_lines[insert_at:]
    
    # Save
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    
    print(f"  Moved VirtualGround to line {insert_at + 2} and fixed penetration")
    print(f"  Done!")

print("\n=== All tail configs processed ===")
