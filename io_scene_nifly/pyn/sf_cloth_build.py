"""Build a Starfield cloth blob (BSClothExtraData) from a cloth model: what sf_cloth.read_model
returns, edited, or one made from scratch.

Every vanilla cloth is put together the same way (census of the 298 vanilla cloth nifs,
2026-10-24), so one builder covers hair, tails and skirts. Per piece of cloth, an hclClothData:

    simClothDatas[1]        the particles, sim triangles, constraint sets and collidables
    bufferDefinitions[2]    a scratch buffer and the sim buffer, a vertex per particle
    transformSetDefinitions[1]  the skeleton's bones
    operators               skin (skeleton -> scratch), move particles (pins the fixed ones),
                            simulate, bone deform (each driven bone follows a sim triangle),
                            copy (scratch -> sim buffer)
    clothStateDatas         "Simulate" = skin, move, simulate, deform;
                            "Animate"  = skin, copy, deform

and one hkaSkeleton for the blob. The cloth only moves bones; the nif's shapes are skinned to
them as usual.

The builder writes the plainest form vanilla uses: bone-space skinning (as vanilla hair has),
a straight copy between the buffers, links as singles. Constraint sets run in vanilla's order:
local range, bone planes, standard (and compressible) links, bend, stretch links, volume.
What the model doesn't describe -- names, the landscape-collision block, the simulate config's
flags -- comes from the piece's own hclClothData when it was read from a blob, else from
vanilla's values.
"""
import copy
import math
import struct

from . import sf_cloth
from .havok_graph import Arr, Obj, write_graph
from .havok_tagfile import Tagfile, TagfileError
from .havok_tagwrite import TagDoc
from .sf_cloth_types import TYPES

PACKED_UNIT = 12288                 # hkPackedVector3 exponent word for 2**-15: unit normals

# Each operator's use of the two buffers -- (buffer, per-component flags, triangles read) --
# and of the transform set, as every vanilla cloth has them.
SKIN_BUFFERS = [(0, [6, 6, 0, 0], False)]
MOVE_BUFFERS = [(0, [1, 0, 0, 0], False), (1, [2, 0, 0, 0], False)]
SIM_BUFFERS = [(1, [15, 6, 0, 0], False)]
DEFORM_BUFFERS = [(1, [1, 0, 0, 0], True)]
COPY_BUFFERS = [(0, [1, 1, 0, 0], False), (1, [6, 6, 0, 0], False)]

# Run order of constraint set kinds, as vanilla runs them.
RUN_ORDER = ['hclLocalRangeConstraintSet', 'hclBonePlanesConstraintSet',
             'hclStandardLinkConstraintSetMx', 'hclCompressibleLinkConstraintSetMx',
             'hclBendStiffnessConstraintSetMx', 'hclBendStiffnessConstraintSet',
             'hclStretchLinkConstraintSetMx', 'hclVolumeConstraintMx', 'hclVolumeConstraint']

DEFAULT_SIMULATION_INFO = {'gravity': [0.0, 0.0, -9.81, 1.0], 'globalDampingPerSecond': 0.8}
DEFAULT_TRANSFER = {'transformSetIndex': 0, 'transformIndex': 0,
                    'transferTranslationMotion': True, 'minTranslationSpeed': 0.0,
                    'maxTranslationSpeed': 10.0, 'minTranslationBlend': 0.6,
                    'maxTranslationBlend': 0.6, 'transferRotationMotion': True,
                    'minRotationSpeed': 30.0, 'maxRotationSpeed': 90.0,
                    'minRotationBlend': 0.0, 'maxRotationBlend': 0.6}
DEFAULT_LANDSCAPE = {'landscapeRadius': 0.05, 'enableStuckParticleDetection': False,
                     'stuckParticlesStretchFactorSq': 9.0, 'pinchDetectionEnabled': False,
                     'pinchDetectionPriority': 0, 'pinchDetectionRadius': 0.0,
                     'collisionTolerance': 0.2}
DEFAULT_CONFIG = {'name': 'Default Config', 'instanceCollidablesUsed': None, 'subSteps': 1,
                  'numberOfSolveIterations': 1, 'useAllInstanceCollidables': True,
                  'adaptConstraintStiffness': True}


class ClothBuildError(Exception):
    pass


class _Types:
    """Type signatures for the builder's objects, from the shipped type definitions."""
    def __init__(self, blob):
        self.tf, self.doc = Tagfile(blob), TagDoc(blob)
        self.by_name = {}
        for t in self.tf.types[1:]:
            if t.members or t.name not in self.by_name:
                self.by_name[t.name] = t

    def sig(self, t):
        return self.doc._signature(t.index)

    def cls(self, name):
        if name not in self.by_name:
            raise ClothBuildError(f"no type {name}")
        return self.sig(self.by_name[name])

    def member_type(self, cls, path):
        t = self.by_name[cls]
        for name in path:
            m = next((m for m in self.tf.all_members(t) if m[0] == name), None)
            if m is None:
                raise ClothBuildError(f"{t.name} has no member {name}")
            t = m[3]
        return t

    def members(self, cls):
        return [m[0] for m in self.tf.all_members(self.by_name[cls])]


T = None


def _types():
    global T
    if T is None:
        T = _Types(TYPES)
    return T


def obj(cls, **fields):
    """An object of class `cls`; every member must be given, but the reference count."""
    names = _types().members(cls)
    for k in ('sizeAndFlags', 'refCount'):
        if k in names:
            fields.setdefault(k, 0)
    missing = [n for n in names if n not in fields]
    extra = [k for k in fields if k not in names]
    if missing or extra:
        raise ClothBuildError(f"{cls}: missing {missing}, unknown {extra}")
    return Obj(_types().cls(cls), {n: fields[n] for n in names})


def arr(cls, path, items):
    """The array member `path` (a name, or a tuple of names down nested records) of `cls`
    holding `items`; None when there are none, as vanilla writes an empty array."""
    items = list(items)
    if not items:
        return None
    path = (path,) if isinstance(path, str) else path
    t = _types().member_type(cls, path)
    return Arr(_types().sig(_types().tf.subtype_of(t)), items)


def ptrs(cls, field, objs):
    return arr(cls, field, objs)


# --- small linear algebra (row-major 4x4 lists) ------------------------------------------------

def _inv(m):
    """Inverse of an affine 4x4 (any 3x3 part)."""
    a = [row[:3] for row in m[:3]]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
           - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-30:
        raise ClothBuildError("a matrix with no inverse (a degenerate sim triangle?)")
    inv = [[(a[(j + 1) % 3][(i + 1) % 3] * a[(j + 2) % 3][(i + 2) % 3]
             - a[(j + 1) % 3][(i + 2) % 3] * a[(j + 2) % 3][(i + 1) % 3]) / det
            for j in range(3)] for i in range(3)]
    t = [m[i][3] for i in range(3)]
    it = [-sum(inv[i][k] * t[k] for k in range(3)) for i in range(3)]
    return [inv[i] + [it[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _col_major(m, w_rot=0.0):
    """A row-major 4x4 as hkMatrix4's 16 floats, column by column."""
    out = []
    for c in range(4):
        out += [m[r][c] for r in range(3)] + [1.0 if c == 3 else w_rot]
    return out


def _apply(m, p):
    return [sum(m[i][k] * p[k] for k in range(3)) + m[i][3] for i in range(3)]


def _rot(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(v):
    ln = math.sqrt(sum(x * x for x in v))
    return [x / ln for x in v] if ln else [0.0, 0.0, 0.0]


# --- usage records ---------------------------------------------------------------------------

def _bits(bones, nb):
    words = [0] * ((nb + 31) // 32)
    for b in bones:
        words[b // 32] |= 1 << (b % 32)
    return {'storage': {'words': arr('hclTransformSetUsage::TransformTracker',
                                     ('read', 'storage', 'words'), words), 'numBits': nb}}


def _tracker(nb, read=(), written=(), read_before_write=None):
    rbw = read if read_before_write is None else read_before_write
    return {'read': _bits(read, nb), 'readBeforeWrite': _bits(rbw, nb),
            'written': _bits(written, nb)}


def _buffer_access(uses):
    return arr('hclOperator', 'usedBuffers',
               [{'bufferIndex': b, 'bufferUsage': {'perComponentFlags': list(f),
                                                    'trianglesRead': tr},
                 'shadowBufferIndex': b} for b, f, tr in uses])


def _transform_access(flags, trackers):
    """One transform set's use: per component (0 the transforms, 1 their inverse transposes),
    its flags and (read, written) bone sets."""
    if not any(flags):
        return None
    return {'flags': list(flags), 'trackers': trackers}


def _transform_arr(access, nb):
    if access is None:
        return None
    tr = [_tracker(nb, sorted(r), sorted(w), sorted(rbw)) for r, w, rbw in access['trackers']]
    return arr('hclOperator', 'usedTransformSets',
               [{'transformSetIndex': 0,
                 'transformSetUsage': {
                     'perComponentFlags': access['flags'],
                     'perComponentTransformTrackers': arr(
                         'hclTransformSetUsage', 'perComponentTransformTrackers', tr)}}])


def _merge_state(ops_uses, nb):
    """A cloth state's use of buffers and transforms: the OR of its operators', in order. A
    bone read counts as read-before-write unless an earlier operator wrote it."""
    bufs = {}
    for uses, _ta in ops_uses:
        for b, f, tr in uses:
            cur = bufs.setdefault(b, ([0, 0, 0, 0], False))
            bufs[b] = ([x | y for x, y in zip(cur[0], f)], cur[1] or tr)
    flags, sets = [0, 0], [[set(), set(), set()], [set(), set(), set()]]
    for _uses, ta in ops_uses:
        if ta is None:
            continue
        for c in range(2):
            flags[c] |= ta['flags'][c]
            r, w, _rbw = ta['trackers'][c]
            sets[c][2] |= set(r) - sets[c][1]
            sets[c][0] |= set(r)
            sets[c][1] |= set(w)
    access = _transform_access(flags, [tuple(s) for s in sets])
    return [(b, f, tr) for b, (f, tr) in sorted(bufs.items())], access


# --- the pieces ------------------------------------------------------------------------------

def _template(sim, path, default):
    """A plain sub-record from the piece's own blob, or vanilla's default."""
    v = sim.graph
    try:
        for k in path:
            v = v[k]
    except (TypeError, KeyError, IndexError):
        return copy.deepcopy(default)
    return copy.deepcopy(v) if v is not None else copy.deepcopy(default)


def _name(sim, path, default):
    v = _template(sim, path, None)
    return v if isinstance(v, str) else default


def _set_path(record, path, value):
    for k in path[:-1]:
        record = record[k]
    cur = record[path[-1]]
    if isinstance(cur, list):
        value = list(value)[:3] + cur[3:]
    record[path[-1]] = value


def _vertex_normals(positions, triangles):
    nrm = [[0.0, 0.0, 0.0] for _ in positions]
    for t in triangles:
        a, b, c = (positions[i] for i in t)
        n = _cross(_sub(b, a), _sub(c, a))
        for v in t:
            nrm[v] = [x + y for x, y in zip(nrm[v], n)]
    return [_norm(n) for n in nrm]


def _pack_normal(v):
    return {'values': [max(-32767, min(32767, round(x * 32768))) for x in v[:3]] + [PACKED_UNIT]}


def _skin_op(sim, bone_index, binds, nb, positions, normals):
    """hclBoneSpaceSkinPNOperator over every particle, from the model's skin weights."""
    n = len(positions)
    infl = []
    for p in range(n):
        ws = sorted(((w, b) for b, w in sim.skin[p] if w > 0), reverse=True)[:4] \
            if p < len(sim.skin) else []
        if not ws:
            raise ClothBuildError(f"{sim.cloth_data or sim.name}: particle {p} has no skin "
                                  f"weights")
        total = sum(w for w, _b in ws)
        infl.append([(bone_index(b), w / total) for w, b in ws])
    subset = sorted({b for i in infl for b, _w in i})
    sub_of = {b: k for k, b in enumerate(subset)}
    inv = {b: _inv(binds[b]) for b in subset}

    groups = {4: [], 2: [], 1: []}
    for p, i in enumerate(infl):
        groups[1 if len(i) == 1 else 2 if len(i) == 2 else 4].append(p)
    per_block = {4: 4, 2: 8, 1: 16}
    kind_name = {4: 'four', 2: 'two', 1: 'one'}
    control = {4: 0, 2: 2, 1: 3}
    blocks = {4: [], 2: [], 1: []}
    control_bytes, local_pns = [], []
    for nblend in (4, 2, 1):
        verts = groups[nblend]
        for start in range(0, len(verts), per_block[nblend]):
            vs = verts[start:start + per_block[nblend]]
            vs = vs + [vs[-1]] * (per_block[nblend] - len(vs))
            bone_idx, lpos, lnrm = [], [], []
            for v in vs:
                ws = infl[v] + [(infl[v][0][0], 0.0)] * (nblend - len(infl[v]))
                for b, w in ws:
                    bone_idx.append(sub_of[b])
                    lp = _apply(inv[b], positions[v])
                    ln = _rot(inv[b], normals[v])
                    lpos.append([x * w for x in lp] + [w])
                    lnrm.append(_pack_normal([x * w for x in ln]))
            cls = f'hclBoneSpaceDeformer::{kind_name[nblend].capitalize()}BlendEntryBlock'
            block = {'vertexIndices': vs, 'boneIndices': bone_idx}
            if 'padding' in _types().members(cls):
                block['padding'] = _padding(cls)
            blocks[nblend].append(block)
            control_bytes.append(control[nblend])
            local_pns.append({'localPosition': lpos, 'localNormal': lnrm})

    deformer = {f'{k}BlendEntries': arr('hclBoneSpaceDeformer', f'{k}BlendEntries',
                                        blocks[nb_] if nb_ else [])
                for k, nb_ in (('four', 4), ('three', 0), ('two', 2), ('one', 1))}
    deformer.update({'controlBytes': arr('hclBoneSpaceDeformer', 'controlBytes', control_bytes),
                     'startVertexIndex': 0, 'endVertexIndex': n - 1, 'partialWrite': False})
    return {'subset': subset, 'deformer': deformer,
            'localPNs': arr('hclBoneSpaceSkinPNOperator', 'localPNs', local_pns)}


def _padding(cls):
    """A zeroed value for a block's padding member, shaped as the type says."""
    t = _types().member_type(cls, ('padding',))
    fmt = _types().tf.format_of(t)
    return [0] * (fmt >> 8)


def _collidable(col, bone_index, binds):
    """hclCollidable for a model collidable, plus its (bone, offset) for the transform map."""
    tm = [list(r) for r in col.transform]
    p = col.params
    if col.shape == 'capsule':
        d = _sub(p['end'], p['start'])
        l2 = sum(x * x for x in d)
        shape = obj('hclCapsuleShape', type=0, start=list(p['start']) + [0.0],
                    end=list(p['end']) + [0.0], dir=_norm(d) + [0.0], radius=p['radius'],
                    capLenSqrdInv=1.0 / l2 if l2 else 0.0)
    elif col.shape == 'tapered_capsule':
        shape = obj('hclTaperedCapsuleShape', **_tapered(p))
    elif col.shape == 'sphere':
        shape = obj('hclSphereShape', type=0,
                    sphere={'pos': list(p['center']) + [p['radius']]})
    else:
        raise ClothBuildError(f"{col.name}: no collision shape {col.shape}")
    rec = copy.copy(col.graph.value) if col.graph is not None else {
        'linearVelocity': [0.0] * 4, 'angularVelocity': [0.0] * 4, 'userData': 0,
        'pinchDetectionRadius': 0.01, 'pinchDetectionPriority': 0,
        'pinchDetectionEnabled': False, 'virtualCollisionPointCollisionEnabled': False,
        'enabled': True}
    rec.pop('sizeAndFlags', None)
    rec.pop('refCount', None)
    rec.update(transform=_col_major(tm), shape=shape, name=col.name)
    b = bone_index(col.bone)
    return obj('hclCollidable', **rec), b, sf_cloth.matmul(_inv(binds[b]), tm)


def _tapered(p):
    """A tapered capsule's fields, every derived one recomputed from its ends and radii."""
    small, big = list(p['small']), list(p['big'])
    rs, rb = p['small_radius'], p['big_radius']
    axis = _sub(big, small)
    ln = math.sqrt(sum(x * x for x in axis))
    if ln == 0:
        raise ClothBuildError("a tapered capsule of zero length")
    u = [x / ln for x in axis]
    dr = rb - rs
    sin_t = dr / ln
    cos_t = math.sqrt(max(0.0, 1 - sin_t * sin_t))
    tan_t = sin_t / cos_t if cos_t else 0.0
    d = ln * rs / dr if dr else 0.0
    apex = [s - x * d for s, x in zip(small, u)]
    return {'type': 0, 'small': small + [0.0], 'big': big + [0.0], 'coneApex': apex + [0.0],
            'coneAxis': u + [0.0], 'lVec': [ln] * 4, 'dVec': [d] * 4,
            'tanThetaVecNeg': [-tan_t] * 4, 'smallRadius': rs, 'bigRadius': rb, 'l': ln, 'd': d,
            'cosTheta': cos_t, 'sinTheta': sin_t, 'tanTheta': tan_t, 'tanThetaSqr': tan_t * tan_t}


def _constraint_sets(sim, positions, particles, bone_index):
    """The piece's constraint sets, in run order: [(Obj, kind)]."""
    inv = [1.0 / p['mass'] if p['mass'] else 0.0 for p in particles]
    pinned = {i for i, p in enumerate(particles) if not p['mass']}
    out = []
    for k, lr in enumerate(sim.local_ranges):
        recs = []
        per_stiff = any(r['stiffness'] is not None for r in lr['particles'].values())
        for pidx in sorted(lr['particles']):
            r = lr['particles'][pidx]
            rec = {'particleIndex': pidx, 'referenceVertex': pidx, 'maximumDistance': r['max'],
                   'maxNormalDistance': r['max_normal'], 'minNormalDistance': r['min_normal']}
            if per_stiff:
                rec['stiffness'] = r['stiffness'] if r['stiffness'] is not None else 1.0
            recs.append(rec)
        field = 'localStiffnessConstraints' if per_stiff else 'localConstraints'
        other = 'localConstraints' if per_stiff else 'localStiffnessConstraints'
        out.append(obj('hclLocalRangeConstraintSet', name=lr['name'] or 'LocalRange',
                       constraintId={'value': 0}, type=0,
                       **{field: arr('hclLocalRangeConstraintSet', field, recs), other: None},
                       referenceMeshBufferIdx=0, stiffness=lr['stiffness'],
                       shapeType=lr['shape'], applyNormalComponent=lr['normal']))
    std = [(a, b) for a, b, kind in sim.links if kind == 'standard']
    if std:
        s = sim.link_stiffness.get('standard', 1.0)
        singles = []
        for a, b in std:
            wa, wb = inv[a], inv[b]
            if wa + wb == 0:
                continue                         # two pinned particles: nothing to hold
            singles.append({'restLength': sf_cloth._dist(positions, a, b),
                            'stiffnessA': s * wa / (wa + wb), 'stiffnessB': -s * wb / (wa + wb),
                            'particleA': a, 'particleB': b})
        out.append(obj('hclStandardLinkConstraintSetMx', name='standardLinks',
                       constraintId={'value': 0}, type=0, batches=None,
                       singles=arr('hclStandardLinkConstraintSetMx', 'singles', singles)))
    if sim.bend:
        recs, max_h2 = sf_cloth.bend_records(positions, particles, sim.triangles, sim.bend)
        if recs:
            out.append(obj('hclBendStiffnessConstraintSetMx', name='BendStiffness Constraint',
                           constraintId={'value': 0}, type=0, batches=None,
                           singles=arr('hclBendStiffnessConstraintSetMx', 'singles', recs),
                           maxRestPoseHeightSq=64.0 * max_h2, clampBendStiffness=True,
                           useRestPoseConfig=True))
    stretch = [(a, b) for a, b, kind in sim.links if kind == 'stretch']
    if stretch:
        s = sim.link_stiffness.get('stretch', 1.0)
        singles = []
        for a, b in stretch:
            if b in pinned and a not in pinned:
                a, b = b, a                      # a stretch link runs from its pinned end
            singles.append({'restLength': sf_cloth._dist(positions, a, b) * sim.stretch_slack,
                            'stiffness': s, 'particleA': a, 'particleB': b})
        out.append(obj('hclStretchLinkConstraintSetMx', name='stretchLinks',
                       constraintId={'value': 0}, type=0, batches=None,
                       singles=arr('hclStretchLinkConstraintSetMx', 'singles', singles)))
    planes = [{'planeEquationBone': list(p['equation']), 'particleIndex': i,
               'transformIndex': bone_index(p['bone']), 'stiffness': p['stiffness']}
              for p in sim.planes for i in p['particles']]
    if planes:
        name = next((p['set'] for p in sim.planes if p.get('set')), 'BoneGlobalPlane Constraint')
        out.append(obj('hclBonePlanesConstraintSet', name=name, constraintId={'value': 0},
                       type=0, bonePlanes=arr('hclBonePlanesConstraintSet', 'bonePlanes', planes),
                       transformSetIndex=0))
    out += list(sim.carried)
    out.sort(key=lambda o: RUN_ORDER.index(o.type_name) if o.type_name in RUN_ORDER
             else len(RUN_ORDER))
    built = []
    for k, cs in enumerate(out):
        if cs in sim.carried:
            cs = Obj(cs.type, dict(cs.value))   # a copy: its id is renumbered
        cs['constraintId'] = {'value': k}
        built.append(cs)
    return built


def _bone_planes_bones(sets):
    return {bp['transformIndex'] for cs in sets if cs.type_name == 'hclBonePlanesConstraintSet'
            for bp in cs['bonePlanes'] or []}


def _cloth_data(sim, cloth, bone_index, binds, nb, shared):
    who = sim.cloth_data or sim.name
    positions = [list(p) for p in sim.positions]
    particles = sim.particles
    n, nt = len(positions), len(sim.triangles)
    if n == 0:
        raise ClothBuildError(f"{who}: no particles")
    pinned = sorted(i for i, p in enumerate(particles) if not p['mass'])
    normals = _vertex_normals(positions, sim.triangles)

    # The simulated cloth.
    sd = {'name': sim.name or 'Simulation Cloth'}
    sd['simulationInfo'] = _template(sim, ('simClothDatas', 0, 'simulationInfo'),
                                     DEFAULT_SIMULATION_INFO)
    sd['transferMotionData'] = _template(sim, ('simClothDatas', 0, 'transferMotionData'),
                                         DEFAULT_TRANSFER)
    if sim.transfer_bone:
        sd['transferMotionData']['transformIndex'] = bone_index(sim.transfer_bone)
    config = None
    for op in (sim.graph['operators'] or []) if sim.graph is not None else []:
        if op.type_name == 'hclSimulateOperator' and op['simulateOpConfigs']:
            config = copy.deepcopy(op['simulateOpConfigs'][0])
    config = config or copy.deepcopy(DEFAULT_CONFIG)
    for key, (record, path) in sf_cloth.SETTINGS.items():
        if key in sf_cloth.DERIVED_SETTINGS or key not in sim.settings:
            continue
        target = sd if record == 'sim' else config
        if isinstance(path[0], tuple):
            for p, v in zip(path, sim.settings[key]):
                _set_path(target, p, v)
        else:
            _set_path(target, path, sim.settings[key])

    sets = _constraint_sets(sim, positions, particles, bone_index)
    cols = [cloth.collidables[k] for k in sim.collidable_ids]
    for k in sim.collidable_ids:          # one object per collidable, shared between pieces
        if k not in shared:
            shared[k] = _collidable(cloth.collidables[k], bone_index, binds)
    built_cols = [shared[k] for k in sim.collidable_ids]
    masks = list(sim.collision_masks) + [0] * (n - len(sim.collision_masks))
    all_bits = (1 << len(cols)) - 1 if cols else 0
    masks = [0 if i in pinned else (m & all_bits) for i, m in enumerate(masks[:n])]

    pose = obj('hclSimClothPose', name=_name(sim, ('simClothDatas', 0, 'simClothPoses', 0, 'name'),
                                              'DefaultClothPose'),
               positions=arr('hclSimClothPose', 'positions', [p + [1.0] for p in positions]))
    C = 'hclSimClothData'
    sd.update(
        particleDatas=arr(C, 'particleDatas', [
            {'mass': p['mass'], 'invMass': 1.0 / p['mass'] if p['mass'] else 0.0,
             'radius': p['radius'], 'friction': p['friction']} for p in particles]),
        fixedParticles=arr(C, 'fixedParticles', pinned),
        doNormals=True, simOpIds=arr(C, 'simOpIds', [2]),
        simClothPoses=arr(C, 'simClothPoses', [pose]),
        staticConstraintSets=arr(C, 'staticConstraintSets', sets),
        antiPinchConstraintSets=None,
        collidableTransformMap={
            'transformSetIndex': 0 if cols else -1,
            'transformIndices': arr('hclSimClothData::CollidableTransformMap', 'transformIndices',
                                    [b for _c, b, _o in built_cols]),
            'offsets': arr('hclSimClothData::CollidableTransformMap', 'offsets',
                           [_col_major(o) for _c, _b, o in built_cols])},
        perInstanceCollidables=arr(C, 'perInstanceCollidables', [c for c, _b, _o in built_cols]),
        maxParticleRadius=max(p['radius'] for p in particles),
        staticCollisionMasks=arr(C, 'staticCollisionMasks', masks),
        actions=None,
        totalMass=sum(p['mass'] for p in particles),
        transferMotionEnabled=_template(sim, ('simClothDatas', 0, 'transferMotionEnabled'), True),
        landscapeCollisionEnabled=False,
        landscapeCollisionData=_template(sim, ('simClothDatas', 0, 'landscapeCollisionData'),
                                         DEFAULT_LANDSCAPE),
        numLandscapeCollidableParticles=0,
        triangleIndices=arr(C, 'triangleIndices', [i for t in sim.triangles for i in t]),
        triangleFlips=arr(C, 'triangleFlips', [0] * ((nt + 7) // 8)),
        pinchDetectionEnabled=False,
        perParticlePinchDetectionEnabledFlags=arr(C, 'perParticlePinchDetectionEnabledFlags',
                                                  [False] * n),
        collidablePinchingDatas=arr(C, 'collidablePinchingDatas', [
            {'pinchDetectionEnabled': False, 'pinchDetectionPriority': 0,
             'pinchDetectionRadius': 0.01} for _c in cols]),
        minPinchedParticleIndex=0, maxPinchedParticleIndex=0, maxCollisionPairs=0,
        virtualCollisionPointsData={k: None if k not in ('numVCPoints', 'numLandscapeVCPoints')
                                    else 0
                                    for k in _types().members('hclVirtualCollisionPointsData')})
    sim_obj = obj(C, **sd)

    # Operators.
    skin = _skin_op(sim, bone_index, binds, nb, positions, normals)
    skin_ta = _transform_access([9, 0], [(skin['subset'], (), skin['subset']), ((), (), ())])
    col_bones = {b for _c, b, _o in built_cols}
    if sd['transferMotionEnabled']:
        col_bones.add(sd['transferMotionData']['transformIndex'])
    plane_bones = _bone_planes_bones(sets)
    sim_ta = _transform_access([9 if col_bones else 0, 9 if plane_bones else 0],
                               [(col_bones, (), col_bones), (plane_bones, (), plane_bones)])
    sim_buffers = list(SIM_BUFFERS)
    lrs = [cs for cs in sets if cs.type_name == 'hclLocalRangeConstraintSet']
    if lrs:
        normal = any(cs['applyNormalComponent'] for cs in lrs)
        sim_buffers = [(0, [1, 1 if normal else 0, 0, 0], False)] + sim_buffers

    driven = _driven(sim, bone_index, binds, positions)
    deform_ta = _transform_access([2, 0], [((), [b for b, _t, _l in driven], ()), ((), (), ())])
    names = {op.type_name: op['name'] for op in (sim.graph['operators'] if sim.graph else [])}
    ops_uses = [(SKIN_BUFFERS, skin_ta), (MOVE_BUFFERS, None), (sim_buffers, sim_ta),
                (DEFORM_BUFFERS, deform_ta), (COPY_BUFFERS, None)]

    def op(cls, k, **fields):
        uses, ta = ops_uses[k]
        return obj(cls, name=names.get(cls, fields.pop('default_name')), operatorID=k, type=0,
                   usedBuffers=_buffer_access(uses), usedTransformSets=_transform_arr(ta, nb),
                   **fields)

    exe = list(range(len(sets))) + [-1]
    config['constraintExecution'] = arr('hclSimulateOperator::Config', 'constraintExecution', exe)
    operators = [
        op('hclBoneSpaceSkinPNOperator', 0, default_name='Skin Simulation',
           transformSubset=arr('hclBoneSpaceSkinPNOperator', 'transformSubset', skin['subset']),
           outputBufferIndex=0, transformSetIndex=0, boneSpaceDeformer=skin['deformer'],
           localPNs=skin['localPNs'], localUnpackedPNs=None),
        op('hclMoveParticlesOperator', 1, default_name='Move Particles',
           vertexParticlePairs=arr('hclMoveParticlesOperator', 'vertexParticlePairs',
                                   [{'vertexIndex': p, 'particleIndex': p} for p in pinned]),
           simClothIndex=0, refBufferIdx=0),
        op('hclSimulateOperator', 2, default_name='Sim', simClothIndex=0,
           simulateOpConfigs=arr('hclSimulateOperator', 'simulateOpConfigs', [config])),
        op('hclSimpleMeshBoneDeformOperator', 3, default_name='Deform', inputBufferIdx=1,
           outputTransformSetIdx=0,
           triangleBonePairs=arr('hclSimpleMeshBoneDeformOperator', 'triangleBonePairs',
                                 [{'boneOffset': b * 64, 'triangleOffset': t * 6}
                                  for b, t, _l in driven]),
           localBoneTransforms=arr('hclSimpleMeshBoneDeformOperator', 'localBoneTransforms',
                                   [_col_major(m, w_rot=0.0) for _b, _t, m in driven])),
        op('hclCopyVerticesOperator', 4, default_name='VertGather Op', inputBufferIdx=0,
           outputBufferIdx=1, numberOfVertices=n, startVertexIn=0, startVertexOut=0,
           copyNormals=True),
    ]

    states = []
    for name, seq in (('Simulate', [0, 1, 2, 3]), ('Animate', [0, 4, 3])):
        bufs, ta = _merge_state([ops_uses[k] for k in seq], nb)
        states.append(obj('hclClothState', name=name,
                          operators=arr('hclClothState', 'operators', seq),
                          usedBuffers=_buffer_access(bufs),
                          usedTransformSets=_transform_arr(ta, nb),
                          usedSimCloths=arr('hclClothState', 'usedSimCloths', [0]),
                          dependencyGraph=_linear_graph(len(seq))))

    mesh_name = _name(sim, ('bufferDefinitions', 0, 'meshName'), 'Cloth_Sim')
    layout = _template(sim, ('bufferDefinitions', 0, 'bufferLayout'), None) or _layout()
    sim_layout = copy.deepcopy(layout)
    layout['triangleFormat'], sim_layout['triangleFormat'] = 2, 1
    buffers = [
        obj('hclScratchBufferDefinition', meshName=mesh_name, bufferName='Sim Scratch', type=6,
            subType=0, numVertices=n, numTriangles=0, bufferLayout=layout, triangleIndices=None,
            storeNormals=True, storeTangentsAndBiTangents=False),
        obj('hclBufferDefinition', meshName=mesh_name, bufferName='SimBuf', type=1, subType=0,
            numVertices=n, numTriangles=nt, bufferLayout=sim_layout)]
    tset = obj('hclTransformSetDefinition', name=_name(sim, ('transformSetDefinitions', 0, 'name'),
                                                        'Root Transforms'),
               type=1, numTransforms=nb)
    D = 'hclClothData'
    return obj(D, name=sim.cloth_data or 'Cloth',
               simClothDatas=arr(D, 'simClothDatas', [sim_obj]),
               bufferDefinitions=arr(D, 'bufferDefinitions', buffers),
               transformSetDefinitions=arr(D, 'transformSetDefinitions', [tset]),
               operators=arr(D, 'operators', operators),
               clothStateDatas=arr(D, 'clothStateDatas', states),
               stateTransitions=None, actions=None, generatedAtRuntime=False, targetPlatform=2)


def _layout():
    """The buffer layout every vanilla buffer has: positions and normals, 16 bytes each."""
    elems = [{'vectorConversion': 0, 'vectorSize': 16, 'slotId': 0, 'slotStart': 0},
             {'vectorConversion': 0, 'vectorSize': 16, 'slotId': 1, 'slotStart': 0},
             {'vectorConversion': 250, 'vectorSize': 0, 'slotId': 0, 'slotStart': 0},
             {'vectorConversion': 250, 'vectorSize': 0, 'slotId': 0, 'slotStart': 0}]
    slots = [{'flags': 1, 'stride': 16}, {'flags': 1, 'stride': 16},
             {'flags': 0, 'stride': 0}, {'flags': 0, 'stride': 0}]
    return {'elementsLayout': elems, 'slots': slots, 'numSlots': 2, 'triangleFormat': 2}


def _linear_graph(k):
    G = 'hclStateDependencyGraph'
    branch = {'branchId': 0, 'stateOperatorIndices': arr('hclStateDependencyGraph::Branch',
                                                          'stateOperatorIndices', range(k)),
              'parentBranches': None, 'childBranches': None}
    int_arr = _types().sig(_types().tf.subtype_of(_types().member_type(G, ('children',))))
    inner = _types().sig(_types().tf.subtype_of(_types().tf.types[
        _types().doc.find_type(int_arr)]))

    def ints(xs):
        return Arr(inner, list(xs)) if xs else None
    return obj(G, branches=arr(G, 'branches', [branch]), rootBranchIds=arr(G, 'rootBranchIds', [0]),
               children=Arr(int_arr, [ints([i + 1]) if i + 1 < k else None for i in range(k)]),
               parents=Arr(int_arr, [ints([i - 1]) if i else None for i in range(k)]),
               multiThreadable=False)


def _driven(sim, bone_index, binds, positions):
    """[(bone, triangle, local transform)]: each driven bone follows the sim triangle whose
    centre is nearest it, offset by L = inverse(F) * bind, where F's columns are the
    triangle's first two corners less its centre, their cross product (not normalised) and the
    centre."""
    out, seen = [], set()
    tris = [t for t in sim.triangles if len(set(t)) == 3]
    if not tris:
        raise ClothBuildError(f"{sim.cloth_data or sim.name}: no sim triangles to drive bones")
    for bone, _t in sim.driven:
        b = bone_index(bone)
        if b in seen:
            continue
        seen.add(b)
        bp = [binds[b][i][3] for i in range(3)]
        best = min(range(len(sim.triangles)), key=lambda k: (
            len(set(sim.triangles[k])) < 3,
            math.dist([sum(positions[v][i] for v in sim.triangles[k]) / 3 for i in range(3)], bp)))
        t = sim.triangles[best]
        c = [sum(positions[v][i] for v in t) / 3 for i in range(3)]
        e0, e1 = _sub(positions[t[0]], c), _sub(positions[t[1]], c)
        nrm = _cross(e0, e1)
        F = [[e0[i], e1[i], nrm[i], c[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]
        out.append((b, best, sf_cloth.matmul(_inv(F), binds[b])))
    return out


def _skeleton(cloth):
    S = 'hkaSkeleton'
    sk = cloth.skeleton
    name = 'Root'
    if cloth.graph is not None:
        for v in cloth.graph['namedVariants'] or []:
            if v['className'] == S:
                name = v['variant']['name']
    return obj(S, name=name,
               parentIndices=arr(S, 'parentIndices', [p for _n, p, _q in sk]),
               bones=arr(S, 'bones', [{'name': n, 'lockTranslation': False} for n, _p, _q in sk]),
               referencePose=arr(S, 'referencePose', [
                   {'translation': list(t) + [0.0], 'rotation': list(q), 'scale': list(s) + [0.0]}
                   for _n, _p, (t, q, s) in sk]),
               referenceFloats=None, floatSlots=None, localFrames=None, partitions=None)


def build_graph(cloth):
    """The cloth model as a tagfile graph: the hkRootLevelContainer."""
    if not cloth.skeleton:
        raise ClothBuildError("the cloth has no skeleton")
    names = [n for n, _p, _q in cloth.skeleton]
    index = {n: i for i, n in enumerate(names)}

    def bone_index(name):
        if name not in index:
            raise ClothBuildError(f"bone {name} isn't in the cloth's skeleton")
        return index[name]
    binds = sf_cloth.bind_matrices(cloth.skeleton)
    nb = len(names)
    shared = {}
    variants = [{'name': None, 'className': 'hclClothData',
                 'variant': _cloth_data(sim, cloth, bone_index, binds, nb, shared)}
                for sim in cloth.sims]
    variants.append({'name': None, 'className': 'hkaSkeleton', 'variant': _skeleton(cloth)})
    R = 'hkRootLevelContainer'
    return obj(R, namedVariants=arr(R, 'namedVariants', variants))


def build_cloth(cloth):
    """The cloth model as a BSClothExtraData blob."""
    donors = [TYPES]
    return write_graph(build_graph(cloth), donors)
