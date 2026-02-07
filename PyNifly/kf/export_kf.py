"""
KF ANIMATION EXPORT
"""

from contextlib import suppress
import logging
from pathlib import Path
import bpy
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
from ..pyn.pynifly import nifly_path, pynifly_dev_path, pynifly_addon_path, NifFile
from ..pyn.nifdefs import PynIntFlag
from ..blender_defs import LogHandler
from ..nif.controller import ControllerHandler
from .. import bl_info

log = logging.getLogger("pynifly")

class ImportSettingsKF(PynIntFlag):
    create_bones = 1
    rename_bones = 1<<1
    import_anims = 1<<2
    rename_bones_nift = 1<<3
    roll_bones_nift = 1<<4


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
        
        ControllerHandler.export_animation(kfx, context.object)

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

        pyniflyPrefs = bpy.context.preferences.addons["PyNifly"].preferences
        self.do_rename_bones = pyniflyPrefs.rename_bones
        self.rename_bones_niftools = pyniflyPrefs.rename_bones_nift
        if bpy.context.object and bpy.context.object.type == 'ARMATURE':
            arma = bpy.context.object
            self.do_rename_bones = arma.get('PYN_RENAME_BONES', self.do_rename_bones)
            self.do_rename_bones_niftools = arma.get('PYN_RENAME_BONES_NIFTOOLS', self.rename_bones_niftools)
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
        self.log_handler = LogHandler.New(bl_info, "EXPORT", "KF")

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

