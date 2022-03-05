"""Helper routins for tests"""

import sys
import os.path
import pathlib
import logging
import bpy
import bpy_types

pynifly_dev_root = r"C:\Users\User\OneDrive\Dev"
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")


log = logging.getLogger("pynifly")


def test_title(name, desc):
    print (f"\n\n---------------- {name} ----------------")
    print (f"--- {desc}")

def clear_all():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=True, confirm=False)
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
        if with_parent:
            obj.parent.select_set(True)
        bpy.ops.object.delete() 
    
    file_path = os.path.join(pynifly_dev_path, filepath)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.append(filepath=file_path,
                        directory=file_path + innerpath,
                        filename=targetobj)
    return bpy.data.objects[objname]

def export_from_blend(NifExporter, blendfile, objname, game, outfile, shapekey=''):
    """ Covenience routine: Export the object found in another blend file through
        the exporter.
        """
    bpy.ops.object.select_all(action='DESELECT')
    obj = append_from_file(objname, False, blendfile, r"\Object", objname)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="OBJECT")
    exporter = NifExporter(os.path.join(pynifly_dev_path, outfile), game)
    exporter.export([obj])

def find_vertex(mesh, targetloc):
    for v in mesh.vertices:
        if round(v.co[0], 2) == round(targetloc[0], 2) and round(v.co[1], 2) == round(targetloc[1], 2) and round(v.co[2], 2) == round(targetloc[2], 2):
            return v.index
    return -1

def remove_file(fn):
    if os.path.exists(fn):
        os.remove(fn)

def find_shape(name_prefix, collection=bpy.data.objects):
    for o in bpy.data.objects:
        if o.name.startswith(name_prefix):
            return o
    return None