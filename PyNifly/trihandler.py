# ***** BEGIN GPL LICENSE BLOCK *****
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <http://www.gnu.org/licenses/>
#
# ***** END GPL LICENCE BLOCK *****
# --------------------------------------------------------------------------
"""
For Blender 2.92 or greater. May work on eariler versions at your own risk.

Code adapted by Bad Dog from tri export/importer
Original author listed as "Core script by kapaer, modvertice support by deedes"
updated by anon (me) to work with newer blender ( version 2.63+), I hope

"""

# File format:
# Header
#   FRTRI003
#   version number
#   vertexNum
#   faceNum
#   uvNum
#   morphNum
#   modMorphNum
#   addVertexNum
# Vertices:
#   (x,y,z) * vertexNum
# Mod vertices:
#   (x,y,z)  * modVertexNum
# Faces:
#   (p1, p2, p3) * faceNum -- points are indices into the vertex list. 3 points to a face (tris)
# UVs:
#   (u,v) * uvNum -- As many UVs as vertices, has to be a 1:1 map
# UV mapping:
#   (uv1, uv2, uv3) * faceNum -- 1:1 with faces, assigns each vertex on a face to a unique UV point
# Morphs * morphNum:
#   name len (int)
#   name (chars)
#   base diff (float) -- scale factor applied to enitre morph
#   (dx,xy,xz) * vertexNum -- offset for each vertex
#   ...
# ModMorphs * modMorphNum:
#   name len
#   name
#   block length
#   mod vert index * block length -- index of vertex affected; this list is 1:1 with mod vertices (maybe?) 


import os
import logging
from struct import (unpack, pack)

VERSION_STRING = 'FRTRI003'
INT_LEN = 4
FLOAT_LEN = 4
SHORT_LEN = 2
ROTATE_X90 = 0

# Header
class TRIHeader:
    def __init__(self):
        self.str = ''			#Header with version number / magic number
        self.vertexNum = 0		#number of vertices on the base mesh
        self.faceNum = 0			#number of faces on the base mesh
        self.morphNum = 0		#number of regular morphs
        self.uvNum = 0			#number of Vectors for the UV on the base mesh
        self.addMorphNum = 0		#number of modifier morphs
        self.addVertexNum = 0	#number of additional vertices for modifier morphs

    def write(self):
        """ Return packed header, ready for writing """
        return pack('<8s14I',	self.str.encode("iso-8859-15"),	#str
            self.vertexNum,			#vertexNum
            self.faceNum,			#faceNum
            0,0,0,				#(unknown)
            self.uvNum,			#uvNum
            1,					#unknown
            self.morphNum,			#morphNum
            self.addMorphNum,		#addMorphNum
            self.addVertexNum,		#addVertexNum
            0,0,0,0)

    def read(self, file):
        """ Read header from file 
             file = open file object
        """
        errlog = logging.getLogger("pynifly")
        try:
            tmp_data = file.read(0x40)
        except ValueError:
            errlog.error("Cannot read header for file")
            raise ValueError("Error reading TRI file")
        data = unpack('<8s10I16x', tmp_data)
        self.str = data[0].decode("iso-8859-15")
        self.vertexNum = data[1]
        self.faceNum = data[2]
        self.uvNum = data[6]
        self.morphNum = data[8]
        self.addMorphNum = data[9]
        self.addVertexNum = data[10]

    def __str__(self):
        s = "TRI Header:\n"
        s += "Base Vertices : " + str(self.vertexNum) + "\n"
        s += "Faces:          " + str(self.faceNum) + "\n"
        s += "UV Coordinates: " + str(self.uvNum) + "\n"
        s += "Morphs:         " + str(self.morphNum) + "\n"
        s += "Mod Morphs:     " + str(self.addMorphNum) + " with " + str(self.addVertexNum) + " vertices\n"
        return s

    def printCollectedData(self, errlog):
        errlog.error(str(self))

class TriFile():
    def __init__(self):
        self.header = TRIHeader()
        self.vertices = None    # [(x,y,z), ...]
        self.faces = None       # [(p1, p2, p3), ...] where p# is an index into vertices
        self.log = logging.getLogger("pynifly")


    def read_morph(self, file):
        """ Reads a single morph from a tri file
            file = file object positioned at start of morph
            returns = (morph-name, [(x,y,z), ...]) list of new vert positions defined by the morph
            """
        morph_index = len(self.morphs) 
        tmp_data = file.read(INT_LEN)
        if len(tmp_data) < INT_LEN:
            self.log.error("EOF reading morph header\nError on morph number " + str(morph_index) + "\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")
        
        data = unpack('<I', tmp_data)
        tmp_data = file.read(data[0])
        if len(tmp_data) < data[0]:
            self.log.error("EOF reading morph header\nError on morph number " + str(morph_index) + "\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")
        
        data = unpack('<'+str(data[0]-1)+'sx', tmp_data)
        morphSubName = data[0].decode("iso-8859-15")
#       newsk.name = morphName
        #self.log.debug(f"Read morph: {morphSubName}")
        
        tmp_data = file.read(FLOAT_LEN)
        
        if len(tmp_data) < FLOAT_LEN:
            self.log.error("EOF reading morph header\nError on morph number " + str(morph_index) + "\n  \"" + morphSubName + "\"\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")
        data = unpack('<f', tmp_data)
        baseDiff = data[0]
        
        tmp_buffer = file.read(SHORT_LEN * 3 * self.header.vertexNum)
        if len(tmp_buffer) < SHORT_LEN * 3 * self.header.vertexNum:
            self.log.error("EOF reading morph data vertices\nError on morph number " + str(morph_index) + "\n  \"" + morphSubName + "\"\nMorph has valid header, but appears to be corrupt\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")		

#        lidx = 0
#        for ii, nv in enumerate(mesh_key_verts):
        # morph_verts = [ (x, y, z), ...] where x,y,z are absolute values
        morph_verts = [] 
        for lidx in range(self.header.vertexNum):
            data = unpack('<3h', tmp_buffer[SHORT_LEN * 3 * lidx : (SHORT_LEN*3*lidx) + (SHORT_LEN*3)]  )
            morph_verts.append((self.vertices[lidx][0] + data[0] * baseDiff,
                                self.vertices[lidx][1] + data[1] * baseDiff,
                                self.vertices[lidx][2] + data[2] * baseDiff) )

            #nv.co[0] = verts_list[ii][0] + data[0] * baseDiff
            #nv.co[1] = verts_list[ii][1] + data[1] * baseDiff
            #nv.co[2] = verts_list[ii][2] + data[2] * baseDiff
            #lidx = lidx + 1
        #ob.data.update()
        
        #tmp_buffer = ''
        return morphSubName, morph_verts


    def read_modmorph(self, file, i, vertsAdd_Index, vertsAdd_list, vertsAdd_listLength, verts_list):
        """ Reads a single mod morph from a tri file. Mod morphs only morph some of the vertices
            file = file object positioned at start of morph
            returns = (morph-name, [(x,y,z), ...]) list of new vert positions defined by the morph
            """
        morph_index = len(self.modmorphs) 

        tmp_data = file.read(INT_LEN)
        if len(tmp_data) < INT_LEN:
            self.log.error("EOF reading MOD-morph header\nError on MOD-morph number " + str(morph_index) + "\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")
        data = unpack('<I', tmp_data)

        tmp_data = file.read(data[0])
        if len(tmp_data) < data[0]:
            self.log.error("EOF reading MOD-morph header\nError on MOD-morph number " + str(morph_index) + "\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")
        data = unpack('<'+str(data[0]-1)+'sx', tmp_data)
        morphSubName = data[0].decode("iso-8859-15")
        self.log.info(f"Read modmorph {morphSubName}")

        tmp_data = file.read(INT_LEN)
        if len(tmp_data) < INT_LEN:
            self.log.error("EOF reading MOD-morph header\nError on MOD-morph number " + str(morph_index) + "\n  \"" + morphSubName + "\"\nFile appears to be corrupt")
            self.header.printCollectedData(self.log)
            raise ValueError("Error reading TRI file")
        data = unpack('<I', tmp_data)
        blockLength = data[0]
        
        if blockLength > 0:
            nextMorphVertIdx = 0
            tmp_buffer = file.read(INT_LEN*blockLength)
            if len(tmp_buffer) < INT_LEN*blockLength:
                self.log.error("EOF reading MOD-morph data verticies\nError on MOD-morph number " + str(i+1) + "\n  \"" + morphSubName + "\"\nMorph has valid header, but appears to be corrupt\nFile appears to be corrupt")
                self.header.printCollectedData(self.log)
                raise ValueError("Error reading TRI file")	
            data = unpack('<I', tmp_buffer[INT_LEN*nextMorphVertIdx:(INT_LEN*nextMorphVertIdx)+INT_LEN])
            
            nextMorphVertIdx += 1
            
            #ii=int increment, nv=vert structure in the keyshape
            new_verts = []
            for ii, nv in enumerate(self.vertices):
                if (data[0] == ii) and (blockLength >= 0) and (vertsAdd_Index < vertsAdd_listLength):
                    blockLength = blockLength - 1
                    new_verts.append((vertsAdd_list[vertsAdd_Index][0],
                                      vertsAdd_list[vertsAdd_Index][1],
                                      vertsAdd_list[vertsAdd_Index][2] ))
#                    nv.co[0] = vertsAdd_list[vertsAdd_Index][0]
#                    nv.co[1] = vertsAdd_list[vertsAdd_Index][1]
#                    nv.co[2] = vertsAdd_list[vertsAdd_Index][2]
                    vertsAdd_Index += 1
                    if blockLength > 0:
                        data = unpack('<I', tmp_buffer[INT_LEN*nextMorphVertIdx:(INT_LEN*nextMorphVertIdx)+INT_LEN])
                        nextMorphVertIdx += 1
                else:
                    new_verts.append(self.vertices[ii])
        
        #Else, the morph is the same as the base mesh? I think.
        else:
            for ii, nv in enumerate(mesh_key_verts):
                new_verts.append((verts_list[ii][0], verts_list[ii][1], verts_list[ii][2]))
        return morphName, new_verts

    def read(self, file):
        """ Read the given tri file 
            file = file object
            header = TRIheader object to use for this import
            returns (obj with shape keys, mesh with vertex locations)
        """
        errlog = logging.getLogger("pynifly")

        # read primary mesh

        # load vertex data
        verts_list = []
        tmp_buffer = file.read(FLOAT_LEN * 3 * self.header.vertexNum)
        if len(tmp_buffer) < FLOAT_LEN * 3 * self.header.vertexNum:
            errlog.error("EOF reading base model verticies - Should read " + str(header.vertexNum) + " verticies with\n" + str(FLOAT_LEN*3*header.vertexNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            self.header.printCollectedData(errlog)
            raise ValueError("Error reading TRI file")
        
        for i in range(self.header.vertexNum):
            data = unpack('<3f', tmp_buffer[FLOAT_LEN * 3 * i : (FLOAT_LEN*3*i) + (FLOAT_LEN*3)])
            verts_list.append((data[0], data[1], data[2]))

        self.vertices = verts_list
        # mesh.vertices.foreach_set("co", unpack_list(verts_list))

        # load modvertice data
        # "modvertice" = morph data sets, where each set need not contain data for every vertex in the mesh
        # Downside is that the structure must specify which vertices are in each set and which vertex each 3D point refers to
        vertsAdd_list = []
        tmp_buffer = file.read(FLOAT_LEN*3*self.header.addVertexNum)
        if len(tmp_buffer) < FLOAT_LEN*3*self.header.addVertexNum:
            errlog.error("\n----=| Tri Import Error |=----\nEOF reading mod-morph vertices\nShould read " + str(self.header.addVertexNum) + " mod verticies with\n" + str(FLOAT_LEN*3*header.addVertexNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            self.header.printCollectedData(errlog)
            raise ValueError("Error reading TRI file")
        
        for i in range(self.header.addVertexNum):
            data = unpack('<3f', tmp_buffer[FLOAT_LEN*3*i:(FLOAT_LEN*3*i)+(FLOAT_LEN*3)])
            vertsAdd_list.append((data[0], data[1], data[2]))

        # loading faces
        self.faces = []
        tmp_buffer = file.read(INT_LEN*3*self.header.faceNum)
        if len(tmp_buffer) < INT_LEN*3*self.header.faceNum:
            errlog.error("\n----=| Tri Import Error |=----\nEOF reading model faces\nShould read " + str(self.header.faceNum) + " faces with\n" + str(INT_LEN*3*self.header.faceNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            self.header.printCollectedData(errlog)
            raise ValueError("Error reading TRI file")

        for i in range(self.header.faceNum):
            data = unpack('<3I', tmp_buffer[INT_LEN*3*i:(INT_LEN*3*i)+(INT_LEN*3)])
            self.faces.append((data[0], data[1], data[2]))

        numFaces = len(self.faces)

        #### Build shape data outside this routine
        ##TRI file is always triangles. Otherwise, the hardcoded 3's below would be incorrect
        #loops_vert_idx = []
        #faces_loop_start = [0] * numFaces 
        #faces_loop_total = [3] * numFaces  
        #lidx = 0
        #for f in faces:
        #    #Even though f is a list of 3 item lists, blender stores 'loops' as per-vertex data in a 1D list, so the foreach_set down below expects them as a 1D list, not
        #    #a 2D list. So the length of loops_vert_idx list should be len(faces)*3   "Extend" adds elements to the end of an array, "append" appends the object.
        #    #So  a = [1,2,3] ----  a.append( (5,6,7) )  a = [1,2,3,(5,6,7)] and len(a)=4  | whereas | a.extend( (5,6,7) )  a = [1,2,3,5,6,7] and len(a) = 6
        #    loops_vert_idx.extend(f)
        #    faces_loop_start[lidx] = lidx * 3
        #    lidx += 1

    ##    mesh.polygons.add(numFaces)
    ##    mesh.loops.add(numFaces*3)
    ##    mesh.loops.foreach_set("vertex_index", loops_vert_idx)
    ##    mesh.polygons.foreach_set("loop_start", faces_loop_start)
    ##    mesh.polygons.foreach_set("loop_total", faces_loop_total)

        # del faces

        #self.loops_vert_idx = loops_vert_idx
        #self.faces_loop_start = faces_loop_start
        #self.faces_loop_total = faces_loop_total

        # UV
        # mesh.uv_textures.new()

        self.uv_pos = []
        tmp_buffer = file.read(FLOAT_LEN*2 * self.header.uvNum)
        if len(tmp_buffer) < FLOAT_LEN*2*self.header.uvNum:
            errlog.error("\n----=| Tri Import Error |=----\nEOF reading UV Coordinates\nShould read " + str(self.header.uvNum) + " UVs with \n" + str(FLOAT_LEN*2*self.header.uvNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            self.header.printCollectedData(errlog)
            raise ValueError("Error reading TRI file")

        for i in range(self.header.uvNum):
            data = unpack('<2f', tmp_buffer[FLOAT_LEN*2*i:(FLOAT_LEN*2*i)+(FLOAT_LEN*2)])
            self.uv_pos.append((data[0], 1-data[1])) # Inverting "V" to match what we get from nifs

        numUV = len(self.uv_pos)

        #I'm assuming that tri files will always have 1 UV per vertex, but i wasn't able to conirm this for sure.. so:
        if numUV != len(verts_list):
            errlog.error("\n----=| Tri Import Error |=----\nNumber of verticies differs from number of UV coordinates\nTRI file has valid header, but file appears to be corrupt\n   !! Since \'Base Verticies\' != \'UV Coordinates\', file is probably corrupt.\nHowever, if TRI file is *not* corrupted, then it is possible that Author\'s\nassertion regarding TRI files always correlating V and UV array indices\nmight be wrong.\n   Probably should post if you see this error and are sure file is not corrupt")
            self.header.printCollectedData(errlog)
            raise ValueError("Error reading TRI file")

        # NOTE --- For future reference. UV's are placed "on a vertex" but indirectly. Each loop contains one vertex index that is supposed to be tied into
        # a polygon face (there will be face*3 loops for a triangulated mesh) and each "loop" contains the uv. This allows for things like smoothing since a
        # single vertex item can have different data depending on the face being looked at ("coming from a different direction").
        #     therefore, the "loop_indices" can be misleading. This is NOT "The face-vertex index" but is an index into the loop array itself. To get the actual
        # vertex index out of the face (the colleciton of 3+ loops), you must dereference the loop as well. So mesh.loops[mesh.polygons.loop_indices[0]].vertex_index
        #     HOEWEVER, TRI files are of the style where, when a vertex at a locaiton needes alternate info (differnt UV), the vertex is just duplicated. So, even
        # a vertex location needs more than one set of data, each vertex only has one set of data.
        #     Meanwhile, the uv_layers has the uv coordinates in the same indexing order as mesh.loops. So, uv_layers[0].data[5].uv is intended to be the uv
        # coordinates of loop number 5 in mesh.loops, and that is how uv are "placed" on vertex (the vertex of a particular face)
        #

        tmp_buffer = file.read(INT_LEN * 3 * numFaces)
        if len(tmp_buffer) < INT_LEN * 3 * numFaces:
            errlog.error("EOF reading Face Vertex Index to UV Index array - should have " + str(len(mesh.polygons)) + " indicies with \n" + str(INT_LEN*3*len(mesh.polygons)) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            self.header.printCollectedData(errlog)
            raise ValueError("Error reading TRI file")

        # face_uvs array: For each face we have 3 (u,v) locations (3 cuz faces are triangles)
        ### do we need this?
        self.face_uvs = [] 
        for lidx in range(numFaces):
#        lidx = 0
#        for i in mesh.polygons:
            data = unpack('<3I', tmp_buffer[INT_LEN*3*lidx:(INT_LEN*3*lidx)+(INT_LEN*3)])
            self.face_uvs.append([(self.uv_pos[data[0]][0], self.uv_pos[data[0]][1]),
                                  (self.uv_pos[data[1]][0], self.uv_pos[data[1]][1]),
                                  (self.uv_pos[data[2]][0], self.uv_pos[data[2]][1]) ])
            
        #    mesh.uv_layers[0].data[ i.loop_indices[0] ].uv = [ uv_pos[data[0]][0], uv_pos[data[0]][1] ]
        #    mesh.uv_layers[0].data[ i.loop_indices[1] ].uv = [ uv_pos[data[1]][0], uv_pos[data[1]][1] ]
        #    mesh.uv_layers[0].data[ i.loop_indices[2] ].uv = [ uv_pos[data[2]][0], uv_pos[data[2]][1] ]
        #    lidx = lidx + 1

        #del uv_pos

        #Create base shape key
#        newsk = ob.shape_key_add()
        #Important for new blender! Default key is a temporal thing
#        mesh.shape_keys.use_relative=True
#        newsk.name = "Base Shape"
#        ob.data.update()

        self.morphs = {}
        self.morphs['Basis'] = self.vertices

        # read morph data
        if self.header.morphNum > 0:
            for i in range(self.header.morphNum):
#                newsk = ob.shape_key_add()
                #Early versions of blender seem to have a bug where the shape key isn't "applied" until it has been active once
                #not doing this doesn't break anything, but if the user adjusts sliders without actually first highlighting a shape key, the sliders
                #won't work
#                ob.active_shape_key_index = len(mesh.shape_keys.key_blocks) - 1
                #This is a pointer, not a copy
#                mesh_key_verts = mesh.shape_keys.key_blocks[len(mesh.shape_keys.key_blocks) - 1].data
                name, verts = self.read_morph(file)
                self.morphs[name] = verts

        self.modmorphs = {}
                
        # read additional morph data
        if self.header.addMorphNum > 0:
            vertsAdd_Index = 0
            vertsAdd_listLength = len(vertsAdd_list)

            for i in range(self.header.addMorphNum):
                #vertsAdd_Index = self.read_modmorphs(errlog, file, i, vertsAdd_Index, vertsAdd_list, vertsAdd_listLength, verts_list)
                name, verts = self.read_modmorph(file)
                self.modmorphs[name] = verts


    @classmethod
    def from_file(cls, filepath):
        """ Read tris from the given file """
        log = logging.getLogger("pynifly")
        log.level = logging.DEBUG
        log.info(f"Reading tris from {filepath}")

        filename = os.path.basename(filepath)
        file = open(filepath,'rb')
        tri = TriFile()

        # read header
        try:
            tri.header.read(file)
        except ValueError:
            file.close()
            log.error("Cannot read header from file")
            return {'CANCELLED'}

        # version check
        if tri.header.str != VERSION_STRING:
            file.close()
            log.error(f"TRI file is not of correct format. Format given as [{fileHeader.str}] when it should be [FRTRI003]")
            return {'CANCELLED'}

        # options
        #importMenu()

        ## import object
        #scn= bpy.context.scene
        #mesh = bpy.data.meshes.new(filename)
        #ob = bpy.data.objects.new(mesh.name, mesh)

        try:
            tri.read(file)
        except ValueError:
            file.close()
            log.exception("Error importing Tri File")
            return {'CANCELLED'}		

        file.close()

        #If blender version is >= 2.74
        #I'm not entirely sure what the consequence of the possible clearing of custom data might be. Potentially not working, heh.. Might also have no problem
        #I think just losing custom normals and such, so in this case doesn't really matter
        #mesh.validate()
        #mesh.update()

        #ob = bpy.context.scene.objects.link(ob)
        #scn.update()
        #return {'FINISHED'}

        return tri


def write_mesh(ob, scn, filename, filepath, reorder_verts):
    """ Write out an object's tris """
    header = TRIHeader()
    errlog = logging.getLogger("pynifly")

    mesh = ob.to_mesh(scn, False, 'PREVIEW', False, False)

    p = re.compile('(.*) \\[\\d+\\]$')	# extract the morph's name
    q = re.compile('(.*) \\(\\d+\\)$')	# extract the modifier's name

    # obtain the face data
    faces = mesh.polygons

    if (faces == None) or (len(faces) == 0):
        errlog.error(f"Error exporting tris from {ob.name}: Mesh has no faces")
        raise ValueError("Error creating tri file")

    if mesh.shape_keys:
        shapeKeys = mesh.shape_keys.key_blocks
        verts = shapeKeys[0].data			#Base shape's data
    else:
        errlog.error(f"Error exporting tris from {ob.name}: Mesh has no shape keys")
        raise ValueError("Error creating tri file")

    if (verts == None) or (len(verts) == 0):
        errlog.error(f"Error exporting tris from {ob.name}: Mesh has no vertices")
        raise ValueError("Error creating tri file")

    header.vertexNum = len(verts)
    header.faceNum = len(faces)
    header.str = VERSION_STRING

    if (len(mesh.uv_layers) == 0):
        errlog.error(f"Error exporting tris from {ob.name}: Mesh has no UV layer")
        raise ValueError("Error creating tri file")
    
    if (len(mesh.uv_layers) > 1):
        errlog.error(f"Error exporting tris from {ob.name}: Mesh has more than one UV layer")
        raise ValueError("Error creating tri file")

    #Mapping for re-order of vierts to  match a 'sequential face list' index = vertex index, value = index to remap to
    #verts_reorder_mapping will be referenced everwhere in the script, just that only if re-rdering is selcted is the mapping not v#:v#
    if reorder_verts:
        verts_reorder_mapping = [-1 for v in verts]
        current_v_position = 0
        for f_index, f in enumerate(faces):
            #f_vert is the 1st, 2nd, or 3rd index of the face
            for f_vert, loop_index in enumerate(f.loop_indices):
                if f_vert > 2:
                    errlog.error(f"Error exporting tris from {ob.name}: Mesh has faces with more than 3 verts")
                    raise ValueError("Error creating tri file")

                vert_idx = mesh.loops[loop_index].vertex_index
                #if this vertex has not already been remapped, remap it
                if verts_reorder_mapping[vert_idx] == -1:
                    verts_reorder_mapping[vert_idx] = current_v_position
                    current_v_position = current_v_position + 1
    else:
        verts_reorder_mapping = [v_idx for v_idx, v in enumerate(verts)]

    #Not a good idea to pack long strings repeatedly
    modHeaderArrayToPack = []
    modVerticeArrayToPack = []
    morphKeysArrayToPack = []
    morphKeysDiffValuesArrayToPack = []

    modHeaderPacked		= b''	#string to collect the header data
    modVerticePacked	= b''	#string to collect the vertice data
    morphKeysPacked		= b''	#string to collect the morph key data to write


    if shapeKeys: # Should always be true
        morphNameList =[] #Holds a list of previously processed morph names to check for duplicates
        fullMorphNameList =[] #Only full morph names
        modMorphNameList =[] #Only mod-morph names
        
        for i in range(len(shapeKeys) - 1):		#goes thru all shape keys
            #Important! Loop index correction. Basis morph is key = 0, we want to work with 1 through length)
            i = i + 1
            morphName = shapeKeys[i].name		#gets the key's name
            m = p.match(morphName)		#grabs the name and looks if it matches a regular morph
            n = q.match(morphName)		#the same, just for modifiers ("add morph" or "mod morph")
            shape_verts =  shapeKeys[i].data	#gets the shape key's data
            verts_diff = [[] for v in verts]		#list to save vertices to
            if m:
                header.morphNum += 1
                morphName = m.group(1)
                max_diff = 0
                for names in morphNameList:
                    if morphName == names:
                        errlog.error("\n----=| Tri Export Error |=----\nError exporting \'%s\' as TRI:\nDuplicate shape key name found:\n\"%s\"", ob.name, morphName)
                        raise ValueError("Error creating TRI file")
                fullMorphNameList.append(morphName)
                #The TRI format saves the offset data in a 'normalized' form. The largets difference is used as a factor to apply to all the offset values
                #So, the largest difference needs to be found
                vert_idx = 0
                for nv, bv in zip(shape_verts, verts):
                    data = [nv.co[0] - bv.co[0], nv.co[1] - bv.co[1], nv.co[2] - bv.co[2]]
                    if abs(data[0]) > max_diff:
                        max_diff = abs(data[0])
                    if abs(data[1]) > max_diff:
                        max_diff = abs(data[1])
                    if abs(data[2]) > max_diff:
                        max_diff = abs(data[2])
                    verts_diff[verts_reorder_mapping[vert_idx]] = data.copy()
                    vert_idx = vert_idx + 1

                #7fff=max signed integer value for 16 bits = 32767. I guess, dunno why it was like this, but I like hex. Frogs everywhere.
                diff_base = max_diff / 0x7fff
                
                #If the diff is 0, then the morph and the base are identical. That's fine, but the normalization factor shouldn't be 0!
                #Another way to do this would be to just set all the diff values to 0 in the loop below. They should, indeed, all be 0
                #since v[0-2] will all be 0 since the difference calculated above was all exactly 0 or below precision of float.
                #This effectively adds a built-in floor to the amount of offset the export will allow, but I don't think rendering programs will
                #genreally allow that level of precision anyway, heh
                if diff_base == 0: 
                    diff_base = 1
                morphKeysDiffValuesArrayToPack.append( float(diff_base) )

                i = 0
                while i < len(verts_diff):
                    verts_diff[i][0] = int(verts_diff[i][0]/diff_base)
                    verts_diff[i][1] = int(verts_diff[i][1]/diff_base)
                    verts_diff[i][2] = int(verts_diff[i][2]/diff_base)

                    i = i + 1

                morphKeysArrayToPack.append( verts_diff.copy() )

            #The data structures and variables in this are redundant.. oh well
            elif n:
                header.addMorphNum += 1
                morphName = n.group(1)
                for names in morphNameList:
                    if morphName == names:
                        errlog.error("\n----=| Tri Export Error |=----\nError exporting \'%s\' as TRI:\nDuplicate shape key name found:\n\"%s\"", ob.name, morphName)
                        raise ValueError("Error creating TRI file")
                morphNameList.append(morphName)
                modMorphNameList.append(morphName)
                verticeCount 	= 0	#keeps track of the number of vertices
                verticeAdded	= 0	#keeps track of the number of vertices which were actually added to the additional vertex list
                for nv, mv in zip(shape_verts, verts):
                    div = abs(nv.co[0] - mv.co[0]) + abs(nv.co[1] - mv.co[1]) + abs(nv.co[2] - mv.co[2]) / 3
                    if div > 0.00033:		#filter out the vertices which are too similiar to the base mesh
                        data = [nv.co[0], nv.co[1], nv.co[2], verts_reorder_mapping[verticeCount]]
                        verts_diff[verts_reorder_mapping[verticeCount]] = data.copy()
                        header.addVertexNum += 1
                        verticeAdded += 1
                    verticeCount += 1

                modHeaderArrayToPack.append( [] )
                modVerticeArrayToPack.append( [] )

                modHeaderArrayToPack[header.addMorphNum-1].append( int(verticeAdded) )

                #modHeaderPacked is the list of vertex indices referencing the base model array. The index into this list is the same as the index into
                #the list of actual mod vertices (modVerticePacked). It indicates to which vertex in the base model the offset given in the modVerticePacked
                #applies
                for v in verts_diff:
                    if v != []:
                        modHeaderArrayToPack[header.addMorphNum-1].append( int(v[3]) )
                        modVerticeArrayToPack[header.addMorphNum-1].append( [float(v[0]), float(v[1]), float(v[2])] )

            #Else, the shapekey name did not have the correct format []'s or ()'s.
            else:	
                errlog.error("\n----=| Tri Export Error |=----\nError exporting \'%s\' as TRI:\nshape key does not have the correct name format:\n\"%s\"\nAll shapekey names must have the format:\n  Full Morph:  \"Name [#]\"\n  Mod Morph:   \"Name (#)\"\nSee the plugin header comments for details", ob.name, morphName)
                raise ValueError("Error creating TRI file")

    #Pack Morph
    for morphNum, diffValue in enumerate(morphKeysDiffValuesArrayToPack):
        morphKeysPacked += pack('<I'+ str(len(fullMorphNameList[morphNum])) +'sx', len(fullMorphNameList[morphNum])+1, fullMorphNameList[morphNum].encode("iso-8859-15") )
        morphKeysPacked += pack('<f', diffValue)
        morphKeysPacked += pack('<' + str(len(morphKeysArrayToPack[morphNum])*3) + 'h', *[k for j in morphKeysArrayToPack[morphNum] for k in j] )

    #Pack Mod-Morph
    for morphNum, headerArray in enumerate(modHeaderArrayToPack):
        modHeaderPacked += pack('<I'+ str(len(modMorphNameList[morphNum])) +'sx', len(modMorphNameList[morphNum])+1, modMorphNameList[morphNum].encode("iso-8859-15") )
        modHeaderPacked += pack('<I', headerArray[0] )
        modHeaderPacked += pack('<' + str( len(headerArray)-1 ) + 'I', *headerArray[1:]  )
        modVerticePacked += pack('<' + str(len(modVerticeArrayToPack[morphNum])*3) + 'f', *[k for j in modVerticeArrayToPack[morphNum] for k in j] )


    #anon says: I think I understand what the original script was doing, but not entirely. As far as I know, the uv should just be in the same order as the
    #vertices, vertex 1 has uv at index 1, and so forth. The data will be constructed the same way here. There will always be numuv = num verts.. I hope.
    uvDataPacked = b''
    uv_face_mapping = [[0,0,0] for f in faces]
    uv_gather = [[0.0, 0.0] for v in verts]
    for f_index, f in enumerate(faces):
        #mesh.uv_layers[0].data[ mesh.loops[f.loop_start].vertex_index
        for uv_index, i in enumerate(f.loop_indices):
            if uv_index > 2:
                errlog.error("\n----=| Tri Export Error |=----\nError exporting \'%s\' as TRI:\nSelected mesh has faces with more than three vertices.\nTRI file requires only triangle polygons.", ob.name)
                raise ValueError("Error creating TRI file")			
            uv_face_mapping[f_index][uv_index] = verts_reorder_mapping[mesh.loops[i].vertex_index]
            uv_gather[verts_reorder_mapping[mesh.loops[i].vertex_index]] = mesh.uv_layers[0].data[i].uv

    #It is not len-1, range already compensates for that. There are "5 items" so there are 5 iterations of 0 - 4. Not "go
    #up to the number 5" as when just checking a loop index.
    for i in range(len(uv_gather)):
        uvDataPacked += pack('<2f', uv_gather[i][0], uv_gather[i][1])


    header.uvNum = len(uv_gather)
    del uv_gather


    # vertex packing
    vertexDataPacked = b''
    verts_to_pack = [[] for v in verts]
    i = 0
    for v in verts:
        verts_to_pack[verts_reorder_mapping[i]] = [v.co[0], v.co[1], v.co[2]]
        i = i + 1
    for vco in verts_to_pack:
        tmp_data = pack('<3f', vco[0], vco[1], vco[2])
        vertexDataPacked += tmp_data
    
    # face packing
    faceDataPacked = b''
    for f in faces:
        faceDataPacked += pack('<3I', verts_reorder_mapping[mesh.loops[f.loop_indices[0]].vertex_index], verts_reorder_mapping[mesh.loops[f.loop_indices[1]].vertex_index], verts_reorder_mapping[mesh.loops[f.loop_indices[2]].vertex_index])


    faceNumDataPacked = b''
    for i in range(header.faceNum):
        faceNumDataPacked +=  pack('<3I', uv_face_mapping[i][0], uv_face_mapping[i][1], uv_face_mapping[i][2])

    # start writing...
    try:
        file = open(filepath,'wb')
    except:
        errlog.error("\n----=| Tri Export Error |=----\nError exporting \'%s\' as TRI:\nFailed to create output file. Permission problems? Disk full?", ob.name)
        raise ValueError("Error creating TRI file")
    file.write(header.write()
                    + vertexDataPacked
                    + modVerticePacked
                    + faceDataPacked
                    + uvDataPacked
                    + faceNumDataPacked
                    + morphKeysPacked
                    + modHeaderPacked)
    file.close()

if __name__ == "__main__":
    test_path = r"D:\OneDrive\Dev\PyNifly\PyNifly\Tests"
    log = logging.getLogger("pynifly")
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s-%(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    TEST_ALL = True

    if TEST_ALL:
        log.info("Importing tri")
        t = TriFile.from_file(os.path.join(test_path, "FO4/CheetahMaleHead.tri"))
        assert len(t.vertices) == 5315, "Error: Should have expected vertices"
        assert len(t.vertices) == t.header.vertexNum, "Error: Should have expected vertices"
        assert len(t.faces) == 9400, "Error should have expected polys"
        assert len(t.uv_pos) == len(t.vertices), "Error: Should have expected number of UVs"
        assert len(t.face_uvs) == t.header.faceNum, "Error should have expected number of face UVs"
        assert len(t.morphs) > 0, "Error: Should have morphs"
        print("DONE")
