"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

RUN_TESTS = True

bl_info = {
    "name": "NIF format",
    "description": "Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (2, 92, 0),
    "version": (0, 0, 10), 
    "location": "File > Import-Export",
    "warning": "WIP",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

import sys
import os.path
import pathlib
from operator import or_
from functools import reduce
import traceback
import math

pynifly_dev_root = r"D:\OneDrive\Dev"
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")

# Load from dev path if it exists
if os.path.exists(pynifly_dev_path):
    print(f"PyNifly dev path: {pynifly_dev_path}")
    if pynifly_dev_path not in sys.path:
        sys.path.append(pynifly_dev_path)
    nifly_path = os.path.join(pynifly_dev_root, r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll")
else:
    # Load from install location
    py_addon_path = os.path.dirname(os.path.realpath(__file__))
    print(f"PyNifly addon path: {py_addon_path}")
    if py_addon_path not in sys.path:
        sys.path.append(py_addon_path)
    nifly_path = os.path.join(py_addon_path, "NiflyDLL.dll")

print(f"Nifly DLL at {nifly_path}")
if not os.path.exists(nifly_path):
    print("ERROR: pynifly DLL not found")

from pynifly import *
from niflytools import *
import pyniflywhereami

NifFile.Load(nifly_path)

import bpy
from bpy.props import (
        BoolProperty,
        FloatProperty,
        StringProperty,
        EnumProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper)
import bmesh


# ### ---------------------------- IMPORT -------------------------------- ###

def mesh_create_uv(the_mesh, uv_points):
    """ Create UV in Blender to match UVpoints from Nif
        uv_points = [(u, v)...] indexed by vertex index
        """
    new_uv = [(0,0)] * len(the_mesh.data.loops)
    for lp_idx, lp in enumerate(the_mesh.data.loops):
        vert_targeted = lp.vertex_index
        new_uv[lp_idx] = (uv_points[vert_targeted][0], 1-uv_points[vert_targeted][1])
    new_uvlayer = the_mesh.data.uv_layers.new(do_init=False)
    for i, this_uv in enumerate(new_uv):
        new_uvlayer.data[i].uv = this_uv

def mesh_create_groups(the_shape, the_object, skel_dict):
    vg = the_object.vertex_groups
    for bone_name in the_shape.bone_names:
        xlate_name = skel_dict.blender_name(bone_name)
        new_vg = vg.new(name=xlate_name)
        for v, w in the_shape.bone_weights[bone_name]:
            new_vg.add((v,), w, 'ADD')
    
def import_shape(the_shape: NiShape, skel_dict):
    """ Import the shape to a Blender object, using skel_dict to translate bone names """
    v = the_shape.verts
    t = the_shape.tris

    new_mesh = bpy.data.meshes.new(the_shape.name)
    new_mesh.from_pydata(v, [], t)
    new_object = bpy.data.objects.new(the_shape.name, new_mesh)

    # Global-to-skin transform is what offsets all the vertices together, e.g. so that
    # heads can be positioned at the origin. Put the reverse transform on the blender 
    # object so they can be worked on in their skinned position.
    # Use the one on the NiSkinData if it exists.
    xform =  the_shape.global_to_skin_data
    if xform is None:
        xform = the_shape.global_to_skin
    inv_xf = xform.invert()
    new_object.scale = [inv_xf.scale] * 3
    new_object.location = inv_xf.translation
    new_object.rotation_euler[0], new_object.rotation_euler[1], new_object.rotation_euler[2] \
        = inv_xf.rotation.euler_deg()

    mesh_create_uv(new_object, the_shape.uvs)
    mesh_create_groups(the_shape, new_object, skel_dict)
    for f in new_mesh.polygons:
        f.use_smooth = True

    new_mesh.update(calc_edges=True, calc_edges_loose=True)
    new_mesh.validate(verbose=True)
    return new_object

def make_armature(the_coll, the_nif, skel_dict, bone_names):
    arm_data = bpy.data.armatures.new(the_nif.rootName)
    arm_ob = bpy.data.objects.new(the_nif.rootName, arm_data)
    the_coll.objects.link(arm_ob)
    arm_ob.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    
    for bone_game_name in bone_names:
        #print("%s: %s" % (bone_game_name, str(skel_dict.blender_name(bone_game_name))))
        blend_name = skel_dict.blender_name(bone_game_name)
        bone =  arm_data.edit_bones.new(blend_name)
        bone_xform = the_nif.nodes[bone_game_name].xform_to_global
        bone.head = bone_xform.translation
        rot_vec = bone_xform.rotation.by_vector((5.0, 0.0, 0.0))
        bone.tail = (bone.head[0] + rot_vec[0], bone.head[1] + rot_vec[1], bone.head[2] + rot_vec[2])
        bone['pyxform'] = bone_xform.rotation.matrix
        
    # Hook them up
    for arma_bone in arm_data.edit_bones:
        #print("Parenting " + arma_bone.name)
        parentname = None
        skelbone = skel_dict.byBlender[arma_bone.name]
        #print("Skelbone is " + skelbone.blender)
        parentnibone = the_nif.nodes[skelbone.nif].parent
        if parentnibone:
            if parentnibone.name in skel_dict.byNif:
                parentname = skel_dict.byNif[parentnibone.name].blender
                #print("Parent bone from nif: " + parentname)
        if not parentname:
            if skelbone.parent:
                parentname = skelbone.parent.blender
                #print("Parent bone from skeleton: " + parentname)
        if parentname:
            if parentname in arm_data.edit_bones:
                #print("---Found parent bone " + arm_data.edit_bones[parentname].name)
                arma_bone.parent = arm_data.edit_bones[parentname]
            #else:
                #print("Parent bone not in skeleton: " + parentname)

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    return arm_ob

# ### ---------------------------- EXPORT -------------------------------- ###

def extract_face_info(bm):
    uv_lay = bm.loops.layers.uv.active
    loops = []
    uvs = []
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        for seg in f.loops:
            loops.append(seg.vert.index)
            uvs.append(seg[uv_lay].uv[:])
    
    return loops, uvs

def extract_vert_info(obj, bm, target_key):
    """Returns 3 lists of equal length with one entry each for each vertex
        verts = [(x, y, z)... ] 
        norms = [(x, y, z)... ] 
        weights = [{group-name: weight}... ]
        """
    verts = []
    norms = []
    weights = []
    deform_layer = bm.verts.layers.deform.active
    key_layer = None
    if target_key != '':
        key_layer = bm.verts.layers.shape[target_key]
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if target_key == '':
            verts.append(v.co[:])
        else:
            verts.append(v[key_layer][:])
        norms.append(v.normal[:])
        if deform_layer:
            vert_weights = {}
            for g, w in v[deform_layer].items():
                vert_weights[obj.vertex_groups[g].name] = w
            weights.append(vert_weights)
    return verts, norms, weights

def get_bone_locations(arma, bone_names):
    """Return location of bones in list
    arma = data block of armature
    bone_names = list of names
    result = dict{bone-name: MatTransform, ...}
    """
    result = {}
    for b in arma.bones:
        mat = MatTransform()
        mat.translation = b.head
        mat.rotation = RotationMatrix((tuple(b['pyxform'][0]), 
                                       tuple(b['pyxform'][1]), 
                                       tuple(b['pyxform'][2])))
        result[b.name] = mat
    return result

def export_shape(nif, obj, target_key=''):
    """Export given blender object to the given NIF file
        nif = target nif file
        obj = blender object
        target_key = shape key to export
        """
    print("Exporting " + obj.name)
    exportSkel = gameSkeletons[nif.game]
    mesh = obj.data
    is_skinned = (obj.parent and obj.parent.type == 'ARMATURE')
    if is_skinned:
        nif.createSkin()
    
    print("..Triangulating mesh")
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
    
        bmesh.ops.triangulate(bm, faces=bm.faces[:])

        verts, norms, weights_by_vert = extract_vert_info(obj, bm, target_key)
        #loops, polyverts, uvs = extract_face_info(bm)
        loops, uvs = extract_face_info(bm)
    
        print("..Splitting mesh along UV seams")
        mesh_split_by_uv(verts, norms, loops, uvs, weights_by_vert)
        # Old UV map had dups were verts were split; new matches 1-1 with verts
        uvmap_new = [uvs[loops.index(i)] for i in range(0, len(verts))]
        tris = [(loops[i], loops[i+1], loops[i+2]) for i in range(0, len(loops), 3)]
    
        print("..Exporting to nif")
        #for i, v in enumerate(verts):
        #    print(i, v)
        #print(tris)
        #for i, u in enumerate(uvmap_new):
        #    print(loops[i], round(u[0], 4), round(u[1], 4))
        new_shape = nif.createShapeFromData(mesh.name, verts, tris, uvmap_new, norms)

        new_xform = MatTransform();
        new_xform.translation = obj.location
        rot = RotationMatrix.from_euler(obj.rotation_euler[0], 
                                        obj.rotation_euler[1], 
                                        obj.rotation_euler[2])
        if rot is not None:
            new_xform.rotation = rot
        else:
            print(f"Warning: Invalid rotation matrix on {obj.name}")

        if obj.scale[0] != obj.scale[1] or obj.scale[0] != obj.scale[2]:
           print("Warning: Object scale not uniform, using x-value") # apply scale to verts?   
        new_xform.scale = obj.scale[0]
        # new_shape.SetNodeTransform(new_xform)
        
        if is_skinned:
            print("..Parent is armature, skin the mesh")
            new_shape.skin()
            # if new_shape.has_skin_instance: 
            if nif.game == "SKYRIM":
                new_shape.set_global_to_skindata(new_xform.invert())
            else:
                new_shape.set_global_to_skin(new_xform.invert())

            group_names = [g.name for g in obj.vertex_groups]
            weights_by_bone = get_weights_by_bone(weights_by_vert)
            used_bones = weights_by_bone.keys()
            arma_bones = get_bone_locations(obj.parent.data, used_bones)

            for bone_name, bone_xform in arma_bones.items():
                #print("  adding bone " + b)
                if bone_name in weights_by_bone and len(weights_by_bone[bone_name]) > 0:
                    #print(f"..Exporting bone {bone_name} with rotation {bone_xform.rotation.euler_deg()}")
                    new_shape.add_bone(exportSkel.nif_name(bone_name), bone_xform)
                    new_shape.setShapeWeights(exportSkel.nif_name(bone_name),
                                              weights_by_bone[bone_name])

    except:
        bm.free()
        raise 

    bm.free()
    
    print("..DONE")
    return {'FINISHED'}

def import_file(f: NifFile):
    new_collection = bpy.data.collections.new(os.path.basename(f.filepath))
    bpy.context.scene.collection.children.link(new_collection)

    print("..Importing " + f.game + " file")
    sourceSkel = gameSkeletons[f.game]
    bones = set()
    new_objs = []

    for s in f.shapes:
        obj = import_shape(s, sourceSkel)
        new_objs.append(obj)
        new_collection.objects.link(obj)

        for n in s.bone_names: 
            if n in sourceSkel.byNif:
                bones.add(n) 
            else:
                print(n + " not in skel")

    for o in new_objs: o.select_set(True)
    if len(bones) > 0:
        #print("Found bones, creating skeleton: " + str(bones))
        skel = make_armature(new_collection, f, sourceSkel, bones)
        for o in new_objs: o.select_set(True)
        bpy.ops.object.parent_set(type='ARMATURE_NAME', xmirror=False, keep_transform=False)

class ImportNIF(bpy.types.Operator, ImportHelper):
    """Load a NIF File"""
    bl_idname = "import_scene.nifly"
    bl_label = "Import NIF (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".nif"

    def execute(self, context):
        print('Nifly Import')
        bpy.ops.object.select_all(action='DESELECT')
        skel = None
        f = NifFile(self.filepath)
        sourceGame = f.game
        print('Importing ' + self.filepath + ' ' + sourceGame)
        new_collection = bpy.data.collections.new(os.path.basename(f.filepath))
        bpy.context.scene.collection.children.link(new_collection)
#        if len(f.nodes) > 1:
#            skel = make_armature(f)
#            new_collection.objects.link(skel)
        sourceSkel = gameSkeletons[sourceGame]
        bones = set()
        new_objs = []

        for s in f.shapes:
            obj = import_shape(s, sourceSkel)
            new_objs.append(obj)
            new_collection.objects.link(obj)
            for n in s.bone_names: 
                #if n in sourceSkel.byNif:
                bones.add(n) 

        if len(bones) > 0:
            #print("Found bones, creating skeleton: " + str(bones))
            skel = make_armature(new_collection, f, sourceSkel, bones)
            for o in new_objs: o.select_set(True)
            bpy.ops.object.parent_set(type='ARMATURE_NAME', xmirror=False, keep_transform=False)
        
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                ctx = bpy.context.copy()
                ctx['area'] = area
                ctx['region'] = area.regions[-1]
                bpy.ops.view3d.view_selected(ctx)        
        return {'FINISHED'}

def get_common_shapes(obj_list):
    """ Return the shape keys common to all the given objects """
    res = None
    for obj in obj_list:
        o_shapes = set()
        if obj.data.shape_keys:
            o_shapes = set(obj.data.shape_keys.key_blocks.keys())
        if res:
            res = res.intersection(o_shapes)
        else:
            res = o_shapes
    return list(res)

def get_with_uscore(str_list):
    return list(filter((lambda x: x[0] == '_'), str_list))

class ExportNIF(bpy.types.Operator, ExportHelper):
    """Save a NIF File"""

    bl_idname = "export_scene.nifly"
    bl_label = 'Export NIF (Nifly)'
    bl_options = {'PRESET'}

    filename_ext = ".nif"
    
    target_game: EnumProperty(
            name="Target Game",
            items=(('SKYRIM', "Skyrim", ""),
                   ('SKYRIMSE', "Skyrim SE", ""),
                   ('FO4', "Fallout 4", ""),
                   ('FO76', "Fallout 76", ""),
                   ('FO3', "Fallout New Vegas", ""),
                   ('FO3', "Fallout 3", ""),
                   ),
            )

    def execute(self, context):
        print('NIFLY EXPORT')
        try:
            res = {'FINISHED'}
        
            objs_to_export = set()
            armatures_found = set()
        
            for obj in context.selected_objects:  
                if obj.type == 'ARMATURE':
                    armatures_found.add(obj)
                    for child in obj.children:
                        if child.type == 'MESH':
                            objs_to_export.add(child)
                elif obj.type == 'MESH':
                    objs_to_export.add(obj)
        
            if len(objs_to_export) == 0:
                print("Warning: Nothing to export")
                return {"CANCELLED"}
            else:
                shape_keys = get_with_uscore(get_common_shapes(objs_to_export))
                if len(shape_keys) == 0:
                    shape_keys.append('') # just export the plain file
                for sk in shape_keys:
                    fn = os.path.splitext(os.path.basename(self.filepath))
                    fp = os.path.join(os.path.dirname(self.filepath), fn[0] + sk + fn[1])
                    print('Exporting to ' + self.target_game + ' ' + fp)
                    exportf = NifFile()
                    exportf.initialize(self.target_game, fp)
                    for obj in objs_to_export:
                        res = export_shape(exportf, obj, sk)
                    exportf.save()
        
        except:
            print("ERROR exporting nif")
            traceback.print_exc()
            res = {"CANCELLED"}
        return res


def menu_func_import(self, context):
    self.layout.operator(ImportNIF.bl_idname, text="Nif file with Nifly (.nif)")
def menu_func_export(self, context):
    self.layout.operator(ExportNIF.bl_idname, text="Nif file with Nifly (.nif)")

def register():
    bpy.utils.register_class(ImportNIF)
    bpy.utils.register_class(ExportNIF)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(ImportNIF)
    bpy.utils.unregister_class(ExportNIF)

def run_tests():
    print("######################### TESTING ##########################")

    TEST_ALL = True
    TEST_EXPORT = False
    TEST_IMPORT_ARMATURE = False
    TEST_EXPORT_WEIGHTS = False
    TEST_UNIT = False
    TEST_IMP_EXP_SKY = False
    TEST_IMP_EXP_FO4 = False
    TEST_ROUND_TRIP = False
    TEST_UV_SPLIT = False
    TEST_CUSTOM_BONES = False
    TEST_PARENT = True

    if TEST_ALL or TEST_UNIT:
        # Lower-level tests of individual routines for bug hunting
        print("--get_weights_by_bone converts from weights-by-vertex")
        group_names = ("a", "b", "c", "d")
        wbv = [{"a": 0.1, "c": 0.5}, {"b": 0.2}, {"d": 0.0, "b": 0.6}, {"a": 0.4}]
        wbb = get_weights_by_bone(wbv)
        assert wbb["a"] == [(0, 0.1), (3, 0.4)], "ERROR: get_weights_by_bone failed"
        assert wbb["b"] == [(1, 0.2), (2, 0.6)], "ERROR: get_weights_by_bone failed"
        assert wbb["c"] == [(0, 0.5)], "ERROR: get_weights_by_bone failed"

    if TEST_ALL or TEST_EXPORT:
        print("## Can export the basic cube")
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        filepath = os.path.join(pynifly_dev_path, r"tests\Out\testSkyrim01.nif")
        f = NifFile()
        f.initialize("SKYRIM", filepath)
        export_shape(f, cube)
        f.save()

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        f = NifFile(filepath)
        sourceGame = f.game
        assert f.game == "SKYRIM", "ERROR: Wrong game found"

        import_file(f)

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, "ERROR: Cube doesn't have right number of verts"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, "ERROR: Cube doesn't have a UV locations"
        assert len(new_cube.data.polygons) == 12, "ERROR: Cube doesn't have a UV locations"
        # bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can do the same for FO4")

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.selected_objects[0]
        cube.name = "TestCube"
        filepath = os.path.join(pynifly_dev_path, r"tests\Out\testFO401.nif")
        f = NifFile()
        f.initialize("FO4", filepath)
        export_shape(f, cube)
        f.save()

        assert os.path.exists(filepath), "ERROR: Didn't create file"
        bpy.data.objects.remove(cube, do_unlink=True)

        print("## And can read it in again")
        f = NifFile(filepath)
        sourceGame = f.game
        assert f.game == "FO4", "ERROR: Wrong game found"

        import_file(f)

        new_cube = bpy.context.selected_objects[0]
        assert 'Cube' in new_cube.name, "ERROR: cube not named correctly"
        assert len(new_cube.data.vertices) == 14, "ERROR: Cube doesn't have right number of verts"
        assert len(new_cube.data.uv_layers) == 1, "ERROR: Cube doesn't have a UV layer"
        assert len(new_cube.data.uv_layers[0].data) == 36, "ERROR: Cube doesn't have a UV locations"
        assert len(new_cube.data.polygons) == 12, "ERROR: Cube doesn't have a UV locations"
        # bpy.data.objects.remove(cube, do_unlink=True)

    if TEST_ALL or TEST_IMPORT_ARMATURE:
        print("## Can import a Skyrim head with armature")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        filepath = os.path.join(pynifly_dev_path, "tests\Skyrim\malehead.nif")
        f = NifFile(filepath)
        import_file(f)
        male_head = bpy.context.selected_objects[0]
        assert round(male_head.location.z, 0) == 120, "ERROR: Object not elevated to position"
        assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"
        
        print("## Can import a FO4 head  with armature")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        filepath = os.path.join(pynifly_dev_path, "tests\FO4\BaseMaleHead.nif")
        f = NifFile(filepath)
        import_file(f)
        male_head = bpy.data.objects["BaseMaleHead:0"]
        assert int(male_head.location.z) == 120, f"ERROR: Object {male_head.name} at {male_head.location.z}, not elevated to position"
        assert male_head.parent.type == "ARMATURE", "ERROR: Didn't parent to armature"

    if TEST_ALL or TEST_IMP_EXP_SKY:
        print("### Can read the armor nif and spit it back out (no blender shape)")

        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        nif = NifFile(testfile)
        assert "Armor" in nif.getAllShapeNames(), "ERROR: Didn't read armor"

        the_armor = nif.shape_dict["Armor"]
        assert len(the_armor.verts) == 2115, "ERROR: Wrong number of verts"
        assert (len(the_armor.tris) == 3195), "ERROR: Wrong number of tris"

        outfile = os.path.join(pynifly_dev_path, "tests/Out/TestSkinnedFromPy02.nif")
        if os.path.exists(outfile):
            os.remove(outfile)
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
            
    if TEST_ALL or TEST_IMP_EXP_FO4:
        print("### TEST_IMP_EXP_FO4: Can read the body nif and spit it back out (no blender shape)")

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
            

    if TEST_ALL or TEST_EXPORT_WEIGHTS:
        print("TEST_EXPORT_WEIGHTS: Import and export with weights")

        # Import body and armor
        f_in = NifFile(os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif"))
        import_file(f_in)
        the_armor = bpy.data.objects["Armor"]
        the_body = bpy.data.objects["MaleBody"]
        assert 'NPC Foot.L' in the_armor.vertex_groups, f"ERROR: Left foot is in the groups: {the_armor.vertex_groups}"
        
        # Export armor
        filepath_armor = os.path.join(pynifly_dev_path, "tests/out/testArmorSkyrim02.nif")
        if os.path.exists(filepath_armor):
            os.remove(filepath_armor)
        f_out = NifFile()
        f_out.initialize("SKYRIM", filepath_armor)
        export_shape(f_out, the_armor)
        f_out.save()
        assert os.path.exists(filepath_armor), "ERROR: File not created"

        # Check armor
        ftest = NifFile(filepath_armor)
        assert ftest.shapes[0].name[0:5] == "Armor", "ERROR: Armor not read"
        gts = ftest.shapes[0].global_to_skin
        assert int(gts.translation[2]) == -120, "ERROR: Armor not offset"

        # Write armor to FO4 (wrong skeleton but whatevs, just see that it doesn't crash)
        filepath_armor_fo = os.path.join(pynifly_dev_path, r"tests\Out\testArmorFO02.nif")
        if os.path.exists(filepath_armor_fo):
            os.remove(filepath_armor_fo)
        f_out = NifFile()
        f_out.initialize("FO4", filepath_armor_fo)
        export_shape(f_out, the_armor)
        f_out.save()
        assert os.path.exists(filepath_armor_fo), f"ERROR: File {filepath_armor_fo} not created"

        # Write body 
        filepath_body = os.path.join(pynifly_dev_path, r"tests\Out\testBodySkyrim02.nif")
        body_out = NifFile()
        if os.path.exists(filepath_body):
            os.remove(filepath_body)
        body_out.initialize("SKYRIM", filepath_body)
        export_shape(body_out, the_body)
        body_out.save()
        assert os.path.exists(filepath_body), f"ERROR: File {filepath_body} not created"
        # Should do some checking here

    if TEST_ALL or TEST_ROUND_TRIP:
        print("### Can do the full round trip: nif -> blender -> nif -> blender")

        print("..Importing original file")
        testfile = os.path.join(pynifly_dev_path, "tests/Skyrim/test.nif")
        nif = NifFile(testfile)
        import_file(nif)

        armor1 = None
        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor1 = obj

        assert int(armor1.location.z) == 120, "ERROR: Armor moved above origin by 120 to skinned position"
        maxz = max([v.co.z for v in armor1.data.vertices])
        minz = min([v.co.z for v in armor1.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices are positioned below origin"

        print("..Exporting  to test file")
        outfile1 = os.path.join(pynifly_dev_path, "tests/Out/testSkyrim03.nif")
        if os.path.exists(outfile1):
            os.remove(outfile1)
        nif1 = NifFile()
        nif1.initialize("SKYRIM", outfile1)
        export_shape(nif1, armor1)
        nif1.save()
        assert os.path.exists(outfile1), "ERROR: Created output file"

        print("..Re-importing exported file")
        nif2 = NifFile(outfile1)
        import_file(nif2)

        armor2 = None
        for obj in bpy.context.selected_objects:
            if "Armor" in obj.name:
                armor2 = obj

        assert int(armor2.location.z) == 120, "ERROR: Exported armor is re-imported with same position"
        maxz = max([v.co.z for v in armor2.data.vertices])
        minz = min([v.co.z for v in armor2.data.vertices])
        assert maxz < 0 and minz > -130, "Error: Vertices from exported armor are positioned below origin"

    if TEST_ALL or TEST_UV_SPLIT:
        print("### Can split UVs properly")

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
        bpy.context.collection.objects.link(new_object)

        filepath = os.path.join(pynifly_dev_path, "tests/Out/testUV01.nif")
        nif_out = NifFile()
        nif_out.initialize("SKYRIM", filepath)
        export_shape(nif_out, new_object)
        nif_out.save()

        nif_in = NifFile(filepath)
        plane = nif_in.shapes[0]
        assert len(plane.verts) == 8, "Error: Exported nif doesn't have correct verts"
        assert len(plane.uvs) == 8, "Error: Exported nif doesn't have correct UV"
        assert plane.verts[5] == plane.verts[7], "Error: Split vert at different locations"
        assert plane.uvs[5] != plane.uvs[7], "Error: Split vert has different UV locations"

    if TEST_ALL or TEST_CUSTOM_BONES:
        print('### Can handle custom bones correctly')

        testfile = os.path.join(pynifly_dev_path, r"tests\FO4\VulpineInariTailPhysics.nif")
        nif_in = NifFile(testfile)
        bone_xform = nif_in.nodes['Bone_Cloth_H_003'].xform_to_global
        import_file(nif_in)

        outfile = os.path.join(pynifly_dev_path, r"tests\Out\Tail01.nif")
        nif_out = NifFile()
        nif_out.initialize('FO4', outfile)
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                export_shape(nif_out, obj)
        nif_out.save()

        test_in = NifFile(outfile)
        new_xform = test_in.nodes['Bone_Cloth_H_003'].xform_to_global
        assert bone_xform == new_xform, \
            f"Error: Bone transform should not change. Expected\n {bone_xform}, found\n {new_xform}"

    if TEST_ALL or TEST_PARENT:
        print('### Maintain armature structure')

        # Can intuit structure if it's not in the file
        bpy.ops.object.select_all(action='DESELECT')
        testfile = os.path.join(pynifly_dev_path, r"tests\Skyrim\test.nif")
        nif = NifFile(testfile)
        import_file(nif)
        for obj in bpy.context.selected_objects:
            if obj.name.startswith("Scene Root"):
                 assert obj.data.bones['NPC Hand.R'].parent.name == 'NPC Forearm.R', "Error: Should find forearm as parent"
                 print(f"Found parent to hand: {obj.data.bones['NPC Hand.R'].parent.name}")

        # This nif weights to skin bones and parents to not-skin bones so the test doesn't work
        ## Can read structure if it comes from file
        #bpy.ops.object.select_all(action='DESELECT')
        #testfile = os.path.join(pynifly_dev_path, r"tests\FO4\bear_tshirt_turtleneck.nif")
        #nif = NifFile(testfile)
        #import_file(nif)
        #for obj in bpy.context.selected_objects:
        #    if obj.name.startswith("Scene Root"):
        #        assert 'Arm_Hand.R' in obj.data.bones, "Error: Hand should be in armature"
        #        assert obj.data.bones['Arm_Hand.R'].parent.name == 'Arm_ForeArm3_skin.R', "Error: Should find forearm as parent"
        #        print(f"Found parent to hand: {obj.data.bones['Arm_Hand.R'].parent.name}")


    print("######################### TESTS DONE ##########################")


if __name__ == "__main__":
    try:
        do_run_tests = False
        if RUN_TESTS == True:
            do_run_tests = True
    except:
        do_run_tests == False
        
    if not do_run_tests:
        register()
    else:
        try:
            run_tests()
        except:
            traceback.print_exc()