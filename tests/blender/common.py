"""Automated tests for pyNifly export/import addon

Convenient setup for running these tests here: 
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""
import os
import sys
import importlib
import shutil
import logging
import math
from pathlib import Path
import json
import bpy
from mathutils import Matrix, Vector, Quaternion, Euler

# Reload all io_scene_nifly submodules so code changes take effect without
# restarting Blender. Must happen before any from-imports below.
_addon_prefix = "io_scene_nifly"
_stale = [name for name in sys.modules if name == _addon_prefix or name.startswith(_addon_prefix + ".")]
for _name in _stale:
    importlib.reload(sys.modules[_name])
del _stale

import io_scene_nifly.pyn.niflytools as NT
from io_scene_nifly.pyn.nifdefs import PynBufferTypes
from io_scene_nifly.pyn.nifconstants import (
    NiAVFlags, ShaderFlags2, bhkCOFlags, SkyrimCollisionLayer, SkyrimHavokMaterial,
    CycleType, hkResponseType, BroadPhaseType, hkMotionType,
    hkSolverDeactivation, hkQualityType, HAVOC_SCALE_FACTOR)
import io_scene_nifly.pyn.pynifly as pyn
import xml.etree.ElementTree as xml
import io_scene_nifly.blender_defs as BD
from io_scene_nifly.tri.trifile import TriFile
from io_scene_nifly.tri.tripfile import TripFile
from io_scene_nifly.util.reprobj import ReprObject, ReprObjectCollection
from io_scene_nifly.nif import controller
from io_scene_nifly.nif import shader_io
from io_scene_nifly.nif import pyn_props
from .. import test_tools as TT
from .. import test_tools_bpy as TTB
from .. import test_nifchecker as CHK


log = logging.getLogger("pynifly")
log.setLevel(logging.DEBUG)


# Warnings that are a property of the test assets rather than a defect in the code
# under test, so every test that touches such an asset would otherwise need to
# whitelist them. Duplicate triangles turn up in a lot of vanilla meshes;
# TEST_IMPORT_DUPLICATE_TRIS_WARNS covers that the warning still fires.
ALWAYS_EXPECTED = ("duplicate triangle(s) across",)

# Animation export is gated on slotted actions (bpy.types.ActionSlot, Blender 4.4+).
# On an older supported Blender the exporter warns on EVERY export, which otherwise
# fails every test that exports -- 156 of 282 on Blender 4.2. Expected there, not a
# failure. Detected by capability, not version, to match how the exporter gates it.
if not hasattr(bpy.types, 'ActionSlot'):
    ALWAYS_EXPECTED += ("animation export not supported",)


class TestLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("pynifly")
        self.log.addHandler(self)
        self.expected_errors = None
        self.max_error = 0

    def __del__(self):
        if self.log:
            self.log.removeHandler(self)

    def emit(self, record):
        msg = record.getMessage()
        if any([e in msg for e in ALWAYS_EXPECTED]):
            return
        if self.expected_errors:
            if any([e in msg for e in self.expected_errors]):
                return # Expected error, ignore.
        self.max_error = max(self.max_error, record.levelno)

    def start(self, expect_errors=None):
        """
        Start logging for an operation. Return the log and its handler.
        """
        self.max_error = 0
        self.expected_errors = expect_errors
        
    def check(self):
        assert self.max_error <= logging.INFO, \
            f"No errors reported during test {self.max_error} > INFO"        

    def finish(self):
        self.check()        

    @classmethod
    def New(cls):
        lh = TestLogHandler()
        lh.start()
        return lh


test_loghandler:TestLogHandler = TestLogHandler.New()


def dump_action(act):
    print(f"Action {act.name}:")
    for lay in act.layers:
        for strip in lay.strips:
            for i, cb in enumerate(strip.channelbags):
                print(f"   [{i}]ChannelBag for {cb.slot.name_display} with {len(cb.fcurves)} fcurves")
                for j, fc in enumerate(cb.fcurves):
                    print(f"      [{j}] {fc.data_path} with {len(fc.keyframe_points)} keyframes")
                    for k, kp in enumerate(fc.keyframe_points):
                        print(f"         [{k}] Keyframe at {kp.co[0]}: {kp.co[1]}")


def _uparm_r_cuts(nif):
    """Helper: sorted cut offsets on the Up Arm.R bearer (material 0xb2e2764f)."""
    UPARM = 0xb2e2764f
    cuts = []
    for seg in nif.shapes[0].partitions:
        for ss in getattr(seg, 'subsegments', []):
            if ss.material == UPARM and ss.cut_offsets:
                cuts.extend(ss.cut_offsets)
    return sorted(cuts)


def Spriggan_LeavesLandedLoop_Check(lllaction):
    # LeavesLandedLoop has correct range
    assert TT.is_eq(lllaction.frame_range[0], 1, "Frame start")
    assert TT.is_equiv(lllaction.frame_range[1], 123, "Frame end", e=1)

    # Is controlling correct targets
    assert TT.is_eq(len(lllaction.slots), 4, "LeavesLandedLoop requires 4 slots")
    scene_objs = ReprObjectCollection.New(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    lllanims = [ad for ad in controller.all_named_animations(scene_objs) if ad.name == 'LeavesLandedLoop']
    llltargets = [ad.target_obj.blender_obj.name for ad in lllanims]
    assert TT.is_samemembers(llltargets, 
                          ['SprigganFxHandCovers',
                           'SprigganBodyLeaves', 
                           'SprigganHandLeaves', 
                           'SprigganFxTestUnified:0', 
                           ],
                          "LeavesLandedLoop controlled targets")

    # Fcurve targets correct
    fcurve_targets = [fc.data_path for fc in BD.action_fcurves(lllaction)]
    assert TT.is_samemembers(
        fcurve_targets,
        ['nodes["SkyrimShader:Effect"].inputs["Alpha Adjust"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Strength"].default_value'],
        "fcurve data_path values")
    
    # Is controlling SprigganFxHandCovers correctly
    lllhcbag = next((cb for cb in lllaction.layers[0].strips[0].channelbags
                    if 'Alpha Adjust' in cb.fcurves[0].data_path), None)
    assert TT.is_eq(len(lllhcbag.fcurves), 1, "SprigganFxHandCovers fcurves")
    assert TT.is_eq(len(lllhcbag.fcurves[0].keyframe_points), 3, "SprigganFxHandCovers keyframes")
    assert TT.is_equiv(lllhcbag.fcurves[0].keyframe_points[0].co[1], 0, "First keyframe value")
    assert TT.is_equiv(lllhcbag.fcurves[0].keyframe_points[-1].co[1], 0, "Last keyframe value")
    
    # Is controlling SprigganBodyLeaves correctly.
    lllfxbag = next((cb for cb in lllaction.layers[0].strips[0].channelbags
                     if 'Alpha Threshold' in cb.fcurves[0].data_path
                        and len(cb.fcurves[0].keyframe_points) == 7), None)
    assert lllfxbag is not None, "Found SprigganBodyLeaves channelbag"
    assert TT.is_eq(len(lllfxbag.fcurves), 1, "SprigganBodyLeaves fcurves")
    assert TT.is_equiv(lllfxbag.fcurves[0].keyframe_points[0].co[1], 0, "First keyframe value")
    assert TT.is_equiv(lllfxbag.fcurves[0].keyframe_points[1].co[1], 70, "Second keyframe value")
    assert TT.is_equiv(lllfxbag.fcurves[0].keyframe_points[2].co[1], 0, "Third keyframe value")

def Spriggan_KillFX_Check(kfxaction):
    """Check that the KillFx animation sequence was imported correctly."""
    controller.apply_animation("KillFX", bpy.context.scene)

    # KillFX has correct range
    assert TT.is_eq(kfxaction.frame_range[0], 1, "Frame start")
    assert TT.is_equiv(kfxaction.frame_range[1], 121, "Frame end", e=1)

    # Fcurve targets correct
    fcurve_targets = [fc.data_path for fc in BD.action_fcurves(kfxaction)]
    assert TT.is_samemembers(
        fcurve_targets,
        ['nodes["SkyrimShader:Effect"].inputs["Alpha Adjust"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Color"].default_value', 
         'nodes["SkyrimShader:Default"].inputs["Emission Strength"].default_value'],
        "fcurve data_path values")

    # Is controlling correct targets
    assert TT.is_eq(len(kfxaction.slots), 4, "KillFX requires 4 slots")

    # Is controlling SprigganFxHandCovers correctly
    kfxhcbag = [cb for cb in kfxaction.layers[0].strips[0].channelbags
                    if 'Alpha Adjust' in cb.fcurves[0].data_path][0]
    assert TT.is_eq(len(kfxhcbag.fcurves), 1, "SprigganFxHandCovers fcurves")
    assert TT.is_eq(len(kfxhcbag.fcurves[0].keyframe_points), 2, "KillFX SprigganFxHandCovers keyframes")
    assert TT.is_equiv(kfxhcbag.fcurves[0].keyframe_points[0].co[1], 0, "KillFX SprigganFxHandCovers First keyframe value")
    assert TT.is_equiv(kfxhcbag.fcurves[0].keyframe_points[-1].co[1], 0, "KillFX SprigganFxHandCovers Last keyframe value")

    # Is controlling SprigganBodyLeaves correctly.
    # BodyLeaves has one slot & one fcurve controlling Alpha Threshold
    mat_anim = bpy.context.scene.objects['SprigganBodyLeaves'].active_material.node_tree.animation_data
    cb = next(cb for cb in kfxaction.layers[0].strips[0].channelbags
                    if cb.slot == mat_anim.action_slot)
    assert TT.is_eq(len(cb.fcurves), 1, "KillFX SprigganBodyLeaves fcurve count")
    assert TT.is_contains("Alpha Threshold", cb.fcurves[0].data_path, 
                          "KillFX SprigganBodyLeaves controlled property")
    assert TT.is_eq(len(cb.fcurves[0].keyframe_points), 4, "KillFX SprigganBodyLeaves keyframe count")
    assert TT.is_equiv(cb.fcurves[0].keyframe_points[0].co[1], 9.4442, 
                       "KillFX SprigganBodyLeaves First keyframe value")
    
    # SprigganFxTestUnified:0 has one slot & 4 fcurves controlling emission color & strength
    mat_anim = bpy.context.scene.objects['SprigganFxTestUnified:0'].active_material.node_tree.animation_data
    cb = next(cb for cb in kfxaction.layers[0].strips[0].channelbags
                    if cb.slot == mat_anim.action_slot)
    assert any('Emission Strength' in c.data_path for c in cb.fcurves), \
        "KillFX SprigganBodyLeaves has Emission Strength fcurve"
    assert any('Emission Color' in c.data_path for c in cb.fcurves), \
        "KillFX SprigganBodyLeaves has Emission Color fcurve"
    assert TT.is_eq(len(cb.fcurves), 4, "KillFX spriggan body fcurves")
    assert TT.is_contains("Emission Strength", cb.fcurves[3].data_path, "KillFX spriggan body controlled property")
    assert TT.is_eq(len(cb.fcurves[3].keyframe_points), 2, "KillFX spriggan body keyframes")
    assert TT.is_equiv(cb.fcurves[3].keyframe_points[0].co[1], 8, "KillFX spriggan body First keyframe value")
    assert TT.is_equiv(cb.fcurves[3].keyframe_points[1].co[1], 0, "KillFX spriggan body Second keyframe value")


def CheckBow(nif, nifcheck, bow):
    """Check that the glass bow nif is correct."""
    TTB.compare_shapes(nif.shape_dict['ElvenBowSkinned:0'], 
                      nifcheck.shape_dict['ElvenBowSkinned:0'],
                      bow)

    rootcheck = nifcheck.rootNode
    assert rootcheck.name == "GlassBowSkinned.nif", f"Root node name incorrect: {rootcheck.name}"
    assert rootcheck.blockname == "BSFadeNode", f"Root node type incorrect {rootcheck.blockname}"
    assert rootcheck.flags == 14, f"Root block flags set: {rootcheck.flags}"

    # Check the midbone transform
    mbc_xf = nifcheck.get_node_xform_to_global("Bow_MidBone")
    assert NT.VNearEqual(mbc_xf.translation, [1.3064, 6.3735, -0.0198]), f"Midbow in correct location: {str(mbc_xf.translation[:])}"
    m = BD.transform_to_matrix(mbc_xf).to_euler()
    assert NT.VNearEqual(m, [0, 0, -math.pi/2]), f"Midbow rotation is correct: {m}"

    # check the collisions
    midbowcheck = nifcheck.nodes["Bow_MidBone"]
    collcheck = midbowcheck.collision_object
    assert collcheck.blockname == "bhkCollisionObject", f"Collision node block set: {collcheck.blockname}"
    assert bhkCOFlags(collcheck.flags).fullname == "ACTIVE | SYNC_ON_UPDATE"

    bodycheck = collcheck.body
    p = bodycheck.properties
    assert p.collisionFilter_layer == SkyrimCollisionLayer.WEAPON, "Have correct collision layer"
    assert NT.VNearEqual(p.translation[0:3], [0.0931, -0.0709, 0.0006]), f"Collision body translation is correct: {p.translation[0:3]}"

    boxcheck = bodycheck.shape
    assert boxcheck.blockname == 'bhkBoxShape', "Box shape block correct"

    # Rotation and dimensions are related. Could check the bounds, which is a lot of math.
    # Instead check the values, but make sure the values give a good collision.
    #assert NT.VNearEqual(p.rotation[:], [0.0, 0.0, 0.0, 1.0]), f"Collision body rotation correct: {p.rotation[:]}"
    dimv = Vector(boxcheck.properties.bhkDimensions)
    p = bodycheck.properties
    rot = Quaternion((p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2],))
    dimv.rotate(rot)
    assert dimv.x > dimv.y > dimv.z, f"Have good collision bounds: {dimv}"

    bsxcheck = nifcheck.rootNode.get_extra_data(blockname='BSXFlags', name='BSX')
    assert TT.is_eq(bsxcheck.flags, 202, "BSX Flags")

    bsinvcheck = nifcheck.rootNode.get_extra_data(blockname='BSInvMarker', name='INV')
    assert TT.is_eq(bsinvcheck.rotation, (4712, 0, 785), "Inventory marker rotation")
    assert TT.is_equiv(bsinvcheck.zoom, 1.24038, "Inventory marker zoom")


def _np_bodies(nif):
    """The native-physics body each NIF node names, keyed by node name."""
    out = {}
    cache = {}
    for name, node in nif.nodes.items():
        co = node.collision_object
        if co is None or co.blockname != 'bhkNPCollisionObject':
            continue
        ps = co.physics_system
        if ps is None:
            continue
        if ps.id not in cache:
            cache[ps.id] = ps.geometry
        shapes = cache[ps.id]
        if co.body_id is None or co.body_id >= len(shapes):
            continue
        out[name] = shapes[co.body_id]
    return out


def _np_shape_verts(s):
    """All verts of a possibly-compound collision shape.

    Was a closure defined inside a loop, appending to an accumulator rebound each
    iteration -- safe only because it was called in the same iteration.
    """
    if s.shape_type == 'compound':
        out = []
        for c in s.children:
            out.extend(_np_shape_verts(c))
        return out
    return list(s.verts)


def _np_body_world_bounds(nif):
    """World-space AABB of every native-physics body, keyed by node name.

    The engine puts a body where its NIF node is, so a body's world extent is
    the node's global transform applied to the body's shape vertices.  Havok
    units; the node translation is in nif units, so scale the verts to match.
    """
    out = {}
    for name, body in _np_bodies(nif).items():
        pts = _np_shape_verts(body)
        if not pts:
            continue
        mx = BD.transform_to_matrix(nif.nodes[name].global_transform)
        world = [mx @ (Vector(v) * HAVOC_SCALE_FACTOR) for v in pts]
        out[name] = (Vector([min(w[i] for w in world) for i in range(3)]),
                     Vector([max(w[i] for w in world) for i in range(3)]))
    return out


def _np_body_filters(nif):
    """collisionFilterInfo of every native-physics body, keyed by node name."""
    return {name: body.physics.collision_filter_info
            for name, body in _np_bodies(nif).items() if body.physics}


def _hkx_skel_globals(skel):
    """Compute NIF-space global transforms for every bone in a loaded HKX skeleton.

    Mirrors the importer's reference-pose walk; used as ground truth in tests.
    """
    globals_ = []
    for i, p in enumerate(skel.reference_pose):
        q = Quaternion((p.rotation[3], p.rotation[0], p.rotation[1], p.rotation[2]))
        loc = Matrix.Translation(Vector(p.translation)) @ q.to_matrix().to_4x4()
        pidx = skel.parents[i] if i < len(skel.parents) else -1
        globals_.append(globals_[pidx] @ loc if 0 <= pidx < len(globals_) else loc)
    return globals_


def XXX_TEST_COLLISION_FO4():
    """
    FO4 collision export: Not working. Requires an update to Nifly to handle FO4-format
    bhkRigidBody blocks.
    """
    testfile = TTB.test_file(r"tests\FO4\AlarmClock_Bare.nif")
    outfile = TTB.test_file(r"tests\out\TEST_COLLISION_FO4.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    root = [obj for obj in bpy.data.objects if 'pynRoot' in obj][0]
    clock = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH'][0]

    BD.ObjectSelect([clock], active=True)
    bpy.ops.object.duplicate()
    collobj = bpy.context.object
    collobj.name = "bhkConvexVerticesShape"

    bpy.ops.object.add(type='EMPTY')
    rb = bpy.context.object
    rb.name = "bhkRigidBody"
    rb['broadPhaseType'] = "ENTITY"
    collobj.parent = rb

    bpy.ops.object.add(type='EMPTY')
    coll = bpy.context.object
    coll.name = "bhkCollisionObject"
    coll['pynCollisionFlags'] = "SYNC_ON_UPDATE"
    rb.parent = coll
    coll.parent = root

    BD.ObjectSelect([root], active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    coll = nifout.rootNode.collision_object
    body = coll.body
    assert coll.body


def UNITTEST_CUBE_INFO1():
    """Unit test to ensure we can analyze a rotated cube."""
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0,))
    cube = bpy.context.object
    cube.scale = Vector((1, 2, 3,))
    cube.rotation_mode = 'XYZ'
    testrot = (0.35, 1.4, 0)
    cube.rotation_euler = testrot
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    c, d, r = BD.find_box_info(bpy.context.object)
    assert BD.VNearEqual(c, (0, 0, 0)), f"Centerpoint at origin: {c}"
    assert BD.VNearEqual(d, (2, 4, 6)), f"Have correct dimensions: {d}"
    assert BD.VNearEqual(testrot, r.to_euler()[0:3]), f"Have correct rotation: {r}"


def UNITTEST_CUBE_INFO2():
    """Unit test to ensure we can analyze a rotated, translated cube."""
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0,))
    cube = bpy.context.object
    dims = Vector((1, 2, 3,))
    cube.scale = dims
    cube.rotation_mode = 'XYZ'
    testrot = (0.35, 1.4, 0.9)
    cube.rotation_euler = testrot
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    offset = Vector((3, 4, 5,))
    for v in cube.data.vertices:
        v.co += offset
    
    c, d, r = BD.find_box_info(bpy.context.object)
    # Centerpoint is returned as the world location of the geometric center.
    assert BD.VNearEqual(c, offset), f"Centerpoint at translated location: {c}"
    # Dimensions are in the box's local frame of reference. 
    assert BD.VNearEqual(d, dims*2), f"Have correct dimensions: {d}"
    # Rotation is what's required to rotate an aligned box to the actual box's position.
    assert BD.VNearEqual(testrot, r.to_euler()[0:3]), f"Have correct rotation: {r}"


def UNITTEST_CUBE_INFO3():
    """Unit test to ensure we can analyze a cube with translations and rotations on the object."""
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0,))
    cube = bpy.context.object
    dims = Vector((1, 2, 3,))
    cube.scale = dims
    cube.rotation_mode = 'XYZ'
    testrot = (0.35, 1.4, 0.9)
    cube.rotation_euler = testrot
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    offset = Vector((3, 4, 5,))
    for v in cube.data.vertices:
        v.co += offset
    
    objoffset = Vector((6, 7, 8,))
    objscale = 0.1
    cube.location = objoffset
    cube.scale = (objscale,)*3
    c, d, r = BD.find_box_info(bpy.context.object)
    # Centerpoint is returned as the world location of the geometric center.
    assert BD.VNearEqual(c, objoffset+cube.scale*offset), f"Centerpoint at translated location: {c}"
    # Dimensions are in world scale. 
    assert BD.VNearEqual(d, dims*2*cube.scale), f"Have correct dimensions: {d}"
    # Rotation is what's required to rotate an aligned box to the actual box's position.
    assert BD.VNearEqual(testrot, r.to_euler()[0:3]), f"Have correct rotation: {r}"


def LOAD_RIG():
    """Load an animation rig for play. Has to be invoked explicitly."""
    skelfile = TTB.test_file(r"tests\Skyrim\skeleton_vanilla.nif")
    hkxskelfile = TTB.test_file(r"tests\Skyrim\skeleton.hkx")
    bpfile1 = TTB.test_file(r"tests\Skyrim\malebody_1.nif")
    bpfile2 = TTB.test_file(r"tests\Skyrim\malehands_1.nif")
    bpfile3 = TTB.test_file(r"tests\Skyrim\malefeet_1.nif")
    bpfile4 = TTB.test_file(r"tests\Skyrim\malehead.nif")

    bpy.ops.import_scene.pynifly(filepath=skelfile,
                                 create_bones=False, 
                                 rename_bones=True,
                                 import_animations=False,
                                 blender_xf=True)
    BD.ObjectSelect([obj for obj in bpy.data.objects if obj.type == 'ARMATURE'], active=True)
    bpy.context.object['PYN_SKELETON_FILE'] = hkxskelfile
    bpy.ops.import_scene.pynifly(files=[{"name": bpfile1}, 
                                        {"name": bpfile2}, 
                                        {"name": bpfile3}, 
                                        {"name": bpfile4}],
                                 create_bones=False, 
                                 rename_bones=True,
                                 import_animations=False,
                                 blender_xf=True)


# Everything defined above is shared by every test module. Export it explicitly --
# a bare `import *` would skip the leading-underscore helpers (_np_bodies etc.).
__all__ = [_n for _n in list(globals()) if not _n.startswith('__')]
