"""Starfield BSGeometry / external .mesh import (and, later, export).

A Starfield BSGeometry references its geometry as one or more external .mesh files (one per
LOD slot). The geometry isn't present in the NIF, so on import we resolve each .mesh path to
a loose file and load its bytes into the shape before the normal geometry build reads them.
Loose-file resolution reuses the same search PyNifly already does for textures/materials.
"""

import logging
import os
from pathlib import Path
import bpy
from .. import __package__ as base_package
from .. import blender_defs as BD
from ..pyn.niflytools import find_referenced_file, texture_path
from ..gamefinder import find_game

log = logging.getLogger("pynifly")


def mesh_search_paths(game='SF'):
    """Loose-file search roots for resolving .mesh files, mirroring the texture search:
    the user's configured paths plus a registry-derived game Data folder."""
    paths = []
    try:
        prefs = bpy.context.preferences.addons[base_package].preferences
        for p in (prefs.sf_texture_path_1, prefs.sf_texture_path_2,
                  prefs.sf_texture_path_3, prefs.sf_texture_path_4):
            if p and (cleaned := texture_path(p)):
                paths.append(cleaned)
    except Exception:
        pass
    game_data = find_game(game)
    if game_data:
        paths.append(game_data)
    return paths


def resolve_mesh(mesh_path, nif_filepath):
    """Resolve a BSGeometry .mesh path (the verbatim meshName -- no 'geometries\\' root, no
    '.mesh' extension) to a loose file on disk. Returns the path, or None if not found."""
    if not mesh_path:
        return None
    return find_referenced_file(
        mesh_path, nifpath=nif_filepath, root='geometries',
        alt_suffix='.mesh', alt_pathlist=mesh_search_paths())


def load_geometry(the_shape, slot=0):
    """Resolve + load the external .mesh for a BSGeometry LOD slot so the shape's
    verts/tris/uvs/normals/weights become available. Returns True if loaded."""
    mesh_path = the_shape.mesh_path(slot)
    resolved = resolve_mesh(mesh_path, the_shape.file.filepath)
    if not resolved:
        log.warning(f"Could not find external .mesh for '{the_shape.name}': '{mesh_path}' "
                    f"(extract it from the BA2 to a loose file)")
        return False
    with open(resolved, 'rb') as f:
        data = f.read()
    return the_shape.load_mesh(data, slot)


def record_geometry_props(obj, the_shape, slot=0):
    """Record the round-trip data that isn't recoverable from the Blender mesh: the verbatim
    external .mesh path, its LOD slot, and the internal-geometry (0x200) flag. Stored on
    obj.pyn_sf_geometry so export can write geometry back to the same .mesh (in-place
    replacer) or, for a newly-created shape with no recorded path, fall back to
    prefix-autogen."""
    from . import pyn_props
    pyn_props.set_group(obj, 'pyn_sf_geometry',
                        mesh_path=the_shape.mesh_path(slot),
                        lod_slot=slot,
                        is_internal=the_shape.is_internal_geom)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def sf_base_name(obj):
    """The BSGeometry block name for a LOD-child mesh object. The container Empty holds the
    real nif name in pynNodeName; fall back to stripping the ':LOD<slot>' suffix off the
    child's own name."""
    empty = obj.parent
    if empty is not None and empty.get('pynNodeName'):
        return empty['pynNodeName']
    name = obj.name
    if ':LOD' in name:
        name = name.rsplit(':LOD', 1)[0]
    return name


def resolve_mesh_output_path(nif_filepath, mesh_name):
    """Where to write an external .mesh on export. `mesh_name` is the verbatim BSGeometry
    meshName (no 'geometries\\' root, no '.mesh' extension). The .mesh lives at
    <data_root>/geometries/<mesh_name>.mesh, where <data_root> is the folder that holds the
    'meshes' tree the nif is being written into (geometries is a sibling of meshes). If the
    nif isn't under a 'meshes' folder, fall back to a 'geometries' folder beside the nif."""
    p = Path(nif_filepath)
    parts = p.parts
    root = None
    for i, part in enumerate(parts):
        if part.lower() == 'meshes':
            root = Path(*parts[:i]) if i > 0 else Path(p.anchor)
            break
    if root is None:
        root = p.parent
    rel = mesh_name.replace('\\', os.sep).replace('/', os.sep)
    return str(root / 'geometries' / (rel + '.mesh'))


def export_sf_shape(exporter, obj, new_shape, verts, uvs, norms, tris,
                    colors, weights_by_vert, arma, new_xform):
    """Finish exporting a Starfield BSGeometry: set the external .mesh path, vertex colors,
    and skin (bone list -> SkinAttach, per-bone binds -> BSSkin::BoneData, per-vertex weights
    -> the .mesh), then queue the .mesh bytes to be written to disk after the nif is saved.

    Geometry (verts/tris/uvs/normals) is already on `new_shape` from createShapeFromData.
    Returns the resolved output .mesh path (also queued on exporter._sf_meshes)."""
    slot = 0
    grp = getattr(obj, 'pyn_sf_geometry', None)
    if grp is not None:
        slot = grp.lod_slot

    # External .mesh path: reuse the imported meshName verbatim (in-place replacer) or, for a
    # newly-authored shape, autogenerate one under a mod prefix (kept short -- the BSGeometry
    # meshName field is capped at ~46 chars).
    mesh_name = grp.mesh_path if (grp and grp.mesh_path) else ''
    if not mesh_name:
        mesh_name = 'FSF\\' + sf_base_name(obj)
    new_shape.set_mesh_name(mesh_name, slot)

    # Vertex colors: SF meshes always carry them; default to white where Blender has none.
    if colors:
        new_shape.set_mesh_colors([tuple(c) for c in colors], slot)
    else:
        new_shape.set_mesh_colors([(1.0, 1.0, 1.0, 1.0)] * len(verts), slot)

    # Skin: SF has no NiNode bone refs; build the bone name list + binds + per-vertex weights.
    if arma is not None:
        _export_sf_skin(exporter, obj, new_shape, verts, weights_by_vert, arma, new_xform)

    out_path = resolve_mesh_output_path(exporter.nif.filepath, mesh_name)
    if not hasattr(exporter, '_sf_meshes'):
        exporter._sf_meshes = []
    exporter._sf_meshes.append((out_path, new_shape, slot))
    return out_path


def _export_sf_skin(exporter, obj, new_shape, verts, weights_by_vert, arma, new_xform):
    """Assemble SF skinning on a BSGeometry: an ordered bone list (SkinAttach), a bind
    (skin-to-bone) transform per bone (BSSkin::BoneData), and per-vertex weights (top 4,
    normalized). Bone ordering fixes the index that both SkinAttach and the weights use."""
    arma_bones = arma.data.bones

    # Ordered list of bones that actually weight this shape, in armature order for stability.
    used = set()
    for vw in weights_by_vert:
        for nm, w in vw.items():
            if w > 0.00005 and nm in arma_bones:
                used.add(nm)
    bone_list = [b.name for b in arma_bones if b.name in used]
    if not bone_list:
        log.warning(f"{obj.name}: Starfield shape has no armature-bone weights; "
                    "exporting without skin.")
        return
    bone_index = {nm: i for i, nm in enumerate(bone_list)}

    # SkinAttach: nif-name each bone (SF names generally pass through unchanged).
    nif_names = [exporter.nif_name(nm) for nm in bone_list]
    new_shape.skin_bones(nif_names)

    # Per-bone bind = inverse of (vert-frame -> bone), same formula as the generic export_skin.
    for i, nm in enumerate(bone_list):
        xf = BD.get_bone_xform(arma, nm, exporter.game, False, exporter.settings.export_pose)
        xfinv = (new_xform.inverted() @ xf).inverted()
        new_shape.set_bone_bind(i, BD.pack_xf_to_buf(xfinv, exporter.scale))

    # Per-vertex weights: keep the 4 heaviest bone weights, normalized.
    for v, vw in enumerate(weights_by_vert):
        pairs = [(w, bone_index[nm]) for nm, w in vw.items()
                 if w > 0.00005 and nm in bone_index]
        pairs.sort(reverse=True)
        pairs = pairs[:4]
        total = sum(w for w, _ in pairs)
        if total <= 0:
            continue
        idxs = [bi for _, bi in pairs]
        wts = [w / total for w, _ in pairs]
        new_shape.set_vert_weights(v, idxs, wts)

    # Finalize per-bone bounding spheres now that binds + weights are set. Skipping this leaves
    # the default zero-radius spheres, which crash the Creation Kit on actor load.
    new_shape.update_skin_bounds()


def write_sf_meshes(exporter):
    """Write every queued external .mesh to disk (called after nif.save()). Each entry is
    (output_path, BSGeometry_shape, slot)."""
    for out_path, shape, slot in getattr(exporter, '_sf_meshes', []):
        data = shape.save_mesh(slot)
        if not data:
            log.warning(f"No .mesh data to write for {out_path}")
            continue
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)
        log.info(f"Wrote external .mesh: {out_path}")
