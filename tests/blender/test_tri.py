"""TRI / TRIP morph files and shape keys tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *


@TT.category('SKYRIMSE', 'BODYPART', 'TRI')
def TEST_HEADPART():
    """Can read & write an SE head part"""
    # Tri files can be loaded up into a shape in blender as shape keys. On SE, when there
    # are shape keys a BSDynamicTriShape is used on export.
    testfile = TTB.test_file(r"tests/SkyrimSE/malehead.nif")
    testtri = TTB.test_file(r"tests/SkyrimSE/malehead.tri")
    testfileout = TTB.test_file(r"tests/out/TEST_HEADPART.nif")
    testfileout2 = TTB.test_file(r"tests/out/TEST_HEADPART2.nif")
    testfileout3 = TTB.test_file(r"tests/out/TEST_HEADPART3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, import_tris=False)
    obj = bpy.context.object

    bpy.ops.import_scene.pyniflytri(filepath=testtri)

    TT.assert_eq(len(obj.data.shape_keys.key_blocks), 45, "Key block count")
    TT.assert_eq(obj.data.shape_keys.key_blocks[0].name, "Basis", "First key block name")
    TT.assert_contains('BigAah', [k.name for k in obj.data.shape_keys.key_blocks], "Has BigAah key")
    TT.assert_equiv(obj.data.shape_keys.key_blocks['BigAah'].value, 0.0, "BigAah value")

    ### EXPORT SIMPLE ###

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game='SKYRIMSE')
    
    nif2 = pyn.NifFile(testfileout)
    head2 = nif2.shapes[0]
    TT.assert_eq(len(nif2.shapes), 1, "shape count")
    TT.assert_eq(head2.blockname, "BSDynamicTriShape", "Block type")

    ### EXPORT SHAPE KEY ###

    # We can export whatever shape is defined by the shape keys.
    obj.data.shape_keys.key_blocks['Blink.L'].value = 1
    obj.data.shape_keys.key_blocks['MoodHappy'].value = 1
    bpy.ops.export_scene.pynifly(filepath=testfileout2, target_game='SKYRIMSE', 
                                 export_modifiers=True)
    
    nif3 = pyn.NifFile(testfileout2)
    head3 = nif3.shapes[0]
    eyelid = TTB.find_vertex(obj.data, [-2.52558, 7.31011, 124.389])
    mouth = TTB.find_vertex(obj.data, [1.8877, 7.50949, 118.859])
    TT.assert_equiv_not(head2.verts[eyelid], head3.verts[eyelid], "vert position")
    TT.assert_equiv_not(head2.verts[mouth], head3.verts[mouth], "vert position")

    ### EXPORT WITH MODIFIER ###

    obj.data.shape_keys.key_blocks['Blink.L'].value = 0
    obj.data.shape_keys.key_blocks['MoodHappy'].value = 0
    mod = obj.modifiers.new("Decimate", 'DECIMATE')
    mod.ratio = 0.2
    bpy.ops.export_scene.pynifly(filepath=testfileout3, 
                                 target_game='SKYRIMSE', 
                                 export_modifiers=True,
                                 intuit_defaults=False,)
    nif4 = pyn.NifFile(testfileout3)
    head4 = nif4.shapes[0]
    assert TT.is_lt(len(head4.verts), 300, "Vert count")


@TT.category('SKYRIM', 'BODYPART', 'TRI')
def TEST_TRI_SIMPLE():
    """Can create and export a mesh with shapekeys to a tri file."""
    tricubenif = TTB.test_file(r"tests\Out\tricube01.nif")
    tricubeniftri = TTB.test_file(r"tests\Out\tricube01.tri")
    tricubenifchg = TTB.test_file(r"tests\Out\tricube01chargen.tri")

    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.selected_objects[0]
    cube.name = "TriCube"
    sk1 = cube.shape_key_add()
    sk1.name = "Aah"
    sk2 = cube.shape_key_add()
    sk2.name = "CombatAnger"
    sk3 = cube.shape_key_add()
    sk3.name = "*Extra"
    sk4 = cube.shape_key_add()
    sk4.name = "BrowIn"
    bpy.ops.export_scene.pynifly(filepath=tricubenif, target_game='SKYRIM', intuit_defaults=False)

    assert os.path.exists(tricubenif), f"Error: Should have exported {tricubenif}"
    assert os.path.exists(tricubeniftri), f"Error: Should have exported {tricubeniftri}"
    assert os.path.exists(tricubenifchg), f"Error: Should have exported {tricubenifchg}"
    
    cubetri = TriFile.from_filepath(tricubeniftri)
    assert "Aah" in cubetri.morphs, f"Error: 'Aah' should be in tri"
    assert "BrowIn" not in cubetri.morphs, f"Error: 'BrowIn' should not be in tri"
    assert "*Extra" not in cubetri.morphs, f"Error: '*Extra' should not be in tri"
    
    cubechg = TriFile.from_filepath(tricubenifchg)
    assert "Aah" not in cubechg.morphs, f"Error: 'Aah' should not be in chargen"
    assert "BrowIn" in cubechg.morphs, f"Error: 'BrowIn' should be in chargen"
    assert "*Extra" not in cubechg.morphs, f"Error: '*Extra' should not be in chargen"
    

@TT.category('FO4', 'TRI')
@TT.expect_errors(("Could not find materials file",))
def TEST_TRI_EXISTING():
    """Can load a tri file into an existing mesh"""

    testfile = TTB.test_file(r"tests\FO4\meshes\CheetahMaleHead.nif")
    testtri2 = TTB.test_file(r"tests\FO4\meshes\CheetahMaleHead.tri")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object

    # log.debug(f"Importing tri with {bpy.context.object.name} selected")
    bpy.ops.import_scene.pyniflytri(filepath=testtri2)

    assert TT.is_ge(len(obj.data.shape_keys.key_blocks), 47, "Shape key count")


@TT.category('FO4', 'TRI')
def TEST_TRI_STANDALONE():
    """Can load a tri file as a new mesh"""
    testtri3 = TTB.test_file(r"tests\FO4\meshes\CheetahMaleHead.tri")
    testout2 = TTB.test_file(r"tests\Out\CheetahMaleHead02.nif")
    testout2tri = TTB.test_file(r"tests\Out\CheetahMaleHead02.tri")
    testout2chg = TTB.test_file(r"tests\Out\CheetahMaleHead02chargen.tri")

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None
    bpy.ops.import_scene.pyniflytri(filepath=testtri3)
    triobj = bpy.context.object
    assert triobj.name.startswith("CheetahMaleHead"), f"Error: Should be named like tri file, found {triobj.name}"
    assert "LJaw" in triobj.data.shape_keys.key_blocks.keys(), "Error: Should be no keys missing"
    
    ### Can export a shape with tris

    bpy.ops.export_scene.pynifly(filepath=testout2, target_game="FO4", intuit_defaults=False)
    
    ### Check export
    nif2 = pyn.NifFile(testout2)
    tri2 = TriFile.from_filepath(testout2tri)
    assert not os.path.exists(testout2chg), f"{testout2chg} should not have been created"
    assert TT.is_eq(len(nif2.shapes[0].verts), len(tri2.vertices), "Vert count")
    assert TT.is_eq(len(nif2.shapes[0].tris), len(tri2.faces), "Face count")
    assert TT.is_eq(tri2.header.morphNum, len(triobj.data.shape_keys.key_blocks)-1, "morph count")
    

@TT.category('SKYRIM', 'TRI')
def TEST_TRI_EYES():
    """Child eyes tris are odd--handle them correctly."""
    testfile = TTB.test_file(r"tests\Skyrim\eyeschild.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)


@TT.category('SKYRIMSE', 'TRI')
def TEST_TRI_HIMBO():
    """HIMBO tris are odd."""
    testfile = TTB.test_file(r"tests\SkyrimSE\himbo.nif")
    testfile2 = TTB.test_file(r"tests\SkyrimSE\himbo.tri")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    assert len(bpy.data.objects) > 2, f"Have more than 2 objects: {bpy.data.objects}"
    bpy.ops.import_scene.pyniflytri(filepath=testfile2)


@TT.category('FONV', 'TRI')
def TEST_TRI_WILLOW():
    """Import tri file correctly"""
    testfile = TTB.test_file(r"tests\FONV\headfemale_willow.tri")
    bpy.ops.import_scene.pyniflytri(filepath=testfile)
    assert bpy.context.object.name is not None, f"Imported tri file: {bpy.context.object.name}"


@TT.category('FO4', 'TRI')
def TEST_TRI_BASEMALEHEAD():
    """Import tri file correctly when the nif has more verts than the tri."""
    testfile = TTB.test_file(r"tests\FO4\basemalehead.nif")
    testfile2 = TTB.test_file(r"tests\FO4\basemalehead.tri")
    bpy.ops.import_scene.pynifly(filepath=testfile)
    assert bpy.context.object.name is not None, f"Imported nif file: {bpy.context.object.name}"
    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 1, f"Have one mesh: {meshes}"
    mesh = meshes[0]
    assert mesh.data.shape_keys is not None, "Mesh has shape keys"
    assert len(mesh.data.shape_keys.key_blocks) > 5, f"Expected more than 5 shape keys, got {len(mesh.data.shape_keys.key_blocks)}"


@TT.category('SKYRIMSE', 'SHAPEKEY')
def TEST_IMPORT_AS_SHAPES():
    # When two files are selected for import, they are imported as shape keys if possible.
    """Can import 2 meshes as shape keys"""

    testfiles = [{"name": TTB.test_file(r"tests\SkyrimSE\body1m_0.nif")}, 
                 {"name": TTB.test_file(r"tests\SkyrimSE\body1m_1.nif")}, ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert TT.is_eq(len(meshes), 2, f"mesh count")
    sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
    assert TT.is_samemembers(sknames0, ['Basis', '_0', '_1'], f"{meshes[0].name} Shape key names")
    sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
    assert TT.is_samemembers(sknames1, ['Basis', '_0', '_1'], f"{meshes[1].name} Shape keys names")
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    assert TT.is_eq(len(armatures), 1, f"armature count")


@TT.category('SKYRIMSE', 'SHAPEKEY')
def TEST_ADD_SHAPES():
    # When an active shape matches a shape being imported, the second is imported as a shape key.

    testfile1 = TTB.test_file(r"tests\SkyrimSE\femalefeet_0.nif")
    testfile2 = TTB.test_file(r"tests\SkyrimSE\femalefeet_1.nif")
    
    bpy.ops.import_scene.pynifly(filepath=testfile1)

    obj1 = bpy.context.object
    assert obj1.data.shape_keys is None, "No shape keys yet"

    bpy.ops.import_scene.pynifly(filepath=testfile2, import_shapekeys=True)

    assert bpy.context.object == obj1, "Same object still active"
    assert obj1.data.shape_keys is not None, "Now have shape keys"


@TT.category('FO4', 'BODYPART', 'SHAPEKEY')
def TEST_IMPORT_MULT_SHAPES():
    """Can import >2 meshes as shape keys"""
    # When multiple files are selected for a single import, they are connected up as 
    # shape keys if possible.

    testfiles = [{"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_Cat.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_CatF.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_Horse.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_Hyena.nif")}, 
                    {"name": TTB.test_file(r"tests\FO4\PoliceGlasses\Glasses_LionLyk.nif")}, 
                    ]
    bpy.ops.import_scene.pynifly(files=testfiles)

    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    assert len(meshes) == 2, f"Have 2 meshes: {meshes}"
    sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
    assert set(sknames0) == set(['Basis', '_Cat', '_CatF', '_Horse', '_Hyena', '_LionLyk']), \
        f"Shape keys are named correctly: {sknames0}"
    sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
    assert set(sknames1) == set(['Basis', '_Cat', '_CatF', '_Horse', '_Hyena', '_LionLyk']), \
        f"Shape keys are named correctly: {sknames1}"
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    assert len(armatures) == 1, f"Have 1 armature: {armatures}"


@TT.category('FO4', 'BODYPART', 'SHAPEKEY')
def TEST_EXP_SK_RENAMED():
    """Ensure renamed shape keys export properly"""
    if bpy.app.version[0] < 3: return

    # The export/import process can change left/right shape keys to better match Blender's
    # naming conventions.
    #
    # Doesn't work on 2.x. Not sure why.
    outfile = TTB.test_file(r"tests/Out/TEST_EXP_SK_RENAMED.nif")
    trifile = TTB.test_file(r"tests/Out/TEST_EXP_SK_RENAMED.tri")
    chargenfile = TTB.test_file(r"tests/Out/TEST_EXP_SK_RENAMEDchargen.tri")

    TTB.append_from_file("BaseFemaleHead:0", True, r"tests\FO4\FemaleHead.blend", 
                     r"\Object", "BaseFemaleHead:0")

    head = bpy.data.objects["BaseFemaleHead:0"]
    initial_keys = set(head.data.shape_keys.key_blocks.keys())

    pyn.NifFile.clear_log()
    BD.ObjectSelect((bpy.data.objects["BaseFemaleHead:0"],), active=True)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')
    
    ### CHECK EXPORT ###

    assert "ERROR" not in pyn.NifFile.message_log(), \
        f"Error: Expected no error message, got: \n{pyn.NifFile.message_log()}---\n"
    assert not os.path.exists(chargenfile), f"Chargen file not created: {os.path.exists(chargenfile)}"

    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, f"Expected head nif"

    ### CHECK TRI FILE ###
    
    tri1 = TriFile.from_filepath(trifile)
    new_keys = set()
    d = BD.gameSkeletons["FO4"]
    for m in tri1.morphs.keys():
        if m in d.morph_dic_blender:
            new_keys.add(d.morph_dic_blender[m])
        else:
            new_keys.add(m)

    assert new_keys == initial_keys, f"Got same keys back as written: {new_keys - initial_keys} / {initial_keys - new_keys}"
    assert len(tri1.morphs) == 51, f"Expected 51 morphs, got {len(tri1.morphs)} morphs: {tri1.morphs.keys()}"

    ### RE-IMPORT NIF ###

    # Hide what we previously loaded so we can see what is imported
    for obj in bpy.context.scene.objects:
        obj.hide_set(True)

    bpy.ops.import_scene.pynifly(filepath=outfile)
    obj = bpy.context.object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)

    ### RE-IMPORT TRI ###

    bpy.ops.import_scene.pyniflytri(filepath=trifile)

    ### CHECK ###

    TT.assert_eq(len(obj.data.shape_keys.key_blocks), 51, f"key block count")
    TT.assert_contains('Smile.L', obj.data.shape_keys.key_blocks, f"Expected key")


@TT.category('SKYRIMSE', 'BODYPART', 'SHAPEKEY')
def TEST_SK_MULT():
    """Export multiple objects with only some shape keys"""

    outfile = TTB.test_file(r"tests/Out/TEST_SK_MULT.nif")
    outfile0 = TTB.test_file(r"tests/Out/TEST_SK_MULT_0.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_SK_MULT_1.nif")

    TTB.append_from_file("CheMaleMane", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "CheMaleMane")
    TTB.append_from_file("MaleTail", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "MaleTail")
    bpy.context.view_layer.objects.active = bpy.data.objects["CheMaleMane"]
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects["CheMaleMane"].select_set(True)
    bpy.data.objects["MaleTail"].select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    nif1 = pyn.NifFile(outfile1)
    assert len(nif1.shapes) == 2, "Wrote the 1 file successfully"
    assert 'NPC Spine2 [Spn2]' in nif1.nodes, "Found spine2 bone"
    assert 'TailBone01' in nif1.nodes, "Found Tailbone01"
    assert 'NPC L Clavicle [LClv]' in nif1.nodes, "Found Clavicle"

    nif0 = pyn.NifFile(outfile0)
    assert len(nif0.shapes) == 2, "Wrote the 0 file successfully"
    assert 'NPC Spine2 [Spn2]' in nif0.nodes, "Found Spine2 in _0 file"
    assert 'TailBone01' in nif0.nodes, "Found tailbone01 in _0 file"
    assert 'NPC L Clavicle [LClv]' in nif0.nodes, "Found clavicle in _0 file"


@TT.category('SKYRIM', 'TRI')
def TEST_TRI2():
    """Regression: Test correct improt of tri"""
    testfile = TTB.test_file(r"tests/Skyrim/Meshes/OtterMaleHead.nif")
    trifile = TTB.test_file(r"tests/Skyrim/Meshes/OtterMaleHeadChargen.tri")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    bpy.ops.import_scene.pyniflytri(filepath=trifile)

    v1 = obj.data.shape_keys.key_blocks['VampireMorph'].data[1]
    assert v1.co[0] <= 30, "Shape keys not relative to current mesh"


@TT.category('SKYRIM', 'TRI')
@TT.expect_errors( ('Number of verticies differs from number of UV coordinates',) )
def TEST_BAD_TRI():
    """Tris with messed up UVs can be imported"""
    # Tri files have UVs in them, but it's mostly not used, and some tris have messed up
    # UVs. Make sure they can be read anyway.

    testfile = TTB.test_file(r"tests/Skyrim/bad_tri.tri")
    testfile2 = TTB.test_file(r"tests/Skyrim/bad_tri_2.tri")
    
    bpy.ops.import_scene.pyniflytri(filepath=testfile)
    obj = bpy.context.object
    assert len(obj.data.vertices) == 6711, f"Expected 6711 vertices, found {len(obj.data.vertices)}"

    bpy.ops.import_scene.pyniflytri(filepath=testfile2)
    obj2 = bpy.context.object
    assert len(obj2.data.vertices) == 11254, f"Expected 11254 vertices, found {len(obj2.data.vertices)}"


@TT.category('SKYRIMSE', 'EXTRA_DATA', 'TRI')
def TEST_TRIP_SE():
    """Bodypart tri extra data and file are written on export"""
    # Special bodytri files allow for Bodyslide or FO4 body morphing.
    outfile = TTB.test_file(r"tests/Out/TEST_TRIP_SE.nif")
    outfile1 = TTB.test_file(r"tests/Out/TEST_TRIP_SE_1.nif")
    outfiletrip = TTB.test_file(r"tests/Out/TEST_TRIP_SE.tri")

    TTB.append_from_file("Penis_CBBE", True, r"tests\SkyrimSE\HorseFuta.blend", 
                     r"\Object", "Penis_CBBE")
    bpy.ops.object.select_all(action='DESELECT')
    obj = TTB.find_shape("Penis_CBBE")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # intuit_defaults=False honors these kwargs directly, so the test doesn't depend on the
    # (user-configurable) addon preference default for write_bodytri.
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE', write_bodytri=True,
                                 intuit_defaults=False)

    print(' ------- Check --------- ')
    nifcheck = pyn.NifFile(outfile1)

    bodycheck = nifcheck.shape_dict["Penis_CBBE"]
    assert TT.is_eq(bodycheck.name, "Penis_CBBE", f"Penis found")

    stringdata = [sd for sd in bodycheck.extra_data(blockname="NiStringExtraData")]
    assert stringdata, f"Found string data"
    sd = stringdata[0]
    assert TT.is_eq(sd.name, 'BODYTRI', f"BODYTRI string data")
    assert TT.is_eq(sd.string_data.endswith("TEST_TRIP_SE.tri"), True, f"BODYTRI filename")

    tripcheck = TripFile.from_filepath(outfiletrip)
    assert TT.is_eq(len(tripcheck.shapes), 1, f"shape count")
    bodymorphs = tripcheck.shapes['Penis_CBBE']
    assert TT.is_eq(len(bodymorphs), 27, f"morphs count")
    assert TT.is_contains("CrotchBack", bodymorphs.keys(), f"morphs")


@TT.category('FO4', 'BODYPART', 'TRI')
def TEST_TRIP():
    """Body tri extra data and file are written on export"""
    outfile = TTB.test_file(r"tests/Out/TEST_TRIP.nif")
    outfiletrip = TTB.test_file(r"tests/Out/TEST_TRIP.tri")

    TTB.append_from_file("BaseMaleBody", True, r"tests\FO4\BodyTalk.blend", r"\Object", "BaseMaleBody")
    bpy.ops.object.select_all(action='DESELECT')
    body = TTB.find_shape("BaseMaleBody")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', write_bodytri=True,
                                 intuit_defaults=False)

    print(' ------- Check --------- ')
    nifcheck = pyn.NifFile(outfile)

    bodycheck = nifcheck.shape_dict["BaseMaleBody"]
    assert TT.is_eq(bodycheck.name, "BaseMaleBody", f"Body found in nif")

    stringdata = [sd for sd in nifcheck.root.extra_data(blockname="NiStringExtraData")]
    assert stringdata, f"Found string data"
    sd = stringdata[0]
    assert TT.is_eq(sd.name, 'BODYTRI', f"BODYTRI string data")
    assert TT.is_eq(sd.string_data.endswith("TEST_TRIP.tri"), True, f"BODYTRI filename")

    tripcheck = TripFile.from_filepath(outfiletrip)
    assert TT.is_eq(len(tripcheck.shapes), 1, f"shape count")
    bodymorphs = tripcheck.shapes['BaseMaleBody']
    assert TT.is_gt(len(bodymorphs), 30, f"morphs count: {len(bodymorphs)}")
    assert TT.is_contains("BTShoulders", bodymorphs.keys(), f"morphs")


@TT.category('FO4', 'BODYPART', 'TRI')
def TEST_TRIP_REIMPORT():
    """Re-importing an FO4 nif that carries a BODYTRI + .tri loads the trip
    morphs as shape keys.

    Regression: import_tris passed find_trip's *path* straight to import_trip,
    which expects a loaded TripFile, crashing with
    'WindowsPath has no attribute shapes'. Export under a 'meshes' dir so the
    BODYTRI ref resolves on re-import (find_trip needs a 'meshes' segment).
    """
    outfile = TTB.test_file(r"tests/Out/meshes/TEST_TRIP_REIMPORT.nif")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    TTB.append_from_file("BaseMaleBody", True, r"tests\FO4\BodyTalk.blend", r"\Object", "BaseMaleBody")
    bpy.ops.object.select_all(action='DESELECT')
    body = TTB.find_shape("BaseMaleBody")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4', write_bodytri=True)

    # Fresh scene, then re-import the exported nif: the BODYTRI -> .tri must
    # load as shape keys without the TripFile crash.
    TTB.clear_all()
    res = bpy.ops.import_scene.pynifly(filepath=outfile)
    assert 'FINISHED' in res, "re-import with BODYTRI succeeds (no TripFile crash)"
    body2 = TTB.find_shape("BaseMaleBody")
    assert body2 is not None, "body re-imported"
    assert body2.data.shape_keys is not None, "trip morphs loaded as shape keys"
    assert TT.is_gt(len(body2.data.shape_keys.key_blocks), 1,
                    "multiple morph shape keys loaded from the trip")


@TT.category('FO4', 'FACEBONES', 'TRI')
def TEST_FACEBONE_EXPORT():
    """Test can export facebones + regular nif; shapes with hidden verts export correctly"""
    # Facebones are exported along with the regular nif as long as either they are 
    # both selected or if there's an armature modifier for both on the shape. 
    # This test doesn't check that second condition.

    outfile = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT.nif", output=True)
    outfile_fb = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif", output=True)
    outfile_tri = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT.tri", output=True)
    outfile_chargen = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri")
    outfile2 = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif", output=True)
    outfile2_fb = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif", output=True)

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = TTB.append_from_file("HorseFemaleHead", False, r"tests\FO4\HeadFaceBones.blend", r"\Object", "HorseFemaleHead")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen",
                                 intuit_defaults=False)

    # Exporter generates normal and facebones nif file
    nif1 = pyn.NifFile(outfile)
    assert len(nif1.shapes) == 1, "Write the file successfully"
    assert len(nif1.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
    nif2 = pyn.NifFile(outfile_fb)
    assert len(nif2.shapes) == 1
    assert len(nif2.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

    # No facebones in the normal file
    # (Not sure if facebones nif needs the normal bones--they are there in vanilla)
    assert len([x for x in nif1.nodes.keys() if "skin_bone" in x]) == 0, f"Expected no skin_bone nodes in regular nif file; found {nif1.nodes.keys()}"
    #assert len([x for x in nif1.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif2.nodes.keys()}"

    # Exporter generates a single tri file named after the normal file
    tri1 = TriFile.from_filepath(outfile_tri)
    assert len(tri1.morphs) > 0
    tri2 = TriFile.from_filepath(outfile_chargen)
    assert len(tri2.morphs) > 0

    # Same behavior if the shape is parented to the facebones skeleton and the normal skeleton is 
    # exported
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active  = bpy.data.objects['HorseFemaleHead']
    bpy.ops.object.parent_clear(type='CLEAR')
    bpy.context.view_layer.objects.active  = bpy.data.objects['FaceBonesSkel']
    bpy.data.objects['HorseFemaleHead'].select_set(True)
    bpy.ops.object.parent_set(type='ARMATURE_NAME') 
    bpy.data.objects['FullBodySkel'].select_set(True)

    # Export shape with facebones parent
    bpy.ops.export_scene.pynifly(filepath=outfile2, target_game='FO4')

    nif3 = pyn.NifFile(outfile2)
    assert len(nif3.shapes) == 1, "Write the file successfully"
    assert len(nif3.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
    nif4 = pyn.NifFile(outfile2_fb)
    assert len(nif4.shapes) == 1
    assert len(nif4.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

    skinbones = [x for x in nif3.nodes.keys() if "skin_bone" in x]
    assert len(skinbones) == 0, f"Expected no skin_bone nodes in regular nif file; found {skinbones}"
    #assert len([x for x in nif4.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif4.nodes.keys()}"


@TT.category('FO4', 'FACEBONES', 'TRI')
def TEST_FACEBONE_EXPORT2():
    """Test can export facebones + regular nif; shapes with hidden verts export correctly"""
    # Regression. Test that facebones and regular mesh are both exported.

    outfile = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2.nif")
    outfile_fb = TTB.test_file(r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif")

    # Have a head shape parented to the normal skeleton but with facebone weights as well
    obj = TTB.append_from_file("FemaleHead.Export.001", False, r"tests\FO4\Animatron Space Simple.blend", r"\Object", "FemaleHead.Export.001")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='SELECT')

    # Normal and Facebones skeleton selected for export
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4", chargen_ext="_chargen")

    outnif = pyn.NifFile(outfile)
    assert len(outnif.shapes) >= 1, f"Have shapes in export file: {outnif.shapes}"

    outniffb = pyn.NifFile(outfile_fb)
    assert len(outniffb.shapes) >= 1, f"Have shapes in facebones export file: {outniffb.shapes}"
