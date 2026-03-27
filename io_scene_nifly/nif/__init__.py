"""
Import/Export the nif format
"""
from contextlib import suppress

_needs_reload = "bpy" in locals()

import bpy
from . import import_nif
from . import export_nif
from . import controller
from . import shader_io
from . import collision
from . import connectpoint

if _needs_reload:
    import importlib
    import_nif = importlib.reload(import_nif)
    export_nif = importlib.reload(export_nif)
    controller = importlib.reload(controller)
    shader_io = importlib.reload(shader_io)
    collision = importlib.reload(collision)
    connectpoint = importlib.reload(connectpoint)


def nifly_menu_import_nif(self, context):
    self.layout.operator(import_nif.ImportNIF.bl_idname, text="Nif file with pyNifly (.nif)")

def nifly_menu_export_nif(self, context):
    self.layout.operator(export_nif.ExportNIF.bl_idname, text="Nif file with pyNifly (.nif)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_nif)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_nif)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(import_nif.ImportNIF)
        bpy.utils.unregister_class(export_nif.ExportNIF)

    controller.unregister()

    # Unregister last import path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_nif
        del bpy.types.WindowManager.pynifly_last_export_path_nif


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_nif)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_nif)
    bpy.utils.register_class(import_nif.ImportNIF)
    bpy.utils.register_class(export_nif.ExportNIF)

    controller.register()

    # Register properties to remember last import paths
    bpy.types.WindowManager.pynifly_last_import_path_nif = bpy.props.StringProperty(
        name="Last NIF Import Path",
        subtype='DIR_PATH',
        default=""
    )
    bpy.types.WindowManager.pynifly_last_export_path_nif = bpy.props.StringProperty(
        name="Last NIF Export Path",
        subtype='DIR_PATH',
        default=""
    )
