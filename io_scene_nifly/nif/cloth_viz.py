"""Draw a Starfield cloth blob (BSClothExtraData) in Blender, and write edits to it back.

Under the cloth's empty, import adds
- a mesh per simulated cloth: vertex = particle at its rest position, face = sim triangle, and an
  edge per link with the int attribute `cloth_link` (1 standard, 2 stretch, 3 both); per-particle
  `cloth_mass` / `cloth_radius` / `cloth_friction`, the pinned particles in vertex group
  `cloth_pinned`, and each of the sim's settings as a `cloth_<setting>` property;
- a mesh per collision shape (capsule, tapered capsule, sphere), named for the collidable, with
  its shape, bone and parameters as properties.

Every one is marked `pynClothViz`, which export skips as a shape. Instead export reads the edits
back off them (apply_edits) and writes them into the blob in place: the settings, the particle
attributes, and capsules and spheres moved, turned or scaled as objects. See pyn/sf_cloth.py for
the blob side, and the "Starfield cloth editing -- plan" doc.
"""
import logging
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from ..pyn import sf_cloth
from ..pyn.nifconstants import HAVOC_SCALE_FACTOR
from .. import blender_defs as BD

log = logging.getLogger("pynifly")

VIZ_PROP = 'pynClothViz'
LINK_BITS = {'standard': 1, 'stretch': 2}


def build(cloth_obj, blob, scale, collection):
    """Draw `blob` under `cloth_obj`. `scale` is the import's scale factor. Returns the objects
    made; a blob that won't decode is logged and drawn as nothing."""
    try:
        cloth = sf_cloth.read_cloth(blob)
    except Exception as e:
        log.warning(f"Could not read the cloth data for display: {e}")
        return []
    s = HAVOC_SCALE_FACTOR * scale
    objs = [_sim_mesh(sim, s) for sim in cloth.sims]
    objs += [_collidable(col, s) for col in cloth.collidables]
    for i, o in enumerate(objs[:len(cloth.sims)]):
        o['cloth_index'] = i
    for i, o in enumerate(objs[len(cloth.sims):]):
        o['cloth_index'] = i
    for o in objs:
        o[VIZ_PROP] = True
        BD.link_to_collection(collection, o)
        # The cloth empty sits off to the side like the other extra-data empties; cancel its
        # placement so the pictures land in the nif root's space, on the character.
        o.parent = cloth_obj
        o.matrix_parent_inverse = cloth_obj.matrix_basis.inverted()
        o.display_type = 'WIRE'
        o.show_in_front = True
    return objs


def _sim_mesh(sim, s):
    bm = bmesh.new()
    # Layers first: adding one reallocates the elements and orphans any held references.
    link = bm.edges.layers.int.new('cloth_link')
    layers = {key: bm.verts.layers.float.new('cloth_' + key)
              for key in ('mass', 'radius', 'friction')}
    verts = [bm.verts.new(Vector(p) * s) for p in sim.positions]
    bm.verts.ensure_lookup_table()
    for tri in sim.triangles:
        if len(set(tri)) == 3:
            try:
                bm.faces.new([verts[i] for i in tri])
            except ValueError:
                pass                                # the same triangle twice
    for a, b, kind in sim.links:
        if a == b:
            continue
        e = bm.edges.get((verts[a], verts[b])) or bm.edges.new((verts[a], verts[b]))
        e[link] |= LINK_BITS[kind]
    for key, layer in layers.items():
        for v, p in zip(verts, sim.particles):
            v[layer] = p[key]

    me = bpy.data.meshes.new(f"Cloth:{sim.cloth_data or sim.name}")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(me.name, me)
    pinned = obj.vertex_groups.new(name='cloth_pinned')
    if sim.pinned:
        pinned.add(sim.pinned, 1.0, 'REPLACE')
    obj['cloth_sim'] = sim.name
    for k, v in sim.settings.items():
        if k not in sf_cloth.DERIVED_SETTINGS:
            obj['cloth_' + k] = list(v) if isinstance(v, tuple) else v
    return obj


def _capsule_mesh(bm, length, r0, r1, segments=16, rings=4):
    """A capsule along +Z from 0 to `length`: a hemisphere of radius r0 at the bottom, r1 at the
    top. Unequal radii draw a tapered capsule."""
    profile = []
    for k in range(rings + 1):                      # bottom pole up to the equator
        a = -math.pi / 2 + (math.pi / 2) * k / rings
        profile.append((r0 * math.sin(a), r0 * math.cos(a)))
    for k in range(rings + 1):                      # equator up to the top pole
        a = (math.pi / 2) * k / rings
        profile.append((length + r1 * math.sin(a), r1 * math.cos(a)))
    ring_verts = []
    for z, r in profile:
        if r < 1e-9:
            ring_verts.append([bm.verts.new((0, 0, z))])
            continue
        ring_verts.append([bm.verts.new((r * math.cos(2 * math.pi * j / segments),
                                         r * math.sin(2 * math.pi * j / segments), z))
                           for j in range(segments)])
    for lo, hi in zip(ring_verts, ring_verts[1:]):
        if lo is hi or (len(lo) == 1 and len(hi) == 1):
            continue
        for j in range(segments):
            a, b = lo[j % len(lo)], lo[(j + 1) % len(lo)]
            c, d = hi[(j + 1) % len(hi)], hi[j % len(hi)]
            quad = list(dict.fromkeys([a, b, c, d]))
            if len(quad) >= 3:
                try:
                    bm.faces.new(quad)
                except ValueError:
                    pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)


def _capsule_frame(col, s):
    """Where a collidable's mesh sits: (frame, length, r0, r1). The mesh is built along +Z from 0
    to `length` (game units), and `frame` takes it into the collidable's own space -- to the
    shape's start, turned to its axis. A sphere is a zero-length capsule at its centre. Radii are
    in metres, as the blob has them."""
    p = col.params
    if col.shape == 'sphere':
        return Matrix.Translation(Vector(p['center']) * s), 0.0, p['radius'], p['radius']
    if col.shape == 'capsule':
        a, b, r0, r1 = p['start'], p['end'], p['radius'], p['radius']
    elif col.shape == 'tapered_capsule':
        a, b, r0, r1 = p['small'], p['big'], p['small_radius'], p['big_radius']
    else:
        return Matrix.Identity(4), 0.0, 0.01, 0.01
    start, axis = Vector(a) * s, (Vector(b) - Vector(a)) * s
    rot = (Vector((0, 0, 1)).rotation_difference(axis.normalized()).to_matrix().to_4x4()
           if axis.length > 1e-9 else Matrix.Identity(4))
    return Matrix.Translation(start) @ rot, axis.length, r0, r1


def _collidable_matrix(col, s):
    """The collidable's own space, in the nif root's space and game units."""
    m = Matrix(col.transform)
    m.translation = m.translation * s
    return m


def _collidable(col, s):
    frame, length, r0, r1 = _capsule_frame(col, s)
    bm = bmesh.new()
    if col.shape == 'sphere':
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=r0 * s)
    else:
        if col.shape not in ('capsule', 'tapered_capsule'):
            log.warning(f"Cloth collidable {col.name}: shape {col.shape} not drawn")
        _capsule_mesh(bm, length, r0 * s, r1 * s)
    me = bpy.data.meshes.new(col.name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(col.name, me)
    obj.matrix_basis = _collidable_matrix(col, s) @ frame
    obj['cloth_shape'] = col.shape
    obj['cloth_bone'] = col.bone or ''
    obj['cloth_params'] = {k: list(v) if isinstance(v, tuple) else v
                           for k, v in col.params.items()}
    return obj


# --- export: read the edits back off the pictures --------------------------------------------

def _attr(me, name, n):
    vals = [0.0] * n
    me.attributes[name].data.foreach_get('value', vals)
    return vals


def _sim_edits(obj, sim, s):
    """Copy what `obj` (a sim mesh) says into `sim`. Positions and pinning aren't written yet:
    a change to either is warned about and left out."""
    me = obj.data
    n = len(me.vertices)
    if n != len(sim.particles):
        raise sf_cloth.ClothEditError(f"{obj.name} has {n} vertices, the cloth has "
                                      f"{len(sim.particles)} particles")
    co = [0.0] * (n * 3)
    me.vertices.foreach_get('co', co)
    moved = [i for i, p in enumerate(sim.positions)
             if (Vector(co[3 * i:3 * i + 3]) / s - Vector(p)).length > 1e-4]
    if moved:
        log.warning(f"{obj.name}: particle(s) {moved[:8]} moved; particle positions aren't "
                    f"written yet, so they keep their places in the cloth")
    vg = obj.vertex_groups.get('cloth_pinned')
    if vg is not None:
        pinned = sorted(v.index for v in me.vertices
                        if any(g.group == vg.index and g.weight > 0 for g in v.groups))
        if pinned != sorted(sim.pinned):
            log.warning(f"{obj.name}: cloth_pinned changed; pinning isn't written yet")
    for key in ('mass', 'radius', 'friction'):
        if 'cloth_' + key in me.attributes:
            for p, v in zip(sim.particles, _attr(me, 'cloth_' + key, n)):
                p[key] = v
    for key in sim.settings:
        if key in sf_cloth.DERIVED_SETTINGS or 'cloth_' + key not in obj:
            continue
        v = obj['cloth_' + key]
        sim.settings[key] = tuple(v) if hasattr(v, '__len__') else v


def _collidable_edits(obj, col, s):
    """Copy the object's move, turn and scale since import into `col`'s shape."""
    frame, length, r0, _r1 = _capsule_frame(col, s)
    delta = (_collidable_matrix(col, s) @ frame).inverted() @ obj.matrix_basis
    # Blender keeps the object's placement as location/rotation/scale, so the matrix it rebuilds
    # is a hair off the one import set. That isn't an edit.
    if all(abs(delta[r][c] - (r == c)) < (1e-3 if c == 3 else 1e-4)
           for r in range(3) for c in range(4)):
        return
    if col.shape not in ('capsule', 'sphere'):
        log.warning(f"{obj.name}: not written: {col.shape} edits aren't written yet")
        return
    scale = delta.to_scale()
    if col.shape == 'sphere':
        col.params['center'] = tuple((frame @ delta).translation / s)
        col.params['radius'] = r0 * (scale.x + scale.y + scale.z) / 3
        return
    col.params['start'] = tuple((frame @ delta @ Vector((0, 0, 0))) / s)
    col.params['end'] = tuple((frame @ delta @ Vector((0, 0, length))) / s)
    col.params['radius'] = r0 * (scale.x + scale.y) / 2


def _mesh_links(obj):
    """{kind: set of frozenset particle pairs} from the sim mesh's link edges."""
    me = obj.data
    if 'cloth_link' not in me.attributes:
        return {}
    vals = [0] * len(me.edges)
    me.attributes['cloth_link'].data.foreach_get('value', vals)
    out = {}
    for e, v in zip(me.edges, vals):
        for kind, bit in LINK_BITS.items():
            if v & bit:
                out.setdefault(kind, set()).add(frozenset(e.vertices))
    return out


def _new_links(obj, sim):
    """Link edges drawn on the sim mesh that the cloth doesn't have: {kind: [(a, b)]}. Links
    taken away aren't written yet, and are warned about."""
    drawn = _mesh_links(obj)
    out = {}
    for kind in LINK_BITS:
        have = {frozenset((a, b)) for a, b, k in sim.links if k == kind}
        mine = drawn.get(kind, set())
        if have - mine:
            log.warning(f"{obj.name}: {len(have - mine)} {kind} link(s) removed; removing links "
                        f"isn't written yet, so they stay")
        out[kind] = sorted(tuple(sorted(p)) for p in mine - have)
    return out


def apply_edits(cloth_obj, blob, scale):
    """`blob` with the edits made to `cloth_obj`'s pictures written in: values in place, then any
    new links, which grow the blob. An edit that can't be written is logged and the blob
    returned as it was."""
    viz = [o for o in cloth_obj.children if o.get(VIZ_PROP)]
    if not viz:
        return blob
    try:
        cloth = sf_cloth.read_cloth(blob)
    except Exception as e:
        log.warning(f"Could not read the cloth data to write edits: {e}")
        return blob
    s = HAVOC_SCALE_FACTOR * scale
    try:
        new_links = {}
        for o in viz:
            i = o.get('cloth_index')
            if 'cloth_sim' in o and i is not None and i < len(cloth.sims):
                _sim_edits(o, cloth.sims[i], s)
                new_links[i] = _new_links(o, cloth.sims[i])
            elif o.get('cloth_shape') and i is not None and i < len(cloth.collidables):
                _collidable_edits(o, cloth.collidables[i], s)
        out = sf_cloth.write_cloth(blob, cloth)
        for i, by_kind in new_links.items():
            for kind, pairs in by_kind.items():
                if pairs:
                    out = sf_cloth.add_links(out, i, pairs, kind)
                    log.info(f"Added {len(pairs)} {kind} link(s) to "
                             f"{cloth.sims[i].cloth_data or cloth.sims[i].name}")
        return out
    except sf_cloth.ClothEditError as e:
        log.error(f"Cloth edits not written, the cloth goes out as imported: {e}")
        return blob
