"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.


RUN_TESTS = True
TEST_BPY_ALL = False


bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (3, 0, 0),
    "version": (5, 7, 0),  
    "location": "File > Import-Export",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

import sys
import os
import os.path
import pathlib
import logging
from operator import or_
from functools import reduce
import traceback
import math
from mathutils import Matrix, Vector, Quaternion, geometry
# import quickhull
import re
import codecs
from typing import Collection

logging.basicConfig(encoding='utf-8', level=logging.DEBUG)
log = logging.getLogger("pynifly")
log.info(f"Loading pynifly version {bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}")

nifly_path = None
if 'PYNIFLY_DEV_ROOT' in os.environ:
    pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
    pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")
    nifly_path = os.path.join(pynifly_dev_root, r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll")

if nifly_path and os.path.exists(nifly_path):
    log.debug(f"PyNifly dev path: {pynifly_dev_path}")
    if pynifly_dev_path not in sys.path:
        sys.path.insert(0, pynifly_dev_path)
    if RUN_TESTS:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
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

from nifdefs import *
from niflytools import *
from pynifly import *
from trihandler import *
import pyniflywhereami

import bpy
import bpy_types
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

NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"
ALPHA_MAP_NAME = "VERTEX_ALPHA"

GLOSS_SCALE = 100

COLLISION_COLOR = (0.559, 0.624, 1.0, 0.5)

BONE_LEN = 5
ROLL_ADJUST = 0 # -pi/2


class ImportFlags(IntFlag):
    CREATE_BONES = 1
    RENAME_BONES = 1 << 1
    ROTATE_MODEL = 1 << 2
    PRESERVE_HIERARCHY = 1 << 3


def MatrixLocRotScale(loc, rot, scale):
    try:
        return Matrix.LocRotScale(loc, rot, scale)
    except:
        pass

    tm = Matrix.Translation(loc)
    rm = Matrix()
    if issubclass(rot.__class__, Quaternion):
        rm = rot.to_matrix()
    else:
        rm = Matrix(rot)
    rm = rm.to_4x4()
    sm = Matrix(((scale[0],0,0,0),
                    (0,scale[1],0,0),
                    (0,0,scale[2],0),
                    (0,0,0,1)))
    m = tm @ rm @ sm
    return m

def transform_to_matrix(xf: TransformBuf) -> Matrix:
    """ Extends TransformBuf to get/give contents as a Blender Matrix """
    return MatrixLocRotScale(xf.translation[:], 
                             Matrix([xf.rotation[0][:],
                                     xf.rotation[1][:], 
                                     xf.rotation[2][:] ]), 
                             [xf.scale]*3)

setattr(TransformBuf, "as_matrix", transform_to_matrix)

def transform_from_matrix(buf: TransformBuf, m: Matrix):
    t, q, s, = m.decompose()
    buf.translation = t[:]
    r = q.to_matrix()
    buf.rotation = MATRIX3(r[0][:], r[1][:], r[2][:])
    buf.scale = max(s[:])

setattr(TransformBuf, "load_matrix", transform_from_matrix)

def make_transformbuf(cls, m: Matrix) -> TransformBuf:
    """ Return a new TransformBuf filled with the data in the matrix """
    buf = TransformBuf()
    buf.load_matrix(m)
    return buf

setattr(TransformBuf, "from_matrix", classmethod(make_transformbuf))


#GAME_BONE_Q = {"FO4": Quaternion((1, 0, 0), radians(-90)),
#               "SKYRIM": Quaternion((0, 0, 1), radians(-90)),
#               "SKYRIMSE": Quaternion((0, 0, 1), radians(-90))}

#GAME_BONE_VECTOR = {"FO4": Vector((5, 0, 0)),
#                    "SKYRIM": Vector((0, 0, 5)),
#                    "SKYRIMSE": Vector((0, 0, 5))}

#def bone_game_adjust(game: str, inverse=False) -> Vector:
#    if game in GAME_BONE_VECTOR:
#        return GAME_BONE_VECTOR[game].copy()
#    return GAME_BONE_VECTOR["SKYRIM"].copy()


bone_vectors = {'X': Vector((1,0,0)), 'Z': Vector((0,0,1))}
game_axes = {'FO4': 'X', 'SKYRIM': 'Z', 'SKYRIMSE': 'Z'}

def qtobone(boneq:Quaternion, axis:str):
    """ Taxes a rotation and axis and applies the rotation to a unit vector
    on that axis. Returns resulting vector and twist. """
    s, t = boneq.to_swing_twist(axis)
    v = bone_vectors[axis].copy()
    v.rotate(boneq)
    return v, t

def transform_to_bone(game:str, nodexf:Matrix):
    """ Turns a nif bone global transform into the equivalent Blender bone 
        nodexf = bone transform (4x4 Matrix)
        parentxf = bone transform of parent, if any
        game = game we are making the bone for
        returns: 
            vector = head location
            vector = tail location
            float = roll to apply to bone
    """
    bonehead, rot, s = nodexf.decompose()
    axis = game_axes[game]
    bonevec, roll = qtobone(rot, axis)
    return bonehead, bonehead + (bonevec * BONE_LEN), roll + ROLL_ADJUST 

#def bone_to_transform(game, bonehead:Vector, boneaxis:Vector, boneroll:float) -> Matrix:
#    ax = boneaxis.copy()
#    bonevec = bone_game_adjust(game)
#    q = bonevec.rotation_difference(boneaxis)
#    rollq = Quaternion(bonevec, boneroll)
#    q.rotate(rollq)
#    return MatrixLocRotScale(bonehead, q, (1,1,1))

def bonetoq(vec:Vector, roll:float, axis:str):
    """ Takes a vector, roll angle, and axis and returns a quaternion that
    rotates the unit vector on the axis to the input vector, with the roll."""
    bv = bone_vectors[axis].copy()
    q = bv.rotation_difference(vec)
    rollq = Quaternion(bv, roll - ROLL_ADJUST)
    return q @ rollq

def get_bone_global_xf(bone:bpy_types.Bone, game:str) -> Quaternion:
    """ Return the global transform represented by the bone. 
        TODO: Calculate based on the bone head, tail, and roll
    """
    if 'pynXform' in bone:
        # If stashed transform exists, use it for backwards compatibility
        rot = Quaternion(bone['pynXform'])
        loc = bone.head_local
        mx = MatrixLocRotScale(bone.head_local, rot, (1,1,1))
    else:
        vec = (bone.tail_local-bone.head_local)/BONE_LEN
        baxis, broll = bone.AxisRollFromMatrix(bone.matrix_local.to_3x3(), axis=vec)
        rot = bonetoq(vec, broll, game_axes[game])
        mx = MatrixLocRotScale(bone.head_local, rot, (1,1,1))

    return mx


def is_in_plane(plane, vert):
    """ Test whether vert is in the plane defined by the three vectors in plane """
    #find the plane's normal. p0, p1, and p2 are simply points on the plane (in world space)
 
    # Get vector normal to plane
    v1 = plane[0] - plane[1]
    v2 = plane[2] - plane[1]
    normal = v1.cross(v2)
    normal.normalize()

    # Get vector from vertex to a point on the plane
    t = vert - plane[0]
    t.normalize()

    # If the dot product is 0, point is on plane
    dp = normal.dot(t)

    return round(dp, 4) == 0.0

def append_if_new(theList, theVector, errorfactor):
    """ Append vector to list if not already present (to within errorfactor) """
    for a in theList:
        if VNearEqual(a, theVector, epsilon=errorfactor):
            return
    theList.append(theVector)


# ######################################################################## ###
#                                                                          ###
# -------------------------------- IMPORT -------------------------------- ###
#                                                                          ###
# ######################################################################## ###

# -----------------------------  SHADERS  -------------------------------

def get_image_node(node_input):
    """Walk the shader nodes backwards until a texture node is found.
        node_input = the shader node input to follow; may be null"""
    n = None
    if node_input and len(node_input.links) > 0: 
        n = node_input.links[0].from_node

    while n and type(n) != bpy.types.ShaderNodeTexImage:
        if 'Base Color' in n.inputs.keys() and n.inputs['Base Color'].is_linked:
            n = n.inputs['Base Color'].links[0].from_node
        elif 'Image' in n.inputs.keys() and n.inputs['Image'].is_linked:
            n = n.inputs['Image'].links[0].from_node
        elif 'Color' in n.inputs.keys() and n.inputs['Color'].is_linked:
            n = n.inputs['Color'].links[0].from_node
        elif 'R' in n.inputs.keys() and n.inputs['R'].is_linked:
            n = n.inputs['R'].links[0].from_node
    return n

def find_shader_node(nodelist, idname):
    return next((x for x in nodelist if x.bl_idname == idname), None)

def import_shader_attrs(material, shader, shape):
    attrs = shape.shader_attributes
    if not attrs: 
        return

    attrs.extract(material)

    try:
        material['BS_Shader_Block_Name'] = shape.shader_block_name
        material['BSLSP_Shader_Name'] = shape.shader_name
        shader.inputs['Emission'].default_value = (attrs.Emissive_Color_R, attrs.Emissive_Color_G, attrs.Emissive_Color_B, attrs.Emissive_Color_A)
        shader.inputs['Emission Strength'].default_value = attrs.Emissive_Mult

        if shape.shader_block_name == 'BSLightingShaderProperty':
            shader.inputs['Alpha'].default_value = attrs.Alpha
            shader.inputs['Metallic'].default_value = attrs.Glossiness/GLOSS_SCALE
        elif shape.shader_block_name == 'BSEffectShaderProperty':
            shader.inputs['Alpha'].default_value = attrs.Falloff_Start_Opacity

    except Exception as e:
        # Any errors, print the error but continue
        log.warning(str(e))

def import_shader_alpha(mat, shape):
    if shape.has_alpha_property:
        mat.alpha_threshold = shape.alpha_property.threshold
        if shape.alpha_property.flags & 1:
            mat.blend_method = 'BLEND'
            mat.alpha_threshold = shape.alpha_property.threshold/255
        else:
            mat.blend_method = 'CLIP'
            mat.alpha_threshold = shape.alpha_property.threshold/255
        mat['NiAlphaProperty_flags'] = shape.alpha_property.flags
        mat['NiAlphaProperty_threshold'] = shape.alpha_property.threshold
        return True
    else:
        return False

def obj_create_material(obj, shape):
    img_offset_x = -1200
    cvt_offset_x = -300
    inter1_offset_x = -900
    inter2_offset_x = -700
    inter3_offset_x = -500
    offset_y = -300
    yloc = 0

    nifpath = shape.file.filepath

    fulltextures = extend_filenames(nifpath, "meshes", shape.textures)
    missing = missing_files(fulltextures)
    if len(missing) > 0:
        log.warning(f". . Some texture files not found: {missing}")
    log.debug(". . creating material")

    mat = bpy.data.materials.new(name=(obj.name + ".Mat"))

    # Stash texture strings for future export
    for i, t in enumerate(shape.textures):
        mat['BSShaderTextureSet_' + str(i)] = t

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bdsf = nodes.get("Principled BSDF")

    import_shader_attrs(mat, bdsf, shape)
    has_alpha = import_shader_alpha(mat, shape)

    # --- Diffuse --

    txtnode = nodes.new("ShaderNodeTexImage")
    try:
        img = bpy.data.images.load(fulltextures[0], check_existing=True)
        img.colorspace_settings.name = "sRGB"
        txtnode.image = img
    except:
        pass
    txtnode.location = (bdsf.location[0] + img_offset_x, bdsf.location[1])
    
    mat.node_tree.links.new(txtnode.outputs['Color'], bdsf.inputs['Base Color'])
    if has_alpha:
        mat.node_tree.links.new(txtnode.outputs['Alpha'], bdsf.inputs['Alpha'])

    yloc = txtnode.location[1] + offset_y

    matlinks = mat.node_tree.links

    # --- Subsurface --- 

    if fulltextures[2] != "": 
        # Have a sk separate from a specular
        skimgnode = nodes.new("ShaderNodeTexImage")
        try:
            skimg = bpy.data.images.load(fulltextures[2], check_existing=True)
            if skimg != txtnode.image:
                skimg.colorspace_settings.name = "Non-Color"
            skimgnode.image = skimg
        except:
            pass
        skimgnode.location = (txtnode.location[0], yloc)
        matlinks.new(skimgnode.outputs['Color'], bdsf.inputs["Subsurface Color"])
        yloc = skimgnode.location[1] + offset_y
        
    # --- Specular --- 

    if fulltextures[7] != "":
        simgnode = nodes.new("ShaderNodeTexImage")
        try:
            simg = bpy.data.images.load(fulltextures[7], check_existing=True)
            simg.colorspace_settings.name = "Non-Color"
            simgnode.image = simg
        except:
            pass
        simgnode.location = (txtnode.location[0], yloc)

        if shape.file.game in ["FO4"]:
            # specular combines gloss and spec
            seprgb = nodes.new("ShaderNodeSeparateRGB")
            seprgb.location = (bdsf.location[0] + cvt_offset_x, yloc)
            matlinks.new(simgnode.outputs['Color'], seprgb.inputs['Image'])
            matlinks.new(seprgb.outputs['R'], bdsf.inputs['Specular'])
            matlinks.new(seprgb.outputs['G'], bdsf.inputs['Metallic'])
        else:
            matlinks.new(simgnode.outputs['Color'], bdsf.inputs['Specular'])
            # bdsf.inputs['Metallic'].default_value = 0
            
        yloc = simgnode.location[1] + offset_y

    # --- Normal Map --- 
    
    if fulltextures[1] != "":
        nmap = nodes.new("ShaderNodeNormalMap")
        if shape.shader_attributes and shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
            nmap.space = "OBJECT"
        else:
            nmap.space = "TANGENT"
        nmap.location = (bdsf.location[0] + cvt_offset_x, yloc)
        
        nimgnode = nodes.new("ShaderNodeTexImage")
        try:
            nimg = bpy.data.images.load(fulltextures[1], check_existing=True) 
            nimg.colorspace_settings.name = "Non-Color"
            nimgnode.image = nimg
        except:
            pass
        nimgnode.location = (txtnode.location[0], yloc)
        
        if shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
            # Need to swap green and blue channels for blender
            rgbsep = nodes.new("ShaderNodeSeparateRGB")
            rgbcomb = nodes.new("ShaderNodeCombineRGB")
            matlinks.new(rgbsep.outputs['R'], rgbcomb.inputs['R'])
            matlinks.new(rgbsep.outputs['G'], rgbcomb.inputs['B'])
            matlinks.new(rgbsep.outputs['B'], rgbcomb.inputs['G'])
            matlinks.new(rgbcomb.outputs['Image'], nmap.inputs['Color'])
            matlinks.new(nimgnode.outputs['Color'], rgbsep.inputs['Image'])
            rgbsep.location = (bdsf.location[0] + inter1_offset_x, yloc)
            rgbcomb.location = (bdsf.location[0] + inter2_offset_x, yloc)
        elif shape.file.game == 'FO4':
            # Need to invert the green channel for blender
            rgbsep = nodes.new("ShaderNodeSeparateRGB")
            rgbcomb = nodes.new("ShaderNodeCombineRGB")
            colorinv = nodes.new("ShaderNodeInvert")
            matlinks.new(rgbsep.outputs['R'], rgbcomb.inputs['R'])
            matlinks.new(rgbsep.outputs['B'], rgbcomb.inputs['B'])
            matlinks.new(rgbsep.outputs['G'], colorinv.inputs['Color'])
            matlinks.new(colorinv.outputs['Color'], rgbcomb.inputs['G'])
            matlinks.new(rgbcomb.outputs['Image'], nmap.inputs['Color'])
            matlinks.new(nimgnode.outputs['Color'], rgbsep.inputs['Image'])
            rgbsep.location = (bdsf.location[0] + inter1_offset_x, yloc)
            rgbcomb.location = (bdsf.location[0] + inter3_offset_x, yloc)
            colorinv.location = (bdsf.location[0] + inter2_offset_x, yloc - rgbcomb.height * 0.9)
        else:
            matlinks.new(nimgnode.outputs['Color'], nmap.inputs['Color'])
            nmap.location = (bdsf.location[0] + inter2_offset_x, yloc)
                         
        matlinks.new(nmap.outputs['Normal'], bdsf.inputs['Normal'])

        if shape.file.game in ["SKYRIM", "SKYRIMSE"] and \
            shape.shader_attributes and \
            not shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
            # Specular is in the normal map alpha channel
            matlinks.new(nimgnode.outputs['Alpha'], bdsf.inputs['Specular'])
            
        
    obj.active_material = mat

def export_shader_attrs(obj, shader, shape):
    mat = obj.active_material

    if 'BSLSP_Shader_Name' in mat.keys() and len(mat['BSLSP_Shader_Name']) > 0:
        shape.shader_name = mat['BSLSP_Shader_Name']

    shape.shader_attributes.load(mat)

    shape.shader_attributes.Emissive_Color_R = shader.inputs['Emission'].default_value[0]
    shape.shader_attributes.Emissive_Color_G = shader.inputs['Emission'].default_value[1]
    shape.shader_attributes.Emissive_Color_B = shader.inputs['Emission'].default_value[2]
    shape.shader_attributes.Emissive_Color_A = shader.inputs['Emission'].default_value[3]
    shape.shader_attributes.Emissive_Mult = shader.inputs['Emission Strength'].default_value

    if shape.shader_block_name == "BSLightingShaderProperty":
        shape.shader_attributes.Alpha = shader.inputs['Alpha'].default_value
        shape.shader_attributes.Glossiness = shader.inputs['Metallic'].default_value * GLOSS_SCALE


def has_msn_shader(obj):
    val = False
    if obj.active_material:
        nodelist = obj.active_material.node_tree.nodes
        shader_node = find_shader_node(nodelist, 'ShaderNodeBsdfPrincipled')
        normal_input = shader_node.inputs['Normal']
        if normal_input and normal_input.is_linked:
            nmap_node = normal_input.links[0].from_node
            if nmap_node.bl_idname == 'ShaderNodeNormalMap' and nmap_node.space == "OBJECT":
                val = True
    return val


def read_object_texture(mat: bpy.types.Material, index: int):
    """Return the index'th texture in the saved texture custom properties"""
    n = 'BSShaderTextureSet_' + str(index)
    try:
        return mat[n]
    except:
        return None


def set_object_texture(shape: NiShape, mat: bpy.types.Material, i: int):
    t = read_object_texture(mat, i)
    if t:
        shape.set_texture(i, t)



# -----------------------------  MESH CREATION -------------------------------

def mesh_create_normals(the_mesh, normals):
    """ Create custom normals in Blender to match those on the object 
        normals = [(x, y, z)... ] 1:1 with mesh verts
        """
    if normals:
        the_mesh.use_auto_smooth = True
        the_mesh.normals_split_custom_set([(0, 0, 0) for l in the_mesh.loops])
        the_mesh.normals_split_custom_set_from_vertices(normals)


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

def mesh_create_bone_groups(the_shape, the_object, do_name_xlate):
    """ Create groups to capture bone weights """
    vg = the_object.vertex_groups
    for bone_name in the_shape.bone_names:
        if do_name_xlate:
            xlate_name = the_shape.file.blender_name(bone_name)
        else:
            xlate_name = bone_name
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
        if type(p) == FO4Segment:
            for sseg in p.subsegments:
                log.debug(f"..found subsegment {sseg.name}")
                new_vg = vg.new(name=sseg.name)
                partn_groups.append(new_vg)
    for part_idx, face in zip(the_shape.partition_tris, mesh.polygons):
        if part_idx < len(partn_groups):
            this_vg = partn_groups[part_idx]
            for lp in face.loop_indices:
                this_loop = mesh.loops[lp]
                this_vg.add((this_loop.vertex_index,), 1.0, 'ADD')
    if len(the_shape.segment_file) > 0:
        log.debug(f"..Putting segment file '{the_shape.segment_file}' on '{the_object.name}'")
        the_object['FO4_SEGMENT_FILE'] = the_shape.segment_file


def import_colors(mesh, shape):
    log.debug(f"Have shaderflags1: {ShaderFlags1(shape.shader_attributes.Shader_Flags_1).fullname}")
    log.debug(f"Have shaderflags2: {ShaderFlags2(shape.shader_attributes.Shader_Flags_2).fullname}")
    try:
        if (shape.shader_attributes.Shader_Flags_2 & ShaderFlags2.VERTEX_COLORS) \
            and shape.colors and len(shape.colors) > 0:
            log.debug(f"..Importing vertex colors for {shape.name}")
            clayer = mesh.vertex_colors.new()
            alphlayer = None
            if shape.shader_attributes.Shader_Flags_1 & ShaderFlags1.VERTEX_ALPHA:
                alphlayer = mesh.vertex_colors.new()
                alphlayer.name = ALPHA_MAP_NAME
        
            colors = shape.colors
            for lp in mesh.loops:
                c = colors[lp.vertex_index]
                clayer.data[lp.index].color = (c[0], c[1], c[2], 1.0)
                if alphlayer:
                    alph = colors[lp.vertex_index][3]
                    alphlayer.data[lp.index].color = [alph, alph, alph, 1.0]
    except:
        log.error(f"ERROR: Could not read colors on shape {shape.name}")


def get_node_transform(the_node) -> Matrix:
    """ Returns location of the_node ready for blender as a transform """
    try:
        if the_node.has_skin_instance:
            # Global-to-skin transform is what offsets all the vertices together, e.g. so that
            # heads can be positioned at the origin. Put the reverse transform on the blender 
            # object so they can be worked on in their skinned position.
            # Use the one on the NiSkinData if it exists.
            xform = the_node.global_to_skin_data
            if xform is None:
                xform = the_node.global_to_skin
            xf = xform.as_matrix()
            xf.invert()
            return xf
    except:
        pass

    # Statics get transformed according to the shape's transform
    xf = the_node.transform # transform
    log.debug(f". . shape {the_node.name} transform: {xf}")
    return xf.as_matrix()


class NifImporter():
    """Does the work of importing a nif, independent of Blender's operator interface"""
    def __init__(self, 
                 filename: str, 
                 f: ImportFlags = ImportFlags.CREATE_BONES | ImportFlags.RENAME_BONES):
        self.filename = filename
        self.flags = f
        self.armature = None
        self.bones = set()
        self.objects_created = {} # Dictionary of objects created, indexed by node handle
        self.nif = NifFile(filename)
        self.loc = [0, 0, 0]   # location for new objects 

    def incr_loc(self):
        self.loc = list(map(sum, zip(self.loc, [0.5, 0.5, 0.5])))

    def next_loc(self):
        l = self.loc
        self.incr_loc()
        return l

    # -----------------------------  EXTRA DATA  -------------------------------

    def import_extra(self, f: NifFile):
        """ Import any extra data from the root, and create corresponding shapes 
            Returns a list of the new extradata objects
        """
        # extradata = []

        for s in f.string_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "NiStringExtraData"
            ed.show_name = True
            ed['NiStringExtraData_Name'] = s[0]
            ed['NiStringExtraData_Value'] = s[1]
            # extradata.append(ed)
            self.objects_created[s[0] + s[1]] = ed

        for s in f.behavior_graph_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSBehaviorGraphExtraData"
            ed.show_name = True
            ed['BSBehaviorGraphExtraData_Name'] = s[0]
            ed['BSBehaviorGraphExtraData_Value'] = s[1]
            ed['BSBehaviorGraphExtraData_CBS'] = s[2]
            # extradata.append(ed)
            self.objects_created[s[0] + s[1]] = ed

        for c in f.cloth_data: 
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSClothExtraData"
            ed.show_name = True
            ed['BSClothExtraData_Name'] = c[0]
            ed['BSClothExtraData_Value'] = codecs.encode(c[1], 'base64')
            # extradata.append(ed)
            self.objects_created[c[0]] = ed

        b = f.bsx_flags
        if b:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSXFlags"
            ed.show_name = True
            ed['BSXFlags_Name'] = b[0]
            ed['BSXFlags_Value'] = BSXFlags(b[1]).fullname
            # extradata.append(ed)
            self.objects_created[b[0]] = ed

        invm = f.inventory_marker
        if invm:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSInvMarker"
            ed.show_name = True
            ed['BSInvMarker_Name'] = invm[0]
            ed['BSInvMarker_RotX'] = invm[1]
            ed['BSInvMarker_RotY'] = invm[2]
            ed['BSInvMarker_RotZ'] = invm[3]
            ed['BSInvMarker_Zoom'] = invm[4]
            # extradata.append(ed)
            self.objects_created[invm[0]] = ed

        for fm in f.furniture_markers:
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            obj = bpy.context.object
            obj.name = "BSFurnitureMarkerNode"
            obj.show_name = True
            obj.empty_display_type = 'SINGLE_ARROW'
            obj.location = fm.offset[:]
            obj.rotation_euler = (-pi/2, 0, fm.heading)
            obj.scale = (40,10,10)
            obj['AnimationType'] = FurnAnimationType.GetName(fm.animation_type)
            obj['EntryPoints'] = FurnEntryPoints(fm.entry_points).fullname

        #return extradata


    def import_shape_extra(self, obj, shape):
        """ Import any extra data from the shape if given or the root if not, and create 
        corresponding shapes """
        loc = list(obj.location)
        self.incr_loc()

        for s in shape.string_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "NiStringExtraData"
            ed.show_name = True
            ed['NiStringExtraData_Name'] = s[0]
            ed['NiStringExtraData_Value'] = s[1]
            ed.parent = obj
            self.objects_created[str(shape._handle) + s[0]] = ed
            #extradata.append(ed)

        for s in shape.behavior_graph_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSBehaviorGraphExtraData"
            ed.show_name = True
            ed['BSBehaviorGraphExtraData_Name'] = s[0]
            ed['BSBehaviorGraphExtraData_Value'] = s[1]
            ed.parent = obj
            self.objects_created[str(shape._handle) + s[0]] = ed
            #extradata.append(ed)

        #return extradata


    def import_node_parents(self, node):
        """ Import the chain of parents of the given node all the way up to the root """
        nif = node.file
        # Get list of parents of the given node from the list, bottom-up. 
        parents = []
        n = node.parent
        while n:
            parents.insert(0, n)
            n = n.parent

        # Create the parents top-down
        obj = None
        p = None
        for ch in parents[1:]: # [0] is the root node
            if ch._handle not in self.objects_created:
                bpy.ops.object.add(radius=1.0, type='EMPTY')
                obj = bpy.context.object
                obj.name = ch.name
                obj["pynBlock_Name"] = ch.blockname
                obj.matrix_local = ch.transform.as_matrix()
                obj.parent = p
                p = obj
                self.objects_created[ch._handle] = obj
                log.debug(f". . Created node {ch.name}")

                if ch.collision_object:
                    self.import_collision_obj(ch.collision_object, obj)
            else:
                obj = self.objects_created[ch._handle]

        return obj

    def import_shape(self, the_shape: NiShape):
        """ Import the shape to a Blender object, translating bone names 
            self.objects_created = Set to a list of objects created. Might be more than one
            because of extra data nodes.
        """
        log.debug(f". Importing shape {the_shape.name}")
        v = the_shape.verts
        t = the_shape.tris

        new_mesh = bpy.data.meshes.new(the_shape.name)
        new_mesh.from_pydata(v, [], t)
        new_object = bpy.data.objects.new(the_shape.name, new_mesh)
        self.objects_created[the_shape._handle] = new_object
    
        import_colors(new_mesh, the_shape)

        log.info(f". . import flags: {self.flags}")
        parent = self.import_node_parents(the_shape)
        new_object.matrix_world = get_node_transform(the_shape)
        if parent:
            new_object.parent = parent

        if self.flags & ImportFlags.ROTATE_MODEL:
            log.info(f". . Rotating model to match blender")
            r = new_object.rotation_euler[:]
            new_object.rotation_euler = (r[0], r[1], r[2]+pi)
            new_object["PYNIFLY_IS_ROTATED"] = True

        mesh_create_uv(new_object.data, the_shape.uvs)
        mesh_create_bone_groups(the_shape, new_object, self.flags & ImportFlags.RENAME_BONES)
        mesh_create_partition_groups(the_shape, new_object)
        for f in new_mesh.polygons:
            f.use_smooth = True

        new_mesh.update(calc_edges=True, calc_edges_loose=True)
        new_mesh.validate(verbose=True)

        if the_shape.normals:
            mesh_create_normals(new_object.data, the_shape.normals)
        new_mesh.calc_normals_split()

        obj_create_material(new_object, the_shape)
        
        # Root block type goes on the shape object because there isn't another good place
        # to put it.
        f = the_shape.file
        root = f.nodes[f.rootName]
        if root.blockname != "NiNode":
            new_object["pynRootNode_BlockType"] = root.blockname
        new_object["pynRootNode_Name"] = root.name
        new_object["pynRootNode_Flags"] = RootFlags(root.flags).fullname

        if the_shape.collision_object:
            self.import_collision_obj(the_shape.collision_object, new_object)

        self.import_shape_extra(new_object, the_shape)

        new_object['PYN_GAME'] = self.nif.game
        new_object['PYN_RENAME_BONES'] = ((self.flags & ImportFlags.RENAME_BONES) != 0)
        new_object['PYN_PRESERVE_HIERARCHY'] = ((self.flags & ImportFlags.PRESERVE_HIERARCHY) != 0)


    def add_bone_to_arma(self, name, nifname):
        """ Add bone to armature. Bone may come from nif or reference skeleton.
            name = name to use for the bone in blender 
            nifname = name the bone has in the nif
            returns new bone
        """
        armdata = self.armature.data

        if name in armdata.edit_bones:
            return None
    
        # use the transform in the file if there is one; otherwise get the 
        # transform from the reference skeleton
        xf = self.nif.get_node_xform_to_global(nifname) 
        # log.debug(f"Found bone transform {name} ({nifname}) = {xf}")
        bone_xform = xf.as_matrix()

        bone = armdata.edit_bones.new(name)
        h, t, r = transform_to_bone(self.nif.game, bone_xform)

        bone.head = h
        bone.tail = t
        bone.roll = r
        bone['PYN_TRANSFORM'] = bone_xform.to_quaternion()[:] # stash rotation for later

        return bone


    def connect_armature(self):
        """ Connect up the bones in an armature to make a full skeleton.
            Use parent/child relationships in the nif if present, from the skel otherwise.
            Uses flags
                CREATE_BONES - add bones from skeleton as needed
                RENAME_BONES - rename bones to conform with blender conventions
            Returns list of bone nodes with collisions found along the way
            """
        arm_data = self.armature.data
        bones_to_parent = [b.name for b in arm_data.edit_bones]
        collisions = set()

        i = 0
        while i < len(bones_to_parent): # list will grow while iterating
            bonename = bones_to_parent[i]
            arma_bone = arm_data.edit_bones[bonename]

            if arma_bone.parent is None:
                parentname = None
                parentnifname = None
                skelbone = None
                
                # look for a parent in the nif
                nifname = self.nif.nif_name(bonename)
                if nifname in self.nif.nodes:
                    thisnode = self.nif.nodes[nifname]
                    if thisnode.collision_object:
                        collisions.add(thisnode)

                    niparent = thisnode.parent
                    if niparent and niparent._handle != self.nif.root:
                        try:
                            parentnifname = niparent.nif_name
                        except:
                            parentnifname = niparent.name
                        if self.flags & ImportFlags.RENAME_BONES:
                            parentname = niparent.blender_name
                        else:
                            parentname = parentnifname

                if parentname is None and (self.flags & ImportFlags.CREATE_BONES):
                    # No parent in the nif. If it's a known bone, get parent from skeleton
                    if self.flags & ImportFlags.RENAME_BONES:
                        if arma_bone.name in self.nif.dict.byBlender:
                            p = self.nif.dict.byBlender[bonename].parent
                            if p:
                                parentname = p.blender
                                parentnifname = p.nif
                    else:
                        if arma_bone.name in self.nif.dict.byNif:
                            p = self.nif.dict.byNif[bonename].parent
                            if p:
                                parentname = p.nif
                                parentnifname = p.nif
            
                # if we got a parent from somewhere, hook it up
                if parentname:
                    if parentname not in arm_data.edit_bones:
                        # Add parent bones and put on our list so we can get its parent
                        new_parent = self.add_bone_to_arma(parentname, parentnifname)
                        bones_to_parent.append(parentname)  
                        arma_bone.parent = new_parent
                    else:
                        arma_bone.parent = arm_data.edit_bones[parentname]
            i += 1

        return collisions
        

    def make_armature(self,
                      the_coll: bpy_types.Collection, 
                      bone_names: set):
        """ Make a Blender armature from the given info. If the current active object is an
                armature, bones will be added to it instead of creating a new one.
            Inputs:
                the_coll = Collection to put the armature in. 
                bone_names = bones to include in the armature. Additional bones will be added from
                    the reference skeleton as needed to connect every bone to the skeleton root.
                self.armature = existing armature to add the new bones to. May be None.
            Returns: 
                self.armature = new armature, set as active object
            """
        if self.armature is None:
            log.debug(f"..Creating new armature for the import")
            arm_data = bpy.data.armatures.new(self.nif.rootName)
            self.armature = bpy.data.objects.new(self.nif.rootName, arm_data)
            the_coll.objects.link(self.armature)
        else:
            self.armature = self.armature

        bpy.ops.object.select_all(action='DESELECT')
        self.armature.select_set(True)
        bpy.context.view_layer.objects.active = self.armature
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    
        for bone_game_name in bone_names:
            if self.flags & ImportFlags.RENAME_BONES:
                name = self.nif.blender_name(bone_game_name)
            else:
                name = bone_game_name

            xf = self.nif.get_node_xform_to_global("NPC Spine1")
            log.debug(f"make_armature ({name}): Spine1 translation is {xf.translation[:]}")

            self.add_bone_to_arma(name, bone_game_name)
        
        # Hook the armature bones up to a skeleton
        collisions = self.connect_armature()

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        for bonenode in collisions:
            self.import_collision_obj(bonenode.collision_object, self.armature, bonenode)


    def import_bhkConvexTransformShape(self, cs:CollisionShape, cb:bpy_types.Object):
        bpy.ops.object.add(radius=1.0, type='EMPTY')
        cshape = bpy.context.object
        cshape['bhkMaterial'] = SkyrimHavokMaterial(cs.properties.bhkMaterial).name
        cshape['bhkRadius'] = cs.properties.bhkRadius
        xf = Matrix(cs.transform)
        xf.translation = xf.translation * HAVOC_SCALE_FACTOR
        cshape.matrix_local = xf

        self.import_collision_shape(cs.child, cshape)

        return cshape


    def import_bhkListShape(self, cs:CollisionShape, cb:bpy_types.Object):
        """ Import collision list. cs=collision node in nif. cb=collision body in Blender """
        bpy.ops.object.add(radius=1.0, type='EMPTY')
        cshape = bpy.context.object
        cshape.show_name = True
        cshape['bhkMaterial'] = SkyrimHavokMaterial(cs.properties.bhkMaterial).name

        for child in cs.children:
            self.import_collision_shape(child, cshape)

        return cshape

    def import_bhkBoxShape(self, cs:CollisionShape, cb:bpy_types.Object):
        m = bpy.data.meshes.new(cs.blockname)
        prop = cs.properties
        dx = prop.bhkDimensions[0] * HAVOC_SCALE_FACTOR
        dy = prop.bhkDimensions[1] * HAVOC_SCALE_FACTOR
        dz = prop.bhkDimensions[2] * HAVOC_SCALE_FACTOR
        v = [ [-dx, dy, dz],    
              [-dx, -dy, dz],   
              [-dx, -dy, -dz],  
              [-dx, dy, -dz],
              [dx, dy, dz],
              [dx, -dy, dz],
              [dx, -dy, -dz],
              [dx, dy, -dz] ]
        #log.debug(f"Creating shape with vertices: {v}")
        m.from_pydata(v, [], 
                      [ (0, 1, 2, 3), 
                        (4, 5, 6, 7),
                        (0, 1, 5, 4),
                        (2, 3, 7, 6),
                        (0, 4, 7, 3), 
                        (5, 1, 2, 6)])
        obj = bpy.data.objects.new(cs.blockname, m)
        obj.matrix_world = cb.matrix_world
        bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
        # bpy.context.scene.collection.objects.link(obj)
        obj['bhkMaterial'] = SkyrimHavokMaterial(prop.bhkMaterial).name
        obj['bhkRadius'] = prop.bhkRadius
        # self.objects_created.append(obj)
        return obj
        
    def import_bhkCapsuleShape(self, cs:CollisionShape, cb:bpy_types.Object):
        prop = cs.properties
        p1 = Vector(prop.point1)
        p2 = Vector(prop.point2)
        vaxis = p2 - p1
        log.debug(f"Creating capsule shape between {p1} and {p2}")
        shapelen = vaxis.length * HAVOC_SCALE_FACTOR
        shaperad = prop.radius1 * HAVOC_SCALE_FACTOR

        bpy.ops.mesh.primitive_cylinder_add(radius=shaperad, depth=shapelen)
        obj = bpy.context.object

        q = Quaternion((1,0,0), -pi/2)
        objtrans, objrot, objscale = obj.matrix_world.decompose()
        objrot.rotate(q)
        objtrans = Vector(( (((p2.x - p1.x)/2) + p1.x) * HAVOC_SCALE_FACTOR,
                            (((p2.y - p1.y)/2) + p1.y) * HAVOC_SCALE_FACTOR,
                            (((p2.z - p1.z)/2) + p1.z) * HAVOC_SCALE_FACTOR,
                            ))
        
        obj.matrix_world = MatrixLocRotScale(objtrans, objrot, objscale)

        for p in obj.data.polygons:
            p.use_smooth = True
        obj.data.update()
        
        # bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
        obj['bhkMaterial'] = SkyrimHavokMaterial(prop.bhkMaterial).name
        obj['bhkRadius'] = prop.bhkRadius
        return obj
        

    def show_collision_normals(self, cs:CollisionShape, cso):
        #norms = [Vector(n)*HAVOC_SCALE_FACTOR for n in cs.normals]
        bpy.ops.object.select_all(action='DESELECT')
        for n in cs.normals:
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            obj = bpy.context.object
            obj.empty_display_type = 'SINGLE_ARROW'
            obj.empty_display_size = n[3] * -HAVOC_SCALE_FACTOR
            v = Vector(n)
            v.normalize()
            q = Vector((0,0,1)).rotation_difference(v)
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = q
            obj.parent = cso
            #bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
            

    def import_bhkConvexVerticesShape(self, 
                                      collisionnode:CollisionShape,
                                      collisionbody:bpy_types.Object):
        """ Import a bhkConvexVerticesShape object.
            collisionnode = the bhkConvexVerticesShape node in the nif
            collisionbody = parent collision body object in Blender """
        prop = collisionnode.properties
        #transl = Vector((0,0,0))
        #if collisionbody['Collision_Block_Name'] != "bhkRigidBodyT":
        #    transl = collisionbody.location * -1

        sourceverts = [Vector(v[0:3])*HAVOC_SCALE_FACTOR for v in collisionnode.vertices]

        m = bpy.data.meshes.new(collisionnode.blockname)
        bm = bmesh.new()
        m.from_pydata(sourceverts, [], [])
        bm.from_mesh(m)

        bmesh.ops.convex_hull(bm, input=bm.verts)
        bm.to_mesh(m)

        obj = bpy.data.objects.new(collisionnode.blockname, m)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
        
        obj['bhkMaterial'] = SkyrimHavokMaterial(prop.bhkMaterial).name
        obj['bhkRadius'] = prop.bhkRadius
        # self.objects_created.append(obj)

        log.info(f"1. Imported bhkConvexVerticesShape {obj.name} matrix: \n{obj.matrix_world}")
        if log.getEffectiveLevel() == logging.DEBUG:
            self.show_collision_normals(collisionnode, obj)
        obj.rotation_mode = "QUATERNION"
        q = collisionbody.rotation_quaternion.copy()
        q.invert()
        obj.rotation_quaternion = q
        log.info(f"2. Imported bhkConvexVerticesShape {obj.name} matrix: \n{obj.matrix_world}")
        return obj


    def import_collision_shape(self, cs:CollisionShape, cb:bpy_types.Object):
        sh = None
        log.debug(f"Found collision shape {cs.blockname}")
        if cs.blockname == "bhkBoxShape":
            sh = self.import_bhkBoxShape(cs, cb)
        elif cs.blockname == "bhkConvexVerticesShape":
            sh = self.import_bhkConvexVerticesShape(cs, cb)
        elif cs.blockname == "bhkListShape":
            sh = self.import_bhkListShape(cs, cb)
        elif cs.blockname == "bhkConvexTransformShape":
            sh = self.import_bhkConvexTransformShape(cs, cb)
        elif cs.blockname == "bhkCapsuleShape":
            sh = self.import_bhkCapsuleShape(cs, cb)
        else:
            log.warning(f"Found unimplemented collision shape: {cs.blockname}")
            self.warnings.add('WARNING')
        
        if sh:
            sh.name = cs.blockname
            sh.parent = cb
            sh.color = COLLISION_COLOR


    collision_body_ignore = ['rotation', 'translation', 'guard', 'unusedByte1', 
                             'unusedInts1_0', 'unusedInts1_1', 'unusedInts1_2',
                             'unusedBytes2_0', 'unusedBytes2_1', 'unusedBytes2_2']

    def import_collision_body(self, cb:CollisionBody, c:bpy_types.Object):
        bpy.ops.object.add(radius=1.0, type='EMPTY')
        cbody = bpy.context.object
        cbody.parent = c
        cbody.name = cb.blockname
        cbody.show_name = True
        self.incr_loc

        p = cb.properties
        p.extract(cbody, ignore=self.collision_body_ignore)

        # The rotation in the nif is a quaternion with the angle in the 4th position, in radians
        log.debug(f"Found collision body with properties:\n{p}")
        if cb.blockname == "bhkRigidBodyT":
            cbody.rotation_mode = 'QUATERNION'
            log.debug(f"Rotating collision body around quaternion {(p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2])}")
            cbody.rotation_quaternion = (p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2], )
            cbody.location = Vector(p.translation[0:3]) * HAVOC_SCALE_FACTOR

        cs = cb.shape
        if cs:
            self.import_collision_shape(cs, cbody)

        #log.debug(f"Loaded collision body {cbody.name} with properties {list(cbody.keys())}")


    def import_collision_obj(self, c:CollisionObject, parentObj=None, bone=None):
        """ Import collision object. Parent is target of collision. 
            If target is a bone, parent is armature and "bone" is bone name.
            """
        bpy.ops.object.mode_set(mode='OBJECT', toggle=True)
        if c.blockname == "bhkCollisionObject":
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            col = bpy.context.object
            col.name = c.blockname
            col.show_name = True
            col['pynCollisionFlags'] = bhkCOFlags(c.flags).fullname

            if parentObj:
                col.parent = parentObj
                if parentObj.type == "ARMATURE":
                    col.matrix_world = get_node_transform(bone)
                    col['pynCollisionTarget'] = bone.name

            cb = c.body
            if cb:
                self.import_collision_body(cb, col)

    def import_collisions(self):
        """ Import top-level collision, if any """
        r = self.nif.rootNode
        if r.collision_object:
            self.import_collision_obj(r.collision_object, None)

    def execute(self):
        """Perform the import operation as previously defined"""
        NifFile.clear_log()

        new_collection = bpy.data.collections.new(os.path.basename(self.filename))
        bpy.context.scene.collection.children.link(new_collection)
        bpy.context.view_layer.active_layer_collection \
             = bpy.context.view_layer.layer_collection.children[new_collection.name]
    
        log.info(f"Importing {self.nif.game} file {self.nif.filepath}")
        if bpy.context.object and bpy.context.object.type == "ARMATURE":
            self.armature = bpy.context.object
            log.info(f"..Current object is an armature, parenting shapes to {self.armature.name}")

        # Import shapes
        for s in self.nif.shapes:
            for n in s.bone_names: 
                #log.debug(f"....adding bone {n} for {s.name}")
                self.bones.add(n) 
            if self.nif.game == 'FO4' and fo4FaceDict.matches(self.bones) > 10:
                self.nif.dict = fo4FaceDict

            self.import_shape(s)

        log.debug(f"Objects created on this import: {self.objects_created}")
        for obj in self.objects_created.values():
            if not obj.name in new_collection.objects and obj.type == 'MESH':
                log.debug(f"...Adding object {obj.name} to collection {new_collection.name}")
                new_collection.objects.link(obj)

        # Import armature
        if len(self.bones) > 0 or len(self.nif.shapes) == 0:
            if len(self.nif.shapes) == 0:
                log.debug(f"....No shapes in nif, importing bones as skeleton")
                self.bones = set(self.nif.nodes.keys())
            else:
                log.debug(f"....Found self.bones, creating armature")
            self.make_armature(new_collection, self.bones)
        
            if len(self.objects_created) > 0:
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.view_layer.objects.active = self.armature
                for o in self.objects_created.values(): 
                    if o.type == 'MESH': 
                        o.select_set(True)
                bpy.ops.object.parent_set(type='ARMATURE_NAME', xmirror=False, keep_transform=False)
            else:
                self.armature.select_set(True)
    
        # Import nif-level extra data
        objs = self.import_extra(self.nif)
        
        # Import top-level collisions
        self.import_collisions()

        active_set = False
        for o in self.objects_created.values(): 
            if not active_set:
                bpy.context.view_layer.objects.active = o
                active_set = True
            o.select_set(True)


    @classmethod
    def do_import(cls, 
                  filename: str, 
                  flags: ImportFlags = ImportFlags.CREATE_BONES | ImportFlags.RENAME_BONES):
        imp = NifImporter(filename, flags)
        imp.execute()
        return imp


class ImportNIF(bpy.types.Operator, ImportHelper):
    """Load a NIF File"""
    bl_idname = "import_scene.nifly"
    bl_label = "Import NIF (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".nif"
    filter_glob: StringProperty(
        default="*.nif",
        options={'HIDDEN'},
    )

    create_bones: bpy.props.BoolProperty(
        name="Create Bones",
        description="Create vanilla bones as needed to make skeleton complete.",
        default=True)

    rename_bones: bpy.props.BoolProperty(
        name="Rename Bones",
        description="Rename bones to conform to Blender's left/right conventions.",
        default=True)


    def execute(self, context):
        log.info("\n\n====================================\nNIFLY IMPORT V%d.%d.%d" % bl_info['version'])
        status = {'FINISHED'}

        flags = ImportFlags(0)
        if self.create_bones:
            flags |= ImportFlags.CREATE_BONES
        if self.rename_bones:
            flags |= ImportFlags.RENAME_BONES
        #if self.rotate_model:
        #    flags |= ImportFlags.ROTATE_MODEL

        try:
            NifFile.Load(nifly_path)

            bpy.ops.object.select_all(action='DESELECT')

            NifImporter.do_import(self.filepath, flags)
        
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

def create_shape_keys(obj, tri: TriFile):
    """Adds the shape keys in tri to obj 
        """
    mesh = obj.data
    if mesh.shape_keys is None:
        log.debug(f"Adding first shape key to {obj.name}")
        newsk = obj.shape_key_add()
        mesh.shape_keys.use_relative=True
        newsk.name = "Basis"
        mesh.update()

    base_verts = tri.vertices

    dict = None
    if obj.parent and obj.parent.type == 'ARMATURE':
        g = best_game_fit(obj.parent.data.bones)
        if g != "":
            dict = gameSkeletons[g]

    for game_morph_name, morph_verts in sorted(tri.morphs.items()):
        if dict and game_morph_name in dict.morph_dic_blender:
            morph_name = dict.morph_dic_blender[game_morph_name]
        else:
            morph_name = game_morph_name
        if morph_name not in mesh.shape_keys.key_blocks:
            newsk = obj.shape_key_add()
            newsk.name = morph_name

            obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
            #This is a pointer, not a copy
            mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
            # We may be applying the morphs to a different shape than the one stored in 
            # the tri file. But the morphs in the tri file are absolute locations, as are 
            # shape key locations. So we need to calculate the offset in the tri and apply that 
            # to our shape keys.
            for key_vert, morph_vert, base_vert in zip(mesh_key_verts, morph_verts, base_verts):
                key_vert.co[0] += morph_vert[0] - base_vert[0]
                key_vert.co[1] += morph_vert[1] - base_vert[1]
                key_vert.co[2] += morph_vert[2] - base_vert[2]
        
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
                log.warning(f"BS Tri file shape does not match any selected object: {shapename}")
                result.add('WARNING')
            else:
                create_trip_shape_keys(matchlist[0], trip)
    else:
        result.add('WRONGTYPE')

    return result


def import_tri(filepath, cobj):
    """ Import the tris from filepath into cobj
        If cobj is None, create a new object
        """
    tri = TriFile.from_file(filepath)
    if not type(tri) == TriFile:
        log.error(f"Error reading tri file")
        return None

    new_object = None

    if cobj:
        log.debug(f"Importing with selected object {cobj.name}, type {cobj.type}")
        if cobj.type == "MESH":
            log.debug(f"Selected mesh vertex match: {cobj.name} {len(cobj.data.vertices)} =? {len(tri.vertices)}")

    # Check whether selected object should receive shape keys
    if cobj and cobj.type == "MESH" and len(cobj.data.vertices) == len(tri.vertices):
        new_object = cobj
        new_mesh = new_object.data
        log.info(f"Verts match, loading tri into existing shape {new_object.name}")

    if new_object is None:
        new_mesh = bpy.data.meshes.new(os.path.basename(filepath))
        new_mesh.from_pydata(tri.vertices, [], tri.faces)
        new_object = bpy.data.objects.new(new_mesh.name, new_mesh)

        for f in new_mesh.polygons:
            f.use_smooth = True

        new_mesh.update(calc_edges=True, calc_edges_loose=True)
        new_mesh.validate(verbose=True)

        if tri.import_uv:
            mesh_create_uv(new_mesh, tri.uv_pos)
   
        new_collection = bpy.data.collections.new(os.path.basename(os.path.basename(filepath) + ".Coll"))
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.objects.link(new_object)
        bpy.context.view_layer.objects.active = new_object
        new_object.select_set(True)

    create_shape_keys(new_object, tri)

    return new_object


class ImportTRI(bpy.types.Operator, ImportHelper):
    """Load a TRI File"""
    bl_idname = "import_scene.niflytri"
    bl_label = "Import TRI (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".tri"
    filter_glob: StringProperty(
        default="*.tri",
        options={'HIDDEN'},
    )

    def execute(self, context):
        log.info("NIFLY IMPORT V%d.%d.%d" % bl_info['version'])
        status = {'FINISHED'}

        try:
            
            v = import_trip(self.filepath, context.selected_objects)
            if 'WRONGTYPE' in v:
                import_tri(self.filepath, bpy.context.object)
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

def select_all_faces(mesh):
    """ Make sure all mesh elements are visible and all faces are selected """
    bpy.ops.object.mode_set(mode = 'OBJECT') # Have to be in object mode

    for v in mesh.vertices:
        v.hide = False
    for e in mesh.edges:
        e.hide = False
    for p in mesh.polygons:
        p.hide = False
        p.select = True


def check_partitions(vi1, vi2, vi3, weights):
    """ Chcek whether the = 3 verts (specified by index) all have the same partitions 
        weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts
       """
    p1 = set([k for k in weights[vi1].keys() if is_partition(k)])
    p2 = set([k for k in weights[vi2].keys() if is_partition(k)])
    p3 = set([k for k in weights[vi3].keys() if is_partition(k)])
    log.debug(f"Checking tri: {p1}, {p2}, {p3}")
    return len(p1.intersection(p2, p3)) > 0


def trim_to_four(weights, arma):
    """ Trim to the 4 heaviest weights in the armature
        weights = [(group_name: weight), ...] """
    if arma:
        #log.debug(f"Trimming to 4 on armature {arma.name}")
        lst = filter(lambda p: p[0] in arma.data.bones, weights)
        #log.debug(f"Arma weights: {lst}")
        notlst = filter(lambda p: p[0] not in arma.data.bones, weights)
        sd = sorted(lst, reverse=True, key=lambda item: item[1])[0:4]
        #log.debug(f"Arma weights sorted: {sd}")
        sd.extend(notlst)
        #if len(sd) != len(weights):
        #    log.info(f"Trimmed weights to {sd}")
        return dict(sd)
    else:
        return dict(weights)


def has_uniform_scale(obj):
    """ Determine whether an object has uniform scale """
    return NearEqual(obj.scale[0], obj.scale[1]) and NearEqual(obj.scale[1], obj.scale[2])

def extract_vert_info(obj, mesh, arma, target_key=''):
    """Returns 3 lists of equal length with one entry each for each vertex
        verts = [(x, y, z)... ] - base or as modified by target-key if provided
        weights = [{group-name: weight}... ] - 1:1 with verts list
        dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
            if "target_key" is specified this will be empty
            shape key is the blender name
        """
    weights = []
    morphdict = {}
    msk = mesh.shape_keys

    sf = Vector((1,1,1))
    if not has_uniform_scale(obj):
        # Apply non-uniform scale to verts directly
        sf = obj.scale

    if target_key != '' and msk and target_key in msk.key_blocks.keys():
        log.debug(f"....exporting shape {target_key} only")
        verts = [(v.co * sf)[:] for v in msk.key_blocks[target_key].data]
    else:
        verts = [(v.co * sf)[:] for v in mesh.vertices]

    for i, v in enumerate(mesh.vertices):
        vert_weights = []
        for vg in v.groups:
            try:
                vert_weights.append([obj.vertex_groups[vg.group].name, vg.weight])
            except:
                log.error(f"ERROR: Vertex #{v.index} references invalid group #{vg.group}")
        
        weights.append(trim_to_four(vert_weights, arma))
    
    if target_key == '' and msk:
        for sk in msk.key_blocks:
            morphdict[sk.name] = [(v.co * sf)[:] for v in sk.data]

    #log.debug(f"....Vertex 18 at {[round(v,2) for v in verts[18]]}")
    return verts, weights, morphdict


def tag_unweighted(obj, bones):
    """ Find and return verts that are not weighted to any of the given bones 
        result = (v_index, ...) list of indices into the vertex list
    """
    log.debug(f"..Checking for unweighted verts on {obj.name}")
    unweighted_verts = []
    for v in obj.data.vertices:
        maxweight = 0.0
        if len(v.groups) > 0:
            maxweight = max([g.weight for g in v.groups])
        if maxweight < 0.0001:
            unweighted_verts.append(v.index)
    log.debug(f"..Unweighted vert count: {len(unweighted_verts)}")
    return unweighted_verts


def create_group_from_verts(obj, name, verts):
    """ Create a vertex group from the list of vertex indices.
    Use the existing group if any """
    if name in obj.vertex_groups.keys():
        g = obj.vertex_groups[name]
    else:
        g = obj.vertex_groups.new(name=name)
    g.add(verts, 1.0, 'ADD')


def is_facebones(arma):
    #return (fo4FaceDict.matches(set(list(arma.data.bones.keys()))) > 20)
    return  len([x for x in arma.data.bones.keys() if x.startswith('skin_bone_')]) > 5


def best_game_fit(bonelist):
    """ Find the game that best matches the skeleton """
    boneset = set([b.name for b in bonelist])
    maxmatch = 0
    matchgame = ""
    #print(f"Checking bonelist {[b.name for b in bonelist]}")
    for g, s in gameSkeletons.items():
        n = s.matches(boneset)
        if n > maxmatch:
            maxmatch = n
            matchgame = g
    n = fo4FaceDict.matches(boneset)
    if n > maxmatch:
        matchgame = "FO4"
    return matchgame


def expected_game(nif, bonelist):
    """ Check whether the nif's game is the best match for the given bonelist """
    matchgame = best_game_fit(bonelist)
    return matchgame == "" or matchgame == nif.game or \
        (matchgame in ['SKYRIM', 'SKYRIMSE'] and nif.game in ['SKYRIM', 'SKYRIMSE'])


def is_partition(name):
    """ Check whether <name> is a valid partition or segment name """
    if SkyPartition.name_match(name) >= 0:
        return True

    if FO4Segment.name_match(name) >= 0:
        return True

    parent_name, subseg_id, material = FO4Subsegment.name_match(name)
    if parent_name:
        return True

    return False


def partitions_from_vert_groups(obj):
    """ Return dictionary of Partition objects for all vertex groups that match the partition 
        name pattern. These are all partition objects including subsegments.
    """
    val = {}
    if obj.vertex_groups:
        vg_sorted = sorted([g.name for g in obj.vertex_groups])
        for nm in vg_sorted:
            vg = obj.vertex_groups[nm]
            skyid = SkyPartition.name_match(vg.name)
            if skyid >= 0:
                val[vg.name] = SkyPartition(part_id=skyid, flags=0, name=vg.name)
            else:
                segid = FO4Segment.name_match(vg.name)
                if segid >= 0:
                    #log.debug(f"Found FO4Segment '{vg.name}'")
                    val[vg.name] = FO4Segment(part_id=len(val), index=segid, name=vg.name)
                else:
                    # Check if this is a subsegment. All segs sort before their subsegs, 
                    # so it will already have been created if it exists separately
                    parent_name, subseg_id, material = FO4Subsegment.name_match(vg.name)
                    if parent_name:
                        if not parent_name in val:
                            # Create parent segments if not there
                            log.debug(f"Subseg {vg.name} needs parent {parent_name}; existing parents are {val.keys()}")
                            val[parent_name] = FO4Segment(len(val), 0, parent_name)
                        p = val[parent_name]
                        #log.debug(f"Found FO4Subsegment '{vg.name}' child of '{parent_name}'")
                        val[vg.name] = FO4Subsegment(len(val), subseg_id, material, p, name=vg.name)
    
    return val


def all_vertex_groups(weightdict):
    """ Return the set of group names that have non-zero weights """
    val = set()
    for g, w in weightdict.items():
        if w > 0.0001:
            val.add(g)
    return val


def get_effective_colormaps(mesh):
    """ Return the colormaps we want to use
        Returns colormap, alphamap
        Either may be null
        """
    if not mesh.vertex_colors:
        return None, None

    vc = mesh.vertex_colors
    am = None
    cm = vc.active.data

    if vc.active.name == ALPHA_MAP_NAME:
        cm = None
        if vc.items()[0][0] == ALPHA_MAP_NAME and len(vc) > 1:
            cm = vc.items()[1][1]
        else:
            cm = vc.items()[0][1]

    if ALPHA_MAP_NAME in vc.keys():
        am = vc[ALPHA_MAP_NAME].data

    return cm, am

def get_loop_color(mesh, loopindex, cm, am):
    """ Return the color of the vertex-in-loop at given loop index using
        cm = color map to use
        am = alpha map to use """
    ### This routine crashes on the TEST_COLLISION_MULTI test. One of the leeks
    ### causes a crash on the color table. 
    log.debug(f"Calling get_loop_color with {mesh}, {loopindex}, {cm}:{len(cm)}, {am}:{len(am)}")
    log.debug(f"Test color: {cm[5].color[:]}")
    vc = mesh.vertex_colors
    alpha = 1.0
    color = (1.0, 1.0, 1.0)
    if cm:
        log.debug( f"Loop index less than color length {loopindex} < {len(cm)}")
        color = cm[loopindex].color
    if am:
        log.debug(f"Loop index less than alpha length {loopindex} < {len(am)}")
        acolor = am[loopindex].color
        alpha = (acolor[0] + acolor[1] + acolor[2])/3

    return (color[0], color[1], color[2], alpha)
    

def mesh_from_key(editmesh, verts, target_key):
    faces = []
    for p in editmesh.polygons:
        faces.append([editmesh.loops[lpi].vertex_index for lpi in p.loop_indices])
    log.debug(f"....Remaking mesh with shape {target_key}: {len(verts)} verts, {len(faces)} faces")
    newverts = [v.co[:] for v in editmesh.shape_keys.key_blocks[target_key].data]
    newmesh = bpy.data.meshes.new(editmesh.name)
    newmesh.from_pydata(newverts, [], faces)
    return newmesh


def get_common_shapes(obj_list):
    """ Return the shape keys found in any of the given objects """
    res = None
    log.debug(f"Checking shape keys on {obj_list}")
    for obj in obj_list:
        o_shapes = set()
        if obj.data.shape_keys:
            o_shapes = set(obj.data.shape_keys.key_blocks.keys())
        if res:
            res = res.union(o_shapes)
        else:
            res = o_shapes
    if res:
        res = list(res)
    return res


def get_with_uscore(str_list):
    return list(filter((lambda x: x[0] == '_'), str_list))


class NifExporter:
    """ Object that handles the export process 
    """
    def __init__(self, filepath, game, export_flags=ImportFlags.RENAME_BONES):
        self.filepath = filepath
        self.game = game
        self.nif = None
        self.trip = None
        self.warnings = set()
        self.armature = None
        self.facebones = None
        self.flags = export_flags
        self.active_obj = None

        # Objects that are to be written out
        self.objects = set()
        self.bg_data = set()
        self.str_data = set()
        self.cloth_data = set()
        self.grouping_nodes = set()
        self.bsx_flag = None
        self.inv_marker = None
        self.furniture_markers = set()
        self.collisions = set()
        
        # Shape keys that start with underscore trigger a separate file export
        # for each shape key
        self.file_keys = []  
        self.objs_unweighted = set()
        self.objs_scale = set()
        self.objs_mult_part = set()
        self.objs_no_part = set()
        self.arma_game = []
        self.bodytri_written = False

        # Dictionary of objects written to nif. {Blender object name: NiNode}
        self.objs_written = {}

        self.message_log = []
        #self.rotate_model = rotate


    def export_shape_data(self, obj, shape):
        """ Export a shape's extra data """
        edlist = []
        strlist = []
        for ch in obj.children:
             if 'NiStringExtraData_Name' in ch:
                strlist.append( (ch['NiStringExtraData_Name'], ch['NiStringExtraData_Value']) )
                self.objs_written[ch.name] = shape
             if 'BSBehaviorGraphExtraData_Name' in ch:
                edlist.append( (ch['BSBehaviorGraphExtraData_Name'], 
                               ch['BSBehaviorGraphExtraData_Value']) )
                self.objs_written[ch.name] = shape
        #ed = [ (x['NiStringExtraData_Name'], x['NiStringExtraData_Value']) for x in \
        #        obj.children if 'NiStringExtraData_Name' in x.keys()]
        if len(strlist) > 0:
            shape.string_data = strlist
    
        #ed = [ (x['BSBehaviorGraphExtraData_Name'], x['BSBehaviorGraphExtraData_Value']) \
        #        for x in obj.children if 'BSBehaviorGraphExtraData_Name' in x.keys()]
        if len(edlist) > 0:
            shape.behavior_graph_data = edlist


    def add_object(self, obj):
        """ Adds the given object to the objects to export """
        if obj.type == 'ARMATURE':
            facebones_obj = (self.game == 'FO4') and (is_facebones(obj))
            if facebones_obj and self.facebones is None:
                self.facebones = obj
            if (not facebones_obj) and (self.armature is None):
                self.armature = obj 

        elif obj.type == 'MESH':
            par = obj.parent
            par2 = None
            if par:
                par2 = par.parent
            if not ( obj.name.startswith('bhk') and par and par.name.startswith('bhk') and par2 and par2.name.startswith('bhkCollisionObject') ):
                self.objects.add(obj)
                if obj.parent and obj.parent.type == 'ARMATURE':
                    self.add_object(obj.parent)
                self.file_keys = get_with_uscore(get_common_shapes(self.objects))

        elif obj.type == 'EMPTY':
            if 'BSBehaviorGraphExtraData_Name' in obj.keys():
                self.bg_data.add(obj)

            elif 'NiStringExtraData_Name' in obj.keys():
                self.str_data.add(obj)

            elif 'BSClothExtraData_Name' in obj.keys():
                self.cloth_data.add(obj)

            elif 'BSXFlags_Name' in obj.keys():
                self.bsx_flag = obj

            elif 'BSInvMarker_Name' in obj.keys():
                self.inv_marker = obj

            elif obj.name.startswith("BSFurnitureMarkerNode"):
                self.furniture_markers.add(obj)

            elif obj.name.startswith("bhkCollisionObject"):
                self.collisions.add(obj)

            else:
                self.grouping_nodes.add(obj)
                for c in obj.children:
                    self.add_object(c)


    def set_objects(self, objects):
        """ Set the objects to export from the given list of objects 
        """
        for x in objects:
            self.add_object(x)


    def from_context(self, context):
        """ Set the objects to export from the given context 
        """
        self.set_objects(context.selected_objects)


    # --------- DO THE EXPORT ---------

    def export_tris(self, obj, verts, tris, uvs, morphdict):
        """ Export a tri file to go along with the given nif file, if there are shape keys 
            and it's not a faceBones nif.
            dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
        """
        result = {'FINISHED'}

        if obj.data.shape_keys is None:
            return result

        fpath = os.path.split(self.nif.filepath)
        fname = os.path.splitext(fpath[1])

        if fname[0].endswith('_faceBones'):
            return result

        fname_tri = os.path.join(fpath[0], fname[0] + ".tri")
        fname_chargen = os.path.join(fpath[0], fname[0] + "_chargen.tri")

        # Don't export anything that starts with an underscore or asterisk
        objkeys = obj.data.shape_keys.key_blocks.keys()
        export_keys = set(filter((lambda n: n[0] not in ('_', '*') and n != 'Basis'), objkeys))
        expression_morphs = self.nif.dict.expression_filter(export_keys)
        trip_morphs = set(filter((lambda n: n[0] == '>'), objkeys))
        # Leftovers are chargen candidates
        leftover_morphs = export_keys.difference(expression_morphs).difference(trip_morphs)
        chargen_morphs = self.nif.dict.chargen_filter(leftover_morphs)

        if len(expression_morphs) > 0 and len(trip_morphs) > 0:
            log.warning(f"Found both expression morphs and BS tri morphs in shape {obj.name}. May be an error.")
            result = {'WARNING'}

        if len(expression_morphs) > 0:
            log.debug(f"....Exporting expressions {expression_morphs}")
            tri = TriFile()
            tri.vertices = verts
            tri.faces = tris
            tri.uv_pos = uvs
            tri.face_uvs = tris # (because 1:1 with verts)
            for m in expression_morphs:
                if m in self.nif.dict.morph_dic_game:
                    triname = self.nif.dict.morph_dic_game[m]
                else:
                    triname = m
                if m in morphdict:
                    tri.morphs[triname] = morphdict[m]
    
            log.info(f"Generating tri file '{fname_tri}'")
            tri.write(fname_tri) # Only expression morphs to write at this point

        if len(chargen_morphs) > 0:
            log.debug(f"....Exporting chargen morphs {chargen_morphs}")
            tri = TriFile()
            tri.vertices = verts
            tri.faces = tris
            tri.uv_pos = uvs
            tri.face_uvs = tris # (because 1:1 with verts)
            for m in chargen_morphs:
                if m in morphdict:
                    tri.morphs[m] = morphdict[m]
    
            log.info(f"Generating tri file '{fname_chargen}'")
            tri.write(fname_chargen, chargen_morphs)

        if len(trip_morphs) > 0:
            log.info(f"Generating BS tri shapes for '{obj.name}'")
            self.trip.set_morphs(obj.name, morphdict, verts)

        return result


    def export_extra_data(self):
        """ Export any top-level extra data represented as Blender objects. 
            Sets self.bodytri_done if one of the extra data nodes represents a bodytri
        """
        sdlist = []
        for st in self.str_data:
            sdlist.append( (st['NiStringExtraData_Name'], st['NiStringExtraData_Value']) )
            self.objs_written[st.name] = self.nif
            self.bodytri_written |= (st['NiStringExtraData_Name'] == 'BODYTRI')

        if len(sdlist) > 0:
            self.nif.string_data = sdlist
        
        bglist = []
        for bg in self.bg_data: 
            bglist.append( (bg['BSBehaviorGraphExtraData_Name'], 
                            bg['BSBehaviorGraphExtraData_Value'], 
                            bg['BSBehaviorGraphExtraData_CBS']) )
            self.objs_written[bg.name] = self.nif

        if len(bglist) > 0:
            self.nif.behavior_graph_data = bglist 

        cdlist = []
        for cd in self.cloth_data:
            cdlist.append( (cd['BSClothExtraData_Name'], 
                            codecs.decode(cd['BSClothExtraData_Value'], "base64")) )
            self.objs_written[cd.name] = self.nif

        if len(cdlist) > 0:
            self.nif.cloth_data = cdlist 

        if self.bsx_flag:
            log.debug(f"Exporting BSXFlags node")
            self.nif.bsx_flags = [self.bsx_flag['BSXFlags_Name'],
                                  BSXFlags.parse(self.bsx_flag['BSXFlags_Value'])]
            self.objs_written[self.bsx_flag.name] = self.nif

        if self.inv_marker:
            log.debug(f"Exporting BSInvMarker node")
            self.nif.inventory_marker = [self.inv_marker['BSInvMarker_Name'], 
                                         self.inv_marker['BSInvMarker_RotX'], 
                                         self.inv_marker['BSInvMarker_RotY'], 
                                         self.inv_marker['BSInvMarker_RotZ'], 
                                         self.inv_marker['BSInvMarker_Zoom']]
            self.objs_written[self.inv_marker.name] = self.nif

        fmklist = []
        for fm in self.furniture_markers:
            buf = FurnitureMarkerBuf()
            buf.offset = fm.location[:]
            buf.heading = fm.rotation_euler.z
            buf.animation_type = FurnAnimationType.GetValue(fm['AnimationType'])
            buf.entry_points = FurnEntryPoints.parse(fm['EntryPoints'])
            fmklist.append(buf)
        
        if len(fmklist) > 0:
            self.nif.furniture_markers = fmklist


    def export_bhkCapsuleShape(self, s, xform):
        """ Export capsule shape. 
            Returns (shape, coordinates)
            shape = collision shape in the nif object
            coordinates = center of the shape in Blender world coordinates) """ 
        cshape = None
        center = Vector()

        # Capsule covers the extent of the shape
        props = bhkCapsuleShapeProps(s)
        xf = s.matrix_local
        xfv = [xf @ v.co for v in s.data.vertices]

        maxx = max([v[0] for v in xfv])
        maxy = max([v.y for v in xfv])
        maxz = max([v[2] for v in xfv])
        minx = min([v[0] for v in xfv])
        miny = min([v[1] for v in xfv])
        minz = min([v[2] for v in xfv])
        halfspanx = (maxx - minx)/2
        halfspany = (maxy - miny)/2
        halfspanz = (maxz - minz)/2
        center = s.matrix_world @ Vector([minx + halfspanx, miny + halfspany, minz + halfspanz])
                
        props.bhkRadius = halfspanx / HAVOC_SCALE_FACTOR
        props.radius1 = halfspanx / HAVOC_SCALE_FACTOR
        props.radius2 = halfspanx / HAVOC_SCALE_FACTOR

        props.point1[0] = (minx+halfspanx) / HAVOC_SCALE_FACTOR
        props.point1[1] = maxy / HAVOC_SCALE_FACTOR
        props.point1[2] = (minz+halfspanz) / HAVOC_SCALE_FACTOR
        props.point2[0] = (minx+halfspanx) / HAVOC_SCALE_FACTOR
        props.point2[1] = miny / HAVOC_SCALE_FACTOR
        props.point2[2] = (minz+halfspanz) / HAVOC_SCALE_FACTOR
        cshape = self.nif.add_coll_shape("bhkCapsuleShape", props)
        log.debug(f"Created capsule collision shape at {props.point1[:]}, {props.point2[:]}, radius {props.bhkRadius}")

        return cshape, center


    def export_bhkBoxShape(self, s, xform):
        """ Export box shape. 
            Returns (shape, coordinates)
            shape = collision shape in the nif object
            coordinates = center of the shape in Blender world coordinates) """ 
        cshape = None
        center = Vector()
        try:
            # Box covers the extent of the shape, whatever it is
            p = bhkBoxShapeProps(s)
            # TODO: Take the cruft out when we're sure it's correct
            # xf = xform # s.matrix_world
            # xfv = [xf @ v.co for v in s.data.vertices]
            xfv = [v.co for v in s.data.vertices]
            maxx = max([v[0] for v in xfv])
            maxy = max([v[1] for v in xfv])
            maxz = max([v[2] for v in xfv])
            minx = min([v[0] for v in xfv])
            miny = min([v[1] for v in xfv])
            minz = min([v[2] for v in xfv])
            halfspanx = (maxx - minx)/2
            halfspany = (maxy - miny)/2
            halfspanz = (maxz - minz)/2
            center = s.matrix_world @ Vector([minx + halfspanx, miny + halfspany, minz + halfspanz])
                
            p.bhkDimensions[0] = halfspanx / HAVOC_SCALE_FACTOR
            p.bhkDimensions[1] = halfspany / HAVOC_SCALE_FACTOR
            p.bhkDimensions[2] = halfspanz / HAVOC_SCALE_FACTOR
            if 'radius' not in s.keys():
                p.bhkRadius = max(halfspanx, halfspany, halfspanz) / HAVOC_SCALE_FACTOR
            cshape = self.nif.add_coll_shape("bhkBoxShape", p)
            log.debug(f"Created collision shape with dimensions {p.bhkDimensions[:]}")
        except:
            log.exception(f"Cannot create collision shape from {s.name}")
            self.warnings.add('WARNING')

        return cshape, center
        

    def export_bhkConvexVerticesShape(self, s, xform):
        # Assume the verts are exactly the convex shape
        effectiveXF = xform @ s.matrix_local

        p = bhkConvexVerticesShapeProps(s)
        bm = bmesh.new()
        bm.from_mesh(s.data)
        bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=True)

        verts1 = [effectiveXF @ v.co for v in bm.verts]
        # verts1 = [xform @ v.co for v in s.data.vertices]
        verts = [v / HAVOC_SCALE_FACTOR for v in verts1]

        # Need a normal for each face
        norms = []
        for face in s.data.polygons:
            # Length needs to be distance from origin to face along this normal
            facevert = s.data.vertices[face.vertices[0]].co
            vintersect = geometry.distance_point_to_plane(
                Vector((0,0,0)), facevert, face.normal)
            n = Vector((face.normal[0], face.normal[1], face.normal[2], 
                        vintersect/HAVOC_SCALE_FACTOR))
            log.debug(f"Writing convex normal {n}")
            append_if_new(norms, n, 0.1)
        
            cshape = self.nif.add_coll_shape("bhkConvexVerticesShape", p, verts, norms)

        return cshape, Vector()


    def export_bhkConvexTransformShape(self, s, xform):
        childxf = xform @ s.matrix_local
        childnode, childcenter = self.export_collision_shape(s.children, childxf)

        if not childnode:
            return None, None

        props = bhkConvexTransformShapeProps(s)
        havocxf = s.matrix_world.copy()
        havocxf.translation = havocxf.translation / HAVOC_SCALE_FACTOR
        cshape = self.nif.add_coll_shape("bhkConvexTransformShape", 
                                         props, transform=havocxf)
        cshape.child = childnode
        return cshape, xform.translation


    def export_bhkListShape(self, s, xform):
        props = bhkListShapeProps(s)
        cshape = self.nif.add_coll_shape("bhkListShape", props)

        xf = s.matrix_local @ xform
        for ch in s.children: 
            if ch.name.startswith("bhk"):
                shapenode, nodetransl = self.export_collision_shape([ch], xf)
                if shapenode:
                    cshape.add_child(shapenode)

        return cshape, s.matrix_local.translation


    def export_collision_shape(self, shape_list, xform=Matrix()):
        """ Takes a list of shapes, but only exports the first one """
        for cs in shape_list:
            if cs.name.startswith("bhkBoxShape"):
                return self.export_bhkBoxShape(cs, xform)
            elif cs.name.startswith("bhkConvexVerticesShape"):
                return self.export_bhkConvexVerticesShape(cs, xform)
            elif cs.name.startswith("bhkListShape"):
                return self.export_bhkListShape(cs, xform)
            elif cs.name.startswith("bhkCapsuleShape"):
                return self.export_bhkCapsuleShape(cs, xform)
            elif cs.name.startswith("bhkConvexTransformShape"):
                return self.export_bhkConvexTransformShape(cs, xform)
        return None, None

    def get_collision_target(self, collisionobj) -> Matrix:
        """ Return the world transform matrix for the collision target. If the target
        is the root node return None. """
        mx = None
        targ = collisionobj.parent
        if targ == None:
            mx = collisionobj.matrix_world.copy()
            log.exception(f"No target, using collision object: {collisionobj.name}")
            return mx

        if targ.type == 'ARMATURE':
            targname = collisionobj['pynCollisionTarget']
            log.debug(f"Finding target bone: {targname}")
            targbone = targ.data.bones[targname]
            mx = self.get_bone_xform(targbone)

            log.debug(f"Found collision target bone {targbone} loc {mx.translation}")
            log.debug(f"Found collision target bone {targbone} rot {mx.to_euler()}")

            return mx

        mx = targ.matrix_world.copy()
        log.debug(f"Using parent object: {targ.name}")
        return mx


    def export_collision_body(self, body_list, coll):
        """ Export the collision body elements. coll is the parent collision object """
        body = None
        for b in body_list:
            blockname = 'bhkRigidBody'
            if b.name.startswith('bhkRigidBodyT'):
                blockname = 'bhkRigidBodyT'

            targxf = self.get_collision_target(coll)

            xform = Matrix()
            if blockname == 'bhkRigidBody':
                # Get verts in world coords 
                xform = b.matrix_world.copy()
                # xform.invert()
                # Apply the transform from target
                targxfi = targxf.copy()
                targxfi.invert()
                xform = targxfi @ xform

            cshape, ctr = self.export_collision_shape(b.children, xform)
            log.debug(f"Collision Center: {ctr}")

            if cshape:
                # Coll body can be anywhere. What matters is the location of the collision 
                # shape relative to the collision target--that gets stored on the 
                # collision body
                props = bhkRigidBodyProps(b)
                
                # If there's no target, root is the target. We don't support transforms 
                # on root yet.
                targloc, targq, targscale = targxf.decompose()
            
                targq.invert()
                props.rotation[0] = targq.x
                props.rotation[1] = targq.y
                props.rotation[2] = targq.z
                props.rotation[3] = targq.w
                log.debug(f"Target rotation: {targq.w}, {targq.x}, {targq.y}, {targq.z}")

                rv = ctr - targloc
                log.debug(f"Target to center: {rv}")
                if blockname == 'bhkRigidBodyT':
                    rv.rotate(targq)
                log.debug(f"Target to center rotated: {rv}")
                # rv = bodq.invert().rotate(rv)

                props.translation[0] = (rv.x) / HAVOC_SCALE_FACTOR
                props.translation[1] = (rv.y) / HAVOC_SCALE_FACTOR
                props.translation[2] = (rv.z) / HAVOC_SCALE_FACTOR
                props.translation[3] = 0
                log.debug(f"In havoc units: {rv / HAVOC_SCALE_FACTOR}")

                log.debug(f"Writing collision body with translation: {props.translation[:]} and rotation {props.rotation[:]}")

                body = self.nif.add_rigid_body(blockname, props, cshape)
        return body

    def export_collisions(self, objlist):
        """ Export all the collisions in objlist. (Should be only one.) Apply the skin first so bones are available. """
        log.debug("Writing collisions")
        if self.armature:
            log.debug(". . Applying skin")
            self.nif.apply_skin()

        for coll in objlist:
            body = self.export_collision_body(coll.children, coll)
            if body:
                if coll.name not in self.objs_written:
                    targnode = None
                    p = coll.parent
                    if p == None:
                        targnode = self.nif.rootNode
                    elif p.type == "ARMATURE":
                        targname = coll['pynCollisionTarget']
                        targnode = self.nif.nodes[targname]
                    else:
                        log.debug(f"Exporting collision {coll.name}, exported objects are {self.objs_written.keys()}")
                        if p.name not in self.objs_written:
                            targnode = self.export_shape_parents(coll)
                        else:
                            targnode = self.objs_written[p.name]

                    log.debug(f"Writing collision object {coll.name} under {targnode}")
                    self.nif.add_collision(targnode, targnode, body, 
                            bhkCOFlags.parse(coll['pynCollisionFlags']).value)
                    self.objs_written[coll.name] = targnode


    def get_loop_partitions(self, face, loops, weights):
        vi1 = loops[face.loop_start].vertex_index
        p = set([k for k in weights[vi1].keys() if is_partition(k)])
        for i in range(face.loop_start+1, face.loop_start+face.loop_total):
            vi = loops[i].vertex_index
            p = p.intersection(set([k for k in weights[vi].keys() if is_partition(k)]))
    
        if len(p) != 1:
            face_verts = [lp.vertex_index for lp in loops[face.loop_start:face.loop_start+face.loop_total]]
            if len(p) == 0:
                log.warning(f'Face {face.index} has no partitions')
                self.warnings.add('NO_PARTITION')
                self.objs_no_part.add(self.active_obj)
                create_group_from_verts(self.active_obj, NO_PARTITION_GROUP, face_verts)
                return 0
            elif len(p) > 1:
                log.warning(f'Face {face.index} has too many partitions: {p}')
                self.warnings.add('MANY_PARITITON')
                self.objs_mult_part.add(self.active_obj)
                create_group_from_verts(self.active_obj, MULTIPLE_PARTITION_GROUP, face_verts)

        return p.pop()


    def extract_face_info(self, mesh, uvlayer, loopcolors, weights, obj_partitions, use_loop_normals=False):
        """ Extract triangularized face info from the mesh. 
            Return 
            loops = [vert-index, ...] list of vert indices in loops. Triangularized, 
                so these are to be read in triples.
            uvs = [(u,v), ...] list of uv coordinates 1:1 with loops
            norms = [(x,y,z), ...] list of normal vectors 1:1 with loops
                --Normal vectors come from the loops, because they reflect whether the edges
                are sharp or the object has flat shading
            colors = [(r,g,b,a), ...] 1:1 with loops
            partition_map = [n, ...] list of partition IDs, 1:1 with tris 

        """
        loops = []
        uvs = []
        orig_uvs = []
        norms = []
        colors = []
        partition_map = []

        # Calculating normals messes up the passed-in UV, so get the data out of it first
        for f in mesh.polygons:
            for i in f.loop_indices:
                orig_uvs.append(uvlayer[i].uv[:])
                #log.debug(f"....Adding uv index {uvlayer[i].uv[:]}")

        # CANNOT figure out how to get the loop normals correctly.  They seem to follow the
        # face normals even on smooth shading.  (TEST_NORMAL_SEAM tests for this.) So use the
        # vertex normal except when there are custom split normals.
        bpy.ops.object.mode_set(mode='OBJECT') #required to get accurate normals
        mesh.calc_normals()
        mesh.calc_normals_split()

        def write_loop_vert(loopseg):
            """ Write one vert, given as a MeshLoop 
            """
            loops.append(loopseg.vertex_index)
            uvs.append(orig_uvs[loopseg.index])
            #if colormap or alphamap:
            #    colors.append(get_loop_color(mesh, loopseg.index, colormap, alphamap))
            if loopcolors:
                colors.append(loopcolors[loopseg.index])
            if use_loop_normals:
                norms.append(loopseg.normal[:])
            else:
                norms.append(mesh.vertices[loopseg.vertex_index].normal[:])

        # Write out the loops as triangles, and partitions to match
        for f in mesh.polygons:
            if f.loop_total < 3:
                log.warning(f"Degenerate polygons on {mesh.name}: 0={l0}, 1={l1}")
            else:
                if obj_partitions and len(obj_partitions) > 0:
                    loop_partition = self.get_loop_partitions(f, mesh.loops, weights)
                #log.debug(f"Writing verts for polygon start={f.loop_start}, total={f.loop_total}, partition={loop_partition}")
                l0 = mesh.loops[f.loop_start]
                l1 = mesh.loops[f.loop_start+1]
                for i in range(f.loop_start+2, f.loop_start+f.loop_total):
                    loopseg = mesh.loops[i]

                    #log.debug(f"Writing triangle: [{l0.vertex_index}, {l1.vertex_index}, {loopseg.vertex_index}]")
                    write_loop_vert(l0)
                    write_loop_vert(l1)
                    write_loop_vert(loopseg)
                    if obj_partitions and len(obj_partitions) > 0:
                        if loop_partition:
                            partition_map.append(obj_partitions[loop_partition].id)
                        else:
                            log.warning(f"Writing first partition for face without partitions {obj_partitions}")
                            partition_map.append(next(iter(obj_partitions.values())).id)
                    #log.debug(f"Created tri with partition {loop_partition}")
                    l1 = loopseg

        return loops, uvs, norms, colors, partition_map


    def export_partitions(self, obj, weights_by_vert, tris):
        """ Export partitions described by vertex groups
            weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts. For 
                partitions, can assume the weights are 1.0
            tris = [(v1, v2, v3)...] where v1-3 are indices into the vertex list
            returns (partitions, tri_indices)
                partitions = list of partition objects
                tri_indices = list of paritition indices, 1:1 with the shape's tri list
        """
        log.debug(f"..Exporting partitions")
        partitions = partitions_from_vert_groups(obj)
        #log.debug(f"....Found partitions {list(partitions.keys())}")

        if len(partitions) == 0:
            return [], []

        partition_set = set(list(partitions.keys()))

        tri_indices = [0] * len(tris)

        for i, t in enumerate(tris):
            # All 3 have to be in the same vertex group to count
            vg0 = all_vertex_groups(weights_by_vert[t[0]])
            vg1 = all_vertex_groups(weights_by_vert[t[1]])
            vg2 = all_vertex_groups(weights_by_vert[t[2]])
            tri_partitions = vg0.intersection(vg1).intersection(vg2).intersection(partition_set)
            if len(tri_partitions) > 0:
                if len(tri_partitions) > 1:
                    log.warning(f"Found multiple partitions for tri {t} in object {obj.name}: {tri_partitions}")
                    self.warnings.add('MANY_PARITITON')
                    self.objs_mult_part.add(obj)
                    create_group_from_verts(obj, MULTIPLE_PARTITION_GROUP, t)
                    # log.debug(f"Number of verts in multiple partitions: {len(obj.vertex_groups[MULTIPLE_PARTITION_GROUP])}")

                # Triangulation may put some tris in two partitions. Just choose one--
                # exact division doesn't matter (if it did user should have put in an edge)
                tri_indices[i] = partitions[next(iter(tri_partitions))].id
            else:
                log.warning(f"Tri {t} is not assigned any partition")
                self.warnings.add('NO_PARTITION')
                self.objs_no_part.add(obj)
                create_group_from_verts(obj, NO_PARTITION_GROUP, t)

        #log.debug(f"Partitions for export: {partitions.keys()}, {tri_indices[0:20]}")
        return list(partitions.values()), tri_indices


    def extract_colors(self, mesh):
        """Extract vertex color data from the given mesh. Use the VERTEX_ALPHA color map
            for alpha values if it exists.
            Returns [c.color[:] for c in editmesh.vertex_colors.active.data]
                This is 1:1 with loops
            """
        vc = mesh.vertex_colors
        alphamap = None
        alphamapname = ''
        colormap = None
        colormapname = ''
        colorlen = 0
        if ALPHA_MAP_NAME in vc.keys():
            alphamap = vc[ALPHA_MAP_NAME].data
            alphamapname = ALPHA_MAP_NAME
            colorlen = len(alphamap)
        if vc.active.data == alphamap:
            # Alpha map is active--see if theres another map to use for colors. If not, 
            # colors will be set to white
            for c in vc:
                if c.data != alphamap:
                    colormap = c.data
                    colormapname = c.name
                    break
        else:
            colormap = vc.active.data
            colormapname = vc.active.name
            colorlen = len(colormap)

        log.debug(f"...Writing vertex colors from map {colormapname}, vertex alpha from {alphamapname}")
        loopcolors = [(0.0, 0.0, 0.0, 0.0)] * colorlen
        for i in range(0, colorlen):
            if colormap:
                c = colormap[i].color[:]
            else:
                c = (1.0, 1.0, 1.0, 1.0)
            if alphamap:
                a = alphamap[i].color
                c = (c[0], c[1], c[2], (a[0] + a[1] + a[2])/3)
            loopcolors[i] = c

        return loopcolors


    def extract_mesh_data(self, obj, arma, target_key):
        """ 
        Extract the triangularized mesh data from the given object
            obj = object being exported
            arma = controlling armature, if any. Needed so we can limit bone weights.
            target_key = shape key to export
        returns
            verts = list of XYZ vertex locations
            norms_new = list of XYZ normal values, 1:1 with verts
            uvmap_new = list of (u, v) values, 1:1 with verts
            colors_new = list of RGBA color values 1:1 with verts. May be None.
            tris = list of (t1, t2, t3) vert indices to define triangles
            weights_by_vert = [dict[group-name: weight], ...] 1:1 with verts
            morphdict = {shape-key: [verts...], ...} only if "target_key" is NOT specified
        NOTE this routine changes selection and switches to edit mode and back
        """
        editmesh = obj.data
        loopcolors = None
        
        try:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
                
            # This next little dance ensures the mesh.vertices locations are correct
            obj.active_shape_key_index = 0
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.object.mode_set(mode = 'OBJECT')
                
            editmesh.update()
         
            verts, weights_by_vert, morphdict \
                = extract_vert_info(obj, editmesh, arma, target_key)
        
            # Pull out vertex colors first because trying to access them later crashes
            bpy.ops.object.mode_set(mode = 'OBJECT') # Required to get vertex colors
            if len(editmesh.vertex_colors) > 0:
                loopcolors = self.extract_colors(editmesh)
        
            # Apply shape key verts to the mesh so normals will be correct.  If the mesh has
            # custom normals, fukkit -- use the custom normals and assume the deformation
            # won't be so great that it looks bad.
            bpy.ops.object.mode_set(mode = 'OBJECT') 
            uvlayer = editmesh.uv_layers.active.data
            if target_key != '' and \
                editmesh.shape_keys and \
                target_key in editmesh.shape_keys.key_blocks.keys() and \
                not editmesh.has_custom_normals:
                editmesh = mesh_from_key(editmesh, verts, target_key)
                    
            # Extracting and triangularizing
            partitions = partitions_from_vert_groups(obj)
            loops, uvs, norms, loopcolors, partition_map = \
                self.extract_face_info(
                    editmesh, uvlayer, loopcolors, weights_by_vert, partitions,
                    use_loop_normals=editmesh.has_custom_normals)
        
            log.info("..Splitting mesh along UV seams")
            mesh_split_by_uv(verts, loops, norms, uvs, weights_by_vert, morphdict)
            #log.info(f"..Loops as split: {loops}")

            # Make uv and norm lists 1:1 with verts (rather than with loops)
            log.debug(f"Length verts={len(verts)}, len loops={len(loops)}, len uvs={len(uvs)}, len norms={len(norms)}")
            uvmap_new = [(0.0, 0.0)] * len(verts)
            norms_new = [(0.0, 0.0, 0.0)] * len(verts)
            for i, vi in enumerate(loops):
                assert vi < len(verts), f"Error: Invalid vert index in loops: {vi} >= {len(verts)}"
                uvmap_new[vi] = uvs[i]
                norms_new[vi] = norms[i]
        
            ## Our "loops" list matches 1:1 with the mesh's loops. So we can use the polygons
            ## to pull the loops
            #tris = []
            #for p in editmesh.polygons:
            #    tris.append((loops[p.loop_start], loops[p.loop_start+1], loops[p.loop_start+2]))
            tris = []
            for i in range(0, len(loops), 3):
                tris.append((loops[i], loops[i+1], loops[i+2]))
        
            colors_new = None
            if len(loopcolors) > 0:
                log.debug(f"..Exporting vertex colors for shape {obj.name}")
                colors_new = [(0.0, 0.0, 0.0, 0.0)] * len(verts)
                for i, lp in enumerate(loops):
                    colors_new[lp] = loopcolors[i]
            else:
                log.debug(f"..No vertex colors in shape {obj.name}")
        
        finally:
            #obj.rotation_euler = original_rot
            #obj.data = originalmesh
            #obj.active_shape_key_index = saved_sk
            pass

        return verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, \
            morphdict, partitions, partition_map


    def export_shape_parents(self, obj):
        """ Export any parent NiNodes the shape might need 
            Returns the nif node that should be the parent of the shape (may be None)
        """
        ancestors = []
        p = obj.parent
        while p:
            ancestors.insert(0, p)
            p = p.parent

        last_parent = None
        ninode = None
        for p in ancestors:
            if p.type == 'EMPTY' and 'pynBlock_Name' in p:
                if p.name in self.objs_written:
                    ninode = self.objs_written[p.name]
                else:
                    ninode = self.nif.add_node(p.name, 
                                               TransformBuf.from_matrix(p.matrix_world),
                                               last_parent)
                    last_parent = p
                    log.debug(f"Writing shape parent {p.name} as {ninode}")
                    self.objs_written[p.name] = ninode
                    collisions = [x for x in p.children if x.name.startswith("bhkCollisionObject")]
                    if len(collisions) > 0:
                        self.export_collisions(collisions)
                    log.debug(f"Wrote {p.name} block")
        
        return ninode


    def get_bone_xforms(self, arma, bone_names, shape):
        """Return transforms for the bones in list, getting rotation from what we stashed on import. Checks the "preserve_hierarchy" flag to determine whether to return global 
          or local transforms.
            arma = data block of armature
            bone_names = list of names
            shape = shape being exported
            result = dict{bone-name: MatTransform, ...}
        """
        result = {}
        for b in arma.bones:
            result[b.name] = self.get_bone_xform(b)        
    
        return result

    def get_bone_xform(self, b:bpy_types.Bone) -> Matrix:
        """ Return the local transform represented by the bone """
        bonexf = get_bone_global_xf(b, self.game)
        #boneloc = b.head_local
        #try:
        #    bonerot = Quaternion(b['pynXform'])
        #except:
        #    log.debug(f"No 'pynXform' property on {b.name}")
        #    bonerot = Quaternion()
        #bonexf = MatrixLocRotScale(boneloc, bonerot, (1,1,1))
        # log.debug(f"{b.name} global transform: \n{bonexf}")

        if b.parent and (self.flags & ImportFlags.PRESERVE_HIERARCHY):
            # Calculate the relative transform from the parent
            boneloc, bonerot, bonescale = bonexf.decompose()
            parloc, parrot, parscale = get_bone_global_xf(b.parent, self.game).decompose()

            boneloc -= parloc
            # parentq = Quaternion(b.parent['pynXform'])
            bonerot.rotate(parrot.inverted())
            boneloc.rotate(parrot.inverted())

            bonexf = MatrixLocRotScale(boneloc, bonerot, (1,1,1))
            # log.debug(f"{b.name} local transform: \n{bonexf}")

        return bonexf


    def write_bone(self, shape:NiShape, b:bpy_types.Bone, writtenbones:dict):
        """ Write a shape's bone, writing all parent bones first if necessary 
            Returns the node in the target nif for the new bone """
        if b.name in writtenbones:
            return writtenbones[b.name]

        parname = None
        if b.parent:
            parname = self.write_bone(shape, b.parent, writtenbones)
        
        xf = self.get_bone_xform(b)

        if self.flags & ImportFlags.RENAME_BONES:
            nifname = self.nif.nif_name(b.name)
        else:
            nifname = b.name

        tb = TransformBuf.from_matrix(xf)

        #log.debug(f"Writing bone {nifname} with transform\n{tb}")
        shape.add_bone(nifname, tb, parname)
        writtenbones[b.name] = nifname
        return nifname


    def write_bone_hierarchy(self, shape:NiShape, arma:bpy.types.Armature, used_bones:list):
        """ Write the bone hierarchy to the nif. Do this first so that transforms 
        and parent/child relationships are correct. Do not assume that the skeleton is fully
        connected (do Blender armatures have to be fully connected?). 
        used_bones - list of bone names to write. """
        writtenbones = {}
        for b in used_bones:
            if b in arma.bones:
                self.write_bone(shape, arma.bones[b], writtenbones)


    def export_skin(self, obj, arma, new_shape, new_xform, weights_by_vert):
        log.info("..Parent is armature, skin the mesh")
        new_shape.skin()
        new_shape.transform = TransformBuf.from_matrix(new_xform)
        newxfi = new_xform.copy()
        newxfi.invert()
        new_shape.set_global_to_skin(TransformBuf.from_matrix(newxfi))
    
        group_names = [g.name for g in obj.vertex_groups]
        weights_by_bone = get_weights_by_bone(weights_by_vert)
        used_bones = weights_by_bone.keys()

        if self.flags & ImportFlags.PRESERVE_HIERARCHY:
            self.write_bone_hierarchy(new_shape, arma.data, used_bones)

        arma_bones = self.get_bone_xforms(arma.data, used_bones, new_shape)
    
        for bone_name, bone_xform in arma_bones.items():
            if bone_name in weights_by_bone and len(weights_by_bone[bone_name]) > 0:
                if self.flags & ImportFlags.RENAME_BONES:
                    nifname = new_shape.file.nif_name(bone_name)
                else:
                    nifname = bone_name

                tb = TransformBuf.from_matrix(bone_xform)
                # log.debug(f"Writing bone {nifname} with transform\n{tb}")
                new_shape.add_bone(nifname, tb)
                # log.debug(f"....Adding bone {nifname}")
                new_shape.setShapeWeights(nifname, weights_by_bone[bone_name])


    def export_shader(self, obj, shape: NiShape):
        """Create shader from the object's material"""
        log.debug(f"...exporting material for object {obj.name}")
        shader = shape.shader_attributes
        mat = obj.active_material

        # Use textures stored in properties as defaults; override them with shader nodes
        set_object_texture(shape, mat, 7)

        try:
            nodelist = mat.node_tree.nodes

            shader_node = None

            if not 'Principled BSDF' in nodelist:
                log.warning(f"...Have material but no Principled BSDF for {obj.name}")
            else:
                shader_node = nodelist['Principled BSDF']

            # Texture paths
            if shader_node:
                export_shader_attrs(obj, shader_node, shape)

                for textureslot in range(0, 9):
                    foundpath = ""
                
                    if textureslot == 0:
                        diffuse_input = shader_node.inputs['Base Color']
                        if diffuse_input and diffuse_input.is_linked:
                            diffuse_node = diffuse_input.links[0].from_node
                            if hasattr(diffuse_node, 'image') and diffuse_node.image:
                                foundpath = diffuse_node.image.filepath
                
                    elif textureslot == 1:
                        normal_input = shader_node.inputs['Normal']
                        is_obj_space = False
                        if normal_input and normal_input.is_linked:
                            nmap_node = normal_input.links[0].from_node
                            if nmap_node.bl_idname == 'ShaderNodeNormalMap':
                                is_obj_space = (nmap_node.space == "OBJECT")
                                if is_obj_space:
                                    shape.shader_attributes.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
                                else:
                                    shape.shader_attributes.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)
                                image_node = get_image_node(nmap_node.inputs['Color'])
                                if image_node and image_node.image:
                                    norm_txt_node = image_node
                                    foundpath = norm_txt_node.image.filepath

                    elif textureslot == 2:
                        sk_node = get_image_node(shader_node.inputs['Subsurface Color'])
                        if sk_node and sk_node.image:
                            foundpath = sk_node.image.filepath

                    elif textureslot == 7:
                        if is_obj_space:
                            spec_node = get_image_node(shader_node.inputs['Specular'])
                            if spec_node and spec_node.image:
                                    foundpath = spec_node.image.filepath

                    # Use the shader node path if it's usable, the one stashed in 
                    # custom properties if not
                    txtidx = foundpath.lower().find('textures')
                    ext = foundpath[-3:]
                    if txtidx >= 0 and ext.lower() == "dds":
                        texturepath = foundpath[txtidx:]
                    else:
                        try:
                            texturepath = mat[f'BSShaderTextureSet_{textureslot}']
                        except:
                            texturepath = ""

                    if len(texturepath) > 0:
                        #log.debug(f"....Writing diffuse texture path {textureslot}: '{texturepath}'")
                        shape.set_texture(textureslot, texturepath)

            # Write alpha if any after the textures
            alpha_input = shader_node.inputs['Alpha']
            if alpha_input and alpha_input.is_linked:
                mat = obj.active_material
                if 'NiAlphaProperty_flags' in mat.keys():
                    shape.alpha_property.flags = mat['NiAlphaProperty_flags']
                else:
                    shape.alpha_property.flags = 4844
                shape.alpha_property.threshold = int(mat.alpha_threshold * 255)
                #if 'NiAlphaProperty_threshold' in mat.keys():
                #    shape.alpha_property.threshold = mat['NiAlphaProperty_threshold']
                #else:
                #    shape.alpha_property.threshold = 128
                shape.save_alpha_property()

        except:
            log.warning(f"Couldn't parse the shader nodes on {obj.name}")
            self.warnings.add('WARNING')


    def export_shape(self, obj, target_key='', arma=None):
        """ Export given blender object to the given NIF file; also writes any associated
            tri file. Checks to make sure the object
            wasn't already written.
            obj = blender object
            target_key = shape key to export
            arma = armature to skin to
            """
        if obj.name in self.objs_written:
            return
        self.active_obj = obj

        my_parent = self.export_shape_parents(obj)

        log.info("Exporting " + obj.name)
        log.info(f" . with shapes: {self.file_keys}")

        retval = set()

        is_skinned = (arma is not None)
        unweighted = []
        if UNWEIGHTED_VERTEX_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[UNWEIGHTED_VERTEX_GROUP])
        if MULTIPLE_PARTITION_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[MULTIPLE_PARTITION_GROUP])
        if NO_PARTITION_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[NO_PARTITION_GROUP])
        
        if is_skinned:
            # Get unweighted bones before we muck up the list by splitting edges
            unweighted = tag_unweighted(obj, arma.data.bones.keys())
            if not expected_game(self.nif, arma.data.bones):
                log.warning(f"Exporting to game that doesn't match armature: game={self.nif.game}, armature={arma.name}")
                retval.add('GAME')

        verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, morphdict, \
            partitions, partition_map = \
           self.extract_mesh_data(obj, arma, target_key)

        is_headpart = obj.data.shape_keys \
                and len(self.nif.dict.expression_filter(set(obj.data.shape_keys.key_blocks.keys()))) > 0
        if is_headpart:
            log.debug(f"...shape is headpart, shape keys = {self.nif.dict.expression_filter(set(obj.data.shape_keys.key_blocks.keys()))}")

        obj.data.update()
        norms_exp = norms_new
        has_msn = has_msn_shader(obj)
        if has_msn:
            norms_exp = None

        is_effectshader = False
        mat = None
        if obj.active_material:
           mat = obj.active_material
        if mat and 'BS_Shader_Block_Name' in mat:
            is_effectshader = (mat['BS_Shader_Block_Name'] == 'BSEffectShaderProperty')

        log.debug(f"..Exporting '{obj.name}' to nif: {len(verts)} vertices, {len(tris)} tris, parent {my_parent}")
        new_shape = self.nif.createShapeFromData(obj.name, verts, tris, uvmap_new, norms_exp,
                                                 is_headpart, is_skinned, is_effectshader,
                                                 parent=my_parent)
        if colors_new:
            new_shape.set_colors(colors_new)

        self.export_shape_data(obj, new_shape)
        
        if mat:
            self.export_shader(obj, new_shape)
            log.debug(f"....'{new_shape.name}' has textures: {new_shape.textures}")
            if has_msn:
                new_shape.shader_attributes.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
            else:
                new_shape.shader_attributes.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)
            if colors_new:
                new_shape.shader_attributes.shaderflags2_set(ShaderFlags2.VERTEX_COLORS)
            else:
                new_shape.shader_attributes.shaderflags2_clear(ShaderFlags2.VERTEX_COLORS)
            log.debug(f"Object {obj.name} has vertex color maps {[vc.name for vc in obj.data.vertex_colors]}")
            if ALPHA_MAP_NAME in obj.data.vertex_colors.keys():
                new_shape.shader_attributes.shaderflags1_set(ShaderFlags1.VERTEX_ALPHA)
            else:
                new_shape.shader_attributes.shaderflags1_clear(ShaderFlags1.VERTEX_ALPHA)
                
            new_shape.save_shader_attributes()
        else:
            log.debug(f"..No material on {obj.name}")

        if is_skinned:
            self.nif.createSkin()

        #new_xform = obj.matrix_world.copy()
        new_xform = obj.matrix_local.copy()
        if not has_uniform_scale(obj):
            l, r, s = new_xform.decompose()
            new_xform = MatrixLocRotScale(l, r, Vector((1,1,1)))
        
        if is_skinned:
            self.export_skin(obj, arma, new_shape, new_xform, weights_by_vert)
            if len(unweighted) > 0:
                create_group_from_verts(obj, UNWEIGHTED_VERTEX_GROUP, unweighted)
                log.warning("Some vertices are not weighted to the armature in object {obj.name}")
                self.objs_unweighted.add(obj)

            # partitions, tri_indices = self.export_partitions(obj, weights_by_vert, tris)
            if len(partitions) > 0:
                if 'FO4_SEGMENT_FILE' in obj.keys():
                    log.debug(f"....Writing segment file {obj['FO4_SEGMENT_FILE']}")
                    new_shape.segment_file = obj['FO4_SEGMENT_FILE']

                # log.debug(f"Partitions for export: {partitions.keys()}, {partition_map[0:20]}")
                new_shape.set_partitions(partitions.values(), partition_map)

            self.export_collisions([c for c in arma.children if c.name.startswith("bhkCollisionObject")])
        else:
            log.debug(f"...Exporting {new_shape.name} with transform \n{new_xform}")
            new_shape.transform = TransformBuf.from_matrix(new_xform)

        self.export_collisions([c for c in obj.children if c.name.startswith("bhkCollisionObject")])

        self.objs_written[obj.name] = new_shape

        obj['PYN_GAME'] = self.game
        obj['PYN_RENAME_BONES'] = (self.flags & ImportFlags.RENAME_BONES) != 0
        obj['PYN_PRESERVE_HIERARCHY'] = (self.flags & ImportFlags.PRESERVE_HIERARCHY) != 0

        retval |= self.export_tris(obj, verts, tris, uvmap_new, morphdict)
        log.info(f"..{obj.name} successfully exported to {self.nif.filepath}")
        return retval


    def export_file_set(self, arma, suffix=''):
        """ Create a set of nif files from the given object, using the given armature and appending
            the suffix. One file is created per shape key with the shape key used as suffix. Associated
            TRIP files are exported if there is TRIP info.
                arma = skeleton to use 
                suffix = suffix to append to the filenames, after the shape key suffix
            """
        if self.file_keys is None or len(self.file_keys) == 0:
            shape_keys = ['']
        else:
            shape_keys = self.file_keys

        for sk in shape_keys:
            fname_ext = os.path.splitext(os.path.basename(self.filepath))
            fbasename = fname_ext[0] + sk + suffix
            fnamefull = fbasename + fname_ext[1]
            fpath = os.path.join(os.path.dirname(self.filepath), fnamefull)

            self.objs_written.clear()

            log.info(f"..Exporting to {self.game} {fpath}")
            self.nif = NifFile()

            rt = "NiNode"
            rn = "Scene Root"

            shape = next(iter(self.objects))
            if "pynRootNode_BlockType" in shape:
                rt = shape["pynRootNode_BlockType"]
            if "pynRootNode_Name" in shape:
                rn = shape["pynRootNode_Name"]
            
            self.nif.initialize(self.game, fpath, rt, rn)
            if "pynRootNode_Flags" in shape:
                log.debug(f"Root node flags are '{shape['pynRootNode_Flags']}' = '{RootFlags.parse(shape['pynRootNode_Flags']).value}'")
                self.nif.rootNode.flags = RootFlags.parse(shape["pynRootNode_Flags"]).value

            if suffix == '_faceBones':
                self.nif.dict = fo4FaceDict

            self.trip = TripFile()
            trippath = os.path.join(os.path.dirname(self.filepath), fbasename) + ".tri"

            for obj in self.objects:
                self.export_shape(obj, sk, arma)
                log.debug(f"Exported shape {obj.name}")

            # Check for bodytri morphs--write the extra data node if needed
            log.debug(f"TRIP data: shapes={len(self.trip.shapes)}, bodytri written: {self.bodytri_written}, filepath: {truncate_filename(trippath, 'meshes')}")
            if len(self.trip.shapes) > 0 and not self.bodytri_written:
                self.nif.string_data = [('BODYTRI', truncate_filename(trippath, "meshes"))]

            self.export_collisions([c for c in self.collisions if c.parent == None])
            self.export_extra_data()

            self.nif.save()
            log.info(f"..Wrote {fpath}")
            self.message_log.append(self.nif.message_log())

            if len(self.trip.shapes) > 0:
                self.trip.write(trippath)
                log.info(f"..Wrote {trippath}")


    def execute(self):
        if not self.objects:
            log.warning(f"No objects selected for export")
            self.warnings.add('NOTHING')
            return

        log.debug(f"""
Exporting objects: {self.objects}
string data: {self.str_data}
BG data: {self.bg_data}
cloth data: {self.cloth_data}
collisions: {self.collisions}
armature: {self.armature}
facebones: {self.facebones}""")
        NifFile.clear_log()
        if self.facebones:
            self.export_file_set(self.facebones, '_faceBones')
        if self.armature:
            self.export_file_set(self.armature, '')
        if self.facebones is None and self.armature is None:
            self.export_file_set(None, '')
        log.debug("Nifly Message Log:\n" + NifFile.message_log())
    
    def export(self, objects):
        self.set_objects(objects)
        self.execute()

    @classmethod
    def do_export(cls, filepath, game, objects):
        return NifExporter(filepath, game).export(objects)
        

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

    rename_bones: bpy.props.BoolProperty(
        name="Rename Bones",
        description="Rename bones from Blender conventions back to nif.",
        default=True)

    preserve_hierarchy: bpy.props.BoolProperty(
        name="Preserve Bone Hierarchy",
        description="Preserve bone hierarchy in exported nif.",
        default=False)


    def __init__(self):
        obj = bpy.context.object
        if obj is None:
            self.report({"ERROR"}, "No active object to export")
            return

        self.filepath = clean_filename(obj.name)
        arma = None
        if obj.type == "ARMATURE":
            arma = obj
        else:
            if obj.parent and obj.parent.type == "ARMATURE":
                arma = obj.parent
        g = ""
        try:
            g = obj['PYN_GAME']
        except:
            if arma:
                g = best_game_fit(arma.data.bones)
        if g != "":
            self.target_game = g
        
        if 'PYN_RENAME_BONES' in obj and obj['PYN_RENAME_BONES']:
            self.rename_bones = True
        else:
            self.rename_bones = False

        if 'PYN_PRESERVE_HIERARCHY' in obj and obj['PYN_PRESERVE_HIERARCHY']:
            self.preserve_hierarchy = True
        else:
            self.preserve_hierarchy = False

        
    @classmethod
    def poll(cls, context):
        if context.object is None:
            log.error("Must select an object to export")
            return False

        if context.object.mode != 'OBJECT':
            log.error("Must be in Object Mode to export")
            return False

        return True

    def execute(self, context):
        res = set()

        if not self.poll(context):
            self.report({"ERROR"}, f"Cannot run exporter--see system console for details")
            return {'CANCELLED'} 

        flags = 0
        if self.rename_bones:
            flags = ImportFlags.RENAME_BONES
        if self.preserve_hierarchy:
            flags |= ImportFlags.PRESERVE_HIERARCHY

        log.info("\n\n\n==============================\nNIFLY EXPORT V%d.%d.%d\n==============================" % bl_info['version'])
        NifFile.Load(nifly_path)

        try:
            exporter = NifExporter(self.filepath, self.target_game, export_flags=flags)
            exporter.from_context(context)
            exporter.export(context.selected_objects)
            
            rep = False
            if len(exporter.objs_unweighted) > 0:
                self.report({"ERROR"}, f"The following objects have unweighted vertices.See the '*UNWEIGHTED*' vertex group to find them: \n{exporter.objs_unweighted}")
                rep = True
            if len(exporter.objs_scale) > 0:
                self.report({"ERROR"}, f"The following objects have non-uniform scale, which nifs do not support. Scale applied to verts before export.\n{exporter.objs_scale}")
                rep = True
            if len(exporter.objs_mult_part) > 0:
                self.report({'WARNING'}, f"Some faces have been assigned to more than one partition, which should never happen.\n{exporter.objs_mult_part}")
                rep = True
            if len(exporter.objs_no_part) > 0:
                self.report({'WARNING'}, f"Some faces have been assigned to no partition, which should not happen for skinned body parts.\n{exporter.objs_no_part}")
                rep = True
            if len(exporter.arma_game) > 0:
                self.report({'WARNING'}, f"The armature appears to be designed for a different game--check that it's correct\nArmature: {exporter.arma_game}, game: {exporter.game}")
                rep = True
            if 'NOTHING' in exporter.warnings:
                self.report({'WARNING'}, f"No mesh selected; nothing to export")
                rep = True
            if 'WARNING' in exporter.warnings:
                self.report({'WARNING'}, f"Export completed with warnings. Check the console window.")
                rep = True
            if not rep:
                self.report({'INFO'}, f"Export successful")
            
        except:
            log.exception("Export of nif failed")
            self.report({"ERROR"}, "Export of nif failed, see console window for details")
            res.add("CANCELLED")

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



def run_tests():
    print("""
    ############################################################
    ##                                                        ##
    ##                        TESTING                         ##
    ##                                                        ##
    ############################################################
    """)

    from test_tools import test_title, clear_all, append_from_file, export_from_blend, find_vertex, remove_file, find_shape
    from pynifly_tests import run_tests

    NifFile.Load(nifly_path)
    #LoggerInit()

    clear_all()

    # Tests in this file are for functionality under development. They should be moved to
    # pynifly_tests.py when stable.


    if True: # TEST_BPY_ALL or TEST_HYENA_PARTITIONS:
        test_title("TEST_HYENA_PARTITIONS", "Partitions export successfully, with warning")

        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_HYENA_PARTITIONS.nif")
        remove_file(outfile)

        append_from_file("HyenaMaleHead", True, r"tests\FO4\HyenaHead.blend", r"\Object", "HyenaMaleHead")
        append_from_file("Skeleton", True, r"tests\FO4\HyenaHead.blend", r"\Object", "Skeleton")
        exporter = NifExporter(outfile, "FO4")
        exporter.export([bpy.data.objects["HyenaMaleHead"], bpy.data.objects["FaceBones.Skel"], bpy.data.objects["Skeleton"]])
        assert len(exporter.warnings) == 1, f"One warning reported ({exporter.warnings})"

        nif1 = NifFile(outfile)
        assert len(nif1.shapes) == 1, "Wrote the file successfully"

    if True: # TEST_BPY_ALL or TEST_SK_MULT:
        test_title("TEST_SK_MULT", "Export multiple objects with only some shape keys")

        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_SK_MULT.nif")
        remove_file(outfile)

        append_from_file("CheMaleMane", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "CheMaleMane")
        append_from_file("MaleTail", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "MaleTail")
        exporter = NifExporter(outfile, "SKYRIMSE")
        exporter.export([bpy.data.objects["CheMaleMane"], bpy.data.objects["MaleTail"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SK_MULT_1.nif"))
        assert len(nif1.shapes) == 2, "Wrote the file successfully"


    if True: # TEST_BPY_ALL or TEST_MULT_PART:
        test_title("TEST_MULT_PART", "Export shape with face that might fall into multiple partititions")

        clear_all()

        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_MULT_PART.nif")
        remove_file(outfile)
        append_from_file("MaleHead", True, r"tests\SkyrimSE\multiple_partitions.blend", r"\Object", "MaleHead")
        exporter = NifExporter(outfile, "SKYRIMSE")
        obj = bpy.data.objects["MaleHead"]
        exporter.export([obj])

        assert "*MULTIPLE_PARTITIONS*" not in obj.vertex_groups, f"Exported without throwing *MULTIPLE_PARTITIONS* error"



    if TEST_BPY_ALL:
        run_tests(pynifly_dev_path, NifExporter, NifImporter, import_tri)



    print("""
    ############################################################
    ##                                                        ##
    ##                    TESTS DONE                          ##
    ##                                                        ##
    ############################################################
    """)


if __name__ == "__main__":
    try:
        log.setLevel(logging.DEBUG)
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
