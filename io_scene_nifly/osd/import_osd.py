"""Import BodySlide OSD files as shape keys on selected objects."""

import re
import logging
from pathlib import Path
import bpy
from bpy_extras.io_utils import ImportHelper
from .. import blender_defs as BD
from .. import bl_info
from .osdfile import OSDFile, is_osd

log = logging.getLogger("pynifly")

# Pattern to strip Blender's ".001" suffix for name matching
_BLENDER_SUFFIX = re.compile(r'\.\d{3}$')


def _base_name(name):
    """Strip Blender's .001/.002/etc suffix from a name."""
    return _BLENDER_SUFFIX.sub('', name)


def create_osd_shape_keys(obj, morphs):
    """Add OSD morph data as shape keys on obj.

    morphs: {slider_name: [[vert_index, (dx, dy, dz)], ...], ...}
    """
    mesh = obj.data
    verts = mesh.vertices

    if mesh.shape_keys is None or "Basis" not in mesh.shape_keys.key_blocks:
        newsk = obj.shape_key_add()
        newsk.name = "Basis"

    for morph_name, morph_verts in sorted(morphs.items()):
        newsk = obj.shape_key_add()
        newsk.name = ">" + morph_name
        newsk.value = 0

        obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
        mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
        for vert_index, offsets in morph_verts:
            if vert_index < len(mesh_key_verts):
                for i in range(3):
                    mesh_key_verts[vert_index].co[i] = verts[vert_index].co[i] + offsets[i]

        mesh.update()

    obj.active_shape_key_index = 0


def import_osd(osd, target_objs):
    """Import an OSD file onto selected objects.

    OSD compound entry names are split using selected object names as shape
    name keys. Blender's .001 suffixes are stripped for matching.
    """
    # Build candidate shape names from selected objects (base names)
    candidate_names = []
    obj_by_name = {}
    for o in target_objs:
        base = _base_name(o.name)
        candidate_names.append(o.name)
        obj_by_name[o.name] = o
        if base != o.name:
            candidate_names.append(base)
            obj_by_name[base] = o

    # Split OSD entries using the candidate names
    osd.split_entries(candidate_names)

    for shapename, morphs in osd.shapes.items():
        obj = obj_by_name.get(shapename)
        if obj is None:
            log.warning(f"OSD shape '{shapename}' does not match any selected object")
        else:
            log.info(f"Applying {len(morphs)} sliders to '{obj.name}'")
            create_osd_shape_keys(obj, morphs)


class ImportOSD(bpy.types.Operator, ImportHelper):
    """Load a BodySlide OSD File"""
    bl_idname = "import_scene.pynifly_osd"
    bl_label = "Import OSD (PyNifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".osd"
    filter_glob: bpy.props.StringProperty(
        default="*.osd",
        options={'HIDDEN'},
    )

    def invoke(self, context, event):
        if context.window_manager.pynifly_last_import_path_osd:
            self.filepath = str(Path(context.window_manager.pynifly_last_import_path_osd)
                                / Path(self.filepath))
        return super().invoke(context, event)

    def execute(self, context):
        self.log_handler = BD.LogHandler()
        self.log_handler.start(bl_info, "IMPORT", "OSD")
        self.status = {'FINISHED'}
        self.file_path = Path(self.filepath)

        try:
            osd = OSDFile.from_file(self.file_path)
            if not osd.is_valid:
                log.error(f"Not a valid OSD file: {self.filepath}")
                self.status = {'CANCELLED'}
            else:
                import_osd(osd, context.selected_objects)
                log.info(f"Imported OSD file with {len(osd.entries)} entries"
                         f" into shapes: {list(osd.shapes.keys())}")

            self.log_handler.finish("IMPORT OSD", self.filepath)

        except:
            self.log_handler.log.exception("Import of OSD failed")
            self.report({"ERROR"}, "Import of OSD failed, see console window for details")
            self.status = {'CANCELLED'}

        finally:
            self.log_handler.finish("IMPORT OSD", self.filepath)

        wm = context.window_manager
        wm.pynifly_last_import_path_osd = str(self.file_path)

        return self.status.intersection({'FINISHED', 'CANCELLED'})
