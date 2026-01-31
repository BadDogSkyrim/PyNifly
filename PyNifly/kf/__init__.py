"""
KF ANIMATION IMPORT
"""

import os
from contextlib import suppress
import logging
from pathlib import Path
import bpy
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
from PyNifly.pynifly import nifly_path, NifFile
from PyNifly.nifdefs import PynIntFlag
import PyNifly.blender_defs as BD
import PyNifly.nif.controller as controller
from PyNifly.nif.import_nif import NifImporter

log = logging.getLogger("pynifly")

class ImportSettingsKF(PynIntFlag):
    create_bones = 1
    rename_bones = 1<<1
    import_anims = 1<<2
    rename_bones_nift = 1<<3
    roll_bones_nift = 1<<4


class ImportKF(bpy.types.Operator, ImportHelper):
    """Import Blender animation to an armature"""

    bl_idname = "import_scene.pynifly_kf"
    bl_label = 'Import KF (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".kf"
    filter_glob: StringProperty(
        default="*.kf",
        options={'HIDDEN'},
    ) # type: ignore

    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    ) # type: ignore

    directory: StringProperty() # type: ignore

    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False

        if (not context.object) or context.object.type != "ARMATURE":
            # log.error("Cannot import KF: Active object must be an armature.")
            return False

        if context.object.mode != 'OBJECT':
            # log.error("Must be in Object Mode to import")
            return False

        return True
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nif:NifFile = None
        self.armature = None
        self.import_flags = ImportSettingsKF.import_anims # KF file always imports animations

        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            self.reference_skel = obj.get('PYN_SKELETON_FILE', '')
            self.do_rename_bones = obj.get('PYN_RENAME_BONES', BD.RENAME_BONES_DEF)
            self.rename_bones_niftools = obj.get('PYN_RENAME_BONES_NIFTOOLS', BD.RENAME_BONES_NIFT_DEF)


    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_import_path_kf:
            self.filepath = str(Path(context.window_manager.pynifly_last_import_path_kf) 
                                / Path(self.filepath))
        return super().invoke(context, event)


    def execute(self, context):
        res = set()
        self.file_path = Path(self.filepath)
        self.directory_path = Path(self.directory)

        if not self.poll(context):
            self.report({"ERROR"}, f"Cannot run importer--see system console for details")
            return {'CANCELLED'} 

        self.log_handler = BD.LogHandler()
        self.log_handler.start(BD.bl_info, "IMPORT", "KF")

        if self.do_rename_bones: 
            self.import_flags |= ImportSettingsKF.rename_bones
        if self.rename_bones_niftools: 
            self.import_flags |= ImportSettingsKF.rename_bones_nift
        self.collection = bpy.data.collections.new(self.file_path.stem)
        context.scene.collection.children.link(self.collection)
        try:
            NifFile.Load(nifly_path)
            folderpath = self.file_path.parent
            filenames = [f.name for f in self.files]
            if filenames:
                fullfiles = [folderpath / f.name for f in self.files]
            else:
                fullfiles = [self.file_path]
            for filename in fullfiles:
                filepath = self.directory_path / filename
                imp = NifImporter(filepath, [], [], self.import_flags,
                                  collection=self.collection)
                imp.context = context
                imp.armature = context.object
                imp.nif = NifFile(filepath)
                imp.import_nif()

        except Exception as e:
            self.log_handler.log.exception(f"Import of KF failed: {e}")
            self.report({"ERROR"}, "Import of KF failed, see console window for details.")
            res.add('CANCELLED')

        finally:
            self.log_handler.finish("IMPORT", self.filepath)

        # Save the directory path for next time
        if 'CANCELLED' not in res:
            wm = context.window_manager
            wm.pynifly_last_import_path_kf = os.path.dirname(self.filepath)
            res.add('FINISHED')

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

################################################################################
#                                                                              #
#                             KF ANIMATION EXPORT                              #
#                                                                              #
################################################################################

class KFExporter():
    def __init__(self, filepath:Path, context, 
                 fps=30, do_rename_bones=True, rename_bones_niftools=False):
        self.file_path = filepath
        self.context = context
        self.filename_base = self.file_path.stem
        self.fps = fps
        self.do_rename_bones = do_rename_bones
        self.rename_bones_niftools = rename_bones_niftools

        
    def nif_name(self, blender_name):
        if self.do_rename_bones or self.rename_bones_nift:
            return self.nif.nif_name(blender_name)
        else:
            return blender_name


    @classmethod
    def Export(cls, filepath:Path, context,
               fps=30, do_rename_bones=True, rename_bones_niftools=False):
        kfx = KFExporter(filepath, context,
            fps=30, do_rename_bones=True, rename_bones_niftools=False)

        # Export whatever animation is attached to the active object.
        kfx.nif = NifFile()
        kfx.nif.initialize("SKYRIM", str(filepath), "NiControllerSequence", 
                            kfx.filename_base)
        
        controller.ControllerHandler.export_animation(kfx, context.object)

        kfx.nif.save()


class ExportKF(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.pynifly_kf"
    bl_label = 'Export KF (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".kf"

    fps: bpy.props.FloatProperty(
        name="FPS",
        description="Frames per second for export",
        default=30) # type: ignore

    do_rename_bones: bpy.props.BoolProperty(
        name="Rename Bones",
        description="Rename bones from Blender conventions back to nif.",
        default=True) # type: ignore

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename Bones as per NifTools",
        description="Rename bones from NifTools' Blender conventions back to nif.",
        default=False) # type: ignore


    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False

        if (not context.object) or context.object.type != 'ARMATURE':
            # log.debug("Must select an armature to export animations.")
            return False

        if (not context.object.animation_data) or (not context.object.animation_data.action):
            # log.debug("Active object must have an animation associated with it.")
            return False

        return True
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []
        self.errors = set()
        self.given_scale_warning = False

        NifFile.Load(nifly_path)

        if bpy.context.object and bpy.context.object.type == 'ARMATURE':
            arma = bpy.context.object
            if 'PYN_RENAME_BONES' in arma:
                self.do_rename_bones = arma['PYN_RENAME_BONES']
            if 'PYN_RENAME_BONES_NIFTOOLS' in arma:
                self.do_rename_bones_niftools = arma['PYN_RENAME_BONES_NIFTOOLS']


    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_export_path_kf:
            self.filepath = str(Path(context.window_manager.pynifly_last_export_path_kf) 
                                / Path(self.filepath))
        return super().invoke(context, event)

    def execute(self, context):
        self.context = context
        res = set()
        self.log_handler = BD.LogHandler.New(BD.bl_info, "EXPORT", "KF")

        if not self.poll(context):
            return {'CANCELLED'} 

        if self.fps <= 0 or self.fps >= 200:
            self.report({"ERROR"}, f"FPS outside of valid range, using 30fps: {self.fps}")
            self.fps = 30

        if not self.filepath \
                and bpy.context.object.animation_data \
                and bpy.context.object.animation_data.action:
            self.filepath =  bpy.context.object.animation_data.action.name
        self.file_path = Path(self.filepath)
            
        try:
            KFExporter.Export(self.file_path, context,
                fps=self.fps, 
                do_rename_bones=self.do_rename_bones, 
                rename_bones_niftools=self.rename_bones_niftools)
        except:
            log.exception("Export of KF failed")

        if self.log_handler.max_error >= logging.ERROR:
            self.report({"ERROR"}, "Export of KF failed, see console window for details")
            res.add("CANCELLED")
            self.log_handler.finish("EXPORT", str(self.file_path))

        # Save the directory path for next time
        if 'CANCELLED' not in res:
            wm = context.window_manager
            wm.pynifly_last_export_path_kf = str(self.file_path.parent)

        return res.intersection({'CANCELLED'}, {'FINISHED'})


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
        del bpy.types.WindowManager.pynifly_last_import_path_nif
        del bpy.types.WindowManager.pynifly_last_import_path_tri
        del bpy.types.WindowManager.pynifly_last_import_path_kf
        del bpy.types.WindowManager.pynifly_last_import_path_hkx
    # Unregister last export path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_export_path_nif
        del bpy.types.WindowManager.pynifly_last_export_path_kf
        del bpy.types.WindowManager.pynifly_last_export_path_hkx
        del bpy.types.WindowManager.pynifly_last_export_path_skel_hkx
    # 356
    # +900

def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_kf)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_kf)

    # Register properties to remember last import paths
    bpy.types.WindowManager.pynifly_last_import_path_kf = StringProperty(
        name="Last KF Import Path",
        subtype='DIR_PATH',
        default=""
    )
    bpy.types.WindowManager.pynifly_last_export_path_kf = StringProperty(
        name="Last KF Export Path",
        subtype='DIR_PATH',
        default=""
    )


if __name__ == "__main__":
    unregister()
    register()
