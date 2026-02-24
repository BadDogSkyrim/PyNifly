"""
Import of nif files to Blender
"""

import os
from contextlib import suppress
from mathutils import Matrix, Vector, Euler, Color
from math import pi
import codecs
import logging
import json
from pathlib import Path
import bpy
from bpy.props import CollectionProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from .. import bl_info
from ..pyn.niflytools import fo4FaceDict, find_trip, find_tris, MatNearEqual
from ..pyn.nifdefs import (ShaderFlags1, ShaderFlags2, BSXFlagsValues, BSValueNodeFlags, 
                     NiAVFlags, VertexFlags, PynIntFlag)
# from ..pyn.pynifly import (P.NiShape, FurnAnimationType, FurnEntryPoints, P.NiNode, P.NifFile, 
#                            P.nifly_path, P.hkxSkeletonFile)
from ..pyn import pynifly as P
from .. import blender_defs as BD
from ..util.settings import (ImportSettings, 
    PYN_BLENDER_XF_PROP,
    PYN_GAME_PROP,
    PYN_RENAME_BONES_NIFTOOLS_PROP,
    PYN_RENAME_BONES_PROP,
    PYN_ROTATE_BONES_PRETTY_PROP,
    )
from ..util.reprobj import ReprObject, ReprObjectCollection
from . import shader_io 
from . import controller 
from . import collision 
from . import connectpoint 
from ..tri.trifile import TriFile
from ..tri.import_tri import open_tri, import_tri, import_trip

log = logging.getLogger('pynifly')

NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"
ALPHA_MAP_NAME = "VERTEX_ALPHA"
COLOR_MAP_NAME = "Col"

ARMATURE_BONE_GROUPS = ['NPC', 'CME']

CAMERA_LENS = 80


# Properties that don't need to be remembered on imported objects.
NISHAPE_IGNORE = [
    "bufSize", 
    'bufType',
    "id", 
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
    "flags",
    "vertexFlags",
    "pynValueNodeFlags",
    ]


# --------- Helper functions -------------

def get_setting(obj, setting_name, default_value):
    if setting_name in obj:
        return obj[setting_name]
    else:
        return default_value


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


def armatures_match(a, b):
    """Returns true if all bones of the first armature have the same position in the second"""
    bpy.ops.object.mode_set(mode = 'OBJECT')
    for bone in a.data.bones:
        if bone.name in b.data.bones:
            if not MatNearEqual(bone.matrix_local, b.data.bones[bone.name].matrix_local):
                return False
            elif not MatNearEqual(a.pose.bones[bone.name].matrix, b.pose.bones[bone.name].matrix):
                return False
            else:
                pass
        else:
            pass
    return True


# ######################################################################## ###
#                                                                          ###
# -------------------------------- IMPORT -------------------------------- ###
#                                                                          ###
# ######################################################################## ###

# -----------------------------  MESH CREATION -------------------------------

def mesh_create_normals(the_mesh, normals):
    """ 
    Create custom normals in Blender to match those on the object 
        normals = [(x, y, z)... ] 1:1 with mesh verts
    """
    if normals:
        # Make sure the normals are unit length
        # Magic incantation to set custom normals
        if hasattr(the_mesh, "use_auto_smooth"):
            the_mesh.use_auto_smooth = True
        the_mesh.normals_split_custom_set([(0, 0, 0)] * len(the_mesh.loops))
        the_mesh.normals_split_custom_set_from_vertices([Vector(v).normalized() for v in normals])


def mesh_create_partition_groups(the_shape, the_object):
    """ Create groups to capture partitions """
    mesh = the_object.data
    vg = the_object.vertex_groups
    partn_groups = []
    for p in the_shape.partitions:
        if p.name in vg:
            new_vg = vg[p.name]
        else:
            new_vg = vg.new(name=p.name)
        partn_groups.append(new_vg)
        if hasattr(p, "subsegments"):
            # Walk through subsegments, if any. Skyrim doesn't have them.
            for sseg in p.subsegments:
                new_vg = vg.new(name=sseg.name)
                partn_groups.append(new_vg)
    for part_idx, face in zip(the_shape.partition_tris, mesh.polygons):
        if part_idx < len(partn_groups):
            this_vg = vg[partn_groups[part_idx].name]
            for lp in face.loop_indices:
                this_loop = mesh.loops[lp]
                this_vg.add((this_loop.vertex_index,), 1.0, 'ADD')
    if len(the_shape.segment_file) > 0:
        the_object['FO4_SEGMENT_FILE'] = the_shape.segment_file


def import_colors(mesh:bpy.types.Mesh, shape:P.NiShape):
    try:
        use_vertex_colors = False
        use_vertex_alpha = False
        if shape.file.game in ['SKYRIM', 'SKYRIMSE']:
            use_vertex_colors = shape.shader.properties.shaderflags2_test(ShaderFlags2.VERTEX_COLORS)
            use_vertex_alpha = shape.shader.properties.shaderflags1_test(ShaderFlags1.VERTEX_ALPHA)
        else:
            if shape.properties.hasVertexColors or shape.shader.blockname == 'BSEffectShaderProperty':
                # FO4 appears to combine vertex alpha with vertex color, so always provide alpha.
                # or ((shape.shader_block_name == 'BSEffectShaderProperty' and shape.file.game == 'FO4'))
                # If we have a BSEffectShaderProperty in FO4 we assume the alpha channel
                # is used whether or not VERTEX_ALPHA is set. Some FO4 meshes seem to work
                # this way. 
                use_vertex_colors = True
                use_vertex_alpha = True
        if use_vertex_colors \
            and shape.colors and len(shape.colors) > 0:
            clayer = None
            try: #Post V3.5
                clayer = mesh.color_attributes.new(name=COLOR_MAP_NAME, type='FLOAT_COLOR', domain='POINT')
            except:
                clayer = mesh.vertex_colors.new()
            alphlayer = None
            if use_vertex_alpha:
                try:
                    alphlayer = mesh.color_attributes.new(
                        name=ALPHA_MAP_NAME, type='FLOAT_COLOR', domain='POINT')
                except:
                    alphlayer = mesh.vertex_colors.new()
                alphlayer.name = ALPHA_MAP_NAME
        
            colors = shape.colors
            if clayer.domain == 'POINT':
                for i in range(0, len(mesh.vertices)):
                    c = colors[i]
                    clayer.data[i].color = (c[0], c[1], c[2], 1.0)
                    if alphlayer:
                        alph = colors[i][3] 
                        cv = list(Color([alph, alph, alph]))
                        # cv = list(Color([alph, alph, alph]).from_scene_linear_to_srgb())
                        cv.append(1.0)
                        alphlayer.data[i].color = cv
            else:
                for lp in mesh.loops:
                    c = colors[lp.vertex_index]
                    clayer.data[lp.index].color = (c[0], c[1], c[2], 1.0)
                    if alphlayer:
                        alph = colors[lp.vertex_index][3]
                        alphlayer.data[lp.index].color = [alph, alph, alph, 1.0]
    except:
        log.exception(f"Could not read colors on shape {shape.name}")


class NifImporter():
    """
    Does the work of importing a nif, independent of Blender's operator interface.
    """
    def __init__(self, 
                 filename_list, # Files may be combined into one Blender object
                 target_objects=None, # Object to fold imported objects into, if possible
                 target_armatures=None, # Armatures to use for imported objects
                 import_settings=None, # Dictionary of settings
                 collection=None, # Collection to link objects into, null to create new collection 
                 reference_skel=None, # Reference skeleton for bone creation (P.NifFile)
                 base_transform=Matrix.Identity(4), # Transform to apply to root
                 context=bpy.context,
                 chargen_ext="chargen", # Extension for chargen tri files
                 animation_name=None, # Base name of animation being imported, if any
                 scale=1.0,
                 anim_warn=False
                 ):
        
        self.filename_list = filename_list
        self.target_armatures = set(target_armatures) if target_armatures else set()
        self.collection = collection
        self.settings = import_settings
        self.reference_skel = reference_skel
        self.import_xf = base_transform # Transform applied to root for blender convenience.
        self.context = context
        self.chargen_ext = chargen_ext
        self.animation_name = animation_name
        self.anim_warn = anim_warn
        self.scale = scale

        self.armature = None # Armature used for current shape import
        if target_armatures: self.armature = next(iter(target_armatures))
        self.context = bpy.context 
        self.is_facegen = False
        self.is_new_armature = True # Armature is derived from current nif; set false if adding to existing arma
        self.created_child_cp = None
        self.bones = set()
        self.objects_created = ReprObjectCollection() # Dictionary of objects created, indexed by node handle
                                  # (or object name, if no handle)
        self.nodes_loaded = {} # Dictionary of nodes from the nif file loaded, indexed by Blender name
        self.loaded_meshes = [] # Holds blender objects created from shapes in a nif

        self.connect_points = connectpoint.ConnectPointCollection()
        try:
            self.connect_points.add_all(context.selected_objects)
        except:
            self.connect_points.add_all(bpy.context.selected_objects)
        self.loaded_parent_cp = {}
        self.loaded_child_cp = {}
        
        self.nif = None # P.NifFile(filename)
        self.loc = Vector((0, 0, 0))   # location for new objects 
        self.warnings = []
        self.root_object = None  # Blender representation of root object
        self.auxbones = False
        self.ref_compat = False
        self.controller_mgr = None


    def __str__(self):
        return f"""
        Importing nif: {self.filename_list} {"(FACEGEN_FILE)" if self.is_facegen else ""}
            flags: {self.settings} 
            armature: {self.armature} 
            connect points: {[x.name for x in self.connect_points.parents]}, {[x.names for x in self.connect_points.child]} 
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
    
    def nif_name(self, blender_name):
        """Return the name to use in the nif for a bone."""
        if self.settings.rename_bones or self.settings.rename_bones_niftools:
            return self.nif.nif_name(blender_name)
        else:
            return blender_name
        
    def blender_name(self, nif_name):
        """Return the name to use in Blender for a bone."""
        if self.is_facegen and nif_name == "Head":
            # Facegen nifs use a "Head" bone, which appears to be the "HEAD" bone misnamed.
            return "HEAD"  
        elif self.settings.rename_bones or self.settings.rename_bones_niftools:
            return self.nif.blender_name(nif_name)
        else:
            return nif_name

    def calc_obj_transform(self, the_shape:P.NiShape, scale_factor=1.0) -> Matrix:
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
            return BD.apply_scale_xf(BD.transform_to_matrix(the_shape.transform), scale_factor)

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
        xform_shape = BD.transform_to_matrix(the_shape.transform)
        xform_calc = BD.transform_to_matrix(the_shape.calc_global_to_skin()) 
        if the_shape.has_global_to_skin:
            # The global-to-skin doesn't stand alone. It has to be combined with the
            # shape's transform and the transform from the bind positions. E.g. the
            # Argonian head has a null global-to-skin and uses the bone transforms to lift
            # itself into place. 
            xform = BD.transform_to_matrix(the_shape.global_to_skin)
            xf = (xform_shape @ xform @ xform_calc).inverted()
        else:
            xf = xform_calc.inverted()
            
        offset_consistent = True
        
        ### All of this is unreachable now.
        offset_xf = None
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
                    skel_bone_xf= BD.transform_to_matrix(skel_bone.global_transform)
                    bindpos = BD.bind_position(the_shape, bn)
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
                        log.warning(f"Shape {the_shape.name} does not have consitent offset from reference skeleton {self.reference_skel.filepath}--can't use it to extend the armature.")
                        self.settings.create_bones = False
                        break

            if offset_consistent and offset_xf:
                # If the offset is close to the standard FO4 bodypart offset, normalize it 
                # so all bodyparts are consistent.
                if self.nif.game == 'FO4' and  MatNearEqual(offset_xf, BD.fo4_bodypart_xf, epsilon=3):
                    xf = xf @ BD.fo4_bodypart_xf
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
                bone_xf = BD.pose_transform(the_shape, b)
                if pose_xf:
                    # Some common nifs such as the Bodytalk male body need some extra
                    # fudge factor. Reducing epsilon here will result in their shape not
                    # getting adjusted to the armature location. 
                    if not MatNearEqual(pose_xf, bone_xf, epsilon=0.5):
                        same = False
                        break
                else:
                    pose_xf = bone_xf
            if same: 
                # If the offset is close to the standard FO4 bodypart offset, normalize it 
                # so all bodyparts are consistent.
                bpi = BD.fo4_bodypart_xf.inverted()
                if self.nif.game == 'FO4' and  MatNearEqual(pose_xf, bpi, epsilon=3):
                    xf = xf @ bpi
                else:
                    xf = xf @ pose_xf
                xf.invert()

        return BD.apply_scale_xf(xf, scale_factor)


    # -----------------------------  EXTRA DATA  -------------------------------

    def import_bound(self, node, parent_obj, extblock:P.BSBound):
        bpy.ops.mesh.primitive_cube_add(
            size=1, 
            enter_editmode=False, 
            calc_uvs=False,
            align='WORLD', 
            location=extblock.center, 
            scale=(extblock.half_extents[0]*2, 
                   extblock.half_extents[1]*2, 
                   extblock.half_extents[2]*2))
        bpy.context.object.display_type = 'WIRE'

        ed = bpy.context.object
        ed.name = "BSBound:" + extblock.name
        ed.show_name = True
        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)


    def import_bone_lod(self, node, parent_obj, extblock:P.BSBoneLODExtraData):
        bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
        ed = bpy.context.object
        ed.name = "BSBoneLOD:" + extblock.name
        ed.show_name = True
        ed['pynBoneLOD'] = json.dumps(extblock.lod_data)
        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)


    def import_bsx(self, node, parent_obj, extblock:P.BSXFlags):
        bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
        ed = bpy.context.object
        ed.name = "BSXFlags:" + extblock.name
        ed.show_name = True
        ed.empty_display_type = 'SPHERE'
        ed['BSXFlags_Name'] = extblock.name
        ed['BSXFlags_Value'] = extblock.flags.fullname
        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)


    def import_integer(self, node, parent_obj, extblock:P.NiIntegerExtraData):
        bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
        ed = bpy.context.object
        ed.name = "NiIntegerExtraData:" + extblock.name
        ed.show_name = True
        ed.empty_display_type = 'SPHERE'
        ed['NiIntegerExtraData_Name'] = extblock.name
        ed['NiIntegerExtraData_Value'] = extblock.integer_data
        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)


    def import_inventory_marker(self, node, parent_obj, invm:P.BSInvMarker):
        bpy.ops.object.add(type='CAMERA', 
                            location=[0, 100, 0],
                            rotation=[-pi/2, pi, 0])
        ed = bpy.context.object
        ed.name = "BSInvMarker:" + invm.name
        ed.show_name = True 

        neut = BD.MatrixLocRotScale((0, 100, 0),
                                    Euler((-pi/2, pi, 0), 'XYZ'),
                                    (1,1,1))
        mx = BD.MatrixLocRotScale((0,0,0), 
                                Euler(Vector(invm.rotation)/1000, 'XYZ'),
                                (1,1,1))
        ed.matrix_world = mx @ neut
        mx, focal_len = BD.inv_to_cam(invm.rotation, invm.zoom)
        ed.data.lens = focal_len

        ed['BSInvMarker_Name'] = invm.name
        ed['BSInvMarker_RotX'] = invm.rotation[0]
        ed['BSInvMarker_RotY'] = invm.rotation[1]
        ed['BSInvMarker_RotZ'] = invm.rotation[2]
        ed['BSInvMarker_Zoom'] = invm.zoom

        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)

        # Set up the render resolution to work for the inventory marker camera.
        self.context.scene.render.resolution_x = 1400
        self.context.scene.render.resolution_y = 1200


    def import_furniture_markers(self, node, parent_obj, fm:P.BSFurnitureMarkerNode):
        """
        Import furniture markers from BSFurnitureMarkerNode.
        Creates a Blender empty object for each furniture marker position.
        """
        # Import each furniture marker as a separate Blender object
        for i, marker in enumerate(fm.furniture_markers):
            bpy.ops.object.add(radius=1.0, type='EMPTY')
            obj = bpy.context.object
            obj.name = "BSFurnitureMarkerNode:" + fm.name
            obj.show_name = True
            obj.empty_display_type = 'SINGLE_ARROW'
            obj.location = Vector(marker.offset[:]) * self.scale
            obj.rotation_euler = (-pi/2, 0, marker.heading)
            obj.scale = Vector((40,10,10)) * self.scale
            obj['AnimationType'] = marker.animation_type_name
            obj['EntryPoints'] = marker.entry_points_list
            obj.parent = parent_obj
            self.objects_created.add(ReprObject(blender_obj=obj))
            BD.link_to_collection(self.collection, obj)


    def import_stringdata(self, node, parent_obj, stringdata:P.NiStringExtraData):
        bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
        ed = bpy.context.object
        ed.name = "NiStringExtraData:" + stringdata.name
        ed.show_name = True
        ed.empty_display_type = 'SPHERE'
        ed['NiStringExtraData_Name'] = stringdata.name
        ed['NiStringExtraData_Value'] = stringdata.string_data
        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)


    def import_behavior_graph_data(self, node, parent_obj, behavior:P.BSBehaviorGraphExtraData):
        bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
        ed = bpy.context.object
        ed.name = "BSBehaviorGraphExtraData:" + behavior.name
        ed.show_name = True
        ed.empty_display_type = 'SPHERE'
        ed['BSBehaviorGraphExtraData_Name'] = behavior.name
        ed['BSBehaviorGraphExtraData_Value'] = behavior.behavior_graph_file
        ed['BSBehaviorGraphExtraData_CBS'] = behavior.controls_base_skeleton
        ed.parent = parent_obj
        self.objects_created.add(ReprObject(blender_obj=ed))
        BD.link_to_collection(self.collection, ed)


    def import_cloth_data(self, node, parent_obj):
        for cd in self.nif.cloth_data:
            bpy.ops.object.add(radius=self.scale, type='EMPTY', location=self.next_loc())
            ed = bpy.context.object
            ed.name = "BSClothExtraData"
            ed.show_name = True
            ed.empty_display_type = 'SPHERE'
            ed['BSClothExtraData_Name'] = cd[0]
            ed['BSClothExtraData_Value'] = codecs.encode(cd[1], 'base64')
            ed.parent = parent_obj
            self.objects_created.add(ReprObject(blender_obj=ed))
            BD.link_to_collection(self.collection, ed)


    def import_skip(self, node, parent_obj, extblock):
        """Dummy import for extra data handled elsewhere."""
        pass


    extra_data_handlers = {
        'BSBound': import_bound,
        'BSBoneLODExtraData': import_bone_lod,
        'BSXFlags': import_bsx,
        'NiIntegerExtraData': import_integer,
        'BSInvMarker': import_inventory_marker,
        'BSFurnitureMarkerNode': import_furniture_markers,
        'NiStringExtraData': import_stringdata,
        'BSBehaviorGraphExtraData': import_behavior_graph_data,
        'BSConnectPoint::Parents': import_skip,
        }

    def import_extra(self, parent_obj:bpy.types.Object, n:P.NiNode):
        """ Import any extra data from the node, and create corresponding shapes. 
            If n is None, get the extra data from the root.
        """
        if not n: n = self.nif.rootNode
        if not parent_obj: parent_obj = self.root_object

        for extradata in n.extra_data():
            handler = self.extra_data_handlers.get(extradata.blockname)
            if handler:
                try:
                    handler(self, n, parent_obj, extradata)
                except Exception as e:
                    log.exception(f"Error importing extra data block {extradata.blockname} on node {n.name}")
            else:
                log.warning(f"Unknown extra data block {extradata.blockname} on node {n.name}") 
        
        # Cloth data is BSExtraData not NiExtraData, so find it separately.
        if n == self.nif.rootNode:
            self.import_cloth_data(n, parent_obj)

        # self.import_bound(n, parent_obj)
        # self.import_bone_lod(n, parent_obj)
        # self.import_bsx(n, parent_obj)
        # self.import_inventory_marker(n, parent_obj)
        # self.import_furniture_markers(n, parent_obj)
        # self.import_stringdata(n, parent_obj)
        # self.import_behavior_graph_data(n, parent_obj)
        # self.import_cloth_data(n, parent_obj)


    def bone_in_armatures(self, bone_name):
        """Determine whether a bone is in one of the armatures we've imported.
        Returns the bone or None.
        """
        for arma in self.target_armatures:
            if bone_name in arma.data.bones:
                return arma.data.bones[bone_name]
        return None


    def import_ninode(self, arma, ninode:P.NiNode, parent=None):
        """Create Blender representation of an NiNode

        Don't import the node if (1) it's already been imported, (2) it's been imported as
        a bone in the skeleton, or (3) it's the root node
        
        * arma = armature to add the bone to; may be None
        * ninode = nif node
        * parent = Blender parent for new object
        * Returns the Blender representation of the node, either an object or a bone, or
          none
        """
        robj = self.objects_created.find_nifnode(ninode)
        if robj: return robj.blender_obj
        obj = None

        bl_name = self.blender_name(ninode.name)
        bn = self.bone_in_armatures(bl_name)
        if bn: return bn 

        if not parent: parent = self.root_object
        skelbone = None
        if self.reference_skel and ninode.name in self.reference_skel.nodes:
            skelbone = self.reference_skel.nodes[ninode.name]

        elif ninode.file.game == "FO4" and ninode.name in fo4FaceDict.byNif:
            skelbone = fo4FaceDict.byNif[ninode.name]

        if (skelbone and arma) or (parent and type(parent) == bpy.types.Bone):
            # IF have not created this as bone in an armature already AND it's a known
            # skeleton bone, AND we have an armature, OR if its parent is abone in the
            # armature THEN create it as an armature bone even tho it's not used in the
            # shape
            arma = self.armature
            BD.ObjectSelect([arma])
            bpy.ops.object.mode_set(mode = 'EDIT')
            bn = self.add_bone_to_arma(arma, self.blender_name(ninode.name), ninode.name)
            bpy.ops.object.mode_set(mode = 'OBJECT')
            return bn

        # If not a known skeleton bone, just import as an EMPTY object
        if self.context.object and (not self.context.object.hide_get()): 
            bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.add(radius=1.0, type='EMPTY', )
        obj = bpy.context.object
        obj.name = ninode.name
        obj["pynBlockName"] = ninode.blockname
        obj["pynNodeName"] = ninode.name
        if hasattr(ninode.properties, 'valueNodeFlags'):
            obj["pynValueNodeFlags"] = BSValueNodeFlags(ninode.properties.valueNodeFlags).fullname
        # if ninode.blockname == 'BSValueNode':
        #     obj["pynValue"] = ninode.properties.value
        #     obj["pynValueNodeFlags"] = BSValueNodeFlags(ninode.properties.valueNodeFlags).fullname
        if hasattr(ninode, 'flags'):
            obj["pynNodeFlags"] = NiAVFlags(ninode.flags).fullname
        #     # NiControllerSequence blocks don't have flags
        #     obj["pynNodeFlags"] = NiAVFlags(ninode.flags).fullname
        # except:
        #     pass
        ninode.properties.extract(obj, ignore=NISHAPE_IGNORE, game=ninode.file.game)

        # Only the root node gets the import transform. It gets applied to all children automatically.
        if ninode.id == 0: 
            bpy.ops.object.mode_set(mode = 'OBJECT')
            obj.name = ninode.name + ":ROOT"
            obj["pynRoot"] = True
            obj[PYN_BLENDER_XF_PROP] = MatNearEqual(self.import_xf, BD.blender_import_xf)
            obj[PYN_GAME_PROP] = self.nif.game
            obj.empty_display_type = 'CONE'

            try:
                mx = self.import_xf @ BD.transform_to_matrix(ninode.transform)
            except:
                mx = Matrix.Identity(4)
            obj.matrix_local = mx

            self.root_object = obj
            parent = None
        else:
            obj.matrix_local = BD.transform_to_matrix(ninode.transform)

        if parent:
            if type(parent) == bpy.types.Object:
                obj.parent = parent
            else:
                # Can't set a bone as parent, but get the node in the right position
                obj.matrix_local = BD.apply_scale_xf(
                    BD.transform_to_matrix(ninode.global_transform), self.scale) 
                obj.parent = self.root_object
        self.objects_created.add(ReprObject(blender_obj=obj, nifnode=ninode))
        BD.link_to_collection(self.collection, obj)

        try:
            if ninode.collision_object and self.settings.import_collisions:
                collision.CollisionHandler.import_collision_obj(
                    self, ninode.collision_object, obj)
        except:
            log.exception(f"Error importing collisions {ninode.name}")

        try:
            self.import_extra(obj, ninode)
        except:
            log.exception(f"Error importing extra data {ninode.name}")

        try:
            if self.root_object != obj and ninode.controller and self.settings.import_animations: 
                # import animations if this isn't the root node. If it is, they may reference
                # any of the root's children and so wait until those can be imported.
                if self.anim_warn:
                    self.warn(f"io_scene_nifly does not support importing animations on Blender version {bpy.app.version} .")
                    self.anim_warn = False
                else:
                    self.controller_mgr.import_controller(ninode.controller, 
                                                          arma if arma else obj, 
                                                          obj)
        except:
            log.exception(f"Error importing controllers {ninode.name}")
        
        return obj


    def import_node_parents(self, arma, node: P.NiNode):
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
        """
        Import any NiNodes that don't have any special purpose--likely skeleton bones
        that aren't used in shapes.
        """
        original_bones = set()
        if arma:
            for n in arma.data.bones.keys():
                original_bones.add(n)

        for nm, n in nif.nodes.items():
            if (# Isn't collision, or we are importing collisions
                (not nm.startswith('bhk') or self.settings.import_collisions) 
                # Isn't a shader node, which are handled with their parent
                and (not n.__class__.__name__.startswith('NiShader'))
                # Isn't an editor marker, or we are importing editor markers
                and ((not n.id in self.editor_markers) 
                     or (not self.settings.smart_editor_markers))): 
                p = self.import_node_parents(arma, n)
                self.import_ninode(arma, n, p)
        
        if arma:
            # Set the pose position for the bones we just added
            new_bones = set(arma.data.bones.keys()).difference(original_bones)
            bone_names = [(self.nif_name(n), n) for n in new_bones]
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
            

    def import_shape(self, the_shape: P.NiShape):
        """ Import the shape to a Blender object, translating bone names if requested
            
        * self.objects_created = List of objects created, extended with objects associated
          with this shape. Might be more than one because of extra data nodes.
        * self.loaded_meshes = List of Blender objects created that represent meshes,
          extended with this shape.
        * self.nodes_loaded = Dictionary mapping blender name : P.NiShape from nif
        """
        try:
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
            try:
                new_object["pynNodeFlags"] = NiAVFlags(the_shape.flags).fullname
                if the_shape.properties.vertexDesc:
                    new_object["pynVertexDesc"] = VertexFlags(the_shape.properties.vertexDesc).fullname
            except Exception as e:
                log.warn(f"Error setting pynVertexDesc for {new_object.name}: {e}")
            self.loaded_meshes.append(new_object)
            self.nodes_loaded[new_object.name] = the_shape
        
            if not self.settings.mesh_only:
                self.objects_created.add(ReprObject(new_object, the_shape))
                
                import_colors(new_mesh, the_shape)

                parent = self.import_node_parents(None, the_shape) 

                # Parent the shape. Skinned meshes will be parented to the parent found in 
                # the nif, not to the armature. 
                if parent: # and parent != self.root_object: # and not the_shape.bone_names:
                    new_object.parent = parent

                BD.mesh_create_uv(new_object.data, the_shape.uvs)
                self.mesh_create_bone_groups(the_shape, new_object)
                mesh_create_partition_groups(the_shape, new_object)
                for f in new_mesh.polygons:
                    f.use_smooth = True

                new_mesh.validate(verbose=True)

                if the_shape.normals:
                    mesh_create_normals(new_object.data, the_shape.normals)

                shader_io.ShaderImporter().import_material(new_object, the_shape, BD.asset_path)

                if the_shape.collision_object and self.settings.import_collisions:
                    collision.CollisionHandler.import_collision_obj(
                        self, the_shape.collision_object, new_object)

                if self.controller_mgr:
                    # Importing animations.
                    if the_shape.controller:
                        self.controller_mgr.import_controller(
                            the_shape.controller,
                            target_object=new_object,
                            target_element=new_object)
                        
                    elif the_shape.shader.controller:
                        self.controller_mgr.import_controller(
                            the_shape.shader.controller,
                            target_object=new_object, 
                            target_element=new_object.active_material.node_tree)
                    
                self.import_extra(new_object, the_shape)

                new_object[PYN_GAME_PROP] = self.nif.game
                new_object[PYN_BLENDER_XF_PROP] = MatNearEqual(self.import_xf, BD.blender_import_xf)
                new_object[PYN_RENAME_BONES_PROP] = self.settings.rename_bones
                new_object[PYN_RENAME_BONES_NIFTOOLS_PROP] = self.settings.rename_bones_niftools

            BD.link_to_collection(self.collection, new_object)

        except Exception as e:
            log.exception(f"Error importing shape {the_shape.name}: {e}")


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
                shape_bone_xf = (
                    obj.matrix_local @ BD.apply_scale_xf(BD.bind_position(shape, b), self.scale) )
                arma_xf = BD.get_bone_xform(arma, blend_name, shape.file.game, False, False)
                if not MatNearEqual(shape_bone_xf, arma_xf):
                    is_ok = False
                    this_offset = shape_bone_xf @ arma_xf 
                    if offset_xf:
                        if not MatNearEqual(this_offset, offset_xf):
                            offset_consistent = False
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

        if import_pose is set, we return self.armature. That's either the one selected
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

        if self.settings.import_pose:
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
        if (self.settings.create_bones and self.reference_skel 
                and nifname in self.reference_skel.nodes):
            bone_xform = BD.transform_to_matrix(self.reference_skel.nodes[nifname].global_transform)
            bone = BD.create_bone(armdata, bone_name, bone_xform, 
                               self.nif.game, self.scale, 0)
        else:
            xf = self.nif.get_node_xform_to_global(nifname) 
            bone_xform = BD.transform_to_matrix(xf)
            # We have the world position of the bone, so we don't need the armature's 
            # skin transform. (We might need the armature object's Blender transform. 
            # But that's always the identity.)
            bone = BD.create_bone(armdata, bone_name, bone_xform, 
                               self.nif.game, self.scale, 0)

        return bone
    

    def set_bone_poses(self, arma, nif:P.NifFile, bonelist:list):
        """
        Set the pose transform of all the given bones. Pose transform is the transform on
        the P.NiNode in the nif being imported.
        *   bonelist = [(nif-name, blender-name), ...]
        """
        for bn, blname in bonelist:
            if bn in nif.nodes and blname in arma.pose.bones:
                nif_bone = nif.nodes[bn]
                if isinstance(nif_bone, P.NiNode) and nif_bone.name != nif.rootName:
                    bone_xf = BD.transform_to_matrix(nif_bone.global_transform)

                    if self.is_facegen:
                        try:
                            # Facegen bone rotations are missing--get them from the skeleton
                            skel_bone = self.reference_skel.nodes['HEAD' if bn=='Head' else bn]
                            skb_xf = BD.transform_to_matrix(skel_bone.global_transform)
                            skbloc, skbrot, skbscale = skb_xf.decompose()
                            bloc, brot, bscale = bone_xf.decompose()
                            bone_xf = BD.MatrixLocRotScale(bloc, skbrot, bscale)
                        except:
                            log.exception(f"Error handling facegen bone rotations {bn}")

                    pb_xf = BD.apply_scale_transl(bone_xf, self.scale)
                    pose_bone = arma.pose.bones[blname]
                    pbmx = BD.get_pose_blender_xf(bone_xf, self.nif.game, self.scale)
                    pose_bone.matrix = pbmx
                    bpy.context.view_layer.update()


    def set_all_bone_poses(self, arma, nif:P.NifFile):
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
        BD.ObjectSelect([arma])
        
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

                if (parentname is None and self.settings.create_bones
                        and not BD.is_facebone(bonename)):
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
                        new_parent = self.add_bone_to_arma(arma, parentname, parentnifname)
                        bones_to_parent.append(parentname)  
                        arm_data.edit_bones[bonename].parent = new_parent
                        new_bones.append((parentnifname, parentname))
                    else:
                        arm_data.edit_bones[bonename].parent = arm_data.edit_bones[parentname]

            i += 1

        bpy.ops.object.mode_set(mode='OBJECT')
        arma.update_from_editmode()
        self.set_all_bone_poses(arma, self.nif)
        bpy.ops.object.mode_set(mode='OBJECT')

        if self.settings.import_collisions:
            for bonenode in collisions:
                collision.CollisionHandler.import_collision_obj(
                    self, bonenode.collision_object, arma, bonenode)
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
        BD.ObjectSelect([arma])
        bpy.ops.object.mode_set(mode='EDIT')
        for b in arma.data.edit_bones:
            b.roll += -90 * pi / 180
        bpy.ops.object.mode_set(mode='OBJECT')
        arma.update_from_editmode()

    
    def add_bones_to_arma(self, arma, nif, bone_names):
        """Add all the bones in the list to the armature.
        * bone_names = nif bone names to import
        """
        BD.ObjectSelect([arma], active=True)
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


    def make_armature(self, the_coll: bpy.types.Collection, name_prefix=""):
        """Make a Blender armature from the given info. 
            
            Inputs:
            *   the_coll = Collection to put the armature in. 
            *   bone_names = bones to include in the armature.
            *   self.armature = existing armature to add the new bones to. May be None.
            
            Returns: 
            * new armature, set as active object
            """
        arm_data = bpy.data.armatures.new(BD.arma_name(name_prefix + self.nif.rootName))
        arma = bpy.data.objects.new(BD.arma_name(name_prefix + self.nif.rootName), arm_data)
        arma.parent = self.root_object
        BD.link_to_collection(the_coll, arma)

        if self.nif.dict.use_niftools:
            with suppress(AttributeError):
                # Support NifTools axis settings
                arm_data.niftools.axis_forward = "Z"
                arm_data.niftools.axis_up = "-X"

        arma[PYN_BLENDER_XF_PROP] = MatNearEqual(self.import_xf, BD.blender_import_xf)
        arma[PYN_RENAME_BONES_PROP] = self.settings.rename_bones
        arma[PYN_ROTATE_BONES_PRETTY_PROP] = self.settings.rotate_bones_pretty
        arma[PYN_RENAME_BONES_NIFTOOLS_PROP] = self.settings.rename_bones_niftools

        return arma


    def is_compatible_skeleton(self, skin_xf:Matrix, shape:P.NiShape, skel:P.NifFile) -> bool:
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
                m1 = skin_xf @ BD.transform_to_matrix(shape.get_shape_skin_to_bone(b)).inverted()
                m2 = BD.transform_to_matrix(skel.nodes[b].global_transform)
                # We give a fairly generous allowance for how close is close enough. 0.03 
                # allows the FO4 meshes to be parented to their skeletons. 
                if not MatNearEqual(m1, m2, epsilon=variance):
                    return False
        return True


    def set_parent_arma(self, arma, obj, nif_shape:P.NiShape, s2a_xf:Matrix):
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
        obj.matrix_local = unscaled_skin_xf.copy()
        skin_xf = unscaled_skin_xf.copy()

        # Create bones. If import_pose, positions are the P.NiNode positions of the
        # bone. Otherwise, they are the skin-to-bone transforms (bind position).
        BD.ObjectSelect([arma])
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
                    xf = BD.transform_to_matrix(bone_node.global_transform)
                elif self.settings.import_pose: ### and not self.is_facegen:
                    # Using nif locations of bones. 
                    bone_node = nif_shape.file.nodes[bn]
                    xf = BD.transform_to_matrix(bone_node.global_transform)
                else:
                    # Have to trust the bind position in the nif.
                    # Facegen nifs always use the bind position.
                    bone_shape_xf = BD.transform_to_matrix(nif_shape.get_shape_skin_to_bone(bn)).inverted()
                    xf = skin_xf @ bone_shape_xf
                BD.create_bone(arma.data, blname, xf, self.nif.game, 1.0, 0)
                new_bones.append((bn, blname))

        # Do the pose in a separate pass so we don't have to flip between modes.
        if not self.settings.import_pose:
            bpy.ops.object.mode_set(mode = 'OBJECT')
            self.set_bone_poses(arma, self.nif, new_bones)
        bpy.ops.object.mode_set(mode = 'OBJECT')

        BD.ObjectSelect([obj])
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

            BD.ObjectSelect([arma], active=True)
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.armature_apply()
            bpy.ops.object.mode_set(mode='OBJECT')

            mnew = obj.modifiers.new("Armature", 'ARMATURE')
            mnew.object = arma
    

    def import_nif(self, priors=None):
        """
        Import a single file.

        If the vert count of a new shape matches that of a shape in the "priors" list,
        only import the mesh. It will be merged as a shape key later.
        """
        log.info(f"Importing {self.nif.game} file {self.nif.filepath}")

        if self.settings.create_collection:
            self.collection = bpy.data.collections.new(os.path.basename(self.nif.filepath))
            self.context.scene.collection.children.link(self.collection)
        
        if self.settings.import_animations:
            self.controller_mgr = controller.ControllerHandler(self)

        self.editor_markers = connectpoint.connectpoints_with_markers(self.nif)

        # Each file gets its own root object in Blender.
        self.root_object = None

        if self.nif.rootNode.blockname == "NiControllerSequence" and self.controller_mgr:
            # Top-level node of a KF animation file is a Controller Sequence. 
            # Import it and done.
            self.controller_mgr.import_controller(
                self.nif.rootNode, target_object=self.armature, target_element=self.armature,
                animation_name=self.animation_name)
            return

        self.is_facegen = ("BSFaceGenNiNodeSkinned" in self.nif.nodes)
        if self.is_facegen: 
            self.settings.import_pose = False
        # Import the root node
        self.import_ninode(None, self.nif.rootNode)

        imp_mesh_only = self.settings.mesh_only

        # Import shapes
        for s in self.nif.shapes:
            if self.nif.game in ['FO4', 'FO76'] and BD.is_facebones(s.bone_names):
                self.nif.dict = fo4FaceDict
            self.nif.dict.use_niftools = self.settings.rename_bones_niftools
            self.import_shape(s)
            imp_mesh_only = (imp_mesh_only 
                or (any(len(s.verts) == len(pc.data.vertices) for pc in priors) 
                    if priors else False))

        orphan_shapes = set([o for o in self.objects_created.blender_objects()
                             if o.parent==None and not 'pynRoot' in o])
            
        if imp_mesh_only:
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
                self.target_armatures.add(self.armature)
                self.connect_armature(self.armature)
                self.group_bones(self.armature)
            else:
                # List of armatures available for shapes
                if self.armature:
                    self.target_armatures.add(self.armature) 

                if self.settings.apply_skinning:
                    for obj in self.loaded_meshes:
                        sh = self.nodes_loaded[obj.name]
                        self.ref_compat = self.is_compatible_skeleton(obj.matrix_local, sh, self.reference_skel)
                        self.set_object_xf(sh, obj)
                        if sh.has_skin_instance:
                            target_arma, target_xf = self.find_compatible_arma(obj, self.target_armatures)
                            self.armature = target_arma
                            new_arma = self.set_parent_arma(target_arma, obj, sh, target_xf) #target_xf)
                            if self.is_facegen: self.facegen_cleanup(obj)
                            if not target_arma:
                                self.target_armatures.add(new_arma)
                                self.armature = new_arma
                            orphan_shapes.discard(obj)

                for arma in self.target_armatures:
                    if self.settings.create_bones:
                        bonenames = [n.name for n in self.nif.nodes.values()
                                     if n.blockname == 'P.NiNode']
                        self.add_bones_to_arma(arma, self.nif, bonenames)
                    self.connect_armature(arma)
                    self.group_bones(arma)
                    if self.controller_mgr:
                        self.controller_mgr.import_bone_animations(self.armature)
    
            # Gather up any NiNodes that weren't captured any other way 
            self.import_loose_ninodes(self.nif)

            # Import nif-level elements
            self.connect_points.import_points(
                nif=self.nif, 
                root_object=self.root_object, 
                armature=self.armature, 
                objects_created=self.objects_created, 
                scale=self.scale, 
                next_loc=self.next_loc(), 
                editor_markers=self.editor_markers,
                smart_markers=self.settings.smart_editor_markers,)
        
            # Import top-level animations
            if self.controller_mgr and self.nif.rootNode.controller:
                self.controller_mgr.import_controller(
                    self.nif.rootNode.controller, self.root_object, self.root_object)

            cp = self.connect_points.child_in_nif(self.nif)
            if cp:
                self.root_object.parent = cp.blender_obj

        # Anything not yet parented gets put under the root.
        for o in orphan_shapes:
            o.parent = self.root_object


    def import_tris(self):
        """Import any tri files associated with the nif."""
        imported_meshes = [x for x in self.objects_created.blender_objects() if x.type == 'MESH']
        tpf = find_trip(self.nif)
        if tpf:
            import_trip(tpf, imported_meshes)
        elif len(imported_meshes) == 1:
            # No tri files if there's a trip file; 
            # must be only a single mesh to have a tri file.
            trifiles = find_tris(self.nif)
            for tf in trifiles:
                tf = open_tri(tf)
                if tf and isinstance(tf, TriFile):
                    import_tri(tf, imported_meshes[0])


    def merge_shapes(self, filename, obj_list, new_filename, new_obj_list):
        """
        Merge new_obj_list into obj_list as shape keys. 
        If filenames follow io_scene_nifly's naming conventions, create a shape key for the
        base shape and rename the shape keys appropriately.
        """
        # Can name shape keys to our convention if they end with underscore-something and
        # everything before the underscore is the same
        fn_parts = filename.split('_')
        new_fn_parts = new_filename.split('_')
        rename_keys = len(fn_parts) > 1 and len(new_fn_parts) > 1 and fn_parts[0:-1] == new_fn_parts[0:-1]
        obj_shape_name = '_' + fn_parts[-1]

        for newobj in new_obj_list:
            if newobj.type == 'MESH':
                matching_objs = [obj for obj in obj_list 
                    if BD.nonunique_name(obj.name) == BD.nonunique_name(newobj.name)]
                if len(matching_objs) > 0:
                    obj = matching_objs[0]
                    if len(obj.data.vertices) == len(newobj.data.vertices):
                        BD.ObjectSelect([obj, newobj])

                        if rename_keys:
                            if (not obj.data.shape_keys) or (not obj.data.shape_keys.key_blocks) \
                                    or (obj_shape_name not in [s.name for s in obj.data.shape_keys.key_blocks]):
                                if not obj.data.shape_keys:
                                    obj.shape_key_add(name='Basis')
                                obj.shape_key_add(name=obj_shape_name)

                        bpy.ops.object.join_shapes()
                        self.objects_created.remove(newobj)
                        bpy.data.objects.remove(newobj)

                        obj.data.shape_keys.key_blocks[-1].name = '_' + new_fn_parts[-1]


    def execute(self):
        """Perform the import operation as previously defined"""
        P.NifFile.clear_log()

        prior_vertcounts = dict()
        prior_fn = ''
        prior_shapes = None
        if self.settings.import_shapekeys:
            prior_shapes = set()
            for obj in bpy.context.scene.objects:
                if obj.select_get() and obj.type == 'MESH':
                    prior_vertcounts[obj.name] = len(obj.data.vertices)

        log.info(str(self))

        if self.settings.rotate_bones_pretty:
            BD.game_rotations = BD.game_rotations_pretty
        else:
            BD.game_rotations = BD.game_rotations_none

        for this_file in self.filename_list:
            fn, fext = os.path.splitext(os.path.basename(this_file))

            if fext.lower() == ".nif":
                self.nif = P.NifFile(this_file)
            elif fext in [".hkx", ".xml"]:
                self.nif = P.hkxSkeletonFile(this_file)
            else:
                ValueError("Import file of unknown type.")
            if not self.reference_skel:
                self.reference_skel = self.nif.reference_skel

            # Determine whether the new shapes should be merged into existing shapes
            this_vertcounts = None
            if self.settings.import_shapekeys:
                this_vertcounts = dict()
                for nifobj in self.nif.shapes:
                    this_vertcounts[nifobj.name] = len(nifobj.verts)

                for name, vc in this_vertcounts.items():
                    if name in prior_vertcounts:
                        if vc == prior_vertcounts[name]:
                            prior_shapes.add(bpy.context.scene.objects[name]) 

            have_priors = (prior_shapes is not None and len(prior_shapes) > 0)
            self.loaded_meshes = []
            self.import_nif(prior_shapes)
            if self.settings.import_tris:
                self.import_tris()

            if have_priors:
                self.merge_shapes(prior_fn, prior_shapes, fn, self.loaded_meshes)
            elif prior_shapes is not None:
                prior_fn = fn
                for m in self.loaded_meshes:
                    prior_shapes.add(m)
                prior_vertcounts = this_vertcounts

        # Connect up all the children loaded in this batch with all the parents loaded in this batch
        self.connect_points.connect_all()


    @classmethod
    def do_import(cls, filename, settings=None, collection=None, reference_skel=None,
                  context=bpy.context, chargen="chargen", scale=1.0):
        """
        Perform a nif import operation.
        """

        armatures = set()
        targ_objs = []

        # Only use the active object if it's selected and visible. Too confusing otherwise.
        obj = bpy.context.object
        if obj and obj.select_get() and (not obj.hide_get()):
            if obj.type == "ARMATURE":
                armatures.add(obj)
                log.info(f"Active object is an armature, parenting shapes to {obj.name}")
            elif obj.type == 'MESH':
                prior_vertcounts = [len(obj.data.vertices)]
                targ_objs = [obj]
                log.info(f"Active object is a mesh, will import as shape key if possible: {obj.name}")

        imp = NifImporter(filename, targ_objs, armatures, import_settings=settings, 
                          collection=collection, reference_skel=reference_skel, 
                          context=context, chargen_ext=chargen, scale=scale)
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
    ) # type: ignore

    # At this point the io_scene_nifly preferences have not been initialized. So we have to
    # use the defaults here.
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},) # type: ignore

    create_bones: bpy.props.BoolProperty(
        name="Create bones",
        description="Create vanilla bones as needed to make skeleton complete.",
        default=ImportSettings.__dataclass_fields__["create_bones"].default) # type: ignore

    rename_bones: bpy.props.BoolProperty(
        name="Rename bones",
        description="Rename bones to conform to Blender's left/right conventions.",
        default=ImportSettings.__dataclass_fields__["rename_bones"].default) # type: ignore

    rotate_bones_pretty: bpy.props.BoolProperty(
        name="Pretty bone orientation",
        description="Orient bones to show structure.",
        default=ImportSettings.__dataclass_fields__["rotate_bones_pretty"].default) # type: ignore

    blender_xf: bpy.props.BoolProperty(
        name="Use Blender orientation",
        description="Use Blender's orientation and scale",
        default=ImportSettings.__dataclass_fields__["blender_xf"].default) # type: ignore

    import_animations: bpy.props.BoolProperty(
        name="Import animations",
        description="Import any animations embedded in the nif.",
        default=ImportSettings.__dataclass_fields__["import_animations"].default) # type: ignore

    import_collisions: bpy.props.BoolProperty(
        name="Import collisions",
        description="Import any collisions embedded in the nif.",
        default=ImportSettings.__dataclass_fields__["import_collisions"].default) # type: ignore

    import_tris: bpy.props.BoolProperty(
        name="Import tri files",
        description="Import any tri files that appear to be associated with the nif.",
        default=ImportSettings.__dataclass_fields__["import_tris"].default) # type: ignore

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename bones as per NifTools",
        description="Rename bones using NifTools' naming scheme to conform to Blender's left/right conventions.",
        default=ImportSettings.__dataclass_fields__["rename_bones_niftools"].default) # type: ignore

    import_shapekeys: bpy.props.BoolProperty(
        name="Import as shape keys",
        description="Import similar objects as shape keys where possible on multi-file imports.",
        default=ImportSettings.__dataclass_fields__["import_shapekeys"].default) # type: ignore

    apply_skinning: bpy.props.BoolProperty(
        name="Apply skin to mesh",
        description="Applies any transforms defined in shapes' partitions to the final mesh.",
        default=ImportSettings.__dataclass_fields__["apply_skinning"].default) # type: ignore

    import_pose: bpy.props.BoolProperty(
        name="Create armature from pose position",
        description="Creates any armature from the bone P.NiNode (pose) position.",
        default=ImportSettings.__dataclass_fields__["import_pose"].default) # type: ignore
    
    mesh_only: bpy.props.BoolProperty(
        name="Import mesh only",
        description="Import only the mesh, not armature or other elements.",
        default=ImportSettings.__dataclass_fields__["mesh_only"].default) # type: ignore

    smart_editor_markers: bpy.props.BoolProperty(
        name="Smart editor marker handling",
        description="Do not create editor marker objects on import; recreate on export.",
        default=ImportSettings.__dataclass_fields__["smart_editor_markers"].default) # type: ignore

    create_collection: bpy.props.BoolProperty(
        name="Import to collections",
        description="Import each nif to its own new collection.",
        default=ImportSettings.__dataclass_fields__["create_collection"].default) # type: ignore

    reference_skel: bpy.props.StringProperty(
        name="Reference skeleton",
        description="Reference skeleton to use for the bone hierarchy",
        default=ImportSettings.__dataclass_fields__["reference_skeleton"].default) # type: ignore
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = ImportSettings()


    @classmethod
    def poll(cls, context):
        if not P.nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False
        return True


    def invoke(self, context, event):
        """
        Get per-import settings for this import. Offer the io_scene_nifly preferences as defaults.
        """
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_import_path_nif:
            self.filepath = str(Path(context.window_manager.pynifly_last_import_path_nif)
                                / Path(self.filepath))
            
        # Load defaults. Use the addon's defaults unless something about the current
        # objects override them.
        pyniflyPrefs = bpy.context.preferences.addons["io_scene_nifly"].preferences
        self.blender_xf = pyniflyPrefs.blender_xf
        self.rename_bones = pyniflyPrefs.rename_bones
        self.rename_bones_niftools = pyniflyPrefs.rename_bones_niftools
        self.rotate_bones_pretty = pyniflyPrefs.rotate_bones_pretty
        self.import_tris = pyniflyPrefs.import_tris

        if bpy.context.object and bpy.context.object.select_get() and bpy.context.object.type == 'ARMATURE':
            # We are loading into an existing armature. The various settings should match.
            arma = bpy.context.object
            self.blender_xf = arma.get(PYN_BLENDER_XF_PROP, pyniflyPrefs.blender_xf)
            self.rename_bones = arma.get(PYN_RENAME_BONES_PROP, pyniflyPrefs.rename_bones)
            self.rename_bones_niftools = arma.get(PYN_RENAME_BONES_NIFTOOLS_PROP, pyniflyPrefs.rename_bones_niftools)
            self.rotate_bones_pretty = arma.get(PYN_ROTATE_BONES_PRETTY_PROP, pyniflyPrefs.rotate_bones_pretty)
            # When loading into an armature, ignore the nif's bind position--use the
            # armature's.
            self.import_pose = True
        return super().invoke(context, event)


    def execute(self, context):
        self.log_handler = BD.LogHandler.New(bl_info, "IMPORT", "NIF")

        self.status = {'FINISHED'}
        fullfiles = ''
        self.context = context
        self.initial_frame = context.scene.frame_current
        try:
            context.scene.frame_set(1)

            P.NifFile.Load(P.nifly_path)

            folderpath = os.path.dirname(self.filepath)
            filenames = [f.name for f in self.files]
            if len(filenames) > 0:
                fullfiles = [os.path.join(folderpath, f.name) for f in self.files]
            else:
                fullfiles = [self.filepath]

            armatures = set()
            targ_objs = []

            # Only use the active object if it's selected and visible. Too confusing otherwise.
            obj = bpy.context.object
            if obj and obj.select_get() and (not obj.hide_get()):
                if obj.type == "ARMATURE":
                    armatures.add(obj)
                    log.info(f"Active object is an armature, parenting shapes to {obj.name}")
                elif obj.type == 'MESH':
                    prior_vertcounts = [len(obj.data.vertices)]
                    targ_objs = [obj]
                    log.info(f"Active object is a mesh, will import as shape key if possible: {obj.name}")

            give_anim_warning = False
            if self.import_animations and not hasattr(bpy.types, 'ActionSlot'):
                self.import_animations = False
                give_anim_warning = True

            # import_settings = ImportSettings()
            # import_settings.create_bones = self.create_bones
            # import_settings.rename_bones = self.rename_bones
            # import_settings.rotate_bones_pretty = self.rotate_bones_pretty
            # import_settings.rename_bones_niftools = self.rename_bones_niftools
            # import_settings.import_shapekeys = self.import_shapekeys
            # import_settings.import_animations = self.import_animations
            # import_settings.import_collisions = self.import_collisions
            # import_settings.import_tris = self.import_tris
            # import_settings.apply_skinning = self.apply_skinning
            # import_settings.smart_editor_markers = self.smart_editor_markers
            # import_settings.import_pose = self.import_pose
            # import_settings.create_collection = self.create_collection

            skel = None
            if self.reference_skel:
                skel = P.NifFile(self.reference_skel)
            
            xf = Matrix.Identity(4)
            if self.blender_xf:
                xf = BD.blender_import_xf

            coll = None
            if context.view_layer.active_layer_collection:
                coll = context.view_layer.active_layer_collection.collection
            
            imp = NifImporter(
                fullfiles, 
                targ_objs, 
                armatures, 
                import_settings=self, 
                collection=coll, 
                reference_skel=skel,
                base_transform=xf,
                context=context, 
                anim_warn = give_anim_warning
                )
            imp.execute()

            # Cleanup. Select all shapes imported, except the root node.
            objlist = [x for x in imp.objects_created.blender_objects() 
                        if x.type=='MESH' and not x.name.endswith(':BBX')]
            if (not objlist) and imp.armature:
                objlist = [imp.armature]
            BD.highlight_objects(objlist, context)
            BD.ObjectSelect(objlist)

        except:
            log.exception("Import of nif failed")
            self.report({"ERROR"}, "Import of nif failed, see console window for details")
            self.status = {'CANCELLED'}

        finally:
            self.log_handler.finish("IMPORT", fullfiles)
            self.context.scene.frame_set(self.initial_frame)

        # Save the directory path for next time
        wm = context.window_manager
        wm.pynifly_last_import_path_nif = self.filepath

        return self.status

    def __str__(self):
        return f"ImportNif: create_bones={self.create_bones}, rename_bones={self.rename_bones}, rotate_bones_pretty={self.rotate_bones_pretty}, rename_bones_niftools={self.rename_bones_niftools}, import_shapekeys={self.import_shapekeys}, import_animations={self.import_animations}, import_collisions={self.import_collisions}, import_tris={self.import_tris}, apply_skinning={self.apply_skinning}, smart_editor_markers={self.smart_editor_markers}, import_pose={self.import_pose}, create_collection={self.create_collection}, reference_skel='{self.reference_skel}'"
    