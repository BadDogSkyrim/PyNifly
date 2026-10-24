"""Read Havok 2019 tagfiles ("TAG0"), the container Starfield uses for its Havok blobs (the cloth
in BSClothExtraData, among others).

A tagfile carries its own type definitions, so it can be read without knowing the classes in
advance: every object comes back as a dict of named fields.

    TAG0                        root container
      SDKV   "20190200"         SDK version
      DATA                      the object bytes
      TYPE                      the type definitions
        TPTR                    (runtime pointer table; zeros in a file)
        TST1                    type-name strings, NUL-separated
        TNA1                    the types: name + template parameters
        FST1                    field-name strings, NUL-separated
        TBDY                    each type's parent, flags, format, size and fields
        THSH                    type hashes
        TPAD                    padding
      INDX
        ITEM                    the item table: (type, offset into DATA, count) per item
        PTCH                    where in DATA the item references are

Section header: big-endian u32 whose top two bits are flags (0 = container of sections,
1 = data) and low 30 bits the size including the 8-byte header, then a 4-character tag.

    python havok_tagfile.py <file.nif | file.bin> [--types] [--item N]
"""
import struct
import sys

# Type format kinds: the low 5 bits of a type's format word.
F_VOID, F_OPAQUE, F_BOOL, F_STRING, F_INT, F_FLOAT, F_POINTER, F_CLASS, F_ARRAY, F_TUPLE = range(10)
KIND_NAMES = ['void', 'opaque', 'bool', 'string', 'int', 'float', 'pointer', 'class', 'array',
              'tuple']

# Type body flags: which optional fields follow in TBDY.
B_FORMAT, B_SUBTYPE, B_VERSION, B_SIZEALIGN, B_FLAGS, B_MEMBERS, B_INTERFACES, B_ATTRIBUTE = \
    0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80


class TagfileError(Exception):
    pass


def sections(b, start=0, end=None):
    """(tag, payload start, payload end, is_container) for each section in b[start:end]."""
    end = len(b) if end is None else end
    o = start
    while o + 8 <= end:
        head, tag = struct.unpack_from('>I4s', b, o)
        size = head & 0x3FFFFFFF
        if size < 8 or o + size > end:
            break
        yield tag.decode('ascii', 'replace'), o + 8, o + size, (head >> 30) == 0
        o += size


def section_map(b):
    """{tag: (start, end)} for every section at any depth."""
    out = {}

    def walk(start, end):
        for tag, s, e, container in sections(b, start, end):
            out[tag] = (s, e)
            if container:
                walk(s, e)
    walk(0, len(b))
    return out


class Reader:
    """A cursor over a byte string, reading Havok's packed integers."""
    def __init__(self, b, o, end):
        self.b, self.o, self.end = b, o, end

    def more(self):
        return self.o < self.end

    def varint(self):
        """Havok's variable-length unsigned int: the high bits of the first byte say how many
        bytes follow, and the value is big-endian."""
        b, o = self.b, self.o
        x = b[o]
        if x & 0x80 == 0:
            self.o += 1
            return x
        top = x >> 3
        if 0x10 <= top <= 0x17:
            self.o += 2
            return ((x << 8) | b[o + 1]) & 0x3FFF
        if 0x18 <= top <= 0x1B:
            self.o += 3
            return ((x << 16) | (b[o + 1] << 8) | b[o + 2]) & 0x1FFFFF
        if top == 0x1C:
            self.o += 4
            return int.from_bytes(b[o:o + 4], 'big') & 0x7FFFFFF
        if top == 0x1D:
            self.o += 5
            return int.from_bytes(b[o:o + 5], 'big') & 0x7FFFFFFFF
        if top == 0x1E:
            self.o += 8
            return int.from_bytes(b[o:o + 8], 'big') & 0x7FFFFFFFFFFFFFF
        if top == 0x1F:
            self.o += 9
            return int.from_bytes(b[o + 1:o + 9], 'big')
        raise TagfileError(f"bad varint byte {x:#x} at {o}")


def strings(b, start, end):
    return b[start:end].split(b'\0')[:-1] and [s.decode('utf-8', 'replace')
                                              for s in b[start:end].split(b'\0')[:-1]]


class Type:
    def __init__(self, index, name):
        self.index, self.name = index, name
        self.templates = []          # [(name, value)]: 't...' values are types, 'v...' ints
        self.parent = None
        self.format = 0
        self.subtype = None          # pointer/array element type
        self.version = None
        self.size = self.align = None
        self.flags = 0
        self.members = []            # [(name, flags, offset, type)]
        self.interfaces = []

    @property
    def kind(self):
        return self.format & 0x1F

    def __repr__(self):
        t = ', '.join(f"{n}={v.name if isinstance(v, Type) else v}" for n, v in self.templates)
        return f"{self.name}<{t}>" if t else self.name


class Tagfile:
    def __init__(self, b):
        if b[4:8] != b'TAG0':
            raise TagfileError("not a Havok tagfile (no TAG0)")
        self.b = b
        self.sec = section_map(b)
        sv = self.sec.get('SDKV')
        self.sdk = b[sv[0]:sv[1]].decode('ascii', 'replace') if sv else None
        self.data_start = self.sec['DATA'][0]
        self._read_types()
        self._read_items()

    def _read_types(self):
        b = self.b
        tnames = strings(b, *self.sec['TST1'])
        fnames = strings(b, *self.sec['FST1'])
        r = Reader(b, *self.sec['TNA1'])
        n = r.varint()
        self.types = [None] + [Type(i, None) for i in range(1, n)]
        for i in range(1, n):
            t = self.types[i]
            t.name = tnames[r.varint()]
            for _ in range(r.varint()):
                tn = tnames[r.varint()]
                v = r.varint()
                t.templates.append((tn, self.types[v] if tn.startswith('t') else v))

        r = Reader(b, *self.sec['TBDY'])
        while r.more():
            i = r.varint()
            if i == 0:
                continue
            t = self.types[i]
            t.parent = self.types[r.varint()]
            opt = r.varint()
            if opt & B_FORMAT:
                t.format = r.varint()
            if opt & B_SUBTYPE:
                t.subtype = self.types[r.varint()]
            if opt & B_VERSION:
                t.version = r.varint()
            if opt & B_SIZEALIGN:
                t.size, t.align = r.varint(), r.varint()
            if opt & B_FLAGS:
                t.flags = r.varint()
            if opt & B_MEMBERS:
                for _ in range(r.varint()):
                    name, mflags = fnames[r.varint()], r.varint()
                    if mflags & 0x80:          # one more value before the offset (meaning
                        r.varint()             # unknown; seen as 3 on hclCollidable.userData)
                    t.members.append((name, mflags, r.varint(), self.types[r.varint()]))
            if opt & B_INTERFACES:
                for _ in range(r.varint()):
                    t.interfaces.append((self.types[r.varint()], r.varint()))
            if opt & B_ATTRIBUTE:
                r.varint()

    def _read_items(self):
        s, e = self.sec['ITEM']
        self.items = []
        for o in range(s, e, 12):
            flags, offset, count = struct.unpack_from('<III', self.b, o)
            self.items.append((self.types[flags & 0xFFFFFF] if flags & 0xFFFFFF else None,
                               flags >> 24, offset, count))

    # --- type helpers ---
    def resolved(self, t):
        """`t`, or the first ancestor that says what it is (format, size, members)."""
        while t is not None and not t.format and t.parent is not None:
            t = t.parent
        return t

    def all_members(self, t):
        chain = []
        while t is not None:
            chain.append(t)
            t = t.parent
        out = []
        for c in reversed(chain):
            out.extend(c.members)
        return out

    def size_of(self, t):
        while t is not None:
            if t.size is not None:
                return t.size
            t = t.parent
        raise TagfileError(f"no size for {t}")

    def format_of(self, t):
        while t is not None:
            if t.format:
                return t.format
            t = t.parent
        return 0

    def subtype_of(self, t):
        while t is not None:
            if t.subtype is not None:
                return t.subtype
            t = t.parent
        return None

    # --- values ---
    def read(self, t, o, depth=0):
        """The value of type `t` at absolute offset `o`."""
        fmt = self.format_of(t)
        kind = fmt & 0x1F
        b = self.b
        if kind == F_BOOL:
            return bool(b[o])
        if kind == F_INT:
            size = self.size_of(t)
            signed = bool(fmt & 0x200)
            return int.from_bytes(b[o:o + size], 'little', signed=signed)
        if kind == F_FLOAT:
            size = self.size_of(t)
            return struct.unpack_from('<f' if size == 4 else '<d', b, o)[0]
        if kind == F_STRING:
            return self.item_string(struct.unpack_from('<I', b, o)[0])
        if kind == F_POINTER:
            return ItemRef(self, struct.unpack_from('<I', b, o)[0])
        if kind == F_ARRAY and not fmt & 0x20:
            return ItemRef(self, struct.unpack_from('<I', b, o)[0])
        if kind == F_TUPLE or kind == F_ARRAY:     # 0x20: inline, fmt >> 8 elements (hkVector4)
            n = fmt >> 8
            et = self.subtype_of(t)
            es = self.size_of(et)
            return [self.read(et, o + k * es, depth) for k in range(n)]
        if kind in (F_CLASS, F_OPAQUE, F_VOID):
            members = self.all_members(t)
            if not members:
                return bytes(b[o:o + (self.size_of(t) or 0)])
            return {name: self.read(mt, o + off, depth + 1)
                    for name, _flags, off, mt in members}
        return f"<{KIND_NAMES[kind] if kind < len(KIND_NAMES) else kind}>"

    def item_string(self, idx):
        if idx == 0 or idx >= len(self.items):
            return None
        _t, _f, off, count = self.items[idx]
        s = self.b[self.data_start + off:self.data_start + off + count]
        return s.split(b'\0')[0].decode('utf-8', 'replace')

    # --- in-place writes: same sizes, offsets and references, so the blob stays valid ---
    def locate(self, idx, k=0, path=()):
        """(absolute offset, type) of element `k` of item `idx`, then down the member `path`."""
        t, _f, off, _c = self.items[idx]
        o = self.data_start + off + k * self.size_of(t)
        for name in path:
            m = next((m for m in self.all_members(t) if m[0] == name), None)
            if m is None:
                raise TagfileError(f"{t.name} has no member {name}")
            o, t = o + m[2], m[3]
        return o, t

    def get_at(self, idx, k=0, path=()):
        """The current value (edits included) of element `k` of item `idx` down `path`."""
        o, t = self.locate(idx, k, path)
        saved, self.b = self.b, self.buf
        try:
            return self.read(t, o)
        finally:
            self.b = saved

    def set_at(self, idx, value, k=0, path=()):
        """Overwrite a bool, int, float or inline vector in place."""
        o, t = self.locate(idx, k, path)
        self._write(o, t, value)

    @property
    def buf(self):
        if not hasattr(self, '_buf'):
            self._buf = bytearray(self.b)
        return self._buf

    def _write(self, o, t, value, buf=None):
        """Write `value` as type `t` at `o` in `buf` (default: the edit buffer). A class takes a
        dict of its members, missing ones left as they are. References -- pointers, strings,
        plain arrays -- can't be written: each needs an entry in PTCH."""
        buf = self.buf if buf is None else buf
        fmt = self.format_of(t)
        kind = fmt & 0x1F
        if kind == F_BOOL:
            buf[o] = 1 if value else 0
        elif kind == F_INT:
            size = self.size_of(t)
            buf[o:o + size] = int(value).to_bytes(size, 'little', signed=bool(fmt & 0x200))
        elif kind == F_FLOAT:
            struct.pack_into('<f' if self.size_of(t) == 4 else '<d', buf, o, value)
        elif (kind == F_TUPLE or kind == F_ARRAY) and fmt & 0x20:
            n, et = fmt >> 8, self.subtype_of(t)
            if len(value) != n:
                raise TagfileError(f"{t.name} holds {n} values, not {len(value)}")
            es = self.size_of(et)
            for k, v in enumerate(value):
                self._write(o + k * es, et, v, buf)
        elif kind == F_CLASS and self.all_members(t):
            for name, _flags, off, mt in self.all_members(t):
                if name in value:
                    self._write(o + off, mt, value[name], buf)
        else:
            raise TagfileError(f"can't write a {KIND_NAMES[kind]} in place")

    def append_to_array(self, idx, values):
        """The blob with `values` (dicts, for a class element type) added to the end of array
        item `idx`. Returns new bytes; this Tagfile is left as it was.

        An array is referred to by its item number, never by position, and item offsets (in
        ITEM) and reference positions (in PTCH) both count from the start of DATA. So a longer
        copy can go at the end of DATA, with its item pointed at it, and nothing else moves. The
        old copy stays behind, unused. Elements holding references would need PTCH entries, and
        are refused."""
        t, _flags, off, count = self.items[idx]
        size = self.size_of(t)
        b = self.buf
        ds, de = self.sec['DATA']
        payload = bytearray(b[ds:de])
        new_off = (len(payload) + 15) & ~15
        payload += bytes(new_off - len(payload))
        payload += b[ds + off:ds + off + count * size]
        for v in values:
            elem = bytearray(size)
            self._write(0, t, v, elem)
            payload += elem
        payload += bytes(-len(payload) % 4)

        tag_end = self.sec['TAG0'][1]
        out = bytearray(b[:ds - 8])
        head = struct.unpack_from('>I', b, ds - 8)[0]
        out += struct.pack('>I', (head & 0xC0000000) | (len(payload) + 8)) + b'DATA'
        out += payload
        out += b[de:tag_end]
        out += b[tag_end:]
        delta = len(out) - len(b)
        head0 = struct.unpack_from('>I', out, 0)[0]
        struct.pack_into('>I', out, 0, (head0 & 0xC0000000) | ((head0 & 0x3FFFFFFF) + delta))
        # The ITEM section moved by delta along with everything after DATA.
        entry = self.sec['ITEM'][0] + delta + 12 * idx
        struct.pack_into('<II', out, entry + 4, new_off, count + len(values))
        return bytes(out)

    def to_bytes(self):
        """The blob, with any in-place edits."""
        return bytes(self.buf)

    def item(self, idx):
        """Item `idx` decoded: one value, or a list for an array item."""
        t, _flags, off, count = self.items[idx]
        size = self.size_of(t)
        base = self.data_start + off
        vals = [self.read(t, base + k * size) for k in range(count)]
        return vals[0] if count == 1 else vals


class ItemRef:
    def __init__(self, tf, idx):
        self.tf, self.idx = tf, idx

    def get(self):
        return None if self.idx == 0 else self.tf.item(self.idx)

    def list(self):
        """The item as a list, even when it has one element (get() returns that bare); a null
        reference is an empty list."""
        if self.idx == 0:
            return []
        v = self.tf.item(self.idx)
        return [v] if self.tf.items[self.idx][3] == 1 else v

    def __repr__(self):
        if self.idx == 0:
            return 'null'
        t, _f, _o, count = self.tf.items[self.idx]
        return f"#{self.idx}:{t.name}[{count}]"


def _blob_from(path):
    if path.lower().endswith('.nif'):
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pyn.pynifly import NifFile
        cd = NifFile(path).cloth_data
        if not cd:
            raise TagfileError(f"{path} has no cloth data")
        return cd[0][1]
    return open(path, 'rb').read()


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--types', action='store_true')
    ap.add_argument('--item', type=int, action='append')
    a = ap.parse_args(argv)
    tf = Tagfile(_blob_from(a.file))
    print(f"SDK {tf.sdk}: {len(tf.types) - 1} types, {len(tf.items) - 1} items")
    if a.types:
        for t in tf.types[1:]:
            fmt = tf.format_of(t)
            print(f"{t.index:4} {t!r:50} parent={t.parent!r} kind={KIND_NAMES[fmt & 0x1F]} "
                  f"fmt={fmt:#x} size={t.size} sub={t.subtype!r}")
            for m in t.members:
                print(f"         +{m[2]:<4} {m[0]:32} {m[3]!r}")
    for i in (a.item or []):
        print(i, tf.items[i][0], tf.item(i))
    if not a.types and not a.item:
        for i, (t, f, off, count) in enumerate(tf.items[1:], 1):
            print(f"{i:4} {t!r:60} flags={f:#x} off={off:<6} count={count}")


if __name__ == '__main__':
    main(sys.argv[1:])
