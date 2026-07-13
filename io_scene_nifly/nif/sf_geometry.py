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
    # Record the source .mesh's per-vertex influence count (max bones weighting any vertex) so a
    # re-export preserves it instead of the generic cap; editable to trim down.
    counts = {}
    for vw_list in the_shape.bone_weights.values():
        for vi, w in vw_list:
            if w > 0.00005:
                counts[vi] = counts.get(vi, 0) + 1
    src_wpv = min(max(counts.values(), default=0), SF_MAX_WEIGHTS_PER_VERTEX)
    pyn_props.set_group(obj, 'pyn_sf_geometry',
                        mesh_path=the_shape.mesh_path(slot),
                        lod_slot=slot,
                        is_internal=the_shape.is_internal_geom,
                        weights_per_vertex=src_wpv)


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

    # Queue the material for a loose .mat write (recovered from its shader graph on nif.save()).
    mat = obj.active_material
    if mat is not None and mat.get('BSLSP_Shader_Name'):
        if not hasattr(exporter, '_sf_materials'):
            exporter._sf_materials = []
        exporter._sf_materials.append(mat)
    return out_path


# Max bone influences kept per vertex. Starfield has no hard limit (vanilla body = 6,
# hair = 7); the .mesh stores one weightsPerVertex for the whole shape and pads verts with
# fewer. Capping generously at 8 covers observed vanilla assets while keeping the file bounded.
SF_MAX_WEIGHTS_PER_VERTEX = 8


def _export_sf_skin(exporter, obj, new_shape, verts, weights_by_vert, arma, new_xform):
    """Assemble SF skinning on a BSGeometry: an ordered bone list (SkinAttach), a bind
    (skin-to-bone) transform per bone (BSSkin::BoneData), and per-vertex weights (the heaviest
    influences, normalized). Bone ordering fixes the index that both SkinAttach and the weights
    use. The shape's weightsPerVertex is the max influence count across its verts (<= the cap),
    matching how vanilla sizes it -- must be set before skin_bones zeroes the weight slots."""
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

    # Precompute each vertex's heaviest influences so the shape's weightsPerVertex can be set
    # from the true max before skinning (nifly sizes/caps the weight slots to it).
    vert_pairs = []
    for vw in weights_by_vert:
        pairs = [(w, bone_index[nm]) for nm, w in vw.items()
                 if w > 0.00005 and nm in bone_index]
        pairs.sort(reverse=True)
        vert_pairs.append(pairs[:SF_MAX_WEIGHTS_PER_VERTEX])
    weights_per_vertex = max((len(p) for p in vert_pairs), default=1) or 1

    # SkinAttach: nif-name each bone (SF names generally pass through unchanged).
    nif_names = [exporter.nif_name(nm) for nm in bone_list]
    new_shape.skin_bones(nif_names, weights_per_vertex)

    # Per-bone bind = inverse of (vert-frame -> bone), same formula as the generic export_skin.
    for i, nm in enumerate(bone_list):
        xf = BD.get_bone_xform(arma, nm, exporter.game, False, exporter.settings.export_pose)
        xfinv = (new_xform.inverted() @ xf).inverted()
        new_shape.set_bone_bind(i, BD.pack_xf_to_buf(xfinv, exporter.scale))

    # Per-vertex weights, normalized over the kept influences.
    for v, pairs in enumerate(vert_pairs):
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


def resolve_material_output_path(nif_filepath, mat_ref):
    """Where to write a loose .mat on export. `mat_ref` is the material's path ('Materials\\...\\
    x.mat', relative to Data\\). Written to <data_root>/<mat_ref>, where <data_root> holds the
    'meshes' tree the nif is written into (materials is a sibling of meshes) -- so a round-trip to
    an Out/ tree lands beside the exported nif and never touches the source material."""
    p = Path(nif_filepath)
    parts = p.parts
    root = None
    for i, part in enumerate(parts):
        if part.lower() == 'meshes':
            root = Path(*parts[:i]) if i > 0 else Path(p.anchor)
            break
    if root is None:
        root = p.parent
    rel = mat_ref.replace('\\', os.sep).replace('/', os.sep)
    return str(root / rel)


def write_sf_materials(exporter):
    """Write a loose .mat for each exported SF material, recovered from its shader graph (called
    after nif.save()). Only materials with a recoverable SF graph (shader model or layers) are
    written; the file lands in the output tree, not over the source material."""
    from . import shader_io
    from ..pyn import sf_materials
    seen = set()
    for mat in getattr(exporter, '_sf_materials', []):
        mat_ref = mat.get('BSLSP_Shader_Name', '')
        if not mat_ref or mat_ref in seen:
            continue
        seen.add(mat_ref)
        data = shader_io.recover_sf_material(mat)
        if not data or (not data.get('layers') and not data['settings'].get('shader_model')):
            continue
        out_path = resolve_material_output_path(exporter.nif.filepath, mat_ref)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(sf_materials.write_mat(data, filename=mat_ref))
        log.info(f"Wrote loose .mat: {out_path}")
