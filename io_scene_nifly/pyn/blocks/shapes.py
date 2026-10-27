"""Shape blocks -- NiShape and every geometry type, Starfield's BSGeometry included -- and
the unit-scale helpers that read their size."""

from __future__ import annotations

import os
from enum import Enum
import re
import logging
from ctypes import *
from typing import ValuesView, List
from collections.abc import MutableMapping
import xml.etree.ElementTree as xml
from pathlib import Path
from ..niflytools import *
from ..nifdefs import *
from ..niflydll import nifly, nifly_path
from ..nifconstants import BSXFlagsValues, HAVOC_SCALE_FACTOR, game_traits
from .nodes import NiNode


log = logging.getLogger("pynifly")


# Every FO4/Skyrim nif shape stores vertex indices (and numVertices) as 16-bit,
# so a single shape can address at most 65535 vertices. NiTriShapeData/NiTriStripsData
# also store their triangle count as 16-bit (another 65535 cap); the BS*TriShape
# family (FO4, and BSTriShape/BSSubIndexTriShape/BSDynamicTriShape on SSE) uses
# 32-bit triangle counts — and the FO4 segmentation (BSSITSSegment) uses 32-bit
# triangle indices — so those shapes are vertex-limited only.
NIF_MAX_U16 = 65535


_TRI_16BIT_BLOCKTYPES = frozenset({
    'NiTriShape', 'NiTriShapeData', 'NiTriStrips', 'NiTriStripsData'})


# A unit factor is only believed when it is the same ratio for this many bone axes, to
# this relative tolerance. Both are loose enough for half-precision node transforms and
# far tighter than the spread a genuinely posed rig produces.
_UNIT_SCALE_MIN_SAMPLES = 30


_UNIT_SCALE_TOLERANCE = 0.002


def _havok_metres_or_one(ratios):
    """The unit factor for a skeleton whose bone ratios aren't one uniform scale.

    Not one scale means a posed rig, a nif that only shares bone names, or a skeleton of
    different proportions from the reference. The last still needs converting when it is
    in metres: Starfield's female skeleton against our (male) reference scatters 48..135,
    but every ratio sits within a factor of two of a median 0.3% from the Havok scale. A
    posed rig clusters near 1 instead. So believe Havok metres only when the ratios cluster
    tightly round it, and otherwise decline."""
    med = sorted(ratios)[len(ratios) // 2]
    if med <= 0 or abs(med / HAVOC_SCALE_FACTOR - 1) > 0.01:
        return 1.0
    if any(r <= 0 or not 0.5 < r / med < 2.0 for r in ratios):
        return 1.0
    return HAVOC_SCALE_FACTOR


def node_unit_scale(nif, reference):
    """How many of `reference`'s units one of `nif`'s node-transform units is.

    Starfield is the one game that mixes unit systems: it ships skeleton.nif and
    skeleton_facebones.nif with their NiNode transforms in Havok metres, while the .mesh
    geometry those bones skin, the BSSkinBoneData binds, and our own reference skeletons
    are all in Bethesda game units. Importing such a file without converting puts its
    bones ~70x too close to the origin.

    The factor is measured, not assumed, because "Starfield nifs are in metres" is false --
    statics and weapons carry ordinary game-unit node transforms, and only the skeleton
    files are the odd ones out. So compare this nif's node positions against the reference
    skeleton's, bone by bone, and accept the ratio only when every shared bone agrees on
    it. A nif that is simply POSED differs from the reference per bone rather than by one
    scale, so its ratios scatter and we decline -- which is what keeps FO4 posed rigs
    (power armor) out of this.

    Returns 1.0 whenever there is nothing to convert or nothing to measure against.
    """
    if reference is None or nif is None:
        return 1.0

    ratios = []
    for name, node in nif.nodes.items():
        ref = reference.nodes.get(name)
        if ref is None:
            continue
        a = node.global_transform.translation
        b = ref.global_transform.translation
        for i in range(3):
            # Skip axes sitting near zero: their ratio is dominated by rounding.
            if abs(b[i]) > 0.05 and abs(a[i]) > 1e-6:
                ratios.append(b[i] / a[i])

    if len(ratios) < _UNIT_SCALE_MIN_SAMPLES:
        return 1.0

    lo, hi = min(ratios), max(ratios)
    if lo <= 0 or (hi - lo) / hi > _UNIT_SCALE_TOLERANCE:
        return _havok_metres_or_one(ratios)

    scale = sum(ratios) / len(ratios)
    # Close enough to 1 to be measurement noise rather than a different unit system.
    return 1.0 if abs(scale - 1.0) < _UNIT_SCALE_TOLERANCE else scale


def shape_size_error(nverts, ntris, blocktype):
    """Return an error message if a shape of the given block type would exceed the
    nif format's hard 16-bit limits, else None. `blocktype` is the block name the
    shape will be written as (e.g. 'BSTriShape', 'NiTriShape')."""
    if nverts > NIF_MAX_U16:
        return (f"has {nverts} vertices, over the {NIF_MAX_U16}-vertex limit "
                "(nif vertex indices are 16-bit). Reduce the poly count or split "
                "the mesh into multiple shapes.")
    if blocktype in _TRI_16BIT_BLOCKTYPES and ntris > NIF_MAX_U16:
        return (f"has {ntris} triangles, over the {NIF_MAX_U16}-triangle limit for "
                f"{blocktype} (triangle count is 16-bit). Reduce the poly count or "
                "split the mesh into multiple shapes.")
    return None


# --- NifShape --- #
class NiShape(NiNode):
    buffer_type = PynBufferTypes.NiShapeBufType

    @classmethod
    def New(cls, handle=None, shapetype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        # cls.load_subclasses()
        if properties:
            shapetype = cls._buftype_name(properties.bufType)
        if not shapetype:
            if id == NODEID_NONE:
                id = nifly.getBlockID(file._handle, handle)
            shapetype = check_msg(dll_string, nifly.getBlockname, file._handle, id)
        try:
            new_shape = False
            if not handle and id == NODEID_NONE:
                new_shape = True
                id = check_msg(
                    nifly.addBlock,
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            if not handle:
                handle = check_msg(nifly.getBlockByID, id)
            
            s = file.read_node(
                handle=handle, id=id, parent=parent, properties=properties)
            if new_shape:
                s._partitions = []
            return s
        except KeyError:
            _niffile.NifFile.log.warning(f"Shape type is not implemented: {shapetype}")
            return None
        except Exception as e:
            _niffile.NifFile.log.error(f"Error creating shape of type {shapetype}: {e}")
            return None

    @classmethod
    def getbuf(cls, values=None):
        return NiShapeBuf(values)
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, parent=None, 
                 properties=None, name=""):
        super().__init__(handle=handle, file=file, id=id, parent=parent, 
                         properties=properties, name=name)
        self._bone_ids = None
        self._bone_names = None
        self._unique_bone_names = None
        self._normals = None
        self._colors = None
        self._scale = 1.0
        self._tris = None
        self._uvs = None
        self._textures = None
        self._is_skinned = False
        self._verts = None
        self._weights = None
        self._partitions = None
        self._partition_tris = None
        self._segment_file = ''
        self.is_head_part = False
        self._shader = None
        self._alpha = None

    def _setShapeXform(self):
        nifly.setTransform(self._handle, self.transform)

    @property
    def verts(self):
        if not self._verts:
            verts = (c_float * 3 * self.properties.vertexCount)()
            nifly.getVertsForShape(
                self.file._handle, self._handle, verts, self.properties.vertexCount * 3, 0)
            self._verts = [(v[0], v[1], v[2]) for v in verts]
        return self._verts

    @property
    def colors(self):
        """Returns colors as a list of 4-tuples representing color values, 1:1 with vertices."""
        if self._colors is None:
            if self.properties.hasVertexColors:
                buflen = self.properties.vertexCount
                buf = (c_float * 4 * buflen)()
                nifly.getColorsForShape(self.file._handle, self._handle, buf, buflen*4)
                self._colors = [(c[0], c[1], c[2], c[3]) for c in buf]
            else:
                self._colors = []
        return self._colors
    
    @property
    def normals(self):
        if not self._normals:
            buflen = self.properties.vertexCount 
            if buflen > 0:
                norms = (c_float * 3 * buflen)()
                nifly.getNormalsForShape(
                        self.file._handle, self._handle, norms, buflen * 3, 0)
                self._normals = [(n[0], n[1], n[2]) for n in norms]
        return self._normals

    @property
    def tris(self):
        if self._tris is None:
            triCount = self.properties.triangleCount
            buf = (c_uint16 * 3 * triCount)()
            nifly.getTriangles(
                    self.file._handle, self._handle, buf, triCount * 3, 0)
            self._tris = [(t[0], t[1], t[2]) for t in buf]
        return self._tris

    def _read_partitions(self):
        self._partitions = []
        buf = (c_uint16 * 2)()
        pc = nifly.getPartitions(self.file._handle, self._handle, None, 0)
        buf = (c_uint16 * 2 * pc)()
        pc = nifly.getPartitions(self.file._handle, self._handle, buf, pc)
        for i in range(pc):
            self._partitions.append(SkyPartition(buf[i][1], buf[i][0], namedict=self.file.dict))
    
    def _read_segments(self, num):
        self._partitions = []
        buf = (c_int * 2 * num)()
        pc = nifly.getSegments(self.file._handle, self._handle, buf, num)
        for i in range(num):
            p = FO4Segment(part_id=buf[i][0], index=i, subsegments=buf[i][1], namedict=self.file.dict)
            self._partitions.append(p)
            buf2 = (c_uint32 * 3 * p.subseg_count)()
            ssn = nifly.getSubsegments(self.file._handle, self._handle, p.id, buf2, p.subseg_count)
            for i in range(ssn):
                ss = FO4Subsegment(part_id=buf2[i][0],
                                   user_slot=buf2[i][1],
                                   material=buf2[i][2],
                                   parent=p,
                                   namedict=self.file.dict)
                # Pull cut offsets (slice-plane positions) for this subsegment.
                # Len+Data pattern: query count, then fill if any.
                cn = nifly.getSubsegmentCutOffsets(
                    self.file._handle, self._handle, ss.id, None, 0)
                if cn > 0:
                    cbuf = (c_float * cn)()
                    nifly.getSubsegmentCutOffsets(
                        self.file._handle, self._handle, ss.id, cbuf, cn)
                    ss.cut_offsets = [cbuf[k] for k in range(cn)]

    @property
    def partitions(self):
        if self._partitions is None:
            segc = nifly.segmentCount(self.file._handle, self._handle)
            if segc > 0:
                self._read_segments(segc)
            else:
                self._read_partitions()
        return self._partitions

    @property
    def partition_tris(self):
        """Returns a list of partition indices matching 1-1 with tris"""
        if self._partition_tris is None:
            buf = (c_uint16 * 1)()
            pc = nifly.getPartitionTris(self.file._handle, self._handle, None, 0)
            buf = (c_uint16 * pc)()
            pc = nifly.getPartitionTris(self.file._handle, self._handle, buf, pc)
            self._partition_tris = [0] * pc
            for i in range(pc):
                self._partition_tris[i] = buf[i]
        return self._partition_tris

    @property
    def segment_file(self):
        buflen = nifly.getSegmentFile(self.file._handle, self._handle, None, 0)+1
        buf = (c_char * buflen)()
        buflen = nifly.getSegmentFile(self.file._handle, self._handle, buf, buflen)
        self._segment_file = buf.value.decode('utf-8')
        return self._segment_file

    @segment_file.setter
    def segment_file(self, val):
        self._segment_file = val
    
    @property
    def uvs(self):
        if self._uvs is None:
            uvCount = self.properties.vertexCount
            buf = (c_float * 2 * uvCount)()
            check_msg(nifly.getUVs,
                    self.file._handle, self._handle, buf, uvCount * 2, 0)
            self._uvs = [(uv[0], uv[1]) for uv in buf]
        return self._uvs

    @property
    def skin_instance_name(self):
        """Return the block name of the skin instance, or '' if none."""
        sid = self.properties.skinInstanceID
        if sid == NODEID_NONE:
            return ''
        return dll_string(nifly.getBlockname, self.file._handle, sid)

    @property
    def shader_block_name(self):
        return dll_string(nifly.getBlockname, self.file._handle, self.properties.shaderPropertyID)

    @property
    def shaderflags1(self):
        return nifly.getShaderFlags1(self.file._handle, self._handle)

    @shaderflags1.setter
    def shaderflags1(self, val):
        nifly.setShaderFlags(self.file._handle, self._handle, val)

    @property
    def textures(self):
        return self.shader.textures

    def set_texture(self, slot:str, texturepath):
        """Set texture in the named slot to the given string."""
        self.shader.set_texture(slot, texturepath)
    
    @property
    def shader(self):
        """
        Returns a NiShaderBuf-like object associated with the shape. For Skyrim, this is
        the shader block; for FO4 it's the materials file associated with the shape's
        shader.
        """
        if self._shader is None:
            if self.file.game == 'FO4':
                self._shader = NiShaderFO4(
                    file=self.file, id=self.properties.shaderPropertyID, parent=self)
            else:
                self._shader = NiShader(
                    file=self.file, id=self.properties.shaderPropertyID, parent=self)

        return self._shader

    def save_shader_attributes(self):
        """
        Write out the shader attributes. FO4 files will have the shader properties written
        to the nif, not to a separate materials file.
        """
        if self._shader and self._shader._properties:
            name = self.shader.name
            if name is None: name = ''
            shader_id = nifly.addBlock(
                self.file._handle, 
                self._shader.name.encode('utf-8'), 
                byref(self._shader._properties), 
                self.id)
            self._shader.id = shader_id
            self.properties.shaderPropertyID = shader_id

    @property
    def has_alpha_property(self):
        return self.alpha_property != None
    
    @has_alpha_property.setter
    def has_alpha_property(self, val):
        if val and not self._alpha:
            self._alpha = NiAlphaProperty(file=self.file, parent=self)
    
    @property
    def alpha_property(self):
        if self._alpha is None and self.properties.alphaPropertyID != NODEID_NONE:
            self._alpha = NiAlphaProperty(
                file=self.file, id=self.properties.alphaPropertyID, parent=self)
        return self._alpha

    def save_alpha_property(self):
        if self._alpha:
            alpha_id = nifly.addBlock(
                self.file._handle, None, 
                byref(self._alpha.properties), self.id)
            self._alpha.id = alpha_id
            self.properties.alphaPropertyID = alpha_id

    @property
    def bone_names(self):
        """ List of bone names in the shape """
        if self._bone_names is None:
            bufsize = 300
            buf = create_string_buffer(bufsize+1)
            actualsize = nifly.getShapeBoneNames(self.file._handle, self._handle, buf, bufsize)
            if actualsize > bufsize:
                buf = create_string_buffer(actualsize+1)
                nifly.getShapeBoneNames(self.file._handle, self._handle, buf, actualsize+1)
            bn = buf.value.decode('utf-8').split('\n')
            self._bone_names = list(filter((lambda n: len(n) > 0), bn))
        return self._bone_names
        
    @property
    def bone_ids(self):
        if self._bone_ids is None:
            id_count = nifly.getShapeBoneCount(self.file._handle, self._handle)
            BUFDEF = c_int * id_count
            buf = BUFDEF()
            nifly.getShapeBoneIDs(self.file._handle, self._handle, buf, id_count)
            self._bone_ids = list(buf)
        return self._bone_ids

    @property
    def unique_bone_names(self):
        """Bone names deduplicated by node id, in first-occurrence order.

        The raw bone_names/bone_ids lists are partition-palette-aligned: a bone
        node repeats once per SkinPartition (skinned trees especially). This
        collapses those repeats to one name per distinct node.
        """
        if self._unique_bone_names is None:
            seen = set()
            result = []
            for nm, bid in zip(self.bone_names, self.bone_ids):
                if bid not in seen:
                    seen.add(bid)
                    result.append(nm)
            self._unique_bone_names = result
        return self._unique_bone_names

    def _bone_weights(self, bone_id):
        # Weights for all vertices (that are weighted to it)
        BUFSIZE = nifly.getShapeBoneWeightsCount(self.file._handle, self._handle, bone_id)
        BUFDEF = VERTEX_WEIGHT_PAIR * BUFSIZE
        buf = BUFDEF()
        nifly.getShapeBoneWeights(self.file._handle, self._handle,
                                          bone_id, buf, BUFSIZE)
        out = [(x.vertex, x.weight) for x in buf]
        return out

    @property
    def bone_weights(self):
        """ Dictionary of bone weights
            returns {bone-name: [(vertex-index, weight), ...], ...}

            Weights are aggregated by node id: the bone list is
            partition-palette-aligned, so a bone repeated across SkinPartitions
            carries a disjoint set of vertex weights at each palette position.
            Summing per vertex across those positions keeps every weight (a
            name-keyed overwrite would drop all but the last position).
            """
        if self._weights is None:
            by_id = {}     # node id -> {vertex: summed weight}
            id_name = {}   # node id -> name (first occurrence)
            for pos, (name, bid) in enumerate(zip(self.bone_names, self.bone_ids)):
                id_name.setdefault(bid, name)
                verts = by_id.setdefault(bid, {})
                for v, w in self._bone_weights(pos):
                    verts[v] = verts.get(v, 0.0) + w
            self._weights = {id_name[bid]: list(verts.items())
                             for bid, verts in by_id.items()}
        return self._weights

    def get_used_bones(self):
        """
        Return bones that have non-zero weights
        NOTE not really filtering out non-zero weights rn
        """
        return list(self.bone_weights.keys())

    @property
    def has_skin_instance(self):
        """ Determine whether this mash has a NiSkinData block.
            WARNING CURRENTLY BROKEN 
            """
        return nifly.hasSkinInstance(self._handle)

    @property
    def has_global_to_skin(self):
        """Determine whether the shape has the global-to-skin transform."""
        buf = TransformBuf()
        return nifly.getShapeGlobalToSkin(self.file._handle, self._handle, buf)
    
    def calc_global_to_skin(self):
        """Calculate the global-to-skin transform (whether or not it exists)."""
        buf = TransformBuf()
        nifly.calcShapeGlobalToSkin(self.file._handle, self._handle, buf)
        return buf
    
    @property
    def global_to_skin(self):
        """Return the global-to-skin transform on this shape; calculate it if not
        present. Calculated by averaging the skin-to-bone (pose) transforms on all the
        bones. 
        """
        buf = TransformBuf()
        has_xform = nifly.getShapeGlobalToSkin(self.file._handle, self._handle, buf)
        if not has_xform:
            nifly.calcShapeGlobalToSkin(self.file._handle, self._handle, buf)
        return buf

    def get_shape_skin_to_bone(self, bone_name):
        """ Return the skin-to-bone transform, getting it from the nif data """
        buf = TransformBuf()
        xform_found = nifly.getShapeSkinToBone(self.file._handle, 
                                                       self._handle, 
                                                       bone_name.encode('utf-8'),
                                                       buf)
        if xform_found:
            return buf
        else:
            return None

    def get_shape_skin_to_bone_by_index(self, bone_index):
        """Return the skin-to-bone transform for the bone at the given INDEX, or None.

        Starfield (BSGeometry/BSSkinBoneData) stores bind transforms indexed by position and
        carries no NiNode boneRefs, so the name-based lookup fails; this reads BSSkinBoneData
        directly by index. Bone index matches the order of unique_bone_names / SkinAttach.
        """
        buf = TransformBuf()
        xform_found = nifly.getShapeSkinToBoneByIndex(self.file._handle,
                                                      self._handle,
                                                      bone_index,
                                                      buf)
        return buf if xform_found else None

    def set_skin_to_bone_xform(self, bone_name, xform: TransformBuf):
        """Set the skin-to-bone transform on the shape's skin, using the skin."""
        nifly.setShapeSkinToBone(self.file._handle,
                                         self._handle,
                                         bone_name.encode('utf-8'),
                                         xform)


    # #############  Creating shapes #############

    def skin(self):
        nifly.skinShape(self.file._handle, self._handle)
        self._is_skinned = True

    def demote_skin_instance(self):
        """Replace BSDismemberSkinInstance with plain NiSkinInstance on this shape."""
        if nifly.demoteSkinInstance:
            nifly.demoteSkinInstance(self.file._handle, self._handle)

    def set_global_to_skin(self, transform):
        """ Sets the skin transform which offsets the vert locations. This allows a head
            to have verts around the origin but to be positioned properly when skinned.
            Works whether or not there is a SkinInstance block
            """
        if not self._is_skinned:
            self.skin()
        nifly.setShapeGlobalToSkin(self.file._handle, self._handle, transform)

    def add_bone(self, bone_name, xform=None, parent_name=None):
        """Add bone to shape. This resets all the shape's bone information, so 
        skin-to-bone transforms and bone weights will need to be reset.
        Add all bones first, then set transforms and weights.
        """
        if not self._is_skinned:
            self.skin()
        if xform:
            buf = xform
        else:
            buf = TransformBuf() 
            buf.set_identity()
        
        par = None
        if parent_name:
            par = parent_name.encode('utf-8')
        
        h = nifly.addBoneToNifShape(self.file._handle, self._handle, 
                                            bone_name.encode('utf-8'), buf,
                                            par)
        NiNode(handle=h, file=self.file, name=bone_name)

        
    def setShapeWeights(self, bone_name, vert_weights):
        """ Set the weights for a bone in a shape. 
        """
        VERT_BUF_DEF = VERTEX_WEIGHT_PAIR * len(vert_weights)
        vert_buf = VERT_BUF_DEF()
        for i, vw in enumerate(vert_weights):
            vert_buf[i].vertex = vw[0]
            vert_buf[i].weight = vw[1]
        xfbuf = TransformBuf()

        nifly.setShapeBoneWeights(self.file._handle, self._handle, 
                                      bone_name.encode('utf-8'),
                                      vert_buf, len(vert_weights))
       
    def set_partitions(self, partitionlist, trilist):
        """ Set the partitions for a shape
            partitionlist = list of Partition objects, either Skyrim or FO. Any Subsegments in the
                list are ignored. Subsegments are found separately under Partitions.
            trilist = 1:1 with shape tris. For Skyrim, each entry is either a partition ID
                (e.g. 130, 143) or an index into partitionlist (0, 1, ...) — the values from
                NiShape.partition_tris are accepted directly. For FO4, entries must be
                segment/subsegment IDs (the partition_tris values).
            """
        if len(partitionlist) == 0:
            return
        
        # In FO4, create a clean list of segments covering subsegments in partitionlist.
        # In Skyrim, just use the partitionlist as given.
        if self.file.game == 'FO4':
            pdict = {}
            maxid = max([p.id for p in partitionlist])
            for p in partitionlist:
                if type(p).__name__ == "FO4Subsegment":
                    seg_new = p.parent
                elif type(p).__name__ == "FO4Segment":
                    seg_new = p
                if seg_new.name not in pdict:
                    pdict[seg_new.name] = seg_new
                # All prior segments must also be included
                for i in range(0, seg_new.index):
                    if f"FO4 Seg {i:03d}" not in pdict:
                        maxid += 1
                        pdict[f"FO4 Seg {i:03d}"] = FO4Segment(part_id=maxid, index=i)
            parts = list(pdict.values())
            parts.sort(key=lambda x: x.index)
        else:
            parts = list(filter(
                lambda x: type(x).__name__ == "SkyPartition", 
                partitionlist))

        if len(parts) == 0:
            return

        parts_lookup = {}
        
        tbuf = (c_uint16 * len(trilist))()

        if game_traits(self.file.game).skyrim:
            # nifly wants indices into the partition list. The trilist may already be
            # indices (as returned by partition_tris) or partition IDs (the older idiom).
            pbuf = (c_uint16 * 2 * len(parts))()
            for i, p in enumerate(parts):
                pbuf[i][0] = 0
                pbuf[i][1] = p.id
                parts_lookup[p.id] = i

            # Auto-detect: if every value matches a partition ID, treat as IDs;
            # otherwise if every value is a valid index, treat as indices.
            n = len(parts)
            all_ids = all(t in parts_lookup for t in trilist)
            all_indices = all(0 <= t < n for t in trilist)
            as_indices = all_indices and not all_ids

            for i, t in enumerate(trilist):
                if as_indices:
                    tbuf[i] = t
                else:
                    try:
                        tbuf[i] = parts_lookup[t]
                    except KeyError:
                        # Report the error unless the id is 0--that means we couldn't assign the
                        # partition and that error has already been reported
                        if t != 0:
                            log.error(f"Tri at index {i} assigned partition id {t}, but no such partition defined")
                            log.error(f"Partitions are {parts_lookup.items()}")
                        tbuf[i] = pbuf[0][1] # Export with the first partition so we get something out

            nifly.setPartitions(self.file._handle, self._handle,
                                        pbuf, len(parts),
                                        tbuf, len(trilist))
        else:
            # For segments, the trilist has to refer to IDs becuase of referring to subsegments.
            pbuf = (c_uint16 * len(parts))()
            for i, p in enumerate(parts):
                pbuf[i] = p.id 
                parts_lookup[p.id] = i

            for i, t in enumerate(trilist): 
                tbuf[i] = trilist[i]

            sslist = []
            cutcounts = []   # one entry per subsegment, parallel to sslist quads
            cutdata = []     # concatenated cut-offset floats
            for seg in parts:
                for sseg in seg.subsegments:
                    sslist.extend([sseg.id, seg.id, sseg.user_slot, sseg.material])
                    co = getattr(sseg, "cut_offsets", None) or []
                    cutcounts.append(len(co))
                    cutdata.extend(co)
            sbuf = (c_uint32 * len(sslist))()
            for i, s in enumerate(sslist):
                sbuf[i] = s
            ccbuf = (c_uint32 * len(cutcounts))()
            for i, n in enumerate(cutcounts):
                ccbuf[i] = n
            cdbuf = (c_float * len(cutdata))()
            for i, v in enumerate(cutdata):
                cdbuf[i] = v

            nifly.setSegments(self.file._handle, self._handle,
                                      pbuf, len(parts),
                                      sbuf, int(len(sslist)/4),
                                      tbuf, len(trilist),
                                      self._segment_file.encode('utf-8'),
                                      ccbuf, len(cutcounts),
                                      cdbuf, len(cutdata))

    def set_colors(self, colors):
        buf = (c_float * 4 * len(colors))()
        for i, c in enumerate(colors):
            buf[i][0] = c[0]
            buf[i][1] = c[1]
            buf[i][2] = c[2]
            buf[i][3] = c[3]
        nifly.setColorsForShape(self.file._handle, self._handle, 
                                        buf, len(colors))


# --- NiTriShape --- #
class NiTriShape(NiShape):
    buffer_type = PynBufferTypes.NiTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiTriShapeBuf(values)


class BSSegmentedTriShape(NiTriShape):
    pass


class NiScreenElements(NiTriShape):
    pass


# --- BSTriShape --- #
class BSTriShape(NiShape):
    buffer_type = PynBufferTypes.BSTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        b = BSTriShapeBuf(values)
        b.bufType = PynBufferTypes.BSTriShapeBufType
        return b


# --- BSDynamicTriShape --- #
class BSDynamicTriShape(NiShape):
    buffer_type = PynBufferTypes.BSDynamicTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        b = BSDynamicTriShapeBuf(values)
        b.bufType = PynBufferTypes.BSDynamicTriShapeBufType
        return b


# --- BSSubIndexTriShape --- #
class BSSubIndexTriShape(NiShape):
    buffer_type = PynBufferTypes.BSSubIndexTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        b = BSSubIndexTriShapeBuf(values)
        b.bufType = PynBufferTypes.BSSubIndexTriShapeBufType
        return b


# --- BSGeometry (Starfield) --- #
class BSGeometry(NiShape):
    """Starfield geometry shape. Holds one mesh slot per LOD; each slot's geometry lives in
    an external .mesh file (referenced by meshName) and isn't present until load_mesh() feeds
    the bytes. Once a slot is loaded+selected, the normal geometry/bone accessors work (nifly
    routes them through GetGeometryData and reads bones from SkinAttach)."""
    buffer_type = PynBufferTypes.BSGeometryBufType

    @classmethod
    def getbuf(cls, values=None):
        # C++ reads a BSGeometry block as a plain NiShapeBuf (no distinct C++ bufType).
        return NiShapeBuf(values)

    @property
    def colors(self):
        """Per-vertex colors of the loaded/selected .mesh. A BSGeometry keeps its colors in the
        external .mesh (BSGeometryMeshData.vColors), which the generic color accessor doesn't
        read -- so route through the dedicated reader (else every color is black)."""
        if self._colors is None:
            n = len(self.verts)
            if n:
                buf = (c_float * 4 * n)()
                got = nifly.getBSGeometryColors(self.file._handle, self._handle, buf, n)
                self._colors = [(c[0], c[1], c[2], c[3]) for c in buf[:got]]
            else:
                self._colors = []
        return self._colors

    @property
    def mesh_count(self):
        """Number of LOD mesh slots."""
        return nifly.getBSGeometryMeshCount(self.file._handle, self._handle)

    @property
    def is_internal_geom(self):
        """True if mesh data is embedded in the NIF (flag 0x200) vs an external .mesh."""
        return bool(nifly.getBSGeometryInternalFlag(self.file._handle, self._handle))

    def mesh_path(self, slot=0):
        """The external .mesh path (verbatim meshName) for LOD slot `slot`."""
        buf = create_string_buffer(256)
        n = nifly.getBSGeometryMeshPath(self.file._handle, self._handle, slot, buf, 256)
        if n >= 256:
            buf = create_string_buffer(n + 1)
            nifly.getBSGeometryMeshPath(self.file._handle, self._handle, slot, buf, n + 1)
        return buf.value.decode('utf-8')

    def mesh_paths(self):
        """All LOD mesh paths, one per slot."""
        return [self.mesh_path(i) for i in range(self.mesh_count)]

    def load_mesh(self, data, slot=0):
        """Load external .mesh bytes into LOD slot `slot` and select it. Refreshes the cached
        geometry so verts/tris/normals/uvs/weights read from the loaded mesh."""
        ok = nifly.loadBSGeometryMeshData(
            self.file._handle, self._handle, slot, data, len(data))
        self._invalidate_geometry()
        return bool(ok)

    def select_mesh(self, slot):
        """Select which LOD slot the geometry accessors read from."""
        nifly.selectBSGeometryMesh(self.file._handle, self._handle, slot)
        self._invalidate_geometry()

    def save_mesh(self, slot=0):
        """Serialize LOD slot `slot` to external-.mesh bytes (regenerating meshlets + cull
        data first) and return them, ready to write to the resolved .mesh path. Returns
        b"" if the slot has no data."""
        n = nifly.saveBSGeometryMeshData(self.file._handle, self._handle, slot, None, 0)
        if n <= 0:
            return b""
        buf = create_string_buffer(n)
        nifly.saveBSGeometryMeshData(self.file._handle, self._handle, slot, buf, n)
        return buf.raw[:n]

    def set_mesh_name(self, name, slot=0):
        """Set the external .mesh path (meshName) the NIF references for LOD slot `slot`.
        The .mesh bytes themselves are written separately via save_mesh()."""
        nifly.setBSGeometryMeshName(
            self.file._handle, self._handle, slot, name.encode('utf-8'))
        self._invalidate_geometry()

    def add_mesh(self, verts, tris, uvs=None, normals=None):
        """Add a LOD slot filled from this geometry, the way createShapeFromData fills slot 0.
        Returns the new slot's index, which is left selected. Set its meshName, colors and
        weights with the slot-taking setters; the skin's bone list is shared by every slot."""
        n = len(verts)
        vbuf = (c_float * 3 * n)(*[tuple(v) for v in verts])
        tbuf = (c_uint16 * 3 * len(tris))(*[tuple(t) for t in tris])
        ubuf = (c_float * 2 * n)(*[tuple(u) for u in uvs]) if uvs else None
        nbuf = (c_float * 3 * n)(*[tuple(v) for v in normals]) if normals else None
        slot = nifly.addBSGeometryMesh(self.file._handle, self._handle, vbuf, n,
                                       tbuf, len(tris), ubuf, nbuf)
        self._invalidate_geometry()
        return slot

    def set_mesh_tangents(self, tangents, tangent_ws=None, slot=0):
        """Set per-vertex tangents for LOD slot `slot`. tangents = [(x,y,z)...]; tangent_ws =
        the 2-bit bitangent-sign W of each tangent (1 or 3), defaulting to 1 if omitted."""
        n = len(tangents)
        tbuf = (c_float * 3 * n)()
        for i, t in enumerate(tangents):
            tbuf[i] = (t[0], t[1], t[2])
        wbuf = (c_uint8 * n)()
        for i in range(n):
            wbuf[i] = (tangent_ws[i] if tangent_ws else 1)
        nifly.setBSGeometryTangents(
            self.file._handle, self._handle, slot, tbuf, wbuf, n)

    def set_mesh_colors(self, colors, slot=0):
        """Set per-vertex colors for LOD slot `slot`. colors = [(r,g,b,a)...] floats 0..1,
        stored as the .mesh's byte colors."""
        n = len(colors)
        cbuf = (c_float * 4 * n)()
        for i, c in enumerate(colors):
            cbuf[i] = (c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)
        nifly.setBSGeometryColors(self.file._handle, self._handle, slot, cbuf, n)

    def skin_bones(self, bone_names, weights_per_vertex=4):
        """Set up SF skinning: create the BSSkin::Instance + BSSkin::BoneData (identity binds)
        + SkinAttach carrying `bone_names` (in order), set the mesh's weightsPerVertex, and zero
        the per-vertex weight slots. `weights_per_vertex` sizes the .mesh's uniform weight slots
        (nifly caps set_vert_weights to it), so pass the max influence count the shape will use.
        Call set_bone_bind() + set_vert_weights() afterward. Geometry must already be set."""
        namesNL = "\n".join(bone_names).encode('utf-8')
        nifly.skinBSGeometry(self.file._handle, self._handle, namesNL, len(bone_names),
                             weights_per_vertex)
        self._invalidate_geometry()

    def get_shape_skin_to_bone(self, bone_name):
        """The bind (skin-to-bone) transform for `bone_name`, or None if the shape doesn't use
        it. Starfield keys binds by position in the bone list and has no NiNode boneRefs for
        the generic name lookup to walk, so go through the bone's index."""
        try:
            i = list(self.bone_names).index(bone_name)
        except ValueError:
            return None
        return self.get_shape_skin_to_bone_by_index(i)

    def set_bone_bind(self, bone_index, xform: TransformBuf):
        """Set the skin-to-bone (bind) transform for the bone at `bone_index` (SkinAttach
        order). Pass the bind in game units; the DLL divides translation by havokScale."""
        nifly.setBSGeometryBoneBind(self.file._handle, self._handle, bone_index, xform)

    def set_weights_per_vertex(self, weights_per_vertex, slot=0):
        """Prepare LOD slot `slot` for weights: select it, set how many influences its .mesh
        stores per vertex, and zero its weights. skin_bones() does this for the selected slot;
        call this for each further slot before its set_vert_weights()."""
        nifly.setBSGeometryWeightsPerVertex(self.file._handle, self._handle, slot,
                                            weights_per_vertex)
        self._invalidate_geometry()

    def set_vert_weights(self, vert_index, bone_indices, weights, slot=None):
        """Set the bone weights for one vertex. bone_indices index the shape's bone list
        (SkinAttach order); weights are floats (nifly normalizes + quantizes into the .mesh).
        Writes to the selected LOD slot, or to `slot` if given (which then stays selected)."""
        if slot is not None:
            nifly.selectBSGeometryMesh(self.file._handle, self._handle, slot)
        n = len(bone_indices)
        bbuf = (c_uint8 * n)(*bone_indices)
        wbuf = (c_float * n)(*weights)
        nifly.setBSGeometryVertWeights(self.file._handle, self._handle, vert_index, bbuf, wbuf, n)

    def update_skin_bounds(self):
        """Recompute the per-bone bounding spheres in BSSkin::BoneData from the current binds +
        vertex weights. Call once after all set_bone_bind()/set_vert_weights() calls. Leaving the
        default zero-radius spheres crashes the Creation Kit when it opens an actor using the mesh."""
        nifly.updateBSGeometrySkinBounds(self.file._handle, self._handle)

    def _invalidate_geometry(self):
        # vertexCount/triangleCount live in the cached NiShapeBuf, which is stale once a
        # different .mesh slot is loaded/selected. Clear it and the geometry caches so they
        # re-read against the now-current mesh.
        self._properties = None
        self._verts = self._tris = self._uvs = self._normals = self._colors = None
        self._weights = self._bone_names = self._bone_ids = self._unique_bone_names = None

    @property
    def tris(self):
        """BSGeometry doesn't populate NiGeometryData's 16-bit triangleCount, so size the
        buffer from getTriangles' authoritative return value (a second pass if the first
        buffer was too small)."""
        if self._tris is None:
            cap = max(self.properties.vertexCount * 4, 64)
            buf = (c_uint16 * 3 * cap)()
            n = nifly.getTriangles(self.file._handle, self._handle, buf, cap * 3, 0)
            if n > cap:
                cap = n
                buf = (c_uint16 * 3 * cap)()
                nifly.getTriangles(self.file._handle, self._handle, buf, cap * 3, 0)
            self._tris = [(buf[i][0], buf[i][1], buf[i][2]) for i in range(n)]
        return self._tris

    @property
    def unique_bone_names(self):
        """SkinAttach bone names are already unique -- no partition-palette repetition."""
        return self.bone_names

    @property
    def bone_weights(self):
        """SF weights are keyed by bone INDEX (position in the SkinAttach bone list). There
        are no node-ref bone IDs, so the base class's id-based dedup doesn't apply."""
        if self._weights is None:
            self._weights = {name: self._bone_weights(i)
                             for i, name in enumerate(self.bone_names)}
        return self._weights


# --- NiTriStrips --- #
class NiTriStrips(NiShape):
    buffer_type = PynBufferTypes.NiTriStripsBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiTriStripsBuf(values)


# --- BSMeshLODTriShape --- #
class BSMeshLODTriShape(NiShape):
    buffer_type = PynBufferTypes.BSMeshLODTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSMeshLODTriShapeBuf(values)


# --- BSLODTriShape --- #
class BSLODTriShape(NiShape):
    buffer_type = PynBufferTypes.BSLODTriShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSLODTriShapeBuf(values)


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .base import (FO4Segment, FO4Subsegment, SkyPartition, check_msg, dll_string)  # noqa: E402
from .shaders import (NiAlphaProperty, NiShader, NiShaderFO4)  # noqa: E402
from . import niffile as _niffile  # noqa: E402
