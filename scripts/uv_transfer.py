"""Copy several parts' textures onto one mesh made by joining them.

A Starfield crowd head is head, eyes, mouth, tongue and hands joined into one mesh with one
texture set, its UVs repacked. This builds that texture set from the parts' own textures, in two
stages:

MAP, once, inside Blender. Select the parts, make the joined mesh active, open this file in the
Text Editor and Run Script. Every triangle of the joined mesh is matched to the part triangle it
is a copy of, and the result is written to "<active object>.uvmap.npz" next to the .blend. The
report it prints ends with the paint commands for this set of objects, the textures filled in from
the parts' materials where they can be.

    Headless: blender <file.blend> --background --python uv_transfer.py --
                  map --target CrowdHead --parts CanineMaleHead "RightEye:0:LOD0" ... [--out x.npz]

PAINT, once per texture type, with ordinary Python (numpy + Pillow):

    python uv_transfer.py paint --map CrowdHead.uvmap.npz --out CrowdHead_color.png
        --part "CanineMaleHead=male_fox_color.png" --part "Hands_3rd_M:0:LOD0=#b07a4a" ...

    --part NAME=FILE|#hex   one per part in the map, any order. FILE is .png or .dds; #rrggbb,
                            #rrggbbaa or #gg is a flat colour, for a part with no such texture.
    --size N                output size; defaults to the largest input texture.
    --normal                the textures are normal maps: each pixel is turned with its triangle.
    --opengl                ... OpenGL normal maps (green up). Starfield's are DirectX (green down).
    --pad N                 extend each island's colour N pixels outward (default 16).
    --bits 8|16             PNG bit depth (default 8; 16 with --normal).
"""
import argparse
import io
import math
import os
import struct
import sys
import zlib

import numpy as np

try:
    import bpy
    if not hasattr(bpy, 'context'):   # a stray `bpy` folder in site-packages, not Blender
        bpy = None
except ImportError:
    bpy = None


class MapError(Exception):
    """The joined mesh has faces that match no part. `faces` holds their polygon indices."""
    def __init__(self, msg, faces):
        super().__init__(msg)
        self.faces = faces


# --- Map (Blender) -------------------------------------------------------------------------------

def _world_verts(obj):
    """The mesh's own vertices (no modifiers) in world space."""
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    M = np.array(obj.matrix_world, np.float64)
    return co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]


def _loop_uvs(obj):
    me = obj.data
    if me.uv_layers.active is None:
        raise MapError(f"{obj.name} has no UV map", [])
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get('uv', uv)
    return uv.reshape(-1, 2).astype(np.float64)


def _material_indices(obj):
    me = obj.data
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', mi)
    return mi


def part_list(objects):
    """The parts the objects make: one per object, or one per material in use when an object's
    faces use several (each material has its own texture). Returns [(name, object, material
    index or None for the whole object)]; a split part is named "<object>:<material>"."""
    out = []
    for o in objects:
        used = sorted(set(_material_indices(o).tolist()))
        if len(used) < 2:
            out.append((o.name, o, None))
            continue
        for i in used:
            mat = o.data.materials[i] if i < len(o.data.materials) else None
            out.append((f"{o.name}:{mat.name if mat else f'slot{i}'}", o, i))
    return out


def build_map(target, parts, tol=1e-3):
    """Match every triangle of `target` to the triangle of one of `parts` it is a copy of.

    A target triangle matches when its three corners sit, within `tol`, on vertices of a single
    face of one part object; each corner then takes the UV that face gives its vertex, so seams
    come out right. That face's material says which part it is (see part_list). Faces deleted
    from the target don't matter. Raises MapError naming the target faces that match nothing.
    Returns the map as a dict of arrays: `parts` (names), `part` (index per triangle), `tgt_uv`
    and `src_uv` (triangle x corner x uv)."""
    from mathutils.kdtree import KDTree

    plist = part_list(parts)
    names = [n for n, _o, _i in plist]
    obj_names = [p.name for p in parts]
    part_of = []   # per object: material index -> part index
    for p in parts:
        ids = {i: k for k, (_n, o, i) in enumerate(plist) if o is p}
        part_of.append(ids)
    pmats = [_material_indices(p) for p in parts]
    pverts, puvs, ploops, pfaces_of = [], [], [], []
    for p in parts:
        me = p.data
        pverts.append(_world_verts(p))
        puvs.append(_loop_uvs(p))
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get('vertex_index', lv)
        starts = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_start', starts)
        totals = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_total', totals)
        ploops.append((lv, starts, totals))
        faces_of = [[] for _ in range(len(me.vertices))]
        for f, (s, n) in enumerate(zip(starts, totals)):
            for v in lv[s:s + n]:
                faces_of[v].append(f)
        pfaces_of.append(faces_of)

    offsets = np.cumsum([0] + [len(v) for v in pverts])
    kd = KDTree(int(offsets[-1]))
    for pi, co in enumerate(pverts):
        for vi, c in enumerate(co):
            kd.insert(c, int(offsets[pi] + vi))
    kd.balance()

    def owner(gid):
        pi = int(np.searchsorted(offsets, gid, side='right') - 1)
        return pi, gid - int(offsets[pi])

    me = target.data
    tco = _world_verts(target)
    tuv = _loop_uvs(target)
    if hasattr(me, 'calc_loop_triangles'):
        me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tri_v = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', tri_v)
    tri_l = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('loops', tri_l)
    tri_p = np.empty(nt, np.int32)
    me.loop_triangles.foreach_get('polygon_index', tri_p)
    tri_v, tri_l = tri_v.reshape(-1, 3), tri_l.reshape(-1, 3)

    cand = {}   # target vertex -> {(part, part vertex)}

    def candidates(v):
        if v not in cand:
            cand[v] = {owner(gid) for _co, gid, _d in kd.find_range(tco[v], tol)}
        return cand[v]

    part = np.empty(nt, np.int16)
    src = np.empty((nt, 3, 2))
    failed = {}
    for t in range(nt):
        cs = [candidates(int(v)) for v in tri_v[t]]
        faces = None
        for c in cs:
            fs = {(pi, f) for pi, pv in c for f in pfaces_of[pi][pv]}
            faces = fs if faces is None else faces & fs
        if not faces:
            failed.setdefault(int(tri_p[t]), t)
            continue
        pi, f = min(faces)
        lv, starts, totals = ploops[pi]
        s, n = starts[f], totals[f]
        for k, c in enumerate(cs):
            loop = next(s + j for j in range(n) if (pi, int(lv[s + j])) in c)
            src[t, k] = puvs[pi][loop]
        ids = part_of[pi]
        part[t] = ids[None] if None in ids else ids[int(pmats[pi][f])]

    if failed:
        msg = [f"{len(failed)} face(s) of {target.name} don't sit on any part's face:"]
        for fi in list(failed)[:5]:
            c = tco[me.polygons[fi].vertices].mean(axis=0)
            _co, gid, dist = kd.find(c)
            msg.append(f"  face {fi} at ({c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f}), "
                       f"{dist:.3f} from {obj_names[owner(gid)[0]]}")
        raise MapError("\n".join(msg), sorted(failed))

    return {'parts': np.array(names), 'part': part, 'tgt_uv': tuv[tri_l], 'src_uv': src,
            'target': np.array(target.name)}


def _uv_linear(src, tgt):
    """Per triangle, the 2x2 map taking source-UV edges to target-UV edges, or None if flat."""
    Es = np.stack([src[:, 1] - src[:, 0], src[:, 2] - src[:, 0]], axis=-1)
    Et = np.stack([tgt[:, 1] - tgt[:, 0], tgt[:, 2] - tgt[:, 0]], axis=-1)
    ok = np.abs(np.linalg.det(Es)) > 1e-14
    A = np.zeros_like(Es)
    A[ok] = Et[ok] @ np.linalg.inv(Es[ok])
    return A, ok


def _rotations(A):
    """The rotation (or reflection) part of each 2x2 map: the nearest orthogonal matrix."""
    U, _S, Vt = np.linalg.svd(A)
    return U @ Vt


def map_report(m):
    """Per part: triangle count, typical UV scale and rotation, mirrored count."""
    A, ok = _uv_linear(m['src_uv'], m['tgt_uv'])
    R = _rotations(A)
    det = np.linalg.det(A)
    rep = {}
    for pi, name in enumerate(m['parts']):
        sel = (m['part'] == pi) & ok
        if not sel.any():
            rep[str(name)] = {'triangles': int((m['part'] == pi).sum()), 'scale': 0.0,
                              'scale_range': (0.0, 0.0), 'rotation': 0, 'mirrored': 0}
            continue
        scale = np.sqrt(np.abs(det[sel]))
        ang = np.round(np.degrees(np.arctan2(R[sel, 1, 0], R[sel, 0, 0]))).astype(int) % 360
        vals, counts = np.unique(ang, return_counts=True)
        rep[str(name)] = {'triangles': int((m['part'] == pi).sum()),
                          'scale': float(np.median(scale)),
                          'scale_range': (float(np.percentile(scale, 5)),
                                          float(np.percentile(scale, 95))),
                          'rotation': int(vals[np.argmax(counts)]),
                          'mirrored': int((det[sel] < 0).sum())}
    return rep


def write_map(path, m):
    np.savez_compressed(path, **m)


def read_map(path):
    with np.load(path) as f:
        return {k: f[k] for k in f.files}


# Which sockets carry each texture type: an SF Layer group's inputs, or Blender's own nodes.
_CHANNELS = {
    'color':  ({'Albedo', 'Base Color'}, {'BSDF_DIFFUSE': 'Color'}),
    'normal': ({'Normal Tex'}, {'NORMAL_MAP': 'Color'}),
    'rough':  ({'Roughness'}, {}),
    'metal':  ({'Metallic'}, {}),
    'ao':     ({'AO'}, {}),
}


def _images_feeding(sock):
    """Image nodes upstream of a socket, through anything but group nodes (a group's inputs are
    reached directly, as sockets of their own)."""
    found, seen, todo = set(), set(), [sock]
    while todo:
        s = todo.pop()
        for link in s.links:
            n = link.from_node
            if n.name in seen:
                continue
            seen.add(n.name)
            if n.type == 'TEX_IMAGE':
                if n.image is not None:
                    found.add(n.image)
            elif n.type != 'GROUP':
                todo.extend(i for i in n.inputs if i.is_linked)
    return found


def material_textures(obj, index=None):
    """{channel: (file path or None, note)} from the object's materials, or just the one in
    slot `index`."""
    images = {ch: set() for ch in _CHANNELS}
    mats = obj.data.materials if index is None else obj.data.materials[index:index + 1]
    for mat in mats:
        if mat is None or not mat.node_tree:
            continue
        for n in mat.node_tree.nodes:
            for ch, (names, by_type) in _CHANNELS.items():
                socks = [i for i in n.inputs if i.name in names and i.is_linked]
                if n.type in by_type and by_type[n.type] in n.inputs:
                    socks.append(n.inputs[by_type[n.type]])
                for s in socks:
                    images[ch] |= _images_feeding(s)
    out = {}
    for ch, ims in images.items():
        if len(ims) == 1:
            im = next(iter(ims))
            path = bpy.path.abspath(im.filepath) if im.filepath else ''
            out[ch] = (os.path.normpath(path), '') if path and os.path.isfile(path) else \
                (None, f"image {im.name} has no file on disk")
        elif ims:
            out[ch] = (None, "several images: " + ", ".join(sorted(i.name for i in ims)))
        else:
            out[ch] = (None, "nothing plugged in")
    return out


def paint_commands(map_path, target, parts):
    """One paint command per texture type, textures filled in from the parts' materials."""
    script = os.path.abspath(__file__) if os.path.isfile(__file__) else 'uv_transfer.py'
    folder = os.path.dirname(map_path)
    plist = part_list(parts)
    tex = {name: material_textures(o, i) for name, o, i in plist}
    lines = []
    for ch in _CHANNELS:
        out = os.path.join(folder, f"{target.name}_{ch}.png")
        cmd = [f'python "{script}" paint --map "{map_path}" --out "{out}"']
        if ch == 'normal':
            cmd.append('--normal')
        notes = []
        for name, _o, _i in plist:
            path, note = tex[name][ch]
            cmd.append(f'--part "{name}={path or f"<{name} {ch}>"}"')
            if note:
                notes.append(f"#   {name}: {note}")
        lines.append(f"# {ch}")
        lines.extend(notes)
        lines.append(" ".join(cmd))
    return "\n".join(lines)


def print_report(m, map_path=None, target=None, parts=None):
    print(f"uv_transfer: {len(m['part'])} triangles of {m['target']} mapped")
    for name, r in map_report(m).items():
        lo, hi = r['scale_range']
        print(f"  {name}: {r['triangles']} triangles, scale {r['scale']:.3f} "
              f"({lo:.3f}-{hi:.3f}), rotated {r['rotation']} deg, {r['mirrored']} mirrored")
    if map_path:
        print(f"Map written to {map_path}\n")
        print("Paint commands (fill in any <placeholder>):\n")
        print(paint_commands(map_path, target, parts))


def _safe_name(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def select_faces(obj, faces):
    """Select exactly these faces, with their edges and vertices, so Edit Mode shows them in
    any select mode. Everything else is deselected."""
    me = obj.data
    sel = np.zeros(len(me.polygons), bool)
    sel[list(faces)] = True
    starts = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_start', starts)
    totals = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_total', totals)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('edge_index', le)
    in_sel = np.zeros(len(me.loops), bool)
    for f in faces:
        in_sel[starts[f]:starts[f] + totals[f]] = True
    vsel = np.zeros(len(me.vertices), bool)
    vsel[lv[in_sel]] = True
    esel = np.zeros(len(me.edges), bool)
    esel[le[in_sel]] = True
    me.polygons.foreach_set('select', sel)
    me.vertices.foreach_set('select', vsel)
    me.edges.foreach_set('select', esel)
    me.update()


def run_in_blender():
    """Text Editor: the active object is the target, the other selected meshes are the parts."""
    if bpy.context.mode != 'OBJECT':
        raise RuntimeError("uv_transfer: switch to Object Mode first")
    target = bpy.context.view_layer.objects.active
    parts = [o for o in bpy.context.selected_objects if o is not target and o.type == 'MESH']
    if target is None or target.type != 'MESH' or not parts:
        raise RuntimeError("uv_transfer: select the parts, then make the joined mesh active")
    folder = os.path.dirname(bpy.data.filepath) or os.getcwd()
    map_path = os.path.join(folder, _safe_name(target.name) + ".uvmap.npz")
    try:
        m = build_map(target, parts)
    except MapError as e:
        if e.faces:
            select_faces(target, e.faces)
            print(f"{e}\nThose faces are selected in {target.name}; no map written.")
        raise
    write_map(map_path, m)
    print_report(m, map_path, target, parts)


def run_headless(argv):
    ap = argparse.ArgumentParser(prog="uv_transfer.py -- map")
    ap.add_argument('command', choices=['map'])
    ap.add_argument('--target', required=True)
    ap.add_argument('--parts', nargs='+', required=True)
    ap.add_argument('--out')
    ap.add_argument('--tol', type=float, default=1e-3)
    a = ap.parse_args(argv)
    target = bpy.data.objects[a.target]
    parts = [bpy.data.objects[n] for n in a.parts]
    m = build_map(target, parts, a.tol)
    out = a.out or os.path.join(os.path.dirname(bpy.data.filepath),
                                _safe_name(target.name) + ".uvmap.npz")
    write_map(out, m)
    print_report(m, out, target, parts)


# --- Paint ---------------------------------------------------------------------------------------

def _pyramid(img):
    """The image and successive half-size copies (2x2 averages), down to 1 pixel."""
    levels = [img]
    while min(levels[-1].shape[:2]) > 1:
        a = levels[-1]
        h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
        a = a[:h, :w]
        levels.append((a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) / 4)
    return levels


def _bilinear(img, u, v):
    """Sample img (top row first) at UVs (v up), wrapping like a game texture."""
    h, w = img.shape[:2]
    x = np.mod(u, 1.0) * w - 0.5
    y = np.mod(1.0 - v, 1.0) * h - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0, y0 = x0.astype(int) % w, y0.astype(int) % h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy)
            + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)


def _fit_channels(a, c):
    """Grey -> RGB, RGB -> RGBA (alpha 1), as needed to reach c channels."""
    if a.shape[-1] == c:
        return a
    if a.shape[-1] in (1, 2) and c >= 3:
        a = np.concatenate([a[..., :1]] * 3 + ([a[..., 1:2]] if a.shape[-1] == 2 else []), -1)
    if a.shape[-1] < c:
        a = np.concatenate([a, np.ones(a.shape[:-1] + (c - a.shape[-1],), a.dtype)], -1)
    return a[..., :c]


def paint(m, textures, size=None, normal=False, opengl=False, pad=16, background=None):
    """Paint the joined mesh's texture from one texture per part.

    textures: {part name: image array (rows top first, H x W x C, 0..1) or a flat colour tuple}.
    Returns the image as an array, size x size x C."""
    names = [str(n) for n in m['parts']]
    missing = [n for n in names if n not in textures]
    if missing:
        raise ValueError("no texture given for part(s): " + ", ".join(missing))
    extra = [n for n in textures if n not in names]
    if extra:
        raise ValueError("not a part in this map: " + ", ".join(extra))

    arrays = {n: (t if t.ndim == 3 else t[..., None]).astype(np.float32)
              for n, t in textures.items() if isinstance(t, np.ndarray)}
    if size is None:
        if not arrays:
            raise ValueError("every part is a flat colour: give --size")
        size = max(max(a.shape[:2]) for a in arrays.values())
    c = max([a.shape[-1] for a in arrays.values()]
            + [len(t) for t in textures.values() if not isinstance(t, np.ndarray)])
    if normal:
        c = max(c, 3)
    pyr = {n: _pyramid(_fit_channels(a, c)) for n, a in arrays.items()}
    flat = {n: _fit_channels(np.array(t, np.float32)[None], c)[0]
            for n, t in textures.items() if not isinstance(t, np.ndarray)}

    if background is None:
        background = (0.5, 0.5, 1.0, 1.0) if normal else (0.0, 0.0, 0.0, 1.0)
    out = np.empty((size, size, c), np.float32)
    out[:] = _fit_channels(np.array(background, np.float32)[None], c)[0]
    filled = np.zeros((size, size), bool)

    tgt, src, part = m['tgt_uv'], m['src_uv'], m['part']
    A, ok = _uv_linear(src, tgt)
    R = _rotations(A)
    P = np.empty_like(tgt)
    P[..., 0] = tgt[..., 0] * size
    P[..., 1] = (1.0 - tgt[..., 1]) * size
    green = 1.0 if opengl else -1.0

    for t in range(len(part)):
        (x0, y0), (x1, y1), (x2, y2) = P[t]
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-12:
            continue
        xa = max(int(math.floor(min(x0, x1, x2) - 0.5)), 0)
        xb = min(int(math.ceil(max(x0, x1, x2) - 0.5)), size - 1)
        ya = max(int(math.floor(min(y0, y1, y2) - 0.5)), 0)
        yb = min(int(math.ceil(max(y0, y1, y2) - 0.5)), size - 1)
        if xa > xb or ya > yb:
            continue
        gy, gx = np.mgrid[ya:yb + 1, xa:xb + 1]
        cx, cy = gx + 0.5, gy + 0.5
        l0 = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / d
        l1 = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / d
        l2 = 1.0 - l0 - l1
        inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not inside.any():
            continue
        iy, ix = gy[inside], gx[inside]
        name = names[part[t]]
        if name in flat:
            out[iy, ix] = flat[name]
            filled[iy, ix] = True
            continue
        S = src[t]
        uv = l0[inside, None] * S[0] + l1[inside, None] * S[1] + l2[inside, None] * S[2]
        levels = pyr[name]
        h, w = levels[0].shape[:2]
        src_px = abs((S[1, 0] - S[0, 0]) * (S[2, 1] - S[0, 1])
                     - (S[2, 0] - S[0, 0]) * (S[1, 1] - S[0, 1])) * w * h
        ratio = math.sqrt(src_px / abs(d)) if src_px > 0 else 1.0
        level = min(max(int(math.floor(math.log2(ratio))), 0) if ratio > 1 else 0,
                    len(levels) - 1)
        px = _bilinear(levels[level], uv[:, 0], uv[:, 1])
        if normal and ok[t]:
            nx = px[:, 0] * 2 - 1
            ny = (px[:, 1] * 2 - 1) * green          # in UV space, v up
            r = R[t]
            rx, ry = r[0, 0] * nx + r[0, 1] * ny, r[1, 0] * nx + r[1, 1] * ny
            nz = np.sqrt(np.clip(1 - rx * rx - ry * ry, 0, 1))
            px = px.copy()
            px[:, 0], px[:, 1], px[:, 2] = (rx + 1) / 2, (ry * green + 1) / 2, (nz + 1) / 2
        out[iy, ix] = px
        filled[iy, ix] = True

    _dilate(out, filled, pad)
    return out


def _dilate(out, filled, steps):
    """Extend filled pixels outward `steps` times, each new pixel the mean of its filled
    4-neighbours, so mipmaps don't pull background in at island edges."""
    for _ in range(steps):
        if filled.all():
            return
        acc = np.zeros_like(out)
        cnt = np.zeros(filled.shape, np.float32)
        for sl_to, sl_from in (((slice(1, None), slice(None)), (slice(None, -1), slice(None))),
                               ((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                               ((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
                               ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
            f = filled[sl_from]
            acc[sl_to] += out[sl_from] * f[..., None]
            cnt[sl_to] += f
        new = ~filled & (cnt > 0)
        out[new] = acc[new] / cnt[new][:, None]
        filled |= new


# --- Image files ---------------------------------------------------------------------------------

# Pillow decodes the block-compressed DDS formats but not their sRGB twins; the blocks are the
# same, so relabel those in memory.
_SRGB_TO_LINEAR = {29: 28, 72: 71, 75: 74, 78: 77, 91: 87, 93: 88, 99: 98}


def load_image(path):
    """An image file as float32, rows top first, H x W x C, 0..1."""
    from PIL import Image
    if path.lower().endswith('.dds'):
        b = bytearray(open(path, 'rb').read())
        if b[84:88] == b'DX10':
            fmt = struct.unpack_from('<I', b, 128)[0]
            if fmt in _SRGB_TO_LINEAR:
                struct.pack_into('<I', b, 128, _SRGB_TO_LINEAR[fmt])
        im = Image.open(io.BytesIO(bytes(b)))
    else:
        im = Image.open(path)
    im.load()
    if im.mode in ('I;16', 'I;16B', 'I;16L', 'I'):
        a = np.asarray(im, np.float64) / 65535.0
    else:
        if im.mode not in ('L', 'LA', 'RGB', 'RGBA'):
            im = im.convert('RGBA' if 'transparency' in im.info else 'RGB')
        a = np.asarray(im, np.float64) / 255.0
    if a.ndim == 2:
        a = a[..., None]
    return a.astype(np.float32)


def _png_chunk(kind, data):
    return (struct.pack('>I', len(data)) + kind + data
            + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))


def save_image(a, path, bits=8):
    """Write H x W x C (0..1) as PNG: grey, grey+alpha, RGB or RGBA, 8 or 16 bits."""
    a = np.clip(a, 0, 1)
    h, w, c = a.shape
    if bits == 8:
        from PIL import Image
        mode = {1: 'L', 2: 'LA', 3: 'RGB', 4: 'RGBA'}[c]
        px = np.round(a * 255).astype(np.uint8)
        Image.fromarray(px[..., 0] if c == 1 else px, mode).save(path)
        return
    px = np.round(a * 65535).astype('>u2')
    rows = np.concatenate([np.zeros((h, 1), np.uint8), px.reshape(h, -1).view(np.uint8)], axis=1)
    color_type = {1: 0, 2: 4, 3: 2, 4: 6}[c]
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(_png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 16, color_type, 0, 0, 0)))
        f.write(_png_chunk(b'IDAT', zlib.compress(rows.tobytes(), 6)))
        f.write(_png_chunk(b'IEND', b''))


def parse_flat(spec):
    """'#rrggbb', '#rrggbbaa' or '#gg' -> a tuple of 0..1 floats."""
    h = spec.lstrip('#')
    if len(h) not in (2, 6, 8) or any(ch not in '0123456789abcdefABCDEF' for ch in h):
        raise ValueError(f"not a colour: {spec}")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in range(0, len(h), 2))


def paint_main(argv):
    ap = argparse.ArgumentParser(prog="uv_transfer.py paint",
                                 description="Paint a joined mesh's texture from its parts'.")
    ap.add_argument('--map', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--part', action='append', default=[], metavar='NAME=FILE|#hex')
    ap.add_argument('--size', type=int)
    ap.add_argument('--normal', action='store_true')
    ap.add_argument('--opengl', action='store_true')
    ap.add_argument('--pad', type=int, default=16)
    ap.add_argument('--bits', type=int, choices=[8, 16])
    a = ap.parse_args(argv)

    m = read_map(a.map)
    textures = {}
    for spec in a.part:
        name, sep, value = spec.partition('=')
        if not sep:
            ap.error(f"--part needs NAME=FILE or NAME=#colour: {spec}")
        if value.startswith('<'):
            ap.error(f"fill in the texture for {name}: {value}")
        textures[name] = parse_flat(value) if value.startswith('#') else load_image(value)
    try:
        img = paint(m, textures, a.size, a.normal, a.opengl, a.pad)
    except ValueError as e:
        ap.error(str(e))
    bits = a.bits or (16 if a.normal else 8)
    save_image(img, a.out, bits)
    print(f"Wrote {a.out}: {img.shape[1]}x{img.shape[0]}, {img.shape[2]} channel(s), {bits}-bit")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'paint':
        paint_main(sys.argv[2:])
    elif bpy is not None:
        args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
        if args:
            run_headless(args)
        else:
            run_in_blender()
    else:
        print(__doc__)
