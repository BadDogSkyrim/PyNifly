"""
KF ANIMATION IMPORT
"""
from contextlib import suppress
import logging

_needs_reload = "bpy" in locals()

import bpy
from . import import_kf
from . import export_kf

if _needs_reload:
    import importlib
    import_kf = importlib.reload(import_kf)
    export_kf = importlib.reload(export_kf)


def nifly_menu_import_kf(self, context):
    self.layout.operator(import_kf.ImportKF.bl_idname, text="KF file with pyNifly (.kf)")

def nifly_menu_export_kf(self, context):
    self.layout.operator(export_kf.ExportKF.bl_idname, text="KF file with pyNifly (.kf)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_kf)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_kf)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(import_kf.ImportKF)
        bpy.utils.unregister_class(export_kf.ExportKF)

    # Unregister last import path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_kf
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_export_path_kf


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_kf)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_kf)
    bpy.utils.register_class(import_kf.ImportKF)
    bpy.utils.register_class(export_kf.ExportKF)

    # Register properties to remember last import paths
    bpy.types.WindowManager.pynifly_last_import_path_kf = bpy.props.StringProperty(
        name="Last KF Import Path",
        subtype='DIR_PATH',
        default=""
    )
    bpy.types.WindowManager.pynifly_last_export_path_kf = bpy.props.StringProperty(
        name="Last KF Export Path",
        subtype='DIR_PATH',
        default=""
    )
