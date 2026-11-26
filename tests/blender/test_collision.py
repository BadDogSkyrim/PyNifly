"""Collision, physics and MOPP tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('SKYRIM', 'SHADER', 'PHYSICS')
def TEST_POT():
    """Test that pot shaders doesn't throw an error; also collisions"""
    testfile = TTB.test_file(r"tests\SkyrimSE\spitpotopen01_ALT.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    assert 'ANCHOR:0' in bpy.data.objects.keys()

    anchor = bpy.data.objects['ANCHOR']
    anchor_sh = anchor.constraints[0].target
    assert anchor_sh, "Have collision shape for anchor"

    anchor_z = anchor.matrix_world.translation.z
    anchor_sh_z = anchor_sh.matrix_world.translation.z
    assert BD.NearEqual(anchor_z, anchor_sh_z), f"Near equal z locations: {anchor_z} == {anchor_sh_z}"

    hook = bpy.data.objects['L1_Hook']
    hook_sh = hook.constraints[0].target
    assert hook_sh, "Have collision shape for hook"

    hook_z = hook.matrix_world.translation.z
    hook_sh_z = hook_sh.matrix_world.translation.z
    assert BD.NearEqual(hook_z, hook_sh_z), f"Hook collision near hook: {hook_z} > {hook_sh_z}"
    for v in hook_sh.data.vertices:
        assert v.co.z < 0, f"Hook verts all below hook anchor point: {v.co}"


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_BOW_SCALE():
    """Collisions scale correctly on import and export"""
    # Collisions have to be scaled with everything else if the import/export
    # has a scale factor.

    # Primarily tests collisions, but this nif has everything: collisions, root node as
    # fade node, bone hierarchy, extra data nodes. So tests for those and also  
    # UV orientation and texture handling

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW_SCALE.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 blender_xf=True, 
                                 import_pose=False,
                                 rename_bones=False)

    # ------- Check --------
    bow = TTB.find_shape("ElvenBowSkinned:0")

    # Check shape size
    assert TT.is_equiv(bow.scale, Vector((1,1,1,)), "Bow scale")
    maxy = max(v.co.y for v in bow.data.vertices)
    miny = min(v.co.y for v in bow.data.vertices)
    assert TT.is_equiv(maxy, 64.4891, "Max y")
    assert TT.is_equiv(miny, -50.5509, "Min y")

    # Make sure the bone positions didn't get messed up by blender_xf.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    mxbind = arma.data.bones['Bow_StringBone1'].matrix_local
    mxpose = arma.pose.bones['Bow_StringBone1'].matrix
    assert TT.is_equiv(mxbind, mxpose, "Bind position vs pose position")

    # Check collision info
    midbone = arma.data.bones['Bow_MidBone']
    midbonew = arma.matrix_world @ midbone.matrix_local
    coll = arma.pose.bones['Bow_MidBone'].constraints[0].target
    assert TT.is_equiv(coll.matrix_world.translation, midbonew.translation, "Collision position")

    q = coll.matrix_world.to_quaternion()
    assert TT.is_equiv(q, (0.7071, 0.0, 0.0, 0.7071,), "Collision body rotation")

    # Scale factor applied to bow
    objmin, objmax = TTB.get_obj_bbox(bow, worldspace=True)
    assert TT.is_lt(objmax.y - objmin.y, 12, "Bow scale")

    # Collision box bounds close to bow bounds.
    collbox = TTB.find_shape('bhkBoxShape')
    assert TTB.close_bounds(bow, collbox), "Collision just covers bow"

    # Quick unit test--getting box info should be correct in world coordinates.
    c, d, r = BD.find_box_info(collbox)
    dworld = collbox.matrix_world.to_quaternion().inverted() @ (r @ d)
    dworld = Vector([abs(n) for n in dworld])

    # The rotation should result is the long axis aligned with y, short with z
    assert dworld.y > dworld.x > dworld.z, "Have correct rotation"

    # Centerpoint of collision box is just offset from origin
    assert TT.is_equiv(c, Vector((0.6402, 0.0143, 0.002,)), "Centerpoint")

    ### FIX ###

    # Move the edge of the collision box so it covers the bow better
    for v in collbox.data.vertices:
        if v.co.x < 0:
            v.co.x -= 0.1
        if v.co.y > 0:
            v.co.y += 6

    collbox.update_from_editmode()
    boxmin, boxmax = TTB.get_obj_bbox(collbox, worldspace=True)
    assert NT.VNearEqual(objmax, boxmax, epsilon=1.0), f"Collision just covers bow: {objmax} ~~ {boxmax}"

    ### EXPORT ###

    # We want the special properties of the root node. 
    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                 target_game='SKYRIMSE', 
                                 preserve_hierarchy=True,
                                 blender_xf=True,
                                 intuit_defaults=False,)
    
    ### CHECK ###

    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)

    TTB.compare_shapes(nif.shape_dict['ElvenBowSkinned:0'],
                      nifcheck.shape_dict['ElvenBowSkinned:0'],
                      bow)

    rootcheck = nifcheck.rootNode
    assert TT.is_eq(rootcheck.name, "GlassBowSkinned.nif", "Root node name")
    assert TT.is_eq(rootcheck.blockname, "BSFadeNode", "Root node type")
    assert TT.is_eq(rootcheck.flags, 14, "Root block flags")

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert TT.is_eq(collcheck.blockname, "bhkCollisionObject", "Collision node block")
    assert TT.is_eq(bhkCOFlags(collcheck.flags).fullname, "ACTIVE | SYNC_ON_UPDATE", "Collision flags")

    # Full check of locations and rotations to make sure we got them right
    TTB.compare_bones('Bow_MidBone', nif, nifcheck, e=0.001)
    TTB.compare_bones('Bow_StringBone2', nif, nifcheck, e=0.001)

    # Re-import the nif to make sure collisions are right. Could test them in the nif
    # directly but the math is gnarly.
    TTB.clear_all()

    bpy.ops.import_scene.pynifly(filepath=outfile, 
                                 blender_xf=True,
                                 import_pose=False,
                                 rename_bones=False)
    bow = bpy.context.object
    arma = bow.modifiers['Armature'].object
    bone = arma.pose.bones['Bow_MidBone']
    box = bone.constraints[0].target
    mina, maxa = TTB.get_obj_bbox(bow, worldspace=True)
    minb, maxb = TTB.get_obj_bbox(box, worldspace=True)
    assert TT.is_lt(minb[0], mina[0], "Box min x")
    assert TT.is_lt(minb[1], mina[1], "Box min y")
    assert TT.is_gt(maxb[0], maxa[0], "Box max x")
    assert TT.is_gt(maxb[1], maxa[1], "Box max y")


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_BOW():
    """Can read and write bow"""
    # The bow has a simple collision that we can import and export.
    # Note the bow nif as shipped by Bethesda throws errors on import, and the 
    # collision does not match the mesh closely at all. This test adjusts it on
    # export because it was too ugly.

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    obj = bpy.context.object

    # Check root info
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    TT.assert_eq(root["pynBlockName"], 'BSFadeNode', "Root block type")
    TT.assert_eq(root["pynNodeName"], "GlassBowSkinned.nif", "Root block name")
    TT.assert_eq(root["pynNodeFlags"], 
                 "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR", 
                 "root node flags")
    TT.assert_eq(len([c for c in root.children if c.type=='MESH']), 1, "Mesh count")

    # Check shape size
    bow = TTB.find_shape("ElvenBowSkinned:0")
    maxy = max(v.co.y for v in bow.data.vertices)
    miny = min(v.co.y for v in bow.data.vertices)
    TT.assert_equiv(maxy, 64.4891, "max y")
    TT.assert_equiv(miny, -50.5509, "min y")

    # Check armature
    arma = bow.modifiers['Armature'].object
    TT.assert_eq(len(arma.data.bones), 7, "Bone count")
    maxx = max(b.matrix_local.translation.x for b in arma.data.bones)
    minx = min(b.matrix_local.translation.x for b in arma.data.bones)
    maxy = max(b.matrix_local.translation.y for b in arma.data.bones)
    miny = min(b.matrix_local.translation.y for b in arma.data.bones)
    TT.assert_gt(maxx, 1.0, "max x")
    TT.assert_lt(minx, -10.0, "min x")
    TT.assert_gt(maxy, 50.0, "max y")
    TT.assert_lt(miny, -50.0, "min y")

    # Check collision info
    coll = arma.pose.bones['Bow_MidBone'].constraints['bhkCollisionConstraint'].target
    TT.assert_eq(coll.name, 'bhkBoxShape', "Collision shape")
    TT.assert_eq(coll.pyn_collisionobj.flags, "ACTIVE | SYNC_ON_UPDATE", "bhkCollisionShape represents a collision")
    TT.assert_eq(coll.pyn_rigidbody.collisionFilter_layer, SkyrimCollisionLayer.WEAPON.name,
                 "Collsion filter layer")

    # Default collision response is 1 = SIMPLE_CONTACT, so no property for it.
    # assert coll["collisionResponse"] == hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"

    # assert NT.VNearEqual(coll.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), f"Collision body rotation correct: {collbody.rotation_quaternion}"

    TT.assert_eq(coll.pyn_collshape.bhkMaterial, 'MATERIAL_BOWS_STAVES', "Shape material")
    TT.assert_equiv(coll.pyn_collshape.bhkRadius, 0.0136, "Radius")

    # Covers the bow closely in the Y axis
    bowmax = max((bow.matrix_world @ v.co).y for v in bow.data.vertices)
    boxmax = max((coll.matrix_world @ v.co).y for v in coll.data.vertices)
    TT.assert_equiv(bowmax, boxmax, "Collision max extent", e=0.1)
    bowmin = min((bow.matrix_world @ v.co).y for v in bow.data.vertices)
    boxmin = min((coll.matrix_world @ v.co).y for v in coll.data.vertices)
    TT.assert_equiv(bowmin, boxmin+0.25, "Collision min extent", e=0.1)

    # Covers the bow badly in the X axis
    bowmax = max((bow.matrix_world @ v.co).x for v in bow.data.vertices)
    boxmax = max((coll.matrix_world @ v.co).x for v in coll.data.vertices)
    TT.assert_equiv(bowmax, boxmax+5.4, "Collision max extent", e=0.1)
    bowmin = min((bow.matrix_world @ v.co).x for v in bow.data.vertices)
    boxmin = min((coll.matrix_world @ v.co).x for v in coll.data.vertices)
    TT.assert_equiv(bowmin, boxmin+1.25, "Collision min extent", e=0.1)

    # Check extra data
    bged = TTB.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    TT.assert_eq(bged.pyn_bsbehavior.value, r"Weapons\Bow\BowProject.hkx", "BGED node value")

    strd = TTB.find_shape("NiStringExtraData", type='EMPTY')
    TT.assert_eq(strd.pyn_nistrdata.value, "WeaponBow", "string extra data value")

    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    TT.assert_eq(bsxf.parent, root, "Extra data parent")
    TT.assert_eq(bsxf.pyn_bsxflags.name, "BSX", "BSX Flags name")
    TT.assert_eq(bsxf.pyn_bsxflags.value, "HAVOC | COMPLEX | DYNAMIC | ARTICULATED", "BSX Flags value")

    invm = TTB.find_shape("BSInvMarker", type='CAMERA')
    TT.assert_eq(invm.pyn_invmarker.name, "INV", "Inventory marker name")
    TT.assert_eq(invm.pyn_invmarker.rotation[0], 4712, "Inventory marker x rotation")
    TT.assert_equiv(invm.pyn_invmarker.zoom, 1.1273, "Inventory marker zoom")

    # Check shape as deformed by armature
    BD.ObjectSelect([bow], active=True)
    bpy.ops.object.duplicate()
    bpy.context.object.name = 'TEST_COLLISION_BOW_COPY'
    for m in bow.modifiers:
        if m.type == 'ARMATURE':
            bpy.ops.object.modifier_apply(modifier=m.name)
    maxy = max(v.co.y for v in bow.data.vertices)
    miny = min(v.co.y for v in bow.data.vertices)
    TT.assert_equiv(maxy, 64.4891, "Max y")
    TT.assert_equiv(miny, -50.5509, "Min y")
    
    ### FIX ###

    # Move the edge of the collision box so it covers the bow better
    for v in coll.data.vertices:
        if v.co.y > 0:
            v.co.y += 5.4

    ### EXPORT ###

    # Exporting the root object takes everything with it and sets root properties.
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', 
                                 preserve_hierarchy=True)

    ### CHECK ###

    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    CheckBow(nif, nifcheck, bow)


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_BOW2():
    """Can modify collision shape location."""

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW2.nif")
    
    bpy.ops.import_scene.pynifly(filepath=testfile)
    bow = bpy.context.object
    root = bow.parent
    arma = bow.modifiers['Armature'].object
    coll = arma.pose.bones['Bow_MidBone'].constraints['bhkCollisionConstraint'].target
    bged = TTB.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TTB.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    invm = TTB.find_shape("BSInvMarker", type='CAMERA')

    # ------- Export --------
    # Move the edge of the collision box so it covers the bow better
    for v in coll.data.vertices:
        if v.co.y > 0:
            v.co.y += 5.4

    # Move the collision object 
    coll.location = coll.location + Vector([5, 10, 0])

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile2, target_game='SKYRIMSE')

    # ------- Check Results 2 --------
    nif = pyn.NifFile(testfile)
    nifcheck2 = pyn.NifFile(outfile2)
    CheckBow(nif, nifcheck2, bow)

    assert TT.is_eq([(s.name, len(s.verts)) for s in nifcheck2.shapes],
                    [('ElvenBowSkinned:0', 1561)], "bow exported")
    collcheck2 = nifcheck2.nodes["Bow_MidBone"].collision_object
    assert TT.is_eq((collcheck2.blockname, collcheck2.body.shape.blockname),
                    ('bhkCollisionObject', 'bhkBoxShape'), "moved collision box exported")

    # midbowcheck2 = nifcheck2.nodes["Bow_MidBone"]
    # collcheck2 = midbowcheck2.collision_object
    # assert collcheck2.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck2.blockname}"
    # assert bhkCOFlags(collcheck2.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # # Full check of locations and rotations to make sure we got them right
    # mbc_xf = nifcheck2.get_node_xform_to_global("Bow_MidBone")
    # assert NT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    # m = BD.transform_to_matrix(mbc_xf).to_euler()
    # assert NT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    # bodycheck2 = collcheck2.body
    # p = bodycheck2.properties
    # assert NT.VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
    # assert NT.VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


@TT.category('SKYRIM', 'PHYSICS')
@TT.parameterize('bl', ['NATURAL', 'BLENDER'])
def TEST_COLLISION_BOW3(bl):
    """Can modify collision shape type"""
    # We can change the collision by editing the Blender shapes. Collision shape has a
    # rotation and no scale. Check with and without Blender transform.

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile3 = TTB.test_file(f"tests/Out/TEST_COLLISION_BOW3_{bl}.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=(bl=='BLENDER'))
    bow = bpy.context.object
    root = bow.parent
    arma = bow.modifiers['Armature'].object
    coll = arma.pose.bones['Bow_MidBone'].constraints['bhkCollisionConstraint'].target

    # ------- Export --------

    # Move the collision object 
    for v in coll.data.vertices:
        if NT.NearEqual(v.co.y, 3.3, epsilon=0.5):
            v.co.y = 9.3
            if v.co.x > 0:
                v.co.x = 30.6
            else:
                v.co.x = -19.5
    coll.name = "bhkConvexVerticesShape"

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile3, target_game='SKYRIMSE')
    
    # ------- Check Results 3 --------

    nifcheck3 = pyn.NifFile(outfile3)

    midbowcheck3 = nifcheck3.nodes["Bow_MidBone"]
    collcheck3 = midbowcheck3.collision_object
    assert collcheck3.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck3.blockname}"
    assert bhkCOFlags(collcheck3.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    # Full check of locations and rotations to make sure we got them right
    mbc_xf = nifcheck3.get_node_xform_to_global("Bow_MidBone")
    assert NT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = BD.transform_to_matrix(mbc_xf).to_euler()
    assert NT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    bodycheck3 = collcheck3.body

    cshapecheck3 = bodycheck3.shape
    assert cshapecheck3.blockname == "bhkConvexVerticesShape", f"Shape is convex vertices: {cshapecheck3.blockname}"
    assert NT.VNearEqual(cshapecheck3.vertices[0], (-0.73, -0.267, 0.014, 0.0)), "Convex shape is correct"


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_HIER():
    """Can read and write hierarchy of nodes containing shapes"""
    # These leeks are two shapes collected under an NiNode, with the collision on the 
    # NiNode. 

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\grilledleekstest.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_HIER.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek0 = TTB.find_shape("Leek04:0")
    leek1 = TTB.find_shape("Leek04:1")
    leek4 = leek0.parent
    assert leek4.name == 'Leek04', "Have correct parent"
    assert leek0.parent == leek1.parent, "Have correct parent/child relationships"
    assert len(leek4.constraints) > 0, "Have constraint on parent"
    cshape = leek4.constraints[0].target
    assert cshape, "Have collision shape"
    xf = cshape.matrix_world
    minx = min((xf @ v.co).x for v in cshape.data.vertices)
    maxx = max((xf @ v.co).x for v in cshape.data.vertices)
    miny = min((xf @ v.co).y for v in cshape.data.vertices)
    maxy = max((xf @ v.co).y for v in cshape.data.vertices)
    assert abs(minx - -12.2) < 0.1, f"Minimum x of collision shape is correct: {minx}"
    assert abs(maxx - -5.5) < 0.1, f"Maximum x of collision shape is correct: {maxx}"
    assert abs(miny - -2.4) < 0.1, f"Minimum y of collision shape is correct: {miny}"
    assert abs(maxy - 1.7) < 0.1, f"Maximum y of collision shape is correct: {maxy}"

    # ------- Export --------

    # Select the objects to export. Do this instead of exporting the root. Should still
    # work.
    leek4 = bpy.data.objects["Leek04"]
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    invm = TTB.find_shape("BSInvMarker", type='CAMERA')
    BD.ObjectSelect([leek4, bsxf, invm], active=True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check Results --------

    nifOrig = pyn.NifFile(testfile)
    l4NodeOrig = nifOrig.nodes["Leek04"]
    collOrig = l4NodeOrig.collision_object
    rbOrig = collOrig.body
    shOrig = rbOrig.shape

    nifcheck = pyn.NifFile(outfile)
    leek4Check = nifcheck.nodes['Leek04']
    coCheck = leek4Check.collision_object
    rbCheck = coCheck.body
    shCheck = rbCheck.shape
    assert shCheck.blockname == "bhkConvexVerticesShape", "Have our convex vert shape"
    l0Check = nifcheck.shape_dict["Leek04:0"]
    l1Check = nifcheck.shape_dict["Leek04:1"]
    assert l0Check.parent.name == "Leek04", f"Shapes are under the grouping node: {l0Check.parent.name}"
    assert l1Check.parent.name == "Leek04", f"Shapes are under the grouping node: {l1Check.parent.name}"
    # Vertices match. Depends on verts not getting re-ordered.
    assert NT.VNearEqual(shCheck.vertices[0], shOrig.vertices[0]), f"Collision vertices match 0: {shCheck.vertices[0][:]} == {shOrig.vertices[0][:]}"
    assert NT.VNearEqual(shCheck.vertices[5], shOrig.vertices[5]), f"Collision vertices match 0: {shCheck.vertices[5][:]} == {shOrig.vertices[5][:]}"


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_MULTI():
    """Can read and write shape with multiple collision shapes"""

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\grilledleeks01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_MULTI.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    leek10 = TTB.find_shape("Leek01:0")
    leek11 = TTB.find_shape("Leek01:1")
    leek1 = leek10.parent
    leek1 == leek10.parent == leek11.parent, "Parent/child relationships correct"
    assert leek1.name == "Leek01", "Have correct parent"
    assert len(leek1.constraints) > 0, "Leek has constraints"
    
    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check ---------
    nif = pyn.NifFile(outfile)
    l1 = nif.nodes["Leek01"]
    l4 = nif.nodes["Leek04"]
    assert l1.collision_object.body.shape.blockname == "bhkConvexVerticesShape", "Have the correct collisions"
    assert l4.collision_object.body.shape.blockname == "bhkConvexVerticesShape", "Have the correct collisions"
    l10 = nif.shape_dict["Leek01:0"]
    l11 = nif.shape_dict["Leek01:1"]
    assert l10.parent.name == "Leek01", f"Leek01:0 parent correct: {l10.parent.name}"
    assert l11.parent.name == "Leek01", f"Leek01:0 parent correct: {l11.parent.name}"
    l40 = nif.shape_dict["Leek04:0"]
    l41 = nif.shape_dict["Leek04:1"]
    assert l40.parent.name == "Leek04", f"Leek04:0 parent correct: {l40.parent.name}"
    assert l41.parent.name == "Leek04", f"Leek04:0 parent correct: {l41.parent.name}"


@TT.category('SKYRIM', 'PHYSICS')
@TT.parameterize('bx', [True, False])
def TEST_COLLISION_CONVEXVERT(bx):
    """"Can read and write shape with convex verts collision shape at scale."""
    print(f"<<<Can read and write shape with convex verts collision shape at scale {bx}>>>")

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\cheesewedge01.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_CONVEXVERT.{'BL' if bx else 'NAT'}.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=bx)

    # Check transform
    cheese = bpy.data.objects["CheeseWedge01:0"]
    TT.assert_equiv(cheese.location, (0,0,0,), "cheese location")
    TT.assert_equiv(cheese.rotation_euler, (0,0,0,), "cheese rotation")
    TT.assert_equiv(cheese.scale, Vector((1,1,1,)), "cheese scale")

    # Check collision info
    root = cheese.parent
    constr = [c for c in root.constraints if c.type == 'COPY_TRANSFORMS']
    assert constr, "Have constraints on root"
    coll = constr[0].target
    assert coll, "Have collision object"
    assert coll.rigid_body, "Collision object has physics"
    TT.assert_eq(coll.rigid_body.type, 'ACTIVE', "Collision body type")
    TT.assert_equiv(coll.rigid_body.mass, 2.5, "mass")
    TT.assert_equiv(coll.rigid_body.friction, 0.5, "friction")
    TT.assert_eq(coll.pyn_collshape.bhkMaterial, 'CLOTH', "Shape material custom property")

    xmax1 = max([v.co.x for v in cheese.data.vertices])
    xmax2 = max([v.co.x for v in coll.data.vertices])
    TT.assert_equiv(xmax1, xmax2, "Max x vertex", e=0.5)
    corner = coll.data.vertices[0].co
    TT.assert_equiv(corner, (-4.18715, -7.89243, 7.08596,), "Collision shape position")

    # ------- Export --------

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', 
                                    blender_xf=bx)

    # ------- Check Results --------

    niforig = pyn.NifFile(testfile)
    rootorig = niforig.rootNode
    collorig = rootorig.collision_object
    bodyorig = collorig.body
    cvsorig = bodyorig.shape

    nifcheck = pyn.NifFile(outfile)
    rootcheck = nifcheck.rootNode
    collcheck = rootcheck.collision_object
    bodycheck = collcheck.body
    cvscheck = bodycheck.shape

    TT.assert_eq(rootcheck.name, "CheeseWedge01", "Root node name")
    TT.assert_eq(rootcheck.blockname, "BSFadeNode", "Root node type")

    TT.assert_eq(collcheck.blockname, "bhkCollisionObject", "Collision node type")
    TT.assert_eq(collcheck.target, rootcheck, "Collision target")

    TT.assert_eq(bodycheck.blockname, "bhkRigidBody", "Rigid body type")
    TT.assert_eq(bodycheck.properties.mass, 2.5, "Rigid body mass")
    TT.assert_eq(bodycheck.properties.friction, 0.5, "Rigid body friction")

    TT.assert_eq(cvscheck.blockname, "bhkConvexVerticesShape", "Collision shape type")
    TT.assert_eq(cvscheck.properties.bhkMaterial, SkyrimHavokMaterial.CLOTH, 
        "Collision body shape material")

    minxch = min(v[0] for v in cvscheck.vertices)
    maxxch = max(v[0] for v in cvscheck.vertices)
    minxorig = min(v[0] for v in cvsorig.vertices)
    maxxorig = max(v[0] for v in cvsorig.vertices)

    TT.assert_equiv(minxch, minxorig, "Vertex x min")
    TT.assert_equiv(maxxch, maxxorig, "Vertex x max")

    # Re-import
    #
    # There have been issues with importing the exported nif and having the 
    # collision be wrong
    # TTB.clear_all()
    BD.ObjectSelect([], active=False)
    for obj in bpy.context.scene.objects:
        obj.hide_set(True)
    bpy.ops.import_scene.pynifly(filepath=outfile)

    cheese_new = bpy.context.object
    impcollshape = cheese_new.parent.constraints[0].target
    zmin = min([v.co.z for v in impcollshape.data.vertices])
    TT.assert_gt(zmin, -0.01, "Minimum z")


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_PANEL_SURFACES():
    """An author-created collision object gets its PyNifly panel back on export.

    Verifies the general mechanism the SF-morph fix relies on: any export that *reads* a
    typed group goes through ensure_*_migrated, which sets the group's `_migrated` flag as
    a side effect -- so a shape whose group was never migrated (author-created) surfaces its
    panel after export. We simulate an author-created shape by stripping the migrated flag
    off an imported collision, then export and check the panel comes back."""
    testfile = TTB.test_file(r"tests\Skyrim\cheesewedge01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_PANEL_SURFACES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    cheese = bpy.data.objects["CheeseWedge01:0"]
    root = cheese.parent
    coll = root.constraints[0].target

    # Simulate an author-created collision: clear every migrated flag import set (the object
    # carries a group each for the shape, rigid body, and collision object), so the panel hides.
    for k in ('pyn_collshape_migrated', 'pyn_rigidbody_migrated', 'pyn_collisionobj_migrated'):
        if k in coll:
            del coll[k]
    bpy.context.view_layer.objects.active = coll
    assert not pyn_props.PYN_PT_block.poll(bpy.context), \
        "precondition: with no migrated groups the panel is hidden"

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # Export reads the shape's props through collshape_store -> ensure_handwired_migrated, which
    # sets the flag as a side effect -- so the panel comes back with no morph-style change needed.
    assert coll.get('pyn_collshape_migrated'), \
        "export re-marked the collision-shape group migrated via the ensure_*_migrated read path"
    bpy.context.view_layer.objects.active = coll
    assert pyn_props.PYN_PT_block.poll(bpy.context), "the PyNifly block panel shows after export"


@TT.category('SKYRIM', 'PHYSICS')
@TT.parameterize('bx', [True, False])
def TEST_COLLISION_CAPSULE(bx):
    """Can read and write shape with collision capsule shapes with and without Blender transforms"""
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    print(f"<<<Can read and write shape with collision capsule shapes with Blender transforms {bx}>>>")

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\staff04.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_CAPSULE.{'BL' if bx else 'NAT'}.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=bx)

    staff = TTB.find_shape("3rdPersonStaff04")
    coll = staff.parent.constraints[0].target
    assert coll.pyn_collshape.bhkMaterial == 'SOLID_METAL', "Have correct material"
    strd = TTB.find_shape("NiStringExtraData", type="EMPTY")
    bsxf = TTB.find_shape("BSXFlags", type="EMPTY")
    invm = TTB.find_shape("BSInvMarker", type="EMPTY")

    # The staff has bits that stick out, so its bounding box is a bit larger than
    # the collision's.
    staffmin, staffmax = TTB.get_obj_bbox(staff, worldspace=True)
    collmin, collmax = TTB.get_obj_bbox(coll, worldspace=True)
    assert staffmax[0] > collmax[0], f"Staff surrounds collision: {staffmax}, {collmax}"
    assert staffmax[1] > collmax[1], f"Staff surrounds collision: {staffmax}, {collmax}"
    assert staffmax[2] > collmax[2], f"Staff surrounds collision: {staffmax}, {collmax}"
    assert staffmin[0] < collmin[0], f"Staff surrounds collision: {staffmax}, {collmax}"
    assert staffmin[1] < collmin[1], f"Staff surrounds collision: {staffmax}, {collmax}"
    assert staffmin[2] < collmin[2], f"Staff surrounds collision: {staffmax}, {collmax}"

    # -------- Export --------
    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', blender_xf=bx)

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)
    staffcheck = nifcheck.shape_dict["3rdPersonStaff04:1"]
    collcheck = nifcheck.rootNode.collision_object
    rbcheck = collcheck.body
    shapecheck = rbcheck.shape
    assert shapecheck.blockname == "bhkCapsuleShape", f"Got a capsule collision back {shapecheck.blockname}"

    niforig = pyn.NifFile(testfile)
    collorig = niforig.rootNode.collision_object
    rborig = collorig.body
    shapeorig = rborig.shape
    assert NT.NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), \
        f"Wrote the correct radius: {shapecheck.properties.radius1}"
    
    assert NT.NearEqual(shapeorig.properties.point1[1], 
                        shapecheck.properties.point1[1],
                        epsilon=0.05), \
        f"Wrote the correct radius: {shapecheck.properties.point1[1]}"


@TT.category('SKYRIM', 'PHYSICS')
@TT.parameterize('bx', [True, False])
def TEST_COLLISION_CAPSULE2(bx):
    """Can read and write shape with collision capsule shapes with and without Blender transforms."""
    # Note that the collision object is slightly offset from the shaft of the staff.
    # It might even be intentional, to give the staff a more irregular roll, since 
    # they didn't do a collision for the protrusions.
    print(f"<<<Can read and write shape with collision capsule shapes with Blender transforms {bx}>>>")

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\staff04-collision.nif")
    outfile = TTB.test_file(
        f"tests/Out/TEST_COLLISION_CAPSULE2.{'BL' if bx else 'NAT'}.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=bx)

    staff = TTB.find_shape("3rdPersonStaff04")
    root = staff.parent
    collshape = root.constraints[0].target

    # -------- Export --------
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM', blender_xf=bx)

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)
    staffcheck = nifcheck.shape_dict["3rdPersonStaff04:1"]
    collcheck = nifcheck.rootNode.collision_object
    rbcheck = collcheck.body
    shapecheck = rbcheck.shape
    assert shapecheck.blockname == "bhkCapsuleShape", f"Got a capsule collision back {shapecheck.blockname}"

    niforig = pyn.NifFile(testfile)
    collorig = niforig.rootNode.collision_object
    rborig = collorig.body
    shapeorig = rborig.shape
    assert NT.NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), \
        f"Wrote the correct radius: {shapecheck.properties.radius1}"
    
    assert NT.NearEqual(shapeorig.properties.point1[1], 
                        shapecheck.properties.point1[1],
                        epsilon=0.002), \
        f"Wrote the correct point location: {shapecheck.properties.point1[1]}"


@TT.category('SKYRIM', 'PHYSICS')
@TT.parameterize('bx', ['BLENDER', 'NATURAL'])
def TEST_COLLISION_LIST(bx):
    """
    Can read and write shape with collision list and collision transform shapes with and
    without Blender transform.
    """
    print(f"<<<Can read and write shape with collision list and collision transform shapes with Blender transform {bx}>>>")

    # ------- Load --------
    testfile = TTB.test_file(r"tests\Skyrim\falmerstaff.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_LIST_{bx}.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=(bx=='BLENDER'))

    staff = TTB.find_shape("Staff3rdPerson:0")
    root = staff.parent
    collshape = root.constraints[0].target
    assert collshape.name.startswith('bhkListShape'), "Have list shape"
    yvals = set(round(obj.location.y, 1) for obj in collshape.children)
    expectedy = set(map(lambda x: round(x*HAVOC_SCALE_FACTOR, 1), [0.632, -0.19, 0.9]))
    assert yvals == expectedy, f"Have expected y vals: {yvals} == {expectedy}"

    assert collshape.name.startswith("bhkListShape"), f"Found list collision shape: {collshape.name}"
    assert len(collshape.children) == 3, " Collision shape has children"

    # -------- Export --------
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                    target_game='SKYRIM', 
                                    blender_xf=(bx=='BLENDER'))

    # ------- Check ---------
    niforig = pyn.NifFile(testfile)
    stafforig = niforig.shape_dict["Staff3rdPerson:0"]
    collorig = niforig.rootNode.collision_object
    listorig = collorig.body.shape
    xfshapesorig = listorig.children[:]
    xfshapematorig = [s.properties.bhkMaterial for s in xfshapesorig]

    nifcheck = pyn.NifFile(outfile)
    staffcheck = nifcheck.shape_dict["Staff3rdPerson:0"]
    collcheck = nifcheck.rootNode.collision_object
    listcheck = collcheck.body.shape
    xfshapescheck = listcheck.children[:]
    xfshapematcheck = [s.properties.bhkMaterial for s in xfshapescheck]

    assert xfshapematcheck == xfshapematorig, \
        f"Materials written to ConvexTransformShape: {xfshapematcheck} == {xfshapematorig}"

    assert listcheck.blockname == "bhkListShape", f"Got a list collision back {listcheck.blockname}"
    assert len(listcheck.children) == 3, f"Got our list elements back: {len(listcheck.children)}"

    convex_xf_shape = listcheck.children[0]
    convex_xf = Matrix(convex_xf_shape.properties.transform)
    assert convex_xf.to_scale()[0] == 1.0, f"Have the correct scale: {convex_xf.to_scale()}"

    assert convex_xf_shape.child.blockname == "bhkBoxShape", "Found the box shape"

    # Check that the ConvexTransforms put the collision shapes in the right place,
    # no matter what order they're written.
    xflist = set(round(xfs.transform[1][3], 3) for xfs in xfshapesorig)
    xfcheck = set(round(xfs.transform[1][3], 3) for xfs in xfshapescheck)
    assert xflist == xfcheck, "Have same transforms in both files"

    cts45check = None
    for cts in listcheck.children:
        erot = Matrix(cts.transform).to_euler()
        theta = round(math.degrees(erot.x))
        if NT.NearEqual(theta % 45, 0): # Is some multiple of 45
            cts45check = cts
    boxdiag = cts45check.child
    assert NT.NearEqual(boxdiag.properties.bhkDimensions[1], 0.170421), f"Diagonal box has correct size: {boxdiag.properties.bhkDimensions[1]}"


@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_BOW_CHANGE():
    """Changing collision type works correctly"""

    # ------- Load --------
    testfile = TTB.test_file(r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_BOW_CHANGE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    arma = obj.modifiers['Armature'].object
    bone = arma.pose.bones['Bow_MidBone']
    collshape = bone.constraints[0].target
    bged = TTB.find_shape("BSBehaviorGraphExtraData", type='EMPTY')
    strd = TTB.find_shape("NiStringExtraData", type='EMPTY')
    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    invm = TTB.find_shape("BSInvMarker", type='EMPTY')
    assert TT.is_eq(collshape.name, 'bhkBoxShape', "Found collision shape")
    
    collshape.name = "bhkConvexVerticesShape"

    # ------- Export --------

    BD.ObjectSelect([obj for obj in bpy.data.objects if 'pynRoot' in obj], active=True)
    
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check Results --------

    nifcheck = pyn.NifFile(outfile)
    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert TT.is_eq(collcheck.blockname, "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}")
    bodycheck = collcheck.body
    assert TT.is_eq(bodycheck.properties.bufType, PynBufferTypes.bhkRigidBodyBufType, "Have correct buffer type")

    names = [x.name for x in nifcheck.root.extra_data(blockname="BSBehaviorGraphExtraData")]
    assert TT.is_contains("BGED", names, f"Error: Expected BGED in {names}")
    bgedCheck = nifcheck.root.get_extra_data(blockname='BSBehaviorGraphExtraData', name='BGED')
    assert TT.is_eq(bgedCheck.behavior_graph_file, "Weapons\\Bow\\BowProject.hkx", "Extra data value")
    assert TT.is_eq(bgedCheck.controls_base_skeleton, False, "Extra data controls base skeleton")


@TT.min_version(4, 0, 0)
@TT.category('SKYRIM', 'PHYSICS')
def TEST_COLLISION_XFORM():
    """
    Can read and write shape with collision we build ourselves in Blender.
    """
    # TriShapes provide for a collision to be attached to them directly but vanilla Skyrim
    # nifs never do that. So make a root node and attach the collision to that.
    #
    # Note we then have to export the root node or we don't get the collisions.

    # Blender V2.x does not import the whole parent chain when appending an object from
    # another file, so don't try to run this on that version.

    # ------- Load --------
    blendfile = TTB.test_file(r"tests/SkyrimSE/staff.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_XFORM.nif")
    
    bpy.ops.object.add(radius=1.0, type='EMPTY')
    root = bpy.context.object
    root.name = 'Root'

    staff = TTB.append_from_file("Staff", True, blendfile, r"\Object", "Staff")
    inv = TTB.append_from_file("BSInvMarker", True, blendfile, r"\Object", "BSInvMarker")
    flg = TTB.append_from_file("BSXFlags", True, blendfile, r"\Object", "BSXFlags")
    ext = TTB.append_from_file("NiStringExtraData", True, blendfile, r"\Object", "NiStringExtraData")
    c1 = TTB.append_from_file("bhkCapsuleShape", True, blendfile, r"\Object", "bhkCapsuleShape")
    c2 = TTB.append_from_file("bhkConvexVerticesShape", True, blendfile, r"\Object", "bhkConvexVerticesShape")
    c3 = TTB.append_from_file("bhkConvexVerticesShape.001", True, blendfile, r"\Object", "bhkConvexVerticesShape.001")
    c4 = TTB.append_from_file("bhkConvexVerticesShape.002", True, blendfile, r"\Object", "bhkConvexVerticesShape.002")
    listcollision = TTB.append_from_file("bhkListShape", True, blendfile, r"\Object", "bhkListShape")
    c1.parent = listcollision
    c2.parent = listcollision
    c3.parent = listcollision
    c4.parent = listcollision

    # # Set up the collision target
    # staff.constraints["Copy Transforms"].target = listcollision
    
    # Append screwed positions up, so fix them.
    for c in [c1, c2, c3, c4, listcollision]:
        for v in c.data.vertices:
            v.co = v.co + Vector((0, listcollision.location.y, 0))

    if len(root.constraints) == 0: 
        constr = root.constraints.new('COPY_TRANSFORMS')
    root.constraints['Copy Transforms'].target = listcollision
    root['pynRoot'] = True
    staff.parent = root
    inv.parent = root
    flg.parent = root
    ext.parent = root
    for obj in bpy.data.objects:
        if obj.name.startswith('bhkListShape') and obj.name != 'bhkListShape':
            BD.ObjectSelect([obj], active=True)
            bpy.ops.object.delete()

    # -------- Export --------
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # ------- Check ---------
    nifcheck = pyn.NifFile(outfile)
    staffcheck = nifcheck.shape_dict["Staff"]
    collcheck = nifcheck.rootNode.collision_object
    rbcheck = collcheck.body
    listcheck = rbcheck.shape
    capsules = [c.child for c in listcheck.children if c.child.blockname == "bhkCapsuleShape"]
    assert capsules[0].properties.point1[1] < 0 < capsules[0].properties.point2[1], \
        "Capsule crosses origin"
    
    capcts = listcheck.children[0] 
    capshape = capcts.child
    assert capshape.blockname == 'bhkCapsuleShape', "Have the capsule"
    capmaxy = (capcts.transform[1][3] + capshape.properties.point2[1]) * HAVOC_SCALE_FACTOR
    assert BD.NearEqual(capmaxy, 67, epsilon=1.0), f"Capsule max y correct: {capmaxy}"

    capminy = (capcts.transform[1][3] + capshape.properties.point1[1]) * HAVOC_SCALE_FACTOR
    assert BD.NearEqual(capminy, -73.4, epsilon=1.0), f"Capsule min y correct: {capminy}"


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_CAPSULE_STAIRS():
    """FO4 bhkPhysicsSystem: compressed_mesh and polytope imported as separate objects.

    CapsuleExtStairsFree01.nif contains a single bhkPhysicsSystem shared by the
    root node and StairHelper03.  That system holds two bodies: one compressed-mesh
    stair shape and one convex-polytope bounding hull.

    Expected import result:
      - Exactly two shape objects (one per body), both named bhkPhysicsSystem_*.
      - The shared physics system is imported only once despite two referencing nodes.
      - The polytope object has Push (GN) and Bevel modifiers for its convex radius.
      - Combined collision bounds overlap the visual mesh on every axis.

    Expected export/round-trip:
      - Both shape types are preserved after export -> reimport.
    """
    testfile = TTB.test_file(r"tests\FO4\CapsuleExtStairsFree01.nif")
    outfile  = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_CAPSULE_STAIRS.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]

    # Separate by shape type.
    cm_shapes   = [o for o in physics_shapes
                   if o.get('pynCollisionShapeType') == 'compressed_mesh']
    poly_shapes = [o for o in physics_shapes
                   if o.get('pynCollisionShapeType') == 'polytope']

    # The shared physics system must be imported exactly once (not once per node).
    # With 2 bodies per system and 1 system, expect exactly 2 shape objects total.
    assert TT.is_eq(len(cm_shapes),   1, "One compressed_mesh shape imported")
    assert TT.is_eq(len(poly_shapes), 1, "One polytope shape imported")

    # Polytope should have Push (GN) and Bevel modifiers for the convex radius.
    poly_obj   = poly_shapes[0]
    push_mods  = [m for m in poly_obj.modifiers if m.name == 'bhkPush']
    bevel_mods = [m for m in poly_obj.modifiers if m.name == 'bhkBevel']
    assert TT.is_gt(len(push_mods),  0, "Polytope has a Push modifier")
    assert TT.is_gt(len(bevel_mods), 0, "Polytope has a Bevel modifier")

    # Combined bounds of all shapes must overlap the visual mesh on every axis.
    mesh_obj = bpy.data.objects["CapsuleExtStairsFree01:1"]
    mesh_bounds = TTB.world_bounds(mesh_obj)
    coll_bounds = TTB.combined_world_bounds(cm_shapes + poly_shapes)
    TTB.assert_bounds_overlap(coll_bounds, mesh_bounds, 5, "Collision vs mesh")

    # ---- Export and round-trip verify ----------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    chk_cm     = [o for o in chk_shapes if o.get('pynCollisionShapeType') == 'compressed_mesh']
    chk_poly   = [o for o in chk_shapes if o.get('pynCollisionShapeType') == 'polytope']
    assert TT.is_eq(len(chk_cm),   1, "Round-trip preserves compressed_mesh shape")
    assert TT.is_eq(len(chk_poly), 1, "Round-trip preserves polytope shape")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_DRUMAG():
    """FO4 bhkPhysicsSystem: compound with multiple polytope children.

    tests/tests/FO4/Shotgun/DrumMag.nif has a single bhkNPCollisionObject on
    CombatShotgunDrumMagazine.  Its bhkPhysicsSystem contains one
    hknpDynamicCompoundShape whose children are two convex polytopes
    (each 8 verts / 12 faces).

    Expected import result:
      - Two polytope objects (compound children flattened to leaves).
      - Both tagged pynCollisionShapeType='polytope'.
      - Both have Push (GN) and Bevel modifiers (convex_radius > 0 for each).

    Expected export/round-trip:
      - pack_shapes dispatches to pack_multi_polytope (two-body all-polytope).
      - Reimport recovers exactly two polytope shapes.
    """
    testfile = TTB.test_file(r"tests\FO4\Shotgun\DrumMag.nif")
    outfile  = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_DRUMAG.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    poly_shapes    = [o for o in physics_shapes
                      if o.get('pynCollisionShapeType') == 'polytope']

    # Compound has 2 polytope children → 2 separate Blender objects.
    assert TT.is_eq(len(poly_shapes), 2, "Two polytope shapes imported from compound")

    # Each should have Push (GN) and Bevel modifiers (both children have convex_radius>0).
    for ps_obj in poly_shapes:
        push_mods  = [m for m in ps_obj.modifiers if m.name == 'bhkPush']
        bevel_mods = [m for m in ps_obj.modifiers if m.name == 'bhkBevel']
        assert TT.is_gt(len(push_mods),  0, f"{ps_obj.name} has Push modifier")
        assert TT.is_gt(len(bevel_mods), 0, f"{ps_obj.name} has Bevel modifier")

    # ---- Bounds check: shell-matching polytope vs ShotgunShell004:0 mesh ------
    shell_obj = bpy.data.objects.get('ShotgunShell004:0')
    assert TT.is_neq(shell_obj, None, "ShotgunShell004:0 mesh exists")

    sx0, sx1, sy0, sy1, sz0, sz1 = TTB.world_bounds(shell_obj)
    sy_span = sy1 - sy0  # ≈ 6.148 Blender units

    # The shell-matching polytope is the smaller one (shell collision << drum magazine collision).
    def bbox_volume(ob):
        b = TTB.world_bounds(ob)
        return (b[1]-b[0]) * (b[3]-b[2]) * (b[5]-b[4])

    shell_poly = min(poly_shapes, key=bbox_volume)
    px0, px1, py0, py1, pz0, pz1 = TTB.world_bounds(shell_poly)

    # y-span should be within 2 Blender units of the shell mesh y-span (≈6.15 vs ≈5.47).
    assert TT.is_lt(abs((py1 - py0) - sy_span), 2.0,
                    "Shell polytope y-span close to shell mesh y-span")

    # x and y extents should overlap with the shell mesh.
    assert TT.is_lt(px0, sx1, "Shell polytope x-min < shell mesh x-max (x extents overlap)")
    assert TT.is_lt(sy0, py1, "Shell mesh y-min < shell polytope y-max (y extents overlap)")

    # z-center of collision polytope is offset below the shell mesh z-center.
    pz_center = (pz0 + pz1) / 2
    sz_center = (sz0 + sz1) / 2
    assert TT.is_lt(pz_center, sz_center,
                    "Shell polytope z-center is offset below shell mesh z-center")

    # ---- Export and round-trip verify ----------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # Check the exported NIF directly at pynifly level before reimporting in Blender.
    from pyn.pynifly import NifFile as PynNifFile
    from pyn.bhk_autounpack import parse_bytes as _parse_bytes
    _chk_nif = PynNifFile(outfile)
    _chk_coll = _chk_nif.root.collision_object
    assert TT.is_neq(_chk_coll, None, "Exported NIF has a collision object")
    _chk_ps = _chk_coll.physics_system
    assert TT.is_neq(_chk_ps, None, "Exported NIF has a bhkPhysicsSystem")
    _chk_raw = _chk_ps.data
    assert TT.is_gt(len(_chk_raw), 0, "Exported bhkPhysicsSystem has non-empty data")
    _chk_decoded = _parse_bytes(_chk_raw)
    _chk_leaf = []
    def _chk_collect(sl):
        for s in sl:
            if s.shape_type == 'compound':
                _chk_collect(s.children)
            else:
                _chk_leaf.append(s)
    _chk_collect(_chk_decoded)
    assert TT.is_eq(len(_chk_leaf), 2, "Exported packfile decodes to 2 leaf shapes")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    chk_poly   = [o for o in chk_shapes if o.get('pynCollisionShapeType') == 'polytope']
    assert TT.is_eq(len(chk_poly), 2, "Round-trip preserves both polytope shapes")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_BOSRADARDISH():
    """FO4 bhkPhysicsSystem with two compound bodies (Main + Swivel).

    The physics system has 2 bodies — one per NIF node (Main, Swivel).  Each
    NIF node should get its own bhkPhysicsSystem container in Blender so that
    COPY_TRANSFORMS constraints target only the correct shapes.

    Main → 4 polytopes covering the dish base (z ≈ 0..170 Bl).
    Swivel → 2 polytopes covering the rotating head (z ≈ 169..276 Bl).
    """
    testfile = TTB.test_file(r"tests\FO4\Meshes\BOSRadarDish.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    polys = [o for o in bpy.data.objects if o.get('pynCollisionShapeType') == 'polytope']
    assert TT.is_eq(len(polys), 6, "Six polytope shapes imported total")

    # Two separate bhkPhysicsSystem containers (one for Main, one for Swivel).
    containers = [o for o in bpy.data.objects if o.get('pynRigidBody') == 'bhkPhysicsSystem'
                  and o.type == 'EMPTY']
    assert TT.is_eq(len(containers), 2, "Two bhkPhysicsSystem containers (one per NIF node)")

    swivel = bpy.data.objects.get('Swivel:0')
    assert TT.is_neq(swivel, None, "Swivel:0 mesh exists")

    def world_z_bounds(ob):
        vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
        return min(v.z for v in vs), max(v.z for v in vs)

    sw_zmin, sw_zmax = world_z_bounds(swivel)

    # Swivel's container holds 2 polytopes whose centroids fall in Swivel:0's world z range.
    swivel_polys = [
        p for p in polys
        if sw_zmin - 20 < sum(world_z_bounds(p)) / 2 < sw_zmax + 20
    ]
    assert TT.is_eq(len(swivel_polys), 2, "Two polytopes cover the Swivel region")

    all_z = [z for p in swivel_polys for z in world_z_bounds(p)]
    tol = 15.0
    assert TT.is_lt(abs(min(all_z) - sw_zmin), tol, "Swivel polytopes bottom near Swivel:0 bottom")
    assert TT.is_lt(abs(max(all_z) - sw_zmax), tol, "Swivel polytopes top near Swivel:0 top")


@TT.category('FO4', 'PHYSICS')
@TT.expect_errors( ("Target of controller not found",
                    "Unknown block type: NiBoolData",
                    "Unknown block type: BSPositionData", # We don't yet handle particle systems
                    # The vanilla gear door really carries 16,097 duplicate tris (every tri
                    # doubled, same winding); dropping them is harmless. Checked 2026-10-03.
                    "Dropped 16097 duplicate triangle(s)",
                    # FXPaper01/FXPaper002 blow along a spline; path animation isn't
                    # imported yet. One summary line, not an "Unknown block type" per block.
                    "Path animation (NiPathInterpolator) is not supported: skipped on 2 object(s)") )
def TEST_COLLISION_FO4_GEARDOOR():
    """FO4 bhkPhysicsSystem shared by 24 NIF nodes — per-body collision import.

    VltGearDoor01.nif has one bhkPhysicsSystem with 24 bodies shared across 24
    NIF nodes.  Each node's bhkNPCollisionObject has a bodyID selecting which
    body to import.

    We verify:
      - Collision shapes were imported for nodes whose collisions are processed
      - Each collision-bearing node has its own constraint target
      - The GearDoor gear shape is correctly positioned (non-identity body rotation)
      - VltGearKeySupport collision is correctly positioned (identity body rotation,
        uses node world transform)
    """
    testfile = TTB.test_file(r"tests\FO4\Meshes\VltGearDoor01.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    coll_shapes = [o for o in bpy.data.objects
                   if o.get('pynCollisionShapeType') in ('polytope', 'compressed_mesh')]
    assert TT.is_gt(len(coll_shapes), 3, "Collision shapes imported")

    # Each collision-bearing node is linked to its own collision. Both of these nodes are
    # animated, so the link runs from the collision to the node (the animation wins); a
    # static node would carry the constraint itself.
    for node_name in ["GearDoor", "VltGearKeySupport"]:
        node_obj = bpy.data.objects[node_name]
        followers = [o for o in bpy.data.objects
                     if any(con.name == 'bhkCollisionConstraint' and con.target == node_obj
                            for con in o.constraints)]
        TT.assert_eq(len(followers), 1, f"{node_name} has its collision")
        assert not [con for con in node_obj.constraints
                    if con.name == 'bhkCollisionConstraint'], \
            f"Animated {node_name} isn't pinned to its collision"
    static = bpy.data.objects["VltGenerator02"]
    assert [con for con in static.constraints if con.name == 'bhkCollisionConstraint'], \
        "Static VltGenerator02 is still driven by its collision"

    # Helper: get world-space vertex bounds for all child meshes of a node.
    def mesh_bounds(node_name):
        xs, ys, zs = [], [], []
        for obj in bpy.data.objects:
            if obj.type != 'MESH' or obj.parent is None:
                continue
            if obj.parent.name != node_name:
                continue
            if obj.get('pynRigidBody'):
                continue  # skip collision objects
            for v in obj.data.vertices:
                wv = obj.matrix_world @ v.co
                xs.append(wv.x); ys.append(wv.y); zs.append(wv.z)
        return xs, ys, zs

    # Helper: check if any collision shape covers the given bounds on all 3 axes.
    def find_covering_collision(mesh_xs, mesh_ys, mesh_zs, tol=15.0):
        mbounds = (min(mesh_xs), max(mesh_xs), min(mesh_ys), max(mesh_ys),
                   min(mesh_zs), max(mesh_zs))
        for obj in coll_shapes:
            if not obj.data.vertices:
                continue
            cb = TTB.world_bounds(obj)
            if (cb[0] <= mbounds[1] + tol and cb[1] >= mbounds[0] - tol
                    and cb[2] <= mbounds[3] + tol and cb[3] >= mbounds[2] - tol
                    and cb[4] <= mbounds[5] + tol and cb[5] >= mbounds[4] - tol):
                return True
        return False

    # GearDoor: collision should cover child mesh bounds.
    gxs, gys, gzs = mesh_bounds("GearDoor")
    assert gzs, "GearDoor has child meshes"
    assert find_covering_collision(gxs, gys, gzs), \
        f"No collision covers GearDoor mesh z={min(gzs):.0f}..{max(gzs):.0f}"

    # VltGearKeySupport: collision should cover child mesh bounds.
    kxs, kys, kzs = mesh_bounds("VltGearKeySupport")
    assert kzs, "VltGearKeySupport has child meshes"
    assert find_covering_collision(kxs, kys, kzs), \
        f"No collision covers VltGearKeySupport mesh z={min(kzs):.0f}..{max(kzs):.0f}"


@TT.category('FO4', 'PHYSICS')
def TEST_FO4_COMPOUND_PHYSICS_ROUNDTRIP():
    """A single-body compound collision round-trips and stays loadable in game.

    The vanilla armor workbench's collision is one rigid body whose shape is an
    hknpDynamicCompoundShape of 36 convex polytopes (referenced by body_id 0),
    plus a hknpDynamicCompoundShapeData bounding-volume BVH tree. PyNifly used to
    flatten it to 36 sibling meshes and re-export it as 36 separate bodies with an
    unset body_id (0xFFFFFFFF) -> crash in bhkNPCollisionObject::CreateInstance.

    Import now groups the polytopes under a two-level bhkPhysicsSystem ->
    bhkCompound hierarchy (each child carrying its instance transform) for viewing,
    and stashes the original packfile. Export writes that packfile back verbatim
    and sets body_id -- so the collision (including the BVH tree the engine's
    updateAabb walks) is byte-identical to vanilla. Regenerating the tree from
    Blender geometry is future work (see TODO.md).
    """
    testfile = TTB.test_file(r"tests\FO4\WorkstationArmorB01.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_FO4_COMPOUND_PHYSICS_ROUNDTRIP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=False)

    system = bpy.data.objects['bhkPhysicsSystem']
    compound = bpy.data.objects['bhkCompound']
    assert TT.is_eq(compound.parent, system, "bhkCompound is under the physics system")
    assert compound.get('pynCollisionCompound'), "bhkCompound tagged as a compound body"
    kids = [o for o in bpy.data.objects if o.parent == compound]
    assert TT.is_eq(len(kids), 36, "compound groups 36 polytope children")

    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    try:
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    except RuntimeError as e:
        assert "unweighted vertices" in str(e), f"unexpected export error: {e}"

    src = pyn.NifFile(testfile)
    dst = pyn.NifFile(outfile)
    vco = src.nodes['WorkstationArmor'].collision_object
    eco = dst.nodes['WorkstationArmor'].collision_object

    assert TT.is_eq(eco.body_id, 0, "exported collision object body_id is 0 (not the crash sentinel)")

    # Preserved verbatim, so the physics packfile -- including the BVH tree the
    # engine walks in updateAabb -- is byte-identical to vanilla.
    assert TT.is_eq(eco.physics_system.data, vco.physics_system.data,
                    "exported physics packfile is byte-identical to vanilla")
    assert b'DynamicCompoundShapeData' in eco.physics_system.data, \
        "exported packfile keeps the compound bounding-volume tree"
    # The import's grouping empty is not a node (#450 8.3).
    assert TT.is_eq(set(dst.nodes) - set(src.nodes), set(), "no nodes added on export")

    # ---- a compound of COMPRESSED MESHES, not polytopes ----
    # DExtStands1x1Top01 is one body whose compound holds two compressed meshes.
    # The decoder only recognised polytope children, so this came through as two
    # loose meshes: nothing was tagged as a compound, the packfile was never
    # stashed, and export wrote two bodies where vanilla has one -- silently,
    # because every individual step looked reasonable.
    TTB.clear_all()
    cmfile = TTB.test_file(
        r"tests\FO4\Meshes\Architecture\DiamondCity\DExt\DExtStands1x1Top01.nif")
    cmout = TTB.test_file(r"tests\Out\TEST_FO4_COMPOUND_PHYSICS_ROUNDTRIP_CM.nif")

    bpy.ops.import_scene.pynifly(filepath=cmfile, import_animations=False)
    cm_compound = bpy.data.objects['bhkCompound']
    assert cm_compound.get('pynCollisionCompound'), \
        "a compound of compressed meshes is tagged as a compound body"
    cm_kids = [o for o in bpy.data.objects if o.parent == cm_compound]
    assert TT.is_eq(len(cm_kids), 2, "compound groups its two compressed meshes")

    # Everything selected, as a modder exports: the collision empties are selected too.
    BD.ObjectSelect(list(bpy.data.objects), active=True)
    bpy.context.view_layer.objects.active = next(o for o in bpy.data.objects if 'pynRoot' in o)
    bpy.ops.export_scene.pynifly(filepath=cmout, target_game='FO4')

    cm_src = pyn.NifFile(cmfile)
    cm_dst = pyn.NifFile(cmout)
    src_ps = cm_src.nodes['DExtStands1x1Top01'].collision_object.physics_system
    dst_ps = cm_dst.nodes['DExtStands1x1Top01'].collision_object.physics_system
    assert TT.is_eq(dst_ps.data, src_ps.data,
                    "compound-of-mesh packfile is preserved byte for byte")
    assert TT.is_eq(set(cm_dst.nodes) - set(cm_src.nodes), set(), "no nodes added on export")


ELEVATOR = os.path.join(TT.FO4_ASSETS, r"Meshes\Interiors\Vault\Rooms\VltOutsideEntrance01.nif")
SAVED_SYSTEM_WARNING = "written as imported"


def _collision_nodes(path):
    """node name -> (body ID, physics system block id, system bytes)."""
    nif = pyn.NifFile(path)
    out = {}
    for n in nif.nodes.values():
        co = n.collision_object
        if co is not None and co.blockname == 'bhkNPCollisionObject':
            out[n.name] = (co.body_id, co.physics_system.id, bytes(co.physics_system.data))
    return out


def _export_all(outfile):
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = next(
        o for o in bpy.data.objects if 'pynRoot' in o)
    with captured_warnings() as w:
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    return [m for m in w.messages if SAVED_SYSTEM_WARNING in m]


@TT.category('FO4', 'PHYSICS')
@TT.expect_errors(("Could not find texture", "Unknown block type", SAVED_SYSTEM_WARNING))
def TEST_COLLISION_FO4_SAVED_SYSTEM():
    """A physics system holding a compound body is written once, for all its bodies,
    and an edit to any of them is reported, not dropped without a word (#444).

    The Vault 111 elevator room keeps one system with three bodies: a compound of two
    compressed meshes on the root, and loose bodies on rampdummy and Point01.  A
    compound can't be rebuilt yet (its bounding-volume tree), so the system is written
    from the bytes saved at import.  Export used to write the root that whole system
    and the other two bodies again in a second, rebuilt one -- bodies doubled -- and
    an edit to the compound was dropped silently.  304 vanilla systems mix a compound
    with other bodies this way (11-25).
    """
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_SAVED_SYSTEM.nif")
    vanilla = _collision_nodes(ELEVATOR)
    van_bytes = next(iter(vanilla.values()))[2]
    expect_ids = {n: v[0] for n, v in vanilla.items()}
    assert TT.is_eq(expect_ids, {'VltOutsideEntrance01': 0, 'rampdummy': 1, 'Point01': 2},
                    "vanilla: three nodes, one body each")

    def load():
        TTB.clear_all()
        bpy.ops.import_scene.pynifly(filepath=ELEVATOR, import_animations=False)
        compound = next(o for o in bpy.data.objects if o.get('pynCollisionCompound'))
        loose = {o.get('pynCollisionBodyID'): o for o in bpy.data.objects
                 if o.get('pynSavedSystem') and o.get('pynCollisionShapeType')
                 and o.parent is not compound}
        return compound, loose

    # ---- Unedited: one system, vanilla's bytes, every node at its own body ----
    compound, loose = load()
    key = compound.get('pynSavedSystem')
    assert TT.is_true(key, "the compound's system is marked as saved")
    assert TT.is_eq(sorted(loose), [1, 2], "the two loose bodies are found by body ID")
    assert TT.is_eq({o.get('pynSavedSystem') for o in loose.values()}, {key},
                    "the loose bodies carry the same system")
    warnings = _export_all(outfile)
    assert TT.is_eq(warnings, [], "no edit warning for an unedited system")
    out = _collision_nodes(outfile)
    assert TT.is_eq({n: v[0] for n, v in out.items()}, expect_ids,
                    "each node names its own body")
    assert TT.is_eq(len({v[1] for v in out.values()}), 1, "one physics system for all three")
    assert TT.is_true(next(iter(out.values()))[2] == van_bytes, "the system is vanilla's")

    # ---- An edited loose body is reported; the system stays as imported ----
    compound, loose = load()
    loose[2].data.vertices[0].co.z += 10.0
    warnings = _export_all(outfile)
    assert TT.is_eq(len(warnings), 1, "one warning for the edited loose body")
    assert TT.is_true(loose[2].name in warnings[0], "it names the edited object")
    out = _collision_nodes(outfile)
    assert TT.is_eq(len({v[1] for v in out.values()}), 1, "still one system")
    assert TT.is_true(next(iter(out.values()))[2] == van_bytes, "still vanilla's")

    # ---- An edited compound mesh is reported ----
    compound, loose = load()
    kid = sorted((o for o in bpy.data.objects if o.parent is compound),
                 key=lambda o: o.name)[0]
    kid.location.z += 50.0
    warnings = _export_all(outfile)
    assert TT.is_eq(len(warnings), 1, "one warning for the moved compound mesh")
    assert TT.is_true(kid.name in warnings[0], "it names the moved object")

    # ---- A deleted loose body is reported: the saved system still has it ----
    compound, loose = load()
    bpy.data.objects.remove(loose[1])
    warnings = _export_all(outfile)
    assert TT.is_eq(len(warnings), 1, "one warning for the deleted body")
    assert TT.is_true("body 1" in warnings[0], "it names the missing body")

    # ---- With the compound deleted, the rest is rebuilt from Blender ----
    compound, loose = load()
    for o in [o for o in bpy.data.objects if o.parent is compound] + [compound]:
        bpy.data.objects.remove(o)
    warnings = _export_all(outfile)
    assert TT.is_eq(warnings, [], "nothing saved is left to warn about")
    out = _collision_nodes(outfile)
    assert TT.is_eq(sorted(out), ['Point01', 'rampdummy'], "the loose bodies are written")
    assert TT.is_eq(len({v[1] for v in out.values()}), 1, "in one system")
    assert TT.is_true(b'hknpDynamicCompoundShape' not in out['Point01'][2],
                      "a rebuilt one, without the compound")


@TT.category('FO4', 'PHYSICS')
@TT.expect_errors(("Could not find texture", "Unknown block type", SAVED_SYSTEM_WARNING,
                   "physics constraints PyNifly can't read", "weren't both imported"))
def TEST_COLLISION_FO4_SAVED_SYSTEM_VARIETY():
    """Saved systems of other shapes than the elevator's round-trip unedited, with no
    edit warning: vanilla's bytes, one system, each node at its own body.

    Each one tripped the 11-25 check over the 304 vanilla systems that mix a compound
    with other bodies:
    - HitLgRmMidCorOut02DST: a compound with ONE child.  Import made no compound empty
      for it, so nothing was saved: the system was rebuilt, bodies renumbered, and
      the child's instance transform dropped.
    - Gurney01: sphere bodies (the centre is in the vertices, not on the object).
    - Jangles01: two compounds in one system, and a sphere no body owns.
    - ConstitutionLaunch01: compound meshes 3,000 units out, where matrix_local is
      1e-3 off (worked back from world matrices) -- the object's own transform isn't.
    - Workshop_WindmillGenerator01: a compound child whose float32 transform puts its
      points 4e-4 off at 250 units: transforms are compared, not placed points.
    - UtilityPole01: a body no node names, so import makes nothing for it.  That isn't
      a deletion.
    """
    for rel in (r"Meshes\Interiors\HighTech\LgRooms\HitLgRmMidCorOut02DST.nif",
                r"Meshes\SetDressing\Hospital\Gurney01.nif",
                r"Meshes\Props\StuffedAnimals\Jangles01.nif",
                r"Meshes\Effects\Quest\MS11\ConstitutionLaunch01.nif",
                r"Meshes\SetDressing\Workshop\Workshop_WindmillGenerator01.nif",
                r"Meshes\SetDressing\UtilityPoles\UtilityPole01.nif"):
        src = os.path.join(TT.FO4_ASSETS, rel)
        outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_SAVED_SYSTEM_VARIETY.nif")
        name = os.path.basename(rel)
        TTB.clear_all()
        bpy.ops.import_scene.pynifly(filepath=src, import_animations=False)
        warnings = _export_all(outfile)
        assert TT.is_eq(warnings, [], f"{name}: no edit warning")
        vanilla, out = _collision_nodes(src), _collision_nodes(outfile)
        assert TT.is_eq({n: v[0] for n, v in out.items()},
                        {n: v[0] for n, v in vanilla.items()}, f"{name}: body IDs")
        assert TT.is_eq(len({v[1] for v in out.values()}), 1, f"{name}: one system")
        assert TT.is_true(next(iter(out.values()))[2] == next(iter(vanilla.values()))[2],
                          f"{name}: vanilla's system")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_VAULT_SHELF():
    """FO4 bhkPhysicsSystem: single compressed_mesh whose bounds match the visual mesh.

    Vault_Shelf_02.nif has a bhkNPCollisionObject on the root node whose
    bhkPhysicsSystem stores a single hknpCompressedMeshShape.  The shape's
    AABB and vertices are already in world space — the Havok body transform
    (z ≈ 0.73 Havok units ≈ 51 Blender units) is the centre-of-mass position
    and must NOT be added to the vertices a second time.

    Expected import result:
      - One compressed_mesh collision object named bhkPhysicsSystem.
      - Its world-space bounds are within 5 Blender units of the visual mesh
        bounds on every axis (the shelf spans ≈ ±74 x, ±39 y, 0..113 z).

    Expected export/round-trip:
      - Collision is preserved after export → reimport with the same bounds.
    """
    testfile = TTB.test_file(r"tests\FO4\Meshes\Vault_Shelf_02.nif")
    outfile  = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_VAULT_SHELF.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    cm_shapes = [o for o in physics_shapes
                 if o.get('pynCollisionShapeType') == 'compressed_mesh']
    assert TT.is_eq(len(cm_shapes), 1, "One compressed_mesh shape imported")

    coll_obj = cm_shapes[0]

    # Visual mesh — use the larger of the two mesh objects (the shelf body)
    mesh_obj = bpy.data.objects.get('Vault_Shelf_02:1 - L2_Vault_Shelf_02:1')
    assert TT.is_neq(mesh_obj, None, "Visual mesh Vault_Shelf_02:1 - L2_Vault_Shelf_02:1 exists")

    mesh_bounds = TTB.world_bounds(mesh_obj)
    coll_bounds = TTB.world_bounds(coll_obj)
    TTB.assert_bounds_close(coll_bounds, mesh_bounds, 5.0, "Collision vs mesh")

    # ---- Export and round-trip verify ----------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    chk_cm = [o for o in chk_shapes if o.get('pynCollisionShapeType') == 'compressed_mesh']
    assert TT.is_eq(len(chk_cm), 1, "Round-trip preserves compressed_mesh shape")

    chk_mesh = [o for o in bpy.data.objects if o.name.startswith('Vault_Shelf_02')]
    chk_mesh = [o for o in chk_mesh if o.type == 'MESH' and not o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_gt(len(chk_mesh), 0, "Round-trip preserves visual mesh")

    rt_coll = chk_cm[0]
    rt_mesh = max(chk_mesh, key=lambda o: len(o.data.vertices))
    *_, rc_zmin, rc_zmax = TTB.world_bounds(rt_coll)
    *_, rm_zmin, rm_zmax = TTB.world_bounds(rt_mesh)
    assert TT.is_lt(abs(rc_zmin - rm_zmin), 5.0, "Round-trip collision z-min close to mesh z-min")
    assert TT.is_lt(abs(rc_zmax - rm_zmax), 5.0, "Round-trip collision z-max close to mesh z-max")


@TT.category('FO4', 'PHYSICS')
@TT.expect_errors( ("Could not find texture",
                    "Could not load normal texture",
                    "Could not load diffuse texture",
                    "Could not find materials file",))
def TEST_COLLISION_FO4_CANDLE_BOTTLE():
    """FO4 bhkPhysicsSystem: standalone polytope with world-space vertices.

    CandleBottleLit01.nif has a single standalone convex polytope (no compound
    wrapper).  The BodyCInfo position equals the vertex centroid, meaning the
    verts are stored in world space and the body transform must NOT be applied.

    The visual mesh sits on the z=0 plane (Z: 0..29 BU).  The collision must
    sit in the same region, not shifted upward by the body COM offset.
    """
    testfile = TTB.test_file(r"tests\FO4\Meshes\CandleBottleLit01.nif")
    outfile  = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_CANDLE_BOTTLE.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_eq(len(physics_shapes), 1, "One collision shape imported")

    coll_obj = physics_shapes[0]
    assert TT.is_eq(coll_obj.get('pynCollisionShapeType'), 'polytope',
                     "Shape is a polytope")

    mesh_obj = bpy.data.objects.get('CandleBottle01:0')
    assert TT.is_neq(mesh_obj, None, "Visual mesh CandleBottle01:0 exists")

    _, _, _, _, mz0, mz1 = TTB.world_bounds(mesh_obj)
    _, _, _, _, cz0, cz1 = TTB.world_bounds(coll_obj)

    # Collision z-min must be near the mesh z-min (both near z=0).
    assert TT.is_lt(abs(cz0 - mz0), 5.0, "Collision z-min near mesh z-min")
    # Collision z-max must be near the mesh z-max (~29 BU), not shifted up.
    assert TT.is_lt(abs(cz1 - mz1), 5.0, "Collision z-max near mesh z-max")

    # Flame:0 has an alpha property with alpha_test=False but threshold=128.
    # The threshold must survive the round-trip even when alpha_test is off.
    flame_obj = bpy.data.objects.get('Flame:0')
    assert TT.is_neq(flame_obj, None, "Flame:0 exists")
    flame_mat = flame_obj.data.materials[0]
    assert TT.is_eq(flame_mat['NiAlphaProperty_threshold'], 128,
                     "Flame:0 alpha threshold imported as 128")

    # ---- Export and round-trip verify ----------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_gt(len(chk_shapes), 0, "Round-trip preserves collision shape")
    _, _, _, _, rz0, rz1 = TTB.world_bounds(chk_shapes[0])
    assert TT.is_lt(abs(rz0 - mz0), 5.0, "Round-trip collision z-min near mesh z-min")

    # Check Flame:0 alpha threshold survived the round-trip.
    chk_flame = bpy.data.objects.get('Flame:0')
    assert TT.is_neq(chk_flame, None, "Flame:0 exists after round-trip")
    chk_mat = chk_flame.data.materials[0]
    assert TT.is_eq(chk_mat['NiAlphaProperty_threshold'], 128,
                     "Flame:0 alpha threshold preserved after round-trip")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_POOLBALL():
    """FO4 bhkPhysicsSystem: sphere collision shape import, export, round-trip."""
    testfile = TTB.test_file(r"tests\FO4\Meshes\Poolball_Cue.nif")
    outfile  = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_POOLBALL.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # A sphere collision shape should be created.
    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_eq(len(physics_shapes), 1, "One collision shape imported")

    coll_obj = physics_shapes[0]
    assert TT.is_eq(coll_obj.get('pynCollisionShapeType'), 'sphere',
                     "Shape is a sphere")
    assert TT.is_eq(coll_obj.rigid_body.collision_shape, 'CONVEX_HULL',
                     "Rigid body collision shape is CONVEX_HULL")

    # Sphere mesh dimensions encode the radius; check it's reasonable.
    orig_dim = max(coll_obj.dimensions)
    assert TT.is_gt(orig_dim, 0.1, "Sphere collision mesh has positive size")

    # Visual mesh should exist.
    mesh_obj = bpy.data.objects.get('Poolball_Cue:0')
    assert TT.is_neq(mesh_obj, None, "Visual mesh Poolball_Cue:0 exists")

    # ---- Export and round-trip verify ----------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_eq(len(chk_shapes), 1, "Round-trip preserves one collision shape")

    chk_obj = chk_shapes[0]
    assert TT.is_eq(chk_obj.get('pynCollisionShapeType'), 'sphere',
                     "Round-trip shape is still a sphere")

    chk_dim = max(chk_obj.dimensions)
    assert TT.is_equiv(chk_dim, orig_dim,
                        "Sphere size preserved after round-trip")

    # bodyID indexes the physics system's body array. It defaults to a sentinel,
    # and every FO4 collision we exported was keeping that default -- the engine
    # then indexes the body array with 0xFFFFFFFF and writes through whatever it
    # lands on, in bhkNPCollisionObject::CreateInstance, while loading the cell.
    out_nif = pyn.NifFile(outfile)
    for name, node in out_nif.nodes.items():
        co = node.collision_object
        if co is None or co.blockname != 'bhkNPCollisionObject':
            continue
        assert TT.is_neq(co.body_id, 0xFFFFFFFF,
                         f"exported collision on {name} names a real body")


@TT.category('FO4', 'PHYSICS')
# DiamondBulkhead01 references a cubemap the test texture tree doesn't carry.
@TT.expect_errors( ("Could not find texture", ) )
def TEST_COLLISION_FO4_PHYSICS_SYSTEM():
    """FO4 bhkNPCollisionObject: import, export from mesh geometry, reimport and verify"""
    testfile = TTB.test_file(r"tests\FO4\InsFloorMat01.nif")
    outfile  = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_PHYSICS_SYSTEM.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # The root node's bhkNPCollisionObject should produce a bhkPhysicsSystem mesh
    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_gt(len(physics_shapes), 0, "bhkPhysicsSystem collision mesh was imported")

    ps_obj = physics_shapes[0]
    assert TT.is_eq(ps_obj.type, 'MESH', "Collision object is a mesh")
    assert TT.is_gt(len(ps_obj.data.vertices), 0, "Collision mesh has vertices")
    assert TT.is_gt(len(ps_obj.data.polygons), 0, "Collision mesh has polygons")
    assert TT.is_eq(ps_obj.display_type, 'WIRE', "Collision mesh displayed as wire")
    assert TT.is_eq(ps_obj['pynRigidBody'], 'bhkPhysicsSystem', "Collision mesh tagged as bhkPhysicsSystem")

    orig_nvert = len(ps_obj.data.vertices)
    orig_npoly = len(ps_obj.data.polygons)
    orig_xs = [(ps_obj.matrix_world @ v.co).x for v in ps_obj.data.vertices]
    orig_ys = [(ps_obj.matrix_world @ v.co).y for v in ps_obj.data.vertices]
    orig_zs = [(ps_obj.matrix_world @ v.co).z for v in ps_obj.data.vertices]

    assert TT.is_lt(min(orig_xs), 0, "Collision mesh extends past origin on negative x")
    assert TT.is_gt(max(orig_xs), 0, "Collision mesh extends past origin on positive x")
    height = max(orig_zs) - min(orig_zs)
    assert TT.is_gt(height, 0.5, "Collision mesh height greater than 0.5")
    assert TT.is_lt(height, 1.0, "Collision mesh height less than 1.0")

    # Export everything; the exporter skips bhkPhysicsSystem objects as direct shapes
    # and exports them only through the constraint on the root.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # Reimport and verify the bhkPhysicsSystem geometry survived the round-trip
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_gt(len(chk_shapes), 0, "Exported nif has bhkPhysicsSystem collision mesh")

    chk = chk_shapes[0]
    assert TT.is_eq(len(chk.data.vertices), orig_nvert, "Vertex count preserved after export")
    assert TT.is_eq(len(chk.data.polygons), orig_npoly, "Polygon count preserved after export")

    chk_xs = [(chk.matrix_world @ v.co).x for v in chk.data.vertices]
    chk_ys = [(chk.matrix_world @ v.co).y for v in chk.data.vertices]
    chk_zs = [(chk.matrix_world @ v.co).z for v in chk.data.vertices]
    assert TT.is_equiv(min(chk_xs), min(orig_xs), "X min preserved", e=0.1)
    assert TT.is_equiv(max(chk_xs), max(orig_xs), "X max preserved", e=0.1)
    assert TT.is_equiv(min(chk_ys), min(orig_ys), "Y min preserved", e=0.1)
    assert TT.is_equiv(max(chk_ys), max(orig_ys), "Y max preserved", e=0.1)
    assert TT.is_equiv(min(chk_zs), min(orig_zs), "Z min preserved", e=0.1)
    assert TT.is_equiv(max(chk_zs), max(orig_zs), "Z max preserved", e=0.1)

    # ---- a body stays where its node puts it ----
    # A body's shape verts are in its node's space, so a node with a non-zero
    # transform places them.  Exporting verts in world space instead left the
    # node to transform them a second time, throwing the collision off by the
    # node's translation -- up to 1700 units on DiamondRichBase01's buildings,
    # far enough that the collision was simply somewhere else.
    TTB.clear_all()
    rbfile = TTB.test_file(
        r"tests\FO4\Meshes\Architecture\DiamondCity\Stadium_Ext\DiamondRichBase01.nif")
    rbout = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_PLACEMENT.nif")

    srcnif = pyn.NifFile(rbfile)
    src_bounds = _np_body_world_bounds(srcnif)
    offset_nodes = [n for n in src_bounds
                    if max(abs(x) for x in srcnif.nodes[n].global_transform.translation) > 1.0]
    assert TT.is_gt(len(offset_nodes), 0, "fixture has collision on offset nodes")

    bpy.ops.import_scene.pynifly(filepath=rbfile)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=rbout, target_game='FO4')

    out_bounds = _np_body_world_bounds(pyn.NifFile(rbout))
    assert TT.is_eq(sorted(out_bounds), sorted(src_bounds),
                    "every collision body comes back")
    for n, (lo, hi) in src_bounds.items():
        olo, ohi = out_bounds[n]
        assert TT.is_lt((olo - lo).length, 2.0, f"{n} collision keeps its position")
        assert TT.is_lt((ohi - hi).length, 2.0, f"{n} collision keeps its extent")

    # ---- a body keeps what it collides with ----
    # collisionFilterInfo picks the body's collision layer.  Nothing in Blender
    # held it, so export wrote 1 (static) on every body: DiamondShack04's
    # entrance stairs came back on the wrong layer.
    TTB.clear_all()
    fifile = TTB.test_file(
        r"tests\FO4\Meshes\Architecture\DiamondCity\ShackRV_Ext\DiamondShack04.nif")
    fiout = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_FILTER.nif")

    src_filters = _np_body_filters(pyn.NifFile(fifile))
    assert TT.is_eq(sorted(src_filters.values()), [1, 31],
                    "fixture has a body on a non-default collision layer")

    bpy.ops.import_scene.pynifly(filepath=fifile)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=fiout, target_game='FO4')

    assert TT.is_eq(_np_body_filters(pyn.NifFile(fiout)), src_filters,
                    "every body keeps its collision filter")

    # ---- back faces survive the round trip ----
    # A collision surface is made solid from both sides by carrying the same
    # triangle twice, wound opposite ways.  Blender cannot hold two faces on one
    # set of vertex indices whatever the winding, and import used to drop the
    # second -- turning a two-sided wall one-sided, silently.  Import now gives
    # the repeat its own copy of the vertices, so the count comes back whole.
    # DiamondBulkhead01: 16 collision triangles, 8 of them the reverse of another.
    TTB.clear_all()
    bkfile = TTB.test_file(
        r"tests\FO4\Meshes\Architecture\DiamondCity\Stadium_Ext\DiamondBulkhead01.nif")
    bkout = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_BACKFACES.nif")

    src_tris = len(pyn.NifFile(bkfile).nodes['DiamondBulkhead01']
                   .collision_object.physics_system.geometry[0].faces)
    assert TT.is_eq(src_tris, 16, "vanilla collision has 16 triangles")

    bpy.ops.import_scene.pynifly(filepath=bkfile)
    bk = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')][0]
    assert TT.is_eq(len(bk.data.polygons), 16,
                    "every collision triangle survives import, back faces included")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=bkout, target_game='FO4')
    out_tris = len(pyn.NifFile(bkout).nodes['DiamondBulkhead01']
                   .collision_object.physics_system.geometry[0].faces)
    assert TT.is_eq(out_tris, 16, "and they are all exported again")


LUNCHBOX_DEST = os.path.join(TT.FO4_ASSETS, r"Meshes\SetDressing\LunchBoxKids\LunchBoxKids01Dest.nif")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_SHAPE_HEADERS():
    """FO4 collision shapes keep their own material, flags and convex radius.

    Export wrote one template header on every shape: Plastic, flags 0x0103 and radius
    0.01.  LunchBoxKids01Dest's three pieces are MetalLight, flags 0x0143 (the 0x40 bit
    keeps them from sinking into floors), and three different radii.  In game the
    re-exported lunchbox sounded like plastic, sank and jittered.

    Import shows each shape's material by name and its flags; export writes them back.
    A material typed in Blender is exported as its CRC, and a shape with none set gets
    Metal and vanilla's usual flags.

    Also checks the motion properties' deactivation bytes, which were exported as zeros
    (pieces froze in mid-air).
    """
    from io_scene_nifly.pyn.fo4_havok_materials import material_id
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_SHAPE_HEADERS.nif")
    vanilla = pyn.NifFile(LUNCHBOX_DEST)
    van_hdrs = _np_shape_headers(vanilla)
    assert TT.is_eq(sorted(van_hdrs), ['Bone001', 'Bone003', 'Bone004'], "three bodies")
    assert TT.is_eq(set(_np_motion_tails(vanilla)), {"ff 67 9b 99 04 73 75 06 73 00 00 00"},
                    "vanilla deactivation bytes")

    bpy.ops.import_scene.pynifly(filepath=LUNCHBOX_DEST)
    shapes = {o.name: o for o in bpy.data.objects if o.get('pynRigidBody') == 'bhkPhysicsSystem'}
    assert TT.is_eq(len(shapes), 3, "three collision shapes")
    for o in shapes.values():
        assert TT.is_eq(o.pyn_collshape.bhkMaterial, "MetalLight", f"{o.name} material by name")
        assert TT.is_eq(o.pyn_fo4phys.shape_flags, "143", f"{o.name} flags")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = pyn.NifFile(outfile)
    assert TT.is_eq(_np_shape_headers(out), van_hdrs, "every shape's header round-trips")
    assert TT.is_eq(set(_np_motion_tails(out)), {"ff 67 9b 99 04 73 75 06 73 00 00 00"},
                    "deactivation bytes exported")

    # Edited in Blender: one shape made Wood, one with nothing set.
    bone_of = {c.target.name: pb.name
               for arma in bpy.data.objects if arma.type == 'ARMATURE'
               for pb in arma.pose.bones for c in pb.constraints if c.type == 'COPY_TRANSFORMS'}
    by_bone = {bone_of[n]: o for n, o in shapes.items()}
    by_bone['Bone001'].pyn_collshape.bhkMaterial = "Wood"
    by_bone['Bone004'].pyn_collshape.bhkMaterial = ""
    by_bone['Bone004'].pyn_fo4phys.shape_flags = ""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    hdrs = _np_shape_headers(pyn.NifFile(outfile))
    assert TT.is_eq(hdrs['Bone001'][:2], (0x0143, material_id("Wood")), "material set in Blender")
    assert TT.is_eq(hdrs['Bone004'][:2], (0x0143, material_id("Metal")), "nothing set: Metal")
    assert TT.is_eq(hdrs['Bone003'], van_hdrs['Bone003'], "untouched shape unchanged")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_UNWEIGHTED_BONE():
    """A bone that owns a collision is exported even when nothing is weighted to it.

    Export looked for the collision's bone among the nodes already written, and a bone
    with no weights never was: KeyError 'Bone003' (Discord report D2).  Here the
    lunchbox's Bone003 weights are moved to Bone001 and only the mesh is exported.
    """
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_UNWEIGHTED_BONE.nif")
    bpy.ops.import_scene.pynifly(filepath=LUNCHBOX_DEST)
    mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Bone003' in o.vertex_groups][0]
    g3, g1 = mesh.vertex_groups['Bone003'], mesh.vertex_groups['Bone001']
    for v in mesh.data.vertices:
        for g in v.groups:
            if g.group == g3.index:
                g1.add([v.index], g.weight, 'ADD')
    mesh.vertex_groups.remove(g3)

    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    out = pyn.NifFile(outfile)
    assert TT.is_true('Bone003' in out.nodes, "Bone003 written")
    assert TT.is_eq(sorted(_np_shape_headers(out)), ['Bone001', 'Bone003', 'Bone004'],
                    "every bone keeps its collision")
    assert TT.is_true('Bone003' not in out.shapes[0].bone_names, "Bone003 is not in the skin")


FLOORLIGHT = os.path.join(TT.FO4_ASSETS, r"Meshes\SetDressing\HighTech\HighTechLightFloor02.nif")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_CAPSULE():
    """FO4 capsule collision imports as a capsule mesh and exports as the same capsule.

    HighTechLightFloor02's only collision is an hknpCapsuleShape, which neither import
    nor export knew: the light came out with no collision at all (report C2).  The
    capsule mesh is the authority on export: its ends and radius are read off it.
    """
    from io_scene_nifly.pyn.nifconstants import game_collision_sf
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_CAPSULE.nif")
    van = _np_bodies(pyn.NifFile(FLOORLIGHT))
    assert TT.is_eq([s.shape_type for s in van.values()], ['capsule'], "vanilla: one capsule")
    vcap = list(van.values())[0]

    bpy.ops.import_scene.pynifly(filepath=FLOORLIGHT)
    caps = [o for o in bpy.data.objects if o.get('pynCollisionShapeType') == 'capsule']
    assert TT.is_eq(len(caps), 1, "one capsule object")
    sf = HAVOC_SCALE_FACTOR * game_collision_sf['FO4']
    zs = [(caps[0].matrix_world @ v.co).z for v in caps[0].data.vertices]
    top = max(vcap.capsule_ends[0][2], vcap.capsule_ends[1][2]) + vcap.convex_radius
    assert TT.is_equiv(max(zs), top * sf, "capsule reaches its top", e=0.01)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = _np_bodies(pyn.NifFile(outfile))
    assert TT.is_eq(sorted(out), sorted(van), "the capsule's node keeps its collision")
    ocap = list(out.values())[0]
    assert TT.is_eq(ocap.shape_type, 'capsule', "exported as a capsule")
    assert TT.is_equiv(ocap.convex_radius, vcap.convex_radius, "radius", e=1e-4)
    # The mesh doesn't say which end is a; the capsule is the same either way.
    for k, (o, v) in enumerate(zip(sorted(ocap.capsule_ends), sorted(vcap.capsule_ends))):
        for j in range(3):
            assert TT.is_equiv(o[j], v[j], f"end {k}", e=1e-4)
    assert TT.is_eq((ocap.shape_flags, ocap.user_data), (vcap.shape_flags, vcap.user_data),
                    "flags and material")


@TT.category('FO4', 'PHYSICS')
@TT.expect_errors(("hknpConvexShape", "isn't supported"))
def TEST_COLLISION_FO4_UNSUPPORTED_SHAPE():
    """A collision shape PyNifly can't handle is reported, not silently dropped.

    DecoMainA1x1WinC01's collision is a plain hknpConvexShape, which import doesn't read:
    it warns, naming the type.  On export, a shape object of a type export doesn't know
    warns too, and the rest of the nif is still written.
    """
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_UNSUPPORTED_SHAPE.nif")
    with captured_warnings() as w:
        bpy.ops.import_scene.pynifly(filepath=os.path.join(
            TT.FO4_ASSETS, r"Meshes\Architecture\Buildings\DecoKit\DecoMainA1x1WinC01.nif"))
    assert TT.is_true(any("hknpConvexShape" in m for m in w.messages),
                      "import names the shape type it can't read")

    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=FLOORLIGHT)
    cap = [o for o in bpy.data.objects if o.get('pynCollisionShapeType') == 'capsule'][0]
    cap['pynCollisionShapeType'] = 'cylinder'
    bpy.ops.object.select_all(action='SELECT')
    with captured_warnings() as w:
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    assert TT.is_true(any("cylinder" in m for m in w.messages), "export names it too")
    assert TT.is_gt(len(pyn.NifFile(outfile).shapes), 0, "the rest of the nif is written")


def _canon_loop(f):
    """A face loop rotated to start at its smallest index (winding kept)."""
    f = list(f)
    k = f.index(min(f))
    return tuple(f[k:] + f[:k])


def _hull_ok(s):
    """Every vertex of a polytope lies on or inside every face's plane."""
    for f in s.faces:
        p = [s.verts[i] for i in f]
        n = Vector((0, 0, 0))
        for k in range(len(p)):
            a, b = Vector(p[k]), Vector(p[(k + 1) % len(p)])
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x),
                         (a.x - b.x) * (a.y + b.y)))
        n.normalize()
        top = max(n.dot(Vector(v)) for v in p)
        if any(n.dot(Vector(v)) > top + 1e-5 for v in s.verts):
            return False
    return True


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_HULL():
    """FO4 polytopes are written as hulls, the way vanilla writes them.

    LunchBoxKids01Dest's three pieces are boxes: 6 quads each.  Import used to fan
    every face into triangles, and export wrote whatever the mesh held -- a box came
    back as 12 triangles, each with its own plane and a minHalfAngle of 0, and the
    pieces jittered and sank (Discord report D7).

    - Import keeps the quads, and no padding vertices.
    - Export of the untouched boxes gives back vanilla's faces.
    - A box triangulated in Blender is written as 6 quads again.
    - A box with a corner pushed in is written as the hull of its vertices: the dented
      corner left out, every vertex inside every plane.
    """
    import bmesh
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_HULL.nif")
    van = _np_bodies(pyn.NifFile(LUNCHBOX_DEST))
    van_faces = {k: sorted(map(_canon_loop, s.faces)) for k, s in van.items()}

    bpy.ops.import_scene.pynifly(filepath=LUNCHBOX_DEST)
    shapes = {o.name: o for o in bpy.data.objects if o.get('pynRigidBody') == 'bhkPhysicsSystem'}
    assert TT.is_eq(len(shapes), 3, "three collision shapes")
    for o in shapes.values():
        assert TT.is_eq(sorted(len(p.vertices) for p in o.data.polygons), [4] * 6,
                        f"{o.name}: imported as 6 quads")
        assert TT.is_eq(len(o.data.vertices), 8, f"{o.name}: 8 vertices, no padding")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = _np_bodies(pyn.NifFile(outfile))
    for k, s in out.items():
        assert TT.is_eq(sorted(map(_canon_loop, s.faces)), van_faces[k], f"{k}: vanilla's faces")
        assert TT.is_lt(max(math.dist(a, b) for a, b in zip(s.verts, van[k].verts)), 1e-4,
                        f"{k}: vanilla's vertices")

    bone_of = {c.target.name: pb.name
               for arma in bpy.data.objects if arma.type == 'ARMATURE'
               for pb in arma.pose.bones for c in pb.constraints if c.type == 'COPY_TRANSFORMS'}
    by_bone = {bone_of[n]: o for n, o in shapes.items()}

    bm = bmesh.new()
    bm.from_mesh(by_bone['Bone001'].data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(by_bone['Bone001'].data)
    bm.free()
    assert TT.is_eq(len(by_bone['Bone001'].data.polygons), 12, "Bone001 triangulated")

    dented = by_bone['Bone003'].data
    centre = sum((v.co for v in dented.vertices), Vector()) / len(dented.vertices)
    # Past 2/3 of the way in, the corner is inside the plane through its neighbours.
    dented.vertices[0].co = dented.vertices[0].co.lerp(centre, 0.8)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = _np_bodies(pyn.NifFile(outfile))
    assert TT.is_eq(sorted(map(_canon_loop, out['Bone001'].faces)), van_faces['Bone001'],
                    "triangulated box: 6 quads again")
    d = out['Bone003']
    assert TT.is_eq(len(d.verts), 7, "dented box: the dented corner is left out")
    assert TT.is_eq(sorted(len(f) for f in d.faces), [3, 3, 3, 3, 4, 4, 4],
                    "dented box: 3 whole sides, 3 cut, and the cut corner")
    assert TT.is_true(_hull_ok(d), "dented box: every vertex inside every plane")
    assert TT.is_eq(sorted(map(_canon_loop, out['Bone004'].faces)), van_faces['Bone004'],
                    "untouched box unchanged")


def _np_mass(nif):
    """Each native-physics body's mass data (TT.havok_mass_data), keyed by node name."""
    out = {}
    for name, node in nif.nodes.items():
        co = node.collision_object
        if co is None or co.blockname != 'bhkNPCollisionObject' or co.physics_system is None:
            continue
        out[name] = TT.havok_mass_data(co.physics_system.data)[co.body_id]
    return out


def _check_motion_follows_shape(m, label):
    """The motion record agrees with the shape's mass record and the body's pose."""
    from pyn import mass_props as MP
    mo, ms = m['motion'], m['msp']
    want = tuple(p + x for p, x in zip(m['pos'], MP.mat_vec(MP.quat_to_matrix(m['quat']),
                                                             ms['com'])))
    assert TT.is_equiv(mo['com'], want, f"{label}: centre of mass in the world", e=1e-4)
    mass = 1 / mo['inv_mass']
    assert TT.is_equiv(mo['mass_factor'], mass / ms['volume'], f"{label}: mass factor",
                       e=1e-4 * mo['mass_factor'])


PIPBOY = os.path.join(TT.FO4_ASSETS, r"Meshes\AnimObjects\PipBoy.nif")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_MASS():
    """FO4 mass data is worked out from the collision shape on export.

    Vanilla's centre of mass and inertia are pure geometry -- the hull pushed out by
    its convex radius, inertia 1.5 times the solid's -- so export computes them rather
    than writing a stock record (Discord report D3: pieces pivoted about the model's
    origin and rocked after landing) or carrying the import's numbers along.

    - The lunchbox's pieces import as Active rigid bodies of mass 5.
    - Untouched, they export with vanilla's mass data.
    - Moving a piece's collision moves its centre of mass with it, inertia unchanged.
    - Making a piece bigger gives it more volume and inertia.
    - A keyframed body (the PipBoy) imports as Animated and exports keyframed.
    """
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_MASS.nif")
    van = _np_mass(pyn.NifFile(LUNCHBOX_DEST))
    van_geo = _np_bodies(pyn.NifFile(LUNCHBOX_DEST))

    bpy.ops.import_scene.pynifly(filepath=LUNCHBOX_DEST)
    shapes = {o.name: o for o in bpy.data.objects if o.get('pynRigidBody') == 'bhkPhysicsSystem'}
    for o in shapes.values():
        assert TT.is_eq(o.rigid_body.type, 'ACTIVE', f"{o.name}: dynamic")
        assert TT.is_eq(o.rigid_body.kinematic, False, f"{o.name}: not keyframed")
        assert TT.is_equiv(o.rigid_body.mass, 5.0, f"{o.name}: mass", e=1e-4)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = _np_mass(pyn.NifFile(outfile))
    assert TT.is_eq(set(out), set(van), "the same bodies")
    for k, m in out.items():
        v = van[k]
        assert TT.is_equiv(m['msp']['volume'], v['msp']['volume'], f"{k}: volume",
                           e=1e-3 * v['msp']['volume'])
        assert TT.is_equiv(m['msp']['com'], v['msp']['com'], f"{k}: centre of mass", e=1e-4)
        assert TT.is_lt(TT.rel_err(TT.mass_tensor(m['msp']['moments'], m['msp']['axes']),
                                   TT.mass_tensor(v['msp']['moments'], v['msp']['axes'])),
                        1e-3, f"{k}: inertia")
        assert TT.is_equiv(m['motion']['inv_mass'], 0.2, f"{k}: inverse mass", e=1e-6)
        _check_motion_follows_shape(m, k)

    bone_of = {c.target.name: pb.name
               for arma in bpy.data.objects if arma.type == 'ARMATURE'
               for pb in arma.pose.bones for c in pb.constraints if c.type == 'COPY_TRANSFORMS'}
    by_bone = {bone_of[n]: o for n, o in shapes.items()}

    # Move Bone003's collision 0.1 Havok units along its own x; double Bone004's.
    moved = by_bone['Bone003'].data
    step = Vector((0.1 * HAVOC_SCALE_FACTOR, 0, 0))
    for vx in moved.vertices:
        vx.co += step
    grown = by_bone['Bone004'].data
    centre = sum((vx.co for vx in grown.vertices), Vector()) / len(grown.vertices)
    for vx in grown.vertices:
        vx.co = centre + (vx.co - centre) * 2

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = _np_mass(pyn.NifFile(outfile))
    geo = _np_bodies(pyn.NifFile(outfile))
    for k, m in out.items():
        _check_motion_follows_shape(m, k)

    shift = [a - b for a, b in zip(geo['Bone003'].verts[0], van_geo['Bone003'].verts[0])]
    assert TT.is_gt(max(map(abs, shift)), 0.05, "Bone003's shape moved")
    m, v = out['Bone003']['msp'], van['Bone003']['msp']
    assert TT.is_equiv(m['com'], [a + d for a, d in zip(v['com'], shift)],
                       "moved: centre of mass moved with it", e=1e-4)
    assert TT.is_equiv(m['volume'], v['volume'], "moved: same volume", e=1e-3 * v['volume'])
    assert TT.is_lt(TT.rel_err(TT.mass_tensor(m['moments'], m['axes']),
                               TT.mass_tensor(v['moments'], v['axes'])), 1e-3,
                    "moved: same inertia")

    m, v = out['Bone004']['msp'], van['Bone004']['msp']
    assert TT.is_gt(m['volume'], 4 * v['volume'], "doubled: more than 4x the volume")
    assert TT.is_gt(max(m['moments']), 16 * max(v['moments']),
                    "doubled: more than 16x the inertia")

    m, v = out['Bone001']['msp'], van['Bone001']['msp']
    assert TT.is_equiv(m['volume'], v['volume'], "untouched piece unchanged",
                       e=1e-3 * v['volume'])

    # Keyframed.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    van = _np_mass(pyn.NifFile(PIPBOY))
    assert TT.is_eq([m['motion']['inv_mass'] for m in van.values()], [0.0],
                    "vanilla PipBoy: one keyframed body")
    bpy.ops.import_scene.pynifly(filepath=PIPBOY)
    shapes = [o for o in bpy.data.objects if o.get('pynRigidBody') == 'bhkPhysicsSystem']
    assert TT.is_eq(len(shapes), 1, "PipBoy: one collision shape")
    assert TT.is_eq(shapes[0].rigid_body.type, 'ACTIVE', "PipBoy: Active")
    assert TT.is_eq(shapes[0].rigid_body.kinematic, True, "PipBoy: Animated")
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_MASS_pipboy.nif")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = list(_np_mass(pyn.NifFile(outfile)).values())
    assert TT.is_eq(len(out), 1, "PipBoy: one body")
    mo = out[0]['motion']
    assert TT.is_eq((mo['inv_mass'], mo['mass_factor'], mo['inv_inertia'], mo['props_id']),
                    (0.0, 1.0, (0.0, 0.0, 0.0, 0.0), 0xFFFF), "PipBoy: keyframed")


def _np_systems(nif):
    """{node name: (system block id, body id)} for every native-physics node."""
    return {name: (n.collision_object.physics_system.id, n.collision_object.body_id)
            for name, n in nif.nodes.items()
            if n.collision_object and n.collision_object.blockname == 'bhkNPCollisionObject'
            and n.collision_object.physics_system}


def _np_hinges(nif):
    """The hinges of a nif's one physics system, as world frames keyed by the node
    names of their bodies: {(node A, node B): (pivot, axis, limits, friction)}, in
    Havok units.  The frames are A's, placed by A's node."""
    from io_scene_nifly.pyn.bhk_autounpack import parse_constraints
    sysids = {s for s, _ in _np_systems(nif).values()}
    assert TT.is_eq(len(sysids), 1, "one physics system")
    node_of = {b: name for name, (_, b) in _np_systems(nif).items()}
    ps = next(n.collision_object.physics_system for n in nif.nodes.values()
              if n.collision_object and n.collision_object.blockname == 'bhkNPCollisionObject')
    hinges, others = parse_constraints(ps.data)
    out = {}
    for c in hinges:
        g = nif.nodes[node_of[c.body_a]].global_transform
        R = Matrix([g.rotation[0][:], g.rotation[1][:], g.rotation[2][:]])
        t = Vector(g.translation[:]) / HAVOC_SCALE_FACTOR
        pivot = R @ Vector(c.pivot_a) + t
        axis = R @ Vector([c.rot_a[i][0] for i in range(3)])
        out[(node_of[c.body_a], node_of[c.body_b])] = (pivot, axis.normalized(),
                                                       (c.min_angle, c.max_angle), c.friction)
    return out, others


def _check_hinges(got, want, label, limit_tol=0.02):
    assert TT.is_eq(set(got), set(want), f"{label}: hinged bodies")
    for k in want:
        gp, ga, gl, gf = got[k]
        wp, wa, wl, wf = want[k]
        assert TT.is_lt((gp - wp).length, 1e-4, f"{label} {k}: pivot")
        assert TT.is_gt(abs(ga.dot(wa)), 1 - 1e-5, f"{label} {k}: axis")
        assert TT.is_equiv(gl, wl, f"{label} {k}: limits", e=limit_tol)
        assert TT.is_equiv(gf, wf, f"{label} {k}: friction", e=1e-6)


def _bone_of_collision():
    """{collision object name: bone it drives}."""
    return {c.target.name: pb.name
            for arma in bpy.data.objects if arma.type == 'ARMATURE'
            for pb in arma.pose.bones for c in pb.constraints if c.type == 'COPY_TRANSFORMS'}


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_SPHERE_CENTRE():
    """A sphere whose centre is off its body's origin imports and exports in place.

    The Mr Handy skeleton's COM sphere is centred 0.0633 along its shape's x, and its
    body is turned -90 degrees about y, so the centre is 0.0633 above the body's
    position.  Import placed it at the body's position, and export (until 11-25)
    wrote a broken sphere -- the robot ignored bullets and hung the game on death.

    A non-human skeleton is its own reference skeleton: given as one, every node
    exports where vanilla has it.  (Left to the default human reference, bones the two
    share take the human's rest, and CharacterBumper moves.)

    - Import: the sphere mesh is centred at the body's position plus the turned centre.
    - Export: the centre of mass is vanilla's, and every node is where vanilla has it.
    """
    from io_scene_nifly.pyn import mass_props as MP
    from io_scene_nifly.pyn.bhk_autounpack import parse_bytes
    robot_skel = TTB.test_file(r"tests\FO4\RobotSkeleton.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_SPHERE_CENTRE.nif")
    van_nif = pyn.NifFile(robot_skel)
    van = parse_bytes(van_nif.nodes['COM'].collision_object.physics_system.data)[0]
    expect = [p + c for p, c in zip(van.transform.position,
                                    MP.mat_vec(MP.quat_to_matrix(van.transform.quaternion),
                                               van.sphere_center))]
    assert TT.is_equiv(expect, (0.0, 0.0, 1.1112), "vanilla's centre, worked out", e=1e-4)

    bpy.ops.import_scene.pynifly(filepath=robot_skel, reference_skel=robot_skel)
    [sph] = [o for o in bpy.data.objects if o.get('pynCollisionShapeType') == 'sphere']
    sf = max(sph.dimensions) / 2 / van.sphere_radius
    centre = sum((v.co for v in sph.data.vertices), Vector()) / len(sph.data.vertices) / sf
    assert TT.is_equiv(centre, expect, "sphere imported at its centre", e=1e-4)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = _np_mass(pyn.NifFile(outfile))
    van_mass = _np_mass(van_nif)
    assert TT.is_equiv(out['COM']['motion']['com'], van_mass['COM']['motion']['com'],
                       "centre of mass as vanilla's", e=1e-4)
    out_nif = pyn.NifFile(outfile)
    for name, node in van_nif.nodes.items():
        if name == van_nif.rootName:
            continue
        assert TT.is_equiv(out_nif.nodes[name].global_transform.translation[:],
                           node.global_transform.translation[:], f"{name} in place", e=1e-4)


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_BODY_FLAGS():
    """A trigger and a body's 0x10000 flag import as checkboxes and export as vanilla's.

    The Mr Handy skeleton's CharacterBumper is a trigger (material flags 0x200000,
    triggerType 2, body flags 0x10) and its COM body has flags 0x10080.  Export wrote
    0 for all of them, making the bumper a solid capsule inside the robot.

    - Import: the bumper's FO4 Physics "trigger" is on, the COM's "0x10000" is on.
    - Export: every body's flags and material flags are vanilla's.
    - Clearing COM's 0x10000 leaves 0x80, which export works out from it being moved
      by physics.
    """
    robot_skel = TTB.test_file(r"tests\FO4\RobotSkeleton.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_BODY_FLAGS.nif")
    van_nif = pyn.NifFile(robot_skel)
    van = {n: TT.havok_body_flags(van_nif.nodes[n].collision_object.physics_system.data)[0]
           for n in ('COM', 'CharacterBumper')}

    bpy.ops.import_scene.pynifly(filepath=robot_skel, reference_skel=robot_skel)
    by_bone = {b: bpy.data.objects[o] for o, b in _bone_of_collision().items()}
    com, bump = by_bone['COM'], by_bone['CharacterBumper']
    assert TT.is_eq((com.pyn_fo4phys.trigger, com.pyn_fo4phys.body_flag_10000),
                    (False, True), "COM: 0x10000, not a trigger")
    assert TT.is_eq((bump.pyn_fo4phys.trigger, bump.pyn_fo4phys.body_flag_10000),
                    (True, False), "bumper: a trigger")

    def exported():
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
        nif = pyn.NifFile(outfile)
        systems = _np_systems(nif)
        [sid] = {s for s, _ in systems.values()}
        data = [n for n in nif.nodes.values() if n.collision_object
                and n.collision_object.blockname == 'bhkNPCollisionObject'][0] \
            .collision_object.physics_system.data
        flags = TT.havok_body_flags(data)
        return {name: flags[b] for name, (_, b) in systems.items()}

    assert TT.is_eq(exported(), van, "vanilla's flags")
    com.pyn_fo4phys.body_flag_10000 = False
    assert TT.is_eq(exported()['COM'], (0x80, 0, 0), "moved by physics: 0x80")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_HINGE():
    """FO4 hinges come in as Blender hinges and go back out, in one physics system.

    The lunchbox is one system of 3 bodies: the box, a side panel and a top flap, the
    two hinged to the box by limited hinges.  Export used to split it into 3 systems
    and drop the hinges, so in game the pieces fell apart (Discord report D1).

    - Import: two hinge Rigid Body Constraints, between the right objects, at the
      pivots, with vanilla's limits (Blender counts the angle the other way, so
      they're negated and swapped) and friction.
    - Export: one system, every node naming the body vanilla's names, and vanilla's
      hinges.
    """
    van_nif = pyn.NifFile(LUNCHBOX_DEST)
    van_hinges, _ = _np_hinges(van_nif)
    van_sys = _np_systems(van_nif)

    bpy.ops.import_scene.pynifly(filepath=LUNCHBOX_DEST)
    bone_of = _bone_of_collision()
    empties = [o for o in bpy.data.objects if o.rigid_body_constraint]
    assert TT.is_eq(len(empties), 2, "two hinges")
    for e in empties:
        c = e.rigid_body_constraint
        key = (bone_of[c.object1.name], bone_of[c.object2.name])
        assert TT.is_contains(key, van_hinges, f"{e.name}: hinged bodies")
        pivot, axis, (lo, hi), friction = van_hinges[key]
        assert TT.is_eq(c.type, 'HINGE', f"{e.name}: a hinge")
        assert TT.is_eq(e.parent, c.object1, f"{e.name}: parented to body A")
        assert TT.is_true(c.use_limit_ang_z, f"{e.name}: limited")
        assert TT.is_equiv((c.limit_ang_z_lower, c.limit_ang_z_upper), (-hi, -lo),
                           f"{e.name}: limits, Blender's way round", e=0.02)
        assert TT.is_equiv(e.pyn_constraint.friction, friction, f"{e.name}: friction", e=1e-6)
        mw = e.matrix_world
        assert TT.is_lt((mw.translation / HAVOC_SCALE_FACTOR - pivot).length, 1e-4,
                        f"{e.name}: at the pivot")
        assert TT.is_gt(abs(mw.col[2].xyz.normalized().dot(axis)), 1 - 1e-5,
                        f"{e.name}: Z along the hinge axis")

    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_HINGE.nif")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = pyn.NifFile(outfile)
    sys_out = _np_systems(out)
    assert TT.is_eq(len({s for s, _ in sys_out.values()}), 1, "one physics system")
    assert TT.is_eq({k: b for k, (_, b) in sys_out.items()},
                    {k: b for k, (_, b) in van_sys.items()}, "each node names vanilla's body")
    van_geo, out_geo = _np_bodies(van_nif), _np_bodies(out)
    for k in van_geo:
        assert TT.is_lt(max(math.dist(a, b) for a, b in zip(out_geo[k].verts, van_geo[k].verts)),
                        1e-4, f"{k}: its own shape")
    got, others = _np_hinges(out)
    assert TT.is_eq(others, {}, "nothing else")
    _check_hinges(got, van_hinges, "exported")


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_HINGE_NEW():
    """A hinge added in Blender exports, between bodies built in Blender.

    The lunchbox's hinges are deleted and its bodies' indices cleared, as if built
    by hand; one new hinge joins the flap to the box.  Bodies without an index don't
    stop the export: they're numbered in export order.  Limits set in Blender come
    out negated and swapped, Havok's way round.
    """
    bpy.ops.import_scene.pynifly(filepath=LUNCHBOX_DEST)
    bone_of = _bone_of_collision()
    for e in [o for o in bpy.data.objects if o.rigid_body_constraint]:
        bpy.data.objects.remove(e)
    shapes = {bone_of[o.name]: o for o in bpy.data.objects
              if o.get('pynRigidBody') == 'bhkPhysicsSystem'}
    for o in shapes.values():
        if 'pynCollisionBodyID' in o:
            del o['pynCollisionBodyID']

    flap, box = shapes['Bone003'], shapes['Bone001']
    e = bpy.data.objects.new("myhinge", None)
    bpy.context.scene.collection.objects.link(e)
    e.matrix_world = Matrix.Translation(flap.matrix_world.translation) @ \
        Matrix.Rotation(math.pi / 2, 4, 'X')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = e
    e.select_set(True)
    bpy.ops.rigidbody.constraint_add(type='HINGE')
    c = e.rigid_body_constraint
    c.object1, c.object2 = flap, box
    c.use_limit_ang_z = True
    c.limit_ang_z_lower, c.limit_ang_z_upper = -1.0, 0.1
    want_pivot = e.matrix_world.translation / HAVOC_SCALE_FACTOR
    want_axis = e.matrix_world.col[2].xyz.normalized()

    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_HINGE_NEW.nif")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    out = pyn.NifFile(outfile)
    sys_out = _np_systems(out)
    assert TT.is_eq(len({s for s, _ in sys_out.values()}), 1, "one physics system")
    assert TT.is_eq(sorted(b for _, b in sys_out.values()), [0, 1, 2], "bodies numbered")
    got, _ = _np_hinges(out)
    _check_hinges(got, {('Bone003', 'Bone001'): (want_pivot, want_axis, (-0.1, 1.0), 0.01)},
                  "new hinge", limit_tol=1e-5)


@TT.category('PHYSICS')
def TEST_BLENDER_HINGE_SIGN():
    """Blender's hinge counts its angle as object 2 turning NEGATIVELY about the
    constraint's Z: an arm hinged to a fixed block falls the way the lower limit
    allows.  Havok counts the other way, so import and export negate and swap the
    limits; if Blender changes this, they must change too.
    """
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    sc.rigidbody_world.point_cache.frame_end = 120
    bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0))
    base = bpy.context.object
    bpy.ops.rigidbody.object_add(type='PASSIVE')
    bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0))
    arm = bpy.context.object
    arm.scale = (5, 1, 1)
    bpy.ops.object.transform_apply(scale=True)
    arm.location = (0.6, 0, 0)
    bpy.ops.rigidbody.object_add(type='ACTIVE')
    arm.rigid_body.collision_shape = 'BOX'
    arm.rigid_body.collision_collections[0] = False
    arm.rigid_body.collision_collections[1] = True
    e = bpy.data.objects.new("hinge", None)
    sc.collection.objects.link(e)
    e.matrix_world = Matrix.Rotation(-math.pi / 2, 4, 'X')    # Z along world +Y
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = e
    e.select_set(True)
    bpy.ops.rigidbody.constraint_add(type='HINGE')
    c = e.rigid_body_constraint
    c.object1, c.object2 = base, arm
    c.use_limit_ang_z = True
    c.limit_ang_z_lower, c.limit_ang_z_upper = -1.0, 0.1
    try:
        for f in range(1, 121):
            sc.frame_set(f)
        m = arm.matrix_world.copy()
    finally:
        # Leave no simulation behind: a later test's rigid bodies would fall. The hinge and
        # bodies go while the world still holds them: removed after the world, the hinge
        # points at freed Bullet bodies, and deleting it crashed Blender in the next test's
        # cleanup (btRigidBody::removeConstraintRef, full suite 2026-11-26).
        sc.frame_set(1)
        for o in (e, arm, base):
            bpy.data.objects.remove(o)
        bpy.ops.rigidbody.world_remove()
    turned = math.atan2(-m.col[0].z, m.col[0].x)     # about +Y; falling is positive
    assert TT.is_equiv(turned, 1.0, "the arm falls to minus the lower limit", e=0.05)


@TT.category('FO4', 'PHYSICS')
def TEST_COLLISION_FO4_SHOTGUN_BARREL():
    """FO4 bhkPhysicsSystem: shotgun barrel collision sits near the visual mesh.

    CombatShotgunBarrel_1.nif has a collision that should align with the barrel
    visual mesh (~21 BU long along Y).  Import, verify the collision bounds are
    close to the visual mesh, export, reimport and check the round-trip.
    """
    testfile = TTB.test_file(r"tests\FO4\Shotgun\CombatShotgunBarrel_1.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 create_bones=False,
                                 rename_bones=False)

    # Find the visual meshes (the NIF has two: barrel body and a smaller part)
    barrel_meshes = [o for o in bpy.data.objects
                     if o.type == 'MESH' and o.name.startswith('CombatShotgunBarrel:')]
    assert TT.is_gt(len(barrel_meshes), 0, "Barrel visual meshes exist")

    # Find the collision shape
    physics_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_gt(len(physics_shapes), 0, "bhkPhysicsSystem collision imported")

    coll_obj = physics_shapes[0]
    assert TT.is_eq(coll_obj.type, 'MESH', "Collision object is a mesh")
    assert TT.is_gt(len(coll_obj.data.vertices), 0, "Collision mesh has vertices")

    mesh_bounds = TTB.combined_world_bounds(barrel_meshes)
    coll_bounds = TTB.world_bounds(coll_obj)
    TTB.assert_bounds_close(coll_bounds, mesh_bounds, 5.0, "Collision vs barrel mesh")

    # Barrel NIF has child connect points, so collision uses pynCollisionTarget
    # (custom property) rather than a constraint.
    coll_targets = [obj for obj in bpy.data.objects
                    if obj.get('pynCollisionTarget') == coll_obj.name]
    assert TT.is_gt(len(coll_targets), 0, "pynCollisionTarget set for collision")

    # ---- Export and round-trip verify ----------------------------------------
    outfile = TTB.test_file(r"tests\Out\TEST_COLLISION_FO4_SHOTGUN_BARREL.nif")
    orig_nvert = len(coll_obj.data.vertices)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.import_scene.pynifly(filepath=outfile, create_collection=True)

    chk_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_gt(len(chk_shapes), 0, "Round-trip preserves collision shape")

    chk = chk_shapes[0]
    assert TT.is_eq(len(chk.data.vertices), orig_nvert, "Vertex count preserved")


@TT.category('SKYRIMSE', 'PHYSICS', 'ANIMATION')
def TEST_COLLISION_ANIMATED_NODE():
    """An animated node with a collision plays its animation in Blender and round-trips.

    Vanilla impjaildoor01.nif: Door01 carries a bhkCollisionObject and is driven by the
    Open/Close sequences. Normally the collision drives its node (the node copies the
    collision's transforms, so physics moves the mesh). For an animated node that pins it
    and the animation can't play, so the link runs the other way: the collision follows
    the node, and is kinematic so the rigid body sim takes its transform from the node.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\impjaildoor01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_COLLISION_ANIMATED_NODE.nif")
    nif = pyn.NifFile(testfile)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    sc = bpy.context.scene
    door = bpy.data.objects['Door01']
    TT.assert_eq([c for c in door.constraints if c.type == 'COPY_TRANSFORMS'], [],
                 "Animated node isn't pinned to its collision")
    coll = next(o for o in bpy.data.objects
                if any(c.type == 'COPY_TRANSFORMS' and c.target == door for c in o.constraints))
    assert coll.rigid_body and coll.rigid_body.kinematic, "Collision is kinematic"

    # The door swings, and the collision swings with it.
    act = door.animation_data.action
    sc.frame_set(int(act.frame_start))
    closed = door.matrix_world.copy()
    sc.frame_set(int(act.frame_end))
    dg = bpy.context.evaluated_depsgraph_get()
    swung = door.evaluated_get(dg).matrix_world
    TT.assert_gt(closed.to_quaternion().rotation_difference(swung.to_quaternion()).angle, 1.0,
                 "Door swings")
    assert NT.MatNearEqual(coll.evaluated_get(dg).matrix_world, swung), "Collision follows the door"

    ### EXPORT ###
    sc.frame_set(int(act.frame_start))
    root = next(obj for obj in bpy.data.objects if 'pynRoot' in obj)
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    nifout = pyn.NifFile(outfile)
    co_in, co_out = nif.nodes['Door01'].collision_object, nifout.nodes['Door01'].collision_object
    assert co_out is not None, "Door01 keeps its collision"
    TT.assert_eq(co_out.body.shape.blockname, co_in.body.shape.blockname, "Collision shape")
    TT.assert_eq(co_out.body.properties.collisionFilter_layer,
                 co_in.body.properties.collisionFilter_layer, "Collision layer")
    TT.assert_eq(co_out.body.properties.motionSystem, co_in.body.properties.motionSystem,
                 "Motion system")
    assert nifout.nodes['Door01'].properties.transform.NearEqual(
        nif.nodes['Door01'].properties.transform, epsilon=0.001), "Door01 rest transform"
    TT.assert_eq(
        {k: sorted(b.node_name for b in s.controlled_blocks)
         for k, s in nifout.root.controller.sequences.items()},
        {k: sorted(b.node_name for b in s.controlled_blocks)
         for k, s in nif.root.controller.sequences.items()},
        "Sequences")


@TT.category('SKYRIM', 'COLLISION')
def TEST_COLLISION_PROPERTIES():
    """Test some specific collision property values."""
    testfile = TTB.test_file(r"tests\SkyrimSE\SteelDagger.nif")
    outfile = TTB.test_file(r"tests\out\TEST_COLLISION_PROPERTIES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    root = [obj for obj in bpy.data.objects if 'pynRoot' in obj][0]
    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    coll = nifout.rootNode.collision_object
    body = coll.body
    assert body.properties.broadPhaseType == BroadPhaseType.ENTITY, "Have correct broad phase type"
    assert body.properties.collisionResponse2 == hkResponseType.SIMPLE_CONTACT, "Have correct CollisionResponse2"
    assert body.properties.processContactCallbackDelay == 65535, "Have correct processContactCallbackDelay"
    assert body.properties.rollingFrictionMult == 0, "Have correct rollingFrictionMult"
    assert body.properties.motionSystem == hkMotionType.SPHERE_STABILIZED, "Have correct motionSystem"
    assert body.properties.solverDeactivation == hkSolverDeactivation.LOW, "Have correct solverDeactivation"
    assert body.properties.qualityType == hkQualityType.MOVING, "Have correct qualityType"


@TT.category('SKYRIMSE', 'TREE', 'COLLISION')
def TEST_TREE_EXPORT_FIDELITY():
    """Exported tree matches vanilla block types.

    Two regressions guarded here: (1) the lowest-LOD billboards must stay
    NiTriShape (SSE export used to force everything to BSTriShape); (2) the trunk
    capsules go bare in the bhkListShape -- export must NOT wrap each in a
    bhkConvexTransformShape (those aren't in the Blender scene; they were being
    fabricated on export).
    """
    from ctypes import create_string_buffer
    from collections import Counter
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_TREE_EXPORT_FIDELITY.nif", output=True)
    bpy.ops.import_scene.pynifly(filepath=testfile)
    for o in bpy.data.objects:
        o.select_set(True)
    root = next(o for o in bpy.data.objects if 'pynRoot' in o)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nif = pyn.NifFile(outfile); h = nif._handle
    c = Counter(); i = 0
    while True:
        b = create_string_buffer(128); pyn.nifly.getBlockname(h, i, b, 128)
        nm = b.value.decode()
        if not nm:
            break
        c[nm] += 1; i += 1
        if i > 300:
            break
    assert TT.is_eq(c['NiTriShape'], 2, f"LOD billboards stay NiTriShape: {c['NiTriShape']}")
    assert TT.is_eq(c['bhkConvexTransformShape'], 0,
                     f"No fabricated bhkConvexTransformShape: {c['bhkConvexTransformShape']}")
    assert TT.is_eq(c['bhkCapsuleShape'], 3, f"All 3 capsules exported bare: {c['bhkCapsuleShape']}")


@TT.category('SKYRIMSE', 'COLLISION')
def TEST_PRETTY_BONE_COLLISION():
    """Pretty bones + a bone-mounted collision: pose == rest AND the collision
    sits at the bone's real (un-pretty) position.

    A bhkCollisionObject on a bone adds a COPY_TRANSFORMS constraint. The collision
    is placed at the bone's real (un-pretty) world position so it follows the mesh;
    the constraint that would drive the bone to it is left disabled under pretty
    bones, so the cosmetically-rotated bone keeps its rest pose (no mesh deform).
    Two things must hold: (1) every bone's pose == rest; (2) all three trunk
    capsules land at the same world geometry with pretty on as with pretty off
    (full vertex sets, so a swing would be caught) -- they must NOT follow the
    cosmetic bone rotation, which put off-axis branch capsules 90 deg off branch.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\treeaspen03.nif")

    def capsules_world():
        """All bhkCapsuleShape objects' full vertex sets in world space, sorted by
        name so pretty and non-pretty imports line up."""
        caps = sorted((o for o in bpy.data.objects
                       if o.name.startswith('bhkCapsule')), key=lambda o: o.name)
        return [[(o.matrix_world @ v.co).copy() for v in o.data.vertices]
                for o in caps]

    # Pretty: pose must equal rest, and a bone collision constraint must exist.
    bpy.ops.import_scene.pynifly(filepath=testfile, rotate_bones_pretty=True)
    bpy.context.view_layer.update()
    armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert armatures, "Imported a skinned tree with an armature"
    assert any(c.name == 'bhkCollisionConstraint'
               for arma in armatures for pb in arma.pose.bones
               for c in pb.constraints), "A bone carries a bhkCollisionConstraint"

    mismatches = []
    for arma in armatures:
        for pb in arma.pose.bones:
            rest = arma.data.bones[pb.name].matrix_local
            diff = max(abs(rest[i][j] - pb.matrix[i][j])
                       for i in range(4) for j in range(4))
            if diff > 0.001:
                mismatches.append(f"{arma.name}/{pb.name}: maxdiff={diff:.3f}")
    assert not mismatches, \
        "Pretty bone pose must equal rest even with a bone collision:\n" + "\n".join(mismatches)

    pretty_caps = capsules_world()
    assert TT.is_eq(len(pretty_caps), 3, f"All 3 trunk capsules imported: {len(pretty_caps)}")

    # Non-pretty: every capsule must land at the same world geometry (not just
    # position -- full vertex sets, so a 90 deg swing would be caught too).
    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=testfile, rotate_bones_pretty=False)
    bpy.context.view_layer.update()
    plain_caps = capsules_world()
    assert TT.is_eq(len(plain_caps), 3, f"All 3 capsules (non-pretty): {len(plain_caps)}")

    for ci, (pc, plc) in enumerate(zip(pretty_caps, plain_caps)):
        assert TT.is_eq(len(pc), len(plc), f"Capsule {ci} same vertex count")
        for vi, (pv, plv) in enumerate(zip(pc, plc)):
            assert NT.VNearEqual(pv, plv, 0.01), \
                f"Capsule {ci} vert {vi} must be pretty-invariant: " \
                f"pretty={pv[:]} plain={plv[:]}"


@TT.category('SKYRIM', 'MOPP')
@TT.parameterize(("game",      "testpath"),
                 [("SKYRIM",    r"tests\Skyrim\noblecrate01.nif"),
                  ("SKYRIMSE",  r"tests\SkyrimSE\noblecrate01.nif")])
def TEST_COLLISION_MOPP_ROUNDTRIP(game, testpath):
    """MOPP collision round-trip: import noblecrate01, export, reimport, verify geometry."""
    testfile = TTB.test_file(testpath)
    outfile = TTB.test_file(f"tests/Out/TEST_COLLISION_MOPP_ROUNDTRIP_{game}.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Find the collision shape (named after the child shape type)
    coll_objs = [o for o in bpy.data.objects
                 if o.name.startswith("bhkPackedNiTriStripsShape")
                 or o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs), 0, "Found MOPP collision object")
    coll_obj = coll_objs[0]

    orig_vert_count = len(coll_obj.data.vertices)
    orig_tri_count = len(coll_obj.data.polygons)
    assert TT.is_gt(orig_vert_count, 0, f"Collision has {orig_vert_count} verts")
    assert TT.is_gt(orig_tri_count, 0, f"Collision has {orig_tri_count} tris")

    # Select all objects and export
    BD.ObjectSelect(list(bpy.data.objects), active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game=game)

    # Verify the exported NIF's rigid body has a valid rotation quaternion.
    # A zero quaternion [0,0,0,0] crashes the Havok physics engine.
    from pyn.pynifly import NifFile
    outnif = NifFile(outfile)
    out_body = outnif.rootNode.collision_object.body
    out_rot = out_body.properties.rotation
    rot_len_sq = sum(out_rot[i]**2 for i in range(4))
    assert TT.is_equiv(rot_len_sq, 1.0,
                        f"Rigid body rotation is unit quaternion (len²={rot_len_sq})", e=0.01)

    # Clear and reimport
    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=outfile)

    # Find collision again
    coll_objs2 = [o for o in bpy.data.objects
                  if o.name.startswith("bhkPackedNiTriStripsShape")
                  or o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs2), 0, "Reimported MOPP collision found")
    coll_obj2 = coll_objs2[0]

    reimport_vert_count = len(coll_obj2.data.vertices)
    reimport_tri_count = len(coll_obj2.data.polygons)
    assert TT.is_eq(reimport_vert_count, orig_vert_count,
                     f"Vertex count preserved: {reimport_vert_count}")
    assert TT.is_eq(reimport_tri_count, orig_tri_count,
                     f"Triangle count preserved: {reimport_tri_count}")


@TT.category('SKYRIM', 'MOPP')
def TEST_COLLISION_MOPP_MATERIALS():
    """Multi-material MOPP round-trip: import dockcorsol01, verify vertex groups, export, reimport."""
    testfile = TTB.test_file(r"tests\SkyrimSE\dockcorsol01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_MOPP_MATERIALS.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Find the collision shape
    coll_objs = [o for o in bpy.data.objects
                 if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs), 0, "Found compressed mesh collision")
    coll_obj = coll_objs[0]

    # Should have SKY_HAV_MAT_ vertex groups
    mat_groups = [vg for vg in coll_obj.vertex_groups
                  if vg.name.startswith("SKY_HAV_MAT_")]
    assert TT.is_gt(len(mat_groups), 1,
                     f"Multiple material vertex groups: {[vg.name for vg in mat_groups]}")

    mat_names = sorted(vg.name for vg in mat_groups)
    log.info(f"Material groups on import: {mat_names}")

    # Verify specific materials (dockcorsol01 has WOOD + CLOTH)
    assert "SKY_HAV_MAT_WOOD" in mat_names or "SKY_HAV_MAT_MATERIAL_CLOTH" in mat_names, \
        f"Expected WOOD or CLOTH in {mat_names}"

    orig_tri_count = len(coll_obj.data.polygons)

    # Export
    BD.ObjectSelect(list(bpy.data.objects), active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # Reimport
    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=outfile)

    # Find collision again
    coll_objs2 = [o for o in bpy.data.objects
                  if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs2), 0, "Reimported collision found")
    coll_obj2 = coll_objs2[0]

    # Triangle count preserved
    reimport_tri_count = len(coll_obj2.data.polygons)
    assert TT.is_eq(reimport_tri_count, orig_tri_count,
                     f"Triangle count preserved: {reimport_tri_count}")

    # Material vertex groups preserved
    mat_groups2 = [vg for vg in coll_obj2.vertex_groups
                   if vg.name.startswith("SKY_HAV_MAT_")]
    assert TT.is_eq(len(mat_groups2), len(mat_groups),
                     f"Material group count preserved: {len(mat_groups2)}")

    mat_names2 = sorted(vg.name for vg in mat_groups2)
    assert TT.is_eq(mat_names2, mat_names,
                     f"Material group names preserved: {mat_names2}")

    # Verify bhkCompressedMeshShapeData properties on the exported file
    nifcheck = pyn.NifFile(outfile)
    coll_shapes = [n.collision_object.body.shape.child
                   for n in nifcheck.nodes.values()
                   if n.collision_object and n.collision_object.body
                   and n.collision_object.body.shape
                   and hasattr(n.collision_object.body.shape, 'child')]
    assert TT.is_gt(len(coll_shapes), 0, "Found compressed mesh shape in exported NIF")
    cms = coll_shapes[0]
    assert TT.is_equiv(cms.properties.error, 0.001,
                        f"error field: {cms.properties.error}")
    assert TT.is_eq(cms.properties.materialType, 1,
                     f"materialType field: {cms.properties.materialType}")
    assert TT.is_eq(cms.properties.bitsPerIndex, 17,
                     "bitsPerIndex vanilla standard")
    assert TT.is_eq(cms.properties.bitsPerWIndex, 18,
                     "bitsPerWIndex vanilla standard")
    assert TT.is_eq(cms.properties.maskIndex, 0x1FFFF,
                     "maskIndex vanilla standard")
    assert TT.is_eq(cms.properties.maskWIndex, 0x3FFFF,
                     "maskWIndex vanilla standard")

    # Verify bhkMoppBvTreeShape properties — read from fresh NifFile to ensure
    # we're checking the on-disk values, not cached in-memory objects.
    nifcheck2 = pyn.NifFile(outfile)
    for n in nifcheck2.nodes.values():
        if n.collision_object and n.collision_object.body and n.collision_object.body.shape:
            shape = n.collision_object.body.shape
            if hasattr(shape, 'mopp_data'):
                mopp_bytes, origin, scale = shape.mopp_data
                assert TT.is_gt(scale, 0, f"MOPP scale is positive: {scale}")
                log.debug(f"MOPP buildType value: {shape.properties.buildType}")
                assert TT.is_eq(shape.properties.buildType, 1,
                                f"MOPP buildType (BUILT_WITHOUT_CHUNK_SUBDIVISION): {shape.properties.buildType}")
                break
    else:
        assert False, "No MOPP shape found in exported NIF"


@TT.category('SKYRIM', 'MOPP')
def TEST_COLLISION_MOPP_MULTICHUNK():
    """Multi-chunk MOPP round-trip: dockstepsdown01 (923 verts, 550 tris, 5+ chunks, 4 materials)."""
    testfile = TTB.test_file(r"tests\SkyrimSE\dockstepsdown01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_MOPP_MULTICHUNK.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile)

    coll_objs = [o for o in bpy.data.objects
                 if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs), 0, "Found compressed mesh collision")
    coll_obj = coll_objs[0]

    orig_vert_count = len(coll_obj.data.vertices)
    orig_tri_count = len(coll_obj.data.polygons)
    assert TT.is_gt(orig_vert_count, 255, f"Mesh needs multiple chunks: {orig_vert_count} verts")

    mat_groups = [vg for vg in coll_obj.vertex_groups
                  if vg.name.startswith("SKY_HAV_MAT_")]
    mat_names = sorted(vg.name for vg in mat_groups)
    log.info(f"Import: {orig_vert_count} verts, {orig_tri_count} tris, materials: {mat_names}")

    # Export
    BD.ObjectSelect(list(bpy.data.objects), active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # Reimport
    TTB.clear_all()
    bpy.ops.import_scene.pynifly(filepath=outfile)

    coll_objs2 = [o for o in bpy.data.objects
                  if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs2), 0, "Reimported collision found")
    coll_obj2 = coll_objs2[0]

    reimport_tri_count = len(coll_obj2.data.polygons)
    assert TT.is_eq(reimport_tri_count, orig_tri_count,
                     f"Triangle count preserved: {reimport_tri_count}")

    # Material groups preserved
    mat_groups2 = [vg for vg in coll_obj2.vertex_groups
                   if vg.name.startswith("SKY_HAV_MAT_")]
    mat_names2 = sorted(vg.name for vg in mat_groups2)
    assert TT.is_eq(mat_names2, mat_names,
                     f"Material groups preserved: {mat_names2}")


@TT.category('SKYRIM', 'MOPP')
def TEST_COLLISION_MOPP_MOUNTAINPEAK():
    """Large MOPP collision round-trip: mountainpeak02 (4290 verts, 1754 tris)."""
    testfile = TTB.test_file(r"tests\SkyrimSE\mountainpeak02.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_MOPP_MOUNTAINPEAK.nif", output=True)

    # Read original collision stats via pyn
    nif_orig = pyn.NifFile(testfile)
    orig_root = nif_orig.rootNode
    orig_co = orig_root.collision_object
    orig_body = orig_co.body
    orig_mopp = orig_body.shape
    orig_cmesh = orig_mopp.child
    orig_verts = orig_cmesh.vertices
    orig_tris = orig_cmesh.triangles
    orig_mopp_data, orig_origin, orig_scale = orig_mopp.mopp_data
    log.info(f"Original: {len(orig_verts)} verts, {len(orig_tris)} tris, "
             f"MOPP {len(orig_mopp_data)} bytes")

    # Import into Blender
    bpy.ops.import_scene.pynifly(filepath=testfile, create_collection=True)
    import_coll = bpy.context.collection

    coll_objs = [o for o in import_coll.all_objects
                 if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs), 0, "collision imported")
    coll_obj = coll_objs[0]

    import_vert_count = len(coll_obj.data.vertices)
    import_tri_count = len(coll_obj.data.polygons)
    assert TT.is_eq(import_vert_count, len(orig_verts), "imported vert count")
    assert TT.is_eq(import_tri_count, len(orig_tris), "imported tri count")
    log.info(f"Imported: {import_vert_count} verts, {import_tri_count} tris")

    # Check bounding box is reasonable (mountain peak ~119x137x122 Havok units)
    bb = TTB.get_obj_bbox(coll_obj, worldspace=True)
    bb_size = bb[1] - bb[0]
    assert TT.is_gt(bb_size.x, 5.0, "collision X extent")
    assert TT.is_gt(bb_size.y, 5.0, "collision Y extent")
    assert TT.is_gt(bb_size.z, 5.0, "collision Z extent")

    # Single-material mesh should have one SKY_HAV_MAT_ vertex group
    mat_vgroups = [vg for vg in coll_obj.vertex_groups
                   if vg.name.startswith("SKY_HAV_MAT_")]
    assert TT.is_eq(len(mat_vgroups), 1, "one material vertex group")
    assert TT.is_eq(mat_vgroups[0].name, "SKY_HAV_MAT_STONE", "material is STONE")

    # Also check visual meshes imported
    vis_meshes = [o for o in import_coll.all_objects
                  if o.type == 'MESH' and not o.name.startswith("bhk")]
    assert TT.is_eq(len(vis_meshes), 2, "visual mesh count")

    # Export
    BD.ObjectSelect(list(import_coll.all_objects), active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    # Compare exported NIF collision against original
    nif_out = pyn.NifFile(outfile)
    out_root = nif_out.rootNode
    out_co = out_root.collision_object
    assert out_co is not None, "exported NIF has collision"
    out_body = out_co.body
    out_mopp = out_body.shape
    assert TT.is_eq(out_mopp.blockname, "bhkMoppBvTreeShape", "MOPP shape type")

    out_cmesh = out_mopp.child
    assert TT.is_eq(out_cmesh.blockname, "bhkCompressedMeshShape", "child shape type")

    # Verify vanilla-standard bitsPerIndex/bitsPerWIndex
    out_cms_props = out_cmesh.properties
    assert TT.is_eq(out_cms_props.bitsPerIndex, 17, "bitsPerIndex")
    assert TT.is_eq(out_cms_props.bitsPerWIndex, 18, "bitsPerWIndex")
    assert TT.is_eq(out_cms_props.maskIndex, 0x1FFFF, "maskIndex")
    assert TT.is_eq(out_cms_props.maskWIndex, 0x3FFFF, "maskWIndex")

    out_verts = out_cmesh.vertices
    out_tris = out_cmesh.triangles
    log.info(f"Exported: {len(out_verts)} verts, {len(out_tris)} tris")

    # Triangle count preserved exactly; vert count may increase due to
    # chunk boundary duplication (each chunk has its own local vertex set).
    assert TT.is_ge(len(out_verts), len(orig_verts), "exported vert count")
    assert TT.is_eq(len(out_tris), len(orig_tris), "exported tri count")

    # Material should be STONE on all triangles
    out_mat_ids = out_cmesh.material_ids
    out_unique_mats = set(out_mat_ids)
    assert TT.is_eq(len(out_unique_mats), 1, "single material in export")
    assert TT.is_eq(next(iter(out_unique_mats)), 3741512247, "exported material is STONE")

    # Check MOPP data was generated
    out_mopp_data, out_origin, out_scale = out_mopp.mopp_data
    log.info(f"Exported MOPP: {len(out_mopp_data)} bytes, "
             f"origin=({out_origin[0]:.3f},{out_origin[1]:.3f},{out_origin[2]:.3f}), "
             f"scale={out_scale:.6f}")
    assert TT.is_gt(len(out_mopp_data), 0, "MOPP bytecode generated")

    # MOPP origin should be close to original
    for i in range(3):
        assert TT.is_equiv(out_origin[i], orig_origin[i], f"MOPP origin[{i}]", e=1.0)

    # Bounding box of exported verts should match original closely
    orig_xs = [v[0] for v in orig_verts]
    orig_ys = [v[1] for v in orig_verts]
    orig_zs = [v[2] for v in orig_verts]
    out_xs = [v[0] for v in out_verts]
    out_ys = [v[1] for v in out_verts]
    out_zs = [v[2] for v in out_verts]
    assert TT.is_equiv(min(out_xs), min(orig_xs), "vert min X", e=1.0)
    assert TT.is_equiv(max(out_xs), max(orig_xs), "vert max X", e=1.0)
    assert TT.is_equiv(min(out_ys), min(orig_ys), "vert min Y", e=1.0)
    assert TT.is_equiv(max(out_ys), max(orig_ys), "vert max Y", e=1.0)
    assert TT.is_equiv(min(out_zs), min(orig_zs), "vert min Z", e=1.0)
    assert TT.is_equiv(max(out_zs), max(orig_zs), "vert max Z", e=1.0)

    # Rigid body properties should be preserved
    out_bp = out_body.properties
    orig_bp = orig_body.properties
    assert TT.is_eq(out_bp.collisionFilter_layer, orig_bp.collisionFilter_layer,
                     "collision layer")
    assert TT.is_equiv(out_bp.friction, orig_bp.friction, "friction", e=0.01)
    assert TT.is_equiv(out_bp.restitution, orig_bp.restitution, "restitution", e=0.01)

    # Reimport to verify the generated NIF is loadable
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=outfile, create_collection=True)
    reimport_coll = bpy.context.collection

    re_coll = [o for o in reimport_coll.all_objects
               if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(re_coll), 0, "reimported collision found")
    re_vert_count = len(re_coll[0].data.vertices)
    re_tri_count = len(re_coll[0].data.polygons)
    assert TT.is_ge(re_vert_count, len(orig_verts), "reimported vert count")
    assert TT.is_eq(re_tri_count, len(orig_tris), "reimported tri count")
    log.info(f"Reimported: {re_vert_count} verts, {re_tri_count} tris — OK")


@TT.category('SKYRIM', 'MOPP')
@TT.expect_errors(("Could not find texture", "Could not load"))
def TEST_COLLISION_MOPP_SEVMAGETOWER():
    """Very large MOPP collision round-trip: SEVMageTower05 (>65k verts).
    Exercises both uint32-wide triangle indices and the >64KB MOPP spine encoder.
    No "exceeds 64K" degradation warning should be emitted, the Target field on
    the bhkCompressedMeshShape should point to the root node, and the reimport
    must succeed."""
    import logging
    testfile = TTB.test_file(r"tests\SkyrimSE\SEVMageTower05.nif")
    outfile = TTB.test_file(
        r"tests/Out/TEST_COLLISION_MOPP_SEVMAGETOWER.nif", output=True)

    nif_orig = pyn.NifFile(testfile)
    orig_root = nif_orig.rootNode
    orig_mopp = orig_root.collision_object.body.shape
    orig_cmesh = orig_mopp.child
    orig_verts = orig_cmesh.vertices
    orig_tris = orig_cmesh.triangles
    log.info(f"Original: {len(orig_verts)} verts, {len(orig_tris)} tris")
    assert TT.is_gt(len(orig_verts), 65535, "fixture really has >65k verts")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_collection=True)
    import_coll = bpy.context.collection

    coll_objs = [o for o in import_coll.all_objects
                 if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(coll_objs), 0, "collision imported")

    # Capture MOPP warnings during export to confirm the spine encoder kicks
    # in cleanly (no "exceeds 64K" messages).
    warnings_seen = []
    class _Cap(logging.Handler):
        def emit(self, record):
            warnings_seen.append(record.getMessage())
    cap = _Cap(level=logging.WARNING)
    pyn_log = logging.getLogger("pynifly")
    pyn_log.addHandler(cap)
    try:
        BD.ObjectSelect(list(import_coll.all_objects), active=True)
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')
    finally:
        pyn_log.removeHandler(cap)

    degraded = [w for w in warnings_seen if "exceeds 64K" in w]
    assert TT.is_eq(degraded, [],
                    f"No MOPP degradation warnings (got {len(degraded)}: "
                    f"{degraded[:1]})")

    nif_out = pyn.NifFile(outfile)
    out_mopp = nif_out.rootNode.collision_object.body.shape
    assert TT.is_eq(out_mopp.blockname, "bhkMoppBvTreeShape", "MOPP shape type")
    out_cmesh = out_mopp.child
    assert TT.is_eq(out_cmesh.blockname, "bhkCompressedMeshShape",
                    "child shape type")
    assert TT.is_eq(out_cmesh.properties.targetID, nif_out.rootNode.id,
                    f"Target points to root (got {out_cmesh.properties.targetID}, "
                    f"expected {nif_out.rootNode.id})")

    out_tris = out_cmesh.triangles
    assert TT.is_eq(len(out_tris), len(orig_tris), "exported tri count")
    max_out_index = max(max(t) for t in out_tris)
    assert TT.is_gt(max_out_index, 65535,
                    f"exported triangles reference >65535 vertex indices "
                    f"(max {max_out_index})")

    out_mopp_data, _, _ = out_mopp.mopp_data
    assert TT.is_gt(len(out_mopp_data), 0, "MOPP bytecode generated")
    log.info(f"Exported MOPP: {len(out_mopp_data)} bytes")

    # Reimport sanity check
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=outfile, create_collection=True)
    reimport_coll = bpy.context.collection
    re_coll = [o for o in reimport_coll.all_objects
               if o.name.startswith("bhkCompressedMeshShape")]
    assert TT.is_gt(len(re_coll), 0, "reimported collision found")
    assert TT.is_eq(len(re_coll[0].data.polygons), len(orig_tris),
                    "reimported tri count")


@TT.category('SKYRIM', 'MOPP', 'COLLISION')
@TT.expect_errors(("Could not find texture", "Could not load"))
def TEST_COLLISION_MOPP_RADIUS():
    """The bhkCompressedMeshShape convex radius round-trips.

    SEVMageTower05 uses 0.001, not PyNifly's 0.005 default, so a hardcoded
    export radius shows up as a changed value on the round trip."""
    testfile = TTB.test_file(r"tests\SkyrimSE\SEVMageTower05.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLLISION_MOPP_RADIUS.nif", output=True)

    orig_radius = pyn.NifFile(testfile).rootNode.collision_object.body.shape.child.properties.radius
    assert TT.is_neq(round(orig_radius, 5), 0.005,
                     f"fixture radius {orig_radius} differs from the export default")

    bpy.ops.import_scene.pynifly(filepath=testfile, create_collection=True)
    import_coll = bpy.context.collection
    BD.ObjectSelect(list(import_coll.all_objects), active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    out_radius = pyn.NifFile(outfile).rootNode.collision_object.body.shape.child.properties.radius
    assert TT.is_equiv(out_radius, orig_radius,
                       f"convex radius round-trips (was {orig_radius}, got {out_radius})")
