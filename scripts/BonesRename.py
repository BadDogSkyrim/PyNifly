import os
import struct
from niflytools import *
from pynifly import *

nifly_path = r"C:\Users\User\OneDrive\Dev\PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
NifFile.Load(nifly_path)
NifFile.log.setLevel(logging.DEBUG)

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
    elif "R Calf" in str:
        str = str.replace("R Calf", "Calf") + ".R"
    elif "L Foot" in str:
        str = str.replace("L Foot", "Foot") + ".L"
    elif "R Foot" in str:
        str = str.replace("R Foot", "Foot") + ".R"
    elif "L Toe" in str:
        str = str.replace("L Toe", "Toe") + ".L"
    elif "R Toe" in str:
        str = str.replace("R Toe", "Toe") + ".R"
    elif "L Clavicle" in str:
        str = str.replace("L Clavicle", "Clavicle") + ".L"
    elif "R Clavicle" in str:
        str = str.replace("R Clavicle", "Clavicle") + ".R"
    elif "L Thumb" in str:
        str = str.replace("L Thumb", "Thumb") + ".L"
    elif "R Thumb" in str:
        str = str.replace("R Thumb", "Thumb") + ".R"
    elif "L Finger" in str:
        str = str.replace("L Finger", "Finger") + ".L"
    elif "R Finger" in str:
        str = str.replace("R Finger", "Finger") + ".R"
    elif "L Forearm" in str:
        str = str.replace("L Forearm", "Forearm") + ".L"
    elif "R Forearm" in str:
        str = str.replace("R Forearm", "Forearm") + ".R"
    elif "L ForeTwist" in str:
        str = str.replace("L ForeTwist", "ForeTwist") + ".L"
    elif "R ForeTwist" in str:
        str = str.replace("R ForeTwist", "ForeTwist") + ".R"
    elif "L Hand" in str:
        str = str.replace("L Hand", "Hand") + ".L"
    elif "R Hand" in str:
        str = str.replace("R Hand", "Hand") + ".R"
    elif "L UpperArm" in str:
        str = str.replace("L UpperArm", "UpperArm") + ".L"
    elif "R UpperArm" in str:
        str = str.replace("R UpperArm", "UpperArm") + ".R"
    elif "L Breast" in str:
        str = str.replace("L Breast", "Breast") + ".L"
    elif "R Breast" in str:
        str = str.replace("R Breast", "Breast") + ".R"
    elif "LUpArmTwistBone" in str:
        str = str.replace("LUpArmTwistBone", "UpArmTwistBone") + ".L"
    elif "RUpArmTwistBone" in str:
        str = str.replace("RUpArmTwistBone", "UpArmTwistBone") + ".R"
    elif "LPauldron" in str:
        str = str.replace("LPauldron", "Pauldron") + ".L"
    elif "RPauldron" in str:
        str = str.replace("RPauldron", "Pauldron") + ".R"
    if "L Thigh" in str:
        str = str.replace("L Thigh", "Thigh") + ".L"
    elif "R Thigh" in str:
        str = str.replace("R Thigh", "Thigh") + ".R"
    if "LArm" in str:
        str = str.replace("LArm", "Arm") + ".L"
    elif "RArm" in str:
        str = str.replace("RArm", "Arm") + ".R"
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
    elif "SkirtL" in str:
        str = str.replace("SkirtL", "Skirt") + ".L"
    elif "SkirtR" in str:
        str = str.replace("SkirtR", "Skirt") + ".R"
    elif "_L_" in str:
        str = str.replace("_L_", "_") + ".L"
    elif "_R_" in str:
        str = str.replace("_R_", "_") + ".R"

    s1 = str.split("[")
    s2 = str.split("]")
    if len(s2) > 1:
        str = s1[0].strip() + s2[1]
    
    return str


f = NifFile(r"C:\ModOrganizer\Fallout4\mods\00 FO4 Assets\Meshes\Actors\Character\CharacterAssets\BaseMaleHead_faceBones.nif")

##for name, node in f.nodes.items():
##	print(f"{xlate(skyrimDict.blender_name(name))}, {name}, {xlate(skyrimDict.blender_name(ParentName(node)))}")

for name, node in f.nodes.items():
    print(f"    SkeletonBone('{xlate(name)}', '{name}', '{xlate(ParentName(node))}'),")
