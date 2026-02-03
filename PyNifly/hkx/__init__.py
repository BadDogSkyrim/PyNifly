
"""
HKX ANIMATION IMPORT/EXPORT
"""

from contextlib import suppress
import logging
import bpy
from .import_hkx import ImportHKX, hkxcmd_path
from .export_hkx import ExportHKX, ExportSkelHKX
from .skeleton_hkx import ImportSkel, ExportSkel


def nifly_menu_import_hkx(self, context):
    self.layout.operator(ImportHKX.bl_idname, text="HKX animation or skeleton file with pyNifly (.hkx)")

def nifly_menu_export_hkx(self, context):
    self.layout.operator(ExportHKX.bl_idname, text="HKX file with pyNifly (.hkx)")

def nifly_menu_export_skelhkx(self, context):
    self.layout.operator(ExportSkelHKX.bl_idname, text="Skeleton file with pyNifly (.hkx)")

def nifly_menu_import_skel(self, context):
    self.layout.operator(ImportSkel.bl_idname, text="Skeleton file (.xml)")

def nifly_menu_export_skel(self, context):
    self.layout.operator(ExportSkel.bl_idname, text="Skeleton file (.xml)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_hkx)
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_skel)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_hkx)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_skelhkx)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_skel)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ImportHKX)
        bpy.utils.unregister_class(ImportSkel)
        bpy.utils.unregister_class(ExportHKX)
        bpy.utils.unregister_class(ExportSkelHKX)
        bpy.utils.unregister_class(ExportSkel)

    # Unregister saved path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_hkx
        del bpy.types.WindowManager.pynifly_last_export_path_hkx
        del bpy.types.WindowManager.pynifly_last_export_path_skel_hkx
        del bpy.types.WindowManager.pynifly_last_export_path_skel

def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_hkx)
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_skel)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_hkx)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_skelhkx)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_skel)
    with suppress(RuntimeError):
        bpy.utils.register_class(ImportHKX)
        bpy.utils.register_class(ImportSkel)
    with suppress(RuntimeError):
        bpy.utils.register_class(ExportHKX)
    with suppress(RuntimeError):
        bpy.utils.register_class(ExportSkelHKX)
    with suppress(RuntimeError):
        bpy.utils.register_class(ExportSkel)

    # Register properties to remember last import paths
    bpy.types.WindowManager.pynifly_last_import_path_hkx = bpy.props.StringProperty(
        name="Last HKX Import Path",
        subtype='DIR_PATH',
        default=""
    )
    bpy.types.WindowManager.pynifly_last_export_path_hkx = bpy.props.StringProperty(
        name="Last HKX Export Path",
        subtype='DIR_PATH',
        default=""
    )
    bpy.types.WindowManager.pynifly_last_export_path_skel_hkx = bpy.props.StringProperty(
        name="Last Skeleton HKX Export Path",
        subtype='DIR_PATH',
        default=""
    )

    log = logging.getLogger("pynifly")
    if hkxcmd_path:
        log.debug(f"Found hkxcmd at {hkxcmd_path}")
    else:
        log.error(f"Could not locate hkxcmd in the pyNifly install. Animations cannot be exported to HKX format.")


if __name__ == "__main__":
    unregister()
    register()
