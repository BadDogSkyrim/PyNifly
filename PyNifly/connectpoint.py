"""Handles connect points for FO4."""
# Copyright © 2024, Bad Dog.

import bpy
import bpy.types
from mathutils import Matrix, Vector, Quaternion, Euler, geometry, Color
import blender_defs as BD
import nifdefs

CONNECT_POINT_SCALE = 1.0


def connection_name_root(s): 
    """Return the root part of a connection name ('P-Foo' -> 'Foo')"""
    parts = s.split('-', 1)
    if len(parts) < 2:
        print(f"WARNING: connection name malformed: {s}")
        return parts[0]
    return parts[-1]


def get_nifname(obj):
    n = BD.nonunique_name(obj)
    return n.split('::', 1)[-1]


def is_parent(obj):
    """Determine whether the given Blender object represets a parent connect point."""
    try:
        return obj.type == "EMPTY" and obj.name.startswith("BSConnectPointParents")
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
        return obj.type == "EMPTY" and obj.name.startswith("BSConnectPoint")
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
    def new(cls, scale, nif, cp, blendroot, blendarma, objectlist:BD.ReprObjectCollection):
        """
        Create a representation of a nif's parent connect point in Blender.

        Parent connect points are parented to their target object or bone.
        """
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
            pcp.parent = parentobj 
            if bonename: 
                pcp.parent_type = 'BONE'
                pcp.parent_bone = bonename
        else:
            pcp.parent = blendroot

        BD.link_to_collection(blendroot.users_collection[0], pcp)

        ro = BD.ReprObject(blender_obj=pcp, nifnode=cp)
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


    def import_points(self, nif, root_object, arma, objectlist, scale, location):
        ccp = ConnectPointChild.new(scale, nif, location, root_object.users_collection[0])
        if ccp: self.add(ccp)
        for cp in nif.connect_points_parent:
            self.add(ConnectPointParent.new(scale, nif, cp, root_object, arma, objectlist))


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
        Add all blender objects in "objects" representing connect points to this collection.
        """
        for obj in objects:
            self.add(obj)
            for child in obj.children:
                self.add(child)
            # t = connectpoint_type(obj)
            # if t == 'PARENT':
            #     cp = ConnectPointParent(get_nifname(obj), BD.ReprObject(blender_obj=obj))
            #     self.add(cp)
            # elif t == 'CHILD':
            #     cp = ConnectPointChild([get_nifname(obj)], BD.ReprObject(blender_obj=obj))
            #     self.add(cp)


    def child_in_nif(self, nif): 
        """
        Find the child object associated with the nif (for when multiple nifs are imported
        at once).
        """
        for cp in self.child:
            if cp.nif is nif:
                return cp
        return None
    

    def export_all(self, nif):
        """Export all connect points in collection to nif."""
        connect_par = []
        for cp in self.parents:
            obj = cp.obj.blender_obj
            buf = nifdefs.ConnectPointBuf()
            buf.name = (cp.name).encode('utf-8')
            buf.translation[0], buf.translation[1], buf.translation[2] \
                = obj.matrix_local.translation[:]
            buf.rotation[0], buf.rotation[1], buf.rotation[2], buf.rotation[3] \
                = obj.matrix_local.to_quaternion()[:]
            buf.scale = obj.matrix_local.to_scale()[0] / CONNECT_POINT_SCALE
            # buf.translation[0], buf.translation[1], buf.translation[2] \
            #     = obj.matrix_world.translation[:]
            # buf.rotation[0], buf.rotation[1], buf.rotation[2], buf.rotation[3] \
            #     = obj.matrix_world.to_quaternion()[:]
            # buf.scale = obj.matrix_world.to_scale()[0] / CONNECT_POINT_SCALE

            if obj and obj.parent:
                buf.parent = BD.nonunique_name(obj.parent).encode('utf-8')
                if obj.parent.type == 'ARMATURE' and obj.parent_type == 'BONE' and obj.parent_bone:
                    bonename = nif.nif_name(obj.parent_bone)
                    buf.parent = bonename.encode('utf-8')
            
            connect_par.append(buf)

        if connect_par:
            nif.connect_points_parent = connect_par

        if self.child:
            cp = self.child[0]
            nif.connect_pt_child_skinned = cp.skinned
            nif.connect_points_child = list(cp.names)
