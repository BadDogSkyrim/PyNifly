""" Modify nifs matching the given characteristics. """
from pathlib import Path

target_directory = (r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\BD Canine Races\meshes",
                    )

asset_dirs = (Path(r"C:\Users\hughr\AppData\Roaming\Vortex\skyrimse\mods\Cat Races-44919-2-2-1611793835\textures"),
              Path(r"C:\Modding\SkyrimSEAssets\00 Vanilla Assets\textures"),
              Path(r"C:\steam\steamapps\common\Skyrim Special Edition\Data\textures"),
              )

import math
import os
import pynifly

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
pynifly.NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

replacers = (
    (r"textures\actors\character\lykaios\hair", r"textures\YAS\Hair"),
    (r"textures\actors\character\hair\apachii", r"textures\YAS\Hair\Apachii"),
    (r"textures\actors\character\sabrelionmale", r"textures\YAS\Hair"),
    (r"textures\YAS\Hair\Male\manecolor", r"textures\YAS\Hair\manecolor"),
    (r"textures\actors\character\hair\nuska", r"textures\YAS\Hair\Nuska")
)


def all_files(directory):
    """Recursively returns all files in a directory and its subdirectories."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".nif"):
                yield os.path.join(root, filename)


def path_exists(tex_path, asset_dirs):
    """Check if a texture path exists in any of the asset directories."""
    for ad in asset_dirs:
        texpath = Path(tex_path)
        texparts = texpath.parts
        if texparts and texparts[0].lower() == "textures":
            texpath = Path(*texparts[1:])
        full_path = ad / texpath
        if full_path.exists():
            return True
    return False


def fix_nif(fn):
    """Fix one nif."""
    nif = pynifly.NifFile(fn)
    modified = False
    for shape in nif.shapes:
        if shape.shader and -0.001 < shape.shader.properties.Glossiness < 0.001:
            shape.shader.properties.Glossiness = 64
            shape.shader.write_properties()
            modified = True

    if modified:
        print(f"Modified {fn}")
        nif.save()


documents_folder = os.path.join(os.path.expanduser("~"), "Documents")
for td in target_directory:
    print(f"Checking {td}")
    for i, f in enumerate(all_files(td)):
        if i % 1000 == 0:
            print(f"Checked {i} files...")
        fix_nif(f)
print(f"Done.")