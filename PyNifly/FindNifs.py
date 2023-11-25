'''
Find nifs that have certain characteristics.
'''
import os
import sys
import struct
import collections
import logging
from ctypes import Structure, c_bool, c_char, c_float, c_uint8, c_uint32
from pathlib import Path
import pynifly
import nifdefs

targetFolder = r"C:\Modding\Fallout4\mods\00 FO4 Assets\Meshes"

# Folders to exclude
targetExcludes = [r'C:\Modding\Fallout4\mods\00 FO4 Assets\Meshes\Actors\Character\FaceGenData']

pynlog = logging.getLogger("pynifly")

def TestNif(n:pynifly.NifFile):
    for s in n.shapes:
        if s.shader.blockname == 'BSLightingShaderProperty' \
            and s.shader.properties.Alpha != 1.0:
            return True, s.name

    return False, None

def WalkTree(folder_path):
    """Return all nif files in a directory tree, recursively."""
    for root, directories, files in os.walk(folder_path):
        excl = [x for x in targetExcludes if root.startswith(x)]
        if not excl:
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
    counter = 0
    foundcount = 0
    foundlist = []
    for f in WalkTree(fp):
        if counter % 1000 == 0 and counter > 0:
            print(f"...Checking [{counter}] {os.path.split(f)[0]}")
        try:
            b, n = TestNif(pynifly.NifFile(f))
            if b:
                # foundlist.append((f, n, ))
                print(f, n)
                foundcount += 1
        except Exception as e:
            pynlog.debug(f + ": " + str(e))
        counter += 1
    print(f"Done. Found {foundcount} in {counter} files")
    # for f, n in foundlist:
    #     print(f, n)


pynlog = logging.getLogger("pynifly")
pynlog.addHandler(logging.FileHandler('findnifs.log'))


# Load from install location
py_addon_path = os.path.dirname(os.path.realpath(__file__))
if py_addon_path not in sys.path:
    sys.path.append(py_addon_path)
dev_path = os.path.join(py_addon_path, "NiflyDLL.dll")

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
pynifly.NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

# pynlog.addHandler(LoggerListHandler)

PrintNifs(targetFolder)

print("Done")