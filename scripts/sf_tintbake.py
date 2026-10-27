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

A head's body types are one head: <head>.nif (or <head>_average.nif, as a '_average' shape key
exports it), <head>_thin.nif and <head>_overweight.nif share one UV layout, so each variant is
baked once and written as <name>.nif, <name>_thin.nif and <name>_overweight.nif (each with its
companion), all on the one material. The manifest lists them under "nifs", by body type.

With a [tail] table, it also writes the race's tail once per skin tone in use, its material
switched to that tone's body texture: crowds have no skin tones, so a tail that matches its head
has to be a copy too. The plugin builder gives each head armor the tail for its tone. Run one
recipe per sex: each bakes that sex's tail, and the builder puts the male tails in the tail
addons' male model and the female tails in their female model.

It writes a manifest, <recipe name>.variants.json beside the recipe, that the plugin builder reads to write the
records. Normal, rough, metal and AO are shared by every variant of a head and are not touched.

The recipe (TOML; relative paths are relative to the recipe file):

    race = "FSFFoxRace"
    phenotype = "male_fox_md1"        # the face skin-tone entry the faces start from
    sex = "male"                      # optional: taken from the phenotype's prefix
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
    "CanineMaleHead" = "face"
    "CanineLeftEye" = "eyes"
    "CanineRightEye" = "eyes"
    "CanineHands" = "hands"
    "CanineMaleMouth" = "teeth"
    "CanineMaleTongue" = "teeth"

    [[layers]]                        # composited over the skin tone in stack order
    slot = "Dermaesthetic"            # options: the tone's chargen filter, as the creator offers
    code = "d"
    [[layers]]
    slot = "Complexion1"              # options: the group of that name
    code = "c"
    optional = true                   # "none" is an option too
    weights = { none = 100 }          # optional, any option table: see Weights below

    [eyes]
    code = "e"
    weights = { Dead = 0 }            # EyeColor options; 0 = never picked

    [teeth]                           # used when a part is painted "teeth"
    code = "t"
    weights = { Teeth_Clean = 80, Teeth_Dirty = 20 }   # TeethCustomization options

    [beards]                          # optional: a beard per variant, fitted to its head
    code = "b"
    percent = 50                      # about how many variants have one: 100 all, 0 none
    folder = "Beards"                 # under `heads`: <head>_<beard>[_thin|_overweight].nif
    colors = "FSFFox_Crowd_Beard_Colors"   # the Simple AVM group its addon names (colour)

    [tail]                            # optional: a tail per skin tone, to match the heads
    race = "FSFFoxRace"               # whose skin has the tail (default: the recipe's race)
    slot = 15                         # the tail addon's body slot
    nif = "Actors/FSFCanine/Mesh/Tail/CanineMaleTail.nif"   # optional: this sex's tail, under
                                      # Meshes; default the addon's model for the recipe's sex
                                      # (MOD2 male, MOD3 female)

A part is painted with "face" (the composite), "hands" (the tone's hands texture), "eyes" (an
EyeColor option), "teeth" (a TeethCustomization option), a texture -- a file path, or a path
under the data folders -- or #rrggbb.
A layer can name `files = [...]` instead of using the race's options, and a mask layer
(*_mask textures) takes `colors = ["#rrggbb", ...]`.

Names say what is in them: Crowd_Head_Fox_md1_sk2_d1c3e5 is head Crowd_Head_Fox_md1, skin
tone 2, option 1 of layer d, option 3 of layer c (0 = none), eye colour 5; a part painted
"teeth" adds t<n>, the teeth option. With [beards] bRuff01 (or b0, none) follows; the beard
doesn't change the texture, so the texture, material and nifs are named without it. Each variant gets one of its head's beards or none,
`percent` of the time, picked stably by name.

Beards: a crowd head's jaw and chin are in its mesh, and nothing morphs a beard to fit, so each
beard is exported per head and body type into `heads`\\Beards. Its colour comes from the AVM
group its addon names (`colors`), not the face texture; the plugin builder makes the addon. Option numbers count
from 1 in the race's own lists, so they don't move when the recipe weights one 0.

Weights: `weights = { Label = n }` in [eyes], [teeth] or a [[layers]] entry makes an option more
or less likely. Labels are the race's (case doesn't matter), "none" for an optional layer's
no-option, a file's name for `files`. Weights are relative; an option not named weighs 50, and 0
means never. A variant weighs its options' weights multiplied, and the `limit` sample is a
weighted pick: the same set every run, and with no weights the same set as ever.

Layers composite the way the chargen face does, in the stack's order: a full-colour layer
(*_color) is laid over what's below by its own alpha (proven in game for dermaesthetics); a mask
layer blends its colour in by mask x intensity (not yet proven against a vanilla bake).
"""
import argparse
import copy
import hashlib
import itertools
import json
import math
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
from pyn.sf_files import nif_header_strings         # noqa: E402

ROLES = ('face', 'hands', 'eyes', 'teeth')
DERMAESTHETIC = 'Dermaesthetic'
CHARGEN_DERMAESTHETIC = 'Chargen_Dermaesthetic'
STACK = 'PostBlendFaceCustomizationLayers'
EYE_COLOR = 'EyeColor'
TEETH = 'TeethCustomization'
FACEBONES = '_facebones'
TAIL_SLOT = 15                       # the body slot a race's tail addon is on


class RecipeError(Exception):
    pass


# --- the recipe -----------------------------------------------------------------------------

# Every name a recipe may use, per table ('' the top level, 'layers' each [[layers]] entry).
# [parts] keys are the uv map's part names, so they're free. Anything else is a typo the bake
# would otherwise ignore -- [beard] for [beards] baked no beards and said nothing.
RECIPE_KEYS = {
    '': {'race', 'phenotype', 'sex', 'plugin', 'data', 'heads', 'uvmap', 'out', 'tones', 'limit',
         'seed', 'size', 'parts', 'layers', 'eyes', 'teeth', 'beards', 'tail'},
    'layers': {'slot', 'code', 'optional', 'files', 'colors', 'weights'},
    'eyes': {'code', 'weights'},
    'teeth': {'code', 'weights'},
    'beards': {'code', 'percent', 'folder', 'colors'},
    'tail': {'race', 'slot', 'nif'},
}


def check_recipe_keys(r):
    """Refuse a table or key RECIPE_KEYS doesn't know, suggesting the close one."""
    import difflib

    def check(keys, where, known):
        for k in keys:
            if k == 'exclude' and 'weights' in known:
                raise RecipeError(f"{where}: `exclude` is replaced by weights -- give those "
                                  f"options 0, e.g. weights = {{ Dead = 0 }}")
            if k not in known:
                close = difflib.get_close_matches(k, known, n=1)
                raise RecipeError(f"{where}: unknown {k!r}"
                                  + (f" -- did you mean {close[0]!r}?" if close else
                                     f"; known: {', '.join(sorted(known))}"))

    check(r, 'recipe', RECIPE_KEYS[''])
    for table in ('eyes', 'teeth', 'beards', 'tail'):
        if isinstance(r.get(table), dict):
            check(r[table], f"[{table}]", RECIPE_KEYS[table])
    for i, ly in enumerate(r.get('layers') or [], 1):
        check(ly, f"[[layers]] #{i}", RECIPE_KEYS['layers'])


def load_recipe(path):
    with open(path, 'rb') as f:
        r = tomllib.load(f)
    check_recipe_keys(r)
    r['_dir'] = os.path.dirname(os.path.abspath(path))
    r['_name'] = os.path.splitext(os.path.basename(path))[0]
    for key in ('race', 'phenotype', 'data', 'heads', 'uvmap', 'out', 'parts'):
        if key not in r:
            raise RecipeError(f"recipe has no {key!r}")
    r.setdefault('layers', [])
    r.setdefault('eyes', {})
    r['eyes'].setdefault('code', 'e')
    r.setdefault('teeth', {})
    r['teeth'].setdefault('code', 't')
    r.setdefault('limit', 40)
    r.setdefault('seed', 1)
    r.setdefault('size', 1024)
    r.setdefault('sex', 'female' if r['phenotype'].lower().startswith('female') else 'male')
    if r['sex'] not in ('male', 'female'):
        raise RecipeError(f"sex must be male or female, not {r['sex']!r}")
    r['data'] = [recipe_path(r, d) for d in r['data']]
    for key in ('heads', 'uvmap', 'out'):
        r[key] = recipe_path(r, r[key])
    if 'beards' in r:
        r['beards'].setdefault('code', 'b')
        r['beards'].setdefault('percent', 50)
        r['beards'].setdefault('folder', 'Beards')
        check_beards_cfg(r['beards'])
    codes = [ly.get('code') for ly in r['layers']] + [r['eyes']['code']] +         ([r['teeth']['code']] if uses_teeth(r) else []) + \
        ([r['beards']['code']] if 'beards' in r else [])
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
    eyes:   [(label, path)]
    teeth:  [(label, path)]"""
    def __init__(self, tones, slots, derm, eyes, stack, tail=None, teeth=None):
        self.tones, self.slots, self.derm, self.eyes, self.stack = tones, slots, derm, eyes, stack
        self.teeth = teeth or []
        self.tail = tail             # race_tail(), when the recipe asks for tails

    def layer(self, slot, tone):
        if slot == DERMAESTHETIC:
            return self.derm[tone] if tone < len(self.derm) else []
        return self.slots.get(slot, [])


def for_sex(values, sex):
    """The value for `sex` from a race field the record repeats per sex (HSTT, BSTT): male
    first, then female. One value serves both."""
    if not values:
        return None
    return values[1] if sex == 'female' and len(values) > 1 else values[0]


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
    hands = [p for _, p in simple(for_sex([sr.get_string() for sr in race.get_subrecords('HSTT')],
                                          r['sex']))]
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
    opts = Options(list(zip(faces, hands)), slots, derm, simple(EYE_COLOR), stack,
                   teeth=simple(TEETH))
    if 'tail' in r:
        opts.tail = race_tail(R, plugins, r, simple)
    return opts


def race_tail(R, plugins, r, simple):
    """The tail on a race's skin, found by its body slot, and the race's body skin tones.

    Crowds have no skin tones, so a crowd head bakes its tone in; a tail has to come in the
    same tone. This finds the tail addon the player race wears and the body-tone textures its
    material can be switched between."""
    t = r['tail']
    race = R.find_race(plugins, t.get('race', r['race']))
    if race is None:
        raise RecipeError(f"tail race {t.get('race', r['race'])!r} is not in the load order")
    skin = plugins.resolve_form_id(race.get_subrecord('WNAM').get_form_id(), race.plugin)
    bit = 1 << t.get('slot', TAIL_SLOT)
    for sr in skin.get_subrecords('MODL'):
        arma = plugins.resolve_form_id(sr.get_form_id(), skin.plugin)
        bo = arma.get_subrecord('BO64') if arma is not None else None
        if bo is not None and struct.unpack('<Q', bytes(bo.data))[0] & bit:
            break
    else:
        raise RecipeError(f"{race.editor_id}'s skin {skin.editor_id} has no addon on body slot "
                          f"{t.get('slot', TAIL_SLOT)}")
    # The addon's model for this recipe's sex (male and female tails can differ), unless the
    # recipe names its own.
    model = t.get('nif') or R.text(arma, 'MOD3' if r['sex'] == 'female' else 'MOD2')
    tones = [[p for _, p in simple(sr.get_string())] for sr in race.get_subrecords('BSTT')]
    return {'addon': arma.editor_id, 'nif': model, 'body_tones': tones}


# --- the variants ---------------------------------------------------------------------------

def find_heads(folder):
    """The crowd-head nifs in `folder`: every nif except the _facebones companions."""
    names = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith('.nif')
                   and not os.path.splitext(f)[0].lower().endswith(FACEBONES))
    if not names:
        raise RecipeError(f"no head nifs in {folder}")
    return [os.path.join(folder, f) for f in names]


# Body types, by file-name suffix. Vanilla ships every crowd head as <head>.nif (average),
# <head>_thin.nif and <head>_overweight.nif. PyNifly writes one nif per '_' shape key -- the key
# '_' writes the plain one -- and exports from before that said _average for it.
BODY_SUFFIXES = {'_thin': '_thin', '_overweight': '_overweight', '_average': ''}
BODY_NAMES = {'': 'average', '_thin': 'thin', '_overweight': 'overweight'}


def split_body(stem):
    """(head name, body suffix) from a nif's name: 'X_Thin' -> ('X', '_thin'), 'X' -> ('X', '')."""
    for suffix, body in BODY_SUFFIXES.items():
        if stem.lower().endswith(suffix):
            return stem[:-len(suffix)], body
    return stem, ''


def group_heads(paths):
    """{head name: {body suffix: path}}: a head's body types are one head."""
    out = {}
    for path in paths:
        head, body = split_body(os.path.splitext(os.path.basename(path))[0])
        bodies = out.setdefault(head, {})
        if body in bodies:
            raise RecipeError(f"{head} has two {BODY_NAMES[body]} nifs: {bodies[body]}, {path}")
        bodies[body] = path
    return out


def find_beards(heads_folder, cfg, head_names):
    """{head: {beard: {body suffix: path}}} from the heads folder's beard folder.

    A beard is exported per head and body type -- a crowd head's jaw and chin are in its mesh,
    and nothing morphs a beard to fit -- named <head>_<beard>[_thin|_overweight].nif. The head
    is the longest known head name followed by '_', so md1 and md10 don't collide."""
    folder = os.path.join(heads_folder, cfg['folder'])
    if not os.path.isdir(folder):
        return {}
    by_len = sorted(head_names, key=len, reverse=True)
    out = {}
    for f in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(f)
        if ext.lower() != '.nif' or stem.lower().endswith(FACEBONES):
            continue
        name, body = split_body(stem)
        head = next((h for h in by_len if name.lower().startswith(h.lower() + '_')), None)
        if head is None:
            raise RecipeError(f"{os.path.join(folder, f)}: names no head in {heads_folder} "
                              f"(beards are <head>_<beard>.nif)")
        beard = name[len(head) + 1:]
        bodies = out.setdefault(head, {}).setdefault(beard, {})
        if body in bodies:
            raise RecipeError(f"{head}'s {beard} has two {BODY_NAMES[body]} nifs: "
                              f"{bodies[body]}, {os.path.join(folder, f)}")
        bodies[body] = os.path.join(folder, f)
    return out


def write_body_nifs(bodies, out, meshes_rel, name, new_mat):
    """A variant's nifs: each body type's head and its _facebones companion, pointing at the
    variant's material `new_mat`. Returns {body type: nif path under Meshes}."""
    written = {}
    for body, src in sorted(bodies.items()):
        old_mat = nif_material(src)
        nif_rel = os.path.join(meshes_rel, name + body + '.nif').replace(os.sep, '\\')
        dst = under(out, 'Meshes', nif_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        retarget_nif(src, dst, old_mat, new_mat)
        stem = os.path.splitext(src)[0]
        companion = next((stem + s for s in (FACEBONES + '.nif', '_faceBones.nif')
                          if os.path.exists(stem + s)), None)
        if companion:
            retarget_nif(companion, under(out, 'Meshes', meshes_rel, name + body + FACEBONES + '.nif'),
                         old_mat, new_mat)
        written[BODY_NAMES[body]] = nif_rel
    return written


def is_mask(path):
    return os.path.splitext(path)[0].lower().endswith('_mask')


def layer_options(r, ly, opts, tone):
    """A layer's options for one skin tone: [(label, path)], the label what `weights` names --
    the race's label, or a `files` entry's file name without its extension."""
    if 'files' in ly:
        return [(os.path.splitext(os.path.basename(f))[0], recipe_path(r, f)) for f in ly['files']]
    if ly['slot'] not in opts.stack and ly['slot'] != DERMAESTHETIC:
        raise RecipeError(f"{ly['slot']!r} is not a slot in {STACK}")
    return opts.layer(ly['slot'], tone)


def layer_choices(r, ly, opts, tone):
    """A layer's choices for one skin tone: [(code, path or None, colour or None, weight)],
    leaving out the ones weighted 0.

    The code is the option's 1-based place in the race's list (0 for "none", whose label in
    `weights` is "none"); a mask layer's is that plus a letter for the colour, and its colours
    share the option's weight."""
    found = layer_options(r, ly, opts, tone)
    labels = (['none'] if ly.get('optional') else []) + [lab for lab, _ in found]
    # A dermaesthetic's options differ by tone, so a label is known if any tone offers it.
    known = {'none'} | {lab for t in range(len(opts.tones)) for lab, _ in layer_options(r, ly, opts, t)}
    weights = dict(zip(labels, option_weights(ly, labels, f"layer {ly.get('code')}", known)))
    out = [('0', None, None, weights['none'])] if ly.get('optional') else []
    for i, (label, path) in enumerate(found, 1):
        code, w = f"{i}", weights[label]
        if is_mask(path):
            colors = ly.get('colors')
            if not colors:
                raise RecipeError(f"layer {ly['code']}: {path} is a mask; give `colors`")
            out += [(code + 'abcdefghijklmnopqrstuvwxyz'[j], path, c, w)
                    for j, c in enumerate(colors)]
        else:
            out.append((code, path, None, w))
    return [ch for ch in out if ch[3] > 0]


# An option `weights` doesn't name weighs this. Weights are relative, so naming one option 80
# and another 20 makes them 80:20, and an unnamed third sits between them at 50.
DEFAULT_WEIGHT = 50


def option_weights(table, labels, what, known=None):
    """The weight of each of `labels` from `table`'s `weights = { Label = n }`: unnamed options
    DEFAULT_WEIGHT, 0 never. Labels match case-insensitively; one the options don't have
    (`known`, default `labels`) is refused, as is a weight that isn't a number >= 0."""
    if 'exclude' in table:
        raise RecipeError(f"{what}: `exclude` is replaced by weights -- give those options 0, "
                          f"e.g. weights = {{ {(table['exclude'] or ['Dead'])[0]} = 0 }}")
    given = table.get('weights') or {}
    known = {k.lower() for k in (known if known is not None else labels)}
    unknown = [k for k in given if k.lower() not in known]
    if unknown:
        raise RecipeError(f"{what}: weights name {', '.join(unknown)}, which isn't an option; "
                          f"the options are {', '.join(labels)}")
    for k, w in given.items():
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0:
            raise RecipeError(f"{what}: weight of {k} must be a number >= 0, not {w!r}")
    low = {k.lower(): w for k, w in given.items()}
    return [low.get(lab.lower(), DEFAULT_WEIGHT) for lab in labels]


def uses_teeth(r):
    """Does any part paint with the race's teeth options? Only then are teeth a dimension, so a
    recipe that paints the mouth one fixed texture keeps its names."""
    return 'teeth' in (r.get('parts') or {}).values()


def check_beards_cfg(cfg):
    """[beards] percent is a whole number 0..100: 100 every variant has a beard, 0 none does."""
    p = cfg.get('percent')
    if isinstance(p, bool) or not isinstance(p, int) or not 0 <= p <= 100:
        raise RecipeError(f"[beards] percent must be a whole number from 0 to 100, not {p!r}")


def _unit(seed, tag, name):
    """A stable number in [0, 1) from the seed and a name: the same pick every run."""
    h = hashlib.sha256(f"{seed}:{tag}:{name}".encode()).digest()
    return int.from_bytes(h[:8], 'big') / 2 ** 64


def beard_choice(r, stem, bodies, beards, base):
    """The variant `base`'s beard: (code, beard name or None, {body suffix: nif}).

    With [beards], about `percent` of a head's variants get one of its fitted beards -- 100 all,
    0 none -- picked stably from the base name, so the same recipe gives the same beards."""
    cfg = r.get('beards')
    if cfg is None:
        return None, None, {}
    mine = sorted((beards or {}).get(stem, {}).items())
    for beard, nifs in mine:
        missing = [BODY_NAMES[b] for b in bodies if b not in nifs]
        if missing:
            raise RecipeError(f"{stem}'s beard {beard} has no {', '.join(missing)} nif; a beard "
                              f"is fitted per body type")
    seed = r.get('seed', 1)
    if not mine or _unit(seed, 'beard', base) >= cfg['percent'] / 100:
        return cfg['code'] + '0', None, {}
    beard, nifs = mine[int(_unit(seed, 'which', base) * len(mine))]
    return cfg['code'] + beard, beard, nifs


def variant_space(r, opts, heads, beards=None, log=print):
    """Every variant the recipe allows, as dicts with the name and what goes into it.

    `beards` is find_beards(): with a [beards] table each variant also gets a beard or none
    (beard_choice). The beard doesn't change the texture, so 'base' -- the name without the
    beard -- names the baked texture, material and nifs. At percent 100 a head with no beard
    fitted is left out, with a warning to `log`; none left at all is an error."""
    tones = r.get('tones', list(range(len(opts.tones))))
    bad = [t for t in tones if not 0 <= t < len(opts.tones)]
    if bad:
        raise RecipeError(f"skin tone(s) {bad} out of range 0..{len(opts.tones) - 1}")
    def weighted(table, options, what):
        ws = option_weights(table, [lab for lab, _ in options], what)
        return [(f"{i}", p, w) for i, ((_, p), w) in enumerate(zip(options, ws), 1) if w > 0]

    eyes = weighted(r['eyes'], opts.eyes, '[eyes]')
    if not eyes:
        raise RecipeError("no eye colours to choose from")
    teeth = [(None, None, 1)]
    if uses_teeth(r):
        teeth = weighted(r['teeth'], opts.teeth, '[teeth]')
        if not teeth:
            raise RecipeError(f"a part is painted 'teeth' but {TEETH} offers nothing to choose")

    out = []
    cfg = r.get('beards')
    skipped = []
    for stem, bodies in group_heads(heads).items():
        if cfg is not None and cfg['percent'] >= 100 and not (beards or {}).get(stem):
            skipped.append(stem)
            continue
        head = bodies.get('', next(iter(bodies.values())))      # the average, if there is one
        for tone in tones:
            combos = [[]]
            for ly in r['layers']:
                choices = layer_choices(r, ly, opts, tone)
                if not choices:
                    raise RecipeError(f"layer {ly['code']} has no options for skin tone {tone}")
                combos = [c + [(ly, ch)] for c in combos for ch in choices]
            for combo in combos:
                for (eye_code, eye, eye_w), (teeth_code, tooth, teeth_w) in \
                        itertools.product(eyes, teeth):
                    # The option codes run together (d1c1e5t1): a code is letters, an option
                    # number digits, so they still read apart, and names stay short.
                    codes = [ly['code'] + ch[0] for ly, ch in combo]
                    codes.append(r['eyes']['code'] + eye_code)
                    if teeth_code:
                        codes.append(r['teeth']['code'] + teeth_code)
                    base = f"{stem}_sk{tone}_{''.join(codes)}"
                    beard_code, beard, beard_nifs = beard_choice(r, stem, bodies, beards, base)
                    weight = eye_w * teeth_w
                    for _, ch in combo:
                        weight *= ch[3]
                    out.append({'name': base + (beard_code or ''), 'weight': weight,
                                'base': base, 'stem': stem, 'head': head, 'bodies': bodies,
                                'tone': tone,
                                'layers': [(ly.get('slot'), ch[1], ch[2])
                                           for ly, ch in combo if ch[1]],
                                'eye': eye, 'teeth': tooth, 'beard': beard,
                                'beard_nifs': beard_nifs})
    if skipped:
        if not out:
            raise RecipeError(f"no head has a beard in {cfg['folder']}, and the recipe gives "
                              f"every variant one (percent = 100)")
        log(f"WARNING: left out {', '.join(skipped)}: no beard in {cfg['folder']}, and the "
            f"recipe gives every variant one (percent = 100)")
    return out


def pick(variants, limit, seed):
    """`limit` variants, a weighted pick by each variant's 'weight' (default 1).

    Random-looking but stable: each name hashes under `seed` to a number u in [0, 1), and the
    `limit` lowest -ln(1 - u) / weight win -- a weighted draw without replacement, the same set
    every time. -ln(1 - u) rises with u, so when the weights are equal it keeps the names that
    hash lowest, as the unweighted pick did. Adding a head or an option only brings in the few
    new names that beat the old ones, instead of reshuffling."""
    def key(v):
        u = int.from_bytes(hashlib.sha256(f"{seed}:{v['name']}".encode()).digest(), 'big') / 2 ** 256
        return -math.log1p(-u) / v.get('weight', 1)
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


def same_path(a, b):
    return a.replace('/', '\\').lower() == b.replace('/', '\\').lower()


def derive_material(doc, filename, color, old=None):
    """A copy of a .mat document at `filename` whose colour texture is `color`.

    The colour texture is the slot-0 texture, or, in a material with several (a body material
    keeps a mask in a second layer's slot 0), the one whose path is `old`.

    The copy's own objects get new `res:` ids the way vanilla's crowd materials differ from
    each other: same namespace (words 2 and 3), new first word. References into the imported
    templates keep theirs. Two loose materials that defined the same ids with different
    textures would be asking the game which one wins."""
    doc = copy.deepcopy(doc)
    own = {o['ID'] for o in doc['Objects'] if 'ID' in o}
    remap = {}
    for rid in own:
        _, w1, w2, w3 = rid.split(':')
        crc = zlib.crc32(f"{filename.lower()}|{rid}".encode()) & 0xffffffff
        remap[rid] = f"res:{crc:08X}:{w2}:{w3}"

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
            if comp.get('Type') == 'BSMaterial::MRTextureFile' and comp.get('Index') == 0 \
                    and (old is None or same_path(comp['Data']['FileName'], old)):
                comp['Data']['FileName'] = color
                found += 1
    if found != 1:
        raise RecipeError(f"{filename}: the base material has {found} colour textures"
                          f"{' named ' + old if old else ''}, not 1")
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

def data_file(r, *parts):
    """The first data folder's copy of a game path, or None."""
    return next((p for p in (under(d, *parts) for d in r['data']) if os.path.exists(p)), None)


def load_material(r, mat_rel, who):
    path = data_file(r, mat_rel)
    if path is None:
        raise RecipeError(f"{who}: material {mat_rel} not found under the data folders")
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_material(out, mat_game, doc):
    path = under(out, mat_game)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, indent=2)


def bake_tails(r, tail, tones, log):
    """One copy of the race's tail per skin tone in `tones`, its material switched to that tone's
    body texture. Returns {tone: nif path under Meshes}.

    The body-tone group is whichever of the race's groups holds the tail material's current
    colour texture, so the tail keeps the texture layout it was painted for."""
    nif = data_file(r, 'Meshes', tail['nif'])
    if nif is None:
        raise RecipeError(f"tail nif {tail['nif']} not found under the data folders")
    mat_rel = nif_material(nif)
    doc = load_material(r, mat_rel, nif)
    slot0 = [c['Data']['FileName'] for o in doc['Objects'] for c in o.get('Components', [])
             if c.get('Type') == 'BSMaterial::MRTextureFile' and c.get('Index') == 0]
    for group in tail['body_tones']:
        old = next((s for s in slot0 for g in group if same_path(s, 'Data\\' + g)), None)
        if old:
            break
    else:
        raise RecipeError(f"{mat_rel}: no colour texture is one of the race's body skin tones")
    stem = os.path.splitext(os.path.basename(tail['nif']))[0]
    mat_stem = os.path.splitext(os.path.basename(mat_rel))[0]
    out = {}
    for tone in sorted(tones):
        mat_game = os.path.join(os.path.dirname(mat_rel), 'Variants',
                                f"{mat_stem}_sk{tone}.mat").replace(os.sep, '\\')
        write_material(r['out'], mat_game,
                       derive_material(doc, mat_game, 'Data\\' + group[tone], old=old))
        nif_rel = os.path.join(os.path.dirname(tail['nif']), 'Variants',
                               f"{stem}_sk{tone}.nif").replace(os.sep, '\\')
        dst = under(r['out'], 'Meshes', nif_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        retarget_nif(nif, dst, mat_rel, mat_game)
        out[tone] = nif_rel
        log(f"  tail {nif_rel}")
    return out


def head_info(r, head):
    """Where a head's variant files go, and the material they derive from."""
    mat_rel = nif_material(head)                                   # Materials\...\x.mat
    doc = load_material(r, mat_rel, head)
    color = colour_texture(doc)                                    # Data\Textures\...\x.dds
    tex_dir = os.path.dirname(color.split('\\', 1)[1] if color.lower().startswith('data\\')
                              else color)
    return {'mat_rel': mat_rel, 'doc': doc,
            'meshes': os.path.join(game_rel(os.path.dirname(head), 'Meshes'), 'Variants'),
            'materials': os.path.join(os.path.dirname(mat_rel), 'Variants'),
            'textures': os.path.join(tex_dir, 'variants')}


def manifest_entry(v, nifs, mat_game, color_game):
    """A variant's manifest entry. 'nifs' (by body type) are the baked head; 'beard_nifs' (by
    body type, paths under Meshes) the beard fitted to it, used as exported."""
    entry = {'name': v['name'], 'head': os.path.basename(v['head']), 'tone': v['tone'],
             'nif': nifs.get('average', next(iter(nifs.values()))),
             'nifs': nifs, 'material': mat_game, 'texture': color_game}
    if v.get('beard'):
        entry['beard'] = v['beard']
        entry['beard_nifs'] = {BODY_NAMES[b]: game_rel(p, 'Meshes')
                               for b, p in sorted(v['beard_nifs'].items())}
    return entry


def bake(r, force=False, dry_run=False, log=print):
    opts = read_options(r)
    heads = find_heads(r['heads'])
    groups = group_heads(heads)
    beards = find_beards(r['heads'], r['beards'], list(groups)) if 'beards' in r else None
    space = variant_space(r, opts, heads, beards, log=log)
    chosen = pick(space, r['limit'], r['seed'])
    log(f"{len(space)} combinations over {len(groups)} head(s); baking {len(chosen)}")
    for head, bodies in groups.items():
        fitted = sorted((beards or {}).get(head, {}))
        log(f"  {head}: {', '.join(BODY_NAMES[b] for b in sorted(bodies))}"
            + (f"; beards {', '.join(fitted) or 'none'}" if beards is not None else ''))
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
    baked = {}                           # base name -> its nifs: one bake serves every beard
    out = r['out']
    for v in chosen:
        info = infos.setdefault(v['head'], head_info(r, v['head']))
        name = v['base']                 # the beard doesn't change the texture
        tex_rel = os.path.join(info['textures'], name + '_color.png')
        mat_game = os.path.join(info['materials'], name + '.mat').replace(os.sep, '\\')
        dds = under(out, os.path.splitext(tex_rel)[0] + '.dds')
        color_game = 'Data\\' + os.path.splitext(tex_rel)[0].replace(os.sep, '\\') + '.dds'
        if name in baked:
            manifest.append(manifest_entry(v, baked[name], mat_game, color_game))
            log(f"  {v['name']} (shares {name})")
            continue

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
                elif role == 'teeth':
                    textures[part] = load_texture(r, v['teeth'], cache)
                elif role.startswith('#'):
                    textures[part] = parse_color(role)[:3]
                else:
                    textures[part] = load_texture(r, role, cache)
            img = uv_transfer.paint(m, textures, size=r['size'])
            png = under(out, tex_rel)
            os.makedirs(os.path.dirname(png), exist_ok=True)
            uv_transfer.save_image(img[..., :3], png)
            pngs.add(os.path.dirname(png))

        write_material(out, mat_game, derive_material(info['doc'], mat_game, color_game))

        baked[name] = write_body_nifs(v['bodies'], out, info['meshes'], name, mat_game)
        manifest.append(manifest_entry(v, baked[name], mat_game, color_game))
        log(f"  {v['name']}")

    if pngs:
        convert_dds(pngs, log)
    result = {'race': r['race'], 'sex': r['sex'], 'variants': manifest}
    if 'beards' in r and r['beards'].get('colors'):
        result['beard_colors'] = r['beards']['colors']
    if opts.tail:
        nifs = bake_tails(r, opts.tail, {v['tone'] for v in chosen}, log)
        result['tail'] = {'addon': opts.tail['addon'], 'nifs': {str(k): v for k, v in nifs.items()}}
    path = os.path.join(r['_dir'], r['_name'] + '.variants.json')     # not in the mod
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=2)
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
