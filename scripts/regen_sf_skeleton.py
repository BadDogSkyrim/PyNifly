"""Rebuild the shipped Starfield reference skeleton from the vanilla one, in game units.

    python scripts/regen_sf_skeleton.py [--vanilla PATH] [--out PATH]

Starfield is the one game that mixes unit systems. It ships `skeleton.nif` and
`skeleton_facebones.nif` with their NiNode transforms in Havok metres -- a whole human
spans 1.74 of them -- while the `.mesh` geometry those bones skin, the `BSSkinBoneData`
binds, and every other nif's node transforms are in Bethesda game units.

A reference skeleton supplies bone REST positions for that geometry, so it has to be in
the geometry's units. Ours is therefore the vanilla skeleton scaled by
`HAVOC_SCALE_FACTOR`, which is why it does not match the game file byte for byte. That
difference is deliberate; see TEST_SF_REFERENCE_SKELETON, which pins it.

The copy shipped before 2026-09-22 was built with 69.96900 where the codebase's constant
is 69.99125 -- a 0.03% discrepancy with no explanation behind it. This script exists so
the file can be regenerated from one number instead of an unrecorded one.

Only the node hierarchy is reproduced: names, parenting and transforms, which is all a
reference skeleton is read for. The Havok ragdoll rig in the vanilla file is dropped.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'io_scene_nifly'))

from pyn.pynifly import NifFile                      # noqa: E402
from pyn.nifconstants import HAVOC_SCALE_FACTOR      # noqa: E402

DEFAULT_VANILLA = os.path.join(
    r'C:\Modding\Starfield\00StarfieldAssets',
    r'meshes\actors\human\characterassets\skeleton.nif')
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'io_scene_nifly', 'skeletons', 'SF', 'skeleton.nif')


def ordered_nodes(nif):
    """Every node, parents before children, so add_node can resolve a parent by name."""
    out, seen = [], set()

    def emit(node):
        if node.name in seen:
            return
        parent = getattr(node, 'parent', None)
        if parent is not None and parent.name != node.name:
            emit(parent)
        seen.add(node.name)
        out.append(node)

    for n in nif.nodes.values():
        emit(n)
    return out


def regenerate(vanilla_path, out_path, scale=HAVOC_SCALE_FACTOR):
    src = NifFile(vanilla_path)
    out = NifFile()
    out.initialize('SF', out_path, 'NiNode', src.rootName)

    written = 0
    for node in ordered_nodes(src):
        if node.name == src.rootName:
            continue                     # the root comes from initialize()
        xf = node.transform.copy()
        # The LOCAL translation is scaled, so the whole hierarchy lands scaled. Rotation
        # and the transform's own scale component are unitless -- leave them alone.
        xf.translation = tuple(c * scale for c in node.transform.translation)
        out.add_node(node.name, xf, node.parent.name if node.parent else src.rootName)
        written += 1

    out.save()
    return src, written


def verify(vanilla_path, out_path, scale=HAVOC_SCALE_FACTOR):
    """Check the result really is the vanilla skeleton and nothing but, times `scale`."""
    chk, van = NifFile(out_path), NifFile(vanilla_path)
    problems = []

    missing, extra = set(van.nodes) - set(chk.nodes), set(chk.nodes) - set(van.nodes)
    if missing or extra:
        problems.append(f"node set differs: missing {sorted(missing)[:5]}, "
                        f"extra {sorted(extra)[:5]}")

    worst, worst_name = 0.0, None
    for name, v in van.nodes.items():
        if name not in chk.nodes:
            continue
        a = chk.nodes[name].global_transform.translation
        b = v.global_transform.translation
        for i in range(3):
            d = abs(a[i] - b[i] * scale)
            if d > worst:
                worst, worst_name = d, name
    if worst > 0.001:
        problems.append(f"{worst_name} is {worst:.5f} off vanilla*{scale}")

    def parent_of(nif, n):
        p = nif.nodes[n].parent
        return p.name if p else None

    bad = [n for n in van.nodes
           if n in chk.nodes and parent_of(chk, n) != parent_of(van, n)]
    if bad:
        problems.append(f"{len(bad)} parent mismatches, e.g. {bad[:5]}")

    return len(chk.nodes), worst, worst_name, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vanilla', default=DEFAULT_VANILLA,
                    help="the game's own skeleton.nif (default: the unpacked assets tree)")
    ap.add_argument('--out', default=DEFAULT_OUT,
                    help="where to write it (default: the shipped reference skeleton)")
    ap.add_argument('--dry-run', action='store_true',
                    help="write to <out>.new instead of replacing the shipped file")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.vanilla):
        print(f"Not found: {args.vanilla}", file=sys.stderr)
        return 2
    out_path = args.out + '.new' if args.dry_run else args.out

    src, written = regenerate(args.vanilla, out_path)
    print(f"{src.rootName!r}: {len(src.nodes)} nodes in, {written} written, "
          f"scaled by {HAVOC_SCALE_FACTOR}")
    print(f"  -> {out_path} ({os.path.getsize(out_path):,} bytes)")

    n, worst, worst_name, problems = verify(args.vanilla, out_path)
    for p in problems:
        print(f"  FAILED: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"  verified: {n} nodes, parenting intact, worst deviation "
          f"{worst:.6f} ({worst_name})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
