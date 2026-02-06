"""

HKX ANIMATION EXPORT

"""
from contextlib import suppress
import os
import subprocess
import logging
from pathlib import Path
import xml.etree.ElementTree as xml
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
from ..pyn.nifdefs import PynIntFlag
from ..pyn.niflytools import tmp_filepath, nospace_filepath, copyfile
from ..pyn.pynifly import nifly_path, pynifly_dev_path, pynifly_addon_path, NifFile
from ..blender_defs import LogHandler
from .. import bl_info
from . import skeleton_hkx
from ..pyn.xmltools import XMLFile
from ..kf.export_kf import KFExporter


class ImportSettingsHKX(PynIntFlag):
    create_bones = 1
    rename_bones = 1<<1
    import_anims = 1<<2
    rename_bones_nift = 1<<3
    roll_bones_nift = 1<<4


hkxcmd_path = None

if pynifly_dev_path:
    hkxcmd_path = os.path.join(pynifly_dev_path, "hkxcmd.exe")
else:
    hkxcmd_path = os.path.join(pynifly_dev_path, "hkxcmd.exe")
    hkxcmd_path = os.path.join(pynifly_addon_path, "hkxcmd.exe")

log = logging.getLogger("pynifly")


################################################################################
#                                                                              #
#                             HKX ANIMATION EXPORT                             #
#                                                                              #
################################################################################

class ExportHKX(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.pynifly_hkx"
    bl_label = 'Export HKX (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"

    reference_skel: bpy.props.StringProperty(
        name="Reference skeleton",
        description="HKX reference skeleton to use for animation binding",
        default="") # type: ignore

    fps: bpy.props.FloatProperty(
        name="FPS",
        description="Frames per second for export",
        default=30) # type: ignore

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            if 'PYN_SKELETON_FILE'in obj:
                self.reference_skel = obj['PYN_SKELETON_FILE']


    @classmethod
    def poll(cls, context):
        if (not context.object) or context.object.type != 'ARMATURE':
            # log.error("Must select an armature to export animations.")
            return False

        if (not context.object.animation_data) or (not context.object.animation_data.action):
            # log.error("Active object must have an animation associated with it.")
            return False

        if not hkxcmd_path:
            log.error("hkxcmd.exe not found--animation I/O not available.")
            return False

        return True


    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_export_path_hkx:
            self.filepath = str(Path(context.window_manager.pynifly_last_export_path_hkx) 
                                / Path(self.filepath))
        return super().invoke(context, event)

    def generate_hkx(self, filepath):
        """Generates an HKX file from a KF file. Also generates an XML file."""

        # Generate HKX from KF
        log.debug(f"{hkxcmd_path} CONVERTKF {self.reference_skel_short} {self.kf_filepath} {filepath}")
        stat = subprocess.run([hkxcmd_path, 
                               "CONVERTKF", 
                               self.reference_skel_short, 
                               str(self.kf_filepath), 
                               filepath], 
                               capture_output=True, 
                               check=False)
        if stat.returncode:
            s = stat.stderr.decode('utf-8').strip()
            log.error(f"HKXCMD failed with error: {s}")
            return None
        if not os.path.exists(filepath):
            log.error(f"HKXCMD failed to create {filepath} with error {stat.stderr.decode('utf-8').strip()}")
            return None
        log.info(f"Created temporary HKX file: {filepath}")

        if self.xml_filepath:
            # Generate XML from HKX
            stat = subprocess.run([hkxcmd_path, 
                                "CONVERT", 
                               "-V:XML",
                                filepath, 
                                self.xml_filepath], 
                                capture_output=True, check=True)
            if stat.returncode:
                s = stat.stderr.decode('utf-8').strip()
                log.error(s)
                return None
            if not os.path.exists(self.xml_filepath):
                log.error(f"Failed to create {self.xml_filepath}")
                return None
            
            log.info(f"Created temporary XML file: {self.xml_filepath}")

    def write_annotations(self):
        """Write animation text annotations to the intermediate xml file.
        Returns False if there were no annotations, so the original HKX is fine.
        """
        markers = self.context.scene.timeline_markers
        if len(markers) == 0:
            return False
        
        xmlfile = xml.parse(self.xml_filepath)
        xmlroot = xmlfile.getroot()
        annotation_tracks = next(x for x in xmlroot.iter('hkparam') if x.attrib['name'] == "annotationTracks")
        tracks = [obj for obj in annotation_tracks]
        for t in tracks: 
            annotation_tracks.remove(t)

        # # Writing a single track. Don't know how or why we would have more.
        annotation_tracks.set('numelements', "1")
        trackobj = xml.SubElement(annotation_tracks, 'hkobject')
        annotations = xml.SubElement(
            trackobj, 'hkparam', {'name': 'annotations', 'numelements': str(len(markers))})
        
        for m in markers:
            markobj = xml.SubElement(annotations, 'hkobject')
            timeparam = xml.SubElement(markobj, 'hkparam', {'name': 'time'})
            timeparam.text = f"{(m.frame/self.fps):f}"
            textparam =xml.SubElement(markobj, 'hkparam', {'name': 'text'})
            textparam.text = m.name
        
        self.xml_filepath_out = tmp_filepath(self.filepath, ext='.xml')
        xmlfile.write(self.xml_filepath_out)
        log.info(f"Created final XML file: {self.xml_filepath_out}")
        
        return True
    

    def rename_output(self):
        """If we renamed our output to deal with spaces in names, set it back to what it
        should be."""
        copyfile(self.filepath_short, self.filepath)


    def generate_final_hkx(self):
        stat = subprocess.run([hkxcmd_path, 
                               "CONVERT", 
                               "-V:WIN32",
                               self.xml_filepath, 
                               self.filepath_short], 
                               capture_output=True, check=True)
        if stat.returncode:
            s = stat.stderr.decode('utf-8').strip()
            log.error(s)
            return None
        if not os.path.exists(self.filepath_short):
            log.error(f"Failed to create {self.filepath_short}")
            return None
    
        log.info(f"Created HKX file: {self.filepath_short}")


    def execute(self, context):
        res = set()
        refskelpath = Path(self.reference_skel.strip('"'))
        self.reference_skel_short = nospace_filepath(refskelpath)
        if refskelpath != self.reference_skel_short:
            copyfile(self.reference_skel, self.reference_skel_short)
        self.filepath_short = nospace_filepath(Path(self.filepath))
        if self.reference_skel:
            context.object['PYN_SKELETON_FILE'] = self.reference_skel

        if not self.poll(context):
            log.error(f"Cannot run exporter--see system console for details")
            return {'CANCELLED'} 

        self.context = context
        self.fps = context.scene.render.fps
        self.has_markers = (len(context.scene.timeline_markers) > 0)
        self.hkx_tmp_filepath = tmp_filepath(Path(self.filepath), ext=".hkx")
        self.xml_filepath = None
        self.xml_filepath_out = None
        self.log_handler = LogHandler.New(bl_info, "EXPORT", "HKX")
        NifFile.Load(nifly_path)
        NifFile.clear_log()

        # Export whatever animation is attached to the active object.
        self.kf_filepath = Path(tmp_filepath(Path(self.filepath), ext=".kf"))
        try:
            KFExporter.Export(self.kf_filepath, context, fps=self.fps)
            log.info(f"Created temporary kf file: {self.kf_filepath}")
        except:
            log.exception("Creation of temporary KF file failed")

        if self.log_handler.max_error <= logging.WARNING:
            try:
                if self.has_markers:
                    self.xml_filepath = tmp_filepath(self.filepath, ext=".xml")
                    self.generate_hkx(self.hkx_tmp_filepath)
                    self.write_annotations()
                    self.generate_final_hkx()
                else:
                    self.generate_hkx(self.filepath_short)
                self.rename_output()

                res.add('FINISHED')
            except:
                self.log_handler.log.exception("Export of HKX failed")
                res.add('CANCELLED')

        self.log_handler.finish("EXPORT", self.filepath)

        # Save the directory path for next time
        if 'CANCELLED' not in res:
            wm = context.window_manager
            wm.pynifly_last_export_path_hkx = os.path.dirname(self.filepath)

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

class ExportSkelHKX(skeleton_hkx.ExportSkel):
    """Export Blender armature to a skeleton HKX file"""

    bl_idname = "export_scene.skeleton_hkx"
    bl_label = 'Export skeleton HKX'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"


    @classmethod
    def poll(cls, context):
        if (not context.object) or context.object.type != 'ARMATURE':
            # log.error("Must select an armature to export animations.")
            return False

        if not hkxcmd_path:
            log.error("hkxcmd.exe not found--skeleton export not available.")
            return False

        return True


    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_export_path_skel_hkx:
            self.filepath = str(Path(context.window_manager.pynifly_last_export_path_skel_hkx) 
                                / Path(self.filepath))
        return super().invoke(context, event)

    def execute(self, context):
        self.log_handler = LogHandler.New(bl_info, "EXPORT SKELETON", "HKX")

        try:
            self.context = context
            fp = Path(self.filepath)
            out_filepath = fp
            self.filepath = str(tmp_filepath(fp, ".xml"))
            self.do_export()

            XMLFile.SetPath(hkxcmd_path)
            XMLFile.xml_to_hkx(Path(self.filepath), out_filepath)

            status = {'FINISHED'}
            # Save the directory path for next time
            wm = context.window_manager
            wm.pynifly_last_export_path_skel_hkx = str(out_filepath.parent)
            return status
        except:
            self.log_handler.log.exception("Import of HKX failed")
            status = {'CANCELLED'}
            self.log_handler.finish("IMPORT", str(out_filepath))

        return status

