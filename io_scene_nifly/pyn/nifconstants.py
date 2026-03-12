"""
Magic constants and data structures used in nif files.
"""
from .pynenum import PynIntFlag, PynIntEnum


NODEID_NONE = 4294967295
NO_SHADER_REF = 4294967294  # Signals DLL to not create a shader for the shape

# There are 64 Skyrim units in a yard and havok works in metres, so:
HAVOC_SCALE_FACTOR = HSF = 69.99125

game_collision_sf = {"FONV": 0.1, "FO3": 0.1, "FO4": 1.0, "FO4VR": 10, "FO76": 1.0,
                     "SKYRIM": 1.0, "SKYRIMSE": 1.0, "SKYRIMVR": 1.0}

class NiAVFlags(PynIntFlag):
    HIDDEN = 1
    SELECTIVE_UPDATE = 1 << 1
    SELECTIVE_UPDATE_TRANSF = 1 << 2
    SELECTIVE_UPDATE_CONTR = 1 << 3
    SELECTIVE_UPDATE_RIGID = 1 << 4
    DISPLAY_OBJECT = 1 << 5
    DISABLE_SORTING = 1 << 6
    SEL_UPD_TRANSF_OVERRIDE = 1 << 7
    UNKNOWN_8 = 1 << 8
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
    MESH_LOD_SKY = 1 << 27
    UNKNOWN_28 = 1 << 28

class BSXFlagsValues(PynIntFlag):
    ANIMATED = 1
    HAVOC = 1 << 1
    RAGDOLL = 1 << 2
    COMPLEX = 1 << 3
    ADDON = 1 << 4
    EDITOR_MARKER = 1 << 5
    DYNAMIC = 1 << 6
    ARTICULATED = 1 << 7
    NEEDS_XFORM_UPDATES = 1 << 8
    EXTERNAL_EMIT = 1 << 9
    MAGIC_SHADER_PARTICLES = 1 << 10
    LIGHTS = 1 << 11
    BREAKABLE = 1 << 12

class BSLSPShaderType(PynIntEnum):
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
    
class ShaderFlags1FO4(PynIntFlag):
	SPECULAR = 1 << 0
	SKINNED = 1 << 1
	TEMP_REFRACTION = 1 << 2
	VERTEX_ALPHA = 1 << 3
	GREYSCALETOPALETTE_COLOR = 1 << 4
	GREYSCALETOPALETTE_ALPHA = 1 << 5
	USE_FALLOFF = 1 << 6
	ENVIRONMENT_MAPPING = 1 << 7
	RGB_FALLOFF = 1 << 8
	CAST_SHADOWS = 1 << 9
	FACE = 1 << 10
	UI_MASK_RECTS = 1 << 11
	MODEL_SPACE_NORMALS = 1 << 12
	NON_PROJECTIVE_SHADOWS = 1 << 13
	LANDSCAPE = 1 << 14
	REFRACTION = 1 << 15
	FIRE_REFRACTION = 1 << 16
	EYE_ENVIRONMENT_MAPPING = 1 << 17
	HAIR = 1 << 18
	SCREENDOOR_ALPHA_FADE = 1 << 19
	LOCALMAP_HIDE_SECRET = 1 << 20
	SKIN_TINT = 1 << 21
	OWN_EMIT = 1 << 22
	PROJECTED_UV = 1 << 23
	MULTIPLE_TEXTURES = 1 << 24
	TESSELLATE = 1 << 25
	DECAL = 1 << 26
	DYNAMIC_DECAL = 1 << 27
	CHARACTER_LIGHTING = 1 << 28
	EXTERNAL_EMITTANCE = 1 << 29
	SOFT_EFFECT = 1 << 30
	ZBUFFER_TEST = 1 << 31

class ShaderFlags2FO4(PynIntFlag):
	ZBUFFER_WRITE = 1 << 0
	LOD_LANDSCAPE = 1 << 1
	LOD_OBJECTS = 1 << 2
	NO_FADE = 1 << 3
	DOUBLE_SIDED = 1 << 4
	VERTEX_COLORS = 1 << 5
	GLOW_MAP = 1 << 6
	TRANSFORM_CHANGED = 1 << 7
	DISMEMBERMENT_MEATCUFF = 1 << 8
	TINT = 1 << 9
	GRASS_VERTEX_LIGHTING = 1 << 10
	GRASS_UNIFORM_SCALE = 1 << 11
	GRASS_FIT_SLOPE = 1 << 12
	GRASS_BILLBOARD = 1 << 13
	NO_LOD_LAND_BLEND = 1 << 14
	DISMEMBERMENT = 1 << 15
	WIREFRAME = 1 << 16
	WEAPON_BLOOD = 1 << 17
	HIDE_ON_LOCAL_MAP = 1 << 18
	PREMULT_ALPHA = 1 << 19
	VATS_TARGET = 1 << 20
	ANISOTROPIC_LIGHTING = 1 << 21
	SKEW_SPECULAR_ALPHA = 1 << 22
	MENU_SCREEN = 1 << 23
	MULTI_LAYER_PARALLAX = 1 << 24
	ALPHA_TEST = 1 << 25
	GRADIENT_REMAP = 1 << 26
	VATS_TARGET_DRAW_ALL = 1 << 27
	PIPBOY_SCREEN = 1 << 28
	TREE_ANIM = 1 << 29
	EFFECT_LIGHTING = 1 << 30
	REFRACTION_WRITES_DEPTH = 1 << 31


class BSValueNodeFlags(PynIntFlag):
	BILLBOARDWORLD_Z = 1 << 0
	USE_PLAYER_ADJUST = 1 << 1


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

class hkResponseType(PynIntEnum):
    INVALID = 0
    SIMPLE_CONTACT = 1
    REPORTING = 2
    NONE = 3

class BroadPhaseType(PynIntEnum):
    INVALID = 0
    ENTITY =  1
    PHANTOM = 2
    BORDER = 3

class hkMotionType(PynIntEnum):
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

class SkyrimCollisionLayer(PynIntEnum):
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

class hkQualityType(PynIntEnum):
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

class hkDeactivatorType(PynIntEnum):
    INVALID = 0
    NEVER = 1
    SPATIAL = 2

class hkSolverDeactivation(PynIntEnum):
    INVALID = 0
    OFF = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    MAX = 5

class SkyrimHavokMaterial(PynIntEnum):
    # From nif.xml with a SKY_HAV_MAT_ prefix.
    NONE = 0 # Invalid Material
    BROKEN_STONE = 131151687 # Broken Stone
    MATERIAL_BLOCK_BLADE_1HAND = 165778930 # Material Block Blade 1Hand
    MATERIAL_MEAT = 220124585 # Material Meat
    MATERIAL_CARRIAGE_WHEEL = 322207473 # Material Carriage Wheel
    MATERIAL_METAL_LIGHT = 346811165 # Material Metal Light
    LIGHT_WOOD = 365420259 # Light Wood
    SNOW = 398949039 # Snow
    GRAVEL = 428587608 # Gravel
    MATERIAL_CHAIN_METAL = 438912228 # Material Chain Metal
    BOTTLE = 493553910 # Bottle
    WOOD = 500811281 # Wood
    MATERIAL_ASH = 534864873 # Material Ash
    SKIN = 591247106 # Skin
    MATERIAL_BLOCK_BLUNT = 593401068 # Material Block Blunt
    MATERIAL_CLOTH = 617099282 # Material Cloth
    INSECT = 668408902 # Insect
    BARREL = 732141076 # Barrel
    MATERIAL_CERAMIC_MEDIUM = 781661019 # Material Ceramic Medium
    MATERIAL_BASKET = 790784366 # Material Basket
    ICE = 873356572 # Ice
    STAIRS_GLASS = 880200008 # Stairs Glass
    STAIRS_STONE = 899511101 # Stairs Stone
    WATER = 1024582599 # Water
    MATERIAL_BONE_ACTOR = 1028101969 # Material Bone Actor
    MATERIAL_BLADE_1HAND = 1060167844 # Material Blade 1Hand
    MATERIAL_BOOK = 1264672850 # Material Book
    MATERIAL_CARPET = 1286705471 # Material Carpet
    SOLID_METAL = 1288358971 # Solid Metal
    MATERIAL_AXE_1HAND = 1305674443 # Material Axe 1Hand
    MATERIAL_BLOCK_BLADE_2HAND = 1312943906 # Material Block Blade 2Hand
    ORGANIC_LARGE = 1322093133 # Organic Large
    CHAIN_METAL = 1440721808 # Chain Metal
    STAIRS_WOOD = 1461712277 # Stairs Wood
    MUD = 1486385281 # Mud
    MATERIAL_BOULDER_SMALL = 1550912982 # Material Boulder Small
    STAIRS_SNOW = 1560365355 # Stairs Snow
    HEAVY_STONE = 1570821952 # Heavy Stone
    CHARACTER_BUMPER = 1574477864 # Character Bumper
    TRAP = 1591009235 # Unknown in Creation Kit v1.6.89.0. Found in trap objects or clutter\displaycases\displaycaselgangled01.nif or actors\deer\character assets\skeleton.nif.
    MATERIAL_BOWS_STAVES = 1607128641 # Material Bows Staves
    MATERIAL_SOLID_METAL = 1668849266 # Material Solid Metal
    ALDUIN = 1730220269 # Alduin
    MATERIAL_WOOD_MEDIUM = 1734341287 # Material Wood Medium
    MATERIAL_BLOCK_BOWS_STAVES = 1763418903 # Material Block Bows Staves
    MATERIAL_WOOD_AS_STAIRS = 1803571212 # Material Wood As Stairs
    MATERIAL_BLADE_2HAND_ = 1820198263 # Material Blade 2Hand 
    GRASS = 1848600814 # Grass
    MATERIAL_BOULDER_LARGE = 1885326971 # Material Boulder Large
    MATERIAL_STONE_AS_STAIRS = 1886078335 # Material Stone As Stairs
    MATERIAL_BLADE_2HAND = 2022742644 # Material Blade 2Hand
    MATERIAL_BOTTLE_SMALL = 2025794648 # Material Bottle Small
    BONE_ACTOR = 2058949504 # Bone Actor
    SAND = 2168343821 # Sand
    HEAVY_METAL = 2229413539 # Heavy Metal
    MATERIAL_WOOD_HEAVY = 2290050264 # Material Wood Heavy
    MATERIAL_ICE_FORM = 2431524493 # Material Ice Form
    DRAGON = 2518321175 # Dragon
    MATERIAL_BLADE_1HAND_SMALL = 2617944780 # Material Blade 1Hand Small
    MATERIAL_SKIN_SMALL = 2632367422 # Material Skin Small
    MATERIAL_POTS_PANS = 2742858142 # Material Pots Pans
    MATERIAL_STAIRS_WOOD = 2794252627 # Material Stairs Wood
    MATERIAL_SKIN_SKELETON = 2821299363 # Material Skin Skeleton
    MATERIAL_BLUNT_1HAND = 2872791301 # Material Blunt 1Hand
    STAIRS_BROKEN_STONE = 2892392795 # Stairs Broken Stone
    MATERIAL_SKIN_LARGE = 2965929619 # Material Skin Large
    ORGANIC = 2974920155 # Organic
    MATERIAL_BONE = 3049421844 # Material Bone
    HEAVY_WOOD = 3070783559 # Heavy Wood
    MATERIAL_CHAIN = 3074114406 # Material Chain
    DIRT = 3106094762 # Dirt
    GHOST = 3312543676 # Ghost
    MATERIAL_SKIN_METAL_LARGE = 3387452107 # Material Skin Metal Large
    MATERIAL_BLOCK_AXE = 3400476823 # Material Block Axe
    MATERIAL_ARMOR_LIGHT = 3424720541 # Material Armor Light
    MATERIAL_SHIELD_LIGHT = 3448167928 # Material Shield Light
    MATERIAL_COIN = 3589100606 # Material Coin
    MATERIAL_BLOCK_BLUNT_2HAND = 3662306947 # Material Block Blunt 2Hand
    MATERIAL_SHIELD_HEAVY = 3702389584 # Material Shield Heavy
    MATERIAL_ARMOR_HEAVY = 3708432437 # Material Armor Heavy
    MATERIAL_ARROW = 3725505938 # Material Arrow
    GLASS = 3739830338 # Glass
    STONE = 3741512247 # Stone
    MATERIAL_WATER_PUDDLE = 3764646153 # Material Water Puddle
    CLOTH = 3839073443 # Cloth
    MATERIAL_SKIN_METAL_SMALL = 3855001958 # Material Skin Metal Small
    WARD = 3895166727 # Ward
    WEB = 3934839107 # Web
    MATERIAL_BLADE_1HAND_ = 3941234649 # Material Blade 1Hand 
    MATERIAL_BLUNT_2HAND = 3969592277 # Material Blunt 2Hand
    STAIRS_METAL = 3974071006 # Stairs Metal
    DLC1_SWINGING_BRIDGE = 4239621792 # Unknown in Creation Kit v1.9.32.0. Found in Dawnguard DLC in meshes\dlc01\prototype\dlc1protoswingingbridge.nif.
    MATERIAL_BOULDER_MEDIUM = 4283869410 # Material Boulder Medium

    @classmethod
    def get_name(cls, val):
        """Turns the material enum into a string--if not found, just returns the input."""
        try:
            return SkyrimHavokMaterial(val).name
        except:
            return str(val)
        
class VertexFlags(PynIntFlag):
    VERTEX = 1 << 0
    UV = 1 << 1
    UV_2 = 1 << 2
    NORMAL = 1 << 3
    TANGENT = 1 << 4
    COLORS = 1 << 5
    SKINNED = 1 << 6
    LANDDATA = 1 << 7
    EYEDATA = 1 << 8
    INSTANCE = 1 << 9
    FULLPREC = 1 << 10

    @classmethod
    def get_name(cls, val):
        """Turns the material enum into a string--if not found, just returns the input."""
        try:
            return VertexFlags(val).name
        except:
            return str(val)


class EffectShaderControlledVariable(PynIntEnum):
	Emissive_Multiple = 0
	Falloff_Start_Angle = 1
	Falloff_Stop_Angle = 2
	Falloff_Start_Opacity = 3
	Falloff_Stop_Opacity = 4
	Alpha_Transparency = 5
	U_Offset = 6
	U_Scale = 7
	V_Offset = 8
	V_Scale = 9


class AnimType(PynIntEnum):
    APP_TIME = 0
    APP_INIT = 1


class CycleType(PynIntEnum):
    LOOP = 0
    REVERSE = 1
    CLAMP = 2


class ExtraDataType(PynIntEnum):
    BehaviorGraph = 1
    String = 2
    Cloth = 3
    InvMarker = 4
    BSXFlags = 5
