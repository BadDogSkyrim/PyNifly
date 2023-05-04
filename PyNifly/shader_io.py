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

    if vc.active_color_name == ALPHA_MAP_NAME:
        cm = None
        if vc[0] == ALPHA_MAP_NAME and len(vc) > 1:
            cm = vc[1]
        else:
            cm = vc[0]

    if ALPHA_MAP_NAME in vc.keys():
        am = vc[ALPHA_MAP_NAME]

    return cm, am


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

class ShaderImporter:
    def __init__(self):
        self.material = None
        self.shape = None
        self.colormap = None
        self.alpha_colormap = None
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


    def find_textures(self, shape:NiShape):
        """
        Locate the textures referenced in the nif. Look for them in the nif's own filetree
        (if the nif is in a filetree). Otherwise look in Blender's texture directory if
        defined. If the texture file exists with a PNG extension, use that in preference
        to the DDS file.

        * shape = shape to read for texture files
        * self.textures <- list of filepaths to use.
        """
        self.textures = [''] * 10

        # Use any textures from Blender's texture directory, if defined
        btextures = None
        blender_dir = bpy.context.preferences.filepaths.texture_directory
        if os.path.exists(blender_dir):
            btextures = extend_filenames(blender_dir, None, shape.textures)

        # Extend relative filenames in nif with nif's own filepath
        fulltextures = extend_filenames(shape.file.filepath, "meshes", shape.textures)

        for i in range(0, len(shape.textures)):
            # First option is to use a png, if any
            if btextures and btextures[i]:
                fpng = Path(btextures[i]).with_suffix('.png')
                if os.path.exists(fpng):
                    self.textures[i] = str(fpng)
                    continue

            if fulltextures[i]:
                fpng = Path(fulltextures[i]).with_suffix('.png')
                if os.path.exists(fpng):
                    self.textures[i] = str(fpng)
                    continue
            
            if btextures and btextures[i] and os.path.exists(btextures[i]):
                self.textures[i] = btextures[i]
            
            if fulltextures[i] and os.path.exists(fulltextures[i]):
                self.textures[i] = fulltextures[i]
            
        # # Check if the user has converted textures to png
        # self.log.debug(f"Diffuse as in nif: {fulltextures[0]}")
        # for i, tx in enumerate(fulltextures):
        #     #log.debug(f"Finding texture {i}: {tx}")
        #     if len(tx) > 0 and tx[-4:].lower() == '.dds':
        #         # Check for converted texture in the nif's filetree
        #         txpng = tx[0:-3] + 'png'
        #         if blender_dir:
        #             #log.debug("Check in Blender's default texture directory first")
        #             fndds = os.path.join(blender_dir, shape.textures[i])
        #             #log.debug("Got blender texture path")
        #             fnpng = os.path.splitext(fndds)[0] + '.png'
        #             if os.path.exists(fnpng):
        #                 fulltextures[i] = fnpng
        #                 log.info(f"Using png texture from Blender's texture directory: {fnpng}")
        #         if fulltextures[i][-4:].lower() == '.dds':
        #             log.debug(f"checking texture path {txpng}")
        #             if os.path.exists(txpng):
        #                 fulltextures[i] = txpng
        #                 log.info(f"Using png texture from nif's node tree': {txpng}")

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
                                txtnode.location[1] - attrnode.height - self.offset_y)
            
            mixnode = self.nodes.new("ShaderNodeMix")
            mixnode.data_type = 'RGBA'
            mixnode.location = (attrnode.location[0] - self.inter2_offset_x, attrnode.location[1])
            self.link(txtnode.outputs['Color'], mixnode.inputs[6])
            self.link(attrnode.outputs['Color'], mixnode.inputs[7])
            self.link(mixnode.outputs[2], self.bsdf.inputs['Base Color'])
            attrnode.attribute_name = self.colormap.name
            attrnode.attribute_type = "GEOMETRY"
            mixnode.blend_type = 'MULTIPLY'
            mixnode.inputs['Factor'].default_value = 1
        else:
            self.link(txtnode.outputs['Color'], self.bsdf.inputs['Base Color'])

        if self.alpha_colormap:
            attrnode = self.nodes.new("ShaderNodeAttribute")
            attrnode.attribute_name = ALPHA_MAP_NAME
            attrnode.attribute_type = "GEOMETRY"
            attrnode.location = (txtnode.location[0], 
                                    txtnode.location[1] - attrnode.height - self.offset_y)

            # Magic values make the khajiit head look good. Check against other meshes.
            mapnode1 = self.nodes.new("ShaderNodeMapRange")
            mapnode1.inputs['From Min'].default_value = 0.29
            mapnode1.inputs['From Max'].default_value = 0.8
            mapnode1.location = (attrnode.location[0] - self.inter2_offset_x, attrnode.location[1])
            self.link(attrnode.outputs['Color'], mapnode1.inputs['Value'])
            
            mapnode2 = self.nodes.new("ShaderNodeMapRange")
            mapnode2.inputs['From Min'].default_value = 0.4
            mapnode2.inputs['To Max'].default_value = 0.38
            mapnode2.location = (attrnode.location[0] - self.inter1_offset_x, attrnode.location[1])
            self.link(mapnode1.outputs['Result'], mapnode2.inputs['To Min'])
            self.link(txtnode.outputs['Alpha'], mapnode2.inputs['Value'])

            self.link(mapnode2.outputs['Result'], self.bsdf.inputs['Alpha'])
            
        else:
            self.link(txtnode.outputs['Alpha'], self.bsdf.inputs['Alpha'])

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

        # Stash texture strings for future export
        for i, t in enumerate(shape.textures):
            self.material['BSShaderTextureSet_' + str(i)] = t

        self.find_textures(shape)

        self.import_shader_attrs(shape)
        import_shader_alpha(self.material, shape)
        self.colormap, self.alpha_colormap = get_effective_colormaps(obj.data)

        self.import_diffuse()
        self.import_subsurface()
        self.import_specular()
        self.import_normal(shape)

        obj.active_material = self.material


