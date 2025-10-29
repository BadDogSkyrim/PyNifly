"""Common definitions for the Blender plugin"""

import os
import shutil
import tempfile
from enum import IntFlag
from mathutils import Matrix, Vector, Quaternion, Euler
from mathutils import geometry
import bpy
import bpy_types
import re
from nifdefs import *
from pynifly import *

import ctypes
from ctypes import wintypes
_GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
_GetShortPathNameW.argtypes = [wintypes.LPWSTR, wintypes.LPWSTR, wintypes.DWORD]
_GetShortPathNameW.restype = wintypes.DWORD

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
    """
    Returns the root name of an object, before Blender added '.00n' to make it unique.
    Accepts either an object or a string.
    """
    if type(obj) is str:
        s = obj
    else:
        s = obj.name
    m = name_pat.search(s)
    if m:
        return m.group(1)
    return s


def ObjectSelect(objlist, deselect=True, active=False):
    """Select all the objects in the list"""
    try:
        bpy.ops.object.mode_set(mode = 'OBJECT')
    except:
        pass
    if deselect:
        bpy.ops.object.select_all(action='DESELECT')
    if hasattr(objlist, "__iter__"):
        for o in objlist:
            try:
                o.select_set(True)
            except:
                pass
        o1 = objlist[0] if len(objlist) > 0 else None
    else:
        try:
            objlist.select_set(True)
        except:
            pass
        o1 = objlist
    if active and objlist:
        try:
            bpy.context.view_layer.objects.active = o1
        except:
            pass


def ObjectActive(obj):
    """Set the given object active"""
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def MatrixLocRotScale(loc, rot, scale=None):
    """Same as Matrix.LocRotScale, For backwards compatibility."""
    if scale == None: scale = Vector((1,1,1,))
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


def make_transformbuf(m: Matrix) -> TransformBuf:
    """ Return a new TransformBuf filled with the data in the matrix """
    buf = TransformBuf()
    transform_from_matrix(buf, m)
    return buf


def key_rotation(ti:NiTransformData, frame):
    """
    Return the rotation element at the given frame as a quaternion.
    """
    if ti.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
        f0 = [ti.xrotations[frame].value, ti.yrotations[frame].value, ti.zrotations[frame].value]
        td_rot_euler = Euler(f0, 'XYZ')
        td_rot_quat = td_rot_euler.to_quaternion()
    elif ti.properties.rotationType == NiKeyType.LINEAR_KEY:
        td_rot_quat = Quaternion(ti.qrotations[frame].value)
    return td_rot_quat


def append_if_new(theList, theVector, errorfactor):
    """ Append vector to list if not already present (to within errorfactor) """
    for a in theList:
        if VNearEqual(a, theVector, epsilon=errorfactor):
            return
    theList.append(theVector)


def orthogonal_faces(m):
    """
    Return 3 orthogonal faces of mesh m.
    Returns: (faces, opposites)
    Opposites corrospond 1:1 with faces.
    """
    faces = [m.polygons[0]] # Faces, all orthogonal to each other
    opposites = [None] # Opposing faces, 1:1

    for p in m.polygons:
        pn = p.normal
        if p not in faces and p not in opposites:
            # Only keep p if it's orthogonal to faces we have OR parallel to them.
            is_orth = True
            for i, f in enumerate(faces):
                dp = abs(f.normal.dot(pn))
                if NearEqual(dp, 1.0): 
                    # Capture opposite (parallel) faces as we go
                    opposites[i] = p
                    is_orth = False
                elif not NearEqual(dp, 0):
                    is_orth = False
                if not is_orth: break

            if is_orth:
                faces.append(p)
                opposites.append(None)

    return faces, opposites


def find_box_info(box):
    """
    Given a cube (cuboid, really), return the dimensions and transform. Cube must not be
    triangularized.
    Returns:
    center = centerpoint of box (may not match the object origin) in wolrd coordinates
    dimensions = (width, height, depth) of cube in world scale
    rotation = rotation necessary to align dimensions with box's local frame of reference
    """
    faces, opposites = orthogonal_faces(box.data)

    ctr = []
    dimv = Vector([
        (f2.center-f1.center).length for f1, f2 in zip(faces, opposites)
    ])
    # for f1, f2 in zip(faces, opposites):
    #     # Get the width/height/depth
    #     p1 = box.matrix_world @ box.data.vertices[f1.vertices[0]].co
    #     p2 = box.matrix_world @ box.data.vertices[f2.vertices[0]].co
    #     n2 = box.matrix_world @ f2.normal
    #     d = abs(geometry.distance_point_to_plane(p1, p2, n2))
    #     dimensions.append(d)

    # dimv = Vector(dimensions)
    # In an unrotated cube, the first face points along -X.
    xrot = Vector((-1, 0, 0,)).rotation_difference(faces[0].normal)
    # Second face points to +Y, so rotate around X to fix it.
    yn = faces[1].normal.copy()
    yn.rotate(xrot.inverted())
    yrot = Vector((0, 1, 0, )).rotation_difference(yn)
    # Need to return the rotation from neutral, so add the box's local rotation.
    rot = (xrot @ yrot)

    # Calculate the centerpoint 
    ctr =  box.matrix_world @ (faces[0].center + (opposites[0].center - faces[0].center)/2)

    return ctr, box.matrix_world.to_scale() * dimv, rot


def bind_position(shape:NiShape, bone: str) -> Matrix:
    """Return the bind position for a bone in a shape."""
    return transform_to_matrix(shape.get_shape_skin_to_bone(bone)).inverted()


def pose_transform(shape:NiShape, bone: str):
    """Return the pose transform for the given bone.
    
    This is the transform from pose position to bind position for a bone.
    It's the same for all bones in a nif, unless the nif has the shape in a posed
    position--changing bone positions relative to each other.
    """
    bonexf = transform_to_matrix(shape.file.nodes[bone].global_transform)
    sk2b = transform_to_matrix(shape.get_shape_skin_to_bone(bone))
    return (bonexf @ sk2b).inverted()

def arma_name(n):
    """Return the name for the armature given the name of the root node."""
    return n + ":ARMATURE"


BONE_LEN = 5
FACEBONE_LEN = 2

# Game rotations rotate the bones so they look like a skeleton. This is a convenience for
# the modder but mucks up anything that depends on those rotations: FO4 connection points, 
# QUADRATIC_KEY animation data, maybe collisions? 

# game_rotations = {'X': (Quaternion(Vector((0,0,1)),
#                         radians(-90)).to_matrix().to_4x4(), Quaternion(Vector((0,0,1)),
#                   radians(-90)).inverted().to_matrix().to_4x4()), 'Z':
#                         (Quaternion(Vector((1,0,0)), radians(90)).to_matrix().to_4x4(),
# Quaternion(Vector((1,0,0)), radians(90)).inverted().to_matrix().to_4x4())} 

# What if we don't add a rotation--just use what the nif has. Not so pretty for the user
# but arguably more correct?
game_rotations = {'X': (Matrix.Identity(4),
                        Matrix.Identity(4)),
                  'Z': (Matrix.Identity(4),
                        Matrix.Identity(4))}

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
        bone.tail = Vector((FACEBONE_LEN,0,0))
    else:
        bone.tail = Vector((BONE_LEN,0,0))

    # Direction of tail doesn't matter. It will get set by the bone_blender transform.
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


class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.max_error = 0
        self.log = None


    def __del__(self):
        if self.log:
            self.log.removeHandler(self)


    def emit(self, record):
        self.max_error = max(self.max_error, record.levelno)


    def start(self, bl_info, action, importtype):
        """
        Start logging for an operation. Return the log and its handler.
        """
        self.log = logging.getLogger("pynifly")
        self.log.addHandler(self)
        self.log.info(f"""


====================================
PYNIFLY {action} {importtype} V{bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}

""")


    def finish(self, action, files):
        if self.max_error >= logging.ERROR:
            errmsg = "WITH ERRORS"
        elif self.max_error >= logging.WARNING:
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
        

    @classmethod
    def New(cls, bl_info, action, importtype):
        lh = LogHandler()
        lh.start(bl_info, action, importtype)
        return lh


def get_short_path_name(long_name):
    """
    Gets the short path name of a given long path. Leave the filename itself untouched
    unless it has spaces.
    http://stackoverflow.com/a/23598461/200291
    """
    pname = os.path.dirname(long_name)
    bname = os.path.basename(long_name).replace(' ', '_')
    output_buf_size = len(long_name)
    while True:
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        needed = _GetShortPathNameW(pname, output_buf, output_buf_size)
        if output_buf_size >= needed:
            break
        else:
            output_buf_size = needed
    return os.path.join(output_buf.value, bname)


CAMERA_NEUTRAL = MatrixLocRotScale((0, 100, 0), Euler((-pi/2,pi,0), 'XYZ'), (1,1,1))

def cam_to_inv(mx, focal_len):
    """Given a camera object world matrix, returns an inventory marker 3-tuple:
        [x-rot, y-rot, z-rot], zoom
    """
    res = mx @ CAMERA_NEUTRAL 
    eu = res.to_euler()
    eu_out = [round((v * 1000)) % round(2000*pi) for v in eu[0:3]]
    f = ((focal_len-38)/231.79487)+1.4
    return eu_out, f

def inv_to_cam(im_rot, zoom):
    """Given an inventory marker rotation triple and zoom factor, return
    a Blender world matrix and focal length appropriate for a camera object.
    """
    focal_len = 231.79487 * (zoom-1.4) + 38 
    cammx = MatrixLocRotScale(
        (0,0,0),
        Euler([v/1000 for v in im_rot], 'XYZ'),
        (1,1,1) )
    return cammx.inverted() @ CAMERA_NEUTRAL, focal_len


def highlight_objects(objlist, context, is_callback=False):
    """
    Highlight the given objects in the viewports. Select them, make sure
    they are visible in the 3D view, make sure they are visible in the outliner.
    """
    ObjectSelect(objlist, active=True)

    context.view_layer.update()
    for a in context.screen.areas: 
        if a.type in ['OUTLINER', 'VIEW_3D']:
            for r in a.regions:
                if r.type == 'WINDOW':
                    try:
                        with context.temp_override(area=a, region=r):
                            try:
                                if a.type == 'OUTLINER':
                                    # On Blender 4, outliner.show_active doesn't work from the
                                    # import call. Let Blender set state and then repeat the
                                    # call.
                                    bpy.ops.outliner.show_active()
                                    if not is_callback:
                                        bpy.app.timers.register(highlight_selected, first_interval=0.5)
                                else:
                                    bpy.ops.view3d.view_selected()
                            except:
                                pass
                    except:
                        pass


def highlight_selected():
    highlight_objects([x for x in bpy.context.selected_objects if x.type=="MESH"], bpy.context, is_callback=True)


def color_mapping(colormap):
    """
    Determine what type of mapping scheme a color attribute uses, in a
    blender-version-independent way.
    """
    try:
        mapping_scheme = colormap.domain
    except:
        # Older
        mapping_scheme = 'CORNER'
    return mapping_scheme
    
def find_node(socket, nodetype, nodelist=None):
    """
    Find all shader nodes of the given type that feed the given socket.
    Found nodes are appended to the list passed in and it is returned.
    """
    if nodelist is None:
        nodes = []
    else:
        nodes = nodelist

    if not socket.is_linked:
        return nodes
    
    n = socket.links[0].from_node
    if n.bl_idname == nodetype:
        # This is what we're looking for. Don't look for any more behind this node.
        if n not in nodes:
            nodes.append(n)
        return nodes
    
    elif n.bl_idname == "ShaderNodeGroup":
        # Dive into the group and see if it's in there.
        gnodes = n.node_tree.nodes
        goutputs = [x for x in n.node_tree.nodes if x.bl_idname == 'NodeGroupOutput']
        if goutputs:
            find_node(goutputs[0].inputs[0], nodetype, nodelist=nodes)

    # Check the inputs for more results.
    for ns in n.inputs:
        find_node(ns, nodetype, nodelist=nodes) 
    
    return nodes


def link_to_collection(coll, obj):
    if obj.users_collection:
        c = obj.users_collection[0]
        c.objects.unlink(obj)
    coll.objects.link(obj)


class ReprObject():
    """Object that is represented in both nif and Blender"""
    def __init__(self, blender_obj=None, nifnode=None):
        self.blender_obj = blender_obj
        self.nifnode = nifnode

    @property
    def name(self):
        if self.blender_obj: return self.blender_obj.name
        return self.nifnode.name


class ReprObjectCollection():
    """Collection of represented objects. Adds dictionaries for fast lookup."""
    def __init__(self):
        self._collection = set()
        # Blender dict indexed by name
        self.blenderdict = {}
        # Need a separate dictionary for each file imported, indexed by filepath.
        self._filedict = {}

    def __len__(self):
        return len(self._collection)
    
    def __iter__(self):
        for ro in self._collection:
            yield ro


    @classmethod
    def New(cls, blender_objs=None):
        """
        Create a new ReprObjectCollection, optionally prefilled with the given blender objects.
        """
        roc = ReprObjectCollection()
        if blender_objs:
            for obj in blender_objs:
                roc.add(ReprObject(blender_obj=obj))
        return roc


    def add(self, reprobj):
        """
        Add a ReprObject to the collection. 
        """
        self._collection.add(reprobj)
        if reprobj.blender_obj:
            self.blenderdict[reprobj.blender_obj.name] = reprobj
        if reprobj.nifnode:
            fp = reprobj.nifnode.file.filepath
            if fp in self._filedict:
                d = self._filedict[fp]
            else:
                self._filedict[fp] = {}
                d = self._filedict[fp]
            d[reprobj.nifnode.id] = reprobj


    def add_pair(self, obj, nifnode):
        self.add(ReprObject(obj, nifnode))


    def find_nifnode(self, nifnode):
        fp = nifnode.file.filepath
        if fp in self._filedict:
            d = self._filedict[fp]
            if nifnode.id in d:
                return d[nifnode.id]
        return None


    def find_blend(self, blendobj):
        """
        Find a blender object in the collection.
        """
        if blendobj.name in self.blenderdict: 
            return self.blenderdict[blendobj.name]
        return None


    def find_nifname(self, nif, name):
        for reprobj in self._collection:
            if reprobj.nifnode \
                and reprobj.nifnode.file == nif \
                and reprobj.nifnode.name == name: 
                return reprobj
        return None


    def blender_objects(self):
        for ro in self._collection:
            if ro.blender_obj:
                yield ro.blender_obj
    

def action_fcurves(action):
    """Generator to yield all fcurves in an action."""
    for lay in action.layers:
        for strip in lay.strips:
            for cb in strip.channelbags:
                for fc in cb.fcurves:
                    yield fc

    
def TEST_CAM():
    print('TEST_CAM')
    # Camera at [0, 100, 0] pointed back at origin. This is the default position. 
    # Camera is behind Suzanne. 
    mx = Matrix((
            (-1.0000,  0.0000, 0.0000,   0.0000),
            ( 0.0000, -0.0000, 1.0000, 100.0000),
            ( 0.0000,  1.0000, 0.0000,   0.0000),
            ( 0.0000,  0.0000, 0.0000,   1.0000) ))
    inv, z = cam_to_inv(mx, 38) 
    assert inv == [0, 0, 0], f"Cam at default position: {inv}"

    # Camera at [0, -100, 0], pointed at origin. This puts the cam on the other side.
    # Camera pointed at Suzanne's face.
    mx = Matrix((
            ( 1.0000, -0.0000,  0.0000,  0),
            (-0.0000, -0.0000, -1.0000, -100),
            ( 0.0000,  1.0000, -0.0000,  0),
            ( 0.0000,  0.0000,  0.0000,  1.0000)))
    inv, z = cam_to_inv(mx, 38)
    assert VNearEqual(inv, [0, 0, 3142], epsilon=2), f"Cam on opposite side of model: {inv}"

    # Camera on negative X axis, pointed at origin. Shows Suzanne looking to the right.
    mx = Matrix((
            ( 0.0000, 0.0000, -1.0000, -100.0000),
            (-1.0000, 0.0000, -0.0000,   -0.0000),
            ( 0.0000, 1.0000,  0.0000,    0.0000),
            ( 0.0000, 0.0000,  0.0000,    1.0000)))
    inv, z = cam_to_inv(mx, 38)
    assert VNearEqual(inv, [0, 0, 1570], epsilon=2), f"Cam shows right profile: {inv}"


if __name__ == "__main__":
    print("------------RUNNING TESTS--------------")
    TEST_CAM()
    print("------------TESTS COMPLETE-------------")