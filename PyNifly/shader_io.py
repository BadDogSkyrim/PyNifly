"""Shader Import/Export for pyNifly"""

# Copyright © 2021, Bad Dog.

import os
from pathlib import Path
import logging
import bpy
from pynifly import *

ALPHA_MAP_NAME = "VERTEX_ALPHA"
GLOSS_SCALE = 100
ATTRIBUTE_NODE_HEIGHT = 200
TEXTURE_NODE_WIDTH = 400
TEXTURE_NODE_HEIGHT = 290

NISHADER_IGNORE = ['bufSize', 
                   'bufType', 
                   'nameID', 
                   'controllerID', 
                   'UV_Offset_U',
                   'UV_Offset_V',
                   'UV_Scale_U',
                   'UV_Scale_V',
                   ]

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
        mixnode.inputs['Fac'].default_value = 1

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
        self.game = None

        self.inputs_offset_x = -1900
        self.calc1_offset_x = -1700
        self.calc2_offset_x = -1500
        self.img_offset_x = -1200
        self.cvt_offset_x = -300
        self.inter1_offset_x = -900
        self.inter2_offset_x = -700
        self.inter3_offset_x = -500
        self.offset_y = -300
        self.gap_y = 10
        self.yloc = 0
        self.ytop = 0

        self.log = logging.getLogger("pynifly")

    
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
            self.bsdf.inputs['Emission'].default_value = shader.Emissive_Color
            self.bsdf.inputs['Emission Strength'].default_value = shader.Emissive_Mult

            if shader.blockname == 'BSLightingShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = shader.Alpha
                self.bsdf.inputs['Metallic'].default_value = shader.Glossiness/GLOSS_SCALE
            elif shape.shader_block_name == 'BSEffectShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = shader.Falloff_Start_Opacity

            self.nodes['UV_Offset_U'].outputs['Value'].default_value = shape.shader.UV_Offset_U
            self.nodes['UV_Offset_V'].outputs['Value'].default_value = shape.shader.UV_Offset_V
            self.nodes['UV_Scale_U'].outputs['Value'].default_value = shape.shader.UV_Scale_U
            self.nodes['UV_Scale_V'].outputs['Value'].default_value = shape.shader.UV_Scale_V

        except Exception as e:
            # Any errors, print the error but continue
            log.warning(str(e))


    def make_node(self, nodetype, name=None, xloc=0, yloc=0, height=300):
        """
        Make a node.If yloc not provided, use and increment the current ytop location.
        xloc is relative to the BSDF node. Have to pass the height in because Blender's
        height isn't correct.
        """
        n = self.nodes.new(nodetype)
        if yloc:
            n.location = (self.bsdf.location[0] + xloc, yloc)
        else:
            n.location = (self.bsdf.location[0] + xloc, self.ytop)
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
                       self.bsdf.location[1] + 300,)

        self.texmap = self.make_node('ShaderNodeMapping', xloc=self.calc2_offset_x, yloc=0)
        self.link(tc.outputs['UV'], self.texmap.inputs['Vector'])

        self.ytop = self.bsdf.location[1]
        uvou = self.make_node('ShaderNodeValue', name='UV_Offset_U', xloc=self.inputs_offset_x)
        uvov = self.make_node('ShaderNodeValue', name='UV_Offset_V', xloc=self.inputs_offset_x)
        
        xyc = self.make_node('ShaderNodeCombineXYZ', 
            xloc=self.calc1_offset_x, yloc=uvou.location[1])
        self.link(uvou.outputs['Value'], xyc.inputs['X'])
        self.link(uvov.outputs['Value'], xyc.inputs['Y'])
        xyc.inputs['Z'].default_value = 0

        self.link(xyc.outputs['Vector'], self.texmap.inputs['Location'])
        
        uvsu = self.make_node('ShaderNodeValue', name='UV_Scale_U', xloc=self.inputs_offset_x)
        uvsv = self.make_node('ShaderNodeValue', name='UV_Scale_V', xloc=self.inputs_offset_x)

        xys = self.make_node('ShaderNodeCombineXYZ', 
            xloc=self.calc1_offset_x, yloc=uvsu.location[1])
        self.link(uvsu.outputs['Value'], xys.inputs['X'])
        self.link(uvsv.outputs['Value'], xys.inputs['Y'])
        xys.inputs['Z'].default_value = 1.0

        self.link(xys.outputs['Vector'], self.texmap.inputs['Scale'])
        

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
        if blender_dir.lower().endswith('textures'):
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
        txtnode = self.nodes.new("ShaderNodeTexImage")
        try:
            img = bpy.data.images.load(self.textures['Diffuse'], check_existing=True)
            img.colorspace_settings.name = "sRGB"
            txtnode.image = img
        except:
            pass
        txtnode.location = (self.bsdf.location[0] + self.img_offset_x, self.bsdf.location[1])
        self.link(self.texmap.outputs['Vector'], txtnode.inputs['Vector'])

        colornode = None
        if self.colormap:
            colornode = self.make_node("ShaderNodeAttribute", "ColorMap", 
                                      xloc=txtnode.location[0], 
                                      yloc=txtnode.location[1] + ATTRIBUTE_NODE_HEIGHT)
            
            mixnode = new_mixnode(self.material, 
                                  txtnode.outputs['Color'],
                                  colornode.outputs['Color'],
                                  self.bsdf.inputs['Base Color'])
            mixnode.location = (self.bsdf.location[0] + self.inter1_offset_x, 
                                txtnode.location[1] - self.offset_y)
            colornode.attribute_name = self.colormap.name
            colornode.attribute_type = "GEOMETRY"
            self.ytop = colornode.location[1]
        else:
            self.link(txtnode.outputs['Color'], self.bsdf.inputs['Base Color'])

        if self.alphamap:
            attrnode = self.make_node("ShaderNodeAttribute", "AlphaMap",
                                      xloc=txtnode.location[0],
                                      yloc=txtnode.location[1] + ATTRIBUTE_NODE_HEIGHT)
            attrnode.attribute_name = ALPHA_MAP_NAME
            attrnode.attribute_type = "GEOMETRY"
            if colornode: 
                colornode.location = (colornode.location[0], txtnode.location[1] + ATTRIBUTE_NODE_HEIGHT*2)

            # Magic values make the khajiit head look good. Check against other meshes.
            mapnode1 = self.make_node("ShaderNodeMapRange",
                                      xloc=self.bsdf.location[0] + self.inter1_offset_x,
                                      yloc=txtnode.location[1])
            mapnode1.inputs['From Min'].default_value = 0.29
            mapnode1.inputs['From Max'].default_value = 0.8
            self.link(attrnode.outputs['Color'], mapnode1.inputs['Value'])
            
            mapnode2 = self.make_node("ShaderNodeMapRange",
                                      xloc=self.bsdf.location[0] + self.inter2_offset_x,
                                      yloc = txtnode.location[1])
            mapnode2.inputs['From Min'].default_value = 0.4
            mapnode2.inputs['To Max'].default_value = 0.38
            self.link(mapnode1.outputs['Result'], mapnode2.inputs['To Min'])
            self.link(txtnode.outputs['Alpha'], mapnode2.inputs['Value'])
            self.link(mapnode2.outputs['Result'], self.bsdf.inputs['Alpha'])

            self.ytop = attrnode.location[1]
            
        self.yloc = txtnode.location[1] + self.offset_y
        self.diffuse = txtnode


    def import_subsurface(self):
        """Set up nodes for subsurface texture"""
        #log.debug("Handling subsurface texture")
        if 'SoftLighting' in self.textures: 
            # Have a sk separate from a specular
            skimgnode = self.nodes.new("ShaderNodeTexImage")
            try:
                skimg = bpy.data.images.load(self.textures['SoftLighting'], check_existing=True)
                if skimg != self.diffuse.image:
                    skimg.colorspace_settings.name = "Non-Color"
                skimgnode.image = skimg
            except:
                pass
            skimgnode.location = (self.diffuse.location[0], self.yloc)
            self.link(self.texmap.outputs['Vector'], skimgnode.inputs['Vector'])
            self.link(skimgnode.outputs['Color'], self.bsdf.inputs["Subsurface Color"])
            self.yloc = skimgnode.location[1] + self.offset_y
            

    def import_specular(self):
        """Set up nodes for specular texture"""
        #log.debug("Handling specular texture")
        if 'Specular' in self.textures:
            simgnode = self.nodes.new("ShaderNodeTexImage")
            try:
                simg = bpy.data.images.load(self.textures['Specular'], check_existing=True)
                simg.colorspace_settings.name = "Non-Color"
                simgnode.image = simg
            except:
                pass
            simgnode.location = (self.diffuse.location[0], self.yloc)
            self.link(self.texmap.outputs['Vector'], simgnode.inputs['Vector'])

            if self.game in ["FO4"]:
                # specular combines gloss and spec
                invg = self.nodes.new("ShaderNodeInvert")
                invg.location = (self.bsdf.location[0] + self.cvt_offset_x, self.yloc)
                self.link(invg.outputs['Color'], self.bsdf.inputs['Roughness'])

                try:
                    seprgb = self.nodes.new("ShaderNodeSeparateColor")
                    seprgb.mode = 'RGB'
                    self.link(simgnode.outputs['Color'], seprgb.inputs['Color'])
                    self.link(seprgb.outputs['Red'], self.bsdf.inputs['Specular'])
                    self.link(seprgb.outputs['Green'], invg.inputs['Color'])
                except:
                    seprgb = self.nodes.new("ShaderNodeSeparateRGB")
                    self.link(simgnode.outputs['Color'], seprgb.inputs['Image'])
                    self.link(seprgb.outputs['R'], self.bsdf.inputs['Specular'])
                    self.link(seprgb.outputs['G'], invg.inputs['Color'])

                seprgb.location = (self.bsdf.location[0] + 2*self.cvt_offset_x, self.yloc)
            else:
                self.link(simgnode.outputs['Color'], self.bsdf.inputs['Specular'])
                
            self.yloc = simgnode.location[1] + self.offset_y


    def import_normal(self, shape):
        """Set up nodes for the normal map"""
        #log.debug("Handling normal map texture")
        if 'Normal' in shape.textures:
            nmap = self.nodes.new("ShaderNodeNormalMap")
            if shape.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                nmap.space = "OBJECT"
            else:
                nmap.space = "TANGENT"
            nmap.location = (self.bsdf.location[0] + self.cvt_offset_x, self.yloc)
            
            nimgnode = self.nodes.new("ShaderNodeTexImage")
            try:
                nimg = bpy.data.images.load(self.textures['Normal'], check_existing=True) 
                nimg.colorspace_settings.name = "Non-Color"
                nimgnode.image = nimg
            except:
                pass
            nimgnode.location = (self.diffuse.location[0], self.yloc)
            self.link(self.texmap.outputs['Vector'], nimgnode.inputs['Vector'])
            
            if shape.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                # Need to swap green and blue channels for blender
                try:
                    # 3.3 
                    rgbsep = self.nodes.new("ShaderNodeSeparateColor")
                    rgbsep.mode = 'RGB'
                    rgbcomb = self.nodes.new("ShaderNodeCombineColor")
                    rgbcomb.mode = 'RGB'
                    self.link(rgbsep.outputs['Red'], rgbcomb.inputs['Red'])
                    self.link(rgbsep.outputs['Green'], rgbcomb.inputs['Blue'])
                    self.link(rgbsep.outputs['Blue'], rgbcomb.inputs['Green'])
                    self.link(rgbcomb.outputs['Color'], nmap.inputs['Color'])
                    self.link(nimgnode.outputs['Color'], rgbsep.inputs['Color'])
                except:
                    # < 3.3
                    rgbsep = self.nodes.new("ShaderNodeSeparateRGB")
                    rgbcomb = self.nodes.new("ShaderNodeCombineRGB")
                    self.link(rgbsep.outputs['R'], rgbcomb.inputs['R'])
                    self.link(rgbsep.outputs['G'], rgbcomb.inputs['B'])
                    self.link(rgbsep.outputs['B'], rgbcomb.inputs['G'])
                    self.link(rgbcomb.outputs['Image'], nmap.inputs['Color'])
                    self.link(nimgnode.outputs['Color'], rgbsep.inputs['Image'])
                rgbsep.location = (self.bsdf.location[0] + self.inter1_offset_x, self.yloc)
                rgbcomb.location = (self.bsdf.location[0] + self.inter2_offset_x, self.yloc)

            elif shape.file.game in ['FO4', 'FO76']:
                # Need to invert the green channel for blender
                try:
                    rgbsep = self.nodes.new("ShaderNodeSeparateColor")
                    rgbsep.mode = 'RGB'
                    rgbcomb = self.nodes.new("ShaderNodeCombineColor")
                    rgbcomb.mode = 'RGB'
                    colorinv = self.nodes.new("ShaderNodeInvert")
                    self.link(rgbsep.outputs['Red'], rgbcomb.inputs['Red'])
                    self.link(rgbsep.outputs['Blue'], rgbcomb.inputs['Blue'])
                    self.link(rgbsep.outputs['Green'], colorinv.inputs['Color'])
                    self.link(colorinv.outputs['Color'], rgbcomb.inputs['Green'])
                    self.link(rgbcomb.outputs['Color'], nmap.inputs['Color'])
                    self.link(nimgnode.outputs['Color'], rgbsep.inputs['Color'])
                except:
                    rgbsep = self.nodes.new("ShaderNodeSeparateRGB")
                    rgbcomb = self.nodes.new("ShaderNodeCombineRGB")
                    colorinv = self.nodes.new("ShaderNodeInvert")
                    self.link(rgbsep.outputs['R'], rgbcomb.inputs['R'])
                    self.link(rgbsep.outputs['B'], rgbcomb.inputs['B'])
                    self.link(rgbsep.outputs['G'], colorinv.inputs['Color'])
                    self.link(colorinv.outputs['Color'], rgbcomb.inputs['G'])
                    self.link(rgbcomb.outputs['Image'], nmap.inputs['Color'])
                    self.link(nimgnode.outputs['Color'], rgbsep.inputs['Image'])

                rgbsep.location = (self.bsdf.location[0] + self.inter1_offset_x, self.yloc)
                rgbcomb.location = (self.bsdf.location[0] + self.inter3_offset_x, self.yloc)
                colorinv.location = (self.bsdf.location[0] + self.inter2_offset_x, self.yloc - rgbcomb.height * 0.9)
            else:
                self.link(nimgnode.outputs['Color'], nmap.inputs['Color'])
                nmap.location = (self.bsdf.location[0] + self.inter2_offset_x, self.yloc)
                            
            self.link(nmap.outputs['Normal'], self.bsdf.inputs['Normal'])

            if shape.file.game in ["SKYRIM", "SKYRIMSE"] and \
                not shape.shader.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                # Specular is in the normal map alpha channel
                self.link(nimgnode.outputs['Alpha'], self.bsdf.inputs['Specular'])
                

    def import_material(self, obj, shape:NiShape):
        """
        Import the shader info from shape and create a Blender representation using shader
        nodes.
        """
        if obj.type == 'EMPTY': return 

        self.game = shape.file.game

        self.material = bpy.data.materials.new(name=(obj.name + ".Mat"))
        self.material.use_nodes = True
        self.nodes = self.material.node_tree.nodes
        self.bsdf = self.nodes["Principled BSDF"]
        self.ytop = self.bsdf.location[1]

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
        self.normal_node = None
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
                    if nmap_node.bl_idname == 'ShaderNodeNormalMap':
                        self.normal_node = nmap_node
                        self.is_obj_space = (nmap_node.space == "OBJECT")

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

            for i in range(0, 4):
                shape.shader.Emissive_Color[i] = self.shader_node.inputs['Emission'].default_value[i]

            if shape.shader.blockname == "BSLightingShaderProperty":
                shape.shader.Alpha = self.shader_node.inputs['Alpha'].default_value
                shape.shader.Glossiness = self.shader_node.inputs['Metallic'].default_value * GLOSS_SCALE

            shape.save_shader_attributes()
            
        except:
            self.warn("Could not determine shader attributes")


    def get_diffuse(self):
        """Get the diffuse filepath, given the material's shader node."""
        try:
            imgnode = get_image_node(self.shader_node.inputs['Base Color'])
            return imgnode.image.filepath
        except:
            self.warn("Could not find diffuse filepath")
        return ''
    

    def get_normal(self):
        """
        Get the normal map filepath, given the shader node.
        """
        try:
            image_node = get_image_node(self.normal_node.inputs['Color'])
            return image_node.image.filepath
        except:
            self.warn("Could not find normal filepath")
        return ''
    

    def get_specular(self):
        try:
            if self.is_obj_space:
                return get_image_filepath(self.shader_node.inputs['Specular'])
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
    

    def write_texture(self, shape, textureslot:str):
        foundpath = ""
    
        try:
            if textureslot == 'Diffuse':
                foundpath = self.get_diffuse()
            elif textureslot == 'Normal':
                foundpath = self.get_normal()
            elif textureslot == 'SoftLighting':
                foundpath = get_image_filepath(self.shader_node.inputs['Subsurface Color'])
            elif textureslot == 'Specular':
                foundpath = self.get_specular()
        except:
            self.warn("Could not follow shader nodes to find texture files")
            foundpath = ""

        # Use the shader node path if it's usable. The path stashed in 
        # custom properties is already there if not.
        if foundpath:
            #log.debug(f"Writing texture: '{foundpath}'")
            try:
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
        # else:
        #     log.debug(f"No texture in slot {textureslot}: '{foundpath}'")


    def export_textures(self, shape: NiShape):
        """Create shader in nif from the blender object's material"""
        # Use textures stored in properties as defaults; override them with shader nodes
        set_object_textures(shape, self.material)

        if not self.shader_node: return

        for textureslot in ['Diffuse', 'Normal', 'SoftLighting', 'Specular']:
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

