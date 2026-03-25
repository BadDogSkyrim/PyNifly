"""MOPP quality benchmark — compares vanilla vs PyNifly MOPP compilation.

Reads vanilla NIFs, measures false-positive rate and code size for both
the original MOPP bytecode and our compiled version. Outputs a CSV.

Usage:
    cd PyNifly
    python tests/mopp_benchmark.py [--nifs-dir DIR] [--max N] [--samples N] [--out FILE]

Defaults:
    --nifs-dir  C:/Modding/SkyrimSEAssets/00 Vanilla Assets/meshes/architecture
    --max       40
    --samples   500
    --out       C:/tmp/mopp_quality_comparison.csv
"""

import sys
import os
import glob
import csv
import argparse
import statistics

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pyn_parent = os.path.join(_script_dir, '..')
if _pyn_parent not in sys.path:
    sys.path.insert(0, _pyn_parent)

from pyn.pynifly import NifFile
from pyn.mopp_compiler import compile_mopp, _derive_largest_dim
from scripts.mopp_verifier import verify_tightness


def benchmark_nifs(nifs_dir, max_nifs=40, num_samples=500, seed=42):
    """Run MOPP quality comparison on vanilla NIFs.

    Returns list of dicts with per-NIF results.
    """
    results = []
    count = 0
    for f in sorted(glob.glob(os.path.join(nifs_dir, '**', '*.nif'), recursive=True)):
        if count >= max_nifs:
            break
        try:
            nif = NifFile(f)
            for node in nif.nodes.values():
                co = node.collision_object
                if not (co and co.body and co.body.shape
                        and hasattr(co.body.shape, 'child')):
                    continue
                mopp_shape = co.body.shape
                child = mopp_shape.child
                if child.blockname != 'bhkCompressedMeshShape':
                    continue

                verts = child.vertices
                tris = child.triangles
                if len(tris) < 10:
                    continue

                vanilla_bytes, origin, scale = mopp_shape.mopp_data
                if len(vanilla_bytes) == 0:
                    continue
                vanilla_ld = _derive_largest_dim(vanilla_bytes, origin)
                if vanilla_ld is None or vanilla_ld <= 0:
                    continue

                # Vanilla tightness
                vanilla_avg, _ = verify_tightness(
                    vanilla_bytes, origin, vanilla_ld, verts, tris,
                    radius=0.005, num_samples=num_samples, seed=seed)

                # Our compilation
                output_ids = list(range(len(tris)))
                our_bytes, our_origin, our_scale = compile_mopp(
                    verts, tris, radius=0.005, output_ids=output_ids)
                our_ld = _derive_largest_dim(our_bytes, our_origin)
                if our_ld is None or our_ld <= 0:
                    continue

                our_avg, _ = verify_tightness(
                    our_bytes, our_origin, our_ld, verts, tris,
                    radius=0.005, num_samples=num_samples, seed=seed)

                short = os.path.relpath(f, nifs_dir)
                row = {
                    'nif': short,
                    'tris': len(tris),
                    'verts': len(verts),
                    'vanilla_fp': vanilla_avg,
                    'ours_fp': our_avg,
                    'vanilla_size': len(vanilla_bytes),
                    'ours_size': len(our_bytes),
                }
                results.append(row)
                print(f'{short}: tris={len(tris):4d}  '
                      f'vanilla={vanilla_avg:5.2f}  ours={our_avg:5.2f}  '
                      f'vsize={len(vanilla_bytes):5d}  osize={len(our_bytes):5d}')
                count += 1
                break
        except Exception:
            pass
    return results


def print_summary(results):
    if not results:
        print('No results.')
        return
    v_fp = [r['vanilla_fp'] for r in results]
    o_fp = [r['ours_fp'] for r in results]
    v_sz = [r['vanilla_size'] for r in results]
    o_sz = [r['ours_size'] for r in results]

    print(f'\n{"="*70}')
    print(f'Summary ({len(results)} meshes):')
    print(f'  Vanilla FP rate: mean={statistics.mean(v_fp):.3f}, '
          f'stdev={statistics.stdev(v_fp) if len(v_fp) > 1 else 0:.3f}')
    print(f'  Ours    FP rate: mean={statistics.mean(o_fp):.3f}, '
          f'stdev={statistics.stdev(o_fp) if len(o_fp) > 1 else 0:.3f}')
    print(f'  Vanilla size:    mean={statistics.mean(v_sz):.0f} bytes')
    print(f'  Ours    size:    mean={statistics.mean(o_sz):.0f} bytes '
          f'({statistics.mean(o_sz)/statistics.mean(v_sz):.2f}x)')


def write_csv(results, outpath):
    with open(outpath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            'nif', 'tris', 'verts', 'vanilla_fp', 'ours_fp',
            'vanilla_size', 'ours_size'])
        writer.writeheader()
        writer.writerows(results)
    print(f'\nWrote {len(results)} rows to {outpath}')


def main():
    parser = argparse.ArgumentParser(description='MOPP quality benchmark')
    parser.add_argument('--nifs-dir',
        default=r'C:/Modding/SkyrimSEAssets/00 Vanilla Assets/meshes/architecture')
    parser.add_argument('--max', type=int, default=40)
    parser.add_argument('--samples', type=int, default=500)
    parser.add_argument('--out', default=r'C:/tmp/mopp_quality_comparison.csv')
    args = parser.parse_args()

    results = benchmark_nifs(args.nifs_dir, max_nifs=args.max,
                             num_samples=args.samples)
    write_csv(results, args.out)
    print_summary(results)


if __name__ == '__main__':
    main()
