"""Build a Fallout 4 cloth blob (BSClothExtraData, an hk_2014 packfile) from a cloth model:
what fo4_cloth.read_model returns, edited, or one made from scratch.

Each piece of cloth is the graph 183 of vanilla's 185 pieces have:

    simClothDatas[1]        particles, sim triangles, constraint sets, collidables, pose
    bufferDefinitions[2]    a scratch buffer and the sim buffer ("SimBuf"), a vertex per particle
    transformSetDefinitions[1]  the skeleton's bones
    operators               0 skin (skeleton -> scratch, object space), 1 move particles (the
                            pinned ones), 2 simulate, 3 bone deform (each driven bone follows a
                            sim triangle), 4 copy (scratch -> sim buffer)
    clothStateDatas         "Simulate" = 0 1 2 3, "Animate" = 0 4 3

and one hkaSkeleton for the blob. Everything else in the file is worked out from the model by
the rules in the phase 7 notes, each checked on the vanilla files: link lengths and
stiffnesses, bend weights and curvature, the skin blocks and packed positions, bone-deform
transforms, capsule fields, volume frames, buffer usage, transform trackers, masses and
counts. The cloth only moves bones; the nif's shapes are skinned to them as usual.
"""
import math
import struct

from . import sf_cloth
from .hk2014_graph import Obj, write_graph
from .sf_cloth_build import _col_major, _cross, _inv, _norm, _sub, _tapered

FLT_MAX = 3.4028234663852886e+38
COLLISION_TOLERANCE = struct.unpack('<f', bytes.fromhex('cbf85f41'))[0]  # 13.998 in every file
UNIT_EXP = 12288                    # packed-vector exponent word for 2**-31: unit normals
BUFFER_LAYOUT = {'elementsLayout': [0, 16, 0, 0, 0, 16, 1, 0, 250, 0, 0, 0, 250, 0, 0, 0],
                 'slots': [1, 16, 1, 16, 0, 0, 0, 0], 'numSlots': 2}
SET_NAMES = {'standard': 'Standard Links', 'stretch': 'Stretch Link',
             'compressible': 'Compressible Links', 'bend_link': 'Bend Links',
             'bend': 'Bend Stiffness', 'local_range': 'Local Range',
             'volume': 'Volume Constraint', 'planes': 'BoneGlobalPlane Constraint'}
# Constraint kinds in the order vanilla most often runs them, for a cloth without its own.
DEFAULT_ORDER = ['local_range', 'planes', 'standard', 'compressible', 'bend_link', 'bend',
                 'stretch', 'volume']


class ClothBuildError(Exception):
    pass


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _length(v):
    return math.sqrt(_dot(v, v))


# --- formulas -----------------------------------------------------------------------------------

def bend_record(P, a, b, c, d, inv, k):
    """An hclBendStiffnessConstraintSet link for the hinge on edge (c, d) with wings a and b:
    the weights of Volino and Magnenat-Thalmann, the curvature the rest shape has, and
    stiffness -k / sum(weight^2 * invMass). None if the hinge is degenerate or all pinned."""
    A, B, C, D = (P[i] for i in (a, b, c, d))
    n1 = _cross(_sub(A, C), _sub(A, D))
    n2 = _cross(_sub(B, D), _sub(B, C))
    n3 = _cross(_sub(C, B), _sub(C, A))
    n4 = _cross(_sub(D, A), _sub(D, B))
    l1, l2, l3, l4 = (_length(n) for n in (n1, n2, n3, n4))
    cd = _length(_sub(C, D))
    if not (l1 and l2 and l3 + l4 and cd):
        return None
    w = (l2 / (l1 + l2), l1 / (l1 + l2), -l4 / (l3 + l4), -l3 / (l3 + l4))
    h = [sum(wi * X[j] for wi, X in zip(w, (A, B, C, D))) for j in range(3)]
    n = _norm([n1[j] / l1 + n2[j] / l2 for j in range(3)])
    curv = -_dot(h, n) / ((l1 / cd) * (l2 / cd))
    den = sum(wi * wi * inv[p] for wi, p in zip(w, (a, b, c, d)))
    if not den:
        return None
    return {'weightA': w[0], 'weightB': w[1], 'weightC': w[2], 'weightD': w[3],
            'bendStiffness': -k / den, 'restCurvature': curv,
            'particleA': a, 'particleB': b, 'particleC': c, 'particleD': d}


def hinges(triangles):
    """{(c, d): [wing, wing]} for every edge two triangles share."""
    edges = {}
    for t in triangles:
        if len(set(t)) < 3:
            continue
        for j in range(3):
            edges.setdefault(tuple(sorted((t[j], t[(j + 1) % 3]))), []).append(t[(j + 2) % 3])
    return {e: w for e, w in edges.items() if len(w) == 2}


def vertex_normals(positions, triangles, flips):
    """Each vertex's normal: its triangles' normals weighted by the corner angle, a flipped
    triangle's turned over (the rule most vanilla cloth fits)."""
    acc = [[0.0, 0.0, 0.0] for _ in positions]
    for t, f in zip(triangles, flips):
        if len(set(t)) < 3:
            continue
        P = [positions[i] for i in t]
        n = _norm(_cross(_sub(P[1], P[0]), _sub(P[2], P[0])))
        if f:
            n = [-x for x in n]
        for i in range(3):
            u, v = _norm(_sub(P[(i + 1) % 3], P[i])), _norm(_sub(P[(i + 2) % 3], P[i]))
            a = math.acos(max(-1.0, min(1.0, _dot(u, v))))
            acc[t[i]] = [x + a * y for x, y in zip(acc[t[i]], n)]
    return [_norm(n) for n in acc]


def triangle_flips(positions, triangles, normals):
    """Each triangle's flip bit: set when it faces against its corners' normals."""
    out = []
    for t in triangles:
        P = [positions[i] for i in t]
        n = _cross(_sub(P[1], P[0]), _sub(P[2], P[0]))
        vn = [sum(normals[i][j] for i in t) for j in range(3)]
        out.append(1 if _dot(n, vn) < 0 else 0)
    return out


def _pack(v, unit=False):
    """An hkPackedVector3: int16 x, y, z and an exponent word; the value is
    (int16 << 16) * float(bits = word << 16). Positions take the smallest power-of-two scale
    that fits the largest component."""
    if unit:
        return [max(-32767, min(32767, round(x * 32768))) for x in v[:3]] + [UNIT_EXP]
    m = max(abs(x) for x in v[:3])
    k = math.ceil(math.log2(m / 32767)) - 16 if m > 0 else -31
    word = struct.unpack('<I', struct.pack('<f', 2.0 ** k))[0] >> 16
    sc = 2.0 ** (16 + k)
    return [max(-32768, min(32767, round(x / sc))) for x in v[:3]] + [word]


def _bytes_255(ws):
    """Weights as bytes summing to 255, the rounding put on the largest."""
    b = [round(w * 255) for w in ws]
    b[0] += 255 - sum(b)
    return b


# --- pieces -----------------------------------------------------------------------------------

def _skin(sim, bone_index, binds, normals):
    """hclObjectSpaceSkinPNOperator over every particle (scratch vertex = particle)."""
    n = len(sim.positions)
    infl = []
    for p in range(n):
        ws = sorted(((w, bone_index(b)) for b, w in sim.skin[p] if w > 0),
                    reverse=True)[:4] if p < len(sim.skin) else []
        if not ws:
            raise ClothBuildError(f"{sim.cloth_data}: particle {p} isn't skinned to any bone")
        tot = sum(w for w, _b in ws)
        infl.append([(w / tot, b) for w, b in ws])
    subset = sorted({b for i in infl for _w, b in i})
    sub_of = {b: k for k, b in enumerate(subset)}
    blocks = {4: [], 3: [], 2: [], 1: []}
    control, pns = [], []
    by_count = {}
    for p, i in enumerate(infl):
        by_count.setdefault(len(i), []).append(p)
    kind_byte = {4: 0, 3: 1, 2: 2, 1: 3}
    for cnt in (4, 3, 2, 1):
        verts = by_count.get(cnt, [])
        for s in range(0, len(verts), 16):
            vs = verts[s:s + 16]
            vs = vs + [vs[-1]] * (16 - len(vs))
            bi, bw = [], []
            for v in vs:
                bi += [sub_of[b] for _w, b in infl[v]]
                bw += _bytes_255([w for w, _b in infl[v]])
            blk = {'vertexIndices': vs, 'boneIndices': bi}
            if cnt > 1:
                blk['boneWeights'] = bw
            blocks[cnt].append(blk)
            control.append(kind_byte[cnt])
            pos, nrm = [], []
            for v in vs:
                pos += _pack(sim.positions[v])
                nrm += _pack(normals[v], unit=True)
            pns.append({'localPosition': pos, 'localNormal': nrm})
    return Obj('hclObjectSpaceSkinPNOperator', {
        'name': 'Skin Simulation', 'operatorID': 0,
        'boneFromSkinMeshTransforms': [tuple(_col_major(_inv(binds[b]))) for b in subset],
        'transformSubset': subset, 'outputBufferIndex': 0, 'transformSetIndex': 0,
        'fourBlendEntries': blocks[4], 'threeBlendEntries': blocks[3],
        'twoBlendEntries': blocks[2], 'oneBlendEntries': blocks[1],
        'controlBytes': control, 'startVertexIndex': 0, 'endVertexIndex': n - 1,
        'partialWrite': 0, 'skinFlags': 2, 'localPNs': pns, 'localUnpackedPNs': []}), subset


def _driven(sim, bone_index, binds):
    """[(bone, triangle, local transform)]: each driven bone follows a sim triangle -- its own
    if the model names one, else the one whose centre is nearest it -- offset by
    L = inverse(F) * bind, F's columns the triangle's first two corners less its centre, their
    cross product and the centre."""
    P = sim.positions
    tris = sim.triangles
    good = [k for k, t in enumerate(tris) if len(set(t)) == 3]
    if not good:
        raise ClothBuildError(f"{sim.cloth_data}: no sim triangles to drive bones")
    out, seen = [], set()
    for bone, t in sim.driven:
        b = bone_index(bone)
        if b in seen:
            continue
        seen.add(b)
        bp = [binds[b][i][3] for i in range(3)]
        if t is None or t >= len(tris) or len(set(tris[t])) < 3:
            t = min(good, key=lambda k: math.dist(
                [sum(P[v][i] for v in tris[k]) / 3 for i in range(3)], bp))
        tri = tris[t]
        c = [sum(P[v][i] for v in tri) / 3 for i in range(3)]
        e0, e1 = _sub(P[tri[0]], c), _sub(P[tri[1]], c)
        nrm = _cross(e0, e1)
        F = [[e0[i], e1[i], nrm[i], c[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]
        out.append((b, t, sf_cloth.matmul(_inv(F), binds[b])))
    return out


def _collidable(col, bone_index, binds):
    p = col.params
    if col.shape == 'capsule':
        d = _sub(p['end'], p['start'])
        l2 = _dot(d, d)
        shape = Obj('hclCapsuleShape', {
            'start': tuple(p['start']) + (0.0,), 'end': tuple(p['end']) + (0.0,),
            'dir': tuple(_norm(d)) + (0.0,), 'radius': p['radius'],
            'capLenSqrdInv': 1.0 / l2 if l2 else 0.0})
    elif col.shape == 'tapered_capsule':
        if abs(p['big_radius'] - p['small_radius']) < 1e-6:
            raise ClothBuildError(f"{col.name}: a tapered capsule's radii must differ")
        t = _tapered(p)
        t.pop('type')
        shape = Obj('hclTaperedCapsuleShape', {k: tuple(v) if isinstance(v, list) else v
                                               for k, v in t.items()})
    else:
        raise ClothBuildError(f"{col.name}: FO4 cloth has no {col.shape} shape")
    tm = [list(r) for r in col.transform]
    b = bone_index(col.bone)
    c = Obj('hclCollidable', {
        'name': col.name, 'transform': tuple(_col_major(tm)),
        'linearVelocity': (0.0,) * 4, 'angularVelocity': (0.0,) * 4, 'usingVelocities': 0,
        'pinchDetectionRadius': 0.01, 'shape': shape})
    return c, b, sf_cloth.matmul(_inv(binds[b]), tm)


def _links(sim, kind, inv, P):
    pairs = [(a, b) for a, b, k in sim.links if k == kind and a != b]
    s = sim.link_stiffness.get(kind, 1.0)
    out = []
    for a, b in pairs:
        d = math.dist(P[a], P[b])
        den = inv[a] + inv[b]
        if kind == 'stretch':
            if inv[a] and not inv[b]:
                a, b = b, a                     # A is the pinned end
            out.append({'particleA': a, 'particleB': b,
                        'restLength': d * sim.stretch_slack, 'stiffness': s})
        elif kind == 'compressible':
            out.append({'particleA': a, 'particleB': b, 'restLength': d,
                        'compressionLength': d * 0.95, 'stiffness': s / den if den else 0.0})
        elif kind == 'bend_link':
            out.append({'particleA': a, 'particleB': b, 'bendMinLength': d,
                        'stretchMaxLength': d, 'bendStiffness': s / den if den else 0.0,
                        'stretchStiffness': s / den if den else 0.0})
        else:
            out.append({'particleA': a, 'particleB': b, 'restLength': d,
                        'stiffness': s / den if den else 0.0})
    return out


def _volume(vol, P):
    parts = sorted(vol['particles'])
    if not parts:
        return None
    w = 1.0 / len(parts)
    c = [sum(P[p][i] for p in parts) * w for i in range(3)]

    def frame(p):
        return tuple(_sub(P[p], c)) + (0.0,)
    free = [(p, k) for p, k in sorted(vol['particles'].items()) if k is not None]

    def batches(items, last):
        full = len(items) // 16 * 16
        bs = [{'frameVector': [frame(p) for p, _x in items[s:s + 16]],
               'particleIndex': [p for p, _x in items[s:s + 16]],
               last: [x for _p, x in items[s:s + 16]]} for s in range(0, full, 16)]
        ss = [{'frameVector': frame(p), 'particleIndex': p, last: x} for p, x in items[full:]]
        return bs, ss
    fb, fs = batches([(p, w) for p in parts], 'weight')
    ab, as_ = batches(free, 'stiffness')
    return {'name': vol['name'] or SET_NAMES['volume'], 'frameBatchDatas': fb,
            'frameSingleDatas': fs, 'applyBatchDatas': ab, 'applySingleDatas': as_}


def _constraint_sets(sim, inv, bone_index):
    """{kind: [hcl set Obj]} for every kind the model has records for."""
    P = sim.positions
    sets = {}

    def add(kind, cls, value):
        value.setdefault('name', SET_NAMES[kind.rstrip('0123456789')])
        value.setdefault('constraintId', 0)
        sets[kind] = Obj(cls, value)
    for kind, cls in (('standard', 'hclStandardLinkConstraintSet'),
                      ('stretch', 'hclStretchLinkConstraintSet'),
                      ('compressible', 'hclCompressibleLinkConstraintSet'),
                      ('bend_link', 'hclBendLinkConstraintSet')):
        links = _links(sim, kind, inv, P)
        if links:
            add(kind, cls, {'links': links})
    recs = []
    for (c, d), (a, b) in sorted(hinges(sim.triangles).items()):
        k = sim.bend.get(frozenset((c, d)), 0.0)
        if k:
            r = bend_record(P, a, b, c, d, inv, k)
            if r is not None:
                recs.append(r)
    if recs:
        add('bend', 'hclBendStiffnessConstraintSet', {'links': recs, 'useRestPoseConfig': 1})
    for k, lr in enumerate(sim.local_ranges, 1):
        cons = [{'particleIndex': p, 'referenceVertex': p, 'maximumDistance': r['max'],
                 'maxNormalDistance': r['max_normal'], 'minNormalDistance': r['min_normal']}
                for p, r in sorted(lr['particles'].items()) if inv[p]]
        if cons:
            add(f'local_range{k}', 'hclLocalRangeConstraintSet', {
                'name': lr['name'] or SET_NAMES['local_range'], 'localConstraints': cons,
                'referenceMeshBufferIdx': 0, 'stiffness': lr['stiffness'],
                'shapeType': lr['shape'], 'applyNormalComponent': int(bool(lr['normal']))})
    for k, vol in enumerate(getattr(sim, 'volumes', []), 1):
        v = _volume(vol, P)
        if v is not None:
            add(f'volume{k}', 'hclVolumeConstraintMx', v)
    planes = []
    for p in sim.planes:
        for i in p['particles']:
            planes.append({'planeEquationBone': tuple(p['equation']), 'particleIndex': i,
                           'transformIndex': bone_index(p['bone']),
                           'stiffness': p['stiffness']})
    if planes:
        add('planes', 'hclBonePlanesConstraintSet', {
            'name': sim.planes[0].get('set') or SET_NAMES['planes'], 'bonePlanes': planes,
            'transformSetIndex': 0})
    return sets


def _order(sim, sets):
    """The sets in the model's run order (vanilla's default for kinds it doesn't name), and
    the simulate operator's constraintExecution."""
    want = [k for k in getattr(sim, 'solve_order', []) if k in sets]
    for kind in DEFAULT_ORDER:
        for k in sorted(sets):
            if k.rstrip('0123456789') == kind and k not in want:
                want.append(k)
    first = []
    for k in want:
        if k not in first:
            first.append(k)
    return [sets[k] for k in first], [first.index(k) for k in want] + [-1]


def _bitfield(bits, nb):
    words = [0] * ((nb + 31) // 32)
    for b in bits:
        words[b // 32] |= 1 << (b % 32)
    return {'words': words, 'numBits': nb}


def _state(name, ops, buffers, read, written, nb):
    tracker = {'read': _bitfield(read, nb),
               'readBeforeWrite': _bitfield(set(read) - set(written), nb),
               'written': _bitfield(written, nb)}
    empty = {'read': _bitfield((), nb), 'readBeforeWrite': _bitfield((), nb),
             'written': _bitfield((), nb)}
    return Obj('hclClothState', {
        'name': name, 'operators': ops,
        'usedBuffers': [{'bufferIndex': b, 'bufferUsage': list(u), 'shadowBufferIndex': b}
                        for b, u in buffers],
        'usedTransformSets': [{'transformSetIndex': 0, 'perComponentFlags': [11, 0],
                               'perComponentTransformTrackers': [tracker, empty]}],
        'usedSimCloths': [0]})


def _cloth_data(sim, cloth, bone_index, binds, nb, shared_cols):
    P = sim.positions
    n = len(P)
    if n == 0:
        raise ClothBuildError(f"{sim.cloth_data}: no particles")
    tris = [tuple(t) for t in sim.triangles]
    particles = []
    for p in sim.particles:
        m = p['mass']
        particles.append({'mass': m, 'invMass': 1.0 / m if m else 0.0,
                          'radius': p['radius'], 'friction': p['friction']})
    inv = [p['invMass'] for p in particles]
    normals = getattr(sim, 'normals', None)
    flips = getattr(sim, 'flips', None)
    if flips is None or len(flips) != len(tris):
        flips = triangle_flips(P, tris, normals) if normals else [0] * len(tris)
    if not normals or len(normals) != n:
        normals = vertex_normals(P, tris, flips)

    # Collidables, shared between pieces as the model shares them.
    cols, col_bones, offsets = [], [], []
    for ci in sim.collidable_ids:
        if ci not in shared_cols:
            shared_cols[ci] = _collidable(cloth.collidables[ci], bone_index, binds)
        c, b, off = shared_cols[ci]
        cols.append(c)
        col_bones.append(b)
        offsets.append(tuple(_col_major(off)))
    masks = list(sim.collision_masks)[:n] + [0] * (n - len(sim.collision_masks))
    pinch_flags = [0] * n
    for p in getattr(sim, 'pinch', []):
        if p < n:
            pinch_flags[p] = 1
    pinched = [p for p in range(n) if pinch_flags[p]]
    # Pinch settings per collidable: the sim's own, else the collidable's, else vanilla's usual.
    cpinch = getattr(sim, 'collidable_pinch', None) or []
    pinch_datas = []
    for k, ci in enumerate(sim.collidable_ids):
        pd = cpinch[k] if k < len(cpinch) and cpinch[k] else             getattr(cloth.collidables[ci], 'pinch', None)
        pinch_datas.append(dict(pd) if pd else {'pinchDetectionEnabled': 0,
                                                'pinchDetectionPriority': 0,
                                                'pinchDetectionRadius': 0.01})
    flip_bytes = [0] * ((len(tris) + 7) // 8)
    for k, f in enumerate(flips):
        if f:
            flip_bytes[k // 8] |= 1 << (k % 8)

    sets = _constraint_sets(sim, inv, bone_index)
    set_list, execution = _order(sim, sets)
    st = sim.settings
    g = tuple(st.get('gravity', (0.0, 0.0, -686.7)))[:3]
    sd = Obj('hclSimClothData', {
        'gravity': g + (1.0,), 'globalDampingPerSecond': st.get('damping', 0.9999),
        'collisionTolerance': COLLISION_TOLERANCE, 'subSteps': 0,
        'pinchDetectionEnabled': int(st.get('pinch_detection', 0)),
        'landscapeCollisionEnabled': int(st.get('landscape_collision', 0)),
        'transferMotionEnabled': int(st.get('transfer_motion', 1)),
        'name': sim.name, 'particleDatas': particles, 'fixedParticles': list(sim.pinned),
        'triangleIndices': [i for t in tris for i in t], 'triangleFlips': flip_bytes,
        'totalMass': sum(p['mass'] for p in particles),
        'transformSetIndex': 0 if cols else -1, 'transformIndices': col_bones,
        'offsets': offsets, 'perInstanceCollidables': cols,
        'staticConstraintSets': set_list, 'antiPinchConstraintSets': [],
        'simClothPoses': [Obj('hclSimClothPose', {
            'name': 'Simulation Pose', 'positions': [tuple(p) + (1.0,) for p in P]})],
        'actions': [], 'staticCollisionMasks': masks,
        'perParticlePinchDetectionEnabledFlags': pinch_flags,
        'collidablePinchingDatas': pinch_datas,
        'minPinchedParticleIndex': pinched[0] if pinched else 0,
        'maxPinchedParticleIndex': pinched[-1] if pinched else 0,
        # Bit 31 of a mask is set on some vanilla particles; it isn't a collidable.
        'maxCollisionPairs': sum(bin(m & ((1 << len(cols)) - 1)).count('1') for m in masks),
        'maxParticleRadius': max(p['radius'] for p in particles),
        'landscape': list(st.get('landscape', (0.05, 0.0, 9.0, 0.0))),
        'landscapeValue': st.get('landscape_value', 0.0),
        'landscapeCount': st.get('landscape_count', 0), 'value332': 1,
        'transferTransformSetIndex': 0,
        'transferTransformIndex': bone_index(sim.transfer_bone) if sim.transfer_bone else 0,
        'transferTranslationMotion': int(st.get('transfer_translation', 1)),
        'minTranslationSpeed': st.get('transfer_translation_speeds', (0.0, 10.0))[0],
        'maxTranslationSpeed': st.get('transfer_translation_speeds', (0.0, 10.0))[1],
        'minTranslationBlend': st.get('transfer_translation_min', 0.7),
        'maxTranslationBlend': st.get('transfer_translation_max', 0.7),
        'transferRotationMotion': int(st.get('transfer_rotation', 1)),
        'minRotationSpeed': st.get('transfer_rotation_speeds', (60.0, 180.0))[0],
        'maxRotationSpeed': st.get('transfer_rotation_speeds', (60.0, 180.0))[1],
        'minRotationBlend': st.get('transfer_rotation_min', 0.0),
        'maxRotationBlend': st.get('transfer_rotation_max', 0.5)})

    skin, subset = _skin(sim, bone_index, binds, normals)
    pinned = list(sim.pinned)
    move = Obj('hclMoveParticlesOperator', {
        'name': 'Move Particles', 'operatorID': 0,
        'vertexParticlePairs': [{'vertexIndex': p, 'particleIndex': p} for p in pinned],
        'simClothIndex': 0, 'refBufferIdx': 0})
    simop = Obj('hclSimulateOperator', {
        'name': 'Sim', 'operatorID': 0, 'simClothIndex': 0,
        'subSteps': st.get('sub_steps', 2), 'numberOfSolveIterations': 1,
        'constraintExecution': execution,
        'adaptConstraintStiffness': int(st.get('adapt_stiffness', 1))})
    driven = _driven(sim, bone_index, binds)
    deform = Obj('hclSimpleMeshBoneDeformOperator', {
        'name': 'Deform', 'operatorID': 0, 'inputBufferIdx': 1, 'outputTransformSetIdx': 0,
        'triangleBonePairs': [{'boneOffset': b * 64, 'triangleOffset': t * 6}
                              for b, t, _L in driven],
        'localBoneTransforms': [tuple(_col_major(L, w_rot=0.0)) for _b, _t, L in driven],
        'minTriangleArea': 0.0})
    copy_op = Obj('hclCopyVerticesOperator', {
        'name': 'VertGather Op', 'operatorID': 0, 'inputBufferIdx': 0, 'outputBufferIdx': 1,
        'numberOfVertices': n, 'startVertexIn': 0, 'startVertexOut': 0, 'copyNormals': 1})

    layout = dict(BUFFER_LAYOUT)
    scratch = Obj('hclScratchBufferDefinition', {
        'name': getattr(sim, 'buffer_name', None) or sim.cloth_data or 'Cloth_SIM',
        'type': 6, 'subType': 0, 'numVertices': n, 'numTriangles': 0,
        'bufferLayout': dict(layout, triangleFormat=2), 'triangleIndices': [],
        'storeNormals': 1, 'storeTangentsAndBiTangents': 0})
    simbuf = Obj('hclBufferDefinition', {
        'name': 'SimBuf', 'type': 1, 'subType': 0, 'numVertices': n,
        'numTriangles': len(tris), 'bufferLayout': dict(layout, triangleFormat=1)})
    tset = Obj('hclTransformSetDefinition', {'name': 'Root Transforms', 'type': 1,
                                             'numTransforms': nb})

    written = sorted({b for b, _t, _L in driven})
    reads = set(subset) | set(col_bones)
    extra = {bone_index(b) for b in getattr(sim, 'extra_reads', [])}
    # The Simulate state reads the transfer bone while transfer motion is on.
    transfer = {bone_index(sim.transfer_bone)} \
        if sim.transfer_bone and st.get('transfer_motion', 1) else set()
    lr = any(s.type_name == 'hclLocalRangeConstraintSet' for s in set_list)
    simulate = _state('Simulate', [0, 1, 2, 3],
                      [(0, (7, 7 if lr else 6, 0, 0, 0)), (1, (9, 0, 0, 0, 1))],
                      sorted(reads | extra | transfer), written, nb)
    animate = _state('Animate', [0, 4, 3], [(0, (7, 7, 0, 0, 0)), (1, (7, 6, 0, 0, 1))],
                     sorted(set(subset) | extra), written, nb)
    return Obj('hclClothData', {
        'name': sim.cloth_data or sim.name, 'simClothDatas': [sd],
        'bufferDefinitions': [scratch, simbuf], 'transformSetDefinitions': [tset],
        'operators': [skin, move, simop, deform, copy_op],
        'clothStateDatas': [simulate, animate], 'actions': [], 'targetPlatform': 2})


def _skeleton(cloth):
    sk = cloth.skeleton
    return Obj('hkaSkeleton', {
        'name': sk[0][0] if sk else 'Root',
        'parentIndices': [p for _n, p, _q in sk],
        'bones': [{'name': nm, 'lockTranslation': 0} for nm, _p, _q in sk],
        'referencePose': [{'translation': tuple(t) + (0.0,), 'rotation': tuple(q),
                           'scale': tuple(s) + (0.0,)} for _n, _p, (t, q, s) in sk],
        'referenceFloats': [], 'floatSlots': [], 'localFrames': [], 'partitions': []})


def build_graph(cloth):
    """The cloth model as an hk_2014 graph: the hkRootLevelContainer."""
    if not cloth.skeleton:
        raise ClothBuildError("the cloth has no skeleton")
    names = [nm for nm, _p, _q in cloth.skeleton]
    index = {nm: i for i, nm in enumerate(names)}

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
    return Obj('hkRootLevelContainer', {'namedVariants': variants})


def build_cloth(cloth):
    """The cloth model as a BSClothExtraData blob."""
    return write_graph(build_graph(cloth))
