"""A Havok 2019 tagfile as a graph of Python values, and back: the layer the cloth builder writes
through, so it never deals in item numbers, offsets or PTCH.

    read_graph(blob)            the root object, every reference followed
    write_graph(root, donors)   a new tagfile holding the graph; types come from the donor blobs

Values are what havok_tagfile reads -- bool, int, float, a list for an inline tuple (hkVector4),
a dict for a class -- except that references are followed:

    Obj     an object a pointer refers to: its concrete type and value (a dict)
    Arr     an hkArray's elements, with their type
    str     a string (hkStringPtr, char*); None for a null one

A type is named by its signature, (name, template arguments) as TagDoc._signature gives it, so
a graph can be written with types from any blob that defines them. Shared objects stay shared:
an Obj or Arr reached twice is written once.

The writer lays the graph out depth first from the root, which is item 1, each object or array
16-byte aligned, and lists every reference in PTCH under the type it's read at -- so no PTCH
entry falls outside an item, and the type sections are padded as TagDoc pads them (the two traps
that make Starfield drop a cloth).
"""
import struct

from .havok_tagfile import (F_ARRAY, F_BOOL, F_CLASS, F_FLOAT, F_INT, F_OPAQUE, F_POINTER,
                            F_STRING, F_TUPLE, F_VOID, Tagfile, TagfileError)
from .havok_tagwrite import TagDoc

ITEM_OBJECT, ITEM_ARRAY = 0x10, 0x20


class Obj:
    __slots__ = ('type', 'value')

    def __init__(self, type, value):
        self.type, self.value = type, value

    @property
    def type_name(self):
        return self.type[0]

    def __getitem__(self, k):
        return self.value[k]

    def __setitem__(self, k, v):
        self.value[k] = v

    def __repr__(self):
        return f"Obj({self.type[0]})"


class Arr:
    __slots__ = ('type', 'items')

    def __init__(self, type, items):
        self.type, self.items = type, items

    @property
    def type_name(self):
        return self.type[0]

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, k):
        return self.items[k]

    def __repr__(self):
        return f"Arr({self.type[0]}[{len(self.items)}])"


def _kind(tf, t):
    return tf.format_of(t) & 0x1F


def _inline(tf, t):
    fmt = tf.format_of(t)
    return fmt & 0x1F == F_TUPLE or (fmt & 0x1F == F_ARRAY and fmt & 0x20)


def read_graph(blob):
    """The root object of `blob` (item 1), with every reference followed."""
    tf, doc = Tagfile(blob), TagDoc(blob)
    memo = {}

    def item(idx):
        if idx == 0:
            return None
        if idx in memo:
            return memo[idx]
        t, flags, off, count = tf.items[idx]
        sig = doc._signature(t.index)
        node = Obj(sig, None) if flags == ITEM_OBJECT else Arr(sig, None)
        memo[idx] = node
        size, base = tf.size_of(t), tf.data_start + off
        vals = [value(t, base + k * size) for k in range(count)]
        if flags == ITEM_OBJECT:
            if count != 1:
                raise TagfileError(f"object item {idx} holds {count} elements")
            node.value = vals[0]
        else:
            node.items = vals
        return node

    def value(t, o):
        kind = _kind(tf, t)
        if kind == F_STRING:
            return tf.item_string(struct.unpack_from('<I', tf.b, o)[0])
        if kind == F_POINTER or (kind == F_ARRAY and not _inline(tf, t)):
            return item(struct.unpack_from('<I', tf.b, o)[0])
        if _inline(tf, t):
            et = tf.subtype_of(t)
            es = tf.size_of(et)
            return [value(et, o + k * es) for k in range(tf.format_of(t) >> 8)]
        if kind in (F_CLASS, F_OPAQUE, F_VOID):
            members = tf.all_members(t)
            if not members:
                return bytes(tf.b[o:o + (tf.size_of(t) or 0)])
            return {name: value(mt, o + off) for name, _f, off, mt in members}
        return tf.read(t, o)

    return item(1)


def walk(root):
    """Every Obj and Arr reachable from `root`, each once, depth first."""
    seen, out = set(), []

    def visit(v):
        if isinstance(v, (Obj, Arr)):
            if id(v) in seen:
                return
            seen.add(id(v))
            out.append(v)
            visit(v.value if isinstance(v, Obj) else v.items)
        elif isinstance(v, dict):
            for x in v.values():
                visit(x)
        elif isinstance(v, list):
            for x in v:
                visit(x)
    visit(root)
    return out


class _Writer:
    def __init__(self, donors):
        self.donors = [TagDoc(b) for b in donors]
        doc = TagDoc(donors[0])
        doc.data = bytearray()
        doc.items = [[0, 0, 0]]
        doc.patches = []
        doc.tna, doc.bodies, doc.hashes = [None], [], []
        doc.tnames, doc.fnames = [], []
        doc.tptr = bytes(8)
        doc._raw = {tag: b'' for tag in doc._raw}
        self.doc = doc
        self._types = {}
        self._donor_index = {}

    def type_index(self, sig):
        """This blob's index for the type with signature `sig`, copied from the first donor
        that has it."""
        if sig in self._types:
            return self._types[sig]
        for k, d in enumerate(self.donors):
            index = self._donor_index.setdefault(k, {})
            if not index:
                for t in range(1, len(d.tna)):
                    index.setdefault(d._signature(t), t)
            if sig in index:
                self._types[sig] = self.doc.copy_type(d, index[sig])
                return self._types[sig]
        raise TagfileError(f"no donor defines the type {sig}")

    def write(self, root):
        for node in walk(root):
            self.type_index(node.type)
        self.char = self.type_index(('char', ()))
        self.tf = Tagfile(self.doc.to_bytes())         # the types, to lay values out by
        self.memo = {}
        self.alloc(root)
        return self.doc.to_bytes()

    def alloc(self, node):
        if node is None:
            return 0
        if id(node) in self.memo:
            return self.memo[id(node)]
        t = self.tf.types[self.type_index(node.type)]
        vals = [node.value] if isinstance(node, Obj) else node.items
        # An empty array's element type may have no definition at all (vanilla's
        # compressible-link singles): it needs no size.
        size = self.tf.size_of(t) if vals else 0
        idx, off = self.doc.add_item(t.index, bytes(size * len(vals)), len(vals),
                                     kind=ITEM_OBJECT if isinstance(node, Obj) else ITEM_ARRAY)
        self.memo[id(node)] = idx
        for k, v in enumerate(vals):
            self.put(t, v, off + k * size)
        return idx

    def string(self, s):
        raw = s.encode('utf-8') + b'\0'
        idx, _off = self.doc.add_item(self.char, raw, len(raw), kind=ITEM_ARRAY)
        return idx

    def ref(self, t, o, idx):
        struct.pack_into('<I', self.doc.data, o, idx)
        if idx:
            self.doc.add_patch(t.index, o)

    def put(self, t, v, o):
        tf, kind = self.tf, _kind(self.tf, t)
        if kind == F_STRING:
            self.ref(t, o, 0 if v is None else self.string(v))
        elif kind == F_POINTER or (kind == F_ARRAY and not _inline(tf, t)):
            if v is not None and not isinstance(v, (Obj, Arr)):
                raise TagfileError(f"{t.name}: a reference needs an Obj or Arr, not {v!r}")
            self.ref(t, o, self.alloc(v))
        elif _inline(tf, t):
            et = tf.subtype_of(t)
            es = tf.size_of(et)
            n = tf.format_of(t) >> 8
            if len(v) != n:
                raise TagfileError(f"{t.name} holds {n} values, not {len(v)}")
            for k, x in enumerate(v):
                self.put(et, x, o + k * es)
        elif kind in (F_CLASS, F_OPAQUE, F_VOID):
            members = tf.all_members(t)
            if not members:
                self.doc.data[o:o + len(v)] = v
                return
            for name, _f, off, mt in members:
                if name not in v:
                    raise TagfileError(f"{t.name}: no value for {name}")
                self.put(mt, v[name], o + off)
        elif kind in (F_BOOL, F_INT, F_FLOAT):
            tf._write(o, t, v, self.doc.data)
        else:
            raise TagfileError(f"{t.name}: can't write a value of kind {kind}")


def write_graph(root, donors):
    """A tagfile holding the graph under `root`. `donors` are blobs whose type definitions the
    graph's types are copied from, the first that has each; only the types the graph uses (and
    the types they refer to) go in."""
    return _Writer(donors).write(root)


def same(a, b, tol=0.0, path='root', _seen=None):
    """Where graphs `a` and `b` first differ, as a path string, or None if they hold the same
    values. Floats may differ by `tol`, relative to their size."""
    _seen = set() if _seen is None else _seen
    if isinstance(a, (Obj, Arr)) or isinstance(b, (Obj, Arr)):
        if type(a) is not type(b) or a.type != b.type:
            return f"{path}: {a!r} vs {b!r}"
        if (id(a), id(b)) in _seen:
            return None
        _seen.add((id(a), id(b)))
        if isinstance(a, Obj):
            return same(a.value, b.value, tol, f"{path}<{a.type[0]}>", _seen)
        return same(a.items, b.items, tol, f"{path}<{a.type[0]}>", _seen)
    if isinstance(a, dict):
        if not isinstance(b, dict) or a.keys() != b.keys():
            return f"{path}: fields differ"
        for k in a:
            d = same(a[k], b[k], tol, f"{path}.{k}", _seen)
            if d:
                return d
        return None
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            return f"{path}: {len(a) if isinstance(a, list) else a!r} vs " \
                   f"{len(b) if isinstance(b, list) else b!r} elements"
        for k, (x, y) in enumerate(zip(a, b)):
            d = same(x, y, tol, f"{path}[{k}]", _seen)
            if d:
                return d
        return None
    if isinstance(a, float) and isinstance(b, float):
        if a != b and not (a != a and b != b) and abs(a - b) > tol * max(1.0, abs(a), abs(b)):
            return f"{path}: {a} vs {b}"
        return None
    return None if a == b else f"{path}: {a!r} vs {b!r}"
