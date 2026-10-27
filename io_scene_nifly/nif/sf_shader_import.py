"""Starfield material import: a .mat (and the materials it imports) becomes a Blender
material built from the SF node groups."""

import json
import os
import logging
import bpy
from .. import blender_defs as BD
from ..pyn.niflytools import find_referenced_file
from ..pyn.sf_materials import SF_TEXTURE_SLOTS
from ..pyn.pynifly import NiShape
from ..blender_defs import COLOR_MAP_NAME
from .shader_nodes import (MIXNODE_OUT, SEPARATOR_OUT1, SEPARATOR_OUT2, SEPARATOR_OUT3, make_mixnode, make_separator)
from .sf_shader_groups import (PYN_SF_BASE, PYN_SF_BLEND, PYN_SF_CHAIN, PYN_SF_COLOR, PYN_SF_IMPORT, PYN_SF_LAYER, PYN_SF_LOD_MATERIAL, PYN_SF_MIP_BIAS, PYN_SF_MODE, PYN_SF_NODE, PYN_SF_NODES, PYN_SF_ORIGIN, PYN_SF_OVERRIDE_COLOR_TYPE, PYN_SF_PARAM_BOOL, PYN_SF_PARAM_FLOAT, PYN_SF_PATH, PYN_SF_REPLACE_SLOT, PYN_SF_SLOT, PYN_SF_TEX_REPLACE, PYN_SF_TEX_RESOLUTION, PYN_SF_TEX_SLOTS, SF_BASE_Y, SF_BLEND_DX, SF_BLEND_WIDTH, SF_BLEND_Y, SF_BSDF_GAP, SF_COMP_BASE_Y, SF_COMP_DY, SF_LAYER_GAP, SF_LAYER_GROUP, SF_LAYER_NODE_H, SF_LAYER_NODE_W, SF_LAYER_TEX_DX, SF_LAYER_TOP_Y, SF_MASK_GAP, SF_SHADER_MODEL_PROP, SF_SLOT_TO_LAYER_INPUT, SF_SUBSURFACE_SCALE, SF_TEX_DY, SF_TEX_NODE_H, SF_X_BLEND0, SF_X_LAYER, _SF_BUNDLE_NAMES, _SF_COMPONENTS, _SF_LAYER_TEX_INPUTS, _ensure_sf_base_group, _group_base, _reconstruct_normal_rgb, _stamp_indexed, _stamp_json, add_sf_component_node, ensure_sf_blend_eye_group, ensure_sf_layer_group, sf_blend_group_for, sf_cdb_path, sf_material_search)

log = logging.getLogger("pynifly")

class SFShaderImporter:
    """Builds a Blender material from a Starfield .mat. ShaderImporter hands every
    Starfield shape here."""
    def __init__(self, sf_cache=None):
        """
        * sf_cache: a dict the importer keeps for the whole import, so shapes sharing a
          Starfield .mat share one material and the SF Base groups are filled once.
        """
        self._sf_cache = sf_cache if sf_cache is not None else {}
        self.material = None
        self.shape = None
        self.nodes = None
        self.game = None
        self._sf_chain = None      # the resolved Import chain of the material being read
        self._sf_origins = {}      # {object id: provenance entry} from that chain
        self.logger = logging.getLogger("pynifly")

    def warn(self, msg):
        self.logger.warning(msg)

    def _build_alt_pathlist(self):
        return BD.alt_texture_paths(self.game)


    def _sf_cdb_path(self):
        """The configured Starfield materialsbeta.cdb path (expanded), or None if unset/absent."""
        return sf_cdb_path()


    def _sf_material_search(self, matpath):
        """Materials-tree roots to resolve this material's Import chain against."""
        return sf_material_search(matpath, self._sf_altpaths)


    def _sf_read_material(self, matpath):
        """The EFFECTIVE material at `matpath` -- what it says plus what it inherits.

        A Starfield `.mat` is normally a derivation: 99.5% of vanilla materials name a
        parent with `Import` and restate only what they change, and only 0.3% name their own
        shader model. Reading the file alone therefore gets a fragment -- no shader model, no
        settings the template supplies, and components missing whichever fields the author
        did not repeat. The chain is resolved first so the node tree is built from the
        material the engine would actually assemble.
        """
        from ..pyn import sf_matchain, sf_materials
        try:
            chain = sf_matchain.resolve_material(
                matpath, search=self._sf_material_search(matpath),
                cdb=self._sf_cdb_path())
        except Exception as e:
            self.warn(f"Could not resolve the Import chain for '{matpath}': {e}")
            try:
                with open(matpath, 'r', encoding='utf-8-sig') as f:
                    return sf_materials.parse_mat(f.read())
            except OSError as e2:
                self.warn(f"Could not read material '{matpath}': {e2}")
                return None

        # A declared parent we could not find means real content is missing, and the result
        # would look complete anyway -- so say which one. An unresolved tail in
        # Materials\Layered\Root is normal: those ship only inside the .cdb.
        missing = [r for r in chain.unresolved
                   if not r.startswith('res:') and 'layered' not in r.lower()]
        if missing:
            self.warn(f"Material '{os.path.basename(matpath)}' inherits from "
                      f"{', '.join(missing)}, which could not be found; values it supplies "
                      f"are missing.")

        # Two different facts, both needed. The chain is where resolution WENT, for
        # diagnosis; the imports are what this file DECLARES, and export writes them back
        # verbatim rather than re-deriving them from where values ended up coming from.
        self.material[PYN_SF_CHAIN] = json.dumps(
            [os.path.basename(p) for p in chain.paths])
        self.material[PYN_SF_IMPORT] = json.dumps(chain.imports)
        self._sf_chain = chain
        self._sf_origins = chain.origin_map()
        return sf_materials.parse_mat_doc(chain.to_doc())


    def _sf_origin_of(self, meta):
        """Provenance for the one `.mat` object a carried node meta stands for, or None.

        The root is keyed by the empty id: it is `Objects[0]` whether or not it carries
        one, which is exactly what the meta records for it.
        """
        if not meta or not self._sf_origins:
            return None
        return self._sf_origins.get(meta.get('id', ''))

    def _sf_origins_for(self, metas):
        """The same, for a node that stands for several objects: `{kind: entry}`."""
        out = {}
        for kind, meta in (metas or {}).items():
            entry = self._sf_origin_of(meta) if isinstance(meta, dict) else None
            if entry:
                out[kind] = entry
        return out

    def _sf_component_origin(self, key):
        """Provenance for one root settings component, per field.

        Asked of the chain rather than read off the object's entry because the two answer
        different questions: the root's RECORD is always local, while the component on it
        may be wholly inherited -- which is the case for 99.7% of vanilla materials'
        shader model and most of what comes with it.
        """
        from ..pyn import sf_materials
        ctype = sf_materials.COMPONENT_TYPES.get(key)
        if not (ctype and self._sf_chain):
            return None
        return self._sf_chain.component_origin(self._sf_chain.root, ctype)


    def import_sf_material(self, obj, shape:NiShape):
        """Import a Starfield layered .mat as a native Principled-BSDF PBR material.

        SF carries no texture set in the NIF -- the shader's Name points at a loose .mat whose
        MRTextureFile nodes list one texture per PBR property (albedo/normal/rough/metal/ao/
        emissive). We resolve + parse the .mat, wire each map to the matching Principled input
        (SF normals are BC5 XY, so Z is reconstructed), and stash the raw slot paths as
        BSShaderTextureSet_<slot> for round-trip + the PyNifly Shader panel. Vanilla materials
        compiled into materialsbeta.cdb must be pre-extracted to a loose .mat (PyNifly never
        cracks archives).
        """
        from ..pyn import sf_materials

        self.shape = shape
        self.game = shape.file.game
        shape.shader.alternate_paths = self._build_alt_pathlist()

        # The mesh is the authority on whether a vertex-color multiply can be built. Colors are
        # imported before the shader, so asking the object here gives the right answer.
        has_colors = (getattr(obj.data, 'color_attributes', None) is not None
                      and COLOR_MAP_NAME in obj.data.color_attributes)

        # Shapes that use the same .mat share its material: nothing else from the nif goes on it.
        key = None
        if shape.shader.name:
            key = ('material', shape.shader.name.lower().replace('/', '\\'),
                   shape.shader.blockname, has_colors)
            done = self._sf_cache.get(key)
            if done is not None and done.name in bpy.data.materials:
                obj.active_material = done
                return

        self.material = bpy.data.materials.new(name=(obj.name + ".Mat"))
        self.material.use_nodes = True
        self.material['BS_Shader_Block_Name'] = shape.shader.blockname
        self.material['BSLSP_Shader_Name'] = shape.shader.name  # the .mat path, for export

        altpaths = self._build_alt_pathlist()
        self._sf_nifpath = shape.file.filepath
        self._sf_altpaths = altpaths
        self._sf_chain = None
        self._sf_origins = {}
        mat_ref = shape.shader.name  # 'Materials\...\x.mat'
        parsed = None
        if mat_ref:
            matpath = find_referenced_file(mat_ref, nifpath=shape.file.filepath,
                                           root='materials', alt_suffix=None, alt_pathlist=altpaths)
            if matpath:
                parsed = self._sf_read_material(matpath)
            else:
                # No loose .mat -> read straight from the material database if configured.
                cdb_path = self._sf_cdb_path()
                if cdb_path:
                    parsed = sf_materials.material_from_cdb(cdb_path, mat_ref)
                if parsed is None:
                    self.warn(f"Could not find material '{mat_ref}' (no loose .mat; set the "
                              f"Starfield .cdb path in PyNifly preferences to read materials "
                              f"straight from the database)")
        parsed = parsed or {}
        textures = parsed.get('textures', {})
        settings = parsed.get('settings', {})
        layers = parsed.get('layers', [])
        blenders = parsed.get('blenders', [])
        # A flat (non-layered) material still gets one implicit layer so it carries an SF Layer
        # marker + stamped images -> it recovers uniformly on export.
        if not layers and textures:
            layers = [{'textures': dict(textures), 'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0)}]

        # Stash raw slot paths for round-trip + the panel.
        for slot, path in textures.items():
            self.material['BSShaderTextureSet_' + slot] = path

        # Resolve the flat base PBR (base-layer-wins) + each layer's own textures + blend masks.
        resolved = self._resolve_sf_texset(textures)
        layers_resolved = self._resolve_sf_layers(layers)
        blenders_resolved = self._resolve_sf_blenders(blenders)

        self._build_sf_nodes(resolved, settings, layers_resolved, blenders_resolved,
                             has_vertex_colors=has_colors)
        self._build_sf_base_chain(self._sf_chain)
        obj.active_material = self.material
        if key is not None:
            self._sf_cache[key] = self.material

    def _resolve_sf_texset(self, texdict):
        """Resolve a {slot: .mat-path} set to {slot: (resolved_filepath, verbatim_mat_path)} so image
        nodes can be stamped with the .mat path for export recovery. Unresolvable slots are dropped."""
        out = {}
        for slot, path in texdict.items():
            p = self._sf_resolve(path)
            if p:
                out[slot] = (p, path)
        return out

    def _resolve_sf_layers(self, layers):
        """Resolve each parsed layer's textures, carrying every non-texture field (uv tiling, the
        vertex-color albedo override, the shader knobs, texture replacements) through to the node
        build unchanged. Copying the layer and replacing only `textures` means a family added to
        the parser reaches the node build without a change here."""
        out = []
        for ly in layers:
            entry = dict(ly)
            entry['textures'] = self._resolve_sf_texset(ly.get('textures', {}))
            entry.setdefault('uv_scale', (1.0, 1.0))
            entry.setdefault('uv_offset', (0.0, 0.0))
            entry.setdefault('override_color', '')
            out.append(entry)
        return out

    def _resolve_sf_blenders(self, blenders):
        """Resolve each parsed blender's texture mask, carrying its mode, vertex-color mask channel
        and shader knobs through to the node build unchanged."""
        out = []
        for b in blenders:
            mp = b.get('mask')
            fp = self._sf_resolve(mp)
            entry = dict(b)
            entry['mode'] = b.get('mode', '')
            entry['mask'] = (fp, mp) if fp else None
            entry['channel'] = b.get('channel', '')
            out.append(entry)
        return out

    def _sf_resolve(self, path):
        """Resolve a .mat texture path to a loose file (prefer .png). None (with a warning) if
        not found. Empty path -> None silently."""
        if not path:
            return None
        p = find_referenced_file(path, nifpath=self._sf_nifpath, alt_suffix='.png',
                                 alt_pathlist=self._sf_altpaths)
        if not p:
            self.warn(f"Could not find SF texture: '{path}'")
        return p

    def _sf_load_image(self, path, colorspace):
        img = bpy.data.images.load(path, check_existing=True)
        try:
            img.colorspace_settings.name = colorspace
        except Exception:
            pass
        return img

    @staticmethod
    def _sf_split(entry):
        """A resolved texture entry is (filepath, mat_path) from import, or a bare filepath from
        direct/test callers -> (filepath, mat_path|None)."""
        if isinstance(entry, (tuple, list)):
            return entry[0], (entry[1] if len(entry) > 1 else None)
        return entry, None

    def _sf_stamp(self, node, path=None, slot=None, layer=None):
        """Stamp export-recovery custom props on a node (image path/slot/layer)."""
        if path is not None:
            node[PYN_SF_PATH] = path
        if slot is not None:
            node[PYN_SF_SLOT] = slot
        if layer is not None:
            node[PYN_SF_LAYER] = layer

    def _sf_teximg(self, slot, resolved, colorspace, location, layer=0):
        """Image node for a base-layer slot. `resolved[slot]` is (filepath, mat_path); the .mat
        path + slot + layer are stamped for export recovery."""
        filepath, matpath = self._sf_split(resolved[slot])
        n = self.nodes.new('ShaderNodeTexImage')
        n.image = self._sf_load_image(filepath, colorspace)
        n.location = location
        n.label = slot
        self._sf_stamp(n, path=matpath, slot=slot, layer=layer)
        return n

    def _sf_normal_rgb(self, image_node, x, y):
        """SF normals are BC5, storing X/Y only. Reconstruct Z = sqrt(1 - x^2 - y^2) and recombine
        into a full [0,1] tangent-space normal color. Returns the CombineColor output (RGB) -- feed
        a Normal Map node for a single layer, or the SF Normal Blend group for a detail blend.

        Shares `_reconstruct_normal_rgb` with the SF Layer group: this was a second copy of the
        same math, so the DirectX green flip had to be got right in two places at once."""
        return _reconstruct_normal_rgb(self.material.node_tree,
                                       image_node.outputs['Color'], (x, y))

    def _sf_normalmap(self, rgb_socket, x, y):
        """Wrap a reconstructed normal RGB in a Normal Map node -> a Normal vector."""
        nmap = self.nodes.new('ShaderNodeNormalMap')
        nmap.location = (x, y)
        self.material.node_tree.links.new(rgb_socket, nmap.inputs['Color'])
        return nmap.outputs['Normal']

    def _sf_reconstruct_normal(self, image_node, x, y):
        """Single-layer BC5 normal -> a Normal Map node's Normal output."""
        return self._sf_normalmap(self._sf_normal_rgb(image_node, x, y), x + 1800, y)

    def _sf_teximg_path(self, filepath, colorspace, location, uv_scale=None, uv_offset=None,
                        matpath=None, slot=None, layer=None):
        """A texture image node for a resolved filepath, optionally fed by a Mapping node for a
        layer's UV tiling/offset (a UV scale of (1,1)/offset (0,0) needs no Mapping). Stamped with
        the .mat path/slot/layer for export recovery."""
        n = self.nodes.new('ShaderNodeTexImage')
        n.image = self._sf_load_image(filepath, colorspace)
        n.location = location
        if slot:
            n.label = slot
        self._sf_stamp(n, path=matpath, slot=slot, layer=layer)
        if uv_scale and (tuple(uv_scale) != (1.0, 1.0) or (uv_offset and tuple(uv_offset) != (0.0, 0.0))):
            nt = self.material.node_tree
            tc = self.nodes.new('ShaderNodeTexCoord'); tc.location = (location[0] - 500, location[1])
            mp = self.nodes.new('ShaderNodeMapping'); mp.location = (location[0] - 300, location[1])
            mp.inputs['Scale'].default_value = (uv_scale[0], uv_scale[1], 1.0)
            if uv_offset:
                mp.inputs['Location'].default_value = (uv_offset[0], uv_offset[1], 0.0)
            nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
            nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n

    def _build_sf_layer(self, nt, index, layer, x, y):
        """One layer's texture image nodes -> an SF Layer group -> the PBR bundle. Returns the
        SF Layer group node (its outputs are the bundle)."""
        node = nt.nodes.new('ShaderNodeGroup')
        node.node_tree = ensure_sf_layer_group()
        node.location = (x, y)
        node.width = 300   # roomy -- lots of channels
        node.label = f"{SF_LAYER_GROUP} {index}"
        node[PYN_SF_LAYER] = index
        _stamp_json(node, PYN_SF_NODES, layer.get('nodes'))
        _stamp_json(node, PYN_SF_ORIGIN, self._sf_origins_for(layer.get('nodes')))
        # What this layer's Material and TextureSet carry besides their textures.
        _stamp_indexed(node, PYN_SF_PARAM_BOOL, layer.get('param_bools'))
        _stamp_indexed(node, PYN_SF_PARAM_FLOAT, layer.get('mat_params'))
        if layer.get('color') is not None:
            node[PYN_SF_COLOR] = list(layer['color'])
        if layer.get('mip_bias') is not None:
            node[PYN_SF_MIP_BIAS] = layer['mip_bias']
        if layer.get('tex_resolution') is not None:
            node[PYN_SF_TEX_RESOLUTION] = layer['tex_resolution']

        # One shared UV Mapping per layer (only when non-identity), stamped with the layer index
        # so export recovers the tiling off it. Feeds all this layer's image nodes.
        us = layer.get('uv_scale', (1.0, 1.0))
        uo = layer.get('uv_offset', (0.0, 0.0))
        uv_out = None
        if tuple(us) != (1.0, 1.0) or tuple(uo) != (0.0, 0.0):
            tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (x - 1250, y)
            mapping = nt.nodes.new('ShaderNodeMapping'); mapping.location = (x - 1050, y)
            mapping[PYN_SF_LAYER] = index
            mapping.inputs['Scale'].default_value = (us[0], us[1], 1.0)
            mapping.inputs['Location'].default_value = (uo[0], uo[1], 0.0)
            nt.links.new(tc.outputs['UV'], mapping.inputs['Vector'])
            uv_out = mapping.outputs['Vector']

        # Everything feeding this layer's inputs, stacked in group-input-socket order -- which is
        # .mat slot order -- closely spaced, topmost aligned to the layer node's top (never above
        # it). Textures and flat-colour replacements share one column, so a layer's inputs read
        # down the same way its TextureSet lists them.
        input_order = [n for _s, n, _b, _d in _SF_LAYER_TEX_INPUTS]

        def socket_order(inp):
            return input_order.index(inp) if inp in input_order else len(input_order)

        present = []
        for slot, entry in layer.get('textures', {}).items():
            m = SF_SLOT_TO_LAYER_INPUT.get(slot)
            if m:
                present.append((socket_order(m[0]), 'tex', slot, m[0], m[1], entry))

        # A TextureReplacement stands IN FOR a texture: across the vanilla human materials, no slot
        # ever carries both (0 of 11). So a replacement with a colour becomes an RGB node feeding
        # that slot's group input -- the flat colour the game would use, visible and editable.
        # A replacement with no colour of its own inherits one from the parent template, which we
        # can't resolve, so it stays a flag rather than a node with an invented colour.
        for slot_idx, rep in sorted((layer.get('tex_replace') or {}).items()):
            slot = SF_TEXTURE_SLOTS.get(slot_idx)
            m = SF_SLOT_TO_LAYER_INPUT.get(slot) if slot else None
            if 'enabled' in rep:
                node[PYN_SF_TEX_REPLACE + str(slot_idx)] = rep['enabled']
            if 'color' in rep and m:
                present.append((socket_order(m[0]), 'rgb', slot, m[0], slot_idx, rep['color']))

        present.sort(key=lambda t: t[0])
        # Which slots got an image node: one of these with nothing plugged in at export was
        # removed in Blender, even if its node was deleted outright.
        tex_slots = [t[2] for t in present if t[1] == 'tex']
        if tex_slots:
            node[PYN_SF_TEX_SLOTS] = tex_slots
        for k, (_order, kind, slot, inp, aux, value) in enumerate(present):
            loc = (x - SF_LAYER_TEX_DX, y - k * SF_TEX_DY)
            if kind == 'tex':
                fp, mp = self._sf_split(value)
                img = self._sf_teximg_path(fp, aux, loc, matpath=mp, slot=slot, layer=index)
                if uv_out is not None:
                    nt.links.new(uv_out, img.inputs['Vector'])
                nt.links.new(img.outputs['Color'], node.inputs[inp])
            else:
                rgb = nt.nodes.new('ShaderNodeRGB')
                rgb.location = loc
                rgb.label = f"{slot} (replaced)"
                rgb[PYN_SF_REPLACE_SLOT] = aux
                rgb[PYN_SF_LAYER] = index
                rgb.outputs['Color'].default_value = tuple(value)
                nt.links.new(rgb.outputs['Color'], node.inputs[inp])

        # MaterialOverrideColor 'Multiply': this layer's albedo is multiplied by the mesh vertex
        # color. Insert the multiply on the layer's Base Color output and register it so downstream
        # bundle reads (blends / the final BSDF wiring) pick up the overridden socket.
        # Recorded whether or not it can be rendered: it is part of the material and has to
        # survive export regardless of what this particular mesh carries.
        if layer.get('override_color'):
            node[PYN_SF_OVERRIDE_COLOR_TYPE] = layer['override_color']
        # Only build the multiply when there is actually a vertex color to multiply BY. Blender's
        # Attribute node evaluates to zero for an attribute the mesh doesn't have, so wiring this
        # up on a mesh without vertex colors renders the whole surface black -- vanilla naked_m
        # imported that way. The game takes an absent vertex color as white, so leaving the albedo
        # alone is the faithful result.
        if layer.get('override_color') == 'Multiply' and getattr(self, '_sf_has_vertex_colors', True):
            vcol = self._sf_vertex_color_node(nt)
            mix = make_mixnode(nt, node.outputs['Base Color'], vcol.outputs['Color'],
                               factor=1.0, blend_type='MULTIPLY',
                               location=(x + SF_LAYER_NODE_W + 2 * SF_MASK_GAP, y))
            mix.label = 'Vertex Color x Albedo'
            self._sf_base_override[node] = mix.outputs[MIXNODE_OUT]

        # This layer's lowest edge = the lower of the last texture node's bottom and the layer
        # node's bottom -- used to place the next layer just below it.
        last_tex_bottom = (y - (len(present) - 1) * SF_TEX_DY - SF_TEX_NODE_H) if present else y
        bottom = min(last_tex_bottom, y - SF_LAYER_NODE_H)
        return node, bottom

    def _sf_vertex_color_node(self, nt):
        """The mesh's vertex-color Attribute node (VERTEX_COLOR), created once per material and
        cached. SF meshes always carry vertex colors; a layer's MaterialOverrideColor 'Multiply'
        reads the full color from here to multiply into that layer's albedo."""
        if getattr(self, '_sf_vcol', None) is None:
            attr = nt.nodes.new('ShaderNodeAttribute')
            attr.attribute_type = 'GEOMETRY'
            attr.attribute_name = COLOR_MAP_NAME
            attr.label = 'Vertex Color'
            # Align with the per-layer texture-coordinate nodes (also at x - 1250).
            attr.location = (SF_X_LAYER - 1250, SF_COMP_BASE_Y)
            self._sf_vcol = attr
        return self._sf_vcol

    def _sf_bundle_out(self, node, chan):
        """A bundle channel's output socket, honoring a per-layer Base Color override (a layer whose
        material multiplies albedo by vertex color). Non-overridden channels read straight off the
        group node -- so blends and the final BSDF wiring go through this uniformly."""
        if chan == 'Base Color':
            override = getattr(self, '_sf_base_override', {}).get(node)
            if override is not None:
                return override
        return node.outputs[chan]

    def _build_sf_blend(self, nt, index, blender, bundle_a, bundle_b, x, y, iris_radius=None):
        """Composite two bundles via an SF Blend group (chosen by mode). Returns the group node.

        `iris_radius` (a socket) makes this the iris/sclera blend of an eye, which computes its
        own mask from it (ensure_sf_blend_eye_group). Only the material's own graph passes it;
        the inherited-template views stay as the files describe them."""
        node = nt.nodes.new('ShaderNodeGroup')
        node.node_tree = (ensure_sf_blend_eye_group() if iris_radius is not None
                          else sf_blend_group_for(blender.get('mode', '')))
        node.location = (x, y)
        node.width = SF_BLEND_WIDTH   # blends are wide (many bundle sockets) -- give them room
        node.label = _group_base(node.node_tree.name)   # the version is noise in the graph
        node[PYN_SF_BLEND] = index
        node[PYN_SF_MODE] = blender.get('mode', '')
        _stamp_json(node, PYN_SF_NODE, blender.get('node'))
        # A blender's UV stream hangs off its own meta, so provenance for the pair is
        # keyed the way a layer's is.
        _stamp_json(node, PYN_SF_ORIGIN, self._sf_origins_for(
            {'node': blender.get('node'),
             'uvstream': (blender.get('node') or {}).get('uvstream')}))
        _stamp_indexed(node, PYN_SF_PARAM_BOOL, blender.get('param_bools'))
        _stamp_indexed(node, PYN_SF_PARAM_FLOAT, blender.get('mat_params'))
        for chan in _SF_BUNDLE_NAMES:
            nt.links.new(self._sf_bundle_out(bundle_a, chan), node.inputs['A ' + chan])
            nt.links.new(self._sf_bundle_out(bundle_b, chan), node.inputs['B ' + chan])
        # Blend mask: the mask TEXTURE drives the blend. ColorChannelTypeComponent (when present)
        # selects which channel of the mask to use -- face-detail masks are channel-packed (chin in
        # green, lips in blue), so several blenders share the pattern of one mask + a channel. No
        # channel means use the texture directly (as before).
        channel = blender.get('channel')
        mask = blender.get('mask')
        if mask:
            mfile, mpath = self._sf_split(mask)
            # Mask sits just to the right of the layer node this blend composites in (bundle_b),
            # level with that node's vertical midpoint.
            mx = bundle_b.location[0] + SF_LAYER_NODE_W + SF_MASK_GAP
            my = bundle_b.location[1] - SF_LAYER_NODE_H // 2
            mnode = self._sf_teximg_path(mfile, 'Non-Color', (mx, my),
                                         matpath=mpath, slot='Mask')
            mnode[PYN_SF_BLEND] = index
            if channel == 'Alpha':
                nt.links.new(mnode.outputs['Alpha'], node.inputs['Mask'])
            elif channel:
                sep = make_separator(nt, mnode.outputs['Color'], (mx + SF_LAYER_TEX_DX, my))
                out = {'Red': SEPARATOR_OUT1, 'Green': SEPARATOR_OUT2,
                       'Blue': SEPARATOR_OUT3}.get(channel)
                nt.links.new(sep.outputs[out] if out else mnode.outputs['Color'],
                             node.inputs['Mask'])
            else:
                nt.links.new(mnode.outputs['Color'], node.inputs['Mask'])
        elif iris_radius is not None:
            nt.links.new(iris_radius, node.inputs['Iris Radius'])
        return node

    def _add_sf_component_nodes(self, nt, settings, anchor_x):
        """Add one per-component settings group node for each component the material has (skipping
        the flat 'shader_model'/'filename' keys), stash the shader-model identity on the material,
        and return {component_key: node}. The nodes stack upward above the last blend node
        (anchor_x) and share the blend width."""
        settings = settings or {}
        if settings.get('shader_model'):
            self.material[SF_SHADER_MODEL_PROP] = settings['shader_model']
        # The root's own indexed families live on the material, since the root LayeredMaterial is
        # what the Blender material stands for. An LOD reference names a separate material in the
        # game's database, so it is carried as an opaque id.
        _stamp_indexed(self.material, PYN_SF_PARAM_BOOL, settings.get('param_bools'))
        _stamp_indexed(self.material, PYN_SF_LOD_MATERIAL, settings.get('lod_materials'))
        _stamp_json(self.material, PYN_SF_NODE, settings.get('node'))
        _stamp_json(self.material, PYN_SF_ORIGIN, self._sf_origin_of(settings.get('node')))
        comp_nodes = {}
        y = SF_COMP_BASE_Y
        for key in _SF_COMPONENTS:
            block = settings.get(key)
            if block is not None:
                node = add_sf_component_node(nt, key, block, (anchor_x, y))
                node.width = SF_BLEND_WIDTH
                _stamp_json(node, PYN_SF_ORIGIN, self._sf_component_origin(key))
                comp_nodes[key] = node
                y += SF_COMP_DY
        return comp_nodes

    def _bundle_to_principled(self, nt, bsdf, bundle, comp_nodes, settings):
        """Wire a final bundle (an SF Layer/Blend group node) into the Principled BSDF, plus each
        present settings-component node driving its bit (SSS / emission / alpha test / hair sheen)."""
        o = bundle.outputs
        bx = bsdf.location[0]
        # Base Color honors a per-layer vertex-color override when `bundle` is a lone overridden
        # layer (single-layer material); composited bundles carry the override inside the blend.
        base_color = self._sf_bundle_out(bundle, 'Base Color')
        make_mixnode(nt, base_color, o['AO'], output=bsdf.inputs['Base Color'],
                     factor=1.0, blend_type='MULTIPLY', location=(bx - 300, 300))
        nt.links.new(o['Roughness'], bsdf.inputs['Roughness'])
        nt.links.new(o['Metallic'], bsdf.inputs['Metallic'])
        nt.links.new(self._sf_normalmap(o['Normal'], bx - 300, -400), bsdf.inputs['Normal'])
        if 'Subsurface Scale' in bsdf.inputs:
            bsdf.inputs['Subsurface Scale'].default_value = SF_SUBSURFACE_SCALE

        tr = comp_nodes.get('translucency')
        if tr is not None and 'Subsurface Weight' in bsdf.inputs:
            nt.links.new(tr.outputs['SSS Weight'], bsdf.inputs['Subsurface Weight'])

        em = comp_nodes.get('emissive')
        if em is not None:
            nt.links.new(o['Emissive'], em.inputs['Emissive'])
            ecol = bsdf.inputs.get('Emission Color') or bsdf.inputs.get('Emission')
            if ecol is not None:
                nt.links.new(em.outputs['Emissive Color'], ecol)
            if 'Emission Strength' in bsdf.inputs:
                nt.links.new(em.outputs['Emissive Strength'], bsdf.inputs['Emission Strength'])

        al = comp_nodes.get('alpha')
        if al is not None and 'Alpha' in bsdf.inputs:
            nt.links.new(o['Opacity'], al.inputs['Opacity'])
            nt.links.new(al.outputs['Alpha Out'], bsdf.inputs['Alpha'])

        # Hair -> Principled Sheen (fuzzy rim). First pass; calibrate by eye.
        hr = comp_nodes.get('hair')
        if hr is not None:
            if 'Sheen Weight' in bsdf.inputs:
                nt.links.new(hr.outputs['Sheen Weight'], bsdf.inputs['Sheen Weight'])
            if 'Sheen Roughness' in bsdf.inputs:
                nt.links.new(hr.outputs['Sheen Roughness'], bsdf.inputs['Sheen Roughness'])

    def _build_sf_base_chain(self, chain):
        """Nested `SF Base` group nodes for everything this material inherits from.

        Provenance stamps answer "where did this value come from" one node at a time, which
        you have to think to ask. This answers "what is under me" by being visible in the
        graph: one group per level of the chain, each containing the next, each holding the
        layers, blends and settings that level actually supplies.

        Returns the outermost group node, or None when nothing is inherited.
        """
        if chain is None or len(chain.paths) < 2:
            return None
        from ..pyn import sf_matchain, sf_materials

        saved_nodes = self.nodes
        inner = None
        try:
            # Innermost (the root template) first, so each level can hold the one below it.
            built = self._sf_cache.setdefault('sf_base_built', set())
            for path in reversed(chain.paths[1:]):
                label = sf_matchain.material_label(path)
                group = _ensure_sf_base_group(label)
                if label in built:
                    # Filled already in this import: a level's content and what it holds
                    # below it don't depend on which material inherits from it.
                    inner = group
                    continue
                built.add(label)
                self.nodes = group.nodes
                try:
                    level = sf_matchain.resolve_level(
                        path, search=self._sf_material_search(chain.paths[0]),
                        cdb=self._sf_cdb_path())
                    parsed = (sf_materials.parse_mat_doc(level.to_doc()) if level
                              else {'layers': [], 'blenders': [], 'settings': {}})
                except Exception as e:
                    self.warn(f"Could not read the inherited material '{label}': {e}")
                    parsed = {'layers': [], 'blenders': [], 'settings': {}}
                self._fill_sf_base_group(group, parsed, inner)
                inner = group
        finally:
            self.nodes = saved_nodes

        node = self.material.node_tree.nodes.new('ShaderNodeGroup')
        node.node_tree = inner
        node.location = (SF_X_LAYER, SF_BASE_Y)
        node.width = SF_BLEND_WIDTH
        node.label = _group_base(inner.name)
        node[PYN_SF_BASE] = sf_matchain.material_label(chain.paths[1])
        return node

    def _fill_sf_base_group(self, group, parsed, inner):
        """One level of the chain drawn inside its own group: what THIS material supplies."""
        group.nodes.clear()
        nt = group
        if inner is not None:
            child = nt.nodes.new('ShaderNodeGroup')
            child.node_tree = inner
            child.location = (SF_X_LAYER, SF_BASE_Y)
            child.width = SF_BLEND_WIDTH
            child.label = _group_base(inner.name)

        settings = parsed.get('settings') or {}
        n_blend = min(len(parsed.get('blenders') or []),
                      max(0, len(parsed.get('layers') or []) - 1))
        y = SF_COMP_BASE_Y
        for key in _SF_COMPONENTS:
            block = settings.get(key)
            if block is not None:
                comp = add_sf_component_node(
                    nt, key, block,
                    (SF_X_BLEND0 + max(0, n_blend - 1) * SF_BLEND_DX, y))
                comp.width = SF_BLEND_WIDTH
                y += SF_COMP_DY

        layer_nodes = []
        next_top = SF_LAYER_TOP_Y
        for i, ly in enumerate(self._resolve_sf_layers(parsed.get('layers') or [])):
            node, bottom = self._build_sf_layer(nt, i, ly, SF_X_LAYER, next_top)
            layer_nodes.append(node)
            next_top = bottom - SF_LAYER_GAP

        prev, bx = (layer_nodes[0] if layer_nodes else None), SF_X_BLEND0
        for i, b in enumerate(self._resolve_sf_blenders(parsed.get('blenders') or [])):
            if prev is None or i + 1 >= len(layer_nodes):
                break
            prev = self._build_sf_blend(nt, i, b, prev, layer_nodes[i + 1], bx, SF_BLEND_Y)
            bx += SF_BLEND_DX

    def _build_sf_nodes(self, resolved, settings=None, layers_resolved=None,
                        blenders_resolved=None, has_vertex_colors=True):
        """Wire the resolved SF PBR textures into a Principled BSDF, plus the SF Parameters node
        (SSS / emissive / alpha settings + shader-model identity), driving Subsurface + Emission.

        `resolved` is the flat base-layer-wins PBR (P0). `layers_resolved`/`blenders_resolved`
        carry the full layer graph (P1): a second layer's detail normal is composited over the
        base normal via the SF Normal Blend group (RNM), masked by its blender.

        `has_vertex_colors` says whether the mesh actually carries the color attribute, which
        decides whether a layer's vertex-color albedo multiply can be built at all."""
        nt = self.material.node_tree
        self.nodes = nt.nodes
        self._sf_has_vertex_colors = has_vertex_colors
        # Per-material vertex-color state: the shared Attribute/separator node (lazily created) and
        # the map of layer node -> overridden Base Color socket (MaterialOverrideColor 'Multiply').
        self._sf_vcol = None
        self._sf_base_override = {}
        bsdf = next((n for n in self.nodes if n.type == 'BSDF_PRINCIPLED'), None) \
            or self.nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in self.nodes if n.type == 'OUTPUT_MATERIAL'), None) \
            or self.nodes.new('ShaderNodeOutputMaterial')
        # A flat material (no layer graph) is one implicit layer, so the same Layer->Blend->
        # Principled path handles both.
        layers_resolved = list(layers_resolved or [])
        if not layers_resolved and resolved:
            layers_resolved = [{'textures': dict(resolved),
                                'uv_scale': (1.0, 1.0), 'uv_offset': (0.0, 0.0)}]

        # Per-component settings group nodes -- created first so the bundle wiring can read them.
        # They sit above the last blend node (its X is deterministic from the layer/blender counts).
        n_blend = min(len(blenders_resolved or []), max(0, len(layers_resolved) - 1))
        last_blend_x = SF_X_BLEND0 + max(0, n_blend - 1) * SF_BLEND_DX
        comp_nodes = self._add_sf_component_nodes(nt, settings, last_blend_x)

        # Layers: one SF Layer group per layer, stacked in a single column (shared X). Layer 0's top
        # texture is on the blend row; each next layer drops just below the prior layer's lowest edge
        # (content-driven, so tall texture stacks don't overlap).
        layer_nodes = []
        next_top = SF_LAYER_TOP_Y
        for i, ly in enumerate(layers_resolved):
            node, bottom = self._build_sf_layer(nt, i, ly, SF_X_LAYER, next_top)
            layer_nodes.append(node)
            next_top = bottom - SF_LAYER_GAP

        # Blends: a left-to-right chain (blend of layers 0/1 leftmost) on one row at the BSDF's Y.
        final = None
        last_x = SF_X_LAYER
        if layer_nodes:
            final = layer_nodes[0]
            bx = SF_X_BLEND0
            # An eye's first blender joins iris and sclera and says nothing about how; the
            # shader cuts by UV radius, so that is what the preview does -- unless the
            # material gives the blender a mode or mask of its own, which then wins.
            eye = comp_nodes.get('eye')
            is_eye = (eye is not None and (settings or {}).get('shader_model') == 'Eye1Layer')
            for i, b in enumerate(blenders_resolved or []):
                if i + 1 >= len(layer_nodes):
                    break
                iris = (eye.outputs['Iris Radius']
                        if is_eye and i == 0 and not b.get('mode') and not b.get('mask')
                        else None)
                final = self._build_sf_blend(nt, i, b, final, layer_nodes[i + 1], bx, SF_BLEND_Y,
                                             iris_radius=iris)
                last_x = bx
                bx += SF_BLEND_DX

        # BSDF sits an extra gap right of the last blend (or the lone layer); output just beyond.
        bsdf.location = (last_x + SF_BSDF_GAP, 0)
        out.location = (bsdf.location[0] + 400, 0)
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        if final is not None:
            self._bundle_to_principled(nt, bsdf, final, comp_nodes, settings)
