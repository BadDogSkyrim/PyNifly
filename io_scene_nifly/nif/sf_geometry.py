"""Starfield BSGeometry / external .mesh import (and, later, export).

A Starfield BSGeometry references its geometry as one or more external .mesh files (one per
LOD slot). The geometry isn't present in the NIF, so on import we resolve each .mesh path to
a loose file and load its bytes into the shape before the normal geometry build reads them.
Loose-file resolution reuses the same search PyNifly already does for textures/materials.
"""

import logging
import bpy
from .. import __package__ as base_package
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
