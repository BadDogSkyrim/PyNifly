"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

RUN_TESTS = True
TEST_BPY_ALL = False


bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (2, 92, 0),
    "version": (0, 0, 51),  
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

NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"

GLOSS_SCALE = 100

#log.setLevel(logging.DEBUG)
#pynifly_ch = logging.StreamHandler()
#pynifly_ch.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(name)s-%(levelname)s: %(message)s')
#pynifly_ch.setFormatter(formatter)
#log.addHandler(ch)


# ######################################################################## ###
#                                                                          ###
# -------------------------------- IMPORT -------------------------------- ###
#                                                                          ###
# ######################################################################## ###

# -----------------------------  EXTRA DATA  -------------------------------

def import_extra(f: NifFile):
    """ Import any extra data from the root, and create corresponding shapes """
    loc = [0.0, 0.0, 0.0]

    for s in f.string_data:
        bpy.ops.object.add(radius=1.0, type='EMPTY', location=loc)
        ed = bpy.context.object
        ed.name = "NiStringExtraData"
        ed.show_name = True
        ed['NiStringExtraData_Name'] = s[0]
        ed['NiStringExtraData_Value'] = s[1]
        loc[0] += 3.0

    for s in f.behavior_graph_data:
        bpy.ops.object.add(radius=1.0, type='EMPTY', location=loc)
        ed = bpy.context.object
        ed.name = "BSBehaviorGraphExtraData"
        ed.show_name = True
        ed['BSBehaviorGraphExtraData_Name'] = s[0]
        ed['BSBehaviorGraphExtraData_Value'] = s[1]
        loc[0] += 3.0

def import_shape_extra(obj, shape):
    """ Import any extra data from the shape if given or the root if not, and create 
    corresponding shapes """
    loc = obj.location

    for s in shape.string_data:
        bpy.ops.object.add(radius=1.0, type='EMPTY', location=loc)
        ed = bpy.context.object
        ed.name = "NiStringExtraData"
        ed.show_name = True
        ed['NiStringExtraData_Name'] = s[0]
        ed['NiStringExtraData_Value'] = s[1]
        ed.parent = obj
        loc[0] += 3.0

    for s in shape.behavior_graph_data:
        bpy.ops.object.add(radius=1.0, type='EMPTY', location=loc)
        ed = bpy.context.object
        ed.name = "BSBehaviorGraphExtraData"
        ed.show_name = True
        ed['BSBehaviorGraphExtraData_Name'] = s[0]
        ed['BSBehaviorGraphExtraData_Value'] = s[1]
        ed.parent = obj
        loc[0] += 3.0

def export_shape_data(obj, shape):
    ed = [ (x['NiStringExtraData_Name'], x['NiStringExtraData_Value']) for x in \
            obj.children if 'NiStringExtraData_Name' in x.keys()]
    if len(ed) > 0:
        shape.string_data = ed
    
    ed = [ (x['BSBehaviorGraphExtraData_Name'], x['BSBehaviorGraphExtraData_Value']) for x in \
            obj.children if 'BSBehaviorGraphExtraData_Name' in x.keys()]
    if len(ed) > 0:
        shape.behavior_graph_data = ed


# -----------------------------  SHADERS  -------------------------------


def import_shader_attrs(material, shader, shape):
    attrs = shape.shader_attributes

    material['BSLSP_Shader_Type'] = attrs.Shader_Type
    material['BSLSP_Shader_Name'] = shape.shader_name
    material['BSLSP_Shader_Flags_1'] = hex(attrs.Shader_Flags_1)
    material['BSLSP_Shader_Flags_2'] = hex(attrs.Shader_Flags_2)
    shader.inputs['Emission'].default_value = (attrs.Emissive_Color_R, attrs.Emissive_Color_G, attrs.Emissive_Color_B, attrs.Emissive_Color_A)
    shader.inputs['Emission Strength'].default_value = attrs.Emissive_Mult
    shader.inputs['Alpha'].default_value = attrs.Alpha
    material['BSLSP_Refraction_Str'] = attrs.Refraction_Str
    shader.inputs['Metallic'].default_value = attrs.Glossiness/GLOSS_SCALE
    material['BSLSP_Spec_Color_R'] = attrs.Spec_Color_R
    material['BSLSP_Spec_Color_G'] = attrs.Spec_Color_G
    material['BSLSP_Spec_Color_B'] = attrs.Spec_Color_B
    material['BSLSP_Spec_Str'] = attrs.Spec_Str
    material['BSLSP_Soft_Lighting'] = attrs.Soft_Lighting
    material['BSLSP_Rim_Light_Power'] = attrs.Rim_Light_Power
    material['BSLSP_Skin_Tint_Color_R'] = attrs.Skin_Tint_Color_R
    material['BSLSP_Skin_Tint_Color_G'] = attrs.Skin_Tint_Color_G
    material['BSLSP_Skin_Tint_Color_B'] = attrs.Skin_Tint_Color_B

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
    img_offset_x = -1000
    cvt_offset_x = -300
    inter1_offset_x = -700
    inter2_offset_x = -500
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


    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bdsf = nodes.get("Principled BSDF")

    import_shader_attrs(mat, bdsf, shape)
    has_alpha = import_shader_alpha(mat, shape)

    # --- Diffuse --

    txtnode = nodes.new("ShaderNodeTexImage")
    try:
        img = bpy.data.images.load(fulltextures[0], check_existing=True)
        txtnode.image = img
    except:
        pass
    txtnode.location = (bdsf.location[0] + img_offset_x, bdsf.location[1])
    
    mat.node_tree.links.new(txtnode.outputs['Color'], bdsf.inputs['Base Color'])
    if has_alpha:
        mat.node_tree.links.new(txtnode.outputs['Alpha'], bdsf.inputs['Alpha'])

    yloc = txtnode.location[1] + offset_y

    # --- Subsurface --- 

    if fulltextures[2] != "": 
        # Have a sk separate from a specular
        skimgnode = nodes.new("ShaderNodeTexImage")
        try:
            skimg = bpy.data.images.load(fulltextures[2], check_existing=True)
            skimg.colorspace_settings.name = "Non-Color"
            skimgnode.image = skimg
        except:
            pass
        skimgnode.location = (txtnode.location[0], yloc)
        mat.node_tree.links.new(skimgnode.outputs['Color'], bdsf.inputs["Subsurface Color"])
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
            mat.node_tree.links.new(simgnode.outputs['Color'], seprgb.inputs['Image'])
            mat.node_tree.links.new(seprgb.outputs['R'], bdsf.inputs['Specular'])
            mat.node_tree.links.new(seprgb.outputs['G'], bdsf.inputs['Metallic'])
        else:
            mat.node_tree.links.new(simgnode.outputs['Color'], bdsf.inputs['Specular'])
            # bdsf.inputs['Metallic'].default_value = 0
            
        yloc = simgnode.location[1] + offset_y

    # --- Normal Map --- 
    
    if fulltextures[1] != "":
        nmap = nodes.new("ShaderNodeNormalMap")
        if shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
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
            rgbsep = nodes.new("ShaderNodeSeparateRGB")
            rgbcomb = nodes.new("ShaderNodeCombineRGB")
            mat.node_tree.links.new(rgbsep.outputs['R'], rgbcomb.inputs['R'])
            mat.node_tree.links.new(rgbsep.outputs['G'], rgbcomb.inputs['B'])
            mat.node_tree.links.new(rgbsep.outputs['B'], rgbcomb.inputs['G'])
            mat.node_tree.links.new(rgbcomb.outputs['Image'], nmap.inputs['Color'])
            mat.node_tree.links.new(nimgnode.outputs['Color'], rgbsep.inputs['Image'])
            rgbsep.location = (bdsf.location[0] + inter1_offset_x, yloc)
            rgbcomb.location = (bdsf.location[0] + inter2_offset_x, yloc)
        else:
            mat.node_tree.links.new(nimgnode.outputs['Color'], nmap.inputs['Color'])
            nmap.location = (bdsf.location[0] + inter2_offset_x, yloc)
                         
        mat.node_tree.links.new(nmap.outputs['Normal'], bdsf.inputs['Normal'])

        if shape.parent.game in ["SKYRIM", "SKYRIMSE"] and not shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
            # Specular is in the normal map alpha channel
            mat.node_tree.links.new(nimgnode.outputs['Alpha'], bdsf.inputs['Specular'])
            
        
    obj.active_material = mat

def find_shader_node(nodelist, nodeid):
    """ Look up a shader node by bl_idname"""
    resultlist = list(filter(lambda n: n.bl_idname == nodeid, nodelist))
    if len(resultlist) > 0:
        return resultlist[0]
    else:
        return None

def export_shader_attrs(obj, shader, shape):
    mat = obj.active_material

    if 'BSLSP_Shader_Type' in mat.keys():
        shape.shader_attributes.Shader_Type = int(mat['BSLSP_Shader_Type'])
        log.debug(f"....setting shader type to {shape.shader_attributes.Shader_Type}")
    if 'BSLSP_Shader_Name' in mat.keys() and len(mat['BSLSP_Shader_Name']) > 0:
        shape.shader_name = mat['BSLSP_Shader_Name']
    if 'BSLSP_Shader_Flags_1' in mat.keys():
        shape.shader_attributes.Shader_Flags_1 = int(mat['BSLSP_Shader_Flags_1'], 16)
    if 'BSLSP_Shader_Flags_2' in mat.keys():
        shape.shader_attributes.Shader_Flags_2 = int(mat['BSLSP_Shader_Flags_2'], 16)
    shape.shader_attributes.Emissive_Color_R = shader.inputs['Emission'].default_value[0]
    shape.shader_attributes.Emissive_Color_G = shader.inputs['Emission'].default_value[1]
    shape.shader_attributes.Emissive_Color_B = shader.inputs['Emission'].default_value[2]
    shape.shader_attributes.Emissive_Color_A = shader.inputs['Emission'].default_value[3]
    shape.shader_attributes.Emissive_Mult = shader.inputs['Emission Strength'].default_value
    shape.shader_attributes.Alpha = shader.inputs['Alpha'].default_value
    if 'BSLSP_Refraction_Str' in mat.keys():
        shape.Refraction_Str = mat['BSLSP_Refraction_Str']
    shape.shader_attributes.Glossiness = shader.inputs['Metallic'].default_value * GLOSS_SCALE
    if 'BSLSP_Spec_Color_R' in mat.keys():
        shape.shader_attributes.Spec_Color_R = mat['BSLSP_Spec_Color_R']
    if 'BSLSP_Spec_Color_G' in mat.keys():
        shape.shader_attributes.Spec_Color_G = mat['BSLSP_Spec_Color_G']
    if 'BSLSP_Spec_Color_B' in mat.keys():
        shape.shader_attributes.Spec_Color_B = mat['BSLSP_Spec_Color_B']
    if 'BSLSP_Spec_Str' in mat.keys():
        shape.shader_attributes.Spec_Str = mat['BSLSP_Spec_Str']
    if 'BSLSP_Spec_Str' in mat.keys():
        shape.shader_attributes.Soft_Lighting = mat['BSLSP_Soft_Lighting']
    if 'BSLSP_Spec_Str' in mat.keys():
        shape.shader_attributes.Rim_Light_Power = mat['BSLSP_Rim_Light_Power']
    if 'BSLSP_Skin_Tint_Color_R' in mat.keys():
        shape.shader_attributes.Skin_Tint_Color_R = mat['BSLSP_Skin_Tint_Color_R']
    if 'BSLSP_Skin_Tint_Color_G' in mat.keys():
        shape.shader_attributes.Skin_Tint_Color_G = mat['BSLSP_Skin_Tint_Color_G']
    if 'BSLSP_Skin_Tint_Color_B' in mat.keys():
        shape.shader_attributes.Skin_Tint_Color_G = mat['BSLSP_Skin_Tint_Color_B']

    #log.debug(f"Shader Type: {shape.shader_attributes.Shader_Type}")
    #log.debug(f"Shader attributes: \n{shape.shader_attributes}")

def has_msn_shader(obj):
    val = False
    if obj.active_material:
        nodelist = obj.active_material.node_tree.nodes
        shader_node = find_shader_node(nodelist, 'ShaderNodeBsdfPrincipled')
        normal_input = shader_node.inputs['Normal']
        if normal_input.is_linked:
            nmap_node = normal_input.links[0].from_node
            if nmap_node.space == "OBJECT":
                val = True
    return val

def export_shader(obj, shape):
    """Create shader from the given material"""
    log.debug(f"...exporting material for object {obj.name}")
    shader = shape.shader_attributes
    nodelist = obj.active_material.node_tree.nodes
    
    # Texture paths
    norm_txt_node = None
    shader_node = find_shader_node(nodelist, 'ShaderNodeBsdfPrincipled')
    if shader_node:
        export_shader_attrs(obj, shader_node, shape)

        diffuse_input = shader_node.inputs['Base Color']
        if diffuse_input.is_linked:
            diffuse_node = diffuse_input.links[0].from_node
            if diffuse_node.image:
                diffuse_fp_full = diffuse_node.image.filepath
                diffuse_fp = diffuse_fp_full[diffuse_fp_full.lower().find('textures'):]
                log.debug(f"....Writing diffuse texture path '{diffuse_fp}'")
                shape.set_texture(0, diffuse_fp)
        
        normal_input = shader_node.inputs['Normal']
        if normal_input.is_linked:
            nmap_node = normal_input.links[0].from_node
            if nmap_node.space == "OBJECT":
                shape.shader_attributes.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
            else:
                shape.shader_attributes.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)
            prior_input = nmap_node.inputs['Color']
            prior_node = prior_input.links[0].from_node
            if prior_node and prior_node.bl_idname == 'ShaderNodeCombineRGB':
                prior_input = prior_node.inputs['R']
                prior_node = prior_input.links[0].from_node
            if prior_node and prior_node.bl_idname == 'ShaderNodeSeparateRGB':
                prior_input = prior_node.inputs['Image']
                prior_node = prior_input.links[0].from_node
            if prior_node and prior_node.bl_idname == 'ShaderNodeTexImage' and prior_node.image:
                norm_txt_node = prior_node
                norm_fp_full = norm_txt_node.image.filepath
                norm_fp = norm_fp_full[norm_fp_full.lower().find('textures'):]
                log.debug(f"....Writing normal texture path '{norm_fp}'")
                shape.set_texture(1, norm_fp)

        sk_input = shader_node.inputs['Subsurface Color']
        if sk_input.is_linked:
            sk_node = sk_input.links[0].from_node
            if sk_node.image:
                sk_fp_full = sk_node.image.filepath
                sk_fp = sk_fp_full[sk_fp_full.lower().find('textures'):]
                log.debug(f"....Writing subsurface texture path '{sk_fp}'")
                shape.set_texture(2, sk_fp)

        spec_input = shader_node.inputs['Specular']
        if spec_input.is_linked:
            prior_node = spec_input.links[0].from_node
            if prior_node and prior_node.bl_idname == 'ShaderNodeSeparateRGB':
                prior_input = prior_node.inputs['Image']
                prior_node = prior_input.links[0].from_node
            if prior_node and prior_node.bl_idname == 'ShaderNodeTexImage'and \
                prior_node != norm_txt_node and prior_node.image:
                spec_fp_full = prior_node.image.filepath
                spec_fp = spec_fp_full[spec_fp_full.lower().find('textures'):]
                log.debug(f"....Writing subsurface texture path '{spec_fp}'")
                shape.set_texture(7, spec_fp)

        alpha_input = shader_node.inputs['Alpha']
        if alpha_input.is_linked:
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


# -----------------------------  MESH CREATION -------------------------------

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
    if len(shape.colors) > 0:
        log.debug(f"..Importing vertex colors for {shape.name}")
        clayer = mesh.vertex_colors.new()
        colors = shape.colors
        for lp in mesh.loops:
            clayer.data[lp.index].color = colors[lp.vertex_index]


def import_shape(the_shape: NiShape):
    """ Import the shape to a Blender object, translating bone names """
    v = the_shape.verts
    t = the_shape.tris

    new_mesh = bpy.data.meshes.new(the_shape.name)
    new_mesh.from_pydata(v, [], t)
    new_object = bpy.data.objects.new(the_shape.name, new_mesh)
    import_colors(new_mesh, the_shape)

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
    new_object.rotation_euler[0], new_object.rotation_euler[1], new_object.rotation_euler[2] = inv_xf.rotation.euler_deg()

    mesh_create_uv(new_object.data, the_shape.uvs)
    mesh_create_bone_groups(the_shape, new_object)
    mesh_create_partition_groups(the_shape, new_object)
    for f in new_mesh.polygons:
        f.use_smooth = True

    new_mesh.update(calc_edges=True, calc_edges_loose=True)
    new_mesh.validate(verbose=True)

    obj_create_material(new_object, the_shape)

    import_shape_extra(new_object, the_shape) 

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
    
    # use the transform in the file if there is one; otherwise get the 
    # transform from the reference skeleton
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

    # Import shapes
    for s in f.shapes:
        for n in s.bone_names: 
            log.debug(f"....adding bone {n} for {s.name}")
            bones.add(n) 
        if f.game == 'FO4' and fo4FaceDict.matches(bones) > 10:
            f.dict = fo4FaceDict

        obj = import_shape(s)
        new_objs.append(obj)
        new_collection.objects.link(obj)

    # Import armature
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
    
    # Import nif-level extra data
    import_extra(f)

    for o in new_objs: o.select_set(True)
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
    if mesh.shape_keys is None:
        log.debug(f"Adding first shape key to {obj.name}")
        newsk = obj.shape_key_add()
        mesh.shape_keys.use_relative=True
        newsk.name = "Basis"
        mesh.update()

    for morph_name, morph_verts in sorted(tri.morphs.items()):
        if morph_name not in mesh.shape_keys.key_blocks:
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
                log.warning(f"BS Tri file shape does not match any selected object: {shapename}")
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
            tri.morphs[m] = morphdict[m]
    
        log.info(f"Generating tri file '{fname_tri}'")
        tri.write(fname_tri, expression_morphs)

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
    log.debug(f"....UV in object mode: {uvlayer[2].uv[:]}")

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
    """Returns 5 lists of equal length with one entry each for each vertex
        verts = [(x, y, z)... ] - base or as modified by target-key if provided
        weights = [{group-name: weight}... ] - 1:1 with verts list
        dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
            if "target_key" is specified this will be empty
        """
    weights = []
    morphdict = {}

    if target_key != '' and mesh.shape_keys:
        log.debug(f"....exporting shape {target_key} only")
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
        mat = MatTransform()
        mat.translation = b.head_local
        try:
            mat.rotation = RotationMatrix((tuple(b['pyxform'][0]), 
                                           tuple(b['pyxform'][1]), 
                                           tuple(b['pyxform'][2])))
        except:
            nif = shape.parent
            bone_xform = nif.get_node_xform_to_global(nif.nif_name(b.name)) 
            mat.rotation = bone_xform.rotation
        
        result[b.name] = mat
    
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
    new_shape.transform = new_xform
    new_shape.set_global_to_skin(new_xform.invert())
    
    group_names = [g.name for g in obj.vertex_groups]
    weights_by_bone = get_weights_by_bone(weights_by_vert)
    used_bones = weights_by_bone.keys()
    arma_bones = get_bone_xforms(arma.data, used_bones, new_shape)
    
    for bone_name, bone_xform in arma_bones.items():
        # print(f"  shape {obj.name} adding bone {bone_name}")
        if bone_name in weights_by_bone and len(weights_by_bone[bone_name]) > 0:
            # print(f"..Shape {obj.name} exporting bone {bone_name} with rotation {bone_xform.rotation.euler_deg()}")
            nifname = new_shape.parent.nif_name(bone_name)
            new_shape.add_bone(nifname, bone_xform)
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
    g.add(verts, 1.0, 'REPLACE')


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
    return matchgame == "" or matchgame == nif.game


def partitions_from_vert_groups(obj):
    """ Return dictionary of Partition objects for all vertex groups that match the partition 
        name pattern. These are all partition objects including subsegments.
    """
    val = {}
    if obj.vertex_groups:
        for vg in obj.vertex_groups:
            skyid = SkyPartition.name_match(vg.name)
            if skyid >= 0:
                val[vg.name] = SkyPartition(part_id=skyid, flags=0, name=vg.name)
            else:
                segid = FO4Segment.name_match(vg.name)
                if segid >= 0:
                    val[vg.name] = FO4Segment(len(val), 0, name=vg.name)
        
        # A second pass to pick up subsections
        for vg in obj.vertex_groups:
            if vg.name not in val:
                parent_name, subseg_id, material = FO4Subsegment.name_match(vg.name)
                if subseg_id >= 0:
                    if not parent_name in val.keys():
                        # Create parent segments if not there
                        if parent_name == '':
                            parent_name = f"FO4Segment #{len(val)}"
                        parid = FO4Segment.name_match(parent_name)
                        val[parent_name] = FO4Segment(len(val), 0, parent_name)
                    p = val[parent_name]
                    log.debug(f"....Found FO4Subsegment '{vg.name}' child of '{parent_name}'")
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
    outnif.initialize(game, filepath)
    ret = export_shape(outnif, outtrip, shape, '', shape.parent) 
    outnif.save()
    log.info(f"..Wrote {filepath}")
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


class NifExporter:
    """ Object that handles the export process 
    """
    def __init__(self, filepath, game):
        self.filepath = filepath
        self.game = game
        self.warnings = set()
        self.armature = None
        self.facebones = None
        self.objects = set([])
        self.bg_data = set([])
        self.str_data = set([])
        # Shape keys that start with underscore and are common to all exportable shapes trigger
        # a separate file export for each shape key
        self.file_keys = []
        self.objs_unweighted = set()
        self.objs_scale = set()
        self.objs_mult_part = set()
        self.objs_no_part = set()
        self.arma_game = []

    def add_object(self, obj):
        """ Adds the given object to the objects to export """
        if obj.type == 'ARMATURE':
            if self.game == 'FO4' and is_facebones(obj) and self.facebones is None:
                self.facebones = obj
            if self.armature is None:
                self.armature = obj 

        elif obj.type == 'MESH':
            self.objects.add(obj)
            if obj.parent and obj.parent.type == 'ARMATURE':
                self.add_object(obj.parent)
            self.file_keys = get_with_uscore(get_common_shapes(self.objects))

        elif 'BSBehaviorGraphExtraData_Name' in obj.keys():
            self.bg_data.add(obj)

        elif 'NiStringExtraData_Name' in obj.keys():
            self.str_data.add(obj)

        # remove extra data nodes with objects in the export list as parents so they 
        # don't get exported twice
        for n in self.bg_data:
            if n.parent and n.parent in self.objects:
                self.bg_data.remove(n)
        for n in self.str_data:
            if n.parent and n.parent in self.objects:
                self.str_data.remove(n)

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

    def export_extra_data(self, nif):
        exdatalist = [ (x['NiStringExtraData_Name'], x['NiStringExtraData_Value']) for x in \
            self.str_data]
        if len(exdatalist) > 0:
            nif.string_data = exdatalist

        exdatalist = [ (x['BSBehaviorGraphExtraData_Name'], x['BSBehaviorGraphExtraData_Value']) \
                for x in self.bg_data]
        if len(exdatalist) > 0:
            nif.behavior_graph_data = exdatalist

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
            # All 3 have to be in the vertex group to count
            vg0 = all_vertex_groups(weights_by_vert[t[0]])
            vg1 = all_vertex_groups(weights_by_vert[t[1]])
            vg2 = all_vertex_groups(weights_by_vert[t[2]])
            tri_partitions = vg0.intersection(vg1).intersection(vg2).intersection(partition_set)
            if len(tri_partitions) > 0:
                #if len(tri_partitions) > 1:
                #    log.warning(f"Found multiple partitions for tri {t} in object {obj.name}: {tri_partitions}")
                #    self.objs_mult_part.add(obj)
                #    create_group_from_verts(obj, MULTIPLE_PARTITION_GROUP, t)

                # Triangulation will put some tris in two partitions. Just choose one--
                # exact division doesn't matter (if it did user should have put in an edge)
                tri_indices[i] = partitions[next(iter(tri_partitions))].id
            else:
                log.warning(f"Tri {t} is not assigned any partition")
                self.objs_no_part.add(obj)
                create_group_from_verts(obj, NO_PARTITION_GROUP, t)

        return list(partitions.values()), tri_indices

    def extract_mesh_data(self, obj, target_key):
        """ 
        Extract the mesh data from the given object
            obj = object being exported
            target_key = shape key to export
        returns
            verts = list of XYZ vertex locations
            norms_new = list of XYZ normal values, 1:1 with verts
            uvmap_new = list of (u, v) values, 1:1 with verts
            colors_new = list of RGB color values 1:1 with verts. May be None.
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

        try:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        
            # If scales aren't uniform, apply them before export
            if obj.scale[0] != obj.scale[1] or obj.scale[0] != obj.scale[2]:
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
                loopcolors = [c.color[:] for c in editmesh.vertex_colors.active.data]
                #log.debug(f"Saved loop colors: {loopcolors}")
        
            # Apply shape key verts to the mesh so normals will be correct.  If the mesh has
            # custom normals, fukkit -- use the custom normals and assume the deformation
            # won't be so great that it looks bad.
            bpy.ops.object.mode_set(mode = 'OBJECT') 
            uvlayer = editmesh.uv_layers.active.data
            if target_key != '' and not editmesh.has_custom_normals:
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

        obj.data.update()
        log.info("..Exporting to nif")
        norms_exp = norms_new
        has_msn = has_msn_shader(obj)
        if has_msn:
            norms_exp = None

        new_shape = nif.createShapeFromData(obj.name, verts, tris, uvmap_new, norms_exp, 
                                            is_headpart, is_skinned)
        if colors_new:
            new_shape.set_colors(colors_new)

        export_shape_data(obj, new_shape)
        
        if obj.active_material:
            export_shader(obj, new_shape)
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

        new_xform = MatTransform();
        new_xform.translation = obj.location
        new_xform.rotation = RotationMatrix((obj.matrix_local[0][0:3], 
                                                obj.matrix_local[1][0:3], 
                                                obj.matrix_local[2][0:3]))
        new_xform.scale = obj.scale[0]
        
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
            new_shape.transform = new_xform

        retval |= export_tris(nif, trip, obj, verts, tris, uvmap_new, morphdict)

        log.info(f"..{obj.name} successfully exported")
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
            exportf.initialize(self.game, fpath)
            if suffix == '_faceBones':
                exportf.dict = fo4FaceDict

            self.export_extra_data(exportf)

            trip = TripFile()

            for obj in self.objects:
                self.export_shape(exportf, trip, obj, sk, arma)
                log.debug(f"Exported shape {obj.name}")

            exportf.save()
            log.info(f"..Wrote {fpath}")

            if len(trip.shapes) > 0:
                trippath = os.path.join(os.path.dirname(self.filepath), fbasename) + ".tri"
                trip.write(trippath)
                log.info(f"..Wrote {trippath}")


    def do_export(self):
        log.debug(f"..Exporting objects: {self.objects}\nstring data: {self.str_data}\nBG data: {self.bg_data}\narmature: armatrue: {self.armature},\nfacebones: {self.facebones}")
        if self.facebones:
            self.export_file_set(self.facebones, '_faceBones')
        if self.armature:
            self.export_file_set(self.armature, '')
        if self.facebones is None and self.armature is None:
            self.export_file_set(None, '')
    
    def export(self, objects):
        self.set_objects(objects)
        self.do_export()
        

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

        log.info("NIFLY EXPORT V%d.%d.%d" % bl_info['version'])
        NifFile.Load(nifly_path)

        try:
            exporter = NifExporter(self.filepath, self.target_game)
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
    TEST_PARTITIONS = False
    TEST_SEGMENTS = False
    TEST_BP_SEGMENTS = False
    TEST_ROGUE01 = False
    TEST_ROGUE02 = False
    TEST_NORMAL_SEAM = False
    TEST_COLORS = False
    TEST_HEADPART = False
    TEST_FACEBONES = False
    TEST_FACEBONE_EXPORT = False
    TEST_TIGER_EXPORT = False
    TEST_JIARAN = False
    TEST_SHADER_LE = False
    TEST_SHADER_SE = False
    TEST_SHADER_FO4 = False
    TEST_SHADER_ALPHA = False
    TEST_SHEATH = False
    TEST_FEET = False
    TEST_SKYRIM_XFORM = True

    NifFile.Load(nifly_path)
    #LoggerInit()

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

    def export_from_blend(blendfile, objname, game, outfile, shapekey=''):
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

        clear_all()
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        log.debug("TODO: support objects with flat shading or autosmooth properly")
        for f in cube.data.polygons: f.use_smooth = True

        filepath = os.path.join(pynifly_dev_path, r"tests\Out\testSkyrim01.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'SKYRIM')
        exporter.export([cube])

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

        print("## And can do the same for FO4")

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        for f in cube.data.polygons: f.use_smooth = True

        filepath = os.path.join(pynifly_dev_path, r"tests\Out\testFO401.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'FO4')
        exporter.export([cube])

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        f = NifFile(filepath)
        sourceGame = f.game
        assert f.game == "FO4", "ERROR: Wrong game found"
        assert f.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape, got {f.shapes[0].blockname}"

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
        remove_file(outfile)
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

        clear_all()

        # Import body and armor
        f_in = NifFile(os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif"))
        import_nif(f_in)
        the_armor = bpy.data.objects["Armor"]
        the_body = bpy.data.objects["MaleBody"]
        assert 'NPC Foot.L' in the_armor.vertex_groups, f"ERROR: Left foot is in the groups: {the_armor.vertex_groups}"
        
        # Export armor
        filepath_armor = os.path.join(pynifly_dev_path, "tests/out/testArmorSkyrim02.nif")
        remove_file(filepath_armor)
        exporter = NifExporter(filepath_armor, 'SKYRIM')
        exporter.export([the_armor])
        assert os.path.exists(filepath_armor), "ERROR: File not created"

        # Check armor
        ftest = NifFile(filepath_armor)
        assert ftest.shapes[0].name[0:5] == "Armor", "ERROR: Armor not read"
        gts = ftest.shapes[0].global_to_skin
        assert int(gts.translation[2]) == -120, f"ERROR: Armor offset not correct: {gts.translation[2]}"

        # Write armor to FO4 (wrong skeleton but whatevs, just see that it doesn't crash)
        filepath_armor_fo = os.path.join(pynifly_dev_path, r"tests\Out\testArmorFO02.nif")
        remove_file(filepath_armor_fo)
        exporter = NifExporter(filepath_armor_fo, 'FO4')
        exporter.export([the_armor])
        assert os.path.exists(filepath_armor_fo), f"ERROR: File {filepath_armor_fo} not created"

        # Write body 
        filepath_body = os.path.join(pynifly_dev_path, r"tests\Out\testBodySkyrim02.nif")
        body_out = NifFile()
        remove_file(filepath_body)
        exporter = NifExporter(filepath_body, 'SKYRIM')
        exporter.export([the_body])
        assert os.path.exists(filepath_body), f"ERROR: File {filepath_body} not created"
        # Should do some checking here

    if TEST_BPY_ALL or TEST_ROUND_TRIP:
        print("## TEST_ROUND_TRIP Can do the full round trip: nif -> blender -> nif -> blender")

        print("..Importing original file")
        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor1 = obj

        assert int(armor1.location.z) == 120, "ERROR: Armor moved above origin by 120 to skinned position"
        maxz = max([v.co.z for v in armor1.data.vertices])
        minz = min([v.co.z for v in armor1.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices are positioned below origin"

        assert len(armor1.data.vertex_colors) == 0, "ERROR: Armor should have no colors"

        print("..Exporting  to test file")
        outfile1 = os.path.join(pynifly_dev_path, "tests/Out/testSkyrim03.nif")
        remove_file(outfile1)
        exporter = NifExporter(outfile1, 'SKYRIM')
        exporter.export([armor1])
        #export_shape_to(armor1, outfile1, "SKYRIM")
        #export_file_set(outfile1, 'SKYRIM', [''], [armor1], armor1.parent)
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
        new_object.data.uv_layers.active = newuv
        bpy.context.collection.objects.link(new_object)
        bpy.context.view_layer.objects.active = new_object

        filepath = os.path.join(pynifly_dev_path, "tests/Out/testUV01.nif")
        exporter = NifExporter(filepath, "SKYRIM")
        exporter.export([new_object])
        #export_file_set(filepath, "SKYRIM", [''], [new_object], None)

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
                e = NifExporter(outfile, "FO4")
                e.export([obj])

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
        e = NifExporter(outfile, 'FO4')
        e.export([eyes, head])
        #export_file_set(outfile, 'FO4', [''], [eyes, head], head.parent)
        #outnif = NifFile()
        #outnif.initialize("FO4", outfile)
        #export_shape(outnif, TripFile(), eyes)
        #export_shape(outnif, TripFile(), head)
        #outnif.save()

        testnif = NifFile(outfile)
        testhead = testnif.shape_by_root('Baby_Head')
        testeyes = testnif.shape_by_root('Baby_Eyes')
        assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
        assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"
        assert testhead.blockname == "BSSubIndexTriShape", f"Error: Expected BSSubIndexTriShape on skinned shape, got {testhead.blockname}"

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
            remove_file(f)

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

        e = NifExporter(os.path.join(pynifly_dev_path, testout2), "FO4")
        e.export([triobj])
        #export_file_set(os.path.join(pynifly_dev_path, testout2), "FO4", [''], [triobj], triobj.parent)
        
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
        e = NifExporter(tricubenif, "SKYRIM")
        e.export([cube])
        #export_file_set(tricubenif, "SKYRIM", [''], [cube], cube.parent)

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

        baby = append_from_file("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
        baby.parent.name == "BabyExportRoot", f"Error: Should have baby and armature"
        log.debug(f"Found object {baby.name}")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests\Out\weight0.nif"), "FO4")
        e.export([baby])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests\Out\weight0.nif"), 
        #                "FO4", 
        #                [''],
        #                [baby], 
        #                baby.parent)
        assert UNWEIGHTED_VERTEX_GROUP in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


    if TEST_BPY_ALL or TEST_SPLIT_NORMAL:
        print("## TEST_SPLIT_NORMAL Can handle meshes with split normals")

        plane = append_from_file("Plane", False, r"tests\skyrim\testSplitNormalPlane.blend", r"\Object", "Plane")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), "FO4")
        e.export([plane])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), 
        #                "FO4", [''], [plane], plane.parent)


    if TEST_BPY_ALL or TEST_PARTITIONS:
        print("## TEST_PARTITIONS: Can read Skyrim partions")
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/MaleHead.nif")

        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        assert "SBP_130_HEAD" in obj.vertex_groups, "Skyrim body parts read in as vertex groups with sensible names"

        print("### Can write Skyrim partitions")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"), "SKYRIM")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"),
        #                "SKYRIM", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"))
        assert len(nif2.shapes[0].partitions) == 3, "Have all skyrim partitions"
        assert nif2.shapes[0].partitions[2].id == 143, "Have ears"

    if TEST_BPY_ALL or TEST_SEGMENTS:
        print("### TEST_SEGMENTS: Can read FO4 segments")
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/VanillaMaleBody.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        assert "FO4 Human Arm.R" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "Should have FO4 segment file read and saved for later use"

        print("### Can write FO4 segments")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"),
        #                "FO4", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"))
        assert len(nif2.shapes[0].partitions) == 7, "Have all FO4 partitions"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == nif2.shapes[0].segment_file, f"Nif should reference segment file, found '{nif2.shapes[0].segment_file}'"

    if TEST_BPY_ALL or TEST_BP_SEGMENTS:
        print("### TEST_BP_SEGMENTS: Can read FO4 bodypart segments")
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/Helmet.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        #for o in bpy.context.selected_objects:
        #    if o.name.startswith("Helmet:0"):
        #        obj = o
        obj = bpy.context.object
        assert "FO4 30 - Hair Top" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
        assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == obj['FO4_SEGMENT_FILE'], "FO4 segment file read and saved for later use"

        print("### Can write FO4 segments")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"),
        #                "FO4", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"))
        assert len(nif2.shapes[0].partitions) == 2, "Have all FO4 partitions"
        ss30 = None
        for p in nif2.shapes[0].partitions:
            for s in p.subsegments:
                if s.user_slot == 30:
                    ss30 = s
                    break
        assert ss30 is not None, "Mesh has FO4Subsegment 30"
        assert ss30.material == 0x86b72980, "FO4Subsegment 30 should have correct material"
        assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == nif2.shapes[0].segment_file, "Nif references segment file"

    if TEST_BPY_ALL or TEST_ROGUE01:
        print("### TEST_ROGUE01: Mesh with wonky normals exports correctly")

        obj = append_from_file("MHelmetLight:0", False, r"tests\FO4\WonkyNormals.blend", r"\Object", "MHelmetLight:0")
        assert obj.name == "MHelmetLight:0", "Got the right object"
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE01.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE01.nif"), 
        #                "FO4", [''], [obj], obj.parent)

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE01.nif"))
        shape2 = nif2.shapes[0]

        assert round(shape2.normals[44][0]) == 0, f"Normal should point sraight up, found {shape2.normals[44]}"
        assert round(shape2.normals[44][1]) == 0, f"Normal should point sraight up, found {shape2.normals[44]}"
        assert round(shape2.normals[44][2]) == 1, f"Normal should point sraight up, found {shape2.normals[44]}"

        assert 6.82 == round(shape2.verts[12][0], 2), f"Vert location wrong: 6.82 != {shape2.verts[12][0]}"
        assert 0.58 == round(shape2.verts[12][1], 2), f"Vert location wrong: 0.58 != {shape2.verts[12][0]}"
        assert 9.05 == round(shape2.verts[12][2], 2), f"Vert location wrong: 9.05 != {shape2.verts[12][0]}"
        assert 0.13 == round(shape2.verts[5][0], 2), f"Vert location wrong: 0.13 != {shape2.verts[5][0]}"
        assert 9.24 == round(shape2.verts[5][1], 2), f"Vert location wrong: 9.24 != {shape2.verts[5][0]}"
        assert 8.91 == round(shape2.verts[5][2], 2), f"Vert location wrong: 8.91 != {shape2.verts[5][0]}"
        assert -3.21 == round(shape2.verts[33][0], 2), f"Vert location wrong: -3.21 != {shape2.verts[33][0]}"
        assert -1.75 == round(shape2.verts[33][1], 2), f"Vert location wrong: -1.75 != {shape2.verts[33][0]}"
        assert 12.94 == round(shape2.verts[33][2], 2), f"Vert location wrong: 12.94 != {shape2.verts[33][0]}"

        # Original has a tri <12, 13, 14>. Find it in the original and then in the exported object

        found = -1
        target = set([12, 13, 14])
        for p in obj.data.polygons:
            ps = set([obj.data.loops[lp].vertex_index for lp in p.loop_indices])
            if ps == target:
                print(f"Found triangle in source mesh at {p.index}")
                found = p.index
                break
        assert found >= 0, "Triangle not in source mesh"

        found = -1
        for i, t in enumerate(shape2.tris):
            if set(t) == target:
                print(f"Found triangle in target mesh at {i}")
                found = i
                break
        assert found >= 0, "Triangle not in output mesh"

    if TEST_BPY_ALL or TEST_ROGUE02:
        print("### TEST_ROGUE02: Shape keys export normals correctly")

        #obj = append_from_file("Plane", False, r"tests\Skyrim\ROGUE02-normals.blend", r"\Object", "Plane")
        #assert obj.name == "Plane", "Got the right object"
        #bpy.ops.object.select_all(action='DESELECT')
        #bpy.context.view_layer.objects.active = obj
        #bpy.ops.object.mode_set(mode="OBJECT")
        #outnif = NifFile()
        #outtrip = TripFile()
        #outnif.initialize("SKYRIM", os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE02_warp.nif"))
        #export_shape(outnif, outtrip, obj, "_warp") 
        #outnif.save()
        export_from_blend(r"tests\Skyrim\ROGUE02-normals.blend",
                          "Plane",
                          "SKYRIM",
                          r"tests/Out/TEST_ROGUE02.nif",
                          "_warp")

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE02_warp.nif"))
        shape2 = nif2.shapes[0]
        assert len(shape2.verts) == 25, f"Export shouldn't create extra vertices, found {len(shape2.verts)}"
        v = [round(x, 1) for x in shape2.verts[18]]
        assert v == [0.0, 0.0, 0.2], f"Vertex found at incorrect position: {v}"
        n = [round(x, 1) for x in shape2.normals[8]]
        assert n == [0, 1, 0], f"Normal should point along y axis, instead: {n}"


    if TEST_BPY_ALL or TEST_NORMAL_SEAM:
        print("### TEST_NORMAL_SEAM: Normals on a split seam are seamless")

        export_from_blend(r"tests\FO4\TestKnitCap.blend",
                          "MLongshoremansCap:0",
                          "FO4",
                          r"tests/Out/TEST_NORMAL_SEAM.nif",
                          "_Dog")

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_NORMAL_SEAM_Dog.nif"))
        shape2 = nif2.shapes[0]
        target_vert = [i for i, v in enumerate(shape2.verts) if VNearEqual(v, (0.0, 8.0, 9.3))]

        assert len(target_vert) == 2, "Expect vert to have been split"
        assert VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


    if TEST_BPY_ALL or TEST_COLORS:
        print("### TEST_COLORS: Can read & write vertex colors")
        bpy.ops.object.select_all(action='DESELECT')
        export_from_blend(r"tests\FO4\VertexColors.blend",
                          "Plane",
                          "FO4",
                          r"tests/Out/TEST_COLORS_Plane.nif",
                          "_Test")

        nif3 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLORS_Plane.nif"))
        assert len(nif3.shapes[0].colors) > 0, f"Expected color layers, have: {len(nif3.shapes[0].colors)}"
        cd = nif3.shapes[0].colors
        assert cd[0] == (0.0, 1.0, 0.0, 1.0), f"First vertex found: {cd[0]}"
        assert cd[1] == (1.0, 1.0, 0.0, 1.0), f"Second vertex found: {cd[1]}"
        assert cd[2] == (1.0, 0.0, 0.0, 1.0), f"Second vertex found: {cd[2]}"
        assert cd[3] == (0.0, 0.0, 1.0, 1.0), f"Second vertex found: {cd[3]}"

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/HeadGear1.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        colordata = obj.data.vertex_colors.active.data
        targetv = find_vertex(obj.data, (1.62, 7.08, 0.37))
        assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
        for lp in obj.data.loops:
            if lp.vertex_index == targetv:
                assert colordata[lp.index].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[lp.index].color[:]}"

        testfileout = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLORSB_HeadGear1.nif")
        e = NifExporter(testfileout, "FO4")
        e.export([obj])
        #export_file_set(testfileout, "FO4", [''], [obj], obj.parent)

        nif2 = NifFile(testfileout)
        assert nif2.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not reread correctly: {nif2.shapes[0].colors[0]}"
        assert nif2.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0), f"Color 561 not reread correctly: {nif2.shapes[0].colors[561]}"

    if TEST_BPY_ALL or TEST_HEADPART:
        print("### TEST_HEADPART: Can read & write an SE head part")

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/SKYRIMSE/malehead.nif")
        nif = NifFile(testfile)
        import_nif(nif)
        obj = bpy.context.object

        testtri = os.path.join(pynifly_dev_path, r"tests/SKYRIMSE/malehead.tri")
        import_tri(testtri)

        assert len(obj.data.shape_keys.key_blocks) == 45, f"Expected key blocks 45 != {len(obj.data.shape_keys.key_blocks)}"
        assert obj.data.shape_keys.key_blocks[0].name == "Basis", f"Expected first key 'Basis' != {obj.data.shape_keys.key_blocks[0].name}"

        testfileout = os.path.join(pynifly_dev_path, r"tests/out/TEST_HEADPART_malehead.nif")
        e = NifExporter(testfileout, 'SKYRIMSE')
        e.export([obj])
        #export_file_set(testfileout, 'SKYRIMSE', [''], [obj], obj.parent)

        nif2 = NifFile(testfileout)
        assert len(nif2.shapes) == 1, f"Expected single shape, 1 != {len(nif2.shapes)}"
        assert nif2.shapes[0].blockname == "BSDynamicTriShape", f"Expected 'BSDynamicTriShape' != '{nif2.shapes[0].blockname}'"


    if TEST_BPY_ALL or TEST_FACEBONES:
        print("### TEST_FACEBONES: Facebones are renamed from Blender to the game's names")

        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/basemalehead_facebones.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        assert 'skin_bone_Dimple.R' in obj.vertex_groups.keys(), f"Expected munged vertex groups"
        assert 'skin_bone_Dimple.R' in obj.parent.data.bones.keys(), f"Expected munged bone names"
        assert 'skin_bone_R_Dimple' not in obj.vertex_groups.keys(), f"Expected munged vertex groups"
        assert 'skin_bone_R_Dimple' not in obj.parent.data.bones.keys(), f"Expected munged bone names"

        outfile = os.path.join(pynifly_dev_path, r"tests/Out/basemalehead.nif")
        remove_file(outfile)
        e = NifExporter(outfile, 'FO4')
        e.export([obj])
        #export_file_set(outfile, 'FO4', [''], [obj], obj.parent, '_faceBones')

        outfile2 = os.path.join(pynifly_dev_path, r"tests/Out/basemalehead_facebones.nif")
        nif2 = NifFile(outfile2)
        assert 'skin_bone_R_Dimple' in nif2.shapes[0].bone_names, f"Expected game bone names, got {nif2.shapes[0].bone_names[0:10]}"
    
        
    if TEST_BPY_ALL or TEST_FACEBONE_EXPORT:
        print("### TEST_FACEBONE_EXPORT: Test can export facebones + regular nif; shapes with hidden verts export correctly")

        clear_all()

        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.tri"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri"))

        obj = append_from_file("HorseFemaleHead", False, r"tests\FO4\HeadFaceBones.blend", r"\Object", "HorseFemaleHead")
        bpy.ops.object.select_all(action='SELECT')
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.nif"),
                               "FO4")
        exporter.from_context(bpy.context)
        exporter.do_export()

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.nif"))
        assert len(nif1.shapes) == 1, "Write the file successfully"
        assert len(nif1.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif"))
        assert len(nif2.shapes) == 1
        assert len(nif2.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"
        tri1 = TriFile.from_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.tri"))
        assert len(tri1.morphs) > 0
        tri2 = TriFile.from_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri"))
        assert len(tri2.morphs) > 0

    if TEST_BPY_ALL or TEST_JIARAN:
        print("#### TEST_JIARAN: Armature with no stashed transforms exports correctly")

        clear_all()
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"))

        append_from_file("hair.001", True, r"tests\SKYRIMSE\jiaran.blend", r"\Object", "hair.001")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"), 
                               'SKYRIMSE')
        exporter.export([bpy.data.objects["hair.001"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"))
        assert len(nif1.shapes) == 1, f"Expected Jiaran nif"

    if TEST_BPY_ALL or TEST_SHADER_LE:
        print("## TEST_SHADER_LE Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileLE = os.path.join(pynifly_dev_path, r"tests\Skyrim\meshes\actors\character\character assets\malehead.nif")
        nifLE = NifFile(fileLE)
        import_nif(nifLE)
        shaderAttrsLE = nifLE.shapes[0].shader_attributes
        for obj in bpy.context.selected_objects:
            if "MaleHeadIMF" in obj.name:
                headLE = obj
        assert len(headLE.active_material.node_tree.nodes) == 9, "ERROR: Didn't import images"
        g = round(headLE.active_material.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value, 4)
        assert round(g, 4) == 33/GLOSS_SCALE, f"Glossiness not correct, value is {g}"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_LE.nif"), 
                               'SKYRIM')
        exporter.export([headLE])

        nifcheckLE = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_LE.nif"))
        
        assert nifcheckLE.shapes[0].textures[0] == nifLE.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[0]}' != '{nifLE.shapes[0].textures[0]}'"
        assert nifcheckLE.shapes[0].textures[1] == nifLE.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[1]}' != '{nifLE.shapes[0].textures[1]}'"
        assert nifcheckLE.shapes[0].textures[2] == nifLE.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[2]}' != '{nifLE.shapes[0].textures[2]}'"
        assert nifcheckLE.shapes[0].textures[7] == nifLE.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[7]}' != '{nifLE.shapes[0].textures[7]}'"
        assert nifcheckLE.shapes[0].shader_attributes == shaderAttrsLE, f"Error: Shader attributes not preserved:\n{nifcheckLE.shapes[0].shader_attributes}\nvs\n{shaderAttrsLE}"

    if TEST_BPY_ALL or TEST_SHADER_FO4:
        print("## TEST_SHADER_FO4 Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileFO4 = os.path.join(pynifly_dev_path, r"tests\FO4\Meshes\Actors\Character\CharacterAssets\basemalehead.nif")
        nifFO4 = NifFile(fileFO4)
        import_nif(nifFO4)
        shaderAttrsFO4 = nifFO4.shapes[0].shader_attributes
        for obj in bpy.context.selected_objects:
            if "BaseMaleHead:0" in obj.name:
                headFO4 = obj
        assert len(headFO4.active_material.node_tree.nodes) == 7, "ERROR: Didn't import images"

        print("## Shader attributes are written on export")

        exp = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_FO4.nif"), 'FO4')
        exp.export([headFO4])

        nifcheckFO4 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_FO4.nif"))
        
        assert nifcheckFO4.shapes[0].textures[0] == nifFO4.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[0]}' != '{nifFO4.shapes[0].textures[0]}'"
        assert nifcheckFO4.shapes[0].textures[1] == nifFO4.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[1]}' != '{nifFO4.shapes[0].textures[1]}'"
        assert nifcheckFO4.shapes[0].textures[2] == nifFO4.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[2]}' != '{nifFO4.shapes[0].textures[2]}'"
        assert nifcheckFO4.shapes[0].textures[7] == nifFO4.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[7]}' != '{nifFO4.shapes[0].textures[7]}'"
        assert nifcheckFO4.shapes[0].shader_attributes == shaderAttrsFO4, f"Error: Shader attributes not preserved:\n{nifcheckFO4.shapes[0].shader_attributes}\nvs\n{shaderAttrsFO4}"
        assert nifcheckFO4.shapes[0].shader_name == nifFO4.shapes[0].shader_name, f"Error: Shader name not preserved: '{nifcheckFO4.shapes[0].shader_name}' != '{nifFO4.shapes[0].shader_name}'"


    if TEST_BPY_ALL or TEST_SHADER_SE:
        print("## TEST_SHADER_SE Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileSE = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\meshes\furniture\noble\noblecrate01.nif")
        nifSE = NifFile(fileSE)
        import_nif(nifSE)
        shaderAttrsSE = nifSE.shapes[0].shader_attributes
        for obj in bpy.context.selected_objects:
            if "NobleCrate01:1" in obj.name:
                crate = obj
        assert len(crate.active_material.node_tree.nodes) == 5, "ERROR: Didn't import images"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_SE.nif"), 
                               'SKYRIMSE')
        exporter.export([crate])

        nifcheckSE = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_SE.nif"))
        
        assert nifcheckSE.shapes[0].textures[0] == nifSE.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[0]}' != '{nifSE.shapes[0].textures[0]}'"
        assert nifcheckSE.shapes[0].textures[1] == nifSE.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[1]}' != '{nifSE.shapes[0].textures[1]}'"
        assert nifcheckSE.shapes[0].textures[2] == nifSE.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[2]}' != '{nifSE.shapes[0].textures[2]}'"
        assert nifcheckSE.shapes[0].textures[7] == nifSE.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[7]}' != '{nifSE.shapes[0].textures[7]}'"
        assert nifcheckSE.shapes[0].shader_attributes == shaderAttrsSE, f"Error: Shader attributes not preserved:\n{nifcheckSE.shapes[0].shader_attributes}\nvs\n{shaderAttrsSE}"

    if TEST_BPY_ALL or TEST_SHADER_ALPHA:
        print("## TEST_SHADER_ALPHA Shader attributes are read and turned into Blender shader nodes")
        # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the suffix.

        clear_all()

        fileAlph = os.path.join(pynifly_dev_path, r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
        nifAlph = NifFile(fileAlph)
        import_nif(nifAlph)
        furshape = nifAlph.shapes[1]
        for obj in bpy.context.selected_objects:
            if "tail_fur.001" in obj.name:
                tail = obj
        assert len(tail.active_material.node_tree.nodes) == 9, "ERROR: Didn't import images"
        assert tail.active_material.blend_method == 'CLIP', f"Error: Alpha blend is '{tail.active_material.blend_method}', not 'CLIP'"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_ALPH.nif"), 'SKYRIM')
        exporter.export([tail])

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_ALPH.nif"))
        checkfurshape = None
        for s in nifCheck.shapes:
            if s.name == "tail_fur.001":
                checkfurshape = s
                break
        
        assert checkfurshape.textures[0] == furshape.textures[0], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[0]}' != '{furshape.textures[0]}'"
        assert checkfurshape.textures[1] == furshape.textures[1], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[1]}' != '{furshape.textures[1]}'"
        assert checkfurshape.textures[2] == furshape.textures[2], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[2]}' != '{furshape.textures[2]}'"
        assert checkfurshape.textures[7] == furshape.textures[7], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[7]}' != '{furshape.textures[7]}'"
        assert checkfurshape.shader_attributes == furshape.shader_attributes, f"Error: Shader attributes not preserved:\n{checkfurshape.shader_attributes}\nvs\n{furshape.shader_attributes}"

        assert checkfurshape.has_alpha_property, f"Error: Did not write alpha property"
        assert checkfurshape.alpha_property.flags == furshape.alpha_property.flags, f"Error: Alpha flags incorrect: {checkfurshape.alpha_property.flags} != {furshape.alpha_property.flags}"
        assert checkfurshape.alpha_property.threshold == furshape.alpha_property.threshold, f"Error: Alpha flags incorrect: {checkfurshape.alpha_property.threshold} != {furshape.alpha_property.threshold}"


    if TEST_BPY_ALL or TEST_SHEATH:
        print("## TEST_SHEATH Extra data nodes are imported and exported")
        
        clear_all()

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True, confirm=False)
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/sheath_p1_1.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        bgnames = set([obj['BSBehaviorGraphExtraData_Name'] for obj in bpy.data.objects if obj.name.startswith("BSBehaviorGraphExtraData")])
        assert bgnames == set(["BGED"]), f"Error: Expected BG extra data properties, found {bgnames}"
        snames = set([obj['NiStringExtraData_Name'] for obj in bpy.data.objects if obj.name.startswith("NiStringExtraData")])
        assert snames == set(["HDT Havok Path", "HDT Skinned Mesh Physics Object"]), f"Error: Expected string extra data properties, found {snames}"

        # Write and check
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHEATH.nif"), 'SKYRIM')
        exporter.export(bpy.data.objects)

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHEATH.nif"))
        sheathShape = nifCheck.shapes[0]
        names = [x[0] for x in nifCheck.behavior_graph_data]
        assert "BGED" in names, f"Error: Expected BGED in {names}"
        strings = [x[0] for x in nifCheck.string_data]
        assert "HDT Havok Path" in strings, f"Error expected havoc path in {strings}"
        assert "HDT Skinned Mesh Physics Object" in strings, f"Error: Expected physics object in {strings}"


    if TEST_BPY_ALL or TEST_FEET:
        print("## TEST_FEET Extra data nodes are imported and exported")

        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/caninemalefeet_1.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        feet = bpy.data.objects['FootLowRes']
        assert len(feet.children) == 1, "Feet have children"
        assert feet.children[0]['NiStringExtraData_Name'] == "SDTA", "Feet have extra data child"
        assert feet.children[0]['NiStringExtraData_Value'].startswith('[{"name"'), f"Feet have string data"

        # Write and check that it's correct
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FEET.nif"), 'SKYRIMSE')
        exporter.export([feet])

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FEET.nif"))
        feetShape = nifCheck.shapes[0]
        assert feetShape.string_data[0][0] == 'SDTA', "String data name written correctly"
        assert feetShape.string_data[0][1].startswith('[{"name"'), "String data value written correctly"

    if TEST_BPY_ALL or TEST_SKYRIM_XFORM:
        print("## TEST_SKYRIM_XFORM: Can read & write the Skyrim shape transforms")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/MaleHead.nif")
        nif = NifFile(testfile)
        import_nif(nif)

        obj = bpy.context.object
        assert int(obj.location[2]) == 120, f"Shape offset not applied to head, found {obj.location[2]}"

        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SKYRIM_XFORM.nif"), "SKYRIM")
        e.export([obj])
        
        nifcheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SKYRIM_XFORM.nif"))
        headcheck = nifcheck.shapes[0]
        assert int(headcheck.transform.translation[2]) == 120, f"Shape offset not written correctly, found {headcheck.transform.translation[2]}"
        assert int(headcheck.global_to_skin.translation[2]) == -120, f"Shape global-to-skin not written correctly, found {headcheck.global_to_skin.translation[2]}"



# #############################################################################################
#
#    REGRESSION TESTS
#
#    These tests cover specific cases that have caused bugs in the past.
#
# ############################################################################################

    if TEST_BPY_ALL or TEST_TIGER_EXPORT:
        print("### TEST_TIGER_EXPORT: Tiger head exports without errors")

        clear_all()
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT_faceBones.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.tri"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT_chargen.tri"))

        append_from_file("TigerMaleHead", True, r"tests\FO4\Tiger.blend", r"\Object", "TigerMaleHead")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"), 
                               'FO4')
        exporter.export([bpy.data.objects["TigerMaleHead"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"))
        assert len(nif1.shapes) == 1, f"Expected tiger nif"



        
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
