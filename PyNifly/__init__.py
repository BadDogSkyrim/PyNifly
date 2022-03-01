"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.


RUN_TESTS = True
TEST_BPY_ALL = True


bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (3, 0, 0),
    "version": (2, 2, 0),  
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
from mathutils import Matrix, Vector, Quaternion
import re
import codecs
from typing import Collection

log = logging.getLogger("pynifly")
log.info(f"Loading pynifly version {bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}")

pynifly_dev_root = r"C:\Users\User\OneDrive\Dev"
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")
nifly_path = os.path.join(pynifly_dev_root, r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll")

if os.path.exists(nifly_path):
    log.debug(f"PyNifly dev path: {pynifly_dev_path}")
    if pynifly_dev_path not in sys.path:
        sys.path.append(pynifly_dev_path)
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

from pynifly import *
from niflytools import *
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

#log.setLevel(logging.DEBUG)
#pynifly_ch = logging.StreamHandler()
#pynifly_ch.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(name)s-%(levelname)s: %(message)s')
#pynifly_ch.setFormatter(formatter)
#log.addHandler(ch)

# Extend TransformBuf to get/give contents as a Blender Matrix

def transform_to_matrix(xf: TransformBuf) -> Matrix:
    return Matrix.LocRotScale(xf.translation[:], 
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

#def get_quat_from_blend(blenderobj):
#    v = blenderobj.rotation_mode
#    blenderobj.rotation_mode = 'QUATERNION'
#    q = blenderobj.rotation_quaternion
#    qr = Quaternion([q.w, q.x, q.y, q.z])
#    blenderobj.rotation_mode = v
#    return qr

#def get_xform_from_blend(blender_object):
#    """ Return a MatTransform to capture blender object location """
#    m = MatTransform()
#    m.translation = Vector(blender_object.location[:])
#    blender_object.rotation_mode = 'QUATERNION'
#    q = blender_object.rotation_quaternion
#    m.rotation = RotationMatrix.from_quaternion(Quaternion([q.w, q.x, q.y, q.z]))
#    m.scale = sum(blender_object.scale[:])/3t
#    return m

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
    #    material['BSLSP_Shader_Flags_1'] = hex(attrs.Shader_Flags_1)
    #    material['BSLSP_Shader_Flags_2'] = hex(attrs.Shader_Flags_2)
    #    material['BSSP_UV_Offset_U'] = attrs.UV_Offset_U
    #    material['BSSP_UV_Offset_V'] = attrs.UV_Offset_V
    #    material['BSSP_UV_Scale_U'] = attrs.UV_Scale_U
    #    material['BSSP_UV_Scale_V'] = attrs.UV_Scale_V
        shader.inputs['Emission'].default_value = (attrs.Emissive_Color_R, attrs.Emissive_Color_G, attrs.Emissive_Color_B, attrs.Emissive_Color_A)
        shader.inputs['Emission Strength'].default_value = attrs.Emissive_Mult

        if shape.shader_block_name == 'BSLightingShaderProperty':
    #        material['BSLSP_Shader_Type'] = attrs.Shader_Type
            shader.inputs['Alpha'].default_value = attrs.Alpha
    #        material['BSLSP_Refraction_Str'] = attrs.Refraction_Str
            shader.inputs['Metallic'].default_value = attrs.Glossiness/GLOSS_SCALE
    #        material['BSLSP_Spec_Color_R'] = attrs.Spec_Color_R
    #        material['BSLSP_Spec_Color_G'] = attrs.Spec_Color_G
    #        material['BSLSP_Spec_Color_B'] = attrs.Spec_Color_B
    #        material['BSLSP_Spec_Str'] = attrs.Spec_Str
    #        material['BSLSP_Soft_Lighting'] = attrs.Soft_Lighting
    #        material['BSLSP_Rim_Light_Power'] = attrs.Rim_Light_Power
    #        material['BSLSP_Skin_Tint_Color_R'] = attrs.Skin_Tint_Color_R
    #        material['BSLSP_Skin_Tint_Color_G'] = attrs.Skin_Tint_Color_G
    #        material['BSLSP_Skin_Tint_Color_B'] = attrs.Skin_Tint_Color_B
        elif shape.shader_block_name == 'BSEffectShaderProperty':
            shader.inputs['Alpha'].default_value = attrs.Falloff_Start_Opacity
    #        material['BSESP_Falloff_Start_Angle'] = attrs.Falloff_Start_Angle
    #        material['BSESP_Falloff_Start_Opacity'] = attrs.Falloff_Start_Opacity
    #        material['BSESP_Falloff_Stop_Angle'] = attrs.Falloff_Stop_Opacity
    #        material['BSESP_Soft_Fallof_Depth'] = attrs.Soft_Fallof_Depth
    #        material['BSESP_Env_Map_Scale'] = attrs.Env_Map_Scale
    #        material['BSESP_Tex_Clamp_Mode'] = attrs.Tex_Clamp_mode

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

    nifpath = shape.parent.filepath

    fulltextures = extend_filenames(nifpath, "meshes", shape.textures)
    missing = missing_files(fulltextures)
    if len(missing) > 0:
        log.warning(f". . Some texture files not found: {missing}")
    #if not check_files(fulltextures):
    #    log.debug(f". . texture files not available, not creating material: \n\tnif path = {nifpath}\n\t textures = {fulltextures}")
    #    return
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

        if shape.parent.game in ["FO4"]:
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
        elif shape.parent.game == 'FO4':
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

        if shape.parent.game in ["SKYRIM", "SKYRIMSE"] and \
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

    #if 'BSLSP_Shader_Flags_1' in mat.keys():
    #    shape.shader_attributes.Shader_Flags_1 = int(mat['BSLSP_Shader_Flags_1'], 16)
    #if 'BSLSP_Shader_Flags_2' in mat.keys():
    #    shape.shader_attributes.Shader_Flags_2 = int(mat['BSLSP_Shader_Flags_2'], 16)
    #if 'BSSP_UV_Offset_U' in mat.keys():
    #    shape.shader_attributes.UV_Offset_U = mat['BSSP_UV_Offset_U']
    #if 'BSSP_UV_Offset_V' in mat.keys():
    #    shape.shader_attributes.UV_Offset_V = mat['BSSP_UV_Offset_V']
    #if 'BSSP_UV_Scale_U' in mat.keys():
    #    shape.shader_attributes.UV_Scale_U = mat['BSSP_UV_Scale_U']
    #if 'BSSP_UV_Scale_V' in mat.keys():
    #    shape.shader_attributes.UV_Scale_V = mat['BSSP_UV_Scale_V']
    shape.shader_attributes.Emissive_Color_R = shader.inputs['Emission'].default_value[0]
    shape.shader_attributes.Emissive_Color_G = shader.inputs['Emission'].default_value[1]
    shape.shader_attributes.Emissive_Color_B = shader.inputs['Emission'].default_value[2]
    shape.shader_attributes.Emissive_Color_A = shader.inputs['Emission'].default_value[3]
    shape.shader_attributes.Emissive_Mult = shader.inputs['Emission Strength'].default_value

    #if ('BS_Shader_Block_Name' in mat) and (mat['BS_Shader_Block_Name'] == 'BSEffectShaderProperty'):
    #    if 'BSESP_Falloff_Start_Angle' in mat.keys():
    #        shape.shader_attributes.Falloff_Start_Angle = mat['BSESP_Falloff_Start_Angle']
    #    if 'BSESP_Falloff_Start_Opacity' in mat.keys():
    #        shape.shader_attributes.Falloff_Start_Opacity = mat['BSESP_Falloff_Start_Opacity']
    #    if 'BSESP_Falloff_Stop_Angle' in mat.keys():
    #        shape.shader_attributes.Falloff_Stop_Angle = mat['BSESP_Falloff_Stop_Angle']
    #    if 'BSESP_Soft_Fallof_Depth' in mat.keys():
    #        shape.shader_attributes.Soft_Fallof_Depth = mat['BSESP_Soft_Fallof_Depth']
    #    if 'BSESP_Env_Map_Scale' in mat.keys():
    #        shape.shader_attributes.Env_Map_Scale = mat['BSESP_Env_Map_Scale']
    #    if 'BSESP_Tex_Clamp_Mode' in mat.keys():
    #        shape.shader_attributes.Tex_Clamp_Mode = mat['BSESP_Tex_Clamp_Mode']

    #else:
    #    if 'BSLSP_Shader_Type' in mat.keys():
    #        shape.shader_attributes.Shader_Type = int(mat['BSLSP_Shader_Type'])
    if shape.shader_block_name == "BSLightingShaderProperty":
        shape.shader_attributes.Alpha = shader.inputs['Alpha'].default_value
        shape.shader_attributes.Glossiness = shader.inputs['Metallic'].default_value * GLOSS_SCALE
    #    if 'BSLSP_Refraction_Str' in mat.keys():
    #        shape.Refraction_Str = mat['BSLSP_Refraction_Str']
    #    shape.shader_attributes.Glossiness = shader.inputs['Metallic'].default_value * GLOSS_SCALE
    #    if 'BSLSP_Spec_Color_R' in mat.keys():
    #        shape.shader_attributes.Spec_Color_R = mat['BSLSP_Spec_Color_R']
    #    if 'BSLSP_Spec_Color_G' in mat.keys():
    #        shape.shader_attributes.Spec_Color_G = mat['BSLSP_Spec_Color_G']
    #    if 'BSLSP_Spec_Color_B' in mat.keys():
    #        shape.shader_attributes.Spec_Color_B = mat['BSLSP_Spec_Color_B']
    #    if 'BSLSP_Spec_Str' in mat.keys():
    #        shape.shader_attributes.Spec_Str = mat['BSLSP_Spec_Str']
    #    if 'BSLSP_Spec_Str' in mat.keys():
    #        shape.shader_attributes.Soft_Lighting = mat['BSLSP_Soft_Lighting']
    #    if 'BSLSP_Spec_Str' in mat.keys():
    #        shape.shader_attributes.Rim_Light_Power = mat['BSLSP_Rim_Light_Power']
    #    if 'BSLSP_Skin_Tint_Color_R' in mat.keys():
    #        shape.shader_attributes.Skin_Tint_Color_R = mat['BSLSP_Skin_Tint_Color_R']
    #    if 'BSLSP_Skin_Tint_Color_G' in mat.keys():
    #        shape.shader_attributes.Skin_Tint_Color_G = mat['BSLSP_Skin_Tint_Color_G']
    #    if 'BSLSP_Skin_Tint_Color_B' in mat.keys():
    #        shape.shader_attributes.Skin_Tint_Color_G = mat['BSLSP_Skin_Tint_Color_B']

    #log.debug(f"Shader Type: {shape.shader_attributes.Shader_Type}")
    #log.debug(f"Shader attributes: \n{shape.shader_attributes}")

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


def export_shader(obj, shape: NiShape):
    """Create shader from the object's material"""
    log.debug(f"...exporting material for object {obj.name}")
    shader = shape.shader_attributes
    mat = obj.active_material

    # Use textures stored in properties as defaults; override them with shader nodes
    set_object_texture(shape, mat, 7)

    try:
        nodelist = mat.node_tree.nodes

        shader_node = None
        diffuse_fp = None
        norm_fp = None
        sk_fp = None
        spec_fp = None

        if not 'Principled BSDF' in nodelist:
            log.warning(f"...Have material but no Principled BSDF for {obj.name}")
        else:
            shader_node = nodelist['Principled BSDF']

        for i in [3, 4, 5, 6, 8]:
            set_object_texture(shape, mat, i)
    
        # Texture paths
        norm_txt_node = None
        if shader_node:
            export_shader_attrs(obj, shader_node, shape)

            diffuse_input = shader_node.inputs['Base Color']
            if diffuse_input and diffuse_input.is_linked:
                diffuse_node = diffuse_input.links[0].from_node
                if hasattr(diffuse_node, 'image') and diffuse_node.image:
                    diffuse_fp_full = diffuse_node.image.filepath
                    diffuse_fp = diffuse_fp_full[diffuse_fp_full.lower().find('textures'):]
                    log.debug(f"....Writing diffuse texture path '{diffuse_fp}'")
        
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
                        norm_fp_full = norm_txt_node.image.filepath
                        norm_fp = norm_fp_full[norm_fp_full.lower().find('textures'):]
                        log.debug(f"....Writing normal texture path '{norm_fp}'")

            sk_node = get_image_node(shader_node.inputs['Subsurface Color'])
            if sk_node and sk_node.image:
                sk_fp_full = sk_node.image.filepath
                sk_fp = sk_fp_full[sk_fp_full.lower().find('textures'):]
                log.debug(f"....Writing subsurface texture path '{sk_fp}'")

            # Separate specular slot is only used if it's a MSN
            if is_obj_space:
                spec_node = get_image_node(shader_node.inputs['Specular'])
                if spec_node and spec_node.image:
                        spec_fp_full = spec_node.image.filepath
                        spec_fp = spec_fp_full[spec_fp_full.lower().find('textures'):]
                        log.debug(f"....Writing subsurface texture path '{spec_fp}'")

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

        else:
            log.warning(f"...Have material but no shader node for {obj.name}")

        if diffuse_fp:
            shape.set_texture(0, diffuse_fp)
        else:
            set_object_texture(shape, mat, 0)
        if norm_fp:
            shape.set_texture(1, norm_fp)
        else:
            set_object_texture(shape, mat, 1)
        if sk_fp:
            shape.set_texture(2, sk_fp)
        else:
            set_object_texture(shape, mat, 2)
        if spec_fp:
            shape.set_texture(7, spec_fp)
        else:
            set_object_texture(shape, mat, 7)
    except:
        log.warning(f"...Could not use shader nodes for {obj.name}, using cached texture paths")


# -----------------------------  MESH CREATION -------------------------------\

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
            xlate_name = the_shape.parent.blender_name(bone_name)
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
    try:
        if shape.colors and len(shape.colors) > 0:
            log.debug(f"..Importing vertex colors for {shape.name}")
            clayer = mesh.vertex_colors.new()
            alphlayer = mesh.vertex_colors.new()
            alphlayer.name = ALPHA_MAP_NAME
        
            colors = shape.colors
            for lp in mesh.loops:
                c = colors[lp.vertex_index]
                clayer.data[lp.index].color = (c[0], c[1], c[2], 1.0)
                alph = colors[lp.vertex_index][3]
                alphlayer.data[lp.index].color = [alph, alph, alph, 1.0]
    except:
        log.error(f"ERROR: Could not read colors on shape {shape.name}")


def get_node_location(the_shape: NiShape) -> Matrix:
    """ Returns location of the_shape ready for blender as a transform """
    try:
        if the_shape.has_skin_instance:
            # Global-to-skin transform is what offsets all the vertices together, e.g. so that
            # heads can be positioned at the origin. Put the reverse transform on the blender 
            # object so they can be worked on in their skinned position.
            # Use the one on the NiSkinData if it exists.
            xform = the_shape.global_to_skin_data
            if xform is None:
                xform = the_shape.global_to_skin
            # log.debug(f"....Found transform {the_shape.global_to_skin} on {the_shape.name} in '{self.nif.filepath}'")
            xf = xform.as_matrix()
            xf.invert()
            return xf
            #new_object.matrix_world = inv_xf.as_matrix()
            #new_object.location = inv_xf.translation
    except:
        pass

    # Statics get transformed according to the shape's transform
    # new_object.scale = (the_shape.transform.scale, ) * 3
    # xf = the_shape.transform.invert()
    # new_object.matrix_world = xf.as_matrix() 
    # new_object.location = the_shape.transform.translation
    xf = the_shape.transform
    log.debug(f". . shape {the_shape.name} transform: {xf}")
    return xf.as_matrix()
    #new_object.matrix_world = the_shape.transform.invert().as_matrix()
    #new_object.location = the_shape.transform.translation
    #new_object.scale = [the_shape.transform.scale] * 3
    #log.debug(f". . New object transform: \n{new_object.matrix_world}")


class NifImporter():
    """Does the work of importing a nif, independent of Blender's operator interface"""
    class ImportFlags(IntFlag):
        CREATE_BONES = 1
        RENAME_BONES = 1 << 1
        ROTATE_MODEL = 1 << 2

    def __init__(self, 
                 filename: str, 
                 f: ImportFlags = ImportFlags.CREATE_BONES | ImportFlags.RENAME_BONES):
        self.filename = filename
        self.flags = f
        self.armature = None
        self.bones = set()
        self.objects_created = []
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
        extradata = []

        for s in f.string_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "NiStringExtraData"
            ed.show_name = True
            ed['NiStringExtraData_Name'] = s[0]
            ed['NiStringExtraData_Value'] = s[1]
            extradata.append(ed)

        for s in f.behavior_graph_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSBehaviorGraphExtraData"
            ed.show_name = True
            ed['BSBehaviorGraphExtraData_Name'] = s[0]
            ed['BSBehaviorGraphExtraData_Value'] = s[1]
            extradata.append(ed)

        for c in f.cloth_data: 
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSClothExtraData"
            ed.show_name = True
            ed['BSClothExtraData_Name'] = c[0]
            ed['BSClothExtraData_Value'] = codecs.encode(c[1], 'base64')
            extradata.append(ed)

        b = f.bsx_flags
        if b:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSXFlags"
            ed.show_name = True
            ed['BSXFlags_Name'] = b[0]
            ed['BSXFlags_Value'] = BSXFlags(b[1]).fullname
            extradata.append(ed)

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
            extradata.append(ed)


        return extradata


    def import_shape_extra(self, obj, shape):
        """ Import any extra data from the shape if given or the root if not, and create 
        corresponding shapes """
        extradata = []
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
            extradata.append(ed)

        for s in shape.behavior_graph_data:
            bpy.ops.object.add(radius=1.0, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSBehaviorGraphExtraData"
            ed.show_name = True
            ed['BSBehaviorGraphExtraData_Name'] = s[0]
            ed['BSBehaviorGraphExtraData_Value'] = s[1]
            ed.parent = obj
            extradata.append(ed)

        return extradata


    def import_shape(self, the_shape: NiShape):
        """ Import the shape to a Blender object, translating bone names 
            self.objects_created = Set to a list of objects created. Might be more than one because 
                of extra data nodes.
        """
        log.debug(f". Importing shape {the_shape.name}")
        v = the_shape.verts
        t = the_shape.tris

        new_mesh = bpy.data.meshes.new(the_shape.name)
        new_mesh.from_pydata(v, [], t)
        new_object = bpy.data.objects.new(the_shape.name, new_mesh)
        self.objects_created.append(new_object)
    
        import_colors(new_mesh, the_shape)

        log.info(f". . import flags: {self.flags}")
        new_object.matrix_world = get_node_location(the_shape)

        if self.flags & self.ImportFlags.ROTATE_MODEL:
            log.info(f". . Rotating model to match blender")
            r = new_object.rotation_euler[:]
            new_object.rotation_euler = (r[0], r[1], r[2]+pi)
            new_object["PYNIFLY_IS_ROTATED"] = True

        mesh_create_uv(new_object.data, the_shape.uvs)
        mesh_create_bone_groups(the_shape, new_object, self.flags & self.ImportFlags.RENAME_BONES)
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
        f = the_shape.parent
        root = f.nodes[f.rootName]
        if root.blockname != "NiNode":
            new_object["pynRootNode_BlockType"] = root.blockname
        new_object["pynRootNode_Name"] = root.name
        new_object["pynRootNode_Flags"] = RootFlags(root.flags).fullname

        self.objects_created.extend(self.import_shape_extra(new_object, the_shape))


    def add_bone_to_arma(self, name):
        """ Add bone to armature. Bone may come from nif or reference skeleton.
            name = name to use for the bone in blender 
            returns new bone
        """
        armdata = self.armature.data

        if name in armdata.edit_bones:
            return None
    
        # use the transform in the file if there is one; otherwise get the 
        # transform from the reference skeleton
        xf = self.nif.get_node_xform_to_global(self.nif.nif_name(name)) 
        bone_xform = transform_to_matrix(xf)
        xft, xfr, xfs = bone_xform.decompose()

        bone = armdata.edit_bones.new(name)
        bone.head = xft
        if self.nif.game in ("SKYRIM", "SKYRIMSE"):
            rot_vec = Vector((0, 0, 5))
            # bone_xform.rotation.by_vector((0.0, 0.0, 5.0))
        else:
            rot_vec = Vector((5,0,0)) # bone_xform.rotation.by_vector((5.0, 0.0, 0.0))
        rot_vec.rotate(bone_xform)
        bone.tail = bone.head + rot_vec
        bone['pyxform'] = xfr # stash for later

        return bone


    def connect_armature(self):
        """ Connect up the bones in an armature to make a full skeleton.
            Use parent/child relationships in the nif if present, from the skel otherwise.
            Uses flags
                CREATE_BONES - add bones from skeleton as needed
                RENAME_BONES - rename bones to conform with blender conventions
            """
        arm_data = self.armature.data
        bones_to_parent = [b.name for b in arm_data.edit_bones]

        i = 0
        while i < len(bones_to_parent): # list will grow while iterating
            bonename = bones_to_parent[i]
            arma_bone = arm_data.edit_bones[bonename]

            if arma_bone.parent is None:
                parentname = None
                skelbone = None
                # look for a parent in the nif
                nifname = self.nif.nif_name(bonename)
                if nifname in self.nif.nodes:
                    niparent = self.nif.nodes[nifname].parent
                    if niparent and niparent._handle != self.nif.root:
                        if self.flags & self.ImportFlags.RENAME_BONES:
                            parentname = niparent.blender_name
                        else:
                            parentname = niparent.nif_name

                if parentname is None and (self.flags & self.ImportFlags.CREATE_BONES):
                    # No parent in the nif. If it's a known bone, get parent from skeleton
                    if self.flags & self.ImportFlags.RENAME_BONES:
                        if arma_bone.name in self.nif.dict.byBlender:
                            p = self.nif.dict.byBlender[bonename].parent
                            if p:
                                parentname = p.blender
                    else:
                        if arma_bone.name in self.nif.dict.byNif:
                            p = self.nif.dict.byNif[bonename].parent
                            if p:
                                parentname = p.nif
            
                # if we got a parent from somewhere, hook it up
                if parentname:
                    if parentname not in arm_data.edit_bones:
                        # Add parent bones and put on our list so we can get its parent
                        new_parent = self.add_bone_to_arma(parentname)
                        bones_to_parent.append(parentname)  
                        arma_bone.parent = new_parent
                    else:
                        arma_bone.parent = arm_data.edit_bones[parentname]
            i += 1
        

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
            if self.flags & self.ImportFlags.RENAME_BONES:
                name = self.nif.blender_name(bone_game_name)
            else:
                name = bone_game_name
            self.add_bone_to_arma(name)
        
        # Hook the armature bones up to a skeleton
        self.connect_armature()

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)


    def import_collision_shape(self, cs:CollisionShape, cb:bpy_types.Object):
        if cs.blockname != "bhkBoxShape":
            return None

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
        obj.name = cs.blockname
        obj.parent = cb
        bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
        # bpy.context.scene.collection.objects.link(obj)
        p = cs.properties
        obj['bhkMaterial'] = SkyrimHavokMaterial(p.bhkMaterial).name
        obj['bhkRadius'] = p.bhkRadius
        self.objects_created.append(obj)
        
        self.incr_loc

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

        #rm = RotationMatrix.from_quaternion(Quaternion(p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2])
        #transl = rm.by_vector(p.translation[0:3])
        # cbody.rotation_euler = mathutils.Euler((p.rotation[0], p.rotation[2], p.rotation[1]), 'XYZ')
        # The rotation in the nif is a quaternion with the angle in the 4th position, in radians
        log.debug(f"Found collision body with properties: {p}")
        cbody.rotation_mode = 'QUATERNION'
        log.debug(f"Rotating collision body around quaternion {(p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2])}")
        cbody.rotation_quaternion = (p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2], )
        cbody.location = Vector(p.translation[0:3]) * HAVOC_SCALE_FACTOR

        cs = cb.shape
        if cs:
            self.import_collision_shape(cs, cbody)

        #log.debug(f"Loaded collision body {cbody.name} with properties {list(cbody.keys())}")

    def import_collision_obj(self, c:CollisionObject):
        if c.blockname == "bhkCollisionObject":
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            col = bpy.context.object
            col.name = c.blockname
            col.show_name = True
            col['pynFlags'] = bhkCOFlags(c.flags).fullname
            col['pynTarget'] = c.target.name

            # targ = bpy.data.objects[c.target.name]
            col.matrix_world = get_node_location(c.target)
            # col.location = xform.translation.tuple

            cb = c.body
            if cb:
                self.import_collision_body(cb, col)

    def import_collisions(self):
        """ Walk through the nif looking for collision objects and import them """
        log.debug("Import collisions")
        for k, n in self.nif.nodes.items():
            c = n.collision_object
            if c:
                self.import_collision_obj(c)

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

        for obj in self.objects_created:
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
                for o in self.objects_created: 
                    if o.type == 'MESH': 
                        o.select_set(True)
                bpy.ops.object.parent_set(type='ARMATURE_NAME', xmirror=False, keep_transform=False)
            else:
                self.armature.select_set(True)
    
        # Import nif-level extra data
        objs = self.import_extra(self.nif)
        
        # Import collisions
        self.import_collisions()

        for o in self.objects_created: o.select_set(True)
        if len(self.objects_created) > 0:
            bpy.context.view_layer.objects.active = self.objects_created[0]


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

    #rotate_model: bpy.props.BoolProperty(
    #    name="Rotate Model",
    #    description="Rotate model to face forward in blender",
    #    default=True)


    def execute(self, context):
        log.info("\n\n====================================\nNIFLY IMPORT V%d.%d.%d" % bl_info['version'])
        status = {'FINISHED'}

        flags = NifImporter.ImportFlags(0)
        if self.create_bones:
            flags |= NifImporter.ImportFlags.CREATE_BONES
        if self.rename_bones:
            flags |= NifImporter.ImportFlags.RENAME_BONES
        #if self.rotate_model:
        #    flags |= NifImporter.ImportFlags.ROTATE_MODEL

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
            #log.debug(f"Morph {morph_name} in tri file should have same number of verts as Blender shape: {len(mesh_key_verts)} != {len(morph_verts)}")
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

        if tri.import_uv:
            mesh_create_uv(new_mesh, tri.uv_pos)
   
        new_collection = bpy.data.collections.new(os.path.basename(os.path.basename(filepath) + ".Coll"))
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.objects.link(new_object)
        bpy.context.view_layer.objects.active = new_object
        new_object.select_set(True)

    create_shape_keys(new_object, tri)

    return new_object


def export_tris(nif, trip, obj, verts, tris, uvs, morphdict):
    """ Export a tri file to go along with the given nif file, if there are shape keys 
        and it's not a faceBones nif.
        dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
    """
    result = {'FINISHED'}

    if obj.data.shape_keys is None:
        return result

    fpath = os.path.split(nif.filepath)
    fname = os.path.splitext(fpath[1])

    if fname[0].endswith('_faceBones'):
        return result

    fname_tri = os.path.join(fpath[0], fname[0] + ".tri")
    fname_chargen = os.path.join(fpath[0], fname[0] + "_chargen.tri")

    # Don't export anything that starts with an underscore or asterisk
    objkeys = obj.data.shape_keys.key_blocks.keys()
    export_keys = set(filter((lambda n: n[0] not in ('_', '*') and n != 'Basis'), objkeys))
    expression_morphs = nif.dict.expression_filter(export_keys)
    trip_morphs = set(filter((lambda n: n[0] == '>'), objkeys))
    # Leftovers are chargen candidates
    leftover_morphs = export_keys.difference(expression_morphs).difference(trip_morphs)
    chargen_morphs = nif.dict.chargen_filter(leftover_morphs)

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
            if m in nif.dict.morph_dic_game:
                triname = nif.dict.morph_dic_game[m]
            else:
                triname = m
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
            tri.morphs[m] = morphdict[m]
    
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


def extract_face_info(mesh, uvlayer, use_loop_normals=False):
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

    # Calculating normals messes up the passed-in UV, so get the data out of it first
    for f in mesh.polygons:
        for i in f.loop_indices:
            uvs.append(uvlayer[i].uv[:])
            #log.debug(f"....Adding uv index {uvlayer[i].uv[:]}")

    # CANNOT figure out how to get the loop normals correctly.  They seem to follow the
    # face normals even on smooth shading.  (TEST_NORMAL_SEAM tests for this.) So use the
    # vertex normal except when there are custom split normals.
    bpy.ops.object.mode_set(mode='OBJECT') #required to get accurate normals
    mesh.calc_normals()
    mesh.calc_normals_split()

    for f in mesh.polygons:
        for i in f.loop_indices:
            loopseg = mesh.loops[i]
            loops.append(loopseg.vertex_index)
            if use_loop_normals:
                norms.append(loopseg.normal[:])
            else:
                norms.append(mesh.vertices[loopseg.vertex_index].normal[:])

    return loops, uvs, norms


def extract_vert_info(obj, mesh, target_key=''):
    """Returns 3 lists of equal length with one entry each for each vertex
        verts = [(x, y, z)... ] - base or as modified by target-key if provided
        weights = [{group-name: weight}... ] - 1:1 with verts list
        dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
            if "target_key" is specified this will be empty
            shape key is the blender name
        """
    weights = []
    morphdict = {}

    if target_key != '' and mesh.shape_keys and target_key in mesh.shape_keys.key_blocks.keys():
        log.debug(f"....exporting shape {target_key} only")
        verts = [v.co[:] for v in mesh.shape_keys.key_blocks[target_key].data]
    else:
        verts = [v.co[:] for v in mesh.vertices]

    for v in mesh.vertices:
        vert_weights = {}
        for vg in v.groups:
            try:
                vert_weights[obj.vertex_groups[vg.group].name] = vg.weight
            except:
                log.error(f"ERROR: Vertex #{v.index} references invalid group #{vg.group}")
        weights.append(vert_weights)
    
    if target_key == '' and mesh.shape_keys:
        for sk in mesh.shape_keys.key_blocks:
            morphdict[sk.name] = [v.co[:] for v in sk.data]

    #log.debug(f"....Vertex 18 at {[round(v,2) for v in verts[18]]}")
    return verts, weights, morphdict


def get_bone_xforms(arma, bone_names, shape):
    """Return transforms for the bones in list, getting rotation from what we stashed on import
        arma = data block of armature
        bone_names = list of names
        shape = shape being exported
        result = dict{bone-name: MatTransform, ...}
    """
    result = {}
    for b in arma.bones:
        loc = Vector(b.head_local)
        try:
            # Todo: Calc from relative head->tail locations)
            rot = Quaternion(b['pyxform'])
        except:
            nif = shape.parent
            bone_xform = nif.get_node_xform_to_global(nif.nif_name(b.name)) 
            rot = Matrix([bone_xform.rotation[0][:], 
                          bone_xform.rotation[1][:], 
                          bone_xform.rotation[2][:]])
        
        result[b.name] = Matrix.LocRotScale(loc, rot, [1,1,1])
    
    return result

def export_skin(obj, arma, new_shape, new_xform, weights_by_vert):
    log.info("..Parent is armature, skin the mesh")
    new_shape.skin()
    # if new_shape.has_skin_instance: 
    # just use set_global_to_skin -- it does the check (maybe)
    #if nif.game in ("SKYRIM", "SKYRIMSE"):
    #    new_shape.set_global_to_skindata(new_xform.invert())
    #else:
    #    new_shape.set_global_to_skin(new_xform.invert())
    new_shape.transform = TransformBuf.from_matrix(new_xform)
    newxfi = new_xform.copy()
    newxfi.invert()
    new_shape.set_global_to_skin(TransformBuf.from_matrix(newxfi))
    
    group_names = [g.name for g in obj.vertex_groups]
    weights_by_bone = get_weights_by_bone(weights_by_vert)
    used_bones = weights_by_bone.keys()
    arma_bones = get_bone_xforms(arma.data, used_bones, new_shape)
    
    for bone_name, bone_xform in arma_bones.items():
        # print(f"  shape {obj.name} adding bone {bone_name}")
        if bone_name in weights_by_bone and len(weights_by_bone[bone_name]) > 0:
            # print(f"..Shape {obj.name} exporting bone {bone_name} with rotation {bone_xform.rotation.euler_deg()}")
            nifname = new_shape.parent.nif_name(bone_name)
            new_shape.add_bone(nifname, TransformBuf.from_matrix(bone_xform))
            log.debug(f"....Adding bone {nifname}")
                #nif.nodes[bone_name].xform_to_global)
            new_shape.setShapeWeights(nifname, weights_by_bone[bone_name])


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
        #print(f"Checking against game {g} match is {n}")
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
                    log.debug(f"Found FO4Segment '{vg.name}'")
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
                        log.debug(f"Found FO4Subsegment '{vg.name}' child of '{parent_name}'")
                        val[vg.name] = FO4Subsegment(len(val), subseg_id, material, p, name=vg.name)
    
    return val


def all_vertex_groups(weightdict):
    """ Return the set of group names that have non-zero weights """
    val = set()
    for g, w in weightdict.items():
        if w > 0.0001:
            val.add(g)
    return val


def mesh_from_key(editmesh, verts, target_key):
    faces = []
    for p in editmesh.polygons:
        faces.append([editmesh.loops[lpi].vertex_index for lpi in p.loop_indices])
    log.debug(f"....Remaking mesh with shape {target_key}: {len(verts)} verts, {len(faces)} faces")
    newverts = [v.co[:] for v in editmesh.shape_keys.key_blocks[target_key].data]
    newmesh = bpy.data.meshes.new(editmesh.name)
    newmesh.from_pydata(newverts, [], faces)
    return newmesh


def export_shape_to(shape, filepath, game):
    outnif = NifFile()
    outtrip = TripFile()
    rt = "NiNode"
    rn = "Scene Root"
    if "pynRootNode_BlockType" in shape:
        rt = shape["pynRootNode_BlockType"]
    if "pynRootNode_Name" in shape:
        rn = shape["pynRootNode_Name"]
    outnif.initialize(game, filepath, rt, rn)
    if "pynRootNode_Flags" in shape:
        outf.root.flags = shape["pynRootNode_Flags"]
    ret = export_shape(outnif, outtrip, shape, '', shape.parent) 
    outnif.save()
    log.info(f"Wrote {filepath}")
    return ret


def get_common_shapes(obj_list):
    """ Return the shape keys found in any of the given objects """
    res = None
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
    def __init__(self, filepath, game, rotate=False):
        self.filepath = filepath
        self.game = game
        self.warnings = set()
        self.armature = None
        self.facebones = None
        self.objects = set()
        self.bg_data = set()
        self.str_data = set()
        self.cloth_data = set()
        self.bsx_flag = None
        self.inv_marker = None
        self.collisions = set()
        # Shape keys that start with underscore trigger
        # a separate file export for each shape key
        self.file_keys = []
        self.objs_unweighted = set()
        self.objs_scale = set()
        self.objs_mult_part = set()
        self.objs_no_part = set()
        self.arma_game = []
        self.bodytri_written = False
        self.message_log = []
        #self.rotate_model = rotate


    def export_shape_data(self, obj, shape):
        ed = [ (x['NiStringExtraData_Name'], x['NiStringExtraData_Value']) for x in \
                obj.children if 'NiStringExtraData_Name' in x.keys()]
        if len(ed) > 0:
            shape.string_data = ed
    
        ed = [ (x['BSBehaviorGraphExtraData_Name'], x['BSBehaviorGraphExtraData_Value']) \
                for x in obj.children if 'BSBehaviorGraphExtraData_Name' in x.keys()]
        if len(ed) > 0:
            shape.behavior_graph_data = ed


    def add_object(self, obj):
        """ Adds the given object to the objects to export """
        if obj.type == 'ARMATURE':
            facebones_obj = (self.game == 'FO4') and (is_facebones(obj))
            if facebones_obj and self.facebones is None:
                self.facebones = obj
            if (not facebones_obj) and (self.armature is None):
                self.armature = obj 

        elif obj.type == 'MESH':
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

            elif 'pynTarget' in obj.keys():
                self.collisions.add(obj)

        # remove extra data nodes with objects in the export list as parents so they 
        # don't get exported twice
        for n in self.bg_data:
            if n.parent and n.parent in self.objects:
                self.bg_data.remove(n)
        for n in self.str_data:
            if n.parent and n.parent in self.objects:
                self.str_data.remove(n)
        for n in self.cloth_data:
            if n.parent and n.parent in self.objects:
                self.cloth_data.remove(n)

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

    def export_extra_data(self, nif: NifFile):
        """ Export any extra data represented as Blender objects. 
            Sets self.bodytri_done if one of the extra data nodes represents a bodytri
        """
        exdatalist = [ (x['NiStringExtraData_Name'], x['NiStringExtraData_Value']) 
                        for x in self.str_data]
        if len(exdatalist) > 0:
            nif.string_data = exdatalist

        self.bodytri_written = ('BODYTRI' in [x[0] for x in exdatalist])

        bglist = [ (x['BSBehaviorGraphExtraData_Name'], x['BSBehaviorGraphExtraData_Value']) \
                for x in self.bg_data]
        if len(bglist) > 0:
            nif.behavior_graph_data = bglist 

        cdlist = [ 
            (x['BSClothExtraData_Name'], codecs.decode(x['BSClothExtraData_Value'], "base64")) for x in self.cloth_data]
        if len(cdlist) > 0:
            nif.cloth_data = cdlist 

        if self.bsx_flag:
            log.debug(f"Exporting BSXFlags node")
            nif.bsx_flags = [self.bsx_flag['BSXFlags_Name'],
                             BSXFlags.parse(self.bsx_flag['BSXFlags_Value'])]

        if self.inv_marker:
            log.debug(f"Exporting BSInvMarker node")
            nif.inventory_marker = [self.inv_marker['BSInvMarker_Name'], 
                                    self.inv_marker['BSInvMarker_RotX'], 
                                    self.inv_marker['BSInvMarker_RotY'], 
                                    self.inv_marker['BSInvMarker_RotZ'], 
                                    self.inv_marker['BSInvMarker_Zoom']]


    def export_collision_shape(self, nif:NifFile, shape_list):
        """ Export box shape. Returns (shape, coordinates)
            shape = collision shape in the nif object
            coordinates = center of the shape in Blender world coordinates) """ 
        cshape = None
        center = Vector()
        for s in shape_list:
            try:
                # Box covers the extent of the shape, whatever it is
                p = bhkBoxShapeProps(s)
                xf = s.matrix_world
                xfv = [xf @ v.co for v in s.data.vertices]
                maxx = max([v[0] for v in xfv])
                maxy = max([v[1] for v in xfv])
                maxz = max([v[2] for v in xfv])
                minx = min([v[0] for v in xfv])
                miny = min([v[1] for v in xfv])
                minz = min([v[2] for v in xfv])
                halfspanx = (maxx - minx)/2
                halfspany = (maxy - miny)/2
                halfspanz = (maxz - minz)/2
                center = Vector([minx + halfspanx, miny + halfspany, minz + halfspanz])
                
                p.bhkDimensions[0] = halfspanx / HAVOC_SCALE_FACTOR
                p.bhkDimensions[1] = halfspany / HAVOC_SCALE_FACTOR
                p.bhkDimensions[2] = halfspanz / HAVOC_SCALE_FACTOR
                if 'radius' not in s.keys():
                    p.bhkRadius = max(halfspanx, halfspany, halfspanz) / HAVOC_SCALE_FACTOR
                cshape = nif.add_coll_shape("bhkBoxShape", p)
                log.debug(f"Created collision shape with dimensions {p.bhkDimensions[:]}")
            except:
                log.exception(f"Cannot create collision shape from {s.name}")
                self.warnings.add('WARNING')

        return cshape, center

    def get_collision_target(self, collisionobj) -> Matrix:
        """ Return the world transform matrix for the collision target """
        # TODO: Should really do this off the target object, not the collision object.
        # Collision object is fine after an import because it matches, but user needs to
        # be able to create a new one
        xf = collisionobj.matrix_world
        log.debug(f"Collision target: {xf}")
        return xf

    def export_collision_body(self, nif:NifFile, body_list, coll):
        """ Export the collision body elements. coll is the parent collision object """
        body = None
        for b in body_list:
            cshape, ctr = self.export_collision_shape(nif, b.children)
            log.debug(f"Collision Center: {ctr}")

            if cshape:
                # Coll body can be anywhere. What matters is the location of the collision 
                # shape relative to the collision target--that gets stored on the 
                # collision body
                targxf = self.get_collision_target(coll)
                targloc, targq, targscale = targxf.decompose()
            
                props = bhkRigidBodyProps(b)
                targq.invert()
                props.rotation[0] = targq.x
                props.rotation[1] = targq.y
                props.rotation[2] = targq.z
                props.rotation[3] = targq.w
                log.debug(f"Target rotation: {targq.w}, {targq.x}, {targq.y}, {targq.z}")

                rv = ctr - targloc
                rv.rotate(targq)
                log.debug(f"Body to center: {ctr - targloc}")
                log.debug(f"Body to center rotated: {rv}")
                # rv = bodq.invert().rotate(rv)

                props.translation[0] = (rv.x) / HAVOC_SCALE_FACTOR
                props.translation[1] = (rv.y) / HAVOC_SCALE_FACTOR
                props.translation[2] = (rv.z) / HAVOC_SCALE_FACTOR
                props.translation[3] = 0
                log.debug(f"In havoc units: {rv / HAVOC_SCALE_FACTOR}")

                log.debug(f"Writing collision body with translation: {props.translation[:]} and rotation {props.rotation[:]}")
                body = nif.add_rigid_body("bhkRigidBodyT", props, cshape)
        return body

    def export_collisions(self, nif:NifFile):
        """ Export collisions. Apply the skin first so bones are available. """
        nif.apply_skin()

        for coll in self.collisions:
            body = self.export_collision_body(nif, coll.children, coll)
            if body:
                tn = coll['pynTarget']
                try:
                    targ = nif.nodes[tn]
                    nif.add_collision(targ, targ, body, bhkCOFlags.parse(coll['pynFlags']).value)
                except:
                    log.warning(f"Collision references object not included in export: {coll.name} -> {tn}")
                    self.warnings.add('WARNING')


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
        log.debug(f"....Found partitions {list(partitions.keys())}")

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

        log.debug(f"Partitions for export: {partitions.keys()}, {tri_indices[0:20]}")
        return list(partitions.values()), tri_indices

    def extract_colors(self, mesh):
        """Extract vertex color data from the given mesh. Use the VERTEX_ALPHA color map
            for alpha values if it exists."""
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
        #loopcolors = [c.color[:] for c in editmesh.vertex_colors.active.data]

    def extract_mesh_data(self, obj, target_key):
        """ 
        Extract the mesh data from the given object
            obj = object being exported
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
        originalmesh = obj.data
        editmesh = originalmesh.copy()
        saved_sk = obj.active_shape_key_index
        obj.data = editmesh
        loopcolors = None
        
        original_rot = obj.rotation_euler[:]
        #if self.rotate_model:
        #    obj.rotation_euler = (original_rot[0], original_rot[1], original_rot[2]+pi)

        try:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        
            # If scales aren't uniform, apply them before export
            if (round(obj.scale[0], 4) != round(obj.scale[1], 4)) \
                    or (round(obj.scale[0], 4) != round(obj.scale[2], 4)):
                log.warning(f"Object {obj.name} scale not uniform, applying before export") 
                self.objs_scale.add('SCALE')
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
            # This next little dance ensures the mesh.vertices locations are correct
            obj.active_shape_key_index = 0
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.object.mode_set(mode = 'OBJECT')
            #log.debug(f"....Vertex 12 position: {mesh.vertices[12].co}")
        
            # Can't get custom normals out of a bmesh (known limitation). Can't triangulate
            # a regular mesh except through the operator. 
            log.info("..Triangulating mesh")
            select_all_faces(editmesh)
            bpy.ops.object.mode_set(mode = 'EDIT') # Required to convert to tris
            bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
        
            for p in editmesh.polygons:
                p.use_smooth = True
        
            editmesh.update()
         
            verts, weights_by_vert, morphdict = extract_vert_info(obj, editmesh, target_key)
        
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
        
            loops, uvs, norms = extract_face_info(editmesh, uvlayer, use_loop_normals=editmesh.has_custom_normals)
        
            log.info("..Splitting mesh along UV seams")
            mesh_split_by_uv(verts, norms, loops, uvs, weights_by_vert, morphdict)
            # Old UV map had dups where verts were split; new matches 1-1 with verts
            uvmap_new = [(0.0, 0.0)] * len(verts)
            norms_new = [(0.0, 0.0, 0.0)] * len(verts)
            for i, lp in enumerate(loops):
                assert lp < len(verts), f"Error: Invalid vert index in loops: {lp} >= {len(verts)}"
                uvmap_new[lp] = uvs[i]
                norms_new[lp] = norms[i]
            #uvmap_new = [uvs[loops.index(i)] for i in range(len(verts))]
            #norms_new = [norms[loops.index(i)] for i in range(len(verts))]
        
            # Our "loops" list matches 1:1 with the mesh's loops. So we can use the polygons
            # to pull the loops
            tris = []
            for p in editmesh.polygons:
                tris.append((loops[p.loop_start], loops[p.loop_start+1], loops[p.loop_start+2]))
        
            #tris = [(loops[i], loops[i+1], loops[i+2]) for i in range(0, len(loops), 3)]
            colors_new = None
            if loopcolors:
                log.debug(f"..Exporting vertex colors for shape {obj.name}")
                colors_new = [(0.0, 0.0, 0.0, 0.0)] * len(verts)
                for i, lp in enumerate(loops):
                    colors_new[lp] = loopcolors[i]
            else:
                log.debug(f"..No vertex colors in shape {obj.name}")
        
        finally:
            obj.rotation_euler = original_rot
            obj.data = originalmesh
            obj.active_shape_key_index = saved_sk

        return verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, morphdict

    def export_shape(self, nif, trip, obj, target_key='', arma=None):
        """Export given blender object to the given NIF file
            nif = target nif file
            trip = target file for BS Tri shapes
            obj = blender object
            target_key = shape key to export
            arma = armature to skin to
            """
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
            if not expected_game(nif, arma.data.bones):
                log.warning(f"Exporting to game that doesn't match armature: game={nif.game}, armature={arma.name}")
                retval.add('GAME')

        verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, morphdict = \
           self.extract_mesh_data(obj, target_key)

        is_headpart = obj.data.shape_keys \
                and len(nif.dict.expression_filter(set(obj.data.shape_keys.key_blocks.keys()))) > 0
        if is_headpart:
            log.debug(f"...shape is headpart, shape keys = {nif.dict.expression_filter(set(obj.data.shape_keys.key_blocks.keys()))}")

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

        log.debug(f"..Exporting to nif: {len(verts)} vertices, {len(tris)} tris")
        new_shape = nif.createShapeFromData(obj.name, verts, tris, uvmap_new, norms_exp, 
                                            is_headpart, is_skinned, is_effectshader)
        if colors_new:
            new_shape.set_colors(colors_new)

        self.export_shape_data(obj, new_shape)
        
        if mat:
            export_shader(obj, new_shape)
            log.debug(f"....'{new_shape.name}' has textures: {new_shape.textures}")
            if has_msn:
                new_shape.shader_attributes.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
            else:
                new_shape.shader_attributes.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)
            if colors_new:
                new_shape.shader_attributes.shaderflags2_set(ShaderFlags2.VERTEX_COLORS)
            else:
                new_shape.shader_attributes.shaderflags2_clear(ShaderFlags2.VERTEX_COLORS)
            new_shape.save_shader_attributes()
        else:
            log.debug(f"..No material on {obj.name}")

        if is_skinned:
            nif.createSkin()

        #new_xform = MatTransform();
        #new_xform.translation = Vector(obj.location)
        ##new_xform.rotation = RotationMatrix((obj.matrix_local[0][0:3], 
        ##                                     obj.matrix_local[1][0:3], 
        ##                                     obj.matrix_local[2][0:3]))
        #new_xform.rotation = RotationMatrix.from_euler_rad(*obj.rotation_euler[:])
        #new_xform.scale = obj.scale[0]
        new_xform = obj.matrix_world.copy()
        
        if is_skinned:
            export_skin(obj, arma, new_shape, new_xform, weights_by_vert)
            if len(unweighted) > 0:
                create_group_from_verts(obj, UNWEIGHTED_VERTEX_GROUP, unweighted)
                log.warning("Some vertices are not weighted to the armature in object {obj.name}")
                self.objs_unweighted.add(obj)

            partitions, tri_indices = self.export_partitions(obj, weights_by_vert, tris)
            if len(partitions) > 0:
                if 'FO4_SEGMENT_FILE' in obj.keys():
                    log.debug(f"....Writing segment file {obj['FO4_SEGMENT_FILE']}")
                    new_shape.segment_file = obj['FO4_SEGMENT_FILE']
                new_shape.set_partitions(partitions, tri_indices)
        else:
            log.debug(f"...Exporting {new_shape.name} with transform {new_xform}")
            new_shape.transform = TransformBuf.from_matrix(new_xform)

        retval |= export_tris(nif, trip, obj, verts, tris, uvmap_new, morphdict)

        log.info(f"..{obj.name} successfully exported to {nif.filepath}")
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

            log.info(f"..Exporting to {self.game} {fpath}")
            exportf = NifFile()

            rt = "NiNode"
            rn = "Scene Root"

            shape = next(iter(self.objects))
            if "pynRootNode_BlockType" in shape:
                rt = shape["pynRootNode_BlockType"]
            if "pynRootNode_Name" in shape:
                rn = shape["pynRootNode_Name"]
            
            exportf.initialize(self.game, fpath, rt, rn)
            if "pynRootNode_Flags" in shape:
                log.debug(f"Root node flags are '{shape['pynRootNode_Flags']}' = '{RootFlags.parse(shape['pynRootNode_Flags']).value}'")
                exportf.rootNode.flags = RootFlags.parse(shape["pynRootNode_Flags"]).value

            if suffix == '_faceBones':
                exportf.dict = fo4FaceDict


            trip = TripFile()
            trippath = os.path.join(os.path.dirname(self.filepath), fbasename) + ".tri"

            for obj in self.objects:
                self.export_shape(exportf, trip, obj, sk, arma)
                log.debug(f"Exported shape {obj.name}")

            # Check for bodytri morphs--write the extra data node if needed
            if len(trip.shapes) > 0 and not self.bodytri_written:
                exportf.string_data = [('BODYTRI', truncate_filename(trippath, "meshes"))]

            self.export_collisions(exportf)
            self.export_extra_data(exportf)

            exportf.save()
            log.info(f"..Wrote {fpath}")
            self.message_log.append(exportf.message_log())

            if len(trip.shapes) > 0:
                trip.write(trippath)
                log.info(f"..Wrote {trippath}")


    def execute(self):
        if not self.objects:
            log.warning(f"No objects selected for export")
            self.warnings.add('NOTHING')
            return

        log.debug(f"..Exporting objects: {self.objects}\nstring data: {self.str_data}\nBG data: {self.bg_data}\ncloth data: {self.cloth_data}\narmature: armature: {self.armature},\nfacebones: {self.facebones}")
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

    #rotate_model: bpy.props.BoolProperty(
    #    name="Rotate Model",
    #    description="Rotate model from blender-forward to nif-forward",
    #    default=True)


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
        if arma:
            g = best_game_fit(arma.data.bones)
            if g != "":
                self.target_game = g
        
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

        log.info("\n\n==============================\nNIFLY EXPORT V%d.%d.%d\n==============================" % bl_info['version'])
        NifFile.Load(nifly_path)

        try:
            exporter = NifExporter(self.filepath, self.target_game) # , rotate=self.rotate_model)
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
                self.report({'WARNING'}, f"The armature appears to be designed for a different game--check that it's correct\nArmature: {exporter.arma_game}, game: {exportf.game}")
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

    if TEST_BPY_ALL:
        run_tests(pynifly_dev_path, NifExporter, NifImporter, import_tri)


    # Tests in this file are for functionality under development. They should be moved to
    # pynifly_tests.py when stable.



    if True:
        test_title("TEST_BOW", "Can read and write bow")
        # Primarily tests collisions, but also tests fade node, extra data nodes, 
        # UV orientation, and texture handling
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BOW.nif")

        NifImporter.do_import(testfile)

        # Check root info
        obj = bpy.context.object
        assert obj["pynRootNode_BlockType"] == 'BSFadeNode', "pynRootNode_BlockType holds the type of root node for the given shape"
        assert obj["pynRootNode_Name"] == "GlassBowSkinned.nif", "pynRootNode_Name holds the name for the root node"
        assert obj["pynRootNode_Flags"] == "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR", f"'pynRootNode_Flags' holds the flags on the root node: {obj['pynRootNode_Flags']}"

        # Check collision info
        coll = find_shape('bhkCollisionObject')
        assert coll['pynFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
        assert coll['pynTarget'] == 'Bow_MidBone', f"'Target' names the object the collision affects, in this case a bone: {coll['pynTarget']}"

        collbody = coll.children[0]
        assert collbody.name == 'bhkRigidBodyT', f"Child of collision is the collision body object"
        assert collbody['collisionFilter_layer'] == SkyrimCollisionLayer.WEAPON.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
        assert collbody["collisionResponse"] == hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"
        assert VNearEqual(collbody.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), f"Collision body rotation correct: {collbody.rotation_quaternion}"

        collshape = collbody.children[0]
        assert collshape.name == 'bhkBoxShape', f"Collision shape is child of the collision body"
        assert collshape['bhkMaterial'] == 'MATERIAL_BOWS_STAVES', f"Shape material is a custom property: {collshape['bhkMaterial']}"
        assert round(collshape['bhkRadius'],4) == 0.0136, f"Radius property available as custom property: {collshape['bhkRadius']}"
        corner = map(abs, collshape.data.vertices[0].co)
        assert VNearEqual(corner, [11.01445, 57.6582, 0.95413]), f"Collision shape in correct position: {corner}"

        bged = find_shape("BSBehaviorGraphExtraData")
        assert bged['BSBehaviorGraphExtraData_Value'] == "Weapons\Bow\BowProject.hkx", f"BGED node contains bow project: {bged['BSBehaviorGraphExtraData_Value']}"

        strd = find_shape("NiStringExtraData")
        assert strd['NiStringExtraData_Value'] == "WeaponBow", f"Str ED node contains bow value: {strd['NiStringExtraData_Value']}"

        bsxf = find_shape("BSXFlags")
        assert bsxf['BSXFlags_Name'] == "BSX", f"BSX Flags contain name BSX: {bsxf['BSXFlags_Name']}"
        assert bsxf['BSXFlags_Value'] == "HAVOC | COMPLEX | DYNAMIC | ARTICULATED", "BSX Flags object contains correct flags: {bsxf['BSXFlags_Value']}"

        invm = find_shape("BSInvMarker")
        assert invm['BSInvMarker_Name'] == "INV", f"Inventory marker shape has correct name: {invm['BSInvMarker_Name']}"
        assert invm['BSInvMarker_RotX'] == 4712, f"Inventory marker rotation correct: {invm['BSInvMarker_RotX']}"
        assert round(invm['BSInvMarker_Zoom'], 4) == 1.1273, f"Inventory marker zoom correct: {invm['BSInvMarker_Zoom']}"
       
        # ------- Export --------

        # Move the edge of the collision box so it covers the bow better
        for v in collshape.data.vertices:
            if v.co.x > 0:
                v.co.x = 16.5

        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([obj, coll, bged, strd, bsxf, invm])

        # ------- Check Results --------

        nifcheck = NifFile(outfile)
        rootcheck = nifcheck.rootNode
        assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
        assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
        assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

        bsxcheck = nifcheck.bsx_flags
        assert bsxcheck == ["BSX", 202], f"BSX Flag node found: {bsxcheck}"

        bsinvcheck = nifcheck.inventory_marker
        assert bsinvcheck[0:4] == ["INV", 4712, 0, 785], f"Inventory marker set: {bsinvcheck}"
        assert round(bsinvcheck[4], 4) == 1.1273, f"Inventory marker zoom set: {bsinvcheck[4]}"

        midbowcheck = nifcheck.nodes["Bow_MidBone"]
        collcheck = midbowcheck.collision_object
        assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
        assert bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

        # Full check of locations and rotations to make sure we got them right
        mbc_xf = nifcheck.get_node_xform_to_global("Bow_MidBone")
        assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
        m = mbc_xf.as_matrix().to_euler()
        assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

        bodycheck = collcheck.body
        p = bodycheck.properties
        assert VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
        assert VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


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
