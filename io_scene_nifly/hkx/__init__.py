"""
HKX ANIMATION IMPORT/EXPORT
"""
from contextlib import suppress
import logging

_needs_reload = "bpy" in locals()

import bpy
from . import import_hkx
from . import export_hkx
from . import skeleton_hkx
from . import anim_fo4

if _needs_reload:
    import importlib
    anim_fo4 = importlib.reload(anim_fo4)
    import_hkx = importlib.reload(import_hkx)
    export_hkx = importlib.reload(export_hkx)
    skeleton_hkx = importlib.reload(skeleton_hkx)


def nifly_menu_import_hkx(self, context):
    self.layout.operator(import_hkx.ImportHKX.bl_idname, text="HKX animation or skeleton file with pyNifly (.hkx)")

def nifly_menu_export_hkx(self, context):
    self.layout.operator(export_hkx.ExportHKX.bl_idname, text="HKX file with pyNifly (.hkx)")

def nifly_menu_export_skelhkx(self, context):
    self.layout.operator(export_hkx.ExportSkelHKX.bl_idname, text="Skeleton file with pyNifly (.hkx)")

def nifly_menu_import_skel(self, context):
    self.layout.operator(skeleton_hkx.ImportSkel.bl_idname, text="Skeleton file (.xml)")

def nifly_menu_export_skel(self, context):
    self.layout.operator(skeleton_hkx.ExportSkel.bl_idname, text="Skeleton file (.xml)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_hkx)
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_skel)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_hkx)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_skelhkx)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_skel)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(import_hkx.ImportHKX)
        bpy.utils.unregister_class(skeleton_hkx.ImportSkel)
        bpy.utils.unregister_class(export_hkx.ExportHKX)
        bpy.utils.unregister_class(export_hkx.ExportSkelHKX)
        bpy.utils.unregister_class(skeleton_hkx.ExportSkel)

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
        bpy.utils.register_class(import_hkx.ImportHKX)
        bpy.utils.register_class(skeleton_hkx.ImportSkel)
    with suppress(RuntimeError):
        bpy.utils.register_class(export_hkx.ExportHKX)
    with suppress(RuntimeError):
        bpy.utils.register_class(export_hkx.ExportSkelHKX)
    with suppress(RuntimeError):
        bpy.utils.register_class(skeleton_hkx.ExportSkel)

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
    if import_hkx.hkxcmd_path:
        log.debug(f"Found hkxcmd at {import_hkx.hkxcmd_path}")
    else:
        log.error(f"Could not locate hkxcmd in the pyNifly install. Animations cannot be exported to HKX format.")
