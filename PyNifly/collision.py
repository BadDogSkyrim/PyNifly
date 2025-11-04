"""Collision Import/Export for pyNifly"""

# Copyright © 2024, Bad Dog.

import bpy
import bmesh
from pynifly import *
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
import blender_defs as BD


COLLISION_BODY_IGNORE = ['rotation', 'translation', 'guard', 'unusedByte1', 
                            'unusedInts1_0', 'unusedInts1_1', 'unusedInts1_2',
                            'unusedBytes2_0', 'unusedBytes2_1', 'unusedBytes2_2',
                            'bhkRadius', 'linearDamping', 'angularDamping',
                            'friction', 'mass']
    

BOX_SHAPE_IGNORE = ['bhkDimensions']
CAPSULE_SHAPE_IGNORE = ['point1', 'point2']

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
        bodyxf = BD.MatrixLocRotScale(t, q, Vector((1,1,1)))

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
    BD.ObjectSelect([obj], active=True)
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
        self.blender_name = None
        self.collection = None
        self.export_xf = None
        self.game = None
        self.import_xf = None
        self.nif = parent_handler.nif
        self.objs_written = None
        self.logger = logging.getLogger("pynifly")
    

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
        cshape['bhkMaterial'] = SkyrimHavokMaterial.get_name(cs.properties.bhkMaterial)
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
        obj.matrix_world = parentxf.copy()
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


    def import_collision_shape(self, cs:bhkShape, parentxf):
        sh = None
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
            BD.ObjectSelect([sh], active=True)
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
        BD.ObjectSelect([sh], active=True)
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
            sh.rigid_body.linear_damping = p.linearDamping / HAVOC_SCALE_FACTOR
            sh.rigid_body.angular_damping = p.angularDamping / HAVOC_SCALE_FACTOR
            sh.rigid_body.collision_margin = cb.shape.properties.bhkRadius 
        except:
            pass
            
        if sh.name.split('.')[0] == 'bhkListShape':
            rbtype = 'ACTIVE' if p.collisionFilter_layer in collision_active_layers else 'PASSIVE'
            sh.rigid_body.collision_shape = 'COMPOUND'
            for ch in sh.children:
                BD.ObjectSelect([ch], active=True)
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
        if not c.body: return None

        if bone:
            xf = importer.import_xf @ BD.transform_to_matrix(bone.global_transform)
        else:
            xf = parentObj.matrix_world

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
            constr.name = ('bhkCollisionConstraint')

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
            sf = (HAVOC_SCALE_FACTOR * game_collision_sf[self.game] * (1/self.export_xf.to_scale()[0]))
            ctr, d, r = BD.find_box_info(box)
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
            BD.append_if_new(norms, n, 0.1)
        
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

        havocxf = BD.MatrixLocRotScale(childtransl, childrot, Vector((1,1,1,)))
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


    def export_collision_body(self, targobj, collpair:BD.ReprObject):
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
            mx = BD.MatrixLocRotScale(rv/HAVOC_SCALE_FACTOR, targq, (1,1,1))
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

        colnode = targnode.add_collision(None, flags=flags)
        collpair = BD.ReprObject(coll, colnode)
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
        if parent_handler.objs_written.find_blend(collshape): return 

        exporter.export_collision_object(targobj, collshape)


