"""
KF ANIMATION IMPORT
"""

from contextlib import suppress
import logging
import bpy
from .import_kf import ImportKF
from .export_kf import ExportKF


def nifly_menu_import_kf(self, context):
    self.layout.operator(ImportKF.bl_idname, text="KF file with pyNifly (.kf)")

def nifly_menu_export_kf(self, context):
    self.layout.operator(ExportKF.bl_idname, text="KF file with pyNifly (.kf)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_kf)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_kf)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ImportKF)
        bpy.utils.unregister_class(ExportKF)

    # Unregister last import path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_kf
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_export_path_kf


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_kf)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_kf)
    with suppress(RuntimeError):
        bpy.utils.register_class(ImportKF)
        bpy.utils.register_class(ExportKF)

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
