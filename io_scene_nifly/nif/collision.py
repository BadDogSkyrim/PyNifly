"""Collision Import/Export for pyNifly"""

# Copyright © 2024, Bad Dog.

import math
import bpy
import bmesh
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
from ..pyn.nifconstants import (
    HAVOC_SCALE_FACTOR, game_collision_sf, SkyrimCollisionLayer, SkyrimHavokMaterial,
    bhkCOFlags)
from ..blender_defs import (MatrixLocRotScale, ObjectSelect, transform_to_matrix, 
                            find_box_info, append_if_new, MatrixLocRotScale)
from ..util.reprobj import ReprObject
from ..pyn.pynifly import *


COLLISION_BODY_IGNORE = [
    'angularDamping',
    'bhkRadius', 
    'childCount',
    'friction', 
    'guard', 
    'linearDamping', 
    'mass',
    'rotation', 
    'translation', 
    'transform', # on bhkSimpleShapePhantom
    'unused2_1', 
    'unused2_2', 
    'unused2_3', 
    'unused2_4',
    'unusedByte1',
    'unusedBytes2_0', 
    'unusedBytes2_1', 
    'unusedBytes2_2',
    'unusedInts1_0', 
    'unusedInts1_1', 
    'unusedInts1_2',
    ]
    

BOX_SHAPE_IGNORE = ['bhkDimensions']
CAPSULE_SHAPE_IGNORE = ['point1', 'point2']

COLLISION_COLOR = (0.559, 0.624, 1.0, 0.5) # Default color


def _get_or_create_push_nodegroup():
    """Return a Geometry Nodes group that expands a convex hull by Radius.

    Pipeline: Extrude Mesh (individual faces, offset=Radius) → Convex Hull.

    Extrude Mesh pushes each face outward by exactly Radius along its own normal.
    Convex Hull then wraps all the resulting vertices, which places each corner
    vertex at the intersection of the three adjacent offset face planes — the
    mathematically correct Minkowski expansion vertex.  The triangular facets
    the hull adds at original corners approximate the sphere caps.
    The node group is created once and reused for all polytope collision objects.
    """
    name = 'bhkPushOut'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    # Blender 4.0+ / 5.0 uses ng.interface rather than ng.inputs/outputs
    ng.interface.new_socket('Geometry', in_out='INPUT',  socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Radius',   in_out='INPUT',  socket_type='NodeSocketFloat')
    gin  = ng.nodes.new('NodeGroupInput')
    gout = ng.nodes.new('NodeGroupOutput')
    ext  = ng.nodes.new('GeometryNodeExtrudeMesh')
    ext.mode = 'FACES'
    ext.inputs['Individual'].default_value = True
    hull = ng.nodes.new('GeometryNodeConvexHull')
    lnk  = ng.links.new
    lnk(gin.outputs['Geometry'], ext.inputs['Mesh'])
    lnk(gin.outputs['Radius'],   ext.inputs['Offset Scale'])
    lnk(ext.outputs['Mesh'],     hull.inputs['Geometry'])
    lnk(hull.outputs['Convex Hull'], gout.inputs['Geometry'])
    return ng
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
    

def RigidBodyXF(cb: bhkWorldObject):
    """
    Return a matrix representing the transform applied by a collision body.
    bhkRigidBody objects don't apply a transform; bhkRigidBodyT and bhkSimpleShapePhantom
    do. Matrix is in nif units, not Havoc units.

    Returns an identity transform if the collision body doesn't apply one.
    """
    p = cb.properties
    if p.bufType == PynBufferTypes.bhkRigidBodyTBufType:
        # bhkRigidBodyT blocks store rotation as a quaternion with the angle in the 4th
        # position, in radians 
        q = Quaternion((p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2],))
        t = Vector(p.translation[0:3]) * HAVOC_SCALE_FACTOR
        bodyxf = MatrixLocRotScale(t, q, Vector((1,1,1)))

    # bhkSimpleShapePhantom has a transform built in.
    # TODO: Should this be translated to nif units?
    elif p.bufType == PynBufferTypes.bhkSimpleShapePhantomBufType:
        bodyxf = Matrix([r for r in p.transform])

    else:
        bodyxf = Matrix.Identity(4)

    return bodyxf


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
    ObjectSelect([obj])
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


class CollisionHandler():
    def __init__(self, parent_handler):
        self.root_object = parent_handler.root_object
        self.blender_name = None
        self.collection = None
        self.export_xf = None
        self.game = None
        self.import_xf = None
        self.nif = parent_handler.nif
        self.objs_written = None
        self.logger = logging.getLogger("pynifly")
        # Shared cache so the same bhkPhysicsSystem block is only imported once
        if not hasattr(parent_handler, '_physics_system_cache'):
            parent_handler._physics_system_cache = {}
        self._physics_system_cache = parent_handler._physics_system_cache
    

    def warn(self, msg):
        self.logger.warning(msg)


    # ------- COLLISION IMPORT --------

    @property
    def import_scale(self):
        """Return the scale factor being used on the import.
        Only looks at the x-value because they're all the same.
        Useful for havoc values that are stored as properties. 
        """
        return self.import_xf.to_scale()[0]


    def import_bhkConvexTransformShape(self, cs:bhkShape, parentxf:Matrix):
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


    def import_bhkListShape(self, cs:bhkShape, parentxf:Matrix):
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
        # cshape['bhkMaterial'] = SkyrimHavokMaterial.get_name(cs.properties.bhkMaterial)
        cshape.matrix_world = parentxf.copy()

        # children = []
        for child in cs.children:
            childobj = self.import_collision_shape(child, parentxf)
            childobj.parent = cshape

        return cshape


    def import_bhkBoxShape(self, cs:bhkShape, parentxf):
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

        # Set the transform first, then parent the object so any transforms on the root
        # don't affect the collision transforms.
        # TODO: Get this right.
        obj.matrix_world = parentxf.copy()
        # obj.parent = self.root_object

        obj['bhkMaterial'] = SkyrimHavokMaterial.get_name(prop.bhkMaterial)
        obj['bhkRadius'] = prop.bhkRadius * self.import_scale

        self.collection.objects.link(obj)

        return obj
        
    def import_bhkCapsuleShape(self, cs:bhkShape, parentxf:Matrix):
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
        

    def import_bhkSphereShape(self, cs:bhkShape, parentxf:Matrix):
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
        

    def show_collision_normals(self, cs:bhkShape, cso):
        sf = -HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
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
                                      collisionnode:bhkShape,
                                      parentxf:Matrix):
        """
        Import a bhkConvexVerticesShape object.
            collisionnode = the bhkConvexVerticesShape node in the nif
            targobj = parent collision body object in Blender 
        """
        prop = collisionnode.properties

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
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

        q = parentxf.to_quaternion()
        q.invert()
        obj.rotation_quaternion = q
        return obj


    def _create_physics_shape_object(self, s, name, sf, parentxf, body_offset,
                                      single_body, all_standalone):
        """Create a Blender object for one leaf collision shape from a Havok packfile.

        For mesh-based shapes (polytope, compressed_mesh) the shape's vertices are
        transformed and scaled into Blender space.  For primitive shapes (sphere,
        and future capsule/box) a Blender primitive mesh is created instead.

        Returns the created Blender object (not yet linked to rigid body system).
        """
        if s.shape_type == 'sphere':
            radius_bl = s.sphere_radius * sf
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=16, ring_count=8, radius=radius_bl,
                calc_uvs=False, location=(0, 0, 0))
            obj = bpy.context.object
            obj.name = name
            obj.data.name = name
            obj.matrix_world = parentxf.copy()
            for p in obj.data.polygons:
                p.use_smooth = True
            obj.data.update()
            return obj

        # Mesh-based shapes: apply body transform then scale to Blender units.
        # Single-body systems: shape vertices are in world space; the body
        # transform is just the centre-of-mass and must NOT be applied.
        # Multi-body systems: vertices are body-local; the body transform
        # places each shape in world space.
        # Compound children always need their instance transform applied
        # (single_body is True for compounds since they're one top-level shape).
        apply_xform = (s.transform is not None
                       and s.shape_type != 'compressed_mesh'
                       and not (single_body and all_standalone))

        if apply_xform:
            p, r = s.transform.position, s.transform.rotation
            tp = (p[0]+body_offset[0], p[1]+body_offset[1], p[2]+body_offset[2])
            xverts = [
                (r[0][0]*v[0]+r[0][1]*v[1]+r[0][2]*v[2]+tp[0],
                 r[1][0]*v[0]+r[1][1]*v[1]+r[1][2]*v[2]+tp[1],
                 r[2][0]*v[0]+r[2][1]*v[1]+r[2][2]*v[2]+tp[2])
                for v in s.verts
            ]
        else:
            xverts = list(s.verts)

        scaled_verts = [[x*sf, y*sf, z*sf] for x, y, z in xverts]

        m = bpy.data.meshes.new(name)
        m.from_pydata(scaled_verts, [], list(s.faces))
        m.update()

        obj = bpy.data.objects.new(name, m)
        obj.matrix_world = parentxf.copy()
        self.collection.objects.link(obj)
        return obj


    def import_bhkNPCollisionObject(self, c, parentxf: Matrix):
        """Import FO4 native-physics collision from bhkPhysicsSystem binary data.

        Creates one Blender mesh object per leaf shape decoded from the packfile.
        Compound shapes are recursed so their children become individual objects.

        Single-body systems: the shape object itself (or a container Empty for
        multi-leaf single bodies) is returned as the constraint target.

        Multi-body systems (N compound bodies, N NIF nodes referencing the same
        physics-system block): each call picks the next compound body in order,
        creating a separate container per NIF node.  This ensures each node's
        COPY_TRANSFORMS constraint targets only its own collision shapes.

        For polytope shapes with a non-zero convex radius, a Geometry Nodes Push
        modifier and a Bevel modifier are added to visualise the Minkowski expansion.
        The base mesh vertices (before modifiers) are the raw inner hull; the
        convex radius is stored in pynCollisionRadius for use at export time.

        Returns None silently if the DLL functions are not yet available.
        """
        from ..pyn.bhk_autounpack import parse_bytes

        ps = c.physics_system
        if ps is None:
            return None

        # Multi-body support: each NIF-node reference picks the next body in order.
        # Cache stores (parsed_shapes, next_body_index) so parsing happens only once.
        if ps.id in self._physics_system_cache:
            shapes, body_idx = self._physics_system_cache[ps.id]
            self._physics_system_cache[ps.id] = (shapes, body_idx + 1)
        else:
            raw = ps.data
            if not raw:
                return None  # DLL not updated yet or block has no data; skip silently
            try:
                shapes = parse_bytes(raw)
            except RuntimeError as e:
                self.warn(f"bhkPhysicsSystem decode failed: {e}")
                return None
            body_idx = 0
            self._physics_system_cache[ps.id] = (shapes, 1)

        # Collect leaf shapes.
        # body.transform holds the body's world position; _collect accumulates it as
        # the initial offset so all vertices end up in Havok world space before scaling.
        # Nested sub-compounds (if any) accumulate their own offsets on top.
        leaf_shapes = []  # list of (CollisionShape, sub_compound_offset_havok)
        def _collect(s, offset=(0.0, 0.0, 0.0)):
            if s.shape_type == 'compound':
                body_pos = s.transform.position if s.transform else (0.0, 0.0, 0.0)
                new_offset = (offset[0]+body_pos[0],
                              offset[1]+body_pos[1],
                              offset[2]+body_pos[2])
                for child in s.children:
                    _collect(child, new_offset)
            else:
                leaf_shapes.append((s, offset))

        # Three packfile layouts share this importer:
        #   Flat/shared (e.g. CapsuleExtStairs, pack_multi_polytope output): all
        #     top-level shapes are standalone (no compound wrapper).  Every shape
        #     belongs to the single first-referencing NIF node; subsequent NIF-node
        #     references to the same physics system are silently skipped.
        #   Compound-multi-body (e.g. BOSRadarDish): top-level shapes are compound
        #     bodies; each NIF-node reference gets the next compound body in order.
        #
        # Single-body systems store shape vertices in world space; the body
        # transform is just the centre-of-mass and must NOT be applied.
        # Multi-body systems store body-local vertices; each body's transform
        # places its shape in world space.
        single_body = len(shapes) == 1
        all_standalone = all(s.shape_type != 'compound' for s in shapes)
        if all_standalone:
            if body_idx > 0:
                # Shared physics system — already imported by the first reference.
                return None
            for s in shapes:
                _collect(s)
            self._physics_system_cache[ps.id] = (shapes, len(shapes))
        else:
            # Compound format: sequential one-body-per-call.
            if body_idx >= len(shapes):
                self.warn("bhkPhysicsSystem has more NIF-node references than bodies; skipping")
                return None
            _collect(shapes[body_idx])

        if not leaf_shapes:
            return None

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        multi = len(leaf_shapes) > 1

        # For multi-shape systems use an Empty as the constraint-target container so
        # all shape objects are siblings in the outliner rather than parent→child.
        if multi:
            container = bpy.data.objects.new("bhkPhysicsSystem", None)
            container.matrix_world = parentxf.copy()
            container.empty_display_type = 'PLAIN_AXES'
            container.empty_display_size = 0.1
            container['pynRigidBody'] = 'bhkPhysicsSystem'
            self.collection.objects.link(container)
            anchor = container
        else:
            container = None
            anchor = None  # will be set to the single shape object

        for i, (s, body_offset) in enumerate(leaf_shapes):
            # Name: single-shape systems keep the legacy name; multi-shape use
            # a type suffix so the shape types are distinguishable.
            _SUFFIXES = {'compressed_mesh': '_cm', 'sphere': '_sphere',
                         'polytope': '_poly'}
            if len(leaf_shapes) == 1:
                name = "bhkPhysicsSystem"
            else:
                name = "bhkPhysicsSystem" + _SUFFIXES.get(s.shape_type, f'_{s.shape_type}')

            obj = self._create_physics_shape_object(
                s, name, sf, parentxf, body_offset,
                single_body=single_body, all_standalone=all_standalone)

            ObjectSelect([obj])
            bpy.ops.rigidbody.object_add(type='PASSIVE')
            rb_shape = {'sphere': 'SPHERE'}.get(s.shape_type, 'MESH')
            obj.rigid_body.collision_shape = rb_shape
            obj.color = COLLISION_COLOR
            obj.display_type = 'WIRE'
            obj['pynRigidBody'] = 'bhkPhysicsSystem'
            obj['pynCollisionShapeType'] = s.shape_type

            # Store physics properties (mass, inertia, material) from packfile.
            if s.physics is not None:
                obj['pynPhysDynamic'] = s.physics.is_dynamic
                if s.physics.is_dynamic:
                    obj['pynPhysMass'] = s.physics.mass
                    obj['pynPhysInertia'] = list(s.physics.inertia)
                obj['pynPhysMaterial'] = s.physics.body_props_raw.hex()

            # For polytopes, store the convex radius and add visualisation modifiers.
            if s.shape_type == 'polytope' and s.convex_radius > 0.0:
                radius_bl = s.convex_radius * sf
                obj['pynCollisionRadius'] = radius_bl
                # Push + Convex Hull: expands faces outward by radius_bl, then
                # wraps with a convex hull to place corner vertices at the exact
                # intersection of the offset face planes (Minkowski expansion).
                ng = _get_or_create_push_nodegroup()
                push = obj.modifiers.new('bhkPush', 'NODES')
                push.node_group = ng
                for item in ng.interface.items_tree:
                    if getattr(item, 'in_out', None) == 'INPUT' and item.name == 'Radius':
                        push[item.identifier] = radius_bl
                        break
                # Bevel: rounds the hull edges to approximate the Minkowski sphere.
                bev = obj.modifiers.new('bhkBevel', 'BEVEL')
                bev.width = radius_bl
                bev.limit_method = 'NONE'
                bev.segments = 2

            if container is not None:
                obj.parent = container
                obj.matrix_local = Matrix.Identity(4)
            else:
                anchor = obj  # single shape: the shape itself is the anchor

        return anchor


    collision_shape_importers = {
        "bhkBoxShape": import_bhkBoxShape,
        "bhkConvexVerticesShape": import_bhkConvexVerticesShape,
        "bhkListShape": import_bhkListShape,
        "bhkConvexTransformShape": import_bhkConvexTransformShape,
        "bhkCapsuleShape": import_bhkCapsuleShape,
        "bhkSphereShape": import_bhkSphereShape,
    }

    def import_collision_shape(self, cs:bhkShape, parentxf):
        sh = None
        if cs.blockname in self.collision_shape_importers:
            sh = self.collision_shape_importers[cs.blockname](self, cs, parentxf)
        else:
            self.warn(f"Found unimplemented collision shape: {cs.blockname}")
        
        if sh:
            ObjectSelect([sh])
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
        ObjectSelect([sh])
        bpy.ops.object.transform_apply()
        sh.matrix_world = targetxf.copy()

        # We don't have a separate Blender object for rigid body properties, so store them
        # on the shape.
        p = cb.properties
        p.extract(sh, ignore=COLLISION_BODY_IGNORE)
        if not cb.blockname.startswith('bhkRigidBody'):
            # Shape's parent wasn't a rigidbody. Remember what it was for export.
            sh['pynRigidBody'] = cb.blockname

        try:
            sh.rigid_body.mass = p.mass # / HAVOC_SCALE_FACTOR
            sh.rigid_body.friction = p.friction # / HAVOC_SCALE_FACTOR
            sh.rigid_body.use_margin = True
            sh.rigid_body.linear_damping = p.linearDamping # / HAVOC_SCALE_FACTOR
            sh.rigid_body.angular_damping = p.angularDamping # / HAVOC_SCALE_FACTOR
            sh.rigid_body.collision_margin = cb.shape.properties.bhkRadius / HAVOC_SCALE_FACTOR
        except:
            pass
            
        if sh.name.split('.')[0] == 'bhkListShape':
            # No collisionFilter_layer on bhkListShape
            rbtype = 'ACTIVE'
            # rbtype = 'ACTIVE' if p.collisionFilter_layer in collision_active_layers else 'PASSIVE'
            sh.rigid_body.collision_shape = 'COMPOUND'
            for ch in sh.children:
                ObjectSelect([ch])
                bpy.ops.rigidbody.object_add(type=rbtype)
                
        return sh


    @classmethod
    def import_collision_obj(
        cls, parent_handler, c:NiCollisionObject, parentObj=None, bone:NiNode=None):
        """
        Import collision object. 
        
        * parentObj is target of collision if it's a NiNode. If target is a bone,
        parentObj is armature and "bone" is the NiNode for the bone. 
        * Returns new collision object.
        """
        importer = CollisionHandler(parent_handler)
        importer.import_xf = parent_handler.import_xf
        importer.blender_name = parent_handler.blender_name
        importer.collection = parent_handler.collection

        bpy.ops.object.mode_set(mode='OBJECT')
        if c.blockname not in ["bhkCollisionObject",
                           "bhkSPCollisionObject",
                           "bhkNPCollisionObject",
                           "bhkPCollisionObject",
                           "bhkBlendCollisionObject"]:
            importer.warn(f"Found an unknown type of collision: {c.blockname}")
            return None

        if bone:
            xf = importer.import_xf @ transform_to_matrix(bone.global_transform)
        else:
            xf = parentObj.matrix_world

        if c.blockname == "bhkNPCollisionObject":
            # Body transforms from the Havok packfile are applied during flatten;
            # only the global import transform applies here.
            np_xf = importer.import_xf
            sh = importer.import_bhkNPCollisionObject(c, np_xf)
            if not sh: return None  # DLL not ready or no data; skip silently
        else:
            if not c.body: return None
            sh = importer.import_collision_body(c.body, xf)
            if not sh:
                importer.warn(f"{parentObj.name} has unsupported collision shape")
                return
        
        sh['pynCollisionFlags'] = bhkCOFlags(c.flags).fullname

        if parentObj:
            if parentObj.type == 'ARMATURE' and bone:
                bn = importer.blender_name(bone.name)
                if bn in parentObj.data.bones:
                    pb = parentObj.pose.bones[bn]
                    constr = pb.constraints.new(type='COPY_TRANSFORMS')
                    constr.target = sh
                else:
                    importer.warn(f"Bone is missing: {bone.name}")
            else:
                constr = parentObj.constraints.new('COPY_TRANSFORMS')
                constr.target = sh
                # For bhkNPCollisionObject the physics mesh sits at world origin
                # and is independent of the target node.  Keep the constraint so
                # the exporter can discover the collision, but zero its influence
                # so it does not pull parentObj to origin.
                if c.blockname == "bhkNPCollisionObject":
                    constr.influence = 0.0
            constr.name = 'bhkCollisionConstraint'

        return sh
    

    ######## EXPORT ########

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

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.game] 

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


    def export_bhkBoxShape(self, box, xform) -> bhkShape:
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
            sf = (HAVOC_SCALE_FACTOR 
                  * game_collision_sf[self.game] 
                  * (1/self.export_xf.to_scale()[0])
                #   * box.parent.matrix_world.to_scale()[0] # to put collision shapes under the root
                  )
            ctr, d, r = find_box_info(box)
            if len(d) == 3:
                bhkDim = (d / sf) / 2
                for i in range(0, 3):
                    p.bhkDimensions[i] = bhkDim[i]

                cshape = self.nif.add_shape(p)
        except Exception as e:
            self.warn(f"Unexpected error: {e}")

        if not cshape:
            self.warn(f'Cannot create collision shape from {box.name}')
            
        return cshape, ctr, r
        

    def export_bhkConvexVerticesShape(self, s, xform):
        """
        Export a convex vertices shape that wraps around whatever the import shape
        is.
        """
        p = bhkConvexVerticesShapeProps(s, game=self.game)
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
            props.bhkRadius = s.rigid_body.collision_margin * HAVOC_SCALE_FACTOR

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


    def export_collision_body(self, targobj, collpair:ReprObject):
        """ 
        Export the collision body for the given collision.

        * targobj = Blender object that has the collision.
        * coll = ReprObject object representing the collision
        * colnode = Nif node representing the collision
        """
        coll = collpair.blender_obj

        # Blender's collision object has the same transform as the target (because that's
        # how we model collisions). 
        if not coll.rigid_body: return
        if 'pynRigidBody' not in coll: 
            bodytype = 'bhkRigidBody'
        else:
            bodytype = coll['pynRigidBody']

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

        # If the target is a pose bone, use its world location (glassbowskinned). 
        # If it's a node (dwemer chest), use its local location.
        # TODO: Clean this up. We check for a bone above, probably could use that.
        if have_bone:
            rv = ctr - targlocw 
        else:
            rv = ctr - targloc

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

        # colnode = self.objs_written[coll.name]
        body_node = collpair.nifnode.add_body(props)

        return body_node


    def export_collision_object(self, targobj, coll):
        """
        Export the given collision object. 
        targobj = Blender object with the collision.
        coll = Blender object representing the collision.
        """
        if self.objs_written.find_blend(coll): return

        flags = None
        if 'pynCollisionFlags' in coll:
            flags = bhkCOFlags.parse(coll['pynCollisionFlags']).value

        targpair = self.objs_written.find_blend(targobj)
        if targpair:
            targnode = targpair.nifnode
        else:
            targnode = self.nif.nodes[targobj.name]

        if coll.get('pynRigidBody') == 'bhkPhysicsSystem':
            from ..pyn.bhk_autounpack import CollisionShape, PhysicsProps
            sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.game]

            _SHAPE_TYPES = ('compressed_mesh', 'polytope', 'sphere')
            # Collect the main collision object and any children that carry
            # pynCollisionShapeType (set during import for multi-shape systems).
            shape_objs = []
            if coll.get('pynCollisionShapeType') in _SHAPE_TYPES:
                shape_objs.append(coll)
            for ch in coll.children:
                if ch.get('pynCollisionShapeType') in _SHAPE_TYPES:
                    shape_objs.append(ch)

            coll_node = targnode.add_collision(
                None, flags=flags or 0,
                collision_type=PynBufferTypes.bhkNPCollisionObjectBufType)

            if shape_objs:
                # Build physics properties from the first shape object's
                # custom properties (all shapes in one system share the same body).
                ref = shape_objs[0]
                is_dyn = ref.get('pynPhysDynamic', False)
                if is_dyn:
                    physics = PhysicsProps(
                        is_dynamic=True,
                        mass=ref.get('pynPhysMass', 0.0),
                        inertia=tuple(ref.get('pynPhysInertia', [0.0, 0.0, 0.0])),
                        body_props_raw=bytes.fromhex(ref.get('pynPhysMaterial', '00ff003f003fcd3e01024c3deeff7f7f')),
                    )
                else:
                    mat_hex = ref.get('pynPhysMaterial', '00ff003f003fcd3e01024c3deeff7f7f')
                    physics = PhysicsProps(
                        is_dynamic=False,
                        body_props_raw=bytes.fromhex(mat_hex),
                    )

                # Build CollisionShape objects from Blender mesh data and pack
                # using the appropriate packer (polytope, compressed_mesh, mixed, or sphere).
                shapes = []
                for obj in shape_objs:
                    shape_type = obj['pynCollisionShapeType']
                    if shape_type == 'sphere':
                        # Derive Havok radius from the Blender mesh dimensions.
                        sphere_r = max(obj.dimensions) / 2.0 / sf
                        shapes.append(CollisionShape(
                            shape_type='sphere',
                            name=obj.name,
                            transform=None,
                            verts=[],
                            faces=[],
                            convex_radius=0.0,
                            children=[],
                            sphere_radius=sphere_r,
                            physics=physics,
                        ))
                    else:
                        world_mat = self.export_xf @ obj.matrix_world
                        verts = [tuple(world_mat @ v.co / sf) for v in obj.data.vertices]
                        faces = [list(p.vertices) for p in obj.data.polygons]
                        # convex_radius is stored in Blender units; convert back to Havok.
                        radius = obj.get('pynCollisionRadius', 0.0) / sf
                        shapes.append(CollisionShape(
                            shape_type=shape_type,
                            name=obj.name,
                            transform=None,
                            verts=verts,
                            faces=faces,
                            convex_radius=radius,
                            children=[],
                            physics=physics,
                        ))
                # Compute density for dynamic bodies from geometry.
                if is_dyn and physics.mass > 0:
                    from ..pyn.bhk_autopack import compute_density
                    # Use the first shape's geometry to compute density.
                    s0 = shapes[0] if shapes else None
                    if s0 is not None:
                        physics.density = compute_density(
                            physics.mass, s0.verts, s0.faces,
                            s0.convex_radius, s0.shape_type,
                            s0.sphere_radius)

                # pack_shapes requires compressed_mesh before polytope.
                shapes.sort(key=lambda s: 0 if s.shape_type == 'compressed_mesh' else 1)
                bhkPhysicsSystem.New(self.nif, shapes=shapes, parent=coll_node)
            else:
                # Legacy path: no pynCollisionShapeType tag — treat the whole
                # mesh as a single convex polytope (pre-existing behaviour).
                world_mat = self.export_xf @ coll.matrix_world
                verts = [(*(world_mat @ v.co / sf),) for v in coll.data.vertices]
                faces = [list(p.vertices) for p in coll.data.polygons]
                bhkPhysicsSystem.New(self.nif, verts=verts, faces=faces, parent=coll_node)

            self.objs_written.add(ReprObject(coll, targnode))
            return

        colnode = targnode.add_collision(
            None, flags=flags,
            collision_type=PynBufferTypes.bhkSPCollisionObjectBufType
                if coll.get('pynRigidBody') == 'bhkSimpleShapePhantom'
                else None)
        collpair = ReprObject(coll, colnode)
        self.objs_written.add(collpair)

        body = self.export_collision_body(targobj, collpair)


    @classmethod
    def export_collisions(cls, parent_handler, obj):
        """
        Export the object's collision. 
                
        Collision shapes are tied to their target with a copy-transforms constraint.
        """
        exporter = CollisionHandler(parent_handler)
        exporter.objs_written = parent_handler.objs_written
        exporter.game = parent_handler.game
        exporter.export_xf = parent_handler.export_xf

        targobj = obj
        if obj.type == 'ARMATURE':
            # For an armature, find collisions on the bones.
            # collisions = []
            for pb in obj.pose.bones:
                for c in pb.constraints:
                    if c.type == 'COPY_TRANSFORMS':
                        exporter.export_collision_object(pb, c.target)
        else:
            # For a regular object, find collisions on the object itself.
            for c in obj.constraints:
                if c.type == 'COPY_TRANSFORMS' and c.target:
                    exporter.export_collision_object(targobj, c.target)

