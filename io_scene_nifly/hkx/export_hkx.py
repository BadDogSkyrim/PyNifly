"""

HKX ANIMATION EXPORT

"""
import logging
from pathlib import Path
import bpy
from bpy_extras.io_utils import ExportHelper
from ..pyn.pynifly import NifFile
from ..blender_defs import LogHandler
from .. import bl_info
from . import skeleton_hkx
from . import anim_fo4
from . import anim_skyrim
from .import_hkx import PYN_HKX_BONES_PROP, PYN_HKX_GAME_PROP, PYN_HKX_PTR_SIZE_PROP, extract_fo4_animation


log = logging.getLogger("pynifly")


def _load_reference_skeleton(filepath):
    """Read an HKX skeleton to export against. Returns (skeleton, game, ptr_size), where
    game is 'SKYRIM' or 'FO4', or None if the file isn't a skeleton we can read."""
    filepath = filepath.strip('"')
    if anim_fo4.is_fo4_hkx(filepath):
        skel = anim_fo4.load_fo4_skeleton(filepath)
        game, ptr_size = 'FO4', 8
    elif anim_skyrim.is_skyrim_hkx(filepath):
        skel = anim_skyrim.load_skyrim_skeleton(filepath)
        game = 'SKYRIM'
        with open(filepath, 'rb') as f:
            hdr = f.read(0x11)
        ptr_size = hdr[0x10] if len(hdr) >= 0x11 and hdr[:4] == b'\x57\xE0\xE0\x57' else 4
    else:
        return None
    if not skel or not skel.bones:
        return None
    return skel, game, ptr_size


################################################################################
#                                                                              #
#                             HKX ANIMATION EXPORT                             #
#                                                                              #
################################################################################

class ExportHKX(bpy.types.Operator, ExportHelper):
    """Export the active armature's animation to an HKX file"""

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
        description="HKX skeleton the animation is for. Needed when the armature wasn't "
                    "imported from an HKX skeleton",
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

        return True


    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_export_path_hkx:
            self.filepath = str(Path(context.window_manager.pynifly_last_export_path_hkx)
                                / Path(self.filepath))
        return super().invoke(context, event)


    def _game_and_skeleton(self, arma):
        """The target game ('FO4', 'SKYRIM_LE' or 'SKYRIM_SE') and the reference skeleton
        to export against--None when the armature carries its own HKX bone list."""
        if arma.get(PYN_HKX_BONES_PROP):
            return self.game, None

        if not self.reference_skel:
            log.error("This armature wasn't imported from an HKX skeleton. Choose the "
                      "HKX skeleton the animation is for as the reference skeleton.")
            return None, None
        ref = _load_reference_skeleton(self.reference_skel)
        if ref is None:
            log.error(f"Cannot read a skeleton from reference skeleton {self.reference_skel}")
            return None, None
        skel, skel_game, ptr_size = ref

        # The skeleton decides the game; for Skyrim the chosen LE/SE wins, so an animation
        # can be written for either from the same skeleton.
        if skel_game == 'FO4':
            game = 'FO4'
        elif self.game in ('SKYRIM_LE', 'SKYRIM_SE'):
            game = self.game
        else:
            game = 'SKYRIM_SE' if ptr_size == 8 else 'SKYRIM_LE'
        arma['PYN_SKELETON_FILE'] = self.reference_skel
        return game, skel


    def execute(self, context):
        res = set()

        if not self.poll(context):
            log.error("Cannot run exporter--see system console for details")
            return {'CANCELLED'}

        self.context = context
        self.log_handler = LogHandler.New(bl_info, "EXPORT", "HKX")
        NifFile.clear_log()

        try:
            game, skel = self._game_and_skeleton(context.object)
            anim_data = None
            if game:
                anim_data = extract_fo4_animation(
                    context.object, fps=self.fps, skeleton=skel,
                    game=('FO4' if game == 'FO4' else 'SKYRIM'))
                if anim_data is None:
                    log.error("Failed to extract animation data from armature.")
            if anim_data is None:
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
        return {'CANCELLED'} if 'CANCELLED' in res else {'FINISHED'}


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

