import os
import struct
from niflytools import *
from pynifly import *

def ParentName(n):
    if n.parent:
        return n.parent.name
    else:
        return 'None'

def xlate(str):
    if "L Calf" in str:
        str = str.replace("L Calf", "Calf") + ".L"
    elif "R Calf" in str:
        str = str.replace("R Calf", "Calf") + ".R"
    if "L Thigh" in str:
        str = str.replace("L Thigh", "Thigh") + ".L"
    elif "R Thigh" in str:
        str = str.replace("R Thigh", "Thigh") + ".R"
    if "CME L " in str:
        str = str.replace("CME L ", "CME ") + ".L"
    elif "CME R " in str:
        str = str.replace("CME R ", "CME ") + ".R"
    if "NPC L " in str:
        str = str.replace("NPC L ", "NPC ") + ".L"
    elif "NPC R " in str:
        str = str.replace("NPC R ", "NPC ") + ".R"
    elif "SwordLeft" in str:
        str = str.replace("SwordLeft", "Sword") + ".L"
    elif "SwordRight" in str:
        str = str.replace("SwordRight", "Sword") + ".R"
    elif "RightWing" in str:
        str = str.replace("RightWing", "Wing") + ".R"
    elif "LeftWing" in str:
        str = str.replace("LeftWing", "Wing") + ".L"
    elif "AnimObjectR" in str:
        str = str.replace("AnimObjectR", "AnimObject") + ".R"
    elif "AnimObjectL" in str:
        str = str.replace("AnimObjectL", "AnimObject") + ".L"
    str = str.replace("[LF", "[F")
    str = str.replace("[RF", "[F")
    str = str.replace("[LH", "[H")
    str = str.replace("[RH", "[H")
    str = str.replace("[LM", "[M")
    str = str.replace("[RM", "[M")
    
    return str

f = NifFile(r"D:\OneDrive\Dev\PyNifly\PyNifly\skeletons\Skyrim\skeletonbeast.nif")

##for name, node in f.nodes.items():
##	print(f"{xlate(skyrimDict.blender_name(name))}, {name}, {xlate(skyrimDict.blender_name(ParentName(node)))}")

for name, node in f.nodes.items():
    print(f"    SkeletonBone('{xlate(name)}', '{name}', '{xlate(ParentName(node))}'),")
