"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (4, 5, 0),
    "version": (23, 0, 1),   
    "location": "File > Import-Export",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

from contextlib import suppress
import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, BoolProperty
from .util.settings import ImportSettings, ExportSettings

from . import nif
from . import tri
from . import hkx
from . import kf

class PyNiflyPreferences(AddonPreferences):
    bl_idname = __package__   # critical: must match your add-on module name

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
        default=ImportSettings.__dataclass_fields__["rename_bones"].default,
    ) # type: ignore

    rename_bones_niftools: BoolProperty(
        name="NifTools-friendly bone names",
        description=("Renames bones to match the NifTools importer/exporter. Use if you " +
                     "need interoperability with NifToos."),
        default=ImportSettings.__dataclass_fields__["rename_bones_niftools"].default
    ) # type: ignore

    rotate_bones_pretty: BoolProperty(
        name="Bone orientation matches skeleton structure",
        description=("Bone orientation matches limbs in humanoid skeletons. " +
                     "Should have no other effect. Disable if you see problems."),
        options={'HIDDEN'},
        default=ImportSettings.__dataclass_fields__["rotate_bones_pretty"].default,
    ) # type: ignore

    import_tris: BoolProperty(
        name="Import tri files when found",
        description=("If importing a nif and a tri file is found with the same name, or the "
            + "name + 'chargen', import the tri as well."),
        default=ImportSettings.__dataclass_fields__["import_tris"].default,
    ) # type: ignore

    blender_xf: BoolProperty(
        name="Blender-friendly scene orientation",
        description=("Rotates the scene 90 degrees around the Z axis and scale down to match Blender. " +
                     "Disable to preserve the original orientation."),
        default=ImportSettings.__dataclass_fields__["blender_xf"].default
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
        layout.prop(self, "blender_xf")

def register():
    bpy.utils.register_class(PyNiflyPreferences)
    hkx.register()
    kf.register()
    nif.register()
    tri.register()

def unregister():
    with suppress(RuntimeError):
        bpy.utils.unregister_class(PyNiflyPreferences)
    hkx.unregister()
    kf.unregister()
    nif.unregister()
    tri.unregister()