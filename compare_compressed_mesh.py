"""Compare bhkCompressedMeshShape and bhkCompressedMeshShapeData between two NIF files."""
import sys
import os

os.environ['PYNIFLY_DEV_ROOT'] = 'c:/Modding'
sys.path.insert(0, 'c:/Modding/PyNifly/io_scene_nifly')

from ctypes import create_string_buffer, byref, c_float, c_uint16, c_uint32
from pyn.pynifly import NifFile
from pyn.niflydll import nifly
from pyn.nifdefs import bhkCompressedMeshShapeBuf

INPUT = 'c:/Modding/PyNifly/tests/tests/SkyrimSE/dockcorsol01.nif'
OUTPUT = 'c:/Modding/PyNifly/tests/tests/Out/TEST_COLLISION_MOPP_MATERIALS.nif'


def get_blockname(handle, block_id):
    buf = create_string_buffer(128)
    nifly.getBlockname(handle, block_id, buf, 128)
    return buf.value.decode('utf-8')


def find_blocks_by_type(nif, target_type):
    """Walk all blocks by ID to find ones matching target_type."""
    results = []
    block_id = 0
    while True:
        name = get_blockname(nif._handle, block_id)
        if not name:
            break
        if name == target_type:
            results.append(block_id)
        block_id += 1
    return results


def print_compressed_mesh_shape_props(nif, shape_id, label):
    """Print bhkCompressedMeshShape buffer properties."""
    buf = bhkCompressedMeshShapeBuf()
    rc = nifly.getBlock(nif._handle, shape_id, byref(buf))
    print(f"\n=== {label}: bhkCompressedMeshShape (block {shape_id}) ===")
    print(f"  bufSize   = {buf.bufSize}")
    print(f"  bufType   = {buf.bufType}")
    print(f"  radius    = {buf.radius}")
    print(f"  dataID    = {buf.dataID}")
    return buf.dataID


def print_compressed_mesh_data_info(nif, data_id, label):
    """Print bhkCompressedMeshShapeData info from DLL functions."""
    print(f"\n=== {label}: bhkCompressedMeshShapeData (block {data_id}) ===")
    blockname = get_blockname(nif._handle, data_id)
    print(f"  blockname = {blockname}")

    # Get vertices
    if nifly.getCollCompressedMeshShapeVerts is not None:
        count = nifly.getCollCompressedMeshShapeVerts(nif._handle, data_id, None, 0)
        print(f"  vertex count = {count}")
        if count > 0:
            buf = (c_float * (count * 3))()
            nifly.getCollCompressedMeshShapeVerts(nif._handle, data_id, buf, count)
            verts = [(buf[i*3], buf[i*3+1], buf[i*3+2]) for i in range(count)]
            print(f"  first 5 verts = {verts[:5]}")
            if count > 5:
                print(f"  last 5 verts  = {verts[-5:]}")
            # Compute bounding box
            xs = [v[0] for v in verts]
            ys = [v[1] for v in verts]
            zs = [v[2] for v in verts]
            print(f"  bounds min = ({min(xs):.6f}, {min(ys):.6f}, {min(zs):.6f})")
            print(f"  bounds max = ({max(xs):.6f}, {max(ys):.6f}, {max(zs):.6f})")
    else:
        print("  [getCollCompressedMeshShapeVerts not available]")

    # Get triangles
    if nifly.getCollCompressedMeshShapeTris is not None:
        count = nifly.getCollCompressedMeshShapeTris(nif._handle, data_id, None, 0)
        print(f"  triangle count = {count}")
        if count > 0:
            buf = (c_uint16 * (count * 3))()
            nifly.getCollCompressedMeshShapeTris(nif._handle, data_id, buf, count)
            tris = [(buf[i*3], buf[i*3+1], buf[i*3+2]) for i in range(count)]
            print(f"  first 5 tris = {tris[:5]}")
            if count > 5:
                print(f"  last 5 tris  = {tris[-5:]}")
    else:
        print("  [getCollCompressedMeshShapeTris not available]")

    # Get per-triangle materials
    if nifly.getCollCompressedMeshTriMaterials is not None:
        count = nifly.getCollCompressedMeshTriMaterials(nif._handle, data_id, None, 0)
        print(f"  tri material count = {count}")
        if count > 0:
            buf = (c_uint32 * count)()
            nifly.getCollCompressedMeshTriMaterials(nif._handle, data_id, buf, count)
            mats = list(buf)
            unique_mats = sorted(set(mats))
            print(f"  unique materials = {unique_mats}")
            print(f"  material distribution = {{{', '.join(f'{m}: {mats.count(m)}' for m in unique_mats)}}}")
            print(f"  first 10 tri materials = {mats[:10]}")
    else:
        print("  [getCollCompressedMeshTriMaterials not available]")


def analyze_file(filepath, label):
    print(f"\n{'='*70}")
    print(f"FILE: {label}")
    print(f"  {filepath}")
    print(f"{'='*70}")

    nif = NifFile(filepath)
    print(f"  Game: {nif.game}")

    # List all blocks
    print(f"\n  All blocks:")
    block_id = 0
    while True:
        name = get_blockname(nif._handle, block_id)
        if not name:
            break
        print(f"    [{block_id}] {name}")
        block_id += 1

    # Find bhkCompressedMeshShape blocks
    cms_ids = find_blocks_by_type(nif, 'bhkCompressedMeshShape')
    for sid in cms_ids:
        data_id = print_compressed_mesh_shape_props(nif, sid, label)
        if data_id != 0xFFFFFFFF:
            print_compressed_mesh_data_info(nif, data_id, label)

    # Also check bhkMoppBvTreeShape
    mopp_ids = find_blocks_by_type(nif, 'bhkMoppBvTreeShape')
    for mid in mopp_ids:
        from pyn.nifdefs import bhkMoppBvTreeShapeBuf
        buf = bhkMoppBvTreeShapeBuf()
        nifly.getBlock(nif._handle, mid, byref(buf))
        print(f"\n=== {label}: bhkMoppBvTreeShape (block {mid}) ===")
        print(f"  bufSize = {buf.bufSize}")
        print(f"  bufType = {buf.bufType}")
        print(f"  shapeID = {buf.shapeID}")

        # MOPP data
        if nifly.getCollMoppCodeLen is not None:
            code_len = nifly.getCollMoppCodeLen(nif._handle, mid)
            print(f"  mopp code length = {code_len}")
            if code_len > 0 and nifly.getCollMoppCode is not None:
                from ctypes import c_uint8
                origin = (c_float * 3)()
                scale = c_float()
                code_buf = (c_uint8 * code_len)()
                nifly.getCollMoppCode(nif._handle, mid, origin, byref(scale), code_buf, code_len)
                print(f"  mopp origin = ({origin[0]:.6f}, {origin[1]:.6f}, {origin[2]:.6f})")
                print(f"  mopp scale  = {scale.value:.6f}")
                print(f"  mopp code first 20 bytes = {list(code_buf[:20])}")

    # Also print rigid body props if present
    rb_ids = find_blocks_by_type(nif, 'bhkRigidBody') + find_blocks_by_type(nif, 'bhkRigidBodyT')
    for rid in rb_ids:
        from pyn.nifdefs import bhkRigidBodyProps
        buf = bhkRigidBodyProps()
        nifly.getBlock(nif._handle, rid, byref(buf))
        rbtype = get_blockname(nif._handle, rid)
        print(f"\n=== {label}: {rbtype} (block {rid}) ===")
        for field_name, field_type in bhkRigidBodyProps._fields_:
            val = getattr(buf, field_name)
            if hasattr(val, '__len__'):
                val = list(val)
            print(f"  {field_name} = {val}")

    return nif


# Run
nif_in = analyze_file(INPUT, "INPUT")
nif_out = analyze_file(OUTPUT, "OUTPUT")

print("\n\nDone.")
