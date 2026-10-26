"""Rewrite a Havok 2019 tagfile ("TAG0") whole: the layer under structural edits -- new types,
new objects, longer arrays -- that the in-place edits in havok_tagfile can't make.

TagDoc keeps each section as the raw numbers it holds (string-table indices, type indices,
offsets), in file order, and writes them back the same way, so an unedited blob comes back
byte-identical. See havok_tagfile for the format. What it adds:

    copy_type(donor, t)       bring a type, and every type it refers to, over from another blob
    add_item(t, data, count)  a new object or array at the end of DATA
    add_patch(t, offset)      record that DATA[offset] holds a reference of type t (PTCH)

havok_graph writes whole blobs through these.

PTCH lists, per reference TYPE (each hkArray<...>, T*, hkStringPtr instance is its own type),
the DATA offsets holding a reference; the u32 there is an item index. A new reference has to
be listed, or the loader never resolves it.
"""
import struct

from .havok_tagfile import Reader, Tagfile, TagfileError, section_map


def encode_varint(v):
    """Inverse of Reader.varint, shortest form."""
    if v < 0x80:
        return bytes([v])
    if v < 0x4000:
        return (0x8000 | v).to_bytes(2, 'big')
    if v < 0x200000:
        return (0xC00000 | v).to_bytes(3, 'big')
    if v < 0x8000000:
        return (0xE0000000 | v).to_bytes(4, 'big')
    if v < 0x800000000:
        return (0xE800000000 | v).to_bytes(5, 'big')
    if v < 0x800000000000000:
        return (0xF000000000000000 | v).to_bytes(8, 'big')
    return b'\xf8' + v.to_bytes(8, 'big')


def _strings(raw):
    """(strings, trailing bytes after the last NUL)."""
    end = raw.rfind(b'\0') + 1
    return [s.decode('utf-8') for s in raw[:end].split(b'\0')[:-1]], raw[end:]


def _section(tag, payload, container=False):
    return struct.pack('>I', (0 if container else 0x40000000) | (len(payload) + 8)) + \
        tag.encode('ascii') + payload


class Body:
    """One TBDY entry, as raw numbers."""
    __slots__ = ('index', 'parent', 'opt', 'format', 'subtype', 'version', 'size', 'align',
                 'flags', 'members', 'interfaces', 'attribute')

    def __init__(self, index):
        self.index = index
        self.parent = 0
        self.opt = 0
        self.format = self.subtype = self.version = self.size = self.align = None
        self.flags = self.attribute = None
        self.members = []          # [name idx (FST1), flags, extra or None, offset, type idx]
        self.interfaces = []       # [(type idx, value)]


class TagDoc:
    def __init__(self, blob):
        self.blob = bytes(blob)
        b = self.blob
        sec = section_map(b)
        self.sdkv = b[sec['SDKV'][0]:sec['SDKV'][1]]
        self.data = bytearray(b[sec['DATA'][0]:sec['DATA'][1]])
        self.tail = b[sec['TAG0'][1]:]
        self.order = [tag for tag in ('TPTR', 'TST1', 'TNA1', 'FST1', 'TBDY', 'THSH', 'TPAD')
                      if tag in sec]
        self.tptr = b[sec['TPTR'][0]:sec['TPTR'][1]]
        self._raw = {tag: b[sec[tag][0]:sec[tag][1]] for tag in self.order}
        self.tpad = b[sec['TPAD'][0]:sec['TPAD'][1]] if 'TPAD' in sec else b''
        self.tnames, self.tst_pad = _strings(b[sec['TST1'][0]:sec['TST1'][1]])
        self.fnames, self.fst_pad = _strings(b[sec['FST1'][0]:sec['FST1'][1]])

        r = Reader(b, *sec['TNA1'])
        n = r.varint()
        self.tna = [None]                    # per type: (name idx, [(template name idx, v)])
        for _ in range(1, n):
            name = r.varint()
            self.tna.append((name, [(r.varint(), r.varint()) for _ in range(r.varint())]))
        self.tna_pad = b[r.o:sec['TNA1'][1]]

        r = Reader(b, *sec['TBDY'])
        self.bodies = []                     # in file order; a 0 entry is kept as Body(0)
        while r.more():
            body = Body(r.varint())
            self.bodies.append(body)
            if body.index == 0:
                continue
            body.parent, body.opt = r.varint(), r.varint()
            if body.opt & 0x01:
                body.format = r.varint()
            if body.opt & 0x02:
                body.subtype = r.varint()
            if body.opt & 0x04:
                body.version = r.varint()
            if body.opt & 0x08:
                body.size, body.align = r.varint(), r.varint()
            if body.opt & 0x10:
                body.flags = r.varint()
            if body.opt & 0x20:
                for _ in range(r.varint()):
                    name, mflags = r.varint(), r.varint()
                    extra = r.varint() if mflags & 0x80 else None
                    body.members.append([name, mflags, extra, r.varint(), r.varint()])
            if body.opt & 0x40:
                body.interfaces = [(r.varint(), r.varint()) for _ in range(r.varint())]
            if body.opt & 0x80:
                body.attribute = r.varint()
        # TBDY is padded to 4 bytes with zeros, which read as empty (index 0) entries. They're
        # padding, not bodies, and only ever at the end: a body written after them is never read.
        while self.bodies and self.bodies[-1].index == 0:
            self.bodies.pop()
        if any(body.index == 0 for body in self.bodies):
            raise TagfileError("TBDY has an empty entry before its end")

        r = Reader(b, *sec['THSH'])
        self.hashes = []
        for _ in range(r.varint()):
            i = r.varint()
            self.hashes.append((i, struct.unpack_from('<I', b, r.o)[0]))
            r.o += 4
        self.thsh_pad = b[r.o:sec['THSH'][1]]

        s, e = sec['ITEM']
        self.items = [list(struct.unpack_from('<III', b, o)) for o in range(s, e, 12)]
        s, e = sec['PTCH']
        self.patches = []                    # [(type idx, [DATA offsets])]
        o = s
        while o < e:
            t, n = struct.unpack_from('<II', b, o)
            self.patches.append([t, list(struct.unpack_from(f'<{n}I', b, o + 8))])
            o += 8 + 4 * n

    # --- writing --------------------------------------------------------------------------
    def to_bytes(self):
        tna = bytearray(encode_varint(len(self.tna)))
        for name, temps in self.tna[1:]:
            tna += encode_varint(name) + encode_varint(len(temps))
            for tn, v in temps:
                tna += encode_varint(tn) + encode_varint(v)

        tbdy = bytearray()
        for body in self.bodies:
            tbdy += encode_varint(body.index)
            if body.index == 0:
                continue
            tbdy += encode_varint(body.parent) + encode_varint(body.opt)
            if body.opt & 0x01:
                tbdy += encode_varint(body.format)
            if body.opt & 0x02:
                tbdy += encode_varint(body.subtype)
            if body.opt & 0x04:
                tbdy += encode_varint(body.version)
            if body.opt & 0x08:
                tbdy += encode_varint(body.size) + encode_varint(body.align)
            if body.opt & 0x10:
                tbdy += encode_varint(body.flags)
            if body.opt & 0x20:
                tbdy += encode_varint(len(body.members))
                for name, mflags, extra, off, mt in body.members:
                    tbdy += encode_varint(name) + encode_varint(mflags)
                    if mflags & 0x80:
                        tbdy += encode_varint(extra)
                    tbdy += encode_varint(off) + encode_varint(mt)
            if body.opt & 0x40:
                tbdy += encode_varint(len(body.interfaces))
                for t, v in body.interfaces:
                    tbdy += encode_varint(t) + encode_varint(v)
            if body.opt & 0x80:
                tbdy += encode_varint(body.attribute)

        thsh = bytearray(encode_varint(len(self.hashes)))
        for i, h in self.hashes:
            thsh += encode_varint(i) + struct.pack('<I', h)

        parts = {
            'TPTR': self.tptr,
            'TST1': self._padded('TST1', ''.join(s + '\0' for s in self.tnames).encode('utf-8'),
                                 0xFF),
            'TNA1': self._padded('TNA1', bytes(tna), 0),
            'FST1': self._padded('FST1', ''.join(s + '\0' for s in self.fnames).encode('utf-8'),
                                 0xFF),
            'TBDY': self._padded('TBDY', bytes(tbdy), 0),
            'THSH': self._padded('THSH', bytes(thsh), 0),
            'TPAD': self.tpad,
        }
        typ = b''.join(_section(tag, parts[tag]) for tag in self.order)
        item = b''.join(struct.pack('<III', *it) for it in self.items)
        ptch = b''.join(struct.pack(f'<II{len(offs)}I', t, len(offs), *offs)
                        for t, offs in self.patches)
        body = (_section('SDKV', self.sdkv) + _section('DATA', bytes(self.data)) +
                _section('TYPE', typ, container=True) +
                _section('INDX', _section('ITEM', item) + _section('PTCH', ptch),
                         container=True))
        return _section('TAG0', body, container=True) + self.tail

    def _padded(self, tag, content, fill):
        """A type subsection's payload, padded to 4 bytes with `fill` as vanilla always is
        (TST1/FST1 with 0xFF, the rest with 0). Unchanged content keeps its original padding --
        Felid's tail has an unpadded THSH and loads -- so an unedited blob stays identical."""
        raw = self._raw[tag]
        rest = raw[len(content):]
        if raw[:len(content)] == content and len(rest) < 4 and set(rest) <= {fill}:
            return raw
        return content + bytes([fill]) * (-len(content) % 4)

    # --- types ------------------------------------------------------------------------------
    def type_name(self, t):
        return self.tnames[self.tna[t][0]] if t else None

    def _signature(self, t, seen=()):
        """A type's identity across blobs: its name and template arguments, recursively."""
        if not t:
            return None
        if self.tna[t] is None:                       # a type still being copied in
            return ('<pending>', t)
        if t in seen:
            return ('<cycle>', self.type_name(t))
        name, temps = self.tna[t]
        args = tuple((self.tnames[tn], self._signature(v, seen + (t,))
                      if self.tnames[tn].startswith('t') else v) for tn, v in temps)
        return (self.tnames[name], args)

    def find_type(self, signature):
        for t in range(1, len(self.tna)):
            if self.tna[t] is not None and self._signature(t) == signature:
                return t
        return None

    def body_of(self, t):
        return next((b for b in self.bodies if b.index == t), None)

    def _tname(self, s):
        if s not in self.tnames:
            self.tnames.append(s)
        return self.tnames.index(s)

    def _fname(self, s):
        if s not in self.fnames:
            self.fnames.append(s)
        return self.fnames.index(s)

    def copy_type(self, donor, t, _map=None):
        """This blob's index for `donor`'s type `t`, adding it -- and every type its body and
        templates refer to -- if this blob doesn't have it yet. Types match by name and
        template arguments."""
        _map = {} if _map is None else _map
        if not t:
            return 0
        if t in _map:
            return _map[t]
        mine = self.find_type(donor._signature(t))
        if mine is not None:
            _map[t] = mine
            # A blob can name a type it never defines (no TBDY body); take the donor's.
            if self.body_of(mine) is None and donor.body_of(t) is not None:
                self._copy_body(donor, t, mine, _map)
            return mine
        new = len(self.tna)
        _map[t] = new
        name, temps = donor.tna[t]
        self.tna.append(None)                # reserve the index; templates may refer back
        self.tptr += bytes(8)
        tmp = []
        for tn, v in temps:
            tname = donor.tnames[tn]
            tmp.append((self._tname(tname),
                        self.copy_type(donor, v, _map) if tname.startswith('t') else v))
        self.tna[new] = (self._tname(donor.tnames[name]), tmp)
        if donor.body_of(t) is not None:
            self._copy_body(donor, t, new, _map)
        else:
            h = next((h for i, h in donor.hashes if i == t), None)
            if h is not None:
                self.hashes.append((new, h))
        return new

    def _copy_body(self, donor, t, mine, _map):
        """Donor type `t`'s TBDY body, as this blob's type `mine`."""
        db = donor.body_of(t)
        body = Body(mine)
        body.parent = self.copy_type(donor, db.parent, _map)
        body.opt = db.opt
        body.format, body.version = db.format, db.version
        body.size, body.align, body.flags, body.attribute = \
            db.size, db.align, db.flags, db.attribute
        body.subtype = self.copy_type(donor, db.subtype, _map) if db.subtype else db.subtype
        body.members = [[self._fname(donor.fnames[mn]), mflags, extra, off,
                         self.copy_type(donor, mt, _map)]
                        for mn, mflags, extra, off, mt in db.members]
        body.interfaces = [(self.copy_type(donor, it, _map), v) for it, v in db.interfaces]
        self.bodies.append(body)
        if not any(i == mine for i, _h in self.hashes):
            h = next((h for i, h in donor.hashes if i == t), None)
            if h is not None:
                self.hashes.append((mine, h))

    # --- objects ------------------------------------------------------------------------------
    def add_item(self, t, data, count, kind=None, align=16):
        """A new item of type `t` holding `count` elements of `data` (bytes), placed at the end
        of DATA. `kind` is the item's high-byte flags: 0x10 an object, 0x20 an array (default:
        an object when count is 1). Returns (item index, DATA offset)."""
        if kind is None:
            kind = 0x10 if count == 1 else 0x20
        self.data += bytes(-len(self.data) % align)
        off = len(self.data)
        self.data += data
        self.data += bytes(-len(self.data) % 4)
        self.items.append([(kind << 24) | t, off, count])
        return len(self.items) - 1, off

    def stray_patches(self):
        """PTCH offsets that lie in no item. Every vanilla blob has none, and Starfield drops the
        whole cloth when there are any."""
        tf = Tagfile(self.to_bytes())
        spans = [(off, off + cnt * tf.size_of(tf.types[fl & 0xFFFFFF]))
                 for fl, off, cnt in self.items[1:]]
        return [(t, o) for t, offs in self.patches for o in offs
                if not any(a <= o < z for a, z in spans)]

    def add_patch(self, t, offset):
        """DATA[offset] holds a reference of type `t`."""
        for group in self.patches:
            if group[0] == t:
                group[1].append(offset)
                group[1].sort()
                return
        self.patches.append([t, [offset]])
        self.patches.sort(key=lambda g: g[0])

    def tagfile(self):
        """A reader over the blob as it stands now."""
        return Tagfile(self.to_bytes())


def roundtrip_ok(blob):
    """True if TagDoc writes `blob` back byte-identical."""
    try:
        return TagDoc(blob).to_bytes() == bytes(blob)
    except TagfileError:
        return False
