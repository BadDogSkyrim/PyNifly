"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

RUN_TESTS = False
TEST_BPY_ALL = False


bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (2, 92, 0),
    "version": (0, 0, 25), 
    "location": "File > Import-Export",
    "warning": "WIP",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

import sys
import os.path
import pathlib
import logging
from operator import or_
from functools import reduce
import traceback
import math
import re

log = logging.getLogger("pynifly")
log.info(f"Loading pynifly version {bl_info['version']}")

pynifly_dev_root = r"C:\Users\User\OneDrive\Dev"
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")
nifly_path = os.path.join(pynifly_dev_root, r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll")

if os.path.exists(nifly_path):
    log.debug(f"PyNifly dev path: {pynifly_dev_path}")
    if pynifly_dev_path not in sys.path:
        sys.path.append(pynifly_dev_path)
    log.setLevel(logging.DEBUG)
else:
    # Load from install location
    py_addon_path = os.path.dirname(os.path.realpath(__file__))
    log.debug(f"PyNifly addon path: {py_addon_path}")
    if py_addon_path not in sys.path:
        sys.path.append(py_addon_path)
    nifly_path = os.path.join(py_addon_path, "NiflyDLL.dll")
    log.setLevel(logging.INFO)

log.info(f"Nifly DLL at {nifly_path}")
if not os.path.exists(nifly_path):
    log.error("ERROR: pynifly DLL not found")

from pynifly import *
from niflytools import *
from trihandler import *
import pyniflywhereami

import bpy
from bpy.props import (
        BoolProperty,
        FloatProperty,
        StringProperty,
        EnumProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper)
import bmesh


#log.setLevel(logging.DEBUG)
#pynifly_ch = logging.StreamHandler()
#pynifly_ch.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(name)s-%(levelname)s: %(message)s')
#pynifly_ch.setFormatter(formatter)
#log.addHandler(ch)


# ### ---------------------------- IMPORT -------------------------------- ###

def mesh_create_uv(the_mesh, uv_points):
    """ Create UV in Blender to match UVpoints from Nif
        uv_points = [(u, v)...] indexed by vertex index
        """
    new_uv = [(0,0)] * len(the_mesh.loops)
    for lp_idx, lp in enumerate(the_mesh.loops):
        vert_targeted = lp.vertex_index
        new_uv[lp_idx] = (uv_points[vert_targeted][0], 1-uv_points[vert_targeted][1])
    new_uvlayer = the_mesh.uv_layers.new(do_init=False)
    for i, this_uv in enumerate(new_uv):
        new_uvlayer.data[i].uv = this_uv

def mesh_create_bone_groups(the_shape, the_object):
    """ Create groups to capture bone weights """
    vg = the_object.vertex_groups
    for bone_name in the_shape.bone_names:
        xlate_name = the_shape.parent.blender_name(bone_name)
        new_vg = vg.new(name=xlate_name)
        for v, w in the_shape.bone_weights[bone_name]:
            new_vg.add((v,), w, 'ADD')
    

def mesh_create_partition_groups(the_shape, the_object):
    """ Create groups to capture partitions """
    mesh = the_object.data
    vg = the_object.vertex_groups
    partn_groups = []
    for p in the_shape.partitions:
        log.debug(f"..found partition {p.name}")
        new_vg = vg.new(name=p.name)
        partn_groups.append(new_vg)
        if type(p) == FO4Partition:
            for sseg in p.subsegments:
                new_vg = vg.new(name=sseg.name)
                partn_groups.append(new_vg)
    for part_idx, face in zip(the_shape.partition_tris, mesh.polygons):
        if part_idx < len(partn_groups):
            this_vg = partn_groups[part_idx]
            for lp in face.loop_indices:
                this_loop = mesh.loops[lp]
                this_vg.add((this_loop.vertex_index,), 1.0, 'ADD')
    if len(the_shape.segment_file) > 0:
        the_object['FO4_SEGMENT_FILE'] = the_shape.segment_file

    
def import_shape(the_shape: NiShape):
    """ Import the shape to a Blender object, translating bone names """
    v = the_shape.verts
    t = the_shape.tris

    new_mesh = bpy.data.meshes.new(the_shape.name)
    new_mesh.from_pydata(v, [], t)
    new_object = bpy.data.objects.new(the_shape.name, new_mesh)

    # Global-to-skin transform is what offsets all the vertices together, e.g. so that
    # heads can be positioned at the origin. Put the reverse transform on the blender 
    # object so they can be worked on in their skinned position.
    # Use the one on the NiSkinData if it exists.
    xform =  the_shape.global_to_skin_data
    if xform is None:
        xform = the_shape.global_to_skin
    inv_xf = xform.invert()
    new_object.scale = [inv_xf.scale] * 3
    new_object.location = inv_xf.translation
    # vv Use matrix here instead of conversion?
    new_object.rotation_euler[0], new_object.rotation_euler[1], new_object.rotation_euler[2] \
        = inv_xf.rotation.euler_deg()

    mesh_create_uv(new_object.data, the_shape.uvs)
    mesh_create_bone_groups(the_shape, new_object)
    mesh_create_partition_groups(the_shape, new_object)
    for f in new_mesh.polygons:
        f.use_smooth = True

    new_mesh.update(calc_edges=True, calc_edges_loose=True)
    new_mesh.validate(verbose=True)
    return new_object

def add_bone_to_arma(armdata, name, nif):
    """ Add bone to armature. Bone may come from nif or reference skeleton.
        armdata = armature data block
        name = blender name of the new bone
        nif = nif we're importing
        returns new bone
    """
    if name in armdata.edit_bones:
        return None
    
    # use the transform in the file if there is one
    bone_xform = nif.get_node_xform_to_global(nif.nif_name(name)) 

    bone = armdata.edit_bones.new(name)
    bone.head = bone_xform.translation
    if nif.game in ("SKYRIM", "SKYRIMSE"):
        rot_vec = bone_xform.rotation.by_vector((0.0, 0.0, 5.0))
    else:
        rot_vec = bone_xform.rotation.by_vector((5.0, 0.0, 0.0))
    bone.tail = (bone.head[0] + rot_vec[0], bone.head[1] + rot_vec[1], bone.head[2] + rot_vec[2])
    bone['pyxform'] = bone_xform.rotation.matrix # stash for later

    #print(f"Added bone {name} at {bone.head[:]} - {bone.tail[:]}")
    return bone

def connect_armature(arm_data, the_nif):
    """ Connect up the bones in an armature to make a full skeleton.
        Use parent/child relationships in the nif if present, from the skel otherwise.
        arm_data: Data block of the armature
        the_nif: Nif being imported
        """
    log.info("..Connecting armature")
    bones_to_parent = [b.name for b in arm_data.edit_bones]
    i = 0
    while i < len(bones_to_parent): # list will grow while iterating
        bonename = bones_to_parent[i]
        arma_bone = arm_data.edit_bones[bonename]

        if arma_bone.parent is None:
            #print("Parenting " + bonename)
            parentname = None
            skelbone = None
            # look for a parent in the nif
            nifname = the_nif.nif_name(bonename)
            if nifname in the_nif.nodes:
                niparent = the_nif.nodes[nifname].parent
                if niparent and niparent._handle != the_nif.root:
                    parentname = niparent.blender_name
                    #print("Parent bone from nif: " + parentname)

            if parentname is None:
                # No parent in the nif. If it's a known bone, get parent from skeleton
                if arma_bone.name in the_nif.dict.byBlender:
                    p = the_nif.dict.byBlender[bonename].parent
                    if p:
                        parentname = p.blender
                        #print("Parent bone from skeleton: " + parentname)
            
            # if we got a parent from somewhere, hook it up
            if parentname:
                if parentname not in arm_data.edit_bones:
                    # Add parent bones and put on our list so we can get its parent
                    #print(f"Parenting new bone {arma_bone.name} -> {parentname}")
                    new_parent = add_bone_to_arma(arm_data, parentname, the_nif)
                    bones_to_parent.append(parentname)  
                    arma_bone.parent = new_parent
                else:
                    #print(f"Parenting known {arma_bone.name} -> {parentname}")
                    arma_bone.parent = arm_data.edit_bones[parentname]
        i += 1

def make_armature(the_coll, the_nif, bone_names):
    """ Make a Blender armature from the given info. 
        the_coll = Collection to put the armature in. If the current active object is an
            armature, they will be added to it instead of creating a new one.
        the_nif = Nif file to read bone data from
        bone_names = bones to include in the armature. Additional bones will be added from
            the reference skeleton as needed to connect every bone to the skeleton root.
        Returns: New armature, set as active object
        """
    if bpy.context.object and bpy.context.object.type == "ARMATURE":
        arm_ob = bpy.context.object
    else:
        bpy.ops.object.select_all(action='DESELECT')
        arm_data = bpy.data.armatures.new(the_nif.rootName)
        arm_ob = bpy.data.objects.new(the_nif.rootName, arm_data)
        the_coll.objects.link(arm_ob)
        arm_ob.select_set(True)
        bpy.context.view_layer.objects.active = arm_ob

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    
    for bone_game_name in bone_names:
        add_bone_to_arma(arm_ob.data, the_nif.blender_name(bone_game_name), the_nif)
        
    # Hook the armature bones up to a skeleton
    connect_armature(arm_ob.data, the_nif)

    #print(f"***All armature edit bones: " + str(list(arm_ob.data.edit_bones.keys())))
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    #print(f"***All armature '{arm_ob.name}' bones: " + str(list(arm_ob.data.bones.keys())))
    return arm_ob

def import_nif(f: NifFile):
    new_collection = bpy.data.collections.new(os.path.basename(f.filepath))
    bpy.context.scene.collection.children.link(new_collection)

    log.info("..Importing " + f.game + " file")
    bones = set()
    new_objs = []

    for s in f.shapes:
        obj = import_shape(s)
        new_objs.append(obj)
        new_collection.objects.link(obj)

        for n in s.bone_names: 
            log.debug(f"....adding bone {n} for {s.name}")
            bones.add(n) 

    for o in new_objs: o.select_set(True)

    if len(bones) > 0 or len(f.shapes) == 0:
        if len(bones) == 0:
            log.debug(f"....No shapes in nif, importing bones as skeleton")
            bones = set(f.nodes.keys())
        else:
            log.debug(f"....Found bones, creating armature")
        arma = make_armature(new_collection, f, bones)
        
        if len(new_objs) > 0:
            for o in new_objs: o.select_set(True)
            bpy.ops.object.parent_set(type='ARMATURE_NAME', xmirror=False, keep_transform=False)
        else:
            arma.select_set(True)
    
    if len(new_objs) > 0:
        bpy.context.view_layer.objects.active = new_objs[0]


class ImportNIF(bpy.types.Operator, ImportHelper):
    """Load a NIF File"""
    bl_idname = "import_scene.nifly"
    bl_label = "Import NIF (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".nif"

    def execute(self, context):
        log.info("NIFLY IMPORT V%d.%d.%d" % bl_info['version'])
        status = {'FINISHED'}

        try:
            NifFile.Load(nifly_path)

            bpy.ops.object.select_all(action='DESELECT')

            f = NifFile(self.filepath)
            import_nif(f)
        
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    ctx = bpy.context.copy()
                    ctx['area'] = area
                    ctx['region'] = area.regions[-1]
                    bpy.ops.view3d.view_selected(ctx)

        except:
            log.exception("Import of nif failed")
            self.report({"ERROR"}, "Import of nif failed, see console window for details")
            status = {'CANCELLED'}
                
        return status


# ### ---------------------------- TRI Files -------------------------------- ###

def create_shape_keys(obj, tri:TriFile):
    """Adds the shape keys in tri to obj 
        """
    mesh = obj.data
    #if mesh.shape_keys is None:
    #    log.debug(f"Adding first shape key to {obj.name}")
    #    newsk = obj.shape_key_add()
    #    mesh.shape_keys.use_relative=True
    #    newsk.name = "Basis"
    #    mesh.update()

    for morph_name, morph_verts in sorted(tri.morphs.items()):
        newsk = obj.shape_key_add()
        newsk.name = morph_name

        obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
        #This is a pointer, not a copy
        mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
        #log.debug(f"Morph {morph_name} in tri file should have same number of verts as Blender shape: {len(mesh_key_verts)} != {len(morph_verts)}")
        for key_vert, morph_vert in zip(mesh_key_verts, morph_verts):
            key_vert.co[0] = morph_vert[0]
            key_vert.co[1] = morph_vert[1]
            key_vert.co[2] = morph_vert[2]
        
        mesh.update()

def create_trip_shape_keys(obj, trip:TripFile):
    """Adds the shape keys in trip to obj 
        """
    mesh = obj.data
    verts = mesh.vertices

    if mesh.shape_keys is None or "Basis" not in mesh.shape_keys.key_blocks:
        newsk = obj.shape_key_add()
        newsk.name = "Basis"

    offsetmorphs = trip.shapes[obj.name]
    for morph_name, morph_verts in sorted(offsetmorphs.items()):
        newsk = obj.shape_key_add()
        newsk.name = ">" + morph_name

        obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
        #This is a pointer, not a copy
        mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
        #log.debug(f"Morph {morph_name} in tri file should have same number of verts as Blender shape: {len(mesh_key_verts)} != {len(morph_verts)}")
        for vert_index, offsets in morph_verts:
            for i in range(3):
                mesh_key_verts[vert_index].co[i] = verts[vert_index].co[i] + offsets[i]
        
        mesh.update()


def import_trip(filepath, target_objs):
    """ Import a BS Tri file. 
        These TRI files do not have full shape data so they have to be matched to one of the 
        objects in target_objs.
        return = True if the file is a BS Tri file
        """
    result = set()
    trip = TripFile.from_file(filepath)
    if trip.is_valid:
        for shapename, offsetmorphs in trip.shapes.items():
            matchlist = [o for o in target_objs if o.name == shapename]
            if len(matchlist) == 0:
                log.warning("BS Tri file shape does not match any selected object: {shapename}")
                result.add('WARNING')
            else:
                create_trip_shape_keys(matchlist[0], trip)
    else:
        result.add('WRONGTYPE')

    return result


def import_tri(filepath):
    cobj = bpy.context.object

    #trip = TripFile.from_file(filepath)
    #if trip.is_valid:
    #    if cobj is None or cobj.type != "MESH":
    #        log.info(f"Loading a Bodyslide TRI -- requires a matching selected mesh")
    #        raise "Cannot import Bodyslide TRI file without a selected object"
    #    create_trip_shape_keys(cobj, trip)
    #    return cobj

    tri = TriFile.from_file(filepath)

    new_object = None

    if cobj:
        log.debug(f"Importing with selected object {cobj.name}, type {cobj.type}")
        if cobj.type == "MESH":
            log.debug(f"Selected mesh vertex match: {len(cobj.data.vertices)}/{len(tri.vertices)}")

    # Check whether selected object should receive shape keys
    if cobj and cobj.type == "MESH" and len(cobj.data.vertices) == len(tri.vertices):
        new_object = cobj
        new_mesh = new_object.data
        log.info(f"Verts match, loading tri into existing shape {new_object.name}")
    #elif trip.is_valid:
    #    log.info(f"Loading a Bodyslide TRI -- requires a matching selected mesh")
    #    raise "Cannot import Bodyslide TRI file without a selected object"

    if new_object is None:
        new_mesh = bpy.data.meshes.new(os.path.basename(filepath))
        new_mesh.from_pydata(tri.vertices, [], tri.faces)
        new_object = bpy.data.objects.new(new_mesh.name, new_mesh)

        for f in new_mesh.polygons:
            f.use_smooth = True

        new_mesh.update(calc_edges=True, calc_edges_loose=True)
        new_mesh.validate(verbose=True)

        mesh_create_uv(new_mesh, tri.uv_pos)
   
        new_collection = bpy.data.collections.new(os.path.basename(os.path.basename(filepath) + ".Coll"))
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.objects.link(new_object)
        bpy.context.view_layer.objects.active = new_object
        new_object.select_set(True)

    create_shape_keys(new_object, tri)

    return new_object


def export_tris(nif, trip, obj, verts, tris, loops, uvs, morphdict):
    """ Export a tri file to go along with the given nif file, if there are shape keys 
    """
    result = {'FINISHED'}

    if obj.data.shape_keys is None:
        return result

    fpath = os.path.split(nif.filepath)
    fname = os.path.splitext(fpath[1])
    fname_tri = os.path.join(fpath[0], fname[0] + ".tri")
    fname_chargen = os.path.join(fpath[0], fname[0] + "_chargen.tri")

    # Don't export anything that starts with an underscore or asterisk
    objkeys = obj.data.shape_keys.key_blocks.keys()
    export_keys = set(filter((lambda n: n[0] not in ('_', '*') and n != 'Basis'), objkeys))
    expression_morphs = nif.dict.expressions.intersection(export_keys)
    trip_morphs = set(filter((lambda n: n[0] == '>'), objkeys))
    chargen_morphs = export_keys.difference(expression_morphs).difference(trip_morphs)

    if len(expression_morphs) > 0 and len(trip_morphs) > 0:
        log.warning(f"Found both expression morphs and BS tri morphs in shape {obj.name}. May be an error.")
        result = {'WARNING'}

    if len(expression_morphs) > 0 or len(chargen_morphs) > 0:
        tri = TriFile()
        tri.vertices = verts
        tri.faces = tris
        tri.uv_pos = uvs
        tri.face_uvs = tris # (because 1:1 with verts)
        tri.morphs = morphdict
    
        if len(expression_morphs) > 0:
            log.info(f"Generating tri file '{fname_tri}'")
            #log.debug(f"Expression morphs: {expression_morphs}")
            tri.write(fname_tri, expression_morphs)

        if len(chargen_morphs) > 0:
            log.info(f"Generating tri file '{fname_chargen}'")
            tri.write(fname_chargen, chargen_morphs)

    if len(trip_morphs) > 0:
        log.info(f"Generating BS tri shapes for '{obj.name}'")
        trip.set_morphs(obj.name, morphdict, verts)

    return result

class ImportTRI(bpy.types.Operator, ImportHelper):
    """Load a TRI File"""
    bl_idname = "import_scene.niflytri"
    bl_label = "Import TRI (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".tri"

    def execute(self, context):
        log.info("NIFLY IMPORT V%d.%d.%d" % bl_info['version'])
        status = {'FINISHED'}

        try:
            
            v = import_trip(self.filepath, context.selected_objects)
            if 'WRONGTYPE' in v:
                import_tri(self.filepath)
            status.union(v)
        
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    ctx = bpy.context.copy()
                    ctx['area'] = area
                    ctx['region'] = area.regions[-1]
                    bpy.ops.view3d.view_selected(ctx)

            if 'WARNING' in status:
                self.report({"ERROR"}, "Import completed with warnings, see console for details")

        except:
            log.exception("Import of tri failed")
            self.report({"ERROR"}, "Import of tri failed, see console window for details")
            status = {'CANCELLED'}
                
        return status.intersection({'FINISHED', 'CANCELLED'})

# ### ---------------------------- EXPORT -------------------------------- ###

def clean_filename(fn):
    return "".join(c for c in fn.strip() if (c.isalnum() or c in "._- "))

def select_all_faces(workingctx, mesh):
    bpy.ops.object.mode_set(mode = 'OBJECT')
    for f in mesh.polygons:
        f.select = True


def extract_face_info(ctxt, mesh):
    """ Extract face info from the mesh. Mesh is triangularized. 
        Return 
        loops = [vert-index, ...] list of vert indices in loops (which are tris)
        uvs = [(u,v), ...] list of uv coordinates 1:1 with loops
        norms = [(x,y,z), ...] list of normal vectors 1:1 with loops
        --Normal vectors come from the loops, because they reflect whether the edges
        are sharp or the object has flat shading
        """
    loops = []
    uvs = []
    norms = []
    uvlayer = mesh.uv_layers.active.data

    bpy.ops.object.mode_set(mode='OBJECT') #required to get UVs
    for f in mesh.polygons:
        for i in f.loop_indices:
            loopseg = mesh.loops[i]
            loops.append(loopseg.vertex_index)
            uvs.append(uvlayer[i].uv[:])
            #if mesh.has_custom_normals:
            norms.append(loopseg.normal[:])
            #log.debug(f"LOOP NORMAL: {i} = {loopseg.normal[:]}")
            #else:
            #    norms.append(mesh.vertices[loopseg.vertex_index].normal[:])

    return loops, uvs, norms


def extract_vert_info(obj, mesh, target_key=''):
    """Returns 5 lists of equal length with one entry each for each vertex
        verts = [(x, y, z)... ] - base or as modified by target-key if provided
        weights = [{group-name: weight}... ] - 1:1 with verts list
        dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
            if "target_key" is specified this will be empty
        """
    weights = []
    morphdict = {}

    if target_key != '' and mesh.shape_keys:
        verts = [v.co[:] for v in mesh.shape_keys.key_blocks[target_key].data]
    else:
        verts = [v.co[:] for v in mesh.vertices]

    for v in mesh.vertices:
        vert_weights = {}
        for vg in v.groups:
            vert_weights[obj.vertex_groups[vg.group].name] = vg.weight
        weights.append(vert_weights)
    
    if target_key == '' and mesh.shape_keys:
        for sk in mesh.shape_keys.key_blocks:
            morphdict[sk.name] = [v.co[:] for v in sk.data]

    return verts, weights, morphdict


def get_bone_xforms(arma, bone_names):
    """Return transforms for the bones in list, getting rotation from what we stashed on import
        arma = data block of armature
        bone_names = list of names
        result = dict{bone-name: MatTransform, ...}
    """
    result = {}
    for b in arma.bones:
        mat = MatTransform()
        mat.translation = b.head_local
        mat.rotation = RotationMatrix((tuple(b['pyxform'][0]), 
                                       tuple(b['pyxform'][1]), 
                                       tuple(b['pyxform'][2])))
        result[b.name] = mat
    return result

def export_skin(obj, new_shape, new_xform, weights_by_vert):
    log.info("..Parent is armature, skin the mesh")
    new_shape.skin()
    # if new_shape.has_skin_instance: 
    # just use set_global_to_skin -- it does the check (maybe)
    #if nif.game in ("SKYRIM", "SKYRIMSE"):
    #    new_shape.set_global_to_skindata(new_xform.invert())
    #else:
    #    new_shape.set_global_to_skin(new_xform.invert())
    new_shape.set_global_to_skin(new_xform.invert())
    
    group_names = [g.name for g in obj.vertex_groups]
    weights_by_bone = get_weights_by_bone(weights_by_vert)
    used_bones = weights_by_bone.keys()
    arma_bones = get_bone_xforms(obj.parent.data, used_bones)
    
    for bone_name, bone_xform in arma_bones.items():
        # print(f"  shape {obj.name} adding bone {bone_name}")
        if bone_name in weights_by_bone and len(weights_by_bone[bone_name]) > 0:
            # print(f"..Shape {obj.name} exporting bone {bone_name} with rotation {bone_xform.rotation.euler_deg()}")
            nifname = new_shape.parent.nif_name(bone_name)
            new_shape.add_bone(nifname, bone_xform)
                #nif.nodes[bone_name].xform_to_global)
            new_shape.setShapeWeights(nifname, weights_by_bone[bone_name])


def tag_unweighted(obj, bones):
    """ Find and return verts that are not weighted to any of the given bones 
        result = (v_index, ...) list of indices into the vertex list
    """
    log.debug(f"..Checking for unweighted verts on {obj.name}")
    unweighted_verts = []
    for v in obj.data.vertices:
        maxweight = max([g.weight for g in v.groups])
        if maxweight < 0.0001:
            unweighted_verts.append(v.index)
    log.debug(f"..Unweighted vert count: {len(unweighted_verts)}")
    return unweighted_verts


def create_group_from_verts(obj, name, verts):
    """ Create a new vertex group from the list of vertex indices """
    if name in obj.vertex_groups:
        obj.vertex_groups.remove(obj.vertex_groups[name])
    g = obj.vertex_groups.new(name=name)
    g.add(verts, 1.0, 'REPLACE')


def best_game_fit(bonelist):
    """ Find the game that best matches the skeleton """
    boneset = set([b.name for b in bonelist])
    maxmatch = 0
    matchgame = ""
    #print(f"Checking bonelist {[b.name for b in bonelist]}")
    for g, s in gameSkeletons.items():
        n = s.matches(boneset)
        #print(f"Checking against game {g} match is {n}")
        if n > maxmatch:
            maxmatch = n
            matchgame = g
    return matchgame


def expected_game(nif, bonelist):
    """ Check whether the nif's game is the best match for the given bonelist """
    matchgame = best_game_fit(bonelist)
    return matchgame == "" or matchgame == nif.game


def partitions_from_vert_groups(obj):
    """ Return dictionary of Partition objects for all vertex groups that match the partition name 
        pattern. These are all partition objects including subsegments.
    """
    val = {}
    if obj.vertex_groups:
        for vg in obj.vertex_groups:
            skyid = SkyPartition.name_match(vg.name)
            if skyid >= 0:
                val[vg.name] = SkyPartition(part_id=skyid, flags=0, name=vg.name)
            else:
                segid = FO4Partition.name_match(vg.name)
                if segid >= 0:
                    val[vg.name] = FO4Partition(segid, 0, name=vg.name)
        
        # A second pass to pick up subsections
        for vg in obj.vertex_groups:
            parent_name, subseg_id, material = Subsegment.name_match(vg.name)
            if subseg_id >= 0:
                if not parent_name in val:
                    # Create parent segments if not there
                    parid = FO4Partition.name_match(parent_name)
                    val[parent_name] = FOPartition(parid, 0, parent_name)
                p = val[parent_name]
                log.debug(f"....Found subsegment {vg.name} child of {parent_name}")
                val[vg.name] = Subsegment(len(val)+1, 0, material, p, name=vg.name)
    
    return val


def all_vertex_groups(weightdict):
    """ Return the set of group names that have non-zero weights """
    val = set()
    for g, w in weightdict.items():
        if w > 0.0001:
            val.add(g)
    return val


def export_partitions(obj, weights_by_vert, tris):
    """ Export partitions described by vertex groups
        weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts. For 
            partitions, can assume the weights are 1.0
        tris = [(v1, v2, v3)...] where v1-3 are indices into the vertex list
    """
    log.debug(f"..Exporting partitions")
    partitions = partitions_from_vert_groups(obj)
    log.debug(f"....Found partitions {list(partitions.keys())}")

    if len(partitions) == 0:
        return [], []

    partition_set = set(list(partitions.keys()))

    tri_indices = [0] * len(tris)

    for i, t in enumerate(tris):
        # All 3 have to be in the vertex group to count
        vg0 = all_vertex_groups(weights_by_vert[t[0]])
        vg1 = all_vertex_groups(weights_by_vert[t[1]])
        vg2 = all_vertex_groups(weights_by_vert[t[2]])
        tri_partitions = vg0.intersection(vg1).intersection(vg2).intersection(partition_set)
        if len(tri_partitions) > 0:
            if len(tri_partitions) > 1:
                log.warning(f"....Found multiple partitions for tri {t}: {tri_partitions}")
            tri_indices[i] = partitions[next(iter(tri_partitions))].id

    return list(partitions.values()), tri_indices


def export_shape(nif, trip, obj, target_key=''):
    """Export given blender object to the given NIF file
        nif = target nif file
        trip = target file for BS Tri shapes
        obj = blender object
        target_key = shape key to export
        """
    log.info("Exporting " + obj.name)
    mesh = obj.data
    workingctx = bpy.context # bpy.context.copy()
    retval = {'FINISHED'}

    is_skinned = (obj.parent and obj.parent.type == 'ARMATURE')
    unweighted = []
        
    if is_skinned:
        # Get unweighted bones before we muck up the list by splitting edges
        unweighted = tag_unweighted(obj, obj.parent.data.bones.keys())
        if not expected_game(nif, obj.parent.data.bones):
            log.warning(f"Exporting to game that doesn't match armature: game={nif.game}, armature={obj.parent.name}")
            retval.add('GAME')

    log.info("..Triangulating mesh")
    originalmesh = mesh.copy()
    try:
        editmesh = mesh
        #tempobj = bpy.data.objects.new("pynifly_tmp", editmesh)
        #tempobj.data = editmesh
        #workingctx.collection.objects.link(tempobj)
        #workingctx.view_layer.objects.active = tempobj
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        #workingctx.scene.objects.active = ob

        # Can't figure out how to get custom normals out of a bmesh. Can't figure out how to triangulate
        # a copy of a regular mesh. So do this hack.
        #bm = bmesh.new()
        #bm.from_mesh(mesh)
        #bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
        #editmesh = mesh.copy()
        #bm.to_mesh(editmesh)

        select_all_faces(workingctx, editmesh)
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')

        editmesh.update()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        # Calculate the normals--have to do this after triangularization and in object mode
        editmesh.calc_normals()
        editmesh.calc_normals_split()

        verts, weights_by_vert, morphdict = extract_vert_info(obj, editmesh, target_key)
        loops, uvs, norms = extract_face_info(workingctx, editmesh)
    
        log.info("..Splitting mesh along UV seams")
        mesh_split_by_uv(verts, norms, loops, uvs, weights_by_vert, morphdict)
        # Old UV map had dups where verts were split; new matches 1-1 with verts
        uvmap_new = [uvs[loops.index(i)] for i in range(len(verts))]
        norms_new = [norms[loops.index(i)] for i in range(len(verts))]
        tris = [(loops[i], loops[i+1], loops[i+2]) for i in range(0, len(loops), 3)]
    finally:
        obj.data = originalmesh
    
    log.info("..Exporting to nif")
    new_shape = nif.createShapeFromData(obj.name, verts, tris, uvmap_new, norms_new)

    if is_skinned:
        nif.createSkin()

    new_xform = MatTransform();
    new_xform.translation = obj.location
    new_xform.rotation = RotationMatrix((obj.matrix_local[0][0:3], 
                                            obj.matrix_local[1][0:3], 
                                            obj.matrix_local[2][0:3]))

    if obj.scale[0] != obj.scale[1] or obj.scale[0] != obj.scale[2]:
        log.warning("Object scale not uniform, using x-value") # apply scale to verts?   
        retval.add('SCALE')
    new_xform.scale = obj.scale[0]
        
    if is_skinned:
        export_skin(obj, new_shape, new_xform, weights_by_vert)
        if len(unweighted) > 0:
            create_group_from_verts(obj, "*UNWEIGHTED*", unweighted)
            log.warning("Some vertices are not weighted to the armature")
            retval.add('UNWEIGHTED')

        partitions, tri_indices = export_partitions(obj, weights_by_vert, tris)
        if len(partitions) > 0:
            new_shape.set_partitions(partitions, tri_indices)
    else:
        new_shape.transform = new_xform

    retval.union(export_tris(nif, trip, obj, verts, tris, loops, uvmap_new, morphdict))

    log.info(f"..{obj.name} successfully exported")
    return retval


def export_shape_to(shape, filepath, game):
    outnif = NifFile()
    outtrip = TripFile()
    outnif.initialize(game, filepath)
    ret = export_shape(outnif, outtrip, shape) 
    outnif.save()
    return ret


def get_common_shapes(obj_list):
    """ Return the shape keys common to all the given objects """
    res = None
    for obj in obj_list:
        o_shapes = set()
        if obj.data.shape_keys:
            o_shapes = set(obj.data.shape_keys.key_blocks.keys())
        if res:
            res = res.intersection(o_shapes)
        else:
            res = o_shapes
    return list(res)

def get_with_uscore(str_list):
    return list(filter((lambda x: x[0] == '_'), str_list))


class ExportNIF(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.nifly"
    bl_label = 'Export NIF (Nifly)'
    bl_options = {'PRESET'}

    filename_ext = ".nif"
    
    target_game: EnumProperty(
            name="Target Game",
            items=(('SKYRIM', "Skyrim", ""),
                   ('SKYRIMSE', "Skyrim SE", ""),
                   ('FO4', "Fallout 4", ""),
                   ('FO76', "Fallout 76", ""),
                   ('FO3', "Fallout New Vegas", ""),
                   ('FO3', "Fallout 3", ""),
                   ),
            )

    def __init__(self):
        obj = bpy.context.object
        if obj:
            self.filepath = clean_filename(obj.name)
        arma = None
        if obj.type == "ARMATURE":
            arma = obj
        else:
            if obj.parent and obj.parent.type == "ARMATURE":
                arma = obj.parent
        if arma:
            g = best_game_fit(arma.data.bones)
            if g != "":
                self.target_game = g
        

    def execute(self, context):
        log.info("NIFLY EXPORT V%d.%d.%d" % bl_info['version'])
        NifFile.Load(nifly_path)

        try:
            res = set()
        
            objs_to_export = set()
            armatures_found = set()
            objs_unweighted = []
            objs_scale = []
            arma_game = []
        
            for obj in context.selected_objects:  
                if obj.type == 'ARMATURE':
                    armatures_found.add(obj)
                    for child in obj.children:
                        if child.type == 'MESH':
                            objs_to_export.add(child)
                elif obj.type == 'MESH':
                    objs_to_export.add(obj)
        
            if len(objs_to_export) == 0:
                log.warning("Warning: Nothing to export")
                self.report("Warning: Nothing to export")
                return {"CANCELLED"}
            else:
                shape_keys = get_with_uscore(get_common_shapes(objs_to_export))
                if len(shape_keys) == 0:
                    shape_keys.append('') # just export the plain file
                
                for sk in shape_keys:
                    fname_ext = os.path.splitext(os.path.basename(self.filepath))
                    fbasename = fname_ext[0] + sk
                    fnamefull = fbasename + fname_ext[1]
                    fpath = os.path.join(os.path.dirname(self.filepath), fnamefull)

                    log.info(f"..Exporting to {self.target_game} {fpath}")
                    exportf = NifFile()
                    exportf.initialize(self.target_game, fpath)

                    trip = TripFile()

                    for obj in objs_to_export:
                        r = export_shape(exportf, trip, obj, sk)
                        #log.debug(f"Exported shape {obj.name} with result {str(r)}")
                        if 'UNWEIGHTED' in r:
                            objs_unweighted.append(obj.name)
                        if 'SCALE' in r:
                            objs_scale.append(obj.name)
                        if 'GAME' in r:
                            arma_game.append(obj.parent.name)
                        res = res.union(r)

                    exportf.save()

                    if len(trip.shapes) > 0:
                        trip.write(os.path.join(os.path.dirname(self.filepath), fname_ext[0]) 
                                   + ".tri")
            
            rep = False
            if 'UNWEIGHTED' in res:
                self.report({"ERROR"}, f"The following objects have unweighted vertices.\nSee the '*UNWEIGHTED*' vertex groups to find them: \n{objs_unweighted}")
                rep = True
            if 'SCALE' in res:
                self.report({"ERROR"}, f"The following objects have non-uniform scale, which nifs do not support.\nUsing the x scale value: \n{objs_scale}")
                rep = True
            if 'GAME' in res:
                self.report({'WARNING'}, f"The armature appears to be designed for a different game--check that it's correct\nArmature: {arma_game}, game: {exportf.game}")
                rep = True
            if 'WARNING' in res:
                self.report({'WARNING'}, f"Export completed with warnings. Check the console window.")
                rep = True
            if not rep:
                self.report({'INFO'}, f"Export successful")
            
        except:
            log.exception("Export of nif failed")
            self.report({"ERROR"}, "Export of nif failed, see console window for details")
            res.add("CANCELLED")

        log.info("Export successful")
        return res.intersection({'CANCELLED'}, {'FINISHED'})


def nifly_menu_import_nif(self, context):
    self.layout.operator(ImportNIF.bl_idname, text="Nif file with Nifly (.nif)")
def nifly_menu_import_tri(self, context):
    self.layout.operator(ImportTRI.bl_idname, text="Tri file with Nifly (.tri)")
def nifly_menu_export(self, context):
    self.layout.operator(ExportNIF.bl_idname, text="Nif file with Nifly (.nif)")

def register():
    bpy.utils.register_class(ImportNIF)
    bpy.utils.register_class(ImportTRI)
    bpy.utils.register_class(ExportNIF)
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_nif)
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_tri)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_nif)
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_tri)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export)
    bpy.utils.unregister_class(ImportNIF)
    bpy.utils.unregister_class(ExportNIF)


def append_collection(objname, with_parent, filepath, innerpath, targetobj):
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


def run_tests():
    print("""
    ############################################################
    ##                                                        ##
    ##                        TESTING                         ##
    ##                                                        ##
    ############################################################
    """)

    TEST_EXPORT = False
    TEST_IMPORT_ARMATURE = False
    TEST_EXPORT_WEIGHTS = False
    TEST_UNIT = False
    TEST_IMP_EXP_SKY = False
    TEST_IMP_EXP_FO4 = False
    TEST_ROUND_TRIP = False
    TEST_UV_SPLIT = False
    TEST_CUSTOM_BONES = False
    TEST_BPY_PARENT = False
    TEST_BABY = False
    TEST_CONNECTED_SKEL = False
    TEST_TRI = False
    TEST_0_WEIGHTS = False
    TEST_SPLIT_NORMAL = False
    TEST_SKEL = False
    TEST_PARTITIONS = True
    TEST_SEGMENTS = True

    NifFile.Load(nifly_path)
    #LoggerInit()

    if TEST_BPY_ALL or TEST_UNIT:
        # Lower-level tests of individual routines for bug hunting
        print("## TEST_UNIT get_weights_by_bone converts from weights-by-vertex")
        group_names = ("a", "b", "c", "d")
        wbv = [{"a": 0.1, "c": 0.5}, {"b": 0.2}, {"d": 0.0, "b": 0.6}, {"a": 0.4}]
        wbb = get_weights_by_bone(wbv)
        assert wbb["a"] == [(0, 0.1), (3, 0.4)], "ERROR: get_weights_by_bone failed"
        assert wbb["b"] == [(1, 0.2), (2, 0.6)], "ERROR: get_weights_by_bone failed"
        assert wbb["c"] == [(0, 0.5)], "ERROR: get_weights_by_bone failed"

    if TEST_BPY_ALL or TEST_EXPORT:
        print("## TEST_EXPORT Can export the basic cube")
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        log.debug("TODO: support objects with flat shading or autosmooth properly")
        for f in cube.data.polygons: f.use_smooth = True
        filepath = os.path.join(pynifly_dev_path, r"tests\Out\testSkyrim01.nif")
        export_shape_to(cube, filepath, "SKYRIM")

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        f = NifFile(filepath)
        sourceGame = f.game
        assert f.game == "SKYRIM", "ERROR: Wrong game found"

        import_nif(f)

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, f"ERROR: Cube should have 14 verts, has {len(new_cube.data.vertices)}"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, f"ERROR: Cube should have 36 UV locations, has {len(new_cube.data.uv_layers[0].data)}"
        assert len(new_cube.data.polygons) == 12, f"ERROR: Cube should have 12 polygons, has {len(new_cube.data.polygons)}"
        # bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can do the same for FO4")

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        for f in cube.data.polygons: f.use_smooth = True
        filepath = os.path.join(pynifly_dev_path, r"tests\Out\testFO401.nif")
        export_shape_to(cube, filepath, "FO4")

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        f = NifFile(filepath)
        sourceGame = f.game
        assert f.game == "FO4", "ERROR: Wrong game found"

        import_nif(f)

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, f"ERROR: Cube should have 14 verts, has {len(new_cube.data.vertices)}"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, f"ERROR: Cube should have 36 UV locations, has {len(new_cube.data.uv_layers[0].data)}"
        assert len(new_cube.data.polygons) == 12, f"ERROR: Cube should have 12 polygons, has {len(new_cube.data.polygons)}"
        # bpy.data.objects.remove(cube, do_unlink=True)

    if TEST_BPY_ALL or TEST_IMPORT_ARMATURE:
        print("## TEST_IMPORT_ARMATURE Can import a Skyrim head with armature")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        filepath = os.path.join(pynifly_dev_path, "tests\Skyrim\malehead.nif")
        f = NifFile(filepath)
        import_nif(f)
        male_head = bpy.context.selected_objects[0]
        assert round(male_head.location.z, 0) == 120, "ERROR: Object not elevated to position"
        assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"
        
        print("## Can import a FO4 head  with armature")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        filepath = os.path.join(pynifly_dev_path, "tests\FO4\BaseMaleHead.nif")
        f = NifFile(filepath)
        import_nif(f)
        male_head = bpy.data.objects["BaseMaleHead:0"]
        assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
        assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"

    if TEST_BPY_ALL or TEST_IMP_EXP_SKY:
        print("## TEST_IMP_EXP_SKY Can read the armor nif and spit it back out (no blender shape)")

        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        nif = NifFile(testfile)
        assert "Armor" in nif.getAllShapeNames(), "ERROR: Didn't read armor"

        the_armor = nif.shape_dict["Armor"]
        assert len(the_armor.verts) == 2115, "ERROR: Wrong number of verts"
        assert (len(the_armor.tris) == 3195), "ERROR: Wrong number of tris"

        outfile = os.path.join(pynifly_dev_path, "tests/Out/TestSkinnedFromPy02.nif")
        if os.path.exists(outfile):
            os.remove(outfile)
        new_nif = NifFile()
        new_nif.initialize("SKYRIM", outfile)
        new_nif.createSkin()
        
        new_armor = new_nif.createShapeFromData("Armor", 
                                                the_armor.verts,
                                                the_armor.tris,
                                                the_armor.uvs,
                                                the_armor.normals)
        new_armor.skin()
        armor_gts = MatTransform((0.000256, 1.547526, -120.343582))
        new_armor.set_global_to_skin(armor_gts)

        for b in the_armor.bone_weights.keys():
            new_armor.add_bone(b)
            new_armor.setShapeWeights(b, the_armor.bone_weights[b])
        
        new_nif.save()
            
    if TEST_BPY_ALL or TEST_IMP_EXP_FO4:
        print("## TEST_IMP_EXP_FO4 Can read the body nif and spit it back out (no blender shape)")

        nif = NifFile(os.path.join(pynifly_dev_path, "tests\FO4\BTMaleBody.nif"))
        assert "BaseMaleBody:0" in nif.getAllShapeNames(), "ERROR: Didn't read nif"

        the_body = nif.shape_dict["BaseMaleBody:0"]

        new_nif = NifFile()
        new_nif.initialize("FO4", os.path.join(pynifly_dev_path, "tests/Out/TestSkinnedFO03.nif"))
        new_nif.createSkin()
        
        new_body = new_nif.createShapeFromData("BaseMaleBody:0", 
                                                the_body.verts,
                                                the_body.tris,
                                                the_body.uvs,
                                                the_body.normals)
        new_body.skin()
        body_gts = MatTransform((0.000256, 1.547526, -120.343582))
        new_body.set_global_to_skin(body_gts)

        no_transform = MatTransform()
        for b in the_body.bone_weights.keys():
            new_body.add_bone(b)
            new_body.setShapeWeights(b, the_body.bone_weights[b])
        
        new_nif.save()
            

    if TEST_BPY_ALL or TEST_EXPORT_WEIGHTS:
        print("## TEST_EXPORT_WEIGHTS Import and export with weights")

        # Import body and armor
        f_in = NifFile(os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif"))
        import_nif(f_in)
        the_armor = bpy.data.objects["Armor"]
        the_body = bpy.data.objects["MaleBody"]
        assert 'NPC Foot.L' in the_armor.vertex_groups, f"ERROR: Left foot is in the groups: {the_armor.vertex_groups}"
        
        # Export armor
        filepath_armor = os.path.join(pynifly_dev_path, "tests/out/testArmorSkyrim02.nif")
        if os.path.exists(filepath_armor):
            os.remove(filepath_armor)
        export_shape_to(the_armor, filepath_armor, "SKYRIM")
        assert os.path.exists(filepath_armor), "ERROR: File not created"

        # Check armor
        ftest = NifFile(filepath_armor)
        assert ftest.shapes[0].name[0:5] == "Armor", "ERROR: Armor not read"
        gts = ftest.shapes[0].global_to_skin
        assert int(gts.translation[2]) == -120, "ERROR: Armor not offset"

        # Write armor to FO4 (wrong skeleton but whatevs, just see that it doesn't crash)
        filepath_armor_fo = os.path.join(pynifly_dev_path, r"tests\Out\testArmorFO02.nif")
        if os.path.exists(filepath_armor_fo):
            os.remove(filepath_armor_fo)
        export_shape_to(the_armor, filepath_armor_fo, "FO4")
        assert os.path.exists(filepath_armor_fo), f"ERROR: File {filepath_armor_fo} not created"

        # Write body 
        filepath_body = os.path.join(pynifly_dev_path, r"tests\Out\testBodySkyrim02.nif")
        body_out = NifFile()
        if os.path.exists(filepath_body):
            os.remove(filepath_body)
        export_shape_to(the_body, filepath_body, "SKYRIM")
        assert os.path.exists(filepath_body), f"ERROR: File {filepath_body} not created"
        # Should do some checking here

    if TEST_BPY_ALL or TEST_ROUND_TRIP:
        print("## TEST_ROUND_TRIP Can do the full round trip: nif -> blender -> nif -> blender")

        print("..Importing original file")
        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        armor1 = None
        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor1 = obj

        assert int(armor1.location.z) == 120, "ERROR: Armor moved above origin by 120 to skinned position"
        maxz = max([v.co.z for v in armor1.data.vertices])
        minz = min([v.co.z for v in armor1.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices are positioned below origin"

        print("..Exporting  to test file")
        outfile1 = os.path.join(pynifly_dev_path, "tests/Out/testSkyrim03.nif")
        if os.path.exists(outfile1):
            os.remove(outfile1)
        export_shape_to(armor1, outfile1, "SKYRIM")
        assert os.path.exists(outfile1), "ERROR: Created output file"

        print("..Re-importing exported file")
        nif2 = NifFile(outfile1)
        import_nif(nif2)

        armor2 = None
        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor2 = obj

        assert int(armor2.location.z) == 120, "ERROR: Exported armor is re-imported with same position"
        maxz = max([v.co.z for v in armor2.data.vertices])
        minz = min([v.co.z for v in armor2.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices from exported armor are positioned below origin"

    if TEST_BPY_ALL or TEST_UV_SPLIT:
        print("## TEST_UV_SPLIT Can split UVs properly")

        verts = [(-1.0, -1.0, 0.0), 
                 (1.0, -1.0, 0.0), (-1.0, 1.0, 0.0), (1.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)]
        norms = [(0.0, 0.0, 1.0), (0.0, 0.0, 2.0), (0.0, 0.0, 3.0), (0.0, 0.0, 4.0), (0.0, 0.0, 5.0), (0.0, 0.0, 6.0)]
        weights = [{0: 0.4},
                   {0: 0.6},
                   {0: 1.0},
                   {0: 0.8},
                   {0: 0.3},
                   {0: 0.1}]
        tris  = [(1, 5, 4),
                 (4, 2, 0),
                 (1, 3, 5),
                 (4, 5, 2)]
        loops = [1, 5, 4,
                 4, 2, 0,
                 1, 3, 5,
                 4, 5, 2]
        uvs = [(0.9, 0.1), # vert 1 (tri 0)
               (0.6, 0.9), # vert 5
               (0.6, 0.1), # vert 4
               (0.4, 0.1), # vert 4 (tri 1)
               (0.1, 0.9), # vert 2
               (0.1, 0.1), # vert 0
               (0.9, 0.1), # vert 1 (tri 2)
               (0.9, 0.9), # vert 3
               (0.6, 0.9), # vert 5
               (0.4, 0.1), # vert 4 (tri 3)
               (0.4, 0.9), # vert 5
               (0.1, 0.9)] # vert 2
        new_mesh = bpy.data.meshes.new("TestUV")
        new_mesh.from_pydata(verts, [], tris)
        newuv = new_mesh.uv_layers.new(do_init=False)
        for i, this_uv in enumerate(uvs):
            newuv.data[i].uv = this_uv
        new_object = bpy.data.objects.new("TestUV", new_mesh)
        bpy.context.collection.objects.link(new_object)

        filepath = os.path.join(pynifly_dev_path, "tests/Out/testUV01.nif")
        export_shape_to(new_object, filepath, "SKYRIM")

        nif_in = NifFile(filepath)
        plane = nif_in.shapes[0]
        assert len(plane.verts) == 8, "Error: Exported nif doesn't have correct verts"
        assert len(plane.uvs) == 8, "Error: Exported nif doesn't have correct UV"
        assert plane.verts[5] == plane.verts[7], "Error: Split vert at different locations"
        assert plane.uvs[5] != plane.uvs[7], "Error: Split vert has different UV locations"

    if TEST_BPY_ALL or TEST_CUSTOM_BONES:
        print('## TEST_CUSTOM_BONES Can handle custom bones correctly')

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\VulpineInariTailPhysics.nif")
        nif_in = NifFile(testfile)
        bone_xform = nif_in.nodes['Bone_Cloth_H_003'].xform_to_global
        import_nif(nif_in)

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\Tail01.nif")
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                export_shape_to(obj, outfile, "FO4")

        test_in = NifFile(outfile)
        new_xform = test_in.nodes['Bone_Cloth_H_003'].xform_to_global
        assert bone_xform == new_xform, \
            f"Error: Bone transform should not change. Expected\n {bone_xform}, found\n {new_xform}"

    if TEST_BPY_ALL or TEST_BPY_PARENT:
        print('### Maintain armature structure')

        # Can intuit structure if it's not in the file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif")
        nif = NifFile(testfile)
        import_nif(nif)
        for obj in bpy.context.selected_objects:
            if obj.name.startswith("Scene Root"):
                 assert obj.data.bones['NPC Hand.R'].parent.name == 'NPC Forearm.R', "Error: Should find forearm as parent"
                 print(f"Found parent to hand: {obj.data.bones['NPC Hand.R'].parent.name}")

        ## Can read structure if it comes from file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\bear_tshirt_turtleneck.nif")
        nif = NifFile(testfile)
        import_nif(nif)
        for obj in bpy.context.selected_objects:
            if obj.name.startswith("Scene Root"):
                assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
                assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3.R', "Error: Should find forearm as parent"
                print(f"Found parent to hand: {obj.data.bones['Arm_Hand.R'].parent.name}")
        print('### Maintain armature structure PASSED')

    if TEST_BPY_ALL or TEST_BABY:
        print('## TEST_BABY Can export baby parts')

        # Can intuit structure if it's not in the file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\baby.nif")
        nif = NifFile(testfile)
        import_nif(nif)
        head = bpy.data.objects['Baby_Head:0']
        eyes = bpy.data.objects['Baby_Eyes:0']

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\baby01.nif")
        outnif = NifFile()
        outnif.initialize("FO4", outfile)
        export_shape(outnif, TripFile(), eyes)
        export_shape(outnif, TripFile(), head)
        outnif.save()

        testnif = NifFile(outfile)
        testhead = testnif.shape_by_root('Baby_Head')
        testeyes = testnif.shape_by_root('Baby_Eyes')
        assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
        assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"

        # TODO: Test that baby's unkown skeleton is connected
      
    if TEST_BPY_ALL or TEST_CONNECTED_SKEL:
        print('## TEST_CONNECTED_SKEL Can import connected skeleton')

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\vanillaMaleBody.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        #print("FO4 LArm_UpperTwist1: ", nif.get_node_xform_to_global('LArm_UpperTwist1') )
        #print("FO4 LArm_UpperTwist1_skin: ", nif.get_node_xform_to_global('LArm_UpperTwist1_skin') )

        for s in bpy.context.selected_objects:
            if 'MaleBody.nif' in s.name:
                assert 'Leg_Thigh.L' in s.data.bones.keys(), "Error: Should have left thigh"
                assert s.data.bones['Leg_Thigh.L'].parent.name == 'Pelvis', "Error: Thigh should connect to pelvis"

    if TEST_BPY_ALL or TEST_SKEL:
        print('## TEST_SKEL Can import skeleton file with no shapes')

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"skeletons\FO4\skeleton.nif")

        nif = NifFile(testfile)
        import_nif(nif)

        arma = bpy.data.objects["skeleton.nif"]
        assert 'Leg_Thigh.L' in arma.data.bones, "Error: Should have left thigh"

    if TEST_BPY_ALL or TEST_TRI:
        print("## TEST_TRI Can load a tri file into an existing mesh")

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\CheetahMaleHead.nif")
        testtri2 = os.path.join(pynifly_dev_path, r"tests\FO4\CheetahMaleHead.tri")
        testtri3 = os.path.join(pynifly_dev_path, r"tests\FO4\CheetahMaleHead.tri")
        testout2 = os.path.join(pynifly_dev_path, r"tests\Out\CheetahMaleHead02.nif")
        testout2tri = os.path.join(pynifly_dev_path, r"tests\Out\CheetahMaleHead02.tri")
        testout2chg = os.path.join(pynifly_dev_path, r"tests\Out\CheetahMaleHead02_chargen.tri")
        tricubenif = os.path.join(pynifly_dev_path, r"tests\Out\tricube01.nif")
        tricubeniftri = os.path.join(pynifly_dev_path, r"tests\Out\tricube01.tri")
        tricubenifchg = os.path.join(pynifly_dev_path, r"tests\Out\tricube01_chargen.tri")
        for f in [testout2, testout2tri, testout2chg, tricubenif]:
            if os.path.exists(f):
                os.remove(f)

        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        if obj.type == "ARMATURE":
            obj = obj.children[0]
            bpy.context.view_layer.objects.active = obj

        log.debug(f"Importing tri with {bpy.context.object.name} selected")
        triobj2 = import_tri(testtri2)

        assert len(obj.data.shape_keys.key_blocks) == 47, f"Error: {obj.name} should have enough keys ({len(obj.data.shape_keys.key_blocks)})"

        print("### Can import a simple tri file")

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = None
        triobj = import_tri(testtri3)
        assert triobj.name.startswith("CheetahMaleHead.tri"), f"Error: Should be named like tri file, found {triobj.name}"
        assert "LJaw" in triobj.data.shape_keys.key_blocks.keys(), "Error: Should be no keys missing"
        
        print('### Can export a shape with tris')

        export_shape_to(triobj, os.path.join(pynifly_dev_path, testout2), "FO4")
        
        print('### Exported shape and tri match')
        nif2 = NifFile(os.path.join(pynifly_dev_path, testout2))
        tri2 = TriFile.from_file(os.path.join(pynifly_dev_path, testout2tri))
        assert not os.path.exists(testout2chg), f"{testout2chg} should not have been created"
        assert len(nif2.shapes[0].verts) == len(tri2.vertices), f"Error vert count should match, {len(nif2.shapes[0].verts)} vs {len(tri2.vertices)}"
        assert len(nif2.shapes[0].tris) == len(tri2.faces), f"Error vert count should match, {len(nif2.shapes[0].tris)} vs {len(tri2.faces)}"
        assert tri2.header.morphNum == len(triobj.data.shape_keys.key_blocks)-1, \
            f"Error: morph count should match, file={tri2.header.morphNum} vs {triobj.name}={len(triobj.data.shape_keys.key_blocks)}"
        
        print('### Tri and chargen export as expected')

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TriCube"
        sk1 = cube.shape_key_add()
        sk1.name = "Aah"
        sk2 = cube.shape_key_add()
        sk2.name = "CombatAnger"
        sk3 = cube.shape_key_add()
        sk3.name = "*Extra"
        sk4 = cube.shape_key_add()
        sk4.name = "BrowIn"
        export_shape_to(cube, tricubenif, "SKYRIM")

        assert os.path.exists(tricubenif), f"Error: Should have exported {tricubenif}"
        assert os.path.exists(tricubeniftri), f"Error: Should have exported {tricubeniftri}"
        assert os.path.exists(tricubenifchg), f"Error: Should have exported {tricubenifchg}"
        
        cubetri = TriFile.from_file(tricubeniftri)
        assert "Aah" in cubetri.morphs, f"Error: 'Aah' should be in tri"
        assert "BrowIn" not in cubetri.morphs, f"Error: 'BrowIn' should not be in tri"
        assert "*Extra" not in cubetri.morphs, f"Error: '*Extra' should not be in tri"
        
        cubechg = TriFile.from_file(tricubenifchg)
        assert "Aah" not in cubechg.morphs, f"Error: 'Aah' should not be in chargen"
        assert "BrowIn" in cubechg.morphs, f"Error: 'BrowIn' should be in chargen"
        assert "*Extra" not in cubechg.morphs, f"Error: '*Extra' should not be in chargen"
        

    if TEST_BPY_ALL or TEST_0_WEIGHTS:
        print("## TEST_0_WEIGHTS Gives warning on export with 0 weights")

        baby = append_collection("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
        baby.parent.name == "BabyExportRoot", f"Error: Should have baby and armature"
        log.debug(f"Found object {baby.name}")
        export_shape_to(baby, os.path.join(pynifly_dev_path, r"tests\Out\weight0.nif"), "FO4")
        assert "*UNWEIGHTED*" in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


    if TEST_BPY_ALL or TEST_SPLIT_NORMAL:
        print("## TEST_SPLIT_NORMAL Can handle meshes with split normals")

        plane = append_collection("Plane", False, r"tests\skyrim\testSplitNormalPlane.blend", r"\Object", "Plane")
        export_shape_to(plane, os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), "FO4")


    if TEST_BPY_ALL or TEST_PARTITIONS:
        print("## TEST_PARTITIONS Can read Skyrim partions")
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/MaleHead.nif")

        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        assert "SBP_130_HEAD" in obj.vertex_groups, "Skyrim body parts read in as vertex groups with sensible names"

        print("### Can write Skyrim partitions")
        export_shape_to(obj, os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"), "SKYRIM")
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"))
        assert len(nif2.shapes[0].partitions) == 3, "Have all skyrim partitions"
        assert nif2.shapes[0].partitions[2].id == 143, "Have ears"

    if TEST_BPY_ALL or TEST_SEGMENTS:
        print("### Can read FO4 segments")
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/VanillaMaleBody.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        assert "FO4 Human 2" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "FO4 segment file read and saved for later use"

        print("### Can write FO4 segments")
        export_shape_to(obj, os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"), "FO4")
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"))
        assert len(nif2.shapes[0].partitions) == 7, "Have all FO4 partitions"

    print("""
    ############################################################
    ##                                                        ##
    ##                    TESTS DONE                          ##
    ##                                                        ##
    ############################################################
    """)


if __name__ == "__main__":
    try:
        do_run_tests = False
        if RUN_TESTS == True:
            do_run_tests = True
    except:
        do_run_tests == False
        
    if not do_run_tests:
        try:
            unregister()
        except:
            pass
        register()
    else:
        try:
            run_tests()
        except:
            traceback.print_exc()


# To do: 
# - Don't export chargen tri if no chargens - test that _ and * aren't exported
# - Hook new mesh to existing armature, if selected
