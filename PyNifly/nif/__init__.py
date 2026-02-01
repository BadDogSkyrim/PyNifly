"""
Import/Export the nif format
"""
import os 
import importlib
from contextlib import suppress
import bpy
from .import_nif import ImportNIF
from .export_nif import ExportNIF
from . import controller
from . import shader_io
from . import controller
from . import collision
from . import connectpoint


if 'PYNIFLY_DEV_ROOT' in os.environ:
    importlib.reload(shader_io)
    importlib.reload(controller)
    importlib.reload(collision)
    importlib.reload(connectpoint)


def nifly_menu_import_nif(self, context):
    self.layout.operator(ImportNIF.bl_idname, text="Nif file with pyNifly (.nif)")

def nifly_menu_export_nif(self, context):
    self.layout.operator(ExportNIF.bl_idname, text="Nif file with pyNifly (.nif)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_nif)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_nif)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ImportNIF)
        bpy.utils.unregister_class(ExportNIF)

    controller.unregister()

    # Unregister last import path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_nif
        del bpy.types.WindowManager.pynifly_last_export_path_nif


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_nif)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_nif)
    with suppress(RuntimeError):
        bpy.utils.register_class(ImportNIF)
        bpy.utils.register_class(ExportNIF)

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


if __name__ == "__main__":
    unregister()
    register()
