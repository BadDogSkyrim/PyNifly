"""Action-scoped GUI for native HKX animation annotations."""

import json
from collections import Counter

import bpy
from bpy.props import IntProperty, StringProperty

from .import_hkx import (
    PYN_HKX_ANNOTATIONS_PROP,
    PYN_HKX_BONES_PROP,
    _annotation_entries_from_action,
)


def _active_action(context):
    obj = context.object
    if obj is None or obj.animation_data is None:
        return None
    return obj.animation_data.action


def _entries(action):
    entries = _annotation_entries_from_action(action)
    return list(entries) if entries is not None else []


def _write_entries(action, entries):
    normalized = [
        {"frame": int(round(entry["frame"])), "text": str(entry["text"]).strip()}
        for entry in entries
        if str(entry.get("text", "")).strip()
    ]
    normalized.sort(key=lambda entry: entry["frame"])
    action[PYN_HKX_ANNOTATIONS_PROP] = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":")
    )
    return normalized


def _remove_marker_mirror(scene, entries):
    remaining = Counter(
        (int(round(entry["frame"])), entry["text"])
        for entry in entries
    )
    for marker in list(scene.timeline_markers):
        key = (marker.frame, marker.name)
        if remaining[key] > 0:
            scene.timeline_markers.remove(marker)
            remaining[key] -= 1


def _mirror_entries(scene, old_entries, new_entries):
    _remove_marker_mirror(scene, old_entries)
    for entry in new_entries:
        scene.timeline_markers.new(
            entry["text"], frame=int(round(entry["frame"]))
        )


def _commit(context, action, old_entries, new_entries):
    normalized = _write_entries(action, new_entries)
    _mirror_entries(context.scene, old_entries, normalized)
    return normalized


class PYN_OT_hkx_annotation_add(bpy.types.Operator):
    bl_idname = "pynifly.hkx_annotation_add"
    bl_label = "Add Annotation"
    bl_description = "Add an annotation to the active Action and timeline mirror"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _active_action(context)
        wm = context.window_manager
        text = wm.pyn_hkx_annotation_text.strip()
        if action is None:
            self.report({'ERROR'}, "The selected Havok armature has no active Action")
            return {'CANCELLED'}
        if not text:
            self.report({'ERROR'}, "Annotation text cannot be empty")
            return {'CANCELLED'}
        old_entries = _entries(action)
        new_entries = old_entries + [{
            "frame": wm.pyn_hkx_annotation_frame,
            "text": text,
        }]
        _commit(context, action, old_entries, new_entries)
        wm.pyn_hkx_annotation_text = ""
        return {'FINISHED'}


class PYN_OT_hkx_annotation_edit(bpy.types.Operator):
    bl_idname = "pynifly.hkx_annotation_edit"
    bl_label = "Edit HKX Annotation"
    bl_description = "Edit this action-owned HKX annotation"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})
    frame: IntProperty(name="Frame")
    text: StringProperty(name="Text")

    def invoke(self, context, _event):
        action = _active_action(context)
        entries = _entries(action)
        if action is None or not 0 <= self.index < len(entries):
            return {'CANCELLED'}
        self.frame = int(round(entries[self.index]["frame"]))
        self.text = entries[self.index]["text"]
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, _context):
        col = self.layout.column(align=True)
        col.prop(self, "frame")
        col.prop(self, "text")

    def execute(self, context):
        action = _active_action(context)
        old_entries = _entries(action)
        text = self.text.strip()
        if action is None or not 0 <= self.index < len(old_entries):
            self.report({'ERROR'}, "Annotation no longer exists")
            return {'CANCELLED'}
        if not text:
            self.report({'ERROR'}, "Annotation text cannot be empty")
            return {'CANCELLED'}
        new_entries = list(old_entries)
        new_entries[self.index] = {"frame": self.frame, "text": text}
        _commit(context, action, old_entries, new_entries)
        return {'FINISHED'}


class PYN_OT_hkx_annotation_remove(bpy.types.Operator):
    bl_idname = "pynifly.hkx_annotation_remove"
    bl_label = "Remove HKX Annotation"
    bl_description = "Remove this action-owned HKX annotation"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        action = _active_action(context)
        old_entries = _entries(action)
        if action is None or not 0 <= self.index < len(old_entries):
            return {'CANCELLED'}
        new_entries = list(old_entries)
        new_entries.pop(self.index)
        _commit(context, action, old_entries, new_entries)
        return {'FINISHED'}


class PYN_OT_hkx_annotations_pull_markers(bpy.types.Operator):
    bl_idname = "pynifly.hkx_annotations_pull_markers"
    bl_label = "Use Timeline Markers"
    bl_description = (
        "Replace action annotations with timeline markers inside the Action frame range"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _active_action(context)
        if action is None:
            return {'CANCELLED'}
        if action.use_frame_range:
            frame_start, frame_end = action.frame_start, action.frame_end
        else:
            frame_start, frame_end = action.frame_range
        entries = [
            {"frame": marker.frame, "text": marker.name}
            for marker in context.scene.timeline_markers
            if marker.name and frame_start <= marker.frame <= frame_end
        ]
        _write_entries(action, entries)
        self.report({'INFO'}, f"Stored {len(entries)} timeline markers on {action.name}")
        return {'FINISHED'}


class PYN_OT_hkx_annotations_rebuild_markers(bpy.types.Operator):
    bl_idname = "pynifly.hkx_annotations_rebuild_markers"
    bl_label = "Rebuild Timeline Mirror"
    bl_description = "Recreate timeline markers for the active Action annotations"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _active_action(context)
        if action is None:
            return {'CANCELLED'}
        entries = _entries(action)
        _mirror_entries(context.scene, entries, entries)
        self.report({'INFO'}, f"Mirrored {len(entries)} annotations")
        return {'FINISHED'}


class PYN_PT_hkx_annotations(bpy.types.Panel):
    bl_idname = "PYN_PT_hkx_annotations"
    bl_label = "PyNifly HKX Annotations"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj is not None
            and obj.type == 'ARMATURE'
            and bool(obj.get(PYN_HKX_BONES_PROP))
        )

    def draw(self, context):
        layout = self.layout
        action = _active_action(context)
        if action is None:
            layout.label(text="No active Action", icon='ERROR')
            return

        layout.label(text=f"Action: {action.name}", icon='ACTION')
        entries = _entries(action)
        if entries:
            box = layout.box()
            for index, entry in enumerate(entries):
                row = box.row(align=True)
                row.label(text=str(int(round(entry["frame"]))))
                row.label(text=entry["text"])
                edit = row.operator(
                    PYN_OT_hkx_annotation_edit.bl_idname,
                    text="",
                    icon='GREASEPENCIL',
                )
                edit.index = index
                remove = row.operator(
                    PYN_OT_hkx_annotation_remove.bl_idname,
                    text="",
                    icon='X',
                )
                remove.index = index
        else:
            layout.label(text="No action-owned annotations")

        add_box = layout.box()
        wm = context.window_manager
        row = add_box.row(align=True)
        row.prop(wm, "pyn_hkx_annotation_frame")
        row.prop(wm, "pyn_hkx_annotation_text")
        add_box.operator(PYN_OT_hkx_annotation_add.bl_idname, icon='ADD')

        row = layout.row(align=True)
        row.operator(PYN_OT_hkx_annotations_pull_markers.bl_idname)
        row.operator(PYN_OT_hkx_annotations_rebuild_markers.bl_idname)


_CLASSES = (
    PYN_OT_hkx_annotation_add,
    PYN_OT_hkx_annotation_edit,
    PYN_OT_hkx_annotation_remove,
    PYN_OT_hkx_annotations_pull_markers,
    PYN_OT_hkx_annotations_rebuild_markers,
    PYN_PT_hkx_annotations,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.pyn_hkx_annotation_frame = IntProperty(
        name="Frame", default=0
    )
    bpy.types.WindowManager.pyn_hkx_annotation_text = StringProperty(name="Text")


def unregister():
    for name in ("pyn_hkx_annotation_frame", "pyn_hkx_annotation_text"):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
