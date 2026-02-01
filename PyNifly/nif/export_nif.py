"""
Export Blender meshes to NIF files.
"""

import os
from contextlib import suppress
from mathutils import Matrix, Vector, Euler, Color
import codecs
import logging
import json
from pathlib import Path
import bpy
from bpy_extras.io_utils import ExportHelper
from ..tri.trifile import TriFile
from ..tri.tripfile import TripFile
from ..pyn.niflytools import NearEqual, MatNearEqual, mesh_split_by_uv, fo4FaceDict
from ..pyn.nifdefs import (BSXFlags, NiAVFlags, VertexFlags)
from .. import blender_defs as BD
from ..blender_defs import ReprObject, ReprObjectCollection, ObjectSelect, ObjectActive
from ..pyn import pynifly
from .. import bl_info
from . import shader_io 
from . import controller 
from . import collision 
from . import connectpoint 

log = logging.getLogger("pynifly")

def clean_filename(fn):
    s = fn.strip()
    if s.endswith(":ROOT"): s = s[0:-5]
    return "".join(c for c in s if (c.isalnum() or c in "._- "))

def select_all_faces(mesh):
    """ Make sure all mesh elements are visible and all faces are selected """
    bpy.ops.object.mode_set(mode = 'OBJECT') # Have to be in object mode

    for v in mesh.vertices:
        v.hide = False
    for e in mesh.edges:
        e.hide = False
    for p in mesh.polygons:
        p.hide = False
        p.select = True


def check_partitions(vi1, vi2, vi3, weights):
    """ Chcek whether the = 3 verts (specified by index) all have the same partitions 
        weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts
       """
    p1 = set([k for k in weights[vi1].keys() if is_partition(k)])
    p2 = set([k for k in weights[vi2].keys() if is_partition(k)])
    p3 = set([k for k in weights[vi3].keys() if is_partition(k)])
    return len(p1.intersection(p2, p3)) > 0


def trim_to_four(weights, arma):
    """ Trim to the 4 heaviest weights in the armature
        weights = [(group_name: weight), ...] """
    if arma:
        lst = filter(lambda p: p[0] in arma.data.bones, weights)
        notlst = filter(lambda p: p[0] not in arma.data.bones, weights)
        sd = sorted(lst, reverse=True, key=lambda item: item[1])[0:4]
        sd.extend(notlst)
        return dict(sd)
    else:
        return dict(weights)


def has_uniform_scale(obj):
    """ Determine whether an object has uniform scale """
    return NearEqual(obj.scale[0], obj.scale[1]) and NearEqual(obj.scale[1], obj.scale[2])


def extract_vert_info(obj, mesh, arma, target_key='', scale_factor=1.0):
    """Returns 3 lists of equal length with one entry each for each vertex
    *   verts = [(x, y, z)... ] - base or as modified by target-key if provided
    *   weights = [{group-name: weight}... ] - 1:1 with verts list
    *   dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
            shape-key is the blender name.
        """
    weights = []
    morphdict = {}
    msk = mesh.shape_keys
    error_groups = set()

    sf = Vector((1,1,1))
    if not has_uniform_scale(obj):
        # Apply non-uniform scale to verts directly
        sf = obj.scale

    if target_key != '' and msk and target_key in msk.key_blocks.keys():
        verts = [(v.co * sf / scale_factor)[:] for v in msk.key_blocks[target_key].data]
    else:
        verts = [(v.co * sf / scale_factor)[:] for v in mesh.vertices]

    for i, v in enumerate(mesh.vertices):
        vert_weights = []
        for vg in v.groups:
            try:
                vgn = obj.vertex_groups[vg.group].name
                vert_weights.append([vgn, vg.weight])
            except:
                if vg.group not in error_groups:
                    log.error(f"Object {obj.name} vertex #{v.index} (and possibly others) references invalid group #{vg.group}")
                error_groups.add(vg.group)
        
        weights.append(trim_to_four(vert_weights, arma))
    
    if msk: 
        # We return shape key locations for all interesting shape keys.
        # target_key specifies the base shape for this export. The other shape keys are
        # relative to "basis", not target_key. So if target_key is provided, we need to
        # adjust.
        if target_key == '': target_key = 0

        for sk in msk.key_blocks:    
            morphdict[sk.name] = [
                ((vkey.co + (vtarg.co - vbase.co))*sf)[:] 
                for vkey, vtarg, vbase 
                in zip(sk.data, msk.key_blocks[target_key].data, sk.relative_key.data)]

    return verts, weights, morphdict


def tag_unweighted(obj, bones):
    """ Find and return verts that are not weighted to any of the given bones 
        result = (v_index, ...) list of indices into the vertex list
    """
    unweighted_verts = []
    for v in obj.data.vertices:
        maxweight = 0.0
        if len(v.groups) > 0:
            maxweight = max([g.weight for g in v.groups])
        if maxweight < 0.0001:
            unweighted_verts.append(v.index)
    return unweighted_verts


def create_group_from_verts(obj, name, verts):
    """ Create a vertex group from the list of vertex indices.
    Use the existing group if any """
    if name in obj.vertex_groups.keys():
        g = obj.vertex_groups[name]
    else:
        g = obj.vertex_groups.new(name=name)
    g.add(verts, 1.0, 'ADD')


def expected_game(nif, bonelist):
    """ Check whether the nif's game is the best match for the given bonelist """
    matchgame = BD.best_game_fit(bonelist)
    return matchgame == "" or matchgame == nif.game or \
        (matchgame in ['SKYRIM', 'SKYRIMSE'] and nif.game in ['SKYRIM', 'SKYRIMSE'])


def is_partition(name):
    """ Check whether <name> is a valid partition or segment name """
    if pynifly.SkyPartition.name_match(name) >= 0:
        return True

    if pynifly.FO4Segment.name_match(name) >= 0:
        return True

    parent_name, subseg_id, material = pynifly.FO4Subsegment.name_match(name)
    if parent_name:
        return True

    return False


def partitions_from_vert_groups(obj, game):
    """ Return dictionary of Partition objects for all vertex groups that match the partition 
        name pattern. These are all partition objects including subsegments.
    """
    val = {}
    if obj.vertex_groups:
        vg_sorted = sorted([g.name for g in obj.vertex_groups])
        for nm in vg_sorted:
            vg = obj.vertex_groups[nm]
            skyid = -1
            if game in ['SKYRIM', 'SKYRIMSE']:
                skyid = pynifly.SkyPartition.name_match(vg.name)
            if skyid >= 0:
                val[vg.name] = pynifly.SkyPartition(part_id=skyid, flags=0, name=vg.name)
            elif game in ['FO4', 'FO76', 'FO3' 'FONV']:
                segid = pynifly.FO4Segment.name_match(vg.name)
                if segid >= 0:
                    val[vg.name] = pynifly.FO4Segment(part_id=len(val), index=segid, name=vg.name)
                else:
                    # Check if this is a subsegment. All segs sort before their subsegs, 
                    # so it will already have been created if it exists separately
                    parent_name, subseg_id, material = pynifly.FO4Subsegment.name_match(vg.name)
                    if parent_name:
                        if not parent_name in val:
                            # Create parent segments if not there
                            val[parent_name] = pynifly.FO4Segment(
                                part_id=len(val), 
                                index=pynifly.FO4Segment.name_match(parent_name), 
                                name=parent_name)
                        p = val[parent_name]
                        val[vg.name] = pynifly.FO4Subsegment(len(val), subseg_id, material, p, name=vg.name)
    
    return val


def all_vertex_groups(weightdict):
    """ Return the set of group names that have non-zero weights """
    val = set()
    for g, w in weightdict.items():
        if w > 0.0001:
            val.add(g)
    return val


def get_loop_color(mesh, loopindex, cm, am):
    """ Return the color of the vertex-in-loop at given loop index using
        cm = color map to use
        am = alpha map to use """
    vc = mesh.vertex_colors
    alpha = 1.0
    color = (1.0, 1.0, 1.0)
    if cm:
        color = cm[loopindex].color
    if am:
        acolor = am[loopindex].color
        alpha = (acolor[0] + acolor[1] + acolor[2])/3

    return (color[0], color[1], color[2], alpha)
    

def mesh_from_key(editmesh, verts, target_key):
    faces = []
    for p in editmesh.polygons:
        faces.append([editmesh.loops[lpi].vertex_index for lpi in p.loop_indices])
    newverts = [v.co[:] for v in editmesh.shape_keys.key_blocks[target_key].data]
    newmesh = bpy.data.meshes.new(editmesh.name)
    newmesh.from_pydata(newverts, [], faces)
    return newmesh


def get_common_shapes(obj_list) -> set:
    """Return the shape keys found in any of the given objects """
    res = None
    for obj in obj_list:
        o_shapes = set()
        if obj.data.shape_keys:
            o_shapes = set(obj.data.shape_keys.key_blocks.keys())
        if res:
            res = res.union(o_shapes)
        else:
            res = o_shapes
    if res:
        res = list(res)
    return res


def get_with_uscore(str_list):
    if str_list:
        return list(filter((lambda x: x[0] == '_'), str_list))
    else:
        return []


class NifExporter:
    """ Object that handles the export process independent of Blender's export class """
    def __init__(self, filepath, game, export_flags=BD.RENAME_BONES_DEF, chargen="chargen", scale=1.0):
        self.filepath = filepath
        self.game = game
        self.nif = None
        self.trip = None
        self.warnings = set()
        self.armature = None
        self.facebones = None
        self.do_rename_bones = BD.RENAME_BONES_DEF
        self.rename_bones_nift = BD.RENAME_BONES_NIFT_DEF
        self.preserve_hierarchy = BD.PRESERVE_HIERARCHY_DEF
        self.write_bodytri = BD.WRITE_BODYTRI_DEF
        self.export_pose = BD.EXPORT_POSE_DEF
        self.export_modifiers = BD.EXPORT_MODIFIERS_DEF
        self.export_animations = BD.EXPORT_ANIMATIONS_DEF
        self.export_colors = BD.EXPORT_COLORS_DEF
        self.active_obj = None
        self.scale = scale
        self.root_object = None
        self.export_xf = Matrix.Identity(4)

        # Objects that are to be written out
        self.objects = [] # Ordered list of objects to write--first my have root node info
        self.bg_data = set()
        self.str_data = set()
        self.cloth_data = set()
        self.grouping_nodes = set()
        self.bsx_flag = None
        self.bone_lod = None
        self.bound = None
        self.inv_marker = None
        self.furniture_markers = set()
        self.connect_points = connectpoint.ConnectPointCollection()
        self.trippath = ''
        self.chargen_ext = chargen
        self.writtenbones = {}
        self.shape_bones = {}
        
        # Shape keys that start with underscore trigger a separate file export
        # for each shape key
        self.file_keys = []  
        self.objs_unweighted = set()
        self.objs_scale = set()
        self.objs_mult_part = set()
        self.objs_no_part = set()
        self.arma_game = []
        self.bodytri_written = False
        self.objs_written = ReprObjectCollection()

        self.message_log = []

    def __str__(self):
        flags = []
        if self.do_rename_bones: flags.append("RENAME_BONES")
        if self.rename_bones_nift: flags.append("RENAME_BONES_NIFT")
        if self.preserve_hierarchy: flags.append("PRESERVE_HIERARCHY")
        if self.write_bodytri: flags.append("WRITE_BODYTRI")
        if self.export_pose: flags.append("EXPORT_POSE")
        if self.export_modifiers: flags.append("EXPORT_MODIFIERS")
        if self.export_animations: flags.append("EXPORT_ANIMATIONS")
        if self.export_colors: flags.append("EXPORT_COLORS")
        return f"""
        Exporting objects: {[o.name for o in self.objects]}
            flags: {'|'.join(flags)}
            string data: {self.str_data}
            BG data: {self.bg_data}
            cloth data: {self.cloth_data}
            armature: {self.armature.name if self.armature else 'None'}
            facebones: {self.facebones.name if self.facebones else 'None'}
            connect points: {[x.name for x in self.connect_points.parents]}, {[x.names for x in self.connect_points.child]}
            orientation: {self.export_xf.to_euler()}
            scale factor: {round(self.export_scale, 4)}
            shapes: {self.file_keys}
            to file: {self.filepath}
        """

    def warn(self, msg, tags=[]):
        """
        Report a warning-level error message to the log, and capture any tags
        for later reporting.
        """
        log.warning(msg)

    @property
    def export_scale(self):
        """Return the inverse of the scale factor on the export transform. Returning
        the inverse because all the scale factors are expected to match the import.
        """
        return 1/self.export_xf.to_scale()[0]
    
    def nif_name(self, blender_name):
        if self.do_rename_bones or self.rename_bones_nift:
            return self.nif.nif_name(blender_name)
        else:
            return blender_name

    def unique_name(self, obj):
        """
        Return a unique node name for the Blender object. Use the root of the Blender name
        if possible, because that might match to a name in a trip file. Otherwise use the
        full Blender name, and if that fails make a unique name.
        """
        names = self.nif.getAllShapeNames()
        simplename = BD.nonunique_name(obj)
        if simplename not in names: return simplename
        if obj.name not in names: return obj.name
        for i in range(0, 100):
            n = simplename + "-" + f"{i:03}"
            if n not in names: return n
        return obj.name

    def export_shape_data(self, robj:ReprObject):
        """ Export a shape's extra data """
        edlist = []
        strlist = []
        for ch in robj.blender_obj.children:
             if 'NiStringExtraData_Name' in ch:
                strlist.append( (ch['NiStringExtraData_Name'], ch['NiStringExtraData_Value']) )
                self.objs_written.add(ReprObject(ch, None)) # [ch.name] = shape
             if 'BSBehaviorGraphExtraData_Name' in ch:
                edlist.append( (ch['BSBehaviorGraphExtraData_Name'], 
                               ch['BSBehaviorGraphExtraData_Value']) )
                self.objs_written.add(ReprObject(ch, None)) # [ch.name] = shape
        
        if len(strlist) > 0:
            robj.nifnode.string_data = strlist
        if len(edlist) > 0:
            robj.nifnode.behavior_graph_data = edlist


    def add_armature(self, arma):
        """Add an armature to the export"""
        facebones_arma = (self.game in ['FO4', 'FO76']) and (BD.is_facebones(arma.data.bones.keys()))
        if facebones_arma and self.facebones is None:
            self.facebones = arma
        if (not facebones_arma) and (self.armature is None):
            self.armature = arma 


    def add_object(self, obj):
        """
        Adds the given object to the objects to export. Object may be mesh, armature,
        or anything else. 
        
        * If an armature is selected, all child objects are exported 
        * If a skinned mesh is selected, all armatures referenced in armature modifiers
          are considered for export.
        """
        if obj in self.objects or obj in self.grouping_nodes: return

        if obj.type == 'ARMATURE':
            self.add_armature(obj)
            for c in obj.children:
                self.add_object(c)

        elif obj.type == 'MESH':
            if not obj.name.startswith("BSBound:"):
                # Export the mesh, but use its parent and use any armature modifiers
                self.objects.append(obj)
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object:
                        # Don't add any of the armature's other children unless they were
                        # independently selected.
                        self.add_armature(mod.object)
            elif obj.name.startswith("BSBound:"):
                self.bound = obj

        elif obj.type == 'CAMERA':
            self.inv_marker = obj

        elif obj.type == 'EMPTY':
            if 'BSBehaviorGraphExtraData_Name' in obj.keys():
                self.bg_data.add(obj)

            elif 'NiStringExtraData_Name' in obj.keys() and obj.parent \
                    and obj.parent.get('pynRoot', False):
                self.str_data.add(obj)

            elif 'BSClothExtraData_Name' in obj.keys():
                self.cloth_data.add(obj)

            elif 'BSXFlags_Name' in obj.keys():
                self.bsx_flag = obj

            elif 'pynBoneLOD' in obj.keys():
                self.bone_lod = obj

            elif obj.name.startswith("BSFurnitureMarkerNode"):
                self.furniture_markers.add(obj)

            elif (obj.type == 'EMPTY') and (not connectpoint.is_connectpoint(obj)):
                self.grouping_nodes.add(obj)
                for c in obj.children:
                    if not c.hide_get(): 
                        self.add_object(c)

        if connectpoint.is_connectpoint(obj):
            self.connect_points.add(obj)


    def set_objects(self, objects:list):
        """ 
        Set the objects to export from the given list of objects 
        """
        for x in objects:
            if not x.hide_get():
                self.add_object(x)
                if "pynRoot" in x:
                    self.root_object = x
        self.connect_points.add_all(objects)
        self.file_keys = get_with_uscore(get_common_shapes(self.objects))


    # --------- DO THE EXPORT ---------

    def export_tris(self, robj:ReprObject, verts, tris, uvs, morphdict):
        """ Export a tri file to go along with the given nif file, if there are shape keys 
            and it's not a faceBones nif.
            dict = {shape-key: [verts...], ...} - verts list for each shape which is valid for export.
        """
        result = {'FINISHED'}

        obj = robj.blender_obj
        if obj.data.shape_keys is None or len(morphdict) == 0:
            return result

        fpath = os.path.split(self.nif.filepath)
        fname = os.path.splitext(fpath[1])

        if fname[0].endswith('_faceBones'):
            return result

        fname_tri = os.path.join(fpath[0], fname[0] + ".tri")
        fname_chargen = os.path.join(fpath[0], fname[0] + self.chargen_ext + ".tri")
        if self.chargen_ext != BD.CHARGEN_EXT_DEF: obj['PYN_CHARGEN_EXT'] = self.chargen_ext 

        # Don't export anything that starts with an underscore or asterisk
        objkeys = obj.data.shape_keys.key_blocks.keys()
        export_keys = set(filter((lambda n: n[0] not in ('_', '*') and n != 'Basis'), objkeys))
        expression_morphs = self.nif.dict.expression_filter(export_keys)
        trip_morphs = set(filter((lambda n: n[0] == '>'), objkeys))
        # Leftovers are chargen candidates
        leftover_morphs = export_keys.difference(expression_morphs).difference(trip_morphs)
        chargen_morphs = self.nif.dict.chargen_filter(leftover_morphs)

        if len(expression_morphs) > 0 and len(trip_morphs) > 0:
            log.warning(f"Found both expression morphs and BS tri morphs in shape {obj.name}. May be an error.")
            result = {'WARNING'}

        if len(expression_morphs) > 0:
            tri = TriFile()
            tri.vertices = verts
            tri.faces = tris
            tri.uv_pos = uvs
            tri.face_uvs = tris # (because 1:1 with verts)
            for m in expression_morphs:
                if m in self.nif.dict.morph_dic_game:
                    triname = self.nif.dict.morph_dic_game[m]
                else:
                    triname = m
                if m in morphdict:
                    tri.morphs[triname] = morphdict[m]
    
            log.info(f"Generating tri file '{fname_tri}'")
            tri.write(fname_tri) # Only expression morphs to write at this point

        if len(chargen_morphs) > 0:
            tri = TriFile()
            tri.vertices = verts
            tri.faces = tris
            tri.uv_pos = uvs
            tri.face_uvs = tris # (because 1:1 with verts)
            for m in chargen_morphs:
                if m in morphdict:
                    tri.morphs[m] = morphdict[m]
    
            log.info(f"Generating tri file '{fname_chargen}'")
            tri.write(fname_chargen, chargen_morphs)

        if len(trip_morphs) > 0:
            expdict = {}
            for k, v in morphdict.items():
                if k[0] == '>':
                    n = k[1:]
                    expdict[n] = v
            self.trip.set_morphs(robj.nifnode.name, expdict, verts)
            
        return result


    def export_extra_data(self):
        """ Export any top-level extra data represented as Blender objects. 
            Sets self.bodytri_done if one of the extra data nodes represents a bodytri
        """
        sdlist = []
        for st in self.str_data:
            if st['NiStringExtraData_Name'] != 'BODYTRI' or self.game not in ['FO4', 'FO76']:
                # FO4 bodytris go at the top level
                sdlist.append( (st['NiStringExtraData_Name'], st['NiStringExtraData_Value']) )
                self.objs_written.add_pair(st, self.nif.rootNode) # [st.name] = self.nif
                self.bodytri_written |= (st['NiStringExtraData_Name'] == 'BODYTRI')

        if len(sdlist) > 0:
            self.nif.string_data = sdlist
        
        bglist = []
        for bg in self.bg_data: 
            bglist.append( (bg['BSBehaviorGraphExtraData_Name'], 
                            bg['BSBehaviorGraphExtraData_Value'], 
                            bg['BSBehaviorGraphExtraData_CBS']) )
            self.objs_written.add(ReprObject(bg, self.nif.rootNode)) # [bg.name] = self.nif

        if len(bglist) > 0:
            self.nif.behavior_graph_data = bglist 

        cdlist = []
        for cd in self.cloth_data:
            cdlist.append( (cd['BSClothExtraData_Name'], 
                            codecs.decode(cd['BSClothExtraData_Value'], "base64")) )
            self.objs_written.add(ReprObject(cd, self.nif.rootNode)) # [cd.name] = self.nif

        if len(cdlist) > 0:
            self.nif.cloth_data = cdlist 

        if self.bsx_flag:
            self.nif.rootNode.bsx_flags = [self.bsx_flag['BSXFlags_Name'],
                                  BSXFlags.parse(self.bsx_flag['BSXFlags_Value'])]
            self.objs_written.add(ReprObject(self.bsx_flag, self.nif.rootNode)) # [self.bsx_flag.name] = self.nif

        if self.bone_lod:
            self.nif.rootNode.bone_lod_extra = [
                self.bone_lod.name.split(":", 1)[1],
                json.loads(self.bone_lod['pynBoneLOD'])]
            self.objs_written.add(ReprObject(self.bone_lod, self.nif.rootNode)) # [self.bone_lod.name] = self.nif

        if self.bound:
            self.nif.rootNode.bounds_extra = [
                BD.nonunique_name(self.bound.name.split(":",1)[1]),
                self.bound.location,
                (max(v.co.x for v in self.bound.data.vertices),
                 max(v.co.y for v in self.bound.data.vertices),
                 max(v.co.z for v in self.bound.data.vertices)),]
            self.objs_written.add(ReprObject(self.bsx_flag, self.nif.rootNode)) # [self.bsx_flag.name] = self.nif

        if self.inv_marker:
            inv_rot, inv_zoom = BD.cam_to_inv(self.inv_marker.matrix_world, self.inv_marker.data.lens)

            self.nif.rootNode.inventory_marker = [
                self.inv_marker['BSInvMarker_Name'], 
                inv_rot[0],
                inv_rot[1],
                inv_rot[2],
                inv_zoom]
            self.objs_written.add(ReprObject(self.inv_marker, self.nif.rootNode)) # [self.inv_marker.name] = self.nif

        fmklist = []
        for fm in self.furniture_markers:
            buf = pynifly.FurnitureMarkerBuf()
            buf.offset = (fm.location / self.scale)[:]
            buf.heading = fm.rotation_euler.z
            buf.animation_type = pynifly.FurnAnimationType.GetValue(fm['AnimationType'])
            buf.entry_points = pynifly.NiObject.parse(fm['EntryPoints'])
            fmklist.append(buf)
        
        if fmklist:
            self.nif.furniture_markers = fmklist


    def get_loop_partitions(self, face, loops, weights):
        vi1 = loops[face.loop_start].vertex_index
        p = set([k for k in weights[vi1].keys() if is_partition(k)])
        for i in range(face.loop_start+1, face.loop_start+face.loop_total):
            vi = loops[i].vertex_index
            p = p.intersection(set([k for k in weights[vi].keys() if is_partition(k)]))
    
        if len(p) != 1:
            face_verts = [lp.vertex_index for lp in loops[face.loop_start:face.loop_start+face.loop_total]]
            if len(p) == 0:
                self.warnings.add('NO_PARTITION')
                if not self.objs_no_part:
                    log.warning(f"Face {face.index} on object {self.active_obj.name} is in no partition")
                self.objs_no_part.add(self.active_obj)
                create_group_from_verts(self.active_obj, BD.NO_PARTITION_GROUP, face_verts)
                return None
            elif len(p) > 1:
                self.warnings.add('MANY_PARITITON')
                if not self.objs_mult_part:
                    log.warning(f"Some faces have been assigned to more than one partition")
                self.objs_mult_part.add(self.active_obj)
                create_group_from_verts(self.active_obj, BD.MULTIPLE_PARTITION_GROUP, face_verts)
                None

        return p.pop()


    def extract_face_info(self, mesh, uvlayer, loopcolors, weights, obj_partitions, use_loop_normals=False):
        """ Extract triangularized face info from the mesh. 
            Return 
            loops = [vert-index, ...] list of vert indices in loops. Triangularized, 
                so these are to be read in triples.
            uvs = [(u,v), ...] list of uv coordinates 1:1 with loops
            norms = [(x,y,z), ...] list of normal vectors 1:1 with loops
                --Normal vectors come from the loops, because they reflect whether the edges
                are sharp or the object has flat shading
            colors = [(r,g,b,a), ...] 1:1 with loops
            partition_map = [n, ...] list of partition IDs, 1:1 with tris 

        """
        loops = []
        uvs = []
        orig_uvs = []
        norms = []
        colors = []
        partition_map = []

        # Calculating normals messes up the passed-in UV, so get the data out of it first
        for f in mesh.polygons:
            for i in f.loop_indices:
                orig_uvs.append(uvlayer[i].uv[:])

        # CANNOT figure out how to get the loop normals correctly.  They seem to follow the
        # face normals even on smooth shading.  (TEST_NORMAL_SEAM tests for this.) So use the
        # vertex normal except when there are custom split normals.
        bpy.ops.object.mode_set(mode='OBJECT') #required to get accurate normals

        # Before Blender 4.0 have to calculate normals. 4.0 doesn't need it and throws
        # an error.
        if hasattr(mesh, "calc_normals_split"):
            # Blender 4.0+ has normals in the loops, so no need to calculate them
            mesh.calc_normals_split()
        if hasattr(mesh, "calc_normals"):
            # Blender 3.0+ has normals in the vertices, so no need to calculate them
            mesh.calc_normals()

        def write_loop_vert(loopseg):
            """ Write one vert, given as a MeshLoop 
            """
            loops.append(loopseg.vertex_index)
            uvs.append(orig_uvs[loopseg.index])
            if loopcolors:
                colors.append(loopcolors[loopseg.index])
            if use_loop_normals:
                norms.append(loopseg.normal[:])
            else:
                norms.append(mesh.vertices[loopseg.vertex_index].normal[:])

        # Write out the loops as triangles, and partitions to match
        have_partitions = True
        partition_err = False
        for f in mesh.polygons:
            if f.loop_total < 3:
                log.warning(f"Degenerate polygons on {mesh.name}: 0={l0}, 1={l1}")
            else:
                if obj_partitions and len(obj_partitions) > 0:
                    loop_partition = self.get_loop_partitions(f, mesh.loops, weights)
                    if not loop_partition: partition_err = True
                l0 = mesh.loops[f.loop_start]
                l1 = mesh.loops[f.loop_start+1]
                for i in range(f.loop_start+2, f.loop_start+f.loop_total):
                    loopseg = mesh.loops[i]

                    write_loop_vert(l0)
                    write_loop_vert(l1)
                    write_loop_vert(loopseg)
                    if obj_partitions and len(obj_partitions) > 0:
                        if loop_partition:
                            partition_map.append(obj_partitions[loop_partition].id)
                        else:
                            have_partitions = False
                            partition_map.append(next(iter(obj_partitions.values())).id)
                    l1 = loopseg

        if not have_partitions:
            log.warning(f"Wrote faces without partitions on {mesh}")
        if partition_err:
            log.warning(f"Some faces are in multiple partitions, or no partition")

        return loops, uvs, norms, colors, partition_map


    def find_colormaps(self, mesh):
        """
        Find the color maps for the given mesh. Use the VERTEX_ALPHA color map for alpha
        values if it exists.

        Returns [color map, alpha map] -- Either may be None
        """
        try:
            vc = mesh.color_attributes
            active_color = vc.active_color
        except:
            vc = mesh.vertex_colors
            active_color = vc.active
        alphamap = None
        colormap = None
        if BD.ALPHA_MAP_NAME in vc.keys():
            alphamap = vc[BD.ALPHA_MAP_NAME]
        if alphamap and active_color and active_color.data == alphamap.data:
            # Alpha map is active--see if there's another map to use for colors. If not,
            # colors will be set to white
            for c in vc:
                if c.data != alphamap.data:
                    colormap = c
                    break
        elif active_color:
            colormap = active_color

        return colormap, alphamap


    def extract_colors(self, mesh):
        """
        Extract vertex color data from the given mesh. Use the VERTEX_ALPHA color map for
        alpha values if it exists.

        Returns [(r, g, b, a)...], 1:1 with loops whether the color map is using corners
        or points.
        """
        colormap, alphamap = self.find_colormaps(mesh)
        if colormap == None and alphamap == None: return

        loopcolors = None
        if colormap:
            mapping_scheme = BD.color_mapping(colormap)

            loopcolors = [(0.0, 0.0, 0.0, 0.0)] * len(mesh.loops)
            if mapping_scheme == "CORNER":
                for i, c in enumerate(colormap.data):
                    loopcolors[i] = c.color[:]
                    
            elif mapping_scheme == "POINT":
                for i, loop in enumerate(mesh.loops):
                    loopcolors[i] = colormap.data[loop.vertex_index].color[:]

        if alphamap:
            mapping_scheme = BD.color_mapping(alphamap)

            if loopcolors == None: loopcolors = [(0.0, 0.0, 0.0, 0.0)] * len(mesh.loops)
            if mapping_scheme == "CORNER":
                for i, alph in enumerate(alphamap.data):
                    c = loopcolors[i]
                    a = alph.color[0:3]
                    loopcolors[i] = (c[0], c[1], c[2], (a[0] + a[1] + a[2])/3)
            elif mapping_scheme == 'POINT':
                for i, loop in enumerate(mesh.loops):
                    c = loopcolors[i]
                    a = Color(alphamap.data[loop.vertex_index].color[0:3])
                    loopcolors[i] = (c[0], c[1], c[2], (a[0] + a[1] + a[2])/3)

        return loopcolors


    def extract_mesh_data(self, obj, arma, target_key):
        """ 
        Extract the triangularized mesh data from the given object
            obj = object being exported
            arma = controlling armature, if any. Needed so we can limit bone weights.
            target_key = shape key to export
        returns
            verts = list of XYZ vertex locations
            norms_new = list of XYZ normal values, 1:1 with verts
            uvmap_new = list of (u, v) values, 1:1 with verts
            colors_new = list of RGBA color values 1:1 with verts. May be None.
            tris = list of (t1, t2, t3) vert indices to define triangles
            weights_by_vert = [dict[group-name: weight], ...] 1:1 with verts
            morphdict = {shape-key: [verts...], ...} XXX>only if "target_key" is NOT specified
            paretitions = list of Partition objects, one for each partition
            partition_map = [n, ...] list of partition IDs, 1:1 with verts
        
        NOTE this routine changes selection and switches to edit mode and back
        """
        loopcolors = None
        saved_sk = obj.active_shape_key_index
        
        ObjectSelect([obj], active=True)
            
        # This next little dance ensures the mesh.vertices locations are correct
        if self.export_modifiers:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            obj1 = obj.evaluated_get(depsgraph) 
        else:
            obj1 = obj           
        obj1.active_shape_key_index = 0
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.object.mode_set(mode = 'OBJECT')
        editmesh = obj1.data
        editmesh.update()
        
        verts, weights_by_vert, morphdict \
            = extract_vert_info(obj1, editmesh, arma, target_key, self.scale)
    
        # Pull out vertex colors first because trying to access them later crashes
        bpy.ops.object.mode_set(mode = 'OBJECT') # Required to get vertex colors
        if self.export_colors:
            export = False
            try:
                c = editmesh.color_attributes.active_color
                export = True
            except:
                export = (len(editmesh.vertex_colors) > 0)
            if export: loopcolors = self.extract_colors(editmesh)
    
        # Apply shape key verts to the mesh so normals will be correct.  If the mesh has
        # custom normals, fukkit -- use the custom normals and assume the deformation
        # won't be so great that it looks bad.
        bpy.ops.object.mode_set(mode = 'OBJECT') 
        uvlayer = editmesh.uv_layers.active.data
        if target_key != '' and \
            editmesh.shape_keys and \
            target_key in editmesh.shape_keys.key_blocks.keys() and \
            not editmesh.has_custom_normals:
            editmesh = mesh_from_key(editmesh, verts, target_key)
                
        # Extracting and triangularizing
        partitions = partitions_from_vert_groups(obj1, self.game)
        loops, uvs, norms, loopcolors, partition_map = \
            self.extract_face_info(
                editmesh, uvlayer, loopcolors, weights_by_vert, partitions,
                use_loop_normals=editmesh.has_custom_normals)
    
        mesh_split_by_uv(verts, loops, norms, uvs, weights_by_vert, morphdict)

        # Make uv and norm lists 1:1 with verts (rather than with loops)
        uvmap_new = [(0.0, 0.0)] * len(verts)
        norms_new = [(0.0, 0.0, 0.0)] * len(verts)
        for i, vi in enumerate(loops):
            assert vi < len(verts), f"Error: Invalid vert index in loops: {vi} >= {len(verts)}"
            uvmap_new[vi] = uvs[i]
            norms_new[vi] = norms[i]
    
        ## Our "loops" list matches 1:1 with the mesh's loops. So we can use the polygons
        ## to pull the loops
        tris = []
        for i in range(0, len(loops), 3):
            tris.append((loops[i], loops[i+1], loops[i+2]))
    
        colors_new = None
        if len(loopcolors) > 0:
            colors_new = [(0.0, 0.0, 0.0, 0.0)] * len(verts)
            for i, lp in enumerate(loops):
                colors_new[lp] = loopcolors[i]
        
        obj.active_shape_key_index = saved_sk

        return verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, \
            morphdict, partitions, partition_map


    def export_node(self, obj:bpy.types.Object, parent:ReprObject=None) -> pynifly.NiNode:
        """Export a NiNode for the given Blender object."""
        ref = None
        with BD.stashed_animation(obj):
            nodetype = obj.get('pynBlockName', 'NiNode')
            props = pynifly.NiObject.block_types[nodetype].getbuf(values=obj)
            xf = BD.make_transformbuf(BD.apply_scale_xf(obj.matrix_local, 1))
            props.transform = xf
            if "pynNodeFlags" in obj:
                try:
                    props.flags = NiAVFlags.parse(obj["pynNodeFlags"]).value
                except Exception as e:
                    log.warning(f"Error setting node flags for {obj.name}: {e}")
            ninode = self.nif.add_block(
                name=BD.nonunique_name(obj.name), 
                buf=props, 
                parent=parent.nifnode if parent else None)
            # ninode = self.nif.add_node(obj.name, xf, parent.nifnode if parent else None)
            ref = ReprObject(obj, ninode) 
            self.objs_written.add(ref) 
            collision.CollisionHandler.export_collisions(self, obj)
            
        if self.export_animations:
            controller.ControllerHandler.export_animated_obj(self, ref)
        return ref
   

    def export_shape_parents(self, obj) -> pynifly.NiNode:
        """Export any parent NiNodes the shape might need 

        Returns the handle of the nif node that should be the parent of the shape (may be
        None).
        """
        # ancestors list contains all parents from root to obj's immediate parent
        ancestors = []
        p = obj.parent
        while p:
            if p.type != 'ARMATURE': ancestors.insert(0, p)
            p = p.parent

        last_parent = None
        ref = None
        ninode = None
        for this_parent in ancestors:
            ref = self.objs_written.find_blend(this_parent)
            if (not ref) and  ('pynRoot' not in this_parent):
                ref = self.export_node(this_parent, last_parent)
            last_parent = ref
        
        return ref


    def get_bone_xforms(self, arma, bone_names, shape):
        """Return transforms for the bones in list. Checks the "preserve_hierarchy" flag to 
        determine whether to return global or local transforms.
            arma = armature
            bone_names = list of names
            shape = shape being exported
            result = dict{bone-name: MatTransform, ...}
        """
        result = {}
        for b in arma.data.bones:
            result[b.name] = BD.get_bone_xform(arma, b.name, self.game, 
                                            self.preserve_hierarchy,
                                            self.export_pose)
    
        return result


    def write_bone(self, shape:pynifly.NiShape, arma, bone_name, bones_to_write):
        """ 
        Write a shape's bone, writing all parent bones first if necessary Returns the name
        of the node in the target nif for the new bone. 
        
        * shape - bone is added to shape's skin. May be None, if only writing a skeleton.
        * arma - parent armature
        * bone_name - bone to write (blender name)
        * bones_to_write - list of bones that the shape needs. If the bone isn't in this
          list, only write it if it's needed for the hierarchy.
        """
        if bone_name in self.shape_bones:
            return self.shape_bones[bone_name]

        if not bone_name in bones_to_write and not self.preserve_hierarchy:
            return None

        nifname = self.nif_name(bone_name)
        self.shape_bones[bone_name] = nifname
        
        bone_parent = arma.data.bones[bone_name].parent
        parname = None
        if bone_parent and bone_name not in self.writtenbones:
            parname = self.write_bone(shape, arma, bone_parent.name, bones_to_write)

        xf = BD.get_bone_xform(arma, bone_name, self.game, 
                            self.preserve_hierarchy,
                            self.export_pose)
        tb = BD.pack_xf_to_buf(xf, self.scale)
        
        if bone_name in bones_to_write and shape:
            shape.add_bone(nifname, tb, 
                           (parname if self.preserve_hierarchy else None))
        elif bone_name not in self.writtenbones and (self.preserve_hierarchy or not shape):
            # Not a shape bone but needed for the hierarchy
            self.nif.add_node(nifname, tb, parname)

        self.writtenbones[bone_name] = nifname
        
        return nifname


    def write_bone_hierarchy(self, shape:pynifly.NiShape, arma, used_bones:list):
        """Write the bone hierarchy to the nif. Do this first so that transforms 
        and parent/child relationships are correct. Do not assume that the skeleton is fully
        connected (do Blender armatures have to be fully connected?). 
        used_bones - list of bone names to write. 
        """
        for bone_name in used_bones:
            if bone_name in arma.data.bones:
                self.write_bone(shape, arma, bone_name)


    def export_skin(self, obj, arma, new_shape, new_xform, weights_by_vert):
        """
        Export the skin for a shape, including bones used by the skin.
        """
        log.info(f"Skinning {obj.name}")
        new_shape.skin()
        new_shape.transform = BD.make_transformbuf(new_xform)
        newxfi = new_xform.copy()
        newxfi.invert()
        new_shape.set_global_to_skin(BD.make_transformbuf(newxfi))
    
        weights_by_bone = pynifly.get_weights_by_bone(weights_by_vert, arma.data.bones.keys())

        for bone_name in  weights_by_bone.keys():
            self.write_bone(new_shape, arma, bone_name, weights_by_bone.keys())

        for bone_name, bone_weights in weights_by_bone.items():
            nifname = self.nif_name(bone_name)
            if self.export_pose:
                # Bind location is different from pose location
                xf = BD.get_bone_xform(arma, bone_name, self.game, False, False)
                xfoffs = obj.matrix_world.inverted() @ xf
                xfinv = xfoffs.inverted()
                tb_bind = BD.pack_xf_to_buf(xfinv, self.scale)
                new_shape.set_skin_to_bone_xform(nifname, tb_bind)
            else:
                # Have to set skin-to-bone again because adding the bones nuked it
                xf = BD.get_bone_xform(arma, bone_name, self.game, False, self.export_pose)
                xfoffs = obj.matrix_local.inverted() @ xf
                xfinv = xfoffs.inverted()
                tb = BD.pack_xf_to_buf(xfinv, self.scale)
                    
                new_shape.set_skin_to_bone_xform(nifname, tb)

            self.writtenbones[bone_name] = nifname
            new_shape.setShapeWeights(nifname, bone_weights)


    def apply_shape_key(self, key_name):
        pass


    def export_shape(self, obj, target_key='', arma=None):
        """ Export given blender object to the given NIF file; also writes any associated
            tri file. Checks to make sure the object wasn't already written.
            obj = blender object
            target_key = shape key to export
            arma = armature to skin to
            """
        if self.objs_written.find_blend(obj) or BD.nonunique_name(obj) in collision.collision_names:
            return
        log.info(f"Exporting {obj.name}")

        self.active_obj = obj
        self.shape_bones = {}

        with BD.stashed_animation(obj):
            # If there's a hierarchy, export parents (recursively) first
            my_parent = self.export_shape_parents(obj)

            retval = set()

            # Prepare for reporting any bone weight errors
            is_skinned = (arma is not None)
            unweighted = []
            if BD.UNWEIGHTED_VERTEX_GROUP in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[BD.UNWEIGHTED_VERTEX_GROUP])
            if BD.MULTIPLE_PARTITION_GROUP in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[BD.MULTIPLE_PARTITION_GROUP])
            if BD.NO_PARTITION_GROUP in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[BD.NO_PARTITION_GROUP])
            
            if is_skinned:
                # Get unweighted bones before we muck up the list by splitting edges
                unweighted = tag_unweighted(obj, arma.data.bones.keys())
                if not expected_game(self.nif, arma.data.bones):
                    log.warning(f"Exporting to game that doesn't match armature: game={self.nif.game}, armature={arma.name}")
                    retval.add('GAME')

            # Collect key info about the mesh 
            verts, norms_new, uvmap_new, colors_new, tris, weights_by_vert, morphdict, partitions, partition_map = \
                self.extract_mesh_data(self.active_obj, arma, target_key)

            is_headpart = obj.data.shape_keys \
                    and len(self.nif.dict.expression_filter(set(obj.data.shape_keys.key_blocks.keys()))) > 0

            obj.data.update()
            shaderexp = shader_io.ShaderExporter(obj, self.nif.game)

            if shaderexp.is_obj_space:
                norms_exp = None
            else:
                norms_exp = norms_new

            # Make the shape in the nif file. Use the shape's block type, or choose a
            # reasonable default.
            if 'pynBlockName' in obj:
                blocktype = obj['pynBlockName']
            elif is_headpart and self.game == 'SKYRIMSE':
                blocktype = 'BSDynamicTriShape'
            elif partitions and self.game == 'FO4':
                blocktype = 'BSSubIndexTriShape' 
            elif self.game == 'SKYRIM':
                blocktype = 'NiTriShape' 
            else:
                blocktype = 'BSTriShape'
            
            blockclass = pynifly.NiObject.block_types[blocktype]
            props = blockclass.getbuf(obj)

            # If we're exporting a mesh that is a connect point, export the mesh as the 
            # editor marker for that point. Exported editor markers are always parented
            # to the root regardless of the connect point's target.
            if connectpoint.is_connectpoint(obj):
                obj_name = "EditorMarker"
                p = None
            else:
                obj_name = self.unique_name(obj)
                p = my_parent.nifnode if my_parent else None
            new_shape = self.nif.createShapeFromData(obj_name, 
                                                     verts, tris, uvmap_new, norms_exp,
                                                     props=props,
                                                     parent=p)
            if "pynNodeFlags" in obj:
                try:
                    new_shape.flags = NiAVFlags.parse(obj['pynNodeFlags']).value
                except Exception as e:
                    log.warning(f"Error setting pynNodeFlags for {obj.name}: pynNodeFlags={obj['pynNodeFlags']}")
            if "pynVertexDesc" in obj and obj["pynVertexDesc"]:
                try:
                    new_shape.properties.vertexDesc = VertexFlags.parse(obj['pynVertexDesc']).value
                except Exception as e:
                    log.warn(f"Error setting pynVertexDesc for {obj.name}: pynVertexDesc={obj['pynVertexDesc']}")

            robj = ReprObject(obj, new_shape)
            self.objs_written.add(robj)

            if colors_new:
                new_shape.set_colors(colors_new)

            self.export_shape_data(robj)
            
            shaderexp.export(new_shape)

            # Using local transform because the shapes will be parented in the nif
            new_xform = obj.matrix_local * (1/self.scale) 
            if not has_uniform_scale(obj):
                # Non-uniform scales applied to verts, so just use 1.0 for the scale on the object
                l, r, s = new_xform.decompose()
                new_xform = BD.MatrixLocRotScale(l, r, Vector((1,1,1))) 
            elif  not NearEqual(self.scale, 1.0):
                # Export scale factor applied to verts, so scale obj translation but not obj scale 
                l, r, s = new_xform.decompose()
                new_xform = BD.MatrixLocRotScale(l, r, obj.matrix_local.to_scale()) 
            
            if is_skinned:
                self.export_skin(self.active_obj, arma, new_shape, new_xform, weights_by_vert)
                if len(unweighted) > 0:
                    create_group_from_verts(obj, BD.UNWEIGHTED_VERTEX_GROUP, unweighted)
                    log.warning(f"Some vertices are not weighted to the armature in object {obj.name}")
                    self.objs_unweighted.add(obj)

                if len(partitions) > 0:
                    if 'FO4_SEGMENT_FILE' in obj.keys():
                        new_shape.segment_file = obj['FO4_SEGMENT_FILE']

                    new_shape.set_partitions(
                        [p for p in partitions.values() if p.id in partition_map], 
                        partition_map)

                collision.CollisionHandler.export_collisions(self, arma)
            else:
                new_shape.transform = BD.make_transformbuf(new_xform)

        # Write other block types
        collision.CollisionHandler.export_collisions(self, obj)
        try:
            if (self.export_animations 
                    and obj.active_material 
                    and obj.active_material.node_tree 
                    and obj.active_material.node_tree.animation_data):
                controller.ControllerHandler.export_shader_controller(
                    self, robj, obj.active_material.node_tree)
        except Exception as e:
            log.exception(f"Error exporting controller for object {obj.name}: {e}")

        # Write tri file
        retval |= self.export_tris(robj, verts, tris, uvmap_new, morphdict)

        # Write TRIP extra data 
        if self.write_bodytri \
            and self.game in ['SKYRIM', 'SKYRIMSE'] \
            and len(self.trip.shapes) > 0:
            new_shape.string_data = [('BODYTRI', BD.truncate_filename(self.trippath, "meshes"))]

        obj['PYN_GAME'] = self.game
        obj['PYN_BLENDER_XF'] = MatNearEqual(self.export_xf, BD.blender_export_xf)
        if self.preserve_hierarchy != BD.PRESERVE_HIERARCHY_DEF:
            obj['PYN_PRESERVE_HIERARCHY'] = self.preserve_hierarchy 
        if arma:
            arma['PYN_RENAME_BONES'] = self.do_rename_bones
            if self.rename_bones_nift != BD.RENAME_BONES_NIFT_DEF:
                arma['PYN_RENAME_BONES_NIFTOOLS'] = self.rename_bones_nift 
        if self.write_bodytri != BD.WRITE_BODYTRI_DEF:
            obj['PYN_WRITE_BODYTRI_ED'] = self.write_bodytri 
        if self.export_pose != BD.EXPORT_POSE_DEF: obj['PYN_EXPORT_POSE'] = self.export_pose 

        if self.active_obj != obj:
            bpy.data.meshes.remove(self.active_obj.data)
            self.active_obj = None

        log.info(f"{obj.name} successfully exported to {self.nif.filepath}\n")
        return retval
    

    def export_armature(self, arma):
        """Export an armature with no shapes"""
        for b in arma.data.bones:
            self.write_bone(None, arma, b.name, arma.data.bones.keys())
        collision.CollisionHandler.export_collisions(self, arma)


    def export_nif(self, fpath, suffix, sk):
        """
        Export to a single nif file.

        * fpath = file path to write
        * suffix = None or "_facebones" when a filebones nif is to be written
        * sk = target shape key to export
        """
        self.objs_written = ReprObjectCollection()
        pynifly.NifFile.clear_log()
        self.nif = pynifly.NifFile()

        if self.objects:
            shape = next(iter(self.objects))
        else:
            shape = self.armature

        rt = "NiNode"
        rn = "Scene Root"
        if self.root_object:
            rt = self.root_object.get("pynBlockName", "NiNode")
            rn = BD.name_from_root(self.root_object)
        
        self.nif.initialize(self.game, fpath, rt, rn)
        if self.root_object:
            self.objs_written.add_pair(self.root_object, self.nif.rootNode) 
            if "pynNodeFlags" in self.root_object:
                try:
                    self.nif.rootNode.flags = NiAVFlags.parse(self.root_object["pynNodeFlags"]).value
                except Exception as e:
                    log.warn(f"Error setting pynNodeFlags for root object {self.root_object.name}: pynNodeFlags={self.root_object['pynNodeFlags']}")

        if suffix == '_faceBones':
            self.nif.dict = fo4FaceDict

        self.nif.dict.use_niftools = self.rename_bones_nift
        self.writtenbones = {}

        if self.objects:
            for obj in self.objects:
                if suffix == "_faceBones" and self.facebones:
                    # Have exporting the facebones variant and have a facebones armature
                    self.export_shape(obj, sk, self.facebones)
                elif (not suffix) and self.armature:
                    # Exporting the main file and have an armature to do it with. 
                    self.export_shape(obj, sk, self.armature)
                elif (not suffix) and self.facebones:
                    # Exporting the main file and have a facebones armature to do it
                    # with. Facebones armatures generally have all the necessary bones
                    # for export, so it's fine to use them.
                    self.export_shape(obj, sk, self.facebones)
                elif (not self.facebones) and (not self.armature):
                    # No armatures, just export the shape.
                    self.export_shape(obj, sk)
        elif self.armature:
            # Just export the skeleton
            self.export_armature(self.armature)

        # Make sure any grouping nodes get exported, even if they're empty.
        for obj in self.grouping_nodes:
            if 'pynRoot' not in obj and not self.objs_written.find_blend(obj):
                par = None
                if obj.parent:
                    par = self.objs_written.find_blend(obj.parent)
                self.export_node(obj, par)

        # Check for bodytri morphs--write the extra data node if needed
        if self.write_bodytri \
                and self.game in ['FO4', 'FO76'] \
                and len(self.trip.shapes) > 0 \
                and  not self.bodytri_written:
            self.nif.string_data = [('BODYTRI', BD.truncate_filename(self.trippath, "meshes"))]

        if self.root_object:
            collision.CollisionHandler.export_collisions(self, self.root_object)
        self.export_extra_data()
        self.connect_points.export_all(self.nif, BD.asset_path)
        if self.export_animations:
            controller.ControllerHandler.export_named_animations(self, self.objs_written)
            if self.armature:
                controller.ControllerHandler.export_animated_armature(self, self.armature)

        self.nif.save()
        log.info(f"..Wrote {fpath}")
        msgs = list(filter(lambda x: not x.startswith('Info: Loaded skeleton') and len(x)>0, 
                            self.nif.message_log().split('\n')))
        if msgs:
            self.message_log.append(self.nif.message_log())


    def export_file_set(self, suffix=''):
        """ 
        Create a set of nif files from the target objects, using the given armature and
        appending the suffix. One file is created per shape key with the shape key used as
        suffix. Associated TRIP files are exported if there is TRIP info.
                
        * suffix = suffix to append to the filenames, after the shape key suffix. Empty
          string for regular nifs, non-empty for facebones nifs
        * self.objects = Objects to export
        """
        if self.file_keys is None or len(self.file_keys) == 0:
            shape_keys = ['']
        else:
            shape_keys = self.file_keys

        # One TRIP file is written even if we have variants of the mesh ("_" prefix)
        fname_ext = os.path.splitext(os.path.basename(self.filepath))
        self.trip = TripFile()
        self.trippath = os.path.join(os.path.dirname(self.filepath), fname_ext[0]) + ".tri"

        for sk in shape_keys:
            fbasename = fname_ext[0] + sk + suffix
            fnamefull = fbasename + fname_ext[1]
            fpath = os.path.join(os.path.dirname(self.filepath), fnamefull)

            self.export_nif(fpath, suffix, sk)

        if len(self.trip.shapes) > 0:
            self.trip.write(self.trippath)
            log.info(f"Wrote {self.trippath}")


    def execute(self):
        if not self.objects and not self.armature:
            self.warn(f"No objects selected for export", tags=["NOTHING"])
            return

        log.info(str(self))
        pynifly.NifFile.clear_log()
        self.export_file_set('')
        if self.facebones:
            self.export_file_set('_faceBones')
        msgs = list(filter(lambda x: not x.startswith('Info: Loaded skeleton') and len(x)>0, 
                           pynifly.NifFile.message_log().split('\n')))
        if msgs:
            log.debug("Nifly Message Log:\n" + pynifly.NifFile.message_log())
    
    def export(self, objects):
        self.set_objects(objects)
        self.execute()

    @classmethod
    def do_export(cls, filepath, game, objects, scale=1.0):
        return NifExporter(filepath, game, scale=scale).export(objects)


def get_default_scale():
    return 1.0


def current_active_object(context):
    """
    Determine the object to use as the active object. Only use blender's active object if
    it is also selected. It's too confusing to be working on an unselected object. If
    there's no active object choose the first selected object.
    """
    if context.object and context.object.select_get():
        return context.object
    if context.selected_objects:
        return context.selected_objects[0]
    return None

    
def get_default_game_target(context):
    """Look at currently selected objects to determine game target."""
    g = "SKYRIM"
    obj = current_active_object(context)
    if 'PYN_GAME' in obj:
        g = obj['PYN_GAME']
    else:
        selected_armatures = [a for a in context.selected_objects if a.type == 'ARMATURE']
        if selected_armatures:
            g = BD.best_game_fit(selected_armatures[0].data.bones)
    return g
    

class ExportNIF(bpy.types.Operator, ExportHelper):
    """Export Blender object(s) to a NIF File"""

    bl_idname = "export_scene.pynifly"
    bl_label = 'Export NIF (Nifly)'
    bl_options = {'PRESET'}

    filename_ext = ".nif"

    target_game: bpy.props.EnumProperty(
            name="Target Game",
            items=(('SKYRIM', "Skyrim", ""),
                   ('SKYRIMSE', "Skyrim SE", ""),
                   ('FO4', "Fallout 4", ""),
                   ('FO76', "Fallout 76", ""),
                   ('FO3', "Fallout New Vegas", ""),
                   ('FO3', "Fallout 3", ""),
                   ),
            ) # type: ignore

    use_blender_xf: bpy.props.BoolProperty(
        name="Use Blender orientation",
        description="Use Blender's orientation and scale.",
        default=BD.BLENDER_XF_DEF
        ) # type: ignore
    
    do_rename_bones: bpy.props.BoolProperty(
        name="Rename Bones",
        description="Rename bones from Blender conventions back to nif.",
        default=True) # type: ignore

    rename_bones_niftools: bpy.props.BoolProperty(
        name="Rename Bones as per NifTools",
        description="Rename bones from NifTools' Blender conventions back to nif.",
        default=False) # type: ignore

    preserve_hierarchy: bpy.props.BoolProperty(
        name="Preserve Bone Hierarchy",
        description="Preserve bone hierarchy in exported nif.",
        default=False) # type: ignore

    write_bodytri: bpy.props.BoolProperty(
        name="Export BODYTRI Extra Data",
        description="Write an extra data node pointing to the BODYTRI file, if there are any bodytri shape keys. Not needed if exporting for Bodyslide, because they write their own.",
        default=True) # type: ignore

    export_pose: bpy.props.BoolProperty(
        name="Export pose position",
        description="Export bones in pose position.",
        default=False) # type: ignore
    
    export_modifiers: bpy.props.BoolProperty(
        name="Export modifiers",
        description="Export all active modifiers (including shape keys)",
        default=False) # type: ignore

    export_animations: bpy.props.BoolProperty(
        name="Export animations",
        description="Export animations embedded in the nif file",
        default=False) # type: ignore

    export_colors: bpy.props.BoolProperty(
        name="Export vertex color/alpha",
        description="Use vertex color attributes as vertex color",
        default=True) # type: ignore

    chargen_ext: bpy.props.StringProperty(
        name="Chargen extension",
        description="Extension to use for chargen files (not including file extension).",
        default="chargen") # type: ignore

    # For debugging. If False, use the properties passed in with the invocation. If invoked through
    # the UI it will be true.
    intuit_defaults: bpy.props.BoolProperty(
        name="Intuit Defaults",
        description="Get defaults from current selection",
        default=True,
        options={'HIDDEN'},
    ) # type: ignore
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objects_to_export = bpy.context.selected_objects 

        if not self.objects_to_export:
            self.report({"ERROR"}, "No objects selected for export")
            return

        obj = self.objects_to_export[0]
        if not self.filepath:
            self.filepath = clean_filename(obj.name)

        lst = [obj for obj in self.objects_to_export if "pynRoot" in obj]
        obj_root = lst[0] if lst else None

        export_armature = None
        if obj.type == 'ARMATURE':
            export_armature = obj
        else:
            export_armature, fb_arma = BD.find_armatures(obj)
            if not export_armature:
                export_armature = fb_arma

        if self.intuit_defaults:
            g = ""
            if 'PYN_GAME' in obj:
                g = obj['PYN_GAME']
            else:
                if export_armature:
                    g = BD.best_game_fit(export_armature.data.bones)
            if g != "":
                self.target_game = g
        
            if obj_root and 'PYN_BLENDER_XF' in obj_root:
                self.use_blender_xf = obj_root['PYN_BLENDER_XF']
            elif obj and 'PYN_BLENDER_XF' in obj:
                self.use_blender_xf = obj['PYN_BLENDER_XF']
                
            if export_armature and 'PYN_RENAME_BONES' in export_armature:
                self.do_rename_bones = export_armature['PYN_RENAME_BONES']
            else:
                # User might have selected a root or an object, not an armature. Pick up
                # the rename flag from whetever they did select.
                objs = self.objects_to_export
                i = 0
                while i < len(objs):
                    objs.extend(objs[i].children)
                    i += 1
                objs_flagged = [x for x in objs if 'PYN_RENAME_BONES' in x]
                if objs_flagged:
                    self.do_rename_bones = all(x['PYN_RENAME_BONES'] for x in objs_flagged)

            if export_armature and 'PYN_RENAME_BONES_NIFTOOLS' in export_armature:
                self.rename_bones_niftools = export_armature['PYN_RENAME_BONES_NIFTOOLS']

            if obj and 'PYN_PRESERVE_HIERARCHY' in obj:
                self.preserve_hierarchy = obj['PYN_PRESERVE_HIERARCHY']

            if obj and 'PYN_WRITE_BODYTRI_ED' in obj:
                self.write_bodytri = obj['PYN_WRITE_BODYTRI_ED']

            if obj and 'PYN_EXPORT_POSE' in obj:
                self.export_pose = obj['PYN_EXPORT_POSE']

            if obj and 'PYN_CHARGEN_EXT' in obj:
                self.chargen_ext = obj['PYN_CHARGEN_EXT']

        
    @classmethod
    def poll(cls, context):
        if not pynifly.nifly_path:
            log.error("pyNifly DLL not found--pyNifly disabled")
            return False

        if len(context.selected_objects) == 0:
            log.error("Must select an object to export")
            return False

        if context.object.mode != 'OBJECT':
            log.error("Must be in Object Mode to export")
            return False

        return True

    def invoke(self, context, event):
        # Set the default directory to the last used path if available
        if context.window_manager.pynifly_last_export_path_nif:
            self.filepath = str(Path(context.window_manager.pynifly_last_export_path_nif) 
                                / Path(self.filepath))
        return super().invoke(context, event)

    def execute(self, context):
        res = set()
        selected_objs = context.selected_objects
        active_obj = context.object
        initial_frame = context.scene.frame_current

        if not self.poll(context):
            self.report({"ERROR"}, f"Cannot run exporter--see system console for details")
            return {'CANCELLED'} 

        if len(self.objects_to_export) == 0:
            self.report({"ERROR"}, "No objects selected for export")
            return {'CANCELLED'}

        self.log_handler = BD.LogHandler.New(bl_info, "EXPORT", "NIF")
        pynifly.NifFile.Load(pynifly.nifly_path)

        try:
            context.scene.frame_set(1)
            exporter = NifExporter(self.filepath, 
                                   self.target_game, 
                                   chargen=self.chargen_ext)

            exporter.context = context
            exporter.do_rename_bones = self.do_rename_bones
            exporter.rename_bones_nift = self.rename_bones_niftools
            exporter.preserve_hierarchy = self.preserve_hierarchy
            exporter.write_bodytri = self.write_bodytri
            exporter.export_pose = self.export_pose
            exporter.export_modifiers = self.export_modifiers
            if self.export_animations and not hasattr(bpy.types, 'ActionSlot'):
                log.warning(f"pyNifly animation export not supported in Blender version {bpy.app.version_string}")
                exporter.export_animations = False
            else:
                exporter.export_animations = self.export_animations
            exporter.export_colors = self.export_colors
            if self.use_blender_xf:
                exporter.export_xf = BD.blender_export_xf
            exporter.export(self.objects_to_export)
            
            rep = False
            status = {"SUCCESS"}
            if len(exporter.objs_unweighted) > 0:
                status = {"ERROR"}
                self.report(status, f"The following objects have unweighted vertices.See the '*UNWEIGHTED*' vertex group to find them: \n{exporter.objs_unweighted}")
                rep = True
            if len(exporter.objs_scale) > 0:
                status = {"ERROR"}
                self.report(status, f"The following objects have non-uniform scale, which nifs do not support. Scale applied to verts before export.\n{exporter.objs_scale}")
                rep = True
            if len(exporter.objs_mult_part) > 0:
                status = {"WARNING"}
                self.report(status, f"Some faces have been assigned to more than one partition, which should never happen.\n{exporter.objs_mult_part}")
                rep = True
            if len(exporter.objs_no_part) > 0:
                status = {"WARNING"}
                self.report(status, f"Some faces have been assigned to no partition, which should not happen for skinned body parts.\n{exporter.objs_no_part}")
                rep = True
            if len(exporter.arma_game) > 0:
                status = {"WARNING"}
                self.report(status, f"The armature appears to be designed for a different game--check that it's correct\nArmature: {exporter.arma_game}, game: {exporter.game}")
                rep = True
            if 'NOTHING' in exporter.warnings:
                status = {"WARNING"}
                self.report(status, f"No mesh selected; nothing to export")
                rep = True
            if 'WARNING' in exporter.warnings:
                status = {"WARNING"}
                self.report(status, f"Export completed with warnings. Check the console window.")
                rep = True
            if not rep:
                if self.log_handler.max_error <= logging.INFO:
                    self.report({'INFO'}, f"Export successful")
                elif self.log_handler.max_error <= logging.WARNING:
                    self.report({'WARNING'}, f"Export completed with warnings")
                elif self.log_handler.max_error <= logging.WARNING:
                    self.report({'ERROR'}, f"Export failed, see console window for details")
            
        except:
            self.log_handler.log.exception("Export of nif failed")
            self.report({"ERROR"}, "Export of nif failed, see console window for details")
            res.add("CANCELLED")

        self.log_handler.finish("EXPORT", self.objects_to_export)
        context.scene.frame_set(initial_frame)
        ObjectSelect([selected_objs])
        ObjectActive(active_obj)

        # Save the directory path for next time
        if 'CANCELLED' not in res:
            wm = context.window_manager
            wm.pynifly_last_export_path_nif = os.path.dirname(self.filepath)

        return res.intersection({'CANCELLED', 'FINISHED'})
