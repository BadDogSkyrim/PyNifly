""" List FO4 nifs with both long and top hair. """

target_directory = r"C:\Modding\Fallout4\mods\00 FO4 Assets\Meshes\Actors\Character\CharacterAssets\Hair"

import os
import pynifly

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
pynifly.NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))


def all_files(directory):
    """Recursively returns all files in a directory and its subdirectories."""

    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".nif"):
                yield os.path.join(root, filename)


def check_nif(f):
    """Check one nif."""
    n = pynifly.NifFile(f)
    for s in n.shapes:
        if len(s.partitions) >= 2:
            if len([subseg for subseg in s.partitions[1].subsegments 
                    if "Hair Long" in subseg.name or "Hair Top" in subseg.name]):
                print(f)


for f in all_files(target_directory):
    if not "_faceBones" in f:
        check_nif(f)