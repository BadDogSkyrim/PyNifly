""" Simple tools doing mesh operations to support import/export"""

from math import asin, acos, atan2, pi, sin, cos, radians, sqrt
import logging
import re

log = logging.getLogger("pynifly")

def vector_normalize(v):
    d = sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if d == 0:
        d = 1.0
    return (v[0]/d, v[1]/d, v[2]/d)

class RotationMatrix:
    """ Rotation matrix with handy functions """
    def __init__(self, val=None):
        if val is None:
            self.matrix = [(1,0,0),(0,1,0),(0,0,1)]
        else:
            if isinstance(val, RotationMatrix):
                self.matrix = val.copy().matrix
            else:
                self.matrix = val

    def __repr__(self):
        val = ""
        for rw in self.matrix:
            val = val + "[{0:.4f}, {1:.4f}, {2:.4f}] ".format(rw[0], rw[1], rw[2])
        return val        

    def __str__(self):
        val = ""
        for rw in self.matrix:
            val = val + "[{0:.4f}, {1:.4f}, {2:.4f}]\n".format(rw[0], rw[1], rw[2])
        return val        

    def __eq__(self, other):
        for i in range(0, 2):
            for j in range(0, 2):
                if round(self.matrix[i][j], 4) != round(other.matrix[i][j], 4):
                    return False
        return True

    def from_euler_ypr(yaw, pitch, roll):
        """ Create new rotation matrix from Euler data
            This transformation found in Nifly code, not sure if it's useful """
        ch = cos(yaw);
        sh = sin(yaw);
        cp = cos(pitch);
        sp = sin(pitch);
        cb = cos(roll);
        sb = sin(roll);

        rot = [[0,0,0]] * 3
        rot[0][0] = ch * cb + sh * sp * sb;
        rot[0][1] = sb * cp;
        rot[0][2] = -sh * cb + ch * sp * sb;

        rot[1][0] = -ch * sb + sh * sp * cb;
        rot[1][1] = cb * cp;
        rot[1][2] = sb * sh + ch * sp * cb;

        rot[2][0] = sh * cp;
        rot[2][1] = -sp;
        rot[2][2] = ch * cp;
        return RotationMatrix(rot)

    def from_euler(xrot, yrot, zrot):
        """ Convert from blender-style euler anges (in degrees) to a matrix.
            Calculation from wikipedia (where else?)
            """
        c1 = cos(radians(xrot))
        c2 = cos(radians(yrot))
        c3 = cos(radians(zrot))
        s1 = sin(radians(xrot))
        s2 = sin(radians(yrot))
        s3 = sin(radians(zrot))
        
        res = [(c2 * c3,                   -s2,         c2 * s3),
               (s1 * s3 + c1 * c3 * s2,     c1 * c2,    c1 * s2 * s3 - c3 * s1),
               (c3 * s1 * s2 - c1 * s3,     c2 * s1,    c1 * c3 + s1 * s2 * s3)
               ]
        return RotationMatrix(res)

    def from_vector(vec, rotation_angle=None):
        """ Create a rotation matrix from the given vector.
            Rotation angle can be provided or given by the Length of the vector 
        """
        if rotation_angle is None:
            angle = sqrt(vec[0]**2 + vec[1]**2 + vec[2]**2)
        else:
            angle = rotation_angle
        cosang = cos(angle)
        sinang = sin(angle)
        onemcosang = None # one minus cosang
        if cosang > 0.5:
            onemcosang = (sinang**2)/(1+cosang)
        else:
            onemcosang = 1 - cosang;
        if angle == 0:
            n = (1, 0, 0)
        else:
            n = (vec[0]/angle, vec[1]/angle, vec[2]/angle)
        m = RotationMatrix([
                (n[0]*n[0] * onemcosang + cosang, 
                 n[0]*n[1] * onemcosang + n[2] * sinang, 
                 n[2]*n[0] * onemcosang - n[1] * sinang),
                (n[0]*n[1] * onemcosang - n[2] * sinang, 
                 n[1]*n[1] * onemcosang + cosang, 
                 n[1]*n[2] * onemcosang + n[0] * sinang),
                (n[2]*n[0] * onemcosang + n[1] * sinang,
                 n[1]*n[2] * onemcosang - n[0] * sinang,
                 n[2]*n[2] * onemcosang + cosang)])
        return m
                
	        #double angle = std::sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
	        #double cosang = std::cos(angle);
	        #double sinang = std::sin(angle);
	        #double onemcosang = NAN; // One minus cosang
	        #// Avoid loss of precision from cancellation in calculating onemcosang
	        #if (cosang > .5)
		       # onemcosang = sinang * sinang / (1 + cosang);
	        #else
		       # onemcosang = 1 - cosang;
	        #Vector3 n = angle != 0 ? v / angle : Vector3(1, 0, 0);
	        #Matrix3 m;
	        #m[0][0] = n.x * n.x * onemcosang + cosang;
	        #m[1][1] = n.y * n.y * onemcosang + cosang;
	        #m[2][2] = n.z * n.z * onemcosang + cosang;
	        #m[0][1] = n.x * n.y * onemcosang + n.z * sinang;
	        #m[1][0] = n.x * n.y * onemcosang - n.z * sinang;
	        #m[1][2] = n.y * n.z * onemcosang + n.x * sinang;
	        #m[2][1] = n.y * n.z * onemcosang - n.x * sinang;
	        #m[2][0] = n.z * n.x * onemcosang + n.y * sinang;
	        #m[0][2] = n.z * n.x * onemcosang - n.y * sinang;

    def euler(self):
        """ Return the rotation matrix as Euler XYZ, in radians """
        rm = self.matrix
        if rm[0][2] < 1.0:
            if rm[0][2] > -1.0:
                y = atan2(-rm[1][2], rm[2][2])
                p = asin(rm[0][2])
                r = atan2(-rm[0][1], rm[0][0])
            else:
                y = atan2(rm[1][0], rm[1][1])
                p = pi/2.0
                r = 0.0
        else:
            y = atan2(rm[1][0], rm[1][1])
            p = pi/2.0
            r = 0.0
        return (y, p, r)

    def euler_deg(self):
        """ Return the rotation matrix as Euler XYZ, in degrees """
        angles = self.euler()
        return (angles[0] * 180.0/pi, angles[1] * 180.0/pi, angles[2] * 180.0/pi)

    def rotation_vector(self):
        """ Return a rotation vector from the matrix """
        m = self.matrix
        cosang = (m[0][0] + m[1][1] + m[2][2] - 1) * 0.5
        if cosang > 0.5:
            v = (m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0])
            sin2ang = sqrt(v[0]**2 + v[1]**2 + v[2]**2)
            if sin2ang == 0:
                return (0, 0, 0)
            adj = asin(sin2ang * 0.5) / sin2ang
            return (v[0] * adj, v[1] * adj, v[2] * adj) 
        if cosang > -1:
            v = (m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0])
            v = vector_normalize(v)
            adj = acos(cosang)
            return (v[0] * adj, v[1] * adj, v[2] * adj)
        x = (m[0][0] - cosang) * 0.5;
        y = (m[1][1] - cosang) * 0.5;
        z = (m[2][2] - cosang) * 0.5;
        if x < 0.0: x = 0.0
        if y < 0.0: y = 0.0
        if z < 0.0: z = 0.0
        v = (sqrt(x), sqrt(y), sqrt(z))
        v = vector_normalize(v)
        if m[1][2] < m[2][1]:
            v = (-v[0], v[1], v[2])
        if m[2][0] < m[0][2]:
            v = (v[0], -v[1], v[2])
        if m[0][1] < m[1][0]:
            v = (v[0], v[1], -v[2])
        return (v[0] * pi, v[1] * pi, v[2] * pi)


    #double cosang = (m[0][0] + m[1][1] + m[2][2] - 1) * 0.5;
    #if (cosang > 0.5) {
    #	Vector3 v(m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0]);
    #	double sin2ang = v.length();
    #	if (sin2ang == 0)
    #		return Vector3(0, 0, 0);
    #	return v * (std::asin(sin2ang * 0.5) / sin2ang);
    #}
    #if (cosang > -1) {
    #	Vector3 v(m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0]);
    #	v.Normalize();
    #	return v * std::acos(cosang);
    #}
    #// cosang <= -1, sinang == 0
    #double x = (m[0][0] - cosang) * 0.5;
    #double y = (m[1][1] - cosang) * 0.5;
    #double z = (m[2][2] - cosang) * 0.5;

    #// Solve precision issues that would cause NaN
    #if (x < 0.0)
    #	x = 0.0;
    #if (y < 0.0)
    #	y = 0.0;
    #if (z < 0.0)
    #	z = 0.0;

	#Vector3 v(std::sqrt(x), std::sqrt(y), std::sqrt(z));
	#v.Normalize();

	#if (m[1][2] < m[2][1])
	#	v.x = -v.x;
	#if (m[2][0] < m[0][2])
	#	v.y = -v.y;
	#if (m[0][1] < m[1][0])
	#	v.z = -v.z;
	#return v * PI;

    
    def by_vector(self, vec):
        """ Cross product of rotation matrix with the given vector.
            Returns vector rotated by the matrix """
        rm = self.matrix
        return (vec[0]*rm[0][0] + vec[1]*rm[0][1] + vec[2]*rm[0][2],
                vec[0]*rm[1][0] + vec[1]*rm[1][1] + vec[2]*rm[1][2],
                vec[0]*rm[2][0] + vec[1]*rm[2][1] + vec[2]*rm[2][2])

    @property
    def determinant(self):
        rows = self.matrix
        return rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1]) \
            + rows[0][1] * (rows[1][2] * rows[2][0] - rows[1][0] * rows[2][2]) \
            + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])

    def copy(self):
        return RotationMatrix([self.matrix[0], self.matrix[1], self.matrix[2]])
    
    def multiply(self, other):
        y = other.matrix
        x = self.matrix
        new_mx = [[0] * len(y[0])] * len(x)
        for i in range(len(x)):
            for j in range(len(y[0])):
                for k in range(len(y)):
                    new_mx[i][j] += x[i][k] * y[k][j]

        new_mx = [ ( x[0][0]*y[0][0] + x[0][1]*y[1][0] + x[0][2]*y[2][0], 
                     x[0][0]*y[0][1] + x[0][1]*y[1][1] + x[0][2]*y[2][1],
                     x[0][0]*y[0][2] + x[0][1]*y[1][2] + x[0][2]*y[2][2]), 
                   ( x[1][0]*y[0][0] + x[1][1]*y[1][0] + x[1][2]*y[2][0],
                     x[1][0]*y[0][1] + x[1][1]*y[1][1] + x[1][2]*y[2][1],
                     x[1][0]*y[0][2] + x[1][1]*y[1][2] + x[1][2]*y[2][2]), 
                   ( x[2][0]*y[0][0] + x[2][1]*y[1][0] + x[2][2]*y[2][0],
                     x[2][0]*y[0][1] + x[2][1]*y[1][1] + x[2][2]*y[2][1],
                     x[2][0]*y[0][2] + x[2][1]*y[1][2] + x[2][2]*y[2][2])]
        return RotationMatrix(new_mx)


    def invert(self):
        det = self.determinant
        rows = self.matrix
        if det != 0.0:
            idet = 1 / det
            new_rm = [
                ((rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1]) * idet,
                 (rows[2][1] * rows[0][2] - rows[2][2] * rows[0][1]) * idet,
                 (rows[0][1] * rows[1][2] - rows[0][2] * rows[1][1]) * idet),
                ((rows[1][2] * rows[2][0] - rows[1][0] * rows[2][2]) * idet,
                 (rows[2][2] * rows[0][0] - rows[2][0] * rows[0][2]) * idet,
                 (rows[0][2] * rows[1][0] - rows[0][0] * rows[1][2]) * idet),
                ((rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0]) * idet,
                 (rows[2][0] * rows[0][1] - rows[2][1] * rows[0][0]) * idet,
                 (rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]) * idet)]
            return RotationMatrix(new_rm)
        else:
            print("Error: Rotation matrix cannot be inverted")
            return self.copy()


def uv_location(uv):
    """ Rounds UV location to eliminate floating point error """
    return (round(uv[0], 4), round(uv[1], 4))


def VNearEqual(v1, v2):
    return round(v1[0], 1) == round(v2[0], 1) and \
        round(v1[1], 1) == round(v2[1], 1) and \
        round(v1[2], 1) == round(v2[2], 1)


def vert_uv_key(vert_index, uv):
    return str(vert_index) + "_" + str(uv)


def mesh_split_by_uv(verts, norms, loops, uvmap, weights, morphdict):
    """Split a mesh represented by parameters and split verts if necessary because it
        (1) maps to 2 UV locations or (2) has split normals.
        verts = [(x, y, z), ...] vertex locations
        norms = [(x, y, z), ...] normals 1:1 with loops
        loops = [int, ...] blender-style loops--elements are indices into verts
        uvmap = [(u, v), ...] uvmap--matches 1:1 with loops
        weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts
        morphdict = {morph-name: [(x,y,z)...], ...} vertex list for each morph
    Returns
        verts = extended with additional verts where splits were required
        norms = not changed
        loops = modified to reference the new verts where needed
        uvmap = not changed
        weights = extended to match verts
    """
    # Walk the loops. If the associated UV puts the vert in a new location, dup the vert
    vert_uvs = [None] * len(verts) # found UV locations of verts
    vert_norms = [(0.0, 0.0, 0.0)] * len(verts) # found normals of verts
    change_table = {} # {old_vert_index: new_vert_index}
    for i, vert_idx in enumerate(loops):
        this_vert_loc = uv_location(uvmap[i])
        this_vert_norm = norms[i]
        if vert_uvs[vert_idx] is None:
            # Not given this vert a location yet
            vert_uvs[vert_idx] = this_vert_loc
            vert_norms[vert_idx] = this_vert_norm
        elif vert_uvs[vert_idx] != this_vert_loc: # or not VNearEqual(this_vert_norm, vert_norms[vert_idx]):
            # Found already at different location or with different normal
            #if vert_uvs[vert_idx] != this_vert_loc:
            #    log.debug(f"Splitting vert #{vert_idx}, loop #{i}: UV {[round(uv, 4) for uv in uvmap[i]]} != {[round(uv, 4) for uv in vert_uvs[vert_idx]]}")
            #else:
            #    log.debug(f"Splitting vert #{vert_idx}, loop #{i}: Norm {[round(n, 4) for n in this_vert_norm]} != {[round(n, 4) for n in vert_norms[vert_idx]]}")
            vert_key = vert_uv_key(vert_idx, this_vert_loc)
            if vert_key in change_table:
                #print("..found in change table at %d " % change_table[vert_key])
                loops[i] = change_table[vert_key]
            else:
                #print("..not found, creating new vert")
                new_index = len(verts)
                verts.append(verts[vert_idx])
                if weights:
                    weights.append(weights[vert_idx])
                for vlist in morphdict.values():
                    vlist.append(vlist[vert_idx])
                vert_uvs.append(this_vert_loc)
                loops[i] = new_index
                change_table[vert_key] = new_index

# ----------------------- Game-specific Skeleton Dictionaries ---------------------------

def blender_basename(n):
    m = re.match("(.+)\.\d+\Z", n)
    if m:
        return m[1]
    return n
    
class SkeletonBone:
    def __init__(self, blender_name, nif_name, parent=None):
        self.blender = blender_name
        self.nif = nif_name
        self.parent_name = parent
        self.parent = None

class BodyPart:
    def __init__(self, id, name, parent='', material=0):
        self.id = id
        self.name = name
        self.parentname = parent
        self.material = material
        if material == 0 and (id > 100 or id < 0):
            self.material = id

class BoneDict:
    def __init__(self, bone_list, morph_list, part_list, dismem_list=[]):
        self.byNif = {}
        self.byBlender = {}
        self.parts = {}
        self.dismem = {}
        for b in bone_list:
            self.byNif[b.nif] = b
            self.byBlender[b.blender] = b
        for b in bone_list:
            if b.parent_name in self.byBlender:
                b.parent = self.byBlender[b.parent_name]
        self.expressions = set(morph_list)
        for p in part_list:
            self.parts[p.name] = p
        for d in dismem_list:
            self.dismem[d.name] = d

    def blender_name(self, nif_name):
        if nif_name in self.byNif:
            return self.byNif[nif_name].blender
        else:
            return nif_name
    
    def nif_name(self, blender_name):
        if blender_name in self.byBlender:
            return self.byBlender[blender_name].nif
        else:
            return blender_name

    def bodypart(self, name):
        """ Look for 'name' in any of the bodyparts. Strip any trailing '.001'-type
            number before checking. """
        if name is None:
            return None
        name = blender_basename(name)
        if name in self.parts:
            return self.parts[name]
        if name in self.dismem:
            return self.dismem[name]
        return None

    def part_by_id(self, id):
        for bp in self.parts.values():
            if bp.id == id:
                return bp
        for bp in self.dismem.values():
            if bp.id == id:
                return bp
        return None

    def expression_filter(self, name_set):
        return name_set.intersection(self.expressions)

    def chargen_filter(self, candidates):
        """ Filter the given set down to only those that can be a chargen morph.
            Default is to keep everything.
            """
        return candidates

    def matches(self, boneset):
        """ Return count of entries in aList that match skeleton bones """
        return len(boneset.intersection(set(self.byBlender.keys()))) + \
            len(boneset.intersection(set(self.byNif.keys())))
        #return sum([(1 if v in self.byBlender else 0) for v in aList]) + \
        #        sum([(1 if v in self.byNif else 0) for v in aList])

fnvBones = [
    SkeletonBone('Bip01', 'Bip01', None),
    SkeletonBone('Bip01 NonAccum', 'Bip01 NonAccum', 'Bip01'),
    SkeletonBone('Bip01 Pelvis', 'Bip01 Pelvis', 'Bip01 NonAccum'),
    SkeletonBone('Bip01 Thigh.L', 'Bip01 L Thigh', 'Bip01 Pelvis'),
    SkeletonBone('Bip01 Calf.L', 'Bip01 L Calf', 'Bip01 Thigh.L'),
    SkeletonBone('Bip01 Foot.L', 'Bip01 L Foot', 'Bip01 Calf.L'),
    SkeletonBone('Bip01 Toe0.L', 'Bip01 L Toe0', 'Bip01 Foot.L'),
    SkeletonBone('Bip01 Thigh.R', 'Bip01 R Thigh', 'Bip01 Pelvis'),
    SkeletonBone('Bip01 Calf.R', 'Bip01 R Calf', 'Bip01 Thigh.R'),
    SkeletonBone('Bip01 Foot.R', 'Bip01 R Foot', 'Bip01 Calf.R'),
    SkeletonBone('Bip01 Toe0.R', 'Bip01 R Toe0', 'Bip01 Foot.R'),
    SkeletonBone('Bip01 GenHelper', 'Bip01 GenHelper', 'Bip01 Pelvis'),
    SkeletonBone('Bip01 Penis01', 'Bip01 Penis01', 'Bip01 GenHelper'),
    SkeletonBone('Bip01 Penis02', 'Bip01 Penis02', 'Bip01 Penis01'),
    SkeletonBone('Bip01 Penis03', 'Bip01 Penis03', 'Bip01 Penis02'),
    SkeletonBone('Bip01 Penis04', 'Bip01 Penis04', 'Bip01 Penis03'),
    SkeletonBone('Bip01 Penis05', 'Bip01 Penis05', 'Bip01 Penis04'),
    SkeletonBone('Bip01 Penis06', 'Bip01 Penis06', 'Bip01 Penis05'),
    SkeletonBone('Bip01 Scrotum01', 'Bip01 Scrotum01', 'Bip01 GenHelper'),
    SkeletonBone('Bip01 Scrotum02', 'Bip01 Scrotum02', 'Bip01 Scrotum01'),
    SkeletonBone('Dick1', 'Dick1', 'Bip01 Pelvis'),
    SkeletonBone('Dick2', 'Dick2', 'Dick1'),
    SkeletonBone('Dick3', 'Dick3', 'Dick2'),
    SkeletonBone('Dick4', 'Dick4', 'Dick3'),
    SkeletonBone('Balls', 'Balls', 'Bip01 Pelvis'),
    SkeletonBone('vagina.R', 'vagina.R', 'Bip01 Pelvis'),
    SkeletonBone('vagina.L', 'vagina.L', 'Bip01 Pelvis'),
    SkeletonBone('Bip01 Spine', 'Bip01 Spine', 'Bip01 NonAccum'),
    SkeletonBone('Bip01 Spine1', 'Bip01 Spine1', 'Bip01 Spine'),
    SkeletonBone('Bip01 Spine2', 'Bip01 Spine2', 'Bip01 Spine1'),
    SkeletonBone('Bip01 Neck', 'Bip01 Neck', 'Bip01 Spine2'),
    SkeletonBone('Bip01 Neck1', 'Bip01 Neck1', 'Bip01 Neck'),
    SkeletonBone('Bip01 Head', 'Bip01 Head', 'Bip01 Neck1'),
    SkeletonBone('HeadAnims', 'HeadAnims', 'Bip01 Head'),
    SkeletonBone('Bip01 HT', 'Bip01 HT', 'Bip01 Head'),
    SkeletonBone('Bip01 HT2', 'Bip01 HT2', 'Bip01 HT'),
    SkeletonBone('Bip01 Tongue01', 'Bip01 Tongue01', 'Bip01 HT2'),
    SkeletonBone('Bip01 Tongue02', 'Bip01 Tongue02', 'Bip01 Tongue01'),
    SkeletonBone('Bip01 Tongue03', 'Bip01 Tongue03', 'Bip01 Tongue02'),
    SkeletonBone('Bip01 NVG', 'Bip01 NVG', 'Bip01 Head'),
    SkeletonBone('Bip01 NVG1', 'Bip01 NVG1', 'Bip01 NVG'),
    SkeletonBone('Bip01 NVG2', 'Bip01 NVG2', 'Bip01 NVG1'),
    SkeletonBone('Bip01 Clavicle.L', 'Bip01 L Clavicle', 'Bip01 Neck'),
    SkeletonBone('Bip01 UpperArm.L', 'Bip01 L UpperArm', 'Bip01 Clavicle.L'),
    SkeletonBone('Bip01 UpArmTwistBone.L', 'Bip01 LUpArmTwistBone', 'Bip01 UpperArm.L'),
    SkeletonBone('Bip01 Forearm.L', 'Bip01 L Forearm', 'Bip01 UpperArm.L'),
    SkeletonBone('Bip01 ForeTwist.L', 'Bip01 L ForeTwist', 'Bip01 Forearm.L'),
    SkeletonBone('Bip01 Hand.L', 'Bip01 L Hand', 'Bip01 Forearm.L'),
    SkeletonBone('Bip01 Thumb1.L', 'Bip01 L Thumb1', 'Bip01 Hand.L'),
    SkeletonBone('Bip01 Thumb11.L', 'Bip01 L Thumb11', 'Bip01 Thumb1.L'),
    SkeletonBone('Bip01 Thumb12.L', 'Bip01 L Thumb12', 'Bip01 Thumb11.L'),
    SkeletonBone('Bip01 Finger1.L', 'Bip01 L Finger1', 'Bip01 Hand.L'),
    SkeletonBone('Bip01 Finger11.L', 'Bip01 L Finger11', 'Bip01 Finger1.L'),
    SkeletonBone('Bip01 Finger12.L', 'Bip01 L Finger12', 'Bip01 Finger11.L'),
    SkeletonBone('Bip01 Finger2.L', 'Bip01 L Finger2', 'Bip01 Hand.L'),
    SkeletonBone('Bip01 Finger21.L', 'Bip01 L Finger21', 'Bip01 Finger2.L'),
    SkeletonBone('Bip01 Finger22.L', 'Bip01 L Finger22', 'Bip01 Finger21.L'),
    SkeletonBone('Bip01 Finger3.L', 'Bip01 L Finger3', 'Bip01 Hand.L'),
    SkeletonBone('Bip01 Finger31.L', 'Bip01 L Finger31', 'Bip01 Finger3.L'),
    SkeletonBone('Bip01 Finger32.L', 'Bip01 L Finger32', 'Bip01 Finger31.L'),
    SkeletonBone('Bip01 Finger4.L', 'Bip01 L Finger4', 'Bip01 Hand.L'),
    SkeletonBone('Bip01 Finger41.L', 'Bip01 L Finger41', 'Bip01 Finger4.L'),
    SkeletonBone('Bip01 Finger42.L', 'Bip01 L Finger42', 'Bip01 Finger41.L'),
    SkeletonBone('Bip01 Clavicle.R', 'Bip01 R Clavicle', 'Bip01 Neck'),
    SkeletonBone('Bip01 UpperArm.R', 'Bip01 R UpperArm', 'Bip01 Clavicle.R'),
    SkeletonBone('Bip01 UpArmTwistBone.R', 'Bip01 RUpArmTwistBone', 'Bip01 UpperArm.R'),
    SkeletonBone('Bip01 Forearm.R', 'Bip01 R Forearm', 'Bip01 UpperArm.R'),
    SkeletonBone('Bip01 ForeTwist.R', 'Bip01 R ForeTwist', 'Bip01 Forearm.R'),
    SkeletonBone('Bip01 Hand.R', 'Bip01 R Hand', 'Bip01 Forearm.R'),
    SkeletonBone('Weapon', 'Weapon', 'Bip01 Hand.R'),
    SkeletonBone('Bip01 Thumb1.R', 'Bip01 R Thumb1', 'Bip01 Hand.R'),
    SkeletonBone('Bip01 Thumb11.R', 'Bip01 R Thumb11', 'Bip01 Thumb1.R'),
    SkeletonBone('Bip01 Thumb12.R', 'Bip01 R Thumb12', 'Bip01 Thumb11.R'),
    SkeletonBone('Bip01 Finger1.R', 'Bip01 R Finger1', 'Bip01 Hand.R'),
    SkeletonBone('Bip01 Finger11.R', 'Bip01 R Finger11', 'Bip01 Finger1.R'),
    SkeletonBone('Bip01 Finger12.R', 'Bip01 R Finger12', 'Bip01 Finger11.R'),
    SkeletonBone('Bip01 Finger2.R', 'Bip01 R Finger2', 'Bip01 Hand.R'),
    SkeletonBone('Bip01 Finger21.R', 'Bip01 R Finger21', 'Bip01 Finger2.R'),
    SkeletonBone('Bip01 Finger22.R', 'Bip01 R Finger22', 'Bip01 Finger21.R'),
    SkeletonBone('Bip01 Finger3.R', 'Bip01 R Finger3', 'Bip01 Hand.R'),
    SkeletonBone('Bip01 Finger31.R', 'Bip01 R Finger31', 'Bip01 Finger3.R'),
    SkeletonBone('Bip01 Finger32.R', 'Bip01 R Finger32', 'Bip01 Finger31.R'),
    SkeletonBone('Bip01 Finger4.R', 'Bip01 R Finger4', 'Bip01 Hand.R'),
    SkeletonBone('Bip01 Finger41.R', 'Bip01 R Finger41', 'Bip01 Finger4.R'),
    SkeletonBone('Bip01 Finger42.R', 'Bip01 R Finger42', 'Bip01 Finger41.R'),
    SkeletonBone('Bip01 ForeTwistDriver.R', 'Bip01 R ForeTwistDriver', 'Bip01 UpperArm.R'),
    SkeletonBone('Bip01 Pauldron.L', 'Bip01 LPauldron', 'Bip01 Spine2'),
    SkeletonBone('Bip01 Pauldron.R', 'Bip01 RPauldron', 'Bip01 Spine2'),
    SkeletonBone('Bip01 Breast01.L', 'Bip01 L Breast01', 'Bip01 Spine2'),
    SkeletonBone('Bip01 Breast02.L', 'Bip01 L Breast02', 'Bip01 Breast01.L'),
    SkeletonBone('Bip01 Breast03.L', 'Bip01 L Breast03', 'Bip01 Breast02.L'),
    SkeletonBone('Bip01 Breast01.R', 'Bip01 R Breast01', 'Bip01 Spine2'),
    SkeletonBone('Bip01 Breast02.R', 'Bip01 R Breast02', 'Bip01 Breast01.R'),
    SkeletonBone('Bip01 Breast03.R', 'Bip01 R Breast03', 'Bip01 Breast02.R'),
    SkeletonBone('breast.L', 'breast.L', 'Bip01 Spine2'),
    SkeletonBone('breast.R', 'breast.R', 'Bip01 Spine2')]

fnvExpressions = []

fnvParts = []

fnvDict = BoneDict(fnvBones, fnvExpressions, fnvParts)

skyrimBones = [
    SkeletonBone('NPC Root', 'NPC Root [Root]', None),
    SkeletonBone('NPC COM', 'NPC COM [COM ]', 'NPC Root'),
    SkeletonBone('NPC Pelvis', 'NPC Pelvis [Pelv]', 'NPC COM'),
    SkeletonBone('NPC Thigh.L', 'NPC L Thigh [LThg]', 'NPC Pelvis'),
    SkeletonBone('NPC Calf.L', 'NPC L Calf [LClf]', 'NPC Thigh.L'),
    SkeletonBone('NPC Foot.L', 'NPC L Foot [Lft ]', 'NPC Calf.L'),
    SkeletonBone('NPC Toe0.L', 'NPC L Toe0 [LToe]', 'NPC Foot.L'),
    SkeletonBone('NPC Thigh.R', 'NPC R Thigh [RThg]', 'NPC Pelvis'),
    SkeletonBone('NPC Calf.R', 'NPC R Calf [RClf]', 'NPC Thigh.R'),
    SkeletonBone('NPC Foot.R', 'NPC R Foot [Rft ]', 'NPC Calf.R'),
    SkeletonBone('NPC Toe0.R', 'NPC R Toe0 [RToe]', 'NPC Foot.R'),
    SkeletonBone('WeaponDagger', 'WeaponDagger', 'NPC Pelvis'),
    SkeletonBone('WeaponAxe', 'WeaponAxe', 'NPC Pelvis'),
    SkeletonBone('WeaponSword', 'WeaponSword', 'NPC Pelvis'),
    SkeletonBone('WeaponMace', 'WeaponMace', 'NPC Pelvis'),
    SkeletonBone('TailBone01', 'TailBone01', 'NPC Pelvis'),
    SkeletonBone('TailBone02', 'TailBone02', 'TailBone01'),
    SkeletonBone('TailBone03', 'TailBone03', 'TailBone02'),
    SkeletonBone('TailBone04', 'TailBone04', 'TailBone03'),
    SkeletonBone('TailBone05', 'TailBone05', 'TailBone04'),
    SkeletonBone('SkirtFBone01', 'SkirtFBone01', 'NPC Pelvis'),
    SkeletonBone('SkirtFBone02', 'SkirtFBone02', 'SkirtFBone01'),
    SkeletonBone('SkirtFBone03', 'SkirtFBone03', 'SkirtFBone02'),
    SkeletonBone('SkirtBBone01', 'SkirtBBone01', 'NPC Pelvis'),
    SkeletonBone('SkirtBBone02', 'SkirtBBone02', 'SkirtBBone01'),
    SkeletonBone('SkirtBBone03', 'SkirtBBone03', 'SkirtBBone02'),
    SkeletonBone('SkirtBone01.L', 'SkirtLBone01', 'NPC Pelvis'),
    SkeletonBone('SkirtBone02.L', 'SkirtLBone02', 'SkirtBone01.L'),
    SkeletonBone('SkirtBone03.L', 'SkirtLBone03', 'SkirtBone02.L'),
    SkeletonBone('SkirtBone01.R', 'SkirtRBone01', 'NPC Pelvis'),
    SkeletonBone('SkirtBone02.R', 'SkirtRBone02', 'SkirtBone01.R'),
    SkeletonBone('SkirtBone03.R', 'SkirtRBone03', 'SkirtBone02.R'),
    SkeletonBone('NPC Spine', 'NPC Spine [Spn0]', 'NPC Pelvis'),
    SkeletonBone('NPC Spine1', 'NPC Spine1 [Spn1]', 'NPC Spine'),
    SkeletonBone('NPC Spine2', 'NPC Spine2 [Spn2]', 'NPC Spine1'),
    SkeletonBone('NPC Neck', 'NPC Neck [Neck]', 'NPC Spine2'),
    SkeletonBone('NPC Head', 'NPC Head [Head]', 'NPC Neck'),
    SkeletonBone('NPC Head MagicNode', 'NPC Head MagicNode [Hmag]', 'NPC Head'),
    SkeletonBone('NPCEyeBone', 'NPCEyeBone', 'NPC Head'),
    SkeletonBone('NPC Clavicle.R', 'NPC R Clavicle [RClv]', 'NPC Spine2'),
    SkeletonBone('NPC UpperArm.R', 'NPC R UpperArm [RUar]', 'NPC Clavicle.R'),
    SkeletonBone('NPC Forearm.R', 'NPC R Forearm [RLar]', 'NPC UpperArm.R'),
    SkeletonBone('NPC Hand.R', 'NPC R Hand [RHnd]', 'NPC Forearm.R'),
    SkeletonBone('NPC Finger00.R', 'NPC R Finger00 [RF00]', 'NPC Hand.R'),
    SkeletonBone('NPC Finger01.R', 'NPC R Finger01 [RF01]', 'NPC Finger00.R'),
    SkeletonBone('NPC Finger02.R', 'NPC R Finger02 [RF02]', 'NPC Finger01.R'),
    SkeletonBone('NPC Finger10.R', 'NPC R Finger10 [RF10]', 'NPC Hand.R'),
    SkeletonBone('NPC Finger11.R', 'NPC R Finger11 [RF11]', 'NPC Finger10.R'),
    SkeletonBone('NPC Finger12.R', 'NPC R Finger12 [RF12]', 'NPC Finger11.R'),
    SkeletonBone('NPC Finger20.R', 'NPC R Finger20 [RF20]', 'NPC Hand.R'),
    SkeletonBone('NPC Finger21.R', 'NPC R Finger21 [RF21]', 'NPC Finger20.R'),
    SkeletonBone('NPC Finger22.R', 'NPC R Finger22 [RF22]', 'NPC Finger21.R'),
    SkeletonBone('NPC Finger30.R', 'NPC R Finger30 [RF30]', 'NPC Hand.R'),
    SkeletonBone('NPC Finger31.R', 'NPC R Finger31 [RF31]', 'NPC Finger30.R'),
    SkeletonBone('NPC Finger32.R', 'NPC R Finger32 [RF32]', 'NPC Finger31.R'),
    SkeletonBone('NPC Finger40.R', 'NPC R Finger40 [RF40]', 'NPC Hand.R'),
    SkeletonBone('NPC Finger41.R', 'NPC R Finger41 [RF41]', 'NPC Finger40.R'),
    SkeletonBone('NPC Finger42.R', 'NPC R Finger42 [RF42]', 'NPC Finger41.R'),
    SkeletonBone('NPC MagicNode.R', 'NPC R MagicNode [RMag]', 'NPC Hand.R'),
    SkeletonBone('WEAPON', 'WEAPON', 'NPC Hand.R'),
    SkeletonBone('AnimObject.R', 'AnimObjectR', 'NPC Hand.R'),
    SkeletonBone('NPC ForearmTwist1.R', 'NPC R ForearmTwist1 [RLt1]', 'NPC Forearm.R'),
    SkeletonBone('NPC ForearmTwist2.R', 'NPC R ForearmTwist2 [RLt2]', 'NPC Forearm.R'),
    SkeletonBone('NPC UpperarmTwist1.R', 'NPC R UpperarmTwist1 [RUt1]', 'NPC UpperArm.R'),
    SkeletonBone('NPC UpperarmTwist2.R', 'NPC R UpperarmTwist2 [RUt2]', 'NPC UpperarmTwist1.R'),
    SkeletonBone('NPC Pauldron.R', 'NPC R Pauldron', 'NPC Clavicle.R'),
    SkeletonBone('NPC Clavicle.L', 'NPC L Clavicle [LClv]', 'NPC Spine2'),
    SkeletonBone('NPC UpperArm.L', 'NPC L UpperArm [LUar]', 'NPC Clavicle.L'),
    SkeletonBone('NPC Forearm.L', 'NPC L Forearm [LLar]', 'NPC UpperArm.L'),
    SkeletonBone('NPC Hand.L', 'NPC L Hand [LHnd]', 'NPC Forearm.L'),
    SkeletonBone('NPC Finger00.L', 'NPC L Finger00 [LF00]', 'NPC Hand.L'),
    SkeletonBone('NPC Finger01.L', 'NPC L Finger01 [LF01]', 'NPC Finger00.L'),
    SkeletonBone('NPC Finger02.L', 'NPC L Finger02 [LF02]', 'NPC Finger01.L'),
    SkeletonBone('NPC Finger10.L', 'NPC L Finger10 [LF10]', 'NPC Hand.L'),
    SkeletonBone('NPC Finger11.L', 'NPC L Finger11 [LF11]', 'NPC Finger10.L'),
    SkeletonBone('NPC Finger12.L', 'NPC L Finger12 [LF12]', 'NPC Finger11.L'),
    SkeletonBone('NPC Finger20.L', 'NPC L Finger20 [LF20]', 'NPC Hand.L'),
    SkeletonBone('NPC Finger21.L', 'NPC L Finger21 [LF21]', 'NPC Finger20.L'),
    SkeletonBone('NPC Finger22.L', 'NPC L Finger22 [LF22]', 'NPC Finger21.L'),
    SkeletonBone('NPC Finger30.L', 'NPC L Finger30 [LF30]', 'NPC Hand.L'),
    SkeletonBone('NPC Finger31.L', 'NPC L Finger31 [LF31]', 'NPC Finger30.L'),
    SkeletonBone('NPC Finger32.L', 'NPC L Finger32 [LF32]', 'NPC Finger31.L'),
    SkeletonBone('NPC Finger40.L', 'NPC L Finger40 [LF40]', 'NPC Hand.L'),
    SkeletonBone('NPC Finger41.L', 'NPC L Finger41 [LF41]', 'NPC Finger40.L'),
    SkeletonBone('NPC Finger42.L', 'NPC L Finger42 [LF42]', 'NPC Finger41.L'),
    SkeletonBone('NPC MagicNode.L', 'NPC L MagicNode [LMag]', 'NPC Hand.L'),
    SkeletonBone('SHIELD', 'SHIELD', 'NPC Hand.L'),
    SkeletonBone('AnimObject.L', 'AnimObjectL', 'NPC Hand.L'),
    SkeletonBone('NPC ForearmTwist1.L', 'NPC L ForearmTwist1 [LLt1]', 'NPC Forearm.L'),
    SkeletonBone('NPC ForearmTwist2.L', 'NPC L ForearmTwist2 [LLt2]', 'NPC Forearm.L'),
    SkeletonBone('NPC UpperarmTwist1.L', 'NPC L UpperarmTwist1 [LUt1]', 'NPC UpperArm.L'),
    SkeletonBone('NPC UpperarmTwist2.L', 'NPC L UpperarmTwist2 [LUt2]', 'NPC UpperarmTwist1.L'),
    SkeletonBone('NPC Pauldron.L', 'NPC L Pauldron', 'NPC Clavicle.L'),
    SkeletonBone('WeaponBack', 'WeaponBack', 'NPC Spine2'),
    SkeletonBone('WeaponBow', 'WeaponBow', 'NPC Spine2'),
    SkeletonBone('QUIVER', 'QUIVER', 'NPC Spine2'),
    SkeletonBone('MagicEffectsNode', 'MagicEffectsNode', 'NPC Spine'),
    SkeletonBone('Genitals', 'Genitals', 'NPC Pelvis'),
    SkeletonBone('NPC GenitalsBase', 'NPC GenitalsBase [GenBase]', 'NPC Pelvis'),
    SkeletonBone('NPC GenitalsScrotum', 'NPC GenitalsScrotum [GenScrot]', 'NPC GenitalsBase'),
    SkeletonBone('NPC GenitalsScrotum.L', 'NPC L GenitalsScrotum [LGenScrot]', 'NPC GenitalsScrotum'),
    SkeletonBone('NPC GenitalsScrotum.R', 'NPC R GenitalsScrotum [RGenScrot]', 'NPC GenitalsScrotum'),
    SkeletonBone('NPC Genitals01', 'NPC Genitals01 [Gen01]', 'NPC GenitalsBase'),
    SkeletonBone('NPC Genitals02', 'NPC Genitals02 [Gen02]', 'NPC Genitals01'),
    SkeletonBone('NPC Genitals03', 'NPC Genitals03 [Gen03]', 'NPC Genitals02'),
    SkeletonBone('NPC Genitals04', 'NPC Genitals04 [Gen04]', 'NPC Genitals03'),
    SkeletonBone('NPC Genitals05', 'NPC Genitals05 [Gen05]', 'NPC Genitals04'),
    SkeletonBone('NPC Genitals06', 'NPC Genitals06 [Gen06]', 'NPC Genitals05')]

skyrimExpressions = ['Basis', 'Aah', 'BigAah', 'BlinkLeft', 'BlinkRight', 'BMP', 'BrowDownLeft', 
    'BrowDownRight', 'BrowInLeft', 'BrowInRight', 'BrowUpLeft', 'BrowUpRight', 'ChJSh', 'CombatAnger', 
    'CombatShout', 'DialogueAnger', 'DialogueDisgusted', 'DialogueFear', 'DialogueHappy', 
    'DialoguePuzzled', 'DialogueSad', 'DialogueSurprise', 'DST', 'Eee', 'Eh', 'FV', 'I', 'K', 
    'LookDown', 'LookLeft', 'LookRight', 'LookUp', 'MoodAnger', 'MoodDisgusted', 'MoodFear', 
    'MoodHappy', 'MoodPuzzled', 'MoodSad', 'MoodSurprise', 'N', 'Oh', 'OohQ', 'R', 'SkinnyMorph', 
    'SquintLeft', 'SquintRight', 'Th', 'W', 'VampireMorph']

skyrimParts = [
    BodyPart(30, "SBP_30_HEAD"),
    BodyPart(31, "SBP_31_HAIR"), 
    BodyPart(32, "SBP_32_BODY"),
    BodyPart(33, "SBP_33_HANDS"),
    BodyPart(34, "SBP_34_FOREARMS"),
    BodyPart(35, "SBP_35_AMULET"),
    BodyPart(36, "SBP_36_RING"),
    BodyPart(37, "SBP_37_FEET"),
    BodyPart(38, "SBP_38_CALVES"),
    BodyPart(39, "SBP_39_SHIELD"),
    BodyPart(40, "SBP_40_TAIL"),
    BodyPart(41, "SBP_41_LONGHAIR"),
    BodyPart(42, "SBP_42_CIRCLET"),
    BodyPart(43, "SBP_43_EARS"),
    BodyPart(44, "SBP_44_DRAGON_BLOODHEAD_OR_MOD_MOUTH"),
    BodyPart(45, "SBP_45_DRAGON_BLOODWINGL_OR_MOD_NECK"),
    BodyPart(46, "SBP_46_DRAGON_BLOODWINGR_OR_MOD_CHEST_PRIMARY"),
    BodyPart(47, "SBP_47_DRAGON_BLOODTAIL_OR_MOD_BACK"),
    BodyPart(48, "SBP_48_MOD_MISC1"),
    BodyPart(49, "SBP_49_MOD_PELVIS_PRIMARY"),
    BodyPart(50, "SBP_50_DECAPITATEDHEAD"),
    BodyPart(51, "SBP_51_DECAPITATE"),
    BodyPart(52, "SBP_52_MOD_PELVIS_SECONDARY"),
    BodyPart(53, "SBP_53_MOD_LEG_RIGHT"),
    BodyPart(54, "SBP_54_MOD_LEG_LEFT"),
    BodyPart(55, "SBP_55_MOD_FACE_JEWELRY"),
    BodyPart(56, "SBP_56_MOD_CHEST_SECONDARY"),
    BodyPart(57, "SBP_57_MOD_SHOULDER"),
    BodyPart(58, "SBP_58_MOD_ARM_LEFT"),
    BodyPart(59, "SBP_59_MOD_ARM_RIGHT"),
    BodyPart(60, "SBP_60_MOD_MISC2"),
    BodyPart(61, "SBP_61_FX01"),
    BodyPart(130, "SBP_130_HEAD"),
    BodyPart(131, "SBP_131_HAIR"),
    BodyPart(141, "SBP_141_LONGHAIR"),
    BodyPart(142, "SBP_142_CIRCLET"),
    BodyPart(143, "SBP_143_EARS"),
    BodyPart(150, "SBP_150_DECAPITATEDHEAD"),
    BodyPart(230, "SBP_230_NECK") ]

skyrimDict = BoneDict(skyrimBones, skyrimExpressions, skyrimParts)

fo4Bones = [
    SkeletonBone('Root', 'Root', None),
    SkeletonBone('COM', 'COM', 'Root'),
    SkeletonBone('Pelvis', 'Pelvis', 'COM'),
    SkeletonBone('Leg_Thigh.L', 'LLeg_Thigh', 'Pelvis'),
    SkeletonBone('Leg_Calf.L', 'LLeg_Calf', 'Leg_Thigh.L'),
    SkeletonBone('Leg_Foot.L', 'LLeg_Foot', 'Leg_Calf.L'),
    SkeletonBone('Leg_Toe1.L', 'LLeg_Toe1', 'Leg_Foot.L'),
    SkeletonBone('Leg_Calf_skin.L', 'LLeg_Calf_skin', 'Leg_Calf.L'),
    SkeletonBone('Leg_Calf_Low_skin.L', 'LLeg_Calf_Low_skin', 'Leg_Calf.L'),
    SkeletonBone('Leg_Thigh_skin.L', 'LLeg_Thigh_skin', 'Leg_Thigh.L'),
    SkeletonBone('Leg_Thigh_Low_skin.L', 'LLeg_Thigh_Low_skin', 'Leg_Thigh.L'),
    SkeletonBone('Leg_Thigh_Fat_skin.L', 'LLeg_Thigh_Fat_skin', 'Leg_Thigh.L'),
    SkeletonBone('Leg_Thigh.R', 'RLeg_Thigh', 'Pelvis'),
    SkeletonBone('Leg_Calf.R', 'RLeg_Calf', 'Leg_Thigh.R'),
    SkeletonBone('Leg_Foot.R', 'RLeg_Foot', 'Leg_Calf.R'),
    SkeletonBone('Leg_Toe1.R', 'RLeg_Toe1', 'Leg_Foot.R'),
    SkeletonBone('Leg_Calf_skin.R', 'RLeg_Calf_skin', 'Leg_Calf.R'),
    SkeletonBone('Leg_Calf_Low_skin.R', 'RLeg_Calf_Low_skin', 'Leg_Calf.R'),
    SkeletonBone('Leg_Thigh_skin.R', 'RLeg_Thigh_skin', 'Leg_Thigh.R'),
    SkeletonBone('Leg_Thigh_Low_skin.R', 'RLeg_Thigh_Low_skin', 'Leg_Thigh.R'),
    SkeletonBone('Leg_Thigh_Fat_skin.R', 'RLeg_Thigh_Fat_skin', 'Leg_Thigh.R'),
    SkeletonBone('Pelvis_skin', 'Pelvis_skin', 'Pelvis'),
    SkeletonBone('ButtFat_skin.R', 'RButtFat_skin', 'Pelvis'),
    SkeletonBone('ButtFat_skin.L', 'LButtFat_skin', 'Pelvis'),
    SkeletonBone('Pelvis_Rear_skin', 'Pelvis_Rear_skin', 'Pelvis'),
    SkeletonBone('SPINE1', 'SPINE1', 'COM'),
    SkeletonBone('SPINE2', 'SPINE2', 'SPINE1'),
    SkeletonBone('Chest', 'Chest', 'SPINE2'),
    SkeletonBone('Arm_Collarbone.L', 'LArm_Collarbone', 'Chest'),
    SkeletonBone('Arm_UpperArm.L', 'LArm_UpperArm', 'Arm_Collarbone.L'),
    SkeletonBone('Arm_ForeArm1.L', 'LArm_ForeArm1', 'Arm_UpperArm.L'),
    SkeletonBone('Arm_ForeArm2.L', 'LArm_ForeArm2', 'Arm_ForeArm1.L'),
    SkeletonBone('Arm_ForeArm3.L', 'LArm_ForeArm3', 'Arm_ForeArm2.L'),
    SkeletonBone('Arm_Hand.L', 'LArm_Hand', 'Arm_ForeArm3.L'),
    SkeletonBone('Arm_Finger11.L', 'LArm_Finger11', 'Arm_Hand.L'),
    SkeletonBone('Arm_Finger12.L', 'LArm_Finger12', 'Arm_Finger11.L'),
    SkeletonBone('Arm_Finger13.L', 'LArm_Finger13', 'Arm_Finger12.L'),
    SkeletonBone('Arm_Finger21.L', 'LArm_Finger21', 'Arm_Hand.L'),
    SkeletonBone('Arm_Finger22.L', 'LArm_Finger22', 'Arm_Finger21.L'),
    SkeletonBone('Arm_Finger23.L', 'LArm_Finger23', 'Arm_Finger22.L'),
    SkeletonBone('Arm_Finger31.L', 'LArm_Finger31', 'Arm_Hand.L'),
    SkeletonBone('Arm_Finger32.L', 'LArm_Finger32', 'Arm_Finger31.L'),
    SkeletonBone('Arm_Finger33.L', 'LArm_Finger33', 'Arm_Finger32.L'),
    SkeletonBone('Arm_Finger41.L', 'LArm_Finger41', 'Arm_Hand.L'),
    SkeletonBone('Arm_Finger42.L', 'LArm_Finger42', 'Arm_Finger41.L'),
    SkeletonBone('Arm_Finger43.L', 'LArm_Finger43', 'Arm_Finger42.L'),
    SkeletonBone('Arm_Finger51.L', 'LArm_Finger51', 'Arm_Hand.L'),
    SkeletonBone('Arm_Finger52.L', 'LArm_Finger52', 'Arm_Finger51.L'),
    SkeletonBone('Arm_Finger53.L', 'LArm_Finger53', 'Arm_Finger52.L'),
    SkeletonBone('Weapon.L', 'WeaponLeft', 'Arm_Hand.L'),
    SkeletonBone('AnimObject1.L', 'AnimObjectL1', 'Arm_Hand.L'),
    SkeletonBone('AnimObject3.L', 'AnimObjectL3', 'Arm_Hand.L'),
    SkeletonBone('AnimObject2.L', 'AnimObjectL2', 'Arm_Hand.L'),
    SkeletonBone('PipboyBone', 'PipboyBone', 'Arm_ForeArm3.L'),
    SkeletonBone('Arm_ForeArm3_skin.L', 'LArm_ForeArm3_skin', 'Arm_ForeArm3.L'),
    SkeletonBone('Arm_ForeArm2_skin.L', 'LArm_ForeArm2_skin', 'Arm_ForeArm2.L'),
    SkeletonBone('Arm_ForeArm1_skin.L', 'LArm_ForeArm1_skin', 'Arm_ForeArm1.L'),
    SkeletonBone('Arm_UpperTwist1.L', 'LArm_UpperTwist1', 'Arm_UpperArm.L'),
    SkeletonBone('Arm_UpperTwist2.L', 'LArm_UpperTwist2', 'Arm_UpperTwist1.L'),
    SkeletonBone('Arm_UpperTwist2_skin.L', 'LArm_UpperTwist2_skin', 'Arm_UpperTwist2.L'),
    SkeletonBone('Arm_UpperFat_skin.L', 'LArm_UpperFat_skin', 'Arm_UpperTwist2.L'),
    SkeletonBone('LArm_UpperTwist1_skin', 'LArm_UpperTwist1_skin', 'Arm_UpperTwist1.L'),
    SkeletonBone('Arm_UpperArm_skin.L', 'LArm_UpperArm_skin', 'Arm_UpperArm.L'),
    SkeletonBone('Arm_Collarbone_skin.L', 'LArm_Collarbone_skin', 'Arm_Collarbone.L'),
    SkeletonBone('Arm_ShoulderFat_skin.L', 'LArm_ShoulderFat_skin', 'Arm_Collarbone.L'),
    SkeletonBone('Neck', 'Neck', 'Chest'),
    SkeletonBone('HEAD', 'HEAD', 'Neck'),
    SkeletonBone('Head_skin', 'Head_skin', 'HEAD'),
    SkeletonBone('Face_skin', 'Face_skin', 'HEAD'),
    SkeletonBone('Neck_skin', 'Neck_skin', 'Neck'),
    SkeletonBone('Neck1_skin', 'Neck1_skin', 'Neck'),
    SkeletonBone('skin_bone_Neckmuscle2.L', 'skin_bone_L_Neckmuscle2', 'Neck'),
    SkeletonBone('skin_bone_Neckmuscle2.R', 'skin_bone_R_Neckmuscle2', 'Neck'),
    SkeletonBone('Arm_Collarbone.R', 'RArm_Collarbone', 'Chest'),
    SkeletonBone('Arm_UpperArm.R', 'RArm_UpperArm', 'Arm_Collarbone.R'),
    SkeletonBone('Arm_ForeArm1.R', 'RArm_ForeArm1', 'Arm_UpperArm.R'),
    SkeletonBone('Arm_ForeArm2.R', 'RArm_ForeArm2', 'Arm_ForeArm1.R'),
    SkeletonBone('Arm_ForeArm3.R', 'RArm_ForeArm3', 'Arm_ForeArm2.R'),
    SkeletonBone('Arm_Hand.R', 'RArm_Hand', 'Arm_ForeArm3.R'),
    SkeletonBone('Arm_Finger11.R', 'RArm_Finger11', 'Arm_Hand.R'),
    SkeletonBone('Arm_Finger12.R', 'RArm_Finger12', 'Arm_Finger11.R'),
    SkeletonBone('Arm_Finger13.R', 'RArm_Finger13', 'Arm_Finger12.R'),
    SkeletonBone('Arm_Finger21.R', 'RArm_Finger21', 'Arm_Hand.R'),
    SkeletonBone('Arm_Finger22.R', 'RArm_Finger22', 'Arm_Finger21.R'),
    SkeletonBone('Arm_Finger23.R', 'RArm_Finger23', 'Arm_Finger22.R'),
    SkeletonBone('Arm_Finger31.R', 'RArm_Finger31', 'Arm_Hand.R'),
    SkeletonBone('Arm_Finger32.R', 'RArm_Finger32', 'Arm_Finger31.R'),
    SkeletonBone('Arm_Finger33.R', 'RArm_Finger33', 'Arm_Finger32.R'),
    SkeletonBone('Arm_Finger41.R', 'RArm_Finger41', 'Arm_Hand.R'),
    SkeletonBone('Arm_Finger42.R', 'RArm_Finger42', 'Arm_Finger41.R'),
    SkeletonBone('Arm_Finger43.R', 'RArm_Finger43', 'Arm_Finger42.R'),
    SkeletonBone('Arm_Finger51.R', 'RArm_Finger51', 'Arm_Hand.R'),
    SkeletonBone('Arm_Finger52.R', 'RArm_Finger52', 'Arm_Finger51.R'),
    SkeletonBone('Arm_Finger53.R', 'RArm_Finger53', 'Arm_Finger52.R'),
    SkeletonBone('Weapon.R', 'WEAPON', 'Arm_Hand.R'),
    SkeletonBone('AnimObject1.R', 'AnimObjectR1', 'Arm_Hand.R'),
    SkeletonBone('AnimObject2.R', 'AnimObjectR2', 'Arm_Hand.R'),
    SkeletonBone('AnimObject3.R', 'AnimObjectR3', 'Arm_Hand.R'),
    SkeletonBone('Arm_ForeArm3_skin.R', 'RArm_ForeArm3_skin', 'Arm_ForeArm3.R'),
    SkeletonBone('Arm_ForeArm2_skin.R', 'RArm_ForeArm2_skin', 'Arm_ForeArm2.R'),
    SkeletonBone('Arm_ForeArm1_skin.R', 'RArm_ForeArm1_skin', 'Arm_ForeArm1.R'),
    SkeletonBone('Arm_UpperTwist1.R', 'RArm_UpperTwist1', 'Arm_UpperArm.R'),
    SkeletonBone('Arm_UpperTwist2.R', 'RArm_UpperTwist2', 'Arm_UpperTwist1.R'),
    SkeletonBone('Arm_UpperTwist2_skin.R', 'RArm_UpperTwist2_skin', 'Arm_UpperTwist2.R'),
    SkeletonBone('Arm_UpperFat_skin.R', 'RArm_UpperFat_skin', 'Arm_UpperTwist2.R'),
    SkeletonBone('RArm_UpperTwist1_skin', 'RArm_UpperTwist1_skin', 'Arm_UpperTwist1.R'),
    SkeletonBone('Arm_UpperArm_skin.R', 'RArm_UpperArm_skin', 'Arm_UpperArm.R'),
    SkeletonBone('Arm_Collarbone_skin.R', 'RArm_Collarbone_skin', 'Arm_Collarbone.R'),
    SkeletonBone('Arm_ShoulderFat_skin.R', 'RArm_ShoulderFat_skin', 'Arm_Collarbone.R'),
    SkeletonBone('RibHelper.L', 'L_RibHelper', 'Chest'),
    SkeletonBone('RibHelper.R', 'R_RibHelper', 'Chest'),
    SkeletonBone('Chest_skin', 'Chest_skin', 'Chest'),
    SkeletonBone('Breast_skin.L', 'LBreast_skin', 'Chest'),
    SkeletonBone('Breast_skin.R', 'RBreast_skin', 'Chest'),
    SkeletonBone('Chest_Rear_Skin', 'Chest_Rear_Skin', 'Chest'),
    SkeletonBone('Chest_Upper_skin', 'Chest_Upper_skin', 'Chest'),
    SkeletonBone('Neck_Low_skin', 'Neck_Low_skin', 'Chest'),
    SkeletonBone('Spine2_skin', 'Spine2_skin', 'SPINE2'),
    SkeletonBone('UpperBelly_skin', 'UpperBelly_skin', 'SPINE2'),
    SkeletonBone('Spine2_Rear_skin', 'Spine2_Rear_skin', 'SPINE2'),
    SkeletonBone('Spine1_skin', 'Spine1_skin', 'SPINE1'),
    SkeletonBone('Belly_skin', 'Belly_skin', 'SPINE1'),
    SkeletonBone('Spine1_Rear_skin', 'Spine1_Rear_skin', 'SPINE1'),
    SkeletonBone('Camera', 'Camera', 'Root'),
    SkeletonBone('Camera Control', 'Camera Control', 'Root'),
    SkeletonBone('AnimObjectA', 'AnimObjectA', 'Root'),
    SkeletonBone('AnimObjectB', 'AnimObjectB', 'Root'),
    SkeletonBone('CamTargetParent', 'CamTargetParent', 'Root'),
    SkeletonBone('CamTarget', 'CamTarget', 'CamTargetParent'),
    SkeletonBone('CharacterBumper', 'CharacterBumper', 'skeleton.nif'),
    SkeletonBone('Penis_00', 'Penis_00', 'Pelvis'),
    SkeletonBone('Penis_01', 'Penis_01', 'Penis_00'),
    SkeletonBone('Penis_02', 'Penis_02', 'Penis_01'),
    SkeletonBone('Penis_03', 'Penis_03', 'Penis_02'),
    SkeletonBone('Penis_04', 'Penis_04', 'Penis_03'),
    SkeletonBone('Penis_05', 'Penis_05', 'Penis_04'),
    SkeletonBone('Penis_Balls_01', 'Penis_Balls_01', 'Pelvis'),
    SkeletonBone('Penis_Balls_02', 'Penis_Balls_02', 'Penis_Balls_01'),
    SkeletonBone('Vagina_00', 'Vagina_00', 'Pelvis'),
    SkeletonBone('Vagina_01.L', 'Vagina_L_01', 'Vagina_00'),
    SkeletonBone('Vagina_02.L', 'Vagina_L_02', 'Vagina_01.L'),
    SkeletonBone('Vagina_01.R', 'Vagina_R_01', 'Vagina_00'),
    SkeletonBone('Vagina_02.R', 'Vagina_R_02', 'Vagina_01.R'),
    SkeletonBone('Butt_01.L', 'Butt_L_01', 'Pelvis'),
    SkeletonBone('Butt_01.R', 'Butt_R_01', 'Pelvis'),
    SkeletonBone('Anus_00', 'Anus_00', 'Pelvis'),
    SkeletonBone('Anus_01', 'Anus_01', 'Anus_00'),
    SkeletonBone('Anus_02', 'Anus_02', 'Anus_00'),
    SkeletonBone('Anus_03', 'Anus_03', 'Anus_00'),
    SkeletonBone('Anus_04', 'Anus_04', 'Anus_00'),
    SkeletonBone('Belly_01', 'Belly_01', 'SPINE1'),
    SkeletonBone('Belly_02', 'Belly_02', 'SPINE2'),
    SkeletonBone('Breast_00.L', 'Breast_L_00', 'Chest'),
    SkeletonBone('Breast_01.L', 'Breast_L_01', 'Breast_00.L'),
    SkeletonBone('Breast_02.L', 'Breast_L_02', 'Breast_01.L'),
    SkeletonBone('Breast_00.R', 'Breast_R_00', 'Chest'),
    SkeletonBone('Breast_01.R', 'Breast_R_01', 'Breast_00.R'),
    SkeletonBone('Breast_02.R', 'Breast_R_02', 'Breast_01.R'),
    SkeletonBone('Tongue_00', 'Tongue_00', 'HEAD'),
    SkeletonBone('Tongue_01', 'Tongue_01', 'Tongue_00'),
    SkeletonBone('Tongue_02', 'Tongue_02', 'Tongue_01'),
    SkeletonBone('Tongue_03', 'Tongue_03', 'Tongue_02'),
    SkeletonBone('Tongue_04', 'Tongue_04', 'Tongue_03'),
    SkeletonBone('Breast_CBP_00.L', 'Breast_CBP_L_00', 'Chest'),
    SkeletonBone('Breast_CBP_01.L', 'Breast_CBP_L_01', 'Breast_CBP_00.L'),
    SkeletonBone('Breast_CBP_02.L', 'Breast_CBP_L_02', 'Breast_CBP_01.L'),
    SkeletonBone('Breast_CBP_00.R', 'Breast_CBP_R_00', 'Chest'),
    SkeletonBone('Breast_CBP_01.R', 'Breast_CBP_R_01', 'Breast_CBP_00.R'),
    SkeletonBone('Breast_CBP_02.R', 'Breast_CBP_R_02', 'Breast_CBP_01.R'),
    SkeletonBone('Penis_Balls_CBP_01', 'Penis_Balls_CBP_01', 'Pelvis'),
    SkeletonBone('Penis_Balls_CBP_02', 'Penis_Balls_CBP_02', 'Penis_Balls_CBP_01'),
    SkeletonBone('Butt_CBP_01.L', 'Butt_CBP_L_01', 'Pelvis'),
    SkeletonBone('Butt_CBP_01.R', 'Butt_CBP_R_01', 'Pelvis'),
    SkeletonBone('Thigh_CBP_F_01.R', 'Thigh_CBP_R_F_01', 'Leg_Thigh_skin.R'),
    SkeletonBone('Thigh_CBP_F_02.R', 'Thigh_CBP_R_F_02', 'Thigh_CBP_F_01.R'),
    SkeletonBone('Thigh_CBP_B_01.R', 'Thigh_CBP_R_B_01', 'Leg_Thigh_skin.R'),
    SkeletonBone('Thigh_CBP_B_02.R', 'Thigh_CBP_R_B_02', 'Thigh_CBP_B_01.R'),
    SkeletonBone('Thigh_CBP_F_01.L', 'Thigh_CBP_L_F_01', 'LLeg_Thigh_skin'),
    SkeletonBone('Thigh_CBP_F_02.L', 'Thigh_CBP_L_F_02', 'Thigh_CBP_F_01.L'),
    SkeletonBone('Thigh_CBP_B_01.L', 'Thigh_CBP_L_B_01', 'LLeg_Thigh_skin'),
    SkeletonBone('Thigh_CBP_B_02.L', 'Thigh_CBP_L_B_02', 'Thigh_CBP_B_01.L'),
    SkeletonBone('Breast_CBP_03.R', 'Breast_CBP_R_03', 'Breast_CBP_02.R'),
    SkeletonBone('Breast_CBP_04.R', 'Breast_CBP_R_04', 'Breast_CBP_03.R'),
    SkeletonBone('Breast_CBP_03_OFFSET.L', 'Breast_CBP_L_03_OFFSET', 'Breast_CBP_02.L'),
    SkeletonBone('Breast_CBP_03.L', 'Breast_CBP_L_03', 'Breast_CBP_03_OFFSET.L'),
    SkeletonBone('Breast_CBP_04_OFFSET.L', 'Breast_CBP_L_04_OFFSET', 'Breast_CBP_03.L'),
    SkeletonBone('Breast_CBP_04.L', 'Breast_CBP_L_04', 'Breast_CBP_04_OFFSET.L'),
    SkeletonBone('Penis_CBP_00', 'Penis_CBP_00', 'Pelvis'),
    SkeletonBone('Penis_CBP_01', 'Penis_CBP_01', 'Penis_CBP_00'),
    SkeletonBone('Penis_CBP_02', 'Penis_CBP_02', 'Penis_CBP_01'),
    SkeletonBone('Penis_CBP_03', 'Penis_CBP_03', 'Penis_CBP_02'),
    SkeletonBone('Penis_CBP_04', 'Penis_CBP_04', 'Penis_CBP_03'),
    SkeletonBone('Penis_CBP_05', 'Penis_CBP_05', 'Penis_CBP_04'),
    SkeletonBone('Vagina_CBP_00', 'Vagina_CBP_00', 'Pelvis'),
    SkeletonBone('Vagina_CBP_01.L', 'Vagina_CBP_L_01', 'Vagina_CBP_00'),
    SkeletonBone('Vagina_CBP_02.L', 'Vagina_CBP_L_02', 'Vagina_CBP_01.L'),
    SkeletonBone('Vagina_CBP_01.R', 'Vagina_CBP_R_01', 'Vagina_CBP_00'),
    SkeletonBone('Vagina_CBP_02.R', 'Vagina_CBP_R_02', 'Vagina_CBP_01.R'),
    SkeletonBone('Anus_CBP_00', 'Anus_CBP_00', 'Pelvis'),
    SkeletonBone('Anus_CBP_01', 'Anus_CBP_01', 'Anus_CBP_00'),
    SkeletonBone('Anus_CBP_02', 'Anus_CBP_02', 'Anus_CBP_00'),
    SkeletonBone('Anus_CBP_034.R', 'Anus_CBP_03', 'Anus_CBP_00'),
    SkeletonBone('Anus_CBP_034.L', 'Anus_CBP_04', 'Anus_CBP_00'),
    SkeletonBone('Bone_Cloth_H_001', 'Bone_Cloth_H_001', 'Spine1_Rear_skin'),
    SkeletonBone('Bone_Cloth_H_002', 'Bone_Cloth_H_002', 'Bone_Cloth_H_001'),
    SkeletonBone('Bone_Cloth_H_003', 'Bone_Cloth_H_003', 'Bone_Cloth_H_002')]

fo4FaceBones = [
    SkeletonBone('HEAD', 'HEAD', None),
    SkeletonBone('skin_bone_C_MasterEyebrow', 'skin_bone_C_MasterEyebrow', 'HEAD'),
    SkeletonBone('Head_skin', 'Head_skin', 'HEAD'),
    SkeletonBone('Arm_Collarbone_skin.L', 'LArm_Collarbone_skin', 'HEAD'),
    SkeletonBone('Neck1_skin', 'Neck1_skin', 'HEAD'),
    SkeletonBone('Neck_Low_skin', 'Neck_Low_skin', 'HEAD'),
    SkeletonBone('Neck_skin', 'Neck_skin', 'HEAD'),
    SkeletonBone('Arm_Collarbone_skin.R', 'RArm_Collarbone_skin', 'HEAD'),
    SkeletonBone("skin_bone_C_AdamsApple", "skin_bone_C_Adam'sApple", 'HEAD'),
    SkeletonBone('skin_bone_C_Chin', 'skin_bone_C_Chin', 'HEAD'),
    SkeletonBone('skin_bone_C_EyebrowMid', 'skin_bone_C_EyebrowMid', 'HEAD'),
    SkeletonBone('skin_bone_C_ForeheadMid', 'skin_bone_C_ForeheadMid', 'HEAD'),
    SkeletonBone('skin_bone_C_MasterBot', 'skin_bone_C_MasterBot', 'HEAD'),
    SkeletonBone('skin_bone_C_MasterMouth', 'skin_bone_C_MasterMouth', 'HEAD'),
    SkeletonBone('skin_bone_C_MasterNose', 'skin_bone_C_MasterNose', 'HEAD'),
    SkeletonBone('skin_bone_C_MouthBot', 'skin_bone_C_MouthBot', 'HEAD'),
    SkeletonBone('skin_bone_C_MouthTop', 'skin_bone_C_MouthTop', 'HEAD'),
    SkeletonBone('skin_bone_C_Nose', 'skin_bone_C_Nose', 'HEAD'),
    SkeletonBone('skin_bone_C_Nose_Bridge', 'skin_bone_C_Nose_Bridge', 'HEAD'),
    SkeletonBone('skin_bone_Cheek.L', 'skin_bone_L_Cheek', 'HEAD'),
    SkeletonBone('skin_bone_Cheekbone.L', 'skin_bone_L_Cheekbone', 'HEAD'),
    SkeletonBone('skin_bone_CheekBoneBack.L', 'skin_bone_L_CheekBoneBack', 'HEAD'),
    SkeletonBone('skin_bone_Dimple.L', 'skin_bone_L_Dimple', 'HEAD'),
    SkeletonBone('skin_bone_Ear.L', 'skin_bone_L_Ear', 'HEAD'),
    SkeletonBone('skin_bone_EarBot.L', 'skin_bone_L_EarBot', 'HEAD'),
    SkeletonBone('skin_bone_EarMid.L', 'skin_bone_L_EarMid', 'HEAD'),
    SkeletonBone('skin_bone_EarTop.L', 'skin_bone_L_EarTop', 'HEAD'),
    SkeletonBone('skin_bone_Eye.L', 'skin_bone_L_Eye', 'HEAD'),
    SkeletonBone('skin_bone_EyebrowIn.L', 'skin_bone_L_EyebrowIn', 'HEAD'),
    SkeletonBone('skin_bone_EyebrowOut.L', 'skin_bone_L_EyebrowOut', 'HEAD'),
    SkeletonBone('skin_bone_Eyelid_Bot.L', 'skin_bone_L_Eyelid_Bot', 'HEAD'),
    SkeletonBone('skin_bone_Eyelid_Top.L', 'skin_bone_L_Eyelid_Top', 'HEAD'),
    SkeletonBone('skin_bone_EyeUnder.L', 'skin_bone_L_EyeUnder', 'HEAD'),
    SkeletonBone('skin_bone_JawMid.L', 'skin_bone_L_JawMid', 'HEAD'),
    SkeletonBone('skin_bone_JawSide.L', 'skin_bone_L_JawSide', 'HEAD'),
    SkeletonBone('skin_bone_MouthBot.L', 'skin_bone_L_MouthBot', 'HEAD'),
    SkeletonBone('skin_bone_MouthCorner.L', 'skin_bone_L_MouthCorner', 'HEAD'),
    SkeletonBone('skin_bone_MouthTop.L', 'skin_bone_L_MouthTop', 'HEAD'),
    SkeletonBone('skin_bone_NeckMuscle.L', 'skin_bone_L_NeckMuscle', 'HEAD'),
    SkeletonBone('skin_bone_Neckmuscle2.L', 'skin_bone_L_Neckmuscle2', 'HEAD'),
    SkeletonBone('skin_bone_Nostril.L', 'skin_bone_L_Nostril', 'HEAD'),
    SkeletonBone('skin_bone_SideNodeFat.L', 'skin_bone_L_SideNodeFat', 'HEAD'),
    SkeletonBone('skin_bone_Temple.L', 'skin_bone_L_Temple', 'HEAD'),
    SkeletonBone('skin_bone_Cheek.R', 'skin_bone_R_Cheek', 'HEAD'),
    SkeletonBone('skin_bone_Cheekbone.R', 'skin_bone_R_Cheekbone', 'HEAD'),
    SkeletonBone('skin_bone_CheekBoneBack.R', 'skin_bone_R_CheekBoneBack', 'HEAD'),
    SkeletonBone('skin_bone_Dimple.R', 'skin_bone_R_Dimple', 'HEAD'),
    SkeletonBone('skin_bone_Ear.R', 'skin_bone_R_Ear', 'HEAD'),
    SkeletonBone('skin_bone_EarBot.R', 'skin_bone_R_EarBot', 'HEAD'),
    SkeletonBone('skin_bone_EarMid.R', 'skin_bone_R_EarMid', 'HEAD'),
    SkeletonBone('skin_bone_EarTop.R', 'skin_bone_R_EarTop', 'HEAD'),
    SkeletonBone('skin_bone_Eye.R', 'skin_bone_R_Eye', 'HEAD'),
    SkeletonBone('skin_bone_EyebrowIn.R', 'skin_bone_R_EyebrowIn', 'HEAD'),
    SkeletonBone('skin_bone_EyebrowOut.R', 'skin_bone_R_EyebrowOut', 'HEAD'),
    SkeletonBone('skin_bone_Eyelid_Bot.R', 'skin_bone_R_Eyelid_Bot', 'HEAD'),
    SkeletonBone('skin_bone_Eyelid_Top.R', 'skin_bone_R_Eyelid_Top', 'HEAD'),
    SkeletonBone('skin_bone_EyeUnder.R', 'skin_bone_R_EyeUnder', 'HEAD'),
    SkeletonBone('skin_bone_JawMid.R', 'skin_bone_R_JawMid', 'HEAD'),
    SkeletonBone('skin_bone_JawSide.R', 'skin_bone_R_JawSide', 'HEAD'),
    SkeletonBone('skin_bone_MouthBot.R', 'skin_bone_R_MouthBot', 'HEAD'),
    SkeletonBone('skin_bone_MouthCorner.R', 'skin_bone_R_MouthCorner', 'HEAD'),
    SkeletonBone('skin_bone_MouthTop.R', 'skin_bone_R_MouthTop', 'HEAD'),
    SkeletonBone('skin_bone_NeckMuscle.R', 'skin_bone_R_NeckMuscle', 'HEAD'),
    SkeletonBone('skin_bone_Neckmuscle2.R', 'skin_bone_R_Neckmuscle2', 'HEAD'),
    SkeletonBone('skin_bone_Nostril.R', 'skin_bone_R_Nostril', 'HEAD'),
    SkeletonBone('skin_bone_SideNodeFat.R', 'skin_bone_R_SideNodeFat', 'HEAD'),
    SkeletonBone('skin_bone_Temple.R', 'skin_bone_R_Temple', 'HEAD')]

fo4Expressions = ['UprLipRollOut', 'UprLipRollIn', 'UprLipFunnel', 'StickyLips', 
    'RUprLipUp', 'RUprLipDn', 'RUprLidUp', 'RUprLidDn', 'RSmile', 'ROutBrowDn', 
    'RNoseUp', 'RMidBrowUp', 'RMidBrowDn', 'RLwrLipUp', 'RLwrLipDn', 'RLwrLidUp', 
    'RLwrLidDn', 'RLipCornerOut', 'RLipCornerIn', 'RJaw', 'RFrown', 'RCheekUp', 
    'RBrowOutUp', 'Pucker', 'JawOpen', 'JawFwd', 'BrowSqueeze', 'LUprLipUp', 
    'LUprLipDn', 'LUprLidUp', 'LUprLidDn', 'LSmile', 'LOutBrowDn', 'LNoseUp', 
    'LMidBrowUp', 'LMidBrowDn', 'LLwrLipUp', 'LLwrLipDn', 'LLwrLidUp', 'LLwrLidDn', 
    'LLipCornerOut', 'LLipCornerIn', 'LJaw', 'LFrown', 'LCheekUp', 'LBrowOutUp',
    'LwrLipRollOut', 'LwrLipFunnel', 'LwrLipRollIn'
    ]

fo4Dismember = [
    BodyPart(0xffffffff, "FO4 1"),
    BodyPart(0xffffffff, "FO4 Human Arm.R"),
    BodyPart(0xffffffff, "FO4 Human Arm.L"),
    BodyPart(0xffffffff, "FO4 Human Leg.R"),
    BodyPart(0xffffffff, "FO4 Human Leg.L"),
    BodyPart(0x86b72980, "FO4 Head/Hair", "FO4 1"),
    BodyPart(0x0155094f, "FO4 Neck", "FO4 1"),
    BodyPart(0x4630dac2, "FO4 Kne-Clf.L", "FO4 Human Leg.L"),
    BodyPart(0x22324321, "FO4 Kne-Clf.R", "FO4 Human Leg.R"),
    BodyPart(0x212251d8, "FO4 Lo Arm.L", "FO4 Human Arm.L"),
    BodyPart(0x6fc3fbb2, "FO4 Lo Arm.R", "FO4 Human Arm.R"),
    BodyPart(0xa3e42571, "FO4 Lo Ft-Ank.L", "FO4 Human Leg.L"),
    BodyPart(0xc7e6bc92, "FO4 Lo Ft-Ank.R", "FO4 Human Leg.R"),
    BodyPart(0xfc03dc25, "FO4 Up Arm.L", "FO4 Human Arm.L"),
    BodyPart(0xb2e2764f, "FO4 Up Arm.R", "FO4 Human Arm.R"),
    BodyPart(0x865d8d9e, "FO4 Up Thi.L", "FO4 Human Leg.L"),
    BodyPart(0xbf3a3cc5, "FO4 Up Thi.R", "FO4 Human Leg.R"),
    BodyPart(0x2a549ee1, "FO4 Ghoul Up Arm.R", "FO4 Feral Ghoul 2"),
    BodyPart(0xf775131c, "FO4 Ghoul Lo Arm.R", "FO4 Feral Ghoul 2"),
    BodyPart(0x85342e3c, "FO4 Ghoul Hand.R", "FO4 Feral Ghoul 2"),
    BodyPart(0x4e560702, "FO4 Ghoul Up Arm.L", "FO4 Feral Ghoul 4"),
    BodyPart(0x93778aff, "FO4 Ghoul Lo Arm.L", "FO4 Feral Ghoul 4"),
    BodyPart(0x5ae407df, "FO4 Ghoul Hand.L", "FO4 Feral Ghoul 4"),
    BodyPart(0xc0f43cc3, "FO4 Death Claw Neck", "FO4 Death Claw 1"),
    BodyPart(0xf2ba1077, "FO4 Death Claw Up-Arm.R", "FO4 Death Claw 2"),
    BodyPart(0xf4e10d0d, "FO4 Death Claw Elbow-4Arm.R", "FO4 Death Claw 2"),
    BodyPart(0xe2da5319, "FO4 Death Claw Hand.R", "FO4 Death Claw 2"),
    BodyPart(0x17932e95, "FO4 Death Claw Up-Arm.L", "FO4 Death Claw 4"),
    BodyPart(0x0861e2c0, "FO4 Death Claw Elbow-4Arm.L", "FO4 Death Claw 4"),
    BodyPart(0x8beb7000, "FO4 Death Claw Hand.L", "FO4 Death Claw 4"),
    BodyPart(0x9af9d18c, "FO4 Death Claw p Thi.R", "FO4 Death Claw 5"),
    BodyPart(0x8e0daa93, "FO4 Death Claw Lo Leg.R", "FO4 Death Claw 5"),
    BodyPart(0x6bd95520, "FO4 Death Claw Lo Ft.R", "FO4 Death Claw 5"),
    BodyPart(0xa325b267, "FO4 Death Claw Lo Thi.L", "FO4 Death Claw 6"),
    BodyPart(0x51dd8370, "FO4 Death Claw Lo Leg.L", "FO4 Death Claw 6"),
    BodyPart(0xb4097cc3, "FO4 Death Claw Lo Ft.L", "FO4 Death Claw 6"),
    BodyPart(0x9af9d18c, "FO4 Ghoul Up Thi.R", "FO4 Feral Ghoul 5"),
    BodyPart(0x8e0daa93, "FO4 Ghoul Lo Leg.R", "FO4 Feral Ghoul 5"),
    BodyPart(0x6bd95520, "FO4 Ghoul Lo Ft.R", "FO4 Feral Ghoul 5"),
    BodyPart(0xa325b267, "FO4 Ghoul Lo Thi.L", "FO4 Feral Ghoul 6"),
    BodyPart(0x51dd8370, "FO4 Ghoul Lo Leg.L", "FO4 Feral Ghoul 6"),
    BodyPart(0xb4097cc3, "FO4 Ghoul Lo Ft.L", "FO4 Feral Ghoul 6"),
    BodyPart(0x99338c09, "FO4 Mut Hound Fr Up Leg.L", "FO4 Super Mutant Hound 3"),
    BodyPart(0x7491a630, "FO4 Mut Hound Fr Lo Leg.L", "FO4 Super Mutant Hound 3"),
    BodyPart(0x8a99ba3f, "FO4 Mut Hound Fr Foot.L", "FO4 Super Mutant Hound 3"),
    BodyPart(0xa7860026, "FO4 Mut Hound Bk Thigh.L", "FO4 Super Mutant Hound 4"),
    BodyPart(0xaf6a52d7, "FO4 Mut Hound Bk Knee.L", "FO4 Super Mutant Hound 4"),
    BodyPart(0xb42c3610, "FO4 Mut Hound Bk Ankle.L", "FO4 Super Mutant Hound 4"),
    BodyPart(0x6e284ec0, "FO4 Mut Hound Bk Foot.L", "FO4 Super Mutant Hound 4"),
    BodyPart(0x0e97871c, "FO4 Mut Hound Bk Thigh.R", "FO4 Super Mutant Hound 5"),
    BodyPart(0x02433b3b, "FO4 Mut Hound Bk Knee.R", "FO4 Super Mutant Hound 5"),
    BodyPart(0x1d3db12a, "FO4 Mut Hound Bk Ankle.R", "FO4 Super Mutant Hound 5"),
    BodyPart(0x20c9e4aa, "FO4 Mut Hound Bk Foot.R", "FO4 Super Mutant Hound 5"),
    BodyPart(0x5f96443c, "FO4 Mut Hound Fr Up Leg.R", "FO4 Super Mutant Hound 6"),
    BodyPart(0xdd80210a, "FO4 Mut Hound Fr Lo Leg.R", "FO4 Super Mutant Hound 6"),
    BodyPart(0x4c3c720a, "FO4 Mut Hound Fr Foot.R", "FO4 Super Mutant Hound 6"),
    BodyPart(0xa5f4be71, "FO4 Mirelurk Fr Up Arm.R", "FO4 Mirelurk 2"),
    BodyPart(0x99eb64eb, "FO4 Mirelurk Fr Lo Arm.R", "FO4 Mirelurk 2"),
    BodyPart(0x3c9df64f, "FO4 Mirelurk Claw.R", "FO4 Mirelurk 2"),
    BodyPart(0x40f66ca4, "FO4 Mirelurk Shoulder.L", "FO4 Mirelurk 4"),
    BodyPart(0xc1f62792, "FO4 Mirelurk Up Arm.L", "FO4 Mirelurk 4"),
    BodyPart(0xf0da47f2, "FO4 Mirelurk Elbow.L", "FO4 Mirelurk 4"),
    BodyPart(0x55acd556, "FO4 Mirelurk Claw.L", "FO4 Mirelurk 4"),
    BodyPart(0x064f59cd, "FO4 Mirelurk Fr Hip.R", "FO4 Mirelurk 5"),
    BodyPart(0x5b033df6, "FO4 Mirelurk Fr Thigh.R", "FO4 Mirelurk 5"),
    BodyPart(0x15fc7bad, "FO4 Mirelurk Calf.R", "FO4 Mirelurk 5"),
    BodyPart(0xf028841e, "FO4 Mirelurk Foot.R", "FO4 Mirelurk 5"),
    BodyPart(0xf62a541a, "FO4 Mirelurk Hip-Thigh.L", "FO4 Mirelurk 6"),
    BodyPart(0x5b1dd1c7, "FO4 Mirelurk Kne-Clf.L", "FO4 Mirelurk 6"),
    BodyPart(0xbec92e74, "FO4 Mirelurk Fr Foot.L", "FO4 Mirelurk 6"),
    BodyPart(0xfc5546b8, "FO4 Mirelurk Bk Hip-Thigh.R", "FO4 Mirelurk 8"),
    BodyPart(0x24a15449, "FO4 Mirelurk Bk Kne-Clf.R", "FO4 Mirelurk 8"),
    BodyPart(0xc175abfa, "FO4 Mirelurk Bk Foot.R", "FO4 Mirelurk 8"),
    BodyPart(0xb2b4ecd2, "FO4 Mirelurk Bk Hip-Thigh.L", "FO4 Mirelurk 9"),
    BodyPart(0xc1886aab, "FO4 Mirelurk Bk Kne-Clf.L", "FO4 Mirelurk 9"),
    BodyPart(0x245c9518, "FO4 Mirelurk Bk Foot.L", "FO4 Mirelurk 9"),
    BodyPart(0x5530c47b, "FO4 Dog Fr Knee.L", "FO4 Dog 3"),
    BodyPart(0xcc3995c1, "FO4 Dog Fr Calf.L", "FO4 Dog 3"),
    BodyPart(0xbd2750cf, "FO4 Dog Fr Heel+Arch.L", "FO4 Dog 3"),
    BodyPart(0x77fe1ec8, "FO4 Dog Fr Paw.L", "FO4 Dog 3"),
    BodyPart(0x52f7244b, "FO4 Dog Bk Knee.L", "FO4 Dog 4"),
    BodyPart(0xcbfe75f1, "FO4 Dog Bk Calf.L", "FO4 Dog 4"),
    BodyPart(0xfe31ace4, "FO4 Dog Bk Heel+Arch.L", "FO4 Dog 4"),
    BodyPart(0x08eb5fa0, "FO4 Dog Bk Paw.L", "FO4 Dog 4"),
    BodyPart(0x8d270da8, "FO4 Dog Bk Knee.R", "FO4 Dog 5"),
    BodyPart(0x142e5c12, "FO4 Dog Bk Calf+Heel.R", "FO4 Dog 5"),
    BodyPart(0x9a333507, "FO4 Dog Bk Arch.R", "FO4 Dog 5"),
    BodyPart(0x61da7cb9, "FO4 Dog Bk Paw.R", "FO4 Dog 5"),
    BodyPart(0x8ae0ed98, "FO4 Dog Fr Knee.R", "FO4 Dog 6"),
    BodyPart(0x13e9bc22, "FO4 Dog Fr Calf.R", "FO4 Dog 6"),
    BodyPart(0xd925c92c, "FO4 Dog Fr Heel+Arch.R", "FO4 Dog 6"),
    BodyPart(0x1ecf3dd1, "FO4 Dog Fr Paw.R", "FO4 Dog 6"),
    BodyPart(0x8c5ae189, "FO4 Behemoth Arm+Elbow.R", "FO4 Behemoth 2"),
    BodyPart(0x071dfd97, "FO4 Behemoth 4 Arm.R", "FO4 Behemoth 2"),
    BodyPart(0xded0fadf, "FO4 Behemoth Hand.R", "FO4 Behemoth 2"),
    BodyPart(0xc2bb4be3, "FO4 Behemoth Arm+Elbow.L", "FO4 Behemoth 4"),
    BodyPart(0x3e7a4ccc, "FO4 Behemoth 4 Arm.L", "FO4 Behemoth 4"),
    BodyPart(0xe7b74b84, "FO4 Behemoth Hand.L", "FO4 Behemoth 4"),
    BodyPart(0xa411c600, "FO4 Behemoth Calf.R", "FO4 Behemoth 5"),
    BodyPart(0xac900af3, "FO4 Behemoth Foot.R", "FO4 Behemoth 5"),
    BodyPart(0xc0135fe3, "FO4 Behemoth Calf.L", "FO4 Behemoth 6"),
    BodyPart(0x95f7bba8, "FO4 Behemoth Foot.R", "FO4 Behemoth 6"),
    BodyPart(0x3d6644aa, "FO4 Robot 3 Torso", "FO4 Robot 3")     
    ]

fo4Parts = [
    BodyPart(0xffffffff, "FO4 1 | Head/Hair"),
    BodyPart(30, "FO4 30 - Hair Top", material=0x86b72980),
    BodyPart(31, "FO4 31 - Hair Long", material=0x86b72980),
    BodyPart(32, "FO4 32 - Head", material=0x86b72980),
    BodyPart(33, "FO4 33 - Body"),
    BodyPart(35, "FO4 35 - R Hand"),
    BodyPart(36, "FO4 36 - [U] Torso"),
    BodyPart(37, "FO4 37 - [U] L Arm"),
    BodyPart(38, "FO4 38 - [U] R Arm"),
    BodyPart(39, "FO4 39 - [U] L Leg"),
    BodyPart(40, "FO4 40 - [U] R Leg"),
    BodyPart(41, "FO4 41 - [A] Torso"),
    BodyPart(42, "FO4 42 - [A] L Arm"),
    BodyPart(43, "FO4 43 - [A] R Arm"),
    BodyPart(44, "FO4 44 - [A] L Leg"),
    BodyPart(45, "FO4 45 - [A] R Leg"),
    BodyPart(46, "FO4 46 - Headband", material=0x86b72980),
    BodyPart(47, "FO4 47 - Eyes", "FO4 1 | Head/Hair"),
    BodyPart(48, "FO4 48 - Beard", "FO4 1 | Head/Hair"),
    BodyPart(49, "FO4 49 - Mouth", "FO4 1 | Head/Hair"),
    BodyPart(50, "FO4 50 - Neck", "FO4 1 | Neck"),
    BodyPart(51, "FO4 51 - Ring"),
    BodyPart(52, "FO4 52 - Scalp", "FO4 1 | Head/Hair"),
    BodyPart(53, "FO4 53 - Decapitation"),
    BodyPart(54, "FO4 54 - Unnamed"),
    BodyPart(55, "FO4 55 - Unnamed"),
    BodyPart(56, "FO4 56 - Unnamed"),
    BodyPart(57, "FO4 57 - Unnamed"),
    BodyPart(58, "FO4 58 - Unnamed"),
    BodyPart(59, "FO4 59 - Shield"),
    BodyPart(60, "FO4 60 - Pipboy"),
    BodyPart(61, "FO4 61 - FX")]

fo4chargen_pat = re.compile("Type[0-9]+")

class FO4BoneDict(BoneDict):
    def chargen_filter(self, candidates):
        return set([c for c in candidates if fo4chargen_pat.search(c)])

fo4Dict = FO4BoneDict(fo4Bones, fo4Expressions, fo4Parts, fo4Dismember)
fo4FaceDict = FO4BoneDict(fo4FaceBones, fo4Expressions, fo4Parts, fo4Dismember)

gameSkeletons = {
    'SKYRIM': skyrimDict,
    'SKYRIMSE': skyrimDict,
    'FO4': fo4Dict,
    'FO3': fnvDict,
    'FONV': fnvDict}

if __name__ == "__main__":
# ######################################### #
#                                           #
#   FUNCTIONAL TESTS                        #
#                                           #
# ######################################### #

    import sys
    import os.path
    #sys.path.append(r"D:\OneDrive\Dev\PyNifly\PyNifly")
    #from pynifly import *

    # ####################################################################################
    print("--Can split verts of a triangularized plane")
    # Verts 4 & 5 are on a seam
    verts = [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (-1.0, 1.0, 0.0), (1.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)]
    weights = [{0: 0.4},
               {0: 0.6},
               {0: 1.0},
               {0: 0.8},
               {0: 0.3},
               {0: 0.1}]
    loops = [1, 5, 4,
             4, 2, 0,
             1, 3, 5,
             4, 5, 2]
    norms = [(0.0, 0.0, 2.0), (0.0, 0.0, 6.0), (0.0, 0.0, 5.0), 
             (0.0, 0.0, 5.0), (0.0, 0.0, 3.0), (0.0, 0.0, 1.0), 
             (0.0, 0.0, 2.0), (0.0, 0.0, 4.0), (0.0, 0.0, 6.0),
             (0.0, 0.0, 5.0), (0.0, 0.0, 6.0), (0.0, 0.0, 3.0)]
    #norms = [(0.0, 0.0, 1.0), (0.0, 0.0, 2.0), (0.0, 0.0, 3.0), 
    #         (0.0, 0.0, 4.0), (0.0, 0.0, 5.0), (0.0, 0.0, 6.0)
    #         ]
    uvs = [(0.9, 0.1), (0.6, 0.9), (0.6, 0.1),
           (0.4, 0.1), (0.1, 0.9), (0.1, 0.1),
           (0.9, 0.1), (0.9, 0.9), (0.6, 0.9),
           (0.4, 0.1), (0.4, 0.9), (0.1, 0.9)]

    morphdict = {}
    morphdict["by2"] = [(v[0]*2, v[1]*2, v[2]*2) for v in verts]
    morphdict["by3"] = [(v[0]*3, v[1]*3, v[2]*3) for v in verts]
        
    # mesh_split_by_uv() splits the mesh along UV seams--any vert that has two 
    # different UV locations needs to be split
    mesh_split_by_uv(verts, norms, loops, uvs, weights, morphdict)

    # Vert 5 got split into 5 & 7. Data should be the same.
    assert len(verts) == 8, "Error: wrong number of verts after edge splitting"
    assert len(norms) == len(loops), "Error: Count of normals shouldn't change"
    assert len(weights) == 8, "Error: wrong number of weights after edge splitting"
    assert len(morphdict["by2"]) == 8, "Error wrong number of verts in morph after splitting"
    assert len(morphdict["by3"]) == 8, "Error wrong number of verts in morph after splitting"
    assert verts.count((0.0, 1.0, 0.0)) == 2, "Error: Duplicating vert on seam"
    assert verts.count((0.0, -1.0, 0.0)) == 2, "Error: Duplicating vert on seam"
    assert morphdict["by3"].count((0.0, -3.0, 0.0)) == 2, "Error: Duplicating vert on seam in morph"
    assert verts[5] == verts[7], "Error: Duplicating vert 5 to vert 7"
    assert weights[5] == weights[7], "Error: Duplicating weights correctly"
    # Any loop entry referencing vert 5 should have same UV location as one referencing 7
    assert loops[1] == 5 and loops[10] == 7 and uvs[1] != uvs[10], "Error: Duplicating UV locations correctly"


    print("""####################################################################################
    Game skeletons translate to and from blender conventions. This allows blender mirror operations
    to be smart.
    """)

    assert gameSkeletons["SKYRIM"].byBlender['NPC Finger11.L'].nif == 'NPC L Finger11 [LF11]', "Error: Bone not translated correctly"
    assert gameSkeletons["SKYRIM"].byNif['NPC L Finger11 [LF11]'].blender == 'NPC Finger11.L', "Error: Bone not translated correctly"
    assert gameSkeletons["FO4"].byBlender['Arm_Finger13.R'].nif == 'RArm_Finger13', "Error: Bone not translated correctly"
    assert gameSkeletons["FO4"].byNif['RArm_Finger13'].blender == 'Arm_Finger13.R', "Error: Bone not translated correctly"
    assert gameSkeletons["FO4"].byBlender['Arm_Finger51.R'].parent == gameSkeletons["FO4"].byBlender['Arm_Hand.R'], "Error: Parents not correct"
    assert gameSkeletons["SKYRIM"].blender_name('NPC L Finger20 [LF20]') == 'NPC Finger20.L', "Error: Name translation incorrect"
    assert gameSkeletons["SKYRIM"].nif_name('NPC Finger20.L') == 'NPC L Finger20 [LF20]', "Error: Name translation incorrect"
    assert gameSkeletons["FO4"].nif_name('FOOBAR') == 'FOOBAR', "Error: Name translation incorrect"
    

    print("""
##############################################################################
RotationMatrix provides handling for bone rotations and such.
""")
    rm = RotationMatrix([[-0.0072, 0.9995, -0.0313],
                         [-0.0496, -0.0316, -0.9983],
                         [-0.9987, -0.0056, 0.0498]])
    
    # by_vector creates a rotation matrix from a vector 
    assert rm.by_vector((5,0,0)) == (-0.036, -0.248, -4.9935), "Error: Applying rotation matrix"

    # identity is the do-nothing rotation
    # invert() is the inverse rotation
    identity = RotationMatrix()
    assert identity.invert() == identity, "Error: Inverting identity should give itself"

    # euler_deg() returns the rotation in euler degrees
    rm = RotationMatrix([(0,0,1), (1,0,0), (0,1,0)])
    assert rm.euler_deg() == (90.0, 90.0, 0), "Error: Euler degrees reflect same rotation"
    # No idea if this is actually correct, need to figure out rotations
    assert rm.invert().euler_deg() == (-90.0, 0, -90.0), "Error: Euler degrees reflect inverse rotation"

    rm = RotationMatrix.from_euler(0, 0, 0)
    assert rm == identity, "Error: null euler rotation generates null rotation"

    # Not working... what we want to do with blender
    bone_rot = (87.1, -1.8, -90.4)
    bone_mat = RotationMatrix.from_euler(bone_rot[0], bone_rot[1], bone_rot[2])
    rot_vec = bone_mat.by_vector((1, 0, 0))
    res_mat = RotationMatrix.from_vector(rot_vec)
    res_euler = res_mat.euler()

    # from_euler() creates a rotation matrix from euler angles
    r = RotationMatrix.from_euler(20, 30, 40)
    # rotation_vector() returns a vector showing a matrix's rotation
    # from_vector() creates a rotation matrix from a vector
    r1 = RotationMatrix.from_vector(r.rotation_vector())
    # So convert a rotation to a vector and back should be identity
    assert r == r1, "Error: Rotation vectors should be reversable"

    print("Matrixes can be multiplied, which allows trainsforms to be combined.")
    a = RotationMatrix([(1, 2, 3), (4, 5, 6), (7, 8, 9)])
    b = RotationMatrix([(10,20,30), (40, 50, 60), (70, 80, 90)])
    c = a.multiply(b)
    assert c == RotationMatrix([(300, 360, 420), (660, 810, 960), (1020, 1260, 1500)]), "Error: Matrix multiplication failure"

    print("Bones have transforms which are turned into head and tail positions")
    bone_mx = RotationMatrix.from_euler(30, 0, 0)
    print(f"bone_mx = \n{bone_mx}")
    bone_v = bone_mx.by_vector([1, 0, 0])
    print("Can re-create the rotation matrix from the vector")
    new_mx = RotationMatrix.from_vector([n * -1 for n in bone_v], 0)
    # Can't recreate the maxtrix because the vector loses info if the mx
    # rotates it about its own axis. Can code rotation in the lenght of the vector
    # but not convenient for blender. 
    # assert new_mx == bone_mx, "Error: can't recreate rotation matrix from vector"


    # ####################################################################################
    print(
        """
        gameSkeleton matches() function counts the bones that match bones inf the given set
        """)
    print("--Can get count of matching bones from skeleton")
    assert gameSkeletons["FO4"].matches(set(['Leg_Calf.R', 'Leg_Calf_skin.R', 'Leg_Calf_Low_skin.R', 'FOO'])) == 3, "Error: Skeletons should return correct bone match"


    # ####################################################################################
    print ("""
        BoneDict expression_filter returns just the expression morphs for the given game
        BoneDict chargen_filter returns just the chargen morphs for the given game.
            Note for FO4 these aren't predefined, but match *type#. 
        """)
    exprmorphs = set(['DialogueAnger', 'MoodFear', 'CombatShout', 'RUprLipDn', 'RUprLidUp', 'RUprLidDn'])
    assert fo4Dict.expression_filter(exprmorphs) == set(['RUprLipDn', 'RUprLidUp', 'RUprLidDn']), "ERROR: FO4 expression filter incorrect"
    assert skyrimDict.expression_filter(exprmorphs) == set(['DialogueAnger', 'MoodFear', 'CombatShout']), "ERROR: FO4 expression filter incorrect"
    assert fo4Dict.chargen_filter(set(['foo', 'barType1', 'fribble', 'Type45cat', 'aTypeB'])) == set(['barType1', 'Type45cat']), "ERROR: FO4 Chargen filter incorrect"
    
