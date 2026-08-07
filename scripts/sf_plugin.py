"""Minimal Starfield plugin (TES4) reader.

Enough to audit records -- it does not attempt to decode every field, only to walk the
record/group tree and hand back subrecords as raw bytes.

Starfield specifics: 24-byte record header, 24-byte GRUP header, 6-byte subrecord header,
zlib-compressed record data behind flag 0x40000, and an XXXX subrecord that overrides the
size of the subrecord following it (for payloads over 64K).
"""

import struct
import zlib

REC_HDR = struct.Struct('<4sIIIII')     # type, dataSize, flags, formID, vcs1, vcs2
GRP_HDR = struct.Struct('<4sI4sIII')    # 'GRUP', groupSize, label, groupType, stamp, unknown
SUB_HDR = struct.Struct('<4sH')         # type, dataSize

COMPRESSED = 0x00040000


def _decode(data):
    """A zero-terminated plugin string as text."""
    return data.split(b'\0')[0].decode('utf-8', 'replace')


class Record:
    """One plugin record, with its subrecords kept in file order."""

    def __init__(self, sig, formid, flags, data):
        self.sig = sig.decode('latin-1')
        self.formid = formid
        self.flags = flags
        self.subs = list(_subrecords(data))

    def get(self, sig):
        """Payload of the first subrecord with this signature, or None."""
        for s, d in self.subs:
            if s == sig:
                return d
        return None

    def all(self, sig):
        """Payloads of every subrecord with this signature, in file order."""
        return [d for s, d in self.subs if s == sig]

    def string(self, sig):
        d = self.get(sig)
        return _decode(d) if d is not None else None

    def strings(self, sig):
        return [_decode(d) for d in self.all(sig)]

    def formid_of(self, sig):
        d = self.get(sig)
        return struct.unpack('<I', d)[0] if d is not None and len(d) == 4 else None

    def formids(self, sig):
        return [struct.unpack('<I', d)[0] for d in self.all(sig) if len(d) == 4]

    @property
    def edid(self):
        return self.string('EDID')

    def __repr__(self):
        return f"<{self.sig} {self.formid:08X} {self.edid!r}>"


def _subrecords(data):
    """Yield (signature, payload), honouring XXXX size overrides."""
    p, override = 0, None
    while p + 6 <= len(data):
        sig, size = SUB_HDR.unpack_from(data, p)
        p += 6
        sig = sig.decode('latin-1')
        if sig == 'XXXX':
            override = struct.unpack_from('<I', data, p)[0]
            p += size
            continue
        if override is not None:
            size, override = override, None
        yield sig, data[p:p + size]
        p += size


def _walk(buf, p, end, out):
    while p + 24 <= end:
        if buf[p:p + 4] == b'GRUP':
            _, gsize, _label, _gtype, _, _ = GRP_HDR.unpack_from(buf, p)
            if gsize < 24:
                break
            _walk(buf, p + 24, min(p + gsize, end), out)
            p += gsize
        else:
            sig, dsize, flags, formid, _, _ = REC_HDR.unpack_from(buf, p)
            data = buf[p + 24: p + 24 + dsize]
            if flags & COMPRESSED and len(data) >= 4:
                try:
                    data = zlib.decompress(data[4:])
                except zlib.error:
                    pass
            out.append(Record(sig, formid, flags, data))
            p += 24 + dsize
    return out


def load(path):
    """Every record in the plugin, groups flattened away."""
    with open(path, 'rb') as f:
        buf = f.read()
    return _walk(buf, 0, len(buf), [])


if __name__ == '__main__':
    import sys
    from collections import Counter
    recs = load(sys.argv[1])
    print(f"{len(recs)} records")
    for sig, n in Counter(r.sig for r in recs).most_common():
        print(f"  {sig} x{n}")
    print()
    for r in recs:
        print(' ', r)
