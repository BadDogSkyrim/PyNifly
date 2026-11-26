"""An hk_2014 binary packfile (FO4 cloth) as a graph of Python values, and back.

    read_graph(blob)     the root object (hkRootLevelContainer), every pointer followed
    write_graph(root)    a packfile holding the graph

The class layouts are in fo4_cloth_types. Values:

    Obj     an object: its class name and a dict of field values
    dict    an inline struct
    list    an hkArray's elements, or a fixed inline array
    tuple   a vec4 (4 floats) or mat4 (16 floats, column-major)
    str     a string (hkStringPtr); None for a null one

The writer lays the file out as Havok's does, which reproduces every vanilla blob byte for byte:
objects depth first from the root, each followed by its own data -- strings and arrays in field
order, each 16-byte aligned, an array's elements' own data straight after it -- then the objects
it points to, each written once.
"""
import struct

from .fo4_cloth_types import CLASSES, SIGNATURES, STRUCTS

_SCALARS = {'u8': 'B', 'i8': 'b', 'u16': 'H', 'i16': 'h', 'u32': 'I', 'i32': 'i', 'f32': 'f'}
_HEADER = bytes.fromhex(
    '57e0e05710c0c010000000000b00000008010001030000000200000000000000'
    '000000004b000000686b5f323031342e312e302d723100ff0000000015001000'
    '14000000000000000000000000000000')
_SECTIONS_AT = 0x50
_ARRAY_FLAGS = 0x80000000           # capacity word: DONT_DEALLOCATE | capacity


class Hk2014Error(Exception):
    """A packfile the graph layer can't read."""


class Obj:
    __slots__ = ('type_name', 'value')

    def __init__(self, type_name, value=None):
        self.type_name, self.value = type_name, value if value is not None else {}

    def __getitem__(self, k):
        return self.value[k]

    def __setitem__(self, k, v):
        self.value[k] = v

    def get(self, k, default=None):
        return self.value.get(k, default)

    def __repr__(self):
        return f"Obj({self.type_name})"


def _size(t):
    if isinstance(t, str):
        if t in _SCALARS:
            return struct.calcsize(_SCALARS[t])
        return {'vec4': 16, 'mat4': 64, 'str': 8, 'ptr': 8}[t]
    if t[0] == 'arr':
        return 16
    if t[0] == 'fixed':
        return _size(t[1]) * t[2]
    return STRUCTS[t[1]][0]


# --- reading -----------------------------------------------------------------------------------

class _Reader:
    def __init__(self, blob):
        self.b = blob
        if blob[:8] != _HEADER[:8]:
            raise Hk2014Error("not a Havok packfile")
        secs = {}
        for k in range(3):
            o = _SECTIONS_AT + 0x40 * k
            name = blob[o:o + 20].split(b'\0')[0].decode()
            secs[name] = struct.unpack_from('<7I', blob, o + 20)
        cn, d = secs['__classnames__'], secs['__data__']
        self.base = d[0]
        self.local = self._table(d[0] + d[1], d[0] + d[2], 2)
        glob = self._table(d[0] + d[2], d[0] + d[3], 3)
        self.glob = {a: c for a, (_b, c) in glob.items()}
        virt = self._table(d[0] + d[3], d[0] + d[4], 3)
        self.cls = {a: blob[cn[0] + c:blob.index(b'\0', cn[0] + c)].decode()
                    for a, (_b, c) in virt.items()}
        self.objs = {}
        self.covered = {}            # object -> bytes its body's fields cover (checking)

    def _table(self, a, b, n):
        out = {}
        for o in range(a, b - 4 * n + 1, 4 * n):
            t = struct.unpack_from(f'<{n}I', self.b, o)
            if t[0] != 0xFFFFFFFF:
                out[t[0]] = t[1] if n == 2 else t[1:]
        return out

    def obj(self, rel):
        if rel in self.objs:
            return self.objs[rel]
        name = self.cls.get(rel)
        if name not in CLASSES:
            raise Hk2014Error(f"no layout for {name}")
        o = Obj(name)
        self.objs[rel] = o
        size, fields = CLASSES[name]
        self._check_gaps(rel, size, fields, name)
        for off, fname, t in fields:
            o.value[fname] = self.value(t, rel + off)
        return o

    def _check_gaps(self, rel, size, fields, name):
        used = bytearray(size)
        for off, _f, t in fields:
            used[off:off + _size(t)] = b'\1' * _size(t)
        a = self.base + rel
        for i in range(size):
            if not used[i] and self.b[a + i]:
                raise Hk2014Error(f"{name}+{i}: unread byte {self.b[a + i]:#x}")

    def value(self, t, rel):
        a = self.base + rel
        if isinstance(t, str):
            if t in _SCALARS:
                return struct.unpack_from('<' + _SCALARS[t], self.b, a)[0]
            if t == 'vec4':
                return struct.unpack_from('<4f', self.b, a)
            if t == 'mat4':
                return struct.unpack_from('<16f', self.b, a)
            if t == 'str':
                p = self.local.get(rel)
                if p is None:
                    return None
                s = self.base + p
                return self.b[s:self.b.index(b'\0', s)].decode('ascii')
            if t == 'ptr':
                p = self.glob.get(rel)
                return None if p is None else self.obj(p)
        if t[0] == 'arr':
            n = struct.unpack_from('<i', self.b, a + 8)[0]
            p = self.local.get(rel)
            if n and p is None:
                raise Hk2014Error(f"array at {rel:#x} with {n} items and no data")
            es = _size(t[1])
            return [self.value(t[1], p + es * k) for k in range(n)]
        if t[0] == 'fixed':
            es = _size(t[1])
            return [self.value(t[1], rel + es * k) for k in range(t[2])]
        size, fields = STRUCTS[t[1]]
        self._check_gaps(rel, size, fields, t[1])
        return {f: self.value(ft, rel + off) for off, f, ft in fields}


def read_graph(blob):
    """The root object of an hk_2014 cloth packfile, every pointer followed."""
    r = _Reader(blob)
    roots = [a for a, n in r.cls.items() if n == 'hkRootLevelContainer']
    if not roots:
        raise Hk2014Error("no hkRootLevelContainer")
    return r.obj(min(roots))


def walk(root):
    """Every Obj reachable from root, each once, in write order."""
    out, seen = [], set()

    def objs_in(t, v):
        if v is None:
            return
        if t == 'ptr':
            yield v
        elif isinstance(t, tuple):
            if t[0] in ('arr', 'fixed'):
                for x in v:
                    yield from objs_in(t[1], x)
            elif t[0] == 'struct':
                for _o, f, ft in STRUCTS[t[1]][1]:
                    yield from objs_in(ft, v[f])

    def visit(o):
        if id(o) in seen:
            return
        seen.add(id(o))
        out.append(o)
        for _off, f, t in CLASSES[o.type_name][1]:
            for x in objs_in(t, o.value.get(f)):
                visit(x)
    visit(root)
    return out


# --- writing -----------------------------------------------------------------------------------

class _Writer:
    def __init__(self):
        self.d = bytearray()
        self.local = []              # (src, dst)
        self.glob = []               # (src, dst object)
        self.virt = []               # (object offset, class name)
        self.at = {}                 # id(Obj) -> offset

    def align(self):
        self.d += b'\0' * (-len(self.d) % 16)

    def write(self, root):
        self.obj(root)
        return self

    def obj(self, o):
        if id(o) in self.at:
            return
        self.align()
        size, fields = CLASSES[o.type_name]
        start = len(self.d)
        self.at[id(o)] = start
        self.virt.append((start, o.type_name))
        self.d += b'\0' * size
        later = []
        self.fields(fields, o.value, start, later)
        for x in later:
            self.obj(x)

    def fields(self, fields, value, start, later):
        """Write `fields` of `value` (at `start`, already allocated) and then their data."""
        for off, f, t in fields:
            self.put(t, value.get(f), start + off, later)
        for off, f, t in fields:
            self.data(t, value.get(f), start + off, later)

    def put(self, t, v, at, later):
        """The inline part of a value at `at`."""
        if isinstance(t, str):
            if t in _SCALARS:
                struct.pack_into('<' + _SCALARS[t], self.d, at, 0 if v is None else v)
            elif t in ('vec4', 'mat4'):
                struct.pack_into(f'<{_size(t) // 4}f', self.d, at, *v)
            elif t == 'ptr' and v is not None:
                self.glob.append((at, v))
                later.append(v)
            return
        if t[0] == 'arr':
            n = len(v or [])
            struct.pack_into('<iI', self.d, at + 8, n, n | _ARRAY_FLAGS)
        elif t[0] == 'fixed':
            es = _size(t[1])
            for k, x in enumerate(v):
                self.put(t[1], x, at + es * k, later)
        elif t[0] == 'struct':
            for off, f, ft in STRUCTS[t[1]][1]:
                self.put(ft, v.get(f), at + off, later)

    def data(self, t, v, at, later):
        """The out-of-line part of a value whose inline part is at `at`."""
        if t == 'str':
            if v is not None:
                self.align()
                self.local.append((at, len(self.d)))
                self.d += v.encode('ascii') + b'\0'
            return
        if isinstance(t, str):
            return
        if t[0] == 'arr':
            if not v:
                return
            self.align()
            es = _size(t[1])
            start = len(self.d)
            self.local.append((at, start))
            self.d += b'\0' * (es * len(v))
            for k, x in enumerate(v):
                self.put(t[1], x, start + es * k, later)
            for k, x in enumerate(v):
                self.data(t[1], x, start + es * k, later)
        elif t[0] == 'fixed':
            es = _size(t[1])
            for k, x in enumerate(v):
                self.data(t[1], x, at + es * k, later)
        elif t[0] == 'struct':
            for off, f, ft in STRUCTS[t[1]][1]:
                self.data(ft, v.get(f), at + off, later)


def _section_header(name, start, local, glob, virt, end):
    h = bytearray(b'\xff' * 0x40)
    h[:19] = name.encode().ljust(19, b'\0')
    struct.pack_into('<7I', h, 20, start, local, glob, virt, end, end, end)
    return bytes(h)


def write_graph(root):
    """An hk_2014 packfile holding the graph under root."""
    w = _Writer().write(root)
    w.align()
    # Class names: Havok's four, then each class in order of first appearance.
    names = ['hkClass', 'hkClassMember', 'hkClassEnum', 'hkClassEnumItem']
    for _a, n in w.virt:
        if n not in names:
            names.append(n)
    cn = bytearray()
    cn_off = {}
    for n in names:
        cn += struct.pack('<IB', SIGNATURES[n], 9)
        cn_off[n] = len(cn)
        cn += n.encode() + b'\0'
    cn += b'\xff' * (-len(cn) % 16)

    def table(rows, n):
        out = bytearray()
        for r in rows:
            out += struct.pack(f'<{n}I', *r)
        out += b'\xff' * (-len(out) % 16)
        return out
    loc = table(w.local, 2)
    glb = table([(a, 2, w.at[id(o)]) for a, o in w.glob], 3)
    vrt = table([(a, 0, cn_off[n]) for a, n in w.virt], 3)
    data = bytes(w.d)
    cn_start = _SECTIONS_AT + 3 * 0x40
    data_start = cn_start + len(cn)
    l0 = len(data)
    g0 = l0 + len(loc)
    v0 = g0 + len(glb)
    end = v0 + len(vrt)
    hdr = bytearray(_HEADER)
    struct.pack_into('<i', hdr, 0x24, cn_off['hkRootLevelContainer'])
    out = bytearray(hdr)
    n_cn = len(cn)
    out += _section_header('__classnames__', cn_start, n_cn, n_cn, n_cn, n_cn)
    out += _section_header('__types__', data_start, 0, 0, 0, 0)
    out += _section_header('__data__', data_start, l0, g0, v0, end)
    # Every vanilla BSClothExtraData blob ends with one more zero byte.
    return bytes(out + cn + data + loc + glb + vrt) + b'\0'
