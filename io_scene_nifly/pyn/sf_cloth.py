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
from .havok_graph import Obj
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
        # Filled by read_model, for the builder (see _read_rest):
        self.skin = []                # per particle: [(bone name, weight)], weights sum to 1
        self.driven = []              # [(bone name, sim triangle index)] the cloth moves
        self.link_stiffness = {}      # link kind -> the stiffness all its links share
        self.stretch_slack = 1.0      # stretch rest length / rest distance
        self.bend = {}                # frozenset edge (C, D) -> its record's stiffness k
        self.local_ranges = []        # LocalRange sets: settings + {particle: limits}
        self.collision_masks = []     # per particle: bit k = collides with collidable k
        self.planes = []              # bone planes: see _read_planes
        self.carried = []             # constraint sets the builder copies (graph Obj)
        self.transfer_bone = None     # the bone whose motion the cloth takes on
        self.collidable_ids = []      # its collidables, as indices into Cloth.collidables
        self.graph = None             # its hclClothData (havok_graph.Obj)


class Collidable:
    """A collision shape: `transform` is its model-space matrix (4x4 rows, metres); `params` are
    in its own frame -- capsule start/end/radius, tapered capsule small/big/radii, sphere
    center/radius."""
    def __init__(self, name, shape, bone, transform, params):
        self.name, self.shape, self.bone = name, shape, bone
        self.transform, self.params = transform, params
        self.graph = None             # read_model: its hclCollidable (havok_graph.Obj)


class Cloth:
    def __init__(self):
        self.sims = []
        self.collidables = []
        self.skeleton = []            # read_model: [(name, parent index, (t, q, s))]
        self.graph = None             # read_model: the blob's root (havok_graph.Obj)


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

# A cloth made from scratch: the most common vanilla values (census of the 320 vanilla cloths,
# 2026-10-26).
NEW_SETTINGS = {
    'gravity': (0.0, 0.0, -9.81),
    'damping': 0.9,
    'transfer_translation': True,
    'transfer_translation_min': 0.6,
    'transfer_translation_max': 0.6,
    'transfer_translation_speeds': (0.0, 10.0),
    'transfer_rotation': True,
    'transfer_rotation_min': 0.0,
    'transfer_rotation_max': 0.6,
    'transfer_rotation_speeds': (30.0, 90.0),
    'sub_steps': 1,
    'iterations': 1,
}
NEW_PARTICLE = {'mass': 0.08, 'radius': 0.02, 'friction': 0.5}
NEW_BEND = 0.5                  # every hinge of a fresh mesh
NEW_CLOTH_NAME = 'Binary Data'  # the BSClothExtraData block, as all vanilla cloths name it


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
# Vanilla's stiffness varies record to record (painted in Havok's tools), so each hinge keeps
# its own k (SimCloth.bend, the edge attribute cloth_bend in Blender). A batch holds four records
# in parallel arrays.
BEND_SET = 'hclBendStiffnessConstraintSetMx'
BEND_FIELDS = ('weight', 'invMass', 'particle')


def _bend_denominator(r):
    return sum(r['weight' + c] ** 2 * r['invMass' + c] for c in 'ABCD')


def bend_records(positions, particles, triangles, k):
    """Bend-stiffness records for every edge two of `triangles` share, from the rest
    `positions`, so the cloth rests in its rest shape. `k` is one stiffness for every edge, or
    a dict {frozenset edge: stiffness}, where an edge left out (or 0) gets no record. Returns
    (records, largest h^2)."""
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
        kk = k.get(frozenset((c, d)), 0.0) if isinstance(k, dict) else k
        if not kk:
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
        r['bendStiffness'] = -kk / den
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
        poses = sd['simClothPoses'].list()
        if poses:
            sim.positions = [_xyz(p) for p in poses[0].get()['positions'].list()]
        sim.particles = [{k: p[k] for k in ('mass', 'radius', 'friction')}
                         for p in sd['particleDatas'].list()]
        sim.pinned = list(sd['fixedParticles'].list())
        tri = sd['triangleIndices'].list()
        sim.triangles = [tuple(tri[k:k + 3]) for k in range(0, len(tri) - 2, 3)]
        sim.links = _links(tf, sd['staticConstraintSets'].list())
        sim.settings = _settings(tf, sim)
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
            cloth.collidables.append(c)


# --- the rest of a cloth, for the builder ------------------------------------------------------
# Census of the 298 vanilla cloth nifs (2026-10-24): every particle is skinned to the skeleton
# by one skin operator -- bone space (hair) or object space (clothes) -- writing a scratch buffer;
# a copy operator (scratch vertex = particle) or a gather operator (a map) takes it to the
# particles. Blocks of a deformer come in the order its controlBytes give, each byte naming the
# kind (0 four-blend, 1 three, 2 two, 3 one) of the next block of that kind; localPNs has one
# entry per block, in the same order. A block's influences are vertex-major (vertex k's are
# k*n .. k*n+n-1), and a short block is padded by repeating its last vertex. Object space keeps
# weights as bytes summing to 255; bone space keeps each influence's weight as the w of its
# local position.
SKIN_OPS = {'hclBoneSpaceSkinPNOperator': 'boneSpaceDeformer',
            'hclObjectSpaceSkinPNOperator': 'objectSpaceDeformer'}
BLEND_KINDS = {0: ('four', 4), 1: ('three', 3), 2: ('two', 2), 3: ('one', 1)}
LOCAL_RANGE_SET = 'hclLocalRangeConstraintSet'
BONE_PLANES_SET = 'hclBonePlanesConstraintSet'
BUILT_SETS = set(LINK_SETS) | {BEND_SET, LOCAL_RANGE_SET, BONE_PLANES_SET}


def _skin(op, bones):
    """{scratch vertex: [(bone name, weight)]} from a skin operator."""
    d = op[SKIN_OPS[op.type_name]]
    subset = list(op['transformSubset'] or [])
    object_space = op.type_name == 'hclObjectSpaceSkinPNOperator'
    used, out = {}, {}
    for b, cb in enumerate(d['controlBytes'] or []):
        kind, n = BLEND_KINDS[cb]
        block = d[kind + 'BlendEntries'][used.get(kind, 0)]
        used[kind] = used.get(kind, 0) + 1
        bi = block['boneIndices']
        if object_space:
            ws = [w / 255.0 for w in block['boneWeights']] if n > 1 else [1.0] * len(bi)
        else:
            ws = [p[3] for p in op['localPNs'][b]['localPosition']]
        for k, v in enumerate(block['vertexIndices']):
            if v in out or not d['startVertexIndex'] <= v <= d['endVertexIndex']:
                continue
            infl = [(bones[subset[bi[k * n + j]]], ws[k * n + j]) for j in range(n)]
            out[v] = [(name, w) for name, w in infl if w > 0]
    return out


def _records(cs, fields, lanes=4):
    """A constraint set's records as dicts, batches unbatched: a batch's field 'xs' (or the
    plural `fields` gives) holds one value per lane."""
    out = list(cs['singles'] or []) if 'singles' in cs.value else []
    for b in (cs['batches'] or []) if 'batches' in cs.value else []:
        for lane in range(lanes):
            out.append({f: b[p][lane] for f, p in fields.items()})
    return out


STANDARD_BATCH = {'particleA': 'particlesA', 'particleB': 'particlesB',
                  'restLength': 'restLengths', 'stiffnessA': 'stiffnessesA',
                  'stiffnessB': 'stiffnessesB'}
STRETCH_BATCH = {'particleA': 'particlesA', 'particleB': 'particlesB',
                 'restLength': 'restLengths', 'stiffness': 'stiffnesses'}
BEND_BATCH = {**{f'{f}{c}': (f'{f}s{c}' if f != 'invMass' else f'invMasses{c}')
                 for f in BEND_FIELDS for c in 'ABCD'},
              'bendStiffness': 'bendStiffnesses', 'restCurvature': 'restCurvatures'}


def dist(positions, a, b):
    return sum((x - y) ** 2 for x, y in zip(positions[a], positions[b])) ** 0.5


def _read_rest(sim, data, bones):
    """Fill `sim`'s builder fields from its hclClothData graph `data`."""
    sim.graph = data
    sd = data['simClothDatas'][0]
    n = len(sim.particles)
    ops = list(data['operators'])
    gather = next((op for op in ops if op.type_name == 'hclGatherAllVerticesOperator'), None)
    vertex_of = list(gather['vertexInputFromVertexOutput'])[:n] if gather else list(range(n))
    skin_op = next((op for op in ops if op.type_name in SKIN_OPS), None)
    skin = _skin(skin_op, bones) if skin_op else {}
    sim.skin = [skin.get(vertex_of[p], []) for p in range(n)]

    sim.driven = []
    for op in ops:
        if op.type_name == 'hclSimpleMeshBoneDeformOperator':
            sim.driven += [(bones[p['boneOffset'] // 64], p['triangleOffset'] // 6)
                           for p in op['triangleBonePairs']]

    sim.collision_masks = list(sd['staticCollisionMasks'] or [0] * n)
    tmd = sd['transferMotionData']
    sim.transfer_bone = bones[tmd['transformIndex']]         if 0 <= tmd['transformIndex'] < len(bones) else None
    sim.carried, sim.local_ranges, sim.bend, sim.planes = [], [], {}, []
    for cs in sd['staticConstraintSets']:
        t = cs.type_name
        if t == 'hclStandardLinkConstraintSetMx':
            recs = _records(cs, STANDARD_BATCH)
            if recs:
                sim.link_stiffness['standard'] = recs[0]['stiffnessA'] - recs[0]['stiffnessB']
        elif t == 'hclStretchLinkConstraintSetMx':
            recs = _records(cs, STRETCH_BATCH)
            if recs:
                sim.link_stiffness['stretch'] = recs[0]['stiffness']
                ratios = sorted(r['restLength'] / d for r in recs
                                if (d := dist(sim.positions, r['particleA'], r['particleB'])))
                sim.stretch_slack = ratios[len(ratios) // 2] if ratios else 1.0
        elif t == BEND_SET:
            for r in _records(cs, BEND_BATCH):
                den = _bend_denominator(r)
                if den:
                    sim.bend[frozenset((r['particleC'], r['particleD']))] = \
                        -r['bendStiffness'] * den
        elif t == LOCAL_RANGE_SET:
            stiff = cs['localStiffnessConstraints']
            recs = list(stiff if stiff is not None else cs['localConstraints'] or [])
            sim.local_ranges.append({
                'name': cs['name'], 'stiffness': cs['stiffness'], 'shape': cs['shapeType'],
                'normal': cs['applyNormalComponent'],
                'particles': {r['particleIndex']: {
                    'max': r['maximumDistance'], 'max_normal': r['maxNormalDistance'],
                    'min_normal': r['minNormalDistance'],
                    'stiffness': r['stiffness'] if stiff is not None else None}
                    for r in recs}})
        elif t == BONE_PLANES_SET:
            _read_planes(sim, cs, bones)
        else:
            sim.carried.append(cs)


def _qs_matrix(t, q, s):
    """An hkQsTransform as a row-major 4x4."""
    x, y, z, w = q
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[i][j] * s[j] for j in range(3)] + [t[i]] for i in range(3)] + [[0, 0, 0, 1]]


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _matrix_qs(m):
    """A row-major 4x4 (rotation and uniform scale) as an hkQsTransform (t, q xyzw, s)."""
    sc = sum(sum(m[i][j] ** 2 for i in range(3)) ** 0.5 for j in range(3)) / 3
    r = [[m[i][j] / sc for j in range(3)] for i in range(3)]
    tr = r[0][0] + r[1][1] + r[2][2]
    if tr > 0:
        k = 2 * (tr + 1) ** 0.5
        q = ((r[2][1] - r[1][2]) / k, (r[0][2] - r[2][0]) / k, (r[1][0] - r[0][1]) / k, k / 4)
    elif r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        k = 2 * (1 + r[0][0] - r[1][1] - r[2][2]) ** 0.5
        q = (k / 4, (r[0][1] + r[1][0]) / k, (r[0][2] + r[2][0]) / k, (r[2][1] - r[1][2]) / k)
    elif r[1][1] > r[2][2]:
        k = 2 * (1 + r[1][1] - r[0][0] - r[2][2]) ** 0.5
        q = ((r[0][1] + r[1][0]) / k, k / 4, (r[1][2] + r[2][1]) / k, (r[0][2] - r[2][0]) / k)
    else:
        k = 2 * (1 + r[2][2] - r[0][0] - r[1][1]) ** 0.5
        q = ((r[0][2] + r[2][0]) / k, (r[1][2] + r[2][1]) / k, k / 4, (r[1][0] - r[0][1]) / k)
    return tuple(m[i][3] for i in range(3)), q, (sc, sc, sc)


def _invert_rigid(m):
    """The inverse of a rotation-and-uniform-scale row-major 4x4."""
    s2 = sum(m[i][0] ** 2 for i in range(3))
    r = [[m[j][i] / s2 for j in range(3)] for i in range(3)]
    t = [-sum(r[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [r[i] + [t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def skeleton_from(bones, needed, root='Root'):
    """A cloth skeleton, [(name, parent index, (t, q, s))], for a cloth made from scratch: the
    `needed` bones and their ancestors up to `root`, parents first. `bones` maps a bone's name
    to (its parent's name or None, its model-space matrix, row-major 4x4 in metres). Vanilla
    cloths carry anything from 2 bones to the authoring scene's whole skeleton, so the bones a
    cloth uses are enough."""
    keep = set()
    for b in needed:
        while b is not None and b not in keep:
            if b not in bones:
                raise ClothEditError(f"bone {b} isn't in the armature or the reference skeleton")
            keep.add(b)
            b = None if b == root else bones[b][0]
    order = []

    def place(b):
        if b in order:
            return
        p = bones[b][0]
        if p in keep and b != root:
            place(p)
        order.append(b)
    for b in sorted(keep):
        place(b)
    out = []
    for b in order:
        p = bones[b][0] if b != root else None
        pi = order.index(p) if p in keep else -1
        local = bones[b][1] if pi < 0 else matmul(_invert_rigid(bones[p][1]), bones[b][1])
        out.append((b, pi, _matrix_qs(local)))
    return out


def bind_matrices(skeleton):
    """Each bone's model-space bind matrix (row-major 4x4, metres), from the skeleton's
    reference pose composed down the hierarchy (parents come before children)."""
    out = []
    for _name, parent, pose in skeleton:
        m = _qs_matrix(*pose)
        out.append(matmul(out[parent], m) if parent >= 0 else m)
    return out


# --- bone planes -----------------------------------------------------------------------------
# hclBonePlanesConstraintSet: each record keeps one particle on one side of a plane riding one
# bone -- planeEquationBone (nx, ny, nz, d) in the bone's space, the particle kept where
# n.x + d >= 0, the side the normal points to (all 5,421 vanilla records are, at rest). Vanilla
# puts them on body bones: hair on the head, the ponytail on the neck, skirt flaps under the
# hips; the Starborn cape has one per particle.

def _read_planes(sim, cs, bones):
    """Add a bone-plane set's records to sim.planes, one entry per distinct plane: {'bone',
    'equation' (nx, ny, nz, d), 'stiffness', 'particles', 'set' (the set's name)}."""
    by_key = {}
    for bp in cs['bonePlanes'] or []:
        eq = tuple(bp['planeEquationBone'])
        b = bp['transformIndex']
        key = (b, tuple(round(x, 6) for x in eq), round(bp['stiffness'], 6))
        if key not in by_key:
            by_key[key] = {'bone': bones[b] if 0 <= b < len(bones) else None, 'equation': eq,
                           'stiffness': bp['stiffness'], 'particles': [], 'set': cs['name']}
            sim.planes.append(by_key[key])
        by_key[key]['particles'].append(bp['particleIndex'])


def read_model(blob):
    """read_cloth, plus everything else the builder needs: skin weights, driven bones, link
    stiffness, per-edge bend stiffness, local range sets, collision masks, the constraint sets
    it carries over, and the skeleton."""
    from .havok_graph import read_graph, walk
    cloth = read_cloth(blob)
    root = read_graph(blob)
    cloth.graph = root
    nodes = walk(root)
    sk = next((x for x in nodes if isinstance(x, Obj) and x.type_name == 'hkaSkeleton'), None)
    if sk is not None:
        names = [b['name'] for b in sk['bones']]
        parents = list(sk['parentIndices'])
        cloth.skeleton = [(nm, parents[i], (tuple(q['translation'][:3]),
                                             tuple(q['rotation']),
                                             tuple(q['scale'][:3])))
                          for i, (nm, q) in enumerate(zip(names, sk['referencePose']))]
    bones = [b[0] for b in cloth.skeleton]
    datas = [x for x in nodes if isinstance(x, Obj) and x.type_name == 'hclClothData']
    if [d['name'] for d in datas] != [s.cloth_data for s in cloth.sims]:
        raise ClothEditError("the cloth pieces don't line up between the readers")
    cols = []
    for sim, data in zip(cloth.sims, datas):
        _read_rest(sim, data, bones)
        for c in data['simClothDatas'][0]['perInstanceCollidables'] or []:
            if all(c is not x for x in cols):
                cols.append(c)
            sim.collidable_ids.append(next(k for k, x in enumerate(cols) if x is c))
    if len(cols) != len(cloth.collidables):
        raise ClothEditError("the collidables don't line up between the readers")
    for col, g in zip(cloth.collidables, cols):
        col.graph = g
    return cloth


class ClothEditError(Exception):
    """Cloth that can't be read or edited as asked."""


