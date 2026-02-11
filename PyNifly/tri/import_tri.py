"""
.tri file import. Discovers whether the file is a TRIP file or a standard TRI file and
imports accordingly.
"""
from pathlib import Path
import logging
from typing import BinaryIO
import bpy
from bpy_extras.io_utils import ImportHelper
from .. import blender_defs as BD
from ..pyn.niflytools import gameSkeletons
from .. import bl_info
from .trifile import TriFile, is_tri
from .tripfile import TripFile, is_trip

log = logging.getLogger("pynifly")


def open_tri(filepath:Path):
    """
    Open the given file and determine whether it is a TRIP file or a standard TRI file.
    Return either a TriFile or a TripFile.
    """
    with open(str(filepath),'rb') as file:
        if is_tri(file):
            tri = TriFile.from_file(file)
            return tri
        elif is_trip(file):
            trip = TripFile.from_file(file)
            return trip


def read_morph(obj, base_verts, game_dict, game_morph_name, morph_verts, is_rel):
    """
    Read a single morph and create a shape key for it.
    """
    if game_dict and game_morph_name in game_dict.morph_dic_blender:
        morph_name = game_dict.morph_dic_blender[game_morph_name]
    else:
        morph_name = game_morph_name

    mesh = obj.data
    if morph_name not in mesh.shape_keys.key_blocks:
        newsk = obj.shape_key_add()
        newsk.name = morph_name
        newsk.value = 0

        obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
            #This is a pointer, not a copy
        mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data[0:len(morph_verts)]
        if is_rel:
            # We may be applying the morphs to a different shape than the one stored in 
            # the tri file. But the morphs in the tri file are absolute locations, as are 
            # shape key locations. So we need to calculate the offset in the tri and apply that 
            # to our shape keys.
            for key_vert, morph_vert, base_vert in zip(mesh_key_verts, morph_verts, base_verts):
                key_vert.co[0] += morph_vert[0] - base_vert[0]
                key_vert.co[1] += morph_vert[1] - base_vert[1]
                key_vert.co[2] += morph_vert[2] - base_vert[2]
        else:
            # These morphs hold relative locations.
            for key_vert, morph_vert, base_vert in zip(mesh_key_verts, morph_verts, base_verts):
                key_vert.co[0] += morph_vert[0] - base_vert[0]
                key_vert.co[1] += morph_vert[1] - base_vert[1]
                key_vert.co[2] += morph_vert[2] - base_vert[2]
        
        mesh.update()


def create_shape_keys(obj, tri: TriFile):
    """
    Adds the shape keys in tri to obj. Obj may have more verts than tri.
    """
    mesh = obj.data
    if mesh.shape_keys is None:
        newsk = obj.shape_key_add()
        mesh.shape_keys.use_relative=True
        newsk.name = "Basis"
        mesh.update()

    dict = None
    obj_arma = [m.object for m in obj.modifiers if m.type == 'ARMATURE']
    if obj_arma:
        g = BD.best_game_fit(obj_arma[0].data.bones)
        if g != "":
            dict = gameSkeletons[g]

    for game_morph_name, morph_verts in sorted(tri.morphs.items()):
        read_morph(obj, tri.vertices, dict, game_morph_name, morph_verts, True)
    for game_morph_name, morph_verts in sorted(tri.modmorphs.items()):
        read_morph(obj, tri.vertices, dict, game_morph_name, morph_verts, False)


def import_tri(tri:TriFile, cobj, allow_extra_verts=True):
    """
    Import the tris from filepath into cobj
    If cobj is None or if the verts don't match, create a new object
    allow_extra_verts: if True, allow the obj mesh to have more verts than the tri.
    """
    new_object = None

    # Check whether selected object should receive shape keys
    if (cobj and cobj.type == "MESH" 
        and (len(cobj.data.vertices) == len(tri.vertices)
             or (len(cobj.data.vertices) > len(tri.vertices) and allow_extra_verts))):
        new_object = cobj
        new_mesh = new_object.data
        log.info(f"Verts match, loading tri into existing shape {new_object.name}")

    if new_object is None:
        new_mesh = bpy.data.meshes.new(Path(tri.filepath).stem)
        new_mesh.from_pydata(tri.vertices, [], tri.faces)
        new_object = bpy.data.objects.new(new_mesh.name, new_mesh)

        for f in new_mesh.polygons:
            f.use_smooth = True

        new_mesh.update(calc_edges=True, calc_edges_loose=True)
        new_mesh.validate(verbose=True)

        if tri.import_uv:
            BD.mesh_create_uv(new_mesh, tri.uv_pos)
   
        bpy.context.scene.collection.objects.link(new_object)
        BD.ObjectSelect([new_object])

    create_shape_keys(new_object, tri)
    new_object.active_shape_key_index = 0

    return new_object


def create_trip_shape_keys(obj, trip:TripFile):
    """Adds the shape keys in trip to obj."""
    mesh = obj.data
    verts = mesh.vertices

    if mesh.shape_keys is None or "Basis" not in mesh.shape_keys.key_blocks:
        newsk = obj.shape_key_add()
        newsk.name = "Basis"

    offsetmorphs = trip.shapes[obj.name]
    for morph_name, morph_verts in sorted(offsetmorphs.items()):
        newsk = obj.shape_key_add()
        newsk.name = ">" + morph_name
        newsk.value = 0

        obj.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
        #This is a pointer, not a copy
        mesh_key_verts = mesh.shape_keys.key_blocks[obj.active_shape_key_index].data
        for vert_index, offsets in morph_verts:
            for i in range(3):
                mesh_key_verts[vert_index].co[i] = verts[vert_index].co[i] + offsets[i]
        
        mesh.update()

    obj.active_shape_key_index = 0


def import_trip(trip:TripFile, target_objs):
    """
    Import a BS Tri file. 
    These TRI files do not have full shape data so they have to be matched to one of the 
    objects in target_objs.
    """
    for shapename, offsetmorphs in trip.shapes.items():
        matchlist = [o for o in target_objs if o.name == shapename]
        if len(matchlist) == 0:
            log.warning(f"BS Tri file shape does not match any selected object: {shapename}")
        else:
            create_trip_shape_keys(matchlist[0], trip)


class ImportTRI(bpy.types.Operator, ImportHelper):
    """Load a TRI File"""
    bl_idname = "import_scene.pyniflytri"
    bl_label = "Import TRI (Nifly)"
    bl_options = {'PRESET', 'UNDO'}

    do_apply_active: bpy.props.BoolProperty(
        name="Apply to active object",
        description="Apply tri to active object if possible.",
        default=True) # type: ignore

    filename_ext = ".tri"
    filter_glob: bpy.props.StringProperty(
        default="*.tri",
        options={'HIDDEN'},
    ) # type: ignore

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.do_apply_active = (
            bpy.context.object is not None and
            bpy.context.object.select_get() and
            bpy.context.object.type == 'MESH'
        )

    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_import_path_tri:
            self.filepath = str(Path(context.window_manager.pynifly_last_import_path_tri) 
                                / Path(self.filepath))
        return super().invoke(context, event)

    def execute(self, context):
        self.log_handler = BD.LogHandler()
        self.log_handler.start(bl_info, "IMPORT", "TRI")
        self.status = {'FINISHED'}
        self.file_path = Path(self.filepath)

        try:
            tf = open_tri(self.file_path)
            if tf and isinstance(tf, TriFile):
                cobj = bpy.context.object
                obj = import_tri(tf, 
                                (cobj if self.do_apply_active else None), 
                                allow_extra_verts=self.do_apply_active)
                if obj == cobj:
                    log.info(f"Imported .tri file into {cobj.name}")
                else:
                    log.info("Imported .tri file as new object")
            else:
                import_trip(tf, context.selected_objects)
                log.info("Imported Bodyslide .tri file containing {tf.shapes.keys()} shapes" 
                            + f" into selected objects {[o.name for o in context.selected_objects]}")

            try:   
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        ctx = bpy.context.copy()
                        ctx['area'] = area
                        ctx['region'] = area.regions[-1]
                        bpy.ops.view3d.view_selected(ctx)
            except:
                pass # log exception?

            self.log_handler.finish("IMPORT TRI", self.filepath)

        except:
            self.log_handler.log.exception("Import of tri failed")
            self.report({"ERROR"}, "Import of tri failed, see console window for details")
            self.status = {'CANCELLED'}

        finally:
            self.log_handler.finish("IMPORT TRI", self.filepath)

        # Save the directory path for next time
        wm = context.window_manager
        wm.pynifly_last_import_path_tri = str(self.file_path.parent)

        return self.status.intersection({'FINISHED', 'CANCELLED'})
