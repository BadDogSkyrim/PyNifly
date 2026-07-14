"""Starfield morph.dat import: apply a morph.dat as Blender shape keys on a mesh.

morph.dat holds named per-vertex position deltas (see pyn.sf_morph). Each morph name becomes a
shape key on the target mesh; the mesh vertex count/order must match the morph file. Positions
only -- the file's normal/tangent/colour delta channels are not represented in Blender.
"""
from pathlib import Path
import logging
import bpy
import numpy as np
from bpy_extras.io_utils import ImportHelper
from .. import blender_defs as BD
from .. import bl_info
from ..pyn.sf_morph import MorphFile

log = logging.getLogger("pynifly")


def apply_morphs(obj, morph: MorphFile, scale=1.0):
    """Add one shape key per morph in `morph` to mesh object `obj`.

    `scale` multiplies the game-unit deltas (default 1.0 -- the mesh is assumed to be at PyNifly's
    default game-unit import scale). Raises ValueError on a vertex-count mismatch.
    """
    mesh = obj.data
    verts = mesh.vertices
    n = len(verts)
    if n != morph.num_vertices:
        raise ValueError(
            f"Mesh '{obj.name}' has {n} vertices but morph.dat expects {morph.num_vertices}")

    if mesh.shape_keys is None or "Basis" not in mesh.shape_keys.key_blocks:
        basis = obj.shape_key_add()
        basis.name = "Basis"
        mesh.shape_keys.use_relative = True

    # Base coords once into a flat float32 buffer; per-morph copy + sparse add + bulk foreach_set
    # (same fast path as the TRIP importer -- avoids a per-vert Python loop).
    base = np.empty(n * 3, dtype=np.float32)
    verts.foreach_get('co', base)

    deltas = morph.key_deltas()
    for name in morph.morph_names:
        sk = obj.shape_key_add()
        sk.name = name
        sk.value = 0
        coords = base.copy()
        for vi, (dx, dy, dz) in deltas[name].items():
            i = vi * 3
            coords[i]     += dx * scale
            coords[i + 1] += dy * scale
            coords[i + 2] += dz * scale
        sk.data.foreach_set('co', coords)

    obj.active_shape_key_index = 0
    log.info(f"Applied {len(morph.morph_names)} morph(s) to {obj.name}")


class ImportSFMorph(bpy.types.Operator, ImportHelper):
    """Load a Starfield morph.dat as shape keys on the active mesh"""
    bl_idname = "import_scene.pyniflysfmorph"
    bl_label = "Import Starfield Morph (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".dat"
    filter_glob: bpy.props.StringProperty(
        default="*.dat",
        options={'HIDDEN'},
    )  # type: ignore

    def execute(self, context):
        self.log_handler = BD.LogHandler()
        self.log_handler.start(bl_info, "IMPORT", "SFMORPH")
        status = {'FINISHED'}

        obj = context.object
        try:
            if obj is None or obj.type != 'MESH':
                self.report({"ERROR"}, "Select a mesh object to receive the morphs")
                return {'CANCELLED'}
            morph = MorphFile.from_file(Path(self.filepath))
            apply_morphs(obj, morph)
            # Record the source path so export can round-trip to the same file (a morph.dat under
            # a .../performance/... tree is the performance file, else chargen).
            from ..nif import pyn_props
            which = 'performance_path' if 'performance' in self.filepath.lower() else 'chargen_path'
            pyn_props.set_group(obj, 'pyn_sf_morph', **{which: self.filepath})
            log.info(f"Imported Starfield morph.dat into {obj.name}")
        except Exception:
            self.log_handler.log.exception("Import of Starfield morph.dat failed")
            self.report({"ERROR"}, "Import failed, see console window for details")
            status = {'CANCELLED'}
        finally:
            self.log_handler.finish("IMPORT SFMORPH", self.filepath)

        return status
