"""Compress a tree of PNG texture sources into DDS, picking the format from the filename suffix.

    python scripts/sf_texconv.py "C:\\...\\textures\\actors\\FSFCanine"
    python scripts/sf_texconv.py TREE --dry-run
    python scripts/sf_texconv.py TREE --color-format BC3_UNORM --force
    python scripts/sf_texconv.py TREE --size 1k

    *_color.png      -> BC7_UNORM_SRGB  (change with --color-format)
    *_normal.png     -> BC5_SNORM
    *_ao.png         -> BC4_UNORM
    *_rough.png      -> BC4_UNORM
    *_mask.png       -> BC4_UNORM
    *_derm_color.png -> R8G8B8A8_UNORM_SRGB, one mip (uncompressed; the game insists)

Under a `chargen` or `postblenddetails` folder the face-customization textures are
uncompressed, as all 748 vanilla ones are, and their headers are rewritten to match Bethesda's:

    *_color.png      -> R8G8B8A8_UNORM_SRGB, one mip
    *_normal.png     -> R8G8B8A8_SNORM, one mip, legacy (non-DX10) header
    *_ao/_rough/_mask.png -> R8_UNORM, one mip, legacy header

A face normal must not be BC5 there: BC5 keeps only X and Y and has the shader rebuild Z, so
any part of the map where x^2+y^2 > 1 loses Z and flattens. Vanilla's signed format stores it.

Suffixes match regardless of case. Each .dds is written next to its .png, which is left alone.
Other PNGs are ignored. A .dds that is already newer than its .png is skipped unless --force,
unless --size asks for dimensions it doesn't have, or unless it was written in a format these
rules no longer choose.

--size caps the longest side of the output at 512, 1k, 2k or 4k. It only ever shrinks: a source
already within the cap is converted at its own size. Aspect ratio is preserved.

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

# --size takes the names a texture artist uses, not pixel counts.
SIZES = {'512': 512, '1k': 1024, '2k': 2048, '4k': 4096}

# How one kind of texture is made: the DDS format (None means "the colour format", which the user
# can choose), the extra texconv arguments it needs, whether its header is rewritten to Bethesda's
# conventions afterwards, and whether it gets a DX10 header at all.
Spec = collections.namedtuple('Spec', 'format args vanilla_header dx10')
Spec.__new__.__defaults__ = ([], False, True)

# Filename suffix -> Spec. Longer suffixes come first: '_derm_color' also ends with '_color',
# and the first match wins.
SUFFIX_FORMATS = {
    # Dermaesthetic skin-tone overlays are the one face texture Starfield will not take
    # compressed, wherever they live. (Under postblenddetails the folder rule below says the
    # same thing; this catches a derm texture kept anywhere else.)
    '_derm_color': Spec('R8G8B8A8_UNORM_SRGB', ['-m', '1'], vanilla_header=True),
    '_color': Spec(None),
    '_normal': Spec('BC5_SNORM'),
    '_ao': Spec('BC4_UNORM'),
    '_rough': Spec('BC4_UNORM'),
    '_mask': Spec('BC4_UNORM'),
}

# Face-customization textures are authored uncompressed, and that holds for the WHOLE chargen
# face tree, not just postblenddetails. Census of all 748 vanilla .dds under
# textures\actors\human\faces\chargen, every one 1024x1024 with a single mip:
#
#                        chargen/    postblenddetails/
#   _color                    198                   61   DX10 R8G8B8A8_UNORM_SRGB
#   _derm_color                 -                   84   the same
#   _normal                    22                   40   LEGACY 32bpp, DDPF_BUMPDUDV (signed)
#   _ao                        22                   40   LEGACY 8bpp, DDPF_RGB -- R8 by another name
#   _rough                     22                   39   the same legacy 8bpp
#   _mask                      10                  179   the same legacy 8bpp
#   *_mask_1                    -                    5   DX10 BC4_UNORM, the only compressed files
#
# _normal is the one that bites. BC5 stores X and Y only and makes the shader rebuild Z as
# sqrt(1-x^2-y^2), so a map whose x^2+y^2 exceeds 1 anywhere loses Z there and the normal
# flattens into the tangent plane. Vanilla's signed 32bpp format stores Z outright and doesn't
# care. We shipped BC5 here until 2026-09-23.
FACE_DIRS = ('chargen', 'postblenddetails')
FACE_FORMATS = {
    # Longest first: '_derm_color' also ends with '_color'. Both land on the same spec here,
    # but the ordering is load-bearing in SUFFIX_FORMATS and worth keeping consistent.
    '_derm_color': Spec('R8G8B8A8_UNORM_SRGB', ['-m', '1'], vanilla_header=True),
    '_color': Spec('R8G8B8A8_UNORM_SRGB', ['-m', '1'], vanilla_header=True),
    # Vanilla writes these with a LEGACY header, so no -dx10. texconv's own legacy output
    # already carries the right pixel format and channel masks for both; what differs is the
    # size/caps bookkeeping, which match_vanilla_header settles.
    '_normal': Spec('R8G8B8A8_SNORM', ['-m', '1'], vanilla_header=True, dx10=False),
    '_ao': Spec('R8_UNORM', ['-m', '1'], vanilla_header=True, dx10=False),
    '_rough': Spec('R8_UNORM', ['-m', '1'], vanilla_header=True, dx10=False),
    '_mask': Spec('R8_UNORM', ['-m', '1'], vanilla_header=True, dx10=False),
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
DDPF_RGB = 0x40                # vanilla's 8bpp masks say RGB where texconv says LUMINANCE (0x20000)
DDPF_BUMPDUDV = 0x80000        # the legacy "these channels are signed" flag, on face normals
OFF_FLAGS, OFF_HEIGHT, OFF_WIDTH, OFF_LINEAR, OFF_DEPTH = 8, 12, 16, 20, 24
OFF_PF_FLAGS, OFF_FOURCC, OFF_BITCOUNT, OFF_RMASK = 80, 84, 88, 92
OFF_CAPS, OFF_DXGI, OFF_ALPHA_MODE = 108, 128, 144
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


def dds_size(path):
    """(width, height) from a DDS header, or None if it can't be read as one."""
    try:
        with open(path, 'rb') as f:
            head = f.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != DDS_MAGIC:
        return None
    height, width = struct.unpack_from('<2I', head, OFF_HEIGHT)
    return width, height


# Enough to recognise what an existing .dds was written as. Only used to notice that the
# rules have changed under a file; a format not listed here simply isn't checked.
DXGI_BY_NAME = {
    'R8G8B8A8_UNORM': 28, 'R8G8B8A8_UNORM_SRGB': 29, 'R8G8B8A8_SNORM': 31,
    'R8_UNORM': 61, 'BC1_UNORM': 71, 'BC3_UNORM': 77, 'BC4_UNORM': 80,
    'BC5_SNORM': 84, 'BC7_UNORM': 98, 'BC7_UNORM_SRGB': 99,
}
LEGACY_BITS = {'R8_UNORM': 8, 'R8G8B8A8_SNORM': 32}


def dds_encoding(path):
    """('dx10', dxgi) or ('legacy', bits) for an existing DDS, or None if it can't be read."""
    try:
        with open(path, 'rb') as f:
            head = f.read(148)
    except OSError:
        return None
    if len(head) < 148 or head[:4] != DDS_MAGIC:
        return None
    if bytes(head[OFF_FOURCC:OFF_FOURCC + 4]) == b'DX10':
        return ('dx10', struct.unpack_from('<I', head, OFF_DXGI)[0])
    return ('legacy', struct.unpack_from('<I', head, OFF_BITCOUNT)[0])


def wanted_encoding(fmt, spec):
    """What dds_encoding should report for a file we are about to write, or None when we
    can't say -- an arbitrary --color-format, for instance."""
    if spec.dx10:
        dxgi = DXGI_BY_NAME.get(fmt)
        return ('dx10', dxgi) if dxgi is not None else None
    bits = LEGACY_BITS.get(fmt)
    return ('legacy', bits) if bits is not None else None


def capped_size(size, limit):
    """`size` with its longest side brought down to `limit`, or `size` unchanged when it already
    fits (or when there is no limit). Aspect ratio is preserved, and each side is rounded down to
    a multiple of 4 so a block-compressed format still gets whole blocks."""
    if limit is None or max(size) <= limit:
        return size
    scale = limit / max(size)
    return tuple(max(4, round(n * scale) // 4 * 4) for n in size)


def texture_format(path, color_format):
    """(DDS format, Spec) for a PNG by its suffix and where it lives, or None if it isn't one we
    convert. A chargen or postblenddetails folder anywhere in the path picks the uncompressed
    face rules; everything else gets the general BCn ones."""
    folder, filename = os.path.split(path)
    stem, ext = os.path.splitext(filename)
    if ext.lower() != '.png':
        return None
    stem = stem.lower()
    parts = folder.lower().replace('\\', '/').split('/')
    in_face_tree = any(d in parts for d in FACE_DIRS)
    tables = ([FACE_FORMATS] if in_face_tree else []) + [SUFFIX_FORMATS]
    for table in tables:
        for suffix, spec in table.items():
            if stem.endswith(suffix):
                return (spec.format or color_format, spec)
    return None


def match_vanilla_header(path):
    """Rewrite an uncompressed DDS header in place to Bethesda's conventions. Returns None on
    success, or a reason the file was left alone.

    Only the header's DESCRIPTION of the texture changes -- not one pixel moves. The size field
    becomes the whole image (Bethesda writes a linear size where texconv writes one row's pitch),
    and the caps say COMPLEX|MIPMAP as vanilla does even for a single-mip texture.

    Two shapes are handled, both measured against vanilla: a DX10 R8G8B8A8_UNORM_SRGB colour
    layer (4 bytes a pixel), and a legacy-header 8bpp mask (1 byte a pixel), whose pixel-format
    flags also move from texconv's LUMINANCE to vanilla's RGB. Anything else is left alone --
    the byte layout below is only right for a format it has been checked against."""
    with open(path, 'r+b') as f:
        head = bytearray(f.read(148))
        if len(head) < 148 or head[:4] != DDS_MAGIC:
            return "not a DDS"
        height, width = struct.unpack_from('<2I', head, OFF_HEIGHT)
        pf_flags, = struct.unpack_from('<I', head, OFF_PF_FLAGS)
        fourcc = bytes(head[OFF_FOURCC:OFF_FOURCC + 4])
        bitcount, rmask = struct.unpack_from('<2I', head, OFF_BITCOUNT)
        if fourcc == b'DX10':
            dxgi, = struct.unpack_from('<I', head, OFF_DXGI)
            if dxgi != DXGI_R8G8B8A8_UNORM_SRGB:
                return f"unexpected DXGI format {dxgi}"
            bpp = 4
            struct.pack_into('<I', head, OFF_ALPHA_MODE, VANILLA_ALPHA_MODE)
        elif fourcc == b'\0\0\0\0' and bitcount == 8 and rmask == 0xFF:
            bpp = 1
            struct.pack_into('<I', head, OFF_PF_FLAGS, DDPF_RGB)
        elif fourcc == b'\0\0\0\0' and bitcount == 32 and rmask == 0xFF \
                and pf_flags == DDPF_BUMPDUDV:
            # A face normal: legacy 32bpp signed. texconv already writes DDPF_BUMPDUDV and the
            # same channel masks vanilla does, so unlike the 8bpp masks the pixel format is
            # left exactly as it is -- rewriting it to DDPF_RGB would discard the one flag
            # saying these values are signed.
            bpp = 4
        else:
            return f"unhandled pixel format (fourcc {fourcc!r}, {bitcount}bpp, flags {pf_flags:#x})"
        struct.pack_into('<I', head, OFF_FLAGS, VANILLA_FLAGS)
        struct.pack_into('<I', head, OFF_LINEAR, width * height * bpp)
        struct.pack_into('<I', head, OFF_DEPTH, VANILLA_DEPTH)
        struct.pack_into('<I', head, OFF_CAPS, VANILLA_CAPS)
        f.seek(0)
        f.write(head)
    return None


def plan(root, color_format, force, limit=None):
    """Walk the tree. Returns (jobs, skipped): jobs are (png, dds, format, spec, args); skipped
    are (png, reason)."""
    jobs, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            png = os.path.join(dirpath, name)
            found = texture_format(png, color_format)
            if not found:
                continue
            fmt, spec = found
            dds = os.path.splitext(png)[0] + '.dds'
            size = png_size(png)
            if size is None:
                skipped.append((png, "not a valid PNG"))
                continue
            out_size = capped_size(size, limit)
            if out_size[0] % 4 or out_size[1] % 4:
                skipped.append((png, f"{out_size[0]}x{out_size[1]} is not a multiple of 4"))
                continue
            # A .dds that predates its .png is stale, and so is one that --size no longer asks
            # for, and so is one written in a format we no longer choose -- otherwise a rule
            # change here silently leaves every existing texture alone. An unreadable one, or
            # a format we can't name, is left to the mtime alone as it always was.
            want_enc = wanted_encoding(fmt, spec)
            if not force and os.path.exists(dds) \
                    and os.path.getmtime(dds) >= os.path.getmtime(png) \
                    and dds_size(dds) in (None, out_size) \
                    and (want_enc is None or dds_encoding(dds) in (None, want_enc)):
                skipped.append((png, "up to date"))
                continue
            args = list(spec.args)
            if out_size != size:
                args += ['-w', str(out_size[0]), '-h', str(out_size[1])]
            jobs.append((png, dds, fmt, spec, args))
    return jobs, skipped


def convert(texconv, jobs):
    """Run texconv over the jobs, batched by folder and by the arguments they need. Returns the
    failed jobs."""
    groups = {}
    for job in jobs:
        png, _, fmt, spec, args = job
        groups.setdefault((os.path.dirname(png), fmt, tuple(args), spec.dx10), []).append(job)

    failed = []
    for (folder, fmt, extra, dx10), group in groups.items():
        for i in range(0, len(group), BATCH):
            batch = group[i:i + BATCH]
            before = {dds: os.path.getmtime(dds) if os.path.exists(dds) else None
                      for _, dds, _, _, _ in batch}
            # -srgb marks input and output alike as sRGB, so texconv does no gamma conversion
            # in either direction. Without it texconv honours a PNG's sRGB chunk: a tagged
            # grey 128 became 55 in BC4, and an untagged 128 became 189 in an _SRGB format.
            # -dx10 matches vanilla for everything except the uncompressed 8bpp masks, which
            # vanilla writes with a legacy header; texconv otherwise writes legacy FourCCs ('BC5S').
            cmd = [texconv, '-nologo', '-y', *(['-dx10'] if dx10 else []),
                   '-srgb', '-f', fmt, *extra, '-o', folder]
            cmd += [png for png, _, _, _, _ in batch]
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Judge by what landed on disk, not the exit code: one bad file in a batch
            # shouldn't hide the others.
            for job in batch:
                _, dds, _, spec, _ = job
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
    ap.add_argument('--size', type=str.lower, choices=list(SIZES), metavar='SIZE',
                    help=f"cap the longest side of the output at {', '.join(SIZES)} "
                         f"(shrinks only; aspect ratio preserved)")
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

    jobs, skipped = plan(args.root, args.color_format, args.force, SIZES.get(args.size))
    for png, reason in skipped:
        if reason != "up to date":
            print(f"  skip  {shown(png)}: {reason}", file=sys.stderr)
    n_current = sum(1 for _, reason in skipped if reason == "up to date")

    if args.dry_run:
        for png, dds, fmt, spec, job_args in jobs:
            extras = list(job_args) + (['vanilla header'] if spec.vanilla_header else [])
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
    for png, _, fmt, _, _ in failed:
        print(f"  FAILED {fmt} {shown(png)}", file=sys.stderr)
    print(f"{len(jobs) - len(failed)} converted, {len(failed)} failed, {n_current} up to date, "
          f"{len(skipped) - n_current} skipped")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
