
"""
Value and type definitions for nif structures
"""

import struct
from enum import Enum, IntFlag, IntEnum
from ctypes import * # c_void_p, c_int, c_bool, c_char_p, c_wchar_p, c_float, c_uint8, c_uint16, c_uint32, create_string_buffer, Structure, cdll, pointer, addressof

class PynIntFlag(IntFlag):
    @property
    def fullname(self):
        s = []
        for f in type(self):
            if f in self:
                s.append(f)
        return " | ".join(list(map(lambda x: x.name, s)))

    @classmethod
    def parse(cls, value):
        valuelist = value.split(" | ")
        flags = 0
        for v in valuelist:
            flags |= cls[v]
        return flags


VECTOR3 = c_float * 3
VECTOR4 = c_float * 4
VECTOR6_SHORT = c_uint16 * 6
VECTOR12 = c_float * 12
MATRIX3 = VECTOR3 * 3

# Types of root nodes
RT_NINODE = 0
RT_BSFADENODE = 1

class RootFlags(PynIntFlag):
    HIDDEN = 1
    SELECTIVE_UPDATE = 1 << 1
    SELECTIVE_UPDATE_TRANSF = 1 << 2
    SELECTIVE_UPDATE_CONTR = 1 << 3
    SELECTIVE_UPDATE_RIGID = 1 << 4
    DISPLAY_OBJECT = 1 << 5
    DISABLE_SORTING = 1 << 6
    SEL_UPD_TRANSF_OVERRIDE = 1 << 7
    SAVE_EXT_GEOM_DATA = 1 << 9
    NO_DECALS = 1 << 10
    ALWAYS_DRAW = 1 << 11
    MESH_LOD = 1 << 12
    FIXED_BOUND = 1 << 13
    TOP_FADE_NODE = 1 << 14
    IGNORE_FADE = 1 << 15
    NO_ANIM_SYNC_X = 1 << 16
    NO_ANIM_SYNC_Y = 1 << 17
    NO_ANIM_SYNC_Z = 1 << 18
    NO_ANIM_SYNC_S = 1 << 19
    NO_DISMEMBER = 1 << 20
    NO_DISMEMBER_VALIDITY = 1 << 21
    RENDER_USE = 1 << 22
    MATERIALS_APPLIED = 1 << 23
    HIGH_DETAIL = 1 << 24
    FORCE_UPDATE = 1 << 25
    PREPROCESSED_NODE = 1 << 26

class BSLSPAttrs(Structure):
    _fields_ = [
	    ('Shader_Type', c_uint32),
	    ('Shader_Flags_1', c_uint32),
	    ('Shader_Flags_2', c_uint32),
	    ('UV_Offset_U', c_float),
	    ('UV_Offset_V', c_float),
	    ('UV_Scale_U', c_float),
	    ('UV_Scale_V', c_float),
	    ('Emissive_Color_R', c_float),
	    ('Emissive_Color_G', c_float),
	    ('Emissive_Color_B', c_float),
	    ('Emissive_Color_A', c_float),
	    ('Emissive_Mult', c_float),
	    ('Tex_Clamp_Mode', c_uint32),
	    ('Alpha', c_float),
	    ('Refraction_Str', c_float),
	    ('Glossiness', c_float),
	    ('Spec_Color_R', c_float),
	    ('Spec_Color_G', c_float),
	    ('Spec_Color_B', c_float),
	    ('Spec_Str', c_float),
	    ('Soft_Lighting', c_float),
	    ('Rim_Light_Power', c_float),
	    ('Skin_Tint_Alpha', c_float),
	    ('Skin_Tint_Color_R', c_float),
	    ('Skin_Tint_Color_G', c_float),
	    ('Skin_Tint_Color_B', c_float)
        ]
    def __str__(self):
        s = ""
        for attr in self._fields_:
            if len(s) > 0:
                s = s + "\n"
            if attr[0].startswith('Shader_Flags'):
                s = s + f"\t{attr[0]} = {getattr(self, attr[0]):32b}"
            else:        
                s = s + f"\t{attr[0]} = {getattr(self, attr[0])}"
        return s

    def __eq__(self, other):
        return (self.Shader_Type == other.Shader_Type) and \
            (self.Shader_Flags_1 == other.Shader_Flags_1) and \
            (self.Shader_Flags_2 == other.Shader_Flags_2) and \
            (round(self.UV_Offset_U, 4) == round(other.UV_Offset_U, 4)) and \
            (round(self.UV_Offset_V, 4) == round(other.UV_Offset_V, 4)) and \
            (round(self.UV_Scale_U, 4) == round(other.UV_Scale_U, 4)) and \
            (round(self.UV_Scale_V, 4) == round(other.UV_Scale_V, 4)) and \
            (round(self.Emissive_Color_R, 4) == round(other.Emissive_Color_R, 4)) and \
            (round(self.Emissive_Color_G, 4) == round(other.Emissive_Color_G, 4)) and \
            (round(self.Emissive_Color_B, 4) == round(other.Emissive_Color_B, 4)) and \
            (round(self.Emissive_Color_A, 4) == round(other.Emissive_Color_A, 4)) and \
            (round(self.Emissive_Mult, 4) == round(other.Emissive_Mult, 4)) and \
            (self.Tex_Clamp_Mode == other.Tex_Clamp_Mode) and \
            (round(self.Alpha, 4) == round(other.Alpha, 4)) and \
            (round(self.Refraction_Str, 4) == round(other.Refraction_Str, 4)) and \
            (round(self.Glossiness, 4) == round(other.Glossiness, 4)) and \
            (round(self.Spec_Color_R, 4) == round(other.Spec_Color_R, 4)) and \
            (round(self.Spec_Color_G, 4) == round(other.Spec_Color_G, 4)) and \
            (round(self.Spec_Color_B, 4) == round(other.Spec_Color_B, 4)) and \
            (round(self.Spec_Str, 4) == round(other.Spec_Str, 4)) and \
            (round(self.Soft_Lighting, 4) == round(other.Soft_Lighting, 4)) and \
            (round(self.Rim_Light_Power, 4) == round(other.Rim_Light_Power, 4)) and \
            (round(self.Skin_Tint_Alpha, 4) == round(other.Skin_Tint_Alpha, 4)) and \
            (round(self.Skin_Tint_Color_R, 4) == round(other.Skin_Tint_Color_R, 4)) and \
            (round(self.Skin_Tint_Color_G, 4) == round(other.Skin_Tint_Color_G, 4)) and \
            (round(self.Skin_Tint_Color_B, 4) == round(other.Skin_Tint_Color_B, 4))

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

BSLSPAttrs_p = POINTER(BSLSPAttrs)

class BSESPAttrs(Structure):
    _fields_ = [
	    ('Shader_Flags_1', c_uint32),
	    ('Shader_Flags_2', c_uint32),
	    ('UV_Offset_U', c_float),
	    ('UV_Offset_V', c_float),
	    ('UV_Scale_U', c_float),
	    ('UV_Scale_V', c_float),
	    ('Tex_Clamp_Mode', c_uint32),
        ('Lighting_Influence', c_char),
        ('Env_Map_Min_LOD', c_char),
	    ('Falloff_Start_Angle', c_uint32),
	    ('Falloff_Stop_Angle', c_uint32),
	    ('Falloff_Start_Opacity', c_uint32),
	    ('Falloff_Stop_Opacity', c_uint32),
	    ('Emissive_Color_R', c_float),
	    ('Emissive_Color_G', c_float),
	    ('Emissive_Color_B', c_float),
	    ('Emissive_Color_A', c_float),
	    ('Emissive_Mult', c_float),
	    ('Soft_Falloff_Depth', c_uint32),
	    ('Env_Map_Scale', c_uint32)
        ]
    def __str__(self):
        s = ""
        for attr in self._fields_:
            if len(s) > 0:
                s = s + "\n"
            s = s + f"\t{attr[0]} = {getattr(self, attr[0])}"
        return s

    def __eq__(self, other):
        return (self.Shader_Flags_1 == other.Shader_Flags_1) and \
            (self.Shader_Flags_2 == other.Shader_Flags_2) and \
            (round(self.UV_Offset_U, 4) == round(other.UV_Offset_U, 4)) and \
            (round(self.UV_Offset_V, 4) == round(other.UV_Offset_V, 4)) and \
            (round(self.UV_Scale_U, 4) == round(other.UV_Scale_U, 4)) and \
            (round(self.UV_Scale_V, 4) == round(other.UV_Scale_V, 4)) and \
            (round(self.Emissive_Color_R, 4) == round(other.Emissive_Color_R, 4)) and \
            (round(self.Emissive_Color_G, 4) == round(other.Emissive_Color_G, 4)) and \
            (round(self.Emissive_Color_B, 4) == round(other.Emissive_Color_B, 4)) and \
            (round(self.Emissive_Color_A, 4) == round(other.Emissive_Color_A, 4)) and \
            (round(self.Emissive_Mult, 4) == round(other.Emissive_Mult, 4)) and \
            (self.Tex_Clamp_Mode == other.Tex_Clamp_Mode) and \
            (self.Falloff_Start_Angle == other.Falloff_Start_Angle) and \
            (self.Falloff_Stop_Angle == other.Falloff_Stop_Angle) and \
            (self.Falloff_Start_Opacity == other.Falloff_Start_Opacity) and \
            (self.Falloff_Stop_Opacity == other.Falloff_Stop_Opacity) and \
            (self.Soft_Falloff_Depth == other.Soft_Falloff_Depth) 

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

class BSLSPShaderType(IntFlag):
    Default = 0
    Environment_Map = 1
    Glow_Shader = 2
    Parallax = 3
    Face_Tint = 4
    Skin_Tint = 5
    Hair_Tint = 6
    Parallax_Occ = 7
    Multitexture_Landscape = 8
    LOD_Landscape = 9
    Snow = 10
    MultiLayer_Parallax = 11
    Tree_Anim = 12
    LOD_Objects = 13
    Sparkle_Snow = 14
    LOD_Objects_HD = 15
    Eye_Envmap = 16
    Cloud = 17
    LOD_Landscape_Noise = 18
    Multitexture_Landscape_LOD_Blend = 19
    FO4_Dismemberment = 20

class ShaderFlags1(PynIntFlag):
    SPECULAR = 1 << 0
    SKINNED = 1 << 1
    TEMP_REFRACTION = 1 << 2
    VERTEX_ALPHA = 1 << 3
    GREYSCALE_COLOR = 1 << 4
    GREYSCALE_ALPHA = 1 << 5
    USE_FALLOFF = 1 << 6
    ENVIRONMENT_MAPPING = 1 << 7
    RECEIVE_SHADOWS = 1 << 8
    CAST_SHADOWS = 1 << 9
    FACEGEN_DETAIL_MAP = 1 << 10
    PARALLAX = 1 << 11
    MODEL_SPACE_NORMALS = 1 << 12
    NON_PROJECTIVE_SHADOWS = 1 << 13
    LANDSCAPE = 1 << 14
    REFRACTION = 1 << 15
    FIRE_REFRACTION = 1 << 16
    EYE_ENVIRONMENT_MAPPING = 1 << 17
    HAIR_SOFT_LIGHTING = 1 << 18
    SCREENDOOR_ALPHA_FADE = 1 << 19
    LOCALMAP_HIDE_SECRET = 1 << 20
    FACEGEN_RGB_TINT = 1 << 21
    OWN_EMIT = 1 << 22
    PROJECTED_UV = 1 << 23
    MULTIPLE_TEXTURES = 1 << 24
    REMAPPABLE_TEXTURES = 1 << 25
    DECAL = 1 << 26
    DYNAMIC_DECAL = 1 << 27
    PARALLAX_OCCLUSION = 1 << 28
    EXTERNAL_EMITTANCE = 1 << 29
    SOFT_EFFECT = 1 << 30
    ZBUFFER_TEST = 1 << 31

class ShaderFlags2(PynIntFlag):
    ZBUFFER_WRITE = 1
    LOD_LANDSCAPE = 1 << 1
    LOD_OBJECTS = 1 << 2
    NO_FADE = 1 << 3
    DOUBLE_SIDED = 1 << 4
    VERTEX_COLORS = 1 << 5
    GLOW_MAP = 1 << 6
    ASSUME_SHADOWMASK = 1 << 7
    PACKED_TANGENT = 1 << 8
    MULTI_INDEX_SNOW = 1 << 9
    VERTEX_LIGHTING = 1 << 10
    UNIFORM_SCALE = 1 << 11
    FIT_SLOPE = 1 << 12
    BILLBOARD = 1 << 13
    NO_LOD_LAND_BLEND = 1 << 14
    ENVMAP_LIGHT_FADE = 1 << 15
    WIREFRAME = 1 << 16
    WEAPON_BLOOD = 1 << 17
    HIDE_ON_LOCAL_MAP = 1 << 18 
    PREMULT_ALPHA = 1 << 19
    CLOUD_LOD = 1 << 20
    ANISOTROPIC_LIGHTING = 1 << 21
    NO_TRANSPARENCY_MULTISAMPLING = 1 << 22
    UNUSED01 = 1 << 23
    MULTI_LAYER_PARALLAX = 1 << 24
    SOFT_LIGHTING = 1 << 25
    RIM_LIGHTING = 1 << 26
    BACK_LIGHTING = 1 << 27
    UNUSED02 = 1 << 28
    TREE_ANIM = 1 << 29
    EFFECT_LIGHTING = 1 << 30
    HD_LOD_OBJECTS = 1 << 31

class AlphaPropertyBuf(Structure):
    _fields_ = [('flags', c_uint16), ('threshold', c_uint8)]

AlphaPropertyBuf_p = POINTER(AlphaPropertyBuf)

    
class bhkCOFlags(PynIntFlag):
    ACTIVE = 1
    NOTIFY = 1 << 2
    SET_LOCAL = 1 << 3
    DBG_DISPLAY = 1 << 4
    USE_VEL = 1 << 5
    RESET = 1 << 6
    SYNC_ON_UPDATE = 1 << 7
    ANIM_TARGETED = 1 << 10
    DISMEMBERED_LIMB = 1 << 11

class hkResponseType(IntEnum):
    INVALID = 0
    SIMPLE_CONTACT = 1
    REPORTING = 2
    NONE = 3

class BroadPhaseType(IntEnum):
    INVALID = 0
    ENTITY =  1
    PHANTOM = 2
    BORDER = 3

class hkMotionType(IntEnum):
    INVALID = 0,
    DYNAMIC = 1,
    SPHERE_INERTIA = 2,
    SPHERE_STABILIZED = 3,
    BOX_INERTIA = 4,
    BOX_STABILIZED = 5, 
    KEYFRAMED = 6,
    FIXED = 7,
    THIN_BOX = 8,
    CHARACTER = 9

class SkyrimCollisionLayer(IntEnum):
    UNIDENTIFIED = 0
    STATIC = 1
    ANIMSTATIC = 2
    TRANSPARENT = 3
    CLUTTER = 4
    WEAPON = 5
    PROJECTILE = 6
    SPELL = 7
    BIPED = 8
    TREES = 9
    PROPS = 10
    WATER = 11
    TRIGGER = 12
    TERRAIN = 13
    TRAP = 14
    NONCOLLIDABLE = 15
    CLOUD_TRAP = 16
    GROUND = 17
    PORTAL = 18
    DEBRIS_SMALL = 19
    DEBRIS_LARGE = 20
    ACOUSTIC_SPACE = 21
    ACTORZONE = 22
    PROJECTILEZONE = 23
    GASTRAP = 24
    SHELLCASING = 25
    TRANSPARENT_SMALL = 26
    INVISIBLE_WALL = 27
    TRANSPARENT_SMALL_ANIM = 28
    WARD = 29
    CHARCONTROLLER = 30
    STAIRHELPER = 31
    DEADBIP = 32
    BIPED_NO_CC = 33
    AVOIDBOX = 34
    COLLISIONBOX = 35
    CAMERASHPERE = 36
    DOORDETECTION = 37
    CONEPROJECTILE = 38
    CAMERAPICK = 39
    ITEMPICK = 40
    LINEOFSIGHT = 41
    PATHPICK = 42
    CUSTOMPICK1 = 43
    CUSTOMPICK2 = 44
    SPELLEXPLOSION = 45
    DROPPINGPICK = 46
    NULL = 47

class hkQualityType(IntEnum):
    INVALID = 0
    FIXED = 1
    KEYFRAMED = 2
    DEBRIS = 3
    MOVING = 4
    CRITICAL = 5
    BULLET = 6
    USER = 7
    CHARACTER = 8
    KEYFRAMED_REPORT = 9

class hkDeactivatorType(IntEnum):
    INVALID = 0
    NEVER = 1
    SPATIAL = 2

class hkSolverDeactivation(IntEnum):
    INVALID = 0
    OFF = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    MAX = 5

class hkQualityType(IntEnum):
    INVALID = 0
    FIXED = 1
    KEYFRAMED = 2
    DEBRIS = 3
    MOVING = 4
    CRITICAL = 5
    BULLET = 6
    USER = 7
    CHARACTER = 8
    KEYFRAMED_REPORT = 9

class SkyrimHavokMaterial(IntEnum):
    BROKEN_STONE = 131151687
    LIGHT_WOOD = 365420259
    SNOW = 398949039
    GRAVEL = 428587608
    MATERIAL_CHAIN_METAL = 438912228
    BOTTLE = 493553910
    WOOD = 500811281
    SKIN = 591247106
    UNKNOWN_617099282 = 617099282
    BARREL = 732141076
    MATERIAL_CERAMIC_MEDIUM = 781661019
    MATERIAL_BASKET = 790784366
    ICE = 873356572
    STAIRS_STONE = 899511101
    WATER = 1024582599
    UNKNOWN_1028101969 = 1028101969
    MATERIAL_BLADE_1HAND = 1060167844
    MATERIAL_BOOK = 1264672850
    MATERIAL_CARPET = 1286705471
    SOLID_METAL = 1288358971
    MATERIAL_AXE_1HAND = 1305674443
    UNKNOWN_1440721808 = 1440721808
    STAIRS_WOOD = 1461712277
    MUD = 1486385281
    MATERIAL_BOULDER_SMALL = 1550912982
    STAIRS_SNOW = 1560365355
    HEAVY_STONE = 1570821952
    UNKNOWN_1574477864 = 1574477864
    UNKNOWN_1591009235 = 1591009235
    MATERIAL_BOWS_STAVES = 1607128641
    MATERIAL_WOOD_AS_STAIRS = 1803571212
    GRASS = 1848600814
    MATERIAL_BOULDER_LARGE = 1885326971
    MATERIAL_STONE_AS_STAIRS = 1886078335
    MATERIAL_BLADE_2HAND = 2022742644
    MATERIAL_BOTTLE_SMALL = 2025794648
    SAND = 2168343821
    HEAVY_METAL = 2229413539
    UNKNOWN_2290050264 = 2290050264
    DRAGON = 2518321175
    MATERIAL_BLADE_1HAND_SMALL = 2617944780
    MATERIAL_SKIN_SMALL = 2632367422
    STAIRS_BROKEN_STONE = 2892392795
    MATERIAL_SKIN_LARGE = 2965929619
    ORGANIC = 2974920155
    MATERIAL_BONE = 3049421844
    HEAVY_WOOD = 3070783559
    MATERIAL_CHAIN = 3074114406
    DIRT = 3106094762
    MATERIAL_ARMOR_LIGHT = 3424720541
    MATERIAL_SHIELD_LIGHT = 3448167928
    MATERIAL_COIN = 3589100606
    MATERIAL_SHIELD_HEAVY = 3702389584
    MATERIAL_ARMOR_HEAVY = 3708432437
    MATERIAL_ARROW = 3725505938
    GLASS = 3739830338
    STONE = 3741512247
    CLOTH = 3839073443
    MATERIAL_BLUNT_2HAND = 3969592277
    UNKNOWN_4239621792 = 4239621792
    MATERIAL_BOULDER_MEDIUM = 4283869410


class bhkRigidBodyProps(Structure):
    _fields_ = [
        ('collisionFilter_layer', c_uint8),
	    ('collisionFilter_flags', c_uint8),
	    ('collisionFilter_group', c_uint16),
	    ('broadPhaseType', c_uint8),
	    ('prop_data', c_uint32),    
	    ('prop_size', c_uint32),
	    ('prop_flags', c_uint32),
        ('collisionResponse', c_uint8),
        ('unusedByte1', c_uint8),
        ('processContactCallbackDelay', c_uint16),
        ('unkInt1', c_uint32),
        ('collisionFilterCopy_layer', c_uint8),
        ('collisionFilterCopy_flags', c_uint8),
        ('collisionFilterCopy_group', c_uint16),
        ('unkShorts2', VECTOR6_SHORT),
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
        ('gravityFactor', c_float),
        ('friction', c_float),
        ('rollingFrictionMult', c_float),
        ('restitution', c_float),
        ('maxLinearVelocity', c_float),
        ('maxAngularVelocity', c_float),
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
        ('bodyFlagsInt', c_uint32),
        ('bodyFlags', c_uint16),
        ('guard', c_uint64)]

    def __init__(self):
        self.guard = 0xF0F0F0F0

    def __str__(self):
        s = ""
        for attr in self._fields_:
            if len(s) > 0:
                s = s + "\n"
            s = s + f"\t{attr[0]} = {getattr(self, attr[0])}"
        return s

class bhkBoxShapeProps(Structure):
    _fields_ = [
        ("material", c_uint32),
        ("radius", c_float),
        ("dimensions", VECTOR3),
        ("unused", c_float)]

    def __str__(self):
        s = ""
        for attr in self._fields_:
            if len(s) > 0:
                s = s + "\n"
            s = s + f"\t{attr[0]} = {getattr(self, attr[0])}"
        return s

class VERTEX_WEIGHT_PAIR(Structure):
    _fields_ = [("vertex", c_uint16),
                ("weight", c_float)]


