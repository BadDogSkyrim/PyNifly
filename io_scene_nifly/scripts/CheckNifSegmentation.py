""" List FO4 nifs with bad segmentation for hair. """

target_directory = r"C:\steam\steamapps\common\Fallout 4\Data\Meshes\FFO\Hair"

import os
import pynifly

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
# No need to call NifFile.Load() anymore


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
        if len(s.partitions) < 2:
            print(f"{f}: Not enough partitions")
            continue
        if len(s.partitions[0].subsegments) != 0:
            print(f"{f}: Segment 0 has subsegments")
            continue
        if len(s.partitions[1].subsegments) == 0:
            print(f"{f}: No subsegments in segment 1")

for f in all_files(target_directory):
    if not "_faceBones" in f:
        check_nif(f)