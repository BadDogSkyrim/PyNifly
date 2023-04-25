"""Python Tests for running in Blender

    This file is for older, standard regression tests.
"""

from mathutils import Matrix, Vector, Quaternion
from test_tools import *
from pynifly import *
from trihandler import *

NO_PARTITION_GROUP = "*NO_PARTITIONS*"
MULTIPLE_PARTITION_GROUP = "*MULTIPLE_PARTITIONS*"
UNWEIGHTED_VERTEX_GROUP = "*UNWEIGHTED_VERTICES*"
ALPHA_MAP_NAME = "VERTEX_ALPHA"
GLOSS_SCALE = 100

# Todo: Move these to some common header file
class pynFlags(IntFlag):
    CREATE_BONES = 1
    RENAME_BONES = 1 << 1
    ROTATE_MODEL = 1 << 2
    PRESERVE_HIERARCHY = 1 << 3
    WRITE_BODYTRI = 1 << 4
    IMPORT_SHAPES = 1 << 5
    SHARE_ARMATURE = 1 << 6
    APPLY_SKINNING = 1 << 7
    KEEP_TMP_SKEL = 1 << 8 # for debugging
    RENAME_BONES_NIFTOOLS = 1 << 9
    EXPORT_POSE = 1 << 10

def MatrixLocRotScale(loc, rot, scale):
    """Dup from main file"""
    try:
        return Matrix.LocRotScale(loc, rot, scale)
    except:
        tm = Matrix.Translation(loc)
        rm = Matrix()
        if issubclass(rot.__class__, Quaternion):
            rm = rot.to_matrix()
        else:
            rm = Matrix(rot)
        rm = rm.to_4x4()
        sm = Matrix(((scale[0],0,0,0),
                        (0,scale[1],0,0),
                        (0,0,scale[2],0),
                        (0,0,0,1)))
        m = tm @ rm @ sm
        return m


def run_tests(dev_path, NifExporter, NifImporter, import_tri, create_bone, get_bone_global_xf, transform_to_matrix):
    TEST_BPY_ALL = True
    TEST_0_WEIGHTS = True
    TEST_3BBB = True
    TEST_3BBB = True
    TEST_ARMATURE_EXTEND = True
    TEST_BABY = True
    TEST_BAD_TRI = True
    TEST_BONE_HIERARCHY = True
    TEST_BONE_MANIPULATIONS = True
    TEST_BONE_XF = True
    TEST_BONE_XPORT_POS = True
    TEST_BOW = True
    TEST_BOW2 = True
    TEST_BOW3 = True
    TEST_BP_SEGMENTS = True
    TEST_BPY_PARENT = True
    TEST_CHANGE_COLLISION = False # leave false; test not working
    TEST_COLLISION_CAPSULE = True
    TEST_COLLISION_CONVEXVERT = True
    TEST_COLLISION_HIER = True
    TEST_COLLISION_LIST = True
    TEST_COLLISION_MULTI = True
    TEST_COLLISION_XFORM = True
    TEST_COLORS = True
    TEST_CONNECT_POINT= True
    TEST_CONNECTED_SKEL = True
    TEST_COTH_DATA = True
    TEST_CUSTOM_BONES = True
    TEST_DRAUGR_IMPORT = True
    TEST_EXP_SEG_ORDER = True
    TEST_EXP_SEGMENTS_BAD = True
    TEST_EXP_SK_RENAMED = True
    TEST_EXPORT = True
    TEST_EXPORT_HANDS = True
    TEST_EXPORT_WEIGHTS = True
    TEST_FACEBONE_EXPORT = True
    TEST_FACEBONES = True
    TEST_FEET = True
    TEST_FO4_CHAIR = True
    TEST_FURN_MARKER1 = True
    TEST_FURN_MARKER2 = True
    TEST_HEADPART = True
    TEST_HYENA_PARTITIONS = True
    TEST_IMP_EXP_FO4 = True
    TEST_IMP_EXP_FO4_2 = True
    TEST_IMP_EXP_SKY = True
    TEST_IMP_EXP_SKY_2 = True
    TEST_IMP_NORMALS = True
    TEST_IMPORT_ARMATURE = True
    TEST_IMPORT_AS_SHAPES = True
    TEST_IMPORT_MULT_CP = True
    TEST_IMPORT_MULT_SHAPES = True
    TEST_JIARAN = True
    TEST_MULT_PART = True
    TEST_MULTI_IMP = True
    TEST_MUTANT = True
    TEST_NIFTOOLS_NAMES = True
    TEST_NONUNIFORM_SCALE = True
    TEST_NORM = True
    TEST_NORMAL_SEAM = True
    TEST_NOT_FB = True
    TEST_PARTITION_ERRORS = True
    TEST_PARTITIONS = True
    TEST_PIPBOY = False
    TEST_POT = True
    TEST_POT = True
    TEST_RENAME = True
    TEST_ROGUE01 = True
    TEST_ROGUE02 = True
    TEST_ROTSTATIC = True
    TEST_ROTSTATIC2 = True
    TEST_ROUND_TRIP = True
    TEST_SCALING = True
    TEST_SCALING_BP = False
    TEST_SCALING_COLL = False
    TEST_SCALING_OBJ = False
    TEST_SEGMENTS = True
    TEST_SHADER_3_3 = True
    TEST_SHADER_ALPHA = True
    TEST_SHADER_FO4 = True
    TEST_SHADER_LE = True
    TEST_SHADER_SE = True
    TEST_SHADER_SE= True
    TEST_SHAPE_OFFSET = True
    TEST_SHEATH = True
    TEST_SK_MULT = True
    TEST_SKEL = True
    TEST_SKYRIM_XFORM = True
    TEST_SPLIT_NORMAL = True
    TEST_TIGER_EXPORT = True
    TEST_TIGER_EXPORT = True
    TEST_TRI = True
    TEST_TRI2 = True
    TEST_TRIP = True
    TEST_TRIP_SE = True
    TEST_UNIFORM_SCALE = True
    TEST_UV_SPLIT = True
    TEST_VERTEX_ALPHA = True
    TEST_WEAPON_PART= True
    TEST_WEIGHTS_EXPORT = True
    TEST_WELWA = True
    TEST_NEW_COLORS = True
    TEST_IMP_ANIMATRON = False
    TEST_HANDS = False


    if False: 
        """Not a real test--just exposes a bunch of transforms for understanding"""
        test_title("TEST_SHOW_TRANSFORMS", "Some transforms from the argonian head")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\maleheadargonian.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_IMP_ARG.nif")
        skelfile = os.path.join(pynifly_dev_path, r"C:\Modding\SkyrimSE\mods\00 Vanilla Assets\meshes\actors\character\character assets\skeletonbeast.nif")

        skel = NifFile(skelfile)
        skel_head_xf = skel.nodes['NPC Head [Head]'].xform_to_global
        skel_head_mx = MatrixLocRotScale(skel_head_xf.translation, skel_head_xf.rotation, Vector((1,1,1)))
        print(f"Skeleton Head position is \n{skel_head_mx}")
        skel_spine2_xf = skel.nodes['NPC Spine2 [Spn2]'].xform_to_global
        skel_spine2_mx = MatrixLocRotScale(skel_spine2_xf.translation, skel_spine2_xf.rotation, Vector((1,1,1)))
        print(f"Skeleton NPC Spine2 [Spn2] position is \n{skel_spine2_mx}")
        skel_diff = skel_spine2_mx.inverted() @ skel_head_mx 
        print(f"Skeleton offset Head-Spine2 =\n{skel_diff}")
        # These next two are both saying the same thing
        print(f"Skeleton offset Head-Spine2 inverted =\n{skel_diff.inverted()}")
        print(f"Skeleton offset Spine2-Head =\n{skel_head_mx.inverted() @ skel_spine2_mx}")

        nif = NifFile(testfile)
        sh = nif.shapes[0]
        assert sh.name == '_ArgonianMaleHead', f"Have the correct shape: {sh.name}"

        print("Bone nodes in the argonian nif are at the vanilla skeleton positions")
        spine2_xf = nif.nodes['NPC Spine2 [Spn2]'].xform_to_global
        spine2_mx = MatrixLocRotScale(spine2_xf.translation, spine2_xf.rotation, Vector((1,1,1)))
        print(f"xform-to-global for 'NPC Spine2 [Spn2]' is \n{spine2_mx}")

        head_xf = nif.nodes['NPC Head [Head]'].xform_to_global
        head_mx = MatrixLocRotScale(head_xf.translation, head_xf.rotation, Vector((1,1,1)))
        print(f"xform-to-global for 'NPC Head [Head]' is \n{head_mx}")

        print("Skin to bone for spine2 is exactly the inverse offset of spine2 from origin (head bone)--except for rotations")
        sh_sp2 = sh.get_shape_skin_to_bone('NPC Spine2 [Spn2]')
        sh_sp2_mx = MatrixLocRotScale(sh_sp2.translation, sh_sp2.rotation, Vector((1,1,1)))
        sp2_bind = sh_sp2_mx.inverted()
        print(f"skin-to-bone for Spine2 is \n{sh_sp2_mx}")
        print("But inverting the spine2 skin-to-bone is NOT exactly the head-spine2 offset, presumably because of those rotations")
        print(f"Inverse skin-to-bone for Spine2 (bind position) is \n{sp2_bind}")

        print("Head is just about at origin")
        sh_head = sh.get_shape_skin_to_bone('NPC Head [Head]')
        sh_head_mx = MatrixLocRotScale(sh_head.translation, sh_head.rotation, Vector((1,1,1)))
        print(f"skin-to-bone for Head is \n{sh_head_mx}")

        print("Combining bone node location with skin-to-bone transform gives pose location")
        sh_sp2_van = spine2_mx @ sh_sp2_mx.inverted() 
        print(f"Spine2 computed transform is \n{sh_sp2_van}")
        sh_head_van = head_mx @ sh_head_mx.inverted() 
        print(f"Head computed transform is \n{sh_head_van}")

        print("Invert the bind position and we get the skin-to-bone transform for output")
        print(f"Inverse bind position\n{sp2_bind.inverted()}")


        assert False, "----------STOP-----------"

        
    if False: #TEST_BPY_ALL or TEST_IMP_FACEGEN:
        # This test fails -- can't get the head positioned where it belongs, but the head wants to come in
        # with a 90deg rotation.
        # May be because the facegen file refers to bone "Head" not "HEAD".
        test_title("TEST_IMP_FACEGEN", "Can read a facegen nif")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/facegen_simple.nif")
        skelfile = os.path.join(pynifly_dev_path, r"tests/FO4/skeleton.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_IMP_FACEGEN.nif")

        NifImporter.do_import(skelfile)
        skel = find_shape('skeleton.nif')
        ObjectSelect([skel])
        ObjectActive(skel)
        imp = NifImporter(testfile, f = pynFlags.CREATE_BONES \
                      | pynFlags.RENAME_BONES \
                      | pynFlags.IMPORT_SHAPES \
                      | pynFlags.APPLY_SKINNING \
                      | pynFlags.KEEP_TMP_SKEL)
        imp.execute()




    if TEST_BPY_ALL or TEST_HANDS:
        test_title("TEST_HANDS", "Import of hands works correctly")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\3BBB_femalehands_1.nif")
        NifImporter.do_import(testfile, pynFlags.RENAME_BONES | pynFlags.APPLY_SKINNING)
        hands = find_object("Hands", bpy.context.selected_objects, fn=lambda x: x.name)
        assert VNearEqual(hands.data.vertices[413].co, Vector((-26.8438, 2.3812, 78.3215))), f"Hands not warped"


    if TEST_BPY_ALL or TEST_BABY:
        test_title('TEST_BABY', 'Can export baby parts')
        clear_all()

        # Can intuit structure if it's not in the file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\baby.nif")
        NifImporter.do_import(testfile, flags = pynFlags.APPLY_SKINNING)
        head = bpy.data.objects['Baby_Head:0']
        eyes = bpy.data.objects['Baby_Eyes:0']

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_BABY.nif")
        e = NifExporter(outfile, 'FO4', export_flags=pynFlags.PRESERVE_HIERARCHY)
        # This nif imports with different skeletons because the head has a different skin-to-bone transform from 
        # the other shapes. We aren't yet smart enough to export multiple skeletons to one nif.
        e.export([eyes, head])

        testnif = NifFile(outfile)
        testhead = testnif.shape_by_root('Baby_Head')
        testeyes = testnif.shape_by_root('Baby_Eyes')
        assert len(testhead.bone_names) > 10, "Error: Head should have bone weights"
        assert len(testeyes.bone_names) > 2, "Error: Eyes should have bone weights"
        assert testhead.blockname == "BSSubIndexTriShape", f"Error: Expected BSSubIndexTriShape on skinned shape, got {testhead.blockname}"

    if True: #TEST_BPY_ALL or TEST_FACEBONES:
        test_title("TEST_FACEBONES", "Facebones are renamed from Blender to the game's names")
        clear_all()

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
    
        

    if TEST_BPY_ALL or TEST_EXPORT:
        test_title("TEST_EXPORT", "Can export the basic cube")
        clear_all()

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        log.debug("TODO: support objects with flat shading or autosmooth properly")
        for f in cube.data.polygons: f.use_smooth = True

        filepath = os.path.join(pynifly_dev_path, r"tests\Out\TEST_EXPORT_SKY.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'SKYRIM')
        exporter.export([cube])

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        nifcheck = NifFile(filepath)
        shapecheck = nifcheck.shapes[0]
        assert len(shapecheck.tris) == 12, f"Have correct tris: {len(shapecheck.tris)}"
        assert len(shapecheck.verts) == 14, f"Have correct verts: {len(shapecheck.verts)}"
        assert len(shapecheck.normals) == 14, f"Have correct normals: {len(shapecheck.normals)}"
        assert len(shapecheck.uvs) == 14, f"Have correct uvs: {len(shapecheck.uvs)}"

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

        filepath = os.path.join(pynifly_dev_path, r"tests\Out\TEST_EXPORT_FO4.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'FO4')
        exporter.export([cube])

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        importer = NifImporter(filepath)
        importer.execute()

        sourceGame = importer.nif.game
        assert sourceGame == "FO4", "ERROR: Wrong game found"
        assert importer.nif.shapes[0].blockname == "BSTriShape", f"Error: Expected BSTriShape on unskinned shape, got {f.shapes[0].blockname}"

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, f"ERROR: Cube should have 14 verts, has {len(new_cube.data.vertices)}"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, f"ERROR: Cube should have 36 UV locations, has {len(new_cube.data.uv_layers[0].data)}"
        assert len(new_cube.data.polygons) == 12, f"ERROR: Cube should have 12 polygons, has {len(new_cube.data.polygons)}"
        # bpy.data.objects.remove(cube, do_unlink=True)


    if False: # TEST_BPY_ALL or TEST_BONE_MANIPULATIONS:
        # Test to show we can store an arbitrary rotation in a bone head+tail+roll and 
        # recover it afterwards. 
        # This test only runs when in the main file, too much trouble to make it work here

        print('## TEST_BONE_MANIPULATIONS Show our bone manipulations work')
        #bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        clear_all()

        skeldata = bpy.data.armatures.new("SKELDATA")
        skel = bpy.data.objects.new("SKEL", skeldata)
        bpy.context.scene.collection.objects.link(skel)
        skel.select_set(True)
        bpy.context.view_layer.objects.active = skel
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        def test_bone(game, boneloc, boneq):
            log.debug(f"TESTING {game} / {boneloc} / {boneq.axis}, {boneq.angle}")
            bonexf = MatrixLocRotScale(boneloc, boneq, (1,1,1))

            bhead, btail, broll = transform_to_bone(game, bonexf)
            #log.debug(f"transform_to_bone({game}, {boneq}) -> {bhead}, {btail}, {broll}")
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            if "TEST" not in skeldata.edit_bones:
                b = skeldata.edit_bones.new("TEST")
            b = skeldata.edit_bones["TEST"]
            b.head = bhead
            b.tail = btail
            b.roll = broll
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
            b = skeldata.bones["TEST"]
            assert NearEqual((b.head_local-b.tail_local).length, 5), f"Bone length is 5: {(b.head_local-b.tail_local).length}"

            xfout = get_bone_global_xf(b, game, False)
            trOut, qOut, scOut = xfout.decompose()

            qax, qang = qOut.rotation_difference(boneq).to_axis_angle()
            log.debug(f"Quaternion difference is ({qax}, {qang})")
            assert NearEqual(qOut.angle, boneq.angle, 0.01), f"{game} Angle is correct: {qOut.angle} == {boneq.angle}"
            assert VNearEqual(qOut.axis, boneq.axis), f"{game} with angle {boneq.angle}, axis is correct: {qOut.axis} == {boneq.axis}"

        test_bone("SKYRIM", Vector((1,1,1)), Quaternion(Vector((1, 0, 0)), radians(90)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((1,0,0)), radians(90)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((1,0,0)), radians(45)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((0,1,0)), radians(90)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((0,1,0)), radians(45)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((0,0,1)), radians(90)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((0,0,1)), radians(45)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((1,1,0)), radians(90)))
        test_bone("FO4", Vector((0,0,0)), Quaternion(Vector((1,1,0)), radians(45)))
        test_bone("SKYRIM", Vector((13.4525, -4.2124, 22.574)), 
                  Quaternion(Vector((0.1719, 0.95, 0.2605)), radians( 174.42)))
        test_bone("FO4", 
                    Vector([-2.6813, -11.7044, 59.6862]), 
                    Quaternion((0.496972, 0.487948, 0.4868, -0.5271859)))

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        

    if TEST_BPY_ALL or TEST_FURN_MARKER1:
        test_title("TEST_FURN_MARKER1", "Furniture markers work")

        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\farmbench01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_FURN_MARKER1.nif")
        NifImporter.do_import(testfile, 0)

        fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
        
        assert len(fmarkers) == 2, f"Found furniture markers: {fmarkers}"

        # -------- Export --------
        bench = find_shape("FarmBench01:5")
        bsxf = find_shape("BSXFlags")
        fmrklist = [f for f in bpy.data.objects if f.name.startswith("BSFurnitureMarker")]

        exporter = NifExporter(outfile, 'SKYRIMSE')
        explist = [bench, bsxf]
        explist.extend(fmrklist)
        log.debug(f"Exporting: {explist}")
        exporter.export(explist)

        # --------- Check ----------
        nifcheck = NifFile(outfile)
        fmcheck = nifcheck.furniture_markers

        assert len(fmcheck) == 2, f"Wrote the furniture marker correctly: {len(fmcheck)}"


    if TEST_BPY_ALL or TEST_FURN_MARKER2:
        test_title("TEST_FURN_MARKER2", "Furniture markers work")

        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\commonchair01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_FURN_MARKER2.nif")
        NifImporter.do_import(testfile, 0)

        fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
        
        assert len(fmarkers) == 1, f"Found furniture markers: {fmarkers}"
        assert VNearEqual(fmarkers[0].rotation_euler, (-pi/2, 0, 0)), f"Marker points the right direction"

        # -------- Export --------
        chair = find_shape("CommonChair01:0")
        bsxf = find_shape("BSXFlags")
        fmrk = find_shape("BSFurnitureMarkerNode")
        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([chair, bsxf, fmrk])

        # --------- Check ----------
        nifcheck = NifFile(outfile)
        fmcheck = nifcheck.furniture_markers

        assert len(fmcheck) == 1, f"Wrote the furniture marker correctly: {len(fmcheck)}"
        assert fmcheck[0].entry_points == 13, f"Entry point data is correct: {fmcheck[0].entry_points}"


    if (TEST_BPY_ALL or TEST_COLLISION_XFORM) and bpy.app.version[0] >= 3:
        # V2.x does not import the whole parent chain when appending an object 
        # from another file
        test_title("TEST_COLLISION_XFORM", "Can read and write shape with collision capsule shapes")
        clear_all()

        # ------- Load --------
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLLISION_XFORM.nif")

        append_from_file("Staff", True, r"tests\SkyrimSE\staff.blend", r"\Object", "Staff")
        append_from_file("BSInvMarker", True, r"tests\SkyrimSE\staff.blend", r"\Object", "BSInvMarker")
        append_from_file("BSXFlags", True, r"tests\SkyrimSE\staff.blend", r"\Object", "BSXFlags")
        append_from_file("NiStringExtraData", True, r"tests\SkyrimSE\staff.blend", r"\Object", "NiStringExtraData")
        append_from_file("bhkConvexVerticesShape.002", True, r"tests\SkyrimSE\staff.blend", r"\Object", "bhkConvexVerticesShape.002")

        staff = find_shape("Staff")
        coll = find_shape("bhkCollisionObject")
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

        # -------- Export --------
        remove_file(outfile)
        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([staff, coll, bsxf, invm, strd])

        # ------- Check ---------
        # NOTE the collision is just on one of the tines
        nifcheck = NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        listcheck = rbcheck.shape
        cvShapes = [c for c in listcheck.children if c.blockname == "bhkConvexVerticesShape"]
        maxz = max([v[2] for v in cvShapes[0].vertices])
        assert maxz < 0, f"All verts on collisions shape on negative z axis: {maxz}"

        
    if TEST_BPY_ALL or TEST_BOW2:
        test_title("TEST_BOW2", "Can modify collision shape location")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
        NifImporter.do_import(testfile)
        obj = find_shape('ElvenBowSkinned')
        coll = find_shape('bhkCollisionObject')
        collbody = coll.children[0]
        collshape = collbody.children[0]
        bged = find_shape("BSBehaviorGraphExtraData")
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

       # ------- Export --------
        # Move the edge of the collision box so it covers the bow better
        for v in collshape.data.vertices:
            if v.co.x > 0:
                v.co.x = 16.5

        # Move the collision object 
        coll.location = coll.location + Vector([5, 10, 0])
        collshape.location = collshape.location + Vector([-5, -10, 0])

        outfile2 = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BOW2.nif")
        remove_file(outfile2)
        exporter = NifExporter(outfile2, 'SKYRIMSE')
        exporter.export([obj, coll, bged, strd, bsxf, invm])

        # ------- Check Results 2 --------

        nifcheck2 = NifFile(outfile2)

        midbowcheck2 = nifcheck2.nodes["Bow_MidBone"]
        collcheck2 = midbowcheck2.collision_object
        assert collcheck2.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck2.blockname}"
        assert bhkCOFlags(collcheck2.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

        # Full check of locations and rotations to make sure we got them right
        mbc_xf = nifcheck2.get_node_xform_to_global("Bow_MidBone")
        assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
        m = mbc_xf.as_matrix().to_euler()
        assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

        bodycheck2 = collcheck2.body
        p = bodycheck2.properties
        assert VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
        assert VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


    if TEST_BPY_ALL or TEST_BOW3:
        test_title("TEST_BOW3", "Can modify collision shape type")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
        NifImporter.do_import(testfile)
        obj = find_shape('ElvenBowSkinned')
        coll = find_shape('bhkCollisionObject')
        collbody = coll.children[0]
        collshape = collbody.children[0]
        bged = find_shape("BSBehaviorGraphExtraData")
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

       # ------- Export --------

        # Move the collision object 
        for v in collshape.data.vertices:
            if NearEqual(v.co.x, 11.01, epsilon=0.5):
                v.co.x = 16.875
                if v.co.y > 0:
                    v.co.y = 26.72
                else:
                    v.co.y = -26.72
        collshape.name = "bhkConvexVerticesShape"
        collbody.name = "bhkRigidBody"

        outfile3 = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BOW3.nif")
        remove_file(outfile3)
        exporter = NifExporter(outfile3, 'SKYRIMSE')
        exporter.export([obj, coll, bged, strd, bsxf, invm])

        # ------- Check Results 3 --------

        nifcheck3 = NifFile(outfile3)

        midbowcheck3 = nifcheck3.nodes["Bow_MidBone"]
        collcheck3 = midbowcheck3.collision_object
        assert collcheck3.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck3.blockname}"
        assert bhkCOFlags(collcheck3.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

        # Full check of locations and rotations to make sure we got them right
        mbc_xf = nifcheck3.get_node_xform_to_global("Bow_MidBone")
        assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
        m = mbc_xf.as_matrix().to_euler()
        assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

        bodycheck3 = collcheck3.body

        cshapecheck3 = bodycheck3.shape
        assert cshapecheck3.blockname == "bhkConvexVerticesShape", f"Shape is convex vertices: {cshapecheck3.blockname}"
        assert VNearEqual(cshapecheck3.vertices[0], (-0.73, -0.267, 0.014, 0.0)), f"Convex shape is correct"


    if TEST_BPY_ALL or TEST_COLLISION_HIER:
        test_title("TEST_COLLISION_HIER", "Can read and write hierarchy of nodes containing shapes")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\grilledleekstest.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLLISION_HIER.nif")
        remove_file(outfile)

        NifImporter.do_import(testfile)

        leek4 = find_shape("Leek04")
        leek0 = find_shape("Leek04:0")
        leek1 = find_shape("Leek04:1")
        c1 = find_shape("bhkCollisionObject")
        rb = find_shape("bhkRigidBody")
        cshape = find_shape("bhkConvexVerticesShape")
        assert c1.parent.name == "Leek04" in bpy.data.objects, f"Target is a valid object: {c1.parent.name}"
        assert leek0.parent.name == "Leek04" in bpy.data.objects, f"Target is a valid object: {leek0.parent.name}"
        assert leek1.parent.name == "Leek04" in bpy.data.objects, f"Target is a valid object: {leek1.parent.name}"
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

        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")
        exporter = NifExporter(outfile, 'SKYRIM')
        exporter.export([leek4, bsxf, invm])

        # ------- Check Results --------

        nifOrig = NifFile(testfile)
        l4NodeOrig = nifOrig.nodes["Leek04"]
        collOrig = l4NodeOrig.collision_object
        rbOrig = collOrig.body
        shOrig = rbOrig.shape

        nifcheck = NifFile(outfile)
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
        assert VNearEqual(shCheck.vertices[0], shOrig.vertices[0]), f"Collision vertices match 0: {shCheck.vertices[0][:]} == {shOrig.vertices[0][:]}"
        assert VNearEqual(shCheck.vertices[5], shOrig.vertices[5]), f"Collision vertices match 0: {shCheck.vertices[5][:]} == {shOrig.vertices[5][:]}"


    if TEST_BPY_ALL and TEST_ROTSTATIC:
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

        m = Matrix(bodycheck.transform.rotation)
        assert int(m.to_euler()[0]*180/pi) == 90, f"Expected 90deg rotation, got {m.to_euler()}"


    if TEST_BPY_ALL or TEST_EXP_SEGMENTS_BAD:
        test_title("TEST_EXP_SEGMENTS_BAD", "Verts export in the correct segments")
        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_EXP_SEGMENTS_BAD.nif")
        remove_file(outfile)

        append_from_file("ArmorUnder", True, r"tests\FO4\ArmorExportsBadSegments.blend", r"\Object", "ArmorUnder")

        NifFile.clear_log()
        exporter = NifExporter(outfile, 'FO4')
        exporter.export([bpy.data.objects["ArmorUnder"]])
        assert "ERROR" not in NifFile.message_log(), f"Error: Expected no error message, got: \n{NifFile.message_log()}---\n"

        nif1 = NifFile(outfile)
        assert len(nif1.shapes) == 1, f"Single shape was exported"

        body = nif1.shapes[0]
        assert len(body.partitions) >= 4, "All important segments exported"
        assert len(body.partitions[3].subsegments) == 0, "4th partition (body) has no subsegments"
        assert len([x for x in body.partition_tris if x == 3]) == len(body.tris), f"All tris in the 4th partition--found {len([x for x in body.partition_tris if x == 3])}"
        assert len([x for x in body.partition_tris if x != 3]) == 0, f"Regression: No tris in the last partition (or any other)--found {len([x for x in body.partition_tris if x != 3])}"


    if (TEST_BPY_ALL or TEST_EXP_SEG_ORDER) and bpy.app.version[0] >= 3:
        test_title("TEST_EXP_SEG_ORDER", "Segments export in numerical order")
        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_EXP_SEG_ORDER.nif")
        remove_file(outfile)

        append_from_file("SynthGen1Body", True, r"tests\FO4\SynthGen1BodyTest.blend", r"\Object", "SynthGen1Body")

        obj = bpy.data.objects["SynthGen1Body"]
        groups = [g for g in obj.vertex_groups if g.name.startswith('FO4')]
        assert len(groups) == 23, f"Groups properly appended from test file: {len(groups)}"

        NifFile.clear_log()
        exporter = NifExporter(outfile, 'FO4')
        exporter.export([bpy.data.objects["SynthGen1Body"]])
        assert "ERROR" not in NifFile.message_log(), f"Error: Expected no error message, got: \n{NifFile.message_log()}---\n"

        nif1 = NifFile(outfile)
        assert len(nif1.shapes) == 1, f"Single shape was exported"

        # Third segment should be arm, with 5 subsegments
        body = nif1.shapes[0]
        assert len(body.partitions[2].subsegments) == 5, f"Right arm has 5 subsegments, found {len(body.partitions[2].subsegments)}"
        assert body.partitions[2].subsegments[0].material == 0xb2e2764f, "First subsegment is the upper right arm material"
        assert len(body.partitions[3].subsegments) == 0, "Torso has no subsegments"


    if TEST_BPY_ALL or TEST_PARTITIONS:
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
        head = nif2.shapes[0]
        assert len(nif2.shapes[0].partitions) == 3, "Have all skyrim partitions"
        assert set([p.id for p in head.partitions]) == set([130, 143, 230]), "Have all head parts"


    if TEST_BPY_ALL or TEST_SEGMENTS:
        test_title("TEST_SEGMENTS", "Can read FO4 segments")
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/VanillaMaleBody.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        assert "FO4 Seg 003" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names: 'FO4 Seg 003'"
        assert "FO4 Seg 004 | 000 | Up Arm.L" in obj.vertex_groups, "FO4 body segments read in as vertex groups with sensible names: 'FO4 Seg 004 | 000 | Up Arm.L'"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == obj['FO4_SEGMENT_FILE'], "Should have FO4 segment file read and saved for later use"

        print("### Can write FO4 segments")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"), "FO4")
        e.export([obj])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"),
        #                "FO4", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/segmentsVanillaMaleBody.nif"))
        assert len(nif2.shapes[0].partitions) == 7, "Wrote the shape's 7 partitions"
        assert r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf" == nif2.shapes[0].segment_file, f"Nif should reference segment file, found '{nif2.shapes[0].segment_file}'"


    if TEST_BPY_ALL or TEST_SHADER_LE:
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
        shadernodes = headLE.active_material.node_tree.nodes
        assert len(shadernodes) == 9, "ERROR: Didn't import images"
        g = shadernodes['Principled BSDF'].inputs['Metallic'].default_value
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


    if TEST_ALL or TEST_BP_SEGMENTS:
        test_title("TEST_BP_SEGMENTS", "Can read FO4 bodypart segments")
        clear_all()

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/Helmet.nif")
        NifImporter.do_import(testfile)

        #for o in bpy.context.selected_objects:
        #    if o.name.startswith("Helmet:0"):
        #        obj = o
        helmet = next(filter(lambda x: x.name.startswith('Helmet:0'), bpy.context.selected_objects))
        visor = next(filter(lambda x: x.name.startswith('glass:0'), bpy.context.selected_objects))
        helmet = bpy.data.objects['Helmet:0']
        assert helmet.name == "Helmet:0", "Read the helmet object"
        assert "FO4 Seg 001 | Hair Top | Head" in helmet.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"
        assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == helmet['FO4_SEGMENT_FILE'], "FO4 segment file read and saved for later use"

        assert visor.name == "glass:0", "Read the visor object"
        assert "FO4 Seg 001 | Hair Top" in visor.vertex_groups, "FO4 body segments read in as vertex groups with sensible names"

        print("### Can write FO4 segments")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"), "FO4")
        e.export([helmet, visor])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"),
        #                "FO4", [''], [obj], obj.parent)
        
        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_BP_SEGMENTShelmet.nif"))
        helm2 = nif2.shapes[0]
        assert helm2.name == "Helmet:0", "Have the helmet in the nif file"
        assert len(helm2.partitions) == 2, "Have all FO4 partitions"
        ss30 = None
        for p in helm2.partitions:
            for s in p.subsegments:
                if s.user_slot == 30:
                    ss30 = s
                    break
        assert ss30 is not None, "Mesh has FO4Subsegment 30"
        assert ss30.material == 0x86b72980, "FO4Subsegment 30 should have correct material"
        assert "Meshes\\Armor\\FlightHelmet\\Helmet.ssf" == nif2.shapes[0].segment_file, "Nif references segment file"

        visor2 = nif2.shapes[1]
        assert visor2.name == "glass:0", "Have the visor in the nif file"
        assert len(helm2.partitions) == 2, "Visor has all FO4 partitions"
        assert visor2.partitions[1].subsegments[0].user_slot == 30, "Visor has subsegment 30"


    if (TEST_BPY_ALL or TEST_EXP_SK_RENAMED) and bpy.app.version[0] >= 3:
        # Doesn't work on 2.x. Not sure why.
        test_title("TEST_EXP_SK_RENAMED", "Ensure renamed shape keys export properly")
        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_EXP_SK_RENAMED.nif")
        trifile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_EXP_SK_RENAMED.tri")
        remove_file(outfile)
        remove_file(trifile)

        append_from_file("CheetahChildHead", True, r"tests\FO4\Feline Child Test.blend", r"\Object", "CheetahChildHead")

        NifFile.clear_log()
        exporter = NifExporter(outfile, 'FO4')
        exporter.export([bpy.data.objects["CheetahChildHead"]])
        assert "ERROR" not in NifFile.message_log(), f"Error: Expected no error message, got: \n{NifFile.message_log()}---\n"

        nif1 = NifFile(outfile)
        assert len(nif1.shapes) == 1, f"Expected head nif"

        tri1 = TriFile.from_file(trifile)
        assert len(tri1.morphs) == 47, f"Expected 47 morphs, got {len(tri1.morphs)} morphs: {tri1.morphs.keys()}"

        bpy.ops.object.select_all(action='DESELECT')
        NifImporter.do_import(outfile)
        obj = bpy.context.object

        import_tri(trifile, obj)

        assert len(obj.data.shape_keys.key_blocks) == 47, f"Expected key blocks 47 != {len(obj.data.shape_keys.key_blocks)}"
        assert 'Smile.L' in obj.data.shape_keys.key_blocks, f"Expected key 'Smile.L' in {obj.data.shape_keys.key_blocks.keys()}"


    if TEST_BPY_ALL or TEST_COTH_DATA:
        test_title("TEST_COTH_DATA", "Can read and write cloth data")
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


    if TEST_BPY_ALL or TEST_BAD_TRI:
        test_title("TEST_BAD_TRI", "Tris with messed up UVs can be imported")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/bad_tri.tri")
        obj = import_tri(testfile, None)
        assert len(obj.data.vertices) == 6711, f"Expected 6711 vertices, found {len(obj.data.vertices)}"

        testfile2 = os.path.join(pynifly_dev_path, r"tests/Skyrim/bad_tri_2.tri")
        obj2 = import_tri(testfile2, None)
        assert len(obj2.data.vertices) == 11254, f"Expected 11254 vertices, found {len(obj2.data.vertices)}"


    if TEST_BPY_ALL or TEST_TIGER_EXPORT:
        test_title("TEST_TIGER_EXPORT", "Tiger head exports without errors")

        clear_all()
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT_faceBones.nif"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.tri"))
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT_chargen.tri"))

        append_from_file("TigerMaleHead", True, r"tests\FO4\Tiger.blend", r"\Object", "TigerMaleHead")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"), 
                               'FO4', chargen="_chargen")
        exporter.export([bpy.data.objects["TigerMaleHead"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"))
        assert len(nif1.shapes) == 1, f"Expected tiger nif"


    if TEST_BPY_ALL or TEST_3BBB:
        print("## TEST_3BBB: Test that this mesh imports with the right transforms")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/3BBB_femalebody_1.nif")
        NifImporter.do_import(testfile)
        
        obj = bpy.context.object
        assert NearEqual(obj.location[0], 0.0), f"Expected body to be centered on x-axis, got {obj.location}"

        print("## Test that the same armature is used for the next import")
        arma = bpy.data.objects['Scene Root']
        bpy.ops.object.select_all(action='DESELECT')
        arma.select_set(True)
        bpy.context.view_layer.objects.active = arma
        testfile2 = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/3BBB_femalehands_1.nif")
        NifImporter.do_import(testfile2)

        arma2 = bpy.context.object.parent
        assert arma2.name == arma.name, f"Should have parented to same armature: {arma2.name} != {arma.name}"

    if TEST_BPY_ALL or TEST_MUTANT:
        test_title("TEST_MUTANT", "Test that the supermutant body imports correctly the *second* time")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/testsupermutantbody.nif")
        imp = NifImporter.do_import(testfile, pynFlags.RENAME_BONES | pynFlags.APPLY_SKINNING)
        assert round(imp.nif.shapes[0].global_to_skin.translation[2]) == -140, f"Expected -140 z translation in first nif, got {imp.nif.shapes[0].global_to_skin.translation[2]}"

        sm1 = bpy.context.object
        assert round(sm1.location[2]) == 140, f"Expect first supermutant body at 140 Z, got {sm1.location[2]}"

        imp2 = NifImporter.do_import(testfile, pynFlags.RENAME_BONES | pynFlags.APPLY_SKINNING)
        sm2 = bpy.context.object
        assert round(sm2.location[2]) == 140, f"Expect supermutant body at 140 Z, got {sm2.location[2]}"

        
    if TEST_BPY_ALL or TEST_RENAME:
        test_title("TEST_RENAME", "Test that renaming bones works correctly")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\femalebody_1.nif")
        imp = NifImporter.do_import(testfile, pynFlags.CREATE_BONES | pynFlags.APPLY_SKINNING)

        body = bpy.context.object
        vgnames = [x.name for x in body.vertex_groups]
        vgxl = list(filter(lambda x: ".L" in x or ".R" in x, vgnames))
        assert len(vgxl) == 0, f"Expected no vertex groups renamed, got {vgxl}"

        armnames = [b.name for b in body.parent.data.bones]
        armxl = list(filter(lambda x: ".L" in x or ".R" in x, armnames))
        assert len(armxl) == 0, f"Expected no bones renamed in armature, got {armxl}"


    if TEST_BPY_ALL or TEST_EXPORT_HANDS:
        test_title("TEST_EXPORT_HANDS", "Test that hand mesh doesn't throw an error")

        outfile1 = os.path.join(pynifly_dev_path, r"tests/Out/TEST_EXPORT_HANDS.nif")
        remove_file(outfile1)

        append_from_file("SupermutantHands", True, r"tests\FO4\SupermutantHands.blend", r"\Object", "SupermutantHands")
        bpy.ops.object.select_all(action='SELECT')

        exp = NifExporter(outfile1, 'FO4')
        exp.export(bpy.context.selected_objects)

        assert os.path.exists(outfile1)


    if (TEST_BPY_ALL or TEST_PARTITION_ERRORS) and bpy.app.version[0] >= 3:
        # Doesn't run on 2.x, don't know why
        test_title("TEST_PARTITION_ERRORS", "Partitions with errors raise errors")

        clear_all()

        append_from_file("SynthMaleBody", True, r"tests\FO4\SynthBody02.blend", r"\Object", "SynthMaleBody")

        # Partitions must divide up the mesh cleanly--exactly 1 partition per tri
        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_TIGER_EXPORT.nif"), 
                               'FO4')
        exporter.export([bpy.data.objects["SynthMaleBody"]])
        assert len(exporter.warnings) > 0, f"Error: Export should have generated warnings: {exporter.warnings}"
        print(f"Exporter warnings: {exporter.warnings}")
        assert MULTIPLE_PARTITION_GROUP in bpy.data.objects["SynthMaleBody"].vertex_groups, "Error: Expected group to be created for tris in multiple partitions"


    if TEST_BPY_ALL or TEST_POT:
        test_title("TEST_POT", "Test that pot shaders doesn't throw an error")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\spitpotopen01.nif")
        imp = NifImporter.do_import(testfile, pynFlags.APPLY_SKINNING)
        assert 'ANCHOR:0' in bpy.data.objects.keys()


    if TEST_BPY_ALL or TEST_EXPORT_WEIGHTS:
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

    if TEST_BPY_ALL or TEST_ROUND_TRIP:
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
        NifImporter.do_import(outfile1)

        armor2 = None
        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor2 = obj

        assert int(armor2.location.z) == 120, f"ERROR: Exported armor is re-imported with same position: {armor2.location}"
        maxz = max([v.co.z for v in armor2.data.vertices])
        minz = min([v.co.z for v in armor2.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices from exported armor are positioned below origin"

    if TEST_BPY_ALL or TEST_UV_SPLIT:
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


    if TEST_BPY_ALL or TEST_BPY_PARENT:
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

    if TEST_BPY_ALL or TEST_SKEL:
        test_title("TEST_SKEL", "Can import skeleton file with no shapes")
        clear_all()

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"skeletons\FO4\skeleton.nif")

        NifImporter.do_import(testfile)

        arma = bpy.data.objects["skeleton.nif"]
        assert 'Leg_Thigh.L' in arma.data.bones, "Error: Should have left thigh"


    if TEST_BPY_ALL or TEST_0_WEIGHTS:
        test_title("TEST_0_WEIGHTS", "Gives warning on export with 0 weights")
        clear_all()

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


    if TEST_BPY_ALL or TEST_SPLIT_NORMAL:
        test_title("TEST_SPLIT_NORMAL", "Can handle meshes with split normals")
        clear_all()

        plane = append_from_file("Plane", False, r"tests\skyrim\testSplitNormalPlane.blend", r"\Object", "Plane")
        e = NifExporter(os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), "FO4")
        e.export([plane])
        #export_file_set(os.path.join(pynifly_dev_path, r"tests\Out\CustomNormals.nif"), 
        #                "FO4", [''], [plane], plane.parent)


    if TEST_BPY_ALL or TEST_ROGUE01:
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

    if TEST_BPY_ALL or TEST_ROGUE02:
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


    if TEST_BPY_ALL or TEST_NORMAL_SEAM:
        test_title("TEST_NORMAL_SEAM", "Normals on a split seam are seamless")

        export_from_blend(NifExporter, 
                          r"tests\FO4\TestKnitCap.blend",
                          "MLongshoremansCap:0",
                          "FO4",
                          r"tests/Out/TEST_NORMAL_SEAM.nif",
                          "_Dog")

        nif2 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_NORMAL_SEAM_Dog.nif"))
        shape2 = nif2.shapes[0]
        target_vert = [i for i, v in enumerate(shape2.verts) if VNearEqual(v, (0.00037, 7.9961, 9.34375))]

        assert len(target_vert) == 2, f"Expect vert to have been split: {target_vert}"
        assert VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


    if TEST_BPY_ALL or TEST_COLORS:
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

    if TEST_BPY_ALL or TEST_HEADPART:
        test_title("TEST_HEADPART", "Can read & write an SE head part")
        clear_all()

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


    if TEST_BPY_ALL or TEST_JIARAN:
        test_title("TEST_JIARAN", "Armature with no stashed transforms exports correctly")

        clear_all()
        remove_file(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"))

        append_from_file("hair.001", True, r"tests\SKYRIMSE\jiaran.blend", r"\Object", "hair.001")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"), 
                               'SKYRIMSE')
        exporter.export([bpy.data.objects["hair.001"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_JIARAN.nif"))
        assert len(nif1.shapes) == 1, f"Expected Jiaran nif"

    if TEST_BPY_ALL or TEST_SHADER_FO4:
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


    if TEST_BPY_ALL or TEST_SHADER_ALPHA:
        test_title("TEST_SHADER_ALPHA", "Shader attributes are read and turned into Blender shader nodes")
        # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the suffix.

        clear_all()

        fileAlph = os.path.join(pynifly_dev_path, r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
        alphimporter = NifImporter(fileAlph)
        alphimporter.execute()
        nifAlph = alphimporter.nif
        furshape = nifAlph.shapes[1]
        tail = bpy.data.objects["tail_fur"]
        assert len(tail.active_material.node_tree.nodes) == 9, "ERROR: Didn't import images"
        assert tail.active_material.blend_method == 'CLIP', f"Error: Alpha blend is '{tail.active_material.blend_method}', not 'CLIP'"

        print("## Shader attributes are written on export")

        exporter = NifExporter(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_ALPH.nif"), 'SKYRIM')
        exporter.export([tail])

        nifCheck = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_ALPH.nif"))
        checkfurshape = None
        for s in nifCheck.shapes:
            if s.name == "tail_fur":
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


    if TEST_BPY_ALL or TEST_FEET:
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

    if TEST_BPY_ALL or TEST_SKYRIM_XFORM:
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


    if TEST_BPY_ALL or TEST_TRI2:
        test_title("TEST_TRI2", "Test that tris do as expected when the base shape is different")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/OtterMaleHead.nif")
        NifImporter.do_import(testfile)

        obj = bpy.context.object
        trifile = os.path.join(pynifly_dev_path, r"tests/Skyrim/OtterMaleHeadChargen.tri")
        import_tri(trifile, obj)

        v1 = obj.data.shape_keys.key_blocks['VampireMorph'].data[1]
        assert v1.co[0] <= 30, "Shape keys not relative to current mesh"


    if TEST_BPY_ALL or TEST_ROTSTATIC2:
        test_title("TEST_ROTSTATIC2", "Test that statics are transformed according to the shape transform")
        
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/Meshes/SetDressing/Vehicles/Crane03_simplified.nif")
        NifImporter.do_import(testfile)

        glass = bpy.data.objects["Glass:0"]
        assert int(glass.location[0]) == -107, f"Locaation is incorret, got {glass.location[:]}"
        assert round(glass.matrix_world[0][1], 4) == -0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[0][1], 4)} != -0.9971"
        assert round(glass.matrix_world[2][2], 4) == 0.9971, f"Rotation is incorrect, got {round(glass.matrix_world[2][2], 4)} != 59.2036"


    if TEST_BPY_ALL or TEST_SCALING_OBJ:
        test_title("TEST_SCALING_OBJ", "Can scale simple objects")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\farmbench01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_SCALING_OBJ.nif")
        NifImporter.do_import(testfile, 0, scale=0.1)

        bench = find_shape("FarmBench01:5")
        bmax = max([v.co.z for v in bench.data.vertices])
        bmin = min([v.co.z for v in bench.data.vertices])
        assert VNearEqual(bench.scale, (1,1,1)), f"Bench scale factor is 1: {bench.scale}"
        assert bmax < 3.1, f"Max Z is scaled down: {bmax}"
        assert bmin >= 0, f"Min Z is correct: {bmin}"

        fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
        assert fmarkers[0].location.z < 3.4, f"Furniture marker location is correct: {fmarkers[0].location.z}"


        # -------- Export --------
        bsxf = find_shape("BSXFlags")
        explist = [bench, bsxf]
        explist.extend(fmarkers)
        log.debug(f"Exporting: {explist}")
        exporter = NifExporter(outfile, 'SKYRIMSE', scale=0.1).export(explist)

        # --------- Check ----------
        nifcheck = NifFile(outfile)
        bcheck = nifcheck.shapes[0]
        fmcheck = nifcheck.furniture_markers
        bchmax = max([v[2] for v in bcheck.verts])
        assert bchmax > 30, f"Max Z is scaled up: {bchmax}"
        assert len(fmcheck) == 2, f"Wrote the furniture marker correctly: {len(fmcheck)}"
        assert fmcheck[0].offset[2] > 30, f"Furniture marker Z scaled up: {fmcheck[0].offset[2]}"




        
