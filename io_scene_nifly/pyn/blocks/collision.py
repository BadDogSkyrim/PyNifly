"""Havok collision blocks: bhk shapes, rigid bodies, constraints, collision objects and
the FO4 physics system."""

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
from .base import NiObject


log = logging.getLogger("pynifly")


class bhkShape(NiObject):
    @classmethod
    def New(cls, collisiontype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        if properties:
            collisiontype = cls.buffer_types[properties.bufType].__name__
        elif not collisiontype:
            collisiontype = dll_string(nifly.getBlockname, file._handle, id)
        try:
            if id == NODEID_NONE:
                id = nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            return file.read_node(
                id=id, parent=parent, properties=properties)
        except Exception:
            return None


class bhkBoxShape(bhkShape):
    buffer_type = PynBufferTypes.bhkBoxShapeBufType
    needsTransform = True
    buffer_type = PynBufferTypes.bhkBoxShapeBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkBoxShapeProps(values)


class bhkCapsuleShape(bhkShape):
    buffer_type = PynBufferTypes.bhkCapsuleShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkCapsuleShapeProps(values)


class bhkSphereShape(bhkShape):
    buffer_type = PynBufferTypes.bhkSphereShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkSphereShapeBuf(values)


class bhkConvexVerticesShape(bhkShape):
    buffer_type = PynBufferTypes.bhkConvexVerticesShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkConvexVerticesShapeProps(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        super().__init__(handle=handle, id=id, file=file, parent=parent, 
                         properties=properties)
        self._vertices = None
        self._normals = None

    @property
    def vertices(self):
        if not self._vertices:
            verts = (VECTOR4 * self.properties.vertsCount)()
            nifly.getCollShapeVerts(self.file._handle, 
                                            self.id, 
                                            verts, self.properties.vertsCount)
            self._vertices = [tuple(v) for v in verts]
        return self._vertices

    @property
    def normals(self):
        if not self._normals:
            norms = (VECTOR4 * self.properties.normalsCount)()
            nifly.getCollShapeNormals(self.file._handle, 
                                              self.id, 
                                              norms, self.properties.normalsCount)
            self._normals = [tuple(v) for v in norms]
        return self._normals


class bhkListShape(bhkShape):
    buffer_type = PynBufferTypes.bhkListShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkListShapeProps(values)

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._children = None

    @property
    def children(self):
        if not self._children:
            if self.properties.childCount == 0:
                self._children = []
            else:
                buf = (c_uint32 * self.properties.childCount)()
                nifly.getCollListShapeChildren(self.file._handle,
                                                       self.id,
                                                       buf, self.properties.childCount)
                self._children = []
                for idx in buf:
                    self._children.append(bhkShape.New(
                        id=idx, file=self.file, parent=self))
        
        return self._children

    def add_child(self, childnode):
        nifly.addCollListChild(
            self.file._handle, self.id, childnode.id)

    def add_shape(self, childprops, transform=None):
        child = bhkShape.New(file=self.file, properties=childprops, parent=self)
        if not self._children:
            self._children = []
        self._children.append(child)
        return child


class bhkConvexTransformShape(bhkShape):
    buffer_type = PynBufferTypes.bhkConvexTransformShapeBufType
    needsTransform = False
    
    @classmethod
    def getbuf(cls, values=None):
        return bhkConvexTransformShapeProps(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, 
                 properties=None, transform=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, 
                         parent=parent)
        if transform:
            self._set_transform(transform)
        self._child = None

    def _set_transform(self, xf):
        pt = self._props.transform
        for r in range(0, 4):
            for c in range(0, 4):
                pt[c*4+r] = xf[r][c]

    @property
    def transform(self):
        t = self.properties.transform
        return ((t[0][0], t[1][0], t[2][0], t[3][0]),
                (t[0][1], t[1][1], t[2][1], t[3][1]),
                (t[0][2], t[1][2], t[2][2], t[3][2]),
                (t[0][3], t[1][3], t[2][3], t[3][3]))

    def add_shape(self, childprops):
        child = bhkShape.New(file=self.file, properties=childprops, parent=self)
        self._child = child
        self.properties.shapeID = child.id
        return child

    @property
    def child(self):
        if self._child: return self._child
        self._child = bhkShape.New(id=self.properties.shapeID, file=self.file, parent=self)
        return self._child

    @child.setter
    def child(self, value):
        nifly.setCollConvexTransformShapeChild(self.file._handle,
                                                       self.id,
                                                       value.id)


class bhkMoppBvTreeShape(bhkShape):
    """MOPP BVH tree wrapping a child collision shape (bhkPackedNiTriStripsShape or bhkCompressedMeshShape)."""
    buffer_type = PynBufferTypes.bhkMoppBvTreeShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkMoppBvTreeShapeBuf(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        super().__init__(handle=handle, id=id, file=file, parent=parent, properties=properties)
        self._child = None

    @property
    def child(self):
        if self._child is None:
            self._child = bhkShape.New(
                id=self.properties.shapeID, file=self.file, parent=self)
        return self._child

    @property
    def mopp_data(self):
        """Return (mopp_bytes, origin, scale) or (b'', (0,0,0), 0) if unavailable."""
        length = nifly.getCollMoppCodeLen(self.file._handle, self.id)
        if length <= 0:
            return b"", (0.0, 0.0, 0.0), 0.0
        origin_buf = (c_float * 3)()
        scale_buf = c_float()
        mopp_buf = (c_uint8 * length)()
        nifly.getCollMoppCode(self.file._handle, self.id,
                              origin_buf, byref(scale_buf), mopp_buf, length)
        origin = (origin_buf[0], origin_buf[1], origin_buf[2])
        return bytes(mopp_buf), origin, scale_buf.value

    @classmethod
    def Create(cls, file, verts, tris, game, radius=0.005, material=0,
               face_materials=None, parent=None):
        """Create a bhkMoppBvTreeShape with child shape and MOPP bytecode.

        Args:
            file: NifFile to add blocks to.
            verts: List of (x,y,z) in Havok space.
            tris: List of (i,j,k) triangle indices.
            game: Game name string ('SKYRIMSE', 'SKYRIM', etc.).
            radius: Collision radius.
            material: Default Havok material ID.
            face_materials: Optional per-face material uint32 list.
            parent: Parent block (bhkRigidBody).

        Returns:
            bhkMoppBvTreeShape instance.
        """
        from ..mopp_compiler import compile_mopp

        # Create MOPP block (child shape ID will be set by child creation)
        buf = bhkMoppBvTreeShapeBuf()
        buf.shapeID = NODEID_NONE
        buf.buildType = 1  # placeholder; real value set in setCollMoppCode below
        mopp_id = check_msg(nifly.addBlock, file._handle, None, byref(buf),
                            parent.id if parent else NODEID_NONE)
        mopp_shape = cls(file=file, id=mopp_id, properties=buf, parent=parent)

        # Create the appropriate child shape
        if game in ('SKYRIM',):
            if face_materials and len(set(face_materials)) > 1:
                log.warning("Skyrim LE does not support per-chunk materials; "
                            "using default material")
            child = bhkPackedNiTriStripsShape.Create(
                file, verts, tris, radius=radius, material=material,
                parent=mopp_shape)
            output_ids = list(range(len(tris)))
        else:
            # For SE, pass default material via face_materials if no per-face
            # materials are provided.
            if not face_materials and material != 0:
                face_materials = [material] * len(tris)
            child, output_ids = bhkCompressedMeshShape.Create(
                file, verts, tris, radius=radius,
                face_materials=face_materials, parent=mopp_shape,
                target=file.rootNode)

        # Compile MOPP bytecode
        mopp_bytes, origin, scale = compile_mopp(verts, tris, radius=radius,
                                                  output_ids=output_ids)

        # Set MOPP code on the block.
        # The 'scale' parameter is stored in offset.w and used by the engine
        # for MOPP spatial quantisation (254*256*256 / largest_dim).
        # buildType: 0=BUILT_WITH_CHUNK_SUBDIVISION,
        #            1=BUILT_WITHOUT_CHUNK_SUBDIVISION, 2=BUILD_NOT_SET
        # Vanilla always uses 1 (BUILT_WITHOUT_CHUNK_SUBDIVISION).
        origin_buf = (c_float * 3)(*origin)
        mopp_buf = (c_uint8 * len(mopp_bytes))(*mopp_bytes)
        check_msg(nifly.setCollMoppCode, file._handle, mopp_id,
                  origin_buf, c_float(scale), mopp_buf, len(mopp_bytes),
                  c_uint8(1))

        return mopp_shape


class bhkPackedNiTriStripsShape(bhkShape):
    """Packed triangle strips shape (Skyrim LE). Child of bhkMoppBvTreeShape."""
    buffer_type = PynBufferTypes.bhkPackedNiTriStripsShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkPackedNiTriStripsShapeBuf(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        super().__init__(handle=handle, id=id, file=file, parent=parent, properties=properties)
        self._vertices = None
        self._triangles = None

    @classmethod
    def Create(cls, file, verts, tris, radius=0.005, material=0, parent=None):
        """Create a bhkPackedNiTriStripsShape with geometry data.

        Args:
            file: NifFile to add blocks to.
            verts: List of (x,y,z) in Havok space.
            tris: List of (i,j,k) triangle indices.
            radius: Collision radius.
            material: Havok material ID.
            parent: Parent block (bhkMoppBvTreeShape).

        Returns:
            bhkPackedNiTriStripsShape instance.
        """
        buf = bhkPackedNiTriStripsShapeBuf()
        buf.radius = radius
        buf.material = material
        shape_id = check_msg(nifly.addBlock, file._handle, None, byref(buf),
                             parent.id if parent else NODEID_NONE)

        if nifly.getCollPackedStripsDataID is not None:
            data_id = nifly.getCollPackedStripsDataID(file._handle, shape_id)

            if data_id >= 0 and nifly.setCollPackedStripsVerts is not None:
                # Set vertices
                flat_verts = (c_float * (len(verts) * 3))()
                for i, (x, y, z) in enumerate(verts):
                    flat_verts[i*3] = x
                    flat_verts[i*3+1] = y
                    flat_verts[i*3+2] = z
                check_msg(nifly.setCollPackedStripsVerts, file._handle,
                          data_id, flat_verts, len(verts))

            if data_id >= 0 and nifly.setCollPackedStripsTris is not None:
                # Set triangles (no normals for now)
                flat_tris = (c_uint16 * (len(tris) * 3))()
                for i, (a, b, c) in enumerate(tris):
                    flat_tris[i*3] = a
                    flat_tris[i*3+1] = b
                    flat_tris[i*3+2] = c
                check_msg(nifly.setCollPackedStripsTris, file._handle,
                          data_id, flat_tris, len(tris), None)

        shape = cls(file=file, id=shape_id, properties=buf, parent=parent)
        return shape

    @property
    def vertices(self):
        if self._vertices is None:
            if nifly.getCollPackedStripsShapeVerts is None:
                self._vertices = []
                return self._vertices
            count = nifly.getCollPackedStripsShapeVerts(
                self.file._handle, self.properties.dataID, None, 0)
            if count > 0:
                buf = (c_float * (count * 3))()
                nifly.getCollPackedStripsShapeVerts(
                    self.file._handle, self.properties.dataID, buf, count)
                self._vertices = [(buf[i*3], buf[i*3+1], buf[i*3+2])
                                  for i in range(count)]
            else:
                self._vertices = []
        return self._vertices

    @property
    def triangles(self):
        if self._triangles is None:
            if nifly.getCollPackedStripsShapeTris is None:
                self._triangles = []
                return self._triangles
            count = nifly.getCollPackedStripsShapeTris(
                self.file._handle, self.properties.dataID, None, 0)
            if count > 0:
                buf = (c_uint16 * (count * 3))()
                nifly.getCollPackedStripsShapeTris(
                    self.file._handle, self.properties.dataID, buf, count)
                self._triangles = [(buf[i*3], buf[i*3+1], buf[i*3+2])
                                   for i in range(count)]
            else:
                self._triangles = []
        return self._triangles


class bhkCompressedMeshShape(bhkShape):
    """Compressed mesh shape (Skyrim SE). Child of bhkMoppBvTreeShape."""
    buffer_type = PynBufferTypes.bhkCompressedMeshShapeBufType
    needsTransform = False

    @classmethod
    def getbuf(cls, values=None):
        return bhkCompressedMeshShapeBuf(values)

    def __init__(self, handle=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        super().__init__(handle=handle, id=id, file=file, parent=parent, properties=properties)
        self._vertices = None
        self._triangles = None

    @classmethod
    def Create(cls, file, verts, tris, radius=0.005, face_materials=None,
               parent=None, target=None):
        """Create a bhkCompressedMeshShape with chunked geometry data.

        Segments the mesh into chunks (<=255 verts, <=255 tris each),
        quantizes vertices, builds triangle strips, and creates all DLL blocks.

        Args:
            file: NifFile to add blocks to.
            verts: List of (x,y,z) in Havok space.
            tris: List of (i,j,k) triangle indices.
            radius: Collision radius.
            face_materials: Optional per-face HavokMaterial uint32 list.
            parent: Parent block (bhkMoppBvTreeShape).
            target: NiNode this collision belongs to. Defaults to file.rootNode.
                Vanilla SE nifs set Target to the root node.

        Returns:
            (bhkCompressedMeshShape, output_ids)
            output_ids: List of MOPP output IDs per input triangle.
        """
        from ..mesh_segment import segment_mesh
        from ..tri_strip import stripify

        # Build materials array from per-face materials
        # materials_list[i] = (havok_material, layer) — chunks reference by index
        if face_materials and any(m != 0 for m in face_materials):
            unique_mats = sorted(set(face_materials))
            mat_to_idx = {m: i for i, m in enumerate(unique_mats)}
        else:
            unique_mats = [0]  # single default material
            mat_to_idx = {0: 0}
            face_materials = None  # treat as uniform

        # Segment mesh into chunks — split by material first if multi-material
        if face_materials and len(unique_mats) > 1:
            # Group faces by material, then segment each material group
            all_groups = segment_mesh(verts, tris)
            # Re-split any group that mixes materials
            groups = []
            for group in all_groups:
                mats_in_group = set(face_materials[fi] for fi in group)
                if len(mats_in_group) <= 1:
                    groups.append(group)
                else:
                    for mat_val in mats_in_group:
                        sub = [fi for fi in group if face_materials[fi] == mat_val]
                        if sub:
                            groups.append(sub)
        else:
            groups = segment_mesh(verts, tris)

        # Vanilla Havok toolchain always uses fixed bit-field widths for
        # shape-key encoding, regardless of actual chunk sizes.  The engine
        # may assume these constants when decoding MOPP output IDs.
        bits_per_index = 17
        bits_per_w_index = 18
        mask_index = 0x1FFFF
        mask_w_index = 0x3FFFF

        # Set up buffer with data-block params and create shape + data blocks
        if target is None:
            target = file.rootNode
        buf = bhkCompressedMeshShapeBuf()
        buf.radius = radius
        buf.bitsPerIndex = bits_per_index
        buf.bitsPerWIndex = bits_per_w_index
        buf.maskIndex = mask_index
        buf.maskWIndex = mask_w_index
        buf.error = 0.001  # standard quantization tolerance for Skyrim SE
        buf.materialType = 1 if face_materials else 0
        buf.targetID = target.id if target else NODEID_NONE
        shape_id = check_msg(nifly.addBlock, file._handle, None, byref(buf),
                             parent.id if parent else NODEID_NONE)

        data_id = nifly.getCollCompressedMeshShapeDataID(file._handle, shape_id)
        if data_id < 0:
            shape = cls(file=file, id=shape_id, properties=buf, parent=parent)
            return shape, list(range(len(tris)))

        # Set materials array on the data block
        if len(unique_mats) > 0:
            mat_buf = (c_uint32 * len(unique_mats))(*unique_mats)
            check_msg(nifly.setCollCompressedMeshMaterials, file._handle,
                      data_id, mat_buf, None, len(unique_mats))

        # Build MOPP output IDs per input triangle
        output_ids = [0] * len(tris)

        # Set AABB
        all_x = [verts[i][0] for tri in tris for i in tri]
        all_y = [verts[i][1] for tri in tris for i in tri]
        all_z = [verts[i][2] for tri in tris for i in tri]
        bmin = (c_float * 3)(min(all_x), min(all_y), min(all_z))
        bmax = (c_float * 3)(max(all_x), max(all_y), max(all_z))
        check_msg(nifly.setCollCompressedMeshAABB, file._handle,
                  data_id, bmin, bmax)

        # Process each chunk
        for chunk_idx, face_group in enumerate(groups):
            chunk_tris = [tris[fi] for fi in face_group]

            # Collect unique vertices used by this chunk
            used_vert_set = set()
            for a, b, c in chunk_tris:
                used_vert_set.update((a, b, c))
            used_verts = sorted(used_vert_set)
            global_to_local = {g: l for l, g in enumerate(used_verts)}

            # Remap tris to local indices
            local_tris = [(global_to_local[a], global_to_local[b], global_to_local[c])
                          for a, b, c in chunk_tris]

            # Quantize vertices
            local_verts = [verts[g] for g in used_verts]
            if local_verts:
                tx = min(v[0] for v in local_verts)
                ty = min(v[1] for v in local_verts)
                tz = min(v[2] for v in local_verts)
            else:
                tx = ty = tz = 0.0

            # Check spatial extent fits in uint16 quantization (max 65.535 units)
            if local_verts:
                extent = max(
                    max(v[a] for v in local_verts) - min(v[a] for v in local_verts)
                    for a in range(3))
                if extent > 65.535:
                    log.warning(
                        f"Collision chunk {chunk_idx} spans {extent:.1f} Havok units "
                        f"(max 65.535); vertices will be clamped")

            quant_verts = []
            for x, y, z in local_verts:
                qx = max(0, min(65535, round((x - tx) * 1000.0)))
                qy = max(0, min(65535, round((y - ty) * 1000.0)))
                qz = max(0, min(65535, round((z - tz) * 1000.0)))
                quant_verts.extend([qx, qy, qz])

            # Build triangle strips
            strips, leftovers = stripify(local_tris)

            # Build indices array: strip indices first, then flat leftover indices
            indices = []
            strip_lengths = []
            for strip in strips:
                strip_lengths.append(len(strip))
                indices.extend(strip)
            for a, b, c in leftovers:
                indices.extend([a, b, c])

            # Add chunk via DLL
            translation_buf = (c_float * 4)(tx, ty, tz, 0.0)
            vert_buf = (c_uint16 * len(quant_verts))(*quant_verts)
            idx_buf = (c_uint16 * len(indices))(*indices)
            strip_buf = (c_uint16 * len(strip_lengths))(*strip_lengths) if strip_lengths else None
            # Determine material index for this chunk
            chunk_mat_idx = 0
            if face_materials:
                chunk_mat = face_materials[face_group[0]]
                chunk_mat_idx = mat_to_idx.get(chunk_mat, 0)
            check_msg(nifly.addCollCompressedMeshChunk,
                      file._handle, data_id,
                      translation_buf,
                      vert_buf, len(local_verts),
                      idx_buf, len(indices),
                      strip_buf, len(strip_lengths),
                      chunk_mat_idx)

            # Compute output IDs for MOPP.
            # chunk_index is 1-based (0 is for bigTris).
            # tri_in_chunk = INDEX POSITION within the indices array, NOT
            # the sequential triangle number.  For strip triangle k in a
            # strip starting at index offset strip_start: tri_in_chunk =
            # strip_start + k.  For flat triangle k: flat_start + k*3.
            # output = ((chunk_idx+1) << bits_per_w_index) | (winding << bits_per_index) | tri_in_chunk
            local_tri_sets = [frozenset(lt) for lt in local_tris]
            idx_pos = 0  # current position in the indices array
            for strip in strips:
                for k in range(len(strip) - 2):
                    winding = k & 1
                    tri_in_chunk = idx_pos + k
                    oid = ((chunk_idx + 1) << bits_per_w_index) | (winding << bits_per_index) | tri_in_chunk
                    if k % 2 == 0:
                        tri_set = frozenset((strip[k], strip[k+1], strip[k+2]))
                    else:
                        tri_set = frozenset((strip[k], strip[k+2], strip[k+1]))
                    for gi, fi in enumerate(face_group):
                        if local_tri_sets[gi] == tri_set:
                            output_ids[fi] = oid
                            local_tri_sets[gi] = None  # prevent double-match
                            break
                idx_pos += len(strip)
            # Flat triangles: each occupies 3 index positions
            for li, (a, b, c) in enumerate(leftovers):
                tri_in_chunk = idx_pos + li * 3
                oid = ((chunk_idx + 1) << bits_per_w_index) | (0 << bits_per_index) | tri_in_chunk
                leftover_set = frozenset((a, b, c))
                for gi, fi in enumerate(face_group):
                    if local_tri_sets[gi] == leftover_set:
                        output_ids[fi] = oid
                        local_tri_sets[gi] = None
                        break

        shape = cls(file=file, id=shape_id, properties=buf, parent=parent)
        return shape, output_ids

    @property
    def vertices(self):
        if self._vertices is None:
            count = nifly.getCollCompressedMeshShapeVerts(
                self.file._handle, self.properties.dataID, None, 0)
            if count > 0:
                buf = (c_float * (count * 3))()
                nifly.getCollCompressedMeshShapeVerts(
                    self.file._handle, self.properties.dataID, buf, count)
                self._vertices = [(buf[i*3], buf[i*3+1], buf[i*3+2])
                                  for i in range(count)]
            else:
                self._vertices = []
        return self._vertices

    @property
    def triangles(self):
        if self._triangles is None:
            count = nifly.getCollCompressedMeshShapeTris(
                self.file._handle, self.properties.dataID, None, 0)
            if count > 0:
                buf = (c_uint32 * (count * 3))()
                nifly.getCollCompressedMeshShapeTris(
                    self.file._handle, self.properties.dataID, buf, count)
                self._triangles = [(buf[i*3], buf[i*3+1], buf[i*3+2])
                                   for i in range(count)]
            else:
                self._triangles = []
        return self._triangles

    @property
    def material_ids(self):
        """Return per-triangle HavokMaterial uint32, same order as triangles."""
        count = nifly.getCollCompressedMeshTriMaterials(
            self.file._handle, self.properties.dataID, None, 0)
        if count <= 0:
            return []
        buf = (c_uint32 * count)()
        nifly.getCollCompressedMeshTriMaterials(
            self.file._handle, self.properties.dataID, buf, count)
        return list(buf)


class bhkConstraint(NiObject):
    buffer_type = PynBufferTypes.bhkRagdollConstraintBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkRagdollConstraintBuf(values)
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._entities = None

    @property
    def entities(self):
        if self._entities: return self._entities

        buf = (c_uint32 * self.properties.entityCount)()
        nifly.getRagdollEntities(
            self.file._handle, self.id, byref(buf), self.properties.entityCount)
        self._entities = []
        for constr_id in buf:
            self._entities.append(bhkWorldObject(file=self.file, id=constr_id, parent=self))
        
        return self._entities       


class bhkWorldObject(NiObject):
    @classmethod
    def getbuf(cls, values=None):
        assert False, "bhkWorldObject should never be instantiated directly."

    @classmethod
    def get_buffer(cls, bodytype, values=None):
        return NiObject.block_types[bodytype].getbuf(values=values)

    @classmethod
    def New(cls, objtype=None, id=NODEID_NONE, file=None, parent=None, properties=None):
        if properties:
            objtype = cls._buftype_name(properties.bufType)
        elif not objtype:
            objtype = dll_string(nifly.getBlockname, file._handle, id)
        # try:
        if id == NODEID_NONE:
            id = nifly.addBlock(
                file._handle, 
                None, 
                byref(properties), 
                parent.id if parent else None)
        return file.read_node(id=id, parent=parent, properties=properties)

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._shape = None
        self._constraints = None

    @property 
    def constraints(self):
        if self._constraints: return self._constraints

        buf = (c_uint32 * self.properties.constraintCount)()
        nifly.getRigidBodyConstraints(
            self.file._handle, self.id, byref(buf), self.properties.constraintCount)
        self._constraints = []
        for constr_id in buf:
            self._constraints.append(bhkConstraint(file=self.file, id=constr_id, parent=self))
        
        return self._constraints

    @property
    def shape(self):
        if not self._shape:
            shape_index =self.properties.shapeID
            self._shape = bhkShape.New(
                id=shape_index, file=self.file, parent=self)
        return self._shape

    def add_shape(self, properties, vertices=None, normals=None, transform=None):
        """ Create collision shape 
            bhkConvexVerticesShape - vertices can be vectors of 3 points. Normals must be 
                vectors of 4 elements: x, y, z (setting direction), and w (length)
            bhkBoxShape & others - All data passed in through the properties
        """
        return self.file.add_shape(properties=properties, parent=self, 
                                   vertices=vertices, normals=normals, transform=transform)


class bhkRigidBody(bhkWorldObject):
    buffer_type = PynBufferTypes.bhkRigidBodyBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkRigidBodyProps(values)


class bhkRigidBodyT(bhkRigidBody):
    buffer_type = PynBufferTypes.bhkRigidBodyTBufType

    @classmethod
    def getbuf(cls, values=None):
        buf = bhkRigidBodyProps(values)
        buf.bufType = PynBufferTypes.bhkRigidBodyTBufType
        return buf


class bhkSimpleShapePhantom(bhkWorldObject):
    buffer_type = PynBufferTypes.bhkSimpleShapePhantomBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkSimpleShapePhantomBuf(values)


class NiCollisionObject(NiObject):
    """Represents various collision objects."""
    buffer_type = PynBufferTypes.NiCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)

    @classmethod
    def New(cls, 
            collisiontype=None, id=NODEID_NONE, file=None, parent=None, 
            properties=None):
        if properties:
            collisiontype = cls._buftype_name(properties.bufType)
        elif not collisiontype:
            collisiontype = dll_string(nifly.getBlockname, file._handle, id)
        try:
            if id == NODEID_NONE:
                id = nifly.addBlock(
                    file._handle, 
                    None, 
                    byref(properties), 
                    parent.id if parent else None)
            return file.read_node(id=id, parent=parent, properties=properties)
        except Exception:
            return None

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._body = None

    @property
    def flags(self):
        """ Return the collision object flags """
        return self.properties.flags

    @property
    def target(self):
        """ Return the node that is the target of the collision object """
        targ = nifly.getCollTarget(self.file._handle, self._handle)
        return self.file.nodeByHandle(targ)

    @property
    def body(self):
        """ Return the collision body object """
        if not self._body:
            if self.properties.bodyID != NODEID_NONE:
                self._body = bhkWorldObject.New(id=self.properties.bodyID, file=self.file, parent=self)
        return self._body

    def add_body(self, properties):
        """ Create a rigid body for this collision object """
        # rb_index = check_id(nifly.addBlock,
        #     self.file._handle, None, byref(properties), self.id)
        self._body = bhkWorldObject.New(file=self.file, parent=self, properties=properties)
        return self._body


class bhkPhysicsSystem(NiObject):
    """FO4 native-physics collision data — wraps a raw Havok packfile blob."""

    buffer_type = PynBufferTypes.bhkPhysicsSystemBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        # Skip getNodeByID — bhkPhysicsSystem data is accessed directly via block id.
        self._handle = handle
        self._controller = None
        self.file = file
        self.id = id
        self._parent = parent
        self._properties = properties
        self._blockname = None

    @classmethod
    def getbuf(cls, values=None):
        return bhkPhysicsSystemBuf(values)

    @property
    def data(self) -> bytes:
        """Return the raw Havok packfile bytes stored in this block.
        Returns b"" if the DLL functions are not yet available.
        """
        if nifly.getPhysicsSystemDataLen is None:
            return b""
        n = nifly.getPhysicsSystemDataLen(self.file._handle, self.id)
        if n <= 0:
            return b""
        buf = (c_char * n)()
        nifly.getPhysicsSystemData(self.file._handle, self.id, buf, n)
        return bytes(buf.raw)

    def write_data(self, data: bytes):
        """Write raw Havok packfile bytes into this block."""
        if nifly.setPhysicsSystemData is None:
            raise RuntimeError("setPhysicsSystemData not available in this DLL version")
        nifly.setPhysicsSystemData(self.file._handle, self.id, data, len(data))

    @classmethod
    def New(cls, file, data: bytes = None, shapes=None, verts=None, faces=None, parent=None):
        """Create a new bhkPhysicsSystem block in *file*.

        Pass one of:
          *data*   — raw Havok packfile bytes
          *shapes* — List[CollisionShape] from bhk_autounpack; packed via pack_shapes()
          *verts* + *faces* — raw geometry; packed via pack_convex_polytope()
        """
        if data is None:
            if shapes is not None:
                from ..bhk_autopack import pack_shapes
                data = pack_shapes(shapes)
            else:
                from ..bhk_autopack import pack_convex_polytope
                data = pack_convex_polytope(verts, faces)
        buf = bhkPhysicsSystemBuf()
        buf.dataSize = len(data)
        id = check_msg(nifly.addBlock,
                       file._handle, None, byref(buf),
                       parent.id if parent else NODEID_NONE)
        ps = cls(file=file, id=id, properties=buf, parent=parent)
        ps.write_data(data)
        return ps

    @property
    def geometry(self):
        """Return a list of CollisionShape objects decoded from the Havok packfile.

        Each CollisionShape has:
          shape_type: str — "polytope", "compressed_mesh", or "compound"
          name: str — suggested Blender object name
          transform: Optional[BodyTransform] — body position/rotation (None = identity)
          verts: List[Vert3] — (x, y, z) float tuples in Havok space
          faces: List[Face] — vertex index tuples (empty for compound shapes)
          convex_radius: float — Minkowski expansion radius (0.0 for mesh/compound)
          children: List[CollisionShape] — non-empty only for compound shapes
        """
        from ..bhk_autounpack import parse_bytes
        return parse_bytes(self.data)


class bhkNPCollisionObject(NiCollisionObject):
    buffer_type = PynBufferTypes.bhkNPCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkNPCollisionObjectBuf(values)

    @property
    def physics_system(self) -> bhkPhysicsSystem:
        """Return the bhkPhysicsSystem block referenced by this collision object."""
        data_id = self.properties.dataID
        if data_id == NODEID_NONE:
            return None
        return self.file.read_node(id=data_id)

    @property
    def body_id(self) -> int:
        """Return the body index within the physics system."""
        return self.properties.bodyID


class bhkNiCollisionObject(NiCollisionObject):
    buffer_type = PynBufferTypes.bhkNiCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)


class bhkCollisionObject(bhkNiCollisionObject):
    buffer_type = PynBufferTypes.bhkCollisionObjectBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkCollisionObjectBuf(values)


class bhkPCollisionObject(bhkNiCollisionObject):
    buffer_type = PynBufferTypes.bhkPCollisionObjectBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkNiCollisionObjectBuf(values)


class bhkSPCollisionObject(bhkPCollisionObject):
    buffer_type = PynBufferTypes.bhkSPCollisionObjectBufType
    @classmethod
    def getbuf(cls, values=None):
        return bhkSPCollisionObjectBuf(values)


class bhkBlendCollisionObject(bhkCollisionObject):
    buffer_type = PynBufferTypes.bhkBlendCollisionObjectBufType

    @classmethod
    def getbuf(cls, values=None):
        return bhkBlendCollisionObjectBuf(values)


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .base import (check_msg, dll_string)  # noqa: E402
