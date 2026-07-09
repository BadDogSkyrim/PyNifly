"""
Typed property groups auto-generated from the ctypes buffer structs.

First slice: the shader properties (NiShaderBuf) as a Material-attached PropertyGroup,
replacing the flat material["<field>"] custom-property approach with typed,
panel-surfaced properties. Import writes the group (import_shader_group); export reads
it back (shader_store + ensure_shader_migrated for legacy .blend files).

The generator maps each buffer field's ctypes type to a bpy.props definition; the
GroupStore adapter lets the group stand in for the dict-like store that
`pynStructure.extract()`/`load()` already speak, so no per-field wiring is needed.
See docs/property_architecture.md.
"""

import bpy
import logging
from ctypes import c_float, c_uint8, c_uint16, c_uint32, c_char, c_int
from ..pyn.nifdefs import (NiShaderBuf, bhkRigidBodyProps,
                           BSValueNodeBuf, NiSwitchNodeBuf, BSMultiBoundNodeBuf)
from ..pyn.structs import _enum_types
# NISHADER_IGNORE = shader fields represented in Blender's nodes (UV offset/scale, emissive,
# clamp, glossiness…); they must NOT become properties. shader_io is imported before this
# module in nif/__init__.py, so this top-level import is safe.
from .shader_io import NISHADER_IGNORE
from .collision import COLLISION_BODY_IGNORE

log = logging.getLogger("pynifly")

# ---------------------------------------------------------------------------
# ctypes -> bpy.props mapping
# ---------------------------------------------------------------------------

# Buffer-management / ID fields that extract() never stores (not user data).
_SKIP_FIELDS = {
    'bufSize', 'bufType', 'nameID', 'bBSLightingShaderProperty', 'bslspShaderType',
    'controllerID', 'extraDataCount', 'numSF1', 'numSF2', 'textureSetID',
    'rootMaterialNameID', 'hasTextureArrays', 'numTextureArrays',
    # Vestigial: nifly deleted the legacy BSShaderProperty::shaderFlags (uint16). We keep
    # the buffer slot for ABI, hardcode it on read, never write it. The real flag words are
    # Shader_Flags_1/_2. Not user data.
    'shaderFlags',
}

# Fields whose extract_field()/extract stores an enum *string* (flag fullnames, type name,
# collision-layer / motion-system / etc. names) rather than the raw integer — force
# StringProperty so setattr() of the extracted value succeeds and load() parses it back.
# Sourced from structs._enum_types, the single registry of self-converting enum fields
# (covers shader flags/type AND the bhkRigidBody physics enums).
_STRING_OVERRIDE = set(_enum_types)


def _bprop_for(fieldname, ctype, default_buf):
    """Return a (bpy.props function call) for one buffer field, or None to skip."""
    tname = ctype.__name__

    if fieldname in _STRING_OVERRIDE:
        return bpy.props.StringProperty(name=fieldname, default="")

    # scalar float
    if ctype is c_float:
        return bpy.props.FloatProperty(name=fieldname,
                                       default=float(getattr(default_buf, fieldname)))
    # unsigned integers -> IntProperty. Blender IntProperty is signed 32-bit; a c_uint32
    # ref/flags field whose default sets the high bit (e.g. NODEID_NONE) overflows and
    # crashes registration, so skip those — they're never user-facing physics/data props.
    if ctype in (c_uint8, c_uint16, c_uint32, c_int):
        dflt = int(getattr(default_buf, fieldname))
        if not (-2**31 <= dflt < 2**31):
            return None
        return bpy.props.IntProperty(name=fieldname, default=dflt)
    # single char: these buffer fields (doTranslucency, thickObject, useSSR…) are
    # boolean-ish small ints, not text -> IntProperty. extract() hands them over as a
    # decoded 1-char string; GroupStore.__setitem__ coerces that to the int, and load()
    # assigns the int straight back to the c_char field (ctypes accepts an integer).
    if ctype is c_char:
        raw = getattr(default_buf, fieldname)
        dflt = raw[0] if isinstance(raw, (bytes, bytearray)) and len(raw) else int(raw or 0)
        return bpy.props.IntProperty(name=fieldname, default=dflt)

    # fixed-size char arrays (CHAR256 texture paths) -> StringProperty. ctypes returns
    # these as bytes; keep the buffer default so an unset field round-trips to the same value.
    if tname.startswith('c_char_Array_'):
        raw = getattr(default_buf, fieldname)
        dflt = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else str(raw)
        return bpy.props.StringProperty(name=fieldname, default=dflt)

    # fixed-size float arrays (VECTOR2/3/4) -> FloatVectorProperty; color-named -> color picker
    if tname.startswith('c_float_Array_'):
        n = int(tname.rsplit('_', 1)[1])
        try:
            dflt = tuple(float(x) for x in getattr(default_buf, fieldname))
        except Exception:
            dflt = tuple(0.0 for _ in range(n))
        kwargs = dict(name=fieldname, size=n, default=dflt)
        if 'color' in fieldname.lower() and n in (3, 4):
            kwargs['subtype'] = 'COLOR'
            kwargs['min'] = 0.0  # color picker; no hard max so HDR values aren't clamped
        return bpy.props.FloatVectorProperty(**kwargs)

    # anything else (byte arrays, char[256], etc.) — skip for the PoC
    return None


def make_group_class(clsname, buf_cls, skip=None):
    """Dynamically build a PropertyGroup class from a buffer struct's _fields_."""
    skip = (skip or set()) | _SKIP_FIELDS
    default_buf = buf_cls()
    annotations = {}
    for fn, ct in buf_cls._fields_:
        if fn in skip:
            continue
        prop = _bprop_for(fn, ct, default_buf)
        if prop is not None:
            annotations[fn] = prop
    return type(clsname, (bpy.types.PropertyGroup,), {'__annotations__': annotations})


# Field names this group actually carries (for the import populator + panel).
def group_fieldnames(group):
    return list(getattr(group, '__annotations__', {}).keys())


# ---------------------------------------------------------------------------
# The shader group (PoC slice)
# ---------------------------------------------------------------------------

PynShaderProps = make_group_class('PynShaderProps', NiShaderBuf, skip=set(NISHADER_IGNORE))


# ---------------------------------------------------------------------------
# GroupStore: adapt a typed PropertyGroup to the dict-like store that
# pynStructure.extract()/load() already speak, so the group is a drop-in
# replacement for the old material["<field>"] custom-property store.
# ---------------------------------------------------------------------------

class GroupStore:
    """Present a PropertyGroup as the dict-like store extract()/load() expect.

    * __setitem__ (extract writes here): decode bytes / ctypes char arrays to str,
      then setattr onto the typed prop.
    * __getitem__ (load reads here): a float-vector prop is returned as a
      "(a, b, c)" string so _get_from_store's eval-path rebuilds a ctypes VECTOR
      (a bare list would fail ctypes array assignment). Scalars / flag strings /
      char-array strings pass through natively.
    * __contains__: a flag/type string-override field reports absent while empty,
      so an unset flag leaves the buffer at its own default — matching the old
      sparse custom-property behaviour (only non-defaults were ever stored).
    """
    def __init__(self, group):
        self._g = group
        self._names = set(group_fieldnames(group))

    def __contains__(self, k):
        if k not in self._names:
            return False
        if k in _STRING_OVERRIDE and getattr(self._g, k) == "":
            return False
        return True

    def keys(self):
        return list(self._names)

    def get(self, k, default=None):
        return self[k] if k in self else default

    def __getitem__(self, k):
        v = getattr(self._g, k)
        if not isinstance(v, str) and hasattr(v, '__len__'):
            return str(tuple(v))
        return v

    def __setitem__(self, k, v):
        if k not in self._names:
            return
        if isinstance(v, bytes):
            v = v.decode('utf-8', 'replace')
        elif type(v).__name__.startswith('c_char_Array'):
            v = bytes(v).split(b'\x00', 1)[0].decode('utf-8', 'replace')
        try:
            setattr(self._g, k, v)
            return
        except (TypeError, ValueError, OverflowError):
            pass
        # c_char fields arrive as a decoded 1-char string but the group holds them as
        # ints (see _bprop_for) — coerce the byte value.
        if isinstance(v, str):
            try:
                setattr(self._g, k, ord(v) if len(v) == 1 else int(v))
            except (TypeError, ValueError, OverflowError):
                pass  # leave at default


# Marks a material whose pyn_shader group holds the authoritative shader data, so
# ensure_shader_migrated() doesn't re-import stale legacy custom props over it.
_MIGRATED_KEY = 'pyn_shader_migrated'


def shader_store(material):
    """The GroupStore wrapping this material's shader property group."""
    return GroupStore(material.pyn_shader)


def import_shader_group(material, shader_props, game):
    """Populate the typed shader group from a freshly-read NiShaderBuf (import)."""
    material[_MIGRATED_KEY] = True  # fresh data is authoritative; no legacy migration
    shader_props.extract(GroupStore(material.pyn_shader),
                         ignore=NISHADER_IGNORE, game=game)


def ensure_shader_migrated(material):
    """First-touch migration for old .blend files / custom-prop-driven export: copy any
    legacy per-field custom properties onto the typed group. New imports set the flag
    directly, so this is a no-op for them."""
    if material.get(_MIGRATED_KEY):
        return
    store = GroupStore(material.pyn_shader)
    keys = set(material.keys())
    for fn in group_fieldnames(material.pyn_shader):
        if fn in keys:
            try:
                store[fn] = material[fn]
            except Exception:
                pass
    material[_MIGRATED_KEY] = True


# ---------------------------------------------------------------------------
# Field -> base game
# ---------------------------------------------------------------------------
# Best-shot mapping derived from nifly's BSLightingShaderProperty::Sync version guards
# (src/Shaders.cpp), collapsed to base games (Skyrim LE/SE = "SKYRIM"):
#   no guard / Stream<130 -> SKYRIM ; IsFO4()/Stream>=130 -> FO4 ;
#   Stream>139 & <172 -> FO76 ; Stream>=172 -> STARFIELD.
# Only non-Skyrim fields are listed; everything unlisted is common (SKYRIM+). REVIEW.
GAME_ORDER = ['SKYRIM', 'FO4', 'FO76', 'STARFIELD']
GAME_LABEL = {'FO4': 'Fallout 4', 'FO76': 'Fallout 76', 'STARFIELD': 'Starfield'}

_SHADER_FIELD_GAME = {
    # FO4+ (IsFO4() / User==12 && Stream>=130 blocks)
    'subsurfaceRolloff': 'FO4',
    'rimlightPower2': 'FO4',
    'backlightPower': 'FO4',
    'grayscaleToPaletteScale': 'FO4',
    'fresnelPower': 'FO4',
    'wetnessSpecScale': 'FO4',
    'wetnessSpecPower': 'FO4',
    'wetnessMinVar': 'FO4',
    'wetnessEnvmapScale': 'FO4',      # Stream==130 (base FO4) only
    'wetnessFresnelPower': 'FO4',
    'wetnessMetalness': 'FO4',
    'useSSR': 'FO4',                  # case 1, IsFO4() guard
    'wetnessUseSSR': 'FO4',           # case 1, IsFO4() guard
    'Skin_Tint_Alpha': 'FO4',         # case 5, Stream>=130 guard (skinTintColor itself is common)
    # FO76 (User==12 && Stream>139, Stream<172)
    'wetnessUnknown1': 'FO76',        # Stream>130
    'wetnessUnknown2': 'FO76',        # Stream>=155
    'lumEmittance': 'FO76',
    'exposureOffset': 'FO76',
    'finalExposureMin': 'FO76',
    'finalExposureMax': 'FO76',
    'doTranslucency': 'FO76',
    'subsurfaceColor': 'FO76',
    'transmissiveScale': 'FO76',
    'turbulence': 'FO76',
    'thickObject': 'FO76',
    'mixAlbedo': 'FO76',
    # STARFIELD (Stream>=172): the SF-only floats (unkFloat/unkShort) aren't in this buffer — none here.
    # COMMON (unlisted) includes the shader-TYPE-gated fields — present in any game that uses the
    # type, not version-gated: skinTintColor (type5), hairTintColor (type6), maxPasses/scale (type7),
    # parallax* (type11), sparkleParameters (type14 "Sparkle Snow", Skyrim), eye* (type16),
    # Env_Map_Scale (type1). Also uncertain/common (REVIEW): emissiveColor, emittanceColor.
}


def field_game(fieldname):
    return _SHADER_FIELD_GAME.get(fieldname, 'SKYRIM')


def _fields_by_game(group):
    out = {g: [] for g in GAME_ORDER}
    for fn in group_fieldnames(group):
        out[field_game(fn)].append(fn)
    return out


# ---------------------------------------------------------------------------
# Panels — main draws the common (Skyrim+) fields; a collapsible child panel per
# later game shows that game's added fields (all shown, non-common collapsed).
# ---------------------------------------------------------------------------

class PYN_PT_shader(bpy.types.Panel):
    bl_idname = "PYN_PT_shader"
    bl_label = "PyNifly Shader"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        layout = self.layout
        grp = getattr(context.material, 'pyn_shader', None)
        if grp is None:
            layout.label(text="(no PyNifly shader data)")
            return
        col = layout.column(align=True)
        for fn in _fields_by_game(grp)['SKYRIM']:
            col.prop(grp, fn)


def _make_shader_child_panel(game):
    def draw(self, context):
        grp = getattr(context.material, 'pyn_shader', None)
        if grp is None:
            return
        col = self.layout.column(align=True)
        for fn in _fields_by_game(grp)[game]:
            col.prop(grp, fn)
    return type(
        f'PYN_PT_shader_{game.lower()}',
        (bpy.types.Panel,),
        {
            'bl_idname': f'PYN_PT_shader_{game.lower()}',
            'bl_parent_id': 'PYN_PT_shader',
            'bl_label': GAME_LABEL[game],
            'bl_space_type': 'PROPERTIES',
            'bl_region_type': 'WINDOW',
            'bl_context': 'material',
            'bl_options': {'DEFAULT_CLOSED'},
            'poll': classmethod(lambda cls, context: context.material is not None),
            'draw': draw,
        },
    )


# Only build child panels for later games that actually have fields in this group.
_child_panels = [
    _make_shader_child_panel(g)
    for g in GAME_ORDER[1:]
    if any(field_game(fn) == g for fn in getattr(PynShaderProps, '__annotations__', {}))
]


# ---------------------------------------------------------------------------
# Generic per-block property groups (Object-attached)
# ---------------------------------------------------------------------------
# The shader was one buffer struct on Material. Object blocks are many buffer structs,
# but the extract/load-to-object surface is small (import_nif node + shape, collision.py).
# A block buffer with a registered group uses it; anything un-converted falls back to the
# old flat obj["<field>"] custom props, so this rolls out incrementally and safely.
#
# Curated ignore lists — structural / ID / derived / Blender-represented fields are never
# user properties (mirrors NISHAPE_IGNORE but kept self-contained here so the per-block
# decisions live with the groups and pyn_props has no import_nif dependency).

_COMMON_BLOCK_IGNORE = {
    'bufSize', 'bufType', 'id', 'nameID', 'controllerID', 'extraDataCount', 'flags',
    'transform', 'collisionID', 'propertyCount', 'childCount', 'effectCount',
}
_NODE_IGNORE = _COMMON_BLOCK_IGNORE | {'multiBoundID'}  # multiBoundID: ref, rebuilt on export

_block_specs = []          # ordered list of {'attr','grp'} for registration + panel
_spec_by_bufcls = {}       # exact buffer class -> spec (MRO-walked in _spec_for_bufcls)


def _register_block_group(model_buf, attr, ignore, also=()):
    """Build+record a group class from model_buf, mapped from model_buf (and any `also`
    buffer classes that should share it, e.g. LOD trishape variants)."""
    grp = make_group_class('Pyn_' + attr, model_buf, skip=set(ignore))
    spec = {'attr': attr, 'grp': grp, 'buf': model_buf, 'ignore': list(ignore)}
    for bc in (model_buf,) + tuple(also):
        _spec_by_bufcls[bc] = spec
    _block_specs.append(spec)
    return spec


def _spec_for_bufcls(buf_cls):
    for klass in getattr(buf_cls, '__mro__', ()):
        s = _spec_by_bufcls.get(klass)
        if s is not None:
            return s
    return None


def _bufcls_of(block_cls):
    """The buffer STRUCT class a NiObject block type constructs. Must come from getbuf():
    NiObject.buffer_types maps to block classes, not buffer structs."""
    try:
        return type(block_cls.getbuf())
    except Exception:
        return None


def _migkey(attr):
    return attr + '_migrated'


def import_block_props(datablock, buf, ignore=None, game='SKYRIM'):
    """Import a block's buffer into its typed group if registered, else flat custom props."""
    spec = _spec_for_bufcls(type(buf))
    if spec is None:
        buf.extract(datablock, ignore=ignore, game=game)
        return
    datablock[_migkey(spec['attr'])] = True  # authoritative; no legacy migration needed
    buf.extract(GroupStore(getattr(datablock, spec['attr'])), ignore=ignore, game=game)


def ensure_block_migrated(datablock, spec):
    """First-touch migration of legacy flat custom props onto a block group — for old .blend
    files and the set-custom-prop-to-drive-export workflow. Goes THROUGH the buffer
    (flat props -> buffer -> group) so it reuses the canonical converters and normalises
    every legacy representation (int enums, matrix strings, short vectors)."""
    key = _migkey(spec['attr'])
    if datablock.get(key):
        return
    try:
        buf = spec['buf']()
        buf.load(datablock, ignore=spec['ignore'])
        buf.extract(GroupStore(getattr(datablock, spec['attr'])), ignore=spec['ignore'])
    except Exception:
        log.exception(f"pyn_props: could not migrate legacy {spec['attr']} props on {datablock.name}")
    datablock[key] = True


def block_values(datablock, block_cls):
    """The values source getbuf() should load from on export: the typed group (migrating
    legacy props first) if registered for this block's buffer, else the datablock itself."""
    spec = _spec_for_bufcls(_bufcls_of(block_cls)) if block_cls is not None else None
    if spec is None:
        return datablock
    ensure_block_migrated(datablock, spec)
    return GroupStore(getattr(datablock, spec['attr']))


# Registered blocks. Only buffers that add real, user-facing properties get groups.
# Plain NiNode carries no user fields once structural fields are ignored; NiShape's only
# non-structural field (hasFullPrecision) is a precision flag driven by the export setting,
# not user data — both fall back to flat props (unchanged behaviour) via the dispatch.
_register_block_group(BSValueNodeBuf, 'pyn_valuenode', _NODE_IGNORE)        # value, valueNodeFlags
_register_block_group(NiSwitchNodeBuf, 'pyn_switchnode', _NODE_IGNORE)      # switchFlags, switchActiveIndex
_register_block_group(BSMultiBoundNodeBuf, 'pyn_multibound', _NODE_IGNORE)  # cullingMode
# bhkRigidBody: the physics props (restitution, gravityFactor, maxLin/AngVelocity,
# penetrationDepth, motion/deactivator/solver/qualityType, collision filter/response…).
# mass/friction/damping live on Blender's native rigid_body and stay in COLLISION_BODY_IGNORE.
# The stored datablock is the collision shape object (import stores body props on the shape).
# Also drop the non-physics c_uint32 refs/handles/flags (shapeID is set from the exported
# shape; worldObj*/unknownInt*/bodyFlagsInt are havok-internal, not user data).
_RIGIDBODY_IGNORE = set(COLLISION_BODY_IGNORE) | {
    'shapeID', 'worldObjData', 'worldObjSize', 'worldObjCapFlags',
    'unknownInt1', 'unknownInt2', 'bodyFlagsInt',
}
_register_block_group(bhkRigidBodyProps, 'pyn_rigidbody', _RIGIDBODY_IGNORE)


_BLOCK_LABEL = {
    'pyn_valuenode': 'BSValueNode', 'pyn_switchnode': 'NiSwitchNode',
    'pyn_multibound': 'BSMultiBoundNode', 'pyn_rigidbody': 'Rigid Body',
}


# ---------------------------------------------------------------------------
# Hand-wired object groups
# ---------------------------------------------------------------------------
# Blocks whose bespoke storage / scale handling / enum-name conventions don't fit the
# generic buffer-derived path get a hand-authored PropertyGroup here. They share the same
# GroupStore read/write, migration, and PYN_PT_block panel as the generated groups.

_handwired_specs = []  # {attr, grp, label, legacy}   legacy: {field: legacy_custom_prop_key}


def _register_handwired_group(clsname, attr, annotations, label, legacy=None):
    grp = type(clsname, (bpy.types.PropertyGroup,), {'__annotations__': dict(annotations)})
    spec = {'attr': attr, 'grp': grp, 'label': label, 'legacy': legacy or {}}
    _handwired_specs.append(spec)
    return spec


def _handwired_spec(attr):
    return next((s for s in _handwired_specs if s['attr'] == attr), None)


def ensure_handwired_migrated(datablock, spec):
    """First-touch migration of legacy flat custom props onto a hand-wired group."""
    key = _migkey(spec['attr'])
    if datablock.get(key):
        return
    grp = getattr(datablock, spec['attr'])
    for fn, legacy_key in spec['legacy'].items():
        if legacy_key in datablock:
            try:
                setattr(grp, fn, datablock[legacy_key])
            except (TypeError, ValueError):
                pass
    datablock[key] = True


def handwired_store(datablock, attr):
    """GroupStore for a hand-wired group, migrating any legacy flat props first.
    Suitable as the `values` source for a buffer ctor / .load() on export."""
    spec = _handwired_spec(attr)
    ensure_handwired_migrated(datablock, spec)
    return GroupStore(getattr(datablock, spec['attr']))


# --- Collision shape props (bhkBox/Capsule/Sphere/ConvexVertices/List) -------
# Only two real per-shape props; everything else is mesh geometry. bhkRadius keeps its
# Blender-unit (scaled) value as before; bhkMaterial is the SkyrimHavokMaterial name string
# (StringProperty for robustness — unknown materials occur; matches the rigid-body enum
# fields, which are also name strings).
PynCollShapeProps = None  # set below via _register_handwired_group


def set_collshape(obj, material_name, radius):
    """Import: store a collision shape's material + convex radius on obj.pyn_collshape."""
    g = obj.pyn_collshape
    if material_name is not None:
        g.bhkMaterial = str(material_name)
    if radius is not None:
        g.bhkRadius = float(radius)
    obj[_migkey('pyn_collshape')] = True


def collshape_store(obj):
    """Export: the values source for a collision-shape buffer ctor / .load()."""
    return handwired_store(obj, 'pyn_collshape')


_spec_collshape = _register_handwired_group(
    'PynCollShapeProps', 'pyn_collshape',
    {'bhkMaterial': bpy.props.StringProperty(name='bhkMaterial', default=''),
     'bhkRadius': bpy.props.FloatProperty(name='bhkRadius', default=0.0)},
    label='Collision Shape',
    legacy={'bhkMaterial': 'bhkMaterial', 'bhkRadius': 'bhkRadius'})
PynCollShapeProps = _spec_collshape['grp']


def set_group(obj, attr, **fields):
    """Import helper: set a hand-wired group's fields and mark the object authoritative."""
    g = getattr(obj, attr)
    for k, v in fields.items():
        try:
            setattr(g, k, v)
        except (TypeError, ValueError):
            pass
    obj[_migkey(attr)] = True


def get_group(obj, attr):
    """Export helper: the hand-wired group, migrating any legacy flat props first."""
    ensure_handwired_migrated(obj, _handwired_spec(attr))
    return getattr(obj, attr)


# --- Extra-data blocks (Name/Value custom props on child EMPTYs) -------------
def _reg_extradata(clsname, attr, label, value_prop, legacy, extra=None):
    ann = {'name': bpy.props.StringProperty(name='name', default=''), 'value': value_prop}
    if extra:
        ann.update(extra)
    return _register_handwired_group(clsname, attr, ann, label, legacy=legacy)


_reg_extradata('PynBSXFlagsProps', 'pyn_bsxflags', 'BSXFlags',
               bpy.props.StringProperty(name='value', default=''),
               legacy={'name': 'BSXFlags_Name', 'value': 'BSXFlags_Value'})
_reg_extradata('PynIntDataProps', 'pyn_niintdata', 'NiIntegerExtraData',
               bpy.props.IntProperty(name='value', default=0),
               legacy={'name': 'NiIntegerExtraData_Name', 'value': 'NiIntegerExtraData_Value'})
_reg_extradata('PynStrDataProps', 'pyn_nistrdata', 'NiStringExtraData',
               bpy.props.StringProperty(name='value', default=''),
               legacy={'name': 'NiStringExtraData_Name', 'value': 'NiStringExtraData_Value'})
_reg_extradata('PynBehaviorProps', 'pyn_bsbehavior', 'BSBehaviorGraphExtraData',
               bpy.props.StringProperty(name='value', default=''),
               legacy={'name': 'BSBehaviorGraphExtraData_Name', 'value': 'BSBehaviorGraphExtraData_Value',
                       'cbs': 'BSBehaviorGraphExtraData_CBS'},
               extra={'cbs': bpy.props.BoolProperty(name='cbs', default=False)})
_reg_extradata('PynDecalProps', 'pyn_bsdecal', 'BSDecalPlacementVectorExtraData',
               bpy.props.StringProperty(name='value', default=''),
               legacy={'name': 'BSDecalPlacementVectorExtraData_Name',
                       'value': 'BSDecalPlacementVectorExtraData_Value'})
_register_handwired_group('PynBoneLODProps', 'pyn_bonelod',
    {'value': bpy.props.StringProperty(name='value', default='')}, 'BSBoneLOD',
    legacy={'value': 'pynBoneLOD'})
# rotation + zoom are informational (the camera transform is authoritative on export).
_register_handwired_group('PynInvMarkerProps', 'pyn_invmarker',
    {'name': bpy.props.StringProperty(name='name', default=''),
     'rotation': bpy.props.IntVectorProperty(name='rotation', size=3, default=(0, 0, 0)),
     'zoom': bpy.props.FloatProperty(name='zoom', default=1.0)}, 'BSInvMarker',
    legacy={'name': 'BSInvMarker_Name'})
_register_handwired_group('PynFurnitureProps', 'pyn_furniture',
    {'animation_type': bpy.props.StringProperty(name='animation_type', default=''),
     'entry_points': bpy.props.StringProperty(name='entry_points', default='')}, 'Furniture Marker',
    legacy={'animation_type': 'AnimationType', 'entry_points': 'EntryPoints'})

# --- Collision object wrapper (bhkCollisionObject) flags ---------------------
# pynRigidBody (body-type selector) stays a structural custom prop, like pynBlockName.
_register_handwired_group('PynCollisionObjProps', 'pyn_collisionobj',
    {'flags': bpy.props.StringProperty(name='flags', default='')}, 'Collision Object',
    legacy={'flags': 'pynCollisionFlags'})

# --- FO4 native physics (bhkPhysicsSystem) — parsed havok packfile ------------
# Mass/friction/damping/restitution live on Blender's native rigid_body. These are the
# extra body params. material_hex = raw body_props bytes (hex). pynRigidBody /
# pynCollisionShapeType stay structural selectors.
_register_handwired_group('PynFO4PhysicsProps', 'pyn_fo4phys',
    {'inertia': bpy.props.FloatVectorProperty(name='inertia', size=3, default=(0.0, 0.0, 0.0)),
     'material_hex': bpy.props.StringProperty(name='material_hex', default=''),
     'gravity_factor': bpy.props.FloatProperty(name='gravity_factor', default=1.0),
     'max_lin_vel': bpy.props.FloatProperty(name='max_lin_vel', default=104.4),
     'max_ang_vel': bpy.props.FloatProperty(name='max_ang_vel', default=31.57),
     'collision_radius': bpy.props.FloatProperty(name='collision_radius', default=0.0)},
    'FO4 Physics',
    legacy={'inertia': 'pynPhysInertia', 'material_hex': 'pynPhysMaterial',
            'gravity_factor': 'pynPhysGravityFactor', 'max_lin_vel': 'pynPhysMaxLinVel',
            'max_ang_vel': 'pynPhysMaxAngVel', 'collision_radius': 'pynCollisionRadius'})

# --- Connect points (BSConnectPointChildren) ---------------------------------
# child_names holds the variable-count connected-part names (legacy PYN_CONNECT_CHILD_{i}),
# newline-joined — no static legacy map for those; export falls back to the numbered keys
# for old .blend files. (pynEditorMarker is write-only dead data — left as a flat prop.)
_register_handwired_group('PynConnectPointProps', 'pyn_connectpoint',
    {'skinned': bpy.props.BoolProperty(name='skinned', default=False),
     'child_names': bpy.props.StringProperty(name='child_names', default='')}, 'Connect Point',
    legacy={'skinned': 'PYN_CONNECT_CHILD_SKINNED'})


def _object_panel_specs():
    """All Object-attached block/shape groups, buffer-derived + hand-wired, for the panel."""
    out = [{'attr': s['attr'], 'label': _BLOCK_LABEL.get(s['attr'], s['attr'])}
           for s in _block_specs]
    out += [{'attr': s['attr'], 'label': s['label']} for s in _handwired_specs]
    return out


class PYN_PT_block(bpy.types.Panel):
    """Shows the typed properties for whatever block type(s) this object was imported as."""
    bl_idname = "PYN_PT_block"
    bl_label = "PyNifly Block"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and any(obj.get(_migkey(s['attr'])) for s in _object_panel_specs())

    def draw(self, context):
        obj = context.object
        for spec in _object_panel_specs():
            if not obj.get(_migkey(spec['attr'])):
                continue
            grp = getattr(obj, spec['attr'])
            fns = group_fieldnames(grp)
            if not fns:
                continue
            box = self.layout.box()
            box.label(text=spec['label'])
            col = box.column(align=True)
            for fn in fns:
                col.prop(grp, fn)


# ---------------------------------------------------------------------------
# Export settings — consolidated, sticky per-nif export options.
# ---------------------------------------------------------------------------
# Replaces the scattered PYN_* custom props with two typed groups: nif-level settings on
# the nif's root object, skeleton settings on the armature (Bad Dog's root+armature split).
# Fields, types and defaults come from the ExportSettings dataclass — the single source of
# truth the operator already mirrors.

from ..util.settings import (
    ExportSettings, PYN_BLENDER_XF_PROP, PYN_PRESERVE_HIERARCHY_PROP,
    PYN_RENAME_BONES_NIFTOOLS_PROP, PYN_RENAME_BONES_PROP, PYN_ROTATE_BONES_PRETTY_PROP,
    PYN_WRITE_BODYTRI_ED_PROP, PYN_EXPORT_POSE_PROP, PYN_CHARGEN_EXT_PROP)

# `game` stays on its legacy PYN_GAME custom prop — it's inferred by multi-object discovery
# (_discover_game), not a pure sticky preference, so it's not part of this consolidation.
_EXPORT_ROOT_FIELDS = ['blender_xf', 'write_bodytri', 'export_modifiers',
                       'export_animations', 'export_colors', 'export_recenter_half_precision',
                       'export_full_precision', 'chargen_extension']
_EXPORT_SKEL_FIELDS = ['rename_bones', 'rename_bones_niftools', 'rotate_bones_pretty',
                       'export_pose', 'preserve_hierarchy']

# field -> legacy scattered custom prop, for one-time migration of old .blend files.
_EXPORT_LEGACY = {
    'blender_xf': PYN_BLENDER_XF_PROP,
    'write_bodytri': PYN_WRITE_BODYTRI_ED_PROP, 'chargen_extension': PYN_CHARGEN_EXT_PROP,
    'rename_bones': PYN_RENAME_BONES_PROP, 'rename_bones_niftools': PYN_RENAME_BONES_NIFTOOLS_PROP,
    'rotate_bones_pretty': PYN_ROTATE_BONES_PRETTY_PROP, 'export_pose': PYN_EXPORT_POSE_PROP,
    'preserve_hierarchy': PYN_PRESERVE_HIERARCHY_PROP,
}
_EXPORT_MIG_KEY = 'pyn_export_migrated'  # guard: legacy props already scanned for this object


def _export_prop_for(field):
    dflt = ExportSettings.__dataclass_fields__[field].default
    if isinstance(dflt, bool):
        return bpy.props.BoolProperty(name=field, default=dflt)
    return bpy.props.StringProperty(name=field, default=str(dflt))


def _make_export_group(clsname, fields):
    ann = {fn: _export_prop_for(fn) for fn in fields}
    return type(clsname, (bpy.types.PropertyGroup,), {'__annotations__': ann})


PynExportProps = _make_export_group('PynExportProps', _EXPORT_ROOT_FIELDS)
PynExportSkelProps = _make_export_group('PynExportSkelProps', _EXPORT_SKEL_FIELDS)

_EXPORT_ANCHORS = (  # (group attr, field list)
    ('pyn_export', _EXPORT_ROOT_FIELDS),
    ('pyn_export_skel', _EXPORT_SKEL_FIELDS),
)


def _migrate_export_anchor(datablock, attr, fields):
    """One-time copy of any legacy scattered PYN_* props onto the group. setattr marks each
    migrated field is_property_set (making it authoritative); untouched fields stay unset and
    keep deferring to the addon-preference defaults. The guard prevents rescanning."""
    if datablock is None or datablock.get(_EXPORT_MIG_KEY):
        return
    grp = getattr(datablock, attr)
    for fn in fields:
        legacy = _EXPORT_LEGACY.get(fn)
        if legacy and legacy in datablock:
            try:
                setattr(grp, fn, datablock[legacy])
            except (TypeError, ValueError):
                pass
    datablock[_EXPORT_MIG_KEY] = True


def read_export_settings(root_obj, armature_obj):
    """{field: value} for every setting the user has explicitly set (via a prior export or
    migrated from a legacy prop). Uses Blender's per-property `is_property_set`, so a field
    that's never been touched is omitted and the caller falls back to the addon-preference /
    dataclass default — preserving the old layered behaviour exactly."""
    out = {}
    for datablock, (attr, fields) in ((root_obj, _EXPORT_ANCHORS[0]),
                                      (armature_obj, _EXPORT_ANCHORS[1])):
        if datablock is None:
            continue
        _migrate_export_anchor(datablock, attr, fields)
        grp = getattr(datablock, attr)
        for fn in fields:
            if grp.is_property_set(fn):
                out[fn] = getattr(grp, fn)
    return out


def write_export_settings(root_obj, armature_obj, settings):
    """Store the export settings (an ExportSettings-like object or dict) onto the groups.
    setattr marks each field is_property_set, so it becomes sticky for the next export."""
    def val(k):
        return settings[k] if isinstance(settings, dict) else getattr(settings, k)
    for datablock, (attr, fields) in ((root_obj, _EXPORT_ANCHORS[0]),
                                      (armature_obj, _EXPORT_ANCHORS[1])):
        if datablock is None:
            continue
        grp = getattr(datablock, attr)
        for fn in fields:
            try:
                setattr(grp, fn, val(fn))
            except (TypeError, ValueError, KeyError, AttributeError):
                pass


class PYN_PT_export(bpy.types.Panel):
    """Sticky nif-level export settings, on the nif's root object."""
    bl_idname = "PYN_PT_export"
    bl_label = "PyNifly Export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and 'pynRoot' in context.object

    def draw(self, context):
        grp = context.object.pyn_export
        col = self.layout.column(align=True)
        for fn in _EXPORT_ROOT_FIELDS:
            col.prop(grp, fn)


class PYN_PT_export_skel(bpy.types.Panel):
    """Sticky skeleton export settings, on the armature."""
    bl_idname = "PYN_PT_export_skel"
    bl_label = "PyNifly Skeleton Export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'ARMATURE'

    def draw(self, context):
        grp = context.object.pyn_export_skel
        col = self.layout.column(align=True)
        for fn in _EXPORT_SKEL_FIELDS:
            col.prop(grp, fn)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (PynShaderProps, PYN_PT_shader, *_child_panels,
            *[s['grp'] for s in _block_specs],
            *[s['grp'] for s in _handwired_specs], PYN_PT_block,
            PynExportProps, PynExportSkelProps, PYN_PT_export, PYN_PT_export_skel)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.Material.pyn_shader = bpy.props.PointerProperty(type=PynShaderProps)
    for s in _block_specs:
        setattr(bpy.types.Object, s['attr'], bpy.props.PointerProperty(type=s['grp']))
    for s in _handwired_specs:
        setattr(bpy.types.Object, s['attr'], bpy.props.PointerProperty(type=s['grp']))
    bpy.types.Object.pyn_export = bpy.props.PointerProperty(type=PynExportProps)
    bpy.types.Object.pyn_export_skel = bpy.props.PointerProperty(type=PynExportSkelProps)


def unregister():
    if hasattr(bpy.types.Material, 'pyn_shader'):
        del bpy.types.Material.pyn_shader
    for attr in ('pyn_export', 'pyn_export_skel'):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)
    for s in _block_specs + _handwired_specs:
        if hasattr(bpy.types.Object, s['attr']):
            delattr(bpy.types.Object, s['attr'])
    for c in reversed(_classes):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
