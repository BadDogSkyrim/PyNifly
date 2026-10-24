"""Starfield cloth (BSClothExtraData) as the parts Blender draws: per simulated cloth, its
particles, sim triangles and links; and the collision shapes the particles can't pass through.

The blob is a Havok tagfile (see havok_tagfile). Everything here is in Havok METRES, in the
character's model space, as the blob stores it; the importer converts to game units.

    hclClothData
      simClothDatas[]       hclSimClothData: one simulated cloth
        particleDatas       mass, invMass, radius, friction per particle
        fixedParticles      pinned particle indices (mass 0, driven by skinning, not simulated)
        simClothPoses[0]    hclSimClothPose.positions: rest position per particle
        triangleIndices     the sim mesh, three indices per triangle
        staticConstraintSets  standard / stretch link sets (batches of 4 + singles) and others
        perInstanceCollidables + collidableTransformMap: the collidables and the bone each follows
      operators[]           hclSimulateOperator carries the solver's sub-steps and iterations

Vanilla uses three collision shapes (census of 298 cloth nifs, 2026-10-23): hclCapsuleShape,
hclTaperedCapsuleShape (skirts) and hclSphereShape (the Aceles only).
"""
from .havok_tagfile import Tagfile

SHAPES = {'hclCapsuleShape': 'capsule', 'hclTaperedCapsuleShape': 'tapered_capsule',
          'hclSphereShape': 'sphere'}
LINK_SETS = {'hclStandardLinkConstraintSetMx': 'standard',
             'hclStretchLinkConstraintSetMx': 'stretch'}


class SimCloth:
    """One simulated cloth: rest positions (metres, model space), particle records, pinned
    indices, triangles, links as (a, b, kind), and its settings by friendly name."""
    def __init__(self, name):
        self.name = name
        self.cloth_data = ''          # the hclClothData (piece of cloth) it belongs to
        self.positions = []
        self.particles = []
        self.pinned = []
        self.triangles = []
        self.links = []
        self.settings = {}
        self._idx = None              # (item, element) of the hclSimClothData
        self._config = None           # (item, element) of its simulate operator's config
        self._particles = None        # item index of particleDatas
        self._singles = {}            # link kind -> item index of its first set's singles array
        self._bend = []               # item indices of its bend-stiffness sets


class Collidable:
    """A collision shape: `transform` is its model-space matrix (4x4 rows, metres); `params` are
    in its own frame -- capsule start/end/radius, tapered capsule small/big/radii, sphere
    center/radius."""
    def __init__(self, name, shape, bone, transform, params):
        self.name, self.shape, self.bone = name, shape, bone
        self.transform, self.params = transform, params
        self._shape = None            # item index of the shape


class Cloth:
    def __init__(self):
        self.sims = []
        self.collidables = []


def _type_name(tf, ref):
    t = tf.items[ref.idx][0]
    return t.name if t is not None else None


def _matrix(f):
    """A Havok 4x4 (hkMatrix4 / hkTransform: four columns of four floats; the rotation columns'
    w is garbage) as row-major nested lists."""
    m = [[f[4 * c + r] for c in range(4)] for r in range(3)]
    return m + [[0.0, 0.0, 0.0, 1.0]]


def _xyz(v):
    return tuple(v[:3])


def _links(tf, sets):
    out = []
    for ref in sets:
        kind = LINK_SETS.get(_type_name(tf, ref))
        if kind is None:
            continue
        cs = ref.get()
        for b in cs['batches'].list() if cs['batches'] is not None else []:
            out += [(a, bb, kind) for a, bb in zip(b['particlesA'], b['particlesB'])]
        for s in cs['singles'].list() if cs['singles'] is not None else []:
            out.append((s['particleA'], s['particleB'], kind))
    return out


def _shape_params(kind, s):
    if kind == 'capsule':
        return {'start': _xyz(s['start']), 'end': _xyz(s['end']), 'radius': s['radius']}
    if kind == 'tapered_capsule':
        return {'small': _xyz(s['small']), 'big': _xyz(s['big']),
                'small_radius': s['smallRadius'], 'big_radius': s['bigRadius']}
    if kind == 'sphere':
        p = s['sphere']['pos']
        return {'center': _xyz(p), 'radius': p[3]}
    return {}


# Each setting: (which record, member path). 'sim' = the hclSimClothData, 'config' = its simulate
# operator's config. A pair of paths is a (min, max) setting; a vector setting is the xyz of an
# hkVector4. total_mass is the sum of the particle masses, so it's read here but derived on write.
SETTINGS = {
    'gravity': ('sim', ('simulationInfo', 'gravity')),
    'damping': ('sim', ('simulationInfo', 'globalDampingPerSecond')),
    'total_mass': ('sim', ('totalMass',)),
    'transfer_translation': ('sim', ('transferMotionData', 'transferTranslationMotion')),
    'transfer_translation_min': ('sim', ('transferMotionData', 'minTranslationBlend')),
    'transfer_translation_max': ('sim', ('transferMotionData', 'maxTranslationBlend')),
    'transfer_translation_speeds': ('sim', (('transferMotionData', 'minTranslationSpeed'),
                                            ('transferMotionData', 'maxTranslationSpeed'))),
    'transfer_rotation': ('sim', ('transferMotionData', 'transferRotationMotion')),
    'transfer_rotation_min': ('sim', ('transferMotionData', 'minRotationBlend')),
    'transfer_rotation_max': ('sim', ('transferMotionData', 'maxRotationBlend')),
    'transfer_rotation_speeds': ('sim', (('transferMotionData', 'minRotationSpeed'),
                                         ('transferMotionData', 'maxRotationSpeed'))),
    'sub_steps': ('config', ('subSteps',)),
    'iterations': ('config', ('numberOfSolveIterations',)),
}
DERIVED_SETTINGS = {'total_mass'}


def _where(sim, record):
    return sim._idx if record == 'sim' else sim._config


def _get(tf, where, path):
    if isinstance(path[0], tuple):
        return tuple(_get(tf, where, p) for p in path)
    v = tf.get_at(where[0], where[1], path)
    return _xyz(v) if isinstance(v, list) else v


def _settings(tf, sim):
    out = {}
    for key, (record, path) in SETTINGS.items():
        where = _where(sim, record)
        if where is not None:
            out[key] = _get(tf, where, path)
    return out


# --- bend stiffness ----------------------------------------------------------------------------
# hclBendStiffnessConstraintSetMx: a spring at each edge two sim triangles share. Each record
# names the two "wing" particles A, B (the triangles' far corners) and the edge's C, D, and was
# worked out from vanilla's 3,256 records (2026-10-23):
#   weights   A, B = dB/(dA+dB), dA/(dA+dB)  (dA, dB: wing distances from the edge line)
#             C, D = -(1-t), -t              (t: where the wings' weighted point meets C-D)
#   h         = sum of weight * position     (zero when the two triangles lie flat)
#   restCurvature = -(h . n) / (dA * dB)     (n: unit normal of triangle A, C, D)
#   bendStiffness = -k / sum(weight^2 * invMass)   -- k from 0 to 1, as links split stiffness
#   the set's maxRestPoseHeightSq = 64 * the largest h^2.
# Vanilla's stiffness varies record to record (painted per vertex in Havok's tools); here one k
# covers the set. A batch holds four records in parallel arrays.
BEND_SET = 'hclBendStiffnessConstraintSetMx'
BEND_FIELDS = ('weight', 'invMass', 'particle')


def _bend_rows(tf, set_idx):
    """[(item, element, batch lane or None, record dict)] for every record in a bend set."""
    cs = tf.item(set_idx)
    rows = []
    if cs['singles'] is not None and cs['singles'].idx:
        idx = cs['singles'].idx
        rows += [(idx, k, None, r) for k, r in enumerate(cs['singles'].list())]
    if cs['batches'] is not None and cs['batches'].idx:
        idx = cs['batches'].idx
        for k, b in enumerate(cs['batches'].list()):
            for lane in range(4):
                r = {f'{f}{c}': b[f'{f}s{c}' if f != 'invMass' else f'invMasses{c}'][lane]
                     for f in BEND_FIELDS for c in 'ABCD'}
                r['bendStiffness'] = b['bendStiffnesses'][lane]
                r['restCurvature'] = b['restCurvatures'][lane]
                rows.append((idx, k, lane, r))
    return rows


def _bend_denominator(r):
    return sum(r['weight' + c] ** 2 * r['invMass' + c] for c in 'ABCD')


def _bend_stiffness(tf, sim):
    """The set's stiffness k (the median, since vanilla's varies by record), or 0 with no set."""
    ks = sorted(-r['bendStiffness'] * _bend_denominator(r)
                for idx in sim._bend for *_x, r in _bend_rows(tf, idx) if _bend_denominator(r))
    return ks[len(ks) // 2] if ks else 0.0


def _rewrite_bend(tf, sim, k, particles):
    """The sim's bend records with the particles' inverse masses as they now are, and stiffness
    k -- or, with k None, each record keeping its own k (vanilla's are painted per vertex)."""
    inv = [1.0 / p['mass'] if p['mass'] else 0.0 for p in particles]
    for set_idx in sim._bend:
        for idx, el, lane, r in _bend_rows(tf, set_idx):
            own = -r['bendStiffness'] * _bend_denominator(r)
            for c in 'ABCD':
                r['invMass' + c] = inv[r['particle' + c]]
            d = _bend_denominator(r)
            stiff = -(own if k is None else k) / d if d else 0.0
            if lane is None:
                for c in 'ABCD':
                    tf.set_at(idx, r['invMass' + c], el, ('invMass' + c,))
                tf.set_at(idx, stiff, el, ('bendStiffness',))
                continue
            for c in 'ABCD':
                v = tf.get_at(idx, el, ('invMasses' + c,))
                v[lane] = r['invMass' + c]
                tf.set_at(idx, v, el, ('invMasses' + c,))
            v = tf.get_at(idx, el, ('bendStiffnesses',))
            v[lane] = stiff
            tf.set_at(idx, v, el, ('bendStiffnesses',))


def bend_records(positions, particles, triangles, k):
    """Bend-stiffness records for every edge two of `triangles` share, from the rest
    `positions`, so the cloth rests in its rest shape. Returns (records, largest h^2)."""
    import math

    def sub(a, b):
        return [x - y for x, y in zip(a, b)]

    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    inv = [1.0 / p['mass'] if p['mass'] else 0.0 for p in particles]
    edges = {}
    for tri in triangles:
        if len(set(tri)) < 3:
            continue
        for j in range(3):
            edges.setdefault(tuple(sorted((tri[j], tri[(j + 1) % 3]))), []).append(tri[(j + 2) % 3])
    recs, max_h2 = [], 0.0
    for (c, d), wings in sorted(edges.items()):
        if len(wings) != 2:
            continue
        a, b = wings
        xa, xb, xc, xd = (positions[i] for i in (a, b, c, d))
        e = sub(xd, xc)
        le = math.sqrt(dot(e, e))
        if le == 0:
            continue
        da = math.sqrt(dot(cross(e, sub(xa, xc)), cross(e, sub(xa, xc)))) / le
        db = math.sqrt(dot(cross(e, sub(xb, xc)), cross(e, sub(xb, xc)))) / le
        if da == 0 or db == 0:
            continue
        wa, wb = db / (da + db), da / (da + db)
        p = [wa * u + wb * v for u, v in zip(xa, xb)]
        t = dot(sub(p, xc), e) / (le * le)
        w = (wa, wb, -(1 - t), -t)
        h = [sum(wi * x[i] for wi, x in zip(w, (xa, xb, xc, xd))) for i in range(3)]
        n = cross(e, sub(xa, xc))
        ln = math.sqrt(dot(n, n))
        curv = -dot(h, n) / ln / (da * db) if ln else 0.0
        r = {'weightA': w[0], 'weightB': w[1], 'weightC': w[2], 'weightD': w[3],
             'particleA': a, 'particleB': b, 'particleC': c, 'particleD': d,
             'invMassA': inv[a], 'invMassB': inv[b], 'invMassC': inv[c], 'invMassD': inv[d],
             'restCurvature': curv}
        den = _bend_denominator(r)
        if den == 0:
            continue                       # all four pinned: nothing to bend
        r['bendStiffness'] = -k / den
        recs.append(r)
        max_h2 = max(max_h2, dot(h, h))
    return recs, max_h2


def read_cloth(blob):
    """Decode a BSClothExtraData blob into a Cloth."""
    tf = Tagfile(blob)
    names = [t.name if t is not None else None for t, _f, _o, _c in tf.items]
    cloth = Cloth()

    bones = []
    if 'hkaSkeleton' in names:
        bones = [b['name'] for b in tf.item(names.index('hkaSkeleton'))['bones'].list()]

    seen = set()
    for idx, n in enumerate(names):
        if n == 'hclClothData':
            _read_cloth_data(tf, tf.item(idx), bones, cloth, seen)
    return cloth


def _read_cloth_data(tf, data, bones, cloth, seen):
    """One hclClothData -- a blob may hold several, one per piece of cloth (the pirate officer's
    lower half has six) -- into `cloth`. `seen` keeps collidables shared between pieces single."""
    configs = {}
    for ref in data['operators'].list():
        if _type_name(tf, ref) == 'hclSimulateOperator':
            op = ref.get()
            ref_cfg = op['simulateOpConfigs']
            if ref_cfg is not None and ref_cfg.idx:
                configs.setdefault(op['simClothIndex'], (ref_cfg.idx, 0))

    for i, ref in enumerate(data['simClothDatas'].list()):
        sd = ref.get()
        sim = SimCloth(sd['name'])
        sim.cloth_data = data['name']
        sim._idx, sim._config = (ref.idx, 0), configs.get(i)
        sim._particles = sd['particleDatas'].idx
        poses = sd['simClothPoses'].list()
        if poses:
            sim.positions = [_xyz(p) for p in poses[0].get()['positions'].list()]
        sim.particles = [{k: p[k] for k in ('mass', 'radius', 'friction')}
                         for p in sd['particleDatas'].list()]
        sim.pinned = list(sd['fixedParticles'].list())
        tri = sd['triangleIndices'].list()
        sim.triangles = [tuple(tri[k:k + 3]) for k in range(0, len(tri) - 2, 3)]
        sim.links = _links(tf, sd['staticConstraintSets'].list())
        for cref in sd['staticConstraintSets'].list():
            kind = LINK_SETS.get(_type_name(tf, cref))
            singles = cref.get()['singles'] if kind else None
            if kind and kind not in sim._singles and singles is not None and singles.idx:
                sim._singles[kind] = singles.idx
            if _type_name(tf, cref) == BEND_SET:
                sim._bend.append(cref.idx)
        sim.settings = _settings(tf, sim)
        sim.settings['bend_stiffness'] = _bend_stiffness(tf, sim)
        cloth.sims.append(sim)

        ctm = sd['collidableTransformMap']
        bone_idx = ctm['transformIndices'].list() if ctm['transformIndices'] is not None else []
        for k, cref in enumerate(sd['perInstanceCollidables'].list()
                                 if sd['perInstanceCollidables'] is not None else []):
            if cref.idx in seen:
                continue
            seen.add(cref.idx)
            col = cref.get()
            shape_ref = col['shape']
            kind = SHAPES.get(_type_name(tf, shape_ref), _type_name(tf, shape_ref))
            bi = bone_idx[k] if k < len(bone_idx) else None
            bone = bones[bi] if bi is not None and bi < len(bones) else None
            c = Collidable(col['name'], kind, bone, _matrix(col['transform']),
                           _shape_params(kind, shape_ref.get()))
            c._shape = shape_ref.idx
            cloth.collidables.append(c)


class ClothEditError(Exception):
    """An edit that can't be written in place: a count changed, or a field we don't write yet."""


def _differs(a, b):
    if isinstance(a, (tuple, list)):
        return len(a) != len(b) or any(_differs(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return abs(a - b) > 1e-7 * max(1.0, abs(a), abs(b))
    return a != b


def _put(tf, where, path, value):
    """Write `value` at `path`, keeping a vector's w and a (min, max) pair's layout."""
    if isinstance(path[0], tuple):
        for p, v in zip(path, value):
            _put(tf, where, p, v)
        return
    cur = tf.get_at(where[0], where[1], path)
    if isinstance(cur, list):
        value = list(value)[:3] + cur[3:]
    tf.set_at(where[0], value, where[1], path)


def write_cloth(blob, cloth):
    """`blob` with `cloth`'s values written back in place (cloth as read_cloth returned it, then
    edited). Only values that differ from the blob are written, so an unedited cloth comes back
    byte-identical; a derived field is recomputed only when what it derives from changed.

    Writable: the settings (but total_mass, which follows the masses), each particle's mass,
    radius and friction, and capsule / sphere parameters. Raises ClothEditError for anything
    that would change a count or size, or a field not written yet (rest positions, tapered
    capsules)."""
    tf = Tagfile(blob)
    orig = read_cloth(blob)
    if len(orig.sims) != len(cloth.sims) or len(orig.collidables) != len(cloth.collidables):
        raise ClothEditError("the number of cloth pieces or collidables changed")

    add_bend = []
    for si, (o, sim) in enumerate(zip(orig.sims, cloth.sims)):
        who = sim.cloth_data or sim.name
        if len(sim.particles) != len(o.particles):
            raise ClothEditError(f"{who}: {len(sim.particles)} particles, the blob has "
                                 f"{len(o.particles)}")
        if _differs(sim.positions, o.positions):
            raise ClothEditError(f"{who}: particle positions changed; they aren't written yet")
        for key, (record, path) in SETTINGS.items():
            if key in DERIVED_SETTINGS or key not in sim.settings or key not in o.settings:
                continue
            if _differs(sim.settings[key], o.settings[key]):
                _put(tf, _where(sim, record), path, sim.settings[key])

        mass_changed = radius_changed = False
        for k, (p, op) in enumerate(zip(sim.particles, o.particles)):
            if _differs(p['mass'], op['mass']):
                if (op['mass'] == 0) != (p['mass'] == 0):
                    raise ClothEditError(f"{who}: particle {k} would change between pinned "
                                         f"(mass 0) and free; pinning isn't written yet")
                tf.set_at(o._particles, p['mass'], k, ('mass',))
                tf.set_at(o._particles, 1.0 / p['mass'] if p['mass'] else 0.0, k, ('invMass',))
                mass_changed = True
            if _differs(p['radius'], op['radius']):
                tf.set_at(o._particles, p['radius'], k, ('radius',))
                radius_changed = True
            if _differs(p['friction'], op['friction']):
                tf.set_at(o._particles, p['friction'], k, ('friction',))
        if mass_changed:
            tf.set_at(o._idx[0], sum(p['mass'] for p in sim.particles), o._idx[1], ('totalMass',))
        if radius_changed:
            tf.set_at(o._idx[0], max(p['radius'] for p in sim.particles), o._idx[1],
                      ('maxParticleRadius',))
        k_new = sim.settings.get('bend_stiffness', 0.0)
        k_changed = _differs(k_new, o.settings.get('bend_stiffness', 0.0))
        if o._bend and (k_changed or mass_changed):
            _rewrite_bend(tf, o, k_new if k_changed else None, sim.particles)
        elif not o._bend and k_changed and k_new > 0:
            add_bend.append((si, k_new))          # a new set: structural, written last

    for o, col in zip(orig.collidables, cloth.collidables):
        if col.shape != o.shape:
            raise ClothEditError(f"{col.name}: shape changed from {o.shape} to {col.shape}")
        if not _differs(col.params, o.params):
            continue
        p = col.params
        if col.shape == 'capsule':
            start, end = list(p['start']), list(p['end'])
            d = [e - s for s, e in zip(start, end)]
            length2 = sum(x * x for x in d)
            _put(tf, (o._shape, 0), ('start',), start)
            _put(tf, (o._shape, 0), ('end',), end)
            _put(tf, (o._shape, 0), ('radius',), p['radius'])
            if length2 > 0:
                _put(tf, (o._shape, 0), ('dir',), [x / length2 ** 0.5 for x in d])
                _put(tf, (o._shape, 0), ('capLenSqrdInv',), 1.0 / length2)
        elif col.shape == 'sphere':
            tf.set_at(o._shape, list(p['center']) + [p['radius']], 0, ('sphere', 'pos'))
        else:
            raise ClothEditError(f"{col.name}: {col.shape} edits aren't written yet")
    out = tf.to_bytes()
    for si, k in add_bend:
        out = add_bend_constraints(out, si, k)
    return out


def link_record(kind, a, b, positions, particles, stiffness=1.0):
    """A new link between particles a and b, as its set's Single stores it. The rest length is
    their rest distance. A standard link splits its stiffness by the two particles' inverse
    masses -- stiffnessA = s*wA/(wA+wB), stiffnessB = -s*wB/(wA+wB) -- which is what vanilla's
    0.5/-0.5 (equal masses) and 0/-1 (A pinned) are."""
    pa, pb = positions[a], positions[b]
    rest = sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5
    if kind == 'stretch':
        return {'restLength': rest, 'stiffness': stiffness, 'particleA': a, 'particleB': b}
    wa, wb = (1.0 / p['mass'] if p['mass'] else 0.0 for p in (particles[a], particles[b]))
    if wa + wb == 0:
        raise ClothEditError(f"link {a}-{b} joins two pinned particles")
    return {'restLength': rest, 'stiffnessA': stiffness * wa / (wa + wb),
            'stiffnessB': -stiffness * wb / (wa + wb), 'particleA': a, 'particleB': b}


def add_links(blob, sim_index, pairs, kind='standard', stiffness=1.0):
    """`blob` with links between the particle `pairs` added to sim `sim_index`'s first set of
    `kind` links, as singles. The blob grows (Tagfile.append_to_array)."""
    if not pairs:
        return blob
    cloth = read_cloth(blob)
    sim = cloth.sims[sim_index]
    idx = sim._singles.get(kind)
    if idx is None:
        raise ClothEditError(f"{sim.cloth_data or sim.name} has no {kind} link set with singles "
                             f"to add to")
    n = len(sim.particles)
    have = {frozenset((a, b)) for a, b, k in sim.links if k == kind}
    recs = []
    for a, b in pairs:
        if not (0 <= a < n and 0 <= b < n) or a == b:
            raise ClothEditError(f"link {a}-{b}: no such pair of particles")
        if frozenset((a, b)) in have:
            continue
        have.add(frozenset((a, b)))
        recs.append(link_record(kind, a, b, sim.positions, sim.particles, stiffness))
    return Tagfile(blob).append_to_array(idx, recs) if recs else blob


def bend_links(positions, links, max_angle=30.0):
    """Links that resist bending: for each particle with two standard links running on in nearly
    the same line (within `max_angle` degrees), a link joining the two far ends, unless one is
    there already. On a strip that's each particle to the one two steps along its rail. Returns
    (a, c) pairs."""
    import math
    nbrs = {}
    for a, b, k in links:
        if k == 'standard':
            nbrs.setdefault(a, set()).add(b)
            nbrs.setdefault(b, set()).add(a)
    have = {frozenset((a, b)) for a, b, _k in links}
    cos_limit = math.cos(math.radians(180.0 - max_angle))
    out = []
    for b, ns in nbrs.items():
        ns = sorted(ns)
        for i, a in enumerate(ns):
            for c in ns[i + 1:]:
                u = [x - y for x, y in zip(positions[a], positions[b])]
                v = [x - y for x, y in zip(positions[c], positions[b])]
                lu, lv = math.sqrt(sum(x * x for x in u)), math.sqrt(sum(x * x for x in v))
                if lu == 0 or lv == 0:
                    continue
                if sum(x * y for x, y in zip(u, v)) / (lu * lv) <= cos_limit and \
                        frozenset((a, c)) not in have:
                    have.add(frozenset((a, c)))
                    out.append((a, c))
    return out


def add_bend_constraints(blob, sim_index, k):
    """`blob` with a bend-stiffness set of stiffness `k` (0 to 1) added to sim `sim_index`: a
    record at every edge two sim triangles share, resting in the rest shape.

    Starfield cloth that has no such set also lacks its Havok types, so they're copied in from
    the definitions in sf_cloth_types. The new set is added to the sim's constraint sets and to
    its simulate operator's run order, after the standard links and before the stretch links,
    as vanilla runs them."""
    import struct
    from .havok_tagwrite import TagDoc
    from .sf_cloth_types import TYPES

    cloth = read_cloth(blob)
    sim = cloth.sims[sim_index]
    who = sim.cloth_data or sim.name
    if sim._bend:
        raise ClothEditError(f"{who} already has a bend-stiffness set")
    recs, max_h2 = bend_records(sim.positions, sim.particles, sim.triangles, k)
    if not recs:
        raise ClothEditError(f"{who}: no edge is shared by two sim triangles")

    old = Tagfile(blob)
    sd = old.get_at(sim._idx[0], sim._idx[1])
    sets = sd['staticConstraintSets']
    ids = {}
    for ref in sets.list():
        ids[_type_name(old, ref)] = ref.get()['constraintId']['value']
    new_id = max(ids.values(), default=-1) + 1
    if sim._config is None:
        raise ClothEditError(f"{who} has no simulate operator config to run the set")
    exe_ref = old.get_at(sim._config[0], sim._config[1])['constraintExecution']

    doc, donor = TagDoc(blob), TagDoc(TYPES)
    src = next(t for t in range(1, len(donor.tna))
               if donor.type_name(t) == BEND_SET and not donor.tna[t][1])
    t_set = doc.copy_type(donor, src)
    tf = doc.tagfile()
    set_type = tf.types[t_set]
    mem = {m[0]: m for m in tf.all_members(set_type)}
    singles_arr = mem['singles'][3]
    single_t = next(v for n, v in singles_arr.templates if n == 'tT')

    size = tf.size_of(single_t)
    data = bytearray()
    for r in recs:
        elem = bytearray(size)
        tf._write(0, single_t, r, elem)
        data += elem
    singles_idx, _ = doc.add_item(single_t.index, bytes(data), len(recs), kind=0x20)
    name = b'BendStiffness Constraint\0'
    name_idx, _ = doc.add_item(doc.find_type(('char', ())), name, len(name), kind=0x20)

    obj = bytearray(tf.size_of(set_type))
    tf._write(0, set_type, {'constraintId': {'value': new_id}, 'type': 0,
                            'maxRestPoseHeightSq': 64.0 * max_h2,
                            'clampBendStiffness': True, 'useRestPoseConfig': True}, obj)
    struct.pack_into('<I', obj, mem['name'][2], name_idx)
    struct.pack_into('<I', obj, mem['singles'][2], singles_idx)
    set_idx, set_off = doc.add_item(t_set, bytes(obj), 1, kind=0x10)
    doc.add_patch(mem['name'][3].index, set_off + mem['name'][2])
    doc.add_patch(singles_arr.index, set_off + mem['singles'][2])

    # The sim's list of constraint sets: one pointer longer, each pointer listed in PTCH.
    flags, off, count = doc.items[sets.idx]
    elem_t = flags & 0xFFFFFF
    es = tf.size_of(tf.types[elem_t])
    ptrs = bytes(doc.data[off:off + count * es]) + set_idx.to_bytes(4, 'little') + bytes(es - 4)
    new_off = doc.relocate_item(sets.idx, ptrs, count + 1)      # moves the old pointers' PTCH
    doc.add_patch(elem_t, new_off + count * es)                  # and the new one

    # The run order: after the standard links, before the stretch links (ponytail: 3 0 2 1 -1).
    order = list(exe_ref.list())
    stretch = ids.get('hclStretchLinkConstraintSetMx')
    at = order.index(stretch) if stretch in order else (order.index(-1) if -1 in order
                                                           else len(order))
    order.insert(at, new_id)
    doc.relocate_item(exe_ref.idx, struct.pack(f'<{len(order)}i', *order), len(order))
    return doc.to_bytes()
