
"""
    Value and type definitions for nif structures
"""

import sys
from enum import IntEnum
from ctypes import (Structure, POINTER, byref, c_byte, c_int, c_float, c_uint16, c_char, 
                    c_uint8, c_uint32, c_uint64)
from . import pynmathutils as PM
from . import bgsmaterial
from .pynmathutils import (CHAR256, VECTOR2, VECTOR3, VECTOR4, VECTOR12, MATRIX3, MATRIX4)
from .structs import (pynStructure, TransformBuf)
from .nifconstants import (
    PynIntFlag, PynIntEnum, NODEID_NONE, NO_SHADER_REF,
    NiAVFlags, BSXFlagsValues, BSValueNodeFlags, VertexFlags, EffectShaderControlledVariable,
    SkyrimCollisionLayer, BroadPhaseType, hkResponseType, hkMotionType, hkDeactivatorType,
    hkSolverDeactivation, hkQualityType, ShaderFlags1, ShaderFlags2, ShaderFlags1FO4,
    ShaderFlags2FO4, BSLSPShaderType, SkyrimHavokMaterial, AnimType, CycleType)


class PynBufferTypes(IntEnum):
    NiNodeBufType = 0
    NiShapeBufType = 1
    NiCollisionObjectBufType = 2
    bhkNiCollisionObjectBufType = 3
    bhkPCollisionObjectBufType = 4
    bhkSPCollisionObjectBufType = 5
    bhkRigidBodyBufType = 6
    bhkRigidBodyTBufType = 7
    bhkBoxShapeBufType = 8
    NiControllerManagerBufType = 9
    NiControllerSequenceBufType = 10
    NiTransformInterpolatorBufType = 11
    NiTransformDataBufType = 12
    NiControllerLinkBufType = 13
    BSInvMarkerBufType = 14
    BSXFlagsBufType = 15
    NiMultiTargetTransformControllerBufType = 16
    NiTransformControllerBufType = 17
    bhkCollisionObjectBufType = 18
    bhkCapsuleShapeBufType = 19
    bhkConvexTransformShapeBufType = 20
    bhkConvexVerticesShapeBufType = 21
    bhkListShapeBufType = 22
    bhkBlendCollisionObjectBufType = 23
    bhkRagdollConstraintBufType = 24
    bhkSimpleShapePhantomBufType = 25
    bhkSphereShapeBufType = 26
    BSMeshLODTriShapeBufType = 27
    NiShaderBufType = 28
    AlphaPropertyBufType = 29
    BSDynamicTriShapeBufType = 30
    BSTriShapeBufType = 31
    BSSubIndexTriShapeBufType = 32
    BSEffectShaderPropertyBufType = 33
    NiTriStripsBufType = 34
    BSLODTriShapeBufType = 35
    BSLightingShaderPropertyBufType = 36
    BSShaderPPLightingPropertyBufType = 37
    NiTriShapeBufType = 38
    BSEffectShaderPropertyColorControllerBufType = 39
    NiPoint3InterpolatorBufType = 40
    NiPosDataBufType = 41
    BSEffectShaderPropertyFloatControllerBufType = 42
    NiFloatInterpolatorBufType = 43
    NiFloatDataBufType = 44
    NiBlendPoint3InterpolatorBufType = 45 
    NiBlendFloatInterpolatorBufType = 46   
    NiDefaultAVObjectPaletteBufType = 47
    NiTextKeyExtraDataBufType = 48
    BSNiAlphaPropertyTestRefControllerBufType = 49
    BSLightingShaderPropertyColorControllerBufType = 50
    NiSingleInterpControllerBufType = 51
    BSLightingShaderPropertyFloatControllerBufType = 52
    NiBlendInterpolatorBufType = 53
    NiBlendBoolInterpolatorBufType = 54
    NiBlendTransformInterpolatorBufType = 55
    NiBoolInterpolatorBufType = 56
    NiBoolInterpControllerBufType = 57
    NiVisControllerBufType = 58
    BSValueNodeBufType = 59
    BSBoundBufType = 60
    BSBoneLODBufType = 61
    NiIntegerExtraDataBufType = 62
    BSBehaviorGraphExtraDataBufType = 63
    NiStringExtraDataBufType = 64
    BSClothExtraDataBufType = 65
    BSFurnitureMarkerNodeBufType = 66
    bhkNPCollisionObjectBufType = 67
    bhkPhysicsSystemBufType = 68
    bhkMoppBvTreeShapeBufType = 69
    bhkPackedNiTriStripsShapeBufType = 70
    bhkCompressedMeshShapeBufType = 71
    COUNT = 72


class NiShaderBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('nameID', c_uint32),
        ('bBSLightingShaderProperty', c_char),
        ('bslspShaderType', c_uint32),
        ('controllerID', c_uint32),
        ('extraDataCount', c_uint16),
        ('shaderFlags', c_uint16),
        ('Shader_Type', c_uint32),
	    ('Shader_Flags_1', c_uint32),
	    ('Shader_Flags_2', c_uint32),
        ('Env_Map_Scale', c_float),
        ('numSF1', c_uint32),
        ('numSF2', c_uint32),
	    ('UV_Offset_U', c_float),
	    ('UV_Offset_V', c_float),
	    ('UV_Scale_U', c_float),
	    ('UV_Scale_V', c_float),
        ('textureSetID', c_uint32),
	    ('Emissive_Color', VECTOR4),
	    ('Emissive_Mult', c_float),
        ('rootMaterialNameID', c_uint32),
	    ('textureClampMode', c_uint32),
        # BSLightingShaderProperty
	    ('Alpha', c_float),
	    ('Refraction_Str', c_float),
	    ('Glossiness', c_float),
	    ('Spec_Color', VECTOR3),
	    ('Spec_Str', c_float),
	    ('Soft_Lighting', c_float),
	    ('Rim_Light_Power', c_float),
        ('subsurfaceRolloff', c_float),
        ('rimlightPower2', c_float),
        ('backlightPower', c_float),
        ('grayscaleToPaletteScale', c_float),
        ('fresnelPower', c_float),
        ('wetnessSpecScale', c_float),
        ('wetnessSpecPower', c_float),
        ('wetnessMinVar', c_float),
        ('wetnessEnvmapScale', c_float),
        ('wetnessFresnelPower', c_float),
        ('wetnessMetalness', c_float),
        ('wetnessUnknown1', c_float),
        ('wetnessUnknown2', c_float),
        ('lumEmittance', c_float),
        ('exposureOffset', c_float),
        ('finalExposureMin', c_float),
        ('finalExposureMax', c_float),
        ('doTranslucency', c_char),
	    ('subsurfaceColor', VECTOR3),
        ('transmissiveScale', c_float),
        ('turbulence', c_float),
        ('thickObject', c_char),
        ('mixAlbedo', c_char),
        ('hasTextureArrays', c_char),
        ('numTextureArrays', c_uint32),
        ('useSSR', c_char),
        ('wetnessUseSSR', c_char),
        ('skinTintColor', VECTOR3),
        ('Skin_Tint_Alpha', c_float),
        ('hairTintColor', VECTOR3),
        ('maxPasses', c_float),
        ('scale', c_float),
        ('parallaxInnerLayerThickness', c_float),
        ('parallaxRefractionScale', c_float),
        ('parallaxInnerLayerTextureScale', VECTOR2),
        ('parallaxEnvmapStrength', c_float),
        ('sparkleParameters', VECTOR4),
        ('eyeCubemapScale', c_float),
        ('eyeLeftReflectionCenter', VECTOR3),
        ('eyeRightReflectionCenter', VECTOR3),
        # BSEffectShaderProperty
        ('sourceTexture', CHAR256),
        ('LightingInfluence', c_uint8),
        ('EnvMapMinLOD', c_uint8),
        ('falloffStartAngle', c_float),
        ('falloffStopAngle', c_float),
        ('falloffStartOpacity', c_float),
        ('falloffStopOpacity', c_float),
        ('refractionPower', c_float),
        ('baseColor', VECTOR4),
        ('baseColorScale', c_float),
        ('softFalloffDepth', c_float),
        ('greyscaleTexture', CHAR256),
        ('envMapTexture', CHAR256),
        ('normalTexture', CHAR256),
        ('envMaskTexture', CHAR256),
        ('envMapScale', c_float),
        ('emittanceColor', VECTOR3),
        ('emitGradientTexture', CHAR256),
        # BSShaderPPLightingProperty
        ('refractionStrength', c_float),
        ('refractionFirePeriod', c_uint32),
        ('parallaxMaxPasses', c_float),
        ('parallaxScale', c_float),
        ('emissiveColor', VECTOR4),
        ]
    
    def __init__(self, values=None, game='SKYRIM'):
        super().__init__(values=values, game=game)
        self.bufType = PynBufferTypes.NiShaderBufType
        if values: self.load(values, game=game)

        # TODO: Getting defaults from niflyDLL. Resurrect this and make it consistent
        # or get rid of it.
        # if pynStructure.nifly:
        #     pynStructure.nifly.getBlock(None, NODEID_NONE, byref(self))
        # if values:
        #     self.load(values, game=game)

    def __str__(self):
        s = ""
        for attr in self._fields_:
            if len(s) > 0:
                s = s + "\n"
            s = s + f"\t{attr[0]} = {getattr(self, attr[0])}"
        return s

    def copyto(self, other):
        """Override copyto so that it ignores buffer type and length, and ID fields."""
        for f, t in self._fields_:
            if f not in ['bufType', 'bufSize'] and f[-2:] != 'ID':
                other.__setattr__(f, self.__getattribute__(f))
        return other
    
    def extract_field(self, shape, fieldname, fieldtype, game='SKYRIM'):
        """Extract a single field value to the shape."""
        if fieldname == 'Shader_Flags_1':
            if game in ['SKYRIM', 'SKYRIMSE']:
                shape[fieldname] = ShaderFlags1(self.Shader_Flags_1).fullname
            else:
                shape[fieldname] = ShaderFlags1FO4(self.Shader_Flags_1).fullname
        elif fieldname == 'Shader_Flags_2':
            if game in ['SKYRIM', 'SKYRIMSE']:
                shape[fieldname] = ShaderFlags2(self.Shader_Flags_2).fullname
            else:
                shape[fieldname] = ShaderFlags2FO4(self.Shader_Flags_2).fullname
        elif fieldname == 'Shader_Type':
            shape[fieldname] = BSLSPShaderType(self.Shader_Type).name
        else:
            super().extract_field(shape, fieldname, fieldtype, game=game)

    def shaderflags1_test(self, flag):
        return (self.Shader_Flags_1 & flag) != 0

    def shaderflags1_set(self, flag):
        self.Shader_Flags_1 |= flag.value

    def shaderflags1_clear(self, flag):
        self.Shader_Flags_1 &= ~flag.value

    def shaderflags2_test(self, flag):
        return (self.Shader_Flags_2 & flag) != 0

    def shaderflags2_set(self, flag):
        self.Shader_Flags_2 |= flag.value

    def shaderflags2_clear(self, flag):
        self.Shader_Flags_2 &= ~flag.value

    @property
    def clamp_mode_s(self):
        return self.textureClampMode & 1
    
    @clamp_mode_s.setter
    def clamp_mode_s(self, v):
        self.textureClampMode = (self.textureClampMode & 0xFFFE) | (0 if v == 0 else 1)

    @property
    def clamp_mode_t(self):
        return 1 if (self.textureClampMode & 2) else 0
    
    @clamp_mode_t.setter
    def clamp_mode_t(self, v):
        self.textureClampMode = (self.textureClampMode & 0xFFFD) | (0 if v == 0 else 2)


class BGSMShader(bgsmaterial.BGSMaterial):
    """Mimics the NiShader but gets values from a BGSM file."""

    def __init__(self, bgsmfile=None):
        self.filename = ""
        if bgsmfile:
            self.read(bgsmfile)
            self.filename = bgsmfile

    def shaderflags1_test(self, flag):
        if flag == ShaderFlags1.MODEL_SPACE_NORMALS:
            return self.modelSpaceNormals;

    def shaderflags1_set(self, flag=True):
        if flag == ShaderFlags1.MODEL_SPACE_NORMALS:
            self.modelSpaceNormals = flag.value;

    def shaderflags1_clear(self, flag=True):
        if flag == ShaderFlags1.MODEL_SPACE_NORMALS:
            self.modelSpaceNormals = ~flag.value;


class ALPHA_FUNCTION(IntEnum):
    ONE = 0
    ZERO = 1
    SRC_COLOR = 2
    INV_SRC_COLOR = 3
    DEST_COLOR = 4
    INV_DEST_COLOR = 5
    SRC_ALPHA = 6
    INV_SRC_ALPHA = 7
    DEST_ALPHA = 8
    INV_DEST_ALPHA = 9
    SRC_ALPHA_SATURATE = 10

class ALPHA_FLAG_MASK:
    ALPHA_BLEND = 0x0001
    SOURCE_BLEND_MODE = 0x001E
    DST_BLEND_MODE = 0x01E0
    ALPHA_TEST = 0x0200
    TEST_FUNC = 0x1C00
    NO_SORTER = 0x2000
    CLONE_UNIQUE = 0x4000
    EDITOR_ALPHA_THRESHOLD = 0x8000

class BufInfo(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('blockName', POINTER(c_byte)),
        ('id', c_uint32)
    ]

class AlphaPropertyBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('nameID', c_uint32),
        ('controllerID', c_uint32),
        ('extraDataCount', c_uint16),
        ('flags', c_uint16), 
        ('threshold', c_uint8)
        ]
    def __init__(self, values=None):
        self.flags = 4844
        super().__init__(values=values)
        self.bufType = PynBufferTypes.AlphaPropertyBufType

    @property
    def alpha_blend(self):
        return (self.flags & ALPHA_FLAG_MASK.ALPHA_BLEND) != 0
    @alpha_blend.setter
    def alpha_blend(self, val):
        if val:
            self.flags |= ALPHA_FLAG_MASK.ALPHA_BLEND
        else:
            self.flags &= ~ALPHA_FLAG_MASK.ALPHA_BLEND

    @property
    def alpha_test(self):
        return (self.flags & ALPHA_FLAG_MASK.ALPHA_TEST) != 0
    @alpha_test.setter
    def alpha_test(self, val):
        if val:
            self.flags |= ALPHA_FLAG_MASK.ALPHA_TEST
        else:
            self.flags &= ~ALPHA_FLAG_MASK.ALPHA_TEST

    @property
    def source_blend_mode(self):
        return (self.flags & ALPHA_FLAG_MASK.SOURCE_BLEND_MODE) >> 1
    @source_blend_mode.setter
    def source_blend_mode(self, val):
        self.flags &= ~ALPHA_FLAG_MASK.SOURCE_BLEND_MODE
        self.flags |= ALPHA_FLAG_MASK.SOURCE_BLEND_MODE & (val << 1)

    @property
    def dst_blend_mode(self):
        return (self.flags & ALPHA_FLAG_MASK.DST_BLEND_MODE) >> 5
    @dst_blend_mode.setter
    def dst_blend_mode(self, val):
        self.flags &= ~ALPHA_FLAG_MASK.DST_BLEND_MODE
        self.flags |= ALPHA_FLAG_MASK.DST_BLEND_MODE & (val << 5)


AlphaPropertyBuf_p = POINTER(AlphaPropertyBuf)

    
class NiCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32)
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiCollisionObjectBufType

class bhkNiCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32),
        ('flags', c_uint16),
        ('bodyID', c_uint32),
        ('childCount', c_uint16),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkNiCollisionObjectBufType

class bhkBlendCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32),
        ('flags', c_uint16),
        ('bodyID', c_uint32),
        ('childCount', c_uint16),
        ('heirGain', c_float),
        ('velGain', c_float),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkBlendCollisionObjectBufType

class bhkCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32),
        ('flags', c_uint16),
        ('bodyID', c_uint32),
        ('childCount', c_uint16),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkCollisionObjectBufType

class bhkPCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32),
        ('flags', c_uint16),
        ('bodyID', c_uint32),
        ('childCount', c_uint16),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkPCollisionObjectBufType

class bhkSPCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32),
        ('flags', c_uint16),
        ('bodyID', c_uint32),
        ('childCount', c_uint16),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkSPCollisionObjectBufType

class bhkNPCollisionObjectBuf(pynStructure):
    _fields_ = [
	    ('bufSize', c_uint16),
	    ('bufType', c_uint16),
        ('targetID', c_uint32),
        ('flags', c_uint16),
        ('dataID', c_uint32),     # ID of the bhkPhysicsSystem block
        ('bodyID', c_uint32),     # Index into the physics system's body array
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkNPCollisionObjectBufType

class bhkPhysicsSystemBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('dataSize', c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkPhysicsSystemBufType

class bhkMoppBvTreeShapeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('shapeID', c_uint32),
        ('buildType', c_uint8),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkMoppBvTreeShapeBufType

class bhkPackedNiTriStripsShapeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('material', c_uint32),
        ('radius', c_float),
        ('dataID', c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkPackedNiTriStripsShapeBufType

class bhkCompressedMeshShapeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('radius', c_float),
        ('dataID', c_uint32),
        ('bitsPerIndex', c_uint32),
        ('bitsPerWIndex', c_uint32),
        ('maskIndex', c_uint32),
        ('maskWIndex', c_uint32),
        ('error', c_float),
        ('materialType', c_uint8),
        ('userData', c_uint32),
        ('unkFloat', c_float),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkCompressedMeshShapeBufType

class bhkRigidBodyProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('shapeID', c_uint32),
        ('collisionFilter_layer', c_uint8),
	    ('collisionFilter_flags', c_uint8),
	    ('collisionFilter_group', c_uint16),
	    ('broadPhaseType', c_uint8),
	    ('worldObjData', c_uint32),    
	    ('worldObjSize', c_uint32),
	    ('worldObjCapFlags', c_uint32),
        ('childCount', c_uint16),
        ('collisionResponse', c_uint8),
        ('processContactCallbackDelay', c_uint16),
        ('unknownInt1', c_uint32),
        ('collisionFilterCopy_layer', c_uint8),
        ('collisionFilterCopy_flags', c_uint8),
        ('collisionFilterCopy_group', c_uint16),
        ('unused2_1', c_uint8),
        ('unused2_2', c_uint8),
        ('unused2_3', c_uint8),
        ('unused2_4', c_uint8),
        ('unknownInt2', c_uint32),
        ('collisionResponse2', c_uint8),
        ('unused3', c_uint8),
        ('processContactCallbackDelay2', c_uint16),
        ('translation', VECTOR4),
        ('rotation', VECTOR4),
        ('linearVelocity', VECTOR4),
        ('angularVelocity', VECTOR4),
        ('inertiaMatrix', VECTOR12),
        ('center', VECTOR4),
        ('mass', c_float),
        ('linearDamping', c_float),
        ('angularDamping', c_float),
        ('timeFactor', c_float),
        ('unusedByte4', c_uint8),
        ('gravityFactor', c_float),
        ('friction', c_float),
        ('rollingFrictionMult', c_float),
        ('restitution', c_float),
        ('maxLinearVelocity', c_float),
        ('maxAngularVelocity', c_float),
        ('unusedByte3', c_uint8),
        ('penetrationDepth', c_float),
        ('motionSystem', c_uint8),
        ('deactivatorType', c_uint8),
        ('solverDeactivation', c_uint8),
        ('qualityType', c_uint8),
        ('autoRemoveLevel', c_uint8),
        ('responseModifierFlag', c_uint8),
        ('numShapeKeysInContactPointProps', c_uint8),
        ('forceCollideOntoPpu', c_uint8),
        ('unusedInts1_0', c_uint32),
        ('unusedInts1_1', c_uint32),
        ('unusedInts1_2', c_uint32),
        ('unusedBytes2_0', c_uint8),
        ('unusedBytes2_1', c_uint8),
        ('unusedBytes2_2', c_uint8),
        ('unknownBytes12', c_uint8 * 12),
        ('unknownBytes04', c_uint8 * 4),
        ('constraintCount', c_uint16),
        ('bodyFlagsInt', c_uint32),
        ('bodyFlags', c_uint16)]
    
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkRigidBodyBufType

    def extract_field(self, shape, fieldname, fieldtype, game='SKYRIM'):
        """Extract a single field value to the shape."""
        try:
            if fieldname in ['collisionFilter_layer', 'collisionFilterCopy_layer']:
                shape[fieldname] = SkyrimCollisionLayer(self.__getattribute__(fieldname)).name
            elif fieldname == 'broadPhaseType':
                shape[fieldname] = BroadPhaseType(self.broadPhaseType).name
            elif fieldname == 'collisionResponse':
                shape[fieldname] = hkResponseType(self.collisionResponse).name
            elif fieldname == 'collisionResponse2':
                shape[fieldname] = hkResponseType(self.collisionResponse2).name
            elif fieldname == 'motionSystem':
                shape[fieldname] = hkMotionType(self.motionSystem).name
            elif fieldname == 'deactivatorType':
                shape[fieldname] = hkDeactivatorType(self.deactivatorType).name
            elif fieldname == 'solverDeactivation': 
                shape[fieldname] = hkSolverDeactivation(self.solverDeactivation).name
            elif fieldname == 'qualityType':
                shape[fieldname] = hkQualityType(self.qualityType).name
            else:
                super().extract_field(shape, fieldname, fieldtype, game=game)
        except:
            super().extract_field(shape, fieldname, fieldtype, game=game)


class bhkSimpleShapePhantomBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('shapeID', c_uint32),
        ('collisionFilter_layer', c_uint8),
	    ('collisionFilter_flags', c_uint8),
	    ('collisionFilter_group', c_uint16),
	    ('broadPhaseType', c_uint8),
	    ('worldObjData', c_uint32),    
	    ('worldObjSize', c_uint32),
	    ('worldObjCapFlags', c_uint32),
        ('childCount', c_uint16),
        ('transform', MATRIX4),
        ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkSimpleShapePhantomBufType

class bhkBoxShapeProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("bhkMaterial", c_uint32),
        ("bhkRadius", c_float),
        ("bhkDimensions", VECTOR3)]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkBoxShapeBufType

class bhkCapsuleShapeProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("bhkMaterial", c_uint32),
        ("bhkRadius", c_float),
        ("point1", VECTOR3),
        ("radius1", c_float),
        ("point2", VECTOR3),
        ("radius2", c_float)]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkCapsuleShapeBufType

class bhkSphereShapeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("bhkMaterial", c_uint32),
        ("bhkRadius", c_float),
        ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkSphereShapeBufType

class bhkConvexVerticesShapeProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("bhkMaterial", c_uint32),
        ("bhkRadius", c_float),
        ('verticesProp_data', c_uint32),
	    ('verticesProp_size', c_uint32),
	    ('verticesProp_flags', c_uint32),
        ('normalsProp_data', c_uint32),
	    ('normalsProp_size', c_uint32),
	    ('normalsProp_flags', c_uint32),
	    ('vertsCount', c_uint32),
	    ('normalsCount', c_uint32),
          ]
    def __init__(self, values=None, game='SKYRIM'):
        super().__init__(values=values, game=game)
        self.bufType = PynBufferTypes.bhkConvexVerticesShapeBufType

class bhkListShapeProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("bhkMaterial", c_uint32),
        ('childShape_data', c_uint32),
        ('childShape_size', c_uint32),
        ('childShape_flags', c_uint32),
        ('childFilter_data', c_uint32),
        ('childFilter_size', c_uint32),
        ('childFilter_flags', c_uint32),
        ('childCount', c_uint32) ]
    
    def __init__(self, values=None, game='SKYRIM'):
        super().__init__(values=values, game=game)
        self.bufType = PynBufferTypes.bhkListShapeBufType

    def extract_field(self, shape, fieldname, fieldtype, game='SKYRIM'):
        """Extract a single field value to the shape."""
        if fieldname == 'bhkMaterial':
            shape[fieldname] = SkyrimHavokMaterial(self.bhkMaterial).name
        else:
            super().extract_field(shape, fieldname, fieldtype, game=game)


class bhkConvexTransformShapeProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("shapeID", c_uint32),
        ("bhkMaterial", c_uint32),
        ("bhkRadius", c_float),
        ('transform', MATRIX4) ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkConvexTransformShapeBufType

class bhkRagdollConstraintBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('entityCount', c_uint16),
        ('priority', c_uint32),
        ('twistA', VECTOR4),
        ('planeA', VECTOR4),
        ('motorA', VECTOR4),
        ('pivotA', VECTOR4),
        ('twistB', VECTOR4),
        ('planeB', VECTOR4),
        ('motorB', VECTOR4),
        ('pivotB', VECTOR4),
        ('coneMaxAngle', c_float),
        ('planeMinAngle', c_float),
        ('planeMaxAngle', c_float),
        ('twistMinAngle', c_float),
        ('twistMaxAngle', c_float),
        ('maxFriction', c_float),
        ('motorType', c_uint8),
        # bhkPositionConstraintMotor motorPosition;
        ('positionConstraint_tau', c_float),
        ('positionConstraint_damping', c_float),
        ('positionConstraint_propRV', c_float),
        ('positionConstraint_constRV', c_float),
        # bhkVelocityConstraintMotor motorVelocity;
        ('velocityConstraint_tau', c_float),
        ('velocityConstraint_velocityTarget', c_float),
        ('velocityConstraint_useVTFromCT', c_uint8),
        # bhkSpringDamperConstraintMotor motorSpringDamper;
        ('springDamp_springConstant', c_float),
        ('springDamp_springDamping', c_float),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkRagdollConstraintBufType


class BSFurnitureMarkerNodeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("position_count", c_uint32) ]

    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSFurnitureMarkerNodeBufType


class FurnitureMarkerDataBuf(pynStructure):
    _fields_ = [
        ("offset", VECTOR3),
        ("heading", c_float),
        ("animation_type", c_uint16),
        ("entry_points", c_uint16) ]

    def __init__(self, values=None):
        super().__init__(values=values)

    @property
    def animation_type_name(self) -> str:
        try:
            return FurnAnimationType(self.animation_type).name
        except:
            return str(self.animation_type)
    
    @animation_type_name.setter
    def animation_type_name(self, val):
        try:
            self.animation_type = FurnAnimationType[val].value
        except:
            self.animation_type = int(val, 0)

    @property
    def entry_points_list(self) -> str:
        lst = []
        for i in range(16):
            if (self.entry_points & (1 << i)) != 0:
                try:
                    lst.append(FurnEntryPoints(self.entry_points & (1 << i)).name)
                except:
                    lst.append(str(self.entry_points & (1 << i)))
        return "|".join(lst)
    
    @entry_points_list.setter
    def entry_points_list(self, val):
        lst = val.split("|")
        self.entry_points = 0
        for e in lst:
            if e:
                try:
                    self.entry_points |= FurnEntryPoints[e].value
                except:
                    self.entry_points |= int(e, 0)


class ConnectPointBuf(pynStructure):
    _fields_ = [
        ("parent", c_char * 256),
        ("name", c_char * 256),
        ("rotation", VECTOR4),
        ("translation", VECTOR3),
        ("scale", c_float)]


class NiObjectBuf(pynStructure):
    _fields_ = [
        ('blockSize', c_uint32),
        ('groupID', c_uint16),
        ('id', c_uint32),
    ]


class NiNodeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('id', c_uint32),
        ("nameID", c_uint32),
        ("controllerID", c_uint32),
        ("extraDataCount", c_uint16),
        ("flags", c_uint32),
        ("transform", TransformBuf),
        ("collisionID", c_uint32),
        ("childCount", c_uint16),
        ("effectCount", c_uint16),
    ]
    def __init__(self, values=None):
        self.transform.set_identity()
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiNodeBufType
        self.nameID = self.controllerID = self.collisionID = NODEID_NONE

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.nameID = NODEID_NONE
        c.controllerID = NODEID_NONE
        c.collisionID = NODEID_NONE
        return c


class BSValueNodeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('id', c_uint32),
        ("nameID", c_uint32),
        ("controllerID", c_uint32),
        ("extraDataCount", c_uint16),
        ("flags", c_uint32),
        ("transform", TransformBuf),
        ("collisionID", c_uint32),
        ("childCount", c_uint16),
        ("effectCount", c_uint16),
        ("value", c_int),
        ("valueNodeFlags", c_uint8),
    ]
    def __init__(self, values=None):
        self.transform.set_identity()
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSValueNodeBufType
        self.nameID = self.controllerID = self.collisionID = NODEID_NONE

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.nameID = NODEID_NONE
        c.controllerID = NODEID_NONE
        c.collisionID = NODEID_NONE
        return c


class BSXFlagsBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("stringRefCount", c_uint16),
        ("integerData", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSXFlagsBufType


class BSBoundBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("id", c_uint32),
        ("nameID", c_uint32),
        ("center", VECTOR3),
        ("halfExtents", VECTOR3),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSBoundBufType


class BSBoneLODBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("id", c_uint32),
        ("nameID", c_uint32),
        ("lodCount", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSBoneLODBufType

class BoneLODInfoBuf(pynStructure):
    _fields_ = [
        ("distance", c_uint32),
        ("nameID", c_uint32),
    ]

class BSInvMarkerBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("stringRefCount", c_uint16),
        ("rot0", c_uint16),
        ("rot1", c_uint16),
        ("rot2", c_uint16),
        ("zoom", c_float),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSInvMarkerBufType


class NiShapeBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("id", c_uint32),
        ("nameID", c_uint32),
        ("controllerID", c_uint32),
        ("extraDataCount", c_uint16),
        ("flags", c_uint32),
        ("transform", TransformBuf),
        ("propertyCount", c_uint16),
        ("collisionID", c_uint32),
        ("hasVertices", c_uint8),
        ("hasNormals", c_uint8),
        ("hasVertexColors", c_uint8),
        ("hasUV", c_uint8),
        ("hasFullPrecision", c_uint8),
        ("boundingSphereCenter", VECTOR3),
        ("boundingSphereRadius", c_float),
        ("vertexCount", c_uint32),
        ("triangleCount", c_uint32),
        ("skinInstanceID", c_uint32),
        ("shaderPropertyID", c_uint32),
        ("alphaPropertyID", c_uint32),
        ("vertexDesc", c_uint64),
        ]
    def __init__(self, values=None):
        self.nameID = self.controllerID = self.collisionID = NODEID_NONE
        self.skinInstanceID = self.shaderPropertyID = self.alphaPropertyID = NODEID_NONE
        self.transform.set_identity()
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiShapeBufType



class BSDynamicTriShapeBuf(NiShapeBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSDynamicTriShapeBufType



class BSTriShapeBuf(NiShapeBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSTriShapeBufType


class BSSubIndexTriShapeBuf(NiShapeBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSSubIndexTriShapeBufType


class NiTriStripsBuf(NiShapeBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiTriStripsBufType


class NiTriShapeBuf(NiShapeBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiTriShapeBufType


class BSMeshLODTriShapeBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("id", c_uint32),
        ("nameID", c_uint32),
        ("controllerID", c_uint32),
        ("extraDataCount", c_uint16),
        ("flags", c_uint32),
        ("transform", TransformBuf),
        ("propertyCount", c_uint16),
        ("collisionID", c_uint32),
        ("hasVertices", c_uint8),
        ("hasNormals", c_uint8),
        ("hasVertexColors", c_uint8),
        ("hasUV", c_uint8),
        ("hasFullPrecision", c_uint8),
        ("boundingSphereCenter", VECTOR3),
        ("boundingSphereRadius", c_float),
        ("vertexCount", c_uint32),
        ("triangleCount", c_uint32),
        ("skinInstanceID", c_uint32),
        ("shaderPropertyID", c_uint32),
        ("alphaPropertyID", c_uint32),
        ("vertexDesc", c_uint64),
        ("lodSize0", c_uint32),
        ("lodSize1", c_uint32),
        ("lodSize2", c_uint32),
        ]
    def __init__(self, values=None):
        self.nameID = self.controllerID = self.collisionID = NODEID_NONE
        self.skinInstanceID = self.shaderPropertyID = self.alphaPropertyID = NODEID_NONE
        self.transform.set_identity()
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSMeshLODTriShapeBufType


class BSLODTriShapeBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("id", c_uint32),
        ("nameID", c_uint32),
        ("controllerID", c_uint32),
        ("extraDataCount", c_uint16),
        ("flags", c_uint32),
        ("transform", TransformBuf),
        ("propertyCount", c_uint16),
        ("collisionID", c_uint32),
        ("hasVertices", c_uint8),
        ("hasNormals", c_uint8),
        ("hasVertexColors", c_uint8),
        ("hasUV", c_uint8),
        ("hasFullPrecision", c_uint8),
        ("boundingSphereCenter", VECTOR3),
        ("boundingSphereRadius", c_float),
        ("vertexCount", c_uint32),
        ("triangleCount", c_uint32),
        ("skinInstanceID", c_uint32),
        ("shaderPropertyID", c_uint32),
        ("alphaPropertyID", c_uint32),
        ("vertexDesc", c_uint64),
        ("level0", c_uint32),
        ("level1", c_uint32),
        ("level2", c_uint32),
        ]
    def __init__(self, values=None):
        self.nameID = self.controllerID = self.collisionID = NODEID_NONE
        self.skinInstanceID = self.shaderPropertyID = self.alphaPropertyID = NODEID_NONE
        self.transform.set_identity()
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSLODTriShapeBufType
        

class TimeControllerFlags:
    # <bitfield name="TimeControllerFlags" storage="ushort">
    #     Flags for NiTimeController
    #     <member width="1" pos="0" mask="0x0001" name="Anim Type" type="AnimType" />
    #     <member width="2" pos="1" mask="0x0006" name="Cycle Type" type="CycleType" default="CYCLE_CLAMP" />
    #     <member width="1" pos="3" mask="0x0008" name="Active" type="bool" default="true" />
    #     <member width="1" pos="4" mask="0x0010" name="Play Backwards" type="bool" />
    #     <member width="1" pos="5" mask="0x0020" name="Manager Controlled" type="bool" />
    #     <member width="1" pos="6" mask="0x0040" name="Compute Scaled Time" type="bool" default="true" />
    #     <member width="1" pos="7" mask="0x0080" name="Forced Update" type="bool" />
    # </bitfield>
    def __init__(self,
                 anim_type=AnimType.APP_TIME,
                 cycle_type=CycleType.LOOP,
                 active=True,
                 play_backwards=False,
                 manager_controlled=False,
                 compute_scaled=True,
                 forced_update=False):
        self.anim_type = anim_type
        self.cycle_type = cycle_type
        self.active = active
        self.play_backwards = play_backwards
        self.manager_controlled = manager_controlled
        self.compute_scaled = compute_scaled
        self.forced_update = forced_update

    @property
    def flags(self):
        return (
            self.anim_type
            | (self.cycle_type << 1)
            | ((1 if self.active else 0) << 3)
            | ((1 if self.play_backwards else 0) << 4)
            | ((1 if self.manager_controlled else 0) << 5)
            | ((1 if self.compute_scaled else 0) << 6)
            | ((1 if self.forced_update else 0) << 7)
        )
    
    @flags.setter
    def flags(self, val):
        self.anim_type = val & 1
        self.cycle_type = (val >> 1) & 3
        self.active = (((val >> 3) & 1) != 0)
        self.play_backwards = (((val >> 4) & 1) != 0)
        self.manager_controlled = (((val >> 5) & 1) != 0)
        self.compute_scaled = (((val >> 6) & 1) != 0)
        self.forced_update = (((val >> 7) & 1) != 0)


class NiControllerManagerBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("nextControllerID", c_uint32),
        ("flags", c_uint16),
        ("frequency", c_float),
        ("phase", c_float),
        ("startTime", c_float),
        ("stopTime", c_float),
        ("targetID", c_uint32),
        ("cumulative", c_uint8),
        ("controllerSequenceCount", c_uint16),
        ("objectPaletteID", c_uint32)]
    def __init__(self, values=None):
        self.nextControllerID = NODEID_NONE
        self.targetID = NODEID_NONE
        self.objectPaletteID = NODEID_NONE
        self.flags = 76
        self.frequency = 1.0
        self.phase = 0
        self.startTime = sys.float_info.max
        self.stopTime = -sys.float_info.max
        self.cumulative = False
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiControllerManagerBufType


class NiMultiTargetTransformControllerBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ('id', c_uint32),
        ("nextControllerID", c_uint32),
        ("flags", c_uint16),
        ("frequency", c_float),
        ("phase", c_float),
        ("startTime", c_float),
        ("stopTime", c_float),
        ("targetID", c_uint32),
        ("targetCount", c_uint16)]
    def __init__(self, values=None):
        self.nextControllerID = NODEID_NONE
        self.targetID = NODEID_NONE
        self.flags = 108
        self.frequency = 1.0
        self.phase = 0
        self.startTime = sys.float_info.max
        self.stopTime = -sys.float_info.max
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiMultiTargetTransformControllerBufType

class NiControllerSequenceBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("id", c_uint32), 
        ("nameID", c_uint32), 
        ("arrayGrowBy", c_uint32), 
        ("controlledBlocksCount", c_uint16),
        ("weight", c_float), 
        ("textKeyID", c_uint32),
        ("cycleType", c_uint32),
        ("frequency", c_float),
        ("startTime", c_float),
        ("stopTime", c_float),
        ("managerID", c_uint32),
        ("accumRootNameID", c_uint32),
        ("animNotesID", c_uint32),
        ("animNotesCount", c_uint16),
    ]
    def __init__(self, values=None):
        self.arrayGrowBy = 1
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiControllerSequenceBufType
        self.nameID = NODEID_NONE
        self.textKeyID = NODEID_NONE
        self.managerID = NODEID_NONE
        self.accumRootNameID = NODEID_NONE
        self.animNotesID = NODEID_NONE

class ControllerLinkBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("interpolatorID", c_uint32),
        ("controllerID", c_uint32),
        ("priority", c_uint8),
        ("nodeName", c_uint32),
        ("propType", c_uint32),
        ("ctrlType", c_uint32), 
        ("ctrlID", c_uint32), 
        ("interpID", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiControllerLinkBufType
        self.interpolatorID = NODEID_NONE
        self.controllerID = NODEID_NONE
        self.nodeName = NODEID_NONE
        self.propType = NODEID_NONE
        self.ctrlType = NODEID_NONE
        self.ctrlID = NODEID_NONE
        self.interpID = NODEID_NONE


class LightingShaderControlledVariable(PynIntEnum):
    Refraction_Strength = 0
    Unknown_3 = 3
    Unknown_4 = 4
    Environment_Map_Scale = 8
    Glossiness = 9
    Specular_Strength = 10
    Emissive_Multiple = 11
    Alpha = 12
    Unknown_13 = 13
    Unknown_14 = 14
    U_Offset = 20
    U_Scale = 21
    V_Offset = 22
    V_Scale = 23

class EffectShaderControlledColor(PynIntEnum):
    EMISSIVE = 0

class NiSingleInterpControllerBuf(pynStructure):
    _fields_ = [
	    ("bufSize", c_uint16),
        ("bufType", c_uint16),
        ("nextControllerID", c_uint32),
        ("flags", c_uint16),
        ("frequency", c_float),
        ("phase", c_float),
        ("startTime", c_float),
        ("stopTime", c_float),
	    ("targetID", c_uint32),
        ("interpolatorID", c_uint32),
        ("controlledVariable", c_uint32),
    ]
    def __init__(self, values=None, buftype=PynBufferTypes.NiSingleInterpControllerBufType):
        self.nextControllerID = NODEID_NONE
        self.targetID = NODEID_NONE
        self.interpolatorID = NODEID_NONE
        super().__init__(values=values)
        self.bufType = buftype

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.nextControllerID = NODEID_NONE
        c.targetID = NODEID_NONE
        c.interpolatorID = NODEID_NONE
        return c
    
    def copyto(self, other, exclude=[]):
        c = super().copyto(other, exclude=exclude)
        c.nextControllerID = NODEID_NONE
        c.targetID = NODEID_NONE
        c.interpolatorID = NODEID_NONE
        return c


class BSEffectShaderPropertyFloatControllerBuf(NiSingleInterpControllerBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSEffectShaderPropertyFloatControllerBufType


class BSEffectShaderPropertyColorControllerBuf(NiSingleInterpControllerBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSEffectShaderPropertyColorControllerBufType


class BSNiAlphaPropertyTestRefControllerBuf(NiSingleInterpControllerBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSNiAlphaPropertyTestRefControllerBufType


class NiTransformControllerBuf(NiSingleInterpControllerBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiTransformControllerBufType


class LightingShaderControlledColor(PynIntEnum): 
    SPECULAR = 0
    EMISSIVE = 1

class BSLightingShaderPropertyColorControllerBuf(NiSingleInterpControllerBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSLightingShaderPropertyColorControllerBufType


class BSLightingShaderPropertyFloatControllerBuf(NiSingleInterpControllerBuf):
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSLightingShaderPropertyFloatControllerBufType


class NiTransformInterpolatorBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("translation", VECTOR3),
        ("rotation", VECTOR4),
        ("scale", c_float),
        ("dataID", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiTransformInterpolatorBufType

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.dataID = NODEID_NONE
        return c
    
    def copyto(self, other, exclude=[]):
        c = super().copyto(other, exclude=exclude)
        c.dataID = NODEID_NONE
        return c


class NiFloatInterpolatorBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("value", c_float),
        ("dataID", c_uint32),
    ]
    def __init__(self, values=None):
        self.floatValue = -sys.float_info.max
        self.dataID = NODEID_NONE
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiFloatInterpolatorBufType

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.dataID = NODEID_NONE
        return c
    
    def copyto(self, other, exclude=[]):
        c = super().copyto(other, exclude=exclude)
        c.dataID = NODEID_NONE
        return c


class NiBoolInterpolatorBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("value", c_float),
        ("dataID", c_uint32),
    ]
    def __init__(self, values=None):
        self.boolValue = -sys.float_info.max
        self.dataID = NODEID_NONE
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiBoolInterpolatorBufType

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.dataID = NODEID_NONE
        return c
    
    def copyto(self, other, exclude=[]):
        c = super().copyto(other, exclude=exclude)
        c.dataID = NODEID_NONE
        return c


class NiPoint3InterpolatorBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("value", VECTOR3),
        ("dataID", c_uint32),
    ]
    def __init__(self, values=None):
        self.dataID = NODEID_NONE
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiPoint3InterpolatorBufType

    def copy(self, exclude=[]):
        c = super().copy(exclude=exclude)
        c.dataID = NODEID_NONE
        return c
    
    def copyto(self, other, exclude=[]):
        c = super().copyto(other, exclude=exclude)
        c.dataID = NODEID_NONE
        return c


class InterpBlendFlags(PynIntFlag):
    NONE = 0, 
    MANAGER_CONTROLLED = 1

class InterpBlendItem(pynStructure):
	("interpolatorID", c_uint32),
	("weight", c_float),
	("normalizedWeight", c_float),
	("priority", c_uint8),
	("easeSpinner", c_float),

class NiBlendInterpolatorBuf(pynStructure):
    _fields_ = [
        # NiFloatInterpolator
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("flags", c_uint8),
        ("arraySize", c_uint8),
        ("weightThreshold", c_float),
        ("interpCount", c_uint8),
        ("singleIndex", c_uint8),
        ("highPriority", c_char),
        ("nextHighPriority", c_char),
        ("singleTime", c_float),
        ("highWeightsSum", c_float),
        ("nextHighWeightsSum", c_float),
        ("highEaseSpinner", c_float),
        # NiBlendBoolInterpretor
        ("boolValue", c_uint8),
        # NIBlendFloatInterpolator
        ("floatValue", c_float),
        # NiBlendPoint3Interpolator
        ("point3Value", VECTOR3),
    ]
    def __init__(self, values=None):
        self.flags = InterpBlendFlags.MANAGER_CONTROLLED
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiBlendInterpolatorBufType


class NiAnimationKeyGroupBuf(pynStructure):
    _fields_ = [
        ("numKeys", c_uint32),
        ("interpolation", c_uint32)
    ]


class NiTransformDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("rotationType", c_uint32), 
        ("rotationKeyCount", c_uint32),
        ("xRotations", NiAnimationKeyGroupBuf),
        ("yRotations", NiAnimationKeyGroupBuf),
        ("zRotations", NiAnimationKeyGroupBuf),
        ("translations", NiAnimationKeyGroupBuf),
        ("scales", NiAnimationKeyGroupBuf),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiTransformDataBufType


class NiPosDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("keys", NiAnimationKeyGroupBuf), 
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiPosDataBufType


class NiFloatDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("keys", NiAnimationKeyGroupBuf), 
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiFloatDataBufType


class KeyDataBuf(pynStructure):
    def getbuf(self):
        return self
    

class NiAnimKeyFloatBuf(KeyDataBuf):
    _fields_ = [
        ("time", c_float),
        ("value", c_float),
        ("forward", c_float),
        ("backward", c_float),
    ]
    def __init__(self, time=0, value=0, forward=0, backward=0):
        self.time = time
        self.value = value
        self.forward = forward
        self.backward = backward

class NiAnimKeyLinearBuf(KeyDataBuf):
    _fields_ = [
        ("time", c_float),
        ("value", c_float)
    ]

class NiAnimKeyLinearQuatBuf(KeyDataBuf):
    _fields_ = [
        ("time", c_float),
        ("value", VECTOR4)
    ]

class NiAnimKeyLinearTransBuf(KeyDataBuf):
    _fields_ = [
        ("time", c_float),
        ("value", VECTOR3)
    ]

class NiAnimKeyQuadTransBuf(KeyDataBuf):
    _fields_ = [
        ("time", c_float),
        ("value", VECTOR3),
        ("forward", VECTOR3),
        ("backward", VECTOR3),
    ]

class NiDefaultAVObjectPaletteBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("sceneID", c_uint32),
        ("objCount", c_uint16),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiDefaultAVObjectPaletteBufType

class NiTextKeyExtraDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("textKeyCount", c_uint16),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiTextKeyExtraDataBufType

class NiIntegerExtraDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("integerData", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiIntegerExtraDataBufType

class BSBehaviorGraphExtraDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("behaviorGraphFileID", c_uint32),
        ("controlsBaseSkeleton", c_uint8),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSBehaviorGraphExtraDataBufType

class NiStringExtraDataBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("nameID", c_uint32),
        ("stringDataID", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiStringExtraDataBufType

class TextKeyBuf(pynStructure):
    _fields_ = [
        ("time", c_float),
        ("valueID", c_uint32),
    ]

class NiKeyType(PynIntEnum):
    NO_INTERP = 0
    LINEAR_KEY = 1
    QUADRATIC_KEY = 2
    TBC_KEY = 3
    XYZ_ROTATION_KEY = 4
    CONST_KEY = 5

class FurnAnimationType(PynIntEnum):
    SIT = 1
    SLEEP = 2
    LEAN = 4 

class FurnEntryPoints(PynIntFlag):
    FRONT = 1
    BEHIND = 1 << 1
    RIGHT = 1 << 2
    LEFT = 1 << 3
    UP = 1 << 4

class VERTEX_WEIGHT_PAIR(Structure):
    _fields_ = [("vertex", c_uint16),
                ("weight", c_float)]
