"""Python Tests for running in Blender

    This file is for older, standard regression tests.
"""

from test_tools import *
from pynifly import *

def run_tests(dev_path, NifExporter, NifImporter):
    TEST_EXPORT = True
    TEST_IMPORT_ARMATURE = True


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

