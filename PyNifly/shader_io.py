"""Shader Import/Export for pyNifly"""

# Copyright © 2021, Bad Dog.

import os
from pathlib import Path
import logging
import bpy
from pynifly import *
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
import blender_defs as BD

ALPHA_MAP_NAME = "VERTEX_ALPHA"
MSN_GROUP_NAME = "MSN_TRANSFORM"
TANGENT_GROUP_NAME = "TANGENT_TRANSFORM"
GLOSS_SCALE = 100
ATTRIBUTE_NODE_HEIGHT = 200
NODE_WIDTH = 200
TEXTURE_NODE_WIDTH = 300
TEXTURE_NODE_HEIGHT = 290
INPUT_NODE_HEIGHT = 100
COLOR_NODE_HEIGHT = 200
NORMAL_SCALE = 1.0 # Possible to make normal more obvious

NISHADER_IGNORE = [
    'baseColor',
    'baseColorScale',
    'bufSize', 
    'bufType', 
    'controllerID', 
    'Emissive_Color',
    'Emissive_Mult',
    'greyscaleTexture',
    'nameID', 
    'sourceTexture',
    'UV_Offset_U',
    'UV_Offset_V',
    'UV_Scale_U',
    'UV_Scale_V',
    'textureClampMode',
    ]

def tangent_normal(nodetree, source, destination, location):
    """
    Create a group node that handles the transformations for tangent space normals (Skyrim
    and FO4).
    """
    # # Create a new shader group
    # shader_group = bpy.data.node_groups.new(type='ShaderNodeTree', name='TangentNormal')

    # # create group inputs
    # group_inputs = shader_group.nodes.new('NodeGroupInput')
    # group_inputs.location = (-200,0)
    # shader_group.inputs.new('NodeSocketColor','Image')

    shader_group = None
    internal_location = location
    internal_nodetree = nodetree

    nodelist = internal_nodetree.nodes
    # Need to invert the green channel for blender
    try:
        rgbsep = nodelist.new("ShaderNodeSeparateColor")
        rgbsep.mode = 'RGB'
        combine_name = "ShaderNodeCombineColor"
        socketname = 'Color'
    except:
        rgbsep = nodelist.new("ShaderNodeSeparateRGB")
        combine_name = "ShaderNodeCombineRGB"
        socketname = 'Image'
    rgbsep.location = internal_location

    colorinv = nodelist.new("ShaderNodeInvert")
    colorinv.location = rgbsep.location + Vector((200, -150))
    rgbcomb = nodelist.new(combine_name)
    rgbcomb.location = colorinv.location + Vector((200, 150))
    if combine_name == "ShaderNodeCombineRGB": rgbcomb.mode = 'RGB'

    nmap = nodelist.new("ShaderNodeNormalMap")
    nmap.location = rgbcomb.location + Vector((200, 0))
    nmap.space = 'TANGENT'
    nmap.inputs['Strength'].default_value = 2.0 # Make it a little more obvious.

    internal_nodetree.links.new(rgbsep.outputs[0], rgbcomb.inputs[0])
    internal_nodetree.links.new(rgbsep.outputs[2], rgbcomb.inputs[2])
    internal_nodetree.links.new(rgbsep.outputs[1], colorinv.inputs['Color'])
    internal_nodetree.links.new(colorinv.outputs['Color'], rgbcomb.inputs[1])
    internal_nodetree.links.new(rgbcomb.outputs[socketname], nmap.inputs['Color'])
    internal_nodetree.links.new(source, rgbsep.inputs[socketname])
    
    # # create group outputs
    # group_outputs = shader_group.nodes.new('NodeGroupOutput')
    # group_outputs.location = nmap.location + Vector((200, 0))
    # shader_group.outputs.new('NodeSocketVector', 'Normal')

    internal_nodetree.links.new(nmap.outputs['Normal'], destination)

    # # Make the node in the object's shader that references this group.
    # g = nodetree.nodes.new("ShaderNodeGroup")
    # g.name = TANGENT_GROUP_NAME
    # g.label = "Tangent Normal"
    # g.location = location
    # g.node_tree = shader_group
    # nodetree.links.new(source, g.inputs[0])
    # nodetree.links.new(g.outputs[0], destination)

    # return g

def make_separator(nodetree, input, loc):
    """
    Make a separator node with input connected to socket "input".
    Safe for all Blender 3.x and 4.0
    """
    try:
        rgbsep = nodetree.nodes.new("ShaderNodeSeparateColor")
        rgbsep.location = loc
        rgbsep.mode = 'RGB'
        nodetree.links.new(input, rgbsep.inputs['Color'])
        return rgbsep
    except:
        pass

    rgbsep = nodetree.nodes.new("ShaderNodeSeparateRGB")
    rgbsep.location = loc
    nodetree.links.new(input, rgbsep.inputs['Image'])
    return rgbsep


def make_specular(nodetree, source, strength, color, bsdf, location=(0, 0)):
    """'
    Make nodes to handle specular.
    source = socket with the source specular map.
    strength = socket with the specular strength to use.
    color = socket with the specular color to use.
    bsdf = shader node to receive specular values.
    """
    if 'Specular' in bsdf.inputs:
        skt = bsdf.inputs['Specular']
    elif 'Specular IOR Level' in bsdf.inputs:
        skt = bsdf.inputs['Specular IOR Level']
    m = new_mixnode(nodetree,
                    source,
                    strength,
                    skt)
    m.location = location

    nodetree.links.new(color, bsdf.inputs['Specular Tint'])
   

def make_combiner(nodetree, r, g, b, loc):
    """
    Make a combiner node with inputs from sockets r, g, b. Returns output socket.
    Safe for all Blender 3.x and 4.0
    """
    try:
        combiner = nodetree.nodes.new("ShaderNodeCombineColor")
        combiner.location = loc
        combiner.mode = 'RGB'
        nodetree.links.new(r, combiner.inputs[0])
        nodetree.links.new(g, combiner.inputs[1])
        nodetree.links.new(b, combiner.inputs[2])
        return combiner
    except:
        pass

    rgbsep = nodetree.nodes.new("ShaderNodeCombineRGB")
    combiner.location = loc
    nodetree.links.new(r, combiner.inputs[0])
    nodetree.links.new(g, combiner.inputs[1])
    nodetree.links.new(b, combiner.inputs[2])
    return combiner


def make_shader_skyrim(parent, location, msn=False, colormap_name='Col'):
    """
    Returns a group node implementing a shader for Skyrim.
    """
    grp = bpy.data.node_groups.new(type='ShaderNodeTree', name='SkyrimShader')

    group_inputs = grp.nodes.new('NodeGroupInput')
    group_inputs.location = (-6*NODE_WIDTH, -0.5 * TEXTURE_NODE_HEIGHT)
    grp.inputs.new('NodeSocketColor', 'Diffuse')
    grp.inputs.new('NodeSocketFloat', 'Alpha')
    grp.inputs.new('NodeSocketFloat', 'Alpha Mult')
    grp.inputs.new('NodeSocketColor', 'Use Vertex Color')
    grp.inputs.new('NodeSocketColor', 'Vertex Color')
    grp.inputs.new('NodeSocketFloat', 'Use Vertex Alpha')
    grp.inputs.new('NodeSocketFloat', 'Vertex Alpha')
    grp.inputs.new('NodeSocketColor', 'Subsurface')
    grp.inputs.new('NodeSocketColor', 'Subsurface Str')
    grp.inputs.new('NodeSocketColor', 'Specular')
    grp.inputs.new('NodeSocketColor', 'Specular Color')
    grp.inputs.new('NodeSocketFloat', 'Specular Str')
    grp.inputs.new('NodeSocketColor', 'Normal')
    grp.inputs.new('NodeSocketFloat', 'Glossiness')
    grp.inputs.new('NodeSocketColor', 'Emission')
    grp.inputs.new('NodeSocketFloat', 'Emission Strength')

    # Shader output node
    bsdf = grp.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (NODE_WIDTH, 0)

    # Diffuse and alpha
    mixcolor = new_mixnode(grp, 
                          group_inputs.outputs['Diffuse'],
                          group_inputs.outputs['Vertex Color'],
                          bsdf.inputs['Base Color'])
    mixcolor.location = group_inputs.location + Vector((2 * NODE_WIDTH, 2*TEXTURE_NODE_HEIGHT,))
    grp.links.new(group_inputs.outputs['Use Vertex Color'], mixcolor.inputs['Factor'])
    diffuse_socket = mixcolor.outputs[0]
    
    # mixvertalph = new_mixnode(grp, 
    #                       group_inputs.outputs['Alpha'],
    #                       group_inputs.outputs['Vertex Alpha'],
    #                       None)
    # mixvertalph.location = mixcolor.location + Vector((0, -TEXTURE_NODE_HEIGHT,))
    # grp.links.new(group_inputs.outputs['Use Vertex Alpha'], mixvertalph.inputs['Factor'])
    
    invalph = grp.nodes.new('ShaderNodeMath')
    invalph.location = mixcolor.location + Vector((0, -TEXTURE_NODE_HEIGHT))
    invalph.operation = 'SUBTRACT'
    invalph.inputs[0].default_value = 1.0
    grp.links.new(group_inputs.outputs['Use Vertex Alpha'], invalph.inputs[1])

    mixvertalph = grp.nodes.new('ShaderNodeMath')
    mixvertalph.location = invalph.location + Vector((NODE_WIDTH, 0,))
    mixvertalph.operation = 'MAXIMUM'
    grp.links.new(invalph.outputs[0], mixvertalph.inputs[0])
    grp.links.new(group_inputs.outputs['Vertex Alpha'], mixvertalph.inputs[1])

    mixtxtalph = grp.nodes.new('ShaderNodeMath')
    mixtxtalph.location = mixvertalph.location + Vector((NODE_WIDTH, 0,))
    mixtxtalph.operation = 'MULTIPLY'
    grp.links.new(mixvertalph.outputs[0], mixtxtalph.inputs[0])
    grp.links.new(group_inputs.outputs['Alpha'], mixtxtalph.inputs[1])

    multalph = grp.nodes.new('ShaderNodeMath')
    multalph.location = mixtxtalph.location + Vector((NODE_WIDTH, 0,))
    multalph.operation = 'MULTIPLY'
    grp.links.new(mixtxtalph.outputs[0], multalph.inputs[0])
    grp.links.new(group_inputs.outputs['Alpha Mult'], multalph.inputs[1])
    grp.links.new(multalph.outputs[0], bsdf.inputs['Alpha'])

    # Subsurface
    specsat = grp.nodes.new('ShaderNodeHueSaturation')
    specsat.location = invalph.location + Vector((NODE_WIDTH, -COLOR_NODE_HEIGHT))
    grp.links.new(group_inputs.outputs['Subsurface Str'], specsat.inputs['Saturation'])
    grp.links.new(group_inputs.outputs['Subsurface'], specsat.inputs['Color'])

    if 'Subsurface Weight' in bsdf.inputs:
        grp.links.new(group_inputs.outputs['Subsurface Str'], bsdf.inputs["Subsurface Weight"])
    else:
        grp.links.new(group_inputs.outputs['Subsurface Str'], bsdf.inputs["Subsurface"])

    if "Subsurface Color" in bsdf.inputs:
        # If there's a color input, connect to that.
        grp.links.new(specsat.outputs['Color'], bsdf.inputs["Subsurface Color"])
    else:
        # No color input. Let the shader do the scattering, but mix the subsurface
        # color with the base color.
        m = new_mixnode(grp, 
                        diffuse_socket,
                        specsat.outputs['Color'],
                        bsdf.inputs['Base Color'],
                        blend_type='SCREEN')
        m.location = Vector((NODE_WIDTH, -COLOR_NODE_HEIGHT))

    # Specular 
    make_specular(grp,
                  group_inputs.outputs['Specular'],
                  group_inputs.outputs['Specular Str'],
                  group_inputs.outputs['Specular Color'],
                  bsdf,
                  mixcolor.location + Vector((0, -2.2*TEXTURE_NODE_HEIGHT)))
    # if 'Specular' in bsdf.inputs:
    #     skt = bsdf.inputs['Specular']
    # elif 'Specular IOR Level' in bsdf.inputs:
    #     skt = bsdf.inputs['Specular IOR Level']
    # m = new_mixnode(grp,
    #                 group_inputs.outputs['Specular'],
    #                 group_inputs.outputs['Specular Str'],
    #                 skt)
    # m.location = mixcolor.location + Vector((0, -2.2*TEXTURE_NODE_HEIGHT))

    # grp.links.new(group_inputs.outputs['Specular Color'], bsdf.inputs['Specular Tint'])

    # Glossiness

    map = grp.nodes.new('ShaderNodeMapRange')
    map.location = group_inputs.location + Vector((3 * NODE_WIDTH, -0.8 * TEXTURE_NODE_HEIGHT))
    map.inputs['From Min'].default_value = 0
    map.inputs['From Max'].default_value = 200
    map.inputs['To Min'].default_value = 1
    map.inputs['To Max'].default_value = 0
    grp.links.new(group_inputs.outputs['Glossiness'], map.inputs['Value'])
    grp.links.new(map.outputs[0], bsdf.inputs['Roughness'])

    # # Alternate inputs for Blender 4.0
    # if 'Specular IOR Level' in self.bsdf.inputs:
    #     # TODO: This is all wrong. IOR isn't what we want.
    #     # If there's a direct IOR level input, have to map range 0-1 to 1-2
    #     tobw = self.make_node('ShaderNodeRGBToBW',
    #                             xloc=last_node.location.x + 300,
    #                             yloc=simgnode.location.y)
    #     self.link(spec_socket, tobw.inputs['Color'])

    #     map = self.make_node('ShaderNodeMapRange',
    #                             xloc=tobw.location.x + 150,
    #                             yloc=simgnode.location.y)
    #     map.inputs['From Min'].default_value = 0
    #     map.inputs['From Max'].default_value = 1
    #     map.inputs['To Min'].default_value = 1
    #     map.inputs['To Max'].default_value = 2

    #     self.link(tobw.outputs['Val'], map.inputs[0])
    #     self.link(map.outputs[0], self.bsdf.inputs['Specular IOR Level'])

    # else:
    #     # Just hook to the specular input.
    #     self.link(spec_socket, self.bsdf.inputs['Specular'])

    # Normal map
    if msn:
        sep = make_separator(grp,
                             group_inputs.outputs['Normal'],
                             group_inputs.location + Vector((2 * NODE_WIDTH, -2 * TEXTURE_NODE_HEIGHT)))        
        # Need to swap green and blue channels for blender
        comb = make_combiner(grp, 
                             sep.outputs[0],
                             sep.outputs[2],
                             sep.outputs[1],
                             sep.location + Vector((NODE_WIDTH, 0)))

        norm = grp.nodes.new("ShaderNodeNormalMap")
        norm.location = comb.location + Vector((NODE_WIDTH, 0))
        norm.space = 'OBJECT'
        norm.inputs['Strength'].default_value = NORMAL_SCALE

        grp.links.new(comb.outputs[0], norm.inputs['Color'])
    else:
        separator = make_separator(
            grp, 
            group_inputs.outputs['Normal'], 
            group_inputs.location + Vector((2 * NODE_WIDTH, -2 * TEXTURE_NODE_HEIGHT)))

        inv = grp.nodes.new("ShaderNodeInvert")
        inv.location = separator.location + Vector((NODE_WIDTH, 0))
        grp.links.new(separator.outputs[2], inv.inputs['Color'])

        combiner = make_combiner(
            grp, 
            separator.outputs[0], 
            inv.outputs[0], 
            separator.outputs[2],
            inv.location + Vector((NODE_WIDTH, 0, )))
        
        norm = grp.nodes.new('ShaderNodeNormalMap')
        norm.location = combiner.location + Vector((NODE_WIDTH, 0, ))
        grp.links.new(combiner.outputs[0], norm.inputs['Color'])
    grp.links.new(norm.outputs['Normal'], bsdf.inputs['Normal'])

    # Emission
    grp.links.new(group_inputs.outputs['Emission'], bsdf.inputs['Emission'])
    grp.links.new(group_inputs.outputs['Emission Strength'], bsdf.inputs['Emission Strength'])    

    # Group outpts

    group_outputs = grp.nodes.new('NodeGroupOutput')
    group_outputs.location = (bsdf.location.x + NODE_WIDTH*2, 0)
    grp.outputs.new('NodeSocketShader', 'BSDF')
    grp.links.new(bsdf.outputs['BSDF'], group_outputs.inputs['BSDF'])

    shader_node = parent.nodes.new('ShaderNodeGroup')
    shader_node.name = shader_node.label = 'Skyrim Shader'
    shader_node.location = location
    shader_node.node_tree = grp

    return shader_node


def make_shader_fo4(parent, location):
    """
    Returns a group node implementing a shader for FO4.
    """
    grp = bpy.data.node_groups.new(type='ShaderNodeTree', name='FO4Shader')

    group_inputs = grp.nodes.new('NodeGroupInput')
    group_inputs.location = (-NODE_WIDTH, -TEXTURE_NODE_HEIGHT)
    grp.inputs.new('NodeSocketColor', 'Diffuse')
    grp.inputs.new('NodeSocketColor', 'Specular')
    grp.inputs.new('NodeSocketColor', 'Specular Color')
    grp.inputs.new('NodeSocketColor', 'Specular Str')
    grp.inputs.new('NodeSocketColor', 'Normal')
    grp.inputs.new('NodeSocketFloat', 'Alpha')
    grp.inputs.new('NodeSocketFloat', 'Alpha Mult')
    grp.inputs.new('NodeSocketColor', 'Emission')
    grp.inputs.new('NodeSocketFloat', 'Emission Strength')

    # Shader output node
    bsdf = grp.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (NODE_WIDTH * 4, 0)
    grp.links.new(group_inputs.outputs['Diffuse'], bsdf.inputs['Base Color'])
    grp.links.new(group_inputs.outputs['Alpha'], bsdf.inputs['Alpha'])

    # Specular and gloss
    separator = make_separator(grp, group_inputs.outputs['Specular'], (0, -50))

    inv = grp.nodes.new("ShaderNodeInvert")
    inv.location = (NODE_WIDTH, separator.location.y-100)
    grp.links.new(separator.outputs[1], inv.inputs['Color'])
    grp.links.new(inv.outputs[0], bsdf.inputs['Roughness'])

    make_specular(grp,
                  separator.outputs[0],
                  group_inputs.outputs['Specular Str'],
                  group_inputs.outputs['Specular Color'],
                  bsdf,
                  inv.location + Vector((NODE_WIDTH, INPUT_NODE_HEIGHT)))

    # # Alternate inputs for Blender 4.0
    # if 'Specular IOR Level' in self.bsdf.inputs:
    #     # TODO: This is all wrong. IOR isn't what we want.
    #     # If there's a direct IOR level input, have to map range 0-1 to 1-2
    #     tobw = self.make_node('ShaderNodeRGBToBW',
    #                             xloc=last_node.location.x + 300,
    #                             yloc=simgnode.location.y)
    #     self.link(spec_socket, tobw.inputs['Color'])

    #     map = self.make_node('ShaderNodeMapRange',
    #                             xloc=tobw.location.x + 150,
    #                             yloc=simgnode.location.y)
    #     map.inputs['From Min'].default_value = 0
    #     map.inputs['From Max'].default_value = 1
    #     map.inputs['To Min'].default_value = 1
    #     map.inputs['To Max'].default_value = 2

    #     self.link(tobw.outputs['Val'], map.inputs[0])
    #     self.link(map.outputs[0], self.bsdf.inputs['Specular IOR Level'])

    # else:
    #     # Just hook to the specular input.
    #     self.link(spec_socket, self.bsdf.inputs['Specular'])

    # Normal map
    separator = make_separator(grp, group_inputs.outputs['Normal'], (0, -1.5 * TEXTURE_NODE_HEIGHT))

    inv = grp.nodes.new("ShaderNodeInvert")
    inv.location = (NODE_WIDTH, separator.location.y-50)
    grp.links.new(separator.outputs[2], inv.inputs['Color'])

    combiner = make_combiner(grp, separator.outputs[0], inv.outputs[0], separator.outputs[2],
                             (NODE_WIDTH * 2, separator.location.y))
    
    norm = grp.nodes.new('ShaderNodeNormalMap')
    norm.location = (NODE_WIDTH * 3, separator.location.y)
    grp.links.new(combiner.outputs[0], norm.inputs['Color'])
    grp.links.new(norm.outputs['Normal'], bsdf.inputs['Normal'])

    group_outputs = grp.nodes.new('NodeGroupOutput')
    group_outputs.location = (bsdf.location.x + NODE_WIDTH*2, 0)
    grp.outputs.new('NodeSocketShader', 'BSDF')
    grp.links.new(bsdf.outputs['BSDF'], group_outputs.inputs['BSDF'])

    shader_node = parent.nodes.new('ShaderNodeGroup')
    shader_node.name = shader_node.label = 'FO4 Shader'
    shader_node.location = location
    shader_node.node_tree = grp

    return shader_node


def make_uv_node(parent, location):
    """
    Returns a group node for handling shader UV attributes: U/V origin, scale, and clamp
    mode.
    parent = parent node tree to contain the new node.
    """
    grp = bpy.data.node_groups.new(type='ShaderNodeTree', name='UV_Converter')

    group_inputs = grp.nodes.new('NodeGroupInput')
    group_inputs.location = (-200, 0)
    grp.inputs.new('NodeSocketFloat', 'Offset U')
    grp.inputs.new('NodeSocketFloat', 'Offset V')
    grp.inputs.new('NodeSocketFloat', 'Scale U')
    grp.inputs.new('NodeSocketFloat', 'Scale V')
    grp.inputs.new('NodeSocketInt', 'Clamp S')
    grp.inputs.new('NodeSocketInt', 'Clamp T')

    tc = grp.nodes.new('ShaderNodeTexCoord')
    tc.location = (-200, 400)

    tcsep = grp.nodes.new('ShaderNodeSeparateXYZ')
    tcsep.location = (tc.location.x + 200, tc.location.y)
    grp.links.new(tc.outputs['UV'], tcsep.inputs['Vector'])

    # Transform the U value

    u_add = grp.nodes.new('ShaderNodeMath')
    u_add.location = (tcsep.location.x + 200, tcsep.location.y)
    u_add.operation = 'ADD'
    grp.links.new(tcsep.outputs['X'], u_add.inputs[0])
    grp.links.new(group_inputs.outputs['Offset U'], u_add.inputs[1])

    u_scale = grp.nodes.new('ShaderNodeMath')
    u_scale.location = (u_add.location.x + 200, u_add.location.y - 50)
    u_scale.operation = 'MULTIPLY'
    grp.links.new(u_add.outputs['Value'], u_scale.inputs[0])
    grp.links.new(group_inputs.outputs['Scale U'], u_scale.inputs[1])

    u_map = grp.nodes.new('ShaderNodeMapRange')
    u_map.location = (u_scale.location.x + 200, u_scale.location.y - 200)
    grp.links.new(u_scale.outputs['Value'], u_map.inputs['Value'])

    u_comb = grp.nodes.new('ShaderNodeMix')
    u_comb.location = (u_map.location.x + 200, u_scale.location.y - 50)
    grp.links.new(group_inputs.outputs['Clamp S'], u_comb.inputs['Factor'])
    grp.links.new(u_scale.outputs['Value'], u_comb.inputs['B'])
    grp.links.new(u_map.outputs['Result'], u_comb.inputs['A'])

    # Transform the V value

    v_add = grp.nodes.new('ShaderNodeMath')
    v_add.location = (tcsep.location.x + 200, tcsep.location.y - 500)
    v_add.operation = 'ADD'
    grp.links.new(tcsep.outputs['Y'], v_add.inputs[0])
    grp.links.new(group_inputs.outputs['Offset V'], v_add.inputs[1])

    v_scale = grp.nodes.new('ShaderNodeMath')
    v_scale.location = (v_add.location.x + 200, v_add.location.y - 50)
    v_scale.operation = 'MULTIPLY'
    grp.links.new(v_add.outputs['Value'], v_scale.inputs[0])
    grp.links.new(group_inputs.outputs['Scale V'], v_scale.inputs[1])

    v_map = grp.nodes.new('ShaderNodeMapRange')
    v_map.location = (v_scale.location.x + 200, v_scale.location.y - 200)
    grp.links.new(v_scale.outputs['Value'], v_map.inputs['Value'])

    v_comb = grp.nodes.new('ShaderNodeMix')
    v_comb.location = (v_map.location.x + 200, v_scale.location.y - 50)
    grp.links.new(group_inputs.outputs['Clamp T'], v_comb.inputs['Factor'])
    grp.links.new(v_scale.outputs['Value'], v_comb.inputs['B'])
    grp.links.new(v_map.outputs['Result'], v_comb.inputs['A'])

    # Combine U & V

    uv_comb = grp.nodes.new('ShaderNodeCombineXYZ')
    uv_comb.location = (u_comb.location.x + 200, 0)
    grp.links.new(u_comb.outputs['Result'], uv_comb.inputs['X'])
    grp.links.new(v_comb.outputs['Result'], uv_comb.inputs['Y'])

    group_outputs = grp.nodes.new('NodeGroupOutput')
    group_outputs.location = (uv_comb.location.x + 200, 0)
    grp.outputs.new('NodeSocketVector', 'Vector')

    grp.links.new(uv_comb.outputs['Vector'], group_outputs.inputs['Vector'])


    # xyc = grp.nodes.new('ShaderNodeCombineXYZ')
    # xyc.location = (0, 100)
    # grp.links.new(group_inputs.outputs['Offset U'], xyc.inputs['X'])
    # grp.links.new(group_inputs.outputs['Offset V'], xyc.inputs['Y'])
    # xyc.inputs['Z'].default_value = 0

    # self.ytop = self.bsdf.location.y
    # uvou = self.make_node('ShaderNodeValue', name='UV_Offset_U', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
    # uvov = self.make_node('ShaderNodeValue', name='UV_Offset_V', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
    
    
    # uvsu = self.make_node('ShaderNodeValue', name='UV_Scale_U', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
    # uvsv = self.make_node('ShaderNodeValue', name='UV_Scale_V', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT*2)

    # xys = grp.nodes.new('ShaderNodeCombineXYZ')
    # xys.location = (0, -100)
    # grp.links.new(group_inputs.outputs['Scale U'], xys.inputs['X'])
    # grp.links.new(group_inputs.outputs['Scale V'], xys.inputs['Y'])
    # xys.inputs['Z'].default_value = 1.0

    # texmap = grp.nodes.new('ShaderNodeMapping')
    # texmap.location = (200, 0)
    # grp.links.new(tc.outputs['UV'], texmap.inputs['Vector'])
    # grp.links.new(xyc.outputs['Vector'], texmap.inputs['Location'])
    # grp.links.new(xys.outputs['Vector'], texmap.inputs['Scale'])
    # grp.links.new(texmap.outputs['Vector'], group_outputs.inputs['Vector'])

    shader_node = parent.new('ShaderNodeGroup')
    shader_node.name = shader_node.label = 'UV_Converter'
    shader_node.location = location
    shader_node.node_tree = grp

    return shader_node


def modelspace_normal(nodetree, source, destination, location):
    """
    Create a group node that handles the transformations for model space normals (Skyrim
    and FO4).

    Don't know yet how to handle group inputs and outputs for Blender 4.0, so finess that.
    """
    # Create a new shader group
    # shader_group = None
    # try:
    #     shader_group = bpy.data.node_groups.new(type='ShaderNodeTree', name='TangentNormal')

    #     # create group inputs
    #     group_inputs = shader_group.nodes.new('NodeGroupInput')
    #     group_inputs.location = (-200,0)
    #     shader_group.inputs.new('NodeSocketColor','Image')
    #     internal_location = (0, 0)
    #     internal_nodetree = shader_group
    # except:
    shader_group = None
    internal_location = location
    internal_nodetree = nodetree

    nodelist = internal_nodetree.nodes
    # Need to invert the green channel for blender
    try:
        rgbsep = nodelist.new("ShaderNodeSeparateColor")
        rgbsep.mode = 'RGB'
        combine_name = "ShaderNodeCombineColor"
        socketname = 'Color'

    except:
        rgbsep = nodelist.new("ShaderNodeSeparateRGB")
        combine_name = "ShaderNodeCombineRGB"
        socketname = 'Image'
    
    rgbsep.location = internal_location
    rgbcomb = nodelist.new(combine_name)
    rgbcomb.location = rgbsep.location + Vector((200, 0))
    if combine_name == "ShaderNodeCombineRGB": rgbcomb.mode = 'RGB'

    nmap = nodelist.new("ShaderNodeNormalMap")
    nmap.location = rgbcomb.location + Vector((200, 0))
    nmap.space = 'OBJECT'
    nmap.inputs['Strength'].default_value = NORMAL_SCALE

    # Need to swap green and blue channels for blender
    internal_nodetree.links.new(rgbsep.outputs[0], rgbcomb.inputs[0])
    internal_nodetree.links.new(rgbsep.outputs[1], rgbcomb.inputs[2])
    internal_nodetree.links.new(rgbsep.outputs[2], rgbcomb.inputs[1])
    internal_nodetree.links.new(rgbcomb.outputs[socketname], nmap.inputs['Color'])
    
    # create group outputs
    if shader_group:
        internal_nodetree.links.new(group_inputs.outputs[0], rgbsep.inputs[socketname])

        group_outputs = shader_group.nodes.new('NodeGroupOutput')
        group_outputs.location = nmap.location + Vector((200, 0))
        shader_group.outputs.new('NodeSocketVector', 'Normal')

        shader_group.links.new(nmap.outputs['Normal'], group_outputs.inputs[0])

        # Make the node in the object's shader that references this group.
        g = nodetree.nodes.new("ShaderNodeGroup")
        g.name = MSN_GROUP_NAME
        g.label = "Object Normal"
        g.location = location
        g.node_tree = shader_group

        nodetree.links.new(source, g.inputs[0])
        nodetree.links.new(g.outputs[0], destination)
    else:
        nodetree.links.new(source, rgbsep.inputs[socketname])
        nodetree.links.new(nmap.outputs['Normal'], destination)


def get_effective_colormaps(mesh):
    """ Return the colormaps we want to use
        Returns (colormap, alphamap)
        Either may be null
        """
    if not mesh:
        return None, None

    vertcolors = None
    colormap = None
    alphamap = None
    try:
        vertcolors = mesh.color_attributes
        colormap = vertcolors.active_color
    except:
        pass
    if not vertcolors:
        try:
            vertcolors = mesh.vertex_colors
            colormap = mesh.vertex_colors.active
        except:
            pass

    if not vertcolors:
        return None, None
        
    if colormap.name == ALPHA_MAP_NAME:
        alphamap = colormap
        colormap = None
        for vc in vertcolors:
            if vc.name != ALPHA_MAP_NAME:
                colormap = vc
                break

    if not alphamap and ALPHA_MAP_NAME in vertcolors.keys():
        alphamap = vertcolors[ALPHA_MAP_NAME]

    return colormap, alphamap


def new_mixnode(nodetree, input1, input2, output, blend_type='MULTIPLY'):
    """
    Create a shader RGB mix node--or fall back if it's an older version of Blender.
    """
    mixnode = None
    try:
        # Blender 3.5
        mixnode = nodetree.nodes.new("ShaderNodeMix")
        mixnode.data_type = 'RGBA'
        nodetree.links.new(input1, mixnode.inputs[6])
        nodetree.links.new(input2, mixnode.inputs[7])
        if output: nodetree.links.new(mixnode.outputs[2], output)
        mixnode.blend_type = blend_type
        mixnode.inputs['Factor'].default_value = 1
    except:
        pass

    if not mixnode:
        # Blender 3.1
        mixnode = nodetree.nodes.new("ShaderNodeMixRGB")
        nodetree.links.new(input1, mixnode.inputs['Color1'])
        nodetree.links.new(input2, mixnode.inputs['Color2'])
        if output: nodetree.links.new(mixnode.outputs['Color'], output)
        mixnode.blend_type = 'MULTIPLY'
        mixnode.inputs[0].default_value = 1

    return mixnode



class ShaderImporter:
    def __init__(self):
        self.material = None
        self.shape = None
        self.colormap = None
        self.alphamap = None
        self.bsdf = None
        self.nodes = None
        self.textures = {}
        self.diffuse = None
        self.diffuse_socket = None
        self.game = None
        self.do_specular = False

        self.inputs_offset_x = -1900
        self.calc1_offset_x = -1700
        self.calc2_offset_x = -1500
        self.img_offset_x = -1200
        self.cvt_offset_x = -300
        self.inter1_offset_x = -850
        self.inter2_offset_x = -700
        self.inter3_offset_x = -500
        self.inter4_offset_x = -300
        self.offset_y = -300
        self.gap_y = 10
        self.xloc = 0
        self.yloc = 0
        self.ytop = 0

        self.log = logging.getLogger("pynifly")

    
    @property 
    def emission_color_skt(self):
        if 'Emission Color' in self.bsdf.inputs:
            return self.bsdf.inputs['Emission Color']
        if 'Emission' in self.bsdf.inputs:
            return self.bsdf.inputs['Emission']
        

    def import_shader_attrs(self, shape:NiShape):
        """
        Import the shader attributes associated with the shape. All attributes are stored
        as properties on the material; attributes that have Blender equivalents are used
        to set up Blender nodes and properties.
        """
        shader = shape.shader
        shader.properties.extract(self.material, ignore=NISHADER_IGNORE)

        try:
            self.material['BS_Shader_Block_Name'] = shader.blockname
            self.material['BSLSP_Shader_Name'] = shader.name

            for i, v in enumerate(shader.Emissive_Color):
                self.nodes['Emissive_Color'].outputs[0].default_value[i] = v
            self.nodes['Emissive_Mult'].outputs[0].default_value = shader.Emissive_Mult

            if shader.blockname == 'BSLightingShaderProperty':
                self.nodes['Alpha'].outputs[0].default_value = shader.Alpha
                if 'Glossiness' in self.nodes:
                    self.nodes['Glossiness'].outputs['Value'].default_value = shader.Glossiness
            elif shape.shader_block_name == 'BSEffectShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = shader.falloffStartOpacity

            self.nodes['UV_Offset_U'].outputs['Value'].default_value = shape.shader.UV_Offset_U
            self.nodes['UV_Offset_V'].outputs['Value'].default_value = shape.shader.UV_Offset_V
            self.nodes['UV_Scale_U'].outputs['Value'].default_value = shape.shader.UV_Scale_U
            self.nodes['UV_Scale_V'].outputs['Value'].default_value = shape.shader.UV_Scale_V
            self.nodes['Clamp_S'].outputs['Value'].default_value \
                = (shape.shader.textureClampMode & 2) / 2
            self.nodes['Clamp_T'].outputs['Value'].default_value \
                = shape.shader.textureClampMode & 1

        except Exception as e:
            # Any errors, print the error but continue
            log.warning(str(e))


    def make_node(self, nodetype, name=None, xloc=None, yloc=None, height=300):
        """
        Make a node.If yloc not provided, use and increment the current ytop location.
        xloc is relative to the BSDF node. Have to pass the height in because Blender's
        height isn't correct.
        """
        if xloc != None:
            self.xloc = xloc
        n = self.nodes.new(nodetype)
        if yloc != None:
            n.location = (self.bsdf.location[0] + self.xloc, yloc)
        else:
            n.location = (self.bsdf.location[0] + self.xloc, self.ytop)
            self.ytop -= height + self.gap_y

        if name: 
            n.name = name
            n.label = name

        return n
    

    def make_uv_nodes(self):
        """
        Make the value nodes and calculations that are used as input to the shader.
        """

        self.ytop = self.bsdf.location.y
        uvou = self.make_node('ShaderNodeValue', name='UV_Offset_U', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        uvov = self.make_node('ShaderNodeValue', name='UV_Offset_V', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        
        uvsu = self.make_node('ShaderNodeValue', name='UV_Scale_U', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        uvsv = self.make_node('ShaderNodeValue', name='UV_Scale_V', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)

        clamps = self.make_node('ShaderNodeValue', name='Clamp_S', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        clampt = self.make_node('ShaderNodeValue', name='Clamp_T', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT*2)

        self.texmap = make_uv_node(self.nodes, (self.calc1_offset_x, 0,))
        self.link(uvou.outputs['Value'], self.texmap.inputs['Offset U'])
        self.link(uvov.outputs['Value'], self.texmap.inputs['Offset V'])
        self.link(uvsu.outputs['Value'], self.texmap.inputs['Scale U'])
        self.link(uvsv.outputs['Value'], self.texmap.inputs['Scale V'])
        self.link(clamps.outputs['Value'], self.texmap.inputs['Clamp S'])
        self.link(clampt.outputs['Value'], self.texmap.inputs['Clamp T'])


    def make_input_nodes(self):
        """Make additional input nodes."""
        if self.shape.shader.properties.bufType == PynBufferTypes.BSLightingShaderPropertyBufType:
            if self.game in ['SKYRIM', 'SKYRIMSE']:
                gl = self.make_node('ShaderNodeValue', 
                                    name='Glossiness', 
                                    xloc=self.diffuse.location.x, 
                                    height=INPUT_NODE_HEIGHT)
            
                # roughscale = self.make_node('ShaderNodeMapRange', 
                #                             xloc=self.calc2_offset_x,
                #                             yloc=gl.location.y-50)
                # roughscale.inputs['From Min'].default_value = 0
                # roughscale.inputs['From Max'].default_value = 200
                # roughscale.inputs['To Min'].default_value = 1.0
                # roughscale.inputs['To Max'].default_value = 0
                self.link(gl.outputs['Value'], self.bsdf.inputs['Glossiness'])
                # self.link(roughscale.outputs[0], self.bsdf.inputs['Roughness'])
        
        ec = self.make_node('ShaderNodeRGB',
                            name='Emissive_Color',
                            xloc=self.diffuse.location.x, 
                            height=COLOR_NODE_HEIGHT)        
        self.link(ec.outputs['Color'], self.emission_color_skt)
        em = self.make_node('ShaderNodeValue', 
                            name='Emissive_Mult', 
                            xloc=self.diffuse.location.x, 
                            height=INPUT_NODE_HEIGHT)
        self.link(em.outputs['Value'], self.bsdf.inputs['Emission Strength'])
        

    def import_shader_alpha(self, shape):
        if shape.has_alpha_property:
            self.material.alpha_threshold = shape.alpha_property.threshold
            if shape.alpha_property.flags & 1:
                self.material.blend_method = 'BLEND'
                self.material.alpha_threshold = shape.alpha_property.threshold/255
            else:
                self.material.blend_method = 'CLIP'
                self.material.alpha_threshold = shape.alpha_property.threshold/255
            self.material['NiAlphaProperty_flags'] = shape.alpha_property.flags
            self.material['NiAlphaProperty_threshold'] = shape.alpha_property.threshold

            if self.diffuse and self.bsdf and not self.bsdf.inputs['Alpha'].is_linked:
                # Alpha input may already have been hooked up if there are vertex alphas
                self.link(self.diffuse.outputs['Alpha'], self.bsdf.inputs['Alpha'])

            return True
        return False


    def find_textures(self, shape:NiShape):
        """
        Locate the textures referenced in the nif. Look for them in the nif's own filetree
        (if the nif is in a filetree). Otherwise look in Blender's texture directory if
        defined. If the texture file exists with a PNG extension, use that in preference
        to the DDS file.

        * shape = shape to read for texture files
        * self.textures <- dictionary of filepaths to use.
        """
        # log.debug(f"<find_textures>")
        self.textures = {}

        # Use any textures from Blender's texture directory, if defined. 
        # Strip the trailing "textures" directory, if present.
        btextures = None
        blender_dir = bpy.context.preferences.filepaths.texture_directory
        if os.path.split(blender_dir)[1] == '':
            blender_dir = os.path.split(blender_dir)[0]
        if os.path.split(blender_dir)[1].lower() == 'textures':
            blender_dir = os.path.split(blender_dir)[0]
        # if os.path.exists(blender_dir):
        #     btextures = extend_filenames(blender_dir, None, shape.textures)

        # Extend relative filenames in nif with nif's own filepath
        # fulltextures = extend_filenames(shape.file.filepath, "meshes", shape.textures)

        # Get the path to the "data" folder containing the nif.
        nif_dir = extend_filenames(shape.file.filepath, "meshes")
        
        for k, t in shape.textures.items():
            # Sometimes texture paths are missing the "textures" directory. 
            if not t.lower().startswith('textures'):
                t = os.path.join('textures', t)

            # First option is to use a png from Blender's texture directory, if any
            if blender_dir:
                fpng = Path(blender_dir, t).with_suffix('.png')
                if os.path.exists(fpng):
                    self.textures[k] = str(fpng)
                    continue

            # No PNG in Blender's directory, look for one relative to the nif.
            fpng = Path(nif_dir, t).with_suffix('.png')
            if os.path.exists(fpng):
                self.textures[k] = str(fpng)
                continue
            
            # No PNG at all, check for DDS.
            if blender_dir:
                fdds = os.path.join(blender_dir, t)
                if os.path.exists(fdds):
                    self.textures[k] = fdds
                    continue
            
            fdds = os.path.join(nif_dir, t)
            if os.path.exists(fdds):
                self.textures[k] = fdds
            

    def link(self, a, b):
        """Create a link between two nodes"""
        self.material.node_tree.links.new(a, b)


    def import_diffuse(self):
        """Create nodes for the diffuse texture."""
        #log.debug("Handling diffuse texture")
        self.ytop = self.bsdf.location.y + 2 * TEXTURE_NODE_HEIGHT

        txtnode = self.make_node("ShaderNodeTexImage",
                                 name='Diffuse_Texture',
                                 xloc=self.bsdf.location.x + self.img_offset_x,
                                 height=TEXTURE_NODE_HEIGHT)
        try:
            img = bpy.data.images.load(self.textures['Diffuse'], check_existing=True)
            img.colorspace_settings.name = "sRGB"
            txtnode.image = img
        except:
            pass
        self.link(self.texmap.outputs['Vector'], txtnode.inputs['Vector'])
        self.link(txtnode.outputs['Color'], self.bsdf.inputs['Diffuse'])

        if self.shape.has_alpha_property:
            self.link(txtnode.outputs['Alpha'], self.bsdf.inputs['Alpha'])
        else:
            alph = self.make_node('ShaderNodeRGB',
                                  name='Opaque Alpha',
                                  xloc=txtnode.location.x,
                                  height=COLOR_NODE_HEIGHT)
            alph.outputs['Color'].default_value = (1, 1, 1, 1)
            self.link(alph.outputs['Color'], self.bsdf.inputs['Alpha'])

        alph = self.make_node('ShaderNodeValue',
                                name='Alpha',
                                xloc=txtnode.location.x,
                                height=INPUT_NODE_HEIGHT)
        self.link(alph.outputs[0], self.bsdf.inputs['Alpha Mult'])

        if 'Use Vertex Color' in self.bsdf.inputs:
            usecolor = self.make_node('ShaderNodeValue',
                                name='Use Vertex Color',
                                height=INPUT_NODE_HEIGHT)
            self.link(usecolor.outputs[0], self.bsdf.inputs['Use Vertex Color'])
            if self.colormap:
                cmap = self.make_node('ShaderNodeAttribute',
                                    name='Vertex Color',
                                    xloc=txtnode.location.x,
                                    height=COLOR_NODE_HEIGHT)
                cmap.attribute_type = 'GEOMETRY'
                cmap.attribute_name = self.colormap.name
                self.link(cmap.outputs['Color'], self.bsdf.inputs['Vertex Color'])
                usecolor.outputs[0].default_value = 1
            else:
                usecolor.outputs[0].default_value = 0

        if 'Use Vertex Alpha' in self.bsdf.inputs:
            usealpha = self.make_node('ShaderNodeValue',
                                name='Use Vertex Alpha',
                                height=INPUT_NODE_HEIGHT)
            self.link(usealpha.outputs[0], self.bsdf.inputs['Use Vertex Alpha'])
            if self.alphamap:
                vmap = self.make_node('ShaderNodeAttribute',
                                    name='Vertex Alpha',
                                    xloc=txtnode.location.x,
                                    height=COLOR_NODE_HEIGHT)
                vmap.attribute_type = 'GEOMETRY'
                vmap.attribute_name = self.alphamap.name
                self.link(vmap.outputs['Color'], self.bsdf.inputs['Vertex Alpha'])
                usealpha.outputs[0].default_value = 1
            else:
                usealpha.outputs[0].default_value = 0

        self.diffuse = txtnode


    def import_subsurface(self):
        """Set up nodes for subsurface texture"""
        if 'SoftLighting' in self.textures and self.shape.textures['SoftLighting']: 
            # Have a sk separate from a specular. Make an image node.
            skimgnode = self.make_node("ShaderNodeTexImage",
                                       name='Subsurface_Texture',
                                       xloc=self.bsdf.location.x + self.img_offset_x,
                                       height=TEXTURE_NODE_HEIGHT)
            try:
                skimg = bpy.data.images.load(self.textures['SoftLighting'], check_existing=True)
                if skimg != self.diffuse.image:
                    skimg.colorspace_settings.name = "Non-Color"
                skimgnode.image = skimg
            except:
                pass
            self.link(self.texmap.outputs['Vector'], skimgnode.inputs['Vector'])
            self.link(skimgnode.outputs['Color'], self.bsdf.inputs['Subsurface'])

            v = self.make_node('ShaderNodeValue',
                                name='Subsurface Strength',
                                xloc=skimgnode.location.x,
                                height=INPUT_NODE_HEIGHT)
            v.outputs[0].default_value = self.shape.shader.Soft_Lighting
            self.link(v.outputs['Value'], self.bsdf.inputs['Subsurface Str'])


    def import_specular(self):
        """Set up nodes for specular texture"""
        if self.shape.shader.shaderflags1_test(ShaderFlags1.SPECULAR) \
                and 'Specular' in self.textures \
                    and self.shape.textures['Specular']:
            # Make the specular texture input node.
            simgnode = self.make_node("ShaderNodeTexImage",
                                      name='Specular_Texture',
                                      xloc=self.bsdf.location.x + self.img_offset_x,
                                      height=TEXTURE_NODE_HEIGHT)
            try:
                simg = bpy.data.images.load(self.textures['Specular'], check_existing=True)
                simg.colorspace_settings.name = "Non-Color"
                simgnode.image = simg
            except:
                pass
            self.link(self.texmap.outputs['Vector'], simgnode.inputs['Vector'])
            self.link(simgnode.outputs['Color'], self.bsdf.inputs['Specular'])

            c = self.make_node('ShaderNodeRGB',
                               name='Specular Color',
                               xloc=simgnode.location.x,
                               height=COLOR_NODE_HEIGHT)
            for i, v in enumerate(self.shape.shader.Spec_Color):
                c.outputs[0].default_value[i] = v
            self.link(c.outputs[0], self.bsdf.inputs['Specular Color'])

            c = self.make_node('ShaderNodeValue',
                               name='Specular Strength',
                               xloc=simgnode.location.x,
                               height=INPUT_NODE_HEIGHT)
            c.outputs[0].default_value = self.shape.shader.Spec_Str
            self.link(c.outputs[0], self.bsdf.inputs['Specular Str'])

            # if self.game in ["FO4"]:
            #     # specular combines gloss and spec
            #     invg = self.nodes.new("ShaderNodeInvert")
            #     invg.location = (self.inter2_offset_x, simgnode.location.y-50)
            #     self.link(invg.outputs['Color'], self.bsdf.inputs['Roughness'])
            #     last_node = invg

            #     try:
            #         seprgb = self.make_node("ShaderNodeSeparateColor", 
            #                                 xloc=self.inter1_offset_x,
            #                                 yloc=simgnode.location.y)
            #         seprgb.mode = 'RGB'
            #         self.link(simgnode.outputs['Color'], seprgb.inputs['Color'])
            #         spec_socket = seprgb.outputs['Red']
            #         self.link(seprgb.outputs['Green'], invg.inputs['Color'])
            #     except:
            #         seprgb = self.nodes.new("ShaderNodeSeparateRGB", 
            #                                 xloc=self.inter1_offset_x,
            #                                 yloc=simgnode.location.y)
            #         self.link(simgnode.outputs['Color'], seprgb.inputs['Image'])
            #         spec_socket = seprgb.outputs['R']
            #         self.link(seprgb.outputs['G'], invg.inputs['Color'])

            # else:
            #     # Skyrim just has a specular in the specular.
            #     spec_socket = simgnode.outputs['Color']


    def import_normal(self, shape):
        """Set up nodes for the normal map"""
        #log.debug("Handling normal map texture")
        if 'Normal' in shape.textures and shape.textures['Normal']:
            nimgnode = self.make_node("ShaderNodeTexImage",
                                      name='Normal_Texture',
                                      xloc=self.bsdf.location.x + self.img_offset_x,
                                      height=TEXTURE_NODE_HEIGHT)
            self.link(self.texmap.outputs['Vector'], nimgnode.inputs['Vector'])
            try:
                nimg = bpy.data.images.load(self.textures['Normal'], check_existing=True) 
                nimg.colorspace_settings.name = "Non-Color"
                nimgnode.image = nimg
            except:
                pass

            self.link(nimgnode.outputs['Color'], self.bsdf.inputs['Normal'])
            if self.game in ['SKYRIM', 'SKYRIMSE']:
                if not shape.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                    # Tangent normals have specular in alpha channel.
                    if 'Specular' in self.bsdf.inputs:
                        self.link(nimgnode.outputs['Alpha'], self.bsdf.inputs['Specular'])
                    elif 'Specular IOR Level' in self.bsdf.inputs:
                        self.link(nimgnode.outputs['Alpha'], self.bsdf.inputs['Specular IOR Level'])
                    

    def import_envmap(self):
        """
        Set up nodes for environment map texture. Don't know how to set it up as an actual
        environment mask so just let it hang out unconnected.
        """
        if self.shape.shader.shaderflags1_test(BSLSPShaderType.Environment_Map) \
                and 'EnvMap' in self.shape.textures \
                and self.shape.textures['EnvMap']: 
            imgnode = self.make_node("ShaderNodeTexImage",
                                     name='EnvMap_Texture',
                                     xloc=self.bsdf.location.x + self.img_offset_x,
                                     height=TEXTURE_NODE_HEIGHT)
            try:
                img = bpy.data.images.load(self.textures['EnvMap'], check_existing=True)
                if img != self.diffuse.image:
                    img.colorspace_settings.name = "Non-Color"
                imgnode.image = img
            except:
                pass
            self.link(self.texmap.outputs['Vector'], imgnode.inputs['Vector'])
            

    def import_envmask(self):
        """Set up nodes for environment mask texture."""
        if self.shape.shader.shaderflags1_test(BSLSPShaderType.Environment_Map) \
                and 'EnvMask' in self.shape.textures \
                and self.shape.textures['EnvMask']: 
            imgnode = self.make_node("ShaderNodeTexImage",
                                     name='EnvMask_Texture',
                                     xloc=self.diffuse.location.x,
                                     height=TEXTURE_NODE_HEIGHT)
            self.link(self.texmap.outputs['Vector'], imgnode.inputs['Vector'])
            try:
                img = bpy.data.images.load(self.textures['EnvMask'], check_existing=True)
                if img != self.diffuse.image:
                    img.colorspace_settings.name = "Non-Color"
                imgnode.image = img
            except:
                pass

            ## Not doing this yet. For now, just store the texture path.
            # # Env Mask multiplies with the specular.
            # spec_out = None
            # if 'Specular' in self.bsdf.inputs:
            #     spec_out = self.bsdf.inputs["Specular"].links[0].from_socket
            # elif 'Specular IOL Level' in self.bsdf.inputs:
            #     spec_out = self.bsdf.inputs["Specular IOL Level"].links[0].from_socket
            # if spec_out:
            #     bw = self.make_node("ShaderNodeRGBToBW", 
            #                         xloc=imgnode.location.x + TEXTURE_NODE_WIDTH,
            #                         yloc=imgnode.location.y)
            #     mult = self.make_node("ShaderNodeMath",
            #                         xloc=bw.location.x + NODE_WIDTH,
            #                         yloc=imgnode.location.y)
            #     self.link(imgnode.outputs['Color'], bw.inputs[0])
            #     self.link(bw.outputs[0], mult.inputs[1])
            #     self.link(spec_out, mult.inputs[0])
            #     self.link(mult.outputs[0], self.bsdf.inputs["Specular"])

            

    def import_material(self, obj, shape:NiShape):
        """
        Import the shader info from shape and create a Blender representation using shader
        nodes.
        """
        if obj.type == 'EMPTY': return 

        self.shape = shape
        self.game = shape.file.game

        self.material = bpy.data.materials.new(name=(obj.name + ".Mat"))
        self.material.use_nodes = True
        self.nodes = self.material.node_tree.nodes

        # Stash texture strings for future export
        for k, t in shape.textures.items():
            if t:
                self.material['BSShaderTextureSet_' + k] = t

        self.find_textures(shape)

        self.nodes.remove(self.nodes["Principled BSDF"])
        mo = self.nodes['Material Output']

        if self.game == 'FO4':
            self.bsdf = make_shader_fo4(self.material.node_tree, 
                (mo.location.x - NODE_WIDTH, mo.location.y))
        else:
            self.bsdf = make_shader_skyrim(self.material.node_tree,
                mo.location + Vector((-NODE_WIDTH, 0)),
                msn=shape.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS))
        
        self.bsdf.width = 250
        self.bsdf.location.x -= 100
        self.link(self.bsdf.outputs['BSDF'], 
                  self.nodes['Material Output'].inputs['Surface'])
        
        self.img_offset_x = -1.5 * TEXTURE_NODE_WIDTH
        self.calc1_offset_x = self.img_offset_x - NODE_WIDTH*2
        self.calc2_offset_x = self.img_offset_x - NODE_WIDTH
        self.inputs_offset_x = self.img_offset_x - 3*NODE_WIDTH

        self.ytop = self.bsdf.location.y
        self.inter1_offset_x += self.bsdf.location.x
        self.inter2_offset_x += self.bsdf.location.x
        self.inter3_offset_x += self.bsdf.location.x
        self.inter4_offset_x += self.bsdf.location.x

        self.make_uv_nodes()
        self.colormap, self.alphamap = get_effective_colormaps(obj.data)

        self.import_diffuse()
        self.import_subsurface()
        self.import_specular()
        self.import_normal(shape)
        self.make_input_nodes()
        self.import_envmap()
        self.import_envmask()
        self.import_shader_attrs(shape)
        self.import_shader_alpha(shape)

        obj.active_material = self.material


def set_object_textures(shape: NiShape, mat: bpy.types.Material):
    """Set the shape's textures from the value from the material's custom properties."""
    for k, v in mat.items():
        if k.startswith('BSShaderTextureSet_'):
            slot = k[len('BSShaderTextureSet_'):]
            shape.set_texture(slot, v)

    
def get_image_node(node_input):
    """Walk the shader nodes backwards until a texture node is found.
        node_input = the shader node input to follow; may be null"""
    #log.debug(f"Walking shader nodes backwards to find image: {node_input.name}")
    n = None
    if node_input and len(node_input.links) > 0: 
        n = node_input.links[0].from_node

    while n and not hasattr(n, "image"):
        #log.debug(f"Walking nodes: {n.name}")
        new_n = None
        if n.type == 'MIX':
            new_n = n.inputs[6].links[0].from_node
        if not new_n:
            for inp in ['Base Color', 'Image', 'Color', 'R', 'Red']:
                if inp in n.inputs.keys() and n.inputs[inp].is_linked:
                    new_n = n.inputs[inp].links[0].from_node
                    break
        n = new_n
    return n


def get_image_filepath(node_input):
    try:
        n = get_image_node(node_input)
        return n.image.filepath
    except:
        pass
    return ''


def has_msn_shader(obj):
    """
    Find the normal node and determine its type.
    We could just walk backwards from the Material Output, but that's inefficient.
    Instead find the normal input, either on the shader or the group node that's 
    implementing the shader.
    """
    val = False
    try:
        matoutlist = [x for x in obj.active_material.node_tree.nodes if x.bl_idname == 'ShaderNodeOutputMaterial']
        mat_out = matoutlist[0]
        surface_skt = mat_out.inputs['Surface']
        start_node = surface_skt.links[0].from_node
        if start_node.bl_idname == 'ShaderNodeGroup':
            grp_outputs = [n for n in start_node.node_tree.nodes if n.bl_idname == 'NodeGroupOutput']
            group_out = grp_outputs[0]
            start_node = group_out.inputs[0].links[0].from_node
        normlist = BD.find_node(start_node.inputs["Normal"], 'ShaderNodeNormalMap')
        val = normlist[0].space == 'OBJECT'
    except: 
        pass
    return val


class ShaderExporter:
    def __init__(self, blender_obj):
        self.obj = blender_obj
        self.is_obj_space = False
        self.have_errors = False

        self.material = None
        self.shader_node = None
        if blender_obj.active_material:
            self.material = blender_obj.active_material
            nodelist = self.material.node_tree.nodes
            if not "Material Output" in nodelist:
                log.warning(f"Have material but no Material Output for {self.material.name}")
            else:
                self.material_output = nodelist["Material Output"]
                if self.material_output.inputs['Surface'].is_linked:
                    self.shader_node = self.material_output.inputs['Surface'].links[0].from_node
                    self.is_obj_space = has_msn_shader(blender_obj)
                if not self.shader_node:
                    log.warning(f"Have material but no shader node for {self.material.name}")

            # if self.shader_node:
            #     normal_input = self.shader_node.inputs['Normal']
            #     nmap_nodes = BD.find_node(normal_input, 'ShaderNodeNormalMap')
            #     if nmap_nodes:
            #         self.is_obj_space = (nmap_nodes[0].space == 'OBJECT')
            #         # self.is_obj_space = nmap_node.name.startswith(MSN_GROUP_NAME)

        self.vertex_colors, self.vertex_alpha = get_effective_colormaps(blender_obj.data)

    def warn(self, msg):
        log.warn(msg)
        self.have_errors = True


    def export_shader_attrs(self, shape):
        try:
            if not self.material:
                return
            
            if 'BSLSP_Shader_Name' in self.material and self.material['BSLSP_Shader_Name']:
                shape.shader_name = self.material['BSLSP_Shader_Name']

            shape.shader.properties.load(self.material)
            if 'BS_Shader_Block_Name' in self.material:
                if self.material['BS_Shader_Block_Name'] == "BSLightingShaderProperty":
                    shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
                elif self.material['BS_Shader_Block_Name'] == "BSEffectShaderProperty":
                    shape.shader.properties.bufType = PynBufferTypes.BSEffectShaderPropertyBufType
                elif self.material['BS_Shader_Block_Name'] == "BSShaderPPLightingProperty":
                    shape.shader.properties.bufType = PynBufferTypes.BSShaderPPLightingPropertyBufType
                else:
                    self.warn(f"Unknown shader type: {self.material['BS_Shader_Block_Name']}")

            nl = self.material.node_tree.nodes
            if 'UV_Offset_U' in nl:
                shape.shader.properties.UV_Offset_U = nl['UV_Offset_U'].outputs['Value'].default_value
            if 'UV_Offset_V' in nl:
                shape.shader.properties.UV_Offset_V = nl['UV_Offset_V'].outputs['Value'].default_value
            if 'UV_Scale_U' in nl:
                shape.shader.properties.UV_Scale_U = nl['UV_Scale_U'].outputs['Value'].default_value
            if 'UV_Scale_V' in nl:
                shape.shader.properties.UV_Scale_V = nl['UV_Scale_V'].outputs['Value'].default_value
            
            texmode = 0
            if 'Clamp_S' in nl:
                texmode = 2 * max(min(nl['Clamp_S'].outputs['Value'].default_value, 1), 0)
            if 'Clamp_T' in nl:
                texmode += max(min(nl['Clamp_T'].outputs['Value'].default_value, 1), 0)
            shape.shader.properties.textureClampMode = int(texmode)

            shape.shader.properties.Emissive_Mult = nl['Emissive_Mult'].outputs[0].default_value
            shape.shader.properties.baseColorScale = nl['Emissive_Mult'].outputs[0].default_value
            for i in range(0, 4):
                shape.shader.properties.Emissive_Color[i] = nl['Emissive_Color'].outputs[0].default_value[i] 
                shape.shader.properties.baseColor[i] = nl['Emissive_Color'].outputs[0].default_value[i] 

            if shape.shader.blockname == "BSLightingShaderProperty":
                shape.shader.Alpha = self.shader_node.inputs['Alpha'].default_value
                shape.shader.Glossiness = nl['Glossiness'].outputs['Value'].default_value

            shape.save_shader_attributes()
            
        except:
            self.warn("Could not determine shader attributes")


    # def get_diffuse(self):
    #     """Get the diffuse filepath, given the material's shader node."""
    #     try:
    #         # imgnode = get_image_node(self.shader_node.inputs['Base Color'])
    #         imgnode = self.material.node_tree.nodes['Diffuse_Texture']
    #         return imgnode.image.filepath
    #     except:
    #         self.warn("Could not find diffuse filepath")
    #     return ''
    

    # def get_normal(self):
    #     """
    #     Get the normal map filepath, given the shader node.
    #     """
    #     try:
    #         image_node = find_node(self.bsdf.inputs['Normal'], "ShaderNodeTexImage")
    #         normalmap = find_node(self.bsdf.inputs['Normal'], "ShaderNodeNormalMap")
    #         image_node = self.material.node_tree.nodes['Normal_Texture']
    #         return image_node.image.filepath
    #     except:
    #         self.warn("Could not find normal filepath")
    #     return ''
    

    # def get_subsurface(self):
    #     try:
    #         if 'Subsurface_Texture' in self.material.node_tree.nodes:
    #             return self.material.node_tree.nodes['Subsurface_Texture'].image.filepath
    #         # if self.is_obj_space:
    #         #     return get_image_filepath(self.shader_node.inputs['Specular'])
    #     except:
    #         self.warn("Could not find subsurface texture filepath")
    #     return ''


    # def get_specular(self):
    #     try:
    #         if 'Specular_Texture' in self.material.node_tree.nodes:
    #             return self.material.node_tree.nodes['Specular_Texture'].image.filepath
    #         # if self.is_obj_space:
    #         #     return get_image_filepath(self.shader_node.inputs['Specular'])
    #     except:
    #         self.warn("Could not find specular filepath")
    #     return ''


    @property
    def is_effectshader(self):
        try:
            return self.material['BS_Shader_Block_Name'] == 'BSEffectShaderProperty'
        except:
            pass
        return False
    

    def write_texture(self, shape, textureslot:str):
        """
        Write the given texture slot to the nif shape.
        """
        foundpath = ""
        imagenode = None
        if textureslot == "EnvMap":
            if "EnvMap_Texture" in self.material.node_tree.nodes:
                imagenode = self.material.node_tree.nodes["EnvMap_Texture"]
        elif textureslot == "EnvMask":
            if "EnvMask_Texture" in self.material.node_tree.nodes:
                imagenode = self.material.node_tree.nodes["EnvMask_Texture"]
        elif textureslot == "SoftLighting":
            # Subsurface is hidden behind mixnodes in 4.0 so just grab the node by name.
            # Maybe we should just do this for all texture layers.
            if "SoftLighting_Texture" in self.material.node_tree.nodes:
                imagenode = self.material.node_tree.nodes["SoftLighting_Texture"]
            elif 'Subsurface Color' in self.shader_node.inputs:
                imagenodes = BD.find_node(self.shader_node.inputs["Subsurface Color"], "ShaderNodeTexImage")
                if imagenodes: imagenode = imagenodes[0]
        elif textureslot == "Specular":
            if "Specular_Texture" in self.material.node_tree.nodes:
                imagenode = self.material.node_tree.nodes["Specular_Texture"]
            else:
                # Don't have an obvious texture node, walk the BSDF inputs backwards.
                if "Specular" in self.shader_node.inputs:
                    imagenodes = BD.find_node(self.shader_node.inputs["Specular"], "ShaderNodeTexImage")
                elif "Specular IOR Level" in self.shader_node.inputs:
                    imagenodes = BD.find_node(self.shader_node.inputs["Specular IOR Level"], "ShaderNodeTexImage")
                if imagenodes: imagenode = imagenodes[0]
        elif textureslot == "Diffuse":
            try:
                imagenodes = BD.find_node(self.shader_node.inputs["Base Color"], "ShaderNodeTexImage")
            except:
                imagenodes = BD.find_node(self.shader_node.inputs["Diffuse"], "ShaderNodeTexImage")
            if imagenodes: imagenode = imagenodes[0]
        else:
            # Look through the node tree behind the texture slot to find the right image
            # node.
            imagenodes = BD.find_node(self.shader_node.inputs[textureslot], "ShaderNodeTexImage")
            if imagenodes: imagenode = imagenodes[0]
        
        if imagenode:
            if textureslot == 'Specular':
                # Check to see if the specular is coming from the normal texture. If so,
                # don't use it.
                normnodes = BD.find_node(self.shader_node.inputs["Normal"], "ShaderNodeTexImage")
                if normnodes and normnodes[0] == imagenode:
                    return
                
            try:
                foundpath = imagenode.image.filepath
                fplc = Path(foundpath.lower())
                if fplc.drive.endswith('textures'):
                    txtindex = 0
                else:
                    txtindex = fplc.parts.index('textures')
                fp = Path(foundpath)
                relpath = Path(*fp.parts[txtindex:])
                shape.set_texture(textureslot, str(relpath.with_suffix('.dds')))
            except ValueError:
                self.warn(f"No 'textures' folder found in path: {foundpath}")
            except Exception as e:
                self.warn(f"Texture image in block {imagenode.name} not usable.")
        else:
            self.warn(f"Could not find image shader node for {textureslot} layer.")


    def export_textures(self, shape: NiShape):
        """Create shader in nif from the blender object's material"""
        # Use textures stored in properties as defaults; override them with shader nodes
        set_object_textures(shape, self.material)

        if not self.shader_node: return

        for textureslot in ['Diffuse', 'Normal', 'SoftLighting', 'Specular', 
                            'EnvMap', 'EnvMask']:
            self.write_texture(shape, textureslot)

        # Write alpha if any after the textures
        try:
            alpha_input = self.shader_node.inputs['Alpha']
            if alpha_input and alpha_input.is_linked \
                and alpha_input.links[0].from_node.bl_idname == 'ShaderNodeTexImage' \
                and self.material:
                shape.has_alpha_property = True
                if 'NiAlphaProperty_flags' in self.material:
                    shape.alpha_property.flags = self.material['NiAlphaProperty_flags']
                else:
                    shape.alpha_property.flags = 4844
                shape.alpha_property.threshold = int(self.material.alpha_threshold * 255)
                shape.save_alpha_property()
        except:
            self.warn("Could not determine alpha property")


    def export(self, new_shape:NiShape):
        """Top-level routine for exporting a shape's texture attributes."""
        if not self.material: return

        self.export_shader_attrs(new_shape)
        self.export_textures(new_shape)
        if self.is_obj_space:
            new_shape.shader.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
        else:
            new_shape.shader.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)

        #log.debug(f"Exporting vertex color flag: {self.vertex_colors}")
        if self.vertex_colors:
            new_shape.shader.shaderflags2_set(ShaderFlags2.VERTEX_COLORS)
        else:
            new_shape.shader.shaderflags2_clear(ShaderFlags2.VERTEX_COLORS)

        if self.vertex_alpha:
            new_shape.shader.shaderflags1_set(ShaderFlags1.VERTEX_ALPHA)
        else:
            new_shape.shader.shaderflags1_clear(ShaderFlags1.VERTEX_ALPHA)
            
        new_shape.save_shader_attributes()

        if self.have_errors:
            log.warn(f"Shader nodes are not set up for export to nif. Check and fix in generated nif file.")

