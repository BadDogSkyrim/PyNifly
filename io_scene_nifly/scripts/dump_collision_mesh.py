"""Export collision mesh geometry as OBJ for visualization.

Usage: python dump_collision_mesh.py <input_nif> <output_obj>

Exports the bhkCompressedMeshShape chunk triangles as an OBJ file
with correct winding, so you can inspect face orientation in Blender.
"""
import sys, os

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pyn_parent = os.path.join(_script_dir, '..')
if _pyn_parent not in sys.path:
    sys.path.insert(0, _pyn_parent)

from pyn.pynifly import NifFile


def export_collision_obj(nif_path, obj_path):
    f = NifFile(nif_path)
    co = f.rootNode.collision_object
    if not co:
        print("No collision object")
        return

    body = co.body
    shape = body.shape
    child = shape.child

    verts = child.vertices
    tris = child.triangles

    print(f"Collision: {len(verts)} verts, {len(tris)} tris")

    with open(obj_path, 'w') as out:
        out.write(f"# Collision mesh from {os.path.basename(nif_path)}\n")
        out.write(f"# {len(verts)} vertices, {len(tris)} triangles\n\n")

        for v in verts:
            out.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        out.write("\n")

        for a, b, c in tris:
            # OBJ is 1-indexed
            out.write(f"f {a+1} {b+1} {c+1}\n")

    print(f"Wrote {obj_path}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python dump_collision_mesh.py <input_nif> <output_obj>")
        sys.exit(1)
    export_collision_obj(sys.argv[1], sys.argv[2])
