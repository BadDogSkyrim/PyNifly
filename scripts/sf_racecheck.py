"""Audit a Starfield custom race for the things that silently break a head or a body.

Every check here corresponds to a failure that actually cost a debugging session: a head that
renders black, renders invisible, or crashes the Creation Kit during FaceGen, and a body or
pair of hands that simply never appear. Most of them are silent in the CK -- the whole point
of this tool is to make them loud.

    python scripts/sf_racecheck.py --data "C:\\...\\Starfield\\Data"           # whole load order
    python scripts/sf_racecheck.py --data ... --race FSFFoxRace
    python scripts/sf_racecheck.py --data ... --plugin FSFPlayer_FOX.esm      # + its masters
    python scripts/sf_racecheck.py --data ... -v -o report   # -> report.txt
    python scripts/sf_racecheck.py --data ... --sex male
    python scripts/sf_racecheck.py --data "C:\\...\\Starfield\\Data,C:\\...\\Starfield Assets" ...

--data takes a comma-separated list of folders, searched in order for every file: give the game's
Data folder first and a folder of unpacked vanilla assets after it, and loose mod files win over
vanilla the way they do in game. Plugins are loaded from the first folder.

What gets loaded: with --plugin, that plugin and all its masters, recursively. Without it, the
game's active load order -- Starfield.esm and the official masters, then whatever Plugins.txt
marks active, in order. Every lookup, --race included, then takes the winning override across
everything loaded, the way the game does. The race is auto-detected when the mods (anything
outside the game's own plugins) define exactly one.

Plugins are read with esplib. NIF checks need PyNifly's NiflyDLL and are skipped with a note if
it can't be loaded.

Exit code is 1 if anything FAILed, so it can gate a build.
"""

import argparse
import collections
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'io_scene_nifly'))

import esplib.plugin
from esplib import LoadOrder, Plugin, PluginSet
from pyn import sf_matchain
from pyn.sf_cdb import load_cdb
from pyn.sf_morph import MorphFile
from pyn.sf_materials import material_id

FAIL, WARN, OK, INFO = 'FAIL', 'WARN', 'ok', 'info'

# The race's chargen blocks, in the order the record stores them. --sex narrows this to one.
SEXES = ('MALE', 'FEMALE')


def npc_sex(npc):
    """'MALE' or 'FEMALE' from ACBS bit 0, or None if the NPC has no ACBS."""
    acbs = npc.get_subrecord('ACBS')
    if acbs is None or acbs.size < 4:
        return None
    return 'FEMALE' if acbs.get_uint32() & 1 else 'MALE'


def label_sex(name):
    """The sex a face skin tone label is for, from its prefix -- or None if it has none.
    'female' is tested first: it ends in 'male', but a label starts with its sex."""
    for sx in ('FEMALE', 'MALE'):
        if name.lower().startswith(sx.lower()):
            return sx
    return None


# Head-part types from HDPT PNAM, as seen in vanilla.
HDPT_FACE = 1
HDPT_RIGHT_EYE, HDPT_LEFT_EYE = 2, 12
HDPT_HAIR, HDPT_FACIAL_HAIR = 3, 4

# The four base maps a FaceGen bake reads from the race's FCTP directory, by filename
# convention. Only the albedo has an AVMD route; the rest are filename-only.
FCTP_SUFFIXES = ['_normal.dds', '_rough.dds', '_ao.dds']


def text(rec, sig):
    """A subrecord's string value, or None when the record does not carry it."""
    sr = rec.get_subrecord(sig) if rec is not None else None
    return sr.get_string() if sr is not None else None


class Report:
    def __init__(self):
        self.findings = []

    def add(self, level, area, msg, detail=None):
        self.findings.append((level, area, msg, detail))

    def fail(self, area, msg, detail=None):
        self.add(FAIL, area, msg, detail)

    def warn(self, area, msg, detail=None):
        self.add(WARN, area, msg, detail)

    def ok(self, area, msg, detail=None):
        self.add(OK, area, msg, detail)

    def info(self, area, msg, detail=None):
        self.add(INFO, area, msg, detail)

    def count(self, level):
        return sum(1 for f in self.findings if f[0] == level)

    def summary(self):
        return (f"{self.count(FAIL)} failed, {self.count(WARN)} warnings, "
                f"{self.count(OK)} passed")

    def render(self, verbose, out=None):
        out = sys.stdout if out is None else out
        order = [FAIL, WARN, OK, INFO]
        shown = order if verbose else [FAIL, WARN]
        area = None
        for level in order:
            if level not in shown:
                continue
            for lv, ar, msg, detail in self.findings:
                if lv != level:
                    continue
                if ar != area:
                    print(f"\n-- {ar} " + "-" * max(0, 58 - len(ar)), file=out)
                    area = ar
                print(f"  [{lv:4}] {msg}", file=out)
                if detail:
                    for line in (detail if isinstance(detail, list) else [detail]):
                        print(f"         {line}", file=out)
        print(f"\n{'=' * 64}\n{self.summary()}", file=out)
        if not verbose and self.count(OK):
            print("(-v shows passing checks)", file=out)
        return self.count(FAIL)


# --- file helpers ---------------------------------------------------------------------------

def data_path(data, *parts):
    """A path under the data folders `data` (a list). The first folder that has it wins, the
    way a loose file overrides an archive; when none does, the path under the first folder."""
    rel = [p.replace('\\', os.sep).replace('/', os.sep) for p in parts]
    paths = [os.path.join(root, *rel) for root in data]
    return next((path for path in paths if os.path.exists(path)), paths[0])


def exists(data, *parts):
    return os.path.exists(data_path(data, *parts))


def is_dds(path):
    """Whether a texture path names a .dds -- the only texture format the game reads."""
    return os.path.splitext(path.strip())[1].lower() == '.dds'


NOT_DDS_ADVICE = ("Starfield reads DDS textures only. Convert the source (scripts/sf_texconv.py "
                  "does a folder at a time) and point the path at the .dds.")


def list_dir(data, *parts):
    """Every file name in this folder across all the data folders -- a mod's folder in the game
    Data and the vanilla folder of the same name in unpacked assets are one folder to the game."""
    rel = [p.replace('\\', os.sep).replace('/', os.sep) for p in parts]
    names = []
    for root in data:
        folder = os.path.join(root, *rel)
        if os.path.isdir(folder):
            names += [n for n in os.listdir(folder) if n not in names]
    return names


def mesh_vertex_count(path):
    """Vertex count of an external Starfield .mesh, without the DLL.

    Layout: uint32 version, uint32 indexCount, uint16 indices, float scale, uint32 flags,
    uint32 vertexCount. Validated against 44 loose meshes including vanilla heads.
    """
    with open(path, 'rb') as f:
        buf = f.read(64)
        _ver, icount = struct.unpack_from('<II', buf, 0)
        off = 8 + icount * 2
        f.seek(off)
        _scale, _flags, vcount = struct.unpack('<fII', f.read(12))
    return vcount


def mesh_rel(mesh_name):
    """A NIF's meshName -> its Data-relative path. Names come with or without the geometries
    prefix and with or without the .mesh extension."""
    n = mesh_name.replace('/', '\\')
    if not n.lower().startswith('geometries\\'):
        n = 'geometries\\' + n
    if not n.lower().endswith('.mesh'):
        n += '.mesh'
    return n


def resolve_mesh(data, mesh_name):
    """A NIF's meshName -> a path under Data."""
    return data_path(data, mesh_rel(mesh_name))


# --- morph checks ---------------------------------------------------------------------------

ZERO_RECORD_CRASH = ("No key moves a vertex. The CK's MorphRenderPass logs \"invalid buffers\" "
                     "and crashes on it.")


def check_part_morphs(rep, data, hdpt, plugins):
    """A head part's morphs -- facial hair, eyebrows, ears, anything but the race's face, which
    check_morphs judges against the race's declared keys.

    Unlike the face, a part may leave keys empty (vanilla beards leave 9+), so only a file with
    no morph data at all is a failure: the CK crashes on it. A part with no MNAM has no morphs."""
    pnam = hdpt.get_subrecord('PNAM')
    if pnam is not None and pnam.get_uint32() == HDPT_FACE:
        return
    if hdpt.get_subrecord('MNAM') is None:
        return
    who = hdpt.editor_id or '?'
    mrph = plugins.resolve_reference(hdpt, 'MNAM')
    if mrph is None:
        rep.fail('morphs', f"{who}: MNAM points at no MRPH record")
        return
    verts = model_mesh_verts(data, text(hdpt, 'MODL'))
    for sig, label in (('TCMP', 'chargen'), ('TMPP', 'performance')):
        rel = text(mrph, sig)
        if not rel:
            continue
        f = data_path(data, rel, 'morph.dat')
        if not os.path.exists(f):
            rep.fail('morphs', f"{who}: no {label} morph.dat", rel)
            continue
        try:
            m = MorphFile.from_file(f)
        except Exception as e:
            rep.fail('morphs', f"{who}: {label} morph.dat could not be read: {e}", f)
            continue
        if not m.records:
            rep.fail('morphs', f"{who}: {label} morph.dat has {len(m.morph_names)} keys and no "
                               f"morph data -- crashes the CK", [rel, ZERO_RECORD_CRASH])
        elif verts is not None and m.num_vertices != verts:
            rep.fail('morphs', f"{who}: {label} morph has {m.num_vertices} verts, its mesh has "
                               f"{verts}", rel)
        else:
            rep.ok('morphs', f"{who}: {label} morph ({len(m.morph_names)} keys)")


def check_morphs(rep, data, mrph, declared_names, head_verts, composed_names=None):
    """The single most expensive class of bug: morphs the engine cannot use."""
    if mrph is None:
        rep.fail('morphs', "Head part has no MRPH (Morphable Object) record")
        return

    for sig, label in (('TCMP', 'chargen'), ('TMPP', 'performance')):
        rel = text(mrph, sig)
        if not rel:
            rep.fail('morphs', f"MRPH has no {sig} ({label} morph path)")
            continue

        d = data_path(data, rel)
        f = data_path(data, rel, 'morph.dat')
        if not os.path.isdir(d):
            rep.fail('morphs', f"{label}: {sig} directory does not exist",
                     [rel, "The engine falls back to the VANILLA morphs, which will not "
                           "match your vertex count."])
            continue
        if not os.path.exists(f):
            rep.fail('morphs', f"{label}: no morph.dat in the {sig} directory",
                     [rel, "Empty directory means the engine uses the vanilla morphs instead."])
            continue

        try:
            m = MorphFile.from_file(f)
        except Exception as e:
            rep.fail('morphs', f"{label}: morph.dat could not be read: {e}", f)
            continue

        if not m.records:
            rep.fail('morphs', f"{label}: morph.dat has {len(m.morph_names)} keys and no morph "
                               f"data -- crashes the CK", [rel, ZERO_RECORD_CRASH])
            continue

        deltas = m.key_deltas()
        empty = [n for n in m.morph_names if not deltas[n]]

        # THE check. A declared-but-empty key makes the whole head invisible, silently.
        if empty:
            rep.fail('morphs',
                     f"{label}: {len(empty)} of {len(m.morph_names)} morph keys have NO "
                     f"vertex displacement",
                     [f"first few: {', '.join(empty[:6])}",
                      "A declared key with no data makes the head INVISIBLE in game and in "
                      "the CK. Either sculpt them, or trim the race's MPGM list to the "
                      "morphs that really exist."])
        else:
            rep.ok('morphs', f"{label}: all {len(m.morph_names)} keys carry displacement")

        # Vertex count must match the head mesh or the CK crashes during the FaceGen bake.
        if head_verts is not None:
            if m.num_vertices != head_verts:
                rep.fail('morphs',
                         f"{label}: morph has {m.num_vertices} verts, head mesh has "
                         f"{head_verts}",
                         "ApplyChargenMorph fails on a mismatch and the CK crashes on "
                         "FaceGen (null BSGeometry).")
            else:
                rep.ok('morphs', f"{label}: vertex count matches the head mesh "
                                 f"({head_verts})")

        # Names the game will never match.
        dirty = [n for n in m.morph_names if n != n.strip()]
        if dirty:
            rep.fail('morphs', f"{label}: {len(dirty)} key name(s) have leading/trailing "
                               f"whitespace", [repr(n) for n in dirty[:6]])

        dupes = {n for n in m.morph_names if m.morph_names.count(n) > 1}
        if dupes:
            rep.warn('morphs', f"{label}: duplicate key names", sorted(dupes)[:6])

        # The race declares which chargen morphs must exist.
        if sig == 'TCMP' and declared_names:
            have = set(m.morph_names)
            missing = sorted(set(declared_names) - have)
            if missing:
                rep.fail('morphs',
                         f"chargen: {len(missing)} morph(s) the race declares are not in "
                         f"morph.dat",
                         [', '.join(missing[:8]),
                          "The race's MPGM list and the morph file must agree."])
            else:
                rep.ok('morphs', f"chargen: all {len(declared_names)} race-declared morphs "
                                 f"are present")

        # What the creator composes, which is not the same list. See check_composition.
        if sig == 'TCMP' and composed_names:
            have = set(m.morph_names)
            missing = sorted(set(composed_names) - have)
            if missing:
                rep.fail('morphs',
                         f"chargen: {len(missing)} morph(s) the creator can compose are not "
                         f"in morph.dat",
                         [', '.join(missing[:8]),
                          "Hand-built NPCs name BMPN directly and will look fine; a "
                          "player-made character asks for these and gets nothing."])
            else:
                rep.ok('morphs', f"chargen: all {len(composed_names)} composable keys "
                                 f"are present")


def check_composition(rep, per_sex, own_face, sexes=SEXES):
    """The rule the creator relies on: a Morph Groups key is '<phenotype>_<region>'.

    The race states the phenotypes (FMRI/FMRU) and the regions (MPGN) separately, so the two
    can drift -- and when they do, everything an author builds by hand still works while
    anything the player builds in the creator asks for a key that was never authored.

    Returns the composable key set per sex, for checking against morph.dat."""
    composed = {}
    for sx in sexes:
        block = per_sex[sx]
        phenos = [n for _i, n in block['phenotypes']]
        groups = block['groups']
        if not phenos and not groups:
            continue

        # A sex that declares morphs but owns no face part can never be checked against a
        # morph file -- and in practice means the tree for that sex was never built.
        if groups and sx not in own_face:
            rep.fail('morphs', f"{sx.lower()}: race declares {len(block['morphs'])} morph "
                               f"group members but has no Face head part of its own",
                     "Nothing points at a morph.dat for this sex, so the declared keys "
                     "cannot resolve. The head renders invisible.")

        if not phenos:
            rep.fail('morphs', f"{sx.lower()}: morph groups declared but no phenotype rows "
                               f"(FMRI) to compose them with",
                     "The creator's Shape Blend list is built from the phenotype table; "
                     "with none, there is nothing to blend.")
            continue
        dupes = sorted({p for p in phenos if phenos.count(p) > 1})
        if dupes:
            rep.fail('morphs', f"{sx.lower()}: duplicate phenotype names in the FMRI table",
                     [', '.join(dupes), "Two rows composing the same key is ambiguous."])

        keys = {f"{p}_{region}" for p in phenos for region, _m in groups}
        composed[sx] = keys

        undeclared, orphan, wrong_size = [], [], []
        for region, members in groups:
            want = [f"{p}_{region}" for p in phenos]
            undeclared += [k for k in want if k not in members]
            orphan += [m for m in members if m not in want]
            if len(members) != len(phenos):
                wrong_size.append(f"{region} has {len(members)}, expected {len(phenos)}")

        if undeclared:
            rep.fail('morphs',
                     f"{sx.lower()}: {len(undeclared)} composable key(s) the race does not "
                     f"declare in MPGM",
                     [', '.join(sorted(undeclared)[:8]),
                      f"phenotypes: {', '.join(sorted(phenos))}",
                      "The creator composes <phenotype>_<region> from the FMRI table and "
                      "the MPGN names. Anything it composes must be declared and sculpted."])
        else:
            rep.ok('morphs', f"{sx.lower()}: all {len(keys)} composable keys "
                             f"({len(phenos)} phenotypes x {len(groups)} regions) declared")

        if orphan:
            rep.warn('morphs',
                     f"{sx.lower()}: {len(orphan)} MPGM member(s) no phenotype composes",
                     [', '.join(sorted(orphan)[:8]),
                      "Reachable only by naming BMPN by hand -- the creator will never "
                      "select them."])
        if wrong_size:
            rep.warn('morphs', f"{sx.lower()}: morph group(s) not one member per phenotype",
                     wrong_size[:6])
    return composed


# --- head part / nif checks -----------------------------------------------------------------

def split_by_sex(race):
    """The race's per-sex chargen blocks. MNAM opens the male block, FNAM the female, and
    head parts / morph groups / regions / phenotypes all belong to whichever is open.

    'groups' keeps the MPGN -> MPGM nesting that 'regions' and 'morphs' flatten away, and
    'phenotypes' collects the FMRI rows of the phenotype table (FMRI id, then the FMRU raw
    name). The sculpt rows share that table and the same id space, so FMSR rows are kept
    apart -- only the FMRI ones compose morph keys.

    The id space is per sex, not per race: vanilla HumanRace uses id 1 for male_as_md1 and for
    female_eu_md2. Never merge the two tables into one id-keyed lookup.

    'tones' holds the block's BSTT / HSTT / FSTT / FCTP strings. FSTT is race-wide but written
    in only one block (the female one, in every race seen), so look in both."""
    out = {'MALE': {'parts': [], 'morphs': [], 'regions': [], 'groups': [],
                    'phenotypes': [], 'sculpt': [], 'tones': {}},
           'FEMALE': {'parts': [], 'morphs': [], 'regions': [], 'groups': [],
                      'phenotypes': [], 'sculpt': [], 'tones': {}}}
    sex, idx, group, row = None, None, None, None
    for sr in race.subrecords:
        s = sr.signature
        if s == 'MNAM':
            sex, group, row = 'MALE', None, None
        elif s == 'FNAM':
            sex, group, row = 'FEMALE', None, None
        elif sex is None:
            continue
        elif s == 'INDX' and sr.size == 4:
            idx = sr.get_uint32()
        elif s == 'HEAD' and sr.size == 4:
            out[sex]['parts'].append((idx, sr.get_form_id()))
        elif s == 'MPGM':
            out[sex]['morphs'].append(sr.get_string())
            if group is not None:
                group[1].append(sr.get_string())
        elif s == 'MPGN':
            out[sex]['regions'].append(sr.get_string())
            group = (sr.get_string(), [])
            out[sex]['groups'].append(group)
        elif s in ('FMRI', 'FMSR') and sr.size == 4:
            row = ('phenotypes' if s == 'FMRI' else 'sculpt', sr.get_uint32())
        elif s == 'FMRU' and row is not None:
            out[sex][row[0]].append((row[1], sr.get_string()))
            row = None
        elif s in ('BSTT', 'HSTT', 'FSTT', 'FCTP'):
            out[sex]['tones'][s] = sr.get_string()
    return out


def valid_for_race(hdpt, race, plugins):
    """Does this head part's RNAM Valid Races form-list include the race?

    RNAM points at an FLST, not at a RACE, so membership is one hop further than it looks.
    A head part that names no list is valid for everything and counts as a match."""
    sr = hdpt.get_subrecord('RNAM')
    if sr is None or sr.get_form_id().value == 0:
        return True
    flst = plugins.resolve_form_id(sr.get_form_id(), hdpt.plugin)
    if flst is None:
        return False
    # Compare the resolved records, not raw formIDs: the same race reached from two plugins
    # has two different local formIDs, and resolving both lands on the one winning record.
    target = plugins.resolve_form_id(race.form_id, race.plugin) or race
    for entry in flst.get_subrecords('LNAM'):
        if plugins.resolve_form_id(entry.get_form_id(), flst.plugin) is target:
            return True
    return False


def race_head_parts(race, plugins, official):
    """Every head part outside the game's own plugins that is valid for the race.

    The race's own HEAD list holds only its *defaults* -- one per slot. Everything else the
    mods ship for this race (the alternate eyes, hair, ears, the parts the creator offers)
    is reachable only through each HDPT's RNAM Valid Races list, so a check driven by the
    HEAD list alone silently skips most of a mod's head parts."""
    return [h for h in winning_records(plugins, 'HDPT')
            if plugin_name(h) not in official and valid_for_race(h, race, plugins)]


def check_head_parts(rep, data, race, nif_reader, per_sex, plugins, official, sexes=SEXES,
                     avm=None):
    """The race's head parts and the NIFs behind them.

    Two sources, because either alone leaves a hole: the race's per-sex HEAD list (its
    defaults, which is what the game falls back to) and every head part in the load order
    whose RNAM Valid Races list includes the race (which is what the creator offers).

    Only parts whose winning copy lives outside the game's own plugins are inspected. A part
    the game itself defines has its assets in a BA2 we cannot read, so following it would
    produce nothing but noise.

    Whether an NPC lists the race's face part is not checked: an NPC with no face part of its
    own gets the race's."""
    parts = {sx: per_sex[sx]['parts'] for sx in per_sex}
    own_face = {}
    seen = set()
    for sx in sexes:
        if not parts[sx]:
            rep.warn('head parts', f"{sx.lower()}: race lists no head parts")
            continue
        rep.ok('head parts', f"{sx.lower()}: {len(parts[sx])} head parts")
        for _i, fid in parts[sx]:
            hdpt = plugins.resolve_form_id(fid, race.plugin)
            if hdpt is None or plugin_name(hdpt) in official:
                continue                      # the game's own part; assets are in a BA2
            pnam = hdpt.get_subrecord('PNAM')
            if pnam is not None and pnam.get_uint32() == HDPT_FACE:
                own_face[sx] = hdpt
            seen.add(id(hdpt))
            check_head_nif(rep, data, hdpt, nif_reader)
            check_part_morphs(rep, data, hdpt, plugins)
            if avm is not None:
                check_follicle_mask(rep, data, hdpt, avm, official)

    # The rest of the mod's parts for this race -- the ones the race doesn't default to.
    extra = [h for h in race_head_parts(race, plugins, official)
             if id(h) not in seen]
    if extra:
        rep.ok('head parts', f"{len(extra)} more head part(s) valid for this race but not "
                             f"among its defaults",
               sorted(h.editor_id or '?' for h in extra)[:8])
        for hdpt in extra:
            check_head_nif(rep, data, hdpt, nif_reader)
            check_part_morphs(rep, data, hdpt, plugins)
            if avm is not None:
                check_follicle_mask(rep, data, hdpt, avm, official)

    if not own_face:
        rep.warn('head parts', "Race defines no Face head part of its own (PNAM type 1)",
                 "Every head part resolves to a master, so this race has no custom head.")
    return own_face


# The creator offers only the head parts on these lists (hardcoded FormIDs 0003D9AF / 0003D9B0,
# found here by EditorID so a mod's override is what's read). A part's RNAM Valid Races only says
# who may wear it. The types the vanilla lists hold: eyes, hair, facial hair, eyebrows, jewelry,
# eyelashes -- faces, teeth and the rest come from the race, not the menu.
CHARGEN_OPTIONS = {'MALE': 'HeadPartsChargenOptionsMale', 'FEMALE': 'HeadPartsChargenOptionsFemale'}
CHARGEN_OPTION_TYPES = {HDPT_RIGHT_EYE, HDPT_HAIR, HDPT_FACIAL_HAIR, 6, 7, HDPT_LEFT_EYE, 13}
HDPT_PLAYABLE, HDPT_MALE, HDPT_FEMALE, HDPT_EXTRA_PART = 0x01, 0x02, 0x04, 0x10
HDPT_SEX_FLAG = {'MALE': HDPT_MALE, 'FEMALE': HDPT_FEMALE}


def check_chargen_options(rep, parts, plugins, sexes=SEXES):
    """WARN for each playable head part of a menu type that its sex's chargen list doesn't offer.
    It renders on an NPC that has it, but the player can never pick it. Extra parts (pulled in by
    another part) are skipped."""
    lists = {f.editor_id: f for f in winning_records(plugins, 'FLST')
             if f.editor_id in CHARGEN_OPTIONS.values()}
    for sx in sexes:
        flst = lists.get(CHARGEN_OPTIONS[sx])
        if flst is None:
            rep.info('chargen', f"{CHARGEN_OPTIONS[sx]} not loaded; chargen choices not checked")
            continue
        offered = {id(plugins.resolve_form_id(e.get_form_id(), flst.plugin))
                   for e in flst.get_subrecords('LNAM')}
        missing = []
        for h in parts:
            data, pnam = h.get_subrecord('DATA'), h.get_subrecord('PNAM')
            flags = data.data[0] if data and data.data else 0
            if (not flags & HDPT_PLAYABLE or flags & HDPT_EXTRA_PART
                    or not flags & HDPT_SEX_FLAG[sx]
                    or pnam is None or pnam.get_uint32() not in CHARGEN_OPTION_TYPES):
                continue
            if id(h) not in offered:
                missing.append(h.editor_id or '?')
        if missing:
            rep.warn('chargen', f"{sx.lower()}: {len(missing)} playable head part(s) not on "
                                f"{CHARGEN_OPTIONS[sx]} ({flst.form_id}, winning copy in "
                                f"{plugin_name(flst)}), so chargen won't offer them",
                     sorted(missing))
        else:
            rep.ok('chargen', f"{sx.lower()}: every playable head part is on {CHARGEN_OPTIONS[sx]}")


def is_eye(hdpt, stem):
    """An eye head part, by type or by the *_righteye / *_lefteye naming vanilla uses."""
    pnam = hdpt.get_subrecord('PNAM')
    if pnam is not None and pnam.get_uint32() in (HDPT_RIGHT_EYE, HDPT_LEFT_EYE):
        return True
    names = (stem.lower(), (hdpt.editor_id or '').lower())
    return any(n.endswith(('righteye', 'lefteye')) for n in names)


def check_head_nif(rep, data, hdpt, nif_reader):
    """The NIF a head part names, its external .mesh, and the facebones pair."""
    modl = text(hdpt, 'MODL')
    if not modl:
        # Odd, but done on purpose: a "no hair" part with no model blanks the hair.
        rep.warn('nif', f"{hdpt.editor_id}: head part has no MODL")
        return
    if not exists(data, 'meshes', modl):
        rep.fail('nif', f"{hdpt.editor_id}: MODL not on disk", modl)
        return
    rep.ok('nif', f"{hdpt.editor_id}: MODL present", modl)

    # A Starfield head part needs a facebones twin next to it. Match case-insensitively
    # against the real directory listing -- probing candidate spellings on Windows finds the
    # same file several times over.
    stem, ext = os.path.splitext(os.path.basename(modl))
    want = (stem + '_facebones' + ext).lower()
    facebones = next((f for f in list_dir(data, 'meshes', os.path.dirname(modl))
                      if f.lower() == want), None)
    if facebones is None and is_eye(hdpt, stem):
        rep.info('nif', f"{hdpt.editor_id}: no _facebones NIF -- normal for eyes, vanilla's "
                        f"have none")
    elif facebones is None:
        rep.fail('nif', f"{hdpt.editor_id}: no _facebones NIF beside the head",
                 [f"expected {stem}_facebones{ext}",
                  "A head part without its facebones twin does not render."])
    else:
        rep.ok('nif', f"{hdpt.editor_id}: facebones NIF present ({facebones})")

    if nif_reader is None:
        return
    todo = [modl]
    if facebones:
        todo.append(os.path.join(os.path.dirname(modl), facebones))
    for rel in todo:
        nif_reader(rep, data, data_path(data, 'meshes', rel), rel)


# A few shader models are driven by a settings component that carries their whole reason to
# exist -- Eye1Layer reads the iris parallax depths from EyeSettingsComponent. Omit it and the
# material still parses, still resolves every texture, and still previews correctly in the CK,
# but the part is invisible in game.
#
# Measured over all 10,530 vanilla materials: these three models appear on 21 materials, always
# on the root object, and every one carries its component. No other shader model ever carries
# one of these, so the pairing is exceptionless in both directions.
SHADER_MODEL_SETTINGS = {
    'Eye1Layer':   'EyeSettingsComponent',      # 8/8 vanilla
    '1LayerMouth': 'MouthSettingsComponent',    # 2/2
    'Hair1Layer':  'HairSettingsComponent',     # 11/11
}


def check_shader_settings(rep, data, mat_rel, path):
    """A shader model that needs a settings component and didn't get one.

    Asked of the material's whole INHERITANCE CHAIN, not of the file alone. A `.mat` is
    normally a derivation, and only 0.3% of vanilla materials name their own shader model --
    the rest inherit it, along with its settings component, from the template they import.
    Reading the local file only would miss the model on almost every real material, and
    would then fail a derived material that correctly inherits both.
    """
    search = [os.path.join(d, 'materials') for d in data
              if os.path.isdir(os.path.join(d, 'materials'))]
    try:
        chain = sf_matchain.resolve_material(path, search=search or None)
    except Exception as e:
        rep.warn('materials', f"{mat_rel}: could not resolve its Import chain: {e}",
                 "The shader-model/settings check is skipped for it.")
        return

    check_skin_vertex_alpha(rep, mat_rel, chain)

    want = SHADER_MODEL_SETTINGS.get(chain.shader_model)
    if not want or chain.root.component('BSMaterial::' + want) is not None:
        return
    rep.fail('materials',
             f"{mat_rel}: shader model '{chain.shader_model}' has no {want}",
             [f"{chain.shader_model} is driven by that component; without it the part is "
              f"INVISIBLE in game while the Creation Kit preview looks correct.",
              "Every vanilla material using this shader model carries it, on the template "
              "if not on the material itself.",
              f"Chain searched: {' -> '.join(os.path.basename(p) for p in chain.paths)}"])


# The skin shader models. On these, alpha settings that take opacity from vertex colour
# (Blender.UseVertexColor) make the whole shape invisible on a character, even where vertex
# alpha is 1.0, while the CK's armor preview still draws it. Texture opacity works. Found in
# game on a custom race's body and tail, 2026-10-12. Vanilla never does it: no skin material
# has an alpha component at all, and vertex-colour opacity appears only on standard and decal
# models.
SKIN_SHADER_MODELS = {'BodySkin1Layer', 'BodySkin2Layer', 'Skin5Layer'}


def check_skin_vertex_alpha(rep, mat_rel, chain):
    """A skin material whose opacity comes from vertex colour."""
    if chain.shader_model not in SKIN_SHADER_MODELS:
        return
    al = chain.root.component('BSMaterial::AlphaSettingsComponent')
    blender = ((al.data if al else {}).get('Blender') or {}).get('Data') or {}
    if str(blender.get('UseVertexColor', 'false')).lower() != 'true':
        return
    rep.fail('materials',
             f"{mat_rel}: {chain.shader_model} takes its opacity from vertex colour",
             ["Alpha settings with UseVertexColor on a skin shader make the whole shape "
              "INVISIBLE on a character, while the CK armor preview still draws it.",
              "Put the transparency in the opacity texture and turn off Use Vertex Color "
              "on the material's SF AlphaSettingsComponent node.",
              f"Chain searched: {' -> '.join(os.path.basename(p) for p in chain.paths)}"])


_material_dbs = {}


def material_db(data):
    """The game's compiled material database, from the first --data folder that has
    materials\\materialsbeta.cdb loose (an unpacked-assets folder, normally), or None."""
    for d in data:
        path = os.path.join(d, 'materials', 'materialsbeta.cdb')
        if os.path.exists(path):
            if path not in _material_dbs:
                _material_dbs[path] = load_cdb(path)
            return _material_dbs[path]
    return None


_archive_names = {}


def ba2_names(path):
    """The file names a BA2 holds, lowercased with backslashes. Only the name table is read:
    the header gives the file count (at 12) and the table's offset (at 16), and the table is a
    u16 length + name per file, the same in every BTDX version."""
    with open(path, 'rb') as f:
        magic, _ver, _kind, count, offset = struct.unpack('<4sI4sIQ', f.read(24))
        if magic != b'BTDX':
            return set()
        f.seek(offset)
        raw = f.read()
    names, pos = set(), 0
    for _ in range(count):
        n = struct.unpack_from('<H', raw, pos)[0]
        names.add(raw[pos + 2:pos + 2 + n].decode('utf-8', 'replace').lower().replace('/', '\\'))
        pos += 2 + n
    return names


def archive_names(data):
    """Every file name in the BA2s of the --data folders. A path in here exists, even though it
    isn't loose -- which is how to tell a vanilla asset from one a mod forgot to make."""
    key = tuple(data)
    if key not in _archive_names:
        names = set()
        for d in data:
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.lower().endswith('.ba2'):
                    try:
                        names |= ba2_names(os.path.join(d, fn))
                    except (OSError, struct.error):
                        pass
        _archive_names[key] = names
    return _archive_names[key]


def asset_exists(data, rel):
    """Whether a Data-relative path is loose in a --data folder or inside one of its BA2s."""
    return exists(data, rel) or rel.lower().replace('/', '\\') in archive_names(data)


def material_textures(doc):
    """(object name, Data-relative path) for every texture a parsed .mat names."""
    for o in doc.get('Objects', []):
        name = next((c['Data'].get('Name') for c in o.get('Components', [])
                     if c.get('Type', '').endswith('CTName')), '?')
        for c in o.get('Components', []):
            if not c.get('Type', '').endswith('MRTextureFile'):
                continue
            fn = c.get('Data', {}).get('FileName', '')
            if not fn:
                continue
            rel = fn.replace('/', '\\')
            # Material texture paths carry a leading "Data\", the way vanilla writes them.
            if rel.lower().startswith('data\\'):
                rel = rel[5:]
            yield name, rel


def check_material(rep, data, mat_rel, own_root, seen):
    """A shape's `.mat`: does it exist, is it game-valid, do its textures exist?

    A material that parses fine but points at a texture nobody produced renders the shape
    black, and nothing in the CK says so.
    """
    if not mat_rel or mat_rel in seen:
        return
    seen.add(mat_rel)

    path = data_path(data, mat_rel)
    if not os.path.exists(path):
        # Vanilla materials are compiled into materialsbeta.cdb, not shipped loose, so a
        # missing file is only wrong when the database doesn't have the path either.
        db = material_db(data)
        if db is None:
            rep.warn('materials', f"{mat_rel}: no loose file, and no materialsbeta.cdb "
                                  f"to look it up in",
                     "Add a folder of unpacked vanilla assets to --data to check it.")
        elif db.material_dbid(mat_rel) is not None:
            rep.info('materials', f"{mat_rel}: compiled into materialsbeta.cdb")
        else:
            rep.fail('materials', f"{mat_rel}: material does not exist",
                     "Not a loose file in any --data folder, and not in the game's "
                     "materialsbeta.cdb. Check the material path on the shape.")
        return

    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
    except Exception as e:
        rep.fail('materials', f"{mat_rel}: could not be parsed: {e}")
        return

    objects = doc.get('Objects', [])
    no_parent = [o for o in objects if not o.get('Parent')]
    ids = [o.get('ID') for o in objects if o.get('ID')]
    placeholder = [i for i in ids if i.startswith('res:0000000')]

    # A node with no Parent has no base DOM, so the game can't build the material -> magenta.
    # NifSkope and PyNifly's own reader are both lenient about this; the game is not.
    if len(no_parent) > 1:
        rep.fail('materials', f"{mat_rel}: {len(no_parent)} objects have no Parent",
                 "Only the root LayeredMaterial may omit Parent. Renders magenta in game.")
    if placeholder:
        rep.fail('materials', f"{mat_rel}: {len(placeholder)} placeholder res: ID(s)",
                 placeholder[:4])
    if len(set(ids)) != len(ids):
        rep.fail('materials', f"{mat_rel}: duplicate res: IDs")

    check_shader_settings(rep, data, mat_rel, path)

    missing_own, missing_other, not_dds = [], [], []
    for name, rel in material_textures(doc):
        if not is_dds(rel):
            not_dds.append(f"{name}: {rel}")
        if exists(data, rel):
            continue
        norm = rel.lower()
        (missing_own if own_root and own_root in norm
         else missing_other).append(f"{name}: {rel}")

    if not_dds:
        rep.fail('materials', f"{mat_rel}: {len(not_dds)} texture path(s) are not .dds",
                 not_dds[:6] + [NOT_DDS_ADVICE])
    if missing_own:
        rep.fail('materials', f"{mat_rel}: {len(missing_own)} of this mod's texture(s) do "
                              f"not exist",
                 missing_own[:6] + ["A missing albedo renders the shape BLACK. Note export "
                                    "rewrites the extension to .dds, so a .png in Blender "
                                    "still needs a .dds beside it."])
    if missing_other:
        rep.warn('materials', f"{mat_rel}: {len(missing_other)} texture(s) not found loose",
                 [missing_other[0] + (f"  (+{len(missing_other) - 1} more)"
                                      if len(missing_other) > 1 else ''),
                  "Vanilla paths are probably inside a BA2, which this tool cannot read."])
    if not missing_own and not missing_other:
        rep.ok('materials', f"{mat_rel}: all textures resolve")


def make_nif_reader(own_root):
    """A NIF inspector, or None when the DLL can't be loaded."""
    seen_materials = set()
    seen_nifs = set()
    try:
        from pyn.pynifly import NifFile
    except Exception:
        return None

    def read(rep, data, path, label):
        # One NIF fills several slots -- a body addon names the same mesh for 3rd and
        # 1st person -- and repeating its findings once per slot buries everything else.
        key = os.path.normcase(os.path.abspath(path))
        if key in seen_nifs:
            return
        seen_nifs.add(key)
        try:
            f = NifFile(path)
        except Exception as e:
            rep.warn('nif', f"{label}: could not be read: {e}")
            return
        for s in f.shapes:
            # Head parts and body parts are placed by their skin -- an eye rides its eye bone.
            # An unskinned shape has its position baked into its transform and nothing to
            # attach it to the actor, so it doesn't show. All 427 vanilla head-part and
            # skin-addon NIFs are fully skinned.
            if not s.bone_names:
                rep.fail('nif', f"{label}: {s.name} is not skinned",
                         "It has no bones, so the game can't attach it to the actor. In "
                         "Blender, give it an Armature modifier and vertex groups for its "
                         "bones (an eye: all vertices in R_Eye or L_Eye), then re-export.")
            mat = s.shader.name if s.shader else None
            if mat:
                check_material(rep, data, mat, own_root, seen_materials)
                want = material_id(mat)
                got = [ed.integer_data for ed in s.extra_data()
                       if type(ed).__name__ == 'NiIntegerExtraData' and ed.name == 'MaterialID']
                if got and got[0] != want:
                    rep.fail('nif', f"{label}: {s.name} MaterialID does not match its "
                                    f"material path",
                             [f"stored {got[0]}, expected {want} for {mat}",
                              "Usually means the .mat was moved or renamed by hand. "
                              "Re-export instead."])
                elif not got:
                    rep.warn('nif', f"{label}: {s.name} has no MaterialID extra data", mat)
            if getattr(s, 'properties', None) is not None and s.properties.flags == 0:
                rep.warn('nif', f"{label}: {s.name} has shape flags 0",
                         "Vanilla head parts use 14, Felid uses 526. A Blender-authored "
                         "shape that was never imported has no pynNodeFlags to write.")
            try:
                mp = s.mesh_path(0)
            except Exception:
                continue
            if mp:
                full = resolve_mesh(data, mp)
                if not os.path.exists(full):
                    rep.fail('nif', f"{label}: external .mesh missing", mp)
    return read


def model_mesh_verts(data, modl):
    """Vertex count behind a NIF's first shape, or None if it can't be determined.

    Needs the DLL to read the NIF, but the .mesh itself is read directly -- see
    mesh_vertex_count."""
    if not modl or not exists(data, 'meshes', modl):
        return None
    try:
        from pyn.pynifly import NifFile
        f = NifFile(data_path(data, 'meshes', modl))
        for s in f.shapes:
            mp = s.mesh_path(0)
            if mp:
                full = resolve_mesh(data, mp)
                if os.path.exists(full):
                    return mesh_vertex_count(full)
    except Exception:
        pass
    return None


def head_mesh_verts(data, hdpt):
    """Vertex count of the face head part's mesh, or None if it can't be determined."""
    return model_mesh_verts(data, text(hdpt, 'MODL'))


# --- body checks -----------------------------------------------------------------------------

# ARMA record flags. Vanilla skin addons use these, but not universally -- the frozen-corpse
# skin addons carry neither -- so they are reported, never required.
ARMA_IS_SKIN = 0x00000080
ARMA_IS_SKIN_HANDS = 0x00000100
ARMA_NO_MODEL = 0x00000400

# ARMA biped models, and the body morph (MRPH) that belongs to each. A skin addon carries
# one per sex per view; a male-only race still points its female slots at the vanilla body.
BIPED_MODELS = [('MALE', 'MOD2', 'NAM4', 'male 3rd person'),
                ('FEMALE', 'MOD3', 'NAM6', 'female 3rd person'),
                ('MALE', 'MOD4', 'NAM5', 'male 1st person'),
                ('FEMALE', 'MOD5', 'NAM7', 'female 1st person')]


def arma_races(arma, plugins):
    """Every race an armor addon says it fits: RNAM plus the Additional Races array.

    ARMA reuses MODL for that array -- on an ARMO the same signature means something else
    entirely (the addon list), so never share this between the two."""
    out = []
    for sr in [arma.get_subrecord('RNAM')] + arma.get_subrecords('MODL'):
        if sr is None or sr.get_form_id().value == 0:
            continue
        r = plugins.resolve_form_id(sr.get_form_id(), arma.plugin)
        if r is not None:
            out.append(r)
    return out


CROWD_RACE = 'HumanCrowdRace'


def is_crowd_race(race, plugins):
    """Whether `race` is a crowd race: HumanCrowdRace, or one using it as its Armor Race. A crowd
    actor's head, eyes and arms are one mesh carried by the head armor in its outfit, so the
    chargen machinery -- head parts, hands, tint layers, skin tones, face textures -- isn't used."""
    if race.editor_id == CROWD_RACE:
        return True
    armor_race = plugins.resolve_reference(race, 'RNAM')
    return armor_race is not None and armor_race.editor_id == CROWD_RACE


BIPED_HEAD = 1 << 2                 # BO64 bit of the head slot, where crowd heads go


def biped_slots(rec):
    sr = rec.get_subrecord('BO64') if rec is not None else None
    return int.from_bytes(bytes(sr.data)[:8], 'little') if sr is not None else 0


def outfit_armors(plugins, outfit):
    """The armors an outfit can put on: its items, with leveled lists opened all the way down.
    An outfit's INAM is an array of form IDs; a list's LVLO is {level, form ID, count}."""
    out, seen = [], set()

    def visit(rec):
        if rec is None or id(rec) in seen:
            return
        seen.add(id(rec))
        if rec.signature == 'ARMO':
            out.append(rec)
        elif rec.signature == 'LVLI':
            for sr in rec.get_subrecords('LVLO'):
                visit(plugins.resolve_form_id(sr.get_form_id(4), rec.plugin))

    for sr in outfit.get_subrecords('INAM'):
        for i in range(sr.size // 4):
            visit(plugins.resolve_form_id(sr.get_form_id(i * 4), outfit.plugin))
    return out


def crowd_head_models(plugins, npcs):
    """The models a crowd race's actors wear on their heads, {(sex, model): info}.

    A crowd actor's head is clothing: its outfit holds a head list, the list holds head armors
    (head slot), and each armor's addons name a model per sex. Every addon counts -- a fox crowd
    head armor also carries its tail -- and info['head'] says whether the addon itself is in the
    head slot (only those have a _faceBones companion). info['armors'] names the armors."""
    out = {}
    for npc in npcs:
        sex = npc_sex(npc)
        outfit = plugins.resolve_reference(npc, 'DOFT') if npc.get_subrecord('DOFT') else None
        if sex is None or outfit is None:
            continue
        for armo in outfit_armors(plugins, outfit):
            if not biped_slots(armo) & BIPED_HEAD:
                continue
            for sr in armo.get_subrecords('MODL'):
                arma = plugins.resolve_form_id(sr.get_form_id(), armo.plugin)
                rel = text(arma, 'MOD2' if sex == 'MALE' else 'MOD3')
                if rel:
                    info = out.setdefault((sex, rel), {
                        'head': bool(biped_slots(arma) & BIPED_HEAD), 'armors': set()})
                    info['armors'].add(armo.editor_id)
    return out


# Advice for each crowd-head finding, said once however many heads share it.
CROWD_ADVICE = {
    'model': "The addon names a NIF that isn't loose or in any archive: that head is invisible.",
    'mesh': "The NIF's geometry lives in this external .mesh; without it the shape is invisible.",
    'material': "Not a loose file, and not in the game's materialsbeta.cdb.",
    'no material db': "Add a folder of unpacked vanilla assets to --data to check these.",
    'texture': "Not loose and not in any BA2. A missing albedo renders black, a missing normal "
               "flat. A .png beside it doesn't count: convert it to .dds.",
    'companion': "Every vanilla crowd head has a <name>_facebones.nif companion, a plain copy "
                 "of the head, and the game draws the crowd head from it.",
    'face rig': "The crowd skeleton has no face bones. A crowd head's companion must be a plain "
                "copy of the head NIF, not a chargen face rig: copy the head over it.",
}


def check_crowd_heads(rep, data, models):
    """The crowd heads' NIFs, meshes, materials, textures and _faceBones companions.

    Forty variants of one head share their mesh, textures and companion layout, so each problem
    is reported once, with how many models have it and a few examples."""
    try:
        from pyn.pynifly import NifFile
    except Exception:
        return                                  # run() already warned the DLL is missing
    area = 'crowd heads'
    if not models:
        rep.warn(area, "no crowd heads found",
                 "No NPC of this race has a default outfit with a head-slot armor in it.")
        return
    found = collections.defaultdict(lambda: collections.defaultdict(set))  # key -> item -> models
    db = material_db(data)
    materials = {}                              # mat path -> its textures, or None

    def textures_of(mat):
        if mat not in materials:
            materials[mat] = None
            path = data_path(data, mat)
            if os.path.exists(path):
                try:
                    with open(path, encoding='utf-8') as f:
                        materials[mat] = [rel for _n, rel in material_textures(json.load(f))]
                except (OSError, ValueError):
                    pass
        return materials[mat]

    def inspect(rel, who, head):
        if not asset_exists(data, os.path.join('meshes', rel)):
            found[(FAIL, 'model', "model not on disk")][rel].add(who)
            return
        path = data_path(data, 'meshes', rel)
        if not os.path.exists(path):
            return                              # vanilla, in a BA2: nothing to read
        try:
            nif = NifFile(path)
        except Exception as e:
            rep.warn(area, f"{rel}: could not be read: {e}")
            return
        for s in nif.shapes:
            for mp in s.mesh_paths():
                if mp and not asset_exists(data, mesh_rel(mp)):
                    found[(FAIL, 'mesh', "external .mesh missing")][mp].add(who)
            mat = s.shader.name if s.shader else None
            if not mat:
                continue
            if textures_of(mat) is None and not os.path.exists(data_path(data, mat)):
                if db is None:
                    found[(WARN, 'no material db', "material not loose, and no "
                                                   "materialsbeta.cdb to look it up in")][mat].add(who)
                elif db.material_dbid(mat) is None:
                    found[(FAIL, 'material', "material does not exist")][mat].add(who)
                continue
            for tex in textures_of(mat) or []:
                if not asset_exists(data, tex):
                    found[(FAIL, 'texture', "texture does not exist")][tex].add(who)
        if not head:
            return
        folder, stem = os.path.split(path)
        stem = os.path.splitext(stem)[0].lower()
        companion = next((f for f in os.listdir(folder)
                          if f.lower() == stem + '_facebones.nif'), None)
        if companion is None:
            found[(WARN, 'companion', "no _faceBones companion")][rel].add(who)
            return
        comp_rel = os.path.join(os.path.dirname(rel), companion)
        try:
            face_bones = sum(b.lower().startswith('facebone')
                             for s in NifFile(os.path.join(folder, companion)).shapes
                             for b in s.bone_names)
        except Exception:
            face_bones = 0
        if face_bones:
            found[(FAIL, 'face rig', "_faceBones companion is a face rig")][
                f"{comp_rel} ({face_bones} face bones)"].add(who)
        inspect(comp_rel, who, False)

    for (sex, rel), info in sorted(models.items()):
        inspect(rel, rel, info['head'])

    for (level, kind, msg), items in sorted(found.items(), key=lambda kv: kv[0][1]):
        heads = set().union(*items.values())
        n = len(heads)
        shown = sorted(items)[:6]
        more = [f"(+{len(items) - len(shown)} more)"] if len(items) > len(shown) else []
        example = [] if len(items) > 1 or len(heads) == 1 else [f"e.g. {sorted(heads)[0]}"]
        rep.add(level, area, f"{msg} ({n} crowd model{'s' if n != 1 else ''})",
                shown + more + example + [CROWD_ADVICE[kind]])
    if not found:
        rep.ok(area, f"{len(models)} crowd head model(s): models, meshes, materials, "
                     f"textures and companions all resolve")


def check_body(rep, data, race, plugins, nif_reader, own_root, sexes=SEXES, crowd=False):
    """The race's skin: WNAM -> ARMO -> its ARMA addons -> the body and hand NIFs.

    A head part is named by the race directly, but the body is reached through an armor
    record, and every hop can drop it silently: an addon that does not list the race renders
    nothing at all, with no message anywhere."""
    if race.get_subrecord('WNAM') is None:
        return                                  # check_race_misc already FAILed on this
    armo = plugins.resolve_reference(race, 'WNAM')
    if armo is None:
        rep.warn('body', "skin ARMO is in neither the plugin nor its masters",
                 [str(race.get_subrecord('WNAM').get_form_id()),
                  "Nothing below can be checked. Is the master list right?"])
        return
    rep.ok('body', f"skin ARMO {armo.editor_id!r}")

    # 'Armor Race' redirects armor lookups at another race; a custom race normally sets it
    # to HumanRace so vanilla clothing fits. A skin addon that lists either race is used (the
    # Armor Race alone is verified in game); listing only the race itself gets a warning.
    armor_race = plugins.resolve_reference(race, 'RNAM')
    if armor_race is race:
        armor_race = None
    if armor_race is not None:
        rep.info('body', f"race's Armor Race is {armor_race.editor_id}, not itself")

    addons = [sr for sr in armo.get_subrecords('MODL') if sr.get_form_id().value]
    if not addons:
        rep.fail('body', f"{armo.editor_id}: skin ARMO lists no armor addons",
                 "The actor has no body at all.")
        return
    if len(addons) < 2 and not crowd:            # a crowd's hands come with its head armor
        rep.warn('body', f"{armo.editor_id}: only {len(addons)} armor addon",
                 "Vanilla skin carries a body addon and a hands addon; hands are a "
                 "separate biped slot and will be missing without their own.")

    for sr in addons:
        arma = plugins.resolve_form_id(sr.get_form_id(), armo.plugin)
        if arma is None:
            rep.warn('body',
                     f"{armo.editor_id}: armor addon {sr.get_form_id()} not found")
            continue
        check_body_addon(rep, data, race, arma, armor_race, plugins, nif_reader, own_root,
                         sexes)


# The skin-tone swap picks its texture by the addon's record flag: Is Skin gets the race's body
# tone (BSTT), Is Skin Hands the hands tone (HSTT). Vanilla pairs the flag with the slot without
# exception -- all 3 Is Skin Hands addons are in the hands slot, none of the 14 Is Skin ones are.
BIPED_HANDS = 1 << 6


def check_skin_flag_slot(rep, who, flags, bo64):
    """A skin addon whose skin flag doesn't match its slot gets the other tone texture."""
    in_hands = bool(bo64 & BIPED_HANDS)
    if flags & ARMA_IS_SKIN_HANDS and not in_hands:
        rep.fail('body', f"{who}: flagged Is Skin Hands but not in the hands slot",
                 ["Skin tone gives it the HANDS tone texture, sampled at its own UVs: the "
                  "wrong colour. A tail or other body part wants Is Skin."])
    elif flags & ARMA_IS_SKIN and not flags & ARMA_IS_SKIN_HANDS and in_hands:
        rep.fail('body', f"{who}: in the hands slot but flagged Is Skin",
                 ["Skin tone gives it the BODY tone texture instead of the hands one. "
                  "Hands want Is Skin Hands."])


def check_body_addon(rep, data, race, arma, armor_race, plugins, nif_reader, own_root,
                     sexes=SEXES):
    """One ARMA: does this race actually get it, and are its models and morphs sound?"""
    who = arma.editor_id or str(arma.form_id)
    flags = int(arma.flags)
    role = ('body' if flags & ARMA_IS_SKIN else
            'hands' if flags & ARMA_IS_SKIN_HANDS else 'unflagged')
    rep.info('body', f"{who}: addon role {role}")
    bo64 = arma.get_subrecord('BO64')
    check_skin_flag_slot(rep, who, flags,
                         int.from_bytes(bo64.data[:8], 'little') if bo64 is not None else 0)

    if flags & ARMA_NO_MODEL:
        rep.warn('body', f"{who}: addon has the 'No Model' flag set",
                 "Its models are ignored, so this part of the body renders nothing.")

    usable = arma_races(arma, plugins)
    fits = ', '.join(sorted(r.editor_id or str(r.form_id) for r in usable)) or '(none)'
    if race not in usable and armor_race is not None and armor_race in usable:
        # Enough on its own: HumanCorpseRace's skin names only its Armor Race, and a fox crowd
        # race renders vanilla's crowd sweater, which lists HumanCrowdRace, its Armor Race.
        rep.ok('body', f"{who}: the race's Armor Race {armor_race.editor_id} is in the "
                       f"addon's race list")
    elif race not in usable:
        rep.fail('body', f"{who}: neither this race nor its Armor Race is in the addon's "
                         f"race list" if armor_race is not None else
                         f"{who}: this race is not in the addon's race list",
                 [f"addon fits: {fits}",
                  f"add {race.editor_id} to its Race or Additional Races.",
                  "An addon the race does not match is skipped without a word -- that "
                  "slot of the body is simply invisible."])
    elif armor_race is not None and armor_race not in usable:
        rep.warn('body', f"{who}: the race's Armor Race {armor_race.editor_id} is not in "
                         f"the addon's race list",
                 [f"addon fits: {fits}",
                  "The engine matches armor addons against one of the two, and vanilla "
                  "does not settle which: MannequinRace's skin names only itself while "
                  "HumanCorpseRace's names only its Armor Race. Listing both costs "
                  "nothing and is the first thing to try on an invisible body."])
    else:
        rep.ok('body', f"{who}: race is in the addon's race list")

    for sx, modl, morph, label in BIPED_MODELS:
        if sx not in sexes:
            continue
        check_body_model(rep, data, arma, who, modl, morph, label, plugins, nif_reader,
                         own_root)


def check_body_model(rep, data, arma, who, modl, morph, label, plugins, nif_reader,
                     own_root):
    """One biped model on an addon: the NIF, its materials, and its body morph."""
    rel = text(arma, modl)
    if not rel:
        rep.info('body', f"{who}: no {label} model ({modl})")
        return

    if not exists(data, 'meshes', rel):
        # Under the race's own asset tree it is a file this mod owes; anywhere else it is
        # almost certainly a vanilla path living in a BA2, which this tool cannot read.
        if own_root and own_root in rel.lower().replace('/', '\\'):
            rep.fail('body', f"{who}: {label} model not on disk", rel)
        else:
            rep.info('body', f"{who}: {label} model not loose (vanilla, in a BA2?)", rel)
        return
    rep.ok('body', f"{who}: {label} model present", rel)

    if nif_reader is not None:
        nif_reader(rep, data, data_path(data, 'meshes', rel), rel)

    # The body morph is the head's failure mode all over again: the engine applies it by
    # vertex index, so a body remeshed to a different count silently breaks.
    if arma.get_subrecord(morph) is None:
        rep.info('body', f"{who}: no {label} body morph ({morph})")
        return
    rec = plugins.resolve_reference(arma, morph)
    if rec is None:
        rep.info('body', f"{who}: {label} body morph "
                         f"{arma.get_subrecord(morph).get_form_id()} not found")
        return
    check_body_morph(rep, data, who, label, rec, rel)


def is_vanilla_human(rel):
    """Whether a model or morph path is in vanilla's human tree: Actors\\Human*\\... or
    Meshes\\Morphs\\Human*\\... A mod's own files sit under its species' folders."""
    parts = [p for p in rel.lower().replace('/', '\\').split('\\') if p]
    for anchor in ('actors', 'morphs'):
        if anchor in parts:
            at = parts.index(anchor) + 1
            return at < len(parts) and parts[at].startswith('human')
    return False


def check_body_morph(rep, data, who, label, mrph_rec, model_rel):
    """A body morph's vertex count against the model it morphs. A mismatch is the mod's to fix
    unless both are vanilla's: an addon naming vanilla's 1st person body with vanilla's chargen
    morph keeps Bethesda's own mismatched pairing."""
    verts = model_mesh_verts(data, model_rel)
    for sig in ('TCMP', 'TMPP'):
        d = text(mrph_rec, sig)
        if not d:
            continue
        f = data_path(data, d, 'morph.dat')
        if not os.path.exists(f):
            rep.info('body', f"{who}: {label} morph.dat not loose (vanilla, in a BA2?)", d)
            continue
        try:
            m = MorphFile.from_file(f)
        except Exception as e:
            rep.fail('body', f"{who}: {label} morph.dat could not be read: {e}", f)
            continue
        if verts is None:
            rep.info('body', f"{who}: {label} morph has {m.num_vertices} verts "
                             f"(model count unknown)")
        elif m.num_vertices != verts and is_vanilla_human(model_rel) and is_vanilla_human(d):
            rep.warn('body', f"{who}: {label} morph has {m.num_vertices} verts, the model "
                             f"has {verts}",
                     [d, "Both the model and the morph are vanilla's, paired this way by "
                         "Bethesda; nothing for this mod to fix."])
        elif m.num_vertices != verts:
            rep.fail('body', f"{who}: {label} morph has {m.num_vertices} verts, the model "
                             f"has {verts}",
                     [d, "The morph is applied by vertex index. A body remeshed to a "
                         "different count cannot use the vanilla body morphs -- point the "
                         "addon at a morph built for this mesh."])
        else:
            rep.ok('body', f"{who}: {label} morph matches the model ({verts} verts)")


# --- texture / skin-tone checks --------------------------------------------------------------

def check_face_textures(rep, data, race, phenotypes, regions):
    """FCTP supplies the FaceGen base maps by filename convention -- no AVMD route, no
    fallback to the material."""
    fctp = text(race, 'FCTP')
    if not fctp:
        rep.warn('face textures', "Race has no FCTP; the CK falls back to the human path")
        return
    d = data_path(data, 'textures', fctp)
    if not os.path.isdir(d):
        rep.fail('face textures', "FCTP directory does not exist", fctp)
        return
    rep.ok('face textures', "FCTP directory present", fctp)

    # '<sex>_default' is the engine's hard-coded fallback phenotype, so its maps are always
    # needed. The ethnicity/age phenotypes only matter once chargen can select them.
    critical, optional = [], []
    for pheno in sorted(phenotypes):
        bucket = critical if pheno.endswith('_default') else optional
        for suffix in FCTP_SUFFIXES:
            if not exists(data, 'textures', fctp, pheno + suffix):
                bucket.append(pheno + suffix)
    for region in sorted(regions) + ['null']:
        if not exists(data, 'textures', fctp, f"FCT_{region}_mask.dds"):
            critical.append(f"FCT_{region}_mask.dds")

    if critical:
        rep.fail('face textures', f"{len(critical)} required map(s) missing from FCTP",
                 [', '.join(critical[:10]),
                  "Normal/rough/AO and the region masks have NO AVMD route -- they are "
                  "found by filename only. A missing normal map renders the face black."])
    else:
        rep.ok('face textures', "all maps for the default phenotype are present")

    if optional:
        rep.warn('face textures',
                 f"{len(optional)} map(s) missing for non-default phenotypes",
                 [', '.join(optional),
                  "Only bites once chargen can select those phenotypes."])

    # Source art alongside the DDS is normal while authoring -- worth noting, not a failure,
    # since it only matters if something actually references it or it ships in the kit.
    stray = [f for f in list_dir(data, 'textures', fctp)
             if f.lower().endswith(('.png', '.tga', '.jpg'))]
    if stray:
        rep.warn('face textures', f"{len(stray)} non-DDS file(s) in the FCTP directory",
                 [', '.join(stray[:6]),
                  "Starfield loads DDS only. Harmless as working files; exclude them when "
                  "building the kit."])


# The stack of face tint slots, found by this name (chargen.md §4.3).
STACK_TNAM = 'PostBlendFaceCustomizationLayers'


def dds_dimensions(path):
    """(width, height) from a DDS header, or None."""
    try:
        with open(path, 'rb') as f:
            head = f.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b'DDS ':
        return None
    height, width = struct.unpack_from('<2I', head, 12)
    return width, height


def face_option_groups(avm):
    """The Simple groups whose textures the face composite can use: every slot the stack names,
    and its Chargen_ twin (the list the creator offers), with Complex groups -- the per-tone
    dermaesthetic filters -- opened up."""
    stack = avm.get((AVM_COMPLEX, STACK_TNAM))
    if stack is None:
        return []
    by_lower = {}
    for (kind, name), g in avm.items():
        by_lower.setdefault(name.lower(), []).append((kind, g))
    out, seen = [], set()

    def add(g, kind):
        if g is None or id(g) in seen:
            return
        seen.add(id(g))
        if kind == AVM_SIMPLE:
            out.append(g)
        elif kind == AVM_COMPLEX:
            for lnam, vnam in complex_entries(g):
                child = complex_target(lnam, vnam, avm)
                if child is not None:
                    mnam = child.get_subrecord('MNAM')
                    add(child, mnam.get_uint32() if mnam is not None else None)

    for lnam, vnam in complex_entries(stack):
        target = complex_target(lnam, vnam, avm)
        if target is not None:
            mnam = target.get_subrecord('MNAM')
            add(target, mnam.get_uint32() if mnam is not None else None)
        for kind, g in by_lower.get('chargen_' + lnam.lower(), []):
            add(g, kind)
    return out


def check_face_texture_sizes(rep, data, fctp, avm):
    """Every texture the face composite uses must be the same size.

    The creator re-composites the face whenever a tint layer changes, from the FCTP base maps
    and the chosen options. With mixed sizes the face goes BLACK on that first change; all at
    1024 works, all at 2048 works (Bad Dog, in game 2026-10-18). Vanilla's are all 1024 only
    because they match -- so a vanilla option left in a group fails against base maps of
    another size."""
    area = 'face textures'
    advice = ("The face goes black the first time a tint layer changes. Any size works, as "
              "long as the base maps and every option share it (vanilla: all 1024).")
    base = {}
    root = data_path(data, 'textures', fctp)
    if os.path.isdir(root):
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith('.dds'):
                    p = os.path.join(dirpath, f)
                    base[os.path.relpath(p, root)] = dds_dimensions(p)
    base = {k: v for k, v in base.items() if v}
    if not base:
        return

    # The race's own folder sets the size; it has to agree with itself first.
    counts = collections.Counter(base.values())
    size = counts.most_common(1)[0][0]
    fmt = '{0}x{1}'.format
    if len(counts) > 1:
        odd = sorted(f"{k}: {fmt(*v)}" for k, v in base.items() if v != size)
        rep.fail(area, f"the FCTP folder's {len(base)} textures are not all one size: " + ', '.join(
                     f"{n} at {fmt(*s)}" for s, n in counts.most_common()),
                 odd[:8] + ([f"(+{len(odd) - 8} more)"] if len(odd) > 8 else []) + [advice])

    # Then every option the creator can lay over it.
    off = []
    n_options = 0
    for g in face_option_groups(avm):
        wrong = collections.Counter()
        for _lnam, path in simple_entries(g):
            if path and is_dds(path) and exists(data, path):
                dims = dds_dimensions(data_path(data, path))
                if dims:
                    n_options += 1
                    if dims != size:
                        wrong[dims] += 1
        if wrong:
            off.append(f"{g.editor_id or text(g, 'TNAM')} ({plugin_name(g)}): " + ', '.join(
                f"{n} at {fmt(*s)}" for s, n in wrong.most_common()))
    if off:
        rep.fail(area, f"{len(off)} tint group(s) offer options that aren't {fmt(*size)}, the "
                       f"size of the race's face maps", off[:12]
                 + ([f"(+{len(off) - 12} more groups)"] if len(off) > 12 else [])
                 + [advice, "A vanilla option is 1024: at any other size, replace or drop it."])
    elif len(counts) == 1:
        rep.ok(area, f"the face maps and all {n_options} tint options are {fmt(*size)}")


def check_skin_tones(rep, data, race, avm, own_prefix, sexes=SEXES):
    """RACE -> AVMD chain. Two different lookup rules, and getting either wrong is silent.

    `avm` is avm_index(): every group in the load order by (kind, TNAM), latest winning."""
    phenotypes = set()

    fstt = text(race, 'FSTT')
    if not fstt:
        rep.warn('skin tones', "Race has no FSTT (face skin tones)")
        return phenotypes

    cg = avm.get((AVM_COMPLEX, fstt))
    if cg is None:
        if any(t == fstt for _k, t in avm):
            rep.fail('skin tones', f"FSTT {fstt!r} is not a ComplexGroup (MNAM 2)",
                     "FSTT must go through a kind-2 ComplexGroup; there is no direct "
                     "race->SimpleGroup path.")
        else:
            rep.fail('skin tones', f"FSTT {fstt!r} matches no AVMD in the load order",
                     "RACE->AVMD matches the target's bare TNAM.")
        return phenotypes
    rep.ok('skin tones', f"FSTT -> ComplexGroup {cg.editor_id!r}")

    key = None
    for sr in cg.subrecords:
        if sr.signature == 'LNAM':
            key = sr.get_string()
            if label_sex(key) not in (*sexes, None):
                key = None                      # the other sex's face; not being checked
                continue
            phenotypes.add(key)
        elif sr.signature == 'VNAM' and key is not None:
            target = sr.get_string()
            # ComplexGroup entries match "<Kind>_" + TNAM, NOT the bare TNAM.
            head, _, rest = target.partition('_')
            if head not in ('SimpleGroup', 'ComplexGroup', 'Modulation'):
                rep.fail('skin tones', f"{key}: VNAM {target!r} has no <Kind>_ prefix",
                         "Must be 'SimpleGroup_' + the target's TNAM.")
                continue
            child = avm.get((AVM_PREFIX[head], rest))
            if child is None:
                rep.fail('skin tones', f"{key}: -> {target} matches no group in the load order",
                         f"A ComplexGroup entry names its target as '<Kind>_' + TNAM; no "
                         f"{head} has TNAM {rest!r}.")
                continue
            check_simplegroup_textures(rep, data, child, key, own_prefix)

    return phenotypes


def check_simplegroup_textures(rep, data, grp, key, own_prefix):
    """Skin-tone albedo paths. A vanilla path that isn't loose is almost certainly inside a
    BA2, which we can't see -- only paths under the race's own texture tree are a real fail."""
    missing_own, missing_other = [], []
    for sr in grp.subrecords:
        if sr.signature != 'VNAM':
            continue
        rel = sr.get_string()
        if not rel or exists(data, rel):
            continue
        norm = rel.lower().replace('/', '\\')
        (missing_own if own_prefix and own_prefix in norm else missing_other).append(rel)

    if missing_own:
        rep.fail('skin tones', f"{key}: {len(missing_own)} of this race's skin-tone "
                               f"texture(s) not on disk", missing_own[:5])
    if missing_other:
        rep.warn('skin tones',
                 f"{key}: {len(missing_other)} skin-tone texture(s) not found loose",
                 [missing_other[0] + (f"  (+{len(missing_other) - 1} more)"
                                      if len(missing_other) > 1 else ''),
                  "Probably vanilla and inside a BA2, which this tool cannot read. But note "
                  "they are HUMAN textures -- any skin tone but the overridden one gives a "
                  "human face."])
    if not missing_own and not missing_other:
        rep.ok('skin tones', f"{key}: skin-tone textures present")


# --- the Creation Kit's own skin-tone rules --------------------------------------------------

# AVMD MNAM group kinds, per sf1.pas wbIdxAVMByType, and the prefixes a Complex group's VNAM uses.
AVM_SIMPLE, AVM_COMPLEX, AVM_MODULATION = 1, 2, 3
AVM_KIND_NAME = {AVM_SIMPLE: 'Simple', AVM_COMPLEX: 'Complex', AVM_MODULATION: 'Modulation'}
AVM_PREFIX = {'SimpleGroup': AVM_SIMPLE, 'ComplexGroup': AVM_COMPLEX, 'Modulation': AVM_MODULATION}

# The game-wide filter of dermaesthetic options per skin tone, and the group it filters. Both
# are looked up by name; no race field points at them.
CHARGEN_DERMAESTHETIC = 'Chargen_Dermaesthetic'
DERMAESTHETIC = 'Dermaesthetic'


def avm_index(plugins):
    """Every AVMD group in the load order, keyed by (kind, TNAM); a later plugin wins.

    AVMD groups are found by name, never by formID, and a name is unique only within a kind --
    ComplexionMask1 exists as both a Simple and a Modulation group -- so the kind is part of the
    key. Masters are included because a race routinely points at vanilla groups."""
    out = {}
    for plugin in plugins:
        for rec in plugin.get_records_by_signature('AVMD'):
            name, kind = text(rec, 'TNAM'), rec.get_subrecord('MNAM')
            if name and kind is not None and kind.size == 4:
                out[(kind.get_uint32(), name)] = rec
    return out


def avm_entries(rec):
    """A group's entry names (LNAM), in order."""
    return [sr.get_string() for sr in rec.get_subrecords('LNAM')]


def complex_children(rec, index):
    """A Complex group's entries as {LNAM: the group it resolves to, or None}.

    An entry's VNAM names its target as '<Kind>_<TNAM>'. With no VNAM, the LNAM names the target
    itself, as whichever kind of group exists under that name."""
    pairs, cur = [], None
    for sr in rec.subrecords:
        if sr.signature == 'LNAM':
            cur = [sr.get_string(), None]
            pairs.append(cur)
        elif sr.signature == 'VNAM' and cur is not None and cur[1] is None:
            cur[1] = sr.get_string()
    out = {}
    for lnam, vnam in pairs:
        if vnam:
            head, _, name = vnam.partition('_')
            kind = AVM_PREFIX.get(head)
            out[lnam] = index.get((kind, name)) if kind else None
        else:
            out[lnam] = next((index[(k, lnam)] for k in AVM_KIND_NAME if (k, lnam) in index),
                             None)
    return out


# A hair or beard head part's NAM3 "Mask" is a key into one of these Simple groups, chosen by
# the part's type. Measured over every vanilla hair/beard part: 115 keys, all exact-case, all in
# the group for their type. Eyebrows use NAM3 for a colour group instead.
FOLLICLE_GROUPS = {HDPT_HAIR: 'HairFollicleMask', HDPT_FACIAL_HAIR: 'BeardFollicleMask'}

# A Simple group named '<group>_AVMDEXT' extends <group>: Shattered Space adds its scalp masks
# that way, never overriding HairFollicleMask, and its hair parts' keys resolve only there.
AVMD_EXTENSION = '_AVMDEXT'


def complex_entries(rec):
    """A Complex group's entries as [(LNAM, VNAM or None)], in order."""
    pairs = []
    for sr in rec.subrecords:
        if sr.signature == 'LNAM':
            pairs.append([sr.get_string(), None])
        elif sr.signature == 'VNAM' and pairs and pairs[-1][1] is None:
            pairs[-1][1] = sr.get_string()
    return [tuple(p) for p in pairs]


def complex_target(lnam, vnam, index):
    """The group a Complex entry resolves to, or None -- complex_children's rule for one entry."""
    if vnam:
        head, _, name = vnam.partition('_')
        kind = AVM_PREFIX.get(head)
        return index.get((kind, name)) if kind else None
    return next((index[(k, lnam)] for k in AVM_KIND_NAME if (k, lnam) in index), None)


def check_avm_groups(rep, data, plugins, own_avmds, official):
    """Every AVMD group the mods define or override must resolve: each Complex entry to a
    group, each Simple entry's texture to a file.

    These are global lists, found by name, so a broken entry fails silently and for everyone:
    a stack slot pointed at a group nobody defines just never composites. Vanilla's own copy
    of a group sets the bar -- the shipped stack has entries that resolve to nothing -- so an
    entry vanilla's copy can't resolve either isn't the mod's doing. Textures only vanilla's
    records name are in BA2s, out of sight."""
    area = 'tint groups'
    avm = avm_index(plugins)
    vanilla = avm_index([p for p in plugins
                         if p.file_path is not None and p.file_path.name.lower() in official])
    vanilla_paths = {p.lower().replace('/', '\\')
                     for g in vanilla.values() for _, p in simple_entries(g) if p}
    n = 0
    for rec in own_avmds:
        kind = rec.get_subrecord('MNAM')
        kind = kind.get_uint32() if kind is not None and kind.size == 4 else None
        name = text(rec, 'TNAM')
        who = f"{rec.editor_id or name} ({plugin_name(rec)})"
        theirs = vanilla.get((kind, name))
        if kind == AVM_COMPLEX:
            before = dict(complex_entries(theirs)) if theirs is not None else {}
            for lnam, vnam in complex_entries(rec):
                n += 1
                if complex_target(lnam, vnam, avm) is not None:
                    continue
                if lnam in before and before[lnam] == vnam:
                    rep.info(area, f"{who}: {lnam} -> {vnam} resolves to nothing, as in "
                                   f"vanilla")
                    continue
                detail = ["A Complex entry names its target as '<Kind>_' + TNAM; no group "
                          "of that kind and name is in the load order."]
                was = before.get(lnam)
                if was and complex_target(lnam, was, avm) is not None:
                    detail.append(f"Vanilla's {name} has {lnam} -> {was}.")
                rep.fail(area, f"{who}: {lnam} -> {vnam or lnam} matches no group", detail)
        elif kind == AVM_SIMPLE:
            missing = []
            for lnam, path in simple_entries(rec):
                if not path:
                    continue
                n += 1
                if exists(data, path) or path.lower().replace('/', '\\') in vanilla_paths:
                    continue
                missing.append(f"{lnam}: {path}")
            if missing:
                rep.fail(area, f"{who}: {len(missing)} texture(s) not found",
                         missing[:8] + ([f"(+{len(missing) - 8} more)"] if len(missing) > 8
                                        else []))
    if n and not any(f[0] == FAIL and f[1] == area for f in rep.findings):
        rep.ok(area, f"all {n} entries in the mods' AVMD groups resolve")


def simple_entries(rec):
    """A Simple group's entries as [(LNAM, VNAM or None)], in order."""
    pairs = []
    for sr in rec.subrecords:
        if sr.signature == 'LNAM':
            pairs.append([sr.get_string(), None])
        elif sr.signature == 'VNAM' and pairs and pairs[-1][1] is None:
            pairs[-1][1] = sr.get_string()
    return [tuple(p) for p in pairs]


def check_follicle_mask(rep, data, hdpt, avm, official):
    """A hair or beard part's NAM3 mask must be a key in its follicle-mask group, and the
    texture that entry names must exist.

    The engine never builds a path from the key: it looks the key up in the group, which pairs
    it with a texture path. A .dds on disk with the right-looking name does nothing if no group
    lists it. Textures named by the game's own plugins live in BA2s, so only a mod's entries
    are looked for on disk."""
    pnam = hdpt.get_subrecord('PNAM')
    grp_name = FOLLICLE_GROUPS.get(pnam.get_uint32() if pnam is not None else None)
    key = text(hdpt, 'NAM3')
    if grp_name is None or key is None or key.strip().upper() in ('', 'NONE'):
        return
    who = hdpt.editor_id or str(hdpt.form_id)
    names = [grp_name, grp_name + AVMD_EXTENSION]
    groups = [(n, avm[(AVM_SIMPLE, n)]) for n in names if (AVM_SIMPLE, n) in avm]

    found = case_only = None
    for gname, grp in groups:
        for lnam, vnam in simple_entries(grp):
            if lnam == key:
                found = (gname, grp, vnam)
                break
            if case_only is None and lnam.lower() == key.lower():
                case_only = (gname, grp, vnam, lnam)
        if found:
            break

    if found is None and case_only is not None:
        gname, grp, vnam, lnam = case_only
        rep.warn('hair masks', f"{who}: mask (NAM3) '{key}' matches '{lnam}' in {gname} only "
                               f"if case is ignored",
                 "Every vanilla part matches its key exactly; make the case agree.")
        found = (gname, grp, vnam)

    if found is None:
        elsewhere = sorted(f"{AVM_KIND_NAME.get(k, k)} {n}" for (k, n), g in avm.items()
                           if n not in names and key in avm_entries(g))
        detail = [f"A {'facial hair' if grp_name == 'BeardFollicleMask' else 'hair'} part "
                  f"(PNAM {pnam.get_uint32()}) looks its NAM3 up in the Simple group "
                  f"{grp_name}. The key isn't a filename; a .dds on disk does nothing unless a "
                  f"group entry points at it."]
        if elsewhere:
            detail.append(f"'{key}' IS listed in {', '.join(elsewhere)} -- the wrong group "
                          f"for this part type.")
        detail.append(f"Fix: add an entry LNAM '{key}' / VNAM <texture path> to {grp_name}, "
                      f"or to a new Simple group named {grp_name}{AVMD_EXTENSION} (how "
                      f"Shattered Space extends it without overriding the vanilla record).")
        rep.fail('hair masks', f"{who}: mask (NAM3) '{key}' is not listed in {grp_name}",
                 detail)
        return

    gname, grp, vnam = found
    if not vnam:
        rep.fail('hair masks', f"{who}: {gname} entry '{key}' names no texture (VNAM)")
    elif plugin_name(grp) in official:
        rep.ok('hair masks', f"{who}: mask '{key}' listed in {gname}")
    elif not exists(data, vnam):
        rep.fail('hair masks', f"{who}: mask '{key}' texture not on disk",
                 [vnam, f"named by {gname} in {plugin_name(grp)}"])
    else:
        rep.ok('hair masks', f"{who}: mask '{key}' in {gname} -> {vnam}")


def check_ck_simple_group(rep, who, part, name, index):
    """A body or hands skin-tone type must name a non-empty Simple group. Returns it, or None."""
    if not name:
        rep.fail('skin tone rules', f"{who}: race has no {part} skin tone type",
                 "CK: \"Empty skin tone type\". STON has nothing to index for this part.")
        return None
    grp = index.get((AVM_SIMPLE, name))
    if grp is None:
        other = [AVM_KIND_NAME[k] for k in (AVM_COMPLEX, AVM_MODULATION) if (k, name) in index]
        rep.fail('skin tone rules', f"{who}: {part} skin tone type '{name}' is not a Simple group",
                 [f"it exists only as a {' / '.join(other)} group" if other else
                  "no AVMD group of that name in the plugin or its masters",
                  "CK: \"is not a valid SimpleGroup type\"."])
        return None
    if not avm_entries(grp):
        rep.fail('skin tone rules', f"{who}: {part} skin tone type '{name}' has no entries")
        return None
    return grp


def check_ck_skin_tone_rules(rep, per_sex, index, npcs, sexes=SEXES):
    """The skin-tone rules the Creation Kit itself validates.

    Taken from the validator strings in CreationKit.exe -- "Validates that the number of subtype
    entries for hand skin tones matches the number of entries for body skin tones" and its
    siblings -- so this is Bethesda's definition of a valid race, not an inference from vanilla.

    One STON indexes the body, hands and face groups at once, and the BODY group is the count the
    rest must match: a shorter group has no entry for some tones, which is a missing or wrong
    texture for any actor that picks one. Those are FAILs. The game-wide dermaesthetic filter and
    an out-of-range NPC index are WARNs -- the first only narrows the creator's options, and the
    engine clamps the second.
    """
    area = 'skin tone rules'
    fstt_name = per_sex['FEMALE']['tones'].get('FSTT') or per_sex['MALE']['tones'].get('FSTT')
    fstt = index.get((AVM_COMPLEX, fstt_name)) if fstt_name else None
    faces = complex_children(fstt, index) if fstt is not None else {}
    if fstt_name and fstt is None:
        rep.info(area, f"face skin tones '{fstt_name}' is not a Complex group in the load order; "
                       f"face rules skipped")

    if faces:
        bad = sorted(k for k in faces if not k.startswith(('male', 'female')))
        if bad:
            rep.fail(area, f"{len(bad)} face skin tone label(s) not prefixed 'male' or 'female'",
                     [', '.join(bad[:8]),
                      "CK: every face skin tone label must be prefixed with 'male' or 'female'. "
                      "The creator sorts faces by sex on that prefix."])
        else:
            rep.ok(area, f"all {len(faces)} face skin tone labels are sex-prefixed")

    body_counts = {}
    for sx in sexes:
        block = per_sex[sx]
        if not block['tones'] and not block['phenotypes']:
            continue                                # no chargen for this sex at all
        who = sx.lower()
        tones = block['tones']

        body = check_ck_simple_group(rep, who, 'body', tones.get('BSTT'), index)
        hands = check_ck_simple_group(rep, who, 'hands', tones.get('HSTT'), index)
        if body is None:
            continue
        n = len(avm_entries(body))
        body_counts[sx] = n
        rep.info(area, f"{who}: body skin tones '{tones['BSTT']}' has {n} entries -- the count "
                       f"everything else must match")

        if hands is not None:
            nh = len(avm_entries(hands))
            if nh != n:
                rep.fail(area, f"{who}: hands skin tones '{tones['HSTT']}' has {nh} entries, "
                               f"body has {n}",
                         "CK: \"same number of subtype entries as the body skin tone type\".")
            else:
                rep.ok(area, f"{who}: hands and body skin tones both have {n} entries")

        if fstt is None:
            continue

        # Every phenotype this sex can blend, plus its hard-coded default, must be a face skin
        # tone entry whose group is as long as the body's.
        default = ('male' if sx == 'MALE' else 'female') + '_default'
        wanted = list(block['phenotypes']) + [(None, default)]
        short, missing = [], []
        for rid, name in wanted:
            where = f"facial bone region {rid}" if rid is not None else "the default"
            if not name:
                rep.fail(area, f"{who}: empty skin tone subtype at {where}")
                continue
            if name not in faces:
                missing.append(f"'{name}' ({where})")
                continue
            grp = faces[name]
            if grp is None:
                rep.fail(area, f"{who}: face skin tone entry '{name}' resolves to no group")
                continue
            nf = len(avm_entries(grp))
            if nf != n:
                short.append(f"'{name}' has {nf}")

        if missing:
            rep.fail(area, f"{who}: {len(missing)} phenotype(s) are not entries of face skin tones "
                           f"'{fstt_name}'",
                     [', '.join(missing[:6]),
                      "CK: \"Invalid skin tone subtype ... should be a valid subtype\". The "
                      "phenotype table names a face the skin-tone group cannot supply."])
        if short:
            rep.fail(area, f"{who}: {len(short)} face skin tone group(s) differ from the body's "
                           f"{n} entries",
                     [', '.join(short[:6]),
                      "CK: \"same number of subtype entries as the body skin tone type\"."])
        if not missing and not short:
            rep.ok(area, f"{who}: all {len(wanted)} phenotype(s) (incl. {default}) have face skin "
                         f"tones matching the body's {n}")

    # The dermaesthetic filter is one game-wide record, so it has to agree with every playable
    # race at once.
    derm = index.get((AVM_COMPLEX, CHARGEN_DERMAESTHETIC))
    if derm is not None and body_counts:
        nd = len(avm_entries(derm))
        for sx, n in sorted(body_counts.items()):
            # CK validates they match, but only one direction bites. Fewer tones than the filter
            # just leaves filter entries unused -- vanilla ChildRace ships 3 against its 9.
            if n > nd:
                rep.warn(area, f"{sx.lower()}: body has {n} skin tones, the game-wide "
                               f"'{CHARGEN_DERMAESTHETIC}' filter has only {nd}",
                         [f"Tones {nd}..{n - 1} have no filter entry, so the creator offers them "
                          f"no dermaesthetic choices.",
                          "The filter is found by name and shared by every race: lengthening it "
                          "for this race changes it for all the others too."])
            elif n < nd:
                rep.info(area, f"{sx.lower()}: body has {n} skin tones, fewer than the "
                               f"'{CHARGEN_DERMAESTHETIC}' filter's {nd} -- harmless, and what "
                               f"vanilla ChildRace does")
        main = index.get((AVM_SIMPLE, DERMAESTHETIC))
        if main is not None:
            valid = set(avm_entries(main))
            bad = sorted({e for grp in complex_children(derm, index).values() if grp is not None
                          for e in avm_entries(grp) if e not in valid})
            if bad:
                rep.warn(area, f"{len(bad)} dermaesthetic filter entr(ies) are not options of "
                               f"'{DERMAESTHETIC}'",
                         [', '.join(bad[:6]),
                          "CK: \"all entries from skin tone filters are valid entries from the main "
                          "Dermaesthetic reserved type\"."])

    for npc in npcs:
        ston = npc.get_subrecord('STON')
        if ston is None or ston.size < 1:
            continue
        n = body_counts.get(npc_sex(npc))
        if n is not None and ston.data[0] >= n:
            rep.warn(area, f"NPC {npc.editor_id!r} has STON {ston.data[0]} but its body skin tones "
                           f"have only {n} entries",
                     f"Valid range is 0..{n - 1} (1..{n} in the CK). The engine clamps it, so the "
                     f"NPC silently gets a different tone.")


def check_npcs(rep, race, npcs):
    for npc in npcs:
        edct = npc.get_subrecord('EDCT')
        if edct is not None and edct.size >= 1 and edct.data[0] == 0:
            rep.warn('npcs', f"{npc.editor_id!r} has no tint layers (EDCT 0)",
                     "At least one tint layer is what triggers a per-NPC FaceGen bake.")
        ston = npc.get_subrecord('STON')
        if ston is None or ston.size < 1:
            rep.warn('npcs', f"{npc.editor_id!r} has no skin tone (STON)")


def check_record_texture_paths(rep, avmds, npcs):
    """Texture paths stored in mod records must name a .dds: every AVMD Simple group entry
    the mods win with (skin tones, tint options), and every tint layer on this race's NPCs.

    The NPC's copy matters on its own -- the FaceGen bake uses the path stored on the tint
    entry, not the group's -- so fixing the group does not fix an NPC saved against it."""
    area = 'texture paths'
    bad, n = [], 0
    for rec in avmds:
        kind = rec.get_subrecord('MNAM')
        if kind is None or kind.size != 4 or kind.get_uint32() != AVM_SIMPLE:
            continue                            # Complex VNAMs name groups, not textures
        for sr in rec.get_subrecords('VNAM'):
            path = sr.get_string()
            if path:
                n += 1
                if not is_dds(path):
                    bad.append(f"{rec.editor_id or text(rec, 'TNAM')}: {path}")
    for npc in npcs:
        prev = None
        for sr in npc.subrecords:
            # A tint entry's texture is the VNAM straight after its QNAM (option name).
            if sr.signature == 'VNAM' and prev == 'QNAM':
                path = sr.get_string()
                if path:
                    n += 1
                    if not is_dds(path):
                        bad.append(f"NPC {npc.editor_id}: {path}")
            prev = sr.signature

    if bad:
        rep.fail(area, f"{len(bad)} texture path(s) in mod records are not .dds",
                 bad[:8] + ([f"(+{len(bad) - 8} more)"] if len(bad) > 8 else [])
                 + [NOT_DDS_ADVICE])
    elif n:
        rep.ok(area, f"all {n} texture paths in AVMD groups and NPC tints are .dds")


def check_race_misc(rep, race):
    if race.get_subrecord('WNAM') is None:
        rep.fail('race', "Race has no WNAM (skin ARMO)",
                 "Without a body whose ARMA covers this race, skin/tint compositing fails "
                 "and the head renders black.")
    else:
        rep.ok('race', "Race has a skin ARMO (WNAM)")

    if race.get_subrecord('SRAC') is None and not race.get_subrecords('SADD'):
        rep.warn('race', "Race has neither SRAC nor its own subgraph data",
                 "It will have no animation graph.")


# --- plugin loading ------------------------------------------------------------------------

# Top-level groups to parse. Skipping the rest turns reading Starfield.esm from a minute
# into a second, and every record type we follow by formID is here: the vanilla body morphs
# an armor addon points at, armor or head records a race reuses wholesale, and the form lists
# a head part's Valid Races goes through.
GROUPS = {'RACE', 'ARMO', 'ARMA', 'MRPH', 'HDPT', 'AVMD', 'NPC_', 'FLST', 'OTFT', 'LVLI'}

# What the game loads before anything in Plugins.txt, in this order, whether or not it is
# listed there. Starfield.esm, then the official masters -- xEdit's wbOfficialDLC in
# wbDefinitionsSF1.pas, which is the authority here; Bethesda documents no such list.
IMPLICIT_MASTERS = ['Starfield.esm']
OFFICIAL_MASTERS = ['ShatteredSpace.esm', 'Constellation.esm', 'OldMars.esm', 'SFBGS003.esm',
                    'SFBGS004.esm', 'SFBGS006.esm', 'SFBGS007.esm', 'SFBGS008.esm',
                    'SFBGS00D.esm', 'SFBGS047.esm', 'SFBGS050.esm',
                    'BlueprintShips-Starfield.esm', 'BlueprintShips-SFBGS050.esm']


def _no_string_tables():
    # Starfield.esm is flagged localized, so esplib goes looking for its string tables and
    # dies in the BA2 reader -- Starfield's archive header is not the Fallout 4 one esplib
    # knows. No check here reads a localized string, so skip the step entirely rather than
    # lose the master. Belongs in esplib as "failing to load strings is not fatal".
    esplib.plugin.Plugin._load_string_tables = lambda self: None


def plugin_masters(data, name):
    """A plugin's own master list, from its header alone. [] if the file can't be found."""
    path = name if os.path.isabs(name) else data_path(data, name)
    if not os.path.exists(path):
        return []
    return list(Plugin.load(path, only_signatures=set()).header.masters)


def load_order_names(data, plugin=None, plugins_txt=None, ccc_file=None):
    """The plugins to load, in load order.

    With `plugin`: that plugin and every master it needs, recursively, masters first -- a
    patch whose only master is a mod still needs the mod's own masters, or nothing the mod
    overrides resolves.

    Without it: the game's active load order. The implicit and official masters first (only
    those actually present), then the Creation Club list if the game has one, then the
    entries Plugins.txt marks active ('*'), in its order. `plugins_txt` and `ccc_file`
    default to the ones the installed game uses.
    """
    _no_string_tables()
    if plugin:
        order, seen = [], set()

        def gather(name):
            key = os.path.basename(name).lower()
            if key in seen:
                return
            seen.add(key)
            for m in plugin_masters(data, name):
                gather(m)
            order.append(os.path.basename(name))
        gather(plugin)
        return order

    if plugins_txt is None:
        from esplib.game_discovery import find_game
        game = find_game('sf1')
        plugins_txt = game.plugins_txt() if game else None
        if ccc_file is None and game is not None:
            ccc_file = game.ccc_file()
    if plugins_txt is None or not os.path.exists(plugins_txt):
        raise FileNotFoundError("Starfield's Plugins.txt was not found; name a plugin with "
                                "--plugin instead")

    order = list(IMPLICIT_MASTERS)
    have = {n.lower() for n in order}

    def add(name):
        if name and name.lower() not in have:
            order.append(name)
            have.add(name.lower())

    for name in OFFICIAL_MASTERS:
        if os.path.exists(data_path(data, name)):
            add(name)
    if ccc_file and os.path.exists(ccc_file):
        with open(ccc_file, encoding='utf-8', errors='replace') as f:
            for line in f:
                if os.path.exists(data_path(data, line.strip())):
                    add(line.strip())
    with open(plugins_txt, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('*'):
                add(line[1:].strip())
    return order


def official_plugins(order):
    """The names in `order` that are the game's own: their assets live in BA2s we cannot read,
    so a check that finds one of their records there has nothing to inspect."""
    official = {n.lower() for n in IMPLICIT_MASTERS + OFFICIAL_MASTERS}
    return {n.lower() for n in order if n.lower() in official}


def plugin_name(rec):
    """The file a record came from, lowercased."""
    p = rec.plugin
    return p.file_path.name.lower() if p is not None and p.file_path else ''


def load_plugins(rep, data, order, plugin_dir=None):
    """Every plugin in `order`, as an esplib PluginSet.

    The set is what makes a reference resolvable: esplib maps the file-index byte of a
    formID through the plugin's own master list, and picks the winning override when more
    than one file defines a record. Only the record types we follow are parsed, in every
    plugin alike -- any of them may be the one that wins.
    """
    _no_string_tables()
    data_dir = next((d for d in data if os.path.isdir(d)), None)
    plugins = PluginSet(LoadOrder.from_list(order, data_dir=data_dir, game_id='sf1',
                                            fallback_dir=plugin_dir))
    for who in order:
        if plugins.load_plugin(who, only_signatures=GROUPS) is None:
            rep.warn('race', f"{who!r} could not be loaded",
                     [f"looked in {', '.join(data)}",
                      "Records it owns cannot be resolved, so every check that follows one "
                      "into it is skipped."])
    return plugins


def winning_records(plugins, sig):
    """The winning copy of every `sig` record in the load order, once each, in the order the
    records first appear."""
    out, seen = [], set()
    for plugin in plugins:
        for rec in plugin.get_records_by_signature(sig):
            win = plugins.resolve_form_id(rec.form_id, plugin) or rec
            if id(win) not in seen:
                seen.add(id(win))
                out.append(win)
    return out


def find_race(plugins, edid):
    """The winning RACE whose EditorID is `edid`, or None."""
    return next((r for r in reversed(winning_records(plugins, 'RACE'))
                 if r.editor_id == edid), None)


def is_new_record(rec):
    """True if `rec` is defined by its own plugin rather than overriding a master's record."""
    p = rec.plugin
    return p is not None and rec.form_id.file_index >= len(p.header.masters)


# --- main -------------------------------------------------------------------------------------

# What -o gets when the name carries no extension of its own. The report is plain text.
REPORT_EXT = '.txt'


def report_path(name):
    """The file -o actually writes. A name with no extension gets REPORT_EXT.

    `splitext` splits on the last dot in the final component only, so a dot in a parent
    directory ("C:\\my.stuff\\report") still counts as no extension. Trailing dots go first:
    they are nobody's idea of an extension, and Windows cannot store them in a name anyway."""
    name = name.rstrip('.')
    stem, ext = os.path.splitext(name)
    return name if ext else stem + REPORT_EXT

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', required=True,
                    help="Starfield Data folder, or a comma-separated list of folders searched "
                         "in order (e.g. Data, then unpacked vanilla assets)")
    ap.add_argument('--plugin', help="plugin filename or path; it and its masters are loaded. "
                                     "Omit to load the game's active load order (Plugins.txt)")
    ap.add_argument('--race', help="race EDID, found anywhere in the load order (auto-detected "
                                   "if the mods define just one)")
    ap.add_argument('--sex', choices=['both', 'male', 'female'], default='both',
                    help="check only this sex's chargen, models and NPCs (default both)")
    ap.add_argument('-v', '--verbose', action='store_true', help="show passing checks too")
    ap.add_argument('-o', '--output', metavar='FILE',
                    help=f"write the report here instead of stdout ({REPORT_EXT} is added if "
                         f"you leave the extension off); the terminal still gets the "
                         f"one-line tally")
    args = ap.parse_args(argv)
    args.data = [d.strip() for d in args.data.split(',') if d.strip()]
    missing = [d for d in args.data if not os.path.isdir(d)]
    if not args.data or missing:
        ap.error(f"--data folder not found: {', '.join(missing) or '(none given)'}")

    if not args.output:
        return run(args, sys.stdout)[0]

    # Report to the file, tally to the terminal -- a run that is gating a build should say
    # what happened without anyone having to open the file. Name the resolved path, which is
    # not always what was typed.
    path = report_path(args.output)
    with open(path, 'w', encoding='utf-8') as out:
        code, summary = run(args, out)
    print(f"{path}: {summary or 'no report written -- see the file'}")
    return code


def run(args, out):
    """The audit itself, writing its report to `out`. Returns (exit code, tally)."""
    plugin_path, plugin_dir = args.plugin, None
    if plugin_path:
        if not os.path.isabs(plugin_path) and not os.path.exists(plugin_path):
            plugin_path = data_path(args.data, plugin_path)
        if not os.path.exists(plugin_path):
            print(f"Could not find {args.plugin}", file=out)
            return 2, None
        plugin_dir = os.path.dirname(os.path.abspath(plugin_path))
        source = f"{os.path.basename(plugin_path)} and its masters"
    else:
        source = "the active load order (Plugins.txt)"

    rep = Report()
    try:
        order = load_order_names(args.data, plugin=plugin_path)
    except FileNotFoundError as e:
        print(str(e), file=out)
        return 2, None
    plugins = load_plugins(rep, args.data, order, plugin_dir)
    official = official_plugins(order)

    # The race: by EditorID anywhere in the load order, else the one race a mod defines.
    if args.race:
        race = find_race(plugins, args.race)
        if race is None:
            print(f"No RACE {args.race!r} in {source}", file=out)
            return 2, None
    else:
        races = [r for r in winning_records(plugins, 'RACE')
                 if plugin_name(r) not in official and is_new_record(r)]
        if len(races) != 1:
            print(f"{len(races)} races defined outside the game's own plugins; pick one with "
                  f"--race: {[r.editor_id for r in races]}", file=out)
            return 2, None
        race = races[0]

    print(f"Race    : {race.editor_id} {race.form_id} (winning copy in "
          f"{race.plugin.file_path.name if race.plugin else '?'})", file=out)
    print(f"Loaded  : {len(order)} plugins -- {source}", file=out)
    sexes = SEXES if args.sex == 'both' else (args.sex.upper(),)
    if args.sex != 'both':
        print(f"Sex     : {args.sex} only", file=out)

    # The mod's own actor-texture tree, e.g. 'actors\fsfcanine' from the FCTP path. Used to
    # tell "this mod forgot to make a file" from "this is vanilla and lives in a BA2".
    fctp = (text(race, 'FCTP') or '').lower().replace('/', '\\')
    own_root = '\\'.join(fctp.split('\\')[:2]) or None

    nif_reader = make_nif_reader(own_root)
    if nif_reader is None:
        rep.warn('nif', "NiflyDLL could not be loaded -- NIF and mesh checks were SKIPPED",
                 "MaterialID, external .mesh and morph-vs-mesh vertex counts are unchecked.")

    # Everything below works on winning records across the whole load order. "Ours" means
    # a winning copy that lives outside the game's own plugins -- the only records whose
    # assets we can see on disk.
    npcs = [r for r in winning_records(plugins, 'NPC_')
            if plugins.resolve_reference(r, 'RNAM') is race and npc_sex(r) in sexes]
    avm = avm_index(plugins)
    own_avmds = [r for r in winning_records(plugins, 'AVMD') if plugin_name(r) not in official]

    # Two groups of the same kind and name in ONE plugin are ambiguous. The same name in a
    # later plugin is not -- that is how a mod replaces a vanilla group.
    for p in plugins:
        if p.file_path is None or p.file_path.name.lower() in official:
            continue
        keys = [(r.get_subrecord('MNAM').get_uint32() if r.get_subrecord('MNAM') else None,
                 text(r, 'TNAM')) for r in p.get_records_by_signature('AVMD')]
        dupes = {k[1] for k in keys if k[1] and keys.count(k) > 1}
        if dupes:
            rep.fail('skin tones', f"{p.file_path.name}: duplicate AVMD TNAMs make lookups "
                                   f"ambiguous", sorted(dupes))

    per_sex = split_by_sex(race)
    crowd = is_crowd_race(race, plugins)

    check_race_misc(rep, race)
    if crowd:
        rep.info('race', f"crowd race (Armor Race {CROWD_RACE}): head, eyes and arms come from "
                         f"the head armor, so the head part, tint, skin tone and face texture "
                         f"checks are skipped")
    else:
        own_face = check_head_parts(rep, data=args.data, race=race, nif_reader=nif_reader,
                                    per_sex=per_sex, plugins=plugins, official=official,
                                    sexes=sexes, avm=avm)
        check_chargen_options(rep, race_head_parts(race, plugins, official), plugins, sexes)
    check_body(rep, args.data, race, plugins, nif_reader, own_root, sexes, crowd=crowd)
    if not crowd:
        check_npcs(rep, race, npcs)
    check_record_texture_paths(rep, own_avmds, npcs)
    check_avm_groups(rep, args.data, plugins, own_avmds, official)

    if crowd:
        check_crowd_heads(rep, args.data, crowd_head_models(plugins, npcs))
        n_fail = rep.render(args.verbose, out)
        return (1 if n_fail else 0), rep.summary()

    phenotypes = check_skin_tones(rep, args.data, race, avm, fctp, sexes)
    check_ck_skin_tone_rules(rep, per_sex, avm, npcs, sexes)
    regions = {r for sx in sexes for r in per_sex[sx]['regions']}
    check_face_textures(rep, args.data, race, phenotypes or {sexes[0].lower() + '_default'},
                        regions)
    if text(race, 'FCTP'):
        check_face_texture_sizes(rep, args.data, text(race, 'FCTP'), avm)

    composed = check_composition(rep, per_sex, own_face, sexes)

    # Morphs are per-sex: a male head is judged against the male MPGM list only.
    for sx, face in sorted(own_face.items()):
        mrph = plugins.resolve_reference(face, 'MNAM')
        verts = head_mesh_verts(args.data, face)
        if verts:
            rep.info('morphs', f"{sx.lower()} head mesh has {verts} vertices")
        check_morphs(rep, args.data, mrph, per_sex[sx]['morphs'], verts,
                     composed_names=composed.get(sx))

    n_fail = rep.render(args.verbose, out)
    return (1 if n_fail else 0), rep.summary()


if __name__ == '__main__':
    sys.exit(main())
