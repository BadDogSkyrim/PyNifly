"""Reading a Starfield material in Blender back into .mat terms, for export."""

from pathlib import Path
import logging
import bpy
from .sf_shader_groups import (PYN_SF_BLEND, PYN_SF_COLOR, PYN_SF_IMPORT, PYN_SF_LAYER, PYN_SF_LOD_MATERIAL, PYN_SF_MIP_BIAS, PYN_SF_MODE, PYN_SF_NODE, PYN_SF_NODES, PYN_SF_OVERRIDE, PYN_SF_OVERRIDE_COLOR_TYPE, PYN_SF_PARAM_BOOL, PYN_SF_PARAM_FLOAT, PYN_SF_PATH, PYN_SF_REPLACE_SLOT, PYN_SF_SLOT, PYN_SF_TEX_REPLACE, PYN_SF_TEX_RESOLUTION, PYN_SF_TEX_SLOTS, SF_BLEND_GROUP, SF_LAYER_GROUP, SF_SHADER_MODEL_PROP, SF_SLOT_TO_LAYER_INPUT, _SF_COMPONENTS, _is_group, _recover_indexed, _recover_json, recover_sf_component, sf_component_node_of)
from .shader_nodes import (SEPARATOR_OUT1, SEPARATOR_OUT2, SEPARATOR_OUT3)

log = logging.getLogger("pynifly")

def _recover_sf_settings(material):
    """Read the settings dict back off the per-component settings group nodes (each present only
    if the material has that component) + the shader-model material property. Component keys map
    1:1 to settings-block keys (translucency/emissive/alpha/hair)."""
    s = {}
    sm = material.get(SF_SHADER_MODEL_PROP)
    if sm:
        s['shader_model'] = sm
    for key in _SF_COMPONENTS:
        node = sf_component_node_of(material, key)
        if node is not None:
            s[key] = recover_sf_component(node, key)
    bools = _recover_indexed(material, PYN_SF_PARAM_BOOL, bool)
    if bools:
        s['param_bools'] = bools
    lods = _recover_indexed(material, PYN_SF_LOD_MATERIAL, str)
    if lods:
        s['lod_materials'] = lods
    node = _recover_json(material, PYN_SF_NODE)
    if node:
        s['node'] = node
    return s


def _sf_game_texture_path(node):
    """The game-relative Textures\\...\\*.dds path for an SF image node, taken from its ASSIGNED
    image datablock -- the shader graph is the source of truth (as FO4/Skyrim export reads the
    node, not a stored property), so a swapped image is honored on export. Returns None when there
    is no image or it doesn't live under a 'textures' tree, letting the caller fall back to the
    imported pyn_sf_path stamp."""
    img = getattr(node, 'image', None)
    fp = getattr(img, 'filepath', '') if img else ''
    if not fp:
        return None
    parts = Path(bpy.path.abspath(fp)).parts
    lower = [p.lower() for p in parts]
    if 'textures' not in lower:
        return None
    return str(Path(*parts[lower.index('textures'):]).with_suffix('.dds'))


def _image_feeding(sock):
    """The image node plugged into an input socket, looking through reroutes; None if the input
    is fed by anything else or nothing."""
    while sock.is_linked:
        n = sock.links[0].from_node
        if n.type == 'REROUTE':
            sock = n.inputs[0]
            continue
        return n if n.type == 'TEX_IMAGE' else None
    return None


def _put_if(d, key, value):
    """Record a recovered family only when it has something in it, matching the parser: a layer
    with no such component produces a dict with no such key, so an untouched material recovers to
    exactly what was parsed."""
    if value:
        d[key] = value


def _nodes_reaching_output(nt):
    """The nodes that feed the active Material Output, walking links backwards from it.

    What isn't wired isn't in the material: a layer whose group node can't reach the output plays
    no part in what the user sees, so it plays no part in what we export. Returns None when the
    tree has no active output node at all -- then connectivity says nothing and every node counts.
    """
    out = next((n for n in nt.nodes
                if n.type == 'OUTPUT_MATERIAL' and getattr(n, 'is_active_output', False)), None)
    if out is None:
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        return None
    seen, stack = set(), [out]
    while stack:
        node = stack.pop()
        if node is None or node.name in seen:
            continue
        seen.add(node.name)
        for inp in node.inputs:
            for link in inp.links:
                stack.append(link.from_node)
    return seen




def _recover_sf_overrides(material, nodes):
    """Object ids the user has claimed for this material, whatever the parent says.

    Export decides what a material owns by diffing against its parents, which reads a value
    equal to the parent's as inherited. That is right almost always and unsayable exactly
    once: "I set this deliberately, and it must not follow the parent if the parent changes."
    The Override flag on a node says it, and it is the only thing about ownership that has to
    be stored -- everything else is computed at write time from the chain itself.
    """
    ids = []
    if material.get(PYN_SF_OVERRIDE):
        meta = _recover_json(material, PYN_SF_NODE) or {}
        ids.append(meta.get('id', ''))
    for n in nodes:
        if not n.get(PYN_SF_OVERRIDE):
            continue
        metas = _recover_json(n, PYN_SF_NODES)
        if metas is None:
            one = _recover_json(n, PYN_SF_NODE)
            metas = {'node': one} if one else {}
        for meta in metas.values():
            if isinstance(meta, dict) and meta.get('id'):
                ids.append(meta['id'])
            if isinstance(meta, dict) and isinstance(meta.get('uvstream'), dict):
                ids.append(meta['uvstream'].get('id', ''))
    return [i for i in ids if i is not None]


def recover_sf_material(material):
    """Walk a material's shader graph back into a normalised dict (as parse_mat returns), so it can
    be written out with sf_materials.write_mat. Sources: the SF Parameters node (settings), the SF
    Layer / SF Blend marker nodes (structure + UV/mode), and the image nodes' assigned textures
    (with the stamped pyn_sf_path as a fallback). Returns None if the material has no node tree.

    A layer or blender whose group node cannot reach the Material Output is NOT recovered: what
    isn't wired isn't part of the material, so it has no business in the .mat (see
    _nodes_reaching_output). The test is applied to the GROUP node, and everything stamped with
    that layer's or blender's index then follows it. Judging each satellite node on its own
    connectivity looks tidier but is wrong: a layer with no textures still carries a Mapping node
    that feeds nothing, and dropping it silently reset five vanilla materials' UV tiling to 1:1.
    The settings nodes are exempt for the same reason -- they are knobs read off a node, not part
    of the shading path."""
    nt = getattr(material, 'node_tree', None)
    if nt is None:
        return None
    wired = _nodes_reaching_output(nt)

    def is_wired(node):
        return wired is None or node.name in wired

    live_layers = {n[PYN_SF_LAYER] for n in nt.nodes
                   if _is_group(n, SF_LAYER_GROUP) and PYN_SF_LAYER in n and is_wired(n)}
    live_blends = {n[PYN_SF_BLEND] for n in nt.nodes
                   if _is_group(n, SF_BLEND_GROUP) and PYN_SF_BLEND in n and is_wired(n)}
    nodes = [n for n in nt.nodes
             if (n.get(PYN_SF_LAYER) in live_layers if PYN_SF_LAYER in n
                 else n.get(PYN_SF_BLEND) in live_blends if PYN_SF_BLEND in n
                 else True)]

    # A layer's textures are the images plugged into its inputs: the input names the slot, and the
    # assigned image names the file, with the import stamp as the fallback for an image that
    # doesn't live under a 'textures' tree. An image that isn't plugged in isn't exported, stamp
    # or no stamp.
    slot_of_input = {inp: slot for slot, (inp, _cs)
                     in SF_SLOT_TO_LAYER_INPUT.items()}
    images_by_layer = {}
    removed_by_layer = {}
    for marker in nodes:
        if not (_is_group(marker, SF_LAYER_GROUP) and PYN_SF_LAYER in marker):
            continue
        idx = marker[PYN_SF_LAYER]
        found = images_by_layer.setdefault(idx, {})
        for inp, slot in slot_of_input.items():
            sock = marker.inputs.get(inp)
            img = _image_feeding(sock) if sock is not None else None
            if img is None:
                continue
            path = _sf_game_texture_path(img) or img.get(PYN_SF_PATH)
            if path:
                found[slot] = path
            else:
                log.warning(f"{material.name}: the image plugged into layer {idx}'s {inp} "
                            f"isn't under a 'textures' folder, so it has no game path; "
                            f"not exported")
        # A slot that had a texture and now has nothing plugged in was removed, and the file its
        # texture set carried has to go too. "Had a texture" is import's record on the layer,
        # plus any stamped image of this layer still in the tree.
        had = set(marker.get(PYN_SF_TEX_SLOTS, ()))
        had |= {n[PYN_SF_SLOT] for n in nt.nodes
                if getattr(n, 'type', '') == 'TEX_IMAGE' and n.get(PYN_SF_LAYER) == idx
                and PYN_SF_SLOT in n}
        removed_by_layer[idx] = sorted(s for s in had if s in SF_SLOT_TO_LAYER_INPUT
                                       and s not in found)

    # UV tiling per layer, off the shared Mapping node stamped with the layer index (absent = 1:1).
    uv_by_layer = {n[PYN_SF_LAYER]: n for n in nodes
                   if getattr(n, 'type', '') == 'MAPPING' and PYN_SF_LAYER in n}

    layers = []
    layer_markers = {n[PYN_SF_LAYER]: n for n in nodes
                     if _is_group(n, SF_LAYER_GROUP) and PYN_SF_LAYER in n}
    # A slot filled by a flat colour instead of a texture: the RGB node's colour is the value, so
    # a user who recolours it is exporting what they see.
    replace_colors = {}
    for n in nodes:
        if getattr(n, 'type', '') == 'RGB' and PYN_SF_REPLACE_SLOT in n and PYN_SF_LAYER in n:
            replace_colors.setdefault(n[PYN_SF_LAYER], {})[int(n[PYN_SF_REPLACE_SLOT])] = \
                tuple(n.outputs['Color'].default_value)

    for idx in sorted(layer_markers):
        mp = uv_by_layer.get(idx)
        if mp is not None:
            sc = mp.inputs['Scale'].default_value
            of = mp.inputs['Location'].default_value
            uv_scale, uv_offset = (sc[0], sc[1]), (of[0], of[1])
        else:
            uv_scale, uv_offset = (1.0, 1.0), (0.0, 0.0)
        marker = layer_markers[idx]
        entry = {'textures': images_by_layer.get(idx, {}),
                 'uv_scale': uv_scale, 'uv_offset': uv_offset,
                 'override_color': marker.get(PYN_SF_OVERRIDE_COLOR_TYPE, '')}
        _put_if(entry, 'removed_textures', removed_by_layer.get(idx))
        _put_if(entry, 'param_bools', _recover_indexed(marker, PYN_SF_PARAM_BOOL, bool))
        _put_if(entry, 'mat_params', _recover_indexed(marker, PYN_SF_PARAM_FLOAT, float))
        if PYN_SF_COLOR in marker:
            entry['color'] = tuple(marker[PYN_SF_COLOR])
        if PYN_SF_MIP_BIAS in marker:
            entry['mip_bias'] = bool(marker[PYN_SF_MIP_BIAS])
        if PYN_SF_TEX_RESOLUTION in marker:
            entry['tex_resolution'] = str(marker[PYN_SF_TEX_RESOLUTION])
        # An 'enabled' flag on the layer node and a colour on an RGB node are two halves of one
        # TextureReplacement, so they are recombined per slot.
        replacements = {}
        for slot_idx, enabled in _recover_indexed(marker, PYN_SF_TEX_REPLACE, bool).items():
            replacements[slot_idx] = {'enabled': enabled}
        for slot_idx, color in replace_colors.get(idx, {}).items():
            replacements.setdefault(slot_idx, {})['color'] = color
        _put_if(entry, 'tex_replace', replacements)
        _put_if(entry, 'nodes', _recover_json(marker, PYN_SF_NODES))
        layers.append(entry)

    # Mask texture per blend index (may sit behind a channel separator, so found by its stamp, not
    # by walking the Mask link).
    mask_tex_by_blend = {n[PYN_SF_BLEND]: n for n in nodes
                         if getattr(n, 'type', '') == 'TEX_IMAGE'
                         and PYN_SF_BLEND in n and PYN_SF_PATH in n}
    blenders = []
    blend_markers = {n[PYN_SF_BLEND]: n for n in nodes
                     if _is_group(n, SF_BLEND_GROUP) and PYN_SF_BLEND in n}
    for idx in sorted(blend_markers):
        m = blend_markers[idx]
        mtex = mask_tex_by_blend.get(idx)
        mask = (_sf_game_texture_path(mtex) or mtex[PYN_SF_PATH]) if mtex else ''
        # The mask channel (ColorChannelTypeComponent) is the source socket feeding the blend Mask:
        # a separator's Red/Green/Blue or the mask texture's own Alpha. A direct texture 'Color' link
        # means no channel. The graph is the source of truth.
        channel = ''
        mask_in = m.inputs.get('Mask')   # the eye blend has none: it computes its own
        if mask_in is not None and mask_in.is_linked:
            sock = mask_in.links[0].from_socket.name
            channel = {SEPARATOR_OUT1: 'Red', SEPARATOR_OUT2: 'Green', SEPARATOR_OUT3: 'Blue',
                       'Alpha': 'Alpha'}.get(sock, '')
        entry = {'mode': m.get(PYN_SF_MODE, ''), 'mask': mask, 'channel': channel}
        _put_if(entry, 'node', _recover_json(m, PYN_SF_NODE))
        _put_if(entry, 'param_bools', _recover_indexed(m, PYN_SF_PARAM_BOOL, bool))
        _put_if(entry, 'mat_params', _recover_indexed(m, PYN_SF_PARAM_FLOAT, float))
        blenders.append(entry)

    textures = {}
    for ly in layers:
        for slot, path in ly['textures'].items():
            textures.setdefault(slot, path)

    return {'filename': material.get('BSLSP_Shader_Name', ''),
            'textures': textures, 'settings': _recover_sf_settings(material),
            'layers': layers, 'blenders': blenders,
            # What this material derives from, as it declared it. Export writes it back and
            # resolves against it; a material with none is written complete, which is legal
            # to parse and renders nothing, so it is the from-scratch author's problem.
            'imports': _recover_json(material, PYN_SF_IMPORT) or [],
            'overrides': _recover_sf_overrides(material, nodes)}
