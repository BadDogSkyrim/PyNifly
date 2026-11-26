"""Fallout 4 cloth (BSClothExtraData, an hk_2014 packfile) as the cloth model sf_cloth defines,
so FO4 cloth is drawn, edited and rebuilt the way Starfield's is.

    read_model(blob)    the model: sf_cloth.Cloth with its sims, collidables and skeleton

Units are the file's: game units, as the nif. The graph comes from hk2014_graph; the formulas
here and in fo4_cloth_build were checked on the 146 vanilla nifs with cloth (2026-11-26; phase
7 notes):

- Each hclClothData is one piece: one hclSimClothData, its particles skinned to the skeleton by
  one or two object-space skin operators writing scratch buffers, which a copy or gather
  operator (or, on the lab coats, two gathers) takes to the sim buffer. Every particle's skin
  is found through those, so the builder can write the one plain graph vanilla mostly uses.
- Standard and bend links share one stiffness s per set, stored as s / (invMassA + invMassB);
  stretch links store theirs plainly, with rest length = distance * slack. Compressible links:
  compression length 0.95 * rest. Bend links: both lengths the distance.
- Volume sets: a set of particles, each weighted 1/N with its offset from their centre; the
  free ones are pulled back with a stiffness each.
- The cloth takes on some of the character's motion from one bone (transfer motion: COM in
  most vanilla pieces), which the Simulate state also reads.
"""
import struct

from . import sf_cloth
from .hk2014_graph import read_graph, walk
from .sf_cloth import Cloth, ClothEditError, Collidable, SimCloth

LINK_SETS = {'hclStandardLinkConstraintSet': 'standard',
             'hclStretchLinkConstraintSet': 'stretch',
             'hclCompressibleLinkConstraintSet': 'compressible',
             'hclBendLinkConstraintSet': 'bend_link'}
SHAPES = {'hclCapsuleShape': 'capsule', 'hclTaperedCapsuleShape': 'tapered_capsule'}
SKIN_OP = 'hclObjectSpaceSkinPNOperator'
BLEND_KINDS = {0: ('four', 4), 1: ('three', 3), 2: ('two', 2), 3: ('one', 1)}
COMPRESSION = 0.95             # compressible links: compression length / rest length

# Settings: model key -> (record, field). 'sim' = the hclSimClothData, 'op' = its simulate
# operator. Anything not here is worked out by the builder (fo4_cloth_build).
SETTINGS = {
    'gravity': ('sim', 'gravity'),
    'damping': ('sim', 'globalDampingPerSecond'),
    'transfer_motion': ('sim', 'transferMotionEnabled'),
    'landscape_collision': ('sim', 'landscapeCollisionEnabled'),
    'landscape': ('sim', 'landscape'),
    'pinch_detection': ('sim', 'pinchDetectionEnabled'),
    'landscape_value': ('sim', 'landscapeValue'),
    'landscape_count': ('sim', 'landscapeCount'),
    # Transfer motion, named as Starfield's.
    'transfer_translation': ('sim', 'transferTranslationMotion'),
    'transfer_translation_min': ('sim', 'minTranslationBlend'),
    'transfer_translation_max': ('sim', 'maxTranslationBlend'),
    'transfer_translation_speeds': ('sim', ('minTranslationSpeed', 'maxTranslationSpeed')),
    'transfer_rotation': ('sim', 'transferRotationMotion'),
    'transfer_rotation_min': ('sim', 'minRotationBlend'),
    'transfer_rotation_max': ('sim', 'maxRotationBlend'),
    'transfer_rotation_speeds': ('sim', ('minRotationSpeed', 'maxRotationSpeed')),
    'sub_steps': ('op', 'subSteps'),
    'adapt_stiffness': ('op', 'adaptConstraintStiffness'),
}

# A cloth made from scratch: vanilla's most common values (fieldcensus, 185 pieces).
NEW_SETTINGS = {
    'gravity': (0.0, 0.0, -686.7),
    'damping': 0.9999,
    'transfer_motion': 1,
    'landscape_collision': 0,
    'landscape': (0.05, 0.0, 9.0, 0.0),
    'pinch_detection': 0,
    'landscape_value': 0.0,
    'landscape_count': 0,
    'transfer_translation': 1,
    'transfer_translation_min': 0.7,
    'transfer_translation_max': 0.7,
    'transfer_translation_speeds': (0.0, 10.0),
    'transfer_rotation': 1,
    'transfer_rotation_min': 0.0,
    'transfer_rotation_max': 0.5,
    'transfer_rotation_speeds': (60.0, 180.0),
    'sub_steps': 2,
    'adapt_stiffness': 1,
}
NEW_PARTICLE = {'mass': 0.1, 'radius': 1.0, 'friction': 0.3}
NEW_BEND = 0.5


def _xyz(v):
    return tuple(v[:3])


def _rows(m):
    """A column-major mat4 as row-major nested lists. The rotation columns' w is junk in
    vanilla (collidable transforms carry -1 there), so the last row is always 0 0 0 1."""
    return [[m[4 * c + r] for c in range(4)] for r in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _skeleton(sk):
    return [(b['name'], p, (_xyz(q['translation']), tuple(q['rotation']), _xyz(q['scale'])))
            for b, p, q in zip(sk['bones'], sk['parentIndices'], sk['referencePose'])]


def _unpack(q):
    """An hkPackedVector3's value: (int16 << 16) * float(bits = word << 16)."""
    sc = struct.unpack('<f', struct.pack('<I', (q[3] & 0xFFFF) << 16))[0]
    return tuple((v << 16) * sc for v in q[:3])


def _skin_op(op, bones, normals):
    """{scratch vertex: [(bone, weight)]} from an object-space skin operator; each vertex's
    rest normal into `normals`."""
    subset = op['transformSubset']
    used, out = {}, {}
    for j, cb in enumerate(op['controlBytes']):
        kind, n = BLEND_KINDS[cb]
        block = op[kind + 'BlendEntries'][used.get(kind, 0)]
        used[kind] = used.get(kind, 0) + 1
        bi = block['boneIndices']
        ws = [w / 255.0 for w in block['boneWeights']] if n > 1 else [1.0] * 16
        for k, v in enumerate(block['vertexIndices']):
            if v in out or not op['startVertexIndex'] <= v <= op['endVertexIndex']:
                continue                    # a short block repeats its last vertex
            infl = [(bones[subset[bi[k * n + i]]], ws[k * n + i]) for i in range(n)]
            out[v] = [(b, w) for b, w in infl if w > 0]
            normals[v] = _unpack(op['localPNs'][j]['localNormal'][4 * k:4 * k + 4])
    return out


def _particle_sources(data, n):
    """For each particle, (buffer, vertex) it's gathered from in the Animate state: the copy
    and gather operators that fill the sim buffer from the scratch buffers."""
    ops = data['operators']
    sim_buf = next(k for k, b in enumerate(data['bufferDefinitions'])
                   if b.type_name == 'hclBufferDefinition')
    animate = next((s for s in data['clothStateDatas'] if s['name'] == 'Animate'),
                   data['clothStateDatas'][-1])
    src = [None] * n
    for i in animate['operators']:
        op = ops[i]
        t = op.type_name
        if t == 'hclCopyVerticesOperator' and op['outputBufferIdx'] == sim_buf:
            for k in range(op['numberOfVertices']):
                p = op['startVertexOut'] + k
                if p < n:
                    src[p] = (op['inputBufferIdx'], op['startVertexIn'] + k)
        elif t == 'hclGatherAllVerticesOperator' and op['outputBufferIdx'] == sim_buf:
            for p, v in enumerate(op['vertexInputFromVertexOutput'][:n]):
                if v >= 0:
                    src[p] = (op['inputBufferIdx'], v)
        elif t == 'hclGatherSomeVerticesOperator' and op['outputBufferIdx'] == sim_buf:
            for pr in op['vertexPairs']:
                if pr['indexOutput'] < n:
                    src[pr['indexOutput']] = (op['inputBufferIdx'], pr['indexInput'])
    return src


def _bits(bf):
    return {i for i in range(bf['numBits']) if bf['words'][i // 32] >> (i % 32) & 1}


def _reads(data, sd, bones, known, driven):
    """The bones both states read beyond what the builder works out (the skin, collidable and
    transfer bones): a few vanilla pieces read leg bones."""
    col_bones = {bones[i] for i in sd['transformIndices']}
    extra = {}
    for st in data['clothStateDatas']:
        ts = st['usedTransformSets']
        if not ts or not ts[0]['perComponentTransformTrackers']:
            continue
        read = {bones[i] for i in _bits(ts[0]['perComponentTransformTrackers'][0]['read'])}
        extra[st['name']] = read - known - col_bones - driven
    sim_x = extra.get('Simulate', set())
    return sorted(sim_x & extra.get('Animate', set()) if 'Animate' in extra else set())


def _links(sim, sets):
    """Links, link stiffness and slack from the sim's link sets."""
    inv = [p['invMass'] for p in sets['_particles']]
    for cs in sets['_all']:
        kind = LINK_SETS.get(cs.type_name)
        if kind is None:
            continue
        links = cs['links']
        sim.links += [(lk['particleA'], lk['particleB'], kind) for lk in links]
        if not links:
            continue
        if kind == 'stretch':
            sim.link_stiffness[kind] = links[0]['stiffness']
            ratios = sorted(lk['restLength'] / d for lk in links
                            if (d := sf_cloth.dist(sim.positions, lk['particleA'],
                                                   lk['particleB'])))
            sim.stretch_slack = ratios[len(ratios) // 2] if ratios else 1.0
            continue
        field = 'bendStiffness' if kind == 'bend_link' else 'stiffness'
        for lk in links:
            den = inv[lk['particleA']] + inv[lk['particleB']]
            if den:
                # Stored as float32 s / den: round off the noise (vanilla s is 1 or 0.95).
                sim.link_stiffness[kind] = round(lk[field] * den, 6)
                break


def _bend(sim, cs, inv):
    for r in cs['links']:
        den = sum(r['weight' + c] ** 2 * inv[r['particle' + c]] for c in 'ABCD')
        if den:
            sim.bend[frozenset((r['particleC'], r['particleD']))] = -r['bendStiffness'] * den


def _local_range(cs):
    return {'name': cs['name'], 'stiffness': cs['stiffness'], 'shape': cs['shapeType'],
            'normal': bool(cs['applyNormalComponent']),
            'particles': {r['particleIndex']: {
                'max': r['maximumDistance'], 'max_normal': r['maxNormalDistance'],
                'min_normal': r['minNormalDistance'], 'stiffness': None}
                for r in cs['localConstraints']}}


def _volume(cs):
    """A volume set: {'name', 'particles': {particle: stiffness, or None for one it only
    weighs (a pinned one)}}."""
    parts = {}
    for b in cs['frameBatchDatas']:
        for p in b['particleIndex']:
            parts[p] = None
    for s in cs['frameSingleDatas']:
        parts[s['particleIndex']] = None
    for b in cs['applyBatchDatas']:
        for p, k in zip(b['particleIndex'], b['stiffness']):
            parts[p] = k
    for s in cs['applySingleDatas']:
        parts[s['particleIndex']] = s['stiffness']
    return {'name': cs['name'], 'particles': parts}


def _planes(sim, cs, bones):
    by_key = {}
    for bp in cs['bonePlanes']:
        eq = tuple(bp['planeEquationBone'])
        b = bp['transformIndex']
        key = (b, tuple(round(x, 6) for x in eq), round(bp['stiffness'], 6))
        if key not in by_key:
            by_key[key] = {'bone': bones[b] if 0 <= b < len(bones) else None, 'equation': eq,
                           'stiffness': bp['stiffness'], 'particles': [], 'set': cs['name']}
            sim.planes.append(by_key[key])
        by_key[key]['particles'].append(bp['particleIndex'])


# Constraint sets in the order the simulate operator runs them, by kind; the builder writes one
# set of each kind it has records for (local ranges numbered), in this order.
ORDER_KIND = {'hclStandardLinkConstraintSet': 'standard',
              'hclStretchLinkConstraintSet': 'stretch',
              'hclCompressibleLinkConstraintSet': 'compressible',
              'hclBendLinkConstraintSet': 'bend_link',
              'hclBendStiffnessConstraintSet': 'bend',
              'hclVolumeConstraintMx': 'volume',
              'hclBonePlanesConstraintSet': 'planes'}


def _read_piece(data, bones, cloth, seen_cols):
    sd = data['simClothDatas'][0]
    sim = SimCloth(sd['name'])
    sim.cloth_data = data['name']
    sim.graph = data
    sim.positions = [_xyz(p) for p in sd['simClothPoses'][0]['positions']]
    pd = sd['particleDatas']
    n = len(pd)
    sim.particles = [{k: p[k] for k in ('mass', 'radius', 'friction')} for p in pd]
    sim.pinned = list(sd['fixedParticles'])
    tri = sd['triangleIndices']
    sim.triangles = [tuple(tri[k:k + 3]) for k in range(0, len(tri) - 2, 3)]
    flips = sd['triangleFlips']
    sim.flips = [flips[k // 8] >> (k % 8) & 1 for k in range(len(sim.triangles))]
    sim.collision_masks = list(sd['staticCollisionMasks']) or [0] * n
    sim.pinch = [k for k, f in enumerate(sd['perParticlePinchDetectionEnabledFlags']) if f]

    ops = data['operators']
    simop = next(op for op in ops if op.type_name == 'hclSimulateOperator')
    rec = {'sim': sd, 'op': simop}
    def setting(k, r, f):
        if isinstance(f, tuple):
            return tuple(rec[r][x] for x in f)
        v = rec[r][f]
        return _xyz(v) if k == 'gravity' else tuple(v) if isinstance(v, list) else v
    sim.settings = {k: setting(k, r, f) for k, (r, f) in SETTINGS.items()}

    # Skin, through whichever copy or gather fills each particle.
    skins, normals = {}, {}
    for op in ops:
        if op.type_name == SKIN_OP:
            buf = op['outputBufferIndex']
            skins.setdefault(buf, {}).update(_skin_op(op, bones, normals.setdefault(buf, {})))
    src = _particle_sources(data, n)
    sim.skin = [skins.get(s[0], {}).get(s[1], []) if s else [] for s in src]
    sim.normals = [normals.get(s[0], {}).get(s[1], (0.0, 0.0, 1.0)) if s else (0.0, 0.0, 1.0)
                   for s in src]
    sim.buffer_name = next((b['name'] for b in data['bufferDefinitions']
                            if b.type_name == 'hclScratchBufferDefinition'), None)
    unskinned = [p for p, s in enumerate(sim.skin) if not s]
    if unskinned:
        raise ClothEditError(f"{sim.cloth_data}: particles {unskinned[:5]} have no skin")

    sim.driven = []
    for op in ops:
        if op.type_name == 'hclSimpleMeshBoneDeformOperator':
            sim.driven += [(bones[p['boneOffset'] // 64], p['triangleOffset'] // 6)
                           for p in op['triangleBonePairs']]

    # Constraint sets, and the order they run in.
    sets = sd['staticConstraintSets']
    sim.links, sim.link_stiffness, sim.bend = [], {}, {}
    sim.local_ranges, sim.volumes, sim.planes, sim.carried = [], [], [], []
    _links(sim, {'_all': sets, '_particles': pd})
    inv = [p['invMass'] for p in pd]
    kinds = []
    for cs in sets:
        t = cs.type_name
        if t == 'hclBendStiffnessConstraintSet':
            _bend(sim, cs, inv)
        elif t == 'hclLocalRangeConstraintSet':
            sim.local_ranges.append(_local_range(cs))
            kinds.append(f'local_range{len(sim.local_ranges)}')
            continue
        elif t == 'hclVolumeConstraintMx':
            sim.volumes.append(_volume(cs))
            kinds.append(f'volume{len(sim.volumes)}')
            continue
        elif t == 'hclBonePlanesConstraintSet':
            _planes(sim, cs, bones)
        elif t not in LINK_SETS:
            raise ClothEditError(f"{sim.cloth_data}: constraint set {t} isn't known")
        kinds.append(ORDER_KIND[t])
    sim.solve_order = [kinds[i] for i in simop['constraintExecution'] if 0 <= i < len(kinds)]

    skin_bones = {b for infl in sim.skin for b, _w in infl}
    ti = sd['transferTransformIndex']
    sim.transfer_bone = bones[ti] if 0 <= ti < len(bones) else None
    sim.extra_reads = _reads(data, sd, bones, skin_bones | {sim.transfer_bone},
                             {b for b, _t in sim.driven})

    # Collidables: the sim's, each a shape riding a bone. Pieces may share one.
    sim.collidable_ids = []
    sim.collidable_pinch = []
    for k, col in enumerate(sd['perInstanceCollidables']):
        if id(col) not in seen_cols:
            seen_cols[id(col)] = len(cloth.collidables)
            shape = col['shape']
            kind = SHAPES.get(shape.type_name)
            if kind is None:
                raise ClothEditError(f"collidable {col['name']}: shape {shape.type_name}")
            if kind == 'capsule':
                params = {'start': _xyz(shape['start']), 'end': _xyz(shape['end']),
                          'radius': shape['radius']}
            else:
                params = {'small': _xyz(shape['small']), 'big': _xyz(shape['big']),
                          'small_radius': shape['smallRadius'],
                          'big_radius': shape['bigRadius']}
            bi = sd['transformIndices'][k]
            c = Collidable(col['name'], kind, bones[bi], _rows(col['transform']), params)
            c.graph = col
            cloth.collidables.append(c)
        sim.collidable_ids.append(seen_cols[id(col)])
        pdat = sd['collidablePinchingDatas']
        pinch = dict(pdat[k]) if k < len(pdat) else None
        sim.collidable_pinch.append(pinch)
        c = cloth.collidables[seen_cols[id(col)]]
        if getattr(c, 'pinch', None) is None:
            c.pinch = pinch
    return sim


def read_model(blob):
    """The cloth model a BSClothExtraData blob holds."""
    root = read_graph(blob)
    nodes = walk(root)
    sk = next((o for o in nodes if o.type_name == 'hkaSkeleton'), None)
    if sk is None:
        raise ClothEditError("the cloth has no skeleton")
    cloth = Cloth()
    cloth.graph = root
    cloth.skeleton = _skeleton(sk)
    bones = [b[0] for b in cloth.skeleton]
    seen = {}
    for data in (o for o in nodes if o.type_name == 'hclClothData'):
        cloth.sims.append(_read_piece(data, bones, cloth, seen))
    return cloth


def model_differences(A, B):
    """What differs between two cloth models, as short labels: [] for the same cloth (to float
    precision; skin weights to the byte the file keeps them in)."""
    def close(a, b, tol=1e-4):
        if isinstance(a, (list, tuple)):
            return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
        if isinstance(a, float) or isinstance(b, float):
            return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
        return a == b
    out = []
    if not close(A.skeleton, B.skeleton, 1e-5):
        out.append('skeleton')
    for sa, sb in zip(A.sims, B.sims):
        for f in ('positions', 'pinned', 'triangles', 'collision_masks', 'flips', 'pinch',
                  'stretch_slack', 'transfer_bone', 'extra_reads', 'solve_order', 'settings',
                  'link_stiffness'):
            if not close(getattr(sa, f), getattr(sb, f)):
                out.append(f)
        if not close([[p[k] for k in sorted(p)] for p in sa.particles],
                     [[p[k] for k in sorted(p)] for p in sb.particles]):
            out.append('particles')
        # A link's two ends either way round (the builder puts a stretch link's pinned end
        # first).
        if {(frozenset(lk[:2]), lk[2]) for lk in sa.links} !=                 {(frozenset(lk[:2]), lk[2]) for lk in sb.links}:
            out.append('links')
        if sa.bend.keys() != sb.bend.keys() or \
                not all(close(sa.bend[k], sb.bend[k], 1e-3) for k in sa.bend):
            out.append('bend')
        if [sorted((b, round(w * 255)) for b, w in i) for i in sa.skin] != \
                [sorted((b, round(w * 255)) for b, w in i) for i in sb.skin]:
            out.append('skin')
        if not close(sa.normals, sb.normals, 2e-3):
            out.append('normals')
        if sorted(sa.driven) != sorted(sb.driven):
            out.append('driven')
        if [lr['particles'] for lr in sa.local_ranges] != \
                [lr['particles'] for lr in sb.local_ranges]:
            if not all(close([[r[k] for k in ('max', 'max_normal', 'min_normal')]
                              for _p, r in sorted(x['particles'].items())],
                             [[r[k] for k in ('max', 'max_normal', 'min_normal')]
                              for _p, r in sorted(y['particles'].items())])
                       for x, y in zip(sa.local_ranges, sb.local_ranges)):
                out.append('local ranges')
        if [sorted(v['particles']) for v in sa.volumes] != \
                [sorted(v['particles']) for v in sb.volumes]:
            out.append('volumes')
        if len(sa.planes) != len(sb.planes):
            out.append('planes')
    for ca, cb in zip(A.collidables, B.collidables):
        if (ca.bone, ca.shape) != (cb.bone, cb.shape) or not close(ca.transform, cb.transform) \
                or not all(close(ca.params[k], cb.params[k]) for k in ca.params):
            out.append(f'collidable {ca.name}')
    return out
