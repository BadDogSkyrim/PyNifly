"""Python Tests for running in Blender

    This file is for older, standard regression tests.
"""

from test_tools import *
from pynifly import *
from trihandler import *

NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"
ALPHA_MAP_NAME = "VERTEX_ALPHA"
GLOSS_SCALE = 100


def get_image_node(node_input):
    """Walk the shader nodes backwards until a texture node is found.
        node_input = the shader node input to follow; may be null"""
    n = None
    if node_input and len(node_input.links) > 0: 
        n = node_input.links[0].from_node

    while n and type(n) != bpy.types.ShaderNodeTexImage:
        if 'Base Color' in n.inputs.keys() and n.inputs['Base Color'].is_linked:
            n = n.inputs['Base Color'].links[0].from_node
        elif 'Image' in n.inputs.keys() and n.inputs['Image'].is_linked:
            n = n.inputs['Image'].links[0].from_node
        elif 'Color' in n.inputs.keys() and n.inputs['Color'].is_linked:
            n = n.inputs['Color'].links[0].from_node
        elif 'R' in n.inputs.keys() and n.inputs['R'].is_linked:
            n = n.inputs['R'].links[0].from_node
    return n


def run_tests(dev_path, NifExporter, NifImporter, import_tri):
    TEST_IMP_NORMALS = True
    TEST_COTH_DATA = True
    TEST_MUTANT = True
    TEST_RENAME = True
    TEST_BONE_XPORT_POS = True
    TEST_POT = True
    TEST_3BBB = True
    TEST_BAD_TRI = True
    TEST_TIGER_EXPORT = True
    TEST_EXPORT_HANDS = True
    TEST_PARTITION_ERRORS = True
    TEST_SCALING = True
    TEST_POT = True
    TEST_EXPORT = True
    TEST_IMPORT_ARMATURE = True
    TEST_EXPORT_WEIGHTS = True
    TEST_IMP_EXP_SKY = True
    TEST_IMP_EXP_FO4 = True
    TEST_ROUND_TRIP = True
    TEST_UV_SPLIT = True
    TEST_CUSTOM_BONES = True
    TEST_BPY_PARENT = True
    TEST_BABY = True
    TEST_CONNECTED_SKEL = True
    TEST_TRI = True
    TEST_0_WEIGHTS = True
    TEST_SPLIT_NORMAL = True
    TEST_SKEL = True
    TEST_PARTITIONS = True
    TEST_SEGMENTS = True
    TEST_BP_SEGMENTS = True
    TEST_ROGUE01 = True
    TEST_ROGUE02 = True
    TEST_NORMAL_SEAM = True
    TEST_COLORS = True
    TEST_HEADPART = True
    TEST_FACEBONES = True
    TEST_FACEBONE_EXPORT = True
    TEST_TIGER_EXPORT = True
    TEST_JIARAN = True
    TEST_SHADER_LE = True
    TEST_SHADER_SE = True
    TEST_SHADER_FO4 = True
    TEST_SHADER_ALPHA = True
    TEST_SHEATH = True
    TEST_FEET = True
    TEST_SKYRIM_XFORM = True
    TEST_TRI2 = True
    TEST_3BBB = True
    TEST_ROTSTATIC = True
    TEST_ROTSTATIC2 = True
    TEST_VERTEX_ALPHA = True


    if TEST_IMP_NORMALS:
        print("### TEST_IMP_NORMALS: Can import normals from nif shape")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/cube.nif")
        NifImporter.do_import(testfile)

        # all loop custom normals point off at diagonals
        obj = bpy.context.object
        for l in obj.data.loops:
            for i in [0, 1, 2]:
                assert round(abs(l.normal[i]), 3) == 0.577, f"Expected diagonal normal, got loop {l.index}/{i} = {l.normal[i]}"


    if TEST_COTH_DATA:
        print("### TEST_COTH_DATA: Can read and write cloth data")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/HairLong01.nif")
        NifImporter.do_import(testfile)
        
        assert 'BSClothExtraData' in bpy.data.objects.keys(), f"Found no cloth extra data in {bpy.data.objects.keys()}"

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_COTH_DATA.nif"), 
                               'FO4')
        exporter.export([bpy.data.objects["HairLong01:0"], 
                         bpy.data.objects["BSClothExtraData"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_COTH_DATA.nif"))
        assert len(nif1.shapes) == 1, f"Expected hair nif"
        assert len(nif1.cloth_data) == 1, f"Expected cloth data"
        assert len(nif1.cloth_data[0][1]) == 46257, f"Expected 46257 bytes of cloth data, found {len(nif1.cloth_data[0][1])}"



    if TEST_BAD_TRI:
        print("### TEST_BAD_TRI: Tris with messed up UVs can be imported")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/bad_tri.tri")
        obj = import_tri(testfile, None)
        assert len(obj.data.vertices) == 6711, f"Expected 6711 vertices, found {len(obj.data.vertices)}"

        testfile2 = os.path.join(pynifly_dev_path, r"tests/Skyrim/bad_tri_2.tri")
        obj2 = import_tri(testfile2, None)
        assert len(obj2.data.vertices) == 11254, f"Expected 11254 vertices, found {len(obj2.data.vertices)}"


    if TEST_TIGER_EXPORT:
        print("### TEST_TIGER_EXPORT: Tiger head exports without errors")

        clear_all()
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT_faceBones.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.tri"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT_chargen.tri"))

        append_from_file("TigerMaleHead", True, r"tests\FO4\Tiger.blend", r"\Object", "TigerMaleHead")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"), 
                               'FO4')
        exporter.export([bpy.data.objects["TigerMaleHead"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"))
        assert len(nif1.shapes) == 1, f"Expected tiger nif"


    if TEST_3BBB:
        print("## TEST_3BBB: Test that this mesh imports with the right transforms")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/3BBB_femalebody_1.nif")
        NifImporter.do_import(testfile)
        
        obj = bpy.context.object
        assert obj.location[0] == 0, f"Expected body to be centered on x-axis, got {obj.location[:]}"

        print("## Test that the same armature is used for the next import")
        arma = bpy.data.objects['Scene Root']
        bpy.ops.object.select_all(action='DESELECT')
        arma.select_set(True)
        bpy.context.view_layer.objects.active = arma
        testfile2 = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/3BBB_femalehands_1.nif")
        NifImporter.do_import(testfile2)

        arma2 = bpy.context.object.parent
        assert arma2.name == arma.name, f"Should have parented to same armature: {arma2.name} != {arma.name}"

    if TEST_MUTANT:
        print("### TEST_MUTANT: Test that the supermutant body imports correctly the *second* time")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/testsupermutantbody.nif")
        imp = NifImporter.do_import(testfile, NifImporter.ImportFlags.RENAME_BONES)
        log.debug(f"Expected -140 z translation in first nif, got {imp.nif.shapes[0].global_to_skin.translation[2]}")

        sm1 = bpy.context.object
        assert round(sm1.location[2]) == 140, f"Expect first supermutant body at 140 Z, got {sm1.location[2]}"
        assert round(imp.nif.shapes[0].global_to_skin.translation[2]) == -140, f"Expected -140 z translation in first nif, got {imp.nif.shapes[0].global_to_skin.translation[2]}"

        imp2 = NifImporter.do_import(testfile, NifImporter.ImportFlags.RENAME_BONES)
        sm2 = bpy.context.object
        assert round(sm2.location[2]) == 140, f"Expect supermutant body at 140 Z, got {sm2.location[2]}"

        
    if TEST_RENAME:
        print("### TEST_RENAME: Test that renaming bones works correctly")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"C:\Users\User\OneDrive\Dev\PyNifly\PyNifly\tests\Skyrim\femalebody_1.nif")
        imp = NifImporter.do_import(testfile, NifImporter.ImportFlags.CREATE_BONES)

        body = bpy.context.object
        vgnames = [x.name for x in body.vertex_groups]
        vgxl = list(filter(lambda x: ".L" in x or ".R" in x, vgnames))
        assert len(vgxl) == 0, f"Expected no vertex groups renamed, got {vgxl}"

        armnames = [b.name for b in body.parent.data.bones]
        armxl = list(filter(lambda x: ".L" in x or ".R" in x, armnames))
        assert len(armxl) == 0, f"Expected no bones renamed in armature, got {vgxl}"


    if TEST_BONE_XPORT_POS:
        print("### Test that bones named like vanilla bones but from a different skeleton export to the correct position")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\draugr.nif")
        imp = NifImporter.do_import(testfile, 0)
        draugr = bpy.context.object
        spine2 = draugr.parent.data.bones['NPC Spine2 [Spn2]']
        assert round(spine2.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2.head[2]}"

        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BONE_XPORT_POS.nif")
        exp = NifExporter(outfile, 'SKYRIM')
        exp.export([bpy.data.objects["Body_Male_Naked"]])

        impcheck = NifImporter.do_import(outfile, 0)

        nifbone = impcheck.nif.nodes['NPC Spine2 [Spn2]']
        assert round(nifbone.transform.translation[2], 2) == 102.36, f"Expected nif location at z 102.36, found {nifbone.transform.translation[2]}"

        draugrcheck = bpy.context.object
        spine2check = draugrcheck.parent.data.bones['NPC Spine2 [Spn2]']
        assert round(spine2check.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2check.head[2]}"


    if TEST_EXPORT_HANDS:
        print("### TEST_EXPORT_HANDS: Test that hand mesh doesn't throw an error")

        outfile1 = os.path.join(pynifly_dev_path, r"tests/Out/TEST_EXPORT_HANDS.nif")
        remove_file(outfile1)

        append_from_file("SupermutantHands", True, r"tests\FO4\SupermutantHands.blend", r"\Object", "SupermutantHands")
        bpy.ops.object.select_all(action='SELECT')

        exp = NifExporter(outfile1, 'FO4')
        exp.export(bpy.context.selected_objects)

        assert os.path.exists(outfile1)


    if TEST_PARTITION_ERRORS:
        print("### TEST_PARTITION_ERRORS: Partitions with errors raise errors")

        clear_all()

        append_from_file("SynthMaleBody", True, r"tests\FO4\SynthBody02.blend", r"\Object", "SynthMaleBody")

        # Partitions must divide up the mesh cleanly--exactly 1 partition per tri
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"), 
                               'FO4')
        exporter.export([bpy.data.objects["SynthMaleBody"]])
        assert len(exporter.warnings) > 0, f"Error: Export should have generated warnings: {exporter.warnings}"
        print(f"Exporter warnings: {exporter.warnings}")
        assert MULTIPLE_PARTITION_GROUP in bpy.data.objects["SynthMaleBody"].vertex_groups, "Error: Expected group to be created for tris in multiple partitions"


    if TEST_SCALING:
        print("### Test that scale factors happen correctly")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\statuechampion.nif")
        NifImporter.do_import(testfile, 0)
        
        base = bpy.data.objects['basis1']
        assert int(base.scale[0]) == 10, f"ERROR: Base scale should be 10, found {base.scale[0]}"
        tail = bpy.data.objects['tail_base.001']
        assert round(tail.scale[0], 1) == 1.7, f"ERROR: Tail scale should be ~1.7, found {tail.scale}"
        assert round(tail.location[0], 0) == -158, f"ERROR: Tail x loc should be -158, found {tail.location}"

        testout = os.path.join(pynifly_dev_path, r"tests\Out\TEST_SCALING.nif")
        exp = NifExporter.do_export(testout, "SKYRIM", bpy.data.objects[:])
        checknif = NifFile(testout)
        checkfoot = checknif.shape_dict['FootLowRes']
        assert checkfoot.transform.rotation.matrix[0][0] == 1.0, f"ERROR: Foot rotation matrix not identity: {checkfoot.transform.rotation.matrix}"
        assert checkfoot.transform.scale == 1.0, f"ERROR: Foot scale not correct: {checkfoot.transform.scale}"
        checkbase = checknif.shape_dict['basis3']
        assert checkbase.transform.rotation.matrix[0][0] == 1.0, f"ERROR: Base rotation matrix not identity: {checkbase.transform.rotation.matrix}"
        assert checkbase.transform.scale == 10.0, f"ERROR: Base scale not correct: {checkbase.transform.scale}"


    if TEST_POT:
        print("### Test that pot shaders doesn't throw an error")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\spitpotopen01.nif")
        imp = NifImporter.do_import(testfile, 0)
        assert 'ANCHOR:0' in bpy.data.objects.keys()


    if TEST_EXPORT:
        test_title("TEST_EXPORT", "Can export the basic cube")

        clear_all()
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        log.debug("TODO: support objects with flat shading or autosmooth properly")
        for f in cube.data.polygons: f.use_smooth = True

        filepath = os.path.join(dev_path, r"tests\Out\testSkyrim01.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'SKYRIM')
        exporter.export([cube])

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        importer = NifImporter(filepath)
        importer.execute()
        sourceGame = importer.nif.game
        assert sourceGame == "SKYRIM", "ERROR: Wrong game found"

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, f"ERROR: Cube should have 14 verts, has {len(new_cube.data.vertices)}"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, f"ERROR: Cube should have 36 UV locations, has {len(new_cube.data.uv_layers[0].data)}"
        assert len(new_cube.data.polygons) == 12, f"ERROR: Cube should have 12 polygons, has {len(new_cube.data.polygons)}"

        print("## And can do the same for FO4")

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        for f in cube.data.polygons: f.use_smooth = True

        filepath = os.path.join(dev_path, r"tests\Out\testFO401.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'FO4')
        exporter.export([cube])

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        importer = NifImporter(filepath)
        sourceGame = importer.nif.game
        assert sourceGame == "FO4", "ERROR: Wrong game found"
        assert importer.nif.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape, got {f.shapes[0].blockname}"

        importer.execute()

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, f"ERROR: Cube should have 14 verts, has {len(new_cube.data.vertices)}"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, f"ERROR: Cube should have 36 UV locations, has {len(new_cube.data.uv_layers[0].data)}"
        assert len(new_cube.data.polygons) == 12, f"ERROR: Cube should have 12 polygons, has {len(new_cube.data.polygons)}"
        # bpy.data.objects.remove(cube, do_unlink=True)


    if TEST_IMPORT_ARMATURE:
        test_title("TEST_IMPORT_ARMATURE", "Can import a Skyrim head with armature")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        filepath = os.path.join(pynifly_dev_path, "tests\Skyrim\malehead.nif")
        NifImporter.do_import(filepath)
        male_head = bpy.context.selected_objects[0]
        assert round(male_head.location.z, 0) == 120, "ERROR: Object not elevated to position"
        assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"
        
        print("## Can import a FO4 head  with armature")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        filepath = os.path.join(pynifly_dev_path, "tests\FO4\BaseMaleHead.nif")
        f = NifFile(filepath)
        NifImporter.do_import(filepath)
        male_head = bpy.data.objects["BaseMaleHead:0"]
        assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
        assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"


    if TEST_IMP_EXP_SKY:
        test_title("TEST_IMP_EXP_SKY", "Can read the armor nif and spit it back out (no blender shape)")

        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        nif = NifFile(testfile)
        assert "Armor" in nif.getAllShapeNames(), "ERROR: Didn't read armor"

        the_armor = nif.shape_dict["Armor"]
        assert len(the_armor.verts) == 2115, "ERROR: Wrong number of verts"
        assert (len(the_armor.tris) == 3195), "ERROR: Wrong number of tris"

        outfile = os.path.join(pynifly_dev_path, "tests/Out/TestSkinnedFromPy02.nif")
        remove_file(outfile)
        new_nif = NifFile()
        new_nif.initialize("SKYRIM", outfile)
        new_nif.createSkin()
        
        new_armor = new_nif.createShapeFromData("Armor", 
                                                the_armor.verts,
                                                the_armor.tris,
                                                the_armor.uvs,
                                                the_armor.normals)
        new_armor.skin()
        armor_gts = MatTransform((0.000256, 1.547526, -120.343582))
        new_armor.set_global_to_skin(armor_gts)

        for b in the_armor.bone_weights.keys():
            new_armor.add_bone(b)
            new_armor.setShapeWeights(b, the_armor.bone_weights[b])
        
        new_nif.save()
            
    if TEST_IMP_EXP_FO4:
        test_title("TEST_IMP_EXP_FO4", "Can read the body nif and spit it back out (no blender shape)")

        nif = NifFile(os.path.join(pynifly_dev_path, "tests\FO4\BTMaleBody.nif"))
        assert "BaseMaleBody:0" in nif.getAllShapeNames(), "ERROR: Didn't read nif"

        the_body = nif.shape_dict["BaseMaleBody:0"]

        new_nif = NifFile()
        new_nif.initialize("FO4", os.path.join(pynifly_dev_path, "tests/Out/TestSkinnedFO03.nif"))
        new_nif.createSkin()
        
        new_body = new_nif.createShapeFromData("BaseMaleBody:0", 
                                                the_body.verts,
                                                the_body.tris,
                                                the_body.uvs,
                                                the_body.normals)
        new_body.skin()
        body_gts = MatTransform((0.000256, 1.547526, -120.343582))
        new_body.set_global_to_skin(body_gts)

        no_transform = MatTransform()
        for b in the_body.bone_weights.keys():
            new_body.add_bone(b)
            new_body.setShapeWeights(b, the_body.bone_weights[b])
        
        new_nif.save()
            

    if TEST_EXPORT_WEIGHTS:
        test_title("TEST_EXPORT_WEIGHTS", "Import and export with weights")

        clear_all()

        # Import body and armor
        NifImporter.do_import(os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif"))
        the_armor = bpy.data.objects["Armor"]
        the_body = bpy.data.objects["MaleBody"]
        assert 'NPC Foot.L' in the_armor.vertex_groups, f"ERROR: Left foot is in the groups: {the_armor.vertex_groups}"
        
        # Export armor
        filepath_armor = os.path.join(pynifly_dev_path, "tests/out/testArmorSkyrim02.nif")
        remove_file(filepath_armor)
        exporter = NifExporter(filepath_armor, 'SKYRIM')
        exporter.export([the_armor])
        assert os.path.exists(filepath_armor), "ERROR: File not created"

        # Check armor
        ftest = NifFile(filepath_armor)
        assert ftest.shapes[0].name[0:5] == "Armor", "ERROR: Armor not read"
        gts = ftest.shapes[0].global_to_skin
        assert int(gts.translation[2]) == -120, f"ERROR: Armor offset not correct: {gts.translation[2]}"

        # Write armor to FO4 (wrong skeleton but whatevs, just see that it doesn't crash)
        filepath_armor_fo = os.path.join(pynifly_dev_path, r"tests\Out\testArmorFO02.nif")
        remove_file(filepath_armor_fo)
        exporter = NifExporter(filepath_armor_fo, 'FO4')
        exporter.export([the_armor])
        assert os.path.exists(filepath_armor_fo), f"ERROR: File {filepath_armor_fo} not created"

        # Write body 
        filepath_body = os.path.join(pynifly_dev_path, r"tests\Out\testBodySkyrim02.nif")
        body_out = NifFile()
        remove_file(filepath_body)
        exporter = NifExporter(filepath_body, 'SKYRIM')
        exporter.export([the_body])
        assert os.path.exists(filepath_body), f"ERROR: File {filepath_body} not created"
        # Should do some checking here

    if TEST_ROUND_TRIP:
        test_title("TEST_ROUND_TRIP", "Can do the full round trip: nif -> blender -> nif -> blender")

        print("..Importing original file")
        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        NifImporter.do_import(testfile)

        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor1 = obj

        assert int(armor1.location.z) == 120, "ERROR: Armor moved above origin by 120 to skinned position"
        maxz = max([v.co.z for v in armor1.data.vertices])
        minz = min([v.co.z for v in armor1.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices are positioned below origin"

        assert len(armor1.data.vertex_colors) == 0, "ERROR: Armor should have no colors"

        print("..Exporting  to test file")
        outfile1 = os.path.join(pynifly_dev_path, "tests/Out/testSkyrim03.nif")
        remove_file(outfile1)
        exporter = NifExporter(outfile1, 'SKYRIM')
        exporter.export([armor1])
        #export_shape_to(armor1, outfile1, "SKYRIM")
        #export_file_set(outfile1, 'SKYRIM', [''], [armor1], armor1.parent)
        assert os.path.exists(outfile1), "ERROR: Created output file"

        print("..Re-importing exported file")
        NifImporter.do_import(outfile)

        armor2 = None
        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor2 = obj

        assert int(armor2.location.z) == 120, "ERROR: Exported armor is re-imported with same position"
        maxz = max([v.co.z for v in armor2.data.vertices])
        minz = min([v.co.z for v in armor2.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices from exported armor are positioned below origin"

    if TEST_UV_SPLIT:
        test_title("TEST_UV_SPLIT", "Can split UVs properly")

        verts = [(-1.0, -1.0, 0.0), 
                 (1.0, -1.0, 0.0), (-1.0, 1.0, 0.0), (1.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)]
        norms = [(0.0, 0.0, 1.0), (0.0, 0.0, 2.0), (0.0, 0.0, 3.0), (0.0, 0.0, 4.0), (0.0, 0.0, 5.0), (0.0, 0.0, 6.0)]
        weights = [{0: 0.4},
                   {0: 0.6},
                   {0: 1.0},
                   {0: 0.8},
                   {0: 0.3},
                   {0: 0.1}]
        tris  = [(1, 5, 4),
                 (4, 2, 0),
                 (1, 3, 5),
                 (4, 5, 2)]
        loops = [1, 5, 4,
                 4, 2, 0,
                 1, 3, 5,
                 4, 5, 2]
        uvs = [(0.9, 0.1), # vert 1 (tri 0)
               (0.6, 0.9), # vert 5
               (0.6, 0.1), # vert 4
               (0.4, 0.1), # vert 4 (tri 1)
               (0.1, 0.9), # vert 2
               (0.1, 0.1), # vert 0
               (0.9, 0.1), # vert 1 (tri 2)
               (0.9, 0.9), # vert 3
               (0.6, 0.9), # vert 5
               (0.4, 0.1), # vert 4 (tri 3)
               (0.4, 0.9), # vert 5
               (0.1, 0.9)] # vert 2
        new_mesh = bpy.data.meshes.new("TestUV")
        new_mesh.from_pydata(verts, [], tris)
        newuv = new_mesh.uv_layers.new(do_init=False)
        for i, this_uv in enumerate(uvs):
            newuv.data[i].uv = this_uv
        new_object = bpy.data.objects.new("TestUV", new_mesh)
        new_object.data.uv_layers.active = newuv
        bpy.context.collection.objects.link(new_object)
        bpy.context.view_layer.objects.active = new_object

        filepath = os.path.join(pynifly_dev_path, "tests/Out/testUV01.nif")
        exporter = NifExporter(filepath, "SKYRIM")
        exporter.export([new_object])
        #export_file_set(filepath, "SKYRIM", [''], [new_object], None)

        nif_in = NifFile(filepath)
        plane = nif_in.shapes[0]
        assert len(plane.verts) == 8, "Error: Exported nif doesn't have correct verts"
        assert len(plane.uvs) == 8, "Error: Exported nif doesn't have correct UV"
        assert plane.verts[5] == plane.verts[7], "Error: Split vert at different locations"
        assert plane.uvs[5] != plane.uvs[7], "Error: Split vert has different UV locations"

    if TEST_CUSTOM_BONES:
        print('## TEST_CUSTOM_BONES Can handle custom bones correctly')

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\VulpineInariTailPhysics.nif")
        nifimp = NifImporter(testfile)
        bone_xform = nifimp.nif.nodes['Bone_Cloth_H_003'].xform_to_global
        nifimp.execute()

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\Tail01.nif")
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                e = NifExporter(outfile, "FO4")
                e.export([obj])

        test_in = NifFile(outfile)
        new_xform = test_in.nodes['Bone_Cloth_H_003'].xform_to_global
        assert bone_xform == new_xform, \
            f"Error: Bone transform should not change. Expected\n {bone_xform}, found\n {new_xform}"

    if TEST_BPY_PARENT:
        print('### Maintain armature structure')

        # Can intuit structure if it's not in the file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif")
        NifImporter.do_import(testfile)
        for obj in bpy.context.selected_objects:
            if obj.name.startswith("Scene Root"):
                 assert obj.data.bones['NPC Hand.R'].parent.name == 'NPC Forearm.R', "Error: Should find forearm as parent"
                 print(f"Found parent to hand: {obj.data.bones['NPC Hand.R'].parent.name}")

        ## Can read structure if it comes from file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\bear_tshirt_turtleneck.nif")
        NifImporter.do_import(testfile)
        for obj in bpy.context.selected_objects:
            if obj.name.startswith("Scene Root"):
                assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
                assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3.R', "Error: Should find forearm as parent"
                print(f"Found parent to hand: {obj.data.bones['Arm_Hand.R'].parent.name}")
        print('### Maintain armature structure PASSED')

    if TEST_BABY:
        print('## TEST_BABY Can export baby parts')

        # Can intuit structure if it's not in the file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\baby.nif")
        NifImporter.do_import(testfile)
        head = bpy.data.objects['Baby_Head:0']
        eyes = bpy.data.objects['Baby_Eyes:0']

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\baby01.nif")
        e = NifExporter(outfile, 'FO4')
        e.export([eyes, head])
        #export_file_set(outfile, 'FO4', [''], [eyes, head], head.parent)
        #outnif = NifFile()
        #outnif.initialize("FO4", outfile)
        #export_shape(outnif, TripFile(), eyes)
        #export_shape(outnif, TripFile(), head)
        #outnif.save()

        testnif = NifFile(outfile)
        testhead = testnif.shape_by_root('Baby_Head')
        testeyes = testnif.shape_by_root('Baby_Eyes')
        assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
        assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"
        assert testhead.blockname == "BSSubIndexTriShape", f"Error: Expected BSSubIndexTriShape on skinned shape, got {testhead.blockname}"

        # TODO: Test that baby's unkown skeleton is connected
      
    if TEST_CONNECTED_SKEL:
        print('## TEST_CONNECTED_SKEL Can import connected skeleton')

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\vanillaMaleBody.nif")
        NifImporter.do_import(testfile)

        #print("FO4 LArm_UpperTwist1: ", nif.get_node_xform_to_global('LArm_UpperTwist1') )
        #print("FO4 LArm_UpperTwist1_skin: ", nif.get_node_xform_to_global('LArm_UpperTwist1_skin') )

        for s in bpy.context.selected_objects:
            if 'MaleBody.nif' in s.name:
                assert 'Leg_Thigh.L' in s.data.bones.keys(), "Error: Should have left thigh"
                assert s.data.bones['Leg_Thigh.L'].parent.name == 'Pelvis', "Error: Thigh should connect to pelvis"

    if TEST_SKEL:
        print('## TEST_SKEL Can import skeleton file with no shapes')

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"skeletons\FO4\skeleton.nif")

        NifImporter.do_import(testfile)

        arma = bpy.data.objects["skeleton.nif"]
        assert 'Leg_Thigh.L' in arma.data.bones, "Error: Should have left thigh"

    if TEST_TRI:
        test_title("TEST_TRI", "Can load a tri file into an existing mesh")

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\CheetahMaleHead.nif")
        testtri2 = os.path.join(pynifly_dev_path, r"tests\FO4\CheetahMaleHead.tri")
        testtri3 = os.path.join(pynifly_dev_path, r"tests\FO4\CheetahMaleHead.tri")
        testout2 = os.path.join(pynifly_dev_path, r"tests\Out\CheetahMaleHead02.nif")
        testout2tri = os.path.join(pynifly_dev_path, r"tests\Out\CheetahMaleHead02.tri")
        testout2chg = os.path.join(pynifly_dev_path, r"tests\Out\CheetahMaleHead02_chargen.tri")
        tricubenif = os.path.join(pynifly_dev_path, r"tests\Out\tricube01.nif")
        tricubeniftri = os.path.join(pynifly_dev_path, r"tests\Out\tricube01.tri")
        tricubenifchg = os.path.join(pynifly_dev_path, r"tests\Out\tricube01_chargen.tri")
        for f in [testout2, testout2tri, testout2chg, tricubenif]:
            remove_file(f)

        NifImporter.do_import(testfile)

        obj = bpy.context.object
        if obj.type == "ARMATURE":
            obj = obj.children[0]
            bpy.context.view_layer.objects.active = obj

        log.debug(f"Importing tri with {bpy.context.object.name} selected")
        triobj2 = import_tri(testtri2, obj)

        assert len(obj.data.shape_keys.key_blocks) == 47, f"Error: {obj.name} should have enough keys ({len(obj.data.shape_keys.key_blocks)})"

        print("### Can import a simple tri file")

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = None
        triobj = import_tri(testtri3, None)
        assert triobj.name.startswith("CheetahMaleHead.tri"), f"Error: Should be named like tri file, found {triobj.name}"
        assert "LJaw" in triobj.data.shape_keys.key_blocks.keys(), "Error: Should be no keys missing"
        
        print('### Can export a shape with tris')

        e = NifExporter(os.path.join(pynifly_dev_path, testout2), "FO4")
        e.export([triobj])
        #export_file_set(os.path.join(pynifly_dev_path, testout2), "FO4", [''], [triobj], triobj.parent)
        
        print('### Exported shape and tri match')
        nif2 = NifFile(os.path.join(pynifly_dev_path, testout2))
        tri2 = TriFile.from_file(os.path.join(pynifly_dev_path, testout2tri))
        assert not os.path.exists(testout2chg), f"{testout2chg} should not have been created"
        assert len(nif2.shapes[0].verts) == len(tri2.vertices), f"Error vert count should match, {len(nif2.shapes[0].verts)} vs {len(tri2.vertices)}"
        assert len(nif2.shapes[0].tris) == len(tri2.faces), f"Error vert count should match, {len(nif2.shapes[0].tris)} vs {len(tri2.faces)}"
        assert tri2.header.morphNum == len(triobj.data.shape_keys.key_blocks)-1, \
            f"Error: morph count should match, file={tri2.header.morphNum} vs {triobj.name}={len(triobj.data.shape_keys.key_blocks)}"
        
        print('### Tri and chargen export as expected')

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
        e = NifExporter(tricubenif, "SKYRIM")
        e.export([cube])
        #export_file_set(tricubenif, "SKYRIM", [''], [cube], cube.parent)

        assert os.path.exists(tricubenif), f"Error: Should have exported {tricubenif}"
        assert os.path.exists(tricubeniftri), f"Error: Should have exported {tricubeniftri}"
        assert os.path.exists(tricubenifchg), f"Error: Should have exported {tricubenifchg}"
        
        cubetri = TriFile.from_file(tricubeniftri)
        assert "Aah" in cubetri.morphs, f"Error: 'Aah' should be in tri"
        assert "BrowIn" not in cubetri.morphs, f"Error: 'BrowIn' should not be in tri"
        assert "*Extra" not in cubetri.morphs, f"Error: '*Extra' should not be in tri"
        
        cubechg = TriFile.from_file(tricubenifchg)
        assert "Aah" not in cubechg.morphs, f"Error: 'Aah' should not be in chargen"
        assert "BrowIn" in cubechg.morphs, f"Error: 'BrowIn' should be in chargen"
        assert "*Extra" not in cubechg.morphs, f"Error: '*Extra' should not be in chargen"
        

    if TEST_0_WEIGHTS:
        test_title("TEST_0_WEIGHTS", "Gives warning on export with 0 weights")

        baby = append_from_file("TestBabyhead", True, r"tests\FO4\Test0Weights.blend", r"\Collection", "BabyCollection")
        baby.parent.name == "BabyExportRoot", f"Error: Should have baby and armature"
        log.debug(f"Found object {baby.name}")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests\Out\weight0.nif"), "FO4")
        e.export([baby])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests\Out\weight0.nif"), 
        #                "FO4", 
        #                [''],
        #                [baby], 
        #                baby.parent)
        assert UNWEIGHTED_VERTEX_GROUP in baby.vertex_groups, "Unweighted vertex group captures vertices without weights"


    if TEST_SPLIT_NORMAL:
        test_title("TEST_SPLIT_NORMAL", "Can handle meshes with split normals")

        plane = append_from_file("Plane", False, r"tests\skyrim\testSplitNormalPlane.blend", r"\Object", "Plane")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), "FO4")
        e.export([plane])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), 
        #                "FO4", [''], [plane], plane.parent)


    if TEST_PARTITIONS:
        test_title("TEST_PARTITIONS", "Can read Skyrim partions")
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/MaleHead.nif")

        NifImporter.do_import(testfile)

        obj = bpy.context.object
        assert "SBP_130_HEAD" in obj.vertex_groups, "Skyrim body parts read in as vertex groups with sensible names"

        print("### Can write Skyrim partitions")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"), "SKYRIM")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"),
        #                "SKYRIM", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/testPartitionsSky.nif"))
        assert len(nif2.shapes[0].partitions) == 3, "Have all skyrim partitions"
        assert nif2.shapes[0].partitions[2].id == 143, "Have ears"

    if TEST_SEGMENTS:
        test_title("TEST_SEGMENTS", "Can read FO4 segments")
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/VanillaMaleBody.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        assert "FO4 Human Arm.R" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "Should have FO4 segment file read and saved for later use"

        print("### Can write FO4 segments")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"),
        #                "FO4", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"))
        assert len(nif2.shapes[0].partitions) == 7, "Have all FO4 partitions"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == nif2.shapes[0].segment_file, f"Nif should reference segment file, found '{nif2.shapes[0].segment_file}'"

    if TEST_BP_SEGMENTS:
        test_title("TEST_BP_SEGMENTS", "Can read FO4 bodypart segments")
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/Helmet.nif")
        NifImporter.do_import(testfile)

        #for o in bpy.context.selected_objects:
        #    if o.name.startswith("Helmet:0"):
        #        obj = o
        obj = bpy.context.object
        assert "FO4 30 - Hair Top" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
        assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == obj['FO4_SEGMENT_FILE'], "FO4 segment file read and saved for later use"

        print("### Can write FO4 segments")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"),
        #                "FO4", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"))
        assert len(nif2.shapes[0].partitions) == 2, "Have all FO4 partitions"
        ss30 = None
        for p in nif2.shapes[0].partitions:
            for s in p.subsegments:
                if s.user_slot == 30:
                    ss30 = s
                    break
        assert ss30 is not None, "Mesh has FO4Subsegment 30"
        assert ss30.material == 0x86b72980, "FO4Subsegment 30 should have correct material"
        assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == nif2.shapes[0].segment_file, "Nif references segment file"

    if TEST_ROGUE01:
        test_title("TEST_ROGUE01", "Mesh with wonky normals exports correctly")

        obj = append_from_file("MHelmetLight:0", False, r"tests\FO4\WonkyNormals.blend", r"\Object", "MHelmetLight:0")
        assert obj.name == "MHelmetLight:0", "Got the right object"
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE01.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE01.nif"), 
        #                "FO4", [''], [obj], obj.parent)

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE01.nif"))
        shape2 = nif2.shapes[0]

        assert round(shape2.normals[44][0]) == 0, f"Normal should point sraight up, found {shape2.normals[44]}"
        assert round(shape2.normals[44][1]) == 0, f"Normal should point sraight up, found {shape2.normals[44]}"
        assert round(shape2.normals[44][2]) == 1, f"Normal should point sraight up, found {shape2.normals[44]}"

        assert 6.82 == round(shape2.verts[12][0], 2), f"Vert location wrong: 6.82 != {shape2.verts[12][0]}"
        assert 0.58 == round(shape2.verts[12][1], 2), f"Vert location wrong: 0.58 != {shape2.verts[12][0]}"
        assert 9.05 == round(shape2.verts[12][2], 2), f"Vert location wrong: 9.05 != {shape2.verts[12][0]}"
        assert 0.13 == round(shape2.verts[5][0], 2), f"Vert location wrong: 0.13 != {shape2.verts[5][0]}"
        assert 9.24 == round(shape2.verts[5][1], 2), f"Vert location wrong: 9.24 != {shape2.verts[5][0]}"
        assert 8.91 == round(shape2.verts[5][2], 2), f"Vert location wrong: 8.91 != {shape2.verts[5][0]}"
        assert -3.21 == round(shape2.verts[33][0], 2), f"Vert location wrong: -3.21 != {shape2.verts[33][0]}"
        assert -1.75 == round(shape2.verts[33][1], 2), f"Vert location wrong: -1.75 != {shape2.verts[33][0]}"
        assert 12.94 == round(shape2.verts[33][2], 2), f"Vert location wrong: 12.94 != {shape2.verts[33][0]}"

        # Original has a tri <12, 13, 14>. Find it in the original and then in the exported object

        found = -1
        target = set([12, 13, 14])
        for p in obj.data.polygons:
            ps = set([obj.data.loops[lp].vertex_index for lp in p.loop_indices])
            if ps == target:
                print(f"Found triangle in source mesh at {p.index}")
                found = p.index
                break
        assert found >= 0, "Triangle not in source mesh"

        found = -1
        for i, t in enumerate(shape2.tris):
            if set(t) == target:
                print(f"Found triangle in target mesh at {i}")
                found = i
                break
        assert found >= 0, "Triangle not in output mesh"

    if TEST_ROGUE02:
        test_title("TEST_ROGUE02", "Shape keys export normals correctly")

        #obj = append_from_file("Plane", False, r"tests\Skyrim\ROGUE02-normals.blend", r"\Object", "Plane")
        #assert obj.name == "Plane", "Got the right object"
        #bpy.ops.object.select_all(action='DESELECT')
        #bpy.context.view_layer.objects.active = obj
        #bpy.ops.object.mode_set(mode="OBJECT")
        #outnif = NifFile()
        #outtrip = TripFile()
        #outnif.initialize("SKYRIM", os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE02_warp.nif"))
        #export_shape(outnif, outtrip, obj, "_warp") 
        #outnif.save()
        export_from_blend(NifExporter,
                          r"tests\Skyrim\ROGUE02-normals.blend",
                          "Plane",
                          "SKYRIM",
                          r"tests/Out/TEST_ROGUE02.nif",
                          "_warp")

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROGUE02_warp.nif"))
        shape2 = nif2.shapes[0]
        assert len(shape2.verts) == 25, f"Export shouldn't create extra vertices, found {len(shape2.verts)}"
        v = [round(x, 1) for x in shape2.verts[18]]
        assert v == [0.0, 0.0, 0.2], f"Vertex found at incorrect position: {v}"
        n = [round(x, 1) for x in shape2.normals[8]]
        assert n == [0, 1, 0], f"Normal should point along y axis, instead: {n}"


    if TEST_NORMAL_SEAM:
        test_title("TEST_NORMAL_SEAM", "Normals on a split seam are seamless")

        export_from_blend(NifExporter, 
                          r"tests\FO4\TestKnitCap.blend",
                          "MLongshoremansCap:0",
                          "FO4",
                          r"tests/Out/TEST_NORMAL_SEAM.nif",
                          "_Dog")

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_NORMAL_SEAM_Dog.nif"))
        shape2 = nif2.shapes[0]
        target_vert = [i for i, v in enumerate(shape2.verts) if VNearEqual(v, (0.0, 8.0, 9.3))]

        assert len(target_vert) == 2, "Expect vert to have been split"
        assert VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


    if TEST_COLORS:
        test_title("TEST_COLORS", "Can read & write vertex colors")
        bpy.ops.object.select_all(action='DESELECT')
        export_from_blend(NifExporter, 
                          r"tests\FO4\VertexColors.blend",
                          "Plane",
                          "FO4",
                          r"tests/Out/TEST_COLORS_Plane.nif",
                          "_Test")

        nif3 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLORS_Plane.nif"))
        assert len(nif3.shapes[0].colors) > 0, f"Expected color layers, have: {len(nif3.shapes[0].colors)}"
        cd = nif3.shapes[0].colors
        assert cd[0] == (0.0, 1.0, 0.0, 1.0), f"First vertex found: {cd[0]}"
        assert cd[1] == (1.0, 1.0, 0.0, 1.0), f"Second vertex found: {cd[1]}"
        assert cd[2] == (1.0, 0.0, 0.0, 1.0), f"Second vertex found: {cd[2]}"
        assert cd[3] == (0.0, 0.0, 1.0, 1.0), f"Second vertex found: {cd[3]}"

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/HeadGear1.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        colordata = obj.data.vertex_colors.active.data
        targetv = find_vertex(obj.data, (1.62, 7.08, 0.37))
        assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
        for lp in obj.data.loops:
            if lp.vertex_index == targetv:
                assert colordata[lp.index].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[lp.index].color[:]}"

        testfileout = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLORSB_HeadGear1.nif")
        e = NifExporter(testfileout, "FO4")
        e.export([obj])
        #export_file_set(testfileout, "FO4", [''], [obj], obj.parent)

        nif2 = NifFile(testfileout)
        assert nif2.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not reread correctly: {nif2.shapes[0].colors[0]}"
        assert nif2.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0), f"Color 561 not reread correctly: {nif2.shapes[0].colors[561]}"

    if TEST_HEADPART:
        test_title("TEST_HEADPART", "Can read & write an SE head part")

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/SKYRIMSE/malehead.nif")
        NifImporter.do_import(testfile)
        obj = bpy.context.object

        testtri = os.path.join(pynifly_dev_path, r"tests/SKYRIMSE/malehead.tri")
        import_tri(testtri, obj)

        assert len(obj.data.shape_keys.key_blocks) == 45, f"Expected key blocks 45 != {len(obj.data.shape_keys.key_blocks)}"
        assert obj.data.shape_keys.key_blocks[0].name == "Basis", f"Expected first key 'Basis' != {obj.data.shape_keys.key_blocks[0].name}"

        testfileout = os.path.join(pynifly_dev_path, r"tests/out/TEST_HEADPART_malehead.nif")
        e = NifExporter(testfileout, 'SKYRIMSE')
        e.export([obj])
        #export_file_set(testfileout, 'SKYRIMSE', [''], [obj], obj.parent)

        nif2 = NifFile(testfileout)
        assert len(nif2.shapes) == 1, f"Expected single shape, 1 != {len(nif2.shapes)}"
        assert nif2.shapes[0].blockname == "BSDynamicTriShape", f"Expected 'BSDynamicTriShape' != '{nif2.shapes[0].blockname}'"


    if TEST_FACEBONES:
        test_title("TEST_FACEBONES", "Facebones are renamed from Blender to the game's names")

        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/basemalehead_facebones.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        assert 'skin_bone_Dimple.R' in obj.vertex_groups.keys(), f"Expected munged vertex groups"
        assert 'skin_bone_Dimple.R' in obj.parent.data.bones.keys(), f"Expected munged bone names"
        assert 'skin_bone_R_Dimple' not in obj.vertex_groups.keys(), f"Expected munged vertex groups"
        assert 'skin_bone_R_Dimple' not in obj.parent.data.bones.keys(), f"Expected munged bone names"

        outfile = os.path.join(pynifly_dev_path, r"tests/Out/basemalehead.nif")
        remove_file(outfile)
        e = NifExporter(outfile, 'FO4')
        e.export([obj])
        #export_file_set(outfile, 'FO4', [''], [obj], obj.parent, '_faceBones')

        outfile2 = os.path.join(pynifly_dev_path, r"tests/Out/basemalehead_facebones.nif")
        nif2 = NifFile(outfile2)
        assert 'skin_bone_R_Dimple' in nif2.shapes[0].bone_names, f"Expected game bone names, got {nif2.shapes[0].bone_names[0:10]}"
    
        
    if TEST_FACEBONE_EXPORT:
        test_title("TEST_FACEBONE_EXPORT", "Test can export facebones + regular nif; shapes with hidden verts export correctly")

        clear_all()

        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.tri"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri"))

        # Have a head shape parented to the normal skeleton but with facebone weights as well
        obj = append_from_file("HorseFemaleHead", False, r"tests\FO4\HeadFaceBones.blend", r"\Object", "HorseFemaleHead")
        bpy.ops.object.select_all(action='SELECT')

        # Normal and Facebones skeleton selected for export
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.nif"),
                               "FO4")
        exporter.from_context(bpy.context)
        exporter.execute()

        # Exporter generates normal and facebones nif file
        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.nif"))
        assert len(nif1.shapes) == 1, "Write the file successfully"
        assert len(nif1.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_faceBones.nif"))
        assert len(nif2.shapes) == 1
        assert len(nif2.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

        # No facebones in the normal file
        # (Not sure if facebones nif needs the normal bones--they are there in vanilla)
        assert len([x for x in nif1.nodes.keys() if "skin_bone" in x]) == 0, f"Expected no skin_bone nodes in regular nif file; found {nif1.nodes.keys()}"
        #assert len([x for x in nif1.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif2.nodes.keys()}"

        # Exporter generates a single tri file named after the normal file
        tri1 = TriFile.from_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT.tri"))
        assert len(tri1.morphs) > 0
        tri2 = TriFile.from_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT_chargen.tri"))
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
        exporter2 = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT2.nif"),
                               "FO4")
        exporter2.from_context(bpy.context)
        exporter2.execute()

        nif3 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT2.nif"))
        assert len(nif3.shapes) == 1, "Write the file successfully"
        assert len(nif3.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif1.shapes[0].tris)}"
        nif4 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FACEBONE_EXPORT2_faceBones.nif"))
        assert len(nif4.shapes) == 1
        assert len(nif4.shapes[0].tris) == 8922, f"Expected 8922 tris, found {len(nif2.shapes[0].tris)}"

        skinbones = [x for x in nif3.nodes.keys() if "skin_bone" in x]
        assert len(skinbones) == 0, f"Expected no skin_bone nodes in regular nif file; found {skinbones}"
        #assert len([x for x in nif4.nodes.keys() if x == "Neck"]) == 0, f"Expected no regular nodes in facebones nif file; found {nif4.nodes.keys()}"


    if TEST_JIARAN:
        test_title("TEST_JIARAN", "Armature with no stashed transforms exports correctly")

        clear_all()
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"))

        append_from_file("hair.001", True, r"tests\SKYRIMSE\jiaran.blend", r"\Object", "hair.001")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"), 
                               'SKYRIMSE')
        exporter.export([bpy.data.objects["hair.001"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"))
        assert len(nif1.shapes) == 1, f"Expected Jiaran nif"

    if TEST_SHADER_LE:
        test_title("TEST_SHADER_LE", "Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileLE = os.path.join(pynifly_dev_path, r"tests\Skyrim\meshes\actors\character\character assets\malehead.nif")
        leimport = NifImporter(fileLE)
        leimport.execute()
        nifLE = leimport.nif
        shaderAttrsLE = nifLE.shapes[0].shader_attributes
        for obj in bpy.context.selected_objects:
            if "MaleHeadIMF" in obj.name:
                headLE = obj
        assert len(headLE.active_material.node_tree.nodes) == 9, "ERROR: Didn't import images"
        g = round(headLE.active_material.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value, 4)
        assert round(g, 4) == 33/GLOSS_SCALE, f"Glossiness not correct, value is {g}"
        assert headLE.active_material['BSShaderTextureSet_2'] == r"textures\actors\character\male\MaleHead_sk.dds", f"Expected stashed texture path, found {headLE.active_material['BSShaderTextureSet_2']}"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_LE.nif"), 
                               'SKYRIM')
        exporter.export([headLE])

        nifcheckLE = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_LE.nif"))
        
        assert nifcheckLE.shapes[0].textures[0] == nifLE.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[0]}' != '{nifLE.shapes[0].textures[0]}'"
        assert nifcheckLE.shapes[0].textures[1] == nifLE.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[1]}' != '{nifLE.shapes[0].textures[1]}'"
        assert nifcheckLE.shapes[0].textures[2] == nifLE.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[2]}' != '{nifLE.shapes[0].textures[2]}'"
        assert nifcheckLE.shapes[0].textures[7] == nifLE.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckLE.shapes[0].textures[7]}' != '{nifLE.shapes[0].textures[7]}'"
        assert nifcheckLE.shapes[0].shader_attributes == shaderAttrsLE, f"Error: Shader attributes not preserved:\n{nifcheckLE.shapes[0].shader_attributes}\nvs\n{shaderAttrsLE}"

    if TEST_SHADER_FO4:
        test_title("TEST_SHADER_FO4", "Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileFO4 = os.path.join(pynifly_dev_path, r"tests\FO4\Meshes\Actors\Character\CharacterAssets\basemalehead.nif")
        importFO4 = NifImporter(fileFO4)
        importFO4.execute()
        nifFO4 = importFO4.nif
        shaderAttrsFO4 = nifFO4.shapes[0].shader_attributes
        for obj in bpy.context.selected_objects:
            if "BaseMaleHead:0" in obj.name:
                headFO4 = obj
        sh = next((x for x in headFO4.active_material.node_tree.nodes if x.name == "Principled BSDF"), None)
        assert sh, "ERROR: Didn't import images"
        txt = get_image_node(sh.inputs["Base Color"])
        assert txt and txt.image, "ERROR: Didn't import images"

        print("## Shader attributes are written on export")

        exp = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_FO4.nif"), 'FO4')
        exp.export([headFO4])

        nifcheckFO4 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_FO4.nif"))
        
        assert nifcheckFO4.shapes[0].textures[0] == nifFO4.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[0]}' != '{nifFO4.shapes[0].textures[0]}'"
        assert nifcheckFO4.shapes[0].textures[1] == nifFO4.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[1]}' != '{nifFO4.shapes[0].textures[1]}'"
        assert nifcheckFO4.shapes[0].textures[2] == nifFO4.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[2]}' != '{nifFO4.shapes[0].textures[2]}'"
        assert nifcheckFO4.shapes[0].textures[7] == nifFO4.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckFO4.shapes[0].textures[7]}' != '{nifFO4.shapes[0].textures[7]}'"
        assert nifcheckFO4.shapes[0].shader_attributes == shaderAttrsFO4, f"Error: Shader attributes not preserved:\n{nifcheckFO4.shapes[0].shader_attributes}\nvs\n{shaderAttrsFO4}"
        assert nifcheckFO4.shapes[0].shader_name == nifFO4.shapes[0].shader_name, f"Error: Shader name not preserved: '{nifcheckFO4.shapes[0].shader_name}' != '{nifFO4.shapes[0].shader_name}'"


    if TEST_SHADER_SE:
        test_title("TEST_SHADER_SE", "Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileSE = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\meshes\furniture\noble\noblecrate01.nif")
        seimporter = NifImporter(fileSE)
        seimporter.execute()
        nifSE = seimporter.nif
        shaderAttrsSE = nifSE.shapes[0].shader_attributes
        for obj in bpy.context.selected_objects:
            if "NobleCrate01:1" in obj.name:
                crate = obj
        assert len(crate.active_material.node_tree.nodes) == 5, "ERROR: Didn't import images"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_SE.nif"), 
                               'SKYRIMSE')
        exporter.export([crate])

        nifcheckSE = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_SE.nif"))
        
        assert nifcheckSE.shapes[0].textures[0] == nifSE.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[0]}' != '{nifSE.shapes[0].textures[0]}'"
        assert nifcheckSE.shapes[0].textures[1] == nifSE.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[1]}' != '{nifSE.shapes[0].textures[1]}'"
        assert nifcheckSE.shapes[0].textures[2] == nifSE.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[2]}' != '{nifSE.shapes[0].textures[2]}'"
        assert nifcheckSE.shapes[0].textures[7] == nifSE.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[7]}' != '{nifSE.shapes[0].textures[7]}'"
        assert nifcheckSE.shapes[0].shader_attributes == shaderAttrsSE, f"Error: Shader attributes not preserved:\n{nifcheckSE.shapes[0].shader_attributes}\nvs\n{shaderAttrsSE}"

    if TEST_SHADER_ALPHA:
        test_title("TEST_SHADER_ALPHA", "Shader attributes are read and turned into Blender shader nodes")
        # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the suffix.

        clear_all()

        fileAlph = os.path.join(pynifly_dev_path, r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
        alphimporter = NifImporter(fileAlph)
        alphimporter.execute()
        nifAlph = alphimporter.nif
        furshape = nifAlph.shapes[1]
        for obj in bpy.context.selected_objects:
            if "tail_fur.001" in obj.name:
                tail = obj
        assert len(tail.active_material.node_tree.nodes) == 9, "ERROR: Didn't import images"
        assert tail.active_material.blend_method == 'CLIP', f"Error: Alpha blend is '{tail.active_material.blend_method}', not 'CLIP'"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_ALPH.nif"), 'SKYRIM')
        exporter.export([tail])

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_ALPH.nif"))
        checkfurshape = None
        for s in nifCheck.shapes:
            if s.name == "tail_fur.001":
                checkfurshape = s
                break
        
        assert checkfurshape.textures[0] == furshape.textures[0], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[0]}' != '{furshape.textures[0]}'"
        assert checkfurshape.textures[1] == furshape.textures[1], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[1]}' != '{furshape.textures[1]}'"
        assert checkfurshape.textures[2] == furshape.textures[2], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[2]}' != '{furshape.textures[2]}'"
        assert checkfurshape.textures[7] == furshape.textures[7], \
            f"Error: Texture paths not preserved: '{checkfurshape.textures[7]}' != '{furshape.textures[7]}'"
        assert checkfurshape.shader_attributes == furshape.shader_attributes, f"Error: Shader attributes not preserved:\n{checkfurshape.shader_attributes}\nvs\n{furshape.shader_attributes}"

        assert checkfurshape.has_alpha_property, f"Error: Did not write alpha property"
        assert checkfurshape.alpha_property.flags == furshape.alpha_property.flags, f"Error: Alpha flags incorrect: {checkfurshape.alpha_property.flags} != {furshape.alpha_property.flags}"
        assert checkfurshape.alpha_property.threshold == furshape.alpha_property.threshold, f"Error: Alpha flags incorrect: {checkfurshape.alpha_property.threshold} != {furshape.alpha_property.threshold}"


    if TEST_SHEATH:
        test_title("TEST_SHEATH", "Extra data nodes are imported and exported")
        
        clear_all()

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True, confirm=False)
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/sheath_p1_1.nif")
        NifImporter.do_import(testfile)

        bgnames = set([obj['BSBehaviorGraphExtraData_Name'] for obj in bpy.data.objects if obj.name.startswith("BSBehaviorGraphExtraData")])
        assert bgnames == set(["BGED"]), f"Error: Expected BG extra data properties, found {bgnames}"
        snames = set([obj['NiStringExtraData_Name'] for obj in bpy.data.objects if obj.name.startswith("NiStringExtraData")])
        assert snames == set(["HDT Havok Path", "HDT Skinned Mesh Physics Object"]), f"Error: Expected string extra data properties, found {snames}"

        # Write and check
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHEATH.nif"), 'SKYRIM')
        exporter.export(bpy.data.objects)

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHEATH.nif"))
        sheathShape = nifCheck.shapes[0]
        names = [x[0] for x in nifCheck.behavior_graph_data]
        assert "BGED" in names, f"Error: Expected BGED in {names}"
        strings = [x[0] for x in nifCheck.string_data]
        assert "HDT Havok Path" in strings, f"Error expected havoc path in {strings}"
        assert "HDT Skinned Mesh Physics Object" in strings, f"Error: Expected physics object in {strings}"


    if TEST_FEET:
        test_title("TEST_FEET", "Extra data nodes are imported and exported")

        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/caninemalefeet_1.nif")
        NifImporter.do_import(testfile)

        feet = bpy.data.objects['FootLowRes']
        assert len(feet.children) == 1, "Feet have children"
        assert feet.children[0]['NiStringExtraData_Name'] == "SDTA", "Feet have extra data child"
        assert feet.children[0]['NiStringExtraData_Value'].startswith('[{"name"'), f"Feet have string data"

        # Write and check that it's correct
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FEET.nif"), 'SKYRIMSE')
        exporter.export([feet])

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_FEET.nif"))
        feetShape = nifCheck.shapes[0]
        assert feetShape.string_data[0][0] == 'SDTA', "String data name written correctly"
        assert feetShape.string_data[0][1].startswith('[{"name"'), "String data value written correctly"

    if TEST_SKYRIM_XFORM:
        test_title("TEST_SKYRIM_XFORM", "Can read & write the Skyrim shape transforms")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/MaleHead.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        assert int(obj.location[2]) == 120, f"Shape offset not applied to head, found {obj.location[2]}"

        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SKYRIM_XFORM.nif"), "SKYRIM")
        e.export([obj])
        
        nifcheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SKYRIM_XFORM.nif"))
        headcheck = nifcheck.shapes[0]
        assert int(headcheck.transform.translation[2]) == 120, f"Shape offset not written correctly, found {headcheck.transform.translation[2]}"
        assert int(headcheck.global_to_skin.translation[2]) == -120, f"Shape global-to-skin not written correctly, found {headcheck.global_to_skin.translation[2]}"


    if TEST_TRI2:
        test_title("TEST_TRI2", "Test that tris do as expected when the base shape is different")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/OtterMaleHead.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        trifile = os.path.join(pynifly_dev_path, r"tests/Skyrim/OtterMaleHeadChargen.tri")
        import_tri(trifile, obj)

        v1 = obj.data.shape_keys.key_blocks['VampireMorph'].data[1]
        assert v1.co[0] <= 30, "Shape keys not relative to current mesh"


    if TEST_ROTSTATIC:
        test_title("TEST_ROTSTATIC", "Test that statics are transformed according to the shape transform")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/rotatedbody.nif")
        NifImporter.do_import(testfile)

        body = bpy.data.objects["LykaiosBody"]
        head = bpy.data.objects["FemaleHead"]
        assert body.rotation_euler[0] != (0.0, 0.0, 0.0), f"Expected rotation, got {body.rotation_euler}"

        NifExporter.do_export(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROTSTATIC.nif"), 
                              "SKYRIM",
                              [body, head])
        
        nifcheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_ROTSTATIC.nif"))
        assert "LykaiosBody" in nifcheck.shape_dict.keys(), f"Expected LykaiosBody shape, found {[s.name for s in nifcheck.shapes]}"
        bodycheck = nifcheck.shape_dict["LykaiosBody"]

        assert int(bodycheck.transform.rotation.euler_deg()[0]) == 90.0, f"Expected 90deg rotation, got {bodycheck.transform.rotation.euler_deg()}"


    if TEST_ROTSTATIC2:
        test_title("TEST_ROTSTATIC2", "Test that statics are transformed according to the shape transform")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/Crane03_simplified.nif")
        NifImporter.do_import(testfile)

        glass = bpy.data.objects["Glass:0"]
        assert int(glass.location[0]) == -107, f"Locaation is incorret, got {glass.location[:]}"
        assert round(glass.matrix_world[0][1], 4) == -0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[0][1], 4)} != -0.9971"
        assert round(glass.matrix_world[2][2], 4) == 0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[2][2], 4)} != 59.2036"


    if TEST_VERTEX_ALPHA:
        test_title("TEST_VERTEX_ALPHA", "Export shape with vertex alpha values")

        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_VERTEX_ALPHA.nif")
        remove_file(outfile)
        append_from_file("Cube", True, r"tests\Skyrim\AlphaCube.blend", r"\Object", "Cube")
        exporter = NifExporter(outfile, "SKYRIM")
        exporter.export([bpy.data.objects["Cube"]])

        nifcheck = NifFile(outfile)
        shapecheck = nifcheck.shapes[0]

        assert shapecheck.colors[0][3] == 0.0, f"Expected 0, found {shapecheck.colors[0]}"
        for c in shapecheck.colors:
            assert c[0] == 1.0 and c[1] == 1.0 and c[2] == 1.0, f"Expected all white verts in nif, found {c}"

        NifImporter.do_import(outfile)
        objcheck = bpy.context.object
        colorscheck = objcheck.data.vertex_colors
        assert ALPHA_MAP_NAME in colorscheck.keys(), f"Expected alpha map, found {objcheck.data.vertex_colors.keys()}"

        assert min([c.color[1] for c in colorscheck[ALPHA_MAP_NAME].data]) == 0, f"Expected some 0 alpha values"
        for i, c in enumerate(objcheck.data.vertex_colors['Col'].data):
            assert c.color[:] == (1.0, 1.0, 1.0, 1.0), f"Expected all white, full alpha in read object, found {i}: {c.color[:]}"
