"""Handles import/export of controller nodes."""
# Copyright © 2024, Bad Dog.

# TODO: Make sure flags on mesh allow animations

import os
from pathlib import Path
import logging
import traceback
from dataclasses import dataclass
from collections.abc import Iterator
import bpy
import bpy.props 
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
from pynifly import *
import blender_defs as BD
from nifdefs import *
import re


ANIMATION_NAME_MARKER = "ANIM"
ANIMATION_NAME_SEP = "|"
KFP_HANDLE_OFFSET = 10

# Animations come in at twice the speed. Not sure why. Apply an adjustment factor.
ANIMATION_TIME_ADJUST = 1


shader_nodes = {    
    "Fallout 4 MTS": "Lighting", 
    "FO4 Effect Shader": "Effect", 
    "SkyrimShader:Effect": "Effect", 
    "SkyrimShader:Default": "Lighting", 
} 

def _shader_game(nodename):
    if nodename.startswith("Fallout") or nodename.startswith('FO4'):
        return 'FO4'
    else:
        return 'SKYRIM'
    

def _determine_shader_name(game, shader_type):
    for k, n in shader_nodes.items():
        if n == shader_type:
            if _shader_game(k) == game:
                return k
    return None


class ControlledVariable:
    def __init__(self, var_list):
        self.variables = var_list

    def blend_find(self, node, socket, shader_type=None):
        """Find the right controlled variable given blender shader node and socket."""
        for n, s, d, t, v in self.variables:
            if n == node and s == socket:
                # If we were not given a shader type take any match. If the match isn't
                # for a shader, take it. If it is for a shader, has to match on the shader
                # type.
                if (not shader_type) or (
                    not (t.__name__.startswith("BSEffect") or t.__name__.startswith("BSLighting"))
                    ) or (t.__name__[0:8] == shader_type[0:8]):
                    return t, v
        return None, None
    
    def nif_find(self, game, ctltype, varid):
        """Find the right shader node and socket given a nif controller target."""
        for n, s, d, t, v in self.variables:
            if t == ctltype and varid == v:
                for nodename, nodetype in shader_nodes.items():
                    if nodetype == n:
                        if game == 'FO4' and 'Skyrim' not in nodename:
                            return nodename, s, d
                        if game in ['SKYRIM', 'SKYRIMSE'] and 'Skyrim' in nodename:
                            return nodename, s, d
                return n, s, d
        return None, None, None
        

controlled_vars = ControlledVariable([
    ("AlphaProperty", "Alpha Threshold", "inputs", BSNiAlphaPropertyTestRefController, 0),
    ("Effect", "Alpha Adjust", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.Alpha_Transparency),
    ("Effect", "Emission Strength", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.Emissive_Multiple),
    ("Effect", "Emission Strength", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.Falloff_Start_Angle),
    ("Effect", "Emission Strength", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.Falloff_Start_Opacity),
    ("Effect", "Emission Strength", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.Falloff_Stop_Angle),
    ("Effect", "Emission Strength", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.Falloff_Stop_Opacity),
    ("Fallout 4 MTS - Greyscale To Palette Vector", "Palette", "inputs", BSEffectShaderPropertyColorController, EffectShaderControlledColor.EMISSIVE),
    ("Lighting", "Alpha Mult", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.Alpha),
    ("Lighting", "Emission Color", "inputs", BSLightingShaderPropertyColorController, LightingShaderControlledColor.EMISSIVE),
    ("Lighting", "Emission Strength", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.Emissive_Multiple),
    ("Lighting", "Glossiness", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.Glossiness),
    ("Lighting", "Specular Color", "inputs", BSLightingShaderPropertyColorController, LightingShaderControlledColor.SPECULAR),
    ("Lighting", "Specular Str", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.Specular_Strength),
    ("UV_Converter", "Offset U", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.U_Offset),
    ("UV_Converter", "Offset U", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.U_Offset),
    ("UV_Converter", "Offset V", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.V_Offset),
    ("UV_Converter", "Offset V", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.V_Offset),
    ("UV_Converter", "Scale U", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.U_Scale),
    ("UV_Converter", "Scale U", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.U_Scale),
    ("UV_Converter", "Scale V", "inputs", BSEffectShaderPropertyFloatController, EffectShaderControlledVariable.V_Scale),
    ("UV_Converter", "Scale V", "inputs", BSLightingShaderPropertyFloatController, LightingShaderControlledVariable.V_Scale),
    # ("Alpha Threshold", "0", "outputs", BSNiAlphaPropertyTestRefController, EffectShaderControlledVariable.Alpha_Transparency),
])

active_animation = ""

_animation_pulldown_items = []


def sanitize_name(name:str):
    return name.replace(ANIMATION_NAME_SEP, ANIMATION_NAME_SEP*2)


def desanitize_name(name:str):
    return name.replace(ANIMATION_NAME_SEP*2, ANIMATION_NAME_SEP)


def make_action_name(animation_name=None, target_obj=None, target_elem=None):
    """
    Build an animation name suitable for applying to an action.
    """
    if animation_name:
        return animation_name
    elif target_obj is not None:
        return target_obj.name
    else:
        return "Animation"


def current_animations(nif, refobjs:BD.ReprObjectCollection):
    """
    Find all exportable animations for objects in refobjs.
    Returns a dictionary: {animation_name: [Animation], ...}
    """
    matches = {}
    for act in bpy.data.actions: 
        animdesc = None
        for s in act.slots:
            for u in s.users():
                t = (u in refobjs.blenderdict)
                t = t or (u.active_material and u.active_material.node_tree)
                if t:
                    animdesc = analyze_animation(act, s, bpy.context.scene, animdesc)
                    if act.name not in matches:
                        matches[act.name] = []
                    matches[act.name].append(s)

    return matches


def _animations_for_pulldown(self, context):
    """Find all animations and return them in a form suitable for a Blender pulldown."""
    _animation_pulldown_items = []
    found_names = set()
    for act in all_named_animations(BD.ReprObjectCollection.New(bpy.context.scene.objects)):
        found_names.add(act.name)

    for f in sorted(found_names):
        _animation_pulldown_items.append((f, f, "Animation"), )

    return _animation_pulldown_items


def apply_action(act):
    """Make the given action active in the scene."""
    for s in act.slots:
        if s.target_id_type == 'OBJECT':
            objname = s.name_display
            obj = bpy.context.scene.objects.get(objname)
            if obj:
                if not obj.animation_data:
                    obj.animation_data_delete()
                    obj.animation_data_create()
                obj.animation_data.action = act
                obj.animation_data.action_slot = s
    bpy.context.scene.frame_start = int(act.frame_start)
    bpy.context.scene.frame_end = int(act.frame_end)


@dataclass
class AnimationData:
    name: str = ""
    action = None
    slot = None
    target_obj = None
    target_elem = None
    start_time: float = 10000.0
    stop_time: float = -10000.0
    start_frame: int = 10000
    stop_frame: int = -10000
    cycle_type: CycleType = CycleType.LOOP
    frequency: float = 1.0
    markers: dict = None


def all_actions():
    """Iterator returning all actions and slots."""
    for act in bpy.data.actions:
        for slot in act.slots:
            yield act, slot


def all_obj_animations(export_objs:BD.ReprObjectCollection):
    """Iterator returning quads: (action, slot, target_obj, target_elem)"""
    for act in bpy.data.actions:
        for slot in act.slots:
            targ = elem = None
            for reprobj in export_objs:
                obj = reprobj.blender_obj
                if slot.target_id_type == 'NODETREE':
                    if obj.active_material and 'pynActionSlots' in obj.active_material.node_tree:
                        for avail_actions in obj.active_material.node_tree['pynActionSlots'].split('||'):
                            actionname, slotname = avail_actions.split('|')
                            if actionname == act.name and slotname == slot.name_display:
                                targ = reprobj
                                elem = obj.active_material.node_tree
                                yield act, slot, targ, elem
                else: 
                    if 'pynActionSlots' in obj:
                        for avail_actions in obj['pynActionSlots'].split('||'):
                            actionname, slotname = avail_actions.split('|')
                            if actionname == act.name and slotname == slot.name_display:
                                targ = reprobj
                                elem = None
                                yield act, slot, targ, elem


def all_named_animations(export_objs:BD.ReprObjectCollection) -> Iterator[AnimationData]:
    """
    Iterator returning all actions/slots that are exportable as named animations
    representable as controller sequences. They must have a target that is being exported
    and has the 'pynActionSlots' property.
    """
    ## TODO: What if they animate something we can't export? Maybe return everything and 
    ## let later parts of the code decide.

    for act, slot, targ, elem in all_obj_animations(export_objs):
        if act.get('pynController', '') == 'NiControllerSequence':
            res = AnimationData()
            res.name = act.name
            res.action = act
            res.slot = slot
            res.target_obj = targ
            res.target_elem = elem
            res.start_time = (act.frame_start - 1) / bpy.context.scene.render.fps
            res.stop_time = (act.frame_end - 1) / bpy.context.scene.render.fps
            res.start_frame = act.frame_start
            res.stop_frame = act.frame_end
            res.cycle_type = CycleType.LOOP if act.use_cyclic else CycleType.CLAMP

            res.markers = {}
            for m in act.pose_markers:
                res.markers[m.name] = (m.frame - 1) / bpy.context.scene.render.fps

            yield res


def apply_animation(anim_name, myscene):
    """
    Apply the named animation to the currently visible objects.
    """
    act = None
    for act, slot, targobj, elem in all_obj_animations(
            BD.ReprObjectCollection.New(myscene.objects)):
        if act.name == anim_name:
            if elem:
                targ = elem
            else:
                targ = targobj.blender_obj
            targ.animation_data_clear()
            targ.animation_data_create()
            targ.animation_data.action = act
            targ.animation_data.action_slot = slot
            myscene.frame_start = math.floor(act.curve_frame_range[0])
            myscene.frame_end = math.ceil(act.curve_frame_range[1])
    if not act:
        log = logging.getLogger("pynifly")
        log.error(f"Animation not found: {anim_name}")


def actionslot_fcurves(action, slot):
    """Return all fcurves in the given action slot."""
    res = []
    for layer in action.layers:
        for strip in layer.strips:
            cb = strip.channelbag(slot)
            if cb:
                res.extend(cb.fcurves)
    return res


def analyze_animation(anim:bpy.types.Action, slot:bpy.types.ActionSlot, 
                      myscene, export_objs:BD.ReprObjectCollection) -> AnimationData:
    """
    Analyze the given action and slot but do not apply it. If it's exportable as an
    animation, return an AnimationData object. Otherwise return None.
    """
    res = AnimationData()

    for name, robj in export_objs.blenderdict.items():
        obj = robj.blender_obj
        if obj.name == slot.name_display:
            res.target_obj = robj
            break
        if obj.active_material and obj.active_material.node_tree:
            if obj.active_material.node_tree.name == slot.name_display:
                res.target_obj = robj
                res.target_elem = obj.active_material.node_tree
                break

    res.name = anim.name
    res.action = anim
    res.slot = slot
    res.start_time = (anim.frame_start - 1) / myscene.render.fps
    res.stop_time = (anim.frame_end - 1) / myscene.render.fps
    res.start_frame = anim.frame_start
    res.stop_frame = anim.frame_end
    res.cycle_type = CycleType.LOOP if anim.use_cyclic else CycleType.CLAMP

    res.markers = {}
    if "pynMarkers" in anim:
        for name, val in anim["pynMarkers"].items():
            res.markers[name] = val

    return res


def curve_bone_target(curve):
    """
    Return the curve target and type for the curve. The target is the bone name if any,
    otherwise ''. Type is '.location', '.scale', etc.
    """
    m = re.match(r"""pose.bones\[('|")([^'"]+)('|")\]\.?(.*)""", curve.data_path)
    if m: 
        return m.groups()[1], m.groups()[3]
    else:
        return '', curve.data_path


class ControllerHandler():
    def __init__(self, parent_handler, objlist:BD.ReprObjectCollection=None):
        self.action = None
        self.action_group = ""
        self.action_name = ""
        self.action_name_root = ""
        self.frame_end = 0
        self.frame_start = 0
        self.parent = parent_handler
        self.path_name = None
        self.animation_target = None  
        self.action_target = None # 
        self.accum_root = None
        self.given_scale_warning = False
        self.export_objs = objlist
        self.action_slot = None
        self.channelbag = None

        # Single MultiTargetTransformController and ObjectPalette to use fo all controller
        # sequences in a ControllerManager
        self.cm_controller = None 
        self.controller_sequence:NiControllerSequence = None
        self.cm_obj_palette = None
        
        self.controlled_objects = set()
        self.start_time = sys.float_info.max
        self.end_time = -sys.float_info.max

        # Necessary context from the parent.
        self.nif = parent_handler.nif
        self.context:bpy.types.Context = parent_handler.context
        self.fps = parent_handler.context.scene.render.fps
        self.logger = logging.getLogger("pynifly")
        self.auxbones = None
        if hasattr(parent_handler, "auxbones"): 
            self.auxbones = parent_handler.auxbones
        self.nif_name = None
        if hasattr(parent_handler, "nif_name"): 
            self.nif_name = parent_handler.nif_name
        self.blender_name = None
        if hasattr(parent_handler, "blender_name"): 
            self.blender_name = parent_handler.blender_name
        self.objects_created = None
        if hasattr(parent_handler, "objects_created"):
            self.objects_created:BD.ReprObjectCollection = parent_handler.objects_created
        if hasattr(parent_handler, "objs_written"):
            self.objects_created:BD.ReprObjectCollection = parent_handler.objs_written

        self.export_each_frame = False


    def warn(self, msg):
        self.logger.warning(msg)


    def _find_target(self, nifname):
        """
        Find the blender object 
        """
        try:
            nifnode = self.nif.nodes[nifname]
            return self.objects_created.find_nifnode(nifnode).blender_obj
        except:
            return None


    def _find_nif_target(self, blendname):
        nifname = self.nif_name(blendname)
        if nifname in self.nif.nodes:
            return self.nif.nodes[nifname]
        return None


    def _key_nif_to_blender(self, key0, key1, key2):
        """
        Return blender fcurve handle values for key1.

        key0 and key2 may be omitted if key1 is first or last.
        """
        frame1 = key1.time*(self.fps * ANIMATION_TIME_ADJUST)+1
        if key2:
            frame2 = key2.time*(self.fps * ANIMATION_TIME_ADJUST)+1
            frame_delt_r = (frame2 - frame1)
            slope_right = key1.backward/frame_delt_r
        else:
            frame_delt_r = 1
            slope_right = key1.backward

        if key0:
            frame0 = key0.time * (self.fps * ANIMATION_TIME_ADJUST) + 1
            frame_delt_l = (frame1 - frame0)
            slope_left = key1.forward/frame_delt_l
        else:
            frame_delt_l = 1
            slope_left = key1.forward

        partial = 1/3
        handle_l = Vector((frame1 - frame_delt_l*partial, key1.value - slope_left*frame_delt_l*partial))
        handle_r = Vector((frame1 + frame_delt_r*partial, key1.value + slope_right*frame_delt_r*partial))
        
        return handle_l, handle_r


    def _point3key_nif_to_blender(self, key0, key1, key2, i):
        """
        Return blender fcurve handle values for key1.

        key0 and key2 may be omitted if key1 is first or last.
        """
        _key0 = None
        if key0:
            _key0 = NiAnimKeyFloatBuf(time=key0.time,
                                      value=key0.value[i],
                                      forward=key0.forward[i],
                                      backward=key0.backward[i],)
        _key1 = None
        if key1:
            _key1 = NiAnimKeyFloatBuf(time=key1.time,
                                      value=key1.value[i],
                                      forward=key1.forward[i],
                                      backward=key1.backward[i],)
        _key2 = None
        if key2:
            _key2 = NiAnimKeyFloatBuf(time=key2.time,
                                      value=key2.value[i],
                                      forward=key2.forward[i],
                                      backward=key2.backward[i],)

        return self._key_nif_to_blender(_key0, _key1, _key2)


    def _import_interp_controller(self, fi:NiInterpController, interp:NiInterpController):
        """Import a subclass of NiInterpController."""
        fi.import_node(self, interp)


    def _import_color_controller(self, seq:NiSequence, block:ControllerLink):
        """Import one color controller block."""
        if block.node_name in self.nif.nodes:
            target_node = self.nif.nodes[block.node_name]

            target_obj = self.objects_created.find_nifnode(target_node).blender_obj
            if not target_obj:
                self.warn(f"Target object was not imported: {block.node_name}")
                return
        else:
            self.warn(f"Target block not found in nif. Is it corrupt? ({block.node_name})")

        self.action_group = "Color Property Transforms"
        self.path_name = None
        self.action_name = f"{block.node_name}_{seq.name}"


    def _new_animation(self, anim_context):
        """
        Set up to import a new animation from the nif file.

        Nif animations can control multiple elements and multiple types of elements.
        Blender actions are associated with a single element. So it may require mulitple
        blender actions to represent a nif animation. 
        """
        self.context.scene.timeline_markers.clear()
        self.animation_actions = []
        self.action = None

        self.action_name = ""
        self.action_group = ""
        self.path_name = ""
        self.frame_start = 1
        self.frame_end = 1
        self.is_cyclic = anim_context.is_cyclic
        self.action_slot = None
        self.channelbag = None


    def _new_action(self, name_suffix=None):
        """
        Create a new action to represent all or part of a nif animation.
        """
        if not self.animation_target:
            self.warn("No animation target") 

        suf = name_suffix
        if suf is None:
            suf = self.action_group
        self.action_name = make_action_name(self.anim_name, self.animation_target, suf)

        ## Create the action. Ignore any existing action on the target.
        self.action = bpy.data.actions.new(self.action_name)
        self.action.frame_start = self.frame_start
        self.action.frame_end = self.frame_end
        self.action.use_frame_range = True
        self.action.use_cyclic = self.is_cyclic 
        self.anim_name = self.action.name # Just in case Blender added a suffix
        if self.controller_sequence:
            self.action['pynController'] = 'NiControllerSequence'
        self.action_slot = None
        self.channelbag = None

        # Some nifs have multiple animations with different names. Others just animate
        # various nif blocks. If there's a name, make this an asset so we can track them.
        if self.anim_name:
            self.action.use_fake_user = True
            self.action.asset_mark()
            self.animation_actions.append(self.action)


    def _new_slot(self):
        """
        Set up to store fcurves in a new action slot for the controller action.
        The slot itself is created when the first fcurve is addded.
        """
        try:
            if self.action_target and self.action_target.type == 'ARMATURE' and not self.bone_target:
                self.bone_target = self._find_target(self.action_target.name)
        except:
            self.action_target = None
        if not self.action_target: return

        if (not self.action_target.animation_data) or (
                self.action_target.animation_data.action != self.action):
            self.action_target.animation_data_clear()
            self.action_target.animation_data_create()
            self.action_target.animation_data.action = self.action
            self.action_target.animation_data.action_slot = None

        # The channelbag will be created when we add fcurves.
        self.channelbag = None


    def _record_slot(self):
        """
        Record the action slot handle on the target object for export later. An object may
        have multiple action slots if it has multiple named animations or if multiple
        properties are being animated. We store slot handles in a custom property
        'pynActionSlots' as a tuple of integers. Each integer is an action slot handle.
        During export, we look for this property to find which action slots apply to this
        object.

        Also set the frame range to include these fcurves.
        """
        if self.action_target.animation_data and self.action_target.animation_data.action_slot:
            s = self.action_target.animation_data.action_slot
            val = f"{self.action.name}|{s.name_display}"
            try:
                if 'pynActionSlots' in self.action_target:
                    if val not in self.action_target['pynActionSlots']:
                        self.action_target['pynActionSlots'] = f"{self.action_target['pynActionSlots']}||{val}"
                else:
                    self.action_target['pynActionSlots'] = val
            except Exception as e:
                log.warn(f"Could not assign action slot for {self.action_target}: {e}")

            # Expand the action's frame range to cover these fcurves.
            mintime = min([
                fc.keyframe_points[0].co[0] for fc in BD.action_fcurves(self.action)])
            maxtime = max([
                fc.keyframe_points[-1].co[0] for fc in BD.action_fcurves(self.action)])
            self.action.frame_start = round(min(self.action.frame_start, mintime))
            self.action.frame_end = round(max(self.action.frame_end, maxtime))
            self.context.scene.frame_start = round(self.action.frame_start)
            self.context.scene.frame_end = round(self.action.frame_end)


    def _animate_bone(self, bone_name:str):
        """
        Set up to import the animation of a bone as part of a larger animation. 
        
        Returns TRUE if the target bone was found, FALSE otherwise.
        """
        # Armature may have had bone names converted or not. Check both ways.
        name = bone_name
        if name not in self.animation_target.data.bones:
            name = self.blender_name(name)
            if name not in self.animation_target.data.bones:
                # Some nodes are uppercase in the skeleton but not in the animations.
                # Don't know if they are ignored in game or if the game is doing
                # case-insensitive matching.
                self.warn(f"Controller target not found: {bone_name}")
                return False
            
        self.action_group = name
        self.bone_target = self.animation_target.pose.bones[name]
        self.path_name = f'pose.bones["{name}"]'
        return True


    def _new_bone_anim(self, ctlr):
        """
        Set up to import the animation of a bone as part of a larger animation. 
        
        Returns TRUE if the target bone was found, FALSE otherwise.
        """
        if not self.action_target:
            self.warn("No action target in _new_bone_anim")

        if self.bone_target:
            name = self.bone_target.name
        else:
            name = self.animation_target.name
        
        self.path_name = f'pose.bones["{name}"]'
        self.animation_target = self.action_target.pose.bones[name]
        self.action_group = name


    def _new_element_action(self, anim_context, target_name, property_type, suffix):
        """
        Set up info to create an action slot to animate a single element (bone, shader,
        node). This may be part of a larger nif animation/blender action. The actual
        action and action slot aren't created until we load the interpolator, because for
        various reasons we might never get there.

        target_name is the name of the target in the nif file.
         
        Returns TRUE if the target element was found, FALSE otherwise.
        """
        try:
            targ = self.objects_created.find_nifname(self.nif, target_name)
            self.animation_target = targ.blender_obj
            if property_type in ['BSEffectShaderProperty', 'BSLightingShaderProperty',
                                 'NiAlphaProperty']:
                self.action_target = targ.blender_obj.active_material.node_tree
                suffix = "Shader"
            else:
                self.action_target = targ.blender_obj
            if self.action_target:
                return True
        except:
            pass

        self.warn(f"Target of controller not found: {target_name}")
        return False
            

    def _new_transform_action(self, ctlr):
        """
        Create a new standalone NiTransform animation.

        NiNodes that are imported into an armature have to have an action on the armature
        with a path that references the bone, and it's one action for all the bones.
        NiNodes that are imported as EMPTYs have their action on the EMPTY itself and it's
        a separate action for each EMPTY.
        """
        if self.action_target and self.action_target.type == 'ARMATURE':
            if not self.action_target.animation_data:
                self._new_animation(ctlr)
                self._new_action("Transform")
            self._new_bone_anim(ctlr)
        else:
            self._new_animation(ctlr)
            self._new_element_action(ctlr, ctlr.target.name, "Transform")
        ctlr.import_node(self, ctlr.interpolator)


    def _new_armature_action(self, anim_context):
        """
        Create an action to animate an armature.
        
        Animating an armature means moving the bone pose positions around. It is
        represented in Blender as a single action.
        """
        self._new_action("Pose")
        self.action_group = "Object Transforms"


    def _import_controller_link(self, seq:NiSequence, block:ControllerLink):
        """
        Import one controlled block.

        Imports a single controller link (Controlled Block) within a ControllerSequence
        block. One element will be animated by this link block, but may require multiple
        fcurves.
        """
        try:
            # Animating an armature just needs one slot--each bone gets its own fcurve.
            # Otherwise one slot per controller link block.
            if self.animation_target.type == 'ARMATURE':
                if not self._animate_bone(block.node_name):
                    return
                if not self.action_slot:
                    self._new_slot()
            else:
                if not self._new_element_action(
                    seq, block.node_name, block.property_type, None):
                    return
                self._new_slot()

            if block.controller:
                block.controller.import_node(self, block.interpolator)

            if block.interpolator:
                # If there's no controller, everything is done by the interpolator.
                block.interpolator.import_node(self, None)

            self._record_slot()

        except Exception as e:
            log.exception(f"Error importing sequence {seq.name}: {e}")

    def _import_text_keys(self, tk:NiTextKeyExtraData):
        for time, val in tk.keys:
            m = self.action.pose_markers.new(val)
            m.frame = round(time*(self.fps * ANIMATION_TIME_ADJUST))+1


    # --- PUBLIC FUNCTIONS ---

    def import_controller(self, ctlr, target_object=None, target_element=None, target_bone=None,
                          animation_name=None):
        """
        Import the animation defined by a controller block.
        
        ctlr = 
            May be a NiControllerManager containg multiple named sequences. Each sequence
            is a separate action with slots for each target object/material.

            May be a NiTransformController on an individual bone, part of the armature's
            animation. it will be imported as additional fcurves on the armature action.

            May be a NiTransformController on a node in a nif. The nif may have other animated
            nodes. Animations will be imported as slots on a single action.

        target_object = The blender object controlled by the animation, e.g. armature, mesh object.
        
        target_element = The blender object an action must be bound to, e.g. bone, material.
        """
        self.animation_target = target_object
        self.action_target = target_element
        if not self.action:
            if hasattr(ctlr, "name"):
                self.anim_name = ctlr.name
            else:
                self.anim_name = Path(ctlr.file.filepath).stem
            self._new_animation(ctlr)
        self.bone_target = target_bone

        ctlr.import_node(self)


    def import_bone_animations(self, arma):
        """Load any animations associated with individual armature bones."""
        for b in arma.data.bones:
            nifbone = self._find_nif_target(b.name)
            if nifbone and nifbone.controller:
                self.import_controller(nifbone.controller, arma, arma, b)


    @classmethod
    def import_block(controller_class, controller_block, parent, 
                     target_object=None):
        """
        Import a single controller block. 

        * controller_block = block to import
        * parent = NifImporter object holding context
        * target_object = target being controlled.
        """
        importer = ControllerHandler(parent)
        importer.import_controller(controller_block, target_object=target_object)


    ### EXPORT ###

    def _key_blender_to_nif(self, kfp0, kfp1, kfp2):
        """
        Return nif key values for keyframe point kfp1.

        kfp0 and kfp2 may be omitted if kfp1 is first or last.
        """
        slope_right = (kfp1.handle_right[1]-kfp1.co.y) / (kfp1.handle_right[0]-kfp1.co.x)
        slope_left = (kfp1.handle_left[1]-kfp1.co.y) / (kfp1.handle_left[0]-kfp1.co.x)
        
        if kfp0:
            forward = slope_left * (kfp1.co.x-kfp0.co.x)
        else:
            forward = slope_left
        if kfp2:
            backward = slope_right * (kfp2.co.x-kfp1.co.x)
        else:
            backward = slope_right

        return forward, backward


    def _get_curve_linear_values(self, curve):
        """
        Transform a blender curve into nif keys. 
        Returns [[time, value]...] for each keyframe in the curve.
        """
        keys = []
        for k in curve.keyframe_points:
            k = NiAnimKeyLinearXYZBuf()
            k.time = (k.co.x-1) / ( self.fps * ANIMATION_TIME_ADJUST)
            k.value = k.co.y
            keys.append(k)
        return keys


    def _get_curve_quad_values(self, curve):
        """
        Transform a blender curve into nif keys. 
        Returns [NiAnimKeyFloatBuf, ...] for each keyframe in the curve.
        """
        keys = []
        points = [None] + list(curve.keyframe_points) + [None]
        while points[1]:
            if points[1].interpolation == 'BEZIER':
                k = QuadScalarKey()
            elif points[1].interpolation == 'LINEAR':
                k = LinearScalarKey()
            else:
                k = LinearScalarKey()
                self.warn(f"Unsupported interpolation type {points[1].interpolation}, using LINEAR")
            k.time = (points[1].co.x-1) / (self.fps * ANIMATION_TIME_ADJUST)
            k.value = points[1].co.y
            if points[1].interpolation == 'BEZIER':
                k.forward, k.backward = self._key_blender_to_nif(points[0], points[1], points[2])
            keys.append(k)
            points.pop(0)
        return keys


    def _get_curve_quad_vector(self, curvexyz, basexf=Matrix.Identity(4)):
        """
        Transform a blender curve into nif keys. 

        curvexyz = List of 3 fcurves, holding the x, y, & z curves.
        Returns [NiAnimKeyQuadTransBuf, ...] for each keyframe in the curve.
        """
        kx = self._get_curve_quad_values(curvexyz[0])
        ky = self._get_curve_quad_values(curvexyz[1])
        kz = self._get_curve_quad_values(curvexyz[2])

        out_list = []
        for x, y, z in zip(kx, ky, kz):
            k = NiAnimKeyQuadTransBuf()
            if not all_NearEqual([x.time, y.time, z.time]):
                raise Exception(f"Time values do not match")
            k.time = x.time
            k.value[0] = x.value + basexf.translation.x
            k.value[1] = y.value + basexf.translation.y
            k.value[2] = z.value + basexf.translation.z
            k.forward[0] = x.forward
            k.forward[1] = y.forward
            k.forward[2] = z.forward
            k.backward[0] = x.backward
            k.backward[1] = y.backward
            k.backward[2] = z.backward
            out_list.append(k)
        return out_list


    def _add_controlled_object(self, obj:BD.ReprObject):
        """
        Add the object and all its children recursively to the set of controlled objects.
        """
        self.controlled_objects.add(obj)
        for child in obj.blender_obj.children:
            if child.type in ['EMPTY', 'MESH']:
                ro = self.objects_created.find_blend(child)
                if ro: self._add_controlled_object(ro)
        

    def _write_controlled_objects(self, cm:NiControllerManager):
        if len(self.controlled_objects) == 0: return

        for obj in self.controlled_objects:
            self.cm_obj_palette.add_object(obj.nifnode.name, obj.nifnode)


    def _select_controller(self, dp, shader_type=None):
        """
        Determine the controller class and controlled variable needed to represent an
        fcurve in a nif file.
        """
        if (dp.startswith("location") or dp.startswith("rotation")):
            ctlclass = NiTransformController
            return ctlclass, None
        elif dp.startswith("node"):
            fcurve_match = re.match(
                r"""nodes\[['"]([^]]+)['"]\].(inputs|outputs)\[['"]([^]]+)['"]\]""", dp)
            if not fcurve_match:
                raise Exception(f"Could not handle animation fcurve: {dp}")
            
            node_name, i_o, socket_name = fcurve_match.groups()
            if node_name in shader_nodes:
                node_type = shader_nodes[node_name]
            else: 
                node_type = node_name
            return controlled_vars.blend_find(node_type, socket_name, shader_type)


    def _export_activated_obj(self, anim:AnimationData):
        """
        Export a single activated object--an object with animation_data on it. 

        Returns a list of controller/interpolator pairs created. May have to be more than
        one if several variables are controlled, or if both variables and color are
        controlled.
        """
        interps_created = []
        controller = None # self.cm_controller
        ctlvar = ctlvar_cur = None
        ctlclass = ctlclass_cur = None
        self.action = anim.action
        self.start_time=(self.action.curve_frame_range[0]-1)/(self.fps * ANIMATION_TIME_ADJUST)
        self.stop_time=(self.action.curve_frame_range[1]-1)/(self.fps * ANIMATION_TIME_ADJUST)
        fcurves = actionslot_fcurves(anim.action, anim.slot)
        shader_type = None
        if anim.target_elem and anim.target_elem.type == 'SHADER':
            shader_type = anim.target_obj.nifnode.shader.blockname
        try:
            while fcurves:
                ctlclass, ctlvar = self._select_controller(fcurves[0].data_path, shader_type)
                if ctlclass is None:
                    self.warn(f"Could not export fcurve {fcurves[0].data_path} on {anim.target_obj.name}")
                    fcurves.pop(0)
                    continue

                if ((ctlclass != ctlclass_cur) or (ctlvar != ctlvar_cur)
                    or (ctlclass_cur is None)):

                    # New node type needed, start a new controller/interpolator pair
                    mytarget = anim.target_obj.nifnode
                    if issubclass(ctlclass, BSNiAlphaPropertyTestRefController):
                        mytarget = anim.target_obj.nifnode.alpha_property
                    elif anim.target_elem and anim.target_elem.type == 'SHADER':
                        mytarget = anim.target_obj.nifnode.shader

                    grp, interp = ctlclass.fcurve_exporter(self, fcurves, anim.target_obj)

                    if self.controller_sequence:
                        myinterp = ctlclass.blend_interpolator(self)
                        myparent = None
                    else:
                        myinterp = interp
                        myparent = anim.target_obj.nifnode.shader

                    if self.cm_controller and issubclass(ctlclass, NiTransformController):
                        controller = self.cm_controller

                    elif (ctlclass != NiTransformController): 
                        if mytarget.controller is None:
                            controller = ctlclass.New(
                                file=self.nif,
                                flags=TimeControllerFlags(
                                    cycle_type=(CycleType.LOOP if self.action.use_cyclic else CycleType.CLAMP),
                                    manager_controlled=(self.cm_controller is not None)
                                ).flags,
                                target=mytarget,
                                start_time=self.start_time,
                                stop_time=self.stop_time,
                                next_controller=controller,
                                interpolator=myinterp,
                                var=ctlvar,
                                parent=myparent)
                        else:
                            controller = mytarget.controller
                        
                    interps_created.append((controller, interp))

                ctlclass_cur = ctlclass
                ctlvar_cur = ctlvar

            # Target has to point to the first controller in the chain (but the chain
            # was built from last to first).
            if mytarget.properties.controllerID == NODEID_NONE and interps_created:
                mytarget.controller = interps_created[-1][0]
                
        except:
            log.exception(f"Error exporting fcurves to class {ctlclass} for {anim.name}")
        
        return interps_created
            

    def _export_text_keys(self, action:bpy.types.Action, cs:NiControllerSequence):
        """
        Export any timeline markers to the given NiControllerSequence as text keys.
        """
        tked = None
        
        for m in action.pose_markers:
            if not tked:
                tked = NiTextKeyExtraData.New(file=self.nif, parent=cs)
            tked.add_key((m.frame-1)/(self.fps * ANIMATION_TIME_ADJUST), m.name)


    def _export_anim_markers(self, cs:NiControllerSequence, markers):
        """
        Export any timeline markers to the given NiControllerSequence as text keys.
        markers = {name, timestamp}
        """
        ordered_markers = [(v, n) for n, v in markers.items()]
        if ordered_markers:
            ordered_markers.sort()
            tked = NiTextKeyExtraData.New(file=self.nif, parent=cs)
            for v, n in ordered_markers:
                tked.add_key(v, n)


    def _export_animations(self):
        """
        Export any actions that represent named nif animations to the target nif.
        """
        self.accum_root = self.nif.rootNode
        self.controlled_objects = BD.ReprObjectCollection()

        cm:NiControllerManager = None

        anim:BD.ReprObjectCollection = None
        for anim in all_named_animations(self.export_objs):
            # Don't create the nif container blocks until we need them.
            if not self.cm_controller:
                self.cm_controller = NiMultiTargetTransformController.New(
                    file=self.nif, flags=108, target=self.nif.rootNode)
                
            if not cm:
                cm = NiControllerManager.New(
                    file=self.parent.nif, 
                    flags=TimeControllerFlags(cycle_type=CycleType.CLAMP),
                    next_controller=self.cm_controller,
                    parent=self.accum_root)

            if not self.cm_obj_palette:
                self.cm_obj_palette = NiDefaultAVObjectPalette.New(self.nif, self.nif.rootNode, parent=cm)

            if (not self.controller_sequence) or (anim.name != self.controller_sequence.name):
                self.controller_sequence:NiControllerSequence = NiControllerSequence.New(
                    file=self.parent.nif,
                    name=anim.name,
                    accum_root_name=self.parent.nif.rootName,
                    start_time=anim.start_time,
                    stop_time=anim.stop_time,
                    cycle_type=anim.cycle_type,
                    frequency=anim.frequency,
                    parent=cm
                )

            self._export_anim_markers(self.controller_sequence, anim.markers)

            # if the target is an ARMATURE, do something different
            interps = []
            try:
                interps = self._export_activated_obj(anim)
            except:
                log.exception(f"Could not export animation {anim.name} on object {anim.target_obj.blender_obj.name}")
            
            for ctlr, intp in interps:
                self.controller_sequence.add_controlled_block(
                    name=anim.target_obj.nifnode.name,
                    interpolator=intp,
                    controller=ctlr,
                    controller_type=(ctlr.blockname 
                                        if ctlr.blockname != 'NiMultiTargetTransformController'
                                        else 'NiTransformController'),
                )
            self.cm_obj_palette.add_object(anim.target_obj.nifnode.name, anim.target_obj.nifnode)

        self._write_controlled_objects(cm)


    @classmethod
    def export_animation(cls, parent_handler, arma):
        """Export one action to one animation KF file."""
        exporter = ControllerHandler(parent_handler)
        exporter.nif = parent_handler.nif
        exporter.controller_sequence = exporter.nif.rootNode
        exporter.action = arma.animation_data.action
        cp = exporter.controller_sequence.properties.copy()
        exporter.start_time = cp.startTime = (exporter.action.curve_frame_range[0]-1)/exporter.fps
        exporter.stop_time = cp.stopTime = (exporter.action.curve_frame_range[1]-1)/exporter.fps
        cp.cycleType = CycleType.LOOP if exporter.action.use_cyclic else CycleType.CLAMP
        cp.frequency = 1.0
        exporter.controller_sequence.properties = cp
        exporter._export_text_keys(exporter.action, exporter.controller_sequence)

        # Collect list of curves. They will be picked off in clumps until the list is empty.
        curve_list = list(exporter.action.fcurves)
        while curve_list:
            bonename, ti = NiTransformController.fcurve_exporter(exporter, curve_list, arma)
            nifbonename = exporter.nif_name(bonename)

            exporter.controller_sequence.add_controlled_block(
                name=nifbonename,
                interpolator=ti,
                controller_type="NiTransformController"
            )


    @classmethod
    def export_animated_armature(cls, parent_handler, arma):
        """
        Export an animated skinned mesh (loadscreenalduinwall.nif).
        """
        if not arma.animation_data:return

        exporter = ControllerHandler(parent_handler)
        exporter.nif = parent_handler.nif

        exporter.action = arma.animation_data.action
        exporter.start_time=(exporter.action.curve_frame_range[0]-1)/exporter.fps
        exporter.stop_time=(exporter.action.curve_frame_range[1]-1)/exporter.fps
        curves = list(exporter.action.fcurves)
        while curves:
            bonename, ti = NiTransformController.fcurve_exporter(exporter, curves, arma)
            nifbonename = exporter.nif_name(bonename)
            # KF animation files have no controllers, so only create one if the target
            # bone exists in the nif.
            if nifbonename in exporter.nif.nodes:
                nifbone = exporter.nif.nodes[nifbonename]
                ctlr = NiTransformController.New(
                    file=exporter.nif,
                    flags=TimeControllerFlags(
                            cycle_type=CycleType.LOOP if exporter.action.use_cyclic else CycleType.CLAMP)
                            .flags,
                    start_time=exporter.start_time,
                    stop_time=exporter.stop_time,
                    interpolator=ti,
                    target=nifbone,
                    parent=nifbone
                    )


    @classmethod
    def export_animated_obj(cls, parent_handler, obj):
        """
        Export an animated object.
        """
        if not obj.animation_data: return
        if not obj.animation_data.action: return
        if obj.animation_data.action.get('pynController', '') == 'NiControllerSequence':
            return

        exporter = ControllerHandler(parent_handler)
        exporter.nif = parent_handler.nif

        exporter.action = obj.animation_data.action
        exporter.action_slot = obj.animation_data.action_slot
        exporter.start_time=(exporter.action.curve_frame_range[0]-1)/exporter.fps
        exporter.stop_time=(exporter.action.curve_frame_range[1]-1)/exporter.fps
        curves = []
        for lay in exporter.action.layers:
            for strip in lay.strips:
                for b in strip.channelbags:
                    if b.slot == exporter.action_slot:
                        curves = list(b.fcurves)
                        break

        while curves:
            targetnodename, ti = NiTransformController.fcurve_exporter(exporter, curves, obj)
            nifnodename = exporter.nif_name(targetnodename)
            # KF animation files have no controllers, so only create one if the target
            # bone exists in the nif.
            if nifnodename in exporter.nif.nodes:
                nifnode = exporter.nif.nodes[nifnodename]
                ctlr = NiTransformController.New(
                    file=exporter.nif,
                    flags=TimeControllerFlags(
                            cycle_type=CycleType.LOOP if exporter.action.use_cyclic else CycleType.CLAMP)
                            .flags,
                    start_time=exporter.start_time,
                    stop_time=exporter.stop_time,
                    interpolator=ti,
                    target=nifnode,
                    parent=nifnode
                    )


    @classmethod
    def export_shader_controller(cls, parent_handler, activeobj:BD.ReprObject, activeelem):
        """Export an obj that has an animated shader."""

        a = activeelem.animation_data.action

        # If the animation is a named animation, it will be part of a controller 
        # sequence so we don't need to export it now.
        if a.get('pynController', '') == 'NiControllerSequence': return

        # If the animation has multiple slots, don't export this one individually
        if len(a.slots) > 1: return

        objcol = BD.ReprObjectCollection()
        objcol.add(activeobj)
        s = activeelem.animation_data.action_slot
        dat = analyze_animation(a, s, bpy.context.scene, objcol)

        exporter = ControllerHandler(parent_handler, objcol)
        exporter.nif = parent_handler.nif
        exporter._export_activated_obj(dat)


    @classmethod
    def export_named_animations(cls, parent_handler, object_dict:BD.ReprObjectCollection):
        """
        Export a ControllerManager to manage all named animations (if any). 
        Only animations controlling objects in the given list count.

        * object_dict = dictionary of objects to consider
        """
        exporter = ControllerHandler(parent_handler, object_dict)
        exporter._export_animations()


### Handlers for importing different types of blocks

def _import_float_data(td, importer:ControllerHandler):
    if not importer.path_name: return

    curve = importer.action.fcurve_ensure_for_datablock(importer.action_target, importer.path_name)

    if td.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY \
            or td.properties.keys.interpolation == NiKeyType.LINEAR_KEY:
        keys = [None]
        keys.extend(td.keys)
        keys.append(None)
        while keys[1]:
            frame = keys[1].time * (importer.fps * ANIMATION_TIME_ADJUST) + 1
            kfp = curve.keyframe_points.insert(frame, keys[1].value)
            if td.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY:
                kfp.interpolation = 'BEZIER'
                kfp.handle_left_type = "FREE"
                kfp.handle_right_type = "FREE"
                kfp.handle_left, kfp.handle_right = importer._key_nif_to_blender(keys[0], keys[1], keys[2])
            else:
                kfp.interpolation = 'LINEAR'
            importer.start_time = min(importer.start_time, keys[1].time)
            importer.end_time = max(importer.end_time, keys[1].time)
            keys.pop(0)
    else:
        importer.warn(f"NYI: NiFloatData type {td.properties.keys.interpolation}")

NiFloatData.import_node = _import_float_data


def _import_pos_data(td:NiPosData, importer:ControllerHandler):
    if not importer.path_name: return

    if td.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY:
        for i in range(0, 3):
            curve = importer.action.fcurve_ensure_for_datablock(importer.action_target, importer.path_name, index=i)
            keys = [None]
            keys.extend(td.keys)
            keys.append(None)
            while keys[1]:
                frame = keys[1].time * (importer.fps * ANIMATION_TIME_ADJUST) + 1
                kfp = curve.keyframe_points.insert(frame, keys[1].value[i])
                kfp.handle_left_type = "FREE"
                kfp.handle_right_type = "FREE"
                kfp.handle_left, kfp.handle_right \
                    = importer._point3key_nif_to_blender(keys[0], keys[1], keys[2], i)
                importer.start_time = min(importer.start_time, keys[1].time)
                importer.end_time = max(importer.end_time, keys[1].time)
                keys.pop(0)
    else:
        importer.warn(f"NYI: NiPosData type {td.properties.keys.interpolation}")

NiPosData.import_node = _import_pos_data


def _import_transform_data(td:NiTransformData, 
                           importer:ControllerHandler, 
                           have_parent_rotation,
                           tiv,
                           tiq):
    """
    Import transform data.

    - Returns the rotation mode that must be set on the target. If this interpolator
        is using XYZ rotations, the rotation mode must be set to Euler. 
    """
    if importer.path_name:
        path_prefix = importer.path_name + "."
    else:
        path_prefix = ""
    qinv = tiq.inverted()

    targ = importer.bone_target if importer.bone_target else importer.action_target
    # Action group is the bone name if animating an armature, otherwise just "Object Transforms"
    if  not importer.action_group: importer.action_group = "Object Transforms" 
    
    targ.rotation_mode = "QUATERNION"
    if td.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
        targ.rotation_mode = "XYZ"
        if td.xrotations or td.yrotations or td.zrotations:
            curveX = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_euler", index=0)
            curveY = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_euler", index=1)
            curveZ = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_euler", index=2)

            if all_equal([len(td.xrotations), len(td.yrotations), len(td.zrotations)]):
                x_rot = ('LINEAR' if td.properties.xRotations.interpolation == NiKeyType.LINEAR_KEY
                            else 'BEZIER')
                y_rot = ('LINEAR' if td.properties.yRotations.interpolation == NiKeyType.LINEAR_KEY
                            else 'BEZIER')
                z_rot = ('LINEAR' if td.properties.zRotations.interpolation == NiKeyType.LINEAR_KEY
                            else 'BEZIER')
                for x, y, z in zip(td.xrotations, td.yrotations, td.zrotations):
                    # In theory the X/Y/Z dimensions do not have to have key frames at
                    # the same time signatures. But an Euler rotation needs all 3.
                    # Probably they will all line up because generating them any other
                    # way is surely hard. So hope for that and post a warning if not.
                    if not all_NearEqual([x.time, y.time, z.time]):
                        importer.warn(f"Keyframes do not align for '{importer.path_name}. Animations may be incorrect.")

                    # Need to apply the parent rotation. If we stay in Eulers, we may
                    # have gimbal lock. If we convert to quaternions, we may lose the
                    # distinction between +180 and -180, which are different things
                    # for animations. So only apply the parent rotation if there is
                    # one; in those cases we're just hoping it comes out right.
                    ve = Euler(Vector((x.value, y.value, z.value)), 'XYZ')
                    if have_parent_rotation:
                        ke = ve.copy()
                        kq = ke.to_quaternion()
                        vq = qinv @ kq
                        ve = vq.to_euler()
                    kx = curveX.keyframe_points.insert(x.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, ve[0])
                    kx.interpolation = x_rot
                    ky = curveY.keyframe_points.insert(y.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, ve[1])
                    ky.interpolation = y_rot
                    kz = curveZ.keyframe_points.insert(z.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, ve[2])
                    kz.interpolation = z_rot
                    importer.start_time = min(importer.start_time, x.time, y.time, z.time)
                    importer.end_time = max(importer.end_time, x.time, y.time, z.time)
                    
            else:
                # This method of getting the inverse of the Euler doesn't always
                # work, maybe because of gimbal lock.
                ve = tiq.to_euler()

                for i, k in enumerate(td.xrotations):
                    val = k.value - ve[0]
                    curveX.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, val)
                    importer.start_time = min(importer.start_time, k.time)
                    importer.end_time = max(importer.end_time, k.time)
                for i, k in enumerate(td.yrotations):
                    val = k.value - ve[1]
                    curveY.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, val)
                    importer.start_time = min(importer.start_time, k.time)
                    importer.end_time = max(importer.end_time, k.time)
                for i, k in enumerate(td.zrotations):
                    val = k.value - ve[2]
                    curveZ.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, val)
                    importer.start_time = min(importer.start_time, k.time)
                    importer.end_time = max(importer.end_time, k.time)
    
    elif td.properties.rotationType in [NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY]:
        if td.properties.rotationType == NiKeyType.LINEAR_KEY:
            key_type = 'LINEAR'
        else:
            key_type = 'BEZIER'
        try:
            # The curve may already have been started.
            curveW = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_quaternion", index=0)
            curveX = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_quaternion", index=1)
            curveY = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_quaternion", index=2)
            curveZ = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_quaternion", index=3)
        except:
            curveW = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "rotation_quaternion", index=0)

        for i, k in enumerate(td.qrotations):
            kq = Quaternion(k.value)
            # Auxbones animations are not correct yet, but they seem to need something
            # different from animations on the full skeleton.
            if importer.auxbones:
                vq = kq 
            else:
                vq = qinv @ kq 

            kw = curveW.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, vq[0])
            kw.interpolation = key_type
            kx = curveX.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, vq[1])
            kx.interpolation = key_type
            ky = curveY.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, vq[2])
            ky.interpolation = key_type
            kz = curveZ.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, vq[3])
            kz.interpolation = key_type
            importer.start_time = min(importer.start_time, k.time)
            importer.end_time = max(importer.end_time, k.time)

    elif td.properties.rotationType == NiKeyType.NO_INTERP:
        pass
    else:
        importer.warn(f"Not Yet Implemented: Rotation type {td.properties.rotationType} at {importer.path_name}")

    # Seems like a value of + or - infinity in the Transform
    if len(td.translations) > 0:
        xlate_interp = (
            'LINEAR' if td.properties.translations.interpolation == NiKeyType.LINEAR_KEY
                else 'BEZIER')
        curveLocX = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "location", index=0)
        curveLocY = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "location", index=1)
        curveLocZ = importer.action.fcurve_ensure_for_datablock(importer.action_target, path_prefix + "location", index=2)
        for k in td.translations:
            v = Vector(k.value)

            if importer.auxbones:
                pass 
            else:
                v = v - tiv
            k1 = curveLocX.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, v[0])
            k1.interpolation = xlate_interp
            k2 = curveLocY.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, v[1])
            k2.interpolation = xlate_interp
            k3 = curveLocZ.keyframe_points.insert(k.time * (importer.fps * ANIMATION_TIME_ADJUST) + 1, v[2])
            k3.interpolation = xlate_interp
            importer.start_time = min(importer.start_time, k.time)
            importer.end_time = max(importer.end_time, k.time)

NiTransformData.import_node = _import_transform_data


# #####################################
# Importers for NiInterpolator blocks. 

def _import_float_interpolator(fi:NiFloatInterpolator, 
                               importer:ControllerHandler, 
                               interp:NiInterpController):
    """
    "interp" is the controller to use when this interpolator doesn't have one.
    """
    td = fi.data
    if td: td.import_node(importer)
    
NiFloatInterpolator.import_node = _import_float_interpolator


def _import_point3_interpolator(fi:NiPoint3Interpolator, 
                                importer:ControllerHandler, 
                                interp:NiInterpController):
    """
    "interp" is the controller to use when this interpolator doesn't have one.
    """
    td = fi.data
    if td: td.import_node(importer)
    
NiPoint3Interpolator.import_node = _import_point3_interpolator


def _import_blendfloat_interpolator(fi:NiBlendFloatInterpolator, 
                               importer:ControllerHandler, 
                               interp:NiInterpController):
    if fi.properties.flags != InterpBlendFlags.MANAGER_CONTROLLED:
        importer.warn(f"NYI: BlendFloatInterpolator that is not MANAGER_CONTROLLED")
    
NiBlendFloatInterpolator.import_node = _import_blendfloat_interpolator


def _import_transform_interpolator(ti:NiTransformInterpolator, 
                                   importer:ControllerHandler, 
                                   interp:NiInterpController):
    """
    Import a transform interpolator, including its data block.

    - Returns the rotation mode that must be set on the target. If this interpolator
        is using XYZ rotations, the rotation mode must be set to Euler. 
    """
    if not ti.data:
        # Some NiTransformController blocks have null duration and no data. Not sure
        # how to interpret those, so ignore them.
        return None
    
    # ti, the parent NiTransformInterpolator, has the transform-to-global necessary
    # for this animation. It matches the transform of the target being animated.
    have_parent_rotation = False
    if max(ti.properties.rotation[:]) > 3e+38 or min(ti.properties.rotation[:]) < -3e+38:
        tiq = Quaternion()
    else:
        have_parent_rotation = True
        tiq = Quaternion(ti.properties.rotation)
    qinv = tiq.inverted()
    tiv = Vector(ti.properties.translation)

    # Some interpolators have bogus translations. Dunno why.
    if tiv[0] <= -1e+30 or tiv[0] >= 1e+30: tiv[0] = 0
    if tiv[1] <= -1e+30 or tiv[1] >= 1e+30: tiv[1] = 0
    if tiv[2] <= -1e+30 or tiv[2] >= 1e+30: tiv[2] = 0

    ti.data.import_node(importer, have_parent_rotation, tiv, tiq)

NiTransformInterpolator.import_node = _import_transform_interpolator


# #####################################
# Importers for NiTimeController blocks. Controllers usually have their own interpolators,
# but may not. If not, they get the interpolator from a parent ControllerLink, so it has
# to be passed in.

def _ignore_interp(interp):
    """Determine whether to ignore an interpolator."""
    return ((not interp) 
            or (isinstance(interp, NiBlendInterpolator) 
                and interp.properties.flags == InterpBlendFlags.MANAGER_CONTROLLED))


def _import_transform_controller(tc:NiTransformController, 
                                 importer:ControllerHandler, 
                                 interp:NiInterpController=None):
    """Import transform controller block."""
    if not interp:
        interp = tc.interpolator

    if importer.animation_target and interp:
        if importer.animation_target.type == 'ARMATURE':
            importer._animate_bone(tc.target.name)
            if not importer.action: importer._new_action()
            importer._new_slot()
            interp.import_node(importer, None)
        else:
            importer.action_group = "Object Transforms"
            if not importer.action: importer._new_action()
            importer._new_slot()
            interp.import_node(importer, None)
            importer._record_slot()
    else:
        importer.warn(f"Found no target for {type(tc)}")

NiTransformController.import_node = _import_transform_controller


def _import_alphatest_controller(ctlr:BSNiAlphaPropertyTestRefController, 
                                 importer:ControllerHandler,
                                 interp:NiInterpController=None):
    importer.action_group = "Shader"
    importer.path_name = f'nodes["AlphaProperty"].inputs["Alpha Threshold"].default_value'
    if not interp:
        interp = ctlr.interpolator
    if _ignore_interp(interp):
        log.debug(f"No interpolator available for controller {ctlr.id}")
        return
    
    td = interp.data
    if td: 
        if not importer.action: importer._new_action()
        importer._new_slot()
        td.import_node(importer)
        importer._record_slot()
    
BSNiAlphaPropertyTestRefController.import_node = _import_alphatest_controller


def _import_ESPFloat_controller(ctlr:BSEffectShaderPropertyFloatController, 
                                 importer:ControllerHandler,
                                 interp:NiInterpController=None):
    """
    Import float controller block.
    importer.action_target should be the material node_tree the action affects.
    """
    if not interp:
        interp = ctlr.interpolator
    if _ignore_interp(interp):
        log.debug(f"Not importing interpolator {'None' if interp is None else interp.blockname} for controller {ctlr.id}")
        return

    if not importer.action_target:
        importer.warn("No target object")

    importer.action_group = "Shader"
    importer.path_name = ""
    try:
        nodename, inputname, in_out = controlled_vars.nif_find(
            importer.nif.game,
            BSEffectShaderPropertyFloatController, 
            ctlr.properties.controlledVariable)
        if nodename is None:
            raise Exception(f"Invalid controlled target on controller {ctlr.id}")
        importer.path_name = \
            f'nodes["{nodename}"].{in_out}["{inputname}"].default_value'
    except:
        pass

    if not importer.path_name: 
        if ctlr.properties.controlledVariable == EffectShaderControlledVariable.Alpha_Transparency:
            log.info(f"Common error: Nif controller {ctlr.id} attempting to control effect shader alpha transparency, which does not exist.")
            return
        else:
            raise Exception(f"NYI: Cannot handle controlled variable on controller {ctlr.id}: {repr(EffectShaderControlledVariable(ctlr.properties.controlledVariable))}") 

    td = interp.data
    if td: 
        if not importer.action: importer._new_action()
        importer._new_slot()
        td.import_node(importer)
        importer._record_slot()
    
BSEffectShaderPropertyFloatController.import_node = _import_ESPFloat_controller


def _import_ESPColor_controller(ctlr:BSEffectShaderPropertyColorController, 
                                 importer:ControllerHandler,
                                 interp:NiInterpController=None):
    """
    Import float controller block.
    importer.action_target should be the material node_tree the action affects.
    """
    if not importer.action_target:
        importer.warn("No target object")

    importer.action_group = "Shader"
    if "Fallout 4 MTS - Greyscale To Palette Vector" in importer.action_target.nodes:
        importer.path_name = f'nodes["Fallout 4 MTS - Greyscale To Palette Vector"].inputs["Palette"].default_value'
    else:
        importer.path_name = f'nodes["FO4 Effect Shader"].inputs["Emission Color"].default_value'

    if not interp:
        interp = ctlr.interpolator
    if _ignore_interp(interp):
        log.debug(f"No interpolator available for controller {ctlr.id}")
        return
    td = interp.data
    if td: 
        if not importer.action: importer._new_action()
        importer._new_slot()
        td.import_node(importer)
        importer._record_slot()
    
BSEffectShaderPropertyColorController.import_node = _import_ESPColor_controller


def _import_LSPColorController(ctlr:BSLightingShaderPropertyColorController, 
                               importer:ControllerHandler,
                               interp:NiInterpController=None):
    """
    Import controller block.
    importer.action_target should be the material node_tree the action affects.
    """
    if not interp:
        interp = ctlr.interpolator
    if _ignore_interp(interp):
        # If no usable interpolator, just skip. This is part of a ControllerSequence and
        # we'll find it again when we load that.
        log.debug(f"No interpolator available for controller {ctlr.id}")
        return

    if not importer.action_target:
        importer.warn("No target object")

    importer.action_group = "Shader"
    importer.path_name = ""
    try:
        nodename, inputname, in_out = controlled_vars.nif_find(
            importer.nif.game,
            BSLightingShaderPropertyColorController, 
            ctlr.properties.controlledVariable)
        importer.path_name = \
                f'nodes["{nodename}"].{in_out}["{inputname}"].default_value'
    except:
        pass

    if not importer.path_name: 
        importer.warn(f"NYI: Cannot handle controlled variable on controller {ctlr.id}: {repr(LightingShaderControlledColor(ctlr.properties.controlledVariable))}") 
    else:    
        
        td = interp.data
        if td: 
            if not importer.action: importer._new_action()
            importer._new_slot()
            td.import_node(importer)
            importer._record_slot()
    
BSLightingShaderPropertyColorController.import_node = _import_LSPColorController


def _import_LSPFloatController(ctlr:BSLightingShaderPropertyFloatController, 
                               importer:ControllerHandler,
                               interp:NiInterpController=None):
    """
    Import controller block.
    importer.action_target should be the material node_tree the action affects.
    """
    if not interp:
        interp = ctlr.interpolator
    if _ignore_interp(interp):
        # If no usable interpolator, just skip. This is part of a ControllerSequence and
        # we'll find it again when we load that.
        log.debug(f"No interpolator available for controller {ctlr.id}")
        return

    if not importer.action_target:
        raise Exception("No target object")

    importer.action_group = "Shader"
    importer.path_name = ""
    try:
        nodename, inputname, in_out = controlled_vars.nif_find(
            importer.nif.game,
            BSLightingShaderPropertyFloatController, 
            ctlr.properties.controlledVariable)
        importer.path_name = \
            f'nodes["{nodename}"].{in_out}["{inputname}"].default_value'
    except:
        pass

    if not importer.path_name: 
        importer.warn(f"NYI: Cannot handle controlled variable on controller {ctlr.id}: {ctlr.properties.controlledVariable} on {ctlr.id}") 
    else:    
        
        td = interp.data
        if td: 
            if not importer.action: importer._new_action()
            importer._new_slot()
            td.import_node(importer)
            importer._record_slot()
    
BSLightingShaderPropertyFloatController.import_node = _import_LSPFloatController


def _import_multitarget_transform_controller( 
        block:ControllerLink, 
        importer:ControllerHandler, 
        interp:NiInterpController, ):
    """Import multitarget transform controller block from a controller link block."""
    # NiMultiTargetTransformController doesn't actually link to a controller or an
    # interpolator. It just references the target objects. The parent Control Link
    # block references the interpolator.
    importer.action_group = None
    importer.path_name = ""


NiMultiTargetTransformController.import_node = _import_multitarget_transform_controller


def _import_controller_sequence(seq:NiControllerSequence, 
                                importer:ControllerHandler,
                                interp=None):
    """
    Import a single controller sequence block.
    
    A controller sequence represents a single animation. It contains a list of
    ControllerLink structures, called "Controlled Block" in NifSkope. (They are not
    full, separate blocks in the nif file.) Each Controller Link block controls one
    element being animated.

    A ControllerSequence maps to multiple Blender actions, because several objects may
    be animated. The actions are marked as assets so they persist. 

    There may be text keys associated with this animation. They are represented as
    Blender TimelineMarker objects and apply across all the different actions that
    make up the animation. They are aso stored as a dictionary on the actions so they
    can be recovered when the user switches between animations.
    """
    importer._new_animation(seq)
    importer.anim_name = seq.name
    importer.controller_sequence = seq
    importer.start_time = min(importer.start_time, seq.properties.startTime)
    importer.end_time = max(importer.end_time, seq.properties.stopTime)

    if importer.animation_target.type == 'ARMATURE':
        importer._new_armature_action(seq)
    else:
        importer._new_action()

    for cb in seq.controlled_blocks:
        importer._import_controller_link(seq, cb)

    if seq.text_key_data: importer._import_text_keys(seq.text_key_data)

NiControllerSequence.import_node = _import_controller_sequence


def _import_controller_manager(cm:NiControllerManager, 
                                importer:ControllerHandler, 
                                interp=None):
    a = None
    for seq in cm.sequences.values():
        seq.import_node(importer)
        if not a: a = importer.action
    if a: 
        apply_action(a)

NiControllerManager.import_node = _import_controller_manager


def _get_interpolation_type(curvelist):
    """
    Return the interpolation type needed to represet a set of fcurves. If any curve has
    bezier handles, the interpolation will be QUADRATIC. 
    """
    for c in curvelist:
        for k in c.keyframe_points:
            if k.interpolation == 'BEZIER':
                return NiKeyType.QUADRATIC_KEY
    return NiKeyType.LINEAR_KEY


def _parse_transform_curves(exporter:ControllerHandler, curve_list):
    """
    Pull fcurves affecting the same target object off the list and parse them. Return
    a NiTransformData object representing the fcurves, and the curves themselves.

    Rules:

    * If rotationType == LINEAR or QUADRATIC, rotation keys are quaternions, no quadratic
    interpolation, only one channel. Generally many more keyframes emitted.

    * If rotationType == XYZ, rotation keys are Eulers, X, Y, and Z in separate channels,
    each channel has its own interpolation (which can be different), and key times and
    number of signatures can be different.

    * Translation keys are XYZ but only one channel, and one interpolation type.
    """
    loc = []
    eu = []
    quat = []
    scale = []
    props = NiTransformDataBuf()
    c = None

    targetname, curve_type = curve_bone_target(curve_list[0])
    while curve_list:
        c = curve_list.pop(0)
        if curve_type == "location":
            loc.append(c)
        elif curve_type == "rotation_quaternion":
            quat.append(c)
        elif curve_type == "rotation_euler":
            eu.append(c)
        elif curve_type == "scale":
            scale.append(c)
        else:
            log.warning(f"Unknown curve type: {c.data_path}")
        
        if not curve_list: break
        t1, curve_type = curve_bone_target(curve_list[0]) 
        if t1 != targetname: break
        targetname = t1
    
    if len(loc) != 3 and len(eu) != 3 and len(quat) != 4:
        raise Exception(f"No useable transforms in fcurves for {c.data_path}")

    if loc: 
        props.translations.interpolation = _get_interpolation_type(loc)
    if quat: 
        props.rotationType = _get_interpolation_type(quat)
    if eu:
        props.rotationType = NiKeyType.XYZ_ROTATION_KEY
        props.xRotations.interpolation = _get_interpolation_type([eu[0]])
        props.yRotations.interpolation = _get_interpolation_type([eu[1]])
        props.zRotations.interpolation = _get_interpolation_type([eu[2]])
    if scale:
        props.scales.interpolation = _get_interpolation_type(scale)

    return props, loc, eu, quat, scale


def _export_quaterion_curves(exporter, td, quat, rot_type, targ_q):
    """
    Export quaternion fcurves. 

    td = NiTransformData object
    quat = list of 4 fcurves containing quaternion values
    rot_type = Indicates whether bezier or linear curves are used
    targ_q = rotation of the target bone, if any
    """
    # Can't do quadratic interpolation with quaternions, so if the rot_type is QUADRATIC
    # export keys using the current fps.
    if rot_type == NiKeyType.QUADRATIC_KEY:
        timesig = exporter.start_time
        timestep = 1/(exporter.fps * ANIMATION_TIME_ADJUST)

        while timesig < exporter.stop_time + 0.0001:
            fr = timesig * (exporter.fps * ANIMATION_TIME_ADJUST) + 1
            tdq = Quaternion([quat[0].evaluate(fr), 
                                quat[1].evaluate(fr), 
                                quat[2].evaluate(fr), 
                                quat[3].evaluate(fr)])
            kq = targ_q  @ tdq
            td.add_qrotation_key(timesig, kq)
            timesig += timestep

    else:
        # The curve uses linear interpolation, so it's fine to export just keyframes. Each
        # fcurve of the quaternion could have different keyframes but it's not likely and
        # nifs don't support it, so don't allow it.
        if not all_equal([len(quat[0].keyframe_points), len(quat[1].keyframe_points), 
                          len(quat[2].keyframe_points), len(quat[3].keyframe_points)]):
            raise Exception(f"Different number of quaternion keyframes")
        
        for k1, k2, k3, k4 in zip(quat[0].keyframe_points, quat[1].keyframe_points, 
                                quat[2].keyframe_points, quat[3].keyframe_points):
            if not all_NearEqual([k1.co[0], k2.co[0], k3.co[0], k4.co[0]]):
                raise Exception (f"Quaternion keyframes not at matching times")
            
            tdq = Quaternion([k1.co[1], k2.co[1], k3.co[1], k4.co[1]])
            timesig = (k1.co[0]-1)/(exporter.fps * ANIMATION_TIME_ADJUST)
            kq = targ_q  @ tdq
            td.add_qrotation_key(timesig, kq)


def _export_euler_curves(exporter, td, eu, targ_q):
    """
    Export Euler fcurves. 

    td = NiTransformData object
    eu = list of 3 fcurves containing Euler x/y/z values
    targ_q = rotation of the target bone, if any
    """
    if td.properties.xRotations.interpolation == NiKeyType.QUADRATIC_KEY:
        xkeys = exporter._get_curve_quad_values(eu[0])
    else:
        xkeys = exporter._get_curve_linear_values(eu[0])
    if td.properties.yRotations.interpolation == NiKeyType.QUADRATIC_KEY:
        ykeys = exporter._get_curve_quad_values(eu[1])
    else:
        ykeys = exporter._get_curve_linear_values(eu[1])
    if td.properties.zRotations.interpolation == NiKeyType.QUADRATIC_KEY:
        zkeys = exporter._get_curve_quad_values(eu[2])
    else:
        zkeys = exporter._get_curve_linear_values(eu[2])

    # Bone fcurve rotations are relative to the bone, but nif keyframes are absolute. So
    # make the conversion if necessary.
    if targ_q and not NearEqual(targ_q.angle, 0, epsilon=0.01):
        if not (len(xkeys) == len(ykeys) == len(zkeys)):
            raise Exception("NYI: Euler bone rotations when different number of fcurve keyframes")
        for xk, yk, zk in zip(xkeys, ykeys, zkeys):
            if not all_NearEqual([xk.time, yk.time, zk.time]):
                raise Exception("NYI: Euler bone rotations when fcurve keyframes at different times")
            euk = Euler([xk.value, yk.value, zk.value])
            quatk = euk.to_quaternion()
            quatk1 = targ_q @ quatk
            euk1 = quatk1.to_euler()
            xk.value = euk1[0]
            yk.value = euk1[1]
            zk.value = euk1[2]

    td.add_xyz_rotation_keys("X", xkeys)
    td.add_xyz_rotation_keys("Y", ykeys)
    td.add_xyz_rotation_keys("Z", zkeys)


def _get_keyframe_indices(curve_list):
    """
    Return an ordered list of keyframe indices for all keyframes in the given list of
    fcurves.
    """
    frameset = set()
    for c in curve_list:
        for k in c.keyframe_points:
            frameset.add(round(k.co[0], 2))
    frames = list(frameset)
    frames.sort()
    return frames


def _next_keyframe_index(curve_list):
    findices = _get_keyframe_indices(curve_list)

    keyframes = []
    for c in curve_list:
        keyframes.append(list(c.keyframe_points))
    
    for kfindex in findices:
        matches = []
        for i, klist in enumerate(keyframes):
            if klist[0].co.x == kfindex:
                matches.append(klist.pop(0))
            else:
                matches.append(None)
        yield kfindex, matches


def _export_loc_curves(exporter, td, loc, targ_xf):
    """
    Export location fcurves. 

    td = NiTransformData object
    loc = list of 3 fcurves containing location x/y/z values
    """
    if exporter.export_each_frame:
        timesig = exporter.start_time
        timestep = 1/(exporter.fps * ANIMATION_TIME_ADJUST)
        while timesig < exporter.stop_time + 0.0001:
            fr = timesig * (exporter.fps * ANIMATION_TIME_ADJUST) + 1
            kv =Vector([loc[0].evaluate(fr), 
                            loc[1].evaluate(fr), 
                            loc[2].evaluate(fr)])
            rv = kv + targ_xf.translation
            td.add_translation_key(timesig, rv)
            timesig += timestep

    else:
        if td.properties.translations.interpolation == NiKeyType.QUADRATIC_KEY:
            td.add_quad_translation_keys(exporter._get_curve_quad_vector(loc, targ_xf))
        else:
            if not (len(loc[0].keyframe_points) == len(loc[1].keyframe_points) == len(loc[2].keyframe_points)):
                raise Exception("NYI: Euler bone rotations when different number of fcurve keyframes")
            for k0, k1, k2 in zip(loc[0].keyframe_points, loc[1].keyframe_points, loc[2].keyframe_points):
                if not all_NearEqual([k0.co.x, k1.co.x, k2.co.x]):
                    raise Exception (f"Translation keys not at matching frames for {exporter.action_target.name}")

                timesig = (k0.co.x-1)/(exporter.fps * ANIMATION_TIME_ADJUST)
                kv = Vector([k0.co.y, k1.co.y, k2.co.y])
                rv = kv + targ_xf.translation
                td.add_translation_key(timesig, rv)


def _export_transform_curves(exporter:ControllerHandler, curve_list, targetobj=None):
    """
    Export a group of curves from the list to a TransformInterpolator/TransformData pair.
    A group maps to a controlled object, so each group should be one such pair. The curves
    that are used are picked off the list.

    * Returns (group name, TransformInterpolator for the set of curves).
    """
    if not curve_list: return None, None
    
    # Bone target implies targetobj is an armature containing that bone. Else targetobj is
    # a ReprObject for a node being manipulated.
    targetname, curve_type = curve_bone_target(curve_list[0])
    if targetname:
        if not targetname in targetobj.data.bones:
            raise Exception(f"Target bone not found in armature: {targetobj.name}/{targetname}")
        targ = targetobj.data.bones[targetname]
        if targ.parent:
            targ_xf = targ.parent.matrix_local.inverted() @ targ.matrix_local
        else:
            targ_xf = targ.matrix_local
    else:
        targ_xf = Matrix.Identity(4)
    targ_q = targ_xf.to_quaternion()

    loc = []
    eu = []
    quat = []
    scale = []

    props, loc, eu, quat, scale = _parse_transform_curves(exporter, curve_list)

    if scale:
        if not exporter.given_scale_warning:
            log.info(f"Ignoring scale transforms--not used in Skyrim")
            exporter.given_scale_warning = True

    ti = NiTransformInterpolator.New(
        file=exporter.nif,
        translation=targ_xf.translation[:],
        rotation=targ_q[:],
        scale=1.0,
    )
    
    td:NiTransformData = NiTransformData.New(
        file=exporter.nif,
        properties=props,
        parent=ti,
    )

    if len(quat) == 4:
        _export_quaterion_curves(exporter, td, quat, props.rotationType, targ_q)

    if len(eu) == 3:
        _export_euler_curves(exporter, td, eu, (targ_q if targetname else None))
            
    if len(loc) == 3:
        _export_loc_curves(exporter, td, loc, targ_xf)

    return (targetname if targetname else targetobj.name), ti

NiTransformController.fcurve_exporter = _export_transform_curves


def _create_blend_transform(exporter):
    return NiBlendTransformInterpolator.New(exporter.nif)

NiTransformController.blend_interpolator = _create_blend_transform


def _export_color_curves(exporter, curve_list, target_obj=None):
    """
    Export fcurves controlling a color value. The 3 color channels are popped off the
    curve list. Returns the interpolator.
    """
    dat = NiPosData.New(exporter.nif, interpolation=NiKeyType.QUADRATIC_KEY)
    fcv = (curve_list.pop(0), curve_list.pop(0), curve_list.pop(0), )

    # Have to assume all channels have the same keyframes.
    keyframes = [(None, None, None, )]
    for k1, k2, k3 in zip(fcv[0].keyframe_points, fcv[1].keyframe_points, fcv[2].keyframe_points):
        if k1.co[0] != k2.co[0] or k1.co[0] != k3.co[0]:
            raise Exception(f"Cannot handle color fcurves with mismatched keyframes")
        keyframes.append((k1, k2, k3,))
    keyframes.append((None, None, None, ))

    for i in range(1, len(keyframes)-1):
        kfr, kfg, kfb = keyframes[i]
        kfbuf = NiAnimKeyQuadTransBuf()
        kfbuf.time = (kfr.co.x-1)/(exporter.fps * ANIMATION_TIME_ADJUST)
        kfbuf.value[0] = kfr.co.y
        kfbuf.forward[0], kfbuf.backward[0] = exporter._key_blender_to_nif(
            kfp0=keyframes[i-1][0],
            kfp1=keyframes[i][0],
            kfp2=keyframes[i+1][0]
        )
        kfbuf.value[1] = kfg.co.y
        kfbuf.forward[1], kfbuf.backward[1] = exporter._key_blender_to_nif(
            kfp0=keyframes[i-1][1],
            kfp1=keyframes[i][1],
            kfp2=keyframes[i+1][1]
        )
        kfbuf.value[2] = kfb.co.y
        kfbuf.forward[2], kfbuf.backward[2] = exporter._key_blender_to_nif(
            kfp0=keyframes[i-1][2],
            kfp1=keyframes[i][2],
            kfp2=keyframes[i+1][2]
        )
        dat.add_key(kfbuf)

    interp = NiPoint3Interpolator.New(exporter.nif, data=dat)
    return "", interp

BSLightingShaderPropertyColorController.fcurve_exporter = _export_color_curves
BSEffectShaderPropertyColorController.fcurve_exporter = _export_color_curves


def _create_blend_color(exporter):
    return NiBlendPoint3Interpolator.New(exporter.nif)

BSLightingShaderPropertyColorController.blend_interpolator = _create_blend_color
BSEffectShaderPropertyColorController.blend_interpolator = _create_blend_color


def _export_float_curves(exporter, fcurves, target_obj=None):
    """
    Export a float curve from the list to a NiFloatInterpolator/NiFloatData pair. 
    The curve is picked off the list.

    * Returns (group name, NiFloatInterpolator for the set of curves).
    """
    fc = fcurves.pop(0)
    keys = exporter._get_curve_quad_values(fc)
    fdp = NiFloatDataBuf()
    fdp.keys.interpolation = NiKeyType.QUADRATIC_KEY
    if len(keys) > 0 and type(keys[0]) is LinearScalarKey:
        fdp.keys.interpolation = NiKeyType.LINEAR_KEY
    fd = NiFloatData(file=exporter.nif, properties=fdp, keys=keys)

    fip = NiFloatInterpolatorBuf()
    fip.dataID = fd.id
    fi = NiFloatInterpolator(file=exporter.nif, properties=fip)
    return "", fi

BSLightingShaderPropertyFloatController.fcurve_exporter = _export_float_curves
BSEffectShaderPropertyFloatController.fcurve_exporter = _export_float_curves
BSNiAlphaPropertyTestRefController.fcurve_exporter = _export_float_curves


def _create_blend_float(exporter):
    return NiBlendFloatInterpolator.New(exporter.nif)

BSLightingShaderPropertyFloatController.blend_interpolator = _create_blend_float
BSEffectShaderPropertyFloatController.blend_interpolator = _create_blend_float
BSNiAlphaPropertyTestRefController.blend_interpolator = _create_blend_float


class AssignAnimPanel(bpy.types.Panel):
    bl_idname = "PYNIFLY_apply_anim"
    bl_label = "Apply Animation"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        self.layout.label(text="Apply Animation")


class WM_OT_ApplyAnim(bpy.types.Operator):
    bl_idname = "wm.apply_anim"
    bl_label = "Apply Nif Animation"
    bl_options = {'REGISTER', 'UNDO'}

    # Keeping the list of animations in a module-level variable because EnumProperty doesn't
    # like it if the list contents goes away.
    _animations_found = []

    anim_chooser : bpy.props.EnumProperty(name="Animation Selection",
                                           items=_animations_for_pulldown,
                                           )  # type: ignore
    
    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event): # Used for user interaction
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context): # Draw options (typically displayed in the tool-bar)
        row = self.layout
        row.prop(self, "anim_chooser", text="Animation name")

    def execute(self, context): # Runs by default 
        apply_animation(self.anim_chooser, context.scene)
        return {'FINISHED'}


def _draw_apply_animation_menu_entry(self, context):
    self.layout.operator(WM_OT_ApplyAnim.bl_idname)

def register():
    try:
        bpy.types.VIEW3D_MT_view.remove(_draw_apply_animation_menu_entry)
        bpy.utils.unregister_class(WM_OT_ApplyAnim)
    except:
        pass
    bpy.types.VIEW3D_MT_view.append(_draw_apply_animation_menu_entry)
    bpy.utils.register_class(WM_OT_ApplyAnim)

def unregister():
    try:
        bpy.types.VIEW3D_MT_view.remove(_draw_apply_animation_menu_entry)
        bpy.utils.unregister_class(WM_OT_ApplyAnim)
    except:
        pass
