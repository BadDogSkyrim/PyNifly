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
        self.parent = parent_handler
        self.fps = self.parent.context.scene.render.fps


    def warn(self, msg):
        self.parent.warn(msg)
    

    def import_transform_interpolator(self, ti:NiTransformInterpolator, 
                            target_node:bpy.types.Object, 
                            action:bpy.types.Action, 
                            group_name:str, 
                            path_name:str, 
                            parentxf:Matrix):
        """
        Import a transform interpolator, including its data block.

        - Returns the rotation mode that must be set on the target. If this interpolator
          is using XYZ rotations, the rotation mode must be set to Euler. 
        """
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

        if path_name:
            path_prefix = path_name + "."
        else:
            path_prefix = ""

        if td.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
            rotation_mode = "XYZ"
            if td.xrotations or td.yrotations or td.zrotations:
                curveX = action.fcurves.new(path_prefix + "rotation_euler", index=0, action_group=group_name)
                curveY = action.fcurves.new(path_prefix + "rotation_euler", index=1, action_group=group_name)
                curveZ = action.fcurves.new(path_prefix + "rotation_euler", index=2, action_group=group_name)

                if len(td.xrotations) == len(td.yrotations) and len(td.xrotations) == len(td.zrotations):
                    for x, y, z in zip(td.xrotations, td.yrotations, td.zrotations):
                        # In theory the X/Y/Z dimensions do not have to have key frames at
                        # the same time signatures. But an Euler rotation needs all 3.
                        # Probably they will all line up because generating them any other
                        # way is surely hard. So hope for that and post a warning if not.
                        if not (NearEqual(x.time, y.time) and NearEqual(x.time, z.time)):
                            self.parent.warn(f"Keyframes do not align for '{path_name}. Animations may be incorrect.")

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

            curveW = action.fcurves.new(path_prefix + "rotation_quaternion", index=0, action_group=group_name)
            curveX = action.fcurves.new(path_prefix + "rotation_quaternion", index=1, action_group=group_name)
            curveY = action.fcurves.new(path_prefix + "rotation_quaternion", index=2, action_group=group_name)
            curveZ = action.fcurves.new(path_prefix + "rotation_quaternion", index=3, action_group=group_name)

            for i, k in enumerate(td.qrotations):
                kq = Quaternion(k.value)
                # Auxbones animations are not correct yet, but they seem to need something
                # different from animations on the full skeleton.
                if self.parent.auxbones:
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
            self.parent.warn(f"Nif contains unimplemented rotation type at {path_name}: {td.properties.rotationType}")

        # Seems like a value of + or - infinity in the Transform
        if len(td.translations) > 0:
            curveLocX = action.fcurves.new(path_prefix + "location", index=0, action_group=group_name)
            curveLocY = action.fcurves.new(path_prefix + "location", index=1, action_group=group_name)
            curveLocZ = action.fcurves.new(path_prefix + "location", index=2, action_group=group_name)
            for k in td.translations:
                v = Vector(k.value)

                if self.parent.auxbones:
                    pass 
                else:
                    v = v - tiv
                curveLocX.keyframe_points.insert(k.time * self.fps + 1, v[0])
                curveLocY.keyframe_points.insert(k.time * self.fps + 1, v[1])
                curveLocZ.keyframe_points.insert(k.time * self.fps + 1, v[2])

        return rotation_mode


    def import_float_interpolator(self, 
                                  fi:NiFloatInterpolator, 
                                  animated_obj:bpy.types.Object, 
                                  action:bpy.types.Action, 
                                  group_name:str, 
                                  path_name:str):
        """Import a float interpolator block."""
        td:NiFloatData = fi.data
        curve = action.fcurves.new(path_name)
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
            self.parent.warn(f"Unknown interpolation type for NiFloatInterpolator: {td.keys.interpolation}")


    def import_transform_controller(self, seq:NiSequence, block:ControllerLink):
        """Import transform controller block."""
        xf = Matrix.Identity(4)
        
        if block.node_name in self.parent.nif.nodes:
            target_node = self.parent.nif.nodes[block.node_name]

            if target_node._handle in self.parent.objects_created:
                target_obj = self.parent.objects_created[target_node._handle]
            else:
                self.parent.warn(f"Target object was not imported: {block.node_name}")
                return
            action_group = "Object Transforms"
            path_name = None
            action_name = f"{block.node_name}_{seq.name}"
        else:
            # Armature may have had bone names converted or not. Check both ways.
            name = block.node_name
            if name not in self.parent.armature.data.bones:
                name = self.parent.blender_name(name)
                if name not in self.parent.armature.data.bones:
                    name = None
            if name:
                action_group = name
                path_name = f'pose.bones["{action_group}"]'
                target_obj = self.parent.armature
                action_name = seq.name
                xf = self.parent.armature.data.bones[name].matrix_local.copy()
            else:
                self.parent.warn(f"Controller target not found: {block.node_name}")
                return 

        if not target_obj.animation_data:
            target_obj.animation_data_create()

        new_action = None
        if action_group != "Object Transforms":
            new_action = target_obj.animation_data.action

        if not new_action:
            new_action = bpy.data.actions.new(action_name)
            try:
                new_action.frame_start = seq.properties.startTime * self.fps + 1
                new_action.frame_end = seq.properties.stopTime * self.fps + 1
                new_action.use_frame_range = True
                new_action.use_fake_user = True
            except:
                pass
            new_action.asset_mark()

        rotmode = self.import_transform_interpolator(
            block.interpolator, 
            target_obj, 
            new_action, 
            action_group,
            path_name, 
            xf)
        
        if action_group == "Object Transforms":
            target_obj.rotation_mode = rotmode
        else:
            target_obj.pose.bones[name].rotation_mode = rotmode

        if not target_obj.animation_data.action:
            target_obj.animation_data.action = new_action


    def import_float_controller(
            self, ctlr:BSEffectShaderPropertyFloatController, target_obj):
        """Import float controller block."""
        animated_obj = target_obj.active_material.node_tree
        if not animated_obj.animation_data:
            animated_obj.animation_data_create()
        
        action_group = "Shader Nodetree"
        if ctlr.controlledVariable == CONTROLLED_VARIABLE_TYPES.U_Offset:
            controlled_node = "UV_Converter"
            controlled_input = 0
        elif ctlr.controlledVariable == CONTROLLED_VARIABLE_TYPES.V_Offset:
            controlled_node = "UV_Converter"
            controlled_input = 1
        elif ctlr.controlledVariable == CONTROLLED_VARIABLE_TYPES.U_Scale:
            controlled_node = "UV_Converter"
            controlled_input = 2
        elif ctlr.controlledVariable == CONTROLLED_VARIABLE_TYPES.V_Scale:
            controlled_node = "UV_Converter"
            controlled_input = 3
        else:
            self.parent.warn(f"Cannot handle controlled variable {ctlr.controlledVariable}")
            return

        action_name = f"{target_obj.name}_Controlled_Shader"
        path_name = f'nodes["{controlled_node}"].inputs[{controlled_input}].default_value'
        new_action = bpy.data.actions.new(action_name)
        try:
            new_action.frame_start = ctlr.properties.startTime * self.fps + 1
            new_action.frame_end = ctlr.properties.stopTime * self.fps + 1
            new_action.use_frame_range = True
            new_action.use_fake_user = True
            self.parent.context.scene.frame_end = int(1 + new_action.frame_end)
        except:
            pass
        new_action.asset_mark()

        self.import_float_interpolator(
            ctlr.interpolator, 
            animated_obj, 
            new_action, 
            action_group,
            path_name)
        
        if not animated_obj.animation_data.action:
            animated_obj.animation_data.action = new_action


    def import_color_controller(self, seq:NiSequence, block:ControllerLink):
        """Import one color controller block."""
        if block.node_name in self.parent.nif.nodes:
            target_node = self.parent.nif.nodes[block.node_name]

            if target_node._handle in self.parent.objects_created:
                target_obj = self.parent.objects_created[target_node._handle]
            else:
                self.parent.warn(f"Target object was not imported: {block.node_name}")
                return
        else:
            self.parent.warn(f"Target block not found in nif. Is it corrupt? ({block.node_name})")

        action_group = "Color Property Transforms"
        path_name = None
        action_name = f"{block.node_name}_{seq.name}"


    def import_controller_link(self, seq:NiSequence, block:ControllerLink):
        """Import one controlled block."""
        # Imports a single controller link (Controlled Block) within a ControllerSequence
        # block.
        if block.controller_type == "NiTransformController":
            self.import_transform_controller(seq, block)
        elif block.controller_type == 'BSEffectShaderPropertyColorController':
            self.import_color_controller(seq, block)
        elif block.controller_type == 'BSEffectShaderPropertyFloatController':
            self.import_float_controller(seq, block)
        else:
            self.parent.warn(f"Nif has unknown controller type: {block.controller_type}")
            return


    def import_sequences(self, seq):
        """Import a single controller sequence block."""
        # A controller sequence contains a list of ControllerLink structures, called
        # "Controlled Block" in NifSkope. (They are not full, separate blocks in the nif
        # file.)
        self.parent.context.scene.frame_end = 1 + int(
            (seq.properties.stopTime - seq.properties.startTime) * self.fps)
        for cb in seq.controlled_blocks:
            self.import_controller_link(seq, cb)


    def import_controller(self, ctlr, target_object=None):
        """Import the animation defined by a controller block."""
        if ctlr.blockname == "NiControllerSequence": 
            for seq in ctlr.sequences.values():
                self.import_sequences(seq)
            return
        elif ctlr.blockname == "BSEffectShaderPropertyFloatController":
            self.import_float_controller(ctlr, target_object)

    @classmethod
    def import_block(controller_class, controller_block, parent, target_object=None):
        importer = ControllerHandler(parent)
        importer.import_controller(controller_block, target_object=target_object)


    ### EXPORT ###

    def export_curves(self, arma, curve_list):
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
                

    def export_animation(self, animated_object, target_block, parent):
        """Export one animation action to a nif file."""
        action = animated_object.animation_data.action

        cp = controller.properties.copy()
        cp.startTime = (action.curve_frame_range[0]-1)/self.fps
        cp.stopTime = (action.curve_frame_range[1]-1)/self.fps
        cp.cycleType = CycleType.CYCLE_LOOP if action.use_cyclic else CycleType.CYCLE_CLAMP
        cp.frequency = 1.0
        controller.properties = cp

        # Collect list of curves. They will be picked off in clumps until the list is empty.
        curve_list = list(action.fcurves)
        while curve_list:
            targname, ti = self.export_curves(arma, curve_list)
            if targname and ti:
                controller.add_controlled_block(
                    name=self.nif.nif_name(targname),
                    interpolator=ti,
                    node_name = self.nif.nif_name(targname),
                    controller_type = "NiTransformController")

    @classmethod
    def export_shader_controller(cclass, obj, trishape):
        """Export an obj that has an animated shader."""
