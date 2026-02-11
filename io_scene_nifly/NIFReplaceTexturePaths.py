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
from nifdefs import ShaderFlags1, ShaderFlags2

# targetFolder = r"C:\Modding\SkyrimLE\mods\00 Vanilla Assets\meshes"
targetFolder = r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\FurrySkyrim2025\meshes\YAS\Hair"
findString = r"textures\actors\character\hair\apachii\khajiit"
replaceString = r"textures\YAS\Hair\Apachii"

# Folders to exclude
targetExcludes = [
    r'C:\Modding\Fallout4\mods\00 FO4 Assets\Meshes\Actors\Character\FaceGenData',
    r'C:\Modding\SkyrimSE\mods\00 Vanilla Assets\meshes\actors\character\facegendata',
    r'C:\Modding\SkyrimLE\mods\00 Vanilla Assets\meshes\actors\character\facegendata']

pynlog = logging.getLogger("pynifly")

def TestNif(nif:pynifly.NifFile):
    # Find shapes without env map flag but with envmap_light_fade flag
    for k, n in nif.nodes.items():
        if n.collision_object and \
            n.collision_object.body and \
                n.collision_object.body.shape and \
                    n.collision_object.body.shape.blockname == 'bhkSphereShape':
            return True, n.name

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


def FixNifs(fp):
    """Fix all nifs that match criteria."""
    counter = 0
    foundcount = 0
    for f in WalkTree(fp): 
        counter += 1
        if counter % 1000 == 0 and counter > 0:
            print(f"...Checking [{counter}] {os.path.split(f)[0]}")

        changed = 0
        nif = pynifly.NifFile(f)
        for s in nif.shapes:
            for n, p in s.shader.textures.items():
                if findString in p:
                    foundcount += 1
                    print(f"Found {findString} in {f} at {n}: {p}")
                    # Replace the texture path
                    newpath = p.replace(findString, replaceString)
                    s.set_texture(n, newpath)
                    changed += 1
        if changed > 0:
            nif.save()
    print(f"Done. Found {foundcount} in {counter} files")


pynlog = logging.getLogger("pynifly")
pynlog.addHandler(logging.FileHandler('findnifs.log'))


# Load from install location
py_addon_path = os.path.dirname(os.path.realpath(__file__))
if py_addon_path not in sys.path:
    sys.path.append(py_addon_path)
dev_path = os.path.join(py_addon_path, "NiflyDLL.dll")

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
pynifly.NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

FixNifs(targetFolder)

print("Done")