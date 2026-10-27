"""Shader and alpha property blocks, and the texture map of a shader."""

from __future__ import annotations

import os
from enum import Enum
import re
import logging
from ctypes import *
from typing import ValuesView, List
from collections.abc import MutableMapping
import xml.etree.ElementTree as xml
from pathlib import Path
from ..niflytools import *
from ..nifdefs import *
from ..niflydll import nifly, nifly_path
from ..nifconstants import BSXFlagsValues, HAVOC_SCALE_FACTOR, game_traits
from .base import NiProperty


log = logging.getLogger("pynifly")


class NiAlphaProperty(NiProperty):
    @classmethod
    def getbuf(cls, values=None):
        return AlphaPropertyBuf(values)

    @property
    def parent(self):
        if not self._parent:
            for sh in self.file.shapes:
                if sh.properties.alphaPropertyID == self.id:
                    self._parent = sh
                    break
        return self._parent


class TextureMap(MutableMapping):
    """A shader's textures by slot name ('Diffuse', 'Normal', ...).

    Assigning a slot writes the texture path to the nif; the change is saved with the file.
    A slot the shader has no place for raises KeyError -- including 'RootMaterialPath', which
    FO4 shaders report here but is the shader's root material name, not a texture. When the
    textures come from an FO4 material file the map is read-only: assignment raises TypeError,
    since the material file, not the nif, holds them.
    """
    def __init__(self, cache, writer=None, readonly_reason=None):
        self._cache = cache
        self._writer = writer
        self._readonly_reason = readonly_reason

    def __getitem__(self, slot):
        return self._cache[slot]

    def __iter__(self):
        return iter(self._cache)

    def __len__(self):
        return len(self._cache)

    def __setitem__(self, slot, path):
        if self._writer is None:
            raise TypeError(self._readonly_reason)
        self._writer(slot, path)
        self._cache[slot] = path

    def __delitem__(self, slot):
        if self._writer is None:
            raise TypeError(self._readonly_reason)
        self._writer(slot, '')
        del self._cache[slot]

    def __repr__(self):
        return f"TextureMap({self._cache!r})"


class NiShader(NiProperty):
    """
    Handles shader attributes for a Nif. In Skyrim, returns values from the underlying
    shader block. In FO4, most attributes come from the associated materials file.
    """
    buffer_type = PynBufferTypes.NiShaderBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiShaderBuf(values)

    # Texture-set slot index for each texture a lighting shader can hold. Some slots are shared:
    # which name a slot is read under depends on the shader flags.
    LIGHTING_TEXTURE_SLOTS = {
        'Diffuse': 0, 'Normal': 1, 'Glow': 2, 'RimLighting': 2, 'SoftLighting': 2,
        'HeightMap': 3, 'Greyscale': 3, 'EnvMap': 4, 'EnvMask': 5,
        'FacegenDetail': 6, 'InnerLayer': 6, 'Specular': 7, 'Wrinkles': 8}
    # The properties field holding each texture an effect shader can hold.
    EFFECT_TEXTURE_FIELDS = {
        'Diffuse': 'sourceTexture', 'Greyscale': 'greyscaleTexture', 'EnvMap': 'envMapTexture',
        'Normal': 'normalTexture', 'EnvMapMask': 'envMaskTexture',
        'EmitGradient': 'emitGradientTexture'}
    # nifly's texture-slot index for the effect-shader textures it can set on a block already in
    # the file (NifFile::SetTextureSlot). It has none for EmitGradient.
    EFFECT_TEXTURE_SLOTS = {
        'Diffuse': 0, 'Normal': 1, 'Greyscale': 3, 'EnvMap': 4, 'EnvMapMask': 5}

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)

        self._textures = None
        self._texture_map = None

    @property
    def parent(self):
        if not self._parent:
            for sh in self.file.shapes:
                if sh.properties.shaderPropertyID == self.id:
                    self._parent = sh
                    break 
        return self._parent
    
    # Names are handled simply, because they get written when the shader gets written.
    @property
    def name(self):
        return super().name
    
    @name.setter
    def name(self, val):
        if val:
            self._name = val

    def _readtexture(self, niffile, shape, layer):
        bufsize = 500
        buf = create_string_buffer(bufsize)
        check_msg(nifly.getShaderTextureSlot, niffile, shape, layer-1, buf, bufsize)
        return buf.value.decode('utf-8')

    @property
    def textures(self):
        """The shader's textures by slot name, as a TextureMap. Assigning a slot writes it to
        the nif: `shape.textures['Diffuse'] = r'textures\\foo_d.dds'`."""
        if self._texture_map is None:
            self._texture_map = TextureMap(self._read_textures(), self._write_texture)
        return self._texture_map

    def _read_textures(self):
        """The shader block's textures as a plain dict, read once and cached."""
        if self._textures is None:
            self._textures = {}
            if self.properties.bufType == PynBufferTypes.BSLightingShaderPropertyBufType:
                f = self.file._handle
                s = self._parent._handle
                self._textures["Diffuse"] = self._readtexture(f, s, 1)
                self._textures["Normal"] = self._readtexture(f, s, 2)

                if self.properties.shaderflags2_test(ShaderFlags2.GLOW_MAP):
                    self._textures["Glow"] = self._readtexture(f, s, 3)

                try:
                    # Skyrim only
                    if self.properties.shaderflags2_test(ShaderFlags2.RIM_LIGHTING):
                        self._textures["RimLighting"] = self._readtexture(f, s, 3)
                    if self.properties.shaderflags2_test(ShaderFlags2.SOFT_LIGHTING):
                        self._textures["SoftLighting"] = self._readtexture(f, s, 3)
                    if self.properties.shaderflags1_test(ShaderFlags1.PARALLAX):
                        self._textures["HeightMap"] = self._readtexture(f, s, 4)
                    if self.properties.shaderflags1_test(ShaderFlags1.GREYSCALE_COLOR):
                        self._textures["Greyscale"] = self._readtexture(f, s, 4)
                    if self.properties.shaderflags2_test(ShaderFlags2.ENVMAP_LIGHT_FADE):
                        self._textures["EnvMap"] = self._readtexture(f, s, 5)
                    if self.properties.shaderflags1_test(ShaderFlags1.FACEGEN_DETAIL_MAP):
                        self._textures["FacegenDetail"] = self._readtexture(f, s, 7)
                except Exception:
                    pass

                if (self.properties.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING) 
                        or self.properties.shaderflags1_test(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)):
                    self._textures["EnvMap"] = self._readtexture(f, s, 5)
                    self._textures["EnvMask"] = self._readtexture(f, s, 6)

                if self.properties.shaderflags2_test(ShaderFlags2.MULTI_LAYER_PARALLAX):
                    self._textures["InnerLayer"] = self._readtexture(f, s, 7)

                if (self.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)
                    or self.properties.shaderflags1_test(ShaderFlags1.SPECULAR)):
                    self._textures["Specular"] = self._readtexture(f, s, 8)

                # The root material path lives in the shader block (rootMaterialNameID),
                # not the texture set. Expose it here so the block-read path matches
                # the material-read path, which also returns RootMaterialPath.
                if self.properties.rootMaterialNameID != NODEID_NONE:
                    self._textures["RootMaterialPath"] = self.file.get_string(
                        self.properties.rootMaterialNameID)

            if self.properties.bufType == PynBufferTypes.BSEffectShaderPropertyBufType:
                self._textures['Diffuse'] = self.properties.sourceTexture.decode()
                self._textures['Greyscale'] = self.properties.greyscaleTexture.decode()
                self._textures['EnvMap'] = self.properties.envMapTexture.decode()
                self._textures['Normal'] = self.properties.normalTexture.decode()
                self._textures['EnvMapMask'] = self.properties.envMaskTexture.decode()
                self._textures['EmitGradient'] = self.properties.emitGradientTexture.decode()

        return self._textures

    def _write_texture(self, slot:str, texturepath):
        """Write one texture path to the nif. KeyError if this shader has no such slot."""
        path = texturepath.encode('utf-8')
        buftype = self.properties.bufType
        if buftype == PynBufferTypes.BSLightingShaderPropertyBufType:
            if slot not in self.LIGHTING_TEXTURE_SLOTS:
                raise KeyError(f"A lighting shader has no '{slot}' texture; slots are "
                               f"{sorted(self.LIGHTING_TEXTURE_SLOTS)}")
            nifly.setShaderTextureSlot(
                self.file._handle, self._parent._handle, self.LIGHTING_TEXTURE_SLOTS[slot], path)
        elif buftype == PynBufferTypes.BSEffectShaderPropertyBufType:
            if slot not in self.EFFECT_TEXTURE_FIELDS:
                raise KeyError(f"An effect shader has no '{slot}' texture; slots are "
                               f"{sorted(self.EFFECT_TEXTURE_FIELDS)}")
            field = self.EFFECT_TEXTURE_FIELDS[slot]
            if getattr(self.properties, field) == path:
                return
            # Effect-shader textures live in the block itself. Until the block is in the file
            # (an export fills the buffer, then writes the block) setting the buffer is enough;
            # once it is, nifly's texture-slot setter writes the block -- but only if the block
            # in the file really is an effect shader: an export can give a new shape's buffer a
            # different type from its placeholder block.
            if self.id != NODEID_NONE:
                if dll_string(nifly.getBlockname, self.file._handle, self.id) == 'BSEffectShaderProperty':
                    if slot not in self.EFFECT_TEXTURE_SLOTS:
                        raise NotImplementedError(
                            f"'{slot}' can't be changed on an effect shader already in the file")
                    nifly.setShaderTextureSlot(
                        self.file._handle, self._parent._handle,
                        self.EFFECT_TEXTURE_SLOTS[slot], path)
            setattr(self.properties, field, path)
        else:
            raise KeyError(f"Can't write textures to a {self.blockname}")

    def set_texture(self, slot:str, texturepath):
        """Set texture in the named slot to the given string. Prefer assigning to `textures`,
        which refuses a slot the shader doesn't have; this silently ignores one."""
        try:
            self._write_texture(slot, texturepath)
        except KeyError:
            return
        if self._textures is not None:
            self._textures[slot] = texturepath

    # Individual getter routines for shader flags so the caller doesn't have to worry
    # about Skyrim vs FO4.

    @property
    def flag_vertex_alpha(self):
        return self.properties.shaderflags1_test(ShaderFlags1.VERTEX_ALPHA)

    @property
    def flag_facegen_RBG_tint(self):
        return self.properties.shaderflags1_test(ShaderFlags1.FACEGEN_RGB_TINT)

    @property
    def flag_greyscale_color(self):
        return self.properties.shaderflags1_test(ShaderFlags1.GREYSCALE_COLOR)

    @property
    def flag_greyscale_alpha(self):
        return self.properties.shaderflags1_test(ShaderFlags1.GREYSCALE_ALPHA)

    @property
    def flag_decal(self):
        return self.properties.shaderflags1_test(ShaderFlags1.DECAL)

    @property
    def flag_environment_mapping(self):
        return self.properties.shaderflags1_test(ShaderFlags1.ENVIRONMENT_MAPPING)

    @property
    def flag_zbuffer_test(self):
        return self.properties.shaderflags1_test(ShaderFlags1.ZBUFFER_TEST)

    @property
    def flag_cast_shadows(self):
        return self.properties.shaderflags1_test(ShaderFlags1.CAST_SHADOWS)
        
    @property
    def flag_external_emittance(self):
        return self.properties.shaderflags1_test(ShaderFlags1.EXTERNAL_EMITTANCE)
        
    @property
    def flag_eye_environment_mapping(self):
        return self.properties.shaderflags1_test(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)

    @property
    def flag_hair(self):
        # FO4 SLSF1 bit 18 (Skyrim names this bit HAIR_SOFT_LIGHTING).
        return self.properties.shaderflags1_test(ShaderFlags1FO4.HAIR)

    @property
    def flag_own_emit(self):
        return self.properties.shaderflags1_test(ShaderFlags1.OWN_EMIT)

    @property
    def flag_model_space_normals(self):
        return self.properties.shaderflags1_test(ShaderFlags1.MODEL_SPACE_NORMALS)

    @property
    def flag_rgb_falloff(self):
        # FO4-only SLSF1 bit 8 (Skyrim names this bit RECEIVE_SHADOWS).
        return self.properties.shaderflags1_test(ShaderFlags1FO4.RGB_FALLOFF)

    @property
    def flag_specular(self):
        return self.properties.shaderflags1_test(ShaderFlags1.SPECULAR)
        
    @property
    def flag_use_falloff(self):
        return self.properties.shaderflags1_test(ShaderFlags1.USE_FALLOFF)

    @property
    def flag_double_sided(self):
        return self.properties.shaderflags2_test(ShaderFlags2.DOUBLE_SIDED)

    @property
    def flag_vertex_colors(self):
        return self.properties.shaderflags2_test(ShaderFlags2.VERTEX_COLORS)

    @property
    def flag_no_fade(self):
        return self.properties.shaderflags2_test(ShaderFlags2.NO_FADE)

    @property
    def flag_glow_map(self):
        return self.properties.shaderflags2_test(ShaderFlags2.GLOW_MAP)

    @property
    def flag_zbuffer_write(self):
        return self.properties.shaderflags2_test(ShaderFlags2.ZBUFFER_WRITE)

    @property
    def flag_anisotropic_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.ANISOTROPIC_LIGHTING)

    @property
    def flag_transform_changed(self):
        # FO4 SLSF2 bit 7. The Skyrim ShaderFlags2 enum names this same bit
        # ASSUME_SHADOWMASK and has no TRANSFORM_CHANGED member, so referencing it
        # there raised AttributeError; use the FO4 enum for this FO4-only flag.
        return self.properties.shaderflags2_test(ShaderFlags2FO4.TRANSFORM_CHANGED)

    @property
    def flag_vats_target_draw_all(self):
        # FO4-only SLSF2 bit 27 (Skyrim names this bit BACK_LIGHTING).
        return self.properties.shaderflags2_test(ShaderFlags2FO4.VATS_TARGET_DRAW_ALL)

    @property
    def flag_gradient_remap(self):
        # FO4-only SLSF2 bit 26 (Skyrim names this bit RIM_LIGHTING).
        return self.properties.shaderflags2_test(ShaderFlags2FO4.GRADIENT_REMAP)

    @property
    def flag_alpha_test(self):
        # FO4-only SLSF2 bit 25 (Skyrim names this bit SOFT_LIGHTING).
        return self.properties.shaderflags2_test(ShaderFlags2FO4.ALPHA_TEST)

    @property
    def flag_tree_anim(self):
        return self.properties.shaderflags2_test(ShaderFlags2.TREE_ANIM)
        
    @property
    def flag_effect_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.EFFECT_LIGHTING)

    @property
    def flag_rim_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.RIM_LIGHTING)

    @property
    def flag_soft_lighting(self):
        return self.properties.shaderflags2_test(ShaderFlags2.SOFT_LIGHTING)

    @property
    def texture_clamp_mode(self):
        return self.properties.textureClampMode
    
    @texture_clamp_mode.setter
    def texture_clamp_mode(self, value):
        self.properties.textureClampMode = value


class BSDistantTreeShaderProperty(NiShader):
    pass


class BSLightingShaderProperty(NiShader):
    pass


class BSShaderLightingProperty(NiShader):
    pass


class BSShaderNoLightingProperty(NiShader):
    pass


class BSShaderProperty(NiShader):
    pass


class BSSkyShaderProperty(NiShader):
    pass


class BSWaterShaderProperty(NiShader):
    pass


class DistantLODShaderProperty(NiShader):
    pass


class HairShaderProperty(NiShader):
    pass


class Lighting30ShaderProperty(NiShader):
    pass


class NiMaterialProperty(NiShader):
    pass


class SkyShaderProperty(NiShader):
    pass


class TallGrassShaderProperty(NiShader):
    pass


class TileShaderProperty(NiShader):
    pass


class VolumetricFogShaderProperty(NiShader):
    pass


class WaterShaderProperty(NiShader):
    pass


class BSEffectShaderProperty(NiShader):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyBufType

    @classmethod
    def getbuf(cls, values=None):
        b = NiShaderBuf(values)
        b.bufType = PynBufferTypes.BSEffectShaderPropertyBufType
        return b


class BSShaderPPLightingProperty(NiShader):
    buffer_type = PynBufferTypes.BSShaderPPLightingPropertyBufType

    @classmethod
    def getbuf(cls, values=None):
        b = NiShaderBuf(values)
        b.bufType = PynBufferTypes.BSShaderPPLightingPropertyBufType
        return b


class NiShaderFO4(NiShader):
    """
    Shader for FO4 nifs. Alters NiShader behavior to get values from the materials file
    when necessary.
    """
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        self._materials = None
        self._checked_for_materials = False
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._checked_for_materials = False
        
    def _load_properties_from_materials(self):
        """Load materials properties into shader properties so the rest of the world doesn't have to care."""
        if not self._materials: return

        p = self._properties
        p.textureClampMode = self._materials.tileFlags
        p.UV_Offset_U = self._materials.UV_Offset_U
        p.UV_Offset_V = self._materials.UV_Offset_V
        p.UV_Scale_U = self._materials.UV_Scale_U
        p.UV_Scale_V = self._materials.UV_Scale_V
        p.Alpha = self._materials.Alpha
        p.Env_Map_Scale = self._materials.environmentMappingMaskScale
        # emittanceColor only exists in the BGSM when emitEnabled is set (the editor
        # hides it otherwise). When emit is off the material has no emissive colour,
        # so leave the shader block's value rather than clobbering it with black.
        # BGEM (effect) materials have no emitEnabled flag -- default True so they
        # keep copying as before.
        if getattr(self._materials, 'emitEnabled', True):
            # emittanceColor is RGB only; the material doesn't carry an emissive
            # alpha, so leave the block's alpha rather than forcing it.
            p.Emissive_Color[0] = self._materials.emittanceColor[0]
            p.Emissive_Color[1] = self._materials.emittanceColor[1]
            p.Emissive_Color[2] = self._materials.emittanceColor[2]
        p.Emissive_Mult = self._materials.emittanceMult
        p.Refraction_Str = self._materials.refractionPower
        p.Glossiness = self._materials.smoothness
        p.Rim_Light_Power = self._materials.rimPower
        p.subsurfaceRolloff = self._materials.subsurfaceRolloff
        p.fresnelPower = self._materials.fresnelPower

        # grayscaleToPaletteScale and wetnessControl_* are BGSM (lighting-shader)
        # properties; BGEM effect shaders don't carry them.
        if self._materials.signature == b'BGSM':
            p.grayscaleToPaletteScale = self._materials.grayscaleToPaletteScale

            # wetnessControl_* use -1.0 in the BGSM as an "unspecified" sentinel,
            # while the NIF block holds the real effective values. Copy a material
            # value only when it actually specifies one (>= 0); otherwise keep the
            # block value rather than clobbering it with the sentinel.
            for fld in ('wetnessSpecScale', 'wetnessSpecPower', 'wetnessMinVar',
                        'wetnessEnvmapScale', 'wetnessFresnelPower', 'wetnessMetalness'):
                matval = getattr(self._materials, fld, -1.0)
                if matval >= 0.0:
                    setattr(p, fld, matval)

        # Shader flags 1/2. The material is authoritative only for the bits it
        # actually represents (set/cleared individually below). Don't zero the
        # whole field first: NIF-level flags that no material property maps to --
        # notably SLSF1_Skinned -- live in the shader block and must survive the
        # material load. Starting from the block value preserves them.
        if self._materials.decal:
            p.shaderflags1_set(ShaderFlags1.DECAL)
        else:
            p.shaderflags1_clear(ShaderFlags1.DECAL)

        if self._materials.environmentMapping:
            p.shaderflags1_set(ShaderFlags1.ENVIRONMENT_MAPPING)
        else:
            p.shaderflags1_clear(ShaderFlags1.ENVIRONMENT_MAPPING)

        if self._materials.zbuffertest:
            p.shaderflags1_set(ShaderFlags1.ZBUFFER_TEST)
        else:
            p.shaderflags1_clear(ShaderFlags1.ZBUFFER_TEST)

        if self._materials.twoSided:
            p.shaderflags2_set(ShaderFlags2.DOUBLE_SIDED)
        else:
            p.shaderflags2_clear(ShaderFlags2.DOUBLE_SIDED)

        if self._materials.glowmap:
            p.shaderflags2_set(ShaderFlags2.GLOW_MAP)
        else:
            p.shaderflags2_clear(ShaderFlags2.GLOW_MAP)

        if self._materials.zbufferwrite:
            p.shaderflags2_set(ShaderFlags2.ZBUFFER_WRITE)
        else:
            p.shaderflags2_clear(ShaderFlags2.ZBUFFER_WRITE)

        if self._materials.grayscaleToPaletteColor:
            p.shaderflags1_set(ShaderFlags1.GREYSCALE_COLOR)
        else:
            p.shaderflags1_clear(ShaderFlags1.GREYSCALE_COLOR)

        if self._materials.signature == b'BGSM':
            if self._materials.skinTint:
                p.shaderflags1_set(ShaderFlags1.FACEGEN_RGB_TINT)
            else:
                p.shaderflags1_clear(ShaderFlags1.FACEGEN_RGB_TINT)

            if self._materials.castShadows:
                p.shaderflags1_set(ShaderFlags1.CAST_SHADOWS)
            else:
                p.shaderflags1_clear(ShaderFlags1.CAST_SHADOWS)

            if self._materials.anisoLighting:
                p.shaderflags2_set(ShaderFlags2.ANISOTROPIC_LIGHTING)
            else:
                p.shaderflags2_clear(ShaderFlags2.ANISOTROPIC_LIGHTING)

            if self._materials.tree:
                p.shaderflags2_set(ShaderFlags2.TREE_ANIM)
            else:
                p.shaderflags2_clear(ShaderFlags2.TREE_ANIM)

            if self._materials.externalEmittance:
                p.shaderflags1_set(ShaderFlags1.EXTERNAL_EMITTANCE)
            else:
                p.shaderflags1_clear(ShaderFlags1.EXTERNAL_EMITTANCE)

            if self._materials.environmentMappingEye:
                p.shaderflags1_set(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)
            else:
                p.shaderflags1_clear(ShaderFlags1.EYE_ENVIRONMENT_MAPPING)

            if self._materials.hair:
                p.shaderflags1_set(ShaderFlags1.HAIR_SOFT_LIGHTING)
            else:
                p.shaderflags1_clear(ShaderFlags1.HAIR_SOFT_LIGHTING)

            # OWN_EMIT (SLSF1, bit 22) is NOT material-owned: vanilla FO4 blocks
            # carry it independently of the BGSM's emitEnabled (which controls the
            # material's own emittance colour, a different concept). Driving it off
            # emitEnabled dropped the block flag on nearly every FO4 shape. Leave
            # it to survive from the shader block, like SLSF1_Skinned.

            if self._materials.modelSpaceNormals:
                p.shaderflags1_set(ShaderFlags1.MODEL_SPACE_NORMALS)
            else:
                p.shaderflags1_clear(ShaderFlags1.MODEL_SPACE_NORMALS)

            if self._materials.specularEnabled:
                p.shaderflags1_set(ShaderFlags1.SPECULAR)
            else:
                p.shaderflags1_clear(ShaderFlags1.SPECULAR)

        if self._materials.signature == b'BGEM':
            if self._materials.falloffEnabled:
                p.shaderflags1_set(ShaderFlags1.USE_FALLOFF)
            else:
                p.shaderflags1_clear(ShaderFlags1.USE_FALLOFF)

            if self._materials.effectLightingEnabled:
                p.shaderflags2_set(ShaderFlags2.EFFECT_LIGHTING)
            else:
                p.shaderflags2_clear(ShaderFlags2.EFFECT_LIGHTING)

    @property
    def materials(self):
        """Return the materials file if any."""
        if not self._checked_for_materials:
            # Find and read the materials file if any. This is where the shader properties
            # will come from. Some FO4 nifs don't have materials files. Apparently (?)
            # they use the shader block attributes.
            if self.name:
                # Build search paths starting with the nif's own materials root
                altpaths = []
                
                # Add the nif's own materials root first
                if self.file.materialsRoot:
                    altpaths.append(self.file.materialsRoot)
                
                # Add any additional paths provided via alternate_paths attribute
                alternate_paths = getattr(self, 'alternate_paths', None)
                if alternate_paths:
                    if isinstance(alternate_paths, (list, tuple)):
                        altpaths.extend(alternate_paths)
                    else:
                        altpaths.append(alternate_paths)
                
                fullpath = find_referenced_file(self.name, self.file.filepath, root='materials',
                                                alt_pathlist=altpaths)
                if fullpath:
                    try:
                        self._materials = bgsmaterial.MaterialFile.Open(fullpath)
                    except Exception:
                        log.exception(
                            f"Could not read materials file '{fullpath}' "
                            f"referenced by shader '{self.name}'")
                        self._materials = None
                    if self._materials:
                        self._load_properties_from_materials()
                else:
                    log.warning(
                        f"Could not find materials file '{self.name}' "
                        f"(searched nif filetree and {len(altpaths)} alternate path(s))")
            self._checked_for_materials = True
        return self._materials
    
    @property
    def properties(self):
        """
        Return shader properties. Return the materials file properties if any; caller will
        have to deal with any properties that differ between FO4 and Skyrim. Return the
        properties buffer if no materials file.
        """
        if not self._properties:
            super().properties

        self.materials  # Force load of materials if any.

        return self._properties
        
    @property
    def textures(self):
        """The textures the game uses: the material file's when there is one (read-only --
        change the material file), else the shader block's (writable, as for NiShader)."""
        if self.materials:
            return TextureMap(
                self.materials.textures,
                readonly_reason=(f"These textures come from the material file '{self.name}'; "
                                 f"change them there. To set the nif's own texture set, use "
                                 f"set_texture()."))
        else:
            return super().textures


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .base import (check_msg, dll_string)  # noqa: E402
