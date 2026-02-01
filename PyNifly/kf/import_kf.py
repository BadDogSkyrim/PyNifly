"""
#                                                                              #
#                             KF ANIMATION IMPORT                              #
#                                                                              #
"""

import os
from contextlib import suppress
import logging
from pathlib import Path
import bpy
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
from ..pyn.pynifly import nifly_path, pynifly_dev_path, pynifly_addon_path, NifFile
from ..pyn.nifdefs import PynIntFlag
from ..blender_defs import RENAME_BONES_DEF, RENAME_BONES_NIFT_DEF, LogHandler
from ..nif.import_nif import NifImporter
from .. import bl_info

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
            self.do_rename_bones = obj.get('PYN_RENAME_BONES', RENAME_BONES_DEF)
            self.rename_bones_niftools = obj.get('PYN_RENAME_BONES_NIFTOOLS', RENAME_BONES_NIFT_DEF)


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

        self.log_handler = LogHandler()
        self.log_handler.start(bl_info, "IMPORT", "KF")

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
