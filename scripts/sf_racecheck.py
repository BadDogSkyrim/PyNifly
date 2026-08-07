"""Audit a Starfield custom race for the things that silently break a head.

Every check here corresponds to a failure that actually cost a debugging session: a head that
renders black, renders invisible, or crashes the Creation Kit during FaceGen. Most of them are
silent in the CK -- the whole point of this tool is to make them loud.

    python scripts/sf_racecheck.py --data "C:\\...\\Starfield\\Data" --plugin FSF.esp
    python scripts/sf_racecheck.py --data ... --plugin FSF.esp --race FSFCanineRace

The race is auto-detected when the plugin defines exactly one. NIF checks need PyNifly's
NiflyDLL and are skipped with a note if it can't be loaded; everything else is pure Python.

Exit code is 1 if anything FAILed, so it can gate a build.
"""

import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'io_scene_nifly'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sf_plugin
from pyn.sf_morph import MorphFile
from pyn.sf_materials import material_id

FAIL, WARN, OK, INFO = 'FAIL', 'WARN', 'ok', 'info'

# Head-part types from HDPT PNAM, as seen in vanilla.
HDPT_FACE = 1

# The four base maps a FaceGen bake reads from the race's FCTP directory, by filename
# convention. Only the albedo has an AVMD route; the rest are filename-only.
FCTP_SUFFIXES = ['_normal.dds', '_rough.dds', '_ao.dds']


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

    def render(self, verbose):
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
                    print(f"\n-- {ar} " + "-" * max(0, 58 - len(ar)))
                    area = ar
                print(f"  [{lv:4}] {msg}")
                if detail:
                    for line in (detail if isinstance(detail, list) else [detail]):
                        print(f"         {line}")
        n_fail = sum(1 for f in self.findings if f[0] == FAIL)
        n_warn = sum(1 for f in self.findings if f[0] == WARN)
        n_ok = sum(1 for f in self.findings if f[0] == OK)
        print(f"\n{'=' * 64}\n{n_fail} failed, {n_warn} warnings, {n_ok} passed")
        if not verbose and n_ok:
            print("(-v shows passing checks)")
        return n_fail


# --- file helpers ---------------------------------------------------------------------------

def data_path(data, *parts):
    return os.path.join(data, *[p.replace('\\', os.sep).replace('/', os.sep) for p in parts])


def exists(data, *parts):
    return os.path.exists(data_path(data, *parts))


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


def resolve_mesh(data, mesh_name):
    """A NIF's meshName -> a path under Data. Names come with or without the geometries
    prefix and with or without the .mesh extension."""
    n = mesh_name.replace('/', '\\')
    if not n.lower().startswith('geometries\\'):
        n = 'geometries\\' + n
    if not n.lower().endswith('.mesh'):
        n += '.mesh'
    return data_path(data, n)


# --- morph checks ---------------------------------------------------------------------------

def check_morphs(rep, data, mrph, declared_names, head_verts):
    """The single most expensive class of bug: morphs the engine cannot use."""
    if mrph is None:
        rep.fail('morphs', "Head part has no MRPH (Morphable Object) record")
        return

    for sig, label in (('TCMP', 'chargen'), ('TMPP', 'performance')):
        rel = mrph.string(sig)
        if not rel:
            rep.fail('morphs', f"MRPH has no {sig} ({label} morph path)")
            continue

        d = data_path(data, rel)
        f = os.path.join(d, 'morph.dat')
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


# --- head part / nif checks -----------------------------------------------------------------

def split_by_sex(race):
    """The race's per-sex chargen blocks. MNAM opens the male block, FNAM the female, and
    head parts / morph groups / regions all belong to whichever is open."""
    out = {'MALE': {'parts': [], 'morphs': [], 'regions': []},
           'FEMALE': {'parts': [], 'morphs': [], 'regions': []}}
    sex, idx = None, None
    for s, d in race.subs:
        if s == 'MNAM':
            sex = 'MALE'
        elif s == 'FNAM':
            sex = 'FEMALE'
        elif sex is None:
            continue
        elif s == 'INDX' and len(d) == 4:
            idx = struct.unpack('<I', d)[0]
        elif s == 'HEAD' and len(d) == 4:
            out[sex]['parts'].append((idx, struct.unpack('<I', d)[0]))
        elif s == 'MPGM':
            out[sex]['morphs'].append(sf_plugin._decode(d))
        elif s == 'MPGN':
            out[sex]['regions'].append(sf_plugin._decode(d))
    return out


def check_head_parts(rep, data, race, by_id, npcs, nif_reader, per_sex):
    """The race's own head parts, the NIFs behind them, and whether NPCs actually wear them."""
    parts = {sx: per_sex[sx]['parts'] for sx in per_sex}
    own_face = {}
    for sx in ('MALE', 'FEMALE'):
        if not parts[sx]:
            rep.warn('head parts', f"{sx.lower()}: race lists no head parts")
            continue
        rep.ok('head parts', f"{sx.lower()}: {len(parts[sx])} head parts")
        for _i, fid in parts[sx]:
            hdpt = by_id.get(fid)
            if hdpt is None:
                continue                      # lives in a master; can't inspect it here
            if hdpt.formid_of('PNAM') == HDPT_FACE:
                own_face[sx] = hdpt
            check_head_nif(rep, data, hdpt, nif_reader)

    for sx, hdpt in own_face.items():
        for npc in npcs:
            if hdpt.formid not in npc.formids('PNAM'):
                rep.fail('head parts',
                         f"NPC {npc.edid!r} does not use this race's face part "
                         f"{hdpt.edid!r}",
                         ["The NPC's own PNAM list overrides the race's, so it is wearing "
                          "some other (probably vanilla) head.",
                          f"add {hdpt.formid:08X} to its head parts"])
            else:
                rep.ok('head parts', f"NPC {npc.edid!r} uses {hdpt.edid!r}")

    if not own_face:
        rep.warn('head parts', "Race defines no Face head part of its own (PNAM type 1)",
                 "Every head part resolves to a master, so this race has no custom head.")
    return own_face


def check_head_nif(rep, data, hdpt, nif_reader):
    """The NIF a head part names, its external .mesh, and the facebones pair."""
    modl = hdpt.string('MODL')
    if not modl:
        rep.fail('nif', f"{hdpt.edid}: head part has no MODL")
        return
    if not exists(data, 'meshes', modl):
        rep.fail('nif', f"{hdpt.edid}: MODL not on disk", modl)
        return
    rep.ok('nif', f"{hdpt.edid}: MODL present", modl)

    # A Starfield head part needs a facebones twin next to it. Match case-insensitively
    # against the real directory listing -- probing candidate spellings on Windows finds the
    # same file several times over.
    stem, ext = os.path.splitext(os.path.basename(modl))
    folder = data_path(data, 'meshes', os.path.dirname(modl))
    facebones = None
    if os.path.isdir(folder):
        want = (stem + '_facebones' + ext).lower()
        facebones = next((f for f in os.listdir(folder) if f.lower() == want), None)
    if facebones is None:
        rep.fail('nif', f"{hdpt.edid}: no _facebones NIF beside the head",
                 [f"expected {stem}_facebones{ext}",
                  "A head part without its facebones twin does not render."])
    else:
        rep.ok('nif', f"{hdpt.edid}: facebones NIF present ({facebones})")

    if nif_reader is None:
        return
    todo = [modl]
    if facebones:
        todo.append(os.path.join(os.path.dirname(modl), facebones))
    for rel in todo:
        nif_reader(rep, data, data_path(data, 'meshes', rel), rel)


def check_material(rep, data, mat_rel, own_root, seen):
    """A shape's `.mat`: does it resolve, is it game-valid, do its textures exist?

    A material that parses fine but points at a texture nobody produced renders the shape
    black, and nothing in the CK says so.
    """
    if not mat_rel or mat_rel in seen:
        return
    seen.add(mat_rel)

    path = data_path(data, mat_rel)
    if not os.path.exists(path):
        rep.info('materials', f"{mat_rel}: no loose file (compiled into the .cdb?)")
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

    missing_own, missing_other = [], []
    for o in objects:
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
            if exists(data, rel):
                continue
            norm = rel.lower()
            (missing_own if own_root and own_root in norm
             else missing_other).append(f"{name}: {rel}")

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
    try:
        from pyn.pynifly import NifFile
    except Exception:
        return None

    def read(rep, data, path, label):
        try:
            f = NifFile(path)
        except Exception as e:
            rep.warn('nif', f"{label}: could not be read: {e}")
            return
        for s in f.shapes:
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


def head_mesh_verts(data, hdpt, nif_reader):
    """Vertex count of the face head part's mesh, or None if it can't be determined."""
    modl = hdpt.string('MODL') if hdpt else None
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


# --- texture / skin-tone checks --------------------------------------------------------------

def check_face_textures(rep, data, race, phenotypes, regions):
    """FCTP supplies the FaceGen base maps by filename convention -- no AVMD route, no
    fallback to the material."""
    fctp = race.string('FCTP')
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
            if not os.path.exists(os.path.join(d, pheno + suffix)):
                bucket.append(pheno + suffix)
    for region in sorted(regions) + ['null']:
        if not os.path.exists(os.path.join(d, f"FCT_{region}_mask.dds")):
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
                 [f"{len({o.rsplit('_', 1)[0] for o in optional})} phenotypes affected",
                  "Only bites once chargen can select those phenotypes."])

    # Source art alongside the DDS is normal while authoring -- worth noting, not a failure,
    # since it only matters if something actually references it or it ships in the kit.
    stray = [f for f in os.listdir(d) if f.lower().endswith(('.png', '.tga', '.jpg'))]
    if stray:
        rep.warn('face textures', f"{len(stray)} non-DDS file(s) in the FCTP directory",
                 [', '.join(stray[:6]),
                  "Starfield loads DDS only. Harmless as working files; exclude them when "
                  "building the kit."])


def check_skin_tones(rep, data, race, avmd_by_tnam, own_prefix):
    """RACE -> AVMD chain. Two different lookup rules, and getting either wrong is silent."""
    phenotypes = set()

    fstt = race.string('FSTT')
    if not fstt:
        rep.warn('skin tones', "Race has no FSTT (face skin tones)")
        return phenotypes

    cg = avmd_by_tnam.get(fstt)
    if cg is None:
        rep.fail('skin tones', f"FSTT {fstt!r} matches no AVMD",
                 "RACE->AVMD matches the target's bare TNAM.")
        return phenotypes
    if cg.formid_of('MNAM') != 2:
        rep.fail('skin tones', f"FSTT {fstt!r} is not a ComplexGroup (MNAM 2)",
                 "FSTT must go through a kind-2 ComplexGroup; there is no direct "
                 "race->SimpleGroup path.")
        return phenotypes
    rep.ok('skin tones', f"FSTT -> ComplexGroup {cg.edid!r}")

    key = None
    for s, d in cg.subs:
        if s == 'LNAM':
            key = sf_plugin._decode(d)
            phenotypes.add(key)
        elif s == 'VNAM':
            target = sf_plugin._decode(d)
            # ComplexGroup entries match "<Kind>_" + TNAM, NOT the bare TNAM.
            head, _, rest = target.partition('_')
            if head not in ('SimpleGroup', 'ComplexGroup', 'Modulation'):
                rep.fail('skin tones', f"{key}: VNAM {target!r} has no <Kind>_ prefix",
                         "Must be 'SimpleGroup_' + the target's TNAM.")
                continue
            child = avmd_by_tnam.get(rest)
            if child is None:
                # May legitimately live in a master.
                rep.info('skin tones', f"{key}: -> {target} (not in this plugin)")
                continue
            check_simplegroup_textures(rep, data, child, key, own_prefix)

    return phenotypes


def check_simplegroup_textures(rep, data, grp, key, own_prefix):
    """Skin-tone albedo paths. A vanilla path that isn't loose is almost certainly inside a
    BA2, which we can't see -- only paths under the race's own texture tree are a real fail."""
    missing_own, missing_other = [], []
    for s, d in grp.subs:
        if s != 'VNAM':
            continue
        rel = sf_plugin._decode(d)
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


def check_npcs(rep, race, npcs):
    for npc in npcs:
        edct = npc.get('EDCT')
        if edct is not None and len(edct) >= 1 and edct[0] == 0:
            rep.warn('npcs', f"{npc.edid!r} has no tint layers (EDCT 0)",
                     "At least one tint layer is what triggers a per-NPC FaceGen bake.")
        ston = npc.get('STON')
        if ston is None or len(ston) < 1:
            rep.warn('npcs', f"{npc.edid!r} has no skin tone (STON)")


def check_race_misc(rep, race):
    if race.formid_of('WNAM') is None:
        rep.fail('race', "Race has no WNAM (skin ARMO)",
                 "Without a body whose ARMA covers this race, skin/tint compositing fails "
                 "and the head renders black.")
    else:
        rep.ok('race', "Race has a skin ARMO (WNAM)")

    if race.formid_of('SRAC') is None and not race.all('SADD'):
        rep.warn('race', "Race has neither SRAC nor its own subgraph data",
                 "It will have no animation graph.")


# --- main -------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', required=True, help="Starfield Data directory")
    ap.add_argument('--plugin', required=True, help="plugin filename or path")
    ap.add_argument('--race', help="race EDID (auto-detected if the plugin has just one)")
    ap.add_argument('-v', '--verbose', action='store_true', help="show passing checks too")
    args = ap.parse_args(argv)

    plugin = args.plugin
    if not os.path.isabs(plugin) and not os.path.exists(plugin):
        plugin = os.path.join(args.data, plugin)
    recs = sf_plugin.load(plugin)
    by_id = {r.formid: r for r in recs}

    races = [r for r in recs if r.sig == 'RACE']
    if args.race:
        race = next((r for r in races if r.edid == args.race), None)
        if race is None:
            print(f"No RACE {args.race!r} in {plugin}")
            return 2
    elif len(races) == 1:
        race = races[0]
    else:
        print(f"{len(races)} RACE records; pick one with --race: "
              f"{[r.edid for r in races]}")
        return 2

    rep = Report()
    print(f"Race    : {race.edid} [{race.formid:08X}]")
    print(f"Plugin  : {plugin}")

    # The mod's own actor-texture tree, e.g. 'actors\fsfcanine' from the FCTP path. Used to
    # tell "this mod forgot to make a file" from "this is vanilla and lives in a BA2".
    fctp_raw = (race.string('FCTP') or '').lower().replace('/', '\\')
    own_root = '\\'.join(fctp_raw.split('\\')[:2]) or None

    nif_reader = make_nif_reader(own_root)
    if nif_reader is None:
        rep.warn('nif', "NiflyDLL could not be loaded -- NIF and mesh checks were SKIPPED",
                 "MaterialID, external .mesh and morph-vs-mesh vertex counts are unchecked.")

    npcs = [r for r in recs if r.sig == 'NPC_' and r.formid_of('RNAM') == race.formid]
    avmd_by_tnam = {r.string('TNAM'): r for r in recs if r.sig == 'AVMD'}

    tnams = [r.string('TNAM') for r in recs if r.sig == 'AVMD']
    dupes = {t for t in tnams if t and tnams.count(t) > 1}
    if dupes:
        rep.fail('skin tones', "duplicate AVMD TNAMs make lookups ambiguous", sorted(dupes))

    per_sex = split_by_sex(race)

    check_race_misc(rep, race)
    own_face = check_head_parts(rep, data=args.data, race=race, by_id=by_id, npcs=npcs,
                                nif_reader=nif_reader, per_sex=per_sex)
    check_npcs(rep, race, npcs)

    fctp = (race.string('FCTP') or '').lower().replace('/', '\\')
    phenotypes = check_skin_tones(rep, args.data, race, avmd_by_tnam, fctp)
    regions = {r for sx in per_sex for r in per_sex[sx]['regions']}
    check_face_textures(rep, args.data, race, phenotypes or {'male_default'}, regions)

    # Morphs are per-sex: a male head is judged against the male MPGM list only.
    for sx, face in sorted(own_face.items()):
        mrph = by_id.get(face.formid_of('MNAM'))
        verts = head_mesh_verts(args.data, face, nif_reader)
        if verts:
            rep.info('morphs', f"{sx.lower()} head mesh has {verts} vertices")
        check_morphs(rep, args.data, mrph, per_sex[sx]['morphs'], verts)

    n_fail = rep.render(args.verbose)
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
