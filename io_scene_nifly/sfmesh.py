import os
import struct
import numpy

fn = r"C:\Modding\Starfield\Mods\00 Vanilla\geometries\0007a7819c3463d5c58d\b123dd7af0d766880cd7.mesh"
fn = r"C:\Modding\Starfield\Mods\00 Vanilla\geometries\000b141e334c1c8dd7f2\4b72f297733c0f19e844.mesh"

# Male? 
fn = r"C:\Modding\Starfield\Mods\00 Vanilla\geometries\f0fa5a7c0787ddca3d06\1cea3ab2df14cc2a75ca.mesh"

# Has 414 verts, has colors
fn = r"C:\Modding\Starfield\Mods\00 Vanilla\geometries\000b141e334c1c8dd7f2\4b72f297733c0f19e844.mesh"


def HalfToFloat(h):
    s = int((h >> 15) & 0x00000001)     # sign
    e = int((h >> 10) & 0x0000001f)     # exponent
    f = int(h &         0x000003ff)     # fraction

    if e == 0:
       if f == 0:
          return int(s << 31)
       else:
          while not (f & 0x00000400):
             f <<= 1
             e -= 1
          e += 1
          f &= ~0x00000400
        #   print(s, e, f)
    elif e == 31:
       if f == 0:
          return int((s << 31) | 0x7f800000)
       else:
          return int((s << 31) | 0x7f800000 | (f << 13))

    e = e + (127 -15)
    f = f << 13

    ival = int((s << 31) | (e << 23) | f)
    b = struct.pack('I', ival)
    return struct.unpack('f', b)[0]


with open(fn, 'rb') as f:
    # buffer order is Position, Coord1, Coord2, Color, Normal, Tangent, Weight.
    buf = f.read(4)
    version = struct.unpack('<I', buf)[0]

    tris = []
    buf = f.read(4)
    trisize = struct.unpack('<I', buf)[0]
    for i in range(0, trisize, 3):
        buf = f.read(6)
        triple = struct.unpack('<HHH', buf)
        tris.append(triple)

    dt_double = numpy.dtype("<f2, <f2")
    dt_triple = numpy.dtype("<f2, <f2, <f2")
    dt_quad = numpy.dtype("<f2, <f2, <f2, <f2")
    # byte unkBytes1[3];
    unk1 = f.read(3)
    # uint flags;
    buf = f.read(4)
    flags = struct.unpack('<I', buf)
    # byte unkByte1;
    unk2 = f.read(1)

    # uint numVerts1;
    buf = f.read(4)
    numverts = struct.unpack('<I', buf)[0]

    # byte vertexBuffer[numVerts1*6];
    buf = f.read(numverts * 6)
    verts = numpy.frombuffer(buf, dtype=dt_triple)

    # verts2 = []
    # intverts = struct.iter_unpack("<HHH", buf)
    # for x, y, z in intverts:
    #    v = [HalfToFloat(x), HalfToFloat(y), HalfToFloat(z)]
    #    verts2.append(v)

    # uint numVerts2;
    numcoords = struct.unpack('<I', f.read(4))[0]
    # byte coordsBuffer[numVerts2*4];
    coords = numpy.frombuffer(f.read(numcoords * 4), dtype=dt_double)

    numcoords2 = struct.unpack('<I', f.read(4))[0]
    coords2 = numpy.frombuffer(f.read(numcoords2 * 4), dtype=dt_double)

    numcolors = struct.unpack('<I', f.read(4))[0]
    buf = f.read(numcolors * 8)
    colors = numpy.frombuffer(buf, "III")

    numsomething = struct.unpack('<I', f.read(4))[0]
    


assert numcoords == numverts, f"Vert count consistent"
print(tris[0])
print(tris[-1])
print("--verts--")
for v in verts[0:10]:
    print(f"{v}")
print("--coords--")
for c in coords[0:10]:
    print(c)

print("Done")