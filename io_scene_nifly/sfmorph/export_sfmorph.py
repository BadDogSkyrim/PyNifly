"""Starfield morph.dat export: write a mesh's shape keys as morph.dat file(s).

A head's shape keys split into two output files by name (see pyn.sf_morph.is_expression_morph):
expression / action-unit keys -> a `performance/` morph.dat, chargen sliders -> a `chargen/`
morph.dat. Each non-Basis shape key becomes a named morph; its per-vertex offset from Basis is the
position delta (sparse -- only vertices moved beyond `epsilon`). Positions only: the morph.dat
normal/tangent/colour channels are written as neutral defaults (see pyn.sf_morph).

Output paths come from the object's `pyn_sf_morph` group (chargen_path / performance_path); an
unset path is derived from the export dialog path by swapping the chargen<->performance sibling
folder.
"""
import os
from pathlib import Path
import logging
import bpy
import numpy as np
from bpy_extras.io_utils import ExportHelper
from .. import blender_defs as BD
from .. import bl_info
from ..pyn.sf_morph import (MorphFile, MAX_KEYS, is_expression_morph,
                            morph_relpath, resolve_morph_output, swap_morph_tree)

log = logging.getLogger("pynifly")


def _key_deltas(kb, base, n, scale, epsilon):
    """Sparse per-vertex delta dict for one shape key (vs the Basis buffer `base`)."""
    co = np.empty(n * 3, dtype=np.float32)
    kb.data.foreach_get('co', co)
    d = ((co - base) / scale).reshape(n, 3)
    moved = np.nonzero(np.abs(d).max(axis=1) > epsilon)[0]
    return {int(vi): (float(d[vi, 0]), float(d[vi, 1]), float(d[vi, 2])) for vi in moved}


def build_morphs(obj, scale=1.0, epsilon=1e-4):
    """Split `obj`'s shape keys into performance vs chargen MorphFiles by is_expression_morph.

    Returns {'chargen': MorphFile|None, 'performance': MorphFile|None} (None where that group has
    no shape keys). Raises ValueError if the object has no Basis or a group exceeds the key cap.
    """
    mesh = obj.data
    keys = mesh.shape_keys
    if keys is None or "Basis" not in keys.key_blocks:
        raise ValueError(f"'{obj.name}' has no shape keys with a Basis to export")

    basis = keys.key_blocks["Basis"]
    n = len(mesh.vertices)
    base = np.empty(n * 3, dtype=np.float32)
    basis.data.foreach_get('co', base)

    groups = {'chargen': ([], {}), 'performance': ([], {})}
    for kb in keys.key_blocks:
        if kb.name == "Basis":
            continue
        which = 'performance' if is_expression_morph(kb.name) else 'chargen'
        names, deltas = groups[which]
        names.append(kb.name)
        deltas[kb.name] = _key_deltas(kb, base, n, scale, epsilon)

    out = {}
    for which, (names, deltas) in groups.items():
        if not names:
            out[which] = None
            continue
        if len(names) > MAX_KEYS:
            raise ValueError(f"{len(names)} {which} morphs exceeds the {MAX_KEYS}-morph cap")
        out[which] = MorphFile.from_deltas(names, n, deltas)
    return out


def resolve_morph_paths(obj, dialog_path):
    """Return absolute (chargen_path, performance_path) for the export.

    The object's pyn_sf_morph group holds each path RELATIVE to 'meshes' (stashed on import). We
    fill an unset sibling by swapping the chargen<->performance tree, seed from the export dialog
    path if nothing is stored, then resolve each relative path to absolute against the dialog path
    as the export anchor (its 'meshes' root -> the Data root). Either may be '' if undetermined.
    """
    grp = getattr(obj, 'pyn_sf_morph', None)
    cp = (getattr(grp, 'chargen_path', '') if grp else '') or ''
    pp = (getattr(grp, 'performance_path', '') if grp else '') or ''

    # Derive the missing sibling from the other (swap chargen<->performance in the stored path).
    if cp and not pp:
        pp = swap_morph_tree(cp)
    if pp and not cp:
        cp = swap_morph_tree(pp)

    # Nothing stored -> seed from the dialog path (relative-ize it, derive the sibling).
    seed = str(dialog_path) if dialog_path else ''
    if not cp and not pp and seed:
        low = seed.lower()
        if 'performance' in low:
            pp = morph_relpath(seed); cp = swap_morph_tree(pp)
        elif 'chargen' in low:
            cp = morph_relpath(seed); pp = swap_morph_tree(cp)
        else:
            cp = seed   # no chargen/performance hint -> write the (chargen-classed) file here

    return resolve_morph_output(cp, seed), resolve_morph_output(pp, seed)


class ExportSFMorph(bpy.types.Operator, ExportHelper):
    """Write the active mesh's shape keys as Starfield morph.dat file(s) (chargen + performance)"""
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
            morphs = build_morphs(obj)
            cp, pp = resolve_morph_paths(obj, self.filepath)
            wrote = []
            for which, path in (('chargen', cp), ('performance', pp)):
                mf = morphs[which]
                if mf is None:
                    continue
                if not path:
                    log.warning(f"{len(mf.morph_names)} {which} morph(s) but no {which} output "
                                f"path (set {obj.name}.pyn_sf_morph.{which}_path)")
                    continue
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                mf.to_file(path)
                wrote.append(f"{len(mf.morph_names)} {which} -> {path}")
            if not wrote:
                self.report({"ERROR"}, "No morphs written (no shape keys or no output paths)")
                status = {'CANCELLED'}
            else:
                log.info(f"Exported Starfield morphs from {obj.name}: " + "; ".join(wrote))
        except Exception:
            self.log_handler.log.exception("Export of Starfield morph.dat failed")
            self.report({"ERROR"}, "Export failed, see console window for details")
            status = {'CANCELLED'}
        finally:
            self.log_handler.finish("EXPORT SFMORPH", self.filepath)

        return status
