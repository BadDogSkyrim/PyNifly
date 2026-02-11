"""
KF ANIMATION IMPORT
"""

import os
import importlib
from contextlib import suppress
import logging
import bpy

from . import import_kf
from . import export_kf


def reload_all():
    if 'PYNIFLY_DEV_ROOT' in os.environ:
        importlib.reload(import_kf)
        importlib.reload(export_kf)


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
    reload_all()
    
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_kf)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_kf)
    with suppress(RuntimeError):
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


if __name__ == "__main__":
    unregister()
    register()
