"""Starfield file formats read without the DLL: the nif header's string table, a .mesh's
vertex count, and the names inside a BA2. For scripts that need a quick look at a file, not a
full load."""

import struct


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
