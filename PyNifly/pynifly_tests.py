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
class PyNiflyFlags(IntFlag):
    CREATE_BONES = 1
    RENAME_BONES = 1 << 1
    ROTATE_MODEL = 1 << 2
    PRESERVE_HIERARCHY = 1 << 3
    WRITE_BODYTRI = 1 << 4
    IMPORT_SHAPES = 1 << 5
    SHARE_ARMATURE = 1 << 6
    APPLY_SKINNING = 1 << 7
    KEEP_TMP_SKEL = 1 << 8 # for debugging

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
    TEST_BPY_ALL = True
    TEST_IMP_NORMALS = False
    TEST_COTH_DATA = False
    TEST_MUTANT = False
    TEST_RENAME = False
    TEST_BONE_XPORT_POS = False
    TEST_POT = False
    TEST_3BBB = False
    TEST_BAD_TRI = False
    TEST_TIGER_EXPORT = False
    TEST_EXPORT_HANDS = False
    TEST_PARTITION_ERRORS = False
    TEST_SCALING = False
    TEST_POT = False
    TEST_EXPORT = False
    TEST_IMPORT_ARMATURE = False
    TEST_EXPORT_WEIGHTS = False
    TEST_IMP_EXP_SKY = False
    TEST_IMP_EXP_FO4 = False
    TEST_ROUND_TRIP = False
    TEST_UV_SPLIT = False
    TEST_CUSTOM_BONES = False
    TEST_BPY_PARENT = False
    TEST_BABY = False
    TEST_CONNECTED_SKEL = True
    TEST_TRI = False
    TEST_0_WEIGHTS = False
    TEST_SPLIT_NORMAL = False
    TEST_SKEL = False
    TEST_PARTITIONS = False
    TEST_SEGMENTS = False
    TEST_BP_SEGMENTS = False
    TEST_ROGUE01 = False
    TEST_ROGUE02 = False
    TEST_NORMAL_SEAM = False
    TEST_COLORS = False
    TEST_HEADPART = False
    TEST_FACEBONES = False
    TEST_FACEBONE_EXPORT = False
    TEST_TIGER_EXPORT = False
    TEST_JIARAN = False
    TEST_SHADER_LE = False
    TEST_SHADER_SE = False
    TEST_SHADER_FO4 = False
    TEST_SHADER_ALPHA = True
    TEST_SHEATH = False
    TEST_FEET = False
    TEST_SKYRIM_XFORM = False
    TEST_TRI2 = False
    TEST_3BBB = False
    TEST_ROTSTATIC = False
    TEST_ROTSTATIC2 = False
    TEST_VERTEX_ALPHA = False
    TEST_EXP_SK_RENAMED = False
    TEST_EXP_SEG_ORDER = False
    TEST_EXP_SEGMENTS_BAD = False
    TEST_BOW = False
    TEST_BOW2 = False
    TEST_BOW3 = False
    TEST_COLLISION_CONVEXVERT = False
    TEST_COLLISION_HIER = False
    TEST_COLLISION_MULTI = False
    TEST_COLLISION_XFORM = False
    TEST_COLLISION_CAPSULE = False
    TEST_COLLISION_LIST = False
    TEST_WELWA = False
    TEST_TRIP = False
    TEST_TRIP_SE = False
    TEST_FURN_MARKER2 = False
    TEST_FURN_MARKER1 = False
    TEST_BONE_HIERARCHY = False
    TEST_BONE_MANIPULATIONS = False
    TEST_UNIFORM_SCALE = False
    TEST_NONUNIFORM_SCALE = False
    TEST_CHANGE_COLLISION = False
    TEST_DRAUGR_IMPORT = False
    TEST_WEIGHTS_EXPORT = False
    TEST_FO4_CHAIR = False
    TEST_MULT_PART = False
    TEST_HYENA_PARTITIONS = False
    TEST_SK_MULT = False
    TEST_NORM = False
    TEST_SHADER_3_3 = False
    TEST_SHADER_SE= False
    TEST_CONNECT_POINT= False
    TEST_WEAPON_PART= False
    TEST_IMPORT_AS_SHAPES = False
    TEST_IMPORT_MULT_CP = False
    TEST_IMPORT_MULT_SHAPES = False
    TEST_ARMATURE_EXTEND = False


    #if TEST_BPY_ALL or TEST_CHANGE_COLLISION:
    #    test_title("TEST_CHANGE_COLLISION", "Changing collision type works correctly")
    #    clear_all()

    #    # ------- Load --------
    #    testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
    #    outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_CHANGE_COLLISION.nif")

    #    NifImporter.do_import(testfile)

    #    obj = bpy.context.object
    #    coll = find_shape('bhkCollisionObject')
    #    collbody = coll.children[0]
    #    collshape = find_shape('bhkBoxShape')
    #    bged = find_shape("BSBehaviorGraphExtraData")
    #    strd = find_shape("NiStringExtraData")
    #    bsxf = find_shape("BSXFlags")
    #    invm = find_shape("BSInvMarker")
    #    assert collshape.name == 'bhkBoxShape', f"Found collision shape"
        
    #    collshape.name = "bhkConvexVerticesShape"

    #    # ------- Export --------

    #    # Move the edge of the collision box so it covers the bow better
    #    exporter = NifExporter(outfile, 'SKYRIMSE')
    #    exporter.export([obj, coll, bged, strd, bsxf, invm])

    #    # ------- Check Results --------

    #    nifcheck = NifFile(outfile)
    #    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    #    collcheck = midbowcheck.collision_object
    #    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    #    bodycheck = collcheck.body
    #    shapecheck = bodycheck.shape


    if TEST_BPY_ALL or TEST_ARMATURE_EXTEND:
        test_title("TEST_ARMATURE_EXTEND", "Can extend an armature with a second NIF")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\BaseMaleBody.nif")
        testfile2 = os.path.join(pynifly_dev_path, r"tests\FO4\BaseMaleHead.nif")

        NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING | PyNiflyFlags.RENAME_BONES)

        arma = bpy.data.objects[r"Scene Root"]
        assert "SPINE1" in arma.data.bones, "Found neck bone in skeleton"
        assert not "HEAD" in arma.data.bones, "Did not find head bone in skeleton"

        bpy.context.view_layer.objects.active = arma
        arma.select_set(True)
        NifImporter.do_import(testfile2, PyNiflyFlags.APPLY_SKINNING | PyNiflyFlags.RENAME_BONES)
        assert not "BaseMaleHead.nif" in bpy.data.objects, "Head import did not create new skeleton"
        assert "HEAD" in arma.data.bones, "Found head bone in skeleton"




    if TEST_BPY_ALL or TEST_FACEBONES:
        test_title("TEST_FACEBONES", "Can read facebones correctly")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\BaseMaleHead_faceBones.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_WELWA.nif")

        NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING | PyNiflyFlags.RENAME_BONES)

        head = find_shape("BaseMaleHead_faceBones:0")
        maxy = max([v.co.y for v in head.data.vertices])
        assert maxy < 11.8, f"Max y not too large: {maxy}"
        assert not "skin_bone_C_MasterEyebrow" in bpy.data.objects, f"Did not load empty node for skin_bone_C_MasterEyebrow"
        assert "skin_bone_C_MasterEyebrow" in head.parent.data.bones, f"Loaded bone for parented bone skin_bone_C_MasterEyebrow"


    if TEST_BPY_ALL or TEST_WELWA:
        test_title("TEST_WELWA", "Can read and write shape with unusual skeleton")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\welwa.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_WELWA.nif")

        NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING)

        welwa = find_shape("111")
        skel = welwa.parent
        lipbone = skel.data.bones['NPC UpperLip']
        assert VNearEqual(lipbone.matrix_local.translation, (0, 49.717827, 161.427307)), f"Found {lipbone.name} at {lipbone.matrix_local.translation}"
        spine1 = skel.data.bones['NPC Spine1']
        assert VNearEqual(spine1.matrix_local.translation, (0, -50.551056, 64.465019)), f"Found {spine1.name} at {spine1.matrix_local.translation}"

        exporter = NifExporter(outfile, 'SKYRIMSE', export_flags=0)
        exporter.export([welwa])

        # ------- Check ---------
        nifcheck = NifFile(outfile)

        assert "NPC Pelvis [Pelv]" not in nifcheck.nodes, f"Human pelvis name not written: {nifcheck.nodes.keys()}"


    if TEST_BPY_ALL or TEST_NORM:
        test_title("TEST_NORM", "Normals are read correctly")
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests/FO4/LBoot.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_NORM.nif")

        NifImporter.do_import(testfile)
        boot = find_shape("L_Boot")


        boot.data.calc_normals_split()

        # Get vert 527
        targetvert = boot.data.vertices[527]
        #targetvert =  next(filter(lambda v: VNearEqual(v.co, (-14.2989, 9.6691, -117.153), epsilon=0.1), boot.data.vertices))
        #targetvert = boot.data.vertices[0]
        #assert VNearEqual(targetvert.co, (-18.28125, 10.890625, -116.25)), \
        #    f"Have the right vertex: {targetvert.co}"
        assert VNearEqual(targetvert.normal, (0.7304, 0.1842, 0.6577)), \
            f"Vertex normal as expected: {targetvert.normal}"
        vertloops = [l.index for l in boot.data.loops if l.vertex_index == targetvert.index]
        custnormal = boot.data.loops[vertloops[0]].normal
        print(f"TEST_NORM custnormal: loop {vertloops[0]} has normal {custnormal}")
        assert custnormal[1] > 0, f"Custom normal points forward: {custnormal}"
        assert custnormal[2] > 0, f"Custom normal points up: {custnormal}"
        custnormal2 = boot.data.loops[vertloops[2]].normal
        assert VNearEqual(custnormal, custnormal2), f"Face normals match: {custnormal} == {custnormal2}"


    if TEST_BPY_ALL or TEST_SKIN_BONE_XF:
        test_title("TEST_SKIN_BONE_XF", "Skin-to-bone transforms work correctly")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\3BBB_femalehands_1.nif")
        NifImporter.do_import(testfile, PyNiflyFlags.RENAME_BONES | PyNiflyFlags.APPLY_SKINNING)
        hands = find_object("Hands", bpy.context.selected_objects, fn=lambda x: x.name)
        assert VNearEqual(hands.data.vertices[413].co, Vector((-26.8438, 2.3812, 78.3215))), f"Hands not warped"

        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\maleheadargonian.nif")
        NifImporter.do_import(testfile, PyNiflyFlags.RENAME_BONES | PyNiflyFlags.APPLY_SKINNING)
        head = find_object("_ArgonianMaleHead", bpy.context.selected_objects, fn=lambda x: x.name)
        minz = min([v.co.z for v in head.data.vertices])
        assert NearEqual(minz, -11.012878, epsilon=0.1), f"Min Z is negative: {minz}"
        maxz = max([v.co.z for v in head.data.vertices])
        assert NearEqual(maxz, 11.262238, epsilon=0.1), f"Min Z is negative: {minz}"
        assert NearEqual(head.location.z, 120.343582), f"Head is positioned at head position: {head.location}"


    if TEST_BPY_ALL or TEST_CONNECT_POINT:
        test_title("TEST_CONNECT_POINT", "Connect points are imported and exported")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\CombatShotgun.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_CONNECT_POINT.nif")
        NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING)
        parentnames = ['P-Barrel', 'P-Casing', 'P-Grip', 'P-Mag', 'P-Scope']
        childnames = ['C-Receiver', 'C-Reciever']

        shotgun = next(filter(lambda x: x.name.startswith('CombatShotgunReceiver:0'), bpy.context.selected_objects))
        cpparents = list(filter(lambda x: x.name.startswith('BSConnectPointParents'), bpy.context.selected_objects))
        cpchildren = list(filter(lambda x: x.name.startswith('BSConnectPointChildren'), bpy.context.selected_objects))
        cpcasing = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Casing'), bpy.context.selected_objects))
        
        assert len(cpparents) == 5, f"Found parent connect points: {cpparents}"
        p = [x.name.split("::")[1] for x in cpparents]
        p.sort()
        assert p == parentnames, f"Found correct parentnames: {p}"

        assert cpchildren, f"Found child connect points: {cpchildren}"
        assert (cpchildren[0]['PYN_CONNECT_CHILD_0'] == "C-Receiver") or \
            (cpchildren[0]['PYN_CONNECT_CHILD_1'] == "C-Receiver"), \
            f"Did not find child name"

        assert NearEqual(cpcasing.rotation_quaternion.w, 0.9098), f"Have correct rotation: {cpcasing.rotation_quaternion}"
        assert cpcasing.parent.name == "CombatShotgunReceiver", f"Casing has correct parent {cpcasing.parent.name}"

        # -------- Export --------
        exporter = NifExporter(outfile, 'FO4')
        print(f"Writing to test file: {[shotgun] + cpparents + cpchildren}")
        exporter.export([shotgun] + cpparents + cpchildren)

        ## --------- Check ----------
        nifcheck = NifFile(outfile)
        pcheck = [x.name.decode() for x in nifcheck.connect_points_parent]
        pcheck.sort()
        assert pcheck ==parentnames, f"Wrote correct parent names: {pcheck}"
        pcasing = next(filter(lambda x: x.name.decode()=="P-Casing", nifcheck.connect_points_parent))
        assert NearEqual(pcasing.rotation[0], 0.909843564), "Have correct rotation: {p.casing.rotation[0]}"

        chnames = nifcheck.connect_points_child
        chnames.sort()
        assert chnames == childnames, f"Wrote correct child names: {chnames}"


    if TEST_BPY_ALL or TEST_WEAPON_PART:
        test_title("TEST_WEAPON_PART", "Weapon parts are imported at the parent connect point")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\CombatShotgun.nif")
        partfile = os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\CombatShotgunBarrel_1.nif")
        partfile2 = os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\DrumMag.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_WEAPON_PART.nif")

        NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING)
        barrelpcp = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Barrel'), bpy.context.selected_objects))
        assert barrelpcp, f"Found the connect point for barrel parts"
        magpcp = next(filter(lambda x: x.name.startswith('BSConnectPointParents::P-Mag'), bpy.context.selected_objects))
        assert magpcp, f"Found the connect point for magazine parts"

        bpy.context.view_layer.objects.active = barrelpcp
        NifImporter.do_import(partfile, PyNiflyFlags.APPLY_SKINNING)
        barrelccp = next(filter(lambda x: x.name.startswith('BSConnectPointChildren'), bpy.context.selected_objects))
        assert barrelccp, f"Barrel's child connect point found {barrelccp}"
        assert barrelccp.parent == barrelpcp, f"Child connect point parented to parent connect point: {barrelccp.parent}"


    if TEST_BPY_ALL or TEST_IMPORT_MULT_SHAPES:
        test_title("TEST_IMPORT_MULT_SHAPES", "Can import >2 meshes as shape keys")
        clear_all()

        testfiles = [os.path.join(pynifly_dev_path, r"tests\FO4\PoliceGlasses\Glasses_Cat.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\FO4\PoliceGlasses\Glasses_CatF.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\FO4\PoliceGlasses\Glasses_Horse.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\FO4\PoliceGlasses\Glasses_Hyena.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\FO4\PoliceGlasses\Glasses_LionLyk.nif"), 
                     ]
        NifImporter.do_import(testfiles)

        meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
        assert len(meshes) == 2, f"Have 2 meshes: {meshes}"
        sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
        assert set(sknames0) == set(['Basis', '_Cat', '_CatF', '_Horse', '_Hyena', '_LionLyk']), f"Shape keys are named correctly: {sknames0}"
        sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
        assert set(sknames1) == set(['Basis', '_Cat', '_CatF', '_Horse', '_Hyena', '_LionLyk']), f"Shape keys are named correctly: {sknames1}"
        armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
        assert len(armatures) == 1, f"Have 1 armature: {armatures}"


    if TEST_BPY_ALL or TEST_IMPORT_MULT_CP:
        test_title("TEST_IMPORT_MULT_CP", "Can import multiple files and connect up the connect points")
        clear_all()

        testfiles = [os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\CombatShotgun.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\CombatShotgunBarrel.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\FO4\Shotgun\Stock.nif"), ]
        NifImporter.do_import(testfiles)

        meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
        assert len(meshes) == 5, f"Have 5 meshes: {meshes}"
        barrelparent = [obj for obj in bpy.data.objects if obj.name == 'BSConnectPointParents::P-Barrel']
        assert len(barrelparent) == 1, f"Have barrel parent connect point {barrelparent}"
        barrelchild = [obj for obj in bpy.data.objects \
                       if obj.name.startswith('BSConnectPointChildren')
                            and obj['PYN_CONNECT_CHILD_0'] == 'C-Barrel']
        assert len(barrelchild) == 1, f"Have a single barrel child {barrelchild}"
        

    if TEST_BPY_ALL or TEST_IMPORT_AS_SHAPES:
        test_title("TEST_IMPORT_AS_SHAPES", "Can import 2 meshes as shape keys")
        clear_all()

        testfiles = [os.path.join(pynifly_dev_path, r"tests\SkyrimSE\body1m_0.nif"), 
                     os.path.join(pynifly_dev_path, r"tests\SkyrimSE\body1m_1.nif"), ]
        NifImporter.do_import(testfiles)

        meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
        assert len(meshes) == 2, f"Have 2 meshes: {meshes}"
        sknames0 = [sk.name for sk in meshes[0].data.shape_keys.key_blocks]
        assert set(sknames0) == set(['Basis', '_0', '_1']), f"Shape keys are named correctly: {sknames0}"
        sknames1 = [sk.name for sk in meshes[1].data.shape_keys.key_blocks]
        assert set(sknames1) == set(['Basis', '_0', '_1']), f"Shape keys are named correctly: {sknames1}"
        armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
        assert len(armatures) == 1, f"Have 1 armature: {armatures}"


    if TEST_BPY_ALL or TEST_SHADER_SE:
        test_title("TEST_SHADER_SE", "Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        fileSE = os.path.join(pynifly_dev_path, 
                              r"tests\skyrimse\meshes\armor\dwarven\dwarvenboots_envscale.nif")
        seimporter = NifImporter(fileSE)
        seimporter.execute()
        nifSE = seimporter.nif
        shaderAttrsSE = nifSE.shapes[0].shader_attributes
        boots = next(filter(lambda x: x.name.startswith('Shoes'), bpy.context.selected_objects))
        assert len(boots.active_material.node_tree.nodes) >= 5, "ERROR: Didn't import shader nodes"
        assert shaderAttrsSE.Env_Map_Scale == 5, "Read the correct environment map scale"

        print("## Shader attributes are written on export")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_SE.nif")
        remove_file(outfile)
        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([boots])

        nifcheckSE = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_SE.nif"))
        
        assert nifcheckSE.shapes[0].textures[0] == nifSE.shapes[0].textures[0], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[0]}' != '{nifSE.shapes[0].textures[0]}'"
        assert nifcheckSE.shapes[0].textures[1] == nifSE.shapes[0].textures[1], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[1]}' != '{nifSE.shapes[0].textures[1]}'"
        assert nifcheckSE.shapes[0].textures[2] == nifSE.shapes[0].textures[2], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[2]}' != '{nifSE.shapes[0].textures[2]}'"
        assert nifcheckSE.shapes[0].textures[7] == nifSE.shapes[0].textures[7], \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[7]}' != '{nifSE.shapes[0].textures[7]}'"
        assert nifcheckSE.shapes[0].shader_attributes.Env_Map_Scale == shaderAttrsSE.Env_Map_Scale, f"Error: Shader attributes not preserved:\n{nifcheckSE.shapes[0].shader_attributes}\nvs\n{shaderAttrsSE}"


    if TEST_BPY_ALL or TEST_SHADER_3_3:
        test_title("TEST_SHADER_3_3", "Shader attributes are read and turned into Blender shader nodes")

        clear_all()

        append_from_file("FootMale_Big", True, r"tests\SkyrimSE\feet.3.3.blend", 
                         r"\Object", "FootMale_Big")
        bpy.ops.object.select_all(action='DESELECT')
        obj = find_shape("FootMale_Big")

        print("## Shader attributes are written on export")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_3_3.nif")
        remove_file(outfile)
        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([obj])

        nifcheckSE = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHADER_3_3.nif"))
        
        assert nifcheckSE.shapes[0].textures[0] == r"textures\actors\character\male\MaleBody_1.dds", \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[0]}'"
        assert nifcheckSE.shapes[0].textures[1] == r"textures\actors\character\male\MaleBody_1_msn.dds", \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[1]}'"
        assert nifcheckSE.shapes[0].textures[2] == r"textures\actors\character\male\MaleBody_1_sk.dds", \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[2]}'"
        assert nifcheckSE.shapes[0].textures[7] == r"textures\actors\character\male\MaleBody_1_S.dds", \
            f"Error: Texture paths not preserved: '{nifcheckSE.shapes[0].textures[7]}'"


    if TEST_BPY_ALL or TEST_TRIP_SE:
        test_title("TEST_TRIP_SE", "Bodypart tri extra data and file are written on export")
        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_TRIP_SE.nif")
        outfile1 = os.path.join(pynifly_dev_path, r"tests/Out/TEST_TRIP_SE_1.nif")
        outfiletrip = os.path.join(pynifly_dev_path, r"tests/Out/TEST_TRIP_SE.tri")

        append_from_file("Penis_CBBE", True, r"tests\SkyrimSE\HorseFuta.blend", 
                         r"\Object", "Penis_CBBE")
        bpy.ops.object.select_all(action='DESELECT')
        obj = find_shape("Penis_CBBE")

        remove_file(outfile)
        export = NifExporter(outfile, 'SKYRIMSE', PyNiflyFlags.RENAME_BONES | PyNiflyFlags.WRITE_BODYTRI | PyNiflyFlags.APPLY_SKINNING)
        export.export([obj])

        print(' ------- Check --------- ')
        nifcheck = NifFile(outfile1)

        bodycheck = nifcheck.shape_dict["Penis_CBBE"]
        assert bodycheck.name == "Penis_CBBE", f"Penis found in nif"

        stringdata = bodycheck.string_data
        assert stringdata, f"Found string data: {stringdata}"
        sd = stringdata[0]
        assert sd[0] == 'BODYTRI', f"Found BODYTRI string data"
        assert sd[1].endswith("TEST_TRIP_SE.tri"), f"Found correct filename"

        tripcheck = TripFile.from_file(outfiletrip)
        assert len(tripcheck.shapes) == 1, f"Found shape"
        bodymorphs = tripcheck.shapes['Penis_CBBE']
        assert len(bodymorphs) == 27, f"Found enough morphs: {len(bodymorphs)}"
        assert "CrotchBack" in bodymorphs.keys(), f"Found 'CrotchBack' in {bodymorphs.keys()}"


    if TEST_BPY_ALL or TEST_TRIP:
        test_title("TEST_TRIP", "Body tri extra data and file are written on export")
        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_TRIP.nif")
        outfiletrip = os.path.join(pynifly_dev_path, r"tests/Out/TEST_TRIP.tri")

        append_from_file("BaseMaleBody", True, r"tests\FO4\BodyTalk.blend", r"\Object", "BaseMaleBody")
        bpy.ops.object.select_all(action='DESELECT')
        body = find_shape("BaseMaleBody")

        print("Found body: " + body.name)

        remove_file(outfile)
        export = NifExporter(outfile, 'FO4', PyNiflyFlags.WRITE_BODYTRI | PyNiflyFlags.APPLY_SKINNING)
        export.export([body])

        print(' ------- Check --------- ')
        nifcheck = NifFile(outfile)

        bodycheck = nifcheck.shape_dict["BaseMaleBody"]
        assert bodycheck.name == "BaseMaleBody", f"Body found in nif"

        stringdata = nifcheck.string_data
        assert stringdata, f"Found string data: {stringdata}"
        sd = stringdata[0]
        assert sd[0] == 'BODYTRI', f"Found BODYTRI string data"
        assert sd[1].endswith("TEST_TRIP.tri"), f"Found correct filename"

        tripcheck = TripFile.from_file(outfiletrip)
        assert len(tripcheck.shapes) == 1, f"Found shape"
        bodymorphs = tripcheck.shapes['BaseMaleBody']
        assert len(bodymorphs) > 30, f"Found enough morphs: {len(len(bodymorphs))}"
        assert "BTShoulders" in bodymorphs.keys(), f"Found 'BTShoulders' in {bodymorphs.keys()}"


    if TEST_BPY_ALL or TEST_SHEATH:
        test_title("TEST_SHEATH", "Extra data nodes are imported and exported")
        clear_all()

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True, confirm=False)
        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/sheath_p1_1.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_SHEATH.nif")
        NifImporter.do_import(testfile)

        bglist = [obj for obj in bpy.data.objects if obj.name.startswith("BSBehaviorGraphExtraData")]
        slist = [obj for obj in bpy.data.objects if obj.name.startswith("NiStringExtraData")]
        bgnames = set([obj['BSBehaviorGraphExtraData_Name'] for obj in bglist])
        assert bgnames == set(["BGED"]), f"Error: Expected BG extra data properties, found {bgnames}"
        snames = set([obj['NiStringExtraData_Name'] for obj in slist])
        assert snames == set(["HDT Havok Path", "HDT Skinned Mesh Physics Object"]), \
            f"Error: Expected string extra data properties, found {snames}"

        # Write and check
        print('------- Can write extra data -------')
        exporter = NifExporter(outfile, 'SKYRIM')
        exporter.export(bpy.data.objects)


        print('------ Extra data checks out----')
        nifCheck = NifFile(outfile)
        sheathShape = nifCheck.shapes[0]

        names = [x[0] for x in nifCheck.behavior_graph_data]
        assert "BGED" in names, f"Error: Expected BGED in {names}"
        bgedCheck = nifCheck.behavior_graph_data[0]
        log.debug(f"BGED value is {bgedCheck}")
        assert bgedCheck[1] == "AuxBones\SOS\SOSMale.hkx", f"Extra data value = AuxBones/SOS/SOSMale.hkx: {bgedCheck}"
        assert bgedCheck[2], f"Extra data controls base skeleton: {bgedCheck}"

        strings = [x[0] for x in nifCheck.string_data]
        assert "HDT Havok Path" in strings, f"Error expected havoc path in {strings}"
        assert "HDT Skinned Mesh Physics Object" in strings, f"Error: Expected physics object in {strings}"


    if TEST_BPY_ALL or TEST_TRI:
        test_title("TEST_TRI", "Can load a tri file into an existing mesh")
        clear_all()

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

        NifImporter.do_import(testfile, chargen="_chargen")

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
        
    if TEST_BPY_ALL or TEST_HYENA_PARTITIONS:
        test_title("TEST_HYENA_PARTITIONS", "Partitions export successfully, with warning")

        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_HYENA_PARTITIONS.nif")
        remove_file(outfile)

        append_from_file("HyenaMaleHead", True, r"tests\FO4\HyenaHead.blend", r"\Object", "HyenaMaleHead")
        append_from_file("Skeleton", True, r"tests\FO4\HyenaHead.blend", r"\Object", "Skeleton")
        exporter = NifExporter(outfile, "FO4")
        exporter.export([bpy.data.objects["HyenaMaleHead"], bpy.data.objects["FaceBones.Skel"], bpy.data.objects["Skeleton"]])
        assert len(exporter.warnings) == 1, f"One warning reported ({exporter.warnings})"

        nif1 = NifFile(outfile)
        assert len(nif1.shapes) == 1, "Wrote the file successfully"

    if TEST_BPY_ALL or TEST_SK_MULT:
        test_title("TEST_SK_MULT", "Export multiple objects with only some shape keys")

        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_SK_MULT.nif")
        remove_file(outfile)

        append_from_file("CheMaleMane", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "CheMaleMane")
        append_from_file("MaleTail", True, r"tests\SkyrimSE\Neck ruff.blend", r"\Object", "MaleTail")
        exporter = NifExporter(outfile, "SKYRIMSE")
        exporter.export([bpy.data.objects["CheMaleMane"], bpy.data.objects["MaleTail"]])

        nif1 = NifFile(os.path.join(pynifly_dev_path, r"tests/Out/TEST_SK_MULT_1.nif"))
        assert len(nif1.shapes) == 2, "Wrote the file successfully"


    if TEST_BPY_ALL or TEST_MULT_PART:
        test_title("TEST_MULT_PART", "Export shape with face that might fall into multiple partititions")

        clear_all()

        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_MULT_PART.nif")
        remove_file(outfile)
        append_from_file("MaleHead", True, r"tests\SkyrimSE\multiple_partitions.blend", r"\Object", "MaleHead")
        exporter = NifExporter(outfile, "SKYRIMSE")
        obj = bpy.data.objects["MaleHead"]
        exporter.export([obj])

        assert "*MULTIPLE_PARTITIONS*" not in obj.vertex_groups, f"Exported without throwing *MULTIPLE_PARTITIONS* error"

    if TEST_BPY_ALL or TEST_FO4_CHAIR:
        test_title("TEST_FO4_CHAIR", "Extra data nodes are imported and exported")
        
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\FederalistChairOffice01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_FO4_CHAIR.nif")
        NifImporter.do_import(testfile, 0)

        fmarkers = [obj for obj in bpy.data.objects if obj.name.startswith("BSFurnitureMarkerNode")]
        
        assert len(fmarkers) == 4, f"Found furniture markers: {fmarkers}"
        mk = bpy.data.objects['BSFurnitureMarkerNode']
        assert VNearEqual(mk.rotation_euler, (-pi/2, 0, 0)), \
            f"Marker {mk.name} points the right direction: {mk.rotation_euler, (-pi/2, 0, 0)}"

        # -------- Export --------
        chair = find_shape("FederalistChairOffice01:2")
        fmrk = list(filter(lambda x: x.name.startswith('BSFurnitureMarkerNode'), bpy.data.objects))
        
        exporter = NifExporter(outfile, 'FO4')
        exporter.export([chair] + fmrk)

        # --------- Check ----------
        nifcheck = NifFile(outfile)
        fmcheck = nifcheck.furniture_markers

        assert len(fmcheck) == 4, f"Wrote the furniture marker correctly: {len(fmcheck)}"
        assert fmcheck[0].entry_points == 0, f"Entry point data is correct: {fmcheck[0].entry_points}"


    if TEST_CHANGE_COLLISION or TEST_BPY_ALL:
        test_title("TEST_CHANGE_COLLISION", "Changing collision type works correctly")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_CHANGE_COLLISION.nif")

        NifImporter.do_import(testfile)

        obj = bpy.context.object
        coll = find_shape('bhkCollisionObject')
        collbody = coll.children[0]
        collshape = find_shape('bhkBoxShape')
        bged = find_shape("BSBehaviorGraphExtraData")
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")
        assert collshape.name == 'bhkBoxShape', f"Found collision shape"
        
        collshape.name = "bhkConvexVerticesShape"

        # ------- Export --------

        # Move the edge of the collision box so it covers the bow better
        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([obj, coll, bged, strd, bsxf, invm])

        # ------- Check Results --------

        nifcheck = NifFile(outfile)
        midbowcheck = nifcheck.nodes["Bow_MidBone"]
        collcheck = midbowcheck.collision_object
        assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
        bodycheck = collcheck.body

        names = [x[0] for x in nifcheck.behavior_graph_data]
        assert "BGED" in names, f"Error: Expected BGED in {names}"
        bgedCheck = nifcheck.behavior_graph_data[0]
        log.debug(f"BGED value is {bgedCheck}")
        assert bgedCheck == ("BGED", "Weapons\\Bow\\BowProject.hkx", False), f"Extra data value = {bgedCheck}"
        assert not bgedCheck[2], f"Extra data controls base skeleton: {bgedCheck}"


    if TEST_BPY_ALL or TEST_VERTEX_ALPHA:
        test_title("TEST_VERTEX_ALPHA", "Export shape with vertex alpha values")

        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_VERTEX_ALPHA.nif")
        remove_file(outfile)
        append_from_file("Cube", True, r"tests\Skyrim\AlphaCube.blend", r"\Object", "Cube")
        exporter = NifExporter(outfile, "SKYRIM")
        exporter.export([bpy.data.objects["Cube"]])

        nifcheck = NifFile(outfile)
        shapecheck = nifcheck.shapes[0]

        assert shapecheck.shader_attributes.Shader_Flags_1 & ShaderFlags1.VERTEX_ALPHA, f"Expected VERTEX_ALPHA set: {ShaderFlags1(shapecheck.shader_attributes.Shader_Flags_1).fullname}"
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


    if TEST_WEIGHTS_EXPORT or TEST_BPY_ALL:
        test_title("TEST_WEIGHTS_EXPORT", "Exporting this head weights all verts correctly")
        clear_all()
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_WEIGHTS_EXPORT.nif")

        append_from_file("CheetahFemaleHead", True, r"tests\FO4\CheetahHead.blend", r"\Object", "CheetahFemaleHead")
        bpy.ops.object.select_all(action='DESELECT')

        head = find_shape("CheetahFemaleHead")
        print(head.name)
        skel = find_shape("BaseFemaleHead.nif")
        print(skel.name)
        
        remove_file(outfile)
        exp = NifExporter(outfile, 'FO4')
        exp.export([head, skel])

        # ------- Check ---------
        nifcheck = NifFile(outfile)

        headcheck = nifcheck.shape_dict["CheetahFemaleHead"]
        bw = headcheck.bone_weights
        for vert_index, v in enumerate(headcheck.verts):
            weightfound = False
            for bn in headcheck.get_used_bones():
                index_list = [p[0] for p in bw[bn]]
                weightfound |= (vert_index in index_list)
            assert weightfound, f"Weight not found for vert #{vert_index}"


    if TEST_DRAUGR_IMPORT or TEST_BPY_ALL:
        test_title("TEST_DRAUGR_IMPORT", "Import of this draugr mesh positions hood correctly")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\draugr lich01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_DRAUGR_IMPORT.nif")

        NifImporter.do_import(testfile)

        helm = find_shape("Helmet")
        hood = find_shape("Hood")

        helmz = max([x[2] for x in helm.bound_box])
        hoodz = max([x[2] for x in hood.bound_box])
        # CURRENT BUG. Figure out how to handle this nif.
        # assert helmz < hoodz, f"Helm height should be less than hood height: {helmz} < {hoodz}"
        

    if TEST_BPY_ALL or TEST_SCALING:
        test_title("TEST_SCALING", "Test that scale factors happen correctly")

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
        assert checkfoot.transform.rotation[0][0] == 1.0, f"ERROR: Foot rotation matrix not identity: {checkfoot.transform}"
        assert NearEqual(checkfoot.transform.scale, 1.0), f"ERROR: Foot scale not correct: {checkfoot.transform.scale}"

        zmax = max([v[2] for v in checkfoot.verts])
        zmin = min([v[2] for v in checkfoot.verts])
        assert zmax > 140, f"Foot is not scaled: {zmin} - {zmax}"
        assert zmin > 85, f"Foot is not scaled: {zmin} - {zmax}"

        checkbase = checknif.shape_dict['basis3']
        assert checkbase.transform.rotation[0][0] == 1.0, f"ERROR: Base rotation matrix not identity: {checkbase.transform.rotation}"
        assert checkbase.transform.scale == 10.0, f"ERROR: Base scale not correct: {checkbase.transform.scale}"
        zmax = max([v[2] for v in checkbase.verts])
        zmin = min([v[2] for v in checkbase.verts])
        assert zmax < 81, f"basis3 is not scaled: {zmin} - {zmax}"
        assert zmin < 15, f"basis3 is not scaled: {zmin} - {zmax}"


    if TEST_BPY_ALL or TEST_UNIFORM_SCALE:
        test_title("TEST_UNIFORM_SCALE", "Can export objects with non-uniform scaling")
        clear_all()

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        cube.scale = Vector((4.0, 4.0, 4.0))

        filepath = os.path.join(pynifly_dev_path, r"tests\Out\TEST_UNIFORM_SCALE.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'SKYRIM')
        exporter.export([cube])

        nifcheck = NifFile(filepath)
        shapecheck = nifcheck.shapes[0]
        assert NearEqual(shapecheck.transform.scale, 4.0), f"Shape scaled x4: {shapecheck.transform.scale}"
        for v in shapecheck.verts:
            assert VNearEqual(map(abs, v), [1,1,1]), f"All vertices at unit position: {v}"


    if TEST_BPY_ALL or TEST_NONUNIFORM_SCALE:
        test_title("TEST_NONUNIFORM_SCALE", "Can export objects with non-uniform scaling")
        clear_all()

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        cube.scale = Vector((2.0, 4.0, 8.0))

        filepath = os.path.join(pynifly_dev_path, r"tests\Out\TEST_NONUNIFORM_SCALE.nif")
        remove_file(filepath)
        exporter = NifExporter(filepath, 'SKYRIM')
        exporter.export([cube])

        nifcheck = NifFile(filepath)
        shapecheck = nifcheck.shapes[0]
        assert NearEqual(shapecheck.transform.scale, 1.0), f"Nonuniform scale exported in verts so scale is 1: {shapecheck.transform.scale}"
        for v in shapecheck.verts:
            assert not VNearEqual(map(abs, v), [1,1,1]), f"All vertices scaled away from unit position: {v}"


    if TEST_BPY_ALL or TEST_COLLISION_MULTI:
        test_title("TEST_COLLISION_MULTI", "Can read and write shape with multiple collision shapes")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\grilledleeks01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLLISION_MULTI.nif")

        NifImporter.do_import(testfile)

        leek1 = find_shape("Leek01")
        leek10 = find_shape("Leek01:0")
        leek11 = find_shape("Leek01:1")
        leek2 = find_shape("Leek02")
        leek3 = find_shape("Leek03")
        leek4 = find_shape("Leek04")
        c1 = find_shape("bhkCollisionObject", leek1.children)
        c2 = find_shape("bhkCollisionObject", leek2.children)
        assert set(leek1.children) == set( (c1, leek10, leek11) ), f"Children of Leek01 are correct: {leek1.children} == {c1}, {leek10}, {leek11}"
        
        # -------- Export --------
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")
        exporter = NifExporter(outfile, 'SKYRIM')
        exporter.export([leek1, leek2, leek3, leek4, bsxf, invm])

        # ------- Check ---------
        nif = NifFile(outfile)
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

            xfout = get_bone_global_xf(b, game)
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
        

    if TEST_BPY_ALL or TEST_CUSTOM_BONES:
        print('## TEST_CUSTOM_BONES Can handle custom bones correctly')
        clear_all()

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\VulpineInariTailPhysics.nif")
        nifimp = NifImporter(testfile)
        nifimp.execute()
        bone_xform = nifimp.nif.nodes['Bone_Cloth_H_003'].xform_to_global

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\TEST_CUSTOM_BONES.nif")
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                e = NifExporter(outfile, "FO4")
                e.export([obj])

        test_in = NifFile(outfile)
        new_xform = test_in.nodes['Bone_Cloth_H_003'].xform_to_global
        bone_euler = Matrix(bone_xform.rotation).to_euler()
        new_euler = Matrix(new_xform.rotation).to_euler()
        log.debug(f"Have rotations old: {bone_euler}, new: {new_euler}")
        assert VNearEqual(bone_xform.translation, new_xform.translation), f"Error: Bone 'Bone_Cloth_H_003' transform should not change. Expected\n {bone_xform}, found\n {new_xform}"
        assert MatNearEqual(bone_xform.rotation, new_xform.rotation), f"Error: Bone 'Bone_Cloth_H_003' rotation should not change. Expected\n {bone_xform}, found\n {new_xform}"
        assert round(bone_xform.scale) == round(new_xform.scale), f"Error: 'Bone_Cloth_H_003' Scale factors should not change. Expected {bone_xform.scale}, found {bone_xform.scale}"


    if TEST_BPY_ALL or TEST_CONNECTED_SKEL:
        test_title('TEST_CONNECTED_SKEL', 'Can import connected skeleton')
        clear_all()

        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\vanillaMaleBody.nif")
        NifImporter.do_import(testfile)

        s = bpy.data.objects[r"BASE meshes\Actors\Character\CharacterAssets\MaleBody.nif"]
        assert s.type == 'ARMATURE', f"Imported the skeleton {s}" 
        assert 'Leg_Thigh.L' in s.data.bones.keys(), "Error: Should have left thigh"
        lthigh = s.data.bones['Leg_Thigh.L']
        assert lthigh.parent.name == 'Pelvis', "Error: Thigh should connect to pelvis"
        assert VNearEqual(lthigh.head_local, (-6.6151, 0.0005, 68.9113)), f"Thigh head in correct location: {lthigh.head_local}"
        assert VNearEqual(lthigh.tail_local, (-7.2513, -0.1925, 63.9557)), f"Thigh tail in correct location: {lthigh.tail_local}"


    if TEST_BPY_ALL or TEST_BONE_HIERARCHY:
        test_title("TEST_BONE_HIERARCHY", "Bone hierarchy can be written on export")
        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\SkyrimSE\Anna.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BONE_HIERARCHY.nif")

        NifImporter.do_import(testfile)

        hair = find_shape("KSSMP_Anna")
        skel = hair.parent
        assert skel

        print("# -------- Export --------")
        remove_file(outfile)
        exporter = NifExporter(outfile, 'SKYRIMSE',
                               export_flags=PyNiflyFlags.PRESERVE_HIERARCHY 
                                            | PyNiflyFlags.RENAME_BONES | PyNiflyFlags.APPLY_SKINNING)
        exporter.export([hair])

        print("# ------- Check ---------")
        nifcheck = NifFile(outfile)
        haircheck = nifcheck.shape_dict["KSSMP_Anna"]

        com = nifcheck.nodes["NPC COM [COM ]"]
        assert VNearEqual(com.transform.translation, (0, 0, 68.9113)), f"COM location is correct: \n{com.transform}"

        spine0 = nifcheck.nodes["NPC Spine [Spn0]"]
        assert VNearEqual(spine0.transform.translation, (0, -5.239852, 3.791618)), f"spine0 location is correct: \n{spine0.transform}"
        spine0Rot = Matrix(spine0.transform.rotation).to_euler()
        assert VNearEqual(spine0Rot, (-0.0436, 0, 0)), f"spine0 rotation correct: {spine0Rot}"

        spine1 = nifcheck.nodes["NPC Spine1 [Spn1]"]
        assert VNearEqual(spine1.transform.translation, (0, 0, 8.748718)), f"spine1 location is correct: \n{spine1.transform}"
        spine1Rot = Matrix(spine1.transform.rotation).to_euler()
        assert VNearEqual(spine1Rot, (0.1509, 0, 0)), f"spine1 rotation correct: {spine1Rot}"

        spine2 = nifcheck.nodes["NPC Spine2 [Spn2]"]
        assert spine2.parent.name == "NPC Spine1 [Spn1]", f"Spine2 parent is correct"
        assert VNearEqual(spine2.transform.translation, (0, -0.017105, 9.864068), 0.01), f"Spine2 location is correct: \n{spine2.transform}"

        head = nifcheck.nodes["NPC Head [Head]"]
        assert VNearEqual(head.transform.translation, (0, 0, 7.392755)), f"head location is correct: \n{head.transform}"
        headRot = Matrix(head.transform.rotation).to_euler()
        assert VNearEqual(headRot, (0.1913, 0.0009, -0.0002), 0.01), f"head rotation correct: {headRot}"

        l3 = nifcheck.nodes["Anna L3"]
        assert l3.parent, f"'Anna L3' parent exists"
        assert l3.parent.name == 'Anna L2', f"'Anna L3' parent is '{l3.parent.name}'"
        assert VNearEqual(l3.transform.translation, (0, 5, -6), 0.1), f"{l3.name} location correct: \n{l3.transform}"


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


    if TEST_BPY_ALL or TEST_COLLISION_LIST:
        test_title("TEST_COLLISION_LIST", "Can read and write shape with collision list and collision transform shapes")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\falmerstaff.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLLISION_LIST.nif")

        NifImporter.do_import(testfile)

        staff = find_shape("Staff3rdPerson:0")
        coll = find_shape("bhkCollisionObject")
        collbody = coll.children[0]
        collshape = collbody.children[0]
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

        assert collshape.name.startswith("bhkListShape"), f"Found list collision shape: {collshape.name}"
        assert len(collshape.children) == 3, f" Collision shape has children"
        
        # -------- Export --------
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")
        exporter = NifExporter(outfile, 'SKYRIM')
        exporter.export([staff, coll, bsxf, invm, strd])

        # ------- Check ---------
        nifcheck = NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff3rdPerson:0"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        listcheck = rbcheck.shape
        assert listcheck.blockname == "bhkListShape", f"Got a list collision back {listcheck.blockname}"
        assert len(listcheck.children) == 3, f"Got our list elements back: {len(listcheck.children)}"

        cts0check = listcheck.children[0]
        assert cts0check.child.blockname == "bhkBoxShape", f"Found the box shape"

        cts45check = [cts for cts in listcheck.children if NearEqual(cts.transform[1][1], 0.7071, 0.01)]
        boxdiag = cts45check[0].child
        assert NearEqual(boxdiag.properties.bhkDimensions[1], 0.170421), f"Diagonal box has correct size: {boxdiag.properties.bhkDimensions[1]}"

    if TEST_BPY_ALL or TEST_COLLISION_CAPSULE:
        test_title("TEST_COLLISION_CAPSULE", "Can read and write shape with collision capsule shapes")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\staff04.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLLISION_CAPSULE.nif")

        NifImporter.do_import(testfile)

        staff = find_shape("3rdPersonStaff04")
        coll = find_shape("bhkCollisionObject")
        collbody = coll.children[0]
        collshape = collbody.children[0]
        strd = find_shape("NiStringExtraData")
        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")

        assert collshape.name.startswith("bhkCapsuleShape"), f"Found list collision shape: {collshape.name}"
        v = collshape.data.vertices[5]
        assert NearEqual(v.co.z, 67.4) or NearEqual(v.co.y, -67.4), f"Found verts where expected for {collshape.name}: {v.co}"
        assert VNearEqual(collshape.location, (0, -2.8, 0.79), 0.1), f"Collision in right location for {collshape.name}: {collshape.location})"

        # -------- Export --------
        remove_file(outfile)
        exporter = NifExporter(outfile, 'SKYRIM')
        exporter.export([staff, coll, bsxf, invm, strd])

        # ------- Check ---------
        nifcheck = NifFile(outfile)
        staffcheck = nifcheck.shape_dict["3rdPersonStaff04:1"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        shapecheck = rbcheck.shape
        assert shapecheck.blockname == "bhkCapsuleShape", f"Got a capsule collision back {shapecheck.blockname}"

        niforig = NifFile(testfile)
        collorig = niforig.rootNode.collision_object
        rborig = collorig.body
        shapeorig = rborig.shape
        assert NearEqual(shapeorig.properties.radius1, shapecheck.properties.radius1), f"Wrote the correct radius: {shapecheck.properties.radius1}"
        assert NearEqual(shapeorig.properties.point1[1], shapecheck.properties.point1[1]), f"Wrote the correct radius: {shapecheck.properties.point1[1]}"


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
        nifcheck = NifFile(outfile)
        staffcheck = nifcheck.shape_dict["Staff"]
        collcheck = nifcheck.rootNode.collision_object
        rbcheck = collcheck.body
        listcheck = rbcheck.shape
        cvShapes = [c for c in listcheck.children if c.blockname == "bhkConvexVerticesShape"]
        maxz = max([v[2] for v in cvShapes[0].vertices])
        assert maxz < 0, f"All verts on collisions shape on negative z axis: {maxz}"

        
    if TEST_BPY_ALL or TEST_BOW:
        test_title("TEST_BOW", "Can read and write bow")
        # Primarily tests collisions, but also tests fade node, extra data nodes, 
        # UV orientation, and texture handling
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests/SkyrimSE/meshes/weapons/glassbowskinned.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BOW.nif")

        NifImporter.do_import(testfile)

        # Check root info
        obj = bpy.context.object
        assert obj["pynRootNode_BlockType"] == 'BSFadeNode', "pynRootNode_BlockType holds the type of root node for the given shape"
        assert obj["pynRootNode_Name"] == "GlassBowSkinned.nif", "pynRootNode_Name holds the name for the root node"
        assert obj["pynRootNode_Flags"] == "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR", f"'pynRootNode_Flags' holds the flags on the root node: {obj['pynRootNode_Flags']}"

        # Check collision info
        coll = find_shape('bhkCollisionObject')
        assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
        assert coll['pynCollisionTarget'] == 'Bow_MidBone', f"'Target' names the object the collision affects, in this case a bone: {coll['pynCollisionTarget']}"

        collbody = coll.children[0]
        assert collbody.name == 'bhkRigidBodyT', f"Child of collision is the collision body object"
        assert collbody['collisionFilter_layer'] == SkyrimCollisionLayer.WEAPON.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
        assert collbody["collisionResponse"] == hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"
        assert VNearEqual(collbody.rotation_quaternion, (0.7071, 0.0, 0.0, 0.7071)), f"Collision body rotation correct: {collbody.rotation_quaternion}"

        collshape = collbody.children[0]
        assert collshape.name == 'bhkBoxShape', f"Collision shape is child of the collision body"
        assert collshape['bhkMaterial'] == 'MATERIAL_BOWS_STAVES', f"Shape material is a custom property: {collshape['bhkMaterial']}"
        assert round(collshape['bhkRadius'],4) == 0.0136, f"Radius property available as custom property: {collshape['bhkRadius']}"
        corner = map(abs, collshape.data.vertices[0].co)
        assert VNearEqual(corner, [11.01445, 57.6582, 0.95413]), f"Collision shape in correct position: {corner}"

        bged = find_shape("BSBehaviorGraphExtraData")
        assert bged['BSBehaviorGraphExtraData_Value'] == "Weapons\Bow\BowProject.hkx", f"BGED node contains bow project: {bged['BSBehaviorGraphExtraData_Value']}"

        strd = find_shape("NiStringExtraData")
        assert strd['NiStringExtraData_Value'] == "WeaponBow", f"Str ED node contains bow value: {strd['NiStringExtraData_Value']}"

        bsxf = find_shape("BSXFlags")
        assert bsxf['BSXFlags_Name'] == "BSX", f"BSX Flags contain name BSX: {bsxf['BSXFlags_Name']}"
        assert bsxf['BSXFlags_Value'] == "HAVOC | COMPLEX | DYNAMIC | ARTICULATED", "BSX Flags object contains correct flags: {bsxf['BSXFlags_Value']}"

        invm = find_shape("BSInvMarker")
        assert invm['BSInvMarker_Name'] == "INV", f"Inventory marker shape has correct name: {invm['BSInvMarker_Name']}"
        assert invm['BSInvMarker_RotX'] == 4712, f"Inventory marker rotation correct: {invm['BSInvMarker_RotX']}"
        assert round(invm['BSInvMarker_Zoom'], 4) == 1.1273, f"Inventory marker zoom correct: {invm['BSInvMarker_Zoom']}"
       
        # ------- Export --------

        # Move the edge of the collision box so it covers the bow better
        for v in collshape.data.vertices:
            if v.co.x > 0:
                v.co.x = 16.5

        exporter = NifExporter(outfile, 'SKYRIMSE')
        exporter.export([obj, coll, bged, strd, bsxf, invm])

        # ------- Check Results --------

        nifcheck = NifFile(outfile)
        rootcheck = nifcheck.rootNode
        assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
        assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
        assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

        bsxcheck = nifcheck.bsx_flags
        assert bsxcheck == ["BSX", 202], f"BSX Flag node found: {bsxcheck}"

        bsinvcheck = nifcheck.inventory_marker
        assert bsinvcheck[0:4] == ["INV", 4712, 0, 785], f"Inventory marker set: {bsinvcheck}"
        assert round(bsinvcheck[4], 4) == 1.1273, f"Inventory marker zoom set: {bsinvcheck[4]}"

        midbowcheck = nifcheck.nodes["Bow_MidBone"]
        collcheck = midbowcheck.collision_object
        assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
        assert bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

        # Full check of locations and rotations to make sure we got them right
        mbc_xf = nifcheck.get_node_xform_to_global("Bow_MidBone")
        assert VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
        m = mbc_xf.as_matrix().to_euler()
        assert VNearEqual(m, [0, 0, -pi/2]), f"Midbow rotation is correct: {m}"

        bodycheck = collcheck.body
        p = bodycheck.properties
        assert VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"
        assert VNearEqual(p.rotation[:], [0.0, 0.0, 0.707106, 0.707106]), f"Collision body rotation correct: {p.rotation[:]}"


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


    if TEST_BPY_ALL or TEST_COLLISION_CONVEXVERT:
        test_title("TEST_COLLISION_CONVEXVERT", "Can read and write shape with convex verts collision shape")
        clear_all()

        # ------- Load --------
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\cheesewedge01.nif")
        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_COLLISION_CONVEXVERT.nif")

        NifImporter.do_import(testfile)

        # Check transform
        obj = find_shape('CheeseWedge')
        assert VNearEqual(obj.location, (0,0,0)), f"Cheese wedge at right location"
        assert VNearEqual(obj.rotation_euler, (0,0,0)), f"Cheese wedge not rotated"
        assert obj.scale == Vector((1,1,1)), f"Cheese wedge scale 1"

        # Check collision info
        coll = find_shape('bhkCollisionObject')
        assert coll['pynCollisionFlags'] == "ACTIVE | SYNC_ON_UPDATE", f"bhkCollisionShape represents a collision"
        assert coll.parent == None, f"Collision shape has no parent"

        collbody = coll.children[0]
        assert collbody.name == 'bhkRigidBody', f"Child of collision is the collision body object"
        assert collbody['collisionFilter_layer'] == SkyrimCollisionLayer.CLUTTER.name, f"Collsion filter layer is loaded as string: {collbody['collisionFilter_layer']}"
        assert collbody["collisionResponse"] == hkResponseType.SIMPLE_CONTACT.name, f"Collision response loaded as string: {collbody['collisionResponse']}"

        collshape = collbody.children[0]
        assert collshape.name == 'bhkConvexVerticesShape', f"Collision shape is child of the collision body"
        assert collshape['bhkMaterial'] == 'CLOTH', f"Shape material is a custom property: {collshape['bhkMaterial']}"
        obj = find_shape('CheeseWedge01', collection=bpy.context.selected_objects)
        xmax1 = max([v.co.x for v in obj.data.vertices])
        xmax2 = max([v.co.x for v in collshape.data.vertices])
        assert abs(xmax1 - xmax2) < 0.5, f"Max x vertex nearly the same: {xmax1} == {xmax2}"
        corner = collshape.data.vertices[0].co
        assert VNearEqual(corner, (-4.18715, -7.89243, 7.08596)), f"Collision shape in correct position: {corner}"

        # ------- Export --------

        bsxf = find_shape("BSXFlags")
        invm = find_shape("BSInvMarker")
        exporter = NifExporter(outfile, 'SKYRIM')
        exporter.export([obj, coll, bsxf, invm])

        # ------- Check Results --------

        nifcheck = NifFile(outfile)

        rootcheck = nifcheck.rootNode
        assert rootcheck.name == "CheeseWedge01", f"Root node name incorrect: {rootcheck.name}"
        assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"

        collcheck = rootcheck.collision_object
        assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
        assert collcheck.target == rootcheck, f"Target of collision is root: {rootcheck.name}"

        bodycheck = collcheck.body
        assert bodycheck.blockname == "bhkRigidBody", f"Correctly wrote bhkRigidBody: {bodycheck.blockname}"

        shapecheck = bodycheck.shape
        assert shapecheck.blockname == "bhkConvexVerticesShape", f"Collision body's shape property returns the collision shape"
        assert shapecheck.properties.bhkMaterial == SkyrimHavokMaterial.CLOTH, "Collision body shape material is readable"
        assert VNearEqual(shapecheck.vertices[0], [-0.059824, -0.112763, 0.101241, 0]), f"Vertex 0 is correct"
        assert VNearEqual(shapecheck.vertices[7], [-0.119985, 0.000001, 0, 0]), f"Vertex 7 is correct"

        # Re-import
        #
        # There have been issues with importing the exported nif and having the 
        # collision be wrong
        clear_all()
        NifImporter.do_import(outfile)

        impcollshape = find_shape("bhkConvexVerticesShape")
        zmin = min([v.co.z for v in impcollshape.data.vertices])
        assert zmin >= -0.01, f"Minimum z is positive: {zmin}"

       
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


    if TEST_IMP_NORMALS:
        test_title("TEST_IMP_NORMALS", "Can import normals from nif shape")
        clear_all()

        testfile = os.path.join(pynifly_dev_path, r"tests/Skyrim/cube.nif")
        NifImporter.do_import(testfile)

        # all loop custom normals point off at diagonals
        obj = bpy.context.object
        for l in obj.data.loops:
            for i in [0, 1, 2]:
                assert round(abs(l.normal[i]), 3) == 0.577, f"Expected diagonal normal, got loop {l.index}/{i} = {l.normal[i]}"


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
        imp = NifImporter.do_import(testfile, PyNiflyFlags.RENAME_BONES | PyNiflyFlags.APPLY_SKINNING)
        assert round(imp.nif.shapes[0].global_to_skin.translation[2]) == -140, f"Expected -140 z translation in first nif, got {imp.nif.shapes[0].global_to_skin.translation[2]}"

        sm1 = bpy.context.object
        assert round(sm1.location[2]) == 140, f"Expect first supermutant body at 140 Z, got {sm1.location[2]}"

        imp2 = NifImporter.do_import(testfile, PyNiflyFlags.RENAME_BONES | PyNiflyFlags.APPLY_SKINNING)
        sm2 = bpy.context.object
        assert round(sm2.location[2]) == 140, f"Expect supermutant body at 140 Z, got {sm2.location[2]}"

        
    if TEST_BPY_ALL or TEST_RENAME:
        test_title("TEST_RENAME", "Test that renaming bones works correctly")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\femalebody_1.nif")
        imp = NifImporter.do_import(testfile, PyNiflyFlags.CREATE_BONES | PyNiflyFlags.APPLY_SKINNING)

        body = bpy.context.object
        vgnames = [x.name for x in body.vertex_groups]
        vgxl = list(filter(lambda x: ".L" in x or ".R" in x, vgnames))
        assert len(vgxl) == 0, f"Expected no vertex groups renamed, got {vgxl}"

        armnames = [b.name for b in body.parent.data.bones]
        armxl = list(filter(lambda x: ".L" in x or ".R" in x, armnames))
        assert len(armxl) == 0, f"Expected no bones renamed in armature, got {armxl}"


    if TEST_BPY_ALL or TEST_BONE_XPORT_POS:
        test_title("TEST_BONE_XPORT_POS", "Test that bones named like vanilla bones but from a different skeleton export to the correct position")

        clear_all()
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\draugr.nif")
        imp = NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING)
        draugr = bpy.context.object
        spine2 = draugr.parent.data.bones['NPC Spine2 [Spn2]']
        assert round(spine2.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2.head[2]}"

        outfile = os.path.join(pynifly_dev_path, r"tests/Out/TEST_BONE_XPORT_POS.nif")
        exp = NifExporter(outfile, 'SKYRIM')
        exp.export([bpy.data.objects["Body_Male_Naked"]])

        impcheck = NifImporter.do_import(outfile, PyNiflyFlags.APPLY_SKINNING)

        nifbone = impcheck.nif.nodes['NPC Spine2 [Spn2]']
        assert round(nifbone.transform.translation[2], 2) == 102.36, f"Expected nif location at z 102.36, found {nifbone.transform.translation[2]}"

        draugrcheck = bpy.context.object
        spine2check = draugrcheck.parent.data.bones['NPC Spine2 [Spn2]']
        assert round(spine2check.head[2], 2) == 102.36, f"Expected location at z 102.36, found {spine2check.head[2]}"


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
        imp = NifImporter.do_import(testfile, PyNiflyFlags.APPLY_SKINNING)
        assert 'ANCHOR:0' in bpy.data.objects.keys()


    if TEST_BPY_ALL or TEST_IMPORT_ARMATURE:
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


    if TEST_BPY_ALL or TEST_IMP_EXP_SKY:
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
        armor_gts = TransformBuf()
        armor_gts.translation = (0.000256, 1.547526, -120.343582)
        new_armor.set_global_to_skin(armor_gts)

        for b in the_armor.bone_weights.keys():
            new_armor.add_bone(b)
            new_armor.setShapeWeights(b, the_armor.bone_weights[b])
        
        new_nif.save()
            
    if TEST_BPY_ALL or TEST_IMP_EXP_FO4:
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
        body_gts = TransformBuf()
        body_gts.translation = (0.000256, 1.547526, -120.343582)
        new_body.set_global_to_skin(body_gts)

        for b in the_body.bone_weights.keys():
            new_body.add_bone(b)
            new_body.setShapeWeights(b, the_body.bone_weights[b])
        
        new_nif.save()
            

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

    if TEST_BPY_ALL or TEST_BABY:
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


    if TEST_BPY_ALL or TEST_FACEBONES:
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
    
        
    if TEST_BPY_ALL or TEST_FACEBONE_EXPORT:
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
                               "FO4", chargen="_chargen")
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


