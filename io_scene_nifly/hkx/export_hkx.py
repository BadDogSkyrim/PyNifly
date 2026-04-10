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
from ..pyn.pynifly import NifFile
from ..pyn.niflydll import nifly_path, pynifly_dev_path, pynifly_addon_path
from ..blender_defs import LogHandler
from .. import bl_info
from . import skeleton_hkx
from ..pyn.xmltools import XMLFile
from ..kf.export_kf import KFExporter
from . import anim_fo4
from . import anim_skyrim
from .import_hkx import PYN_HKX_BONES_PROP, PYN_HKX_GAME_PROP, PYN_HKX_PTR_SIZE_PROP, extract_fo4_animation


hkxcmd_path = None

if pynifly_dev_path:
    hkxcmd_path = os.path.join(pynifly_dev_path, "hkxcmd.exe")
else:
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

    game: bpy.props.EnumProperty(
        name="Game",
        description="Target game format for the exported HKX file",
        items=[
            ('FO4', "Fallout 4", "Fallout 4 (hk_2014, 64-bit)"),
            ('SKYRIM_LE', "Skyrim LE", "Skyrim Legendary Edition (hk_2010, 32-bit pointers)"),
            ('SKYRIM_SE', "Skyrim SE", "Skyrim Special Edition (hk_2010, 64-bit pointers)"),
        ],
        default='FO4') # type: ignore

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
        self.fps = bpy.context.scene.render.fps
        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            if 'PYN_SKELETON_FILE'in obj:
                self.reference_skel = obj['PYN_SKELETON_FILE']
            # Default game from armature properties
            arm_game = obj.get(PYN_HKX_GAME_PROP, '')
            if arm_game == 'SKYRIM':
                ptr_size = obj.get(PYN_HKX_PTR_SIZE_PROP, 4)
                self.game = 'SKYRIM_SE' if ptr_size == 8 else 'SKYRIM_LE'
            elif arm_game == 'FO4':
                self.game = 'FO4'


    @classmethod
    def poll(cls, context):
        if (not context.object) or context.object.type != 'ARMATURE':
            return False

        if (not context.object.animation_data) or (not context.object.animation_data.action):
            return False

        # FO4/Skyrim armatures (with PYN_HKX_BONES) don't need hkxcmd
        if context.object.get(PYN_HKX_BONES_PROP):
            return True

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
        
        self.xml_filepath_out = tmp_filepath(Path(self.filepath), ext='.xml')
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

        if not self.poll(context):
            log.error(f"Cannot run exporter--see system console for details")
            return {'CANCELLED'}

        self.context = context
        self.log_handler = LogHandler.New(bl_info, "EXPORT", "HKX")
        NifFile.clear_log()

        # ── FO4 / Skyrim native path ──
        if context.object.get(PYN_HKX_BONES_PROP):
            game = self.game
            try:
                anim_data = extract_fo4_animation(context.object, fps=self.fps)
                if anim_data is None:
                    log.error("Failed to extract animation data from armature.")
                    res.add('CANCELLED')
                elif game in ('SKYRIM_LE', 'SKYRIM_SE'):
                    ptr_size = 8 if game == 'SKYRIM_SE' else 4
                    anim_skyrim.write_skyrim_animation(self.filepath, anim_data, ptr_size=ptr_size)
                    fmt = "SE" if ptr_size == 8 else "LE"
                    log.info(f"Exported Skyrim {fmt} animation: {self.filepath}")
                    res.add('FINISHED')
                else:
                    anim_fo4.write_fo4_animation(self.filepath, anim_data)
                    log.info(f"Exported FO4 animation: {self.filepath}")
                    res.add('FINISHED')
            except:
                log.exception("HKX export failed")
                res.add('CANCELLED')

            self.log_handler.finish("EXPORT", self.filepath)
            wm = context.window_manager
            wm.pynifly_last_export_path_hkx = self.filepath
            return res.intersection({'CANCELLED'}, {'FINISHED'})

        # ── Skyrim path (via hkxcmd) ──
        refskelpath = Path(self.reference_skel.strip('"'))
        self.reference_skel_short = nospace_filepath(refskelpath)
        if refskelpath != self.reference_skel_short:
            copyfile(self.reference_skel, self.reference_skel_short)
        self.filepath_short = nospace_filepath(Path(self.filepath))
        if self.reference_skel:
            context.object['PYN_SKELETON_FILE'] = self.reference_skel

        self.has_markers = (len(context.scene.timeline_markers) > 0)
        self.hkx_tmp_filepath = tmp_filepath(Path(self.filepath), ext=".hkx")
        self.xml_filepath = None
        self.xml_filepath_out = None

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
                    self.xml_filepath = tmp_filepath(Path(self.filepath), ext=".xml")
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
        wm = context.window_manager
        wm.pynifly_last_export_path_hkx = self.filepath

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

class ExportSkelHKX(bpy.types.Operator, ExportHelper):
    """Export Blender armature to an HKX skeleton file (Skyrim LE/SE or FO4)"""

    bl_idname = "export_scene.skeleton_hkx"
    bl_label = 'Export skeleton HKX'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"

    game: bpy.props.EnumProperty(
        name="Game",
        description="Target game format for the exported skeleton HKX file",
        items=[
            ('SKYRIM_LE', "Skyrim LE", "Skyrim Legendary Edition (hk_2010, 32-bit pointers)"),
            ('SKYRIM_SE', "Skyrim SE", "Skyrim Special Edition (hk_2010, 64-bit pointers)"),
            ('FO4', "Fallout 4", "Fallout 4 (hk_2014, 64-bit pointers)"),
        ],
        default='SKYRIM_SE') # type: ignore

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            arm_game = obj.get(PYN_HKX_GAME_PROP, '')
            if arm_game == 'SKYRIM':
                ptr_size = obj.get(PYN_HKX_PTR_SIZE_PROP, 8)
                self.game = 'SKYRIM_SE' if ptr_size == 8 else 'SKYRIM_LE'
            elif arm_game == 'FO4':
                self.game = 'FO4'

    @classmethod
    def poll(cls, context):
        return bool(context.object and context.object.type == 'ARMATURE')

    def invoke(self, context, event):
        if context.window_manager.pynifly_last_export_path_skel_hkx:
            self.filepath = str(Path(context.window_manager.pynifly_last_export_path_skel_hkx)
                                / Path(self.filepath))
        return super().invoke(context, event)

    def execute(self, context):
        self.log_handler = LogHandler.New(bl_info, "EXPORT SKELETON", "HKX")
        try:
            arma = context.object
            skel = skeleton_hkx.extract_skeleton_from_armature(arma)
            if self.game == 'FO4':
                anim_fo4.write_fo4_skeleton(self.filepath, skel)
            else:
                ptr_size = 8 if self.game == 'SKYRIM_SE' else 4
                anim_skyrim.write_skyrim_skeleton(self.filepath, skel, ptr_size=ptr_size)
            log.info(f"Exported {self.game} skeleton: {self.filepath} ({len(skel.bones)} bones)")

            wm = context.window_manager
            wm.pynifly_last_export_path_skel_hkx = self.filepath
            return {'FINISHED'}
        except Exception:
            self.log_handler.log.exception("Skeleton HKX export failed")
            self.report({"ERROR"}, "Skeleton export failed, see system console")
            return {'CANCELLED'}
        finally:
            self.log_handler.finish("EXPORT", self.filepath)

