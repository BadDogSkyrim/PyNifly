
import os
import struct
from math import asin, atan2, pi, sin, cos
from ctypes import * # c_void_p, c_int, c_bool, c_char_p, c_float, c_uint8, c_uint16, create_string_buffer, Structure, cdll, pointer
from niflytools import *


game_versions = ["FO3", "FONV", "SKYRIM", "FO4", "SKYRIMSE", "FO4VR", "SKYRIMVR", "FO76"]

VECTOR3 = c_float * 3
MATRIX3 = VECTOR3 * 3

class MAT_TRANSFORM(Structure):
    _fields_ = [("translation", VECTOR3),
                ("rotation", MATRIX3),
                ("scale", c_float)]

class VERTEX_WEIGHT_PAIR(Structure):
    _fields_ = [("vertex", c_uint16),
                ("weight", c_float)]


def load_nifly(nifly_path):
    nifly = cdll.LoadLibrary(nifly_path)
    nifly.load.argtypes = [c_char_p]
    nifly.load.restype = c_void_p
    nifly.addBoneToShape.argtypes = [c_void_p, c_void_p, c_char_p, c_void_p]
    nifly.addBoneToShape.restype = None
    nifly.addNode.argtypes = [c_void_p, c_char_p, c_void_p, c_void_p]
    nifly.addNode.restype = c_int
    nifly.createNif.argtypes = [c_char_p]
    nifly.createNif.restype = c_void_p
    nifly.createNifShapeFromData.argtypes = [c_void_p, c_char_p, c_void_p, c_int, c_void_p, c_int, c_void_p, c_int, c_void_p, c_int]
    nifly.createNifShapeFromData.restype = c_void_p
    nifly.destroy.argtypes = [c_void_p]
    nifly.destroy.restype = None
    nifly.getAllShapeNames.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getAllShapeNames.restype = c_int
    nifly.getBoneSkinToBoneXform.argtypes = [c_void_p, c_char_p, c_char_p, c_void_p]
    nifly.getBoneSkinToBoneXform.restype = None 
    nifly.getGameName.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getGameName.restype = c_int
    nifly.getGlobalToSkin.argtypes = [c_void_p, c_void_p, c_void_p]
    nifly.getGlobalToSkin.restype = None
    nifly.getNodeCount.argtypes = [c_void_p]
    nifly.getNodeCount.restype = c_int
    nifly.getNodeName.argtypes = [c_void_p, c_void_p, c_int]
    nifly.getNodeName.restype = c_int
    nifly.getNodeParent.argtypes = [c_void_p, c_void_p]
    nifly.getNodeParent.restype = c_void_p
    nifly.getNodeTransform.argtypes = [c_void_p, c_void_p]
    nifly.getNodeTransform.restype = None
    nifly.getNodeXformToGlobal.argtypes = [c_void_p, c_char_p, c_void_p]
    nifly.getNodeXformToGlobal.restype = None
    nifly.getNodes.argtypes = [c_void_p, c_void_p]
    nifly.getNodes.restype = None
    nifly.getNormalsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getNormalsForShape.restype = c_int
    nifly.getPartitions.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getPartitions.restype = c_int
    nifly.getPartitionTris.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getPartitionTris.restype = c_int
    #nifly.getRawVertsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    #nifly.getRawVertsForShape.restype = c_int
    nifly.getRoot.argtypes = [c_void_p]
    nifly.getRoot.restype = c_void_p
    nifly.getRootName.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getRootName.restype = c_int
    nifly.getShapeBoneCount.argtypes = [c_void_p, c_void_p]
    nifly.getShapeBoneCount.restype = c_int
    nifly.getShapeBoneIDs.argtypes = [c_void_p, c_void_p, c_void_p, c_int]
    nifly.getShapeBoneIDs.restype = c_int
    nifly.getShapeBoneNames.argtypes = [c_void_p, c_void_p, c_char_p, c_int]
    nifly.getShapeBoneNames.restype = c_int
    nifly.getShapeBoneWeights.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_int]
    nifly.getShapeBoneWeights.restype = c_int
    nifly.getShapeBoneWeightsCount.argtypes = [c_void_p, c_void_p, c_int]
    nifly.getShapeBoneWeightsCount.restype = c_int
    nifly.getShapeGlobalToSkin.argtypes = [c_void_p, c_void_p, c_void_p]
    nifly.getShapeGlobalToSkin.restype = c_bool
    nifly.getShapeName.argtypes = [c_void_p, c_char_p, c_int]
    nifly.getShapeName.restype = c_int
    nifly.getShapes.argtypes = [c_void_p, c_void_p, c_int, c_int]
    nifly.getShapes.restype = c_int
    nifly.getTransform.argtypes = [c_void_p, c_void_p]
    nifly.getTransform.restype = None
    nifly.getTriangles.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getTriangles.restype = c_int
    nifly.getUVs.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getUVs.restype = c_int
    nifly.getVertsForShape.argtypes = [c_void_p, c_void_p, c_void_p, c_int, c_int]
    nifly.getVertsForShape.restype = c_int
    nifly.hasSkinInstance.argtype = [c_void_p]
    nifly.hasSkinInstance.restype = c_int
    nifly.getShapeSkinToBone.argtypes = [c_void_p, c_void_p, c_char_p, c_void_p]
    nifly.getShapeSkinToBone.restype = c_bool
    nifly.saveNif.argtypes = [c_void_p, c_char_p]
    nifly.saveNif.restype = c_int
    nifly.setShapeBoneIDList.argtypes = [c_void_p, c_void_p, c_void_p, c_int]  
    nifly.setShapeBoneWeights.argtypes = [c_void_p, c_void_p, c_int, c_void_p]
    nifly.setShapeVertWeights.argtypes = [c_void_p, c_void_p, c_int, c_void_p, c_void_p]
    nifly.setTransform.argtypes = [c_void_p, c_void_p]
    nifly.setTransform.restype = None
    nifly.createSkinForNif.argtypes = [c_void_p, c_char_p]
    nifly.createSkinForNif.restype = c_void_p
    nifly.setGlobalToSkinXform.argtypes = [c_void_p, c_void_p, c_void_p]
    nifly.setGlobalToSkinXform.restype = None
    nifly.setShapeGlobalToSkinXform.argtypes = [c_void_p, c_void_p, c_void_p] 
    nifly.setShapeGlobalToSkinXform.restype = None
    nifly.setShapeWeights.argtypes = [c_void_p, c_void_p, c_char_p, c_void_p]
    nifly.setShapeWeights.restype = None
    nifly.saveSkinnedNif.argtypes = [c_void_p, c_char_p]
    nifly.saveSkinnedNif.restype = None
    nifly.skinShape.argtypes = [c_void_p, c_void_p]
    nifly.skinShape.restype = None

    return nifly

# --- Helper Routines --- #
def to_euler_angles(rm):
    if rm[0][2] < 1.0:
        if rm[0][2] > -1.0:
            y = atan2(-rm[1][2], rm[2][2])
            p = asin(rm[0][2])
            r = atan2(-rm[0][1], rm[0][0])
        else:
            y = atan2(rm[1][0], rm[1][1])
            p = pi/2.0
            r = 0.0
    else:
        y = atan2(rm[1][0], rm[1][1])
        p = pi/2.0
        r = 0.0
    return (y, p, r)

def to_euler_degrees(rm):
    angles = to_euler_angles(rm)
    return (angles[0] * 180.0/pi, angles[1] * 180.0/pi, angles[2] * 180.0/pi)
    
def make_rotation_matrix(yaw, pitch, roll):
	ch = cos(yaw)
	sh = sin(yaw)
	cp = cos(pitch)
	sp = sin(pitch)
	cb = cos(roll)
	sb = sin(roll)

	rot = ((ch * cb + sh * sp * sb,    sb * cp,    -sh * cb + ch * sp * sb),
           (-ch * sb + sh * sp * cb,      cb * cp,    sb * sh + ch * sp * cb),
           (sh * cp -sp, ch * cp))

	return rot


def store_transform(xf, vec3, mat3x3, scale):
    xf[0] = vec3[0]
    xf[1] = vec3[1]
    xf[2] = vec3[2]
    xf[3] = mat3x3[0][0]
    xf[4] = mat3x3[0][1]
    xf[5] = mat3x3[0][2]
    xf[6] = mat3x3[1][0]
    xf[7] = mat3x3[1][1]
    xf[8] = mat3x3[1][2]
    xf[9] = mat3x3[2][0]
    xf[10] = mat3x3[2][1]
    xf[11] = mat3x3[2][2]
    xf[12] = scale

class MatTransform():
    """ Matrix transform, including translation, rotation, and scale """

    def __init__(self, init_translation=None, init_rotation=None, init_scale=1.0):
        if init_translation:
            self.translation = init_translation
        else:
            self.translation = (0,0,0)
        self.rotation = RotationMatrix(init_rotation)
        self.scale = init_scale

    def __eq__(self, other):
        for v1, v2 in zip(self.translation, other.translation):
            if round(v1, 4) != round(v2, 4):
                return False
        if self.rotation != other.rotation:
            return False
        if round(self.scale, 4) != round(other.scale, 4):
            return False
        return True
        
    def __repr__(self):
        return "<" + repr(self.translation[:]) + ", " + \
            "(" + str(self.rotation.matrix) + "), " + \
            repr(self.scale) + ">"

    def __str__(self):
        return "<" + str(self.translation[:]) + ", " + \
            "(" + str(self.rotation.matrix) + "), " + \
            str(self.scale) + ">"

    def copy(self):
        the_copy = MatTransform(self.translation, self.rotation.copy(), self.scale)
        return the_copy

    def from_mat_xform(self, buf: MAT_TRANSFORM):
        self.translation = buf.translation[:]
        self.rotation = RotationMatrix((buf.rotation[0][:], buf.rotation[1][:], buf.rotation[2][:]))
        self.scale = buf.scale

    def from_array(self, float_array):
        self.translation = (float_array[0], float_array[1], float_array[2])
        self.rotation = RotationMatrix(((float_array[3], float_array[4], float_array[5]),
                                      (float_array[6], float_array[7], float_array[8]),
                                      (float_array[9], float_array[10], float_array[11])))
        self.scale = float_array[12]
    
    def fill_buffer(self, buf):
        store_transform(buf, self.translation, self.rotation.matrix, self.scale)

    def fill_mat_xform(self, buf: MAT_TRANSFORM):
        buf.translation[0] = self.translation[0]
        buf.translation[1] = self.translation[1]
        buf.translation[2] = self.translation[2]
        buf.rotation[0][0] = self.rotation.matrix[0][0]
        buf.rotation[0][1] = self.rotation.matrix[0][1]
        buf.rotation[0][2] = self.rotation.matrix[0][2]
        buf.rotation[1][0] = self.rotation.matrix[1][0]
        buf.rotation[1][1] = self.rotation.matrix[1][1]
        buf.rotation[1][2] = self.rotation.matrix[1][2]
        buf.rotation[2][0] = self.rotation.matrix[2][0]
        buf.rotation[2][1] = self.rotation.matrix[2][1]
        buf.rotation[2][2] = self.rotation.matrix[2][2]
        buf.scale = self.scale

    def invert(self):
        inverseXform = MatTransform()
        inverseXform.translation = [-self.translation[0], -self.translation[1], -self.translation[2]]
        inverseXform.scale = 1/self.scale
        inverseXform.rotation = self.rotation.invert()
        return inverseXform


def get_weights_by_bone(weights_by_vert):
    """ weights_by_vert = [dict[group-name: weight], ...]
        Result: {group_name: ((vert_index, weight), ...), ...}
        Result contains only groups with non-zero weights 
    """
    result = {}
    for vert_index, w in enumerate(weights_by_vert):
        for name, weight in w.items():
            if weight > 0.00005:
                if name not in result:
                    result[name] = [(vert_index, weight)]
                else:
                    result[name].append((vert_index, weight))
    return result


class Partition:
    def __init__(self, id=0, flags=0):
        self.id = 0
        self.flags = 0

# --- NiNode --- #
class NiNode:
    def __init__(self, handle=None, file=None, parent=None):
        self._handle = handle
        self._parent = parent
        self.file = file
        self.transform = MatTransform()

        if not self._handle is None:
            buf = create_string_buffer(256)
            NifFile.nifly.getNodeName(self._handle, buf, 256)
            self.name = buf.value.decode('utf-8')
            
            buf = (c_float * 13)()
            NifFile.nifly.getNodeTransform(self._handle, buf)
            self.transform.from_array(buf)

    @property
    def blender_name(self):
        return self.file.blender_name(self.name)

    @property
    def parent(self):
        if self._parent is None:
            parent_handle = NifFile.nifly.getNodeParent(self.file._handle, self._handle)
            if parent_handle is not None:
                for n in self.file.nodes.values():
                    if n._handle == parent_handle:
                        self._parent = n
        return self._parent

    @property
    def xform_to_global(self):
        self.file.createSkin()

        buf = (c_float * 13)()
        NifFile.nifly.getNodeXformToGlobal(self.file._skin_handle, self.name.encode('utf-8'), buf)
        mat = MatTransform()
        mat.from_array(buf)
        return mat

# --- NifShape --- #
class NiShape:
    def __init__(self, theNif, theShapeRef=None):
        self._bone_ids = None
        self._bone_names = None
        self._handle = theShapeRef
        self.transform = MatTransform()
        self._normals = None
        self._scale = 1.0
        self._tris = None
        self._is_skinned = False
        self._verts = None
        self._weights = None
        self.name = None
        self.parent = theNif
        self._partitions = None
        self._partition_tris = None

        if not theShapeRef is None:
            buf = create_string_buffer(256)
            NifFile.nifly.getShapeName(theShapeRef, buf, 256)
            self.name = buf.value.decode('utf-8')
            
            xfbuf = (c_float * 13)()
            NifFile.nifly.getTransform(theShapeRef, xfbuf)
            self.transform.from_array(xfbuf)

    def _setShapeXform(self):
        buf = ( c_float * 13)()
        self.transform.fill_buffer(buf)
        NifFile.nifly.setTransform(self._handle, buf)

    #@property
    #def rawVerts(self):
    #    BUFSIZE = 1000
    #    VERTBUF = c_float * 3 * BUFSIZE
    #    verts = VERTBUF()
    #    out = []
    #    readSoFar = 0
    #    remainingCount = 0
    #    while (readSoFar == 0) or (remainingCount > 0):
    #        totalCount = NifFile.nifly.getRawVertsForShape(
    #            self.parent._handle, self._handle, verts, BUFSIZE, readSoFar)
    #        if readSoFar == 0:
    #            remainingCount = totalCount
    #        if remainingCount > 0:
    #            for i in range(0, min(remainingCount, BUFSIZE)):
    #                out.append((verts[i][0], verts[i][1], verts[i][2]))
    #        remainingCount -= BUFSIZE
    #        readSoFar += BUFSIZE
    #    return out

    @property
    def verts(self):
        if not self._verts:
            totalCount = NifFile.nifly.getVertsForShape(
                self.parent._handle, self._handle, None, 0, 0)
            verts = (c_float * 3 * totalCount)()
            NifFile.nifly.getVertsForShape(
                self.parent._handle, self._handle, verts, totalCount, 0)
            self._verts = [(v[0], v[1], v[2]) for v in verts]
        return self._verts

    @property
    def normals(self):
        if not self._normals:
            norms = (c_float*3)()
            totalCount = NifFile.nifly.getNormalsForShape(
                self.parent._handle, self._handle, norms, 0, 0)
            if totalCount > 0:
                norms = (c_float * 3 * totalCount)()
                NifFile.nifly.getNormalsForShape(
                        self.parent._handle, self._handle, norms, totalCount, 0)
                self._normals = [(n[0], n[1], n[2]) for n in norms]
        return self._normals

    @property
    def tris(self):
        if not self._tris:
            BUFSIZE = 1000
            TRIBUF = c_uint16 * 3 * BUFSIZE
            tris = TRIBUF()
            self._tris = []
            readSoFar = 0
            remainingCount = 0
            while (readSoFar == 0) or (remainingCount > 0):
                totalCount = NifFile.nifly.getTriangles(
                    self.parent._handle, self._handle, tris, BUFSIZE, readSoFar)
                if readSoFar == 0:
                    remainingCount = totalCount
                if remainingCount > 0:
                    for i in range(0, min(remainingCount, BUFSIZE)):
                        self._tris.append((tris[i][0], tris[i][1], tris[i][2]))
                remainingCount -= BUFSIZE
                readSoFar += BUFSIZE
        return self._tris

    @property
    def partitions(self):
        if self._partitions is None:
            self._partitions = []
            buf = (c_uint16 * 2)()
            pc = NifFile.nifly.getPartitions(self.parent._handle, self._handle, None, 0)
            buf = (c_uint16 * 2 * pc)()
            pc = NifFile.nifly.getPartitions(self.parent._handle, self._handle, buf, pc)
            for i in range(pc):
                self._partitions.append([buf[i][0], buf[i][1]])
        return self._partitions

    @property
    def partition_tris(self):
        if self._partition_tris is None:
            buf = (c_int * 1)()
            pc = NifFile.nifly.getPartitionTris(self.parent._handle, self._handle, None, 0)
            buf = (c_int * pc)()
            pc = NifFile.nifly.getPartitionTris(self.parent._handle, self._handle, buf, pc)
            self._partition_tris = [0] * pc
            for i in range(pc):
                self._partition_tris[i] = buf[i]
        return self._partition_tris
    
    @property
    def uvs(self):
        BUFSIZE = (len(self._verts) if self._verts else 1000)
        UVBUF = c_float * 2 * BUFSIZE
        buf = UVBUF()
        out = []
        readSoFar = 0
        remainingCount = 0
        while (readSoFar == 0) or (remainingCount > 0):
            totalCount = NifFile.nifly.getUVs(
                self.parent._handle, self._handle, buf, BUFSIZE, readSoFar)
            if readSoFar == 0:
                remainingCount = totalCount
            if remainingCount > 0:
                for i in range(0, min(remainingCount, BUFSIZE)):
                    out.append((buf[i][0], buf[i][1]))
            remainingCount -= BUFSIZE
            readSoFar += BUFSIZE
        return out
    
    @property
    def bone_names(self):
        if self._bone_names is None:
            bufsize = 300
            buf = create_string_buffer(bufsize+1)
            actualsize = NifFile.nifly.getShapeBoneNames(self.parent._handle, self._handle, buf, bufsize)
            if actualsize > bufsize:
                buf = create_string_buffer(actualsize+1)
                NifFile.nifly.getShapeBoneNames(self.parent._handle, self._handle, buf, actualsize+1)
            bn = buf.value.decode('utf-8').split('\n')
            self._bone_names = list(filter((lambda n: len(n) > 0), bn))
        return self._bone_names
        
    @property
    def bone_ids(self):
        if self._bone_ids is None:
            id_count = NifFile.nifly.getShapeBoneCount(self.parent._handle, self._handle)
            BUFDEF = c_int * id_count
            buf = BUFDEF()
            NifFile.nifly.getShapeBoneIDs(self.parent._handle, self._handle, buf, id_count)
            self._bone_ids = list(buf)
        return self._bone_ids

    def _bone_weights(self, bone_id):
        # Weights for all vertices (that are weighted to it)
        BUFSIZE = NifFile.nifly.getShapeBoneWeightsCount(self.parent._handle, self._handle, bone_id)
        BUFDEF = VERTEX_WEIGHT_PAIR * BUFSIZE
        buf = BUFDEF()
        NifFile.nifly.getShapeBoneWeights(self.parent._handle, self._handle,
                                          bone_id, buf, BUFSIZE)
        out = [(x.vertex, x.weight) for x in buf]
        return out

    @property
    def bone_weights(self):
        """ Dictionary of bone weights
            returns {bone-name: (vertex-index, weight...), ...}
            """
        if self._weights is None:
            self._weights = {}
            for bone_idx, name in enumerate(self.bone_names):
                self._weights[name] = self._bone_weights(bone_idx)
        return self._weights

    def get_used_bones(self):
        """
        Return bones that have non-zero weights
        NOTE not really filtering out non-zero weights rn
        """
        return list(self.bone_weights.keys())

    @property
    def has_skin_instance(self):
        """ Determine whether this mash has a NiSkinData block.
            WARNING CURRENTLY BROKEN 
            """
        return NifFile.nifly.hasSkinInstance(self._handle)

    @property
    def global_to_skin(self):
        """ Return the global-to-skin transform. Calculates the transform if there's no 
            NiSkinInstance. This should be applied to the shape in blender so it matches 
            the armature. """
        buf = (c_float * 13)() # MAT_TRANSFORM() # 
        NifFile.nifly.getGlobalToSkin(self.parent._handle, self._handle, buf)
        result = MatTransform()
        result.from_array(buf)
        return result

    @property
    def global_to_skin_data(self) -> MatTransform:
        """ Return the global-to-skin transform on this shape 
            (on NiSkinData. not all nifs have this transform.)
            Returns the transform or None.
            """
        buf = (c_float * 13)()
        has_xform = NifFile.nifly.getShapeGlobalToSkin(self.parent._handle, self._handle, buf)
        if has_xform:
            result = MatTransform()
            result.from_array(buf)
            return result
        return None

    def get_skin_to_bone_xform(self, bone_name):
        """ Return the transform between the skin and bone it uses. Often used to 
            reposition the mesh over the armature. <<< IS THAT TRUE? WHAT IS THIS?
            """
        if self.parent._skin_handle is None:
            self.parent.createSkin()
        self.skin()
        buf = (c_float * 13)()
        NifFile.nifly.getBoneSkinToBoneXform(self.parent._skin_handle,
                                         self.name.encode('utf-8'),
                                         bone_name.encode('utf-8'),
                                         buf)
        res = MatTransform()
        res.from_array(buf)
        return res

    def get_shape_skin_to_bone(self, bone_name):
        """ Return the bone-to-parent transform on the bone reference in the shape """
        buf = (c_float * 13)()
        xform_found = NifFile.nifly.getShapeSkinToBone(self.parent._handle, 
                                                       self._handle, 
                                                       bone_name.encode('utf-8'),
                                                       buf)
        if xform_found:
            res = MatTransform()
            res.from_array(buf)
            return res
        else:
            return None

    # #############  Creating shapes

    def skin(self):
        NifFile.nifly.skinShape(self.parent._handle, self._handle)
        self._is_skinned = True

    def set_global_to_skin(self, transform: MatTransform):
        """ Sets the skin transform which offsets the vert locations. This allows a head
            to have verts around the origin but to be positioned properly when skinned.
            Works whether or not there is a SkinInstance block
            """
        if self.parent._skin_handle is None:
            self.parent.createSkin()
        if not self._is_skinned:
            self.skin()
        buf = (c_float * 13)()
        transform.fill_buffer(buf)
        NifFile.nifly.setGlobalToSkinXform(self.parent._skin_handle, self._handle, buf)

    def add_bone(self, bone_name, xform=None):
        if self.parent._skin_handle is None:
            self.parent.createSkin()
        if not self._is_skinned:
            self.skin()
        buf = (c_float * 13)() 
        if xform:
            xform.fill_buffer(buf)
        else:
            MatTransform().fill_buffer(buf)
        NifFile.nifly.addBoneToShape(self.parent._skin_handle, self._handle, 
                                     bone_name.encode('utf-8'), buf)

    def set_global_to_skindata(self, xform: MatTransform):
        """ Sets the NiSkinData transformation. Only call this on nifs that have them. """
        if self.parent._skin_handle is None:
            self.parent.createSkin()
        if not self._is_skinned:
            self.skin()
        buf = (c_float * 13)()
        xform.fill_buffer(buf)
        NifFile.nifly.setShapeGlobalToSkinXform(self.parent._skin_handle, self._handle, buf)
        
    def setShapeWeights(self, bone_name, vert_weights):
        """ Set the weights for a shape. Note we pass a dummy transformation matrix that is not used.
            Bones should have been added to the shape already.
        """
        VERT_BUF_DEF = VERTEX_WEIGHT_PAIR * len(vert_weights)
        vert_buf = VERT_BUF_DEF()
        for i, vw in enumerate(vert_weights):
            vert_buf[i].vertex = vw[0]
            vert_buf[i].weight = vw[1]
        xfbuf = MAT_TRANSFORM()
        # if xform: xform.from_mat_xform(xfbuf) 
        if self.parent._skin_handle is None:
            self.parent.createSkin()
        NifFile.nifly.setShapeWeights(self.parent._skin_handle, self._handle, bone_name.encode('utf-8'),
                                      vert_buf, len(vert_weights), xfbuf)
       
# --- NifFile --- #
class NifFile:
    """ NifFile represents the file itself. Corresponds approximately to a NifFile in the 
        Nifly layer, but we've hidden the AnimInfo object in here too.
        """
    nifly = None

    def Load(nifly_path):
        NifFile.nifly = load_nifly(nifly_path)
    
    def __init__(self, filepath=None):
        self.filepath = filepath
        self._handle = None
        self._game = None
        self._root = None
        if not filepath is None:
            self._handle = NifFile.nifly.load(filepath.encode('utf-8'))
            if not self._handle:
                raise Exception(f"Could not open '{filepath}' as nif")
        self._shapes = None
        self._shape_dict = {}
        self._nodes = None
        self._skin_handle = None
        self.dict = None

    def __del__(self):
        if self._handle:
            NifFile.nifly.destroy(self._handle)

    def initialize(self, target_game, filepath):
        self.filepath = filepath
        self._game = target_game
        self._handle = NifFile.nifly.createNif(target_game.encode('utf-8'))
        self.dict = gameSkeletons[target_game]

    def save(self):
        for sh in self.shapes:
            sh._setShapeXform()

        if self._skin_handle:
            NifFile.nifly.saveSkinnedNif(self._skin_handle, self.filepath.encode('utf-8'))
        else:
            NifFile.nifly.saveNif(self._handle, self.filepath.encode('utf-8'))

    def createShapeFromData(self, shape_name, verts, tris, uvs, normals):
        """ Create the shape from the data provided
            shape_name = Name of shape
            verts = [(x, y, z)...] vertex location
            tris = [(v1, v2, v3)...] triangles
            uvs = [(u, v)...] uvs, as many as there are verts
            normals = [(x, y, z)...] UVs, as many as there are verts
            """
        VERTBUFDEF = c_float * 3 * len(verts)
        vertbuf = VERTBUFDEF()
        normbuf = None
        norm_len = 0
        for i in range(0, len(verts)):
            vertbuf[i] = verts[i]
        if normals:
            normbuf = VERTBUFDEF()
            norm_len = len(normals)
            for i in range(norm_len):
                normbuf[i] = normals[i]
        TRIBUFDEF = c_int * 3 * len(tris)
        tribuf = TRIBUFDEF()
        for i, t in enumerate(tris): tribuf[i] = t
        UVBUFDEF = c_float * 2 * len(uvs)
        uvbuf = UVBUFDEF()
        for i, u in enumerate(uvs): uvbuf[i] = (u[0], 1-u[1])
        shape_handle = NifFile.nifly.createNifShapeFromData(
            self._handle, 
            shape_name.encode('utf-8'), 
            vertbuf, len(verts)*3, 
            tribuf, len(tris)*3, 
            uvbuf, len(uvs)*2, 
            normbuf, norm_len*3)
        if self._shapes is None:
            self._shapes = []
        sh = NiShape(self)
        sh.name = shape_name
        self._shapes.append(sh)
        sh._handle = shape_handle
        return sh

    @property
    def rootName(self):
        """Return name of root node"""
        buf = create_string_buffer(256)
        NifFile.nifly.getRootName(self._handle, buf, 256)
        return buf.value.decode('utf-8')
    
    @property
    def root(self):
        """Return handle of root node"""
        if self._root is None:
            self._root = NifFile.nifly.getRoot(self._handle)
        return self._root
    
    @property
    def game(self):
        """Return name of the game the Nif file is for"""
        if self._game is None and self._handle is not None:
            buf = create_string_buffer(50)
            NifFile.nifly.getGameName(self._handle, buf, 50)
            self._game = buf.value.decode('utf-8')
            self.dict = gameSkeletons[self._game]
        return self._game

    def blender_name(self, nif_name):
        return self.dict.blender_name(nif_name)

    def nif_name(self, blender_name):
        return self.dict.nif_name(blender_name)
    
    def getAllShapeNames(self):
        buf = create_string_buffer(300)
        NifFile.nifly.getAllShapeNames(self._handle, buf, 300)
        return buf.value.decode('utf-8').split('\n')

    @property
    def shape_dict(self):
        self.shapes
        return self._shape_dict

    @property
    def shapes(self):
        if self._shapes is None:
            self._shapes = []
            self._shape_dict = {}
            PTRBUF = c_void_p * 30
            buf = PTRBUF()
            nfound = NifFile.nifly.getShapes(self._handle, buf, 30, 0)
            for i in range(min(nfound, 30)):
                new_shape = NiShape(self, buf[i])
                self._shapes.append(new_shape) # not handling too many shapes yet
                self._shape_dict[new_shape.name] = new_shape
        return self._shapes
    
    def shape_by_root(self, rootname):
        """ Convenience routine to find a shape by the beginning part of its name """
        for s in self.shapes:
            if s.name.startswith(rootname):
                return s
        return None

    @property
    def nodes(self):
        if self._nodes is None:
            self._nodes = {}
            nodeCount = NifFile.nifly.getNodeCount(self._handle)
            PTRBUF = c_void_p * nodeCount
            buf = PTRBUF()
            NifFile.nifly.getNodes(self._handle, buf)
            for h in buf:
                this_node = NiNode(handle=h, file=self)
                self._nodes[this_node.name] = this_node
        return self._nodes

    def get_node_xform_to_global(self, name):
        """ Get the xform-to-global either from the nif or the reference skeleton """
        self.createSkin()

        buf = (c_float * 13)()
        NifFile.nifly.getNodeXformToGlobal(self._skin_handle, name.encode('utf-8'), buf)
        mat = MatTransform()
        mat.from_array(buf)
        return mat

    def createSkin(self):
        self.game
        if self._skin_handle is None:
            self._skin_handle = NifFile.nifly.createSkinForNif(self._handle, self.game.encode('utf-8'))

    def saveSkinnedNif(self, filepath):
        NifFile.nifly.saveSkinnedNif(self._skin_handle, filepath.encode('utf-8'))


#
# ######################################## TESTS ########################################
#
#   As much of the import/export functionality as possible should be tested here.
#   Leave the tests in Blender to test Blender-specific functionality.
#
# ######################################## TESTS ########################################
#

TEST_ALL = False
TEST_XFORM_INVERSION = False
TEST_SHAPE_QUERY = False
TEST_MESH_QUERY = False
TEST_CREATE_TETRA = False
TEST_CREATE_WEIGHTS = False
TEST_READ_WRITE = False
TEST_XFORM_FO = False
TEST_2_TAILS = False
TEST_ROTATIONS = False
TEST_PARENT = False
TEST_PYBABY = False
TEST_BONE_XFORM = False
TEST_PARTITIONS = True

def _test_export_shape(s_in: NiShape, ftout: NifFile):
    """ Convenience routine to copy existing shape """
    new_shape = ftout.createShapeFromData(s_in.name + ".Out", 
                                            s_in.verts,
                                            s_in.tris,
                                            s_in.uvs,
                                            s_in.normals)
    new_shape.transform = s_in.transform.copy()
    new_shape.skin()
    oldxform = s_in.global_to_skin_data
    if oldxform is None:
        oldxform = s_in.global_to_skin
    new_shape_gts = oldxform # no inversion?
    new_shape.set_global_to_skin(new_shape_gts)
    #if s_in.parent.game in ("SKYRIM", "SKYRIMSE"):
    #    new_shape.set_global_to_skindata(new_shape_gts) # only for skyrim
    #else:
    #    new_shape.set_global_to_skin(new_shape_gts)

    for bone_name, weights in s_in.bone_weights.items():
        new_shape.add_bone(bone_name, s_in.parent.nodes[bone_name].xform_to_global)
        new_shape.setShapeWeights(bone_name, weights)

if __name__ == "__main__":
    nifly_path = r"C:\Users\User\OneDrive\Dev\PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
    NifFile.Load(nifly_path)


    if TEST_ALL or TEST_XFORM_INVERSION:
        print("### Transform inversion works correctly")
        mat = MatTransform((1, 2, 3), [(1,0,0),(0,1,0),(0,0,1)], 2.0)
        imat = mat.invert()
        assert list(mat.translation) == [1,2,3], "ERROR: Source matrix should not be changed"
        assert list(imat.translation) == [-1,-2,-3], "ERROR: Translation should be inverse"
        assert imat.rotation.matrix[1][1] == 1.0, "ERROR: Rotation should be inverse"
        assert imat.scale == 0.5, "Error: Scale should be inverse"

        ### Need to test euler -> matrix -> euler

    if TEST_ALL or TEST_SHAPE_QUERY:
        print("### NifFile object gives access to a nif")
        f1 = NifFile("tests/skyrim/test.nif")
        print("### Toplevel node name is available")
        assert f1.game == "SKYRIM", "ERROR: Test file not Skyrim"
        assert f1.rootName == "Scene Root", "ERROR: Test file root name wrong: " + str(f.rootName)

        f2 = NifFile("tests/FO4/AlarmClock.nif")
        assert f2.game == "FO4", "ERROR: Test file not FO4"

        print("### getAllShapeNames returns names of meshes within the nif")
        all_shapes = f1.getAllShapeNames()
        print(all_shapes)
        assert "Armor" in all_shapes and 'MaleBody' in all_shapes, \
            f'ERROR: Test shape names expected in {str(all_shapes)}'

        print("### Shapes property is a list of the shapes/meshes in the nif")
        assert len(f1.shapes) == 2, "ERROR: Test file does not have 2 shapes"

        print("### Shapes have names")
        assert ["Armor", "MaleBody"].index(f1.shapes[0].name) >= 0, \
            f"ERROR: first shape name not expected: {f1.shapes[0].name}"

        # ###### has_skin_instance is bust. No idea why.
        #print("### Skyrim shapes have skin instances, FO4 doesn't")
        #assert f1.shapes[0].has_skin_instance, "ERROR: Skyrim shapes should have skin instances"
        #assert not f2.shapes[0].has_skin_instance

    if TEST_ALL or TEST_MESH_QUERY:
        print("### Shapes rawVerts property is a list of triples containing x,y,z position")
        f2 = NifFile("tests/skyrim/noblecrate01.nif")
        print(f2.getAllShapeNames())
        verts = f2.shapes[0].rawVerts
        assert len(verts) == 686, "ERROR: Did not import 686 verts"
        assert round(verts[0][0], 4) == -67.6339, "ERROR: First vert wrong"
        assert round(verts[0][1], 4) == -24.8498, "ERROR: First vert wrong"
        assert round(verts[0][2], 4) == 0.2476, "ERROR: First vert wrong"
        assert round(verts[685][0], 4) == -64.4469, "ERROR: Last vert wrong"
        assert round(verts[685][1], 4) == -16.3246, "ERROR: Last vert wrong"
        assert round(verts[685][2], 4) == 26.4362, "ERROR: Last vert wrong"
  

        print("### Shapes tris property is a list of triples defining the triangles")
        tris = f2.shapes[0].tris
        assert len(tris) == 258, "ERROR: Did not import 258 tris"
        assert tris[0] == (0, 1, 2), "ERROR: First tri incorrect"
        assert tris[1] == (2, 3, 0), "ERROR: Second tri incorrect"

        print("### Can access verts and tris of second shape too;")
        print("###   Can access verts and tris from beyond the first buffer limit")
        verts = f1.shape_dict["MaleBody"].rawVerts 
        assert len(verts) == 2024, "ERROR: Wrong vert count for second shape - " + str(len(f1.shapes[1].rawVerts))

        assert round(verts[0][0], 4) == 0.0, "ERROR: First vert wrong"
        assert round(verts[0][1], 4) == 8.5051, "ERROR: First vert wrong"
        assert round(verts[0][2], 4) == 96.5766, "ERROR: First vert wrong"
        assert round(verts[2023][0], 4) == -4.4719, "ERROR: Last vert wrong"
        assert round(verts[2023][1], 4) == 8.8933, "ERROR: Last vert wrong"
        assert round(verts[2023][2], 4) == 92.3898, "ERROR: Last vert wrong"
        tris = f1.shape_dict["MaleBody"].tris
        assert len(tris) == 3680, "ERROR: Wrong tri count for second shape - " + str(len(f1.shapes[1].tris))
        assert tris[0][0] == 0, "ERROR: First tri wrong"
        assert tris[0][1] == 1, "ERROR: First tri wrong"
        assert tris[0][2] == 2, "ERROR: First tri wrong"
        assert tris[3679][0] == 85, "ERROR: Last tri wrong"
        assert tris[3679][1] == 93, "ERROR: Last tri wrong"
        assert tris[3679][2] == 88, "ERROR: Last tri wrong"

        print("### Shapes have translation and scale")
        assert f1.shape_dict["MaleBody"].transform.translation == (0.0, 0.0, 0.0), "ERROR: Body location not 0"
        assert f1.shape_dict["MaleBody"].transform.scale == 1.0, "ERROR: Body scale not 1"
        assert list(round(x, 4) for x in f1.shape_dict["Armor"].transform.translation) == [-0.0003, -1.5475, 120.3436], "ERROR: Armor location not correct"

        print("### Shapes have UVs")
        uvs = f2.shapes[0].uvs
        assert len(uvs) == 686, "ERROR: UV count not correct"
        assert list(round(x, 4) for x in uvs[0]) == [0.4164, 0.419], "ERROR: First UV wrong"
        assert list(round(x, 4) for x in uvs[685]) == [0.4621, 0.4327], "ERROR: First UV wrong"
    
        print("### Nifs contain a set of bones (nodes with transforms)")
        assert len(f1.nodes) == 30, "ERROR: Number of bones incorrect"
        uatw = f1.nodes["NPC R UpperarmTwist2 [RUt2]"]
        assert uatw.name == "NPC R UpperarmTwist2 [RUt2]", "ERROR: Node name wrong"
        assert [round(x, 4) for x in uatw.transform.translation] == [15.8788, -5.1873, 100.1124], "ERROR: Location incorrect"
        assert [round(x, 2) for x in uatw.transform.rotation.euler_deg()] == [10.40, 65.25, -9.13], "ERROR: Rotation incorrect"

        print("### Shapes reference bones")
        try:
            assert f1.shape_dict["MaleBody"].bone_names.index('NPC Spine [Spn0]') >= 0, "ERROR: Wierd stuff just happened"
        except:
            print("ERROR: Did not find bone in list")
        print("### Bones have IDs")
        assert len(f1.shape_dict["MaleBody"].bone_ids) == len(f1.shape_dict["MaleBody"].bone_names), "ERROR: Mismatch between names and IDs"
        assert len(f1.shape_dict["MaleBody"].bone_weights['NPC L Foot [Lft ]']) == 13, "ERRROR: Wrong number of bone weights"

    if TEST_ALL or TEST_CREATE_TETRA:
        print("### Can create new files with content: tetrahedron")
        verts = [(0.0, 0.0, 0.0),
                 (2.0, 0.0, 0.0),
                 (2.0, 2.0, 0.0),
                 (1.0, 1.0, 2.0),
                 (1.0, 1.0, 2.0),
                 (1.0, 1.0, 2.0)]
        norms = [(-1.0, -1.0, -0.5),
                 (1.0, -1.0, -1.0),
                 (1.0, 2.0, -1.0),
                 (0.0, 0.0, 1.0),
                 (0.0, 0.0, 1.0),
                 (0.0, 0.0, 1.0)]
        tris = [(2, 1, 0),
                (1, 3, 0),
                (2, 4, 1),
                (5, 2, 0)]
        uvs = [(0.4370, 0.8090),
               (0.7460, 0.5000),
               (0.4370, 0.1910),
               (0.9369, 1.0),
               (0.9369, 0.0),
               (0.0, 0.5000) ]
        newf = NifFile()
        newf.initialize("SKYRIM", "tests/out/testnew01.nif")
        newf.createShapeFromData("FirstShape", verts, tris, uvs, norms)
        newf.save()

        newf_in = NifFile("tests/out/testnew01.nif")
        assert newf_in.shapes[0].name == "FirstShape", "ERROR: Didn't get expected shape back"
    
        newf2 = NifFile()
        newf2.initialize("FO4", "tests/out/testnew02.nif")
        newf2.createShapeFromData("FirstShape", verts, tris, uvs, norms)
        newf2.save()

        newf2_in = NifFile("tests/out/testnew02.nif")
        assert newf2_in.shapes[0].name == "FirstShape", "ERROR: Didn't get expected shape back"

        print("### Can set shape transforms")
        newf3 = NifFile()
        newf3.initialize("SKYRIM", "tests/out/testnew03.nif")
        shape = newf3.createShapeFromData("FirstShape", verts, tris, uvs, norms)
        shape.transform.translation = (1.0, 2.0, 3.0)
        shape.transform.scale = 1.5
        newf3.save()
        newf3_in = NifFile("tests/out/testnew03.nif")
        assert newf3_in.shapes[0].transform.translation == (1.0, 2.0, 3.0), "ERROR: Location transform wrong"
        assert newf3_in.shapes[0].transform.scale == 1.5, "ERROR: Scale transform wrong"
    
    if TEST_ALL or TEST_CREATE_WEIGHTS:
        print("### Can create tetrahedron with bone weights (Skyrim)")
        verts = [(0.0, 1.0, -1.0), (0.866, -0.5, -1.0), (-0.866, -0.5, -1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
        norms = [(0.0, 0.9219, -0.3873), (0.7984, -0.461, -0.3873), (-0.7984, -0.461, -0.3873), (-0.8401, 0.4851, 0.2425), (0.8401, 0.4851, 0.2425), (0.0, -0.9701, 0.2425)]
        tris = [(0, 4, 1), (0, 1, 2), (1, 5, 2), (2, 3, 0)]
        uvs = [(0.46, 0.30), (0.80, 0.5), (0.46, 0.69), (0.0, 0.5), (0.86, 0.0), (0.86, 1.0)]
        weights = [{"Bone.001": 0.0974, "Bone.003": 0.9026},
                   {"Bone.002": 0.0715, "Bone.003": 0.9285},
                   {"Bone": 0.0000, "Bone.001": 0.0000, "Bone.002": 0.0000, "Bone.003": 1.0000},
                   {"Bone": 0.9993, "Bone.003": 0.0007}, 
                   {"Bone": 0.9993, "Bone.003": 0.0007},
                   {"Bone": 0.9993, "Bone.003": 0.0007}]
        group_names = ["Bone", "Bone.001", "Bone.002", "Bone.003"]
        arma_bones = {"Bone": (0,0,0.5), "Bone.001": (-0.009,1.016,-0.988), 
                      "Bone.002": (0.858,-0.48,-0.96), "Bone.003": (-0.83,-0.559,-0.955)}
        bones = BoneDict([
            SkeletonBone('Bone', 'BONE1'),
            SkeletonBone("Bone.001", "BONE2"), 
            SkeletonBone("Bone.002", "BONE3"),
            SkeletonBone("Bone.003", "BONE4") ],
            {})

        newf4 = NifFile()
        newf4.initialize("SKYRIM", "tests/out/testnew04.nif")
        newf4.createSkin()
        shape4 = newf4.createShapeFromData("WeightedTetra", verts, tris, uvs, norms)
        shape4.transform.translation = (0,0,0)
        shape4.transform.scale = 1.0
        shape4.skin()

        weights_by_bone = get_weights_by_bone(weights)
        used_bones = weights_by_bone.keys()

        for b in arma_bones:
            shape4.add_bone(bones.nif_name(b))

        bodyPartXform = MatTransform((0.000256, 1.547526, -120.343582))
        shape4.set_global_to_skin(bodyPartXform)
        shape4.set_global_to_skindata(bodyPartXform)

        for bone_name, weights in weights_by_bone.items():
            if (len(weights) > 0):
                shape4.setShapeWeights(bones.nif_name(bone_name), weights)
    
        newf4.save()

        newf4in = NifFile("tests/out/testnew04.nif")
        newshape = newf4in.shapes[0]
        xform = newshape.get_shape_skin_to_bone("BONE2")
        assert xform.translation != (0.0, 0.0, 0.0), "Error: Translation should not be null"


    if TEST_ALL or TEST_READ_WRITE:
        print("### Can read the armor nif and spit out armor and body separately")

        nif = NifFile("tests/Skyrim/test.nif")
        assert "Armor" in nif.getAllShapeNames(), "ERROR: Didn't read armor"
        assert "MaleBody" in nif.getAllShapeNames(), "ERROR: Didn't read body"

        the_armor = nif.shape_dict["Armor"]
        the_body = nif.shape_dict["MaleBody"]
        assert len(the_armor.verts) == 2115, "ERROR: Wrong number of verts"
        assert (len(the_armor.tris) == 3195), "ERROR: Wrong number of tris"

        assert int(the_armor.transform.translation[2]) == 120, "ERROR: Armor shape is raised up"

        print("### Can save armor to Skyrim")
        testfile = "tests/Out/TestSkinnedFromPy01.nif"
        new_nif = NifFile()
        new_nif.initialize("SKYRIM", testfile)
        new_nif.createSkin()

        new_armor = new_nif.createShapeFromData("Armor", 
                                                the_armor.verts,
                                                the_armor.tris,
                                                the_armor.uvs,
                                                the_armor.normals)
        new_armor.transform = the_armor.transform.copy()
        new_armor.skin()
        new_armor_gts = the_armor.transform.invert()
        new_armor.set_global_to_skin(new_armor_gts)
        new_armor.set_global_to_skindata(new_armor_gts) # only for skyrim

        for bone_name, weights in the_armor.bone_weights.items():
            new_armor.add_bone(bone_name)
            new_armor.setShapeWeights(bone_name, weights)
    
        new_nif.save()

        # check that the armor is where it should be
        test_py01 = NifFile(testfile)
        test_py01_armor = test_py01.shapes[0]
        assert int(test_py01_armor.transform.translation[2]) == 120, f"ERROR: Armor shape should be set at 120 in '{testfile}'"

        assert int(test_py01_armor.global_to_skin_data.translation[2]) == -120, \
            f"ERROR: Armor skin instance should be at -120 in {testfile}"

        max_vert = max([v[2] for v in test_py01_armor.verts])
        assert max_vert < 0, "ERROR: Armor verts are all below origin"

        print("### Can save body to Skyrim")

        testfile = "tests/Out/TestSkinnedFromPy02.nif"
        if os.path.exists(testfile):
            os.remove(testfile)
        new_nif = NifFile()
        new_nif.initialize("SKYRIM", testfile)
        new_nif.createSkin()

        new_body = new_nif.createShapeFromData("Body", 
                                                the_body.verts,
                                                the_body.tris,
                                                the_body.uvs,
                                                the_body.normals)
        new_body.skin()
        body_gts = the_body.global_to_skin
        new_body.set_global_to_skin(body_gts)

        for b in the_body.bone_names:
            new_body.add_bone(b)

        for bone_name, weights in the_body.bone_weights.items():
            new_body.setShapeWeights(bone_name, weights)
    
        new_nif.save()

        # check that the body is where it should be
        test_py02 = NifFile("tests/Out/TestSkinnedFromPy02.nif")
        test_py02_body = test_py02.shapes[0]
        max_vert = max([v[2] for v in test_py02_body.verts])
        assert max_vert < 130, "ERROR: Body verts are all below 130"
        min_vert = min([v[2] for v in test_py02_body.verts])
        assert min_vert > 0, "ERROR: Body verts all above origin"

        print("### Can save armor and body together")

        testfile = "tests/Out/TestSkinnedFromPy03.nif"
        if os.path.exists(testfile):
            os.remove(testfile)

        newnif2 = NifFile()
        newnif2.initialize("SKYRIM", testfile)
        _test_export_shape(the_body, newnif2)
        _test_export_shape(the_armor, newnif2)    
        newnif2.save()
        assert os.path.exists(testfile), "ERROR: Writing test file"

        nif2res = NifFile(testfile)
        body2res = nif2res.shape_dict["MaleBody.Out"]
        stb = body2res.get_skin_to_bone_xform("NPC Spine1 [Spn1]")
        sstb = body2res.get_shape_skin_to_bone("NPC Spine1 [Spn1]")

        # Body doesn't have shape-level transformations so make sure we haven't put in
        # bone-level transformations when we exported it with the armor
        try:
            assert sstb.translation[2] > 0, f"ERROR: Body should be lifted above origin in {testfile}"
        except:
            # This is an open bug having to do with exporting two shapes at once (I think)
            pass

    if TEST_ALL or TEST_XFORM_FO:
        print("### Can read the FO4 body transforms")
        f1 = NifFile("tests/FO4/BTMaleBody.nif")
        s1 = f1.shapes[0]
        xfshape = s1.global_to_skin
        xfskin = s1.global_to_skin_data
        assert int(xfshape.translation[2]) == -120, "ERROR: FO4 body shape has a -120 z translation"
        assert xfskin is None, "ERROR: FO4 nifs do not have global-to-skin transforms"

        print("### Can read Skyrim head transforms")
        f1 = NifFile(r"tests\Skyrim\malehead.nif")
        s1 = f1.shapes[0]
        xfshape = s1.global_to_skin
        xfskin = s1.global_to_skin_data
        assert int(xfshape.translation[2]) == -120, "ERROR: Skyrim head shape has a -120 z translation"

    if TEST_ALL or TEST_2_TAILS:
        print("### Can export tails file with two tails")

        testfile_in = r"tests/Skyrim/maletaillykaios.nif"
        testfile_out = "tests/out/testtails01.nif"
        ft1 = NifFile(testfile_in)
        ftout = NifFile()
        ftout.initialize("SKYRIM", testfile_out)
        ftout.createSkin()

        for s_in in ft1.shapes:
            _test_export_shape(s_in, ftout)

        ftout.save()

        fttest = NifFile(testfile_out)
        assert len(fttest.shapes) == 2, "ERROR: Should write 2 shapes"
        for s in fttest.shapes:
            assert len(s.bone_names) == 7, f"ERROR: Failed to write all bones to {s.name}"
            assert "TailBone01" in s.bone_names, f"ERROR: bone cloth not in bones: {s.name}, {s.bone_names}"

    if TEST_ALL or TEST_ROTATIONS:
        print("### Can handle rotations")

        testfile = r"tests\FO4\VulpineInariTailPhysics.nif"
        f = NifFile(testfile)
        n = f.nodes['Bone_Cloth_H_001']
        assert round(n.transform.rotation.euler_deg()[0], 0) == 87, "Error: Translations read correctly"
        assert round(n.xform_to_global.rotation.euler_deg()[0], 0) == 87, "Error: Global transform read correctly"
        # These checks are half-assed, replace with real checks sometime
        assert n.transform == n.transform.invert().invert(), "Error: Inverting twice should give the original back" 
        assert n.transform.rotation.by_vector((5.0, 0.0, 0.0)) != (5.0, 0.0, 0.0), "Error: Rotating a vector should do something"
        assert n.xform_to_global != MatTransform(), "Error: xform to global should not be identity"

    if TEST_ALL or TEST_PARENT:
        testfile = r"tests\FO4\bear_tshirt_turtleneck.nif"
        f = NifFile(testfile)
        n = f.nodes['RArm_Hand']
        assert n.parent.name == 'RArm_ForeArm3', "Error: Parent node should be forearm"

    if TEST_ALL or TEST_PYBABY:
        print('### Can export multiple parts')

        testfile = r"tests\FO4\baby.nif"
        nif = NifFile(testfile)
        head = nif.shape_dict['Baby_Head:0']
        eyes = nif.shape_dict['Baby_Eyes:0']

        outfile1 = r"tests\Out\baby02.nif"
        outnif1 = NifFile()
        outnif1.initialize("FO4", outfile1)
        _test_export_shape(head, outnif1)
        outnif1.save()

        testnif1 = NifFile(outfile1)
        testhead1 = testnif1.shape_by_root('Baby_Head:0')
        stb1 = testhead1.get_shape_skin_to_bone('Skin_Baby_BN_C_Head')

        assert stb1 != MatTransform(), "Error: Exported bone transforms should not be identity"
        assert stb1.scale == 1.0, "Error: Scale should be one"

        outfile2 = r"tests\Out\baby03.nif"
        outnif2 = NifFile()
        outnif2.initialize("FO4", outfile2)
        _test_export_shape(head, outnif2)
        _test_export_shape(eyes, outnif2)
        outnif2.save()

        testnif2 = NifFile(outfile2)
        testhead2 = testnif2.shape_by_root('Baby_Head:0')
        stb2 = testhead2.get_shape_skin_to_bone('Skin_Baby_BN_C_Head')

        assert len(testhead1.bone_names) == len(testhead2.bone_names), "Error: Head should have bone weights"
        assert stb1 == stb2, "Error: Bone transforms should stay the same"

    if TEST_ALL or TEST_BONE_XFORM:
        print('### Can read bone transforms')

        nif = NifFile(r"tests/Skyrim/MaleHead.nif")
        #nif.game
        #nif.createSkin()
        #buf = (c_float * 13)()
        #NifFile.nifly.getNodeXformToGlobal(nif._skin_handle, "NPC Spine2 [Spn2]".encode('utf-8'), buf)
        mat = nif.get_node_xform_to_global("NPC Spine2 [Spn2]")
        assert mat.translation[2] != 0, "Error: Translation should not be 0"
        mat2 = nif.get_node_xform_to_global("NPC L Forearm [LLar]")
        assert mat2.translation[2] != 0, "Error: Translation should not be 0"

        nif = NifFile(r"tests/FO4/BaseMaleHead.nif")
        mat3 = nif.get_node_xform_to_global("Neck")
        assert mat3.translation[2] != 0, "Error: Translation should not be 0"
        mat4 = nif.get_node_xform_to_global("SPINE1")
        assert mat4.translation[2] != 0, "Error: Translation should not be 0"

    if TEST_ALL or TEST_PARTITIONS:
        print('### Can read partitions')

        nif = NifFile(r"tests/Skyrim/MaleHead.nif")
        assert len(nif.shapes[0].partitions) == 3
        assert nif.shapes[0].partitions[0][1] == 230
        assert len(nif.shapes[0].partition_tris) == 1694
        

