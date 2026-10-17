"""Bake Starfield crowd-head variants from a race's skin tones and tint layers.

A crowd head can't wear tint layers: it is one merged mesh (head, eyes, mouth, arms) with one
baked texture set. So the variety a chargen face gets from its skin tone and tint layers has to
be baked into separate crowd heads. This builds them from a recipe:

    python scripts/sf_tintbake.py bake recipe.toml [--dry-run] [--force]

For every crowd-head nif in the recipe's `heads` folder it enumerates every combination of skin
tone and tint-layer option the race offers, keeps a stable random sample of `limit` of them, and
for each one writes:

    <name>_color.dds  the face composited in the chargen head's UV space, then painted into the
                      crowd-head layout (uv_transfer) with that tone's hands and an eye colour
    <name>.mat        the head's crowd material with only the colour texture changed
    <name>.nif        the head's nif and its _facebones companion, pointing at that material.
                      They keep the head's .mesh, morph and BoneTrn, so a variant costs only
                      its texture.

and a manifest, <recipe name>.variants.json beside the recipe, that the plugin builder reads to write the
records. Normal, rough, metal and AO are shared by every variant of a head and are not touched.

The recipe (TOML; relative paths are relative to the recipe file):

    race = "FSFFoxRace"
    phenotype = "male_fox_md1"        # the face skin-tone entry the faces start from
    plugin = "FSFPlayer_FOX.esm"      # optional: it and its masters; default the active load order
    data = ["C:/Steam/steamapps/common/Starfield/Data", "C:/Modding/Starfield/00StarfieldAssets"]
    heads = "C:/Steam/steamapps/common/Starfield/Data/Meshes/Actors/FSFFox_Crowd/Mesh/Male"
    uvmap = "CrowdHead.uvmap.npz"
    out = "C:/Modding/Starfield/Mods/FSF_test"    # mod root the variants are written under
    tones = [1, 2, 3, 4]              # optional: skin-tone indices, 0-based; default all
    limit = 40                        # how many variants in all, across every head
    seed = 1
    size = 1024                       # colour texture size

    [parts]                           # what each part of the uv map is painted with
    "CanineMaleHead.COMBINED:CanineMaleHead.Mat" = "face"
    "CanineLeftEye" = "eyes"
    "CanineRightEye" = "eyes"
    "CanineHands" = "hands"
    "CanineMaleHead.COMBINED:CanineTeeth.Mat" = "Textures/Actors/FSFCanine/faces/Teeth/CanineMaleMouth_color.dds"

    [[layers]]                        # composited over the skin tone in stack order
    slot = "Dermaesthetic"            # options: the tone's chargen filter, as the creator offers
    code = "d"
    [[layers]]
    slot = "Complexion1"              # options: the group of that name
    code = "c"
    optional = true                   # "none" is an option too

    [eyes]
    code = "e"
    exclude = ["Dead"]                # EyeColor options never picked

A part is painted with "face" (the composite), "hands" (the tone's hands texture), "eyes" (an
EyeColor option), a texture -- a file path, or a path under the data folders -- or #rrggbb.
A layer can name `files = [...]` instead of using the race's options, and a mask layer
(*_mask textures) takes `colors = ["#rrggbb", ...]`.

Names say what is in them: Crowd_Head_Fox_md1_sk2_d1_c3_e5 is head Crowd_Head_Fox_md1, skin
tone 2, option 1 of layer d, option 3 of layer c (0 = none), eye colour 5. Option numbers count
from 1 in the race's own lists, so they don't move when the recipe excludes something.

Layers composite the way the chargen face does, in the stack's order: a full-colour layer
(*_color) is laid over what's below by its own alpha (proven in game for dermaesthetics); a mask
layer blends its colour in by mask x intensity (not yet proven against a vanilla bake).
"""
import argparse
import copy
import hashlib
import json
import os
import struct
import sys
import tomllib
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'io_scene_nifly'))

import uv_transfer                                  # noqa: E402
from pyn.sf_materials import material_id            # noqa: E402

ROLES = ('face', 'hands', 'eyes')
DERMAESTHETIC = 'Dermaesthetic'
CHARGEN_DERMAESTHETIC = 'Chargen_Dermaesthetic'
STACK = 'PostBlendFaceCustomizationLayers'
EYE_COLOR = 'EyeColor'
FACEBONES = '_facebones'


class RecipeError(Exception):
    pass


# --- the recipe -----------------------------------------------------------------------------

def load_recipe(path):
    with open(path, 'rb') as f:
        r = tomllib.load(f)
    r['_dir'] = os.path.dirname(os.path.abspath(path))
    r['_name'] = os.path.splitext(os.path.basename(path))[0]
    for key in ('race', 'phenotype', 'data', 'heads', 'uvmap', 'out', 'parts'):
        if key not in r:
            raise RecipeError(f"recipe has no {key!r}")
    r.setdefault('layers', [])
    r.setdefault('eyes', {})
    r['eyes'].setdefault('code', 'e')
    r['eyes'].setdefault('exclude', [])
    r.setdefault('limit', 40)
    r.setdefault('seed', 1)
    r.setdefault('size', 1024)
    r['data'] = [recipe_path(r, d) for d in r['data']]
    for key in ('heads', 'uvmap', 'out'):
        r[key] = recipe_path(r, r[key])
    codes = [ly.get('code') for ly in r['layers']] + [r['eyes']['code']]
    if any(not c for c in codes) or len(set(codes)) != len(codes):
        raise RecipeError(f"every layer needs its own code: {codes}")
    return r


def recipe_path(r, p):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(r['_dir'], p))


# --- what the race offers -------------------------------------------------------------------

class Options:
    """What a race offers, as texture paths relative to the data folders.

    tones:  [(face, hands)] by skin-tone index
    slots:  {slot: [(label, path)]} for the tint groups, by name
    derm:   [[(label, path)]] the dermaesthetic options per skin-tone index
    eyes:   [(label, path)]"""
    def __init__(self, tones, slots, derm, eyes, stack):
        self.tones, self.slots, self.derm, self.eyes, self.stack = tones, slots, derm, eyes, stack

    def layer(self, slot, tone):
        if slot == DERMAESTHETIC:
            return self.derm[tone] if tone < len(self.derm) else []
        return self.slots.get(slot, [])


def read_options(r):
    """Read the race's skin tones and tint options from the load order.

    Every AVMD group is found by name, the last plugin to define a name winning, so this reads
    what the game would: a player plugin that replaces vanilla's groups is honoured."""
    import sf_racecheck as R
    order = R.load_order_names(r['data'], r.get('plugin'))
    plugins = R.load_plugins(R.Report(), r['data'], order)
    race = R.find_race(plugins, r['race'])
    if race is None:
        raise RecipeError(f"race {r['race']!r} is not in the load order")
    avm = R.avm_index(plugins)

    def simple(name):
        g = avm.get((R.AVM_SIMPLE, name))
        return [(lab, path) for lab, path in R.simple_entries(g) if path] if g else []

    fstt = avm.get((R.AVM_COMPLEX, R.text(race, 'FSTT')))
    if fstt is None:
        raise RecipeError(f"{r['race']}: face skin tones (FSTT) don't resolve")
    face_grp = R.complex_children(fstt, avm).get(r['phenotype'])
    if face_grp is None:
        raise RecipeError(f"{r['race']}'s face skin tones have no {r['phenotype']!r}")
    faces = [p for _, p in R.simple_entries(face_grp)]
    hands = [p for _, p in simple(R.text(race, 'HSTT'))]
    if len(hands) != len(faces):
        raise RecipeError(f"{len(faces)} face skin tones but {len(hands)} hands tones")

    derm_filter = avm.get((R.AVM_COMPLEX, CHARGEN_DERMAESTHETIC))
    derm = []
    if derm_filter is not None:
        # The filter's entries are positional, one per skin-tone index, whatever they're called.
        derm = [[(lab, p) for lab, p in R.simple_entries(g) if p] if g else []
                for g in R.complex_children(derm_filter, avm).values()]

    stack_grp = avm.get((R.AVM_COMPLEX, STACK))
    stack = R.avm_entries(stack_grp) if stack_grp else []
    slots = {name: simple(name) for name in stack}
    return Options(list(zip(faces, hands)), slots, derm, simple(EYE_COLOR), stack)


# --- the variants ---------------------------------------------------------------------------

def find_heads(folder):
    """The crowd-head nifs in `folder`: every nif except the _facebones companions."""
    names = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith('.nif')
                   and not os.path.splitext(f)[0].lower().endswith(FACEBONES))
    if not names:
        raise RecipeError(f"no head nifs in {folder}")
    return [os.path.join(folder, f) for f in names]


def is_mask(path):
    return os.path.splitext(path)[0].lower().endswith('_mask')


def layer_choices(r, ly, opts, tone):
    """A layer's choices for one skin tone: [(code, path or None, colour or None)].

    The code is the option's 1-based place in the race's list (0 for "none"); a mask layer's
    is that plus a letter for the colour."""
    if 'files' in ly:
        found = [(f"{i}", recipe_path(r, f)) for i, f in enumerate(ly['files'], 1)]
    else:
        if ly['slot'] not in opts.stack and ly['slot'] != DERMAESTHETIC:
            raise RecipeError(f"{ly['slot']!r} is not a slot in {STACK}")
        found = [(f"{i}", p) for i, (_, p) in enumerate(opts.layer(ly['slot'], tone), 1)]
    out = [('0', None, None)] if ly.get('optional') else []
    for code, path in found:
        if is_mask(path):
            colors = ly.get('colors')
            if not colors:
                raise RecipeError(f"layer {ly['code']}: {path} is a mask; give `colors`")
            out += [(code + 'abcdefghijklmnopqrstuvwxyz'[j], path, c)
                    for j, c in enumerate(colors)]
        else:
            out.append((code, path, None))
    return out


def variant_space(r, opts, heads):
    """Every variant the recipe allows, as dicts with the name and what goes into it."""
    tones = r.get('tones', list(range(len(opts.tones))))
    bad = [t for t in tones if not 0 <= t < len(opts.tones)]
    if bad:
        raise RecipeError(f"skin tone(s) {bad} out of range 0..{len(opts.tones) - 1}")
    exclude = {e.lower() for e in r['eyes']['exclude']}
    eyes = [(f"{i}", p) for i, (lab, p) in enumerate(opts.eyes, 1) if lab.lower() not in exclude]
    if not eyes:
        raise RecipeError("no eye colours to choose from")

    out = []
    for head in heads:
        stem = os.path.splitext(os.path.basename(head))[0]
        for tone in tones:
            combos = [[]]
            for ly in r['layers']:
                choices = layer_choices(r, ly, opts, tone)
                if not choices:
                    raise RecipeError(f"layer {ly['code']} has no options for skin tone {tone}")
                combos = [c + [(ly, ch)] for c in combos for ch in choices]
            for combo in combos:
                for eye_code, eye in eyes:
                    parts = [stem, f"sk{tone}"] + [ly['code'] + ch[0] for ly, ch in combo]
                    parts.append(r['eyes']['code'] + eye_code)
                    out.append({'name': '_'.join(parts), 'head': head, 'tone': tone,
                                'layers': [(ly.get('slot'), ch[1], ch[2])
                                           for ly, ch in combo if ch[1]],
                                'eye': eye})
    return out


def pick(variants, limit, seed):
    """The `limit` variants whose names hash lowest under `seed`.

    Random-looking but stable: the same recipe picks the same set every time, and adding a head
    or an option only brings in the few new names that hash lower, instead of reshuffling."""
    def key(v):
        return hashlib.sha256(f"{seed}:{v['name']}".encode()).digest()
    return sorted(sorted(variants, key=key)[:limit], key=lambda v: v['name'])


# --- compositing ----------------------------------------------------------------------------

def parse_color(spec):
    c = uv_transfer.parse_flat(spec)
    return c if len(c) == 4 else c[:3] + (1.0,)


def resized(img, h, w):
    if img.shape[:2] == (h, w):
        return img
    from PIL import Image
    return np.stack([np.asarray(Image.fromarray(img[..., i]).resize((w, h), Image.BILINEAR))
                     for i in range(img.shape[-1])], axis=-1).astype(np.float32)


def composite(base, layers):
    """Lay `layers` over `base` (H x W x 3, 0..1), bottom first.

    Each layer is (image, colour, intensity). A colour image (colour None) is laid on by its own
    alpha; a mask (one channel) blends `colour` in by mask x intensity x the colour's alpha."""
    out = base[..., :3].astype(np.float32).copy()
    h, w = out.shape[:2]
    for img, color, intensity in layers:
        img = resized(img, h, w)
        if color is None:
            alpha = img[..., 3:4] if img.shape[-1] == 4 else np.ones((h, w, 1), np.float32)
            rgb = img[..., :3] if img.shape[-1] >= 3 else np.repeat(img[..., :1], 3, axis=-1)
            a = alpha * intensity
            out = out * (1 - a) + rgb * a
        else:
            a = img[..., :1] * intensity * color[3]
            out = out * (1 - a) + np.asarray(color[:3], np.float32) * a
    return out


# --- files ----------------------------------------------------------------------------------

def find_texture(r, path):
    """A texture the recipe or the race names, as a file: an existing path, else a path under
    the data folders. The .png beside a .dds is preferred: it is the source the .dds was made
    from, and Pillow reads every PNG but not every DDS."""
    candidates = [path] if os.path.isabs(path) else \
        [recipe_path(r, path)] + [os.path.join(d, path.replace('\\', os.sep)) for d in r['data']]
    for c in candidates:
        png = os.path.splitext(c)[0] + '.png'
        if os.path.exists(png):
            return png
        if os.path.exists(c):
            return c
    raise RecipeError(f"texture not found: {path}")


def load_texture(r, path, cache):
    if path not in cache:
        cache[path] = uv_transfer.load_image(find_texture(r, path))
    return cache[path]


def nif_header_strings(b):
    """Locate a Bethesda NIF's header string table.

    Returns (max_len_offset, [(offset, string)]), each offset that of the string's u32 length.
    The layout follows nifly's NiHeader::Put for a 20.2.0.7 Bethesda file."""
    o = b.index(b'\n') + 1
    o += 4 + 1 + 4                                   # version, endian, user version
    nblocks, = struct.unpack_from('<I', b, o)
    o += 4
    stream, = struct.unpack_from('<I', b, o)
    o += 4
    o += 1 + b[o]                                    # creator
    if stream > 130:
        o += 4
    for _ in range(3 if stream == 130 else 2):       # export info
        o += 1 + b[o]
    ntypes, = struct.unpack_from('<H', b, o)
    o += 2
    for _ in range(ntypes):
        o += 4 + struct.unpack_from('<I', b, o)[0]
    o += 2 * nblocks + 4 * nblocks                   # block type indices, block sizes
    nstrings, = struct.unpack_from('<I', b, o)
    max_off = o + 4
    o += 8
    strings = []
    for _ in range(nstrings):
        n, = struct.unpack_from('<I', b, o)
        strings.append((o, b[o + 4:o + 4 + n].decode('utf-8', 'replace')))
        o += 4 + n
    return max_off, strings


def nif_material(path):
    """The material path a crowd-head nif's shape uses: the header string that names a .mat."""
    b = open(path, 'rb').read()
    mats = [s for _, s in nif_header_strings(b)[1] if s.lower().endswith('.mat')]
    if len(mats) != 1:
        raise RecipeError(f"{path}: expected one material, found {mats}")
    return mats[0]


def retarget_nif(src, dst, old_mat, new_mat):
    """Copy a nif, pointing its shape at another material.

    Two things name the material: the header string, which only moves the strings after it,
    and the shape's MaterialID, a CRC of the path, which is patched in place. Nothing else is
    rewritten, so the copy keeps the original's .mesh, skin, morph and BoneTrn exactly."""
    b = bytearray(open(src, 'rb').read())
    old_id, new_id = struct.pack('<I', material_id(old_mat)), struct.pack('<I', material_id(new_mat))
    if b.count(old_id) != 1:
        raise RecipeError(f"{src}: MaterialID {old_id.hex()} found {b.count(old_id)} times")
    b[b.index(old_id):b.index(old_id) + 4] = new_id

    max_off, strings = nif_header_strings(b)
    hits = [(o, s) for o, s in strings if s == old_mat]
    if len(hits) != 1:
        raise RecipeError(f"{src}: material string {old_mat!r} found {len(hits)} times")
    o, _ = hits[0]
    enc = new_mat.encode('utf-8')
    b[o:o + 4 + len(old_mat.encode('utf-8'))] = struct.pack('<I', len(enc)) + enc
    longest = max(len(s.encode('utf-8')) for _, s in strings if s != old_mat)
    struct.pack_into('<I', b, max_off, max(longest, len(enc)))
    with open(dst, 'wb') as f:
        f.write(b)


def derive_material(doc, filename, color):
    """A copy of a .mat document at `filename` whose colour texture is `color`.

    The copy's own objects get new `res:` ids the way vanilla's crowd materials differ from
    each other: same namespace (words 2 and 3), new first word. References into the imported
    templates keep theirs. Two loose materials that defined the same ids with different
    textures would be asking the game which one wins."""
    doc = copy.deepcopy(doc)
    own = {o['ID'] for o in doc['Objects'] if 'ID' in o}
    remap = {}
    for old in own:
        _, w1, w2, w3 = old.split(':')
        crc = zlib.crc32(f"{filename.lower()}|{old}".encode()) & 0xffffffff
        remap[old] = f"res:{crc:08X}:{w2}:{w3}"

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, str) and x in remap:
            return remap[x]
        return x
    doc = walk(doc)
    doc['Filename'] = filename

    found = 0
    for obj in doc['Objects']:
        for comp in obj.get('Components', []):
            if comp.get('Type') == 'BSMaterial::MRTextureFile' and comp.get('Index') == 0:
                comp['Data']['FileName'] = color
                found += 1
    if found != 1:
        raise RecipeError(f"{filename}: the base material has {found} colour textures, not 1")
    return doc


def colour_texture(doc):
    for obj in doc['Objects']:
        for comp in obj.get('Components', []):
            if comp.get('Type') == 'BSMaterial::MRTextureFile' and comp.get('Index') == 0:
                return comp['Data']['FileName']
    raise RecipeError("the base material has no colour texture")


def under(root, *parts):
    return os.path.join(root, *[p.replace('\\', os.sep) for p in parts])


def game_rel(path, top):
    """`path` relative to its `top` folder (Meshes, Materials, Textures), backslashed."""
    bits = os.path.normpath(path).split(os.sep)
    low = [x.lower() for x in bits]
    if top.lower() not in low:
        raise RecipeError(f"{path} is not under a {top} folder")
    i = len(low) - 1 - low[::-1].index(top.lower())
    return '\\'.join(bits[i + 1:])


# --- the bake -------------------------------------------------------------------------------

def head_info(r, head):
    """Where a head's variant files go, and the material they derive from."""
    mat_rel = nif_material(head)                                   # Materials\...\x.mat
    mat_file = next((p for p in (under(d, mat_rel) for d in r['data']) if os.path.exists(p)),
                    None)
    if mat_file is None:
        raise RecipeError(f"{head}: material {mat_rel} not found under the data folders")
    with open(mat_file, encoding='utf-8') as f:
        doc = json.load(f)
    color = colour_texture(doc)                                    # Data\Textures\...\x.dds
    tex_dir = os.path.dirname(color.split('\\', 1)[1] if color.lower().startswith('data\\')
                              else color)
    return {'mat_rel': mat_rel, 'doc': doc,
            'meshes': os.path.join(game_rel(os.path.dirname(head), 'Meshes'), 'Variants'),
            'materials': os.path.join(os.path.dirname(mat_rel), 'Variants'),
            'textures': os.path.join(tex_dir, 'variants')}


def bake(r, force=False, dry_run=False, log=print):
    opts = read_options(r)
    heads = find_heads(r['heads'])
    space = variant_space(r, opts, heads)
    chosen = pick(space, r['limit'], r['seed'])
    log(f"{len(space)} combinations over {len(heads)} head(s); baking {len(chosen)}")
    if dry_run:
        for v in chosen:
            log(f"  {v['name']}")
        return chosen

    m = uv_transfer.read_map(r['uvmap'])
    roles = r['parts']
    missing = [str(p) for p in m['parts'] if str(p) not in roles]
    if missing:
        raise RecipeError(f"[parts] doesn't say what paints: {', '.join(missing)}")
    cache, infos, manifest, pngs = {}, {}, [], set()
    out = r['out']
    for v in chosen:
        info = infos.setdefault(v['head'], head_info(r, v['head']))
        name = v['name']
        tex_rel = os.path.join(info['textures'], name + '_color.png')
        mat_game = os.path.join(info['materials'], name + '.mat').replace(os.sep, '\\')
        nif_rel = os.path.join(info['meshes'], name + '.nif')
        dds = under(out, os.path.splitext(tex_rel)[0] + '.dds')

        if force or not os.path.exists(dds):
            face, hands = opts.tones[v['tone']]
            layers = [(load_texture(r, p, cache), None if c is None else parse_color(c), 1.0)
                      for _, p, c in v['layers']]
            face_img = composite(load_texture(r, face, cache), layers)
            textures = {}
            for part, role in roles.items():
                if role == 'face':
                    textures[part] = face_img
                elif role == 'hands':
                    textures[part] = load_texture(r, hands, cache)
                elif role == 'eyes':
                    textures[part] = load_texture(r, v['eye'], cache)
                elif role.startswith('#'):
                    textures[part] = parse_color(role)[:3]
                else:
                    textures[part] = load_texture(r, role, cache)
            img = uv_transfer.paint(m, textures, size=r['size'])
            png = under(out, tex_rel)
            os.makedirs(os.path.dirname(png), exist_ok=True)
            uv_transfer.save_image(img[..., :3], png)
            pngs.add(os.path.dirname(png))

        color_game = 'Data\\' + os.path.splitext(tex_rel)[0].replace(os.sep, '\\') + '.dds'
        doc = derive_material(info['doc'], mat_game, color_game)
        mat_file = under(out, mat_game)
        os.makedirs(os.path.dirname(mat_file), exist_ok=True)
        with open(mat_file, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(doc, f, indent=2)

        nif_file = under(out, 'Meshes', nif_rel)
        os.makedirs(os.path.dirname(nif_file), exist_ok=True)
        retarget_nif(v['head'], nif_file, info['mat_rel'], mat_game)
        stem = os.path.splitext(v['head'])[0]
        companion = next((stem + s for s in (FACEBONES + '.nif', '_faceBones.nif')
                          if os.path.exists(stem + s)), None)
        if companion:
            retarget_nif(companion, under(out, 'Meshes', info['meshes'], name + FACEBONES + '.nif'),
                         info['mat_rel'], mat_game)
        manifest.append({'name': name, 'head': os.path.basename(v['head']),
                         'nif': nif_rel.replace(os.sep, '\\'), 'material': mat_game,
                         'texture': color_game})
        log(f"  {name}")

    if pngs:
        convert_dds(pngs, log)
    path = os.path.join(r['_dir'], r['_name'] + '.variants.json')     # not in the mod
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'race': r['race'], 'variants': manifest}, f, indent=2)
    log(f"Wrote {path}")
    return chosen


def convert_dds(folders, log):
    import sf_texconv
    texconv = sf_texconv.find_texconv(None)
    if not texconv:
        raise RecipeError("texconv.exe not found -- set TEXCONV")
    for folder in sorted(folders):
        jobs, _ = sf_texconv.plan(folder, sf_texconv.DEFAULT_COLOR_FORMAT, False)
        failed = sf_texconv.convert(texconv, jobs)
        if failed:
            raise RecipeError(f"texconv failed on {len(failed)} file(s) in {folder}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('bake', help="bake the variants a recipe describes")
    b.add_argument('recipe')
    b.add_argument('--dry-run', action='store_true', help="list the variants it would bake")
    b.add_argument('--force', action='store_true', help="re-bake textures that already exist")
    b.add_argument('--limit', type=int,
                   help="override the recipe's limit; a smaller one picks a subset of its set")
    a = ap.parse_args(argv)
    try:
        r = load_recipe(a.recipe)
        if a.limit is not None:
            r['limit'] = a.limit
        bake(r, force=a.force, dry_run=a.dry_run)
    except RecipeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
