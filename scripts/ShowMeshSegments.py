"""
ShowMeshSegments.py
-------------------
Blender script: segment the active mesh object using mesh_segment.py and
visualise the result with a face color attribute ("SegmentColor").

Usage:
    1. Select a mesh object in Blender.
    2. Open this script in the Text Editor and click Run Script (or paste into
       the Python Console).
    3. Switch to Vertex Paint or Material Preview mode; change the Viewport
       Color setting to "Attribute" → "SegmentColor" to see the sections.

Notes:
    * The mesh is triangulated in-place by this script (visualization only).
      Work on a copy if you need to preserve the original quad/ngon faces.
    * Requires Blender 4.0+ for color_attributes.
"""

import sys
import colorsys
from pathlib import Path

import bpy
import bmesh

# ---------------------------------------------------------------------------
# Path setup: this script lives in scripts/, project root is one level up.
# ---------------------------------------------------------------------------
_scripts_dir = Path(__file__).resolve().parent
_pyn_dir = _scripts_dir.parent / "io_scene_nifly"
if str(_pyn_dir) not in sys.path:
    sys.path.insert(0, str(_pyn_dir))

from pyn.mesh_segment import segment_mesh

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
ob = bpy.context.active_object
if ob is None or ob.type != 'MESH':
    raise RuntimeError("Select a MESH object before running this script.")

# Triangulate via bmesh (works on a copy of the mesh data, then writes back).
bm = bmesh.new()
bm.from_mesh(ob.data)
bmesh.ops.triangulate(bm, faces=bm.faces)

verts = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
tris  = [tuple(v.index for v in f.verts) for f in bm.faces]

# Write triangulated geometry back so face indices are consistent.
bm.to_mesh(ob.data)
bm.free()
ob.data.update()

# Segment.
groups = segment_mesh(verts, tris)
n_sections = len(groups)

# Build face → section lookup.
tri_section = {}
for sec_idx, face_indices in enumerate(groups):
    for fi in face_indices:
        tri_section[fi] = sec_idx

# ---------------------------------------------------------------------------
# Color attribute
# ---------------------------------------------------------------------------
if "SegmentColor" in ob.data.attributes:
    ob.data.attributes.remove(ob.data.attributes["SegmentColor"])

attr = ob.data.attributes.new(name="SegmentColor", type='FLOAT_COLOR', domain='CORNER')

# Generate N visually distinct colors (full-saturation HSV sweep).
palette = []
for i in range(max(n_sections, 1)):
    r, g, b = colorsys.hsv_to_rgb(i / max(n_sections, 1), 0.8, 0.9)
    palette.append((r, g, b, 1.0))

# Assign the same color to every corner (loop) of each face.
for poly in ob.data.polygons:
    color = palette[tri_section.get(poly.index, 0)]
    for loop_idx in poly.loop_indices:
        attr.data[loop_idx].color = color

# Make SegmentColor the active color attribute for viewport display.
names = [ca.name for ca in ob.data.color_attributes]
if "SegmentColor" in names:
    ob.data.color_attributes.active_color_index = names.index("SegmentColor")
else:
    print(f"  Note: SegmentColor not found in color_attributes (has: {names})")
ob.data.update()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
sec_tri_counts  = [len(g) for g in groups]
sec_vert_counts = [len({v for fi in g for v in tris[fi]}) for g in groups]

print(f"\n=== ShowMeshSegments: {ob.name} ===")
print(f"  Total tris:    {len(tris)}")
print(f"  Total verts:   {len(verts)}")
print(f"  Sections:      {n_sections}")
if n_sections:
    print(f"  Tris  per section: min={min(sec_tri_counts)}  max={max(sec_tri_counts)}")
    print(f"  Verts per section: min={min(sec_vert_counts)}  max={max(sec_vert_counts)}")
print("  All limits satisfied:", all(t <= 255 and v <= 255
                                     for t, v in zip(sec_tri_counts, sec_vert_counts)))
print()
