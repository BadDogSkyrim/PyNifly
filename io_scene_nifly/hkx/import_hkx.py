"""

HKX ANIMATION IMPORT

"""
import os
import subprocess
import logging
from pathlib import Path
import xml.etree.ElementTree as xml
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from ..pyn.nifdefs import PynIntFlag
from ..pyn.niflytools import tmp_copy_nospace, tmp_copy, tmp_filepath
from ..pyn.pynifly import nifly_path, pynifly_dev_path, pynifly_addon_path, NifFile
from .. import blender_defs as bdefs
from .. import bl_info
from ..util.settings import ImportSettings
from ..pyn.xmltools import XMLFile
from ..nif.import_nif import NifImporter


hkxcmd_path = None

if pynifly_dev_path:
    hkxcmd_path = os.path.join(pynifly_dev_path, "hkxcmd.exe")
else:
    hkxcmd_path = os.path.join(pynifly_addon_path, "hkxcmd.exe")

log = logging.getLogger("pynifly")


################################################################################
#                                                                              #
#                             HKX ANIMATION IMPORT                              #
#                                                                              #
################################################################################

class ImportHKX(bpy.types.Operator, ImportHelper):
    """Import HKX file--either a skeleton or an animation to an armature"""

    bl_idname = "import_scene.pynifly_hkx"
    bl_label = 'Import HKX file (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"
    filter_glob: StringProperty(
        default="*.hkx",
        options={'HIDDEN'},
    ) # type: ignore

    blender_xf: bpy.props.BoolProperty(
        name="Use Blender orientation",
        description="Use Blender's orientation and scale",
        default=ImportSettings.__dataclass_fields__["blender_xf"].default) # type: ignore

    rename_bones: bpy.props.BoolProperty(
        name="Rename bones",
        description="Rename bones to conform to Blender's left/right conventions.",
        default=ImportSettings.__dataclass_fields__["rename_bones"].default) # type: ignore

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename bones as per NifTools",
        description="Rename bones using NifTools' naming scheme to conform to Blender's left/right conventions.",
        default=ImportSettings.__dataclass_fields__["rename_bones_niftools"].default) # type: ignore
    
    reference_skel: bpy.props.StringProperty(
        name="Reference skeleton",
        description="HKX reference skeleton to use for animation binding",
        default="") # type: ignore

    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False
        if not hkxcmd_path:
            log.error("hkxcmd.exe not found--HKX I/O not available.")
            return False
        return True
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kf:NifFile = None
        self.armature = None
        self.errors = set()
        self.import_flags = ImportSettings()
        self.animation_name = None
        self.hkx_filepath:Path = None
        self.xml_filepath:Path = None
        self.kf_filepath:Path = None


    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_import_path_hkx:
            self.filepath = str(Path(context.window_manager.pynifly_last_import_path_hkx) 
                                / Path(self.filepath))

        # Override defaults with addon user preferences
        pyniflyPrefs = bpy.context.preferences.addons["io_scene_nifly"].preferences
        self.rename_bones = pyniflyPrefs.rename_bones
        self.rename_bones_niftools = pyniflyPrefs.rename_bones_niftools
        self.blender_xf = pyniflyPrefs.blender_xf

        # Override addon preferences with whatever the selected armature needs.
        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            self.reference_skel = obj.get('PYN_SKELETON_FILE', self.reference_skel)
            self.rename_bones = obj.get('PYN_RENAME_BONES', self.rename_bones)
            self.rename_bones_niftools = obj.get('PYN_RENAME_BONES_NIFTOOLS', self.rename_bones_niftools)
            self.blender_xf = obj.get('PYN_BLENDER_XF', self.blender_xf)

        return super().invoke(context, event)


    def __str__(self):
        return f"""
        Importing HXK: {self.filename_list} 
            setings: {self.import_flags}
            armature: {self.armature} 
        """


    def execute(self, context):
        res = set()
        self.context = context
        self.fps = context.scene.render.fps
        self.hkx_filepath = Path(self.filepath)

        self.import_flags.rename_bones = self.rename_bones
        self.import_flags.rename_bones_niftools = self.rename_bones_niftools
        self.import_flags.blender_xf = self.blender_xf

        try:
            self.log_handler = bdefs.LogHandler.New(bl_info, "IMPORT", "HKX")

            NifFile.Load(nifly_path)
            XMLFile.SetPath(hkxcmd_path)
            self.xmlfile = XMLFile(self.filepath, self)
            if self.xmlfile.contains_skeleton:
                self.import_skeleton()

            if self.xmlfile.contains_animation:
                if self.reference_skel:
                    self.reference_skel = self.reference_skel.strip('"')
                    fp, ext = os.path.splitext(self.reference_skel)
                    if ext.lower() != ".hkx":
                        log.error(f"Must have an HKX file to use as reference skeleton.")
                        return {'CANCELLED'}
                    self.reference_skel_short = tmp_copy_nospace(Path(self.reference_skel))

                if not context.object:
                    log.error(f"Must have selected object for animation.")
                    return {'CANCELLED'}
                if not self.reference_skel:
                    log.error(f"Must provide a reference skeleton for the animation.")
                    return {'CANCELLED'}
                if self.reference_skel:
                    context.object['PYN_SKELETON_FILE'] = self.reference_skel

                self.animation_name = self.hkx_filepath.stem
                stat = self.import_animation()
                res.add(stat)

        except:
            self.log_handler.log.exception("Import of HKX file failed")
            log.error("Import of HKX failed, see console window for details")
            res.add('CANCELLED')

        finally:
            self.log_handler.finish("IMPORT", self.filepath)

        # Save the directory path for next time
        wm = context.window_manager
        wm.pynifly_last_import_path_hkx = str(self.filepath)
        if 'CANCELLED' not in res:
            res.add('FINISHED')

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

    def warn(self, msg):
        self.report({"WARNING"}, msg)
        self.errors.add("WARNING")

    def error(self, msg):
        self.report({"ERROR"}, msg)
        self.errors.add("ERROR")

    def info(self, msg):
        self.report({"INFO"}, msg)


    def import_skeleton(self):
        """self.xmlfile has a skeleton in it. Import the skeleton."""
        imp = NifImporter([self.xmlfile.xml_filepath], import_settings=self.import_flags)
        imp.context = self.context
        if self.context.view_layer.active_layer_collection: 
            imp.collection = self.context.view_layer.active_layer_collection.collection
        imp.settings.create_bones = False
        imp.settings.rename_bones = self.rename_bones
        imp.settings.rename_bones_niftools = self.rename_bones_niftools
        imp.settings.import_animations = True
        imp.settings.import_tris = False
        if self.blender_xf:
            imp.settings.blender_xf = bdefs.blender_import_xf
        imp.execute()
        objlist = [x for x in imp.objects_created.blender_objects() if x.type=='MESH']
        if imp.armature:
            objlist.append(imp.armature)
        bdefs.highlight_objects(objlist, self.context)


    def import_animation(self):
        """self.xmlfile has an animation in it. Import the animation."""
        kf_file = self.make_kf(self.xmlfile.hkx_filepath, is_temp=True)
        if not kf_file:
            return('CANCELLED')
        else:
            imp = NifImporter(str(self.kf_filepath), 
                              target_armatures=[self.context.object],
                              import_settings=self.import_flags,
                              animation_name=self.animation_name,)
            imp.context = self.context
            imp.nif = kf_file
            imp.import_nif()
            self.import_annotations()
            bdefs.highlight_objects([imp.armature], self.context)
            log.info('Import of HKX animation completed successfully')
            return('FINISHED')


    def make_kf(self, filepath_working:Path, is_temp=False) -> NifFile:
        """
        Creates a kf file from a hkx file.  
        
        Returns 
        * KF file is opened and returned as a NifFile. 
        """
        self.kf_filepath = Path(tmp_filepath(filepath_working, ext=".kf"))
        if not self.kf_filepath:
            raise RuntimeError(f"Could not create temporary file {self.kf_filepath}")
        
        # Put the source file in the same folder as the kf because HKXCMD wants them together.
        if filepath_working.parent != self.kf_filepath.parent:
            filepath_working = tmp_copy(filepath_working)

        log.debug(f"{hkxcmd_path} EXPORTKF {self.reference_skel_short} {filepath_working} {self.kf_filepath}")
        stat = subprocess.run([hkxcmd_path, 
                               "EXPORTKF", 
                               str(self.reference_skel_short), 
                               str(filepath_working), 
                               str(self.kf_filepath)], 
                               capture_output=True, check=True)
        if stat.stderr:
            s = stat.stderr.decode('utf-8').strip()
            if not s.startswith("Exporting"):
                log.error(s)
                return None
        if not os.path.exists(self.kf_filepath):
            log.error(f"HKXCMD failed to create {self.kf_filepath}")
            return None
        log.info(f"Temporary KF file created: {self.kf_filepath}")

        return NifFile(str(self.kf_filepath))
    

    def import_annotations(self):
        """Import text annotations from the XML file associated with this import."""
        if not self.xml_filepath or not os.path.exists(self.xml_filepath):
            return
        
        xmlfile = xml.parse(self.xml_filepath)
        xmlroot = xmlfile.getroot()
        annotation_tracks = next(x for x in xmlroot.iter('hkparam') if x.attrib['name'] == "annotationTracks")
        annotations = next(a for a in annotation_tracks.iter('hkparam') if a.attrib['name'] == 'annotations')
        for a in annotations.iter('hkobject'):
            t = None
            txt = None
            for p in a.iter('hkparam'):
                if p.attrib['name'] == "time":
                    t = float(p.text)
                if p.attrib['name'] == "text":
                    txt = p.text
            if t and txt:
                self.context.scene.timeline_markers.new(txt, frame=int(t*self.fps))



