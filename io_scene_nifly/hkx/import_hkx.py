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
from .. import __package__ as base_package
from ..pyn.nifdefs import PynIntFlag
from ..pyn.niflytools import tmp_copy_nospace, tmp_copy, tmp_filepath, fo4Dict, skyrimDict
from ..pyn.niflydll import nifly_path, pynifly_dev_path, pynifly_addon_path
from ..pyn.pynifly import NifFile
from .. import blender_defs as bdefs
from .. import bl_info
from ..util.settings import ImportSettings, PYN_RENAME_BONES_PROP, PYN_RENAME_BONES_NIFTOOLS_PROP, PYN_BLENDER_XF_PROP, PYN_ROTATE_BONES_PRETTY_PROP
from ..pyn.xmltools import XMLFile
from ..nif.import_nif import NifImporter
from . import anim_fo4
from . import anim_skyrim

PYN_HKX_BONES_PROP = 'PYN_HKX_BONES'
PYN_HKX_GAME_PROP = 'PYN_HKX_GAME'
PYN_HKX_PTR_SIZE_PROP = 'PYN_HKX_PTR_SIZE'
PYN_HKX_LOCK_TRANSLATION_PROP = 'PYN_HKX_LOCK_TRANSLATION'
PYN_HKX_FLOAT_SLOTS_PROP = 'PYN_HKX_FLOAT_SLOTS'
PYN_HKX_REFERENCE_FLOATS_PROP = 'PYN_HKX_REFERENCE_FLOATS'
PYN_HKX_ADDITIVE_PROP = 'PYN_HKX_ADDITIVE'


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

    create_collection: bpy.props.BoolProperty(
        name="Import to collection",
        description="Import each HKX skeleton into its own new collection.",
        default=False) # type: ignore

    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False
        # hkxcmd is only needed for Skyrim HKX; FO4 is parsed natively
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
        pyniflyPrefs = bpy.context.preferences.addons[base_package].preferences
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


    def _target_collection(self, context):
        """Return the collection new objects should be linked to.

        With create_collection=True, makes a new collection named after the
        HKX file and sets it as the active layer collection so subsequent
        operations land there too."""
        if self.create_collection:
            coll = bpy.data.collections.new(self.hkx_filepath.stem)
            context.scene.collection.children.link(coll)
            new_lc = context.view_layer.layer_collection.children[coll.name]
            new_lc.exclude = False
            context.view_layer.active_layer_collection = new_lc
            return coll
        return context.view_layer.active_layer_collection.collection


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

            # ── FO4 native path (hk_2014) ──
            if anim_fo4.is_fo4_hkx(self.filepath):
                stat = self.import_fo4(context)
                res.add(stat)

            # ── Skyrim native path (hk_2010) ──
            elif anim_skyrim.is_skyrim_hkx(self.filepath):
                stat = self.import_skyrim(context)
                res.add(stat)

            # ── Legacy hkxcmd path (XML skeletons, etc.) ──
            else:
                if not hkxcmd_path:
                    log.error("hkxcmd.exe not found — required for this HKX file type.")
                    return {'CANCELLED'}
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


    def import_fo4(self, context):
        """Import a FO4 (hk_2014) HKX file — either a skeleton or an animation."""
        # Try skeleton first
        skel = anim_fo4.load_fo4_skeleton(self.filepath)
        if skel and skel.bones:
            return self._import_fo4_skeleton(context, skel)

        # Otherwise treat as animation
        return self._import_fo4_animation(context)


    def _import_fo4_skeleton(self, context, skel):
        """Create a Blender armature from an HKX skeleton."""
        from mathutils import Matrix, Quaternion, Vector

        # HKX animation import computes deltas as rest_q_inv @ q_anim where q_anim
        # is a raw bone-local quaternion (no game rotation).  The rest transform must
        # be in the same space, so build bones WITHOUT pretty rotation.
        bdefs.game_rotations = bdefs.game_rotations_none

        arm_name = bdefs.arma_name(skel.name or self.hkx_filepath.stem)
        arm_data = bpy.data.armatures.new(arm_name)
        arma = bpy.data.objects.new(arm_name, arm_data)

        coll = self._target_collection(context)
        coll.objects.link(arma)
        context.view_layer.objects.active = arma
        arma.select_set(True)

        # Store import settings on the armature (match NIF importer properties)
        arma[PYN_RENAME_BONES_PROP] = self.rename_bones
        arma[PYN_RENAME_BONES_NIFTOOLS_PROP] = self.rename_bones_niftools
        arma[PYN_ROTATE_BONES_PRETTY_PROP] = False
        arma[PYN_BLENDER_XF_PROP] = self.blender_xf

        # Store the HKX bone name list (NIF names) for animation import
        arma[PYN_HKX_BONES_PROP] = ";".join(skel.bones)
        arma[PYN_HKX_GAME_PROP] = 'FO4'

        # Compute global transforms from local reference poses
        global_xfs = []  # one 4x4 Matrix per bone
        for i, pose in enumerate(skel.reference_pose):
            # Local transform: translation + rotation (xyzw) + scale
            q = Quaternion((pose.rotation[3], pose.rotation[0],
                            pose.rotation[1], pose.rotation[2]))
            t = Vector(pose.translation)
            s = Vector(pose.scale)

            local_mx = Matrix.Translation(t) @ q.to_matrix().to_4x4()
            # Apply scale
            for axis in range(3):
                local_mx[axis][0] *= s[axis]
                local_mx[axis][1] *= s[axis]
                local_mx[axis][2] *= s[axis]

            parent_idx = skel.parents[i] if i < len(skel.parents) else -1
            if parent_idx >= 0 and parent_idx < len(global_xfs):
                global_mx = global_xfs[parent_idx] @ local_mx
            else:
                global_mx = local_mx
            global_xfs.append(global_mx)

        # Set up bone name conversion
        if self.rename_bones or self.rename_bones_niftools:
            fo4Dict.use_niftools = self.rename_bones_niftools

        # Create bones in edit mode
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            for i, name in enumerate(skel.bones):
                if not name:
                    continue
                if self.rename_bones or self.rename_bones_niftools:
                    bl_name = fo4Dict.blender_name(name)
                else:
                    bl_name = name

                if i < len(global_xfs):
                    bdefs.create_bone(arm_data, bl_name, global_xfs[i], 'FO4', 1.0, 0)

            # Set up parenting
            for i, name in enumerate(skel.bones):
                if not name:
                    continue
                if self.rename_bones or self.rename_bones_niftools:
                    bl_name = fo4Dict.blender_name(name)
                else:
                    bl_name = name

                parent_idx = skel.parents[i] if i < len(skel.parents) else -1
                if parent_idx >= 0 and parent_idx < len(skel.bones):
                    parent_nif = skel.bones[parent_idx]
                    if self.rename_bones or self.rename_bones_niftools:
                        parent_bl = fo4Dict.blender_name(parent_nif)
                    else:
                        parent_bl = parent_nif

                    bone = arm_data.edit_bones.get(bl_name)
                    parent_bone = arm_data.edit_bones.get(parent_bl)
                    if bone and parent_bone:
                        bone.parent = parent_bone
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

        # Stash lockTranslation per bone
        if skel.lock_translation and len(skel.lock_translation) == len(skel.bones):
            for i, name in enumerate(skel.bones):
                if not name:
                    continue
                if self.rename_bones or self.rename_bones_niftools:
                    bl_name = fo4Dict.blender_name(name)
                else:
                    bl_name = name
                bone = arm_data.bones.get(bl_name)
                if bone is not None:
                    bone[PYN_HKX_LOCK_TRANSLATION_PROP] = bool(skel.lock_translation[i])

        # Stash float slots / reference floats on the armature object
        if skel.float_slots:
            arma[PYN_HKX_FLOAT_SLOTS_PROP] = ";".join(skel.float_slots)
        if skel.reference_floats:
            arma[PYN_HKX_REFERENCE_FLOATS_PROP] = list(skel.reference_floats)

        bdefs.highlight_objects([arma], context)
        log.info(f"Imported FO4 HKX skeleton: {arm_name} ({len(skel.bones)} bones)")
        return 'FINISHED'


    def _import_fo4_animation(self, context):
        """Import a FO4 HKX animation onto the selected armature."""
        anim_data = anim_fo4.load_fo4_animation(self.filepath)

        armature = context.object
        if not armature or armature.type != 'ARMATURE':
            log.error("Must select an armature to import FO4 animation.")
            return 'CANCELLED'

        # ── Resolve bone names for each track ──
        bone_names = self._resolve_fo4_bone_names(anim_data, armature)
        if not bone_names:
            log.error("Cannot determine bone names for animation tracks. "
                      "Import the skeleton HKX first to create the armature.")
            return 'CANCELLED'

        # ── Create Blender action ──
        anim_name = self.hkx_filepath.stem
        apply_fo4_animation(armature, anim_data, bone_names, anim_name,
                            self.fps, self.rename_bones, self.rename_bones_niftools)

        # ── Extend scene frame range to cover animation ──
        context.scene.frame_start = min(context.scene.frame_start, 1)
        context.scene.frame_end = max(context.scene.frame_end, anim_data.num_frames)
        context.scene.frame_set(1)

        # ── Import annotation events as timeline markers ──
        for ann in anim_data.annotations:
            if ann.text:
                context.scene.timeline_markers.new(
                    ann.text, frame=int(ann.time * self.fps) + 1)

        bdefs.highlight_objects([armature], context)
        log.info(f"Import of FO4 HKX animation completed: {anim_name}")
        return 'FINISHED'


    def _resolve_fo4_bone_names(self, anim_data, armature):
        """Build a list of bone names (NIF names), one per animation track.

        Priority:
        1. Stored HKX bone list on armature + binding indices
        2. Reference skeleton HKX file (if provided) + binding indices
        3. Annotation track names (if non-empty)
        """
        indices = anim_data.track_to_bone_indices

        # 1. Stored bone list from skeleton import
        hkx_bones_str = armature.get(PYN_HKX_BONES_PROP)
        if hkx_bones_str:
            skel_bones = hkx_bones_str.split(";")
            if indices:
                names = [skel_bones[idx] if 0 <= idx < len(skel_bones) else ''
                         for idx in indices]
                log.info(f"FO4 bone mapping: armature HKX bones + binding ({len(names)} tracks)")
                return names
            elif len(skel_bones) >= anim_data.num_tracks:
                log.info(f"FO4 bone mapping: armature HKX bones direct ({anim_data.num_tracks} tracks)")
                return skel_bones[:anim_data.num_tracks]

        # 2. Reference skeleton file (legacy path)
        if self.reference_skel:
            skel_path = self.reference_skel.strip('"')
            skel = anim_fo4.load_fo4_skeleton(skel_path)
            if skel and skel.bones:
                if indices:
                    names = [skel.bones[idx] if 0 <= idx < len(skel.bones) else ''
                             for idx in indices]
                    log.info(f"FO4 bone mapping: skeleton HKX file + binding ({len(names)} tracks)")
                    return names
                elif len(skel.bones) >= anim_data.num_tracks:
                    log.info(f"FO4 bone mapping: skeleton HKX file direct ({anim_data.num_tracks} tracks)")
                    return skel.bones[:anim_data.num_tracks]
            else:
                log.warning(f"Reference skeleton has no hkaSkeleton: {skel_path}")

        # 3. Annotation track names
        if anim_data.bone_names and any(n for n in anim_data.bone_names):
            log.info(f"FO4 bone mapping: annotation track names")
            return anim_data.bone_names

        return None


    def import_skyrim(self, context):
        """Import a Skyrim (hk_2010) HKX file — either a skeleton or an animation."""
        skel = anim_skyrim.load_skyrim_skeleton(self.filepath)
        if skel and skel.bones:
            return self._import_skyrim_skeleton(context, skel)

        return self._import_skyrim_animation(context)


    def _import_skyrim_skeleton(self, context, skel):
        """Create a Blender armature from a Skyrim HKX skeleton."""
        from mathutils import Matrix, Quaternion, Vector

        # HKX animation import computes deltas as rest_q_inv @ q_anim where q_anim
        # is a raw bone-local quaternion (no game rotation).  The rest transform must
        # be in the same space, so build bones WITHOUT pretty rotation.
        bdefs.game_rotations = bdefs.game_rotations_none

        arm_name = bdefs.arma_name(skel.name or self.hkx_filepath.stem)
        arm_data = bpy.data.armatures.new(arm_name)
        arma = bpy.data.objects.new(arm_name, arm_data)

        coll = self._target_collection(context)
        coll.objects.link(arma)
        context.view_layer.objects.active = arma
        arma.select_set(True)

        arma[PYN_RENAME_BONES_PROP] = self.rename_bones
        arma[PYN_RENAME_BONES_NIFTOOLS_PROP] = self.rename_bones_niftools
        arma[PYN_ROTATE_BONES_PRETTY_PROP] = False
        arma[PYN_BLENDER_XF_PROP] = self.blender_xf
        arma[PYN_HKX_BONES_PROP] = ";".join(skel.bones)
        arma[PYN_HKX_GAME_PROP] = 'SKYRIM'

        # Store ptr_size from the skeleton file (4=LE, 8=SE)
        with open(str(self.hkx_filepath), 'rb') as f:
            hdr = f.read(0x11)
        if len(hdr) >= 0x11 and hdr[:4] == b'\x57\xE0\xE0\x57':
            arma[PYN_HKX_PTR_SIZE_PROP] = hdr[0x10]
        else:
            arma[PYN_HKX_PTR_SIZE_PROP] = 4  # default LE

        # Stash float slots (weapon visibility, etc.) on the armature object
        if skel.float_slots:
            arma[PYN_HKX_FLOAT_SLOTS_PROP] = ";".join(skel.float_slots)
        if skel.reference_floats:
            arma[PYN_HKX_REFERENCE_FLOATS_PROP] = list(skel.reference_floats)

        # Compute global transforms from local reference poses
        global_xfs = []
        for i, pose in enumerate(skel.reference_pose):
            q = Quaternion((pose.rotation[3], pose.rotation[0],
                            pose.rotation[1], pose.rotation[2]))
            t = Vector(pose.translation)
            s = Vector(pose.scale)

            local_mx = Matrix.Translation(t) @ q.to_matrix().to_4x4()
            for axis in range(3):
                local_mx[axis][0] *= s[axis]
                local_mx[axis][1] *= s[axis]
                local_mx[axis][2] *= s[axis]

            parent_idx = skel.parents[i] if i < len(skel.parents) else -1
            if parent_idx >= 0 and parent_idx < len(global_xfs):
                global_mx = global_xfs[parent_idx] @ local_mx
            else:
                global_mx = local_mx
            global_xfs.append(global_mx)

        if self.rename_bones or self.rename_bones_niftools:
            skyrimDict.use_niftools = self.rename_bones_niftools

        bpy.ops.object.mode_set(mode='EDIT')
        try:
            for i, name in enumerate(skel.bones):
                if not name:
                    continue
                if self.rename_bones or self.rename_bones_niftools:
                    bl_name = skyrimDict.blender_name(name)
                else:
                    bl_name = name

                if i < len(global_xfs):
                    bdefs.create_bone(arm_data, bl_name, global_xfs[i], 'SKYRIM', 1.0, 0)

            for i, name in enumerate(skel.bones):
                if not name:
                    continue
                if self.rename_bones or self.rename_bones_niftools:
                    bl_name = skyrimDict.blender_name(name)
                else:
                    bl_name = name

                parent_idx = skel.parents[i] if i < len(skel.parents) else -1
                if parent_idx >= 0 and parent_idx < len(skel.bones):
                    parent_nif = skel.bones[parent_idx]
                    if self.rename_bones or self.rename_bones_niftools:
                        parent_bl = skyrimDict.blender_name(parent_nif)
                    else:
                        parent_bl = parent_nif

                    bone = arm_data.edit_bones.get(bl_name)
                    parent_bone = arm_data.edit_bones.get(parent_bl)
                    if bone and parent_bone:
                        bone.parent = parent_bone
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

        # Stash lockTranslation per bone (object mode required for arm_data.bones access)
        if skel.lock_translation and len(skel.lock_translation) == len(skel.bones):
            for i, name in enumerate(skel.bones):
                if not name:
                    continue
                if self.rename_bones or self.rename_bones_niftools:
                    bl_name = skyrimDict.blender_name(name)
                else:
                    bl_name = name
                bone = arm_data.bones.get(bl_name)
                if bone is not None:
                    bone[PYN_HKX_LOCK_TRANSLATION_PROP] = bool(skel.lock_translation[i])

        bdefs.highlight_objects([arma], context)
        log.info(f"Imported Skyrim HKX skeleton: {arm_name} ({len(skel.bones)} bones)")
        return 'FINISHED'


    def _import_skyrim_animation(self, context):
        """Import a Skyrim HKX animation onto the selected armature."""
        anim_data = anim_skyrim.load_skyrim_animation(self.filepath)

        armature = context.object
        if not armature or armature.type != 'ARMATURE':
            log.error("Must select an armature to import Skyrim animation.")
            return 'CANCELLED'

        bone_names = self._resolve_skyrim_bone_names(anim_data, armature)
        if not bone_names:
            log.error("Cannot determine bone names for animation tracks. "
                      "Import the skeleton HKX first to create the armature.")
            return 'CANCELLED'

        anim_name = self.hkx_filepath.stem
        apply_fo4_animation(armature, anim_data, bone_names, anim_name,
                            self.fps, self.rename_bones, self.rename_bones_niftools,
                            bone_dict=skyrimDict)

        if anim_data.blend_hint == 1:
            armature[PYN_HKX_ADDITIVE_PROP] = True

        context.scene.frame_start = min(context.scene.frame_start, 1)
        context.scene.frame_end = max(context.scene.frame_end, anim_data.num_frames)
        context.scene.frame_set(1)

        for ann in anim_data.annotations:
            if ann.text:
                context.scene.timeline_markers.new(
                    ann.text, frame=int(ann.time * self.fps) + 1)

        bdefs.highlight_objects([armature], context)
        log.info(f"Import of Skyrim HKX animation completed: {anim_name}")
        return 'FINISHED'


    def _resolve_skyrim_bone_names(self, anim_data, armature):
        """Build bone name list for Skyrim animation tracks.

        Priority:
        1. Binding indices + stored/reference skeleton bone list
        2. Direct 1:1 mapping (only when track count == skeleton bone count)
        3. Annotation track names (for partial-skeleton animations like SOS)
        """
        indices = anim_data.track_to_bone_indices if anim_data.track_to_bone_indices else None

        # Gather skeleton bone list from armature or reference file
        skel_bones = None
        hkx_bones_str = armature.get(PYN_HKX_BONES_PROP)
        if hkx_bones_str:
            skel_bones = hkx_bones_str.split(";")
        elif self.reference_skel:
            skel_path = self.reference_skel.strip('"')
            skel = anim_skyrim.load_skyrim_skeleton(skel_path)
            if skel and skel.bones:
                skel_bones = skel.bones

        if skel_bones:
            # 1. Binding indices → remap
            if indices:
                names = [skel_bones[idx] if 0 <= idx < len(skel_bones) else ''
                         for idx in indices]
                log.info(f"Skyrim bone mapping: skeleton + binding ({len(names)} tracks)")
                return names
            # 2. Direct 1:1 mapping (exact match only)
            if len(skel_bones) == anim_data.num_tracks:
                log.info(f"Skyrim bone mapping: direct 1:1 ({anim_data.num_tracks} tracks)")
                return skel_bones[:anim_data.num_tracks]

        # 3. Annotation track names (partial-skeleton animations)
        if anim_data.bone_names and any(n for n in anim_data.bone_names):
            log.info(f"Skyrim bone mapping: annotation track names ({len(anim_data.bone_names)} tracks)")
            return anim_data.bone_names

        # 4. Last resort: direct mapping even if counts differ
        if skel_bones and len(skel_bones) >= anim_data.num_tracks:
            log.info(f"Skyrim bone mapping: direct (first {anim_data.num_tracks} of {len(skel_bones)} bones)")
            return skel_bones[:anim_data.num_tracks]

        return None


def _bone_rest_local(bone):
    """Return the bone's rest-pose local rotation and translation (relative to parent).

    Returns (Quaternion, Vector) in armature space.
    """
    from mathutils import Matrix, Vector, Quaternion
    if bone.parent:
        local_mx = bone.parent.matrix_local.inverted() @ bone.matrix_local
    else:
        local_mx = bone.matrix_local.copy()
    return local_mx.to_quaternion(), local_mx.to_translation()


def apply_fo4_animation(armature, anim_data, bone_names, anim_name, fps,
                        rename_bones=False, rename_bones_niftools=False,
                        bone_dict=None):
    """Apply decompressed FO4/Skyrim animation data to a Blender armature.

    For NORMAL animations (blend_hint=0), HKX values are absolute bone-local
    transforms.  Blender pose values are deltas from rest:
        q_pose = q_rest_inv @ q_anim
        t_pose = q_rest_inv @ (t_anim - t_rest)

    For ADDITIVE animations (blend_hint=1), HKX values are already deltas
    from rest pose.  They are applied directly as pose bone transforms.
    """
    import bpy
    from mathutils import Quaternion, Vector

    if bone_dict is None:
        bone_dict = fo4Dict

    additive = getattr(anim_data, 'blend_hint', 0) == 1
    if additive:
        log.info("Animation is ADDITIVE (blend_hint=1)")

    # Clear residual pose transforms only for bones that will be animated,
    # so partial animations (e.g. auxbones) don't reset unrelated bones.
    animated_names = set()
    if rename_bones or rename_bones_niftools:
        bone_dict.use_niftools = rename_bones_niftools
    _pb_lookup = {pb.name.lower(): pb for pb in armature.pose.bones}
    for i, nif_name in enumerate(bone_names):
        if not nif_name:
            continue
        if nif_name in armature.pose.bones:
            animated_names.add(nif_name)
        elif rename_bones or rename_bones_niftools:
            renamed = bone_dict.blender_name(nif_name)
            if renamed in armature.pose.bones:
                animated_names.add(renamed)
        else:
            match = _pb_lookup.get(nif_name.lower())
            if match:
                animated_names.add(match.name)
    for pb in armature.pose.bones:
        if pb.name in animated_names:
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)

    # Create action
    action = bpy.data.actions.new(anim_name)
    frame_end = anim_data.num_frames
    action.frame_start = 1
    action.frame_end = frame_end
    action.use_frame_range = True
    action.use_fake_user = True
    action.asset_mark()

    # Assign action to armature
    if not armature.animation_data:
        armature.animation_data_create()
    armature.animation_data.action = action

    # Set up bone name conversion to match how the armature was imported
    if rename_bones or rename_bones_niftools:
        bone_dict.use_niftools = rename_bones_niftools

    # Build a lookup from lowercase bone name to actual pose bone name
    pose_bones = armature.pose.bones
    _pb_lower = {pb.name.lower(): pb.name for pb in pose_bones}

    for i, track in enumerate(anim_data.tracks):
        if i >= len(bone_names):
            break
        nif_name = bone_names[i]
        if not nif_name:
            continue

        # Find the bone in the armature.
        # Try: exact NIF name, renamed name, case-insensitive match.
        bl_name = None
        if nif_name in pose_bones:
            bl_name = nif_name
        elif rename_bones or rename_bones_niftools:
            renamed = bone_dict.blender_name(nif_name)
            if renamed in pose_bones:
                bl_name = renamed
        if bl_name is None:
            bl_name = _pb_lower.get(nif_name.lower())
        if bl_name is None:
            log.debug(f"Bone '{nif_name}' not found in armature, skipping track {i}")
            continue

        pb = pose_bones[bl_name]
        bone = pb.bone
        pb.rotation_mode = 'QUATERNION'
        path_prefix = f'pose.bones["{bl_name}"].'

        # Get the bone's rest-pose local transform for delta computation
        rest_q, rest_t = _bone_rest_local(bone)
        rest_q_inv = rest_q.inverted()

        # ── Rotation fcurves ──
        if track.rotations:
            rot_curves = [
                action.fcurve_ensure_for_datablock(armature, path_prefix + "rotation_quaternion", index=j)
                for j in range(4)
            ]
            for f, quat in enumerate(track.rotations):
                frame = f + 1  # Blender frames are 1-based
                # HKX quat is [x, y, z, w]; convert to Blender Quaternion (w, x, y, z)
                q_anim = Quaternion((quat[3], quat[0], quat[1], quat[2]))
                if additive:
                    q_delta = q_anim
                else:
                    # Delta from rest pose
                    q_delta = rest_q_inv @ q_anim
                for j in range(4):
                    kfp = rot_curves[j].keyframe_points.insert(frame, q_delta[j])
                    kfp.interpolation = 'LINEAR'

        # ── Location fcurves ──
        if track.translations:
            loc_curves = [
                action.fcurve_ensure_for_datablock(armature, path_prefix + "location", index=j)
                for j in range(3)
            ]
            for f, loc in enumerate(track.translations):
                frame = f + 1
                v_anim = Vector(loc)
                if additive:
                    v_delta = v_anim
                else:
                    # Delta from rest pose, rotated into bone-local space
                    v_delta = rest_q_inv @ (v_anim - rest_t)
                for j in range(3):
                    kfp = loc_curves[j].keyframe_points.insert(frame, v_delta[j])
                    kfp.interpolation = 'LINEAR'

        # ── Scale fcurves ──
        if track.scales:
            # Only add scale curves if any frame is non-uniform
            has_scale = any(
                any(abs(s[j] - 1.0) > 1e-5 for j in range(3))
                for s in track.scales
            )
            if has_scale:
                scale_curves = [
                    action.fcurve_ensure_for_datablock(armature, path_prefix + "scale", index=j)
                    for j in range(3)
                ]
                for f, scl in enumerate(track.scales):
                    frame = f + 1
                    for j in range(3):
                        kfp = scale_curves[j].keyframe_points.insert(frame, scl[j])
                        kfp.interpolation = 'LINEAR'

    log.info(f"Created action '{action.name}' with {frame_end} frames")


def extract_fo4_animation(armature, fps=None):
    """Extract animation data from a Blender armature into an AnimationData.

    Evaluates pose bone transforms at each frame, capturing NLA blending,
    constraints, and drivers.  Only selected bones get per-frame animation;
    unselected bones are exported as static (frame-1 value).  If no bones
    are selected, all bones are animated.

    Returns an AnimationData ready for write_fo4_animation(), or None if no action.
    """
    import bpy
    from mathutils import Quaternion, Vector

    if not armature.animation_data or not armature.animation_data.action:
        log.error("Armature has no animation action.")
        return None

    action = armature.animation_data.action

    # Determine frame range (in Blender frames)
    frame_start = int(action.frame_start) if action.use_frame_range else int(action.frame_range[0])
    frame_end = int(action.frame_end) if action.use_frame_range else int(action.frame_range[1])
    blender_frame_count = frame_end - frame_start + 1
    if blender_frame_count < 1:
        log.error("Action has no frames.")
        return None

    if fps is None:
        fps = bpy.context.scene.render.fps

    # Resample if export FPS differs from Blender scene FPS
    blender_fps = bpy.context.scene.render.fps
    duration = (blender_frame_count - 1) / blender_fps
    num_frames = round(duration * fps) + 1 if duration > 0 else 1

    # Select the correct bone dictionary based on game
    game = armature.get(PYN_HKX_GAME_PROP, 'FO4')
    bone_dict = skyrimDict if game == 'SKYRIM' else fo4Dict
    additive = armature.get(PYN_HKX_ADDITIVE_PROP, False)

    # Resolve bone list — use stored HKX bone names if available
    hkx_bones_str = armature.get(PYN_HKX_BONES_PROP)
    rename_bones = armature.get(PYN_RENAME_BONES_PROP, False)
    rename_bones_niftools = armature.get(PYN_RENAME_BONES_NIFTOOLS_PROP, False)

    if rename_bones or rename_bones_niftools:
        bone_dict.use_niftools = rename_bones_niftools

    if hkx_bones_str:
        nif_bone_names = hkx_bones_str.split(";")
    else:
        nif_bone_names = []
        for pb in armature.pose.bones:
            nif_bone_names.append(bone_dict.nif_name(pb.name)
                                  if (rename_bones or rename_bones_niftools)
                                  else pb.name)

    # Build a map from NIF bone name → Blender pose bone
    pose_bones = armature.pose.bones
    _pb_lower = {pb.name.lower(): pb.name for pb in pose_bones}

    def _find_pose_bone(nif_name):
        if nif_name in pose_bones:
            return pose_bones[nif_name]
        if rename_bones or rename_bones_niftools:
            renamed = bone_dict.blender_name(nif_name)
            if renamed in pose_bones:
                return pose_bones[renamed]
        bl = _pb_lower.get(nif_name.lower())
        if bl:
            return pose_bones[bl]
        return None

    # Resolve pose bones for each track
    track_pbs = []
    for nif_name in nif_bone_names:
        track_pbs.append(_find_pose_bone(nif_name))

    # Only selected bones get per-frame animation; if none selected, animate all
    try:
        sel_pbs = bpy.context.selected_pose_bones
        selected_bones = {pb.name for pb in sel_pbs} if sel_pbs else set()
    except AttributeError:
        selected_bones = {pb.name for pb in pose_bones if pb.bone.select}
    animate_all = not selected_bones

    # Rest poses needed for additive animations
    rest_data = {}
    if additive:
        for pb in track_pbs:
            if pb and pb.name not in rest_data:
                rest_data[pb.name] = _bone_rest_local(pb.bone)

    # Initialize tracks
    tracks = [anim_fo4.TrackData() for _ in nif_bone_names]

    scene = bpy.context.scene
    original_frame = scene.frame_current
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # Map original pose bone names to indices for lookup on evaluated object
    track_pb_names = [pb.name if pb else None for pb in track_pbs]

    def _read_bone_local(eval_pb):
        """Read bone-local transform from the evaluated pose."""
        if eval_pb.parent:
            local_mx = eval_pb.parent.matrix.inverted() @ eval_pb.matrix
        else:
            local_mx = eval_pb.matrix.copy()

        q = local_mx.to_quaternion()
        v = local_mx.to_translation()
        s = local_mx.to_scale()

        if additive:
            rest_q, rest_t = rest_data[eval_pb.name]
            rest_q_inv = rest_q.inverted()
            q = rest_q_inv @ q
            v = rest_q_inv @ (v - rest_t)

        return [q.x, q.y, q.z, q.w], [v.x, v.y, v.z], [s.x, s.y, s.z]

    for f in range(num_frames):
        # Convert export frame to Blender frame (fractional) for resampling
        time = f / fps if fps > 0 else 0.0
        bl_frame = frame_start + time * blender_fps
        int_frame = int(bl_frame)
        subframe = bl_frame - int_frame
        scene.frame_set(int_frame, subframe=subframe)
        depsgraph.update()
        eval_armature = armature.evaluated_get(depsgraph)
        eval_pose_bones = eval_armature.pose.bones

        for track_idx, pb_name in enumerate(track_pb_names):
            td = tracks[track_idx]

            if pb_name is None:
                td.rotations.append([0.0, 0.0, 0.0, 1.0])
                td.translations.append([0.0, 0.0, 0.0])
                td.scales.append([1.0, 1.0, 1.0])
                continue

            # Unselected bones: repeat frame-0 value
            if not animate_all and pb_name not in selected_bones and f > 0:
                td.rotations.append(td.rotations[0])
                td.translations.append(td.translations[0])
                td.scales.append(td.scales[0])
                continue

            eval_pb = eval_pose_bones[pb_name]
            rot, loc, scl = _read_bone_local(eval_pb)
            td.rotations.append(rot)
            td.translations.append(loc)
            td.scales.append(scl)

    scene.frame_set(original_frame)

    # Build AnimationData
    binding_indices = list(range(len(nif_bone_names)))
    # duration was computed from the Blender frame range above
    anim_out = anim_fo4.AnimationData(
        duration=duration,
        num_frames=num_frames,
        num_tracks=len(tracks),
        frame_duration=1.0 / fps,
        tracks=tracks,
        bone_names=list(nif_bone_names),
        track_to_bone_indices=binding_indices,
        original_skeleton_name="Root",
        blend_hint=1 if additive else 0,
    )
    return anim_out
