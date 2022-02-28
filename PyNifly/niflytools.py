""" niflytools

    Utility functions and classes to support import/export
    Includes game-specific mesh information

"""

import os
from math import asin, acos, atan2, pi, sin, cos, radians, sqrt
import operator
from functools import reduce
import logging
import re
from pathlib import Path
from typing import Match

from nifdefs import ShaderFlags2

log = logging.getLogger("pynifly")


# ###################### FILE HANDLING ##################################

def extend_filenames(root, separator, files):
    """ Extend the given relative path names with the portion of the root before the separator.
        Separator is the name of a directory in the path """
    rootpath = Path(root)
    try:
        upperpath = list(map(lambda s: s.upper(), rootpath.parts))
        seploc = upperpath.index(separator.upper())
        sharedpart = rootpath.parents[len(rootpath.parts) - seploc - 1]
        return [(str(sharedpart / f) if len(f) > 0 else "") for f in files]
    except:
        return files

def check_files(files):
    """ Check that all files in the given list exist """
    if sum([len(f) for f in files]) == 0:
        return False
    else:
        exists = True
        for f in files:
            exists &= (os.path.exists(f) if len(f) > 0 else True)
        return exists

def missing_files(files):
    """ Returns a list containing the files in the given list that don't exist """
    return [x for x in files if not os.path.exists(x)]

def truncate_filename(filepath: str, root_dir: str)-> str:
    n = filepath.lower().find(root_dir.lower())
    if n < 0:
        return filepath
    else:
        return filepath[(n+len(root_dir)+1):]

# ################# VECTORS, ROTATION MATRICES, MATHY STUFF #################

# Yes, numpy does this but I hate layers and I needed to understand it anyway 

class Vector():
    """ General vector class of any dimension """
    def __init__(self, value=[0, 0, 0]):
        if type(value) == Vector:
            self.tuple = value.tuple
        else:
            self.tuple = list(value)

    def __getitem__(self, i):
        return self.tuple[i]

    def __len__(self):
        return len(self.tuple)

    def __str__(self):
        s = []
        for n in self.tuple:
            s.append(str(round(n,4)))
        return "Vector([" + ", ".join(s) + "])"

    def __repr__(self):
        return f"Vector({self.tuple})"

    @property
    def x(self):
        return self.tuple[0]

    @x.setter
    def x(self, value):
        self.tuple[0] = value

    @property
    def y(self):
        return self.tuple[1]

    @y.setter
    def y(self, value):
        self.tuple[1] = value

    @property
    def z(self):
        return self.tuple[2]

    @z.setter
    def z(self, value):
        self.tuple[2] = value

    def dot(self, other):
        """ Dot product of two vectors returns a scalar """
        return sum(map(lambda x: x[0]*x[1], zip(self.tuple, other.tuple)))

    def scale(self, scalefactor):
        return self.__class__(map(lambda x: x*scalefactor, self.tuple))

    def cross(self, other):
        """ Cross product only defined for 3D vectors """
        return self.__class__([self.y * other.z - self.z * other.y,
                               self.z * other.x - self.x * other.z,
                               self.x * other.y - self.y * other.x])

    def __add__(self, other):
        return self.__class__(map(sum, zip(self.tuple, other.tuple)))

    def __sub__(self, other):
        return self.__class__(map(lambda t: t[0]-t[1], zip(self.tuple, other.tuple)))

    def __eq__(self, other):
        """ Equals defined as approx equal, because that's most useful """
        return len(self.tuple) == len(other.tuple) and \
               reduce(operator.__and__, 
                      map(lambda a: round(a[0],4) == round(a[1],4), zip(self.tuple, other.tuple)))

    def __ne__(self, other):
        return not(self == other)

    @property
    def magnitude(self):
        return sqrt(sum(map(lambda x: x**2, self.tuple)))

    def normalize(self):
        v = self.tuple
        d = self.magnitude
        if d == 0:
            d = 1.0
        vnew = map(lambda x: x/d, v)
        return self.__class__(vnew)

class Quaternion(Vector):
    def __init__(self, value=[0, 0, 0, 0]):
        """ Quaternions represented as [angle, x, y, z] OR as [x, y, z] """
        l = list(value)
        if len(l) == 3:
            super().__init__([0, l[0], l[1], l[2]])
        else:
            super().__init__(l)

    @property
    def angle(self):
        return self.tuple[0]

    @property
    def vector(self):
        return Vector(self.tuple[1:4])

    @property
    def x(self):
        return self.tuple[1]

    @property
    def y(self):
        return self.tuple[2]

    @property
    def z(self):
        return self.tuple[3]

    def __str__(self):
        return f"Quarternion({self.tuple})"

    def __repr__(self):
        return f"Quarternion({self.tuple})"

    def __add__(self, other):
        return Quaternion([self.vector[0] + other.vector[0],
                           self.vector[1] + other.vector[1],
                           self.vector[2] + other.vector[2]],
                          self.angle + other.angle)

    #def __mul__(self, other):
    #    """ Multiplying quarternions returns a quarternion """
    #    return Quaternion(self.vector.cross(other.vector) 
    #                      + other.vector.scale(self.angle) 
    #                      + self.vector.scale(other.angle), 
    #                      self.angle*other.angle - self.vector.dot(other.vector))

    def __matmul__(self, other):
        """ Multiply quaternions (cross product) 
            can also multiply with Vector, which is treated as Quat with angle 0
         https://danceswithcode.net/engineeringnotes/quaternions/quaternions.html """
        r0, r1, r2, r3 = self.tuple
        if len(other) == 3:
            s0, s1, s2, s3 = (0, other[0], other[1], other[2])
        else:
            s0, s1, s2, s3 = other.tuple
        t0 = r0*s0 - r1*s1 - r2*s2 - r3*s3
        t1 = r0*s1 + r1*s0 - r2*s3 + r3*s2
        t2 = r0*s2 + r1*s3 + r2*s0 - r3*s1
        t3 = r0*s3 - r1*s2 + r2*s1 + r3*s0
        return Quaternion([t0, t1, t2, t3])

    #def hamilton_product(self, other):
    #    """ https://en.wikipedia.org/wiki/Quaternion#Hamilton_product """
    #    a1 = self.tuple[0]
    #    b1, c1, d1 = self.tuple[1:4]
    #    a2 = other.angle
    #    b2, c2, d2 = other.vector[:]
    #    a3 = a1*a2 - b1*b2 - c1*c2 - d1*d2
    #    b3 = a1*b2 + b1*a2 + c1*d2 - d1*c2
    #    c3 = a1*c2 - b1*d2 + c1*a2 + d1*b2
    #    d3 = a1*d2 + b1*c2 - c1*b2 + d1*a2
    #    return self.__class__([a3, b3, c3, d3])

    def invert(self):
        """ Inverse is a negation of the vector components 
         https://danceswithcode.net/engineeringnotes/quaternions/quaternions.html """
        return Quaternion([self.tuple[0], -self.tuple[1], -self.tuple[2], -self.tuple[3]])

    def normalize(self):
        v = self.vector.normalize()
        return self.__class__([self.angle, v[0], v[1], v[2]])

    #def invert(self):
    #    n = 1/(self.vector.x**2 + self.vector.y**2 + self.vector.z**2 + self.angle**2)
    #    return Quaternion(self.vector.scale(-n), self.angle*n)

    #def cross(self, other):
    #    cross_i = self.vector.cross(other.vector) + other.vector.scale(self.angle) + self.vector.scale(other.angle)
    #    cross_r = self.angle*other.angle - self.vector.dot(other.vector)
    #    return Quaternion(cross_i, cross_r)

    def rotate(self, v):
        """ Rotate the point represented by XYZ vector v """
        p = Quaternion([0, v[0], v[1], v[2]])
        v = self.invert() @ p @ self
        return v.vector

    @classmethod
    def make_rotation(cls, v):
        """ Makes a rotation quaternion from from angle-axis, v=[angle, x, y, z] """
        a = v[0]
        u = Vector(v[1:4]).normalize() 
        sf = sin(a/2)
        return cls([cos(a/2), u[0] * sf, u[1] * sf, u[2] * sf])

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

    @property
    def trace(self):
        """ Return the trace (sum of diagonals) of the matrix
            https://en.wikipedia.org/wiki/Rotation_matrix#Quaternion """
        m = self.matrix
        return m[0][0] + m[1][1] + m[2][2]

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

    @classmethod
    def from_euler(cls, xrot, yrot, zrot):
        """ Convert from blender-style euler angles (in degrees) to a matrix.
            Calculation from wikipedia (where else?)
            """
        return RotationMatrix.from_euler_rad(radians(xrot), radians(yrot), radians(zrot))

    @classmethod
    def from_euler_rad(cls, xrot, yrot, zrot):
        """ Convert from blender-style euler angles (in radians) to a matrix.
            Calculation from wikipedia (where else?)
            """
        c1 = cos(xrot)
        c2 = cos(yrot)
        c3 = cos(zrot)
        s1 = sin(xrot)
        s2 = sin(yrot)
        s3 = sin(zrot)
        
        res = [(c2 * c3,                   -s2,         c2 * s3),
               (s1 * s3 + c1 * c3 * s2,     c1 * c2,    c1 * s2 * s3 - c3 * s1),
               (c3 * s1 * s2 - c1 * s3,     c2 * s1,    c1 * c3 + s1 * s2 * s3)
               ]
        return RotationMatrix(res)

    @classmethod
    def from_quaternion(cls, quat):
        q0, q1, q2, q3 = quat.tuple
        r = RotationMatrix([
            [q0**2 + q1**2 - q2**2 - q3**2, 2*q1*q2 - 2*q0*q3, 2*q1*q3 + 2*q0*q2],
            [2*q1*q2 + 2*q0*q3, q0**2 - q1**2 + q2**2 - q3**2, 2*q2*q3 - 2*q0*q1],
            [2*q1*q3 - 2*q0*q2, 2*q2*q3 + 2*q0*q1, q0**2 - q1**2 - q2**2 + q3**2]
        ])
        #vx, vy, vz = self.vector[:]
        #a = self.angle
        #r = RotationMatrix([
        #    [1 - 2*(vy**2 + vz**2), 2*(vx*vy + vz*a), 2*vx*vz - vy*a],
        #    [2*(vx*vy - vz*a), 1 - 2*(vx**2 + vz**2), 2*(vy*vz + vx*a)],
        #    [2*(vx*vz + vy*a), 2*(vy*vz - vx*a), 1-2*(vx**2 + vy**2)]
        #    ])
        return r

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

    @property
    def largest_diagonal(self):
        m = self.matrix
        a = 0
        if m[1][1] > m[0][0]:
            a = 1
        if m[2][2] > m[a][a]:
            a = 2
        return a

    def quaternion(self):
        """ Return the rotation matrix as a quaternion """
        m = self.matrix
        t = self.trace
        #r = sqrt(1+t)
        #s = 1/(2*r)
        #w = r/2
        #x = s * (m[0][1] - m[1][2])
        #y = s * (m[0][2] - m[2][0])
        #z = s * (m[1][0] - m[0][1])
        a, b, c = ((0, 1, 2), (1, 2, 0), (2, 0, 1))[self.largest_diagonal]
        r = sqrt(1 + m[a][a] - m[b][b] - m[c][c])
        s = 1/(2*r)
        w = s * (m[c][b] - m[b][c])
        x = r/2
        y = s * (m[a][b] + m[b][a])
        z = s * (m[c][a] + m[a][c])
        return Quaternion([w, x, y, z])


    def rotation_vector(self):
        """ Return a rotation vector from the matrix """
        # Not sure this is really required now that we have quaternions
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
        return Vector([vec[0]*rm[0][0] + vec[1]*rm[0][1] + vec[2]*rm[0][2],
                vec[0]*rm[1][0] + vec[1]*rm[1][1] + vec[2]*rm[1][2],
                vec[0]*rm[2][0] + vec[1]*rm[2][1] + vec[2]*rm[2][2]])

    def rotate(self, vec):
        """ Rotate the given vector """
        return self.by_vector(vec)

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

    def __matmul__(self, other):
        return self.multiply(other)

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

def to_euler_angles(rm):
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

def to_euler_degrees(rm):
    angles = to_euler_angles(rm)
    return (angles[0] * 180.0/pi, angles[1] * 180.0/pi, angles[2] * 180.0/pi)
    
def make_rotation_matrix(yaw, pitch, roll):
	ch = cos(yaw)
	sh = sin(yaw)
	cp = cos(pitch)
	sp = sin(pitch)
	cb = cos(roll)
	sb = sin(roll)

	rot = ((ch * cb + sh * sp * sb,    sb * cp,    -sh * cb + ch * sp * sb),
           (-ch * sb + sh * sp * cb,      cb * cp,    sb * sh + ch * sp * cb),
           (sh * cp -sp, ch * cp))

	return rot


def store_transform(xf, vec3, mat3x3, scale):
    xf[0] = vec3[0]
    xf[1] = vec3[1]
    xf[2] = vec3[2]
    xf[3] = mat3x3[0][0]
    xf[4] = mat3x3[0][1]
    xf[5] = mat3x3[0][2]
    xf[6] = mat3x3[1][0]
    xf[7] = mat3x3[1][1]
    xf[8] = mat3x3[1][2]
    xf[9] = mat3x3[2][0]
    xf[10] = mat3x3[2][1]
    xf[11] = mat3x3[2][2]
    xf[12] = scale

class MatTransform():
    """ Matrix transform, including translation, rotation, and scale """

    def __init__(self, init_translation=None, init_rotation=None, init_scale=1.0):
        if init_translation:
            self.translation = Vector(init_translation)
        else:
            self.translation = Vector([0,0,0])
        self.rotation = RotationMatrix(init_rotation)
        self.scale = init_scale

    def __eq__(self, other):
        for v1, v2 in zip(self.translation, other.translation):
            if round(v1, 4) != round(v2, 4):
                return False
        if self.rotation != other.rotation:
            return False
        if round(self.scale, 4) != round(other.scale, 4):
            return False
        return True
        
    def __repr__(self):
        return "<" + repr(self.translation[:]) + ", " + \
            "(" + str(self.rotation.matrix) + "), " + \
            repr(self.scale) + ">"

    def __str__(self):
        return "MatTransform(" + str(self.translation[:]) + ",\n" + \
            str(self.rotation) + ",\n" + \
            str(self.scale) + ")"

    def __matmul__(self, other):
        """ Compose two transformation matrices OR a matrix with a vector """
        # Could be done with matrix multiplication instead
        if issubclass(other.__class__, MatTransform):
            new_t = self.rotation.rotate(other.translation).scale(self.scale) + self.translation
            new_r = self.rotation @ other.rotation
            return MatTransform(new_t, new_r, self.scale * other.scale)
        else:
            # Treat the other as a vector. Let it fail if other doesn't act like a vector.
            o1 = self.rotation.rotate(other)
            o1 = o1.scale(self.scale)
            return self.translation + o1
        

    def copy(self):
        the_copy = MatTransform(self.translation, self.rotation.copy(), self.scale)
        return the_copy

    def from_array(self, float_array):
        self.translation = Vector([float_array[0], float_array[1], float_array[2]])
        self.rotation = RotationMatrix(((float_array[3], float_array[4], float_array[5]),
                                      (float_array[6], float_array[7], float_array[8]),
                                      (float_array[9], float_array[10], float_array[11])))
        self.scale = float_array[12]
    
    def fill_buffer(self, buf):
        store_transform(buf, self.translation, self.rotation.matrix, self.scale)

    def invert(self):
        inverseXform = MatTransform()
        inverseXform.translation = self.translation.scale(-1)
        inverseXform.scale = 1/self.scale
        inverseXform.rotation = self.rotation.invert()
        return inverseXform

    def as_matrix(self):
        """ Return the transformation matrix as a 4x4 matrix """
        v = [[self.scale, 1, 1, self.translation[0]], [1, self.scale, 1, self.translation[1]], [1, 1, self.scale, self.translation[2]], [0, 0, 0, 1]]
        for i in range(0, 3):
            for j in range(0, 3):
                v[i][j] *= self.rotation.matrix[i][j]
        return v

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
        if material == 0 and (id > 200 or id < 0):
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
        self.expressions = set(set([m[0] for m in morph_list]) | set([m[1] for m in morph_list]))
        self.morph_dic_game = {}
        self.morph_dic_blender = {}
        for m in morph_list:
            self.morph_dic_game[m[0]] = m[1]
            self.morph_dic_blender[m[1]] = m[0]
        
        if type(part_list) == dict:
            self.parts = part_list
        else:
            for p in part_list:
                self.parts[p.name] = p
        if type(dismem_list == dict):
            self.dismem = dismem_list
        else:
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

    def dismember_bone(self, name):
        """ Look for 'name' in any of the bodyparts. Strip any trailing '.001'-type
            number before checking. """
        if name is None:
            return None
        name = blender_basename(name)
        if name in self.dismem:
            return self.dismem[name]
        return None

    def part_by_id(self, id):
        for n, bp in self.parts.items():
            if type(bp) == int:
                if bp == id:
                    return n
            else:
                if bp.id == id:
                    return bp
        return None

    def dismem_by_id(self, id):
        for n, bp in self.dismem.items():
            if bp == id:
                return n
        return None

    def expression_filter(self, name_set):
        """ Return the subset of name_set that are valid FO4 expressions, either blender or native form """
        return name_set.intersection(self.expressions)

    #def morph_to_game(self, morph_name): 
    #    """ Translate a set of expression morphs with Blender names to morphs with game names """
    #    if type(name_set) == type(''):

        return set([m[1] for m in self.morphs if m[0] in name_set or m[1] in name_set])

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

    ### XXXXX OBSOLETE
    def _print_with_parent(self, parent_name, print_list):
        for k, bp in self.dismem.items():
            if bp.parentname == parent_name and bp.name not in print_list:
                print(f"    {bp.name} [part={bp.id if bp.id < 256 else hex(bp.id)}, material={hex(bp.material)}]")
                print_list.add(bp.name)
            
    def dump(self):
        print_list = set()
        for k in sorted([bp.name for bp in fo4Dict.dismem.values() if bp.parentname == '']):
            if k not in print_list:
                print(k)
                print_list.add(k)
                self._print_with_parent(k, print_list)


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

skyrimExpressions = [
    ('Aah', 'Aah'), 
    ('BigAah', 'BigAah'), 
    ('Blink.L', 'BlinkLeft'), 
    ('Blink.R', 'BlinkRight'), 
    ('BMP', 'BMP'), 
    ('BrowDown.L', 'BrowDownLeft'), 
    ('BrowDown.R', 'BrowDownRight'), 
    ('BrowIn.L', 'BrowInLeft'), 
    ('BrowIn.R', 'BrowInRight'), 
    ('BrowUp.L', 'BrowUpLeft'), 
    ('BrowUp.R', 'BrowUpRight'), 
    ('ChJSh', 'ChJSh'), 
    ('CombatAnger', 'CombatAnger'), 
    ('CombatShout', 'CombatShout'), 
	('DialogueAnger', 'DialogueAnger'), 
	('DialogueDisgusted', 'DialogueDisgusted'), 
	('DialogueFear', 'DialogueFear'), 
	('DialogueHappy', 'DialogueHappy'), 
	('DialoguePuzzled', 'DialoguePuzzled'), 
	('DialogueSad', 'DialogueSad'), 
	('DialogueSurprise', 'DialogueSurprise'), 
	('DST', 'DST'), 
	('Eee', 'Eee'), 
	('Eh', 'Eh'), 
	('FV', 'FV'), 
	('I', 'I'), 
	('K', 'K'), 
    ('LookDown', 'LookDown'), 
	('Look.L', 'LookLeft'), 
	('Look.R', 'LookRight'), 
	('LookUp', 'LookUp'), 
	('MoodAnger', 'MoodAnger'), 
	('MoodDisgusted', 'MoodDisgusted'), 
	('MoodFear', 'MoodFear'), 
    ('MoodHappy', 'MoodHappy'), 
	('MoodPuzzled', 'MoodPuzzled'), 
	('MoodSad', 'MoodSad'), 
	('MoodSurprise', 'MoodSurprise'), 
	('N', 'N'), 
	('Oh', 'Oh'), 
	('OohQ', 'OohQ'), 
	('R', 'R'), 
	('SkinnyMorph', 'SkinnyMorph'),
    ('Squint.L', 'SquintLeft'), 
	('Squint.R', 'SquintRight'), 
	('Th', 'Th'), 
	('W', 'W'), 
	('VampireMorph', 'VampireMorph')]

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
    SkeletonBone('Arm_UpperTwist1_skin.L', 'LArm_UpperTwist1_skin', 'Arm_UpperTwist1.L'),
    SkeletonBone('Arm_UpperTwist1_skin.R', 'RArm_UpperTwist1_skin', 'Arm_UpperTwist1.R'),
    SkeletonBone('Arm_UpperTwist2_skin.L', 'LArm_UpperTwist2_skin', 'Arm_UpperTwist2.L'),
    SkeletonBone('Arm_UpperFat_skin.L', 'LArm_UpperFat_skin', 'Arm_UpperTwist2.L'),
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

fo4Expressions = [
    ('UprLipRollOut', 'UprLipRollOut'),
    ('UprLipRollIn', 'UprLipRollIn'),
    ('UprLipFunnel', 'UprLipFunnel'),
    ('StickyLips', 'StickyLips'),
    ('UprLipUp.R', 'RUprLipUp'),
    ('UprLipDn.R', 'RUprLipDn'),
    ('UprLidUp.R', 'RUprLidUp'),
    ('UprLidDn.R', 'RUprLidDn'),
    ('Smile.R', 'RSmile'),
    ('OutBrowDn.R', 'ROutBrowDn'),
    ('NoseUp.R', 'RNoseUp'),
    ('MidBrowUp.R', 'RMidBrowUp'),
    ('MidBrowDn.R', 'RMidBrowDn'),
    ('LwrLipUp.R', 'RLwrLipUp'),
    ('LwrLipDn.R', 'RLwrLipDn'),
    ('LwrLidUp.R', 'RLwrLidUp'),
    ('LwrLidDn.R', 'RLwrLidDn'),
    ('LipCornerOut.R', 'RLipCornerOut'),
    ('LipCornerIn.R', 'RLipCornerIn'),
    ('Jaw.R', 'RJaw'),
    ('Frown.R', 'RFrown'),
    ('CheekUp.R', 'RCheekUp'),
    ('BrowOutUp.R', 'RBrowOutUp'),
    ('Pucker', 'Pucker'),
    ('JawOpen', 'JawOpen'),
    ('JawFwd', 'JawFwd'),
    ('BrowSqueeze', 'BrowSqueeze'),
    ('UprLipUp.L', 'LUprLipUp'),
    ('UprLipDn.L', 'LUprLipDn'),
    ('UprLidUp.L', 'LUprLidUp'),
    ('UprLidDn.L', 'LUprLidDn'),
    ('Smile.L', 'LSmile'),
    ('OutBrowDn.L', 'LOutBrowDn'),
    ('NoseUp.L', 'LNoseUp'),
    ('MidBrowUp.L', 'LMidBrowUp'),
    ('MidBrowDn.L', 'LMidBrowDn'),
    ('LwrLipUp.L', 'LLwrLipUp'),
    ('LwrLipDn.L', 'LLwrLipDn'),
    ('LwrLidUp.L', 'LLwrLidUp'),
    ('LwrLidDn.L', 'LLwrLidDn'),
    ('LipCornerOut.L', 'LLipCornerOut'),
    ('LipCornerIn.L', 'LLipCornerIn'),
    ('Jaw.L', 'LJaw'),
    ('Frown.L', 'LFrown'),
    ('CheekUp.L', 'LCheekUp'),
    ('BrowOutUp.L', 'LBrowOutUp'),
    ('LwrLipRollOut', 'LwrLipRollOut'),
    ('LwrLipFunnel', 'LwrLipFunnel'),
    ('LwrLipRollIn', 'LwrLipRollIn')
    ]

fo4BoneIDs = {
    "Head": 0x86b72980,
    "Lo Arm.R": 0x6fc3fbb2,
    "Lo Arm.L": 0x212251d8,
    "Calf.R": 0x22324321,
    "Calf.L": 0x4630dac2,
    "Neck": 0x0155094f,
    "Up Arm.R": 0xb2e2764f, 
    "Hand.R": 0xB1EC5379,
    "Hand.L": 0xD5EECA9A, 
    "Foot.L": 0xa3e42571, 
    "Foot.R": 0xc7e6bc92, 
    "Up Arm.L": 0xfc03dc25, 
    "Thigh.L": 0x865d8d9e, 
    "Thigh.R": 0xbf3a3cc5, 
    "Ghoul Up Arm.R": 0x2a549ee1, 
    "Ghoul Lo Arm.R": 0xf775131c, 
    "Ghoul Hand.R": 0x85342e3c, 
    "Ghoul Up Arm.L": 0x4e560702,
    "Ghoul Lo Arm.L": 0x93778aff,
    "Ghoul Hand.L": 0x5ae407df, 
    "Death Claw Neck": 0xc0f43cc3,
    "Death Claw Up Arm.R": 0xf2ba1077,
    "Death Claw Elbow.R": 0xf4e10d0d,
    "Death Claw Hand.R": 0xe2da5319,
    "Death Claw Up Arm.L": 0x17932e95,
    "Death Claw Elbow.L": 0x0861e2c0,
    "Death Claw Hand.L": 0x8beb7000,
    "Ghoul Thigh.R": 0x9af9d18c,
    "Ghoul Calf.R": 0x8e0daa93,
    "Ghoul Foot.R": 0x6bd95520,
    "Ghoul Thigh.L": 0xa325b267,
    "Ghoul Calf.L": 0x51dd8370,
    "Ghoul Foot.L": 0xb4097cc3,
    "Mut Hound Fr Up Leg.L": 0x99338c09,
    "Mut Hound Fr Lo Leg.L": 0x7491a630,
    "Mut Hound Fr Foot.L": 0x8a99ba3f,
    "Mut Hound Bk Thigh.L": 0xa7860026,
    "Mut Hound Bk Knee.L": 0xaf6a52d7,
    "Mut Hound Bk Ankle.L": 0xb42c3610,
    "Mut Hound Bk Foot.L": 0x6e284ec0,
    "Mut Hound Bk Thigh.R": 0x0e97871c,
    "Mut Hound Bk Knee.R": 0x02433b3b,
    "Mut Hound Bk Ankle.R": 0x1d3db12a,
    "Mut Hound Bk Foot.R": 0x20c9e4aa,
    "Mut Hound Fr Up Leg.R": 0x5f96443c,
    "Mut Hound Fr Lo Leg.R": 0xdd80210a,
    "Mut Hound Fr Foot.R": 0x4c3c720a,
    "Mirelurk Fr Up Arm.R": 0xa5f4be71,
    "Mirelurk Fr Lo Arm.R": 0x99eb64eb,
    "Mirelurk Claw.R": 0x3c9df64f,
    "Mirelurk Shoulder.L": 0x40f66ca4,
    "Mirelurk Up Arm.L": 0xc1f62792,
    "Mirelurk Elbow.L": 0xf0da47f2,
    "Mirelurk Claw.L": 0x55acd556,
    "Mirelurk Fr Hip.R": 0x064f59cd,
    "Mirelurk Fr Thigh.R": 0x5b033df6,
    "Mirelurk Calf.R": 0x15fc7bad,
    "Mirelurk Foot.R": 0xf028841e,
    "Mirelurk Hip-Thigh.L": 0xf62a541a,
    "Mirelurk Kne-Clf.L": 0x5b1dd1c7,
    "Mirelurk Fr Foot.L": 0xbec92e74,
    "Mirelurk Bk Hip-Thigh.R": 0xfc5546b8,
    "Mirelurk Bk Kne-Clf.R": 0x24a15449,
    "Mirelurk Bk Foot.R": 0xc175abfa,
    "Mirelurk Bk Hip-Thigh.L": 0xb2b4ecd2,
    "Mirelurk Bk Kne-Clf.L": 0xc1886aab,
    "Mirelurk Bk Foot.L": 0x245c9518,
    "Dog Fr Knee.L": 0x5530c47b,
    "Dog Fr Calf.L": 0xcc3995c1,
    "Dog Fr Heel+Arch.L": 0xbd2750cf,
    "Dog Fr Paw.L": 0x77fe1ec8,
    "Dog Bk Knee.L": 0x52f7244b,
    "Dog Bk Calf.L": 0xcbfe75f1,
    "Dog Bk Heel+Arch.L": 0xfe31ace4,
    "Dog Bk Paw.L": 0x08eb5fa0,
    "Dog Bk Knee.R": 0x8d270da8,
    "Dog Bk Calf+Heel.R": 0x142e5c12,
    "Dog Bk Arch.R": 0x9a333507,
    "Dog Bk Paw.R": 0x61da7cb9,
    "Dog Fr Knee.R": 0x8ae0ed98,
    "Dog Fr Calf.R": 0x13e9bc22,
    "Dog Fr Heel+Arch.R": 0xd925c92c,
    "Dog Fr Paw.R": 0x1ecf3dd1,
    "Behemoth Arm+Elbow.R": 0x8c5ae189,
    "Behemoth 4 Arm.R": 0x071dfd97,
    "Behemoth Hand.R": 0xded0fadf,
    "Behemoth Arm+Elbow.L": 0xc2bb4be3,
    "Behemoth 4 Arm.L": 0x3e7a4ccc,
    "Behemoth Hand.L": 0xe7b74b84,
    "Behemoth Calf.R": 0xa411c600,
    "Behemoth Foot.R": 0xac900af3,
    "Behemoth Calf.L": 0xc0135fe3,
    "Behemoth Foot.R": 0x95f7bba8,
    "Robot 3 Torso": 0x3d6644aa,
    "HP-Neck": 0x3D6644AA
    }

fo4Dismember = [
    BodyPart(0xffffffff, "FO4 1"),
    BodyPart(0x86b72980, "FO4 Head/Hair", "FO4 1"),
    BodyPart(0xffffffff, "FO4 Human Arm.R"),
    BodyPart(0x6fc3fbb2, "FO4 Lo Arm.R", "FO4 Human Arm.R"),
    BodyPart(0xffffffff, "FO4 Human Arm.L"),
    BodyPart(0x212251d8, "FO4 Lo Arm.L", "FO4 Human Arm.L"),
    BodyPart(0xffffffff, "FO4 Human Leg.R"),
    BodyPart(0x22324321, "FO4 Kne-Clf.R", "FO4 Human Leg.R"),
    BodyPart(0xffffffff, "FO4 Human Leg.L"),
    BodyPart(0x4630dac2, "FO4 Kne-Clf.L", "FO4 Human Leg.L"),
    BodyPart(0xffffffff, "FO4 Feral Ghoul 2"),
    BodyPart(0xffffffff, "FO4 Feral Ghoul 4"),
    BodyPart(0xffffffff, "FO4 Death Claw 1"),
    BodyPart(0xffffffff, "FO4 Death Claw 2"),
    BodyPart(0xffffffff, "FO4 Death Claw 4"),
    BodyPart(0xffffffff, "FO4 Death Claw 5"),
    BodyPart(0xffffffff, "FO4 Death Claw 6"),
    BodyPart(0xffffffff, "FO4 Super Mutant Hound 3"),
    BodyPart(0xffffffff, "FO4 Super Mutant Hound 4"),
    BodyPart(0xffffffff, "FO4 Super Mutant Hound 5"),
    BodyPart(0xffffffff, "FO4 Super Mutant Hound 6"),
    BodyPart(0xffffffff, "FO4 Mirelurk 2"),
    BodyPart(0xffffffff, "FO4 Mirelurk 4"),
    BodyPart(0xffffffff, "FO4 Mirelurk 5"),
    BodyPart(0xffffffff, "FO4 Mirelurk 6"),
    BodyPart(0xffffffff, "FO4 Mirelurk 8"),
    BodyPart(0xffffffff, "FO4 Mirelurk 9"),
    BodyPart(0xffffffff, "FO4 Dog 3"),
    BodyPart(0xffffffff, "FO4 Dog 4"),
    BodyPart(0xffffffff, "FO4 Dog 5"),
    BodyPart(0xffffffff, "FO4 Dog 6"),
    BodyPart(0xffffffff, "FO4 Behemoth 2"),
    BodyPart(0xffffffff, "FO4 Behemoth 4"),
    BodyPart(0xffffffff, "FO4 Behemoth 5"),
    BodyPart(0xffffffff, "FO4 Behemoth 6"),
    BodyPart(0xffffffff, "FO4 Robot 3"),
    BodyPart(0xffffffff, 'FO4 Synth Torso'),
    BodyPart(0xffffffff, 'FO4 Synth Head'),
    BodyPart(0xffffffff, 'FO4 Synth Arm.L'),
    BodyPart(0xffffffff, 'FO4 Synth Arm.R'),
    BodyPart(0xffffffff, 'FO4 Synth Leg.L'),
    BodyPart(0xffffffff, 'FO4 Synth Leg.R'),
    BodyPart(0x0155094f, "FO4 Neck", "FO4 1"),
    BodyPart(0xffffffff, 'FO4 Supermutant Arm.R'),
    BodyPart(0xb2e2764f, "FO4 SM Arm 01.R", "FO4 Supermutant Arm.R"),
    BodyPart(0xb2e2764f, "FO4 SM Arm 02.R", "FO4 Supermutant Arm.R"),
    BodyPart(0x6fc3fbb2, "FO4 SM Arm 03.R", "FO4 Supermutant Arm.R"),
    BodyPart(0x6fc3fbb2, "FO4 SM Arm 04.R", "FO4 Supermutant Arm.R"),
    BodyPart(0xB1EC5379, "FO4 SM Hand.R", "FO4 Supermutant Arm.R"),
    BodyPart(0xffffffff, 'FO4 Supermutant Arm.L'),
    BodyPart(0xfc03dc25, "FO4 SM Arm 01.L", "FO4 Supermutant Arm.L"),
    BodyPart(0xfc03dc25, "FO4 SM Arm 02.L", "FO4 Supermutant Arm.L"),
    BodyPart(0x212251d8, "FO4 SM Arm 03.L", "FO4 Supermutant Arm.L"),
    BodyPart(0x212251d8, "FO4 SM Arm 04.L", "FO4 Supermutant Arm.L"),
    BodyPart(0xD5EECA9A, "FO4 SM Hand.L", "FO4 Supermutant Arm.L"),
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
    BodyPart(0x9af9d18c, "FO4 Death Claw Up Thi.R", "FO4 Death Claw 5"),
    BodyPart(0x8e0daa93, "FO4 Death Claw Lo Leg.R", "FO4 Death Claw 5"),
    BodyPart(0x6bd95520, "FO4 Death Claw Lo Ft.R", "FO4 Death Claw 5"),
    BodyPart(0xa325b267, "FO4 Death Claw Up Thi.L", "FO4 Death Claw 6"),
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
    BodyPart(0x3d6644aa, "FO4 Robot 3 Torso", "FO4 Robot 3"),
    BodyPart(30, 'FO4 30 - Synth Crotch', 'FO4 Synth Torso'),
    BodyPart(40, "FO4 40 - Synth Shoulder.R", 'FO4 Synth Torso'),
    BodyPart(50, "FO4 50 - Synth Side.L", 'FO4 Synth Torso'),
    BodyPart(60, "FO4 60 - Synth Belly", 'FO4 Synth Torso'),
    BodyPart(70, "FO4 70 - Synth Chest", 'FO4 Synth Torso'),
    BodyPart(80, "FO4 80 - Synth Shoulder.L", 'FO4 Synth Torso'),
    BodyPart(90, "FO4 90 - Synth Side.R", 'FO4 Synth Torso'),
    BodyPart(40, "FO4 40 - Synth Head Rear", 'FO4 Synth Head'),
    BodyPart(65, "FO4 65 - Synth Face", 'FO4 Synth Head'),
    BodyPart(66, "FO4 66 - Synth Ear.L", 'FO4 Synth Head'),
    BodyPart(67, "FO4 67 - Synth Ear.R", 'FO4 Synth Head'),
    BodyPart(90, "FO4 15 - Synth Foot.L", 'FO4 Synth Leg.L'),
    BodyPart(40, "FO4 40 - Synth Thigh.L", 'FO4 Synth Leg.L'),
    BodyPart(90, "FO4 90 - Synth Calf.L", 'FO4 Synth Leg.L'),
    BodyPart(30, 'FO4 30 - Synth Calf.R', 'FO4 Synth Leg.R'),
    BodyPart(50, "FO4 50 - Synth Foot.R", 'FO4 Synth Leg.R'),
    BodyPart(80, "FO4 80 - Synth Thigh.R", 'FO4 Synth Leg.R'),
    BodyPart(40, "FO4 40 - Synth Hand.L", 'FO4 Synth Arm.L'),
    BodyPart(80, "FO4 80 - Synth Arm.L", 'FO4 Synth Arm.L'),
    BodyPart(40, "FO4 40 - Synth Hand.R", 'FO4 Synth Arm.R'),
    BodyPart(90, "FO4 90 - Synth Arm.R", 'FO4 Synth Arm.R')
    ]

fo4Parts = {
    "Hair Top": 30,
    "Hair Long": 31,
    "Head": 32,
    "HP-Neck": 33,
    "Hand": 35,
    "[U] Torso": 36,
    "[U] L Arm": 37,
    "[U] R Arm": 38,
    "[U] L Leg": 39,
    "[U] R Leg": 40,
    "[A] Torso": 41,
    "[A] L Arm": 42,
    "[A] R Arm": 43,
    "[A] L Leg": 44,
    "[A] R Leg": 45,
    "Headband": 46,
    "Eyes": 47,
    "Beard": 48,
    "Mouth": 49,
    "Neck": 50,
    "Ring": 51,
    "Scalp": 52,
    "Decapitation": 53,
    "Unnamed 54": 54,
    "Unnamed 55": 55,
    "Unnamed 56": 56,
    "Unnamed 57": 57,
    "Unnamed 58": 58,
    "Shield": 59,
    "Pipboy": 60,
    "FX": 61,
    "Head Meatcap": 100,
    "Body Meatcap": 101}

fo4chargen_pat = re.compile("Type[0-9]+")

class FO4BoneDict(BoneDict):
    def chargen_filter(self, candidates):
        return set([c for c in candidates if fo4chargen_pat.search(c)])

fo4Dict = FO4BoneDict(fo4Bones, fo4Expressions, fo4Parts, fo4BoneIDs)
fo4FaceDict = FO4BoneDict(fo4FaceBones, fo4Expressions, fo4Parts, fo4BoneIDs)

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
Vectors and quarternions
""")

    v1 = Vector([1, 2, 3])
    v2 = Vector([4, 5, 6])
    assert v1.dot(v2) == 32, f"Vector dot product works: {v1.dot(v2)}"
    v3 = Vector([1, 0, 0])
    v4 = Vector([0, 1, 0])
    assert v3.cross(v4)[:] == [0, 0, 1], f"Vector cross product works: {v3.cross(v4)}"
    v5 = Vector([1, 1, 0])
    v6 = Vector([-1, 1, 0])
    assert list(map(lambda x: round(x, 4), v5.cross(v6)[:])) == [0, 0, 2], f"Vector cross product works: {v5.cross(v6)}"

    v7 = Vector([.5, 3, 1])
    v8 = Vector([.5000001, 3, 1])
    assert v7 == v8, f"Vector comparison works"

    assert not (Vector([1, 2]) == Vector([1, 2, 3])), f"Vector comparison works 2"
    assert not (Vector([1, 2, 4]) == Vector([1, 2, 3])), f"Vector comparison works 3"

    assert v1.scale(2) == Vector([2, 4, 6]), f"Scaling vectors works: {v1.scale(2)}"

    assert (v1 + v2) == Vector([5, 7, 9]), f"Adding vectors works: {v1 + v2}"

    q5 = Quaternion.make_rotation([2*pi/3, 1, 1, 1]) # Rotate all 3 axes
    v5 = Vector([1, 0, 0]) # Vector on X axis
    r51 = q5.rotate(v5)
    assert r51 == Vector([0, 1, 0]), f"Rotation of axes works 1: {r51}"
    assert q5.rotate(q5.rotate(q5.rotate(v5))) == v5, f"3 rotations returns us home"

    rm5 = RotationMatrix.from_quaternion(q5)
    r52 = rm5.by_vector(v5)
    assert r51 == r52, f"Rotation matrix produces same result as quat"

    r90z = Quaternion.make_rotation([pi/2, 0, 0, 1]) # 90deg about the z axis
    x1 = Vector([1,0,0])
    assert r90z.rotate(x1) == Vector([0,1,0]), f"Can rotate abou tthe z axis"

    print("""
##############################################################################
RotationMatrix provides handling for bone rotations and such.
""")
    rm = RotationMatrix([[-0.0072, 0.9995, -0.0313],
                         [-0.0496, -0.0316, -0.9983],
                         [-0.9987, -0.0056, 0.0498]])
    
    # by_vector creates a rotation matrix from a vector 
    assert rm.by_vector([5,0,0]) == Vector([-0.036, -0.248, -4.9935]), "Error: Applying rotation matrix"

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
    c = a @ b
    assert c == RotationMatrix([(300, 360, 420), (660, 810, 960), (1020, 1260, 1500)]), "Error: Matrix multiplication failure"

    rm5 = RotationMatrix.from_quaternion(q5)
    v = Vector ([1, 0.2, 0.3])
    v1 = rm5.rotate(v)
    v2 = q5.rotate(v)
    assert v1 == v2, f"Rotation by matrix == rotation by quaternion {v1} == {v2}"

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

    print("### Transform inversion works correctly")
    mat = MatTransform((1, 2, 3), [(1,0,0),(0,1,0),(0,0,1)], 2.0)
    imat = mat.invert()
    assert list(mat.translation) == [1,2,3], "ERROR: Source matrix should not be changed"
    assert list(imat.translation) == [-1,-2,-3], "ERROR: Translation should be inverse"
    assert imat.rotation.matrix[1][1] == 1.0, "ERROR: Rotation should be inverse"
    assert imat.scale == 0.5, "Error: Scale should be inverse"

    ### Need to test euler -> matrix -> euler
    ### Don't trust the euler conversion, so make rotation matrix from quat
    q6a = Quaternion.make_rotation([pi/2, 0, 0, 1]) # rotate around z
    q6b = Quaternion.make_rotation([pi/2, 0, 1, 0]) # rotate around y
    m6a = MatTransform([1, 2, 3], RotationMatrix.from_quaternion(q6a))
    m6b = MatTransform([0.1,0.2,0.3], RotationMatrix.from_quaternion(q6b))

    mm = m6a @ m6b
    v1 = Vector([1,0,0])
    
    v1a = m6a @ v1
    v1ab = m6b @ v1a
    vmm = mm @ v1
    # v1ab != vmm because when the MTs are combined the second happens in the transformed
    # coordinates of the first; when one is applied after the other the second happens
    # in world coordinates
    assert v1ab == vmm, f"Vector transforms correct: {v1ab} == {vmm}"



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
    exprmorphs = set(['DialogueAnger', 'MoodFear', 'CombatShout', 'RUprLipDn', 'UprLidUp.R', 'RUprLidDn', 'Smile.L'])
    assert fo4Dict.expression_filter(exprmorphs) == set(['RUprLipDn', 'UprLidUp.R', 'RUprLidDn', 'Smile.L']), "ERROR: FO4 expression filter incorrect"
    assert skyrimDict.expression_filter(exprmorphs) == set(['DialogueAnger', 'MoodFear', 'CombatShout']), "ERROR: Skyrim expression filter incorrect"
    assert fo4Dict.chargen_filter(set(['foo', 'barType1', 'fribble', 'Type45cat', 'aTypeB'])) == set(['barType1', 'Type45cat']), "ERROR: FO4 Chargen filter incorrect"

    assert fo4Dict.morph_dic_game['Smile.L'] == 'LSmile', "ERROR: Morph not translated correctly"
    assert fo4Dict.morph_dic_game['UprLidUp.R'] == 'RUprLidUp', "ERROR: Morph not translated correctly"
    assert fo4Dict.morph_dic_blender['LUprLidUp'] == 'UprLidUp.L', "ERROR: Morph not translated correctly"
    
    print("""
##############################################################################
File handling
""")
    print (">>> Can check that a list of files exists")
    assert check_files([r"tests\FO4\HeadGear1.nif", r"tests\Skyrim\malehead.nif"]), "Expected files exist"
    assert not check_files([r"tests\FO4\HeadGear1.nif", r"tests\Skyrim\maleheadXYZ.nif"]), "Unexpected files don't exist"

    print (">>> Can extend filenames from a shared root")
    flst = extend_filenames("C:/mod/meshes/mesh.nif",
                            "meshes",
                            [r"textures\actors\character\male\MaleHead.dds",
                             r"textures\actors\character\male\MaleHead_msn.dds",
                             "",
                             "",
                             r"textures\actors\character\male\MaleHead_sk.dds"])
    assert flst == ['C:\\mod\\textures\\actors\\character\\male\\MaleHead.dds',
                    'C:\\mod\\textures\\actors\\character\\male\\MaleHead_msn.dds',
                    "", 
                    "", 
                    'C:\\mod\\textures\\actors\\character\\male\\MaleHead_sk.dds'], \
        "Error: Extended filenames incorrect"

    print(">>> Can truncate a fliename to a given root")
    str1 = "C:/mod/stuff/meshes/foo/bar/mesh.tri"
    fn = truncate_filename(str1, "meshes")
    assert fn == "foo/bar/mesh.tri"
    fn2 = truncate_filename(str1, "fribble")
    assert fn2 == str1
    
