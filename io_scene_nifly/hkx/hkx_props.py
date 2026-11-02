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


_classes = (PynHkxActionProps, PYN_PT_hkx_action)


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
