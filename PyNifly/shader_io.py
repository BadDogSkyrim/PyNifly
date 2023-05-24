"""Shader Import/Export for pyNifly"""

# Copyright © 2021, Bad Dog.

import os
from pathlib import Path
import logging
import bpy
from pynifly import *

ALPHA_MAP_NAME = "VERTEX_ALPHA"
GLOSS_SCALE = 100


def get_effective_colormaps(mesh):
    """ Return the colormaps we want to use
        Returns (colormap, alphamap)
        Either may be null
        """
    if not mesh:
        return None, None
    if not mesh.color_attributes:
        return None, None

    vc = mesh.color_attributes
    am = None
    cm = vc.active_color

    if vc.active_color.name == ALPHA_MAP_NAME:
        cm = None
        if vc[0] == ALPHA_MAP_NAME and len(vc) > 1:
            cm = vc[1]
        else:
            cm = vc[0]

    if ALPHA_MAP_NAME in vc.keys():
        am = vc[ALPHA_MAP_NAME]

    return cm, am


class ShaderImporter:
    def __init__(self):
        self.material = None
        self.shape = None
        self.colormap = None
        self.alphamap = None
        self.bsdf = None
        self.nodes = None
        self.textures = []
        self.diffuse = None
        self.game = None

        self.img_offset_x = -1200
        self.cvt_offset_x = -300
        self.inter1_offset_x = -900
        self.inter2_offset_x = -700
        self.inter3_offset_x = -500
        self.offset_y = -300
        self.yloc = 0
        self.ytop = 0

        self.log = logging.getLogger("pynifly")

    
    def import_shader_attrs(self, shape:NiShape):
        """
        Import the shader attributes associated with the shape. All attributes are stored
        as properties on the material; attributes that have Blender equivalents are used
        to set up Blender nodes and properties.
        """
        attrs = shape.shader_attributes
        if not attrs: 
            return

        attrs.extract(self.material)

        try:
            self.material['BS_Shader_Block_Name'] = shape.shader_block_name
            self.material['BSLSP_Shader_Name'] = shape.shader_name
            self.bsdf.inputs['Emission'].default_value = (attrs.Emissive_Color_R, attrs.Emissive_Color_G, attrs.Emissive_Color_B, attrs.Emissive_Color_A)
            self.bsdf.inputs['Emission Strength'].default_value = attrs.Emissive_Mult

            if shape.shader_block_name == 'BSLightingShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = attrs.Alpha
                self.bsdf.inputs['Metallic'].default_value = attrs.Glossiness/GLOSS_SCALE
            elif shape.shader_block_name == 'BSEffectShaderProperty':
                self.bsdf.inputs['Alpha'].default_value = attrs.Falloff_Start_Opacity

        except Exception as e:
            # Any errors, print the error but continue
            log.warning(str(e))


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
        * self.textures <- list of filepaths to use.
        """
        # log.debug(f"<find_textures>")
        self.textures = [''] * 10

        # Use any textures from Blender's texture directory, if defined
        btextures = None
        blender_dir = bpy.context.preferences.filepaths.texture_directory
        if os.path.exists(blender_dir):
            # log.debug(f"Blender texture directory: {blender_dir}")
            btextures = extend_filenames(blender_dir, None, shape.textures)
            # log.debug(f"Blender textures: {btextures}")

        # Extend relative filenames in nif with nif's own filepath
        fulltextures = extend_filenames(shape.file.filepath, "meshes", shape.textures)
        log.debug(f"fulltextures = {fulltextures}")
        for i in range(0, len(shape.textures)):
            # First option is to use a png from Blender's texture directory, if any
            if btextures and btextures[i]:
                fpng = Path(btextures[i]).with_suffix('.png')
                # log.debug(f"Looking for {fpng}")
                if os.path.exists(fpng):
                    self.textures[i] = str(fpng)
                    continue

            if fulltextures[i]:
                fpng = Path(fulltextures[i]).with_suffix('.png')
                # log.debug(f"Looking for {fpng}")
                if os.path.exists(fpng):
                    self.textures[i] = str(fpng)
                    continue
            
            # log.debug(f"Looking for {btextures[i] if btextures else None}")
            if btextures and btextures[i] and os.path.exists(btextures[i]):
                self.textures[i] = btextures[i]
            
            log.debug(f"Looking for {fulltextures[i] if fulltextures else None}")
            if fulltextures[i] and os.path.exists(fulltextures[i]):
                self.textures[i] = fulltextures[i]

        # log.debug(f"Found textures {self.textures}")
            

    def link(self, a, b):
        """Create a link between two nodes"""
        self.material.node_tree.links.new(a, b)


    def import_diffuse(self):
        """Create nodes for the diffuse texture."""
        log.debug("Handling diffuse texture")
        txtnode = self.nodes.new("ShaderNodeTexImage")
        try:
            img = bpy.data.images.load(self.textures[0], check_existing=True)
            img.colorspace_settings.name = "sRGB"
            txtnode.image = img
        except:
            pass
        txtnode.location = (self.bsdf.location[0] + self.img_offset_x, self.bsdf.location[1])

        if self.colormap:
            log.debug(f"Have colormap: {self.colormap}")
            attrnode = self.nodes.new("ShaderNodeAttribute")
            attrnode.location = (txtnode.location[0], 
                                 self.ytop - attrnode.height - self.offset_y)
            
            mixnode = self.nodes.new("ShaderNodeMix")
            mixnode.data_type = 'RGBA'
            mixnode.location = (attrnode.location[0] - self.inter2_offset_x, txtnode.location[1])
            self.link(txtnode.outputs['Color'], mixnode.inputs[6])
            self.link(attrnode.outputs['Color'], mixnode.inputs[7])
            self.link(mixnode.outputs[2], self.bsdf.inputs['Base Color'])
            attrnode.attribute_name = self.colormap.name
            attrnode.attribute_type = "GEOMETRY"
            mixnode.blend_type = 'MULTIPLY'
            mixnode.inputs['Factor'].default_value = 1
            self.ytop = attrnode.location[1]
        else:
            self.link(txtnode.outputs['Color'], self.bsdf.inputs['Base Color'])

        if self.alphamap:
            attrnode = self.nodes.new("ShaderNodeAttribute")
            attrnode.attribute_name = ALPHA_MAP_NAME
            attrnode.attribute_type = "GEOMETRY"
            attrnode.location = (txtnode.location[0], 
                                 self.ytop - attrnode.height - self.offset_y)

            # Magic values make the khajiit head look good. Check against other meshes.
            mapnode1 = self.nodes.new("ShaderNodeMapRange")
            mapnode1.inputs['From Min'].default_value = 0.29
            mapnode1.inputs['From Max'].default_value = 0.8
            mapnode1.location = (attrnode.location[0] - self.inter2_offset_x, 
                                 attrnode.location[1])
            self.link(attrnode.outputs['Color'], mapnode1.inputs['Value'])
            
            mapnode2 = self.nodes.new("ShaderNodeMapRange")
            mapnode2.inputs['From Min'].default_value = 0.4
            mapnode2.inputs['To Max'].default_value = 0.38
            mapnode2.location = (attrnode.location[0] - self.inter1_offset_x, 
                                 attrnode.location[1])
            self.link(mapnode1.outputs['Result'], mapnode2.inputs['To Min'])
            self.link(txtnode.outputs['Alpha'], mapnode2.inputs['Value'])
            self.link(mapnode2.outputs['Result'], self.bsdf.inputs['Alpha'])

            self.ytop = attrnode.location[1]
            
        self.yloc = txtnode.location[1] + self.offset_y
        self.diffuse = txtnode


    def import_subsurface(self):
        """Set up nodes for subsurface texture"""
        log.debug("Handling subsurface texture")
        if len(self.textures) > 2 and self.textures[2]: 
            # Have a sk separate from a specular
            skimgnode = self.nodes.new("ShaderNodeTexImage")
            try:
                skimg = bpy.data.images.load(self.textures[2], check_existing=True)
                if skimg != self.diffuse.image:
                    skimg.colorspace_settings.name = "Non-Color"
                skimgnode.image = skimg
            except:
                pass
            skimgnode.location = (self.diffuse.location[0], self.yloc)
            self.link(skimgnode.outputs['Color'], self.bsdf.inputs["Subsurface Color"])
            self.yloc = skimgnode.location[1] + self.offset_y
            

    def import_specular(self):
        """Set up nodes for specular texture"""
        log.debug("Handling specular texture")
        if len(self.textures) > 7 and self.textures[7]:
            simgnode = self.nodes.new("ShaderNodeTexImage")
            try:
                simg = bpy.data.images.load(self.textures[7], check_existing=True)
                simg.colorspace_settings.name = "Non-Color"
                simgnode.image = simg
            except:
                pass
            simgnode.location = (self.diffuse.location[0], self.yloc)

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
        log.debug("Handling normal map texture")
        if shape.textures[1]:
            nmap = self.nodes.new("ShaderNodeNormalMap")
            if shape.shader_attributes and shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
                nmap.space = "OBJECT"
            else:
                nmap.space = "TANGENT"
            nmap.location = (self.bsdf.location[0] + self.cvt_offset_x, self.yloc)
            
            nimgnode = self.nodes.new("ShaderNodeTexImage")
            try:
                nimg = bpy.data.images.load(self.textures[1], check_existing=True) 
                nimg.colorspace_settings.name = "Non-Color"
                nimgnode.image = nimg
            except:
                pass
            nimgnode.location = (self.diffuse.location[0], self.yloc)
            
            if shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
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
                shape.shader_attributes and \
                not shape.shader_attributes.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS):
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
        for i, t in enumerate(shape.textures):
            self.material['BSShaderTextureSet_' + str(i)] = t

        self.find_textures(shape)

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
    for i in range(0, 20):
        prop = 'BSShaderTextureSet_' + str(i)
        if mat and prop in mat:
            shape.set_texture(i, mat[prop])

    
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
    n = get_image_node(node_input)
    try:
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


    def export_shader_attrs(self, shape):
        if not self.material:
            return
        
        if 'BSLSP_Shader_Name' in self.material and self.material['BSLSP_Shader_Name']:
            shape.shader_name = self.material['BSLSP_Shader_Name']

        shape.shader_attributes.load(self.material)

        shape.shader_attributes.Emissive_Color_R = self.shader_node.inputs['Emission'].default_value[0]
        shape.shader_attributes.Emissive_Color_G = self.shader_node.inputs['Emission'].default_value[1]
        shape.shader_attributes.Emissive_Color_B = self.shader_node.inputs['Emission'].default_value[2]
        shape.shader_attributes.Emissive_Color_A = self.shader_node.inputs['Emission'].default_value[3]
        shape.shader_attributes.Emissive_Mult = self.shader_node.inputs['Emission Strength'].default_value

        if shape.shader_block_name == "BSLightingShaderProperty":
            shape.shader_attributes.Alpha = self.shader_node.inputs['Alpha'].default_value
            shape.shader_attributes.Glossiness = self.shader_node.inputs['Metallic'].default_value * GLOSS_SCALE


    def get_diffuse(self):
        """Get the diffuse filepath, given the material's shader node."""
        imgnode = get_image_node(self.shader_node.inputs['Base Color'])
        if imgnode:
            try:
                return imgnode.image.filepath
            except:
                pass
        return ''
    

    def get_normal(self):
        """
        Get the normal map filepath, given the shader node.
        """
        if self.normal_node:
            image_node = get_image_node(self.normal_node.inputs['Color'])
            if image_node and image_node.image:
                try:
                    return image_node.image.filepath
                except:
                    pass
        return ''
    

    def get_specular(self):
        if self.is_obj_space:
            return get_image_filepath(self.shader_node.inputs['Specular'])
        return ''


    @property
    def is_effectshader(self):
        if self.material and 'BS_Shader_Block_Name' in self.material:
            return self.material['BS_Shader_Block_Name'] == 'BSEffectShaderProperty'
        return False
    

    def write_texture(self, shape, textureslot:int):
        foundpath = ""
    
        if textureslot == 0:
            foundpath = self.get_diffuse()
        elif textureslot == 1:
            foundpath = self.get_normal()
        elif textureslot == 2:
            foundpath = get_image_filepath(self.shader_node.inputs['Subsurface Color'])
        elif textureslot == 7:
            foundpath = self.get_specular()

        # Use the shader node path if it's usable. The path stashed in 
        # custom properties is already there if not.
        if foundpath:
            log.debug(f"Writing texture: '{foundpath}'")
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
                log.warning(f"No 'textures' folder found in path: {foundpath}")
        # else:
        #     log.debug(f"No texture in slot {textureslot}: '{foundpath}'")


    def export_textures(self, shape: NiShape):
        """Create shader in nif from the blender object's material"""
        # Use textures stored in properties as defaults; override them with shader nodes
        set_object_textures(shape, self.material)

        if not self.shader_node: return

        for textureslot in range(0, 9):
            self.write_texture(shape, textureslot)

        # Write alpha if any after the textures
        alpha_input = self.shader_node.inputs['Alpha']
        if alpha_input and alpha_input.is_linked and self.material:
            if 'NiAlphaProperty_flags' in self.material:
                shape.alpha_property.flags = self.material['NiAlphaProperty_flags']
            else:
                shape.alpha_property.flags = 4844
            shape.alpha_property.threshold = int(self.material.alpha_threshold * 255)
            shape.save_alpha_property()


    def export(self, new_shape:NiShape):
        self.export_textures(new_shape)
        self.export_shader_attrs(new_shape)
        if self.is_obj_space:
            new_shape.shader_attributes.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
        else:
            new_shape.shader_attributes.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)

        log.debug(f"Exporting vertex color flag: {self.vertex_colors}")
        if self.vertex_colors:
            new_shape.shader_attributes.shaderflags2_set(ShaderFlags2.VERTEX_COLORS)
        else:
            new_shape.shader_attributes.shaderflags2_clear(ShaderFlags2.VERTEX_COLORS)

        if self.vertex_alpha:
            new_shape.shader_attributes.shaderflags1_set(ShaderFlags1.VERTEX_ALPHA)
        else:
            new_shape.shader_attributes.shaderflags1_clear(ShaderFlags1.VERTEX_ALPHA)
            
        new_shape.save_shader_attributes()

