"""Handles connect points for FO4."""
# Copyright © 2024, Bad Dog.

import bpy
import bpy.types
import math
from mathutils import Matrix, Vector, Quaternion, Euler, geometry, Color
import blender_defs as BD
from nifdefs import NiShapeBuf, AlphaPropertyBuf, ConnectPointBuf, NODEID_NONE
from pynifly import NifFile, BSEffectShaderProperty, check_return
import os
import logging

logging.basicConfig(encoding='utf-8', level=logging.DEBUG)
log = logging.getLogger("pynifly")

CONNECT_POINT_SCALE = 15.0

# P-WS-* don't get editor markers. Show them as emptys.
EDITOR_MARKER_COLORS = {
    'P-Balcony01':      Color((1.0, 0.498, 0.0)),
    'P-Ceiling':      Color((1.0, 0.0, 0.0)),
    'P-Corner01':       Color((1.0, 0.0, 1.0)),
    'P-Door':         Color((1.0, 1.0, 0.0)),
    'P-Floor':        Color((0.0, 1.0, 0.0)),
    'P-Wall':         Color((0.0, 0.0, 1.0)),
    'P-WallFlatEnd01':  Color((0.549, 1.0, 0.718)),
}
EDITOR_MARKER_COLOR_DEFAULT = Color((0.8, 0.8, 0.8))
EDITOR_MARKER_ALPHA = 0.750


def connectpoint_transform(cp, scale=1.0):
    """Return a connect point's transform as a Matrix."""
    return Matrix.LocRotScale(
        Vector(cp.translation[:]) * scale,
        Quaternion(cp.rotation[:]),
        ((cp.scale * CONNECT_POINT_SCALE * scale),) * 3
    )


def is_match_connectpoint(nifnode, cp):
    """
    Check whether the nifnode is the editor marker for the connect point cp.
    The nifnode's transform must match the connect point cp: same position
    and orientation.

    Editor markers have their flat side oriented towards -X with a null rotation. The
    matching connect point has a 90deg yaw.  
    """
    if not BD.VNearEqual(nifnode.transform.translation, cp.translation, epsilon=0.001):
        return False
    if not BD.NearEqual(nifnode.transform.scale, cp.scale, epsilon=0.001):
        return False
    nodeq = Matrix(nifnode.transform.rotation).to_quaternion()
    cpq = Quaternion(cp.rotation)
    cpq.rotate(Quaternion((0, 0, 1), math.radians(-90)))
    delta = nodeq.rotation_difference(cpq).angle
    return BD.NearEqual(delta, 0.0, epsilon=0.01)


def connectpoints_with_markers(nif):
    """
    Return a dictionary of connect points in the nif that have matching editor markers.
    Returns {editor_marker_id: connect_point, ...}

    There may be more than one editor marker for a connect point for unknown reasons; all
    will be included.
    """
    d = {}
    markers = [n for n in nif.node_ids.values() if n.name.startswith('EditorMarker')]
    for cp in nif.connect_points_parent:
        for em in markers:
            if is_match_connectpoint(em, cp):
                d[em.id] = cp
    return d


def is_editor_marker(nifnode):
    """Determine whether the given nif node is an editor marker."""
    if nifnode.name.startswith('EditorMarker'):
        if any(c for c in nifnode.file.connect_points_parent if is_match_connectpoint(nifnode, c)):
            return True
    return False


def has_editor_marker(obj, val:bool=True):
    """Determine whether the given connect point object should have an editor marker."""
    obj["pynEditorMarker"] = val


def connection_name_root(s): 
    """Return the root part of a connection name ('P-Foo' -> 'Foo')"""
    parts = s.split('-', 1)
    if len(parts) < 2:
        print(f"WARNING: connection name malformed: {s}")
        return parts[0]
    return parts[-1]


def get_nifname(obj):
    """Return the name for the nif. It may have a suffix like ".001"."""
    # n = BD.nonunique_name(obj)
    return obj.name.split('::', 1)[-1]


def is_parent(obj):
    """Determine whether the given Blender object represets a parent connect point."""
    try:
        return obj.name.startswith("BSConnectPointParents")
    except AttributeError:
        return False
    

def is_child(obj):
    """Determine whether the given Blender object represets a child connect point."""
    try:
        return obj.type == "EMPTY" and obj.name.startswith("BSConnectPointChild")
    except AttributeError:
        return False
    

def is_connectpoint(obj):
    """Determine whether the given Blender object represets a connect point."""
    try:
        return obj.name.startswith("BSConnectPoint")
    except AttributeError:
        return False
    

def connectpoint_type(obj):
    """Determine what kind of connect point we have. Returns None, 'PARENT', or 'CHILD'."""
    try:
        if obj.type == "EMPTY" and obj.name.startswith("BSConnectPoint"):
            if obj.name.startswith("BSConnectPointParent"): return 'PARENT'
            if obj.name.startswith("BSConnectPointChild"): return 'CHILD'
        return None
    except AttributeError:
        return None


class ConnectPointParent():
    def __init__(self, name, reprobj):
        self.name = name
        self.obj = reprobj

    @property
    def blender_obj(self):
        return self.obj.blender_obj

    @classmethod
    def new(cls, scale, nif, cp, blendroot, blendarma, objectlist:BD.ReprObjectCollection, editor_markers):
        """
        Create a representation of a nif's parent connect point in Blender.

        Parent connect points are parented to their target object or bone.

        Returns a ConnectPointParent object for the created connect point.
        """
        # Find the connect point's parent
        cpname = cp.name.decode('utf-8')
        parentobj = None
        parentname = cp.parent.decode('utf-8')
        bonename = None
        if parentname:
            parentimp = objectlist.find_nifname(nif, parentname)
            if parentimp:
                parentobj = parentimp.blender_obj
            elif (parentname in nif.nodes) and blendarma:
                # Parent not imported as an object, maybe it's a bone
                bonename = nif.blender_name(parentname)
                if bonename in blendarma.data.bones:
                    parentobj = blendarma

        # Create the connect point object. Use the imported editor marker if any. If
        # there's more than one, use one that's a mesh by preference.
        pcp = None
        # Get the editor markers for this connect point.
        idlist = [id for id, c in editor_markers.items() if c is cp]
        if idlist:
            # Get the Blender objects for the editor markers
            emlist = [emobj for emobj in objectlist if emobj.nifnode and emobj.nifnode.id in idlist]
            if emlist:
                meshlist = [em for em in emlist if em.blender_obj.type == 'MESH']
                if meshlist:
                    ro = meshlist[0]
                else:
                    ro = emlist[0]
                pcp = ro.blender_obj

        # Create an EMPTY if no editor marker
        if not pcp:
            bpy.ops.object.add(radius=scale, type='EMPTY')
            pcp = bpy.context.object
            pcp.show_name = True
            pcp.empty_display_type = 'ARROWS'

            mx = connectpoint_transform(cp, scale)
            pcp.matrix_world = mx

            ro = BD.ReprObject(blender_obj=pcp, nifnode=cp)

        pcp.name = "BSConnectPointParents" + "::" + cpname

        if parentobj:
            pcp.parent = parentobj 
            if bonename: 
                pcp.parent_type = 'BONE'
                pcp.parent_bone = bonename
        else:
            pcp.parent = blendroot

        BD.link_to_collection(blendroot.users_collection[0], pcp)

        return ConnectPointParent(cpname, ro)


class ConnectPointChild():
    def __init__(self, names, reprobj, nif=None, skinned=False):
        self.names = set(names)
        self.obj = reprobj
        self.nif = nif
        self.skinned = skinned

    @property
    def blender_obj(self):
        return self.obj.blender_obj

    @classmethod
    def new(cls, scale, nif, location, coll):
        """
        Create a representation of a nif's child connect point in Blender.
        Returns None if there is no child connect point.
        """
        if not nif.connect_points_child: return

        bpy.ops.object.add(radius=scale, type='EMPTY', location=location)
        obj = bpy.context.object
        obj.name = "BSConnectPointChildren::" + nif.connect_points_child[0]
        obj.show_name = True
        obj.empty_display_type = 'SPHERE'
        obj.location = (0,0,0)
        obj['PYN_CONNECT_CHILD_SKINNED'] = nif.connect_pt_child_skinned
        for i, n in enumerate(nif.connect_points_child):
            obj[f'PYN_CONNECT_CHILD_{i}'] = n
        BD.link_to_collection(coll, obj)
        
        ro = BD.ReprObject(blender_obj=obj)
        return ConnectPointChild(nif.connect_points_child, ro, nif=nif)
    

class ConnectPointCollection():
    """
    Handle a collection of connect points, which may have unknown parent/child relationships.
    """
    def __init__(self):
        self.parents = [] # Parent connect points
        self.child = [] # Child connect points
        self.keys = {} # Dict of {root_name: [[parent connect points], [child points]]}
    

    def add(self, cp):
        """
        Add a connect point cp to a collection. cp can be a parent or child connect point
        from a nif, or a Blender object representing a connect point.
        """
        if isinstance(cp, ConnectPointParent):
            self.parents.append(cp)
            k = connection_name_root(cp.name)
            if k in self.keys:
                self.keys[k][0].append(cp)
            else:
                self.keys[k] = [[cp], []]

        elif isinstance(cp, ConnectPointChild):
            self.child.append(cp)
            for n in cp.names:
                k = connection_name_root(n)
                if k in self.keys:
                    self.keys[k][1].append(cp)
                else:
                    self.keys[k] = [[], [cp]]

        elif is_parent(cp):
            n = get_nifname(cp)
            if not n in [p.name for p in self.parents]:
                p = ConnectPointParent(n, BD.ReprObject(cp, None))
                self.add(p)

        elif is_child(cp):
            names = set()
            names.add(get_nifname(cp))
            skinned = False
            for k in cp.keys():
                if k == 'PYN_CONNECT_CHILD_SKINNED':
                    skinned = bool(cp[k])
                elif k.startswith('PYN_CONNECT_CHILD'):
                    names.add(cp[k])
            c = ConnectPointChild(names, BD.ReprObject(cp, None), skinned=skinned)
            self.add(c)


    def import_points(self, nif, root_object, armature, objects_created, scale, next_loc,
                      editor_markers, smart_markers):
        """Import connect points from the nif into Blender.
        
        root_object: The Blender object representing the root node of the nif.
        armature: The Blender armature representing the nif's armature, if any.
        objects_created: The collection of imported objects. New connect points and editor marker
            objects are added to this collection.
        scale: The scale transform of the entire import.
        next_loc: The starting location to place empties that don't have natural locations.
        editor_markers: Dictionary of {editor_marker_id: connect_point} as returned by 
            connectpoints_with_markers().
        smart_markers: Whether to use smart editor markers.
        """
        ccp = ConnectPointChild.new(scale, nif, next_loc, root_object.users_collection[0])
        if ccp: self.add(ccp)
        
        for cp in nif.connect_points_parent:
            cpp = ConnectPointParent.new(
                scale, nif, cp, root_object, armature, objects_created, editor_markers)
            self.add(cpp)
            if smart_markers:
                cpp.obj.blender_obj["pynEditorMarker"] = (cp in editor_markers.values())


    def connect_all(self):
        """
        Connect all Blender objects that represent children in the current collection to
        their parents.
        """
        for cp in self.child:
            # A child could have multiple parents if the user has imported multiple
            # parents at once. If so, choose one.
            p = None
            for n in cp.names:
                k = connection_name_root(n)
                if k in self.keys:
                    if len(self.keys[k][0]) > 0:
                        p = self.keys[k][0][0]
                if p: break
            if p:
                constr = cp.blender_obj.constraints.new(type='COPY_TRANSFORMS')
                constr.target = p.blender_obj


    def add_all(self, objects):
        """
        Add all blender objects in "objects" representing connect points to this collection.
        """
        for obj in objects:
            self.add(obj)
            for child in obj.children:
                self.add(child)


    def child_in_nif(self, nif): 
        """
        Find the child object associated with the nif (for when multiple nifs are imported
        at once).
        """
        for cp in self.child:
            if cp.nif is nif:
                return cp
        return None
    

    def construct_editor_marker(self, nif, obj, asset_path, emtpl):
        """Construct an editor marker for the given connect point object."""
        new_prop:NiShapeBuf = emtpl.properties.copy()
        new_prop.nameID = new_prop.conrollerID = new_prop.collisionID = NODEID_NONE
        new_prop.skinInstanceID = new_prop.shaderPropertyID = new_prop.alphaPropertyID = NODEID_NONE
        transl = obj.matrix_world.translation
        new_prop.transform.translation = (transl[0], transl[1], transl[2])
        rot = obj.matrix_world.to_quaternion()
        rot.rotate(Quaternion((0, 0, 1), math.radians(-90)))
        mx = rot.to_matrix()
        new_prop.transform.rotation = (mx[0][:], mx[1][:], mx[2][:])
        new_em = nif.createShapeFromData(emtpl.name, 
                                         emtpl.verts,
                                         emtpl.tris,
                                         emtpl.uvs,
                                         emtpl.normals,
                                         props=new_prop,
                                         use_type=emtpl.properties.bufType,
                                         )

        new_em.shader.name = emtpl.shader.name
        new_em.shader._properties = emtpl.shader.properties.copy()
        new_em.save_shader_attributes()

        alpha = AlphaPropertyBuf()
        new_em.has_alpha_property = True
        new_em.alpha_property.properties.flags = emtpl.alpha_property.properties.flags
        new_em.alpha_property.properties.threshold = emtpl.alpha_property.properties.threshold
        new_em.save_alpha_property()


    def export_all(self, nif, asset_path):
        """Export all connect points in collection to nif."""
        connect_par = []
        nif_tpl = None
        shape_tpl = None
        for cp in self.parents:
            # Export the connect point
            obj = cp.obj.blender_obj
            transl = obj.matrix_local.translation
            rot = obj.matrix_local.to_quaternion()
            scale = obj.matrix_local.to_scale()[0]
            if obj.type == 'MESH':
                rot.rotate(Quaternion((0, 0, 1), math.radians(90)))
            buf = ConnectPointBuf()
            buf.name = BD.nonunique_name(cp.name).encode('utf-8')
            buf.translation[0], buf.translation[1], buf.translation[2] = transl[:]
            buf.rotation[0], buf.rotation[1], buf.rotation[2], buf.rotation[3] = rot[:]
            buf.scale = scale / CONNECT_POINT_SCALE

            if obj and obj.parent:
                buf.parent = BD.nonunique_name(obj.parent).encode('utf-8')
                if obj.parent.type == 'ARMATURE' and obj.parent_type == 'BONE' and obj.parent_bone:
                    bonename = nif.nif_name(obj.parent_bone)
                    buf.parent = bonename.encode('utf-8')
            
            connect_par.append(buf)

            ## No editor markers--they are exported as shapes
            # # Export an editor marker, if wanted
            # if obj.get("pynEditorMarker", True):
            #     if not nif_tpl:
            #         nif_tpl = NifFile(os.path.join(asset_path, "EditorMarker.nif"))
            #         shape_tpl = nif_tpl.shapes[0] 
            #     if shape_tpl:
            #         self.construct_editor_marker(nif, obj, asset_path, shape_tpl)
            #     elif not nif_tpl:
            #         log.warning("Failed to load EditorMarker.nif from asset path.")
            #         nif_tpl = -1 # Only warn once

        if connect_par:
            nif.connect_points_parent = connect_par

        if self.child:
            cp = self.child[0]
            nif.connect_pt_child_skinned = cp.skinned
            nif.connect_points_child = list(cp.names)
