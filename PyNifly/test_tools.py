"""Helper routins for tests"""

import os
import os.path
import logging
import bpy
from niflytools import *


pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")


log = logging.getLogger("pynifly")


def test_title(name, desc):
    print (f"\n\n\n---------------- {name} ----------------")
    print (f"--- {desc}")

def clear_all():
    if bpy.data.objects:
        bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True)
    # for obj in bpy.data.objects:
    #     #bpy.data.objects.remove(obj)
    for c in bpy.data.collections:
        bpy.data.collections.remove(c)

def append_from_file(objname, with_parent, filepath, innerpath, targetobj):
    """ Convenience routine: Load an object from another blender file. 
        Deletes any existing objects with that name first.
    """
    if objname in bpy.data.objects:
        bpy.ops.object.select_all(action='DESELECT')
        obj = bpy.data.objects[objname]
        obj.select_set(True)
        if with_parent and obj.parent:
            obj.parent.select_set(True)
        bpy.ops.object.delete() 
    
    file_path = os.path.join(pynifly_dev_path, filepath)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.append(filepath=file_path,
                        directory=file_path + innerpath,
                        filename=targetobj)
    obj = bpy.data.objects[objname]
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj

def export_from_blend(blendfile, objname, game, outfile, shapekey=''):
    """ Covenience routine: Export the object found in another blend file through
        the exporter.
        """
    bpy.ops.object.select_all(action='DESELECT')
    obj = append_from_file(objname, False, blendfile, r"\Object", objname)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=test_file(outfile), target_game=game)


def find_vertex(mesh, targetloc, epsilon=0.01):
    for v in mesh.vertices:
        if VNearEqual(v.co, targetloc, epsilon=epsilon):
            return v.index
    return -1


def remove_file(fn):
    if os.path.exists(fn):
        os.remove(fn)


def test_file(filename, output=False):
    fullname = os.path.join(pynifly_dev_path, filename)
    if "TESTS/OUT/" in filename.upper() or "TESTS\\OUT\\" in filename.upper():
        output=True
    if output:
        remove_file(fullname)
    return fullname


def find_shape(name_prefix, collection=None):
    if collection is None:
        collection = bpy.data.objects
    for o in collection:
        if o.name.startswith(name_prefix):
            return o
    return None


def get_obj_bbox(obj, worldspace=False, scale=1.0):
    """Return diagonal forming bounding box of Blender object"""
    if worldspace:
        minx = min(v[0] for v in obj.bound_box)
        maxx = max(v[0] for v in obj.bound_box)
        miny = min(v[1] for v in obj.bound_box)
        maxy = max(v[1] for v in obj.bound_box)
        minz = min(v[2] for v in obj.bound_box)
        maxz = max(v[2] for v in obj.bound_box)
        return (((minx+obj.location.x)/scale, 
                 (miny+obj.location.y)/scale, 
                 (minz+obj.location.z)/scale), 
                 ((maxx+obj.location.x)/scale, 
                  (maxy+obj.location.y)/scale, 
                  (maxz+obj.location.z)/scale))
    else:
        minx = min(v.co.x for v in obj.data.vertices)
        miny = min(v.co.y for v in obj.data.vertices)
        minz = min(v.co.z for v in obj.data.vertices)
        maxx = max(v.co.x for v in obj.data.vertices)
        maxy = max(v.co.y for v in obj.data.vertices)
        maxz = max(v.co.z for v in obj.data.vertices)
        return ((minx/scale, miny/scale, minz/scale), (maxx/scale, maxy/scale, maxz/scale))


def get_shape_bbox(shape):
    """Return diagonal forming bounding box of nif shape"""
    minx = min(v[0] for v in shape.verts)
    miny = min(v[1] for v in shape.verts)
    minz = min(v[2] for v in shape.verts)
    maxx = max(v[0] for v in shape.verts)
    maxy = max(v[1] for v in shape.verts)
    maxz = max(v[2] for v in shape.verts)
    return ((minx, miny, minz), (maxx, maxy, maxz))


def compare_shapes(inshape, outshape, blshape, e=0.0001, scale=1.0, ignore_translations=False):
    """Compare significant characteristics of two nif shapes and a Blender object.
    Fail with error message if any are different.
    
    *   ignore_transforms indicates that the transform on the base shape should be
        ignored. This is useful bc it doesn't affect a skinned nif at all, and we write it
        by default if we added a transform for editing.
    """
    inshape_bbox = get_shape_bbox(inshape)
    outshape_bbox = get_shape_bbox(outshape)
    bl_bbox = get_obj_bbox(blshape, scale=scale)

    assert MatNearEqual(bl_bbox, inshape_bbox, e), f"Blender {blshape.name} bounding box matches nif \n{bl_bbox}==\n{inshape_bbox}"
    assert MatNearEqual(outshape_bbox, inshape_bbox, e), f"Nif out {outshape.name} bounding box matches nif in: \n{outshape_bbox}==\n{inshape_bbox}"

    if ignore_translations:
        xfin = inshape.xform_to_global
        xfout = outshape.xform_to_global
        assert MatNearEqual(xfout.rotation, xfin.rotation, 0.01), \
            f"Base transform-to-global unchanged: \n{xfout}\n==\n{xfin}"

        xfin = inshape.transform
        xfout = outshape.transform
        assert MatNearEqual(xfout.rotation, xfin.rotation, 0.01), \
            f"Base TriShape transform unchanged: \n{xfout}\n==\n{xfin}"
    else:
        xfin = inshape.xform_to_global.as_matrix()
        xfout = outshape.xform_to_global.as_matrix()
        assert MatNearEqual(xfout, xfin, 0.01), f"Base transform-to-global unchanged: \n{xfout}\n==\n{xfin}"

        xfin = inshape.transform.as_matrix()
        xfout = outshape.transform.as_matrix()
        assert MatNearEqual(xfout, xfin, 0.01), f"Base TriShape transform unchanged: \n{xfout}\n==\n{xfin}"


def compare_bones(bone_name, in_nif, out_nif, e=0.0001):
    """Compare bone transforms, fail if different"""
    xfin = in_nif.get_node_xform_to_global(bone_name).as_matrix()
    xfout = out_nif.get_node_xform_to_global(bone_name).as_matrix()
    assert MatNearEqual(xfout, xfin, e), \
        f"Bone {bone_name} transform unchanged:\n{xfout}\n==\n{xfin}"


def check_unweighted_verts(nifshape):
    """Fail on any vertex that has no weights."""
    weight_list = [0] * len(nifshape.verts)
    for bone_name, weights in nifshape.bone_weights.items():
        for vert_idx, wgt in weights:
            weight_list[vert_idx] += wgt

    fail = False
    for i, w in enumerate(weight_list):
        if NearEqual(w, 0):
            if not fail: 
                print(f"Shape {nifshape.name} vertex {i} has 0 weight: {w}")
            fail = True
    assert not fail, f"Found 0 vertex weights for verts in {nifshape.name}"


def assert_near_equal(actual, expected, msg, e=0.0001):
    """Assert two values are equal. Values may be scalars, vectors, or matrices."""
    try:
        assert MatNearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"
    except AssertionError:
        raise
    except:
        try:
            assert VNearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"
        except AssertionError:
            raise
        except:
            assert NearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"

def assert_less_than(actual, expected, msg, e=0.0001):
    """Assert actual is less than expected."""
    assert actual < expected, f"Values actual less than expected for {msg}: {actual} < {expected}"


def assert_greater_than(actual, expected, msg, e=0.0001):
    """Assert actual is greater than expected."""
    assert actual > expected, f"Values actual greater than expected for {msg}: {actual} < {expected}"
