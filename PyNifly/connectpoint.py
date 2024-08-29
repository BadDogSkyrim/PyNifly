"""Handles connect points for FO4."""
# Copyright © 2024, Bad Dog.

import bpy
from mathutils import Matrix, Vector, Quaternion, Euler, geometry, Color
import blender_defs as BD

CONNECT_POINT_SCALE = 1.0


def connection_name_root(s): 
    """Return the root part of a connection name ('P-Foo' -> 'Foo')"""
    parts = s.split('-', 1)
    if len(parts) < 2:
        print(f"WARNING: connection name malformed: {s}")
        return parts[0]
    return parts[-1]


def blender_to_nif(obj):
    return obj.name.split('::', 1)[-1]


def is_parent(obj):
    """Determine whether the given Blender object represets a parent connect point."""
    return obj.type == "EMPTY" and obj.name.startswith("BSConnectPointParents")
    

def is_connectpoint(obj):
    """Determine whether the given Blender object represets a connect point."""
    return obj.type == "EMPTY" and obj.name.startswith("BSConnectPoint")
    

def connectpoint_type(obj):
    """Determine what kind of connect point we have. Returns None, 'PARENT', or 'CHILD'."""
    if obj.type == "EMPTY" and obj.name.startswith("BSConnectPoint"):
        if obj.name.startswith("BSConnectPointParent"): return 'PARENT'
        if obj.name.startswith("BSConnectPointChild"): return 'CHILD'
    return None


class ConnectPointParent():
    def __init__(self, name, reprobj):
        self.name = name
        self.obj = reprobj

    @property
    def blender_obj(self):
        return self.obj.blender_obj

    @classmethod
    def new(cls, scale, cp, blendparent, objectlist:BD.ReprObjectCollection):
        """
        Create a representation of a nif's parent connect point in Blender.
        """
        cpname = cp.name.decode('utf-8')
        parentobj = None
        parentname = cp.parent.decode('utf-8')
        if parentname:
            parentobj = objectlist.find_nifname(parentname)

        bpy.ops.object.add(radius=scale, type='EMPTY')
        pcp = bpy.context.object
        pcp.name = "BSConnectPointParents" + "::" + cpname
        pcp.show_name = True
        pcp.empty_display_type = 'ARROWS'
        mx = Matrix.LocRotScale(
            Vector(cp.translation[:]) * scale,
            Quaternion(cp.rotation[:]),
            ((cp.scale * CONNECT_POINT_SCALE * scale),) * 3
        )
        # pcp.matrix_world = parent.matrix_world @ mx
        pcp.matrix_world = mx
        if parentobj:
            pcp.parent = parentobj.blender_obj
        else:
            pcp.parent = blendparent

        BD.link_to_collection(blendparent.users_collection[0], pcp)

        ro = BD.ReprObject(blender_obj=pcp, nifnode=cp)
        return ConnectPointParent(cpname, ro)


class ConnectPointChild():
    def __init__(self, names, reprobj, nif=None):
        self.names = names
        self.obj = reprobj
        self.nif = nif

    @property
    def blender_obj(self):
        return self.obj.blender_obj

    @classmethod
    def new(cls, scale, nif, location, coll):
        """
        Create a representation of a nif's child connect point in Blender.
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
        self.parents = []
        self.child = []
        self.keys = {} 
    

    def add(self, cp):
        """
        Add a connect point to a collection.
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


    def import_points(self, nif, root_object, objectlist, scale, location):
        self.add(ConnectPointChild.new(scale, nif, location, root_object.users_collection[0]))
        for cp in nif.connect_points_parent:
            self.add(ConnectPointParent.new(scale, cp, root_object, objectlist))


    def connect_all(self):
        """
        Connect all Blender objects that represent children in the current collection to
        their parents.
        """
        for cp in self.child:
            # A child could have multiple parents if the user has imported 
            # multiple parents at once. If so, choose one.
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
        Add all blender objects in objects to this collection.
        """
        for obj in objects:
            t = connectpoint_type(obj)
            if t == 'PARENT':
                cp = ConnectPointParent(blender_to_nif(obj), BD.ReprObject(blender_obj=obj))
                self.add(cp)
            elif t == 'CHILD':
                cp = ConnectPointChild(blender_to_nif(obj), BD.ReprObject(blender_obj=obj))
                self.add(cp)


    def child_in_nif(self, nif):
        """
        Find the child object associated with the nif (for when multiple nifs are imported
        at once).
        """
        for cp in self.child:
            if cp.nif is nif:
                return cp
        return None