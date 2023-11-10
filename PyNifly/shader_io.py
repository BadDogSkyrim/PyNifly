"""Shader Import/Export for pyNifly"""

# Copyright © 2021, Bad Dog.

import os
from pathlib import Path
import logging
import bpy
from pynifly import *
from mathutils import Matrix, Vector, Quaternion, Euler, geometry

ALPHA_MAP_NAME = "VERTEX_ALPHA"
MSN_GROUP_NAME = "MSN_TRANSFORM"
TANGENT_GROUP_NAME = "TANGENT_TRANSFORM"
GLOSS_SCALE = 100
ATTRIBUTE_NODE_HEIGHT = 200
TEXTURE_NODE_WIDTH = 400
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
    ]

def find_node(socket, nodetype):
    """
    Find node of the given type that feeds the given socket.
    """
    if not socket.is_linked:
        return None
    
    n = socket.links[0].from_node
    if n.bl_idname == nodetype:
        # This is what we're looking for.
        return n
    elif n.bl_idname == "ShaderNodeGroup":
        # Dive into the group and see if it's in there.
        gnodes = n.node_tree.nodes
        goutputs = [x for x in n.node_tree.nodes if x.bl_idname == 'NodeGroupOutput']
        if goutputs:
            m = find_node(goutputs[0].inputs[0], nodetype)
            if m: 
                return m

    # Not this one, check its inputs.
    for ns in n.inputs:
        m = find_node(ns, nodetype) 
        if m:
            return m
    
    return None


def tangent_normal(nodetree, source, destination, location):
    """
    Create a group node that handles the transformations for tangent space normals (Skyrim
    and FO4).
    """
    # Create a new shader group
    shader_group = bpy.data.node_groups.new(type='ShaderNodeTree', name='TangentNormal')

    # create group inputs
    group_inputs = shader_group.nodes.new('NodeGroupInput')
    group_inputs.location = (-200,0)
    shader_group.inputs.new('NodeSocketColor','Image')

    nodelist = shader_group.nodes
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
    
    colorinv = nodelist.new("ShaderNodeInvert")
    colorinv.location = rgbsep.location + Vector((200, -150))
    rgbcomb = nodelist.new(combine_name)
    rgbcomb.location = colorinv.location + Vector((200, 150))
    if combine_name == "ShaderNodeCombineRGB": rgbcomb.mode = 'RGB'

    nmap = nodelist.new("ShaderNodeNormalMap")
    nmap.location = rgbcomb.location + Vector((200, 0))
    nmap.space = 'TANGENT'
    nmap.inputs['Strength'].default_value = 2.0 # Make it a little more obvious.

    shader_group.links.new(rgbsep.outputs[0], rgbcomb.inputs[0])
    shader_group.links.new(rgbsep.outputs[2], rgbcomb.inputs[2])
    shader_group.links.new(rgbsep.outputs[1], colorinv.inputs['Color'])
    shader_group.links.new(colorinv.outputs['Color'], rgbcomb.inputs[1])
    shader_group.links.new(rgbcomb.outputs[socketname], nmap.inputs['Color'])
    shader_group.links.new(group_inputs.outputs[0], rgbsep.inputs[socketname])
    
    # create group outputs
    group_outputs = shader_group.nodes.new('NodeGroupOutput')
    group_outputs.location = nmap.location + Vector((200, 0))
    shader_group.outputs.new('NodeSocketVector', 'Normal')

    shader_group.links.new(nmap.outputs['Normal'], group_outputs.inputs[0])

    # Make the node in the object's shader that references this group.
    g = nodetree.nodes.new("ShaderNodeGroup")
    g.name = TANGENT_GROUP_NAME
    g.label = "Tangent Normal"
    g.location = location
    g.node_tree = shader_group
    nodetree.links.new(source, g.inputs[0])
    nodetree.links.new(g.outputs[0], destination)

    return g


def modelspace_normal(nodetree, source, destination, location):
    """
    Create a group node that handles the transformations for model space normals (Skyrim
    and FO4).

    Don't know yet how to handle group inputs and outputs for Blender 4.0, so finess that.
    """
    # Create a new shader group
    shader_group = None
    try:
        shader_group = bpy.data.node_groups.new(type='ShaderNodeTree', name='TangentNormal')

        # create group inputs
        group_inputs = shader_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-200,0)
        shader_group.inputs.new('NodeSocketColor','Image')
        internal_location = (0, 0)
        internal_nodetree = shader_group
    except:
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


def new_mixnode(mat, out1, out2, inp):
    """Create a shader Mix node--or fall back if it's an older version of Blender."""
    mixnode = None
    try:
        # Blender 3.5
        mixnode = mat.node_tree.nodes.new("ShaderNodeMix")
        mixnode.data_type = 'RGBA'
        mat.node_tree.links.new(out1, mixnode.inputs[6])
        mat.node_tree.links.new(out2, mixnode.inputs[7])
        mat.node_tree.links.new(mixnode.outputs[2], inp)
        mixnode.blend_type = 'MULTIPLY'
        mixnode.inputs['Factor'].default_value = 1
    except:
        pass

    if not mixnode:
        # Blender 3.1
        mixnode = mat.node_tree.nodes.new("ShaderNodeMixRGB")
        mat.node_tree.links.new(out1, mixnode.inputs['Color1'])
        mat.node_tree.links.new(out2, mixnode.inputs['Color2'])
        mat.node_tree.links.new(mixnode.outputs['Color'], inp)
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
        

    @property
    def subsurface_color_skt(self):
        if "Subsurface Color" in self.bsdf.inputs:
            return self.bsdf.inputs["Subsurface Color"]
        if "Subsurface Radius" in self.bsdf.inputs:
            return self.bsdf.inputs["Subsurface Radius"]


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
            # self.bsdf.inputs['Emission'].default_value = shader.Emissive_Color
            for i, v in enumerate(shader.Emissive_Color):
                self.nodes['Emissive_Color'].outputs[0].default_value[i] = v
            self.nodes['Emissive_Mult'].outputs[0].default_value = shader.Emissive_Mult

            if shader.blockname == 'BSLightingShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = shader.Alpha
                self.nodes['Glossiness'].outputs['Value'].default_value = shader.Glossiness
                # self.bsdf.inputs['Metallic'].default_value = shader.Glossiness/GLOSS_SCALE
            elif shape.shader_block_name == 'BSEffectShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = shader.falloffStartOpacity

            self.nodes['UV_Offset_U'].outputs['Value'].default_value = shape.shader.UV_Offset_U
            self.nodes['UV_Offset_V'].outputs['Value'].default_value = shape.shader.UV_Offset_V
            self.nodes['UV_Scale_U'].outputs['Value'].default_value = shape.shader.UV_Scale_U
            self.nodes['UV_Scale_V'].outputs['Value'].default_value = shape.shader.UV_Scale_V

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
    

    def make_input_nodes(self):
        """
        Make the value nodes and calculations that are used as input to the shader.
        """
        tc = self.make_node('ShaderNodeTexCoord', xloc=self.calc1_offset_x, yloc=0)
        tc.location = (tc.location[0], 
                       self.bsdf.location.y + 300,)

        self.texmap = self.make_node('ShaderNodeMapping', 
                                     xloc=self.calc2_offset_x, 
                                     yloc=self.bsdf.location.y)
        self.link(tc.outputs['UV'], self.texmap.inputs['Vector'])

        self.ytop = self.bsdf.location.y
        uvou = self.make_node('ShaderNodeValue', name='UV_Offset_U', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        uvov = self.make_node('ShaderNodeValue', name='UV_Offset_V', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        
        xyc = self.make_node('ShaderNodeCombineXYZ', 
            xloc=self.calc1_offset_x, yloc=uvou.location.y)
        self.link(uvou.outputs['Value'], xyc.inputs['X'])
        self.link(uvov.outputs['Value'], xyc.inputs['Y'])
        xyc.inputs['Z'].default_value = 0

        self.link(xyc.outputs['Vector'], self.texmap.inputs['Location'])
        
        uvsu = self.make_node('ShaderNodeValue', name='UV_Scale_U', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT)
        uvsv = self.make_node('ShaderNodeValue', name='UV_Scale_V', xloc=self.inputs_offset_x, height=INPUT_NODE_HEIGHT*2)

        xys = self.make_node('ShaderNodeCombineXYZ', 
            xloc=self.calc1_offset_x, yloc=uvsu.location.y)
        self.link(uvsu.outputs['Value'], xys.inputs['X'])
        self.link(uvsv.outputs['Value'], xys.inputs['Y'])
        xys.inputs['Z'].default_value = 1.0

        self.link(xys.outputs['Vector'], self.texmap.inputs['Scale'])

        if self.shape.shader.properties.bufType == PynBufferTypes.BSLightingShaderPropertyBufType:
            # We feed both "metallic" and "roughness" from glossiness because it looks good.
            gl = self.make_node('ShaderNodeValue', 
                                name='Glossiness', 
                                xloc=self.inputs_offset_x, 
                                height=INPUT_NODE_HEIGHT)
            
            # using the metal input does not seem like a win
            # metalscale = self.make_node('ShaderNodeMapRange', 
            #                             xloc=self.calc1_offset_x,
            #                             yloc=gl.location.y)
            # metalscale.inputs['From Min'].default_value = 0
            # metalscale.inputs['From Max'].default_value = 60
            # metalscale.inputs['To Min'].default_value = 0
            # metalscale.inputs['To Max'].default_value = 1.0
            #self.link(gl.outputs['Value'], metalscale.inputs['Value'])
            #self.link(metalscale.outputs[0], self.bsdf.inputs['Metallic'])

            roughscale = self.make_node('ShaderNodeMapRange', 
                                        xloc=self.calc2_offset_x,
                                        yloc=gl.location.y-50)
            roughscale.inputs['From Min'].default_value = 0
            roughscale.inputs['From Max'].default_value = 200
            roughscale.inputs['To Min'].default_value = 1.0
            roughscale.inputs['To Max'].default_value = 0
            self.link(gl.outputs['Value'], roughscale.inputs['Value'])
            self.link(roughscale.outputs[0], self.bsdf.inputs['Roughness'])
        
        ec = self.make_node('ShaderNodeRGB',
                            name='Emissive_Color',
                            xloc=self.inputs_offset_x, 
                            height=COLOR_NODE_HEIGHT)        
        self.link(ec.outputs['Color'], self.emission_color_skt)
        em = self.make_node('ShaderNodeValue', 
                            name='Emissive_Mult', 
                            xloc=self.inputs_offset_x, 
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
        self.ytop = self.bsdf.location.y

        txtnode = self.make_node("ShaderNodeTexImage",
                                 name='Diffuse_Texture',
                                 xloc=self.bsdf.location[0] + self.img_offset_x,
                                 height=TEXTURE_NODE_HEIGHT)
        try:
            img = bpy.data.images.load(self.textures['Diffuse'], check_existing=True)
            img.colorspace_settings.name = "sRGB"
            txtnode.image = img
        except:
            pass
        self.link(self.texmap.outputs['Vector'], txtnode.inputs['Vector'])

        colornode = None
        if self.colormap:
            colornode = self.make_node("ShaderNodeAttribute", "ColorMap", 
                                      xloc=txtnode.location[0], 
                                      yloc=txtnode.location.y + ATTRIBUTE_NODE_HEIGHT)
            colornode.attribute_name = self.colormap.name
            colornode.attribute_type = "GEOMETRY"
            
            mixnode = new_mixnode(self.material, 
                                  txtnode.outputs['Color'],
                                  colornode.outputs['Color'],
                                  self.bsdf.inputs['Base Color'])
            mixnode.location = (self.inter2_offset_x, 
                                txtnode.location.y - self.offset_y)
            
            self.diffuse_socket = mixnode.outputs['Result']
        else:
            self.diffuse_socket = txtnode.outputs['Color']
            self.link(self.diffuse_socket, self.bsdf.inputs['Base Color'])

        if self.alphamap:
            alphanode = self.make_node("ShaderNodeAttribute", "AlphaMap",
                                      xloc=txtnode.location[0],
                                      yloc=txtnode.location.y + ATTRIBUTE_NODE_HEIGHT)
            alphanode.attribute_name = ALPHA_MAP_NAME
            alphanode.attribute_type = "GEOMETRY"
            if colornode: 
                colornode.location = (colornode.location[0], txtnode.location.y + ATTRIBUTE_NODE_HEIGHT*2)

            m = self.make_node('ShaderNodeMath', 
                               xloc=self.inter1_offset_x,
                               yloc=txtnode.location.y)
            m.operation = 'MULTIPLY'
            self.link(alphanode.outputs['Color'], m.inputs[0])
            self.link(txtnode.outputs['Alpha'], m.inputs[1])
            self.link(m.outputs['Value'], self.bsdf.inputs['Alpha'])

        self.diffuse = txtnode


    def import_subsurface(self):
        """Set up nodes for subsurface texture"""
        #log.debug("Handling subsurface texture")
        if 'SoftLighting' in self.textures and self.shape.textures['SoftLighting']: 
            # Have a sk separate from a specular. Make an image node.
            skimgnode = self.make_node("ShaderNodeTexImage",
                                       name='Subsurface_Texture',
                                       xloc=self.diffuse.location.x,
                                       height=TEXTURE_NODE_HEIGHT)
            try:
                skimg = bpy.data.images.load(self.textures['SoftLighting'], check_existing=True)
                if skimg != self.diffuse.image:
                    skimg.colorspace_settings.name = "Non-Color"
                skimgnode.image = skimg
            except:
                pass
            self.link(self.texmap.outputs['Vector'], skimgnode.inputs['Vector'])

            # Turn on subsurface scattering.
            if 'Subsurface Weight' in self.bsdf.inputs:
                self.bsdf.inputs["Subsurface Weight"].default_value = 1.0
            else:
                # Scale back on subsurface color so it doesn't overwhelm the diffuse.
                self.bsdf.inputs["Subsurface"].default_value = 0.25

            if False: # "Subsurface Color" in self.bsdf.inputs:
                # If there's a color input, connect to that.
                self.link(skimgnode.outputs['Color'], self.bsdf.inputs["Subsurface Color"])
            else:
                # No color input. Let the shader do the scattering, but mix the subsurface
                # color with the base color.
                mixnode = self.make_node('ShaderNodeMix', xloc=self.inter3_offset_x, yloc=self.diffuse.location.y)
                mixnode.blend_type = 'SCREEN'
                mixnode.data_type = 'RGBA'
                mixnode.inputs[0].default_value = 1.0
                self.link(self.diffuse_socket, mixnode.inputs['A'])
                self.link(skimgnode.outputs['Color'], mixnode.inputs['B'])
                self.link(mixnode.outputs['Result'], self.bsdf.inputs['Base Color'])
        else:
            self.bsdf.inputs["Subsurface"].default_value = 0.0
            

    def import_specular(self):
        """Set up nodes for specular texture"""
        if 'Specular' in self.textures and self.shape.textures['Specular']:
            # Make the specular texture input node.
            simgnode = self.make_node("ShaderNodeTexImage",
                                      name='Specular_Texture',
                                      xloc=self.diffuse.location.x,
                                      height=TEXTURE_NODE_HEIGHT)
            try:
                simg = bpy.data.images.load(self.textures['Specular'], check_existing=True)
                simg.colorspace_settings.name = "Non-Color"
                simgnode.image = simg
            except:
                pass
            self.link(self.texmap.outputs['Vector'], simgnode.inputs['Vector'])
            last_node = simgnode

            if self.game in ["FO4"]:
                # specular combines gloss and spec
                invg = self.nodes.new("ShaderNodeInvert")
                invg.location = (self.inter2_offset_x, simgnode.location.y-50)
                self.link(invg.outputs['Color'], self.bsdf.inputs['Roughness'])
                last_node = invg

                try:
                    seprgb = self.make_node("ShaderNodeSeparateColor", 
                                            xloc=self.inter1_offset_x,
                                            yloc=simgnode.location.y)
                    seprgb.mode = 'RGB'
                    self.link(simgnode.outputs['Color'], seprgb.inputs['Color'])
                    spec_socket = seprgb.outputs['Red']
                    self.link(seprgb.outputs['Green'], invg.inputs['Color'])
                except:
                    seprgb = self.nodes.new("ShaderNodeSeparateRGB", 
                                            xloc=self.inter1_offset_x,
                                            yloc=simgnode.location.y)
                    self.link(simgnode.outputs['Color'], seprgb.inputs['Image'])
                    spec_socket = seprgb.outputs['R']
                    self.link(seprgb.outputs['G'], invg.inputs['Color'])

            else:
                # Skyrim just has a specular in the specular.
                spec_socket = simgnode.outputs['Color']

            if 'Specular IOR Level' in self.bsdf.inputs:
                # If there's a direct IOR level input, have to map range 0-1 to 1-2
                tobw = self.make_node('ShaderNodeRGBToBW',
                                      xloc=last_node.location.x + 150,
                                      yloc=simgnode.location.y)
                self.link(spec_socket, tobw.inputs[0])

                map = self.make_node('ShaderNodeMapRange',
                                     xloc=tobw.location.x + 150,
                                     yloc=simgnode.location.y)
                map.inputs['From Min'].default_value = 0
                map.inputs['From Max'].default_value = 1
                map.inputs['To Min'].default_value = 1
                map.inputs['To Max'].default_value = 2

                self.link(tobw.outputs[0], map.inputs[0])
                self.link(map.outputs[0], self.bsdf.inputs['Specular IOR Level'])

            else:
                # Just hook to the specular input.
                self.link(spec_socket, self.bsdf.inputs['Specular'])


    def import_normal(self, shape):
        """Set up nodes for the normal map"""
        #log.debug("Handling normal map texture")
        if 'Normal' in shape.textures and shape.textures['Normal']:
            nimgnode = self.make_node("ShaderNodeTexImage",
                                      name='Normal_Texture',
                                      xloc=self.diffuse.location[0],
                                      height=TEXTURE_NODE_HEIGHT)
            self.link(self.texmap.outputs['Vector'], nimgnode.inputs['Vector'])
            try:
                nimg = bpy.data.images.load(self.textures['Normal'], check_existing=True) 
                nimg.colorspace_settings.name = "Non-Color"
                nimgnode.image = nimg
            except:
                pass

            if shape.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                modelspace_normal(
                    self.material.node_tree,
                    nimgnode.outputs['Color'],
                    self.bsdf.inputs['Normal'],
                    (self.inter1_offset_x,
                        nimgnode.location.y,)
                )
            else: 
                tangent_normal(
                    self.material.node_tree,
                    nimgnode.outputs['Color'],
                    self.bsdf.inputs['Normal'],
                    (self.inter1_offset_x,
                        nimgnode.location.y-100,)
                )
                if shape.file.game in ["SKYRIM", "SKYRIMSE"]:
                    # Specular is in the normal map alpha channel
                    self.link(nimgnode.outputs['Alpha'], self.bsdf.inputs['Specular'])
                

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
                                     xloc=self.diffuse.location[0],
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
                                     xloc=self.diffuse.location[0],
                                     height=TEXTURE_NODE_HEIGHT)
            self.link(self.texmap.outputs['Vector'], imgnode.inputs['Vector'])
            try:
                img = bpy.data.images.load(self.textures['EnvMask'], check_existing=True)
                if img != self.diffuse.image:
                    img.colorspace_settings.name = "Non-Color"
                imgnode.image = img
            except:
                pass

            # Env Mask multiplies with the specular.
            spec_out = self.bsdf.inputs["Specular"].links[0].from_socket
            if spec_out:
                bw = self.make_node("ShaderNodeRGBToBW", 
                                    xloc=self.inter1_offset_x,
                                    yloc=imgnode.location.y-50)
                mult = self.make_node("ShaderNodeMath",
                                    xloc=self.inter2_offset_x,
                                    yloc=imgnode.location.y)
                self.link(imgnode.outputs['Color'], bw.inputs[0])
                self.link(bw.outputs[0], mult.inputs[1])
                self.link(spec_out, mult.inputs[0])
                self.link(mult.outputs[0], self.bsdf.inputs["Specular"])

            

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
        self.bsdf = self.nodes["Principled BSDF"]
        self.ytop = self.bsdf.location.y
        self.inter1_offset_x += self.bsdf.location.x
        self.inter2_offset_x += self.bsdf.location.x
        self.inter3_offset_x += self.bsdf.location.x
        self.inter4_offset_x += self.bsdf.location.x

        # Stash texture strings for future export
        for k, t in shape.textures.items():
            if t:
                self.material['BSShaderTextureSet_' + k] = t

        self.find_textures(shape)

        self.make_input_nodes()
        self.import_shader_attrs(shape)
        self.colormap, self.alphamap = get_effective_colormaps(obj.data)

        self.import_diffuse()
        self.import_subsurface()
        self.import_specular()
        self.import_normal(shape)
        self.import_envmap()
        self.import_envmask()
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
    val = False
    if obj.active_material:
        nodelist = obj.active_material.node_tree.nodes
        shader_node = None
        if "Material Output" in nodelist:
            mat_out = nodelist["Material Output"]
            if mat_out.inputs["Surface"].is_linked:
                shader_node = mat_out.inputs['Surface'].links[0].from_node
        if shader_node:
            normal_input = shader_node.inputs['Normal']
            if normal_input and normal_input.is_linked:
                nmap_node = normal_input.links[0].from_node
                if nmap_node.bl_idname == 'ShaderNodeNormalMap' and nmap_node.space == "OBJECT":
                    val = True
    return val


class ShaderExporter:
    def __init__(self, blender_obj):
        self.obj = blender_obj
        self.is_obj_space = False  # Object vs. tangent normals
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
                mat_out = nodelist["Material Output"]
                if mat_out.inputs['Surface'].is_linked:
                    self.shader_node = mat_out.inputs['Surface'].links[0].from_node
                if not self.shader_node:
                    log.warning(f"Have material but no shader node for {self.material.name}")

            if self.shader_node:
                normal_input = self.shader_node.inputs['Normal']
                if normal_input and normal_input.is_linked:
                    nmap_node = normal_input.links[0].from_node
                    self.is_obj_space = nmap_node.name.startswith(MSN_GROUP_NAME)

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


    def get_diffuse(self):
        """Get the diffuse filepath, given the material's shader node."""
        try:
            # imgnode = get_image_node(self.shader_node.inputs['Base Color'])
            imgnode = self.material.node_tree.nodes['Diffuse_Texture']
            return imgnode.image.filepath
        except:
            self.warn("Could not find diffuse filepath")
        return ''
    

    def get_normal(self):
        """
        Get the normal map filepath, given the shader node.
        """
        try:
            image_node = find_node(self.bsdf.inputs['Normal'], "ShaderNodeTexImage")
            normalmap = find_node(self.bsdf.inputs['Normal'], "ShaderNodeNormalMap")
            image_node = self.material.node_tree.nodes['Normal_Texture']
            return image_node.image.filepath
        except:
            self.warn("Could not find normal filepath")
        return ''
    

    def get_subsurface(self):
        try:
            if 'Subsurface_Texture' in self.material.node_tree.nodes:
                return self.material.node_tree.nodes['Subsurface_Texture'].image.filepath
            # if self.is_obj_space:
            #     return get_image_filepath(self.shader_node.inputs['Specular'])
        except:
            self.warn("Could not find subsurface texture filepath")
        return ''


    def get_specular(self):
        try:
            if 'Specular_Texture' in self.material.node_tree.nodes:
                return self.material.node_tree.nodes['Specular_Texture'].image.filepath
            # if self.is_obj_space:
            #     return get_image_filepath(self.shader_node.inputs['Specular'])
        except:
            self.warn("Could not find specular filepath")
        return ''


    @property
    def is_effectshader(self):
        try:
            return self.material['BS_Shader_Block_Name'] == 'BSEffectShaderProperty'
        except:
            pass
        return False
    

    slotdict = {'Diffuse': 'Base Color',
                'SoftLighting': 'Subsurface Color',
                'Specular': 'Specular',
                'Normal': 'Normal'}

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
        else:
            imagenode = find_node(self.shader_node.inputs[self.slotdict[textureslot]], "ShaderNodeTexImage")
        
        if imagenode:
            if textureslot == 'Specular':
                # Check to see if the specular is coming from the normal texture. If so,
                # don't use it.
                normnode = find_node(self.shader_node.inputs["Normal"], "ShaderNodeTexImage")
                if normnode == imagenode:
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

        for textureslot in ['Diffuse', 'Normal', 'SoftLighting', 'Specular', 'EnvMap', 'EnvMask']:
            self.write_texture(shape, textureslot)

        # Write alpha if any after the textures
        try:
            alpha_input = self.shader_node.inputs['Alpha']
            if alpha_input and alpha_input.is_linked and self.material:
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

