"""Shader node helpers shared by every game's materials: node and socket names, layout
constants, and small builders for the nodes they all use."""

import logging
import bpy
from mathutils import Vector


log = logging.getLogger("pynifly")

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
# Node type and socket names as of Blender 4.0, which is the addon's minimum
# (bl_info["blender"]); Blender refuses to enable the addon below it. The pre-4.0
# names are not carried -- ShaderNodeSeparateRGB/CombineRGB were themselves removed
# in Blender 5.0, so a fallback to them would be broken anyway.
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

shader_node_height = {
    'ShaderNodeTexImage': 271,
    'ShaderNodeMapRange': 241,
    'ShaderNodeMath': 148,
    'ShaderNodeValue': 79,
    'ShaderNodeAttribute': 170,
    'ShaderNodeGroup': 200,
}


def relative_loc(nodelist, xpos=POS_RIGHT, vpos=POS_BOTTOM):
    """
    Calculate a location relative to the given node list: to the right of the rightmost
    and at the same level as the lowest.
    """
    if not nodelist: return Vector((0, 0,))

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
    if inputlist:
        node.location = relative_loc(inputlist, xpos=xpos, vpos=vpos) + padding


def make_separator(nodetree, input, loc):
    """
    Make a color separator node with input connected to socket "input".
    """
    rgbsep = nodetree.nodes.new(SEPARATOR_IDNAME)
    rgbsep.mode = 'RGB'

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
    skt = bsdf.inputs['Specular IOR Level']
    m = make_mixnode(nodetree, source, strength, skt, location=location)

    nodetree.links.new(color, bsdf.inputs['Specular Tint'])
   

def make_combiner(nodetree, r, g, b, loc):
    """
    Make a combiner node with inputs from sockets r, g, b. Returns created node.

    b can be a socket or float value.
    """
    combiner = nodetree.nodes.new(COMBINER_IDNAME)

    combiner.location = loc
    combiner.mode = 'RGB'

    nodetree.links.new(r, combiner.inputs[0])
    nodetree.links.new(g, combiner.inputs[1])
    if isinstance(b, bpy.types.NodeSocket):
        nodetree.links.new(b, combiner.inputs[2])
    else:
        combiner.inputs[2].default_value = b
    return combiner


def make_combiner_xyz(nodetree, x, y, z, loc):
    """
    Make a combiner node with inputs from sockets x, y, z. Returns created node.
    """
    combiner = nodetree.nodes.new('ShaderNodeCombineXYZ')
    combiner.location = loc

    nodetree.links.new(x, combiner.inputs[0])
    nodetree.links.new(y, combiner.inputs[1])
    if z: nodetree.links.new(z, combiner.inputs[2])
    return combiner


def make_mixnode(nodetree, input1, input2, output=None, factor=1.0, 
                 blend_type='MULTIPLY', location=None):
    """
    Create a shader RGB mix node--or fall back if it's an older version of Blender.
    """
    mixnode = nodetree.nodes.new(MIXNODE_IDNAME)
    mixnode.data_type = 'RGBA'

    nodetree.links.new(input1, mixnode.inputs[MIXNODE_IN1])
    inputlist = [input1.node]
    if isinstance(input2, bpy.types.NodeSocket):
        nodetree.links.new(input2, mixnode.inputs[MIXNODE_IN2])
        inputlist.append(input2.node)
    else:
        for i, v in enumerate(input2):
            mixnode.inputs[MIXNODE_IN2].default_value[i] = v
    if output: 
        nodetree.links.new(mixnode.outputs[MIXNODE_OUT], output)
    mixnode.blend_type = blend_type
    if isinstance(factor, bpy.types.NodeSocket):
        nodetree.links.new(factor, mixnode.inputs[MIXNODE_FACTOR])
        inputlist.append(factor.node)
    else:
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
        if isinstance(in_from_min, bpy.types.NodeSocket):
            nodetree.links.new(in_from_min, node.inputs['From Min'])
            nodelist.append(in_from_min)
        else:
            node.inputs['From Min'].default_value = in_from_min
    if in_from_max: 
        if isinstance(in_from_max, bpy.types.NodeSocket):
            nodetree.links.new(in_from_max, node.inputs['From Max'])
            nodelist.append(in_from_max)
        else:
            node.inputs['From Max'].default_value = in_from_max
    if in_to_min: 
        if isinstance(in_to_min, bpy.types.NodeSocket):
            nodetree.links.new(in_to_min, node.inputs['To Min'])
            nodelist.append(in_to_min)
        else:
            node.inputs['To Min'].default_value = in_to_min
    if in_to_max: 
        if isinstance(in_to_max, bpy.types.NodeSocket):
            nodetree.links.new(in_to_max, node.inputs['To Max'])
            nodelist.append(in_to_max)
        else:
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
