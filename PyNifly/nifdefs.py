
"""
    Value and type definitions for nif structures
"""

import sys
from enum import Enum, IntFlag, IntEnum
import math
import logging
from ctypes import * # c_void_p, c_int, c_bool, c_char_p, c_wchar_p, c_float, c_uint8, c_uint16, c_uint32, create_string_buffer, Structure, cdll, pointer, addressof
import pynmathutils as PM
import bgsmaterial


def is_in_plane(plane, vert):
    """ Test whether vert is in the plane defined by the three vectors in plane """
    #find the plane's normal. p0, p1, and p2 are simply points on the plane (in world space)
 
    # Get vector normal to plane
    v1 = PM.vecSub(plane[0], plane[1])
    v2 = PM.vecSub(plane[2], plane[1])
    normal = PM.vecCrossProduct(v1, v2)
    normal = PM.vecNormalized(normal)

    # Get vector from vertex to a point on the plane
    t = PM.vecNormalized(PM.vecSub(vert, plane[0]))

    # If the dot product is 0, point is on plane
    dp = PM.vecDotProduct(normal, t)

    return round(dp, 4) == 0.0


def multiply_transforms(transform1, transform2):
    """
    Combine transform 1 with trnasform 2. Rotations are a 3x3 matrix.
    """
    # Extract location, rotation, and scale components from the input transforms
    loc1, rot1, scale1 = transform1
    loc2, rot2, scale2 = transform2
    
    # Compute the new location by applying rotation and scale to the first location
    new_loc = [loc1[0] + (rot1[0][0] * scale1[0] * loc2[0]) + (rot1[0][1] * scale1[1] * loc2[1]) + (rot1[0][2] * scale1[2] * loc2[2]),
               loc1[1] + (rot1[1][0] * scale1[0] * loc2[0]) + (rot1[1][1] * scale1[1] * loc2[1]) + (rot1[1][2] * scale1[2] * loc2[2]),
               loc1[2] + (rot1[2][0] * scale1[0] * loc2[0]) + (rot1[2][1] * scale1[1] * loc2[1]) + (rot1[2][2] * scale1[2] * loc2[2])]
    
    # Compute the new rotation by multiplying rotation matrices
    new_rot = [[0.0, 0.0, 0.0],
               [0.0, 0.0, 0.0],
               [0.0, 0.0, 0.0]]
    
    for i in range(3):
        for j in range(3):
            new_rot[i][j] = (rot1[i][0] * rot2[0][j]) + (rot1[i][1] * rot2[1][j]) + (rot1[i][2] * rot2[2][j])
    
    # Compute the new scale by element-wise multiplication
    new_scale = [scale1[0] * scale2[0], scale1[1] * scale2[1], scale1[2] * scale2[2]]
    
    return new_loc, new_rot, new_scale


# We do not actually support all these versions
game_versions = ["FO3", "FONV", "SKYRIM", "FO4", "SKYRIMSE", "FO4VR", "SKYRIMVR", "FO76"]


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
        if len(value) == 0:
            return 0
        valuelist = value.split("|")
        flags = 0
        for v in valuelist:
            have_val = False
            try:
                flags |= cls[v.strip()]
                have_val = True
            except:
                pass
            if not have_val:
                flags |= int(v, 0)

        return flags

class PynIntEnum(IntEnum):
    @classmethod
    def GetName(cls, i):
        try:
            return cls(i).name
        except:
            return str(i)

    @classmethod
    def GetValue(cls, nm):
        try:
            return cls[nm].value
        except:
            return int(nm, 0)

NODEID_NONE = 4294967295

VECTOR2 = c_float * 2
VECTOR3 = c_float * 3
VECTOR4 = c_float * 4
VECTOR6_SHORT = c_uint16 * 6
VECTOR12 = c_float * 12
MATRIX3 = VECTOR3 * 3
MATRIX4 = VECTOR4 * 4
CHAR256 = c_char * 256

pynBufferDefaults = {
	'broadPhaseType': 'INVALID',
	'collisionFilter_flags': 0,
	'collisionFilter_group': 0,
	'prop_data': 0, 
	'prop_flags': 0,
	'prop_size': 0,
    'angularDamping': 0.05,
    'angularVelocity': "(0, 0, 0, 0)",
    'autoRemoveLevel': 0,
    'bodyFlags': 0,
    'bodyFlagsInt': 0,
    'bodyID' : NODEID_NONE,
    'center': "(0, 0, 0, 0)",
    'childCount': 0,
    'collisionFilter_layer': "STATIC",
    'collisionFilterCopy_flags': 0,
    'collisionFilterCopy_group': 0,
    'collisionFilterCopy_layer': 'STATIC',
    'collisionResponse': 'SIMPLE_CONTACT',
    'collisionResponse2': 'SIMPLE_CONTACT',
    'controllerID' : NODEID_NONE,
    'ctrlID' : NODEID_NONE,
    'ctrlType': NODEID_NONE,
    'deactivatorType': 'NEVER',
    'envMapMinLOD': 0,
    'forceCollideOntoPpu': 0,
    'friction': 0.5,
    'gravityFactor': 1.0,
    'inertiaMatrix': "[1, 0, 0, 0, 1, 0, 0, 0, 1]",
    'interpID' : NODEID_NONE,
    'interpolatorID' : NODEID_NONE,
    'lightingInfluence' : 255,
    'linearDamping': 0.1,
    'linearVelocity': "(0, 0, 0, 0)",
    'mass': 1.0,
    'maxAngularVelocity': 31.57, 
    'maxLinearVelocity': 104.4, 
    'motionSystem': 'DYNAMIC',
    'nameID' : NODEID_NONE,
    'nodeName': NODEID_NONE,
    'normalsCount': 0,
    'numShapeKeysInContactPointProps': 0, 
    'penetrationDepth': 0.15,
    'processContactCallbackDelay': 0xFFFF,
    'propType': NODEID_NONE,
    'qualityType': 'FIXED',
    'responseModifierFlag': 0,
    'restitution': 0.4, 
    'rollingFrictionMult': 1.0,
    'shapeID' : NODEID_NONE,
    'solverDeactivation': 'OFF', 
    'targetID': NODEID_NONE,
    'timeFactor': 1.0,
    'vertsCount': 0,
    }


class pynStructure(Structure):
    nifly = None
    logger = None

    def warn(self, msg):
        if pynStructure.logger: pynStructure.logger.warning(msg)
        self.warnings.append(msg)

    def load(self, shape, ignore=[], game='SKYRIM'):
        """
        Load fields from the dictionary-like object 'shape'. 
        Return list of warnings if any fields can't be set. 
        """
        self.warnings = []
        for f, t in self._fields_:
            v = None
            # try:
            if f in ignore:
                pass
            elif not (f in shape.keys()):
                pass
            elif f == 'Shader_Flags_1':
                if not shape[f]:
                    v = 0
                elif game in ['SKYRIM', 'SKYRIMSE']:
                    v = ShaderFlags1.parse(shape[f]).value
                else:
                    v = ShaderFlags1FO4.parse(shape[f]).value
            elif f == 'Shader_Flags_2':
                if not shape[f]:
                    v = 0
                elif game in ['SKYRIM', 'SKYRIMSE']:
                    v = ShaderFlags2.parse(shape[f]).value
                else:
                    v = ShaderFlags2FO4.parse(shape[f]).value
            elif f == 'Shader_Type':
                if not shape[f]:
                    v = 0
                elif type(shape[f]) == BSLSPShaderType:
                    v = shape[f].value
                elif type(shape[f]) == str:
                    mykey = str(shape[f])
                    myenum = BSLSPShaderType[mykey]
                    myval = myenum.value
                    v = myval
                else:
                    v = int(shape[f])
            elif f in ['collisionFilter_layer', 'collisionFilterCopy_layer']:
                try:
                    v = SkyrimCollisionLayer[shape[f]].value
                except:
                    v = int(shape[f])
            elif f == 'broadPhaseType':
                try:
                    v = BroadPhaseType[shape[f]].value
                except:
                    v = int(shape[f])
            elif f in ['collisionResponse', 'collisionResponse2']:
                try:
                    v = hkResponseType[shape[f]].value
                except:
                    v = int(shape[f])
            elif f == 'motionSystem':
                try:
                    v = hkMotionType[shape[f]].value
                except:
                    v = int(shape[f])
            elif f == 'deactivatorType':
                try:
                    v = hkDeactivatorType[shape[f]].value
                except:
                    v = int(shape[f])
            elif f == 'solverDeactivation': 
                try:
                    v = hkSolverDeactivation[shape[f]].value
                except:
                    v = int(shape[f])
            elif f == 'qualityType':
                try:
                    v = hkQualityType[shape[f]].value
                except:
                    v = int(shape[f])
            elif f == 'bhkMaterial':
                try:
                    v = SkyrimHavokMaterial[shape[f]].value
                except:
                    v = int(shape[f])
            elif t.__name__ == 'c_char_Array_256':
                v = shape[f].encode('utf-8')
            elif t.__name__ == 'c_float_Array_2':
                v = VECTOR2(*eval(shape[f]))
            elif t.__name__ == 'c_float_Array_3':
                v = VECTOR3(*eval(shape[f]))
            elif t.__name__ == 'c_float_Array_4':
                v = VECTOR4(*eval(shape[f]))
            elif t.__name__ == 'c_float_Array_12':
                v = VECTOR12(*eval(shape[f]))
            elif t.__name__ == 'c_ushort_Array_6':
                v = VECTOR6_SHORT(*eval(shape[f]))
            elif t.__name__ == 'c_float':
                v = float(shape[f])
            elif t.__name__ in ['c_ubyte', 'c_ulong', 'c_uint8', 'c_uint16', 'c_uint32', 'c_ulong', 'c_ulonglong']:
                v = int(shape[f])
            else:
                v = shape[f]
            if v is not None:
                try:
                    self.__setattr__(f, v)
            # except KeyError as e:
            #     try:
            #         self.__setattr__(f, int(shape[f]))
            #     except Exception as e:
            #         self.warn(f"Error setting property {f} <- {shape[f]}")
                except Exception as e:
                    raise Exception(f"Error setting property {f} <- {shape[f]}")

    def __init__(self, values=None, game='SKYRIM'):
        """Initialize structure from 'values'."""
        super().__init__()
        if "bufSize" in [n for n, t in self._fields_]:
            self.__setattr__("bufSize", sizeof(self))
                
        self.warnings = []

        self.load(pynBufferDefaults, game=game)
        if values:
            self.load(values, game=game)

    def __str__(self):
        s = ""
        for attr in self._fields_:
            if len(s) > 0:
                s = s + "\n"
            v = getattr(self, attr[0])
            if type(v) in [VECTOR3, VECTOR4, VECTOR12]:
                vals = []
                for n in v:
                    vals.append( f"{n:.4f}" )
                s += f"\t{attr[0]} = [{', '.join(vals)}]"
                
            elif type(v) == MATRIX3:
                rows = []
                for r in v:
                    cols = []
                    for c in r:
                        cols.append(f"{c:.4f}")
                    rows.append(f"\t[{', '.join(cols)}]")
                s += f"\t{attr[0]} = \n" + '\n'.join(rows)
            elif type(v) == float:
                s += f"\t{attr[0]} = {v:.4f}"
            else:
                s += f"\t{attr[0]} = {v}"
        return s

    def __eq__(self, other):
        """
        Compare two structures to see if their values are equal. ID fields are not
        compared because they are not expected to be equal across nifs.
        """
        if not self or not other:
            return False
        for fn, t in self._fields_:
            if fn[-2:] != 'ID':
                if '_Array_' in t.__name__:
                    for x, y in zip(self.__getattribute__(fn), other.__getattribute__(fn)):
                        if type(x) == float and type(y) == float:
                            if not math.isclose(x, y, abs_tol=10**-5):
                                return False
                        elif x != y:
                            return False
                else:
                    x = self.__getattribute__(fn)
                    y = other.__getattribute__(fn)
                    if type(x) == float and type(y) == float:
                        if not math.isclose(x, y, abs_tol=10**-5):
                            return False
                    elif x != y:
                        return False
        return True
    
    def compare(self, other):
        """
        Compare two structures, returning any differences in a list.
        """
        diffs = []
        for fn, t in self._fields_:
            if fn[-2:] != 'ID':
                if '_Array_' in t.__name__:
                    for x, y in zip(self.__getattribute__(fn), other.__getattribute__(fn)):
                        if x != y:
                            return diffs.append((fn, x, y,))
                else:
                    if self.__getattribute__(fn) != other.__getattribute__(fn):
                        diffs.append((fn, self.__getattribute__(fn), other.__getattribute__(fn)))
        return diffs
    
    def extract_field(self, shape, fieldname, fieldtype, game='SKYRIM'):
        """
        Extract a single field from the beffer and set as a key/value pair on the
        dictionary-like "shape". Subclasses can override this for special handling
        on fields that are interpreted for the user.
        """
        if fieldtype.__name__ == 'c_char_Array_256':
            v = self.__getattribute__(fieldname).decode()
        elif '_Array_' in fieldtype.__name__:
            v = [x for x in self.__getattribute__(fieldname)]
        else:
            v = self.__getattribute__(fieldname)
        if type(v) == list:
            shape[fieldname] = repr(v)
        else:
            try:
                shape[fieldname] = v
            except Exception as e:
                # If the value can't be stored natively, store it as a string.
                # This happens when the top bit of a uint32 is set.
                shape[fieldname] = repr(v)

    def extract(self, shape, ignore=[], game='SKYRIM'):
        """
        Extract fields to the dictionary-like object 'shape'. Do not extract any ID
        fields. Do not extract fields that match their default values.
        """
        defaults = self.__class__()
        for fn, t in self._fields_:
            if fn != 'bufType' and fn != 'bufSize' and fn[-2:] != 'ID' \
                and (fn not in ignore) \
                and not (fn == 'Shader_Type' and self.bufType == PynBufferTypes.BSEffectShaderPropertyBufType):

                if '_Array_' in t.__name__:
                    v1 = [x for x in self.__getattribute__(fn)]
                    v2 = [x for x in defaults.__getattribute__(fn)]
                else:
                    v1 = self.__getattribute__(fn) 
                    v2 = defaults.__getattribute__(fn)
                
                if (type(v2) == float and not math.isclose(v1, v2, abs_tol=10**-5)) \
                        or (v1 != v2):
                    try:
                        self.extract_field(shape, fn, t, game=game)
                    except:
                        shape[fn] = repr(t)

    def copy(self, exclude=[]):
        """ Return a copy of the object """
        n = self.__class__()
        for f, t in self._fields_:
            if not f in exclude:
                n.__setattr__(f, self.__getattribute__(f))
        return n

    def copyto(self, other, exclude=[]):
        """ Copy the object's fields to another object """
        for f, t in self._fields_:
            if not f in exclude:
                other.__setattr__(f, self.__getattribute__(f))
        return other
    

# ------ Little bit of matrix math for debugging ----
#   Real code uses Blender's functions

def quaternion_to_matrix(q):
    """
    Convert a quaternion to a 3x3 rotation matrix.
    
    :param q: A quaternion in the format (w, x, y, z)
    :return: The corresponding 3x3 rotation matrix
    """
    w, x, y, z = q
    q_norm = (w**2 + x**2 + y**2 + z**2)**0.5
    if q_norm == 0:
        raise ValueError("Quaternion cannot have zero norm.")
    
    q = (w/q_norm, x/q_norm, y/q_norm, z/q_norm)
    
    q0, q1, q2, q3 = q
    matrix = [
        [1 - 2*q2**2 - 2*q3**2, 2*q1*q2 - 2*q0*q3, 2*q1*q3 + 2*q0*q2],
        [2*q1*q2 + 2*q0*q3, 1 - 2*q1**2 - 2*q3**2, 2*q2*q3 - 2*q0*q1],
        [2*q1*q3 - 2*q0*q2, 2*q2*q3 + 2*q0*q1, 1 - 2*q1**2 - 2*q2**2]
    ]
    
    return matrix

class pynMatrix:
    def __init__(self, v):
        if type(v) == list:
            self._array = v
        elif type(v) == VECTOR3:
            self._array = [[1, 0, 0, v[0]], [0, 1, 0, v[1]], [0, 0, 1, v[2]], [0, 0, 0, 1]]
        elif type(v) == VECTOR4:
            self._array = [[1, 0, 0, v[0]], [0, 1, 0, v[1]], [0, 0, 1, v[2]], [0, 0, 0, v[3]]]

    def __mul__(self, other):
        return pynMatrix([[sum(a*b for a, b in zip(X_row, Y_col)) for Y_col in zip(*other._array)] for X_row in self._array])

    def __str__(self):
        return str(self._array)

    def __eq__(self, other):
        return self._array == other._array

    def to_vector4(self):
        """ Return the translation part of the matrix """
        return VECTOR4(self._array[0][3], self._array[1][3], self._array[2][3], self._array[3][3])

    def to_vector3(self):
        return VECTOR3(self._array[0][3], self._array[1][3], self._array[2][3])

class TransformBuf(pynStructure):
    _fields_ = [
        ('translation', VECTOR3),
        ('rotation', MATRIX3),
        ('scale', c_float) ]
    
    def __init__(self):
        self.set_identity()


    def set_identity(self):
        self.translation = VECTOR3(0, 0, 0)
        self.rotation = MATRIX3((1,0,0), (0,1,0), (0,0,1))
        self.scale = 1
        return self

    def store(self, transl, rot, scale):
        """ Fill buffer from translation, rotation, scale """
        self.translation[0] = transl[0]
        self.translation[1] = transl[1]
        self.translation[2] = transl[2]
        self.rotation = MATRIX3(VECTOR3(*rot[0]), VECTOR3(*rot[1]), VECTOR3(*rot[2]))
        self.scale = max(scale)

    def read(self):
        """ Return translation buffer as translation, rotation, scale """
        return (self.translation, self.rotation, [self.scale]*3)

    def to_matrix(self):
        v0 = list(self.rotation[0])
        v0.append(self.translation[0])
        v1 = list(self.rotation[1])
        v1.append(self.translation[1])
        v2 = list(self.rotation[2])
        v2.append(self.translation[2])
        return pynMatrix([v0, v1, v2, [0,0,0,1]])

    def NearEqual(self, other, epsilon=0.0001):
        for n, m in zip(self.translation[:], other.translation[:]):
            if abs(n-m) > epsilon:
                return False
        for v1, v2 in zip(self.rotation, other.rotation):
            for n, m in zip(v1, v2):
                if abs(n-m) > epsilon:
                    return False
        if abs(self.scale-other.scale) > epsilon:
            return False
        return True

    @classmethod
    def from_matrix(cls, m):
        buf = TransformBuf()
        buf.translation = VECTOR3(m._array[0][3], m._array[1][3], m._array[2][3])
        buf.rotation = MATRIX3(VECTOR3(*m._array[0][0:3]), VECTOR3(*m._array[1][0:3]), VECTOR3(*m._array[2][0:3]))
        buf.scale = 1
        return buf

    def __mul__(self, other):
        """ Compose this transform with the other """
        if type(other) == TransformBuf:
            return TransformBuf.from_matrix(self.to_matrix() * other.to_matrix())
        elif type(other) == VECTOR4:
            return (self.to_matrix() * pynMatrix(other)).to_vector4()
        elif type(other) == VECTOR3:
            return (self.to_matrix() * pynMatrix(other)).to_vector3()
        


# Types of root nodes
RT_NINODE = 0
RT_BSFADENODE = 1

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

class BSXFlags(PynIntFlag):
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
    BARREL = 732141076
    BOTTLE = 493553910
    BROKEN_STONE = 131151687
    CLOTH = 3839073443
    DIRT = 3106094762
    DRAGON = 2518321175
    GLASS = 3739830338
    GRASS = 1848600814
    GRAVEL = 428587608
    HEAVY_METAL = 2229413539
    HEAVY_STONE = 1570821952
    HEAVY_WOOD = 3070783559
    ICE = 873356572
    LIGHT_WOOD = 365420259
    MATERIAL_ARMOR_HEAVY = 3708432437
    MATERIAL_ARMOR_LIGHT = 3424720541
    MATERIAL_ARROW = 3725505938
    MATERIAL_AXE_1HAND = 1305674443
    MATERIAL_BASKET = 790784366
    MATERIAL_BLADE_1HAND = 1060167844
    MATERIAL_BLADE_1HAND_SMALL = 2617944780
    MATERIAL_BLADE_2HAND = 2022742644
    MATERIAL_BLUNT_2HAND = 3969592277
    MATERIAL_BONE = 3049421844
    MATERIAL_BOOK = 1264672850
    MATERIAL_BOTTLE_SMALL = 2025794648
    MATERIAL_BOULDER_LARGE = 1885326971
    MATERIAL_BOULDER_MEDIUM = 4283869410
    MATERIAL_BOULDER_SMALL = 1550912982
    MATERIAL_BOWS_STAVES = 1607128641
    MATERIAL_CARPET = 1286705471
    MATERIAL_CERAMIC_MEDIUM = 781661019
    MATERIAL_CHAIN = 3074114406
    MATERIAL_CHAIN_METAL = 438912228
    MATERIAL_COIN = 3589100606
    MATERIAL_SHIELD_HEAVY = 3702389584
    MATERIAL_SHIELD_LIGHT = 3448167928
    MATERIAL_SKIN_LARGE = 2965929619
    MATERIAL_SKIN_SMALL = 2632367422
    MATERIAL_STONE_AS_STAIRS = 1886078335
    MATERIAL_WOOD_AS_STAIRS = 1803571212
    MUD = 1486385281
    ORGANIC = 2974920155
    SAND = 2168343821
    SKIN = 591247106
    SNOW = 398949039
    SOLID_METAL = 1288358971
    STAIRS_BROKEN_STONE = 2892392795
    STAIRS_SNOW = 1560365355
    STAIRS_STONE = 899511101
    STAIRS_WOOD = 1461712277
    STONE = 3741512247
    UNKNOWN_1028101969 = 1028101969
    UNKNOWN_1440721808 = 1440721808
    UNKNOWN_1574477864 = 1574477864
    UNKNOWN_1591009235 = 1591009235
    UNKNOWN_2290050264 = 2290050264
    UNKNOWN_4239621792 = 4239621792
    UNKNOWN_617099282 = 617099282
    WATER = 1024582599
    WOOD = 500811281

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


class EffectShaderControlledVariable(IntEnum):
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
    COUNT = 56

# bufferTypeList = [''] * PynBufferTypes.COUNT
# blockBuffers = {}

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
        super().__init__()
        self.bufType = PynBufferTypes.NiShaderBufType
        if pynStructure.nifly:
            pynStructure.nifly.getBlock(None, NODEID_NONE, byref(self))
        if values:
            self.load(values, game=game)

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

class bhkRigidBodyProps(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
        ('shapeID', c_uint32),
        ('collisionFilter_layer', c_uint8),
	    ('collisionFilter_flags', c_uint8),
	    ('collisionFilter_group', c_uint16),
	    ('broadPhaseType', c_uint8),
	    ('prop_data', c_uint32),    
	    ('prop_size', c_uint32),
	    ('prop_flags', c_uint32),
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
	    ('prop_data', c_uint32),    
	    ('prop_size', c_uint32),
	    ('prop_flags', c_uint32),
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
    def __init__(self, values=None):
        super().__init__(values=values)
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
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.bhkListShapeBufType

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


class FurnitureMarkerBuf(pynStructure):
    _fields_ = [
        ("offset", VECTOR3),
        ("heading", c_float),
        ("animation_type", c_uint16),
        ("entry_points", c_uint16) ]


class ConnectPointBuf(pynStructure):
    _fields_ = [
        ("parent", c_char * 256),
        ("name", c_char * 256),
        ("rotation", VECTOR4),
        ("translation", VECTOR3),
        ("scale", c_float)]
    

class NiNodeBuf(pynStructure):
    _fields_ = [
        ('bufSize', c_uint16),
        ('bufType', c_uint16),
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
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSMeshLODTriShapeBufType


class BSLODTriShapeBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
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
        super().__init__(values=values)
        self.bufType = PynBufferTypes.BSLODTriShapeBufType
        

class AnimType(PynIntEnum):
    APP_TIME = 0
    APP_INIT = 1

class CycleType(PynIntEnum):
    LOOP = 0
    REVERSE = 1
    CLAMP = 2

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
    def __init__(self, values=None):
        self.nextControllerID = NODEID_NONE
        self.targetID = NODEID_NONE
        self.interpolatorID = NODEID_NONE
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiSingleInterpControllerBufType

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
        ("floatValue", c_float),
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


class NiPoint3InterpolatorBuf(pynStructure):
    _fields_ = [
        ("bufSize", c_uint16),
        ('bufType', c_uint16),
        ("value", VECTOR3), 
        ("dataID", c_uint32),
    ]
    def __init__(self, values=None):
        super().__init__(values=values)
        self.bufType = PynBufferTypes.NiPoint3InterpolatorBufType


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

#class MAT_TRANSFORM(Structure):
#    _fields_ = [("translation", VECTOR3),
#                ("rotation", MATRIX3),
#                ("scale", c_float)]

# There are 64 Skyrim units in a yard and havok works in metres, so:
HAVOC_SCALE_FACTOR = HSF = 69.99125

# FONV collisions seem to be 10X what we'd expect. Dunno why.
["FO3", "FONV", "SKYRIM", "FO4", "SKYRIMSE", "FO4VR", "SKYRIMVR", "FO76"]
game_collision_sf = {"FONV": 0.1, "FO3": 0.1, "FO4": 1.0, "FO4VR": 10, "FO76": 1.0,
                     "SKYRIM": 1.0, "SKYRIMSE": 1.0, "SKYRIMVR": 1.0}

class ModuleTest:
    """Quick and dirty test harness."""

    @property
    def all_tests(self):
        return [k for k in ModuleTest.__dict__.keys() if k.startswith('TEST_')]

        
    def execute_test(self, t):
        print(f"\n------------- {t} -------------")
        the_test = ModuleTest.__dict__[t]
        print(the_test.__doc__)
        the_test()
        print(f"------------- done")

    
    def execute(self, start=None, test=None):
        print("""\n
=====================================================================
======================= Running nifdefs tests =======================
=====================================================================

""")
        if test:
            self.execute_test(test)
        else:
            doit = (start is None) 
            for name in self.all_tests:
                if name == start: doit = True
                if doit:
                    self.execute_test(name)

        print("""

============================================================================
======================= TESTS COMPLETED SUCCESSFULLY =======================
============================================================================
""")


    def TEST_ENUM():
        class ImportSettings(PynIntFlag):
            create_bones = 1
            rename_bones = 1<<1
            import_anims = 1<<2
            rename_bones_nift = 1<<3

        flags = ImportSettings.create_bones | ImportSettings.rename_bones
        print(f"flags = {flags}")
        print(f"Fullname = {flags.fullname}")


    def TEST_FIELDS():
        print("--- Verifying what we can do with fields ---")
        class TestFields:
            _fields_ = [
                ('field1', c_uint16),
                ('field2', VECTOR3),
                ('field3', CHAR256),
            ]


    def TEST_MATRICES():
        print("--- Testing matrix and transform math")
        m1 = pynMatrix([[12,7,3],
                    [4 ,5,6],
                    [7 ,8,9]])
        m2 = pynMatrix([[5,8,1,2],
                    [6,7,3,0],
                    [4,5,9,1]])
        assert m1 * m2 == pynMatrix([[114, 160, 60, 27], 
                                [74, 97, 73, 14], 
                                [119, 157, 112, 23]]), f"Can multiply arrays"

        xb1 = TransformBuf()
        xb1.translation = VECTOR3(1, 2, 3)
        xb1.rotation = MATRIX3((1,0,0),(0,1,0),(0,0,1))
        xb1.scale = 1
        assert xb1.to_matrix() == pynMatrix([[1,0,0,1], [0,1,0,2], [0,0,1,3], [0,0,0,1]]), f"Can convert to matrix"

        xb2 = TransformBuf()
        xb2.translation = VECTOR3(4, 5, 6)
        xb2.rotation = MATRIX3((1,0,0),(0,1,0),(0,0,1))
        xb2.scale = 1

        xbm = xb1 * xb2
        assert list(xbm.translation) == [5, 7, 9], f"TransformBuf operations are correct"

        xv = xb1 * VECTOR3(8, 9, 10)
        assert list(xv) == [9, 11, 13], f"Multiplying transform buf by vector produces a transformed vector {list(xv)}"


    def TEST_STRUCTURES():
        print("--- Testing structures")
        p = bhkRigidBodyProps({"maxLinearVelocity": 555})
        assert round(p.maxLinearVelocity, 4) == 555, f"Expected 555, found {p.maxLinearVelocity}"

        p = bhkRigidBodyProps()
        assert round(p.maxLinearVelocity, 4) == 104.4, f"Expected default value 104.4, found {p.maxLinearVelocity}"
        assert p.collisionFilter_layer == SkyrimCollisionLayer.STATIC.value

        s = {"prop_size": 10,
            "collisionFilter_layer": "WEAPON"}

        p.load(s)

        assert p.prop_size == 10
        assert p.collisionFilter_layer == 5

        print("--- Testing that properties report warnings when missing or incomprehensible")
        p1 = bhkConvexVerticesShapeProps({"bhkMaterial": "BROKEN_STONE"})
        assert len(p1.warnings) == 0, f"No warnings reported"

        p2 = bhkConvexVerticesShapeProps({"bhkMaterial": "26"})
        assert len(p2.warnings) == 0, f"Warnings are reported"
        assert p2.bhkMaterial == 26, f"Material value is correct: {p2.bhkMaterial}"

        try:
            p3 = bhkConvexVerticesShapeProps({"bhkRadius": "FOO"})
            assert False, "Should have thrown an error"
        except:
            pass

        print("---Testing that getting a material name always works")
        assert SkyrimHavokMaterial.get_name(3049421844) == "MATERIAL_BONE", f"Material correct: {SkyrimHavokMaterial.get_name(3049421844)}"
        assert SkyrimHavokMaterial.get_name(53) == "53", f"Material correct: {SkyrimHavokMaterial.get_name(53)}"


if __name__ == "__main__":
    pynStructure.logger = logging.getLogger("pynifly")
    logging.basicConfig()
    pynStructure.logger.setLevel(logging.DEBUG)
    ModuleTest().execute()

