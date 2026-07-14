"""Starfield morph.dat export: write a mesh's shape keys as a morph.dat.

Each non-Basis shape key becomes a named morph; its per-vertex offset from Basis is the position
delta. Sparse -- only vertices that move beyond `epsilon` are recorded. Positions only: the
morph.dat normal/tangent/colour channels are written as neutral defaults (see pyn.sf_morph).
"""
from pathlib import Path
import logging
import bpy
import numpy as np
from bpy_extras.io_utils import ExportHelper
from .. import blender_defs as BD
from .. import bl_info
from ..pyn.sf_morph import MorphFile, MAX_KEYS

log = logging.getLogger("pynifly")


def build_morph(obj, scale=1.0, epsilon=1e-4):
    """Build a MorphFile from mesh object `obj`'s shape keys (positions-only).

    `scale` divides Blender coords back to game units before delta computation (inverse of the
    import `scale`). Basis is the reference; every other key is a morph. Raises ValueError if the
    object has no shape keys or exceeds the 128-key cap.
    """
    mesh = obj.data
    keys = mesh.shape_keys
    if keys is None or "Basis" not in keys.key_blocks:
        raise ValueError(f"'{obj.name}' has no shape keys with a Basis to export")

    basis = keys.key_blocks["Basis"]
    n = len(mesh.vertices)
    base = np.empty(n * 3, dtype=np.float32)
    basis.data.foreach_get('co', base)

    morph_keys = [kb for kb in keys.key_blocks if kb.name != "Basis"]
    if len(morph_keys) > MAX_KEYS:
        raise ValueError(f"{len(morph_keys)} shape keys exceeds the {MAX_KEYS}-morph cap")

    names = []
    deltas = {}
    for kb in morph_keys:
        co = np.empty(n * 3, dtype=np.float32)
        kb.data.foreach_get('co', co)
        d = ((co - base) / scale).reshape(n, 3)
        moved = np.nonzero(np.abs(d).max(axis=1) > epsilon)[0]
        names.append(kb.name)
        deltas[kb.name] = {int(vi): (float(d[vi, 0]), float(d[vi, 1]), float(d[vi, 2]))
                           for vi in moved}
        log.debug(f"morph {kb.name!r}: {len(moved)} of {n} vertices move")

    return MorphFile.from_deltas(names, n, deltas)


class ExportSFMorph(bpy.types.Operator, ExportHelper):
    """Write the active mesh's shape keys as a Starfield morph.dat"""
    bl_idname = "export_scene.pyniflysfmorph"
    bl_label = "Export Starfield Morph (Nifly)"
    bl_options = {'PRESET'}

    filename_ext = ".dat"
    filter_glob: bpy.props.StringProperty(
        default="*.dat",
        options={'HIDDEN'},
    )  # type: ignore

    def execute(self, context):
        self.log_handler = BD.LogHandler()
        self.log_handler.start(bl_info, "EXPORT", "SFMORPH")
        status = {'FINISHED'}

        obj = context.object
        try:
            if obj is None or obj.type != 'MESH':
                self.report({"ERROR"}, "Select a mesh object with shape keys to export")
                return {'CANCELLED'}
            morph = build_morph(obj)
            morph.to_file(Path(self.filepath))
            log.info(f"Exported {len(morph.morph_names)} morph(s) from {obj.name} "
                     f"to {self.filepath}")
        except Exception:
            self.log_handler.log.exception("Export of Starfield morph.dat failed")
            self.report({"ERROR"}, "Export failed, see console window for details")
            status = {'CANCELLED'}
        finally:
            self.log_handler.finish("EXPORT SFMORPH", self.filepath)

        return status
