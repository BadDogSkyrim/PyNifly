"""Handles import/export of controller nodes."""
# Copyright © 2024, Bad Dog.

import os
from pathlib import Path
import logging
import traceback
import bpy
from pynifly import *
from mathutils import Matrix, Vector, Quaternion, Euler, geometry
import blender_defs as BD
from nifdefs import *

KFP_HANDLE_OFFSET = 10

def key_nif_to_blender(frame1, v1, b1, frame2, v2, fwd2):
    """
    Calculate Blender values for handles given an interval from the nif.

    frame1 = frame index of beginning of interval
    v1 = y value at beginning of interval
    b1 = "backwards" value of beginning of interval
    frame2 = frame index of end of interval
    v2 = y value at end of interval
    fwd1 = "forward" value of end of interval

    return = coordinate of right handle of beginning, left handle of end
    """
    # Not trying to do an exact Hermite-to-Bezier conversion because I'm not sure Blender
    # fcurve control points are exactly Beziers. 
    w = frame2 - frame1
    vdiff = v2 - v1
    h2 = Vector((frame2 - w/2, v2 + fwd2*vdiff/2))
    return h2, h2


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

        # Necessary context from the parent.
        self.blender_objects = parent_handler.objects_created
        self.nif = parent_handler.nif
        self.auxbones = parent_handler.auxbones
        self.context = parent_handler.context
        self.fps = parent_handler.context.scene.render.fps
        self.warn = parent_handler.warn
        self.nif_name = parent_handler.nif_name
        self.blender_name = parent_handler.blender_name


    def _find_target(self, nifname):
        try:
            nifnode = self.nif.nodes[nifname]
            return self.blender_objects[nifnode._handle]
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


    def _import_float_interpolator(self, fi:NiFloatInterpolator):
        """Import a float interpolator block."""
        td:NiFloatData = fi.data
        curve = self.action.fcurves.new(self.path_name)
        if td.properties.keys.interpolation == NiKeyType.QUADRATIC_KEY:
            for i, k in enumerate(td.keys):
                curve.keyframe_points.insert(k.time*self.fps+1, k.value)
                kfp = curve.keyframe_points[i]
                kfp.handle_left_type = "FREE"
                kfp.handle_right_type = "FREE"
                if i > 0:
                    prior_kf = curve.keyframe_points[i-1]
                    prior_k = td.keys[i-1]
                    rh1, lh2 = key_nif_to_blender(
                        prior_kf.co[0], prior_kf.co[1], prior_k.backward,
                            kfp.co[0], kfp.co[1], k.forward)
                    kfp.handle_left = lh2
                    prior_kf.handle_right = rh1
            # Patch up first and last keyframes
            curve.keyframe_points[0].handle_left = \
                curve.keyframe_points[0].co + \
                (curve.keyframe_points[-1].handle_left - curve.keyframe_points[-1].co)
            curve.keyframe_points[-1].handle_right = \
                curve.keyframe_points[0].co + \
                (curve.keyframe_points[0].handle_right - curve.keyframe_points[0].co)
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
            self.warn(f"Cannot handle controlled variable {ctlr.properties.controlledVariable}")
            return

        self.path_name = f'nodes["{controlled_node}"].inputs[{controlled_input}].default_value'
        self._import_float_interpolator(ctlr.interpolator)
    

    def _import_color_controller(self, seq:NiSequence, block:ControllerLink):
        """Import one color controller block."""
        if block.node_name in self.nif.nodes:
            target_node = self.nif.nodes[block.node_name]

            if target_node._handle in self.blender_objects:
                target_obj = self.blender_objects[target_node._handle]
            else:
                self.warn(f"Target object was not imported: {block.node_name}")
                return
        else:
            self.warn(f"Target block not found in nif. Is it corrupt? ({block.node_name})")

        action_group = "Color Property Transforms"
        path_name = None
        action_name = f"{block.node_name}_{seq.name}"


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
            self._new_action("Transform")
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

    def _export_curves(self, arma, curve_list):
        """
        Export a group of curves from the list to a TransformInterpolator/TransformData pair. 
        A group maps to a controlled object, so each group should be one such pair.
        The curves that are used are picked off the list.
        * Returns (group name, TransformInterpolator for the set of curves).
        """
        if not curve_list: return None, None
        
        group = curve_list[0].group.name
        scene_fps = self.context.scene.render.fps
        
        loc = []
        eu = []
        quat = []
        scale = []
        while curve_list and curve_list[0].group.name == group:
            dp = curve_list[0].data_path
            if ".location" in dp:
                loc.append(curve_list[0])
                curve_list.pop(0)
            elif ".rotation_quaternion" in dp:
                quat.append(curve_list[0])
                curve_list.pop(0)
            elif ".scale" in dp:
                scale.append(curve_list[0])
                curve_list.pop(0)
            else:
                self.error(f"Unknown curve type: {dp}")
                return None, None
        
        if scale:
            if not self.given_scale_warning:
                self.report({"INFO"}, f"Ignoring scale transforms--not used in Skyrim")
                self.given_scale_warning = True

        if len(loc) != 3 and len(eu) != 3 and len(quat) != 4:
            self.error(f"No useable transforms in group {group}")
            return None, None

        if not group in arma.data.bones:
            self.error(f"Target bone not found in armature: {group}")
            return None, None
        
        targ = arma.data.bones[group]
        if targ.parent:
            targ_xf = targ.parent.matrix_local.inverted() @ targ.matrix_local
        else:
            targ_xf = targ.matrix_local
        targ_trans = targ_xf.translation
        targ_q = targ_xf.to_quaternion()

        tibuf = NiTransformInterpolatorBuf()
        tibuf.translation = targ_trans[:]
        tibuf.rotation = targ_q[:]
        tibuf.scale = 1.0
        ti = NiTransformInterpolator(file=self.nif, props=tibuf)
        
        tdbuf = NiTransformDataBuf()
        if quat:
            tdbuf.rotationType = NiKeyType.QUADRATIC_KEY
        elif eu:
            tdbuf.rotationType = NiKeyType.XYZ_ROTATION_KEY
        if loc:
            tdbuf.translations.interpolation = NiKeyType.LINEAR_KEY
        td = NiTransformData(file=self.nif, props=tdbuf, parent=ti)

        # Lots of error-checking because the user could have done any damn thing.
        if len(quat) == 4:
            timemax = max(q.range()[1]-1 for q in quat)/scene_fps
            timemin = min(q.range()[0]-1 for q in quat)/scene_fps
            timestep = 1/self.fps
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
            timemax = max(v.range()[1]-1 for v in loc)/scene_fps
            timemin = min(v.range()[0]-1 for v in loc)/scene_fps
            timestep = 1/self.fps
            timesig = timemin
            while timesig < timemax + 0.0001:
                fr = timesig * scene_fps + 1
                kv =Vector([loc[0].evaluate(fr), 
                            loc[1].evaluate(fr), 
                            loc[2].evaluate(fr)])
                rv = kv + targ_trans
                td.add_translation_key(timesig, rv)
                timesig += timestep

        return group, ti
                

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
        cp.cycleType = CycleType.CYCLE_LOOP if exporter.action.use_cyclic else CycleType.CYCLE_CLAMP
        cp.frequency = 1.0
        controller.properties = cp

        # Collect list of curves. They will be picked off in clumps until the list is empty.
        curve_list = list(exporter.action.fcurves)
        while curve_list:
            targname, ti = exporter._export_curves(arma, curve_list)
            if targname and ti:
                controller.add_controlled_block(
                    name=exporter.nif.nif_name(targname),
                    interpolator=ti,
                    node_name = exporter.nif.nif_name(targname),
                    controller_type = "NiTransformController")


    @classmethod
    def export_shader_controller(cclass, obj, trishape):
        """Export an obj that has an animated shader."""
