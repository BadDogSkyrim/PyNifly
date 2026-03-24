"""Dump full collision structure of a Skyrim SE NIF file.

Usage: python dump_collision.py <nif_path>
"""
import sys, os, struct

# Ensure the pyn package is importable without changing cwd
_script_dir = os.path.dirname(os.path.abspath(__file__))
_pyn_parent = os.path.join(_script_dir, '..')
if _pyn_parent not in sys.path:
    sys.path.insert(0, _pyn_parent)

from pyn.pynifly import NifFile
from pyn.niflydll import nifly
from pyn.mopp_compiler import disassemble_mopp
from ctypes import c_float, c_uint16, c_uint32, c_int, byref, create_string_buffer


def dump_nif(path):
    f = NifFile(path)
    print(f"=== {os.path.basename(path)} ===")
    print(f"Game: {f.game}")
    print(f"Root: {f.rootNode.name} ({f.rootNode.blockname})")

    # Block listing
    print("\nBlocks:")
    for i in range(50):
        try:
            buf = create_string_buffer(256)
            nifly.getBlockname(f._handle, i, buf, 256)
            name = buf.value.decode('utf-8')
            if not name: break
            print(f"  {i}: {name}")
        except:
            break

    co = f.rootNode.collision_object
    if not co:
        print("\nNo collision object")
        return

    # Collision object
    cop = co.properties
    print(f"\nbhkCollisionObject: target={cop.targetID} body={cop.bodyID} flags={cop.flags}")

    # Rigid body
    body = co.body
    bp = body.properties
    print(f"\n{body.blockname}:")
    print(f"  rotation: [{bp.rotation[0]:.6f}, {bp.rotation[1]:.6f}, {bp.rotation[2]:.6f}, {bp.rotation[3]:.6f}]")
    print(f"  translation: [{bp.translation[0]:.6f}, {bp.translation[1]:.6f}, {bp.translation[2]:.6f}]")
    print(f"  collisionFilter_layer: {bp.collisionFilter_layer}")
    print(f"  broadPhaseType: {bp.broadPhaseType}")
    print(f"  collisionResponse: {bp.collisionResponse}")
    print(f"  motionSystem: {bp.motionSystem}")
    print(f"  qualityType: {bp.qualityType}")
    print(f"  mass: {bp.mass}")
    print(f"  friction: {bp.friction}")
    print(f"  restitution: {bp.restitution}")

    # Shape
    shape = body.shape
    print(f"\n{shape.blockname}:")
    print(f"  shapeID (child): {shape.properties.shapeID}")
    print(f"  buildType: {shape.properties.buildType}")

    # MOPP data
    md, origin, scale = shape.mopp_data
    print(f"  MOPP: {len(md)} bytes")
    print(f"  origin: ({origin[0]:.6f}, {origin[1]:.6f}, {origin[2]:.6f})")
    print(f"  scale (NIF field): {scale}")

    # Child shape
    child = shape.child
    cp = child.properties
    print(f"\n{child.blockname}:")
    print(f"  radius: {cp.radius}")
    print(f"  error: {cp.error}")
    print(f"  bitsPerIndex: {cp.bitsPerIndex}")
    print(f"  bitsPerWIndex: {cp.bitsPerWIndex}")
    print(f"  maskIndex: {cp.maskIndex}")
    print(f"  maskWIndex: {cp.maskWIndex}")
    print(f"  materialType: {cp.materialType}")
    print(f"  userData: {cp.userData}")
    print(f"  unkFloat: {cp.unkFloat}")

    # Geometry
    verts = child.vertices
    tris = child.triangles
    print(f"\nGeometry: {len(verts)} verts, {len(tris)} tris")
    if verts:
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        print(f"  Bounds: ({min(xs):.4f},{min(ys):.4f},{min(zs):.4f}) to ({max(xs):.4f},{max(ys):.4f},{max(zs):.4f})")

    # Materials
    data_id = cp.dataID
    nm = nifly.getCollCompressedMeshTriMaterials(f._handle, data_id, None, 0)
    if nm > 0:
        mbuf = (c_uint32 * nm)()
        nifly.getCollCompressedMeshTriMaterials(f._handle, data_id, byref(mbuf), nm)
        mats = set(mbuf[i] for i in range(nm))
        print(f"  Materials: {mats}")

    # Chunks (using raw binary parse since we may not have chunk reader in DLL)
    print(f"\n--- Chunk details (raw binary parse) ---")
    _dump_chunks_binary(path)

    # MOPP disassembly
    print(f"\n--- MOPP disassembly ---")
    lines = disassemble_mopp(md, origin=origin)
    for line in lines:
        print(line)
    print(f"Total MOPP instructions: {len(lines)}")


def _dump_chunks_binary(path):
    """Parse bhkCompressedMeshShapeData from the raw NIF binary."""
    with open(path, 'rb') as fh:
        raw = fh.read()

    # Parse NIF header to find block offsets
    pos = 0
    while raw[pos:pos+1] != b'\n': pos += 1
    pos += 1
    struct.unpack_from('<I', raw, pos)[0]; pos += 4
    pos += 1; pos += 4
    num_blocks = struct.unpack_from('<I', raw, pos)[0]; pos += 4; pos += 4
    for _ in range(3):
        sl = raw[pos]; pos += 1; pos += sl
    nbt = struct.unpack_from('<H', raw, pos)[0]; pos += 2
    bts = []
    for i in range(nbt):
        tl = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        bts.append(raw[pos:pos+tl].decode()); pos += tl
    btis = [struct.unpack_from('<H', raw, pos + i*2)[0] for i in range(num_blocks)]
    pos += num_blocks * 2
    bsizes = [struct.unpack_from('<I', raw, pos + i*4)[0] for i in range(num_blocks)]
    pos += num_blocks * 4
    ns = struct.unpack_from('<I', raw, pos)[0]; pos += 4; pos += 4
    for i in range(ns):
        sl = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        if sl != 0xFFFFFFFF: pos += sl
    ng = struct.unpack_from('<I', raw, pos)[0]; pos += 4; pos += ng * 4
    hend = pos

    # Find bhkCompressedMeshShapeData block
    off = hend
    for i in range(num_blocks):
        if 'CompressedMeshShapeData' in bts[btis[i]]:
            data = raw[off:off+bsizes[i]]
            _parse_cmsd(data)
            return
        off += bsizes[i]
    print("  No bhkCompressedMeshShapeData block found")


def _parse_cmsd(data):
    """Parse and dump bhkCompressedMeshShapeData."""
    pos = 0
    bpi = struct.unpack_from('<I', data, pos)[0]; pos += 4
    bpwi = struct.unpack_from('<I', data, pos)[0]; pos += 4
    mwi = struct.unpack_from('<I', data, pos)[0]; pos += 4
    mi = struct.unpack_from('<I', data, pos)[0]; pos += 4
    err = struct.unpack_from('<f', data, pos)[0]; pos += 4
    bmin = struct.unpack_from('<4f', data, pos); pos += 16
    bmax = struct.unpack_from('<4f', data, pos); pos += 16
    weld_type = data[pos]; pos += 1
    mat_type = data[pos]; pos += 1

    print(f"  weldingType: {weld_type}")
    print(f"  materialType: {mat_type}")
    print(f"  AABB min: ({bmin[0]:.4f}, {bmin[1]:.4f}, {bmin[2]:.4f})")
    print(f"  AABB max: ({bmax[0]:.4f}, {bmax[1]:.4f}, {bmax[2]:.4f})")

    # mat32, mat16, mat8
    for arr_name in ['mat32', 'mat16', 'mat8']:
        n = struct.unpack_from('<I', data, pos)[0]; pos += 4
        vals = [struct.unpack_from('<I', data, pos + i*4)[0] for i in range(n)]
        pos += n * 4
        if n > 0:
            print(f"  {arr_name}: {vals}")

    # materials
    n = struct.unpack_from('<I', data, pos)[0]; pos += 4
    mats = []
    for i in range(n):
        m = struct.unpack_from('<I', data, pos)[0]; pos += 4
        l = struct.unpack_from('<I', data, pos)[0]; pos += 4
        mats.append((hex(m), l))
    print(f"  materials ({n}): {mats}")

    n = struct.unpack_from('<I', data, pos)[0]; pos += 4
    print(f"  namedMaterials: {n}")

    # transforms
    n_xf = struct.unpack_from('<I', data, pos)[0]; pos += 4
    print(f"  transforms: {n_xf}")
    for i in range(n_xf):
        t = struct.unpack_from('<4f', data, pos); pos += 16
        q = struct.unpack_from('<4f', data, pos); pos += 16
        print(f"    [{i}] trans=({t[0]:.4f},{t[1]:.4f},{t[2]:.4f},{t[3]:.4f}) rot=({q[0]:.4f},{q[1]:.4f},{q[2]:.4f},{q[3]:.4f})")

    # bigVerts
    n_bv = struct.unpack_from('<I', data, pos)[0]; pos += 4
    print(f"  bigVerts: {n_bv}")
    pos += n_bv * 16

    # bigTris
    n_bt = struct.unpack_from('<I', data, pos)[0]; pos += 4
    print(f"  bigTris: {n_bt}")
    for i in range(n_bt):
        pos += 12  # 3 uint16 + uint32 + uint16 welding + uint16 xfIdx

    # chunks
    n_chunks = struct.unpack_from('<I', data, pos)[0]; pos += 4
    print(f"  chunks: {n_chunks}")

    for ci in range(n_chunks):
        tx = struct.unpack_from('<4f', data, pos); pos += 16
        mat_idx = struct.unpack_from('<I', data, pos)[0]; pos += 4
        ref = struct.unpack_from('<H', data, pos)[0]; pos += 2
        xf_idx = struct.unpack_from('<H', data, pos)[0]; pos += 2

        nv = struct.unpack_from('<I', data, pos)[0]; pos += 4
        vert_data = [struct.unpack_from('<H', data, pos + i*2)[0] for i in range(nv)]
        pos += nv * 2

        ni = struct.unpack_from('<I', data, pos)[0]; pos += 4
        idx_data = [struct.unpack_from('<H', data, pos + i*2)[0] for i in range(ni)]
        pos += ni * 2

        ns = struct.unpack_from('<I', data, pos)[0]; pos += 4
        strip_data = [struct.unpack_from('<H', data, pos + i*2)[0] for i in range(ns)]
        pos += ns * 2

        nw = struct.unpack_from('<I', data, pos)[0]; pos += 4
        weld_data = [struct.unpack_from('<H', data, pos + i*2)[0] for i in range(nw)]
        pos += nw * 2

        num_verts = nv // 3
        n_strip_tris = sum(max(0, s-2) for s in strip_data)
        flat_start = sum(strip_data)
        n_flat = (ni - flat_start) // 3
        total_tris = n_strip_tris + n_flat

        print(f"\n  Chunk {ci}:")
        print(f"    translation: ({tx[0]:.4f}, {tx[1]:.4f}, {tx[2]:.4f})")
        print(f"    matIndex: {mat_idx}  ref: {ref}  transformIndex: {xf_idx}")
        print(f"    verts: {num_verts}  indices: {ni}  strips: {strip_data}  tris: {total_tris}")
        print(f"    welding: {nw} entries ({sum(1 for w in weld_data if w != 0)} nonzero)")

        # Dump triangles
        print(f"    Triangles:")
        tri_idx = 0
        idx = 0
        for si, sl in enumerate(strip_data):
            for k in range(sl - 2):
                if k & 1:
                    a, b, c = idx_data[idx+k], idx_data[idx+k+2], idx_data[idx+k+1]
                else:
                    a, b, c = idx_data[idx+k], idx_data[idx+k+1], idx_data[idx+k+2]

                # Dequantize to show world coords
                def dq(vi, axis):
                    return vert_data[vi*3+axis] / 1000.0 + tx[axis]
                wa = (dq(a,0), dq(a,1), dq(a,2))
                wb = (dq(b,0), dq(b,1), dq(b,2))
                wc = (dq(c,0), dq(c,1), dq(c,2))
                w = weld_data[tri_idx] if tri_idx < nw else 0
                we = (w & 0x1F, (w>>5)&0x1F, (w>>10)&0x1F)
                idx_position = idx + k  # index position = strip_start + k
                winding = k & 1
                oid = (1 << 18) | (winding << 17) | idx_position
                print(f"      tri {tri_idx} (strip {si}, k={k}): [{a},{b},{c}] idx_pos={idx_position} oid=0x{oid:08X} weld=0x{w:04X}{we}  v0=({wa[0]:.3f},{wa[1]:.3f},{wa[2]:.3f})")
                tri_idx += 1
            idx += sl

        # Flat triangles
        flat_start = idx
        flat_idx = 0
        for i in range(idx, ni - 2, 3):
            a, b, c = idx_data[i], idx_data[i+1], idx_data[i+2]
            def dq(vi, axis):
                return vert_data[vi*3+axis] / 1000.0 + tx[axis]
            wa = (dq(a,0), dq(a,1), dq(a,2))
            w = weld_data[tri_idx] if tri_idx < nw else 0
            we = (w & 0x1F, (w>>5)&0x1F, (w>>10)&0x1F)
            idx_position = flat_start + flat_idx * 3
            oid = (1 << 18) | idx_position
            print(f"      tri {tri_idx} (flat): [{a},{b},{c}] idx_pos={idx_position} oid=0x{oid:08X} weld=0x{w:04X}{we}  v0=({wa[0]:.3f},{wa[1]:.3f},{wa[2]:.3f})")
            tri_idx += 1
            flat_idx += 1

    # numConvexPieceA
    if pos < len(data):
        ncp = struct.unpack_from('<I', data, pos)[0]; pos += 4
        print(f"\n  numConvexPieceA: {ncp}")

    print(f"\n  Parsed {pos}/{len(data)} bytes")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python dump_collision.py <nif_path>")
        sys.exit(1)
    dump_nif(sys.argv[1])
