"""Handles import/export of controller nodes."""
# Copyright © 2024, Bad Dog.

import os
from pathlib import Path
import logging
import traceback
import bpy
import bpy.props 
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
from pynifly import *
import blender_defs as BD
from nifdefs import *

KFP_HANDLE_OFFSET = 10

controlled_variables_uv = {
    "Offset U": CONTROLLED_VARIABLE_TYPES.U_Offset,
    "Offset V": CONTROLLED_VARIABLE_TYPES.V_Offset,
    "Scale U": CONTROLLED_VARIABLE_TYPES.U_Scale,
    "Scale V": CONTROLLED_VARIABLE_TYPES.V_Scale,
    }


def current_animations(nif, refobjs:BD.ReprObjectCollection):
    """Find all assets that appear to be animation actions."""
    anim_pat = "ANIM|"
    matches = {}
    for act in bpy.data.actions:
        if act.name.startswith(anim_pat):
            name_parts = act.name.split("|", 2)
            anim_name = name_parts[1]
            target_name = name_parts[2]
            if target_name in refobjs.blenderdict:
                if anim_name not in matches:
                    matches[anim_name] = []
                matches[anim_name].append(
                    [act, refobjs.find_nifname(nif, target_name)])
            # animname = act.name.split("|", 2)[1]
            # matches.append(("pyn_" + animname, animname, "Animation", len(matches), ))
    return matches


def _current_animations():
    """Find all assets that appear to be animation actions."""
    anim_pat = "ANIM|"
    matches = []
    for act in bpy.data.actions:
        if act.name.startswith(anim_pat):
            animname = act.name.split("|", 2)[1]
            matches.append(("pyn_" + animname, animname, "Animation", len(matches), ))
    return matches


def apply_animation(anim_name, ctxt=bpy.context):
    """
    Apply the named animation to the currently visible objects.
    Returns a dictionary of animation values.
    """
    res = {
        "start_time": 0,
        "stop_time": 0,
        "cycle_type": CycleType.LOOP,
        "frequency": 1.0,
    }
    anim_pat = "ANIM|" + anim_name + "|"
    matches = []
    for act in bpy.data.actions:
        if act.name.startswith(anim_pat):
            matches.append(act)
    
    for act in matches:
        objname = act.name.split("|", 2)[2]
        if objname in ctxt.scene.objects:
            assign_action(ctxt.scene.objects[objname], act)
            res["start_time"] = min(
                res["start_time"],
                (act.curve_frame_range[0]-1)/ctxt.scene.render.fps)
            res["stop_time"] = max(
                res["stop_time"], 
                (act.curve_frame_range[1]-1)/ctxt.scene.render.fps)
            if (not act.use_cyclic): res["cycle_type"] = CycleType.CLAMP 

    return res


def curve_target(curve):
    """
    Return the curve target for the curve. The target is the bone name if any,
    otherwise ''.
    """
    if curve.data_path.startswith("pose.bones"):
        return eval(curve.data_path.split('[', 1)[1].split(']', 1)[0])
    else:
        return ''


class ControllerHandler():
    def __init__(self, parent_handler):
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
        self.multitarget_controller = None

        # Necessary context from the parent.
        self.nif = parent_handler.nif
        self.context = parent_handler.context
        self.fps = parent_handler.context.scene.render.fps
        self.logger = logging.getLogger("pynifly")
        if hasattr(parent_handler, "auxbones"): 
            self.auxbones = parent_handler.auxbones
        if hasattr(parent_handler, "nif_name"): 
            self.nif_name = parent_handler.nif_name
        if hasattr(parent_handler, "blender_name"): 
            self.blender_name = parent_handler.blender_name
        if hasattr(parent_handler, "objects_created"):
            self.objects_created = parent_handler.objects_created


    def warn(self, msg):
        self.logger.warning(msg)


    def _find_target(self, nifname):
        try:
            nifnode = self.nif.nodes[nifname]
            return self.objects_created.find_nifnode(nifnode).blender_obj
        except:
            return None


    def _find_nif_target(self, blendname):
        try:
            nifname = self.nif_name(blendname)
            nifnode = self.nif.nodes[nifname]
            return nifnode
        except:
            return None


    def _import_transform_interpolator(self, ti:NiTransformInterpolator):
        """
        Import a transform interpolator, including its data block.

        - Returns the rotation mode that must be set on the target. If this interpolator
          is using XYZ rotations, the rotation mode must be set to Euler. 
        """
        if not self.action:
            self.warn("NO ACTION CREATED")
            return None
        
        if not ti.data:
            # Some NiTransformController blocks have null duration and no data. Not sure
            # how to interpret those, so ignore them.
            return None
        
        rotation_mode = "QUATERNION"
        self.action_group = "Object Transforms"

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

        tixf = BD.MatrixLocRotScale(ti.properties.translation, 
                                    Quaternion(ti.properties.rotation),
                                    [1.0]*3)
        tixf.invert()

        locbase = tixf.translation
        rotbase = tixf.to_euler()
        quatbase = tixf.to_quaternion()
        scalebase = -ti.properties.scale
        td = ti.data

        if self.path_name:
            path_prefix = self.path_name + "."
        else:
            path_prefix = ""

        if td.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
            rotation_mode = "XYZ"
            if td.xrotations or td.yrotations or td.zrotations:
                curveX = self.action.fcurves.new(path_prefix + "rotation_euler", index=0, action_group=self.action_group)
                curveY = self.action.fcurves.new(path_prefix + "rotation_euler", index=1, action_group=self.action_group)
                curveZ = self.action.fcurves.new(path_prefix + "rotation_euler", index=2, action_group=self.action_group)

                if len(td.xrotations) == len(td.yrotations) and len(td.xrotations) == len(td.zrotations):
                    for x, y, z in zip(td.xrotations, td.yrotations, td.zrotations):
                        # In theory the X/Y/Z dimensions do not have to have key frames at
                        # the same time signatures. But an Euler rotation needs all 3.
                        # Probably they will all line up because generating them any other
                        # way is surely hard. So hope for that and post a warning if not.
                        if not (NearEqual(x.time, y.time) and NearEqual(x.time, z.time)):
                            self.warn(f"Keyframes do not align for '{self.path_name}. Animations may be incorrect.")

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
                        curveX.keyframe_points.insert(x.time * self.fps + 1, ve[0])
                        curveY.keyframe_points.insert(y.time * self.fps + 1, ve[1])
                        curveZ.keyframe_points.insert(z.time * self.fps + 1, ve[2])
                        
                else:
                    # This method of getting the inverse of the Euler doesn't always
                    # work, maybe because of gimbal lock.
                    ve = tiq.to_euler()

                    for i, k in enumerate(td.xrotations):
                        val = k.value - ve[0]
                        curveX.keyframe_points.insert(k.time * self.fps + 1, val)
                    for i, k in enumerate(td.yrotations):
                        val = k.value - ve[1]
                        curveY.keyframe_points.insert(k.time * self.fps + 1, val)
                    for i, k in enumerate(td.zrotations):
                        val = k.value - ve[2]
                        curveZ.keyframe_points.insert(k.time * self.fps + 1, val)
        
        elif td.properties.rotationType in [NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY]:
            rotation_mode = "QUATERNION"

            try:
                # The curve may already have been started.
                curveW = self.action.fcurves.new(path_prefix + "rotation_quaternion", index=0, action_group=self.action_group)
                curveX = self.action.fcurves.new(path_prefix + "rotation_quaternion", index=1, action_group=self.action_group)
                curveY = self.action.fcurves.new(path_prefix + "rotation_quaternion", index=2, action_group=self.action_group)
                curveZ = self.action.fcurves.new(path_prefix + "rotation_quaternion", index=3, action_group=self.action_group)
            except:
                curveW = self.action.fcurves[path_prefix + "rotation_quaternion"]

            for i, k in enumerate(td.qrotations):
                kq = Quaternion(k.value)
                # Auxbones animations are not correct yet, but they seem to need something
                # different from animations on the full skeleton.
                if self.auxbones:
                    vq = kq 
                else:
                    vq = qinv @ kq 

                curveW.keyframe_points.insert(k.time * self.fps + 1, vq[0])
                curveX.keyframe_points.insert(k.time * self.fps + 1, vq[1])
                curveY.keyframe_points.insert(k.time * self.fps + 1, vq[2])
                curveZ.keyframe_points.insert(k.time * self.fps + 1, vq[3])

        elif td.properties.rotationType == NiKeyType.NO_INTERP:
            pass
        else:
            self.warn(f"Not Yet Implemented: Rotation type {td.properties.rotationType} at {self.path_name}")

        # Seems like a value of + or - infinity in the Transform
        if len(td.translations) > 0:
            curveLocX = self.action.fcurves.new(path_prefix + "location", index=0, action_group=self.action_group)
            curveLocY = self.action.fcurves.new(path_prefix + "location", index=1, action_group=self.action_group)
            curveLocZ = self.action.fcurves.new(path_prefix + "location", index=2, action_group=self.action_group)
            for k in td.translations:
                v = Vector(k.value)

                if self.auxbones:
                    pass 
                else:
                    v = v - tiv
                curveLocX.keyframe_points.insert(k.time * self.fps + 1, v[0])
                curveLocY.keyframe_points.insert(k.time * self.fps + 1, v[1])
                curveLocZ.keyframe_points.insert(k.time * self.fps + 1, v[2])

        return rotation_mode


    def _key_nif_to_blender(self, key0, key1, key2):
        """
        Return blender fcurve handle values for key1.

        key0 and key2 may be omitted if key1 is first or last.
        """
        frame1 = key1.time*self.fps+1
        if key2:
            frame2 = key2.time*self.fps+1
            frame_delt_r = (frame2 - frame1)
            slope_right = key1.backward/frame_delt_r
        else:
            frame_delt_r = 1
            slope_right = key1.backward

        if key0:
            frame0 = key0.time * self.fps + 1
            frame_delt_l = (frame1 - frame0)
            slope_left = key1.forward/frame_delt_l
        else:
            frame_delt_l = 1
            slope_left = key1.forward

        partial = 1/3
        handle_l = Vector((frame1 - frame_delt_l*partial, key1.value - slope_left*frame_delt_l*partial))
        handle_r = Vector((frame1 + frame_delt_r*partial, key1.value + slope_right*frame_delt_r*partial))
        
        return handle_l, handle_r


    def _import_float_interpolator(self, fi:NiFloatInterpolator):
        """Import a float interpolator block."""
        td:NiFloatData = fi.data
        curve = self.action.fcurves.new(self.path_name)
        if td.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY:
            keys = [None]
            keys.extend(td.keys)
            keys.append(None)
            while keys[1]:
                frame = keys[1].time*self.fps+1
                kfp = curve.keyframe_points.insert(frame, keys[1].value)
                kfp.handle_left_type = "FREE"
                kfp.handle_right_type = "FREE"
                kfp.handle_left, kfp.handle_right = self._key_nif_to_blender(keys[0], keys[1], keys[2])
                keys.pop(0)
        else:
            self.warn(f"Unknown interpolation type for NiFloatInterpolator: {td.keys.interpolation}")


    def _import_transform_controller(self, block:ControllerLink):
        """Import transform controller block."""
        self.action_group = "Object Transforms"
        if self.animation_target:
            rotmode = self._import_transform_interpolator(block.interpolator)
            if rotmode: self.animation_target.rotation_mode = rotmode
        else:
            self.warn("Found no target for NiTransformController")


    def _import_multitarget_transform_controller(self, control_ctxt:NiSequence, block:ControllerLink):
        """Import multitarget transform controller block from a controller link block."""
        # NiMultiTargetTransformController doesn't actually link to a controller or an
        # interpolator. It just references the target objects. The parent Control Link
        # block references the interpolator.
        rotmode = self._import_transform_interpolator(block.interpolator)
        self.animation_target.rotation_mode = rotmode


    def _new_float_controller_action(
            self, ctlr:BSEffectShaderPropertyFloatController):
        """Import float controller block."""
        if not self.action_target:
            self.warn("No target object")

        self.action_group = "Shader Nodetree"
        self._new_action("Shader")
        
        self.action_group = "Shader Nodetree"
        if ctlr.properties.controlledVariable == CONTROLLED_VARIABLE_TYPES.U_Offset:
            controlled_node = "UV_Converter"
            controlled_input = 0
        elif ctlr.properties.controlledVariable == CONTROLLED_VARIABLE_TYPES.V_Offset:
            controlled_node = "UV_Converter"
            controlled_input = 1
        elif ctlr.properties.controlledVariable == CONTROLLED_VARIABLE_TYPES.U_Scale:
            controlled_node = "UV_Converter"
            controlled_input = 2
        elif ctlr.properties.controlledVariable == CONTROLLED_VARIABLE_TYPES.V_Scale:
            controlled_node = "UV_Converter"
            controlled_input = 3
        else:
            self.warn(f"NYI: Cannot handle controlled variable {repr(CONTROLLED_VARIABLE_TYPES(ctlr.properties.controlledVariable))}") 
            return

        self.path_name = f'nodes["{controlled_node}"].inputs[{controlled_input}].default_value'
        self._import_float_interpolator(ctlr.interpolator)
    

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
        self.context.scene.frame_end = 1 + int(
            (anim_context.properties.stopTime - anim_context.properties.startTime) * self.fps)

        try:
            self.anim_name = anim_context.name
        except:
            self.anim_name = None
        self.action_name = ""
        self.action_group = ""
        self.path_name = ""
        self.frame_start = anim_context.properties.startTime * self.fps + 1
        self.frame_end = anim_context.properties.stopTime * self.fps + 1
        self.is_cyclic = anim_context.is_cyclic

        # if the animation context has a target, set action_target
        try:
            if not self.action_target or self.action_target.type != 'ARMATURE':
                self.action_target = self._find_target(anim_context.target.name)
            elif self.action_target and self.action_target.type == 'ARMATURE' and not self.bone_target:
                self.bone_target = self._find_target(anim_context.target.name)
        except:
            pass


    def _new_action(self, name_suffix):
        """
        Create a new action to represent all or part of a nif animation.
        """
        if not self.animation_target:
            self.warn("No animation target") 

        n = ["ANIM"]
        if self.anim_name: n.append(self.anim_name)
        n.append(self.animation_target.name)
        if name_suffix: n.append(name_suffix)
        self.action_name = "|".join(n)
        self.action = bpy.data.actions.new(self.action_name)
        self.action.frame_start = self.frame_start
        self.action.frame_end = self.frame_end
        self.action.use_frame_range = True
        self.action.use_cyclic = self.is_cyclic 

        # Some nifs have multiple animations with different names. Others just animate
        # various nif blocks. If there's a name, make this an asset so we can track them.
        if self.anim_name:
            self.action.use_fake_user = True
            self.action.asset_mark()

        self.action_target.animation_data_create()
        self.action_target.animation_data.action = self.action


    def _animate_bone(self, bone_name):
        """
        Set up to import the animation of a bone as part of a larger animation. 
        
        Returns TRUE if the target bone was found, FALSE otherwise.
        """
        # Armature may have had bone names converted or not. Check both ways.
        name = bone_name
        if name not in self.action_target.data.bones:
            name = self.blender_name(name)
            if name not in self.action_target.data.bones:
                # Some nodes are uppercase in the skeleton but not in the animations.
                # Don't know if they are ignored in game or if the game is doing
                # case-insensitive matching.
                self.warn(f"Controller target not found: {bone_name}")
                return False

        self.path_name = f'pose.bones["{name}"]'
        # self.animation_target = self.action_target.pose.bones[name]
        self.action_group = name
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


    def _new_element_action(self, anim_context, target_name, suffix):
        """
        Create an action to animate a single element (bone, shader, node). This may be
        part of a larger nif animation. 

        target_name is the name of the target in the nif file.
         
        Returns TRUE if the target element was found, FALSE otherwise.
        """
        try:
            self.action_target = self._find_target(target_name)
            if self.action_target:
                self.animation_target = self.action_target
                self._new_action(suffix)
                return True
        except:
            pass

        self.warn(f"Target of controller not found: {target_name}")
        return False
            

    def _new_transform_anim(self, ctlr):
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
            # self._new_action("Transform")
            self._new_element_action(ctlr, ctlr.target.name, "Transform")
        self._import_transform_controller(ctlr)


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
        if self.animation_target.type == 'ARMATURE':
            if not self._animate_bone(block.node_name):
                return
        else:
            if not self._new_element_action(seq, block.node_name, None):
                return

        if block.controller:
            # Controller will reference the interpolator.
            if block.controller_type == "NiTransformController":
                if block.controller.blockname == "NiMultiTargetTransformController":
                    self._import_multitarget_transform_controller(seq, block)
                elif block.controller.blockname == "NiTransformData":
                    self._import_transform_controller(block.controller)
                else:
                    self.warn(f"Not yet implemented: {block.controller.blockname} controller type")
            elif block.controller_type == 'BSEffectShaderPropertyColorController':
                self._import_color_controller(seq, block)
            elif block.controller_type == 'BSEffectShaderPropertyFloatController':
                self._new_float_controller_action(block.controller)
            else:
                self.warn(f"Not Yet Implemented: controller type {block.controller_type}")
                return
            
        elif block.interpolator:
            # If there's no controller, everything is done by the interpolator.
            rotmode = self._import_transform_interpolator(block.interpolator)
            self.animation_target.rotation_mode = rotmode


    def _new_controller_seq_anim(self, seq:NiControllerSequence):
        """
        Import a single controller sequence block.
        
        A controller sequence represents a single animation. It contains a list of
        ControllerLink structures, called "Controlled Block" in NifSkope. (They are not
        full, separate blocks in the nif file.) Each Controller Link block controls one
        element being animated.

        * seq = NiControllerSequence block
        """
        self._new_animation(seq)
        if self.animation_target.type == 'ARMATURE':
            self._new_armature_action(seq)

        for cb in seq.controlled_blocks:
            self._import_controller_link(seq, cb)

    # --- PUBLIC FUNCTIONS ---

    def import_controller(self, ctlr, target_object=None, target_element=None, target_bone=None):
        """
        Import the animation defined by a controller block.
        
        target_object = The blender object controlled by the animation, e.g. armature, mesh object.
        target_element = The blender object an action must be bound to, e.g. bone, material.
        """
        self.animation_target = target_object
        self.action_target = target_element
        self.bone_target = target_bone
        if ctlr.blockname == "BSEffectShaderPropertyFloatController":
            self._new_animation(ctlr)
            self._new_float_controller_action(ctlr)
        elif ctlr.blockname == "NiTransformController":
            self._new_transform_anim(ctlr)
        elif ctlr.blockname == "NiControllerSequence": 
            self._new_controller_seq_anim(ctlr)
        elif ctlr.blockname == "NiControllerManager": 
            for seq in ctlr.sequences.values():
                self._new_controller_seq_anim(seq)
        else:
            self.warn(f"Not Yet Implemented: {ctlr.blockname} controller type")


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

    def _get_controlled_variable(self, activated_obj):
        c = self.action.fcurves[0]
        dp = c.data_path
        if not dp.endswith(".default_value"):
            self.warn(f"FCurve has unknown data path: {dp}")
            return 0
        if "UV_Converter" not in dp:
            self.warn(f"NYI: Cannot handle fcurve {dp}")
            return 0

        try:
            target_attr = eval(repr(activated_obj) + "." + dp[:-14])
            return controlled_variables_uv[target_attr.name]
        except:
            self.warn(f"NYI: Can't handle fcurve {dp}")
            return 0


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


    def _get_curve_quad_values(self, curve):
        """
        Transform a blender curve into nif keys. 
        Returns [[time, value, forward, backward]...] for each keyframe in the curve.
        """
        keys = []
        points = [None]
        points.extend(list(curve.keyframe_points))
        points.append(None)
        while points[1]:
            k = NiAnimKeyQuadXYZBuf()
            k.time = (points[1].co.x-1) / self.fps
            k.value = points[1].co.y
            k.forward, k.backward = self._key_blender_to_nif(points[0], points[1], points[2])
            keys.append(k)
            points.pop(0)
        return keys

    def _export_float_curves(self, activated_obj, parent_ctlr=None):
        """
        Export a float curve from the list to a NiFloatInterpolator/NiFloatData pair. 
        The curve is picked off the list.

        * Returns (group name, NiFloatInterpolator for the set of curves).
        """
        keys = self._get_curve_quad_values(self.action.fcurves[0])
        fdp = NiFloatDataBuf()
        fdp.keys.interpolation = NiKeyType.QUADRATIC_KEY
        fd = NiFloatData(file=self.nif, properties=fdp, keys=keys)

        fip = NiFloatInterpolatorBuf()
        fip.dataID = fd.id
        fi = NiFloatInterpolator(file=self.nif, properties=fip, parent=parent_ctlr)
        return fi

    
    def _export_transform_curves(self, targetobj, curve_list):
        """
        Export a group of curves from the list to a TransformInterpolator/TransformData
        pair. A group maps to a controlled object, so each group should be one such pair.
        The curves that are used are picked off the list.
        * Returns (group name, TransformInterpolator for the set of curves).
        """
        if not curve_list: return None, None
        
        targetname = curve_target(curve_list[0])
        scene_fps = self.context.scene.render.fps
        
        loc = []
        eu = []
        quat = []
        scale = []
        timemax = -10000
        timemin = 10000
        timestep = 1/self.fps
        while curve_list and curve_target(curve_list[0]) == targetname:
            c = curve_list.pop(0)
            timemax = max(timemax, (c.range()[1]-1)/scene_fps)
            timemin = min(timemin, (c.range()[0]-1)/scene_fps)
            dp = c.data_path
            if "location" in dp:
                loc.append(c)
            elif "rotation_quaternion" in dp:
                quat.append(c)
            elif "rotation_euler" in dp:
                eu.append(c)
            elif "scale" in dp:
                scale.append(c)
            else:
                self.warn(f"Unknown curve type: {dp}")
        
        if scale:
            if not self.given_scale_warning:
                self.report({"INFO"}, f"Ignoring scale transforms--not used in Skyrim")
                self.given_scale_warning = True

        if len(loc) != 3 and len(eu) != 3 and len(quat) != 4:
            self.warn(f"No useable transforms in group {targetobj.name}/{targetname}")
            return None, None

        tibuf = NiTransformInterpolatorBuf()
        if targetobj.type == 'ARMATURE':
            if not targetname in targetobj.data.bones:
                self.warn(f"Target bone not found in armature: {targetobj.name}/{targetname}")
                return None, None
            
            targ = targetobj.data.bones[targetname]
            if targ.parent:
                targ_xf = targ.parent.matrix_local.inverted() @ targ.matrix_local
            else:
                targ_xf = targ.matrix_local
        else:
            targ_xf = Matrix.Identity(4)
        targ_trans = targ_xf.translation
        targ_q = targ_xf.to_quaternion()            
        tibuf.translation = targ_trans[:]
        tibuf.rotation = targ_q[:]
        tibuf.scale = 1.0
        ti = NiTransformInterpolator(file=self.nif, properties=tibuf)
        
        tdbuf:NiTransformDataBuf = NiTransformDataBuf()
        if quat:
            tdbuf.rotationType = NiKeyType.QUADRATIC_KEY
        elif eu:
            tdbuf.rotationType = NiKeyType.XYZ_ROTATION_KEY
            tdbuf.xRotations.interpolation = NiKeyType.QUADRATIC_KEY
            tdbuf.yRotations.interpolation = NiKeyType.QUADRATIC_KEY
            tdbuf.zRotations.interpolation = NiKeyType.QUADRATIC_KEY
        if loc:
            tdbuf.translations.interpolation = NiKeyType.LINEAR_KEY
        td:NiTransformData = NiTransformData(file=self.nif, properties=tdbuf, parent=ti)

        # Lots of error-checking because the user could have done any damn thing.
        if len(quat) == 4:
            timesig = timemin
            while timesig < timemax + 0.0001:
                fr = timesig * scene_fps + 1
                tdq = Quaternion([quat[0].evaluate(fr), 
                                  quat[1].evaluate(fr), 
                                  quat[2].evaluate(fr), 
                                  quat[3].evaluate(fr)])
                kq = targ_q @ tdq
                td.add_qrotation_key(timesig, kq)
                timesig += timestep

        if len(loc) == 3:
            timesig = timemin
            while timesig < timemax + 0.0001:
                fr = timesig * scene_fps + 1
                kv =Vector([loc[0].evaluate(fr), 
                            loc[1].evaluate(fr), 
                            loc[2].evaluate(fr)])
                rv = kv + targ_trans
                td.add_translation_key(timesig, rv)
                timesig += timestep

        if len(eu) == 3:
            td.add_xyz_rotation_keys("X", self._get_curve_quad_values(eu[0]))
            td.add_xyz_rotation_keys("Y", self._get_curve_quad_values(eu[1]))
            td.add_xyz_rotation_keys("Z", self._get_curve_quad_values(eu[2]))

        return targetname if targetname else targetobj.name, ti
    

    def _export_activated_obj(self, target:BD.ReprObject,  controller=None):
        """
        Export a single activated object--an object with animation_data on it.

        * target = Object with animation data on it to export
        """
        activated_obj = target.blender_obj
        self.action = activated_obj.animation_data.action
        if controller == None:
            if activated_obj.type == 'ARMATURE':
                # KF animation
                controller = self.nif.rootNode
            elif activated_obj.type == 'SHADER':
                # Shader animation
                controller = BSEffectShaderPropertyFloatController(
                    file=self.nif,
                    parent=target.nifnode.shader)
            else:
                self.warn(f"Unknowned activated object type: {activated_obj.type}")
                return
        
            cp = controller.properties.copy()
            cp.startTime = (self.action.curve_frame_range[0]-1)/self.fps
            cp.stopTime = (self.action.curve_frame_range[1]-1)/self.fps
            cp.cycleType = CycleType.CYCLE_LOOP if self.action.use_cyclic else CycleType.CYCLE_CLAMP
            cp.frequency = 1.0
            controller.properties = cp

        if activated_obj.type == 'ARMATURE':
            # Collect list of curves. They will be picked off in clumps until the list is empty.
            curve_list = list(self.action.fcurves)
            while curve_list:
                targname, ti = self._export_transform_curves(activated_obj, curve_list)
                if targname and ti:
                    controller.add_controlled_block(
                        name=self.nif.nif_name(targname),
                        interpolator=ti,
                        node_name = self.nif.nif_name(targname),
                        controller_type = "NiTransformController")
                    
        elif activated_obj.type == 'SHADER':
            self.warn(f"NYI: Shader controller export")

        elif activated_obj.type == 'EMPTY':
            curve_list = list(self.action.fcurves)
            while curve_list:
                targname, ti = self._export_transform_curves(activated_obj, curve_list)
                if self.multitarget_controller:
                    mttc = self.multitarget_controller
                    self.multitarget_controller = None
                else:
                    mttc = NiMultiTargetTransformController.New(
                        file=self.nif,
                        flags=TimeControllerFlags(
                            active=True, cycle_type=controller.properties.cycleType).flags,
                        target=self.accum_root,
                    )
                if targname and ti:
                    controller.add_controlled_block(
                        name=target.nifnode.name,
                        interpolator=ti,
                        controller=mttc,
                        node_name = target.nifnode.name,
                        controller_type = "NiTransformController")
            

    def _set_controller_props(self, props):
        props.startTime = (self.action.curve_frame_range[0]-1)/self.fps
        props.stopTime = (self.action.curve_frame_range[1]-1)/self.fps
        props.frequency = 1.0
        props.flags = (1 << 3) | (1 << 6) | ((0 if self.action.use_cyclic else 2) << 1)
        try:
            props.cycleType = CycleType.CYCLE_LOOP if self.action.use_cyclic else CycleType.CYCLE_CLAMP
        except:
            pass


    def _export_shader(self, activated_obj, nifshape):
        fi = self._export_float_curves(activated_obj)

        fcp = BSEffectShaderPropertyFloatControllerBuf()
        self._set_controller_props(fcp)
        fcp.controlledVariable = self._get_controlled_variable(activated_obj)
        fcp.interpolatorID = fi.id
        fc = BSEffectShaderPropertyFloatController(
            file=self.nif, properties=fcp, parent=nifshape.shader)
        

    def _export_animations(self, anims):
        """
        Export the given animations to the target nif.
        
        * Anims = {"anim name": [(action, obj), ..], ...}
            a dictionary of animation names to list of action/object pairs that implement
            that animation.
        """
        self.accum_root = self.nif.rootNode
        self.multitarget_controller = NiMultiTargetTransformController.New(
            file=self.nif, flags=108, target=self.nif.rootNode)
        
        cm = NiControllerManager.New(
            file=self.parent.nif, 
            flags=TimeControllerFlags(cycle_type=CycleType.CLAMP),
            next_controller=self.multitarget_controller,
            parent=self.accum_root)

        for anim_name, actionlist in anims.items(): 
            vals = apply_animation(anim_name)
            cs:NiControllerSequence = NiControllerSequence.New(
                file=self.parent.nif,
                name=anim_name,
                accum_root_name=self.parent.nif.rootName,
                start_time=vals["start_time"],
                stop_time=vals["stop_time"],
                cycle_type=vals["cycle_type"],
                frequency=vals["frequency"],
                parent=cm
            )

            for act, reprobj in actionlist:
                self._export_activated_obj(reprobj, cs)


    @classmethod
    def export_animation(cls, parent_handler, arma):
        """Export one action to one animation KF file."""
        exporter = ControllerHandler(parent_handler)
        exporter.nif = parent_handler.nif

        exporter.action = arma.animation_data.action
        controller = exporter.nif.rootNode
        cp = controller.properties.copy()
        cp.startTime = (exporter.action.curve_frame_range[0]-1)/exporter.fps
        cp.stopTime = (exporter.action.curve_frame_range[1]-1)/exporter.fps
        cp.cycleType = CycleType.LOOP if exporter.action.use_cyclic else CycleType.CLAMP
        cp.frequency = 1.0
        controller.properties = cp

        # Collect list of curves. They will be picked off in clumps until the list is empty.
        curve_list = list(exporter.action.fcurves)
        while curve_list:
            targname, ti = exporter._export_transform_curves(arma, curve_list)
            if targname and ti:
                controller.add_controlled_block(
                    name=exporter.nif.nif_name(targname),
                    interpolator=ti,
                    node_name = exporter.nif.nif_name(targname),
                    controller_type = "NiTransformController")


    @classmethod
    def export_shader_controller(cls, parent_handler, obj, trishape):
        # """Export an obj that has an animated shader."""
        exporter = ControllerHandler(parent_handler)
        exporter.nif = parent_handler.nif
        exporter.action = obj.active_material.node_tree.animation_data.action
        exporter._export_shader(obj.active_material.node_tree, trishape)


    @classmethod
    def export_named_animations(cls, parent_handler, object_dict:BD.ReprObjectCollection):
        """
        Export a ControllerManager to manage all named animations (if any). 
        Only animations controlling objects in the given list count.

        * object_dict = dictionary of objects to consider
        """
        exporter = ControllerHandler(parent_handler)
        anims = current_animations(parent_handler.nif, object_dict)
        if not anims: return
        exporter._export_animations(anims)


def assign_action(obj, act):
    """Assign the given action to the given object."""
    for g in act.groups:
        if g.name == 'Object Transforms':
            if not obj.animation_data:
                obj.animation_data_create()
            obj.animation_data.action = act


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
    bl_label = "Apply Animation"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "Apply Animation"
    # bl_property = "anim_name"
    bl_property = "anim_pulldown"

    # anim_name : bpy.props.StringProperty(name="Apply Animation") # type: ignore
    anim_pulldown : bpy.props.EnumProperty(items=_current_animations,
                                           name="Animation Selection",
                                           default=0) # type: ignore

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event): # Used for user interaction
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context): # Draw options (typically displayed in the tool-bar)
        row = self.layout
        row.prop(self, "anim_pulldown", text="Animation name")

    def execute(self, context): # Runs by default 
        anim_dict = apply_animation(self.anim_pulldown, context)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(WM_OT_ApplyAnim)

def unregister():
    bpy.utils.unregister_class(WM_OT_ApplyAnim)
