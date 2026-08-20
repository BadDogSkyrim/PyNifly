"""Animation, HKX and KF tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('FO4', 'ANIMATION')
def TEST_FO4_LINEAR_ROTATION_KEYS():
    """Rotation channels using LINEAR keys can be exported.

    An NiTransformData with rotationType XYZ_ROTATION_KEY carries a separate
    interpolation per channel. The vanilla armor workbench animates two bones
    (WorkstationArmorGearBBone, WorkstationArmorSpindleBone) whose channels are
    LINEAR_KEY rather than QUADRATIC_KEY, and exporting them used to raise
    NotImplementedError.

    Those two bones' single keys carry a garbage time in vanilla (-447392.4375,
    confirmed in NifSkope -- not a misread). It's harmless in game: a lone key is
    a constant, and the value is 0. But it lands ~10.7M frames from the origin,
    outside float32 keyframe precision, so it cannot round-trip. Rather than have
    the importer or exporter launder vanilla's data, this test moves the keys to
    the animation start so it exercises the linear-key path, not the junk.
    """
    testfile = TTB.test_file(r"tests\FO4\WorkstationArmorB01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_FO4_LINEAR_ROTATION_KEYS.nif", output=True)

    # rotate_bones_pretty matches the shipped default, not the headless one: with it
    # off, this nif's bones happen to have unrotated rests so no rotation conversion
    # runs and the export path here is never reached.
    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=True,
                                 rotate_bones_pretty=True)

    arma = bpy.data.objects['WorkstationArmorB01:ARMATURE']
    action = arma.animation_data.action
    linear_bones = ['WorkstationArmorGearBBone', 'WorkstationArmorSpindleBone']

    # Move the junk-time keys to frame 1 (nif time 0). Identify them by their
    # absurd frame, not by bone: this nif has several animations, so the same
    # bone also has ordinary bezier curves in other action slots.
    moved = 0
    for fc in BD.action_fcurves(action):
        for k in fc.keyframe_points:
            if k.co.x < 0:
                assert TT.is_eq(k.interpolation, 'LINEAR',
                                "junk-time key is a linear key")
                assert any(b in fc.data_path for b in linear_bones), \
                    f"junk-time key is on a known linear bone: {fc.data_path}"
                k.co.x = 1
                moved += 1
    # Import now resamples misaligned channels onto their common timeline (both
    # the junk time and 0), so all three channels of each of the two bones carry a
    # junk-time key: 3 channels x 2 bones = 6.
    assert TT.is_eq(moved, 6, "normalized the junk-time linear keys")

    # Export just the armature and the shapes skinned to it. (Exporting the whole
    # workbench reports unweighted verts on the unskinned shapes -- unrelated.)
    BD.ObjectSelect([arma,
                     bpy.data.objects['WorkstationArmor:0'],
                     bpy.data.objects['WorkstationArmor:1']], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4',
                                 export_animations=True)

    ### CHECK ###

    nifcheck = pyn.NifFile(outfile)
    for bone in linear_bones:
        node = nifcheck.nodes[bone]
        assert node.controller, f"{bone} has a controller"
        td = node.controller.interpolator.data
        assert TT.is_eq(td.properties.rotationType, pyn.NiKeyType.XYZ_ROTATION_KEY,
                        f"{bone} rotation type")
        for chan, keys in (('xRotations', td.xrotations),
                           ('yRotations', td.yrotations),
                           ('zRotations', td.zrotations)):
            assert TT.is_eq(getattr(td.properties, chan).interpolation,
                            pyn.NiKeyType.LINEAR_KEY, f"{bone} {chan} stayed linear")
            # Constant no-op rotation: one or more linear keys, all at the animation
            # start with value 0. (Count isn't pinned -- resampling the misaligned
            # channels onto their common timeline can leave more than one key, all
            # equal.)
            assert TT.is_gt(len(keys), 0, f"{bone} {chan} has keys")
            for k in keys:
                assert TT.is_equiv(k.time, 0.0, f"{bone} {chan} key time", e=0.001)
                assert TT.is_equiv(k.value, 0.0, f"{bone} {chan} key value", e=0.001)


@TT.category('FO4', 'ANIMATION')
def TEST_FO4_EULER_CURVES_UNALIGNED():
    """Euler rotation channels with different key times can be exported.

    The nif keeps X/Y/Z rotations as three independent channels, each free to
    have its own key times. Exporting them needs a rotation conversion (Euler ->
    quaternion -> Euler) whenever the bone frame differs from the nif frame, and
    that needs all three values at one instant -- so the channels get resampled
    onto a common timeline. This used to raise "NYI: Euler bone rotations when
    fcurve keyframes at different times".

    The vanilla armor workbench has two sources of misalignment:
      - GearBBone/SpindleBone: single keys at vanilla's junk time (-447392) on
        some channels and 0 on others.
      - The SuperSpraySmoke emitters: genuinely 5/5/4 keys, real animation data.

    Whether the export works must not depend on rotate_bones_pretty -- it's a
    display option. It only decides whether a conversion runs; a bone with a
    rotated rest needs the same conversion with pretty off.
    """
    testfile = TTB.test_file(r"tests\FO4\WorkstationArmorB01.nif")

    for pretty in (True, False):
        TTB.clear_all()
        outfile = TTB.test_file(
            rf"tests\out\TEST_FO4_EULER_CURVES_UNALIGNED_{pretty}.nif", output=True)
        bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=True,
                                     rotate_bones_pretty=pretty)

        # The whole workbench, junk key times and all -- no cleanup, because this
        # is what a user actually exports.
        BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
        try:
            bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4',
                                         export_animations=True)
        except RuntimeError as e:
            # The unskinned shapes report unweighted verts, which bpy.ops raises
            # even though the nif is written (the report comes after the export).
            # Tolerate that one and nothing else.
            assert "unweighted vertices" in str(e), f"unexpected export error: {e}"

        nifcheck = pyn.NifFile(outfile)
        for bone in ['WorkstationArmorGearBBone', 'WorkstationArmorSpindleBone']:
            td = nifcheck.nodes[bone].controller.interpolator.data
            assert TT.is_eq(len(td.xrotations), len(td.yrotations),
                            f"pretty={pretty}: {bone} x/y channels aligned")
            assert TT.is_eq(len(td.xrotations), len(td.zrotations),
                            f"pretty={pretty}: {bone} x/z channels aligned")
            assert TT.is_gt(len(td.xrotations), 0,
                            f"pretty={pretty}: {bone} kept its keys")


@TT.category('FO4', 'ANIMATION')
def TEST_FO4_ROOT_ANIMATION():
    """A nif root node's own animation round-trips.

    Child nodes get their animation exported as they are created, but the root
    node isn't created on that path, so its animation used to be dropped without
    a word. The vanilla FO4 armor workbench animates from its root.

    The root is also the one node whose blender object name can't be matched to
    its nif node (the importer appends ":ROOT"), so the export resolves it from
    the ReprObject pairing rather than by name.
    """
    testfile = TTB.test_file(r"tests\FO4\WorkstationArmorB01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_FO4_ROOT_ANIMATION.nif", output=True)

    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=True,
                                 rotate_bones_pretty=True)
    BD.ObjectSelect([o for o in bpy.data.objects if 'pynRoot' in o], active=True)
    try:
        bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4',
                                     export_animations=True)
    except RuntimeError as e:
        assert "unweighted vertices" in str(e), f"unexpected export error: {e}"

    src = pyn.NifFile(testfile)
    dst = pyn.NifFile(outfile)
    assert dst.rootNode.controller, "root node kept its controller"

    srcdat = src.nodes['WorkstationArmorB01'].controller.interpolator.data
    dstdat = dst.rootNode.controller.interpolator.data
    assert TT.is_eq(dstdat.properties.rotationType, pyn.NiKeyType.XYZ_ROTATION_KEY,
                    "root rotation type")
    for chan in ('xrotations', 'yrotations', 'zrotations'):
        srckeys = getattr(srcdat, chan)
        dstkeys = getattr(dstdat, chan)
        assert TT.is_eq(len(dstkeys), len(srckeys), f"root {chan} key count")
        for s, d in zip(srckeys, dstkeys):
            assert TT.is_equiv(d.time, s.time, f"root {chan} key time", e=0.001)
            assert TT.is_equiv(d.value, s.value, f"root {chan} key value", e=0.001)


@TT.category('FO4', 'SHADER', 'ANIMATION')
def TEST_SHADER_LIGHTBULB():
    """Test that effect shader imports correctly."""
    testfile = TTB.test_file(r"tests\FO4\WorkshopLightbulbHanging01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_LIGHTBULB.nif")
    light_animations = ('On', 'Off', 'UnpoweredOn', 'UnpoweredOff', 'PoweringUpOn',
        'PoweringUpOff', 'PoweringDownOn', 'PoweringDownOff',)

    bpy.context.scene.render.fps = 60
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Shader correct
    obj = bpy.data.objects['BulbGlow:2']
    TT.assert_contains("Fallout 4 Effect", obj.active_material.node_tree.nodes, "Effect shader")
    TT.assert_eq(obj.active_material['BS_Shader_Block_Name'], "BSEffectShaderProperty", "Shader block name")
    assert obj.active_material.node_tree.nodes["Fallout 4 Effect"].inputs['Alpha Property'].is_linked, \
        "Alpha linked"
    
    # Animations loaded
    TT.assert_samemembers([b.name for b in bpy.data.actions],
                          light_animations,
                          "Light animations")

    ### EXPORT ###

    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    n = pyn.NifFile(outfile)
    TT.assert_contains('BulbGlow:2', n.shape_dict, "glow shape")
    TT.assert_contains('Bulb001:3', n.shape_dict, "bulb shape")

    TT.assert_samemembers(n.root.controller.sequences,
                          light_animations,
                          "exported light animations")

    TT.assert_equiv(n.root.controller.sequences['On'].text_key_data.keys[1][0], 
                    0.03333, 
                    "End time tag", e=0.001)


@TT.category('SKYRIM', 'SHADER', 'ANIMATION')
def TEST_ANIM_SHADER_GLOW():
    """Glow shader elements and other extra attributes work correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\armor\daedric\daedriccuirass_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_GLOW.nif")

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile)
    glow = bpy.data.objects['MaleTorsoGlow']

    # Check the shader
    shadernodes = glow.active_material.node_tree.nodes
    shader = shadernodes['Material Output'].inputs['Surface'].links[0].from_node
    alpha = shader.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, True, "Alpha Blend")
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, False, "Alpha Test")

    # Check the shader animation is correct.
    action = glow.active_material.node_tree.animation_data.action
    assert action.use_cyclic, f"Cyclic animation: {action.use_cyclic}"

    uv_node = shadernodes['UV_Converter']
    bpy.context.scene.frame_set(0)
    assert uv_node.inputs['Offset V'].default_value == 1, \
        f"V offset starts at 0: {uv_node.inputs['Offset V'].default_value}"
    bpy.context.scene.frame_set(400)
    assert 0.1 < uv_node.inputs['Offset V'].default_value < 0.9, f"V offset is changing: {uv_node.inputs['Offset V'].default_value}"
    bpy.context.scene.frame_set(0)

    ### WRITE ###

    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 export_colors=True,
                                 export_animations=True)

    ### CHECK ###

    # n = pyn.NifFile(testfile)
    nout = pyn.NifFile(outfile)
    CHK.Check_daedriccuirass(nout)


@TT.category('ANIMATION', 'FO4', 'PHYSICS')
def TEST_HIGHTECH_FLOORLIGHT():
    testfile = TTB.test_file(r"tests\FO4\Workshop_HighTechLightFloor05_On.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_HIGHTECH_FLOORLIGHT.nif")

    ### READ ###

    # Higher fps means more precision on timeline markers.
    bpy.context.scene.render.fps = 60

    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=True)

    assert 'Workshop_HighTechLightFloor05_On:0' in bpy.context.scene.objects
    light = bpy.context.scene.objects['Workshop_HighTechLightFloor05_On:0']

    TT.assert_samemembers(bpy.data.actions.keys(),
                          ("On", "Off", "UnpoweredOn", "UnpoweredOff",),
                          "Sequences")


    assert 'AddOnNode211' in bpy.context.scene.objects
    addon = bpy.context.scene.objects['AddOnNode211']
    TT.assert_eq(addon['pynBlockName'], 'BSValueNode', "Addon block name")
    TT.assert_eq(addon.pyn_valuenode.value, 211, "Addon value")
    TT.assert_eq(addon['pynValueNodeFlags'], '', "Addon flags")
    TT.assert_eq(json.loads(addon['pynActionSlots']),
                 json.loads('{"UnpoweredOn": "AddOnNode211", "On": "AddOnNode211", '
                 '"Off": "AddOnNode211", "UnpoweredOff": "AddOnNode211"}'),
                 "Addon action slots")

    # Sphere collision should be centered on the visual mesh, not at the origin.
    coll_shapes = [o for o in bpy.data.objects if o.name.startswith('bhkPhysicsSystem')]
    assert TT.is_eq(len(coll_shapes), 1, "One collision shape imported")
    coll_obj = coll_shapes[0]
    assert TT.is_eq(coll_obj.get('pynCollisionShapeType'), 'sphere',
                     "Collision shape is a sphere")
    mesh_bounds = TTB.world_bounds(light)
    coll_bounds = TTB.world_bounds(coll_obj)
    TTB.assert_bounds_overlap(coll_bounds, mesh_bounds, 5, "Sphere collision vs visual mesh")
    # The mesh sits on the z=0 floor plane in NIF space; if both the mesh and
    # collision are displaced upward by the body offset, this catches it.
    assert TT.is_lt(mesh_bounds[4], 2.0, "Visual mesh z-min near floor (z≈0)")


    ### EXPORT ###

    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if obj.get('pynRoot', False)],
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 export_animations=True)

    ### CHECK ###

    nif = pyn.NifFile(outfile)
    CHK.Check_HighTechLight(nif)


@TT.category('SKYRIM', 'SHADER', 'ANIMATION')
@TT.expect_errors(("Could not find texture", "Could not load"))
def TEST_ANIM_SHADER_FLOATDATA_NOINTERP():
    """NiFloatData with NO_INTERP key type imports as a linear animation, not an error."""
    # WhiteMushroom has a BSLightingShaderPropertyFloatController animating the emissive
    # multiple. Its NiFloatData stores key type 0 (NO_INTERP) with bare time/value keys
    # (no tangents). We used to log "NYI: NiFloatData type 0", leave an empty fcurve, and
    # then crash in _record_slot. Now we treat NO_INTERP as linear and import the keys.
    testfile = TTB.test_file(r"tests\SkyrimSE\WhiteMushroom.nif")

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile, import_animations=True)

    plane = TTB.find_object('Plane')
    nt = plane.active_material.node_tree

    # The shader animation imported.
    action = nt.animation_data.action
    assert action, "Shader has an animation action"

    fc = next((c for c in BD.action_fcurves(action)
               if c.data_path.endswith('"Emission Strength"].default_value')), None)
    assert fc, f"Found Emission Strength fcurve: {[c.data_path for c in BD.action_fcurves(action)]}"

    # Three keys: 0.05 -> 0.5 -> 0.05 (the glow pulse).
    TT.assert_eq(len(fc.keyframe_points), 3, "Number of keyframes")
    values = [kp.co[1] for kp in fc.keyframe_points]
    TT.assert_equiv(values[0], 0.05, "First key value", e=0.001)
    TT.assert_equiv(values[1], 0.5, "Middle key value", e=0.001)
    TT.assert_equiv(values[2], 0.05, "Last key value", e=0.001)
    # NO_INTERP keys have no tangents -> imported as linear.
    for kp in fc.keyframe_points:
        TT.assert_eq(kp.interpolation, 'LINEAR', "Keyframe interpolation")


@TT.category('SKYRIM', 'SHADER', 'ANIMATION')
def TEST_ANIM_SHADER_BSLSP():
    """Controllers on BSLightingShaders work correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\voidshade_1.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIM_SHADER_BSLSP.nif")

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TTB.find_object('head')

    # Check the shader
    shadernodes = head.active_material.node_tree.nodes
    shader = shadernodes['Material Output'].inputs['Surface'].links[0].from_node
    alpha = shader.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, True, "Alpha Blend")
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, False, "Alpha Test")

    # Check the shader animation is correct.
    action = head.active_material.node_tree.animation_data.action
    assert action.use_cyclic, f"Cyclic animation: {action.use_cyclic}"

    uv_node = shadernodes['UV_Converter']
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    TT.assert_eq(uv_node.inputs['Offset V'].default_value, 1, "Offset V")
    bpy.context.scene.frame_set(385)
    bpy.context.view_layer.update()
    assert 0.0 <= uv_node.inputs['Offset V'].default_value <= 0.5, f"V offset is changing: {uv_node.inputs['Offset V'].default_value}"
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    ### WRITE ###

    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 export_colors=True,
                                 export_animations=True)

    ### CHECK ###

    # n = pyn.NifFile(testfile)
    nout = pyn.NifFile(outfile)
    CHK.Check_voidshade(nout)


@TT.category('SKYRIM', 'SHADER', 'ANIMATION')
def TEST_SPRIGGAN():
    """Test that the special spriggan elements work correctly."""
    # Spriggan with limited controllers
    testfile = TTB.test_file(r"tests\Skyrim\spriggan.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SPRIGGAN.nif")
    bpy.context.scene.render.fps = 60

    ### READ ###

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Have a glow map
    bod = bpy.context.scene.objects['SprigganFxTestUnified:0']
    assert TT.is_eq(len([x for x in bod.active_material.node_tree.nodes 
                         if x.type=='TEX_IMAGE' and x.image 
                            and 'spriggan_g' in x.image.name.lower()]),
                        1,
                        "glow map")
    
    # Have all animations
    # act_names = [a.name.split('|') for a in bpy.data.actions if a.name.startswith('ANIM|')]
    expected_animations = [
        'LeavesLandedLoop',
        'LeavesScared',
        'LeavesAwayLoop',
        'LeavesLanding',
        'LeavesToHand',
        'LeavesOnHandLoop',
        'LeavesOffHand',
        'LeavesToHandDark',
        'LeavesOnHandDarkLoop',
        'LeavesOffHandDark',
        'KillFX',]
    assert TT.is_samemembers(bpy.data.actions.keys(), expected_animations, "Animation names")

    Spriggan_KillFX_Check(bpy.data.actions['KillFX'])
    Spriggan_LeavesLandedLoop_Check(bpy.data.actions['LeavesLandedLoop'])

    # Can properly apply KillFX 
    controller.apply_animation("KillFX", bpy.context.scene)
    handleaves = TTB.find_object("SprigganHandLeaves")
    bpy.context.scene.frame_current = 1
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    assert TT.is_equiv(handleaves.active_material.node_tree.nodes["AlphaProperty"]
                        .inputs["Alpha Threshold"].default_value,
                    255,
                    "Alpha Threshold at frame 1")
    bpy.context.scene.frame_current = 40
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    assert TT.is_equiv(handleaves.active_material.node_tree.nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value,
                    255,
                    "Alpha Threshold at frame 40")

    # Can properly apply LeavesLandedLoop 
    controller.apply_animation("LeavesLandedLoop", bpy.context.scene)
    bpy.context.scene.frame_current = 1
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    fxbody = TTB.find_object("SprigganFxTestUnified:0")
    assert TT.is_equiv(fxbody.active_material.node_tree.nodes["SkyrimShader:Default"]
                        .inputs["Emission Strength"].default_value,
                    8,
                    "Emission Strength at frame 1",
                    e=0.1)
    bpy.context.scene.frame_current = 21
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    assert TT.is_equiv(fxbody.active_material.node_tree.nodes["SkyrimShader:Default"]
                        .inputs["Emission Strength"].default_value,
                    6.0,
                    "Emission Strength at frame 21",
                    e=0.1)
    bpy.context.scene.frame_current = 43
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    assert TT.is_equiv(fxbody.active_material.node_tree.nodes["SkyrimShader:Default"]
                        .inputs["Emission Strength"].default_value,
                    13.189745,
                    "Emission Strength at frame 43",
                    e=0.1)

    
    ### WRITE ###
    
    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    testnif = pyn.NifFile(testfile)
    testbod = testnif.shape_dict['SprigganFxTestUnified:0']
    nifout = pyn.NifFile(outfile)
    bodout = nifout.shape_dict['SprigganFxTestUnified:0']
    assert bodout.shader.properties.shaderflags2_test(ShaderFlags2.GLOW_MAP), \
        f"Glow map flag is set"
    assert bodout.shader.textures['Glow'].lower().endswith('spriggan_g.dds')
    leavesout = nifout.shape_dict['SprigganBodyLeaves']
    assert TT.is_eq(leavesout.shader.blockname, 'BSEffectShaderProperty', f"Leaf shader block type")

    outcm:pyn.NiControllerManager = nifout.root.controller
    assert TT.is_equiv(outcm.properties.frequency, 1.0, "Controller Manager frequency")
    assert TT.is_samemembers([s for s in outcm.sequences], expected_animations, "Sequence names")
    for csname, cs in outcm.sequences.items():
        for cb in cs.controlled_blocks:
            assert cb.node_name is not None and cb.node_name != '', f"Have actual node name for sequence {csname}"    
            assert cb.property_type is not None and cb.property_type != '', f"Have actual property type for sequence {csname}"    
            assert cb.controller_type is not None and cb.controller_type != '', f"Have actual controller type for sequence {csname}"
            assert cb.interpolator.id != pyn.NODEID_NONE and cb.interpolator.id != 0, f"Have interpolator for sequence {csname}"
            assert cb.controller.id != pyn.NODEID_NONE and cb.controller.id != 0, f"Have controller for sequence {csname}"

    lllseq:pyn.NiControllerSequence = outcm.sequences['LeavesLandedLoop']
    bodyleavescb:pyn.ControllerLink = [b for b in lllseq.controlled_blocks 
                                       if b.node_name == 'SprigganBodyLeaves'][0]
    ctlr = bodyleavescb.controller
    isinstance(ctlr, pyn.BSNiAlphaPropertyTestRefController), f"Have alpha controller"
    # glow = nif.shape_dict["L2_WindowGlow"]
    # glowcheck = nifcheck.shape_dict["L2_WindowGlow"]

    # assert glow.blockname == glowcheck.blockname == "BSLODTriShape", \
    #     f"Created a LOD shape: {glowcheck.blockname}"
    # assert glow.properties.flags == glowcheck.properties.flags, f"Have correct flags: {glowcheck.properties.flags}"
    # assert glow.shader.blockname == glowcheck.shader.blockname, f"Have correct shader: {glowcheck.shader.blockname}"
    # ### Currently writing VERTEX_ALPHA even tho it wasn't originally set.
    # assert glow.shader.properties.Shader_Flags_1 == glowcheck.shader.properties.Shader_Flags_1, \
    #     f"Have correct shader flags 1: {pyn.ShaderFlags1(glow.shader.properties.Shader_Flags_1).fullname}"
    # assert glow.shader.properties.Shader_Flags_2 == glowcheck.shader.properties.Shader_Flags_2, \
    #     f"Have correct shader flags 1: {pyn.ShaderFlags1(glow.shader.properties.Shader_Flags_2).fullname}"
    # assert glow.shader.properties.LightingInfluence == glowcheck.shader.properties.LightingInfluence, \
    #     f"Have correct lighting influence: {glowcheck.shader.properties.LightingInfluence}"

    # win = nif.shape_dict["BlackBriarChalet:7"]
    # wincheck = nifcheck.shape_dict["BlackBriarChalet:7"]
    # assert BD.VNearEqual(win.shader.properties.parallaxInnerLayerTextureScale,
    #                      wincheck.shader.properties.parallaxInnerLayerTextureScale), \
    #     f"Have correct parallax: {wincheck.shader.properties.parallaxInnerLayerTextureScale}"
    # assert r"textures\cubemaps\ShinyGlass_e.dds" \
    #     == win.shader.textures['EnvMap'] == wincheck.shader.textures['EnvMap'], \
    #     f"Have correct envronment map: {wincheck.shader.textures['EnvMap']}"
    # assert r"textures\architecture\riften\RiftenWindowInner01.dds" \
    #     == win.shader.textures['InnerLayer'] == wincheck.shader.textures['InnerLayer'], \
    #     f"Have correct InnerLayer: {wincheck.shader.textures['InnerLayer']}"


@TT.category('FO4', 'SHADER', 'ANIMATION')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_SHADER_EFFECT_GLOWINGONE():
    """BSEffectShaderProperty attributes are read & written correctly."""
    testfile = TTB.test_file(r"tests\FO4\glowingoneTEST.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_EFFECT_GLOWINGONE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=False)

    # Check we have segments and subsegments.
    body = TTB.find_object("GlowingOneBody:0")
    TT.assert_contains('FO4 Seg 006 | 008 | Ghoul Foot.L', body.vertex_groups, "Foot segment")

    # Simplify.
    
    ### EXPORT ###

    # # Have to export the root object for the flags to carry over.
    BD.ObjectSelect([o for o in bpy.context.scene.objects if 'pynRoot' in o], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)

    # Make sure root node flags got carried over.
    TT.assert_eq(nifcheck.rootNode.properties.flags,
                 nif.rootNode.properties.flags,
                 "Root node flags")

    # The 'flash' body has an effect shader with alpha. The alpha node uses blending, but
    # with peculiar settings that seem to mimic translucency even tho the diffuse alpha is
    # opaque.
    glow = nif.shape_dict["GlowingOneBodyFlash:1"]
    glowcheck = nifcheck.shape_dict["GlowingOneBodyFlash:1"]

    # Check the shader.
    TT.assert_eq(glow.blockname, glowcheck.blockname, "BSSubIndexTriShape", "Shape type")
    TT.assert_eq(glow.properties.flags, glowcheck.properties.flags, "Shape flags")
    TT.assert_eq(glow.shader.blockname, glowcheck.shader.blockname, "Shader type")
    TT.assert_eq(glow.shader.properties.sourceTexture.upper(), 
                 glowcheck.shader.properties.sourceTexture.upper(), 
                 "Source texture")
    TT.assert_eq(glow.shader.properties.greyscaleTexture.upper(), 
                 glowcheck.shader.properties.greyscaleTexture.upper(), 
                 "Grayscale texture")
    
    # Shader knows it has a controller.
    assert glowcheck.shader.controller is not None, f"Shader has a controller"
    
    # Check the alpha
    alphacheck = glowcheck.alpha_property
    TT.assert_eq(alphacheck.properties.flags, 4109, "Alpha flags")

    # Regression: FO4 export must clear the ENVIRONMENT_MAPPING shader flag
    # on every shape (it's ignored by the engine but causes CTDs in practice).
    for shp in nifcheck.shapes:
        assert not shp.shader.properties.shaderflags1_test(pyn.ShaderFlags1.ENVIRONMENT_MAPPING), \
            f"FO4 export cleared ENVIRONMENT_MAPPING on {shp.name}"

    # "PartA" sequence has a color controller that affects the emissive color of
    # "GlowingOneGlowFXstreak:0". (Which is not emissive color at all--emissive color is
    # used for the palette color of the greyscale texture.)
    cm:pyn.NiControllerManager = nifcheck.rootNode.controller
    seq:pyn.NiControllerSequence = cm.sequences["partA"]
    cblist = [cb for cb in seq.controlled_blocks if cb.node_name == "GlowingOneGlowFXstreak:0"]
    TT.assert_samemembers([b.controller_type for b in cblist], 
                          ["BSEffectShaderPropertyColorController", 
                           "BSEffectShaderPropertyFloatController", 
                           "BSEffectShaderPropertyFloatController"],
                          "PartA Controller types")
    cb = [b for b in cblist if b.controller_type == "BSEffectShaderPropertyColorController"][0]
    
    # Interpolator data has reasonable values, including forward/back values.
    dat = cb.interpolator.data
    dat1 = dat.keys[1]
    TT.assert_equiv(dat1.time, 0.3, "Key 1 time")
    TT.assert_equiv(dat1.value[0], 0.894199, "Key 1 value")
    TT.assert_equiv(dat1.backward[0], -0.151786, "Key 1 backward", e=0.1)
    # head2 = nif2.shapes[0]

    # assert head2.has_alpha_property, f"Error: Did not write alpha property"
    # assert head2.alpha_property.properties.flags == head1.alpha_property.properties.flags, f"Error: Alpha flags incorrect: {head2.alpha_property.properties.flags} != {head1.alpha_property.properties.flags}"
    # assert head2.alpha_property.properties.threshold == head1.alpha_property.properties.threshold, f"Error: Alpha flags incorrect: {head2.alpha_property.properties.threshold} != {head1.alpha_property.properties.threshold}"

    # assert head2.textures['Diffuse'] == head1.textures['Diffuse'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['Diffuse']}' != '{head1.textures['Diffuse']}'"
    # assert head2.textures['Normal'] == head1.textures['Normal'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['Normal']}' != '{head1.textures['Normal']}'"
    # assert head2.textures['SoftLighting'] == head1.textures['SoftLighting'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['SoftLighting']}' != '{head1.textures['SoftLighting']}'"
    # assert head2.textures['Specular'] == head1.textures['Specular'], \
    #     f"Error: Texture paths not preserved: '{head2.textures['Specular']}' != '{head1.textures['Specular']}'"
    # dif = head2.shader.properties.compare(head1.shader.properties)
    # assert not dif, f"Error: Shader attributes not preserved: {dif}"


@TT.category('SKYRIMSE', 'ANIMATION', 'SHADER')
@TT.expect_errors( ("Some faces have been assigned to more than one partition",) )
def TEST_ALPHA_THRESHOLD_CHANGE():
    """Regression: Alpha threshold should not change on export."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\CRSTSkinKalaar.nif")
    outfile1 = TTB.test_file(r"tests\Out\TEST_ALPHA_THRESHOLD_CHANGE1.nif")
    outfile2 = TTB.test_file(r"tests\Out\TEST_ALPHA_THRESHOLD_CHANGE2.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    controller.apply_animation("stage1", bpy.context.scene)
    bpy.context.scene.frame_current = 1
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)

    obj = bpy.context.object
    mat = bpy.context.object.active_material
    alphanode = mat.node_tree.nodes['AlphaProperty']
    TT.assert_equiv(alphanode.inputs['Alpha Threshold'].default_value, 6.0, "Alpha Threshold pre-export")

    bpy.ops.export_scene.pynifly(filepath=outfile1, export_animations=True)
    TT.assert_equiv(alphanode.inputs['Alpha Threshold'].default_value, 6.0, "Alpha Threshold post-export")

    nifout = pyn.NifFile(outfile1)
    assert nifout.shapes[0].alpha_property.controller is not None, f"Have alpha property controller"

    # The alpha property can have only one controller, so all sequences must reference it.
    TT.assert_samemembers(nifout.root.controller.sequences.keys(),
                          ("stage1", "stage2", "stage3"),
                          "animation sequences")
    TT.assert_eq(nifout.root.controller.sequences['stage1'].controlled_blocks[0].controller.id,
                 nifout.root.controller.sequences['stage2'].controlled_blocks[0].controller.id,
                 "alpha property controller")
    TT.assert_eq(nifout.root.controller.sequences['stage1'].controlled_blocks[0].controller.id,
                 nifout.root.controller.sequences['stage3'].controlled_blocks[0].controller.id,
                 "alpha property controller")
    

# ANIMATION: asserts an imported action exists, and animation import is gated on
# bpy.types.ActionSlot (Blender 4.4+), so there are no actions below that.
@TT.category('FO4', 'CONNECTPOINT', 'ANIMATION')
def TEST_WORKSHOP_DOOR_CONNECT_POINTS():
    """Workshop door connect points positioned correctly on export."""
    
    testfile = TTB.test_file(r"tests\FO4\Workshop_BldWoodPDoor02.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_WORKSHOP_DOOR_CONNECT_POINTS.nif")
    
    # Set FPS to 30
    bpy.context.scene.render.fps = 30
    
    # Import the workshop door
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 rename_bones=False, 
                                 create_bones=False)
    
    # Check animation frame range
    assert TT.is_gt(len(bpy.data.actions), 0, "Door has at least one action")
    act = bpy.data.actions[0]
    assert TT.is_eq(int(act.frame_start), 1, "Action frame start")
    assert TT.is_eq(int(act.frame_end), 34, "Action frame end")
    
    # Find parent connect points
    cp_parents = [obj for obj in bpy.context.scene.objects 
                  if obj.name.startswith('BSConnectPointParents')]
    
    TT.assert_eq(len(cp_parents), 2, "Workshop door should have 2 parent connect points")
    
    # Store original positions for comparison
    original_positions = {}
    for cp in cp_parents:
        cp_name = cp.name.split("::")[1] if "::" in cp.name else cp.name
        original_positions[cp_name] = cp.matrix_world.translation.copy()
        log.info(f"Original {cp_name} position: {cp.matrix_world.translation}")
    
    # Export back out
    root_obj = next(o for o in bpy.context.scene.objects if 'pynRoot' in o)
    bpy.ops.object.select_all(action='DESELECT')
    root_obj.select_set(True)
    bpy.context.view_layer.objects.active = root_obj
    
    bpy.ops.export_scene.pynifly(filepath=outfile,
                                  target_game='FO4',
                                  intuit_defaults=False,
                                  rename_bones=False)

    # Load and check the exported NIF
    TTB.stage_materials_for(testfile, outfile)
    nif_original = pyn.NifFile(testfile)
    nif_exported = pyn.NifFile(outfile)
    
    # Should have same number of parent connect points
    TT.assert_eq(len(nif_exported.connect_points_parent), 
                 len(nif_original.connect_points_parent),
                 "Connect point count should match")
    
    # Check that all exported animation keys have end time of 1.2
    for seq_name, seq in nif_exported.root.controller.sequences.items():
        for cb in seq.controlled_blocks:
            if cb.interpolator and hasattr(cb.interpolator, 'keys'):
                for key_group in cb.interpolator.keys:
                    if key_group and len(key_group.keys) > 0:
                        last_key = key_group.keys[-1]
                        TT.assert_equiv(last_key.time, 1.2, 
                            f"Animation key end time for {seq_name}:{cb.target_name}", 
                            e=0.001)
    
    # Check each parent connect point position
    for cp_orig in nif_original.connect_points_parent:
        cp_name = cp_orig.name.decode('utf-8')
        
        # Find matching connect point in exported file
        cp_exported = None
        for cp in nif_exported.connect_points_parent:
            if cp.name.decode('utf-8') == cp_name:
                cp_exported = cp
                break
        
        TT.assert_ne(cp_exported, None, f"Connect point {cp_name} should exist in exported file")
        
        # Check translation (position)
        orig_trans = cp_orig.translation
        exp_trans = cp_exported.translation
        
        TT.assert_equiv(exp_trans, orig_trans, 
                        f"Connect point {cp_name} translation", e=0.001)
        
        # Check rotation 
        orig_rot = cp_orig.rotation
        exp_rot = cp_exported.rotation
        
        TT.assert_equiv(exp_rot, orig_rot, 
                        f"Connect point {cp_name} rotation", e=0.001)
        
        log.info(f"Connect point {cp_name} positioning verified - translation: {exp_trans}, rotation: {exp_rot}")


@TT.category('FO4', 'ANIMATION')
def TEST_PIPBOY():
    """
    Test pipboy import/export. Very complex node hierarchy. Animations on multiple nodes
    but no controller sequences.
    """

    def cmp_xf(a, b):
        axf = BD.transform_to_matrix(a.global_transform)
        bxf = BD.transform_to_matrix(b.global_transform)
        assert TTB.MatNearEqual(axf, bxf), f"{a.name} transform preserved: \n{axf}\n != \n{bxf}"

    testfile = TTB.test_file(r"tests\FO4\PipBoy_Simple.nif")
    outfile = TTB.test_file(f"tests/Out/TEST_PIPBOY.nif", output=1)

    bpy.ops.import_scene.pynifly(filepath=testfile)
    TT.assert_true(bpy.data.objects['TapeDeckLid'].animation_data is not None, \
                   "TapeDeckLid animation data")
    
    # Animation has all keyframes.
    TT.assert_eq(max([fc.keyframe_points[-1].co[0] 
                        for fc in BD.action_fcurves(bpy.data.objects['TapeDeckLid']
                                                    .animation_data.action)]), 
                      57, 
                      "Max keyframe")
    TT.assert_eq(int(bpy.data.objects['TapeDeckLid'].animation_data.action.frame_end), 57, "Action end frame")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', 
                                 preserve_hierarchy=True,
                                 export_animations=True)

    nifcheck = pyn.NifFile(outfile)
    TT.assert_true(nifcheck.nodes.get("PipboyBody"), f"Exported PipboyBody")
    TT.assert_true(nifcheck.nodes.get("TapeDeck01"), f"Exported TapeDeck01")
    TT.assert_eq(nifcheck.nodes["TapeDeck01"].parent.name, nifcheck.nodes["PipboyBody"].name, 
                 f"TapeDeck01 parent")
    TT.assert_eq(nifcheck.nodes["TapeDeckLid"].parent.name, nifcheck.nodes["TapeDeck01"].name, 
                 f"TapeDeckLid parent")
    TT.assert_eq(nifcheck.nodes["TapeDeckLid_mesh"].parent.name, nifcheck.nodes["TapeDeckLid"].name, 
                 f"TapeDeckLid_mesh parent")
    TT.assert_eq(nifcheck.shape_dict["TapeDeckLid_mesh:1"].parent.name,
                 nifcheck.nodes["TapeDeckLid_mesh"].name, 
                 f"TapeDeckLid_mesh:1 parent")

    niftest = pyn.NifFile(testfile)

    cmp_xf(nifcheck.nodes["TapeDeck01"], niftest.nodes["TapeDeck01"])
    cmp_xf(nifcheck.nodes["TapeDeckLid"], niftest.nodes["TapeDeckLid"])
    cmp_xf(nifcheck.nodes["TapeDeckLid_mesh"], niftest.nodes["TapeDeckLid_mesh"])
    cmp_xf(nifcheck.shape_dict["TapeDeckLid_mesh:1"], niftest.shape_dict["TapeDeckLid_mesh:1"])

    assert nifcheck.rootNode.controller is None, "Root controller is None"
    assert nifcheck.nodes["PipboyBody"].controller is not None, "PipboyBody controller is not None"
    assert nifcheck.nodes["TapeDeckLid"].controller is not None, "TapeDeckLid controller is not None"
    

@TT.category('FO4', 'ANIMATION')
@TT.expect_errors(("Target of controller not found",))
def TEST_ANIM_ANIMATRON():
    """Can read a FO4 animatron nif"""
    # The animatrons are very complex and their pose and bind positions are different. The
    # two shapes have slightly different bind positions, though they are a small offset
    # from each other.

    testfile = TTB.test_file(r"tests/FO4/AnimatronicNormalWoman-body.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIM_ANIMATRON.nif")
    outfile_fb = TTB.test_file(r"tests/Out/TEST_ANIM_ANIMATRON.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False, 
                                 rename_bones=False, 
                                 import_pose=False)

    sh = TTB.find_shape('BodyLo:0')
    arms = TTB.find_shape('BodyLo:1')
    minv, maxv = TTB.get_obj_bbox(sh)
    assert NT.VNearEqual(minv, Vector((-13.14, -7.83, 38.6)), 0.1), f"Bounding box min correct: {minv}"
    assert NT.VNearEqual(maxv, Vector((14.0, 12.66, 133.5)), 0.1), f"Bounding box max correct: {maxv}"


    arma = arms.modifiers[0].object
    spine2 = arma.data.bones['SPINE2']
    hand = arma.data.bones['RArm_Hand']
    handpose = arma.pose.bones['RArm_Hand']
    assert spine2.matrix_local.translation.z > 30, f"SPINE2 in correct position: {spine2.matrix_local.translation}"
    assert NT.VNearEqual(handpose.matrix.translation, [18.1848, 2.6116, 68.6298]), f"Hand position matches Nif: {handpose.matrix.translation}"

    # thighl = arma.data.bones['LLeg_Thigh']
    # cp_armorleg = TTB.find_shape("BSConnectPointParents::P-ArmorLleg", type='EMPTY')
    # assert cp_armorleg["pynConnectParent"] == "LLeg_Thigh", f"Connect point has correct parent: {cp_armorleg['pynConnectParent']}"
    # assert NT.VNearEqual(cp_armorleg.location, thighl.matrix_local.translation, 0.1), \
    #     f"Connect point at correct position: {cp_armorleg.location} == {thighl.matrix_local.translation}"

    assert arma, f"Found armature '{arma.name}'"
    lleg_thigh = arma.data.bones['LLeg_Thigh']
    assert lleg_thigh.parent, f"LLeg_Thigh has parent"
    assert lleg_thigh.parent.name == 'Pelvis', f"LLeg_Thigh parent is {lleg_thigh.parent.name}"

    # EXPORT

    bpy.ops.object.select_all(action='DESELECT')
    sh.select_set(True)
    TTB.find_shape('BodyLo:1').select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, 
                                 target_game='FO4', 
                                 preserve_hierarchy=True,
                                 export_pose=True,
                                 intuit_defaults=False)

    impnif = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile_fb)
    sh_out = nifout.shapes[0]
    assert sh_out.name == 'BodyLo:0', f"Exported shape: {sh_out.name}"
    minv_out, maxv_out = TTB.get_shape_bbox(sh_out)
    assert NT.VNearEqual(minv_out, minv), f"Minimum bounds equal: {minv_out} == {minv}"
    assert NT.VNearEqual(maxv_out, maxv), f"Minimum bounds equal: {maxv_out} == {maxv}"
    sp2_out = nifout.nodes['SPINE2']
    assert sp2_out.parent.name == 'SPINE1', f"SPINE2 has parent {sp2_out.parent.name}"
    sp2_in = impnif.nodes['SPINE2']
    assert TTB.MatNearEqual(BD.transform_to_matrix(sp2_out.transform), BD.transform_to_matrix(sp2_in.transform)), \
        f"Transforms are equal: \n{sp2_out.transform}\n==\n{sp2_in.transform}"


@TT.category('FO4', 'ANIMATION')
@TT.expect_errors(("Target of controller not found", "Unknown block type: NiBoolData",))
def TEST_ANIMATRON_2():
    """Can read the FO4 astronaut animatron nif"""
    # The animatrons are very complex and their pose and bind positions are different. The
    # two shapes have slightly different bind positions, though they are a small offset
    # from each other.
    testfile = TTB.test_file(r"tests\FO4\AnimatronicSpaceMan.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ANIMATRON_2.nif")
    outfile_fb = TTB.test_file(r"tests/Out/TEST_ANIMATRON_2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False, 
                                 rename_bones=False, 
                                 import_pose=True)


@TT.category('SKYRIM', 'HKX', 'ARMATURE')
def TEST_SKEL_HKX_IMPORT():
    """Skeletons can be imported from HKX files."""
    testfile = TTB.test_file("tests/Skyrim/skeleton.hkx")
    # outfile = TTB.test_file("tests/out/TEST_SKEL_HKX.xml")

    # bpy.ops.import_scene.skeleton_xml(filepath=testfile)
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile)

    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')

    rootbone = arma.data.bones["NPC Root"]
    assert rootbone, f"Have root bone"

    headbone = arma.data.bones["NPC Head"]
    handbone = arma.data.bones["NPC Hand.L"]
    assert BD.NearEqual(headbone.matrix_local.translation[2], 120.3436), f"Head bone where it should be" 
    assert BD.NearEqual(handbone.matrix_local.translation[0], -28.9358), f"L Hand bone where it should be" 
    assert headbone.parent.name == "NPC Neck", f"Bone has correct parent."
    # bonesvert = sorted(arma.data.bones, key=lambda b: b.matrix_local.translation)
    # assert BD.NearEqual(bonesvert[0].matrix_local.translation[2], 0), f"Lowest bone at 0"
    # assert BD.NearEqual(bonesvert[-1].matrix_local.translation[2], 124), f"Highest bone near 124"

    BD.ObjectSelect([arma], active=True)


@TT.category('SKYRIM', 'FO4', 'HKX', 'ARMATURE')
@TT.parameterize(("game",     "blendxf",  "pretty"),
                 [('SKYRIM',  "NATURAL",  "NIF"),
                  ('SKYRIM',  "BLENDER",  "NIF"),
                  ('SKYRIM',  "NATURAL",  "PRETTY"),
                  ('SKYRIM',  "BLENDER",  "PRETTY"),
                  ('FO4',     "NATURAL",  "NIF"),
                  ('FO4',     "BLENDER",  "NIF"),
                  ('FO4',     "NATURAL",  "PRETTY"),
                  ('FO4',     "BLENDER",  "PRETTY"),
                  ])
def TEST_HKX_SKEL_ORIENT(game, blendxf, pretty):
    """HKX skeleton import honors blender-orientation and pretty-bone settings (issue #377).

    The blender transform must ride on the armature OBJECT (so the skeleton scales
    and rotates to match a blender_xf NIF import), while the bones stay in NIF space
    -- optionally with the per-game pretty rotation baked in.
    """
    from io_scene_nifly.hkx import anim_skyrim, anim_fo4

    is_blender = (blendxf == "BLENDER")
    is_pretty = (pretty == "PRETTY")

    if game == 'SKYRIM':
        testfile = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
        skel = anim_skyrim.load_skyrim_skeleton(testfile)
        axis = 'Z'
        root_name, head_name = "NPC Root [Root]", "NPC Head [Head]"
    else:
        testfile = TTB.test_file(r"tests\FO4\skeleton_vanilla.hkx")
        skel = anim_fo4.load_fo4_skeleton(testfile)
        axis = 'X'
        root_name, head_name = "Root", "Head"

    bpy.ops.import_scene.pynifly_hkx(filepath=testfile,
                                     blender_xf=is_blender,
                                     rotate_bones_pretty=is_pretty,
                                     rename_bones=False)

    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')

    # 1. The blender transform lives on the armature object, not the bones.
    expected_obj = BD.blender_import_xf if is_blender else Matrix.Identity(4)
    assert TTB.MatNearEqual(arma.matrix_world, expected_obj, epsilon=0.0001), \
        f"Armature object transform ({blendxf}):\n{arma.matrix_world}\n!=\n{expected_obj}"

    # 2. Bones stay in NIF space (plus pretty rotation), independent of blender_xf.
    gxf = _hkx_skel_globals(skel)
    R = BD.game_rotations_pretty[axis][0] if is_pretty else Matrix.Identity(4)
    for nif_name in (root_name, head_name):
        idx = skel.bones.index(nif_name)
        expected_local = gxf[idx] @ R
        bone = arma.data.bones[nif_name]
        assert TTB.MatNearEqual(bone.matrix_local, expected_local, epsilon=0.001), \
            f"Bone '{nif_name}' matrix_local ({blendxf}/{pretty}):" \
            f"\n{bone.matrix_local}\n!=\n{expected_local}"

    # 3. World position scales/rotates with blender_xf (and is pretty-invariant,
    #    since the pretty rotation has no translation component).
    head_idx = skel.bones.index(head_name)
    head_world = (arma.matrix_world @ arma.data.bones[head_name].matrix_local).translation
    expected_world = (expected_obj @ gxf[head_idx]).translation
    assert NT.VNearEqual(head_world, expected_world, 0.001), \
        f"Head bone world position ({blendxf}/{pretty}): {head_world[:]} != {expected_world[:]}"


@TT.category('SKYRIM', 'FO4', 'HKX', 'ARMATURE')
@TT.parameterize(("game",     "blendxf",  "pretty"),
                 [('SKYRIM',  "NATURAL",  "NIF"),
                  ('SKYRIM',  "BLENDER",  "NIF"),
                  ('SKYRIM',  "NATURAL",  "PRETTY"),
                  ('SKYRIM',  "BLENDER",  "PRETTY"),
                  ('FO4',     "NATURAL",  "NIF"),
                  ('FO4',     "BLENDER",  "NIF"),
                  ('FO4',     "NATURAL",  "PRETTY"),
                  ('FO4',     "BLENDER",  "PRETTY"),
                  ])
def TEST_HKX_SKEL_ORIENT_ROUNDTRIP(game, blendxf, pretty):
    """A skeleton imported under any blender_xf/pretty combo exports back to its
    original raw-NIF reference pose (issue #377 export side)."""
    from io_scene_nifly.hkx import anim_skyrim, anim_fo4

    is_blender = (blendxf == "BLENDER")
    is_pretty = (pretty == "PRETTY")

    if game == 'SKYRIM':
        testfile = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
        load = anim_skyrim.load_skyrim_skeleton
    else:
        testfile = TTB.test_file(r"tests\FO4\skeleton_vanilla.hkx")
        load = anim_fo4.load_fo4_skeleton
    outfile = TTB.test_file(rf"tests\Out\TEST_HKX_SKEL_ORIENT_RT_{game}_{blendxf}_{pretty}.hkx")

    bpy.ops.import_scene.pynifly_hkx(filepath=testfile, rename_bones=False,
                                     blender_xf=is_blender, rotate_bones_pretty=is_pretty)
    arma = next(x for x in bpy.data.objects if x.type == 'ARMATURE')

    BD.ObjectSelect([arma], active=True)
    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        (b if hasattr(b, 'select') else b.bone).select = True
    bpy.ops.export_scene.skeleton_hkx(filepath=outfile)
    bpy.ops.object.mode_set(mode='OBJECT')

    src = load(testfile)
    out = load(outfile)
    src_pose = {n: src.reference_pose[i] for i, n in enumerate(src.bones)}
    out_pose = {n: out.reference_pose[i] for i, n in enumerate(out.bones)}

    for name, sp in src_pose.items():
        op = out_pose[name]
        assert NT.VNearEqual(sp.translation, op.translation, 0.01), \
            f"{game} {blendxf}/{pretty}: bone '{name}' translation {sp.translation} != {op.translation}"
        # Quaternions are sign-ambiguous.
        dot = sum(a * b for a, b in zip(sp.rotation, op.rotation))
        sign = 1 if dot >= 0 else -1
        for j in range(4):
            assert abs(sp.rotation[j] - sign * op.rotation[j]) < 0.01, \
                f"{game} {blendxf}/{pretty}: bone '{name}' rotation[{j}] " \
                f"{sp.rotation[j]:.5f} != {op.rotation[j]:.5f}"


@TT.category('SKYRIM', 'HKX', 'ARMATURE')
def TEST_SKEL_XML():
    """Can export selected bones as a skeleton XML file."""
    # TODO: Decide if this functionality is worth it, or whether we should turn this into 
    # exporting in HKX format. Note TEST_SKEL_TAIL_HKX tests export in HKX format.
    testfile = TTB.test_file("tests/Skyrim/skeletonbeast_vanilla.nif")
    outfile = TTB.test_file("tests/out/TEST_SKEL_XML.xml")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    arma = bpy.data.objects[BD.arma_name('skeletonBeast.nif')]
    BD.ObjectSelect([arma], active=True)

    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        if hasattr(b.bone, 'select'):
            b.bone.select = b.name.startswith('TailBone')
        else:
            # Blender >= 5.0
            b.select = b.name.startswith('TailBone')

    bpy.ops.export_scene.skeleton_xml(filepath=outfile)

    xcheck = xml.parse(outfile)
    xroot = xcheck.getroot()

    # Check we have various key elements
    assert xroot.tag == 'hkpackfile', f"Type is hkpackfile: {xroot.tag}"
    xsec = xroot[0]
    assert xsec.tag == 'hksection', f"Type is hksection: {xsec.tag}"
    assert xsec.attrib['name'] == "__data__", f"Have correct name on section: {xsec.attrib['name']}"
    assert len(xsec[:]) > 0, f"Have children: {xsec[:]}"
    xskel = [x for x in xsec if x.attrib['class'] == 'hkaSkeleton']
    assert len(xskel) > 0, f"Have skeletons: {xskel}"
    assert xskel[0].tag == 'hkobject', f"Type is hkobject: {xskel[0].tag}"
    nameparam = xskel[0].find("./hkparam[@name='name']")
    assert nameparam.text == 'TailBone01', f"Name parameter correct: {nameparam.text}"
    xbones = xskel[0].find("./hkparam[@name='bones']")
    assert xbones is not None, f"Have bones: {xbones}"
    xpose = xskel[0].find("./hkparam[@name='referencePose']")
    assert xpose is not None, f"Have pose: {xpose}"

    # RootLevelContainer has forward references to animation and memory resource
    # containers. Make sure they are correct.
    rlc = xroot.find("./hksection/hkobject[@class='hkRootLevelContainer']/hkparam[@name='namedVariants']")
    ch1 = rlc[0]
    class1 = ch1.find("./hkparam[@name='className']").text
    var1 = ch1.find("./hkparam[@name='variant']").text
    assert class1 in ['hkaAnimationContainer', 'hkMemoryResourceContainer'], f"Found correct forward ref: {class1}"
    ref1 = xsec.find(f"./hkobject[@name='{var1}']")
    assert ref1 != None, f"Found forward ref {var1}"
    assert ref1.attrib['class'] == class1, f"Forward ref correct: {ref1.attrib['class']} == {class1}"
    ch2 = rlc[1]
    class2 = ch2.find("./hkparam[@name='className']").text
    var2 = ch2.find("./hkparam[@name='variant']").text
    assert class2 in ['hkaAnimationContainer', 'hkMemoryResourceContainer'], f"Found correct forward ref: {class2}"
    ref2 = xsec.find(f"./hkobject[@name='{var2}']")
    assert ref2 != None, f"Found forward ref {var2}"
    assert ref2.attrib['class'] == class2, f"Forward ref correct: {ref2.attrib['class']} == {class2}"

    # Similar for hkaAnimationContainer
    skelref = xroot.find("./hksection/hkobject[@class='hkaAnimationContainer']/hkparam[@name='skeletons']")
    assert xskel[0].attrib['name'] == skelref.text, f"Forward ref correct: {xskel[0].attrib['name']} == {skelref.text}"

    incheck = pyn.NifFile(testfile)
    outcheck = pyn.hkxSkeletonFile(outfile)
    inhead = incheck.nodes["TailBone05"]
    outhead = outcheck.nodes["TailBone05"]
    assert inhead.properties.transform.NearEqual(outhead.properties.transform), f"Have same tail transform"


@TT.category('SKYRIM', 'HKX', 'ARMATURE')
def TEST_SKEL_TAIL_HKX():
    """Can import and export a HKX skeleton file."""
    from io_scene_nifly.hkx import anim_skyrim

    testfile = TTB.test_file(r"tests\Skyrim\tailskeleton.hkx")
    outfile = TTB.test_file("tests/out/TEST_SKEL_TAIL_HKX.hkx")

    # Load ground truth from the XML skeleton
    orig = anim_skyrim.load_skyrim_skeleton(testfile)
    assert orig is not None, "Failed to load tail skeleton"

    # Import via operator
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile,
                                     blender_xf=False,
                                     rename_bones=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma and arma.type=='ARMATURE', f"Loaded armature: {arma}"
    bpy.ops.object.select_all(action='DESELECT')
    BD.ObjectSelect([arma], active=True)

    # Export via operator
    bpy.ops.export_scene.skeleton_hkx(filepath=outfile, game='SKYRIM_SE')

    # Read back and compare against ground truth
    rt = anim_skyrim.load_skyrim_skeleton(outfile)
    assert rt is not None, "Failed to reload exported skeleton"
    assert len(rt.bones) == len(orig.bones), \
        f"Bone count: {len(rt.bones)} vs {len(orig.bones)}"

    for i in range(len(orig.bones)):
        assert rt.bones[i] == orig.bones[i], \
            f"Bone {i} name: '{rt.bones[i]}' vs '{orig.bones[i]}'"
        assert rt.parents[i] == orig.parents[i], \
            f"Bone {orig.bones[i]} parent: {rt.parents[i]} vs {orig.parents[i]}"
        a = orig.reference_pose[i]
        b = rt.reference_pose[i]
        for j in range(3):
            assert abs(a.translation[j] - b.translation[j]) < 0.001, \
                f"{orig.bones[i]} translation[{j}]: {a.translation[j]:.6f} vs {b.translation[j]:.6f}"
        dot = sum(x * y for x, y in zip(a.rotation, b.rotation))
        sign = 1 if dot >= 0 else -1
        for j in range(4):
            assert abs(a.rotation[j] - sign * b.rotation[j]) < 0.001, \
                f"{orig.bones[i]} rotation[{j}]: {a.rotation[j]:.6f} vs {b.rotation[j]:.6f}"

    # Re-import the output and compare armature matrices
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile,
                                     blender_xf=False,
                                     rename_bones=False)

    armacheck = bpy.context.object
    assert TTB.MatNearEqual(arma.data.bones['TailBone01'].matrix_local,
                           armacheck.data.bones['TailBone01'].matrix_local), \
        f"Have matching transforms."


@TT.category('SKYRIM', 'HKX', 'ARMATURE')
def TEST_AUXBONES_EXTRACT():
    """Can extract an auxbones skeleton from a full skeleton."""
    from io_scene_nifly.hkx import anim_skyrim

    testfile = TTB.test_file(r"tests\Skyrim\skeletonbeast_vanilla.nif")
    outfile = TTB.test_file("tests/out/TEST_AUXBONES_EXTRACT.hkx")
    checkfile = TTB.test_file(r"tests\Skyrim\tailskeleton.hkx")

    # Load the reference tail skeleton for comparison
    check_skel = anim_skyrim.load_skyrim_skeleton(checkfile)
    assert check_skel is not None, "Failed to load reference tail skeleton"

    # Import the full beast skeleton NIF
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 blender_xf=False,
                                 rename_bones=False,
                                 import_collisions=False)

    arma = bpy.context.object
    assert arma and arma.type=='ARMATURE', f"Loaded armature: {arma}"

    # Select only TailBone bones for export
    bpy.ops.object.mode_set(mode='POSE')
    for b in arma.pose.bones:
        sel = ("TailBone" in b.name)
        if hasattr(b, 'select'):
            b.select = sel
        else:
            b.bone.select = sel

    bpy.ops.export_scene.skeleton_hkx(filepath=outfile, game='SKYRIM_SE')

    # Read back and compare against reference tail skeleton
    out_skel = anim_skyrim.load_skyrim_skeleton(outfile)
    assert out_skel is not None, "Failed to reload exported skeleton"
    assert len(out_skel.bones) == len(check_skel.bones), \
        f"Bone count: {len(out_skel.bones)} vs {len(check_skel.bones)}"

    for i in range(len(check_skel.bones)):
        assert out_skel.bones[i] == check_skel.bones[i], \
            f"Bone {i} name: '{out_skel.bones[i]}' vs '{check_skel.bones[i]}'"
        assert out_skel.parents[i] == check_skel.parents[i], \
            f"Bone {check_skel.bones[i]} parent: {out_skel.parents[i]} vs {check_skel.parents[i]}"
        a = check_skel.reference_pose[i]
        b = out_skel.reference_pose[i]
        for j in range(3):
            assert abs(a.translation[j] - b.translation[j]) < 0.001, \
                f"{check_skel.bones[i]} translation[{j}]: {a.translation[j]:.6f} vs {b.translation[j]:.6f}"
        dot = sum(x * y for x, y in zip(a.rotation, b.rotation))
        sign = 1 if dot >= 0 else -1
        for j in range(4):
            assert abs(a.rotation[j] - sign * b.rotation[j]) < 0.001, \
                f"{check_skel.bones[i]} rotation[{j}]: {a.rotation[j]:.6f} vs {b.rotation[j]:.6f}"


@TT.category('SKYRIMSE', 'HKX', 'ARMATURE')  
def TEST_HKX_SKELETON_ROUNDTRIP():
    """Test HKX skeleton export/import round-trip maintains correct transforms."""
    testfile = TTB.test_file(r"tests\Skyrim\skeever_skeleton.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_HKX_SKELETON_ROUNDTRIP.hkx")

    # Import original NIF skeleton into its own collection
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 blender_xf=False,
                                 rename_bones=False,
                                 rename_bones_niftools=False,
                                 import_collisions=False,
                                 create_collection=True)

    original_arma = bpy.context.object
    assert original_arma and original_arma.type == 'ARMATURE', \
        f"Loaded original armature: {original_arma}"

    # Store original bone transforms for comparison
    original_transforms = {}
    original_parents = {}
    for bone in original_arma.data.bones:
        original_transforms[bone.name] = bone.matrix_local.copy()
        original_parents[bone.name] = bone.parent.name if bone.parent else None

    # Export as HKX skeleton — select all bones
    bpy.ops.object.mode_set(mode='POSE')
    for b in original_arma.pose.bones:
        if hasattr(b, 'select'):
            b.select = True  # Blender >= 5.0
        else:
            b.bone.select = True

    bpy.ops.export_scene.skeleton_hkx(filepath=outfile)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Re-import the HKX skeleton into its own collection so bone names don't
    # collide with the original armature.
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile,
                                     rename_bones=False,
                                     rename_bones_niftools=False,
                                     blender_xf=False,
                                     create_collection=True)

    reimported_arma = bpy.context.object
    assert reimported_arma and reimported_arma.type == 'ARMATURE', \
        f"Failed to reimport armature from HKX: {reimported_arma}"
    assert reimported_arma is not original_arma, "Reimport returned the same armature"
    
    # Verify bone count matches
    original_bone_names = set(original_transforms.keys())
    reimported_bone_names = set(bone.name for bone in reimported_arma.data.bones)
    assert original_bone_names == reimported_bone_names, \
        f"Bone names differ: Original {original_bone_names} vs Reimported {reimported_bone_names}"
    
    # Verify transforms match using TT.is_equiv
    for bone in reimported_arma.data.bones:
        original_mx = original_transforms[bone.name]
        reimported_mx = bone.matrix_local
        
        # Check full matrix with more lenient tolerance for HKX round-trip
        assert TT.is_equiv(reimported_mx, original_mx, f"Bone {bone.name} matrix", e=0.001), \
            f"Bone {bone.name} matrix differs"
        
        # Check parent relationships
        original_parent = original_parents[bone.name]
        reimported_parent = bone.parent.name if bone.parent else None
        assert original_parent == reimported_parent, \
            f"Bone {bone.name} parent differs: Original {original_parent} vs Reimported {reimported_parent}"


@TT.category('SKYRIMSE', 'HKX', 'ARMATURE')
def TEST_HKX_SKELETON_VANILLA_ROUNDTRIP():
    """Import vanilla skeleton.hkx via operator, export via operator, verify output."""
    from io_scene_nifly.hkx import anim_skyrim

    testfile = TTB.test_file(r"tests\SkyrimSE\skeleton_vanilla.hkx")
    outfile = TTB.test_file(r"tests\Out\TEST_HKX_SKELETON_VANILLA_ROUNDTRIP.hkx")

    # Import via Blender operator
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile,
                                      rename_bones=False,
                                      rename_bones_niftools=False,
                                      blender_xf=False,
                                      create_collection=True)

    arma = bpy.context.object
    assert arma and arma.type == 'ARMATURE', f"Expected armature, got {arma}"

    # Export via Blender operator
    bpy.ops.export_scene.skeleton_hkx(filepath=outfile, game='SKYRIM_SE')

    # Read back with library call and verify against hard-coded ground truth
    rt = anim_skyrim.load_skyrim_skeleton(outfile)
    assert rt is not None, "Failed to reload exported skeleton"
    assert len(rt.bones) == 99, f"Expected 99 bones, got {len(rt.bones)}"

    def quat_diff(a_rot, b_rot):
        dot = sum(x * y for x, y in zip(a_rot, b_rot))
        sign = 1 if dot >= 0 else -1
        return [abs(a_rot[j] - sign * b_rot[j]) for j in range(4)]

    # Hard-coded ground truth from vanilla skeleton_vanilla.hkx
    # (bone_name, parent_idx, translation, rotation)
    ground_truth = [
        ('NPC Root [Root]', -1,
         (0.0, 0.0, 0.0),
         (0.0, 0.0, 0.0, 1.0)),
        ('NPC Spine2 [Spn2]', 25,
         (0.0, -0.017105, 9.864067),
         (-0.120360, 0.0, -0.000001, 0.992730)),
        ('WeaponSword', 5,
         (-11.891473, 1.916892, 6.666046),
         (0.682737, -0.372838, 0.571596, -0.261035)),
        ('NPC R Hand [RHnd]', 32,
         (0.000008, 0.000008, 16.046665),
         (0.031782, 0.042821, 0.681437, 0.729931)),
        ('NPC Head [Head]', 35,
         (0.0, 0.000002, 7.392769),
         (0.095523, 0.000446, -0.000063, 0.995427)),
        ('NPC L Calf [LClf]', 6,
         (0.0, 0.0, 35.595261),
         (0.064981, 0.000190, 0.007632, 0.997857)),
    ]

    for name, expected_parent, expected_trans, expected_rot in ground_truth:
        assert name in rt.bones, f"Bone '{name}' missing from output"
        i = rt.bones.index(name)
        assert rt.parents[i] == expected_parent, \
            f"{name} parent: expected {expected_parent}, got {rt.parents[i]}"
        p = rt.reference_pose[i]
        for j in range(3):
            assert abs(p.translation[j] - expected_trans[j]) < 0.001, \
                f"{name} translation[{j}]: expected {expected_trans[j]:.6f}, got {p.translation[j]:.6f}"
        rdiffs = quat_diff(p.rotation, expected_rot)
        for j in range(4):
            assert rdiffs[j] < 0.0002, \
                f"{name} rotation[{j}]: expected {expected_rot[j]:.6f}, got {p.rotation[j]:.6f} (diff {rdiffs[j]:.6f})"


@TT.category('FO4', 'HKX', 'ARMATURE')
def TEST_HKX_FO4_SKELETON_VANILLA_ROUNDTRIP():
    """Import vanilla FO4 skeleton.hkx via operator, export via operator, verify output."""
    from io_scene_nifly.hkx import anim_fo4

    testfile = TTB.test_file(r"tests\FO4\skeleton_vanilla.hkx")
    outfile = TTB.test_file(r"tests\Out\TEST_HKX_FO4_SKELETON_VANILLA_ROUNDTRIP.hkx")

    # Import via Blender operator
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile,
                                      rename_bones=False,
                                      rename_bones_niftools=False,
                                      blender_xf=False,
                                      create_collection=True)

    arma = bpy.context.object
    assert arma and arma.type == 'ARMATURE', f"Expected armature, got {arma}"

    # Export via Blender operator
    bpy.ops.export_scene.skeleton_hkx(filepath=outfile, game='FO4')

    # Read back with library call and verify against hard-coded ground truth
    rt = anim_fo4.load_fo4_skeleton(outfile)
    assert rt is not None, "Failed to reload exported FO4 skeleton"
    assert len(rt.bones) == 95, f"Expected 95 bones, got {len(rt.bones)}"

    def quat_diff(a_rot, b_rot):
        dot = sum(x * y for x, y in zip(a_rot, b_rot))
        sign = 1 if dot >= 0 else -1
        return [abs(a_rot[j] - sign * b_rot[j]) for j in range(4)]

    # Hard-coded ground truth from vanilla FO4 skeleton_vanilla.hkx
    ground_truth = [
        ('Root', -1,
         (0.0, 0.0, 0.0),
         (0.0, 0.0, 0.0, 1.0)),
        ('Spine2', 9,
         (8.704659, -0.000001, -0.000003),
         (0.000001, 0.0, -0.087657, 0.996151)),
        ('RArm_Hand', 24,
         (6.152273, -0.000141, 0.000450),
         (0.703169, 0.066461, -0.036850, 0.706950)),
        ('Head', 12,
         (8.224388, -0.000015, 0.000005),
         (0.000003, 0.000013, -0.160131, 0.987096)),
        ('LLeg_Calf', 3,
         (31.595177, 0.000024, -0.000019),
         (0.000013, -0.013113, -0.061473, 0.998023)),
    ]

    for name, expected_parent, expected_trans, expected_rot in ground_truth:
        assert name in rt.bones, f"Bone '{name}' missing from output"
        i = rt.bones.index(name)
        assert rt.parents[i] == expected_parent, \
            f"{name} parent: expected {expected_parent}, got {rt.parents[i]}"
        p = rt.reference_pose[i]
        for j in range(3):
            assert abs(p.translation[j] - expected_trans[j]) < 0.001, \
                f"{name} translation[{j}]: expected {expected_trans[j]:.6f}, got {p.translation[j]:.6f}"
        rdiffs = quat_diff(p.rotation, expected_rot)
        for j in range(4):
            assert rdiffs[j] < 0.0002, \
                f"{name} rotation[{j}]: expected {expected_rot[j]:.6f}, got {p.rotation[j]:.6f} (diff {rdiffs[j]:.6f})"


@TT.category('SKYRIM', 'ANIMATION', 'PHYSICS')
def TEST_NOBLECHEST():
    """Read and write the animation of chest opening and shutting."""
    # The chest has two top-level named animations, Open and Close
    testfile = TTB.test_file(r"tests\Skyrim\noblechest01.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_NOBLECHEST.nif")

    #### READ ####

    bpy.context.scene.render.fps = 30
    bpy.ops.import_scene.pynifly(filepath=testfile)

    lid = bpy.data.objects["Lid01"]
    animations = ["Open", "Close"]
    assert lid.animation_data is not None
    TT.assert_contains(lid.animation_data.action.name, animations, "animations exist")
    TT.assert_samemembers(animations, bpy.data.actions.keys(), "Have all animations")
    TT.assert_gt(int(lid.animation_data.action.frame_end), 12, "Have enough frames for animation")

    cur_fps = bpy.context.scene.render.fps
    end_frame = 0.5 * cur_fps + 1
    TT.assert_seteq([m.name for m in lid.animation_data.action.pose_markers], ["start", "end"], "Have markers")
    # assert bpy.context.scene.timeline_markers[1].name == "end", f"Marker exists"
    # assert bpy.context.scene.timeline_markers[1].frame == end_frame, f"Correct frame"
    TT.assert_equiv(lid.animation_data.action.pose_markers[1].frame, 16, "Have markers on action", e=0.0001)
    # assert math.isclose(
    #     bpy.data.actions["ANIM|Close|Lid01"]["pynMarkers"]["end"], 0.5, abs_tol=0.0001), f"Have markers on aactions"


    ### ADD COLLISIONS ###
    bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', 
                                    location=(0, 0, 0), scale=(1, 1, 1))
    chestcol = bpy.context.object
    chestcol.name = "bhkConvexVerticesShape_Chest"
    chestcol.display_type = 'WIRE'
    chestcol['collisionFilter_layer'] = SkyrimCollisionLayer.CLUTTER
    chestcol['pynCollisionFlags'] = "ACTIVE | SYNC_ON_UPDATE"
    chestcol['penetrationDepth'] = 0.1
    chestcol['motionSystem'] = hkMotionType.BOX_INERTIA
    chestcol['qualityType'] = hkQualityType.MOVING
    chestcol['inertiaMatrix'] = "[0, 0, 0, 0, 0, 0, 0, 0, 0]"
    chestcol['rollingFrictionMult'] = 0.0
    for v in chestcol.data.vertices:
        if v.co.x < 0:
            v.co.x = -67.3575
        else:
            v.co.x = 67.3575
        if v.co.y < 0 and v.co.z < 0:
            v.co.y = -24.6112 
        elif v.co.y < 0 and v.co.z >= 0:
            v.co.y = -18.9388 
        elif v.co.y >= 0 and v.co.z < 0:
            v.co.y = 24.6112
        else:
            v.co.y = 18.9388
        if v.co.z < 0:
            v.co.z = 0 
        else:
            v.co.z = 27.6
    bpy.ops.rigidbody.object_add()
    chestcol.rigid_body.collision_shape = 'CONVEX_HULL'
    chestcol.rigid_body.mass = 1.0
    chestcol.rigid_body.linear_damping = 0.1
    chestcol.rigid_body.angular_damping = 0.05

    BD.ObjectSelect([bpy.data.objects['Chest01']], active=True)
    bpy.ops.object.constraint_add(type='COPY_TRANSFORMS')
    bpy.context.object.constraints["Copy Transforms"].target = chestcol

    
    ### WRITE ###

    chestroot = bpy.data.objects['NobleChest01:ROOT']
    BD.ObjectSelect([chestroot], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    ### CHECK ###

    nifcheck = pyn.NifFile(outfile)
    
    # Controller Manager
    CHK.Check_noblechest01(nifcheck)
    
    # Check that NiControllerSequence "Open" has controlled block targeting "Lid01" with blank Property Type
    open_sequence = None
    for seq_name, seq in nifcheck.root.controller.sequences.items():
        if seq_name == "Open":
            open_sequence = seq
            break
    
    assert open_sequence is not None, "NiControllerSequence 'Open' should exist"
    
    lid_controlled_block = None
    for cb in open_sequence.controlled_blocks:
        if cb.node_name == "Lid01":
            lid_controlled_block = cb
            break
    
    assert lid_controlled_block is not None, "Controlled block targeting 'Lid01' should exist in Open sequence"
    assert lid_controlled_block.property_type == "" or lid_controlled_block.property_type is None, \
        f"Property Type should be blank for Lid01 controlled block, but was: '{lid_controlled_block.property_type}'"

TEST_NOBLECHEST.category = {'ANIMATION'}


@TT.category('FO4', 'ANIMATION')
def TEST_CIGARETTE():
    """Check we don't get extra objects in the object palette."""
    testfile = TTB.test_file(r"tests\FO4\CigaretteMachine.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_CIGARETTE.nif")

    #### READ ####

    bpy.context.scene.render.fps = 30
    bpy.ops.import_scene.pynifly(filepath=testfile)

    TT.assert_samemembers(("Open", "Close", "OpenClose"), bpy.data.actions.keys(), "animations")
    assert bpy.data.objects["Object003"].animation_data is not None

    ### WRITE ###

    r = bpy.data.objects['Dummy001:ROOT']
    BD.ObjectSelect([r], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    ### CHECK ###

    nifcheck = pyn.NifFile(outfile)
    TT.assert_contains("Object003", 
                       nifcheck.rootNode.controller.object_palette.objects.keys(),
                       "Have Object003 in object palette")


@TT.category('SKYRIM', 'ANIMATION', 'PHYSICS')
def TEST_DWEMER_CHEST():
    """
    Read and write the animation of chest opening and shutting. Also create a collision
    object for the chest and esure it works.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\dwechest01.nif")
    outfile =TTB.test_file(r"tests/Out/TEST_DWEMER_CHEST.nif")

    #### READ ####

    bpy.context.scene.frame_end = 37
    bpy.context.scene.render.fps = 60 

    bpy.ops.import_scene.pynifly(filepath=testfile)
    lid = bpy.data.objects["Box01"]

    # Read animations correctly
    animations = ['Close', 'Open']
    for anim in animations:
        TT.assert_contains(anim, bpy.data.actions, f"Animations")

    # Lid has been animated
    assert lid.animation_data is not None
    TT.assert_contains(lid.animation_data.action.name, animations, "Active animation")
    TT.assert_gt(len(list(BD.action_fcurves(lid.animation_data.action))), 0, "Have curves")
    TT.assert_eq(next(BD.action_fcurves(lid.animation_data.action)).data_path, "location", "data path")

    # Gear07 has been animated and has reasonable fcurves
    gear07 = bpy.data.objects["Gear07"]
    TT.assert_contains(gear07.animation_data.action.name, animations, "Gear animation")
    gear_slot = gear07.animation_data.action_slot
    gear_fcurves = None
    cb = gear07.animation_data.action.layers[0].strips[0].channelbag(gear_slot)
    if cb:
        gear_fcurves = cb.fcurves
    assert gear_fcurves, "Have gear fcurves from action slot"
    TT.assert_eq(len(gear_fcurves), 3, "Have curves")
    gear07z = gear_fcurves[2]
    TT.assert_eq(gear07z.data_path, "rotation_euler", "Have correct data path")
    TT.assert_equiv(gear07z.keyframe_points[-1].co[0], 37.0, "Have correct time")
    TT.assert_equiv(gear07z.keyframe_points[0].co[1], 0, "Start Z value")
    TT.assert_equiv(gear07z.keyframe_points[-1].co[1], 3.1416, "End Z value")

    gear07obj = gear07.children[0]
    TT.assert_eq(len(gear07obj.data.vertices), 476, "Have right number of vertices")

    #### WRITE ####

    # Create a collision object so we can interact with the chest
    bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
    bpy.context.object.location[2] = 0
    bpy.context.object.display_type = 'WIRE'

    collision_obj = bpy.context.object
    for v in collision_obj.data.vertices:
        if v.co.x < 0:
            v.co.x = -55.9238
        else:
            v.co.x = 55.3899
        if v.co.y < 0:
            v.co.y = -25.9097
        else:
            v.co.y = 26.0875
        if v.co.z < 0:
            v.co.z = -22.2872
        else:
            v.co.z = 28.942

    collision_obj.name = "bhkBoxShape_Chest" 
    collision_obj['collisionFilter_layer'] = SkyrimCollisionLayer.CLUTTER
    collision_obj['pynCollisionFlags'] = "ACTIVE | SYNC_ON_UPDATE"
    collision_obj['penetrationDepth'] = 0.1
    collision_obj['motionSystem'] = hkMotionType.BOX_INERTIA
    collision_obj['qualityType'] = hkQualityType.MOVING
    collision_obj['inertiaMatrix'] = "[0, 0, 0, 0, 0, 0, 0, 0, 0]"
    collision_obj['rollingFrictionMult'] = 0.0

    bpy.ops.rigidbody.object_add()
    bpy.context.object.rigid_body.collision_shape = 'CONVEX_HULL'
    collision_obj.rigid_body.mass = 0.0
    collision_obj.rigid_body.linear_damping = 0.099609
    collision_obj.rigid_body.angular_damping = 0.049805

    BD.ObjectSelect([bpy.data.objects['DwarvenChest01:ROOT']], active=True)
    bpy.ops.object.constraint_add(type='COPY_TRANSFORMS')
    bpy.context.object.constraints["Copy Transforms"].target = collision_obj

    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj],
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, export_animations=True)

    original:pyn.NifFile = pyn.NifFile(testfile)

    # #### FIXUP ####
    # ## TODO: Figure this out. Looks okay in nifskope but not in game.

    # niffix:pyn.NifFile = pyn.NifFile(outfile)

    # for anim in ('Open', 'Close',):
    #     for nodename in ('Object189', 'Object188', 'Gear07', 'Gear08', 'Gear09',):
    #         cborig = next(b for b in original.root.controller.sequences[anim].controlled_blocks 
    #                         if b.node_name == nodename)
    #         cbnew = next(b for b in niffix.root.controller.sequences[anim].controlled_blocks 
    #                         if b.node_name == nodename)
    #         print(f"Original {anim}/{nodename} body rot: {Quaternion(cborig.interpolator.rotation).to_axis_angle()}")
    #         print(f"Created {anim}/{nodename} body rot: {Quaternion(cbnew.interpolator.rotation).to_axis_angle()}")

    #         # Force rotations to be correct
    #         pnew = cbnew.interpolator.properties.copy()
    #         pnew.rotation = cborig.interpolator.properties.rotation
    #         pnew.dataID = cbnew.interpolator.properties.dataID
    #         cbnew.interpolator.properties = pnew
    # niffix.save()

    #### CHECK ####

    # Check controller structure
    nif2:pyn.NifFile = pyn.NifFile(outfile)
    cm2:pyn.NiControllerManager = nif2.root.controller
    mtt2:pyn.NiMultiTargetTransformController = cm2.next_controller

    # We write just the parts that are animated to the object palette. Think that's correct.
    TT.assert_samemembers(nif2.root.controller.object_palette.objects.keys(),
        ('Object02', 'Object02:5', 'Object188:5', 'Handle', 'DwarvenChest:4', 'Object01:6', 
         'Gear08:7', 'Object01:0', 'Object188', 'DwarvenChest:2', 'DwarvenChest:5', 
         'Object189:0', 'Gear09:7', 'Box01', 'Gear09', 'Gear07', 'Object01:5', 'Object01:3', ''
         'Gear08', 'Handle:5', 'Object189:3', 'Object189', 'DwarvenChest:3', 'Gear07:7', 
         'Object189:5', 'Box01:5', 'DwarvenChest:6', 'Object01', 'Object189:6', 
         'DwarvenChest:0', 'DwarvenChest:1', 'DwarvenChest'),
        "Object Palette")
    TT.assert_samemembers([s for s in cm2.sequences], ["Open", "Close"], "Controller Sequences")
    open2:pyn.NiControllerSequence = cm2.sequences["Close"]
    openblk:pyn.ControllerLink = next(b for b in open2.controlled_blocks if b.node_name == "Object01")
    TT.assert_eq(openblk.controller.id, mtt2.id, "Controller IDs")

    assert nif2.nodes['Gear07'].controller is None, "Gear07 has no controller"

    # Check physics
    assert nif2.root.collision_object is not None, "Have collision object"
    assert nif2.root.collision_object.body is not None, "Have collision body"
    assert nif2.root.collision_object.body.shape is not None, "Have collision shape"

    TT.assert_eq(nif2.root.collision_object.properties.flags, 
                 bhkCOFlags.ACTIVE + bhkCOFlags.SYNC_ON_UPDATE,
                 "Collision object flags")
    TT.assert_equiv(nif2.root.collision_object.body.properties.mass, 
                 0.0,
                 "mass")
    TT.assert_equiv(nif2.root.collision_object.body.properties.linearDamping, 
                 0.099609,
                 "Linear damping",
                 e=0.01)

    TT.assert_contains(nif2.root.collision_object.body.shape.blockname,
                       ("bhkBoxShape", "bhkConvexVerticesShape",),
                       "Collision shape type")
    
    if nif2.root.collision_object.body.shape.blockname == "bhkBoxShape":
        col_loc = Vector(nif2.root.collision_object.body.properties.translation[0:3]) * HAVOC_SCALE_FACTOR
        col_dim = Vector(nif2.root.collision_object.body.shape.properties.bhkDimensions) * HAVOC_SCALE_FACTOR
        col_bounds = (Vector(col_loc) - Vector(col_dim), Vector(col_loc) + Vector(col_dim),)
        TT.assert_equiv(col_bounds, 
                        (Vector((-55.9238, -25.9097, -22.2872)), Vector((55.3899, 26.0875, 28.942)),), 
                        "Collision bounds", e=0.1)


@TT.category('SKYRIMSE', 'ANIMATION')
def TEST_DWEMER_GEAR_ANIM():
    """Dwemer gear rotation animates linearly from 0 to 2*pi.
    The NIF has quadratic XYZ rotation keys with forward/backward tangents that
    define a linear ramp. Verify the imported fcurve reflects this."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\dweplatformgear01.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    gear = bpy.data.objects["Gear01"]
    assert gear.animation_data, "Gear01 has animation data"

    slot = gear.animation_data.action_slot
    cb = gear.animation_data.action.layers[0].strips[0].channelbag(slot)
    assert cb, "Have channelbag"

    # Find the Z rotation euler curve (index=2)
    z_curve = next((fc for fc in cb.fcurves
                    if fc.data_path == "rotation_euler" and fc.array_index == 2), None)
    assert z_curve, "Have Z rotation fcurve"

    kfp = z_curve.keyframe_points
    TT.assert_eq(len(kfp), 2, "Two keyframes")
    TT.assert_equiv(kfp[0].co[1], 0, "Start Z value")
    TT.assert_equiv(kfp[-1].co[1], 6.2832, "End Z value", e=0.01)

    # Evaluate at the midpoint — should be ~pi for a linear ramp.
    mid_frame = (kfp[0].co[0] + kfp[-1].co[0]) / 2
    mid_val = z_curve.evaluate(mid_frame)
    TT.assert_equiv(mid_val, math.pi, "Midpoint Z value is pi", e=0.1)


@TT.category('SKYRIM', 'ANIMATION')
def TEST_ALDUIN():
    """Read and write animation using bones."""
    testfile = TTB.test_file(r"tests\SkyrimSE\loadscreenalduinwall.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ALDUIN.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 create_bones=False, 
                                 rename_bones=False,
                                 import_animations=True,
                                 blender_xf=True)
    
    # Didn't rename the bones on import
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert "NPC COM" in arma.data.bones, "Have 'NPC COM'"

    # Transforms are correct for selected bones
    nif = pyn.NifFile(testfile)
    assert TT.is_contains("MagicEffectsNode", arma.data.bones, "Have magic effect node")

    lcalf = arma.data.bones['NPC LLegCalf']
    lcalfp = arma.pose.bones['NPC LLegCalf']
    assert TT.is_eq(lcalfp.rotation_mode, "QUATERNION", "L calf bone rotation mode")
    lcalf_fc = [fc for fc in BD.action_fcurves(arma.animation_data.action) 
                if 'NPC LLegCalf' in fc.data_path and 'location' not in fc.data_path]
    assert TT.is_seteq([fc.keyframe_points[5].interpolation for fc in lcalf_fc], ['LINEAR'], "Left calf keyframe interpolation")

    # This nif has an alpha threshold, tho apparently not used, and vertex alpha. Make
    # sure the values come in correctly.
    alduin = TTB.find_object('AlduinAnim:0')
    anodes = alduin.active_material.node_tree.nodes
    bsdf = [s for s in anodes if 'Shader' in s.name][0]
    alpha = bsdf.inputs['Alpha Property'].links[0].from_node
    assert TT.is_eq(alpha.inputs['Alpha Threshold'].default_value, 5, "Alpha Threshold")
    assert TT.is_eq(alpha.inputs['Alpha Test'].default_value, True, "Alpha Test")
    assert TT.is_eq(alpha.inputs['Alpha Blend'].default_value, False, "Alpha Blend")

    def dump_anim():
        """Dump keyframe 0 animation data if any. If no animation data, dump pose
        locations."""
        if arma.animation_data:
            act = arma.animation_data.action
            for f in act.fcurves:
                print(f"{f.data_path}: {f.keyframe_points[0].co[1]:0.4f}")

            comrot = [f for f in act.fcurves if f.data_path == 'pose.bones["NPC COM"].rotation_euler']
            xyzrot = [comrot[0].keyframe_points[0].co[1], 
                    comrot[1].keyframe_points[0].co[1], 
                    comrot[2].keyframe_points[0].co[1]]
            e = Euler(xyzrot, 'XYZ')
            q = e.to_quaternion()
            print(xyzrot)
            print(e)
            print(q)
        else:
            for b in arma.pose.bones:
                print(f"{b.name}: {b.matrix.translation}\n\t{b.matrix.to_quaternion()}")
        
    ### EXPORT ###

    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile,
                                 rename_bones=False,
                                 preserve_hierarchy=True,
                                 export_animations=True,
                                 intuit_defaults=False)

    # No nodes are emitted more than once--no duplicate names.
    nifcheck = pyn.NifFile(outfile)
    assert TT.is_eq(len(nifcheck.node_ids), len(nifcheck.nodes), "No dup node names")
    rootbone = nifcheck.nodes['NPC Root [Root]']

    # Eyes are skinned
    eyes = nifcheck.nodes['AlduinAnim:1']
    assert TT.is_seteq(eyes.bone_names, ['NPC Head'], "Eyes are skinned to head")

    # Rootbone's controller sets the time frame
    rootctlr = rootbone.controller
    assert TT.is_equiv(rootctlr.properties.stopTime, 28.0, "stopTime")

    # We have not changed the name to "NPC COM [COM ]" because we picked up the setting
    # from the armature.
    assert "NPC COM" in nifcheck.nodes, "Have 'NPC COM'"
    
    # Check all the bone and interpolator transforms.
    TTB.check_bone_controllers(nif, nifcheck, ["NPC Root [Root]", "NPC COM", "NPC Pelvis"])
    nodenames1 = set()
    for s in nif.shapes:
        for bn in s.bone_names:
            nodenames1.add(bn)
    nodenames2 = set()
    for s in nifcheck.shapes:
        for bn in s.bone_names:
            nodenames2.add(bn)
    assert TT.is_seteq(nodenames2, nodenames1, "Nodes")
    TTB.check_bone_controllers(nif, nifcheck, nodenames2)

    # combone_in:pyn.NiNode = nif.nodes['NPC COM']
    # cominterp_in:pyn.NiTransformInterpolator = combone_in.controller.interpolator
    # assert NT.VNearEqual(cominterp.properties.translation, cominterp_in.properties.translation), f"Have correct translation"
    # assert NT.VNearEqual(cominterp.properties.rotation, cominterp_in.properties.rotation), f"Have correct rotation"

    # Neck hub rotates around Z with quadratic interpolation.
    neckhub:pyn.NiNode = nifcheck.nodes['NPC NeckHub']
    neckctlr:pyn.NiTransformController = neckhub.controller
    neckinterp:pyn.NiTransformInterpolator = neckctlr.interpolator
    neckdat:pyn.NiTransformData = neckinterp.data
    assert TT.is_gt(len(neckdat.zrotations), 0, "Neck Z rotation count")
    assert TT.is_eq(neckdat.properties.zRotations.interpolation, pyn.NiKeyType.QUADRATIC_KEY, "Rotation type")


@TT.category('SKYRIM', 'HKX', 'ANIMATION')
@TT.expect_errors(("Controller target not found",))
def TEST_KF():
    """Read and write KF animation."""
    if bpy.app.version < (3, 5, 0): return

    testfile = TTB.test_file(r"tests\SkyrimSE\1hm_staggerbacksmallest.kf")
    testfile2 = TTB.test_file(r"tests\SkyrimSE\1hm_attackpowerright.kf")
    skelfile = TTB.test_file(r"tests\SkyrimSE\skeleton_vanilla.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_KF.kf")

    bpy.context.scene.render.fps = 30

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 create_bones=False, 
                                 rename_bones=False,
                                 import_animations=False,
                                 import_collisions=False,
                                 blender_xf=False)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect(arma, active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile)

    a = arma.animation_data.action
    TT.assert_eq(arma.animation_data.action.name, "1hm_staggerbacksmallest", "action name")
    TT.assert_gt(len(arma.animation_data.action.layers[0].strips[0].channelbags[0].fcurves), 
                 0, 
                 "fcurve count")

    # Check that the head moves over the course of the animation
    bpy.context.scene.frame_set(1)
    headpos = arma.pose.bones["NPC COM [COM ]"].location.copy()
    bpy.context.scene.frame_set(8)
    headpos2 = arma.pose.bones["NPC COM [COM ]"].location.copy()
    TT.assert_equiv_not(headpos, headpos2, "Head motion", e=0.001)

    # Loading a second animation shouldn't screw things up.
    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile2)

    TT.assert_eq(arma.animation_data.action.name, "1hm_attackpowerright", "action name after second import")
    act2 = arma.animation_data.action
    TT.assert_eq(int(act2.frame_end), 36, "action frame end")

    TT.assert_contains("1hm_staggerbacksmallest", bpy.data.actions, "first action still exists")

    ### Export ###

    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.export_scene.pynifly_kf(filepath=outfile2)

    kforig = pyn.NifFile(testfile2)
    csorig = kforig.rootNode
    cb2orig = [cb for cb in csorig.controlled_blocks if cb.node_name == 'NPC L Thigh [LThg]'][0]
    ti_thigh_in = cb2orig.interpolator
    td_thigh_in = ti_thigh_in.data
    ti2qorig = Quaternion(ti_thigh_in.properties.rotation)
    print(f"Original Interpolator rotation: {ti2qorig}")
    k20orig = Quaternion(td_thigh_in.qrotations[0].value[:])
    print(f"Original Key rotation: {k20orig}")
    curve20orig = Quaternion(ti2qorig.inverted() @ k20orig)
    print(f"Calculated curve quaternion: {curve20orig}")

    # The animation we wrote is correct
    kfout = pyn.NifFile(outfile2)
    csout = kfout.rootNode
    TT.assert_eq(csout.name, 'TEST_KF', "root node name")
    TT.assert_eq(csout.blockname, 'NiControllerSequence', "block type")
    TT.assert_eq(csout.properties.cycleType, CycleType.CLAMP, "cycle type")
    TT.assert_equiv(csout.properties.stopTime, 1.166667, "stop time")
    cb0 = csout.controlled_blocks[0]
    ti0 = cb0.interpolator
    td0 = ti0.data
    TT.assert_eq(td0.properties.translations.interpolation, pyn.NiKeyType.LINEAR_KEY, "key type")
    TT.assert_eq(td0.translations[0].time, 0, "First time value")
    TT.assert_equiv(td0.translations[0].value, (0.0, 0.0001, 57.8815), "translation", e=0.001)

    # Text key extra data
    TT.assert_eq([x[1] for x in csout.text_key_data.keys], 
                 [x[1] for x in csorig.text_key_data.keys], 
                 "text key labels")
    TT.assert_equiv([x[0] for x in csout.text_key_data.keys], 
                    [x[0] for x in csorig.text_key_data.keys], 
                    "text key values")

    controlled_block_thigh_out = [cb for cb in csout.controlled_blocks if cb.node_name == 'NPC L Thigh [LThg]'][0]
    ti_thigh_out = controlled_block_thigh_out.interpolator
    td_thigh_out = ti_thigh_out.data

    # The interpolator's base transform uses FLT_MAX sentinels when keyed data is
    # present, so skip comparison if the exported side has sentinels.
    if abs(ti_thigh_out.properties.rotation[0]) < 1e+37:
        TT.assert_equiv(ti_thigh_out.properties.translation, ti_thigh_in.properties.translation, "Thigh Interpolator translation")
        mxout = Quaternion(ti_thigh_out.properties.rotation).to_matrix()
        mxorig = Quaternion(ti_thigh_in.properties.rotation).to_matrix()
        TT.assert_equiv(mxout, mxorig, "Thigh Interpolator rotation")
    
    # We've calculated the rotations properly--the rotation we wrote matches the original.
    k2mx = Quaternion(td_thigh_out.qrotations[0].value).to_matrix()
    k2mxorig = Quaternion(td_thigh_in.qrotations[0].value).to_matrix()
    TT.assert_equiv(k2mx, k2mxorig, "rotation keys")

    # Time signatures are calculated correctly.
    # We output at 30 fps so the number isn't exact.
    klast_out = td_thigh_out.qrotations[-1]
    klast_in = td_thigh_in.qrotations[-1]
    TT.assert_equiv(klast_out.time, klast_in.time, "final time signature")

    # Check feet transforms
    cb_foot_in = [cb for cb in csorig.controlled_blocks if cb.node_name == 'NPC L Foot [Lft ]'][0]
    ti_foot_in = cb_foot_in.interpolator
    td_foot_in = ti_foot_in.data
    cb_foot_out = [cb for cb in csout.controlled_blocks if cb.node_name == 'NPC L Foot [Lft ]'][0]
    ti_foot_out = cb_foot_out.interpolator
    td_foot_out = ti_foot_out.data
    if abs(ti_foot_out.properties.rotation[0]) < 1e+37:
        TT.assert_equiv(ti_foot_out.properties.translation, ti_foot_in.properties.translation, "Foot Interpolator translation")
        mxout = Quaternion(ti_foot_out.properties.rotation).to_matrix()
        mxin = Quaternion(ti_foot_in.properties.rotation).to_matrix()
        TT.assert_equiv(mxout, mxin, "Foot Interpolator rotation")

    assert len(td_foot_out.qrotations) > 30 and len(td_foot_out.qrotations) < 40, \
        f"Have reasonable number of frames: {td_foot_out.qrotations}"


@TT.category('SKYRIM', 'HKX')
@TT.expect_errors(("Controller target not found",))
def TEST_KF_RENAME():
    """Read and write KF animation with renamed bones."""
    if bpy.app.version < (3, 5, 0): return

    testfile = TTB.test_file(r"tests\Skyrim\sneakmtidle_original.kf")
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    outfile = TTB.test_file(r"tests\Out\TEST_KF_RENAME.kf")

    bpy.context.scene.render.fps = 30
    # bpy.context.scene.frame_end = 665

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 create_bones=False, 
                                 rename_bones=True,
                                 import_animations=False,
                                 import_collisions=False,
                                 blender_xf=True)
    
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_kf(filepath=testfile)

    anim = arma.animation_data.action
    assert TT.is_gt(len([fc for fc in BD.action_fcurves(anim) if 'NPC Pelvis' in fc.data_path]), 
                 0, 
                 "Pelvis animated")
    translation_curve = [fc for fc in BD.action_fcurves(anim) 
                         if 'Foot.L' in fc.data_path and 'location' in fc.data_path][0]
    assert TT.is_eq(translation_curve.keyframe_points[0].interpolation, 
                    'LINEAR', 
                    "Keyframe point interpolation")

    ### Export ###

    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.ops.export_scene.pynifly_kf(filepath=outfile, rename_bones=True)

    ### Check ###

    nifin = pyn.NifFile(testfile)
    cbin = next(x for x in nifin.rootNode.controlled_blocks if x.node_name == 'NPC L Foot [Lft ]')
    tdin = cbin.interpolator.data

    nifcheck = pyn.NifFile(outfile)
    names = [cb.node_name for cb in nifcheck.rootNode.controlled_blocks]
    assert 'NPC Pelvis [Pelv]' in names, f"Have nif name"
    assert 'NPC Pelvis' not in names, f"Don't have Blender name"

    # 
    # The original has 333 keyframes for the Lft rotations--one keyframe every 1/30 sec,
    # no interpolations. But it only has 2 keyframes for the Lft translations, which just
    # serve to hold it in place. Currently the exporter writes out every keyframe for
    # everything.
    # TODO: Maybe fix this? What are the criteria for not writing every frame?
    #
    footcb:pyn.ControllerLink = next(x for x in nifcheck.rootNode.controlled_blocks if x.node_name == 'NPC L Foot [Lft ]')
    assert TT.is_eq(footcb.controller_type, 'NiTransformController', "Controller Type")
    foottd = footcb.interpolator.data
    assert TT.is_eq(len(foottd.qrotations), 333, f"Number of L Foot rotations")
    assert TT.is_eq(foottd.properties.translations.interpolation, pyn.NiKeyType.LINEAR_KEY, "L Foot translation interpolation")
    assert TT.is_eq(len(foottd.translations), 333, "Number of L Foot translations")
    timeinterval = foottd.qrotations[10].time - foottd.qrotations[9].time
    assert TT.is_equiv(timeinterval, 1/30, "Rotation time interval")
    assert TT.is_equiv(foottd.translations[-1].time, 11.0667, "Last keyframe time")

    assert TT.is_equiv(foottd.qrotations[10].time, tdin.qrotations[10].time, "time signatures")
    assert TT.is_equiv(foottd.translations[1].value, tdin.translations[1].value, f"translation values")

    comcb_in = next(x for x in nifin.rootNode.controlled_blocks if x.node_name == 'NPC COM [COM ]')
    comtd_in = comcb_in.interpolator.data
    commax_in = max(x.value[1] for x in comtd_in.translations)
    commin_in = min(x.value[1] for x in comtd_in.translations)
    comcb = next(x for x in nifcheck.rootNode.controlled_blocks if x.node_name == 'NPC COM [COM ]')
    comtd = comcb.interpolator.data
    commax = max(x.value[1] for x in comtd.translations)
    commin = min(x.value[1] for x in comtd.translations)
    assert TT.is_equiv(commax, commax_in, f"Max com movement")
    assert TT.is_equiv(commin, commin_in, f"Max com movement")


@TT.category('SKYRIM', 'HKX')
def TEST_HKX_2():
    """Can import and export a non-human HKX animation."""
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton_troll.hkx")
    nif_mesh = TTB.test_file(r"tests\Skyrim\troll.nif")
    hkx_anim = TTB.test_file(r"tests\Skyrim\troll_h2hattackleftd.hkx")
    outfile = TTB.test_file(r"tests/Out/created animations/TEST_HKX_2.hkx")

    Path(outfile).parent.mkdir(parents=True, exist_ok=True)

    bpy.context.scene.render.fps = 30

    # Step 1: Import HKX skeleton
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=False,
                                      blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)

    # Step 2: Import NIF mesh onto the skeleton
    bpy.ops.import_scene.pynifly(filepath=nif_mesh,
                                 rename_bones=False,
                                 import_pose=True)

    body = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    assert body is not None, "Troll mesh was imported"

    # Step 3: Import animation
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=False,
                                      blender_xf=False)

    assert arma.animation_data.action is not None, "Have animation loaded"
    act = arma.animation_data.action
    clavcurv = [c for c in BD.action_fcurves(act)
                if c.data_path.startswith('pose.bones["NPC L Clavicle [LClv]"]')]
    assert TT.is_gt(len(clavcurv), 0, "Have LClv curves")

    # Step 4: Export animation
    BD.ObjectSelect([arma], active=True)
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile)

    assert os.path.exists(outfile)

    # Verify roundtrip: re-import and check track count
    from io_scene_nifly.hkx import anim_skyrim
    output_anim = anim_skyrim.load_skyrim_animation(outfile)
    assert output_anim is not None, "Output HKX has animation data"
    assert TT.is_gt(output_anim.num_tracks, 10, "Have at least 10 output tracks")


@TT.category('SKYRIM', 'HKX')
def TEST_AUXBONES():
    """Can import and export an animation on an auxbones skeleton."""
    testfile = TTB.test_file(r"tests\Skyrim\SOSFastErect.hkx")
    hkx_skel = TTB.test_file(r"tests\Skyrim\SOSskeleton.hkx")
    outfile = TTB.test_file(r"tests/Out/created animations/TEST_AUXBONES.hkx")

    bpy.context.scene.render.fps = 60

    # Import the auxbones HKX skeleton
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                     rename_bones=False,
                                     blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)

    # Import the animation
    bpy.ops.import_scene.pynifly_hkx(filepath=testfile,
                                     rename_bones=False,
                                     blender_xf=False)

    assert 'NPC GenitalsBase [GenBase]' in arma.data.bones, "Auxbone exists in skeleton"
    assert arma.animation_data is not None, "Armature has animation data"
    assert arma.animation_data.action is not None, "Armature has an action"

    # This additive animation starts from rest (frame 1) and moves bones.
    # Check Gen06 has moved from rest by the last frame.
    baseb = arma.data.bones['NPC Genitals06 [Gen06]']
    poseb = arma.pose.bones['NPC Genitals06 [Gen06]']
    bpy.context.scene.frame_set(1)
    assert TTB.MatNearEqual(baseb.matrix_local, poseb.matrix, epsilon=0.1), \
        f"Gen06 at rest on frame 1"
    bpy.context.scene.frame_set(int(arma.animation_data.action.frame_end))
    assert not TTB.MatNearEqual(baseb.matrix_local, poseb.matrix, epsilon=0.1), \
        f"Gen06 has moved by last frame"

    orig_frame_end = int(arma.animation_data.action.frame_end)
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile)
    assert os.path.exists(outfile)

    # Re-import and verify roundtrip
    for a in bpy.data.actions:
        bpy.data.actions.remove(a)
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile,
                                     rename_bones=False,
                                     blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation after re-import"
    assert arma.animation_data.action is not None, "Armature has action after re-import"
    reimported = arma.animation_data.action
    assert TT.is_eq(int(reimported.frame_end), orig_frame_end, "Frame count preserved")

    # Re-imported animation should also show movement on Gen06
    bpy.context.scene.frame_set(int(reimported.frame_end))
    assert not TTB.MatNearEqual(baseb.matrix_local, poseb.matrix, epsilon=0.1), \
        f"Gen06 has moved after re-import"


@TT.category('SKYRIM', 'HKX')
def TEST_IMPORT_TAIL():
    """Regression: Import of a single bodypart onto a skeleton should work correctly."""

    testfile = TTB.test_file(r"tests\Skyrim\meshes\actors\character\character animations\1hm_staggerbacksmallest.hkx")
    # testfile2 = TTB.test_file(r"tests\Skyrim\1hm_attackpowerright.hkx")
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    outfile = TTB.test_file(r"tests/Out/created animations/TEST_HKX.hkx")

    bpy.context.scene.render.fps = 60

    # Animations are loaded into a skeleton
    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 create_bones=False, 
                                 rename_bones=True,
                                 import_collisions=False,
                                 import_animations=False,
                                 blender_xf=True)


@TT.category('SKYRIM', 'HKX')
@TT.expect_errors(('Target of fcurve not found', "Ignoring scale transforms"))
def TEST_EXPORT_BOGUS():
    """Export animation with bogus fcurves."""

    testfile = TTB.test_file(r"tests\Skyrim\Pynifly_Issue_357.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_EXPORT_BOGUS.kf")

    bpy.context.scene.render.fps = 60

    with bpy.data.libraries.load(testfile) as (data_from, data_to):
        data_to.objects = [obj for obj in data_from.objects]
    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)
    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE'], active=True)

    bpy.ops.export_scene.pynifly_kf(filepath=outfile)

    assert os.path.exists(outfile)


@TT.category('FO4', 'HKX')
def TEST_FO4_ANIM_IMPORT():
    """Can import FO4 HKX animation onto skeleton imported from HKX."""
    hkx_skel = TTB.test_file(r"tests\FO4\Animations\skeleton.hkx")
    hkx_anim = TTB.test_file(r"tests\FO4\Animations\Death1.hkx")

    bpy.context.scene.render.fps = 30

    # Import the HKX skeleton — creates armature with stored bone list
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=False,
                                      blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert TT.is_gt(len(arma.data.bones), 90, "Skeleton has bones")
    assert 'PYN_HKX_BONES' in arma, "Armature has stored HKX bone list"

    BD.ObjectSelect([arma], active=True)

    # Import FO4 animation — no skeleton reference needed
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=False,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation data"
    assert arma.animation_data.action is not None, "Armature has an action"

    act = arma.animation_data.action
    fcurves = list(BD.action_fcurves(act))
    assert TT.is_gt(len(fcurves), 0, "Action has fcurves")

    # Check that COM bone has animation
    com_curves = [c for c in fcurves if 'COM' in c.data_path]
    assert TT.is_gt(len(com_curves), 0, "COM bone is animated")


@TT.category('FO4', 'HKX')
def TEST_FO4_ANIM_EXPORT():
    """Can export FO4 HKX animation and re-import with matching tracks."""
    hkx_skel = TTB.test_file(r"tests\FO4\Animations\skeleton.hkx")
    hkx_anim = TTB.test_file(r"tests\FO4\Animations\Death1.hkx")
    outfile = TTB.test_file(r"tests\Out\TEST_FO4_ANIM_EXPORT.hkx")

    bpy.context.scene.render.fps = 30

    # Import skeleton + animation
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=False,
                                      blender_xf=False)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=False,
                                      blender_xf=False)

    orig_action = arma.animation_data.action
    orig_frame_end = int(orig_action.frame_end)

    # Export
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile)

    # Clear and re-import to verify roundtrip
    bpy.ops.object.mode_set(mode='OBJECT')
    for a in bpy.data.actions:
        bpy.data.actions.remove(a)

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile,
                                      rename_bones=False,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation after re-import"
    assert arma.animation_data.action is not None, "Armature has action after re-import"

    reimported = arma.animation_data.action
    assert TT.is_eq(int(reimported.frame_end), orig_frame_end, "Frame count preserved")

    # Check fcurves exist
    fcurves = list(BD.action_fcurves(reimported))
    assert TT.is_gt(len(fcurves), 0, "Re-imported action has fcurves")

    # Check COM bone is still animated
    com_curves = [c for c in fcurves if 'COM' in c.data_path]
    assert TT.is_gt(len(com_curves), 0, "COM bone still animated after roundtrip")

    # Verify death pose: COM should be near the floor at last frame
    bpy.context.scene.frame_set(orig_frame_end)
    bpy.context.view_layer.update()
    com_bone = arma.pose.bones.get('COM')
    assert com_bone is not None, "COM bone exists"
    com_z = (arma.matrix_world @ com_bone.matrix).translation.z
    assert TT.is_lt(com_z, 20.0, "COM z near floor at end of death anim")


@TT.category('SKYRIM', 'HKX')
def TEST_SKYRIM_HKX_SKEL_WITH_NIF():
    """Import HKX skeleton, NIF body, then HKX animation — full workflow."""
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    nif_body = TTB.test_file(r"tests\Skyrim\malebody_1.nif")
    hkx_anim = TTB.test_file(r"tests\Skyrim\1hm_staggerbacksmallest.hkx")

    bpy.context.scene.render.fps = 30

    # Step 1: Import HKX skeleton
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=True,
                                      blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)

    # Step 2: Import NIF body onto the HKX armature
    bpy.ops.import_scene.pynifly(filepath=nif_body,
                                  rename_bones=True,
                                  blender_xf=False,
                                  import_pose=True)

    body = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    assert body is not None, "Body mesh was imported"
    arma_mod = next((m for m in body.modifiers if m.type == 'ARMATURE'), None)
    assert arma_mod is not None, "Body has armature modifier"
    assert TT.is_eq(arma_mod.object, arma, "Body is parented to HKX armature")

    max_coord = max(abs(v.co[i]) for v in body.data.vertices for i in range(3))
    assert TT.is_lt(max_coord, 200, f"Vertices within bounds (max={max_coord:.1f})")

    # Step 3: Import animation
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=True,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation data"
    act = arma.animation_data.action
    assert act is not None, "Armature has an action"
    assert TT.is_eq(int(act.frame_end), 38, "Animation has 38 frames")


@TT.category('FO4', 'HKX')
def TEST_FO4_HKX_SKEL_WITH_NIF():
    """Import FO4 HKX skeleton then NIF body — skin bones should be parented to armature bones."""
    hkx_skel = TTB.test_file(r"tests\FO4\Animations\skeleton.hkx")
    nif_body = TTB.test_file(r"tests\FO4\BTMaleBody.nif")

    # Step 1: Import HKX skeleton
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=True,
                                      blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    hkx_bone_count = len(arma.data.bones)
    BD.ObjectSelect([arma], active=True)

    # Step 2: Import NIF body onto the HKX armature (no import_pose — armature
    # compatibility check should pass since HKX and NIF describe the same skeleton)
    bpy.ops.import_scene.pynifly(filepath=nif_body,
                                  rename_bones=True,
                                  blender_xf=False)

    body = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    assert body is not None, "Body mesh was imported"
    arma_mod = next((m for m in body.modifiers if m.type == 'ARMATURE'), None)
    assert arma_mod is not None, "Body has armature modifier"
    assert TT.is_eq(arma_mod.object, arma, "Body is parented to HKX armature")

    # Should have more bones now (skin bones added from body NIF)
    assert TT.is_gt(len(arma.data.bones), hkx_bone_count,
                     "Body NIF added skin bones to armature")

    # Check that skin bones are parented to their corresponding armature bones
    pelvis_skin = arma.data.bones.get('Pelvis_skin')
    assert pelvis_skin is not None, "Pelvis_skin bone exists"
    assert pelvis_skin.parent is not None, "Pelvis_skin has a parent"
    assert TT.is_eq(pelvis_skin.parent.name, 'Pelvis', "Pelvis_skin parented to Pelvis")

    # Check a renamed skin bone too
    chest_skin = arma.data.bones.get('Chest_skin')
    assert chest_skin is not None, "Chest_skin bone exists"
    assert chest_skin.parent is not None, "Chest_skin has a parent"
    assert TT.is_eq(chest_skin.parent.name, 'Chest', "Chest_skin parented to Chest")


@TT.category('SKYRIM', 'HKX')
def TEST_SKYRIM_ANIM_IMPORT():
    """Can import Skyrim HKX animation onto skeleton imported from HKX."""
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    hkx_anim = TTB.test_file(r"tests\Skyrim\1hm_staggerbacksmallest.hkx")

    bpy.context.scene.render.fps = 30

    # Import the HKX skeleton — creates armature with stored bone list
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=True,
                                      blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert arma.name.endswith(':ARMATURE'), f"Armature name ends with :ARMATURE, got '{arma.name}'"
    assert TT.is_eq(len(arma.data.bones), 99, "Skeleton has 99 bones")
    assert 'PYN_HKX_BONES' in arma, "Armature has stored HKX bone list"
    assert TT.is_eq(arma.get('PYN_HKX_GAME'), 'SKYRIM', "Game property is SKYRIM")
    assert TT.is_eq(arma.get('PYN_HKX_PTR_SIZE'), 4, "Ptr size is 4 (LE)")

    # Verify bone renaming was applied (L/R bones use Blender .L/.R suffix)
    assert arma.data.bones.get('NPC Calf.L') is not None, "NPC L Calf renamed to NPC Calf.L"

    BD.ObjectSelect([arma], active=True)

    # Import Skyrim animation
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=True,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation data"
    assert arma.animation_data.action is not None, "Armature has an action"

    act = arma.animation_data.action
    fcurves = list(BD.action_fcurves(act))
    assert TT.is_gt(len(fcurves), 0, "Action has fcurves")

    # Check that NPC COM bone has animation
    com_curves = [c for c in fcurves if 'NPC COM' in c.data_path]
    assert TT.is_gt(len(com_curves), 0, "NPC COM bone is animated")

    # Verify frame range
    assert TT.is_eq(int(act.frame_end), 38, "Animation has 38 frames")

    # Verify annotation markers were imported
    markers = bpy.context.scene.timeline_markers
    assert TT.is_ge(len(markers), 3, "At least 3 annotation markers")


@TT.category('SKYRIM', 'FO4', 'HKX', 'ARMATURE')
@TT.parameterize("game", ['SKYRIM', 'FO4'])
def TEST_HKX_ANIM_ORIENT(game):
    """HKX animation import is correct under every blender_xf / pretty combination (issue #377).

    The pretty rotation only changes how a bone is *represented*, so the posed
    bones must land in the same world positions whether pretty is on or off; the
    blender transform must scale/rotate those world positions to match a
    blender_xf NIF import.  We import the same skeleton+animation under all four
    combinations and compare the resulting world-space pose.
    """
    if game == 'SKYRIM':
        hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
        hkx_anim = TTB.test_file(r"tests\Skyrim\1hm_staggerbacksmallest.hkx")
    else:
        hkx_skel = TTB.test_file(r"tests\FO4\Animations\skeleton.hkx")
        hkx_anim = TTB.test_file(r"tests\FO4\Animations\Death1.hkx")

    bpy.context.scene.render.fps = 30

    def import_and_sample(is_blender, is_pretty):
        TTB.clear_all()
        bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel, rename_bones=False,
                                         blender_xf=is_blender,
                                         rotate_bones_pretty=is_pretty)
        arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
        BD.ObjectSelect([arma], active=True)
        bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim, rename_bones=False,
                                         blender_xf=is_blender,
                                         rotate_bones_pretty=is_pretty)
        act = arma.animation_data.action
        frame = max(2, int(act.frame_end) // 2)
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {pb.name: (arma.matrix_world @ pb.matrix).translation.copy()
                for pb in arma.pose.bones}

    nat_nif    = import_and_sample(False, False)
    nat_pretty = import_and_sample(False, True)
    bl_nif     = import_and_sample(True,  False)
    bl_pretty  = import_and_sample(True,  True)

    assert len(nat_nif) > 20, f"Sampled a real skeleton ({len(nat_nif)} bones)"

    # Pretty must be representation-only: same world pose with it on or off.
    for name in nat_nif:
        assert NT.VNearEqual(nat_nif[name], nat_pretty[name], 0.01), \
            f"{game} bone '{name}' moved when pretty toggled (natural): " \
            f"{nat_nif[name][:]} != {nat_pretty[name][:]}"
        assert NT.VNearEqual(bl_nif[name], bl_pretty[name], 0.01), \
            f"{game} bone '{name}' moved when pretty toggled (blender): " \
            f"{bl_nif[name][:]} != {bl_pretty[name][:]}"

    # blender_xf must scale/rotate the world pose exactly like a NIF import.
    for name in nat_nif:
        expected = BD.blender_import_xf @ nat_nif[name]
        assert NT.VNearEqual(bl_nif[name], expected, 0.01), \
            f"{game} bone '{name}' world pose not transformed by blender_xf: " \
            f"{bl_nif[name][:]} != {expected[:]}"


@TT.category('SKYRIM', 'FO4', 'HKX', 'ARMATURE')
@TT.parameterize("game", ['SKYRIM', 'FO4'])
def TEST_HKX_ANIM_ORIENT_ROUNDTRIP(game):
    """Animation export reverses the pretty-bone rotation: a pretty import →
    export → re-import leaves the world-space pose unchanged (issue #377)."""
    if game == 'SKYRIM':
        hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
        hkx_anim = TTB.test_file(r"tests\Skyrim\1hm_staggerbacksmallest.hkx")
    else:
        hkx_skel = TTB.test_file(r"tests\FO4\Animations\skeleton.hkx")
        hkx_anim = TTB.test_file(r"tests\FO4\Animations\Death1.hkx")
    outfile = TTB.test_file(rf"tests\Out\TEST_HKX_ANIM_ORIENT_RT_{game}.hkx")

    bpy.context.scene.render.fps = 30

    # Import skeleton + animation with pretty bones on.
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel, rename_bones=False,
                                     rotate_bones_pretty=True)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim, rename_bones=False,
                                     rotate_bones_pretty=True)

    frame = max(2, int(arma.animation_data.action.frame_end) // 2)

    def sample():
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {pb.name: (arma.matrix_world @ pb.matrix).translation.copy()
                for pb in arma.pose.bones}

    before = sample()

    # Export the animation and re-import onto the same (pretty) armature.
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile, rename_bones=False,
                                     rotate_bones_pretty=True)

    after = sample()

    # Tolerance covers inherent HKX rotation quantization, which dominates on
    # bones far from the root (fingers) and is identical with pretty on or off.
    # Exact pretty correctness is proven by TEST_HKX_ANIM_ORIENT.
    for name, b in before.items():
        assert NT.VNearEqual(b, after[name], 0.06), \
            f"{game} bone '{name}' world pose changed by anim roundtrip: {b[:]} != {after[name][:]}"


@TT.category('SKYRIM', 'HKX')
def TEST_SKYRIM_ANIM_EXPORT():
    """Can export Skyrim HKX animation and re-import with matching tracks."""
    hkx_skel = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    hkx_anim = TTB.test_file(r"tests\Skyrim\1hm_staggerbacksmallest.hkx")
    outfile = TTB.test_file(r"tests\Out\TEST_SKYRIM_ANIM_EXPORT.hkx")

    bpy.context.scene.render.fps = 30

    # Import skeleton + animation
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=True,
                                      blender_xf=False)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=True,
                                      blender_xf=False)

    orig_action = arma.animation_data.action
    orig_frame_end = int(orig_action.frame_end)

    # Export
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile)

    # Verify the output file has ptr_size=4 in header (LE)
    with open(outfile, 'rb') as f:
        hdr = f.read(0x11)
    assert TT.is_eq(hdr[0x10], 4, "Exported file has ptr_size=4 (LE)")

    # Clear and re-import to verify roundtrip
    bpy.ops.object.mode_set(mode='OBJECT')
    for a in bpy.data.actions:
        bpy.data.actions.remove(a)

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile,
                                      rename_bones=True,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation after re-import"
    assert arma.animation_data.action is not None, "Armature has action after re-import"

    reimported = arma.animation_data.action
    assert TT.is_eq(int(reimported.frame_end), orig_frame_end, "Frame count preserved")

    # Check fcurves exist
    fcurves = list(BD.action_fcurves(reimported))
    assert TT.is_gt(len(fcurves), 0, "Re-imported action has fcurves")

    # Check NPC COM bone is still animated
    com_curves = [c for c in fcurves if 'NPC COM' in c.data_path]
    assert TT.is_gt(len(com_curves), 0, "NPC COM bone still animated after roundtrip")


@TT.category('SKYRIM', 'HKX')
def TEST_SKYRIMSE_ANIM_IMPORT():
    """Can import Skyrim SE HKX animation (8-byte pointers) onto SE skeleton."""
    hkx_skel = TTB.test_file(r"tests\SkyrimSE\skeleton.hkx")
    hkx_anim = TTB.test_file(r"tests\SkyrimSE\1hm_staggerbacksmallest.hkx")

    bpy.context.scene.render.fps = 30

    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=True,
                                      blender_xf=False)

    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert TT.is_true(arma.name.endswith(':ARMATURE'), f"SE armature name ends with :ARMATURE, got '{arma.name}'")
    assert TT.is_eq(len(arma.data.bones), 99, "SE skeleton has 99 bones")
    assert TT.is_eq(arma.get('PYN_HKX_GAME'), 'SKYRIM', "Game property is SKYRIM")
    assert TT.is_eq(arma.get('PYN_HKX_PTR_SIZE'), 8, "Ptr size is 8 (SE)")

    BD.ObjectSelect([arma], active=True)

    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=True,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation data"
    assert arma.animation_data.action is not None, "Armature has an action"

    act = arma.animation_data.action
    fcurves = list(BD.action_fcurves(act))
    assert TT.is_gt(len(fcurves), 0, "Action has fcurves")

    com_curves = [c for c in fcurves if 'NPC COM' in c.data_path]
    assert TT.is_gt(len(com_curves), 0, "NPC COM bone is animated")

    assert TT.is_eq(int(act.frame_end), 38, "Animation has 38 frames")

    markers = bpy.context.scene.timeline_markers
    assert TT.is_ge(len(markers), 3, "At least 3 annotation markers")


@TT.category('SKYRIM', 'HKX')
def TEST_SKYRIMSE_ANIM_EXPORT():
    """Can export Skyrim SE HKX animation with 8-byte pointers and re-import."""
    hkx_skel = TTB.test_file(r"tests\SkyrimSE\skeleton.hkx")
    hkx_anim = TTB.test_file(r"tests\SkyrimSE\1hm_staggerbacksmallest.hkx")
    outfile = TTB.test_file(r"tests\Out\TEST_SKYRIMSE_ANIM_EXPORT.hkx")

    bpy.context.scene.render.fps = 30

    # Import SE skeleton + animation
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_skel,
                                      rename_bones=True,
                                      blender_xf=False)
    arma = next(a for a in bpy.data.objects if a.type == 'ARMATURE')
    assert TT.is_eq(arma.get('PYN_HKX_PTR_SIZE'), 8, "Ptr size is 8 before export")
    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=hkx_anim,
                                      rename_bones=True,
                                      blender_xf=False)

    orig_action = arma.animation_data.action
    orig_frame_end = int(orig_action.frame_end)

    # Export — should produce SE format (ptr_size=8)
    bpy.ops.export_scene.pynifly_hkx(filepath=outfile)

    # Verify the output file has ptr_size=8 in header
    with open(outfile, 'rb') as f:
        hdr = f.read(0x11)
    assert TT.is_eq(hdr[0x10], 8, "Exported file has ptr_size=8 (SE)")

    # Clear and re-import to verify roundtrip
    bpy.ops.object.mode_set(mode='OBJECT')
    for a in bpy.data.actions:
        bpy.data.actions.remove(a)

    BD.ObjectSelect([arma], active=True)
    bpy.ops.import_scene.pynifly_hkx(filepath=outfile,
                                      rename_bones=True,
                                      blender_xf=False)

    assert arma.animation_data is not None, "Armature has animation after re-import"
    assert arma.animation_data.action is not None, "Armature has action after re-import"

    reimported = arma.animation_data.action
    assert TT.is_eq(int(reimported.frame_end), orig_frame_end, "Frame count preserved")

    fcurves = list(BD.action_fcurves(reimported))
    assert TT.is_gt(len(fcurves), 0, "Re-imported action has fcurves")

    com_curves = [c for c in fcurves if 'NPC COM' in c.data_path]
    assert TT.is_gt(len(com_curves), 0, "NPC COM bone still animated after roundtrip")

    # ── Binary format validation (catches CTD-causing bugs) ──
    import struct as _s

    with open(outfile, 'rb') as f:
        raw = f.read()

    # File header
    assert raw[0x28:0x28+14] == b'hk_2010.2.0-r1', "Version string is hk_2010"

    # Class hashes must be hk_2010, not hk_2014 (FO4)
    cn_abs = _s.unpack_from('<I', raw, 0x40 + 0x14)[0]
    cn_end = cn_abs + _s.unpack_from('<I', raw, 0x40 + 0x18)[0]
    classnames = {}
    pos = cn_abs
    while pos < cn_end:
        h, flags = _s.unpack_from('<IB', raw, pos)
        if h == 0xFFFFFFFF:
            break
        s = pos + 5
        e = raw.index(b'\x00', s)
        classnames[raw[s:e].decode('ascii')] = h
        pos = e + 1

    assert TT.is_eq(classnames.get('hkClassMember'), 0x5C7EA4C2,
                     "hkClassMember hash is hk_2010")
    assert TT.is_eq(classnames.get('hkaAnimationContainer'), 0x8DC20333,
                     "hkaAnimationContainer hash is hk_2010")
    assert TT.is_eq(classnames.get('hkMemoryResourceContainer'), 0x4762F92A,
                     "hkMemoryResourceContainer hash is hk_2010")
    assert 'hkaDefaultAnimatedReferenceFrame' not in classnames, \
        "No hkaDefaultAnimatedReferenceFrame in Skyrim anim"

    # Global fixups must exist (inter-object refs)
    ds_abs = _s.unpack_from('<I', raw, 0xA0 + 0x14)[0]
    global_rel = _s.unpack_from('<I', raw, 0xA0 + 0x1C)[0]
    virt_rel = _s.unpack_from('<I', raw, 0xA0 + 0x20)[0]
    global_count = 0
    pos = ds_abs + global_rel
    while pos + 12 <= ds_abs + virt_rel:
        src, sec, dst = _s.unpack_from('<III', raw, pos)
        if src == 0xFFFFFFFF:
            break
        global_count += 1
        pos += 12
    assert TT.is_eq(global_count, 5, "5 global fixups for inter-object refs")

    # Spline data must use 40-bit quaternions (rot_quant=1), not 48-bit (FO4)
    spline_off = None
    exp_rel = _s.unpack_from('<I', raw, 0xA0 + 0x24)[0]
    vpos = ds_abs + virt_rel
    while vpos + 12 <= ds_abs + exp_rel:
        obj, sec, noff = _s.unpack_from('<III', raw, vpos)
        if obj == 0xFFFFFFFF:
            break
        str_s = cn_abs + noff
        str_e = raw.index(b'\x00', str_s)
        if raw[str_s:str_e] == b'hkaSplineCompressedAnimation':
            spline_off = obj
            break
        vpos += 12
    assert spline_off is not None, "Found spline anim object"

    P = 8
    base_sz = 2 * P
    arr_sz = P + 8
    o_ann = base_sz + 16 + P
    o_post_ann = o_ann + arr_sz
    o_block_offsets = ((o_post_ann + 28 + P - 1) & ~(P - 1))
    o_data = o_block_offsets + 4 * arr_sz

    local_rel = _s.unpack_from('<I', raw, 0xA0 + 0x18)[0]
    data_blob_off = None
    lpos = ds_abs + local_rel
    while lpos + 8 <= ds_abs + global_rel:
        src, dst = _s.unpack_from('<II', raw, lpos)
        if src == 0xFFFFFFFF:
            break
        if src == spline_off + o_data:
            data_blob_off = dst
            break
        lpos += 8
    assert data_blob_off is not None, "Data blob fixup found"

    rot_quant = (raw[ds_abs + data_blob_off] >> 2) & 0x0F
    assert TT.is_eq(rot_quant, 1, "Skyrim uses rot_quant=1 (40-bit), not 2 (48-bit)")
