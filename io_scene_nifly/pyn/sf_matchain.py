"""Resolve a Starfield `.mat`'s inheritance chain into one effective material.

A `.mat` is normally a **derivation**: it names one or more parents with `Import`, and its
objects override selected components of the parent's objects. Measured over the 48,505
authored vanilla materials, 99.5% carry `Import` and only 0.3% carry a
`ShaderModelComponent` -- the shader model belongs to the template they derive from. So
reading a material without walking its chain reads almost none of it.

Two independent relations, easy to confuse, and both needed here:

* the **`Parent` field** on an object is INHERITANCE -- "I override that object", naming a
  `res:` id in a parent material (or a template path).
* an object's **`OuterEdge`** is CONTAINMENT -- "I belong to that object", naming an id in
  this document, or `"<this>"` for the material's root.

The document itself is a flat list of database entities; containment is what reassembles it
into a tree. See `docs/plan_sf_material_inheritance.md`.

Nothing here touches Blender.
"""

import json
import logging
import os

log = logging.getLogger("pynifly")

CTNAME = 'BSComponentDB::CTName'
SHADER_MODEL = 'BSMaterial::ShaderModelComponent'
OUTER_EDGE = 'BSComponentDB2::OuterEdge'

# What a resolved object or field says when the material being read set it itself. A path
# would do, but the material may not have one yet (it can be built in Blender and named at
# export), and "mine" is the distinction every consumer of provenance actually asks about.
LOCAL = '<local>'

# Components whose Data.ID names another object. Reaching the effective material means
# following these from the root, so an object nothing points at simply drops out.
REFERENCE_TYPES = (
    'BSMaterial::LayerID',
    'BSMaterial::BlenderID',
    'BSMaterial::MaterialID',
    'BSMaterial::TextureSetID',
    'BSMaterial::UVStreamID',
    # An LOD material is USUALLY a separate material in the game's database, named by an id
    # that resolves to nothing here -- and `walk` then simply skips it. But it can also be a
    # whole sub-material declared in this same document (8 occurrences in an 800-material
    # sample), and leaving it out of this list drops that subtree on the floor.
    'BSMaterial::LODMaterialID',
)

# The root's reference list, which behaves differently from every other component: see
# `_authoritative_refs`.
LAYER_ID = 'BSMaterial::LayerID'
BLENDER_ID = 'BSMaterial::BlenderID'


def _deep_merge(base, over):
    """`over`'s fields laid on `base`'s, recursing into nested dicts.

    An override sets SOME fields of a component and leaves the rest showing through:
    authored `left_eye.mat` gives `EyeSettingsComponent` its six iris numbers while
    `Enabled` comes from the `Eye1Layer` template underneath. Replacing the payload
    wholesale loses exactly the fields the author chose not to restate -- and the result
    still looks like a complete component, which is the dangerous part.
    """
    if not isinstance(base, dict) or not isinstance(over, dict):
        return over
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if k in out else v
    return out


class Value:
    """One resolved component: its merged payload, and where each field came from.

    `data` is the whole component after merging; `origins` maps each top-level field to the
    material that last set it; `origin` names the most-derived material that contributed
    anything, which is what answers "did this file touch this component at all".
    """

    __slots__ = ('type', 'index', 'data', 'origin', 'origins', 'version',
                 'version_origin')

    def __init__(self, ctype, index, data, origin, origins=None, version=None,
                 version_origin=None):
        self.type = ctype
        self.index = index
        self.data = data
        self.origin = origin
        self.origins = origins if origins is not None else {k: origin for k in (data or {})}
        # A component's schema version, carried because it is NOT derivable: vanilla ships
        # `MRTextureFile` at both v1 and v2 and `TextureSetID` at v1 and v3, while CTName,
        # LayerID, ParamBool and most others never carry one at all. 3,054 of 11,934 sampled
        # components have it. Dropping it rewrites the component as a different version of
        # itself.
        #
        # It belongs to the DECLARATION, not to the material: the compiled database --
        # the engine's own composed form -- carries no `Version` on any component at
        # all. So it is tracked back to whoever wrote it, and a material that restates
        # a component without one does not inherit its parent's.
        self.version = version
        self.version_origin = (version_origin if version_origin is not None
                               else (origin if version is not None else None))

    def merged_with(self, other):
        """A new Value: `other` (more derived) laid over this one."""
        origins = dict(self.origins)
        origins.update(other.origins)
        newer = other.version is not None
        return Value(other.type, other.index, _deep_merge(self.data, other.data),
                     other.origin, origins,
                     version=other.version if newer else self.version,
                     version_origin=other.origin if newer else self.version_origin)

    def origin_of(self, field):
        """Which material set one field, or None if nothing did."""
        return self.origins.get(field)

    def __repr__(self):
        return f"<Value {self.type}[{self.index}] from {os.path.basename(self.origin)}>"


class Obj:
    """An object of the effective material: its own identity, plus every component that
    reaches it -- its own, then whatever its `Parent` chain supplies underneath."""

    __slots__ = ('id', 'name', 'parent_ref', 'container', 'origin', '_comps')

    def __init__(self, oid, name, parent_ref, container, origin, comps):
        self.id = oid
        self.name = name
        self.parent_ref = parent_ref
        self.container = container
        self.origin = origin
        self._comps = comps            # {(type, index): Value}

    def component(self, ctype, index=0):
        """The winning Value for a component, or None if nothing in the chain sets it."""
        return self._comps.get((ctype, index))

    def components(self, ctype=None):
        """Every resolved component, optionally of one type, in a stable order."""
        vals = [v for v in self._comps.values() if ctype is None or v.type == ctype]
        return sorted(vals, key=lambda v: (v.type, v.index))

    def references(self):
        """The ids this object points at, as {(type, index): id}."""
        return {(v.type, v.index): v.data['ID']
                for v in self._comps.values()
                if v.type in REFERENCE_TYPES and isinstance(v.data, dict) and v.data.get('ID')}

    def __repr__(self):
        return f"<Obj {self.name or self.id} {len(self._comps)} components>"


class Chain:
    """A material and everything it inherits from, already merged.

    `paths` runs local-first. `unresolved` lists references we could not find -- a chain
    normally ends in `Materials\\Layered\\Root\\*.mat`, which exists in no loose tree, so an
    unresolved tail is expected rather than an error. It is reported instead of hidden
    because "nothing to inherit" and "could not look it up" produce very different
    materials and only one of them is right.
    """

    def __init__(self, paths, unresolved, root, objects, imports=()):
        self.paths = paths
        self.unresolved = unresolved
        self.root = root
        self.objects = objects          # {id: Obj}
        # What the material itself DECLARES it derives from, verbatim and in order -- not
        # the same list as `paths`, which is where resolution actually went. Export has to
        # write this back: a declared parent that happens to contribute no surviving value
        # would vanish from a list derived from origins, and with 7,063 vanilla materials
        # naming 2-7 parents the order matters as well.
        self.imports = list(imports)

    @property
    def shader_model(self):
        v = self.root.component(SHADER_MODEL)
        return v.data.get('FileName') if v else None

    def object_named(self, name):
        for o in self.objects.values():
            if o.name == name:
                return o
        return None

    def to_doc(self):
        """The effective material as a `.mat`-shaped dict, for the existing parser.

        Only objects reachable from the root are emitted, so an inherited layer the derived
        material stopped referencing is genuinely gone. Components come out merged, so a
        consumer sees the material the engine would build rather than the fragment on disk.
        """
        objects = []
        for o in self.walk():
            entry = {'Components': [_as_component(v) for v in o.components()]}
            if o.id:
                entry['ID'] = o.id
            if o.parent_ref:
                entry['Parent'] = o.parent_ref
            objects.append(entry)
        return {'Version': 1, 'Objects': objects}

    def origin_map(self):
        """Which material set each object, and each field that disagrees with it.

        `{object id: {'origin': label, 'fields': {'<Type>[i].<Field>': label}}}`, with the
        root keyed `''` -- the root is `Objects[0]` whether or not it carries an id, and an
        empty id is what the parsed node meta carries for it.

        `fields` lists only the fields whose origin differs from the object's own, so an
        object inherited whole collapses to one string and only genuine overrides cost
        anything. The node tree shows the EFFECTIVE material, so without this there is no
        way to tell an inherited value from an owned one -- and writing an inherited value
        back as if it were local is how a derivation becomes the flat file that renders
        nowhere.

        It is provenance for display and for the export decision to consult; correctness
        never depends on WHICH ancestor a value came from, only on whether it is this
        material's.
        """
        out = {}
        for key, obj in [('', self.root)] + sorted(self.objects.items()):
            own = self.label(obj.origin)
            fields = {}
            for v in obj.components():
                for field, src in v.origins.items():
                    label = self.label(src)
                    if label != own:
                        fields[f"{v.type}[{v.index}].{field}"] = label
            out[key] = {'origin': own, 'fields': fields} if fields else {'origin': own}
        return out

    def component_origin(self, obj, ctype, index=0):
        """The same provenance entry for ONE component, or None if nothing sets it.

        Here `origin` is the most-derived material that contributed any field, which is the
        answer to "did this material touch this component at all" -- the object-level
        origin cannot say, because an object's record and its components come from
        different places as soon as anything is inherited.
        """
        v = obj.component(ctype, index)
        if v is None:
            return None
        own = self.label(v.origin)
        fields = {f: self.label(src) for f, src in v.origins.items()
                  if self.label(src) != own}
        return {'origin': own, 'fields': fields} if fields else {'origin': own}

    def label(self, path):
        """One material of this chain, named for display: `<local>` for the material being
        resolved, `Materials\\...` for everything it inherits from."""
        if self.paths and os.path.normcase(path) == os.path.normcase(self.paths[0]):
            return LOCAL
        return material_label(path)

    def walk(self):
        """Every object reachable from the root, root first, each visited once.

        Reachability is what makes a dropped layer actually disappear: a derived material
        removes one by not referencing it, and the orphan is simply never yielded.
        """
        seen, out, queue = set(), [self.root], [self.root]
        while queue:
            cur = queue.pop(0)
            for oid in cur.references().values():
                if oid in seen:
                    continue
                target = self.objects.get(oid)
                if target is None:
                    continue
                seen.add(oid)
                out.append(target)
                queue.append(target)
        return out


def material_label(path):
    """A material named the way the format names it -- `Materials\\...` -- from whatever we
    have.

    A chain mixes two kinds of origin: real files, found on disk at some arbitrary asset
    root, and documents reconstructed from `materialsbeta.cdb`, whose "path" is the
    reference that named them. Provenance shown to a user has to read the same either way,
    and must not leak whose copy of the game assets this was resolved against.
    """
    p = (path or '').replace('/', os.sep)
    parts = p.split(os.sep)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() == 'materials':
            return os.sep.join(['Materials'] + parts[i + 1:])
    return p


def _as_component(value):
    """One resolved Value back in `.mat` component shape."""
    c = {'Type': value.type, 'Index': value.index, 'Data': value.data}
    # Only when the material that last touched this component is also the one that stated the
    # version. Otherwise the version is the PARENT's way of writing its own declaration, and
    # restating it here puts a version on a component whose author left it unversioned.
    if value.version is not None and value.version_origin == value.origin:
        c['Version'] = value.version
    return c


def _normalise(ref):
    """A material reference -> a path relative to the materials tree, lowercased.

    References appear as `materials/layered/...`, `Data\\MATERIALS\\Layered\\...` and bare
    relative paths, with either slash, in any case.
    """
    r = (ref or '').replace('/', os.sep).replace('\\', os.sep).strip()
    low = r.lower()
    if low.startswith('data' + os.sep):
        r = r[5:]
        low = r.lower()
    if low.startswith('materials' + os.sep):
        r = r[len('materials') + 1:]
    return r


def _find(ref, search):
    """The file a reference names, or None. `search` holds materials-tree roots."""
    rel = _normalise(ref)
    if not rel:
        return None
    for root in search:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            return p
    return None


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _from_cdb(ref, cdb):
    """A material reconstructed from the compiled database, or None.

    The database keys materials by the CRC of their path, so the reference is offered in the
    `Materials\\...` form it uses. What comes back is already composed against its own
    parents -- terminal by construction, which is exactly what a chain tail needs.
    """
    if cdb is None:
        return None
    rel = _normalise(ref)
    if not rel:
        return None
    for candidate in (os.path.join('Materials', rel), rel):
        try:
            doc = cdb.get_material(candidate)
        except Exception as e:
            log.warning(f"Material database lookup failed for {candidate}: {e}")
            return None
        if doc and doc.get('Objects'):
            return doc
    return None


def _container_of(obj):
    for e in obj.get('Edges') or ():
        if e.get('Type') == OUTER_EDGE:
            return e.get('To')
    return None


def _name_of(obj):
    for c in obj.get('Components') or ():
        if c.get('Type') == CTNAME:
            return (c.get('Data') or {}).get('Name')
    return None


# Parsing materialsbeta.cdb costs ~105 MB and a few seconds, and a chain may ask for
# several templates, so a parsed database is kept per file.
_CDB_CACHE = {}


def _open_cdb(cdb):
    """A CdbFile from a path (cached) or an already-parsed one. None if unavailable."""
    if cdb is None or not isinstance(cdb, str):
        return cdb
    key = os.path.normcase(os.path.abspath(cdb))
    if key not in _CDB_CACHE:
        try:
            from pyn import sf_cdb
            _CDB_CACHE[key] = sf_cdb.load_cdb(cdb)
        except Exception as e:
            log.warning(f"Could not open material database {cdb}: {e}")
            _CDB_CACHE[key] = None
    return _CDB_CACHE[key]


def resolve_material(path, search=None, cdb=None, _seen=None, doc=None):
    """Resolve `path` and everything it imports into one effective material.

    `search` is the list of materials-tree roots to resolve references against; it defaults
    to the tree `path` itself sits in, found by walking up to the `materials` directory.

    `cdb` is an optional `materialsbeta.cdb` -- a path or an already-parsed `CdbFile` --
    consulted for references no loose file satisfies. Chains normally end in
    `Materials\\Layered\\Root\\*.mat`, which ships only inside the database, so without it
    the tail of every chain is missing and the result is quietly incomplete.
    """
    path = os.path.abspath(path)
    if search is None:
        search = [tree_root(path)]
    _seen = _seen or set()

    docs = []          # (path, document), local first
    unresolved = []
    # `doc` resolves a document that is not on disk -- one just built for export, checked
    # against its own parents before it is written anywhere. `path` then says where it will
    # live, which is what its relative references resolve against.
    _collect(path, search, docs, unresolved, _seen, _open_cdb(cdb), doc=doc)

    # Objects by id across the whole chain. A more-derived document wins a duplicate id,
    # so walk root-most first and let the local file overwrite.
    raw = {}
    for p, doc in reversed(docs):
        for o in doc.get('Objects') or ():
            if o.get('ID'):
                raw[o['ID']] = (p, o)

    merged = {}
    objects = {}
    for oid, (p, o) in raw.items():
        objects[oid] = Obj(oid, _name_of(o), o.get('Parent'), _container_of(o), p,
                           _merge_components(oid, raw, merged, unresolved))

    # The root is Objects[0] -- ALWAYS, whether or not it carries an id. It is not "the
    # object with no id" (PyNifly's own writer gives the root one) and not "the object with
    # no Parent" (every object in an authored material has one). Guessing either way skips
    # the root entirely on some real material and yields an empty result that still looks
    # like a material. Each document's root lays over the ones it inherits from.
    root_comps = {}
    root_meta = None
    for p, doc in reversed(docs):
        objs = doc.get('Objects') or ()
        if not objs:
            continue
        r = objs[0]
        root_meta = (p, r)
        rid = r.get('ID')
        if rid and rid in raw:
            # It has an id, so its own Parent chain is already resolvable as an object.
            for key, val in _merge_components(rid, raw, merged, unresolved).items():
                root_comps[key] = (root_comps[key].merged_with(val)
                                   if key in root_comps else val)
        else:
            for c in r.get('Components') or ():
                _lay_on(root_comps, c, p)
    _authoritative_refs(root_comps, [p for p, _ in docs])

    rp, rr = root_meta if root_meta else (path, {})
    root = Obj(None, _name_of(rr), rr.get('Parent'), _container_of(rr), rp, root_comps)

    return Chain([p for p, _ in docs], unresolved, root, objects,
                 imports=(docs[0][1].get('Import') or ()) if docs else ())


def derive(doc, parents, imports=None, keep=()):
    """`doc`, a COMPLETE material, rewritten as a derivation of `parents`.

    The inverse of resolution. Resolution lays a child's fields over its parents' and hands
    back everything that reaches the material; this takes everything back off again and
    leaves only what this file has to say for itself. What survives is the delta -- and that
    is the form the game actually reads: 99.5% of authored vanilla materials are written
    this way, and the flat alternative is what did not render.

    Three things are deliberately NOT diffed away:

    * **The root's `LayerID` / `BlenderID` list**, which is authoritative rather than
      additive. Inherit it and a layer the author deleted comes back.
    * **Ids.** An object keeps the id it came in with, verbatim. Minting a new namespace is
      what made the eyes invisible in game (Phase 0 of the plan), and re-namespacing a
      derived material orphans every reference its parent makes to it.
    * **Containment.** `Edges` are emitted for every object this file declares, from the
      reference structure of the complete document -- which is the only place the answer
      exists, since an object's container is frequently not something it references.

    An object left with nothing to say still gets a record: id, `Parent`, edge and no
    components. That bare placeholder is the single commonest object in the game's
    materials, and it is how a derived material claims an inherited object as its own.

    `keep` names object ids to write whole, diffing nothing. It is the answer to the one
    case a diff cannot see: "I set this to the same value the parent happens to have, and I
    mean it to stay that way even if the parent changes". Nothing else can express that,
    because by construction it looks identical to not having touched it. The root is named
    by the empty id.
    """
    objects = doc.get('Objects') or ()
    if not objects:
        return dict(doc)

    container = _containment(objects)
    owned_by_parent = parents.objects if parents is not None else {}
    claimed = set(keep or ())
    out = []
    for i, o in enumerate(objects):
        # A claimed object is diffed against nothing, so every value on it is written.
        inherited = {} if (o.get('ID') or '') in claimed else _inherited_for(
            o, parents, is_root=(i == 0))
        comps = []
        for c in o.get('Components') or ():
            # The root's layer/blender list is the one thing never diffed away -- it is
            # authoritative, so a partial one deletes layers. Other references, LOD
            # materials included, are ordinary components.
            delta = _component_delta(
                c, inherited, keep_whole=(i == 0 and c.get('Type') in (LAYER_ID, BLENDER_ID)))
            if delta is not None:
                comps.append(delta)
        # An object that IS one of the parent's, and that we change nothing about, needs no
        # record here: the reference to it already names it. A material may use a parent's
        # object directly rather than declaring an override -- measured on 6 of ~250 derived
        # materials -- and writing a local placeholder for it says something the authored
        # file does not.
        if i > 0 and not comps and o.get('ID') in owned_by_parent:
            continue
        # An object with nothing left to say carries no `Components` key at all, which is
        # how vanilla writes it -- 498 of 3,938 sampled objects are bare like this.
        entry = {'Components': comps} if comps else {}
        if o.get('ID'):
            entry['ID'] = o['ID']
        if o.get('Parent'):
            entry['Parent'] = o['Parent']
        # The root is the material; nothing contains it. An edge indexes with `EdgeIndex`,
        # not `Index` -- measured 3,438 of 3,438.
        if i > 0:
            entry['Edges'] = [{'Type': OUTER_EDGE, 'EdgeIndex': 0,
                               'To': container.get(o.get('ID'), '<this>')}]
        out.append(entry)

    derived = {'Version': doc.get('Version', 1)}
    if imports:
        derived['Import'] = list(imports)
    if doc.get('Filename'):
        derived['Filename'] = doc['Filename']
    derived['Objects'] = out
    return derived


def _containment(objects):
    """{object id: the id of the object that references it, or `<this>` for the root's own}.

    Containment is a different relation from inheritance and is not recorded per object: it
    only exists in who points at whom. The root's children say `<this>`; everything else
    names its referrer.
    """
    out = {}
    for i, o in enumerate(objects):
        for c in o.get('Components') or ():
            if c.get('Type') not in REFERENCE_TYPES:
                continue
            target = (c.get('Data') or {}).get('ID')
            if target and target not in out:
                out[target] = '<this>' if i == 0 else o.get('ID')
    return out


def _inherited_for(obj, parents, is_root=False):
    """The merged components an object inherits: `{(type, index): Value}`, possibly empty.

    An object inherits through its `Parent`, which names an object in a parent material. An
    object that IS one of the parent's -- a material may reference a parent's object directly
    rather than declaring a local override for it -- inherits that object's own components.
    """
    if parents is None:
        return {}
    if is_root:
        return parents.root._comps
    # Own id first: if this id is one of the parent's objects then we ARE that object, and
    # its merged components are what we inherit. Only a local override -- whose id the parent
    # has never heard of -- inherits through its `Parent`. Asking Parent first diffs such an
    # object against its GRANDparent and invents a delta out of the difference.
    for key in (obj.get('ID'), obj.get('Parent')):
        target = parents.objects.get(key) if key else None
        if target is not None:
            return target._comps
    return {}


def _component_delta(component, inherited, keep_whole=False):
    """One component reduced to the fields the parent does not already supply, or None.

    Field by field, because that is how the engine merges: authored `left_eye.mat` restates
    six of `EyeSettingsComponent`'s seven fields and lets `Enabled` show through. Writing the
    component whole would be harmless; writing it not at all would lose the six. Only the
    difference is correct, and only field-wise diffing finds it.
    """
    ctype, index = component.get('Type'), component.get('Index', 0)
    data = component.get('Data')
    if keep_whole:
        return dict(component)
    base = inherited.get((ctype, index))
    if base is None:
        return dict(component)
    delta = _data_delta(base.data, data)
    if delta is None:
        return None
    out = {'Type': ctype, 'Index': index, 'Data': delta}
    if component.get('Version') is not None:
        out['Version'] = component['Version']
    return out


def _data_delta(base, over):
    """`over` minus whatever `base` already says, or None if it says nothing new.

    Recurses through typed wrappers (`{'Type': ..., 'Data': {...}}`), which several
    components use to nest their real fields, so a wrapper survives when any leaf inside it
    differs and vanishes when none does.
    """
    if not isinstance(base, dict) or not isinstance(over, dict):
        return None if base == over else over
    out = {}
    for k, v in over.items():
        if k not in base:
            out[k] = v
            continue
        sub = _data_delta(base[k], v)
        if sub is not None:
            out[k] = sub
    if not out:
        return None
    # A typed wrapper is meaningless without its identity, so carry `Type` and `Version`
    # whenever anything inside survived -- they name the payload rather than being values of
    # their own. Vanilla writes `"Version": 1` on a nested `BSMaterial::Color` even in a
    # derived file that restates only part of the colour.
    for tag in ('Type', 'Version'):
        if tag in over and tag not in out:
            out[tag] = over[tag]
    return out


def _authoritative_refs(root_comps, paths):
    """Cut the root's layer/blender list down to the one the most-derived document DECLARED.

    Every other component accumulates down the chain. This one does not: a material that
    states a `LayerID` list is stating its whole stack, and the ancestors' entries are gone
    rather than merged under it. That is how a derived material DELETES a layer -- it simply
    declares a shorter list -- and merging them back is silent, because the result is a
    perfectly well-formed material with a layer the author removed.

    Measured against the engine's own composed form (`materialsbeta.cdb`) over 400 materials:
    398 agreed either way, and the 2 that did not are exactly this case -- each declares
    `LayerID[0]` alone over a chain carrying three layers and two blenders, and the engine
    composes one layer and no blenders.

    Layers and blenders go together: the list is ONE declaration, and the most-derived
    document that states any of it states all of it. A material declaring `LayerID[0]` alone
    over a chain with two blenders composes to no blenders, while one declaring
    `LayerID[0]` + `BlenderID[0]` keeps its blender -- 47 vanilla materials are the second
    case, and treating the two types independently gets every one of them wrong.
    """
    rank = {os.path.normcase(p): i for i, p in enumerate(paths)}
    vals = [(k, v) for k, v in root_comps.items() if k[0] in (LAYER_ID, BLENDER_ID)]
    if not vals:
        return
    best = min(rank.get(os.path.normcase(v.origin), len(rank)) for _, v in vals)
    for k, v in vals:
        if rank.get(os.path.normcase(v.origin), len(rank)) != best:
            del root_comps[k]


def resolve_level(ref, search=None, cdb=None):
    """Resolve ONE material of an already-walked chain, by whatever `Chain.paths` called it.

    Those entries are real files for anything found on disk and the naming REFERENCE for
    anything reconstructed from the database -- the `Materials\\Layered\\Root` templates
    exist in no loose tree, so their "path" was never openable. Handing such an entry back to
    `resolve_material` reads as a missing file and warns about it. Returns None if the
    reference resolves nowhere.
    """
    if os.path.exists(ref):
        return resolve_material(ref, search=search, cdb=cdb)
    doc = _from_cdb(ref, _open_cdb(cdb))
    if doc is None:
        return None
    return resolve_material(ref, search=search, cdb=cdb, doc=doc)


def resolve_parents(imports, path, search=None, cdb=None):
    """Everything `imports` names, merged, as one chain -- the state a material inherits.

    Resolved as a document whose only content is the import list, so several parents merge by
    exactly the rules a real material's would, in the same order. Export needs this to work
    out what NOT to write, and a material with 2-7 parents (7,063 of them ship that way) has
    no single parent to point at.
    """
    return resolve_material(path, search=search, cdb=cdb,
                            doc={'Version': 1, 'Import': list(imports), 'Objects': []})


def tree_root(path):
    """The `materials` directory above `path`, or its own directory if there isn't one."""
    cur = os.path.dirname(path)
    while True:
        if os.path.basename(cur).lower() == 'materials':
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(path)
        cur = parent


def _collect(path, search, docs, unresolved, seen, cdb=None, doc=None):
    """Append (path, doc) for `path` and its imports, depth-first, local first.

    `doc` is supplied when the document did not come off disk -- a material reconstructed
    from the compiled database, whose `path` is then the reference that named it rather
    than a real file.
    """
    key = os.path.normcase(os.path.abspath(path)) if doc is None else 'cdb:' + path.lower()
    if key in seen:
        return
    seen.add(key)
    if doc is None:
        try:
            doc = _load(path)
        except Exception as e:
            log.warning(f"Could not read material {path}: {e}")
            unresolved.append(path)
            return
    docs.append((path, doc))

    # Both `Import` and the ROOT object's `Parent` name a material to inherit from, and a
    # document may use either. `left_eye.mat` gives the same target in both; the shader
    # model templates carry no `Import` at all and reach the Root templates only through
    # the root's `Parent`. Following just one of them silently truncates the chain.
    refs = list(doc.get('Import') or ())
    objs = doc.get('Objects') or ()
    if objs and not objs[0].get('ID'):
        rp = objs[0].get('Parent')
        if rp and not rp.startswith('res:') and rp not in refs:
            refs.append(rp)

    for ref in refs:
        found = _find(ref, search)
        if found is not None:
            _collect(found, search, docs, unresolved, seen, cdb)
            continue
        from_db = _from_cdb(ref, cdb)
        if from_db is not None:
            _collect(ref, search, docs, unresolved, seen, cdb, doc=from_db)
            continue
        if ref not in unresolved:
            unresolved.append(ref)


def _merge_components(oid, raw, memo, unresolved):
    """Every component reaching object `oid`: its own over its Parent chain's.

    Keyed by (type, index), so a child component with the same slot replaces the parent's
    and anything the child leaves alone shows through.
    """
    if oid in memo:
        return memo[oid]
    memo[oid] = {}                        # cycle guard; a self-referential Parent is data
    p, o = raw[oid]

    parent_ref = o.get('Parent')
    comps = {}
    if parent_ref and parent_ref in raw:
        comps.update(_merge_components(parent_ref, raw, memo, unresolved))
    elif parent_ref and parent_ref not in unresolved:
        # A parent we never loaded: either a `res:` object or a Root template path. Both
        # live only in the compiled database, so whatever they contribute is missing from
        # this result -- say so rather than pass off a partial merge as complete.
        unresolved.append(parent_ref)

    for c in o.get('Components') or ():
        _lay_on(comps, c, p)

    memo[oid] = comps
    return comps


def _lay_on(comps, component, origin):
    """Lay one raw component onto the accumulated {(type, index): Value}, field-wise."""
    key = (component.get('Type'), component.get('Index', 0))
    val = Value(key[0], key[1], component.get('Data') or {}, origin,
                version=component.get('Version'))
    comps[key] = comps[key].merged_with(val) if key in comps else val
