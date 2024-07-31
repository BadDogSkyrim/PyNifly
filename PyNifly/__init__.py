"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (4, 0, 0),
    "version": (15, 0, 0),   
    "location": "File > Import-Export",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

# System libraries
import sys
import os
import os.path
import logging
import traceback
import subprocess
import xml.etree.ElementTree as xml
from mathutils import Matrix, Vector, Quaternion, Euler, geometry, Color
import codecs
import importlib

# Locate the DLL and other files we need either in their development or install locations.
nifly_path = None
hkxcmd_path = None
pynifly_dev_root = None
pynifly_dev_path = None
asset_path = None

if 'PYNIFLY_DEV_ROOT' in os.environ:
    pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
    pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")
    nifly_path = os.path.join(pynifly_dev_root, r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll")
    hkxcmd_path = os.path.join(pynifly_dev_path, "hkxcmd.exe")
    asset_path = os.path.join(pynifly_dev_path, "blender_assets")

if nifly_path and os.path.exists(nifly_path):
    if pynifly_dev_path not in sys.path:
        sys.path.insert(0, pynifly_dev_path)
else:
    # Load from install location
    py_addon_path = os.path.dirname(os.path.realpath(__file__))
    #log.debug(f"PyNifly addon path: {py_addon_path}")
    if py_addon_path not in sys.path:
        sys.path.append(py_addon_path)
    nifly_path = os.path.join(py_addon_path, "NiflyDLL.dll")
    hkxcmd_path = os.path.join(py_addon_path, "hkxcmd.exe")
    asset_path = os.path.join(py_addon_path, "blender_assets")

# Pynifly tools
from niflytools import *
from nifdefs import *
from pynifly import *
from trihandler import *
import xmltools

# Blender libraries
import bpy
import bpy_types
from bpy.props import (
        BoolProperty,
        CollectionProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper)
import bmesh

# Blender Export/Import components
from blender_defs import *
import shader_io 
import controller 
import skeleton_hkx

if 'PYNIFLY_DEV_ROOT' in os.environ:
    importlib.reload(skeleton_hkx)
    importlib.reload(shader_io)
    importlib.reload(xmltools)

NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"
ALPHA_MAP_NAME = "VERTEX_ALPHA"

CONNECT_POINT_SCALE = 1.0

COLLISION_COLOR = (0.559, 0.624, 1.0, 0.5) # Default color
COLLISION_COLOR_MAP = {'bhkRigidBody': (0.0, 0.8, 0.2, 0.3),
                       'bhkRigidBodyT': (0, 1.0, 0, 0.3),
                       'bhkSimpleShapePhantom': (0.8, 0.8, 0, 0.3),}
collision_names = ["bhkBoxShape", "bhkConvexVerticesShape", "bhkListShape", 
                   "bhkConvexTransformShape", "bhkCapsuleShape",
                   "bhkSphereShape",
                   "bhkRigidBodyT", "bhkRigidBody", "bhkCollisionObject"]

collision_active_layers = [
    SkyrimCollisionLayer.CLUTTER, SkyrimCollisionLayer.WEAPON,
    SkyrimCollisionLayer.PROJECTILE, SkyrimCollisionLayer.TREES,
    SkyrimCollisionLayer.DEBRIS_LARGE, SkyrimCollisionLayer.DEBRIS_SMALL]
    

ARMATURE_BONE_GROUPS = ['NPC', 'CME']

CAMERA_LENS = 80


# Default values for import/export options
APPLY_SKINNING_DEF = True
BLENDER_XF_DEF = False
CHARGEN_EXT_DEF = "chargen"
CREATE_BONES_DEF = True
EXPORT_MODIFIERS_DEF = False
EXPORT_COLORS_DEF = True
EXPORT_POSE_DEF = False
IMPORT_ANIMS_DEF = True
IMPORT_COLLISIONS_DEF = True
IMPORT_SHAPES_DEF = True
IMPORT_TRIS_DEF = False
IMPORT_POSE_DEF = False
ESTIMATE_OFFSET_DEF = True
PRESERVE_HIERARCHY_DEF = False
RENAME_BONES_DEF = True
RENAME_BONES_NIFT_DEF = False
ROLL_BONES_NIFT_DEF = False
SCALE_DEF = 1.0
WRITE_BODYTRI_DEF = False

blender_import_xf = MatrixLocRotScale(Vector((0,0,0)),
                                      Quaternion(Vector((0,0,1)), pi),
                                      (0.1, 0.1, 0.1))
blender_export_xf = blender_import_xf.inverted()

fo4_bodypart_xf = MatrixLocRotScale(Vector((0, -0.9342, 120.841,)),
                                    Quaternion(),
                                    (1, 1, 1,))

NISHAPE_IGNORE = ["bufSize", 
                  'bufType',
                  "nameID", 
                  "controllerID", 
                  "extraDataCount", 
                  "transform",
                  "propertyCount",
                  "collisionID",
                  "hasVertices", 
                  "hasNormals", 
                  "hasVertexColors",
                  "hasUV", 
                  "boundingSphereCenter",
                  "boundingSphereRadius",
                  "vertexCount",
                  "triangleCount", 
                  "skinInstanceID",
                  "shaderPropertyID", 
                  "alphaPropertyID", 
                  ]

COLLISION_BODY_IGNORE = ['rotation', 'translation', 'guard', 'unusedByte1', 
                            'unusedInts1_0', 'unusedInts1_1', 'unusedInts1_2',
                            'unusedBytes2_0', 'unusedBytes2_1', 'unusedBytes2_2',
                            'bhkRadius', 'linearDamping', 'angularDamping',
                            'friction', 'mass']
    

BOX_SHAPE_IGNORE = ['bhkDimensions']
CAPSULE_SHAPE_IGNORE = ['point1', 'point2']

# --------- Helper functions -------------

def LogIf(condition, text):
    if condition:
        log.debug(text)


def is_in_plane(plane, vert):
    """ Test whether vert is in the plane defined by the three vectors in plane """
    #find the plane's normal. p0, p1, and p2 are simply points on the plane (in world space)
 
    # Get vector normal to plane
    v1 = plane[0] - plane[1]
    v2 = plane[2] - plane[1]
    normal = v1.cross(v2)
    normal.normalize()

    # Get vector from vertex to a point on the plane
    t = vert - plane[0]
    t.normalize()

    # If the dot product is 0, point is on plane
    dp = normal.dot(t)

    return round(dp, 4) == 0.0


def append_if_new(theList, theVector, errorfactor):
    """ Append vector to list if not already present (to within errorfactor) """
    for a in theList:
        if VNearEqual(a, theVector, epsilon=errorfactor):
            return
    theList.append(theVector)


def apply_scale_xf(xf:Matrix, sf:float):
    """Apply the scale factor sf to the matrix but NOT to the scale component of the matrix.
    When importing with a scale factor, verts and other elements are scaled already by the scale factor
    so it doesn't need to be part of the transform as well.
    """
    loc, rot, scale = (xf * sf).decompose()
    return MatrixLocRotScale(loc, rot, xf.to_scale())


def apply_scale_transl(xf:Matrix, sf:float) -> Matrix:
    """Apply the scale factor sf to the translation component of the matrix only."""
    loc, rot, scale = xf.decompose()
    return MatrixLocRotScale(loc*sf, rot, scale)


def pack_xf_to_buf(xf, scale_factor: float):
    """Pack a transform to a TransformBuf, applying a scale fator to translation"""
    xf_loc, xf_rot, xf_scale = xf.decompose()
    tb = TransformBuf()
    tb.store(xf_loc/scale_factor, xf_rot.to_matrix(), xf_scale)
    return tb


def armatures_match(a, b):
    """Returns true if all bones of the first armature have the same position in the second"""
    bpy.ops.object.mode_set(mode = 'OBJECT')
    #log.debug(f"<armatures_match> comparing {a.name} with {b.name}")
    for bone in a.data.bones:
        if bone.name in b.data.bones:
            if not MatNearEqual(bone.matrix_local, b.data.bones[bone.name].matrix_local):
                #log.debug(f"Bone {bone.name} positions do not match {a.name} vs {b.name}: \n{bone.matrix_local}!=\n{b.data.bones[bone.name].matrix_local}")
                return False
            elif not MatNearEqual(a.pose.bones[bone.name].matrix, b.pose.bones[bone.name].matrix):
                #log.debug(f"Bone {bone.name} pose positions do not match {a.name} vs {b.name}: \n{a.pose.bones[bone.name].matrix}!=\n{b.pose.bones[bone.name].matrix}")
                return False
            else:
                pass
        else:
            pass
    return True


# ------ Bone handling ------

ROLL_ADJUST = 0 # -90 * pi / 180

def get_pose_blender_xf(node_xf: Matrix, game: str, scale_factor):
    """Take the given bone transform and add in the transform for a blender bone"""
    return apply_scale_transl(node_xf, scale_factor) @ game_rotations[game_axes[game]][0]


def get_bone_global_xf(arma, bone_name, game:str, use_pose) -> Matrix:
    """ Return the global transform represented by the bone. """
    # Scale applied at this level on import, but by callor on export. Should be here for
    # cosistency? 
    # TODO -- CHECK this fix, apply everyWHERE
    if use_pose:
        bmx = arma.pose.bones[bone_name].matrix @ game_rotations[game_axes[game]][1]
    else:
        bmx = arma.data.bones[bone_name].matrix_local @ game_rotations[game_axes[game]][1]
    return bmx

def get_bone_xform(arma, bone_name, game, preserve_hierarchy, use_pose) -> Matrix:
    """Return the local or global transform represented by the bone"""
    bonexf = get_bone_global_xf(arma, bone_name, game, use_pose)

    if preserve_hierarchy:
        bparent = arma.data.bones[bone_name].parent
        if bparent:
            # Calculate the relative transform from the parent
            parent_xf = get_bone_global_xf(arma, bparent.name, game, use_pose)
            loc_xf = parent_xf.inverted() @ bonexf

            return loc_xf

    return bonexf


# ######################################################################## ###
#                                                                          ###
# -------------------------------- IMPORT -------------------------------- ###
#                                                                          ###
# ######################################################################## ###

# -----------------------------  MESH CREATION -------------------------------

def mesh_create_normals(the_mesh, normals):
    """ Create custom normals in Blender to match those on the object 
        normals = [(x, y, z)... ] 1:1 with mesh verts
        """
    if normals:
        # Make sure the normals are unit length
        # Magic incantation to set custom normals
        try:
            the_mesh.use_auto_smooth = True
        except:
            pass
        the_mesh.normals_split_custom_set([(0, 0, 0)] * len(the_mesh.loops))
        the_mesh.normals_split_custom_set_from_vertices([Vector(v).normalized() for v in normals])


def mesh_create_uv(the_mesh, uv_points):
    """ Create UV in Blender to match UVpoints from Nif
        uv_points = [(u, v)...] indexed by vertex index
        """
    new_uv = [(0,0)] * len(the_mesh.loops)
    for lp_idx, lp in enumerate(the_mesh.loops):
        vert_targeted = lp.vertex_index
        new_uv[lp_idx] = (uv_points[vert_targeted][0], 1-uv_points[vert_targeted][1])
    new_uvlayer = the_mesh.uv_layers.new(do_init=False)
    for i, this_uv in enumerate(new_uv):
        new_uvlayer.data[i].uv = this_uv

def mesh_create_partition_groups(the_shape, the_object):
    """ Create groups to capture partitions """
    mesh = the_object.data
    vg = the_object.vertex_groups
    partn_groups = []
    for p in the_shape.partitions:
        new_vg = vg.new(name=p.name)
        partn_groups.append(new_vg)
        try:
            # Walk through subsegments, if any. Skyrim doesn't have them.
            for sseg in p.subsegments:
                new_vg = vg.new(name=sseg.name)
                partn_groups.append(new_vg)
        except:
            pass
    for part_idx, face in zip(the_shape.partition_tris, mesh.polygons):
        if part_idx < len(partn_groups):
            this_vg = partn_groups[part_idx]
            for lp in face.loop_indices:
                this_loop = mesh.loops[lp]
                this_vg.add((this_loop.vertex_index,), 1.0, 'ADD')
    if len(the_shape.segment_file) > 0:
        #log.debug(f"..Putting segment file '{the_shape.segment_file}' on '{the_object.name}'")
        the_object['FO4_SEGMENT_FILE'] = the_shape.segment_file


def import_colors(mesh:bpy_types.Mesh, shape:NiShape):
    try:
        if shape.shader.shaderflags2_test(ShaderFlags2.VERTEX_COLORS) \
            and shape.colors and len(shape.colors) > 0:
            clayer = None
            try: #Post V3.5
                clayer = mesh.color_attributes.new(type='BYTE_COLOR', domain='CORNER')
            except:
                clayer = mesh.vertex_colors.new()
            alphlayer = None
            if ((shape.shader.Shader_Flags_1 & ShaderFlags1.VERTEX_ALPHA) 
                or (shape.file.game == 'FO4')):
                # FO4 appears to combine vertex alpha with vertex color, so always provide alpha.
                # or ((shape.shader_block_name == 'BSEffectShaderProperty' and shape.file.game == 'FO4'))
                # If we have a BSEffectShaderProperty in FO4 we assume the alpha channel
                # is used whether or not VERTEX_ALPHA is set. Some FO4 meshes seem to work
                # this way. 
                try:
                    alphlayer = mesh.color_attributes.new(
                        name=ALPHA_MAP_NAME, type='BYTE_COLOR', domain='CORNER')
                except:
                    alphlayer = mesh.vertex_colors.new()
                alphlayer.name = ALPHA_MAP_NAME
        
            colors = shape.colors
            for lp in mesh.loops:
                c = colors[lp.vertex_index]
                clayer.data[lp.index].color = (c[0], c[1], c[2], 1.0)
                if alphlayer:
                    alph = colors[lp.vertex_index][3]
                    alphlayer.data[lp.index].color = [alph, alph, alph, 1.0]
    except:
        log.error(f"ERROR: Could not read colors on shape {shape.name}")


def create_capsule(pt1, pt2, desired_radius):
    """
    Create a capsule shape.
    pt1, pt2 = endpoints. These are the the centerpoints of the caps.
    """
    desired_len = (pt2-pt1).length + 2*desired_radius
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=12, ring_count=7, enter_editmode=True, 
        align='WORLD', location=(0, 0, 0), 
        scale=(desired_radius, desired_radius, desired_radius))
     
    if desired_len >= 2*desired_radius:
        # Select verts above the origin
        bpy.ops.mesh.select_mode(type='VERT')
        # bpy.ops.transform.translate(value=(0, 0, desired_radius))
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for v in bpy.context.object.data.vertices:
            v.select = (v.co.z > 0)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.transform.translate(value=(0, 0, desired_len-2*desired_radius))
    else:
        # More of a disc than a pill
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.transform.resize(value=(1, 1, desired_len/(2*desired_radius)))

    bpy.ops.object.mode_set(mode='OBJECT')
    obj = bpy.context.object
    objtip = Vector((0, 0, desired_len))
    pt2_relative = pt2-pt1
    pt2_rot = Vector((0, 0, 1)).rotation_difference(pt2_relative)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = pt2_rot
    obj.location = pt1

    bpy.ops.object.transform_apply()

    return bpy.context.object


def find_capsule_ends(obj):
    """
    Find the ends of the given capsule in local coordinates. Must have been created with
    UV spheres making the ends.
    Returns (point1, point2, radius), where the points are the centers of the opposite caps.
    """
    ObjectSelect([obj], active=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    # Get the tips of the caps
    verts = []
    for v in bm.verts:
        if len(v.link_edges) > 4:
            verts.append(Vector(v.co[:]))

    # get the radius.
    r = 0
    centerline = verts[1] - verts[0]
    centerpoint = (centerline)/2 + verts[0]
    # Find the verts closest to the centerpoint in the positive direction. 
    vertdist = []
    mindist = math.inf
    for v in obj.data.vertices:
        dist = geometry.distance_point_to_plane(
            v.co, centerpoint, centerline
        )
        if dist >= -0.001:
            vertdist.append((v, dist,))
            mindist = min(dist, mindist)
    closeverts = [v for v, d in vertdist if d == mindist]

    # Assume these points form a ring around the centerline. Find the max distance.
    if len(closeverts) > 1:
        maxdist = 0
        for v in closeverts[1:]:
            maxdist = max(maxdist, (v.co-closeverts[0].co).length)
        r = maxdist/2

    relvec = centerline.normalized()
    relvec = relvec*r
    p1 = verts[1] - relvec 
    p2 = verts[0] + relvec 

    bpy.ops.object.mode_set(mode='OBJECT')
    return p1, p2, r


class NifImporter():
    """Does the work of importing a nif, independent of Blender's operator interface.
    filename can be a single filepath string or a list of filepaths
    """
    def __init__(self, filename, chargen="chargen", scale=1.0):

        #log.debug(f"Importing {filename} with flags {f}")
        if type(filename) == str:
            self.filename = filename
            self.filename_list = [filename]
        else:
            self.filename = filename[0]
            self.filename_list = filename

        self.context = bpy.context # can be overwritten
        self.collection = None
        self.do_create_bones = CREATE_BONES_DEF
        self.do_rename_bones = RENAME_BONES_DEF
        self.do_import_anims = IMPORT_ANIMS_DEF
        self.rename_bones_nift = RENAME_BONES_NIFT_DEF
        self.roll_bones_nift = ROLL_BONES_NIFT_DEF
        self.do_import_shapes = IMPORT_SHAPES_DEF
        self.do_import_tris = IMPORT_TRIS_DEF
        self.do_apply_skinning = APPLY_SKINNING_DEF
        self.do_import_pose = IMPORT_POSE_DEF
        self.is_facegen = False
        # self.do_estimate_offset = ESTIMATE_OFFSET_DEF
        self.reference_skel = None
        self.chargen_ext = chargen
        self.mesh_only = False
        self.armature = None
        self.imported_armatures = []
        self.is_new_armature = True # Armature is derived from current nif; set false if adding to existing arma
        self.created_child_cp = None
        self.bones = set()
        self.objects_created = {} # Dictionary of objects created, indexed by node handle
                                  # (or object name, if no handle)
        self.nodes_loaded = {} # Dictionary of nodes from the nif file loaded, indexed by Blender name
        self.loaded_meshes = [] # Holds blender objects created from shapes in a nif
        self.nif = None # NifFile(filename)
        self.loc = Vector((0, 0, 0))   # location for new objects 
        self.scale = scale
        self.warnings = []
        self.import_xf = Matrix.Identity(4) # Transform applied to root for blender convenience.
        self.root_object = None  # Blender representation of root object
        self.connect_parents = []
        self.auxbones = False
        self.ref_compat = False


    def __str__(self):
        flags = []
        if self.do_create_bones: flags.append("CREATE_BONES")
        if self.do_rename_bones: flags.append("RENAME_BONES")
        if self.do_import_anims: flags.append("IMPORT_ANIMS")
        if self.rename_bones_nift: flags.append("RENAME_BONES_NIFT")
        if self.roll_bones_nift: flags.append("ROLL_BONES_NIFT")
        if self.do_import_shapes: flags.append("IMPORT_SHAPES")
        if self.do_import_tris: flags.append("IMPORT_TRIS")
        if self.do_apply_skinning: flags.append("APPLY_SKINNING")
        if self.do_import_pose: flags.append("IMPORT_POSE")
        if self.is_facegen: flags.append("FACEGEN_FILE")
        # if self.do_estimate_offset: flags.append("ESTIMATE_OFFSET")
        return f"""
        Importing nif: {self.filename_list}
            flags: {'|'.join(flags)}
            armature: {self.armature} 
            connect point parents: {list(self.loaded_parent_cp.keys())}
            mesh objects: {[obj.name for obj in self.loaded_meshes]}
        """

        
    def warn(self, text:str):
        self.warnings.append(('WARNING', text))
        log.warning(text)

    def incr_loc(self):
        self.loc = self.loc + (Vector((.5, .5, .5)) * self.scale) 

    def next_loc(self):
        l = self.loc
        self.incr_loc()
        return l
    
    @property
    def import_scale(self):
        """Return the scale factor being used on the import.
        Only looks at the x-value because they're all the same.
        Useful for havoc values that are stored as properties. 
        """
        return self.import_xf.to_scale()[0]

    def nif_name(self, blender_name):
        if self.do_rename_bones or self.rename_bones_nift:
            return self.nif.nif_name(blender_name)
        else:
            return blender_name
        
    def blender_name(self, nif_name):
        if self.is_facegen and nif_name == "Head":
            # Facegen nifs use a "Head" bone, which appears to be the "HEAD" bone misnamed.
            return "HEAD"  
        elif self.do_rename_bones or self.rename_bones_nift:
            return self.nif.blender_name(nif_name)
        else:
            return nif_name

    def calc_obj_transform(self, the_shape:NiShape, scale_factor=1.0) -> Matrix:
        """
        Returns location of the_shape ready for blender as a transform.

        If the shape isn't skinned, this is just the transform on the shape. 
        
        If the shape is skinned, return the overall shape transform to use. When there's
        no global-to-skin transform (FO4), calculate that by averaging the transform of
        all the bones. If there is a global-to-skin transform, combine the transform on
        the base shape, the global-to-skin transform, and the average of the bone
        transforms. All these elements have to be taken into account.

        scale_factor is applied to the transform but not to its scale component --
        scale_factor is used to transform vert locations so it's not needed on the
        transform.
        """
        if not hasattr(the_shape, "has_skin_instance") or not the_shape.has_skin_instance:
            # Statics get transformed according to the shape's transform
            return apply_scale_xf(transform_to_matrix(the_shape.transform), scale_factor)

        # Global-to-skin transform is what offsets all the vertices together, e.g. so that
        # heads can be positioned at the origin. Put the reverse transform on the blender 
        # object so they can be worked on in their skinned position.
        # Use the one on the NiSkinData if it exists.
        #xform = the_shape.global_to_skin_data
        #if True: #xform is None:
        xf = Matrix.Identity(4)
        offset_consistent = False
        expected_variation = 0.8 if "SKYRIM" in self.nif.game else 3

        # If there's a global-to-skin transform, combine it with the shape's own transform
        # and use that with the transform implied in the bones. If there's no
        # global-to-skin, the only transform that applies is the one in the bones.
        xform_shape = transform_to_matrix(the_shape.transform)
        xform_calc = transform_to_matrix(the_shape.calc_global_to_skin()) 
        if the_shape.has_global_to_skin:
            # The global-to-skin doesn't stand alone. It has to be combined with the
            # shape's transform and the transform from the bind positions. E.g. the
            # Argonian head has a null global-to-skin and uses the bone transforms to lift
            # itself into place. 
            xform = transform_to_matrix(the_shape.global_to_skin)
            xf = (xform_shape @ xform @ xform_calc).inverted()
        else:
            xf = xform_calc.inverted()
            
        offset_consistent = True
        # if the_shape.has_global_to_skin:
        #     # if this transform exists, use it and don't muck with it.
        #     xform = the_shape.global_to_skin
        #     xf = transform_to_matrix(xform).inverted()
        #     offset_consistent = True
        
        ### All of this is unreachable now.
        offset_xf = None
        if not offset_consistent and  offset_xf == None and self.armature:
            # If we already imported from this nif, check the offset from the shape to the
            # armature we've created. If it's consistent, we just apply that offset.
            for i, bn in enumerate(the_shape.get_used_bones()):
                bnref = bn
                if self.is_facegen and bn == "Head": 
                    bnref = "HEAD"
                if bnref in self.armature.data.bones:
                    skel_bone = self.armature.data.bones[bnref]
                    skel_bone_xf= skel_bone.matrix_local
                    bindpos = bind_position(the_shape, bn)
                    bindinshape = xf @ bindpos
                    this_offset = skel_bone_xf @ bindinshape.inverted()
                    
                    if not offset_xf: 
                        offset_xf = this_offset
                        offset_consistent = True
                    
                    # If the transforms are close, create an average. That's because
                    # there's often some variation, whether it's rounding errors or some
                    # other reason. We need epsilon as large as it is to cover all the
                    # nifs we see, especially nifs with multiple meshes that came from
                    # different sources.
                    elif MatNearEqual(this_offset, offset_xf, epsilon=expected_variation):
                        offset_xf = offset_xf.lerp(this_offset, 1/i)
                    
                    # If transforms are way off, either something's wrong, like we're
                    # trying to use an inappropriate reference skeleton, or it's FO4. FO4
                    # is just weird. Inform the user and don't use this for the average.
                    else:
                        offset_consistent = False
                        log.warn(f"Shape {the_shape.name} does not have consitent offset from nif armature--can't use it to extend the armature.")
                        self.do_create_bones = False
                        break

            if offset_consistent and offset_xf:
                # If the offset is close to the standard FO4 bodypart offset, normalize it 
                # so all bodyparts are consistent.
                if self.nif.game == 'FO4' and  MatNearEqual(offset_xf, fo4_bodypart_xf, epsilon=3):
                    xf = xf @ fo4_bodypart_xf
                else:
                    xf = xf @ offset_xf

        if not offset_consistent and offset_xf == None and self.reference_skel:
            # If we're creating missing vanilla bones, we need to know the offset from the
            # bind positions here to the vanilla bind positions, and we need it to be
            # consistent.
            for i, bn in enumerate(the_shape.get_used_bones()):
                bnref = bn
                if self.is_facegen and bn == "Head": 
                    bnref = "HEAD"
                if bnref in self.reference_skel.nodes:
                    skel_bone = self.reference_skel.nodes[bnref]
                    skel_bone_xf= transform_to_matrix(skel_bone.global_transform)
                    bindpos = bind_position(the_shape, bn)
                    bindinshape = xf @ bindpos
                    this_offset = skel_bone_xf @ bindinshape.inverted()
                    
                    if not offset_xf: 
                        offset_xf = this_offset
                        offset_consistent = True
                    
                    # If the transforms are close, create an average. That's because
                    # there's often some variation, whether it's rounding errors or some
                    # other reason. We need epsilon as large as it is to cover all the
                    # nifs we see, especially nifs with multiple meshes that came from
                    # different sources.
                    elif MatNearEqual(this_offset, offset_xf, epsilon=expected_variation):
                        offset_xf = offset_xf.lerp(this_offset, 1/i)
                    
                    # If transforms are way off, either something's wrong, like we're
                    # trying to use an inappropriate reference skeleton, or it's FO4. FO4
                    # is just weird. Inform the user and don't use this for the average.
                    else:
                        offset_consistent = False
                        log.warn(f"Shape {the_shape.name} does not have consitent offset from reference skeleton {self.reference_skel.filepath}--can't use it to extend the armature.")
                        self.do_create_bones = False
                        break

            if offset_consistent and offset_xf:
                # If the offset is close to the standard FO4 bodypart offset, normalize it 
                # so all bodyparts are consistent.
                if self.nif.game == 'FO4' and  MatNearEqual(offset_xf, fo4_bodypart_xf, epsilon=3):
                    xf = xf @ fo4_bodypart_xf
                else:
                    xf = xf @ offset_xf

        if not offset_consistent: 
            # If there's no global to skin (FO4) and we haven't found consistent bind
            # offsets, maybe the pose offsets will give us a skin transform. If they are
            # all the same they represent a simple reposition of the entire shape. We can
            # put the inverse on the Blender shape.
            pose_xf = None
            same = True
            for b in the_shape.get_used_bones():
                bone_xf = pose_transform(the_shape, b)
                if pose_xf:
                    # Some common nifs such as the Bodytalk male body need some extra
                    # fudge factor. Reducing epsilon here will result in their shape not
                    # getting adjusted to the armature location. 
                    if not MatNearEqual(pose_xf, bone_xf, epsilon=0.5):
                        #log.debug(f"Pose transform not consistent in {the_shape.name} with bone {b}:\n{pose_xf}\n!=\n{bone_xf}")
                        same = False
                        break
                else:
                    pose_xf = bone_xf
            if same: 
                # If the offset is close to the standard FO4 bodypart offset, normalize it 
                # so all bodyparts are consistent.
                bpi = fo4_bodypart_xf.inverted()
                if self.nif.game == 'FO4' and  MatNearEqual(pose_xf, bpi, epsilon=3):
                    xf = xf @ bpi
                else:
                    xf = xf @ pose_xf
                xf.invert()

        #log.debug(f"Shape {the_shape.name} has calculated transform {xf.translation}")
        return apply_scale_xf(xf, scale_factor)


    # -----------------------------  EXTRA DATA  -------------------------------

    def add_to_parents(self, obj):
        """Add the given object to our list of parent connect points loaded in this operation.
        obj must be a valid BSConnectPointParents object. """
        connectname = obj.name[len('BSConnectPointParents::P-'):]
        self.loaded_parent_cp[connectname] = obj


    def add_to_child_cp(self, obj):
        """Add the given object to our list of children connect points loaded in this operation.
        obj must be a valid BSConnectPointChildren object. """
        for i in range(100):
            try:
                n = obj[f"PYN_CONNECT_CHILD_{i}"]
            except:
                break
            connectname = n[2:]
            self.loaded_child_cp[connectname] = obj


    def import_bsx(self, node, parent_obj):
        b = node.bsx_flags
        if b:
            bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSXFlags"
            ed.show_name = True
            ed.empty_display_type = 'SPHERE'
            ed['BSXFlags_Name'] = b[0]
            ed['BSXFlags_Value'] = BSXFlags(b[1]).fullname
            ed.parent = parent_obj
            # extradata.append(ed)
            self.objects_created[ed.name] = ed


    def import_inventory_marker(self, node, parent_obj):
        invm = node.inventory_marker
        if invm:
            bpy.ops.object.add(type='CAMERA', 
                               location=[0, 100, 0],
                               rotation=[-pi/2, pi, 0])
            ed = bpy.context.object
            ed.name = "BSInvMarker:" + invm[0]
            ed.show_name = True 

            neut = MatrixLocRotScale((0, 100, 0),
                                     Euler((-pi/2, pi, 0), 'XYZ'),
                                     (1,1,1))
            mx = MatrixLocRotScale((0,0,0), 
                                   Euler(Vector(invm[1:4])/1000, 'XYZ'),
                                   (1,1,1))
            ed.matrix_world = mx @ neut
            # ed.data.lens = CAMERA_LENS * invm[4] 
            mx, focal_len = inv_to_cam(invm[1:4], invm[4])
            # ed.matrix_world = mx
            ed.data.lens = focal_len

            ed['BSInvMarker_Name'] = invm[0]
            ed['BSInvMarker_RotX'] = invm[1]
            ed['BSInvMarker_RotY'] = invm[2]
            ed['BSInvMarker_RotZ'] = invm[3]
            ed['BSInvMarker_Zoom'] = invm[4]

            ed.parent = parent_obj
            self.objects_created[ed.name] = ed

            # Set up the render resolution to work for the inventory marker camera.
            self.context.scene.render.resolution_x = 1400
            self.context.scene.render.resolution_y = 1200

    def import_furniture_markers(self, node, parent_obj):
        """
        In theory furniture markers can be on any node, but they really apply 
        to the whole nif.
        """
        if node.parent: return

        for fm in self.nif.furniture_markers:
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            obj = bpy.context.object
            obj.name = "BSFurnitureMarkerNode"
            obj.show_name = True
            obj.empty_display_type = 'SINGLE_ARROW'
            obj.location = Vector(fm.offset[:]) * self.scale
            obj.rotation_euler = (-pi/2, 0, fm.heading)
            obj.scale = Vector((40,10,10)) * self.scale
            obj['AnimationType'] = FurnAnimationType.GetName(fm.animation_type)
            obj['EntryPoints'] = FurnEntryPoints(fm.entry_points).fullname
            obj.parent = parent_obj
            self.objects_created[obj.name] = obj


    def import_connect_points_parent(self):
        """
        Parent connect points apply to the whole nif.
        """
        for cp in self.nif.connect_points_parent:
            bpy.ops.object.add(radius=self.scale, type='EMPTY')
            obj = bpy.context.object
            obj.name = "BSConnectPointParents" + "::" + cp.name.decode('utf-8')
            obj.show_name = True
            obj.empty_display_type = 'ARROWS'
            mx = Matrix.LocRotScale(
                Vector(cp.translation[:]) * self.scale,
                Quaternion(cp.rotation[:]),
                ((cp.scale * CONNECT_POINT_SCALE * self.scale),) * 3
            )
            obj.matrix_world = self.root_object.matrix_world @ mx

            parname = cp.parent.decode('utf-8')

            if parname and not parname.startswith("BSConnectPointChildren") \
                and not parname.startswith("BSConnectPointParents"):
                obj["pynConnectParent"] = parname
                parnamebl = self.blender_name(parname)
                if self.armature and parnamebl in self.armature.data.bones:
                    # log.info(f"Connect point {obj.name} is parented to bone {parnamebl}")
                    parbone = self.armature.data.bones[parnamebl]
                    obj.parent = self.armature
                    obj.matrix_world = self.root_object.matrix_world @ (parbone.matrix_local @ mx)
                elif parname in self.nif.nodes:
                    parnode = self.nif.nodes[parname]
                    if parnode._handle in self.objects_created:
                        obj.parent = self.objects_created[parnode._handle]
                        #log.debug(f"Created parent cp {obj.name} with parent {obj.parent.name}")
                    else:
                        self.warn(f"Parent node {parname} not imported")
                else:
                    self.warn(f"Could not find parent node {parname} for connect point {obj.name}")
            else:
                obj.parent = self.root_object

            self.objects_created[obj.name] = obj
            self.add_to_parents(obj)


    def import_connect_points_child(self):
        """
        Import the child connect point. There's only one and it applies to the
        whole nif, so only do it if we're working with the root node.
        """
        if self.nif.connect_points_child:
            childname = self.nif.connect_points_child[0].split('-')[1]
            bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
            obj = bpy.context.object
            obj.name = "BSConnectPointChildren::" + childname
            obj.show_name = True
            obj.empty_display_type = 'SPHERE'
            obj.location = (0,0,0)
            obj['PYN_CONNECT_CHILD_SKINNED'] = self.nif.connect_pt_child_skinned
            for i, n in enumerate(self.nif.connect_points_child):
                obj[f'PYN_CONNECT_CHILD_{i}'] = n
            for pcp in self.connect_parents:
                # If we had a selected parent connect point that matches, parent to it.
                if pcp.name.split('::')[1][2:] == childname:
                    obj.parent = pcp
            if not obj.parent: obj.parent = self.root_object
            self.created_child_cp = obj
            self.objects_created[obj.name] = obj
            self.add_to_child_cp(obj)


    def import_stringdata(self, node, parent_obj):
        for s in node.string_data:
            bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "NiStringExtraData"
            ed.show_name = True
            ed.empty_display_type = 'SPHERE'
            ed['NiStringExtraData_Name'] = s[0]
            ed['NiStringExtraData_Value'] = s[1]
            ed.parent = parent_obj
            # extradata.append(ed)
            self.objects_created[ed.name] = ed


    def import_behavior_graph_data(self, node, parent_obj):
        for s in node.behavior_graph_data:
            bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSBehaviorGraphExtraData"
            ed.show_name = True
            ed.empty_display_type = 'SPHERE'
            ed['BSBehaviorGraphExtraData_Name'] = s[0]
            ed['BSBehaviorGraphExtraData_Value'] = s[1]
            ed['BSBehaviorGraphExtraData_CBS'] = s[2]
            ed.parent = parent_obj
            # extradata.append(ed)
            self.objects_created[ed.name] = ed


    def import_cloth_data(self, node, parent_obj):
        for c in node.cloth_data: 
            bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSClothExtraData"
            ed.show_name = True
            ed.empty_display_type = 'SPHERE'
            ed['BSClothExtraData_Name'] = c[0]
            ed['BSClothExtraData_Value'] = codecs.encode(c[1], 'base64')
            ed.parent = parent_obj
            self.objects_created[ed.name] = ed


    def import_extra(self, parent_obj:bpy_types.Object, n:NiNode):
        """ Import any extra data from the node, and create corresponding shapes. 
            If n is None, get the extra data from the root.
        """
        if not n: n = self.nif.rootNode
        if not parent_obj: parent_obj = self.root_object

        self.import_bsx(n, parent_obj)
        self.import_inventory_marker(n, parent_obj)
        self.import_furniture_markers(n, parent_obj)
        self.import_stringdata(n, parent_obj)
        self.import_behavior_graph_data(n, parent_obj)
        self.import_cloth_data(n, parent_obj)


    def import_connect_points(self):
        """ 
        Import connect point information from the file. Connect points affect the whole
        nif rather than being attached to a shape. They should be dealt with last because
        they refer to other nodes.
        """
        self.import_connect_points_parent()
        self.import_connect_points_child()


    def bone_in_armatures(self, bone_name):
        """Determine whether a bone is in one of the armatures we've imported.
        Returns the bone or None.
        """
        for arma in self.imported_armatures:
            if bone_name in arma.data.bones:
                return arma.data.bones[bone_name]
        return None


    def import_ninode(self, arma, ninode:NiNode, parent=None):
        """Create Blender representation of an NiNode

        Don't import the node if (1) it's already been imported, (2) it's been imported as
        a bone in the skeleton, or (3) it's the root node
        
        * arma = armature to add the bone to; may be None
        * ninode = nif node
        * parent = Blender parent for new object
        * Returns the Blender representation of the node, either an object or a bone, or
          none
        """
        obj = None
        # if ninode.name == ninode.file.rootName:
        #     return None

        if not parent: parent = self.root_object

        # Nothing to do if we've already imported this object. 
        bl_name = self.blender_name(ninode.name)
        if ninode._handle in self.objects_created:
            return self.objects_created[ninode._handle]

        bn = self.bone_in_armatures(bl_name)
        if bn: 
            return bn 

        skelbone = None
        if self.reference_skel and ninode.name in self.reference_skel.nodes:
            skelbone = self.reference_skel.nodes[ninode.name]

        elif ninode.file.game == "FO4" and ninode.name in fo4FaceDict.byNif:
            skelbone = fo4FaceDict.byNif[ninode.name]

        #log.debug(f"Found for {ninode.name} {skelbone} to add to {arma}")
        if skelbone and arma:
            # Have not created this as bone in an armature already AND it's a known
            # skeleton bone, AND we have an armature, create it as an armature bone even
            # tho it's not used in the shape
            #log.debug(f"Creating bone for {bl_name}")
            ObjectSelect([arma], active=True)
            bpy.ops.object.mode_set(mode = 'EDIT')
            bn = self.add_bone_to_arma(arma, self.blender_name(ninode.name), ninode.name)
            bpy.ops.object.mode_set(mode = 'OBJECT')
            return bn

        # If not a known skeleton bone, just import as an EMPTY object
        if self.context.object: bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.add(radius=1.0, type='EMPTY')
        obj = bpy.context.object
        obj.name = ninode.name
        obj["pynBlockName"] = ninode.blockname
        obj["pynNodeName"] = ninode.name
        obj["pynNodeFlags"] = NiAVFlags(ninode.flags).fullname

        # Only the root node gets the import transform. It gets applied to all children automatically.
        if ninode.name == self.nif.rootName: 
            bpy.ops.object.mode_set(mode = 'OBJECT')
            obj.name = ninode.name + ":ROOT"
            obj["pynRoot"] = True
            obj["PYN_BLENDER_XF"] = MatNearEqual(self.import_xf, blender_import_xf)
            obj['PYN_GAME'] = self.nif.game
            obj.empty_display_type = 'CONE'

            mx = self.import_xf @ transform_to_matrix(ninode.transform)
            obj.matrix_local = mx

            self.root_object = obj
            parent = None
        else:
            obj.matrix_local = transform_to_matrix(ninode.transform)

        if parent:
            if type(parent) == bpy_types.Object:
                obj.parent = parent
            else:
                # Can't set a bone as parent, but get the node in the right position
                obj.matrix_local = apply_scale_xf(transform_to_matrix(ninode.global_transform), self.scale) 
                obj.parent = self.root_object
        self.objects_created[ninode._handle] = obj

        if ninode.collision_object:
            self.import_collision_obj(ninode.collision_object, obj)

        self.import_extra(obj, ninode)

        if self.root_object != obj and ninode.controller and self.do_import_anims: 
            # import animations if this isn't the root node. If it is, they may reference
            # any of the root's children and so wait until those can be imported.
            ctlr = controller.ControllerHandler(
                self.nif, self.objects_created, msghandler=self)
            ctlr.import_controller(ninode.controller)
            # self.import_animations(ninode.controller)

        return obj


    def import_node_parents(self, arma, node: NiNode):
        """Import the chain of parents of the given node all the way up to the root"""
        # Get list of parents of the given node from the list, bottom-up. 
        parents = []
        n = node.parent
        while n:
            parents.insert(0, n)
            n = n.parent

        # Create the parents top-down
        obj = None
        p = None
        for ch in parents: # [0] is the root node
            obj = self.import_ninode(arma, ch, p)
            p = obj

        return obj


    def import_loose_ninodes(self, nif, arma=None):
        """Import any NiNodes that don't have any special purpose--likely skeleton bones
        that aren't used in shapes.
        """
        original_bones = set()
        if arma:
            for n in arma.data.bones.keys():
                original_bones.add(n)

        for nm, n in nif.nodes.items():
            # If it's a bhk (collision) node, only consider it if we're importing
            # collisions.
            if not nm.startswith('bhk') or self.do_import_collisions:
                p = self.import_node_parents(arma, n)
                self.import_ninode(arma, n, p)
        
        if arma:
            # Set the pose position for the bones we just added
            new_bones = set(arma.data.bones.keys()).difference(original_bones)
            bone_names = [(self.nif_name(n), n) for n in new_bones]
            #log.debug(f"Setting pose locations for {bone_names}")
            self.set_bone_poses(arma, nif, bone_names)


    def mesh_create_bone_groups(self, the_shape, the_object):
        """ Create groups to capture bone weights """
        vg = the_object.vertex_groups
        for bone_name in the_shape.bone_names:
            new_vg = vg.new(name=self.blender_name(bone_name))
            for v, w in the_shape.bone_weights[bone_name]:
                new_vg.add((v,), w, 'ADD')
    

    def set_object_xf(self, the_shape, new_object):
        # Set the object transform to reflect the skin transform in the nif. This
        # positions the object conveniently for editing.
        mx = self.calc_obj_transform(the_shape, scale_factor=self.scale)
        if new_object.parent: 
            # Have to set matrix_world because setting matrix_local doesn't seem to work.
            new_object.matrix_world = new_object.parent.matrix_world @ mx
        else:
            new_object.matrix_world = mx
            

    def import_shape(self, the_shape: NiShape):
        """ Import the shape to a Blender object, translating bone names if requested
            
        * self.objects_created = List of objects created, extended with objects associated
          with this shape. Might be more than one because of extra data nodes.
        * self.loaded_meshes = List of Blender objects created that represent meshes,
          extended with this shape.
        * self.nodes_loaded = Dictionary mapping blender name : NiShape from nif
        """
        v = the_shape.verts
        t = the_shape.tris
        if self.scale == 1.0:
            v = the_shape.verts
        else:
            v = [(n[0]*self.scale, n[1]*self.scale, n[2]*self.scale) for n in the_shape.verts]

        new_mesh = bpy.data.meshes.new(the_shape.name)
        new_mesh.from_pydata(v, [], t)
        new_mesh.update(calc_edges=True, calc_edges_loose=True)
        new_object = bpy.data.objects.new(the_shape.name, new_mesh)
        new_object['pynBlockName'] = the_shape.blockname
        the_shape.properties.extract(new_object, ignore=NISHAPE_IGNORE)
        self.loaded_meshes.append(new_object)
        self.nodes_loaded[new_object.name] = the_shape
    
        if not self.mesh_only:
            self.objects_created[the_shape._handle] = new_object
            
            import_colors(new_mesh, the_shape)

            parent = self.import_node_parents(None, the_shape) 

            # Parent the shape. Skinned meshes will be parented to the parent found in 
            # the nif, not to the armature. 
            if parent: # and parent != self.root_object: # and not the_shape.bone_names:
                new_object.parent = parent

            mesh_create_uv(new_object.data, the_shape.uvs)
            self.mesh_create_bone_groups(the_shape, new_object)
            mesh_create_partition_groups(the_shape, new_object)
            for f in new_mesh.polygons:
                f.use_smooth = True

            new_mesh.validate(verbose=True)

            if the_shape.normals:
                mesh_create_normals(new_object.data, the_shape.normals)

            shader_io.ShaderImporter().import_material(new_object, the_shape, asset_path)

            if the_shape.collision_object:
                self.import_collision_obj(the_shape.collision_object, new_object)

            if the_shape.controller:
                controller.ControllerHandler.import_block(
                    the_shape.controller,
                    self,
                    target_object=new_object)
                
            if the_shape.shader.controller:
                controller.ControllerHandler.import_block(
                    the_shape.shader.controller,
                    self,
                    target_object=new_object)
                
            self.import_extra(new_object, the_shape)

            new_object['PYN_GAME'] = self.nif.game
            new_object['PYN_BLENDER_XF'] = MatNearEqual(self.import_xf, blender_import_xf)
            new_object['PYN_RENAME_BONES'] = self.do_rename_bones 
            if self.rename_bones_nift != RENAME_BONES_NIFT_DEF:
                new_object['PYN_RENAME_BONES_NIFT'] = self.rename_bones_nift 

        self.collection.objects.link(new_object)


    # ------ ARMATURE IMPORT ------

    def calc_skin_transform(self, arma, obj=None) -> Matrix:
        """
        Determine the skin transform to use for this shape.
        Skin transform will be:
        - the transform on the armature if there is one, combined with the shape's own
        skin transform
        - the skin transform on the shape if there is one
        - the identity matrix
        """
        skin_xf = Matrix.Identity(4)
        # Check for a transform on the armature. If it's present, this overrules
        # everything else. 
        if not obj:
            if 'PYN_TRANSFORM' in arma:
                skin_xf = eval(arma['PYN_TRANSFORM'])
            return skin_xf

        if False: # 'PYN_TRANSFORM' not in arma:
            skin_xf = obj.matrix_local.copy()
            arma['PYN_TRANSFORM'] = repr(skin_xf)
        elif 'PYN_TRANSFORM' in arma:
            try:
                # If the object is being parented to an existing armature, use the skin
                # transform the armature used.
                arma_xf = eval(arma['PYN_TRANSFORM'])
                skin_xf = obj.matrix_local.copy()
                if not MatNearEqual(arma_xf, skin_xf): 
                    log.debug(f"Transforms don't match between {arma.name} and {obj.name}" + f"\n{arma_xf.translation} != {skin_xf.translation}")
                    self.warn(f"Skin transform on {obj.name} do not match existing armature. Shapes may be offset.")
                    return skin_xf @ arma_xf.inverted()
                return arma_xf
            except Exception as e:
                self.warn(repr(e))
                skin_xf = obj.matrix_local.copy()
        else:
            skin_xf = obj.matrix_local.copy()

        return skin_xf


    # def bone_nif_to_blender(self, shape:NiShape, bone:str, skin_xf:Matrix) -> Matrix:
    #     """Return bone's final position in blender
        
    #     arma: armature that will parent bone
    #     skin_xf: the skin transform applied to all shapes under the armature.
    #     """
    #     bone_xf = transform_to_matrix(shape.get_shape_skin_to_bone(bone))
    #     bone_xf = apply_scale_transl(skin_xf, 1/self.scale) @ bone_xf.inverted()
    #     bone_xf = Matrix.Scale(self.scale, 4) @ bone_xf @ game_rotations[game_axes[shape.file.game]][0]
    #     return bone_xf
    

    def check_armature(self, obj, shape, arma):
        """Check whether an armature is consistent with the shape's bone bind positioins. 
        If a single transform will make the armature consistent, return that transform. 

        Returns
        * is_ok - armature is consistent
        * offset_xf - necessary offset from armature to shape
        """
        is_ok = True
        offset_xf = None
        offset_consistent = True

        for b in shape.bone_names:
            blend_name = self.blender_name(b)
            if blend_name in arma.data.bones:
                shape_bone_xf = obj.matrix_local @ apply_scale_xf(bind_position(shape, b), self.scale) 
                arma_xf = get_bone_xform(arma, blend_name, shape.file.game, False, False)
                if not MatNearEqual(shape_bone_xf, arma_xf):
                    is_ok = False
                    this_offset = shape_bone_xf @ arma_xf 
                    if offset_xf:
                        if not MatNearEqual(this_offset, offset_xf):
                            offset_consistent = False
                                #log.debug(f"Offsets different for {b}: {this_offset.translation} != {offset_xf.translation}")
                            break
                    else:
                        offset_xf = this_offset
        
        return is_ok, offset_xf, offset_consistent


    def find_compatible_arma(self, obj, armatures:list):
        """
        Look through the list of armatures and find one that can be used by the shape: One
        that has a global-to-skin transform that is close to that of this shape.

        If do_estimate_offset is clear, return self.armature. If we aren't estimating the
        global-to-skin transform any armature will do.

        if do_import_pose is set, we return self.armature. That's either the one selected
        before import, or reflects bone NiNodes in the nif, so it's the one to use either
        way.

        Otherwise, for an armature to be compatible with a shape's skin, the bind
        positions of the bones in the skin have to be the same as the edit positions of
        the bones in the armature. 

        If there's not a match, it may be that the bind positions were all offset by the
        same amount--just a transpose. If so, we could add this transpose to the skin
        transform and then we can use the same armature.

        If there's no armature, the shape might be compatible with the reference skeleton.
        if so, we return no armature but do return a transform for the reference skeleton
        (if needed).

        Returns (armature, transform-matrix), or None.
        """
        shape = self.nodes_loaded[obj.name]

        if self.do_import_pose:
            return self.armature, None
        else:
            for arma in armatures:
                is_ok, offset, offset_consistent = self.check_armature(obj, shape, arma)
                if is_ok:
                    return arma, offset
        return None, None

    def add_bone_to_arma(self, arma, bone_name:str, nifname:str):
        """Add bone to armature. Bone may come from nif or reference skeleton.
        Bind position is set to vanilla bind position if we're extending the skeleton.
        Otherwise set to the position in the nif. Pose position is not set--do that with
        set_bone_poses afterwards. Blender gets crashy if this isn't done in a separate
        step.

        *   bone_name = name to use for the bone in blender 
        *   nifname = name the bone has in the nif returns new bone
        """
        armdata = arma.data

        if bone_name in armdata.edit_bones:
            return None
    
        # Use the transform from the reference skeleton if we're extending bones; 
        # otherwise use the one in the file.
        if self.do_create_bones and self.reference_skel and nifname in self.reference_skel.nodes:
            bone_xform = transform_to_matrix(self.reference_skel.nodes[nifname].global_transform)
            bone = create_bone(armdata, bone_name, bone_xform, 
                               self.nif.game, self.scale, 0)
        else:
            xf = self.nif.get_node_xform_to_global(nifname) 
            bone_xform = transform_to_matrix(xf)
            # We have the world position of the bone, so we don't need the armature's 
            # skin transform. (We might need the armature object's Blender transform. 
            # But that's always the identity.)
            bone = create_bone(armdata, bone_name, bone_xform, 
                               self.nif.game, self.scale, 0)

        return bone
    

    def set_bone_poses(self, arma, nif:NifFile, bonelist:list):
        """
        Set the pose transform of all the given bones. Pose transform is the transform on
        the NiNode in the nif being imported.
        *   bonelist = [(nif-name, blender-name), ...]
        """
        for bn, blname in bonelist:
            if bn in nif.nodes and blname in arma.pose.bones:
                nif_bone = nif.nodes[bn]
                if nif_bone.blockname == "NiNode" and nif_bone.name != nif.rootName:
                    bone_xf = transform_to_matrix(nif_bone.global_transform)

                    if self.is_facegen:
                        try:
                            # Facegen bone rotations are missing--get them from the skeleton
                            skel_bone = self.reference_skel.nodes['HEAD' if bn=='Head' else bn]
                            skb_xf = transform_to_matrix(skel_bone.global_transform)
                            skbloc, skbrot, skbscale = skb_xf.decompose()
                            bloc, brot, bscale = bone_xf.decompose()
                            bone_xf = MatrixLocRotScale(bloc, skbrot, bscale)
                        except:
                            pass

                    pb_xf = apply_scale_transl(bone_xf, self.scale)
                    pose_bone = arma.pose.bones[blname]
                    pbmx = get_pose_blender_xf(bone_xf, self.nif.game, self.scale)
                    pose_bone.matrix = pbmx
                    bpy.context.view_layer.update()


    def set_all_bone_poses(self, arma, nif:NifFile):
        """Set all bone pose transforms based on the nif. No reason not to do it once at
        the end.
        """
        bonelist = [(self.nif_name(b.name), b.name) for b in arma.data.bones]
        self.set_bone_poses(arma, nif, bonelist)


    def connect_armature(self, arma):
        """ Connect up the bones in an armature to make a full skeleton.
            Use parent/child relationships in the nif if present, from the skel otherwise.
            Uses flags
                CREATE_BONES - add bones from skeleton as needed
                RENAME_BONES - rename bones to conform with blender conventions
                RENAME_BONES_NIFTOOLS - rename bones to conform with blender conventions
            Returns list of bone nodes with collisions found along the way
            """
        #log.debug(f"<connect_armature> {arma.name}={arma.data.bones.keys()}")
        ObjectActive(arma)
        
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')

        arm_data = arma.data
        arm_data.edit_bones.update()
        bones_to_parent = [b.name for b in arm_data.edit_bones]
        new_bones = []
        collisions = set()

        i = 0
        while i < len(bones_to_parent): # list will grow while iterating
            bonename = bones_to_parent[i]
            arma_bone = arm_data.edit_bones[bonename]

            if arma_bone.parent is None:
                parentname = None
                parentnifname = None
                
                # look for a parent in the nif
                nifname = self.nif_name(bonename)
                if nifname in self.nif.nodes:
                    thisnode = self.nif.nodes[nifname]
                    if thisnode.collision_object:
                        collisions.add(thisnode)

                    niparent = thisnode.parent
                    if niparent and niparent.name != self.nif.rootName:
                        try:
                            parentnifname = niparent.nif_name
                        except:
                            parentnifname = niparent.name
                        parentname = self.blender_name(niparent.name)
                        #log.debug(f"Found parent in armature: {parentname}/{parentnifname} for {bonename}/{nifname}")

                if parentname is None and self.do_create_bones and not is_facebone(bonename):
                    ##log.debug(f"No parent for '{nifname}' in the nif. If it's a known bone, get parent from skeleton")
                    if self.reference_skel and \
                        nifname in self.reference_skel.nodes and \
                            nifname != self.reference_skel.rootName:
                        p = self.reference_skel.nodes[nifname].parent
                        if p and p.name != self.reference_skel.rootName:
                            parentname = self.blender_name(p.name)
                            parentnifname = p.name
            
                # if we got a parent from somewhere, hook it up
                if parentname:
                    if parentname not in arm_data.edit_bones:
                        # Add parent bones and put on our list so we can get its parent
                        #log.debug(f"<connect_armature> adding bone {parentname}/{parentnifname}")
                        new_parent = self.add_bone_to_arma(arma, parentname, parentnifname)
                        bones_to_parent.append(parentname)  
                        arm_data.edit_bones[bonename].parent = new_parent
                        new_bones.append((parentnifname, parentname))
                    else:
                        arm_data.edit_bones[bonename].parent = arm_data.edit_bones[parentname]

                        # if saved_pose:
                        #     arma.pose.bones[bonename].matrix = saved_pose 
            i += 1

        bpy.ops.object.mode_set(mode='OBJECT')
        arma.update_from_editmode()
        self.set_all_bone_poses(arma, self.nif)
        bpy.ops.object.mode_set(mode='OBJECT')

        for bonenode in collisions:
            self.import_collision_obj(bonenode.collision_object, arma, bonenode)
        return collisions
    

    def group_bones(self, armature):
        """For convenience, create armature bone groups."""
        ok = False
        try:
            # Blender 4.x
            for b in armature.data.bones:
                bg_name = b.name.split()[0]
                if bg_name not in ARMATURE_BONE_GROUPS:
                    if b.name.endswith("_skin"):
                        bg_name = "Skin"
                    elif '_CBP_' in b.name:
                        bg_name = 'CBP'
                    else:
                        bg_name = None
                if bg_name:
                    if bg_name not in armature.data.collections:
                        c = armature.data.collections.new(name=bg_name)
                    else:
                        c = armature.data.collections[bg_name].assign(b)
                    # Can't set color; not sure how this is supposed to work
                    # b.color.pallet = f'THEME0{c.index+1}'
            ok = True
        except:
            pass

        if not ok:
            try:
                # Blender 3.x
                groups = {}
                for g in armature.pose.bone_groups:
                    groups[g.name] = g

                for b in armature.pose.bones:
                    bg_name = b.name.split()[0]
                    if bg_name not in ARMATURE_BONE_GROUPS:
                        if "_skin" in b.name:
                            bg_name = "Skin"
                        else:
                            bg_name = None
                    if bg_name:
                        if bg_name in groups:
                            target_group = groups[bg_name]
                        else:
                            target_group = armature.pose.bone_groups.new(name=bg_name)
                            groups[bg_name] = target_group
                        if target_group:
                            b.bone_group = target_group
            except:
                pass
        
        if not ok:
            log.info(f"Cannot create convenience bone groups")


    def roll_bones(self, arma):
        ObjectSelect([arma])
        ObjectActive(arma)
        bpy.ops.object.mode_set(mode='EDIT')
        # print(f"Bone roll for 'NPC Calf [Clf].L' = {arma.data.edit_bones['NPC Calf [Clf].L'].roll}")
        for b in arma.data.edit_bones:
            b.roll += -90 * pi / 180
        # print(f"Bone roll for 'NPC Calf [Clf].L' = {arma.data.edit_bones['NPC Calf [Clf].L'].roll}")
        bpy.ops.object.mode_set(mode='OBJECT')
        arma.update_from_editmode()


    
    def add_bones_to_arma(self, arma, nif, bone_names):
        """Add all the bones in the list to the armature.
        * bone_names = nif bone names to import
        """
        ObjectSelect([arma], active=True)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        new_bones = []
        for bone_nif_name in bone_names:
            if bone_nif_name != nif.rootName:
                name = self.blender_name(bone_nif_name)
                self.add_bone_to_arma(arma, name, bone_nif_name)
                new_bones.append((bone_nif_name, name))
        self.set_bone_poses(arma, nif, new_bones)
        bpy.ops.object.mode_set(mode='OBJECT')
        arma.update_from_editmode()


    def make_armature(self, the_coll: bpy_types.Collection, name_prefix=""):
        """Make a Blender armature from the given info. 
            
            Inputs:
            *   the_coll = Collection to put the armature in. 
            *   bone_names = bones to include in the armature.
            *   self.armature = existing armature to add the new bones to. May be None.
            
            Returns: 
            * new armature, set as active object
            """
        arm_data = bpy.data.armatures.new(arma_name(name_prefix + self.nif.rootName))
        arma = bpy.data.objects.new(arma_name(name_prefix + self.nif.rootName), arm_data)
        arma.parent = self.root_object
        the_coll.objects.link(arma)

        # bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        # ObjectSelect([arma], active=True)
        # bpy.ops.object.mode_set(mode='EDIT', toggle=False)

        if self.nif.dict.use_niftools:
            try:
                arm_data.niftools.axis_forward = "Z"
                arm_data.niftools.axis_up = "-X"
            except:
                pass

        #if self.scale != SCALE_DEF: arma['PYN_SCALE_FACTOR'] = self.scale 
        arma['PYN_BLENDER_XF'] = MatNearEqual(self.import_xf, blender_import_xf)
        arma['PYN_RENAME_BONES'] = self.do_rename_bones
        if self.rename_bones_nift != RENAME_BONES_NIFT_DEF:
            arma['PYN_RENAME_BONES_NIFTOOLS'] = self.rename_bones_nift 

        return arma


    def is_compatible_skeleton(self, skin_xf:Matrix, shape:NiShape, skel:NifFile) -> bool:
        """Determine whether the given skeleton file is compatible with the shape. 

        It's compatible if the shape's bones' bind positions are the same as the
        skeleton's bones. 
        """
        if not skel: return False

        # FO4 skin-to-bone is freaking all over the place, so give them a more generous
        # allowance.
        variance = 0.03 if "SKYRIM" in self.nif.game else 0.1
        
        for b in shape.bone_names:
            if b in skel.nodes:
                m1 = skin_xf @ transform_to_matrix(shape.get_shape_skin_to_bone(b)).inverted()
                m2 = transform_to_matrix(skel.nodes[b].global_transform)
                # We give a fairly generous allowance for how close is close enough. 0.03 
                # allows the FO4 meshes to be parented to their skeletons. 
                if not MatNearEqual(m1, m2, epsilon=variance):
                    # log.debug(f"Skeleton not compatible on {b}: \n{m1} != \n{m2}")
                    return False
        return True


    def set_parent_arma(self, arma, obj, nif_shape:NiShape, s2a_xf:Matrix):
        """Set the given armature as controller for the given object. Ensures all the
        bones referenced by the shape are in the armature.
        
        * arma - armature to use. May be None, in which case it's created if necessary.
        * obj - skinned shape. Bones it uses are added to the arma at bind position, with
          the nif location as pose position
        * nif_shape - corresponding shape from the nif
        * s2a_xf - additional transform which must be applied to import this shape under
          this armature (may be None)
        
        Returns armature with bones from this shape added
        """
        if arma is None:
            arma = self.make_armature(self.collection)

        # All shapes parented to the same armature need to have the same transform applied
        # for editing. (Puts body parts in a convenient place for editing.) That transform
        # is stored on the shape.
        unscaled_skin_xf = self.calc_skin_transform(arma, obj)
        if s2a_xf:
            unscaled_skin_xf = unscaled_skin_xf.inverted() @ s2a_xf 

        # FO4 facegen nifs can have wonky transforms. They can be ignored. ### Is this true?
        if True: ### not self.is_facegen:
            obj.matrix_local = unscaled_skin_xf.copy()
        # skin_xf = arma.parent.matrix_world.inverted() @ unscaled_skin_xf
        skin_xf = unscaled_skin_xf.copy()

        # Create bones. If do_import_pose, positions are the NiNode positions of the
        # bone. Otherwise, they are the skin-to-bone transforms (bind position).
        ObjectActive(arma)
        new_bones = []
        bpy.ops.object.mode_set(mode = 'EDIT')

        for bn in nif_shape.bone_names:
            blname = self.blender_name(bn)
            if blname not in arma.data.edit_bones:
                if False: ### self.is_facegen and self.reference_skel: 
                    ### This gives a reasonable skeleton but the head parts are still rotated 
                    ### and off.
                    # FO4 facegen files have wonky bind transforms. Use the reference
                    # skeleton instead.
                    bone_node = self.reference_skel.nodes['HEAD' if bn=='Head' else bn]
                    xf = transform_to_matrix(bone_node.global_transform)
                elif self.do_import_pose: ### and not self.is_facegen:
                    # Using nif locations of bones. 
                    bone_node = nif_shape.file.nodes[bn]
                    # xf = transform_to_matrix(bone_node.properties.transform)
                    xf = transform_to_matrix(bone_node.global_transform)
                else:
                    # Have to trust the bind position in the nif.
                    # Facegen nifs always use the bind position.
                    bone_shape_xf = transform_to_matrix(nif_shape.get_shape_skin_to_bone(bn)).inverted()
                    xf = skin_xf @ bone_shape_xf
                create_bone(arma.data, blname, xf, self.nif.game, 1.0, 0)
                new_bones.append((bn, blname))

        # Do the pose in a separate pass so we don't have to flip between modes.
        if not self.do_import_pose:
            bpy.ops.object.mode_set(mode = 'OBJECT')
            self.set_bone_poses(arma, self.nif, new_bones)
        bpy.ops.object.mode_set(mode = 'OBJECT')

        ObjectActive(obj)
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arma

        return arma
    

    def facegen_cleanup(self, obj):
        """
        Correct FO4 facegen shape locations.
        
        This is a hack but it does work. 
        """
        armatures = [m for m in obj.modifiers if m.type == 'ARMATURE']
        for m in armatures:
            arma = m.object
            bpy.ops.object.modifier_apply(modifier=m.name)

            ObjectSelect([arma], active=True)
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.armature_apply()
            bpy.ops.object.mode_set(mode='OBJECT')

            mnew = obj.modifiers.new("Armature", 'ARMATURE')
            mnew.object = arma
    
        # for b in arma.data.bones:
        #     nifname = self.nif_name(b.name)
        #     if nifname in self.reference_skel.nodes:
        #         rb = self.reference_skel.nodes[nifname]
        #         xf = transform_to_matrix(rb.transform)
        #         xfloc, xfrot, xfscale = xf.decompose()
        #         b.matrix = xfrot.to_matrix()
        # return
        # for pb in arma.pose.bones:
        #     nifname = self.nif_name(pb.name)
        #     if nifname in self.reference_skel.nodes:
        #         rb = self.reference_skel.nodes[nifname]
        #         xf = transform_to_matrix(rb.transform)
        #         xfloc, xfrot, xfscale = xf.decompose()

        #         # Pose transform is relative to bone, so take bone transform out.
        #         b = arma.data.bones[pb.name]
        #         relxf = b.matrix.inverted() @ xfrot.to_matrix()
        #         pb.rotation_quaternion = relxf.to_quaternion()

    
    def animate_bone(self, arma, boneobj, bone:NiNode):
        if not bone.controller: return

        p = bone.controller.properties
        self.context.scene.frame_end = 1 + int(p.stopTime - p.startTime) * self.context.scene.render.fps

        if not arma.animation_data: arma.animation_data_create()
        a = arma.animation_data.action
        if not a:
            action_name = arma.name
            a = bpy.data.actions.new(action_name)
            a.use_fake_user = True
            a.asset_mark()
            arma.animation_data.action = a
        
        rotmode = self.import_interpolator(
            bone.controller.interpolator, 
            arma, 
            a, 
            boneobj.name,
            f'pose.bones["{boneobj.name}"]',
            boneobj.matrix_local)
        arma.pose.bones[boneobj.name].rotation_mode = rotmode


    def animate_armature(self, arma):
        """Load any animations associated with the armature."""
        if not self.do_import_anims: return
        for b in arma.data.bones:
            nifname = self.nif_name(b.name)
            if nifname in self.nif.nodes: 
                self.animate_bone(arma, b, self.nif.nodes[nifname])


    # ------- COLLISION IMPORT --------

    def import_bhkConvexTransformShape(self, cs:CollisionShape, parentxf:Matrix):
        """
        bhkConvexTransformShape just repositions its child. It's not represented
        in blender--its transform is applied directly to the collision shape.
        """
        xf = Matrix(cs.transform)
        xf.translation = xf.translation * HAVOC_SCALE_FACTOR 
        childobj = self.import_collision_shape(cs.child, parentxf)

        # We set the children's location, so ignore any location they already have.
        childobj.matrix_local = xf

        return childobj


    def import_bhkListShape(self, cs:CollisionShape, parentxf:Matrix):
        """ 
        Import collision list. 
        cs= collision node in nif. 
        parentxf = Parent transfoorm.
        """
        bpy.ops.mesh.primitive_cube_add(size=0.01, enter_editmode=False, align='WORLD', 
                                        location=(0, 0, 0), scale=(1, 1, 1))
        cshape = bpy.context.object
        cshape.name = 'bhkListShape'
        cshape.show_name = True
        cshape['bhkMaterial'] = SkyrimHavokMaterial.get_name(cs.properties.bhkMaterial)
        cshape.matrix_world = parentxf.copy()

        # children = []
        for child in cs.children:
            # children.append(self.import_collision_shape(child, targobj))
            childobj = self.import_collision_shape(child, parentxf)
            childobj.parent = cshape

        return cshape


    def import_bhkBoxShape(self, cs:CollisionShape, parentxf):
        m = bpy.data.meshes.new(cs.blockname)
        prop = cs.properties
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        dx = prop.bhkDimensions[0] * sf
        dy = prop.bhkDimensions[1] * sf
        dz = prop.bhkDimensions[2] * sf
        v = [ [-dx, dy, dz],    
              [-dx, -dy, dz],   
              [-dx, -dy, -dz],  
              [-dx, dy, -dz],
              [dx, dy, dz],
              [dx, -dy, dz],
              [dx, -dy, -dz],
              [dx, dy, -dz] ]

        m.from_pydata(v, [], 
                      [ (0, 3, 2, 1), 
                        (4, 5, 6, 7),
                        (0, 1, 5, 4),
                        (2, 3, 7, 6),
                        (0, 4, 7, 3), 
                        (5, 1, 2, 6)])
        obj = bpy.data.objects.new(cs.blockname, m)
        obj.matrix_world = parentxf.copy()
        obj['bhkMaterial'] = SkyrimHavokMaterial.get_name(prop.bhkMaterial)
        obj['bhkRadius'] = prop.bhkRadius * self.import_scale

        self.collection.objects.link(obj)

        return obj
        
    def import_bhkCapsuleShape(self, cs:CollisionShape, parentxf:Matrix):
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        prop = cs.properties
        p1 = Vector(prop.point1) * sf
        p2 = Vector(prop.point2) * sf
        shaperad = prop.radius1 * sf

        obj = create_capsule(p1, p2, shaperad)
        prop.extract(obj, ignore=CAPSULE_SHAPE_IGNORE)

        for p in obj.data.polygons:
            p.use_smooth = True
        obj.data.update()
        
        obj.name = 'bhkCapsuleShape'
        obj.matrix_world = parentxf.copy()
        obj['bhkMaterial'] = SkyrimHavokMaterial.get_name(prop.bhkMaterial)
        obj['bhkRadius'] = prop.bhkRadius
        return obj
        

    def import_bhkSphereShape(self, cs:CollisionShape, parentxf:Matrix):
        prop = cs.properties
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        shaperad = prop.bhkRadius * sf

        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=shaperad, 
                                             calc_uvs=False,
                                             location=(0,0,0))
        obj = bpy.context.object
        obj.matrix_world = parentxf.copy()

        for p in obj.data.polygons:
            p.use_smooth = True
        obj.data.update()
        
        obj['bhkMaterial'] = SkyrimHavokMaterial.get_name(prop.bhkMaterial)
        obj['bhkRadius'] = prop.bhkRadius * self.import_scale
        return obj
        

    def show_collision_normals(self, cs:CollisionShape, cso):
        #norms = [Vector(n)*HAVOC_SCALE_FACTOR for n in cs.normals]
        sf = -HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        # sf = -HAVOC_SCALE_FACTOR * self.scale * game_collision_sf[self.nif.game]
        bpy.ops.object.select_all(action='DESELECT')
        for n in cs.normals:
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            obj = bpy.context.object
            obj.empty_display_type = 'SINGLE_ARROW'
            obj.empty_display_size = n[3] * sf
            v = Vector(n)
            v.normalize()
            q = Vector((0,0,1)).rotation_difference(v)
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = q
            obj.parent = cso
            

    def import_bhkConvexVerticesShape(self, 
                                      collisionnode:CollisionShape,
                                      parentxf:Matrix):
        """
        Import a bhkConvexVerticesShape object.
            collisionnode = the bhkConvexVerticesShape node in the nif
            targobj = parent collision body object in Blender 
        """
        prop = collisionnode.properties

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        # sf = HAVOC_SCALE_FACTOR * self.scale * game_collision_sf[self.nif.game]

        #log.debug(f"Convex verts bounds X RAW: {min(v[0] for v in collisionnode.vertices)}, {max(v[0] for v in collisionnode.vertices)}")
        sourceverts = [Vector(v[0:3])*sf for v in collisionnode.vertices]

        m = bpy.data.meshes.new(collisionnode.blockname)
        bm = bmesh.new()
        m.from_pydata(sourceverts, [], [])
        bm.from_mesh(m)

        bmesh.ops.convex_hull(bm, input=bm.verts)
        bm.to_mesh(m)

        obj = bpy.data.objects.new(collisionnode.blockname, m)
        obj.matrix_world = parentxf.copy()
        self.collection.objects.link(obj)
        
        try:
            obj['bhkMaterial'] = SkyrimHavokMaterial.get_name(prop.bhkMaterial)
        except:
            self.warn(f"Unknown havok material: {prop.bhkMaterial}")
            obj['bhkMaterial'] = str(prop.bhkMaterial)
        obj['bhkRadius'] = prop.bhkRadius * self.import_scale

        # if log.getEffectiveLevel() == logging.DEBUG:
        #     self.show_collision_normals(collisionnode, obj)
        # This gets rotation from target quaternion--is this the same as matrix_world?
        # obj.rotation_mode = "QUATERNION"
        # q = targobj.rotation_quaternion.copy()
        q = parentxf.to_quaternion()
        q.invert()
        obj.rotation_quaternion = q
        return obj


    def import_collision_shape(self, cs:CollisionShape, parentxf):
        sh = None
        #log.debug(f"Found collision shape {cs.blockname}")
        if cs.blockname == "bhkBoxShape":
            sh = self.import_bhkBoxShape(cs, parentxf)
        elif cs.blockname == "bhkConvexVerticesShape":
            sh = self.import_bhkConvexVerticesShape(cs, parentxf)
        elif cs.blockname == "bhkListShape":
            sh = self.import_bhkListShape(cs, parentxf)
        elif cs.blockname == "bhkConvexTransformShape":
            sh = self.import_bhkConvexTransformShape(cs, parentxf)
        elif cs.blockname == "bhkCapsuleShape":
            sh = self.import_bhkCapsuleShape(cs, parentxf)
        elif cs.blockname == "bhkSphereShape":
            sh = self.import_bhkSphereShape(cs, parentxf)
        else:
            self.warn(f"Found unimplemented collision shape: {cs.blockname}")
        
        if sh:
            ObjectSelect([sh], active=True)
            bpy.ops.rigidbody.object_add(type='ACTIVE')

            sh.color = COLLISION_COLOR
            sh.display_type = 'WIRE'

        return sh


    def import_collision_body(self, cb:bhkWorldObject, targetxf):
        """
        Import the RigidBody node.

        targetxf = target's world transform
        returns the collision shape
        """
        if not cb.shape: 
            self.warn(f"Collision has unsupported collision shape")
            return None
        
        # If collision body provides a transform it is relative to the collision target.
        # Blender's collision object does not have the target as parent because it
        # confuses Blender. So combine the target transform with the body transform to get
        # the equivalent.
        # 
        # Blender's collision object sets the transform for the collision target, so that
        # *has* to be the local transform on the collision object. We lose any additional
        # transform added by the body--but that doesn't change the effective collision. 
        bodyxf = RigidBodyXF(cb)

        sh = self.import_collision_shape(cb.shape, bodyxf)
        ObjectSelect([sh], active=True)
        bpy.ops.object.transform_apply()
        sh.matrix_world = targetxf.copy()

        p = cb.properties
        p.extract(sh, ignore=COLLISION_BODY_IGNORE)
        if not cb.blockname.startswith('bhkRigidBody'):
            sh['pynRigidBody'] = cb.blockname

        try:
            sh.rigid_body.mass = p.mass / HAVOC_SCALE_FACTOR
            sh.rigid_body.friction = p.friction / HAVOC_SCALE_FACTOR
            sh.rigid_body.use_margin = True
            sh.rigid_body.collision_margin = cb.shape.properties.bhkRadius # * HAVOC_SCALE_FACTOR
            sh.rigid_body.linear_damping = p.linearDamping / HAVOC_SCALE_FACTOR
            sh.rigid_body.angular_damping = p.angularDamping / HAVOC_SCALE_FACTOR
        except:
            pass
            
        if sh.name.split('.')[0] == 'bhkListShape':
            rbtype = 'ACTIVE' if p.collisionFilter_layer in collision_active_layers else 'PASSIVE'
            sh.rigid_body.collision_shape = 'COMPOUND'
            for ch in sh.children:
                ObjectSelect([ch], active=True)
                bpy.ops.rigidbody.object_add(type=rbtype)
                
        return sh


    def import_collision_obj(self, c:CollisionObject, parentObj=None, bone:NiNode=None):
        """
        Import collision object. 
        * parentObj is target of collision if it's a NiNode. If target is a bone,
        parentObj is armature and "bone" is the NiNode for the bone. 
        * Returns new collision object.
        """
        if not self.do_import_collisions: return None

        col = None
        bpy.ops.object.mode_set(mode='OBJECT')
        if c.blockname not in ["bhkCollisionObject", 
                           "bhkSPCollisionObject", 
                           "bhkNPCollisionObject", 
                           "bhkPCollisionObject",
                           "bhkBlendCollisionObject"]:
            self.warn(f"Found an unknown type of collision: {c.blockname}")
            return None
        if not c.body: return None

        name_ext = bone.blender_name if bone else parentObj.name if parentObj else ""

        if bone:
            xf = self.import_xf @ transform_to_matrix(bone.global_transform)
        else:
            xf = parentObj.matrix_world
        sh = self.import_collision_body(c.body, xf)
        if not sh:
            self.warn(f"{parentObj.name} has unsupported collision shape")
            return
        
        sh['pynCollisionFlags'] = bhkCOFlags(c.flags).fullname

        if parentObj:
            if parentObj.type == 'ARMATURE' and bone:
                bn = self.blender_name(bone.name)
                if bn in parentObj.data.bones:
                    pb = parentObj.pose.bones[bn]
                    constr = pb.constraints.new(type='COPY_TRANSFORMS')
                    constr.target = sh
                else:
                    self.warn(f"Bone is missing: {bone.name}")
            else:
                constr = parentObj.constraints.new('COPY_TRANSFORMS')
                constr.target = sh
            constr.name = ('bhkCollisionConstraint')

        return sh

    # ----- End Collisions ----


    # ----- Begin Animations ----

    # def import_interpolator(self, ti:NiTransformInterpolator, 
    #                         target_node:bpy.types.Object, 
    #                         action:bpy.types.Action, 
    #                         group_name:str, 
    #                         path_name:str, 
    #                         parentxf:Matrix):
    #     """
    #     Import an interpolator, including its data block.

    #     - Returns the rotation mode that must be set on the target. If this interpolator
    #       is using XYZ rotations, the rotation mode must be set to Euler. 
    #     """
    #     rotation_mode = "QUATERNION"

    #     # ti, the parent NiTransformInterpolator, has the transform-to-global necessary
    #     # for this animation. It matches the transform of the target being animated.
    #     have_parent_rotation = False
    #     if max(ti.properties.rotation[:]) > 3e+38 or min(ti.properties.rotation[:]) < -3e+38:
    #         tiq = Quaternion()
    #     else:
    #         have_parent_rotation = True
    #         tiq = Quaternion(ti.properties.rotation)
    #     qinv = tiq.inverted()
    #     # qinv = (parentxf.to_3x3() @ qinv.to_matrix()).to_quaternion()
    #     tiv = Vector(ti.properties.translation)
    #     # Some interpolators have bogus translations. Dunno why.
    #     if tiv[0] <= -1e+30 or tiv[0] >= 1e+30: tiv[0] = 0
    #     if tiv[1] <= -1e+30 or tiv[1] >= 1e+30: tiv[1] = 0
    #     if tiv[2] <= -1e+30 or tiv[2] >= 1e+30: tiv[2] = 0

    #     tixf = MatrixLocRotScale(ti.properties.translation,
    #                              Quaternion(ti.properties.rotation),
    #                              [1.0]*3)
    #     # tixf = parentxf @ tixf
    #     tixf.invert()

    #     locbase = tixf.translation
    #     rotbase = tixf.to_euler()
    #     quatbase = tixf.to_quaternion()
    #     scalebase = -ti.properties.scale
    #     td = ti.data
    #     fps = self.context.scene.render.fps

    #     if path_name:
    #         path_prefix = path_name + "."
    #     else:
    #         path_prefix = ""

    #     if td.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
    #         rotation_mode = "XYZ"
    #         if td.xrotations or td.yrotations or td.zrotations:
    #             curveX = action.fcurves.new(path_prefix + "rotation_euler", index=0, action_group=group_name)
    #             curveY = action.fcurves.new(path_prefix + "rotation_euler", index=1, action_group=group_name)
    #             curveZ = action.fcurves.new(path_prefix + "rotation_euler", index=2, action_group=group_name)

    #             if len(td.xrotations) == len(td.yrotations) and len(td.xrotations) == len(td.zrotations):
    #                 for x, y, z in zip(td.xrotations, td.yrotations, td.zrotations):
    #                     # In theory the X/Y/Z dimensions do not have to have key frames at
    #                     # the same time signatures. But an Euler rotation needs all 3.
    #                     # Probably they will all line up because generating them any other
    #                     # way is surely hard. So hope for that and post a warning if not.
    #                     if not (NearEqual(x.time, y.time) and NearEqual(x.time, z.time)):
    #                         self.warn(f"Keyframes do not align for '{path_name}. Animations may be incorrect.")

    #                     # Need to apply the parent rotation. If we stay in Eulers, we may
    #                     # have gimbal lock. If we convert to quaternions, we may lose the
    #                     # distinction between +180 and -180, which are different things
    #                     # for animations. So only apply the parent rotation if there is
    #                     # one; in those cases we're just hoping it comes out right.
    #                     ve = Euler(Vector((x.value, y.value, z.value)), 'XYZ')
    #                     if have_parent_rotation:
    #                         ke = ve.copy()
    #                         kq = ke.to_quaternion()
    #                         vq = qinv @ kq
    #                         ve = vq.to_euler()
    #                     curveX.keyframe_points.insert(x.time * fps + 1, ve[0])
    #                     curveY.keyframe_points.insert(y.time * fps + 1, ve[1])
    #                     curveZ.keyframe_points.insert(z.time * fps + 1, ve[2])
                        
    #             else:
    #                 # This method of getting the inverse of the Euler doesn't always
    #                 # work, maybe because of gimbal lock.
    #                 ve = tiq.to_euler()

    #                 for i, k in enumerate(td.xrotations):
    #                     val = k.value - ve[0]
    #                     curveX.keyframe_points.insert(k.time * fps + 1, val)
    #                 for i, k in enumerate(td.yrotations):
    #                     val = k.value - ve[1]
    #                     curveY.keyframe_points.insert(k.time * fps + 1, val)
    #                 for i, k in enumerate(td.zrotations):
    #                     val = k.value - ve[2]
    #                     curveZ.keyframe_points.insert(k.time * fps + 1, val)
        
    #     elif td.properties.rotationType in [NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY]:
    #         rotation_mode = "QUATERNION"

    #         curveW = action.fcurves.new(path_prefix + "rotation_quaternion", index=0, action_group=group_name)
    #         curveX = action.fcurves.new(path_prefix + "rotation_quaternion", index=1, action_group=group_name)
    #         curveY = action.fcurves.new(path_prefix + "rotation_quaternion", index=2, action_group=group_name)
    #         curveZ = action.fcurves.new(path_prefix + "rotation_quaternion", index=3, action_group=group_name)

    #         for i, k in enumerate(td.qrotations):
    #             kq = Quaternion(k.value)
    #             # Auxbones animations are not correct yet, but they seem to need something
    #             # different from animations on the full skeleton.
    #             if self.auxbones:
    #                 vq = kq 
    #             else:
    #                 vq = qinv @ kq 

    #             curveW.keyframe_points.insert(k.time * fps + 1, vq[0])
    #             curveX.keyframe_points.insert(k.time * fps + 1, vq[1])
    #             curveY.keyframe_points.insert(k.time * fps + 1, vq[2])
    #             curveZ.keyframe_points.insert(k.time * fps + 1, vq[3])

    #     elif td.properties.rotationType == NiKeyType.NO_INTERP:
    #         pass
    #     else:
    #         self.warn(f"Nif contains unimplemented rotation type at {path_name}: {td.properties.rotationType}")

    #     # Seems like a value of + or - infinity in the Transform
    #     if len(td.translations) > 0:
    #         curveLocX = action.fcurves.new(path_prefix + "location", index=0, action_group=group_name)
    #         curveLocY = action.fcurves.new(path_prefix + "location", index=1, action_group=group_name)
    #         curveLocZ = action.fcurves.new(path_prefix + "location", index=2, action_group=group_name)
    #         for k in td.translations:
    #             v = Vector(k.value)

    #             if self.auxbones:
    #                 pass 
    #             else:
    #                 v = v - tiv
    #             curveLocX.keyframe_points.insert(k.time * fps + 1, v[0])
    #             curveLocY.keyframe_points.insert(k.time * fps + 1, v[1])
    #             curveLocZ.keyframe_points.insert(k.time * fps + 1, v[2])

    #     return rotation_mode


    # def import_color_controller(self, seq:NiSequence, block:ControllerLink):
    #     """Import one controlled block."""
    #     if block.node_name in self.nif.nodes:
    #         target_node = self.nif.nodes[block.node_name]

    #         if target_node._handle in self.objects_created:
    #             target_obj = self.objects_created[target_node._handle]
    #         else:
    #             self.warn(f"Target object was not imported: {block.node_name}")
    #             return
    #     else:
    #         self.warn(f"Target block not found in nif. Is it corrupt? ({block.node_name})")

    #     action_group = "Color Property Transforms"
    #     path_name = None
    #     action_name = f"{block.node_name}_{seq.name}"

        
    # def import_transform_controller(self, seq:NiSequence, block:ControllerLink):
    #     """Import one controlled block."""
    #     xf = Matrix.Identity(4)
        
    #     if block.node_name in self.nif.nodes:
    #         target_node = self.nif.nodes[block.node_name]

    #         if target_node._handle in self.objects_created:
    #             target_obj = self.objects_created[target_node._handle]
    #         else:
    #             self.warn(f"Target object was not imported: {block.node_name}")
    #             return
    #         action_group = "Object Transforms"
    #         path_name = None
    #         action_name = f"{block.node_name}_{seq.name}"
    #     else:
    #         # Armature may have had bone names converted or not. Check both ways.
    #         name = block.node_name
    #         if name not in self.armature.data.bones:
    #             name = self.blender_name(name)
    #             if name not in self.armature.data.bones:
    #                 name = None
    #         if name:
    #             action_group = name
    #             path_name = f'pose.bones["{action_group}"]'
    #             target_obj = self.armature
    #             action_name = seq.name
    #             xf = self.armature.data.bones[name].matrix_local.copy()
    #         else:
    #             self.warn(f"Controller target not found: {block.node_name}")
    #             return 

    #     fps = self.context.scene.render.fps
    #     if not target_obj.animation_data:
    #         target_obj.animation_data_create()

    #     new_action = None
    #     if action_group != "Object Transforms":
    #         new_action = target_obj.animation_data.action

    #     if not new_action:
    #         new_action = bpy.data.actions.new(action_name)
    #         try:
    #             new_action.frame_start = seq.properties.startTime * fps + 1
    #             new_action.frame_end = seq.properties.stopTime * fps + 1
    #             new_action.use_frame_range = True
    #             new_action.use_fake_user = True
    #         except:
    #             pass
    #         new_action.asset_mark()

    #     rotmode = self.import_interpolator(
    #         block.interpolator, 
    #         target_obj, 
    #         new_action, 
    #         action_group,
    #         path_name, 
    #         xf)
        
    #     if action_group == "Object Transforms":
    #         target_obj.rotation_mode = rotmode
    #     else:
    #         target_obj.pose.bones[name].rotation_mode = rotmode

    #     if not target_obj.animation_data.action:
    #         target_obj.animation_data.action = new_action


    # def import_controlled_block(self, seq:NiSequence, block:ControllerLink):
    #     """Import one controlled block."""
    #     if block.controller_type == "NiTransformController":
    #         self.import_transform_controller(seq, block)
    #     elif block.controller_type == 'BSEffectShaderPropertyColorController':
    #         self.import_color_controller(seq, block)
    #     else:
    #         self.warn(f"Nif has unknown controller type: {block.controller_type}")
    #         return


    # def import_sequences(self, seq):
    #     """Import a single controller sequence."""
    #     self.context.scene.frame_end = 1 + int(
    #         (seq.properties.stopTime - seq.properties.startTime) * self.context.scene.render.fps)
    #     for cb in seq.controlled_blocks:
    #         self.import_controlled_block(seq, cb)
        

    def import_controller_seq(self, cseq:NiControllerSequence):
        """Import a ControllerSequence node and children."""
        if not self.armature:
            return
        
        if self.armature.animation_data:
            self.armature.animation_data.action = None

        for cb in cseq.controlled_blocks:
            self.import_controlled_block(cseq, cb)

        if self.armature.animation_data and self.armature.animation_data.action:
            bpy.context.scene.frame_end \
                = int(self.armature.animation_data.action.curve_frame_range[1])
    
    # def import_animations(self, ctrlr: NiTimeController):
    #     """Import the animation defined by this controller."""
    #     if not self.do_import_anims: return
        
        # if ctrlr and hasattr(ctrlr, "sequences"): 
        #     for seq in ctrlr.sequences.values():
        #         self.import_sequences(seq)



    # ----- End Animations ----


    def import_nif(self):
        """Import a single file."""
        log.info(f"Importing {self.nif.game} file {self.nif.filepath}")
        
        # Each file gets its own root object in Blender.
        self.root_object = None

        if self.nif.rootNode.blockname == "NiControllerSequence":
            # Top-level node of a KF animation file is a Controller Sequence. 
            # Import it and done.
            self.import_controller_seq(self.nif.rootNode)
            return

        self.is_facegen = ("BSFaceGenNiNodeSkinned" in self.nif.nodes)
        if self.is_facegen: self.do_import_pose = False
        # Import the root node
        self.import_ninode(None, self.nif.rootNode)

        # Import shapes
        for s in self.nif.shapes:
            if self.nif.game in ['FO4', 'FO76'] and is_facebones(s.bone_names):
                self.nif.dict = fo4FaceDict
            self.nif.dict.use_niftools = self.rename_bones_nift
            self.import_shape(s)

        orphan_shapes = set([o for o in self.objects_created.values() 
                             if o.parent==None and not 'pynRoot' in o])
            
        if self.mesh_only:
            for obj in self.loaded_meshes:
                sh = self.nodes_loaded[obj.name]
                self.set_object_xf(sh, obj)
        else:
            # Make armature
            if len(self.nif.shapes) == 0:
                log.info(f"No shapes in nif, importing bones as skeleton")
                if not self.armature:
                    self.armature = self.make_armature(self.collection)
                self.add_bones_to_arma(self.armature, self.nif, self.nif.nodes.keys())
                self.imported_armatures.append(self.armature)
                self.connect_armature(self.armature)
                self.group_bones(self.armature)
            else:
                # List of armatures available for shapes
                if self.armature:
                    self.imported_armatures = [self.armature] 

                if self.do_apply_skinning:
                    for obj in self.loaded_meshes:
                        sh = self.nodes_loaded[obj.name]
                        self.ref_compat = self.is_compatible_skeleton(obj.matrix_local, sh, self.reference_skel)
                        self.set_object_xf(sh, obj)
                        if sh.has_skin_instance:
                            target_arma, target_xf = self.find_compatible_arma(obj, self.imported_armatures)
                            self.armature = target_arma
                            new_arma = self.set_parent_arma(target_arma, obj, sh, target_xf) #target_xf)
                            if self.is_facegen: self.facegen_cleanup(obj)
                            if not target_arma:
                                self.imported_armatures.append(new_arma)
                                self.armature = new_arma
                            orphan_shapes.discard(obj)

                for arma in self.imported_armatures:
                    if self.do_create_bones:
                        bonenames = [n.name for n in self.nif.nodes.values()
                                     if n.blockname == 'NiNode']
                        self.add_bones_to_arma(arma, self.nif, bonenames)
                    self.connect_armature(arma)
                    self.group_bones(arma)
                    self.animate_armature(self.armature)
    
            # Gather up any NiNodes that weren't captured any other way 
            self.import_loose_ninodes(self.nif)

            # Import nif-level elements
            self.import_connect_points()
        
            # Import top-level animations
            if self.nif.rootNode.controller:
                controller.ControllerHandler.import_block(
                    self.nif.rootNode.controller, self)
            # self.import_animations(self.nif.rootNode.controller)

            # Everything gets parented to the child connect point, if any.
            for o in self.objects_created.values(): 
                if self.created_child_cp and o.parent == None and o != self.created_child_cp:
                    o.parent = self.created_child_cp
                    if o in orphan_shapes: orphan_shapes.remove(o)

        # THink this should not be here...
        # controller.ControllerHandler.import_block(self.nif.rootNode.controller, self)

        # Anything not yet parented gets put under the root.
        for o in orphan_shapes:
            o.parent = self.root_object


    def import_tris(self):
        """Import any tri files associated with the nif."""
        imported_meshes = [x for x in self.objects_created.values() if x.type == 'MESH']
        tripfile = find_trip(self.nif)
        if tripfile:
            import_trip(tripfile, imported_meshes)
        elif len(imported_meshes) == 1:
            # No tri files if there's a trip file; 
            # must be only a single mesh to have a tri file.
            trifiles = find_tris(self.nif)
            for tf in trifiles:
                import_tri(tf, [x for x in self.objects_created.values() if x.type == 'MESH'][0])



    def merge_shapes(self, filename, obj_list, new_filename, new_obj_list):
        """Merge new_obj_list into obj_list as shape keys. 
           If filenames follow PyNifly's naming conventions, create a shape key for the 
           base shape and rename the shape keys appropriately.
        """
        # Can name shape keys to our convention if they end with underscore-something and everything
        # before the underscore is the same
        fn_parts = filename.split('_')
        new_fn_parts = new_filename.split('_')
        rename_keys = len(fn_parts) > 1 and len(new_fn_parts) > 1 and fn_parts[0:-1] == new_fn_parts[0:-1]
        obj_shape_name = '_' + fn_parts[-1]

        for obj, newobj in zip(obj_list, new_obj_list):
            ObjectSelect([obj, newobj])
            ObjectActive(obj)

            if rename_keys:
                if (not obj.data.shape_keys) or (not obj.data.shape_keys.key_blocks) \
                        or (obj_shape_name not in [s.name for s in obj.data.shape_keys.key_blocks]):
                    if not obj.data.shape_keys:
                        obj.shape_key_add(name='Basis')
                    obj.shape_key_add(name=obj_shape_name)

            bpy.ops.object.join_shapes()
            bpy.data.objects.remove(newobj)

            if rename_keys:
                obj.data.shape_keys.key_blocks[-1].name = '_' + new_fn_parts[-1]


    def connect_children_parents(self, parent_shapes, child_shapes):
        """If any of the child connect points in dictionary child_shapes should connect to the
        parent connect points in dictionary parent_shapes, parent them up
        """
        for connectname, parent in parent_shapes.items():
            # Find children that should connect to this parent. Could be more than one. 
            # Also the same child may be in the dictionary more than once under different
            # spellings of the name.
            try: 
                child = child_shapes[connectname]
                if not child.parent:
                    child.parent = parent
            except:
                pass


    def execute(self):
        """Perform the import operation as previously defined"""
        NifFile.clear_log()

        self.connect_parents = [p for p in self.context.selected_objects \
                                if p.name.startswith('BSConnectPointParents')]
        self.loaded_parent_cp = {}
        self.loaded_child_cp = {}
        prior_vertcounts = []
        prior_fn = ''

        # Only use the active object if it's selected. Too confusing otherwise.
        if self.context.object and self.context.object.select_get():
            if self.context.object.type == "ARMATURE":
                self.armature = self.context.object
                log.info(f"Current object is an armature, parenting shapes to {self.armature.name}")
            elif self.context.object.type == "EMPTY" and self.context.object.name.startswith("BSConnectPointParents"):
                self.add_to_parents(self.context.object)
                log.info(f"Current object is a parent connect point, parenting shapes to {self.context.object.name}")
            elif self.context.object.type == 'MESH':
                prior_vertcounts = [len(self.context.object.data.vertices)]
                self.loaded_meshes = [self.context.object]
                log.info(f"Current object is a mesh, will import as shape key if possible: {self.context.object.name}")

        log.info(str(self))

        for this_file in self.filename_list:
            fn, fext = os.path.splitext(os.path.basename(this_file))

            if fext.lower() == ".nif":
                self.nif = NifFile(this_file)
            elif fext in [".hkx", ".xml"]:
                self.nif = hkxSkeletonFile(this_file)
            else:
                ValueError("Import file of unknown type.")
            if not self.reference_skel:
                self.reference_skel = self.nif.reference_skel

            prior_shapes = None
            this_vertcounts = [len(s.verts) for s in self.nif.shapes]
            if self.do_import_shapes:
                if len(this_vertcounts) > 0 and this_vertcounts == prior_vertcounts:
                    #log.debug(f"Vert count of all shapes in nif match shapes in prior nif. They will be loaded as a single shape with shape keys")
                    prior_shapes = self.loaded_meshes
            
            self.loaded_meshes = []
            self.mesh_only = (prior_shapes is not None)
            self.import_nif()
            if self.do_import_tris:
                self.import_tris()

            if prior_shapes:
                ##log.debug(f"Merging shapes: {[s.name for s in prior_shapes]} << {[s.name for s in self.loaded_meshes]}")
                self.merge_shapes(prior_fn, prior_shapes, fn, self.loaded_meshes)
                self.loaded_meshes = prior_shapes
            else:
                prior_vertcounts = this_vertcounts
                prior_fn = fn

        # Connect up all the children loaded in this batch with all the parents loaded in this batch
        self.connect_children_parents(self.loaded_parent_cp, self.loaded_child_cp)


    @classmethod
    def do_import(cls, filename, chargen="chargen", scale=1.0):
        imp = NifImporter(filename, chargen=chargen, scale=scale)
        imp.execute()
        return imp


class ImportNIF(bpy.types.Operator, ImportHelper):
    """Load a NIF File"""
    bl_idname = "import_scene.pynifly"
    bl_label = "Import NIF (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".nif"
    filter_glob: StringProperty(
        default="*.nif",
        options={'HIDDEN'},
    )

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},)

    do_create_bones: bpy.props.BoolProperty(
        name="Create bones",
        description="Create vanilla bones as needed to make skeleton complete.",
        default=CREATE_BONES_DEF)

    # scale_factor: bpy.props.FloatProperty(
    #     name="Scale correction",
    #     description="Scale import - set to 0.1 to match NifTools default",
    #     default=SCALE_DEF)

    use_blender_xf: bpy.props.BoolProperty(
        name="Use Blender orientation",
        description="Use Blender's orientation and scale",
        default=BLENDER_XF_DEF) # type: ignore

    do_rename_bones: bpy.props.BoolProperty(
        name="Rename bones",
        description="Rename bones to conform to Blender's left/right conventions.",
        default=RENAME_BONES_DEF) # type: ignore

    do_import_animations: bpy.props.BoolProperty(
        name="Import animations",
        description="Import any animations embedded in the nif.",
        default=IMPORT_ANIMS_DEF) # type: ignore

    do_import_collisions: bpy.props.BoolProperty(
        name="Import collisions",
        description="Import any collisions embedded in the nif.",
        default=IMPORT_COLLISIONS_DEF) # type: ignore

    do_import_tris: bpy.props.BoolProperty(
        name="Import tri files",
        description="Import any tri files that appear to be associated with the nif.",
        default=IMPORT_COLLISIONS_DEF) # type: ignore

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename bones as per NifTools",
        description="Rename bones using NifTools' naming scheme to conform to Blender's left/right conventions.",
        default=RENAME_BONES_NIFT_DEF) # type: ignore

    do_import_shapes: bpy.props.BoolProperty(
        name="Import as shape keys",
        description="Import similar objects as shape keys where possible on multi-file imports.",
        default=IMPORT_SHAPES_DEF) # type: ignore

    do_apply_skinning: bpy.props.BoolProperty(
        name="Apply skin to mesh",
        description="Applies any transforms defined in shapes' partitions to the final mesh.",
        default=APPLY_SKINNING_DEF) # type: ignore

    do_import_pose: bpy.props.BoolProperty(
        name="Create armature from pose position",
        description="Creates any armature from the bone NiNode (pose) position.",
        default=IMPORT_POSE_DEF
    ) # type: ignore

    # do_estimate_offset: bpy.props.BoolProperty(
    #     name="Apply estimated shape offset",
    #     description="Positions skinned shapes at an offset estimated from bone transforms.",
    #     default=ESTIMATE_OFFSET_DEF
    # ) # type: ignore

    reference_skel: bpy.props.StringProperty(
        name="Reference skeleton",
        description="Reference skeleton to use for the bone hierarchy",
        default="") # type: ignore

    # # For debugging. Updating the UI when debugging tends to crash blender.
    # update_ui: bpy.props.BoolProperty(
    #     name="Update UI",
    #     default=True,
    #     options={'HIDDEN'}
    # )

    def __init__(self):
        if bpy.context.object and bpy.context.object.select_get() and bpy.context.object.type == 'ARMATURE':
            # We are loading into an existing armature. The various settings should match.
            arma = bpy.context.object
            self.use_blender_xf = ('PYN_BLENDER_XF' in arma and arma['PYN_BLENDER_XF'])
            self.do_rename_bones = ('PYN_RENAME_BONES' in arma and arma['PYN_RENAME_BONES'])
            # When loading into an armature, ignore the nif's bind position--use the
            # armature's.
            self.do_import_pose = True


    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False
        return True


    def execute(self, context):
        LogStart(bl_info, "IMPORT", "NIF")
        status = {'FINISHED'}

        #log.debug(f"Filepaths are {[f.name for f in self.files]}")
        #log.debug(f"Filepath is {self.filepath}")

        fullfiles = ''
        try:
            NifFile.Load(nifly_path)

            # bpy.ops.object.select_all(action='DESELECT')

            folderpath = os.path.dirname(self.filepath)
            filenames = [f.name for f in self.files]
            if len(filenames) > 0:
                fullfiles = [os.path.join(folderpath, f.name) for f in self.files]
            else:
                fullfiles = [self.filepath]
            imp = NifImporter(fullfiles, chargen=CHARGEN_EXT_DEF)
            imp.context = context
            if context.view_layer.active_layer_collection: 
                imp.collection = context.view_layer.active_layer_collection.collection
            imp.do_create_bones = self.do_create_bones
            # imp.roll_bones_nift = self.roll_bones
            imp.do_rename_bones = self.do_rename_bones
            imp.rename_bones_nift = self.rename_bones_niftools
            imp.do_import_shapes = self.do_import_shapes
            imp.do_import_anims = self.do_import_animations
            imp.do_import_collisions = self.do_import_collisions
            imp.do_import_tris = self.do_import_tris
            imp.do_apply_skinning = self.do_apply_skinning
            imp.do_import_pose = self.do_import_pose
            # imp.do_estimate_offset = self.do_estimate_offset
            if self.reference_skel:
                imp.reference_skel = NifFile(self.reference_skel)
            if self.use_blender_xf:
                imp.import_xf = blender_import_xf
            imp.execute()
        
            # Cleanup. Select all shapes imported, except the root node.
            objlist = [x for x in imp.objects_created.values() if x.type=='MESH']
            highlight_objects(objlist, context)
            if (not objlist) and imp.armature:
                objlist.append(imp.armature)
            ObjectSelect(objlist)

            status = set()
            for w in imp.warnings:
                #log.debug(f"Message is {w}")
                status.add(w[0])
                self.report({w[0]}, w[1])

            LogFinish("IMPORT", fullfiles, status, False)

        except:
            log.exception("Import of nif failed")
            self.report({"ERROR"}, "Import of nif failed, see console window for details")
            status = {'CANCELLED'}
            LogFinish("IMPORT", fullfiles, status, True)
                
        return {'FINISHED'}


# ### ---------------------------- TRI Files -------------------------------- ###

def create_shape_keys(obj, tri: TriFile):
    """Adds the shape keys in tri to obj 
        """
    mesh = obj.data
    if mesh.shape_keys is None:
        #log.debug(f"Adding first shape key to {obj.name}")
        newsk = obj.shape_key_add()
        mesh.shape_keys.use_relative=True
        newsk.name = "Basis"
        mesh.update()

    base_verts = tri.vertices

    dict = None
    obj_arma = [m.object for m in obj.modifiers if m.type == 'ARMATURE']
    if obj_arma:
        g = best_game_fit(obj_arma[0].data.bones)
        if g != "":
            dict = gameSkeletons[g]

    for game_morph_name, morph_verts in sorted(tri.morphs.items()):
        if dict and game_morph_name in dict.morph_dic_blender:
            morph_name = dict.morph_dic_blender[game_morph_name]
        else:
            morph_name = game_morph_name
        if morph_name not in mesh.shape_keys.key_blocks:
            newsk = obj.shape_key_add()
            newsk.name = morph_name

            obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
            #This is a pointer, not a copy
            mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
            # We may be applying the morphs to a different shape than the one stored in 
            # the tri file. But the morphs in the tri file are absolute locations, as are 
            # shape key locations. So we need to calculate the offset in the tri and apply that 
            # to our shape keys.
            for key_vert, morph_vert, base_vert in zip(mesh_key_verts, morph_verts, base_verts):
                key_vert.co[0] += morph_vert[0] - base_vert[0]
                key_vert.co[1] += morph_vert[1] - base_vert[1]
                key_vert.co[2] += morph_vert[2] - base_vert[2]
        
            mesh.update()

def create_trip_shape_keys(obj, trip:TripFile):
    """Adds the shape keys in trip to obj."""
    mesh = obj.data
    verts = mesh.vertices

    if mesh.shape_keys is None or "Basis" not in mesh.shape_keys.key_blocks:
        newsk = obj.shape_key_add()
        newsk.name = "Basis"

    offsetmorphs = trip.shapes[obj.name]
    for morph_name, morph_verts in sorted(offsetmorphs.items()):
        newsk = obj.shape_key_add()
        newsk.name = ">" + morph_name

        obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
        #This is a pointer, not a copy
        mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
        for vert_index, offsets in morph_verts:
            for i in range(3):
                mesh_key_verts[vert_index].co[i] = verts[vert_index].co[i] + offsets[i]
        
        mesh.update()

    obj.active_shape_key_index = 0


def import_trip(filepath, target_objs):
    """Import a BS Tri file. 
       These TRI files do not have full shape data so they have to be matched to one of the 
       objects in target_objs.
       return = (set of result types: NOT_TRIP or WARNING. Null result means success,
                 list of shape names found in trip file)
       """
    result = set()
    shapelist = []
    trip = TripFile.from_file(filepath)
    if trip.is_valid:
        shapelist = trip.shapes.keys()
        for shapename, offsetmorphs in trip.shapes.items():
            matchlist = [o for o in target_objs if o.name == shapename]
            if len(matchlist) == 0:
                log.warning(f"BS Tri file shape does not match any selected object: {shapename}")
                result.add('WARNING')
            else:
                create_trip_shape_keys(matchlist[0], trip)
    else:
        result.add('NOT_TRIP')

    return (result, shapelist)


def import_tri(filepath, cobj):
    """Import the tris from filepath into cobj
       If cobj is None or if the verts don't match, create a new object
       """
    tri = TriFile.from_file(filepath)
    if not type(tri) == TriFile:
        log.error(f"Error reading tri file")
        return None

    new_object = None

    # Check whether selected object should receive shape keys
    if cobj and cobj.type == "MESH" and len(cobj.data.vertices) == len(tri.vertices):
        new_object = cobj
        new_mesh = new_object.data
        log.info(f"Verts match, loading tri into existing shape {new_object.name}")

    if new_object is None:
        new_mesh = bpy.data.meshes.new(os.path.basename(filepath))
        new_mesh.from_pydata(tri.vertices, [], tri.faces)
        new_object = bpy.data.objects.new(new_mesh.name, new_mesh)

        for f in new_mesh.polygons:
            f.use_smooth = True

        new_mesh.update(calc_edges=True, calc_edges_loose=True)
        new_mesh.validate(verbose=True)

        if tri.import_uv:
            mesh_create_uv(new_mesh, tri.uv_pos)
   
        bpy.context.scene.collection.objects.link(new_object)
        ObjectActive(new_object)
        ObjectSelect([new_object])

    create_shape_keys(new_object, tri)
    new_object.active_shape_key_index = 0

    return new_object


class ImportTRI(bpy.types.Operator, ImportHelper):
    """Load a TRI File"""
    bl_idname = "import_scene.pyniflytri"
    bl_label = "Import TRI (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".tri"
    filter_glob: StringProperty(
        default="*.tri",
        options={'HIDDEN'},
    )

    def execute(self, context):
        LogStart(bl_info, "IMPORT", "TRI")
        status = {'FINISHED'}

        try:
            
            imp = "IMPORT TRIP"
            v, s = import_trip(self.filepath, context.selected_objects)
            if 'NOT_TRIP' in v:
                imp = "IMPORT TRI"
                cobj = bpy.context.object
                obj = import_tri(self.filepath, cobj)
                if obj == cobj:
                    imp = f"IMPORT TRI into {cobj.name}"
                else:
                    imp = "IMPORT TRI as new object"
            else:
                # Have a TRIP file
                imp = f"IMPORT TRIP {list(s)}"
            status = status.union(v)

            try:   
                # TODO: Fix this for 4.0     
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        ctx = bpy.context.copy()
                        ctx['area'] = area
                        ctx['region'] = area.regions[-1]
                        bpy.ops.view3d.view_selected(ctx)
            except:
                pass

            LogFinish(imp, self.filepath, status, False)
            if 'WARNING' in status:
                self.report({"ERROR"}, "Import completed with warnings, see console for details")

        except:
            log.exception("Import of tri failed")
            self.report({"ERROR"}, "Import of tri failed, see console window for details")
            status = {'CANCELLED'}
            LogFinish(imp, self.filepath, status, True)
        
        return status.intersection({'FINISHED', 'CANCELLED'})



################################################################################
#                                                                              #
#                             KF ANIMATION IMPORT                              #
#                                                                              #
################################################################################


class ImportKF(bpy.types.Operator, ExportHelper):
    """Import Blender animation to an armature"""

    bl_idname = "import_scene.pynifly_kf"
    bl_label = 'Import KF (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".kf"
    filter_glob: StringProperty(
        default="*.kf",
        options={'HIDDEN'},
    )

    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )

    directory: StringProperty()

    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False

        if (not context.object) or context.object.type != "ARMATURE":
            log.error("Cannot import KF: Active object must be an armature.")
            return False

        if context.object.mode != 'OBJECT':
            log.error("Must be in Object Mode to import")
            return False

        return True
    

    def __init__(self):
        self.nif:NifFile = None
        self.armature = None
    

    def execute(self, context):
        res = set()

        if not self.poll(context):
            self.report({"ERROR"}, f"Cannot run importer--see system console for details")
            return {'CANCELLED'} 

        LogStart(bl_info, "IMPORT", "KF")

        try:
            NifFile.Load(nifly_path)
            folderpath = os.path.dirname(self.filepath)
            filenames = [f.name for f in self.files]
            if filenames:
                fullfiles = [os.path.join(folderpath, f.name) for f in self.files]
            else:
                fullfiles = [self.filepath]
            for filename in fullfiles:
                filepath = os.path.join(self.directory, filename)
                imp = NifImporter(filepath)
                imp.context = context
                imp.armature = context.object
                imp.do_import_anims = True
                imp.nif = NifFile(filepath)
                imp.import_nif()

        except Exception as e:
            log.exception(f"Import of KF failed: {e}")
            self.report({"ERROR"}, "Import of KF failed, see console window for details.")
            status = {'CANCELLED'}
            LogFinish("IMPORT", self.filepath, status, True)

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

################################################################################
#                                                                              #
#                             HKX ANIMATION IMPORT                              #
#                                                                              #
################################################################################


class ImportHKX(bpy.types.Operator, ExportHelper):
    """Import HKX file--either a skeleton or an animation to an armature"""

    bl_idname = "import_scene.pynifly_hkx"
    bl_label = 'Import HKX file (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"
    filter_glob: StringProperty(
        default="*.hkx",
        options={'HIDDEN'},
    )

    use_blender_xf: bpy.props.BoolProperty(
        name="Use Blender orientation",
        description="Use Blender's orientation and scale",
        default=BLENDER_XF_DEF)

    do_rename_bones: bpy.props.BoolProperty(
        name="Rename bones",
        description="Rename bones to conform to Blender's left/right conventions.",
        default=RENAME_BONES_DEF)

    do_import_animations: bpy.props.BoolProperty(
        name="Import animations",
        description="Import any animations embedded in the nif.",
        default=IMPORT_ANIMS_DEF)

    do_import_collisions: bpy.props.BoolProperty(
        name="Import collisions",
        description="Import any collisions embedded in the nif.",
        default=IMPORT_COLLISIONS_DEF)

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename bones as per NifTools",
        description="Rename bones using NifTools' naming scheme to conform to Blender's left/right conventions.",
        default=RENAME_BONES_NIFT_DEF)
    
    reference_skel: bpy.props.StringProperty(
        name="Reference skeleton",
        description="HKX reference skeleton to use for animation binding",
        default="")


    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False
        if not hkxcmd_path:
            log.error("hkxcmd.exe not found--HKX I/O not available.")
            return False
        return True
    

    def __init__(self):
        self.kf:NifFile = None
        self.armature = None
        self.errors = set()
        self.xml_filepath = None

        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            if 'PYN_SKELETON_FILE'in obj:
                self.reference_skel = obj['PYN_SKELETON_FILE']
    

    def execute(self, context):
        res = set()
        self.context = context
        self.fps = context.scene.render.fps

        try:
            LogStart(bl_info, "IMPORT", "HKX")

            NifFile.Load(nifly_path)
            xmltools.XMLFile.SetPath(hkxcmd_path)
            self.xmlfile = xmltools.XMLFile(self.filepath, self)
            if self.xmlfile.contains_skeleton:
                self.import_skeleton()

            if self.xmlfile.contains_animation:
                if self.reference_skel:
                    self.reference_skel = self.reference_skel.strip('"')
                    fp, ext = os.path.splitext(self.reference_skel)
                    if ext.lower() != ".hkx":
                        self.error(f"Must have an HKX file to use as reference skeleton.")
                        return {'CANCELLED'}
                    self.reference_skel_short = tmp_filepath(self.reference_skel)
                    copyfile(self.reference_skel, self.reference_skel_short)

                if not context.object:
                    self.error(f"Must have selected object for animation.")
                    return {'CANCELLED'}
                if not self.reference_skel:
                    self.error(f"Must provide a reference skeleton for the animation.")
                    return {'CANCELLED'}
                if self.reference_skel:
                    context.object['PYN_SKELETON_FILE'] = self.reference_skel

                res.add(self.import_animation())

        except:
            log.exception("Import of HKX file failed")
            self.error("Import of HKX failed, see console window for details")
            res.add('CANCELLED')
            
        LogFinish("IMPORT", self.filepath, self.errors, False)

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

    def warn(self, msg):
        self.report({"WARNING"}, msg)
        self.errors.add("WARNING")

    def error(self, msg):
        self.report({"ERROR"}, msg)
        self.errors.add("ERROR")

    def info(self, msg):
        self.report({"INFO"}, msg)


    def import_skeleton(self):
        """self.xmlfile has a skeleton in it. Import the skeleton."""
        imp = NifImporter([self.xmlfile.xml_filepath])
        imp.context = self.context
        if self.context.view_layer.active_layer_collection: 
            imp.collection = self.context.view_layer.active_layer_collection.collection
        imp.do_create_bones = False
        imp.do_rename_bones = self.do_rename_bones
        imp.rename_bones_nift = self.rename_bones_niftools
        imp.do_import_anims = self.do_import_animations
        imp.do_import_collisions = False
        imp.do_apply_skinning = False
        if self.use_blender_xf:
            imp.import_xf = blender_import_xf
        imp.execute()
        objlist = [x for x in imp.objects_created.values() if x.type=='MESH']
        if imp.armature:
            objlist.append(imp.armature)
        highlight_objects(objlist, self.context)


    def import_animation(self):
        """self.xmlfile has an animation in it. Import the animation."""
        kf_file = self.make_kf(self.xmlfile.hkx_filepath)
        if not kf_file:
            return('CANCELLED')
        else:
            imp = NifImporter(self.kf_filepath)
            imp.context = self.context
            imp.armature = self.context.object
            imp.do_import_anims = True
            imp.nif = kf_file
            imp.import_nif()
            self.import_annotations()
            highlight_objects([imp.armature], self.context)
            self.info('Import of HKX animation completed successfully')
            return('FINISHED')


    def make_kf(self, filepath_working) -> NifFile:
        """
        Creates a kf file from a hkx file.  
        
        Returns 
        * KF file is opened and returned as a NifFile. 
        """
        self.kf_filepath = tmp_filepath(filepath_working, ext=".kf")

        if not self.kf_filepath:
            raise RuntimeError(f"Could not create temporary file")
        
        stat = subprocess.run([hkxcmd_path, 
                               "EXPORTKF", 
                               self.reference_skel_short, 
                               filepath_working, 
                               self.kf_filepath], 
                               capture_output=True, check=True)
        if stat.stderr:
            s = stat.stderr.decode('utf-8').strip()
            if not s.startswith("Exporting"):
                self.error(s)
                return None
        if not os.path.exists(self.kf_filepath):
            self.error(f"Failed to create {self.kf_filepath}")
            return None
        self.info(f"Temporary KF file created: {self.kf_filepath}")

        return NifFile(self.kf_filepath)
    

    def import_annotations(self):
        """Import text annotations from the XML file associated with this import."""
        if not self.xml_filepath or not os.path.exists(self.xml_filepath):
            return
        
        xmlfile = xml.parse(self.xml_filepath)
        xmlroot = xmlfile.getroot()
        annotation_tracks = next(x for x in xmlroot.iter('hkparam') if x.attrib['name'] == "annotationTracks")
        annotations = next(a for a in annotation_tracks.iter('hkparam') if a.attrib['name'] == 'annotations')
        for a in annotations.iter('hkobject'):
            t = None
            txt = None
            for p in a.iter('hkparam'):
                if p.attrib['name'] == "time":
                    t = float(p.text)
                if p.attrib['name'] == "text":
                    txt = p.text
            if t and txt:
                self.context.scene.timeline_markers.new(txt, frame=int(t*self.fps))



# ### ---------------------------- EXPORT -------------------------------- ###

def clean_filename(fn):
    s = fn.strip()
    if s.endswith(":ROOT"): s = s[0:-5]
    return "".join(c for c in s if (c.isalnum() or c in "._- "))

def select_all_faces(mesh):
    """ Make sure all mesh elements are visible and all faces are selected """
    bpy.ops.object.mode_set(mode = 'OBJECT') # Have to be in object mode

    for v in mesh.vertices:
        v.hide = False
    for e in mesh.edges:
        e.hide = False
    for p in mesh.polygons:
        p.hide = False
        p.select = True


def check_partitions(vi1, vi2, vi3, weights):
    """ Chcek whether the = 3 verts (specified by index) all have the same partitions 
        weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts
       """
    p1 = set([k for k in weights[vi1].keys() if is_partition(k)])
    p2 = set([k for k in weights[vi2].keys() if is_partition(k)])
    p3 = set([k for k in weights[vi3].keys() if is_partition(k)])
    return len(p1.intersection(p2, p3)) > 0


def trim_to_four(weights, arma):
    """ Trim to the 4 heaviest weights in the armature
        weights = [(group_name: weight), ...] """
    if arma:
        lst = filter(lambda p: p[0] in arma.data.bones, weights)
        notlst = filter(lambda p: p[0] not in arma.data.bones, weights)
        sd = sorted(lst, reverse=True, key=lambda item: item[1])[0:4]
        sd.extend(notlst)
        return dict(sd)
    else:
        return dict(weights)


def has_uniform_scale(obj):
    """ Determine whether an object has uniform scale """
    return NearEqual(obj.scale[0], obj.scale[1]) and NearEqual(obj.scale[1], obj.scale[2])


def extract_vert_info(obj, mesh, arma, target_key='', scale_factor=1.0):
    """Returns 3 lists of equal length with one entry each for each vertex
    *   verts = [(x, y, z)... ] - base or as modified by target-key if provided
    *   weights = [{group-name: weight}... ] - 1:1 with verts list
    *   dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
            shape-key is the blender name.
        """
    weights = []
    morphdict = {}
    msk = mesh.shape_keys

    sf = Vector((1,1,1))
    if not has_uniform_scale(obj):
        # Apply non-uniform scale to verts directly
        sf = obj.scale

    if target_key != '' and msk and target_key in msk.key_blocks.keys():
        verts = [(v.co * sf / scale_factor)[:] for v in msk.key_blocks[target_key].data]
    else:
        verts = [(v.co * sf / scale_factor)[:] for v in mesh.vertices]

    for i, v in enumerate(mesh.vertices):
        vert_weights = []
        for vg in v.groups:
            try:
                vgn = obj.vertex_groups[vg.group].name
                vert_weights.append([vgn, vg.weight])
            except:
                log.error(f"ERROR: Vertex #{v.index} references invalid group #{vg.group}")
        
        weights.append(trim_to_four(vert_weights, arma))
    
    if msk: # and target_key == '' 
        for sk in msk.key_blocks:
            morphdict[sk.name] = [(v.co * sf)[:] for v in sk.data]

    return verts, weights, morphdict


def tag_unweighted(obj, bones):
    """ Find and return verts that are not weighted to any of the given bones 
        result = (v_index, ...) list of indices into the vertex list
    """
    unweighted_verts = []
    for v in obj.data.vertices:
        maxweight = 0.0
        if len(v.groups) > 0:
            maxweight = max([g.weight for g in v.groups])
        if maxweight < 0.0001:
            unweighted_verts.append(v.index)
    return unweighted_verts


def create_group_from_verts(obj, name, verts):
    """ Create a vertex group from the list of vertex indices.
    Use the existing group if any """
    if name in obj.vertex_groups.keys():
        g = obj.vertex_groups[name]
    else:
        g = obj.vertex_groups.new(name=name)
    g.add(verts, 1.0, 'ADD')


def best_game_fit(bonelist):
    """ Find the game that best matches the skeleton """
    boneset = set([b.name for b in bonelist])
    maxmatch = 0
    matchgame = ""
    for g, s in gameSkeletons.items():
        n = s.matches(boneset)
        if n > maxmatch:
            maxmatch = n
            matchgame = g
    n = fo4FaceDict.matches(boneset)
    if n > maxmatch:
        matchgame = "FO4"
    return matchgame


def expected_game(nif, bonelist):
    """ Check whether the nif's game is the best match for the given bonelist """
    matchgame = best_game_fit(bonelist)
    return matchgame == "" or matchgame == nif.game or \
        (matchgame in ['SKYRIM', 'SKYRIMSE'] and nif.game in ['SKYRIM', 'SKYRIMSE'])


def is_partition(name):
    """ Check whether <name> is a valid partition or segment name """
    if SkyPartition.name_match(name) >= 0:
        return True

    if FO4Segment.name_match(name) >= 0:
        return True

    parent_name, subseg_id, material = FO4Subsegment.name_match(name)
    if parent_name:
        return True

    return False


def partitions_from_vert_groups(obj):
    """ Return dictionary of Partition objects for all vertex groups that match the partition 
        name pattern. These are all partition objects including subsegments.
    """
    val = {}
    if obj.vertex_groups:
        vg_sorted = sorted([g.name for g in obj.vertex_groups])
        for nm in vg_sorted:
            vg = obj.vertex_groups[nm]
            skyid = SkyPartition.name_match(vg.name)
            if skyid >= 0:
                val[vg.name] = SkyPartition(part_id=skyid, flags=0, name=vg.name)
            else:
                segid = FO4Segment.name_match(vg.name)
                if segid >= 0:
                    val[vg.name] = FO4Segment(part_id=len(val), index=segid, name=vg.name)
                else:
                    # Check if this is a subsegment. All segs sort before their subsegs, 
                    # so it will already have been created if it exists separately
                    parent_name, subseg_id, material = FO4Subsegment.name_match(vg.name)
                    if parent_name:
                        if not parent_name in val:
                            # Create parent segments if not there
                            val[parent_name] = FO4Segment(len(val), 0, parent_name)
                        p = val[parent_name]
                        val[vg.name] = FO4Subsegment(len(val), subseg_id, material, p, name=vg.name)
    
    return val


def all_vertex_groups(weightdict):
    """ Return the set of group names that have non-zero weights """
    val = set()
    for g, w in weightdict.items():
        if w > 0.0001:
            val.add(g)
    return val


def get_loop_color(mesh, loopindex, cm, am):
    """ Return the color of the vertex-in-loop at given loop index using
        cm = color map to use
        am = alpha map to use """
    vc = mesh.vertex_colors
    alpha = 1.0
    color = (1.0, 1.0, 1.0)
    if cm:
        color = cm[loopindex].color
    if am:
        acolor = am[loopindex].color
        alpha = (acolor[0] + acolor[1] + acolor[2])/3

    return (color[0], color[1], color[2], alpha)
    

def mesh_from_key(editmesh, verts, target_key):
    faces = []
    for p in editmesh.polygons:
        faces.append([editmesh.loops[lpi].vertex_index for lpi in p.loop_indices])
    newverts = [v.co[:] for v in editmesh.shape_keys.key_blocks[target_key].data]
    newmesh = bpy.data.meshes.new(editmesh.name)
    newmesh.from_pydata(newverts, [], faces)
    return newmesh


def get_common_shapes(obj_list) -> set:
    """Return the shape keys found in any of the given objects """
    res = None
    for obj in obj_list:
        o_shapes = set()
        if obj.data.shape_keys:
            o_shapes = set(obj.data.shape_keys.key_blocks.keys())
        if res:
            res = res.union(o_shapes)
        else:
            res = o_shapes
    if res:
        res = list(res)
    return res


def get_with_uscore(str_list):
    if str_list:
        return list(filter((lambda x: x[0] == '_'), str_list))
    else:
        return []


class NifExporter:
    """ Object that handles the export process independent of Blender's export class """
    def __init__(self, filepath, game, export_flags=pynFlags.RENAME_BONES, chargen="chargen", scale=1.0):
        self.filepath = filepath
        self.game = game
        self.nif = None
        self.trip = None
        self.warnings = set()
        self.armature = None
        self.facebones = None
        self.do_rename_bones = RENAME_BONES_DEF
        self.rename_bones_nift = RENAME_BONES_NIFT_DEF
        self.preserve_hierarchy = PRESERVE_HIERARCHY_DEF
        self.write_bodytri = WRITE_BODYTRI_DEF
        self.export_pose = EXPORT_POSE_DEF
        self.export_modifiers = EXPORT_MODIFIERS_DEF
        self.export_colors = EXPORT_COLORS_DEF
        self.active_obj = None
        self.scale = scale
        self.root_object = None
        self.export_xf = Matrix.Identity(4)

        # Objects that are to be written out
        self.objects = [] # Ordered list of objects to write--first my have root node info
        self.bg_data = set()
        self.str_data = set()
        self.cloth_data = set()
        self.grouping_nodes = set()
        self.bsx_flag = None
        self.inv_marker = None
        self.furniture_markers = set()
        self.connect_parent = set()
        self.connect_child = set()
        self.trippath = ''
        self.chargen_ext = chargen
        self.writtenbones = {}
        
        # Shape keys that start with underscore trigger a separate file export
        # for each shape key
        self.file_keys = []  
        self.objs_unweighted = set()
        self.objs_scale = set()
        self.objs_mult_part = set()
        self.objs_no_part = set()
        self.arma_game = []
        self.bodytri_written = False

        # Dictionary of objects written to nif. {Blender object name: NiNode}
        self.objs_written = {}

        self.message_log = []

    def __str__(self):
        flags = []
        if self.do_rename_bones: flags.append("RENAME_BONES")
        if self.rename_bones_nift: flags.append("RENAME_BONES_NIFT")
        if self.preserve_hierarchy: flags.append("PRESERVE_HIERARCHY")
        if self.write_bodytri: flags.append("WRITE_BODYTRI")
        if self.export_pose: flags.append("EXPORT_POSE")
        if self.export_modifiers: flags.append("EXPORT_MODIFIERS")
        if self.export_colors: flags.append("EXPORT_COLORS")
        return f"""
        Exporting objects: {[o.name for o in self.objects]}
            flags: {'|'.join(flags)}
            string data: {self.str_data}
            BG data: {self.bg_data}
            cloth data: {self.cloth_data}
            armature: {self.armature.name if self.armature else 'None'}
            facebones: {self.facebones.name if self.facebones else 'None'}
            parent connect points: {self.connect_parent}
            child connect points: {self.connect_child}
            orientation: {self.export_xf.to_euler()}
            scale factor: {round(self.export_scale, 4)}
            shapes: {self.file_keys}
            to file: {self.filepath}
        """

    def log_warning(self, msg):
            log.warning(msg)
            self.warnings.add('WARNING')

    @property
    def export_scale(self):
        """Return the inverse of the scale factor on the export transform. Returning
        the inverse because all the scale factors are expected to match the import.
        """
        return 1/self.export_xf.to_scale()[0]
    
    def nif_name(self, blender_name):
        if self.do_rename_bones or self.rename_bones_nift:
            return self.nif.nif_name(blender_name)
        else:
            return blender_name

    def unique_name(self, obj):
        """
        Return a unique node name for the Blender object. Use the root of the Blender name
        if possible, because that might match to a name in a trip file. Otherwise use the
        full Blender name, and if that fails make a unique name.
        """
        names = self.nif.getAllShapeNames()
        simplename = nonunique_name(obj)
        if simplename not in names: return simplename
        if obj.name not in names: return obj.name
        for i in range(0, 100):
            n = simplename + "-" + f"{i:03}"
            if n not in names: return n
        return obj.name

    def export_shape_data(self, obj, shape):
        """ Export a shape's extra data """
        edlist = []
        strlist = []
        for ch in obj.children:
             if 'NiStringExtraData_Name' in ch:
                strlist.append( (ch['NiStringExtraData_Name'], ch['NiStringExtraData_Value']) )
                self.objs_written[ch.name] = shape
             if 'BSBehaviorGraphExtraData_Name' in ch:
                edlist.append( (ch['BSBehaviorGraphExtraData_Name'], 
                               ch['BSBehaviorGraphExtraData_Value']) )
                self.objs_written[ch.name] = shape
        if len(strlist) > 0:
            shape.string_data = strlist
    
        if len(edlist) > 0:
            shape.behavior_graph_data = edlist


    def add_armature(self, arma):
        """Add an armature to the export"""
        facebones_arma = (self.game in ['FO4', 'FO76']) and (is_facebones(arma.data.bones.keys()))
        if facebones_arma and self.facebones is None:
            self.facebones = arma
        if (not facebones_arma) and (self.armature is None):
            self.armature = arma 


    def add_object(self, obj):
        """
        Adds the given object to the objects to export. Object may be mesh, armature,
        or anything else. 
        
        * If an armature is selected, all child objects are exported 
        * If a skinned mesh is selected, all armatures referenced in armature modifiers
          are considered for export.
        """
        if obj in self.objects or obj in self.grouping_nodes: return

        if obj.type == 'ARMATURE':
            self.add_armature(obj)
            for c in obj.children:
                self.add_object(c)

        elif obj.type == 'MESH':
            # Export the mesh, but use its parent and use any armature modifiers
            self.objects.append(obj)
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    # Don't add any of the armature's other children unless they were
                    # independently selected.
                    self.add_armature(mod.object)

        elif obj.type == 'CAMERA':
            self.inv_marker = obj

        elif obj.type == 'EMPTY':
            if 'BSBehaviorGraphExtraData_Name' in obj.keys():
                self.bg_data.add(obj)

            elif 'NiStringExtraData_Name' in obj.keys():
                self.str_data.add(obj)

            elif 'BSClothExtraData_Name' in obj.keys():
                self.cloth_data.add(obj)

            elif 'BSXFlags_Name' in obj.keys():
                self.bsx_flag = obj

            elif obj.name.startswith("BSFurnitureMarkerNode"):
                self.furniture_markers.add(obj)

            elif obj.name.startswith("BSConnectPointParents"):
                self.connect_parent.add(obj)

            elif obj.name.startswith("BSConnectPointChildren"):
                self.connect_child.add(obj)

            elif obj.type == 'EMPTY':
                self.grouping_nodes.add(obj)
                for c in obj.children:
                    if not c.hide_get(): self.add_object(c)


    def set_objects(self, objects:list):
        """ 
        Set the objects to export from the given list of objects 
        """
        for x in objects:
            self.add_object(x)
            if "pynRoot" in x:
                self.root_object = x
        self.file_keys = get_with_uscore(get_common_shapes(self.objects))


    # --------- DO THE EXPORT ---------

    def export_tris(self, obj, verts, tris, uvs, morphdict):
        """ Export a tri file to go along with the given nif file, if there are shape keys 
            and it's not a faceBones nif.
            dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
        """
        result = {'FINISHED'}

        if obj.data.shape_keys is None or len(morphdict) == 0:
            return result

        fpath = os.path.split(self.nif.filepath)
        fname = os.path.splitext(fpath[1])

        if fname[0].endswith('_faceBones'):
            return result

        fname_tri = os.path.join(fpath[0], fname[0] + ".tri")
        fname_chargen = os.path.join(fpath[0], fname[0] + self.chargen_ext + ".tri")
        if self.chargen_ext != CHARGEN_EXT_DEF: obj['PYN_CHARGEN_EXT'] = self.chargen_ext 

        # Don't export anything that starts with an underscore or asterisk
        objkeys = obj.data.shape_keys.key_blocks.keys()
        export_keys = set(filter((lambda n: n[0] not in ('_', '*') and n != 'Basis'), objkeys))
        expression_morphs = self.nif.dict.expression_filter(export_keys)
        trip_morphs = set(filter((lambda n: n[0] == '>'), objkeys))
        # Leftovers are chargen candidates
        leftover_morphs = export_keys.difference(expression_morphs).difference(trip_morphs)
        chargen_morphs = self.nif.dict.chargen_filter(leftover_morphs)

        if len(expression_morphs) > 0 and len(trip_morphs) > 0:
            log.warning(f"Found both expression morphs and BS tri morphs in shape {obj.name}. May be an error.")
            result = {'WARNING'}

        if len(expression_morphs) > 0:
            tri = TriFile()
            tri.vertices = verts
            tri.faces = tris
            tri.uv_pos = uvs
            tri.face_uvs = tris # (because 1:1 with verts)
            for m in expression_morphs:
                if m in self.nif.dict.morph_dic_game:
                    triname = self.nif.dict.morph_dic_game[m]
                else:
                    triname = m
                if m in morphdict:
                    tri.morphs[triname] = morphdict[m]
    
            log.info(f"Generating tri file '{fname_tri}'")
            tri.write(fname_tri) # Only expression morphs to write at this point

        if len(chargen_morphs) > 0:
            tri = TriFile()
            tri.vertices = verts
            tri.faces = tris
            tri.uv_pos = uvs
            tri.face_uvs = tris # (because 1:1 with verts)
            for m in chargen_morphs:
                if m in morphdict:
                    tri.morphs[m] = morphdict[m]
    
            log.info(f"Generating tri file '{fname_chargen}'")
            tri.write(fname_chargen, chargen_morphs)

        if len(trip_morphs) > 0:
            expdict = {}
            for k, v in morphdict.items():
                if k[0] == '>':
                    n = k[1:]
                    expdict[n] = v
            self.trip.set_morphs(self.objs_written[obj.name].name, expdict, verts)
            
        return result


    def export_extra_data(self):
        """ Export any top-level extra data represented as Blender objects. 
            Sets self.bodytri_done if one of the extra data nodes represents a bodytri
        """
        sdlist = []
        for st in self.str_data:
            if st['NiStringExtraData_Name'] != 'BODYTRI' or self.game not in ['FO4', 'FO76']:
                # FO4 bodytris go at the top level
                sdlist.append( (st['NiStringExtraData_Name'], st['NiStringExtraData_Value']) )
                self.objs_written[st.name] = self.nif
                self.bodytri_written |= (st['NiStringExtraData_Name'] == 'BODYTRI')

        if len(sdlist) > 0:
            self.nif.string_data = sdlist
        
        bglist = []
        for bg in self.bg_data: 
            bglist.append( (bg['BSBehaviorGraphExtraData_Name'], 
                            bg['BSBehaviorGraphExtraData_Value'], 
                            bg['BSBehaviorGraphExtraData_CBS']) )
            self.objs_written[bg.name] = self.nif

        if len(bglist) > 0:
            self.nif.behavior_graph_data = bglist 

        cdlist = []
        for cd in self.cloth_data:
            cdlist.append( (cd['BSClothExtraData_Name'], 
                            codecs.decode(cd['BSClothExtraData_Value'], "base64")) )
            self.objs_written[cd.name] = self.nif

        if len(cdlist) > 0:
            self.nif.cloth_data = cdlist 

        if self.bsx_flag:
            self.nif.rootNode.bsx_flags = [self.bsx_flag['BSXFlags_Name'],
                                  BSXFlags.parse(self.bsx_flag['BSXFlags_Value'])]
            self.objs_written[self.bsx_flag.name] = self.nif

        if self.inv_marker:
            inv_rot, inv_zoom = cam_to_inv(self.inv_marker.matrix_world, self.inv_marker.data.lens)

            self.nif.rootNode.inventory_marker = [
                self.inv_marker['BSInvMarker_Name'], 
                inv_rot[0],
                inv_rot[1],
                inv_rot[2],
                inv_zoom]
            self.objs_written[self.inv_marker.name] = self.nif

        fmklist = []
        for fm in self.furniture_markers:
            buf = FurnitureMarkerBuf()
            buf.offset = (fm.location / self.scale)[:]
            buf.heading = fm.rotation_euler.z
            buf.animation_type = FurnAnimationType.GetValue(fm['AnimationType'])
            buf.entry_points = FurnEntryPoints.parse(fm['EntryPoints'])
            fmklist.append(buf)
        
        if fmklist:
            self.nif.furniture_markers = fmklist

        connect_par = []
        for cp in self.connect_parent:
            buf = ConnectPointBuf()
            buf.name = cp.name.split("::")[1].encode('utf-8')
            if cp.parent and cp.parent.type != 'ARMATURE':
                buf.parent = nonunique_name(cp.parent).encode('utf-8')
                buf.translation[0], buf.translation[1], buf.translation[2] \
                    = cp.matrix_world.translation[:]
                buf.rotation[0], buf.rotation[1], buf.rotation[2], buf.rotation[3] \
                    = cp.matrix_world.to_quaternion()[:]
                buf.scale = cp.matrix_world.to_scale()[0] / CONNECT_POINT_SCALE
            elif cp.parent and cp.parent.type == 'ARMATURE':
                parentname = ''
                if 'pynConnectParent' in cp:
                    parentname = cp['pynConnectParent']
                elif 'PYN_CONNECT_PARENT' in cp:
                    # Older representation of parent
                    parentname = cp['PYN_CONNECT_PARENT']
                buf.parent = parentname.encode('utf-8')
                parentnamebl = self.nif.dict.blender_name(parentname)
                if parentnamebl in cp.parent.data.bones:
                    parentbone = cp.parent.data.bones[parentnamebl]
                    mx = parentbone.matrix_local.inverted() @ cp.matrix_local
                    buf.translation[0] = mx.translation[0]
                    buf.translation[1] = mx.translation[1]
                    buf.translation[2] = mx.translation[2]
                    buf.rotation[0], buf.rotation[1], buf.rotation[2], buf.rotation[3] \
                        = mx.to_quaternion()[:]
                    buf.scale = mx.to_scale()[0] / CONNECT_POINT_SCALE
            
            connect_par.append(buf)
        if connect_par:
            self.nif.connect_points_parent = connect_par

        child_names = []
        for cp in self.connect_child:
            self.nif.connect_pt_child_skinned = cp['PYN_CONNECT_CHILD_SKINNED']
            ##log.debug(f"Extending child names with {[cp[x] for x in cp.keys() if x != 'PYN_CONNECT_CHILD_SKINNED' and x.startswith('PYN_CONNECT_CHILD')]}")
            child_names.extend([cp[x] for x in cp.keys() if x != 'PYN_CONNECT_CHILD_SKINNED' and x.startswith('PYN_CONNECT_CHILD')])
        if child_names:
            ##log.debug(f"Writing connect point children: {child_names}")
            self.nif.connect_points_child = child_names


    def export_bhkCapsuleShape(self, s, xform):
        """Export capsule shape. 
        Returns (shape, coordinates)
        shape = collision shape in the nif object
        coordinates = center of the shape in Blender world coordinates) 
        """ 
        cshape = None
        center = Vector()

        # Capsule covers the extent of the shape
        props = bhkCapsuleShapeProps(s)
        props.load(s, ignore=CAPSULE_SHAPE_IGNORE)

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.game] # * self.export_scale

        point1, point2, r = find_capsule_ends(s)
        if 'bhkRadius' in s:
            r = s['bhkRadius'] 
        else:
            r = r / sf
        props.bhkRadius = props.bhkRadius1 = props.bhkRadius2 = r

        for i, val in enumerate(point1):
            props.point1[i] = val/sf
        for i, val in enumerate(point2):
            props.point2[i] = val/sf

        cshape = self.nif.add_shape(props)

        return cshape, s.location, Quaternion()


    def export_bhkBoxShape(self, box, xform) -> CollisionShape:
        """Export box shape. Box is assumed to have 6 faces, all right angles, any orientation.
        * box = collision shape blender object.
        * xform = Unused. Transform is set by parent.
        Returns (shape, coordinates)
        * shape = collision shape in the nif object
        * coordinates = center of the shape (in Blender world coordinates) 
        * rotation = rotation that must be applied to the shape
        """ 
        # The transform on the box object has to match the transform on the box target, 
        # because that's how collisions are implemented in Blender. So if the box is rotated,
        # we have to recover the rotation from the vert locations.
        cshape = None
        center = Vector()
        try:
            # Box covers the extent of the shape, whatever it is
            p = bhkBoxShapeProps(box)
            p.load(box, ignore=BOX_SHAPE_IGNORE)

            # Have to take the export scale factor into account.
            sf = (HAVOC_SCALE_FACTOR * game_collision_sf[self.game] * (1/self.export_xf.to_scale()[0]))
            ctr, d, r = find_box_info(box)
            if len(d) == 3:
                bhkDim = (d / sf) / 2
                for i in range(0, 3):
                    p.bhkDimensions[i] = bhkDim[i]

                cshape = self.nif.add_shape(p)
        except Exception as e:
            self.log_warning(f"Unexpected error: {e}")

        if not cshape:
            self.log_warning(f'Cannot create collision shape from {box.name}')
            
        return cshape, ctr, r
        

    def export_bhkConvexVerticesShape(self, s, xform):
        """
        Export a convex vertices shape that wraps around whatever the import shape
        is.
        """
        if self.root_object:
            effectiveXF = self.root_object.matrix_world @ s.matrix_world @ xform
        else:
            effectiveXF = s.matrix_world @ xform 

        p = bhkConvexVerticesShapeProps(s)
        bm = bmesh.new()
        bm.from_mesh(s.data)
        bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=True)

        # Now have hull in local coordinates. We need them in world coordinates, respecting
        # whatever transform the export has.
        # OR, bmesh put the verts in world coordinates so we just need to apply the xport
        # transform.
        myscale = (self.export_xf @ s.matrix_world).to_scale()
        verts1 = [myscale * v.co for v in bm.verts]
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        verts = [(v / sf) for v in verts1]

        # Need a normal for each face
        norms = []
        for face in s.data.polygons:
            # Length needs to be distance from origin to face along this normal
            facevert = s.data.vertices[face.vertices[0]].co
            vintersect = geometry.distance_point_to_plane(
                Vector((0,0,0)), facevert, face.normal)
            n = Vector((face.normal[0], face.normal[1], face.normal[2], vintersect/sf))
            append_if_new(norms, n, 0.1)
        
        cshape = self.nif.add_shape(p, vertices=verts, normals=norms)

        return cshape, Vector(), Quaternion()


    def export_bhkConvexTransformShape(self, s, xform):
        """
        s is the collision shape to be controlled by the bhkConvexTransformShape, which
        isn't represented directly in the Blender file at all.
        """
        childxf = self.export_xf @ xform @ s.matrix_local
        childnode, childcenter, childrot = self.export_collision_shape([s], childxf)

        # Collision shape rotation is in the shape's own coordinates. Since this is a
        # child and we are setting the transform, we need the rotation in global
        # coordnates.
        childrot = s.matrix_local.to_quaternion() @ childrot

        if not childnode:
            return None, None, None

        props = bhkConvexTransformShapeProps(s)
        if s.rigid_body.use_margin:
            props.bhkRadius = s.rigid_body.collision_margin # / HAVOC_SCALE_FACTOR

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        targlocw, targqw, targscalew = xform.decompose()

        # We want the transform to be exactly the controlled shape's world transform.
        # If we have a parent list shape, ignore its location because it doesn't have
        # one in the nif.
        childtransl = childcenter - targlocw
        childtransl.rotate(targqw.inverted())
        childtransl = childtransl * self.export_xf.to_scale()
        childtransl = childtransl / sf

        havocxf = MatrixLocRotScale(childtransl, childrot, Vector((1,1,1,)))
        cshape = self.nif.add_shape(props, transform=havocxf)
        cshape.child = childnode
        return cshape, xform.translation, Quaternion()


    def export_bhkListShape(self, s, xform):
        """
        Collisions actually come from the list shape's children. Since collision shapes
        don't have transforms themselves, there has to be an intermediate
        bhkConvexTransform shape to position them.
        """
        props = bhkListShapeProps(s)
        cshape = self.nif.add_shape(props)

        xf = s.matrix_local @ xform
        for ch in s.children: 
            if ch.name.startswith("bhk"):
                shapenode, nodetransl, noderot = self.export_bhkConvexTransformShape(ch, xf)
                if shapenode:
                    cshape.add_child(shapenode)

        return cshape, s.matrix_local.translation, Quaternion()


    def export_collision_shape(self, shape_list, xform=Matrix()):
        """
        Export the first collision shape in shape_list. 
        * shape_list = list of bhk*Shape objects. Should only be one.
        * xform = additional transform to apply. Shapes that position their verts
          explicitly must apply this transform. (Shapes that don't get their position set
          by the RigidBody.)
        
        Returns (shape, coordinates) 
        * shape = collision shape in the nif object 
        * coordinates = center of the shape (in Blender world coordinates) 
        * rotation = rotation to apply to the shape
        """
        for cs in shape_list:
            if cs.name.startswith("bhkBoxShape"):
                return self.export_bhkBoxShape(cs, xform)
            elif cs.name.startswith("bhkConvexVerticesShape"):
                return self.export_bhkConvexVerticesShape(cs, xform)
            elif cs.name.startswith("bhkListShape"):
                return self.export_bhkListShape(cs, xform)
            elif cs.name.startswith("bhkCapsuleShape"):
                return self.export_bhkCapsuleShape(cs, xform)
            elif cs.name.startswith("bhkConvexTransformShape"):
                return self.export_bhkConvexTransformShape(cs, xform)
            # TODO: Add bhkSphereShape
        return None, None, Quaternion()


    def export_collision_body(self, targobj, coll):
        """ 
        Export the collision body for the given collision.

        * targobj = Blender object that has the collision.
        * coll = Blender object representing the collision
        * colnode = Nif node representing the collision
        """
        # Blender's collision object has the same transform as the target (because that's
        # how we model collisions). But the (TBS)
        if not coll.rigid_body: return
        if 'pynRigidBody' not in coll: 
            bodytype = 'bhkRigidBody'
        else:
            bodytype = coll['pynRigidBody']

        # Gonna need relative locations but without the transform the root provides.
        rootinv = Matrix.Identity(4)
        if self.root_object:
            rootinv = self.root_object.matrix_world.inverted()
        
        have_bone = False
        try:
            targxf = self.export_xf @  targobj.matrix_local
            targparent = targobj
        except:
            try:
                # for pose bones
                targparent = targobj.id_data
                targxf = targobj.matrix
                have_bone = True
            except:
                # For edit bones
                targparent = targobj.id_data
                targxf = targobj.matrix_local
                have_bone = True
                
        cshape, ctr, rot = self.export_collision_shape([coll], targxf.inverted()) 
        if not cshape: return None

        props = bhkWorldObject.get_buffer(bodytype, values=coll)
        if props.bufType == PynBufferTypes.bhkRigidBodyBufType and cshape.needsTransform:
            props.bufType = PynBufferTypes.bhkRigidBodyTBufType
        elif props.bufType == PynBufferTypes.bhkRigidBodyTBufType and not cshape.needsTransform:
            props.bufType = PynBufferTypes.bhkRigidBodyBufType
         
        props.shapeID = cshape.id
        props.mass = coll.rigid_body.mass
        props.friction = coll.rigid_body.friction
        props.linearDamping = coll.rigid_body.linear_damping
        props.angularDamping = coll.rigid_body.angular_damping

        targloc, targq, targscale = targxf.decompose()
        targlocw, targqw, targscalew = (targparent.matrix_world @ targxf).decompose()

        # Use any rotation on the collision shape relative to the target's rotation.
        targq = coll.matrix_local.to_quaternion() @ rot.inverted()
        # rv = (rootinv @ ctr) - targloc
        rv = ctr - targlocw
        rv.rotate(targqw.inverted())
        rv = rv * self.export_xf.to_scale()

        if props.bufType == PynBufferTypes.bhkRigidBodyTBufType:
            props.rotation[0] = rot.x
            props.rotation[1] = rot.y
            props.rotation[2] = rot.z
            props.rotation[3] = rot.w

            props.translation[0] = rv.x/HAVOC_SCALE_FACTOR 
            props.translation[1] = rv.y/HAVOC_SCALE_FACTOR 
            props.translation[2] = rv.z/HAVOC_SCALE_FACTOR 
            props.translation[3] = 0

        elif props.bufType == PynBufferTypes.bhkSimpleShapePhantomBufType:
            mx = MatrixLocRotScale(rv/HAVOC_SCALE_FACTOR, targq, (1,1,1))
            for i, r in enumerate(mx):
                for j, v in enumerate(r):
                    props.transform[i][j] = v

        colnode = self.objs_written[coll.name]
        body_node = colnode.add_body(props)

        return body_node


    def export_collision_object(self, targobj, coll):
        """
        Export the given collision object. 
        targobj = Blender object with the collision.
        coll = Blender object representing the collision.
        """
        if coll.name in self.objs_written: return

        flags = None
        if 'pynCollisionFlags' in coll:
            flags = bhkCOFlags.parse(coll['pynCollisionFlags']).value

        try:
            targnode = self.objs_written[targobj.name]
        except:
            targnode = self.nif.nodes[targobj.name]
        colnode = targnode.add_collision(None, flags=flags)
        self.objs_written[coll.name] = colnode

        body = self.export_collision_body(targobj, coll) 


    def export_collisions(self, obj):
        """
        Export the object's collision. 
                
        Collision shapes are tied to their target with a copy-transforms constraint.
        """
        targobj = obj
        if obj.type == 'ARMATURE':
            collisions = []
            for pb in obj.pose.bones:
                for c in pb.constraints:
                    if c.type == 'COPY_TRANSFORMS':
                        collisions.append(c)
                        targobj = pb
        else:
            collisions = [x for x in obj.constraints if x.type == 'COPY_TRANSFORMS']
        if not collisions: return

        collshape = collisions[0].target
        if not collshape: return
        if collshape.name in self.objs_written: return

        self.export_collision_object(targobj, collshape)


    def get_loop_partitions(self, face, loops, weights):
        vi1 = loops[face.loop_start].vertex_index
        p = set([k for k in weights[vi1].keys() if is_partition(k)])
        for i in range(face.loop_start+1, face.loop_start+face.loop_total):
            vi = loops[i].vertex_index
            p = p.intersection(set([k for k in weights[vi].keys() if is_partition(k)]))
    
        if len(p) != 1:
            face_verts = [lp.vertex_index for lp in loops[face.loop_start:face.loop_start+face.loop_total]]
            if len(p) == 0:
                log.warning(f'Face {face.index} has no partitions')
                self.warnings.add('NO_PARTITION')
                self.objs_no_part.add(self.active_obj)
                create_group_from_verts(self.active_obj, NO_PARTITION_GROUP, face_verts)
                return 0
            elif len(p) > 1:
                log.warning(f'Face {face.index} has too many partitions: {p}')
                self.warnings.add('MANY_PARITITON')
                self.objs_mult_part.add(self.active_obj)
                create_group_from_verts(self.active_obj, MULTIPLE_PARTITION_GROUP, face_verts)

        return p.pop()


    def extract_face_info(self, mesh, uvlayer, loopcolors, weights, obj_partitions, use_loop_normals=False):
        """ Extract triangularized face info from the mesh. 
            Return 
            loops = [vert-index, ...] list of vert indices in loops. Triangularized, 
                so these are to be read in triples.
            uvs = [(u,v), ...] list of uv coordinates 1:1 with loops
            norms = [(x,y,z), ...] list of normal vectors 1:1 with loops
                --Normal vectors come from the loops, because they reflect whether the edges
                are sharp or the object has flat shading
            colors = [(r,g,b,a), ...] 1:1 with loops
            partition_map = [n, ...] list of partition IDs, 1:1 with tris 

        """
        loops = []
        uvs = []
        orig_uvs = []
        norms = []
        colors = []
        partition_map = []

        # Calculating normals messes up the passed-in UV, so get the data out of it first
        for f in mesh.polygons:
            for i in f.loop_indices:
                orig_uvs.append(uvlayer[i].uv[:])
                ##log.debug(f"....Adding uv index {uvlayer[i].uv[:]}")

        # CANNOT figure out how to get the loop normals correctly.  They seem to follow the
        # face normals even on smooth shading.  (TEST_NORMAL_SEAM tests for this.) So use the
        # vertex normal except when there are custom split normals.
        bpy.ops.object.mode_set(mode='OBJECT') #required to get accurate normals
        try:
            # Before Blender 4.0 have to calculate normals. 4.0 doesn't need it and throws
            # an error.
            mesh.calc_normals()
            mesh.calc_normals_split()
        except:
            pass

        def write_loop_vert(loopseg):
            """ Write one vert, given as a MeshLoop 
            """
            loops.append(loopseg.vertex_index)
            uvs.append(orig_uvs[loopseg.index])
            if loopcolors:
                colors.append(loopcolors[loopseg.index])
            if use_loop_normals:
                norms.append(loopseg.normal[:])
            else:
                norms.append(mesh.vertices[loopseg.vertex_index].normal[:])

        # Write out the loops as triangles, and partitions to match
        for f in mesh.polygons:
            if f.loop_total < 3:
                log.warning(f"Degenerate polygons on {mesh.name}: 0={l0}, 1={l1}")
            else:
                if obj_partitions and len(obj_partitions) > 0:
                    loop_partition = self.get_loop_partitions(f, mesh.loops, weights)
                l0 = mesh.loops[f.loop_start]
                l1 = mesh.loops[f.loop_start+1]
                for i in range(f.loop_start+2, f.loop_start+f.loop_total):
                    loopseg = mesh.loops[i]

                    write_loop_vert(l0)
                    write_loop_vert(l1)
                    write_loop_vert(loopseg)
                    if obj_partitions and len(obj_partitions) > 0:
                        if loop_partition:
                            partition_map.append(obj_partitions[loop_partition].id)
                        else:
                            log.warning(f"Writing first partition for face without partitions: {f.index}")
                            partition_map.append(next(iter(obj_partitions.values())).id)
                    l1 = loopseg

        return loops, uvs, norms, colors, partition_map


    def export_partitions(self, obj, weights_by_vert, tris):
        """ Export partitions described by vertex groups
            weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts. For 
                partitions, can assume the weights are 1.0
            tris = [(v1, v2, v3)...] where v1-3 are indices into the vertex list
            returns (partitions, tri_indices)
                partitions = list of partition objects
                tri_indices = list of paritition indices, 1:1 with the shape's tri list
        """
        partitions = partitions_from_vert_groups(obj)

        if len(partitions) == 0:
            return [], []

        partition_set = set(list(partitions.keys()))

        tri_indices = [0] * len(tris)

        for i, t in enumerate(tris):
            # All 3 have to be in the same vertex group to count
            vg0 = all_vertex_groups(weights_by_vert[t[0]])
            vg1 = all_vertex_groups(weights_by_vert[t[1]])
            vg2 = all_vertex_groups(weights_by_vert[t[2]])
            tri_partitions = vg0.intersection(vg1).intersection(vg2).intersection(partition_set)
            if len(tri_partitions) > 0:
                if len(tri_partitions) > 1:
                    log.warning(f"Found multiple partitions for tri {t} in object {obj.name}: {tri_partitions}")
                    self.warnings.add('MANY_PARITITON')
                    self.objs_mult_part.add(obj)
                    create_group_from_verts(obj, MULTIPLE_PARTITION_GROUP, t)

                # Triangulation may put some tris in two partitions. Just choose one--
                # exact division doesn't matter (if it did user should have put in an edge)
                tri_indices[i] = partitions[next(iter(tri_partitions))].id
            else:
                log.warning(f"Tri {t} is not assigned any partition")
                self.warnings.add('NO_PARTITION')
                self.objs_no_part.add(obj)
                create_group_from_verts(obj, NO_PARTITION_GROUP, t)

        return list(partitions.values()), tri_indices


    def extract_colors(self, mesh):
        """Extract vertex color data from the given mesh. Use the VERTEX_ALPHA color map
            for alpha values if it exists.
            Returns [c.color[:] for c in editmesh.vertex_colors.active.data]
                This is 1:1 with loops
            """
        try:
            vc = mesh.color_attributes
            active_color = vc.active_color
        except:
            vc = mesh.vertex_colors
            active_color = vc.active
        alphamap = None
        alphamapname = ''
        colormap = None
        colormapname = ''
        colorlen = 0
        if ALPHA_MAP_NAME in vc.keys():
            alphamap = vc[ALPHA_MAP_NAME].data
            alphamapname = ALPHA_MAP_NAME
            colorlen = len(alphamap)
        if alphamap and active_color and active_color.data == alphamap:
            # Alpha map is active--see if there's another map to use for colors. If not,
            # colors will be set to white
            for c in vc:
                if c.data != alphamap:
                    colormap = c.data
                    colormapname = c.name
                    break
        elif active_color:
            colormap = active_color.data
            colormapname = active_color.name
            colorlen = len(colormap)

        loopcolors = [(0.0, 0.0, 0.0, 0.0)] * colorlen
        for i in range(0, colorlen):
            if colormap:
                c = colormap[i].color[:]
            else:
                c = (1.0, 1.0, 1.0, 1.0)
            if alphamap:
                try:
                    a = Color(alphamap[i].color[0:3]).from_srgb_to_scene_linear()
                except:
                    a = Color(alphamap[i].color[0:3])
                c = (c[0], c[1], c[2], (a[0] + a[1] + a[2])/3)
            loopcolors[i] = c

        return loopcolors


    def extract_mesh_data(self, obj, arma, target_key):
        """ 
        Extract the triangularized mesh data from the given object
            obj = object being exported
            arma = controlling armature, if any. Needed so we can limit bone weights.
            target_key = shape key to export
        returns
            verts = list of XYZ vertex locations
            norms_new = list of XYZ normal values, 1:1 with verts
            uvmap_new = list of (u, v) values, 1:1 with verts
            colors_new = list of RGBA color values 1:1 with verts. May be None.
            tris = list of (t1, t2, t3) vert indices to define triangles
            weights_by_vert = [dict[group-name: weight], ...] 1:1 with verts
            morphdict = {shape-key: [verts...], ...} XXX>only if "target_key" is NOT specified
        NOTE this routine changes selection and switches to edit mode and back
        """
        loopcolors = None
        saved_sk = obj.active_shape_key_index
        
        try:
            ObjectSelect([obj])
            ObjectActive(obj)
                
            # This next little dance ensures the mesh.vertices locations are correct
            if self.export_modifiers:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                obj1 = obj.evaluated_get(depsgraph) 
            else:
                obj1 = obj           
            obj1.active_shape_key_index = 0
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.object.mode_set(mode = 'OBJECT')
            editmesh = obj1.data
            editmesh.update()
         
            verts, weights_by_vert, morphdict \
                = extract_vert_info(obj1, editmesh, arma, target_key, self.scale)
        
            # Pull out vertex colors first because trying to access them later crashes
            bpy.ops.object.mode_set(mode = 'OBJECT') # Required to get vertex colors
            if self.export_colors:
                try:
                    c = editmesh.color_attributes.active_color
                    loopcolors = self.extract_colors(editmesh)
                except:
                    if len(editmesh.vertex_colors) > 0:
                        loopcolors = self.extract_colors(editmesh)
        
            # Apply shape key verts to the mesh so normals will be correct.  If the mesh has
            # custom normals, fukkit -- use the custom normals and assume the deformation
            # won't be so great that it looks bad.
            bpy.ops.object.mode_set(mode = 'OBJECT') 
            uvlayer = editmesh.uv_layers.active.data
            if target_key != '' and \
                editmesh.shape_keys and \
                target_key in editmesh.shape_keys.key_blocks.keys() and \
                not editmesh.has_custom_normals:
                editmesh = mesh_from_key(editmesh, verts, target_key)
                    
            # Extracting and triangularizing
            partitions = partitions_from_vert_groups(obj1)
            loops, uvs, norms, loopcolors, partition_map = \
                self.extract_face_info(
                    editmesh, uvlayer, loopcolors, weights_by_vert, partitions,
                    use_loop_normals=editmesh.has_custom_normals)
        
            mesh_split_by_uv(verts, loops, norms, uvs, weights_by_vert, morphdict)

            # Make uv and norm lists 1:1 with verts (rather than with loops)
            uvmap_new = [(0.0, 0.0)] * len(verts)
            norms_new = [(0.0, 0.0, 0.0)] * len(verts)
            for i, vi in enumerate(loops):
                assert vi < len(verts), f"Error: Invalid vert index in loops: {vi} >= {len(verts)}"
                uvmap_new[vi] = uvs[i]
                norms_new[vi] = norms[i]
        
            ## Our "loops" list matches 1:1 with the mesh's loops. So we can use the polygons
            ## to pull the loops
            tris = []
            for i in range(0, len(loops), 3):
                tris.append((loops[i], loops[i+1], loops[i+2]))
        
            colors_new = None
            if len(loopcolors) > 0:
                colors_new = [(0.0, 0.0, 0.0, 0.0)] * len(verts)
                for i, lp in enumerate(loops):
                    colors_new[lp] = loopcolors[i]
        
        finally:
            obj.active_shape_key_index = saved_sk
            pass

        return verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, \
            morphdict, partitions, partition_map


    def export_node(self, obj:bpy_types.Object, parent=None) -> NiNode:
        """Export a NiNode for the given Blender object."""
        xf = make_transformbuf(apply_scale_xf(obj.matrix_local, 1))
        ninode = self.nif.add_node(obj.name, xf, parent)
        self.objs_written[obj.name] = ninode
        self.export_collisions(obj)
        return ninode
   

    def export_shape_parents(self, obj) -> NiNode:
        """Export any parent NiNodes the shape might need 

        Returns the handle of the nif node that should be the parent of the shape (may be
        None).
        """
        # ancestors list contains all parents from root to obj's immediate parent
        ancestors = []
        p = obj.parent
        while p:
            if p.type != 'ARMATURE': ancestors.insert(0, p)
            p = p.parent

        last_parent = None
        ninode = None
        for this_parent in ancestors:
            if 'pynRoot' in this_parent:
                # Only return the root's handle if we wrote it already.
                if this_parent.name in self.objs_written:
                    ninode = self.objs_written[this_parent.name]
            elif this_parent.name in self.objs_written:
                ninode = self.objs_written[this_parent.name]
            else:
                ninode = self.export_node(this_parent, last_parent)
            
            last_parent = ninode
        
        return ninode


    def get_bone_xforms(self, arma, bone_names, shape):
        """Return transforms for the bones in list. Checks the "preserve_hierarchy" flag to 
        determine whether to return global or local transforms.
            arma = armature
            bone_names = list of names
            shape = shape being exported
            result = dict{bone-name: MatTransform, ...}
        """
        result = {}
        for b in arma.data.bones:
            result[b.name] = get_bone_xform(arma, b.name, self.game, 
                                            self.preserve_hierarchy,
                                            self.export_pose)
    
        return result

    def write_bone(self, shape:NiShape, arma, bone_name, bones_to_write):
        """ 
        Write a shape's bone, writing all parent bones first if necessary Returns the name
        of the node in the target nif for the new bone. 
        
        * shape - bone is added to shape's skin. May be None, if only writing a skeleton.
        * arma - parent armature
        * bone_name - bone to write (blender name)
        * bones_to_write - list of bones that the shape needs. If the bone isn't in this
          list, only write it if it's needed for the hierarchy.
        """
        if bone_name in self.writtenbones:
            return self.writtenbones[bone_name]

        if not bone_name in bones_to_write and not self.preserve_hierarchy:
            return None

        bone_parent = arma.data.bones[bone_name].parent
        parname = None
        if bone_parent:
            parname = self.write_bone(shape, arma, bone_parent.name, bones_to_write)
        
        nifname = self.nif_name(bone_name)

        xf = get_bone_xform(arma, bone_name, self.game, 
                            self.preserve_hierarchy,
                            self.export_pose)
        tb = pack_xf_to_buf(xf, self.scale)
        
        if bone_name in bones_to_write and shape:
            shape.add_bone(nifname, tb, 
                           (parname if self.preserve_hierarchy else None))
        elif self.preserve_hierarchy or not shape:
            # Not a shape bone but needed for the hierarchy
            self.nif.add_node(nifname, tb, parname)
        
        self.writtenbones[bone_name] = nifname
        return nifname


    def write_bone_hierarchy(self, shape:NiShape, arma, used_bones:list):
        """Write the bone hierarchy to the nif. Do this first so that transforms 
        and parent/child relationships are correct. Do not assume that the skeleton is fully
        connected (do Blender armatures have to be fully connected?). 
        used_bones - list of bone names to write. 
        """
        self.writtenbones = {}
        for bone_name in used_bones:
            if bone_name in arma.data.bones:
                self.write_bone(shape, arma, bone_name)


    def export_skin(self, obj, arma, new_shape, new_xform, weights_by_vert):
        """
        Export the skin for a shape, including bones used by the skin.
        """
        log.info(f"Skinning {obj.name}")
        new_shape.skin()
        new_shape.transform = make_transformbuf(new_xform)
        newxfi = new_xform.copy()
        newxfi.invert()
        new_shape.set_global_to_skin(make_transformbuf(newxfi))
    
        weights_by_bone = get_weights_by_bone(weights_by_vert, arma.data.bones.keys())

        self.writtenbones = {}
        for bone_name in  weights_by_bone.keys():
            self.write_bone(new_shape, arma, bone_name, weights_by_bone.keys())

        for bone_name, bone_weights in weights_by_bone.items():
            nifname = self.nif_name(bone_name)
            if self.export_pose:
                # Bind location is different from pose location
                xf = get_bone_xform(arma, bone_name, self.game, False, False)
                xfoffs = obj.matrix_world.inverted() @ xf
                xfinv = xfoffs.inverted()
                tb_bind = pack_xf_to_buf(xfinv, self.scale)
                new_shape.set_skin_to_bone_xform(nifname, tb_bind)
            else:
                # Have to set skin-to-bone again because adding the bones nuked it
                xf = get_bone_xform(arma, bone_name, self.game, False, self.export_pose)
                xfoffs = obj.matrix_local.inverted() @ xf
                xfinv = xfoffs.inverted()
                tb = pack_xf_to_buf(xfinv, self.scale)
                    
                new_shape.set_skin_to_bone_xform(nifname, tb)

            self.writtenbones[bone_name] = nifname
            new_shape.setShapeWeights(nifname, bone_weights)


    def apply_shape_key(self, key_name):
        pass


    def export_shape(self, obj, target_key='', arma=None):
        """ Export given blender object to the given NIF file; also writes any associated
            tri file. Checks to make sure the object wasn't already written.
            obj = blender object
            target_key = shape key to export
            arma = armature to skin to
            """
        if obj.name in self.objs_written or nonunique_name(obj) in collision_names:
            return
        log.info(f"Exporting {obj.name}")

        self.active_obj = obj

        # If there's a hierarchy, export parents (recursively) first
        my_parent = self.export_shape_parents(obj)

        retval = set()

        # Prepare for reporting any bone weight errors
        is_skinned = (arma is not None)
        unweighted = []
        if UNWEIGHTED_VERTEX_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[UNWEIGHTED_VERTEX_GROUP])
        if MULTIPLE_PARTITION_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[MULTIPLE_PARTITION_GROUP])
        if NO_PARTITION_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[NO_PARTITION_GROUP])
        
        if is_skinned:
            # Get unweighted bones before we muck up the list by splitting edges
            unweighted = tag_unweighted(obj, arma.data.bones.keys())
            if not expected_game(self.nif, arma.data.bones):
                log.warning(f"Exporting to game that doesn't match armature: game={self.nif.game}, armature={arma.name}")
                retval.add('GAME')

        # Collect key info about the mesh 
        verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, morphdict, partitions, partition_map = \
           self.extract_mesh_data(self.active_obj, arma, target_key)

        is_headpart = obj.data.shape_keys \
                and len(self.nif.dict.expression_filter(set(obj.data.shape_keys.key_blocks.keys()))) > 0

        obj.data.update()
        shaderexp = shader_io.ShaderExporter(obj)

        if shaderexp.is_obj_space:
            norms_exp = None
        else:
            norms_exp = norms_new

        # Make the shape in the nif file. Use the shape's block type, or choose a
        # reasonable default.
        if 'pynBlockName' in obj:
            blocktype = obj['pynBlockName']
        elif is_headpart and self.game == 'SKYRIMSE':
            blocktype = 'BSDynamicTriShape'
        elif partitions and self.game == 'FO4':
            blocktype = 'BSSubIndexTriShape' 
        elif self.game == 'SKYRIM':
            blocktype = 'NiTriShape' 
        else:
            blocktype = 'BSTriShape'
        
        props = blockBuffers[blocktype](obj)
        props.bufType = bufferTypeList.index(blocktype)

        new_shape = self.nif.createShapeFromData(self.unique_name(obj), 
                                                 verts, tris, uvmap_new, norms_exp,
                                                 props=props,
                                                 parent=my_parent)
        self.objs_written[obj.name] = new_shape

        if colors_new:
            new_shape.set_colors(colors_new)

        self.export_shape_data(obj, new_shape)
        
        shaderexp.export(new_shape)

        # Using local transform because the shapes will be parented in the nif
        new_xform = obj.matrix_local * (1/self.scale) 
        if not has_uniform_scale(obj):
            # Non-uniform scales applied to verts, so just use 1.0 for the scale on the object
            l, r, s = new_xform.decompose()
            new_xform = MatrixLocRotScale(l, r, Vector((1,1,1))) 
        elif  not NearEqual(self.scale, 1.0):
            # Export scale factor applied to verts, so scale obj translation but not obj scale 
            l, r, s = new_xform.decompose()
            new_xform = MatrixLocRotScale(l, r, obj.matrix_local.to_scale()) 
        
        if is_skinned:
            self.export_skin(self.active_obj, arma, new_shape, new_xform, weights_by_vert)
            if len(unweighted) > 0:
                create_group_from_verts(obj, UNWEIGHTED_VERTEX_GROUP, unweighted)
                log.warning(f"Some vertices are not weighted to the armature in object {obj.name}")
                self.objs_unweighted.add(obj)

            if len(partitions) > 0:
                if 'FO4_SEGMENT_FILE' in obj.keys():
                    new_shape.segment_file = obj['FO4_SEGMENT_FILE']

                new_shape.set_partitions(partitions.values(), partition_map)

            self.export_collisions(arma)
        else:
            new_shape.transform = make_transformbuf(new_xform)

        # Write other block types
        self.export_collisions(obj)
        if obj.active_material.node_tree.animation_data:
            controller.ControllerHandler.export_shader_controller(obj, new_shape)

        # Write tri file
        retval |= self.export_tris(obj, verts, tris, uvmap_new, morphdict)

        # Write TRIP extra data 
        if self.write_bodytri \
            and self.game in ['SKYRIM', 'SKYRIMSE'] \
            and len(self.trip.shapes) > 0:
            new_shape.string_data = [('BODYTRI', truncate_filename(self.trippath, "meshes"))]

        obj['PYN_GAME'] = self.game
        obj['PYN_BLENDER_XF'] = MatNearEqual(self.export_xf, blender_export_xf)
        if self.preserve_hierarchy != PRESERVE_HIERARCHY_DEF:
            obj['PYN_PRESERVE_HIERARCHY'] = self.preserve_hierarchy 
        if arma:
            arma['PYN_RENAME_BONES'] = self.do_rename_bones
            if self.rename_bones_nift != RENAME_BONES_NIFT_DEF:
                arma['PYN_RENAME_BONES_NIFTOOLS'] = self.rename_bones_nift 
        if self.write_bodytri != WRITE_BODYTRI_DEF:
            obj['PYN_WRITE_BODYTRI_ED'] = self.write_bodytri 
        if self.export_pose != EXPORT_POSE_DEF: obj['PYN_EXPORT_POSE'] = self.export_pose 

        if self.active_obj != obj:
            bpy.data.meshes.remove(self.active_obj.data)
            self.active_obj = None

        log.info(f"{obj.name} successfully exported to {self.nif.filepath}\n")
        return retval
    

    def export_armature(self, arma):
        """Export an armature with no shapes"""
        for b in arma.data.bones:
            self.write_bone(None, arma, b.name, arma.data.bones.keys())


    def export_file_set(self, suffix=''):
        """ 
        Create a set of nif files from the given object, using the given armature and
        appending the suffix. One file is created per shape key with the shape key used as
        suffix. Associated TRIP files are exported if there is TRIP info.
                
        * suffix = suffix to append to the filenames, after the shape key suffix. Empty
          string for regular nifs, non-empty for facebones nifs
        """
        if self.file_keys is None or len(self.file_keys) == 0:
            shape_keys = ['']
        else:
            shape_keys = self.file_keys

        # One TRIP file is written even if we have variants of the mesh ("_" prefix)
        fname_ext = os.path.splitext(os.path.basename(self.filepath))
        self.trip = TripFile()
        self.trippath = os.path.join(os.path.dirname(self.filepath), fname_ext[0]) + ".tri"

        for sk in shape_keys:
            fbasename = fname_ext[0] + sk + suffix
            fnamefull = fbasename + fname_ext[1]
            fpath = os.path.join(os.path.dirname(self.filepath), fnamefull)

            self.objs_written.clear()
            NifFile.clear_log()
            self.nif = NifFile()

            rt = "NiNode"
            rn = "Scene Root"

            if self.objects:
                shape = next(iter(self.objects))
            else:
                shape = self.armature

            if self.root_object:
                try:
                    rt = self.root_object["pynBlockName"]
                except:
                    rt = 'NiNode'
                try:
                    rn = self.root_object["pynNodeName"]
                except:
                    rn = 'Scene Root'
            else:
                if "pynRootNode_BlockType" in shape:
                    rt = shape["pynRootNode_BlockType"]
                if "pynNodeName" in shape:
                    rn = shape["pynNodeName"]
            
            self.nif.initialize(self.game, fpath, rt, rn)
            if self.root_object:
                self.objs_written[self.root_object.name] = self.nif.rootNode
                try:
                    self.nif.rootNode.flags = NiAVFlags.parse(self.root_object["pynNodeFlags"]).value
                except:
                    pass
            elif "pynNodeFlags" in shape:
                self.nif.rootNode.flags = NiAVFlags.parse(shape["pynNodeFlags"]).value

            if suffix == '_faceBones':
                self.nif.dict = fo4FaceDict

            self.nif.dict.use_niftools = self.rename_bones_nift
            self.writtenbones = {}

            if self.objects:
                for obj in self.objects:
                    if suffix == "_faceBones" and self.facebones:
                        # Have exporting the facebones variant and have a facebones armature
                        self.export_shape(obj, sk, self.facebones)
                    elif (not suffix) and self.armature:
                        # Exporting the main file and have an armature to do it with. 
                        self.export_shape(obj, sk, self.armature)
                    elif (not suffix) and self.facebones:
                        # Exporting the main file and have a facebones armature to do it
                        # with. Facebones armatures generally have all the necessary bones
                        # for export, so it's fine to use them.
                        self.export_shape(obj, sk, self.facebones)
                    elif (not self.facebones) and (not self.armature):
                        # No armatures, just export the shape.
                        self.export_shape(obj, sk)
            elif self.armature:
                # Just export the skeleton
                self.export_armature(self.armature)

            # Make sure any grouping nodes get exported, even if they're empty.
            for obj in self.grouping_nodes:
                if 'pynRoot' not in obj and obj.name not in self.objs_written:
                    par = None
                    if obj.parent and obj.parent.name in self.objs_written:
                        par = self.objs_written[obj.parent.name]
                    self.export_node(obj, par)

            # Check for bodytri morphs--write the extra data node if needed
            if self.write_bodytri \
                    and self.game in ['FO4', 'FO76'] \
                    and len(self.trip.shapes) > 0 \
                    and  not self.bodytri_written:
                self.nif.string_data = [('BODYTRI', truncate_filename(self.trippath, "meshes"))]

            if self.root_object:
                for c in self.root_object.constraints:
                    if c.type == 'COPY_TRANSFORMS' and c.target:
                        self.export_collision_object(self.root_object, c.target)
            self.export_extra_data()

            self.nif.save()
            log.info(f"..Wrote {fpath}")
            msgs = list(filter(lambda x: not x.startswith('Info: Loaded skeleton') and len(x)>0, 
                               self.nif.message_log().split('\n')))
            if msgs:
                self.message_log.append(self.nif.message_log())

        if len(self.trip.shapes) > 0:
            self.trip.write(self.trippath)
            log.info(f"Wrote {self.trippath}")


    def execute(self):
        if not self.objects and not self.armature:
            log.warning(f"No objects selected for export")
            self.warnings.add('NOTHING')
            return

        log.info(str(self))
        NifFile.clear_log()
        self.export_file_set('')
        if self.facebones:
            self.export_file_set('_faceBones')
        msgs = list(filter(lambda x: not x.startswith('Info: Loaded skeleton') and len(x)>0, 
                           NifFile.message_log().split('\n')))
        if msgs:
            log.debug("Nifly Message Log:\n" + NifFile.message_log())
    
    def export(self, objects):
        self.set_objects(objects)
        self.execute()

    @classmethod
    def do_export(cls, filepath, game, objects, scale=1.0):
        return NifExporter(filepath, game, scale=scale).export(objects)
        
def get_default_scale():
    return 1.0

def current_active_object(context):
    """
    Determine the object to use as the active object. Only use blender's active object if
    it is also selected. It's too confusing to be working on an unselected object. If
    there's no active object choose the first selected object.
    """
    if context.object and context.object.select_get():
        return context.object
    if context.selected_objects:
        return context.selected_objects[0]
    return None

    
def get_default_game_target(context):
    """Look at currently selected objects to determine game target."""
    g = "SKYRIM"
    obj = current_active_object(context)
    if 'PYN_GAME' in obj:
        g = obj['PYN_GAME']
    else:
        selected_armatures = [a for a in context.selected_objects if a.type == 'ARMATURE']
        if selected_armatures:
            g = best_game_fit(selected_armatures[0].data.bones)
    return g
    

class ExportNIF(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.pynifly"
    bl_label = 'Export NIF (Nifly)'
    bl_options = {'PRESET'}

    filename_ext = ".nif"

    target_game: EnumProperty(
            name="Target Game",
            items=(('SKYRIM', "Skyrim", ""),
                   ('SKYRIMSE', "Skyrim SE", ""),
                   ('FO4', "Fallout 4", ""),
                   ('FO76', "Fallout 76", ""),
                   ('FO3', "Fallout New Vegas", ""),
                   ('FO3', "Fallout 3", ""),
                   ),
            )

    use_blender_xf: bpy.props.BoolProperty(
        name="Use Blender orientation",
        description="Use Blender's orientation and scale.",
        default=BLENDER_XF_DEF
        )
    
    do_rename_bones: bpy.props.BoolProperty(
        name="Rename Bones",
        description="Rename bones from Blender conventions back to nif.",
        default=True)

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename Bones as per NifTools",
        description="Rename bones from NifTools' Blender conventions back to nif.",
        default=False)

    preserve_hierarchy: bpy.props.BoolProperty(
        name="Preserve Bone Hierarchy",
        description="Preserve bone hierarchy in exported nif.",
        default=False)

    write_bodytri: bpy.props.BoolProperty(
        name="Export BODYTRI Extra Data",
        description="Write an extra data node pointing to the BODYTRI file, if there are any bodytri shape keys. Not needed if exporting for Bodyslide, because they write their own.",
        default=True)

    export_pose: bpy.props.BoolProperty(
        name="Export pose position",
        description="Export bones in pose position.",
        default=False)
    
    export_modifiers: bpy.props.BoolProperty(
        name="Export modifiers",
        description="Export all active modifiers (including shape keys)",
        default=False)

    export_colors: bpy.props.BoolProperty(
        name="Export vertex color/alpha",
        description="Use vertex color attributes as vertex color",
        default=False)

    chargen_ext: bpy.props.StringProperty(
        name="Chargen extension",
        description="Extension to use for chargen files (not including file extension).",
        default="chargen")

    # For debugging. If False, use the properties passed in with the invocation. If invoked through
    # the UI it will be true.
    intuit_defaults: bpy.props.BoolProperty(
        name="Intuit Defaults",
        description="Get defaults from current selection",
        default=True,
        options={'HIDDEN'},
    )
    

    def __init__(self):
        self.objects_to_export = bpy.context.selected_objects # get_export_objects(bpy.context)

        if not self.objects_to_export:
            self.report({"ERROR"}, "No objects selected for export")
            return

        obj = self.objects_to_export[0]
        if not self.filepath:
            self.filepath = clean_filename(obj.name)

        lst = [obj for obj in self.objects_to_export if "pynRoot" in obj]
        obj_root = lst[0] if lst else None

        export_armature = None
        if obj.type == 'ARMATURE':
            export_armature = obj
        else:
            export_armature, fb_arma = find_armatures(obj)
            if not export_armature:
                export_armature = fb_arma

        if self.intuit_defaults:
            g = ""
            if 'PYN_GAME' in obj:
                g = obj['PYN_GAME']
            else:
                if export_armature:
                    g = best_game_fit(export_armature.data.bones)
            if g != "":
                self.target_game = g
        
            if obj_root and 'PYN_BLENDER_XF' in obj_root:
                self.use_blender_xf = obj_root['PYN_BLENDER_XF']
            elif obj and 'PYN_BLENDER_XF' in obj:
                self.use_blender_xf = obj['PYN_BLENDER_XF']
                
            if export_armature and 'PYN_RENAME_BONES' in export_armature:
                self.do_rename_bones = export_armature['PYN_RENAME_BONES']

            if export_armature and 'PYN_RENAME_BONES_NIFTOOLS' in export_armature:
                self.rename_bones_niftools = export_armature['PYN_RENAME_BONES_NIFTOOLS']

            if obj and 'PYN_PRESERVE_HIERARCHY' in obj:
                self.preserve_hierarchy = obj['PYN_PRESERVE_HIERARCHY']

            if obj and 'PYN_WRITE_BODYTRI_ED' in obj:
                self.write_bodytri = obj['PYN_WRITE_BODYTRI_ED']

            if obj and 'PYN_EXPORT_POSE' in obj:
                self.export_pose = obj['PYN_EXPORT_POSE']

            if obj and 'PYN_CHARGEN_EXT' in obj:
                self.chargen_ext = obj['PYN_CHARGEN_EXT']

        
    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False

        if len(context.selected_objects) == 0:
            log.error("Must select an object to export")
            return False

        if context.object.mode != 'OBJECT':
            log.error("Must be in Object Mode to export")
            return False

        return True

    def execute(self, context):
        res = set()
        selected_objs = context.selected_objects
        active_obj = context.object

        if not self.poll(context):
            self.report({"ERROR"}, f"Cannot run exporter--see system console for details")
            return {'CANCELLED'} 

        if len(self.objects_to_export) == 0:
            self.report({"ERROR"}, "No objects selected for export")
            return {'CANCELLED'}

        LogStart(bl_info, "EXPORT", "NIF")
        NifFile.Load(nifly_path)

        try:
            exporter = NifExporter(self.filepath, 
                                   self.target_game, 
                                   chargen=self.chargen_ext)

            exporter.do_rename_bones = self.do_rename_bones
            exporter.rename_bones_nift = self.rename_bones_niftools
            exporter.preserve_hierarchy = self.preserve_hierarchy
            exporter.write_bodytri = self.write_bodytri
            exporter.export_pose = self.export_pose
            exporter.export_modifiers = self.export_modifiers
            exporter.export_colors = self.export_colors
            if self.use_blender_xf:
                exporter.export_xf = blender_export_xf
            exporter.export(self.objects_to_export)
            
            rep = False
            status = {"SUCCESS"}
            if len(exporter.objs_unweighted) > 0:
                status = {"ERROR"}
                self.report(status, f"The following objects have unweighted vertices.See the '*UNWEIGHTED*' vertex group to find them: \n{exporter.objs_unweighted}")
                rep = True
            if len(exporter.objs_scale) > 0:
                status = {"ERROR"}
                self.report(status, f"The following objects have non-uniform scale, which nifs do not support. Scale applied to verts before export.\n{exporter.objs_scale}")
                rep = True
            if len(exporter.objs_mult_part) > 0:
                status = {"WARNING"}
                self.report(status, f"Some faces have been assigned to more than one partition, which should never happen.\n{exporter.objs_mult_part}")
                rep = True
            if len(exporter.objs_no_part) > 0:
                status = {"WARNING"}
                self.report(status, f"Some faces have been assigned to no partition, which should not happen for skinned body parts.\n{exporter.objs_no_part}")
                rep = True
            if len(exporter.arma_game) > 0:
                status = {"WARNING"}
                self.report(status, f"The armature appears to be designed for a different game--check that it's correct\nArmature: {exporter.arma_game}, game: {exporter.game}")
                rep = True
            if 'NOTHING' in exporter.warnings:
                status = {"WARNING"}
                self.report(status, f"No mesh selected; nothing to export")
                rep = True
            if 'WARNING' in exporter.warnings:
                status = {"WARNING"}
                self.report(status, f"Export completed with warnings. Check the console window.")
                rep = True
            if not rep:
                self.report({'INFO'}, f"Export successful")
            LogFinish("EXPORT", self.objects_to_export, status, False)
            
        except:
            log.exception("Export of nif failed")
            self.report({"ERROR"}, "Export of nif failed, see console window for details")
            res.add("CANCELLED")
            LogFinish("EXPORT", self.objects_to_export, {"ERROR"}, True)

        ObjectSelect(selected_objs)
        ObjectActive(active_obj)

        return res.intersection({'CANCELLED'}, {'FINISHED'})


################################################################################
#                                                                              #
#                             KF ANIMATION EXPORT                              #
#                                                                              #
################################################################################

class ExportKF(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.pynifly_kf"
    bl_label = 'Export KF (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".kf"

    fps: bpy.props.FloatProperty(
        name="FPS",
        description="Frames per second for export",
        default=30)


    @classmethod
    def poll(cls, context):
        if not nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False

        if (not context.object) or context.object.type != 'ARMATURE':
            log.debug("Must select an armature to export animations.")
            return False

        if (not context.object.animation_data) or (not context.object.animation_data.action):
            log.debug("Active object must have an animation associated with it.")
            return False

        return True
    

    def __init__(self):
        self.messages = []
        self.errors = set()
        self.given_scale_warning = False

        if not self.filepath \
            and bpy.context.object.animation_data \
                and bpy.context.object.animation_data.action:
            self.filepath =  bpy.context.object.animation_data.action.name
            

    def execute(self, context):
        self.context = context
        res = set()

        if not self.poll(context):
            self.report({"ERROR"}, f"Cannot run exporter--see system console for details")
            return {'CANCELLED'} 

        if self.fps <= 0 or self.fps >= 200:
            self.report({"ERROR"}, f"FPS outside of valid range, using 30fps: {self.fps}")
            self.fps = 30

        LogStart(bl_info, "EXPORT", "KF")
        NifFile.Load(nifly_path)
        NifFile.clear_log()

        try:
            # Export whatever animation is attached to the active object.
            self.export_animation(context.object)

        except:
            log.exception("Export of KF failed")
            self.error("Export of KF failed")

        if "ERROR" in self.errors:
            self.report({"ERROR"}, "Export of KF failed, see console window for details")
            res.add("CANCELLED")
            LogFinish("EXPORT", self.filepath, {"ERROR"}, True)
        elif "WARNING" in self.errors:
            self.report({"ERROR"}, "Export of KF completed with warnings, see console window for details")
            res.add("CANCELLED")
            LogFinish("EXPORT", self.filepath, {"WARNING"}, True)
        else:
            self.report({"INFO"}, "Export of KF completed successfully")
            res.add("SUCCESS")
            LogFinish("EXPORT", self.filepath, {"SUCCESS"})

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

    def error(self, msg):
        """Log an error message."""
        log.error(msg)
        self.errors.add("ERROR")
        self.messages.append("ERROR: " + msg)

    def warning(self, msg):
        """Log a warning message."""
        log.warning(msg)
        self.errors.add("WARNING")
        self.messages.append("WARNING: " + msg)


    def export_curves(self, arma, curve_list):
        """Export a group of curves from the list to a TransformInterpolator/TransformData pair. 
        A group maps to a controlled object, so each group should be one such pair.
        The curves that are used are picked off the list.
        * Returns (group name, TransformInterpolator for the set of curves).
        """
        if not curve_list: return None, None
        
        group = curve_list[0].group.name
        scene_fps = self.context.scene.render.fps
        
        loc = []
        eu = []
        quat = []
        scale = []
        while curve_list and curve_list[0].group.name == group:
            dp = curve_list[0].data_path
            if ".location" in dp:
                loc.append(curve_list[0])
                curve_list.pop(0)
            elif ".rotation_quaternion" in dp:
                quat.append(curve_list[0])
                curve_list.pop(0)
            elif ".scale" in dp:
                scale.append(curve_list[0])
                curve_list.pop(0)
            else:
                self.error(f"Unknown curve type: {dp}")
                return None, None
        
        if scale:
            if not self.given_scale_warning:
                self.report({"INFO"}, f"Ignoring scale transforms--not used in Skyrim")
                self.given_scale_warning = True

        if len(loc) != 3 and len(eu) != 3 and len(quat) != 4:
            self.error(f"No useable transforms in group {group}")
            return None, None

        if not group in arma.data.bones:
            self.error(f"Target bone not found in armature: {group}")
            return None, None
        
        targ = arma.data.bones[group]
        if targ.parent:
            targ_xf = targ.parent.matrix_local.inverted() @ targ.matrix_local
        else:
            targ_xf = targ.matrix_local
        targ_trans = targ_xf.translation
        targ_q = targ_xf.to_quaternion()

        tibuf = NiTransformInterpolatorBuf()
        tibuf.translation = targ_trans[:]
        tibuf.rotation = targ_q[:]
        tibuf.scale = 1.0
        ti = NiTransformInterpolator(file=self.nif, props=tibuf)
        
        tdbuf = NiTransformDataBuf()
        if quat:
            tdbuf.rotationType = NiKeyType.QUADRATIC_KEY
        elif eu:
            tdbuf.rotationType = NiKeyType.XYZ_ROTATION_KEY
        if loc:
            tdbuf.translations.interpolation = NiKeyType.LINEAR_KEY
        td = NiTransformData(file=self.nif, props=tdbuf, parent=ti)

        # Lots of error-checking because the user could have done any damn thing.
        if len(quat) == 4:
            timemax = max(q.range()[1]-1 for q in quat)/scene_fps
            timemin = min(q.range()[0]-1 for q in quat)/scene_fps
            timestep = 1/self.fps
            timesig = timemin
            while timesig < timemax + 0.0001:
                fr = timesig * scene_fps + 1
                tdq = Quaternion([quat[0].evaluate(fr), 
                                  quat[1].evaluate(fr), 
                                  quat[2].evaluate(fr), 
                                  quat[3].evaluate(fr)])
                kq = targ_q @ tdq
                td.add_qrotation_key(timesig, kq)
                timesig += timestep

        if len(loc) == 3:
            timemax = max(v.range()[1]-1 for v in loc)/scene_fps
            timemin = min(v.range()[0]-1 for v in loc)/scene_fps
            timestep = 1/self.fps
            timesig = timemin
            while timesig < timemax + 0.0001:
                fr = timesig * scene_fps + 1
                kv =Vector([loc[0].evaluate(fr), 
                            loc[1].evaluate(fr), 
                            loc[2].evaluate(fr)])
                rv = kv + targ_trans
                td.add_translation_key(timesig, rv)
                timesig += timestep

        return group, ti
                

    def export_animation(self, arma):
        """Export one action to one animation KF file."""
        action = arma.animation_data.action
        fps = self.context.scene.render.fps
        self.nif = NifFile()
        self.nif.initialize("SKYRIM", self.filepath, "NiControllerSequence", 
                            os.path.splitext(os.path.basename(self.filepath))[0])
        controller = self.nif.rootNode
        cp = controller.properties.copy()
        cp.startTime = (action.curve_frame_range[0]-1)/fps
        cp.stopTime = (action.curve_frame_range[1]-1)/fps
        cp.cycleType = CycleType.CYCLE_LOOP if action.use_cyclic else CycleType.CYCLE_CLAMP
        cp.frequency = 1.0
        controller.properties = cp

        # Collect list of curves. They will be picked off in clumps until the list is empty.
        curve_list = list(action.fcurves)
        while curve_list:
            targname, ti = self.export_curves(arma, curve_list)
            if targname and ti:
                controller.add_controlled_block(
                    name=self.nif.nif_name(targname),
                    interpolator=ti,
                    node_name = self.nif.nif_name(targname),
                    controller_type = "NiTransformController")

        self.nif.save()


################################################################################
#                                                                              #
#                             HKX ANIMATION EXPORT                              #
#                                                                              #
################################################################################

class ExportHKX(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.pynifly_hkx"
    bl_label = 'Export HKX (pyNifly)'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"

    reference_skel: bpy.props.StringProperty(
        name="Reference skeleton",
        description="Reference skeleton (HKX) to use for animation binding",
        default="")

    fps: bpy.props.FloatProperty(
        name="FPS",
        description="Frames per second for export",
        default=30)

    def __init__(self):
        obj = bpy.context.object
        if obj and obj.type == 'ARMATURE':
            if 'PYN_SKELETON_FILE'in obj:
                self.reference_skel = obj['PYN_SKELETON_FILE']


    @classmethod
    def poll(cls, context):
        if (not context.object) or context.object.type != 'ARMATURE':
            log.error("Must select an armature to export animations.")
            return False

        if (not context.object.animation_data) or (not context.object.animation_data.action):
            log.error("Active object must have an animation associated with it.")
            return False

        if not hkxcmd_path:
            log.error("hkxcmd.exe not found--animation I/O not available.")
            return False

        return True
    

    def execute(self, context):
        res = set()
        self.reference_skel_short = tmp_filepath(self.reference_skel, ext=".hkx")
        copyfile(self.reference_skel, self.reference_skel_short)
        self.filepath_short = tmp_filepath(self.filepath, ext=".hkx")
        if self.reference_skel:
            context.object['PYN_SKELETON_FILE'] = self.reference_skel

        if not self.poll(context):
            self.error(f"Cannot run exporter--see system console for details")
            return {'CANCELLED'} 

        self.context = context
        self.fps = context.scene.render.fps
        self.errors = set()
        self.has_markers = (len(context.scene.timeline_markers) > 0)
        self.hkx_tmp_filepath = tmp_filepath(self.filepath, ext=".hkx")
        self.xml_filepath = None
        self.xml_filepath_out = None
        LogStart(bl_info, "EXPORT", "HKX")
        NifFile.Load(nifly_path)
        NifFile.clear_log()

        try:
            # Export whatever animation is attached to the active object.
            self.kf_filepath = tmp_filepath(self.filepath, ext=".kf")
            bpy.ops.export_scene.pynifly_kf(filepath=self.kf_filepath, fps=self.fps)
            self.info(f"Temporary kf file created: {self.kf_filepath}")
            if self.has_markers:
                self.xml_filepath = tmp_filepath(self.filepath, ext=".xml")
                self.generate_hkx(self.hkx_tmp_filepath)
                self.write_annotations()
                self.generate_final_hkx()
            else:
                self.generate_hkx(self.filepath_short)
            self.rename_output()

            res.add('FINISHED')
        except:
            log.exception("Export of HKX failed")
            self.error("Export of HKX failed")
            res.add('CANCELLED')

        LogFinish("EXPORT", self.filepath, self.errors, False)

        return res.intersection({'CANCELLED'}, {'FINISHED'})
    

    def warn(self, msg):
        self.report({"WARNING"}, msg)
        self.errors.add("WARNING")

    def error(self, msg):
        self.report({"ERROR"}, msg)
        self.errors.add("ERROR")

    def info(self, msg):
        log.info(msg)
        self.report({"INFO"}, msg)

    def generate_hkx(self, filepath):
        """Generates an HKX file from a KF file. Also generates an XML file."""

        # Generate HKX from KF
        stat = subprocess.run([hkxcmd_path, 
                               "CONVERTKF", 
                               self.reference_skel_short, 
                               self.kf_filepath, 
                               filepath], 
                               capture_output=True, check=True)
        if stat.returncode:
            s = stat.stderr.decode('utf-8').strip()
            self.error(s)
            return None
        if not os.path.exists(filepath):
            self.error(f"Failed to create {filepath}")
            return None
        self.info(f"Created temporary HKX file: {filepath}")

        if self.xml_filepath:
            # Generate XML from HKX
            stat = subprocess.run([hkxcmd_path, 
                                "CONVERT", 
                               "-V:XML",
                                filepath, 
                                self.xml_filepath], 
                                capture_output=True, check=True)
            if stat.returncode:
                s = stat.stderr.decode('utf-8').strip()
                self.error(s)
                return None
            if not os.path.exists(self.xml_filepath):
                self.error(f"Failed to create {self.xml_filepath}")
                return None
            
            self.info(f"Created temporary XML file: {self.xml_filepath}")

    def write_annotations(self):
        """Write animation text annotations to the intermediate xml file.
        Returns False if there were no annotations, so the original HKX is fine.
        """
        markers = self.context.scene.timeline_markers
        if len(markers) == 0:
            return False
        
        xmlfile = xml.parse(self.xml_filepath)
        xmlroot = xmlfile.getroot()
        annotation_tracks = next(x for x in xmlroot.iter('hkparam') if x.attrib['name'] == "annotationTracks")
        tracks = [obj for obj in annotation_tracks]
        for t in tracks: 
            annotation_tracks.remove(t)

        # # Writing a single track. Don't know how or why we would have more.
        annotation_tracks.set('numelements', "1")
        trackobj = xml.SubElement(annotation_tracks, 'hkobject')
        annotations = xml.SubElement(
            trackobj, 'hkparam', {'name': 'annotations', 'numelements': str(len(markers))})
        
        for m in markers:
            markobj = xml.SubElement(annotations, 'hkobject')
            timeparam = xml.SubElement(markobj, 'hkparam', {'name': 'time'})
            timeparam.text = f"{(m.frame/self.fps):f}"
            textparam =xml.SubElement(markobj, 'hkparam', {'name': 'text'})
            textparam.text = m.name
        
        self.xml_filepath_out = tmp_filepath(self.filepath, ext='.xml')
        xmlfile.write(self.xml_filepath_out)
        self.info(f"Created final XML file: {self.xml_filepath_out}")
        
        return True
    
    def rename_output(self):
        """If we renamed our output to deal with spaces in names, set it back to what it
        should be."""
        copyfile(self.filepath_short, self.filepath)



    def generate_final_hkx(self):
        stat = subprocess.run([hkxcmd_path, 
                               "CONVERT", 
                               "-V:WIN32",
                               self.xml_filepath, 
                               self.filepath_short], 
                               capture_output=True, check=True)
        if stat.returncode:
            s = stat.stderr.decode('utf-8').strip()
            self.error(s)
            return None
        if not os.path.exists(self.filepath_short):
            self.error(f"Failed to create {self.filepath_short}")
            return None
    
        self.info(f"Created HKX file: {self.filepath_short}")


class ExportSkelHKX(skeleton_hkx.ExportSkel):
    """Export Blender armature to a skeleton HKX file"""

    bl_idname = "export_scene.skeleton_hkx"
    bl_label = 'Export skeleton HKX'
    bl_options = {'PRESET'}

    filename_ext = ".hkx"

    @classmethod
    def poll(cls, context):
        if (not context.object) or context.object.type != 'ARMATURE':
            log.error("Must select an armature to export animations.")
            return False

        if not hkxcmd_path:
            log.error("hkxcmd.exe not found--skeleton export not available.")
            return False

        return True


    def execute(self, context):
        LogStart(bl_info, "EXPORT SKELETON", "HKX")

        try:
            self.context = context
            out_filepath = self.filepath
            self.filepath = tmp_filepath(self.filepath, ".xml")
            self.do_export()

            xmltools.XMLFile.SetPath(hkxcmd_path)
            xmltools.XMLFile.xml_to_hkx(self.filepath, out_filepath)
            log.info(f"Wrote {out_filepath}")

            status = {'FINISHED'}
            return status
        except:
            log.exception("Import of HKX failed")
            self.report({"ERROR"}, "Import of HKX failed, see console window for details")
            status = {'CANCELLED'}
            LogFinish("IMPORT", out_filepath, status, True)


def nifly_menu_import_nif(self, context):
    self.layout.operator(ImportNIF.bl_idname, text="Nif file with pyNifly (.nif)")

def nifly_menu_import_tri(self, context):
    self.layout.operator(ImportTRI.bl_idname, text="Tri file with pyNifly (.tri)")

def nifly_menu_import_kf(self, context):
    self.layout.operator(ImportKF.bl_idname, text="KF file with pyNifly (.kf)")

def nifly_menu_import_hkx(self, context):
    self.layout.operator(ImportHKX.bl_idname, text="HKX animation or skeleton file with pyNifly (.hkx)")

def nifly_menu_export_nif(self, context):
    self.layout.operator(ExportNIF.bl_idname, text="Nif file with pyNifly (.nif)")

def nifly_menu_export_kf(self, context):
    self.layout.operator(ExportKF.bl_idname, text="KF file with pyNifly (.kf)")

def nifly_menu_export_hkx(self, context):
    self.layout.operator(ExportHKX.bl_idname, text="HKX file with pyNifly (.hkx)")

def nifly_menu_export_skelhkx(self, context):
    self.layout.operator(ExportSkelHKX.bl_idname, text="Skeleton file with pyNifly (.hkx)")

pyn_registry = [('i', nifly_menu_import_nif, ImportNIF),
                ('i', nifly_menu_import_tri, ImportTRI),
                ('i', nifly_menu_import_kf, ImportKF),
                ('i', nifly_menu_import_hkx, ImportHKX),
                ('e', nifly_menu_export_nif, ExportNIF),
                ('e', nifly_menu_export_kf, ExportKF),
                ('e', nifly_menu_export_hkx, ExportHKX),
                ('e', nifly_menu_export_skelhkx, ExportSkelHKX),
                ]

def unregister():
    for d, f, c in pyn_registry:
        try:
            if d == 'i':
                bpy.types.TOPBAR_MT_file_import.remove(f)
            else:
                bpy.types.TOPBAR_MT_file_export.remove(f)
        except: 
            pass
        try:
            bpy.utils.unregister_class(c) 
        except:
            pass

    skeleton_hkx.unregister()

def register():
    for d, f, c in pyn_registry:
        try:
            bpy.utils.register_class(c)
        except:
            pass
        try:
            if d == 'i':
                bpy.types.TOPBAR_MT_file_import.append(f)
            else:
                bpy.types.TOPBAR_MT_file_export.append(f)
        except:
            pass
    skeleton_hkx.register()

    if nifly_path:
        log.info(f"Loading pyNifly version {bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}")
        log.debug(f"Running pyNifly DLL from {nifly_path}.")
    else: 
        log.error(f"Could not locate pyNifly DLL--pyNifly is disabled.")
    if hkxcmd_path:
        log.debug(f"Running hkxcmd from {hkxcmd_path}")
    else:
        log.error(f"Could not locate hkxcmd in the pyNifly install. Animations cannot be exported to HKX format.")

    if not asset_path:
        log.error(f"Could not find pyNifly asset library. Shader import will be limited.")


if __name__ == "__main__":
    unregister()
    register()
