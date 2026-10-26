"""Draw a Starfield cloth blob (BSClothExtraData) in Blender, and write edits to it back.

Under the cloth's empty, import adds
- a mesh per simulated cloth: vertex = particle at its rest position, face = sim triangle, and an
  edge per link with the int attribute `cloth_link` (1 standard, 2 stretch, 3 both); per-particle
  `cloth_mass` / `cloth_radius` / `cloth_friction`, the pinned particles in vertex group
  `cloth_pinned`, and each of the sim's settings as a `cloth_<setting>` property;
- a mesh per collision shape (capsule, tapered capsule, sphere), named for the collidable, with
  its shape, bone and parameters as properties;
- a square per bone plane, in its place at the bind pose, its face normal pointing to the side
  particles are kept on, with properties `cloth_plane_bone` and `cloth_plane_stiffness`. The
  particles it holds are the sim mesh's vertex group `plane:<the square's name>`.

The sim mesh also carries what the builder needs: each particle's skin weights as vertex
groups named for bones, its original number (`cloth_particle`) and collision mask, each hinge's
bend stiffness on its edge (`cloth_bend`), the local-range sets as numbered attributes, and as
properties the bones it drives, its link stiffness and the constraint sets carried over.

Every one is marked `pynClothViz`, which export skips as a shape. Instead export makes the
cloth model from them (model_from_pictures) and builds the blob afresh (pyn/sf_cloth_build.py),
so what the pictures show is what's written: moved and added or deleted particles, pinning,
links, hinges, settings, and collision shapes moved, scaled, copied, added or deleted. See
pyn/sf_cloth.py for the reading side, and the "Starfield cloth editing -- plan" doc.
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
PLANE_GROUP = 'plane:'          # sim-mesh vertex group: the particles a bone plane holds


def build(cloth_obj, blob, scale, collection):
    """Draw `blob` under `cloth_obj`. `scale` is the import's scale factor. Returns the objects
    made; a blob that won't decode is logged and drawn as nothing."""
    try:
        cloth = sf_cloth.read_model(blob)
    except Exception as e:
        log.warning(f"Could not read the cloth data for display: {e}")
        return []
    s = HAVOC_SCALE_FACTOR * scale
    sims = [_sim_mesh(sim, s) for sim in cloth.sims]
    cols = [_collidable(col, s) for col in cloth.collidables]
    for i, o in enumerate(sims):
        o['cloth_index'] = i
    for i, o in enumerate(cols):
        o['cloth_index'] = i
    planes = []
    binds = sf_cloth.bind_matrices(cloth.skeleton) if cloth.skeleton else []
    names = [b[0] for b in cloth.skeleton]
    for sim, sim_obj in zip(cloth.sims, sims):
        for p in sim.planes:
            if p['bone'] not in names:
                log.warning(f"Bone plane on {p['bone']}: no such bone, not drawn")
                continue
            o = _plane(p, binds[names.index(p['bone'])], sim.positions, s)
            vg = sim_obj.vertex_groups.new(name=PLANE_GROUP + o.name)
            vg.add(p['particles'], 1.0, 'REPLACE')
            planes.append(o)
    objs = sims + cols + planes
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
    bend = bm.edges.layers.float.new('cloth_bend')
    layers = {key: bm.verts.layers.float.new('cloth_' + key)
              for key in ('mass', 'radius', 'friction')}
    particle = bm.verts.layers.int.new('cloth_particle')
    mask = bm.verts.layers.int.new('cloth_collision_mask')
    ranges = []
    for k, lr in enumerate(sim.local_ranges, 1):
        fields = ['max', 'max_normal', 'min_normal']
        if any(r['stiffness'] is not None for r in lr['particles'].values()):
            fields.append('stiffness')
        ranges.append((lr, {f: bm.verts.layers.float.new(f'cloth_range{k}_{f}') for f in fields}))
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
    for (c, d), k in sim.bend.items():
        e = bm.edges.get((verts[c], verts[d])) or bm.edges.new((verts[c], verts[d]))
        e[bend] = k
    for key, layer in layers.items():
        for v, p in zip(verts, sim.particles):
            v[layer] = p[key]
    for i, v in enumerate(verts):
        v[particle] = i
        v[mask] = sim.collision_masks[i] if i < len(sim.collision_masks) else 0
    for lr, fl in ranges:
        for i, v in enumerate(verts):
            r = lr['particles'].get(i)
            for f, layer in fl.items():
                v[layer] = -1.0 if r is None else (r[f] if r[f] is not None else -1.0)

    me = bpy.data.meshes.new(f"Cloth:{sim.cloth_data or sim.name}")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(me.name, me)
    pinned = obj.vertex_groups.new(name='cloth_pinned')
    if sim.pinned:
        pinned.add(sim.pinned, 1.0, 'REPLACE')
    for i, infl in enumerate(sim.skin):
        for bone, w in infl:
            vg = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            vg.add([i], w, 'REPLACE')
    obj['cloth_sim'] = sim.name
    for k, v in sim.settings.items():
        if k not in sf_cloth.DERIVED_SETTINGS:
            obj['cloth_' + k] = list(v) if isinstance(v, tuple) else v
    obj['cloth_driven_bones'] = ','.join(b for b, _t in sim.driven)
    obj['cloth_transfer_bone'] = sim.transfer_bone or ''
    if 'standard' in sim.link_stiffness:
        obj['cloth_link_stiffness'] = sim.link_stiffness['standard']
    if 'stretch' in sim.link_stiffness:
        obj['cloth_stretch_stiffness'] = sim.link_stiffness['stretch']
    obj['cloth_stretch_slack'] = sim.stretch_slack
    for k, lr in enumerate(sim.local_ranges, 1):
        obj[f'cloth_range{k}_name'] = lr['name'] or ''
        obj[f'cloth_range{k}_stiffness'] = lr['stiffness']
        obj[f'cloth_range{k}_shape'] = lr['shape']
        obj[f'cloth_range{k}_normal'] = lr['normal']
    obj['cloth_carried'] = ', '.join(f"{cs.type_name} '{cs['name']}'" for cs in sim.carried)
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


def _plane(p, bind, positions, s):
    """A square for a bone plane, at its place in the bind pose (game units), centred where
    its particles fall on it, its face normal (+Z) the side they're kept on."""
    B = Matrix(bind)
    nx, ny, nz, d = p['equation']
    n_b = Vector((nx, ny, nz))
    ln = n_b.length or 1.0
    n_b, d = n_b / ln, d / ln
    n_m = (B.to_3x3() @ n_b).normalized()
    origin = B @ (-d * n_b)                         # a point on the plane, model space
    pts = [Vector(positions[i]) for i in p['particles'] if i < len(positions)]
    centre = sum(pts, Vector()) / len(pts) if pts else origin
    centre = centre - n_m * n_m.dot(centre - origin)
    half = max([(q - centre - n_m * n_m.dot(q - centre)).length for q in pts] + [0.02]) * 1.2
    h = half * s
    me = bpy.data.meshes.new(f"Plane:{p['bone']}")
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new(me.name, me)
    rot = Vector((0, 0, 1)).rotation_difference(n_m).to_matrix().to_4x4()
    obj.matrix_basis = Matrix.Translation(centre * s) @ rot
    obj['cloth_plane_bone'] = p['bone']
    obj['cloth_plane_stiffness'] = p['stiffness']
    obj['cloth_plane_set'] = p.get('set') or ''
    return obj


# --- export: the cloth model from the pictures, then the builder ------------------------------

def _attr(me, name, n, default=None):
    """A per-vertex (or per-edge) attribute's values, or None (or `default` * n) if missing."""
    if name not in me.attributes:
        return None if default is None else [default] * n
    a = me.attributes[name]
    vals = [0] * n if a.data_type == 'INT' else [0.0] * n
    a.data.foreach_get('value', vals)
    return vals


def _median(vals, default):
    vals = sorted(v for v in vals if v)
    return vals[len(vals) // 2] if vals else default


def _remap_carried(cs, old_to_new):
    """A carried constraint set with its particle numbers renumbered, or None if it names a
    particle that's gone."""
    def remap(v, key=''):
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                r = remap(x, k)
                if r is _GONE:
                    return _GONE
                out[k] = r
            return out
        if isinstance(v, list):
            out = [remap(x, key) for x in v]
            return _GONE if any(x is _GONE for x in out) else out
        if hasattr(v, 'items') and not isinstance(v, (dict, str)) and hasattr(v, 'type'):
            items = remap(list(v.items), key)
            return _GONE if items is _GONE else type(v)(v.type, items)
        if 'particle' in key.lower() and isinstance(v, int) and not isinstance(v, bool):
            return old_to_new.get(v, _GONE)
        return v
    value = remap(cs.value)
    return None if value is _GONE else type(cs)(cs.type, value)


_GONE = object()


def _sim_from_mesh(obj, sim, s):
    """Rewrite `sim` (as read from the blob) to be what the sim mesh `obj` says. Vertices keep
    their particle's number in `cloth_particle`, so the constraint sets carried over find their
    particles after vertices are added, deleted or reordered."""
    me = obj.data
    who = obj.name
    n = len(me.vertices)
    if n == 0:
        raise sf_cloth.ClothEditError(f"{who} has no vertices")
    ids = _attr(me, 'cloth_particle', n, default=-1)
    # A vertex extruded or duplicated copies its source's number; the first keeps it, the
    # copies are new particles.
    seen = set()
    for i, p in enumerate(ids):
        if p in seen:
            ids[i] = -1
        seen.add(p)
    co = [0.0] * (n * 3)
    me.vertices.foreach_get('co', co)
    # In the nif root's space, so a mesh modelled anywhere under the cloth empty is where it shows.
    m = _root_space(obj, obj.parent) if obj.parent is not None else obj.matrix_world
    positions = [tuple(x / s for x in m @ Vector(co[3 * i:3 * i + 3])) for i in range(n)]

    vg = obj.vertex_groups.get('cloth_pinned')
    pinned = set()
    if vg is not None:
        pinned = {v.index for v in me.vertices
                  if any(g.group == vg.index and g.weight > 0 for g in v.groups)}
    old = sim.particles
    mass = _attr(me, 'cloth_mass', n)
    radius = _attr(me, 'cloth_radius', n)
    friction = _attr(me, 'cloth_friction', n)
    free_mass = _median([p['mass'] for p in old], sf_cloth.NEW_PARTICLE['mass'])
    particles = []
    for i in range(n):
        o = old[ids[i]] if 0 <= ids[i] < len(old) else {}
        m = mass[i] if mass else o.get('mass', free_mass)
        if i in pinned:
            m = 0.0
        elif not m:
            if mass:
                log.warning(f"{who}: particle {i} isn't pinned but has no mass; it gets "
                            f"{free_mass}")
            m = free_mass
        particles.append({
            'mass': m,
            'radius': radius[i] if radius else o.get('radius', _median(
                [p['radius'] for p in old], sf_cloth.NEW_PARTICLE['radius'])),
            'friction': friction[i] if friction else o.get('friction', _median(
                [p['friction'] for p in old], sf_cloth.NEW_PARTICLE['friction']))})
    # A mesh made by hand gets the values it went out with, to see and edit.
    for key, vals in (('mass', mass), ('radius', radius), ('friction', friction)):
        if vals is None:
            me.attributes.new('cloth_' + key, 'FLOAT', 'POINT')
            me.attributes['cloth_' + key].data.foreach_set('value',
                                                           [p[key] for p in particles])

    tris = []
    for poly in me.polygons:
        vs = list(poly.vertices)
        tris += [(vs[0], vs[k], vs[k + 1]) for k in range(1, len(vs) - 1)]

    edges = [tuple(e.vertices) for e in me.edges]
    if 'cloth_link' not in me.attributes:
        # A mesh made by hand: every edge is a standard link, as you see it.
        me.attributes.new('cloth_link', 'INT', 'EDGE')
        me.attributes['cloth_link'].data.foreach_set('value', [1] * len(edges))
    link = _attr(me, 'cloth_link', len(edges))
    links = [(a, b, kind) for (a, b), v in zip(edges, link) for kind, bit in LINK_BITS.items()
             if v & bit]
    if 'cloth_bend' not in me.attributes:
        # A mesh made by hand: every edge two triangles share is a hinge.
        shared = {}
        for poly in me.polygons:
            for ek in poly.edge_keys:
                shared[ek] = shared.get(ek, 0) + 1
        me.attributes.new('cloth_bend', 'FLOAT', 'EDGE')
        me.attributes['cloth_bend'].data.foreach_set(
            'value', [sf_cloth.NEW_BEND if shared.get(e.key, 0) == 2 else 0.0
                      for e in me.edges])
    bend = _attr(me, 'cloth_bend', len(edges), default=0.0)
    hinges = {frozenset(e): k for e, k in zip(edges, bend) if k}

    local_ranges = []
    k = 1
    while f'cloth_range{k}_max' in me.attributes:
        maxd = _attr(me, f'cloth_range{k}_max', n)
        maxn = _attr(me, f'cloth_range{k}_max_normal', n, default=3.402820018375656e+38)
        minn = _attr(me, f'cloth_range{k}_min_normal', n, default=-3.402820018375656e+38)
        stiff = _attr(me, f'cloth_range{k}_stiffness', n)
        local_ranges.append({
            'name': obj.get(f'cloth_range{k}_name', ''),
            'stiffness': obj.get(f'cloth_range{k}_stiffness', 1.0),
            'shape': obj.get(f'cloth_range{k}_shape', 0),
            'normal': bool(obj.get(f'cloth_range{k}_normal', False)),
            'particles': {i: {'max': maxd[i], 'max_normal': maxn[i], 'min_normal': minn[i],
                              'stiffness': stiff[i] if stiff else None}
                          for i in range(n) if maxd[i] >= 0 and i not in pinned}})
        k += 1

    # Every other group is a bone, but the user's own '*' helpers (as with shape keys).
    bone_names = {g.index: g.name for g in obj.vertex_groups
                  if g.name != 'cloth_pinned' and not g.name.startswith(('*', PLANE_GROUP))}
    skin = [[(bone_names[g.group], g.weight) for g in v.groups
             if g.group in bone_names and g.weight > 0] for v in me.vertices]

    old_to_new = {ids[i]: i for i in range(n) if ids[i] >= 0}
    carried = []
    for cs in sim.carried:
        c = _remap_carried(cs, old_to_new)
        if c is None:
            log.warning(f"{who}: {cs.type_name} '{cs['name']}' dropped: a particle it uses "
                        f"was deleted")
        else:
            carried.append(c)
    masks = _attr(me, 'cloth_collision_mask', n)

    sim.positions, sim.particles, sim.triangles, sim.links = positions, particles, tris, links
    sim.pinned = sorted(pinned)
    sim.bend, sim.local_ranges, sim.skin, sim.carried = hinges, local_ranges, skin, carried
    sim.collision_masks = masks if masks is not None else [0] * n
    sim.mask_all = masks is None                      # collide with every collidable
    if 'cloth_driven_bones' in obj:
        sim.driven = [(b.strip(), None) for b in obj['cloth_driven_bones'].split(',')
                      if b.strip()]
    if obj.get('cloth_transfer_bone'):
        sim.transfer_bone = obj['cloth_transfer_bone']
    for prop, kind in (('cloth_link_stiffness', 'standard'),
                       ('cloth_stretch_stiffness', 'stretch')):
        if prop in obj:
            sim.link_stiffness[kind] = obj[prop]
        elif getattr(sim, 'is_new', False):
            obj[prop] = sim.link_stiffness[kind] = 1.0
    if 'cloth_stretch_slack' in obj:
        sim.stretch_slack = obj['cloth_stretch_slack']
    elif getattr(sim, 'is_new', False):
        obj['cloth_stretch_slack'] = sim.stretch_slack
    for key in list(sim.settings):
        if key in sf_cloth.DERIVED_SETTINGS:
            continue
        if 'cloth_' + key not in obj:
            if getattr(sim, 'is_new', False):
                v = sim.settings[key]
                obj['cloth_' + key] = list(v) if isinstance(v, tuple) else v
            continue
        v = obj['cloth_' + key]
        sim.settings[key] = tuple(v) if hasattr(v, '__len__') else v


def _shape_axis(obj, pts):
    """A capsule mesh's axis and a point on it: through its two poles (the vertices more than
    four edges meet at, as on imported capsules and UV spheres) if it has them, else along its
    longest direction through its centre."""
    valence = [0] * len(pts)
    for e in obj.data.edges:
        for v in e.vertices:
            valence[v] += 1
    poles = [i for i, k in enumerate(valence) if k > 4]
    if len(poles) == 2 and (pts[poles[1]] - pts[poles[0]]).length > 1e-9:
        return (pts[poles[1]] - pts[poles[0]]).normalized(), (pts[poles[0]] + pts[poles[1]]) / 2
    c = sum(pts, Vector()) / len(pts)
    cov = Matrix(((0.0,) * 3,) * 3)
    for p in pts:
        d = p - c
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    axis = Vector((1.0, 1.0, 1.0)).normalized()
    for _ in range(100):                       # power iteration: the largest eigenvector
        nxt = cov @ axis
        if nxt.length < 1e-12:
            break
        nxt.normalize()
        if (nxt - axis).length < 1e-10:
            axis = nxt
            break
        axis = nxt
    return axis, c


def _fit_shape(obj, cloth_obj, shape, s):
    """The collision shape the mesh `obj` is, as it stands -- where its vertices are, however
    they got there (moved, scaled, mirrored, transforms applied, edited) -- in model space,
    metres: a capsule's start, end and radius; a tapered capsule's small and big ends and radii;
    a sphere's centre and radius. A capsule's ends are one radius in from the mesh's extent along
    its axis; its radius is the furthest the vertices are from the axis."""
    m = _root_space(obj, cloth_obj)
    pts = [(m @ v.co) / s for v in obj.data.vertices]
    if not pts:
        raise sf_cloth.ClothEditError(f"{obj.name}: a collision shape with no vertices")
    if shape == 'sphere':
        lo = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
        hi = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
        c = (lo + hi) / 2
        return {'center': c, 'radius': max((p - c).length for p in pts)}
    axis, c = _shape_axis(obj, pts)
    ts = [(p - c).dot(axis) for p in pts]
    ds = [((p - c) - axis * t).length for p, t in zip(pts, ts)]
    tmin, tmax = min(ts), max(ts)
    mid = (tmin + tmax) / 2
    ra = max(d for d, t in zip(ds, ts) if t <= mid)
    rb = max(d for d, t in zip(ds, ts) if t >= mid)
    if shape == 'capsule':
        ra = rb = max(ra, rb)
    eps = 1e-4 * max(ra, rb, 1e-6)

    def end(r, lower):
        # A capped end is at its cap's widest ring -- where import draws it, however the mesh
        # has been scaled since; a flat end (a cylinder's) has nothing past that ring, and the
        # capsule's end goes one radius in from it.
        half = [(t, d) for t, d in zip(ts, ds) if (t <= mid if lower else t >= mid)]
        rings = [t for t, d in half if d >= r - eps]
        if rings:
            ring = max(rings) if lower else min(rings)
            if any((t < ring - eps) if lower else (t > ring + eps) for t, _d in half):
                return ring
        return (tmin + r) if lower else (tmax - r)
    lo, hi = end(ra, True), end(rb, False)
    if hi < lo:
        lo = hi = mid
    return {'a': c + axis * lo, 'b': c + axis * hi, 'ra': ra, 'rb': rb}


def _model_ends(col):
    """A collidable's shape in model space: as _fit_shape returns it."""
    T = Matrix(col.transform)
    p = col.params
    if col.shape == 'sphere':
        return {'center': T @ Vector(p['center']), 'radius': p['radius']}
    if col.shape == 'capsule':
        return {'a': T @ Vector(p['start']), 'b': T @ Vector(p['end']), 'ra': p['radius'],
                'rb': p['radius']}
    return {'a': T @ Vector(p['small']), 'b': T @ Vector(p['big']), 'ra': p['small_radius'],
            'rb': p['big_radius']}


def _shape_to(col, fit):
    """Put a fitted model-space shape into `col`, in its own frame -- unless it's where it was,
    when the exact values it had stay (the mesh is only accurate to float precision)."""
    T = Matrix(col.transform)
    Ti = T.inverted()
    was = _model_ends(col) if col.params else None
    if col.shape == 'sphere':
        if was and (fit['center'] - was['center']).length < 1e-5 and \
                abs(fit['radius'] - was['radius']) < 1e-5:
            return
        col.params = {'center': tuple(Ti @ fit['center']), 'radius': fit['radius']}
        return
    a, b, ra, rb = fit['a'], fit['b'], fit['ra'], fit['rb']
    if col.shape == 'tapered_capsule' and ra > rb:
        a, b, ra, rb = b, a, rb, ra                      # small end first
    if was:
        if col.shape == 'capsule' and (a - was['a']).length > (b - was['a']).length:
            a, b = b, a                                  # keep the ends the way round they were
        if (a - was['a']).length < 1e-5 and (b - was['b']).length < 1e-5 and \
                abs(ra - was['ra']) < 1e-5 and abs(rb - was['rb']) < 1e-5:
            return
    if col.shape == 'capsule':
        col.params = {'start': tuple(Ti @ a), 'end': tuple(Ti @ b), 'radius': ra}
    else:
        col.params = {'small': tuple(Ti @ a), 'big': tuple(Ti @ b), 'small_radius': ra,
                      'big_radius': rb}


def _new_collidable(obj, cloth_obj, s):
    """A collidable for a mesh the user added, with `cloth_shape` and `cloth_bone`: its shape
    read from the mesh, in model space."""
    shape = obj.get('cloth_shape')
    if shape not in ('capsule', 'tapered_capsule', 'sphere'):
        raise sf_cloth.ClothEditError(f"{obj.name}: no collision shape {shape}; use capsule, "
                                      f"tapered_capsule or sphere")
    bone = obj.get('cloth_bone', '')
    if not bone:
        raise sf_cloth.ClothEditError(f"{obj.name}: a new collision shape needs a cloth_bone")
    col = sf_cloth.Collidable(obj.name, shape, bone, [list(r) for r in Matrix.Identity(4)], {})
    _shape_to(col, _fit_shape(obj, cloth_obj, shape, s))
    return col


def _root_space(obj, cloth_obj):
    """`obj`'s matrix in the nif root's space, where the imported pictures' placements are."""
    root = cloth_obj.parent
    return (root.matrix_world.inverted() @ obj.matrix_world) if root else obj.matrix_world


def _planes_from_objects(sim_obj, plane_objs, cloth, cloth_obj, s, nif_name=str):
    """The bone planes the sim mesh's `plane:` groups name, each from its square: the plane
    through the square, kept to the side its face normal points, in the bone's space."""
    names = [b[0] for b in cloth.skeleton]
    binds = sf_cloth.bind_matrices(cloth.skeleton)
    me = sim_obj.data
    out = []
    for o in plane_objs:
        vg = sim_obj.vertex_groups.get(PLANE_GROUP + o.name)
        if vg is None:
            continue
        particles = sorted(v.index for v in me.vertices
                           if any(g.group == vg.index and g.weight > 0 for g in v.groups))
        if not particles:
            continue
        bone = nif_name(o['cloth_plane_bone'])
        if bone not in names:
            raise sf_cloth.ClothEditError(f"{o.name}: bone {bone} isn't in the cloth's skeleton")
        m = _root_space(o, cloth_obj)
        n_m = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
        p_m = m.translation / s
        B = Matrix(binds[names.index(bone)])
        Bi = B.inverted()
        n_b = (B.to_3x3().transposed() @ n_m).normalized()
        d = -n_b.dot(Bi @ p_m)
        out.append({'bone': bone, 'equation': (n_b.x, n_b.y, n_b.z, d),
                    'stiffness': o.get('cloth_plane_stiffness', 1.0), 'particles': particles,
                    'set': o.get('cloth_plane_set', '')})
    return out


def is_cloth_empty(obj):
    """A BSClothExtraData empty: one import made, or one the user added by that name."""
    return obj.type == 'EMPTY' and ('BSClothExtraData_Name' in obj
                                    or obj.name.startswith('BSClothExtraData'))


def _sim_objects(cloth_obj):
    """The sim meshes under a cloth empty: every mesh but collision shapes and plane squares."""
    return [o for o in cloth_obj.children if o.type == 'MESH' and not o.get('cloth_shape')
            and not o.get('cloth_plane_bone')]


def _skin_bones(sim):
    return {b for infl in sim.skin for b, w in infl if w > 0}


def _armature_bones(arma, cloth_obj, s, nif_name):
    """{bone: (parent or None, model-space matrix in metres)} for the armature's bones, in the
    nif root's space, as the sim mesh is."""
    root = cloth_obj.parent
    to_root = (root.matrix_world.inverted() if root else Matrix.Identity(4)) @ arma.matrix_world
    out = {}
    for b in arma.data.bones:
        loc, rot, _sc = (to_root @ BD.get_bone_global_xf(arma, b.name, 'SF', False)).decompose()
        m = Matrix.LocRotScale(loc / s, rot, None)
        out[nif_name(b.name)] = (nif_name(b.parent.name) if b.parent else None,
                                 [list(r) for r in m])
    return out


def _reference_bones(ref_skel):
    """{bone: (parent or None, model-space matrix in metres)} from the reference skeleton nif,
    which is in game units."""
    out = {}
    if ref_skel is None:
        return out
    for name, nd in ref_skel.nodes.items():
        g = nd.global_transform
        t = [x / HAVOC_SCALE_FACTOR for x in g.translation]
        r = [list(row) for row in g.rotation]
        out[name] = (nd.parent.name if nd.parent else None,
                     [r[i] + [t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]])
    return out


def _new_sim_defaults(o, sim, arma, ref_names, nif_name):
    """Fill in a new piece's driven bones and transfer bone, if the user hasn't, and show them
    on its mesh. Driven bones are the cloth's own: the armature's bones that aren't in the
    reference skeleton (no vanilla cloth drives one that is) and aren't face bones."""
    if 'cloth_driven_bones' not in o:
        if arma is None:
            raise sf_cloth.ClothEditError(f"{o.name}: a new cloth needs cloth_driven_bones, or "
                                          f"an armature to find them in")
        own = [nif_name(b.name) for b in arma.data.bones]
        sim.driven = [(b, None) for b in own
                      if b not in ref_names and not b.startswith('faceBone')]
        o['cloth_driven_bones'] = ','.join(b for b, _t in sim.driven)
    if not o.get('cloth_transfer_bone'):
        weight = {}
        for i, infl in enumerate(sim.skin):
            if not sim.particles[i]['mass'] or not sim.pinned:
                for b, w in infl:
                    weight[b] = weight.get(b, 0.0) + w
        sim.transfer_bone = max(weight, key=weight.get) if weight else None
        o['cloth_transfer_bone'] = sim.transfer_bone or ''


def model_from_pictures(cloth_obj, blob, scale, arma=None, ref_skel=None, nif_name=str):
    """The cloth model `blob` holds, as edited in Blender: each sim mesh and collision shape
    under `cloth_obj` says what its piece of cloth or collidable is now. With no blob, or for a
    mesh the user added, the piece is made from scratch: settings from vanilla's usual values,
    and (with no blob) the skeleton from `arma`, falling back on `ref_skel` for bones it lacks.
    `nif_name` turns a Blender bone name into the nif's (Head.C -> C_Head)."""
    cloth = sf_cloth.read_model(blob) if blob is not None else sf_cloth.Cloth()
    s = HAVOC_SCALE_FACTOR * scale
    planes = [o for o in cloth_obj.children if o.get('cloth_plane_bone') and o.type == 'MESH']
    ref = _reference_bones(ref_skel)
    pieces, used = [], set()
    for o in _sim_objects(cloth_obj):
        i = o.get('cloth_index')
        if (blob is not None and o.get(VIZ_PROP) and 'cloth_sim' in o and i is not None
                and i < len(cloth.sims) and i not in used):
            used.add(i)
            sim = cloth.sims[i]
        else:
            sim = sf_cloth.SimCloth('Simulation Cloth')
            sim.is_new = True
            sim.cloth_data = o.name.split('.')[0].removeprefix('Cloth:')
            sim.settings = dict(sf_cloth.NEW_SETTINGS)
            cloth.sims.append(sim)
        _sim_from_mesh(o, sim, s)
        sim.skin = [[(nif_name(b), w) for b, w in infl] for infl in sim.skin]
        sim.driven = [(nif_name(b), t) for b, t in sim.driven]
        if sim.transfer_bone:
            sim.transfer_bone = nif_name(sim.transfer_bone)
        if getattr(sim, 'is_new', False):
            _new_sim_defaults(o, sim, arma, ref, nif_name)
        pieces.append((o, sim))
    if not cloth.sims:
        raise sf_cloth.ClothEditError(f"{cloth_obj.name} has no sim mesh under it")

    # Collision shapes: an imported one keeps its place; a copy of one, or a new mesh with
    # cloth_shape, is added; one deleted is gone.
    old = cloth.collidables
    kept, added, claimed = {}, [], set()
    for o in [o for o in cloth_obj.children if o.get('cloth_shape')]:
        i = o.get('cloth_index')
        if i is not None and i < len(old) and i not in claimed and 'cloth_params' in o:
            claimed.add(i)
            _shape_to(old[i], _fit_shape(o, cloth_obj, old[i].shape, s))
            old[i].name, old[i].bone = o.name.split('.')[0], o.get('cloth_bone', old[i].bone)
            kept[i] = old[i]
        elif i is not None and i < len(old) and 'cloth_params' in o:
            c = sf_cloth.Collidable(o.name, old[i].shape, o.get('cloth_bone', old[i].bone),
                                    old[i].transform, {})
            _shape_to(c, _fit_shape(o, cloth_obj, c.shape, s))
            added.append(c)
        else:
            added.append(_new_collidable(o, cloth_obj, s))
    new_list = [old[i] for i in sorted(kept)] + added
    new_index = {i: k for k, i in enumerate(sorted(kept))}
    for sim in cloth.sims:
        if getattr(sim, 'is_new', False):
            # A new piece collides with every shape, unless the user has set its masks.
            sim.collidable_ids = list(range(len(new_list)))
            if sim.mask_all:
                sim.collision_masks = [(1 << len(new_list)) - 1] * len(sim.positions)
            continue
        ids = [new_index[i] for i in sim.collidable_ids if i in new_index]
        bit_of = {b: ids.index(new_index[i]) for b, i in enumerate(sim.collidable_ids)
                  if i in new_index}
        extra = list(range(len(kept), len(new_list)))
        sim.collidable_ids = ids + extra
        masks = []
        for p, m in enumerate(sim.collision_masks):
            if getattr(sim, 'mask_all', False):
                m = (1 << len(sim.collidable_ids)) - 1
            else:
                m = sum(1 << bit_of[b] for b in range(32) if m >> b & 1 and b in bit_of)
                m |= sum(1 << (len(ids) + k) for k in range(len(extra)))
            masks.append(m)
        sim.collision_masks = masks
    cloth.collidables = new_list
    for c in new_list:
        c.bone = nif_name(c.bone)

    if not cloth.skeleton:
        # Made from scratch: the bones the cloth uses, and their ancestors up to Root.
        bones = dict(ref)
        if arma is not None:
            bones.update(_armature_bones(arma, cloth_obj, s, nif_name))
        needed = set()
        for sim in cloth.sims:
            needed |= _skin_bones(sim) | {b for b, _t in sim.driven}
            if sim.transfer_bone:
                needed.add(sim.transfer_bone)
        needed |= {c.bone for c in cloth.collidables}
        needed |= {nif_name(o['cloth_plane_bone']) for o in planes}
        cloth.skeleton = sf_cloth.skeleton_from(bones, needed)
    for o, sim in pieces:
        sim.planes = _planes_from_objects(o, planes, cloth, cloth_obj, s, nif_name)
    return cloth


def apply_edits(cloth_obj, blob, scale, arma=None, ref_skel=None, nif_name=str):
    """`blob` rebuilt from `cloth_obj`'s pictures: every export of a cloth with pictures goes
    through the builder, so what they show is what's written. With no blob, the cloth is made
    from scratch from its sim meshes. An edit that can't be built is logged and the blob
    returned as it was (None for a new cloth: it isn't written)."""
    from ..pyn import sf_cloth_build
    if blob is not None and not any(o.get(VIZ_PROP) for o in cloth_obj.children) \
            and not _sim_objects(cloth_obj):
        return blob
    try:
        return sf_cloth_build.build_cloth(
            model_from_pictures(cloth_obj, blob, scale, arma, ref_skel, nif_name))
    except (sf_cloth.ClothEditError, sf_cloth_build.ClothBuildError) as e:
        if blob is None:
            log.error(f"Cloth {cloth_obj.name} not written: {e}")
        else:
            log.error(f"Cloth edits not written, the cloth goes out as imported: {e}")
        return blob
