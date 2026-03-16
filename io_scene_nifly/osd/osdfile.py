"""Reader for BodySlide OSD (Outfit Studio Data) files.

OSD binary format:
    Header:
        4 bytes: magic (\\x00DSO or OSD\\0)
        4 bytes: version (uint32)
        4 bytes: data count (uint32) — number of entries (one per shape+slider combo)

    Per entry:
        1 byte:  name length (uint8)
        N bytes: compound name (shape name + slider name concatenated, no separator)
        2 bytes: diff count (uint16)
        diff_count * 14 bytes: array of DiffStruct

    DiffStruct (14 bytes):
        2 bytes: vertex index (uint16)
        12 bytes: x, y, z offset (3 * float32)

The compound names must be split using known shape names from context (e.g.
matching against selected Blender objects).
"""

import struct
from pathlib import Path


class OSDFile:
    """Reads and stores OSD morph data.

    After reading, self.entries is a list of (compound_name, diffs) tuples.
    Call split_entries(shape_names) to group them into the shapes dict.
    """

    def __init__(self):
        self.entries = []  # [(compound_name, diffs), ...]
        self.shapes = {}   # {shape_name: {slider_name: diffs, ...}, ...}
        self.is_valid = False
        self.version = 0

    @classmethod
    def from_file(cls, filepath):
        """Read an OSD file and return an OSDFile instance."""
        osd = cls()
        with open(str(filepath), 'rb') as f:
            osd.read(f)
        return osd

    def read(self, file):
        """Parse OSD binary data from an open file handle."""
        magic = file.read(4)
        if magic not in (b'\x00DSO', b'OSD\x00'):
            self.is_valid = False
            return

        self.version = struct.unpack('<I', file.read(4))[0]
        data_count = struct.unpack('<I', file.read(4))[0]

        for _ in range(data_count):
            name_len = struct.unpack('<B', file.read(1))[0]
            compound_name = file.read(name_len).decode('utf-8', errors='replace')

            diff_count = struct.unpack('<H', file.read(2))[0]

            diffs = []
            for _ in range(diff_count):
                idx, dx, dy, dz = struct.unpack('<H3f', file.read(14))
                if abs(dx) > 1e-7 or abs(dy) > 1e-7 or abs(dz) > 1e-7:
                    diffs.append([idx, (dx, dy, dz)])

            self.entries.append((compound_name, diffs))

        self.is_valid = True

    def split_entries(self, shape_names):
        """Split compound entry names using known shape names.

        For each entry, the compound name is matched against the given shape
        names. The longest matching prefix is the shape name; the remainder
        is the slider name.

        Populates self.shapes: {shape_name: {slider_name: diffs, ...}, ...}
        """
        # Sort by length descending so longer names match first
        sorted_names = sorted(shape_names, key=len, reverse=True)

        for compound, diffs in self.entries:
            matched = False
            for name in sorted_names:
                if compound.startswith(name):
                    slider = compound[len(name):]
                    if name not in self.shapes:
                        self.shapes[name] = {}
                    self.shapes[name][slider] = diffs
                    matched = True
                    break
            if not matched:
                # Can't split — store under the full compound name
                if compound not in self.shapes:
                    self.shapes[compound] = {}
                self.shapes[compound][''] = diffs


    def set_morphs(self, shape_name, morphdict, base_verts):
        """Add morph data for a shape from export.

        morphdict: {slider_name: [vert_positions, ...], ...}
            where vert_positions is a list parallel to base_verts.
        base_verts: list of (x, y, z) base vertex positions.

        Converts absolute positions to sparse offsets and stores them.
        """
        if shape_name not in self.shapes:
            self.shapes[shape_name] = {}

        for slider_name, morph_verts in morphdict.items():
            diffs = []
            for i, (mv, bv) in enumerate(zip(morph_verts, base_verts)):
                dx = mv[0] - bv[0]
                dy = mv[1] - bv[1]
                dz = mv[2] - bv[2]
                if abs(dx) > 1e-7 or abs(dy) > 1e-7 or abs(dz) > 1e-7:
                    diffs.append([i, (dx, dy, dz)])
            self.shapes[shape_name][slider_name] = diffs

    def write(self, filepath):
        """Write OSD binary data to a file."""
        # Count total entries (one per shape+slider combo)
        entries = []
        for shape_name, sliders in self.shapes.items():
            for slider_name, diffs in sliders.items():
                compound = shape_name + slider_name
                entries.append((compound, diffs))

        with open(str(filepath), 'wb') as f:
            # Header
            f.write(b'\x00DSO')
            f.write(struct.pack('<I', 1))  # version
            f.write(struct.pack('<I', len(entries)))

            for compound, diffs in entries:
                name_bytes = compound.encode('utf-8')
                f.write(struct.pack('<B', len(name_bytes)))
                f.write(name_bytes)
                f.write(struct.pack('<H', len(diffs)))
                for idx, (dx, dy, dz) in diffs:
                    f.write(struct.pack('<H3f', idx, dx, dy, dz))


def is_osd(filepath):
    """Check if a file is an OSD file by reading the magic bytes."""
    with open(str(filepath), 'rb') as f:
        magic = f.read(4)
        return magic in (b'\x00DSO', b'OSD\x00')
