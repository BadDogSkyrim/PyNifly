"""Import BodySlide OSD files."""

from contextlib import suppress
import bpy
from .import_osd import ImportOSD


def nifly_menu_import_osd(self, context):
    self.layout.operator(ImportOSD.bl_idname, text="BodySlide OSD file (PyNifly)")


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_osd)
    bpy.utils.register_class(ImportOSD)

    bpy.types.WindowManager.pynifly_last_import_path_osd = bpy.props.StringProperty(
        name="Last OSD Import Path",
        subtype='DIR_PATH',
        default=""
    )


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_osd)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ImportOSD)

    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_osd
