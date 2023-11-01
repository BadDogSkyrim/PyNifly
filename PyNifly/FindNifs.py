'''
Find nifs that have certain characteristics.
'''
import os
import sys
import struct
import collections
from ctypes import Structure, c_bool, c_char, c_float, c_uint8, c_uint32
from pathlib import Path
import pynifly

targetFolder = r"C:\Modding\Fallout4\mods\00 FO4 Assets\Meshes"


def WalkTree(folder_path):
    """Return all nif files in a directory tree, recursively."""
    for root, directories, files in os.walk(folder_path):
        for filename in files:
            if os.path.splitext(filename)[1].upper() == '.NIF':
                file_path = os.path.join(root, filename)
                yield file_path

def FileExistsInPaths(fn, rootlist):
    """Determine whether the given file exists in any of the given mod roots."""
    ext = os.path.splitext(fn)[1].upper()
    found = False
    if ext == '.BGSM':
        folder = 'materials'
    elif ext == '.DDS':
        folder = 'textures'
    else: 
        found = True

    if not found:
        for r in rootlist:
            fp = os.path.join(r, folder, fn)
            if os.path.exists(fp):
                found = True
                break

    return found


def PrintNifs(fp):
    """Find all nifs that match criteria."""
    targ = Path(fp)
    for f in WalkTree(fp):
        n = pynifly.NifFile(f)
        for s in n.shapes:
            if s.shader.UV_Scale_U != 1.0:
                print(n.filepath)
            

# Load from install location
py_addon_path = os.path.dirname(os.path.realpath(__file__))
if py_addon_path not in sys.path:
    sys.path.append(py_addon_path)
dev_path = os.path.join(py_addon_path, "NiflyDLL.dll")

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
pynifly.NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

PrintNifs(targetFolder)

print("Done")