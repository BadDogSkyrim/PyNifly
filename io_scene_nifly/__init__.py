"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

bl_info = {
    "name": "NIF format (PyNifly)",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (4, 0, 0),
    "version": (27, 2, 0),
    "location": "File > Import-Export",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

import os
import logging
log = logging.getLogger('pynifly')

log.info(f"PyNifly version {'.'.join(map(str, bl_info['version']))} initializing")

DEBUGGING = ('PYNIFLY_DEV_ROOT' in os.environ)

_needs_reload = "bpy" in locals()

import bpy
from contextlib import suppress
from . import nif, tri, hkx, kf
if DEBUGGING:
    from . import osd

if _needs_reload:
    import importlib
    nif = importlib.reload(nif)
    tri = importlib.reload(tri)
    hkx = importlib.reload(hkx)
    kf = importlib.reload(kf)
    if DEBUGGING:
        osd = importlib.reload(osd)
from bpy.types import AddonPreferences
from bpy.props import StringProperty, BoolProperty
class PyNiflyPreferences(AddonPreferences):
    bl_idname = __package__

    sky_texture_path_1: StringProperty(
        name="Skyrim Texture Path 1",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    sky_texture_path_2: StringProperty(
        name="Skyrim Texture Path 2",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    sky_texture_path_3: StringProperty(
        name="Skyrim Texture Path 3",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    sky_texture_path_4: StringProperty(
        name="Skyrim Texture Path 4",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    fo4_texture_path_1: StringProperty(
        name="Fallout Texture Path 1",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    fo4_texture_path_2: StringProperty(
        name="Fallout Texture Path 2",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    fo4_texture_path_3: StringProperty(
        name="Fallout Texture Path 3",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    fo4_texture_path_4: StringProperty(
        name="Fallout Texture Path 4",
        subtype='DIR_PATH',
        default=""
    ) # type: ignore

    rename_bones: BoolProperty(
        name="Blender-friendly bone names",
        description=("Renames bones according to Blender conventions, e.g. .L for left and" + 
                    " .R for right. Disable if you need to match the game's bone names."),
        default=True,
    ) # type: ignore

    rename_bones_niftools: BoolProperty(
        name="NifTools-friendly bone names",
        description=("Renames bones to match the NifTools importer/exporter. Use if you " +
                    "need interoperability with NifTools."),
        default=False
    ) # type: ignore

    rotate_bones_pretty: BoolProperty(
        name="Orient bones along limb",
        description=("Align bones along limb (head to tail), for a natural-looking, "
                    "easy-to-pose skeleton. Display only; no effect on the imported or "
                    "exported result. Disable if you see problems."),
        options={'HIDDEN'},
        default=False
    ) # type: ignore

    import_tris: BoolProperty(
        name="Import tri files when found",
        description=("If importing a nif and a tri file is found with the same name, or the "
            + "name + 'chargen', import the tri as well."),
        default=True
    ) # type: ignore

    import_shapekeys: BoolProperty(
        name="Import as shape keys",
        description=("Import similar objects as shape keys where possible."),
        default=True
    ) # type: ignore

    blender_xf: BoolProperty(
        name="Blender-friendly scene orientation",
        description=("Rotates the scene 90 degrees around the Z axis and scale down to match Blender. " +
                    "Disable to preserve the original orientation."),
        default=False
    ) # type: ignore

    import_cutpoints: BoolProperty(
        name="Import FO4 dismember cutpoints",
        description=("Visualize FO4 dismemberment cut offsets as editable disks on import. "
                    "The cut data is preserved on the mesh either way; this only controls "
                    "whether the disks are created."),
        default=True
    ) # type: ignore

    write_bodytri: BoolProperty(
        name="Export BODYTRI extra data",
        description=("On FO4 export, write an extra-data node pointing to the BODYTRI file when "
                    "there are bodytri shape keys. Not needed for BodySlide, which writes its own."),
        default=True
    ) # type: ignore

    create_collection: BoolProperty(
        name="Import into a new collection",
        description=("Import each nif into its own new collection rather than the active "
                    "collection. Helps keep separate imports organized."),
        default=False
    ) # type: ignore


    def draw(self, context):
        layout = self.layout
        layout.prop(self, "sky_texture_path_1")
        layout.prop(self, "sky_texture_path_2")
        layout.prop(self, "sky_texture_path_3")
        layout.prop(self, "sky_texture_path_4")
        layout.prop(self, "fo4_texture_path_1")
        layout.prop(self, "fo4_texture_path_2")
        layout.prop(self, "fo4_texture_path_3")
        layout.prop(self, "fo4_texture_path_4")
        layout.prop(self, "rename_bones")
        layout.prop(self, "rename_bones_niftools")
        layout.prop(self, "rotate_bones_pretty")
        layout.prop(self, "import_tris")
        layout.prop(self, "import_shapekeys")
        layout.prop(self, "blender_xf")
        layout.prop(self, "import_cutpoints")
        layout.prop(self, "create_collection")
        layout.prop(self, "write_bodytri")

def _configure_logging():
    """Configure console output for the 'pynifly' logger.

    The library modules deliberately no longer call logging.basicConfig (a library
    must not hijack the host app's root logging). Configuring a console handler is
    the application's job, so the add-on does it here. Without this, Python's
    last-resort handler swallows everything below WARNING and INFO progress
    messages never reach the command window.

    The handler itself is left at NOTSET so verbosity is driven by the logger
    level: INFO normally, DEBUG when developing/running tests.
    """
    log.setLevel(logging.DEBUG if DEBUGGING else logging.INFO)
    if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        log.addHandler(handler)
    # We emit through our own handler; don't also propagate to the root logger
    # (avoids duplicate lines if the host configured root logging).
    log.propagate = False


def register():
    bpy.utils.register_class(PyNiflyPreferences)

    _configure_logging()

    hkx.register()
    kf.register()
    nif.register()
    tri.register()
    if DEBUGGING:
        osd.register()

    log.info(f"PyNifly {'.'.join(map(str, bl_info['version']))} registered")

def unregister():
    hkx.unregister()
    kf.unregister()
    nif.unregister()
    tri.unregister()
    if DEBUGGING:
        osd.unregister()

    with suppress(RuntimeError):
        bpy.utils.unregister_class(PyNiflyPreferences)
