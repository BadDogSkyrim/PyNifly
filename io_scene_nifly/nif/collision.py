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

def _add_collision_radius_modifiers(obj, radius_bl: float):
    """Add push + bevel modifiers to visualise convex radius expansion."""
    ng = _get_or_create_push_nodegroup()
    push = obj.modifiers.new('bhkPush', 'NODES')
    push.node_group = ng
    for item in ng.interface.items_tree:
        if getattr(item, 'in_out', None) == 'INPUT' and item.name == 'Radius':
            push[item.identifier] = radius_bl
            break
    bev = obj.modifiers.new('bhkBevel', 'BEVEL')
    bev.width = radius_bl
    bev.limit_method = 'NONE'
    bev.segments = 2

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

        # Visualise the convex radius with push + bevel modifiers.
        radius_bl = prop.bhkRadius * self.import_scale
        if radius_bl > 0:
            _add_collision_radius_modifiers(obj, radius_bl)

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

        # Visualise the convex radius with push + bevel modifiers.
        radius_bl = prop.bhkRadius * self.import_scale
        if radius_bl > 0:
            _add_collision_radius_modifiers(obj, radius_bl)

        q = parentxf.to_quaternion()
        q.invert()
        obj.rotation_quaternion = q
        return obj


    def _create_physics_shape_object(self, s, name, sf, parentxf,
                                     apply_transform=True):
        """Create a Blender object for one leaf collision shape from a Havok packfile.

        For mesh-based shapes (polytope, compressed_mesh) the shape's vertices are
        transformed and scaled into Blender space.  For primitive shapes (sphere,
        and future capsule/box) a Blender primitive mesh is created instead.

        When apply_transform is True the shape's stored transform (body or instance)
        is applied to the vertices before scaling.  Compressed-mesh shapes always
        skip the transform because their AABB-dequantized verts are world-space.

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

        if (apply_transform
                and s.transform is not None
                and s.shape_type != 'compressed_mesh'):
            p, r = s.transform.position, s.transform.rotation
            xverts = [
                (r[0][0]*v[0]+r[0][1]*v[1]+r[0][2]*v[2]+p[0],
                 r[1][0]*v[0]+r[1][1]*v[1]+r[1][2]*v[2]+p[1],
                 r[2][0]*v[0]+r[2][1]*v[1]+r[2][2]*v[2]+p[2])
                for v in s.verts
            ]
        else:
            xverts = s.verts

        scaled_verts = [[x*sf, y*sf, z*sf] for x, y, z in xverts]

        # Havok packfile quad data can contain duplicate faces;
        # deduplicate to avoid Blender mesh validation errors.
        seen = set()
        faces = []
        for f in s.faces:
            key = tuple(sorted(f))
            if key not in seen:
                seen.add(key)
                faces.append(f)
        m = bpy.data.meshes.new(name)
        m.from_pydata(scaled_verts, [], faces)
        m.update()

        obj = bpy.data.objects.new(name, m)
        obj.matrix_world = parentxf.copy()
        self.collection.objects.link(obj)
        return obj


    def import_bhkNPCollisionObject(self, c, import_xf: Matrix,
                                    node_xf: Matrix):
        """Import FO4 native-physics collision for one NIF node's body.

        Each bhkNPCollisionObject has a bodyID selecting which body in the shared
        bhkPhysicsSystem belongs to this NIF node.  Only that body's shape(s)
        are imported here; other nodes will import their own bodies separately.

        Body transform semantics:
        - Non-identity rotation: the body transform matches the NIF node's world
          transform.  It is applied to the (body-local) vertices so they end up
          in world space; the Blender object uses import_xf (Identity).
        - Identity rotation: the body position is centre-of-mass metadata, NOT
          the node position.  Vertices are already in node-local space and the
          Blender object uses node_xf to position them correctly.
        - Compressed-mesh shapes are always world-space (AABB-dequantized) and
          use import_xf regardless of body rotation.

        Compound shapes are flattened: each leaf becomes its own Blender object.
        Instance transforms within compounds are always applied.

        Returns the collision anchor object, or None if data is unavailable.
        """
        from ..pyn.bhk_autounpack import parse_bytes

        ps = c.physics_system
        if ps is None:
            return None

        # Cache parsed shapes so the packfile is only decoded once.
        if ps.id not in self._physics_system_cache:
            raw = ps.data
            if not raw:
                return None
            try:
                parsed = parse_bytes(raw)
            except RuntimeError as e:
                self.warn(f"bhkPhysicsSystem decode failed: {e}")
                return None
            self._physics_system_cache[ps.id] = parsed

        all_shapes = self._physics_system_cache[ps.id]
        body_id = c.body_id
        single_body = (body_id is not None and body_id < len(all_shapes))

        if not single_body:
            # bodyID is NODEID_NONE or out of range — bulk mode.
            # Import all bodies on the first call; return cached anchor
            # for subsequent calls referencing the same physics system.
            bulk_key = (ps.id, 'bulk')
            if bulk_key in self._physics_system_cache:
                return self._physics_system_cache[bulk_key]
            bodies_to_import = list(all_shapes)
        else:
            bodies_to_import = [all_shapes[body_id]]

        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]

        # Flatten all bodies into leaf shapes with their transform context.
        leaf_entries = []  # list of (leaf_shape, parentxf, apply_transform)
        for body_shape in bodies_to_import:
            is_compound = body_shape.shape_type == 'compound'
            if single_body:
                # Per-body mode.  Use node_xf to position the collision
                # at the NIF node's world location.  Standalone shape
                # verts don't get the body rotation applied (it's Havok
                # simulation metadata).  Compound children carry instance
                # transforms that DO need applying.
                body_xf = node_xf
                apply_body = is_compound
            else:
                # Bulk mode: always apply body transform (we don't have each
                # node's world matrix, so use import_xf for all shapes).
                body_xf = import_xf
                apply_body = True

            leaves = []
            def _collect(s):
                if s.shape_type == 'compound':
                    for child in s.children:
                        _collect(child)
                else:
                    leaves.append(s)
            _collect(body_shape)

            for s in leaves:
                leaf_entries.append((s, body_xf, apply_body))

        if not leaf_entries:
            return None

        multi = len(leaf_entries) > 1

        if multi:
            container = bpy.data.objects.new("bhkPhysicsSystem", None)
            container.matrix_world = leaf_entries[0][1].copy()
            container.empty_display_type = 'PLAIN_AXES'
            container.empty_display_size = 0.1
            container['pynRigidBody'] = 'bhkPhysicsSystem'
            self.collection.objects.link(container)
            anchor = container
        else:
            container = None
            anchor = None

        for i, (s, shape_xf, apply_xf) in enumerate(leaf_entries):
            _SUFFIXES = {'compressed_mesh': '_cm', 'sphere': '_sphere',
                         'polytope': '_poly'}
            if len(leaf_entries) == 1:
                name = "bhkPhysicsSystem"
            else:
                name = "bhkPhysicsSystem" + _SUFFIXES.get(s.shape_type,
                                                          f'_{s.shape_type}')

            obj = self._create_physics_shape_object(
                s, name, sf, shape_xf, apply_transform=apply_xf)

            ObjectSelect([obj])
            bpy.ops.rigidbody.object_add(type='PASSIVE')
            rb_shape = {'sphere': 'SPHERE'}.get(s.shape_type, 'MESH')
            obj.rigid_body.collision_shape = rb_shape
            obj.color = COLLISION_COLOR
            obj.display_type = 'WIRE'
            obj['pynRigidBody'] = 'bhkPhysicsSystem'
            obj['pynCollisionShapeType'] = s.shape_type

            if s.physics is not None:
                if s.physics.is_dynamic:
                    obj.rigid_body.type = 'ACTIVE'
                    obj.rigid_body.mass = s.physics.mass
                    obj['pynPhysInertia'] = list(s.physics.inertia)
                obj.rigid_body.friction = s.physics.friction
                obj.rigid_body.restitution = s.physics.restitution
                obj.rigid_body.linear_damping = s.physics.linear_damping
                obj.rigid_body.angular_damping = s.physics.angular_damping
                obj['pynPhysMaterial'] = s.physics.body_props_raw.hex()
                obj['pynPhysGravityFactor'] = s.physics.gravity_factor
                obj['pynPhysMaxLinVel'] = s.physics.max_linear_velocity
                obj['pynPhysMaxAngVel'] = s.physics.max_angular_velocity

            if s.shape_type == 'polytope' and s.convex_radius > 0.0:
                radius_bl = s.convex_radius * sf
                obj['pynCollisionRadius'] = radius_bl
                _add_collision_radius_modifiers(obj, radius_bl)

            if container is not None:
                obj.parent = container
                obj.matrix_local = Matrix.Identity(4)
            else:
                anchor = obj

        if not single_body:
            self._physics_system_cache[bulk_key] = anchor

        return anchor


    def import_bhkMoppBvTreeShape(self, cs:bhkShape, parentxf:Matrix):
        """Import a MOPP BVH tree shape by delegating to its child shape."""
        child = cs.child
        if child is None:
            self.warn("bhkMoppBvTreeShape has no child shape")
            return None
        if child.blockname in self.collision_shape_importers:
            return self.collision_shape_importers[child.blockname](self, child, parentxf)
        self.warn(f"bhkMoppBvTreeShape: unimplemented child shape: {child.blockname}")
        return None

    def import_bhkPackedNiTriStripsShape(self, cs:bhkShape, parentxf:Matrix):
        """Import a packed triangle strips collision shape as a mesh."""
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        verts = [(v[0]*sf, v[1]*sf, v[2]*sf) for v in cs.vertices]
        tris = cs.triangles
        if not verts or not tris:
            self.warn("bhkPackedNiTriStripsShape has no geometry")
            return None
        m = bpy.data.meshes.new(cs.blockname)
        m.from_pydata(verts, [], tris)
        obj = bpy.data.objects.new(cs.blockname, m)
        obj.matrix_world = parentxf.copy()
        self.collection.objects.link(obj)
        obj['bhkRadius'] = cs.properties.radius * self.import_scale
        return obj

    def import_bhkCompressedMeshShape(self, cs:bhkShape, parentxf:Matrix):
        """Import a compressed mesh collision shape (Skyrim SE) as a mesh."""
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        verts = [(v[0]*sf, v[1]*sf, v[2]*sf) for v in cs.vertices]
        tris = cs.triangles
        if not verts or not tris:
            self.warn("bhkCompressedMeshShape has no geometry")
            return None
        m = bpy.data.meshes.new(cs.blockname)
        m.from_pydata(verts, [], tris)
        obj = bpy.data.objects.new(cs.blockname, m)
        obj.matrix_world = parentxf.copy()
        self.collection.objects.link(obj)
        obj['bhkRadius'] = cs.properties.radius * self.import_scale

        # Create vertex groups for per-triangle Havok materials
        mat_ids = cs.material_ids
        if mat_ids and len(mat_ids) == len(tris):
            unique_mats = set(mat_ids)
            if len(unique_mats) > 1:
                for mat_val in unique_mats:
                    name = "SKY_HAV_MAT_" + SkyrimHavokMaterial.get_name(mat_val)
                    vg = obj.vertex_groups.new(name=name)
                    # Assign faces with this material — add all verts of matching faces
                    face_verts = set()
                    for fi, mid in enumerate(mat_ids):
                        if mid == mat_val:
                            for vi in tris[fi]:
                                face_verts.add(vi)
                    if face_verts:
                        vg.add(list(face_verts), 1.0, 'REPLACE')

        return obj

    collision_shape_importers = {
        "bhkBoxShape": import_bhkBoxShape,
        "bhkConvexVerticesShape": import_bhkConvexVerticesShape,
        "bhkListShape": import_bhkListShape,
        "bhkConvexTransformShape": import_bhkConvexTransformShape,
        "bhkCapsuleShape": import_bhkCapsuleShape,
        "bhkSphereShape": import_bhkSphereShape,
        "bhkMoppBvTreeShape": import_bhkMoppBvTreeShape,
        "bhkPackedNiTriStripsShape": import_bhkPackedNiTriStripsShape,
        "bhkCompressedMeshShape": import_bhkCompressedMeshShape,
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
            sh = importer.import_bhkNPCollisionObject(
                c, importer.import_xf, xf)
            if not sh: return None  # DLL not ready or no data; skip silently
        else:
            if not c.body: return None
            sh = importer.import_collision_body(c.body, xf)
            if not sh:
                importer.warn(f"{parentObj.name} has unsupported collision shape")
                return
        
        sh['pynCollisionFlags'] = bhkCOFlags(c.flags).fullname
        sh['pynCollisionBlockname'] = c.blockname

        # Track collision objects so they can be reparented when the root
        # is connected via weapon-part connect points.
        if not hasattr(parent_handler, '_collision_objects'):
            parent_handler._collision_objects = []
        parent_handler._collision_objects.append(sh)

        if parentObj:
            if parentObj.type == 'ARMATURE' and bone:
                bn = importer.blender_name(bone.name)
                if bn in parentObj.data.bones:
                    pb = parentObj.pose.bones[bn]
                    constr = pb.constraints.new(type='COPY_TRANSFORMS')
                    constr.target = sh
                    constr.name = 'bhkCollisionConstraint'
                    # Blend collisions are additive and don't reposition
                    # bones.  Regular collisions start at 0 and get
                    # enabled to 1 after bone poses are finalized.
                    constr.influence = 0.0
                else:
                    importer.warn(f"Bone is missing: {bone.name}")
            else:
                if importer.nif.connect_points_child:
                    # NIF has child connect points — it's a weapon part
                    # that will join a constrained system.  Use a custom
                    # property instead of a constraint to avoid dep cycles
                    # through the rigid body sim.
                    parentObj['pynCollisionTarget'] = sh.name
                else:
                    constr = parentObj.constraints.new('COPY_TRANSFORMS')
                    constr.target = sh
                    # Multi-shape physics containers are too complex for
                    # a single constraint to drive the mesh.
                    if sh.type == 'EMPTY':
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


    def export_bhkMoppBvTreeShape(self, s, xform, child_type="compressed"):
        """Export a MOPP collision from a Blender mesh object.

        Extracts mesh geometry, converts to Havok space, creates the full
        bhkMoppBvTreeShape → child shape → data chain.

        Args:
            s: Blender mesh object.
            xform: Transform to apply (from export_collision_shape).
            child_type: 'compressed' for SE, 'packed' for LE.
        """
        from pyn.triangulate import triangulate

        # Get verts in world/export coordinates, scaled to Havok space
        myscale = (self.export_xf @ s.matrix_world).to_scale()
        sf = HAVOC_SCALE_FACTOR * game_collision_sf[self.nif.game]
        mesh = s.data
        havok_verts = []
        for v in mesh.vertices:
            hv = myscale * v.co / sf
            havok_verts.append((hv.x, hv.y, hv.z))

        # Triangulate using ear-clipping (preserves original vertex indices)
        tris = []
        for poly in mesh.polygons:
            if len(poly.vertices) == 3:
                tris.append(tuple(poly.vertices))
            else:
                vi = list(poly.vertices)
                coords = [mesh.vertices[i].co for i in vi]
                for a, b, c in triangulate(coords):
                    tris.append((vi[a], vi[b], vi[c]))

        if not tris:
            self.warn("bhkMoppBvTreeShape: no triangles to export")
            return None, None, Quaternion()

        # Determine game and radius
        game = self.nif.game
        radius = 0.005 if game != 'SKYRIM' else 0.1

        # Get default material from custom property
        default_material = s.get('bhkMaterial', 0)
        if isinstance(default_material, str):
            try:
                default_material = SkyrimHavokMaterial[default_material].value
            except KeyError:
                default_material = 0

        # Build per-face material list from SKY_HAV_MAT_ vertex groups
        face_materials = None
        mat_vgroups = {}  # vgroup_index -> havok material uint32
        for vg in s.vertex_groups:
            if vg.name.startswith("SKY_HAV_MAT_"):
                mat_name = vg.name[len("SKY_HAV_MAT_"):]
                try:
                    mat_val = SkyrimHavokMaterial[mat_name].value
                except KeyError:
                    mat_val = 0
                if mat_val:
                    mat_vgroups[vg.index] = mat_val

        if mat_vgroups:
            # For each face, find which material group its verts belong to
            face_materials = []
            for fi, tri in enumerate(tris):
                face_mat = default_material
                # Check first vertex of face — all verts should be in the same group
                vi = tri[0]
                for vgi, mat_val in mat_vgroups.items():
                    try:
                        if s.vertex_groups[vgi].weight(vi) > 0.5:
                            face_mat = mat_val
                            break
                    except RuntimeError:
                        pass  # vertex not in group
                face_materials.append(face_mat)

        # Create the shape hierarchy via high-level API
        mopp_shape = bhkMoppBvTreeShape.Create(
            self.nif, havok_verts, tris, game,
            radius=radius, material=default_material,
            face_materials=face_materials, parent=None)

        return mopp_shape, Vector(), Quaternion()

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
            elif cs.name.startswith("bhkCompressedMeshShape"):
                return self.export_bhkMoppBvTreeShape(cs, xform, child_type="compressed")
            elif cs.name.startswith("bhkPackedNiTriStripsShape"):
                return self.export_bhkMoppBvTreeShape(cs, xform, child_type="packed")
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
                # for pose bones — use the collision shape's world transform
                # in armature space. This matches what COPY_TRANSFORMS with
                # influence=1 would give, regardless of pretty rotations.
                targparent = targobj.id_data
                targxf = targparent.matrix_world.inverted() @ coll.matrix_world
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
        elif hasattr(self, 'writtenbones') and targobj.name in self.writtenbones:
            targnode = self.nif.nodes[self.writtenbones[targobj.name]]
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
                rb = ref.rigid_body
                is_dyn = (rb is not None and rb.type == 'ACTIVE')
                common_props = dict(
                    body_props_raw=bytes.fromhex(ref.get('pynPhysMaterial', '00ff003f003fcd3e01024c3deeff7f7f')),
                    friction=rb.friction if rb else 0.5,
                    restitution=rb.restitution if rb else 0.4,
                    linear_damping=rb.linear_damping if rb else 0.1,
                    angular_damping=rb.angular_damping if rb else 0.05,
                    gravity_factor=ref.get('pynPhysGravityFactor', 1.0),
                    max_linear_velocity=ref.get('pynPhysMaxLinVel', 104.4),
                    max_angular_velocity=ref.get('pynPhysMaxAngVel', 31.57),
                )
                if is_dyn:
                    physics = PhysicsProps(
                        is_dynamic=True,
                        mass=rb.mass,
                        inertia=tuple(ref.get('pynPhysInertia', [0.0, 0.0, 0.0])),
                        **common_props,
                    )
                else:
                    physics = PhysicsProps(
                        is_dynamic=False,
                        **common_props,
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
        exporter.writtenbones = parent_handler.writtenbones

        targobj = obj
        if obj.type == 'ARMATURE':
            # For an armature, find collisions on the bones.
            for pb in obj.pose.bones:
                for c in pb.constraints:
                    if c.type == 'COPY_TRANSFORMS':
                        exporter.export_collision_object(pb, c.target)
        else:
            # For a regular object, find collisions via constraint or
            # custom property (used when part of a constrained system
            # like weapon connect points, to avoid dep cycles).
            for c in obj.constraints:
                if c.type == 'COPY_TRANSFORMS' and c.target:
                    exporter.export_collision_object(targobj, c.target)
            coll_name = obj.get('pynCollisionTarget')
            if coll_name and coll_name in bpy.data.objects:
                exporter.export_collision_object(targobj, bpy.data.objects[coll_name])

