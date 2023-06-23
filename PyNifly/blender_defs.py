"""Common definitions for the Blender plugin"""

from enum import IntFlag
from mathutils import Matrix, Vector, Quaternion, geometry
import bpy
import bpy_types
import re
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

name_pat = re.compile('(.+)\.\d\d\d')

def nonunique_name(obj):
    m = name_pat.search(obj.name)
    if m:
        return m.group(1)
    return obj.name


def ObjectSelect(objlist, deselect=True, active=False):
    """Select all the objects in the list"""
    try:
        bpy.ops.object.mode_set(mode = 'OBJECT')
    except:
        pass
    if deselect:
        bpy.ops.object.select_all(action='DESELECT')
    for o in objlist:
        o.select_set(True)
    if active:
        bpy.context.view_layer.objects.active = objlist[0]


def ObjectActive(obj):
    """Set the given object active"""
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


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

def arma_name(n):
    """Return the name for the armature given the name of the root node."""
    return "ARMA." + n


BONE_LEN = 5
FACEBONE_LEN = 2

game_rotations = {'X': (Quaternion(Vector((0,0,1)), radians(-90)).to_matrix().to_4x4(),
                        Quaternion(Vector((0,0,1)), radians(-90)).inverted().to_matrix().to_4x4()),
                  'Z': (Quaternion(Vector((1,0,0)), radians(90)).to_matrix().to_4x4(),
                        Quaternion(Vector((1,0,0)), radians(90)).inverted().to_matrix().to_4x4())}
bone_vectors = {'X': Vector((1,0,0)), 'Z': Vector((0,0,1))}
game_axes = {'FO3': 'X', 'FO4': 'X', 'FO76': 'X', 'SKYRIM': 'Z', 'SKYRIMSE': 'Z'}


def is_facebone(bname):
    return bname.startswith("skin_bone_")


def get_bone_blender_xf(node_xf: Matrix, game: str, scale_factor):
    """Take the given bone transform and add in the transform for a blender bone"""
    return Matrix.Scale(scale_factor, 4) @ node_xf @ game_rotations[game_axes[game]][0]
    #return apply_scale_transl(node_xf @ game_rotations[game_axes[game]][0], scale_factor)


def create_bone(armdata, bone_name, node_xf:Matrix, game:str, scale_factor, roll):
    """Creates a bone in the armature with the given transform.
    Must be in edit mode.
        armdata = data block for armature
        node_xf = bone transform (4x4 Matrix) - this is bind position
        game = game we are making the bone for
        is_fb = is a facebone (we make them shorter)
        scale_factor = scale factor to apply
    """
    bone = armdata.edit_bones.new(bone_name)
    bone.head = Vector((0,0,0))
    if is_facebone(bone_name):
        v = Vector((FACEBONE_LEN, 0, 0))
    else:
        v = Vector((0, 0, BONE_LEN))
    bone.tail = bone.head + v

    bone.matrix = get_bone_blender_xf(node_xf, game, scale_factor)
    bone.roll += roll

    return bone


def is_facebones(bone_names):
    """Determine whether the list of bone names indicates a facebones skeleton"""
    #return (fo4FaceDict.matches(set(list(arma.data.bones.keys()))) > 20)
    return  len([x for x in bone_names if x.startswith('skin_bone_')]) > 5


def find_armatures(obj):
    """Find armatures associated with obj. 
    Returns (regular armature, facebones armature)
    Only returns the first regular amature it finds--there might be more than one.
    Looks at armature modfiers and also at the parent.
    """
    arma = None
    fb_arma = None
    for skel in [m.object for m in obj.modifiers if m.type == "ARMATURE"]:
        if skel:
            if is_facebones(skel.data.bones.keys()):
                fb_arma = skel
            else:
                if not arma:
                    arma = skel

    if obj.parent and obj.parent.type == "ARMATURE":
        if is_facebones(obj.parent.data.bones.keys()):
            if fb_arma == None:
                fb_arma = obj.parent
        else:
            if arma == None:
                arma = obj.parent

    return arma, fb_arma


def get_export_objects(ctxt:bpy_types.Context) -> list:
    """Collect list of objects to export from the given context. 
    
    * Any selected object is exported
    * Any armatures referenced in an armature modifier of a selected object is
        exported;
    * If an armature is selected all its children are exported.

    We don't add the active object because it's too confusing to have it be
    exported when it's not selected. But if it is selected, it goes first.
    """

    # Doing this at the ImportNif level so why do it here? 
    return ctxt.selected_objects

    # export_objects = []
    # for obj in ctxt.selected_objects:
    #     if obj not in export_objects:
    #         par = obj.parent
    #         gpar = par.parent if par else None
    #         gparname = gpar.name if gpar else ''
    #         if not gparname.startswith('bhkCollisionObject'): 
    #             #log.debug(f"Adding {obj.name} to export objects")
    #             if obj == ctxt.object:
    #                 export_objects.insert(0, obj)
    #             else:
    #                 export_objects.append(obj) 
    #             if obj.type == 'ARMATURE':
    #                 for child in obj.children:
    #                     if child not in export_objects: export_objects.append(child)
    #             else:
    #                 arma, fb_arma = find_armatures(obj)
    #                 if arma:
    #                     export_objects.append(arma)
    #                 if fb_arma:
    #                     export_objects.append(fb_arma)

    # return export_objects


def LogStart(bl_info, action, importtype):
    log.info(f"""


====================================
PYNIFLY {action} {importtype} V{bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}

""")

def LogFinish(action, files, status, is_exception=False):
    if is_exception:
        errmsg = "WITH ERRORS"
    elif 'WARNING' in status:
        errmsg = "WITH WARNINGS"
    else:
        errmsg = "SUCCESSFULLY"

    if type(files) == str:
        fn = os.path.basename(files)
    else:
        s = set()
        for f in files:
            try:
                if type(f) == str:
                    s.add(os.path.basename(f))
                else:
                    s.add(f.name)
            except:
                pass
        fn = str(s)

    log.info(f"""

PyNifly {action} of {fn} completed {errmsg} 
====================================

""")

