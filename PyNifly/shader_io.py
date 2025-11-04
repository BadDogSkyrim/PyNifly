"""Shader Import/Export for pyNifly"""

# Copyright © 2021, Bad Dog.

import os
from pathlib import Path
import logging
import traceback
from contextlib import suppress
import bpy
from pynifly import *
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
import blender_defs as BD
from nifdefs import ShaderFlags1, ShaderFlags2, ShaderFlags1FO4, ShaderFlags2FO4
from niflytools import find_referenced_file

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
HORIZONTAL_GAP = 50
VERTICAL_GAP = 50
NORMAL_SCALE = 1.0 # Possible to make normal more obvious
POS_TOP = 0
POS_MIDDLE = 1
POS_BOTTOM = 2
POS_BELOW = 3
POS_LEFT = 0
POS_RIGHT = 1

# Equivalent nodes that have different names in different versions of blender. Fuckers.
MIXNODE_IDNAME = 'ShaderNodeMix'
MIXNODE_IN1 = 'A'
MIXNODE_IN2 = 'B'
MIXNODE_FACTOR = 'Factor'
MIXNODE_OUT = 'Result'

COMBINER_IDNAME = 'ShaderNodeCombineColor'
COMBINER_OUT = 'Result'

SEPARATOR_IDNAME = 'ShaderNodeSeparateColor'
SEPARATOR_IN = 'Color'
SEPARATOR_OUT1 = 'Red'
SEPARATOR_OUT2 = 'Green'
SEPARATOR_OUT3 = 'Blue'

# Do not store these shader attributes as properties on the object--they are in the shader.
NISHADER_IGNORE = [
    'baseColor',
    'baseColorScale',
    'bufSize', 
    'bufType', 
    'bBSLightingShaderProperty',
    'controllerID', 
    'Emissive_Color',
    'Emissive_Mult',
    'Glossiness',
    'greyscaleTexture',
    'nameID', 
    'sourceTexture',
    'UV_Offset_U',
    'UV_Offset_V',
    'UV_Scale_U',
    'UV_Scale_V',
    'textureClampMode'
    ]

shader_node_height = {
    'ShaderNodeTexImage': 271,
    'ShaderNodeMapRange': 241,
    'ShaderNodeMath': 148,
    'ShaderNodeValue': 79,
    'ShaderNodeAttribute': 170,
    'ShaderNodeGroup': 200,
}


shader_group_nodes = {
    'SkyrimShader:Face': "Alpha Mult",
    'SkyrimShader:Default - MSN': "Alpha Mult", 
    'SkyrimShader:Effect': "Alpha Adjust", 
    'SkyrimShader:Default - TSN': "Alpha Mult",
    "Fallout 4 MTS": "Alpha Mult", 
    "Fallout 4 Effect": "Alpha", # may be wrong
    "Fallout 4 MTS - Face": "Alpha Mult"
}


def get_alpha_input(mat):
    """
    Different shaders have different names. Return the Fallout OR SkyrimShader:Default, TSN, MSN,
    or effect shader. Return the alpha input node for the shader.
    """
    if mat: 
        for n in mat.node_tree.nodes:
            if n.name in shader_group_nodes:
                return n.name, shader_group_nodes[n.name]
        
    return "", ""
            

def relative_loc(nodelist, xpos=POS_RIGHT, vpos=POS_BOTTOM):
    """
    Calculate a location relative to the given node list: to the right of the rightmost
    and at the same level as the lowest.
    """
    maxx = -10000
    minx = 10000
    maxy = -10000
    miny = lowy = 10000
    for n in nodelist:
        maxx = max(maxx, n.location.x + n.width + HORIZONTAL_GAP)
        minx = min(minx, n.location.x)
        maxy = max(maxy, n.location.y)
        miny = min(miny, n.location.y)
        h = shader_node_height[n.bl_idname]
        lowy = min(lowy, n.location.y - h - VERTICAL_GAP)

    if xpos == POS_RIGHT:
        x = maxx
    else:
        x = minx
    if vpos == POS_TOP:
        y = maxy
    elif vpos == POS_BOTTOM:
        y = miny
    elif vpos == POS_BELOW:
        y = lowy
    else:
        y = miny + (maxy-miny)/2 - 100

    return Vector((x, y))


def reposition(node, vpos=POS_BOTTOM, xpos=POS_RIGHT, padding=Vector((0, 0)), reference=None):
    """
    Reposition a node relative to the reference node, or to its own inputs.
    """
    n = reference
    if not n: n = node
    inputlist = []
    for inp in n.inputs:
        if inp.is_linked:
            fn = inp.links[0].from_node
            if fn != node: inputlist.append(fn)
    node.location = relative_loc(inputlist, xpos=xpos, vpos=vpos) + padding


def make_separator(nodetree, input, loc):
    """
    Make a color separator node with input connected to socket "input".
    Safe for all Blender 3.x and 4.0
    """
    global SEPARATOR_IDNAME 
    global SEPARATOR_IN 
    global SEPARATOR_OUT1 
    global SEPARATOR_OUT2 
    global SEPARATOR_OUT3 
    try:
        rgbsep = nodetree.nodes.new(SEPARATOR_IDNAME)
    except:
        SEPARATOR_IDNAME = 'ShaderNodeSeparateRGB'
        SEPARATOR_IN = 'Image'
        SEPARATOR_OUT1 = 'R'
        SEPARATOR_OUT2 = 'G'
        SEPARATOR_OUT3 = 'B'
        rgbsep = nodetree.nodes.new(SEPARATOR_IDNAME)

    try:
        rgbsep.mode = 'RGB'
    except:
        pass

    rgbsep.location = loc
    nodetree.links.new(input, rgbsep.inputs[SEPARATOR_IN])
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
    m = make_mixnode(nodetree, source, strength, skt, location=location)

    nodetree.links.new(color, bsdf.inputs['Specular Tint'])
   

def make_combiner(nodetree, r, g, b, loc):
    """
    Make a combiner node with inputs from sockets r, g, b. Returns created node.
    Safe for all Blender 3.x and 4.0

    b can be a socket or float value.
    """
    global COMBINER_IDNAME
    global COMBINER_OUT
    try:
        combiner = nodetree.nodes.new(COMBINER_IDNAME)
    except:
        COMBINER_IDNAME = 'ShaderNodeCombineRGB'
        COMBINER_OUT = 'Value'
        combiner = nodetree.nodes.new(COMBINER_IDNAME)

    combiner.location = loc
    try:
        combiner.mode = 'RGB'
    except:
        pass

    nodetree.links.new(r, combiner.inputs[0])
    nodetree.links.new(g, combiner.inputs[1])
    try:
        nodetree.links.new(b, combiner.inputs[2])
    except:
        combiner.inputs[2].default_value = b
    return combiner


def make_combiner_xyz(nodetree, x, y, z, loc):
    """
    Make a combiner node with inputs from sockets x, y, z. Returns created node.
    Safe for all Blender 3.x and 4.0
    """
    combiner = nodetree.nodes.new('ShaderNodeCombineXYZ')
    combiner.location = loc

    nodetree.links.new(x, combiner.inputs[0])
    nodetree.links.new(y, combiner.inputs[1])
    if z: nodetree.links.new(z, combiner.inputs[2])
    return combiner


def append_groupnode(parent, name, label, shader_path, location=None):
    """
    Load a group node from the assets file.
    """
    g = bpy.data.node_groups.get(name)
    if not g:
        with bpy.data.libraries.load(shader_path) as (data_from, data_to):
            data_to.node_groups = [name]
        g = data_to.node_groups[0]

    shader_node = parent.nodes.new('ShaderNodeGroup')
    shader_node.label = label
    shader_node.name = name
    if location: shader_node.location = location
    shader_node.node_tree = g

    return shader_node


def make_shader_skyrim(parent, shader_path, location, 
                       msn=False, facegen=False, effect_shader=False, 
                       colormap_name='Col'):
    """
    Returns a group node implementing a shader for Skyrim.
    """
    # Get the shader from the assets file. If that fails, build it here.
    try: 
        if facegen:
            shader_node = append_groupnode(parent, "SkyrimShader:Face", "SkyrimShader:Face", shader_path, location)
        elif effect_shader:
            shader_node = append_groupnode(parent, "SkyrimShader:Effect", "SkyrimShader:Effect", shader_path, location)
        else:
            shader_node = append_groupnode(parent, "SkyrimShader:Default", "SkyrimShader:Default", shader_path, location)
        if "MSN" in shader_node.inputs.keys():
            shader_node.inputs["MSN"].default_value = bool(msn)

        return shader_node
    
    except Exception as e:
        log.warning(f"Could not load shader from assets file: {traceback.format_exc()}; building nodes directly")
        

    grp = bpy.data.node_groups.new(type='ShaderNodeTree', name='SkyrimShader')

    group_inputs = grp.nodes.new('NodeGroupInput')
    group_inputs.location = (-6*NODE_WIDTH, -0.5 * TEXTURE_NODE_HEIGHT)
    try:
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
        grp.inputs.new('NodeSocketColor', 'Emission Color')
        grp.inputs.new('NodeSocketFloat', 'Emission Strength')
    except:
        # Blender 4.0
        grp.interface.new_socket('Diffuse', in_out='INPUT', socket_type='NodeSocketColor')
        if facegen:
            for i in range(0, 3):
                s = grp.interface.new_socket(f'Tint {i+1}', in_out='INPUT', socket_type='NodeSocketFloat')
                s.default_value = 0
                grp.interface.new_socket(f'Tint {i+1} Color', in_out='INPUT', socket_type='NodeSocketColor')
                s = grp.interface.new_socket(f'Tint {i+1} Strength', in_out='INPUT', socket_type='NodeSocketFloat')
                s.default_value = 1.0
                s.min_value = 0.0
                s.max_value = 1.0
        s = grp.interface.new_socket('Alpha', in_out='INPUT', socket_type='NodeSocketFloat')
        s.default_value = 1.0
        s.min_value = 0.0
        s.max_value = 1.0
        s = grp.interface.new_socket('Alpha Mult', in_out='INPUT', socket_type='NodeSocketFloat')
        s.default_value = 1.0
        s.min_value = 0.0
        s.max_value = 1.0
        grp.interface.new_socket('Vertex Color', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Vertex Alpha', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Subsurface', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Subsurface Str', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Specular', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Specular Color', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Specular Str', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Normal', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Glossiness', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Emission Color', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Emission Strength', in_out='INPUT', socket_type='NodeSocketFloat')

    # Shader output node
    bsdf = grp.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (NODE_WIDTH*3, 0)

    # Diffuse includes vertex colors
    mixcolor = make_mixnode(
        grp, 
        group_inputs.outputs['Diffuse'],
        group_inputs.outputs['Vertex Color'],
        bsdf.inputs['Base Color'],
        factor=group_inputs.outputs['Use Vertex Color'],
        location=group_inputs.location + Vector((2 * NODE_WIDTH, 2*TEXTURE_NODE_HEIGHT,))
        )

    diffuse_socket = mixcolor.outputs[MIXNODE_OUT]
    
    if facegen:
        for i in range(0, 3):
            str = make_mixnode(grp,
                            group_inputs.outputs[i*3+1], # tint
                            group_inputs.outputs[i*3+3], # tint strength
                            blend_type='MULTIPLY',
                            location=group_inputs.location + 
                                Vector((NODE_WIDTH*(i+3), TEXTURE_NODE_HEIGHT*(4-i),))
                            )
            mix = make_mixnode(grp,
                            diffuse_socket,
                            group_inputs.outputs[i*3+2],
                            factor=str.outputs[MIXNODE_OUT], 
                            blend_type='MIX',
                            location=group_inputs.location + 
                                Vector((NODE_WIDTH*(i+4), TEXTURE_NODE_HEIGHT*(4-i),))
                            )
            diffuse_socket = mix.outputs[MIXNODE_OUT]

    invalph = grp.nodes.new('ShaderNodeMath')
    invalph.location = mixcolor.location + Vector((0, -TEXTURE_NODE_HEIGHT))
    invalph.operation = 'SUBTRACT'
    invalph.inputs[0].default_value = 1.0

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
    if 'Subsurface Weight' in bsdf.inputs:
        grp.links.new(group_inputs.outputs['Subsurface Str'], bsdf.inputs["Subsurface Weight"])
    else:
        grp.links.new(group_inputs.outputs['Subsurface Str'], bsdf.inputs["Subsurface"])

    if "Subsurface Color" in bsdf.inputs:
        # If there's a color input, connect to that.
        specsat = grp.nodes.new('ShaderNodeHueSaturation')
        specsat.location = invalph.location + Vector((NODE_WIDTH, -COLOR_NODE_HEIGHT))
        grp.links.new(group_inputs.outputs['Subsurface Str'], specsat.inputs['Saturation'])
        grp.links.new(group_inputs.outputs['Subsurface'], specsat.inputs['Color'])

        grp.links.new(specsat.outputs['Color'], bsdf.inputs["Subsurface Color"])
    else:
        # No color input. Let the shader do the scattering, but mix the subsurface
        # color with the base color.
        m = make_mixnode(
            grp, 
            diffuse_socket,
            group_inputs.outputs['Subsurface'],
            bsdf.inputs['Base Color'],
            blend_type='MIX',
            location=invalph.location + Vector((5*NODE_WIDTH, -COLOR_NODE_HEIGHT)))
        m.inputs[MIXNODE_FACTOR].default_value = 0.1

    try:
        grp.links.new(group_inputs.outputs['Subsurface'], bsdf.inputs['Subsurface Radius'])
        bsdf.inputs['Subsurface Scale'].default_value = 2 # Reduce for scaled-down meshes
    except:
        pass

    # Specular 
    make_specular(grp,
                  group_inputs.outputs['Specular'],
                  group_inputs.outputs['Specular Str'],
                  group_inputs.outputs['Specular Color'],
                  bsdf,
                  mixcolor.location + Vector((0, -2.2*TEXTURE_NODE_HEIGHT)))

    # Glossiness
    map = grp.nodes.new('ShaderNodeMapRange')
    map.location = group_inputs.location + Vector((3 * NODE_WIDTH, -0.8 * TEXTURE_NODE_HEIGHT))
    map.inputs['From Min'].default_value = 0
    map.inputs['From Max'].default_value = 200
    map.inputs['To Min'].default_value = 1
    map.inputs['To Max'].default_value = 0
    grp.links.new(group_inputs.outputs['Glossiness'], map.inputs['Value'])
    grp.links.new(map.outputs[0], bsdf.inputs['Roughness'])

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
    if 'Emission' in bsdf.inputs:
        grp.links.new(group_inputs.outputs['Emission Color'], bsdf.inputs['Emission'])
    else:
        grp.links.new(group_inputs.outputs['Emission Color'], bsdf.inputs['Emission Color'])
    grp.links.new(group_inputs.outputs['Emission Strength'], bsdf.inputs['Emission Strength'])

    # Group outpts

    group_outputs = grp.nodes.new('NodeGroupOutput')
    group_outputs.location = (bsdf.location.x + NODE_WIDTH*2, 0)
    try:
        grp.outputs.new('NodeSocketShader', 'BSDF')
    except:
        # Blender 4.0
        grp.interface.new_socket('BSDF', in_out='OUTPUT', socket_type='NodeSocketShader')
    grp.links.new(bsdf.outputs['BSDF'], group_outputs.inputs['BSDF'])

    shader_node = parent.nodes.new('ShaderNodeGroup')
    shader_node.name = shader_node.label = ('Skyrim Face Shader' if facegen else 'SkyrimShader:Default')
    shader_node.location = location
    shader_node.node_tree = grp

    return shader_node


def make_shader_fo4(parent, shader_path, location, facegen=True, effect_shader=False):
    """
    Returns a group node implementing a shader for FO4.

    facegen == true: shader includes tint layers
    effect_shader == true: Modeling a BSEffectShaderProperty
    """
    try:
        shadername = shaderlabel = "Fallout 4 MTS"
        if effect_shader:
            shadername = "Fallout 4 Effect"
            shaderlabel = "FO4 Effect Shader"
        elif facegen:
            shadername = "Fallout 4 MTS - Face"  
            shaderlabel = "FO4 Face Shader"

        shader_node = append_groupnode(parent, shadername, shaderlabel, shader_path, location)

        return shader_node
    
    except Exception as e:
        log.warn(f"Could not load shader from assets file: {traceback.format_exc()}; building nodes directly")

    grp = bpy.data.node_groups.new(type='ShaderNodeTree', name='FO4Shader')

    group_inputs = grp.nodes.new('NodeGroupInput')
    group_inputs.location = (-NODE_WIDTH*2, 0)
    try:
        grp.inputs.new('NodeSocketColor', 'Diffuse')
        if facegen:
            for i in range(0, 3):
                n = grp.inputs.new('NodeSocketFloat', f'Tint {i+1}')
                n.default_value = 0.0
                grp.inputs.new('NodeSocketColor', f'Tint {i+1} Color')
                n = grp.inputs.new('NodeSocketFloat', f'Tint {i+1} Strength')
                n.default_value = 1.0
                n.min_value = 0.0
                n.max_value = 1.0
        grp.inputs.new('NodeSocketColor', 'Specular')
        grp.inputs.new('NodeSocketColor', 'Specular Color')
        grp.inputs.new('NodeSocketColor', 'Specular Str')
        grp.inputs.new('NodeSocketColor', 'Normal')
        n = grp.inputs.new('NodeSocketFloat', 'Alpha')
        n.default_value = 1.0
        n = grp.inputs.new('NodeSocketFloat', 'Alpha Mult')
        n.default_value = 1.0
        n = grp.inputs.new('NodeSocketColor', 'Emission Color')
        n.default_value = 0
        n = grp.inputs.new('NodeSocketFloat', 'Emission Strength')
        n.default_value = 0
    except:
        grp.interface.new_socket('Diffuse', in_out='INPUT', socket_type='NodeSocketColor')
        if facegen:
            for i in range(0, 3):
                s = grp.interface.new_socket(f'Tint {i+1}', in_out='INPUT', socket_type='NodeSocketFloat')
                s.default_value = 0
                grp.interface.new_socket(f'Tint {i+1} Color', in_out='INPUT', socket_type='NodeSocketColor')
                s = grp.interface.new_socket(f'Tint {i+1} Strength', in_out='INPUT', socket_type='NodeSocketFloat')
                s.default_value = 1.0
                s.min_value = 0.0
                s.max_value = 1.0
        grp.interface.new_socket('Specular', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Specular Color', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Specular Str', in_out='INPUT', socket_type='NodeSocketColor')
        grp.interface.new_socket('Normal', in_out='INPUT', socket_type='NodeSocketColor')
        s.default_value = 1.0
        s = grp.interface.new_socket('Alpha Mult', in_out='INPUT', socket_type='NodeSocketFloat')
        s.default_value = 1.0
        s = grp.interface.new_socket('Emission Color', in_out='INPUT', socket_type='NodeSocketColor')
        s.default_value = (0,0,0,0,)
        s = grp.interface.new_socket('Emission Strength', in_out='INPUT', socket_type='NodeSocketFloat')
        s.default_value = 0

    # Create tint layer mixnodes if needed
    diffuse_source = group_inputs.outputs['Diffuse']
    if facegen:
        for i in range(0, 3):
            str = make_mixnode(grp,
                            group_inputs.outputs[i*3+1], # tint
                            group_inputs.outputs[i*3+3], # tint strength
                            blend_type='MULTIPLY',
                            location=(NODE_WIDTH*i, TEXTURE_NODE_HEIGHT*(3-i),)
                            )
            mix = make_mixnode(grp,
                            diffuse_source,
                            group_inputs.outputs[i*3+2],
                            factor=str.outputs[MIXNODE_OUT], 
                            blend_type='MIX',
                            location=(NODE_WIDTH*(i+1), TEXTURE_NODE_HEIGHT*(3-i),)
                            )
            diffuse_source = mix.outputs[MIXNODE_OUT]

    # Shader output node
    bsdf = grp.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (NODE_WIDTH * 4, 0)
    grp.links.new(diffuse_source, bsdf.inputs['Base Color'])
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

    # Normal map
    separator = make_separator(grp, group_inputs.outputs['Normal'], (0, -1.5 * TEXTURE_NODE_HEIGHT))

    inv = grp.nodes.new("ShaderNodeInvert")
    inv.location = (NODE_WIDTH, separator.location.y-50)
    grp.links.new(separator.outputs[SEPARATOR_OUT2], inv.inputs['Color'])

    combiner = make_combiner(
        grp, 
        separator.outputs[SEPARATOR_OUT1], 
        inv.outputs[0], 
        1.0,
        (NODE_WIDTH * 2, separator.location.y))
    
    norm = grp.nodes.new('ShaderNodeNormalMap')
    norm.location = (NODE_WIDTH * 3, separator.location.y)
    grp.links.new(combiner.outputs[0], norm.inputs['Color'])
    grp.links.new(norm.outputs['Normal'], bsdf.inputs['Normal'])

    group_outputs = grp.nodes.new('NodeGroupOutput')
    group_outputs.location = (bsdf.location.x + NODE_WIDTH*2, 0)
    try:
        grp.outputs.new('NodeSocketShader', 'BSDF')
    except:
        grp.interface.new_socket('BSDF', in_out='OUTPUT', socket_type='NodeSocketShader')
    grp.links.new(bsdf.outputs['BSDF'], group_outputs.inputs['BSDF'])

    shader_node = parent.nodes.new('ShaderNodeGroup')
    shader_node.name = shader_node.label = ('FO4 Face Shader' if facegen else 'FO4 Shader')
    shader_node.location = location
    shader_node.node_tree = grp

    return shader_node


def make_uv_node(parent, shader_path, location):
    """
    Returns a group node for handling shader UV attributes: U/V origin, scale, and clamp
    mode.
    parent = parent node tree to contain the new node.
    """
    try: 
        shader_node = append_groupnode(parent, "UV_Converter", "UV_Converter", shader_path, location)
        return shader_node
    except:
        pass

    grp = bpy.data.node_groups.new(type='ShaderNodeTree', name='UV_Converter')

    group_inputs = grp.nodes.new('NodeGroupInput')
    group_inputs.location = (-200, 0)
    try:
        grp.inputs.new('NodeSocketFloat', 'Offset U')
        grp.inputs.new('NodeSocketFloat', 'Offset V')
        grp.inputs.new('NodeSocketFloat', 'Scale U')
        grp.inputs.new('NodeSocketFloat', 'Scale V')
        grp.inputs.new('NodeSocketInt', 'Wrap U')
        grp.inputs.new('NodeSocketInt', 'Wrap V')
    except:
        grp.interface.new_socket('Offset U', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Offset V', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Scale U', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Scale V', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Wrap U', in_out='INPUT', socket_type='NodeSocketFloat')
        grp.interface.new_socket('Wrap V', in_out='INPUT', socket_type='NodeSocketFloat')

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

    u_comb = make_mixnode(
        grp, 
        u_map.outputs['Result'],
        u_scale.outputs['Value'],
        factor=group_inputs.outputs['Wrap S'],
        blend_type='MIX',
        location=(u_map.location.x + 200, u_scale.location.y - 50))

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

    v_comb = make_mixnode(
        grp,
        v_map.outputs['Result'],
        v_scale.outputs['Value'],
        factor=group_inputs.outputs['Wrap T'],
        blend_type='MIX',
        location=(v_map.location.x + 200, v_scale.location.y - 50)
    )

    # Combine U & V
    uv_comb = make_combiner_xyz(
        grp,
        u_comb.outputs[MIXNODE_OUT],
        v_comb.outputs[MIXNODE_OUT],
        None,
        v_comb.location + Vector((NODE_WIDTH, 50))
    )

    group_outputs = grp.nodes.new('NodeGroupOutput')
    group_outputs.location = (uv_comb.location.x + 200, 0)
    try:
        grp.outputs.new('NodeSocketVector', 'Vector')
    except:
        grp.interface.new_socket('Vector', in_out='OUTPUT', socket_type='NodeSocketVector')

    grp.links.new(uv_comb.outputs['Vector'], group_outputs.inputs['Vector'])

    shader_node = parent.new('ShaderNodeGroup')
    shader_node.name = shader_node.label = 'UV_Converter'
    shader_node.location = location
    shader_node.node_tree = grp

    return shader_node


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
        
    if colormap and colormap.name == ALPHA_MAP_NAME:
        alphamap = colormap
        colormap = None
        for vc in vertcolors:
            if vc.name != ALPHA_MAP_NAME:
                colormap = vc
                break

    if not alphamap:
        alphamap = vertcolors.get(ALPHA_MAP_NAME)

    return colormap, alphamap


def make_mixnode(nodetree, input1, input2, output=None, factor=1.0, 
                 blend_type='MULTIPLY', location=None):
    """
    Create a shader RGB mix node--or fall back if it's an older version of Blender.
    """
    global MIXNODE_IDNAME 
    global MIXNODE_IN1 
    global MIXNODE_IN2 
    global MIXNODE_FACTOR 
    global MIXNODE_OUT 
    mixnode = None
    try:
        mixnode = nodetree.nodes.new(MIXNODE_IDNAME)
    except:
        # Fall back to older names
        MIXNODE_IDNAME = 'ShaderNodeMixRGB'
        MIXNODE_IN1 = 'Color1'
        MIXNODE_IN2 = 'Color2'
        MIXNODE_OUT = 'Color'
        MIXNODE_FACTOR = 'Fac'
        mixnode = nodetree.nodes.new(MIXNODE_IDNAME)

    try:
        mixnode.data_type = 'RGBA'
    except: 
        pass

    nodetree.links.new(input1, mixnode.inputs[MIXNODE_IN1])
    inputlist = [input1.node]
    try:
        nodetree.links.new(input2, mixnode.inputs[MIXNODE_IN2])
        inputlist.append(input2.node)
    except:
        for i, v in enumerate(input2):
            mixnode.inputs[MIXNODE_IN2].default_value[i] = v
    if output: 
        nodetree.links.new(mixnode.outputs[MIXNODE_OUT], output)
    mixnode.blend_type = blend_type
    try:
        nodetree.links.new(factor, mixnode.inputs[MIXNODE_FACTOR])
        inputlist.append(factor.node)
    except:
        mixnode.inputs[MIXNODE_FACTOR].default_value = factor
    
    if location: 
        mixnode.location = location
    else:
        mixnode.location = relative_loc(inputlist)

    return mixnode


def make_maprange(nodetree, in_value=None, 
                  in_from_min=None, in_from_max=None,
                  in_to_min=None, in_to_max=None, 
                  location=None,
                  neighbor=None):
    """
    Create a map range node. Min/max values can be numbers or links from another node.
    """
    nodelist = []
    node = nodetree.nodes.new("ShaderNodeMapRange")
    if in_value: 
        nodetree.links.new(in_value, node.inputs['Value'])
        nodelist.append(in_value.node)
    if in_from_min: 
        try:
            nodetree.links.new(in_from_min, node.inputs['From Min'])
            nodelist.append(in_from_min)
        except:
            node.inputs['From Min'].default_value = in_from_min
    if in_from_max: 
        try:
            nodetree.links.new(in_from_max, node.inputs['From Max'])
            nodelist.append(in_from_max)
        except:
            node.inputs['From Max'].default_value = in_from_max
    if in_to_min: 
        try:
            nodetree.links.new(in_to_min, node.inputs['To Min'])
            nodelist.append(in_to_min)
        except:
            node.inputs['To Min'].default_value = in_to_min
    if in_to_max: 
        try:
            nodetree.links.new(in_to_max, node.inputs['To Max'])
            nodelist.append(in_to_max)
        except:
            node.inputs['To Max'].default_value = in_to_max

    if neighbor:
        node.location = neighbor.location + Vector((neighbor.width + HORIZONTAL_GAP, 0))
    elif location: 
        node.location = location
    else:
        node.location = relative_loc(nodelist)

    return node


def make_mathnode(nodetree, 
                  op="MULTIPLY",
                  value1=None, 
                  value2=None,  
                  location=None,
                  neighbor=None):
    """
    Create a math node
    """
    nodelist = []
    node = nodetree.nodes.new("ShaderNodeMath")
    node.operation = op
    if value1: 
        nodetree.links.new(value1, node.inputs[0])
        nodelist.append(value1.node)
    if value2: 
        nodetree.links.new(value2, node.inputs[1])
        nodelist.append(value2.node)

    node.location = relative_loc(nodelist)

    return node


class ShaderImporter:
    def __init__(self):
        """
        Machinery to handle importing shaders. 
        * Logger: implements a "warn" routine to report problems.
        """
        self.material = None
        self.shape = None
        self.colormap = None
        self.alphamap = None
        self.vertex_alpha = None
        self.bsdf = None
        self.nodes = None
        self.textures = {}
        self.diffuse = None
        self.diffuse_socket = None
        self.game = None
        self.do_specular = False
        self.asset_path = False
        self.is_lighting_shader = True
        self.is_effect_shader = False
        self.logger = logging.getLogger("pynifly")

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
        self.gap_x = 40
        self.gap_y = 10
        self.xloc = 0
        self.yloc = 0
        self.ytop = 0
        self.bsdf_xadjust = 0

    
    @property 
    def emission_color_skt(self):
        if 'Emission Color' in self.bsdf.inputs:
            return self.bsdf.inputs['Emission Color']
        if 'Emission' in self.bsdf.inputs:
            return self.bsdf.inputs['Emission']
        

    def warn(self, msg):
        self.logger.warning(msg)


    def import_shader_attrs(self, shape:NiShape):
        """
        Import the shader attributes associated with the shape. All attributes are stored
        as properties on the material; attributes that have Blender equivalents are used
        to set up Blender nodes and properties.
        """
        shader:NiShader = shape.shader

        try:
            shader.properties.extract(self.material, ignore=NISHADER_IGNORE, game=self.game)

            self.material['BS_Shader_Block_Name'] = shader.blockname
            self.material['BSLSP_Shader_Name'] = shader.name

            self.bsdf.inputs['Emission Color'].default_value = shader.properties.Emissive_Color[:]
            self.bsdf.inputs['Emission Strength'].default_value = shader.properties.Emissive_Mult

            if (self.is_lighting_shader and 'Glossiness' in self.bsdf.inputs):
                self.bsdf.inputs['Glossiness'].default_value = shader.properties.Glossiness

            self.texmap.inputs['Offset U'].default_value = shape.shader.properties.UV_Offset_U
            self.texmap.inputs['Offset V'].default_value = shape.shader.properties.UV_Offset_V
            self.texmap.inputs['Scale U'].default_value = shape.shader.properties.UV_Scale_U
            self.texmap.inputs['Scale V'].default_value = shape.shader.properties.UV_Scale_V
            self.texmap.inputs['Wrap U'].default_value = \
                1 if shape.shader.properties.textureClampMode & 2 else 0
            self.texmap.inputs['Wrap V'].default_value = \
                1 if shape.shader.properties.textureClampMode & 1 else 0

            self.material.use_backface_culling = not shape.shader.flag_double_sided

        except Exception as e:
            # Any errors, print the error but continue
            log.exception(f"Error importing shader attributes for shape {shape.name}")


    def make_node(self, nodetype, name=None, xloc=None, yloc=None, height=0):
        """
        Make a node. If yloc not provided, use and increment the current ytop location.
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
            h = height
            if h == 0:
                try:
                    h = shader_node_height[nodetype]
                except:
                    h = 150
            self.ytop -= h + VERTICAL_GAP

        if name: 
            n.name = name
            n.label = name

        return n
    

    def make_uv_nodes(self):
        """
        Make the value nodes and calculations that are used as input to the shader.
        """
        self.ytop = self.bsdf.location.y
        self.texmap = make_uv_node(
            self, 
            self.asset_path, 
            (self.inputs_offset_x-TEXTURE_NODE_WIDTH-HORIZONTAL_GAP, 0,))


    def import_shader_alpha(self, shape):
        if 'Alpha Mult' in self.bsdf.inputs:
            self.bsdf.inputs['Alpha Mult'].default_value = shape.shader.properties.Alpha

        if shape.has_alpha_property:
            props:AlphaPropertyBuf = shape.alpha_property.properties

            alpha = append_groupnode(self, "AlphaProperty",  "Alpha Property", self.asset_path)
            alpha.width = TEXTURE_NODE_WIDTH
            self.link(alpha.outputs[0], self.bsdf.inputs['Alpha Property'])

            if self.diffuse:
                self.link(self.diffuse.outputs['Alpha'], alpha.inputs['Alpha'])
            
            if self.alphamap:
                self.link(self.vertex_alpha.outputs['Color'], alpha.inputs['Vertex Alpha'])

            self.material.alpha_threshold = 1 # Not using the material's alpha threshold
            alpha.inputs['Alpha Test'].default_value = bool(props.alpha_test)
            if props.alpha_test:
                alpha.inputs['Alpha Threshold'].default_value = props.threshold

            alpha.inputs['Alpha Blend'].default_value = bool(props.alpha_blend)
            alpha.inputs['Source Blend Mode'].default_value = props.source_blend_mode
            alpha.inputs['Destination Blend Mode'].default_value = props.dst_blend_mode

            self.material['NiAlphaProperty_flags'] = shape.alpha_property.properties.flags
            self.material['NiAlphaProperty_threshold'] = shape.alpha_property.properties.threshold

            return True
        else:
            if self.vertex_alpha:
                self.link(self.vertex_alpha.outputs['Color'], self.bsdf.inputs['Vertex Alpha'])
            try:
                self.diffuse.image.alpha_mode = 'NONE'
            except:
                pass
            
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
        self.textures = {}

        for k, t in shape.textures.items():
            if not t: continue
            if k == 'RootMaterialPath':
                p = find_referenced_file(
                    t,
                    nifpath=shape.file.filepath, 
                    root='materials',
                    alt_suffix=None, 
                    alt_path=bpy.context.preferences.filepaths.texture_directory)
            else:
                p = find_referenced_file(
                    t,
                    nifpath=shape.file.filepath, 
                    alt_suffix='.png', 
                    alt_path=bpy.context.preferences.filepaths.texture_directory)
            if p:
                self.textures[k] = p


    def link(self, a, b):
        """Create a link between two nodes"""
        self.material.node_tree.links.new(a, b)

    
    def import_grayscale(self, txtnode):
        """
        Import shader nodes to handle grayscale coloring.
        """
        try:
            txt_outskt = txtnode.outputs['Color']
            gtpvector = append_groupnode(self,
                                         "Fallout 4 MTS - Greyscale To Palette Vector",
                                         "Greyscale to Palette Vector",
                                         self.asset_path)
            gtpvector.width = txtnode.width
            if self.is_effect_shader:
                # EffectShader doesn't have a grayscaleToPaletteScale value. Use 0.99
                # instead of 1.0 because 1.0 wraps around to 0.
                gtpvector.inputs['Palette'].default_value = 0.99
            else:
                gtpvector.inputs['Palette'].default_value = self.shape.shader.properties.grayscaleToPaletteScale
            self.link(txt_outskt, gtpvector.inputs['Diffuse'])
            txtnode.image.colorspace_settings.name = "Non-Color"
            reposition(gtpvector)

            palettenode = self.make_node("ShaderNodeTexImage",
                                         name='Palette Vector')
            if 'Greyscale' in self.textures and self.textures['Greyscale']:
                imgp = bpy.data.images.load(self.textures['Greyscale'])
                imgp.colorspace_settings.name = "sRGB"
                palettenode.image = imgp
            else:
                self.warn(f"Could not load greyscale texture '{self.shape.textures['Greyscale']}'")
            self.link(gtpvector.outputs[0], palettenode.inputs[0])
            reposition(palettenode)

            gtpcolor = append_groupnode(self,
                                        "Fallout 4 MTS - Greyscale To Palette Color",
                                        "Greyscale To Palette Color", 
                                         self.asset_path)
            gtpcolor.width = txtnode.width
            self.link(palettenode.outputs["Color"], gtpcolor.inputs['Greyscale'])
            self.link(gtpcolor.outputs['Diffuse'], self.bsdf.inputs['Diffuse'])
            reposition(gtpcolor)
    
        except:
            self.warn(f"Could not load shader nodes from assets file: {traceback.format_exc()}")


    def import_diffuse(self):
        """Create nodes for the diffuse texture."""

        if not ('Diffuse' in self.shape.textures and self.shape.textures['Diffuse']):
            return
        
        txtnode = self.make_node("ShaderNodeTexImage",
                                 name='Diffuse_Texture',
                                 xloc=self.inputs_offset_x)
        txtnode.width = txtnode.width * 1.2
        if 'Diffuse' in self.textures and self.textures['Diffuse']:
            img = bpy.data.images.load(self.textures['Diffuse'], check_existing=True)
            img.colorspace_settings.name = "sRGB"
            txtnode.image = img
        else:
            self.warn(f"Could not load diffuse texture '{self.shape.textures['Diffuse']}'")
        self.link(self.texmap.outputs['Vector'], txtnode.inputs['Vector'])
        if self.shape.shader.flag_greyscale_color:
            # Extra nodes to handle greyscale color mapping
            self.import_grayscale(txtnode)

        else:
            self.link(txtnode.outputs['Color'], self.bsdf.inputs['Diffuse'])

        if 'Vertex Color' in self.bsdf.inputs:
            if self.colormap:
                cmap = self.make_node('ShaderNodeAttribute',
                                    name='Vertex Color',
                                    xloc=self.inputs_offset_x)
                cmap.attribute_type = 'GEOMETRY'
                cmap.attribute_name = self.colormap.name
                self.link(cmap.outputs['Color'], self.bsdf.inputs['Vertex Color'])

        if 'Vertex Alpha' in self.bsdf.inputs:
            if self.alphamap:
                vmap = self.make_node('ShaderNodeAttribute',
                                    name='Vertex Alpha',
                                    xloc=self.inputs_offset_x)
                vmap.attribute_type = 'GEOMETRY'
                vmap.attribute_name = self.alphamap.name
                self.vertex_alpha = vmap

        self.diffuse = txtnode


    def import_subsurface(self):
        """Set up nodes for subsurface texture"""
        if 'SoftLighting' in self.shape.textures and self.shape.textures['SoftLighting']: 
            # Have a sk separate from a specular. Make an image node.
            skimgnode = self.make_node("ShaderNodeTexImage",
                                       name='Subsurface_Texture',
                                       xloc=self.inputs_offset_x)
            if 'SoftLighting' in self.textures and self.textures['SoftLighting']:
                skimg = bpy.data.images.load(self.textures['SoftLighting'], check_existing=True)
                if skimg != self.diffuse.image:
                    skimg.colorspace_settings.name = "Non-Color"
                skimgnode.image = skimg
            else:
                self.warn(f"Could not load subsurface texture '{self.shape.textures['SoftLighting']}'")
            self.link(self.texmap.outputs['Vector'], skimgnode.inputs['Vector'])
            self.link(skimgnode.outputs['Color'], self.bsdf.inputs['Subsurface'])
            reposition(skimgnode, xpos=POS_LEFT, vpos=POS_BELOW, reference=self.bsdf)

            v = self.make_node('ShaderNodeValue',
                                name='Subsurface Strength',
                                xloc=self.inputs_offset_x)
            v.outputs[0].default_value = self.shape.shader.properties.Soft_Lighting
            self.link(v.outputs['Value'], self.bsdf.inputs['Subsurface Str'])


    def import_specular(self):
        """Set up nodes for specular texture"""
        if self.shape.shader.properties.shaderflags1_test(ShaderFlags1.SPECULAR):
            if 'Specular' in self.textures and self.textures['Specular']:
                # Make the specular texture input node.
                simgnode = self.make_node("ShaderNodeTexImage",
                                        name='Specular_Texture',
                                        xloc=self.inputs_offset_x)
                simg = bpy.data.images.load(self.textures['Specular'], check_existing=True)
                simg.colorspace_settings.name = "Non-Color"
                simgnode.image = simg
                self.link(self.texmap.outputs['Vector'], simgnode.inputs['Vector'])
                if 'Smooth Spec' in self.bsdf.inputs: 
                    self.link(simgnode.outputs['Color'], self.bsdf.inputs['Smooth Spec'])
                else:
                    if 'Specular Color' in self.bsdf.inputs:
                        self.link(simgnode.outputs['Color'], self.bsdf.inputs['Specular Color'])
                    else:
                        self.link(simgnode.outputs['Color'], self.bsdf.inputs['Specular'])

            for i, v in enumerate(self.shape.shader.properties.Spec_Color):
                self.bsdf.inputs['Specular Color'].default_value[i] = v

            if 'Specular Str' in self.bsdf.inputs:
                self.bsdf.inputs['Specular Str'].default_value = self.shape.shader.properties.Spec_Str


    def import_glowmap(self):
        """Set up nodes for glow map texture"""
        if self.shape.shader.properties.shaderflags2_test(ShaderFlags2.GLOW_MAP) \
                and 'Glow' in self.textures \
                    and self.shape.textures['Glow']:
            # Make the glow map texture input node.
            simgnode = self.make_node("ShaderNodeTexImage",
                                      name='Glow_Map_Texture',
                                      xloc=self.inputs_offset_x)
            if 'Glow' in self.textures and self.textures['Glow']:
                simg = bpy.data.images.load(self.textures['Glow'], check_existing=True)
                simg.colorspace_settings.name = "Non-Color"
                simgnode.image = simg
            else:
                self.warn(f"Could not load glow map texture '{self.shape.textures['Glow']}'")
            self.link(self.texmap.outputs['Vector'], simgnode.inputs['Vector'])
            try: 
                self.link(simgnode.outputs['Color'], self.bsdf.inputs['Glow Map'])
            except:
                pass


    def import_normal(self):
        """Set up nodes for the normal map"""
        if 'Normal' in self.shape.textures and self.shape.textures['Normal']:
            nimgnode = self.make_node("ShaderNodeTexImage",
                                        name='Normal_Texture',
                                        xloc=self.inputs_offset_x)
            self.link(self.texmap.outputs['Vector'], nimgnode.inputs['Vector'])
            if 'Normal' in self.textures and self.textures['Normal']:
                nimg = bpy.data.images.load(self.textures['Normal'], check_existing=True) 
                nimg.colorspace_settings.name = "Non-Color"
                nimgnode.image = nimg
            else:
                self.warn(f"Could not load normal texture '{self.shape.textures['Normal']}'")

            self.link(nimgnode.outputs['Color'], self.bsdf.inputs['Normal'])
            if self.game in ['SKYRIM', 'SKYRIMSE']:
                if not self.shape.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                    # Tangent normals have specular in alpha channel.
                    if 'Specular' in self.bsdf.inputs:
                        self.link(nimgnode.outputs['Alpha'], self.bsdf.inputs['Specular'])
                    elif 'Specular IOR Level' in self.bsdf.inputs:
                        self.link(nimgnode.outputs['Alpha'], self.bsdf.inputs['Specular IOR Level'])


    def import_material(self, obj, shape:NiShape, asset_path):
        """
        Import the shader info from shape and create a Blender representation using shader
        nodes.
        * logger: Implemenets the "warn" function to report errors.
        """
        try:
            if obj.type == 'EMPTY': return 

            self.shape = shape
            self.game = shape.file.game
            self.is_effect_shader = (shape.shader.blockname == 'BSEffectShaderProperty')
            self.is_lighting_shader = (shape.shader.blockname == 'BSLightingShaderProperty')
            have_face = (self.is_lighting_shader and 
                        shape.shader.properties.Shader_Type == BSLSPShaderType.Face_Tint)
            self.asset_path = os.path.join(asset_path, "shaders.blend")

            self.material = bpy.data.materials.new(name=(obj.name + ".Mat"))
            self.material.use_nodes = True
            self.nodes = self.material.node_tree.nodes

            # Stash texture strings for future export
            for k, t in shape.textures.items():
                if t:
                    self.material['BSShaderTextureSet_' + k] = t

            self.find_textures(shape)

            for n in self.nodes:
                if n.type == 'OUTPUT_MATERIAL': 
                    mo = n
                if 'BSDF' in n.type: 
                    self.nodes.remove(n)

            if self.game == 'FO4':
                self.bsdf = make_shader_fo4(self.material.node_tree, 
                                            self.asset_path, 
                                            (mo.location.x - NODE_WIDTH, mo.location.y),
                                            facegen=have_face,
                                            effect_shader=self.is_effect_shader)
            else:
                self.bsdf = make_shader_skyrim(self.material.node_tree,
                                            self.asset_path,
                                            mo.location + Vector((-NODE_WIDTH, 0)),
                                            msn=shape.shader.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS),
                                            facegen=have_face,
                                            effect_shader=self.is_effect_shader)
            
            self.bsdf.width = 250
            self.bsdf.location.x -= 100
            self.link(self.bsdf.outputs[0], mo.inputs[0])
            
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
            self.import_shader_attrs(shape)
            self.import_shader_alpha(shape)
            self.import_subsurface()
            self.import_specular()
            self.import_normal()
            self.import_glowmap()

            reposition(self.bsdf, vpos=POS_TOP, padding=Vector((HORIZONTAL_GAP*2, 0)))
            reposition(mo)

            obj.active_material = self.material
        except Exception as e:
            self.warn(f"Could not import material for {obj.name}: " + traceback.format_exc())


def set_object_textures(shape: NiShape, mat: bpy.types.Material):
    """Set the shape's textures from the value from the material's custom properties."""
    for k, v in mat.items():
        if k.startswith('BSShaderTextureSet_'):
            slot = k[len('BSShaderTextureSet_'):]
            shape.set_texture(slot, v)

    
def get_image_filepath(node_input):
    try:
        nl = BD.find_node(node_input, 'ShaderNodeTexImage')
        return nl[0].image.filepath
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
    with suppress(IndexError):
        matoutlist = [x for x in obj.active_material.node_tree.nodes if x.bl_idname == 'ShaderNodeOutputMaterial']
        mat_out = matoutlist[0]
        surface_skt = mat_out.inputs[0]
        start_node = surface_skt.links[0].from_node
        if start_node.bl_idname == 'ShaderNodeGroup':
            grp_outputs = [n for n in start_node.node_tree.nodes if n.bl_idname == 'NodeGroupOutput']
            group_out = grp_outputs[0]
            start_node = group_out.inputs[0].links[0].from_node
        normlist = BD.find_node(start_node.inputs.get("Normal"), 'ShaderNodeNormalMap') if "Normal" in start_node.inputs else []
        val = normlist[0].space == 'OBJECT'
    return val


class ShaderExporter:
    def __init__(self, blender_obj, game):
        self.obj = blender_obj
        self.is_obj_space = False
        self.logger = logging.getLogger("pynifly")
        self.game = game

        self.material = None
        self.shader_node = None
        if blender_obj.active_material:
            self.material = blender_obj.active_material
            nodelist = self.material.node_tree.nodes
            if not "Material Output" in nodelist:
                log.warning(f"Have material but no Material Output for {self.material.name}")
            else:
                self.material_output = nodelist["Material Output"]
                if self.material_output.inputs[0].is_linked:
                    self.shader_node = self.material_output.inputs[0].links[0].from_node
                    if 'MSN' in self.shader_node.inputs:
                        self.is_obj_space = bool(self.shader_node.inputs['MSN'].default_value)
                    else:
                        self.is_obj_space = has_msn_shader(blender_obj)
                if not self.shader_node:
                    raise Exception(f"Have material but no shader node for {self.material.name}")

        self.vertex_colors, self.vertex_alpha = get_effective_colormaps(blender_obj.data)

    def warn(self, msg):
        self.logger.warn(msg)


    def _export_shader_attrs(self, shape):
        if not self.material:
            return
        
        try:
            if 'BSLSP_Shader_Name' in self.material and self.material['BSLSP_Shader_Name']:
                shape.shader.name = self.material['BSLSP_Shader_Name']

            shape.shader.properties.load(self.material, game=self.game)
            if 'BS_Shader_Block_Name' in self.material:
                if self.material['BS_Shader_Block_Name'] == "BSLightingShaderProperty":
                    shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
                elif self.material['BS_Shader_Block_Name'] == "BSEffectShaderProperty":
                    shape.shader.properties.bufType = PynBufferTypes.BSEffectShaderPropertyBufType
                    shape.shader.properties.bBSLightingShaderProperty = 0
                elif self.material['BS_Shader_Block_Name'] == "BSShaderPPLightingProperty":
                    shape.shader.properties.bufType = PynBufferTypes.BSShaderPPLightingPropertyBufType
                else:
                    self.warn(f"Unknown shader type: {self.material['BS_Shader_Block_Name']}")

            nl = self.material.node_tree.nodes
            if 'UV_Converter' in nl:
                uv = nl['UV_Converter'].inputs
                shape.shader.properties.UV_Offset_U = uv['Offset U'].default_value
                shape.shader.properties.UV_Offset_V = uv['Offset V'].default_value
                shape.shader.properties.UV_Scale_U = uv['Scale U'].default_value
                shape.shader.properties.UV_Scale_V = uv['Scale V'].default_value

                try:
                    shape.shader.properties.textureClampMode = \
                        (2 if uv['Wrap U'].default_value == 1 else 0) \
                        + (1 if uv['Wrap V'].default_value == 1 else 0)
                except:
                    shape.shader.properties.textureClampMode = \
                        (2 if uv['Clamp S'].default_value == 1 else 0) \
                        + (1 if uv['Clamp T'].default_value == 1 else 0)

            if 'UV_Offset_U' in nl:
                shape.shader.properties.UV_Offset_U = nl['UV_Offset_U'].outputs['Value'].default_value
            if 'UV_Offset_V' in nl:
                shape.shader.properties.UV_Offset_V = nl['UV_Offset_V'].outputs['Value'].default_value
            if 'UV_Scale_U' in nl:
                shape.shader.properties.UV_Scale_U = nl['UV_Scale_U'].outputs['Value'].default_value
            if 'UV_Scale_V' in nl:
                shape.shader.properties.UV_Scale_V = nl['UV_Scale_V'].outputs['Value'].default_value

            shape.shader.properties.Emissive_Mult = self.shader_node.inputs['Emission Strength'].default_value
            shape.shader.properties.baseColorScale = self.shader_node.inputs['Emission Strength'].default_value
            if 'Emission Color' in self.shader_node.inputs:
                em = 'Emission Color'
            else:
                em = 'Emission'
            for i in range(0, 4):
                shape.shader.properties.Emissive_Color[i] = self.shader_node.inputs[em].default_value[i]
                shape.shader.properties.baseColor[i] = self.shader_node.inputs[em].default_value[i] 

            if not self.is_effectshader:
                if 'Alpha Mult' in self.shader_node.inputs:
                    shape.shader.properties.Alpha = self.shader_node.inputs['Alpha Mult'].default_value
            if 'Glossiness' in self.shader_node.inputs:
                shape.shader.properties.Glossiness = self.shader_node.inputs['Glossiness'].default_value
            
        except Exception as e:
            log.exception(f"Could not determine shader attributes: for {shape.name}")


    @property
    def is_effectshader(self):
        try:
            return self.material['BS_Shader_Block_Name'] == 'BSEffectShaderProperty'
        except:
            pass
        return False
    

    texture_slots = {"EnvMap": (1, ShaderFlags1.ENVIRONMENT_MAPPING),
                     "EnvMask": (2, ShaderFlags2.ENVMAP_LIGHT_FADE),
                     "SoftLighting": (2, ShaderFlags2.SOFT_LIGHTING),
                     "Specular": (1, ShaderFlags1.SPECULAR),
                     "Glow": (2, ShaderFlags2.GLOW_MAP),
                     "HeightMap": (1, ShaderFlags1.PARALLAX),
                     "Greyscale": (1, ShaderFlags1.GREYSCALE_COLOR),
                     "FacegenDetail": (1, ShaderFlags1.FACEGEN_DETAIL_MAP),
                     "InnerLayer": (2, ShaderFlags2.MULTI_LAYER_PARALLAX),
                     }
    
    def shader_flag_get(self, shape, textureslot):
        if textureslot in self.texture_slots:
            n, f = self.texture_slots[textureslot]
            if n == 1:
                return shape.shader.properties.shaderflags1_test(f)
            else:
                return shape.shader.properties.shaderflags2_test(f)
    
    def shader_flag_set(self, shape, textureslot):
        if textureslot in self.texture_slots:
            n, f = self.texture_slots[textureslot]
            if n == 1:
                shape.shader.properties.shaderflags1_set(f)
            else:
                shape.shader.properties.shaderflags2_set(f)
    
    def shader_flag_clear(self, shape, textureslot):
        if textureslot in self.texture_slots:
            n, f = self.texture_slots[textureslot]
            if n == 1:
                shape.shader.properties.shaderflags1_clear(f)
            else:
                shape.shader.properties.shaderflags2_clear(f)
    

    def write_texture(self, shape, textureslot:str):
        """
        Write the given texture slot to the nif shape.
        """
        foundpath = ""
        imagenode = None

        if textureslot == "SoftLighting":
            # Subsurface is hidden behind mixnodes in 4.0 so just grab the node by name.
            # Maybe we should just do this for all texture layers.
            if 'Subsurface Color' in self.shader_node.inputs:
                imagenodes = BD.find_node(self.shader_node.inputs["Subsurface Color"], "ShaderNodeTexImage")
                if imagenodes: imagenode = imagenodes[0]
            elif "Subsurface" in self.shader_node.inputs:
                imagenodes = BD.find_node(self.shader_node.inputs["Subsurface"], "ShaderNodeTexImage")
                if imagenodes: imagenode = imagenodes[0]

        elif textureslot == "Specular":
            imagenodes = None
            if "Specular_Texture" in self.material.node_tree.nodes:
                imagenode = self.material.node_tree.nodes["Specular_Texture"]
            else:
                # Don't have an obvious texture node, walk the BSDF inputs backwards.
                if "Specular" in self.shader_node.inputs:
                    imagenodes = BD.find_node(self.shader_node.inputs["Specular"], "ShaderNodeTexImage")
                elif "Specular Color" in self.shader_node.inputs:
                    imagenodes = BD.find_node(self.shader_node.inputs["Specular Color"], "ShaderNodeTexImage")
                elif "Specular IOR Level" in self.shader_node.inputs:
                    imagenodes = BD.find_node(self.shader_node.inputs["Specular IOR Level"], "ShaderNodeTexImage")
                if imagenodes: imagenode = imagenodes[0]

        elif textureslot == "Diffuse":
            if "Base Color" in self.shader_node.inputs:
                imagenodes = BD.find_node(self.shader_node.inputs["Base Color"], "ShaderNodeTexImage")
            else:
                imagenodes = BD.find_node(self.shader_node.inputs["Diffuse"], "ShaderNodeTexImage")
            if imagenodes: imagenode = imagenodes[0]
            # Check whether this is a greyscale texture. If so, look for the diffuse behind it.
            if imagenode and imagenode.label == 'Palette Vector':
                imagenodes = BD.find_node(imagenode.inputs['Vector'], 'ShaderNodeTexImage')
                if imagenodes: imagenode = imagenodes[0]
        else:
            # Look through the node tree behind the texture slot to find the right image
            # node.
            if textureslot in self.shader_node.inputs:
                imagenodes = BD.find_node(self.shader_node.inputs[textureslot], "ShaderNodeTexImage")
                if imagenodes: imagenode = imagenodes[0]

        foundpath = relpath = None
        if imagenode:
            if textureslot == 'Specular':
                # Check to see if the specular is coming from the normal texture. If so,
                # don't use it.
                normnodes = BD.find_node(self.shader_node.inputs["Normal"], "ShaderNodeTexImage")
                if normnodes and normnodes[0] == imagenode:
                    return
            try:
                if imagenode.image:
                    foundpath = imagenode.image.filepath
                    relpath = Path(foundpath)
            except:
                pass
            # Clean up the path for export
            if foundpath:
                fp = Path(foundpath.lower())
                try:
                    txtindex = fp.parts.index('textures')
                    relpath = Path(*fp.parts[txtindex:])
                except ValueError:
                    relpath = fp

        if relpath:
            # Make sure the shader flags reflect the nodes we found.
            self.shader_flag_set(shape, textureslot)
            shape.set_texture(textureslot, str(relpath.with_suffix('.dds')))
        else:
            # No texture for the current slot. If the flags say we should have one and we
            # didn't get one from the object properties, warn and clear the flag. Don't
            # report on EnvMap_Light_Fade because lots of Skyrim nifs have it set and I'm
            # not sure the flag isn't being reused in some way. Or else it doesn't matter
            # if it's set so a bunch of nifs leave it on.
            if self.shader_flag_get(shape, textureslot) \
                and textureslot not in shape.shader.textures \
                    and textureslot != 'EnvMask':
                self.warn(f"Could not find image shader node for {textureslot} layer.")
                self.shader_flag_clear(shape, textureslot)


    def _export_alpha(self, shape:NiShape):
        """
        Export the alpha property.
        """
        if 'Alpha Property' in self.shader_node.inputs:
            alpha_input = self.shader_node.inputs['Alpha Property']
        else:
            alpha_input = None

        if (not alpha_input) or (not alpha_input.is_linked):
            return
        
        shape.has_alpha_property = True

        alphanode = alpha_input.links[0].from_node
        alpha = shape.alpha_property.properties
        try:
            alpha.alpha_test = bool(alphanode.inputs['Alpha Test'].default_value)
            if alpha.alpha_test:
                alpha.threshold = int(alphanode.inputs['Alpha Threshold'].default_value)
            alpha.alpha_blend = bool(alphanode.inputs['Alpha Blend'].default_value)
            alpha.source_blend_mode = alphanode.inputs['Source Blend Mode'].default_value
            alpha.dst_blend_mode = alphanode.inputs['Destination Blend Mode'].default_value
        except:
            if 'NiAlphaProperty_flags' in self.material:
                shape.alpha_property.properties.flags = self.material['NiAlphaProperty_flags']
            else:
                log.warning(f"Shader nodes not set up for alpha on {shape.name}")

        shape.save_alpha_property()


    def _export_textures(self, shape: NiShape):
        """
        Create shader in nif from the blender object's material. 
        Handles only the texture types we know how to handle in the shader. The rest are
        properties on the material and are picked up from there.
        """
        # Use textures stored in properties as defaults; override them with shader nodes
        set_object_textures(shape, self.material)

        if not self.shader_node: return

        # Write the textures we can write. 'Wrinkles' and 'RootMaterialPath' appear in
        # the materials file only.
        for textureslot in ['Diffuse', 'Normal', 'SoftLighting', 'Specular', 
                            'EnvMap', 'EnvMask']:
            self.write_texture(shape, textureslot)


    def export(self, new_shape:NiShape):
        """Top-level routine for exporting a shape's texture attributes."""
        if not self.material: return

        try:
            self._export_shader_attrs(new_shape)
            self._export_textures(new_shape)
            self._export_alpha(new_shape)
            if self.is_obj_space:
                new_shape.shader.properties.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
            else:
                new_shape.shader.properties.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)

            if self.vertex_colors:
                new_shape.shader.properties.shaderflags2_set(ShaderFlags2.VERTEX_COLORS)
            else:
                new_shape.shader.properties.shaderflags2_clear(ShaderFlags2.VERTEX_COLORS)

            if self.vertex_alpha:
                new_shape.shader.properties.shaderflags1_set(ShaderFlags1.VERTEX_ALPHA)
            else:
                new_shape.shader.properties.shaderflags1_clear(ShaderFlags1.VERTEX_ALPHA)

            new_shape.save_shader_attributes()
        except Exception as e:
            # Any errors, print the error but continue
            self.warn(str(e))
