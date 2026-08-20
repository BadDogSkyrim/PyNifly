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
    assert TT.is_equiv(maxy, 64.4891, f"Max y")
    assert TT.is_equiv(miny, -50.5509, f"Min y")

    # Make sure the bone positions didn't get messed up by blender_xf.
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    mxbind = arma.data.bones['Bow_StringBone1'].matrix_local
    mxpose = arma.pose.bones['Bow_StringBone1'].matrix
    assert TT.is_equiv(mxbind, mxpose, f"Bind position vs pose position")

    # Check collision info
    midbone = arma.data.bones['Bow_MidBone']
    midbonew = arma.matrix_world @ midbone.matrix_local
    coll = arma.pose.bones['Bow_MidBone'].constraints[0].target
    assert TT.is_equiv(coll.matrix_world.translation, midbonew.translation, f"Collision position")

    q = coll.matrix_world.to_quaternion()
    assert TT.is_equiv(q, (0.7071, 0.0, 0.0, 0.7071,), f"Collision body rotation")

    # Scale factor applied to bow
    objmin, objmax = TTB.get_obj_bbox(bow, worldspace=True)
    assert TT.is_lt(objmax.y - objmin.y, 12, f"Bow scale")

    # Collision box bounds close to bow bounds.
    collbox = TTB.find_shape('bhkBoxShape')
    assert TTB.close_bounds(bow, collbox), f"Collision just covers bow"

    # Quick unit test--getting box info should be correct in world coordinates.
    c, d, r = BD.find_box_info(collbox)
    dworld = collbox.matrix_world.to_quaternion().inverted() @ (r @ d)
    dworld = Vector([abs(n) for n in dworld])

    # The rotation should result is the long axis aligned with y, short with z
    assert dworld.y > dworld.x > dworld.z, f"Have correct rotation"

    # Centerpoint of collision box is just offset from origin
    assert TT.is_equiv(c, Vector((0.6402, 0.0143, 0.002,)), f"Centerpoint")

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
    assert TT.is_eq(rootcheck.name, "GlassBowSkinned.nif", f"Root node name")
    assert TT.is_eq(rootcheck.blockname, "BSFadeNode", f"Root node type")
    assert TT.is_eq(rootcheck.flags, 14, f"Root block flags")

    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert TT.is_eq(collcheck.blockname, "bhkCollisionObject", f"Collision node block")
    assert TT.is_eq(bhkCOFlags(collcheck.flags).fullname, "ACTIVE | SYNC_ON_UPDATE", f"Collision flags")

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
    assert TT.is_lt(minb[0], mina[0], f"Box min x")
    assert TT.is_lt(minb[1], mina[1], f"Box min y")
    assert TT.is_gt(maxb[0], maxa[0], f"Box max x")
    assert TT.is_gt(maxb[1], maxa[1], f"Box max y")


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

    TT.assert_eq(coll.pyn_collshape.bhkMaterial, 'MATERIAL_BOWS_STAVES', f"Shape material")
    TT.assert_equiv(coll.pyn_collshape.bhkRadius, 0.0136, f"Radius")

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
    TT.assert_eq(strd.pyn_nistrdata.value, "WeaponBow", f"string extra data value")

    bsxf = TTB.find_shape("BSXFlags", type='EMPTY')
    root = [o for o in bpy.data.objects if "pynRoot" in o][0]
    TT.assert_eq(bsxf.parent, root, f"Extra data parent")
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
    assert NT.VNearEqual(cshapecheck3.vertices[0], (-0.73, -0.267, 0.014, 0.0)), f"Convex shape is correct"


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
    assert leek4.name == 'Leek04', f"Have correct parent"
    assert leek0.parent == leek1.parent, f"Have correct parent/child relationships"
    assert len(leek4.constraints) > 0, f"Have constraint on parent"
    cshape = leek4.constraints[0].target
    assert cshape, f"Have collision shape"
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
    assert shCheck.blockname == "bhkConvexVerticesShape", f"Have our convex vert shape"
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
    leek1 == leek10.parent == leek11.parent, f"Parent/child relationships correct"
    assert leek1.name == "Leek01", f"Have correct parent"
    assert len(leek1.constraints) > 0, f"Leek has constraints"
    
    # -------- Export --------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    # ------- Check ---------
    nif = pyn.NifFile(outfile)
    l1 = nif.nodes["Leek01"]
    l4 = nif.nodes["Leek04"]
    assert l1.collision_object.body.shape.blockname == "bhkConvexVerticesShape", f"Have the correct collisions"
    assert l4.collision_object.body.shape.blockname == "bhkConvexVerticesShape", f"Have the correct collisions"
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
    assert constr, f"Have constraints on root"
    coll = constr[0].target
    assert coll, f"Have collision object"
    assert coll.rigid_body, f"Collision object has physics"
    TT.assert_eq(coll.rigid_body.type, 'ACTIVE', f"Collision body type")
    TT.assert_equiv(coll.rigid_body.mass, 2.5, f"mass")
    TT.assert_equiv(coll.rigid_body.friction, 0.5, f"friction")
    TT.assert_eq(coll.pyn_collshape.bhkMaterial, 'CLOTH', f"Shape material custom property")

    xmax1 = max([v.co.x for v in cheese.data.vertices])
    xmax2 = max([v.co.x for v in coll.data.vertices])
    TT.assert_equiv(xmax1, xmax2, f"Max x vertex", e=0.5)
    corner = coll.data.vertices[0].co
    TT.assert_equiv(corner, (-4.18715, -7.89243, 7.08596,), f"Collision shape position")

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

    TT.assert_eq(rootcheck.name, "CheeseWedge01", f"Root node name")
    TT.assert_eq(rootcheck.blockname, "BSFadeNode", f"Root node type")

    TT.assert_eq(collcheck.blockname, "bhkCollisionObject", f"Collision node type")
    TT.assert_eq(collcheck.target, rootcheck, f"Collision target")

    TT.assert_eq(bodycheck.blockname, "bhkRigidBody", f"Rigid body type")
    TT.assert_eq(bodycheck.properties.mass, 2.5, f"Rigid body mass")
    TT.assert_eq(bodycheck.properties.friction, 0.5, f"Rigid body friction")

    TT.assert_eq(cvscheck.blockname, "bhkConvexVerticesShape", f"Collision shape type")
    TT.assert_eq(cvscheck.properties.bhkMaterial, SkyrimHavokMaterial.CLOTH, 
        "Collision body shape material")

    minxch = min(v[0] for v in cvscheck.vertices)
    maxxch = max(v[0] for v in cvscheck.vertices)
    minxorig = min(v[0] for v in cvsorig.vertices)
    maxxorig = max(v[0] for v in cvsorig.vertices)

    TT.assert_equiv(minxch, minxorig, f"Vertex x min")
    TT.assert_equiv(maxxch, maxxorig, f"Vertex x max")

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
    TT.assert_gt(zmin, -0.01, f"Minimum z")


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
    assert coll.pyn_collshape.bhkMaterial == 'SOLID_METAL', f"Have correct material"
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
    assert len(collshape.children) == 3, f" Collision shape has children"

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

    assert convex_xf_shape.child.blockname == "bhkBoxShape", f"Found the box shape"

    # Check that the ConvexTransforms put the collision shapes in the right place,
    # no matter what order they're written.
    xflist = set(round(xfs.transform[1][3], 3) for xfs in xfshapesorig)
    xfcheck = set(round(xfs.transform[1][3], 3) for xfs in xfshapescheck)
    assert xflist == xfcheck, f"Have same transforms in both files"

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
    assert TT.is_eq(collshape.name, 'bhkBoxShape', f"Found collision shape")
    
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
    assert TT.is_eq(bodycheck.properties.bufType, PynBufferTypes.bhkRigidBodyBufType, f"Have correct buffer type")

    names = [x.name for x in nifcheck.root.extra_data(blockname="BSBehaviorGraphExtraData")]
    assert TT.is_contains("BGED", names, f"Error: Expected BGED in {names}")
    bgedCheck = nifcheck.root.get_extra_data(blockname='BSBehaviorGraphExtraData', name='BGED')
    assert TT.is_eq(bgedCheck.behavior_graph_file, "Weapons\\Bow\\BowProject.hkx", f"Extra data value")
    assert TT.is_eq(bgedCheck.controls_base_skeleton, False, f"Extra data controls base skeleton")


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
        f"Capsule crosses origin"
    
    capcts = listcheck.children[0] 
    capshape = capcts.child
    assert capshape.blockname == 'bhkCapsuleShape', f"Have the capsule"
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
                    "Unknown block type: BSPositionData") ) # We don't yet handle particle systems
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

    # Each collision-bearing node should have its own constraint target.
    for node_name in ["GearDoor", "VltGearKeySupport"]:
        node_obj = bpy.data.objects[node_name]
        targets = [con.target for con in node_obj.constraints
                   if con.name == 'bhkCollisionConstraint' and con.target]
        assert TT.is_gt(len(targets), 0,
                         f"{node_name} has collision constraint")

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

    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    bpy.ops.export_scene.pynifly(filepath=cmout, target_game='FO4')

    cm_src = pyn.NifFile(cmfile)
    cm_dst = pyn.NifFile(cmout)
    src_ps = cm_src.nodes['DExtStands1x1Top01'].collision_object.physics_system
    dst_ps = cm_dst.nodes['DExtStands1x1Top01'].collision_object.physics_system
    assert TT.is_eq(dst_ps.data, src_ps.data,
                    "compound-of-mesh packfile is preserved byte for byte")


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
