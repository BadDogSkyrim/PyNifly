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

        testfile = test_file(r"tests\SkyrimSE\maleheadargonian.nif")
        outfile = test_file(r"tests/Out/TEST_IMP_ARG.nif")
        skelfile = test_file(r"C:\Modding\SkyrimSE\mods\00 Vanilla Assets\meshes\actors\character\character assets\skeletonbeast.nif")

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

        testfile = test_file(r"tests/FO4/facegen_simple.nif")
        skelfile = test_file(r"tests/FO4/skeleton.nif")
        outfile = test_file(r"tests/Out/TEST_IMP_FACEGEN.nif")

        bpy.ops.import_scene.pynifly(filepath=skelfile)
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

        testfile = test_file(r"tests\SkyrimSE\3BBB_femalehands_1.nif")
        bpy.ops.import_scene.pynifly(filepath=testfile, pynFlags.RENAME_BONES | pynFlags.APPLY_SKINNING)
        hands = find_object("Hands", bpy.context.selected_objects, fn=lambda x: x.name)
        assert VNearEqual(hands.data.vertices[413].co, Vector((-26.8438, 2.3812, 78.3215))), f"Hands not warped"


    if TEST_BPY_ALL or TEST_EXPORT:
        test_title("TEST_EXPORT", "Can export the basic cube")
        clear_all()

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        log.debug("TODO: support objects with flat shading or autosmooth properly")
        for f in cube.data.polygons: f.use_smooth = True

        filepath = test_file(r"tests\Out\TEST_EXPORT_SKY.nif")
        remove_file(filepath)
        exporter = bpy.ops.export_scene.pynifly(filepath=filepath, 'SKYRIM')
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

        filepath = test_file(r"tests\Out\TEST_EXPORT_FO4.nif")
        remove_file(filepath)
        exporter = bpy.ops.export_scene.pynifly(filepath=filepath, 'FO4')
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
        


        # Should do some checking here









        
