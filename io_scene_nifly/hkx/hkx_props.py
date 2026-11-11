"""HKX settings that belong to one animation, kept on its action.

An armature holds many actions; whether an animation is additive, which bones it has
tracks for, and how it's compressed are facts about each one. Import sets them from the
file, export writes them back, and the PyNifly HKX panel in the Action editor shows them.
"""
import bpy

# Havok blendHint values. hk_2010 (Skyrim) has NORMAL and ADDITIVE = 1; hk_2014 (FO4)
# renamed 1 ADDITIVE_DEPRECATED and added ADDITIVE = 2. All of them hold deltas from the
# rest pose; we keep the value read so a round trip writes it back unchanged.
BLEND_HINT_NORMAL = 0
BLEND_HINT_ADDITIVE = {'SKYRIM': 1, 'FO4': 2}

# Custom properties: on a sync-offset Empty, marking it (nif export skips it); on an action,
# root-motion samples import had no Root bone to put on, written back as they were.
SYNC_OFFSET_TAG = 'pynHkxSyncOffset'
ROOT_MOTION_PROP = 'PYN_HKX_ROOT_MOTION'


class PynHkxActionProps(bpy.types.PropertyGroup):
    blend: bpy.props.EnumProperty(
        name="Blend",
        items=[('NORMAL', "Normal", "Keys are the bones' poses"),
               ('ADDITIVE', "Additive",
                "Keys are deltas from the rest pose, added to whatever else is playing. "
                "Preview over a base animation with an NLA strip set to Combine")],
        default='NORMAL')
    blend_hint_raw: bpy.props.IntProperty(
        name="Blend hint",
        description="The file's exact blendHint, written back for an additive action",
        default=BLEND_HINT_NORMAL)
    tracks: bpy.props.EnumProperty(
        name="Tracks",
        items=[('ALL', "All bones", "Write a track for every bone of the skeleton"),
               ('KEYED', "Keyed bones",
                "Write tracks only for bones the action keys or a constraint drives")],
        default='ALL')
    compression: bpy.props.EnumProperty(
        name="Compression",
        items=[('SPLINE', "Spline", "Spline-compressed, the usual format"),
               ('LOSSLESS', "Lossless", "Exact values (FO4), as 1st-person animations use"),
               ('UNCOMPRESSED', "Uncompressed",
                "Exact values, every bone every frame (interleaved). Not used by vanilla "
                "animations; some modded creatures have it")],
        default='SPLINE')
    rotation_bits: bpy.props.EnumProperty(
        name="Rotation bits",
        description="Precision of spline-compressed rotations",
        items=[('40', "40-bit", "What vanilla animations mostly use"),
               ('48', "48-bit", "More precise; for jitter on fine motion, such as weapons")],
        default='40')
    root_motion: bpy.props.EnumProperty(
        name="Root motion",
        description="Where the Root bone's travel and turn go on export",
        items=[('AUTO', "Game default",
                "FO4: the reference frame. Skyrim: Root's own track (Skyrim keeps root "
                "motion in the behaviour project)"),
               ('EXTRACT', "Reference frame",
                "Root's travel and turn about Z become the reference frame, which moves the "
                "actor; Root's track keeps the rest. Skyrim's dragon flight does this"),
               ('KEEP', "Root bone", "Root's track keeps all its motion")],
        default='AUTO')
    sync_offset: bpy.props.PointerProperty(
        name="Sync offset",
        description="Paired animations: an Empty, child of the armature, placing this "
                    "actor relative to its partner. Its location and turn about Z are "
                    "the offset",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'EMPTY')


# AnimationData.compression (the file's animation class) -> the action's setting
_COMPRESSION = {'SPLINE': 'SPLINE', 'LOSSLESS': 'LOSSLESS', 'INTERLEAVED': 'UNCOMPRESSED'}


def set_from_file(action, anim_data, partial):
    """Record a just-imported animation's settings on its action. partial: the file has
    tracks for only some of the skeleton's bones."""
    blend_hint = anim_data.blend_hint
    action.pyn_hkx.blend = 'NORMAL' if blend_hint == BLEND_HINT_NORMAL else 'ADDITIVE'
    action.pyn_hkx.blend_hint_raw = blend_hint
    action.pyn_hkx.tracks = 'KEYED' if partial else 'ALL'
    action.pyn_hkx.compression = _COMPRESSION.get(anim_data.compression, 'SPLINE')
    action.pyn_hkx.rotation_bits = '48' if anim_data.rot_quant in (2, 5) else '40'
    if any(abs(v) > 1e-6 for s in anim_data.root_motion for v in s):
        action[ROOT_MOTION_PROP] = [v for s in anim_data.root_motion for v in s]


def extracts_root_motion(action, game):
    """Whether export takes the root motion off Root, for this action and game."""
    setting = action.pyn_hkx.root_motion
    return setting == 'EXTRACT' or (setting == 'AUTO' and game == 'FO4')


def stored_root_motion(action):
    """Root-motion samples kept on the action because import had no Root bone for them."""
    flat = list(action.get(ROOT_MOTION_PROP, []))
    return [flat[i:i + 4] for i in range(0, len(flat) - 3, 4)]


def add_sync_offset(action, armature, x=0.0, y=0.0, z=0.0, yaw=0.0):
    """Create the action's sync-offset Empty under the armature and point the action to it."""
    empty = bpy.data.objects.new(f"SyncAnimOffset:{action.name}", None)
    empty.empty_display_type = 'CONE'
    empty.empty_display_size = 5.0
    empty[SYNC_OFFSET_TAG] = True
    for coll in armature.users_collection:
        coll.objects.link(empty)
    empty.parent = armature
    empty.location = (x, y, z)
    empty.rotation_euler = (0.0, 0.0, yaw)
    action.pyn_hkx.sync_offset = empty
    return empty


def sync_offset_for(action, armature):
    """The action's sync offset as (x, y, z, yaw), relative to the armature; None if the
    action has none."""
    empty = action.pyn_hkx.sync_offset
    if empty is None:
        return None
    m = armature.matrix_world.inverted() @ empty.matrix_world
    t = m.to_translation()
    return [t.x, t.y, t.z, m.to_euler().z]


def file_compression(action):
    """The animation class to write for this action, as AnimationData.compression. The
    writers substitute the exact format their game has: FO4 writes lossless for
    Uncompressed, Skyrim (hk_2010, no lossless class) writes interleaved for Lossless."""
    return {v: k for k, v in _COMPRESSION.items()}[action.pyn_hkx.compression]


def blend_hint_for(action, armature, game):
    """The blendHint to write for this action. game is 'SKYRIM' or 'FO4'.

    An action with no setting of its own falls back to the armature flag that 30.2.0 and
    earlier set on import."""
    from .import_hkx import PYN_HKX_ADDITIVE_PROP
    grp = action.pyn_hkx
    if grp.is_property_set('blend'):
        additive = grp.blend == 'ADDITIVE'
    else:
        additive = bool(armature.get(PYN_HKX_ADDITIVE_PROP, False))
    if not additive:
        return BLEND_HINT_NORMAL
    raw = grp.blend_hint_raw
    if game == 'FO4' and raw in (1, 2):
        return raw
    return BLEND_HINT_ADDITIVE[game]


class PYN_PT_hkx_action(bpy.types.Panel):
    """The active action's HKX settings, in the Action editor sidebar."""
    bl_idname = "PYN_PT_hkx_action"
    bl_label = "PyNifly HKX"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = "PyNifly"

    @staticmethod
    def _action(context):
        obj = context.active_object
        ad = obj.animation_data if obj is not None else None
        return ad.action if ad is not None else None

    @classmethod
    def poll(cls, context):
        return cls._action(context) is not None

    def draw(self, context):
        grp = self._action(context).pyn_hkx
        col = self.layout.column()
        col.prop(grp, 'blend')
        col.prop(grp, 'tracks')
        col.prop(grp, 'compression')
        if grp.compression == 'SPLINE':
            col.prop(grp, 'rotation_bits')
        col.prop(grp, 'root_motion')
        row = col.row(align=True)
        row.prop(grp, 'sync_offset')
        if grp.sync_offset is None:
            row.operator(PYN_OT_add_sync_offset.bl_idname, text="", icon='ADD')


class PYN_OT_add_sync_offset(bpy.types.Operator):
    """Add a sync-offset Empty for this paired animation, at the armature's origin"""
    bl_idname = "pynifly.hkx_add_sync_offset"
    bl_label = "Add Sync Offset"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'ARMATURE'
                and PYN_PT_hkx_action._action(context) is not None)

    def execute(self, context):
        add_sync_offset(PYN_PT_hkx_action._action(context), context.active_object)
        return {'FINISHED'}


_classes = (PynHkxActionProps, PYN_OT_add_sync_offset, PYN_PT_hkx_action)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.Action.pyn_hkx = bpy.props.PointerProperty(type=PynHkxActionProps)


def unregister():
    if hasattr(bpy.types.Action, 'pyn_hkx'):
        del bpy.types.Action.pyn_hkx
    for c in reversed(_classes):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
