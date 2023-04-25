"""Common definitions for the Blender plugin"""

from enum import IntFlag
from mathutils import Matrix, Vector, Quaternion, geometry
from nifdefs import *
from pynifly import *


NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"
ALPHA_MAP_NAME = "VERTEX_ALPHA"
GLOSS_SCALE = 100

# Todo: Move these to some common header file
class pynFlags(IntFlag):
    CREATE_BONES = 1
    RENAME_BONES = 1 << 1
    ROTATE_MODEL = 1 << 2
    PRESERVE_HIERARCHY = 1 << 3
    WRITE_BODYTRI = 1 << 4
    IMPORT_SHAPES = 1 << 5
    SHARE_ARMATURE = 1 << 6
    APPLY_SKINNING = 1 << 7
    KEEP_TMP_SKEL = 1 << 8 # for debugging
    RENAME_BONES_NIFTOOLS = 1 << 9
    EXPORT_POSE = 1 << 10


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
        for inp in ['Base Color', 'Image', 'Color', 'R', 'Red']:
            if inp in n.inputs.keys() and n.inputs[inp].is_linked:
                new_n = n.inputs[inp].links[0].from_node
                break
        n = new_n
    return n


def MatrixLocRotScale(loc, rot, scale):
    """Same as Matrix.LocRotScale, For backwards compatibility."""
    try:
        return Matrix.LocRotScale(loc, rot, scale)
    except:
        tm = Matrix.Translation(loc)
        rm = Matrix()
        if issubclass(rot.__class__, Quaternion):
            rm = rot.to_matrix()
        else:
            rm = Matrix(rot)
        rm = rm.to_4x4()
        sm = Matrix(((scale[0],0,0,0),
                        (0,scale[1],0,0),
                        (0,0,scale[2],0),
                        (0,0,0,1)))
        m = tm @ rm @ sm
        return m

def transform_to_matrix(xf: TransformBuf) -> Matrix:
    """ Extends TransformBuf to get/give contents as a Blender Matrix """
    return MatrixLocRotScale(xf.translation[:], 
                             Matrix([xf.rotation[0][:],
                                     xf.rotation[1][:], 
                                     xf.rotation[2][:] ]), 
                             [xf.scale]*3)

def transform_from_matrix(buf: TransformBuf, m: Matrix):
    t, q, s, = m.decompose()
    buf.translation = t[:]
    r = q.to_matrix()
    buf.rotation = MATRIX3(r[0][:], r[1][:], r[2][:])
    buf.scale = max(s[:])

def make_transformbuf(cls, m: Matrix) -> TransformBuf:
    """ Return a new TransformBuf filled with the data in the matrix """
    buf = TransformBuf()
    transform_from_matrix(buf, m)
    return buf


def bind_position(shape:NiShape, bone: str) -> Matrix:
    """Return the bind position for a bone in a shape."""
    return transform_to_matrix(shape.get_shape_skin_to_bone(bone)).inverted()


def pose_transform(shape:NiShape, bone: str):
    """Return the pose transform for the given bone.
    
    This is the transform from pose position to bind position for a bone.
    It's the same for all bones in a nif, unless the nif has the shape in a posed
    position--changing bone positions relative to each other.
    """
    bonexf = transform_to_matrix(shape.file.nodes[bone].xform_to_global)
    sk2b = transform_to_matrix(shape.get_shape_skin_to_bone(bone))
    return (bonexf @ sk2b).inverted()