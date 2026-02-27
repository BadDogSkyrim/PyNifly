"""
Convenience structures and enums for communicating with the nifly DLL.
"""
import logging
import math
from ctypes import (
    Structure, c_uint8, sizeof, 
    c_ubyte, c_char, c_uint, c_uint16, c_uint32, c_uint64, c_ulong, c_ulonglong, c_float)
from .nifconstants import (
    SkyrimCollisionLayer, BroadPhaseType, hkResponseType, hkMotionType, hkDeactivatorType, 
    hkSolverDeactivation, hkQualityType, ShaderFlags1, ShaderFlags2, ShaderFlags1FO4, 
    ShaderFlags2FO4, BSLSPShaderType, SkyrimHavokMaterial, NiAVFlags, NODEID_NONE)
from .pynmathutils import (VECTOR2, VECTOR3, VECTOR4, VECTOR6_SHORT, VECTOR12, MATRIX4, 
                           MATRIX3, pynMatrix)


log = logging.getLogger('pynifly')

# FONV collisions seem to be 10X what we'd expect. Dunno why.
fo4_games = ["FO3", "FONV", "FO4", "FO4VR", "FO76"]
skyrim_games = ["SKYRIM", "SKYRIMSE", "SKYRIMVR"]

# Fields that never need to be saved from import to export.
_noextract_fields = set((
    'bodyID', 'controllerID', 'ctrlID', 'ctrlType', 'interpID', 'interpolatorID', 'nameID',
    'nodeName', 'propType', 'shapeID', 'targetID', 'collisionID', 'skinInstanceID', 
    'shaderPropertyID', 'alphaPropertyID', 'nextControllerID', 'targetID', 'textKeyID', 
    'managerID', 'accumRootNameID', 'animNotesID', 'dataID', 'sceneID', 'behaviorGraphFileID',
    'stringDataID', 'valueID', 'bBSLightingShaderProperty', 'textureSetID', 'rootMaterialNameID',
    'bufSize', 'bufType',
))

pynBufferDefaults = {
	'broadPhaseType': 'ENTITY',
	'collisionFilter_flags': 0,
	'collisionFilter_group': 0,
	'prop_data': 0, 
	'prop_flags': 0,
	'prop_size': 0,
    'Alpha': 1.0,
    'angularDamping': 0.05,
    'angularVelocity': "(0, 0, 0, 0)",
    'autoRemoveLevel': 0,
    'backlightPower': 0.0,
    'baseColor': "(0, 0, 0, 0)",
    'baseColorScale': 0.0,
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
    'doTranslucency': 0,
    'Emissive_Color': "(0, 0, 0, 0)",
    'Emissive_Mult': 1.0,
    'emissiveColor': "(0, 0, 0, 0)",
    'emitGradientTexture': "",
    'emittanceColor': "(0, 0, 0)",
    'Env_Map_Scale': 1.0,
    'envMapMinLOD': 0,
    'EnvMapMinLOD': 0,
    'envMapScale': 0.0,
    'envMapTexture': "",
    'envMaskTexture': "",
    'exposureOffset': 13.5,
    'eyeCubemapScale': 1.0,
    'eyeLeftReflectionCenter': "(0, 0, 0)",
    'eyeRightReflectionCenter': "(0, 0, 0)",
    'falloffStartAngle': 0.0,
    'falloffStartOpacity': 0.0,
    'falloffStopAngle': 0.0,
    'falloffStopOpacity': 0.0,
    'finalExposureMax': 3.0,
    'finalExposureMin': 2.0,
    'forceCollideOntoPpu': 0,
    'fresnelPower': 5.0,
    'friction': 0.5,
    'Glossiness': 1.0,
    'gravityFactor': 1.0,
    'grayscaleToPaletteScale': 1.0,
    'greyscaleTexture': "",
    'hairTintColor': "(1.0, 1.0, 1.0)",
    'hasTextureArrays': 0,
    'inertiaMatrix': "[1, 0, 0, 0, 1, 0, 0, 0, 1]",
    'interpID' : NODEID_NONE,
    'interpolatorID' : NODEID_NONE,
    'lightingInfluence' : 255,
    'LightingInfluence': 0,
    'linearDamping': 0.1,
    'linearVelocity': "(0, 0, 0, 0)",
    'lumEmittance': 100.0,
    'mass': 1.0,
    'maxAngularVelocity': 31.57, 
    'maxLinearVelocity': 104.4, 
    'maxPasses': 1,
    'mixAlbedo': 0,
    'motionSystem': 'DYNAMIC',
    'nameID' : NODEID_NONE,
    'nodeName': NODEID_NONE,
    'normalsCount': 0,
    'normalTexture': "",
    'numShapeKeysInContactPointProps': 0, 
    'numTextureArrays': 0,
    'parallaxEnvmapStrength': 1.0,
    'parallaxInnerLayerTextureScale': "(1.0, 1.0)",
    'parallaxInnerLayerThickness': 0.0,
    'parallaxMaxPasses': 0.0,
    'parallaxRefractionScale': 1.0,
    'parallaxScale': 0.0,
    'penetrationDepth': 0.15,
    'processContactCallbackDelay': 0xFFFF,
    'propType': NODEID_NONE,
    'qualityType': 'FIXED',
    'Refraction_Str': 0.0,
    'refractionFirePeriod': 0,
    'refractionPower': 0.0,
    'refractionStrength': 0.0,
    'responseModifierFlag': 0,
    'restitution': 0.4, 
    'Rim_Light_Power': 2.0,
    'rimlightPower2': 0.0,
    'rollingFrictionMult': 1.0,
    'scale': 1.0,
    'shapeID' : NODEID_NONE,
    'Skin_Tint_Alpha': 0.0,
    'skinTintColor': "(1.0, 1.0, 1.0)",
    'Soft_Lighting': 0.3,
    'softFalloffDepth': 0.0,
    'solverDeactivation': 'OFF', 
    'sourceTexture': "",
    'sparkleParameters': "(0, 0, 0, 0)",
    'Spec_Color': "(1.0, 1.0, 1.0)",
    'Spec_Str': 1.0,
    'subsurfaceColor': "(0, 0, 0)",
    'subsurfaceRolloff': 0.3,
    'targetID': NODEID_NONE,
    'textureClampMode': 3,
    'thickObject': 0,
    'timeFactor': 1.0,
    'transmissiveScale': 1.0,
    'turbulence': 0.0,
    'useSSR': 0,
    'UV_Scale_U': 1.0,
    'UV_Scale_V': 1.0,
    'vertsCount': 0,
    'wetnessEnvmapScale': 0.0,
    'wetnessEnvMapScale': 1.0,
    'wetnessFresnelPower': 1.6,
    'wetnessMetalness': 0.0,
    'wetnessMinVar': 0.2,
    'wetnessSpecPower': 1.4,
    'wetnessSpecScale': 0.6,
    'wetnessUnknown1': 0.0,
    'wetnessUnknown2': 0.0,
    'wetnessUseSSR': 0,

    }

_enum_types = {
    'broadPhaseType': BroadPhaseType,
    'collisionFilter_layer': SkyrimCollisionLayer,
    'collisionFilterCopy_layer': SkyrimCollisionLayer,
    'collisionResponse': hkResponseType,
    'collisionResponse2': hkResponseType,
    'deactivatorType': hkDeactivatorType,
    'motionSystem': hkMotionType,
    'solverDeactivation': hkSolverDeactivation,
    'qualityType': hkQualityType,
    'Shader_Flags_1': ShaderFlags1,
    'Shader_Flags_2': ShaderFlags2,
    'Shader_Type': BSLSPShaderType,
    'bhkMaterial': SkyrimHavokMaterial,
    'flags': NiAVFlags,
}

_numeric_types = set((c_float, c_ubyte, c_uint, c_uint16, c_uint32, c_ulong, c_ulonglong))
_array_types = set((
    'c_char_Array_256', 'c_float_Array_2', 'c_float_Array_3', 'c_float_Array_4', 
    'c_float_Array_12', 'c_ubyte_Array_12',
    ) )

_type_from_store = {
    'c_float': lambda shape, f: float(shape[f]),
    'c_ubyte': lambda shape, f: int(shape[f]),
    'c_uint8': lambda shape, f: int(shape[f]),
    'c_uint16': lambda shape, f: int(shape[f]),
    'c_uint32': lambda shape, f: int(shape[f]),
    'c_ulong': lambda shape, f: int(shape[f]),
    'c_ulonglong': lambda shape, f: int(shape[f]),
    'c_char_Array_256': lambda shape, f: shape[f].encode('utf-8'),
    'c_float_Array_2': lambda shape, f: VECTOR2(*eval(shape[f])),
    'c_float_Array_3': lambda shape, f: VECTOR3(*eval(shape[f])[0:3]),
    'c_float_Array_4': lambda shape, f: VECTOR4(*eval(shape[f])),
    'c_float_Array_12': lambda shape, f: VECTOR12(*eval(shape[f])),
    'c_ushort_Array_6': lambda shape, f: VECTOR6_SHORT(*eval(shape[f])),
    'c_float_Array_4_Array_4': lambda shape, f: 
        MATRIX4(*[VECTOR4(*eval(shape[f])[i]) for i in range(4)]),
}

_field_override_fo4 = {
    'Shader_Flags_1': ShaderFlags1FO4,
    'Shader_Flags_2': ShaderFlags2FO4,
}
    
# _value_getters = {
#     'broadPhaseType': lambda x: BroadPhaseType(x).name,
#     'collisionFilter_layer': lambda x: SkyrimCollisionLayer(x).name,
#     'collisionFilterCopy_layer': lambda x: SkyrimCollisionLayer(x).name,
#     'collisionResponse': lambda x: hkResponseType(x).name,
#     'collisionResponse2': lambda x: hkResponseType(x).name,
#     'deactivatorType': lambda x: hkDeactivatorType(x).name,
#     'motionSystem': lambda x: hkMotionType(x).name,
#     'solverDeactivation': lambda x: hkSolverDeactivation(x).name,
#     'qualityType': lambda x: hkQualityType(x).name,
#     'Shader_Flags_1': lambda x: ShaderFlags1(x).name if x in ShaderFlags1._value2member_map_ else ShaderFlags1FO4(x).name if x in ShaderFlags1FO4._value2member_map_ else str(x),
#     'Shader_Flags_2': lambda x: ShaderFlags2(x).name if x in ShaderFlags2._value2member_map_ else ShaderFlags2FO4(x).name if x in ShaderFlags2FO4._value2member_map_ else str(x),
#     'Shader_Type': lambda x: BSLSPShaderType(x).name if x in BSLSPShaderType._value2member_map_ else str(x),
#     'bhkMaterial': lambda x: SkyrimHavokMaterial(x).name if x in SkyrimHavokMaterial._value2member_map_ else str(x),
# }

# _value_from_store = {
#     'broadPhaseType': lambda x: BroadPhaseType(x).name,
#     'collisionFilter_layer': lambda x: SkyrimCollisionLayer(x).name,
#     'collisionFilterCopy_layer': lambda x: SkyrimCollisionLayer(x).name,
#     'collisionResponse': lambda x: hkResponseType(x).name,
#     'collisionResponse2': lambda x: hkResponseType(x).name,
#     'deactivatorType': lambda x: hkDeactivatorType(x).name,
#     'motionSystem': lambda x: hkMotionType(x).name,
#     'solverDeactivation': lambda x: hkSolverDeactivation(x).name,
#     'qualityType': lambda x: hkQualityType(x).name,
#     'Shader_Flags_1': lambda x, g: 
#         ShaderFlags1(x).name if x in ShaderFlags1._value2member_map_ 
#             else ShaderFlags1FO4(x).name if x in ShaderFlags1FO4._value2member_map_ else str(x),
#     'Shader_Flags_2': lambda x: ShaderFlags2(x).name if x in ShaderFlags2._value2member_map_ else ShaderFlags2FO4(x).name if x in ShaderFlags2FO4._value2member_map_ else str(x),
#     'Shader_Type': lambda x: BSLSPShaderType(x).name if x in BSLSPShaderType._value2member_map_ else str(x),
#     'bhkMaterial': lambda x: SkyrimHavokMaterial(x).name if x in SkyrimHavokMaterial._value2member_map_ else str(x),
# }


def _get_from_store(store, fieldname, typename, game='SKYRIM'):
    """Reads the given field value from its representation in the dictionary-like store."""
    if fieldname in store:
        if fieldname in _enum_types:
            # Field has an enum type that can convert itself.
            try:
                if game in fo4_games and fieldname in _field_override_fo4:
                    return _field_override_fo4[fieldname].parse(store[fieldname])
                else:
                    return _enum_types[fieldname].parse(store[fieldname])
            except KeyError as e:
                pass
            try:
                return int(store[fieldname])
            except Exception as e:
                raise Exception(
                    f"Error converting value {store[fieldname]} for field {fieldname} and game {game}") from e
        elif typename in _array_types:
            # Value may be in a Blender property array or may be stored as a string.
            v = store[fieldname][:]
            if type(v) == str:
                try:
                    v = _type_from_store[typename](store, fieldname)
                except Exception as e:
                    raise Exception(f"Error evaluating array value {v} for field {fieldname} and type {typename}") from e
            return v
        elif typename in _type_from_store:
            # It's a numeric value that needs to be converted correctly.
            try:
                return _type_from_store[typename](store, fieldname)
            except Exception as e:
                raise Exception(
                    f"Error converting value {store}[{fieldname}] for field {fieldname} and type {typename}") from e
        else:
            return store[fieldname]


class pynStructure(Structure):
    """Structures used for communicating data to the nifly DLL."""

    def __init__(self, values=None, game='SKYRIM'):
        """Initialize structure from 'values'."""
        super().__init__()
        if hasattr(self, "bufSize"):
            self.bufSize = sizeof(self)
                
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
    
    def load(self, shape, ignore=[], game='SKYRIM'):
        """
        Load fields from the dictionary-like object 'shape'. 
        """
        if ignore is None: ignore = []
        for f, t in self._fields_:
            if f not in ignore:
                v = _get_from_store(shape, f, t.__name__, game=game)
                if v is not None:
                    try:
                        if type(v).__name__ == 'IDPropertyArray':
                            self.__setattr__(f, v[:])
                        else:
                            self.__setattr__(f, v)
                    except Exception as e:
                        raise Exception(f"Error setting property {f} <- {v}: {e}") from e


    def _value_from_buf(self, fieldname, game='SKYRIM'):
        """Get the value of a field, converting it to a user-friendly representation if possible."""
        v = self.__getattribute__(fieldname)
        if fieldname in _enum_types:
            try:
                if game in fo4_games and fieldname in _field_override_fo4:
                    return _field_override_fo4[fieldname](v).fullname
                else:
                    return _enum_types[fieldname](v).fullname
            except Exception as e:
                log.info(f"Unknown value {v} for field {fieldname} and game {game}") 
            return str(v)

        elif type(v) in [c_float, c_uint16, c_uint32, c_uint64, c_char]:
            return v.value
        else:
            return v
        

    def extract_field(self, shape, fieldname, fieldtype, game='SKYRIM'):
        """
        Extract a single field from the buffer and set as a key/value pair on the
        dictionary-like "shape". Subclasses can override this for special handling
        on fields that are interpreted for the user.
        """
        v = self._value_from_buf(fieldname, game)
        try:
            if type(v).__name__ == 'bytes':
                shape[fieldname] = v.decode('utf-8')
            else:
                shape[fieldname] = v
        except OverflowError as e:
            shape[fieldname] = repr(v)


    def extract(self, shape, ignore=None, game='SKYRIM'):
        """
        Extract fields to the dictionary-like object 'shape'. Do not extract any ID
        fields. Do not extract fields that match their default values.
        """
        if ignore is None: ignore = []
        defaults = self.__class__()
        for fn, t in self._fields_:
            if ((fn not in _noextract_fields) 
                and (fn not in ignore) 
                # and not (fn == 'Shader_Type' 
                #          and self.bufType == PynBufferTypes.BSEffectShaderPropertyBufType)
                ):

                if t.__name__ in _array_types:
                    v1 = [x for x in self.__getattribute__(fn)]
                    v2 = [x for x in defaults.__getattribute__(fn)]
                else:
                    v1 = self.__getattribute__(fn) 
                    v2 = defaults.__getattribute__(fn)
                
                if (type(v2) == float and not math.isclose(v1, v2, abs_tol=10**-5)) \
                        or (v1 != v2):
                    self.extract_field(shape, fn, t, game=game)

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
        

