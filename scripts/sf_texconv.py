"""Compress a tree of PNG texture sources into DDS, picking the format from the filename suffix.

    python scripts/sf_texconv.py "C:\\...\\textures\\actors\\FSFCanine"
    python scripts/sf_texconv.py TREE --dry-run
    python scripts/sf_texconv.py TREE --color-format BC3_UNORM --force

    *_derm_color.png -> R8G8B8A8_UNORM_SRGB, one mip (uncompressed; the game insists)
    *_color.png      -> BC7_UNORM_SRGB  (change with --color-format)
    *_normal.png     -> BC5_SNORM
    *_ao.png         -> BC4_UNORM
    *_rough.png      -> BC4_UNORM
    *_mask.png       -> BC4_UNORM

Suffixes match regardless of case. Each .dds is written next to its .png, which is left alone.
Other PNGs are ignored. A .dds that is already newer than its .png is skipped unless --force.

Pixel values go through unchanged -- the texture author is responsible for getting them right
for the game. In particular normal maps are NOT green-flipped: Starfield wants DirectX (-Y)
normals, so a Blender (OpenGL) bake must be flipped before it gets here. The one conversion
that does happen is the one the format requires: BC5_SNORM stores unsigned PNG values remapped
to [-1, 1], so a flat 128 becomes 0.

The work is done by Microsoft's texconv (DirectXTex), found via --texconv, the TEXCONV
environment variable, PATH, or a copy under C:\\Modding\\Tools.

Exit code is 1 if any texture failed to convert.
"""

import argparse
import collections
import os
import shutil
import struct
import subprocess
import sys

DEFAULT_COLOR_FORMAT = 'BC7_UNORM_SRGB'

# How one kind of texture is made: the DDS format (None means "the colour format", which the user
# can choose), the extra texconv arguments it needs, and whether its header is rewritten to
# Bethesda's conventions afterwards.
Spec = collections.namedtuple('Spec', 'format args vanilla_header')
Spec.__new__.__defaults__ = ([], False)

# Filename suffix -> Spec. Longer suffixes come first: '_derm_color' also ends with '_color',
# and the first match wins.
SUFFIX_FORMATS = {
    # Dermaesthetic skin-tone overlays are the one face texture Starfield will not take
    # compressed. All 84 vanilla files under
    # textures\actors\human\faces\chargen\postblenddetails\dermaesthetic are UNCOMPRESSED
    # R8G8B8A8_UNORM_SRGB, 1024x1024, with a single mip -- no exceptions, no BC7. So this
    # suffix ignores --color-format, and '-m 1' stops texconv building the mip chain it
    # generates by default.
    '_derm_color': Spec('R8G8B8A8_UNORM_SRGB', ['-m', '1'], vanilla_header=True),
    '_color': Spec(None),
    '_normal': Spec('BC5_SNORM'),
    '_ao': Spec('BC4_UNORM'),
    '_rough': Spec('BC4_UNORM'),
    '_mask': Spec('BC4_UNORM'),
}

# --- Bethesda's DDS header conventions ---------------------------------------------------------
# texconv and Bethesda's own writer describe the same uncompressed texture differently. Both are
# legal DDS and the pixels are identical, but Starfield's dermaesthetic layer chooser rejects
# texconv's version, so a derm texture's header is rewritten to match vanilla byte for byte.
# Measured across all 84 vanilla dermaesthetic files; texconv's values are in brackets.
DDS_MAGIC = b'DDS '
VANILLA_FLAGS = 0xA1007        # CAPS|HEIGHT|WIDTH|PIXELFORMAT|MIPMAPCOUNT|LINEARSIZE  [0x2100F]
VANILLA_CAPS = 0x401008        # COMPLEX|TEXTURE|MIPMAP                                [0x1000]
VANILLA_DEPTH = 0              # [1]
VANILLA_ALPHA_MODE = 0         # DDS_ALPHA_MODE_UNKNOWN                                [1, straight]
OFF_FLAGS, OFF_HEIGHT, OFF_WIDTH, OFF_LINEAR, OFF_DEPTH = 8, 12, 16, 20, 24
OFF_FOURCC, OFF_CAPS, OFF_DXGI, OFF_ALPHA_MODE = 84, 108, 128, 144
DXGI_R8G8B8A8_UNORM_SRGB = 29

FALLBACK_TEXCONV = [
    r'C:\Modding\Tools\[Xmh] Tools\Utils\texconv.exe',
    r'C:\Modding\GitTools\xEdit\Edit Scripts\Texconvx64.exe',
]

# texconv's command line takes many files at once; keep each batch well under the Windows
# command-line limit.
BATCH = 40


def find_texconv(given):
    if given:
        return given if os.path.isfile(given) else None
    for candidate in (os.environ.get('TEXCONV'), shutil.which('texconv'),
                      *FALLBACK_TEXCONV):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def shown(path):
    """A path for display: relative to the cwd when that's possible (not across drives)."""
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


def png_size(path):
    """(width, height) from the PNG's IHDR, or None if it isn't a PNG."""
    with open(path, 'rb') as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', head[16:24])


def texture_format(filename, color_format):
    """(DDS format, Spec) for a PNG by its suffix, or None if it isn't one we convert."""
    stem, ext = os.path.splitext(filename)
    if ext.lower() != '.png':
        return None
    stem = stem.lower()
    for suffix, spec in SUFFIX_FORMATS.items():
        if stem.endswith(suffix):
            return (spec.format or color_format, spec)
    return None


def match_vanilla_header(path):
    """Rewrite an uncompressed DDS header in place to Bethesda's conventions. Returns None on
    success, or a reason the file was left alone.

    Only the header's DESCRIPTION of the texture changes -- not one pixel moves. The size field
    becomes the whole image (Bethesda writes a linear size where texconv writes one row's pitch),
    and the caps say COMPLEX|MIPMAP as vanilla does even for a single-mip texture."""
    with open(path, 'r+b') as f:
        head = bytearray(f.read(148))
        if len(head) < 148 or head[:4] != DDS_MAGIC:
            return "not a DDS"
        if bytes(head[OFF_FOURCC:OFF_FOURCC + 4]) != b'DX10':
            return "not a DX10 header"
        dxgi = struct.unpack_from('<I', head, OFF_DXGI)[0]
        if dxgi != DXGI_R8G8B8A8_UNORM_SRGB:
            # Guard the arithmetic below: the whole-image size is only 4 bytes a pixel for this
            # one format, and it is the only format this fixup was measured against.
            return f"unexpected DXGI format {dxgi}"
        height, width = struct.unpack_from('<2I', head, OFF_HEIGHT)
        struct.pack_into('<I', head, OFF_FLAGS, VANILLA_FLAGS)
        struct.pack_into('<I', head, OFF_LINEAR, width * height * 4)
        struct.pack_into('<I', head, OFF_DEPTH, VANILLA_DEPTH)
        struct.pack_into('<I', head, OFF_CAPS, VANILLA_CAPS)
        struct.pack_into('<I', head, OFF_ALPHA_MODE, VANILLA_ALPHA_MODE)
        f.seek(0)
        f.write(head)
    return None


def plan(root, color_format, force):
    """Walk the tree. Returns (jobs, skipped): jobs are (png, dds, format, spec); skipped are
    (png, reason)."""
    jobs, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            found = texture_format(name, color_format)
            if not found:
                continue
            fmt, spec = found
            png = os.path.join(dirpath, name)
            dds = os.path.splitext(png)[0] + '.dds'
            size = png_size(png)
            if size is None:
                skipped.append((png, "not a valid PNG"))
                continue
            if size[0] % 4 or size[1] % 4:
                skipped.append((png, f"{size[0]}x{size[1]} is not a multiple of 4"))
                continue
            if not force and os.path.exists(dds) \
                    and os.path.getmtime(dds) >= os.path.getmtime(png):
                skipped.append((png, "up to date"))
                continue
            jobs.append((png, dds, fmt, spec))
    return jobs, skipped


def convert(texconv, jobs):
    """Run texconv over the jobs, batched by folder and by the arguments they need. Returns the
    failed jobs."""
    groups = {}
    for job in jobs:
        png, _, fmt, spec = job
        groups.setdefault((os.path.dirname(png), fmt, tuple(spec.args)), []).append(job)

    failed = []
    for (folder, fmt, extra), group in groups.items():
        for i in range(0, len(group), BATCH):
            batch = group[i:i + BATCH]
            before = {dds: os.path.getmtime(dds) if os.path.exists(dds) else None
                      for _, dds, _, _ in batch}
            # -srgb marks input and output alike as sRGB, so texconv does no gamma conversion
            # in either direction. Without it texconv honours a PNG's sRGB chunk: a tagged
            # grey 128 became 55 in BC4, and an untagged 128 became 189 in an _SRGB format.
            # -dx10 matches vanilla; texconv otherwise writes legacy FourCCs ('BC5S').
            cmd = [texconv, '-nologo', '-y', '-dx10', '-srgb', '-f', fmt, *extra, '-o', folder]
            cmd += [png for png, _, _, _ in batch]
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Judge by what landed on disk, not the exit code: one bad file in a batch
            # shouldn't hide the others.
            for job in batch:
                _, dds, _, spec = job
                if os.path.exists(dds) and os.path.getmtime(dds) != before[dds]:
                    note = ''
                    if spec.vanilla_header:
                        problem = match_vanilla_header(dds)
                        note = f"  header NOT matched: {problem}" if problem else "  vanilla header"
                    print(f"  {fmt:<20} {shown(dds)}{note}")
                else:
                    failed.append(job)
            if result.returncode or any(job in failed for job in batch):
                print((result.stdout + result.stderr).strip(), file=sys.stderr)
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root', help="folder tree to walk")
    ap.add_argument('--color-format', default=DEFAULT_COLOR_FORMAT, metavar='FORMAT',
                    help=f"texconv format for *_color (default {DEFAULT_COLOR_FORMAT}; "
                         f"e.g. BC3_UNORM or BC1_UNORM for Skyrim)")
    ap.add_argument('--force', action='store_true',
                    help="convert even when the .dds is newer than the .png")
    ap.add_argument('--dry-run', action='store_true', help="list what would be converted")
    ap.add_argument('--texconv', metavar='PATH', help="texconv.exe to use")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        print(f"Not a folder: {args.root}", file=sys.stderr)
        return 2
    args.color_format = args.color_format.upper()
    # texconv finds the output name by splitting on backslashes only; a forward-slash path
    # like a/b/x.png with -o lands in <o>\a/b/x.dds. abspath normalises the separators.
    args.root = os.path.abspath(args.root)

    jobs, skipped = plan(args.root, args.color_format, args.force)
    for png, reason in skipped:
        if reason != "up to date":
            print(f"  skip  {shown(png)}: {reason}", file=sys.stderr)
    n_current = sum(1 for _, reason in skipped if reason == "up to date")

    if args.dry_run:
        for png, dds, fmt, spec in jobs:
            extras = list(spec.args) + (['vanilla header'] if spec.vanilla_header else [])
            print(f"  {fmt:<20} {shown(png)}{'  ' + ' '.join(extras) if extras else ''}")
        print(f"{len(jobs)} to convert, {n_current} up to date, "
              f"{len(skipped) - n_current} skipped")
        return 0

    if not jobs:
        print(f"Nothing to convert ({n_current} up to date, "
              f"{len(skipped) - n_current} skipped)")
        return 0

    texconv = find_texconv(args.texconv)
    if not texconv:
        print("texconv.exe not found -- pass --texconv or set TEXCONV", file=sys.stderr)
        return 2

    failed = convert(texconv, jobs)
    for png, _, fmt, _ in failed:
        print(f"  FAILED {fmt} {shown(png)}", file=sys.stderr)
    print(f"{len(jobs) - len(failed)} converted, {len(failed)} failed, {n_current} up to date, "
          f"{len(skipped) - n_current} skipped")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
