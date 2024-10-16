"""Helper routins for tests"""

import sys
import os
import os.path
import pathlib
import logging
import bpy
from mathutils import Matrix, Vector, Quaternion, Euler
from niflytools import *
import blender_defs as BD


pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")


log = logging.getLogger("pynifly")


PYNIFLY_TEXTURES_SKYRIM = r"C:\Modding\SkyrimLE\mods\00 Vanilla Assets"
PYNIFLY_TEXTURES_FO4 = r"C:\Modding\Fallout4\mods\00 FO4 Assets"


def test_title(name, desc):
    print (f"\n\n\n++++++++++++++++++++++++++++++ {name} ++++++++++++++++++++++++++++++")
    print (f"{desc}")

def clear_all():
    try:
        bpy.ops.object.mode_set(mode = 'OBJECT')
    except:
        pass

    bpy.ops.object.select_all(action='DESELECT')
    # for obj in bpy.context.scene.objects:
    #     if obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'ARMATURE', 'LATTICE', 
    #                     'EMPTY', 'CAMERA', 'LAMP', 'SPEAKER']:
    #         obj.select_set(True)
    #     else:
    #         obj.select_set(False)
    # bpy.ops.object.delete()

    curlen = len(bpy.data.objects)
    while curlen > 0:
        for obj in bpy.data.objects:
            bpy.data.objects.remove(obj)
        if len(bpy.data.objects) >= curlen:
            break
        curlen = len(bpy.data.objects)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)

    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)

    for c in bpy.data.collections:
        bpy.data.collections.remove(c)

    for a in bpy.data.actions:
        bpy.data.actions.remove(a)
    bpy.context.scene.timeline_markers.clear()


def hide_all():
    if bpy.context.mode != 'OBJECT': bpy.ops.object.mode_set(mode = 'OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.hide_view_set()



def append_from_file(objname, with_parent, filepath, innerpath, targetobj):
    """ 
    Convenience routine: Load an object from another blender file. Deletes any existing
    objects with that name first.
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
    path = pathlib.Path(filename)
    if path.parts[1] in ["Skyrim", "SkyrimSE"]:
        bpy.context.preferences.filepaths.texture_directory = PYNIFLY_TEXTURES_SKYRIM
    elif path.parts[1] in ["FO4"]:
        bpy.context.preferences.filepaths.texture_directory = PYNIFLY_TEXTURES_FO4

    fullname = os.path.join(pynifly_dev_path, filename)
    if path.parts[1].upper() == "OUT":
        remove_file(fullname)
    return fullname


def find_shape(name_prefix, collection=None, type='MESH'):
    if collection is None:
        collection = bpy.data.objects
    for o in collection:
        if o.name.startswith(name_prefix) and o.type == type:
            return o
    return None


def get_obj_bbox(obj, worldspace=False, scale=1.0):
    """Return diagonal forming bounding box of Blender object"""
    if worldspace:
        # Worldspace can be hard to calculate given armatures and parent transforms. 
        # So punt--make a copy, apply everything, then return the bounds on the copy.
        try:
            bpy.ops.object.mode_set(mode = 'OBJECT')
        except:
            pass
        bpy.ops.object.select_all(action='DESELECT')
        BD.ObjectSelect([obj], active=True)
        bpy.ops.object.duplicate()
        newobj = bpy.context.object
        newobj.name = "TEST_OBJ." + obj.name
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        for m in newobj.modifiers:
            if m.type == 'ARMATURE':
                bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.ops.object.transform_apply()

        minv = Vector([sys.float_info.max] * 3)
        maxv = Vector([-sys.float_info.max] * 3)
        for v in newobj.data.vertices:
            for i in range(0, 3):
                minv[i] = min(minv[i], v.co[i])
                maxv[i] = max(maxv[i], v.co[i])

        bpy.ops.object.delete()

        return minv, maxv
    
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
    minv = Vector([sys.float_info.max] * 3)
    maxv = Vector([-sys.float_info.max] * 3)
    for v in shape.verts:
        for i, n in enumerate(v):
            minv[i] = min(minv[i], n)
            maxv[i] = max(maxv[i], n)
    return (minv, maxv)


def close_bounds(obja, objb, epsilon=1.0):
    """Check that the bounds of the two Blender objects are within epsilon of each other."""
    mina, maxa = get_obj_bbox(obja, worldspace=True)
    minb, maxb = get_obj_bbox(objb, worldspace=True)
    return VNearEqual(mina, minb, epsilon=epsilon) and VNearEqual(maxa, maxb, epsilon=epsilon) 

    assert VNearEqual(objmin, mina, epsilon=1.0), f"Collision just covers bow: {objmin} ~~ {mina}"


def compare_shapes(inshape, outshape, blshape, e=0.0001, scale=1.0, ignore_translations=False):
    """
    Compare significant characteristics of two nif shapes and a Blender object.
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
        xfin = inshape.global_transform
        xfout = outshape.global_transform
        assert MatNearEqual(xfout.rotation, xfin.rotation, 0.01), \
            f"Base transform-to-global unchanged: \n{xfout}\n==\n{xfin}"

        xfin = inshape.transform
        xfout = outshape.transform
        assert MatNearEqual(xfout.rotation, xfin.rotation, 0.01), \
            f"Base TriShape transform unchanged: \n{xfout}\n==\n{xfin}"
    else:
        xfin = BD.transform_to_matrix(inshape.global_transform)
        xfout = BD.transform_to_matrix(outshape.global_transform)
        assert MatNearEqual(xfout, xfin, 0.01), f"Base transform-to-global unchanged: \n{xfout}\n==\n{xfin}"

        xfin = BD.transform_to_matrix(inshape.transform)
        xfout = BD.transform_to_matrix(outshape.transform)
        assert MatNearEqual(xfout, xfin, 0.01), f"Base TriShape transform unchanged: \n{xfout}\n==\n{xfin}"


def compare_bones(bone_name, in_nif, out_nif, e=0.0001):
    """Compare bone transforms, fail if different"""
    xfin = BD.transform_to_matrix(in_nif.get_node_xform_to_global(bone_name))
    xfout = BD.transform_to_matrix(out_nif.get_node_xform_to_global(bone_name))
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


def assert_equiv(actual, expected, msg, e=0.0001):
    """Assert two values are nearly equal. Values may be scalars, vectors, or matrices."""
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


def assert_eq(actual, expected, msg):
    """Assert actual is same as expected."""
    assert actual == expected, f"{msg} not the same: {actual} = {expected}"


def assert_lt(actual, expected, msg, e=0.0001):
    """Assert actual is less than expected."""
    assert actual < expected, f"Values actual less than expected for {msg}: {actual} < {expected}"


def assert_le(actual, expected, msg, e=0.0001):
    """Assert actual is less than expected."""
    assert actual <= expected, f"Values actual less than expected for {msg}: {actual} <= {expected}"


def assert_gt(actual, expected, msg, e=0.0001):
    """Assert actual is greater than expected."""
    assert actual > expected, f"Values actual greater than expected for {msg}: {actual} > {expected}"


def assert_seteq(actual, expected, msg):
    """Assert two lists have the same members."""
    if type(actual) == set:
        s1 = actual
    else:
        s1 = set(actual)
    if type(expected) == set:
        s2 = expected
    else:
        s2 = set(expected)
    assert s1 == s2, f"{msg} not the same: {actual} == {expected}"


def find_object(name, coll=bpy.context.scene.objects, fn=lambda x: x.name):
    """Find an object by name with the given list of objects
        name = name to find. Blocks in nifs aren't supposed to have the same
            name but sometimes they do. Also, a Blend file might contain imports from several nifs. 
            So we can't be sure the Blender name is exactly the name in the nif. Blender may have 
            appended .### to it, where ### is some number to make it unique.
        coll = list or dictionary of objects
        fn = function to return the name from an object in the collection. Default is for when
            the collection is just a list of objects with names.
        Return = object from list, or None. Object either has the exact name or the name followed 
            by .###
    """
    foundobj = None
    for obj in coll:
        n = fn(obj)
        # Exact matches always take precedence
        if n == name:
            foundobj = obj
            break
        if re.search(name + r'\.\d\d\d', n):
            foundobj = obj
            break
    return foundobj


def test_value(name, v1, v2):
    assert v1 == v2, f"{name} value is correct: {v1} == {v2}"

def test_floatarray(name, v1, v2, epsilon=0.0001):
    assert BD.VNearEqual(v1, v2, epsilon=epsilon), f"{name} value is correct: {v1} == {v2}"