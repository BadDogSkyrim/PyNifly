""" List nifs matching the given characteristics. """

target_directory = (r"C:\Modding\FalloutAssets\00 FO4 Assets\Meshes", 
                    r"C:\Modding\SkyrimSEAssets\00 Vanilla Assets\meshes",
                    )

import math
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


## Check how NiVisControllers use NiBlendBoolInterpolator.
# def check_nif(outfile, fn):
#     """Check one nif."""
#     f = pynifly.NifFile(fn)
#     for n, b in f.nodes.items():
#         s = ""
#         if b.controller:
#             if b.controller.blockname == "NiVisController":
#                 s = f"{fn}\tNiVisController"
#                 if b.controller.interpolator:
#                     s = s + "\t" + b.controller.interpolator.blockname
#                     if b.controller.interpolator.blockname == "NiBlendBoolInterpolator":
#                         s = (s + f"\tweight={b.controller.interpolator.properties.weightThreshold}"
#                             + f"\tvalue={b.controller.interpolator.properties.boolValue}")
#                         if not (math.isclose(b.controller.interpolator.properties.weightThreshold, 0.0)
#                                 and b.controller.interpolator.properties.boolValue == 2):
#                             s = s + "\tEXCEPTION"
#                 else:
#                     s = s + "\tno interpolator"
#         if s: outfile.write(s + "\n")

# # Check how BSEffectShaderPropertyFloatController uses NiBlendFloatInterpolator.
# def check_nif(outfile, fn):
#     """Check one nif."""
#     f = pynifly.NifFile(fn)
#     for n, b in f.nodes.items():
#         s = ""
#         if (hasattr(b, "shader") and b.shader and b.shader.controller 
#                 and b.shader.controller.blockname == "BSEffectShaderPropertyFloatController"):
#             s = f"{fn}\tBSEffectShaderPropertyFloatController"
#             if b.shader.controller.interpolator:
#                 s = s + "\t" + b.shader.controller.interpolator.blockname
#                 if b.shader.controller.interpolator.blockname == "NiBlendFloatInterpolator":
#                     s = (s + f"\tweight={b.shader.controller.interpolator.properties.weightThreshold}"
#                         + f"\tvalue={b.shader.controller.interpolator.properties.floatValue}")
#             else:
#                 s = s + "\tNO INTERPOLATOR"
#         if s: outfile.write(s + "\n")

# Check ControllerID and Interpolator ID values
headers = ("Filename", "ControllerName", "ControllerID", "InterpolatorID")
def check_nif(outfile, fn):
    """Check one nif."""
    f = pynifly.NifFile(fn)
    if f.root.controller and f.root.controller.blockname == "NiControllerManager":
        for cs_name, cs in f.root.controller.sequences.items():
            for cb in cs.controlled_blocks:
                outfile.write(
                    f"{fn}\t{cs_name}\tCtlr={cb.properties.controllerID}\tInterp={cb.properties.interpolatorID}\n")


documents_folder = os.path.join(os.path.expanduser("~"), "Documents")
output_path = os.path.join(documents_folder, "nif_info.txt")
with open(output_path, "w", encoding="utf-8") as outfile:
    outfile.write("\t".join(headers) + "\n")
    for td in target_directory:
        print(f"Checking {td}")
        for i, f in enumerate(all_files(td)):
            if i % 1000 == 0:
                print(f"Checked {i} files...")
            check_nif(outfile, f)
print(f"Done. Wrote output to {output_path}")